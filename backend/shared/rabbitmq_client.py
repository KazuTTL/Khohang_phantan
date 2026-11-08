# backend/shared/rabbitmq_client.py
import asyncio
import json
import logging
from typing import Any, Callable, Coroutine
import aio_pika
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractIncomingMessage

from shared.config import shared_config
from shared.messaging_topology import EXCHANGE_NAME, DLQ_EXCHANGE_NAME, DLQ_QUEUE_NAME

logger = logging.getLogger("RabbitMQClient")


class RabbitMQClient:
    """
    Asynchronous RabbitMQ Client using aio-pika.
    Quản lý kết nối, Topic Exchange 'distributed_warehouse', Dead-letter Queue và Consumer.
    """

    def __init__(self, amqp_url: str | None = None):
        self.amqp_url = amqp_url or shared_config.RABBITMQ_URL
        self.connection: AbstractConnection | None = None
        self.channel: AbstractChannel | None = None
        self.exchange = None
        self.dlx_exchange = None
        self.is_connected = False
        self._closing = False

    async def connect(self, max_retries: int = 3, retry_delay: float = 3.0) -> bool:
        """Kết nối tới RabbitMQ và thiết lập Topology Exchange"""
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"[BROKER] Đang kết nối tới RabbitMQ ({self.amqp_url}) [Lần {attempt}/{max_retries}]...")
                self.connection = await aio_pika.connect_robust(self.amqp_url)
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=20)

                # 1. Khởi tạo Dead Letter Exchange & Queue
                self.dlx_exchange = await self.channel.declare_exchange(
                    DLQ_EXCHANGE_NAME,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True
                )
                dlq = await self.channel.declare_queue(DLQ_QUEUE_NAME, durable=True)
                await dlq.bind(self.dlx_exchange, routing_key="#")

                # 2. Khởi tạo Topic Exchange chính
                self.exchange = await self.channel.declare_exchange(
                    EXCHANGE_NAME,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True
                )

                self.is_connected = True
                logger.info(f"[BROKER] Kết nối RabbitMQ thành công. Topic Exchange '{EXCHANGE_NAME}' đã sẵn sàng.")
                return True
            except Exception as e:
                logger.warning(f"[BROKER] Kết nối RabbitMQ lần {attempt} thất bại: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)

        logger.error("[BROKER] Không thể kết nối tới RabbitMQ Broker sau các lần thử.")
        self.is_connected = False
        return False

    async def publish(self, routing_key: str, message: dict[str, Any], correlation_id: str | None = None) -> bool:
        """
        Publish thông điệp lên Topic Exchange 'distributed_warehouse'.
        """
        if not self.is_connected or not self.exchange:
            logger.error(f"[PUBLISH FAILED] Broker chưa kết nối. Không thể gửi routing_key='{routing_key}'")
            return False

        try:
            body = json.dumps(message, default=str).encode("utf-8")
            pika_msg = aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                correlation_id=correlation_id
            )
            await self.exchange.publish(pika_msg, routing_key=routing_key)
            logger.info(f"[PUBLISH OK] routing_key='{routing_key}' correlation_id='{correlation_id}'")
            return True
        except Exception as e:
            logger.error(f"[PUBLISH ERROR] Lỗi publish routing_key='{routing_key}': {e}")
            return False

    async def publish_to_dlq(self, routing_key: str, message: dict[str, Any], reason: str) -> None:
        """Đẩy thông điệp lỗi vào Dead Letter Queue để điều tra sau"""
        if not self.dlx_exchange:
            return
        try:
            body = json.dumps(message, default=str).encode("utf-8")
            pika_msg = aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                headers={"x-dlq-reason": reason}
            )
            await self.dlx_exchange.publish(pika_msg, routing_key=f"dlq.{routing_key}")
            logger.warning(f"[DLQ PUBLISH] Đã đẩy message vào DLQ: routing_key='dlq.{routing_key}', reason='{reason}'")
        except Exception as e:
            logger.error(f"[DLQ ERROR] Không thể gửi DLQ: {e}")

    async def subscribe(
        self,
        queue_name: str,
        binding_keys: list[str],
        callback: Callable[[dict[str, Any], str], Coroutine[Any, Any, None]]
    ) -> None:
        """
        Khai báo hàng đợi, liên kết với Topic Exchange và lắng nghe sự kiện.
        Tự động Dead-letter nếu xử lý thất bại nhiều lần.
        """
        if not self.channel or not self.exchange:
            raise RuntimeError("RabbitMQ channel/exchange chưa sẵn sàng để subscribe.")

        queue = await self.channel.declare_queue(
            queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": DLQ_EXCHANGE_NAME,
                "x-dead-letter-routing-key": f"dlq.{queue_name}"
            }
        )

        for key in binding_keys:
            await queue.bind(self.exchange, routing_key=key)
            logger.info(f"[SUBSCRIBE] Queue '{queue_name}' bound to routing_key='{key}'")

        async def _message_consumer(message: AbstractIncomingMessage):
            async with message.process(requeue=False, ignore_processed=True):
                try:
                    payload = json.loads(message.body.decode("utf-8"))
                    routing_key = message.routing_key or ""
                    await callback(payload, routing_key)
                except Exception as ex:
                    logger.error(f"[CONSUMER ERROR] Lỗi xử lý message trên queue '{queue_name}': {ex}", exc_info=True)
                    # Gửi vào DLQ
                    try:
                        failed_data = json.loads(message.body.decode("utf-8"))
                        await self.publish_to_dlq(message.routing_key or "unknown", failed_data, str(ex))
                    except Exception:
                        pass

        await queue.consume(_message_consumer)
        logger.info(f"[CONSUMER STARTED] Đang lắng nghe trên queue '{queue_name}'")

    async def close(self) -> None:
        """Đóng an toàn kết nối RabbitMQ"""
        self._closing = True
        if self.channel and not self.channel.is_closed:
            await self.channel.close()
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        self.is_connected = False
        logger.info("[BROKER] Đã đóng kết nối RabbitMQ an toàn.")
