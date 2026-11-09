# backend/branch_service/routers/incoming_transfers.py
import os
import json
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import OutboxEvent, IncomingTransfer
from ..services.stock_service import StockService
from shared.event_schemas import TransferDecisionRequest

BRANCH_CODE = os.getenv("BRANCH_CODE", "HN")
stock_service = StockService(BRANCH_CODE)

router = APIRouter(prefix="/transfers", tags=["Branch Incoming Transfers"])

# Cache in-memory song song với CSDL
incoming_orders: Dict[str, Dict[str, Any]] = {}

@router.get("/incoming")
def list_incoming_transfers(db: Session = Depends(get_db)):
    """Xem danh sách các kiện hàng điều chuyển đang trên đường đến chờ chi nhánh xác nhận (Đọc trực tiếp từ CSDL)"""
    records = db.query(IncomingTransfer).filter(IncomingTransfer.status == "WAITING_CONFIRMATION").order_by(IncomingTransfer.created_at.desc()).all()
    results = []
    for r in records:
        results.append({
            "transfer_id": r.transfer_id,
            "source_branch": r.source_branch,
            "dest_branch": r.dest_branch,
            "sku": r.sku,
            "quantity": r.quantity,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    return results

@router.post("/{transfer_id}/confirm")
def confirm_transfer(transfer_id: str, db: Session = Depends(get_db)):
    """
    Chi nhánh đích xác nhận nhận hàng thành công:
    - Cập nhật trạng thái CSDL cục bộ (status = CONFIRMED)
    - Tăng tồn kho cục bộ (available_qty += qty)
    - Phát sự kiện EVT_TRANSFER_COMPLETED qua Outbox
    """
    db_order = db.query(IncomingTransfer).filter(IncomingTransfer.transfer_id == transfer_id).first()
    order_data = incoming_orders.get(transfer_id)

    if not db_order and not order_data:
        raise HTTPException(status_code=404, detail="Không tìm thấy kiện hàng điều chuyển cần duyệt.")

    sku = db_order.sku if db_order else order_data["sku"]
    qty = db_order.quantity if db_order else order_data["quantity"]
    ref_id = f"TRANSFER-IN-{transfer_id}"

    success = stock_service.transfer_in(
        db=db,
        sku=sku,
        quantity=qty,
        reference_id=ref_id,
        transfer_id=transfer_id
    )

    if success:
        if db_order:
            db_order.status = "CONFIRMED"
            db.commit()
        if transfer_id in incoming_orders:
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
    - Cập nhật CSDL chi nhánh (status = REJECTED)
    - Phát sự kiện EVT_TRANSFER_REJECTED qua Outbox
    - Kích hoạt chuỗi Saga Bù trừ (Compensating Transaction) hoàn trả hàng về kho nguồn!
    """
    db_order = db.query(IncomingTransfer).filter(IncomingTransfer.transfer_id == transfer_id).first()
    order_data = incoming_orders.get(transfer_id)

    if not db_order and not order_data:
        raise HTTPException(status_code=404, detail="Không tìm thấy kiện hàng điều chuyển cần từ chối.")

    reason = payload.reason if payload and payload.reason else "Kho đích không đủ sức chứa hoặc hàng sai quy cách"
    src_branch = db_order.source_branch if db_order else order_data.get("source_branch")
    sku = db_order.sku if db_order else order_data.get("sku")
    qty = db_order.quantity if db_order else order_data.get("quantity")

    # Ghi Outbox sự kiện EVT_TRANSFER_REJECTED
    evt_payload = {
        "event_type": "EVT_TRANSFER_REJECTED",
        "data": {
            "transfer_id": transfer_id,
            "dest_branch": BRANCH_CODE,
            "source_branch": src_branch,
            "sku": sku,
            "quantity": qty,
            "reason": reason
        }
    }
    outbox = OutboxEvent(
        routing_key="evt.transfer.rejected",
        payload=json.dumps(evt_payload, ensure_ascii=False),
        is_published=False
    )
    db.add(outbox)

    if db_order:
        db_order.status = "REJECTED"
        db_order.reason = reason
    db.commit()

    if transfer_id in incoming_orders:
        incoming_orders.pop(transfer_id, None)

    return {
        "status": "REJECTED",
        "transfer_id": transfer_id,
        "reason": reason,
        "message": "Đã từ chối nhận hàng. Hệ thống đang kích hoạt quy trình Rollback hoàn trả kho nguồn."
    }
