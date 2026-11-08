# backend/hq_service/database.py
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from hq_service.config import hq_settings

# NGUYÊN TẮC 1: Mỗi service chỉ có 1 AsyncEngine trỏ tới CSDL của riêng nó (DB_HQ)
engine = create_async_engine(
    hq_settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency cung cấp session DB cục bộ độc lập cho từng request"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
