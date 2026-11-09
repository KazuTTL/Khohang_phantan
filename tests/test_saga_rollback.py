# tests/test_saga_rollback.py
"""
KỊCH BẢN KIỂM THỬ 2: GIAO DỊCH BÙ TRỪ & HOÀN TÁC KHI SỰ CỐ (SAGA COMPENSATION / ROLLBACK)
Luồng nghiệp vụ:
1. HQ khởi tạo điều chuyển 15 sản phẩm 'MACBOOK-AIR-M2' từ HN sang HCM.
2. Kho HN khóa thành công 15 sản phẩm (reserved_qty = 15).
3. Kho HCM từ chối nhận hàng qua API /reject (do kho đầy hoặc phát hiện lỗi).
4. HQ nhận EVT_TRANSFER_REJECTED, chuyển sang COMPENSATING và phát CMD_RELEASE_STOCK.
5. Kho HN nhận CMD_RELEASE_STOCK, thực hiện giao dịch bù trừ:
   reserved_qty -= 15, available_qty += 15.
6. HQ cập nhật trạng thái đơn thành CANCELLED_ROLLED_BACK.
"""
import sys
import time
import httpx

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HQ_URL = "http://localhost:8000/api/v1"
HN_URL = "http://localhost:8001/api/v1"
HCM_URL = "http://localhost:8002/api/v1"

def run_test():
    print("=" * 70)
    print(" KỊCH BẢN 2: KIỂM THỬ GIAO DỊCH BÙ TRỪ SAGA ROLLBACK KHI KHO ĐÍCH TỪ CHỐI")
    print("=" * 70)

    with httpx.Client(timeout=5.0) as client:
        # 1. Kiểm tra tồn ban đầu
        sku = "MACBOOK-AIR-M2"
        qty = 15
        hn_inv_pre = {item["sku"]: item for item in client.get(f"{HN_URL}/inventory").json()}
        hn_avail_pre = hn_inv_pre[sku]["available_qty"]
        print(f"\n[Bước 1] Tồn kho HN trước khi điều chuyển: Available = {hn_avail_pre}, Reserved = {hn_inv_pre[sku]['reserved_qty']}")

        # 2. Tạo đơn điều chuyển
        print(f"\n[Bước 2] HQ phát lệnh chuyển {qty} {sku} từ HN sang HCM...")
        res = client.post(f"{HQ_URL}/transfers", json={
            "source_branch": "HN",
            "dest_branch": "HCM",
            "sku": sku,
            "quantity": qty
        })
        assert res.status_code == 202
        transfer_id = res.json()["transfer_id"]
        print(f" -> Khởi tạo đơn: ID = {transfer_id}")
        time.sleep(2)

        # 3. Kiểm tra HN đã khóa tạm
        hn_inv_mid = {item["sku"]: item for item in client.get(f"{HN_URL}/inventory").json()}
        print(f"\n[Bước 3] Kho HN đã khóa tạm: Available = {hn_inv_mid[sku]['available_qty']} (Đã trừ {qty}), Reserved = {hn_inv_mid[sku]['reserved_qty']}")
        assert hn_inv_mid[sku]["available_qty"] == hn_avail_pre - qty

        # 4. Kho đích TP.HCM từ chối nhận hàng (Giả lập sự cố kho đích)
        print(f"\n[Bước 4] Kho TP.HCM phát hiện lỗi hoặc kho quá tải -> Bấm TỪ CHỐI NHẬN HÀNG...")
        res_reject = client.post(f"{HCM_URL}/transfers/{transfer_id}/reject", json={
            "reason": "Kho đích TP.HCM đang bảo trì hệ thống kệ, không đủ chỗ chứa"
        })
        assert res_reject.status_code == 200
        print(f" -> Kho HCM đã từ chối nhận hàng thành công: {res_reject.json().get('message')}")

        # Đợi để HQ phát lệnh bù trừ CMD_RELEASE_STOCK, HN hoàn trả và Outbox đồng bộ về HQ
        print(" -> Đang chờ Saga Coordinator phát lệnh Bù trừ và Outbox đồng bộ hoàn tác...")
        hn_inv_post = None
        order_post = None
        for _ in range(15):
            time.sleep(1)
            hn_inv_post = {item["sku"]: item for item in client.get(f"{HN_URL}/inventory").json()}
            order_post = client.get(f"{HQ_URL}/transfers/{transfer_id}").json()
            if hn_inv_post[sku]["available_qty"] == hn_avail_pre and order_post.get("saga_status") == "CANCELLED_ROLLED_BACK":
                break

        # 5. Kiểm tra kết quả hoàn trả (Rollback verification)
        print("\n[Bước 5] Kiểm tra tồn kho Kho HN sau khi giao dịch bù trừ hoàn tất...")
        print(f" -> Kho HN sau bù trừ: Available = {hn_inv_post[sku]['available_qty']} (Đã hoàn lại {qty}), Reserved = {hn_inv_post[sku]['reserved_qty']}")
        print(f" -> Trạng thái Saga cuối cùng tại HQ: {order_post['saga_status']} (Lý do: {order_post.get('error_reason')})")

        # Xác minh tồn kho ban đầu được khôi phục 100%
        assert hn_inv_post[sku]["available_qty"] == hn_avail_pre, f"Lỗi: Tồn khả dụng chưa được hoàn lại đủ (Có {hn_inv_post[sku]['available_qty']}, kỳ vọng {hn_avail_pre})"
        assert order_post["saga_status"] == "CANCELLED_ROLLED_BACK", f"Lỗi: Trạng thái Saga không phải CANCELLED_ROLLED_BACK (Hiện tại: {order_post['saga_status']})"

        print("\n" + "=" * 70)
        print(" KẾT QUẢ: GIAO DỊCH BÙ TRỪ HOÀN TÁC (SAGA ROLLBACK) THÀNH CÔNG 100%! [PASSED]")
        print("=" * 70)

if __name__ == "__main__":
    run_test()
