# backend/hq_service/dependencies.py
from fastapi import Header
from pydantic import BaseModel


class CurrentUser(BaseModel):
    user_id: str
    role: str


async def get_current_user(
    x_user_id: str | None = Header(default="hq_manager_01"),
    x_role: str | None = Header(default="HQ_MANAGER")
) -> CurrentUser:
    """
    Xác thực đơn giản thông qua headers X-User-Id và X-Role theo đúng đặc tả đồ án.
    Roles tại HQ: HQ_STAFF, HQ_MANAGER, HQ_AUDITOR
    """
    return CurrentUser(
        user_id=x_user_id or "hq_manager_01",
        role=(x_role or "HQ_MANAGER").strip().upper()
    )
