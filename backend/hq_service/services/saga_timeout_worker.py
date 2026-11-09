# backend/hq_service/services/saga_timeout_worker.py
"""
Saga Timeout Coordinator:
Tự động kích hoạt bù trừ hoàn tác nếu giao dịch bị treo do phân rã mạng (Network Partition)
hoặc Chi nhánh đích bị sập nguồn (Node Crash) không phản hồi.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from ..database import SessionLocal
from ..models import TransferOrder
from shared.event_schemas import RabbitMQMessage, TransferMessageData
from shared.rabbitmq_client import get_broker

logger = logging.getLogger("SagaTimeoutWorker")

# Thời gian chờ tối đa cho 1 giao dịch Saga điều chuyển (giây)
SAGA_TIMEOUT_SECONDS = 60

async def run_saga_timeout_worker(interval_seconds: float = 5.0):
    broker = get_broker()
    logger.info(f"[SAGA TIMEOUT] Bắt đầu tiến trình giám sát Timeout (Ngưỡng = {SAGA_TIMEOUT_SECONDS}s)...")

    while True:
        try:
            db = SessionLocal()
            try:
                now = datetime.utcnow()
                cutoff_time = now - timedelta(seconds=SAGA_TIMEOUT_SECONDS)

                # Tìm các đơn bị treo ở RESERVED_IN_TRANSIT quá hạn
                stuck_orders = db.query(TransferOrder).filter(
                    TransferOrder.saga_status == "RESERVED_IN_TRANSIT",
                    TransferOrder.created_at <= cutoff_time
                ).all()

                for order in stuck_orders:
                    logger.warning(
                        f"[SAGA TIMEOUT] Đơn {order.transfer_id} ({order.source_branch}->{order.dest_branch}) "
                        f"bị treo quá {SAGA_TIMEOUT_SECONDS}s. Kích hoạt giao dịch bù trừ tự động!"
                    )
                    order.saga_status = "COMPENSATING"
                    order.error_reason = f"Giao dịch quá hạn {SAGA_TIMEOUT_SECONDS}s không có phản hồi từ {order.dest_branch}. Tự động bù trừ hoàn trả."
                    db.commit()

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
            finally:
                db.close()
        except asyncio.CancelledError:
            logger.info("[SAGA TIMEOUT] Dừng tiến trình Timeout Worker.")
            break
        except Exception as e:
            logger.error(f"[SAGA TIMEOUT] Lỗi vòng lặp kiểm tra: {e}")

        await asyncio.sleep(interval_seconds)
