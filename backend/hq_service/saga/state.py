# backend/hq_service/saga/state.py
from enum import Enum


class SagaStatus(str, Enum):
    """
    Các trạng thái của giao dịch phân tán Điều chuyển hàng hóa (Stock Transfer Saga).
    """
    INITIATED = "INITIATED"                     # 1. Đã khởi tạo phiếu điều chuyển tại HQ
    RESERVED_IN_TRANSIT = "RESERVED_IN_TRANSIT" # 2. Kho nguồn đã giữ hàng, đang vận chuyển tới kho đích
    COMPLETED = "COMPLETED"                     # 3. Kho đích đã nhập kho thành công (Thành công trọn vẹn)
    COMPENSATING = "COMPENSATING"               # 4. Kho đích từ chối/gặp sự cố -> Đang kích hoạt bù trừ
    ROLLED_BACK = "ROLLED_BACK"                 # 5. Đã hoàn trả lại số hàng giữ về kho nguồn (Rollback thành công)
    FAILED = "FAILED"                           # 6. Thất bại ngay từ Phase 1 (không đủ hàng để giữ)
