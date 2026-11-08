# backend/hq_service/dependencies.py
from fastapi import Header
from pydantic import BaseModel


class CurrentUser(BaseModel):
    user_id: str
    role: str


async def get_current_user(
    x_user_id: str | None = Header(default="anonymous_user"),
    x_role: str | None = Header(default="HQ_ADMIN")
) -> CurrentUser:
    """
    Xác thực đơn giản thông qua headers X-User-Id và X-Role theo đúng đặc tả đồ án.
    """
    return CurrentUser(user_id=x_user_id or "anonymous_user", role=x_role or "HQ_ADMIN")
