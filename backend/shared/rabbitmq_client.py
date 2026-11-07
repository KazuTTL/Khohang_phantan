# backend/shared/rabbitmq_client.py
"""
RabbitMQ Asynchronous Messaging Wrapper
Sử dụng aio-pika để giao tiếp phân tán qua Topic Exchange 'distributed_warehouse'
Hỗ trợ cơ chế tự động kết nối lại (Auto-reconnect) và Cross-Process Fallback khi Broker chưa sẵn sàng.
"""
import os
import json
import asyncio
import logging
from typing import Callable, Awaitable, List, Dict, Any
from pydantic import BaseModel
import httpx

try:
    import aio_pika
except ImportError:
    aio_pika = None

logger = logging.getLogger("RabbitMQClient")
logging.basicConfig(level=logging.INFO)

EXCHANGE_NAME = "distributed_warehouse"
DEFAULT_RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

NODE_URLS = {
    "HQ": "http://127.0.0.1:8000",
    "HN": "http://127.0.0.1:8001",
    "HCM": "http://127.0.0.1:8002"
}

class MessageBroker:
    _instance = None
    _mock_subscribers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}

    def __init__(self, amqp_url: str = DEFAULT_RABBITMQ_URL):
        self.amqp_url = amqp_url
        self.connection = None
        self.channel = None
        self.exchange = None
        self.is_connected = False
        self._closing = False

    async def connect(self):
        """Khởi tạo kết nối tới RabbitMQ và khai báo Topic Exchange"""
        if not aio_pika:
            logger.warning("[BROKER] aio-pika chưa được cài đặt. Hệ thống sẽ sử dụng Cross-Process Fallback.")
            return

        for attempt in range(1, 3):
            try:
                logger.info(f"[BROKER] Đang kết nối tới RabbitMQ ({self.amqp_url}) [Thử lần {attempt}/2]...")
                self.connection = await aio_pika.connect_robust(self.amqp_url, timeout=2.0)
                self.channel = await self.connection.channel()
                self.exchange = await self.channel.declare_exchange(
                    EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
                )
                self.is_connected = True
                logger.info(f"[BROKER] Kết nối thành công tới Exchange '{EXCHANGE_NAME}'!")
                return
            except Exception as e:
                logger.warning(f"[BROKER] Kết nối RabbitMQ thất bại ({e}).")
                await asyncio.sleep(0.5)

        logger.warning("[BROKER] Không kết nối được RabbitMQ Broker. Chuyển sang Cross-Process Fallback dự phòng.")
        self.is_connected = False

    async def publish(self, routing_key: str, message: Any):
        """Phát thông điệp ra Topic Exchange hoặc chuyển tiếp qua Cross-Process Fallback"""
        if isinstance(message, BaseModel):
            payload_str = message.model_dump_json()
        elif isinstance(message, dict):
            payload_str = json.dumps(message, ensure_ascii=False)
        else:
            payload_str = str(message)

        if self.is_connected and self.exchange:
            try:
                msg = aio_pika.Message(
                    body=payload_str.encode("utf-8"),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json"
                )
                await self.exchange.publish(msg, routing_key=routing_key)
                logger.info(f"[BROKER -> PUB] Key='{routing_key}' | Data={payload_str[:120]}...")
                return True
            except Exception as e:
                logger.error(f"[BROKER] Lỗi khi phát tin qua RabbitMQ: {e}")

        # Fallback chế độ khi chưa chạy RabbitMQ container:
        # Gửi sự kiện cho các process cục bộ và các node qua HTTP internal endpoint
        logger.info(f"[FALLBACK_BUS -> PUB] Key='{routing_key}' | Data={payload_str[:120]}...")
        data_dict = json.loads(payload_str)
        await self._dispatch_mock(routing_key, data_dict)

        # Chuyển tiếp tới các node khác
        asyncio.create_task(self._forward_to_other_nodes(routing_key, data_dict))
        return True

    async def _forward_to_other_nodes(self, routing_key: str, data: Dict[str, Any]):
        """Chuyển tiếp sự kiện qua HTTP tới các node tương ứng khi RabbitMQ offline"""
        targets = []
        if routing_key.startswith("cmd.transfer."):
            # cmd.transfer.reserve.HN -> Gửi tới HN
            parts = routing_key.split(".")
            branch = parts[-1]
            if branch in NODE_URLS:
                targets.append(NODE_URLS[branch])
        elif routing_key.startswith("evt."):
            # Sự kiện luôn gửi về HQ
            targets.append(NODE_URLS["HQ"])
            # Nếu là completed, gửi thêm cho source branch
            if routing_key == "evt.transfer.completed":
                src = data.get("data", {}).get("source_branch")
                if src and src in NODE_URLS and NODE_URLS[src] not in targets:
                    targets.append(NODE_URLS[src])

        for target_url in targets:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    await client.post(
                        f"{target_url}/internal/events",
                        json={"routing_key": routing_key, "data": data}
                    )
            except Exception:
                pass

    async def subscribe(self, queue_name: str, routing_keys: List[str], callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        """Đăng ký lắng nghe thông điệp trên Queue với danh sách routing keys"""
        if self.is_connected and self.channel:
            try:
                queue = await self.channel.declare_queue(queue_name, durable=True)
                for rkey in routing_keys:
                    await queue.bind(self.exchange, routing_key=rkey)
                    logger.info(f"[BROKER -> SUB] Queue '{queue_name}' bound to key '{rkey}'")

                async def on_message(message: aio_pika.IncomingMessage):
                    async with message.process():
                        try:
                            data = json.loads(message.body.decode("utf-8"))
                            await callback(data)
                        except Exception as err:
                            logger.error(f"[BROKER -> ERR] Callback queue '{queue_name}' lỗi: {err}")

                await queue.consume(on_message)
                return
            except Exception as e:
                logger.error(f"[BROKER] Lỗi đăng ký Queue '{queue_name}': {e}")

        # Đăng ký vào in-memory bus của process hiện tại
        for rkey in routing_keys:
            if rkey not in self._mock_subscribers:
                self._mock_subscribers[rkey] = []
            self._mock_subscribers[rkey].append(callback)
            logger.info(f"[FALLBACK_BUS -> SUB] Handler registered for key '{rkey}'")

    async def _dispatch_mock(self, routing_key: str, data: Dict[str, Any]):
        """Phân phối routing key pattern (*, #) cho subscriber cục bộ"""
        for pattern, callbacks in self._mock_subscribers.items():
            matched = False
            if pattern == routing_key or pattern == "#":
                matched = True
            elif pattern.endswith(".#") and routing_key.startswith(pattern[:-2]):
                matched = True
            elif pattern.endswith(".*") and routing_key.rsplit(".", 1)[0] == pattern.rsplit(".", 1)[0]:
                matched = True
            elif pattern.count(".") == routing_key.count("."):
                p_parts = pattern.split(".")
                r_parts = routing_key.split(".")
                if all(p == "*" or p == r for p, r in zip(p_parts, r_parts)):
                    matched = True

            if matched:
                for cb in callbacks:
                    asyncio.create_task(cb(data))

    async def close(self):
        """Đóng kết nối Broker an toàn"""
        self._closing = True
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            self.is_connected = False
            logger.info("[BROKER] Đã ngắt kết nối RabbitMQ.")

_broker_instance = None

def get_broker(amqp_url: str = DEFAULT_RABBITMQ_URL) -> MessageBroker:
    global _broker_instance
    if _broker_instance is None:
        _broker_instance = MessageBroker(amqp_url)
    return _broker_instance
