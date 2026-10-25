import sys
import json
from sqlalchemy import create_engine, text
from backend.app.config import settings
from backend.app.services.retrieval import search_chunks

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    total_chunks = conn.execute(text("SELECT COUNT(*) FROM document_chunks")).scalar()
    chunks_with_embed = conn.execute(text("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL")).scalar()
    print(f"Tổng số văn bản: {conn.execute(text('SELECT COUNT(*) FROM documents')).scalar()}")
    print(f"Tổng số chunk: {total_chunks}")
    print(f"Số chunk đã có embedding: {chunks_with_embed}")

test_queries = [
    "Điểm trung bình tích lũy tối thiểu để tốt nghiệp là bao nhiêu?",
    "Sinh viên có cần chứng chỉ Giáo dục quốc phòng và thể chất không?",
    "Hồ sơ xét tốt nghiệp gồm những gì và nộp ở đâu?"
]

from backend.app.db import SessionLocal
db = SessionLocal()

print("\n=== THỬ TRUY XUẤT 3 CÂU HỎI MẪU ===")
for q in test_queries:
    print(f"\nQuery: '{q}'")
    results = search_chunks(db, q)
    print(f"Số chunk trả về: {len(results)}")
    for r in results:
        print(f" - [{r.get('title')}] Mục {r.get('section')} (Chunk #{r.get('chunk_index')}, Score: {r.get('score'):.4f})")
        print(f"   Snippet: {r.get('content')[:120]}...")
db.close()
