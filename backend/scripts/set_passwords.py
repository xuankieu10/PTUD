import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
from sqlalchemy import create_engine, text

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def main():
    db_url = os.getenv("DATABASE_URL", "mssql+pyodbc://@localhost/HocVuAI?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes")
    print(f"Connecting to {db_url}")
    engine = create_engine(db_url)
    
    admin_pw = get_password_hash("Admin@123")
    student_pw = get_password_hash("Sv@12345")
    
    with engine.connect() as conn:
        # Update admin
        conn.execute(text("UPDATE users SET password_hash = :pw WHERE username = 'admin'"), {"pw": admin_pw})
        
        # Update students
        conn.execute(text("UPDATE users SET password_hash = :pw WHERE role = 'student'"), {"pw": student_pw})
        
        conn.commit()
        
        # Query and print
        result = conn.execute(text("SELECT username FROM users"))
        print("Updated passwords for users:")
        for row in result:
            print(f"- {row[0]}")

if __name__ == "__main__":
    main()
