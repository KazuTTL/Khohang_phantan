# backend/hq_service/main.py
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from hq_service.config import hq_settings
from hq_service.consumers.dlq_consumer import process_dlq_message
from hq_service.consumers.hq_event_consumer import process_hq_event
from hq_service.database import Base, engine
from hq_service.routers import branches, catalog, global_inventory, stocktakes, transfers
from hq_service.workers.health_checker import HQHealthChecker
from hq_service.workers.outbox_worker import HQOutboxWorker
from shared.logging_conf import setup_logger
from shared.messaging_topology import DLQ_QUEUE_NAME, get_hq_queue_name
from shared.rabbitmq_client import RabbitMQClient

logger = setup_logger("HQ_SERVICE")

# Global instances
rabbitmq_client = RabbitMQClient(hq_settings.RABBITMQ_URL)
outbox_worker = HQOutboxWorker(rabbitmq_client)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời khởi động và kết thúc của Node Trụ sở chính (HQ)"""
    logger.info("[STARTUP] Đang khởi động Node Trụ sở chính (HQ - Port 8000)...")

    # 1. Khởi tạo bảng CSDL DB_HQ nếu chưa tồn tại
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[STARTUP] CSDL DB_HQ đã sẵn sàng.")

    # 2. Kết nối RabbitMQ Topic Exchange
    connected = await rabbitmq_client.connect()
    
    # 3. Khởi chạy Outbox Worker và Event Consumers nếu Broker kết nối thành công
    if connected:
        await outbox_worker.start()
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
    await outbox_worker.stop()
    await rabbitmq_client.close()
    await engine.dispose()
    logger.info("[SHUTDOWN] HQ Node đã dừng an toàn.")


app = FastAPI(
    title="SmartLog Distributed WMS - HQ Node API",
    description="Node Điều phối Trung tâm & Saga Orchestrator cho Hệ thống Kho Phân tán",
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
    return JSONResponse(
        status_code=500,
        content={"success": False, "data": None, "error": f"Lỗi máy chủ nội bộ: {str(exc)}"}
    )


# Đăng ký các Router nghiệp vụ
app.include_router(branches.router, prefix="/api/v1")
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(global_inventory.router, prefix="/api/v1")
app.include_router(transfers.router, prefix="/api/v1")
app.include_router(stocktakes.router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    """Kiểm tra sức khỏe dịch vụ và kết nối CSDL / RabbitMQ"""
    return await HQHealthChecker.check_health(rabbitmq_client)
