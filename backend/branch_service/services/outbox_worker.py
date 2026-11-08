# backend/branch_service/services/outbox_worker.py
import asyncio
import json
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.config import branch_settings
from branch_service.database import AsyncSessionLocal
from branch_service.models import OutboxMessage
from shared.config import shared_config
from shared.rabbitmq_client import RabbitMQClient

logger = logging.getLogger(f"BranchOutboxWorker_{branch_settings.BRANCH_CODE}")


class BranchOutboxWorker:
    """
    Background worker định kỳ quét bảng Outbox_Messages tại DB của Chi nhánh và publish lên RabbitMQ.
    Đảm bảo tính tự trị: nếu mất kết nối tới broker, tin nhắn lưu an toàn trong CSDL cục bộ
    và sẽ được gửi đi ngay khi kết nối phục hồi.
    """

    def __init__(self, rabbitmq_client: RabbitMQClient):
        self.rmq = rabbitmq_client
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[OUTBOX WORKER] Đã khởi động quét Outbox tại chi nhánh {branch_settings.BRANCH_CODE}...")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"[OUTBOX WORKER] Đã dừng quét Outbox tại chi nhánh {branch_settings.BRANCH_CODE}.")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.process_pending_messages()
            except Exception as e:
                logger.error(f"[OUTBOX ERROR] Lỗi trong vòng lặp Outbox Chi nhánh {branch_settings.BRANCH_CODE}: {e}", exc_info=True)
            await asyncio.sleep(shared_config.OUTBOX_POLL_INTERVAL_SECONDS)

    async def process_pending_messages(self) -> None:
        if not self.rmq.is_connected:
            return

        async with AsyncSessionLocal() as session:
            stmt = (
                select(OutboxMessage)
                .where(OutboxMessage.status == "PENDING")
                .order_by(OutboxMessage.created_at.asc())
                .limit(20)
            )
            res = await session.execute(stmt)
            messages = res.scalars().all()

            if not messages:
                return

            for msg in messages:
                try:
                    payload_dict = json.loads(msg.payload)
                    published = await self.rmq.publish(
                        routing_key=msg.routing_key,
                        message=payload_dict,
                        correlation_id=msg.message_id
                    )
                    if published:
                        msg.status = "PROCESSED"
                        msg.processed_at = datetime.now(timezone.utc)
                    else:
                        msg.retry_count += 1
                        if msg.retry_count >= shared_config.MAX_OUTBOX_RETRIES:
                            msg.status = "FAILED"
                            logger.error(f"[OUTBOX FAILED] Msg {msg.message_id} vượt quá số lần retry.")
                except Exception as ex:
                    msg.retry_count += 1
                    logger.error(f"[OUTBOX PUBLISH ERR] Msg {msg.message_id}: {ex}")
                    if msg.retry_count >= shared_config.MAX_OUTBOX_RETRIES:
                        msg.status = "FAILED"

            await session.commit()
