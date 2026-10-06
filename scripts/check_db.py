from sqlalchemy import create_engine, text
from backend.app.config import settings

print(f"Checking DB connection using URL: {settings.DATABASE_URL}")
try:
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        print(f"SUCCESS: Connected to DB. Number of users: {result}")
except Exception as e:
    print(f"FAILED to connect to DB: {e}")
