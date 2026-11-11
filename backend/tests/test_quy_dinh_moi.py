"""
backend/tests/test_quy_dinh_moi.py
Kiểm thử các quy định cập nhật theo Tong_hop_quy_che_dao_tao_hoc_vu_LHU.docx:
1. Cờ verified trong document_chunks (VB1 = True, VB2 = False).
2. Quy định ngưỡng F (< 4.0) và giải thích xung đột Mục 8.
3. Điều kiện tốt nghiệp theo Điều 15 (150 TC, GDQP-AN, 3 học phần GDTC điểm P >= 5.0).
4. Cấm thi (vắng > 20%, điểm TP < 2.0) kèm cảnh báo thông tin chưa kiểm chứng.
"""

import pytest
from sqlalchemy import text
from backend.app.db import SessionLocal
from backend.app.services.retrieval import search_chunks
from backend.app.routers.chat import clean_academic_regulation_answer


def test_verified_flags_in_database():
    """Kiểm tra cờ verified trong database: các chunk VB2 phải có verified=False."""
    with SessionLocal() as db:
        rows = db.execute(
            text("SELECT chunk_index, section, verified FROM document_chunks WHERE document_id = 9001 ORDER BY chunk_index")
        ).fetchall()
        assert len(rows) == 17, f"Mong đợi 17 chunks cho doc 9001, nhận {len(rows)}"

        verified_map = {r.chunk_index: bool(r.verified) for r in rows}

        # Chunk 0 (Mục 1 Thang điểm): VB1 -> True
        assert verified_map[0] is True
        # Chunk 1 (Mục 2 Cấm thi): VB2 -> False
        assert verified_map[1] is False
        # Chunk 2 (Mục 3.1 Học lại): VB1 -> True
        assert verified_map[2] is True
        # Chunk 6 (Mục 5 Tốt nghiệp): VB1 -> True
        assert verified_map[6] is True
        # Chunk 8 (Mục 6.3 Form học lại): VB2 -> False
        assert verified_map[8] is False
        # Chunk 11 (Mục 7.3 Lệ phí NN-TH): VB2 -> False
        assert verified_map[11] is False
        # Chunk 12 (Mục 7.3 Miễn ngoại ngữ): VB2 -> False
        assert verified_map[12] is False
        # Chunk 14 (Mục 7.4 Kỹ năng mềm): VB2 -> False
        assert verified_map[14] is False


def test_retrieval_returns_verified_field():
    """search_chunks phải trả về trường verified cho mỗi chunk."""
    with SessionLocal() as db:
        chunks = search_chunks(db, "điều kiện cấm thi")
        assert len(chunks) > 0
        for c in chunks:
            assert "verified" in c
            assert isinstance(c["verified"], bool)


def test_cam_thi_answer_includes_unverified_warning():
    """Khi trả lời câu hỏi cấm thi, câu trả lời phải kèm thông báo chưa kiểm chứng."""
    raw_answer = "Sinh viên bị cấm thi khi vắng quá 20% số tiết hoặc điểm thành phần dưới 2.0."
    cleaned = clean_academic_regulation_answer(raw_answer, "điều kiện cấm thi là gì?")
    assert "chưa được xác nhận chính thức" in cleaned.lower() or "chưa kiểm chứng" in cleaned.lower()


def test_nguong_f_conflict_note():
    """Khi hỏi về ngưỡng điểm F, câu trả lời có lưu ý theo Mục 8 về văn bản khác."""
    raw_answer = "Theo quy chế, điểm F là dưới 4.0 và sinh viên phải học lại."
    cleaned = clean_academic_regulation_answer(raw_answer, "ngưỡng điểm F là mấy?")
    assert "dưới 4.0" in cleaned
    assert "mục 8" in cleaned.lower() or "văn bản khác" in cleaned.lower()


def test_graduation_conditions_content_in_rag():
    """Chunk xét tốt nghiệp trong RAG phải chứa đầy đủ Điều 15 (150 TC, GDQP-AN, GDTC điểm P >= 5.0)."""
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT content FROM document_chunks WHERE document_id = 9001 AND chunk_index = 6")
        ).fetchone()
        assert row is not None
        content = row[0]
        assert "150 tín chỉ" in content
        assert "Điều 15" in content
        assert "Giáo dục quốc phòng" in content
        assert "Giáo dục thể chất" in content
        assert "Kỹ năng mềm" in content


def test_graduation_answer_preserves_qd1013_and_khong_con_hoc_phan_khong_dat():
    """
    Câu hỏi điều kiện xét tốt nghiệp:
    - Không lọc bỏ điều kiện QĐ 1013: điểm TBTL toàn khóa >= 5.0 (thang 10), không đang bị đình chỉ học tập.
    - Bắt buộc có ý 'không còn học phần không đạt'.
    - Không tự quy đổi sang thang 4.
    """
    raw_answer = (
        "Điều kiện xét tốt nghiệp:\n"
        "- Tích lũy đủ 150 tín chỉ của CTĐT, không còn học phần không đạt (không còn môn điểm F dưới 4.0).\n"
        "- Có chứng chỉ GDQP-AN và hoàn thành 3 học phần GDTC (điểm P từ 5.0 trở lên).\n"
        "- Đạt chuẩn ngoại ngữ - tin học và hoàn thành Kỹ năng mềm.\n"
        "- Cho đến thời điểm xét tốt nghiệp không bị truy cứu TNHS hoặc không đang trong thời gian bị kỷ luật ở mức đình chỉ học tập (QĐ 1013).\n"
        "- Điểm trung bình tích lũy toàn khóa đạt từ 5.0 trở lên (thang 10) (QĐ 1013)."
    )
    cleaned = clean_academic_regulation_answer(raw_answer, "điều kiện xét tốt nghiệp là gì?")
    assert "không còn học phần không đạt" in cleaned.lower()
    assert "5.0" in cleaned
    assert "đình chỉ" in cleaned.lower()
    assert "truy cứu" in cleaned.lower()


def test_thi_ho_and_buoc_thoi_hoc_not_truncated():
    """
    Câu hỏi về thi hộ / buộc thôi học không bị cắt nội dung kỷ luật, đình chỉ, hay buộc thôi học.
    """
    raw_answer = (
        "Theo quy định về xử lý kỷ luật sinh viên:\n"
        "1. Thi hộ hoặc nhờ người khác thi hộ: Đình chỉ học tập 01 năm đối với trường hợp vi phạm lần thứ nhất; Buộc thôi học đối với trường hợp vi phạm lần thứ hai.\n"
        "2. Sử dụng hồ sơ, bằng cấp, chứng chỉ giả mạo: Buộc thôi học ngay khi phát hiện."
    )
    cleaned = clean_academic_regulation_answer(raw_answer, "Hình thức xử lý khi thi hộ hoặc nhờ người thi hộ là gì?")
    assert "thi hộ" in cleaned.lower()
    assert "đình chỉ học tập 01 năm" in cleaned.lower()
    assert "buộc thôi học" in cleaned.lower()


