import sys, os
sys.path.insert(0, os.path.abspath("."))
from backend.app.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("=== ALL TABLES AND COLUMNS ===")
    tables = [t[0] for t in conn.execute(text("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'"))]
    for tbl in tables:
        cols = [f"{c[0]} ({c[1]})" for c in conn.execute(text(f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{tbl}'"))]
        print(f"\n{tbl}:")
        for col in cols:
            print(f"  {col}")
