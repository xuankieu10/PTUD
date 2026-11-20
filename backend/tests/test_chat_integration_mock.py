"""
backend/tests/test_chat_integration_mock.py
Test tích hợp cho hàm endpoint chat() với Ollama giả (mock), KHÔNG cần SQL Server thật.

Kiểm thử 5 kịch bản chính:
1. Có hồ sơ + câu hỏi tốt nghiệp -> Phản hồi bắt buộc đủ 4 phần chuẩn Cố vấn học vụ, có số liệu chính xác từ code (6/150, GPA, môn nợ).
2. Có hồ sơ (has_ocr=True) nhưng câu hỏi khác (học phí, lịch thi) -> Trả lời tra cứu thông thường, KHÔNG ép 4 phần.
3. Khi LLM chạm giới hạn độ dài (done_reason='length') -> Tự động dùng bản dựng sẵn của code, loại bỏ đoạn cắt cụt ("- Thiếu").
4. Cấu hình ADVISORY_USE_LLM=False -> Trả thẳng bản dựng sẵn của code mà không gọi LLM (tiết kiệm 100% VRAM).
5. Chống ảo giác: Khi LLM trả số bịa (vd "đã đạt 120/150") -> Kết quả cuối dùng số chuẩn của code (6/150).
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.routers.chat import chat, ChatRequest


class MockDbRow:
    """Giả lập row trả về từ SQLAlchemy fetchone()"""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def create_mock_db(has_ocr=True, has_student=True):
    mock_db = MagicMock(spec=Session)

    # Dữ liệu bảng điểm OCR mẫu: 4 môn (2 môn nợ điểm < 4.0, 2 môn đạt 3 TC mỗi môn = 6 TC tích lũy)
    ocr_courses = [
        {"ma_mon": "CS101", "ten_mon": "Nhập môn lập trình", "tin_chi": 3, "diem": 3.0, "is_failed": True},
        {"ma_mon": "MATH101", "ten_mon": "Toán cao cấp 1", "tin_chi": 4, "diem": 3.5, "is_failed": True},
        {"ma_mon": "ENG1", "ten_mon": "English 1", "tin_chi": 3, "diem": 7.0, "is_failed": False},
        {"ma_mon": "CS202", "ten_mon": "Cơ sở dữ liệu", "tin_chi": 3, "diem": 8.0, "is_failed": False},
    ]

    ocr_row = MockDbRow(
        id=101,
        filename="bang_diem_test.pdf",
        total_subjects=4,
        passed_count=2,
        failed_count=2,
        courses_data=json.dumps(ocr_courses, ensure_ascii=False),
        summary_text="Đọc được 4 môn, 2 môn nợ",
        created_at="2026-11-19"
    )

    student_row = MockDbRow(
        id=1,
        user_id=1,
        student_code="12100123",
        full_name="Nguyễn Văn Test",
        major="Công nghệ thông tin",
        cohort="2021"
    )

    def execute_side_effect(statement, params=None):
        sql = str(statement).lower()
        mock_result = MagicMock()

        if "chat_sessions" in sql:
            mock_result.fetchone.return_value = MockDbRow(id=1, user_id=1)
            mock_result.scalar.return_value = 1
        elif "student_ocr_transcripts" in sql:
            mock_result.fetchone.return_value = ocr_row if has_ocr else None
        elif "from students" in sql:
            mock_result.fetchone.return_value = student_row if has_student else None
        elif "chat_messages" in sql:
            mock_result.fetchall.return_value = []
            mock_result.fetchone.return_value = None
            mock_result.scalar.return_value = 1
        elif "curriculum" in sql or "subjects" in sql:
            mock_result.fetchall.return_value = []
        else:
            mock_result.fetchone.return_value = None
            mock_result.fetchall.return_value = []
            mock_result.scalar.return_value = None

        return mock_result

    mock_db.execute.side_effect = execute_side_effect
    return mock_db


def make_mock_call_ollama(text: str, done_reason: str = "stop"):
    """
    Giả lập đúng 100% kiểu trả về của hàm thật _call_ollama:
    - Khi return_done_reason=True: trả về Tuple[str, str] (text, done_reason)
    - Khi return_done_reason=False (mặc định): trả về str (text)
    """
    def _fake(messages, timeout=None, options=None, return_done_reason=False):
        if return_done_reason:
            return text, done_reason
        return text
    return _fake


@patch("backend.app.routers.chat.search_chunks")
@patch("backend.app.routers.chat._call_ollama")
def test_chat_graduation_query_has_4_sections(mock_ollama, mock_search, monkeypatch):
    """Case 1: Có hồ sơ sinh viên + hỏi tốt nghiệp -> Phản hồi đủ 4 phần + đúng số liệu từ code (6/150, GPA, môn nợ)"""
    monkeypatch.setattr(settings, "ADVISORY_USE_LLM", True)
    mock_db = create_mock_db(has_ocr=True)
    mock_search.return_value = [
        {"document_id": 1, "title": "Quy chế đào tạo", "section": "11", "chunk_index": 0, "score": 0.85, "content": "Điều kiện tốt nghiệp tích lũy 150 tín chỉ", "url": None, "so_hieu": "79/QĐ-ĐHLH"}
    ]

    llm_advisory_text = (
        "Chào bạn, dưới đây là tư vấn lộ trình học tập của bạn:\n\n"
        "### 1. TÌNH TRẠNG HIỆN TẠI\n"
        "- Tín chỉ tích lũy: Đã đạt 6/150 tín chỉ.\n"
        "- Điểm GPA: 7.50 (thang 10).\n\n"
        "### 2. CÒN THIẾU GÌ\n"
        "- Còn thiếu 144 tín chỉ.\n"
        "- Môn nợ: Nhập môn lập trình (3 TC), Toán cao cấp 1 (4 TC).\n\n"
        "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT\n"
        "+ Học kỳ hè: Học lại Nhập môn lập trình và Toán cao cấp 1.\n"
        "+ Học kỳ 3: Đăng ký Kỹ thuật lập trình và các môn cơ sở ngành.\n\n"
        "### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ\n"
        "- Rủi ro: Nhập môn lập trình là môn tiên quyết.\n"
        "- Hành động: Đăng ký đợt học hè trên cổng https://dkmh.lhu.edu.vn."
    )
    mock_ollama.side_effect = make_mock_call_ollama(llm_advisory_text, "stop")

    req = ChatRequest(message="Em còn thiếu môn gì và cần học thế nào để tốt nghiệp đúng hạn?", session_id=1)
    res = chat(req, db=mock_db, current_user={"id": 1, "username": "test_user"})

    ans = res["answer"]
    # 1. Đủ 4 phần
    assert "### 1. TÌNH TRẠNG HIỆN TẠI" in ans
    assert "### 2. CÒN THIẾU GÌ" in ans
    assert "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT" in ans
    assert "### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ" in ans

    # 2. Assert các con số thực tế từ code tính toán
    assert "6/150" in ans
    assert "7.5" in ans
    assert "Nhập môn lập trình" in ans
    assert "Toán cao cấp 1" in ans


@patch("backend.app.routers.chat.search_chunks")
@patch("backend.app.routers.chat._call_ollama")
def test_chat_non_graduation_query_no_4_sections(mock_ollama, mock_search, monkeypatch):
    """Case 2: Có hồ sơ (has_ocr=True) nhưng hỏi quy chế khác (học phí) -> Không ép cấu trúc 4 phần"""
    monkeypatch.setattr(settings, "ADVISORY_USE_LLM", True)
    mock_db = create_mock_db(has_ocr=True)
    mock_search.return_value = [
        {"document_id": 2, "title": "Thông báo học phí", "section": "Học phí", "chunk_index": 0, "score": 0.88, "content": "Học phí môn kỹ năng mềm là 500.000đ/môn.", "url": None, "so_hieu": "TB-01"}
    ]

    llm_normal_text = "Theo quy định của Trường Đại học Lạc Hồng, mức học phí đối với các học phần kỹ năng mềm là 500.000 VNĐ/học phần."
    mock_ollama.side_effect = make_mock_call_ollama(llm_normal_text, "stop")

    req = ChatRequest(message="Mức học phí môn kỹ năng mềm của trường là bao nhiêu?", session_id=1)
    res = chat(req, db=mock_db, current_user={"id": 1, "username": "test_user"})

    ans = res["answer"]
    # Câu hỏi tra cứu quy chế thông thường KHÔNG ép 4 phần
    assert "### 1. TÌNH TRẠNG HIỆN TẠI" not in ans
    assert "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT" not in ans
    assert "500.000" in ans


@patch("backend.app.routers.chat.search_chunks")
@patch("backend.app.routers.chat._call_ollama")
def test_chat_graduation_query_done_reason_length_fallback(mock_ollama, mock_search, monkeypatch):
    """Case 3: Khi LLM bị cắt lửng lơ (done_reason='length') -> Tự động fallback sang bản dựng sẵn của code"""
    monkeypatch.setattr(settings, "ADVISORY_USE_LLM", True)
    mock_db = create_mock_db(has_ocr=True)
    mock_search.return_value = [
        {"document_id": 1, "title": "Quy chế đào tạo", "section": "11", "chunk_index": 0, "score": 0.85, "content": "150 tín chỉ", "url": None, "so_hieu": "79"}
    ]

    # Giả lập LLM sinh nửa chừng rồi bị cắt ngắn do hit max token limit
    truncated_llm_text = "Chào bạn, tình trạng của bạn là:\n### 1. TÌNH TRẠNG HIỆN TẠI\n- Tín chỉ: 6/150\n### 2. CÒN THIẾU GÌ\n- Thiếu"
    mock_ollama.side_effect = make_mock_call_ollama(truncated_llm_text, "length")

    req = ChatRequest(message="Kiểm tra tốt nghiệp cho em và lập kế hoạch giúp em với", session_id=1)
    res = chat(req, db=mock_db, current_user={"id": 1, "username": "test_user"})

    ans = res["answer"]
    # Khẳng định câu trả lời không bị lửng lơ mà là bản hoàn chỉnh đủ 4 phần do code dựng sẵn
    assert "### 1. TÌNH TRẠNG HIỆN TẠI" in ans
    assert "### 2. CÒN THIẾU GÌ" in ans
    assert "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT" in ans
    assert "### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ" in ans

    # Khẳng định đoạn cắt cụt '- Thiếu' KHÔNG còn tồn tại trong kết quả
    assert "- Thiếu" not in ans

    # Assert đúng số liệu và môn nợ từ code
    assert "6/150" in ans
    assert "Nhập môn lập trình" in ans
    assert "Toán cao cấp 1" in ans


@patch("backend.app.routers.chat.search_chunks")
@patch("backend.app.routers.chat._call_ollama")
def test_chat_graduation_query_advisory_use_llm_false(mock_ollama, mock_search, monkeypatch):
    """Case 4: Cấu hình ADVISORY_USE_LLM=False -> Trả thẳng bản dựng sẵn từ code, KHÔNG gọi LLM"""
    monkeypatch.setattr(settings, "ADVISORY_USE_LLM", False)
    mock_db = create_mock_db(has_ocr=True)
    mock_search.return_value = [
        {"document_id": 1, "title": "Quy chế đào tạo", "section": "11", "chunk_index": 0, "score": 0.85, "content": "150 tín chỉ", "url": None, "so_hieu": "79"}
    ]

    req = ChatRequest(message="Kiểm tra tốt nghiệp cho em và lập kế hoạch giúp em với", session_id=1)
    res = chat(req, db=mock_db, current_user={"id": 1, "username": "test_user"})

    # Khẳng định _call_ollama không hề bị gọi
    mock_ollama.assert_not_called()

    ans = res["answer"]
    assert "### 1. TÌNH TRẠNG HIỆN TẠI" in ans
    assert "### 2. CÒN THIẾU GÌ" in ans
    assert "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT" in ans
    assert "### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ" in ans
    assert "6/150" in ans
    assert "Nhập môn lập trình" in ans
    assert "Toán cao cấp 1" in ans


@patch("backend.app.routers.chat.search_chunks")
@patch("backend.app.routers.chat._call_ollama")
def test_chat_graduation_query_hallucinated_credits_fallback_to_code(mock_ollama, mock_search, monkeypatch):
    """Case 5: Chống ảo giác - Khi LLM trả số bịa (vd 'đã đạt 120/150') -> Kết quả cuối dùng số chuẩn từ code (6/150)"""
    monkeypatch.setattr(settings, "ADVISORY_USE_LLM", True)
    mock_db = create_mock_db(has_ocr=True)
    mock_search.return_value = [
        {"document_id": 1, "title": "Quy chế đào tạo", "section": "11", "chunk_index": 0, "score": 0.85, "content": "150 tín chỉ", "url": None, "so_hieu": "79"}
    ]

    # Giả lập LLM sinh ảo giác con số đã tích lũy (bịa 120/150 trong khi thực tế chỉ 6/150)
    hallucinated_llm_text = (
        "Chào bạn, kết quả học vụ của bạn:\n\n"
        "### 1. TÌNH TRẠNG HIỆN TẠI\n"
        "- Tín chỉ tích lũy: Đã đạt 120/150 tín chỉ.\n"
        "- Điểm GPA: 9.90 (thang 10).\n\n"
        "### 2. CÒN THIẾU GÌ\n"
        "- Còn thiếu 30 tín chỉ.\n\n"
        "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT\n"
        "+ Học kỳ tới: Đăng ký môn tốt nghiệp.\n\n"
        "### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ\n"
        "- Rủi ro: Không có.\n"
        "- Hành động: Chuẩn bị nhận bằng tốt nghiệp."
    )
    mock_ollama.side_effect = make_mock_call_ollama(hallucinated_llm_text, "stop")

    req = ChatRequest(message="Em còn thiếu môn gì và cần học thế nào để tốt nghiệp đúng hạn?", session_id=1)
    res = chat(req, db=mock_db, current_user={"id": 1, "username": "test_user"})

    ans = res["answer"]
    # Khẳng định câu trả lời KHÔNG chứa con số bịa 120/150
    assert "120/150" not in ans

    # Thay vào đó, kết quả cuối cùng tự động phục hồi về số đúng của code
    assert "### 1. TÌNH TRẠNG HIỆN TẠI" in ans
    assert "### 2. CÒN THIẾU GÌ" in ans
    assert "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT" in ans
    assert "### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ" in ans
    assert "6/150" in ans
    assert "Nhập môn lập trình" in ans
    assert "Toán cao cấp 1" in ans


@patch("backend.app.routers.chat.search_chunks")
@patch("backend.app.routers.chat._call_ollama")
def test_chat_graduation_query_hallucinated_gpa_fallback_to_code(mock_ollama, mock_search, monkeypatch):
    """Case 6: Chống ảo giác - LLM bịa điểm GPA (vd 'GPA 9.90') -> Fallback bản dựng sẵn chuẩn từ code (GPA 7.50)"""
    monkeypatch.setattr(settings, "ADVISORY_USE_LLM", True)
    mock_db = create_mock_db(has_ocr=True)
    mock_search.return_value = [
        {"document_id": 1, "title": "Quy chế đào tạo", "section": "11", "chunk_index": 0, "score": 0.85, "content": "150 tín chỉ", "url": None, "so_hieu": "79"}
    ]

    hallucinated_gpa_text = (
        "### 1. TÌNH TRẠNG HIỆN TẠI\n"
        "- Tín chỉ tích lũy: Đã đạt 6/150 tín chỉ.\n"
        "- Điểm GPA: 9.90 (thang 10).\n\n"
        "### 2. CÒN THIẾU GÌ\n"
        "- Còn thiếu 144 tín chỉ.\n"
        "- Môn nợ: Nhập môn lập trình, Toán cao cấp 1.\n\n"
        "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT\n"
        "+ Học kỳ hè: Đăng ký học lại.\n\n"
        "### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ\n"
        "- Hành động: Đăng ký học phần."
    )
    mock_ollama.side_effect = make_mock_call_ollama(hallucinated_gpa_text, "stop")

    req = ChatRequest(message="Em còn thiếu môn gì và cần học thế nào để tốt nghiệp đúng hạn?", session_id=1)
    res = chat(req, db=mock_db, current_user={"id": 1, "username": "test_user"})

    ans = res["answer"]
    # Điểm GPA bịa 9.90 bị loại bỏ
    assert "9.9" not in ans
    # Kết quả dùng điểm GPA chuẩn từ code (7.5)
    assert "7.5" in ans
    assert "6/150" in ans


@patch("backend.app.routers.chat.search_chunks")
@patch("backend.app.routers.chat._call_ollama")
def test_chat_graduation_query_hallucinated_missing_credits_fallback_to_code(mock_ollama, mock_search, monkeypatch):
    """Case 7: Chống ảo giác - LLM bịa số tín chỉ còn thiếu (vd 'còn thiếu 50 tín chỉ') -> Fallback bản dựng sẵn (144 tín chỉ)"""
    monkeypatch.setattr(settings, "ADVISORY_USE_LLM", True)
    mock_db = create_mock_db(has_ocr=True)
    mock_search.return_value = [
        {"document_id": 1, "title": "Quy chế đào tạo", "section": "11", "chunk_index": 0, "score": 0.85, "content": "150 tín chỉ", "url": None, "so_hieu": "79"}
    ]

    hallucinated_missing_text = (
        "### 1. TÌNH TRẠNG HIỆN TẠI\n"
        "- Tín chỉ tích lũy: Đã đạt 6/150 tín chỉ.\n"
        "- Điểm GPA: 7.50 (thang 10).\n\n"
        "### 2. CÒN THIẾU GÌ\n"
        "- Còn thiếu 50 tín chỉ.\n"
        "- Môn nợ: Nhập môn lập trình, Toán cao cấp 1.\n\n"
        "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT\n"
        "+ Học kỳ hè: Đăng ký học lại.\n\n"
        "### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ\n"
        "- Hành động: Đăng ký học phần."
    )
    mock_ollama.side_effect = make_mock_call_ollama(hallucinated_missing_text, "stop")

    req = ChatRequest(message="Em còn thiếu môn gì và cần học thế nào để tốt nghiệp đúng hạn?", session_id=1)
    res = chat(req, db=mock_db, current_user={"id": 1, "username": "test_user"})

    ans = res["answer"]
    # Số tín chỉ bịa '50' bị loại bỏ (không nhầm với số 150)
    import re
    assert re.search(r"\b50\b", ans) is None
    # Kết quả dùng số chuẩn từ code (144 tín chỉ)
    assert "144" in ans


@patch("backend.app.routers.chat.search_chunks")
@patch("backend.app.routers.chat._call_ollama")
def test_chat_graduation_query_hallucinated_failed_courses_count_fallback_to_code(mock_ollama, mock_search, monkeypatch):
    """Case 8: Chống ảo giác - LLM bịa số môn nợ (vd 'nợ 10 môn') -> Fallback bản dựng sẵn (2 môn nợ)"""
    monkeypatch.setattr(settings, "ADVISORY_USE_LLM", True)
    mock_db = create_mock_db(has_ocr=True)
    mock_search.return_value = [
        {"document_id": 1, "title": "Quy chế đào tạo", "section": "11", "chunk_index": 0, "score": 0.85, "content": "150 tín chỉ", "url": None, "so_hieu": "79"}
    ]

    hallucinated_failed_text = (
        "### 1. TÌNH TRẠNG HIỆN TẠI\n"
        "- Tín chỉ tích lũy: Đã đạt 6/150 tín chỉ.\n"
        "- Điểm GPA: 7.50 (thang 10).\n\n"
        "### 2. CÒN THIẾU GÌ\n"
        "- Tín chỉ còn thiếu: 144 tín chỉ.\n"
        "- Môn chưa đạt: Bạn đang nợ 10 môn học.\n\n"
        "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT\n"
        "+ Học kỳ hè: Đăng ký học lại.\n\n"
        "### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ\n"
        "- Hành động: Đăng ký học phần."
    )
    mock_ollama.side_effect = make_mock_call_ollama(hallucinated_failed_text, "stop")

    req = ChatRequest(message="Em còn thiếu môn gì và cần học thế nào để tốt nghiệp đúng hạn?", session_id=1)
    res = chat(req, db=mock_db, current_user={"id": 1, "username": "test_user"})

    ans = res["answer"]
    # Số môn nợ bịa '10 môn' bị loại bỏ
    assert "10 môn" not in ans
    # Kết quả phục hồi chính xác 2 môn nợ từ code
    assert "2 môn" in ans
    assert "Nhập môn lập trình" in ans
    assert "Toán cao cấp 1" in ans


@patch("backend.app.routers.chat.search_chunks")
@patch("backend.app.routers.chat._call_ollama")
def test_chat_graduation_query_valid_qd22_citation_not_fallback(mock_ollama, mock_search, monkeypatch):
    """
    Test Item 2(e): Câu trả lời đúng có trích dẫn 'QĐ 22' (lấy từ chunk RAG) KHÔNG bị coi là số lạ,
    KHÔNG bị fallback oan, giữ nguyên câu trả lời diễn đạt mượt mà của LLM.
    """
    monkeypatch.setattr(settings, "ADVISORY_USE_LLM", True)
    mock_db = create_mock_db(has_ocr=True)
    # RAG chunk chứa số hiệu văn bản thật: QĐ 22/QĐ-ĐHLH
    mock_search.return_value = [
        {
            "document_id": 1,
            "title": "Quy chế đào tạo LHU",
            "section": "11",
            "chunk_index": 0,
            "score": 0.85,
            "content": "Điều kiện tốt nghiệp theo QĐ 22/QĐ-ĐHLH cần 150 tín chỉ",
            "url": None,
            "so_hieu": "QĐ 22/QĐ-ĐHLH"
        }
    ]

    valid_llm_text = (
        "### 1. TÌNH TRẠNG HIỆN TẠI\n"
        "- Tín chỉ tích lũy: Đã đạt 6/150 tín chỉ theo quy định tại QĐ 22 của Trường Đại học Lạc Hồng.\n"
        "- Điểm trung bình tích lũy (GPA): 7.50 (thang 10) tương đương 3.0 (thang 4).\n"
        "- Điều kiện / chứng chỉ đã đạt: Chưa có dữ liệu chứng chỉ nào được ghi nhận.\n\n"
        "### 2. CÒN THIẾU GÌ\n"
        "- Tín chỉ còn thiếu: Cần tích lũy thêm ít nhất 144 tín chỉ để đủ 150 tín chỉ.\n"
        "- Môn chưa đạt / nợ điểm (2 môn cần học lại/thi lại): Nhập môn lập trình (CS101, 3 TC, điểm: 3.0); Toán cao cấp 1 (MATH101, 4 TC, điểm: 3.5).\n\n"
        "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT\n"
        "+ Học kỳ hè: Đăng ký học lại 2 môn nợ.\n\n"
        "### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ\n"
        "- Hành động cụ thể: Đăng ký học phần theo thông báo của Phòng Đào tạo."
    )
    mock_ollama.side_effect = make_mock_call_ollama(valid_llm_text, "stop")

    req = ChatRequest(message="Em còn thiếu môn gì và cần học thế nào để tốt nghiệp đúng hạn?", session_id=1)
    res = chat(req, db=mock_db, current_user={"id": 1, "username": "test_user"})

    ans = res["answer"]
    # Không bị fallback oan về bản dựng sẵn, giữ nguyên trích dẫn QĐ 22 của LLM
    assert "QĐ 22" in ans
    assert "theo quy định tại QĐ 22 của Trường Đại học Lạc Hồng" in ans


@patch("backend.app.routers.chat.search_chunks")
@patch("backend.app.routers.chat._call_ollama")
def test_chat_graduation_query_hallucinated_number_8_mon_triggers_fallback(mock_ollama, mock_search, monkeypatch):
    """
    Test Item 2(e): Câu trả lời của LLM có số lạ 'đã học 8 môn' (khi whitelist đã thu hẹp,
    bỏ bare số 8) -> Phát hiện số lạ/bịa ngoài ngữ cảnh -> Tự động fallback về bản dựng sẵn của code.
    """
    monkeypatch.setattr(settings, "ADVISORY_USE_LLM", True)
    mock_db = create_mock_db(has_ocr=True)
    mock_search.return_value = [
        {
            "document_id": 1,
            "title": "Quy chế đào tạo LHU",
            "section": "11",
            "chunk_index": 0,
            "score": 0.85,
            "content": "Điều kiện tốt nghiệp 150 tín chỉ",
            "url": None,
            "so_hieu": "QĐ 22/QĐ-ĐHLH"
        }
    ]

    # LLM bịa số lạ 'đã học 8 môn' (trong khi hồ sơ chỉ có 4 môn, 2 môn đạt)
    hallucinated_llm_text = (
        "### 1. TÌNH TRẠNG HIỆN TẠI\n"
        "- Tín chỉ tích lũy: Bạn đã học 8 môn và đạt 6/150 tín chỉ.\n"
        "- Điểm trung bình tích lũy (GPA): 7.5 (thang 10) tương đương 3.0 (thang 4).\n"
        "- Điều kiện / chứng chỉ đã đạt: Chưa có dữ liệu chứng chỉ nào được ghi nhận.\n\n"
        "### 2. CÒN THIẾU GÌ\n"
        "- Tín chỉ còn thiếu: Cần tích lũy thêm ít nhất 144 tín chỉ để đủ 150 tín chỉ.\n"
        "- Môn chưa đạt / nợ điểm (2 môn cần học lại/thi lại): Nhập môn lập trình, Toán cao cấp 1.\n\n"
        "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT\n"
        "+ Học kỳ hè: Đăng ký học lại.\n\n"
        "### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ\n"
        "- Hành động: Đăng ký học phần theo cổng dkmh.lhu.edu.vn."
    )
    mock_ollama.side_effect = make_mock_call_ollama(hallucinated_llm_text, "stop")

    req = ChatRequest(message="Em còn thiếu môn gì và cần học thế nào để tốt nghiệp đúng hạn?", session_id=1)
    res = chat(req, db=mock_db, current_user={"id": 1, "username": "test_user"})

    ans = res["answer"]
    # Số lạ bịa '8 môn' bị loại bỏ do kích hoạt fallback về bản dựng sẵn từ code
    import re
    assert re.search(r"(?<!\d)8\s*môn", ans) is None
    assert "đã học 8 môn" not in ans
    # Bản dựng sẵn từ code không bao giờ có cụm '8 môn' này
    assert "Đã đạt 6/150 tín chỉ" in ans
