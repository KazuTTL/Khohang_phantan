# backend/branch_service/routers/incoming_transfers.py
import os
import json
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import OutboxEvent
from ..services.stock_service import StockService
from shared.event_schemas import TransferDecisionRequest

BRANCH_CODE = os.getenv("BRANCH_CODE", "HN")
stock_service = StockService(BRANCH_CODE)

router = APIRouter(prefix="/transfers", tags=["Branch Incoming Transfers"])

# Lưu tạm trong bộ nhớ danh sách kiện hàng đang chờ chi nhánh đích phê duyệt
incoming_orders: Dict[str, Dict[str, Any]] = {}

@router.get("/incoming")
def list_incoming_transfers():
    """Xem danh sách các kiện hàng điều chuyển đang trên đường đến chờ chi nhánh xác nhận"""
    return list(incoming_orders.values())

@router.post("/{transfer_id}/confirm")
def confirm_transfer(transfer_id: str, db: Session = Depends(get_db)):
    """
    Chi nhánh đích xác nhận nhận hàng thành công:
    - Tăng tồn kho cục bộ (available_qty += qty)
    - Phát sự kiện EVT_TRANSFER_COMPLETED qua Outbox
    """
    order = incoming_orders.get(transfer_id)
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy kiện hàng điều chuyển cần duyệt.")

    sku = order["sku"]
    qty = order["quantity"]
    ref_id = f"TRANSFER-IN-{transfer_id}"

    success = stock_service.transfer_in(
        db=db,
        sku=sku,
        quantity=qty,
        reference_id=ref_id,
        transfer_id=transfer_id
    )

    if success:
        order["status"] = "CONFIRMED"
        incoming_orders.pop(transfer_id, None)
        return {
            "status": "SUCCESS",
            "transfer_id": transfer_id,
            "sku": sku,
            "quantity": qty,
            "message": f"Chi nhánh {BRANCH_CODE} đã xác nhận nhập kho thành công kiện hàng {transfer_id}."
        }
    raise HTTPException(status_code=500, detail="Lỗi khi ghi nhận nhập kho điều chuyển.")

@router.post("/{transfer_id}/reject")
def reject_transfer(transfer_id: str, payload: TransferDecisionRequest = None, db: Session = Depends(get_db)):
    """
    Chi nhánh đích từ chối nhận hàng (Hàng hỏng, sai mã, kho đầy):
    - Phát sự kiện EVT_TRANSFER_REJECTED qua Outbox
    - Kích hoạt chuỗi Saga Bù trừ (Compensating Transaction) hoàn trả hàng về kho nguồn!
    """
    order = incoming_orders.get(transfer_id)
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy kiện hàng điều chuyển cần từ chối.")

    reason = payload.reason if payload and payload.reason else "Kho đích không đủ sức chứa hoặc hàng sai quy cách"

    # Ghi Outbox sự kiện EVT_TRANSFER_REJECTED
    evt_payload = {
        "event_type": "EVT_TRANSFER_REJECTED",
        "data": {
            "transfer_id": transfer_id,
            "dest_branch": BRANCH_CODE,
            "source_branch": order.get("source_branch"),
            "sku": order.get("sku"),
            "quantity": order.get("quantity"),
            "reason": reason
        }
    }
    outbox = OutboxEvent(
        routing_key="evt.transfer.rejected",
        payload=json.dumps(evt_payload, ensure_ascii=False),
        is_published=False
    )
    db.add(outbox)
    db.commit()

    order["status"] = "REJECTED"
    incoming_orders.pop(transfer_id, None)

    return {
        "status": "REJECTED",
        "transfer_id": transfer_id,
        "reason": reason,
        "message": "Đã từ chối nhận hàng. Hệ thống đang kích hoạt quy trình Rollback hoàn trả kho nguồn."
    }
