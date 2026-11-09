# backend/hq_service/consumers/hq_event_consumer.py
import logging
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hq_service.database import AsyncSessionLocal
from hq_service.models import GlobalInventorySnapshot, StocktakeItemGlobal, StocktakeSessionGlobal
from hq_service.saga.handlers import SagaStepHandlers
from shared.idempotency import check_inbox, mark_inbox

logger = logging.getLogger("HQEventConsumer")


async def process_hq_event(message_data: dict[str, Any], routing_key: str) -> None:
    """
    Xử lý tất cả các Event gửi về HQ qua RabbitMQ (routing_key bắt đầu bằng 'evt.').
    Bảo đảm tính Idempotent bằng Inbox Pattern.
    """
    msg_id = message_data.get("message_id") or ""
    event_type = message_data.get("event_type") or ""
    data = message_data.get("data") or message_data.get("payload") or {}

    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 1. Kiểm tra tính Idempotent qua Inbox
            if msg_id and await check_inbox(session, msg_id):
                logger.info(f"[IDEMPOTENT SKIP] Message {msg_id} ({event_type}) đã được xử lý trước đó. Bỏ qua.")
                return

            logger.info(f"[HQ CONSUME] Đang xử lý {event_type} (msg_id={msg_id}, rkey={routing_key})")

            # 2. Xử lý các sự kiện Saga 3 cấp
            if event_type in ["evt.transfer.source_approved", "EVT_STOCK_RESERVED"] or "source_approved" in routing_key:
                await SagaStepHandlers.handle_source_approved(session, data, msg_id)

            elif event_type in ["evt.transfer.source_rejected"] or "source_rejected" in routing_key:
                await SagaStepHandlers.handle_source_rejected(session, data, msg_id)

            elif event_type in ["evt.transfer.reserve_failed", "EVT_RESERVE_FAILED"] or "reserve_failed" in routing_key:
                await SagaStepHandlers.handle_reserve_failed(session, data, msg_id)

            elif event_type in ["evt.transfer.dest_approved", "EVT_TRANSFER_COMPLETED"] or "dest_approved" in routing_key:
                await SagaStepHandlers.handle_dest_approved(session, data, msg_id)

            elif event_type in ["evt.transfer.dest_rejected", "EVT_TRANSFER_REJECTED"] or "dest_rejected" in routing_key:
                await SagaStepHandlers.handle_dest_rejected(session, data, msg_id)

            elif event_type in ["evt.stock.released", "EVT_STOCK_RELEASED"] or "stock_released" in routing_key:
                await SagaStepHandlers.handle_stock_released(session, data, msg_id)

            # 3. Xử lý sự kiện cập nhật tồn kho toàn cục (Read Model Snapshot)
            elif event_type in ["evt.inventory.updated", "EVT_INVENTORY_UPDATED"] or "inventory.updated" in routing_key:
                branch_code = data.get("branch_code")
                sku = data.get("sku")
                available_qty = int(data.get("available_qty", 0))
                reserved_qty = int(data.get("reserved_qty", 0))

                if branch_code and sku:
                    stmt = select(GlobalInventorySnapshot).where(
                        GlobalInventorySnapshot.branch_code == branch_code,
                        GlobalInventorySnapshot.sku == sku
                    )
                    res = await session.execute(stmt)
                    snapshot = res.scalar_one_or_none()
                    if snapshot:
                        snapshot.available_qty = available_qty
                        snapshot.reserved_qty = reserved_qty
                        snapshot.last_synced_at = datetime.now(timezone.utc)
                    else:
                        new_snapshot = GlobalInventorySnapshot(
                            branch_code=branch_code,
                            sku=sku,
                            available_qty=available_qty,
                            reserved_qty=reserved_qty,
                            last_synced_at=datetime.now(timezone.utc)
                        )
                        session.add(new_snapshot)
                    logger.info(f"[SNAPSHOT UPDATED] Kho {branch_code} SKU={sku}: Avail={available_qty}, Res={reserved_qty}")

            # 4. Xử lý sự kiện đồng bộ kiểm kê toàn cục
            elif event_type in ["evt.stocktake.approved", "EVT_STOCKTAKE_APPROVED"] or "stocktake.approved" in routing_key:
                session_id = data.get("session_id")
                if session_id:
                    existing_st = await session.get(StocktakeSessionGlobal, session_id)
                    if not existing_st:
                        global_st = StocktakeSessionGlobal(
                            session_id=session_id,
                            session_code=data.get("session_code", session_id),
                            branch_code=data.get("branch_code", "UNKNOWN"),
                            status="APPROVED",
                            scope_type=data.get("scope_type", "FULL"),
                            total_skus_counted=int(data.get("total_skus_counted", 0)),
                            total_variance_abs=int(data.get("total_variance_abs", 0)),
                            created_by_name=data.get("created_by"),
                            approved_by_name=data.get("approved_by"),
                            created_at=datetime.now(timezone.utc),
                            approved_at=datetime.now(timezone.utc),
                            last_synced_at=datetime.now(timezone.utc)
                        )
                        session.add(global_st)
                        await session.flush()

                        for it in data.get("items", []):
                            st_item = StocktakeItemGlobal(
                                session_id=session_id,
                                sku=it.get("sku"),
                                system_qty_at_start=int(it.get("system_qty_at_start", 0)),
                                counted_qty=int(it.get("counted_qty", 0)),
                                variance_qty=int(it.get("variance_qty", 0)),
                                variance_reason=it.get("variance_reason")
                            )
                            session.add(st_item)
                        logger.info(f"[STOCKTAKE GLOBAL SYNC] Đã đồng bộ phiên kiểm kê {session_id} về HQ.")

            else:
                logger.debug(f"[HQ CONSUME] Sự kiện không cần xử lý: {event_type}")

            # 5. Ghi nhận Inbox để bảo đảm idempotency
            if msg_id:
                await mark_inbox(session, msg_id, event_type)
