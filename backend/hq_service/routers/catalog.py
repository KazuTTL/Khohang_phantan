# backend/hq_service/routers/catalog.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Product, Branch, GlobalInventorySnapshot
from shared.event_schemas import ProductCreate, ProductUpdate
from shared.rabbitmq_client import get_broker

router = APIRouter(prefix="/products", tags=["HQ Catalog"])

@router.get("")
def list_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return products

@router.post("", status_code=201)
async def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    """Tạo sản phẩm mới và tự động phát tán đồng bộ tới toàn bộ chi nhánh kèm số lượng tồn đầu kỳ"""
    existing = db.query(Product).filter(Product.sku == payload.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Sản phẩm có mã SKU '{payload.sku}' đã tồn tại.")

    new_prod = Product(
        sku=payload.sku,
        product_name=payload.product_name,
        unit=payload.unit,
        price=payload.price
    )
    db.add(new_prod)

    # Khởi tạo snapshot cho tất cả chi nhánh theo số lượng chỉ định
    branches = db.query(Branch).all()
    initial_stock_map = payload.initial_stock or {}
    for b in branches:
        init_qty = int(initial_stock_map.get(b.branch_code, 0))
        snap = GlobalInventorySnapshot(
            branch_code=b.branch_code,
            sku=payload.sku,
            available_qty=init_qty,
            reserved_qty=0
        )
        db.add(snap)

    db.commit()
    db.refresh(new_prod)

    # Phát sự kiện đồng bộ sản phẩm tới tất cả các chi nhánh
    broker = get_broker()
    await broker.publish("evt.catalog.product_created", {
        "event_type": "EVT_PRODUCT_CREATED",
        "data": {
            "sku": new_prod.sku,
            "product_name": new_prod.product_name,
            "unit": new_prod.unit,
            "price": new_prod.price,
            "initial_stock": initial_stock_map,
            "min_threshold": payload.min_threshold,
            "max_threshold": payload.max_threshold
        }
    })

    return new_prod

@router.put("/{sku}")
async def update_product(sku: str, payload: ProductUpdate, db: Session = Depends(get_db)):
    """Cập nhật thông tin sản phẩm Master Data và phát tán đồng bộ chi nhánh"""
    prod = db.query(Product).filter(Product.sku == sku).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")

    prod.product_name = payload.product_name
    prod.unit = payload.unit
    prod.price = payload.price

    # Cập nhật snapshot tồn kho chi nhánh nếu có payload.branch_stock
    if payload.branch_stock and isinstance(payload.branch_stock, dict):
        for b_code, new_qty in payload.branch_stock.items():
            valid_qty = max(0, int(new_qty))
            snap = db.query(GlobalInventorySnapshot).filter(
                GlobalInventorySnapshot.sku == sku,
                GlobalInventorySnapshot.branch_code == b_code
            ).first()
            if snap:
                snap.available_qty = valid_qty
            else:
                snap = GlobalInventorySnapshot(
                    branch_code=b_code,
                    sku=sku,
                    available_qty=valid_qty,
                    reserved_qty=0
                )
                db.add(snap)

    db.commit()
    db.refresh(prod)

    # Phát sự kiện đồng bộ cập nhật sản phẩm
    broker = get_broker()
    await broker.publish("evt.catalog.product_updated", {
        "event_type": "EVT_PRODUCT_UPDATED",
        "data": {
            "sku": prod.sku,
            "product_name": prod.product_name,
            "unit": prod.unit,
            "price": prod.price,
            "min_threshold": payload.min_threshold,
            "max_threshold": payload.max_threshold,
            "branch_stock": payload.branch_stock
        }
    })

    return prod

@router.delete("/{sku}")
async def delete_product(sku: str, db: Session = Depends(get_db)):
    """Xóa sản phẩm Master Data (chỉ được xóa khi tồn kho toàn hệ thống bằng 0)"""
    prod = db.query(Product).filter(Product.sku == sku).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")

    snapshots = db.query(GlobalInventorySnapshot).filter(GlobalInventorySnapshot.sku == sku).all()
    total_stock = sum((s.available_qty + s.reserved_qty) for s in snapshots)
    if total_stock > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể xóa mặt hàng '{sku}' vì vẫn còn tồn kho ({total_stock} đơn vị). Hãy xuất hết hàng hoặc kiểm kê về 0 trước khi xóa."
        )

    for s in snapshots:
        db.delete(s)
    db.delete(prod)
    db.commit()

    # Phát sự kiện đồng bộ xóa tới các chi nhánh
    broker = get_broker()
    await broker.publish("evt.catalog.product_deleted", {
        "event_type": "EVT_PRODUCT_DELETED",
        "data": {
            "sku": sku
        }
    })

    return {"message": f"Đã xóa sản phẩm '{sku}' thành công."}
