# backend/branch_service/routers/stocktakes.py
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from branch_service.database import get_db
from branch_service.models import (
    BranchUser, LocalInventory, LocalProduct, StocktakeAuditLog,
    StocktakeItem, StocktakeSession
)
from branch_service.schemas import (
    StandardResponse,
    StocktakeBatchCountRequest,
    StocktakeCountItem,
    StocktakeCreate,
    StocktakeItemResponse,
    StocktakeRejectRequest,
    StocktakeSessionResponse,
)
from branch_service.services.stocktake_service import StocktakeService

router = APIRouter(prefix="/stocktakes", tags=["Branch - Stocktaking Lifecycle (Kiểm kê kho)"])


def _to_str(val: any) -> str:
    if hasattr(val, "value"):
        return str(val.value)
    return str(val) if val is not None else ""


def _map_session_to_response(s: StocktakeSession) -> StocktakeSessionResponse:
    items_resp = [
        StocktakeItemResponse(
            item_id=it.item_id,
            session_id=it.session_id,
            sku=it.sku,
            system_qty_at_start=it.system_qty_at_start,
            counted_qty=it.counted_qty,
            variance_qty=it.variance_qty,
            variance_reason=it.variance_reason,
            status=_to_str(it.status),
            counted_at=it.counted_at,
            adjusted_at=it.adjusted_at
        )
        for it in (s.items or [])
    ]
    return StocktakeSessionResponse(
        session_id=s.session_id,
        session_code=s.session_code,
        branch_code=s.branch_code,
        status=_to_str(s.status),
        scope_type=_to_str(s.scope_type),
        scope_note=s.scope_note,
        created_by=s.created_by,
        counted_by=s.counted_by,
        approved_by=s.approved_by,
        finalized_by=s.finalized_by,
        created_at=s.created_at,
        counting_started_at=s.counting_started_at,
        submitted_at=s.submitted_at,
        approved_at=s.approved_at,
        rejected_at=s.rejected_at,
        cancelled_at=s.cancelled_at,
        finalized_at=s.finalized_at,
        cancel_reason=s.cancel_reason,
        reject_reason=s.reject_reason,
        items=items_resp
    )


@router.get("", response_model=StandardResponse[list[StocktakeSessionResponse]])
async def list_stocktakes(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Lấy danh sách các phiên kiểm kê tại chi nhánh"""
    stmt = (
        select(StocktakeSession)
        .options(selectinload(StocktakeSession.items))
        .order_by(StocktakeSession.created_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(StocktakeSession.status == status.strip().upper())

    res = await db.execute(stmt)
    sessions = res.scalars().all()
    data = [_map_session_to_response(s) for s in sessions]
    return StandardResponse(success=True, data=data, error=None)


@router.get("/preview", response_model=StandardResponse[list[dict]])
async def preview_stocktake_items(
    scope_type: str = "FULL",
    sku_list: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Xem trước danh sách và số lượng tồn kho hệ thống của các mặt hàng sẽ kiểm kê"""
    stmt = (
        select(LocalInventory.sku, LocalProduct.product_name, LocalProduct.unit, LocalInventory.available_qty)
        .outerjoin(LocalProduct, LocalInventory.sku == LocalProduct.sku)
    )
    if scope_type.strip().upper() in ["BY_SKU", "PARTIAL"] and sku_list:
        skus = [s.strip() for s in sku_list.split(",") if s.strip()]
        stmt = stmt.where(LocalInventory.sku.in_(skus))

    res = await db.execute(stmt)
    rows = res.all()

    data = [
        {
            "sku": r[0],
            "product_name": r[1] or r[0],
            "unit": r[2] or "Chiếc",
            "available_qty": r[3]
        }
        for r in rows
    ]
    return StandardResponse(success=True, data=data, error=None)


@router.get("/{session_id}", response_model=StandardResponse[StocktakeSessionResponse])
async def get_stocktake_detail(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Xem chi tiết một phiên kiểm kê cùng toàn bộ danh sách mặt hàng đã/chưa kiểm đếm"""
    stmt = (
        select(StocktakeSession)
        .options(selectinload(StocktakeSession.items))
        .where(StocktakeSession.session_id == session_id.strip())
    )
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy phiên kiểm kê {session_id}")

    return StandardResponse(success=True, data=_map_session_to_response(session), error=None)


@router.post("", response_model=StandardResponse[dict])
async def create_stocktake(
    body: StocktakeCreate,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="auditor_hn"),
    x_role: str | None = Header(default="AUDITOR")
):
    """Khởi tạo đợt kiểm kê mới (DRAFT) và kích hoạt đóng băng hàng hóa"""
    session = await StocktakeService.create_stocktake(
        db=db,
        scope_type=body.scope_type,
        scope_sku_list=body.scope_sku_list,
        note=body.note,
        user_id=x_user_id or "auditor_hn"
    )
    return StandardResponse(
        success=True,
        data={
            "session_id": session.session_id,
            "session_code": session.session_code,
            "status": _to_str(session.status),
            "scope_type": _to_str(session.scope_type)
        },
        error=None
    )


@router.post("/{session_id}/start", response_model=StandardResponse[dict])
async def start_stocktake(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="auditor_hn"),
    x_role: str | None = Header(default="AUDITOR")
):
    """Bắt đầu quá trình đếm thực tế (COUNTING)"""
    await StocktakeService.start_counting(db=db, session_id=session_id.strip(), user_id=x_user_id or "auditor_hn")
    return StandardResponse(success=True, data={"session_id": session_id, "status": "COUNTING"}, error=None)


@router.post("/{session_id}/items/{sku}/count", response_model=StandardResponse[dict])
async def count_single_item(
    session_id: str,
    sku: str,
    actual_qty: int = Query(..., ge=0),
    variance_reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="auditor_hn"),
    x_role: str | None = Header(default="AUDITOR")
):
    """Nhập số lượng thực tế kiểm đếm được của 1 SKU"""
    item = await StocktakeService.count_item(
        db=db,
        session_id=session_id.strip(),
        sku=sku.strip(),
        counted_qty=actual_qty,
        variance_reason=variance_reason,
        user_id=x_user_id or "auditor_hn"
    )
    return StandardResponse(
        success=True,
        data={
            "sku": item.sku,
            "system_qty": item.system_qty_at_start,
            "counted_qty": item.counted_qty,
            "variance_qty": item.variance_qty,
            "status": _to_str(item.status)
        },
        error=None
    )


@router.post("/{session_id}/items/bulk-count", response_model=StandardResponse[list[dict]])
async def bulk_count_items(
    session_id: str,
    body: StocktakeBatchCountRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="auditor_hn"),
    x_role: str | None = Header(default="AUDITOR")
):
    """Nhập hàng loạt số lượng kiểm đếm cho nhiều sản phẩm cùng lúc"""
    counted_results = []
    for it in body.items:
        res = await StocktakeService.count_item(
            db=db,
            session_id=session_id.strip(),
            sku=it.sku.strip(),
            counted_qty=it.actual_qty,
            variance_reason=it.variance_reason,
            user_id=x_user_id or "auditor_hn"
        )
        counted_results.append({
            "sku": res.sku,
            "counted_qty": res.counted_qty,
            "variance_qty": res.variance_qty
        })
    return StandardResponse(success=True, data=counted_results, error=None)


@router.post("/{session_id}/submit", response_model=StandardResponse[dict])
async def submit_stocktake_for_approval(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="auditor_hn"),
    x_role: str | None = Header(default="AUDITOR")
):
    """Nộp kết quả kiểm kê lên Quản lý chi nhánh chờ duyệt (PENDING_APPROVAL)"""
    await StocktakeService.submit_stocktake(db=db, session_id=session_id.strip(), user_id=x_user_id or "auditor_hn")
    return StandardResponse(success=True, data={"session_id": session_id, "status": "PENDING_APPROVAL"}, error=None)


@router.post("/{session_id}/approve", response_model=StandardResponse[dict])
async def approve_stocktake(
    session_id: str,
    note: str | None = None,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="manager_hn"),
    x_role: str | None = Header(default="BRANCH_MANAGER")
):
    """Quản lý chi nhánh phê duyệt -> Tự động cân đối tồn kho và giải phóng đóng băng"""
    result = await StocktakeService.approve_stocktake(
        db=db,
        session_id=session_id.strip(),
        approver_id=x_user_id or "manager_hn",
        note=note
    )
    return StandardResponse(success=True, data=result, error=None)


@router.post("/{session_id}/reject", response_model=StandardResponse[dict])
async def reject_stocktake(
    session_id: str,
    body: StocktakeRejectRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="manager_hn"),
    x_role: str | None = Header(default="BRANCH_MANAGER")
):
    """Từ chối kết quả kiểm kê và giải phóng đóng băng"""
    await StocktakeService.reject_stocktake(
        db=db,
        session_id=session_id.strip(),
        approver_id=x_user_id or "manager_hn",
        reason=body.reason
    )
    return StandardResponse(success=True, data={"session_id": session_id, "status": "REJECTED"}, error=None)


@router.post("/{session_id}/reopen", response_model=StandardResponse[dict])
async def reopen_stocktake(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="manager_hn"),
    x_role: str | None = Header(default="BRANCH_MANAGER")
):
    """Yêu cầu đếm lại -> Mở lại phiên về trạng thái COUNTING"""
    await StocktakeService.reopen_stocktake(db=db, session_id=session_id.strip(), user_id=x_user_id or "manager_hn")
    return StandardResponse(success=True, data={"session_id": session_id, "status": "COUNTING"}, error=None)


@router.post("/{session_id}/cancel", response_model=StandardResponse[dict])
async def cancel_stocktake(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="auditor_hn"),
    x_role: str | None = Header(default="AUDITOR")
):
    """Hủy bỏ phiên kiểm kê và giải phóng đóng băng ngay lập tức"""
    await StocktakeService.cancel_stocktake(db=db, session_id=session_id.strip(), user_id=x_user_id or "auditor_hn")
    return StandardResponse(success=True, data={"session_id": session_id, "status": "CANCELLED"}, error=None)


@router.get("/{session_id}/audit-log", response_model=StandardResponse[list[dict]])
async def get_stocktake_audit_log(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Xem nhật ký kiểm toán truy vết từng hành động trên phiên kiểm kê"""
    stmt = (
        select(StocktakeAuditLog)
        .where(StocktakeAuditLog.session_id == session_id.strip())
        .order_by(StocktakeAuditLog.created_at.asc())
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()

    data = [
        {
            "log_id": l.log_id,
            "session_id": l.session_id,
            "action": l.action,
            "performed_by": l.performed_by,
            "note": l.note,
            "created_at": l.created_at
        }
        for l in logs
    ]
    return StandardResponse(success=True, data=data, error=None)
