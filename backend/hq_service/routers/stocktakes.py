# backend/hq_service/routers/stocktakes.py
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hq_service.database import get_db
from hq_service.dependencies import CurrentUser, get_current_user
from hq_service.models import StocktakeSession
from hq_service.schemas import CreateStocktakeRequest, StandardResponse, StocktakeResponse

router = APIRouter(prefix="/stocktakes", tags=["HQ - Global Stocktakes"])


@router.get("", response_model=StandardResponse[list[StocktakeResponse]])
async def list_stocktake_sessions(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[list[StocktakeResponse]]:
    """Danh sách các phiên kiểm kê toàn hệ thống"""
    stmt = select(StocktakeSession).order_by(StocktakeSession.created_at.desc())
    res = await db.execute(stmt)
    sessions = res.scalars().all()

    data = [
        StocktakeResponse(
            session_id=s.session_id,
            title=s.title,
            status=s.status,
            created_by=s.created_by,
            created_at=s.created_at,
            closed_at=s.closed_at
        )
        for s in sessions
    ]
    return StandardResponse(success=True, data=data)


@router.post("", response_model=StandardResponse[StocktakeResponse])
async def create_stocktake_session(
    req: CreateStocktakeRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[StocktakeResponse]:
    """Phát động một đợt kiểm kê kho hàng toàn hệ thống mới"""
    session_id = str(uuid.uuid4())[:8].upper()
    session = StocktakeSession(
        session_id=session_id,
        title=req.title.strip(),
        status="OPEN",
        created_by=user.user_id,
        created_at=datetime.now(timezone.utc)
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return StandardResponse(
        success=True,
        data=StocktakeResponse(
            session_id=session.session_id,
            title=session.title,
            status=session.status,
            created_by=session.created_by,
            created_at=session.created_at,
            closed_at=session.closed_at
        )
    )


@router.post("/{session_id}/close", response_model=StandardResponse[StocktakeResponse])
async def close_stocktake_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[StocktakeResponse]:
    """Chốt và đóng đợt kiểm kê sau khi các chi nhánh đã đối soát số liệu"""
    session = await db.get(StocktakeSession, session_id.strip())
    if not session:
        return StandardResponse(success=False, error=f"Không tìm thấy phiên kiểm kê {session_id}")

    session.status = "CLOSED"
    session.closed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)

    return StandardResponse(
        success=True,
        data=StocktakeResponse(
            session_id=session.session_id,
            title=session.title,
            status=session.status,
            created_by=session.created_by,
            created_at=session.created_at,
            closed_at=session.closed_at
        )
    )
