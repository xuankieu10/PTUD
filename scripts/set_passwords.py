import os
import sys

# Thêm thư mục gốc vào sys.path để import từ backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend.app.db import SessionLocal
from backend.app.security import get_password_hash

def main():
    db = SessionLocal()
    try:
        users = db.execute(text("SELECT id, username, role FROM users")).fetchall()
        
        updated_usernames = []
        for user in users:
            new_password = None
            if user.role == "admin" or user.username == "admin":
                new_password = "Admin@123"
            elif user.role == "student" or user.username.startswith("sv"):
                new_password = "Sv@12345"
            else:
                # Default for other students
                new_password = "Sv@12345"
                
            if new_password:
                hashed_pw = get_password_hash(new_password)
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
