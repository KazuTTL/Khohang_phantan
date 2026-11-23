# backend/branch_service/main.py
import os
import uuid
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal, DATABASE_URL, get_db
from .models import LocalBranch, LocalCategory, LocalProduct, Account, LocalInventory
from .routers import local_inventory, incoming_transfers
from .consumers.branch_command_consumer import start_branch_consumer
from .services.outbox_worker import run_outbox_worker
from shared.rabbitmq_client import get_broker
from shared.auth import USERS_DB, hash_password
from shared.auth_router import create_auth_router
from shared.cluster_infra import (
    SiteLoadBalancer,
    LocalDBReplicator,
    resolve_sqlite_paths,
    register_lb_middleware,
)

BRANCH_CODE = os.getenv("BRANCH_CODE", "HN")
BRANCH_NAME = os.getenv("BRANCH_NAME", f"Chi nhánh {BRANCH_CODE}")
PORT = int(os.getenv("PORT", "8001"))

_site_label = "Site 2: Kho miền Bắc - Node HN" if BRANCH_CODE == "HN" else f"Site 3: Kho miền Nam - Node {BRANCH_CODE}"
_lb_name = f"LB-{BRANCH_CODE}-{'North' if BRANCH_CODE == 'HN' else 'South'}"
_instances = [f"Local-App-1-{BRANCH_CODE}", f"Local-App-2-{BRANCH_CODE}"]

site_lb = SiteLoadBalancer(site_name=_site_label, lb_name=_lb_name, instances=_instances)
primary_db_path, replica_db_path = resolve_sqlite_paths(DATABASE_URL, f"./db_branch_{BRANCH_CODE.lower()}.db")
db_replicator = LocalDBReplicator(primary_db_path, replica_db_path)


def seed_branch_data():
    """Khởi tạo các bảng tại DB Chi nhánh (Master Replicas + Phân mảnh Local) nếu chưa có"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. CHI_NHANH (Replica Read-Only tại Chi nhánh)
        if not db.query(LocalBranch).first():
            branches = [
                LocalBranch(branch_code="HQ", branch_name="Trụ sở chính (Trung tâm)", address="Số 1 Đại Cồ Việt, Hà Nội", site_type="TRUNG_TAM", status="ACTIVE"),
                LocalBranch(branch_code="HN", branch_name="Chi nhánh Hà Nội", address="KCN Bắc Thăng Long, Hà Nội", site_type="CHI_NHANH", status="ACTIVE"),
                LocalBranch(branch_code="HCM", branch_name="Chi nhánh TP.HCM", address="KCN Tân Bình, TP.HCM", site_type="CHI_NHANH", status="ACTIVE"),
            ]
            db.add_all(branches)

        # 2. DANH_MUC_SP (Replica tại Chi nhánh)
        if not db.query(LocalCategory).first():
            categories = [
                LocalCategory(category_id=1, category_name="Điện tử - Laptop", description="Máy tính xách tay, thiết bị công nghệ"),
                LocalCategory(category_id=2, category_name="Thiết bị ngoại vi", description="Chuột, bàn phím, màn hình"),
                LocalCategory(category_id=3, category_name="Phụ kiện & Lưu trữ", description="Ổ cứng, hub chuyển đổi, cáp kết nối"),
                LocalCategory(category_id=4, category_name="Thiết bị đo kiểm", description="Thiết bị đo lường kỹ thuật chuyên dụng")
            ]
            db.add_all(categories)

        # 3. SAN_PHAM (Replica tại Chi nhánh)
        if not db.query(LocalProduct).first():
            products = [
                LocalProduct(
                    sku="LAPTOP-DELL-01",
                    barcode="8938505970011",
                    product_name="Laptop Dell XPS 15",
                    category_id=1,
                    unit="Chiếc",
                    cost_price=29500000.0,
                    price=35000000.0
                ),
                LocalProduct(
                    sku="MACBOOK-AIR-M2",
                    barcode="8938505970028",
                    product_name="Apple MacBook Air M2",
                    category_id=1,
                    unit="Chiếc",
                    cost_price=24000000.0,
                    price=28000000.0
                ),
                LocalProduct(
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

        # 4. TAI_KHOAN (Đồng bộ về Chi nhánh phục vụ đăng nhập tự trị khi đứt mạng WAN)
        if not db.query(Account).first():
            for u in USERS_DB.values():
                if u["branch"] in (BRANCH_CODE, "HQ"):
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

        # 5. TON_KHO (Phân mảnh ngang theo ma_chi_nhanh)
        if not db.query(LocalInventory).first():
            if BRANCH_CODE == "HN":
                invs = [
                    LocalInventory(sku="LAPTOP-DELL-01", branch_code="HN", available_qty=100, reserved_qty=0, version=1),
                    LocalInventory(sku="MACBOOK-AIR-M2", branch_code="HN", available_qty=40, reserved_qty=0, version=1),
                    LocalInventory(sku="CHUOT-LOGI-MX3", branch_code="HN", available_qty=80, reserved_qty=0, version=1)
                ]
            else:
                invs = [
                    LocalInventory(sku="LAPTOP-DELL-01", branch_code=BRANCH_CODE, available_qty=50, reserved_qty=0, version=1),
                    LocalInventory(sku="MACBOOK-AIR-M2", branch_code=BRANCH_CODE, available_qty=30, reserved_qty=0, version=1),
                    LocalInventory(sku="CHUOT-LOGI-MX3", branch_code=BRANCH_CODE, available_qty=60, reserved_qty=0, version=1)
                ]
            db.add_all(invs)
        db.commit()
    finally:
        db.close()
    db_replicator.replicate_once()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_branch_data()
    broker = get_broker()
    await broker.connect()

    consumer_task = asyncio.create_task(start_branch_consumer())
    outbox_task = asyncio.create_task(run_outbox_worker())
    replica_task = asyncio.create_task(db_replicator.run_loop(interval_seconds=5.0))
    yield
    consumer_task.cancel()
    outbox_task.cancel()
    replica_task.cancel()
    await broker.close()


app = FastAPI(
    title=f"Branch Warehouse Service ({BRANCH_NAME})",
    version="2.0.0",
    description=f"Node Chi nhánh {BRANCH_CODE}: Load Balancer (Local App 1/2), 11-Table Sharding, DB Primary/Replica & Outbox Pattern",
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

app.include_router(local_inventory.router, prefix="/api/v1")
app.include_router(incoming_transfers.router, prefix="/api/v1")
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
    """Trả về thông tin Load Balancer, App Instances và trạng thái DB Primary/Replica tại Site Chi nhánh"""
    db_replicator.replicate_once()
    return {
        "cluster": site_lb.get_status(),
        "database": db_replicator.get_status()
    }


@app.get("/health")
def health_check():
    return {
        "status": "UP",
        "service": f"BRANCH_{BRANCH_CODE}",
        "site": _site_label,
        "branch_code": BRANCH_CODE,
        "branch_name": BRANCH_NAME,
        "port": PORT,
        "load_balancer": site_lb.lb_name,
        "app_instances": site_lb.instances,
        "replica_healthy": db_replicator.is_healthy,
        "broker_connected": get_broker().is_connected
    }
