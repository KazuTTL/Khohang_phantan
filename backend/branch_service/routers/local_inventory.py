# backend/branch_service/routers/local_inventory.py
from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.config import branch_settings
from branch_service.database import get_db
from branch_service.models import LocalInventory, LocalProduct, StockLedger
from branch_service.schemas import (
    AdjustStockRequest, AdjustStockResponse, LocalInventoryItem, StandardResponse
)
from branch_service.services.stock_service import StockService

router = APIRouter(prefix="/inventory", tags=["Branch - Local Inventory (Local Autonomy)"])


@router.get("", response_model=StandardResponse[list[LocalInventoryItem]])
async def get_local_inventory(
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(None)
) -> StandardResponse[list[LocalInventoryItem]]:
    """Tra cứu tồn kho cục bộ tại chi nhánh (Local Autonomy)"""
    stmt = (
        select(
            LocalInventory.sku,
            LocalProduct.product_name,
            LocalProduct.unit,
            LocalInventory.available_qty,
            LocalInventory.reserved_qty,
            LocalInventory.updated_at
        )
        .outerjoin(LocalProduct, LocalInventory.sku == LocalProduct.sku)
        .order_by(LocalInventory.sku.asc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    items = [
        LocalInventoryItem(
            sku=r[0],
            product_name=r[1] or r[0],
            unit=r[2] or "Chiếc",
            available_qty=r[3],
            reserved_qty=r[4],
            updated_at=r[5]
        )
        for r in rows
    ]
    return StandardResponse(success=True, data=items)


@router.post("/adjust", response_model=StandardResponse[AdjustStockResponse])
async def adjust_local_stock(
    req: AdjustStockRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(None)
) -> StandardResponse[AdjustStockResponse]:
    """
    Thực hiện biến động tồn kho tại chỗ (LOCAL_IN hoặc LOCAL_OUT).
    Minh chứng tính năng TỰ TRỊ CỤC BỘ (Local Autonomy):
    Hoạt động bình thường kể cả khi ngắt kết nối với HQ và RabbitMQ.
    """
    change_type = req.change_type.strip().upper()
    if change_type not in ["LOCAL_IN", "LOCAL_OUT"]:
        return StandardResponse(success=False, error="change_type chỉ chấp nhận LOCAL_IN hoặc LOCAL_OUT.")

    try:
        ok, reason, data = await StockService.adjust_stock(
            session=db,
            sku=req.sku.strip(),
            change_type=change_type,
            quantity=req.quantity,
            idempotency_key=req.idempotency_key,
            note=req.note
        )

        if not ok:
            return StandardResponse(success=False, error=reason)

        await db.commit()

        return StandardResponse(
            success=True,
            data=AdjustStockResponse(
                sku=req.sku.strip(),
                change_type=change_type,
                quantity=req.quantity,
                available_qty=data["available_qty"],
                reserved_qty=data["reserved_qty"],
                reference_id=data["reference_id"]
            )
        )
    except Exception as e:
        await db.rollback()
        return StandardResponse(success=False, error=f"Lỗi biến động kho: {str(e)}")


@router.get("/ledger", response_model=StandardResponse[list[dict]])
async def get_stock_ledger(
    sku: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
) -> StandardResponse[list[dict]]:
    """Tra cứu nhật ký biến động kho cục bộ (Stock Ledger)"""
    stmt = select(StockLedger).order_by(StockLedger.ledger_id.desc()).limit(limit)
    if sku:
        stmt = stmt.where(StockLedger.sku == sku.strip())

    res = await db.execute(stmt)
    ledgers = res.scalars().all()

    data = [
        {
            "ledger_id": l.ledger_id,
            "transaction_type": l.transaction_type,
            "sku": l.sku,
            "quantity": l.quantity,
            "available_after": l.available_after,
            "reserved_after": l.reserved_after,
            "reference_id": l.reference_id,
            "idempotency_key": l.idempotency_key,
            "note": l.note,
            "created_at": l.created_at
        }
        for l in ledgers
    ]
    return StandardResponse(success=True, data=data)
