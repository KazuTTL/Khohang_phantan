# backend/hq_service/saga/handlers.py
import json
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hq_service.models import OutboxMessage, TransferOrder
from hq_service.saga.state import SagaStatus
from shared.event_schemas import (
    CmdImportTransferPayload, CmdReleaseStockPayload,
    EvtReserveFailedPayload, EvtStockReleasedPayload, EvtStockReservedPayload,
    EvtTransferCompletedPayload, EvtTransferRejectedPayload, EventEnvelope
)
from shared.messaging_topology import (
    ROUTING_CMD_IMPORT, ROUTING_CMD_RELEASE, get_command_routing_key
)

logger = logging.getLogger("SagaHandlers")


class SagaStepHandlers:
    """
    Xử lý các sự kiện phản hồi từ các Chi nhánh gửi về Trụ sở chính (HQ).
    Mọi bước ghi/chuyển trạng thái đều kèm Outbox Message trong cùng 1 ACID transaction.
    """

    @staticmethod
    async def handle_stock_reserved(session: AsyncSession, event: EvtStockReservedPayload) -> None:
        """
        Phase 1 Thành công: Kho nguồn đã giữ hàng xong.
        Chuyển trạng thái -> RESERVED_IN_TRANSIT
        Phát lệnh Phase 2: CMD_IMPORT_TRANSFER tới kho đích qua Outbox.
        """
        stmt = select(TransferOrder).where(TransferOrder.transfer_id == event.transfer_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            logger.warning(f"[SAGA] Không tìm thấy TransferOrder {event.transfer_id}")
            return

        order.saga_status = SagaStatus.RESERVED_IN_TRANSIT.value
        order.updated_at = datetime.now(timezone.utc)

        # Tạo lệnh CMD_IMPORT_TRANSFER gửi kho đích
        envelope = EventEnvelope[CmdImportTransferPayload](
            message_id=str(uuid.uuid4()),
            correlation_id=order.transfer_id,
            event_type="CMD_IMPORT_TRANSFER",
            source="HQ_SERVICE",
            payload=CmdImportTransferPayload(
                transfer_id=order.transfer_id,
                source_branch=order.source_branch,
                dest_branch=order.dest_branch,
                sku=order.sku,
                quantity=order.quantity
            )
        )
        routing_key = get_command_routing_key(ROUTING_CMD_IMPORT, order.dest_branch)

        outbox = OutboxMessage(
            message_id=envelope.message_id,
            event_type="CMD_IMPORT_TRANSFER",
            routing_key=routing_key,
            payload=json.dumps(envelope.model_dump(mode="json")),
            status="PENDING",
            created_at=datetime.now(timezone.utc)
        )
        session.add(outbox)
        logger.info(f"[SAGA] Đơn {order.transfer_id} chuyển trạng thái RESERVED_IN_TRANSIT -> Phát lệnh nhập kho đích {order.dest_branch}")

    @staticmethod
    async def handle_reserve_failed(session: AsyncSession, event: EvtReserveFailedPayload) -> None:
        """
        Phase 1 Thất bại: Kho nguồn không đủ hàng tồn khả dụng.
        Chuyển trạng thái -> FAILED.
        """
        stmt = select(TransferOrder).where(TransferOrder.transfer_id == event.transfer_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if order:
            order.saga_status = SagaStatus.FAILED.value
            order.error_reason = f"Kho nguồn {event.source_branch} giữ hàng thất bại: {event.reason}"
            order.updated_at = datetime.now(timezone.utc)
            logger.warning(f"[SAGA] Đơn {order.transfer_id} FAILED: {order.error_reason}")

    @staticmethod
    async def handle_transfer_completed(session: AsyncSession, event: EvtTransferCompletedPayload) -> None:
        """
        Phase 2 Thành công: Kho đích đã xác nhận nhập kho thành công.
        Chuyển trạng thái -> COMPLETED (Giao dịch phân tán thành công trọn vẹn).
        """
        stmt = select(TransferOrder).where(TransferOrder.transfer_id == event.transfer_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if order:
            order.saga_status = SagaStatus.COMPLETED.value
            order.updated_at = datetime.now(timezone.utc)
            logger.info(f"[SAGA] Đơn {order.transfer_id} COMPLETED: Hoàn tất chuyển hàng từ {order.source_branch} -> {order.dest_branch}")

    @staticmethod
    async def handle_transfer_rejected(session: AsyncSession, event: EvtTransferRejectedPayload) -> None:
        """
        Phase 2 Thất bại: Kho đích từ chối nhận hoặc gặp sự cố quá tải.
        Kích hoạt Giao dịch bù trừ (Compensating Transaction):
        Chuyển trạng thái -> COMPENSATING
        Phát lệnh CMD_RELEASE_STOCK gửi ngược về kho nguồn để hoàn trả hàng qua Outbox.
        """
        stmt = select(TransferOrder).where(TransferOrder.transfer_id == event.transfer_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            return

        order.saga_status = SagaStatus.COMPENSATING.value
        order.error_reason = f"Kho đích {event.dest_branch} từ chối nhận: {event.reason}"
        order.updated_at = datetime.now(timezone.utc)

        # Lệnh bù trừ hoàn trả hàng cho kho nguồn
        envelope = EventEnvelope[CmdReleaseStockPayload](
            message_id=str(uuid.uuid4()),
            correlation_id=order.transfer_id,
            event_type="CMD_RELEASE_STOCK",
            source="HQ_SERVICE",
            payload=CmdReleaseStockPayload(
                transfer_id=order.transfer_id,
                source_branch=order.source_branch,
                sku=order.sku,
                quantity=order.quantity,
                reason=event.reason
            )
        )
        routing_key = get_command_routing_key(ROUTING_CMD_RELEASE, order.source_branch)

        outbox = OutboxMessage(
            message_id=envelope.message_id,
            event_type="CMD_RELEASE_STOCK",
            routing_key=routing_key,
            payload=json.dumps(envelope.model_dump(mode="json")),
            status="PENDING",
            created_at=datetime.now(timezone.utc)
        )
        session.add(outbox)
        logger.warning(f"[SAGA COMPENSATE] Đơn {order.transfer_id} COMPENSATING -> Gửi lệnh hoàn trả kho nguồn {order.source_branch}")

    @staticmethod
    async def handle_stock_released(session: AsyncSession, event: EvtStockReleasedPayload) -> None:
        """
        Giao dịch bù trừ hoàn tất: Kho nguồn đã giải phóng số hàng giữ.
        Chuyển trạng thái -> ROLLED_BACK.
        """
        stmt = select(TransferOrder).where(TransferOrder.transfer_id == event.transfer_id)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if order:
            order.saga_status = SagaStatus.ROLLED_BACK.value
            order.updated_at = datetime.now(timezone.utc)
            logger.info(f"[SAGA ROLLBACK COMPLETED] Đơn {order.transfer_id} đã ROLLED_BACK an toàn!")
