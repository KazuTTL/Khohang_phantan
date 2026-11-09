# backend/branch_service/models.py
import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer,
    Numeric, PrimaryKeyConstraint, String, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from branch_service.database import Base


# ============================================================================
# 1. ENUMS (Roles, Transaction Types, Statuses)
# ============================================================================

class UserRole(str, enum.Enum):
    STOCK_KEEPER = "STOCK_KEEPER"       # Tạo phiếu nhập NCC, xác nhận nhận hàng vật lý
    SALES = "SALES"                     # Tạo phiếu nhập trả hàng (khách trả)
    AUDITOR = "AUDITOR"                 # Tạo và đếm phiếu kiểm kê
    BRANCH_MANAGER = "BRANCH_MANAGER"   # Duyệt MỌI phiếu tại chi nhánh


class StockChangeType(str, enum.Enum):
    LOCAL_IN = "LOCAL_IN"
    LOCAL_OUT = "LOCAL_OUT"
    RESERVE = "RESERVE"
    COMMIT_OUT = "COMMIT_OUT"
    RELEASE_RESERVE = "RELEASE_RESERVE"
    TRANSFER_IN = "TRANSFER_IN"
    STOCKTAKE_ADJUST = "STOCKTAKE_ADJUST"
    PURCHASE_RECEIVE = "PURCHASE_RECEIVE"


class TransferType(str, enum.Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class TransferApprovalStatus(str, enum.Enum):
    AWAITING_SOURCE_APPROVAL = "AWAITING_SOURCE_APPROVAL"
    SOURCE_APPROVED = "SOURCE_APPROVED"
    SOURCE_REJECTED = "SOURCE_REJECTED"
    AWAITING_DEST_APPROVAL = "AWAITING_DEST_APPROVAL"
    DEST_APPROVED = "DEST_APPROVED"
    DEST_REJECTED = "DEST_REJECTED"
    CANCELLED = "CANCELLED"


class PurchaseReceiptStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RECEIVED = "RECEIVED"
    FINALIZED = "FINALIZED"
    CANCELLED = "CANCELLED"


class PurchaseItemStatus(str, enum.Enum):
    PENDING = "PENDING"
    RECEIVED = "RECEIVED"
    SHORTAGE = "SHORTAGE"
    OVERAGE = "OVERAGE"


class StocktakeStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    COUNTING = "COUNTING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    FINALIZED = "FINALIZED"


class StocktakeScope(str, enum.Enum):
    FULL = "FULL"
    BY_SKU = "BY_SKU"


class StocktakeItemStatus(str, enum.Enum):
    PENDING = "PENDING"
    COUNTED = "COUNTED"
    ADJUSTED = "ADJUSTED"


# ============================================================================
# 2. TABLES & MODELS
# ============================================================================

class BranchUser(Base):
    """Users tại branch: STOCK_KEEPER, SALES, AUDITOR, BRANCH_MANAGER"""
    __tablename__ = "Branch_Users"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class LocalProduct(Base):
    """Danh mục sản phẩm (đồng bộ từ HQ)"""
    __tablename__ = "Local_Products"

    sku: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)


class LocalInventory(Base):
    """Tồn kho cục bộ với version phục vụ concurrency control"""
    __tablename__ = "Local_Inventory"

    sku: Mapped[str] = mapped_column(String(50), ForeignKey("Local_Products.sku"), primary_key=True)
    available_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class StockLedger(Base):
    """Lịch sử biến động kho + Idempotency reference_id UNIQUE"""
    __tablename__ = "Stock_Ledger"

    ledger_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class OutboxEvent(Base):
    """Bảng Outbox_Events cho Transactional Outbox"""
    __tablename__ = "Outbox_Events"

    event_id: Mapped[str] = mapped_column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    routing_key: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class InboxEvent(Base):
    """Bảng Inbox_Events phục vụ Idempotent Consumer"""
    __tablename__ = "Inbox_Events"

    message_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class IncomingTransfer(Base):
    """Điều chuyển (local mirror phục vụ quy trình duyệt 3 cấp)"""
    __tablename__ = "Incoming_Transfers"

    transfer_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    transfer_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False) # INBOUND | OUTBOUND
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    source_branch: Mapped[str] = mapped_column(String(20), nullable=False)
    dest_branch: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reject_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    received_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class Supplier(Base):
    """Nhà cung cấp hàng hóa"""
    __tablename__ = "Suppliers"

    supplier_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PurchaseReceipt(Base):
    """Phiếu nhập hàng từ Nhà Cung Cấp (NCC)"""
    __tablename__ = "Purchase_Receipts"

    receipt_id: Mapped[str] = mapped_column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    receipt_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    branch_code: Mapped[str] = mapped_column(String(20), nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(50), ForeignKey("Suppliers.supplier_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    received_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    items: Mapped[list["PurchaseReceiptItem"]] = relationship("PurchaseReceiptItem", back_populates="receipt", cascade="all, delete-orphan")


class PurchaseReceiptItem(Base):
    """Chi tiết sản phẩm trong phiếu nhập NCC"""
    __tablename__ = "Purchase_Receipt_Items"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_id: Mapped[str] = mapped_column(String(50), ForeignKey("Purchase_Receipts.receipt_id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("Local_Products.sku"), nullable=False)
    expected_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    received_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)

    receipt: Mapped["PurchaseReceipt"] = relationship("PurchaseReceipt", back_populates="items")


class StocktakeSession(Base):
    """Phiên kiểm kê kho hàng tại Chi nhánh"""
    __tablename__ = "Stocktake_Sessions"

    session_id: Mapped[str] = mapped_column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    branch_code: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False) # FULL | BY_SKU
    scope_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str] = mapped_column(String(50), nullable=False)
    counted_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    finalized_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    counting_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    items: Mapped[list["StocktakeItem"]] = relationship("StocktakeItem", back_populates="session", cascade="all, delete-orphan")


class StocktakeItem(Base):
    """Chi tiết từng mặt hàng trong phiên kiểm kê"""
    __tablename__ = "Stocktake_Items"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(50), ForeignKey("Stocktake_Sessions.session_id"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("Local_Products.sku"), nullable=False)
    system_qty_at_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    counted_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variance_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variance_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    counted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    adjusted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    session: Mapped["StocktakeSession"] = relationship("StocktakeSession", back_populates="items")

    __table_args__ = (
        UniqueConstraint("session_id", "sku", name="uq_stocktake_session_sku"),
    )


class StocktakeAuditLog(Base):
    """Nhật ký kiểm toán truy vết các thao tác trên phiên kiểm kê"""
    __tablename__ = "Stocktake_Audit_Log"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    performed_by: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class StockFreezeLog(Base):
    """Bản ghi đóng băng hàng hóa trong đợt kiểm kê"""
    __tablename__ = "Stock_Freeze_Log"

    freeze_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sku: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    frozen_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
