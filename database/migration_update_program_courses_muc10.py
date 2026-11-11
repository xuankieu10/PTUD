"""
database/migration_update_program_courses_muc10.py
Migration cập nhật danh mục môn học (bảng courses) và liên kết với CTĐT CNTT (bảng program_courses)
theo Niên giám 2023 và Mục 7.1 của file Tổng hợp quy chế đào tạo học vụ LHU:
1. Thêm 49 môn học còn thiếu vào bảng courses với mã môn thực tế 6 chữ số (idempotent, chỉ INSERT nếu chưa có).
   - Chọn Phương án A cho 3 môn băn khoăn:
     + 111043: Phân tích thiết kế HT hướng đối tượng (3 TC)
     + 111089: Phân tích thiết kế HT hướng quan hệ (3 TC)
     + 111088: Trí tuệ nhân tạo (3 TC)
     + 111065: Kiểm thử và đảm bảo chất lượng phần mềm (3 TC)
     (Giữ nguyên các môn cũ IT3120, IT4015, IT4040 trong bảng courses, không sửa id cũ).
   - Giữ course_id = NULL cho 4 môn điều kiện: GDQP (id 13), GDTC 1 (id 14), GDTC 2 (id 22), GDTC 3 (id 28).
2. Cập nhật course_id tương ứng trong program_courses.
3. Thực hiện toàn bộ trong TRANSACTION và CHỈ COMMIT khi:
   a) Đúng 0 dòng course_id là NULL ngoài 4 môn điều kiện (GDQP, GDTC 1, 2, 3).
   b) Tổng tín chỉ trong program_courses cho CTĐT = 150.
   c) Graduation-check / credit progress cho student_id = 1 trước và sau không đổi / hợp lệ.
   Nếu bất kỳ kiểm tra nào thất bại -> ROLLBACK và dừng.
"""

import sys
import os
import pyodbc
from dotenv import load_dotenv

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 49 môn cần ánh xạ vào program_courses: (pc_id, code, name, credits_for_course_table)
COURSES_TO_MAP = [
    # HK1
    (15, "102073", "Toán cao cấp 1", 4),
    (16, "102074", "English 1", 3),
    (17, "111094", "Nhập môn lập trình", 2),
    (18, "111001", "Cấu trúc và lắp ráp máy tính", 3),
    (19, "111080", "Phần mềm mã nguồn mở", 2),
    (20, "111055", "Nhập môn Công nghệ thông tin", 1),
    (21, "111053", "Nhập môn Phát triển dự án kỹ thuật", 2),
    # HK2
    (23, "102075", "English 2", 4),
    (24, "111046", "Vật lý thực hành", 3),
    (25, "111047", "Điện tử cơ bản", 2),
    (26, "111056", "Thiết kế UI/UX", 2),
    (27, "111058", "Kỹ thuật lập trình", 2),
    # HK3
    (29, "102063", "Triết học Mác - Lênin", 3),
    (30, "102064", "Kinh tế chính trị Mác - Lênin", 2),
    (31, "102065", "Chủ nghĩa xã hội khoa học", 2),
    (32, "102076", "English 3", 4),
    (33, "111010", "Toán rời rạc", 3),
    (34, "111048", "Tín hiệu số cơ bản", 2),
    (35, "112064", "Mạng máy tính nâng cao", 3),
    # HK4
    (36, "102033", "Tư tưởng Hồ Chí Minh", 2),
    (37, "102006", "Pháp luật đại cương", 2),
    (38, "102077", "English 4", 4),
    (39, "111036", "Dịch vụ mạng", 3),
    (40, "111060", "Hệ quản trị CSDL", 3),
    (41, "111067", "Lập trình Front-End", 2),
    (42, "111081", "Kiến tập", 2),
    # HK5
    (43, "102066", "Lịch sử Đảng Cộng sản Việt Nam", 2),
    (44, "102078", "English 5", 4),
    (45, "111057", "Nguyên lý thống kê", 2),
    (46, "112065", "Thiết kế hệ thống mạng", 3),
    (47, "111066", "Lập trình Back-End", 3),
    (48, "111072", "Lập trình trên môi trường Windows", 3),
    (49, "111043", "Phân tích thiết kế hệ thống hướng đối tượng", 3),
    (50, "111089", "Phân tích thiết kế hệ thống hướng quan hệ", 3),
    # HK6
    (51, "102079", "English 6", 4),
    (52, "112068", "Thiết kế hệ thống mạng nâng cao", 2),
    (53, "111069", "Lập trình giao tiếp thiết bị", 2),
    (54, "111082", "Lập trình ứng dụng di động", 3),
    (55, "111083", "Lập trình ứng dụng web", 3),
    (56, "111071", "Lập trình Python cho học máy", 2),
    (57, "111084", "Lập trình Python trong thị giác máy tính", 2),
    # HK7
    (58, "102080", "English 7", 4),
    (59, "111065", "Kiểm thử và đảm bảo chất lượng phần mềm", 3),
    (60, "111085", "Quản trị website trên VPS", 2),
    (61, "111038", "Phát triển ứng dụng", 9),
    (62, "111088", "Trí tuệ nhân tạo", 3),
    (63, "111061", "Công nghệ Blockchain", 3),
    # HK8
    (64, "111049", "Thực tập", 2),
    (65, "33333", "Tốt nghiệp", 8)
]

CONDITION_PC_IDS = {13, 14, 22, 28}


def run_migration(dry_run: bool = False):
    load_dotenv('.env')
    conn_str = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=HocVuAI;Trusted_Connection=yes;"
    conn = pyodbc.connect(conn_str, autocommit=False)
    cursor = conn.cursor()

    try:
        print("=== BẮT ĐẦU MIGRATION MỤC 10 (COURSES & PROGRAM_COURSES) ===")

        # 0. Kiểm tra thông tin student 1 TRƯỚC migration
        cursor.execute("""
            SELECT SUM(c.credits)
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            WHERE g.student_id = 1 AND g.passed = 1
        """)
        stu1_credits_passed_before = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT SUM(c.credits)
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            WHERE g.student_id = 1 AND g.passed = 0
        """)
        stu1_credits_failed_before = cursor.fetchone()[0] or 0

        print(f"--> Student 1 TRƯỚC: Passed credits = {stu1_credits_passed_before}, Failed credits = {stu1_credits_failed_before}")

        # 1. Thêm các môn mới vào bảng courses (chỉ INSERT khi mã môn chưa tồn tại)
        insert_count = 0
        existing_courses_map = {}  # code -> course_id

        # Lấy danh sách môn hiện có
        cursor.execute("SELECT id, code FROM courses")
        for cid, code in cursor.fetchall():
            existing_courses_map[code] = cid

        for pc_id, code, name, credits_val in COURSES_TO_MAP:
            if code not in existing_courses_map:
                # INSERT vào courses (tên cột là 'credits', không phải 'creds')
                cursor.execute(
                    "INSERT INTO courses (code, name, credits) OUTPUT INSERTED.id VALUES (?, ?, ?)",
                    (code, name, credits_val)
                )
                new_id = cursor.fetchone()[0]
                existing_courses_map[code] = new_id
                insert_count += 1

        print(f"--> Đã INSERT thành công {insert_count} môn mới vào bảng courses.")

        # 2. Cập nhật course_id cho các dòng trong program_courses
        update_count = 0
        for pc_id, code, name, credits_val in COURSES_TO_MAP:
            course_id = existing_courses_map[code]
            cursor.execute(
                "UPDATE program_courses SET course_id = ? WHERE id = ?",
                (course_id, pc_id)
            )
            update_count += cursor.rowcount

        print(f"--> Đã UPDATE course_id cho {update_count} dòng trong program_courses.")

        # 3. KIỂM TRA ĐIỀU KIỆN ĐỂ COMMIT HOẶC ROLLBACK:

        # Kiểm tra a: Đúng 0 dòng course_id là NULL ngoài 4 môn điều kiện (GDQP, GDTC 1, 2, 3)
        cursor.execute("SELECT id, ten_mon FROM program_courses WHERE course_id IS NULL")
        null_rows = cursor.fetchall()
        null_ids = set([r[0] for r in null_rows])

        print(f"--> Các dòng có course_id là NULL: {null_ids}")
        if null_ids != CONDITION_PC_IDS:
            unexpected = null_ids - CONDITION_PC_IDS
            missing = CONDITION_PC_IDS - null_ids
            raise ValueError(f"Kiểm tra a thất bại! Dòng NULL không khớp với 4 môn điều kiện: bất thường = {unexpected}, thiếu = {missing}")
        print("--> [PASS] Kiểm tra a: Đúng 0 dòng course_id là NULL ngoài 4 môn điều kiện.")

        # Kiểm tra b: Tổng tín chỉ trong program_courses cho CTĐT = 150
        cursor.execute("SELECT SUM(tin_chi) FROM program_courses WHERE major = N'Công nghệ thông tin'")
        total_credits_ctdt = cursor.fetchone()[0]
        print(f"--> Tổng tín chỉ CTĐT CNTT: {total_credits_ctdt} TC")
        if total_credits_ctdt != 150:
            raise ValueError(f"Kiểm tra b thất bại! Tổng tín chỉ CTĐT CNTT = {total_credits_ctdt} (kỳ vọng 150).")
        print("--> [PASS] Kiểm tra b: Tổng tín chỉ trong program_courses cho CTĐT = 150.")

        # Kiểm tra c: Graduation-check / credit progress cho student_id = 1 trước và sau không đổi
        cursor.execute("""
            SELECT SUM(c.credits)
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            WHERE g.student_id = 1 AND g.passed = 1
        """)
        stu1_credits_passed_after = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT SUM(c.credits)
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            WHERE g.student_id = 1 AND g.passed = 0
        """)
        stu1_credits_failed_after = cursor.fetchone()[0] or 0

        print(f"--> Student 1 SAU: Passed credits = {stu1_credits_passed_after}, Failed credits = {stu1_credits_failed_after}")
        if (stu1_credits_passed_after != stu1_credits_passed_before or
            stu1_credits_failed_after != stu1_credits_failed_before):
            raise ValueError(
                f"Kiểm tra c thất bại! Tín chỉ student 1 bị thay đổi: "
                f"passed ({stu1_credits_passed_before} -> {stu1_credits_passed_after}), "
                f"failed ({stu1_credits_failed_before} -> {stu1_credits_failed_after})"
            )
        print("--> [PASS] Kiểm tra c: Graduation-check của student_id = 1 trước và sau hoàn toàn nhất quán.")

        if dry_run:
            print("--> Chế độ DRY-RUN: ROLLBACK toàn bộ thay đổi.")
            conn.rollback()
        else:
            conn.commit()
            print("--> [COMMIT THÀNH CÔNG] Toàn bộ thay đổi đã được lưu vào database!")

        return {
            "inserted_courses": insert_count,
            "updated_program_courses": update_count,
            "total_ctdt_credits": total_credits_ctdt,
            "null_course_id_count": len(null_ids)
        }

    except Exception as e:
        conn.rollback()
        print(f"--> [ROLLBACK] Gặp lỗi trong quá trình migration: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    run_migration(dry_run=is_dry)

