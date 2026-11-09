# backend/hq_service/saga/handlers.py
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from hq_service.models import OutboxEvent, SagaStep, TransferOrder
from hq_service.saga.state import SagaStatus
from shared.event_schemas import Envelope
from shared.messaging_topology import (
    ROUTING_CMD_CONFIRM_RECEIVE,
    ROUTING_CMD_RELEASE,
    ROUTING_EVT_TRANSFER_COMPLETED,
    get_command_routing_key,
)

logger = logging.getLogger("SagaStepHandlers")


class SagaStepHandlers:
    """
    Xử lý các sự kiện phản hồi từ các Chi nhánh gửi về Trụ sở chính (HQ).
    Mọi bước chuyển trạng thái Saga đều kèm Outbox Event trong cùng 1 ACID transaction.
    """

    @staticmethod
    async def handle_source_approved(session: AsyncSession, data: dict[str, Any], message_id: str) -> None:
        """
        Cấp 2/3 Thành công: Kho nguồn đã duyệt xuất và giữ hàng thành công.
        Chuyển trạng thái -> PENDING_DEST_APPROVAL.
        Phát lệnh Cấp 3/3: cmd.transfer.confirm_receive.{dest_branch} tới kho đích.
        """
        transfer_id = data.get("transfer_id")
        order = await session.get(TransferOrder, transfer_id)
        if not order:
            logger.warning(f"[SAGA] Không tìm thấy đơn điều chuyển {transfer_id}")
            return

        order.saga_status = SagaStatus.PENDING_DEST_APPROVAL.value
        order.source_approved_by = data.get("approved_by")
        order.source_approved_at = datetime.now(timezone.utc)
        order.updated_at = datetime.now(timezone.utc)

        # Tạo lệnh cmd.transfer.confirm_receive gửi chi nhánh đích
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
            event_type="cmd.transfer.confirm_receive",
            timestamp=datetime.now(timezone.utc),
            data=payload
        )
        rkey = get_command_routing_key(ROUTING_CMD_CONFIRM_RECEIVE, order.dest_branch)

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
            step_name="SOURCE_APPROVE",
            status="SUCCESS",
            message_id=message_id,
            payload=json.dumps(data),
            created_at=datetime.now(timezone.utc)
        ))
        logger.info(f"[SAGA] Đơn {order.transfer_code} kho nguồn {order.source_branch} đã duyệt -> Gửi lệnh tiếp nhận tới kho đích {order.dest_branch}.")

    @staticmethod
    async def handle_source_rejected(session: AsyncSession, data: dict[str, Any], message_id: str) -> None:
        """Kho nguồn từ chối xuất kho -> Chuyển trạng thái REJECTED_BY_SOURCE"""
        transfer_id = data.get("transfer_id")
        order = await session.get(TransferOrder, transfer_id)
        if not order:
            return

        order.saga_status = SagaStatus.REJECTED_BY_SOURCE.value
        order.source_reject_reason = data.get("reason")
        order.updated_at = datetime.now(timezone.utc)

        session.add(SagaStep(
            transfer_id=order.transfer_id,
            step_name="SOURCE_REJECT",
            status="FAILED",
            message_id=message_id,
            payload=json.dumps(data),
            created_at=datetime.now(timezone.utc)
        ))
        logger.warning(f"[SAGA] Đơn {order.transfer_code} bị kho nguồn từ chối: {order.source_reject_reason}")

    @staticmethod
    async def handle_reserve_failed(session: AsyncSession, data: dict[str, Any], message_id: str) -> None:
        """Kho nguồn không đủ hàng để giữ -> Chuyển trạng thái FAILED"""
        transfer_id = data.get("transfer_id")
        order = await session.get(TransferOrder, transfer_id)
        if not order:
            return

        order.saga_status = SagaStatus.FAILED.value
        order.error_reason = data.get("reason", "Kho nguồn không đủ hàng khả dụng")
        order.updated_at = datetime.now(timezone.utc)

        session.add(SagaStep(
            transfer_id=order.transfer_id,
            step_name="RESERVE_FAILED",
            status="FAILED",
            message_id=message_id,
            payload=json.dumps(data),
            created_at=datetime.now(timezone.utc)
        ))
        logger.warning(f"[SAGA] Đơn {order.transfer_code} thất bại do kho nguồn không đủ hàng: {order.error_reason}")

    @staticmethod
    async def handle_dest_approved(session: AsyncSession, data: dict[str, Any], message_id: str) -> None:
        """
        Cấp 3/3 Thành công: Kho đích đã duyệt và nhập kho thành công.
        Chuyển trạng thái Saga -> COMPLETED (Hoàn tất giao dịch phân tán trọn vẹn).
        Phát sự kiện evt.transfer.completed để kho nguồn trừ dứt điểm hàng giữ.
        """
        transfer_id = data.get("transfer_id")
        order = await session.get(TransferOrder, transfer_id)
        if not order:
            return

        order.saga_status = SagaStatus.COMPLETED.value
        order.dest_approved_by = data.get("approved_by")
        order.dest_approved_at = datetime.now(timezone.utc)
        order.updated_at = datetime.now(timezone.utc)

        # Phát evt.transfer.completed cho toàn hệ thống & kho nguồn
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
            event_type="evt.transfer.completed",
            timestamp=datetime.now(timezone.utc),
            data=payload
        )

        session.add(OutboxEvent(
            event_id=msg_id,
            routing_key=ROUTING_EVT_TRANSFER_COMPLETED,
            payload=envelope.model_dump_json(),
            is_published=False,
            next_retry_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        ))

        session.add(SagaStep(
            transfer_id=order.transfer_id,
            step_name="DEST_APPROVE_COMPLETED",
            status="SUCCESS",
            message_id=message_id,
            payload=json.dumps(data),
            created_at=datetime.now(timezone.utc)
        ))
        logger.info(f"[SAGA COMPLETED] Đơn {order.transfer_code} đã hoàn thành trọn vẹn 3 cấp phê duyệt!")

    @staticmethod
    async def handle_dest_rejected(session: AsyncSession, data: dict[str, Any], message_id: str) -> None:
        """
        Cấp 3/3 Thất bại: Kho đích từ chối nhận hàng.
        Kích hoạt Giao dịch bù trừ (Compensating Transaction):
        Chuyển trạng thái -> COMPENSATING.
        Phát lệnh cmd.transfer.release.{source_branch} gửi về kho nguồn để hoàn trả hàng giữ.
        """
        transfer_id = data.get("transfer_id")
        order = await session.get(TransferOrder, transfer_id)
        if not order:
            return

        order.saga_status = SagaStatus.COMPENSATING.value
        order.dest_reject_reason = data.get("reason")
        order.updated_at = datetime.now(timezone.utc)

        # Lệnh bù trừ hoàn trả hàng cho kho nguồn
        msg_id = str(uuid.uuid4())
        payload = {
            "transfer_id": order.transfer_id,
            "transfer_code": order.transfer_code,
            "source_branch": order.source_branch,
            "sku": order.sku,
            "quantity": order.quantity,
            "reason": order.dest_reject_reason
        }
        envelope = Envelope(
            message_id=msg_id,
            event_type="cmd.transfer.release",
            timestamp=datetime.now(timezone.utc),
            data=payload
        )
        rkey = get_command_routing_key(ROUTING_CMD_RELEASE, order.source_branch)

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
            step_name="DEST_REJECT_COMPENSATING",
            status="FAILED",
            message_id=message_id,
            payload=json.dumps(data),
            created_at=datetime.now(timezone.utc)
        ))
        logger.warning(f"[SAGA COMPENSATE] Đơn {order.transfer_code} bị kho đích từ chối -> Kích hoạt hoàn trả kho nguồn {order.source_branch}.")

    @staticmethod
    async def handle_stock_released(session: AsyncSession, data: dict[str, Any], message_id: str) -> None:
        """Giao dịch bù trừ hoàn tất: Kho nguồn đã giải phóng hàng giữ -> ROLLED_BACK"""
        transfer_id = data.get("transfer_id")
        order = await session.get(TransferOrder, transfer_id)
        if not order:
            return

        order.saga_status = SagaStatus.ROLLED_BACK.value
        order.updated_at = datetime.now(timezone.utc)

        session.add(SagaStep(
            transfer_id=order.transfer_id,
            step_name="ROLLBACK_COMPLETED",
            status="COMPENSATED",
            message_id=message_id,
            payload=json.dumps(data),
            created_at=datetime.now(timezone.utc)
        ))
        logger.info(f"[SAGA ROLLBACK COMPLETED] Đơn {order.transfer_code} đã hoàn trả hàng về kho nguồn an toàn.")
