"""
backend/tests/test_ingest_quy_dinh.py
Kiểm thử nạp văn bản quy định đào tạo vào RAG:
1. Phân tách đầy đủ 16 chunk quy định từ file văn_bản_quy_định.docx.
2. Lọc bỏ các URL chuyển hướng google.com rác.
3. Tính idempotent của script ingest_quy_dinh (chạy nhiều lần không gây duplicate chunk trong DB).
"""

import os
import pytest
from sqlalchemy import text
from backend.app.db import engine
from backend.scripts.ingest_quy_dinh import (
    find_docx_file,
    parse_docx_chunks,
    clean_google_urls,
    ingest_quy_dinh,
    DOCUMENT_ID_QUY_DINH
)


def test_clean_google_urls():
    """Đảm bảo loại bỏ các liên kết google.com/url rác."""
    sample_text = "Xem hướng dẫn tại https://www.google.com/url?q=https://example.com/guide và nộp biểu mẫu."
    cleaned = clean_google_urls(sample_text)
    assert "google.com/url" not in cleaned
    assert "Xem hướng dẫn tại" in cleaned
    assert "và nộp biểu mẫu." in cleaned


def test_parse_docx_all_16_chunks():
    """Đọc tệp docx và kiểm tra cấu trúc 17 chunks chuẩn hóa từ văn bản hợp nhất."""
    docx_path = find_docx_file()
    assert os.path.exists(docx_path)

    chunks = parse_docx_chunks(docx_path)
    assert len(chunks) == 17, f"Mong đợi 17 chunks nhưng nhận được {len(chunks)}"

    # Kiểm tra các mục quan trọng theo yêu cầu đề bài
    sections = [c["section"] for c in chunks]
    sources = [c["source"] for c in chunks]
    contents = " ".join([c["content"] for c in chunks])

    # 1. Điều 15: Xét tốt nghiệp (150 tín chỉ, 8 học kỳ, Mác-Lênin, GDQP, GDTC)
    assert any("Điều 15" in s for s in sections)
    assert "150 tín chỉ" in contents
    assert "Mác-Lênin" in contents

    # 2. Điều 19: Cấm thi (vắng quá 20%, điểm thành phần dưới 2.0)
    assert any("Điều 19" in s for s in sections)
    assert "quá 20%" in contents
    assert "2,0" in contents or "2.0" in contents

    # 3. Điều 12: Quy định học lại
    assert any("Điều 12" in s for s in sections)

    # 4. Cải thiện điểm
    assert any("Cải thiện điểm" in s for s in sections)

    # 5. Cảnh báo học vụ và dừng học
    assert any("Cảnh báo học vụ" in s for s in sections)

    # 6. Đăng ký học lại / học vét (Link form, link Zalo)
    assert any("Hướng dẫn đăng ký" in s for s in sections)
    assert "https://forms.gle/" in contents
    assert "https://zalo.me/g/" in contents

    # 7. Thi lại lần 2, thời hạn nộp chứng chỉ tiếng Anh (trước ngày xét tốt nghiệp tối thiểu 1 tháng)
    assert "thi lại lần 2" in contents.lower()
    assert "1 tháng" in contents

    # 8. Mẫu email xin hỗ trợ, lệ phí thi lại, học phí kỹ năng mềm
    assert "cntt@lhu.edu.vn" in contents
    assert "02513.952.251" in contents
    assert "kỹ năng mềm" in contents.lower() or "kĩ năng mềm" in contents.lower()
    assert "Kỹ năng viết CV điện tử và trả" in contents
    assert "Số 10 Huỳnh Văn Nghệ, Biên Hòa, Đồng Nai" in contents

    # Không chứa url rác google.com
    for c in chunks:
        assert "google.com/url" not in c["content"]


def test_ingest_quy_dinh_idempotent():
    """Kiểm tra tính idempotent của ingest: nạp lại không bị duplicate chunks."""
    # Chạy lần 1
    cnt1 = ingest_quy_dinh()
    assert cnt1 == 17

    # Chạy lần 2
    cnt2 = ingest_quy_dinh()
    assert cnt2 == 17

    # Truy vấn DB xác nhận chính xác 17 chunks của DOCUMENT_ID_QUY_DINH
    with engine.connect() as conn:
        doc_count = conn.execute(
            text("SELECT COUNT(*) FROM documents WHERE id = :did"),
            {"did": DOCUMENT_ID_QUY_DINH}
        ).scalar()
        assert doc_count == 1

        chunk_count = conn.execute(
            text("SELECT COUNT(*) FROM document_chunks WHERE document_id = :did"),
            {"did": DOCUMENT_ID_QUY_DINH}
        ).scalar()
        assert chunk_count == 17, f"Dữ liệu bị duplicate! Đếm được {chunk_count} chunks thay vì 17"

