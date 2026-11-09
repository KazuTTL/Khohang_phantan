# backend/branch_service/routers/local_inventory.py
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.database import get_db
from branch_service.models import LocalInventory, LocalProduct, StockLedger
from branch_service.schemas import AdjustStockRequest, AdjustStockResponse, LocalInventoryItem, StandardResponse, StockLedgerItem
from branch_service.services.stock_service import StockService

router = APIRouter(prefix="/inventory", tags=["Branch - Local Inventory (Local Autonomy)"])


@router.get("", response_model=StandardResponse[list[LocalInventoryItem]])
async def list_local_inventory(
    search: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Tra cứu tồn kho cục bộ tại chi nhánh (Local Autonomy)"""
    stmt = (
        select(
            LocalInventory.sku,
            LocalProduct.product_name,
            LocalProduct.unit,
            LocalInventory.available_qty,
            LocalInventory.reserved_qty,
            LocalInventory.version,
            LocalInventory.updated_at
        )
        .outerjoin(LocalProduct, LocalInventory.sku == LocalProduct.sku)
        .order_by(LocalInventory.sku.asc())
    )
    if search:
        s = f"%{search.strip()}%"
        stmt = stmt.where(LocalInventory.sku.ilike(s) | LocalProduct.product_name.ilike(s))

    res = await db.execute(stmt)
    rows = res.all()

    items = [
        LocalInventoryItem(
            sku=r[0],
            product_name=r[1] or r[0],
            unit=r[2] or "Chiếc",
            available_qty=r[3],
            reserved_qty=r[4],
            version=r[5],
            updated_at=r[6]
        )
        for r in rows
    ]
    return StandardResponse(success=True, data=items, error=None)


@router.get("/ledger/history", response_model=StandardResponse[list[StockLedgerItem]])
async def get_stock_ledger(
    sku: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Tra cứu nhật ký biến động kho cục bộ (Append-only Ledger)"""
    stmt = select(StockLedger).order_by(StockLedger.ledger_id.desc()).limit(limit)
    if sku:
        stmt = stmt.where(StockLedger.sku == sku.strip())

    res = await db.execute(stmt)
    ledgers = res.scalars().all()

    data = [
        StockLedgerItem(
            ledger_id=l.ledger_id,
            reference_id=l.reference_id,
            sku=l.sku,
            change_type=l.change_type,
            quantity=l.quantity,
            created_at=l.created_at
        )
        for l in ledgers
    ]
    return StandardResponse(success=True, data=data, error=None)


@router.get("/{sku}", response_model=StandardResponse[LocalInventoryItem])
async def get_sku_inventory(
    sku: str,
    db: AsyncSession = Depends(get_db)
):
    """Xem chi tiết tồn kho và trạng thái của một SKU cụ thể tại chi nhánh"""
    stmt = (
        select(
            LocalInventory.sku,
            LocalProduct.product_name,
            LocalProduct.unit,
            LocalInventory.available_qty,
            LocalInventory.reserved_qty,
            LocalInventory.version,
            LocalInventory.updated_at
        )
        .outerjoin(LocalProduct, LocalInventory.sku == LocalProduct.sku)
        .where(LocalInventory.sku == sku.strip())
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy SKU {sku} tại chi nhánh này.")

    data = LocalInventoryItem(
        sku=row[0],
        product_name=row[1] or row[0],
        unit=row[2] or "Chiếc",
        available_qty=row[3],
        reserved_qty=row[4],
        version=row[5],
        updated_at=row[6]
    )
    return StandardResponse(success=True, data=data, error=None)


@router.post("/adjust", response_model=StandardResponse[AdjustStockResponse])
async def adjust_local_stock(
    body: AdjustStockRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="anonymous_staff"),
    x_role: str | None = Header(default="STOCK_KEEPER")
):
    """
    Thực hiện biến động tồn kho tại chỗ (LOCAL_IN hoặc LOCAL_OUT).
    Minh chứng tính năng TỰ TRỊ CỤC BỘ (Local Autonomy):
    Thao tác thành công ngay cả khi mất kết nối mạng với HQ.
    """
    result = await StockService.adjust_local_stock(
        db=db,
        sku=body.sku.strip(),
        change_type=body.change_type.strip(),
        quantity=body.quantity,
        reason=body.reason,
        user_id=x_user_id or "anonymous"
    )
    return StandardResponse(
        success=True,
        data=AdjustStockResponse(
            new_available=result["new_available"],
            ledger_id=result["ledger_id"],
            message_id=result["message_id"]
        ),
        error=None
    )
