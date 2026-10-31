import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from backend.app.services.retrieval import (
    strip_accents,
    is_unaccented,
    build_accent_dictionary,
    restore_accents,
    rewrite_query,
    compute_keyword_score,
    search_chunks,
)


def test_strip_accents_basic():
    """Kiểm tra loại bỏ dấu tiếng Việt chuẩn và xử lý riêng đ/Đ."""
    assert strip_accents("Đại học Lạc Hồng") == "Dai hoc Lac Hong"
    assert strip_accents("điều kiện xét tốt nghiệp") == "dieu kien xet tot nghiep"
    assert strip_accents("chuẩn đầu ra ngoại ngữ Tiếng Anh") == "chuan dau ra ngoai ngu Tieng Anh"
    assert strip_accents("ĐỒNG NAI đỗ đạt") == "DONG NAI do dat"
    assert strip_accents("") == ""


def test_is_unaccented():
    """Kiểm tra nhận biết câu có dấu và không dấu."""
    assert is_unaccented("dieu kien xet tot nghiep nganh cong nghe thong tin la gi") is True
    assert is_unaccented("chuan dau ra tieng anh can bao nhieu diem toeic") is True
    assert is_unaccented("Điều kiện để được xét tốt nghiệp đại học gồm những gì?") is False
    assert is_unaccented("Cần nộp giấy tờ gì để ra trường?") is False


def test_build_and_restore_accent_dictionary():
    """Kiểm tra việc dựng từ điển từ các chunk và khôi phục dấu tự động."""
    sample_chunks = [
        {
            "content": "Điều kiện để được xét tốt nghiệp đại học ngành công nghệ thông tin gồm điểm tích lũy và chuẩn đầu ra.",
            "title": "Quy chế đào tạo",
        },
        {
            "content": "Chuẩn đầu ra ngoại ngữ tiếng Anh yêu cầu chứng chỉ TOEIC đạt chuẩn Bậc 3 theo khung năng lực.",
            "title": "Quy định chuẩn đầu ra",
        },
        {
            "content": "Sinh viên cần nộp giấy tờ hồ sơ xét tốt nghiệp và đóng lệ phí tại phòng Đào tạo.",
            "title": "Hướng dẫn nộp hồ sơ",
        },
    ]

    accent_dict = build_accent_dictionary(sample_chunks)

    # Đảm bảo các từ không dấu có trong tài liệu được ánh xạ đúng
    assert accent_dict.get("dieu") == "điều"
    assert accent_dict.get("kien") == "kiện"
    assert accent_dict.get("tot") == "tốt"
    assert accent_dict.get("nghiep") == "nghiệp"
    assert accent_dict.get("tieng") == "tiếng"
    assert accent_dict.get("dau") == "đầu"

    # Test khôi phục dấu câu hỏi không dấu
    q_no_accent = "dieu kien xet tot nghiep nganh cong nghe thong tin la gi"
    restored = restore_accents(q_no_accent, accent_dict)
    assert "điều" in restored
    assert "kiện" in restored
    assert "tốt" in restored
    assert "nghiệp" in restored


def test_rewrite_query_synonyms():
    """Kiểm tra rewrite_query mở rộng khẩu ngữ và từ đồng nghĩa."""
    # Q10: khẩu ngữ 'giấy tờ', 'ra trường'
    q10 = "Cần nộp giấy tờ gì để ra trường?"
    rewritten_10 = rewrite_query(q10)
    assert "hồ sơ" in rewritten_10.lower()
    assert "tốt nghiệp" in rewritten_10.lower()

    # Q11: không dấu 'cong nghe thong tin', 'dieu kien'
    q11 = "dieu kien xet tot nghiep nganh cong nghe thong tin la gi"
    rewritten_11 = rewrite_query(q11)
    assert "điều kiện xét tốt nghiệp" in rewritten_11.lower()
    assert "công nghệ thông tin" in rewritten_11.lower()

    # Q12: không dấu 'tieng anh', 'toeic'
    q12 = "chuan dau ra tieng anh can bao nhieu diem toeic"
    rewritten_12 = rewrite_query(q12)
    assert "ngoại ngữ" in rewritten_12.lower()
    assert "bậc 3" in rewritten_12.lower()

    # Khẩu ngữ rớt / trượt / học lại / GDQP
    assert "không đạt" in rewrite_query("em bị rớt 2 môn thì sao").lower()
    assert "học lại" in rewrite_query("khi nào được học vét").lower()
    assert "giáo dục quốc phòng" in rewrite_query("điều kiện chứng chỉ gdqp").lower()


def test_compute_keyword_score_unaccented():
    """Kiểm tra tính điểm từ khóa không phân biệt dấu."""
    chunk_content = "Quy định về chuẩn đầu ra ngoại ngữ Tiếng Anh Bậc 3 TOEIC đạt 450 điểm"
    section = "A.5.1"

    # Câu hỏi có dấu
    score_with_accent = compute_keyword_score("Chuẩn đầu ra tiếng Anh cần bao nhiêu điểm TOEIC?", chunk_content, section)
    assert score_with_accent > 0.0

    # Câu hỏi hoàn toàn không dấu
    score_without_accent = compute_keyword_score("chuan dau ra tieng anh can bao nhieu diem toeic", chunk_content, section)
    assert score_without_accent > 0.0
    # Điểm khớp từ khóa của cả 2 phải tương đương nhau
    assert score_without_accent == pytest.approx(score_with_accent, rel=1e-2)


def test_search_chunks_unaccented_and_slang():
    """Kiểm tra search_chunks với mock DB và mock embeddings."""
    mock_db = MagicMock()

    # Tạo vector 1024 chiều giả lập cho chunk
    chunk_vec1 = np.ones(1024, dtype=np.float32)
    chunk_vec1 /= np.linalg.norm(chunk_vec1)

    chunk_vec2 = np.zeros(1024, dtype=np.float32)
    chunk_vec2[0] = 1.0

    # Dữ liệu 2 chunk mẫu trong DB
    row1 = MagicMock()
    row1.id = 1
    row1.document_id = 101
    row1.title = "Quy định chuẩn đầu ra ngoại ngữ và tin học"
    row1.chunk_index = 0
    row1.content = "Chuẩn đầu ra ngoại ngữ Tiếng Anh Bậc 3 TOEIC đạt tối thiểu 450 điểm."
    row1.embedding = chunk_vec1.tobytes()
    row1.section = "A.5.1"
    row1.so_hieu = "123/QĐ-ĐHLH"
    row1.url = "https://lhu.edu.vn"

    row2 = MagicMock()
    row2.id = 2
    row2.document_id = 102
    row2.title = "Hướng dẫn thủ tục hồ sơ tốt nghiệp"
    row2.chunk_index = 0
    row2.content = "Hồ sơ xét tốt nghiệp sinh viên nộp online tại graduate.lhu.edu.vn và nộp lệ phí 100.000 VNĐ."
    row2.embedding = chunk_vec2.tobytes()
    row2.section = "C"
    row2.so_hieu = "124/QĐ-ĐHLH"
    row2.url = "https://lhu.edu.vn"

    mock_db.execute.return_value.fetchall.return_value = [row1, row2]

    # Mock get_embeddings_batch trả về vector gần với row1
    with patch("backend.app.services.retrieval.get_embeddings_batch") as mock_embed:
        # Giả lập embedding trả về tương đồng cao với chunk_vec1 (0.8)
        query_vec = chunk_vec1.copy()
        mock_embed.return_value = [query_vec.tobytes(), query_vec.tobytes()]

        # Tìm kiếm câu không dấu Q12
        results = search_chunks(mock_db, "chuan dau ra tieng anh can bao nhieu diem toeic")
        assert len(results) > 0
        top_res = results[0]
        assert top_res["id"] == 1
        assert top_res["score"] >= 0.35  # Vượt ngưỡng SIMILARITY_THRESHOLD
        assert top_res["keyword_score"] > 0


def test_embedding_lru_cache():
    """Kiểm tra LRU cache của get_embedding và get_embeddings_batch không gọi lại Ollama khi lặp."""
    from backend.app.services.embedding import get_embedding, get_embeddings_batch, _EMBED_LRU_CACHE

    _EMBED_LRU_CACHE.clear()

    dummy_vec = np.zeros(1024, dtype=np.float32)
    dummy_vec[0] = 0.5
    dummy_bytes = dummy_vec.tobytes()

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embeddings": [dummy_vec.tolist()]}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        # Lần 1: Gọi embed câu hỏi
        emb1 = get_embedding("câu hỏi mẫu về học vụ")
        assert emb1 == dummy_bytes
        assert mock_post.call_count == 1

        # Lần 2: Gọi lại cùng câu hỏi -> phải lấy từ cache, không gọi thêm requests.post
        emb2 = get_embedding("câu hỏi mẫu về học vụ")
        assert emb2 == dummy_bytes
        assert mock_post.call_count == 1  # Vẫn là 1

        # Lần 3: Batch gồm câu cũ và câu mới
        mock_resp.json.return_value = {"embeddings": [dummy_vec.tolist()]}
        batch_res = get_embeddings_batch(["câu hỏi mẫu về học vụ", "câu hỏi mới tinh"])
        assert len(batch_res) == 2
        # Chỉ gọi post cho 1 câu mới
        assert mock_post.call_count == 2

