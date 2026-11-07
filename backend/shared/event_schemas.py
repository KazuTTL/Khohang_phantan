# backend/shared/event_schemas.py
"""
Hợp đồng dữ liệu phân tán (Distributed Event & Command Schemas)
Sử dụng Pydantic để chuẩn hóa định dạng thông điệp giữa HQ, Branch HN, Branch HCM qua RabbitMQ & REST API
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid

# ==============================================================================
# 1. HỢP ĐỒNG THÔNG ĐIỆP RABBITMQ (MESSAGE BROKER CONTRACT)
# ==============================================================================

class TransferMessageData(BaseModel):
    transfer_id: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int = Field(gt=0, description="Số lượng chuyển kho phải lớn hơn 0")
    reason: Optional[str] = None
    extra_payload: Optional[Dict[str, Any]] = None

class RabbitMQMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str # CMD_RESERVE_STOCK, EVT_STOCK_RESERVED, CMD_IMPORT_TRANSFER, etc.
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: TransferMessageData

class InventoryUpdateData(BaseModel):
    branch_code: str
    sku: str
    available_qty: int
    reserved_qty: int
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class InventoryUpdateMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "EVT_INVENTORY_UPDATED"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: InventoryUpdateData

# ==============================================================================
# 2. HỢP ĐỒNG REST API REQUEST/RESPONSE SCHEMAS
# ==============================================================================

# HQ: Tạo sản phẩm mới
class ProductCreate(BaseModel):
    sku: str
    product_name: str
    unit: str = "Chiếc"
    price: float = 0.0

# HQ: Tạo lệnh điều chuyển kho Saga
class TransferOrderCreate(BaseModel):
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int = Field(gt=0, description="Số lượng phải lớn hơn 0")

class TransferOrderResponse(BaseModel):
    transfer_id: str
    source_branch: str
    dest_branch: str
    sku: str
    quantity: int
    saga_status: str
    error_reason: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# Branch: Điều chỉnh xuất nhập tại chỗ (Local Autonomy)
class LocalStockAdjust(BaseModel):
    sku: str
    change_type: str # LOCAL_IN, LOCAL_OUT
    quantity: int = Field(gt=0, description="Số lượng điều chỉnh phải lớn hơn 0")
    reference_id: Optional[str] = None # Idempotency key

# Chi nhánh đích: Xác nhận hoặc từ chối nhận hàng
class TransferDecisionRequest(BaseModel):
    reason: Optional[str] = None
