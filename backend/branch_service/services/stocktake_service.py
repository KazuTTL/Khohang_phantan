# backend/branch_service/services/stocktake_service.py
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
    BranchUser, LocalInventory, OutboxEvent, StockChangeType,
    StockFreezeLog, StockLedger, StocktakeAuditLog,
    StocktakeItem, StocktakeItemStatus, StocktakeScope,
    StocktakeSession, StocktakeStatus, UserRole
)
from shared.event_schemas import EventEnvelope, EvtInventoryUpdatedPayload
from shared.idempotency import safe_transaction
from shared.messaging_topology import ROUTING_EVT_INVENTORY_UPDATED

logger = logging.getLogger("StocktakeService")


class StocktakeService:
    """
    Dịch vụ quản trị Vòng đời Kiểm kê Kho hàng (Stocktake Lifecycle) tại Chi nhánh.
    Đảm bảo tính trung thực số liệu, phân quyền chặt chẽ (SoD - Separation of Duties)
    và tự động đóng băng (Stock Freeze) ngăn chặn tranh chấp khi kiểm đếm.
    """

    @staticmethod
    async def _verify_user_role(db: AsyncSession, user_id: str, required_roles: list[Any]) -> BranchUser:
        """Kiểm tra vai trò người dùng trong Branch_Users"""
        user = await db.get(BranchUser, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=403, detail=f"Người dùng '{user_id}' không tồn tại hoặc bị khóa.")
        
        user_role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
        req_vals = [r.value if hasattr(r, "value") else str(r) for r in required_roles]
        if user_role_val not in req_vals:
            roles_str = ", ".join(req_vals)
            raise HTTPException(status_code=403, detail=f"Thao tác yêu cầu quyền [{roles_str}]. Quyền của bạn: {user_role_val}")
        return user

    @classmethod
    async def create_stocktake(
        cls,
        db: AsyncSession,
        scope_type: str,
        scope_sku_list: list[str] | None,
        note: str | None,
        user_id: str
    ) -> StocktakeSession:
        """
        a) Tạo phiên kiểm kê mới ở trạng thái DRAFT.
        - Validate quyền AUDITOR.
        - Nếu scope FULL: kiểm tra không có phiên FULL nào đang COUNTING hoặc PENDING_APPROVAL.
        - Sinh mã session_code dạng KK-{BRANCH}-{YYYYMMDD}-{seq:03d}.
        - Đóng băng các sản phẩm kiểm kê trong Stock_Freeze_Log.
        """
        await cls._verify_user_role(db, user_id, [UserRole.AUDITOR, UserRole.BRANCH_MANAGER])

        norm_scope = scope_type.strip().upper()
        if norm_scope == "PARTIAL":
            norm_scope = "BY_SKU"
        s_scope = StocktakeScope(norm_scope)

        async with safe_transaction(db):
            # 1. Kiểm tra phiên kiểm kê FULL đang diễn ra
            if s_scope == StocktakeScope.FULL:
                active_stmt = select(StocktakeSession).where(
                    StocktakeSession.scope_type == StocktakeScope.FULL,
                    StocktakeSession.status.in_([StocktakeStatus.COUNTING, StocktakeStatus.PENDING_APPROVAL])
                )
                if (await db.execute(active_stmt)).scalar_one_or_none():
                    raise HTTPException(
                        status_code=409,
                        detail="Chi nhánh đang có một phiên kiểm kê toàn diện (FULL) đang diễn ra. Vui lòng hoàn tất hoặc hủy phiên đó trước."
                    )

            # 2. Sinh mã phiên kiểm kê duy nhất
            today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            seq_stmt = select(func.count(StocktakeSession.session_id)).where(
                StocktakeSession.session_code.like(f"KK-{branch_settings.BRANCH_CODE}-{today_str}-%")
            )
            count = (await db.execute(seq_stmt)).scalar() or 0
            seq_num = count + 1
            session_code = f"KK-{branch_settings.BRANCH_CODE}-{today_str}-{seq_num:03d}"
            session_id = str(uuid.uuid4())

            # 3. Tạo Stocktake_Sessions
            scope_val = s_scope.value if hasattr(s_scope, "value") else str(s_scope)
            session = StocktakeSession(
                session_id=session_id,
                session_code=session_code,
                branch_code=branch_settings.BRANCH_CODE,
                scope_type=scope_val,
                status="DRAFT",
                scope_note=note,
                created_by=user_id,
                created_at=datetime.now(timezone.utc)
            )
            db.add(session)

            # 4. Lấy danh sách tồn kho ban đầu để tạo Stocktake_Items
            inv_stmt = select(LocalInventory)
            if scope_val in ("BY_SKU", "PARTIAL") and scope_sku_list:
                inv_stmt = inv_stmt.where(LocalInventory.sku.in_([s.strip() for s in scope_sku_list]))
            
            inventories = (await db.execute(inv_stmt)).scalars().all()
            if not inventories:
                raise HTTPException(status_code=400, detail="Không tìm thấy sản phẩm nào trong kho thuộc phạm vi kiểm kê.")

            for inv in inventories:
                item = StocktakeItem(
                    session_id=session_id,
                    sku=inv.sku,
                    system_qty_at_start=inv.available_qty,
                    counted_qty=None,
                    variance_qty=None,
                    status=StocktakeItemStatus.PENDING
                )
                db.add(item)

            # 5. Thiết lập đóng băng hàng hóa (Stock_Freeze_Log)
            if s_scope == StocktakeScope.FULL:
                # Đóng băng toàn bộ kho: sku=NULL
                db.add(StockFreezeLog(
                    session_id=session_id,
                    sku=None,
                    frozen_at=datetime.now(timezone.utc)
                ))
            else:
                for inv in inventories:
                    db.add(StockFreezeLog(
                        session_id=session_id,
                        sku=inv.sku,
                        frozen_at=datetime.now(timezone.utc)
                    ))

            # 6. Ghi Audit Log
            db.add(StocktakeAuditLog(
                session_id=session_id,
                action="CREATED",
                performed_by=user_id,
                note=f"Tạo phiên kiểm kê {session_code} phạm vi {s_scope.value} với {len(inventories)} sản phẩm.",
                created_at=datetime.now(timezone.utc)
            ))

            # 7. Ghi Outbox EVT_STOCKTAKE_CREATED
            envelope = EventEnvelope(
                event_type="EVT_STOCKTAKE_CREATED",
                data={
                    "session_id": session_id,
                    "session_code": session_code,
                    "branch_code": branch_settings.BRANCH_CODE,
                    "scope_type": s_scope.value,
                    "created_by": user_id
                }
            )
            db.add(OutboxEvent(
                event_id=envelope.message_id,
                routing_key=f"evt.stocktake.created.{branch_settings.BRANCH_CODE}",
                payload=envelope.model_dump_json(),
                is_published=False,
                next_retry_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            ))

            return session

    @classmethod
    async def start_counting(cls, db: AsyncSession, session_id: str, user_id: str) -> None:
        """b) Chuyển phiên kiểm kê từ DRAFT sang COUNTING (bắt đầu đếm thực tế)"""
        async with safe_transaction(db):
            session = await db.get(StocktakeSession, session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Không tìm thấy phiên kiểm kê.")
            if session.status != StocktakeStatus.DRAFT:
                raise HTTPException(status_code=400, detail=f"Chỉ phiên ở trạng thái DRAFT mới có thể bắt đầu đếm (Hiện tại: {session.status.value}).")
            if session.created_by != user_id:
                raise HTTPException(status_code=403, detail="Chỉ người tạo phiên kiểm kê mới có quyền bắt đầu đếm.")

            session.status = StocktakeStatus.COUNTING
            session.counting_started_at = datetime.now(timezone.utc)

            db.add(StocktakeAuditLog(
                session_id=session_id,
                action="STARTED",
                performed_by=user_id,
                note="Bắt đầu quá trình đếm kho thực tế.",
                created_at=datetime.now(timezone.utc)
            ))

    @classmethod
    async def count_item(
        cls,
        db: AsyncSession,
        session_id: str,
        sku: str,
        counted_qty: int,
        variance_reason: str | None,
        user_id: str
    ) -> StocktakeItem:
        """
        c) Ghi nhận số lượng đếm thực tế của 1 SKU trong phiên kiểm kê.
        Dùng UPDLOCK + ROWLOCK trên hàng Stocktake_Items.
        """
        await cls._verify_user_role(db, user_id, [UserRole.AUDITOR, UserRole.BRANCH_MANAGER])
        if counted_qty < 0:
            raise HTTPException(status_code=400, detail="Số lượng kiểm đếm không được âm.")

        async with safe_transaction(db):
            session = await db.get(StocktakeSession, session_id)
            if not session or session.status != StocktakeStatus.COUNTING:
                raise HTTPException(status_code=400, detail="Phiên kiểm kê không ở trạng thái COUNTING.")

            # Khóa dòng item với UPDLOCK + ROWLOCK
            bind = db.get_bind()
            lock_hint = "WITH (UPDLOCK, ROWLOCK)" if "mssql" in (bind.dialect.name if bind else "") else ""
            item_query = text(
                f"SELECT id, system_qty_at_start FROM Stocktake_Items {lock_hint} "
                f"WHERE session_id = :sid AND sku = :sku"
            )
            res = await db.execute(item_query, {"sid": session_id, "sku": sku})
            row = res.first()
            if not row:
                raise HTTPException(status_code=404, detail=f"SKU {sku} không nằm trong danh sách kiểm kê của phiên này.")

            item_id, sys_qty = row[0], row[1]
            diff = counted_qty - sys_qty

            item = await db.get(StocktakeItem, item_id)
            item.counted_qty = counted_qty
            item.variance_qty = diff
            item.status = StocktakeItemStatus.COUNTED
            item.variance_reason = variance_reason
            item.counted_by = user_id
            item.counted_at = datetime.now(timezone.utc)

            db.add(StocktakeAuditLog(
                session_id=session_id,
                action="ITEM_COUNTED",
                performed_by=user_id,
                note=f"SKU {sku}: Thực tế={counted_qty}, Hệ thống={sys_qty}, Lệch={diff:+} ({variance_reason or 'Không ghi chú'})",
                created_at=datetime.now(timezone.utc)
            ))

            return item

    @classmethod
    async def submit_stocktake(cls, db: AsyncSession, session_id: str, user_id: str) -> None:
        """
        d) Nộp kết quả kiểm kê chờ phê duyệt (PENDING_APPROVAL).
        Bắt buộc toàn bộ mặt hàng trong phiên phải được đếm xong.
        """
        async with safe_transaction(db):
            session = await db.get(StocktakeSession, session_id)
            if not session or session.status != StocktakeStatus.COUNTING:
                raise HTTPException(status_code=400, detail="Chỉ phiên ở trạng thái COUNTING mới có thể nộp duyệt.")

            # Kiểm tra xem có sản phẩm nào chưa đếm không
            uncounted_stmt = select(func.count(StocktakeItem.id)).where(
                StocktakeItem.session_id == session_id,
                StocktakeItem.status == StocktakeItemStatus.PENDING
            )
            uncounted_count = (await db.execute(uncounted_stmt)).scalar() or 0
            if uncounted_count > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Còn {uncounted_count} mặt hàng chưa được kiểm đếm xong. Vui lòng đếm đầy đủ trước khi nộp."
                )

            session.status = StocktakeStatus.PENDING_APPROVAL
            session.submitted_at = datetime.now(timezone.utc)

            db.add(StocktakeAuditLog(
                session_id=session_id,
                action="SUBMITTED",
                performed_by=user_id,
                note="Đã nộp kết quả kiểm kê lên Quản lý chi nhánh chờ phê duyệt.",
                created_at=datetime.now(timezone.utc)
            ))

            envelope = EventEnvelope(
                event_type="EVT_STOCKTAKE_SUBMITTED",
                source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                payload={"session_id": session_id, "session_code": session.session_code, "submitted_by": user_id}
            )
            db.add(OutboxEvent(
                event_id=envelope.message_id,
                routing_key=f"evt.stocktake.submitted.{branch_settings.BRANCH_CODE}",
                payload=envelope.model_dump_json(),
                is_published=False,
                next_retry_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            ))

    @classmethod
    async def approve_stocktake(
        cls,
        db: AsyncSession,
        session_id: str,
        approver_id: str,
        note: str | None = None
    ) -> dict[str, Any]:
        """
        e) Phê duyệt phiên kiểm kê (Dành riêng cho BRANCH_MANAGER).
        - Đảm bảo tính phân quyền (SoD): Người duyệt KHÔNG ĐƯỢC là người tạo phiên.
        - Tự động điều chỉnh số dư tồn kho (Local_Inventory) theo chênh lệch thực tế.
        - Ghi sổ Stock_Ledger loại STOCKTAKE_ADJUST.
        - Giải phóng đóng băng (Stock_Freeze_Log).
        - Ghi Outbox EVT_STOCKTAKE_APPROVED và EVT_INVENTORY_UPDATED.
        """
        await cls._verify_user_role(db, approver_id, [UserRole.BRANCH_MANAGER])

        async with safe_transaction(db):
            session = await db.get(StocktakeSession, session_id)
            if not session or session.status != StocktakeStatus.PENDING_APPROVAL:
                raise HTTPException(status_code=400, detail="Phiên kiểm kê không ở trạng thái PENDING_APPROVAL.")

            # Kiểm tra Separation of Duties (Người duyệt != Người tạo)
            if session.created_by == approver_id:
                raise HTTPException(
                    status_code=403,
                    detail="Nguyên tắc phân tách trách nhiệm (SoD): Người duyệt không được trùng với người tạo phiên kiểm kê."
                )

            # Lấy toàn bộ items
            stmt = select(StocktakeItem).where(StocktakeItem.session_id == session_id)
            items = (await db.execute(stmt)).scalars().all()

            adjusted_count = 0
            total_variance_abs = 0

            # Cập nhật tồn kho cho từng item có chênh lệch
            for item in items:
                if item.variance_qty and item.variance_qty != 0:
                    # Khóa dòng tồn kho
                    bind = db.get_bind()
                    lock_hint = "WITH (UPDLOCK, ROWLOCK)" if "mssql" in (bind.dialect.name if bind else "") else ""
                    inv_q = text(f"SELECT available_qty, reserved_qty, version FROM Local_Inventory {lock_hint} WHERE sku = :sku")
                    row = (await db.execute(inv_q, {"sku": item.sku})).first()
                    if not row:
                        continue

                    avail, res_qty, ver = row[0], row[1], row[2]
                    new_avail = avail + item.variance_qty
                    if new_avail < 0:
                        raise HTTPException(
                            status_code=409,
                            detail=f"Không thể duyệt: Điều chỉnh chênh lệch ({item.variance_qty}) làm tồn kho {item.sku} bị âm ({new_avail} < 0)."
                        )

                    new_ver = ver + 1
                    await db.execute(
                        text("UPDATE Local_Inventory SET available_qty = :avail, version = :ver, updated_at = :now WHERE sku = :sku"),
                        {"avail": new_avail, "ver": new_ver, "now": datetime.now(timezone.utc), "sku": item.sku}
                    )

                    # Ghi Ledger
                    db.add(StockLedger(
                        transaction_type=StockChangeType.STOCKTAKE_ADJUST,
                        sku=item.sku,
                        quantity=item.variance_qty,
                        available_after=new_avail,
                        reserved_after=res_qty,
                        reference_id=f"{session.session_code}:{item.sku}",
                        user_id=approver_id,
                        reason=f"Cân đối kiểm kê {session.session_code}: {item.variance_reason or note or 'Lệch đếm'}",
                        created_at=datetime.now(timezone.utc)
                    ))

                    # Ghi Outbox EVT_INVENTORY_UPDATED cho từng SKU thay đổi
                    env_inv = EventEnvelope(
                        event_type="EVT_INVENTORY_UPDATED",
                        source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                        payload=EvtInventoryUpdatedPayload(
                            branch_code=branch_settings.BRANCH_CODE,
                            sku=item.sku,
                            available_qty=new_avail,
                            reserved_qty=res_qty,
                            change_type="STOCKTAKE_ADJUST",
                            reference_id=session.session_code
                        )
                    )
                    db.add(OutboxEvent(
                        event_id=env_inv.message_id,
                        routing_key=ROUTING_EVT_INVENTORY_UPDATED,
                        payload=env_inv.model_dump_json(),
                        is_published=False,
                        next_retry_at=datetime.now(timezone.utc),
                        created_at=datetime.now(timezone.utc)
                    ))

                    adjusted_count += 1
                    total_variance_abs += abs(item.variance_qty)

            # Cập nhật trạng thái session -> APPROVED
            session.status = StocktakeStatus.APPROVED
            session.approved_by = approver_id
            session.approved_at = datetime.now(timezone.utc)

            # Giải phóng đóng băng (Stock_Freeze_Log)
            await db.execute(
                text("UPDATE Stock_Freeze_Log SET released_at = :now WHERE session_id = :sid AND released_at IS NULL"),
                {"now": datetime.now(timezone.utc), "sid": session_id}
            )

            # Ghi Audit Log
            db.add(StocktakeAuditLog(
                session_id=session_id,
                action="APPROVED",
                performed_by=approver_id,
                note=f"Duyệt kiểm kê {session.session_code}. Điều chỉnh {adjusted_count} mặt hàng. Tổng lệch tuyệt đối: {total_variance_abs}.",
                created_at=datetime.now(timezone.utc)
            ))

            # Outbox EVT_STOCKTAKE_APPROVED
            env_app = EventEnvelope(
                event_type="EVT_STOCKTAKE_APPROVED",
                source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                payload={
                    "session_id": session_id,
                    "session_code": session.session_code,
                    "approved_by": approver_id,
                    "adjusted_count": adjusted_count,
                    "total_variance_abs": total_variance_abs
                }
            )
            db.add(OutboxEvent(
                event_id=env_app.message_id,
                routing_key=f"evt.stocktake.approved.{branch_settings.BRANCH_CODE}",
                payload=env_app.model_dump_json(),
                is_published=False,
                next_retry_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            ))

            return {
                "session_id": session_id,
                "session_code": session.session_code,
                "status": session.status.value,
                "adjusted_count": adjusted_count,
                "total_variance_abs": total_variance_abs
            }

    @classmethod
    async def reject_stocktake(cls, db: AsyncSession, session_id: str, approver_id: str, reason: str) -> None:
        """f.1) Từ chối phê duyệt kiểm kê -> Giải phóng đóng băng"""
        await cls._verify_user_role(db, approver_id, [UserRole.BRANCH_MANAGER])
        async with safe_transaction(db):
            session = await db.get(StocktakeSession, session_id)
            if not session or session.status != StocktakeStatus.PENDING_APPROVAL:
                raise HTTPException(status_code=400, detail="Phiên không ở trạng thái PENDING_APPROVAL.")

            session.status = StocktakeStatus.REJECTED
            # Giải phóng đóng băng
            await db.execute(
                text("UPDATE Stock_Freeze_Log SET released_at = :now WHERE session_id = :sid AND released_at IS NULL"),
                {"now": datetime.now(timezone.utc), "sid": session_id}
            )
            db.add(StocktakeAuditLog(
                session_id=session_id,
                action="REJECTED",
                performed_by=approver_id,
                note=f"Từ chối duyệt kiểm kê: {reason}",
                created_at=datetime.now(timezone.utc)
            ))

    @classmethod
    async def reopen_stocktake(cls, db: AsyncSession, session_id: str, user_id: str) -> None:
        """f.2) Mở lại phiên kiểm kê để đếm lại (từ PENDING_APPROVAL hoặc REJECTED quay lại COUNTING)"""
        await cls._verify_user_role(db, user_id, [UserRole.BRANCH_MANAGER])
        async with safe_transaction(db):
            session = await db.get(StocktakeSession, session_id)
            if not session or session.status not in (StocktakeStatus.PENDING_APPROVAL, StocktakeStatus.REJECTED):
                raise HTTPException(status_code=400, detail="Chỉ phiên PENDING_APPROVAL hoặc REJECTED mới có thể mở lại đếm.")

            session.status = StocktakeStatus.COUNTING
            # Đảm bảo đóng băng được thiết lập lại nếu trước đó đã giải phóng
            await db.execute(
                text("UPDATE Stock_Freeze_Log SET released_at = NULL WHERE session_id = :sid"),
                {"sid": session_id}
            )
            db.add(StocktakeAuditLog(
                session_id=session_id,
                action="REOPENED",
                performed_by=user_id,
                note="Mở lại phiên kiểm kê để đếm lại số liệu.",
                created_at=datetime.now(timezone.utc)
            ))

    @classmethod
    async def cancel_stocktake(cls, db: AsyncSession, session_id: str, user_id: str) -> None:
        """f.3) Hủy phiên kiểm kê -> Giải phóng đóng băng ngay lập tức"""
        async with safe_transaction(db):
            session = await db.get(StocktakeSession, session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Không tìm thấy phiên kiểm kê.")
            if session.status in (StocktakeStatus.APPROVED, StocktakeStatus.FINALIZED):
                raise HTTPException(status_code=400, detail="Không thể hủy phiên đã APPROVED hoặc FINALIZED.")

            session.status = StocktakeStatus.CANCELLED
            # Giải phóng đóng băng
            await db.execute(
                text("UPDATE Stock_Freeze_Log SET released_at = :now WHERE session_id = :sid AND released_at IS NULL"),
                {"now": datetime.now(timezone.utc), "sid": session_id}
            )
            db.add(StocktakeAuditLog(
                session_id=session_id,
                action="CANCELLED",
                performed_by=user_id,
                note="Hủy bỏ phiên kiểm kê và giải phóng đóng băng hàng hóa.",
                created_at=datetime.now(timezone.utc)
            ))
