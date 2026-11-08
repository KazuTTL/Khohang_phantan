# backend/branch_service/services/stocktake_service.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.config import branch_settings
from branch_service.models import LocalInventory, StockLedger, StocktakeRecord
from branch_service.services.outbox_service import OutboxService
from shared.event_schemas import EvtInventoryUpdatedPayload
from shared.messaging_topology import ROUTING_EVT_INVENTORY_UPDATED


class StocktakeService:
    """
    Xử lý kiểm kê và điều chỉnh chênh lệch tồn kho thực tế tại Chi nhánh.
    """

    @staticmethod
    async def record_stocktake(
        session: AsyncSession,
        session_id: str,
        sku: str,
        actual_qty: int,
        note: str | None = None
    ) -> StocktakeRecord:
        # 1. Lấy số lượng hệ thống hiện tại
        stmt = select(LocalInventory).where(LocalInventory.sku == sku)
        res = await session.execute(stmt)
        inv = res.scalar_one_or_none()
        system_qty = inv.available_qty if inv else 0
        current_res = inv.reserved_qty if inv else 0

        diff_qty = actual_qty - system_qty
        record_id = str(uuid.uuid4())[:8].upper()

        # 2. Tạo bản ghi kiểm kê
        record = StocktakeRecord(
            record_id=record_id,
            session_id=session_id,
            sku=sku,
            system_qty=system_qty,
            actual_qty=actual_qty,
            diff_qty=diff_qty,
            note=note,
            created_at=datetime.now(timezone.utc)
        )
        session.add(record)

        # 3. Nếu có chênh lệch, cập nhật tồn kho khả dụng theo số thực tế và ghi sổ
        if diff_qty != 0:
            if inv:
                inv.available_qty = actual_qty
                inv.updated_at = datetime.now(timezone.utc)
            else:
                inv = LocalInventory(
                    sku=sku,
                    available_qty=actual_qty,
                    reserved_qty=0,
                    updated_at=datetime.now(timezone.utc)
                )
                session.add(inv)

            ledger = StockLedger(
                transaction_type="STOCKTAKE_ADJUST",
                sku=sku,
                quantity=diff_qty,
                available_after=actual_qty,
                reserved_after=current_res,
                reference_id=record_id,
                note=f"Điều chỉnh kiểm kê phiên {session_id}: {note or ''}",
                created_at=datetime.now(timezone.utc)
            )
            session.add(ledger)

            # Ghi Outbox để đồng bộ lên HQ Snapshot
            OutboxService.create_outbox_message(
                session=session,
                event_type="EVT_INVENTORY_UPDATED",
                routing_key=ROUTING_EVT_INVENTORY_UPDATED,
                source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                payload_model=EvtInventoryUpdatedPayload(
                    branch_code=branch_settings.BRANCH_CODE,
                    sku=sku,
                    available_qty=actual_qty,
                    reserved_qty=current_res,
                    change_type="STOCKTAKE_ADJUST",
                    reference_id=record_id
                ),
                correlation_id=record_id
            )

        return record
