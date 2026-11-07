# BÁO CÁO TIẾN ĐỘ & HIỆN TRẠNG TRIỂN KHAI DỰ ÁN
## Hệ thống Quản lý Kho hàng Phân tán Đa Chi nhánh

> **Cập nhật lần cuối:** 06/11/2026 (Đã khởi chạy & Xác thực thành công 100%)  
> **Học phần:** Phát triển Ứng dụng Phân tán (UDPT)  
> **Quy mô dự án:** Nhóm 3 thành viên (TV1, TV2, TV3)  
> **Trạng thái hệ thống:** 🟢 **TOÀN BỘ 4 DỊCH VỤ ĐANG HOẠT ĐỘNG (ONLINE)**

---

## 1. Trạng thái Vận hành Hiện tại (Live Cluster Status)

| Dịch vụ / Node | Cổng (Port) | Vai trò phân tán | Trạng thái Live | Đường dẫn truy cập |
| :--- | :---: | :--- | :---: | :--- |
| **Giao diện Web (Frontend)** | `3000` | Single Page Application (ReactJS + Vite + Tailwind) | 🟢 **ONLINE** | [http://localhost:3000](http://localhost:3000) |
| **Node Trụ sở chính (HQ)** | `8000` | Saga Coordinator, Master Catalog, Global Read-Model | 🟢 **ONLINE** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **Chi nhánh Hà Nội (HN)** | `8001` | Branch Node 1, CSDL cục bộ, Khóa dòng, Outbox | 🟢 **ONLINE** | [http://localhost:8001/docs](http://localhost:8001/docs) |
| **Chi nhánh TP.HCM (HCM)** | `8002` | Branch Node 2, CSDL cục bộ, Phê duyệt Saga | 🟢 **ONLINE** | [http://localhost:8002/docs](http://localhost:8002/docs) |

---

## 2. Kết Quả Xác Minh 4 Kịch Bản Kiểm Thử Phân Tán (100% PASSED)

Tất cả 4 kịch bản kiểm thử bảo vệ đồ án đã được chạy trực tiếp trên hệ thống đang chạy và đạt kết quả hoàn hảo:

### ✅ Kịch bản 1: Giao dịch phân tán hoàn tất thành công (Saga Happy Path)
- **Tệp kiểm thử:** `tests/test_saga_happy_path.py`
- **Kết quả:** `PASSED`
- **Diễn biến:**
  1. Kho HN ban đầu có 100 sản phẩm `LAPTOP-DELL-01`, Kho HCM có 50.
  2. HQ khởi tạo đơn điều chuyển 20 sản phẩm sang HCM.
  3. Kho HN nhận lệnh `CMD_RESERVE_STOCK`: `available_qty` giảm còn 80, `reserved_qty` tăng 20.
  4. Kiện hàng xuất hiện tại danh sách chờ nhập kho của Kho HCM.
  5. Kho HCM bấm "Xác nhận nhận hàng": Tồn khả dụng HCM tăng lên 70 (+20).
  6. Trạng thái đơn tại HQ chuyển thành `COMPLETED`.

### ✅ Kịch bản 2: Giao dịch bù trừ hoàn tác khi phát sinh sự cố (Saga Compensation / Rollback)
- **Tệp kiểm thử:** `tests/test_saga_rollback.py`
- **Kết quả:** `PASSED`
- **Diễn biến:**
  1. Kho HN có 40 sản phẩm `MACBOOK-AIR-M2`. Khởi tạo điều chuyển 15 sản phẩm sang HCM.
  2. Kho HN tạm khóa 15 sản phẩm (`available = 25`, `reserved = 15`).
  3. Kho HCM từ chối nhận hàng với lý do "Kho đích bảo trì kệ, không đủ chỗ chứa".
  4. HQ kích hoạt chuỗi bù trừ, phát lệnh `CMD_RELEASE_STOCK` về Kho HN.
  5. Kho HN giải phóng giữ chỗ: `available_qty` được hoàn trả đầy đủ về 40, `reserved_qty = 0`.
  6. Trạng thái đơn tại HQ chuyển thành `CANCELLED_ROLLED_BACK`.

### ✅ Kịch bản 3: Tự trị cục bộ và chống trùng lặp thông điệp (Local Autonomy & Idempotency)
- **Tệp kiểm thử:** `tests/e2e_distributed_test.py`
- **Kết quả:** `PASSED`
- **Diễn biến:**
  1. Kho HN thực hiện xuất bán lẻ tại chỗ 5 sản phẩm độc lập.
  2. Giả lập lỗi mạng, Client gửi lại cùng một `reference_id` (Retry).
  3. Hệ thống phát hiện trùng lặp (`is_duplicate = True`), trả về kết quả cũ mà tuyệt đối không trừ kho lặp lần thứ hai (At-Most-Once Semantics).
  4. Sổ cái `Stock_Ledger` chỉ ghi đúng 1 bản ghi duy nhất.

### ✅ Kịch bản 4: Kiểm soát xung đột đồng thời chống âm kho (Concurrency & Race Condition)
- **Tệp kiểm thử:** `tests/test_concurrency_race_condition.py`
- **Kết quả:** `PASSED`
- **Diễn biến:**
  1. Kho HN còn 50 sản phẩm `CHUOT-LOGI-MX3`.
  2. Bắn đồng thời 10 yêu cầu xuất kho (mỗi yêu cầu đòi 15 sản phẩm, tổng nhu cầu là 150 sản phẩm) trong cùng 1 mili-giây.
  3. Nhờ cơ chế kiểm soát đồng thời (Row Locking & Mutex Lock), chỉ có đúng 3 yêu cầu đầu tiên thành công (xuất 45 sản phẩm).
  4. 7 yêu cầu còn lại bị từ chối với lý do "Tồn kho không đủ để xuất bán".
  5. Tồn kho thực tế còn lại đúng 5 sản phẩm, tuyệt đối không bị âm kho.

---

## 3. Lệnh Dừng và Khởi Động Lại Hệ Thống

Khi muốn dừng toàn bộ các dịch vụ:
```powershell
.\stop_distributed.ps1
```

Khi muốn khởi động lại toàn bộ:
```powershell
.\start_distributed.ps1
```
