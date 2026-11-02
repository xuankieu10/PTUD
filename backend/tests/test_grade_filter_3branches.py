"""
backend/tests/test_grade_filter_3branches.py
Kiểm thử 3 nhánh phân loại môn không đạt theo Quy chế đào tạo (Chương III – Điều 19 & Chương II – Điều 12):
1. Bị cấm thi: vắng quá 20%, điểm thành phần/quá trình dưới 2.0, hoặc cờ cấm thi
2. Được đăng ký thi lần 2 (đầu học kỳ sau) hoặc học lại: điểm < 4.0 nhưng có xác nhận đủ điều kiện dự thi
3. Cần học lại hoặc thi lại: dữ liệu không đủ để phân biệt cấm thi hay không (kèm nhắc xác nhận với giáo vụ)
"""

import pytest
from backend.grade_filter import classify_failure_reason, evaluate_subject, PASSING_GRADE_THRESHOLD


def test_passing_grade_threshold_is_4():
    """Đảm bảo ngưỡng điểm không đạt trong hệ thống là < 4.0 (thang 10 điểm F)."""
    assert PASSING_GRADE_THRESHOLD == 4.0


def test_classify_branch_1_cam_thi_vang_qua_20():
    """Nhánh 1: Sinh viên vắng mặt quá 20% -> Bị cấm thi, cần đăng ký học lại."""
    sub1 = {"name": "Lập trình C", "grade": 3.0, "vang_qua_20": True}
    assert classify_failure_reason(sub1) == "Bị cấm thi, cần đăng ký học lại"

    sub2 = {"name": "Mạng máy tính", "grade": 2.5, "attendance": "vắng quá 20% số tiết"}
    assert classify_failure_reason(sub2) == "Bị cấm thi, cần đăng ký học lại"

    sub3 = {"name": "Hệ điều hành", "grade": 3.5, "ti_le_vang": 0.25}
    assert classify_failure_reason(sub3) == "Bị cấm thi, cần đăng ký học lại"


def test_classify_branch_1_cam_thi_diem_thanh_phan_duoi_2():
    """Nhánh 1: Điểm thành phần / quá trình / giữa kỳ < 2.0 -> Bị cấm thi, cần đăng ký học lại."""
    sub1 = {"name": "Cấu trúc dữ liệu", "grade": 3.0, "diem_thanh_phan": 1.5}
    assert classify_failure_reason(sub1) == "Bị cấm thi, cần đăng ký học lại"

    sub2 = {"name": "Toán rời rạc", "grade": 2.0, "diem_giua_ky": "1,8"}
    assert classify_failure_reason(sub2) == "Bị cấm thi, cần đăng ký học lại"

    sub3 = {"name": "Cơ sở dữ liệu", "grade": 3.5, "ly_do": "Cấm thi do điểm quá trình dưới 2.0"}
    assert classify_failure_reason(sub3) == "Bị cấm thi, cần đăng ký học lại"


def test_classify_branch_2_duoc_thi_lai_lan_2():
    """Nhánh 2: Điểm không đạt nhưng đủ điều kiện dự thi -> Được đăng ký thi lần 2 hoặc học lại."""
    sub1 = {"name": "Giải tích 1", "grade": 3.5, "cam_thi": False}
    assert classify_failure_reason(sub1) == "Được đăng ký thi lần 2 (đầu học kỳ sau) hoặc học lại"

    sub2 = {"name": "Đại số tuyến tính", "grade": 3.0, "duoc_thi_lai": True}
    assert classify_failure_reason(sub2) == "Được đăng ký thi lần 2 (đầu học kỳ sau) hoặc học lại"

    sub3 = {"name": "Vật lý đại cương", "grade": 2.5, "is_eligible_reexam": True}
    assert classify_failure_reason(sub3) == "Được đăng ký thi lần 2 (đầu học kỳ sau) hoặc học lại"


def test_classify_branch_3_chua_du_du_lieu():
    """Nhánh 3: Dữ liệu OCR hoặc điểm số thông thường không có thông tin cấm thi/thi lại -> Cần học lại hoặc thi lại."""
    sub1 = {"name": "Lập trình Web", "grade": 3.5}
    assert classify_failure_reason(sub1) == "Cần học lại hoặc thi lại"

    sub2 = {"name": "An toàn thông tin", "grade": 2.0, "filter_reason": "Điểm dưới 4.0"}
    assert classify_failure_reason(sub2) == "Cần học lại hoặc thi lại"


def test_evaluate_subject_integration():
    """Tích hợp kiểm tra evaluate_subject trả về is_failed và phan_loai đúng chuẩn."""
    sub_failed = {"mon": "Kỹ thuật phần mềm", "diem": 3.0, "cam_thi": True}
    res_failed = evaluate_subject(sub_failed)
    assert res_failed["is_failed"] is True
    assert res_failed["phan_loai"] == "Bị cấm thi, cần đăng ký học lại"
    assert res_failed["nhan_xu_ly"] == "Bị cấm thi, cần đăng ký học lại"

    sub_eligible = {"mon": "Hệ quản trị CSDL", "diem": 3.5, "duoc_thi_lai": True}
    res_eligible = evaluate_subject(sub_eligible)
    assert res_eligible["is_failed"] is True
    assert res_eligible["phan_loai"] == "Được đăng ký thi lần 2 (đầu học kỳ sau) hoặc học lại"

    sub_unknown = {"mon": "Mạng máy tính", "diem": 2.5}
    res_unknown = evaluate_subject(sub_unknown)
    assert res_unknown["is_failed"] is True
    assert res_unknown["phan_loai"] == "Cần học lại hoặc thi lại"

    sub_passed = {"mon": "Pháp luật đại cương", "diem": 6.5}
    res_passed = evaluate_subject(sub_passed)
    assert res_passed["is_failed"] is False
    assert res_passed["phan_loai"] == "Đạt yêu cầu"
