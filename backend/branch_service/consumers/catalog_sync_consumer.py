# backend/branch_service/consumers/catalog_sync_consumer.py
import logging
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from branch_service.config import branch_settings
from branch_service.database import AsyncSessionLocal
from branch_service.models import LocalInventory, LocalProduct
from shared.event_schemas import EvtCatalogUpdatedPayload
from shared.idempotency import check_and_mark_inbox

logger = logging.getLogger(f"CatalogSyncConsumer_{branch_settings.BRANCH_CODE}")
CONSUMER_NAME = f"CatalogSyncConsumer_{branch_settings.BRANCH_CODE}"


async def process_catalog_sync(message_data: dict[str, Any], routing_key: str) -> None:
    """
    Consumer đồng bộ danh mục sản phẩm từ HQ xuống CSDL cục bộ của Chi nhánh.
    """
    msg_id = message_data.get("message_id") or ""
    event_type = message_data.get("event_type") or ""
    payload_dict = message_data.get("payload") or {}

    async with AsyncSessionLocal() as session:
        async with session.begin():
            is_new = await check_and_mark_inbox(session, msg_id, CONSUMER_NAME)
            if not is_new:
                return

            if event_type == "EVT_CATALOG_UPDATED":
                payload = EvtCatalogUpdatedPayload(**payload_dict)
                product = await session.get(LocalProduct, payload.sku)
                if product:
                    product.product_name = payload.product_name
                    product.unit = payload.unit
                    product.updated_at = datetime.now(timezone.utc)
                else:
                    new_product = LocalProduct(
                        sku=payload.sku,
                        product_name=payload.product_name,
                        unit=payload.unit,
                        updated_at=datetime.now(timezone.utc)
                    )
                    session.add(new_product)

                # Đảm bảo có bản ghi trong Local_Inventory nếu chưa có
                inv = await session.get(LocalInventory, payload.sku)
                if not inv:
                    new_inv = LocalInventory(
                        sku=payload.sku,
                        available_qty=0,
                        reserved_qty=0,
                        updated_at=datetime.now(timezone.utc)
                    )
                    session.add(new_inv)

                logger.info(f"[CATALOG SYNC] Kho {branch_settings.BRANCH_CODE} đã đồng bộ SKU={payload.sku} ({payload.product_name})")
