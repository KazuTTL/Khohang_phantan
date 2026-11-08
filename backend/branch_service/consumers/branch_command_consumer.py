# backend/branch_service/consumers/branch_command_consumer.py
import logging
from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.config import branch_settings
from branch_service.database import AsyncSessionLocal
from branch_service.models import StockLedger
from branch_service.services.outbox_service import OutboxService
from branch_service.services.stock_service import StockService
from shared.event_schemas import (
    CmdImportTransferPayload, CmdReleaseStockPayload,
    CmdReserveStockPayload, EvtInventoryUpdatedPayload, EvtTransferCompletedPayload
)
from shared.idempotency import check_and_mark_inbox
from shared.messaging_topology import ROUTING_EVT_INVENTORY_UPDATED

logger = logging.getLogger(f"BranchCommandConsumer_{branch_settings.BRANCH_CODE}")
CONSUMER_NAME = f"BranchCommandConsumer_{branch_settings.BRANCH_CODE}"


async def process_branch_command(message_data: dict[str, Any], routing_key: str) -> None:
    """
    Consumer tiếp nhận các Command từ Saga Orchestrator gửi tới chi nhánh này.
    Bảo đảm tính Idempotent bằng Inbox Pattern.
    """
    msg_id = message_data.get("message_id") or ""
    event_type = message_data.get("event_type") or ""
    payload_dict = message_data.get("payload") or {}

    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 1. NGUYÊN TẮC 4: Kiểm tra tính Idempotent qua Inbox
            is_new = await check_and_mark_inbox(session, msg_id, CONSUMER_NAME)
            if not is_new:
                logger.info(f"[IDEMPOTENT SKIP] Branch {branch_settings.BRANCH_CODE}: Message {msg_id} ({event_type}) đã xử lý trước đó.")
                return

            logger.info(f"[BRANCH CONSUME] Kho {branch_settings.BRANCH_CODE} xử lý {event_type} (msg_id={msg_id})")

            # 2. Lệnh Phase 1: Giữ hàng tại kho xuất
            if event_type == "CMD_RESERVE_STOCK":
                cmd = CmdReserveStockPayload(**payload_dict)
                await StockService.reserve_stock_for_saga(
                    session=session,
                    transfer_id=cmd.transfer_id,
                    dest_branch=cmd.dest_branch,
                    sku=cmd.sku,
                    quantity=cmd.quantity
                )

            # 3. Lệnh Bù trừ (Rollback): Hoàn trả hàng giữ tại kho xuất
            elif event_type == "CMD_RELEASE_STOCK":
                cmd = CmdReleaseStockPayload(**payload_dict)
                await StockService.release_stock_compensation(
                    session=session,
                    transfer_id=cmd.transfer_id,
                    sku=cmd.sku,
                    quantity=cmd.quantity,
                    reason=cmd.reason
                )

            # 4. Lệnh Phase 2: Nhập hàng điều chuyển tại kho đích
            elif event_type == "CMD_IMPORT_TRANSFER":
                cmd = CmdImportTransferPayload(**payload_dict)
                # Tự động tiếp nhận và nhập kho tại kho đích
                await StockService.import_incoming_stock(
                    session=session,
                    transfer_id=cmd.transfer_id,
                    source_branch=cmd.source_branch,
                    sku=cmd.sku,
                    quantity=cmd.quantity
                )

            # 5. Sự kiện hoàn tất Saga: Kho xuất trừ hẳn số lượng đang giữ (Reserved -= quantity)
            elif event_type == "EVT_TRANSFER_COMPLETED":
                evt = EvtTransferCompletedPayload(**payload_dict)
                if evt.source_branch == branch_settings.BRANCH_CODE:
                    # Kho xuất trừ hẳn số lượng Reserved
                    inv_tuple = await StockService._lock_and_get_inventory(session, evt.sku)
                    if inv_tuple:
                        avail, res_qty = inv_tuple
                        new_res = max(0, res_qty - evt.quantity)
                        await session.execute(
                            text("UPDATE Local_Inventory SET reserved_qty = :res WHERE sku = :sku"),
                            {"res": new_res, "sku": evt.sku}
                        )
                        ledger = StockLedger(
                            transaction_type="SAGA_OUT",
                            sku=evt.sku,
                            quantity=evt.quantity,
                            available_after=avail,
                            reserved_after=new_res,
                            reference_id=evt.transfer_id,
                            idempotency_key=f"SAGA-OUT-{evt.transfer_id}",
                            note=f"Xuất kho hoàn tất giao dịch chuyển tới {evt.dest_branch}"
                        )
                        session.add(ledger)

                        OutboxService.create_outbox_message(
                            session=session,
                            event_type="EVT_INVENTORY_UPDATED",
                            routing_key=ROUTING_EVT_INVENTORY_UPDATED,
                            source=f"BRANCH_{branch_settings.BRANCH_CODE}",
                            payload_model=EvtInventoryUpdatedPayload(
                                branch_code=branch_settings.BRANCH_CODE,
                                sku=evt.sku,
                                available_qty=avail,
                                reserved_qty=new_res,
                                change_type="SAGA_OUT",
                                reference_id=evt.transfer_id
                            ),
                            correlation_id=evt.transfer_id
                        )
                        logger.info(f"[SAGA COMMIT OUT] Kho {branch_settings.BRANCH_CODE} trừ dứt điểm {evt.quantity} {evt.sku} cho đơn {evt.transfer_id}")
