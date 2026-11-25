"""
backend/app/services/graduation_checker.py
Bộ kiểm tra điều kiện tốt nghiệp và lập kế hoạch học tập đề xuất theo từng học kỳ
hoàn toàn bằng CODE (deterministic, không để LLM tự tính toán).

Quy tắc:
1. Mọi số liệu tính toán (tín chỉ, GPA, môn nợ, môn thiếu) tính bằng thuật toán chuẩn xác.
2. Tái sử dụng logic xếp hạng môn ưu tiên từ backend.priority_engine (đồ thị tiên quyết).
3. Đề xuất kế hoạch từng học kỳ tuân thủ:
   - Điều kiện tiên quyết (môn A phải học trước môn B).
   - Giới hạn tín chỉ mỗi học kỳ (kỳ chính tối đa 20 TC, kỳ hè tối đa 8 TC theo quy chế).
4. Nếu thiếu thông tin CTĐT (thiếu mã môn, thiếu quan hệ tiên quyết), nêu rõ chỗ thiếu cụ thể.
"""

from typing import List, Dict, Any, Optional, Set, Tuple, Union
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import math
import re
import logging

from backend.priority_engine import build_blocked_map, rank_priority
from backend.app.config import settings

logger = logging.getLogger(__name__)


def round_half_up(value: Union[float, Decimal, str, int], decimals: int = 2) -> float:
    """Làm tròn số học nửa lên (ROUND_HALF_UP) bằng Decimal chuẩn xác."""
    if value is None:
        return 0.0
    d = Decimal(str(value))
    target = Decimal("10") ** -decimals
    return float(d.quantize(target, rounding=ROUND_HALF_UP))

# Giới hạn tín chỉ & điều kiện cấu hình từ settings (hoặc ghi đè từ CTĐT)
DEFAULT_SUGGESTED_CREDITS_PER_SEMESTER = getattr(settings, "SUGGESTED_CREDITS_PER_SEMESTER", getattr(settings, "MAX_CREDITS_PER_SEMESTER", 20))
DEFAULT_SUGGESTED_CREDITS_SUMMER = getattr(settings, "SUGGESTED_CREDITS_SUMMER", getattr(settings, "MAX_CREDITS_SUMMER", 8))
DEFAULT_MAX_CREDITS_PER_SEMESTER = DEFAULT_SUGGESTED_CREDITS_PER_SEMESTER  # Alias tương thích ngược
DEFAULT_MAX_CREDITS_SUMMER = DEFAULT_SUGGESTED_CREDITS_SUMMER  # Alias tương thích ngược
DEFAULT_REQUIRED_CREDITS = getattr(settings, "REQUIRED_CREDITS", 150)
MIN_GRADUATION_GPA = getattr(settings, "MIN_GRADUATION_GPA", 5.0)  # Nguồn: tóm tắt trên trang web Khoa CNTT (chưa có văn bản gốc QĐ 1013)
MAX_STANDARD_SEMESTERS = getattr(settings, "MAX_STANDARD_SEMESTERS", 8)  # Nguồn: Niên giám 2023 Mục 7.1
MAX_EXTENDED_SEMESTERS = getattr(settings, "MAX_EXTENDED_SEMESTERS", 12)  # Nguồn: QĐ 22 Điều 3 Khoản 1


def convert_score_to_scale_4(score_10: float, use_plus_grades: bool = True, round_1dp: Optional[bool] = None) -> Tuple[float, str]:
    """
    Quy đổi điểm thang 10 sang thang 4 và điểm chữ theo Quy chế đào tạo LHU (Điều 11 Khoản 5 QĐ 22):
    - Bảng quy đổi chính thức 8 mức (Điều 11 Khoản 5):
      + 8.5 - 10.0: A  (4.0) - Đạt
      + 8.0 - 8.4:  B+ (3.5) - Đạt
      + 7.0 - 7.9:  B  (3.0) - Đạt
      + 6.5 - 6.9:  C+ (2.5) - Đạt
      + 5.5 - 6.4:  C  (2.0) - Đạt
      + 5.0 - 5.4:  D+ (1.5) - Đạt
      + 4.0 - 4.9:  D  (1.0) - Đạt
      + Dưới 4.0:   F  (0.0) - Không đạt
      
    - Mặc định use_plus_grades=True theo đúng chuẩn văn bản Điều 11 Khoản 5 QĐ 22.
    - Tùy chọn round_1dp (mặc định cấu hình GPA4_ROUND_1DP): làm tròn 1 chữ số thập phân (half-up) trước khi tra bảng.
    """
    if round_1dp is None:
        round_1dp = getattr(settings, "GPA4_ROUND_1DP", False)
    if round_1dp and score_10 is not None:
        score_10 = round_half_up(score_10, 1)

    if use_plus_grades:
        if score_10 >= 8.5:
            return 4.0, "A"
        elif score_10 >= 8.0:
            return 3.5, "B+"
        elif score_10 >= 7.0:
            return 3.0, "B"
        elif score_10 >= 6.5:
            return 2.5, "C+"
        elif score_10 >= 5.5:
            return 2.0, "C"
        elif score_10 >= 5.0:
            return 1.5, "D+"
        elif score_10 >= 4.0:
            return 1.0, "D"
        else:
            return 0.0, "F"
    else:
        # Thang điểm rút gọn 5 mức (không có điểm cộng), tương thích ngược:
        if score_10 >= 8.5:
            return 4.0, "A"
        elif score_10 >= 7.0:
            return 3.0, "B"
        elif score_10 >= 5.5:
            return 2.0, "C"
        elif score_10 >= 4.0:
            return 1.0, "D"
        else:
            return 0.0, "F"


def normalize_course_name(name: str) -> str:
    """Chuẩn hóa tên môn học để so khớp không phân biệt hoa thường, dấu tiếng Việt, dấu gạch nối và tag ngoặc nhọn."""
    if not name:
        return ""
    import unicodedata, re
    text = re.sub(r'\{[^}]*\}', '', str(name))
    text = text.replace("-", " ")
    text = unicodedata.normalize('NFKD', text.strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("đ", "d").replace("Đ", "d")
    text = re.sub(r'\s+', ' ', text).strip()
    # Chuẩn hóa biến thể từ đồng nghĩa giữa PDF và CTĐT (máy học <-> học máy)
    text = text.replace("may hoc", "hoc may")
    return text


def is_special_condition_subject(name: str) -> bool:
    """
    Kiểm tra các học phần điều kiện cấp chứng chỉ theo Điều 11 Quy chế đào tạo:
    - Giáo dục thể chất (GDTC), Thể dục thể thao
    - Giáo dục quốc phòng - An ninh (GDQP-AN), Quân sự
    Các học phần này KHÔNG tính vào 150 tín chỉ tích lũy của CTĐT và KHÔNG tính vào GPA tích lũy.
    """
    norm = normalize_course_name(name)
    triggers = [
        "the chat", "gdtc", "the duc", "boi loi", "dien kinh", "bong chuyen", "bong da", "cau long",
        "quoc phong", "gdqp", "an ninh", "quan su",
        "ky nang mem", "knm"
    ]
    return any(t in norm for t in triggers)


def calculate_academic_summary(courses_history: List[Dict[str, Any]], round_1dp: Optional[bool] = None) -> Dict[str, Any]:
    """
    Tính toán các chỉ số học tập tổng hợp từ lịch sử bảng điểm của sinh viên:
    - Tổng tín chỉ đã tích lũy (passed >= 4.0):
      + Không dùng mã môn làm khóa duy nhất (hỗ trợ trùng mã môn trong PDF).
      + Môn hệ số 0, tín chỉ = 0 KHÔNG tính vào tín chỉ và GPA.
      + Môn điều kiện (GDQP, GDTC) KHÔNG tính vào 150 tín chỉ và GPA.
      + Môn ngoài CTĐT (is_outside_curriculum=True) KHÔNG tính vào tín chỉ và GPA.
      + Học cả 2 môn trong một cặp tự chọn (A và B) KHÔNG cộng đôi tín chỉ (chỉ tính 1 môn).
    - Thiếu TC (tc is None) hoặc thiếu điểm (diem is None) hoặc needs_confirmation:
      -> KHÔNG tính vào tích lũy/GPA, đưa vào danh sách unconfirmed_courses.
    - GPA thang 10 và GPA thang 4 (chỉ tính môn có điểm số và tín chỉ hợp lệ).
    """
    passed_credits = 0
    failed_credits = 0
    total_weighted_10 = Decimal("0.0")
    total_weighted_4 = Decimal("0.0")
    total_weighted_4_round = Decimal("0.0")
    total_gpa_credits = 0
    unconfirmed_courses = []

    seen_passed_courses = set()

    ELECTIVE_GROUPS = {
        "111043": "ELECTIVE_HK5",
        "111089": "ELECTIVE_HK5",
        "111071": "ELECTIVE_HK6",
        "111084": "ELECTIVE_HK6",
        "111088": "ELECTIVE_HK7",
        "111061": "ELECTIVE_HK7",
    }
    seen_elective_groups = set()

    for c in courses_history:
        code = str(c.get("ma_mon") or c.get("course_code") or c.get("code") or "").strip().upper()
        name = str(c.get("ten_mon") or c.get("course_name") or c.get("mon") or c.get("name") or "").strip()
        tc = c.get("tin_chi") if c.get("tin_chi") is not None else c.get("credits")
        diem = c.get("diem") if c.get("diem") is not None else c.get("grade")
        he_so = c.get("he_so")
        needs_confirm = bool(c.get("needs_confirmation"))

        # Kiểm tra môn ngoài CTĐT
        is_outside = bool(c.get("is_outside_curriculum") or c.get("ngoai_ctdt") or c.get("ngoai_chuong_trinh"))

        try:
            diem_val = float(diem) if diem is not None else None
        except (ValueError, TypeError):
            diem_val = None

        try:
            tc_val = int(tc) if tc is not None else None
        except (ValueError, TypeError):
            tc_val = None

        try:
            he_so_val = float(he_so) if he_so is not None else (float(tc_val) if tc_val is not None else 1.0)
        except (ValueError, TypeError):
            he_so_val = 1.0

        # Kiểm tra môn hệ số 0, tín chỉ 0, môn điều kiện (GDTC, GDQP) và môn ngoài CTĐT
        is_condition_sub = is_special_condition_subject(name)
        is_zero_coef = (he_so_val == 0.0 or tc_val == 0)

        # Xử lý thiếu TC, thiếu Điểm hoặc cần xác nhận:
        # Nếu môn không phải môn điều kiện/hệ số 0 mà tc_val is None -> thiếu TC
        # Nếu diem_val is None -> thiếu điểm
        if (tc_val is None and not is_condition_sub) or (diem_val is None) or needs_confirm:
            reasons = []
            if tc_val is None and not is_condition_sub: reasons.append("thiếu số tín chỉ")
            if diem_val is None: reasons.append("chưa có điểm")
            if needs_confirm and tc_val is not None and diem_val is not None:
                reasons.append(c.get("grade_note") or "cần sinh viên xác nhận")

            unconfirmed_courses.append({
                "ma_mon": code,
                "ten_mon": name,
                "tin_chi": tc_val,
                "diem": diem_val,
                "ly_do": ", ".join(reasons)
            })
            continue

        # Định danh môn học không phụ thuộc duy nhất vào mã môn (tránh lỗi khi trùng mã môn 11105, 10207, 11100)
        norm_name = normalize_course_name(name)
        course_unique_key = f"{code}_{norm_name}" if (code and norm_name) else (norm_name or code)

        if diem_val is not None and tc_val is not None:
            if diem_val >= 4.0:
                # Môn hệ số 0, môn điều kiện GDTC/GDQP và môn ngoài CTĐT KHÔNG tính vào tín chỉ tích lũy tốt nghiệp và GPA
                if not is_outside and not is_zero_coef and not is_condition_sub:
                    if course_unique_key not in seen_passed_courses:
                        is_dup_elective = False
                        if code in ELECTIVE_GROUPS:
                            grp = ELECTIVE_GROUPS[code]
                            if grp in seen_elective_groups:
                                is_dup_elective = True
                            else:
                                seen_elective_groups.add(grp)

                        if not is_dup_elective:
                            passed_credits += tc_val
                            seen_passed_courses.add(course_unique_key)

                            score_4, _ = convert_score_to_scale_4(diem_val, round_1dp=round_1dp)
                            score_4_r, _ = convert_score_to_scale_4(diem_val, round_1dp=True)
                            d_val = Decimal(str(diem_val))
                            d_tc = Decimal(str(tc_val))
                            d_score_4 = Decimal(str(score_4))
                            d_score_4_r = Decimal(str(score_4_r))
                            total_weighted_10 += d_val * d_tc
                            total_weighted_4 += d_score_4 * d_tc
                            total_weighted_4_round += d_score_4_r * d_tc
                            total_gpa_credits += tc_val
            else:
                if not is_outside and not is_zero_coef and not is_condition_sub:
                    failed_credits += tc_val

    if total_gpa_credits > 0:
        d_cr = Decimal(str(total_gpa_credits))
        gpa_10 = float((total_weighted_10 / d_cr).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        gpa_4 = float((total_weighted_4 / d_cr).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        gpa_4_round = float((total_weighted_4_round / d_cr).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    else:
        gpa_10 = 0.0
        gpa_4 = 0.0
        gpa_4_round = 0.0

    # Trích xuất danh sách học kỳ có trong bảng điểm
    sem_nums = []
    for c in courses_history:
        hk_str = str(c.get("hoc_ky") or c.get("semester") or "")
        m = re.search(r"Học kỳ\s+(\d+)", hk_str, re.IGNORECASE)
        if m:
            sem_nums.append(int(m.group(1)))

    min_semester = min(sem_nums) if sem_nums else 1
    partial_transcript = bool(min_semester > 1)

    return {
        "passed_credits": passed_credits,
        "failed_credits": failed_credits,
        "gpa_10": gpa_10,
        "gpa_4": gpa_4,
        "gpa_4_round": gpa_4_round,
        "total_gpa_credits": total_gpa_credits,
        "unconfirmed_courses": unconfirmed_courses,
        "partial_transcript": partial_transcript,
        "min_semester": min_semester,
        "present_semesters": sorted(list(set(sem_nums)))
    }


def check_graduation(
    profile: Dict[str, Any],
    curriculum: List[Dict[str, Any]],
    current_semester: int = 5,
    suggested_credits_per_semester: int = DEFAULT_SUGGESTED_CREDITS_PER_SEMESTER,
    suggested_credits_summer: int = DEFAULT_SUGGESTED_CREDITS_SUMMER,
    required_credits: int = DEFAULT_REQUIRED_CREDITS,
    max_credits_per_semester: Optional[int] = None,
    max_credits_summer: Optional[int] = None
) -> Dict[str, Any]:
    """
    Hàm kiểm tra điều kiện tốt nghiệp và lập kế hoạch học kỳ bằng CODE:
    
    Args:
        profile: Thông tin hồ sơ sinh viên:
            - "student_code": MSSV
            - "full_name": Họ tên
            - "major": Ngành học
            - "cohort": Khóa học
            - "courses": Danh sách môn học đã học kèm điểm [{ma_mon, ten_mon, tin_chi, diem, ...}]
            - "certificates": Trạng thái chứng chỉ {english, it, gdqp, gdtc, soft_skills}
        curriculum: Danh mục môn học CTĐT:
            - [{ma_mon, ten_mon, tin_chi, hoc_ky_de_xuat, is_required, mon_tien_quyet}]
        current_semester: Học kỳ hiện tại của sinh viên (ví dụ HK5)
        suggested_credits_per_semester: Gợi ý tối đa tín chỉ học kỳ chính (mặc định 20)
        suggested_credits_summer: Gợi ý tối đa tín chỉ kỳ hè (mặc định 8)
        required_credits: Tín chỉ tích lũy tối thiểu (mặc định 150)
    """
    # Xử lý tham số tương thích ngược nếu truyền max_credits_*
    if max_credits_per_semester is not None:
        suggested_credits_per_semester = max_credits_per_semester
    if max_credits_summer is not None:
        suggested_credits_summer = max_credits_summer
    curriculum_missing_data = []
    
    # 1. Chuẩn hóa dữ liệu CTĐT và kiểm tra tính đầy đủ
    curr_lookup: Dict[str, Dict[str, Any]] = {}
    curr_code_multimap: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    curr_name_lookup: Dict[str, Dict[str, Any]] = {}
    
    for c in curriculum:
        ma = str(c.get("ma_mon") or "").strip().upper()
        ten = str(c.get("ten_mon") or "").strip()
        norm_ten = normalize_course_name(ten)
        if not ma and not ten:
            curriculum_missing_data.append("Phát hiện môn học trong CTĐT không có mã môn và tên môn.")
            continue
        
        tc = c.get("tin_chi")
        if tc is None or tc <= 0:
            curriculum_missing_data.append(f"Môn '{ten or ma}' trong CTĐT thiếu số tín chỉ.")

        item = {
            "ma_mon": ma,
            "ten_mon": ten,
            "tin_chi": tc,
            "hoc_ky_de_xuat": c.get("hoc_ky_de_xuat") or c.get("hoc_ky") or 1,
            "is_required": bool(c.get("is_required", True)),
            "mon_tien_quyet": [str(p).strip().upper() for p in c.get("mon_tien_quyet", []) if p],
            "mon_song_hanh": [str(p).strip().upper() for p in c.get("mon_song_hanh", []) if p]
        }
        if ma:
            curr_lookup[ma] = item
            curr_code_multimap[ma].append(item)
        if norm_ten:
            curr_name_lookup[norm_ten] = item

    # 2. Phân loại các môn trong lịch sử sinh viên (Đạt vs Chưa đạt vs Cần xác nhận)
    raw_courses = profile.get("courses", [])

    # Tự động đánh dấu môn ngoài CTĐT nếu môn không nằm trong CTĐT (cả theo mã môn lẫn tên chuẩn hóa)
    annotated_courses = []
    for c in raw_courses:
        c_item = dict(c)
        c_code = str(c_item.get("ma_mon") or c_item.get("course_code") or c_item.get("code") or "").strip().upper()
        c_name = str(c_item.get("ten_mon") or c_item.get("course_name") or c_item.get("mon") or c_item.get("name") or "").strip()
        c_norm = normalize_course_name(c_name)
        c_cond = is_special_condition_subject(c_name)

        if not c_cond and not c_item.get("is_outside_curriculum") and not c_item.get("ngoai_ctdt"):
            is_generic_elective = ("elective" in c_code.lower() or "tu chon" in c_norm)
            is_in_curr = bool((c_norm and c_norm in curr_name_lookup) or (c_code and c_code in curr_code_multimap) or is_generic_elective)
            if not is_in_curr:
                c_item["is_outside_curriculum"] = True
        annotated_courses.append(c_item)

    summary = calculate_academic_summary(annotated_courses)
    min_semester = summary.get("min_semester", 1)
    is_partial = summary.get("partial_transcript", False)

    # Khai báo môn được miễn / chuyển điểm (nếu có)
    exempted_input = profile.get("exempted_courses") or []
    exempted_keys: Set[str] = set()
    for ex in exempted_input:
        if isinstance(ex, dict):
            c_code = str(ex.get("ma_mon") or ex.get("code") or "").strip().upper()
            c_name = normalize_course_name(ex.get("ten_mon") or ex.get("name") or "")
        else:
            c_str = str(ex).strip()
            c_code = c_str.upper()
            c_name = normalize_course_name(c_str)
        if c_code: exempted_keys.add(c_code)
        if c_name: exempted_keys.add(c_name)

    passed_courses_set: Set[str] = set(exempted_keys)
    failed_courses_dict: Dict[str, Dict[str, Any]] = {}
    unconfirmed_courses: List[Dict[str, Any]] = []
    unconfirmed_keys_set: Set[str] = set()

    for c in raw_courses:
        code = str(c.get("ma_mon") or c.get("course_code") or c.get("code") or "").strip().upper()
        name = str(c.get("ten_mon") or c.get("course_name") or c.get("mon") or c.get("name") or "").strip()
        tc = c.get("tin_chi") if c.get("tin_chi") is not None else c.get("credits")
        diem = c.get("diem") if c.get("diem") is not None else c.get("grade")
        
        try:
            diem_float = float(diem) if diem is not None else None
        except (ValueError, TypeError):
            diem_float = None

        norm_name = normalize_course_name(name)
        # Tra cứu thông tin môn trong CTĐT: Ưu tiên tên môn để không bị lẫn khi mã môn trùng (11105, 10207, 11100)
        curr_info = curr_name_lookup.get(norm_name)
        if not curr_info and code:
            cand = curr_code_multimap.get(code, [])
            curr_info = cand[0] if cand else {}
        curr_info = curr_info or {}

        # Tuyệt đối KHÔNG gán mặc định 2 hay 3 tín chỉ:
        # Lấy từ bảng điểm, nếu bảng điểm thiếu thì tra từ CTĐT, nếu CTĐT cũng thiếu -> None
        tc_final = tc if tc is not None else curr_info.get("tin_chi")
        try:
            tc_int = int(tc_final) if tc_final is not None else None
        except (ValueError, TypeError):
            tc_int = None

        # Định danh môn không phụ thuộc đơn thuần vào mã môn
        key = f"{code}_{norm_name}" if (code and norm_name) else (norm_name or code)
        needs_confirm = bool(c.get("needs_confirmation"))

        is_condition = is_special_condition_subject(name)
        is_missing_tc = (tc_int is None and not is_condition)
        is_missing_diem = (diem_float is None)

        # Môn có diem=None hoặc thiếu TC hoặc c.get("needs_confirmation"):
        # -> KHÔNG xếp đạt/rớt, đưa vào mục "cần xác nhận"
        if is_missing_diem or is_missing_tc or needs_confirm:
            unconfirmed_keys_set.add(key)
            if norm_name: unconfirmed_keys_set.add(norm_name)
            if code: unconfirmed_keys_set.add(code)

            reasons = []
            if is_missing_diem: reasons.append("chưa có điểm")
            if is_missing_tc: reasons.append("thiếu số tín chỉ")
            if needs_confirm and not is_missing_diem and not is_missing_tc:
                reasons.append(c.get("grade_note") or "cần sinh viên xác nhận")

            unconfirmed_courses.append({
                "ma_mon": code or curr_info.get("ma_mon", ""),
                "ten_mon": name or curr_info.get("ten_mon", "Chưa rõ tên môn"),
                "tin_chi": tc_int,
                "diem": diem_float,
                "ly_do": ", ".join(reasons)
            })
            continue

        if diem_float >= 4.0:
            passed_courses_set.add(key)
            if norm_name: passed_courses_set.add(norm_name)
            if code: passed_courses_set.add(code)
            if curr_info.get("ma_mon"): passed_courses_set.add(curr_info["ma_mon"])
            # Nếu đã học lại qua môn thì xóa khỏi danh sách nợ
            if key in failed_courses_dict:
                del failed_courses_dict[key]
            if norm_name in failed_courses_dict:
                del failed_courses_dict[norm_name]
        else:
            # Điểm < 4.0 (môn nợ/chưa đạt)
            if key not in passed_courses_set and norm_name not in passed_courses_set:
                failed_courses_dict[key] = {
                    "ma_mon": code or curr_info.get("ma_mon", ""),
                    "ten_mon": name or curr_info.get("ten_mon", "Chưa rõ tên môn"),
                    "tin_chi": tc_int,
                    "diem": diem_float,
                    "hoc_ky": c.get("hoc_ky") or curr_info.get("hoc_ky_de_xuat")
                }

    def safe_int_hk(hk_val: Any) -> int:
        if isinstance(hk_val, int):
            return hk_val
        m = re.search(r"\d+", str(hk_val or ""))
        return int(m.group(0)) if m else 1

    # 3. Tính toán môn bắt buộc theo CTĐT chưa từng học & môn học kỳ trước chưa kiểm chứng
    missing_required_courses: List[Dict[str, Any]] = []
    unverified_earlier_courses: List[Dict[str, Any]] = []

    ELECTIVE_PAIRS = {
        "111043": "111089",
        "111089": "111043",
        "111071": "111084",
        "111084": "111071",
        "111088": "111061",
        "111061": "111088",
    }

    for c in curriculum:
        ma = str(c.get("ma_mon") or "").strip().upper()
        ten = str(c.get("ten_mon") or "").strip()
        norm_ten = normalize_course_name(ten)
        is_req = bool(c.get("is_required", True))
        
        if is_req:
            is_passed = (norm_ten and norm_ten in passed_courses_set) or (ma and ma in passed_courses_set)
            is_failed = any(norm_ten == normalize_course_name(f.get("ten_mon", "")) for f in failed_courses_dict.values())
            is_unconf = (norm_ten and norm_ten in unconfirmed_keys_set) or (ma and ma in unconfirmed_keys_set)
            is_exempted = (norm_ten and norm_ten in exempted_keys) or (ma and ma in exempted_keys)

            # Kiểm tra xem môn tự chọn tương đương (chọn 1 trong 2) đã hoàn thành chưa:
            alt_ma = ELECTIVE_PAIRS.get(ma)
            is_alt_passed = bool(alt_ma and alt_ma in passed_courses_set)
            if not is_alt_passed and alt_ma:
                alt_curr = curr_lookup.get(alt_ma)
                if alt_curr and alt_curr.get("ten_mon"):
                    is_alt_passed = bool(normalize_course_name(alt_curr["ten_mon"]) in passed_courses_set)

            # Đã học, đã nợ, được miễn hoặc đã đạt môn tự chọn tương đương -> bỏ qua
            if is_passed or is_failed or is_unconf or is_exempted or is_alt_passed:
                continue

            hk_val = safe_int_hk(c.get("hoc_ky_de_xuat") or c.get("hoc_ky") or 1)
            course_item = {
                "ma_mon": ma,
                "ten_mon": ten,
                "tin_chi": c.get("tin_chi"),
                "hoc_ky_de_xuat": hk_val,
                "mon_tien_quyet": [str(p).strip().upper() for p in c.get("mon_tien_quyet", []) if p],
                "mon_song_hanh": [str(p).strip().upper() for p in c.get("mon_song_hanh", []) if p]
            }

            # Nếu bảng điểm bị thiếu các học kỳ trước (min_semester > 1):
            # Các môn bắt buộc có học kỳ đề xuất < min_semester KHÔNG được xếp vào môn thiếu chắc chắn,
            # và KHÔNG được xếp vào kế hoạch học tập. Tách riêng thành unverified_earlier_courses.
            if is_partial and hk_val < min_semester:
                unverified_earlier_courses.append(course_item)
            else:
                missing_required_courses.append(course_item)

    failed_courses = list(failed_courses_dict.values())

    # 4. Tính toán tiến độ tín chỉ & GPA
    passed_credits = summary["passed_credits"]
    credits_missing = max(0, required_credits - passed_credits)

    # 5. Kiểm tra chuẩn đầu ra (Chứng chỉ)
    raw_certs = profile.get("certificates", {})
    certs_status = {
        "english": bool(raw_certs.get("has_english") or raw_certs.get("english") in [True, "đã có", "valid", "dat"]),
        "it": bool(raw_certs.get("has_it") or raw_certs.get("it") in [True, "đã có", "valid", "dat"]),
        "gdqp": bool(raw_certs.get("has_gdqp") or raw_certs.get("gdqp") in [True, "đã có", "valid", "dat"]),
        "gdtc": bool(raw_certs.get("has_gdtc") or raw_certs.get("gdtc") in [True, "đã có", "valid", "dat"]),
        "soft_skills": bool(raw_certs.get("has_soft_skills") or raw_certs.get("soft_skills") in [True, "đã có", "valid", "dat"])
    }

    # Điều kiện tốt nghiệp: Đủ tín chỉ (>=150), GPA >= 5.0, không còn môn nợ, đủ môn bắt buộc, không thiếu dữ liệu kỳ trước, đủ chứng chỉ
    is_eligible = bool(
        passed_credits >= required_credits
        and len(failed_courses) == 0
        and len(missing_required_courses) == 0
        and len(unverified_earlier_courses) == 0
        and summary["gpa_10"] >= MIN_GRADUATION_GPA
        and certs_status["english"]
        and certs_status["it"]
        and certs_status["gdqp"]
        and certs_status["gdtc"]
        and certs_status["soft_skills"]
    )

    # 6. Tính số học kỳ còn lại
    remaining_semesters_standard = max(0, MAX_STANDARD_SEMESTERS - current_semester + 1)
    remaining_semesters_max = max(0, MAX_EXTENDED_SEMESTERS - current_semester + 1)

    # 7. XÂY DỰNG KẾ HOẠCH ĐỀ XUẤT TỪNG HỌC KỲ (PROPOSED PLAN)
    # Tái sử dụng logic xếp hạng ưu tiên từ priority_engine.py
    pe_input = [
        {
            "ma_mon": f.get("ma_mon") or f.get("ten_mon"),
            "mon_hoc": f.get("ten_mon"),
            "tin_chi": f.get("tin_chi"),
            "diem": f.get("diem", 0.0),
            "hoc_ky": f.get("hoc_ky", 1)
        }
        for f in failed_courses
    ]
    ranked_failed = rank_priority(pe_input, curriculum)
    blocked_map = build_blocked_map(curriculum)

    # Tập hợp toàn bộ các môn cần phải hoàn thành trong tương lai:
    # Nhóm A: Môn nợ (ưu tiên cao, cần học lại càng sớm càng tốt)
    # Nhóm B: Môn bắt buộc chưa học (sắp xếp theo học kỳ đề xuất và tiên quyết)
    items_to_schedule = []

    # Map tra cứu độ ưu tiên môn nợ
    rank_score_map = {r.get("ma_mon"): r.get("do_uu_tien", 0.0) for r in ranked_failed}

    def safe_int_hk(hk_val: Any) -> int:
        if isinstance(hk_val, int):
            return hk_val
        m = re.search(r"\d+", str(hk_val or ""))
        return int(m.group(0)) if m else 1

    for f in failed_courses:
        ma = f.get("ma_mon") or f.get("ten_mon")
        items_to_schedule.append({
            "ma_mon": f.get("ma_mon", ""),
            "ten_mon": f.get("ten_mon", ""),
            "tin_chi": f.get("tin_chi"),
            "is_retake": True,
            "priority": rank_score_map.get(ma, 2.0) + 10.0, # Ưu tiên môn học lại trước môn mới
            "mon_tien_quyet": curr_lookup.get(f.get("ma_mon", ""), {}).get("mon_tien_quyet", []),
            "mon_song_hanh": curr_lookup.get(f.get("ma_mon", ""), {}).get("mon_song_hanh", []),
            "hoc_ky_de_xuat": safe_int_hk(f.get("hoc_ky") or 1)
        })

    for m in missing_required_courses:
        ma = m.get("ma_mon")
        num_blocked = len(blocked_map.get(ma, [])) if ma else 0
        p_offset = -0.5 if m.get("mon_song_hanh") else 0.0
        items_to_schedule.append({
            "ma_mon": m.get("ma_mon", ""),
            "ten_mon": m.get("ten_mon", ""),
            "tin_chi": m.get("tin_chi"),
            "is_retake": False,
            "priority": float(num_blocked * 2.0) + max(0.0, (9.0 - float(safe_int_hk(m.get("hoc_ky_de_xuat", 1)))) * 0.5) + p_offset,
            "mon_tien_quyet": m.get("mon_tien_quyet", []),
            "mon_song_hanh": m.get("mon_song_hanh", []),
            "hoc_ky_de_xuat": safe_int_hk(m.get("hoc_ky_de_xuat", 1))
        })

    # Lập lịch phân bổ vào từng học kỳ
    # Bắt đầu từ học kỳ kế tiếp hoặc học kỳ hè nếu có môn nợ
    proposed_plan = []
    scheduled_passed_codes = set(passed_courses_set)

    unverified_codes_set = set()
    unverified_name_map = {}
    for u in unverified_earlier_courses:
        u_code = str(u.get("ma_mon") or "").strip().upper()
        u_ten = str(u.get("ten_mon") or "").strip()
        u_norm = normalize_course_name(u_ten)
        if u_code:
            unverified_codes_set.add(u_code)
            unverified_name_map[u_code] = u_ten
        if u_norm:
            unverified_codes_set.add(u_norm)
            unverified_name_map[u_norm] = u_ten

    # Tiên quyết thuộc nhóm 'unverified' được coi là giả định đã đạt (kèm ghi chú), không chặn môn phía sau
    if is_partial:
        scheduled_passed_codes.update(unverified_codes_set)

    unscheduled_items = list(items_to_schedule)
    
    current_plan_sem = current_semester
    plan_step = 1

    # Cho phép tối đa 8 kỳ kế hoạch (kỳ chính + kỳ hè) để tránh vòng lặp vô hạn
    while unscheduled_items and plan_step <= 8:
        # Nếu có môn học lại, xem xét chèn 1 kỳ hè để trả nợ môn nhẹ tải
        is_summer = (plan_step % 2 == 0) and any(item["is_retake"] for item in unscheduled_items)
        sem_name = f"Học kỳ hè (sau HK{current_plan_sem})" if is_summer else f"Học kỳ {current_plan_sem}"
        credit_limit = suggested_credits_summer if is_summer else suggested_credits_per_semester

        # Kỳ CTĐT bắt buộc vượt 20 TC thì không cắt môn (chỉ áp dụng ở chế độ gợi ý mặc định, không vượt khi truyền giới hạn cứng):
        if not is_summer and max_credits_per_semester is None:
            curr_sem_ctdt_credits = sum(
                int(it.get("tin_chi") or 0)
                for it in unscheduled_items
                if not it.get("is_retake") and safe_int_hk(it.get("hoc_ky_de_xuat")) == current_plan_sem
            )
            credit_limit = max(credit_limit, curr_sem_ctdt_credits)

        current_sem_courses = []
        current_sem_credits = 0
        remaining_items_next = []

        # Sắp xếp các môn ứng viên: ưu tiên priority cao, học kỳ đề xuất sớm
        unscheduled_items.sort(key=lambda x: (x["priority"], -safe_int_hk(x.get("hoc_ky_de_xuat", 1))), reverse=True)

        for item in unscheduled_items:
            ma = item.get("ma_mon", "")
            ten = item.get("ten_mon", "")
            tc_raw = item.get("tin_chi")
            tc = int(tc_raw) if tc_raw is not None else 0
            tien_quyet = item.get("mon_tien_quyet", [])

            # Kiểm tra xem toàn bộ môn tiên quyết đã được hoàn thành ở các kỳ trước chưa
            prereq_satisfied = True
            for pr in tien_quyet:
                if pr and (pr not in scheduled_passed_codes):
                    prereq_satisfied = False
                    break

            # Kiểm tra môn song hành (có thể đã hoàn thành kỳ trước HOẶC đang được xếp trong cùng kỳ này)
            song_hanh = item.get("mon_song_hanh", [])
            coreq_satisfied = True
            curr_sem_codes = {c["ma_mon"] for c in current_sem_courses}
            for sh in song_hanh:
                if sh and (sh not in scheduled_passed_codes) and (sh not in curr_sem_codes):
                    coreq_satisfied = False
                    break

            # Nếu là kỳ hè: chỉ cho phép đăng ký học lại hoặc tối đa tín chỉ nhỏ
            if is_summer and not item["is_retake"]:
                remaining_items_next.append(item)
                continue

            # Nếu thỏa điều kiện tiên quyết & song hành và không vượt giới hạn tín chỉ học kỳ
            if prereq_satisfied and coreq_satisfied and (current_sem_credits + tc <= credit_limit):
                assumed_prereqs = []
                for pr in tien_quyet:
                    if pr and (pr in unverified_codes_set or normalize_course_name(pr) in unverified_codes_set):
                        pr_name = unverified_name_map.get(pr) or unverified_name_map.get(normalize_course_name(pr)) or pr
                        assumed_prereqs.append(pr_name)

                c_item = {
                    "ma_mon": ma,
                    "ten_mon": ten,
                    "tin_chi": tc,
                    "loai": "Học lại" if item["is_retake"] else "Học mới",
                    "mon_tien_quyet": tien_quyet
                }
                if song_hanh:
                    c_item["mon_song_hanh"] = song_hanh
                if assumed_prereqs:
                    c_item["ghi_chu_tien_quyet"] = f"Giả định đã đạt tiên quyết ({', '.join(assumed_prereqs)})"

                current_sem_courses.append(c_item)
                current_sem_credits += tc
            else:
                remaining_items_next.append(item)

        if current_sem_courses:
            # Ghi nhận các môn đã xếp vào kỳ này vào tập hoàn thành cho các kỳ sau
            for c in current_sem_courses:
                if c["ma_mon"]: scheduled_passed_codes.add(c["ma_mon"])
                if c["ten_mon"]: scheduled_passed_codes.add(c["ten_mon"].lower())

            note_parts = []
            if is_summer:
                note_parts.append("Tận dụng kỳ hè để trả nợ môn, giảm tải cho học kỳ chính")
            if any(c["loai"] == "Học lại" for c in current_sem_courses):
                note_parts.append("Ưu tiên học lại môn nợ để mở khóa môn tiên quyết")
            if any("ghi_chu_tien_quyet" in c for c in current_sem_courses):
                note_parts.append("Giả định đã hoàn thành môn tiên quyết ở các kỳ trước chưa có dữ liệu điểm")

            proposed_plan.append({
                "semester_name": sem_name,
                "total_credits": current_sem_credits,
                "courses": current_sem_courses,
                "note": "; ".join(note_parts) if note_parts else "Đăng ký theo tiến độ CTĐT chuẩn"
            })

        # Nếu không xếp được môn nào (ví dụ bị kẹt vòng lặp tiên quyết hoặc đầy tín chỉ)
        if len(remaining_items_next) == len(unscheduled_items):
            # Cưỡng chế đưa 1 môn có ít điều kiện chưa đạt nhất hoặc báo thiếu dữ liệu
            blocked_courses_names = [it.get("ten_mon") for it in unscheduled_items]
            curriculum_missing_data.append(
                f"Không thể sắp xếp tiếp các môn sau do vướng điều kiện tiên quyết chưa đạt: {', '.join(blocked_courses_names[:3])}."
            )
            break

        unscheduled_items = remaining_items_next
        if not is_summer:
            current_plan_sem += 1
        plan_step += 1

    return {
        "student": {
            "student_code": profile.get("student_code", "N/A"),
            "full_name": profile.get("full_name", "Sinh viên"),
            "major": profile.get("major", "Công nghệ thông tin"),
            "cohort": profile.get("cohort", "2021")
        },
        "student_summary": {
            "passed_credits": passed_credits,
            "required_credits": required_credits,
            "credits_missing": credits_missing,
            "failed_credits": summary["failed_credits"],
            "gpa_10": summary["gpa_10"],
            "gpa_4": summary["gpa_4"],
            "gpa_4_round": summary.get("gpa_4_round"),
            "partial_transcript": summary.get("partial_transcript", False),
            "min_semester": summary.get("min_semester", 1),
            "present_semesters": summary.get("present_semesters", [])
        },
        "failed_courses": failed_courses,
        "missing_required_courses": missing_required_courses,
        "unverified_courses": unverified_earlier_courses,
        "unverified_earlier_required_courses": unverified_earlier_courses,
        "unconfirmed_courses": unconfirmed_courses,
        "certificates_status": certs_status,
        "remaining_semesters_standard": remaining_semesters_standard,
        "remaining_semesters_max": remaining_semesters_max,
        "is_eligible": is_eligible,
        "proposed_plan": proposed_plan,
        "curriculum_missing_data": curriculum_missing_data,
        "partial_transcript": summary.get("partial_transcript", False),
        "min_semester": summary.get("min_semester", 1),
        "present_semesters": summary.get("present_semesters", [])
    }


def build_structured_advisory_text(
    grad_result: Dict[str, Any],
    rag_regulations: Optional[Union[List[str], List[Dict[str, Any]]]] = None
) -> Dict[str, str]:
    """
    Code dựng sẵn toàn bộ bản tư vấn học vụ chuẩn xác 4 PHẦN từ kết quả check_graduation.
    LLM chỉ có nhiệm vụ diễn đạt lại tự nhiên hoặc làm văn phong mượt mà hơn,
    tuyệt đối không tự tính toán hay tự sửa số liệu.
    """
    summary = grad_result.get("student_summary", {})
    stu = grad_result.get("student", {})
    failed_courses = grad_result.get("failed_courses", [])
    missing_req = grad_result.get("missing_required_courses", [])
    unverified_earlier = grad_result.get("unverified_courses") or grad_result.get("unverified_earlier_required_courses") or []
    certs = grad_result.get("certificates_status", {})
    plan = grad_result.get("proposed_plan", [])
    is_eligible = grad_result.get("is_eligible", False)
    unconfirmed = grad_result.get("unconfirmed_courses", [])

    # ---------------- PHẦN 1: TÌNH TRẠNG HIỆN TẠI ----------------
    passed_cr = summary.get("passed_credits", 0)
    req_cr = summary.get("required_credits", DEFAULT_REQUIRED_CREDITS)
    gpa_10 = summary.get("gpa_10", 0.0)
    gpa_4 = summary.get("gpa_4", 0.0)
    gpa_4_round = summary.get("gpa_4_round")

    if gpa_4_round is not None and gpa_4_round != gpa_4:
        gpa_4_str = f"{gpa_4:.2f}-{gpa_4_round:.2f} (ước tính, chờ giáo vụ xác nhận cách làm tròn)"
    else:
        gpa_4_str = f"{gpa_4:.2f} (ước tính theo bảng quy đổi)"

    is_partial = bool(grad_result.get("partial_transcript") or summary.get("partial_transcript"))
    min_sem = grad_result.get("min_semester") or summary.get("min_semester") or 1

    gpa_sub = " (tính trên các kỳ hiện có)" if is_partial else ""
    part_1_lines = [
        f"- Tiến độ tín chỉ: Đã đạt {passed_cr}/{req_cr} tín chỉ tích lũy.",
        f"- Điểm trung bình tích lũy (GPA{gpa_sub}): {gpa_10} (thang 10, yêu cầu tốt nghiệp toàn khóa 5.0 theo trang web Khoa, CHƯA KIỂM CHỨNG (chờ giáo vụ)); {gpa_4_str} (thang 4)."
    ]
    if is_partial:
        part_1_lines.append(
            f"- Cảnh báo dữ liệu: Bảng điểm cung cấp chỉ hiển thị từ Học kỳ {min_sem} trở đi, "
            f"thiếu dữ liệu các học kỳ trước đó (từ Học kỳ 1 đến Học kỳ {min_sem - 1})."
        )
    completed_certs = []
    if certs.get("english"): completed_certs.append("Ngoại ngữ (Tiếng Anh)")
    if certs.get("it"): completed_certs.append("Tin học")
    if certs.get("gdqp"): completed_certs.append("GDQP-AN")
    if certs.get("gdtc"): completed_certs.append("GDTC")
    if certs.get("soft_skills"): completed_certs.append("Kỹ năng mềm")

    if completed_certs:
        part_1_lines.append(f"- Điều kiện / chứng chỉ đã đạt: {', '.join(completed_certs)}.")
    else:
        part_1_lines.append("- Điều kiện / chứng chỉ đã đạt: Chưa có dữ liệu chứng chỉ nào được ghi nhận.")

    part_1 = "\n".join(part_1_lines)

    # ---------------- PHẦN 2: CÒN THIẾU GÌ ----------------
    missing_cr = summary.get("credits_missing", 0)
    part_2_lines = []

    if is_eligible:
        part_2_lines.append("- Bạn đã hoàn thành đầy đủ tất cả các môn học và điều kiện theo quy chế, đủ điều kiện xét tốt nghiệp!")
    else:
        if missing_cr > 0:
            if is_partial:
                part_2_lines.append(
                    f"- Tín chỉ còn thiếu: Ước tính cần tích lũy thêm tối đa {missing_cr} tín chỉ để đủ {req_cr} tín chỉ "
                    f"(con số này tính trên các kỳ hiện có và chưa thể khẳng định chắc chắn do thiếu dữ liệu từ Học kỳ 1 đến Học kỳ {min_sem - 1}, "
                    f"bạn có thể đã hoàn thành hoặc được miễn một số tín chỉ ở các học kỳ này)."
                )
            else:
                part_2_lines.append(f"- Tín chỉ còn thiếu: Cần tích lũy thêm ít nhất {missing_cr} tín chỉ để đủ {req_cr} tín chỉ.")
        if failed_courses:
            f_strs = [f"{f.get('ten_mon')} ({f.get('ma_mon') or 'chưa có mã'}, {f.get('tin_chi') if f.get('tin_chi') is not None else 'chưa rõ'} TC, điểm: {f.get('diem')})" for f in failed_courses]
            part_2_lines.append(f"- Môn chưa đạt / nợ điểm ({len(failed_courses)} môn cần học lại/thi lại): {'; '.join(f_strs)}.")
        if unverified_earlier:
            u_earlier_strs = [
                f"{u.get('ten_mon')} ({u.get('ma_mon') or 'chưa có mã'}, {u.get('tin_chi') if u.get('tin_chi') is not None else 'chưa rõ'} TC, CTĐT HK{u.get('hoc_ky_de_xuat')})"
                for u in unverified_earlier[:8]
            ]
            part_2_lines.append(
                f"- Chưa có dữ liệu để kết luận (có thể đã học hoặc được miễn, {len(unverified_earlier)} môn thuộc học kỳ < HK{min_sem}): "
                f"{'; '.join(u_earlier_strs)}{'...' if len(unverified_earlier) > 8 else ''}."
            )
        if missing_req:
            m_strs = [f"{m.get('ten_mon')} ({m.get('ma_mon') or 'chưa có mã'}, {m.get('tin_chi') if m.get('tin_chi') is not None else 'chưa rõ'} TC)" for m in missing_req[:8]]
            part_2_lines.append(f"- Môn bắt buộc CTĐT chưa học ({len(missing_req)} môn): {'; '.join(m_strs)}{'...' if len(missing_req) > 8 else ''}.")
        if unconfirmed:
            u_strs = [
                f"{u.get('ten_mon')} ({u.get('ma_mon') or 'chưa có mã'}, TC: {u.get('tin_chi') if u.get('tin_chi') is not None else 'chưa rõ'}, Điểm: {u.get('diem') if u.get('diem') is not None else 'chưa rõ'}) - Lý do: {u.get('ly_do')}"
                for u in unconfirmed
            ]
            part_2_lines.append(f"- Môn học cần xác nhận lại ({len(unconfirmed)} môn do thiếu tín chỉ/điểm, chưa tính vào tích lũy/GPA): {'; '.join(u_strs)}.")

        missing_certs = []
        if not certs.get("english"): missing_certs.append("Chứng chỉ Ngoại ngữ (chuẩn đầu ra quy định)")
        if not certs.get("it"): missing_certs.append("Chứng chỉ Tin học (chuẩn đầu ra quy định)")
        if not certs.get("gdqp"): missing_certs.append("Chứng chỉ GDQP-AN")
        if not certs.get("gdtc"): missing_certs.append("3 học phần GDTC (điểm P)")
        if not certs.get("soft_skills"): missing_certs.append("4 chứng chỉ Kỹ năng mềm")

        if missing_certs:
            part_2_lines.append(f"- Chuẩn đầu ra còn thiếu: {', '.join(missing_certs)}.")

    part_2 = "\n".join(part_2_lines)

    # ---------------- PHẦN 3: KẾ HOẠCH TỪNG HỌC KỲ ----------------
    part_3_lines = []
    if is_eligible or not plan:
        part_3_lines.append("- Hiện tại bạn không cần đăng ký thêm học phần nào. Hãy nộp hồ sơ xét tốt nghiệp theo thông báo của Nhà trường.")
    else:
        for idx, sem in enumerate(plan, 1):
            s_name = sem.get("semester_name", f"Học kỳ {idx}")
            s_cr = sem.get("total_credits", 0)
            s_courses = sem.get("courses", [])
            s_note = sem.get("note", "")

            course_items = []
            for c in s_courses:
                c_str = f"{c['ten_mon']} ({c.get('tin_chi') if c.get('tin_chi') is not None else 'chưa rõ'} TC, {c.get('loai', 'Học phần')})"
                if c.get("ghi_chu_tien_quyet"):
                    c_str += f" - {c['ghi_chu_tien_quyet']}"
                course_items.append(c_str)
            c_desc = ", ".join(course_items) if course_items else "Không có môn học"
            note_str = f" [Ghi chú: {s_note}]" if s_note else ""
            part_3_lines.append(f"+ {s_name} ({s_cr} tín chỉ): {c_desc}.{note_str}")

        part_3_lines.append(
            "- Lưu ý về kế hoạch: Định mức số tín chỉ tối đa mỗi học kỳ (gợi ý kỳ chính: 20 TC, kỳ hè: 8 TC) "
            "là mức tiến độ giả định của hệ thống nhằm cân bằng khối lượng học tập; sinh viên hãy xác nhận với "
            "Phòng Đào tạo về quy định số tín chỉ đăng ký tối đa chính thức."
        )

    part_3 = "\n".join(part_3_lines)

    # ---------------- PHẦN 4: RỦI RO VÀ LƯU Ý ----------------
    part_4_lines = []
    if summary.get("gpa_10", 0.0) < MIN_GRADUATION_GPA:
        part_4_lines.append(
            f"- Cảnh báo GPA: Điểm trung bình tích lũy hiện tại ({summary.get('gpa_10', 0.0)}/10) chưa đạt ngưỡng "
            f"tối thiểu 5.0 (thang 10) để xét tốt nghiệp theo tóm tắt trên trang web Khoa CNTT (chưa có văn bản gốc QĐ 1013). Bạn cần lên kế hoạch học cải thiện điểm các môn bị điểm D hoặc D+."
        )

    if failed_courses:
        part_4_lines.append("- Rủi ro tiên quyết: Cần ưu tiên học lại các môn nợ ngay ở học kỳ sớm nhất hoặc kỳ hè để tránh bị chặn đăng ký các môn chuyên ngành tiếp theo.")
    
    if not certs.get("english") or not certs.get("it"):
        part_4_lines.append("- Rủi ro chứng chỉ: Chuẩn đầu ra Ngoại ngữ và Tin học cần nộp trước thời điểm xét tốt nghiệp; sinh viên nên theo dõi lịch thi của Trung tâm Ngoại ngữ - Tin học để đăng ký thi sớm.")

    dkmh_url = getattr(settings, "DKMH_URL", "").strip()
    if dkmh_url:
        part_4_lines.append(f"- Thời hạn đăng ký: Đăng ký môn học theo đúng thông báo từng đợt của Phòng Đào tạo trên cổng {dkmh_url}.")
    else:
        part_4_lines.append("- Thời hạn đăng ký: Đăng ký môn học theo đúng thông báo từng đợt của Phòng Đào tạo hoặc liên hệ Phòng Đào tạo.")

    dao_tao_office = getattr(settings, "DAO_TAO_OFFICE", "").strip()
    if dao_tao_office:
        part_4_lines.append(f"- Khi cần hỗ trợ học vụ chính thức: Liên hệ Phòng Đào tạo (phòng {dao_tao_office}) hoặc Văn phòng Khoa Công nghệ thông tin để được giải quyết các trường hợp đặc biệt.")
    else:
        part_4_lines.append("- Khi cần hỗ trợ học vụ chính thức: Liên hệ Phòng Đào tạo hoặc Văn phòng Khoa Công nghệ thông tin để được giải quyết các trường hợp đặc biệt.")

    if rag_regulations:
        # Hỗ trợ cả danh sách chuỗi hoặc danh sách dict chunk (giữ nguyên nhãn VB1 như gốc)
        added_count = 0
        for r in rag_regulations:
            if added_count >= 2:
                break
            if isinstance(r, str) and r.strip():
                part_4_lines.append(r.strip())
                added_count += 1
            elif isinstance(r, dict) and r.get("title"):
                s_title = r.get("title", "")
                s_sec = r.get("section", "Chung")
                part_4_lines.append(f"- Căn cứ quy chế: {s_title} (Mục {s_sec})")
                added_count += 1

    part_4 = "\n".join(part_4_lines)

    return {
        "part_1": part_1,
        "part_2": part_2,
        "part_3": part_3,
        "part_4": part_4
    }


def format_advisory_response(parts: Dict[str, str]) -> str:
    """
    Ghép 4 phần có cấu trúc chuẩn thành văn bản trả lời hoàn chỉnh:
    (1) Tình trạng hiện tại
    (2) Còn thiếu gì
    (3) Kế hoạch từng học kỳ
    (4) Rủi ro và Lưu ý hành động
    """
    return (
        "### 1. TÌNH TRẠNG HIỆN TẠI\n"
        f"{parts.get('part_1', '')}\n\n"
        "### 2. CÒN THIẾU GÌ\n"
        f"{parts.get('part_2', '')}\n\n"
        "### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT\n"
        f"{parts.get('part_3', '')}\n\n"
        "### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ\n"
        f"{parts.get('part_4', '')}"
    )


def validate_and_repair_advisory_response(
    llm_response: str,
    structured_parts: Dict[str, str],
    grad_result: Optional[Dict[str, Any]] = None,
    rag_regulations: Optional[Union[List[str], List[Dict[str, Any]]]] = None
) -> str:
    """
    Hậu kiểm cấu trúc và chống bịa số liệu:
    1. Kiểm tra đủ 4 phần bắt buộc.
    2. Chuẩn hóa dấu phẩy thập phân kiểu Việt ("7,5" -> "7.5").
    3. Trích xuất tập số từ bản dựng sẵn của code (code_numbers).
    4. Trích xuất động số hiệu văn bản / điều khoản từ RAG (dynamic_rag_numbers),
       ví dụ trích '22' từ 'QĐ 22/QĐ-ĐHLH', '11' từ 'Điều 11', KHÔNG hardcode.
    5. Hậu kiểm ngữ nghĩa chống số bịa: GPA, tín chỉ thiếu, môn nợ, tín chỉ tích lũy.
    6. Hậu kiểm số lạ với whitelist thu hẹp có ngữ cảnh:
       Bỏ các số 1-8, 20, 8, 2.0/4.0/5.0 đứng tự do; chỉ cho phép khi đứng cạnh từ khóa tương ứng
       (học kỳ, tối đa tín chỉ, GPA, thang điểm, năm học, %).
    Nếu phát hiện số lạ/bịa -> Tự động fallback về bản dựng sẵn từ code.
    """
    if not llm_response or len(llm_response.strip()) < 80:
        return format_advisory_response(structured_parts)

    res_l = llm_response.lower()

    # 1. Kiểm tra sự hiện diện của 4 phần
    has_part_1 = any(k in res_l for k in ["tình trạng hiện tại", "1. tình trạng", "hiện tại:", "tín chỉ tích lũy"])
    has_part_2 = any(k in res_l for k in ["còn thiếu gì", "2. còn thiếu", "còn thiếu:", "môn chưa đạt", "môn nợ"])
    has_part_3 = any(k in res_l for k in ["kế hoạch", "học kỳ", "3. kế hoạch", "kỳ tới", "lộ trình"])
    has_part_4 = any(k in res_l for k in ["rủi ro", "lưu ý", "4. rủi ro", "hành động", "liên hệ"])

    if not (has_part_1 and has_part_2 and has_part_3 and has_part_4):
        logger.warning("LLM response thiếu 1 trong 4 phần bắt buộc, tự động kích hoạt fallback ghép từ code.")
        return format_advisory_response(structured_parts)

    # 2. Chuẩn hóa dấu phẩy thập phân kiểu Việt ("7,5" -> "7.5") cho cả LLM và code
    norm_llm = re.sub(r'(\d+),(\d+)', r'\1.\2', llm_response)
    code_text = format_advisory_response(structured_parts)
    norm_code = re.sub(r'(\d+),(\d+)', r'\1.\2', code_text)

    def extract_numeric_tokens(text: str) -> Set[float]:
        # Bỏ qua các URL tránh dính số trong link
        clean = re.sub(r'https?://\S+', '', text)
        nums = set()
        for tok in re.findall(r'\b\d+(?:\.\d+)?\b', clean):
            try:
                nums.add(float(tok))
            except ValueError:
                pass
        return nums

    code_numbers = extract_numeric_tokens(norm_code)

    # 3. Trích xuất động số hiệu văn bản / điều khoản từ RAG (không hardcode 11, 12, 19, 79)
    # Quy chế đào tạo chính thức của LHU là Quyết định số 22/QĐ-ĐHLH ("QĐ 22").
    # Các văn bản / điều khoản trích xuất trực tiếp từ các chunk RAG hoặc part_4:
    dynamic_rag_numbers: Set[float] = set()
    scan_sources = []
    if rag_regulations:
        for r in rag_regulations:
            if isinstance(r, dict):
                scan_sources.append(f"{r.get('title', '')} {r.get('section', '')} {r.get('so_hieu', '')} {r.get('snippet', '')} {r.get('content', '')}")
            elif isinstance(r, str):
                scan_sources.append(r)
    scan_sources.append(structured_parts.get("part_4", ""))
    
    combined_rag_text = " ".join(scan_sources)
    for m in re.finditer(r'(?i)\b(?:QĐ|Quyết định|Điều|Khoản|Mục|Thông tư|TT|Số)\s*(\d+(?:\.\d+)?)', combined_rag_text):
        try:
            dynamic_rag_numbers.add(float(m.group(1)))
        except ValueError:
            pass

    # 4. HẬU KIỂM NGỮ NGHĨA CHỐNG SỐ BỊA
    # 4.1. Hậu kiểm GPA bịa
    m_gpa_code = re.search(r"GPA(?:\s*\([^)]*\))?:\s*([0-9]+(?:\.[0-9]+)?)", norm_code, re.IGNORECASE)
    expected_gpa = float(m_gpa_code.group(1)) if m_gpa_code else None
    if expected_gpa is not None:
        llm_gpas = re.findall(r"(?:gpa|điểm trung bình tích lũy|điểm tb tích lũy)[:\s]+([0-9]+(?:\.[0-9]+)?)", norm_llm, re.IGNORECASE)
        for g_str in llm_gpas:
            try:
                g_val = float(g_str)
                if abs(g_val - expected_gpa) > 0.05 and g_val not in code_numbers:
                    logger.warning("LLM bịa điểm GPA: kỳ vọng %.2f, LLM trả %s. Fallback về code.", expected_gpa, g_str)
                    return format_advisory_response(structured_parts)
            except ValueError:
                pass

    # 4.2. Hậu kiểm Tín chỉ còn thiếu bịa
    m_missing_code = re.search(r"(?:còn thiếu|tích lũy thêm)\s*(?:ít nhất|tối đa|khoảng)?\s*([0-9]+)\s*tín chỉ", norm_code, re.IGNORECASE)
    expected_missing = int(m_missing_code.group(1)) if m_missing_code else None
    if expected_missing is not None:
        llm_missings = re.findall(r"(?:còn thiếu|thiếu|tích lũy thêm)\s*(?:ít nhất|tối đa|khoảng)?\s*([0-9]+)\s*tín chỉ", norm_llm, re.IGNORECASE)
        for mis_str in llm_missings:
            try:
                mis_val = int(mis_str)
                if mis_val != expected_missing:
                    logger.warning("LLM bịa số tín chỉ còn thiếu: kỳ vọng %d, LLM trả %s. Fallback về code.", expected_missing, mis_str)
                    return format_advisory_response(structured_parts)
            except ValueError:
                pass

    # 4.3. Hậu kiểm Số môn nợ & Số lượng môn học bịa
    m_failed_code = re.search(r"(?:môn chưa đạt|môn nợ|nợ điểm)\s*(?:\()?\s*([0-9]+)\s*môn", norm_code, re.IGNORECASE)
    expected_failed_cnt = int(m_failed_code.group(1)) if m_failed_code else None
    if expected_failed_cnt is not None:
        llm_failed_cnts = re.findall(r"(?:môn chưa đạt|môn nợ|nợ điểm|đang nợ|nợ)\s*(?:\()?\s*([0-9]+)\s*môn", norm_llm, re.IGNORECASE)
        for f_str in llm_failed_cnts:
            try:
                f_val = int(f_str)
                if f_val != expected_failed_cnt:
                    logger.warning("LLM bịa số môn nợ: kỳ vọng %d, LLM trả %s. Fallback về code.", expected_failed_cnt, f_str)
                    return format_advisory_response(structured_parts)
            except ValueError:
                pass

    # Toàn bộ số lượng môn học (X môn) trong câu trả lời LLM phải khớp với số lượng môn có trong kết quả code
    code_mon_counts = set(int(x) for x in re.findall(r'(\d+)\s*môn', norm_code))
    llm_mon_counts = re.findall(r'(\d+)\s*môn', norm_llm)
    for m_cnt_str in llm_mon_counts:
        try:
            m_cnt_val = int(m_cnt_str)
            if m_cnt_val not in code_mon_counts:
                logger.warning("LLM bịa số lượng môn học: %d môn (không có trong kết quả code: %s). Fallback về code.", m_cnt_val, code_mon_counts)
                return format_advisory_response(structured_parts)
        except ValueError:
            pass

    # 4.4. Hậu kiểm Tín chỉ tích lũy bịa
    m_exp_pass = re.search(r"(\d+)\s*/\s*(\d+)\s*tín chỉ", structured_parts.get("part_1", ""))
    if m_exp_pass:
        exp_passed = int(m_exp_pass.group(1))
        exp_req = int(m_exp_pass.group(2))
        matches_passed = re.findall(r"(?:đã đạt|tích lũy|tích luỹ|hoàn thành)\s*([0-9]+)\s*(?:/\s*([0-9]+))?\s*(?:tín chỉ|tc)", norm_llm, re.IGNORECASE)
        for p_str, r_str in matches_passed:
            p_val = int(p_str)
            if p_val != exp_passed:
                logger.warning("LLM bịa số tín chỉ tích lũy: kỳ vọng %d, LLM trả %s. Fallback về code.", exp_passed, p_str)
                return format_advisory_response(structured_parts)
            if r_str and int(r_str) != exp_req:
                logger.warning("LLM bịa tổng tín chỉ yêu cầu: kỳ vọng %d, LLM trả %s. Fallback về code.", exp_req, r_str)
                return format_advisory_response(structured_parts)

    # 5. HẬU KIỂM TOÀN BỘ SỐ LẠ VỚI WHITELIST THU HẸP CÓ NGỮ CẢNH:
    # Tuyệt đối không cho phép các số bare 1-8, 20, 8, 2.0/4.0/5.0 lọt qua mà không có ngữ cảnh rõ ràng.
    llm_numbers = extract_numeric_tokens(norm_llm)
    for n in llm_numbers:
        if n in code_numbers:
            continue

        # Kiểm tra tính hợp lệ theo ngữ cảnh:
        is_valid = False
        int_n = int(n) if n.is_integer() else None

        # (a) Số trích dẫn văn bản / điều khoản từ RAG (ví dụ QĐ 22, Điều 11)
        if n in dynamic_rag_numbers and int_n is not None:
            if re.search(rf'(?i)\b(?:QĐ|Quyết định|Điều|Khoản|Mục|Thông tư|TT|Số)\s*{int_n}\b', norm_llm):
                is_valid = True

        # (b) Năm học (2020..2030)
        if int_n is not None and 2020 <= int_n <= 2030:
            is_valid = True

        # (c) Thứ tự học kỳ đi kèm từ khóa (Học kỳ 1..12, HK1..12)
        if int_n is not None and 1 <= int_n <= 12:
            if re.search(rf'(?i)\b(?:học kỳ|hk)\s*{int_n}\b', norm_llm):
                is_valid = True

        # (d) Giới hạn tín chỉ đi kèm từ khóa (tối đa 20 tín chỉ, tối đa 8 tín chỉ hè)
        if int_n in (8, 20):
            if re.search(rf'(?i)\b(?:tối đa|giới hạn)\s*{int_n}\s*tín chỉ\b', norm_llm):
                is_valid = True

        # (e) Ngưỡng GPA học vụ đi kèm từ khóa (GPA >= 5.0, GPA tối thiểu 2.0, 4.0)
        if n in (2.0, 4.0, 5.0):
            if re.search(rf'(?i)\b(?:gpa|điểm trung bình)(?:[^\.\n]{{0,30}}){re.escape(str(n))}\b', norm_llm):
                is_valid = True

        # (f) Thang điểm (thang 10, thang điểm 4)
        if int_n in (4, 10):
            if re.search(rf'(?i)\bthang\s+(?:điểm\s+)?{int_n}\b', norm_llm):
                is_valid = True

        # (g) Tỷ lệ phần trăm (% đi kèm)
        if int_n is not None and re.search(rf'\b{int_n}\s*%', norm_llm):
            is_valid = True

        if not is_valid:
            logger.warning(
                "Phát hiện số lạ/bịa trong LLM response: %s (không nằm trong code_numbers và không thỏa mãn điều kiện ngữ cảnh hợp lệ). Fallback về code.",
                n
            )
            return format_advisory_response(structured_parts)

    return llm_response


# Danh mục môn học CTĐT CNTT chuẩn LHU (Fallback độc lập)
DEFAULT_CNTT_CURRICULUM = [
    # HK1 (17 TC)
    {"ma_mon": "102073", "ten_mon": "Toán cao cấp 1", "tin_chi": 4, "hoc_ky_de_xuat": 1, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "102074", "ten_mon": "English 1", "tin_chi": 3, "hoc_ky_de_xuat": 1, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111094", "ten_mon": "Nhập môn lập trình", "tin_chi": 2, "hoc_ky_de_xuat": 1, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111001", "ten_mon": "Cấu trúc và lắp ráp máy tính", "tin_chi": 3, "hoc_ky_de_xuat": 1, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111080", "ten_mon": "Phần mềm mã nguồn mở", "tin_chi": 2, "hoc_ky_de_xuat": 1, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111055", "ten_mon": "Nhập môn Công nghệ thông tin", "tin_chi": 1, "hoc_ky_de_xuat": 1, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111053", "ten_mon": "Nhập môn Phát triển dự án kỹ thuật", "tin_chi": 2, "hoc_ky_de_xuat": 1, "is_required": True, "mon_tien_quyet": []},

    # HK2 (20 TC)
    {"ma_mon": "102087", "ten_mon": "Xác suất thống kê", "tin_chi": 2, "hoc_ky_de_xuat": 2, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "102075", "ten_mon": "English 2", "tin_chi": 4, "hoc_ky_de_xuat": 2, "is_required": True, "mon_tien_quyet": ["102074"]}, # Học trước: 102074
    {"ma_mon": "102014", "ten_mon": "Tin học đại cương", "tin_chi": 3, "hoc_ky_de_xuat": 2, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111046", "ten_mon": "Vật lý thực hành", "tin_chi": 3, "hoc_ky_de_xuat": 2, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111047", "ten_mon": "Điện tử cơ bản", "tin_chi": 2, "hoc_ky_de_xuat": 2, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111056", "ten_mon": "Thiết kế UI/UX", "tin_chi": 2, "hoc_ky_de_xuat": 2, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111058", "ten_mon": "Kỹ thuật lập trình", "tin_chi": 2, "hoc_ky_de_xuat": 2, "is_required": True, "mon_tien_quyet": ["111094"]}, # Học trước: 111094
    {"ma_mon": "112061", "ten_mon": "Mạng máy tính", "tin_chi": 2, "hoc_ky_de_xuat": 2, "is_required": True, "mon_tien_quyet": []},

    # HK3 (25 TC)
    {"ma_mon": "102063", "ten_mon": "Triết học Mác - Lênin", "tin_chi": 3, "hoc_ky_de_xuat": 3, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "102064", "ten_mon": "Kinh tế chính trị Mác - Lênin", "tin_chi": 2, "hoc_ky_de_xuat": 3, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "102065", "ten_mon": "Chủ nghĩa xã hội khoa học", "tin_chi": 2, "hoc_ky_de_xuat": 3, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "102076", "ten_mon": "English 3", "tin_chi": 4, "hoc_ky_de_xuat": 3, "is_required": True, "mon_tien_quyet": ["102075"]}, # Học trước: 102075
    {"ma_mon": "111010", "ten_mon": "Toán rời rạc", "tin_chi": 3, "hoc_ky_de_xuat": 3, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111062", "ten_mon": "Cấu trúc dữ liệu và giải thuật", "tin_chi": 3, "hoc_ky_de_xuat": 3, "is_required": True, "mon_tien_quyet": ["111058"]}, # Học trước: 111058
    {"ma_mon": "111048", "ten_mon": "Tín hiệu số cơ bản", "tin_chi": 2, "hoc_ky_de_xuat": 3, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111059", "ten_mon": "Cơ sở dữ liệu", "tin_chi": 3, "hoc_ky_de_xuat": 3, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "112064", "ten_mon": "Mạng máy tính nâng cao", "tin_chi": 3, "hoc_ky_de_xuat": 3, "is_required": True, "mon_tien_quyet": ["112061"]}, # Học trước: 112061

    # HK4 (21 TC)
    {"ma_mon": "102033", "ten_mon": "Tư tưởng Hồ Chí Minh", "tin_chi": 2, "hoc_ky_de_xuat": 4, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "102006", "ten_mon": "Pháp luật đại cương", "tin_chi": 2, "hoc_ky_de_xuat": 4, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "102077", "ten_mon": "English 4", "tin_chi": 4, "hoc_ky_de_xuat": 4, "is_required": True, "mon_tien_quyet": ["102076"]}, # Học trước: 102076
    {"ma_mon": "111036", "ten_mon": "Dịch vụ mạng", "tin_chi": 3, "hoc_ky_de_xuat": 4, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111070", "ten_mon": "Lập trình hướng đối tượng", "tin_chi": 3, "hoc_ky_de_xuat": 4, "is_required": True, "mon_tien_quyet": ["111062"]}, # Học trước: 111062
    {"ma_mon": "111060", "ten_mon": "Hệ quản trị CSDL", "tin_chi": 3, "hoc_ky_de_xuat": 4, "is_required": True, "mon_tien_quyet": ["111059"]}, # Học trước: 111059
    {"ma_mon": "111067", "ten_mon": "Lập trình Front-End", "tin_chi": 2, "hoc_ky_de_xuat": 4, "is_required": True, "mon_tien_quyet": ["111056"]}, # Học trước: 111056
    {"ma_mon": "111081", "ten_mon": "Kiến tập", "tin_chi": 2, "hoc_ky_de_xuat": 4, "is_required": True, "mon_tien_quyet": []},

    # HK5 (20 TC)
    {"ma_mon": "102066", "ten_mon": "Lịch sử Đảng Cộng sản Việt Nam", "tin_chi": 2, "hoc_ky_de_xuat": 5, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "102078", "ten_mon": "English 5", "tin_chi": 4, "hoc_ky_de_xuat": 5, "is_required": True, "mon_tien_quyet": ["102077"]}, # Học trước: 102077
    {"ma_mon": "111057", "ten_mon": "Nguyên lý thống kê", "tin_chi": 2, "hoc_ky_de_xuat": 5, "is_required": True, "mon_tien_quyet": ["102087"]}, # Học trước: 102087
    {"ma_mon": "112065", "ten_mon": "Thiết kế hệ thống mạng", "tin_chi": 3, "hoc_ky_de_xuat": 5, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111066", "ten_mon": "Lập trình Back-End", "tin_chi": 3, "hoc_ky_de_xuat": 5, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111072", "ten_mon": "Lập trình trên môi trường Windows", "tin_chi": 3, "hoc_ky_de_xuat": 5, "is_required": True, "mon_tien_quyet": ["111060", "111070"]}, # Học trước: 111060, 111070
    {"ma_mon": "111043", "ten_mon": "Phân tích thiết kế hệ thống hướng đối tượng", "tin_chi": 3, "hoc_ky_de_xuat": 5, "is_required": True, "mon_tien_quyet": ["111059", "111060"]}, # Nhánh tự chọn 1 (Chọn 1/2). Học trước: 111059, 111060
    {"ma_mon": "111089", "ten_mon": "Phân tích thiết kế hệ thống hướng quan hệ", "tin_chi": 3, "hoc_ky_de_xuat": 5, "is_required": False, "mon_tien_quyet": []}, # Nhánh tự chọn 2 (Chọn 1/2)

    # HK6 (16 TC)
    {"ma_mon": "102079", "ten_mon": "English 6", "tin_chi": 4, "hoc_ky_de_xuat": 6, "is_required": True, "mon_tien_quyet": ["102078"]}, # Học trước: 102078
    {"ma_mon": "112068", "ten_mon": "Thiết kế hệ thống mạng nâng cao", "tin_chi": 2, "hoc_ky_de_xuat": 6, "is_required": True, "mon_tien_quyet": ["112065"]}, # Học trước: 112065
    {"ma_mon": "111069", "ten_mon": "Lập trình giao tiếp thiết bị", "tin_chi": 2, "hoc_ky_de_xuat": 6, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111082", "ten_mon": "Lập trình ứng dụng di động", "tin_chi": 3, "hoc_ky_de_xuat": 6, "is_required": True, "mon_tien_quyet": ["111066"]}, # Học trước: 111066
    {"ma_mon": "111083", "ten_mon": "Lập trình ứng dụng web", "tin_chi": 3, "hoc_ky_de_xuat": 6, "is_required": True, "mon_tien_quyet": ["111066", "111067"]}, # Học trước: 111066, 111067
    {"ma_mon": "111071", "ten_mon": "Lập trình Python cho học máy", "tin_chi": 2, "hoc_ky_de_xuat": 6, "is_required": True, "mon_tien_quyet": []}, # Nhánh tự chọn 1 (Chọn 1/2)
    {"ma_mon": "111084", "ten_mon": "Lập trình Python trong thị giác máy tính", "tin_chi": 2, "hoc_ky_de_xuat": 6, "is_required": False, "mon_tien_quyet": []}, # Nhánh tự chọn 2 (Chọn 1/2)

    # HK7 (21 TC)
    {"ma_mon": "102080", "ten_mon": "English 7", "tin_chi": 4, "hoc_ky_de_xuat": 7, "is_required": True, "mon_tien_quyet": ["102079"]}, # Học trước: 102079
    {"ma_mon": "111065", "ten_mon": "Kiểm thử và đảm bảo chất lượng phần mềm", "tin_chi": 3, "hoc_ky_de_xuat": 7, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111085", "ten_mon": "Quản trị website trên VPS", "tin_chi": 2, "hoc_ky_de_xuat": 7, "is_required": True, "mon_tien_quyet": []},
    {"ma_mon": "111038", "ten_mon": "Phát triển ứng dụng", "tin_chi": 9, "hoc_ky_de_xuat": 7, "is_required": True, "mon_tien_quyet": ["111069", "111082", "111083"]}, # Học trước: 111069, 111082, 111083
    {"ma_mon": "111088", "ten_mon": "Trí tuệ nhân tạo", "tin_chi": 3, "hoc_ky_de_xuat": 7, "is_required": True, "mon_tien_quyet": ["111071"]}, # Nhánh tự chọn 1 (Chọn 1/2). Học trước: 111071
    {"ma_mon": "111061", "ten_mon": "Công nghệ Blockchain", "tin_chi": 3, "hoc_ky_de_xuat": 7, "is_required": False, "mon_tien_quyet": []}, # Nhánh tự chọn 2 (Chọn 1/2)

    # HK8 (10 TC)
    {"ma_mon": "111049", "ten_mon": "Thực tập", "tin_chi": 2, "hoc_ky_de_xuat": 8, "is_required": True, "mon_tien_quyet": ["111081"]}, # Học trước: 111081
    {"ma_mon": "33333", "ten_mon": "Tốt nghiệp", "tin_chi": 8, "hoc_ky_de_xuat": 8, "is_required": True, "mon_tien_quyet": [], "mon_song_hanh": ["111049"]} # Song hành: 111049
]


def load_curriculum_from_db(db=None, major: str = "Công nghệ thông tin") -> List[Dict[str, Any]]:
    """Tải CTĐT từ database; nếu DB trống hoặc lỗi thì dùng DEFAULT_CNTT_CURRICULUM."""
    if db is not None:
        try:
            from sqlalchemy import text
            sql = """
                SELECT c.code AS ma_mon, c.name AS ten_mon, c.credits AS tin_chi, 
                       pc.hoc_ky AS hoc_ky_de_xuat, pc.is_required
                FROM program_courses pc
                JOIN courses c ON pc.course_id = c.id
                WHERE pc.major = :major
            """
            rows = db.execute(text(sql), {"major": major}).fetchall()
            if rows and len(rows) >= 10:
                result = []
                for r in rows:
                    result.append({
                        "ma_mon": r.ma_mon,
                        "ten_mon": r.ten_mon,
                        "tin_chi": r.tin_chi,
                        "hoc_ky_de_xuat": r.hoc_ky_de_xuat or 1,
                        "is_required": bool(r.is_required),
                        "mon_tien_quyet": [],
                        "mon_song_hanh": []
                    })
                # Merge quan hệ tiên quyết & song hành từ DEFAULT_CNTT_CURRICULUM
                prereq_map = {c["ma_mon"]: c.get("mon_tien_quyet", []) for c in DEFAULT_CNTT_CURRICULUM}
                song_hanh_map = {c["ma_mon"]: c.get("mon_song_hanh", []) for c in DEFAULT_CNTT_CURRICULUM}
                for res in result:
                    if res["ma_mon"] in prereq_map:
                        res["mon_tien_quyet"] = prereq_map[res["ma_mon"]]
                    if res["ma_mon"] in song_hanh_map:
                        res["mon_song_hanh"] = song_hanh_map[res["ma_mon"]]
                return result
        except Exception as e:
            logger.warning(f"Không thể đọc CTĐT từ DB ({e}), sử dụng CTĐT mặc định.")

    return list(DEFAULT_CNTT_CURRICULUM)

