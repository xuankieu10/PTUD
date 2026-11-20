"""
backend/tests/test_graduation_checker.py
Bộ unit test độc lập kiểm tra tính chính xác của hàm check_graduation bằng CODE thuần túy.
KHÔNG gọi LLM, KHÔNG gọi database bên ngoài, thực thi nhanh dưới 1 giây.
"""

import pytest
from backend.app.services.graduation_checker import (
    check_graduation,
    calculate_academic_summary,
    convert_score_to_scale_4
)


@pytest.fixture
def sample_curriculum():
    """Chương trình đào tạo mẫu có quan hệ tiên quyết và số tín chỉ chuẩn"""
    return [
        {"ma_mon": "CS101", "ten_mon": "Nhập môn lập trình", "tin_chi": 3, "hoc_ky_de_xuat": 1, "is_required": True, "mon_tien_quyet": []},
        {"ma_mon": "MATH101", "ten_mon": "Toán cao cấp 1", "tin_chi": 4, "hoc_ky_de_xuat": 1, "is_required": True, "mon_tien_quyet": []},
        {"ma_mon": "CS102", "ten_mon": "Kỹ thuật lập trình", "tin_chi": 3, "hoc_ky_de_xuat": 2, "is_required": True, "mon_tien_quyet": ["CS101"]},
        {"ma_mon": "CS201", "ten_mon": "Cấu trúc dữ liệu và giải thuật", "tin_chi": 4, "hoc_ky_de_xuat": 3, "is_required": True, "mon_tien_quyet": ["CS102"]},
        {"ma_mon": "CS202", "ten_mon": "Cơ sở dữ liệu", "tin_chi": 3, "hoc_ky_de_xuat": 3, "is_required": True, "mon_tien_quyet": []},
        {"ma_mon": "CS301", "ten_mon": "Lập trình Web", "tin_chi": 3, "hoc_ky_de_xuat": 4, "is_required": True, "mon_tien_quyet": ["CS102"]},
        {"ma_mon": "CS401", "ten_mon": "Thực tập doanh nghiệp", "tin_chi": 4, "hoc_ky_de_xuat": 7, "is_required": True, "mon_tien_quyet": []},
        {"ma_mon": "CS402", "ten_mon": "Khóa luận tốt nghiệp", "tin_chi": 8, "hoc_ky_de_xuat": 8, "is_required": True, "mon_tien_quyet": ["CS401"]},
    ]


def test_scale_4_conversion():
    """Kiểm tra quy đổi thang 10 sang thang 4 theo Điều 11"""
    assert convert_score_to_scale_4(9.0) == (4.0, "A")
    assert convert_score_to_scale_4(8.5) == (4.0, "A")
    assert convert_score_to_scale_4(8.2) == (3.5, "B+")
    assert convert_score_to_scale_4(7.5) == (3.0, "B")
    assert convert_score_to_scale_4(7.0) == (3.0, "B")
    assert convert_score_to_scale_4(6.7) == (2.5, "C+")
    assert convert_score_to_scale_4(6.0) == (2.0, "C")
    assert convert_score_to_scale_4(5.5) == (2.0, "C")
    assert convert_score_to_scale_4(5.2) == (1.5, "D+")
    assert convert_score_to_scale_4(4.5) == (1.0, "D")
    assert convert_score_to_scale_4(4.0) == (1.0, "D")
    assert convert_score_to_scale_4(3.9) == (0.0, "F")
    assert convert_score_to_scale_4(0.0) == (0.0, "F")


def test_eligible_student(sample_curriculum):
    """Sinh viên hoàn thành đủ điều kiện tốt nghiệp (150 TC, GPA >= 5.0, đủ 5 chứng chỉ)"""
    # Giả lập sinh viên đã hoàn thành toàn bộ các môn trong CTĐT và thêm các môn tích lũy đủ 150 TC
    passed_courses = [
        {"ma_mon": c["ma_mon"], "ten_mon": c["ten_mon"], "tin_chi": c["tin_chi"], "diem": 7.5}
        for c in sample_curriculum
    ]
    # Bổ sung các môn khác để đạt đủ 150 tín chỉ
    passed_courses.append({"ma_mon": "ELECTIVE_ALL", "ten_mon": "Các môn tự chọn và chuyên ngành", "tin_chi": 118, "diem": 7.0})

    profile = {
        "student_code": "12100123",
        "full_name": "Nguyễn Văn A",
        "major": "Công nghệ thông tin",
        "cohort": "2021",
        "courses": passed_courses,
        "certificates": {
            "has_english": True,
            "has_it": True,
            "has_gdqp": True,
            "has_gdtc": True,
            "has_soft_skills": True
        }
    }

    res = check_graduation(profile, sample_curriculum, current_semester=8, required_credits=150)

    assert res["is_eligible"] is True
    assert res["student_summary"]["passed_credits"] >= 150
    assert res["student_summary"]["credits_missing"] == 0
    assert res["student_summary"]["gpa_10"] >= 5.0
    assert len(res["failed_courses"]) == 0
    assert len(res["missing_required_courses"]) == 0
    assert len(res["proposed_plan"]) == 0  # Không cần thêm kế hoạch vì đã hoàn thành


def test_failed_prerequisite_scheduling(sample_curriculum):
    """
    Sinh viên nợ môn tiên quyết (CS101 Nhập môn lập trình) ở học kỳ 1.
    Kế hoạch đề xuất BẮT BUỘC phải xếp CS101 học lại ở học kỳ đầu tiên,
    và các môn phụ thuộc (CS102, CS201, CS301) phải được xếp ở các học kỳ sau CS101.
    """
    profile = {
        "student_code": "12100999",
        "full_name": "Trần Văn B",
        "major": "Công nghệ thông tin",
        "cohort": "2022",
        "courses": [
            {"ma_mon": "CS101", "ten_mon": "Nhập môn lập trình", "tin_chi": 3, "diem": 3.0}, # NỢ MÔN TIÊN QUYẾT
            {"ma_mon": "MATH101", "ten_mon": "Toán cao cấp 1", "tin_chi": 4, "diem": 6.5}, # ĐẠT
        ],
        "certificates": {"has_english": False, "has_it": True, "has_gdqp": True, "has_gdtc": True, "has_soft_skills": True}
    }

    res = check_graduation(profile, sample_curriculum, current_semester=2, required_credits=32)

    assert res["is_eligible"] is False
    assert len(res["failed_courses"]) == 1
    assert res["failed_courses"][0]["ma_mon"] == "CS101"

    # Kiểm tra kế hoạch đề xuất:
    plan = res["proposed_plan"]
    assert len(plan) > 0

    # Học kỳ đầu tiên trong kế hoạch phải chứa CS101 (học lại)
    first_sem_courses = [c["ma_mon"] for c in plan[0]["courses"]]
    assert "CS101" in first_sem_courses

    # CS102 (phụ thuộc CS101) không được nằm cùng học kỳ với CS101 hoặc trước CS101
    assert "CS102" not in first_sem_courses

    # CS102 phải xuất hiện ở học kỳ sau học kỳ chứa CS101
    found_cs101_sem = -1
    found_cs102_sem = -1
    found_cs201_sem = -1

    for sem_idx, sem in enumerate(plan):
        codes = [c["ma_mon"] for c in sem["courses"]]
        if "CS101" in codes:
            found_cs101_sem = sem_idx
        if "CS102" in codes:
            found_cs102_sem = sem_idx
        if "CS201" in codes:
            found_cs201_sem = sem_idx

    assert found_cs101_sem != -1
    assert found_cs102_sem > found_cs101_sem, "CS102 phải được xếp sau học kỳ hoàn thành CS101"
    if found_cs201_sem != -1:
        assert found_cs201_sem > found_cs102_sem, "CS201 phải được xếp sau học kỳ hoàn thành CS102"


def test_credit_limit_and_split_semesters():
    """
    Kiểm tra giới hạn tín chỉ mỗi kỳ (credit cap: max 20 TC/kỳ chính, max 8 TC/kỳ hè).
    Khi sinh viên cần học 35 tín chỉ, kế hoạch phải chia thành nhiều học kỳ,
    mỗi kỳ không được vượt quá số tín chỉ tối đa quy định.
    """
    large_curriculum = [
        {"ma_mon": f"SUBJ_{i}", "ten_mon": f"Môn học {i}", "tin_chi": 4, "hoc_ky_de_xuat": 5, "is_required": True, "mon_tien_quyet": []}
        for i in range(1, 10)  # 9 môn x 4 TC = 36 tín chỉ
    ]

    profile = {
        "student_code": "12100456",
        "full_name": "Lê Thị C",
        "major": "Công nghệ thông tin",
        "cohort": "2021",
        "courses": [],  # Chưa học môn nào trong số này
        "certificates": {"has_english": True, "has_it": True, "has_gdqp": True, "has_gdtc": True, "has_soft_skills": True}
    }

    res = check_graduation(profile, large_curriculum, current_semester=5, max_credits_per_semester=20, max_credits_summer=8, required_credits=36)

    plan = res["proposed_plan"]
    assert len(plan) >= 2, "36 tín chỉ với max 20 TC/kỳ phải chia làm ít nhất 2 kỳ"

    for sem in plan:
        if "hè" in sem["semester_name"].lower():
            assert sem["total_credits"] <= 8, f"Kỳ hè {sem['semester_name']} vượt quá 8 tín chỉ: {sem['total_credits']}"
        else:
            assert sem["total_credits"] <= 20, f"Kỳ chính {sem['semester_name']} vượt quá 20 tín chỉ: {sem['total_credits']}"


def test_missing_certificates():
    """Sinh viên đủ tín chỉ và GPA nhưng thiếu chứng chỉ chuẩn đầu ra"""
    profile = {
        "student_code": "12100789",
        "full_name": "Hoàng Văn D",
        "major": "Công nghệ thông tin",
        "cohort": "2021",
        "courses": [
            {"ma_mon": "CS101", "ten_mon": "Nhập môn lập trình", "tin_chi": 150, "diem": 8.0}
        ],
        "certificates": {
            "has_english": False, # THIẾU TIẾNG ANH
            "has_it": True,
            "has_gdqp": True,
            "has_gdtc": True,
            "has_soft_skills": False # THIẾU KỸ NĂNG MỀM
        }
    }

    res = check_graduation(profile, [], current_semester=8, required_credits=150)

    assert res["is_eligible"] is False
    assert res["certificates_status"]["english"] is False
    assert res["certificates_status"]["soft_skills"] is False
    assert res["certificates_status"]["it"] is True


def test_missing_curriculum_data_warning():
    """Kiểm tra việc phát hiện và cảnh báo thiếu dữ liệu trong CTĐT"""
    incomplete_curriculum = [
        {"ma_mon": "BAD_1", "ten_mon": "Môn thiếu tín chỉ", "tin_chi": None, "mon_tien_quyet": []},
        {"ma_mon": "", "ten_mon": "", "tin_chi": 3, "mon_tien_quyet": []}
    ]

    profile = {"courses": [], "certificates": {}}
    res = check_graduation(profile, incomplete_curriculum, current_semester=1)

    assert len(res["curriculum_missing_data"]) > 0
    assert any("thiếu số tín chỉ" in w for w in res["curriculum_missing_data"])


def test_duplicate_course_codes_supported():
    """Yêu cầu 4: Kiểm tra mã môn bị trùng (như 11105, 10207, 11100 trong PDF mẫu) không bị đè mất môn"""
    courses = [
        {"ma_mon": "11105", "ten_mon": "Mạng máy tính", "tin_chi": 3, "diem": 7.0},
        {"ma_mon": "11105", "ten_mon": "Thực hành Mạng máy tính", "tin_chi": 1, "diem": 8.0},
        {"ma_mon": "10207", "ten_mon": "Kiến trúc máy tính", "tin_chi": 3, "diem": 6.5},
        {"ma_mon": "10207", "ten_mon": "Thực hành Kiến trúc máy tính", "tin_chi": 1, "diem": 7.5},
    ]
    summary = calculate_academic_summary(courses)
    # Cả 4 môn khác tên dù trùng mã đều phải được tính tín chỉ đầy đủ
    assert summary["passed_credits"] == 3 + 1 + 3 + 1  # 8 tín chỉ
    assert summary["total_gpa_credits"] == 8


def test_zero_coefficient_and_condition_subjects_excluded():
    """Yêu cầu 5: Môn hệ số 0 và môn điều kiện (GDTC, GDQP) không bị tính vào tín chỉ tích lũy/GPA"""
    courses = [
        {"ma_mon": "CS101", "ten_mon": "Lập trình C", "tin_chi": 3, "diem": 8.0, "he_so": 1.0},
        {"ma_mon": "GDQP1", "ten_mon": "Giáo dục quốc phòng và an ninh 1", "tin_chi": 3, "diem": 8.5},
        {"ma_mon": "GDTC1", "ten_mon": "Giáo dục thể chất 1", "tin_chi": 1, "diem": 9.0},
        {"ma_mon": "ZERO1", "ten_mon": "Môn sinh hoạt hướng nghiệp", "tin_chi": 0, "diem": 10.0, "he_so": 0.0},
        {"ma_mon": "ZERO2", "ten_mon": "Môn ngoại khóa thử nghiệm", "tin_chi": 2, "diem": 7.0, "he_so": 0.0},
    ]
    summary = calculate_academic_summary(courses)
    # Chỉ duy nhất môn Lập trình C (3 tín chỉ) được tính vào tín chỉ tích lũy và GPA
    assert summary["passed_credits"] == 3
    assert summary["total_gpa_credits"] == 3
    assert summary["gpa_10"] == 8.0


def test_outside_curriculum_subject_excluded():
    """Yêu cầu 5: Môn ngoài CTĐT không được tính vào tín chỉ tích lũy/GPA"""
    courses = [
        {"ma_mon": "CS101", "ten_mon": "Cơ sở dữ liệu", "tin_chi": 3, "diem": 7.0},
        {"ma_mon": "OUT01", "ten_mon": "Dược lý học đại cương", "tin_chi": 3, "diem": 8.0, "is_outside_curriculum": True},
    ]
    summary = calculate_academic_summary(courses)
    assert summary["passed_credits"] == 3
    assert summary["total_gpa_credits"] == 3
    assert summary["gpa_10"] == 7.0


def test_missing_credits_and_none_grade_marked_unconfirmed():
    """
    Yêu cầu mới:
    1. Thiếu TC (tin_chi is None): không gán mặc định, không tính vào tích lũy/GPA, đưa vào unconfirmed_courses.
    2. Môn có diem=None: không xếp đạt/rớt, đưa vào mục cần xác nhận.
    """
    from backend.app.services.graduation_checker import build_structured_advisory_text

    curriculum = [
        {"ma_mon": "CS101", "ten_mon": "Cơ sở dữ liệu", "tin_chi": 3, "hoc_ky_de_xuat": 1, "is_required": True, "mon_tien_quyet": []},
        {"ma_mon": "CS102", "ten_mon": "Mạng máy tính", "tin_chi": 3, "hoc_ky_de_xuat": 2, "is_required": True, "mon_tien_quyet": []},
    ]

    profile = {
        "student_code": "12100111",
        "full_name": "Nguyễn Test",
        "major": "Công nghệ thông tin",
        "cohort": "2021",
        "courses": [
            {"ma_mon": "CS101", "ten_mon": "Cơ sở dữ liệu", "tin_chi": 3, "diem": 8.0},
            {"ma_mon": "CS999", "ten_mon": "Môn chưa có điểm", "tin_chi": 3, "diem": None}, # diem = None
            {"ma_mon": "CS888", "ten_mon": "Môn thiếu tín chỉ", "tin_chi": None, "diem": 7.5}, # tin_chi = None
        ],
        "certificates": {}
    }

    res = check_graduation(profile, curriculum, current_semester=3, required_credits=150)

    # 1. Chỉ duy nhất môn CS101 (3 TC, điểm 8.0) được tính vào tích lũy
    assert res["student_summary"]["passed_credits"] == 3
    assert res["student_summary"]["failed_credits"] == 0
    assert res["student_summary"]["gpa_10"] == 8.0

    # 2. Hai môn thiếu điểm và thiếu tín chỉ không được xếp vào failed_courses
    assert len(res["failed_courses"]) == 0

    # 3. Hai môn này được xếp vào unconfirmed_courses
    assert len(res["unconfirmed_courses"]) == 2
    unconfirmed_names = [u["ten_mon"] for u in res["unconfirmed_courses"]]
    assert "Môn chưa có điểm" in unconfirmed_names
    assert "Môn thiếu tín chỉ" in unconfirmed_names

    # 4. Bản tư vấn dạng text phải liệt kê các môn cần xác nhận
    text_dict = build_structured_advisory_text(res)
    assert "Môn chưa có điểm" in text_dict["part_2"]
    assert "Môn thiếu tín chỉ" in text_dict["part_2"]
    assert "cần xác nhận lại" in text_dict["part_2"]


def test_elective_branch_b_completion():
    """
    Yêu cầu F.5: Test nhánh tự chọn B:
    Sinh viên học 111089 (3 TC), 111084 (2 TC), 111061 (3 TC)
    - Được tính đủ 3 + 2 + 3 = 8 TC tự chọn vào passed_credits.
    - Không bị báo thiếu nhánh A (111043, 111071, 111088).
    - Không xuất hiện trong proposed_plan hay missing_required_courses.
    """
    from backend.app.services.graduation_checker import DEFAULT_CNTT_CURRICULUM

    profile = {
        "student_code": "12100999",
        "full_name": "Sinh viên Nhánh B",
        "major": "Công nghệ thông tin",
        "cohort": "2021",
        "courses": [
            {"ma_mon": "111089", "ten_mon": "Phân tích thiết kế hệ thống hướng quan hệ", "tin_chi": 3, "diem": 7.0},
            {"ma_mon": "111084", "ten_mon": "Lập trình Python trong thị giác máy tính", "tin_chi": 2, "diem": 8.0},
            {"ma_mon": "111061", "ten_mon": "Công nghệ Blockchain", "tin_chi": 3, "diem": 7.5},
        ],
        "certificates": {}
    }

    res = check_graduation(profile, DEFAULT_CNTT_CURRICULUM, current_semester=8, required_credits=150)

    # 1. Được tính đủ 3 + 2 + 3 = 8 TC
    assert res["student_summary"]["passed_credits"] == 8

    # 2. Không bị báo thiếu các môn nhánh A tương ứng
    missing_codes = [m.get("ma_mon") for m in res["missing_required_courses"]]

    # Nhánh A: 111043, 111071, 111088 không được nằm trong danh sách thiếu
    assert "111043" not in missing_codes
    assert "111071" not in missing_codes
    assert "111088" not in missing_codes

    # Nhánh B: cũng không bị báo thiếu
    assert "111089" not in missing_codes
    assert "111084" not in missing_codes
    assert "111061" not in missing_codes

    # 3. Kế hoạch đề xuất không xếp lại các môn nhánh A này
    planned_codes = []
    for sem in res["proposed_plan"]:
        for c in sem.get("courses", []):
            planned_codes.append(c.get("ma_mon"))
    assert "111043" not in planned_codes
    assert "111071" not in planned_codes
    assert "111088" not in planned_codes
