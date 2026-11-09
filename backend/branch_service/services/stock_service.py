# backend/branch_service/services/stock_service.py
"""
Stock Service: Quản lý giao dịch kho cục bộ tại Chi nhánh
Đặc tính kỹ thuật cốt lõi:
1. Concurrency Control: Kiểm soát tranh chấp bằng Row Locking (UPDLOCK) kết hợp Mutex Threading Lock.
2. Idempotency: Khóa chống trùng lặp dựa trên reference_id (At-Most-Once semantics).
3. Outbox Pattern: Ghi đồng thời biến động kho và OutboxEvent trong cùng 1 Local Transaction.
"""
import json
import logging
import threading
import uuid
from sqlalchemy.orm import Session
from ..models import LocalInventory, StockLedger, OutboxEvent

logger = logging.getLogger("StockService")

# Khóa luồng toàn cục bảo vệ giao dịch cục bộ chống Race Condition
_stock_mutex = threading.RLock()

class StockService:
    def __init__(self, branch_code: str):
        self.branch_code = branch_code

    def _queue_outbox_event(self, db: Session, routing_key: str, event_type: str, data: dict):
        """Lưu sự kiện vào bảng Outbox trong cùng transaction"""
        payload = {
            "event_type": event_type,
            "data": data
        }
        outbox_item = OutboxEvent(
            routing_key=routing_key,
            payload=json.dumps(payload, ensure_ascii=False),
            is_published=False
        )
        db.add(outbox_item)

    def _queue_inventory_sync(self, db: Session, sku: str, avail: int, reserved: int):
        """Ghi outbox để đồng bộ về HQ Global Inventory Snapshot"""
        data = {
            "branch_code": self.branch_code,
            "sku": sku,
            "available_qty": avail,
            "reserved_qty": reserved
        }
        self._queue_outbox_event(db, "evt.inventory.updated", "EVT_INVENTORY_UPDATED", data)

    def reserve_stock(self, db: Session, sku: str, quantity: int, reference_id: str, transfer_id: str) -> bool:
        """
        Khóa giữ hàng tạm thời cho điều chuyển
        UPDLOCK / Optimistic check: available >= quantity
        """
        with _stock_mutex:
            # 1. Chống trùng lặp (Idempotency check)
            existing = db.query(StockLedger).filter(StockLedger.reference_id == reference_id).first()
            if existing:
                logger.info(f"[{self.branch_code}] Request {reference_id} đã xử lý trước đó. Bỏ qua.")
                return True

            # 2. Khóa dòng bản ghi tồn kho
            inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).with_for_update().first()
            if not inv or inv.available_qty < quantity:
                logger.warning(f"[{self.branch_code}] Không đủ hàng để giữ: SKU={sku}, Cần={quantity}, Có={inv.available_qty if inv else 0}")
                # Bắn sự kiện thất bại ra Outbox
                self._queue_outbox_event(
                    db, "evt.transfer.reserve_failed", "EVT_RESERVE_FAILED",
                    {"transfer_id": transfer_id, "source_branch": self.branch_code, "sku": sku, "reason": "Tồn kho khả dụng không đủ"}
                )
                db.commit()
                return False

            # 3. Cập nhật tồn kho
            inv.available_qty -= quantity
            inv.reserved_qty += quantity
            inv.version += 1

            # 4. Ghi sổ cái
            ledger = StockLedger(
                reference_id=reference_id,
                sku=sku,
                change_type="RESERVE",
                quantity=quantity
            )
            db.add(ledger)

            # 5. Ghi Outbox thông báo đã khóa thành công
            self._queue_outbox_event(
                db, "evt.transfer.reserved", "EVT_STOCK_RESERVED",
                {"transfer_id": transfer_id, "source_branch": self.branch_code, "sku": sku, "quantity": quantity}
            )
            self._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)

            db.commit()
            logger.info(f"[{self.branch_code}] KHÓA HÀNG THÀNH CÔNG: SKU={sku}, Qty={quantity}, Ref={reference_id}")
            return True

    def commit_out(self, db: Session, sku: str, quantity: int, reference_id: str, transfer_id: str) -> bool:
        """Tất toán xuất kho chuyển đi (Trừ reserved_qty)"""
        with _stock_mutex:
            existing = db.query(StockLedger).filter(StockLedger.reference_id == reference_id).first()
            if existing:
                return True

            inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).with_for_update().first()
            if inv:
                inv.reserved_qty = max(0, inv.reserved_qty - quantity)
                inv.version += 1

            ledger = StockLedger(
                reference_id=reference_id,
                sku=sku,
                change_type="COMMIT_OUT",
                quantity=quantity
            )
            db.add(ledger)
            if inv:
                self._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)

            db.commit()
            logger.info(f"[{self.branch_code}] TẤT TOÁN XUẤT KHO: SKU={sku}, Qty={quantity}")
            return True

    def release_reserve(self, db: Session, sku: str, quantity: int, reference_id: str, transfer_id: str) -> bool:
        """GIAO DỊCH BÙ TRỪ (Compensating Transaction): Hoàn lại tồn kho cho kho nguồn khi điều chuyển bị hủy"""
        with _stock_mutex:
            existing = db.query(StockLedger).filter(StockLedger.reference_id == reference_id).first()
            if existing:
                return True

            inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).with_for_update().first()
            if inv:
                inv.reserved_qty = max(0, inv.reserved_qty - quantity)
                inv.available_qty += quantity
                inv.version += 1

            ledger = StockLedger(
                reference_id=reference_id,
                sku=sku,
                change_type="RELEASE_RESERVE",
                quantity=quantity
            )
            db.add(ledger)

            # Phát sự kiện EVT_STOCK_RELEASED
            self._queue_outbox_event(
                db, "evt.transfer.released", "EVT_STOCK_RELEASED",
                {"transfer_id": transfer_id, "source_branch": self.branch_code, "sku": sku, "quantity": quantity}
            )
            if inv:
                self._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)

            db.commit()
            logger.info(f"[{self.branch_code}] BÙ TRỪ THÀNH CÔNG: Đã hoàn trả {quantity} sản phẩm {sku} về available_qty")
            return True

    def transfer_in(self, db: Session, sku: str, quantity: int, reference_id: str, transfer_id: str) -> bool:
        """Kho đích nhận hàng điều chuyển thành công: available_qty += quantity"""
        with _stock_mutex:
            existing = db.query(StockLedger).filter(StockLedger.reference_id == reference_id).first()
            if existing:
                return True

            inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).with_for_update().first()
            if not inv:
                inv = LocalInventory(sku=sku, available_qty=quantity, reserved_qty=0, version=1)
                db.add(inv)
            else:
                inv.available_qty += quantity
                inv.version += 1

            ledger = StockLedger(
                reference_id=reference_id,
                sku=sku,
                change_type="TRANSFER_IN",
                quantity=quantity
            )
            db.add(ledger)

            # Bắn sự kiện EVT_TRANSFER_COMPLETED
            self._queue_outbox_event(
                db, "evt.transfer.completed", "EVT_TRANSFER_COMPLETED",
                {"transfer_id": transfer_id, "dest_branch": self.branch_code, "sku": sku, "quantity": quantity}
            )
            self._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)

            db.commit()
            logger.info(f"[{self.branch_code}] NHẬP KHO ĐIỀU CHUYỂN: SKU={sku}, Qty={quantity}, Đã phát EVT_TRANSFER_COMPLETED")
            return True

    def adjust_stock(self, db: Session, sku: str, change_type: str, quantity: int, reference_id: str, partner_name: str = None, note: str = None) -> dict:
        """Tự trị cục bộ (Local Autonomy): Nhập kho mua mới hoặc Xuất bán lẻ độc lập tại chỗ"""
        with _stock_mutex:
            existing = db.query(StockLedger).filter(StockLedger.reference_id == reference_id).first()
            if existing:
                inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).first()
                return {"status": "SUCCESS", "is_duplicate": True, "available_qty": inv.available_qty if inv else 0}

            inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).with_for_update().first()
            if change_type == "LOCAL_OUT":
                if not inv or inv.available_qty < quantity:
                    return {"status": "FAILED", "reason": "Tồn kho không đủ để xuất bán"}
                inv.available_qty -= quantity
                inv.version += 1
            elif change_type == "LOCAL_IN":
                if not inv:
                    inv = LocalInventory(sku=sku, available_qty=quantity, reserved_qty=0, version=1)
                    db.add(inv)
                else:
                    inv.available_qty += quantity
                    inv.version += 1
            else:
                return {"status": "FAILED", "reason": "Loại thao tác không hợp lệ"}

            ledger = StockLedger(
                reference_id=reference_id,
                sku=sku,
                change_type=change_type,
                quantity=quantity,
                partner_name=partner_name,
                note=note
            )
            db.add(ledger)
            self._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)
            db.commit()

            logger.info(f"[{self.branch_code}] TỰ TRỊ CỤC BỘ ({change_type}): SKU={sku}, Qty={quantity}, Tồn mới={inv.available_qty}")
            return {"status": "SUCCESS", "is_duplicate": False, "available_qty": inv.available_qty}

    def audit_stock(self, db: Session, sku: str, actual_qty: int, note: str = "Kiểm kê định kỳ") -> dict:
        """Kiểm kê số lượng thực tế và điều chỉnh chênh lệch tồn kho (Inventory Stock-taking)"""
        with _stock_mutex:
            inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).with_for_update().first()
            if not inv:
                inv = LocalInventory(sku=sku, available_qty=actual_qty, reserved_qty=0, version=1)
                db.add(inv)
                variance = actual_qty
                old_qty = 0
            else:
                old_qty = inv.available_qty
                variance = actual_qty - old_qty
                inv.available_qty = actual_qty
                inv.version += 1

            ref_id = f"AUDIT-{uuid.uuid4().hex[:10].upper()}"
            ledger = StockLedger(
                reference_id=ref_id,
                sku=sku,
                change_type="AUDIT_ADJUST",
                quantity=variance,
                note=f"{note} (Sổ sách: {old_qty}, Thực tế: {actual_qty}, Chênh lệch: {variance:+d})"
            )
            db.add(ledger)
            self._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)
            db.commit()

            logger.info(f"[{self.branch_code}] KIỂM KÊ KHO: SKU={sku}, Cũ={old_qty}, Mới={actual_qty}, Lệch={variance:+d}")
            return {
                "status": "SUCCESS",
                "sku": sku,
                "old_qty": old_qty,
                "actual_qty": actual_qty,
                "variance": variance,
                "reference_id": ref_id
            }
