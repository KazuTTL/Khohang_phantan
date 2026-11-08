# backend/hq_service/routers/global_inventory.py
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hq_service.database import get_db
from hq_service.dependencies import CurrentUser, get_current_user
from hq_service.models import Branch, GlobalInventorySnapshot, Product
from hq_service.schemas import GlobalStockItem, StandardResponse

router = APIRouter(prefix="/global-inventory", tags=["HQ - Global Inventory Snapshot"])


@router.get("", response_model=StandardResponse[list[GlobalStockItem]])
async def get_global_inventory(
    branch_code: str | None = None,
    sku: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[list[GlobalStockItem]]:
    """
    Truy vấn bảng tổng hợp tồn kho toàn quốc (Read-Model Snapshot).
    Được đồng bộ bất đồng bộ từ các sự kiện Outbox của từng Chi nhánh.
    """
    stmt = (
        select(
            GlobalInventorySnapshot.branch_code,
            Branch.branch_name,
            GlobalInventorySnapshot.sku,
            Product.product_name,
            Product.unit,
            GlobalInventorySnapshot.available_qty,
            GlobalInventorySnapshot.reserved_qty,
            GlobalInventorySnapshot.last_synced_at
        )
        .outerjoin(Branch, GlobalInventorySnapshot.branch_code == Branch.branch_code)
        .outerjoin(Product, GlobalInventorySnapshot.sku == Product.sku)
    )

    if branch_code:
        stmt = stmt.where(GlobalInventorySnapshot.branch_code == branch_code.strip().upper())
    if sku:
        stmt = stmt.where(GlobalInventorySnapshot.sku == sku.strip())

    stmt = stmt.order_by(GlobalInventorySnapshot.branch_code.asc(), GlobalInventorySnapshot.sku.asc())

    res = await db.execute(stmt)
    rows = res.all()

    items = [
        GlobalStockItem(
            branch_code=r[0],
            branch_name=r[1] or r[0],
            sku=r[2],
            product_name=r[3] or r[2],
            unit=r[4] or "Chiếc",
            available_qty=r[5],
            reserved_qty=r[6],
            last_synced_at=r[7]
        )
        for r in rows
    ]
    return StandardResponse(success=True, data=items)
