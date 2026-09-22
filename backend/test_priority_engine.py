"""
Unit tests cho priority_engine.py
"""

import pytest
from backend.priority_engine import rank_priority, build_blocked_map

@pytest.fixture
def sample_curriculum():
    return [
        {
            "ma_mon": "CS101",
            "ten_mon": "Nhập môn Lập trình",
            "tin_chi": 3,
            "mon_tien_quyet": [],
            "hoc_ky_de_xuat": 1
        },
        {
            "ma_mon": "CS102",
            "ten_mon": "Cấu trúc dữ liệu",
            "tin_chi": 3,
            "mon_tien_quyet": ["CS101"],
            "hoc_ky_de_xuat": 2
        },
        {
            "ma_mon": "CS103",
            "ten_mon": "Lập trình hướng đối tượng",
            "tin_chi": 3,
            "mon_tien_quyet": ["CS101"],
            "hoc_ky_de_xuat": 2
        },
        {
            "ma_mon": "CS201",
            "ten_mon": "Cơ sở dữ liệu",
            "tin_chi": 4,
            "mon_tien_quyet": ["CS102"],
            "hoc_ky_de_xuat": 3
        },
        {
            "ma_mon": "MATH101",
            "ten_mon": "Giải tích 1",
            "tin_chi": 3,
            "mon_tien_quyet": [],
            "hoc_ky_de_xuat": 1
        }
    ]


def test_complex_prereqs(sample_curriculum):
    """
    Test 1: Môn có nhiều tiên quyết phức tạp.
    CS101 là tiên quyết của CS102, CS103 nên sẽ có mức độ ưu tiên rất cao.
    CS102 là tiên quyết của CS201 (1 môn).
    MATH101 không là tiên quyết của môn nào.
    """
    failed_courses = [
        {"mon_hoc": "Nhập môn Lập trình", "ma_mon": "CS101", "tin_chi": 3, "diem": 3.0, "hoc_ky": "HK1"},
        {"mon_hoc": "Cấu trúc dữ liệu", "ma_mon": "CS102", "tin_chi": 3, "diem": 2.5, "hoc_ky": "HK2"},
        {"mon_hoc": "Giải tích 1", "ma_mon": "MATH101", "tin_chi": 3, "diem": 3.5, "hoc_ky": "HK1"}
    ]
    
    results = rank_priority(failed_courses, sample_curriculum)
    
    assert len(results) == 3
    # CS101 blocked: CS102, CS103 -> 2 môn
    # CS102 blocked: CS201 -> 1 môn
    # MATH101 blocked: 0 môn
    
    ma_mon_order = [r["ma_mon"] for r in results]
    assert ma_mon_order == ["CS101", "CS102", "MATH101"], "Môn có nhiều tiên quyết hơn phải đứng trước"
    
    cs101_result = results[0]
    assert "CS102" in cs101_result["mon_bi_chan"]
    assert "CS103" in cs101_result["mon_bi_chan"]
    assert cs101_result["do_uu_tien"] > results[1]["do_uu_tien"]
    assert "Là tiên quyết của 2 môn" in cs101_result["ly_do"]


def test_course_not_in_curriculum(sample_curriculum):
    """
    Test 2: Môn không nằm trong chương trình.
    """
    failed_courses = [
        {"mon_hoc": "Giải tích 1", "ma_mon": "MATH101", "tin_chi": 3, "diem": 3.5, "hoc_ky": "HK1"},
        {"mon_hoc": "Môn lạ", "ma_mon": "UNKNOWN99", "tin_chi": 2, "diem": 1.0, "hoc_ky": "HK1"}
    ]
    
    results = rank_priority(failed_courses, sample_curriculum)
    
    unknown_result = next(r for r in results if r["ma_mon"] == "UNKNOWN99")
    
    assert unknown_result["mon_bi_chan"] == [], "Môn không trong curriculum không thể chặn môn nào"
    assert unknown_result["do_uu_tien"] > 0
    assert "Không rõ học kỳ đề xuất" in unknown_result["ly_do"]
    assert "Điểm quá thấp" in unknown_result["ly_do"] # vì điểm 1.0


def test_real_output_integration():
    """
    Test 3: Tích hợp output thật từ filter_grades.
    Giả lập cấu trúc dữ liệu trả về từ filter_grades.
    """
    # format từ hệ thống trước đó
    failed_courses = [
        {"mon_hoc": "Triết học Mác", "ma_mon": "LLCT101", "tin_chi": 3, "diem": 2.0, "hoc_ky": "HK1"},
        {"mon_hoc": "Lập trình Web", "ma_mon": "SWE102", "tin_chi": 4, "diem": 3.8, "hoc_ky": "HK4"}
    ]
    
    curriculum_data = [
        {"ma_mon": "LLCT101", "ten_mon": "Triết học Mác", "tin_chi": 3, "mon_tien_quyet": [], "hoc_ky_de_xuat": 1},
        {"ma_mon": "SWE102", "ten_mon": "Lập trình Web", "tin_chi": 4, "mon_tien_quyet": [], "hoc_ky_de_xuat": 4},
        {"ma_mon": "LLCT102", "ten_mon": "Kinh tế chính trị", "tin_chi": 2, "mon_tien_quyet": ["LLCT101"], "hoc_ky_de_xuat": 2}
    ]
    
    results = rank_priority(failed_courses, curriculum_data)
    
    assert len(results) == 2
    # LLCT101: 1 bị chặn, 3TC, HK1, điểm thấp
    # SWE102: 0 bị chặn, 4TC, HK4, điểm cao hơn
    
    llct = next(r for r in results if r["ma_mon"] == "LLCT101")
    swe = next(r for r in results if r["ma_mon"] == "SWE102")
    
    assert "LLCT102" in llct["mon_bi_chan"]
    assert llct["do_uu_tien"] >= 1.0 and llct["do_uu_tien"] <= 10.0
    assert "Điểm quá thấp" in llct["ly_do"] # điểm 2.0 <= 2.0
    
    assert swe["mon_bi_chan"] == []
    assert swe["do_uu_tien"] >= 1.0 and swe["do_uu_tien"] <= 10.0
