# backend/hq_service/routers/global_inventory.py
import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Branch, Product, ProductCategory, Account, GlobalInventorySnapshot, TransferOrder

router = APIRouter(tags=["HQ Global Inventory"])


@router.get("/branches")
async def list_branches(db: Session = Depends(get_db)):
    branches = db.query(Branch).all()
    result = []

    async with httpx.AsyncClient(timeout=1.0) as client:
        for b in branches:
            is_online = False
            if b.site_type == "TRUNG_TAM":
                is_online = True
            else:
                try:
                    health_url = f"{b.api_base_url.replace('/api/v1', '')}/health"
                    res = await client.get(health_url)
                    if res.status_code == 200:
                        is_online = True
                except Exception:
                    is_online = False

            result.append({
                "branch_code": b.branch_code,
                "branch_name": b.branch_name,
                "address": b.address,
                "site_type": b.site_type,
                "status": b.status,
                "api_base_url": b.api_base_url,
                "is_active": b.is_active,
                "is_online": is_online
            })
    return result


@router.get("/inventory/global")
def get_global_inventory(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    categories = {c.category_id: c.category_name for c in db.query(ProductCategory).all()}
    snapshots = db.query(GlobalInventorySnapshot).all()

    # Nhóm snapshot theo SKU
    snap_map = {}
    for s in snapshots:
        if s.sku not in snap_map:
            snap_map[s.sku] = {}
        snap_map[s.sku][s.branch_code] = {
            "available": s.available_qty,
            "reserved": s.reserved_qty
        }

    response = []
    for p in products:
        b_data = snap_map.get(p.sku, {})
        total_avail = sum(item["available"] for item in b_data.values())
        total_res = sum(item["reserved"] for item in b_data.values())

        response.append({
            "sku": p.sku,
            "barcode": p.barcode,
            "product_name": p.product_name,
            "category_id": p.category_id,
            "category_name": categories.get(p.category_id, "Chưa phân loại"),
            "unit": p.unit,
            "cost_price": p.cost_price,
            "price": p.price,
            "total_available": total_avail,
            "total_reserved": total_res,
            "branches": b_data
        })
    return response


@router.get("/schema-overview")
def get_hq_schema_overview(db: Session = Depends(get_db)):
    """Thống kê các bảng dữ liệu tại Node Trung tâm Site 1 theo Thiết kế 11 bảng"""
    return {
        "site": "Site 1 - Trung tâm (HQ)",
        "tables": {
            "CHI_NHANH (Branches)": db.query(Branch).count(),
            "DANH_MUC_SP (Product_Categories)": db.query(ProductCategory).count(),
            "SAN_PHAM (Products)": db.query(Product).count(),
            "TAI_KHOAN (Accounts)": db.query(Account).count(),
            "TONG_HOP_TON_KHO (Global_Inventory_Snapshot)": db.query(GlobalInventorySnapshot).count(),
            "Transfer_Orders (Saga)": db.query(TransferOrder).count()
        }
    }
