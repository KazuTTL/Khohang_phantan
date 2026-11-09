# backend/branch_service/services/stock_service.py
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.config import branch_settings
from branch_service.models import (
    IncomingTransfer, LocalInventory, OutboxEvent, StockFreezeLog, StockLedger
)
from shared.idempotency import check_inbox, mark_inbox, safe_transaction

logger = logging.getLogger("StockService")


class StockService:
    """
    Dịch vụ quản trị cốt lõi Tồn kho & Giao dịch Phân tán tại Chi nhánh.
    Tuân thủ tuyệt đối:
    1. Transactional Outbox: Mọi thao tác cập nhật dữ liệu nghiệp vụ và ghi sự kiện Outbox
       đều nằm trong duy nhất 1 Local ACID Transaction (async with db.begin()).
    2. Pessimistic Concurrency Control: Bắt buộc dùng SELECT ... WITH (UPDLOCK, ROWLOCK)
       trước khi đọc và trừ tồn kho, triệt tiêu race condition và âm kho.
    3. Idempotent Consumer: Kiểm tra bảng Inbox_Events trước khi xử lý bất kỳ command nào.
    4. Stock Freeze Check: Ngăn chặn xuất/nhập đối với sản phẩm đang trong phiên kiểm kê.
    """

    @staticmethod
    async def _check_freeze(db: AsyncSession, sku: str) -> None:
        """
        Kiểm tra SKU có đang bị đóng băng bởi đợt kiểm kê (Stocktake) nào không.
        Nếu freeze đang hoạt động (released_at IS NULL và sku IS NULL hoặc sku=:sku) -> raise 409 Conflict.
        """
        stmt = (
            select(StockFreezeLog)
            .where(
                StockFreezeLog.released_at.is_(None),
                or_(StockFreezeLog.sku == sku, StockFreezeLog.sku.is_(None))
            )
            .limit(1)
        )
        res = await db.execute(stmt)
        freeze = res.scalar_one_or_none()
        if freeze:
            raise HTTPException(
                status_code=409,
                detail=f"Kho đang kiểm kê (Sản phẩm {sku} đang bị đóng băng trong phiên {freeze.session_id})."
            )

    @staticmethod
    async def _lock_and_get_inventory(db: AsyncSession, sku: str) -> tuple[int, int, int] | None:
        """
        Khóa dòng bi quan: SELECT ... WITH (UPDLOCK, ROWLOCK) FROM Local_Inventory WHERE sku=:sku.
        UPDLOCK giữ khóa cập nhật ngay từ lúc đọc, ROWLOCK ép mức khóa dòng chính xác.
        Trả về: (available_qty, reserved_qty, version)
        """
        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind else ""
        lock_hint = "WITH (UPDLOCK, ROWLOCK)" if "mssql" in dialect_name else ""
        query = text(f"SELECT available_qty, reserved_qty, version FROM Local_Inventory {lock_hint} WHERE sku = :sku")
        result = await db.execute(query, {"sku": sku})
        row = result.first()
        if row is None:
            return None
        return (row[0], row[1], row[2])

    @classmethod
    async def adjust_local_stock(
        cls,
        db: AsyncSession,
        sku: str,
        change_type: str,
        quantity: int,
        reason: str | None = None,
        user_id: str | None = None
    ) -> dict[str, Any]:
        """
        a) Biến động tồn kho cục bộ (LOCAL_IN hoặc LOCAL_OUT).
        """
        c_type = change_type.strip().upper()
        if c_type not in ("LOCAL_IN", "LOCAL_OUT"):
            raise HTTPException(status_code=400, detail="change_type chỉ chấp nhận 'LOCAL_IN' hoặc 'LOCAL_OUT'.")

        if quantity <= 0:
            raise HTTPException(status_code=400, detail="Số lượng biến động phải lớn hơn 0.")

        async with safe_transaction(db):
            await cls._check_freeze(db, sku)
            inv = await cls._lock_and_get_inventory(db, sku)
            if inv is None:
                raise HTTPException(status_code=404, detail=f"Sản phẩm {sku} chưa tồn tại trong kho chi nhánh.")

            current_avail, current_res, current_ver = inv

            if c_type == "LOCAL_OUT":
                if current_avail < quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Tồn kho khả dụng không đủ xuất ({current_avail} < {quantity}). Ngăn chặn xuất âm kho."
                    )
                new_avail = current_avail - quantity
            else:
                new_avail = current_avail + quantity

            new_ver = current_ver + 1

            # Update Local_Inventory
            update_stmt = text(
                "UPDATE Local_Inventory SET available_qty = :avail, version = :ver, updated_at = :now WHERE sku = :sku"
            )
            await db.execute(
                update_stmt,
                {"avail": new_avail, "ver": new_ver, "now": datetime.now(timezone.utc), "sku": sku}
            )

            # Insert Stock_Ledger
            ref_id = str(uuid.uuid4())
            ledger = StockLedger(
                reference_id=ref_id,
                sku=sku,
                change_type=c_type,
                quantity=quantity,
                created_at=datetime.now(timezone.utc)
            )
            db.add(ledger)
            await db.flush()

            # Insert Outbox_Events routing 'evt.inventory.updated'
            event_id = str(uuid.uuid4())
            payload = {
                "message_id": event_id,
                "event_type": "evt.inventory.updated",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "branch_code": branch_settings.BRANCH_CODE,
                    "sku": sku,
                    "available_qty": new_avail,
                    "reserved_qty": current_res
                }
            }
            outbox = OutboxEvent(
                event_id=event_id,
                routing_key="evt.inventory.updated",
                payload=json.dumps(payload),
                is_published=False,
                retry_count=0,
                next_retry_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            )
            db.add(outbox)

            return {
                "new_available": new_avail,
                "ledger_id": ledger.ledger_id,
                "message_id": event_id,
                "reference_id": ref_id
            }

    @classmethod
    async def reserve_stock(
        cls,
        db: AsyncSession,
        transfer_id: str,
        message_id: str,
        sku: str,
        quantity: int,
        approved_by: str = "SYSTEM"
    ) -> bool:
        """
        c) Tạm giữ hàng tại kho xuất trong luồng Saga Phase 1 (CMD_RESERVE_STOCK).
        """
        async with safe_transaction(db):
            # Check Inbox (Idempotent)
            if await check_inbox(db, message_id):
                logger.info(f"[IDEMPOTENT HIT] reserve_stock message_id={message_id} đã xử lý.")
                return True

            await cls._check_freeze(db, sku)

            inv = await cls._lock_and_get_inventory(db, sku)
            if inv is None or inv[0] < quantity:
                avail = inv[0] if inv else 0
                await mark_inbox(db, message_id, "cmd.transfer.reserve")
                
                fail_event_id = str(uuid.uuid4())
                fail_payload = {
                    "message_id": fail_event_id,
                    "event_type": "evt.transfer.reserve_failed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "transfer_id": transfer_id,
                        "source_branch": branch_settings.BRANCH_CODE,
                        "sku": sku,
                        "quantity": quantity,
                        "reason": f"Kho {branch_settings.BRANCH_CODE} không đủ tồn khả dụng (Còn {avail}, cần {quantity})"
                    }
                }
                db.add(OutboxEvent(
                    event_id=fail_event_id,
                    routing_key="evt.transfer.reserve_failed",
                    payload=json.dumps(fail_payload),
                    is_published=False,
                    next_retry_at=datetime.now(timezone.utc),
                    created_at=datetime.now(timezone.utc)
                ))
                return False

            # Đủ hàng: available -= q, reserved += q
            current_avail, current_res, current_ver = inv
            new_avail = current_avail - quantity
            new_res = current_res + quantity
            new_ver = current_ver + 1

            update_stmt = text(
                "UPDATE Local_Inventory SET available_qty = :avail, reserved_qty = :res, "
                "version = :ver, updated_at = :now WHERE sku = :sku"
            )
            await db.execute(
                update_stmt,
                {"avail": new_avail, "res": new_res, "ver": new_ver, "now": datetime.now(timezone.utc), "sku": sku}
            )

            # Insert Stock_Ledger RESERVE
            db.add(StockLedger(
                reference_id=f"{transfer_id}:RESERVE",
                sku=sku,
                change_type="RESERVE",
                quantity=quantity,
                created_at=datetime.now(timezone.utc)
            ))

            await mark_inbox(db, message_id, "cmd.transfer.reserve")

            # Insert Outbox 'evt.transfer.source_approved'
            succ_event_id = str(uuid.uuid4())
            succ_payload = {
                "message_id": succ_event_id,
                "event_type": "evt.transfer.source_approved",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "transfer_id": transfer_id,
                    "source_branch": branch_settings.BRANCH_CODE,
                    "dest_branch": "",
                    "sku": sku,
                    "quantity": quantity,
                    "approved_by": approved_by
                }
            }
            db.add(OutboxEvent(
                event_id=succ_event_id,
                routing_key="evt.transfer.source_approved",
                payload=json.dumps(succ_payload),
                is_published=False,
                next_retry_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            ))
            return True

    @classmethod
    async def commit_out(
        cls,
        db: AsyncSession,
        transfer_id: str,
        message_id: str,
        sku: str,
        quantity: int
    ) -> None:
        """
        d) Nhận evt.transfer.completed ở branch NGUỒN: trừ hẳn reserved -= q.
        """
        async with safe_transaction(db):
            if await check_inbox(db, message_id):
                return

            inv = await cls._lock_and_get_inventory(db, sku)
            if inv:
                avail, res_qty, ver = inv
                new_res = max(0, res_qty - quantity)
                new_ver = ver + 1
                await db.execute(
                    text("UPDATE Local_Inventory SET reserved_qty = :res, version = :ver WHERE sku = :sku"),
                    {"res": new_res, "ver": new_ver, "sku": sku}
                )

                db.add(StockLedger(
                    reference_id=f"{transfer_id}:COMMIT",
                    sku=sku,
                    change_type="COMMIT_OUT",
                    quantity=quantity,
                    created_at=datetime.now(timezone.utc)
                ))

            await mark_inbox(db, message_id, "evt.transfer.completed")

    @classmethod
    async def release_stock(
        cls,
        db: AsyncSession,
        transfer_id: str,
        message_id: str,
        sku: str,
        quantity: int
    ) -> None:
        """
        e) Bù trừ hoàn trả (Rollback): reserved -= q, available += q.
        """
        async with safe_transaction(db):
            if await check_inbox(db, message_id):
                return

            inv = await cls._lock_and_get_inventory(db, sku)
            if inv:
                avail, res_qty, ver = inv
                new_res = max(0, res_qty - quantity)
                new_avail = avail + quantity
                new_ver = ver + 1

                await db.execute(
                    text("UPDATE Local_Inventory SET available_qty = :avail, reserved_qty = :res, version = :ver WHERE sku = :sku"),
                    {"avail": new_avail, "res": new_res, "ver": new_ver, "sku": sku}
                )

                db.add(StockLedger(
                    reference_id=f"{transfer_id}:RELEASE",
                    sku=sku,
                    change_type="RELEASE_RESERVE",
                    quantity=quantity,
                    created_at=datetime.now(timezone.utc)
                ))

            await mark_inbox(db, message_id, "cmd.transfer.release")

            rel_event_id = str(uuid.uuid4())
            rel_payload = {
                "message_id": rel_event_id,
                "event_type": "evt.transfer.released",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "transfer_id": transfer_id,
                    "source_branch": branch_settings.BRANCH_CODE,
                    "sku": sku,
                    "quantity": quantity
                }
            }
            db.add(OutboxEvent(
                event_id=rel_event_id,
                routing_key="evt.transfer.released",
                payload=json.dumps(rel_payload),
                is_published=False,
                next_retry_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            ))

    @classmethod
    async def import_transfer(
        cls,
        db: AsyncSession,
        transfer_id: str,
        message_id: str,
        sku: str,
        quantity: int,
        received_qty: int,
        user_id: str = "SYSTEM"
    ) -> None:
        """
        f) Dùng khi dest-approve: tăng available += received_qty.
        """
        async with safe_transaction(db):
            if message_id and await check_inbox(db, message_id):
                return

            await cls._check_freeze(db, sku)

            inv = await cls._lock_and_get_inventory(db, sku)
            if inv:
                avail, res_qty, ver = inv
                new_avail = avail + received_qty
                new_ver = ver + 1
                await db.execute(
                    text("UPDATE Local_Inventory SET available_qty = :avail, version = :ver, updated_at = :now WHERE sku = :sku"),
                    {"avail": new_avail, "ver": new_ver, "now": datetime.now(timezone.utc), "sku": sku}
                )
            else:
                new_avail = received_qty
                await db.execute(
                    text("INSERT INTO Local_Inventory (sku, available_qty, reserved_qty, version, updated_at) VALUES (:sku, :avail, 0, 1, :now)"),
                    {"sku": sku, "avail": new_avail, "now": datetime.now(timezone.utc)}
                )

            # Insert Stock_Ledger TRANSFER_IN
            db.add(StockLedger(
                reference_id=f"{transfer_id}:IN",
                sku=sku,
                change_type="TRANSFER_IN",
                quantity=received_qty,
                created_at=datetime.now(timezone.utc)
            ))

            # Update Incoming_Transfers status='DEST_APPROVED', received_qty
            in_transfer = await db.get(IncomingTransfer, transfer_id)
            source_branch = in_transfer.source_branch if in_transfer else "UNKNOWN"
            if in_transfer:
                in_transfer.status = "DEST_APPROVED"
                in_transfer.received_qty = received_qty
                in_transfer.updated_at = datetime.now(timezone.utc)

            if message_id:
                await mark_inbox(db, message_id, "cmd.transfer.confirm_receive")

            # Outbox evt.transfer.dest_approved
            event_id = str(uuid.uuid4())
            payload = {
                "message_id": event_id,
                "event_type": "evt.transfer.dest_approved",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "transfer_id": transfer_id,
                    "source_branch": source_branch,
                    "dest_branch": branch_settings.BRANCH_CODE,
                    "sku": sku,
                    "quantity": quantity,
                    "received_qty": received_qty,
                    "approved_by": user_id
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

    @classmethod
    async def reject_source(
        cls,
        db: AsyncSession,
        transfer_id: str,
        reason: str,
        user_id: str
    ) -> None:
        """
        g) Chi nhánh nguồn từ chối xuất hàng.
        """
        async with safe_transaction(db):
            in_transfer = await db.get(IncomingTransfer, transfer_id)
            if in_transfer:
                in_transfer.status = "SOURCE_REJECTED"
                in_transfer.reject_reason = reason
                in_transfer.updated_at = datetime.now(timezone.utc)

            event_id = str(uuid.uuid4())
            payload = {
                "message_id": event_id,
                "event_type": "evt.transfer.source_rejected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "transfer_id": transfer_id,
                    "reason": reason,
                    "rejected_by": user_id
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
    async def reject_dest(
        cls,
        db: AsyncSession,
        transfer_id: str,
        reason: str,
        user_id: str
    ) -> None:
        """
        h) Chi nhánh đích từ chối nhận hàng.
        """
        async with safe_transaction(db):
            in_transfer = await db.get(IncomingTransfer, transfer_id)
            if in_transfer:
                in_transfer.status = "DEST_REJECTED"
                in_transfer.reject_reason = reason
                in_transfer.updated_at = datetime.now(timezone.utc)

            event_id = str(uuid.uuid4())
            payload = {
                "message_id": event_id,
                "event_type": "evt.transfer.dest_rejected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "transfer_id": transfer_id,
                    "reason": reason,
                    "rejected_by": user_id
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
