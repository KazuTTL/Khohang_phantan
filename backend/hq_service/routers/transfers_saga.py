# backend/hq_service/routers/transfers_saga.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import TransferOrder
from shared.event_schemas import TransferOrderCreate, RabbitMQMessage, TransferMessageData
from shared.rabbitmq_client import get_broker

router = APIRouter(prefix="/transfers", tags=["HQ Saga Transfers"])

@router.post("", status_code=202)
async def create_transfer_order(payload: TransferOrderCreate, db: Session = Depends(get_db)):
    """
    Khởi động giao dịch phân tán Saga điều chuyển hàng hóa liên kho
    Bước 1: Lưu trạng thái INITIATED vào DB_HQ
    Bước 2: Phát lệnh CMD_RESERVE_STOCK tới Chi nhánh Nguồn
    """
    if payload.source_branch == payload.dest_branch:
        raise HTTPException(status_code=400, detail="Chi nhánh nguồn và chi nhánh đích không được trùng nhau.")

    transfer_id = str(uuid.uuid4())
    order = TransferOrder(
        transfer_id=transfer_id,
        source_branch=payload.source_branch,
        dest_branch=payload.dest_branch,
        sku=payload.sku,
        quantity=payload.quantity,
        saga_status="INITIATED"
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # Gửi lệnh CMD_RESERVE_STOCK tới kho nguồn
    broker = get_broker()
    routing_key = f"cmd.transfer.reserve.{payload.source_branch}"
    message = RabbitMQMessage(
        event_type="CMD_RESERVE_STOCK",
        data=TransferMessageData(
            transfer_id=transfer_id,
            source_branch=payload.source_branch,
            dest_branch=payload.dest_branch,
            sku=payload.sku,
            quantity=payload.quantity
        )
    )
    await broker.publish(routing_key, message)

    return {
        "transfer_id": order.transfer_id,
        "source_branch": order.source_branch,
        "dest_branch": order.dest_branch,
        "sku": order.sku,
        "quantity": order.quantity,
        "saga_status": order.saga_status,
        "message": "Đã khởi động quy trình Saga. Đang chờ kho nguồn khóa giữ hàng khả dụng."
    }

@router.get("")
def list_transfers(db: Session = Depends(get_db)):
    orders = db.query(TransferOrder).order_by(TransferOrder.created_at.desc()).all()
    return orders

@router.get("/{transfer_id}")
def get_transfer(transfer_id: str, db: Session = Depends(get_db)):
    order = db.query(TransferOrder).filter(TransferOrder.transfer_id == transfer_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã điều chuyển.")
    return order
