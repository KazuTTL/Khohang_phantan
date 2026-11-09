# backend/shared/idempotency.py
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def safe_transaction(db: AsyncSession):
    """
    Quản lý transaction an toàn cho SQLAlchemy 2.0 AsyncSession.
    Nếu session đã có transaction đang mở (do lệnh SELECT autobegin), sử dụng begin_nested (SAVEPOINT).
    Nếu chưa có, mở transaction mới (db.begin()).
    """
    if db.in_transaction():
        async with db.begin_nested():
            yield
    else:
        async with db.begin():
            yield


async def check_inbox(db: AsyncSession, message_id: str) -> bool:
    """
    Kiểm tra xem message_id đã từng được xử lý trong Inbox_Events chưa.
    Trả về True nếu ĐÃ TỒN TẠI (cần bỏ qua), False nếu chưa từng xử lý.
    """
    if not message_id:
        return False

    query = text("SELECT 1 FROM Inbox_Events WHERE message_id = :mid")
    result = await db.execute(query, {"mid": message_id})
    return result.scalar() is not None


async def mark_inbox(db: AsyncSession, message_id: str, event_type: str = "UNKNOWN") -> None:
    """
    Ghi nhận message_id vào Inbox_Events trong cùng 1 local transaction.
    Đảm bảo nguyên tắc Idempotent Consumer (xử lý Exactly-Once).
    """
    if not message_id:
        return

    query = text(
        "INSERT INTO Inbox_Events (message_id, event_type, processed_at) "
        "VALUES (:mid, :etype, :now)"
    )
    await db.execute(query, {
        "mid": message_id,
        "etype": event_type,
        "now": datetime.now(timezone.utc)
    })
