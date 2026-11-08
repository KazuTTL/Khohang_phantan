# backend/hq_service/saga/orchestrator.py
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from hq_service.models import OutboxMessage, TransferOrder
from hq_service.saga.state import SagaStatus
from shared.event_schemas import CmdReserveStockPayload, EventEnvelope
from shared.messaging_topology import ROUTING_CMD_RESERVE, get_command_routing_key


class SagaOrchestrator:
    """
    Saga Orchestrator tại Node Trụ sở chính (HQ).
    Điều phối luồng điều chuyển hàng hóa phân tán giữa các chi nhánh.
    """

    @staticmethod
    async def initiate_transfer(
        session: AsyncSession,
        source_branch: str,
        dest_branch: str,
        sku: str,
        quantity: int
    ) -> TransferOrder:
        """
        Khởi tạo tiến trình Saga:
        Gói trong 1 transaction ACID:
        1. Tạo TransferOrder trạng thái INITIATED
        2. Ghi OutboxMessage chứa lệnh CMD_RESERVE_STOCK gửi tới kho nguồn
        """
        transfer_id = str(uuid.uuid4())
        
        # 1. Ghi nhận nghiệp vụ
        order = TransferOrder(
            transfer_id=transfer_id,
            source_branch=source_branch.strip(),
            dest_branch=dest_branch.strip(),
            sku=sku.strip(),
            quantity=quantity,
            saga_status=SagaStatus.INITIATED.value,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        session.add(order)

        # 2. Tạo lệnh gửi qua Outbox (Phase 1: Giữ hàng tại kho nguồn)
        envelope = EventEnvelope[CmdReserveStockPayload](
            message_id=str(uuid.uuid4()),
            correlation_id=transfer_id,
            event_type="CMD_RESERVE_STOCK",
            source="HQ_SERVICE",
            payload=CmdReserveStockPayload(
                transfer_id=transfer_id,
                source_branch=source_branch.strip(),
                dest_branch=dest_branch.strip(),
                sku=sku.strip(),
                quantity=quantity
            )
        )

        routing_key = get_command_routing_key(ROUTING_CMD_RESERVE, source_branch)

        outbox = OutboxMessage(
            message_id=envelope.message_id,
            event_type="CMD_RESERVE_STOCK",
            routing_key=routing_key,
            payload=json.dumps(envelope.model_dump(mode="json")),
            status="PENDING",
            retry_count=0,
            created_at=datetime.now(timezone.utc)
        )
        session.add(outbox)

        # Trả về đối tượng order (sẽ được caller commit cùng transaction)
        return order
