-- ============================================================================
-- init_hq.sql
-- Khởi tạo Schema và dữ liệu mẫu cho Database Trụ sở chính (DB_HQ)
-- ============================================================================

USE DB_HQ;
GO

-- 1. Bảng Danh mục Chi nhánh
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Branches')
BEGIN
    CREATE TABLE Branches (
        branch_code VARCHAR(20) PRIMARY KEY,
        branch_name NVARCHAR(100) NOT NULL,
        is_active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
END
GO

-- 2. Bảng Danh mục Sản phẩm Chuẩn (Master Catalog)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Products')
BEGIN
    CREATE TABLE Products (
        sku VARCHAR(50) PRIMARY KEY,
        product_name NVARCHAR(200) NOT NULL,
        unit NVARCHAR(50) NOT NULL,
        base_price DECIMAL(18, 2) NOT NULL DEFAULT 0,
        is_active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
END
GO

-- 3. Bảng Tổng hợp Tồn kho Toàn hệ thống (Snapshot Read-Model)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Global_Inventory_Snapshot')
BEGIN
    CREATE TABLE Global_Inventory_Snapshot (
        branch_code VARCHAR(20) NOT NULL,
        sku VARCHAR(50) NOT NULL,
        available_qty INT NOT NULL DEFAULT 0,
        reserved_qty INT NOT NULL DEFAULT 0,
        last_synced_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        CONSTRAINT PK_Global_Inventory PRIMARY KEY (branch_code, sku),
        CONSTRAINT FK_Global_Branch FOREIGN KEY (branch_code) REFERENCES Branches(branch_code),
        CONSTRAINT FK_Global_Product FOREIGN KEY (sku) REFERENCES Products(sku)
    );
END
GO

-- 4. Bảng Điều phối Giao dịch Điều chuyển Kho (Saga State Store)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Transfer_Orders')
BEGIN
    CREATE TABLE Transfer_Orders (
        transfer_id VARCHAR(50) PRIMARY KEY,
        source_branch VARCHAR(20) NOT NULL,
        dest_branch VARCHAR(20) NOT NULL,
        sku VARCHAR(50) NOT NULL,
        quantity INT NOT NULL CHECK (quantity > 0),
        -- Trạng thái Saga: INITIATED | RESERVED_IN_TRANSIT | COMPLETED | COMPENSATING | ROLLED_BACK | FAILED
        saga_status VARCHAR(30) NOT NULL,
        error_reason NVARCHAR(500) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
END
GO

-- 5. Bảng Phiên Kiểm kê Toàn hệ thống (Stocktake Sessions)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Stocktake_Sessions')
BEGIN
    CREATE TABLE Stocktake_Sessions (
        session_id VARCHAR(50) PRIMARY KEY,
        title NVARCHAR(200) NOT NULL,
        status VARCHAR(30) NOT NULL DEFAULT 'OPEN', -- OPEN | CLOSED | CANCELLED
        created_by VARCHAR(50) NOT NULL DEFAULT 'SYSTEM',
        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        closed_at DATETIME2 NULL
    );
END
GO

-- 6. Bảng Outbox Messages tại HQ (Transactional Outbox)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Outbox_Messages')
BEGIN
    CREATE TABLE Outbox_Messages (
        message_id VARCHAR(50) PRIMARY KEY,
        event_type VARCHAR(100) NOT NULL,
        routing_key VARCHAR(100) NOT NULL,
        payload NVARCHAR(MAX) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- PENDING | PROCESSED | FAILED
        retry_count INT NOT NULL DEFAULT 0,
        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        processed_at DATETIME2 NULL
    );
    CREATE INDEX IX_Outbox_Pending ON Outbox_Messages(status, created_at);
END
GO

-- 7. Bảng Inbox Messages tại HQ (Idempotent Consumer)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Inbox_Messages')
BEGIN
    CREATE TABLE Inbox_Messages (
        message_id VARCHAR(50) NOT NULL,
        consumer_name VARCHAR(100) NOT NULL,
        processed_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        CONSTRAINT PK_HQ_Inbox PRIMARY KEY (message_id, consumer_name)
    );
END
GO

-- Nạp dữ liệu mẫu ban đầu
MERGE Branches AS target
USING (VALUES 
    ('HN', N'Kho Chi nhánh Hà Nội', 1),
    ('HCM', N'Kho Chi nhánh TP.HCM', 1)
) AS source (branch_code, branch_name, is_active)
ON (target.branch_code = source.branch_code)
WHEN NOT MATCHED THEN
    INSERT (branch_code, branch_name, is_active)
    VALUES (source.branch_code, source.branch_name, source.is_active);

MERGE Products AS target
USING (VALUES 
    ('BAN-PHIM-CO', N'Bàn phím cơ không dây Bluetooth Pro', N'Chiếc', 1250000, 1),
    ('CHUOT-LOGI-MX3', N'Chuột công thái học cao cấp Silent', N'Chiếc', 890000, 1),
    ('TAI-NGHE-SONY', N'Tai nghe chụp tai chống ồn ANC', N'Chiếc', 2450000, 1),
    ('MAN-HINH-4K', N'Màn hình đồ họa 27 inch 4K HDR', N'Chiếc', 6800000, 1)
) AS source (sku, product_name, unit, base_price, is_active)
ON (target.sku = source.sku)
WHEN NOT MATCHED THEN
    INSERT (sku, product_name, unit, base_price, is_active)
    VALUES (source.sku, source.product_name, source.unit, source.base_price, source.is_active);

-- Snapshot ban đầu
MERGE Global_Inventory_Snapshot AS target
USING (VALUES
    ('HN', 'BAN-PHIM-CO', 120, 0),
    ('HN', 'CHUOT-LOGI-MX3', 85, 0),
    ('HN', 'TAI-NGHE-SONY', 45, 0),
    ('HN', 'MAN-HINH-4K', 30, 0),
    ('HCM', 'BAN-PHIM-CO', 60, 0),
    ('HCM', 'CHUOT-LOGI-MX3', 40, 0),
    ('HCM', 'TAI-NGHE-SONY', 15, 0),
    ('HCM', 'MAN-HINH-4K', 20, 0)
) AS source (branch_code, sku, available_qty, reserved_qty)
ON (target.branch_code = source.branch_code AND target.sku = source.sku)
WHEN NOT MATCHED THEN
    INSERT (branch_code, sku, available_qty, reserved_qty)
    VALUES (source.branch_code, source.sku, source.available_qty, source.reserved_qty);
GO
