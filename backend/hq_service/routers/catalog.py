# backend/hq_service/routers/catalog.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Product
from shared.event_schemas import ProductCreate

router = APIRouter(prefix="/products", tags=["HQ Catalog"])

@router.get("")
def list_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return products

@router.post("", status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
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
    db.commit()
    db.refresh(new_prod)
    return new_prod
