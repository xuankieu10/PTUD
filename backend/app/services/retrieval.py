import re
import unicodedata
from collections import defaultdict, Counter
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.services.embedding import get_embeddings_batch
from backend.app.services.synonyms import SYNONYM_MAPPINGS

# Ký tự có dấu trong tiếng Việt dùng để phát hiện câu hỏi không dấu
VIETNAMESE_ACCENT_CHARS = frozenset("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ")

# Bộ nhớ đệm (cache in-memory) cho từ điển khôi phục dấu và chỉ mục chunk
_GLOBAL_ACCENT_DICT: dict[str, str] = {}
_LAST_CHUNKS_SIGNATURE: int = 0


def strip_accents(text: str) -> str:
    """
    Chuẩn hoá loại bỏ dấu tiếng Việt, xử lý riêng chữ đ/Đ thành d/D.
    Sử dụng NFD để tách combining marks và loại bỏ category 'Mn'.
    """
    if not text:
        return ""
    # Xử lý riêng chữ đ và Đ trước khi tách combining diacritics
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", stripped)


def is_unaccented(text: str) -> bool:
    """
    Kiểm tra xem văn bản có phải dạng không dấu (không chứa bất kỳ nguyên âm/phụ âm có dấu) không.
    """
    return not any(c in VIETNAMESE_ACCENT_CHARS for c in text)


def build_accent_dictionary(chunks: list[dict]) -> dict[str, str]:
    """
    Dựng từ điển 'từ không dấu -> từ có dấu phổ biến nhất' từ chính nội dung các chunk trong kho tri thức.
    Đếm tần suất xuất hiện thực tế để chọn từ phù hợp ngữ cảnh học vụ của trường (không hardcode).
    """
    word_freq = defaultdict(Counter)
    word_pattern = re.compile(r'[a-zA-ZàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]+')

    for c in chunks:
        content = (c.get("content") or "") + " " + (c.get("title") or "")
        words = word_pattern.findall(content)
        for w in words:
            w_lower = w.lower()
            unaccent = strip_accents(w_lower)
            # Chỉ thu thập những từ thực sự có dấu
            if w_lower != unaccent:
                word_freq[unaccent][w_lower] += 1

    accent_dict = {}
    for unaccent, counter in word_freq.items():
        most_common_word, _ = counter.most_common(1)[0]
        accent_dict[unaccent] = most_common_word

    return accent_dict


def get_or_build_accent_dictionary(chunks: list[dict]) -> dict[str, str]:
    """
    Lấy từ điển khôi phục dấu từ cache in-memory, hoặc xây mới nếu số lượng chunk thay đổi.
    """
    global _GLOBAL_ACCENT_DICT, _LAST_CHUNKS_SIGNATURE
    sig = len(chunks)
    if not _GLOBAL_ACCENT_DICT or sig != _LAST_CHUNKS_SIGNATURE:
        _GLOBAL_ACCENT_DICT = build_accent_dictionary(chunks)
        _LAST_CHUNKS_SIGNATURE = sig
    return _GLOBAL_ACCENT_DICT


def restore_accents(query: str, accent_dict: dict[str, str]) -> str:
    """
    Khôi phục dấu cho câu hỏi không dấu dựa trên từ điển tần suất từ chunk.
    Bảo toàn chữ hoa/thường của ký tự đầu.
    """
    if not query or not accent_dict:
        return query

    def replace_word(match):
        w = match.group(0)
        w_lower = w.lower()
        if w_lower in accent_dict:
            restored = accent_dict[w_lower]
            if w.isupper():
                return restored.upper()
            elif w[0].isupper():
                return restored.capitalize()
            return restored
        return w

    return re.sub(r'[a-zA-ZàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]+', replace_word, query)


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
    Viết lại câu hỏi và bổ sung từ đồng nghĩa / khẩu ngữ để cải thiện khả năng embedding và retrieval.
    Tận dụng bảng từ đồng nghĩa tách riêng trong synonyms.py.
    """
    q_lower = query.lower()
    q_unaccent = strip_accents(q_lower)
    additions = []

    # Duyệt bảng từ đồng nghĩa / khẩu ngữ
    for triggers, addition_text in SYNONYM_MAPPINGS:
        if any(tr.lower() in q_lower or strip_accents(tr.lower()) in q_unaccent for tr in triggers):
            if addition_text not in additions:
                additions.append(addition_text)

    # Bổ sung cụm điều kiện tốt nghiệp nếu có hỏi về chuẩn đầu ra
    if any(k in q_unaccent for k in ["chuan dau ra", "dau ra", "chuan ra"]):
        if "điều kiện xét tốt nghiệp chuẩn đầu ra" not in additions:
            additions.append("điều kiện xét tốt nghiệp chuẩn đầu ra")

    if additions:
        return f"{query} {' '.join(additions)}"
    return query


def compute_keyword_score(query: str, content: str, section: str = "", content_unaccent: str = "") -> float:
    """
    Tính điểm trùng khớp từ khóa (keyword score) phục vụ tìm kiếm kết hợp Hybrid.
    So khớp trên văn bản không dấu của cả câu hỏi và chunk để hỗ trợ tốt nhất câu không dấu.
    """
    q_unaccent = strip_accents(query).lower()
    c_unaccent = content_unaccent if content_unaccent else strip_accents(content + " " + (section or "")).lower()

    # Bảng nhóm từ khóa: (trigger_khong_dau, [danh_sach_tu_muc_tieu_khong_dau])
    key_phrases = [
        ("chuan dau ra", ["chuan dau ra", "dieu kien tot nghiep", "tot nghiep"]),
        ("dieu kien", ["dieu kien", "chuan dau ra", "tot nghiep"]),
        ("ra truong", ["tot nghiep", "ho so", "le phi", "ra truong"]),
        ("ra bang", ["tot nghiep", "bang dai hoc", "dieu kien"]),
        ("tieng anh", ["tieng anh", "ngoai ngu", "bac 3", "toeic", "ielts", "vstep"]),
        ("ngoai ngu", ["ngoai ngu", "tieng anh", "bac 3", "toeic", "ielts", "vstep"]),
        ("tin hoc", ["tin hoc", "sat hach", "ung dung cong nghe thong tin", "ung dung cntt", "khoa cntt"]),
        ("sat hach", ["sat hach", "sat hach tin hoc"]),
        ("gpa", ["gpa", "diem trung binh", "5.0", "tich luy"]),
        ("diem trung binh", ["diem trung binh", "5.0", "tich luy"]),
        ("quoc phong", ["giao duc quoc phong", "gdqp"]),
        ("the chat", ["giao duc the chat", "gdtc", "the duc"]),
        ("ky nang mem", ["ky nang mem", "4 ky nang", "knm"]),
        ("hoc phi", ["hoc phi"]),
        ("thu vien", ["thu vien", "tai lieu"]),
        ("lien thong", ["lien thong", "hoan chinh"]),
        ("ho so", ["ho so", "graduate.lhu.edu.vn", "giay to"]),
        ("giay to", ["ho so", "graduate.lhu.edu.vn", "giay to", "le phi"]),
        ("le phi", ["le phi", "100.000"]),
        ("giay chung nhan", ["giay chung nhan hoan thanh khoa hoc", "giay chung nhan", "muc d", "phong dao tao"]),
        ("chua nop du", ["chua du dieu kien", "thieu chung chi", "giay chung nhan hoan thanh khoa hoc", "muc d"]),
        ("hoc lai", ["hoc lai", "hoc phan", "hoc ky phu"]),
        ("hoc vet", ["hoc vet", "hoc lai", "tra no mon"]),
        ("rot", ["khong dat", "canh bao hoc vu", "duoi 4.0"]),
        ("truot", ["khong dat", "canh bao hoc vu", "duoi 4.0"]),
    ]

    matched_groups = 0
    total_relevant_groups = 0

    for trigger, target_kws in key_phrases:
        if trigger in q_unaccent:
            total_relevant_groups += 1
            if any(kw in c_unaccent for kw in target_kws):
                matched_groups += 1

    if total_relevant_groups > 0:
        return matched_groups / total_relevant_groups
    return 0.0


def search_chunks(db: Session, query: str) -> list[dict]:
    # 1. Lấy toàn bộ chunks từ database
    sql = """
        SELECT c.id, c.document_id, d.title, c.chunk_index, c.content, c.embedding, c.section, d.so_hieu, d.url
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.status = 'indexed'
    """
    rows = db.execute(text(sql)).fetchall()

    if not rows:
        return []

    # 2. Xây dựng danh sách chunk kèm bản không dấu được tính trước
    embs = []
    chunk_data = []
    for row in rows:
        emb = np.frombuffer(row.embedding, dtype=np.float32)
        embs.append(emb)
        content_str = row.content or ""
        sec_str = getattr(row, "section", None) or ""
        # Lưu trước bản không dấu của chunk để tối ưu tốc độ so khớp từ khóa
        content_unaccent = strip_accents(f"{content_str} {sec_str}").lower()

        chunk_data.append({
            "id": row.id,
            "document_id": row.document_id,
            "title": row.title,
            "chunk_index": row.chunk_index,
            "content": content_str,
            "section": getattr(row, "section", None),
            "so_hieu": getattr(row, "so_hieu", None),
            "url": getattr(row, "url", None),
            "content_unaccent": content_unaccent,
        })

    doc_embs = np.vstack(embs)

    # 3. Khôi phục dấu cho câu hỏi không dấu qua từ điển học từ chính các chunk
    accent_dict = get_or_build_accent_dictionary(chunk_data)
    unaccent_flag = is_unaccented(query)
    restored_query = restore_accents(query, accent_dict)
    has_restored = unaccent_flag and (strip_accents(restored_query).lower() == strip_accents(query).lower() and restored_query.lower() != query.lower())

    # 4. Viết lại câu hỏi và embedding song song nếu là câu hỏi không dấu
    rewritten_orig = rewrite_query(query)

    if has_restored:
        rewritten_restored = rewrite_query(restored_query)
        # Embed cả 2 bản: bản gốc không dấu và bản đã khôi phục dấu
        query_binaries = get_embeddings_batch([rewritten_orig, rewritten_restored])
        q_emb_orig = np.frombuffer(query_binaries[0], dtype=np.float32)
        q_emb_restored = np.frombuffer(query_binaries[1], dtype=np.float32)

        sim_orig = cosine_similarity(q_emb_orig, doc_embs)
        sim_restored = cosine_similarity(q_emb_restored, doc_embs)
        # Lấy độ tương đồng vector tốt nhất giữa 2 bản
        vec_similarities = np.maximum(sim_orig, sim_restored)
    else:
        query_binary = get_embeddings_batch([rewritten_orig])[0]
        q_emb = np.frombuffer(query_binary, dtype=np.float32)
        vec_similarities = cosine_similarity(q_emb, doc_embs)

    # 5. Hybrid combine: Vector similarity (70%) + Keyword score không dấu (30%)
    results = []
    for idx, v_score in enumerate(vec_similarities):
        c = chunk_data[idx]
        kw_score = compute_keyword_score(
            query,
            c["content"],
            c.get("section") or "",
            c.get("content_unaccent") or ""
        )

        combined_score = float(0.70 * v_score + 0.30 * kw_score)

        # Giữ nguyên ngưỡng SIMILARITY_THRESHOLD không hạ thấp
        if combined_score >= settings.SIMILARITY_THRESHOLD or v_score >= settings.SIMILARITY_THRESHOLD:
            c["score"] = combined_score
            c["vector_score"] = float(v_score)
            c["keyword_score"] = float(kw_score)
            results.append(c)

    # Sắp xếp giảm dần theo điểm số kết hợp
    results = sorted(results, key=lambda x: x["score"], reverse=True)

    # 6. Khử trùng lặp và lọc bớt chunk không cần thiết để giảm độ dài prompt
    q_lower = query.lower()
    q_unaccent = strip_accents(q_lower)
    is_lien_thong = ("liên thông" in q_lower or "hoàn chỉnh" in q_lower or "lien thong" in q_unaccent or "hoan chinh" in q_unaccent)

    # Kiểm tra xem câu hỏi có nhắc riêng từng mảng không
    mentions_only_english = any(w in q_unaccent for w in ["tieng anh", "ngoai ngu", "toeic", "ielts", "toefl", "cambridge"]) and not any(w in q_unaccent for w in ["tin hoc", "sat hach", "chuan dau ra", "quy dinh ve chuan"])
    mentions_only_it = any(w in q_unaccent for w in ["tin hoc", "sat hach", "mos", "cisco", "cntt", "cong nghe thong tin"]) and not any(w in q_unaccent for w in ["tieng anh", "ngoai ngu", "chuan dau ra", "quy dinh ve chuan"])
    has_specific_image = any(w in q_unaccent for w in ["hinh 1", "hinh 2"])

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

    # Lấy top_k cấu hình trong settings để kiểm soát lượng ngữ cảnh
    return filtered_candidates[:settings.TOP_K]

