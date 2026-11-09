# backend/branch_service/services/outbox_worker.py
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from branch_service.config import branch_settings
from branch_service.models import OutboxEvent
from shared.rabbitmq_client import RabbitMQClient

logger = logging.getLogger(f"BranchOutboxWorker_{branch_settings.BRANCH_CODE}")


async def outbox_loop(session_factory: async_sessionmaker, publisher: RabbitMQClient) -> None:
    """
    Tiến trình quét Outbox nền độc lập (Transactional Outbox Worker).
    - Sử dụng khóa UPDLOCK, READPAST trên SQL Server để quét an toàn không gây tranh chấp hoặc khóa hàng loạt.
    - Cơ chế Exponential Backoff (2^retry_count seconds) khi RabbitMQ broker gặp sự cố.
    """
    logger.info(f"[OUTBOX LOOP] Bắt đầu tiến trình quét Outbox tại Chi nhánh {branch_settings.BRANCH_CODE}...")

    while True:
        try:
            if publisher.is_connected:
                now = datetime.now(timezone.utc)
                async with session_factory() as session:
                    async with session.begin():
                        bind = session.get_bind()
                        dialect_name = bind.dialect.name if bind else ""

                        # Trên SQL Server dùng UPDLOCK, READPAST để các worker không block lẫn nhau
                        if "mssql" in dialect_name:
                            stmt = text(
                                "SELECT TOP 50 event_id, routing_key, payload, retry_count "
                                "FROM Outbox_Events WITH (UPDLOCK, READPAST) "
                                "WHERE is_published = 0 AND next_retry_at <= :now "
                                "ORDER BY created_at ASC"
                            )
                            res = await session.execute(stmt, {"now": now})
                            rows = res.all()
                            
                            for row in rows:
                                event_id, routing_key, payload_str, retry_count = row[0], row[1], row[2], row[3]
                                try:
                                    payload_dict = json.loads(payload_str)
                                    published = await publisher.publish(
                                        routing_key=routing_key,
                                        message=payload_dict,
                                        correlation_id=event_id
                                    )
                                    if published:
                                        await session.execute(
                                            text("UPDATE Outbox_Events SET is_published = 1 WHERE event_id = :eid"),
                                            {"eid": event_id}
                                        )
                                    else:
                                        new_retry = retry_count + 1
                                        next_retry = now + timedelta(seconds=min(300, 2 ** new_retry))
                                        await session.execute(
                                            text("UPDATE Outbox_Events SET retry_count = :rc, next_retry_at = :nr WHERE event_id = :eid"),
                                            {"rc": new_retry, "nr": next_retry, "eid": event_id}
                                        )
                                except Exception as ex:
                                    logger.error(f"[OUTBOX PUBLISH ERR] Event {event_id}: {ex}")
                                    new_retry = retry_count + 1
                                    next_retry = now + timedelta(seconds=min(300, 2 ** new_retry))
                                    await session.execute(
                                        text("UPDATE Outbox_Events SET retry_count = :rc, next_retry_at = :nr WHERE event_id = :eid"),
                                        {"rc": new_retry, "nr": next_retry, "eid": event_id}
                                    )
                        else:
                            # Dialect SQLite fallback
                            stmt_orm = (
                                select(OutboxEvent)
                                .where(OutboxEvent.is_published.is_(False), OutboxEvent.next_retry_at <= now)
                                .order_by(OutboxEvent.created_at.asc())
                                .limit(50)
                            )
                            events = (await session.execute(stmt_orm)).scalars().all()
                            for ev in events:
                                try:
                                    payload_dict = json.loads(ev.payload)
                                    published = await publisher.publish(
                                        routing_key=ev.routing_key,
                                        message=payload_dict,
                                        correlation_id=ev.event_id
                                    )
                                    if published:
                                        ev.is_published = True
                                    else:
                                        ev.retry_count += 1
                                        ev.next_retry_at = now + timedelta(seconds=min(300, 2 ** ev.retry_count))
                                except Exception as ex:
                                    ev.retry_count += 1
                                    ev.next_retry_at = now + timedelta(seconds=min(300, 2 ** ev.retry_count))

        except Exception as e:
            logger.error(f"[OUTBOX WORKER EXCEPTION] Chi nhánh {branch_settings.BRANCH_CODE}: {e}", exc_info=True)

        await asyncio.sleep(2.0)
