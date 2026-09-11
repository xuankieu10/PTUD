"""
FastAPI Backend Server phục vụ Frontend:
- Upload file bảng điểm (ảnh/PDF)
- Xử lý pipeline đọc điểm và nhận diện vùng đỏ
- Trả về kết quả JSON, thống kê và ảnh trực quan hóa dạng Base64
- API kiểm tra kết nối Ollama và lấy danh sách model sẵn có
- API tải file kết quả CSV và JSON
"""

import base64
import logging
import os
import shutil
import uuid
from typing import Optional, List
import requests
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.pipeline import run_pipeline
from backend.ocr_extractor import DEFAULT_VISION_MODEL, DEFAULT_OLLAMA_HOST

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("GradeBackendAPI")

app = FastAPI(
    title="Student Transcript Grade Pipeline API",
    description="API đọc bảng điểm học sinh bằng Ollama Vision và lọc môn không đạt kết hợp OpenCV HSV.",
    version="1.0.0"
)

# Cấu hình CORS để Frontend (React/Vite) gọi API không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.abspath("temp_uploads")
OUTPUT_DIR = os.path.abspath("output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Bộ nhớ tạm lưu phiên làm việc để tải file CSV/JSON
SESSION_CACHE = {}


@app.get("/api/health")
def check_health(host: str = DEFAULT_OLLAMA_HOST):
    """
    Kiểm tra trạng thái server và kết nối tới Ollama.
    Lấy danh sách các model đã cài đặt trên máy.
    """
    ollama_online = False
    installed_models: List[str] = []
    error_msg = None

    try:
        res = requests.get(f"{host.rstrip('/')}/api/tags", timeout=3)
        if res.status_code == 200:
            ollama_online = True
            models_data = res.json().get("models", [])
            installed_models = [m.get("name", "") for m in models_data if "name" in m]
    except Exception as e:
        error_msg = str(e)

    return {
        "status": "online",
        "ollama": {
            "online": ollama_online,
            "host": host,
            "models": installed_models,
            "recommended_model": DEFAULT_VISION_MODEL,
            "has_recommended": any(DEFAULT_VISION_MODEL in m for m in installed_models),
            "error": error_msg
        }
    }


@app.post("/api/process")
async def process_transcript(
    file: UploadFile = File(...),
    model: str = Form(DEFAULT_VISION_MODEL),
    host: str = Form(DEFAULT_OLLAMA_HOST)
):
    """
    Tiếp nhận file bảng điểm (ảnh/PDF), chạy toàn bộ pipeline và trả về kết quả.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Không có tên file.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng file '{ext}' không được hỗ trợ. Vui lòng tải lên file ảnh (.jpg, .png) hoặc .pdf."
        )

    session_id = str(uuid.uuid4())
    session_upload_dir = os.path.join(UPLOAD_DIR, session_id)
    session_output_dir = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(session_upload_dir, exist_ok=True)
    os.makedirs(session_output_dir, exist_ok=True)

    input_file_path = os.path.join(session_upload_dir, file.filename)

    try:
        # Lưu file tải lên
        with open(input_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Đã nhận file upload [{file.filename}], kích thước: {os.path.getsize(input_file_path)} bytes.")

        # Thực thi pipeline
        result = run_pipeline(
            input_path=input_file_path,
            output_dir=session_output_dir,
            model=model,
            host=host
        )

        # Đọc ảnh annotated chuyển sang Base64 để gửi về Frontend hiển thị tức thì
        annotated_b64 = None
        if os.path.exists(result["annotated_image_path"]):
            with open(result["annotated_image_path"], "rb") as img_f:
                annotated_b64 = "data:image/png;base64," + base64.b64encode(img_f.read()).decode("utf-8")

        # Lưu session cache cho thao tác download
        SESSION_CACHE[session_id] = {
            "json_path": result["json_path"],
            "csv_path": result["csv_path"],
            "filename": file.filename
        }

        return {
            "success": True,
            "session_id": session_id,
            "filename": file.filename,
            "summary": {
                "total_subjects": result["total_subjects"],
                "passed_count": result["passed_count"],
                "failed_count": result["failed_count"],
                "red_regions_count": result["red_regions_count"]
            },
            "failed_subjects": result["failed_subjects"],
            "all_subjects": result["all_subjects"],
            "annotated_image": annotated_b64
        }

    except ConnectionError as conn_err:
        logger.error(f"Lỗi kết nối Ollama: {conn_err}")
        raise HTTPException(
            status_code=503,
            detail=f"Không thể kết nối với Ollama tại '{host}'. Vui lòng kiểm tra dịch vụ Ollama local."
        )
    except Exception as e:
        logger.exception(f"Lỗi xử lý file: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi trong quá trình xử lý: {str(e)}")


@app.get("/api/download/{file_type}")
def download_result_file(file_type: str, session_id: str):
    """
    Tải về file kết quả CSV hoặc JSON theo session_id.
    """
    session_data = SESSION_CACHE.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Phiên làm việc không tồn tại hoặc đã hết hạn.")

    if file_type == "csv":
        file_path = session_data.get("csv_path")
        media_type = "text/csv; charset=utf-8"
        filename = f"ket_qua_mon_khong_dat_{session_id[:8]}.csv"
    elif file_type == "json":
        file_path = session_data.get("json_path")
        media_type = "application/json; charset=utf-8"
        filename = f"ket_qua_mon_khong_dat_{session_id[:8]}.json"
    else:
        raise HTTPException(status_code=400, detail="Loại file tải về phải là 'csv' hoặc 'json'.")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File kết quả không tìm thấy trên server.")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api:app", host="127.0.0.1", port=8000, reload=True)
