import os
import sys
import getpass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.security import get_password_hash
from backend.app.db import engine
from sqlalchemy import text

def main():
    admin_pw = os.getenv("ADMIN_PASSWORD")
    student_pw = os.getenv("STUDENT_PASSWORD")

    if not admin_pw:
        admin_pw = getpass.getpass("Nhập mật khẩu cho tài khoản admin: ")
    if not student_pw:
        student_pw = getpass.getpass("Nhập mật khẩu cho tài khoản sinh viên: ")

    if not admin_pw or not student_pw:
        print("Lỗi: Cần cung cấp mật khẩu cho cả admin và sinh viên.")
        sys.exit(1)

    admin_hash = get_password_hash(admin_pw)
    student_hash = get_password_hash(student_pw)

    print("Đang kết nối database...")
    with engine.connect() as conn:
        # Update admin
        conn.execute(text("UPDATE users SET password_hash = :pw WHERE username = 'admin' OR role = 'admin'"), {"pw": admin_hash})
        
        # Update students
        conn.execute(text("UPDATE users SET password_hash = :pw WHERE role = 'student'"), {"pw": student_hash})
        
        conn.commit()
        
        # Query and print
        result = conn.execute(text("SELECT username FROM users"))
        print("Updated passwords for users:")
        for row in result:
            print(f"- {row[0]}")

if __name__ == "__main__":
    main()
