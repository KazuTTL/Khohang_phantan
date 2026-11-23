# backend/hq_service/models.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from .database import Base


class Branch(Base):
    """Bảng 1: CHI_NHANH - Danh mục Chi nhánh / Kho (Master)"""
    __tablename__ = "Branches"
    branch_code = Column(String(20), primary_key=True)
    branch_name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=True)
    site_type = Column(String(20), default="CHI_NHANH", nullable=False)  # TRUNG_TAM | CHI_NHANH
    status = Column(String(20), default="ACTIVE", nullable=False)  # ACTIVE | MAINTENANCE | INACTIVE
    api_base_url = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)


class ProductCategory(Base):
    """Bảng 2: DANH_MUC_SP - Danh mục Ngành hàng (Master)"""
    __tablename__ = "Product_Categories"
    category_id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)


class Product(Base):
    """Bảng 3: SAN_PHAM - Danh mục Hàng hóa chung (Master)"""
    __tablename__ = "Products"
    sku = Column(String(50), primary_key=True)
    barcode = Column(String(100), unique=True, index=True, nullable=True)
    product_name = Column(String(200), nullable=False)
    category_id = Column(Integer, ForeignKey("Product_Categories.category_id"), nullable=True, default=1)
    unit = Column(String(50), default="Chiếc")
    cost_price = Column(Float, default=0.0)
    price = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Account(Base):
    """Bảng 4: TAI_KHOAN - Danh mục Tài khoản người dùng (Quản lý tập trung tại HQ, đồng bộ về Site)"""
    __tablename__ = "Accounts"
    account_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(30), nullable=False)  # HQ_MANAGER | BRANCH_MANAGER | BRANCH_STAFF
    branch_code = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class GlobalInventorySnapshot(Base):
    """Bảng 11: TONG_HOP_TON_KHO - Báo cáo tổng hợp tồn kho toàn hệ thống tại Trung tâm"""
    __tablename__ = "Global_Inventory_Snapshot"
    branch_code = Column(String(20), primary_key=True)
    sku = Column(String(50), primary_key=True)
    available_qty = Column(Integer, default=0)
    reserved_qty = Column(Integer, default=0)
    last_synced_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TransferOrder(Base):
    """Bảng Điều phối Giao dịch Phân tán Saga (Orchestrator)"""
    __tablename__ = "Transfer_Orders"
    transfer_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_branch = Column(String(20), nullable=False)
    dest_branch = Column(String(20), nullable=False)
    sku = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    # INITIATED | RESERVED_IN_TRANSIT | COMPLETED | COMPENSATING | CANCELLED_ROLLED_BACK | FAILED
    saga_status = Column(String(40), default="INITIATED")
    error_reason = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TransferRequest(Base):
    """Bảng Yêu cầu Xin điều chuyển hàng từ Chi nhánh gửi lên Trụ sở (Pull Transfer Request)"""
    __tablename__ = "Transfer_Requests"
    request_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    requesting_branch = Column(String(20), nullable=False)
    suggested_source_branch = Column(String(20), nullable=False)
    sku = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    reason = Column(String(500), nullable=True)
    requested_by = Column(String(64), default="branch_user")
    # PENDING | APPROVED | REJECTED
    status = Column(String(20), default="PENDING", nullable=False)
    transfer_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
