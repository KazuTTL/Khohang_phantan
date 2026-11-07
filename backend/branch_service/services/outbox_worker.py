# backend/branch_service/services/outbox_worker.py
"""
Outbox Worker: Đảm bảo giao tiếp phân tán tin cậy (Reliable Messaging)
Quét định kỳ các thông điệp chưa gửi trong bảng Outbox_Events để phát lên RabbitMQ.
Giải quyết bài toán: Mạng gián đoạn hoặc RabbitMQ restart đột ngột không làm mất thông điệp.
"""
import json
import asyncio
import logging
from ..database import SessionLocal
from ..models import OutboxEvent
from shared.rabbitmq_client import get_broker

logger = logging.getLogger("OutboxWorker")

async def run_outbox_worker(interval_seconds: float = 2.0):
    broker = get_broker()
    logger.info("[OUTBOX WORKER] Đã khởi động tiến trình quét Outbox...")

    while True:
        try:
            db = SessionLocal()
            try:
                # Quét các sự kiện chưa phát (tối đa 20 bản ghi mỗi đợt)
                pending_events = db.query(OutboxEvent).filter(OutboxEvent.is_published == False).order_by(OutboxEvent.created_at.asc()).limit(20).all()

                for evt in pending_events:
                    try:
                        payload_data = json.loads(evt.payload)
                        success = await broker.publish(evt.routing_key, payload_data)
                        if success:
                            evt.is_published = True
                            db.commit()
                            logger.info(f"[OUTBOX] Đã phát thành công Event {evt.event_id} -> Key: {evt.routing_key}")
                    except Exception as err:
                        logger.error(f"[OUTBOX] Lỗi khi phát Event {evt.event_id}: {err}")
                        break # Tạm dừng đợt này, thử lại đợt kế tiếp
            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("[OUTBOX WORKER] Nhận tín hiệu dừng tiến trình.")
            break
        except Exception as e:
            logger.error(f"[OUTBOX WORKER] Ngoại lệ vòng lặp: {e}")

        await asyncio.sleep(interval_seconds)
