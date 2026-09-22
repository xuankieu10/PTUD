"""
Module so khớp chứng chỉ sinh viên với các điều kiện tốt nghiệp của nhà trường.
Sử dụng thư viện rapidfuzz để so khớp mờ (Fuzzy Matching) giữa loại chứng chỉ /
tên chứng chỉ trích xuất từ ảnh với danh mục điều kiện tốt nghiệp chuẩn.

Nguyên tắc an toàn:
- CHỈ tự động cập nhật trạng thái 'Đã hoàn tất' khi:
  + Độ tin cậy trích xuất là 'cao'
  + Khớp rõ ràng và có độ tương đồng cao với 1 trong các mục điều kiện tốt nghiệp
- Nếu độ tin cậy 'thap', 'trung binh', 'Không xác định' hoặc không khớp mục nào:
  -> Trả về 'Cần xác nhận thủ công' kèm dữ liệu đã trích xuất, tuyệt đối không tự cập nhật sai.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Danh mục điều kiện tốt nghiệp chuẩn tại trường
DEFAULT_REQUIRED_CATEGORIES = ["Ngoại ngữ", "Tin học", "Quốc phòng", "Thể chất"]

# Từ điển các từ khóa / tên gọi thực tế thường gặp của từng loại chứng chỉ
CATEGORY_KEYWORD_MAP: Dict[str, List[str]] = {
    "Ngoại ngữ": [
        "ngoại ngữ", "tiếng anh", "toeic", "ielts", "toefl", "vstep", "cambridge",
        "tiếng anh b1", "tiếng anh b2", "chứng chỉ b1", "chứng chỉ b2", "vstep b1", "vstep b2",
        "cefr b1", "cefr b2", "cefr c1", "tiếng nhật", "jlpt", "tiếng nhật n1", "tiếng nhật n2",
        "tiếng nhật n3", "tiếng nhật n4", "tiếng nhật n5", "tiếng hàn", "topik", "tiếng trung",
        "hsk", "tiếng pháp", "delf", "english", "chứng chỉ ngoại ngữ", "khung năng lực ngoại ngữ"
    ],
    "Tin học": [
        "tin học", "mos", "ic3", "cntt", "công nghệ thông tin", "tin học ứng dụng",
        "tin học văn phòng", "icdl", "chuẩn kỹ năng sử dụng cntt", "chứng chỉ tin học",
        "kỹ năng cntt cơ bản", "kỹ năng cntt nâng cao", "word", "excel", "powerpoint",
        "tin học đại cương"
    ],
    "Quốc phòng": [
        "quốc phòng", "gdqp", "giáo dục quốc phòng", "an ninh", "quốc phòng và an ninh",
        "quân sự", "giáo dục quốc phòng - an ninh", "gdqp&an", "quốc phòng an ninh",
        "giấy chứng nhận gdqp", "chứng chỉ giáo dục quốc phòng"
    ],
    "Thể chất": [
        "thể chất", "gdtc", "giáo dục thể chất", "thể dục", "bơi lội", "điền kinh",
        "thể thao", "chứng nhận thể chất", "giáo dục thể chất và thể thao",
        "giấy chứng nhận gdtc", "chứng chỉ giáo dục thể chất"
    ]
}

# Ngưỡng điểm fuzzy match tối thiểu (0-100) để công nhận khớp danh mục
FUZZY_MATCH_THRESHOLD = 70.0


def _normalize_text(text: Optional[str]) -> str:
    """Chuẩn hóa chuỗi văn bản để so khớp: chữ thường, loại bỏ khoảng trắng thừa."""
    if not text:
        return ""
    return " ".join(str(text).strip().lower().split())


def find_best_category_match(
    loai_chung_chi: str,
    ten_chung_chi_cu_the: str,
    required_list: List[str]
) -> Tuple[Optional[str], float, str]:
    """
    Tìm danh mục phù hợp nhất trong required_list dựa trên:
    1. So khớp trực tiếp tên danh mục
    2. So khớp từ khóa / từ đồng nghĩa (Keyword Lookup)
    3. So khớp mờ (Fuzzy Token Ratio) qua thư viện rapidfuzz

    Returns:
        (best_category, best_score, match_method)
    """
    loai_norm = _normalize_text(loai_chung_chi)
    ten_norm = _normalize_text(ten_chung_chi_cu_the)
    combined_text = f"{loai_norm} {ten_norm}".strip()

    if not loai_norm and not ten_norm:
        return None, 0.0, "empty_input"

    # 1. So khớp trực tiếp tên danh mục chuẩn (Exact Match)
    for cat in required_list:
        cat_norm = _normalize_text(cat)
        if loai_norm == cat_norm:
            return cat, 100.0, "exact_category_match"

    # 2. Kiểm tra từ khóa đặc trưng (Keyword Substring Match)
    for cat in required_list:
        keywords = CATEGORY_KEYWORD_MAP.get(cat, [])
        for kw in keywords:
            kw_norm = _normalize_text(kw)
            # Kiểm tra từ khóa xuất hiện như một từ nguyên vẹn
            if kw_norm and (
                kw_norm in loai_norm.split()
                or kw_norm in ten_norm.split()
                or (len(kw_norm) >= 4 and kw_norm in combined_text)
            ):
                return cat, 95.0, f"keyword_match ({kw})"

    # 3. So khớp mờ bằng rapidfuzz (Fuzzy Matching)
    best_cat: Optional[str] = None
    best_score: float = 0.0
    best_kw: str = ""

    for cat in required_list:
        cat_norm = _normalize_text(cat)
        # Điểm so khớp với tên danh mục
        score_cat_name = fuzz.token_sort_ratio(combined_text, cat_norm)
        score_partial_name = fuzz.partial_ratio(loai_norm, cat_norm)
        current_max = max(score_cat_name, score_partial_name)

        # Điểm so khớp với các từ khóa con
        for kw in CATEGORY_KEYWORD_MAP.get(cat, []):
            kw_norm = _normalize_text(kw)
            s1 = fuzz.token_sort_ratio(loai_norm, kw_norm)
            s2 = fuzz.token_set_ratio(ten_norm, kw_norm)
            s3 = fuzz.partial_ratio(combined_text, kw_norm)
            kw_score = max(s1, s2, s3)
            if kw_score > current_max:
                current_max = kw_score
                best_kw = kw

        if current_max > best_score:
            best_score = float(current_max)
            best_cat = cat

    if best_score >= FUZZY_MATCH_THRESHOLD:
        return best_cat, best_score, f"fuzzy_match ({best_kw or best_cat}: {best_score:.1f}%)"

    return None, best_score, "no_match"


def match_certificate(
    extracted_json: Dict[str, Any],
    required_list: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Xác định chứng chỉ khớp với mục nào trong danh sách điều kiện tốt nghiệp
    và đưa ra gợi ý cập nhật trạng thái tốt nghiệp.

    Args:
        extracted_json: Dict chứa các trường do extractor trích xuất:
            - loai_chung_chi (str)
            - ten_chung_chi_cu_the (str)
            - ten_nguoi_duoc_cap (str | None)
            - ngay_cap (str | None)
            - do_tin_cay (str: 'cao' | 'trung binh' | 'thap')
        required_list: Danh sách các điều kiện tốt nghiệp cần đối chiếu
            (mặc định: ["Ngoại ngữ", "Tin học", "Quốc phòng", "Thể chất"])

    Returns:
        Dict chi tiết kết quả so khớp:
            - muc_tot_nghiep_khop: Tên danh mục chuẩn khớp được hoặc None
            - do_tuong_dong: Điểm tương đồng % (0 - 100)
            - phuong_thuc_khop: Cách thức khớp (exact, keyword, fuzzy)
            - trang_thai_cap_nhat: 'Đã hoàn tất' | 'Cần xác nhận thủ công'
            - tu_dong_cap_nhat: True | False
            - ly_do: Giải thích quyết định
            - thong_tin_trich_xuat: Bản sao dữ liệu gốc đã trích xuất
    """
    if required_list is None:
        required_list = DEFAULT_REQUIRED_CATEGORIES

    loai_chung_chi = str(extracted_json.get("loai_chung_chi") or "").strip()
    ten_chung_chi = str(extracted_json.get("ten_chung_chi_cu_the") or "").strip()
    do_tin_cay = str(extracted_json.get("do_tin_cay") or "thap").strip().lower()

    # Thực hiện so khớp với danh mục chuẩn
    best_cat, score, method = find_best_category_match(
        loai_chung_chi,
        ten_chung_chi,
        required_list
    )

    # Đánh giá quy tắc an toàn:
    # 1. Điều kiện từ chối tự động (BẮT BUỘC cần xác nhận thủ công):
    # - do_tin_cay là 'thap' hoặc 'trung binh'
    # - loai_chung_chi là 'Không xác định'
    # - Không tìm thấy danh mục khớp (best_cat is None)
    is_unknown = loai_chung_chi.lower() in ("không xác định", "unknown", "")
    is_low_confidence = do_tin_cay in ("thap", "trung binh")
    no_category_matched = best_cat is None

    if is_unknown or is_low_confidence or no_category_matched:
        tu_dong_cap_nhat = False
        trang_thai_cap_nhat = "Cần xác nhận thủ công"

        reasons = []
        if is_unknown:
            reasons.append("Loại chứng chỉ không xác định hoặc không rõ ràng")
        if do_tin_cay == "thap":
            reasons.append("Độ tin cậy trích xuất từ ảnh thấp (ảnh có thể mờ hoặc mất nét)")
        elif do_tin_cay == "trung binh":
            reasons.append("Độ tin cậy ở mức trung bình, cần cán bộ đào tạo kiểm tra lại")
        if no_category_matched:
            reasons.append(f"Không khớp với bất kỳ điều kiện tốt nghiệp nào trong danh sách: {required_list}")

        ly_do = "; ".join(reasons)
    else:
        # 2. Điều kiện tự động cập nhật 'Đã hoàn tất':
        # - do_tin_cay là 'cao'
        # - Khớp rõ ràng danh mục chuẩn
        tu_dong_cap_nhat = True
        trang_thai_cap_nhat = "Đã hoàn tất"
        ly_do = f"Khớp rõ ràng với điều kiện tốt nghiệp '{best_cat}' và độ tin cậy trích xuất cao"

    result = {
        "muc_tot_nghiep_khop": best_cat,
        "do_tuong_dong": round(score, 1),
        "phuong_thuc_khop": method,
        "trang_thai_cap_nhat": trang_thai_cap_nhat,
        "tu_dong_cap_nhat": tu_dong_cap_nhat,
        "ly_do": ly_do,
        "thong_tin_trich_xuat": {
            "loai_chung_chi": loai_chung_chi,
            "ten_chung_chi_cu_the": ten_chung_chi,
            "ten_nguoi_duoc_cap": extracted_json.get("ten_nguoi_duoc_cap"),
            "ngay_cap": extracted_json.get("ngay_cap"),
            "do_tin_cay": do_tin_cay
        }
    }

    logger.info(
        f"Kết quả so khớp chứng chỉ: Mục='{best_cat}' ({score}%) | "
        f"Trạng thái='{trang_thai_cap_nhat}' | Tự động={tu_dong_cap_nhat}"
    )
    return result
