# backend/branch_service/routers/local_inventory.py
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import LocalProduct, LocalInventory, StockLedger
from ..services.stock_service import StockService
from shared.event_schemas import LocalStockAdjust

BRANCH_CODE = os.getenv("BRANCH_CODE", "HN")
stock_service = StockService(BRANCH_CODE)

router = APIRouter(tags=["Branch Local Inventory"])

@router.get("/inventory")
def get_local_inventory(db: Session = Depends(get_db)):
    """Tra cứu tồn kho thực tế nội bộ tại chi nhánh hiện tại"""
    products = db.query(LocalProduct).all()
    prod_map = {p.sku: p for p in products}

    inv_records = db.query(LocalInventory).all()
    result = []
    for inv in inv_records:
        p = prod_map.get(inv.sku)
        result.append({
            "sku": inv.sku,
            "product_name": p.product_name if p else inv.sku,
            "unit": p.unit if p else "Chiếc",
            "available_qty": inv.available_qty,
            "reserved_qty": inv.reserved_qty,
            "version": inv.version,
            "updated_at": inv.updated_at.isoformat() if inv.updated_at else None
        })
    return result

@router.post("/inventory/adjust")
def adjust_inventory(payload: LocalStockAdjust, db: Session = Depends(get_db)):
    """
    Tự trị cục bộ (Local Autonomy):
    Nhập kho hoặc xuất kho bán lẻ tại chỗ.
    Vận hành 100% độc lập ngay cả khi Trụ sở chính (HQ) hoặc mạng Internet bị ngắt kết nối!
    """
    ref_id = payload.reference_id or f"ADJ-{uuid.uuid4().hex[:12].upper()}"
    res = stock_service.adjust_stock(
        db=db,
        sku=payload.sku,
        change_type=payload.change_type,
        quantity=payload.quantity,
        reference_id=ref_id
    )

    if res.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=res.get("reason", "Thao tác kho thất bại"))

    return {
        **res,
        "reference_id": ref_id,
        "sku": payload.sku,
        "branch": BRANCH_CODE,
        "message": "Điều chỉnh tồn kho cục bộ thành công (Đã đưa vào Outbox để đồng bộ)"
    }

@router.get("/ledger")
def get_stock_ledger(db: Session = Depends(get_db)):
    """Xem lịch sử ghi sổ biến động kho (Audit Trail & Idempotency Key)"""
    records = db.query(StockLedger).order_by(StockLedger.ledger_id.desc()).limit(100).all()
    return records
