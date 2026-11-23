# backend/branch_service/models.py
import os
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from .database import Base


def _default_branch() -> str:
    return os.getenv("BRANCH_CODE", "HN")


# ==============================================================================
# CÁC BẢNG DANH MỤC CHUNG NHÂN BẢN TỪ TRUNG TÂM (MASTER REPLICAS)
# ==============================================================================

class LocalBranch(Base):
    """Bảng 1 (Bản sao tại Chi nhánh): CHI_NHANH"""
    __tablename__ = "Branches"
    branch_code = Column(String(20), primary_key=True)
    branch_name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=True)
    site_type = Column(String(20), default="CHI_NHANH", nullable=False)
    status = Column(String(20), default="ACTIVE", nullable=False)


class LocalCategory(Base):
    """Bảng 2 (Bản sao tại Chi nhánh): DANH_MUC_SP"""
    __tablename__ = "Product_Categories"
    category_id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)


class LocalProduct(Base):
    """Bảng 3 (Bản sao tại Chi nhánh): SAN_PHAM"""
    __tablename__ = "Local_Products"
    sku = Column(String(50), primary_key=True)
    barcode = Column(String(100), unique=True, index=True, nullable=True)
    product_name = Column(String(200), nullable=False)
    category_id = Column(Integer, nullable=True, default=1)
    unit = Column(String(50), default="Chiếc")
    cost_price = Column(Float, default=0.0)
    price = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Account(Base):
    """Bảng 4 (Đồng bộ về Chi nhánh để đăng nhập tự trị khi đứt mạng WAN): TAI_KHOAN"""
    __tablename__ = "Accounts"
    account_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(30), nullable=False)
    branch_code = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==============================================================================
# CÁC BẢNG NGHIỆP VỤ CỤC BỘ (PHÂN MẢNH NGANG THEO ma_chi_nhanh)
# ==============================================================================

class LocalInventory(Base):
    """Bảng 5: TON_KHO - Tồn kho cục bộ phân mảnh ngang tại Site Chi nhánh"""
    __tablename__ = "Local_Inventory"
    sku = Column(String(50), primary_key=True)
    branch_code = Column(String(20), default=_default_branch, nullable=False)  # Shard Key: HN | HCM
    available_qty = Column(Integer, default=0, nullable=False)
    reserved_qty = Column(Integer, default=0, nullable=False)
    min_threshold = Column(Integer, default=10, nullable=False)
    max_threshold = Column(Integer, default=200, nullable=False)
    version = Column(Integer, default=1, nullable=False)  # Khóa lạc quan (Optimistic Locking)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WarehouseTransaction(Base):
    """Bảng 6: GIAO_DICH_KHO - Phiếu Nhập / Xuất / Kiểm kê / Chuyển kho"""
    __tablename__ = "Warehouse_Transactions"
    transaction_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    branch_code = Column(String(20), default=_default_branch, nullable=False)
    receipt_code = Column(String(50), unique=True, nullable=False)  # VD: NK-HN-20261123-A1B2
    # NHAP_KHO | XUAT_KHO | KIEM_KE | CHUYEN_KHO_DI | CHUYEN_KHO_DEN
    transaction_type = Column(String(30), nullable=False)
    counterpart_branch = Column(String(20), nullable=True)
    saga_transfer_id = Column(String(64), index=True, nullable=True)
    created_by = Column(String(64), nullable=True)
    # CHO_XU_LY | HOAN_THANH | DA_HUY | SAGA_ROLLBACK
    status = Column(String(30), default="HOAN_THANH", nullable=False)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WarehouseTransactionDetail(Base):
    """Bảng 7: CHI_TIET_GIAO_DICH - Chi tiết mặt hàng trong phiếu kho (Phân mảnh dẫn xuất)"""
    __tablename__ = "Warehouse_Transaction_Details"
    detail_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String(64), ForeignKey("Warehouse_Transactions.transaction_id"), nullable=False)
    branch_code = Column(String(20), default=_default_branch, nullable=False)
    sku = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)  # Dương (+) nếu nhập, Âm (-) nếu xuất
    post_transaction_balance = Column(Integer, nullable=False)  # Snapshot tồn kho ngay sau giao dịch


class CustomerOrder(Base):
    """Bảng 8: DON_HANG - Đơn đặt hàng của khách hàng/đại lý tại Chi nhánh"""
    __tablename__ = "Customer_Orders"
    order_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    branch_code = Column(String(20), default=_default_branch, nullable=False)
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=True)
    total_amount = Column(Float, default=0.0, nullable=False)
    # MOI_TAO | DANG_SOAN_HANG | DA_XUAT_KHO | DA_HUY
    status = Column(String(30), default="DA_XUAT_KHO", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CustomerOrderDetail(Base):
    """Bảng 9: CHI_TIET_DON_HANG - Chi tiết sản phẩm trong Đơn hàng"""
    __tablename__ = "Customer_Order_Details"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(64), ForeignKey("Customer_Orders.order_id"), nullable=False)
    sku = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)


# ==============================================================================
# CÁC BẢNG SỔ CÁI, KIỆN HÀNG SAGA & HÀNG ĐỢI OUTBOX
# ==============================================================================

class StockLedger(Base):
    """Sổ cái kiểm toán chi tiết & Idempotency Key"""
    __tablename__ = "Stock_Ledger"
    ledger_id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(100), unique=True, nullable=False)  # Idempotency Key
    sku = Column(String(50), nullable=False)
    change_type = Column(String(30), nullable=False)
    quantity = Column(Integer, nullable=False)
    partner_name = Column(String(100), nullable=True)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class IncomingTransfer(Base):
    """Kiện hàng điều chuyển Saga đang chờ duyệt nhập tại Chi nhánh đích"""
    __tablename__ = "Incoming_Transfers"
    transfer_id = Column(String(64), primary_key=True)
    source_branch = Column(String(20), nullable=False)
    dest_branch = Column(String(20), nullable=False)
    sku = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(30), default="WAITING_CONFIRMATION")
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OutboxEvent(Base):
    """Bảng 10: SU_KIEN_DONG_BO - Hàng đợi Transactional Outbox Pattern"""
    __tablename__ = "Outbox_Events"
    event_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    branch_code = Column(String(20), default=_default_branch, nullable=False)
    # SYNC_INVENTORY | SYNC_TRANSACTION | SAGA_STOCK_TRANSFER
    event_type = Column(String(50), default="SYNC_INVENTORY", nullable=False)
    routing_key = Column(String(100), nullable=False)
    payload = Column(String, nullable=False)
    # PENDING | PROCESSING | COMPLETED | FAILED
    delivery_status = Column(String(20), default="PENDING", nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
