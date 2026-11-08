-- ============================================================================
-- 01_create_databases.sql
-- Kịch bản khởi tạo 3 Cơ sở dữ liệu vật lý riêng biệt cho kiến trúc phân tán:
-- 1. DB_HQ: CSDL tại Trụ sở chính (Port 1433)
-- 2. DB_Branch_HN: CSDL tại Chi nhánh Hà Nội (Port 1434)
-- 3. DB_Branch_HCM: CSDL tại Chi nhánh TP.HCM (Port 1435)
-- ============================================================================

-- 1. Tạo Database cho Trụ sở chính (HQ Node)
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'DB_HQ')
BEGIN
    CREATE DATABASE DB_HQ COLLATE Latin1_General_100_CI_AS_SC_UTF8;
    PRINT 'Đã tạo CSDL DB_HQ thành công.';
END
GO

-- 2. Tạo Database cho Chi nhánh Hà Nội (Branch HN)
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'DB_Branch_HN')
BEGIN
    CREATE DATABASE DB_Branch_HN COLLATE Latin1_General_100_CI_AS_SC_UTF8;
    PRINT 'Đã tạo CSDL DB_Branch_HN thành công.';
END
GO

-- 3. Tạo Database cho Chi nhánh TP.HCM (Branch HCM)
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'DB_Branch_HCM')
BEGIN
    CREATE DATABASE DB_Branch_HCM COLLATE Latin1_General_100_CI_AS_SC_UTF8;
    PRINT 'Đã tạo CSDL DB_Branch_HCM thành công.';
END
GO
