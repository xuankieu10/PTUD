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


def test_cam_thi_answer_guarantees_both_conditions():
    """
    Câu hỏi điều kiện cấm thi: Luôn đảm bảo đủ cả 2 điều kiện
    (1: vắng quá 20% số tiết, 2: điểm thành phần dưới 2.0).
    """
    # Trường hợp raw answer chỉ có 1 ý (vắng quá 20%), thiếu ý điểm thành phần
    raw_answer_only_absent = "Sinh viên bị cấm thi khi vắng mặt quá 20% số tiết học phần."
    cleaned = clean_academic_regulation_answer(raw_answer_only_absent, "Điều kiện bị cấm thi kết thúc học phần là gì?")
    assert "20%" in cleaned
    assert "2.0" in cleaned or "2,0" in cleaned
    assert "thành phần" in cleaned.lower() or "bộ phận" in cleaned.lower()

    # Trường hợp raw answer chỉ có ý điểm thành phần, thiếu ý vắng 20%
    raw_answer_only_score = "Sinh viên bị cấm thi nếu điểm thành phần dưới 2.0."
    cleaned2 = clean_academic_regulation_answer(raw_answer_only_score, "Điều kiện cấm thi là gì?")
    assert "20%" in cleaned2
    assert "2.0" in cleaned2 or "2,0" in cleaned2


def test_hoc_vet_does_not_claim_nha_truong_chua_co_van_ban():
    """
    Câu hỏi học vét: Không được khẳng định 'Nhà trường chưa có văn bản',
    phải dùng 'tài liệu hiện có không đề cập riêng'.
    """
    raw_answer = "Hiện tại Nhà trường chưa có văn bản quy định riêng về lớp học vét; sinh viên học lại theo quy trình."
    cleaned = clean_academic_regulation_answer(raw_answer, "Lớp học vét là gì và đăng ký ở đâu?")
    assert "chưa có văn bản" not in cleaned.lower()
    assert "tài liệu hiện có không đề cập riêng" in cleaned.lower()


def test_personal_vs_general_query_routing():
    """
    Kiểm tra phân loại và bảo toàn dữ liệu sinh viên:
    - Câu hỏi cá nhân ('môn nào tôi đang bị F?', 'tôi còn thiếu bao nhiêu tín chỉ?'):
      có dùng dữ liệu sinh viên (trả về môn IT2030 hoặc tín chỉ của student 1).
    - Câu hỏi quy chế chung ('điều kiện tốt nghiệp là gì?'):
      không bị chèn template dữ liệu cá nhân của sinh viên.
    """
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend.app.security import create_access_token

    client = TestClient(app)
    # user_id = 2 là tài khoản sv01 (gắn với student_id = 1, MSSV 20210001)
    token = create_access_token(subject=2, role="student")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Câu hỏi cá nhân: "môn nào tôi đang bị F?" -> phải tra cứu dữ liệu cá nhân của student 1
    res_f = client.post("/chat", json={"message": "môn nào tôi đang bị F?"}, headers=headers)
    assert res_f.status_code == 200
    ans_f = res_f.json().get("answer", "")
    # Student 1 nợ môn IT2030 (Cấu trúc dữ liệu và giải thuật)
    assert "it2030" in ans_f.lower() or "cấu trúc dữ liệu" in ans_f.lower() or "chưa đạt" in ans_f.lower() or "học phần" in ans_f.lower()

    # 2. Câu hỏi cá nhân: "tôi còn thiếu bao nhiêu tín chỉ?" -> phải có thông tin tín chỉ của student 1
    res_tc = client.post("/chat", json={"message": "tôi còn thiếu bao nhiêu tín chỉ?"}, headers=headers)
    assert res_tc.status_code == 200
    ans_tc = res_tc.json().get("answer", "")
    assert "tín chỉ" in ans_tc.lower()
    assert "17" in ans_tc or "133" in ans_tc or "thiếu" in ans_tc.lower()

    # 3. Câu hỏi quy chế chung: "điều kiện tốt nghiệp là gì?" -> KHÔNG chèn hồ sơ cá nhân
    res_gen = client.post("/chat", json={"message": "điều kiện tốt nghiệp là gì?"}, headers=headers)
    assert res_gen.status_code == 200
    ans_gen = res_gen.json().get("answer", "")
    # Phải là quy chế chung (Điều 15 / 150 tín chỉ)
    assert "150 tín chỉ" in ans_gen
    # KHÔNG được chứa thông tin cá nhân cụ thể của student 1 (ví dụ MSSV 20210001, hoặc báo student 1 nợ IT2030)
    assert "20210001" not in ans_gen
    assert "bảng điểm ocr" not in ans_gen.lower()



