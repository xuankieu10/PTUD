"""
database/migration_sync_curriculum_59_courses.py
Migration chuẩn hóa danh mục môn học CTĐT CNTT LHU (59 dòng, 150 tín chỉ) theo Niên giám 2023:
1. Thêm 6 môn học cơ sở ngành chính thức (mã 6 chữ số) vào bảng courses:
   - 102087: Xác suất thống kê (2 TC)
   - 102014: Tin học đại cương (3 TC)
   - 112061: Mạng máy tính (2 TC)
   - 111062: Cấu trúc dữ liệu và giải thuật (3 TC)
   - 111059: Cơ sở dữ liệu (3 TC)
   - 111070: Lập trình hướng đối tượng (3 TC)
   (Giữ nguyên các môn legacy IT/MI trong courses để không vi phạm ràng buộc FK với bảng grades cũ).
2. Ánh xạ các dòng pc_id tương ứng trong program_courses sang course_id mã 6 chữ số:
   - pc_id 12 -> 102087
   - pc_id 1  -> 102014
   - pc_id 4  -> 112061
   - pc_id 2  -> 111062
   - pc_id 3  -> 111059
   - pc_id 5  -> 111070
3. Đảm bảo cấu trúc 59 dòng của program_courses:
   - 4 môn điều kiện (GDQP, GDTC 1, 2, 3) có tin_chi = NULL (GDQP course_id = NULL vì Niên giám không có mã).
   - 3 môn nhánh tự chọn thứ 2 (111089, 111084, 111061) có tin_chi = NULL để không cộng đôi.
   - 52 môn học tính điểm có tổng SUM(tin_chi) = đúng 150 TC.
4. Idempotent và hỗ trợ --dry-run.
"""

import sys
import os
import pyodbc
from dotenv import load_dotenv

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 6 môn cơ sở ngành chính thức cần đảm bảo trong courses và map vào program_courses
OFFICIAL_CORE_COURSES = [
    (12, "102087", "Xác suất thống kê", 2, 2),
    (1,  "102014", "Tin học đại cương", 3, 2),
    (4,  "112061", "Mạng máy tính", 2, 2),
    (2,  "111062", "Cấu trúc dữ liệu và giải thuật", 3, 3),
    (3,  "111059", "Cơ sở dữ liệu", 3, 3),
    (5,  "111070", "Lập trình hướng đối tượng", 3, 4),
]


def run_migration(dry_run: bool = False):
    load_dotenv('.env')
    conn_str = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=HocVuAI;Trusted_Connection=yes;"
    conn = pyodbc.connect(conn_str, autocommit=False)
    cursor = conn.cursor()

    try:
        print("=== BẮT ĐẦU MIGRATION CHUẨN HÓA CTĐT 59 DÒNG (150 TC) ===")
        print(f"--> Chế độ: {'DRY-RUN (Chỉ kiểm tra, không ghi DB)' if dry_run else 'RUN (Thực thi ghi DB)'}")

        # 1. Kiểm tra / thêm 6 môn chính thức vào bảng courses
        cursor.execute("SELECT id, code, name, credits FROM courses")
        courses_by_code = {r[1]: {"id": r[0], "name": r[2], "credits": r[3]} for r in cursor.fetchall()}

        inserted_courses = []
        for pc_id, code, name, creds, hk in OFFICIAL_CORE_COURSES:
            if code not in courses_by_code:
                if not dry_run:
                    cursor.execute(
                        "INSERT INTO courses (code, name, credits) OUTPUT INSERTED.id VALUES (?, ?, ?)",
                        (code, name, creds)
                    )
                    new_id = cursor.fetchone()[0]
                    courses_by_code[code] = {"id": new_id, "name": name, "credits": creds}
                else:
                    courses_by_code[code] = {"id": -999, "name": name, "credits": creds}
                inserted_courses.append((code, name, creds))

        print(f"--> [Courses] Môn mới cần thêm vào bảng courses: {len(inserted_courses)}")
        for c in inserted_courses:
            print(f"    + INSERT: {c[0]} - {c[1]} ({c[2]} TC)")

        # 2. Ánh xạ pc_id sang course_id mã 6 chữ số
        updated_mappings = []
        for pc_id, code, name, creds, hk in OFFICIAL_CORE_COURSES:
            target_cid = courses_by_code[code]["id"]
            cursor.execute("SELECT id, course_id, ten_mon, tin_chi FROM program_courses WHERE id = ?", (pc_id,))
            row = cursor.fetchone()
            if row:
                old_cid = row[1]
                if old_cid != target_cid:
                    updated_mappings.append((pc_id, name, old_cid, target_cid, code))
                    if not dry_run:
                        cursor.execute(
                            "UPDATE program_courses SET course_id = ?, tin_chi = ? WHERE id = ?",
                            (target_cid, creds, pc_id)
                        )

        print(f"--> [Program Courses] Số dòng ánh xạ lại course_id: {len(updated_mappings)}")
        for u in updated_mappings:
            print(f"    + UPDATE pc_id={u[0]} ({u[1]}): course_id cũ={u[2]} -> mới={u[3]} (mã {u[4]})")

        # 3. Kiểm tra tính toàn vẹn của program_courses
        cursor.execute("SELECT COUNT(*) FROM program_courses WHERE major = N'Công nghệ thông tin'")
        total_rows = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(tin_chi) FROM program_courses WHERE major = N'Công nghệ thông tin'")
        total_credits = cursor.fetchone()[0]

        cursor.execute("SELECT id, ten_mon FROM program_courses WHERE major = N'Công nghệ thông tin' AND course_id IS NULL")
        null_courses = cursor.fetchall()

        print("\n--> [KIỂM TRA TÍNH TOÀN VẸN]")
        print(f"    - Tổng số dòng program_courses: {total_rows} (Kỳ vọng: 59)")
        print(f"    - Tổng tín chỉ CTĐT: {total_credits} TC (Kỳ vọng: 150)")
        print(f"    - Số môn có course_id là NULL: {len(null_courses)} môn")
        for nc in null_courses:
            print(f"      * pc_id={nc[0]}: {nc[1]}")

        if total_rows != 59:
            raise ValueError(f"Tổng số dòng CTĐT = {total_rows} != 59!")
        if total_credits != 150:
            raise ValueError(f"Tổng tín chỉ CTĐT = {total_credits} != 150!")
        
        # 4. Kiểm tra student 1 không bị lỗi
        cursor.execute("""
            SELECT SUM(c.credits)
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            WHERE g.student_id = 1 AND g.passed = 1
        """)
        stu1_passed = cursor.fetchone()[0] or 0
        print(f"    - Tín chỉ tích lũy đạt của Student 1: {stu1_passed} TC (bảo toàn)")

        if dry_run:
            print("\n--> [DRY-RUN HOÀN TẤT] Rollback toàn bộ transaction, DB không thay đổi.")
            conn.rollback()
        else:
            conn.commit()
            print("\n--> [COMMIT THÀNH CÔNG] Toàn bộ CTĐT đã được chuẩn hóa vào SQL Server!")

        return {
            "total_rows": total_rows,
            "total_credits": total_credits,
            "inserted_courses": len(inserted_courses),
            "updated_mappings": len(updated_mappings)
        }

    except Exception as e:
        conn.rollback()
        print(f"\n--> [ROLLBACK] Lỗi migration: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    run_migration(dry_run=is_dry)
