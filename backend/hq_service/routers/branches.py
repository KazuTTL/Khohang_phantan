# backend/hq_service/routers/branches.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hq_service.database import get_db
from hq_service.dependencies import CurrentUser, get_current_user
from hq_service.models import Branch
from hq_service.schemas import BranchResponse, CreateBranchRequest, StandardResponse

router = APIRouter(prefix="/branches", tags=["HQ - Branches"])


@router.get("", response_model=StandardResponse[list[BranchResponse]])
async def list_branches(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[list[BranchResponse]]:
    """Lấy danh sách tất cả các chi nhánh trong hệ thống"""
    stmt = select(Branch).order_by(Branch.branch_code.asc())
    res = await db.execute(stmt)
    branches = res.scalars().all()

    data = [
        BranchResponse(
            branch_code=b.branch_code,
            branch_name=b.branch_name,
            api_base_url=b.api_base_url,
            is_active=b.is_active,
            is_online=b.is_online
        )
        for b in branches
    ]
    return StandardResponse(success=True, data=data)


@router.post("", response_model=StandardResponse[BranchResponse])
async def create_branch(
    req: CreateBranchRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[BranchResponse]:
    """Đăng ký chi nhánh mới vào mạng lưới phân tán"""
    code = req.branch_code.strip().upper()
    existing = await db.get(Branch, code)
    if existing:
        raise HTTPException(status_code=400, detail=f"Mã chi nhánh '{code}' đã tồn tại.")

    branch = Branch(
        branch_code=code,
        branch_name=req.branch_name.strip(),
        api_base_url=req.api_base_url.strip(),
        is_active=True,
        is_online=True
    )
    db.add(branch)
    await db.commit()
    await db.refresh(branch)

    return StandardResponse(
        success=True,
        data=BranchResponse(
            branch_code=branch.branch_code,
            branch_name=branch.branch_name,
            api_base_url=branch.api_base_url,
            is_active=branch.is_active,
            is_online=branch.is_online
        )
    )
