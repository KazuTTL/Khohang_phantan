-- ==============================================================================
-- DATABASE SCHEMA: HỆ THỐNG QUẢN LÝ KHO ĐA CHI NHÁNH PHÂN TÁN
-- Tuân thủ: Nghiệp vụ UDPT (BFD 1.0 - 6.0) & Chịu lỗi Hệ phân tán (Chương 8)
-- ==============================================================================

-- 1. THỰC THỂ GỐC: KHO (Kho là to nhất - Root Node)
CREATE TABLE IF NOT EXISTS warehouses (
    id TEXT PRIMARY KEY,                 -- Mã kho: HN, DN, SG
    name TEXT NOT NULL,                 -- Tên chi nhánh: Kho Hà Nội, Đà Nẵng, TP.HCM
    address TEXT,                       -- Địa chỉ thực tế
    phone TEXT,                         -- Hotline chi nhánh
    status TEXT DEFAULT 'ACTIVE'        -- ACTIVE, INACTIVE, MAINTENANCE
);

-- 2. PHÂN HỆ 1.0: DANH MỤC HÀNG HÓA CHUNG (D1)
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,                 -- Mã sản phẩm: SP001, SP002...
    name TEXT NOT NULL,                 -- Tên sản phẩm
    sku TEXT UNIQUE,                    -- Barcode / SKU
    unit TEXT DEFAULT 'Cái',            -- Đơn vị tính: Cái, Thùng, Hộp, Kg
    category TEXT,                      -- Nhóm hàng: May mặc, Điện tử, Gia dụng
    price REAL DEFAULT 0.0              -- Giá niêm yết
);

-- 3. PHÂN HỆ 6.0: VỊ TRÍ LƯU TRỮ TRONG KHO (D3)
-- Phân cấp chi tiết: Kho -> Khu vực (Zone) -> Dãy (Aisle) -> Kệ (Rack) -> Tầng (Shelf) -> Ô (Bin)
CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY,                 -- Mã ô: HN-Z1-A01-R01-S1-B01
    warehouse_id TEXT NOT NULL,         -- Thuộc kho nào
    zone TEXT NOT NULL,                 -- Khu vực: ZONE-A (Hàng nhanh), ZONE-B (Hàng nặng)...
    aisle TEXT NOT NULL,                -- Dãy: A01, A02...
    rack TEXT NOT NULL,                 -- Kệ: R01, R02...
    shelf TEXT NOT NULL,                -- Tầng: S1, S2...
    bin TEXT NOT NULL,                  -- Ô: B01, B02...
    capacity INTEGER DEFAULT 1000,      -- Sức chứa tối đa (đơn vị sản phẩm)
    status TEXT DEFAULT 'AVAILABLE',    -- AVAILABLE, FULL, OCCUPIED, DISABLED
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);

-- BẢNG LIÊN KẾT TỒN KHO THEO VỊ TRÍ (Gắn trực tiếp từng ô kệ với hàng hóa)
CREATE TABLE IF NOT EXISTS location_stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,  -- Số lượng thực tế đang nằm tại ô
    reserved INTEGER NOT NULL DEFAULT 0,  -- Số lượng đang được giữ chỗ (đang chờ xuất hoặc chuyển)
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(location_id, product_id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
    FOREIGN KEY (location_id) REFERENCES locations(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- 4. PHÂN HỆ 2.0: QUẢN LÝ NHẬP KHO (Gắn trực tiếp với vị trí ô kệ)
CREATE TABLE IF NOT EXISTS import_orders (
    id TEXT PRIMARY KEY,                 -- Mã phiếu: NK-2026-001
    warehouse_id TEXT NOT NULL,         -- Kho tiếp nhận
    supplier_name TEXT NOT NULL,        -- Nhà cung cấp
    created_by TEXT NOT NULL,           -- Nhân viên lập phiếu
    received_by TEXT,                   -- Thủ kho thực tế nhận hàng
    status TEXT DEFAULT 'PENDING',      -- PENDING, COMPLETED, CANCELLED
    note TEXT,                          -- Ghi chú nhập hàng
    total_amount REAL DEFAULT 0.0,      -- Tổng giá trị phiếu nhập
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);

CREATE TABLE IF NOT EXISTS import_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    location_id TEXT NOT NULL,          -- Xếp vào vị trí/ô kệ nào
    quantity INTEGER NOT NULL,          -- Số lượng nhập vào ô
    unit_price REAL DEFAULT 0.0,        -- Đơn giá nhập
    FOREIGN KEY (order_id) REFERENCES import_orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

-- 5. PHÂN HỆ 3.0: QUẢN LÝ XUẤT KHO (Lấy từ vị trí ô kệ cụ thể)
CREATE TABLE IF NOT EXISTS export_orders (
    id TEXT PRIMARY KEY,                 -- Mã phiếu: XK-2026-001
    warehouse_id TEXT NOT NULL,         -- Kho xuất
    customer_name TEXT NOT NULL,        -- Khách hàng hoặc Đơn vị nhận
    created_by TEXT NOT NULL,           -- Nhân viên lập phiếu
    picked_by TEXT,                     -- Nhân viên nhặt hàng / lấy hàng từ kệ
    status TEXT DEFAULT 'PENDING',      -- PENDING, COMPLETED, CANCELLED
    note TEXT,
    total_amount REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);

CREATE TABLE IF NOT EXISTS export_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    location_id TEXT NOT NULL,          -- Nhặt từ vị trí/ô kệ nào
    quantity INTEGER NOT NULL,          -- Số lượng nhặt ra
    unit_price REAL DEFAULT 0.0,        -- Đơn giá bán/xuất
    FOREIGN KEY (order_id) REFERENCES export_orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

-- 6. PHÂN HỆ 4.0: CHUYỂN KHO LIÊN CHI NHÁNH (Điều phối bởi 2PC Coordinator)
CREATE TABLE IF NOT EXISTS transfer_orders (
    id TEXT PRIMARY KEY,                 -- Mã giao dịch 2PC txn_id (UUID)
    from_warehouse_id TEXT NOT NULL,    -- Kho xuất đi
    to_warehouse_id TEXT NOT NULL,      -- Kho nhận đến
    created_by TEXT NOT NULL,           -- Người tạo yêu cầu chuyển
    status TEXT DEFAULT 'INIT',         -- INIT -> PREPARED -> COMMITTED / ABORTED
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_warehouse_id) REFERENCES warehouses(id),
    FOREIGN KEY (to_warehouse_id) REFERENCES warehouses(id)
);

CREATE TABLE IF NOT EXISTS transfer_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transfer_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    from_location_id TEXT NOT NULL,     -- Vị trí lấy ở kho xuất
    to_location_id TEXT NOT NULL,       -- Vị trí cất ở kho đích
    quantity INTEGER NOT NULL,
    FOREIGN KEY (transfer_id) REFERENCES transfer_orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- 7. PHÂN HỆ 5.0: TỒN KHO & PHIẾU KIỂM KÊ (Đầy đủ trạng thái + Người kiểm kê)
CREATE TABLE IF NOT EXISTS audit_notes (
    id TEXT PRIMARY KEY,                 -- Mã phiếu: KK-2026-001
    warehouse_id TEXT NOT NULL,         -- Kho kiểm kê
    title TEXT NOT NULL,                -- Tiêu đề đợt kiểm kê
    status TEXT DEFAULT 'DRAFT',        -- DRAFT (Mới tạo) -> IN_PROGRESS (Đang kiểm kê) -> COMPLETED (Đã kiểm kê) -> ADJUSTED (Đã cân bằng) | CANCELLED (Đã hủy)
    auditor_name TEXT NOT NULL,         -- Ai là người đi kiểm kê thực tế
    approved_by TEXT,                   -- Quản lý kho / Kế toán trưởng phê duyệt cân bằng
    note TEXT,                          -- Đánh giá chung
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,             -- Thời điểm hoàn tất kiểm đếm
    adjusted_at TIMESTAMP,              -- Thời điểm phê duyệt cân bằng kho
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);

CREATE TABLE IF NOT EXISTS audit_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id TEXT NOT NULL,
    location_id TEXT NOT NULL,          -- Ô kệ kiểm kê
    product_id TEXT NOT NULL,           -- Mặt hàng kiểm kê
    system_qty INTEGER NOT NULL,        -- Số lượng tồn hệ thống sổ sách ghi nhận
    actual_qty INTEGER,                 -- Số lượng đếm thực tế
    diff_qty INTEGER DEFAULT 0,         -- Lệch: actual_qty - system_qty (Âm là thiếu, Dương là thừa)
    reason TEXT,                        -- Nguyên nhân chênh lệch (Hỏng hóc, Thất thoát, Nhầm lẫn)
    FOREIGN KEY (audit_id) REFERENCES audit_notes(id),
    FOREIGN KEY (location_id) REFERENCES locations(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- ==============================================================================
-- CÁC BẢNG CHỊU LỖI HỆ THỐNG PHÂN TÁN (DISTRIBUTED SYSTEMS CHAPTER 8)
-- ==============================================================================

-- 8. MỤC 8.3: BẢNG DEDUPLICATION / IDEMPOTENCY CHO RPC & CLIENT-SERVER
-- Đảm bảo nếu client gửi lại cùng 1 txn_id thì không bị thực hiện lại hai lần
CREATE TABLE IF NOT EXISTS processed_txns (
    txn_id TEXT PRIMARY KEY,            -- Idempotency key (UUID hoặc Mã giao dịch)
    operation TEXT NOT NULL,            -- Tên nghiệp vụ (IMPORT, EXPORT, TRANSFER, AUDIT)
    result TEXT NOT NULL,               -- PREPARED, COMMITTED, ABORTED, SUCCESS, FAILED
    response_payload TEXT,              -- Kết quả trả về lưu trữ dạng JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. MỤC 8.5 & 8.6: WRITE-AHEAD LOG (WAL) TRÊN TỪNG NODE KHO (PESSIMISTIC LOGGING)
CREATE TABLE IF NOT EXISTS wal_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id TEXT NOT NULL,
    operation TEXT NOT NULL,            -- PREPARE, COMMIT, ABORT, ADJUST_STOCK
    payload TEXT,                       -- Tham số dữ liệu JSON
    state TEXT NOT NULL,                -- INIT, READY, COMMITTED, ABORTED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
