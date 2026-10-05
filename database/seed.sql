-- database/seed.sql
USE HocVuAI;
GO

-- 1. users
-- Admin (Ghi chú: password_hash dưới đây chỉ là dữ liệu giả lập cho bcrypt hash)
IF NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
BEGIN
    INSERT INTO users (username, password_hash, role)
    VALUES ('admin', '$2b$12$dummyBcryptHashForAdmin......................', 'admin');
END

-- Students
IF NOT EXISTS (SELECT 1 FROM users WHERE username = 'sv01')
BEGIN
    INSERT INTO users (username, password_hash, role)
    VALUES ('sv01', '$2b$12$dummyBcryptHashForSv01.......................', 'student');
END

IF NOT EXISTS (SELECT 1 FROM users WHERE username = 'sv02')
BEGIN
    INSERT INTO users (username, password_hash, role)
    VALUES ('sv02', '$2b$12$dummyBcryptHashForSv02.......................', 'student');
END

IF NOT EXISTS (SELECT 1 FROM users WHERE username = 'sv03')
BEGIN
    INSERT INTO users (username, password_hash, role)
    VALUES ('sv03', '$2b$12$dummyBcryptHashForSv03.......................', 'student');
END
GO

-- 2. students
DECLARE @uid1 INT = (SELECT id FROM users WHERE username = 'sv01');
DECLARE @uid2 INT = (SELECT id FROM users WHERE username = 'sv02');
DECLARE @uid3 INT = (SELECT id FROM users WHERE username = 'sv03');

IF NOT EXISTS (SELECT 1 FROM students WHERE student_code = '20210001')
BEGIN
    INSERT INTO students (user_id, student_code, full_name, major, cohort)
    VALUES (@uid1, '20210001', N'Nguyễn Văn A', N'Công nghệ thông tin', 'K66');
END

IF NOT EXISTS (SELECT 1 FROM students WHERE student_code = '20210002')
BEGIN
    INSERT INTO students (user_id, student_code, full_name, major, cohort)
    VALUES (@uid2, '20210002', N'Trần Thị B', N'Công nghệ thông tin', 'K66');
END

IF NOT EXISTS (SELECT 1 FROM students WHERE student_code = '20210003')
BEGIN
    INSERT INTO students (user_id, student_code, full_name, major, cohort)
    VALUES (@uid3, '20210003', N'Lê Văn C', N'Công nghệ thông tin', 'K66');
END
GO

-- 3. courses
-- 12 courses
IF NOT EXISTS (SELECT 1 FROM courses WHERE code = 'IT1110')
    INSERT INTO courses (code, name, credits) VALUES ('IT1110', N'Tin học đại cương', 4);
IF NOT EXISTS (SELECT 1 FROM courses WHERE code = 'IT2030')
    INSERT INTO courses (code, name, credits) VALUES ('IT2030', N'Cấu trúc dữ liệu và giải thuật', 3);
IF NOT EXISTS (SELECT 1 FROM courses WHERE code = 'IT3040')
    INSERT INTO courses (code, name, credits) VALUES ('IT3040', N'Cơ sở dữ liệu', 3);
IF NOT EXISTS (SELECT 1 FROM courses WHERE code = 'IT3080')
    INSERT INTO courses (code, name, credits) VALUES ('IT3080', N'Mạng máy tính', 3);
IF NOT EXISTS (SELECT 1 FROM courses WHERE code = 'IT3100')
    INSERT INTO courses (code, name, credits) VALUES ('IT3100', N'Lập trình hướng đối tượng', 3);
IF NOT EXISTS (SELECT 1 FROM courses WHERE code = 'IT3120')
    INSERT INTO courses (code, name, credits) VALUES ('IT3120', N'Phân tích và thiết kế hệ thống', 3);
IF NOT EXISTS (SELECT 1 FROM courses WHERE code = 'IT4015')
    INSERT INTO courses (code, name, credits) VALUES ('IT4015', N'Nhập môn Trí tuệ nhân tạo', 3);
IF NOT EXISTS (SELECT 1 FROM courses WHERE code = 'IT4040')
    INSERT INTO courses (code, name, credits) VALUES ('IT4040', N'Kỹ thuật phần mềm', 3);
IF NOT EXISTS (SELECT 1 FROM courses WHERE code = 'IT4060')
    INSERT INTO courses (code, name, credits) VALUES ('IT4060', N'An toàn thông tin', 3);
IF NOT EXISTS (SELECT 1 FROM courses WHERE code = 'MI1111')
    INSERT INTO courses (code, name, credits) VALUES ('MI1111', N'Giải tích 1', 4);
IF NOT EXISTS (SELECT 1 FROM courses WHERE code = 'MI1121')
    INSERT INTO courses (code, name, credits) VALUES ('MI1121', N'Giải tích 2', 4);
IF NOT EXISTS (SELECT 1 FROM courses WHERE code = 'MI2020')
    INSERT INTO courses (code, name, credits) VALUES ('MI2020', N'Xác suất thống kê', 3);
GO

-- 4. program_courses
DECLARE @major NVARCHAR(255) = N'Công nghệ thông tin';
-- Link all 12 courses to major IT.
-- Assuming all are required except the last two
INSERT INTO program_courses (major, course_id, is_required)
SELECT @major, id, 
       CASE WHEN code IN ('IT4040', 'IT4060') THEN 0 ELSE 1 END
FROM courses
WHERE NOT EXISTS (
    SELECT 1 FROM program_courses pc WHERE pc.major = @major AND pc.course_id = courses.id
);
GO

-- 5. grades
DECLARE @sid1 INT = (SELECT id FROM students WHERE student_code = '20210001');
DECLARE @sid2 INT = (SELECT id FROM students WHERE student_code = '20210002');
DECLARE @sid3 INT = (SELECT id FROM students WHERE student_code = '20210003');

DECLARE @cid_it1110 INT = (SELECT id FROM courses WHERE code = 'IT1110');
DECLARE @cid_it2030 INT = (SELECT id FROM courses WHERE code = 'IT2030');
DECLARE @cid_it3040 INT = (SELECT id FROM courses WHERE code = 'IT3040');
DECLARE @cid_it3080 INT = (SELECT id FROM courses WHERE code = 'IT3080');
DECLARE @cid_mi1111 INT = (SELECT id FROM courses WHERE code = 'MI1111');
DECLARE @cid_mi2020 INT = (SELECT id FROM courses WHERE code = 'MI2020');
DECLARE @cid_it3100 INT = (SELECT id FROM courses WHERE code = 'IT3100');

-- Grades for sid1 (6 courses)
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid1 AND course_id = @cid_it1110 AND semester = '20211')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid1, @cid_it1110, 8.5, '20211', 1, 'manual');
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid1 AND course_id = @cid_mi1111 AND semester = '20211')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid1, @cid_mi1111, 7.0, '20211', 1, 'manual');
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid1 AND course_id = @cid_it2030 AND semester = '20212')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid1, @cid_it2030, 3.5, '20212', 0, 'ocr'); -- Failed
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid1 AND course_id = @cid_mi2020 AND semester = '20212')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid1, @cid_mi2020, 6.0, '20212', 1, 'manual');
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid1 AND course_id = @cid_it3040 AND semester = '20221')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid1, @cid_it3040, 9.0, '20221', 1, 'manual');
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid1 AND course_id = @cid_it3080 AND semester = '20221')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid1, @cid_it3080, 8.0, '20221', 1, 'manual');

-- Grades for sid2 (7 courses)
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid2 AND course_id = @cid_it1110 AND semester = '20211')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid2, @cid_it1110, 9.5, '20211', 1, 'ocr');
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid2 AND course_id = @cid_mi1111 AND semester = '20211')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid2, @cid_mi1111, 2.0, '20211', 0, 'ocr'); -- Failed
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid2 AND course_id = @cid_mi1111 AND semester = '20212')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid2, @cid_mi1111, 5.5, '20212', 1, 'ocr'); -- Retake and pass
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid2 AND course_id = @cid_it2030 AND semester = '20212')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid2, @cid_it2030, 8.0, '20212', 1, 'ocr');
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid2 AND course_id = @cid_mi2020 AND semester = '20212')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid2, @cid_mi2020, 7.5, '20212', 1, 'ocr');
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid2 AND course_id = @cid_it3040 AND semester = '20221')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid2, @cid_it3040, 8.5, '20221', 1, 'ocr');
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid2 AND course_id = @cid_it3080 AND semester = '20221')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid2, @cid_it3080, 9.0, '20221', 1, 'ocr');

-- Grades for sid3 (6 courses)
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid3 AND course_id = @cid_it1110 AND semester = '20211')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid3, @cid_it1110, 6.0, '20211', 1, 'manual');
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid3 AND course_id = @cid_mi1111 AND semester = '20211')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid3, @cid_mi1111, 6.5, '20211', 1, 'manual');
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid3 AND course_id = @cid_it2030 AND semester = '20212')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid3, @cid_it2030, 5.0, '20212', 1, 'manual');
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid3 AND course_id = @cid_mi2020 AND semester = '20212')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid3, @cid_mi2020, 2.5, '20212', 0, 'manual'); -- Failed
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid3 AND course_id = @cid_it3040 AND semester = '20221')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid3, @cid_it3040, 7.0, '20221', 1, 'manual');
IF NOT EXISTS (SELECT 1 FROM grades WHERE student_id = @sid3 AND course_id = @cid_it3100 AND semester = '20221')
    INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (@sid3, @cid_it3100, 8.0, '20221', 1, 'manual');
GO

-- 6. documents
DECLARE @adminId INT = (SELECT id FROM users WHERE username = 'admin');

IF NOT EXISTS (SELECT 1 FROM documents WHERE title = N'Quy chế đào tạo')
BEGIN
    INSERT INTO documents (title, source, status, uploaded_by)
    VALUES (N'Quy chế đào tạo', N'Manual Upload', 'pending', @adminId);
END

IF NOT EXISTS (SELECT 1 FROM documents WHERE title = N'Điều kiện xét tốt nghiệp')
BEGIN
    INSERT INTO documents (title, source, status, uploaded_by)
    VALUES (N'Điều kiện xét tốt nghiệp', N'Manual Upload', 'pending', @adminId);
END
GO
