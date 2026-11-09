# backend/hq_service/workers/outbox_worker.py
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from hq_service.models import OutboxEvent
from shared.rabbitmq_client import RabbitMQClient

logger = logging.getLogger("HQOutboxWorker")


async def outbox_loop(session_factory: async_sessionmaker, rabbitmq_client: RabbitMQClient) -> None:
    """
    Vòng lặp định kỳ quét bảng Outbox_Events tại DB_HQ và publish lên RabbitMQ.
    Áp dụng Pessimistic Locking với UPDLOCK, READPAST để hỗ trợ mở rộng an toàn.
    """
    batch_size = 20
    poll_interval = 0.5

    while True:
        try:
            if not rabbitmq_client.is_connected:
                await asyncio.sleep(1.0)
                continue

            async with session_factory() as session:
                async with session.begin():
                    bind = session.get_bind()
                    dialect_name = bind.dialect.name if bind else ""
                    lock_hint = "WITH (UPDLOCK, READPAST)" if "mssql" in dialect_name else ""

                    query = text(f"""
                        SELECT TOP ({batch_size}) event_id, routing_key, payload, retry_count
                        FROM Outbox_Events {lock_hint}
                        WHERE is_published = 0 AND next_retry_at <= :now
                        ORDER BY next_retry_at ASC
                    """)

                    result = await session.execute(query, {"now": datetime.now(timezone.utc)})
                    rows = result.fetchall()

                    for row in rows:
                        event_id, routing_key, payload_str, retry_count = row
                        try:
                            payload_data = json.loads(payload_str)
                            published = await rabbitmq_client.publish(
                                routing_key=routing_key,
                                message=payload_data,
                                correlation_id=event_id
                            )
                            if published:
                                await session.execute(
                                    text("UPDATE Outbox_Events SET is_published = 1 WHERE event_id = :eid"),
                                    {"eid": event_id}
                                )
                                logger.debug(f"[HQ OUTBOX PUBLISHED] event_id={event_id} -> {routing_key}")
                            else:
                                raise RuntimeError("Publisher confirm negative ack")
                        except Exception as pub_err:
                            new_retry = retry_count + 1
                            backoff_seconds = min(2 ** new_retry, 60)
                            next_retry = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
                            logger.warning(
                                f"[HQ OUTBOX RETRY] event_id={event_id} lần {new_retry} thất bại: {pub_err}. "
                                f"Thử lại sau {backoff_seconds}s"
                            )
                            await session.execute(
                                text("""
                                    UPDATE Outbox_Events
                                    SET retry_count = :rc, next_retry_at = :nxt
                                    WHERE event_id = :eid
                                """),
                                {"rc": new_retry, "nxt": next_retry, "eid": event_id}
                            )

        except asyncio.CancelledError:
            logger.info("[HQ OUTBOX] Worker đã dừng theo tín hiệu shutdown.")
            break
        except Exception as e:
            logger.error(f"[HQ OUTBOX LOOP ERROR] {e}", exc_info=True)

        await asyncio.sleep(poll_interval)
