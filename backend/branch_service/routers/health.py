# backend/branch_service/routers/health.py
from fastapi import APIRouter
from sqlalchemy import text

from branch_service.config import branch_settings
from branch_service.database import AsyncSessionLocal
from shared.rabbitmq_client import RabbitMQClient

router = APIRouter(tags=["Branch - Health Check"])


def get_health_router(rabbitmq_client: RabbitMQClient) -> APIRouter:
    @router.get("/health")
    async def health_check():
        db_healthy = False
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
                db_healthy = True
        except Exception:
            pass

        return {
            "status": "UP" if db_healthy else "DEGRADED",
            "service": f"BRANCH_{branch_settings.BRANCH_CODE}",
            "branch_code": branch_settings.BRANCH_CODE,
            "branch_name": branch_settings.BRANCH_NAME,
            "port": branch_settings.PORT,
            "database_connected": db_healthy,
            "broker_connected": rabbitmq_client.is_connected
        }

    return router
