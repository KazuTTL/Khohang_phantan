# backend/branch_service/main.py
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from branch_service.config import branch_settings
from branch_service.consumers.branch_command_consumer import process_branch_command
from branch_service.consumers.catalog_sync_consumer import process_catalog_sync
from branch_service.database import Base, engine
from branch_service.routers import incoming_transfers, local_inventory, stocktakes
from branch_service.routers.health import get_health_router
from branch_service.services.outbox_worker import BranchOutboxWorker
from shared.logging_conf import setup_logger
from shared.messaging_topology import (
    ROUTING_EVT_CATALOG_UPDATED, ROUTING_EVT_TRANSFER_COMPLETED,
    get_branch_queue_name
)
from shared.rabbitmq_client import RabbitMQClient

logger = setup_logger(f"BRANCH_{branch_settings.BRANCH_CODE}")

# Global instances
rabbitmq_client = RabbitMQClient(branch_settings.RABBITMQ_URL)
outbox_worker = BranchOutboxWorker(rabbitmq_client)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời khởi động và kết thúc của Node Chi nhánh (Branch Node)"""
    logger.info(f"[STARTUP] Đang khởi động Chi nhánh {branch_settings.BRANCH_CODE} (Port {branch_settings.PORT})...")

    # 1. Khởi tạo bảng CSDL cục bộ DB_Branch_{CODE} nếu chưa tồn tại
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"[STARTUP] CSDL DB_Branch_{branch_settings.BRANCH_CODE} đã sẵn sàng.")

    # 2. Kết nối RabbitMQ Topic Exchange
    connected = await rabbitmq_client.connect()

    # 3. Khởi chạy Outbox Worker và Command Consumers nếu Broker kết nối thành công
    if connected:
        await outbox_worker.start()
        try:
            branch_queue = get_branch_queue_name(branch_settings.BRANCH_CODE)
            # Lắng nghe các command gửi tới chi nhánh này + sự kiện hoàn tất transfer
            await rabbitmq_client.subscribe(
                queue_name=branch_queue,
                binding_keys=[
                    f"cmd.transfer.*.{branch_settings.BRANCH_CODE}",
                    ROUTING_EVT_TRANSFER_COMPLETED
                ],
                callback=process_branch_command
            )

            # Lắng nghe sự kiện đồng bộ danh mục sản phẩm từ HQ
            catalog_queue = f"q.branch.{branch_settings.BRANCH_CODE.lower()}.catalog"
            await rabbitmq_client.subscribe(
                queue_name=catalog_queue,
                binding_keys=[ROUTING_EVT_CATALOG_UPDATED],
                callback=process_catalog_sync
            )
        except Exception as e:
            logger.error(f"[STARTUP CONSUMER ERROR] {e}")
    else:
        logger.warning(f"[STARTUP] Chi nhánh {branch_settings.BRANCH_CODE}: RabbitMQ chưa sẵn sàng. Outbox Worker sẽ chờ kết nối lại.")

    yield

    # Shutdown
    logger.info(f"[SHUTDOWN] Đang dừng Chi nhánh {branch_settings.BRANCH_CODE}...")
    await outbox_worker.stop()
    await rabbitmq_client.close()
    await engine.dispose()
    logger.info(f"[SHUTDOWN] Chi nhánh {branch_settings.BRANCH_CODE} đã dừng an toàn.")


app = FastAPI(
    title=f"SmartLog WMS - Branch {branch_settings.BRANCH_CODE} API",
    description=f"Node Chi nhánh {branch_settings.BRANCH_NAME} (Vận hành Tự trị Cục bộ & Khóa dòng UPDLOCK)",
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
async def branch_exception_handler(request: Request, exc: Exception):
    logger.error(f"[UNHANDLED EXCEPTION] {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "data": None, "error": f"Lỗi chi nhánh: {str(exc)}"}
    )


# Đăng ký các Router nghiệp vụ
app.include_router(local_inventory.router, prefix="/api/v1")
app.include_router(incoming_transfers.router, prefix="/api/v1")
app.include_router(stocktakes.router, prefix="/api/v1")
app.include_router(get_health_router(rabbitmq_client))
