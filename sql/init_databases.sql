-- ==============================================================================
-- SQL SERVER INITIALIZATION SCRIPT FOR DISTRIBUTED WAREHOUSE SYSTEM (NHÓM 9)
-- Chuẩn hóa đủ 11 bảng CSDL phân tán trên 3 Site độc lập:
--   Site 1: DB_HQ (Trung tâm - Master Data & Báo cáo TONG_HOP_TON_KHO)
--   Site 2: DB_Branch_HN (Kho miền Bắc - Phân mảnh ngang TON_KHO_HN)
--   Site 3: DB_Branch_HCM (Kho miền Nam - Phân mảnh ngang TON_KHO_HCM)
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. SITE 1: CƠ SỞ DỮ LIỆU DB_HQ (Node Trụ sở chính)
-- ------------------------------------------------------------------------------
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'DB_HQ')
    CREATE DATABASE DB_HQ;
GO

USE DB_HQ;
GO

-- Bảng 1: CHI_NHANH (Branches)
IF OBJECT_ID('Branches', 'U') IS NULL
CREATE TABLE Branches (
    branch_code VARCHAR(20) PRIMARY KEY,
    branch_name NVARCHAR(100) NOT NULL,
    address NVARCHAR(255) NULL,
    site_type VARCHAR(20) NOT NULL DEFAULT 'CHI_NHANH', -- TRUNG_TAM | CHI_NHANH
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',       -- ACTIVE | MAINTENANCE | INACTIVE
    api_base_url VARCHAR(255) NOT NULL,
    is_active BIT DEFAULT 1
);
GO

-- Bảng 2: DANH_MUC_SP (Product_Categories)
IF OBJECT_ID('Product_Categories', 'U') IS NULL
CREATE TABLE Product_Categories (
    category_id INT IDENTITY(1,1) PRIMARY KEY,
    category_name NVARCHAR(100) NOT NULL,
    description NVARCHAR(255) NULL
);
GO

-- Bảng 3: SAN_PHAM (Products)
IF OBJECT_ID('Products', 'U') IS NULL
CREATE TABLE Products (
    sku VARCHAR(50) PRIMARY KEY,
    barcode VARCHAR(100) UNIQUE NULL,
    product_name NVARCHAR(200) NOT NULL,
    category_id INT NULL FOREIGN KEY REFERENCES Product_Categories(category_id),
    unit NVARCHAR(50) NOT NULL,
    cost_price DECIMAL(18,2) DEFAULT 0.0,
    price DECIMAL(18,2) DEFAULT 0.0,
    updated_at DATETIME2 DEFAULT SYSDATETIME()
);
GO

-- Bảng 4: TAI_KHOAN (Accounts)
IF OBJECT_ID('Accounts', 'U') IS NULL
CREATE TABLE Accounts (
    account_id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name NVARCHAR(100) NOT NULL,
    role VARCHAR(30) NOT NULL,
    branch_code VARCHAR(20) NOT NULL,
    is_active BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT SYSDATETIME()
);
GO

-- Bảng 11: TONG_HOP_TON_KHO (Global_Inventory_Snapshot)
IF OBJECT_ID('Global_Inventory_Snapshot', 'U') IS NULL
CREATE TABLE Global_Inventory_Snapshot (
    branch_code VARCHAR(20) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    available_qty INT NOT NULL DEFAULT 0,
    reserved_qty INT NOT NULL DEFAULT 0,
    last_synced_at DATETIME2 DEFAULT SYSDATETIME(),
    PRIMARY KEY (branch_code, sku),
    FOREIGN KEY (branch_code) REFERENCES Branches(branch_code)
);
GO

-- Bảng Điều phối Saga: Transfer_Orders
IF OBJECT_ID('Transfer_Orders', 'U') IS NULL
CREATE TABLE Transfer_Orders (
    transfer_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    source_branch VARCHAR(20) NOT NULL,
    dest_branch VARCHAR(20) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    saga_status VARCHAR(40) NOT NULL,
    error_reason NVARCHAR(500) NULL,
    created_at DATETIME2 DEFAULT SYSDATETIME(),
    updated_at DATETIME2 DEFAULT SYSDATETIME()
);
GO

-- Seed dữ liệu mẫu Site 1 (HQ)
IF NOT EXISTS (SELECT 1 FROM Branches WHERE branch_code = 'HQ')
    INSERT INTO Branches (branch_code, branch_name, address, site_type, status, api_base_url, is_active)
    VALUES ('HQ', N'Trụ sở chính (Trung tâm)', N'Số 1 Đại Cồ Việt, Hà Nội', 'TRUNG_TAM', 'ACTIVE', 'http://hq_service:8000/api/v1', 1);

IF NOT EXISTS (SELECT 1 FROM Branches WHERE branch_code = 'HN')
    INSERT INTO Branches (branch_code, branch_name, address, site_type, status, api_base_url, is_active)
    VALUES ('HN', N'Chi nhánh Hà Nội', N'KCN Bắc Thăng Long, Hà Nội', 'CHI_NHANH', 'ACTIVE', 'http://branch_hn:8001/api/v1', 1);

IF NOT EXISTS (SELECT 1 FROM Branches WHERE branch_code = 'HCM')
    INSERT INTO Branches (branch_code, branch_name, address, site_type, status, api_base_url, is_active)
    VALUES ('HCM', N'Chi nhánh TP.HCM', N'KCN Tân Bình, TP.HCM', 'CHI_NHANH', 'ACTIVE', 'http://branch_hcm:8002/api/v1', 1);

IF NOT EXISTS (SELECT 1 FROM Product_Categories)
    INSERT INTO Product_Categories (category_name, description) VALUES
        (N'Điện tử - Laptop', N'Máy tính xách tay, thiết bị công nghệ'),
        (N'Thiết bị ngoại vi', N'Chuột, bàn phím, màn hình');
GO


-- ------------------------------------------------------------------------------
-- 2. SITE 2: CƠ SỞ DỮ LIỆU DB_Branch_HN (Kho miền Bắc - Hà Nội)
-- ------------------------------------------------------------------------------
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'DB_Branch_HN')
    CREATE DATABASE DB_Branch_HN;
GO

USE DB_Branch_HN;
GO

-- Bản sao Danh mục nhân bản từ Site 1
IF OBJECT_ID('Branches', 'U') IS NULL
CREATE TABLE Branches (
    branch_code VARCHAR(20) PRIMARY KEY,
    branch_name NVARCHAR(100) NOT NULL,
    address NVARCHAR(255) NULL,
    site_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL
);

IF OBJECT_ID('Product_Categories', 'U') IS NULL
CREATE TABLE Product_Categories (
    category_id INT PRIMARY KEY,
    category_name NVARCHAR(100) NOT NULL,
    description NVARCHAR(255) NULL
);

IF OBJECT_ID('Local_Products', 'U') IS NULL
CREATE TABLE Local_Products (
    sku VARCHAR(50) PRIMARY KEY,
    barcode VARCHAR(100) UNIQUE NULL,
    product_name NVARCHAR(200) NOT NULL,
    category_id INT NULL,
    unit NVARCHAR(50) NOT NULL,
    cost_price DECIMAL(18,2) DEFAULT 0.0,
    price DECIMAL(18,2) DEFAULT 0.0,
    updated_at DATETIME2 DEFAULT SYSDATETIME()
);

IF OBJECT_ID('Accounts', 'U') IS NULL
CREATE TABLE Accounts (
    account_id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name NVARCHAR(100) NOT NULL,
    role VARCHAR(30) NOT NULL,
    branch_code VARCHAR(20) NOT NULL,
    is_active BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT SYSDATETIME()
);

-- Bảng 5: TON_KHO (Phân mảnh ngang tại Site 2)
IF OBJECT_ID('Local_Inventory', 'U') IS NULL
CREATE TABLE Local_Inventory (
    sku VARCHAR(50) PRIMARY KEY,
    branch_code VARCHAR(20) NOT NULL DEFAULT 'HN',
    available_qty INT NOT NULL DEFAULT 0 CHECK (available_qty >= 0),
    reserved_qty INT NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
    min_threshold INT NOT NULL DEFAULT 10,
    max_threshold INT NOT NULL DEFAULT 200,
    version INT NOT NULL DEFAULT 1,
    updated_at DATETIME2 DEFAULT SYSDATETIME()
);

-- Bảng 6: GIAO_DICH_KHO
IF OBJECT_ID('Warehouse_Transactions', 'U') IS NULL
CREATE TABLE Warehouse_Transactions (
    transaction_id VARCHAR(64) PRIMARY KEY,
    branch_code VARCHAR(20) NOT NULL,
    receipt_code VARCHAR(50) UNIQUE NOT NULL,
    transaction_type VARCHAR(30) NOT NULL,
    counterpart_branch VARCHAR(20) NULL,
    saga_transfer_id VARCHAR(64) NULL,
    created_by VARCHAR(64) NULL,
    status VARCHAR(30) NOT NULL,
    note NVARCHAR(500) NULL,
    created_at DATETIME2 DEFAULT SYSDATETIME()
);

-- Bảng 7: CHI_TIET_GIAO_DICH
IF OBJECT_ID('Warehouse_Transaction_Details', 'U') IS NULL
CREATE TABLE Warehouse_Transaction_Details (
    detail_id VARCHAR(64) PRIMARY KEY,
    transaction_id VARCHAR(64) NOT NULL FOREIGN KEY REFERENCES Warehouse_Transactions(transaction_id),
    branch_code VARCHAR(20) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    quantity INT NOT NULL,
    post_transaction_balance INT NOT NULL
);

-- Bảng 8: DON_HANG
IF OBJECT_ID('Customer_Orders', 'U') IS NULL
CREATE TABLE Customer_Orders (
    order_id VARCHAR(64) PRIMARY KEY,
    branch_code VARCHAR(20) NOT NULL,
    customer_name NVARCHAR(100) NOT NULL,
    customer_phone VARCHAR(20) NULL,
    total_amount DECIMAL(18,2) NOT NULL DEFAULT 0.0,
    status VARCHAR(30) NOT NULL,
    created_at DATETIME2 DEFAULT SYSDATETIME()
);

-- Bảng 9: CHI_TIET_DON_HANG
IF OBJECT_ID('Customer_Order_Details', 'U') IS NULL
CREATE TABLE Customer_Order_Details (
    id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL FOREIGN KEY REFERENCES Customer_Orders(order_id),
    sku VARCHAR(50) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(18,2) NOT NULL
);

-- Bảng 10: SU_KIEN_DONG_BO (Transactional Outbox)
IF OBJECT_ID('Outbox_Events', 'U') IS NULL
CREATE TABLE Outbox_Events (
    event_id VARCHAR(64) PRIMARY KEY,
    branch_code VARCHAR(20) NOT NULL DEFAULT 'HN',
    event_type VARCHAR(50) NOT NULL DEFAULT 'SYNC_INVENTORY',
    routing_key VARCHAR(100) NOT NULL,
    payload NVARCHAR(MAX) NOT NULL,
    delivery_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    retry_count INT NOT NULL DEFAULT 0,
    is_published BIT DEFAULT 0,
    created_at DATETIME2 DEFAULT SYSDATETIME()
);
GO


-- ------------------------------------------------------------------------------
-- 3. SITE 3: CƠ SỞ DỮ LIỆU DB_Branch_HCM (Kho miền Nam - TP.HCM)
-- (Cấu trúc phân mảnh tương tự Site 2 với branch_code = 'HCM')
-- ------------------------------------------------------------------------------
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'DB_Branch_HCM')
    CREATE DATABASE DB_Branch_HCM;
GO

USE DB_Branch_HCM;
GO

IF OBJECT_ID('Local_Inventory', 'U') IS NULL
CREATE TABLE Local_Inventory (
    sku VARCHAR(50) PRIMARY KEY,
    branch_code VARCHAR(20) NOT NULL DEFAULT 'HCM',
    available_qty INT NOT NULL DEFAULT 0 CHECK (available_qty >= 0),
    reserved_qty INT NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
    min_threshold INT NOT NULL DEFAULT 10,
    max_threshold INT NOT NULL DEFAULT 200,
    version INT NOT NULL DEFAULT 1,
    updated_at DATETIME2 DEFAULT SYSDATETIME()
);
GO
