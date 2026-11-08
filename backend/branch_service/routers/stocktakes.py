# backend/branch_service/routers/stocktakes.py
from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.database import get_db
from branch_service.models import StocktakeRecord
from branch_service.schemas import (
    StandardResponse, StocktakeRecordResponse, SubmitStocktakeRequest
)
from branch_service.services.stocktake_service import StocktakeService

router = APIRouter(prefix="/stocktakes", tags=["Branch - Local Stocktaking"])


@router.post("/records", response_model=StandardResponse[StocktakeRecordResponse])
async def submit_stocktake_count(
    req: SubmitStocktakeRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(None)
) -> StandardResponse[StocktakeRecordResponse]:
    """Ghi nhận số lượng đếm kiểm kê thực tế tại chi nhánh"""
    try:
        record = await StocktakeService.record_stocktake(
            session=db,
            session_id=req.session_id.strip(),
            sku=req.sku.strip(),
            actual_qty=req.actual_qty,
            note=req.note
        )
        await db.commit()
        await db.refresh(record)

        return StandardResponse(
            success=True,
            data=StocktakeRecordResponse(
                record_id=record.record_id,
                session_id=record.session_id,
                sku=record.sku,
                system_qty=record.system_qty,
                actual_qty=record.actual_qty,
                diff_qty=record.diff_qty,
                note=record.note,
                created_at=record.created_at
            )
        )
    except Exception as e:
        await db.rollback()
        return StandardResponse(success=False, error=f"Lỗi kiểm kê: {str(e)}")


@router.get("/records", response_model=StandardResponse[list[StocktakeRecordResponse]])
async def list_stocktake_records(
    session_id: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> StandardResponse[list[StocktakeRecordResponse]]:
    """Tra cứu các bản ghi kiểm kê tại chi nhánh"""
    stmt = select(StocktakeRecord).order_by(StocktakeRecord.created_at.desc())
    if session_id:
        stmt = stmt.where(StocktakeRecord.session_id == session_id.strip())

    res = await db.execute(stmt)
    records = res.scalars().all()

    data = [
        StocktakeRecordResponse(
            record_id=r.record_id,
            session_id=r.session_id,
            sku=r.sku,
            system_qty=r.system_qty,
            actual_qty=r.actual_qty,
            diff_qty=r.diff_qty,
            note=r.note,
            created_at=r.created_at
        )
        for r in records
    ]
    return StandardResponse(success=True, data=data)
