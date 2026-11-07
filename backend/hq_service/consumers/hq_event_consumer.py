# backend/hq_service/consumers/hq_event_consumer.py
"""
HQ Saga Orchestrator Consumer
Lắng nghe các sự kiện từ các Branch Node để điều phối các bước tiếp theo trong chuỗi Saga
và đồng bộ Global Inventory Snapshot.
"""
import logging
from typing import Dict, Any
from ..database import SessionLocal
from ..models import TransferOrder, GlobalInventorySnapshot
from shared.event_schemas import RabbitMQMessage, TransferMessageData
from shared.rabbitmq_client import get_broker

logger = logging.getLogger("HQEventConsumer")

async def start_hq_consumer():
    broker = get_broker()
    queue_name = "hq_saga_events_queue"
    routing_keys = [
        "evt.transfer.reserved",
        "evt.transfer.reserve_failed",
        "evt.transfer.completed",
        "evt.transfer.rejected",
        "evt.transfer.released",
        "evt.inventory.updated"
    ]

    async def handle_event(msg_dict: Dict[str, Any]):
        event_type = msg_dict.get("event_type")
        data = msg_dict.get("data", {})
        logger.info(f"[HQ CONSUMER] Nhận sự kiện: {event_type} | Data: {data}")

        db = SessionLocal()
        try:
            # 1. Đồng bộ tồn kho toàn cục
            if event_type == "EVT_INVENTORY_UPDATED":
                branch_code = data.get("branch_code")
                sku = data.get("sku")
                avail = data.get("available_qty", 0)
                reserved = data.get("reserved_qty", 0)

                snap = db.query(GlobalInventorySnapshot).filter(
                    GlobalInventorySnapshot.branch_code == branch_code,
                    GlobalInventorySnapshot.sku == sku
                ).first()

                if snap:
                    snap.available_qty = avail
                    snap.reserved_qty = reserved
                else:
                    snap = GlobalInventorySnapshot(
                        branch_code=branch_code,
                        sku=sku,
                        available_qty=avail,
                        reserved_qty=reserved
                    )
                    db.add(snap)
                db.commit()
                logger.info(f"[HQ INVENTORY] Cập nhật Snapshot: Chi nhánh {branch_code} | {sku} -> Avail={avail}, Reserved={reserved}")
                return

            # 2. Xử lý trạng thái Saga Điều chuyển
            transfer_id = data.get("transfer_id")
            if not transfer_id:
                return

            order = db.query(TransferOrder).filter(TransferOrder.transfer_id == transfer_id).first()
            if not order:
                logger.warning(f"[HQ SAGA] Không tìm thấy đơn {transfer_id} trong DB_HQ")
                return

            # A. Kho nguồn đã khóa hàng thành công
            if event_type == "EVT_STOCK_RESERVED":
                order.saga_status = "RESERVED_IN_TRANSIT"
                db.commit()
                logger.info(f"[HQ SAGA] Đơn {transfer_id}: Chuyển sang RESERVED_IN_TRANSIT. Gửi lệnh nhập kho tới {order.dest_branch}.")

                # Phát lệnh CMD_IMPORT_TRANSFER tới kho đích
                cmd_import = RabbitMQMessage(
                    event_type="CMD_IMPORT_TRANSFER",
                    data=TransferMessageData(
                        transfer_id=order.transfer_id,
                        source_branch=order.source_branch,
                        dest_branch=order.dest_branch,
                        sku=order.sku,
                        quantity=order.quantity
                    )
                )
                await broker.publish(f"cmd.transfer.import.{order.dest_branch}", cmd_import)

            # B. Kho nguồn khóa hàng thất bại (Hết hàng hoặc lỗi)
            elif event_type == "EVT_RESERVE_FAILED":
                order.saga_status = "FAILED"
                order.error_reason = data.get("reason", "Kho nguồn không đủ tồn kho khả dụng")
                db.commit()
                logger.warning(f"[HQ SAGA] Đơn {transfer_id}: Khóa hàng thất bại. Đóng đơn với FAILED.")

            # C. Kho đích đã xác nhận nhập kho thành công -> Hoàn tất Saga
            elif event_type == "EVT_TRANSFER_COMPLETED":
                order.saga_status = "COMPLETED"
                db.commit()
                logger.info(f"[HQ SAGA] Đơn {transfer_id}: Hoàn tất giao dịch chuyển kho (COMPLETED)!")

            # D. Kho đích từ chối nhận hàng -> Kích hoạt Giao dịch bù trừ (Rollback)
            elif event_type == "EVT_TRANSFER_REJECTED":
                order.saga_status = "COMPENSATING"
                order.error_reason = data.get("reason", "Kho đích từ chối nhận hàng")
                db.commit()
                logger.warning(f"[HQ SAGA] Đơn {transfer_id}: Bị từ chối ({order.error_reason}). Kích hoạt bù trừ CMD_RELEASE_STOCK tới {order.source_branch}.")

                # Phát lệnh hoàn trả hàng cho kho nguồn
                cmd_release = RabbitMQMessage(
                    event_type="CMD_RELEASE_STOCK",
                    data=TransferMessageData(
                        transfer_id=order.transfer_id,
                        source_branch=order.source_branch,
                        dest_branch=order.dest_branch,
                        sku=order.sku,
                        quantity=order.quantity,
                        reason=order.error_reason
                    )
                )
                await broker.publish(f"cmd.transfer.release.{order.source_branch}", cmd_release)

            # E. Kho nguồn đã hoàn trả hàng thành công
            elif event_type == "EVT_STOCK_RELEASED":
                order.saga_status = "CANCELLED_ROLLED_BACK"
                db.commit()
                logger.info(f"[HQ SAGA] Đơn {transfer_id}: Đã hoàn tác xong toàn bộ (CANCELLED_ROLLED_BACK).")

        except Exception as e:
            logger.error(f"[HQ CONSUMER] Lỗi xử lý sự kiện: {e}")
            db.rollback()
        finally:
            db.close()

    await broker.subscribe(queue_name, routing_keys, handle_event)
