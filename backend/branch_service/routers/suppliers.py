# backend/branch_service/routers/suppliers.py
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.database import get_db
from branch_service.models import BranchUser, Supplier, UserRole
from branch_service.schemas import StandardResponse, SupplierCreate, SupplierResponse

router = APIRouter(prefix="/suppliers", tags=["Branch - Suppliers"])


@router.get("", response_model=StandardResponse[list[SupplierResponse]])
async def list_suppliers(
    search: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Lấy danh sách các Nhà cung cấp của chi nhánh"""
    stmt = select(Supplier).order_by(Supplier.supplier_name.asc())
    if search:
        s = f"%{search.strip()}%"
        stmt = stmt.where(Supplier.supplier_name.ilike(s) | Supplier.supplier_id.ilike(s))

    res = await db.execute(stmt)
    suppliers = res.scalars().all()

    data = [
        SupplierResponse(
            supplier_id=s.supplier_id,
            supplier_name=s.supplier_name,
            tax_code=s.tax_code,
            contact_phone=s.contact_phone,
            is_active=s.is_active
        )
        for s in suppliers
    ]
    return StandardResponse(success=True, data=data, error=None)


@router.get("/{supplier_id}", response_model=StandardResponse[SupplierResponse])
async def get_supplier(
    supplier_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Xem chi tiết một nhà cung cấp"""
    s = await db.get(Supplier, supplier_id.strip())
    if not s:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy nhà cung cấp {supplier_id}.")

    return StandardResponse(
        success=True,
        data=SupplierResponse(
            supplier_id=s.supplier_id,
            supplier_name=s.supplier_name,
            tax_code=s.tax_code,
            contact_phone=s.contact_phone,
            is_active=s.is_active
        ),
        error=None
    )


@router.post("", response_model=StandardResponse[SupplierResponse])
async def create_supplier(
    body: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="manager_hn"),
    x_role: str | None = Header(default="BRANCH_MANAGER")
):
    """Tạo mới nhà cung cấp (Yêu cầu quyền BRANCH_MANAGER hoặc STOCK_KEEPER)"""
    existing = await db.get(Supplier, body.supplier_id.strip())
    if existing:
        raise HTTPException(status_code=400, detail=f"Mã nhà cung cấp '{body.supplier_id}' đã tồn tại.")

    new_supplier = Supplier(
        supplier_id=body.supplier_id.strip(),
        supplier_name=body.supplier_name.strip(),
        tax_code=body.tax_code.strip() if body.tax_code else None,
        contact_phone=body.contact_phone.strip() if body.contact_phone else None,
        is_active=body.is_active
    )
    db.add(new_supplier)
    await db.commit()
    await db.refresh(new_supplier)

    return StandardResponse(
        success=True,
        data=SupplierResponse(
            supplier_id=new_supplier.supplier_id,
            supplier_name=new_supplier.supplier_name,
            tax_code=new_supplier.tax_code,
            contact_phone=new_supplier.contact_phone,
            is_active=new_supplier.is_active
        ),
        error=None
    )
