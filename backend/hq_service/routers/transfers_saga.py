# backend/hq_service/routers/transfers_saga.py
import uuid
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import TransferOrder, TransferRequest
from shared.event_schemas import (
    TransferOrderCreate,
    TransferPullRequestCreate,
    RabbitMQMessage,
    TransferMessageData,
)
from shared.rabbitmq_client import get_broker
from shared.auth import get_current_user, require_hq_manager

router = APIRouter(tags=["HQ Saga Transfers"])


async def _initiate_saga_transfer(
    db: Session,
    source_branch: str,
    dest_branch: str,
    sku: str,
    quantity: int,
) -> TransferOrder:
    transfer_id = str(uuid.uuid4())
    order = TransferOrder(
        transfer_id=transfer_id,
        source_branch=source_branch,
        dest_branch=dest_branch,
        sku=sku,
        quantity=quantity,
        saga_status="INITIATED"
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    broker = get_broker()
    routing_key = f"cmd.transfer.reserve.{source_branch}"
    message = RabbitMQMessage(
        event_type="CMD_RESERVE_STOCK",
        data=TransferMessageData(
            transfer_id=transfer_id,
            source_branch=source_branch,
            dest_branch=dest_branch,
            sku=sku,
            quantity=quantity
        )
    )
    await broker.publish(routing_key, message)
    return order


@router.post("/transfers", status_code=202)
async def create_transfer_order(
    payload: TransferOrderCreate,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_hq_manager)
):
    """
    Khởi động giao dịch phân tán Saga điều chuyển hàng hóa liên kho
    Bước 1: Lưu trạng thái INITIATED vào DB_HQ
    Bước 2: Phát lệnh CMD_RESERVE_STOCK tới Chi nhánh Nguồn
    """
    if payload.source_branch == payload.dest_branch:
        raise HTTPException(status_code=400, detail="Chi nhánh nguồn và chi nhánh đích không được trùng nhau.")

    order = await _initiate_saga_transfer(
        db=db,
        source_branch=payload.source_branch,
        dest_branch=payload.dest_branch,
        sku=payload.sku,
        quantity=payload.quantity,
    )

    return {
        "transfer_id": order.transfer_id,
        "source_branch": order.source_branch,
        "dest_branch": order.dest_branch,
        "sku": order.sku,
        "quantity": order.quantity,
        "saga_status": order.saga_status,
        "message": "Đã khởi động quy trình Saga. Đang chờ kho nguồn khóa giữ hàng khả dụng."
    }


@router.get("/transfers")
def list_transfers(db: Session = Depends(get_db)):
    orders = db.query(TransferOrder).order_by(TransferOrder.created_at.desc()).all()
    return orders


@router.get("/transfers/{transfer_id}")
def get_transfer(transfer_id: str, db: Session = Depends(get_db)):
    order = db.query(TransferOrder).filter(TransferOrder.transfer_id == transfer_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã điều chuyển.")
    return order


# ==============================================================================
# YÊU CẦU XIN ĐIỀU CHUYỂN HÀNG TỪ CHI NHÁNH (PULL TRANSFER REQUEST)
# ==============================================================================

@router.get("/transfer-requests")
def list_transfer_requests(db: Session = Depends(get_db)):
    """Danh sách yêu cầu xin điều chuyển hàng từ các Chi nhánh gửi lên HQ"""
    return db.query(TransferRequest).order_by(TransferRequest.created_at.desc()).all()


@router.post("/transfer-requests", status_code=201)
def create_transfer_request(
    payload: TransferPullRequestCreate,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Chi nhánh gửi yêu cầu xin bổ sung/điều chuyển hàng lên Trụ sở HQ"""
    src_branch = payload.suggested_source_branch or ("HCM" if payload.requesting_branch == "HN" else "HN")
    if src_branch == payload.requesting_branch:
        raise HTTPException(status_code=400, detail="Kho đề xuất xuất hàng phải khác kho yêu cầu.")

    req_row = TransferRequest(
        request_id=str(uuid.uuid4()),
        requesting_branch=payload.requesting_branch,
        suggested_source_branch=src_branch,
        sku=payload.sku,
        quantity=payload.quantity,
        reason=payload.reason,
        requested_by=user.get("username", "branch_user"),
        status="PENDING"
    )
    db.add(req_row)
    db.commit()
    db.refresh(req_row)
    return req_row


@router.post("/transfer-requests/{request_id}/approve")
async def approve_transfer_request(
    request_id: str,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_hq_manager)
):
    """HQ duyệt yêu cầu xin điều chuyển của chi nhánh và tự động phát lệnh Saga"""
    req_row = db.query(TransferRequest).filter(TransferRequest.request_id == request_id).first()
    if not req_row:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu điều chuyển.")
    if req_row.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Yêu cầu này đã được xử lý trước đó ({req_row.status}).")

    order = await _initiate_saga_transfer(
        db=db,
        source_branch=req_row.suggested_source_branch,
        dest_branch=req_row.requesting_branch,
        sku=req_row.sku,
        quantity=req_row.quantity,
    )
    req_row.status = "APPROVED"
    req_row.transfer_id = order.transfer_id
    db.commit()
    db.refresh(req_row)
    return {
        "status": "APPROVED",
        "request_id": req_row.request_id,
        "transfer_id": order.transfer_id,
        "saga_status": order.saga_status,
        "message": f"Đã duyệt yêu cầu và phát lệnh Saga {order.transfer_id} ({order.source_branch} -> {order.dest_branch})."
    }


@router.post("/transfer-requests/{request_id}/reject")
def reject_transfer_request(
    request_id: str,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_hq_manager)
):
    """HQ từ chối yêu cầu xin điều chuyển hàng của chi nhánh"""
    req_row = db.query(TransferRequest).filter(TransferRequest.request_id == request_id).first()
    if not req_row:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu điều chuyển.")
    req_row.status = "REJECTED"
    db.commit()
    return {"status": "REJECTED", "request_id": request_id, "message": "Đã từ chối yêu cầu điều chuyển."}
