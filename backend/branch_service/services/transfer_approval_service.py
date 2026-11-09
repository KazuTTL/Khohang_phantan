# backend/branch_service/services/transfer_approval_service.py
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.config import branch_settings
from branch_service.models import (
    BranchUser, IncomingTransfer, LocalInventory, OutboxEvent, StockLedger, UserRole
)
from shared.idempotency import check_inbox, mark_inbox, safe_transaction

logger = logging.getLogger("TransferApprovalService")


class TransferApprovalService:
    """
    Dịch vụ phê duyệt Điều chuyển hàng hóa 3 cấp (HQ_MANAGER -> SOURCE_MANAGER -> DEST_MANAGER).
    Tuân thủ phân quyền và bảo vệ toàn vẹn dữ liệu với UPDLOCK + ROWLOCK.
    """

    @staticmethod
    async def _verify_manager(db: AsyncSession, manager_id: str) -> BranchUser:
        user = await db.get(BranchUser, manager_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=403, detail=f"Người dùng '{manager_id}' không tồn tại hoặc bị khóa.")
        if user.role != UserRole.BRANCH_MANAGER.value:
            raise HTTPException(status_code=403, detail=f"Chỉ Quản lý chi nhánh (BRANCH_MANAGER) mới có quyền duyệt. Vai trò của bạn: {user.role}")
        return user

    @classmethod
    async def on_approve_request(cls, db: AsyncSession, message_id: str, data: dict[str, Any]) -> None:
        """
        a) Khi nhận lệnh cmd.transfer.approve_request.{branch}:
        Tạo Incoming_Transfers dạng OUTBOUND, status='AWAITING_SOURCE_APPROVAL'.
        """
        async with safe_transaction(db):
            if message_id and await check_inbox(db, message_id):
                return

            transfer_id = data["transfer_id"]
            existing = await db.get(IncomingTransfer, transfer_id)
            if not existing:
                in_t = IncomingTransfer(
                    transfer_id=transfer_id,
                    transfer_code=data.get("transfer_code"),
                    type="OUTBOUND",
                    sku=data["sku"].strip(),
                    quantity=int(data["quantity"]),
                    source_branch=data["source_branch"].strip(),
                    dest_branch=data["dest_branch"].strip(),
                    status="AWAITING_SOURCE_APPROVAL",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(in_t)

            if message_id:
                await mark_inbox(db, message_id, "cmd.transfer.approve_request")
            logger.info(f"[OUTBOUND TRANSFER CREATED] Đơn {transfer_id} đang chờ Quản lý kho nguồn {branch_settings.BRANCH_CODE} duyệt.")

    @classmethod
    async def source_approve(cls, db: AsyncSession, transfer_id: str, manager_id: str) -> dict[str, Any]:
        """
        b) Quản lý chi nhánh nguồn phê duyệt xuất chuyển:
        - Khóa dòng Local_Inventory WITH (UPDLOCK, ROWLOCK).
        - Nếu available < quantity -> raise 409 Conflict.
        - available -= q, reserved += q.
        - Ghi Stock_Ledger RESERVE.
        - UPDATE Incoming_Transfers status='SOURCE_APPROVED'.
        - INSERT Outbox 'evt.transfer.source_approved'.
        """
        await cls._verify_manager(db, manager_id)

        async with safe_transaction(db):
            in_t = await db.get(IncomingTransfer, transfer_id)
            if not in_t:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn điều chuyển {transfer_id}.")
            if in_t.status != "AWAITING_SOURCE_APPROVAL":
                raise HTTPException(status_code=400, detail=f"Đơn không ở trạng thái AWAITING_SOURCE_APPROVAL (Hiện tại: {in_t.status}).")
            if in_t.source_branch != branch_settings.BRANCH_CODE:
                raise HTTPException(status_code=403, detail="Quản lý chi nhánh chỉ được duyệt đơn xuất từ chi nhánh mình.")

            # Khóa và kiểm tra tồn kho
            bind = db.get_bind()
            lock_hint = "WITH (UPDLOCK, ROWLOCK)" if "mssql" in (bind.dialect.name if bind else "") else ""
            inv_q = text(f"SELECT available_qty, reserved_qty, version FROM Local_Inventory {lock_hint} WHERE sku = :sku")
            row = (await db.execute(inv_q, {"sku": in_t.sku})).first()
            if not row or row[0] < in_t.quantity:
                avail = row[0] if row else 0
                raise HTTPException(
                    status_code=409,
                    detail=f"Kho nguồn không đủ hàng để giữ (Khả dụng: {avail}, Cần: {in_t.quantity})."
                )

            avail, res_qty, ver = row[0], row[1], row[2]
            new_avail = avail - in_t.quantity
            new_res = res_qty + in_t.quantity
            new_ver = ver + 1

            await db.execute(
                text("UPDATE Local_Inventory SET available_qty = :avail, reserved_qty = :res, version = :ver, updated_at = :now WHERE sku = :sku"),
                {"avail": new_avail, "res": new_res, "ver": new_ver, "now": datetime.now(timezone.utc), "sku": in_t.sku}
            )

            # Ghi Ledger
            db.add(StockLedger(
                reference_id=f"{transfer_id}:RESERVE",
                sku=in_t.sku,
                change_type="RESERVE",
                quantity=in_t.quantity,
                created_at=datetime.now(timezone.utc)
            ))

            in_t.status = "SOURCE_APPROVED"
            in_t.updated_at = datetime.now(timezone.utc)

            # Ghi Outbox evt.transfer.source_approved
            event_id = str(uuid.uuid4())
            payload = {
                "message_id": event_id,
                "event_type": "evt.transfer.source_approved",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "transfer_id": transfer_id,
                    "source_branch": in_t.source_branch,
                    "dest_branch": in_t.dest_branch,
                    "sku": in_t.sku,
                    "quantity": in_t.quantity,
                    "approved_by": manager_id
                }
            }
            db.add(OutboxEvent(
                event_id=event_id,
                routing_key="evt.transfer.source_approved",
                payload=json.dumps(payload),
                is_published=False,
                next_retry_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            ))

            return {
                "transfer_id": transfer_id,
                "status": "SOURCE_APPROVED",
                "source_branch": in_t.source_branch,
                "sku": in_t.sku,
                "quantity": in_t.quantity
            }

    @classmethod
    async def source_reject(cls, db: AsyncSession, transfer_id: str, reason: str, manager_id: str) -> None:
        """c) Chi nhánh nguồn từ chối duyệt xuất kho"""
        await cls._verify_manager(db, manager_id)

        async with safe_transaction(db):
            in_t = await db.get(IncomingTransfer, transfer_id)
            if not in_t or in_t.status != "AWAITING_SOURCE_APPROVAL":
                raise HTTPException(status_code=400, detail="Đơn không ở trạng thái AWAITING_SOURCE_APPROVAL.")

            in_t.status = "SOURCE_REJECTED"
            in_t.reject_reason = reason
            in_t.updated_at = datetime.now(timezone.utc)

            event_id = str(uuid.uuid4())
            payload = {
                "message_id": event_id,
                "event_type": "evt.transfer.source_rejected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "transfer_id": transfer_id,
                    "reason": reason,
                    "rejected_by": manager_id
                }
            }
            db.add(OutboxEvent(
                event_id=event_id,
                routing_key="evt.transfer.source_rejected",
                payload=json.dumps(payload),
                is_published=False,
                next_retry_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            ))

    @classmethod
    async def on_confirm_receive(cls, db: AsyncSession, message_id: str, data: dict[str, Any]) -> None:
        """
        d) Khi nhận lệnh cmd.transfer.confirm_receive.{branch}:
        Tạo Incoming_Transfers dạng INBOUND, status='AWAITING_DEST_APPROVAL'.
        """
        async with safe_transaction(db):
            if message_id and await check_inbox(db, message_id):
                return

            transfer_id = data["transfer_id"]
            existing = await db.get(IncomingTransfer, transfer_id)
            if not existing:
                in_t = IncomingTransfer(
                    transfer_id=transfer_id,
                    transfer_code=data.get("transfer_code"),
                    type="INBOUND",
                    sku=data["sku"].strip(),
                    quantity=int(data["quantity"]),
                    source_branch=data["source_branch"].strip(),
                    dest_branch=data["dest_branch"].strip(),
                    status="AWAITING_DEST_APPROVAL",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(in_t)
            else:
                existing.status = "AWAITING_DEST_APPROVAL"
                existing.type = "INBOUND"
                existing.dest_branch = data["dest_branch"].strip()
                existing.updated_at = datetime.now(timezone.utc)

            if message_id:
                await mark_inbox(db, message_id, "cmd.transfer.confirm_receive")
            logger.info(f"[INBOUND TRANSFER CREATED] Đơn {transfer_id} đang chờ Quản lý kho đích {branch_settings.BRANCH_CODE} duyệt nhận.")

    @classmethod
    async def dest_approve(cls, db: AsyncSession, transfer_id: str, received_qty: int, manager_id: str) -> dict[str, Any]:
        """
        e) Quản lý chi nhánh đích phê duyệt nhập kho:
        - Khóa dòng Local_Inventory WITH (UPDLOCK, ROWLOCK) cho sku.
        - available += received_qty.
        - Ghi Stock_Ledger TRANSFER_IN.
        - UPDATE Incoming_Transfers status='DEST_APPROVED', received_qty=received_qty.
        - Ghi Outbox 'evt.transfer.dest_approved' + 'evt.inventory.updated'.
        """
        await cls._verify_manager(db, manager_id)

        async with safe_transaction(db):
            in_t = await db.get(IncomingTransfer, transfer_id)
            if not in_t:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn điều chuyển {transfer_id}.")
            if in_t.status != "AWAITING_DEST_APPROVAL":
                raise HTTPException(status_code=400, detail=f"Đơn không ở trạng thái AWAITING_DEST_APPROVAL (Hiện tại: {in_t.status}).")
            if in_t.dest_branch != branch_settings.BRANCH_CODE:
                raise HTTPException(status_code=403, detail="Quản lý chi nhánh chỉ được duyệt đơn nhập về chi nhánh mình.")

            # Khóa và cập nhật tồn kho
            bind = db.get_bind()
            lock_hint = "WITH (UPDLOCK, ROWLOCK)" if "mssql" in (bind.dialect.name if bind else "") else ""
            inv_q = text(f"SELECT available_qty, reserved_qty, version FROM Local_Inventory {lock_hint} WHERE sku = :sku")
            row = (await db.execute(inv_q, {"sku": in_t.sku})).first()
            if row:
                avail, res_qty, ver = row[0], row[1], row[2]
                new_avail = avail + received_qty
                new_ver = ver + 1
                await db.execute(
                    text("UPDATE Local_Inventory SET available_qty = :avail, version = :ver, updated_at = :now WHERE sku = :sku"),
                    {"avail": new_avail, "ver": new_ver, "now": datetime.now(timezone.utc), "sku": in_t.sku}
                )
            else:
                new_avail = received_qty
                res_qty = 0
                await db.execute(
                    text("INSERT INTO Local_Inventory (sku, available_qty, reserved_qty, version, updated_at) VALUES (:sku, :avail, 0, 1, :now)"),
                    {"sku": in_t.sku, "avail": new_avail, "now": datetime.now(timezone.utc)}
                )

            # Ghi Ledger
            db.add(StockLedger(
                reference_id=f"{transfer_id}:IN",
                sku=in_t.sku,
                change_type="TRANSFER_IN",
                quantity=received_qty,
                created_at=datetime.now(timezone.utc)
            ))

            in_t.status = "DEST_APPROVED"
            in_t.received_qty = received_qty
            in_t.updated_at = datetime.now(timezone.utc)

            # Outbox evt.transfer.dest_approved
            event_id = str(uuid.uuid4())
            payload = {
                "message_id": event_id,
                "event_type": "evt.transfer.dest_approved",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "transfer_id": transfer_id,
                    "source_branch": in_t.source_branch,
                    "dest_branch": in_t.dest_branch,
                    "sku": in_t.sku,
                    "quantity": in_t.quantity,
                    "received_qty": received_qty,
                    "approved_by": manager_id
                }
            }
            db.add(OutboxEvent(
                event_id=event_id,
                routing_key="evt.transfer.dest_approved",
                payload=json.dumps(payload),
                is_published=False,
                next_retry_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            ))

            # Outbox evt.inventory.updated
            inv_ev_id = str(uuid.uuid4())
            inv_payload = {
                "message_id": inv_ev_id,
                "event_type": "evt.inventory.updated",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "branch_code": branch_settings.BRANCH_CODE,
                    "sku": in_t.sku,
                    "available_qty": new_avail,
                    "reserved_qty": res_qty
                }
            }
            db.add(OutboxEvent(
                event_id=inv_ev_id,
                routing_key="evt.inventory.updated",
                payload=json.dumps(inv_payload),
                is_published=False,
                next_retry_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            ))

            return {
                "transfer_id": transfer_id,
                "status": "DEST_APPROVED",
                "received_qty": received_qty,
                "new_available": new_avail
            }

    @classmethod
    async def dest_reject(cls, db: AsyncSession, transfer_id: str, reason: str, manager_id: str) -> None:
        """f) Quản lý chi nhánh đích từ chối nhận hàng điều chuyển"""
        await cls._verify_manager(db, manager_id)

        async with safe_transaction(db):
            in_t = await db.get(IncomingTransfer, transfer_id)
            if not in_t or in_t.status != "AWAITING_DEST_APPROVAL":
                raise HTTPException(status_code=400, detail="Đơn không ở trạng thái AWAITING_DEST_APPROVAL.")

            in_t.status = "DEST_REJECTED"
            in_t.reject_reason = reason
            in_t.updated_at = datetime.now(timezone.utc)

            event_id = str(uuid.uuid4())
            payload = {
                "message_id": event_id,
                "event_type": "evt.transfer.dest_rejected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "transfer_id": transfer_id,
                    "reason": reason,
                    "rejected_by": manager_id
                }
            }
            db.add(OutboxEvent(
                event_id=event_id,
                routing_key="evt.transfer.dest_rejected",
                payload=json.dumps(payload),
                is_published=False,
                next_retry_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            ))
