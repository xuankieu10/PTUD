import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.services.embedding import get_embeddings_batch

def cosine_similarity(query_emb: np.ndarray, doc_embs: np.ndarray) -> np.ndarray:
    """Tính cosine similarity giữa câu hỏi và ma trận các chunk."""
    # Chuẩn hóa vector câu hỏi
    q_norm = np.linalg.norm(query_emb)
    if q_norm == 0:
        return np.zeros(doc_embs.shape[0])
    q_normalized = query_emb / q_norm
    
    # Chuẩn hóa ma trận document chunks
    d_norms = np.linalg.norm(doc_embs, axis=1, keepdims=True)
    d_norms[d_norms == 0] = 1 # Tránh chia cho 0
    d_normalized = doc_embs / d_norms
    
    # Nhân ma trận
    similarities = np.dot(d_normalized, q_normalized)
    return similarities

def search_chunks(db: Session, query: str) -> list[dict]:
    # 1. Embed query
    query_binary = get_embeddings_batch([query])[0]
    query_emb = np.frombuffer(query_binary, dtype=np.float32)
    
    # 2. Get chunks from DB
    # Chỉ lấy từ những document có status = 'indexed'
    sql = """
        SELECT c.id, c.document_id, d.title, c.chunk_index, c.content, c.embedding
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.status = 'indexed'
    """
    rows = db.execute(text(sql)).fetchall()
    
    if not rows:
        return []
    
    # 3. Calculate similarities
    embs = []
    chunk_data = []
    for row in rows:
        emb = np.frombuffer(row.embedding, dtype=np.float32)
        embs.append(emb)
        chunk_data.append({
            "document_id": row.document_id,
            "title": row.title,
            "chunk_index": row.chunk_index,
            "content": row.content
        })
        
    doc_embs = np.vstack(embs)
    similarities = cosine_similarity(query_emb, doc_embs)
    
    # 4. Filter and sort
    results = []
    for idx, score in enumerate(similarities):
        if score >= settings.SIMILARITY_THRESHOLD:
            chunk_data[idx]["score"] = float(score)
            results.append(chunk_data[idx])
            
    # Sắp xếp giảm dần theo điểm số
    results = sorted(results, key=lambda x: x["score"], reverse=True)
    
    # Lấy top K
    return results[:settings.TOP_K]
