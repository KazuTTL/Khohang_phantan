-- ============================================================================
-- sql/init_hq.sql
-- Khởi tạo Schema đầy đủ cho Database Trụ sở chính (DB_HQ - Port 1433)
-- ============================================================================

-- 1. HQ Users (3 HQ Roles)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'HQ_Users')
BEGIN
    CREATE TABLE HQ_Users (
        user_id VARCHAR(50) PRIMARY KEY,
        full_name NVARCHAR(100) NOT NULL,
        role VARCHAR(20) NOT NULL CHECK (role IN ('HQ_STAFF','HQ_MANAGER','HQ_AUDITOR')),
        is_active BIT DEFAULT 1
    );
END
GO

-- 2. Branches
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Branches')
BEGIN
    CREATE TABLE Branches (
        branch_code VARCHAR(20) PRIMARY KEY,
        branch_name NVARCHAR(100) NOT NULL,
        api_base_url VARCHAR(255) NOT NULL,
        is_active BIT DEFAULT 1,
        is_online BIT DEFAULT 1
    );
END
GO

-- 3. Master Products
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Products')
BEGIN
    CREATE TABLE Products (
        sku VARCHAR(50) PRIMARY KEY,
        product_name NVARCHAR(200) NOT NULL,
        unit NVARCHAR(50) NOT NULL,
        is_deleted BIT DEFAULT 0,
        updated_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

-- 4. Global Inventory Snapshot (Read Model)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Global_Inventory_Snapshot')
BEGIN
    CREATE TABLE Global_Inventory_Snapshot (
        branch_code VARCHAR(20) NOT NULL,
        sku VARCHAR(50) NOT NULL,
        available_qty INT NOT NULL DEFAULT 0,
        reserved_qty INT NOT NULL DEFAULT 0,
        last_synced_at DATETIME2 DEFAULT SYSDATETIME(),
        PRIMARY KEY (branch_code, sku)
    );
END
GO

-- 5. Transfer Orders (Saga Orchestration State)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Transfer_Orders')
BEGIN
    CREATE TABLE Transfer_Orders (
        transfer_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        transfer_code VARCHAR(30) NOT NULL UNIQUE,
        source_branch VARCHAR(20) NOT NULL,
        dest_branch VARCHAR(20) NOT NULL,
        sku VARCHAR(50) NOT NULL,
        quantity INT NOT NULL CHECK (quantity > 0),
        -- Status flow:
        -- DRAFT → PENDING_HQ_APPROVAL → HQ_APPROVED → REJECTED_BY_HQ
        --   → PENDING_SOURCE_APPROVAL → SOURCE_APPROVED → REJECTED_BY_SOURCE
        --   → PENDING_DEST_APPROVAL → COMPLETED | REJECTED_BY_DEST
        --   → COMPENSATING → ROLLED_BACK
        --   → FAILED (nếu reserve fail)
        saga_status VARCHAR(40) NOT NULL,
        created_by VARCHAR(50) NOT NULL,
        hq_approved_by VARCHAR(50) NULL,
        source_approved_by VARCHAR(50) NULL,
        dest_approved_by VARCHAR(50) NULL,
        hq_approved_at DATETIME2 NULL,
        source_approved_at DATETIME2 NULL,
        dest_approved_at DATETIME2 NULL,
        hq_reject_reason NVARCHAR(500) NULL,
        source_reject_reason NVARCHAR(500) NULL,
        dest_reject_reason NVARCHAR(500) NULL,
        error_reason NVARCHAR(500) NULL,
        created_at DATETIME2 DEFAULT SYSDATETIME(),
        updated_at DATETIME2 DEFAULT SYSDATETIME()
    );
    CREATE INDEX IX_Transfer_Status ON Transfer_Orders(saga_status);
END
GO

-- 6. Saga Steps Log
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Saga_Steps')
BEGIN
    CREATE TABLE Saga_Steps (
        step_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        transfer_id UNIQUEIDENTIFIER NOT NULL,
        step_name VARCHAR(50) NOT NULL,
        status VARCHAR(20) NOT NULL,
        message_id UNIQUEIDENTIFIER NULL,
        payload NVARCHAR(MAX) NULL,
        created_at DATETIME2 DEFAULT SYSDATETIME()
    );
    CREATE INDEX IX_SagaSteps_Transfer ON Saga_Steps(transfer_id);
END
GO

-- 7. Outbox & Inbox
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
    CREATE INDEX IX_HQ_Outbox_Pending ON Outbox_Events(is_published, next_retry_at) WHERE is_published = 0;
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

-- 8. Global Stocktakes
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Stocktake_Sessions_Global')
BEGIN
    CREATE TABLE Stocktake_Sessions_Global (
        session_id UNIQUEIDENTIFIER PRIMARY KEY,
        session_code VARCHAR(30) NOT NULL,
        branch_code VARCHAR(20) NOT NULL,
        status VARCHAR(30) NOT NULL,
        scope_type VARCHAR(20) NOT NULL,
        total_skus_counted INT NOT NULL DEFAULT 0,
        total_variance_abs INT NOT NULL DEFAULT 0,
        created_by_name NVARCHAR(100) NULL,
        approved_by_name NVARCHAR(100) NULL,
        finalized_by_name NVARCHAR(100) NULL,
        created_at DATETIME2 NOT NULL,
        approved_at DATETIME2 NULL,
        finalized_at DATETIME2 NULL,
        last_synced_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Stocktake_Items_Global')
BEGIN
    CREATE TABLE Stocktake_Items_Global (
        item_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        session_id UNIQUEIDENTIFIER NOT NULL,
        sku VARCHAR(50) NOT NULL,
        system_qty_at_start INT NOT NULL,
        counted_qty INT NOT NULL,
        variance_qty INT NOT NULL,
        variance_reason NVARCHAR(500) NULL
    );
END
GO

-- Seed Data
IF NOT EXISTS (SELECT 1 FROM Branches WHERE branch_code = 'HN')
BEGIN
    INSERT INTO Branches (branch_code, branch_name, api_base_url, is_active, is_online)
    VALUES ('HN', N'Chi nhánh Hà Nội', 'http://branch_hn:8001', 1, 1);
END

IF NOT EXISTS (SELECT 1 FROM Branches WHERE branch_code = 'HCM')
BEGIN
    INSERT INTO Branches (branch_code, branch_name, api_base_url, is_active, is_online)
    VALUES ('HCM', N'Chi nhánh TP.HCM', 'http://branch_hcm:8002', 1, 1);
END

IF NOT EXISTS (SELECT 1 FROM HQ_Users WHERE user_id = 'hq_staff_01')
BEGIN
    INSERT INTO HQ_Users (user_id, full_name, role, is_active) VALUES
    ('hq_staff_01', N'Nguyễn Văn Nhân', 'HQ_STAFF', 1),
    ('hq_manager_01', N'Trần Thị Duyệt', 'HQ_MANAGER', 1),
    ('hq_auditor_01', N'Lê Văn Kiểm', 'HQ_AUDITOR', 1);
END
GO
