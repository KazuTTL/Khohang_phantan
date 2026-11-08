# backend/shared/idempotency.py
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def check_and_mark_inbox(session: AsyncSession, message_id: str, consumer_name: str) -> bool:
    """
    Kiểm tra và ghi nhận Inbox Message trong cùng 1 Database Transaction cục bộ.
    Đảm bảo nguyên tắc Idempotent Consumer (Ngữ nghĩa xử lý Exactly-once):
    - Trả về True: Message chưa từng được xử lý -> Cho phép xử lý và ghi nhận vào Inbox.
    - Trả về False: Message đã được xử lý trước đó -> Bỏ qua (Duplicate / Replay).
    """
    if not message_id:
        return True

    # 1. Kiểm tra tồn tại trong Inbox_Messages
    check_query = text(
        "SELECT 1 FROM Inbox_Messages WHERE message_id = :msg_id AND consumer_name = :c_name"
    )
    result = await session.execute(check_query, {"msg_id": message_id, "c_name": consumer_name})
    if result.scalar() is not None:
        # Đã xử lý rồi -> Bỏ qua để chống duplicate
        return False

    # 2. Ghi nhận vào Inbox_Messages (chưa commit, sẽ commit cùng business transaction)
    insert_query = text(
        "INSERT INTO Inbox_Messages (message_id, consumer_name, processed_at) "
        "VALUES (:msg_id, :c_name, :proc_at)"
    )
    await session.execute(
        insert_query,
        {
            "msg_id": message_id,
            "c_name": consumer_name,
            "proc_at": datetime.now(timezone.utc)
        }
    )
    return True
