-- ============================================================================
-- sql/init_branch_template.sql
-- Khởi tạo Schema đầy đủ cho Database Chi nhánh (chạy cho cả DB_Branch_HN và DB_Branch_HCM)
-- ============================================================================

-- 1. Users tại branch (8 Roles phân quyền)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Branch_Users')
BEGIN
    CREATE TABLE Branch_Users (
        user_id VARCHAR(50) PRIMARY KEY,
        full_name NVARCHAR(100) NOT NULL,
        role VARCHAR(20) NOT NULL CHECK (role IN ('STOCK_KEEPER','SALES','AUDITOR','BRANCH_MANAGER')),
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

-- 2. Danh mục sản phẩm (đồng bộ từ HQ)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Local_Products')
BEGIN
    CREATE TABLE Local_Products (
        sku VARCHAR(50) PRIMARY KEY,
        product_name NVARCHAR(200) NOT NULL,
        unit NVARCHAR(50) NOT NULL
    );
END
GO

-- 3. Tồn kho cục bộ (Pessimistic Row Lock: UPDLOCK, ROWLOCK)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Local_Inventory')
BEGIN
    CREATE TABLE Local_Inventory (
        sku VARCHAR(50) PRIMARY KEY,
        available_qty INT NOT NULL DEFAULT 0 CHECK (available_qty >= 0),
        reserved_qty INT NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
        version INT NOT NULL DEFAULT 1,
        updated_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

-- 4. Lịch sử biến động kho + Idempotency
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Stock_Ledger')
BEGIN
    CREATE TABLE Stock_Ledger (
        ledger_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        reference_id VARCHAR(100) NOT NULL UNIQUE,
        sku VARCHAR(50) NOT NULL,
        change_type VARCHAR(30) NOT NULL CHECK (change_type IN (
            'LOCAL_IN','LOCAL_OUT','RESERVE','COMMIT_OUT','RELEASE_RESERVE',
            'TRANSFER_IN','STOCKTAKE_ADJUST','PURCHASE_RECEIVE')),
        quantity INT NOT NULL,
        created_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

-- 5. Outbox & Inbox (Transactional Outbox & Idempotent Consumer)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Outbox_Events')
BEGIN
    CREATE TABLE Outbox_Events (
        event_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        routing_key VARCHAR(100) NOT NULL,
        payload NVARCHAR(MAX) NOT NULL,
        is_published BIT DEFAULT 0,
        retry_count INT DEFAULT 0,
        next_retry_at DATETIME2 DEFAULT SYSDATETIME(),
        created_at DATETIME2 DEFAULT SYSDATETIME()
    );
    CREATE INDEX IX_Outbox_Pending ON Outbox_Events(is_published, next_retry_at) 
        WHERE is_published = 0;
END
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Inbox_Events')
BEGIN
    CREATE TABLE Inbox_Events (
        message_id UNIQUEIDENTIFIER PRIMARY KEY,
        event_type VARCHAR(50) NOT NULL,
        processed_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

-- 6. Điều chuyển hàng hóa (Local mirror phục vụ phê duyệt 3 cấp)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Incoming_Transfers')
BEGIN
    CREATE TABLE Incoming_Transfers (
        transfer_id UNIQUEIDENTIFIER PRIMARY KEY,
        transfer_code VARCHAR(30) NULL,
        type VARCHAR(20) NOT NULL CHECK (type IN ('INBOUND','OUTBOUND')),
        sku VARCHAR(50) NOT NULL,
        quantity INT NOT NULL,
        source_branch VARCHAR(20) NOT NULL,
        dest_branch VARCHAR(20) NOT NULL,
        -- Status: AWAITING_SOURCE_APPROVAL | SOURCE_APPROVED | SOURCE_REJECTED
        --         | AWAITING_DEST_APPROVAL | DEST_APPROVED | DEST_REJECTED | CANCELLED
        status VARCHAR(30) NOT NULL,
        reject_reason NVARCHAR(500) NULL,
        received_qty INT NULL,
        created_at DATETIME2 DEFAULT SYSDATETIME(),
        updated_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

-- 7. Nhà cung cấp
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Suppliers')
BEGIN
    CREATE TABLE Suppliers (
        supplier_id VARCHAR(50) PRIMARY KEY,
        supplier_name NVARCHAR(200) NOT NULL,
        tax_code VARCHAR(20) NULL,
        contact_phone VARCHAR(20) NULL,
        is_active BIT DEFAULT 1
    );
END
GO

-- 8. Phiếu nhập NCC
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Purchase_Receipts')
BEGIN
    CREATE TABLE Purchase_Receipts (
        receipt_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        receipt_code VARCHAR(30) NOT NULL UNIQUE,
        branch_code VARCHAR(20) NOT NULL,
        supplier_id VARCHAR(50) NOT NULL,
        status VARCHAR(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
            'DRAFT','PENDING_APPROVAL','APPROVED','REJECTED','RECEIVED','FINALIZED','CANCELLED')),
        created_by VARCHAR(50) NOT NULL,
        approved_by VARCHAR(50) NULL,
        received_by VARCHAR(50) NULL,
        invoice_number VARCHAR(50) NULL,
        total_amount DECIMAL(18,2) NULL,
        note NVARCHAR(500) NULL,
        created_at DATETIME2 DEFAULT SYSDATETIME(),
        submitted_at DATETIME2 NULL,
        approved_at DATETIME2 NULL,
        rejected_at DATETIME2 NULL,
        received_at DATETIME2 NULL,
        reject_reason NVARCHAR(500) NULL,
        FOREIGN KEY (supplier_id) REFERENCES Suppliers(supplier_id)
    );
END
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Purchase_Receipt_Items')
BEGIN
    CREATE TABLE Purchase_Receipt_Items (
        item_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        receipt_id UNIQUEIDENTIFIER NOT NULL,
        sku VARCHAR(50) NOT NULL,
        expected_qty INT NOT NULL CHECK (expected_qty > 0),
        received_qty INT NULL,
        unit_price DECIMAL(18,2) NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'PENDING' 
            CHECK (status IN ('PENDING','RECEIVED','SHORTAGE','OVERAGE')),
        FOREIGN KEY (receipt_id) REFERENCES Purchase_Receipts(receipt_id)
    );
END
GO

-- 9. Phiếu kiểm kê
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Stocktake_Sessions')
BEGIN
    CREATE TABLE Stocktake_Sessions (
        session_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        session_code VARCHAR(30) NOT NULL UNIQUE,
        branch_code VARCHAR(20) NOT NULL,
        status VARCHAR(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
            'DRAFT','COUNTING','PENDING_APPROVAL','APPROVED','REJECTED','CANCELLED','FINALIZED')),
        scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('FULL','BY_SKU')),
        scope_note NVARCHAR(500) NULL,
        created_by VARCHAR(50) NOT NULL,
        counted_by VARCHAR(50) NULL,
        approved_by VARCHAR(50) NULL,
        finalized_by VARCHAR(50) NULL,
        created_at DATETIME2 DEFAULT SYSDATETIME(),
        counting_started_at DATETIME2 NULL,
        submitted_at DATETIME2 NULL,
        approved_at DATETIME2 NULL,
        rejected_at DATETIME2 NULL,
        cancelled_at DATETIME2 NULL,
        finalized_at DATETIME2 NULL,
        cancel_reason NVARCHAR(500) NULL,
        reject_reason NVARCHAR(500) NULL
    );
    CREATE INDEX IX_Stocktake_Branch_Status ON Stocktake_Sessions(branch_code, status);
END
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Stocktake_Items')
BEGIN
    CREATE TABLE Stocktake_Items (
        item_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        session_id UNIQUEIDENTIFIER NOT NULL,
        sku VARCHAR(50) NOT NULL,
        system_qty_at_start INT NOT NULL DEFAULT 0,
        counted_qty INT NULL,
        variance_qty INT NULL,
        variance_reason NVARCHAR(500) NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'PENDING' 
            CHECK (status IN ('PENDING','COUNTED','ADJUSTED')),
        counted_at DATETIME2 NULL,
        adjusted_at DATETIME2 NULL,
        FOREIGN KEY (session_id) REFERENCES Stocktake_Sessions(session_id),
        UNIQUE (session_id, sku)
    );
END
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Stocktake_Audit_Log')
BEGIN
    CREATE TABLE Stocktake_Audit_Log (
        log_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        session_id UNIQUEIDENTIFIER NOT NULL,
        action VARCHAR(50) NOT NULL,
        performed_by VARCHAR(50) NOT NULL,
        note NVARCHAR(500) NULL,
        created_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Stock_Freeze_Log')
BEGIN
    CREATE TABLE Stock_Freeze_Log (
        freeze_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        session_id UNIQUEIDENTIFIER NOT NULL,
        sku VARCHAR(50) NULL,           -- NULL = freeze toàn branch
        frozen_at DATETIME2 DEFAULT SYSDATETIME(),
        released_at DATETIME2 NULL
    );
END
GO

-- Seed users mẫu
IF NOT EXISTS (SELECT 1 FROM Branch_Users WHERE user_id = 'keeper_hn_01')
BEGIN
    INSERT INTO Branch_Users (user_id, full_name, role, is_active) VALUES
    ('keeper_hn_01', N'Nguyễn Văn Kho', 'STOCK_KEEPER', 1),
    ('sales_hn_01', N'Vũ Thị Bán', 'SALES', 1),
    ('auditor_hn_01', N'Lê Thị Kiểm', 'AUDITOR', 1),
    ('manager_hn_01', N'Trần Văn Quản', 'BRANCH_MANAGER', 1);
END
GO
