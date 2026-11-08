# backend/hq_service/consumers/hq_event_consumer.py
import logging
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hq_service.database import AsyncSessionLocal
from hq_service.models import GlobalInventorySnapshot
from hq_service.saga.handlers import SagaStepHandlers
from shared.event_schemas import (
    EvtInventoryUpdatedPayload, EvtReserveFailedPayload,
    EvtStockReleasedPayload, EvtStockReservedPayload,
    EvtTransferCompletedPayload, EvtTransferRejectedPayload
)
from shared.idempotency import check_and_mark_inbox

logger = logging.getLogger("HQEventConsumer")
CONSUMER_NAME = "HQEventConsumer"


async def process_hq_event(message_data: dict[str, Any], routing_key: str) -> None:
    """
    Xử lý tất cả các Event gửi về HQ qua RabbitMQ (routing_key bắt đầu bằng 'evt.').
    Bảo đảm tính Idempotent bằng Inbox Pattern.
    """
    msg_id = message_data.get("message_id") or ""
    event_type = message_data.get("event_type") or ""
    payload_dict = message_data.get("payload") or {}

    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 1. Kiểm tra tính Idempotent qua Inbox
            is_new = await check_and_mark_inbox(session, msg_id, CONSUMER_NAME)
            if not is_new:
                logger.info(f"[IDEMPOTENT SKIP] Message {msg_id} ({event_type}) đã được xử lý trước đó. Bỏ qua.")
                return

            logger.info(f"[HQ CONSUME] Đang xử lý {event_type} (msg_id={msg_id}, rkey={routing_key})")

            # 2. Xử lý các sự kiện Saga
            if event_type == "EVT_STOCK_RESERVED":
                payload = EvtStockReservedPayload(**payload_dict)
                await SagaStepHandlers.handle_stock_reserved(session, payload)

            elif event_type == "EVT_RESERVE_FAILED":
                payload = EvtReserveFailedPayload(**payload_dict)
                await SagaStepHandlers.handle_reserve_failed(session, payload)

            elif event_type == "EVT_TRANSFER_COMPLETED":
                payload = EvtTransferCompletedPayload(**payload_dict)
                await SagaStepHandlers.handle_transfer_completed(session, payload)

            elif event_type == "EVT_TRANSFER_REJECTED":
                payload = EvtTransferRejectedPayload(**payload_dict)
                await SagaStepHandlers.handle_transfer_rejected(session, payload)

            elif event_type == "EVT_STOCK_RELEASED":
                payload = EvtStockReleasedPayload(**payload_dict)
                await SagaStepHandlers.handle_stock_released(session, payload)

            # 3. Xử lý sự kiện cập nhật tồn kho toàn cục (Snapshot Sync)
            elif event_type == "EVT_INVENTORY_UPDATED":
                payload = EvtInventoryUpdatedPayload(**payload_dict)
                stmt = select(GlobalInventorySnapshot).where(
                    GlobalInventorySnapshot.branch_code == payload.branch_code,
                    GlobalInventorySnapshot.sku == payload.sku
                )
                res = await session.execute(stmt)
                snapshot = res.scalar_one_or_none()
                if snapshot:
                    snapshot.available_qty = payload.available_qty
                    snapshot.reserved_qty = payload.reserved_qty
                    snapshot.last_synced_at = datetime.now(timezone.utc)
                else:
                    new_snapshot = GlobalInventorySnapshot(
                        branch_code=payload.branch_code,
                        sku=payload.sku,
                        available_qty=payload.available_qty,
                        reserved_qty=payload.reserved_qty,
                        last_synced_at=datetime.now(timezone.utc)
                    )
                    session.add(new_snapshot)
                logger.info(f"[SNAPSHOT UPDATED] Kho {payload.branch_code} SKU={payload.sku}: Avail={payload.available_qty}, Res={payload.reserved_qty}")

            else:
                logger.debug(f"[HQ CONSUME] Sự kiện chưa đăng ký xử lý riêng: {event_type}")

        # Transaction commit tự động khi thoát async with session.begin()
