# backend/hq_service/models.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from .database import Base

class Branch(Base):
    __tablename__ = "Branches"
    branch_code = Column(String(20), primary_key=True)
    branch_name = Column(String(100), nullable=False)
    api_base_url = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)

class Product(Base):
    __tablename__ = "Products"
    sku = Column(String(50), primary_key=True)
    product_name = Column(String(200), nullable=False)
    unit = Column(String(50), default="Chiếc")
    price = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class GlobalInventorySnapshot(Base):
    __tablename__ = "Global_Inventory_Snapshot"
    branch_code = Column(String(20), primary_key=True)
    sku = Column(String(50), primary_key=True)
    available_qty = Column(Integer, default=0)
    reserved_qty = Column(Integer, default=0)
    last_synced_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TransferOrder(Base):
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
