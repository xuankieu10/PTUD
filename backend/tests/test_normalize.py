"""
Bộ kiểm thử unit test cho module normalize.py:
- Test 1: Chuẩn hóa dữ liệu giả đầy đủ với 2 môn pass và 1 môn fail.
- Test 2: Kiểm tra xử lý các trường không có trong code cũ (trả về None / null, không tự bịa).
- Test 3: Tích hợp với output của module lọc điểm cũ (filter_grades) với 2 môn pass, 1 môn fail.
"""

import json
import pytest
from backend.normalize import normalize_transcript, normalize_to_json
from backend.grade_filter import filter_grades


def test_normalize_basic_two_pass_one_fail():
    """
    Test 1: Dữ liệu giả gồm 2 môn đạt và 1 môn không đạt có đầy đủ thông tin.
    Kiểm tra cấu trúc schema, phân loại trạng thái môn học và tính toán summary.
    """
    sample_data = {
        "student_id": "2211001",
        "semester_current": "HK1-2024",
        "courses": [
            {
                "code": "CS101",
                "name": "Cấu trúc dữ liệu và giải thuật",
                "credits": 3,
                "grade": 8.5,
                "semester": "HK1-2024",
                "retake_count": 0
            },
            {
                "code": "CS102",
                "name": "Cơ sở dữ liệu",
                "credits": 3,
                "grade": 7.0,
                "semester": "HK1-2024",
                "retake_count": 0
            },
            {
                "code": "MATH101",
                "name": "Toán rời rạc",
                "credits": 2,
                "grade": 3.5,  # Dưới 4.0 -> không đạt
                "semester": "HK1-2024",
                "retake_count": 1
            }
        ]
    }

    result = normalize_transcript(sample_data)

    # 1. Kiểm tra trường cấp cao
    assert result["student_id"] == "2211001"
    assert result["semester_current"] == "HK1-2024"
    assert len(result["courses"]) == 3

    # 2. Kiểm tra trạng thái 2 môn pass, 1 môn fail
    c1, c2, c3 = result["courses"]
    assert c1["name"] == "Cấu trúc dữ liệu và giải thuật"
    assert c1["status"] == "passed"
    assert c1["grade"] == 8.5

    assert c2["name"] == "Cơ sở dữ liệu"
    assert c2["status"] == "passed"
    assert c2["grade"] == 7.0

    assert c3["name"] == "Toán rời rạc"
    assert c3["status"] == "failed"
    assert c3["grade"] == 3.5
    assert c3["retake_count"] == 1

    # 3. Kiểm tra tính toán summary
    # total_credits_earned = 3 + 3 = 6
    assert result["summary"]["total_credits_earned"] == 6
    # total_credits_failed = 2
    assert result["summary"]["total_credits_failed"] == 2
    # GPA = (8.5 * 3 + 7.0 * 3 + 3.5 * 2) / 8 = (25.5 + 21.0 + 7.0) / 8 = 53.5 / 8 = 6.69
    assert result["summary"]["gpa"] == 6.69


def test_normalize_missing_fields_returns_null():
    """
    Test 2: Dữ liệu đầu vào bị thiếu nhiều trường (chỉ có tên môn và điểm).
    Đảm bảo các trường không có trong code cũ sẽ trả về None (null trong JSON), không tự bịa.
    """
    minimal_data = [
        {"mon": "Lập trình Web", "diem": 6.5},         # pass
        {"mon": "Trí tuệ nhân tạo", "diem": 9.0},      # pass
        {"mon": "Mạng máy tính", "diem": 2.0}          # fail (< 4.0)
    ]

    result = normalize_transcript(minimal_data)

    # Kiểm tra trường thiếu ở cấp độ sinh viên -> null
    assert result["student_id"] is None
    assert result["semester_current"] is None

    # Kiểm tra các trường môn học bị thiếu -> trả về null / default rỗng
    assert len(result["courses"]) == 3
    for course in result["courses"]:
        assert course["semester"] is None
        assert course["credits"] == 0
        assert course["retake_count"] == 0

    # Kiểm tra trạng thái môn
    assert result["courses"][0]["status"] == "passed"
    assert result["courses"][1]["status"] == "passed"
    assert result["courses"][2]["status"] == "failed"

    # Vì credits = 0 nên total_credits = 0, GPA tính theo trung bình cộng: (6.5 + 9.0 + 2.0) / 3 = 5.83
    assert result["summary"]["total_credits_earned"] == 0
    assert result["summary"]["total_credits_failed"] == 0
    assert result["summary"]["gpa"] == 5.83

    # Kiểm tra chuyển đổi sang chuỗi JSON hợp lệ
    json_str = normalize_to_json(minimal_data)
    parsed_back = json.loads(json_str)
    assert parsed_back["student_id"] is None
    assert parsed_back["courses"][0]["semester"] is None


def test_normalize_integration_with_grade_filter_output():
    """
    Test 3: Tích hợp trực tiếp với kết quả trả về từ hàm filter_grades của code cũ.
    Gọi lại module cũ, không sửa code cũ, chuyển đổi sang JSON schema cố định.
    """
    # Dữ liệu trích xuất kiểu cũ (2 môn đạt, 1 môn không đạt)
    raw_extracted_subjects = [
        {"mon": "Triết học Mác - Lênin", "diem": "8.0", "so_tin_chi": 3, "ma_mon": "TH01"},
        {"mon": "Tiếng Anh chuyên ngành", "diem": "7.5", "so_tin_chi": 4, "ma_mon": "TA01"},
        {"mon": "Vật lý đại cương", "diem": "3.0", "so_tin_chi": 2, "ma_mon": "VL01"}
    ]

    # Gọi hàm code cũ để kiểm tra
    failed_subjects, all_evaluated = filter_grades(raw_extracted_subjects)
    assert len(all_evaluated) == 3
    assert len(failed_subjects) == 1

    # Đưa vào module normalize (gọi lại logic evaluate_subject từ code cũ)
    normalized = normalize_transcript(
        raw_extracted_subjects,
        student_id="SV2022_001",
        semester_current="Học kỳ 2 (2024-2025)"
    )

    assert normalized["student_id"] == "SV2022_001"
    assert normalized["semester_current"] == "Học kỳ 2 (2024-2025)"
    assert len(normalized["courses"]) == 3

    # Kiểm tra phân loại 2 môn pass, 1 môn fail
    statuses = [c["status"] for c in normalized["courses"]]
    assert statuses == ["passed", "passed", "failed"]

    # Kiểm tra tổng tín chỉ: passed = 3 + 4 = 7; failed = 2
    assert normalized["summary"]["total_credits_earned"] == 7
    assert normalized["summary"]["total_credits_failed"] == 2

    # GPA = (8.0 * 3 + 7.5 * 4 + 3.0 * 2) / (3 + 4 + 2) = (24 + 30 + 6) / 9 = 60 / 9 = 6.67
    assert normalized["summary"]["gpa"] == 6.67
