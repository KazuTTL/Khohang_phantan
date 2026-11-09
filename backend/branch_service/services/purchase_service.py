# backend/branch_service/services/purchase_service.py
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from branch_service.config import branch_settings
from branch_service.models import (
    BranchUser, LocalInventory, LocalProduct, OutboxEvent,
    PurchaseReceipt, PurchaseReceiptItem, StockLedger, Supplier, UserRole
)
from shared.idempotency import safe_transaction

logger = logging.getLogger("PurchaseService")


class PurchaseService:
    """
    Dịch vụ quản lý Nhập hàng từ Nhà Cung Cấp (Purchase Receipts).
    Tuân thủ phân quyền: STOCK_KEEPER tạo và nhận hàng, BRANCH_MANAGER duyệt.
    Không ai tự duyệt phiếu mình tạo (created_by != approved_by).
    """

    @staticmethod
    async def _verify_user_role(db: AsyncSession, user_id: str, required_roles: list[str]) -> BranchUser:
        user = await db.get(BranchUser, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=403, detail=f"Người dùng '{user_id}' không tồn tại hoặc bị khóa.")
        if user.role not in required_roles:
            roles_str = ", ".join(required_roles)
            raise HTTPException(status_code=403, detail=f"Thao tác yêu cầu quyền [{roles_str}]. Quyền của bạn: {user.role}")
        return user

    @classmethod
    async def create_receipt(
        cls,
        db: AsyncSession,
        supplier_id: str,
        invoice_number: str | None,
        items: list[dict[str, Any]],
        user_id: str,
        note: str | None = None
    ) -> dict[str, Any]:
        """a) STOCK_KEEPER tạo phiếu nhập NCC ở trạng thái DRAFT"""
        await cls._verify_user_role(db, user_id, [UserRole.STOCK_KEEPER.value, UserRole.BRANCH_MANAGER.value])

        supplier = await db.get(Supplier, supplier_id.strip())
        if not supplier or not supplier.is_active:
            raise HTTPException(status_code=404, detail=f"Nhà cung cấp {supplier_id} không tồn tại hoặc đã ngừng hợp tác.")

        if not items:
            raise HTTPException(status_code=400, detail="Phiếu nhập phải có ít nhất 1 sản phẩm.")

        async with safe_transaction(db):
            today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            seq_stmt = select(func.count(PurchaseReceipt.receipt_id)).where(
                PurchaseReceipt.receipt_code.like(f"NK-{branch_settings.BRANCH_CODE}-{today_str}-%")
            )
            count = (await db.execute(seq_stmt)).scalar() or 0
            receipt_code = f"NK-{branch_settings.BRANCH_CODE}-{today_str}-{(count + 1):03d}"
            receipt_id = str(uuid.uuid4())

            total_amount = 0.0
            receipt_items: list[PurchaseReceiptItem] = []

            for it in items:
                sku = it["sku"].strip()
                prod = await db.get(LocalProduct, sku)
                if not prod:
                    raise HTTPException(status_code=404, detail=f"Sản phẩm {sku} không tồn tại trong danh mục.")

                expected_qty = int(it["expected_qty"])
                if expected_qty <= 0:
                    raise HTTPException(status_code=400, detail=f"Số lượng dự kiến cho {sku} phải lớn hơn 0.")

                unit_price = float(it.get("unit_price") or 0.0)
                total_amount += (expected_qty * unit_price)

                receipt_items.append(
                    PurchaseReceiptItem(
                        receipt_id=receipt_id,
                        sku=sku,
                        expected_qty=expected_qty,
                        unit_price=unit_price,
                        status="PENDING"
                    )
                )

            receipt = PurchaseReceipt(
                receipt_id=receipt_id,
                receipt_code=receipt_code,
                branch_code=branch_settings.BRANCH_CODE,
                supplier_id=supplier_id.strip(),
                status="DRAFT",
                created_by=user_id,
                invoice_number=invoice_number,
                total_amount=total_amount,
                note=note,
                created_at=datetime.now(timezone.utc)
            )
            db.add(receipt)
            for r_item in receipt_items:
                db.add(r_item)

            return {
                "receipt_id": receipt_id,
                "receipt_code": receipt_code,
                "status": "DRAFT",
                "total_amount": total_amount,
                "items_count": len(receipt_items)
            }

    @classmethod
    async def submit_receipt(cls, db: AsyncSession, receipt_id: str, user_id: str) -> None:
        """b) Chuyển phiếu từ DRAFT sang PENDING_APPROVAL"""
        async with safe_transaction(db):
            receipt = await db.get(PurchaseReceipt, receipt_id)
            if not receipt:
                raise HTTPException(status_code=404, detail="Không tìm thấy phiếu nhập.")
            if receipt.status != "DRAFT":
                raise HTTPException(status_code=400, detail=f"Chỉ phiếu DRAFT mới có thể nộp duyệt (Hiện tại: {receipt.status}).")
            if receipt.created_by != user_id:
                raise HTTPException(status_code=403, detail="Chỉ người tạo phiếu mới có quyền nộp duyệt.")

            receipt.status = "PENDING_APPROVAL"
            receipt.submitted_at = datetime.now(timezone.utc)

    @classmethod
    async def approve_receipt(cls, db: AsyncSession, receipt_id: str, approver_id: str, note: str | None = None) -> None:
        """c) BRANCH_MANAGER duyệt phiếu (KHÔNG tăng inventory — chờ receive)"""
        await cls._verify_user_role(db, approver_id, [UserRole.BRANCH_MANAGER.value])

        async with safe_transaction(db):
            receipt = await db.get(PurchaseReceipt, receipt_id)
            if not receipt:
                raise HTTPException(status_code=404, detail="Không tìm thấy phiếu nhập.")
            if receipt.status != "PENDING_APPROVAL":
                raise HTTPException(status_code=400, detail="Chỉ phiếu PENDING_APPROVAL mới có thể phê duyệt.")
            if receipt.created_by == approver_id:
                raise HTTPException(status_code=403, detail="Nguyên tắc phân tách: Người duyệt không được trùng người tạo.")

            receipt.status = "APPROVED"
            receipt.approved_by = approver_id
            receipt.approved_at = datetime.now(timezone.utc)
            if note:
                receipt.note = f"{receipt.note or ''} | Duyệt: {note}"

    @classmethod
    async def reject_receipt(cls, db: AsyncSession, receipt_id: str, reason: str, approver_id: str) -> None:
        """d) BRANCH_MANAGER từ chối duyệt phiếu"""
        await cls._verify_user_role(db, approver_id, [UserRole.BRANCH_MANAGER.value])

        async with safe_transaction(db):
            receipt = await db.get(PurchaseReceipt, receipt_id)
            if not receipt or receipt.status != "PENDING_APPROVAL":
                raise HTTPException(status_code=400, detail="Phiên không ở trạng thái PENDING_APPROVAL.")

            receipt.status = "REJECTED"
            receipt.reject_reason = reason
            receipt.rejected_at = datetime.now(timezone.utc)

    @classmethod
    async def receive_receipt(
        cls,
        db: AsyncSession,
        receipt_id: str,
        received_items: list[dict[str, Any]],
        user_id: str
    ) -> dict[str, Any]:
        """
        e) STOCK_KEEPER nhận hàng thực tế:
        - Khóa dòng Local_Inventory WITH (UPDLOCK, ROWLOCK) cho từng item.
        - Cập nhật available += received_qty.
        - Ghi sổ Stock_Ledger loại LOCAL_IN với ref = receipt_id:sku.
        - Cập nhật Purchase_Receipt_Items status (RECEIVED / SHORTAGE / OVERAGE).
        - Ghi Outbox evt.inventory.updated.
        """
        await cls._verify_user_role(db, user_id, [UserRole.STOCK_KEEPER.value, UserRole.BRANCH_MANAGER.value])

        async with safe_transaction(db):
            stmt = (
                select(PurchaseReceipt)
                .options(selectinload(PurchaseReceipt.items))
                .where(PurchaseReceipt.receipt_id == receipt_id)
            )
            receipt = (await db.execute(stmt)).scalar_one_or_none()
            if not receipt:
                raise HTTPException(status_code=404, detail="Không tìm thấy phiếu nhập.")
            if receipt.status != "APPROVED":
                raise HTTPException(status_code=400, detail=f"Chỉ phiếu APPROVED mới được phép nhận hàng (Hiện tại: {receipt.status}).")

            # Map received_qty by sku
            item_map = {it["sku"].strip(): int(it["received_qty"]) for it in received_items}

            bind = db.get_bind()
            lock_hint = "WITH (UPDLOCK, ROWLOCK)" if "mssql" in (bind.dialect.name if bind else "") else ""

            received_count = 0

            for p_item in receipt.items:
                rec_qty = item_map.get(p_item.sku, p_item.expected_qty) # default to expected if omitted
                p_item.received_qty = rec_qty

                if rec_qty == p_item.expected_qty:
                    p_item.status = "RECEIVED"
                elif rec_qty < p_item.expected_qty:
                    p_item.status = "SHORTAGE"
                else:
                    p_item.status = "OVERAGE"

                # Khóa và cập nhật tồn kho
                inv_q = text(f"SELECT available_qty, reserved_qty, version FROM Local_Inventory {lock_hint} WHERE sku = :sku")
                row = (await db.execute(inv_q, {"sku": p_item.sku})).first()
                if row:
                    avail, res_qty, ver = row[0], row[1], row[2]
                    new_avail = avail + rec_qty
                    new_ver = ver + 1
                    await db.execute(
                        text("UPDATE Local_Inventory SET available_qty = :avail, version = :ver, updated_at = :now WHERE sku = :sku"),
                        {"avail": new_avail, "ver": new_ver, "now": datetime.now(timezone.utc), "sku": p_item.sku}
                    )
                else:
                    new_avail = rec_qty
                    res_qty = 0
                    await db.execute(
                        text("INSERT INTO Local_Inventory (sku, available_qty, reserved_qty, version, updated_at) VALUES (:sku, :avail, 0, 1, :now)"),
                        {"sku": p_item.sku, "avail": new_avail, "now": datetime.now(timezone.utc)}
                    )

                # Ghi Ledger
                db.add(StockLedger(
                    reference_id=f"{receipt.receipt_code}:{p_item.sku}",
                    sku=p_item.sku,
                    change_type="LOCAL_IN",
                    quantity=rec_qty,
                    created_at=datetime.now(timezone.utc)
                ))

                # Ghi Outbox evt.inventory.updated
                ev_id = str(uuid.uuid4())
                payload = {
                    "message_id": ev_id,
                    "event_type": "evt.inventory.updated",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "branch_code": branch_settings.BRANCH_CODE,
                        "sku": p_item.sku,
                        "available_qty": new_avail,
                        "reserved_qty": res_qty
                    }
                }
                db.add(OutboxEvent(
                    event_id=ev_id,
                    routing_key="evt.inventory.updated",
                    payload=json.dumps(payload),
                    is_published=False,
                    next_retry_at=datetime.now(timezone.utc),
                    created_at=datetime.now(timezone.utc)
                ))
                received_count += 1

            receipt.status = "RECEIVED"
            receipt.received_by = user_id
            receipt.received_at = datetime.now(timezone.utc)

            return {
                "receipt_id": receipt_id,
                "status": "RECEIVED",
                "received_count": received_count
            }

    @classmethod
    async def cancel_receipt(cls, db: AsyncSession, receipt_id: str, user_id: str) -> None:
        """f) Hủy phiếu nhập"""
        async with safe_transaction(db):
            receipt = await db.get(PurchaseReceipt, receipt_id)
            if not receipt:
                raise HTTPException(status_code=404, detail="Không tìm thấy phiếu.")
            if receipt.status in ("RECEIVED", "FINALIZED", "CANCELLED"):
                raise HTTPException(status_code=400, detail=f"Không thể hủy phiếu ở trạng thái {receipt.status}.")

            receipt.status = "CANCELLED"
