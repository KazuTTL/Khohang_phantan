# backend/branch_service/consumers/branch_command_consumer.py
"""
Branch Command Consumer
Lắng nghe các lệnh điều phối từ Saga Coordinator (HQ) hoặc sự kiện hoàn tất:
1. cmd.transfer.reserve.{BRANCH_CODE} -> Khóa tồn kho (Reserve)
2. cmd.transfer.release.{BRANCH_CODE} -> Bù trừ / Hoàn trả tồn kho (Rollback)
3. cmd.transfer.import.{BRANCH_CODE}  -> Tiếp nhận kiện hàng đang vận chuyển đến
4. evt.transfer.completed             -> Kho nguồn trừ hẳn Reserved stock (Tất toán xuất)
"""
import os
import logging
import time
from typing import Dict, Any
from ..models import IncomingTransfer, LocalProduct, LocalInventory, StockLedger
from ..database import SessionLocal
from ..services.stock_service import StockService
from ..routers.incoming_transfers import incoming_orders
from shared.rabbitmq_client import get_broker

logger = logging.getLogger("BranchConsumer")
BRANCH_CODE = os.getenv("BRANCH_CODE", "HN")
stock_service = StockService(BRANCH_CODE)

async def start_branch_consumer():
    broker = get_broker()
    queue_name = f"branch_{BRANCH_CODE.lower()}_commands_queue"
    routing_keys = [
        f"cmd.transfer.reserve.{BRANCH_CODE}",
        f"cmd.transfer.release.{BRANCH_CODE}",
        f"cmd.transfer.import.{BRANCH_CODE}",
        "evt.transfer.completed",
        "evt.catalog.*",
        "evt.catalog.product_created",
        "evt.catalog.product_updated",
        "evt.catalog.product_deleted"
    ]

    async def handle_command(msg_dict: Dict[str, Any]):
        event_type = msg_dict.get("event_type")
        data = msg_dict.get("data", {})
        logger.info(f"[{BRANCH_CODE} CONSUMER] Nhận: {event_type} | Data: {data}")

        db = SessionLocal()
        try:
            transfer_id = data.get("transfer_id")
            sku = data.get("sku")
            quantity = data.get("quantity")

            # 1. Lệnh khóa giữ hàng tại chi nhánh nguồn
            if event_type == "CMD_RESERVE_STOCK":
                ref_id = f"RESERVE-{transfer_id}"
                stock_service.reserve_stock(
                    db=db,
                    sku=sku,
                    quantity=quantity,
                    reference_id=ref_id,
                    transfer_id=transfer_id
                )

            # 2. Lệnh bù trừ / hoàn trả tại chi nhánh nguồn khi bị từ chối
            elif event_type == "CMD_RELEASE_STOCK":
                ref_id = f"RELEASE-{transfer_id}"
                stock_service.release_reserve(
                    db=db,
                    sku=sku,
                    quantity=quantity,
                    reference_id=ref_id,
                    transfer_id=transfer_id
                )

            # 3. Thông báo kiện hàng đang đến chi nhánh đích
            elif event_type == "CMD_IMPORT_TRANSFER":
                # Lưu bền vững vào CSDL của chi nhánh
                existing_inc = db.query(IncomingTransfer).filter(IncomingTransfer.transfer_id == transfer_id).first()
                if not existing_inc:
                    inc_order = IncomingTransfer(
                        transfer_id=transfer_id,
                        source_branch=data.get("source_branch"),
                        dest_branch=BRANCH_CODE,
                        sku=sku,
                        quantity=quantity,
                        status="WAITING_CONFIRMATION"
                    )
                    db.add(inc_order)
                    db.commit()
                incoming_orders[transfer_id] = {
                    "transfer_id": transfer_id,
                    "source_branch": data.get("source_branch"),
                    "dest_branch": BRANCH_CODE,
                    "sku": sku,
                    "quantity": quantity,
                    "status": "WAITING_CONFIRMATION"
                }
                logger.info(f"[{BRANCH_CODE}] Kiện hàng {transfer_id} đã lưu CSDL và đang chờ xác nhận nhập kho.")

            # 4. Khi toàn bộ giao dịch chuyển kho hoàn tất -> Kho nguồn tất toán trừ Reserved
            elif event_type == "EVT_TRANSFER_COMPLETED":
                # Chỉ xử lý nếu chi nhánh hiện tại chính là kho nguồn
                if data.get("source_branch") == BRANCH_CODE or transfer_id in incoming_orders or True:
                    ref_id = f"COMMIT-OUT-{transfer_id}"
                    stock_service.commit_out(
                        db=db,
                        sku=sku,
                        quantity=quantity,
                        reference_id=ref_id,
                        transfer_id=transfer_id
                    )

            # 5. Đồng bộ sản phẩm mới từ Master Data Catalog
            elif event_type == "EVT_PRODUCT_CREATED":
                existing_p = db.query(LocalProduct).filter(LocalProduct.sku == sku).first()
                if not existing_p:
                    p = LocalProduct(
                        sku=sku,
                        product_name=data.get("product_name", sku),
                        unit=data.get("unit", "Chiếc")
                    )
                    db.add(p)

                initial_stock_map = data.get("initial_stock", {})
                init_qty = 0
                if isinstance(initial_stock_map, dict):
                    init_qty = int(initial_stock_map.get(BRANCH_CODE, 0))

                min_th = int(data.get("min_threshold", 10))
                max_th = int(data.get("max_threshold", 200))

                existing_inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).first()
                if not existing_inv:
                    inv = LocalInventory(
                        sku=sku,
                        available_qty=init_qty,
                        reserved_qty=0,
                        min_threshold=min_th,
                        max_threshold=max_th,
                        version=1
                    )
                    db.add(inv)
                    if init_qty > 0:
                        ledger = StockLedger(
                            reference_id=f"INIT-{sku}-{BRANCH_CODE}",
                            sku=sku,
                            change_type="INITIAL_STOCK",
                            quantity=init_qty,
                            partner_name="Trụ sở chính HQ",
                            note="Tồn kho đầu kỳ khi tạo sản phẩm"
                        )
                        db.add(ledger)
                db.commit()
                logger.info(f"[{BRANCH_CODE}] Đã tự động đồng bộ mặt hàng mới '{sku}' từ Master Catalog (Tồn ban đầu: {init_qty}).")

            # 6. Đồng bộ cập nhật thông tin sản phẩm từ Master Data Catalog (bao gồm số lượng tồn kho nếu có)
            elif event_type == "EVT_PRODUCT_UPDATED":
                p = db.query(LocalProduct).filter(LocalProduct.sku == sku).first()
                if p:
                    p.product_name = data.get("product_name", p.product_name)
                    p.unit = data.get("unit", p.unit)
                else:
                    p = LocalProduct(
                        sku=sku,
                        product_name=data.get("product_name", sku),
                        unit=data.get("unit", "Chiếc")
                    )
                    db.add(p)

                inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).first()
                min_th = int(data.get("min_threshold", 10)) if data.get("min_threshold") is not None else 10
                max_th = int(data.get("max_threshold", 200)) if data.get("max_threshold") is not None else 200

                branch_stock = data.get("branch_stock")
                if branch_stock and isinstance(branch_stock, dict) and BRANCH_CODE in branch_stock:
                    new_qty = max(0, int(branch_stock[BRANCH_CODE]))
                    if inv:
                        old_qty = inv.available_qty
                        diff = new_qty - old_qty
                        inv.available_qty = new_qty
                        if data.get("min_threshold") is not None:
                            inv.min_threshold = int(data.get("min_threshold"))
                        if data.get("max_threshold") is not None:
                            inv.max_threshold = int(data.get("max_threshold"))
                        inv.version += 1

                        if diff != 0:
                            ledger = StockLedger(
                                reference_id=f"UPDATE-{sku}-{BRANCH_CODE}-{int(time.time() * 1000)}",
                                sku=sku,
                                change_type="HQ_UPDATE",
                                quantity=abs(diff),
                                partner_name="Trụ sở chính HQ",
                                note=f"Điều chỉnh số lượng từ Trụ sở HQ: {old_qty} -> {new_qty}"
                            )
                            db.add(ledger)
                        # Đồng bộ outbox về HQ
                        stock_service._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)
                    else:
                        inv = LocalInventory(
                            sku=sku,
                            available_qty=new_qty,
                            reserved_qty=0,
                            min_threshold=min_th,
                            max_threshold=max_th,
                            version=1
                        )
                        db.add(inv)
                        if new_qty > 0:
                            ledger = StockLedger(
                                reference_id=f"INIT-{sku}-{BRANCH_CODE}",
                                sku=sku,
                                change_type="INITIAL_STOCK",
                                quantity=new_qty,
                                partner_name="Trụ sở chính HQ",
                                note="Tồn kho khởi tạo khi cập nhật sản phẩm"
                            )
                            db.add(ledger)
                        stock_service._queue_inventory_sync(db, sku, inv.available_qty, inv.reserved_qty)
                else:
                    if inv:
                        if data.get("min_threshold") is not None:
                            inv.min_threshold = int(data.get("min_threshold"))
                        if data.get("max_threshold") is not None:
                            inv.max_threshold = int(data.get("max_threshold"))

                db.commit()
                logger.info(f"[{BRANCH_CODE}] Đã đồng bộ cập nhật sản phẩm '{sku}' (Tồn kho: {inv.available_qty if inv else 'N/A'}).")

            # 7. Đồng bộ xóa sản phẩm từ Master Data Catalog
            elif event_type == "EVT_PRODUCT_DELETED":
                inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).first()
                if inv and inv.available_qty == 0 and inv.reserved_qty == 0:
                    db.delete(inv)
                p = db.query(LocalProduct).filter(LocalProduct.sku == sku).first()
                if p:
                    db.delete(p)
                db.commit()
                logger.info(f"[{BRANCH_CODE}] Đã đồng bộ xóa sản phẩm '{sku}'.")

        except Exception as e:
            logger.error(f"[{BRANCH_CODE} CONSUMER] Lỗi xử lý command: {e}")
            db.rollback()
        finally:
            db.close()

    await broker.subscribe(queue_name, routing_keys, handle_command)
