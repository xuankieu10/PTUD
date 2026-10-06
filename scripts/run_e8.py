from sqlalchemy import create_engine, text
from backend.app.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    doc = conn.execute(text("SELECT TOP 1 id, status FROM documents ORDER BY id DESC")).fetchone()
    if doc:
        print(f"Doc ID: {doc.id}, Status: {doc.status}")
        chunks = conn.execute(text("SELECT id, DATALENGTH(embedding) as emb_len FROM document_chunks WHERE document_id = :id"), {"id": doc.id}).fetchall()
        print(f"Num chunks: {len(chunks)}")
        for c in chunks:
            print(f"Chunk {c.id} embedding bytes: {c.emb_len}")
    else:
        print("No documents found.")
