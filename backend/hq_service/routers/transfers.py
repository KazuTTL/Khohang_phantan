# backend/hq_service/routers/transfers.py
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hq_service.database import get_db
from hq_service.dependencies import CurrentUser, get_current_user
from hq_service.models import TransferOrder
from hq_service.saga.orchestrator import SagaOrchestrator
from hq_service.schemas import CreateTransferRequest, StandardResponse, TransferResponse

router = APIRouter(prefix="/transfers", tags=["HQ - Distributed Stock Transfers (Saga)"])


@router.post("", response_model=StandardResponse[TransferResponse])
async def create_transfer_order(
    req: CreateTransferRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[TransferResponse]:
    """
    Khởi tạo giao dịch điều chuyển kho liên chi nhánh (Stock Transfer Saga).
    Giao dịch phân tán được điều phối theo Saga Pattern kết hợp Transactional Outbox.
    """
    if req.source_branch.strip().upper() == req.dest_branch.strip().upper():
        return StandardResponse(
            success=False,
            error="Kho nguồn và kho đích phải khác nhau."
        )

    try:
        # NGUYÊN TẮC 3: Tạo TransferOrder + OutboxMessage trong cùng 1 ACID Transaction
        order = await SagaOrchestrator.initiate_transfer(
            session=db,
            source_branch=req.source_branch.strip().upper(),
            dest_branch=req.dest_branch.strip().upper(),
            sku=req.sku.strip(),
            quantity=req.quantity
        )
        await db.commit()
        await db.refresh(order)

        return StandardResponse(
            success=True,
            data=TransferResponse(
                transfer_id=order.transfer_id,
                source_branch=order.source_branch,
                dest_branch=order.dest_branch,
                sku=order.sku,
                quantity=order.quantity,
                saga_status=order.saga_status,
                error_reason=order.error_reason,
                created_at=order.created_at,
                updated_at=order.updated_at
            )
        )
    except Exception as e:
        await db.rollback()
        return StandardResponse(success=False, error=f"Lỗi khởi tạo Saga điều chuyển: {str(e)}")


@router.get("", response_model=StandardResponse[list[TransferResponse]])
async def list_transfers(
    status: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[list[TransferResponse]]:
    """Lấy danh sách các đơn điều chuyển hàng hóa liên kho"""
    stmt = select(TransferOrder).order_by(TransferOrder.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(TransferOrder.saga_status == status.strip().upper())

    res = await db.execute(stmt)
    orders = res.scalars().all()

    data = [
        TransferResponse(
            transfer_id=o.transfer_id,
            source_branch=o.source_branch,
            dest_branch=o.dest_branch,
            sku=o.sku,
            quantity=o.quantity,
            saga_status=o.saga_status,
            error_reason=o.error_reason,
            created_at=o.created_at,
            updated_at=o.updated_at
        )
        for o in orders
    ]
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
        return StandardResponse(success=False, error=f"Không tìm thấy đơn điều chuyển {transfer_id}")

    return StandardResponse(
        success=True,
        data=TransferResponse(
            transfer_id=order.transfer_id,
            source_branch=order.source_branch,
            dest_branch=order.dest_branch,
            sku=order.sku,
            quantity=order.quantity,
            saga_status=order.saga_status,
            error_reason=order.error_reason,
            created_at=order.created_at,
            updated_at=order.updated_at
        )
    )
