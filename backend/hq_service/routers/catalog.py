# backend/hq_service/routers/catalog.py
import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hq_service.database import get_db
from hq_service.dependencies import CurrentUser, get_current_user
from hq_service.models import OutboxEvent, Product
from hq_service.schemas import CreateProductRequest, ProductResponse, StandardResponse
from shared.event_schemas import Envelope
from shared.messaging_topology import ROUTING_EVT_CATALOG_UPDATED

router = APIRouter(prefix="/catalog", tags=["HQ - Master Catalog"])


@router.get("", response_model=StandardResponse[list[ProductResponse]])
async def list_products(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[list[ProductResponse]]:
    """Tra cứu danh mục sản phẩm chuẩn toàn hệ thống (Master Data)"""
    stmt = select(Product).where(Product.is_deleted == False).order_by(Product.sku.asc())
    res = await db.execute(stmt)
    products = res.scalars().all()

    data = [
        ProductResponse(
            sku=p.sku,
            product_name=p.product_name,
            unit=p.unit,
            is_deleted=p.is_deleted,
            updated_at=p.updated_at
        )
        for p in products
    ]
    return StandardResponse(success=True, data=data)


@router.post("", response_model=StandardResponse[ProductResponse])
async def create_or_update_product(
    req: CreateProductRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
) -> StandardResponse[ProductResponse]:
    """
    Tạo hoặc cập nhật sản phẩm trong Master Catalog.
    Ghi Outbox Event EVT_CATALOG_UPDATED trong cùng 1 ACID transaction để đồng bộ xuống các chi nhánh.
    """
    sku = req.sku.strip()
    product = await db.get(Product, sku)

    if product:
        product.product_name = req.product_name.strip()
        product.unit = req.unit.strip()
        product.is_deleted = False
        product.updated_at = datetime.now(timezone.utc)
    else:
        product = Product(
            sku=sku,
            product_name=req.product_name.strip(),
            unit=req.unit.strip(),
            is_deleted=False
        )
        db.add(product)

    # NGUYÊN TẮC 3: Ghi Outbox trong cùng transaction để đồng bộ xuống các chi nhánh qua RabbitMQ
    msg_id = str(uuid.uuid4())
    payload = {
        "sku": product.sku,
        "product_name": product.product_name,
        "unit": product.unit,
        "action": "UPSERT"
    }
    envelope = Envelope(
        message_id=msg_id,
        event_type="evt.catalog.updated",
        timestamp=datetime.now(timezone.utc),
        data=payload
    )

    outbox = OutboxEvent(
        event_id=msg_id,
        routing_key=ROUTING_EVT_CATALOG_UPDATED,
        payload=envelope.model_dump_json(),
        is_published=False,
        next_retry_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc)
    )
    db.add(outbox)

    await db.commit()
    await db.refresh(product)

    return StandardResponse(
        success=True,
        data=ProductResponse(
            sku=product.sku,
            product_name=product.product_name,
            unit=product.unit,
            is_deleted=product.is_deleted,
            updated_at=product.updated_at
        )
    )
