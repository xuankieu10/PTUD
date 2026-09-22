"""
Module chuẩn hóa dữ liệu kết quả học tập sang JSON schema cố định:
- Nhận đầu vào là kết quả từ pipeline / grade_filter hiện có (không sửa code cũ).
- Chuẩn hóa các trường về đúng cấu trúc:
  + student_id: string | null
  + semester_current: string | null
  + courses: danh sách môn học với status ("passed" | "failed" | "not_taken")
  + summary: gpa, total_credits_earned, total_credits_failed
- Giữ nguyên quy tắc: Nếu field nào code cũ không có thì trả null, không tự bịa.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Union

# Tái sử dụng trực tiếp logic và hằng số từ module cũ, KHÔNG sửa code cũ
from backend.grade_filter import PASSING_GRADE_THRESHOLD, evaluate_subject

logger = logging.getLogger(__name__)


def normalize_course_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chuẩn hóa 1 bản ghi môn học sang đúng schema:
    {
      "code": string,
      "name": string,
      "credits": int,
      "grade": float | null,
      "status": "passed" | "failed" | "not_taken",
      "semester": string | null,
      "retake_count": int
    }
    """
    # 1. Mã môn học (code)
    code_raw = (
        item.get("code")
        or item.get("ma_mon")
        or item.get("ma")
        or item.get("ma_hoc_phan")
    )
    code = str(code_raw).strip() if code_raw is not None else ""

    # 2. Tên môn học (name)
    name_raw = (
        item.get("name")
        or item.get("mon")
        or item.get("ten_mon")
        or item.get("ten_mon_hoc")
    )
    name = str(name_raw).strip() if name_raw is not None else ""

    # 3. Số tín chỉ (credits)
    credits_raw = (
        item.get("credits")
        if "credits" in item
        else (
            item.get("so_tin_chi")
            or item.get("tin_chi")
            or item.get("he_so")
            or item.get("stc")
        )
    )
    try:
        credits_val = int(credits_raw) if credits_raw is not None else 0
    except (ValueError, TypeError):
        credits_val = 0

    # 4. Điểm số (grade)
    grade_raw = (
        item.get("grade")
        if "grade" in item
        else (
            item.get("diem")
            if "diem" in item
            else item.get("diem_so")
        )
    )
    grade_val: Optional[float] = None
    if grade_raw is not None:
        try:
            # Xử lý trường hợp chuỗi số dùng dấu phẩy '7,5'
            clean_grade = str(grade_raw).replace(",", ".").strip()
            grade_val = round(float(clean_grade), 2)
        except (ValueError, TypeError):
            grade_val = None

    # 5. Trạng thái môn học (status: "passed" | "failed" | "not_taken")
    # Ưu tiên cờ is_failed hoặc trạng thái đã được evaluate_subject đánh giá
    is_failed_flag = item.get("is_failed")
    trang_thai_str = str(item.get("trang_thai", "")).strip().lower()

    if is_failed_flag is True or "không đạt" in trang_thai_str or "failed" in trang_thai_str:
        status = "failed"
    elif is_failed_flag is False or "đạt" in trang_thai_str or "passed" in trang_thai_str:
        status = "passed"
    elif grade_val is not None:
        # Dùng ngưỡng chuẩn PASSING_GRADE_THRESHOLD = 4.0 từ code cũ
        status = "failed" if grade_val < PASSING_GRADE_THRESHOLD else "passed"
    else:
        # Nếu hoàn toàn không có điểm
        status = "not_taken"

    # 6. Học kỳ của môn (semester)
    semester_raw = (
        item.get("semester")
        or item.get("hoc_ky")
        or item.get("ky")
    )
    semester = str(semester_raw).strip() if semester_raw is not None else None

    # 7. Số lần học lại (retake_count)
    retake_raw = (
        item.get("retake_count")
        if "retake_count" in item
        else (
            item.get("so_lan_hoc_lai")
            or item.get("hoc_lai")
        )
    )
    try:
        retake_count = int(retake_raw) if retake_raw is not None else 0
    except (ValueError, TypeError):
        retake_count = 0

    return {
        "code": code,
        "name": name,
        "credits": credits_val,
        "grade": grade_val,
        "status": status,
        "semester": semester,
        "retake_count": retake_count
    }


def calculate_summary(courses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Tính toán phần summary:
    - gpa: Điểm trung bình có trọng số theo tín chỉ (hoặc trung bình cộng nếu không có tín chỉ)
    - total_credits_earned: Tổng số tín chỉ của các môn đạt ("passed")
    - total_credits_failed: Tổng số tín chỉ của các môn không đạt ("failed")
    """
    total_credits_earned = sum(c["credits"] for c in courses if c["status"] == "passed")
    total_credits_failed = sum(c["credits"] for c in courses if c["status"] == "failed")

    # Tính GPA
    courses_with_grades_and_credits = [
        c for c in courses
        if c["grade"] is not None and c["credits"] > 0
    ]

    if courses_with_grades_and_credits:
        # Trường hợp 1: Có đầy đủ điểm và tín chỉ -> tính điểm trung bình tích lũy theo trọng số
        total_points = sum(c["grade"] * c["credits"] for c in courses_with_grades_and_credits)
        total_creds = sum(c["credits"] for c in courses_with_grades_and_credits)
        gpa = round(total_points / total_creds, 2) if total_creds > 0 else None
    else:
        # Trường hợp 2: Có điểm nhưng không có trường tín chỉ -> tính trung bình cộng thông thường
        courses_with_grades = [c for c in courses if c["grade"] is not None]
        if courses_with_grades:
            gpa = round(sum(c["grade"] for c in courses_with_grades) / len(courses_with_grades), 2)
        else:
            gpa = None

    return {
        "gpa": gpa,
        "total_credits_earned": total_credits_earned,
        "total_credits_failed": total_credits_failed
    }


def normalize_transcript(
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    student_id: Optional[str] = None,
    semester_current: Optional[str] = None
) -> Dict[str, Any]:
    """
    Hàm chính chuyển đổi output hiện tại sang cấu trúc JSON schema cố định:
    
    {
      "student_id": string | null,
      "semester_current": string | null,
      "courses": [...],
      "summary": {
        "gpa": float | null,
        "total_credits_earned": int,
        "total_credits_failed": int
      }
    }
    
    Args:
        data: Kết quả từ run_pipeline, danh sách all_subjects, hoặc list các môn học
        student_id: Mã sinh viên (nếu có, không có sẽ trả null)
        semester_current: Học kỳ hiện tại (nếu có, không có sẽ trả null)
        
    Returns:
        Dict đúng chuẩn JSON schema yêu cầu
    """
    raw_courses: List[Dict[str, Any]] = []

    # 1. Trích xuất danh sách môn học từ các định dạng đầu ra của code cũ
    if isinstance(data, list):
        raw_courses = data
    elif isinstance(data, dict):
        # Trích xuất student_id và semester_current nếu đã có trong dict
        if student_id is None:
            student_id = data.get("student_id") or data.get("mssv") or data.get("ma_sinh_vien")
        if semester_current is None:
            semester_current = data.get("semester_current") or data.get("hoc_ky_hien_tai") or data.get("hoc_ky")

        # Tìm danh sách môn trong các key thường gặp của pipeline cũ
        if "all_subjects" in data and isinstance(data["all_subjects"], list):
            raw_courses = data["all_subjects"]
        elif "courses" in data and isinstance(data["courses"], list):
            raw_courses = data["courses"]
        elif "subjects" in data and isinstance(data["subjects"], list):
            raw_courses = data["subjects"]
        elif "failed_subjects" in data and isinstance(data["failed_subjects"], list):
            raw_courses = data["failed_subjects"]

    # 2. Chuẩn hóa từng môn học
    courses = [normalize_course_item(item) for item in raw_courses if isinstance(item, dict)]

    # 3. Tính toán tổng hợp summary
    summary = calculate_summary(courses)

    # 4. Chuẩn hóa student_id và semester_current (nếu không có thì trả null, không tự bịa)
    final_student_id = str(student_id).strip() if student_id is not None else None
    final_semester_current = str(semester_current).strip() if semester_current is not None else None

    result = {
        "student_id": final_student_id,
        "semester_current": final_semester_current,
        "courses": courses,
        "summary": summary
    }

    logger.info(
        f"Đã chuẩn hóa {len(courses)} môn học. "
        f"Số tín chỉ đạt: {summary['total_credits_earned']}, "
        f"Số tín chỉ không đạt: {summary['total_credits_failed']}, "
        f"GPA: {summary['gpa']}."
    )
    return result


def normalize_to_json(
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    student_id: Optional[str] = None,
    semester_current: Optional[str] = None,
    indent: int = 2
) -> str:
    """
    Hàm tiện ích chuyển đổi và xuất thẳng ra chuỗi JSON định dạng chuẩn.
    """
    normalized_dict = normalize_transcript(data, student_id=student_id, semester_current=semester_current)
    return json.dumps(normalized_dict, ensure_ascii=False, indent=indent)
