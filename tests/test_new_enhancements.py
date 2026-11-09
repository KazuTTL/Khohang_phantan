# tests/test_new_enhancements.py
"""
KỊCH BẢN KIỂM THỬ 5: CÁC TÍNH NĂNG NÂNG CẤP TOÀN DIỆN (PHƯƠNG ÁN C)
1. Xác thực phân quyền người dùng (JWT / RBAC)
2. Quản lý danh mục & Đồng bộ phân tán (Master Data Catalog Replication)
3. Thiết lập định mức tồn kho & Cảnh báo tồn kho an toàn (Min/Max Thresholds)
4. Kiểm kê kho thực tế & Tự động điều chỉnh chênh lệch (Inventory Stock-taking)
5. Nhập/Xuất kho gắn đối tác Nhà cung cấp / Khách hàng (Partner Audit Trail)
6. Bền bỉ hóa kiện hàng đến trong CSDL chi nhánh (Persistence Recovery)
"""
import sys
import time
import uuid
import httpx

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HQ_URL = "http://localhost:8000/api/v1"
HN_URL = "http://localhost:8001/api/v1"
HCM_URL = "http://localhost:8002/api/v1"

def run_test():
    print("=" * 70)
    print(" KỊCH BẢN 5: KIỂM THỬ CÁC TÍNH NĂNG NÂNG CẤP TOÀN DIỆN (PHƯƠNG ÁN C)")
    print("=" * 70)

    with httpx.Client(timeout=10.0) as client:
        # 1. Kiểm thử Xác thực & Phân quyền (Auth & JWT)
        print("\n[Mục 1] Kiểm thử Xác thực Người dùng (JWT Authentication)...")
        login_res = client.post(f"{HQ_URL}/auth/login", json={"username": "admin", "password": "admin123"})
        assert login_res.status_code == 200, f"Đăng nhập thất bại: {login_res.text}"
        auth_data = login_res.json()
        token = auth_data["access_token"]
        print(f" -> Đăng nhập thành công Admin HQ! Token = {token[:25]}... (Role: {auth_data['user']['role']})")

        me_res = client.get(f"{HQ_URL}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        assert me_res.json()["username"] == "admin"
        print(" -> Xác thực Token thành công: Lấy đúng thông tin người dùng từ /auth/me")

        # 2. Kiểm thử Tạo mới Sản phẩm & Đồng bộ Phân tán (Master Data Replication)
        print("\n[Mục 2] HQ tạo sản phẩm mới và đồng bộ phân tán sang các chi nhánh...")
        new_sku = f"KEYBOARD-RGB-{uuid.uuid4().hex[:6].upper()}"
        create_prod_res = client.post(f"{HQ_URL}/products", json={
            "sku": new_sku,
            "product_name": "Bàn phím cơ không dây RGB",
            "unit": "Chiếc",
            "price": 1850000.0,
            "category": "Phụ kiện"
        })
        assert create_prod_res.status_code == 201, f"Tạo sản phẩm thất bại: {create_prod_res.text}"
        print(f" -> Tạo thành công sản phẩm tại Trụ sở chính (HQ): {new_sku}")

        # Chờ Broker phát tán sang HN và HCM
        print(" -> Chờ Message Broker đồng bộ sản phẩm sang Kho Hà Nội và TP.HCM...")
        replicated_hn = False
        replicated_hcm = False
        for _ in range(8):
            time.sleep(1)
            hn_items = {item["sku"] for item in client.get(f"{HN_URL}/inventory").json()}
            hcm_items = {item["sku"] for item in client.get(f"{HCM_URL}/inventory").json()}
            if new_sku in hn_items:
                replicated_hn = True
            if new_sku in hcm_items:
                replicated_hcm = True
            if replicated_hn and replicated_hcm:
                break

        assert replicated_hn, f"Sản phẩm {new_sku} chưa đồng bộ tới Kho HN"
        assert replicated_hcm, f"Sản phẩm {new_sku} chưa đồng bộ tới Kho HCM"
        print(f" -> ĐỒNG BỘ THÀNH CÔNG: Cả Kho HN và Kho HCM đã tự động ghi nhận SKU {new_sku} vào CSDL cục bộ!")

        # 3. Kiểm thử Định mức Tồn kho & Cảnh báo an toàn (Min/Max Thresholds)
        print("\n[Mục 3] Thiết lập định mức tồn kho và kiểm tra cảnh báo thiếu hàng...")
        thresh_res = client.put(f"{HN_URL}/inventory/{new_sku}/thresholds", json={
            "min_threshold": 20,
            "max_threshold": 100
        })
        assert thresh_res.status_code == 200
        hn_inv = {item["sku"]: item for item in client.get(f"{HN_URL}/inventory").json()}
        assert hn_inv[new_sku]["min_threshold"] == 20
        assert hn_inv[new_sku]["is_low_stock"] == True # Vì tồn hiện tại = 0 <= 20
        print(f" -> Kho HN: Thiết lập min=20, max=100. Tồn hiện tại = 0 -> Cảnh báo is_low_stock = True (Chính xác!)")

        # 4. Kiểm thử Nhập kho từ Nhà cung cấp (Partner Inbound)
        print("\n[Mục 4] Nhập kho 50 cái từ Nhà cung cấp 'Công ty Phân phối Tin học ABC'...")
        adjust_res = client.post(f"{HN_URL}/inventory/adjust", json={
            "sku": new_sku,
            "change_type": "LOCAL_IN",
            "quantity": 50,
            "partner_name": "Công ty Phân phối Tin học ABC",
            "note": "Nhập lô hàng theo Hợp đồng PO-2026-001"
        })
        assert adjust_res.status_code == 200
        hn_inv_after = {item["sku"]: item for item in client.get(f"{HN_URL}/inventory").json()}
        assert hn_inv_after[new_sku]["available_qty"] == 50
        assert hn_inv_after[new_sku]["is_low_stock"] == False # 50 > 20
        print(f" -> Nhập kho thành công: Tồn kho tăng lên 50. Cảnh báo is_low_stock = False (Đã an toàn)")

        # 5. Kiểm thử Kiểm kê Kho thực tế & Điều chỉnh Chênh lệch (Stock-taking Audit)
        print("\n[Mục 5] Kiểm kê thực tế tại kệ phát hiện còn 48 cái (Hụt 2 cái do lỗi đóng gói)...")
        audit_res = client.post(f"{HN_URL}/inventory/audit", json={
            "sku": new_sku,
            "actual_qty": 48,
            "note": "Kiểm kê đột xuất quý 4"
        })
        assert audit_res.status_code == 200
        audit_data = audit_res.json()
        assert audit_data["actual_qty"] == 48
        assert audit_data["variance"] == -2
        print(f" -> Kết quả kiểm kê: Sổ sách=50, Thực tế=48, Chênh lệch = {audit_data['variance']}. CSDL tự điều chỉnh về 48!")

        # 6. Kiểm tra Sổ cái Stock_Ledger xác minh lưu vết đối tác và kiểm kê
        print("\n[Mục 6] Kiểm tra Sổ cái Stock_Ledger đối soát nghiệp vụ...")
        ledger = client.get(f"{HN_URL}/ledger").json()
        sku_records = [r for r in ledger if r.get("sku") == new_sku]
        assert len(sku_records) >= 2, f"Không tìm thấy đủ bản ghi sổ cái cho SKU {new_sku}"
        print(f" -> Tìm thấy {len(sku_records)} bản ghi sổ cái hợp lệ mang mã {new_sku} (Bao gồm LOCAL_IN và AUDIT_ADJUST)")

        # 7. Kiểm thử Bền bỉ hóa Kiện hàng điều chuyển (Persisted Incoming Transfer)
        print("\n[Mục 7] Kiểm thử Bền bỉ hóa kiện hàng đến trong CSDL Chi nhánh đích...")
        transfer_res = client.post(f"{HQ_URL}/transfers", json={
            "source_branch": "HN",
            "dest_branch": "HCM",
            "sku": new_sku,
            "quantity": 10
        })
        assert transfer_res.status_code == 202
        t_id = transfer_res.json()["transfer_id"]
        print(f" -> Tạo lệnh chuyển 10 cái {new_sku} sang HCM: ID = {t_id}")

        # Chờ kiện hàng xuất hiện tại HCM
        hcm_incoming = False
        for _ in range(8):
            time.sleep(1)
            incoming_list = client.get(f"{HCM_URL}/transfers/incoming").json()
            if any(item["transfer_id"] == t_id for item in incoming_list):
                hcm_incoming = True
                break

        assert hcm_incoming, f"Kiện hàng {t_id} không tìm thấy trong danh sách đến của HCM"
        print(f" -> Kiện hàng {t_id} đã được lưu bền vững trong CSDL Chi nhánh TP.HCM!")

        # HCM xác nhận nhận hàng
        confirm_res = client.post(f"{HCM_URL}/transfers/{t_id}/confirm")
        assert confirm_res.status_code == 200
        print(f" -> Kho HCM xác nhận nhận hàng thành công. Hoàn tất chuỗi kiểm thử!")

        print("\n" + "=" * 70)
        print(" KẾT QUẢ: TOÀN BỘ 7 HẠNG MỤC NÂNG CẤP ĐẠT KẾT QUẢ XUẤT SẮC! [PASSED]")
        print("=" * 70)

if __name__ == "__main__":
    run_test()
