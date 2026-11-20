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

from backend.app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_VISION_MODEL = getattr(settings, "VLM_MODEL", getattr(settings, "OLLAMA_VISION_MODEL", "qwen2.5vl:7b"))
DEFAULT_IMAGE_DIM = getattr(settings, "MAX_IMAGE_DIM", 1280)

DEFAULT_TIMEOUT = getattr(settings, "OCR_TIMEOUT_SECONDS", getattr(settings, "OLLAMA_TIMEOUT_OCR", 300))

PRIMARY_PROMPT = (
    "Bạn là trợ lý AI chuyên đọc bảng điểm học sinh / sinh viên từ ảnh.\n"
    "Trong ảnh là bảng điểm gồm nhiều dòng môn học xếp từ trên xuống dưới.\n"
    "Nhiệm vụ: Duyệt TẤT CẢ các dòng trong bảng từ trên xuống dưới và trích xuất TOÀN BỘ các môn học có trong bảng:\n"
    "- Mã môn học: cột 'Mã môn' hoặc 'Mã HP' (nếu có, không có thì để chuỗi rỗng '').\n"
    "- Tên môn học: cột 'Tên môn học' hoặc 'Tên học phần'.\n"
    "- Số tín chỉ: cột 'Số TC' hoặc 'Tín chỉ' (số nguyên, nếu không có để null).\n"
    "- Điểm số: lấy điểm tổng kết ở cột 'Điểm TB' / 'Điểm TK' / 'Điểm chữ' hoặc cột điểm cuối cùng.\n"
    "- Học kỳ: cột 'Học kỳ' (nếu có, ví dụ 1, 2, 'HK1', không có để null).\n"
    "Yêu cầu định dạng đầu ra: một đối tượng JSON có key 'danh_sach' chứa mảng toàn bộ các môn học:\n"
    '{\n'
    '  "danh_sach": [\n'
    '    {"ma_mon": "102073", "ten_mon": "Toán cao cấp 1", "tin_chi": 4, "diem": 8.5, "hoc_ky": 1},\n'
    '    {"ma_mon": "111094", "ten_mon": "Nhập môn lập trình", "tin_chi": 2, "diem": 3.5, "hoc_ky": 1}\n'
    '  ]\n'
    '}\n'
    "chỉ trả JSON, không thêm giải thích."
)

RETRY_PROMPT = (
    "LỖI: Bạn cần trích xuất ĐẦY ĐỦ TẤT CẢ các dòng môn học trong bảng từ trên xuống dưới. "
    "Trả về định dạng JSON object: "
    '{"danh_sach": [{"ma_mon": "...", "ten_mon": "...", "tin_chi": 3, "diem": 8.0, "hoc_ky": 1}, ...]}. '
    "chỉ trả JSON, không thêm giải thích."
)


def unload_model(model_name: str, host: str = DEFAULT_OLLAMA_HOST):
    """
    Giải phóng mô hình khỏi VRAM ngay lập tức bằng cách gọi keep_alive=0 tới Ollama.
    Tối ưu cho máy chỉ có 4GB VRAM để nạp tuần tự 1 model duy nhất.
    """
    try:
        url = f"{host.rstrip('/')}/api/generate"
        requests.post(url, json={"model": model_name, "keep_alive": 0}, timeout=5)
        logger.info(f"Đã giải phóng VRAM mô hình '{model_name}'.")
    except Exception as e:
        logger.warning(f"Không thể giải phóng mô hình '{model_name}': {e}")


def optimize_image_for_vision(img: Image.Image, max_dim: int = DEFAULT_IMAGE_DIM) -> Image.Image:
    """
    Thu nhỏ ảnh nếu cạnh dài lớn hơn max_dim (mặc định <= 1280px) để tối ưu VRAM (4GB) và tăng tốc suy luận.
    """
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return img


def encode_image_to_base64(image_input: Union[str, Image.Image, np.ndarray], max_dim: int = DEFAULT_IMAGE_DIM) -> str:
    """
    Chuyển đổi file ảnh, đối tượng PIL Image hoặc numpy BGR array sang chuỗi base64.
    Đảm bảo kích thước ảnh luôn <= max_dim (1280px).
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
    Chuẩn hóa các khóa và kiểu dữ liệu về schema đầy đủ:
    {"ma_mon": str, "ten_mon": str, "tin_chi": int, "diem": float, "hoc_ky": Any, "mon": str}
    """
    normalized = []
    for idx, item in enumerate(raw_list):
        if not isinstance(item, dict):
            continue

        # Tìm tên môn
        mon = (
            item.get("ten_mon")
            or item.get("mon")
            or item.get("mon_hoc")
            or item.get("subject")
            or item.get("name")
        )
        # Tìm mã môn
        ma_mon = (
            item.get("ma_mon")
            or item.get("ma_hp")
            or item.get("course_code")
            or item.get("code")
            or ""
        )
        # Tìm tín chỉ
        tc_val = (
            item.get("tin_chi")
            or item.get("so_tc")
            or item.get("credits")
            or item.get("tc")
        )
        # Tìm học kỳ
        hk_val = (
            item.get("hoc_ky")
            or item.get("semester")
            or item.get("hk")
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
        ma_mon_str = str(ma_mon).strip() if ma_mon else ""

        # Parse tín chỉ
        tin_chi_int = None
        if tc_val is not None:
            try:
                tin_chi_int = int(float(str(tc_val).strip()))
            except Exception:
                tin_chi_int = None

        # Parse học kỳ
        hoc_ky_parsed = None
        if hk_val is not None:
            hk_s = str(hk_val).strip()
            m_hk = re.search(r"\d+", hk_s)
            hoc_ky_parsed = int(m_hk.group(0)) if m_hk else hk_s

        # Chuyển đổi điểm số sang float
        try:
            if isinstance(diem_val, (int, float)):
                diem_float = float(diem_val)
            else:
                clean_str = str(diem_val).replace(",", ".").strip()
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
            "ma_mon": ma_mon_str,
            "ten_mon": mon_str,
            "tin_chi": tin_chi_int,
            "diem": round(diem_float, 2),
            "hoc_ky": hoc_ky_parsed,
            # Dual-mapping tương thích ngược hoàn toàn
            "mon": mon_str,
            "course_code": ma_mon_str,
            "course_name": mon_str,
            "credits": tin_chi_int,
            "grade": round(diem_float, 2),
            "semester": hoc_ky_parsed
        }

        if "bbox" in item:
            item_dict["bbox"] = item["bbox"]

        normalized.append(item_dict)

    if not normalized:
        raise ValueError("Không tìm thấy môn học hợp lệ nào trong kết quả JSON.")

    return normalized


def resolve_vision_model(model_name: str, host: str = DEFAULT_OLLAMA_HOST) -> str:
    """Tự động chọn mô hình Vision khả dụng trong Ollama (ưu tiên model có sẵn theo cấu hình OLLAMA_VISION_MODEL)"""
    target = model_name or DEFAULT_VISION_MODEL
    try:
        r = requests.get(f"{host.rstrip('/')}/api/tags", timeout=2)
        if r.status_code == 200:
            installed = [m.get("name", "") for m in r.json().get("models", [])]
            if any(target in m for m in installed):
                return target
            for fallback in [DEFAULT_VISION_MODEL, "qwen2.5vl:7b", "qwen2.5vl:3b", "qwen2.5vl", "llava"]:
                for m in installed:
                    if fallback in m:
                        return m
    except Exception:
        pass
    return target


def query_ollama(
    prompt: str,
    image_base64: str,
    model: str = DEFAULT_VISION_MODEL,
    host: str = DEFAULT_OLLAMA_HOST,
    timeout: int = DEFAULT_TIMEOUT
) -> str:
    """
    Gửi request tới API Ollama `/api/generate`.
    Sử dụng VLM_KEEP_ALIVE ngắn để giải phóng VRAM ngay sau khi hoàn thành.
    """
    model = resolve_vision_model(model, host)
    url = f"{host.rstrip('/')}/api/generate"
    cpu_cores = os.cpu_count() or 4
    num_threads = max(1, cpu_cores - 2)

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
        "keep_alive": getattr(settings, "VLM_KEEP_ALIVE", "0s"),
        "format": "json",  # Bật chế độ ép JSON của Ollama
        "options": {
            "num_thread": num_threads,
            "num_predict": 1500,
            "temperature": 0.1,
            "num_ctx": getattr(settings, "NUM_CTX", 2048)
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
                f"Vui lòng mở terminal chạy lệnh: 'ollama pull {model}' hoặc chọn mô hình đã có sẵn trên máy (ví dụ: {DEFAULT_VISION_MODEL})."
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
        raise TimeoutError("Quá thời gian xử lý khi đọc bảng điểm. Hãy dùng ảnh rõ nét, dưới 2MB, hoặc chỉ gửi trang có bảng điểm.")
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
    actual_model = resolve_vision_model(model, host)
    logger.info(f"Đang gửi ảnh tới Ollama Vision (Model: {actual_model}, Host: {host})...")

    try:
        raw_response = query_ollama(PRIMARY_PROMPT, image_b64, model=actual_model, host=host, timeout=timeout)

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
                    '[{"ma_mon": "...", "ten_mon": "...", "tin_chi": 3, "diem": 8.0, "hoc_ky": 1}, ...]. '
                    "chỉ trả JSON, không thêm giải thích."
                )
                retry_response = query_ollama(retry_multi_prompt, image_b64, model=actual_model, host=host, timeout=timeout)
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
                retry_response = query_ollama(RETRY_PROMPT, image_b64, model=actual_model, host=host, timeout=timeout)
                try:
                    parsed_result = clean_and_parse_json(retry_response)
                    logger.info(f"Retry thành công! Trích xuất được {len(parsed_result)} môn học.")
                    return parsed_result
                except Exception as retry_error:
                    logger.error(f"Retry thất bại. Model vẫn không trả về JSON hợp lệ: {retry_error}")
                    raise ValueError(
                        f"Không thể phân tích kết quả JSON từ mô hình {actual_model} sau khi retry. "
                        f"Phản hồi: {retry_response}"
                    )

            raise parse_error
    finally:
        # Giải phóng VRAM của VLM model ngay lập tức để nhường bộ nhớ cho LLM
        unload_model(actual_model, host)
