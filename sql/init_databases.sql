-- ==============================================================================
-- SQL SERVER INITIALIZATION SCRIPT FOR DISTRIBUTED WAREHOUSE SYSTEM
-- Khởi tạo 3 Cơ sở dữ liệu: DB_HQ, DB_Branch_HN, DB_Branch_HCM
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. TẠO CƠ SỞ DỮ LIỆU DB_HQ (Node Trụ sở chính)
-- ------------------------------------------------------------------------------
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'DB_HQ')
BEGIN
    CREATE DATABASE DB_HQ;
END
GO

USE DB_HQ;
GO

-- Bảng Branches: Danh mục các chi nhánh trực thuộc
IF OBJECT_ID('Branches', 'U') IS NULL
BEGIN
    CREATE TABLE Branches (
        branch_code VARCHAR(20) PRIMARY KEY, -- 'HN', 'HCM', 'DN'
        branch_name NVARCHAR(100) NOT NULL,
        api_base_url VARCHAR(255) NOT NULL,
        is_active BIT DEFAULT 1
    );
END
GO

-- Bảng Products: Danh mục sản phẩm chuẩn Master Data
IF OBJECT_ID('Products', 'U') IS NULL
BEGIN
    CREATE TABLE Products (
        sku VARCHAR(50) PRIMARY KEY,
        product_name NVARCHAR(200) NOT NULL,
        unit NVARCHAR(50) NOT NULL,
        price DECIMAL(18,2) DEFAULT 0.0,
        updated_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

-- Bảng Global_Inventory_Snapshot: Tổng hợp tồn kho toàn hệ thống (Đồng bộ bất đồng bộ từ các chi nhánh)
IF OBJECT_ID('Global_Inventory_Snapshot', 'U') IS NULL
BEGIN
    CREATE TABLE Global_Inventory_Snapshot (
        branch_code VARCHAR(20) NOT NULL,
        sku VARCHAR(50) NOT NULL,
        available_qty INT NOT NULL DEFAULT 0,
        reserved_qty INT NOT NULL DEFAULT 0,
        last_synced_at DATETIME2 DEFAULT SYSDATETIME(),
        PRIMARY KEY (branch_code, sku),
        FOREIGN KEY (branch_code) REFERENCES Branches(branch_code)
    );
END
GO

-- Bảng Transfer_Orders: Quản lý trạng thái giao dịch Saga Điều phối chuyển kho
IF OBJECT_ID('Transfer_Orders', 'U') IS NULL
BEGIN
    CREATE TABLE Transfer_Orders (
        transfer_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        source_branch VARCHAR(20) NOT NULL,
        dest_branch VARCHAR(20) NOT NULL,
        sku VARCHAR(50) NOT NULL,
        quantity INT NOT NULL CHECK (quantity > 0),
        -- Trạng thái Saga: INITIATED | RESERVED_IN_TRANSIT | COMPLETED | COMPENSATING | CANCELLED_ROLLED_BACK | FAILED
        saga_status VARCHAR(30) NOT NULL,
        error_reason NVARCHAR(500) NULL,
        created_at DATETIME2 DEFAULT SYSDATETIME(),
        updated_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

-- Nạp dữ liệu mẫu ban đầu cho HQ
INSERT INTO Branches (branch_code, branch_name, api_base_url, is_active)
VALUES 
    ('HN', N'Chi nhánh Hà Nội', 'http://branch_hn:8001/api/v1', 1),
    ('HCM', N'Chi nhánh TP.HCM', 'http://branch_hcm:8002/api/v1', 1)
ON CONFLICT (branch_code) DO NOTHING; -- Hoặc cấu trúc MERGE

IF NOT EXISTS (SELECT 1 FROM Branches WHERE branch_code = 'HN')
    INSERT INTO Branches (branch_code, branch_name, api_base_url, is_active) VALUES ('HN', N'Chi nhánh Hà Nội', 'http://branch_hn:8001/api/v1', 1);

IF NOT EXISTS (SELECT 1 FROM Branches WHERE branch_code = 'HCM')
    INSERT INTO Branches (branch_code, branch_name, api_base_url, is_active) VALUES ('HCM', N'Chi nhánh TP.HCM', 'http://branch_hcm:8002/api/v1', 1);

IF NOT EXISTS (SELECT 1 FROM Products WHERE sku = 'LAPTOP-DELL-01')
    INSERT INTO Products (sku, product_name, unit, price) VALUES ('LAPTOP-DELL-01', N'Laptop Dell XPS 15', N'Chiếc', 35000000.0);

IF NOT EXISTS (SELECT 1 FROM Products WHERE sku = 'MACBOOK-AIR-M2')
    INSERT INTO Products (sku, product_name, unit, price) VALUES ('MACBOOK-AIR-M2', N'Apple MacBook Air M2', N'Chiếc', 28000000.0);

IF NOT EXISTS (SELECT 1 FROM Products WHERE sku = 'CHUOT-LOGI-MX3')
    INSERT INTO Products (sku, product_name, unit, price) VALUES ('CHUOT-LOGI-MX3', N'Chuột Logitech MX Master 3S', N'Con', 2200000.0);

-- Snapshot ban đầu
IF NOT EXISTS (SELECT 1 FROM Global_Inventory_Snapshot WHERE branch_code = 'HN' AND sku = 'LAPTOP-DELL-01')
    INSERT INTO Global_Inventory_Snapshot (branch_code, sku, available_qty, reserved_qty) VALUES ('HN', 'LAPTOP-DELL-01', 100, 0);

IF NOT EXISTS (SELECT 1 FROM Global_Inventory_Snapshot WHERE branch_code = 'HCM' AND sku = 'LAPTOP-DELL-01')
    INSERT INTO Global_Inventory_Snapshot (branch_code, sku, available_qty, reserved_qty) VALUES ('HCM', 'LAPTOP-DELL-01', 50, 0);

IF NOT EXISTS (SELECT 1 FROM Global_Inventory_Snapshot WHERE branch_code = 'HN' AND sku = 'MACBOOK-AIR-M2')
    INSERT INTO Global_Inventory_Snapshot (branch_code, sku, available_qty, reserved_qty) VALUES ('HN', 'MACBOOK-AIR-M2', 40, 0);

IF NOT EXISTS (SELECT 1 FROM Global_Inventory_Snapshot WHERE branch_code = 'HCM' AND sku = 'MACBOOK-AIR-M2')
    INSERT INTO Global_Inventory_Snapshot (branch_code, sku, available_qty, reserved_qty) VALUES ('HCM', 'MACBOOK-AIR-M2', 30, 0);
GO


-- ------------------------------------------------------------------------------
-- 2. TẠO CƠ SỞ DỮ LIỆU DB_Branch_HN (Chi nhánh Hà Nội)
-- ------------------------------------------------------------------------------
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'DB_Branch_HN')
BEGIN
    CREATE DATABASE DB_Branch_HN;
END
GO

USE DB_Branch_HN;
GO

IF OBJECT_ID('Local_Products', 'U') IS NULL
BEGIN
    CREATE TABLE Local_Products (
        sku VARCHAR(50) PRIMARY KEY,
        product_name NVARCHAR(200) NOT NULL,
        unit NVARCHAR(50) NOT NULL
    );
END
GO

IF OBJECT_ID('Local_Inventory', 'U') IS NULL
BEGIN
    CREATE TABLE Local_Inventory (
        sku VARCHAR(50) PRIMARY KEY,
        available_qty INT NOT NULL DEFAULT 0 CHECK (available_qty >= 0),
        reserved_qty INT NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
        version INT NOT NULL DEFAULT 1, -- Khóa lạc quan (Optimistic Locking)
        updated_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

IF OBJECT_ID('Stock_Ledger', 'U') IS NULL
BEGIN
    CREATE TABLE Stock_Ledger (
        ledger_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        reference_id VARCHAR(100) NOT NULL UNIQUE, -- Idempotency Key chống trùng lặp
        sku VARCHAR(50) NOT NULL,
        change_type VARCHAR(30) NOT NULL, -- LOCAL_IN | LOCAL_OUT | RESERVE | COMMIT_OUT | RELEASE_RESERVE | TRANSFER_IN
        quantity INT NOT NULL,
        created_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

IF OBJECT_ID('Outbox_Events', 'U') IS NULL
BEGIN
    CREATE TABLE Outbox_Events (
        event_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        routing_key VARCHAR(100) NOT NULL,
        payload NVARCHAR(MAX) NOT NULL,
        is_published BIT DEFAULT 0,
        created_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

-- Seed dữ liệu kho Hà Nội
IF NOT EXISTS (SELECT 1 FROM Local_Products WHERE sku = 'LAPTOP-DELL-01')
    INSERT INTO Local_Products (sku, product_name, unit) VALUES ('LAPTOP-DELL-01', N'Laptop Dell XPS 15', N'Chiếc');
IF NOT EXISTS (SELECT 1 FROM Local_Products WHERE sku = 'MACBOOK-AIR-M2')
    INSERT INTO Local_Products (sku, product_name, unit) VALUES ('MACBOOK-AIR-M2', N'Apple MacBook Air M2', N'Chiếc');
IF NOT EXISTS (SELECT 1 FROM Local_Products WHERE sku = 'CHUOT-LOGI-MX3')
    INSERT INTO Local_Products (sku, product_name, unit) VALUES ('CHUOT-LOGI-MX3', N'Chuột Logitech MX Master 3S', N'Con');

IF NOT EXISTS (SELECT 1 FROM Local_Inventory WHERE sku = 'LAPTOP-DELL-01')
    INSERT INTO Local_Inventory (sku, available_qty, reserved_qty, version) VALUES ('LAPTOP-DELL-01', 100, 0, 1);
IF NOT EXISTS (SELECT 1 FROM Local_Inventory WHERE sku = 'MACBOOK-AIR-M2')
    INSERT INTO Local_Inventory (sku, available_qty, reserved_qty, version) VALUES ('MACBOOK-AIR-M2', 40, 0, 1);
IF NOT EXISTS (SELECT 1 FROM Local_Inventory WHERE sku = 'CHUOT-LOGI-MX3')
    INSERT INTO Local_Inventory (sku, available_qty, reserved_qty, version) VALUES ('CHUOT-LOGI-MX3', 80, 0, 1);
GO


-- ------------------------------------------------------------------------------
-- 3. TẠO CƠ SỞ DỮ LIỆU DB_Branch_HCM (Chi nhánh TP.HCM)
-- ------------------------------------------------------------------------------
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'DB_Branch_HCM')
BEGIN
    CREATE DATABASE DB_Branch_HCM;
END
GO

USE DB_Branch_HCM;
GO

IF OBJECT_ID('Local_Products', 'U') IS NULL
BEGIN
    CREATE TABLE Local_Products (
        sku VARCHAR(50) PRIMARY KEY,
        product_name NVARCHAR(200) NOT NULL,
        unit NVARCHAR(50) NOT NULL
    );
END
GO

IF OBJECT_ID('Local_Inventory', 'U') IS NULL
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

IF OBJECT_ID('Stock_Ledger', 'U') IS NULL
BEGIN
    CREATE TABLE Stock_Ledger (
        ledger_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        reference_id VARCHAR(100) NOT NULL UNIQUE,
        sku VARCHAR(50) NOT NULL,
        change_type VARCHAR(30) NOT NULL,
        quantity INT NOT NULL,
        created_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

IF OBJECT_ID('Outbox_Events', 'U') IS NULL
BEGIN
    CREATE TABLE Outbox_Events (
        event_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        routing_key VARCHAR(100) NOT NULL,
        payload NVARCHAR(MAX) NOT NULL,
        is_published BIT DEFAULT 0,
        created_at DATETIME2 DEFAULT SYSDATETIME()
    );
END
GO

-- Seed dữ liệu kho TP.HCM
IF NOT EXISTS (SELECT 1 FROM Local_Products WHERE sku = 'LAPTOP-DELL-01')
    INSERT INTO Local_Products (sku, product_name, unit) VALUES ('LAPTOP-DELL-01', N'Laptop Dell XPS 15', N'Chiếc');
IF NOT EXISTS (SELECT 1 FROM Local_Products WHERE sku = 'MACBOOK-AIR-M2')
    INSERT INTO Local_Products (sku, product_name, unit) VALUES ('MACBOOK-AIR-M2', N'Apple MacBook Air M2', N'Chiếc');
IF NOT EXISTS (SELECT 1 FROM Local_Products WHERE sku = 'CHUOT-LOGI-MX3')
    INSERT INTO Local_Products (sku, product_name, unit) VALUES ('CHUOT-LOGI-MX3', N'Chuột Logitech MX Master 3S', N'Con');

IF NOT EXISTS (SELECT 1 FROM Local_Inventory WHERE sku = 'LAPTOP-DELL-01')
    INSERT INTO Local_Inventory (sku, available_qty, reserved_qty, version) VALUES ('LAPTOP-DELL-01', 50, 0, 1);
IF NOT EXISTS (SELECT 1 FROM Local_Inventory WHERE sku = 'MACBOOK-AIR-M2')
    INSERT INTO Local_Inventory (sku, available_qty, reserved_qty, version) VALUES ('MACBOOK-AIR-M2', 30, 0, 1);
IF NOT EXISTS (SELECT 1 FROM Local_Inventory WHERE sku = 'CHUOT-LOGI-MX3')
    INSERT INTO Local_Inventory (sku, available_qty, reserved_qty, version) VALUES ('CHUOT-LOGI-MX3', 60, 0, 1);
GO
