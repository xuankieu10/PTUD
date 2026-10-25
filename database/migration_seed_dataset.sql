-- database/migration_seed_dataset.sql
-- Migration bổ sung bảng điều kiện tốt nghiệp và các cột cho program_courses, documents
USE HocVuAI;
GO

-- 1. Bảng điều kiện tốt nghiệp: graduation_conditions
IF OBJECT_ID('graduation_conditions', 'U') IS NULL
BEGIN
    CREATE TABLE graduation_conditions (
        id INT IDENTITY(1,1),
        ma NVARCHAR(50) NOT NULL,
        nhom NVARCHAR(100) NOT NULL,
        dieu_kien NVARCHAR(255) NOT NULL,
        mo_ta NVARCHAR(MAX) NULL,
        ap_dung_chinh_quy NVARCHAR(50) NULL,
        ap_dung_lien_thong_hoan_chinh NVARCHAR(50) NULL,
        muc_tren_trang NVARCHAR(100) NULL,
        created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_graduation_conditions PRIMARY KEY (id),
        CONSTRAINT UQ_graduation_conditions_ma UNIQUE (ma)
    );
END
GO

-- Tạo View dieu_kien_tot_nghiep tương thích tên tiếng Việt
IF OBJECT_ID('dieu_kien_tot_nghiep', 'V') IS NULL AND OBJECT_ID('dieu_kien_tot_nghiep', 'U') IS NULL
BEGIN
    EXEC('CREATE VIEW dieu_kien_tot_nghiep AS SELECT id, ma, nhom, dieu_kien, mo_ta, ap_dung_chinh_quy, ap_dung_lien_thong_hoan_chinh, muc_tren_trang, created_at FROM graduation_conditions');
END
GO

-- 2. Bổ sung các cột cho program_courses
IF COL_LENGTH('program_courses', 'hoc_ky') IS NULL
BEGIN
    ALTER TABLE program_courses ADD hoc_ky INT NULL;
END
GO

IF COL_LENGTH('program_courses', 'loai') IS NULL
BEGIN
    ALTER TABLE program_courses ADD loai NVARCHAR(100) NULL;
END
GO

IF COL_LENGTH('program_courses', 'nhom_tu_chon') IS NULL
BEGIN
    ALTER TABLE program_courses ADD nhom_tu_chon NVARCHAR(100) NULL;
END
GO

IF COL_LENGTH('program_courses', 'nhan_tren_trang') IS NULL
BEGIN
    ALTER TABLE program_courses ADD nhan_tren_trang NVARCHAR(255) NULL;
END
GO

IF COL_LENGTH('program_courses', 'ghi_chu') IS NULL
BEGIN
    ALTER TABLE program_courses ADD ghi_chu NVARCHAR(MAX) NULL;
END
GO

IF COL_LENGTH('program_courses', 'ten_mon') IS NULL
BEGIN
    ALTER TABLE program_courses ADD ten_mon NVARCHAR(255) NULL;
END
GO

IF COL_LENGTH('program_courses', 'tin_chi') IS NULL
BEGIN
    ALTER TABLE program_courses ADD tin_chi INT NULL;
END
GO

-- Cho phép course_id trong program_courses nhận NULL khi môn học chưa có mã học phần trong bảng courses
IF EXISTS (
    SELECT 1 FROM sys.columns 
    WHERE object_id = OBJECT_ID('program_courses') 
      AND name = 'course_id' 
      AND is_nullable = 0
)
BEGIN
    IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_program_courses_major_course')
    BEGIN
        ALTER TABLE program_courses DROP CONSTRAINT UQ_program_courses_major_course;
    END

    ALTER TABLE program_courses ALTER COLUMN course_id INT NULL;

    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_program_courses_major_course' AND object_id = OBJECT_ID('program_courses'))
    BEGIN
        CREATE UNIQUE INDEX UQ_program_courses_major_course 
        ON program_courses(major, course_id) 
        WHERE course_id IS NOT NULL;
    END
END
GO

-- Index phục vụ kiểm tra trùng lặp môn theo major + ten_mon
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_program_courses_major_ten_mon' AND object_id = OBJECT_ID('program_courses'))
BEGIN
    CREATE INDEX IX_program_courses_major_ten_mon 
    ON program_courses(major, ten_mon);
END
GO

-- 3. Bổ sung các cột lưu nguồn văn bản trong documents: so_hieu, url, ngay_thu_thap
IF COL_LENGTH('documents', 'so_hieu') IS NULL
BEGIN
    ALTER TABLE documents ADD so_hieu NVARCHAR(100) NULL;
END
GO

IF COL_LENGTH('documents', 'url') IS NULL
BEGIN
    ALTER TABLE documents ADD url NVARCHAR(500) NULL;
END
GO

IF COL_LENGTH('documents', 'ngay_thu_thap') IS NULL
BEGIN
    ALTER TABLE documents ADD ngay_thu_thap NVARCHAR(50) NULL;
END
GO

-- Đồng bộ giá trị url từ source_url nếu có
IF COL_LENGTH('documents', 'source_url') IS NOT NULL
BEGIN
    UPDATE documents SET url = source_url WHERE url IS NULL AND source_url IS NOT NULL;
END
GO

-- 4. Bổ sung metadata cho document_chunks nếu chưa có
IF COL_LENGTH('document_chunks', 'section') IS NULL
BEGIN
    ALTER TABLE document_chunks ADD section NVARCHAR(100) NULL;
END
GO

IF COL_LENGTH('document_chunks', 'metadata') IS NULL
BEGIN
    ALTER TABLE document_chunks ADD metadata NVARCHAR(MAX) NULL;
END
GO

PRINT N'Migration completed successfully!';
GO
