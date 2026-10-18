import sys
import os
from sqlalchemy import text
import traceback

# Add the project root to sys.path so we can import backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.db import SessionLocal
from backend.app.security import get_password_hash

def main():
    out = open("db_test_result.txt", "w", encoding="utf-8")
    try:
        db = SessionLocal()
        
        out.write("--- Buoc 2: Kiem tra du lieu hien co ---\n")
        user_check = db.execute(text("SELECT username FROM users WHERE username = '123000969'")).fetchone()
        if user_check:
            out.write("[+] Tim thay username '123000969'\n")
        else:
            out.write("[-] Khong tim thay username '123000969'\n")
            
        users_list = db.execute(text("SELECT username FROM users")).fetchmany(5)
        out.write(f"5 username mau: {[u.username for u in users_list]}\n")

        out.write("\n--- Buoc 3: Tao user test01 ---\n")
        test_user = db.execute(text("SELECT id FROM users WHERE username = 'test01'")).fetchone()
        if test_user:
            out.write("User test01 da ton tai, dang xoa...\n")
            db.execute(text("DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM chat_sessions WHERE user_id = :uid)"), {"uid": test_user.id})
            db.execute(text("DELETE FROM chat_sessions WHERE user_id = :uid"), {"uid": test_user.id})
            db.execute(text("DELETE FROM grades WHERE student_id IN (SELECT id FROM students WHERE user_id = :uid)"), {"uid": test_user.id})
            db.execute(text("DELETE FROM students WHERE user_id = :uid"), {"uid": test_user.id})
            db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": test_user.id})
            db.commit()

        pwd_hash = get_password_hash("Test@123")
        res = db.execute(text("INSERT INTO users (username, password_hash, role) OUTPUT INSERTED.id VALUES ('test01', :pwd, 'student')"), {"pwd": pwd_hash})
        user_id = res.fetchone()[0]
        
        # Insert student normally (without IDENTITY_INSERT)
        res_stu = db.execute(text("INSERT INTO students (user_id, student_code, full_name, major, cohort) OUTPUT INSERTED.id VALUES (:uid, 'T01', 'Sinh Vien Test', 'CNTT', 2020)"), {"uid": user_id})
        student_id = res_stu.fetchone()[0]
        
        courses_to_insert = [
            ("CS101", "C++ Programming", 3),
            ("CS102", "Data Structures", 4)
        ]
        
        course_ids = []
        for code, name, credits in courses_to_insert:
            c = db.execute(text("SELECT id FROM courses WHERE code = :code"), {"code": code}).fetchone()
            if not c:
                ins_c = db.execute(text("INSERT INTO courses (code, name, credits) OUTPUT INSERTED.id VALUES (:code, :name, :credits)"), {"code": code, "name": name, "credits": credits})
                c_id = ins_c.fetchone()[0]
            else:
                c_id = c.id
            course_ids.append(c_id)
            
        for c_id in course_ids:
            db.execute(text("INSERT INTO grades (student_id, course_id, passed, source, score, semester) VALUES (:sid, :cid, 0, 'manual', 3.0, '2023_1')"), {"sid": student_id, "cid": c_id})
            
        db.commit()
        out.write(f"[+] Tao user test01 thanh cong. users.id={user_id}, students.id={student_id}\n")
        print(f"[+] Tao user test01 thanh cong. users.id={user_id}, students.id={student_id}")
        
    except Exception as e:
        out.write(f"LOI DB: {e}\n")
        out.write(traceback.format_exc())
    finally:
        try:
            db.close()
        except:
            pass
        out.close()

if __name__ == "__main__":
    main()
