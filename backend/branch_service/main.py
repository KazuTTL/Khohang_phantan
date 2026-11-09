# backend/branch_service/main.py
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from branch_service.config import branch_settings
from branch_service.consumers.branch_command_consumer import dispatch_branch_message
from branch_service.consumers.catalog_sync_consumer import on_catalog_sync
from branch_service.database import Base, async_session_factory, engine
from branch_service.models import BranchUser, LocalInventory, LocalProduct, Supplier, UserRole
from branch_service.routers import (
    health,
    local_inventory,
    purchase_receipts,
    stocktakes,
    suppliers,
    transfers,
    users,
)
from branch_service.services.outbox_worker import outbox_loop
from shared.logging_conf import setup_logger
from shared.messaging_topology import ROUTING_EVT_CATALOG_UPDATED, get_branch_queue_name
from shared.rabbitmq_client import RabbitMQClient

logger = setup_logger(f"BRANCH_{branch_settings.BRANCH_CODE}")

# Global RabbitMQ Client instance
rabbitmq_client = RabbitMQClient(branch_settings.RABBITMQ_URL)
outbox_task: asyncio.Task | None = None


async def seed_initial_data():
    """Tự động khởi tạo người dùng mặc định và dữ liệu mẫu nếu bảng rỗng"""
    code = branch_settings.BRANCH_CODE.lower()
    async with async_session_factory() as session:
        async with session.begin():
            # Seed Branch_Users với 4 vai trò bắt buộc theo chuẩn SoD
            existing_user = await session.get(BranchUser, f"manager_{code}")
            if not existing_user:
                branch_users = [
                    BranchUser(
                        user_id=f"manager_{code}",
                        full_name=f"Quản lý Chi nhánh {branch_settings.BRANCH_CODE}",
                        role=UserRole.BRANCH_MANAGER.value,
                        is_active=True
                    ),
                    BranchUser(
                        user_id=f"stock_{code}",
                        full_name=f"Thủ kho Chi nhánh {branch_settings.BRANCH_CODE}",
                        role=UserRole.STOCK_KEEPER.value,
                        is_active=True
                    ),
                    BranchUser(
                        user_id=f"sales_{code}",
                        full_name=f"Nhân viên Bán hàng {branch_settings.BRANCH_CODE}",
                        role=UserRole.SALES.value,
                        is_active=True
                    ),
                    BranchUser(
                        user_id=f"auditor_{code}",
                        full_name=f"Kiểm toán viên Kho {branch_settings.BRANCH_CODE}",
                        role=UserRole.AUDITOR.value,
                        is_active=True
                    )
                ]
                session.add_all(branch_users)

            # Seed Nhà Cung Cấp mẫu
            existing_supp = await session.get(Supplier, "NCC-SAMSUNG")
            if not existing_supp:
                suppliers_list = [
                    Supplier(supplier_id="NCC-SAMSUNG", supplier_name="Công ty Điện tử Samsung Vina", tax_code="0301112233", contact_phone="0901234567", is_active=True),
                    Supplier(supplier_id="NCC-LOGITECH", supplier_name="Nhà phân phối Logitech Digiworld", tax_code="0109988776", contact_phone="0912345678", is_active=True),
                    Supplier(supplier_id="NCC-APPLE", supplier_name="Apple Vietnam Authorized Distributor", tax_code="0312456789", contact_phone="0988776655", is_active=True)
                ]
                session.add_all(suppliers_list)

            # Seed Local_Products & Local_Inventory nếu chưa có
            p1 = await session.get(LocalProduct, "BAN-PHIM-CO")
            if not p1:
                products = [
                    LocalProduct(sku="BAN-PHIM-CO", product_name="Bàn phím cơ không dây Bluetooth Pro", unit="Chiếc"),
                    LocalProduct(sku="CHUOT-LOGI-MX3", product_name="Chuột công thái học cao cấp Silent", unit="Chiếc"),
                    LocalProduct(sku="TAI-NGHE-SONY", product_name="Tai nghe chụp tai chống ồn ANC", unit="Chiếc"),
                    LocalProduct(sku="MAN-HINH-4K", product_name="Màn hình đồ họa 27 inch 4K HDR", unit="Chiếc")
                ]
                session.add_all(products)
                await session.flush()

                # Tồn kho ban đầu
                init_qty = 100 if branch_settings.BRANCH_CODE == "HN" else 50
                invs = [
                    LocalInventory(sku="BAN-PHIM-CO", available_qty=init_qty, reserved_qty=0, version=1),
                    LocalInventory(sku="CHUOT-LOGI-MX3", available_qty=init_qty, reserved_qty=0, version=1),
                    LocalInventory(sku="TAI-NGHE-SONY", available_qty=30, reserved_qty=0, version=1),
                    LocalInventory(sku="MAN-HINH-4K", available_qty=20, reserved_qty=0, version=1)
                ]
                session.add_all(invs)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời khởi động và kết thúc của Node Chi nhánh"""
    global outbox_task
    logger.info(f"[STARTUP] Khởi động Chi nhánh {branch_settings.BRANCH_CODE} (Port {branch_settings.PORT})...")

    # 1. Khởi tạo schema CSDL cục bộ DB_Branch_{CODE}
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"[STARTUP] CSDL DB_Branch_{branch_settings.BRANCH_CODE} đã sẵn sàng.")

    # 2. Seed dữ liệu mẫu (Users, Products, Inventory, Suppliers)
    await seed_initial_data()

    # 3. Kết nối RabbitMQ Broker
    connected = await rabbitmq_client.connect()

    # 4. Khởi chạy Outbox Worker loop
    outbox_task = asyncio.create_task(outbox_loop(async_session_factory, rabbitmq_client))

    # 5. Đăng ký Consumers nếu RabbitMQ kết nối thành công
    if connected:
        branch_code = branch_settings.BRANCH_CODE
        cmd_queue = get_branch_queue_name(branch_code)
        
        # Callback wrapper cho branch commands
        async def _cmd_consumer(msg_data, rkey):
            await dispatch_branch_message(msg_data, rkey, async_session_factory)

        # Lắng nghe các lệnh điều chuyển 3 cấp và chốt sổ
        await rabbitmq_client.subscribe(
            queue_name=cmd_queue,
            binding_keys=[
                f"cmd.transfer.approve_request.{branch_code}",
                f"cmd.transfer.confirm_receive.{branch_code}",
                f"cmd.transfer.release.{branch_code}",
                f"cmd.transfer.reserve.{branch_code}",
                f"cmd.transfer.import.{branch_code}",
                f"cmd.stocktake.finalize.{branch_code}",
                "evt.transfer.completed"
            ],
            callback=_cmd_consumer
        )

        # Callback wrapper cho catalog sync
        async def _catalog_consumer(msg_data, rkey):
            await on_catalog_sync(msg_data, rkey, async_session_factory)

        catalog_queue = f"q.branch.{branch_code.lower()}.catalog_sync"
        await rabbitmq_client.subscribe(
            queue_name=catalog_queue,
            binding_keys=[ROUTING_EVT_CATALOG_UPDATED],
            callback=_catalog_consumer
        )
    else:
        logger.warning(f"[STARTUP] RabbitMQ chưa kết nối. Chi nhánh {branch_settings.BRANCH_CODE} hoạt động ở chế độ TỰ TRỊ CỤC BỘ (Local Autonomy).")

    yield

    # Shutdown
    logger.info(f"[SHUTDOWN] Đang dừng Chi nhánh {branch_settings.BRANCH_CODE}...")
    if outbox_task:
        outbox_task.cancel()
        try:
            await outbox_task
        except asyncio.CancelledError:
            pass

    await rabbitmq_client.close()
    await engine.dispose()
    logger.info(f"[SHUTDOWN] Chi nhánh {branch_settings.BRANCH_CODE} đã dừng an toàn.")


app = FastAPI(
    title=f"SmartLog WMS - Branch {branch_settings.BRANCH_CODE} Service",
    description=f"Node Dịch vụ Kho Chi nhánh {branch_settings.get_branch_display_name()} (FastAPI + SQLAlchemy 2.0 + aio-pika)",
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
async def branch_global_exception_handler(request: Request, exc: Exception):
    logger.error(f"[UNHANDLED EXCEPTION] {request.method} {request.url.path}: {exc}", exc_info=True)
    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "data": None, "error": detail}
    )


# Đăng ký các Router cho Branch Service
app.include_router(local_inventory.router, prefix="/api/v1")
app.include_router(purchase_receipts.router, prefix="/api/v1")
app.include_router(transfers.router, prefix="/api/v1")
app.include_router(stocktakes.router, prefix="/api/v1")
app.include_router(suppliers.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(health.get_health_router(rabbitmq_client))

# Alias hỗ trợ frontend: /api/v1/ledger
app.add_api_route("/api/v1/ledger", local_inventory.get_stock_ledger, methods=["GET"], tags=["Branch - Local Inventory (Local Autonomy)"])
