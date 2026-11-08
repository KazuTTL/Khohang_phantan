# backend/hq_service/models.py
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer,
    Numeric, PrimaryKeyConstraint, String, Text
)
from hq_service.database import Base


class Branch(Base):
    __tablename__ = "Branches"

    branch_code = Column(String(20), primary_key=True, index=True)
    branch_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class Product(Base):
    __tablename__ = "Products"

    sku = Column(String(50), primary_key=True, index=True)
    product_name = Column(String(200), nullable=False)
    unit = Column(String(50), nullable=False)
    base_price = Column(Numeric(18, 2), default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class GlobalInventorySnapshot(Base):
    __tablename__ = "Global_Inventory_Snapshot"

    branch_code = Column(String(20), ForeignKey("Branches.branch_code"), nullable=False)
    sku = Column(String(50), ForeignKey("Products.sku"), nullable=False)
    available_qty = Column(Integer, default=0, nullable=False)
    reserved_qty = Column(Integer, default=0, nullable=False)
    last_synced_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("branch_code", "sku", name="pk_global_inventory"),
    )


class TransferOrder(Base):
    __tablename__ = "Transfer_Orders"

    transfer_id = Column(String(50), primary_key=True, index=True)
    source_branch = Column(String(20), nullable=False)
    dest_branch = Column(String(20), nullable=False)
    sku = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    # INITIATED | RESERVED_IN_TRANSIT | COMPLETED | COMPENSATING | ROLLED_BACK | FAILED
    saga_status = Column(String(30), nullable=False, default="INITIATED")
    error_reason = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class StocktakeSession(Base):
    __tablename__ = "Stocktake_Sessions"

    session_id = Column(String(50), primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    status = Column(String(30), default="OPEN", nullable=False) # OPEN | CLOSED | CANCELLED
    created_by = Column(String(50), default="SYSTEM", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    closed_at = Column(DateTime, nullable=True)


class OutboxMessage(Base):
    __tablename__ = "Outbox_Messages"

    message_id = Column(String(50), primary_key=True)
    event_type = Column(String(100), nullable=False)
    routing_key = Column(String(100), nullable=False)
    payload = Column(Text, nullable=False) # JSON serialized
    status = Column(String(20), default="PENDING", nullable=False, index=True) # PENDING | PROCESSED | FAILED
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    processed_at = Column(DateTime, nullable=True)


class InboxMessage(Base):
    __tablename__ = "Inbox_Messages"

    message_id = Column(String(50), nullable=False)
    consumer_name = Column(String(100), nullable=False)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("message_id", "consumer_name", name="pk_hq_inbox"),
    )
