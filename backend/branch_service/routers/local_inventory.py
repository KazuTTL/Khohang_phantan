# backend/branch_service/routers/local_inventory.py
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import (
    LocalBranch,
    LocalCategory,
    LocalProduct,
    Account,
    LocalInventory,
    StockLedger,
    WarehouseTransaction,
    WarehouseTransactionDetail,
    CustomerOrder,
    CustomerOrderDetail,
    IncomingTransfer,
    OutboxEvent,
)
from ..services.stock_service import StockService
from shared.event_schemas import (
    LocalStockAdjust,
    StockThresholdUpdate,
    StockAuditRequest,
    CustomerOrderCreate,
)

BRANCH_CODE = os.getenv("BRANCH_CODE", "HN")
stock_service = StockService(BRANCH_CODE)

router = APIRouter(tags=["Branch Local Inventory"])


@router.get("/inventory")
def get_local_inventory(db: Session = Depends(get_db)):
    """Tra cứu tồn kho thực tế nội bộ tại chi nhánh hiện tại (TON_KHO phân mảnh theo ma_chi_nhanh)"""
    products = db.query(LocalProduct).all()
    prod_map = {p.sku: p for p in products}

    inv_records = db.query(LocalInventory).all()
    result = []
    for inv in inv_records:
        p = prod_map.get(inv.sku)
        result.append({
            "sku": inv.sku,
            "branch_code": getattr(inv, "branch_code", BRANCH_CODE),
            "barcode": p.barcode if p else None,
            "product_name": p.product_name if p else inv.sku,
            "category_id": p.category_id if p else 1,
            "unit": p.unit if p else "Chiếc",
            "cost_price": p.cost_price if p else 0.0,
            "price": p.price if p else 0.0,
            "available_qty": inv.available_qty,
            "reserved_qty": inv.reserved_qty,
            "min_threshold": getattr(inv, "min_threshold", 10),
            "max_threshold": getattr(inv, "max_threshold", 200),
            "is_low_stock": inv.available_qty <= getattr(inv, "min_threshold", 10),
            "version": inv.version,
            "updated_at": inv.updated_at.isoformat() if inv.updated_at else None
        })
    return result


@router.get("/categories")
def list_local_categories(db: Session = Depends(get_db)):
    """Lấy danh mục ngành hàng được nhân bản tại Chi nhánh (DANH_MUC_SP)"""
    return db.query(LocalCategory).all()


@router.put("/inventory/{sku}/thresholds")
def update_thresholds(sku: str, payload: StockThresholdUpdate, db: Session = Depends(get_db)):
    """Cập nhật định mức tồn kho an toàn (Min/Max Thresholds)"""
    inv = db.query(LocalInventory).filter(LocalInventory.sku == sku).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Không tìm thấy mặt hàng trong kho.")

    inv.min_threshold = payload.min_threshold
    inv.max_threshold = payload.max_threshold
    db.commit()
    return {
        "status": "SUCCESS",
        "sku": sku,
        "min_threshold": inv.min_threshold,
        "max_threshold": inv.max_threshold,
        "message": f"Đã cập nhật định mức tồn kho cho {sku}."
    }


@router.post("/inventory/audit")
def audit_inventory(payload: StockAuditRequest, db: Session = Depends(get_db)):
    """Kiểm kê kho thực tế và tự động điều chỉnh chênh lệch tồn kho (Stock-taking & Variance Adjustment)"""
    res = stock_service.audit_stock(
        db=db,
        sku=payload.sku,
        actual_qty=payload.actual_qty,
        note=payload.note
    )
    return {
        **res,
        "branch": BRANCH_CODE,
        "message": f"Kiểm kê hoàn tất. Chênh lệch: {res['variance']:+d} (Đã ghi nhận sổ cái, phiếu kiểm kê và đồng bộ snapshot)."
    }


@router.post("/inventory/adjust")
def adjust_inventory(payload: LocalStockAdjust, db: Session = Depends(get_db)):
    """
    Tự trị cục bộ (Local Autonomy):
    Nhập kho hoặc xuất kho bán lẻ tại chỗ (có lưu đối tác Nhà cung cấp / Khách hàng).
    Vận hành 100% độc lập ngay cả khi Trụ sở chính (HQ) hoặc mạng Internet bị ngắt kết nối!
    """
    ref_id = payload.reference_id or f"ADJ-{uuid.uuid4().hex[:12].upper()}"
    res = stock_service.adjust_stock(
        db=db,
        sku=payload.sku,
        change_type=payload.change_type,
        quantity=payload.quantity,
        reference_id=ref_id,
        partner_name=payload.partner_name,
        note=payload.note
    )

    if res.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=res.get("reason", "Thao tác kho thất bại"))

    return {
        **res,
        "reference_id": ref_id,
        "sku": payload.sku,
        "branch": BRANCH_CODE,
        "partner_name": payload.partner_name,
        "note": payload.note,
        "message": "Điều chỉnh tồn kho cục bộ thành công (Đã đưa vào Outbox để đồng bộ)"
    }


@router.get("/ledger")
def get_stock_ledger(db: Session = Depends(get_db)):
    """Xem lịch sử ghi sổ biến động kho (Audit Trail & Idempotency Key)"""
    records = db.query(StockLedger).order_by(StockLedger.ledger_id.desc()).limit(100).all()
    return records


# ==============================================================================
# ĐƠN HÀNG TẠI CHI NHÁNH (DON_HANG & CHI_TIET_DON_HANG)
# ==============================================================================

@router.get("/orders")
def list_customer_orders(db: Session = Depends(get_db)):
    """Danh sách đơn đặt hàng của khách hàng tại Chi nhánh (DON_HANG + CHI_TIET_DON_HANG)"""
    orders = db.query(CustomerOrder).order_by(CustomerOrder.created_at.desc()).limit(50).all()
    details = db.query(CustomerOrderDetail).all()
    detail_map = {}
    for d in details:
        detail_map.setdefault(d.order_id, []).append({
            "id": d.id,
            "sku": d.sku,
            "quantity": d.quantity,
            "unit_price": d.unit_price
        })

    return [
        {
            "order_id": o.order_id,
            "branch_code": o.branch_code,
            "customer_name": o.customer_name,
            "customer_phone": o.customer_phone,
            "total_amount": o.total_amount,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "items": detail_map.get(o.order_id, [])
        }
        for o in orders
    ]


@router.post("/orders", status_code=201)
def create_customer_order(payload: CustomerOrderCreate, db: Session = Depends(get_db)):
    """Tạo đơn hàng tại chi nhánh (DON_HANG + CHI_TIET_DON_HANG), tự động xuất kho & sinh phiếu GIAO_DICH_KHO"""
    res = stock_service.create_customer_order(
        db=db,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        items=[item.model_dump() for item in payload.items]
    )
    if res.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=res.get("reason", "Không thể tạo đơn hàng"))
    return res


# ==============================================================================
# PHIẾU GIAO DỊCH KHO (GIAO_DICH_KHO & CHI_TIET_GIAO_DICH)
# ==============================================================================

@router.get("/transactions")
def list_warehouse_transactions(db: Session = Depends(get_db)):
    """Xem danh sách phiếu giao dịch kho kèm chi tiết mặt hàng và tồn sau giao dịch"""
    txs = db.query(WarehouseTransaction).order_by(WarehouseTransaction.created_at.desc()).limit(50).all()
    details = db.query(WarehouseTransactionDetail).all()
    detail_map = {}
    for d in details:
        detail_map.setdefault(d.transaction_id, []).append({
            "detail_id": d.detail_id,
            "sku": d.sku,
            "quantity": d.quantity,
            "post_transaction_balance": d.post_transaction_balance
        })

    return [
        {
            "transaction_id": t.transaction_id,
            "branch_code": t.branch_code,
            "receipt_code": t.receipt_code,
            "transaction_type": t.transaction_type,
            "counterpart_branch": t.counterpart_branch,
            "saga_transfer_id": t.saga_transfer_id,
            "created_by": t.created_by,
            "status": t.status,
            "note": t.note,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "details": detail_map.get(t.transaction_id, [])
        }
        for t in txs
    ]


@router.get("/outbox")
def list_outbox_events(db: Session = Depends(get_db)):
    """Xem hàng đợi sự kiện đồng bộ Outbox (SU_KIEN_DONG_BO)"""
    rows = db.query(OutboxEvent).order_by(OutboxEvent.created_at.desc()).limit(50).all()
    return [
        {
            "event_id": r.event_id,
            "branch_code": r.branch_code,
            "event_type": r.event_type,
            "routing_key": r.routing_key,
            "delivery_status": r.delivery_status,
            "retry_count": r.retry_count,
            "is_published": r.is_published,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in rows
    ]


@router.get("/schema-overview")
def get_branch_schema_overview(db: Session = Depends(get_db)):
    """Thống kê số lượng bản ghi các bảng tại Site Chi nhánh theo Thiết kế 11 bảng"""
    return {
        "site": f"Branch Node ({BRANCH_CODE})",
        "tables": {
            "CHI_NHANH (Branches - Replica)": db.query(LocalBranch).count(),
            "DANH_MUC_SP (Product_Categories - Replica)": db.query(LocalCategory).count(),
            "SAN_PHAM (Local_Products - Replica)": db.query(LocalProduct).count(),
            "TAI_KHOAN (Accounts - Synced)": db.query(Account).count(),
            "TON_KHO (Local_Inventory - Sharded)": db.query(LocalInventory).count(),
            "GIAO_DICH_KHO (Warehouse_Transactions)": db.query(WarehouseTransaction).count(),
            "CHI_TIET_GIAO_DICH (Warehouse_Transaction_Details)": db.query(WarehouseTransactionDetail).count(),
            "DON_HANG (Customer_Orders)": db.query(CustomerOrder).count(),
            "CHI_TIET_DON_HANG (Customer_Order_Details)": db.query(CustomerOrderDetail).count(),
            "SU_KIEN_DONG_BO (Outbox_Events)": db.query(OutboxEvent).count(),
            "Incoming_Transfers (Saga Dest)": db.query(IncomingTransfer).count(),
            "Stock_Ledger (Audit)": db.query(StockLedger).count()
        }
    }
