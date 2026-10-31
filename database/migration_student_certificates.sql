-- database/migration_student_certificates.sql
-- Migration tạo bảng student_certificates (idempotent, IF NOT EXISTS)

IF OBJECT_ID('student_certificates', 'U') IS NULL
BEGIN
    CREATE TABLE student_certificates (
        id INT IDENTITY(1,1),
        student_id INT NOT NULL,
        certificate_type NVARCHAR(100) NOT NULL,
        certificate_name NVARCHAR(255) NULL,
        issued_date NVARCHAR(50) NULL,
        status NVARCHAR(50) DEFAULT 'valid',
        created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_student_certificates PRIMARY KEY (id),
        CONSTRAINT FK_student_certificates_students FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    );
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_student_certificates_student_id' AND object_id = OBJECT_ID('student_certificates'))
BEGIN
    CREATE INDEX IX_student_certificates_student_id ON student_certificates(student_id);
END
GO

