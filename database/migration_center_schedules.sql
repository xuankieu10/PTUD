-- ============================================================================
-- Migration: Bảng lịch học (center_schedules) và lịch thi (center_exams)
--            cho Trung tâm Ngoại ngữ - Tin học (NNTH) Trường ĐH Lạc Hồng
-- Tương thích Microsoft SQL Server (T-SQL)
-- ============================================================================

USE [HocVuAI];
GO

-- 1. Bảng lịch học / khai giảng (center_schedules)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'center_schedules')
BEGIN
    CREATE TABLE center_schedules (
        id INT IDENTITY(1,1) PRIMARY KEY,
        lop_id INT NOT NULL CONSTRAINT UQ_center_schedules_lop_id UNIQUE,
        ten_khoa_hoc NVARCHAR(255) NOT NULL,
        ten_lop NVARCHAR(255) NULL,
        loai NVARCHAR(50) NOT NULL, -- N'Ngoại ngữ' hoặc N'Tin học'
        ngay_khai_giang DATE NULL,
        ngay_khai_giang_str NVARCHAR(50) NULL,
        ngay_ket_thuc DATE NULL,
        ngay_ket_thuc_str NVARCHAR(50) NULL,
        lich_hoc NVARCHAR(255) NULL,
        hinh_thuc NVARCHAR(100) NULL, -- 'Zoom', 'CS1', Online/Offline
        hoc_phi NVARCHAR(50) NULL,
        ky_thi_du_kien NVARCHAR(255) NULL,
        link_dang_ky NVARCHAR(255) NULL,
        so_luong NVARCHAR(50) NULL,
        phong NVARCHAR(100) NULL,
        mo_ta NVARCHAR(MAX) NULL,
        ngay_lay_du_lieu DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );

    CREATE INDEX IX_center_schedules_ngay_kg ON center_schedules(ngay_khai_giang);
    CREATE INDEX IX_center_schedules_loai ON center_schedules(loai);
    PRINT 'Đã tạo bảng center_schedules thành công.';
END
ELSE
BEGIN
    PRINT 'Bảng center_schedules đã tồn tại.';
END
GO

-- 2. Bảng lịch thi (center_exams)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'center_exams')
BEGIN
    CREATE TABLE center_exams (
        id INT IDENTITY(1,1) PRIMARY KEY,
        ky_thi_id INT NOT NULL,
        is_du_kien BIT NOT NULL DEFAULT 0, -- 0: chính thức, 1: dự kiến
        ten_ky_thi NVARCHAR(255) NOT NULL,
        loai NVARCHAR(50) NOT NULL, -- N'Ngoại ngữ' hoặc N'Tin học'
        ngay_thi DATE NULL,
        ngay_thi_str NVARCHAR(50) NULL,
        han_dang_ky NVARCHAR(255) NULL,
        hoan_thi NVARCHAR(255) NULL,
        tinh_trang NVARCHAR(100) NULL, -- 'Còn nhận đăng ký.', 'Chưa nhận đăng ký.'
        tinh_trang_code INT NULL,
        le_phi_thi NVARCHAR(50) NULL,
        le_phi_chung_chi NVARCHAR(50) NULL,
        le_phi_tong NVARCHAR(50) NULL,
        thang INT NULL,
        nam INT NULL,
        ghi_chu NVARCHAR(MAX) NULL,
        ngay_lay_du_lieu DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        CONSTRAINT UQ_center_exams_ky_thi UNIQUE (ky_thi_id, is_du_kien)
    );

    CREATE INDEX IX_center_exams_ngay_thi ON center_exams(ngay_thi);
    CREATE INDEX IX_center_exams_loai ON center_exams(loai);
    CREATE INDEX IX_center_exams_is_du_kien ON center_exams(is_du_kien);
    PRINT 'Đã tạo bảng center_exams thành công.';
END
ELSE
BEGIN
    PRINT 'Bảng center_exams đã tồn tại.';
END
GO

-- 3. Bảng lịch sử đồng bộ (center_sync_history)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'center_sync_history')
BEGIN
    CREATE TABLE center_sync_history (
        id INT IDENTITY(1,1) PRIMARY KEY,
        sync_type NVARCHAR(50) NOT NULL DEFAULT 'NNTH',
        status NVARCHAR(50) NOT NULL, -- 'SUCCESS', 'ERROR'
        schedules_count INT NOT NULL DEFAULT 0,
        exams_count INT NOT NULL DEFAULT 0,
        error_message NVARCHAR(MAX) NULL,
        synced_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );

    CREATE INDEX IX_center_sync_history_synced_at ON center_sync_history(synced_at DESC);
    PRINT 'Đã tạo bảng center_sync_history thành công.';
END
ELSE
BEGIN
    PRINT 'Bảng center_sync_history đã tồn tại.';
END
GO
