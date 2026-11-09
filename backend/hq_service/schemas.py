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


# ============================================================================
# HQ User Schemas
# ============================================================================

class HQUserResponse(BaseModel):
    user_id: str
    full_name: str
    role: str
    is_active: bool


# ============================================================================
# Branch Schemas
# ============================================================================

class CreateBranchRequest(BaseModel):
    branch_code: str = Field(..., max_length=20)
    branch_name: str = Field(..., max_length=100)
    api_base_url: str = Field(..., max_length=255)


class BranchResponse(BaseModel):
    branch_code: str
    branch_name: str
    api_base_url: str
    is_active: bool
    is_online: bool


# ============================================================================
# Catalog Schemas
# ============================================================================

class CreateProductRequest(BaseModel):
    sku: str = Field(..., max_length=50)
    product_name: str = Field(..., max_length=200)
    unit: str = Field(..., max_length=50)


class UpdateProductRequest(BaseModel):
    product_name: str | None = Field(None, max_length=200)
    unit: str | None = Field(None, max_length=50)


class ProductResponse(BaseModel):
    sku: str
    product_name: str
    unit: str
    is_deleted: bool
    updated_at: datetime


# ============================================================================
# Global Inventory Schemas
# ============================================================================

class GlobalStockItem(BaseModel):
    branch_code: str
    branch_name: str | None = None
    sku: str
    product_name: str | None = None
    unit: str | None = None
    available_qty: int
    reserved_qty: int
    last_synced_at: datetime


# ============================================================================
# Transfer Schemas (Saga Orchestration)
# ============================================================================

class CreateTransferRequest(BaseModel):
    source_branch: str = Field(..., max_length=20)
    dest_branch: str = Field(..., max_length=20)
    sku: str = Field(..., max_length=50)
    quantity: int = Field(..., gt=0)


class RejectTransferRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)


class TransferResponse(BaseModel):
    transfer_id: str
    transfer_code: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int
    saga_status: str
    created_by: str
    hq_approved_by: str | None = None
    source_approved_by: str | None = None
    dest_approved_by: str | None = None
    hq_approved_at: datetime | None = None
    source_approved_at: datetime | None = None
    dest_approved_at: datetime | None = None
    hq_reject_reason: str | None = None
    source_reject_reason: str | None = None
    dest_reject_reason: str | None = None
    error_reason: str | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Global Stocktake Schemas
# ============================================================================

class StocktakeItemGlobalResponse(BaseModel):
    item_id: int
    session_id: str
    sku: str
    system_qty_at_start: int
    counted_qty: int
    variance_qty: int
    variance_reason: str | None = None


class StocktakeSessionGlobalResponse(BaseModel):
    session_id: str
    session_code: str
    branch_code: str
    status: str
    scope_type: str
    total_skus_counted: int
    total_variance_abs: int
    created_by_name: str | None = None
    approved_by_name: str | None = None
    finalized_by_name: str | None = None
    created_at: datetime
    approved_at: datetime | None = None
    finalized_at: datetime | None = None
    last_synced_at: datetime
    items: list[StocktakeItemGlobalResponse] = []
