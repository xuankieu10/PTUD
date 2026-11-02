import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.api import app
from backend.app.security import create_access_token
from backend.app.prompts import FACULTY_NOT_SUPPORTED_RESPONSE

client = TestClient(app)

def make_headers():
    token = create_access_token(subject=1, role="admin")
    return {"Authorization": f"Bearer {token}"}

# 7 câu hỏi hợp lệ (kỳ vọng không bị chặn)
VALID_ACADEMIC_QUERIES = [
    "khoa cong nghe thong tin duoc xet tot nghiep som khong",
    "sinh vien duoc mien thi tin hoc khi nao",
    "dieu kien de duoc cap bang tot nghiep la gi",
    "toi duoc nhan giay chung nhan hoan thanh khong",
    "khoa cntt duoc to chuc sat hach tin hoc khong",
    "Sinh viên Khoa CNTT được miễn ngoại ngữ khi nào?",
    "luat nao quy dinh chuan dau ra",
    # Bổ sung câu A1 từng bị false positive
    "Sinh viên bị kỷ luật cảnh cáo có được xét tốt nghiệp không?",
]

# 4 câu cần chặn (kỳ vọng phải bị chặn do hỏi khoa/ngành khác)
BLOCKED_FACULTY_QUERIES = [
    "dieu kien tot nghiep khoa duoc la gi",
    "Điều kiện tốt nghiệp của sinh viên Khoa Dược là gì?",
    "khoa luat yeu cau chuan dau ra ngoai ngu nhu the nao",
    "Khoa Luật yêu cầu chuẩn đầu ra ngoại ngữ như thế nào?",
]

@pytest.mark.parametrize("query", VALID_ACADEMIC_QUERIES)
@patch("backend.app.routers.chat.search_chunks")
@patch("backend.app.routers.chat._call_ollama")
def test_guardrail_false_positive_allowed(mock_call_ollama, mock_search, query):
    """Kiểm tra các câu hỏi học vụ hợp lệ KHÔNG bị chặn nhầm bởi guardrail."""
    mock_search.return_value = [
        {"document_id": 1, "title": "Quy chế học vụ", "chunk_index": 0, "score": 0.9, "content": "Quy định chi tiết"}
    ]
    mock_call_ollama.return_value = "Câu trả lời tư vấn học vụ hợp lệ."

    headers = make_headers()
    res = client.post("/chat", json={"message": query}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] != FACULTY_NOT_SUPPORTED_RESPONSE
    assert "Khoa Công nghệ Thông tin" not in data["answer"] or "chỉ hỗ trợ" not in data["answer"]

@pytest.mark.parametrize("query", BLOCKED_FACULTY_QUERIES)
@patch("backend.app.routers.chat.search_chunks")
@patch("backend.app.routers.chat._call_ollama")
def test_guardrail_other_faculty_blocked(mock_call_ollama, mock_search, query):
    """Kiểm tra các câu hỏi về Khoa khác (Dược, Luật) PHẢI bị guardrail chặn chuẩn xác."""
    mock_search.return_value = []
    headers = make_headers()
    res = client.post("/chat", json={"message": query}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == FACULTY_NOT_SUPPORTED_RESPONSE
    mock_call_ollama.assert_not_called()

