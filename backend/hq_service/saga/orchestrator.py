# backend/hq_service/saga/orchestrator.py
import json
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hq_service.models import OutboxEvent, Product, SagaStep, TransferOrder
from hq_service.saga.state import SagaStatus
from shared.event_schemas import Envelope
from shared.messaging_topology import get_command_routing_key, ROUTING_CMD_APPROVE_REQUEST

logger = logging.getLogger("SagaOrchestrator")


class SagaOrchestrator:
    """
    Saga Orchestrator tại Node Trụ sở chính (HQ).
    Điều phối quy trình Phê duyệt Điều chuyển 3 cấp:
    1. HQ_MANAGER duyệt -> Phát lệnh cmd.transfer.approve_request.{source}
    2. SOURCE_MANAGER duyệt -> Nhận evt.transfer.source_approved -> Phát lệnh cmd.transfer.confirm_receive.{dest}
    3. DEST_MANAGER duyệt -> Nhận evt.transfer.dest_approved -> Phát evt.transfer.completed -> COMPLETED
    """

    @classmethod
    async def create_transfer(
        cls,
        session: AsyncSession,
        source_branch: str,
        dest_branch: str,
        sku: str,
        quantity: int,
        user_id: str
    ) -> TransferOrder:
        """Tạo đơn điều chuyển mới ở trạng thái PENDING_HQ_APPROVAL"""
        if source_branch.strip().upper() == dest_branch.strip().upper():
            raise ValueError("Chi nhánh nguồn và chi nhánh đích không được trùng nhau.")
        if quantity <= 0:
            raise ValueError("Số lượng điều chuyển phải lớn hơn 0.")

        # Sinh mã transfer_code dạng DC-YYYYMMDD-seq
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        seq_stmt = select(func.count(TransferOrder.transfer_id)).where(
            TransferOrder.transfer_code.like(f"DC-{today_str}-%")
        )
        count = (await session.execute(seq_stmt)).scalar() or 0
        transfer_code = f"DC-{today_str}-{(count + 1):03d}"
        transfer_id = str(uuid.uuid4())

        order = TransferOrder(
            transfer_id=transfer_id,
            transfer_code=transfer_code,
            source_branch=source_branch.strip().upper(),
            dest_branch=dest_branch.strip().upper(),
            sku=sku.strip(),
            quantity=quantity,
            saga_status=SagaStatus.PENDING_HQ_APPROVAL.value,
            created_by=user_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        session.add(order)

        # Ghi log SagaStep
        session.add(SagaStep(
            transfer_id=transfer_id,
            step_name="CREATE_TRANSFER",
            status="SUCCESS",
            payload=json.dumps({"quantity": quantity, "sku": sku, "created_by": user_id}),
            created_at=datetime.now(timezone.utc)
        ))

        logger.info(f"[SAGA INITIATED] Đơn điều chuyển {transfer_code} ({transfer_id}) được tạo, chờ HQ phê duyệt.")
        return order

    @classmethod
    async def hq_approve(
        cls,
        session: AsyncSession,
        transfer_id: str,
        manager_id: str
    ) -> TransferOrder:
        """
        Cấp 1/3: Quản lý HQ duyệt đơn điều chuyển:
        - Đổi trạng thái sang PENDING_SOURCE_APPROVAL
        - Ghi Outbox gửi lệnh cmd.transfer.approve_request.{source_branch}
        """
        order = await session.get(TransferOrder, transfer_id.strip())
        if not order:
            raise ValueError(f"Không tìm thấy đơn điều chuyển {transfer_id}.")
        if order.saga_status not in [SagaStatus.DRAFT.value, SagaStatus.PENDING_HQ_APPROVAL.value]:
            raise ValueError(f"Đơn không ở trạng thái chờ HQ duyệt (Hiện tại: {order.saga_status}).")

        order.saga_status = SagaStatus.PENDING_SOURCE_APPROVAL.value
        order.hq_approved_by = manager_id
        order.hq_approved_at = datetime.now(timezone.utc)
        order.updated_at = datetime.now(timezone.utc)

        # Tạo Event Envelope cho cmd.transfer.approve_request
        msg_id = str(uuid.uuid4())
        payload = {
            "transfer_id": order.transfer_id,
            "transfer_code": order.transfer_code,
            "source_branch": order.source_branch,
            "dest_branch": order.dest_branch,
            "sku": order.sku,
            "quantity": order.quantity
        }
        envelope = Envelope(
            message_id=msg_id,
            event_type="cmd.transfer.approve_request",
            timestamp=datetime.now(timezone.utc),
            data=payload
        )

        rkey = get_command_routing_key(ROUTING_CMD_APPROVE_REQUEST, order.source_branch)
        session.add(OutboxEvent(
            event_id=msg_id,
            routing_key=rkey,
            payload=envelope.model_dump_json(),
            is_published=False,
            next_retry_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        ))

        session.add(SagaStep(
            transfer_id=order.transfer_id,
            step_name="HQ_APPROVE",
            status="SUCCESS",
            message_id=msg_id,
            payload=json.dumps({"approved_by": manager_id}),
            created_at=datetime.now(timezone.utc)
        ))

        logger.info(f"[SAGA HQ APPROVED] Đơn {order.transfer_code} đã được HQ duyệt -> Gửi lệnh yêu cầu duyệt tới kho nguồn {order.source_branch}.")
        return order

    @classmethod
    async def hq_reject(
        cls,
        session: AsyncSession,
        transfer_id: str,
        reason: str,
        manager_id: str
    ) -> TransferOrder:
        """Quản lý HQ từ chối đơn điều chuyển"""
        order = await session.get(TransferOrder, transfer_id.strip())
        if not order:
            raise ValueError(f"Không tìm thấy đơn điều chuyển {transfer_id}.")
        if order.saga_status not in [SagaStatus.DRAFT.value, SagaStatus.PENDING_HQ_APPROVAL.value]:
            raise ValueError(f"Đơn không ở trạng thái chờ HQ duyệt (Hiện tại: {order.saga_status}).")

        order.saga_status = SagaStatus.REJECTED_BY_HQ.value
        order.hq_approved_by = manager_id
        order.hq_reject_reason = reason
        order.updated_at = datetime.now(timezone.utc)

        session.add(SagaStep(
            transfer_id=order.transfer_id,
            step_name="HQ_REJECT",
            status="FAILED",
            payload=json.dumps({"rejected_by": manager_id, "reason": reason}),
            created_at=datetime.now(timezone.utc)
        ))

        logger.info(f"[SAGA HQ REJECTED] Đơn {order.transfer_code} bị HQ từ chối: {reason}")
        return order
