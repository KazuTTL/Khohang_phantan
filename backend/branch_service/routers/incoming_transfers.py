# backend/branch_service/routers/incoming_transfers.py
import logging
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.config import branch_settings
from branch_service.database import get_db
from branch_service.schemas import RejectTransferRequest, StandardResponse
from branch_service.services.outbox_service import OutboxService
from branch_service.services.stock_service import StockService
from shared.event_schemas import EvtTransferRejectedPayload
from shared.messaging_topology import ROUTING_EVT_TRANSFER_REJECTED

logger = logging.getLogger(f"IncomingTransfers_{branch_settings.BRANCH_CODE}")
router = APIRouter(prefix="/transfers", tags=["Branch - Incoming Transfers Confirmation / Rejection"])


@router.post("/{transfer_id}/confirm", response_model=StandardResponse[dict])
async def confirm_incoming_transfer(
    transfer_id: str,
    sku: str = "BAN-PHIM-CO",
    source_branch: str = "HN",
    quantity: int = 10,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(None)
) -> StandardResponse[dict]:
    """
    Thủ kho tại chi nhánh đích bấm Xác nhận nhập kho lô hàng điều chuyển.
    Thực hiện nhập kho và phát sự kiện EVT_TRANSFER_COMPLETED qua Outbox.
    """
    try:
        await StockService.import_incoming_stock(
            session=db,
            transfer_id=transfer_id.strip(),
            source_branch=source_branch.strip(),
            sku=sku.strip(),
            quantity=quantity
        )
        await db.commit()
        return StandardResponse(
            success=True,
            data={
                "transfer_id": transfer_id,
                "status": "CONFIRMED_AND_IMPORTED",
                "message": f"Chi nhánh {branch_settings.BRANCH_CODE} đã tiếp nhận thành công {quantity} {sku}."
            }
        )
    except Exception as e:
        await db.rollback()
        return StandardResponse(success=False, error=f"Lỗi tiếp nhận hàng: {str(e)}")


@router.post("/{transfer_id}/reject", response_model=StandardResponse[dict])
async def reject_incoming_transfer(
    transfer_id: str,
    req: RejectTransferRequest,
    sku: str = "BAN-PHIM-CO",
    source_branch: str = "HN",
    quantity: int = 10,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(None)
) -> StandardResponse[dict]:
    """
    Thủ kho từ chối nhận hàng điều chuyển (ví dụ: kho quá tải, hàng hỏng).
    Kích hoạt Giao dịch Bù trừ (Compensating Transaction / Rollback):
    Ghi Outbox EVT_TRANSFER_REJECTED để HQ gửi lệnh hoàn trả lại cho kho nguồn.
    """
    try:
        # NGUYÊN TẮC 3: Ghi Outbox EVT_TRANSFER_REJECTED trong ACID transaction
        OutboxService.create_outbox_message(
            session=db,
            event_type="EVT_TRANSFER_REJECTED",
            routing_key=ROUTING_EVT_TRANSFER_REJECTED,
            source=f"BRANCH_{branch_settings.BRANCH_CODE}",
            payload_model=EvtTransferRejectedPayload(
                transfer_id=transfer_id.strip(),
                source_branch=source_branch.strip(),
                dest_branch=branch_settings.BRANCH_CODE,
                sku=sku.strip(),
                quantity=quantity,
                reason=req.reason.strip()
            ),
            correlation_id=transfer_id
        )
        await db.commit()

        logger.warning(f"[TRANSFER REJECTED] Kho {branch_settings.BRANCH_CODE} từ chối đơn {transfer_id}: {req.reason}")
        return StandardResponse(
            success=True,
            data={
                "transfer_id": transfer_id,
                "status": "REJECTED_TRIGGER_COMPENSATION",
                "reason": req.reason,
                "message": "Đã từ chối đơn và gửi thông báo kích hoạt Giao dịch bù trừ (Rollback) hoàn kho nguồn."
            }
        )
    except Exception as e:
        await db.rollback()
        return StandardResponse(success=False, error=f"Lỗi từ chối đơn: {str(e)}")
