import sys
import os
import re

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.db import SessionLocal
from backend.app.routers.chat import clean_source_text
from sqlalchemy import text

def migrate_legacy_sources():
    db = SessionLocal()
    try:
        rows = db.execute(
            text("SELECT id, content FROM chat_messages WHERE role = 'assistant' AND (content LIKE '%Ngu%' OR content LIKE '%Tham khảo%' OR content LIKE '%cs.lhu.edu.vn%')")
        ).fetchall()
        print(f"Total potential legacy messages to check: {len(rows)}")

        updated_count = 0
        for r in rows:
            original = r.content or ""
            cleaned = clean_source_text(original)
            if cleaned != original:
                db.execute(
                    text("UPDATE chat_messages SET content = :cleaned WHERE id = :id"),
                    {"cleaned": cleaned, "id": r.id}
                )
                updated_count += 1

        db.commit()
        print(f"Successfully cleaned and updated {updated_count} legacy messages in chat_messages table.")
    except Exception as e:
        db.rollback()
        print(f"Error migrating legacy sources: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_legacy_sources()
