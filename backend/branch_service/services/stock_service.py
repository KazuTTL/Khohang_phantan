# backend/branch_service/services/stock_service.py
import asyncio
from datetime import datetime, timezone
import logging
import uuid
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.config import branch_settings
from branch_service.models import LocalInventory, LocalProduct, StockLedger
from branch_service.services.outbox_service import OutboxService
from shared.event_schemas import (
    EvtInventoryUpdatedPayload, EvtReserveFailedPayload,
    EvtStockReleasedPayload, EvtStockReservedPayload,
    EvtTransferCompletedPayload
)
from shared.messaging_topology import (
    ROUTING_EVT_INVENTORY_UPDATED, ROUTING_EVT_RESERVE_FAILED,
    ROUTING_EVT_STOCK_RELEASED, ROUTING_EVT_STOCK_RESERVED,
    ROUTING_EVT_TRANSFER_COMPLETED
)

logger = logging.getLogger("StockService")

# Async lock bảo vệ đa luồng cục bộ khi chạy trên môi trường SQLite local
_local_branch_lock = asyncio.Lock()


class StockService:
    """
    Dịch vụ quản trị Tồn kho Cục bộ tại Chi nhánh.
    Tuân thủ tuyệt đối:
    - NGUYÊN TẮC 3: Mọi thao tác ghi = 1 local ACID transaction (Business + Outbox).
    - NGUYÊN TẮC 5: Trước khi trừ tồn kho PHẢI dùng 'SELECT ... WITH (UPDLOCK, ROWLOCK)'.
    """

    @staticmethod
    async def _lock_and_get_inventory(session: AsyncSession, sku: str) -> tuple[int, int] | None:
        """
        Khóa dòng bi quan (Pessimistic Row Lock) trước khi đọc và cập nhật tồn kho.
        Dùng 'SELECT ... WITH (UPDLOCK, ROWLOCK)' trên SQL Server để ngăn chặn Race Condition.
        """
        # Xác định dialect động: nếu là SQL Server thì dùng WITH (UPDLOCK, ROWLOCK)
        bind = session.get_bind()
        dialect_name = bind.dialect.name if bind else ""
        
        lock_hint = "WITH (UPDLOCK, ROWLOCK)" if "mssql" in dialect_name else ""
        query = text(f"SELECT available_qty, reserved_qty FROM Local_Inventory {lock_hint} WHERE sku = :sku")
        
        result = await session.execute(query, {"sku": sku})
        row = result.first()
        if row is None:
            return None
        return (row[0], row[1])

    @classmethod
    async def adjust_stock(
        cls,
        session: AsyncSession,
        sku: str,
        change_type: str, # LOCAL_IN | LOCAL_OUT
        quantity: int,
        idempotency_key: str | None = None,
        note: str | None = None
    ) -> tuple[bool, str, dict]:
        """
        Xuất bán tại chỗ (LOCAL_OUT) hoặc Nhập hàng bán lẻ (LOCAL_IN) tại chi nhánh.
        Thể hiện tính TỰ TRỊ CỤC BỘ (Local Autonomy):
        Hoạt động hoàn toàn độc lập với HQ trên CSDL riêng.
        """
        async with _local_branch_lock:
            # 1. Kiểm tra Idempotency Key để chống lặp giao dịch
            if idempotency_key:
                stmt = select(StockLedger).where(StockLedger.idempotency_key == idempotency_key)
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if existing:
                    return (
                        True,
                        "IDEMPOTENT_DUPLICATE",
                        {
                            "available_qty": existing.available_after,
                            "reserved_qty": existing.reserved_after,
                            "reference_id": existing.reference_id or ""
                        }
                    )

            # 2. Khóa dòng với UPDLOCK, ROWLOCK
            inv = await cls._lock_and_get_inventory(session, sku)
            if inv is None:
                return False, f"Sản phẩm {sku} chưa được khởi tạo tồn kho tại chi nhánh này.", {}

            current_avail, current_res = inv
            new_avail = current_avail
            new_res = current_res

            if change_type == "LOCAL_OUT":
                if current_avail < quantity:
                    return False, f"Không đủ tồn kho khả dụng ({current_avail} < {quantity}).", {}
                new_avail = current_avail - quantity
            elif change_type == "LOCAL_IN":
                new_avail = current_avail + quantity
            else:
                return False, f"Loại biến động {change_type} không hợp lệ.", {}

            # 3. Cập nhật Local_Inventory
            update_query = text(
                "UPDATE Local_Inventory SET available_qty = :avail, reserved_qty = :res, "
                "updated_at = :now WHERE sku = :sku"
            )
            await session.execute(
                update_query,
                {"avail": new_avail, "res": new_res, "now": datetime.now(timezone.utc), "sku": sku}
            )

            # 4. Ghi sổ Stock_Ledger
            ref_id = f"LOC-{uuid.uuid4().hex[:8].upper()}"
            ledger = StockLedger(
                transaction_type=change_type,
                sku=sku,
                quantity=quantity,
                available_after=new_avail,
                reserved_after=new_res,
                reference_id=ref_id,
                idempotency_key=idempotency_key,
                note=note or f"Local transaction {change_type} at {branch_settings.BRANCH_CODE}",
                created_at=datetime.now(timezone.utc)
            )
            session.add(ledger)

            # 5. NGUYÊN TẮC 3: Ghi Outbox Message EVT_INVENTORY_UPDATED trong cùng Transaction
            OutboxService.create_outbox_message(
                session=session,
                event_type="EVT_INVENTORY_UPDATED",
                routing_key=ROUTING_EVT_INVENTORY_UPDATED,
                source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                payload_model=EvtInventoryUpdatedPayload(
                    branch_code=branch_settings.BRANCH_CODE,
                    sku=sku,
                    available_qty=new_avail,
                    reserved_qty=new_res,
                    change_type=change_type,
                    reference_id=ref_id
                ),
                correlation_id=ref_id
            )

            return True, "SUCCESS", {
                "available_qty": new_avail,
                "reserved_qty": new_res,
                "reference_id": ref_id
            }

    @classmethod
    async def reserve_stock_for_saga(
        cls,
        session: AsyncSession,
        transfer_id: str,
        dest_branch: str,
        sku: str,
        quantity: int
    ) -> bool:
        """
        Saga Phase 1 tại Kho Xuất:
        Dùng UPDLOCK kiểm tra: nếu đủ hàng thì chuyển available -> reserved.
        Ghi Outbox EVT_STOCK_RESERVED hoặc EVT_RESERVE_FAILED trong cùng transaction.
        """
        async with _local_branch_lock:
            inv = await cls._lock_and_get_inventory(session, sku)
            if inv is None or inv[0] < quantity:
                # Không đủ hàng khả dụng -> Báo lỗi
                avail = inv[0] if inv else 0
                OutboxService.create_outbox_message(
                    session=session,
                    event_type="EVT_RESERVE_FAILED",
                    routing_key=ROUTING_EVT_RESERVE_FAILED,
                    source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                    payload_model=EvtReserveFailedPayload(
                        transfer_id=transfer_id,
                        source_branch=branch_settings.BRANCH_CODE,
                        sku=sku,
                        quantity=quantity,
                        reason=f"Kho {branch_settings.BRANCH_CODE} chỉ còn {avail} sản phẩm (yêu cầu {quantity})"
                    ),
                    correlation_id=transfer_id
                )
                logger.warning(f"[SAGA RESERVE FAILED] Kho {branch_settings.BRANCH_CODE} không đủ hàng cho đơn {transfer_id}")
                return False

            # Đủ hàng -> Available -= qty, Reserved += qty
            current_avail, current_res = inv
            new_avail = current_avail - quantity
            new_res = current_res + quantity

            update_query = text(
                "UPDATE Local_Inventory SET available_qty = :avail, reserved_qty = :res, "
                "updated_at = :now WHERE sku = :sku"
            )
            await session.execute(
                update_query,
                {"avail": new_avail, "res": new_res, "now": datetime.now(timezone.utc), "sku": sku}
            )

            ledger = StockLedger(
                transaction_type="SAGA_RESERVE",
                sku=sku,
                quantity=quantity,
                available_after=new_avail,
                reserved_after=new_res,
                reference_id=transfer_id,
                idempotency_key=f"SAGA-RES-{transfer_id}",
                note=f"Tạm giữ hàng chuyển tới kho {dest_branch}",
                created_at=datetime.now(timezone.utc)
            )
            session.add(ledger)

            # Ghi Outbox EVT_STOCK_RESERVED + EVT_INVENTORY_UPDATED
            OutboxService.create_outbox_message(
                session=session,
                event_type="EVT_STOCK_RESERVED",
                routing_key=ROUTING_EVT_STOCK_RESERVED,
                source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                payload_model=EvtStockReservedPayload(
                    transfer_id=transfer_id,
                    source_branch=branch_settings.BRANCH_CODE,
                    dest_branch=dest_branch,
                    sku=sku,
                    quantity=quantity,
                    available_qty=new_avail,
                    reserved_qty=new_res
                ),
                correlation_id=transfer_id
            )

            OutboxService.create_outbox_message(
                session=session,
                event_type="EVT_INVENTORY_UPDATED",
                routing_key=ROUTING_EVT_INVENTORY_UPDATED,
                source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                payload_model=EvtInventoryUpdatedPayload(
                    branch_code=branch_settings.BRANCH_CODE,
                    sku=sku,
                    available_qty=new_avail,
                    reserved_qty=new_res,
                    change_type="SAGA_RESERVE",
                    reference_id=transfer_id
                ),
                correlation_id=transfer_id
            )

            logger.info(f"[SAGA RESERVED OK] Kho {branch_settings.BRANCH_CODE} giữ {quantity} {sku} cho đơn {transfer_id}")
            return True

    @classmethod
    async def release_stock_compensation(
        cls,
        session: AsyncSession,
        transfer_id: str,
        sku: str,
        quantity: int,
        reason: str
    ) -> None:
        """
        Giao dịch bù trừ (Compensating Transaction / Rollback) tại Kho Xuất:
        Hoàn trả hàng giữ: Reserved -= qty, Available += qty.
        Ghi Outbox EVT_STOCK_RELEASED trong cùng transaction.
        """
        async with _local_branch_lock:
            inv = await cls._lock_and_get_inventory(session, sku)
            if not inv:
                return

            current_avail, current_res = inv
            new_res = max(0, current_res - quantity)
            new_avail = current_avail + quantity

            update_query = text(
                "UPDATE Local_Inventory SET available_qty = :avail, reserved_qty = :res, "
                "updated_at = :now WHERE sku = :sku"
            )
            await session.execute(
                update_query,
                {"avail": new_avail, "res": new_res, "now": datetime.now(timezone.utc), "sku": sku}
            )

            ledger = StockLedger(
                transaction_type="SAGA_RELEASE",
                sku=sku,
                quantity=quantity,
                available_after=new_avail,
                reserved_after=new_res,
                reference_id=transfer_id,
                idempotency_key=f"SAGA-REL-{transfer_id}",
                note=f"Giao dịch bù trừ (Rollback): {reason}",
                created_at=datetime.now(timezone.utc)
            )
            session.add(ledger)

            # Ghi Outbox EVT_STOCK_RELEASED
            OutboxService.create_outbox_message(
                session=session,
                event_type="EVT_STOCK_RELEASED",
                routing_key=ROUTING_EVT_STOCK_RELEASED,
                source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                payload_model=EvtStockReleasedPayload(
                    transfer_id=transfer_id,
                    source_branch=branch_settings.BRANCH_CODE,
                    sku=sku,
                    quantity=quantity
                ),
                correlation_id=transfer_id
            )

            OutboxService.create_outbox_message(
                session=session,
                event_type="EVT_INVENTORY_UPDATED",
                routing_key=ROUTING_EVT_INVENTORY_UPDATED,
                source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                payload_model=EvtInventoryUpdatedPayload(
                    branch_code=branch_settings.BRANCH_CODE,
                    sku=sku,
                    available_qty=new_avail,
                    reserved_qty=new_res,
                    change_type="SAGA_RELEASE",
                    reference_id=transfer_id
                ),
                correlation_id=transfer_id
            )

            logger.info(f"[SAGA COMPENSATION DONE] Kho {branch_settings.BRANCH_CODE} đã hoàn trả {quantity} {sku} cho đơn {transfer_id}")

    @classmethod
    async def import_incoming_stock(
        cls,
        session: AsyncSession,
        transfer_id: str,
        source_branch: str,
        sku: str,
        quantity: int
    ) -> None:
        """
        Nhập kho thành công tại Kho Đích:
        Available += qty.
        Ghi Outbox EVT_TRANSFER_COMPLETED + EVT_INVENTORY_UPDATED trong cùng transaction.
        """
        async with _local_branch_lock:
            inv = await cls._lock_and_get_inventory(session, sku)
            current_avail = inv[0] if inv else 0
            current_res = inv[1] if inv else 0

            new_avail = current_avail + quantity

            if inv:
                update_query = text(
                    "UPDATE Local_Inventory SET available_qty = :avail, "
                    "updated_at = :now WHERE sku = :sku"
                )
                await session.execute(
                    update_query,
                    {"avail": new_avail, "now": datetime.now(timezone.utc), "sku": sku}
                )
            else:
                insert_query = text(
                    "INSERT INTO Local_Inventory (sku, available_qty, reserved_qty, updated_at) "
                    "VALUES (:sku, :avail, 0, :now)"
                )
                await session.execute(
                    insert_query,
                    {"sku": sku, "avail": new_avail, "now": datetime.now(timezone.utc)}
                )

            ledger = StockLedger(
                transaction_type="SAGA_IN",
                sku=sku,
                quantity=quantity,
                available_after=new_avail,
                reserved_after=current_res,
                reference_id=transfer_id,
                idempotency_key=f"SAGA-IN-{transfer_id}",
                note=f"Nhập hàng điều chuyển từ kho {source_branch}",
                created_at=datetime.now(timezone.utc)
            )
            session.add(ledger)

            # Ghi Outbox EVT_TRANSFER_COMPLETED
            OutboxService.create_outbox_message(
                session=session,
                event_type="EVT_TRANSFER_COMPLETED",
                routing_key=ROUTING_EVT_TRANSFER_COMPLETED,
                source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                payload_model=EvtTransferCompletedPayload(
                    transfer_id=transfer_id,
                    source_branch=source_branch,
                    dest_branch=branch_settings.BRANCH_CODE,
                    sku=sku,
                    quantity=quantity
                ),
                correlation_id=transfer_id
            )

            OutboxService.create_outbox_message(
                session=session,
                event_type="EVT_INVENTORY_UPDATED",
                routing_key=ROUTING_EVT_INVENTORY_UPDATED,
                source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                payload_model=EvtInventoryUpdatedPayload(
                    branch_code=branch_settings.BRANCH_CODE,
                    sku=sku,
                    available_qty=new_avail,
                    reserved_qty=current_res,
                    change_type="SAGA_IN",
                    reference_id=transfer_id
                ),
                correlation_id=transfer_id
            )

            logger.info(f"[SAGA IMPORT DONE] Kho {branch_settings.BRANCH_CODE} đã nhập {quantity} {sku} từ đơn {transfer_id}")
