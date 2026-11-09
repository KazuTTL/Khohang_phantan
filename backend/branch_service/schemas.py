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


# ============================================================================
# Local Inventory Schemas
# ============================================================================

class AdjustStockRequest(BaseModel):
    sku: str = Field(..., max_length=50)
    change_type: str = Field(..., description="LOCAL_IN (Nhập kho tại chỗ) hoặc LOCAL_OUT (Xuất bán)")
    quantity: int = Field(..., gt=0)
    reason: str | None = None


class AdjustStockResponse(BaseModel):
    new_available: int
    ledger_id: int
    message_id: str
    available_qty: int | None = None
    reference_id: str | None = None
    message: str | None = None


class LocalInventoryItem(BaseModel):
    sku: str
    product_name: str
    unit: str
    available_qty: int
    reserved_qty: int
    version: int
    updated_at: datetime


class StockLedgerItem(BaseModel):
    ledger_id: int
    reference_id: str
    sku: str
    change_type: str
    quantity: int
    created_at: datetime


# ============================================================================
# Supplier Schemas
# ============================================================================

class SupplierCreate(BaseModel):
    supplier_id: str = Field(..., max_length=50)
    supplier_name: str = Field(..., max_length=200)
    tax_code: str | None = Field(None, max_length=20)
    contact_phone: str | None = Field(None, max_length=20)
    is_active: bool = True


class SupplierResponse(BaseModel):
    supplier_id: str
    supplier_name: str
    tax_code: str | None = None
    contact_phone: str | None = None
    is_active: bool


# ============================================================================
# Purchase Receipt Schemas
# ============================================================================

class PurchaseReceiptItemInput(BaseModel):
    sku: str = Field(..., max_length=50)
    expected_qty: int = Field(..., gt=0)
    unit_price: float = Field(default=0.0, ge=0.0)


class PurchaseReceiptCreate(BaseModel):
    supplier_id: str = Field(..., max_length=50)
    invoice_number: str | None = Field(None, max_length=50)
    note: str | None = Field(None, max_length=500)
    items: list[PurchaseReceiptItemInput] = Field(..., min_length=1)


class PurchaseReceiptItemResponse(BaseModel):
    item_id: int
    receipt_id: str
    sku: str
    expected_qty: int
    received_qty: int | None = None
    unit_price: float | None = None
    status: str


class PurchaseReceiptResponse(BaseModel):
    receipt_id: str
    receipt_code: str
    branch_code: str
    supplier_id: str
    status: str
    created_by: str
    approved_by: str | None = None
    received_by: str | None = None
    invoice_number: str | None = None
    total_amount: float | None = None
    note: str | None = None
    created_at: datetime
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    received_at: datetime | None = None
    reject_reason: str | None = None
    items: list[PurchaseReceiptItemResponse] = []


class RejectReceiptRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)


class ReceiveReceiptItemInput(BaseModel):
    sku: str = Field(..., max_length=50)
    received_qty: int = Field(..., ge=0)


class ReceiveReceiptRequest(BaseModel):
    items: list[ReceiveReceiptItemInput] = Field(..., min_length=1)


# ============================================================================
# Transfer Schemas
# ============================================================================

class TransferItemResponse(BaseModel):
    transfer_id: str
    transfer_code: str | None = None
    type: str
    sku: str
    quantity: int
    source_branch: str
    dest_branch: str
    status: str
    reject_reason: str | None = None
    received_qty: int | None = None
    created_at: datetime
    updated_at: datetime


class RejectTransferRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500, description="Lý do từ chối")


# ============================================================================
# Stocktake Schemas
# ============================================================================

class StocktakeCreate(BaseModel):
    scope_type: str = Field(default="FULL", description="FULL hoặc BY_SKU")
    scope_sku_list: list[str] | None = None
    note: str | None = None


class StocktakeCountItem(BaseModel):
    sku: str = Field(..., max_length=50)
    actual_qty: int = Field(..., ge=0)
    variance_reason: str | None = None


class StocktakeBatchCountRequest(BaseModel):
    items: list[StocktakeCountItem] = Field(..., min_length=1)


class StocktakeItemResponse(BaseModel):
    item_id: int
    session_id: str
    sku: str
    system_qty_at_start: int
    counted_qty: int | None = None
    variance_qty: int | None = None
    variance_reason: str | None = None
    status: str
    counted_at: datetime | None = None
    adjusted_at: datetime | None = None


class StocktakeSessionResponse(BaseModel):
    session_id: str
    session_code: str
    branch_code: str
    status: str
    scope_type: str
    scope_note: str | None = None
    created_by: str
    counted_by: str | None = None
    approved_by: str | None = None
    finalized_by: str | None = None
    created_at: datetime
    counting_started_at: datetime | None = None
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    cancelled_at: datetime | None = None
    finalized_at: datetime | None = None
    cancel_reason: str | None = None
    reject_reason: str | None = None
    items: list[StocktakeItemResponse] = []


class StocktakeRejectRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)


# ============================================================================
# User Schemas
# ============================================================================

class UserResponse(BaseModel):
    user_id: str
    full_name: str
    role: str
    is_active: bool
    branch_code: str
