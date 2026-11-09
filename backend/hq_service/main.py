# backend/hq_service/main.py
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from hq_service.config import hq_settings
from hq_service.consumers.dlq_consumer import process_dlq_message
from hq_service.consumers.hq_event_consumer import process_hq_event
from hq_service.database import AsyncSessionLocal, Base, engine
from hq_service.models import Branch, GlobalInventorySnapshot, HQUser, HQUserRole, Product
from hq_service.routers import branches, catalog, global_inventory, stocktakes, transfers
from hq_service.workers.health_checker import HQHealthChecker
from hq_service.workers.outbox_worker import outbox_loop
from shared.logging_conf import setup_logger
from shared.messaging_topology import DLQ_QUEUE_NAME, get_hq_queue_name
from shared.rabbitmq_client import RabbitMQClient

logger = setup_logger("HQ_SERVICE")

# Global instances
rabbitmq_client = RabbitMQClient(hq_settings.RABBITMQ_URL)
outbox_task: asyncio.Task | None = None


async def seed_hq_initial_data():
    """Tự động khởi tạo dữ liệu mẫu cho Trụ sở chính (Branches, Users, Catalog)"""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 1. Seed Branches
            hn = await session.get(Branch, "HN")
            if not hn:
                session.add_all([
                    Branch(branch_code="HN", branch_name="Chi nhánh Hà Nội", api_base_url="http://branch_hn:8001", is_active=True, is_online=True),
                    Branch(branch_code="HCM", branch_name="Chi nhánh TP.HCM", api_base_url="http://branch_hcm:8002", is_active=True, is_online=True)
                ])

            # 2. Seed HQ Users
            user = await session.get(HQUser, "hq_manager_01")
            if not user:
                session.add_all([
                    HQUser(user_id="hq_staff_01", full_name="Nguyễn Văn Nhân", role=HQUserRole.HQ_STAFF.value, is_active=True),
                    HQUser(user_id="hq_manager_01", full_name="Trần Thị Duyệt", role=HQUserRole.HQ_MANAGER.value, is_active=True),
                    HQUser(user_id="hq_auditor_01", full_name="Lê Văn Kiểm", role=HQUserRole.HQ_AUDITOR.value, is_active=True)
                ])

            # 3. Seed Master Products
            p1 = await session.get(Product, "BAN-PHIM-CO")
            if not p1:
                products = [
                    Product(sku="BAN-PHIM-CO", product_name="Bàn phím cơ không dây Bluetooth Pro", unit="Chiếc", is_deleted=False),
                    Product(sku="CHUOT-LOGI-MX3", product_name="Chuột công thái học cao cấp Silent", unit="Chiếc", is_deleted=False),
                    Product(sku="TAI-NGHE-SONY", product_name="Tai nghe chụp tai chống ồn ANC", unit="Chiếc", is_deleted=False),
                    Product(sku="MAN-HINH-4K", product_name="Màn hình đồ họa 27 inch 4K HDR", unit="Chiếc", is_deleted=False)
                ]
                session.add_all(products)
                await session.flush()

                # Seed initial snapshot for both branches
                snapshots = [
                    GlobalInventorySnapshot(branch_code="HN", sku="BAN-PHIM-CO", available_qty=100, reserved_qty=0),
                    GlobalInventorySnapshot(branch_code="HN", sku="CHUOT-LOGI-MX3", available_qty=100, reserved_qty=0),
                    GlobalInventorySnapshot(branch_code="HN", sku="TAI-NGHE-SONY", available_qty=30, reserved_qty=0),
                    GlobalInventorySnapshot(branch_code="HN", sku="MAN-HINH-4K", available_qty=20, reserved_qty=0),
                    GlobalInventorySnapshot(branch_code="HCM", sku="BAN-PHIM-CO", available_qty=50, reserved_qty=0),
                    GlobalInventorySnapshot(branch_code="HCM", sku="CHUOT-LOGI-MX3", available_qty=50, reserved_qty=0),
                    GlobalInventorySnapshot(branch_code="HCM", sku="TAI-NGHE-SONY", available_qty=30, reserved_qty=0),
                    GlobalInventorySnapshot(branch_code="HCM", sku="MAN-HINH-4K", available_qty=20, reserved_qty=0),
                ]
                session.add_all(snapshots)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời khởi động và kết thúc của Node Trụ sở chính (HQ)"""
    global outbox_task
    logger.info("[STARTUP] Đang khởi động Node Trụ sở chính (HQ - Port 8000)...")

    # 1. Khởi tạo bảng CSDL DB_HQ nếu chưa tồn tại
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[STARTUP] CSDL DB_HQ đã sẵn sàng.")

    # 2. Seed dữ liệu mặc định
    await seed_hq_initial_data()

    # 3. Kết nối RabbitMQ Topic Exchange
    connected = await rabbitmq_client.connect()

    # 4. Khởi chạy Outbox Worker loop
    outbox_task = asyncio.create_task(outbox_loop(AsyncSessionLocal, rabbitmq_client))
    
    # 5. Khởi chạy Event Consumers nếu Broker kết nối thành công
    if connected:
        try:
            # Lắng nghe toàn bộ event từ chi nhánh gửi về HQ: evt.#
            await rabbitmq_client.subscribe(
                queue_name=get_hq_queue_name(),
                binding_keys=["evt.#"],
                callback=process_hq_event
            )
            # Lắng nghe Dead Letter Queue
            await rabbitmq_client.subscribe(
                queue_name=DLQ_QUEUE_NAME,
                binding_keys=["#"],
                callback=process_dlq_message
            )
        except Exception as e:
            logger.error(f"[STARTUP CONSUMER ERROR] {e}")
    else:
        logger.warning("[STARTUP] RabbitMQ chưa sẵn sàng. Outbox Worker sẽ chờ kết nối lại.")

    yield

    # Shutdown
    logger.info("[SHUTDOWN] Đang dừng Node Trụ sở chính...")
    if outbox_task:
        outbox_task.cancel()
        try:
            await outbox_task
        except asyncio.CancelledError:
            pass

    await rabbitmq_client.close()
    await engine.dispose()
    logger.info("[SHUTDOWN] HQ Node đã dừng an toàn.")


app = FastAPI(
    title="SmartLog Distributed WMS - HQ Node API",
    description="Node Điều phối Trung tâm & Saga Orchestrator cho Hệ thống Kho Phân tán (FastAPI + SQLAlchemy 2.0 async + aio-pika)",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handler chuẩn hóa: {"success": False, "data": None, "error": str}
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"[UNHANDLED EXCEPTION] {request.method} {request.url.path}: {exc}", exc_info=True)
    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "data": None, "error": detail}
    )


# Health check endpoint
@app.get("/api/v1/health", tags=["HQ - Health"])
async def health_check():
    """Kiểm tra trạng thái kết nối CSDL và Message Broker của Node HQ"""
    status = await HQHealthChecker.check_health(rabbitmq_client)
    return {"success": True, "data": status, "error": None}


# Đăng ký các Router nghiệp vụ
app.include_router(branches.router, prefix="/api/v1")
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(global_inventory.router, prefix="/api/v1")
app.include_router(transfers.router, prefix="/api/v1")
app.include_router(stocktakes.router, prefix="/api/v1")
