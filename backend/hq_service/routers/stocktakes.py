# backend/hq_service/routers/stocktakes.py
import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hq_service.database import get_db
from hq_service.dependencies import CurrentUser, get_current_user
from hq_service.models import OutboxEvent, StocktakeItemGlobal, StocktakeSessionGlobal
from hq_service.schemas import (
    StandardResponse,
    StocktakeItemGlobalResponse,
    StocktakeSessionGlobalResponse,
)
from shared.event_schemas import Envelope
from shared.messaging_topology import ROUTING_CMD_STOCKTAKE_FINALIZE, get_command_routing_key

router = APIRouter(prefix="/stocktakes", tags=["HQ - Global Stocktakes (Kiểm kê toàn quốc)"])


def _map_global_session(s: StocktakeSessionGlobal) -> StocktakeSessionGlobalResponse:
    items_resp = [
        StocktakeItemGlobalResponse(
            item_id=it.item_id,
            session_id=it.session_id,
            sku=it.sku,
            system_qty_at_start=it.system_qty_at_start,
            counted_qty=it.counted_qty,
            variance_qty=it.variance_qty,
            variance_reason=it.variance_reason
        )
        for it in (s.items or [])
    ]
    return StocktakeSessionGlobalResponse(
        session_id=s.session_id,
        session_code=s.session_code,
        branch_code=s.branch_code,
        status=s.status,
        scope_type=s.scope_type,
        total_skus_counted=s.total_skus_counted,
        total_variance_abs=s.total_variance_abs,
        created_by_name=s.created_by_name,
        approved_by_name=s.approved_by_name,
        finalized_by_name=s.finalized_by_name,
        created_at=s.created_at,
        approved_at=s.approved_at,
        finalized_at=s.finalized_at,
        last_synced_at=s.last_synced_at,
        items=items_resp
    )


@router.get("", response_model=StandardResponse[list[StocktakeSessionGlobalResponse]])
async def list_global_stocktakes(
    branch_code: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[list[StocktakeSessionGlobalResponse]]:
    """Tra cứu danh sách các phiên kiểm kê trên toàn bộ hệ thống chi nhánh"""
    stmt = (
        select(StocktakeSessionGlobal)
        .options(selectinload(StocktakeSessionGlobal.items))
        .order_by(StocktakeSessionGlobal.created_at.desc())
        .limit(limit)
    )
    if branch_code:
        stmt = stmt.where(StocktakeSessionGlobal.branch_code == branch_code.strip().upper())
    if status:
        stmt = stmt.where(StocktakeSessionGlobal.status == status.strip().upper())

    res = await db.execute(stmt)
    sessions = res.scalars().all()
    data = [_map_global_session(s) for s in sessions]
    return StandardResponse(success=True, data=data)


@router.get("/{session_id}", response_model=StandardResponse[StocktakeSessionGlobalResponse])
async def get_global_stocktake_detail(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[StocktakeSessionGlobalResponse]:
    """Xem chi tiết một phiên kiểm kê toàn cục và danh sách sai lệch SKU"""
    stmt = (
        select(StocktakeSessionGlobal)
        .options(selectinload(StocktakeSessionGlobal.items))
        .where(StocktakeSessionGlobal.session_id == session_id.strip())
    )
    res = await db.execute(stmt)
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy phiên kiểm kê {session_id}")
    return StandardResponse(success=True, data=_map_global_session(s))


@router.post("/{session_id}/finalize", response_model=StandardResponse[dict])
async def finalize_stocktake_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[dict]:
    """
    HQ Auditor / Manager chốt sổ kiểm kê chi nhánh:
    - Cập nhật Stocktake_Sessions_Global status='FINALIZED'
    - Ghi Outbox: cmd.stocktake.finalize.{branch_code} để chi nhánh chốt sổ
    """
    session = await db.get(StocktakeSessionGlobal, session_id.strip())
    if not session:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy phiên kiểm kê {session_id}")

    session.status = "FINALIZED"
    session.finalized_at = datetime.now(timezone.utc)
    session.finalized_by_name = user.user_id

    # Ghi Outbox gửi lệnh chốt sổ xuống chi nhánh
    msg_id = str(uuid.uuid4())
    payload = {
        "session_id": session.session_id,
        "session_code": session.session_code,
        "finalized_by": user.user_id
    }
    envelope = Envelope(
        message_id=msg_id,
        event_type="cmd.stocktake.finalize",
        timestamp=datetime.now(timezone.utc),
        data=payload
    )
    rkey = get_command_routing_key(ROUTING_CMD_STOCKTAKE_FINALIZE, session.branch_code)

    session_outbox = OutboxEvent(
        event_id=msg_id,
        routing_key=rkey,
        payload=envelope.model_dump_json(),
        is_published=False,
        next_retry_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc)
    )
    db.add(session_outbox)
    await db.commit()

    return StandardResponse(
        success=True,
        data={
            "session_id": session.session_id,
            "status": "FINALIZED",
            "message": f"Đã chốt sổ kiểm kê cho chi nhánh {session.branch_code}."
        }
    )
