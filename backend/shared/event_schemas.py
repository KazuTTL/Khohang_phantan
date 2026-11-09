# backend/shared/event_schemas.py
import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field


# ============================================================================
# EVENT ENVELOPE
# ============================================================================

class Envelope(BaseModel):
    """
    Chuẩn Message Envelope cho mọi message gửi qua RabbitMQ Topic Exchange.
    Bảo đảm tính Contract-First và khả năng tương thích ngược.
    """
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any]


# ============================================================================
# DATA MODELS
# ============================================================================

class ApproveRequestData(BaseModel):
    """Dữ liệu yêu cầu phê duyệt xuất kho gửi tới chi nhánh nguồn"""
    transfer_id: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int = Field(gt=0)


class ConfirmReceiveData(BaseModel):
    """Dữ liệu yêu cầu tiếp nhận và kiểm đếm gửi tới chi nhánh đích"""
    transfer_id: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int = Field(gt=0)


class ReleaseStockData(BaseModel):
    """Dữ liệu lệnh bù trừ hoàn trả hàng gửi tới kho nguồn"""
    transfer_id: str
    source_branch: str
    sku: str
    quantity: int = Field(gt=0)
    reason: str = "COMPENSATION_TRIGGERED"


class SourceApprovedData(BaseModel):
    """Sự kiện xác nhận kho nguồn đã duyệt xuất và giữ hàng thành công"""
    transfer_id: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int
    approved_by: str


class SourceRejectedData(BaseModel):
    """Sự kiện kho nguồn từ chối xuất kho"""
    transfer_id: str
    reason: str
    rejected_by: str


class DestApprovedData(BaseModel):
    """Sự kiện kho đích đã phê duyệt và nhập kho thành công"""
    transfer_id: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int
    received_qty: int
    approved_by: str


class DestRejectedData(BaseModel):
    """Sự kiện kho đích từ chối nhận hàng (kích hoạt bù trừ)"""
    transfer_id: str
    reason: str
    rejected_by: str


class ReserveFailedData(BaseModel):
    """Sự kiện báo lỗi giữ hàng (kho nguồn không đủ tồn)"""
    transfer_id: str
    reason: str
    source_branch: str
    sku: str
    quantity: int


class InventoryUpdatedData(BaseModel):
    """Sự kiện cập nhật biến động tồn kho gửi về HQ để cập nhật Snapshot"""
    branch_code: str
    sku: str
    available_qty: int
    reserved_qty: int


class CatalogSyncData(BaseModel):
    """Sự kiện đồng bộ danh mục sản phẩm từ HQ xuống các chi nhánh"""
    sku: str
    product_name: str
    unit: str
    action: Literal["UPSERT", "DELETE"] = "UPSERT"


class StocktakeItemSchema(BaseModel):
    sku: str
    system_qty_at_start: int
    counted_qty: int
    variance_qty: int
    variance_reason: str | None = None
    adjusted: bool = True


class StocktakeApprovedData(BaseModel):
    """Sự kiện phê duyệt kiểm kê gửi về HQ chốt sổ toàn hệ thống"""
    session_id: str
    session_code: str
    branch_code: str
    total_skus_counted: int
    total_variance_abs: int
    items: list[StocktakeItemSchema] = Field(default_factory=list)


# Tương thích ngược (Backward compatibility aliases)
EventEnvelope = Envelope
EvtInventoryUpdatedPayload = InventoryUpdatedData
EvtCatalogUpdatedPayload = CatalogSyncData

