"""
backend/tests/test_ctdt_credits_standalone.py
Kiểm thử tự động chương trình đào tạo ngành CNTT (Mục 7.1) trực tiếp từ định nghĩa chunk trong code (KHÔNG CẦN DB):
1. Mỗi học kỳ (HK1–HK8) có chunk riêng biệt, cờ verified=True, nhãn VB1, độ dài <= 600 ký tự.
2. Tổng số tín chỉ từng kỳ đúng chuẩn file Tong_hop... Mục 7.1:
   - HK1: 17 TC
   - HK2: 20 TC
   - HK3: 25 TC
   - HK4: 21 TC
   - HK5: 20 TC
   - HK6: 16 TC
   - HK7: 21 TC
   - HK8: 10 TC
3. Tổng tín chỉ toàn khóa đúng 150 tín chỉ (8 học kỳ).
4. Phân tích từng dòng môn học trong chunk để tính tổng tín chỉ các môn bắt buộc + tự chọn khớp chính xác số TC của kỳ.
"""

import re
import pytest
from backend.scripts.ingest_quy_dinh import parse_docx_chunks

SEMESTER_CREDITS_MAP = {
    1: 17,
    2: 20,
    3: 25,
    4: 21,
    5: 20,
    6: 16,
    7: 21,
    8: 10,
}


@pytest.fixture(scope="module")
def doc_chunks():
    """Đọc định nghĩa chunks từ hàm parse_docx_chunks trong code."""
    return parse_docx_chunks("database/seed_data/Tong_hop_quy_che_dao_tao_hoc_vu_LHU.docx")


def test_chunk_count_and_lengths(doc_chunks):
    """Doc 9001 có đúng 37 chunks chuẩn hóa sau khi tách riêng HK7 và HK8, mỗi chunk <= 600 ký tự."""
    assert len(doc_chunks) == 37, f"Mong đợi 37 chunks nhưng nhận được {len(doc_chunks)}"
    for idx, c in enumerate(doc_chunks):
        assert c["chunk_index"] == idx, f"Sai chunk_index tại vị trí {idx}"
        assert len(c["content"]) <= 600, (
            f"Chunk {idx} ('{c['section']}') dài {len(c['content'])} ký tự, vượt quá 600 ký tự"
        )


def test_hk1_to_hk8_chunks_exist_and_verified(doc_chunks):
    """HK1 đến HK8 phải có chunk riêng (chunk_index 18 đến 25), nhãn VB1 và verified=True."""
    for hk in range(1, 9):
        chunk_idx = 17 + hk
        c = doc_chunks[chunk_idx]
        assert c["chunk_index"] == chunk_idx
        assert c["verified"] is True, f"HK{hk} phải có verified=True"
        assert "VB1" in c["source"], f"HK{hk} phải có nguồn VB1"
        assert f"Học kỳ {hk}" in c["section"], f"Section chunk {chunk_idx} phải chứa 'Học kỳ {hk}'"


def test_each_semester_total_credits_declared(doc_chunks):
    """Kiểm tra tổng số tín chỉ từng học kỳ được công bố trong tiêu đề và nội dung chunk."""
    for hk, expected_tc in SEMESTER_CREDITS_MAP.items():
        chunk_idx = 17 + hk
        c = doc_chunks[chunk_idx]
        content = c["content"]
        section = c["section"]

        # Tiêu đề section phải chứa (X TC)
        assert f"({expected_tc} TC)" in section, f"Section HK{hk} thiếu '({expected_tc} TC)'"

        # Nội dung phải nêu rõ số TC của học kỳ đó
        m = re.search(r"Học kỳ\s+" + str(hk) + r"[^\n]*\(.*?(\d+)\s*TC", content)
        assert m is not None, f"Không tìm thấy số tín chỉ của Học kỳ {hk} trong nội dung"
        declared_tc = int(m.group(1))
        assert declared_tc == expected_tc, (
            f"Học kỳ {hk} công bố {declared_tc} TC, nhưng mong đợi {expected_tc} TC"
        )


def test_course_level_sum_credits_matches_semester(doc_chunks):
    """
    Phân tích từng dòng môn học trong nội dung chunk để cộng tín chỉ:
    - Các môn bắt buộc tính theo số TC ghi trong ngoặc (x TC).
    - Các môn tự chọn tính theo số TC của nhóm tự chọn.
    - GDQP (-) và GDTC (0 TC) không làm tăng tổng tín chỉ.
    """
    for hk, expected_tc in SEMESTER_CREDITS_MAP.items():
        chunk_idx = 17 + hk
        c = doc_chunks[chunk_idx]
        content = c["content"]

        total_calculated = 0
        lines = content.splitlines()

        for line in lines:
            line_s = line.strip()
            # Bỏ qua dòng tiêu đề nguồn, tổng kết
            if not line_s.startswith("-"):
                continue

            # Môn tự chọn (VD: "- Tự chọn 3 TC (chọn 1/2)...")
            if "tự chọn" in line_s.lower():
                m_tc = re.search(r"tự chọn\s+(\d+)\s*TC", line_s, re.IGNORECASE)
                if m_tc:
                    total_calculated += int(m_tc.group(1))
                continue

            # Môn bắt buộc có mã môn 6 chữ số hoặc môn GDTC/GDQP
            m_course = re.search(r"\(([0-9]+)\s*TC", line_s)
            if m_course:
                tc = int(m_course.group(1))
                total_calculated += tc

        assert total_calculated == expected_tc, (
            f"Tổng tín chỉ tính từ các môn của HK{hk} là {total_calculated} TC, không khớp {expected_tc} TC"
        )


def test_total_program_credits_equals_150(doc_chunks):
    """Tổng tín chỉ của cả 8 học kỳ phải đúng 150 tín chỉ."""
    sum_semesters = sum(SEMESTER_CREDITS_MAP.values())
    assert sum_semesters == 150, f"Tổng 8 học kỳ là {sum_semesters}, mong đợi 150"

    # Chunk 25 (HK8 & Tổng kết) phải có câu khẳng định 150 tín chỉ
    hk8_chunk = doc_chunks[25]
    assert "150 tín chỉ" in hk8_chunk["content"], "Chunk HK8 thiếu khẳng định 150 tín chỉ toàn khóa"

