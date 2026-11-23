# backend/hq_service/main.py
import uuid
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal, DATABASE_URL, get_db
from .models import Branch, ProductCategory, Product, Account, GlobalInventorySnapshot
from .routers import catalog, global_inventory, transfers_saga
from .consumers.hq_event_consumer import start_hq_consumer
from .services.saga_timeout_worker import run_saga_timeout_worker
from shared.rabbitmq_client import get_broker
from shared.auth import USERS_DB, hash_password
from shared.auth_router import create_auth_router
from shared.cluster_infra import (
    SiteLoadBalancer,
    LocalDBReplicator,
    resolve_sqlite_paths,
    register_lb_middleware,
)

site_lb = SiteLoadBalancer(
    site_name="Site 1: Trụ sở chính - Báo cáo tổng hợp",
    lb_name="LB-HQ-Central",
    instances=["Central-API-1", "Central-API-2"]
)
primary_db_path, replica_db_path = resolve_sqlite_paths(DATABASE_URL, "./db_hq.db")
db_replicator = LocalDBReplicator(primary_db_path, replica_db_path)


def seed_initial_data():
    """Khởi tạo 11 bảng (phần Site 1 Trung tâm) và nạp dữ liệu mẫu ban đầu nếu chưa có"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. CHI_NHANH
        if not db.query(Branch).first():
            branches = [
                Branch(
                    branch_code="HQ",
                    branch_name="Trụ sở chính (Trung tâm)",
                    address="Số 1 Đại Cồ Việt, Hai Bà Trưng, Hà Nội",
                    site_type="TRUNG_TAM",
                    status="ACTIVE",
                    api_base_url="http://hq_service:8000/api/v1",
                    is_active=True
                ),
                Branch(
                    branch_code="HN",
                    branch_name="Chi nhánh Hà Nội",
                    address="KCN Bắc Thăng Long, Đông Anh, Hà Nội",
                    site_type="CHI_NHANH",
                    status="ACTIVE",
                    api_base_url="http://branch_hn:8001/api/v1",
                    is_active=True
                ),
                Branch(
                    branch_code="HCM",
                    branch_name="Chi nhánh TP.HCM",
                    address="KCN Tân Bình, Tân Phú, TP. Hồ Chí Minh",
                    site_type="CHI_NHANH",
                    status="ACTIVE",
                    api_base_url="http://branch_hcm:8002/api/v1",
                    is_active=True
                )
            ]
            db.add_all(branches)

        # 2. DANH_MUC_SP
        if not db.query(ProductCategory).first():
            categories = [
                ProductCategory(category_id=1, category_name="Điện tử - Laptop", description="Máy tính xách tay, thiết bị công nghệ"),
                ProductCategory(category_id=2, category_name="Thiết bị ngoại vi", description="Chuột, bàn phím, màn hình"),
                ProductCategory(category_id=3, category_name="Phụ kiện & Lưu trữ", description="Ổ cứng, hub chuyển đổi, cáp kết nối"),
                ProductCategory(category_id=4, category_name="Thiết bị đo kiểm", description="Thiết bị đo lường kỹ thuật chuyên dụng")
            ]
            db.add_all(categories)

        # 3. SAN_PHAM
        if not db.query(Product).first():
            products = [
                Product(
                    sku="LAPTOP-DELL-01",
                    barcode="8938505970011",
                    product_name="Laptop Dell XPS 15",
                    category_id=1,
                    unit="Chiếc",
                    cost_price=29500000.0,
                    price=35000000.0
                ),
                Product(
                    sku="MACBOOK-AIR-M2",
                    barcode="8938505970028",
                    product_name="Apple MacBook Air M2",
                    category_id=1,
                    unit="Chiếc",
                    cost_price=24000000.0,
                    price=28000000.0
                ),
                Product(
                    sku="CHUOT-LOGI-MX3",
                    barcode="8938505970035",
                    product_name="Chuột Logitech MX Master 3S",
                    category_id=2,
                    unit="Con",
                    cost_price=1750000.0,
                    price=2200000.0
                )
            ]
            db.add_all(products)

        # 4. TAI_KHOAN (băm mật khẩu PBKDF2-SHA256)
        if not db.query(Account).first():
            for u in USERS_DB.values():
                acc = Account(
                    account_id=str(uuid.uuid4()),
                    username=u["username"],
                    password_hash=hash_password(u["password"]),
                    full_name=u["full_name"],
                    role=u["role"],
                    branch_code=u["branch"],
                    is_active=True
                )
                db.add(acc)

        # 11. TONG_HOP_TON_KHO
        if not db.query(GlobalInventorySnapshot).first():
            snapshots = [
                GlobalInventorySnapshot(branch_code="HN", sku="LAPTOP-DELL-01", available_qty=100, reserved_qty=0),
                GlobalInventorySnapshot(branch_code="HCM", sku="LAPTOP-DELL-01", available_qty=50, reserved_qty=0),
                GlobalInventorySnapshot(branch_code="HN", sku="MACBOOK-AIR-M2", available_qty=40, reserved_qty=0),
                GlobalInventorySnapshot(branch_code="HCM", sku="MACBOOK-AIR-M2", available_qty=30, reserved_qty=0),
                GlobalInventorySnapshot(branch_code="HN", sku="CHUOT-LOGI-MX3", available_qty=80, reserved_qty=0),
                GlobalInventorySnapshot(branch_code="HCM", sku="CHUOT-LOGI-MX3", available_qty=60, reserved_qty=0),
            ]
            db.add_all(snapshots)

        db.commit()
    finally:
        db.close()
    # Nhân bản ngay bản chụp đầu tiên sang DB Replica Dự phòng
    db_replicator.replicate_once()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_initial_data()
    broker = get_broker()
    await broker.connect()
    consumer_task = asyncio.create_task(start_hq_consumer())
    timeout_task = asyncio.create_task(run_saga_timeout_worker())
    replica_task = asyncio.create_task(db_replicator.run_loop(interval_seconds=5.0))
    yield
    consumer_task.cancel()
    timeout_task.cancel()
    replica_task.cancel()
    await broker.close()


app = FastAPI(
    title="HQ Distributed Warehouse Coordinator Service (Site 1)",
    version="2.0.0",
    description="Site 1 Trung tâm: Load Balancer (Central API 1/2), Master Catalog, Global Snapshot & Saga Orchestrator",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Load-Balancer", "X-Served-By-Instance", "X-DB-Role"]
)
register_lb_middleware(app, site_lb)

app.include_router(catalog.router, prefix="/api/v1")
app.include_router(catalog.master_router, prefix="/api/v1")
app.include_router(global_inventory.router, prefix="/api/v1")
app.include_router(transfers_saga.router, prefix="/api/v1")
app.include_router(create_auth_router(get_db, Account), prefix="/api/v1")


@app.post("/internal/events")
async def receive_internal_event(req: dict):
    routing_key = req.get("routing_key", "")
    data = req.get("data", {})
    broker = get_broker()
    await broker._dispatch_mock(routing_key, data)
    return {"status": "OK"}


@app.get("/cluster/status")
def cluster_status():
    """Trả về thông tin Load Balancer, App Instances và trạng thái DB Primary/Replica tại Site 1"""
    db_replicator.replicate_once()
    return {
        "cluster": site_lb.get_status(),
        "database": db_replicator.get_status()
    }


@app.get("/health")
def health_check():
    return {
        "status": "UP",
        "service": "HQ_SERVICE",
        "site": "Site 1 (Trung tâm)",
        "port": 8000,
        "load_balancer": site_lb.lb_name,
        "app_instances": site_lb.instances,
        "replica_healthy": db_replicator.is_healthy,
        "broker_connected": get_broker().is_connected
    }
