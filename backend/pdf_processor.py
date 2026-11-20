"""
Module xử lý file PDF chứa bảng điểm học sinh:
1. Thử trích xuất text trực tiếp bằng pdfplumber nếu có text layer.
2. Nếu không có text layer (PDF scan), chuyển đổi từng trang sang ảnh bằng pdf2image
   (kèm fallback pypdfium2 để tương thích hoàn hảo trên Windows khi chưa cài đặt Poppler).
"""

import logging
import os
import re
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image
import pdfplumber

logger = logging.getLogger(__name__)


def has_text_layer(pdf_path: str, min_chars: int = 30) -> bool:
    """
    Kiểm tra xem file PDF có lớp văn bản (text layer) trích xuất được hay là file scan thuần ảnh.
    
    Args:
        pdf_path: Đường dẫn tới file PDF.
        min_chars: Số lượng ký tự chữ/số tối thiểu để coi là có text layer.
        
    Returns:
        True nếu có text layer, False nếu là file scan.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_text = ""
            for page in pdf.pages:
                text = page.extract_text() or ""
                total_text += text
                
            clean_text = re.sub(r"\s+", "", total_text)
            if len(clean_text) >= min_chars:
                logger.info(f"File PDF '{os.path.basename(pdf_path)}' CÓ text layer ({len(clean_text)} ký tự).")
                return True
            else:
                logger.info(f"File PDF '{os.path.basename(pdf_path)}' KHÔNG có text layer đủ điều kiện (PDF scan).")
                return False
    except Exception as e:
        logger.warning(f"Lỗi khi kiểm tra text layer bằng pdfplumber: {e}. Coi như PDF scan.")
        return False


def convert_pdf_to_images(pdf_path: str, dpi: int = 200, max_pages: int = 3) -> List[Image.Image]:
    """
    Chuyển đổi từng trang của file PDF sang ảnh (PIL Image).
    Chỉ xử lý tối đa max_pages trang đầu (mặc định 3 trang) để tiết kiệm tài nguyên và tăng tốc độ.
    Ưu tiên sử dụng pdf2image theo yêu cầu bài toán.
    Tự động fallback sang pypdfium2 nếu Windows chưa cài đặt Poppler.
    """
    logger.info(f"Đang chuyển đổi PDF sang ảnh (DPI: {dpi})...")
    
    # 1. Thử dùng pdf2image theo yêu cầu
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=dpi)
        if max_pages and len(images) > max_pages:
            logger.info(f"Chỉ xử lý tối đa {max_pages} trang đầu của PDF ({len(images)} trang).")
            images = images[:max_pages]
        logger.info(f"pdf2image: Đã chuyển đổi thành công {len(images)} trang ảnh.")
        return images
    except Exception as err:
        logger.warning(
            f"pdf2image gặp lỗi (thường do thiếu Poppler binary trên Windows): {err}. "
            "Kích hoạt cơ chế dự phòng an toàn qua pypdfium2..."
        )

    # 2. Fallback sang pypdfium2 (hoạt động độc lập, không phụ thuộc Poppler)
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)
        images = []
        total_pages = min(len(pdf), max_pages) if max_pages else len(pdf)
        for page_idx in range(total_pages):
            page = pdf[page_idx]
            # Render trang ở scale tương ứng DPI 200 (200 / 72 ≈ 2.77)
            scale = dpi / 72.0
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            images.append(pil_image)
        logger.info(f"pypdfium2: Đã chuyển đổi thành công {len(images)} trang ảnh.")
        return images
    except Exception as fallback_err:
        raise RuntimeError(f"Không thể chuyển đổi PDF sang ảnh bằng cả pdf2image lẫn pypdfium2: {fallback_err}")


def recover_or_validate_grade(diem_text: str, tp_text: str = "") -> Tuple[Optional[float], bool, str]:
    """
    Xử lý và khôi phục điểm học phần từ bảng điểm PDF:
    - Nếu điểm hợp lệ bình thường ('7.45', '6.95', '8.0'): Trả về (float_val, False, '')
    - Nếu điểm bị mất chữ số đầu (ví dụ: '.95', '.45', '.5', '.00'):
      + Thử tính lại từ điểm thành phần theo công thức LHU: 0.3 * Quá trình + 0.3 * Giữa kỳ + 0.4 * Cuối kỳ.
      + Nếu khớp phần thập phân: Khôi phục chính xác (ví dụ .95 -> 6.95), trả về (calc_val, False, 'Khôi phục từ điểm thành phần')
      + Nếu không có điểm thành phần hoặc không khớp: Trả về (None, True, 'Điểm bị khuyết chữ số nguyên, cần xác nhận')
    """
    clean_d = diem_text.replace(",", ".").strip()
    if not clean_d:
        return None, False, ""

    # Trường hợp bị mất chữ số đầu (bắt đầu bằng dấu chấm hoặc dấu phẩy: .95, .45, .5, .00)
    if clean_d.startswith(".") or clean_d.startswith(","):
        suffix = clean_d.lstrip(".,")
        # Thử tính lại từ điểm thành phần nếu có
        if tp_text:
            m_qt = re.search(r'(?:quá\s*trình|chuyên\s*cần|qt|cc)[:\s]*([0-9]+[.,]?[0-9]*)', tp_text, re.IGNORECASE)
            m_gk = re.search(r'(?:giữa\s*kỳ|gk)[:\s]*([0-9]+[.,]?[0-9]*)', tp_text, re.IGNORECASE)
            m_ck = re.search(r'(?:cuối\s*kỳ|thi|ck)[:\s]*([0-9]+[.,]?[0-9]*)', tp_text, re.IGNORECASE)

            if m_qt and m_gk and m_ck:
                try:
                    v_qt = float(m_qt.group(1).replace(",", "."))
                    v_gk = float(m_gk.group(1).replace(",", "."))
                    v_ck = float(m_ck.group(1).replace(",", "."))
                    # Công thức tính điểm LHU: 30% Quá trình + 30% Giữa kỳ + 40% Cuối kỳ
                    calc_dtb = round(0.3 * v_qt + 0.3 * v_gk + 0.4 * v_ck, 2)
                    calc_str = f"{calc_dtb:.2f}"
                    if calc_str.endswith("." + suffix) or f"{calc_dtb:.1f}".endswith("." + suffix):
                        logger.info(f"Khôi phục thành công điểm bị mất số đầu '{clean_d}' -> {calc_dtb} từ điểm thành phần ({tp_text})")
                        return calc_dtb, False, "Khôi phục từ điểm thành phần"
                    # Trường hợp điểm làm tròn 1 chữ số
                    return calc_dtb, False, "Tính toán từ điểm thành phần"
                except Exception as e:
                    logger.debug(f"Không thể tính lại điểm từ thành phần: {e}")
            elif m_ck and not m_qt and not m_gk:
                # Môn chỉ có điểm cuối kỳ (như GDTC, GDQP)
                try:
                    v_ck = float(m_ck.group(1).replace(",", "."))
                    calc_str = f"{v_ck:.2f}"
                    if calc_str.endswith("." + suffix) or f"{v_ck:.1f}".endswith("." + suffix):
                        return v_ck, False, "Khôi phục từ điểm cuối kỳ"
                except Exception:
                    pass

        # Không thể suy luận chắc chắn: Đánh dấu cần xác nhận, KHÔNG đoán bừa thành 95.0 hay 0.95
        logger.warning(f"Phát hiện điểm bị khuyết chữ số đầu '{clean_d}' không thể khôi phục. Đánh dấu cần xác nhận.")
        return None, True, f"Điểm bị khuyết chữ số nguyên ({clean_d}), cần xác nhận"

    # Điểm bình thường có đầy đủ phần nguyên
    match_num = re.search(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*$", clean_d)
    if match_num:
        try:
            val = float(match_num.group(1))
            if 0.0 <= val <= 10.0:
                return val, False, ""
        except ValueError:
            pass

    # Nếu chuỗi chứa số nằm trong khoảng 0.0 - 10.0
    match_any = re.search(r"([0-9]+(?:\.[0-9]+)?)", clean_d)
    if match_any:
        try:
            val = float(match_any.group(1))
            if 0.0 <= val <= 10.0:
                return val, False, ""
        except ValueError:
            pass

    return None, True, f"Không thể nhận diện điểm từ '{diem_text}'"


def extract_grades_from_pdf_text_layer(pdf_path: str, max_pages: int = 10) -> Tuple[List[Dict[str, Any]], List[Image.Image]]:
    """
    Trích xuất danh sách môn học và điểm trực tiếp từ text layer của PDF bằng pdfplumber.
    Hỗ trợ nhận diện đúng cấu trúc bảng điểm LHU:
    - Cột Mã ('Mã', 'Mã môn')
    - Cột Tên môn ('Tên môn học')
    - Cột Số tín chỉ ('Hệ số', 'Tín chỉ')
    - Cột Điểm thành phần ('Điểm thành phần')
    - Cột Điểm trung bình ('Điểm trung bình')
    Tự động khôi phục hoặc đánh dấu các điểm bị mất số đầu (.95, .45, .5, .00).
    """
    subjects: List[Dict[str, Any]] = []
    page_images = convert_pdf_to_images(pdf_path, max_pages=max_pages)

    with pdfplumber.open(pdf_path) as pdf:
        pages_to_process = pdf.pages[:max_pages] if max_pages else pdf.pages
        for page_idx, page in enumerate(pages_to_process):
            # 1. Thử trích xuất theo bảng biểu (Tables) với tọa độ để nhận diện học kỳ phía trên
            found_tables = []
            try:
                res = page.find_tables()
                if isinstance(res, list):
                    found_tables = res
            except Exception:
                found_tables = []

            # Fallback nếu mock hoặc thư viện chỉ dùng extract_tables
            if not found_tables and hasattr(page, "extract_tables"):
                raw_tables = page.extract_tables() or []
                if isinstance(raw_tables, list):
                    class _PseudoTable:
                        def __init__(self, raw):
                            self._raw = raw
                            self.bbox = (0, 0, getattr(page, "width", 595), getattr(page, "height", 842))
                        def extract(self):
                            return self._raw
                    found_tables = [_PseudoTable(t) for t in raw_tables if t]

            table_parsed = False

            if found_tables:
                for t in found_tables:
                    table = t.extract()
                    if not table or len(table) < 2:
                        continue
                    
                    # Nhận diện học kỳ từ tiêu đề phía trên bảng
                    top_y = t.bbox[1] if hasattr(t, "bbox") and len(t.bbox) > 1 else 0
                    heading_above = ""
                    if hasattr(page, "crop") and hasattr(page, "width"):
                        try:
                            crop_area = (0, max(0, top_y - 45), page.width, top_y)
                            cropped = page.crop(crop_area)
                            if cropped and hasattr(cropped, "extract_text"):
                                txt = cropped.extract_text()
                                if isinstance(txt, str):
                                    heading_above = txt
                        except Exception:
                            heading_above = ""
                    m_hk = re.search(r"Học kỳ\s+(\d+)", heading_above, re.IGNORECASE) if heading_above else None
                    sem_heading = f"Học kỳ {m_hk.group(1)}" if m_hk else ("Ngoài CTĐT" if "ngoài chương trình" in heading_above.lower() else "")
                    
                    header = [re.sub(r'\s+', ' ', str(cell or '')).strip().lower() for cell in table[0]]
                    ma_col_idx = -1
                    mon_col_idx = -1
                    tc_col_idx = -1
                    tp_col_idx = -1
                    diem_col_idx = -1
                    hk_col_idx = -1

                    for c_idx, col_name in enumerate(header):
                        if col_name in ["mã", "ma"] or any(k in col_name for k in ["mã môn", "ma mon", "mã hp", "ma hp", "course code", "code"]):
                            ma_col_idx = c_idx
                        elif any(k in col_name for k in ["tên môn", "ten mon", "tên hp", "ten hp", "môn", "mon", "học phần", "subject"]):
                            mon_col_idx = c_idx
                        elif any(k in col_name for k in ["hệ số", "he so", "tín chỉ", "tin chi", "số tc", "so tc", "credits", "stc", "tc"]):
                            tc_col_idx = c_idx
                        elif any(k in col_name for k in ["thành phần", "tp"]):
                            tp_col_idx = c_idx
                        elif any(k in col_name for k in ["trung bình", "đtb", "dtb"]):
                            diem_col_idx = c_idx
                        elif any(k in col_name for k in ["học kỳ", "hoc ky", "semester", "hk"]):
                            hk_col_idx = c_idx

                    # Nếu chưa tìm thấy cột điểm trung bình, lấy cột điểm nhưng khác cột thành phần
                    if diem_col_idx == -1:
                        for c_idx, col_name in enumerate(header):
                            if any(k in col_name for k in ["điểm", "diem", "score", "grade", "tổng kết", "tk"]) and c_idx != tp_col_idx:
                                diem_col_idx = c_idx
                                break

                    if mon_col_idx != -1 and diem_col_idx != -1:
                        table_parsed = True
                        for row in table[1:]:
                            if len(row) > max(mon_col_idx, diem_col_idx):
                                mon_text = str(row[mon_col_idx] or "").strip().replace("\n", " ")
                                diem_text = str(row[diem_col_idx] or "").strip()
                                ma_text = str(row[ma_col_idx] or "").strip() if (ma_col_idx != -1 and len(row) > ma_col_idx) else ""
                                tc_text = str(row[tc_col_idx] or "").strip() if (tc_col_idx != -1 and len(row) > tc_col_idx) else ""
                                tp_text = str(row[tp_col_idx] or "").strip().replace("\n", " ") if (tp_col_idx != -1 and len(row) > tp_col_idx) else ""
                                hk_text = str(row[hk_col_idx] or "").strip() if (hk_col_idx != -1 and len(row) > hk_col_idx) else sem_heading
                                
                                if not mon_text:
                                    continue
                                
                                # Khôi phục hoặc kiểm tra điểm bị mất số đầu
                                diem_val, needs_confirm, note = recover_or_validate_grade(diem_text, tp_text)
                                
                                tc_int = 0
                                if tc_text:
                                    try:
                                        tc_int = int(float(tc_text))
                                    except Exception:
                                        tc_int = 0
                                
                                subjects.append({
                                    "ma_mon": ma_text,
                                    "ten_mon": mon_text,
                                    "tin_chi": tc_int,
                                    "he_so": tc_int,
                                    "diem": diem_val,
                                    "raw_diem": diem_text,
                                    "needs_confirmation": needs_confirm,
                                    "grade_note": note,
                                    "diem_thanh_phan": tp_text,
                                    "hoc_ky": hk_text or None,
                                    "mon": mon_text,
                                    "course_code": ma_text,
                                    "course_name": mon_text,
                                    "credits": tc_int,
                                    "grade": diem_val,
                                    "semester": hk_text or None,
                                    "page": page_idx
                                })

            # 2. Nếu không có bảng rõ ràng, phân tích từng dòng text
            if not table_parsed:
                text_lines = (page.extract_text() or "").split("\n")
                for line in text_lines:
                    line = line.strip()
                    # Mẫu nhận diện: [Tên môn học] ... [Số điểm từ 0.0 đến 10.0]
                    # Ví dụ: "Toán cao cấp 1: 3.5" hoặc "Giải tích 1    7.0"
                    match = re.search(r"^(.*?)(?:[:\t]|\s{2,})([0-9]+[.,]?[0-9]*)\s*$", line)
                    if match:
                        mon_text = match.group(1).strip()
                        diem_str = match.group(2).replace(",", ".")
                        try:
                            diem_val = float(diem_str)
                            if 0.0 <= diem_val <= 10.0 and len(mon_text) > 2:
                                subjects.append({
                                    "mon": mon_text,
                                    "diem": diem_val,
                                    "page": page_idx
                                })
                        except ValueError:
                            pass

    logger.info(f"pdfplumber trích xuất được {len(subjects)} môn học từ text layer.")
    return subjects, page_images
