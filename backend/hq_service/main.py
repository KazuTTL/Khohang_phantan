# backend/hq_service/main.py
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal
from .models import Branch, Product, GlobalInventorySnapshot
from .routers import catalog, global_inventory, transfers_saga
from .consumers.hq_event_consumer import start_hq_consumer
from shared.rabbitmq_client import get_broker

def seed_initial_data():
    """Khởi tạo bảng và nạp dữ liệu mẫu ban đầu nếu chưa có"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(Branch).first():
            branches = [
                Branch(branch_code="HN", branch_name="Chi nhánh Hà Nội", api_base_url="http://127.0.0.1:8001/api/v1", is_active=True),
                Branch(branch_code="HCM", branch_name="Chi nhánh TP.HCM", api_base_url="http://127.0.0.1:8002/api/v1", is_active=True)
            ]
            db.add_all(branches)

        if not db.query(Product).first():
            products = [
                Product(sku="LAPTOP-DELL-01", product_name="Laptop Dell XPS 15", unit="Chiếc", price=35000000.0),
                Product(sku="MACBOOK-AIR-M2", product_name="Apple MacBook Air M2", unit="Chiếc", price=28000000.0),
                Product(sku="CHUOT-LOGI-MX3", product_name="Chuột Logitech MX Master 3S", unit="Con", price=2200000.0)
            ]
            db.add_all(products)

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo DB & Seed
    seed_initial_data()
    # Kết nối RabbitMQ
    broker = get_broker()
    await broker.connect()
    # Khởi động Consumer nền
    consumer_task = asyncio.create_task(start_hq_consumer())
    yield
    # Dọn dẹp tài nguyên
    consumer_task.cancel()
    await broker.close()

app = FastAPI(
    title="HQ Central Warehouse Service (Node Trụ sở chính)",
    version="1.0.0",
    description="Dịch vụ Trụ sở chính quản lý Master Data, Global Snapshot và điều phối Saga Orchestration",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gắn Routers theo tiền tố chuẩn /api/v1
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(global_inventory.router, prefix="/api/v1")
app.include_router(transfers_saga.router, prefix="/api/v1")

@app.post("/internal/events")
async def receive_internal_event(req: dict):
    routing_key = req.get("routing_key", "")
    data = req.get("data", {})
    broker = get_broker()
    await broker._dispatch_mock(routing_key, data)
    return {"status": "OK"}

@app.get("/health")
def health_check():
    return {
        "status": "UP",
        "service": "HQ_SERVICE",
        "port": 8000,
        "broker_connected": get_broker().is_connected
    }
