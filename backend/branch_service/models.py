# backend/branch_service/models.py
from datetime import datetime, timezone
from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer,
    PrimaryKeyConstraint, String, Text
)
from branch_service.database import Base


class LocalProduct(Base):
    __tablename__ = "Local_Products"

    sku = Column(String(50), primary_key=True, index=True)
    product_name = Column(String(200), nullable=False)
    unit = Column(String(50), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class LocalInventory(Base):
    __tablename__ = "Local_Inventory"

    sku = Column(String(50), ForeignKey("Local_Products.sku"), primary_key=True)
    available_qty = Column(Integer, default=0, nullable=False)
    reserved_qty = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class StockLedger(Base):
    __tablename__ = "Stock_Ledger"

    ledger_id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_type = Column(String(50), nullable=False)
    # LOCAL_IN | LOCAL_OUT | SAGA_RESERVE | SAGA_RELEASE | SAGA_OUT | SAGA_IN | STOCKTAKE_ADJUST
    sku = Column(String(50), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    available_after = Column(Integer, nullable=False)
    reserved_after = Column(Integer, nullable=False)
    reference_id = Column(String(100), nullable=True)
    idempotency_key = Column(String(100), unique=True, nullable=True, index=True)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class OutboxMessage(Base):
    __tablename__ = "Outbox_Messages"

    message_id = Column(String(50), primary_key=True)
    event_type = Column(String(100), nullable=False)
    routing_key = Column(String(100), nullable=False)
    payload = Column(Text, nullable=False)
    status = Column(String(20), default="PENDING", nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    processed_at = Column(DateTime, nullable=True)


class InboxMessage(Base):
    __tablename__ = "Inbox_Messages"

    message_id = Column(String(50), nullable=False)
    consumer_name = Column(String(100), nullable=False)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("message_id", "consumer_name", name="pk_branch_inbox"),
    )


class StocktakeRecord(Base):
    __tablename__ = "Stocktake_Records"

    record_id = Column(String(50), primary_key=True)
    session_id = Column(String(50), nullable=False, index=True)
    sku = Column(String(50), ForeignKey("Local_Products.sku"), nullable=False)
    system_qty = Column(Integer, nullable=False)
    actual_qty = Column(Integer, nullable=False)
    diff_qty = Column(Integer, nullable=False)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
