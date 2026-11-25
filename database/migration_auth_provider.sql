-- database/migration_auth_provider.sql
-- Migration idempotent bổ sung cột auth_provider cho bảng users
-- Mặc định 'local' cho các dòng dữ liệu cũ/tài khoản nội bộ

IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'auth_provider'
)
BEGIN
    ALTER TABLE users 
    ADD auth_provider NVARCHAR(50) NULL CONSTRAINT DF_users_auth_provider DEFAULT 'local';
    
    EXEC('UPDATE users SET auth_provider = ''local'' WHERE auth_provider IS NULL;');
    PRINT 'Da them cot auth_provider vao bang users thanh cong.';
END
ELSE
BEGIN
    PRINT 'Cot auth_provider da ton tai trong bang users.';
END
GO
