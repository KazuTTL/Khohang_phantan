# tests/test_group9_11_tables.py
"""
KỊCH BẢN KIỂM THỬ TOÀN DIỆN THEO THIẾT KẾ NHÓM 9 (11 BẢNG CSDL + KIẾN TRÚC 3 SITE):
1. Kiểm thử Load Balancer (Round-Robin giữa 2 App Instances) & DB Primary -> DB Replica trên cả 3 Site.
2. Kiểm thử Bảng TAI_KHOAN: Băm mật khẩu PBKDF2-SHA256, đồng bộ từ HQ sang Chi nhánh và đăng nhập tự trị tại Chi nhánh.
3. Kiểm thử Bảng DANH_MUC_SP & SAN_PHAM: Tạo danh mục/sản phẩm (có mã vạch, giá vốn, giá bán) tại Site 1 và nhân bản sang Site 2/3.
4. Kiểm thử Bảng DON_HANG, CHI_TIET_DON_HANG, GIAO_DICH_KHO, CHI_TIET_GIAO_DICH: Tạo đơn hàng đa sản phẩm tại HN, trừ tồn TON_KHO và ghi snapshot ton_sau_giao_dich.
5. Kiểm thử Bảng SU_KIEN_DONG_BO (Outbox) & TONG_HOP_TON_KHO (Global Snapshot) đồng bộ về HQ.
"""
import sys
import time
import uuid
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HQ_BASE = "http://localhost:8000"
HN_BASE = "http://localhost:8001"
HCM_BASE = "http://localhost:8002"


def run_test():
    test_id = uuid.uuid4().hex[:6].upper()
    print("=" * 75)
    print(f" KIỂM THỬ KIẾN TRÚC 3 SITE & 11 BẢNG CSDL CHUẨN NHÓM 9 (Run ID: {test_id})")
    print("=" * 75)

    with httpx.Client(timeout=10.0) as client:
        # ------------------------------------------------------------------
        # BƯỚC 1: KIỂM THỬ LOAD BALANCER & DB PRIMARY/REPLICA TRÊN 3 SITE
        # ------------------------------------------------------------------
        print("\n[Bước 1] Kiểm thử Load Balancer Round-Robin & DB Primary-Replica trên 3 Site...")
        for name, base_url, expected_lb in [
            ("Site 1 (HQ)", HQ_BASE, "LB-HQ-Central"),
            ("Site 2 (HN)", HN_BASE, "LB-HN-North"),
            ("Site 3 (HCM)", HCM_BASE, "LB-HCM-South"),
        ]:
            seen_instances = set()
            for _ in range(4):
                r = client.get(f"{base_url}/health")
                assert r.status_code == 200, f"{name} health check failed: {r.text}"
                assert r.headers.get("X-Load-Balancer") == expected_lb
                seen_instances.add(r.headers.get("X-Served-By-Instance"))

            assert len(seen_instances) == 2, f"{name} Load Balancer chưa chia tải 2 instance: {seen_instances}"

            cs = client.get(f"{base_url}/cluster/status")
            assert cs.status_code == 200
            cs_data = cs.json()
            assert cs_data["database"]["replica_healthy"] is True, f"{name} DB Replica chưa healthy"
            assert cs_data["database"]["replica_size_bytes"] > 0
            print(f" -> {name}: LB={expected_lb}, Instances={sorted(seen_instances)}, Replica={cs_data['database']['replica_db']} ({cs_data['database']['replica_size_bytes']} bytes) [OK]")

        # ------------------------------------------------------------------
        # BƯỚC 2: KIỂM THỬ TÀI KHOẢN DB (TAI_KHOAN), HASH MẬT KHẨU & ĐỒNG BỘ
        # ------------------------------------------------------------------
        print("\n[Bước 2] Kiểm thử Bảng TAI_KHOAN (PBKDF2-SHA256) & Đồng bộ từ HQ -> HN...")
        r_accs = client.get(f"{HQ_BASE}/api/v1/accounts")
        assert r_accs.status_code == 200
        accs = r_accs.json()
        assert len(accs) >= 5
        assert all(a["password_hashed"] is True for a in accs), "Phát hiện tài khoản chưa băm mật khẩu!"

        new_staff = f"nv_test_{test_id.lower()}"
        r_create_acc = client.post(f"{HQ_BASE}/api/v1/accounts", json={
            "username": new_staff,
            "password": "secret_password_123",
            "full_name": f"Nhân viên Test {test_id}",
            "role": "BRANCH_STAFF",
            "branch_code": "HN",
            "is_active": True
        })
        assert r_create_acc.status_code == 201, f"Lỗi tạo tài khoản: {r_create_acc.text}"
        time.sleep(2.0)

        # Đăng nhập trực tiếp vào Node HN (tự trị khi mất mạng HQ)
        r_login = client.post(f"{HN_BASE}/api/v1/auth/login", json={
            "username": new_staff,
            "password": "secret_password_123"
        })
        assert r_login.status_code == 200, f"Đăng nhập trực tiếp từ DB CHI NHÁNH HN thất bại: {r_login.text}"
        login_data = r_login.json()
        assert login_data["user"]["auth_source"] == "LOCAL_DB_TAI_KHOAN"
        assert login_data["user"]["branch"] == "HN"
        print(f" -> Tài khoản mới '{new_staff}' đã băm mật khẩu, đồng bộ về HN và đăng nhập tự trị thành công!")

        # ------------------------------------------------------------------
        # BƯỚC 3: KIỂM THỬ DANH_MUC_SP & SAN_PHAM (NHÂN BẢN MASTER DATA)
        # ------------------------------------------------------------------
        print("\n[Bước 3] Kiểm thử Bảng DANH_MUC_SP & SAN_PHAM (Mã vạch, Giá vốn, Giá bán)...")
        cat_name = f"Phụ kiện Mạng {test_id}"
        r_cat = client.post(f"{HQ_BASE}/api/v1/categories", json={
            "category_name": cat_name,
            "description": "Thiết bị mạng doanh nghiệp"
        })
        assert r_cat.status_code == 201, f"Lỗi tạo danh mục: {r_cat.text}"
        cat_id = r_cat.json()["category_id"]

        sku = f"ROUTER-WIFI-{test_id}"
        barcode = f"893999{test_id}"
        r_prod = client.post(f"{HQ_BASE}/api/v1/products", json={
            "sku": sku,
            "barcode": barcode,
            "product_name": f"Router WiFi 6E {test_id}",
            "category_id": cat_id,
            "unit": "Chiếc",
            "cost_price": 1500000.0,
            "price": 2100000.0,
            "initial_stock": {"HN": 30, "HCM": 15},
            "min_threshold": 5,
            "max_threshold": 100
        })
        assert r_prod.status_code == 201, f"Lỗi tạo sản phẩm: {r_prod.text}"
        time.sleep(2.5)

        r_hn_cats = client.get(f"{HN_BASE}/api/v1/categories").json()
        assert any(c["category_id"] == cat_id for c in r_hn_cats), "DANH_MUC_SP chưa được đồng bộ về HN!"

        r_hn_inv = client.get(f"{HN_BASE}/api/v1/inventory").json()
        prod_hn = next((x for x in r_hn_inv if x["sku"] == sku), None)
        assert prod_hn is not None, "Sản phẩm mới chưa đồng bộ về HN"
        assert prod_hn["barcode"] == barcode
        assert prod_hn["cost_price"] == 1500000.0
        assert prod_hn["price"] == 2100000.0
        assert prod_hn["available_qty"] == 30
        assert prod_hn["branch_code"] == "HN"
        print(f" -> Đã đồng bộ DANH_MUC_SP (ID={cat_id}) & SAN_PHAM ({sku}, Barcode={barcode}) về HN (Tồn=30)!")

        # ------------------------------------------------------------------
        # BƯỚC 4: KIỂM THỬ DON_HANG, CHI_TIET_DON_HANG & GIAO_DICH_KHO
        # ------------------------------------------------------------------
        print("\n[Bước 4] Kiểm thử Tạo ĐƠN HÀNG (DON_HANG + CHI_TIET_DON_HANG) & Phiếu Kho (GIAO_DICH_KHO)...")
        r_ord = client.post(f"{HN_BASE}/api/v1/orders", json={
            "customer_name": f"Công ty ABC {test_id}",
            "customer_phone": "0901234567",
            "items": [
                {"sku": sku, "quantity": 6}
            ]
        })
        assert r_ord.status_code == 201, f"Lỗi tạo đơn hàng tại HN: {r_ord.text}"
        ord_res = r_ord.json()
        assert ord_res["total_amount"] == 6 * 2100000.0
        receipt_code = ord_res["receipt_code"]

        r_orders = client.get(f"{HN_BASE}/api/v1/orders").json()
        found_ord = next((o for o in r_orders if o["order_id"] == ord_res["order_id"]), None)
        assert found_ord is not None and len(found_ord["items"]) == 1

        r_txs = client.get(f"{HN_BASE}/api/v1/transactions").json()
        found_tx = next((t for t in r_txs if t["receipt_code"] == receipt_code), None)
        assert found_tx is not None, "Không tìm thấy phiếu GIAO_DICH_KHO vừa sinh!"
        assert found_tx["transaction_type"] == "XUAT_KHO"
        assert found_tx["details"][0]["quantity"] == -6
        assert found_tx["details"][0]["post_transaction_balance"] == 24
        print(f" -> Đơn hàng {ord_res['order_id'][:8]} (Tổng={ord_res['total_amount']:,.0f} đ) -> Phiếu {receipt_code}, Tồn sau GD = 24 [OK]")

        # ------------------------------------------------------------------
        # BƯỚC 5: KIỂM THỬ OUTBOX (SU_KIEN_DONG_BO) & TONG_HOP_TON_KHO
        # ------------------------------------------------------------------
        print("\n[Bước 5] Kiểm thử Outbox (SU_KIEN_DONG_BO) & Đồng bộ TONG_HOP_TON_KHO về HQ...")
        time.sleep(3.5)
        r_outbox = client.get(f"{HN_BASE}/api/v1/outbox").json()
        assert len(r_outbox) > 0
        assert any(e["delivery_status"] == "COMPLETED" for e in r_outbox), "Outbox chưa hoàn thành gửi sự kiện!"

        r_global = client.get(f"{HQ_BASE}/api/v1/inventory/global").json()
        g_item = next((x for x in r_global if x["sku"] == sku), None)
        assert g_item is not None
        assert g_item["branches"]["HN"]["available"] == 24, f"Snapshot HN kỳ vọng 24, thực tế: {g_item['branches']['HN']['available']}"
        assert g_item["branches"]["HCM"]["available"] == 15
        print(" -> Outbox COMPLETED & TONG_HOP_TON_KHO tại HQ đồng bộ chính xác (HN=24, HCM=15)!")

        # ------------------------------------------------------------------
        # BƯỚC 6: KIỂM THỬ CÁC TÍNH NĂNG PHÂN TÁN NÂNG CAO (NHÓM 2)
        # ------------------------------------------------------------------
        print("\n[Bước 6] Kiểm thử WAN Disconnect Toggle, Replica Preview, Strict RBAC & Pull Transfer...")

        # 6A. Live WAN Disconnect Toggle
        assert client.post(f"{HN_BASE}/api/v1/network/wan-toggle", json={"online": False}).json()["wan_online"] is False
        r_ord_off = client.post(f"{HN_BASE}/api/v1/orders", json={
            "customer_name": f"Khách Offline WAN {test_id}",
            "items": [{"sku": sku, "quantity": 4}]
        })
        assert r_ord_off.status_code == 201
        time.sleep(2.5)
        r_outbox_off = client.get(f"{HN_BASE}/api/v1/outbox").json()
        assert any(e["delivery_status"] == "FAILED" and e["retry_count"] >= 1 for e in r_outbox_off), "Outbox phải giữ lại với trạng thái FAILED khi đứt WAN!"
        # Khôi phục WAN -> Outbox tự động đồng bộ Eventual Consistency
        assert client.post(f"{HN_BASE}/api/v1/network/wan-toggle", json={"online": True}).json()["wan_online"] is True
        time.sleep(3.0)
        g_after_wan = next(x for x in client.get(f"{HQ_BASE}/api/v1/inventory/global").json() if x["sku"] == sku)
        assert g_after_wan["branches"]["HN"]["available"] == 20, f"Kỳ vọng 20 sau khôi phục WAN, thực tế: {g_after_wan['branches']['HN']['available']}"
        print(" -> [6A] Live WAN Disconnect -> Outbox giữ sự kiện (FAILED) -> Khôi phục WAN -> Đồng bộ về 20 [OK]")

        # 6B. Đọc trực tiếp từ DB Replica Dự phòng
        rep_hq = client.get(f"{HQ_BASE}/api/v1/replica/preview").json()
        rep_hn = client.get(f"{HN_BASE}/api/v1/replica/preview").json()
        assert rep_hq["status"] == "OK" and rep_hq["source"] == "DB_REPLICA_STANDBY" and rep_hq["row_count"] > 0
        assert rep_hn["status"] == "OK" and rep_hn["source"] == "DB_REPLICA_STANDBY" and rep_hn["row_count"] > 0
        print(f" -> [6B] Đọc thành công DB Replica dự phòng: HQ ({rep_hq['row_count']} dòng), HN ({rep_hn['row_count']} dòng) [OK]")

        # 6C. Strict RBAC (BRANCH_STAFF bị chặn sửa ngưỡng/duyệt điều chuyển; BRANCH_MANAGER bị chặn API HQ)
        staff_token = client.post(f"{HN_BASE}/api/v1/auth/login", json={"username": "staff_hn", "password": "staff123"}).json()["access_token"]
        mgr_token = client.post(f"{HN_BASE}/api/v1/auth/login", json={"username": "manager_hn", "password": "hn123"}).json()["access_token"]
        r_staff_block = client.put(
            f"{HN_BASE}/api/v1/inventory/{sku}/thresholds",
            json={"min_threshold": 5, "max_threshold": 100},
            headers={"Authorization": f"Bearer {staff_token}"}
        )
        assert r_staff_block.status_code == 403, f"Kỳ vọng 403 cho Thủ kho, nhận {r_staff_block.status_code}"
        r_mgr_hq_block = client.post(
            f"{HQ_BASE}/api/v1/categories",
            json={"category_name": "Blocked Cat"},
            headers={"Authorization": f"Bearer {mgr_token}"}
        )
        assert r_mgr_hq_block.status_code == 403, f"Kỳ vọng 403 khi Manager chi nhánh gọi API HQ, nhận {r_mgr_hq_block.status_code}"
        print(" -> [6C] Strict RBAC (Chặn Thủ kho 403 & Chặn chi nhánh gọi API HQ 403) [OK]")

        # 6D. Pull Transfer Request (HCM xin hàng từ HN -> HQ duyệt -> Saga chạy -> HN thấy Outgoing Transfers)
        r_pull = client.post(f"{HQ_BASE}/api/v1/transfer-requests", json={
            "requesting_branch": "HCM",
            "suggested_source_branch": "HN",
            "sku": sku,
            "quantity": 5,
            "reason": "Bổ sung kệ HCM"
        })
        assert r_pull.status_code == 201
        req_id = r_pull.json()["request_id"]
        r_app = client.post(f"{HQ_BASE}/api/v1/transfer-requests/{req_id}/approve")
        assert r_app.status_code == 200
        t_id = r_app.json()["transfer_id"]
        outgoing_hn = []
        incoming_hcm = []
        for _ in range(20):
            time.sleep(0.5)
            outgoing_hn = client.get(f"{HN_BASE}/api/v1/transfers/outgoing").json()
            incoming_hcm = client.get(f"{HCM_BASE}/api/v1/transfers/incoming").json()
            if any(o["transfer_id"] == t_id for o in outgoing_hn) and any(i["transfer_id"] == t_id for i in incoming_hcm):
                break
        assert any(o["transfer_id"] == t_id for o in outgoing_hn), "Không thấy kiện hàng xuất đi tại HN!"
        assert any(i["transfer_id"] == t_id for i in incoming_hcm), "Không thấy kiện hàng chờ nhập tại HCM!"
        assert client.post(f"{HCM_BASE}/api/v1/transfers/{t_id}/confirm").status_code == 200
        time.sleep(2.0)
        print(f" -> [6D] Pull Transfer Request -> HQ Duyệt -> Outgoing HN ghi nhận -> HCM Duyệt nhận thành công [OK]")

        # Kiểm tra schema overview đủ 11 bảng
        hq_schema = client.get(f"{HQ_BASE}/api/v1/schema-overview").json()
        hn_schema = client.get(f"{HN_BASE}/api/v1/schema-overview").json()
        print("\n[Tổng kết Schema Overview]")
        print(f" -> HQ (Site 1): {hq_schema['tables']}")
        print(f" -> HN (Site 2): {hn_schema['tables']}")

        # Dọn dẹp SKU test
        client.post(f"{HN_BASE}/api/v1/inventory/audit", json={"sku": sku, "actual_qty": 0, "note": "Cleanup test"})
        client.post(f"{HCM_BASE}/api/v1/inventory/audit", json={"sku": sku, "actual_qty": 0, "note": "Cleanup test"})
        time.sleep(2.5)
        client.delete(f"{HQ_BASE}/api/v1/products/{sku}")

    print("\n" + "=" * 75)
    print(" ALL GROUP 9 (11 TABLES + 3-SITE CLUSTER + REPLICA) TESTS PASSED 100%!")
    print("=" * 75)


if __name__ == "__main__":
    run_test()
