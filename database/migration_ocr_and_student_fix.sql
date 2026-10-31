-- database/migration_ocr_and_student_fix.sql
-- Migration bo sung bang luu tru ket qua OCR va kiem tra lech ID student/user

-- 1. Tao bang luu tru ket qua OCR bang diem theo sinh vien va phien chat
IF OBJECT_ID('student_ocr_transcripts', 'U') IS NULL
BEGIN
    CREATE TABLE student_ocr_transcripts (
        id INT IDENTITY(1,1),
        user_id INT NOT NULL,
        student_id INT NULL,
        session_id INT NULL,
        filename NVARCHAR(255) NOT NULL,
        total_subjects INT DEFAULT 0,
        passed_count INT DEFAULT 0,
        failed_count INT DEFAULT 0,
        courses_data NVARCHAR(MAX) NOT NULL,
        summary_text NVARCHAR(MAX) NULL,
        created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_student_ocr_transcripts PRIMARY KEY (id),
        CONSTRAINT FK_ocr_transcripts_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT FK_ocr_transcripts_students FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE NO ACTION,
        CONSTRAINT FK_ocr_transcripts_sessions FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE NO ACTION
    );

    CREATE INDEX IX_student_ocr_transcripts_user_id ON student_ocr_transcripts(user_id);
    CREATE INDEX IX_student_ocr_transcripts_session_id ON student_ocr_transcripts(session_id);
END
GO

-- 2. Kiem tra va dong bo an toan: Dam bao toan bo bang grades lien ket dung voi students.id
-- Neu co ban ghi grades nao ma student_id bi gan nham bang users.id thay vi students.id, chuyen ve students.id
UPDATE g
SET g.student_id = s.id
FROM grades g
JOIN users u ON g.student_id = u.id
JOIN students s ON s.user_id = u.id
WHERE g.student_id NOT IN (SELECT id FROM students);
GO
