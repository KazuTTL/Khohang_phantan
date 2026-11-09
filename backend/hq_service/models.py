# backend/hq_service/models.py
import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer,
    Numeric, PrimaryKeyConstraint, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hq_service.database import Base


# ============================================================================
# 1. ENUMS
# ============================================================================

class HQUserRole(str, enum.Enum):
    HQ_STAFF = "HQ_STAFF"
    HQ_MANAGER = "HQ_MANAGER"
    HQ_AUDITOR = "HQ_AUDITOR"


class SagaStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_HQ_APPROVAL = "PENDING_HQ_APPROVAL"
    HQ_APPROVED = "HQ_APPROVED"
    REJECTED_BY_HQ = "REJECTED_BY_HQ"
    PENDING_SOURCE_APPROVAL = "PENDING_SOURCE_APPROVAL"
    SOURCE_APPROVED = "SOURCE_APPROVED"
    REJECTED_BY_SOURCE = "REJECTED_BY_SOURCE"
    PENDING_DEST_APPROVAL = "PENDING_DEST_APPROVAL"
    DEST_APPROVED = "DEST_APPROVED"
    REJECTED_BY_DEST = "REJECTED_BY_DEST"
    COMPLETED = "COMPLETED"
    COMPENSATING = "COMPENSATING"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


# ============================================================================
# 2. TABLES & MODELS
# ============================================================================

class HQUser(Base):
    """Users tại HQ: HQ_STAFF, HQ_MANAGER, HQ_AUDITOR"""
    __tablename__ = "HQ_Users"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Branch(Base):
    """Danh mục chi nhánh"""
    __tablename__ = "Branches"

    branch_code: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)
    branch_name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Product(Base):
    """Danh mục sản phẩm chuẩn Master Data"""
    __tablename__ = "Products"

    sku: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class GlobalInventorySnapshot(Base):
    """Ảnh chụp tồn kho toàn hệ thống (Read Model cho HQ)"""
    __tablename__ = "Global_Inventory_Snapshot"

    branch_code: Mapped[str] = mapped_column(String(20), ForeignKey("Branches.branch_code"), primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("Products.sku"), primary_key=True)
    available_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class TransferOrder(Base):
    """Lệnh điều chuyển hàng hóa đa chi nhánh quản lý bởi Saga Orchestrator"""
    __tablename__ = "Transfer_Orders"

    transfer_id: Mapped[str] = mapped_column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    transfer_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    source_branch: Mapped[str] = mapped_column(String(20), nullable=False)
    dest_branch: Mapped[str] = mapped_column(String(20), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    saga_status: Mapped[str] = mapped_column(String(40), default=SagaStatus.DRAFT.value, nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(50), nullable=False)
    hq_approved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_approved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    dest_approved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hq_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dest_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hq_reject_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_reject_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dest_reject_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class SagaStep(Base):
    """Nhật ký các bước thực thi Saga (Audit trail & Tracing)"""
    __tablename__ = "Saga_Steps"

    step_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transfer_id: Mapped[str] = mapped_column(String(50), ForeignKey("Transfer_Orders.transfer_id"), nullable=False, index=True)
    step_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False) # SUCCESS | FAILED | COMPENSATED
    message_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class OutboxEvent(Base):
    """Bảng Outbox_Events tại HQ cho Transactional Outbox"""
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
    """Bảng Inbox_Events tại HQ phục vụ Idempotent Consumer"""
    __tablename__ = "Inbox_Events"

    message_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class StocktakeSessionGlobal(Base):
    """Bản sao phiên kiểm kê chi nhánh tổng hợp về HQ"""
    __tablename__ = "Stocktake_Sessions_Global"

    session_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    session_code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    branch_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    total_skus_counted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_variance_abs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_by_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    finalized_by_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    items: Mapped[list["StocktakeItemGlobal"]] = relationship("StocktakeItemGlobal", back_populates="session", cascade="all, delete-orphan")


class StocktakeItemGlobal(Base):
    """Chi tiết từng mặt hàng kiểm kê được gửi về HQ"""
    __tablename__ = "Stocktake_Items_Global"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(50), ForeignKey("Stocktake_Sessions_Global.session_id"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    system_qty_at_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    counted_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    variance_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    variance_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    session: Mapped["StocktakeSessionGlobal"] = relationship("StocktakeSessionGlobal", back_populates="items")
