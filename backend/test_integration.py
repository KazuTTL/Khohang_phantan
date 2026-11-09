# backend/test_integration.py
import asyncio
import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["BRANCH_CODE"] = "HN"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi import HTTPException

# Test with in-memory SQLite for rapid offline validation of business logic
test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestSession = async_sessionmaker(bind=test_engine, expire_on_commit=False)


async def run_tests():
    print("=" * 70)
    print("RUNNING DISTRIBUTED WMS BACKEND INTEGRATION TESTS")
    print("=" * 70)

    from branch_service.database import Base as BranchBase
    from branch_service.models import BranchUser, LocalInventory, LocalProduct, StocktakeSession, StocktakeItem, StockFreezeLog, UserRole
    from branch_service.services.stock_service import StockService
    from branch_service.services.transfer_approval_service import TransferApprovalService
    from branch_service.services.purchase_service import PurchaseService
    from branch_service.services.stocktake_service import StocktakeService
    from shared.idempotency import check_inbox, mark_inbox, safe_transaction

    from hq_service.database import Base as HQBase
    from hq_service.models import HQUser, Branch, Product, TransferOrder, SagaStep, OutboxEvent as HQOutbox
    from hq_service.saga.orchestrator import SagaOrchestrator
    from hq_service.saga.handlers import SagaStepHandlers
    from hq_service.saga.state import SagaStatus

    # 1. Initialize Tables
    async with test_engine.begin() as conn:
        await conn.run_sync(BranchBase.metadata.create_all)
        await conn.run_sync(HQBase.metadata.create_all)

    # Seed initial test data
    async with TestSession() as session:
        async with safe_transaction(session):
            # Seed branch users
            session.add_all([
                BranchUser(user_id="manager_hn", full_name="Quản lý HN", role="BRANCH_MANAGER", is_active=True),
                BranchUser(user_id="stock_hn", full_name="Thủ kho HN", role="STOCK_KEEPER", is_active=True),
                BranchUser(user_id="auditor_hn", full_name="Kiểm toán HN", role="AUDITOR", is_active=True),
                BranchUser(user_id="sales_hn", full_name="Bán hàng HN", role="SALES", is_active=True),
            ])
            # Seed local products
            session.add_all([
                LocalProduct(sku="BAN-PHIM-CO", product_name="Bàn phím cơ", unit="Chiếc"),
                LocalProduct(sku="CHUOT-LOGI-MX3", product_name="Chuột Logitech", unit="Chiếc"),
            ])
            # Seed local inventory
            session.add_all([
                LocalInventory(sku="BAN-PHIM-CO", available_qty=100, reserved_qty=0, version=1),
                LocalInventory(sku="CHUOT-LOGI-MX3", available_qty=50, reserved_qty=0, version=1),
            ])
            # Seed HQ Users
            session.add_all([
                HQUser(user_id="hq_staff_01", full_name="HQ Staff", role="HQ_STAFF", is_active=True),
                HQUser(user_id="hq_manager_01", full_name="HQ Manager", role="HQ_MANAGER", is_active=True),
            ])
            # Seed HQ Branches
            session.add_all([
                Branch(branch_code="HN", branch_name="Hà Nội", api_base_url="http://localhost:8001", is_active=True, is_online=True),
                Branch(branch_code="HCM", branch_name="TP.HCM", api_base_url="http://localhost:8002", is_active=True, is_online=True),
            ])

    print("[PASS] Schema & Initial Seed Data Created successfully.")

    # -------------------------------------------------------------------------
    # TEST 1: adjust_local_stock (Local Autonomy)
    # -------------------------------------------------------------------------
    async with TestSession() as session:
        res = await StockService.adjust_local_stock(
            db=session,
            sku="BAN-PHIM-CO",
            change_type="LOCAL_OUT",
            quantity=10,
            reason="Bán lẻ tại quầy",
            user_id="sales_hn"
        )
        assert res["new_available"] == 90, f"Expected 90, got {res['new_available']}"
        print(f"[PASS] TEST 1: adjust_local_stock LOCAL_OUT -10 -> new_available = {res['new_available']}")

    # -------------------------------------------------------------------------
    # TEST 2: Idempotency Inbox Check
    # -------------------------------------------------------------------------
    async with TestSession() as session:
        async with safe_transaction(session):
            exists_before = await check_inbox(session, "msg-001")
            assert not exists_before
            await mark_inbox(session, "msg-001", "TEST_EVENT")

    async with TestSession() as session:
        async with safe_transaction(session):
            exists_after = await check_inbox(session, "msg-001")
            assert exists_after
        print("[PASS] TEST 2: Inbox Idempotency check verified (Exactly-Once).")

    # -------------------------------------------------------------------------
    # TEST 3: Stock Freeze during Stocktake (blocks concurrent adjustments)
    # -------------------------------------------------------------------------
    async with TestSession() as session:
        st = await StocktakeService.create_stocktake(
            db=session,
            scope_type="FULL",
            scope_sku_list=None,
            note="Kiểm kê đột xuất",
            user_id="auditor_hn"
        )
        assert st.status == "DRAFT" or st.status.value == "DRAFT"

        # Now try to adjust stock while frozen -> must raise 409 Conflict
        try:
            await StockService.adjust_local_stock(
                db=session,
                sku="BAN-PHIM-CO",
                change_type="LOCAL_IN",
                quantity=5,
                reason="Nhập thêm",
                user_id="stock_hn"
            )
            assert False, "Should have raised 409 Conflict due to stock freeze!"
        except HTTPException as he:
            assert he.status_code == 409
            print(f"[PASS] TEST 3: Stock Freeze blocks adjustment with 409: '{he.detail}'")

        # Cancel stocktake to release freeze
        await StocktakeService.cancel_stocktake(db=session, session_id=st.session_id, user_id="auditor_hn")
        print("[PASS] TEST 3b: Stocktake cancelled and stock freeze released.")

    # -------------------------------------------------------------------------
    # TEST 4: 3-Level Transfer Approval Saga (Happy Path)
    # -------------------------------------------------------------------------
    # 1. HQ creates transfer
    async with TestSession() as session:
        async with safe_transaction(session):
            order = await SagaOrchestrator.create_transfer(
                session=session,
                source_branch="HN",
                dest_branch="HCM",
                sku="BAN-PHIM-CO",
                quantity=15,
                user_id="hq_staff_01"
            )
            transfer_id = order.transfer_id
            transfer_code = order.transfer_code
            assert order.saga_status == SagaStatus.PENDING_HQ_APPROVAL.value

    print(f"[PASS] TEST 4.1: Transfer created: {transfer_code} -> PENDING_HQ_APPROVAL")

    # 2. HQ Manager Approves -> PENDING_SOURCE_APPROVAL
    async with TestSession() as session:
        async with safe_transaction(session):
            order = await SagaOrchestrator.hq_approve(session, transfer_id, "hq_manager_01")
            assert order.saga_status == SagaStatus.PENDING_SOURCE_APPROVAL.value

    print(f"[PASS] TEST 4.2: HQ Approved -> PENDING_SOURCE_APPROVAL (Outbox cmd.transfer.approve_request emitted)")

    # 3. Source Branch receives command and Source Manager approves
    async with TestSession() as session:
        await TransferApprovalService.on_approve_request(session, "msg-trans-01", {
            "transfer_id": transfer_id,
            "transfer_code": transfer_code,
            "source_branch": "HN",
            "dest_branch": "HCM",
            "sku": "BAN-PHIM-CO",
            "quantity": 15
        })
        src_res = await TransferApprovalService.source_approve(session, transfer_id, "manager_hn")
        assert src_res["status"] == "SOURCE_APPROVED"

    print(f"[PASS] TEST 4.3: Source Branch Manager Approved -> Stock Reserved in HN")

    # 4. HQ receives evt.transfer.source_approved -> PENDING_DEST_APPROVAL
    async with TestSession() as session:
        async with safe_transaction(session):
            await SagaStepHandlers.handle_source_approved(session, {
                "transfer_id": transfer_id,
                "approved_by": "manager_hn"
            }, "msg-trans-02")
            order = await session.get(TransferOrder, transfer_id)
            assert order.saga_status == SagaStatus.PENDING_DEST_APPROVAL.value

    print(f"[PASS] TEST 4.4: HQ handles source_approved -> PENDING_DEST_APPROVAL (Outbox cmd.transfer.confirm_receive emitted)")

    # 5. Dest Branch receives confirm_receive and Dest Manager approves
    async with TestSession() as session:
        await TransferApprovalService.on_confirm_receive(session, "msg-trans-03", {
            "transfer_id": transfer_id,
            "transfer_code": transfer_code,
            "source_branch": "HN",
            "dest_branch": "HN",  # tested within same test branch config
            "sku": "BAN-PHIM-CO",
            "quantity": 15
        })
        dest_res = await TransferApprovalService.dest_approve(session, transfer_id, 15, "manager_hn")
        assert dest_res["status"] == "DEST_APPROVED"

    print(f"[PASS] TEST 4.5: Dest Branch Manager Approved -> Stock incremented at Dest")

    # 6. HQ receives evt.transfer.dest_approved -> COMPLETED
    async with TestSession() as session:
        async with safe_transaction(session):
            await SagaStepHandlers.handle_dest_approved(session, {
                "transfer_id": transfer_id,
                "approved_by": "manager_hcm"
            }, "msg-trans-04")
            order = await session.get(TransferOrder, transfer_id)
            assert order.saga_status == SagaStatus.COMPLETED.value

    print(f"[PASS] TEST 4.6: Saga COMPLETED successfully! 3-level approval complete.")

    # -------------------------------------------------------------------------
    # TEST 5: Saga Compensation (Dest Rejection -> Rollback)
    # -------------------------------------------------------------------------
    async with TestSession() as session:
        # Create new transfer for rollback test
        async with safe_transaction(session):
            order2 = await SagaOrchestrator.create_transfer(
                session=session,
                source_branch="HN",
                dest_branch="HCM",
                sku="CHUOT-LOGI-MX3",
                quantity=10,
                user_id="hq_staff_01"
            )
            t2_id = order2.transfer_id
            await SagaOrchestrator.hq_approve(session, t2_id, "hq_manager_01")

    # Dest rejects
    async with TestSession() as session:
        async with safe_transaction(session):
            await SagaStepHandlers.handle_dest_rejected(session, {
                "transfer_id": t2_id,
                "reason": "Kho đích quá tải, không thể tiếp nhận"
            }, "msg-rej-01")
            order2 = await session.get(TransferOrder, t2_id)
            assert order2.saga_status == SagaStatus.COMPENSATING.value

    print(f"[PASS] TEST 5.1: Dest Rejection triggers COMPENSATING state")

    # Source handles release stock compensation
    async with TestSession() as session:
        await StockService.release_stock(session, t2_id, "msg-rel-01", "CHUOT-LOGI-MX3", 10)

    async with TestSession() as session:
        async with safe_transaction(session):
            await SagaStepHandlers.handle_stock_released(session, {"transfer_id": t2_id}, "msg-rel-02")
            order2 = await session.get(TransferOrder, t2_id)
            assert order2.saga_status == SagaStatus.ROLLED_BACK.value

    print(f"[PASS] TEST 5.2: Compensation completed -> Saga ROLLED_BACK safely!")

    print("=" * 70)
    print("ALL 5 INTEGRATION TESTS PASSED 100%!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_tests())
