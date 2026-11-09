# backend/shared/rabbitmq_client.py
import json
import logging
from typing import Any, Callable, Coroutine
import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage

from shared.event_schemas import Envelope
from shared.messaging_topology import EXCHANGE

logger = logging.getLogger("RabbitMQClient")


class EventPublisher:
    """
    Publisher phát sự kiện qua Topic Exchange 'distributed_warehouse' với Publisher Confirms.
    """
    def __init__(self, channel: AbstractChannel):
        self.channel = channel
        self.exchange = None

    async def init(self) -> None:
        """Khai báo exchange và đảm bảo chế độ confirm"""
        self.exchange = await self.channel.declare_exchange(
            EXCHANGE,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )

    async def publish(
        self,
        routing_key: str,
        event_type: str,
        data: dict[str, Any],
        message_id: str | None = None
    ) -> str:
        """
        Đóng gói Envelope và publish thông điệp bền vững (persistent).
        Trả về message_id.
        """
        envelope = Envelope(
            message_id=message_id or "",
            event_type=event_type,
            data=data
        ) if message_id else Envelope(
            event_type=event_type,
            data=data
        )

        body = json.dumps(envelope.model_dump(mode="json"), default=str).encode("utf-8")
        pika_msg = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=envelope.message_id
        )

        if not self.exchange:
            await self.init()

        await self.exchange.publish(pika_msg, routing_key=routing_key)
        logger.info(f"[PUBLISH OK] event_type='{event_type}', rkey='{routing_key}', msg_id='{envelope.message_id}'")
        return envelope.message_id


class EventConsumer:
    """
    Consumer tiêu thụ thông điệp từ một hàng đợi cụ thể với Manual Acknowledgment.
    Tự động Nack và đẩy vào Dead Letter Queue khi phát sinh ngoại lệ.
    """
    def __init__(self, channel: AbstractChannel, queue_name: str):
        self.channel = channel
        self.queue_name = queue_name

    async def consume(
        self,
        handler: Callable[[AbstractIncomingMessage, Envelope], Coroutine[Any, Any, None]],
        prefetch: int = 10
    ) -> None:
        """
        Bắt đầu lắng nghe hàng đợi với QoS prefetch.
        """
        await self.channel.set_qos(prefetch_count=prefetch)
        queue = await self.channel.get_queue(self.queue_name)

        async def _on_message(message: AbstractIncomingMessage):
            async with message.process(requeue=False, ignore_processed=True):
                try:
                    raw_data = json.loads(message.body.decode("utf-8"))
                    envelope = Envelope(**raw_data)
                    await handler(message, envelope)
                except Exception as ex:
                    logger.error(
                        f"[CONSUMER FAILED] Queue '{self.queue_name}' error: {ex}",
                        exc_info=True
                    )
                    # Message được nack không requeue -> tự động chuyển sang DLX
                    raise

        await queue.consume(_on_message)
        logger.info(f"[CONSUMER STARTED] Đang lắng nghe queue '{self.queue_name}'")
