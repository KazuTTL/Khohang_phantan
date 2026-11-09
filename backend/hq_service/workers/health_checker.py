# backend/hq_service/workers/health_checker.py
import logging
from typing import Any
from sqlalchemy import text
from hq_service.database import AsyncSessionLocal
from shared.rabbitmq_client import RabbitMQClient

logger = logging.getLogger("HQHealthChecker")


class HQHealthChecker:
    @staticmethod
    async def check_health(rabbitmq_client: RabbitMQClient) -> dict[str, Any]:
        db_healthy = False
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
                db_healthy = True
        except Exception as e:
            logger.error(f"[HEALTH CHECK DB ERROR] {e}")

        broker_healthy = rabbitmq_client.is_connected

        return {
            "status": "UP" if (db_healthy and broker_healthy) else "DEGRADED",
            "service": "HQ_SERVICE",
            "database_connected": db_healthy,
            "broker_connected": broker_healthy
        }
