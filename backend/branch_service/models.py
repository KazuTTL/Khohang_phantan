# backend/branch_service/models.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from .database import Base

class LocalProduct(Base):
    __tablename__ = "Local_Products"
    sku = Column(String(50), primary_key=True)
    product_name = Column(String(200), nullable=False)
    unit = Column(String(50), default="Chiếc")

class LocalInventory(Base):
    __tablename__ = "Local_Inventory"
    sku = Column(String(50), primary_key=True)
    available_qty = Column(Integer, default=0, nullable=False)
    reserved_qty = Column(Integer, default=0, nullable=False)
    min_threshold = Column(Integer, default=10, nullable=False) # Định mức tồn kho tối thiểu
    max_threshold = Column(Integer, default=200, nullable=False) # Định mức tồn kho tối đa
    version = Column(Integer, default=1, nullable=False) # Khóa lạc quan (Optimistic Locking)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StockLedger(Base):
    __tablename__ = "Stock_Ledger"
    ledger_id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(String(100), unique=True, nullable=False) # Idempotency Key
    sku = Column(String(50), nullable=False)
    # LOCAL_IN | LOCAL_OUT | RESERVE | COMMIT_OUT | RELEASE_RESERVE | TRANSFER_IN | AUDIT_ADJUST
    change_type = Column(String(30), nullable=False)
    quantity = Column(Integer, nullable=False)
    partner_name = Column(String(100), nullable=True) # Tên Nhà cung cấp hoặc Khách hàng
    note = Column(String(255), nullable=True) # Ghi chú kiểm kê, mã phiếu
    created_at = Column(DateTime, default=datetime.utcnow)

class IncomingTransfer(Base):
    __tablename__ = "Incoming_Transfers"
    transfer_id = Column(String(64), primary_key=True)
    source_branch = Column(String(20), nullable=False)
    dest_branch = Column(String(20), nullable=False)
    sku = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(30), default="WAITING_CONFIRMATION") # WAITING_CONFIRMATION | CONFIRMED | REJECTED
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OutboxEvent(Base):
    __tablename__ = "Outbox_Events"
    event_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    routing_key = Column(String(100), nullable=False)
    payload = Column(String, nullable=False) # Lưu JSON dạng chuỗi
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
