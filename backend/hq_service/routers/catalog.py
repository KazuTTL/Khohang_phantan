# backend/hq_service/routers/catalog.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Product, Branch, GlobalInventorySnapshot, ProductCategory, Account
from shared.event_schemas import ProductCreate, ProductUpdate, CategoryCreate, AccountCreate
from shared.rabbitmq_client import get_broker
from shared.auth import hash_password

router = APIRouter(prefix="/products", tags=["HQ Catalog"])
master_router = APIRouter(tags=["HQ Master Data (Categories & Accounts)"])


# ==============================================================================
# 1. DANH MỤC NGÀNH HÀNG (DANH_MUC_SP)
# ==============================================================================

@master_router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """Lấy danh sách danh mục ngành hàng (DANH_MUC_SP)"""
    return db.query(ProductCategory).all()


@master_router.post("/categories", status_code=201)
async def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    """Tạo danh mục sản phẩm mới tại HQ và nhân bản về các chi nhánh qua RabbitMQ"""
    existing = db.query(ProductCategory).filter(ProductCategory.category_name == payload.category_name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Danh mục '{payload.category_name}' đã tồn tại.")

    cat = ProductCategory(category_name=payload.category_name, description=payload.description)
    db.add(cat)
    db.commit()
    db.refresh(cat)

    broker = get_broker()
    await broker.publish("evt.catalog.category_created", {
        "event_type": "EVT_CATEGORY_CREATED",
        "data": {
            "category_id": cat.category_id,
            "category_name": cat.category_name,
            "description": cat.description
        }
    })
    return cat


# ==============================================================================
# 2. TÀI KHOẢN PHÂN QUYỀN (TAI_KHOAN)
# ==============================================================================

@master_router.get("/accounts")
def list_accounts(db: Session = Depends(get_db)):
    """Xem danh sách tài khoản trong bảng TAI_KHOAN tại Trung tâm (ẩn chuỗi băm)"""
    rows = db.query(Account).all()
    return [
        {
            "account_id": r.account_id,
            "username": r.username,
            "full_name": r.full_name,
            "role": r.role,
            "branch_code": r.branch_code,
            "is_active": r.is_active,
            "password_hashed": str(r.password_hash).startswith("pbkdf2_sha256$"),
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in rows
    ]


@master_router.post("/accounts", status_code=201)
async def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    """Tạo tài khoản mới tại HQ (băm PBKDF2-SHA256) và đồng bộ về chi nhánh tương ứng"""
    existing = db.query(Account).filter(Account.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Tài khoản '{payload.username}' đã tồn tại.")

    pw_hash = hash_password(payload.password)
    acc = Account(
        account_id=str(uuid.uuid4()),
        username=payload.username,
        password_hash=pw_hash,
        full_name=payload.full_name,
        role=payload.role,
        branch_code=payload.branch_code,
        is_active=payload.is_active
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)

    broker = get_broker()
    await broker.publish("evt.catalog.account_synced", {
        "event_type": "EVT_ACCOUNT_SYNCED",
        "data": {
            "account_id": acc.account_id,
            "username": acc.username,
            "password_hash": acc.password_hash,
            "full_name": acc.full_name,
            "role": acc.role,
            "branch_code": acc.branch_code,
            "is_active": acc.is_active
        }
    })

    return {
        "account_id": acc.account_id,
        "username": acc.username,
        "full_name": acc.full_name,
        "role": acc.role,
        "branch_code": acc.branch_code,
        "is_active": acc.is_active,
        "message": f"Đã tạo và phát tín hiệu đồng bộ tài khoản '{acc.username}'."
    }


# ==============================================================================
# 3. DANH MỤC SẢN PHẨM (SAN_PHAM)
# ==============================================================================

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

    barcode_val = payload.barcode or f"BC-{payload.sku}"
    cost_val = payload.cost_price if payload.cost_price is not None else round(float(payload.price) * 0.8, 2)
    cat_id = payload.category_id or 1

    new_prod = Product(
        sku=payload.sku,
        barcode=barcode_val,
        product_name=payload.product_name,
        category_id=cat_id,
        unit=payload.unit,
        cost_price=cost_val,
        price=payload.price
    )
    db.add(new_prod)

    # Chỉ khởi tạo snapshot tồn kho cho các site là CHI_NHANH
    branches = db.query(Branch).filter(Branch.site_type == "CHI_NHANH").all()
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
            "barcode": new_prod.barcode,
            "product_name": new_prod.product_name,
            "category_id": new_prod.category_id,
            "unit": new_prod.unit,
            "cost_price": new_prod.cost_price,
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
    if payload.barcode is not None:
        prod.barcode = payload.barcode
    if payload.category_id is not None:
        prod.category_id = payload.category_id
    if payload.cost_price is not None:
        prod.cost_price = payload.cost_price

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
            "barcode": prod.barcode,
            "product_name": prod.product_name,
            "category_id": prod.category_id,
            "unit": prod.unit,
            "cost_price": prod.cost_price,
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
