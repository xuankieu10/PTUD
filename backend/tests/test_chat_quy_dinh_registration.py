"""
backend/tests/test_chat_quy_dinh_registration.py
Kiểm thử các câu hỏi về Quy chế đào tạo mới và xử lý trễ hạn đăng ký:
1. Nhận diện và trả lời đúng quy định khi hỏi từ ngữ dân dã ("học vét", "bị cấm thi", "thi lại lần 2").
2. Xử lý câu hỏi hết hạn/quá hạn đăng ký môn học (Việc 3):
   - Hướng dẫn P. Đào tạo, theo dõi App ME/Zalo OA
   - Liên hệ trực tiếp Khoa CNTT (02513.952.251, cntt@lhu.edu.vn, phòng B301-B302 CS1)
   - Trích nguồn chuẩn: [Quy chế đào tạo, Chương II – Điều 10 / Chương V]
3. Kiểm tra logic check_deadline().
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.api import app
from backend.app.security import create_access_token
from backend.app.routers.chat import (
    check_deadline,
    is_registration_deadline_query,
    REGISTRATION_OVERDUE_RESPONSE,
    REGISTRATION_OVERDUE_SOURCES
)
from backend.app.services.retrieval import rewrite_query

client = TestClient(app)


def make_headers():
    token = create_access_token(subject=1, role="admin")
    return {"Authorization": f"Bearer {token}"}


def test_check_deadline():
    """Kiểm tra hàm check_deadline với các mốc thời gian."""
    now = datetime(2026, 11, 2, 10, 0, 0)
    past_deadline = now - timedelta(days=2)
    future_deadline = now + timedelta(days=2)

    # Đã quá hạn
    assert check_deadline(now=now, deadline=past_deadline) is True
    # Còn hạn
    assert check_deadline(now=now, deadline=future_deadline) is False
    # Không có deadline -> mặc định True
    assert check_deadline(now=now, deadline=None) is True


def test_is_registration_deadline_query():
    """Kiểm tra nhận diện câu hỏi quá hạn / hết hạn đăng ký."""
    assert is_registration_deadline_query("Tôi bị trễ hạn đăng ký môn học thì làm sao?") is True
    assert is_registration_deadline_query("Hết hạn đăng ký học phần rồi có đăng ký được không?") is True
    assert is_registration_deadline_query("Em bị quá hạn đăng ký học lại") is True
    assert is_registration_deadline_query("Thời hạn đăng ký môn học khi nào hết?") is True

    # Câu hỏi không liên quan đến hạn đăng ký
    assert is_registration_deadline_query("Thời khóa biểu tuần này") is False
    assert is_registration_deadline_query("Xin chào chatbot") is False


def test_chat_registration_overdue_endpoint():
    """Kiểm tra POST /chat khi hỏi về hết hạn đăng ký môn học."""
    headers = make_headers()
    res = client.post(
        "/chat",
        json={"message": "Tôi bị hết hạn đăng ký môn học thì phải làm sao?"},
        headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    ans = data["answer"]
    sources = data["sources"]

    # Kiểm tra nội dung hướng dẫn
    assert "Phòng Đào tạo" in ans
    assert "app me" in ans.lower()
    assert "zalo" in ans.lower()
    assert "02513.952.251" in ans
    assert "cntt@lhu.edu.vn" in ans
    assert "B301" in ans or "B302" in ans
    assert "Số 10 Huỳnh Văn Nghệ, Biên Hòa, Đồng Nai" in ans
    assert "[Văn bản quy định học vụ, Khoa Công nghệ thông tin – Hướng dẫn đăng ký học vụ]" in ans

    # Kiểm tra nguồn
    assert len(sources) > 0
    assert any("Hướng dẫn đăng ký học vụ" in s.get("section", "") for s in sources)

    # Dọn dẹp session test
    session_id = data.get("session_id")
    if session_id:
        from backend.app.db import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("DELETE FROM chat_messages WHERE session_id = :sid"), {"sid": session_id})
            db.execute(text("DELETE FROM chat_sessions WHERE id = :sid"), {"sid": session_id})
            db.commit()


def test_chat_registration_overdue_stream_endpoint():
    """Kiểm tra POST /chat/stream khi hỏi về trễ hạn đăng ký môn học."""
    headers = make_headers()
    res = client.post(
        "/chat/stream",
        json={"message": "Em bị trễ hạn đăng ký học phần, có xin được không?"},
        headers=headers
    )
    assert res.status_code == 200
    body = res.text

    assert "02513.952.251" in body
    assert "cntt@lhu.edu.vn" in body
    assert "app me" in body.lower()
    assert "zalo" in body.lower()
    assert "Hướng dẫn đăng ký học vụ" in body

    # Dọn dẹp session từ stream
    import json
    session_id = None
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                if data.get("session_id"):
                    session_id = data["session_id"]
                    break
            except Exception:
                pass
    if session_id:
        from backend.app.db import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("DELETE FROM chat_messages WHERE session_id = :sid"), {"sid": session_id})
            db.execute(text("DELETE FROM chat_sessions WHERE id = :sid"), {"sid": session_id})
            db.commit()


def test_synonyms_expansion_for_hoc_vet_and_cam_thi():
    """Kiểm tra mở rộng từ đồng nghĩa với các từ dân dã mới bổ sung."""
    exp1 = rewrite_query("học vét là gì")
    assert "học lại" in exp1 or "học phần bắt buộc" in exp1

    exp2 = rewrite_query("em bị cấm thi môn toán")
    assert "vắng quá 20%" in exp2 or "2.0" in exp2

    exp3 = rewrite_query("thi lại lần 2 vào khi nào")
    assert "thi lại" in exp3 or "chuyên cần" in exp3
