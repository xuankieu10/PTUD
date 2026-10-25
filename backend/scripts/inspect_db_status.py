import sys
from sqlalchemy import create_engine, text
from backend.app.config import settings

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        print("DB Connection: SUCCESS")
        tables = conn.execute(text("SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_TYPE, TABLE_NAME")).fetchall()
        print(f"Total tables/views: {len(tables)}")
        for t, type_ in tables:
            try:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM [{t}]")).scalar()
                print(f" - [{type_}] {t}: {cnt} rows")
            except Exception as e:
                print(f" - [{type_}] {t}: ERROR ({e})")
except Exception as e:
    print("DB Connection ERROR:", e)
