import re
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.services.embedding import get_embeddings_batch


def cosine_similarity(query_emb: np.ndarray, doc_embs: np.ndarray) -> np.ndarray:
    """Tính cosine similarity giữa câu hỏi và ma trận các chunk."""
    q_norm = np.linalg.norm(query_emb)
    if q_norm == 0:
        return np.zeros(doc_embs.shape[0])
    q_normalized = query_emb / q_norm

    d_norms = np.linalg.norm(doc_embs, axis=1, keepdims=True)
    d_norms[d_norms == 0] = 1
    d_normalized = doc_embs / d_norms

    similarities = np.dot(d_normalized, q_normalized)
    return similarities


def rewrite_query(query: str) -> str:
    """
    Viết lại câu hỏi và bổ sung từ đồng nghĩa để cải thiện khả năng embedding và retrieval.
    - 'chuẩn đầu ra' -> 'điều kiện tốt nghiệp';
    - 'tiếng Anh' -> 'ngoại ngữ Bậc 3';
    - 'tin học' -> 'sát hạch tin học, ứng dụng công nghệ thông tin'.
    """
    q_lower = query.lower()
    additions = []
    if "chuẩn đầu ra" in q_lower or "chuan dau ra" in q_lower or "đầu ra" in q_lower:
        additions.append("điều kiện xét tốt nghiệp")
    if any(k in q_lower for k in ["tiếng anh", "tieng anh", "anh văn", "toeic", "ielts", "vstep", "ngoại ngữ", "ngoai ngu"]):
        additions.append("ngoại ngữ Tiếng Anh Bậc 3")
    if any(k in q_lower for k in ["tin học", "tin hoc", "sát hạch", "sat hach", "ứng dụng công nghệ thông tin", "cntt", "ung dung cntt"]):
        additions.append("sát hạch tin học ứng dụng công nghệ thông tin Khoa CNTT")
    if any(k in q_lower for k in ["gpa", "điểm trung bình", "diem trung binh", "điểm tích lũy"]):
        additions.append("điểm trung bình tích lũy 5.0")
    if any(k in q_lower for k in ["quốc phòng", "thể chất", "gdqp", "gdtc"]):
        additions.append("Giáo dục quốc phòng GDQP Giáo dục thể chất GDTC")
    if any(k in q_lower for k in ["kỹ năng mềm", "knm"]):
        additions.append("4 kỹ năng mềm")
    if any(k in q_lower for k in ["hồ sơ", "lệ phí", "nộp ở đâu", "đóng tiền"]):
        additions.append("hồ sơ graduate.lhu.edu.vn lệ phí 100.000 VNĐ phòng Đào tạo B101 Cơ sở 1")
    if any(k in q_lower for k in ["giấy chứng nhận", "chưa nộp đủ", "chưa đủ chứng chỉ", "thiếu chứng chỉ", "chưa đủ điều kiện", "thiếu ngoại ngữ", "thiếu tin học"]):
        additions.append("Mục D Giấy chứng nhận hoàn thành khóa học thiếu điều kiện tốt nghiệp phòng Đào tạo B101 Cơ sở 1")

    if additions:
        return f"{query} {' '.join(additions)}"
    return query


def compute_keyword_score(query: str, content: str, section: str = "") -> float:
    """
    Tính điểm trùng khớp từ khóa (keyword score) phục vụ tìm kiếm kết hợp Hybrid.
    """
    q_lower = query.lower()
    c_lower = (content + " " + (section or "")).lower()

    key_phrases = [
        ("chuẩn đầu ra", ["chuẩn đầu ra", "điều kiện tốt nghiệp"]),
        ("tiếng anh", ["tiếng anh", "ngoại ngữ", "bậc 3"]),
        ("ngoại ngữ", ["ngoại ngữ", "tiếng anh", "bậc 3"]),
        ("tin học", ["tin học", "sát hạch", "ứng dụng công nghệ thông tin", "ứng dụng cntt"]),
        ("sát hạch", ["sát hạch", "sát hạch tin học"]),
        ("gpa", ["gpa", "điểm trung bình", "5.0", "tích lũy"]),
        ("điểm trung bình", ["điểm trung bình", "5.0", "tích lũy"]),
        ("quốc phòng", ["giáo dục quốc phòng", "gdqp"]),
        ("thể chất", ["giáo dục thể chất", "gdtc"]),
        ("kỹ năng mềm", ["kỹ năng mềm", "4 kỹ năng"]),
        ("học phí", ["học phí"]),
        ("thư viện", ["thư viện", "tài liệu"]),
        ("liên thông", ["liên thông", "hoàn chỉnh"]),
        ("hồ sơ", ["hồ sơ", "graduate.lhu.edu.vn"]),
        ("lệ phí", ["lệ phí", "100.000"]),
        ("giấy chứng nhận", ["giấy chứng nhận hoàn thành khóa học", "giấy chứng nhận", "mục d", "phòng đào tạo"]),
        ("chưa nộp đủ", ["chưa đủ điều kiện", "thiếu chứng chỉ", "giấy chứng nhận hoàn thành khóa học", "mục d"]),
    ]

    matched_groups = 0
    total_relevant_groups = 0

    for trigger, target_kws in key_phrases:
        if trigger in q_lower:
            total_relevant_groups += 1
            if any(kw in c_lower for kw in target_kws):
                matched_groups += 1

    if total_relevant_groups > 0:
        return matched_groups / total_relevant_groups
    return 0.0


def search_chunks(db: Session, query: str) -> list[dict]:
    # 1. Rewrite query
    rewritten_query = rewrite_query(query)

    # 2. Embed query
    query_binary = get_embeddings_batch([rewritten_query])[0]
    query_emb = np.frombuffer(query_binary, dtype=np.float32)

    # 3. Get chunks from DB
    sql = """
        SELECT c.id, c.document_id, d.title, c.chunk_index, c.content, c.embedding, c.section, d.so_hieu, d.url
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.status = 'indexed'
    """
    rows = db.execute(text(sql)).fetchall()

    if not rows:
        return []

    # 4. Calculate similarities
    embs = []
    chunk_data = []
    for row in rows:
        emb = np.frombuffer(row.embedding, dtype=np.float32)
        embs.append(emb)
        chunk_data.append({
            "id": row.id,
            "document_id": row.document_id,
            "title": row.title,
            "chunk_index": row.chunk_index,
            "content": row.content,
            "section": getattr(row, "section", None),
            "so_hieu": getattr(row, "so_hieu", None),
            "url": getattr(row, "url", None)
        })

    doc_embs = np.vstack(embs)
    vec_similarities = cosine_similarity(query_emb, doc_embs)

    # 5. Hybrid combine: Vector similarity + Keyword score
    results = []
    for idx, v_score in enumerate(vec_similarities):
        c = chunk_data[idx]
        kw_score = compute_keyword_score(query, c["content"], c.get("section") or "")

        combined_score = float(0.70 * v_score + 0.30 * kw_score)

        if combined_score >= settings.SIMILARITY_THRESHOLD or v_score >= settings.SIMILARITY_THRESHOLD:
            c["score"] = combined_score
            c["vector_score"] = float(v_score)
            c["keyword_score"] = float(kw_score)
            results.append(c)

    # Sắp xếp giảm dần theo điểm số kết hợp
    results = sorted(results, key=lambda x: x["score"], reverse=True)

    # 6. Khử trùng lặp và lọc bớt chunk không cần thiết để giảm độ dài prompt
    q_lower = query.lower()
    is_lien_thong = ("liên thông" in q_lower or "hoàn chỉnh" in q_lower)

    # Kiểm tra xem câu hỏi có nhắc riêng từng mảng không
    mentions_only_english = any(w in q_lower for w in ["tiếng anh", "ngoại ngữ", "toeic", "ielts", "toefl", "cambridge"]) and not any(w in q_lower for w in ["tin học", "sát hạch", "chuẩn đầu ra", "quy định về chuẩn"])
    mentions_only_it = any(w in q_lower for w in ["tin học", "sát hạch", "mos", "cisco", "cntt", "công nghệ thông tin"]) and not any(w in q_lower for w in ["tiếng anh", "ngoại ngữ", "chuẩn đầu ra", "quy định về chuẩn"])
    has_specific_image = ("hình 1" in q_lower or "hình 2" in q_lower or "hinh 1" in q_lower or "hinh 2" in q_lower)

    filtered_candidates = []
    for c in results:
        sec = c.get("section") or ""
        # Không trả chunk B (hệ liên thông) trừ khi câu hỏi nhắc "liên thông/hoàn chỉnh"
        if sec == "B" and not is_lien_thong:
            continue
        filtered_candidates.append(c)

    # Khử trùng lặp A.5: nếu A.5 (tổng hợp) đã có trong top ứng viên, loại bỏ A.5.1 và A.5.2 trừ khi hỏi riêng
    has_a5_general = any(c.get("section") == "A.5" for c in filtered_candidates[:3])
    if has_a5_general and not (mentions_only_english or mentions_only_it or has_specific_image):
        deduped = []
        for c in filtered_candidates:
            sec = c.get("section") or ""
            if sec in ["A.5.1", "A.5.2", "A.5.1-hình", "A.5.2-hình"]:
                continue
            deduped.append(c)
        filtered_candidates = deduped

    # Top K tối đa 3 chunk
    return filtered_candidates[:3]
