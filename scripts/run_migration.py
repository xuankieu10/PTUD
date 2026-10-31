import sys, os
sys.path.insert(0, os.path.abspath("."))

from backend.app.db import engine
from sqlalchemy import text

def run_sql_file(conn, file_path):
    print(f"Executing migration from: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    batches = [b.strip() for b in content.split("GO") if b.strip()]
    for idx, batch in enumerate(batches, start=1):
        lines = [l for l in batch.split("\n") if not l.strip().upper().startswith("USE ")]
        sql = "\n".join(lines).strip()
        if not sql:
            continue
        try:
            conn.execute(text(sql))
            conn.commit()
            print(f"  Batch {idx}: Success")
        except Exception as e:
            print(f"  Batch {idx} error: {repr(e)}")
            conn.rollback()

def run_migration():
    migration_files = [
        os.path.join(os.path.abspath("database"), "migration_ocr_and_student_fix.sql"),
        os.path.join(os.path.abspath("database"), "migration_student_certificates.sql")
    ]
    with engine.connect() as conn:
        for mf in migration_files:
            if os.path.exists(mf):
                run_sql_file(conn, mf)

    with engine.connect() as conn:
        for tbl in ['student_ocr_transcripts', 'student_certificates']:
            cols = conn.execute(text(f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{tbl}'")).fetchall()
            print(f"\nColumns in {tbl}:")
            for c in cols:
                print(f"  {c[0]} ({c[1]})")

if __name__ == "__main__":
    run_migration()
