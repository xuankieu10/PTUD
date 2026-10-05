"""
Module lọc môn không đạt theo quy tắc nghiệp vụ:
- Logic: Một môn bị coi là "không đạt" nếu:
    (diem < 4.0) HOẶC (vùng text của môn khớp với vùng màu đỏ phát hiện được).
- Viết bằng code Python thuần túy, không để AI tự quyết định.
- Xuất kết quả ra file JSON và file CSV (UTF-8-SIG chuẩn cho Excel tiếng Việt).
"""

import csv
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from backend.red_detector import is_marked_red

logger = logging.getLogger(__name__)

PASSING_GRADE_THRESHOLD = 4.0


def evaluate_subject(
    subject: Dict[str, Any],
    red_regions: Optional[List[Tuple[int, int, int, int]]] = None
) -> Dict[str, Any]:
    """
    Đánh giá một môn học có đạt hay không:
    - Quy tắc: Môn bị coi là KHÔNG ĐẠT khi và chỉ khi: điểm số < 4.0 HOẶC bị đánh dấu đỏ.
    """
    mon = subject.get("mon", "Chưa rõ tên môn")
    raw_diem = subject.get("diem")
    bbox = subject.get("bbox")

    # 1. Xử lý điểm số an toàn
    diem_val = None
    try:
        if raw_diem is not None and str(raw_diem).strip() != "":
            # Xử lý trường hợp có dấu phẩy ví dụ "8,5"
            clean_diem = str(raw_diem).replace(",", ".").strip()
            diem_val = float(clean_diem)
    except (ValueError, TypeError):
        pass

    # 2. Phát hiện vùng đỏ
    is_red = False
    if bbox and red_regions:
        is_red = is_marked_red(bbox, red_regions)

    # 3. Phân tích kết quả
    is_failed = False
    is_low_grade = False
    reason_parts = []

    if diem_val is None:
        is_failed = True
        reason_parts.append("Điểm không xác định (Vắng/M/Lỗi)")
    elif diem_val < PASSING_GRADE_THRESHOLD:
        is_failed = True
        is_low_grade = True
        reason_parts.append(f"Điểm < {PASSING_GRADE_THRESHOLD}")

    if is_red:
        is_failed = True
        reason_parts.append("Được đánh dấu màu đỏ")

    status_str = "Không đạt" if is_failed else "Đạt"
    reason_str = " | ".join(reason_parts) if reason_parts else "Đạt yêu cầu"

    result = {
        "mon": mon,
        "diem": round(diem_val, 2) if diem_val is not None else 0.0,
        "trang_thai": status_str,
        "is_failed": is_failed,
        "ly_do": reason_str,
        "is_red_marked": is_red,
        "is_low_grade": is_low_grade
    }

    if bbox:
        result["bbox"] = bbox

    return result


def filter_grades(
    subjects: List[Dict[str, Any]],
    red_regions: Optional[List[Tuple[int, int, int, int]]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Lọc danh sách môn học, trả về:
    - Danh sách môn KHÔNG ĐẠT
    - Danh sách toàn bộ môn đã được gán nhãn trạng thái và lý do
    
    Args:
        subjects: Danh sách môn học trích xuất [{"mon": ..., "diem": ...}]
        red_regions: Danh sách bounding box màu đỏ từ OpenCV
        
    Returns:
        (failed_subjects, all_evaluated_subjects)
    """
    failed_subjects: List[Dict[str, Any]] = []
    all_evaluated: List[Dict[str, Any]] = []

    for s in subjects:
        evaluated = evaluate_subject(s, red_regions)
        all_evaluated.append(evaluated)
        if evaluated["is_failed"]:
            failed_subjects.append(evaluated)

    logger.info(
        f"Kết quả lọc: {len(failed_subjects)}/{len(subjects)} môn không đạt "
        f"(ngưỡng điểm < {PASSING_GRADE_THRESHOLD} hoặc có dấu đỏ)."
    )
    return failed_subjects, all_evaluated


def export_to_json(data: List[Dict[str, Any]], output_path: str) -> None:
    """
    Lưu danh sách môn không đạt ra file JSON định dạng đẹp, hỗ trợ ký tự tiếng Việt.
    """
    # Chỉ lưu các trường cần thiết ra file kết quả
    export_list = [
        {
            "mon": item["mon"],
            "diem": item["diem"],
            "trang_thai": item.get("trang_thai", "Không đạt"),
            "ly_do": item.get("ly_do", "")
        }
        for item in data
    ]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_list, f, ensure_ascii=False, indent=2)

    logger.info(f"Đã lưu kết quả JSON tại: {output_path}")


def export_to_csv(data: List[Dict[str, Any]], output_path: str) -> None:
    """
    Lưu danh sách môn không đạt ra file CSV chuẩn UTF-8-SIG để Excel hiển thị đúng tiếng Việt.
    """
    fieldnames = ["STT", "Môn học", "Điểm", "Trạng thái", "Lý do không đạt"]

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, item in enumerate(data, start=1):
            writer.writerow({
                "STT": idx,
                "Môn học": item["mon"],
                "Điểm": item["diem"],
                "Trạng thái": item.get("trang_thai", "Không đạt"),
                "Lý do không đạt": item.get("ly_do", "")
            })

    logger.info(f"Đã lưu kết quả CSV tại: {output_path}")
