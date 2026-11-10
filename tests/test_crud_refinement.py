# tests/test_crud_refinement.py
"""
Test kịch bản hoàn thiện CRUD Danh mục Sản phẩm & Phân bổ Tồn kho Đầu kỳ Đa Chi nhánh
"""
import time
import httpx
import uuid

HQ_URL = "http://localhost:8000"
HN_URL = "http://localhost:8001"
HCM_URL = "http://localhost:8002"

def run_test():
    client = httpx.Client(timeout=10.0)
    test_id = str(uuid.uuid4())[:6].upper()
    test_sku = f"TEST-PROD-{test_id}"

    print(f"\n=======================================================")
    print(f"BAT DAU TEST CRUD & INITIAL STOCK: {test_sku}")
    print(f"=======================================================")

    # 1. Kiem tra tao san pham moi voi ton kho ban dau cho HN va HCM
    print("\n[BƯỚC 1] Tạo sản phẩm mới kèm phân bổ tồn đầu kỳ (HN: 45, HCM: 25)...")
    create_payload = {
        "sku": test_sku,
        "product_name": f"Thiết bị Đo Kiểm {test_id}",
        "unit": "Bộ",
        "price": 12500000.0,
        "category": "Thiết bị đo",
        "initial_stock": {
            "HN": 45,
            "HCM": 25
        },
        "min_threshold": 15,
        "max_threshold": 300
    }
    res = client.post(f"{HQ_URL}/api/v1/products", json=create_payload)
    assert res.status_code == 201, f"Lỗi tạo sản phẩm: {res.text}"
    created_prod = res.json()
    assert created_prod["sku"] == test_sku
    print(f"-> Tạo thành công Master Data tại HQ cho SKU: {test_sku}")

    # Đợi 2-3 giây để RabbitMQ đồng bộ bất đồng bộ tới các chi nhánh
    print("\n[BƯỚC 2] Chờ RabbitMQ phát tán sự kiện EVT_PRODUCT_CREATED tới các chi nhánh...")
    time.sleep(3)

    # 2. Kiểm tra snapshot tại HQ
    res_snap = client.get(f"{HQ_URL}/api/v1/inventory/global")
    assert res_snap.status_code == 200
    global_items = {item["sku"]: item for item in res_snap.json()}
    assert test_sku in global_items, f"SKU {test_sku} chưa xuất hiện trong Snapshot HQ"
    snap_item = global_items[test_sku]
    assert snap_item["total_available"] == 70, f"Tổng khả dụng kỳ vọng 70, thực tế: {snap_item['total_available']}"
    assert snap_item["branches"]["HN"]["available"] == 45
    assert snap_item["branches"]["HCM"]["available"] == 25
    print("-> Snapshot tại HQ hiển thị chính xác tổng tồn kho và tồn chi nhánh: 45 (HN) + 25 (HCM) = 70")

    # 3. Kiểm tra cơ sở dữ liệu nội bộ tại Chi nhánh HN
    res_hn = client.get(f"{HN_URL}/api/v1/inventory")
    assert res_hn.status_code == 200
    hn_inv = next((x for x in res_hn.json() if x["sku"] == test_sku), None)
    assert hn_inv is not None, f"SKU {test_sku} chưa được replicate tới Chi nhánh HN"
    assert hn_inv["available_qty"] == 45, f"Tồn kho tại HN kỳ vọng 45, thực tế: {hn_inv['available_qty']}"
    print(f"-> Chi nhánh HN đã nhận event và lưu tồn kho: {hn_inv['available_qty']} {hn_inv['unit']}")

    # Kiểm tra ledger của HN có ghi nhận INITIAL_STOCK
    res_ledger_hn = client.get(f"{HN_URL}/api/v1/ledger")
    assert res_ledger_hn.status_code == 200
    init_ledger = next((l for l in res_ledger_hn.json() if l["sku"] == test_sku and l["change_type"] == "INITIAL_STOCK"), None)
    assert init_ledger is not None, "Không tìm thấy bút toán INITIAL_STOCK trong Sổ cái HN"
    print(f"-> Sổ cái HN đã ghi nhận bút toán INITIAL_STOCK: Ref={init_ledger['reference_id']}, Qty={init_ledger['quantity']}")

    # 4. Kiểm tra cập nhật thông tin sản phẩm và điều chỉnh tồn kho chi nhánh (Update with Branch Stock)
    print("\n[BƯỚC 3] Chỉnh sửa thông tin Master Data và điều chỉnh tồn kho chi nhánh (HN: 45->60, HCM: 25->35)...")
    update_payload = {
        "product_name": f"Thiết bị Đo Kiểm Nâng Cấp {test_id}",
        "unit": "Hộp",
        "price": 13900000.0,
        "min_threshold": 20,
        "max_threshold": 350,
        "branch_stock": {
            "HN": 60,
            "HCM": 35
        }
    }
    res_update = client.put(f"{HQ_URL}/api/v1/products/{test_sku}", json=update_payload)
    assert res_update.status_code == 200, f"Lỗi cập nhật sản phẩm: {res_update.text}"
    print("-> Cập nhật thành công tại HQ. Đang chờ đồng bộ tới chi nhánh...")
    time.sleep(3)

    # Kiểm tra snapshot tại HQ
    res_snap_after = client.get(f"{HQ_URL}/api/v1/inventory/global")
    snap_after_items = {item["sku"]: item for item in res_snap_after.json()}
    snap_after = snap_after_items[test_sku]
    assert snap_after["total_available"] == 95, f"Tổng tồn kỳ vọng 95, thực tế: {snap_after['total_available']}"
    assert snap_after["branches"]["HN"]["available"] == 60
    assert snap_after["branches"]["HCM"]["available"] == 35
    print(f"-> Snapshot HQ ghi nhận số lượng mới: HN=60, HCM=35 (Tổng = 95)")

    # Kiểm tra tồn kho nội bộ tại Chi nhánh HN
    res_hn_after = client.get(f"{HN_URL}/api/v1/inventory")
    hn_inv_after = next((x for x in res_hn_after.json() if x["sku"] == test_sku), None)
    assert hn_inv_after is not None
    assert hn_inv_after["product_name"] == f"Thiết bị Đo Kiểm Nâng Cấp {test_id}"
    assert hn_inv_after["unit"] == "Hộp"
    assert hn_inv_after["available_qty"] == 60, f"Tồn kho HN kỳ vọng 60, thực tế: {hn_inv_after['available_qty']}"
    print(f"-> Chi nhánh HN đã đồng bộ: Tên='{hn_inv_after['product_name']}', Tồn kho={hn_inv_after['available_qty']}")

    # Kiểm tra sổ cái HN ghi nhận HQ_UPDATE
    res_ledger_hn_after = client.get(f"{HN_URL}/api/v1/ledger")
    update_ledger_hn = next((l for l in res_ledger_hn_after.json() if l["sku"] == test_sku and l["change_type"] == "HQ_UPDATE"), None)
    assert update_ledger_hn is not None, "Không tìm thấy bút toán HQ_UPDATE trong Sổ cái HN"
    assert update_ledger_hn["quantity"] == 15, f"Độ lệch sổ cái kỳ vọng 15, thực tế: {update_ledger_hn['quantity']}"
    print(f"-> Sổ cái HN ghi nhận biến động HQ_UPDATE: Qty={update_ledger_hn['quantity']}")

    # Kiểm tra tồn kho nội bộ tại Chi nhánh HCM
    res_hcm_after = client.get(f"{HCM_URL}/api/v1/inventory")
    hcm_inv_after = next((x for x in res_hcm_after.json() if x["sku"] == test_sku), None)
    assert hcm_inv_after is not None
    assert hcm_inv_after["available_qty"] == 35, f"Tồn kho HCM kỳ vọng 35, thực tế: {hcm_inv_after['available_qty']}"
    print(f"-> Chi nhánh HCM đã đồng bộ tồn kho mới: {hcm_inv_after['available_qty']}")

    # 5. Kiểm tra ràng buộc bảo vệ toàn vẹn: Không được xóa khi còn tồn kho (>0)
    print("\n[BƯỚC 4] Kiểm tra ràng buộc an toàn khi xóa sản phẩm đang có tồn kho...")
    res_del_fail = client.delete(f"{HQ_URL}/api/v1/products/{test_sku}")
    assert res_del_fail.status_code == 400, f"Kỳ vọng HTTP 400 nhưng nhận: {res_del_fail.status_code}"
    print(f"-> Hệ thống từ chối xóa chính xác với thông báo bảo vệ: '{res_del_fail.json().get('detail')}'")

    # 6. Đưa tồn kho về 0 thông qua kiểm kê kho (Audit)
    print("\n[BƯỚC 5] Đưa tồn kho các chi nhánh về 0 bằng phiếu kiểm kê (Audit)...")
    res_audit_hn = client.post(f"{HN_URL}/api/v1/inventory/audit", json={"sku": test_sku, "actual_qty": 0, "note": "Thanh lý trước khi xóa"})
    assert res_audit_hn.status_code == 200
    res_audit_hcm = client.post(f"{HCM_URL}/api/v1/inventory/audit", json={"sku": test_sku, "actual_qty": 0, "note": "Thanh lý trước khi xóa"})
    assert res_audit_hcm.status_code == 200

    # Chờ Outbox worker đồng bộ về HQ snapshot
    time.sleep(3)

    # 7. Thử xóa lại khi tồn kho đã về 0
    print("\n[BƯỚC 6] Xóa sản phẩm khi tồn kho đã về 0...")
    res_del_success = client.delete(f"{HQ_URL}/api/v1/products/{test_sku}")
    assert res_del_success.status_code == 200, f"Lỗi xóa sản phẩm khi tồn kho = 0: {res_del_success.text}"
    print(f"-> HQ đã xóa sản phẩm thành công: {res_del_success.json().get('message')}")

    time.sleep(2)
    # Xác minh sản phẩm không còn trong snapshot HQ
    res_snap_final = client.get(f"{HQ_URL}/api/v1/inventory/global")
    final_skus = [item["sku"] for item in res_snap_final.json()]
    assert test_sku not in final_skus, "SKU vẫn còn tồn tại trong snapshot HQ sau khi xóa"
    print(f"-> Đã xác minh SKU '{test_sku}' được loại bỏ hoàn toàn khỏi Master Catalog & Snapshots!")

    print("\n=======================================================")
    print("ALL CRUD & INITIAL STOCK TESTS PASSED 100%!")
    print("=======================================================\n")

if __name__ == "__main__":
    run_test()
