# backend/branch_service/routers/users.py
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.config import branch_settings
from branch_service.database import get_db
from branch_service.models import BranchUser, UserRole
from branch_service.schemas import StandardResponse, UserResponse

router = APIRouter(prefix="/users", tags=["Branch - Users & Authentication"])


class CreateUserRequest(BaseModel):
    user_id: str = Field(..., max_length=50)
    full_name: str = Field(..., max_length=100)
    role: str = Field(..., description="STOCK_KEEPER, SALES, AUDITOR, BRANCH_MANAGER")


@router.get("/me", response_model=StandardResponse[UserResponse])
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="manager_hn"),
    x_role: str | None = Header(default="BRANCH_MANAGER")
):
    """Lấy thông tin người dùng hiện tại dựa trên Header X-User-Id và X-Role"""
    uid = x_user_id or f"manager_{branch_settings.BRANCH_CODE.lower()}"
    user = await db.get(BranchUser, uid)
    if not user:
        # Nếu chưa có trong DB, trả về thông tin giả lập từ Header
        return StandardResponse(
            success=True,
            data=UserResponse(
                user_id=uid,
                full_name=f"Người dùng {uid}",
                role=x_role or UserRole.BRANCH_MANAGER.value,
                is_active=True,
                branch_code=branch_settings.BRANCH_CODE
            ),
            error=None
        )

    return StandardResponse(
        success=True,
        data=UserResponse(
            user_id=user.user_id,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            branch_code=branch_settings.BRANCH_CODE
        ),
        error=None
    )


@router.get("", response_model=StandardResponse[list[UserResponse]])
async def list_branch_users(
    db: AsyncSession = Depends(get_db)
):
    """Danh sách nhân viên tại chi nhánh này"""
    stmt = select(BranchUser).order_by(BranchUser.user_id.asc())
    res = await db.execute(stmt)
    users = res.scalars().all()

    data = [
        UserResponse(
            user_id=u.user_id,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            branch_code=branch_settings.BRANCH_CODE
        )
        for u in users
    ]
    return StandardResponse(success=True, data=data, error=None)


@router.post("", response_model=StandardResponse[UserResponse])
async def create_branch_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default="manager_hn"),
    x_role: str | None = Header(default="BRANCH_MANAGER")
):
    """Thêm tài khoản nhân viên chi nhánh"""
    existing = await db.get(BranchUser, body.user_id.strip())
    if existing:
        raise HTTPException(status_code=400, detail=f"Tài khoản '{body.user_id}' đã tồn tại.")

    user = BranchUser(
        user_id=body.user_id.strip(),
        full_name=body.full_name.strip(),
        role=body.role.strip().upper(),
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return StandardResponse(
        success=True,
        data=UserResponse(
            user_id=user.user_id,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            branch_code=branch_settings.BRANCH_CODE
        ),
        error=None
    )
