# backend/branch_service/services/outbox_worker.py
"""
Outbox Worker: Đảm bảo giao tiếp phân tán tin cậy (Reliable Messaging)
Quét định kỳ các thông điệp chưa gửi trong bảng Outbox_Events (SU_KIEN_DONG_BO) để phát lên RabbitMQ.
Hỗ trợ kiểm chứng thực tế tình huống đứt cáp WAN (WAN Disconnect Simulation).
"""
import json
import asyncio
import logging
from ..database import SessionLocal
from ..models import OutboxEvent
from shared.rabbitmq_client import get_broker
from shared.cluster_infra import is_wan_online

logger = logging.getLogger("OutboxWorker")


async def run_outbox_worker(interval_seconds: float = 1.0):
    broker = get_broker()
    logger.info("[OUTBOX WORKER] Đã khởi động tiến trình quét Outbox...")

    while True:
        try:
            db = SessionLocal()
            try:
                pending_events = (
                    db.query(OutboxEvent)
                    .filter(OutboxEvent.is_published == False)
                    .order_by(OutboxEvent.created_at.asc())
                    .limit(20)
                    .all()
                )

                if pending_events and not is_wan_online():
                    for evt in pending_events:
                        evt.retry_count += 1
                        evt.delivery_status = "FAILED"
                    db.commit()
                    logger.warning(f"[OUTBOX] Mạng WAN đang ngắt! Giữ lại {len(pending_events)} sự kiện trong hàng đợi.")
                else:
                    for evt in pending_events:
                        try:
                            evt.delivery_status = "PROCESSING"
                            payload_data = json.loads(evt.payload)
                            success = await broker.publish(evt.routing_key, payload_data)
                            if success:
                                evt.is_published = True
                                evt.delivery_status = "COMPLETED"
                                db.commit()
                                logger.info(f"[OUTBOX] Đã phát thành công Event {evt.event_id} -> Key: {evt.routing_key}")
                            else:
                                evt.retry_count += 1
                                evt.delivery_status = "FAILED"
                                db.commit()
                                break
                        except Exception as err:
                            evt.retry_count += 1
                            evt.delivery_status = "FAILED"
                            db.commit()
                            logger.error(f"[OUTBOX] Lỗi khi phát Event {evt.event_id} (lần {evt.retry_count}): {err}")
                            break
            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("[OUTBOX WORKER] Nhận tín hiệu dừng tiến trình.")
            break
        except Exception as e:
            logger.error(f"[OUTBOX WORKER] Ngoại lệ vòng lặp: {e}")

        await asyncio.sleep(interval_seconds)
