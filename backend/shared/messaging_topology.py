# backend/shared/messaging_topology.py
"""
Messaging Topology Definition for RabbitMQ.
Contains Exchange names, Routing Key builders, and Queue naming conventions.
"""

EXCHANGE_NAME = "distributed_warehouse"
DLQ_EXCHANGE_NAME = "distributed_warehouse.dlx"
DLQ_QUEUE_NAME = "q.dlq"

# Routing Key Prefix Constants
ROUTING_CMD_RESERVE = "cmd.transfer.reserve"
ROUTING_CMD_RELEASE = "cmd.transfer.release"
ROUTING_CMD_IMPORT = "cmd.transfer.import"
ROUTING_CMD_SYNC_CATALOG = "cmd.catalog.sync"

ROUTING_EVT_STOCK_RESERVED = "evt.transfer.reserved"
ROUTING_EVT_RESERVE_FAILED = "evt.transfer.reserve_failed"
ROUTING_EVT_TRANSFER_COMPLETED = "evt.transfer.completed"
ROUTING_EVT_TRANSFER_REJECTED = "evt.transfer.rejected"
ROUTING_EVT_STOCK_RELEASED = "evt.transfer.released"
ROUTING_EVT_INVENTORY_UPDATED = "evt.inventory.updated"
ROUTING_EVT_CATALOG_UPDATED = "evt.catalog.updated"


def get_command_routing_key(command_prefix: str, branch_code: str) -> str:
    """Tạo routing key cho lệnh gửi tới một chi nhánh cụ thể: cmd.transfer.xxx.{BRANCH_CODE}"""
    return f"{command_prefix}.{branch_code.strip()}"


def get_branch_queue_name(branch_code: str) -> str:
    """Tên hàng đợi riêng của từng chi nhánh để nhận command: q.branch.{BRANCH_CODE}.commands"""
    return f"q.branch.{branch_code.strip().lower()}.commands"


def get_hq_queue_name() -> str:
    """Tên hàng đợi của Trụ sở chính để nhận tất cả các event từ các chi nhánh: q.hq.events"""
    return "q.hq.events"
