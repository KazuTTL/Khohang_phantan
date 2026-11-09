# backend/branch_service/database.py
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from branch_service.config import branch_settings

# NGUYÊN TẮC 1: Mỗi service chỉ có 1 AsyncEngine trỏ tới CSDL của nó (DB_Branch_HN hoặc DB_Branch_HCM)
# Tuyệt đối CẤM cross-DB query sang CSDL của Trụ sở chính hoặc Chi nhánh khác.
engine = create_async_engine(
    branch_settings.get_db_url(),
    echo=False,
    future=True,
    pool_pre_ping=True
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 Base Declarative Class"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency cung cấp session DB cục bộ độc lập cho từng request"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
