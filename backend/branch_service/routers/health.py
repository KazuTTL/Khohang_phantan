# backend/branch_service/routers/health.py
import httpx
from fastapi import APIRouter
from sqlalchemy import text

from branch_service.config import branch_settings
from branch_service.database import async_session_factory
from shared.rabbitmq_client import RabbitMQClient

router = APIRouter(tags=["Branch - Health Check"])


def get_health_router(rabbitmq_client: RabbitMQClient) -> APIRouter:
    @router.get("/health")
    async def health_check():
        """
        Kiểm tra sức khỏe phân tán:
        1. DB cục bộ: ping SELECT 1
        2. RabbitMQ broker: trạng thái kết nối
        3. HQ Node: gọi thử GET /health với timeout 2.0s
        """
        # 1. Ping DB
        db_ok = False
        try:
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
                db_ok = True
        except Exception:
            db_ok = False

        # 2. Ping MQ
        mq_ok = rabbitmq_client.is_connected and rabbitmq_client.connection and not rabbitmq_client.connection.is_closed

        # 3. Ping HQ
        hq_reachable = False
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{branch_settings.HQ_API_URL}/health")
                if resp.status_code == 200:
                    hq_reachable = True
        except Exception:
            hq_reachable = False

        status = "UP" if (db_ok and mq_ok) else ("AUTONOMOUS" if db_ok else "DOWN")

        return {
            "status": status,
            "service": "branch",
            "branch_code": branch_settings.BRANCH_CODE,
            "branch_name": branch_settings.get_branch_display_name(),
            "port": branch_settings.PORT,
            "db_ok": db_ok,
            "mq_ok": mq_ok,
            "hq_reachable": hq_reachable
        }

    return router
