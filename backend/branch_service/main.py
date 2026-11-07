# backend/branch_service/main.py
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal
from .models import LocalProduct, LocalInventory
from .routers import local_inventory, incoming_transfers
from .consumers.branch_command_consumer import start_branch_consumer
from .services.outbox_worker import run_outbox_worker
from shared.rabbitmq_client import get_broker

BRANCH_CODE = os.getenv("BRANCH_CODE", "HN")
BRANCH_NAME = os.getenv("BRANCH_NAME", f"Chi nhánh {BRANCH_CODE}")
PORT = int(os.getenv("PORT", "8001"))

def seed_branch_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(LocalProduct).first():
            products = [
                LocalProduct(sku="LAPTOP-DELL-01", product_name="Laptop Dell XPS 15", unit="Chiếc"),
                LocalProduct(sku="MACBOOK-AIR-M2", product_name="Apple MacBook Air M2", unit="Chiếc"),
                LocalProduct(sku="CHUOT-LOGI-MX3", product_name="Chuột Logitech MX Master 3S", unit="Con")
            ]
            db.add_all(products)

        if not db.query(LocalInventory).first():
            # Tồn kho ban đầu theo từng chi nhánh
            if BRANCH_CODE == "HN":
                invs = [
                    LocalInventory(sku="LAPTOP-DELL-01", available_qty=100, reserved_qty=0, version=1),
                    LocalInventory(sku="MACBOOK-AIR-M2", available_qty=40, reserved_qty=0, version=1),
                    LocalInventory(sku="CHUOT-LOGI-MX3", available_qty=80, reserved_qty=0, version=1)
                ]
            else: # HCM hoặc chi nhánh khác
                invs = [
                    LocalInventory(sku="LAPTOP-DELL-01", available_qty=50, reserved_qty=0, version=1),
                    LocalInventory(sku="MACBOOK-AIR-M2", available_qty=30, reserved_qty=0, version=1),
                    LocalInventory(sku="CHUOT-LOGI-MX3", available_qty=60, reserved_qty=0, version=1)
                ]
            db.add_all(invs)
        db.commit()
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_branch_data()
    broker = get_broker()
    await broker.connect()

    # Chạy đồng thời Consumer và Outbox Worker
    consumer_task = asyncio.create_task(start_branch_consumer())
    outbox_task = asyncio.create_task(run_outbox_worker())
    yield
    consumer_task.cancel()
    outbox_task.cancel()
    await broker.close()

app = FastAPI(
    title=f"Branch Warehouse Service ({BRANCH_NAME})",
    version="1.0.0",
    description=f"Node Chi nhánh {BRANCH_CODE} vận hành tự trị cục bộ, kiểm soát đồng thời và trao đổi qua Outbox Pattern",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(local_inventory.router, prefix="/api/v1")
app.include_router(incoming_transfers.router, prefix="/api/v1")

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
        "service": f"BRANCH_{BRANCH_CODE}",
        "branch_code": BRANCH_CODE,
        "branch_name": BRANCH_NAME,
        "port": PORT,
        "broker_connected": get_broker().is_connected
    }
