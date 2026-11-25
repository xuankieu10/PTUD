import sys, os, time, json, sqlite3
sys.path.insert(0, 'D:/PTUD')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.scripts.seed_dataset import build_knowledge_base_chunks
from backend.scripts.ingest_quy_dinh import parse_docx_chunks, find_docx_file
from backend.app.services.embedding import get_embeddings_batch

db_path = "database/rag_cache.db"
if os.path.exists(db_path):
    print(f"rag_cache.db already exists ({os.path.getsize(db_path)} bytes).")
    sys.exit(0)

print("Building rag_cache.db...")
t0 = time.time()
engine = create_engine(f"sqlite:///{db_path}")

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            title TEXT,
            source TEXT,
            so_hieu TEXT,
            url TEXT,
            status TEXT
        );
    """))
    conn.execute(text("""
        CREATE TABLE document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            chunk_index INTEGER,
            content TEXT,
            embedding BLOB,
            section TEXT,
            verified BOOLEAN,
            metadata TEXT
        );
    """))
    conn.commit()

# Documents
docs_info = [
    (79, "Điều kiện & Thủ tục quy trình xét cấp bằng Tốt nghiệp Đại học", "04_dieu_kien_tot_nghiep.xlsx", "QĐ 1013/QĐ-ĐHLH", "http://cs.lhu.edu.vn", "indexed"),
    (80, "Chương trình đào tạo ngành Công nghệ thông tin", "03_chuong_trinh_dao_tao.xlsx", "Niên giám 2023", "http://cs.lhu.edu.vn", "indexed"),
    (9001, "Tổng hợp quy chế đào tạo và quy định học vụ LHU", "Tong_hop_quy_che_dao_tao_hoc_vu_LHU.docx", "QĐ 22/QĐ-ĐHLH & Quy định học vụ", "http://cs.lhu.edu.vn", "indexed"),
]

with engine.connect() as conn:
    for d in docs_info:
        conn.execute(text("""
            INSERT INTO documents (id, title, source, so_hieu, url, status)
            VALUES (:id, :title, :source, :so_hieu, :url, :status)
        """), {"id": d[0], "title": d[1], "source": d[2], "so_hieu": d[3], "url": d[4], "status": d[5]})
    conn.commit()

# Chunks
chunks_doc1, chunks_doc2 = build_knowledge_base_chunks()
docx_path = find_docx_file()
chunks_doc9001 = parse_docx_chunks(docx_path)

all_items = []
# Doc 79
for idx, c in enumerate(chunks_doc1):
    all_items.append({
        "document_id": 79, "chunk_index": idx, "content": c["content"], "section": c["section"], "verified": True, "metadata": None
    })
# Doc 80
for idx, c in enumerate(chunks_doc2):
    all_items.append({
        "document_id": 80, "chunk_index": idx, "content": c["content"], "section": c["section"], "verified": True, "metadata": None
    })
# Doc 9001
for c in chunks_doc9001:
    all_items.append({
        "document_id": 9001, "chunk_index": c["chunk_index"], "content": c["content"], "section": c["section"], "verified": c.get("verified", True), "metadata": None
    })

print(f"Total chunks to embed: {len(all_items)}")
texts = [item["content"] for item in all_items]

# Embed in batches of 16
embeddings = []
batch_size = 16
for i in range(0, len(texts), batch_size):
    batch = texts[i:i+batch_size]
    print(f"Embedding batch {i//batch_size + 1}/{(len(texts)+batch_size-1)//batch_size} ({len(batch)} chunks)...")
    embs = get_embeddings_batch(batch)
    embeddings.extend(embs)

with engine.connect() as conn:
    for idx, item in enumerate(all_items):
        conn.execute(text("""
            INSERT INTO document_chunks (document_id, chunk_index, content, embedding, section, verified, metadata)
            VALUES (:did, :idx, :content, :emb, :sec, :verified, :meta)
        """), {
            "did": item["document_id"],
            "idx": item["chunk_index"],
            "content": item["content"],
            "emb": embeddings[idx],
            "sec": item["section"],
            "verified": item["verified"],
            "meta": item["metadata"]
        })
    conn.commit()

print(f"Done in {time.time() - t0:.2f}s. Saved to {db_path}.")
