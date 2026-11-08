# backend/shared/event_schemas.py
from datetime import datetime, timezone
import uuid
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T")


class EventEnvelope(BaseModel, Generic[T]):
    """
    Standard Message Envelope for all asynchronous RabbitMQ messages.
    Tuân thủ nguyên tắc Contract-First và At-Least-Once Delivery.
    """
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    source: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: T


# ============================================================================
# COMMAND PAYLOADS (HQ -> Branch)
# ============================================================================

class CmdReserveStockPayload(BaseModel):
    """Lệnh giữ hàng tại kho xuất trong luồng Saga Phase 1"""
    transfer_id: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int = Field(gt=0)


class CmdReleaseStockPayload(BaseModel):
    """Lệnh bù trừ (Compensating Transaction) giải phóng hàng giữ khi Saga thất bại"""
    transfer_id: str
    source_branch: str
    sku: str
    quantity: int = Field(gt=0)
    reason: str = "COMPENSATION_TRIGGERED"


class CmdImportTransferPayload(BaseModel):
    """Lệnh giao hàng tới kho đích để thực hiện nhập kho trong Phase 2"""
    transfer_id: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int = Field(gt=0)


class CmdSyncCatalogPayload(BaseModel):
    """Lệnh đồng bộ danh mục sản phẩm từ HQ xuống Chi nhánh"""
    sku: str
    product_name: str
    unit: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# EVENT PAYLOADS (Branch -> HQ, Branch -> Cluster)
# ============================================================================

class EvtStockReservedPayload(BaseModel):
    """Sự kiện xác nhận đã giữ hàng thành công tại kho xuất"""
    transfer_id: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int
    available_qty: int
    reserved_qty: int


class EvtReserveFailedPayload(BaseModel):
    """Sự kiện báo lỗi giữ hàng (kho không đủ hàng khả dụng)"""
    transfer_id: str
    source_branch: str
    sku: str
    quantity: int
    reason: str


class EvtTransferCompletedPayload(BaseModel):
    """Sự kiện xác nhận kho đích đã nhận và nhập hàng thành công (Saga Hoàn tất)"""
    transfer_id: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int


class EvtTransferRejectedPayload(BaseModel):
    """Sự kiện kho đích từ chối tiếp nhận (Kích hoạt luồng bù trừ Rollback)"""
    transfer_id: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int
    reason: str


class EvtStockReleasedPayload(BaseModel):
    """Sự kiện kho xuất xác nhận đã thực thi xong giao dịch bù trừ (Rollback hoàn tất)"""
    transfer_id: str
    source_branch: str
    sku: str
    quantity: int


class EvtInventoryUpdatedPayload(BaseModel):
    """Sự kiện cập nhật biến động tồn kho cục bộ lên Snapshot toàn cục tại HQ"""
    branch_code: str
    sku: str
    available_qty: int
    reserved_qty: int
    change_type: str
    reference_id: str | None = None


class EvtCatalogUpdatedPayload(BaseModel):
    """Sự kiện danh mục sản phẩm chuẩn tại HQ được cập nhật"""
    sku: str
    product_name: str
    unit: str
    base_price: float = 0.0
    is_active: bool = True
