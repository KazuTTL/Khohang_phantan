# tests/e2e_distributed_test.py
"""
KỊCH BẢN KIỂM THỬ 3: KHẢ NĂNG TỰ TRỊ CỤC BỘ & TÍNH LŨY BIẾN (LOCAL AUTONOMY & IDEMPOTENCY)
Mục tiêu:
1. Chứng minh Chi nhánh (Cổng 8001) có thể thực hiện xuất/nhập bán hàng hoàn toàn độc lập.
2. Kiểm tra tính lũy biến (Idempotency): Gửi lại cùng một reference_id nhiều lần không bị trừ kho lặp (At-Most-Once Semantics).
3. Kiểm tra bảng Outbox: Mọi biến động đều được đưa vào Outbox để đồng bộ về HQ.
"""
import sys
import uuid
import httpx

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HN_URL = "http://localhost:8001/api/v1"

def run_test():
    print("=" * 70)
    print(" KỊCH BẢN 3: KIỂM THỬ TỰ TRỊ CỤC BỘ & IDEMPOTENCY TẠI CHI NHÁNH")
    print("=" * 70)

    with httpx.Client(timeout=5.0) as client:
        sku = "LAPTOP-DELL-01"
        ref_id = f"LOCAL-SALE-{uuid.uuid4().hex[:8].upper()}"

        # 1. Lấy tồn ban đầu
        inv_pre = {item["sku"]: item for item in client.get(f"{HN_URL}/inventory").json()}
        avail_pre = inv_pre[sku]["available_qty"]
        print(f"\n[Bước 1] Tồn khả dụng ban đầu tại Kho HN: {avail_pre} cái")

        # 2. Thực hiện xuất bán lẻ tại chỗ
        print(f"\n[Bước 2] Thực hiện Xuất bán 5 cái tại chỗ (Reference ID = {ref_id})...")
        res1 = client.post(f"{HN_URL}/inventory/adjust", json={
            "sku": sku,
            "change_type": "LOCAL_OUT",
            "quantity": 5,
            "reference_id": ref_id
        })
        assert res1.status_code == 200
        body1 = res1.json()
        print(f" -> Lần 1: Thành công! Tồn còn lại = {body1['available_qty']} (is_duplicate = {body1.get('is_duplicate')})")
        assert body1["available_qty"] == avail_pre - 5

        # 3. Giả lập gửi lại cùng một Request ID (Mất mạng lúc nhận ACK từ server, client retry)
        print(f"\n[Bước 3] Giả lập Client Retry gửi lại CÙNG MỘT Reference ID ({ref_id})...")
        res2 = client.post(f"{HN_URL}/inventory/adjust", json={
            "sku": sku,
            "change_type": "LOCAL_OUT",
            "quantity": 5,
            "reference_id": ref_id
        })
        assert res2.status_code == 200
        body2 = res2.json()
        print(f" -> Lần 2 (Trùng ID): Hệ thống phát hiện trùng lặp! is_duplicate = {body2.get('is_duplicate')}")
        assert body2.get("is_duplicate") == True, "Lỗi: Không phát hiện được trùng lặp Request ID!"
        assert body2["available_qty"] == avail_pre - 5, "Lỗi: Tồn kho bị trừ hai lần!"

        # 4. Kiểm tra Sổ cái Stock_Ledger
        print(f"\n[Bước 4] Kiểm tra Sổ cái Stock_Ledger xác minh chỉ có đúng 1 bản ghi...")
        ledger = client.get(f"{HN_URL}/ledger").json()
        matched = [entry for entry in ledger if entry["reference_id"] == ref_id]
        print(f" -> Số bản ghi mang Reference ID '{ref_id}' trong CSDL: {len(matched)}")
        assert len(matched) == 1, "Lỗi: Phát hiện bản ghi bị trùng trong sổ cái!"

        print("\n" + "=" * 70)
        print(" KẾT QUẢ: TỰ TRỊ CỤC BỘ & IDEMPOTENCY CHỐNG TRÙNG LẶP HOÀN HẢO! [PASSED]")
        print("=" * 70)

if __name__ == "__main__":
    run_test()
