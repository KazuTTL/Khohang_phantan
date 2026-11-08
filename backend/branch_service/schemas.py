# backend/branch_service/schemas.py
from datetime import datetime
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    """Chuẩn phản hồi thống nhất: {"success": bool, "data": ..., "error": ...}"""
    success: bool
    data: T | None = None
    error: str | None = None


class AdjustStockRequest(BaseModel):
    sku: str = Field(..., max_length=50)
    change_type: str = Field(..., description="LOCAL_IN (Nhập kho bán lẻ) hoặc LOCAL_OUT (Xuất bán tại chỗ)")
    quantity: int = Field(..., gt=0)
    idempotency_key: str | None = None
    note: str | None = None


class AdjustStockResponse(BaseModel):
    sku: str
    change_type: str
    quantity: int
    available_qty: int
    reserved_qty: int
    reference_id: str


class LocalInventoryItem(BaseModel):
    sku: str
    product_name: str
    unit: str
    available_qty: int
    reserved_qty: int
    updated_at: datetime


class ConfirmTransferRequest(BaseModel):
    transfer_id: str


class RejectTransferRequest(BaseModel):
    transfer_id: str
    reason: str = Field(..., min_length=3, description="Lý do từ chối nhận hàng")


class SubmitStocktakeRequest(BaseModel):
    session_id: str
    sku: str
    actual_qty: int = Field(..., ge=0)
    note: str | None = None


class StocktakeRecordResponse(BaseModel):
    record_id: str
    session_id: str
    sku: str
    system_qty: int
    actual_qty: int
    diff_qty: int
    note: str | None = None
    created_at: datetime
