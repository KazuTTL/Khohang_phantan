# backend/branch_service/database.py
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from branch_service.config import branch_settings

# NGUYÊN TẮC 1: Mỗi service chỉ có 1 AsyncEngine trỏ tới CSDL của nó (DB_Branch_HN hoặc DB_Branch_HCM)
engine = create_async_engine(
    branch_settings.get_database_url(),
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
    """Dependency cung cấp session DB cục bộ độc lập cho từng request tại chi nhánh"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
