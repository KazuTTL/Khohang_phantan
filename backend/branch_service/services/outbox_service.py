# backend/branch_service/services/outbox_service.py
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.models import OutboxMessage
from shared.event_schemas import EventEnvelope


class OutboxService:
    """
    Helper chuẩn hóa việc tạo Outbox Message trong cùng 1 Database Transaction ACID.
    Triệt tiêu hoàn toàn rủi ro Dual-Write trong hệ thống phân tán.
    """

    @staticmethod
    def create_outbox_message(
        session: AsyncSession,
        event_type: str,
        routing_key: str,
        source: str,
        payload_model: Any,
        correlation_id: str | None = None
    ) -> OutboxMessage:
        envelope = EventEnvelope(
            message_id=str(uuid.uuid4()),
            correlation_id=correlation_id or str(uuid.uuid4()),
            event_type=event_type,
            source=source,
            payload=payload_model
        )

        outbox = OutboxMessage(
            message_id=envelope.message_id,
            event_type=event_type,
            routing_key=routing_key,
            payload=json.dumps(envelope.model_dump(mode="json")),
            status="PENDING",
            retry_count=0,
            created_at=datetime.now(timezone.utc)
        )
        session.add(outbox)
        return outbox
