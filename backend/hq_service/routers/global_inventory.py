# backend/hq_service/routers/global_inventory.py
import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Branch, Product, GlobalInventorySnapshot

router = APIRouter(tags=["HQ Global Inventory"])

@router.get("/branches")
async def list_branches(db: Session = Depends(get_db)):
    branches = db.query(Branch).all()
    result = []
    
    async with httpx.AsyncClient(timeout=1.0) as client:
        for b in branches:
            is_online = False
            try:
                # Kiểm tra healthcheck của chi nhánh
                health_url = f"{b.api_base_url.replace('/api/v1', '')}/health"
                res = await client.get(health_url)
                if res.status_code == 200:
                    is_online = True
            except Exception:
                is_online = False

            result.append({
                "branch_code": b.branch_code,
                "branch_name": b.branch_name,
                "api_base_url": b.api_base_url,
                "is_active": b.is_active,
                "is_online": is_online
            })
    return result

@router.get("/inventory/global")
def get_global_inventory(db: Session = Depends(get_db)):
    products = db.query(Product).all()
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
            "product_name": p.product_name,
            "unit": p.unit,
            "price": p.price,
            "total_available": total_avail,
            "total_reserved": total_res,
            "branches": b_data
        })
    return response
