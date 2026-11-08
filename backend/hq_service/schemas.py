# backend/hq_service/schemas.py
from datetime import datetime
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    """Chuẩn phản hồi thống nhất toàn hệ thống: {"success": bool, "data": ..., "error": ...}"""
    success: bool
    data: T | None = None
    error: str | None = None


# Branch Schemas
class CreateBranchRequest(BaseModel):
    branch_code: str = Field(..., max_length=20)
    branch_name: str = Field(..., max_length=100)


class BranchResponse(BaseModel):
    branch_code: str
    branch_name: str
    is_active: bool
    created_at: datetime


# Catalog Schemas
class CreateProductRequest(BaseModel):
    sku: str = Field(..., max_length=50)
    product_name: str = Field(..., max_length=200)
    unit: str = Field(..., max_length=50)
    base_price: float = Field(default=0.0, ge=0)


class ProductResponse(BaseModel):
    sku: str
    product_name: str
    unit: str
    base_price: float
    is_active: bool
    updated_at: datetime


# Global Inventory Schemas
class GlobalStockItem(BaseModel):
    branch_code: str
    branch_name: str | None = None
    sku: str
    product_name: str | None = None
    unit: str | None = None
    available_qty: int
    reserved_qty: int
    last_synced_at: datetime


# Transfer Schemas
class CreateTransferRequest(BaseModel):
    source_branch: str = Field(..., max_length=20)
    dest_branch: str = Field(..., max_length=20)
    sku: str = Field(..., max_length=50)
    quantity: int = Field(..., gt=0)


class TransferResponse(BaseModel):
    transfer_id: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int
    saga_status: str
    error_reason: str | None = None
    created_at: datetime
    updated_at: datetime


# Stocktake Schemas
class CreateStocktakeRequest(BaseModel):
    title: str = Field(..., max_length=200)
    created_by: str = "SYSTEM"


class StocktakeResponse(BaseModel):
    session_id: str
    title: str
    status: str
    created_by: str
    created_at: datetime
    closed_at: datetime | None = None
