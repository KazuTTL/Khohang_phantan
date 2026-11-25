# backend/hq_service/routers/catalog.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Product, Branch, GlobalInventorySnapshot, ProductCategory, Account
from shared.event_schemas import (
    ProductCreate,
    ProductUpdate,
    CategoryCreate,
    AccountCreate,
    AccountUpdate,
    AccountStatusUpdate,
)
from shared.rabbitmq_client import get_broker
from shared.auth import hash_password, require_hq_manager

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
async def create_category(payload: CategoryCreate, db: Session = Depends(get_db), user: dict = Depends(require_hq_manager)):
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

VALID_ROLES = {"HQ_MANAGER", "BRANCH_MANAGER", "BRANCH_STAFF"}
VALID_BRANCHES = {"HQ", "HN", "HCM"}


def _serialize_account(acc: Account) -> dict:
    return {
        "account_id": acc.account_id,
        "username": acc.username,
        "full_name": acc.full_name,
        "role": acc.role,
        "branch_code": acc.branch_code,
        "is_active": acc.is_active,
        "password_hashed": str(acc.password_hash).startswith("pbkdf2_sha256$"),
        "created_at": acc.created_at.isoformat() if acc.created_at else None,
    }


async def _publish_account_synced(acc: Account):
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
            "is_active": acc.is_active,
        }
    })


def _ensure_mutable_target(target_username: str, acting_user: dict, action_label: str):
    if target_username == "admin":
        raise HTTPException(
            status_code=400,
            detail=f"Không thể {action_label} tài khoản quản trị gốc 'admin'."
        )
    if acting_user.get("username") == target_username:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể tự {action_label} tài khoản đang đăng nhập ('{target_username}')."
        )


@master_router.get("/accounts")
def list_accounts(db: Session = Depends(get_db)):
    """Xem danh sách tài khoản trong bảng TAI_KHOAN tại Trung tâm (ẩn chuỗi băm)"""
    rows = db.query(Account).all()
    return [_serialize_account(r) for r in rows]


@master_router.post("/accounts", status_code=201)
async def create_account(payload: AccountCreate, db: Session = Depends(get_db), user: dict = Depends(require_hq_manager)):
    """Tạo tài khoản mới tại HQ (băm PBKDF2-SHA256) và đồng bộ về chi nhánh tương ứng"""
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Vai trò '{payload.role}' không hợp lệ.")
    if payload.branch_code not in VALID_BRANCHES:
        raise HTTPException(status_code=400, detail=f"Mã chi nhánh '{payload.branch_code}' không hợp lệ.")

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

    await _publish_account_synced(acc)

    return {
        **_serialize_account(acc),
        "message": f"Đã tạo và phát tín hiệu đồng bộ tài khoản '{acc.username}'."
    }


@master_router.patch("/accounts/{username}/status")
async def update_account_status(
    username: str,
    payload: AccountStatusUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_hq_manager)
):
    """Khóa hoặc mở khóa tài khoản Manager/Staff và đồng bộ trạng thái tới các Chi nhánh"""
    if not payload.is_active:
        _ensure_mutable_target(username, user, "khóa")

    acc = db.query(Account).filter(Account.username == username).first()
    if not acc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tài khoản '{username}'.")

    acc.is_active = payload.is_active
    db.commit()
    db.refresh(acc)

    await _publish_account_synced(acc)

    state_label = "Mở khóa (ACTIVE)" if acc.is_active else "Khóa (LOCKED)"
    return {
        **_serialize_account(acc),
        "message": f"Đã {state_label} tài khoản '{acc.username}' và đồng bộ xuống Chi nhánh."
    }


@master_router.put("/accounts/{username}")
async def update_account(
    username: str,
    payload: AccountUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_hq_manager)
):
    """Cập nhật thông tin, luân chuyển chi nhánh, đổi vai trò hoặc đặt lại mật khẩu tài khoản"""
    acc = db.query(Account).filter(Account.username == username).first()
    if not acc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tài khoản '{username}'.")

    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Vai trò '{payload.role}' không hợp lệ.")
        if username == "admin" and payload.role != "HQ_MANAGER":
            raise HTTPException(status_code=400, detail="Không thể hạ quyền tài khoản quản trị gốc 'admin'.")
        acc.role = payload.role

    if payload.branch_code is not None:
        if payload.branch_code not in VALID_BRANCHES:
            raise HTTPException(status_code=400, detail=f"Mã chi nhánh '{payload.branch_code}' không hợp lệ.")
        if username == "admin" and payload.branch_code != "HQ":
            raise HTTPException(status_code=400, detail="Không thể chuyển chi nhánh của tài khoản quản trị gốc 'admin'.")
        acc.branch_code = payload.branch_code

    if payload.full_name is not None and payload.full_name.strip():
        acc.full_name = payload.full_name.strip()

    if payload.password is not None and payload.password.strip():
        acc.password_hash = hash_password(payload.password)

    if payload.is_active is not None:
        if not payload.is_active:
            _ensure_mutable_target(username, user, "khóa")
        acc.is_active = payload.is_active

    db.commit()
    db.refresh(acc)

    await _publish_account_synced(acc)

    return {
        **_serialize_account(acc),
        "message": f"Đã cập nhật tài khoản '{acc.username}' và đồng bộ sang các Chi nhánh."
    }


@master_router.delete("/accounts/{username}")
async def delete_account(
    username: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_hq_manager)
):
    """Xóa tài khoản Manager/Staff tại HQ và phát tín hiệu xóa đồng bộ tới toàn bộ Chi nhánh"""
    _ensure_mutable_target(username, user, "xóa")

    acc = db.query(Account).filter(Account.username == username).first()
    if not acc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tài khoản '{username}'.")

    deleted_id = acc.account_id
    db.delete(acc)
    db.commit()

    broker = get_broker()
    await broker.publish("evt.catalog.account_deleted", {
        "event_type": "EVT_ACCOUNT_DELETED",
        "data": {
            "account_id": deleted_id,
            "username": username,
        }
    })

    return {
        "username": username,
        "account_id": deleted_id,
        "message": f"Đã xóa tài khoản '{username}' tại HQ và đồng bộ xóa tới HN & HCM."
    }


@master_router.post("/accounts/{username}/resync")
async def resync_account(
    username: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_hq_manager)
):
    """Phát lại sự kiện đồng bộ tài khoản xuống toàn bộ Chi nhánh"""
    acc = db.query(Account).filter(Account.username == username).first()
    if not acc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tài khoản '{username}'.")

    await _publish_account_synced(acc)

    return {
        "username": acc.username,
        "message": f"Đã gửi lại sự kiện đồng bộ EVT_ACCOUNT_SYNCED cho '@{acc.username}' tới HN & HCM."
    }


# ==============================================================================
# 3. DANH MỤC SẢN PHẨM (SAN_PHAM)
# ==============================================================================

@router.get("")
def list_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return products


@router.post("", status_code=201)
async def create_product(payload: ProductCreate, db: Session = Depends(get_db), user: dict = Depends(require_hq_manager)):
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
async def update_product(sku: str, payload: ProductUpdate, db: Session = Depends(get_db), user: dict = Depends(require_hq_manager)):
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
async def delete_product(sku: str, db: Session = Depends(get_db), user: dict = Depends(require_hq_manager)):
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
