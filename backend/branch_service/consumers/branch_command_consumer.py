# backend/branch_service/consumers/branch_command_consumer.py
import logging
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.ext.asyncio import async_sessionmaker

from branch_service.config import branch_settings
from branch_service.models import StocktakeSession, StocktakeStatus
from branch_service.services.stock_service import StockService
from branch_service.services.transfer_approval_service import TransferApprovalService
from shared.idempotency import check_inbox, mark_inbox

logger = logging.getLogger(f"BranchCommandConsumer_{branch_settings.BRANCH_CODE}")


async def on_approve_request(
    data: dict[str, Any],
    message_id: str,
    db_factory: async_sessionmaker
) -> None:
    """
    Tiếp nhận lệnh cmd.transfer.approve_request từ HQ.
    Tạo bản ghi Incoming_Transfers dạng OUTBOUND, status='AWAITING_SOURCE_APPROVAL'.
    """
    async with db_factory() as session:
        await TransferApprovalService.on_approve_request(
            db=session,
            message_id=message_id,
            data=data
        )


async def on_confirm_receive(
    data: dict[str, Any],
    message_id: str,
    db_factory: async_sessionmaker
) -> None:
    """
    Tiếp nhận lệnh cmd.transfer.confirm_receive từ HQ.
    Tạo bản ghi Incoming_Transfers dạng INBOUND, status='AWAITING_DEST_APPROVAL'.
    """
    async with db_factory() as session:
        await TransferApprovalService.on_confirm_receive(
            db=session,
            message_id=message_id,
            data=data
        )


async def on_release_command(
    data: dict[str, Any],
    message_id: str,
    db_factory: async_sessionmaker
) -> None:
    """
    Tiếp nhận lệnh bù trừ CMD_RELEASE_STOCK khi chuyển kho bị hủy/từ chối.
    Hoàn trả lại số lượng đang giữ (reserved) về tồn khả dụng (available).
    """
    transfer_id = data.get("transfer_id")
    sku = data.get("sku")
    quantity = int(data.get("quantity", 0))

    if not transfer_id or not sku or quantity <= 0:
        logger.warning(f"[RELEASE INVALID] Dữ liệu release không hợp lệ: {data}")
        return

    async with db_factory() as session:
        await StockService.release_stock(
            db=session,
            transfer_id=transfer_id,
            message_id=message_id,
            sku=sku,
            quantity=quantity
        )


async def on_transfer_completed(
    data: dict[str, Any],
    message_id: str,
    db_factory: async_sessionmaker
) -> None:
    """
    Tiếp nhận sự kiện EVT_TRANSFER_COMPLETED:
    Nếu chi nhánh này là kho nguồn (source_branch) -> Gọi commit_out để trừ dứt điểm hàng giữ.
    """
    source_branch = data.get("source_branch")
    if source_branch == branch_settings.BRANCH_CODE:
        transfer_id = data.get("transfer_id")
        sku = data.get("sku")
        quantity = int(data.get("quantity", 0))
        async with db_factory() as session:
            await StockService.commit_out(
                db=session,
                transfer_id=transfer_id,
                message_id=message_id,
                sku=sku,
                quantity=quantity
            )


async def on_stocktake_finalize(
    data: dict[str, Any],
    message_id: str,
    db_factory: async_sessionmaker
) -> None:
    """
    Tiếp nhận lệnh chốt sổ kiểm kê từ Trụ sở chính: cmd.stocktake.finalize.{BRANCH_CODE}.
    Chuyển trạng thái phiên kiểm kê -> FINALIZED.
    """
    session_id = data.get("session_id")
    if not session_id:
        return

    async with db_factory() as session:
        async with session.begin():
            if message_id and await check_inbox(session, message_id):
                return

            st_session = await session.get(StocktakeSession, session_id)
            if st_session:
                st_session.status = "FINALIZED"
                st_session.finalized_at = datetime.now(timezone.utc)
                st_session.finalized_by = "HQ_COMMAND"
                logger.info(f"[STOCKTAKE FINALIZED] Phiên kiểm kê {st_session.session_code} đã được chốt sổ bởi HQ.")

            if message_id:
                await mark_inbox(session, message_id, "cmd.stocktake.finalize")


async def dispatch_branch_message(
    message_data: dict[str, Any],
    routing_key: str,
    db_factory: async_sessionmaker
) -> None:
    """Bộ điều phối trung tâm cho toàn bộ command và event nhận được từ RabbitMQ"""
    msg_id = message_data.get("message_id") or ""
    event_type = message_data.get("event_type") or ""
    # Dữ liệu có thể nằm trong 'data' (Envelope chuẩn) hoặc 'payload' (legacy)
    data = message_data.get("data") or message_data.get("payload") or {}

    logger.info(f"[DISPATCH BRANCH] msg_id={msg_id}, type={event_type}, rkey={routing_key}")

    if event_type in ["cmd.transfer.approve_request", "CMD_RESERVE_STOCK"] or "approve_request" in routing_key:
        await on_approve_request(data, msg_id, db_factory)
    elif event_type in ["cmd.transfer.confirm_receive", "CMD_IMPORT_TRANSFER"] or "confirm_receive" in routing_key:
        await on_confirm_receive(data, msg_id, db_factory)
    elif event_type in ["cmd.transfer.release", "CMD_RELEASE_STOCK"] or "release" in routing_key:
        await on_release_command(data, msg_id, db_factory)
    elif event_type in ["evt.transfer.completed", "EVT_TRANSFER_COMPLETED"] or "completed" in routing_key:
        await on_transfer_completed(data, msg_id, db_factory)
    elif event_type in ["cmd.stocktake.finalize", "CMD_STOCKTAKE_FINALIZE"] or "finalize" in routing_key:
        await on_stocktake_finalize(data, msg_id, db_factory)
    else:
        logger.debug(f"[DISPATCH BRANCH] Bỏ qua message không quan tâm: {event_type} ({routing_key})")
