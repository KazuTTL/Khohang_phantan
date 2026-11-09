# backend/branch_service/consumers/catalog_sync_consumer.py
import logging
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.ext.asyncio import async_sessionmaker

from branch_service.config import branch_settings
from branch_service.models import LocalInventory, LocalProduct
from shared.idempotency import check_inbox, mark_inbox

logger = logging.getLogger(f"CatalogSyncConsumer_{branch_settings.BRANCH_CODE}")


async def on_catalog_sync(
    message_data: dict[str, Any],
    routing_key: str,
    db_factory: async_sessionmaker
) -> None:
    """
    Consumer đồng bộ danh mục sản phẩm từ HQ xuống CSDL cục bộ của Chi nhánh.
    Kiểm tra Inbox để đảm bảo tính Idempotent.
    """
    msg_id = message_data.get("message_id") or ""
    event_type = message_data.get("event_type") or ""
    data = message_data.get("data") or message_data.get("payload") or {}

    sku = data.get("sku")
    product_name = data.get("product_name") or data.get("name") or sku
    unit = data.get("unit") or "Chiếc"

    if not sku:
        return

    async with db_factory() as session:
        async with session.begin():
            # 1. Kiểm tra Inbox
            if msg_id and await check_inbox(session, msg_id):
                logger.info(f"[IDEMPOTENT HIT] on_catalog_sync message_id={msg_id} đã được xử lý.")
                return

            # 2. MERGE vào Local_Products
            product = await session.get(LocalProduct, sku)
            if product:
                product.product_name = product_name
                product.unit = unit
            else:
                product = LocalProduct(
                    sku=sku,
                    product_name=product_name,
                    unit=unit
                )
                session.add(product)

            # 3. Đảm bảo có dòng trong Local_Inventory
            inv = await session.get(LocalInventory, sku)
            if not inv:
                inv = LocalInventory(
                    sku=sku,
                    available_qty=0,
                    reserved_qty=0,
                    version=1,
                    updated_at=datetime.now(timezone.utc)
                )
                session.add(inv)

            # 4. Ghi Inbox
            if msg_id:
                await mark_inbox(session, msg_id, event_type or "evt.catalog.sync")
            logger.info(f"[CATALOG SYNC] Chi nhánh {branch_settings.BRANCH_CODE} đã đồng bộ SKU={sku} ({product_name})")
