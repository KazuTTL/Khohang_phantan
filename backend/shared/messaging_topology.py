# backend/shared/messaging_topology.py
import aio_pika
from aio_pika.abc import AbstractChannel

EXCHANGE = "distributed_warehouse"
DLX = "distributed_warehouse.dlx"
DLQ_QUEUE_NAME = "q.dlq"

# Routing Key Constants
ROUTING_EVT_INVENTORY_UPDATED = "evt.inventory.updated"
ROUTING_EVT_CATALOG_UPDATED = "catalog.sync"
ROUTING_EVT_TRANSFER_COMPLETED = "evt.transfer.completed"
ROUTING_EVT_STOCKTAKE_APPROVED = "evt.stocktake.approved"

ROUTING_CMD_APPROVE_REQUEST = "cmd.transfer.approve_request"
ROUTING_CMD_CONFIRM_RECEIVE = "cmd.transfer.confirm_receive"
ROUTING_CMD_RELEASE = "cmd.transfer.release"
ROUTING_CMD_STOCKTAKE_FINALIZE = "cmd.stocktake.finalize"

QUEUES_MAPPING: dict[str, str] = {
    "cmd.transfer.approve_request.*": "q.transfer.approve_request",
    "cmd.transfer.confirm_receive.*": "q.transfer.confirm_receive",
    "cmd.transfer.release.*": "q.transfer.release",
    "cmd.stocktake.finalize.*": "q.stocktake.finalize",
    "evt.transfer.*": "q.hq.transfer_events",
    "evt.inventory.*": "q.hq.inventory_events",
    "evt.stocktake.*": "q.hq.stocktake_events",
    "catalog.sync": "q.branch.catalog_sync"
}


def get_branch_queue_name(branch_code: str) -> str:
    """Trả về tên queue lệnh độc lập cho từng chi nhánh"""
    return f"q.branch.{branch_code.strip().lower()}.commands"


def get_hq_queue_name() -> str:
    """Trả về tên queue tiếp nhận events tại HQ"""
    return "q.hq.transfer_events"


def get_command_routing_key(base_command: str, branch_code: str) -> str:
    """Tạo routing key gửi lệnh tới chi nhánh cụ thể: cmd.transfer.approve_request.HN"""
    return f"{base_command}.{branch_code.strip().upper()}"


async def declare_topology(channel: AbstractChannel):
    """
    Khai báo toàn bộ Topology RabbitMQ:
    1. Topic Exchange 'distributed_warehouse'
    2. Dead Letter Exchange (DLX) và Dead Letter Queue
    3. Các hàng đợi nghiệp vụ và liên kết (bindings) theo routing key pattern
    """
    # 1. Dead Letter Exchange & Queue
    dlx_exchange = await channel.declare_exchange(
        DLX,
        aio_pika.ExchangeType.TOPIC,
        durable=True
    )
    dlq = await channel.declare_queue(DLQ_QUEUE_NAME, durable=True)
    await dlq.bind(dlx_exchange, routing_key="#")

    # 2. Main Topic Exchange
    exchange = await channel.declare_exchange(
        EXCHANGE,
        aio_pika.ExchangeType.TOPIC,
        durable=True
    )

    # 3. Queues & Bindings
    for routing_pattern, queue_name in QUEUES_MAPPING.items():
        queue = await channel.declare_queue(
            queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": DLX,
                "x-dead-letter-routing-key": f"dlq.{queue_name}"
            }
        )
        await queue.bind(exchange, routing_key=routing_pattern)

    return exchange
