# backend/hq_service/consumers/dlq_consumer.py
import logging
from typing import Any

logger = logging.getLogger("DLQConsumer")


async def process_dlq_message(message_data: dict[str, Any], routing_key: str) -> None:
    """
    Consumer giám sát Dead Letter Queue (q.dlq).
    Ghi vết các message gặp sự cố sau khi đã retry hết số lần cho phép.
    """
    msg_id = message_data.get("message_id", "unknown")
    event_type = message_data.get("event_type", "unknown")
    logger.error(
        f"[DLQ ALERT] Phát hiện message thất bại trong Dead Letter Queue: "
        f"msg_id={msg_id}, event_type={event_type}, routing_key={routing_key}, payload={message_data}"
    )
