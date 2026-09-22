"""
Module trích xuất thông tin chứng chỉ sinh viên từ ảnh bằng Ollama Vision API.
Bao gồm:
- Mã hóa ảnh sang Base64 và tối ưu kích thước
- Gửi prompt yêu cầu model trả về JSON:
  {
    "loai_chung_chi": "Ngoại ngữ | Tin học | Quốc phòng | Thể chất | Không xác định",
    "ten_chung_chi_cu_the": string,
    "ten_nguoi_duoc_cap": string hoặc null,
    "ngay_cap": string hoặc null,
    "do_tin_cay": "cao | trung binh | thap"
  }
- Parser kiểm tra và trích xuất JSON chịu lỗi
- Cơ chế retry 1 lần với prompt nhấn mạnh hơn nếu kết quả sai định dạng
"""

import json
import logging
import os
import re
from typing import Dict, Any, Optional, Union
import requests
from PIL import Image
import numpy as np

from backend.ocr_extractor import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_VISION_MODEL,
    DEFAULT_TIMEOUT,
    encode_image_to_base64,
)
from backend.pipeline import resolve_model

logger = logging.getLogger(__name__)

CERTIFICATE_PRIMARY_PROMPT = (
    "Bạn là chuyên gia nhận diện và kiểm định văn bằng, chứng chỉ sinh viên từ ảnh.\n"
    "Nhiệm vụ: Hãy phân tích kỹ bức ảnh và trích xuất các thông tin sau:\n"
    "1. loai_chung_chi: Hãy phân loại chứng chỉ vào ĐÚNG 1 trong 5 nhóm sau:\n"
    "   - 'Ngoại ngữ' (ví dụ: TOEIC, IELTS, TOEFL, VSTEP, Cambridge, chứng chỉ tiếng Anh, tiếng Nhật, tiếng Hàn, tiếng Trung...)\n"
    "   - 'Tin học' (ví dụ: MOS, IC3, CNTT, Ứng dụng CNTT cơ bản/nâng cao, tin học văn phòng, ICDL...)\n"
    "   - 'Quốc phòng' (ví dụ: Giáo dục quốc phòng và an ninh, GDQP, quân sự...)\n"
    "   - 'Thể chất' (ví dụ: Giáo dục thể chất, GDTC, thể dục thể thao, bơi lội...)\n"
    "   - 'Không xác định' (nếu là bằng lái xe, thẻ sinh viên, ảnh phong cảnh, giấy tờ khác hoặc ảnh quá mờ không đọc được)\n"
    "2. ten_chung_chi_cu_the: Tên chính xác in trên chứng chỉ (ví dụ: 'Chứng chỉ TOEIC', 'Chứng chỉ Ứng dụng CNTT cơ bản', 'Giấy chứng nhận GDQP & AN'...). Nếu không có thì ghi rõ.\n"
    "3. ten_nguoi_duoc_cap: Họ và tên người được cấp chứng chỉ (ví dụ: 'Nguyễn Văn A'). Nếu không thấy hãy để null.\n"
    "4. ngay_cap: Ngày cấp in trên chứng chỉ dạng DD/MM/YYYY hoặc chuỗi ngày tháng. Nếu không có để null.\n"
    "5. do_tin_cay: Đánh giá độ tin cậy của việc nhận diện:\n"
    "   - 'cao': Ảnh rõ nét, đầy đủ tiêu đề chứng chỉ, họ tên người được cấp rõ ràng.\n"
    "   - 'trung binh': Ảnh hơi mờ hoặc thiếu một vài thông tin như ngày cấp nhưng vẫn đọc được loại chứng chỉ.\n"
    "   - 'thap': Ảnh quá mờ, bị rách, chụp nghiêng nặng, mất nét hoặc không phải là chứng chỉ hợp lệ.\n\n"
    "Yêu cầu định dạng đầu ra: Trả về một đối tượng JSON ĐÚNG cấu trúc sau:\n"
    "{\n"
    '  "loai_chung_chi": "Ngoại ngữ | Tin học | Quốc phòng | Thể chất | Không xác định",\n'
    '  "ten_chung_chi_cu_the": "string",\n'
    '  "ten_nguoi_duoc_cap": "string hoặc null",\n'
    '  "ngay_cap": "string hoặc null",\n'
    '  "do_tin_cay": "cao | trung binh | thap"\n'
    "}\n"
    "chỉ trả JSON, không thêm giải thích."
)

CERTIFICATE_RETRY_PROMPT = (
    "LỖI: Kết quả trả về trước đó không đúng cấu trúc JSON yêu cầu. "
    "YÊU CẦU BẮT BUỘC: Bạn CHỈ ĐƯỢC PHÉP trả về một JSON Object thuần túy gồm 5 khóa:\n"
    "{\n"
    '  "loai_chung_chi": "Ngoại ngữ | Tin học | Quốc phòng | Thể chất | Không xác định",\n'
    '  "ten_chung_chi_cu_the": "string",\n'
    '  "ten_nguoi_duoc_cap": "string hoặc null",\n'
    '  "ngay_cap": "string hoặc null",\n'
    '  "do_tin_cay": "cao | trung binh | thap"\n'
    "}\n"
    "chỉ trả JSON, không thêm giải thích."
)

VALID_CATEGORIES = {"Ngoại ngữ", "Tin học", "Quốc phòng", "Thể chất", "Không xác định"}
VALID_CONFIDENCES = {"cao", "trung binh", "thap"}


def clean_and_parse_certificate_json(raw_response: str) -> Dict[str, Any]:
    """
    Phân tích và chuẩn hóa chuỗi JSON trích xuất chứng chỉ trả về từ mô hình Vision.
    Chịu lỗi markdown code blocks, dấu câu thừa, ký tự dính ở đuôi.
    """
    text = raw_response.strip()

    # 1. Bóc tách markdown ```json ... ```
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if code_block_match:
        text = code_block_match.group(1).strip()

    # 2. Tìm khối JSON Object {...}
    json_obj_match = re.search(r"\{[\s\S]*\}", text)
    if json_obj_match:
        candidate_text = json_obj_match.group(0).strip()
    else:
        candidate_text = text

    # Làm sạch ký tự lạ đầu và cuối
    candidate_text = re.sub(r"^[^{\[]+", "", candidate_text)
    candidate_text = re.sub(r"[^}\]]+$", "", candidate_text)

    try:
        parsed = json.loads(candidate_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Không thể giải mã JSON từ phản hồi mô hình: {e}. Nội dung thô: {raw_response[:200]}")

    if not isinstance(parsed, dict):
        # Nếu model trả về mảng chứa 1 dict
        if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
            parsed = parsed[0]
        else:
            raise ValueError(f"Kết quả không phải là JSON Object, nhận được: {type(parsed)}")

    # Chuẩn hóa các trường
    loai_chung_chi = str(
        parsed.get("loai_chung_chi")
        or parsed.get("loai")
        or parsed.get("category")
        or "Không xác định"
    ).strip()

    # Chuẩn hóa nếu model viết hoa hoặc dùng từ đồng nghĩa
    loai_norm = loai_chung_chi.title()
    matched_cat = "Không xác định"
    for valid_cat in VALID_CATEGORIES:
        if valid_cat.lower() == loai_chung_chi.lower():
            matched_cat = valid_cat
            break
    if matched_cat == "Không xác định":
        # Giữ nguyên giá trị gốc nếu có thông tin (để matcher fuzzy match xử lý tiếp)
        matched_cat = loai_chung_chi if loai_chung_chi else "Không xác định"

    ten_chung_chi = str(
        parsed.get("ten_chung_chi_cu_the")
        or parsed.get("ten_chung_chi")
        or parsed.get("name")
        or parsed.get("title")
        or "Chứng chỉ không rõ tên"
    ).strip()

    ten_nguoi = parsed.get("ten_nguoi_duoc_cap") or parsed.get("ho_ten") or parsed.get("student_name")
    if ten_nguoi is not None:
        ten_nguoi = str(ten_nguoi).strip()
        if ten_nguoi.lower() in ("null", "none", "", "không có", "không rõ"):
            ten_nguoi = None

    ngay_cap = parsed.get("ngay_cap") or parsed.get("date") or parsed.get("issue_date")
    if ngay_cap is not None:
        ngay_cap = str(ngay_cap).strip()
        if ngay_cap.lower() in ("null", "none", "", "không có", "không rõ"):
            ngay_cap = None

    do_tin_cay_raw = str(
        parsed.get("do_tin_cay")
        or parsed.get("confidence")
        or "thap"
    ).strip().lower()

    if "cao" in do_tin_cay_raw or "high" in do_tin_cay_raw:
        do_tin_cay = "cao"
    elif "trung binh" in do_tin_cay_raw or "medium" in do_tin_cay_raw or "tb" in do_tin_cay_raw:
        do_tin_cay = "trung binh"
    else:
        do_tin_cay = "thap"

    return {
        "loai_chung_chi": matched_cat,
        "ten_chung_chi_cu_the": ten_chung_chi,
        "ten_nguoi_duoc_cap": ten_nguoi,
        "ngay_cap": ngay_cap,
        "do_tin_cay": do_tin_cay,
    }


def query_ollama_certificate(
    prompt: str,
    image_b64: str,
    model: str = DEFAULT_VISION_MODEL,
    host: str = DEFAULT_OLLAMA_HOST,
    timeout: int = DEFAULT_TIMEOUT
) -> str:
    """
    Gửi ảnh chứng chỉ và prompt tới Ollama API.
    """
    url = f"{host.rstrip('/')}/api/generate"
    cpu_cores = os.cpu_count() or 4
    num_threads = max(1, cpu_cores - 2)

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "format": "json",
        "options": {
            "num_thread": num_threads,
            "num_predict": 600,
            "temperature": 0.1
        }
    }

    logger.info(f"Đang gửi ảnh chứng chỉ tới Ollama Vision (Model: {model}, Host: {host})...")
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        response_text = data.get("response", "").strip()
        logger.debug(f"Phản hồi từ Ollama Vision: {response_text[:300]}")
        return response_text
    except requests.exceptions.HTTPError as http_err:
        err_msg = str(http_err)
        try:
            err_json = resp.json()
            if "error" in err_json:
                err_msg = f"{http_err} - Chi tiết từ Ollama: {err_json['error']}"
        except Exception:
            pass
        logger.error(f"Lỗi HTTP khi gọi Ollama API: {err_msg}")
        raise RuntimeError(f"Lỗi khi gọi Ollama API: {err_msg}")
    except requests.exceptions.ConnectionError:
        logger.error(f"Không thể kết nối tới Ollama tại {host}. Hãy kiểm tra dịch vụ đã bật chưa.")
        raise ConnectionError(
            f"Không thể kết nối tới máy chủ Ollama tại {host}. "
            f"Vui lòng đảm bảo Ollama đã được bật (lệnh: 'ollama serve')."
        )
    except requests.exceptions.Timeout:
        logger.error(f"Hết thời gian chờ ({timeout}s) khi gửi ảnh tới Ollama.")
        raise TimeoutError(f"Quá thời gian phản hồi từ Ollama Vision ({timeout}s).")
    except Exception as e:
        logger.error(f"Lỗi không xác định khi gọi Ollama API: {e}")
        raise RuntimeError(f"Lỗi không xác định khi gọi Ollama: {e}")


def extract_certificate_from_image(
    image_input: Union[str, Image.Image, np.ndarray],
    model: Optional[str] = None,
    host: str = DEFAULT_OLLAMA_HOST,
    max_retries: int = 1,
    timeout: int = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """
    Hàm chính xử lý trích xuất thông tin chứng chỉ:
    1. Chuẩn bị ảnh Base64
    2. Tự động xác định model phù hợp nếu model yêu cầu chưa được cài
    3. Gửi prompt lần 1
    4. Thử parse JSON, nếu lỗi thì log và retry 1 lần với prompt nhấn mạnh
    5. Trả về dict chuẩn hoá
    """
    image_b64 = encode_image_to_base64(image_input, max_dim=1024)

    target_model = model or DEFAULT_VISION_MODEL
    target_model = resolve_model(target_model, host=host)

    logger.info(f"=== BẮT ĐẦU TRÍCH XUẤT CHỨNG CHỈ VỚI MODEL {target_model} ===")

    raw_response = query_ollama_certificate(
        CERTIFICATE_PRIMARY_PROMPT,
        image_b64,
        model=target_model,
        host=host,
        timeout=timeout
    )

    try:
        result = clean_and_parse_certificate_json(raw_response)
        logger.info(
            f"Trích xuất chứng chỉ thành công lần 1: [{result.get('loai_chung_chi')}] - "
            f"{result.get('ten_chung_chi_cu_the')} (Độ tin cậy: {result.get('do_tin_cay')})"
        )
        return result
    except Exception as parse_error:
        logger.warning(f"Lần 1: Không thể parse JSON chứng chỉ: {parse_error}. Thử retry 1 lần...")

        if max_retries > 0:
            retry_response = query_ollama_certificate(
                CERTIFICATE_RETRY_PROMPT,
                image_b64,
                model=target_model,
                host=host,
                timeout=timeout
            )
            try:
                result = clean_and_parse_certificate_json(retry_response)
                logger.info(
                    f"Retry thành công: [{result.get('loai_chung_chi')}] - "
                    f"{result.get('ten_chung_chi_cu_the')} (Độ tin cậy: {result.get('do_tin_cay')})"
                )
                return result
            except Exception as retry_err:
                logger.error(f"Retry thất bại: {retry_err}. Phản hồi thô: {retry_response}")
                # Thay vì sập pipeline, trả về đối tượng an toàn yêu cầu xác nhận thủ công
                return {
                    "loai_chung_chi": "Không xác định",
                    "ten_chung_chi_cu_the": "Không đọc được thông tin từ ảnh",
                    "ten_nguoi_duoc_cap": None,
                    "ngay_cap": None,
                    "do_tin_cay": "thap",
                    "loi_he_thong": f"Lỗi phân tích cú pháp JSON từ mô hình: {retry_err}"
                }

        return {
            "loai_chung_chi": "Không xác định",
            "ten_chung_chi_cu_the": "Không đọc được thông tin từ ảnh",
            "ten_nguoi_duoc_cap": None,
            "ngay_cap": None,
            "do_tin_cay": "thap",
            "loi_he_thong": str(parse_error)
        }
