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
    category: Optional[str] = "Điện tử"
    initial_stock: Optional[Dict[str, int]] = Field(default_factory=dict, description="Tồn đầu kỳ theo chi nhánh {'HN': 50, 'HCM': 30}")
    min_threshold: int = Field(default=10, description="Định mức tồn tối thiểu")
    max_threshold: int = Field(default=200, description="Định mức tồn tối đa")

# HQ: Cập nhật thông tin sản phẩm
class ProductUpdate(BaseModel):
    product_name: str
    unit: str = "Chiếc"
    price: float = 0.0
    category: Optional[str] = None
    min_threshold: Optional[int] = None
    max_threshold: Optional[int] = None
    branch_stock: Optional[Dict[str, int]] = Field(default=None, description="Số lượng tồn kho cập nhật cho từng chi nhánh, ví dụ: {'HN': 45, 'HCM': 25}")

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

# Branch: Cập nhật định mức tồn kho
class StockThresholdUpdate(BaseModel):
    min_threshold: int = Field(ge=0, description="Định mức tối thiểu")
    max_threshold: int = Field(gt=0, description="Định mức tối đa")

# Branch: Phiếu kiểm kê kho
class StockAuditRequest(BaseModel):
    sku: str
    actual_qty: int = Field(ge=0, description="Số lượng kiểm kê thực tế tại kệ")
    note: Optional[str] = "Kiểm kê định kỳ"

# Branch: Điều chỉnh xuất nhập tại chỗ (Local Autonomy)
class LocalStockAdjust(BaseModel):
    sku: str
    change_type: str # LOCAL_IN, LOCAL_OUT
    quantity: int = Field(gt=0, description="Số lượng điều chỉnh phải lớn hơn 0")
    reference_id: Optional[str] = None # Idempotency key
    partner_name: Optional[str] = None # Nhà cung cấp hoặc Khách hàng
    note: Optional[str] = None # Ghi chú hóa đơn / phiếu xuất nhập

# Xác thực người dùng (Auth)
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

# Chi nhánh đích: Xác nhận hoặc từ chối nhận hàng
class TransferDecisionRequest(BaseModel):
    reason: Optional[str] = None
