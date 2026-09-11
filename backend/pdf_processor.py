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


def convert_pdf_to_images(pdf_path: str, dpi: int = 200) -> List[Image.Image]:
    """
    Chuyển đổi từng trang của file PDF sang ảnh (PIL Image).
    Ưu tiên sử dụng pdf2image theo yêu cầu bài toán.
    Tự động fallback sang pypdfium2 nếu Windows chưa cài đặt Poppler.
    """
    logger.info(f"Đang chuyển đổi PDF sang ảnh (DPI: {dpi})...")
    
    # 1. Thử dùng pdf2image theo yêu cầu
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=dpi)
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
        for page_idx in range(len(pdf)):
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


def extract_grades_from_pdf_text_layer(pdf_path: str) -> Tuple[List[Dict[str, Any]], List[Image.Image]]:
    """
    Trích xuất danh sách môn học và điểm trực tiếp từ text layer của PDF bằng pdfplumber.
    Đồng thời kết xuất ảnh của từng trang để phục vụ việc nhận diện màu đỏ (OpenCV).
    
    Returns:
        Tuple gồm (danh sách môn kèm điểm và bbox, danh sách ảnh các trang tương ứng).
    """
    subjects: List[Dict[str, Any]] = []
    page_images = convert_pdf_to_images(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            # 1. Thử trích xuất theo bảng biểu (Tables)
            tables = page.extract_tables()
            table_parsed = False

            if tables:
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    
                    header = [str(cell).strip().lower() if cell else "" for cell in table[0]]
                    mon_col_idx = -1
                    diem_col_idx = -1

                    for c_idx, col_name in enumerate(header):
                        if any(k in col_name for k in ["môn", "mon", "học phần", "tên môn", "subject", "khoản"]):
                            mon_col_idx = c_idx
                        elif any(k in col_name for k in ["điểm", "diem", "score", "grade", "tổng kết", "tk"]):
                            diem_col_idx = c_idx

                    if mon_col_idx != -1 and diem_col_idx != -1:
                        table_parsed = True
                        for row in table[1:]:
                            if len(row) > max(mon_col_idx, diem_col_idx):
                                mon_text = str(row[mon_col_idx] or "").strip()
                                diem_text = str(row[diem_col_idx] or "").strip()
                                
                                if not mon_text:
                                    continue
                                
                                match_num = re.search(r"\d+(\.\d+)?", diem_text.replace(",", "."))
                                if match_num:
                                    diem_val = float(match_num.group(0))
                                    subjects.append({
                                        "mon": mon_text,
                                        "diem": diem_val,
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
