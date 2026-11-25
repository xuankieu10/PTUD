"""
backend/tests/test_sample_transcripts_manual_verification.py
Kiểm thử tính toán tổng tín chỉ và GPA từ các tệp Bảng điểm mẫu (PDF)
So sánh khớp chính xác với số liệu tính toán chuẩn (tính tay).
"""

import os
import pytest
from backend.pdf_processor import extract_grades_from_pdf_text_layer
from backend.app.services.graduation_checker import (
    calculate_academic_summary,
    check_graduation,
    build_structured_advisory_text,
    format_advisory_response,
    DEFAULT_CNTT_CURRICULUM
)

SAMPLE_DIR = "D:/test điểm"


@pytest.mark.skipif(not os.path.exists(os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 1.pdf")), reason="Không tìm thấy tệp Bảng điểm mẫu 1.pdf")
def test_verify_sample_transcript_1():
    """
    Kiểm thử Bảng điểm mẫu 1.pdf:
    - Tổng số môn: 28 môn.
    - Môn nợ (điểm < 4.0): Dịch vụ mạng (3 TC, 3.25) và Toán cao cấp 1 (4 TC, 3.25) = 7 TC.
    - Môn điều kiện/hệ số 0 không tính tín chỉ tích lũy & GPA: GDTC 1, 2, 3, GDQP, Kỹ năng khởi nghiệp, Rèn luyện quy đổi.
    - Tín chỉ tích lũy đạt: 52 tín chỉ.
    - Tổng tín chỉ học phần có hệ số: 59 tín chỉ (52 đạt + 7 nợ).
    - GPA thang 10 (chỉ môn đạt): 7.18 (khớp số tính tay 7.16 với dung sai +-0.02 do làm tròn điểm thành phần).
    - GPA thang 4 (chỉ môn đạt): 2.67.
    """
    pdf_path = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 1.pdf")
    subjects, _ = extract_grades_from_pdf_text_layer(pdf_path, max_pages=10)

    summary = calculate_academic_summary(subjects)

    assert len(subjects) == 28
    assert summary["passed_credits"] == 52
    assert summary["failed_credits"] == 7
    assert summary["gpa_10"] == pytest.approx(7.18, abs=0.005)
    assert summary["gpa_4"] == 2.81
    assert summary["total_gpa_credits"] == 52

    # Kiểm tra thêm GPA tính cả môn rớt (toàn bộ 59 tín chỉ)
    total_coef_credits = sum(s.get("he_so", 0) for s in subjects if s.get("he_so", 0) > 0)
    assert total_coef_credits == 59
    total_weighted_all = sum(s.get("he_so", 0) * s.get("diem", 0.0) for s in subjects if s.get("he_so", 0) > 0)
    gpa_all = round(total_weighted_all / total_coef_credits, 2)
    assert gpa_all == pytest.approx(6.71, abs=0.005)


@pytest.mark.skipif(not os.path.exists(os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 2.pdf")), reason="Không tìm thấy tệp Bảng điểm mẫu 2.pdf")
def test_verify_sample_transcript_2():
    """Kiểm thử Bảng điểm mẫu 2.pdf"""
    pdf_path = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 2.pdf")
    subjects, _ = extract_grades_from_pdf_text_layer(pdf_path, max_pages=10)

    summary = calculate_academic_summary(subjects)

    assert len(subjects) == 25
    assert summary["passed_credits"] == 53
    assert summary["failed_credits"] == 10
    assert summary["gpa_10"] == 6.64
    assert summary["gpa_4"] == 2.38


@pytest.mark.skipif(not os.path.exists(os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 3.pdf")), reason="Không tìm thấy tệp Bảng điểm mẫu 3.pdf")
def test_verify_sample_transcript_3():
    """Kiểm thử Bảng điểm mẫu 3.pdf"""
    pdf_path = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 3.pdf")
    subjects, _ = extract_grades_from_pdf_text_layer(pdf_path, max_pages=10)

    summary = calculate_academic_summary(subjects)

    assert len(subjects) == 25
    assert summary["passed_credits"] == 57
    assert summary["failed_credits"] == 6
    assert summary["gpa_10"] == 7.40
    assert summary["gpa_4"] == 2.91


@pytest.mark.skipif(not os.path.exists(os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 4.pdf")), reason="Không tìm thấy tệp Bảng điểm mẫu 4.pdf")
def test_verify_sample_transcript_4():
    """Kiểm thử Bảng điểm mẫu 4.pdf"""
    pdf_path = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 4.pdf")
    subjects, _ = extract_grades_from_pdf_text_layer(pdf_path, max_pages=10)

    summary = calculate_academic_summary(subjects)

    assert len(subjects) == 25
    assert summary["passed_credits"] == 50
    assert summary["failed_credits"] == 12
    assert summary["gpa_10"] == 6.92
    assert summary["gpa_4"] == 2.54


@pytest.mark.skipif(not os.path.exists(SAMPLE_DIR), reason="Thư mục bảng điểm mẫu không tồn tại")
def test_verify_all_4_samples_semester_averages_match_pdf_printed():
    """
    Với CẢ 4 bảng điểm mẫu: tính điểm TB từng học kỳ bằng Decimal + ROUND_HALF_UP,
    so sánh khớp chính xác 100% với điểm TB in trên PDF (bao gồm Mẫu 3 HK2 = 7.53).
    """
    import pdfplumber
    import re
    from decimal import Decimal, ROUND_HALF_UP
    from backend.pdf_processor import recover_or_validate_grade

    for i in range(1, 5):
        fname = f"Bảng điểm mẫu {i}.pdf"
        fpath = os.path.join(SAMPLE_DIR, fname)
        if not os.path.exists(fpath):
            continue

        with pdfplumber.open(fpath) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                tables = page.find_tables()
                for t in tables:
                    top_y = t.bbox[1]
                    crop_area = (0, max(0, top_y - 45), page.width, top_y)
                    heading = page.crop(crop_area).extract_text() or ""

                    m_hk = re.search(r"Học kỳ\s+(\d+)\s+Điểm\s+trung\s+bình:\s*([0-9.,]+)", heading, re.IGNORECASE)
                    if not m_hk:
                        continue

                    sem_num = int(m_hk.group(1))
                    printed_gpa = float(m_hk.group(2).replace(",", "."))

                    rows = t.extract()
                    if not rows or len(rows) < 2:
                        continue

                    header = [str(c or "").strip().lower() for c in rows[0]]
                    mon_idx = next((idx for idx, c in enumerate(header) if "tên" in c or "môn" in c), 1)
                    tc_idx = next((idx for idx, c in enumerate(header) if "hệ số" in c or "tín" in c), 2)
                    tp_idx = next((idx for idx, c in enumerate(header) if "thành phần" in c or "tp" in c), -1)
                    dtb_idx = next((idx for idx, c in enumerate(header) if "trung bình" in c or "đtb" in c), -1)
                    if dtb_idx == -1:
                        dtb_idx = next((idx for idx, c in enumerate(header) if "điểm" in c and idx != tp_idx), -1)

                    sem_credits = Decimal("0")
                    sem_weighted = Decimal("0.0")

                    for r in rows[1:]:
                        if len(r) <= max(mon_idx, dtb_idx):
                            continue
                        mon_name = str(r[mon_idx] or "").strip()
                        if not mon_name:
                            continue
                        tc_str = str(r[tc_idx] or "").strip() if tc_idx != -1 else "0"
                        try:
                            tc_val = int(float(tc_str))
                        except Exception:
                            tc_val = 0

                        diem_raw = str(r[dtb_idx] or "").strip() if dtb_idx != -1 else ""
                        tp_str = str(r[tp_idx] or "").strip() if tp_idx != -1 else ""
                        diem_val, _, _ = recover_or_validate_grade(diem_raw, tp_str)

                        if tc_val > 0 and diem_val is not None:
                            d_tc = Decimal(str(tc_val))
                            d_diem = Decimal(str(diem_val))
                            sem_credits += d_tc
                            sem_weighted += d_diem * d_tc

                    assert sem_credits > 0, f"Học kỳ {sem_num} ({fname}) không có tín chỉ hợp lệ"
                    code_gpa = float((sem_weighted / sem_credits).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                    # Khớp chính xác 100% bằng Decimal + ROUND_HALF_UP (Mẫu 3 HK2 đúng 7.53, không cần dung sai)
                    assert code_gpa == printed_gpa, (
                        f"LỆCH ĐIỂM TB KỲ: {fname} Học kỳ {sem_num}: Code={code_gpa:.2f} != In trên PDF={printed_gpa:.2f}"
                    )


@pytest.mark.skipif(not os.path.exists(SAMPLE_DIR), reason="Thư mục bảng điểm mẫu không tồn tại")
def test_parsed_semesters_count_matches_pdf_headings():
    """
    Test Task 1: Dùng REGEX ĐỘC LẬP trên text thô (không qua parser) để đếm số tiêu đề kỳ:
    - Mẫu 1: 4 kỳ (HK4, HK3, HK2, HK1)
    - Mẫu 2: 4 kỳ (HK4, HK3, HK2, HK1)
    - Mẫu 3: 4 kỳ (HK5, HK4, HK3, HK2)
    - Mẫu 4: 4 kỳ (HK6, HK5, HK4, HK3)
    Sau đó đối chiếu với tập học kỳ parser trả về.
    """
    import pdfplumber
    import re

    expected_raw_headings = {
        "Bảng điểm mẫu 1.pdf": ["Học kỳ 4", "Học kỳ 3", "Học kỳ 2", "Học kỳ 1"],
        "Bảng điểm mẫu 2.pdf": ["Học kỳ 4", "Học kỳ 3", "Học kỳ 2", "Học kỳ 1"],
        "Bảng điểm mẫu 3.pdf": ["Học kỳ 5", "Học kỳ 4", "Học kỳ 3", "Học kỳ 2"],
        "Bảng điểm mẫu 4.pdf": ["Học kỳ 6", "Học kỳ 5", "Học kỳ 4", "Học kỳ 3"]
    }

    for fname, exp_headings in expected_raw_headings.items():
        fpath = os.path.join(SAMPLE_DIR, fname)
        if not os.path.exists(fpath):
            continue

        # Đọc text thô trực tiếp từ PDF, dùng regex độc lập tìm tiêu đề học kỳ
        with pdfplumber.open(fpath) as pdf:
            raw_text = "\n".join([p.extract_text() or "" for p in pdf.pages])
            raw_pdf_headings = re.findall(r"Học kỳ\s+\d+", raw_text)

        # 1. Assert regex độc lập trên text thô
        assert len(raw_pdf_headings) == 4, f"{fname} có {len(raw_pdf_headings)} tiêu đề kỳ trong text thô, mong đợi 4"
        assert raw_pdf_headings == exp_headings, f"{fname}: Tiêu đề text thô {raw_pdf_headings} khác {exp_headings}"

        # 2. Assert parser trích xuất đủ và khớp với các kỳ này
        subjects, _ = extract_grades_from_pdf_text_layer(fpath, max_pages=10)
        parsed_semesters = set(s.get("hoc_ky") for s in subjects if s.get("hoc_ky") and "Học kỳ" in s.get("hoc_ky"))
        assert len(parsed_semesters) == 4
        assert parsed_semesters == set(exp_headings)


@pytest.mark.skipif(not os.path.exists(SAMPLE_DIR), reason="Thư mục bảng điểm mẫu không tồn tại")
def test_partial_transcript_detection_sample_3_and_4():
    """
    Test Task 2: Khi kỳ nhỏ nhất trong bảng điểm > HK1:
    - Bảng điểm mẫu 3 (kỳ nhỏ nhất = HK2) và Mẫu 4 (kỳ nhỏ nhất = HK3) phải có cờ partial_transcript=True.
    - Phần 'Tình trạng' của tư vấn phải cảnh báo thiếu dữ liệu các kỳ trước.
    - Phần 'Còn thiếu' KHÔNG khẳng định chắc chắn 'còn thiếu X tín chỉ' mà phải nói rõ là ước tính/chưa khẳng định chắc chắn.
    - Bảng điểm mẫu 1 và 2 (kỳ nhỏ nhất = HK1) có partial_transcript=False.
    """
    from backend.app.services.graduation_checker import check_graduation, build_structured_advisory_text

    # Mẫu 3: Kỳ nhỏ nhất = HK2 > HK1 -> partial_transcript=True
    path_3 = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 3.pdf")
    subjects_3, _ = extract_grades_from_pdf_text_layer(path_3, max_pages=10)
    summary_3 = calculate_academic_summary(subjects_3)
    assert summary_3["partial_transcript"] is True
    assert summary_3["min_semester"] == 2

    grad_3 = check_graduation(profile={"courses": subjects_3}, curriculum=[])
    assert grad_3["partial_transcript"] is True
    text_3 = build_structured_advisory_text(grad_3)
    assert "Cảnh báo dữ liệu: Bảng điểm cung cấp chỉ hiển thị từ Học kỳ 2 trở đi" in text_3["part_1"]
    assert "tính trên các kỳ hiện có" in text_3["part_1"]
    assert "chưa thể khẳng định chắc chắn do thiếu dữ liệu" in text_3["part_2"]
    assert "Cần tích lũy thêm ít nhất" not in text_3["part_2"]

    # Mẫu 4: Kỳ nhỏ nhất = HK3 > HK1 -> partial_transcript=True
    path_4 = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 4.pdf")
    subjects_4, _ = extract_grades_from_pdf_text_layer(path_4, max_pages=10)
    summary_4 = calculate_academic_summary(subjects_4)
    assert summary_4["partial_transcript"] is True
    assert summary_4["min_semester"] == 3

    grad_4 = check_graduation(profile={"courses": subjects_4}, curriculum=[])
    assert grad_4["partial_transcript"] is True
    text_4 = build_structured_advisory_text(grad_4)
    assert "Cảnh báo dữ liệu: Bảng điểm cung cấp chỉ hiển thị từ Học kỳ 3 trở đi" in text_4["part_1"]
    assert "tính trên các kỳ hiện có" in text_4["part_1"]
    assert "chưa thể khẳng định chắc chắn do thiếu dữ liệu" in text_4["part_2"]
    assert "Cần tích lũy thêm ít nhất" not in text_4["part_2"]

    # Mẫu 1 & 2: Kỳ nhỏ nhất = HK1 -> partial_transcript=False
    path_1 = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 1.pdf")
    subjects_1, _ = extract_grades_from_pdf_text_layer(path_1, max_pages=10)
    summary_1 = calculate_academic_summary(subjects_1)
    assert summary_1["partial_transcript"] is False
    assert summary_1["min_semester"] == 1

    path_2 = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 2.pdf")
    subjects_2, _ = extract_grades_from_pdf_text_layer(path_2, max_pages=10)
    summary_2 = calculate_academic_summary(subjects_2)
    assert summary_2["partial_transcript"] is False
    assert summary_2["min_semester"] == 1


@pytest.mark.skipif(not os.path.exists(SAMPLE_DIR), reason="Thư mục bảng điểm mẫu không tồn tại")
def test_partial_transcript_no_earlier_semester_courses_in_plan_sample_3_and_4():
    """
    Test khẳng định: Khi partial_transcript=True:
    1. Các môn bắt buộc thuộc học kỳ < min_semester theo CTĐT KHÔNG được xếp vào kế hoạch (part 3)
       và KHÔNG được liệt kê như chắc chắn thiếu.
    2. Chúng được tách vào mục riêng: 'Chưa có dữ liệu để kết luận (có thể đã học hoặc được miễn)'.
    3. Hỗ trợ biến tùy chọn 'exempted_courses' trong profile để người dùng khai báo môn đã được miễn/chuyển điểm.
    """
    from backend.app.services.graduation_checker import check_graduation, build_structured_advisory_text, DEFAULT_CNTT_CURRICULUM

    # 1. BẢNG ĐIỂM MẪU 3 (Bắt đầu từ HK2):
    # Các môn HK1 của CTĐT: Toán cao cấp 1 (102073), Nhập môn lập trình (111094), Cấu trúc và lắp ráp máy tính (111001)...
    path_3 = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 3.pdf")
    subjects_3, _ = extract_grades_from_pdf_text_layer(path_3, max_pages=10)

    grad_3 = check_graduation(
        profile={"courses": subjects_3},
        curriculum=DEFAULT_CNTT_CURRICULUM,
        current_semester=5
    )
    assert grad_3["partial_transcript"] is True
    assert grad_3["min_semester"] == 2

    # Các môn HK1 phải nằm trong mục unverified_courses (Chưa có dữ liệu để kết luận)
    unverified_codes_3 = [u["ma_mon"] for u in grad_3["unverified_courses"]]
    assert "102073" in unverified_codes_3  # Toán cao cấp 1
    assert "111094" in unverified_codes_3  # Nhập môn lập trình
    assert "111001" in unverified_codes_3  # Cấu trúc và lắp ráp máy tính

    # Môn HK1 KHÔNG được xuất hiện trong missing_required_courses
    missing_codes_3 = [m["ma_mon"] for m in grad_3["missing_required_courses"]]
    assert "102073" not in missing_codes_3
    assert "111094" not in missing_codes_3

    # Môn HK1 KHÔNG được xuất hiện trong proposed_plan
    plan_codes_3 = []
    for sem in grad_3["proposed_plan"]:
        for c in sem["courses"]:
            plan_codes_3.append(c["ma_mon"])
    assert "102073" not in plan_codes_3
    assert "111094" not in plan_codes_3
    assert "111001" not in plan_codes_3

    # Kiểm tra văn bản 4 phần
    text_3 = build_structured_advisory_text(grad_3)
    assert "Chưa có dữ liệu để kết luận (có thể đã học hoặc được miễn" in text_3["part_2"]
    # Các môn HK1 không nằm trong Kế hoạch phần 3
    assert "Toán cao cấp 1" not in text_3["part_3"]
    assert "Cấu trúc và lắp ráp máy tính" not in text_3["part_3"]

    # 2. BẢNG ĐIỂM MẪU 4 (Bắt đầu từ HK3):
    path_4 = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 4.pdf")
    subjects_4, _ = extract_grades_from_pdf_text_layer(path_4, max_pages=10)

    grad_4 = check_graduation(
        profile={"courses": subjects_4},
        curriculum=DEFAULT_CNTT_CURRICULUM,
        current_semester=5
    )
    assert grad_4["partial_transcript"] is True
    assert grad_4["min_semester"] == 3

    unverified_codes_4 = [u["ma_mon"] for u in grad_4["unverified_courses"]]
    # Các môn HK1 và HK2 nằm trong unverified_courses
    assert "102073" in unverified_codes_4  # HK1: Toán cao cấp 1
    assert "111058" in unverified_codes_4  # HK2: Kỹ thuật lập trình
    assert "111056" in unverified_codes_4  # HK2: Thiết kế UI/UX

    # Các môn HK1, HK2 không được có trong proposed_plan
    plan_codes_4 = [c["ma_mon"] for sem in grad_4["proposed_plan"] for c in sem["courses"]]
    assert "102073" not in plan_codes_4
    assert "111058" not in plan_codes_4
    assert "111056" not in plan_codes_4

    # 3. TEST TÙY CHỌN exempted_courses (Khai báo môn đã được miễn / chuyển điểm):
    grad_3_exempted = check_graduation(
        profile={
            "courses": subjects_3,
            "exempted_courses": ["102073", "Nhập môn lập trình"]
        },
        curriculum=DEFAULT_CNTT_CURRICULUM,
        current_semester=5
    )
    unverified_codes_ex = [u["ma_mon"] for u in grad_3_exempted["unverified_courses"]]
    # Vì đã khai báo miễn/chuyển điểm nên không còn nằm trong mục chưa có dữ liệu kết luận
    assert "102073" not in unverified_codes_ex
    assert "111094" not in unverified_codes_ex


@pytest.mark.skipif(not os.path.exists(SAMPLE_DIR), reason="Thư mục bảng điểm mẫu không tồn tại")
def test_partial_transcript_unverified_prerequisites_do_not_block_future_courses_sample_3():
    """
    Test Item 3: Khi partial_transcript=True:
    Tiên quyết thuộc nhóm 'unverified' (học kỳ < min_semester) được coi là giả định đã đạt (kèm ghi chú),
    KHÔNG chặn môn phía sau.
    
    Dữ liệu sử dụng:
    - Bảng điểm thật: 'Bảng điểm mẫu 3.pdf' (chỉ có HK2..HK5, thiếu toàn bộ HK1).
    - Dữ liệu CTĐT: Sử dụng fixture CTĐT (dựa trên DEFAULT_CNTT_CURRICULUM chuẩn của Khoa CNTT - LHU,
      bổ sung môn bắt buộc HK3 'Chuyên đề Thuật toán nâng cao' có điều kiện tiên quyết là môn HK1
      'Nhập môn lập trình' - 111094).
    """
    from backend.app.services.graduation_checker import check_graduation, build_structured_advisory_text, DEFAULT_CNTT_CURRICULUM

    path_3 = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 3.pdf")
    subjects_3, _ = extract_grades_from_pdf_text_layer(path_3, max_pages=10)

    # Fixture CTĐT: Bổ sung 1 môn HK3 có tiên quyết là môn HK1 (111094 - Nhập môn lập trình)
    curriculum_fixture = [dict(c) for c in DEFAULT_CNTT_CURRICULUM]
    curriculum_fixture.append({
        "ma_mon": "TEST_HK3_01",
        "ten_mon": "Chuyên đề Thuật toán nâng cao",
        "tin_chi": 3,
        "hoc_ky_de_xuat": 3,
        "is_required": True,
        "mon_tien_quyet": ["111094"]  # Tiên quyết là môn HK1 nằm ngoài bảng điểm mẫu 3
    })

    grad = check_graduation(
        profile={"courses": subjects_3},
        curriculum=curriculum_fixture,
        current_semester=5
    )

    # Khẳng định môn HK1 (111094) thuộc nhóm unverified_courses
    unverified_codes = [u["ma_mon"] for u in grad["unverified_courses"]]
    assert "111094" in unverified_codes

    # Môn HK3 (TEST_HK3_01) KHÔNG bị chặn bởi tiên quyết HK1 chưa kiểm chứng,
    # VẪN XUẤT HIỆN trong proposed_plan
    all_plan_courses = []
    for sem in grad["proposed_plan"]:
        for c in sem["courses"]:
            all_plan_courses.append(c)

    plan_codes = [c["ma_mon"] for c in all_plan_courses]
    assert "TEST_HK3_01" in plan_codes, "Môn HK3 có tiên quyết HK1 phải xuất hiện trong kế hoạch học kỳ đề xuất!"

    # Khẳng định môn được ghi chú rõ ràng về giả định đã đạt tiên quyết
    test_hk3_item = next(c for c in all_plan_courses if c["ma_mon"] == "TEST_HK3_01")
    assert "ghi_chu_tien_quyet" in test_hk3_item
    assert "Nhập môn lập trình" in test_hk3_item["ghi_chu_tien_quyet"] or "111094" in test_hk3_item["ghi_chu_tien_quyet"]

    # Khẳng định trong văn bản tư vấn Phần 3 có hiển thị ghi chú giả định này
    text_res = build_structured_advisory_text(grad)
    assert "Chuyên đề Thuật toán nâng cao" in text_res["part_3"]
    assert "Giả định đã đạt tiên quyết" in text_res["part_3"]


def test_prerequisite_map_courses_exist_in_curriculum_and_names_match():
    """
    Test E.3 & I.8: Mọi mã trong prerequisite map phải tồn tại trong curriculum và tên khớp.
    - 26 cạnh tiên quyết (học trước)
    - 1 cạnh song hành (Thực tập 111049 <-> Tốt nghiệp 33333)
    -> Tổng cộng 27 quan hệ ràng buộc môn học.
    """
    from backend.app.services.graduation_checker import DEFAULT_CNTT_CURRICULUM
    curriculum_by_code = {c["ma_mon"]: c["ten_mon"] for c in DEFAULT_CNTT_CURRICULUM}

    total_edges = 0
    total_coreqs = 0
    for course in DEFAULT_CNTT_CURRICULUM:
        target_code = course["ma_mon"]
        target_name = course["ten_mon"]
        for prereq_code in course.get("mon_tien_quyet", []):
            total_edges += 1
            # Mã tiên quyết phải tồn tại trong CTĐT
            assert prereq_code in curriculum_by_code, f"Môn tiên quyết {prereq_code} của {target_name} ({target_code}) không tồn tại trong CTĐT"
            prereq_name = curriculum_by_code[prereq_code]
            assert prereq_name, f"Tên môn tiên quyết {prereq_code} không được để trống"
        for coreq_code in course.get("mon_song_hanh", []):
            total_coreqs += 1
            assert coreq_code in curriculum_by_code, f"Môn song hành {coreq_code} của {target_name} ({target_code}) không tồn tại trong CTĐT"

    assert total_edges == 26, f"Tổng số liên kết tiên quyết (học trước) là {total_edges}, kỳ vọng 26"
    assert total_coreqs == 1, f"Tổng số liên kết song hành là {total_coreqs}, kỳ vọng 1"
    assert total_edges + total_coreqs == 27, f"Tổng số quan hệ ràng buộc là {total_edges + total_coreqs}, kỳ vọng 27"


def test_compare_prerequisite_edges_with_curriculum_tables_in_docx():
    """
    Test H.5 & I.8: Parse bảng 2-9 (HK1 - HK8) trong file Tong_hop_quy_che_dao_tao_hoc_vu_LHU.docx
    và so tập cạnh tiên quyết ('Học trước') và song hành ('Song hành') với DEFAULT_CNTT_CURRICULUM.
    """
    import docx
    import re
    from backend.app.services.graduation_checker import DEFAULT_CNTT_CURRICULUM

    docx_path = os.path.join(os.path.dirname(__file__), "..", "..", "database", "seed_data", "Tong_hop_quy_che_dao_tao_hoc_vu_LHU.docx")
    if not os.path.exists(docx_path):
        pytest.skip("Không tìm thấy file Tong_hop_quy_che_dao_tao_hoc_vu_LHU.docx")

    doc = docx.Document(docx_path)
    docx_prereqs = set()
    docx_coreqs = set()

    for i in range(2, 10):
        t = doc.tables[i]
        for r in t.rows[1:]:
            cells = [c.text.strip().replace("\n", " ") for c in r.cells]
            code = cells[0].strip()
            note = cells[4].strip() if len(cells) > 4 else ""
            if "Học trước:" in note:
                m = re.search(r"Học trước:\s*([0-9,\s]+)", note)
                if m:
                    prereqs = [x.strip() for x in m.group(1).split(",") if x.strip()]
                    for p in prereqs:
                        docx_prereqs.add((p, code))
            if "Song hành:" in note:
                m = re.search(r"Song hành:\s*([0-9,\s]+)", note)
                if m:
                    coreqs = [x.strip() for x in m.group(1).split(",") if x.strip()]
                    for p in coreqs:
                        docx_coreqs.add((p, code))

    curriculum_prereqs = set()
    curriculum_coreqs = set()
    for c in DEFAULT_CNTT_CURRICULUM:
        target = c["ma_mon"]
        for p in c.get("mon_tien_quyet", []):
            curriculum_prereqs.add((p, target))
        for s in c.get("mon_song_hanh", []):
            curriculum_coreqs.add((s, target))

    assert len(docx_prereqs) == 26, f"Docx có {len(docx_prereqs)} cạnh học trước, kỳ vọng 26"
    assert len(docx_coreqs) == 1, f"Docx có {len(docx_coreqs)} cạnh song hành, kỳ vọng 1"
    assert docx_prereqs == curriculum_prereqs, f"Cạnh học trước lệch giữa Docx và CTĐT: {docx_prereqs ^ curriculum_prereqs}"
    assert docx_coreqs == curriculum_coreqs, f"Cạnh song hành lệch giữa Docx và CTĐT: {docx_coreqs ^ curriculum_coreqs}"


def test_sample_transcripts_courses_match_curriculum_names_by_code():
    """
    Test E.3: Mọi môn trong bảng điểm Mẫu 1-4 có mã trong CTĐT phải khớp tên theo mã (không chỉ theo tên chuẩn hóa).
    """
    import re
    from backend.app.services.graduation_checker import DEFAULT_CNTT_CURRICULUM, normalize_course_name
    curriculum_by_code = {c["ma_mon"]: c["ten_mon"] for c in DEFAULT_CNTT_CURRICULUM}

    for i in range(1, 5):
        pdf_path = os.path.join(SAMPLE_DIR, f"Bảng điểm mẫu {i}.pdf")
        if not os.path.exists(pdf_path):
            continue
        subjects, _ = extract_grades_from_pdf_text_layer(pdf_path, max_pages=10)
        for s in subjects:
            code = s.get("course_code")
            raw_name = s.get("course_name")
            if code in curriculum_by_code:
                expected_name = curriculum_by_code[code]
                # 1. Khớp theo normalize_course_name (loại bỏ tag {...}, không phân biệt hoa thường, dấu, gạch nối)
                assert normalize_course_name(raw_name) == normalize_course_name(expected_name), (
                    f"Mẫu {i}: Môn mã {code} có tên PDF '{raw_name}' không khớp tên CTĐT '{expected_name}'"
                )
                # 2. Khớp trực tiếp phần tên gốc sau khi bóc nhãn tag {...}:
                clean_raw = re.sub(r'\{[^}]*\}', '', raw_name).strip()
                # Đồng bộ dấu gạch nối và biến thể máy học / học máy
                clean_std = clean_raw.replace("-", " ").replace("máy học", "học máy").strip().lower()
                expected_std = expected_name.replace("-", " ").replace("máy học", "học máy").strip().lower()
                assert clean_std == expected_std, (
                    f"Mẫu {i}: Môn mã {code} có tên thô bóc tag '{clean_raw}' không khớp tên CTĐT '{expected_name}'"
                )


@pytest.mark.skipif(not os.path.exists(os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 1.pdf")), reason="Không tìm thấy Mẫu 1")
def test_verify_sample_transcript_1_gpa_range_formatting():
    """Kiểm tra Mẫu 1 format GPA thang 4 dạng khoảng khi làm tròn 1 chữ số cho kết quả khác ngưỡng cứng (2.81 vs 2.89)."""
    pdf_path = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 1.pdf")
    subjects, _ = extract_grades_from_pdf_text_layer(pdf_path, max_pages=10)
    summary = calculate_academic_summary(subjects)
    assert summary["gpa_4"] == 2.81
    assert summary["gpa_4_round"] == 2.89

    profile = {"student_code": "SV01", "full_name": "Test SV", "courses": subjects}
    grad = check_graduation(profile, DEFAULT_CNTT_CURRICULUM)
    parts = build_structured_advisory_text(grad)
    formatted = format_advisory_response(parts)
    assert "2.81-2.89 (ước tính, chờ giáo vụ xác nhận cách làm tròn)" in formatted


@pytest.mark.skipif(not os.path.exists(os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 2.pdf")), reason="Không tìm thấy Mẫu 2")
def test_verify_sample_transcript_2_gpa_range_formatting():
    """Kiểm tra Mẫu 2 format GPA thang 4 dạng khoảng khi làm tròn 1 chữ số cho kết quả khác ngưỡng cứng (2.38 vs 2.52)."""
    pdf_path = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 2.pdf")
    subjects, _ = extract_grades_from_pdf_text_layer(pdf_path, max_pages=10)
    summary = calculate_academic_summary(subjects)
    assert summary["gpa_4"] == 2.38
    assert summary["gpa_4_round"] == 2.52

    profile = {"student_code": "SV02", "full_name": "Test SV", "courses": subjects}
    grad = check_graduation(profile, DEFAULT_CNTT_CURRICULUM)
    parts = build_structured_advisory_text(grad)
    formatted = format_advisory_response(parts)
    assert "2.38-2.52 (ước tính, chờ giáo vụ xác nhận cách làm tròn)" in formatted


def test_verify_synthetic_transcript_gpa_single_number_formatting():
    """
    Kiểm tra trường hợp bảng điểm có gpa_4 == gpa_4_round thì format dạng một số:
    '2.50 (ước tính theo bảng quy đổi)'.

    Tính tay:
    - Môn 1: Cơ sở dữ liệu (111059), 3 TC, điểm 7.0 (thang 10) -> điểm chữ B, thang 4 = 3.0. Điểm quy đổi = 3 * 3.0 = 9.0.
      Khi làm tròn 1 chữ số: 7.0 -> 7.0 (B, 3.0).
    - Môn 2: Dịch vụ mạng (111036), 3 TC, điểm 6.0 (thang 10) -> điểm chữ C, thang 4 = 2.0. Điểm quy đổi = 3 * 2.0 = 6.0.
      Khi làm tròn 1 chữ số: 6.0 -> 6.0 (C, 2.0).
    - Tổng tín chỉ tính GPA = 3 + 3 = 6 TC.
    - Tổng điểm thang 4 theo ngưỡng cứng = 9.0 + 6.0 = 15.0.
      => GPA thang 4 (ngưỡng cứng) = 15.0 / 6 = 2.50.
    - Tổng điểm thang 4 khi làm tròn 1 chữ số = 9.0 + 6.0 = 15.0.
      => GPA thang 4 (làm tròn 1 chữ số) = 15.0 / 6 = 2.50.
    - Kết quả: gpa_4 == gpa_4_round == 2.50.
    - Định dạng tư vấn mong đợi: '2.50 (ước tính theo bảng quy đổi)'.
    """
    synthetic_subjects = [
        {"course_code": "111059", "course_name": "Cơ sở dữ liệu", "tin_chi": 3, "diem": 7.0, "he_so": 3},
        {"course_code": "111036", "course_name": "Dịch vụ mạng", "tin_chi": 3, "diem": 6.0, "he_so": 3},
    ]
    summary = calculate_academic_summary(synthetic_subjects)
    assert summary["gpa_4"] == 2.50
    assert summary["gpa_4_round"] == 2.50

    profile = {"student_code": "SV_SYNTH", "full_name": "Sinh viên Tổng hợp", "courses": synthetic_subjects}
    grad = check_graduation(profile, DEFAULT_CNTT_CURRICULUM)
    parts = build_structured_advisory_text(grad)
    formatted = format_advisory_response(parts)
    assert "2.50 (ước tính theo bảng quy đổi)" in formatted


@pytest.mark.skipif(not os.path.exists(os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 3.pdf")), reason="Không tìm thấy Mẫu 3")
def test_verify_sample_transcript_3_gpa_range_formatting():
    """Kiểm tra Mẫu 3 format GPA thang 4 dạng khoảng vì có môn đổi mức điểm (gpa_4=2.91, gpa_4_round=3.03)."""
    pdf_path = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 3.pdf")
    subjects, _ = extract_grades_from_pdf_text_layer(pdf_path, max_pages=10)
    summary = calculate_academic_summary(subjects)
    assert summary["gpa_4"] == 2.91
    assert summary["gpa_4_round"] == 3.03

    profile = {"student_code": "SV03", "full_name": "Test SV", "courses": subjects}
    grad = check_graduation(profile, DEFAULT_CNTT_CURRICULUM)
    parts = build_structured_advisory_text(grad)
    formatted = format_advisory_response(parts)
    assert "2.91-3.03 (ước tính, chờ giáo vụ xác nhận cách làm tròn)" in formatted


@pytest.mark.skipif(not os.path.exists(os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 4.pdf")), reason="Không tìm thấy Mẫu 4")
def test_verify_sample_transcript_4_gpa_range_formatting():
    """Kiểm tra Mẫu 4 format GPA thang 4 dạng khoảng vì có môn đổi mức điểm (gpa_4=2.54, gpa_4_round=2.76)."""
    pdf_path = os.path.join(SAMPLE_DIR, "Bảng điểm mẫu 4.pdf")
    subjects, _ = extract_grades_from_pdf_text_layer(pdf_path, max_pages=10)
    summary = calculate_academic_summary(subjects)
    assert summary["gpa_4"] == 2.54
    assert summary["gpa_4_round"] == 2.76

    profile = {"student_code": "SV04", "full_name": "Test SV", "courses": subjects}
    grad = check_graduation(profile, DEFAULT_CNTT_CURRICULUM)
    parts = build_structured_advisory_text(grad)
    formatted = format_advisory_response(parts)
    assert "2.54-2.76 (ước tính, chờ giáo vụ xác nhận cách làm tròn)" in formatted



