# HỆ THỐNG QUẢN LÝ KHO HÀNG PHÂN TÁN ĐA CHI NHÁNH (DISTRIBUTED WMS)

Hệ thống Quản lý Kho hàng Phân tán (Distributed Warehouse Management System) được thiết kế theo kiến trúc Vi dịch vụ (Microservices) chia sẻ không gian lưu trữ độc lập (Shared-Nothing Architecture), mô hình giao tiếp bất đồng bộ hướng sự kiện (Event-driven) qua RabbitMQ Topic Exchange, áp dụng đầy đủ các nguyên lý cốt lõi của môn học Các hệ thống phân tán: Định lý CAP (Lựa chọn AP + Eventual Consistency), Saga Pattern (Saga Orchestration & Compensating Transaction), Outbox Pattern, Idempotency (Tính bất biến) và Optimistic Concurrency Control (Khóa lạc quan chống tranh chấp âm kho).

---

## 1. TỔNG QUAN KIẾN TRÚC VÀ CÁC NODE HỆ THỐNG

Hệ thống bao gồm 3 Node dịch vụ độc lập hoàn toàn và cụm Message Broker trung gian:

1. **Node Trụ sở chính (HQ Service - Cổng 8000):**
   - Đóng vai trò Master Data Catalog: Quản lý danh mục hàng hóa gốc, duyệt chính sách giá bán.
   - Đóng vai trò Saga Coordinator: Khởi tạo và điều phối các giao dịch chuyển kho liên chi nhánh.
   - Bản chụp tồn kho toàn cục (Global Read-Model Snapshot - CQRS): Thu thập và cập nhật bất đồng bộ số liệu tồn kho từ các chi nhánh để phục vụ tra cứu toàn quốc mà không cần quét trực tiếp vào database chi nhánh.
   - Tiến trình Saga Timeout Worker: Tự động phát hiện các đơn hàng bị treo do đứt kết nối mạng để kích hoạt giao dịch bù trừ hoàn tác.
2. **Node Chi nhánh Hà Nội (Branch HN - Cổng 8001):**
   - Sở hữu cơ sở dữ liệu riêng biệt (db_branch_hn.db), tự trị quản lý tồn kho nội bộ tại Hà Nội.
   - Tiến trình Outbox Worker riêng: Đảm bảo việc ghi CSDL và bắn sự kiện sang RabbitMQ diễn ra tin cậy tuyệt đối (chống mất tin theo nguyên tắc At-Least-Once Delivery).
3. **Node Chi nhánh TP.HCM (Branch HCM - Cổng 8002):**
   - Sở hữu cơ sở dữ liệu riêng biệt (db_branch_hcm.db), tự trị quản lý tồn kho nội bộ tại TP.HCM.
   - Tiến trình Outbox Worker riêng: Tiếp nhận, phê duyệt xác nhận nhập kho hoặc từ chối kiện hàng để kích hoạt quy trình bù trừ hoàn tác.
4. **Message Broker (RabbitMQ - Cổng 5672 AMQP, 15672 Web Management):**
   - Topic Exchange `distributed_warehouse` chịu trách nhiệm phân phối thông điệp và sự kiện bất đồng bộ giữa các node, giúp các dịch vụ không bị phụ thuộc trực tiếp vào nhau (Decoupling).
5. **Giao diện Người dùng (Frontend ReactJS - Cổng 3000):**
   - Dashboard quản trị phân tách Route độc lập theo từng kho, xác thực người dùng bằng JWT Bearer Token và kiểm soát phân quyền (RBAC) nghiêm ngặt.

---

## 2. BẢNG ĐỊA CHỈ VÀ CỔNG TRUY CẬP DỊCH VỤ

| Thành phần | Địa chỉ URL | Chức năng chính |
| :--- | :--- | :--- |
| **Giao diện Web (Frontend)** | http://localhost:3000 | Web Dashboard quản trị toàn bộ hệ thống |
| **Node Trụ sở chính (HQ)** | http://localhost:8000/docs | Tài liệu Swagger REST API Trụ sở chính |
| **Node Chi nhánh Hà Nội (HN)** | http://localhost:8001/docs | Tài liệu Swagger REST API Chi nhánh Hà Nội |
| **Node Chi nhánh TP.HCM (HCM)** | http://localhost:8002/docs | Tài liệu Swagger REST API Chi nhánh TP.HCM |
| **RabbitMQ Management** | http://localhost:15672 | Bảng điều khiển Message Broker (guest / guest) |
| **MSSQL Database** | localhost:14333 | CSDL quan hệ Microsoft SQL Server 2022 |

---

## 3. HƯỚNG DẪN CÀI ĐẶT VÀ KHỞI CHẠY (QUICK START)

### 3.1. Yêu cầu hệ thống
- Đã cài đặt Docker Desktop và Docker Compose (trên Windows, macOS hoặc Linux).
- Đã cài đặt Python 3.11+ (dùng để chạy các kịch bản kiểm thử tự động trong thư mục `tests/`).

### 3.2. Khởi chạy toàn bộ hệ thống bằng Docker Compose
Mở Terminal (PowerShell hoặc Bash) tại thư mục gốc của dự án và thực hiện lệnh:

```bash
docker compose up -d --build
```

Lệnh trên sẽ tự động biên dịch mã nguồn và khởi chạy 6 container:
- `rabbitmq_wms`: Message Broker RabbitMQ 3.13 Management.
- `sqlserver_wms`: CSDL quan hệ Microsoft SQL Server 2022.
- `hq_service`: Dịch vụ Trụ sở chính (FastAPI - Cổng 8000).
- `branch_hn`: Dịch vụ Chi nhánh Hà Nội (FastAPI - Cổng 8001).
- `branch_hcm`: Dịch vụ Chi nhánh TP.HCM (FastAPI - Cổng 8002).
- `frontend_wms`: Giao diện Web Dashboard (ReactJS + Vite - Cổng 3000).

### 3.3. Kiểm tra trạng thái hoạt động của các dịch vụ
Sau khi khởi chạy khoảng 15 đến 20 giây để RabbitMQ hoàn tất mở cổng kết nối, chạy các lệnh kiểm tra sức khỏe (Health Check):

```bash
# Kiểm tra kết nối giữa 3 node backend với RabbitMQ Broker
curl -s http://localhost:8000/health
curl -s http://localhost:8001/health
curl -s http://localhost:8002/health
```

Kết quả phản hồi hợp lệ phải chứa `status: "UP"` và `broker_connected: true`.

*Lưu ý:* Nếu RabbitMQ khởi động chậm hơn backend trong lần chạy đầu tiên khiến cờ `broker_connected: false`, bạn chỉ cần khởi động lại 3 backend bằng lệnh:
```bash
docker restart hq_service branch_hn branch_hcm
```

### 3.4. Dừng toàn bộ hệ thống
Khi cần tắt toàn bộ cụm dịch vụ:
```bash
docker compose down
```

---

## 4. HỆ THỐNG TÀI KHOẢN VÀ PHÂN QUYỀN (RBAC & JWT)

Hệ thống phân tách Route và tài khoản rõ ràng theo vai trò tại địa chỉ `http://localhost:3000/login`:

| Tên tài khoản | Mật khẩu | Vai trò (Role) | Chi nhánh | Quyền hạn và Phạm vi hoạt động |
| :--- | :--- | :--- | :--- | :--- |
| **admin** | admin123 | HQ_MANAGER | HQ | Toàn quyền quản trị Trụ sở chính: Thêm/Sửa/Xóa Master Catalog, phân bổ tồn đầu kỳ cho chi nhánh, phát lệnh điều chuyển phân tán Saga, giám sát toàn quốc. |
| **manager_hn** | hn123 | BRANCH_MANAGER | HN | Quản lý Chi nhánh Hà Nội: Xuất bán/Nhập mua tại chỗ, duyệt kiện hàng chuyển đến, lập phiếu kiểm kê thực tế tại kệ. Không được can thiệp vào kho khác. |
| **manager_hcm** | hcm123 | BRANCH_MANAGER | HCM | Quản lý Chi nhánh TP.HCM: Tương tự Hà Nội, chỉ thao tác trên phạm vi CSDL kho TP.HCM. |
| **staff_hn** | staff123 | BRANCH_STAFF | HN | Thủ kho Hà Nội: Thực hiện phiếu xuất nhập, đếm hàng kiểm kê tại kệ. |
| **staff_hcm** | staff123 | BRANCH_STAFF | HCM | Thủ kho TP.HCM: Thực hiện phiếu xuất nhập, đếm hàng kiểm kê tại kệ. |

*Tiện ích:* Trên màn hình đăng nhập `/login` có tích hợp sẵn khay **"Tài khoản mẫu báo cáo đồ án (Quick Login)"** gồm 4 nút bấm tiện lợi, người dùng chỉ cần click chuột để đăng nhập ngay mà không cần nhập thủ công.

---

## 5. PHÂN TÁCH ROUTE VÀ CÁC TRANG CHỨC NĂNG

### 5.1. Trang Đăng Nhập (`/login`)
- Xác thực tài khoản qua REST API `POST /api/v1/auth/login`, cấp phát mã JWT Bearer Token có chữ ký số HMAC-SHA256.
- Tự động lưu Token vào `localStorage` và chuyển hướng người dùng về đúng trang quản trị theo vai trò.

### 5.2. Trang Quản trị Trụ sở Chính (`/hq` hoặc `/`)
- Dành riêng cho tài khoản có vai trò `HQ_MANAGER`.
- **Quản lý Danh mục Hàng hóa Master Data:**
  + Nút *Thêm Mặt Hàng Mới*: Nhập mã SKU, tên, đơn vị tính, đơn giá và chỉ định trực tiếp số lượng Tồn kho đầu kỳ cho Kho Hà Nội và Kho TP.HCM. Sự kiện `evt.catalog.product_created` sẽ tự động phát tán qua RabbitMQ để nạp vào CSDL cục bộ của cả 2 chi nhánh.
  + Nút *Sửa*: Cập nhật thông tin hàng hóa và đồng bộ tức thì sang các kho.
  + Nút *Xóa*: Tích hợp cơ chế Ràng buộc xóa an toàn (Delete Protection), chỉ cho phép xóa mặt hàng khi toàn bộ tồn kho trên tất cả các chi nhánh bằng 0.
- **Bộ điều phối Giao dịch Phân tán (Saga Coordinator):**
  + Form tạo đơn điều chuyển kho liên chi nhánh (Kho nguồn -> Kho đích).
  + Bảng Dòng thời gian Saga (Saga Timeline): Giám sát trạng thái điều phối theo thời gian thực: `INITIATED` -> `RESERVED_IN_TRANSIT` -> `COMPLETED` hoặc `CANCELLED_ROLLED_BACK`.
- **Bộ Giả lập & Chứng minh Đặc tính Phân tán (Network Chaos Simulator):**
  + Minh họa trực quan 3 đặc tính: Tự trị cục bộ (Local Autonomy), Khôi phục sau sự cố sập nguồn (Crash Recovery) và Tự động hoàn tác do quá hạn (Saga Coordinator Timeout).
- **Thanh Giám sát Nhanh:** Hỗ trợ Quản trị viên HQ chuyển nhanh sang góc nhìn kiểm tra của Kho Hà Nội và Kho TP.HCM.

### 5.3. Trang Chi nhánh Hà Nội (`/branch/hn`) và TP.HCM (`/branch/hcm`)
- Dành riêng cho nhân sự của từng chi nhánh tương ứng.
- **Nghiệp vụ Kho Cục bộ (Local Autonomy):**
  + Tab *Nhập Mua / Xuất Bán*: Nhập hàng từ Nhà cung cấp hoặc Xuất bán cho Khách hàng, ghi nhận đối tác và số hóa đơn vào sổ cái `Stock_Ledger`.
  + Tab *Kiểm Kê Thực Tế*: Nhập số lượng đếm thực tế tại kệ, hệ thống tự động so khớp với số liệu sổ sách, tính chênh lệch và điều chỉnh số dư khả dụng (`AUDIT_ADJUST`).
  + Cập nhật Định mức Tồn kho Min/Max để kích hoạt cờ cảnh báo thiếu hàng `is_low_stock`.
- **Tiếp nhận Kiện hàng Điều chuyển (Incoming Transfers):**
  + Xem danh sách các kiện hàng đang trên đường chuyển đến chi nhánh.
  + Nút *Xác Nhận Nhập Kho*: Tiếp nhận hàng hóa vào kho, hoàn tất đơn Saga (`COMPLETED`).
  + Nút *Từ Chối Nhận Hàng*: Phát sự kiện từ chối, kích hoạt quy trình giao dịch bù trừ hoàn tác (`Saga Rollback`) để hoàn trả số hàng khóa tạm về tồn khả dụng tại kho nguồn.
- **Bảng Đối soát Tồn kho Toàn quốc (Read-Only):**
  + Xem số liệu tồn kho toàn hệ thống ở chế độ Chỉ Đọc (ẩn toàn bộ các nút thêm/sửa/xóa của HQ).
- **Rào chắn Phân quyền (RBAC Route Guard):**
  + Nếu tài khoản thuộc Chi nhánh Hà Nội cố tình truy cập vào tuyến đường `/branch/hcm`, hệ thống sẽ chặn và hiển thị màn hình cảnh báo 403 Forbidden.

---

## 6. HƯỚNG DẪN KIỂM THỬ TỰ ĐỘNG QUA TERMINAL (TEST SUITES)

Dự án cung cấp bộ kịch bản kiểm thử tự động toàn diện được viết bằng Python trong thư mục `tests/`.

### 6.1. Thực thi các kịch bản kiểm thử
Mở Terminal (PowerShell trên Windows) tại thư mục gốc của dự án và chạy các lệnh:

```powershell
$env:PYTHONIOENCODING="utf-8"

# 1. Kiểm thử Saga điều chuyển thành công theo luồng chuẩn (Happy Path)
python tests/test_saga_happy_path.py

# 2. Kiểm thử Giao dịch bù trừ hoàn tác khi kho đích từ chối nhận hàng (Saga Rollback)
python tests/test_saga_rollback.py

# 3. Kiểm thử 10 yêu cầu xuất kho đồng thời chống âm kho (Race Condition & Optimistic Locking)
python tests/test_concurrency_race_condition.py

# 4. Kiểm thử toàn diện tính năng nâng cấp (JWT Auth, Catalog Replication, Kiểm kê kho, Bền bỉ hóa CSDL)
python tests/test_new_enhancements.py

# 5. Kiểm thử CRUD Master Data, Phân bổ tồn đầu kỳ HN/HCM và Ràng buộc xóa an toàn
python tests/test_crud_refinement.py
```

### 6.2. Ý nghĩa và kết quả xác minh của từng kịch bản
- `test_saga_happy_path.py`: Kho HN giảm 20, kho HCM tăng 20, đơn Saga tại HQ chuyển trạng thái `COMPLETED`.
- `test_saga_rollback.py`: Kho HCM từ chối nhận hàng, Saga Coordinator phát lệnh bù trừ `CMD_RELEASE_STOCK`, kho HN nhận lệnh và hoàn trả đầy đủ 15 sản phẩm giữ chỗ về tồn khả dụng, đơn Saga chuyển `CANCELLED_ROLLED_BACK`.
- `test_concurrency_race_condition.py`: Gửi đồng thời 10 yêu cầu đòi xuất tổng cộng 150 sản phẩm trong khi tồn khả dụng chỉ có 80. Hệ thống xử lý thành công đúng 5 yêu cầu (75 sản phẩm), chặn 5 yêu cầu còn lại, tồn kho còn đúng 5, tuyệt đối không bị âm kho.
- `test_crud_refinement.py`: Tạo sản phẩm mới tại HQ kèm chỉ định tồn kho cho HN (45) và HCM (25). CSDL chi nhánh tự động đồng bộ và ghi nhận bút toán `INITIAL_STOCK`. Kiểm tra hệ thống từ chối xóa sản phẩm khi vẫn còn tồn kho (>0). Sau khi kiểm kê về 0, thực hiện xóa thành công khỏi toàn bộ các node.

---

## 7. CẤU TRÚC THƯ MỤC DỰ ÁN

```
Khohang_phantan/
├── backend/
│   ├── branch_service/              # Dịch vụ Node Chi nhánh (FastAPI)
│   │   ├── consumers/               # RabbitMQ Consumer tiếp nhận lệnh điều phối
│   │   ├── routers/                 # REST API tồn kho, kiện hàng đến, kiểm kê
│   │   ├── services/                # Nghiệp vụ tồn kho và tiến trình Outbox Worker
│   │   └── models.py                # Mô hình CSDL SQLite cục bộ chi nhánh
│   ├── hq_service/                  # Dịch vụ Node Trụ sở chính (FastAPI)
│   │   ├── routers/                 # REST API danh mục, điều chuyển Saga, snapshot
│   │   ├── services/                # Tiến trình Saga Timeout Worker tự phục hồi
│   │   └── models.py                # Mô hình CSDL Master Catalog & Snapshots
│   └── shared/                      # Thư viện dùng chung giữa các node
│       ├── auth.py                  # Module xác thực HMAC-SHA256 Token & RBAC
│       ├── event_schemas.py         # Hợp đồng thông điệp phân tán (Pydantic)
│       └── rabbitmq_client.py       # Wrapper kết nối Topic Exchange RabbitMQ
├── frontend/                        # Web Dashboard (ReactJS + Vite + TailwindCSS)
│   └── src/
│       ├── components/              # GlobalStockTable, LocalBranchPanel, ChaosSimulator...
│       ├── context/                 # AuthContext quản lý JWT session
│       ├── pages/                   # LoginPage, HQDashboardPage, BranchDashboardPage
│       ├── api/client.js            # Client gọi REST API đính kèm Authorization header
│       └── App.jsx                  # Root Container và Bộ điều hướng Route Dispatcher
├── tests/                           # Bộ kịch bản kiểm thử phân tán tự động
├── Implement/                       # Nhật ký tiến độ và chi tiết triển khai theo ngày
├── docker-compose.yml               # Cấu hình khởi chạy toàn bộ 6 container
└── README.md                        # Tài liệu hướng dẫn dự án tiếng Việt
```

---

## 8. TÀI LIỆU THAM KHẢO VÀ HƯỚNG DẪN BÁO CÁO ĐỒ ÁN
- **Cẩm nang Hướng dẫn Thuyết trình & Bộ câu hỏi phản biện:** Xem tệp `HUONG_DAN_TEST_VA_KICH_BAN_BAO_CAO_DO_AN_UDPT.md` để nắm kịch bản nói 5 - 7 phút trước hội đồng và câu trả lời cho các câu hỏi lý thuyết phân tán hóc búa.
- **Nhật ký Triển khai Chi tiết:** Xem các tệp báo cáo tổng kết tại thư mục `Implement/2026-11-09.md` và `Implement/2026-11-10.md`.
