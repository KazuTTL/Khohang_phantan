# backend/branch_service/routers/purchase_receipts.py
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from branch_service.database import get_db
from branch_service.models import PurchaseReceipt, PurchaseReceiptItem
from branch_service.schemas import (
    PurchaseReceiptCreate,
    PurchaseReceiptItemResponse,
    PurchaseReceiptResponse,
    ReceiveReceiptRequest,
    RejectReceiptRequest,
    StandardResponse,
)
from branch_service.services.purchase_service import PurchaseService

router = APIRouter(prefix="/purchase-receipts", tags=["Branch - Purchase Receipts (Nhập hàng NCC)"])


def _map_receipt_to_response(r: PurchaseReceipt) -> PurchaseReceiptResponse:
    items_resp = [
        PurchaseReceiptItemResponse(
            item_id=it.item_id,
            receipt_id=it.receipt_id,
            sku=it.sku,
            expected_qty=it.expected_qty,
            received_qty=it.received_qty,
            unit_price=float(it.unit_price) if it.unit_price is not None else None,
            status=it.status
        )
        for it in (r.items or [])
    ]
    return PurchaseReceiptResponse(
        receipt_id=r.receipt_id,
        receipt_code=r.receipt_code,
        branch_code=r.branch_code,
        supplier_id=r.supplier_id,
        status=r.status,
        created_by=r.created_by,
        approved_by=r.approved_by,
        received_by=r.received_by,
        invoice_number=r.invoice_number,
        total_amount=float(r.total_amount) if r.total_amount is not None else None,
        note=r.note,
        created_at=r.created_at,
        submitted_at=r.submitted_at,
        approved_at=r.approved_at,
        rejected_at=r.rejected_at,
        received_at=r.received_at,
        reject_reason=r.reject_reason,
        items=items_resp
    )


@router.get("", response_model=StandardResponse[list[PurchaseReceiptResponse]])
async def list_purchase_receipts(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Danh sách các phiếu nhập hàng NCC tại chi nhánh"""
    stmt = (
        select(PurchaseReceipt)
        .options(selectinload(PurchaseReceipt.items))
        .order_by(PurchaseReceipt.created_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(PurchaseReceipt.status == status.strip().upper())

    res = await db.execute(stmt)
    receipts = res.scalars().all()

    data = [_map_receipt_to_response(r) for r in receipts]
    return StandardResponse(success=True, data=data, error=None)


@router.get("/{receipt_id}", response_model=StandardResponse[PurchaseReceiptResponse])
async def get_purchase_receipt(
    receipt_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Xem chi tiết một phiếu nhập hàng NCC"""
    stmt = (
        select(PurchaseReceipt)
        .options(selectinload(PurchaseReceipt.items))
        .where(PurchaseReceipt.receipt_id == receipt_id.strip())
    )
    res = await db.execute(stmt)
    receipt = res.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy phiếu nhập {receipt_id}.")

    return StandardResponse(success=True, data=_map_receipt_to_response(receipt), error=None)


@router.post("", response_model=StandardResponse[dict])
async def create_purchase_receipt(
    body: PurchaseReceiptCreate,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="stock_hn"),
    x_role: str | None = Header(default="STOCK_KEEPER")
):
    """Tạo phiếu nhập hàng NCC mới ở trạng thái DRAFT"""
    items_data = [item.model_dump() for item in body.items]
    result = await PurchaseService.create_receipt(
        db=db,
        supplier_id=body.supplier_id,
        invoice_number=body.invoice_number,
        items=items_data,
        user_id=x_user_id or "anonymous",
        note=body.note
    )
    return StandardResponse(success=True, data=result, error=None)


@router.post("/{receipt_id}/submit", response_model=StandardResponse[dict])
async def submit_purchase_receipt(
    receipt_id: str,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="stock_hn"),
    x_role: str | None = Header(default="STOCK_KEEPER")
):
    """Nộp phiếu nhập NCC để chờ Quản lý phê duyệt (DRAFT -> PENDING_APPROVAL)"""
    await PurchaseService.submit_receipt(
        db=db,
        receipt_id=receipt_id.strip(),
        user_id=x_user_id or "anonymous"
    )
    return StandardResponse(
        success=True,
        data={"receipt_id": receipt_id, "status": "PENDING_APPROVAL", "message": "Đã gửi phiếu nhập để chờ duyệt."},
        error=None
    )


@router.post("/{receipt_id}/approve", response_model=StandardResponse[dict])
async def approve_purchase_receipt(
    receipt_id: str,
    note: str | None = None,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="manager_hn"),
    x_role: str | None = Header(default="BRANCH_MANAGER")
):
    """
    Quản lý chi nhánh phê duyệt phiếu nhập NCC (PENDING_APPROVAL -> APPROVED).
    Tuân thủ Segregation of Duties: Người duyệt không được là người tạo.
    """
    await PurchaseService.approve_receipt(
        db=db,
        receipt_id=receipt_id.strip(),
        approver_id=x_user_id or "manager_hn",
        note=note
    )
    return StandardResponse(
        success=True,
        data={"receipt_id": receipt_id, "status": "APPROVED", "message": "Phiếu nhập đã được phê duyệt."},
        error=None
    )


@router.post("/{receipt_id}/reject", response_model=StandardResponse[dict])
async def reject_purchase_receipt(
    receipt_id: str,
    body: RejectReceiptRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="manager_hn"),
    x_role: str | None = Header(default="BRANCH_MANAGER")
):
    """Quản lý chi nhánh từ chối duyệt phiếu nhập (PENDING_APPROVAL -> REJECTED)"""
    await PurchaseService.reject_receipt(
        db=db,
        receipt_id=receipt_id.strip(),
        reason=body.reason,
        approver_id=x_user_id or "manager_hn"
    )
    return StandardResponse(
        success=True,
        data={"receipt_id": receipt_id, "status": "REJECTED", "message": "Đã từ chối phiếu nhập."},
        error=None
    )


@router.post("/{receipt_id}/receive", response_model=StandardResponse[dict])
async def receive_purchase_receipt(
    receipt_id: str,
    body: ReceiveReceiptRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="stock_hn"),
    x_role: str | None = Header(default="STOCK_KEEPER")
):
    """
    Thủ kho thực tế nhận hàng và nhập vào kho:
    - Khóa dòng Local_Inventory WITH (UPDLOCK, ROWLOCK)
    - Tăng available_qty
    - Ghi Stock_Ledger (PURCHASE_RECEIVE)
    - Ghi Outbox 'evt.inventory.updated'
    - Cập nhật trạng thái phiếu: RECEIVED
    """
    items_received = [it.model_dump() for it in body.items]
    res = await PurchaseService.receive_receipt(
        db=db,
        receipt_id=receipt_id.strip(),
        items_received=items_received,
        receiver_id=x_user_id or "stock_hn"
    )
    return StandardResponse(
        success=True,
        data={"receipt_id": receipt_id, "status": "RECEIVED", "items_processed": res},
        error=None
    )


@router.post("/{receipt_id}/cancel", response_model=StandardResponse[dict])
async def cancel_purchase_receipt(
    receipt_id: str,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="stock_hn"),
    x_role: str | None = Header(default="STOCK_KEEPER")
):
    """Hủy phiếu nhập (chỉ khi đang ở trạng thái DRAFT hoặc REJECTED)"""
    await PurchaseService.cancel_receipt(
        db=db,
        receipt_id=receipt_id.strip(),
        user_id=x_user_id or "stock_hn",
        reason=reason
    )
    return StandardResponse(
        success=True,
        data={"receipt_id": receipt_id, "status": "CANCELLED", "message": "Đã hủy phiếu nhập."},
        error=None
    )
