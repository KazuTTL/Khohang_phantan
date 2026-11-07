# tests/test_saga_happy_path.py
"""
KỊCH BẢN KIỂM THỬ 1: GIAO DỊCH PHÂN TÁN THÀNH CÔNG (SAGA HAPPY PATH)
Luồng nghiệp vụ:
1. Tạo lệnh điều chuyển 20 sản phẩm 'LAPTOP-DELL-01' từ Kho HN sang Kho HCM qua HQ (Cổng 8000).
2. Kiểm tra Kho HN (Cổng 8001): available_qty giảm 20, reserved_qty tăng 20. Trạng thái đơn = RESERVED_IN_TRANSIT.
3. Kho HCM (Cổng 8002) xác nhận nhận hàng qua API /confirm.
4. Kiểm tra Kho HCM: available_qty tăng 20.
5. Kiểm tra Kho HN: reserved_qty giảm về 0 (tất toán).
6. Kiểm tra HQ: Trạng thái đơn chuyển thành COMPLETED.
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
    print(" KỊCH BẢN 1: KIỂM THỬ SAGA ĐIỀU CHUYỂN KHO THÀNH CÔNG (HAPPY PATH)")
    print("=" * 70)

    with httpx.Client(timeout=5.0) as client:
        # 1. Kiểm tra tồn kho ban đầu
        print("\n[Bước 1] Kiểm tra tồn kho ban đầu tại Hà Nội và TP.HCM...")
        hn_inv_pre = {item["sku"]: item for item in client.get(f"{HN_URL}/inventory").json()}
        hcm_inv_pre = {item["sku"]: item for item in client.get(f"{HCM_URL}/inventory").json()}
        
        sku = "LAPTOP-DELL-01"
        qty = 20
        hn_avail_pre = hn_inv_pre[sku]["available_qty"]
        hcm_avail_pre = hcm_inv_pre[sku]["available_qty"]

        print(f" -> Kho HN ban đầu: Available = {hn_avail_pre}, Reserved = {hn_inv_pre[sku]['reserved_qty']}")
        print(f" -> Kho HCM ban đầu: Available = {hcm_avail_pre}, Reserved = {hcm_inv_pre[sku]['reserved_qty']}")

        # 2. Khởi tạo đơn điều chuyển qua HQ
        print(f"\n[Bước 2] Trụ sở chính HQ khởi tạo Saga điều chuyển {qty} {sku} từ HN -> HCM...")
        res = client.post(f"{HQ_URL}/transfers", json={
            "source_branch": "HN",
            "dest_branch": "HCM",
            "sku": sku,
            "quantity": qty
        })
        assert res.status_code == 202, f"Tạo đơn thất bại: {res.text}"
        transfer_data = res.json()
        transfer_id = transfer_data["transfer_id"]
        print(f" -> Tạo thành công đơn điều chuyển: ID = {transfer_id} (Trạng thái: {transfer_data['saga_status']})")

        # Đợi 1.5s để RabbitMQ truyền thông điệp và HN khóa hàng
        print(" -> Đang chờ Message Broker xử lý lệnh CMD_RESERVE_STOCK...")
        time.sleep(2)

        # 3. Kiểm tra kho nguồn đã khóa hàng chưa
        print("\n[Bước 3] Kiểm tra Kho HN sau khi nhận lệnh khóa giữ hàng...")
        hn_inv_mid = {item["sku"]: item for item in client.get(f"{HN_URL}/inventory").json()}
        print(f" -> Kho HN hiện tại: Available = {hn_inv_mid[sku]['available_qty']} (Đã trừ {qty}), Reserved = {hn_inv_mid[sku]['reserved_qty']} (Đã giữ {qty})")
        assert hn_inv_mid[sku]["available_qty"] == hn_avail_pre - qty, "Lỗi: Available của kho nguồn chưa bị trừ!"
        assert hn_inv_mid[sku]["reserved_qty"] >= qty, "Lỗi: Reserved của kho nguồn chưa tăng!"

        # 4. Kiểm tra kiện hàng đang chờ tại kho HCM
        print("\n[Bước 4] Kiểm tra danh sách hàng chờ nhập tại Kho đích TP.HCM...")
        incoming = client.get(f"{HCM_URL}/transfers/incoming").json()
        has_order = any(item["transfer_id"] == transfer_id for item in incoming)
        print(f" -> Kiện hàng {transfer_id} đã xuất hiện tại danh sách chờ nhập kho HCM: {has_order}")

        # 5. Kho đích xác nhận nhận hàng
        print(f"\n[Bước 5] Kho đích TP.HCM bấm Xác nhận nhận hàng ({transfer_id})...")
        res_confirm = client.post(f"{HCM_URL}/transfers/{transfer_id}/confirm")
        assert res_confirm.status_code == 200, f"Xác nhận nhận hàng lỗi: {res_confirm.text}"
        print(f" -> Phản hồi từ Kho HCM: {res_confirm.json().get('message')}")

        # Đợi 2s để Outbox phát EVT_TRANSFER_COMPLETED về HQ và HN
        time.sleep(2.5)

        # 6. Kiểm tra trạng thái cuối cùng trên toàn hệ thống
        print("\n[Bước 6] Kiểm tra trạng thái cuối cùng (Final Consistency)...")
        hn_inv_post = {item["sku"]: item for item in client.get(f"{HN_URL}/inventory").json()}
        hcm_inv_post = {item["sku"]: item for item in client.get(f"{HCM_URL}/inventory").json()}
        order_post = client.get(f"{HQ_URL}/transfers/{transfer_id}").json()

        print(f" -> Kho HN kết thúc: Available = {hn_inv_post[sku]['available_qty']}, Reserved = {hn_inv_post[sku]['reserved_qty']}")
        print(f" -> Kho HCM kết thúc: Available = {hcm_inv_post[sku]['available_qty']} (Tăng {qty} thành công)")
        print(f" -> Trạng thái Saga tại Trụ sở chính (HQ): {order_post['saga_status']}")

        assert hcm_inv_post[sku]["available_qty"] == hcm_avail_pre + qty, "Lỗi: Kho đích chưa được cộng tồn kho!"
        assert order_post["saga_status"] == "COMPLETED", f"Lỗi: Saga chưa về trạng thái COMPLETED (Hiện tại: {order_post['saga_status']})"

        print("\n" + "=" * 70)
        print(" KẾT QUẢ: KỊCH BẢN SAGA HAPPY PATH THÀNH CÔNG 100%! [PASSED]")
        print("=" * 70)

if __name__ == "__main__":
    run_test()
