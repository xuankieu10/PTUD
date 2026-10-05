-- database/schema.sql
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'HocVuAI')
BEGIN
    CREATE DATABASE HocVuAI;
END
GO

USE HocVuAI;
GO

-- 1. users
IF OBJECT_ID('users', 'U') IS NULL
BEGIN
    CREATE TABLE users (
        id INT IDENTITY(1,1),
        username NVARCHAR(255) NOT NULL,
        password_hash NVARCHAR(255) NOT NULL,
        role NVARCHAR(50) NOT NULL,
        created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_users PRIMARY KEY (id),
        CONSTRAINT UQ_users_username UNIQUE (username),
        CONSTRAINT CK_users_role CHECK (role IN ('student', 'admin'))
    );
END
GO

-- 2. students
IF OBJECT_ID('students', 'U') IS NULL
BEGIN
    CREATE TABLE students (
        id INT IDENTITY(1,1),
        user_id INT NOT NULL,
        student_code NVARCHAR(50) NOT NULL,
        full_name NVARCHAR(255) NOT NULL,
        major NVARCHAR(255) NOT NULL,
        cohort NVARCHAR(50) NOT NULL,
        CONSTRAINT PK_students PRIMARY KEY (id),
        CONSTRAINT UQ_students_user_id UNIQUE (user_id),
        CONSTRAINT UQ_students_student_code UNIQUE (student_code),
        CONSTRAINT FK_students_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
END
GO

-- 3. courses
IF OBJECT_ID('courses', 'U') IS NULL
BEGIN
    CREATE TABLE courses (
        id INT IDENTITY(1,1),
        code NVARCHAR(50) NOT NULL,
        name NVARCHAR(255) NOT NULL,
        credits INT NOT NULL,
        CONSTRAINT PK_courses PRIMARY KEY (id),
        CONSTRAINT UQ_courses_code UNIQUE (code),
        CONSTRAINT CK_courses_credits CHECK (credits > 0)
    );
END
GO

-- 4. program_courses
IF OBJECT_ID('program_courses', 'U') IS NULL
BEGIN
    CREATE TABLE program_courses (
        id INT IDENTITY(1,1),
        major NVARCHAR(255) NOT NULL,
        course_id INT NOT NULL,
        is_required BIT NOT NULL,
        CONSTRAINT PK_program_courses PRIMARY KEY (id),
        CONSTRAINT UQ_program_courses_major_course UNIQUE (major, course_id),
        CONSTRAINT FK_program_courses_courses FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
END
GO

-- 5. grades
IF OBJECT_ID('grades', 'U') IS NULL
BEGIN
    CREATE TABLE grades (
        id INT IDENTITY(1,1),
        student_id INT NOT NULL,
        course_id INT NOT NULL,
        score DECIMAL(4,2) NOT NULL,
        semester NVARCHAR(50) NOT NULL,
        passed BIT NOT NULL,
        source NVARCHAR(50) NOT NULL,
        CONSTRAINT PK_grades PRIMARY KEY (id),
        CONSTRAINT UQ_grades_student_course_semester UNIQUE (student_id, course_id, semester),
        CONSTRAINT FK_grades_students FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        CONSTRAINT FK_grades_courses FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE NO ACTION,
        CONSTRAINT CK_grades_score CHECK (score >= 0 AND score <= 10),
        CONSTRAINT CK_grades_source CHECK (source IN ('manual', 'ocr'))
    );
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_grades_student_id' AND object_id = OBJECT_ID('grades'))
BEGIN
    CREATE INDEX IX_grades_student_id ON grades(student_id);
END
GO

-- 6. documents
IF OBJECT_ID('documents', 'U') IS NULL
BEGIN
    CREATE TABLE documents (
        id INT IDENTITY(1,1),
        title NVARCHAR(255) NOT NULL,
        source NVARCHAR(255),
        status NVARCHAR(50) NOT NULL,
        uploaded_by INT,
        created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_documents PRIMARY KEY (id),
        CONSTRAINT CK_documents_status CHECK (status IN ('pending', 'indexed', 'failed')),
        CONSTRAINT FK_documents_users FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
    );
END
GO

-- 7. document_chunks
IF OBJECT_ID('document_chunks', 'U') IS NULL
BEGIN
    CREATE TABLE document_chunks (
        id INT IDENTITY(1,1),
        document_id INT NOT NULL,
        chunk_index INT NOT NULL,
        content NVARCHAR(MAX) NOT NULL,
        embedding VARBINARY(MAX) NOT NULL,
        CONSTRAINT PK_document_chunks PRIMARY KEY (id),
        CONSTRAINT UQ_document_chunks_doc_index UNIQUE (document_id, chunk_index),
        CONSTRAINT FK_document_chunks_documents FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
    );
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_document_chunks_document_id' AND object_id = OBJECT_ID('document_chunks'))
BEGIN
    CREATE INDEX IX_document_chunks_document_id ON document_chunks(document_id);
END
GO

-- 8. chat_sessions
IF OBJECT_ID('chat_sessions', 'U') IS NULL
BEGIN
    CREATE TABLE chat_sessions (
        id INT IDENTITY(1,1),
        user_id INT NOT NULL,
        title NVARCHAR(255) NOT NULL,
        created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_chat_sessions PRIMARY KEY (id),
        CONSTRAINT FK_chat_sessions_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_chat_sessions_user_id' AND object_id = OBJECT_ID('chat_sessions'))
BEGIN
    CREATE INDEX IX_chat_sessions_user_id ON chat_sessions(user_id);
END
GO

-- 9. chat_messages
IF OBJECT_ID('chat_messages', 'U') IS NULL
BEGIN
    CREATE TABLE chat_messages (
        id INT IDENTITY(1,1),
        session_id INT NOT NULL,
        role NVARCHAR(50) NOT NULL,
        content NVARCHAR(MAX) NOT NULL,
        sources NVARCHAR(MAX),
        created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_chat_messages PRIMARY KEY (id),
        CONSTRAINT FK_chat_messages_sessions FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
        CONSTRAINT CK_chat_messages_role CHECK (role IN ('user', 'assistant')),
        CONSTRAINT CK_chat_messages_sources CHECK (sources IS NULL OR ISJSON(sources) = 1)
    );
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_chat_messages_session_id' AND object_id = OBJECT_ID('chat_messages'))
BEGIN
    CREATE INDEX IX_chat_messages_session_id ON chat_messages(session_id);
END
GO

-- Verify tables
SELECT TABLE_NAME 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_TYPE = 'BASE TABLE';
GO
