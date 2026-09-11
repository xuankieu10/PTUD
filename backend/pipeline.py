"""
Module điều phối toàn bộ Pipeline:
1. Tiếp nhận file ảnh hoặc PDF
2. Xử lý rẽ nhánh PDF (pdfplumber text layer vs pdf2image scan)
3. Nhận diện vùng đỏ bằng OpenCV (HSV)
4. Trích xuất môn & điểm qua Ollama Vision
5. Lọc môn không đạt bằng logic Python thuần
6. Xuất báo cáo JSON, CSV và sinh ảnh trực quan hóa
"""

import logging
import os
import shutil
from typing import Dict, Any, List, Optional
import cv2
import numpy as np
from PIL import Image

from backend.red_detector import (
    detect_red_regions,
    is_marked_red,
    annotate_red_regions,
    load_image
)
from backend.ocr_extractor import (
    extract_grades_from_image,
    DEFAULT_VISION_MODEL,
    DEFAULT_OLLAMA_HOST
)
from backend.pdf_processor import (
    has_text_layer,
    convert_pdf_to_images,
    extract_grades_from_pdf_text_layer
)
from backend.grade_filter import (
    filter_grades,
    export_to_json,
    export_to_csv
)

logger = logging.getLogger(__name__)


import requests

def resolve_model(requested_model: str, host: str) -> str:
    """
    Kiểm tra xem mô hình được yêu cầu có sẵn trong Ollama chưa.
    Nếu chưa, tự động chuyển sang mô hình vision có sẵn (ví dụ: qwen2.5vl:7b) thay vì báo lỗi 404.
    """
    try:
        res = requests.get(f"{host.rstrip('/')}/api/tags", timeout=3)
        if res.status_code == 200:
            models_data = res.json().get("models", [])
            installed = [m.get("name", "") for m in models_data if "name" in m]
            if any(requested_model in m for m in installed):
                return requested_model
            # Tìm model vision thay thế có sẵn
            vision_models = [m for m in installed if any(k in m.lower() for k in ["vision", "vl"])]
            if vision_models:
                fallback = vision_models[0]
                logger.warning(
                    f"Mô hình '{requested_model}' chưa có trong Ollama. "
                    f"Tự động sử dụng mô hình vision sẵn có trên máy: '{fallback}'."
                )
                return fallback
    except Exception as e:
        logger.debug(f"Không thể kiểm tra tags Ollama: {e}")
    return requested_model


def estimate_subject_bboxes(
    image_shape: tuple,
    num_subjects: int,
    header_ratio: float = 0.08,
    footer_ratio: float = 0.02
) -> List[tuple]:
    """
    Ước lượng bounding box cho từng dòng môn học khi model OCR không trả về tọa độ pixel.
    Dựa trên cấu trúc bảng điểm xếp dọc từ trên xuống dưới.
    """
    if num_subjects <= 0:
        return []

    h, w = image_shape[:2]
    table_top = int(h * header_ratio)
    table_bottom = int(h * (1.0 - footer_ratio))
    available_h = max(table_bottom - table_top, 100)
    row_height = available_h / num_subjects

    bboxes = []
    for i in range(num_subjects):
        y1 = int(table_top + i * row_height)
        y2 = int(table_top + (i + 1) * row_height)
        bboxes.append((0, y1, w, y2))
    return bboxes


def run_pipeline(
    input_path: str,
    output_dir: str = "output",
    model: str = DEFAULT_VISION_MODEL,
    host: str = DEFAULT_OLLAMA_HOST
) -> Dict[str, Any]:
    """
    Thực thi toàn bộ pipeline xử lý bảng điểm.
    
    Args:
        input_path: Đường dẫn tới file ảnh (jpg, png) hoặc PDF.
        output_dir: Thư mục lưu kết quả JSON, CSV và ảnh annotated.
        model: Tên model Ollama Vision (llama3.2-vision).
        host: Địa chỉ Ollama server (http://localhost:11434).
        
    Returns:
        Dictionary chứa thống kê, danh sách môn không đạt, toàn bộ môn và đường dẫn file kết quả.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Không tìm thấy file đầu vào: {input_path}")

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    ext = os.path.splitext(input_path)[1].lower()

    # Tự động giải quyết model phù hợp với Ollama hiện tại
    model = resolve_model(model, host)

    logger.info(f"=== BẮT ĐẦU PIPELINE XỬ LÝ: {input_path} (Model: {model}) ===")

    all_extracted_subjects: List[Dict[str, Any]] = []
    all_red_regions: List[tuple] = []
    processed_images: List[np.ndarray] = []

    # 1. Rẽ nhánh theo loại file (PDF vs Ảnh)
    if ext == ".pdf":
        logger.info("Phát hiện định dạng PDF. Đang kiểm tra lớp văn bản (text layer)...")
        if has_text_layer(input_path):
            logger.info("-> PDF có text layer: Sử dụng pdfplumber trích xuất trực tiếp.")
            pdf_subjects, pil_pages = extract_grades_from_pdf_text_layer(input_path)
            all_extracted_subjects.extend(pdf_subjects)

            # Vẫn chạy OpenCV nhận diện màu đỏ trên từng trang PDF kết xuất
            for p_idx, pil_img in enumerate(pil_pages):
                cv_img = load_image(pil_img)
                processed_images.append(cv_img)
                red_boxes = detect_red_regions(cv_img)
                all_red_regions.extend(red_boxes)
        else:
            logger.info("-> PDF scan không có text layer: Chuyển đổi các trang sang ảnh và dùng Ollama Vision.")
            pil_pages = convert_pdf_to_images(input_path)
            for p_idx, pil_img in enumerate(pil_pages):
                cv_img = load_image(pil_img)
                processed_images.append(cv_img)
                red_boxes = detect_red_regions(cv_img)
                all_red_regions.extend(red_boxes)

                page_subjects = extract_grades_from_image(pil_img, model=model, host=host)
                # Gán ước tính bbox theo dòng nếu chưa có
                if page_subjects and "bbox" not in page_subjects[0]:
                    est_boxes = estimate_subject_bboxes(cv_img.shape, len(page_subjects))
                    for s, b in zip(page_subjects, est_boxes):
                        s["bbox"] = b
                all_extracted_subjects.extend(page_subjects)
    else:
        # Ảnh trực tiếp (JPG, PNG, ...)
        logger.info("Phát hiện định dạng ảnh. Đang tiến hành đọc ảnh và phân tích...")
        cv_img = load_image(input_path)
        processed_images.append(cv_img)

        # A. Nhận diện màu đỏ bằng OpenCV
        red_boxes = detect_red_regions(cv_img)
        all_red_regions.extend(red_boxes)

        # B. Trích xuất môn & điểm qua Ollama Vision
        subjects = extract_grades_from_image(cv_img, model=model, host=host)
        
        # Nếu model chưa trả về bbox, ước lượng bounding box dòng tương ứng
        if subjects and "bbox" not in subjects[0]:
            est_boxes = estimate_subject_bboxes(cv_img.shape, len(subjects))
            for s, b in zip(subjects, est_boxes):
                s["bbox"] = b
        all_extracted_subjects.extend(subjects)

    # 2. Áp dụng Logic Lọc Môn Không Đạt (Thuần Python)
    logger.info("Đang áp dụng logic kiểm tra môn không đạt (Điểm < 4.0 HOẶC Vùng đỏ)...")
    failed_subjects, all_evaluated = filter_grades(all_extracted_subjects, all_red_regions)

    # 3. Xuất file kết quả JSON và CSV
    json_path = os.path.join(output_dir, f"{base_name}_failed.json")
    csv_path = os.path.join(output_dir, f"{base_name}_failed.csv")
    export_to_json(failed_subjects, json_path)
    export_to_csv(failed_subjects, csv_path)

    # 4. Sinh ảnh trực quan hóa với bounding box vùng đỏ
    annotated_img_path = os.path.join(output_dir, f"{base_name}_annotated.png")
    if processed_images:
        flagged_boxes = [s["bbox"] for s in failed_subjects if "bbox" in s]
        annotate_red_regions(
            processed_images[0],
            all_red_regions,
            flagged_bboxes=flagged_boxes,
            output_path=annotated_img_path
        )

    summary = {
        "input_file": input_path,
        "total_subjects": len(all_evaluated),
        "failed_count": len(failed_subjects),
        "passed_count": len(all_evaluated) - len(failed_subjects),
        "red_regions_count": len(all_red_regions),
        "failed_subjects": failed_subjects,
        "all_subjects": all_evaluated,
        "json_path": json_path,
        "csv_path": csv_path,
        "annotated_image_path": annotated_img_path
    }

    logger.info(
        f"=== HOÀN TẤT PIPELINE ===\n"
        f"Tổng số môn: {summary['total_subjects']} | Không đạt: {summary['failed_count']} | Đạt: {summary['passed_count']}\n"
        f"File JSON: {json_path}\n"
        f"File CSV:  {csv_path}\n"
        f"Ảnh đánh dấu: {annotated_img_path}"
    )

    return summary
