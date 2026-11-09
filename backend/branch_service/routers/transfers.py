# backend/branch_service/routers/transfers.py
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.database import get_db
from branch_service.models import IncomingTransfer
from branch_service.schemas import RejectTransferRequest, StandardResponse, TransferItemResponse
from branch_service.services.transfer_approval_service import TransferApprovalService

router = APIRouter(prefix="/transfers", tags=["Branch - Transfers (Phê duyệt điều chuyển)"])


class DestApproveBody(BaseModel):
    received_qty: int | None = Field(default=None, ge=1, description="Số lượng thực nhận (nếu None sẽ lấy bằng quantity)")


@router.get("", response_model=StandardResponse[list[TransferItemResponse]])
async def list_transfers(
    transfer_type: str | None = Query(default=None, description="INBOUND hoặc OUTBOUND"),
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Danh sách các đơn điều chuyển đi/đến chi nhánh"""
    stmt = select(IncomingTransfer).order_by(IncomingTransfer.created_at.desc()).limit(limit)
    if transfer_type:
        stmt = stmt.where(IncomingTransfer.type == transfer_type.strip().upper())
    if status:
        stmt = stmt.where(IncomingTransfer.status == status.strip().upper())

    res = await db.execute(stmt)
    transfers = res.scalars().all()

    data = [
        TransferItemResponse(
            transfer_id=t.transfer_id,
            transfer_code=t.transfer_code,
            type=t.type,
            sku=t.sku,
            quantity=t.quantity,
            source_branch=t.source_branch,
            dest_branch=t.dest_branch,
            status=t.status,
            reject_reason=t.reject_reason,
            received_qty=t.received_qty,
            created_at=t.created_at,
            updated_at=t.updated_at
        )
        for t in transfers
    ]
    return StandardResponse(success=True, data=data, error=None)


@router.get("/incoming", response_model=StandardResponse[list[TransferItemResponse]])
async def list_incoming_transfers(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Danh sách các đơn điều chuyển đến chi nhánh (INBOUND)"""
    return await list_transfers(transfer_type="INBOUND", status=None, limit=limit, db=db)


@router.get("/{transfer_id}", response_model=StandardResponse[TransferItemResponse])
async def get_transfer_detail(
    transfer_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Xem chi tiết đơn điều chuyển"""
    t = await db.get(IncomingTransfer, transfer_id.strip())
    if not t:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn điều chuyển {transfer_id}.")

    return StandardResponse(
        success=True,
        data=TransferItemResponse(
            transfer_id=t.transfer_id,
            transfer_code=t.transfer_code,
            type=t.type,
            sku=t.sku,
            quantity=t.quantity,
            source_branch=t.source_branch,
            dest_branch=t.dest_branch,
            status=t.status,
            reject_reason=t.reject_reason,
            received_qty=t.received_qty,
            created_at=t.created_at,
            updated_at=t.updated_at
        ),
        error=None
    )


@router.post("/{transfer_id}/source-approve", response_model=StandardResponse[dict])
async def source_approve_transfer(
    transfer_id: str,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="manager_hn"),
    x_role: str | None = Header(default="BRANCH_MANAGER")
):
    """
    Cấp 2/3: Quản lý chi nhánh NGUỒN phê duyệt xuất chuyển hàng:
    - Khóa dòng Local_Inventory WITH (UPDLOCK, ROWLOCK)
    - Kiểm tra và trừ available_qty, tăng reserved_qty
    - Ghi Stock_Ledger RESERVE
    - Ghi Outbox 'evt.transfer.source_approved'
    """
    res = await TransferApprovalService.source_approve(
        db=db,
        transfer_id=transfer_id.strip(),
        manager_id=x_user_id or "manager_hn"
    )
    return StandardResponse(success=True, data=res, error=None)


@router.post("/{transfer_id}/source-reject", response_model=StandardResponse[dict])
async def source_reject_transfer(
    transfer_id: str,
    body: RejectTransferRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="manager_hn"),
    x_role: str | None = Header(default="BRANCH_MANAGER")
):
    """Quản lý chi nhánh NGUỒN từ chối xuất chuyển hàng"""
    await TransferApprovalService.source_reject(
        db=db,
        transfer_id=transfer_id.strip(),
        reason=body.reason,
        manager_id=x_user_id or "manager_hn"
    )
    return StandardResponse(
        success=True,
        data={"transfer_id": transfer_id, "status": "SOURCE_REJECTED", "message": "Đã từ chối xuất hàng."},
        error=None
    )


@router.post("/{transfer_id}/dest-approve", response_model=StandardResponse[dict])
@router.post("/{transfer_id}/confirm", response_model=StandardResponse[dict])
async def dest_approve_transfer(
    transfer_id: str,
    body: DestApproveBody | None = None,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="manager_hcm"),
    x_role: str | None = Header(default="BRANCH_MANAGER")
):
    """
    Cấp 3/3: Quản lý chi nhánh ĐÍCH phê duyệt nhập kho lô hàng:
    - Khóa dòng Local_Inventory WITH (UPDLOCK, ROWLOCK)
    - Tăng available_qty của chi nhánh đích
    - Ghi Stock_Ledger TRANSFER_IN
    - Ghi Outbox 'evt.transfer.dest_approved' + 'evt.inventory.updated'
    """
    in_t = await db.get(IncomingTransfer, transfer_id.strip())
    if not in_t:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn điều chuyển {transfer_id}.")

    received_qty = body.received_qty if (body and body.received_qty is not None) else in_t.quantity

    res = await TransferApprovalService.dest_approve(
        db=db,
        transfer_id=transfer_id.strip(),
        received_qty=received_qty,
        manager_id=x_user_id or "manager_hcm"
    )
    return StandardResponse(success=True, data=res, error=None)


@router.post("/{transfer_id}/dest-reject", response_model=StandardResponse[dict])
@router.post("/{transfer_id}/reject", response_model=StandardResponse[dict])
async def dest_reject_transfer(
    transfer_id: str,
    body: RejectTransferRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="manager_hcm"),
    x_role: str | None = Header(default="BRANCH_MANAGER")
):
    """Quản lý chi nhánh ĐÍCH từ chối nhận hàng (Kích hoạt Saga Compensation hoàn trả hàng cho kho nguồn)"""
    await TransferApprovalService.dest_reject(
        db=db,
        transfer_id=transfer_id.strip(),
        reason=body.reason,
        manager_id=x_user_id or "manager_hcm"
    )
    return StandardResponse(
        success=True,
        data={"transfer_id": transfer_id, "status": "DEST_REJECTED", "message": "Đã từ chối nhận hàng, kích hoạt hoàn trả kho nguồn."},
        error=None
    )
