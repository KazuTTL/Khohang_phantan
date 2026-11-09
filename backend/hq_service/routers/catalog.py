# backend/hq_service/routers/catalog.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Product, Branch, GlobalInventorySnapshot
from shared.event_schemas import ProductCreate
from shared.rabbitmq_client import get_broker

router = APIRouter(prefix="/products", tags=["HQ Catalog"])

@router.get("")
def list_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return products

@router.post("", status_code=201)
async def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    """Tạo sản phẩm mới và tự động phát tán đồng bộ tới toàn bộ chi nhánh (Distributed Catalog Replication)"""
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

    # Khởi tạo snapshot cho tất cả chi nhánh
    branches = db.query(Branch).all()
    for b in branches:
        snap = GlobalInventorySnapshot(
            branch_code=b.branch_code,
            sku=payload.sku,
            available_qty=0,
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
            "price": new_prod.price
        }
    })

    return new_prod

@router.put("/{sku}")
async def update_product(sku: str, payload: ProductCreate, db: Session = Depends(get_db)):
    """Cập nhật thông tin sản phẩm Master Data"""
    prod = db.query(Product).filter(Product.sku == sku).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")

    prod.product_name = payload.product_name
    prod.unit = payload.unit
    prod.price = payload.price
    db.commit()
    db.refresh(prod)
    return prod
