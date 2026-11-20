import pytest
from unittest.mock import patch, MagicMock
from backend.app.services.query_rewriter import (
    needs_rewriting,
    rewrite_academic_query
)

def test_needs_rewriting():
    history = [
        {"role": "user", "content": "Em bị rớt môn Cấu trúc dữ liệu"},
        {"role": "assistant", "content": "Bạn cần đăng ký học lại."}
    ]

    # Câu hỏi mơ hồ hoặc có trigger từ khóa phụ thuộc ngữ cảnh
    assert needs_rewriting("còn môn đó thì sao?", history) is True
    assert needs_rewriting("khi nào mở?", history) is True
    assert needs_rewriting("thế còn tiếng anh thì sao", history) is True
    assert needs_rewriting("môn này tiên quyết là gì", history) is True
    assert needs_rewriting("bao nhiêu tín chỉ?", history) is True

    # Khi không có lịch sử -> luôn False (không rewrite)
    assert needs_rewriting("còn môn đó thì sao?", []) is False
    assert needs_rewriting("khi nào mở?", None) is False

    # Câu hỏi dài độc lập (> 25 từ) và không có trigger -> False
    long_independent_query = (
        "Xin chào thầy cô, em muốn hỏi về quy trình xét tốt nghiệp đợt tháng 6 năm 2025 "
        "dành cho sinh viên khóa 2021 ngành Công nghệ thông tin theo quy chế đào tạo tín chỉ hiện hành của trường Đại học Lạc Hồng."
    )
    assert needs_rewriting(long_independent_query, history) is False

    # Câu rỗng -> False
    assert needs_rewriting("", history) is False


def test_rewrite_skipped_when_no_history():
    # Không có lịch sử -> giữ nguyên câu hỏi gốc
    q = "còn môn đó thì sao?"
    res = rewrite_academic_query(q, history=[])
    assert res == q

    res_none = rewrite_academic_query(q, history=None)
    assert res_none == q


def test_rewrite_skipped_when_query_already_complete():
    # Câu hỏi dài độc lập (> 25 từ) -> bỏ qua rewriter dù có lịch sử
    long_q = (
        "Xin chào thầy cô, em muốn hỏi về quy trình xét tốt nghiệp đợt tháng 6 năm 2025 "
        "dành cho sinh viên khóa 2021 ngành Công nghệ thông tin theo quy chế đào tạo tín chỉ hiện hành của trường Đại học Lạc Hồng."
    )
    hist = [
        {"role": "user", "content": "Em bị điểm F môn Giải tích"},
        {"role": "assistant", "content": "Bạn cần đăng ký học lại..."}
    ]
    res = rewrite_academic_query(long_q, history=hist)
    assert res == long_q


@patch("backend.app.services.query_rewriter.requests.post")
def test_rewrite_calls_llm_when_ambiguous_with_history(mock_post):
    # Mock LLM response từ Ollama /api/generate
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "Môn Cấu trúc dữ liệu và giải thuật khi nào mở lớp học lại?"
    }
    mock_post.return_value = mock_response

    hist = [
        {"role": "user", "content": "Em bị rớt môn Cấu trúc dữ liệu và giải thuật"},
        {"role": "assistant", "content": "Bạn nợ 3 tín chỉ môn này, cần học lại để đủ điều kiện tốt nghiệp."}
    ]
    ambiguous_q = "khi nào mở lớp lại?"

    res = rewrite_academic_query(ambiguous_q, history=hist)
    assert "Cấu trúc dữ liệu" in res
    assert mock_post.called


@patch("backend.app.services.query_rewriter.requests.post")
def test_rewrite_fallback_to_original_on_error(mock_post):
    # Mock LLM failure (e.g. timeout / connection error)
    mock_post.side_effect = Exception("Ollama connection refused")

    hist = [
        {"role": "user", "content": "Em nợ môn Cơ sở dữ liệu"},
        {"role": "assistant", "content": "Bạn cần học lại."}
    ]
    ambiguous_q = "còn môn đó thì sao?"

    res = rewrite_academic_query(ambiguous_q, history=hist)
    assert res == ambiguous_q
