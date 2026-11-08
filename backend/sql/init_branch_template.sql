-- ============================================================================
-- init_branch_template.sql
-- Template khởi tạo CSDL cho từng Node Chi nhánh (DB_Branch_HN, DB_Branch_HCM, ...)
-- Phục vụ tính năng Tự trị Cục bộ (Local Autonomy) & Kiểm soát đồng thời
-- ============================================================================

-- 1. Bảng Danh mục Sản phẩm Cục bộ (Đồng bộ bất đồng bộ từ HQ)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Local_Products')
BEGIN
    CREATE TABLE Local_Products (
        sku VARCHAR(50) PRIMARY KEY,
        product_name NVARCHAR(200) NOT NULL,
        unit NVARCHAR(50) NOT NULL,
        updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
END
GO

-- 2. Bảng Tồn kho Cục bộ (Nơi áp dụng khóa dòng UPDLOCK, ROWLOCK)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Local_Inventory')
BEGIN
    CREATE TABLE Local_Inventory (
        sku VARCHAR(50) PRIMARY KEY,
        available_qty INT NOT NULL DEFAULT 0 CHECK (available_qty >= 0),
        reserved_qty INT NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
        updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        CONSTRAINT FK_Local_Inventory_Product FOREIGN KEY (sku) REFERENCES Local_Products(sku)
    );
END
GO

-- 3. Bảng Nhật ký Biến động Kho Cục bộ (Stock Ledger)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Stock_Ledger')
BEGIN
    CREATE TABLE Stock_Ledger (
        ledger_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        transaction_type VARCHAR(50) NOT NULL, 
        -- LOCAL_IN | LOCAL_OUT | SAGA_RESERVE | SAGA_RELEASE | SAGA_OUT | SAGA_IN | STOCKTAKE_ADJUST
        sku VARCHAR(50) NOT NULL,
        quantity INT NOT NULL,
        available_after INT NOT NULL,
        reserved_after INT NOT NULL,
        reference_id VARCHAR(100) NULL,
        idempotency_key VARCHAR(100) NULL,
        note NVARCHAR(500) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
    CREATE UNIQUE INDEX IX_Ledger_Idempotency ON Stock_Ledger(idempotency_key) WHERE idempotency_key IS NOT NULL;
END
GO

-- 4. Bảng Outbox Messages tại Chi nhánh (Transactional Outbox Pattern)
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
    CREATE INDEX IX_Branch_Outbox_Pending ON Outbox_Messages(status, created_at);
END
GO

-- 5. Bảng Inbox Messages tại Chi nhánh (Idempotent Consumer)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Inbox_Messages')
BEGIN
    CREATE TABLE Inbox_Messages (
        message_id VARCHAR(50) NOT NULL,
        consumer_name VARCHAR(100) NOT NULL,
        processed_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        CONSTRAINT PK_Branch_Inbox PRIMARY KEY (message_id, consumer_name)
    );
END
GO

-- 6. Bảng Bản ghi Kiểm kê Cục bộ (Stocktake Records)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Stocktake_Records')
BEGIN
    CREATE TABLE Stocktake_Records (
        record_id VARCHAR(50) PRIMARY KEY,
        session_id VARCHAR(50) NOT NULL,
        sku VARCHAR(50) NOT NULL,
        system_qty INT NOT NULL,
        actual_qty INT NOT NULL,
        diff_qty INT NOT NULL,
        note NVARCHAR(500) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        CONSTRAINT FK_Stocktake_Product FOREIGN KEY (sku) REFERENCES Local_Products(sku)
    );
END
GO
