"""
Module tương tác với Ollama Vision API (mặc định model llama3.2-vision tại http://localhost:11434).
Bao gồm:
- Mã hóa ảnh sang Base64
- Gửi prompt yêu cầu model trả về JSON: [{"mon": string, "diem": number}]
- Parser kiểm tra và trích xuất JSON chịu lỗi
- Cơ chế retry 1 lần với prompt nhấn mạnh hơn nếu kết quả trả về sai định dạng
"""

import base64
import io
import json
import logging
import os
import re
from typing import List, Dict, Any, Union, Optional
import requests
from PIL import Image
import numpy as np
import cv2

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_VISION_MODEL = "llama3.2-vision"

DEFAULT_TIMEOUT = 300

PRIMARY_PROMPT = (
    "Bạn là trợ lý AI chuyên đọc bảng điểm học sinh / sinh viên từ ảnh.\n"
    "Trong ảnh là bảng điểm gồm nhiều dòng môn học xếp từ trên xuống dưới.\n"
    "Nhiệm vụ: Duyệt TẤT CẢ các dòng trong bảng từ trên xuống dưới và trích xuất TOÀN BỘ các môn học có trong bảng:\n"
    "- Tên môn học: lấy ở cột 'Tên môn học' (bỏ qua mã số môn).\n"
    "- Điểm số: lấy điểm tổng kết ở cột 'Điểm trung bình' (hoặc cột điểm thành phần cuối cùng bên phải).\n"
    "Yêu cầu định dạng đầu ra: một đối tượng JSON có key 'danh_sach' chứa mảng toàn bộ các môn học:\n"
    '{\n'
    '  "danh_sach": [\n'
    '    {"mon": "Tên môn 1", "diem": 8.6},\n'
    '    {"mon": "Tên môn 2", "diem": 8.9}\n'
    '  ]\n'
    '}\n'
    "chỉ trả JSON, không thêm giải thích."
)

RETRY_PROMPT = (
    "LỖI: Bạn cần trích xuất ĐẦY ĐỦ TẤT CẢ các dòng môn học trong bảng từ trên xuống dưới. "
    "Trả về định dạng JSON object: "
    '{"danh_sach": [{"mon": "Tên môn 1", "diem": 8.6}, {"mon": "Tên môn 2", "diem": 8.9}, ...]}. '
    "chỉ trả JSON, không thêm giải thích."
)


def optimize_image_for_vision(img: Image.Image, max_dim: int = 1024) -> Image.Image:
    """
    Thu nhỏ ảnh nếu quá lớn để tăng tốc độ suy luận của mô hình Vision trên CPU/GPU.
    Mức 1024px đảm bảo giữ nguyên độ sắc nét của bảng nhiều dòng.
    """
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return img


def encode_image_to_base64(image_input: Union[str, Image.Image, np.ndarray], max_dim: int = 1024) -> str:
    """
    Chuyển đổi file ảnh, đối tượng PIL Image hoặc numpy BGR array sang chuỗi base64.
    """
    if isinstance(image_input, str):
        with Image.open(image_input) as pil_img:
            optimized = optimize_image_for_vision(pil_img.convert("RGB"), max_dim=max_dim)
            buffer = io.BytesIO()
            optimized.save(buffer, format="JPEG", quality=85)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    elif isinstance(image_input, Image.Image):
        optimized = optimize_image_for_vision(image_input.convert("RGB"), max_dim=max_dim)
        buffer = io.BytesIO()
        optimized.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    elif isinstance(image_input, np.ndarray):
        rgb = cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        optimized = optimize_image_for_vision(pil_img, max_dim=max_dim)
        buffer = io.BytesIO()
        optimized.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    else:
        raise ValueError(f"Đầu vào ảnh không hợp lệ: {type(image_input)}")


def clean_and_parse_json(raw_response: str) -> List[Dict[str, Any]]:
    """
    Phân tích chuỗi JSON trả về từ mô hình ngôn ngữ thị giác.
    Xử lý các tình huống:
    - Mảng JSON [...]
    - Đối tượng đơn lẻ {...} (khi bảng điểm chỉ có 1 môn hoặc model trả về 1 object)
    - Đối tượng bọc ngoài {"data": [...]} hoặc {"subjects": [...]}
    - Bọc trong markdown ```json ... ```
    - Có ký tự thừa hoặc dấu chấm hỏi ở cuối (ví dụ: ... }?)
    - Dùng key tương đương ('ten_mon', 'subject', 'score', 'diem_so')
    - Định dạng điểm số dạng chuỗi hoặc số thập phân có dấu phẩy ('7,5')
    """
    text = raw_response.strip()

    # 1. Loại bỏ các khối code block ```json ... ``` hoặc ``` ... ```
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if code_block_match:
        text = code_block_match.group(1).strip()

    # 2. Tìm mảng JSON [...] trong văn bản
    json_array_match = re.search(r"\[\s*\{[\s\S]*?\}\s*\]", text)
    if json_array_match:
        try:
            parsed = json.loads(json_array_match.group(0))
            if isinstance(parsed, list):
                return _normalize_subject_list(parsed)
        except Exception:
            pass

    # 3. Tìm đối tượng JSON {...} trong văn bản (kể cả khi model trả về 1 môn hoặc object bọc ngoài)
    json_obj_match = re.search(r"\{[\s\S]*\}", text)
    if json_obj_match:
        try:
            obj = json.loads(json_obj_match.group(0))
            # Trường hợp 3a: Model trả về 1 môn duy nhất: {"mon": ..., "diem": ...}
            if any(k in obj for k in ["mon", "mon_hoc", "ten_mon", "subject", "diem", "score", "grade"]):
                return _normalize_subject_list([obj])

            # Trường hợp 3b: Model trả về {"subjects": [...]} hoặc {"data": [...]}
            for v in obj.values():
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    return _normalize_subject_list(v)
                elif isinstance(v, dict) and any(k in v for k in ["mon", "mon_hoc", "ten_mon", "subject"]):
                    return _normalize_subject_list([v])
        except Exception:
            pass

    # 4. Thử parse trực tiếp sau khi cắt bỏ ký tự thừa ở đầu và cuối (ví dụ dấu '?' hoặc text giải thích)
    clean_text = re.sub(r"^[^{\[]+", "", text)
    clean_text = re.sub(r"[^}\]]+$", "", clean_text)
    if clean_text:
        parsed = json.loads(clean_text)
        if isinstance(parsed, list):
            return _normalize_subject_list(parsed)
        elif isinstance(parsed, dict):
            return _normalize_subject_list([parsed])

    raise ValueError(f"Dữ liệu trả về không thể phân tích thành danh sách môn học: {raw_response}")


def _normalize_subject_list(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Chuẩn hóa các khóa và kiểu dữ liệu về dạng: {"mon": str, "diem": float}
    """
    normalized = []
    for idx, item in enumerate(raw_list):
        if not isinstance(item, dict):
            continue

        # Tìm tên môn
        mon = (
            item.get("mon")
            or item.get("mon_hoc")
            or item.get("ten_mon")
            or item.get("subject")
            or item.get("name")
        )
        # Tìm điểm số
        diem_val = (
            item.get("diem")
            if "diem" in item
            else (
                item.get("score")
                or item.get("diem_so")
                or item.get("grade")
                or item.get("mark")
            )
        )

        if mon is None or diem_val is None:
            continue

        mon_str = str(mon).strip()

        # Chuyển đổi điểm số sang float
        try:
            if isinstance(diem_val, (int, float)):
                diem_float = float(diem_val)
            else:
                # Xử lý chuỗi điểm có dấu phẩy '7,5' hoặc ký hiệu
                clean_str = str(diem_val).replace(",", ".").strip()
                # Tìm số thực đầu tiên trong chuỗi
                match_num = re.search(r"\d+(\.\d+)?", clean_str)
                if match_num:
                    diem_float = float(match_num.group(0))
                else:
                    logger.warning(f"Không thể trích xuất điểm số từ: '{diem_val}', gán mặc định 0.0")
                    diem_float = 0.0
        except Exception as e:
            logger.warning(f"Lỗi ép kiểu điểm số '{diem_val}': {e}. Gán mặc định 0.0")
            diem_float = 0.0

        item_dict: Dict[str, Any] = {
            "mon": mon_str,
            "diem": round(diem_float, 2)
        }

        # Nếu model có trả về bounding box (tùy chọn)
        if "bbox" in item:
            item_dict["bbox"] = item["bbox"]

        normalized.append(item_dict)

    if not normalized:
        raise ValueError("Không tìm thấy môn học hợp lệ nào trong kết quả JSON.")

    return normalized


def query_ollama(
    prompt: str,
    image_base64: str,
    model: str = DEFAULT_VISION_MODEL,
    host: str = DEFAULT_OLLAMA_HOST,
    timeout: int = DEFAULT_TIMEOUT
) -> str:
    """
    Gửi request tới API Ollama `/api/generate`.
    """
    url = f"{host.rstrip('/')}/api/generate"
    cpu_cores = os.cpu_count() or 4
    num_threads = max(1, cpu_cores - 2)

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
        "format": "json",  # Bật chế độ ép JSON của Ollama
        "options": {
            "num_thread": num_threads,
            "num_predict": 1500,
            "temperature": 0.1
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code == 404:
            try:
                err_detail = response.json().get("error", response.text)
            except Exception:
                err_detail = response.text
            raise FileNotFoundError(
                f"Mô hình '{model}' chưa được tải về Ollama ({err_detail}). "
                f"Vui lòng mở terminal chạy lệnh: 'ollama pull {model}' hoặc chọn mô hình đã có sẵn trên máy (ví dụ: qwen2.5vl:7b)."
            )
        response.raise_for_status()
        res_json = response.json()
        return res_json.get("response", "")
    except FileNotFoundError:
        raise
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"Không thể kết nối tới Ollama tại '{host}'. "
            "Vui lòng kiểm tra xem Ollama đã được khởi chạy chưa (ollama serve)."
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Hết thời gian chờ phản hồi từ Ollama ({timeout}s).")
    except Exception as e:
        raise RuntimeError(f"Lỗi khi gọi Ollama API: {e}")


def extract_grades_from_image(
    image_input: Union[str, Image.Image, np.ndarray],
    model: str = DEFAULT_VISION_MODEL,
    host: str = DEFAULT_OLLAMA_HOST,
    max_retries: int = 1,
    timeout: int = DEFAULT_TIMEOUT
) -> List[Dict[str, Any]]:
    """
    Thực hiện trích xuất môn học và điểm số từ ảnh:
    1. Gửi request lần 1 với prompt chuẩn.
    2. Parse JSON. Nếu lỗi, ghi log cảnh báo và retry 1 lần với prompt nhấn mạnh hơn.
    """
    image_b64 = encode_image_to_base64(image_input)

    logger.info(f"Đang gửi ảnh tới Ollama Vision (Model: {model}, Host: {host})...")
    raw_response = query_ollama(PRIMARY_PROMPT, image_b64, model=model, host=host, timeout=timeout)

    try:
        parsed_result = clean_and_parse_json(raw_response)
        logger.info(f"Lần 1: Trích xuất được {len(parsed_result)} môn học.")

        # Nếu model chỉ đọc 1 dòng đầu tiên trong khi bảng có nhiều dòng, kích hoạt retry bổ sung
        if len(parsed_result) <= 1 and max_retries > 0:
            logger.warning("Mô hình mới chỉ trả về 1 dòng môn học. Đang yêu cầu quét tiếp toàn bộ các dòng bên dưới...")
            retry_multi_prompt = (
                "CẢNH BÁO: Bạn mới chỉ lấy 1 dòng đầu tiên! "
                "Trong ảnh là bảng điểm đầy đủ gồm NHIỀU DÒNG từ trên xuống dưới. "
                "Hãy trích xuất TẤT CẢ các dòng môn học trong bảng thành một mảng JSON đầy đủ: "
                '[{"mon": "...", "diem": ...}, {"mon": "...", "diem": ...}, ...]. '
                "chỉ trả JSON, không thêm giải thích."
            )
            retry_response = query_ollama(retry_multi_prompt, image_b64, model=model, host=host, timeout=timeout)
            try:
                second_result = clean_and_parse_json(retry_response)
                if len(second_result) > len(parsed_result):
                    logger.info(f"Quét lại thành công: tìm thấy {len(second_result)} môn học.")
                    return second_result
            except Exception as e:
                logger.warning(f"Lỗi khi quét lại nhiều dòng: {e}")

        return parsed_result
    except Exception as parse_error:
        logger.warning(
            f"Lần 1: Model trả về sai định dạng JSON. Lỗi: {parse_error}. "
            f"Nội dung phản hồi thô: {raw_response[:200]}..."
        )

        if max_retries > 0:
            logger.info("Tiến hành RETRY 1 lần với prompt nhấn mạnh yêu cầu JSON thuần túy...")
            retry_response = query_ollama(RETRY_PROMPT, image_b64, model=model, host=host, timeout=timeout)
            try:
                parsed_result = clean_and_parse_json(retry_response)
                logger.info(f"Retry thành công! Trích xuất được {len(parsed_result)} môn học.")
                return parsed_result
            except Exception as retry_error:
                logger.error(f"Retry thất bại. Model vẫn không trả về JSON hợp lệ: {retry_error}")
                raise ValueError(
                    f"Không thể phân tích kết quả JSON từ mô hình {model} sau khi retry. "
                    f"Phản hồi: {retry_response}"
                )

        raise parse_error
