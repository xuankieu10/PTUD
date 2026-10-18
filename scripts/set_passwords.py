import os
import sys
import getpass

# Thêm thư mục gốc vào sys.path để import từ backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend.app.db import SessionLocal
from backend.app.security import get_password_hash

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

    db = SessionLocal()
    try:
        users = db.execute(text("SELECT id, username, role FROM users")).fetchall()
        
        updated_usernames = []
        for user in users:
            hashed_pw = None
            if user.role == "admin" or user.username == "admin":
                hashed_pw = admin_hash
            elif user.role == "student" or user.username.startswith("sv"):
                hashed_pw = student_hash
            else:
                hashed_pw = student_hash
                
            if hashed_pw:
                db.execute(text("UPDATE users SET password_hash = :hash WHERE id = :id"), {"hash": hashed_pw, "id": user.id})
                updated_usernames.append(user.username)
        
        db.commit()
        print("Updated passwords for users:", ", ".join(updated_usernames))
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
