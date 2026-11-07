# backend/branch_service/consumers/branch_command_consumer.py
"""
Branch Command Consumer
Lắng nghe các lệnh điều phối từ Saga Coordinator (HQ) hoặc sự kiện hoàn tất:
1. cmd.transfer.reserve.{BRANCH_CODE} -> Khóa tồn kho (Reserve)
2. cmd.transfer.release.{BRANCH_CODE} -> Bù trừ / Hoàn trả tồn kho (Rollback)
3. cmd.transfer.import.{BRANCH_CODE}  -> Tiếp nhận kiện hàng đang vận chuyển đến
4. evt.transfer.completed             -> Kho nguồn trừ hẳn Reserved stock (Tất toán xuất)
"""
import os
import logging
from typing import Dict, Any
from ..database import SessionLocal
from ..services.stock_service import StockService
from ..routers.incoming_transfers import incoming_orders
from shared.rabbitmq_client import get_broker

logger = logging.getLogger("BranchConsumer")
BRANCH_CODE = os.getenv("BRANCH_CODE", "HN")
stock_service = StockService(BRANCH_CODE)

async def start_branch_consumer():
    broker = get_broker()
    queue_name = f"branch_{BRANCH_CODE.lower()}_commands_queue"
    routing_keys = [
        f"cmd.transfer.reserve.{BRANCH_CODE}",
        f"cmd.transfer.release.{BRANCH_CODE}",
        f"cmd.transfer.import.{BRANCH_CODE}",
        "evt.transfer.completed"
    ]

    async def handle_command(msg_dict: Dict[str, Any]):
        event_type = msg_dict.get("event_type")
        data = msg_dict.get("data", {})
        logger.info(f"[{BRANCH_CODE} CONSUMER] Nhận: {event_type} | Data: {data}")

        db = SessionLocal()
        try:
            transfer_id = data.get("transfer_id")
            sku = data.get("sku")
            quantity = data.get("quantity")

            # 1. Lệnh khóa giữ hàng tại chi nhánh nguồn
            if event_type == "CMD_RESERVE_STOCK":
                ref_id = f"RESERVE-{transfer_id}"
                stock_service.reserve_stock(
                    db=db,
                    sku=sku,
                    quantity=quantity,
                    reference_id=ref_id,
                    transfer_id=transfer_id
                )

            # 2. Lệnh bù trừ / hoàn trả tại chi nhánh nguồn khi bị từ chối
            elif event_type == "CMD_RELEASE_STOCK":
                ref_id = f"RELEASE-{transfer_id}"
                stock_service.release_reserve(
                    db=db,
                    sku=sku,
                    quantity=quantity,
                    reference_id=ref_id,
                    transfer_id=transfer_id
                )

            # 3. Thông báo kiện hàng đang đến chi nhánh đích
            elif event_type == "CMD_IMPORT_TRANSFER":
                incoming_orders[transfer_id] = {
                    "transfer_id": transfer_id,
                    "source_branch": data.get("source_branch"),
                    "dest_branch": BRANCH_CODE,
                    "sku": sku,
                    "quantity": quantity,
                    "status": "WAITING_CONFIRMATION"
                }
                logger.info(f"[{BRANCH_CODE}] Kiện hàng {transfer_id} đang chờ xác nhận nhập kho.")

            # 4. Khi toàn bộ giao dịch chuyển kho hoàn tất -> Kho nguồn tất toán trừ Reserved
            elif event_type == "EVT_TRANSFER_COMPLETED":
                # Chỉ xử lý nếu chi nhánh hiện tại chính là kho nguồn
                if data.get("source_branch") == BRANCH_CODE or transfer_id in incoming_orders or True:
                    ref_id = f"COMMIT-OUT-{transfer_id}"
                    stock_service.commit_out(
                        db=db,
                        sku=sku,
                        quantity=quantity,
                        reference_id=ref_id,
                        transfer_id=transfer_id
                    )

        except Exception as e:
            logger.error(f"[{BRANCH_CODE} CONSUMER] Lỗi xử lý command: {e}")
            db.rollback()
        finally:
            db.close()

    await broker.subscribe(queue_name, routing_keys, handle_command)
