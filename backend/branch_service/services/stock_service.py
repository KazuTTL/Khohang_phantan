# backend/branch_service/services/stock_service.py
"""
Stock Service: Quản lý giao dịch kho cục bộ tại Chi nhánh
Đặc tính kỹ thuật cốt lõi:
1. Concurrency Control: Kiểm soát tranh chấp bằng Row Locking (UPDLOCK) kết hợp Mutex Threading Lock.
2. Idempotency: Khóa chống trùng lặp dựa trên reference_id (At-Most-Once semantics).
3. Outbox Pattern: Ghi đồng thời biến động kho và OutboxEvent (SU_KIEN_DONG_BO) trong cùng 1 Local Transaction.
4. Phiếu Kho & Đơn hàng: Ghi nhận đồng thời GIAO_DICH_KHO, CHI_TIET_GIAO_DICH (ton_sau_giao_dich), DON_HANG, CHI_TIET_DON_HANG.
"""
import json
import logging
import threading
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from ..models import (
    LocalProduct,
    LocalInventory,
    StockLedger,
    OutboxEvent,
    WarehouseTransaction,
    WarehouseTransactionDetail,
    CustomerOrder,
    CustomerOrderDetail,
)

logger = logging.getLogger("StockService")

# Khóa luồng toàn cục bảo vệ giao dịch cục bộ chống Race Condition
_stock_mutex = threading.RLock()


class StockService:
    def __init__(self, branch_code: str):
        self.branch_code = branch_code

    def _classify_outbox_type(self, routing_key: str) -> str:
        if "transfer" in routing_key:
            return "SAGA_STOCK_TRANSFER"
        if "inventory" in routing_key:
            return "SYNC_INVENTORY"
        return "SYNC_TRANSACTION"

    def _queue_outbox_event(self, db: Session, routing_key: str, event_type: str, data: dict):
        """Lưu sự kiện vào bảng SU_KIEN_DONG_BO (Outbox_Events) trong cùng transaction"""
        payload = {
            "event_type": event_type,
            "data": data
        }
        outbox_item = OutboxEvent(
            branch_code=self.branch_code,
            event_type=self._classify_outbox_type(routing_key),
            routing_key=routing_key,
            payload=json.dumps(payload, ensure_ascii=False),
            delivery_status="PENDING",
            retry_count=0,
            is_published=False
        )
        db.add(outbox_item)

    def _queue_inventory_sync(self, db: Session, sku: str, avail: int, reserved: int):
        """Ghi outbox để đồng bộ về HQ Global Inventory Snapshot (TONG_HOP_TON_KHO)"""
        data = {
            "branch_code": self.branch_code,
            "sku": sku,
            "available_qty": avail,
            "reserved_qty": reserved
        }
        self._queue_outbox_event(db, "evt.inventory.updated", "EVT_INVENTORY_UPDATED", data)

    def _record_warehouse_transaction(
        self,
        db: Session,
        tx_type: str,
        items: List[Dict[str, Any]],
        prefix: str = "GD",
        status: str = "HOAN_THANH",
        counterpart_branch: Optional[str] = None,
        saga_transfer_id: Optional[str] = None,
        note: Optional[str] = None,
        created_by: str = "system"
    ) -> WarehouseTransaction:
        """Ghi phiếu vào bảng GIAO_DICH_KHO và các dòng CHI_TIET_GIAO_DICH (ton_sau_giao_dich)"""
        date_str = datetime.utcnow().strftime("%Y%m%d")
        short_id = uuid.uuid4().hex[:6].upper()
        receipt_code = f"{prefix}-{self.branch_code}-{date_str}-{short_id}"
        tx = WarehouseTransaction(
            transaction_id=str(uuid.uuid4()),
            branch_code=self.branch_code,
            receipt_code=receipt_code,
            transaction_type=tx_type,
            counterpart_branch=counterpart_branch,
            saga_transfer_id=saga_transfer_id,
            created_by=created_by,
            status=status,
            note=note
        )
        db.add(tx)
        for item in items:
            detail = WarehouseTransactionDetail(
                detail_id=str(uuid.uuid4()),
                transaction_id=tx.transaction_id,
                branch_code=self.branch_code,
                sku=item["sku"],
                quantity=item["signed_qty"],
                post_transaction_balance=item["post_balance"]
            )
            db.add(detail)
        return tx

    def reserve_stock(self, db: Session, sku: str, quantity: int, reference_id: str, transfer_id: str, dest_branch: Optional[str] = None) -> bool:
        """
        Khóa giữ hàng tạm thời cho điều chuyển
        UPDLOCK / Optimistic check: available >= quantity
        """
        with _stock_mutex:
            existing = db.query(StockLedger).filter(StockLedger.reference_id == reference_id).first()
            if existing:
                logger.info(f"[{self.branch_code}] Request {reference_id} đã xử lý trước đó. Bỏ qua.")
                return True

            inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).with_for_update().first()
            if not inv or inv.available_qty < quantity:
                logger.warning(f"[{self.branch_code}] Không đủ hàng để giữ: SKU={sku}, Cần={quantity}, Có={inv.available_qty if inv else 0}")
                self._queue_outbox_event(
                    db, "evt.transfer.reserve_failed", "EVT_RESERVE_FAILED",
                    {"transfer_id": transfer_id, "source_branch": self.branch_code, "sku": sku, "reason": "Tồn kho khả dụng không đủ"}
                )
                db.commit()
                return False

            inv.available_qty -= quantity
            inv.reserved_qty += quantity
            inv.version += 1

            ledger = StockLedger(
                reference_id=reference_id,
                sku=sku,
                change_type="RESERVE",
                quantity=quantity
            )
            db.add(ledger)

            self._record_warehouse_transaction(
                db=db,
                tx_type="CHUYEN_KHO_DI",
                items=[{"sku": sku, "signed_qty": -quantity, "post_balance": inv.available_qty}],
                prefix="CKD",
                status="CHO_XU_LY",
                counterpart_branch=dest_branch,
                saga_transfer_id=transfer_id,
                note=f"Tạm khóa hàng xuất điều chuyển Saga {transfer_id}"
            )

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

            tx = db.query(WarehouseTransaction).filter(
                WarehouseTransaction.saga_transfer_id == transfer_id,
                WarehouseTransaction.transaction_type == "CHUYEN_KHO_DI"
            ).first()
            if tx:
                tx.status = "HOAN_THANH"

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

            tx = db.query(WarehouseTransaction).filter(
                WarehouseTransaction.saga_transfer_id == transfer_id,
                WarehouseTransaction.transaction_type == "CHUYEN_KHO_DI"
            ).first()
            if tx:
                tx.status = "SAGA_ROLLBACK"
                tx.note = f"Đã hoàn tác bù trừ Saga {transfer_id}"

            self._queue_outbox_event(
                db, "evt.transfer.released", "EVT_STOCK_RELEASED",
                {"transfer_id": transfer_id, "source_branch": self.branch_code, "sku": sku, "quantity": quantity}
            )
            if inv:
                self._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)

            db.commit()
            logger.info(f"[{self.branch_code}] BÙ TRỪ THÀNH CÔNG: Đã hoàn trả {quantity} sản phẩm {sku} về available_qty")
            return True

    def transfer_in(self, db: Session, sku: str, quantity: int, reference_id: str, transfer_id: str, source_branch: Optional[str] = None) -> bool:
        """Kho đích nhận hàng điều chuyển thành công: available_qty += quantity"""
        with _stock_mutex:
            existing = db.query(StockLedger).filter(StockLedger.reference_id == reference_id).first()
            if existing:
                return True

            inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).with_for_update().first()
            if not inv:
                inv = LocalInventory(sku=sku, branch_code=self.branch_code, available_qty=quantity, reserved_qty=0, version=1)
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

            self._record_warehouse_transaction(
                db=db,
                tx_type="CHUYEN_KHO_DEN",
                items=[{"sku": sku, "signed_qty": quantity, "post_balance": inv.available_qty}],
                prefix="CKN",
                status="HOAN_THANH",
                counterpart_branch=source_branch,
                saga_transfer_id=transfer_id,
                note=f"Nhận kiện hàng điều chuyển Saga {transfer_id}"
            )

            self._queue_outbox_event(
                db, "evt.transfer.completed", "EVT_TRANSFER_COMPLETED",
                {
                    "transfer_id": transfer_id,
                    "source_branch": source_branch,
                    "dest_branch": self.branch_code,
                    "sku": sku,
                    "quantity": quantity
                }
            )
            self._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)

            db.commit()
            logger.info(f"[{self.branch_code}] NHẬP KHO ĐIỀU CHUYỂN: SKU={sku}, Qty={quantity}, Đã phát EVT_TRANSFER_COMPLETED")
            return True

    def adjust_stock(self, db: Session, sku: str, change_type: str, quantity: int, reference_id: str, partner_name: str = None, note: str = None, created_by: str = "system") -> dict:
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
                tx_type = "XUAT_KHO"
                prefix = "XK"
                signed_qty = -quantity
            elif change_type == "LOCAL_IN":
                if not inv:
                    inv = LocalInventory(sku=sku, branch_code=self.branch_code, available_qty=quantity, reserved_qty=0, version=1)
                    db.add(inv)
                else:
                    inv.available_qty += quantity
                    inv.version += 1
                tx_type = "NHAP_KHO"
                prefix = "NK"
                signed_qty = quantity
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

            tx = self._record_warehouse_transaction(
                db=db,
                tx_type=tx_type,
                items=[{"sku": sku, "signed_qty": signed_qty, "post_balance": inv.available_qty}],
                prefix=prefix,
                status="HOAN_THANH",
                note=note or partner_name,
                created_by=created_by
            )

            self._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)
            db.commit()

            logger.info(f"[{self.branch_code}] TỰ TRỊ CỤC BỘ ({change_type}): SKU={sku}, Qty={quantity}, Tồn mới={inv.available_qty}")
            return {
                "status": "SUCCESS",
                "is_duplicate": False,
                "available_qty": inv.available_qty,
                "receipt_code": tx.receipt_code
            }

    def audit_stock(self, db: Session, sku: str, actual_qty: int, note: str = "Kiểm kê định kỳ", created_by: str = "system") -> dict:
        """Kiểm kê số lượng thực tế và điều chỉnh chênh lệch tồn kho (Inventory Stock-taking)"""
        with _stock_mutex:
            inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).with_for_update().first()
            if not inv:
                inv = LocalInventory(sku=sku, branch_code=self.branch_code, available_qty=actual_qty, reserved_qty=0, version=1)
                db.add(inv)
                variance = actual_qty
                old_qty = 0
            else:
                old_qty = inv.available_qty
                variance = actual_qty - old_qty
                inv.available_qty = actual_qty
                inv.version += 1

            ref_id = f"AUDIT-{uuid.uuid4().hex[:10].upper()}"
            full_note = f"{note} (Sổ sách: {old_qty}, Thực tế: {actual_qty}, Chênh lệch: {variance:+d})"
            ledger = StockLedger(
                reference_id=ref_id,
                sku=sku,
                change_type="AUDIT_ADJUST",
                quantity=variance,
                note=full_note
            )
            db.add(ledger)

            tx = self._record_warehouse_transaction(
                db=db,
                tx_type="KIEM_KE",
                items=[{"sku": sku, "signed_qty": variance, "post_balance": inv.available_qty}],
                prefix="KK",
                status="HOAN_THANH",
                note=full_note,
                created_by=created_by
            )

            self._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)
            db.commit()

            logger.info(f"[{self.branch_code}] KIỂM KÊ KHO: SKU={sku}, Cũ={old_qty}, Mới={actual_qty}, Lệch={variance:+d}")
            return {
                "status": "SUCCESS",
                "sku": sku,
                "old_qty": old_qty,
                "actual_qty": actual_qty,
                "variance": variance,
                "reference_id": ref_id,
                "receipt_code": tx.receipt_code
            }

    def create_customer_order(
        self,
        db: Session,
        customer_name: str,
        customer_phone: Optional[str],
        items: List[Dict[str, Any]],
        created_by: str = "system"
    ) -> dict:
        """
        Tạo đơn đặt hàng tại Chi nhánh (DON_HANG & CHI_TIET_DON_HANG),
        đồng thời trừ tồn kho nguyên tử và sinh phiếu xuất kho (GIAO_DICH_KHO & CHI_TIET_GIAO_DICH).
        """
        with _stock_mutex:
            order_id = str(uuid.uuid4())
            total_amount = 0.0
            order_details = []
            tx_items = []
            prod_map = {p.sku: p for p in db.query(LocalProduct).all()}

            # Kiểm tra toàn bộ mặt hàng trước khi trừ kho
            inv_updates = []
            for item in items:
                sku = item["sku"]
                qty = int(item["quantity"])
                inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).with_for_update().first()
                if not inv or inv.available_qty < qty:
                    return {
                        "status": "FAILED",
                        "reason": f"Sản phẩm '{sku}' không đủ tồn kho (Cần {qty}, Có {inv.available_qty if inv else 0})"
                    }
                p = prod_map.get(sku)
                unit_price = float(item["unit_price"]) if item.get("unit_price") is not None else float(p.price if p else 0.0)
                inv_updates.append((inv, sku, qty, unit_price))

            # Áp dụng trừ kho & tạo bản ghi chi tiết đơn hàng
            for inv, sku, qty, unit_price in inv_updates:
                inv.available_qty -= qty
                inv.version += 1
                total_amount += qty * unit_price

                detail = CustomerOrderDetail(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    sku=sku,
                    quantity=qty,
                    unit_price=unit_price
                )
                order_details.append(detail)
                tx_items.append({"sku": sku, "signed_qty": -qty, "post_balance": inv.available_qty})

                ledger = StockLedger(
                    reference_id=f"ORD-{order_id[:8].upper()}-{sku}",
                    sku=sku,
                    change_type="LOCAL_OUT",
                    quantity=qty,
                    partner_name=customer_name,
                    note=f"Xuất theo đơn hàng {order_id[:8].upper()}"
                )
                db.add(ledger)
                self._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)

            order = CustomerOrder(
                order_id=order_id,
                branch_code=self.branch_code,
                customer_name=customer_name,
                customer_phone=customer_phone,
                total_amount=total_amount,
                status="DA_XUAT_KHO"
            )
            db.add(order)
            for d in order_details:
                db.add(d)

            tx = self._record_warehouse_transaction(
                db=db,
                tx_type="XUAT_KHO",
                items=tx_items,
                prefix="XK",
                status="HOAN_THANH",
                note=f"Xuất kho đơn hàng {order_id[:8].upper()} - Khách: {customer_name}",
                created_by=created_by
            )
            db.commit()

            logger.info(f"[{self.branch_code}] TẠO ĐƠN HÀNG THÀNH CÔNG: Order={order_id}, Tổng tiền={total_amount:,.0f}")
            return {
                "status": "SUCCESS",
                "order_id": order.order_id,
                "branch_code": order.branch_code,
                "customer_name": order.customer_name,
                "total_amount": order.total_amount,
                "order_status": order.status,
                "receipt_code": tx.receipt_code,
                "items_count": len(order_details)
            }
