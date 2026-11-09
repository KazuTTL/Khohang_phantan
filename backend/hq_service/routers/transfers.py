# backend/hq_service/routers/transfers.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hq_service.database import get_db
from hq_service.dependencies import CurrentUser, get_current_user
from hq_service.models import SagaStep, TransferOrder
from hq_service.saga.orchestrator import SagaOrchestrator
from hq_service.schemas import (
    CreateTransferRequest,
    RejectTransferRequest,
    StandardResponse,
    TransferResponse,
)

router = APIRouter(prefix="/transfers", tags=["HQ - Distributed Stock Transfers (Saga)"])


def _map_transfer(o: TransferOrder) -> TransferResponse:
    return TransferResponse(
        transfer_id=o.transfer_id,
        transfer_code=o.transfer_code,
        source_branch=o.source_branch,
        dest_branch=o.dest_branch,
        sku=o.sku,
        quantity=o.quantity,
        saga_status=o.saga_status,
        created_by=o.created_by,
        hq_approved_by=o.hq_approved_by,
        source_approved_by=o.source_approved_by,
        dest_approved_by=o.dest_approved_by,
        hq_approved_at=o.hq_approved_at,
        source_approved_at=o.source_approved_at,
        dest_approved_at=o.dest_approved_at,
        hq_reject_reason=o.hq_reject_reason,
        source_reject_reason=o.source_reject_reason,
        dest_reject_reason=o.dest_reject_reason,
        error_reason=o.error_reason,
        created_at=o.created_at,
        updated_at=o.updated_at
    )


@router.post("", response_model=StandardResponse[TransferResponse])
async def create_transfer_order(
    req: CreateTransferRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[TransferResponse]:
    """
    Khởi tạo giao dịch điều chuyển kho liên chi nhánh (Stock Transfer Saga).
    Giao dịch phân tán được điều phối theo Saga Pattern kết hợp Transactional Outbox.
    Trạng thái ban đầu: PENDING_HQ_APPROVAL.
    """
    try:
        async with db.begin():
            order = await SagaOrchestrator.create_transfer(
                session=db,
                source_branch=req.source_branch,
                dest_branch=req.dest_branch,
                sku=req.sku,
                quantity=req.quantity,
                user_id=user.user_id
            )
            await db.flush()
            return StandardResponse(success=True, data=_map_transfer(order))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khởi tạo Saga điều chuyển: {str(e)}")


@router.get("", response_model=StandardResponse[list[TransferResponse]])
async def list_transfers(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[list[TransferResponse]]:
    """Lấy danh sách các đơn điều chuyển hàng hóa toàn hệ thống"""
    stmt = select(TransferOrder).order_by(TransferOrder.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(TransferOrder.saga_status == status.strip().upper())

    res = await db.execute(stmt)
    orders = res.scalars().all()
    data = [_map_transfer(o) for o in orders]
    return StandardResponse(success=True, data=data)


@router.get("/{transfer_id}", response_model=StandardResponse[TransferResponse])
async def get_transfer_detail(
    transfer_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[TransferResponse]:
    """Xem chi tiết trạng thái Saga của một đơn điều chuyển cụ thể"""
    order = await db.get(TransferOrder, transfer_id.strip())
    if not order:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn điều chuyển {transfer_id}")
    return StandardResponse(success=True, data=_map_transfer(order))


@router.post("/{transfer_id}/hq-approve", response_model=StandardResponse[TransferResponse])
async def hq_approve_transfer(
    transfer_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[TransferResponse]:
    """
    Cấp 1/3: Quản lý Trụ sở chính (HQ_MANAGER) phê duyệt đơn điều chuyển.
    - Chuyển trạng thái: PENDING_SOURCE_APPROVAL
    - Ghi Outbox: cmd.transfer.approve_request.{source_branch}
    """
    if user.role != "HQ_MANAGER":
        raise HTTPException(status_code=403, detail="Chỉ có HQ_MANAGER mới có quyền phê duyệt cấp 1.")

    try:
        async with db.begin():
            order = await SagaOrchestrator.hq_approve(
                session=db,
                transfer_id=transfer_id.strip(),
                manager_id=user.user_id
            )
            await db.flush()
            return StandardResponse(success=True, data=_map_transfer(order))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/{transfer_id}/hq-reject", response_model=StandardResponse[TransferResponse])
async def hq_reject_transfer(
    transfer_id: str,
    body: RejectTransferRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[TransferResponse]:
    """Quản lý Trụ sở chính (HQ_MANAGER) từ chối phê duyệt đơn điều chuyển"""
    if user.role != "HQ_MANAGER":
        raise HTTPException(status_code=403, detail="Chỉ có HQ_MANAGER mới có quyền từ chối duyệt cấp 1.")

    try:
        async with db.begin():
            order = await SagaOrchestrator.hq_reject(
                session=db,
                transfer_id=transfer_id.strip(),
                reason=body.reason,
                manager_id=user.user_id
            )
            await db.flush()
            return StandardResponse(success=True, data=_map_transfer(order))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.get("/{transfer_id}/steps", response_model=StandardResponse[list[dict]])
async def get_transfer_saga_steps(
    transfer_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[list[dict]]:
    """Xem lịch sử các bước thực thi Saga (Audit Trail & Distributed Tracing)"""
    stmt = (
        select(SagaStep)
        .where(SagaStep.transfer_id == transfer_id.strip())
        .order_by(SagaStep.created_at.asc())
    )
    res = await db.execute(stmt)
    steps = res.scalars().all()

    data = [
        {
            "step_id": s.step_id,
            "transfer_id": s.transfer_id,
            "step_name": s.step_name,
            "status": s.status,
            "message_id": s.message_id,
            "payload": s.payload,
            "created_at": s.created_at
        }
        for s in steps
    ]
    return StandardResponse(success=True, data=data)
