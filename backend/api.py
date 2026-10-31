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
from typing import Optional, List, Dict, Any
import requests
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.db import get_db
from backend.app.deps import get_current_user_optional
from backend.app.prompts import strip_accents
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from backend.schemas import UnifiedProcessResponse, ProcessSummaryModel, FailedSubject, PrioritySubject

from backend.pipeline import run_pipeline
from backend.ocr_extractor import DEFAULT_VISION_MODEL, DEFAULT_OLLAMA_HOST
from backend.normalize import normalize_transcript
from backend.priority_engine import rank_priority

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("GradeBackendAPI")

# ==================== PYDANTIC SCHEMAS (API CONTRACT) ====================

class ErrorResponseModel(BaseModel):
    success: bool = False
    detail: str
    status_code: int


app = FastAPI(
    title="Student Transcript Grade Pipeline API",
    description="API đọc bảng điểm học sinh bằng Ollama Vision và lọc môn không đạt kết hợp OpenCV HSV.",
    version="1.0.0"
)

# Cấu hình CORS mở rộng cho Frontend (React/Vite dev và staging)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.app.routers import auth, documents, chat, students, transcripts, center
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(students.router)
app.include_router(transcripts.router)
app.include_router(center.router)

import asyncio
from backend.app.db import SessionLocal
from backend.services.nnth_sync import sync_nnth_data

async def _periodic_nnth_sync():
    """Tác vụ nền định kỳ 6 giờ đồng bộ lịch NNTH một lần."""
    await asyncio.sleep(5)  # Đợi 5 giây sau khi ứng dụng khởi động
    while True:
        try:
            logger.info("Bắt đầu job nền đồng bộ lịch NNTH (chu kỳ 6 giờ)...")
            db = SessionLocal()
            try:
                await asyncio.to_thread(sync_nnth_data, db)
            finally:
                db.close()
        except Exception as e:
            logger.error("Lỗi trong job nền đồng bộ NNTH: %s", e)
        await asyncio.sleep(6 * 3600)  # Chu kỳ 6 giờ (21.600 giây)

@app.on_event("startup")
async def start_background_sync():
    asyncio.create_task(_periodic_nnth_sync())


# ==================== GLOBAL EXCEPTION HANDLERS ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Chuẩn hóa toàn bộ lỗi HTTP về đúng JSON schema:
    {"success": false, "detail": "Nội dung lỗi dạng string", "status_code": 400}
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "detail": str(exc.detail),
            "status_code": exc.status_code
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Chuyển lỗi xác thực Pydantic (thường là list object) thành chuỗi thông báo rõ ràng cho FE,
    tránh lỗi [object Object] khi hiển thị trên giao diện.
    """
    error_messages = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err.get("loc", []))
        msg = err.get("msg", "Dữ liệu không hợp lệ")
        error_messages.append(f"[{field}]: {msg}")
    
    readable_detail = "; ".join(error_messages) if error_messages else "Dữ liệu yêu cầu không hợp lệ."
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "detail": readable_detail,
            "status_code": 422
        }
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

    from backend.app.config import settings

    return {
        "status": "online",
        "chat_model": settings.LLM_MODEL,
        "ollama": {
            "online": ollama_online,
            "host": host,
            "models": installed_models,
            "chat_model": settings.LLM_MODEL,
            "recommended_model": DEFAULT_VISION_MODEL,
            "has_recommended": any(DEFAULT_VISION_MODEL in m for m in installed_models),
            "error": error_msg
        }
    }


@app.post("/api/process")
async def process_transcript(
    file: UploadFile = File(...),
    model: str = Form(DEFAULT_VISION_MODEL),
    host: str = Form(DEFAULT_OLLAMA_HOST),
    current_user: Optional[dict] = Depends(get_current_user_optional)
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

        user_id = current_user["id"] if current_user else None
        logger.info(f"Đã nhận file upload [{file.filename}], user_id={user_id}, kích thước: {os.path.getsize(input_file_path)} bytes.")

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

        # Dọn dẹp cache cũ (TTL = 1 giờ = 3600 giây)
        import time
        current_time = time.time()
        expired_sessions = [s_id for s_id, s_data in SESSION_CACHE.items() if current_time - s_data.get("timestamp", 0) > 3600]
        for s_id in expired_sessions:
            del SESSION_CACHE[s_id]

        # Lưu session cache cho thao tác download
        SESSION_CACHE[session_id] = {
            "json_path": result["json_path"],
            "csv_path": result["csv_path"],
            "filename": file.filename,
            "timestamp": current_time
        }

        # Dual-mapping để tương thích cả trường tiếng Việt (mon, diem) và trường chuẩn hóa (name, grade)
        # Chuẩn hóa dữ liệu trước để lấy tên tiếng Anh (name, code, credits)
        normalized_data = normalize_transcript(result["all_subjects"])
        norm_map = { c["name"]: c for c in normalized_data.get("courses", []) }
        
        def map_failed_subject(sub: Dict[str, Any]) -> dict:
            mon = sub.get("mon", "")
            diem = sub.get("diem", 0.0)
            nm = norm_map.get(mon, {})
            return {
                "course_code": nm.get("code"),
                "course_name": nm.get("name", mon),
                "credits": nm.get("credits"),
                "grade": diem,
                "semester": nm.get("semester"),
                "status": "failed",
                "filter_reason": sub.get("ly_do"),
                "is_red_marked": sub.get("is_red_marked", False),
                "bbox": sub.get("bbox")
            }
            
        def map_passed_subject(sub: Dict[str, Any]) -> dict:
            mon = sub.get("mon", "")
            diem = sub.get("diem", 0.0)
            nm = norm_map.get(mon, {})
            return {
                "course_code": nm.get("code"),
                "course_name": nm.get("name", mon),
                "credits": nm.get("credits"),
                "grade": diem,
                "semester": nm.get("semester"),
                "status": "passed",
                "filter_reason": sub.get("ly_do"),
                "is_red_marked": sub.get("is_red_marked", False),
                "bbox": sub.get("bbox")
            }

        contract_failed_subjects = [map_failed_subject(s) for s in result["failed_subjects"]]
        contract_all_subjects = [map_passed_subject(s) if not s.get("is_failed") else map_failed_subject(s) for s in result["all_subjects"]]

        # 3. Gọi Priority Engine
        dummy_curriculum = [
            {"ma_mon": "CS101", "ten_mon": "Nhập môn lập trình", "tin_chi": 3, "mon_tien_quyet": [], "hoc_ky_de_xuat": 1},
            {"ma_mon": "CS102", "ten_mon": "Cấu trúc dữ liệu", "tin_chi": 4, "mon_tien_quyet": ["CS101"], "hoc_ky_de_xuat": 2},
            {"ma_mon": "CS201", "ten_mon": "Lập trình hướng đối tượng", "tin_chi": 3, "mon_tien_quyet": ["CS101"], "hoc_ky_de_xuat": 3},
            {"ma_mon": "MATH101", "ten_mon": "Toán rời rạc", "tin_chi": 3, "mon_tien_quyet": [], "hoc_ky_de_xuat": 1},
            {"ma_mon": "ENG101", "ten_mon": "Tiếng Anh 1", "tin_chi": 3, "mon_tien_quyet": [], "hoc_ky_de_xuat": 1},
        ]
        try:
            pe_input = []
            for f_sub in contract_failed_subjects:
                # Tìm mã môn dự đoán hoặc dùng tên môn làm mã
                course_code = f_sub.get("course_code")
                if not course_code:
                    for dc in dummy_curriculum:
                        if dc["ten_mon"] == f_sub.get("course_name"):
                            course_code = dc["ma_mon"]
                            break
                    course_code = course_code or "UNKNOWN"

                pe_input.append({
                    "ma_mon": course_code,
                    "mon_hoc": f_sub.get("course_name"),
                    "tin_chi": f_sub.get("credits"),
                    "diem": f_sub.get("grade"),
                    "hoc_ky": f_sub.get("semester")
                })
            ranked = rank_priority(pe_input, dummy_curriculum)
            rank_map = { r["ma_mon"]: r for r in ranked if r.get("ma_mon") }
            
            for f_sub in contract_failed_subjects:
                # Cần dùng chung logic lấy course_code
                code = f_sub.get("course_code")
                if not code:
                    for dc in dummy_curriculum:
                        if dc["ten_mon"] == f_sub.get("course_name"):
                            code = dc["ma_mon"]
                            break
                    code = code or "UNKNOWN"
                if code and code in rank_map:
                    f_sub["priority_score"] = rank_map[code].get("do_uu_tien")
                    f_sub["priority_reason"] = rank_map[code].get("ly_do")
                    f_sub["blocked_courses"] = rank_map[code].get("mon_bi_chan", [])
                else:
                    f_sub["priority_score"] = None
                    f_sub["priority_reason"] = None
                    f_sub["blocked_courses"] = []
                    
            # Phải đồng bộ lại vào contract_all_subjects cho các môn failed
            for a_sub in contract_all_subjects:
                if a_sub["status"] == "failed":
                    code = a_sub.get("course_code")
                    if not code:
                        for dc in dummy_curriculum:
                            if dc["ten_mon"] == a_sub.get("course_name"):
                                code = dc["ma_mon"]
                                break
                        code = code or "UNKNOWN"
                    if code and code in rank_map:
                        a_sub["priority_score"] = rank_map[code].get("do_uu_tien")
                        a_sub["priority_reason"] = rank_map[code].get("ly_do")
                        a_sub["blocked_courses"] = rank_map[code].get("mon_bi_chan", [])
                    else:
                        a_sub["priority_score"] = None
                        a_sub["priority_reason"] = None
                        a_sub["blocked_courses"] = []
        except Exception as e:
            logger.error(f"Priority Engine error: {e}")

        summary_contract = {
            "total_subjects": result["total_subjects"],
            "passed_count": result["passed_count"],
            "failed_count": result["failed_count"],
            "red_regions_count": result["red_regions_count"],
            "gpa": normalized_data.get("summary", {}).get("gpa"),
            "total_credits_earned": normalized_data.get("summary", {}).get("total_credits_earned", 0),
            "total_credits_failed": normalized_data.get("summary", {}).get("total_credits_failed", 0)
        }

        return {
            "success": True,
            "session_id": session_id,
            "filename": file.filename,
            "summary": summary_contract,
            "failed_subjects": contract_failed_subjects,
            "all_subjects": contract_all_subjects,
            "annotated_image": annotated_b64,
            "normalized": normalized_data
        }

    except TimeoutError as timeout_err:
        logger.error(f"Quá thời gian xử lý bảng điểm: {timeout_err}")
        raise HTTPException(
            status_code=504,
            detail="Quá thời gian phản hồi từ hệ thống đọc ảnh (timeout). Vui lòng thử lại với hình ảnh có độ phân giải phù hợp hơn."
        )
    except ConnectionError as conn_err:
        logger.error(f"Lỗi kết nối Ollama: {conn_err}")
        raise HTTPException(
            status_code=503,
            detail=f"Không thể kết nối với Ollama tại '{host}'. Vui lòng kiểm tra dịch vụ Ollama local."
        )
    except Exception as e:
        logger.error(f"Lỗi xử lý file bảng điểm: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Đã xảy ra lỗi trong quá trình xử lý bảng điểm. Vui lòng kiểm tra lại chất lượng hình ảnh hoặc thử lại sau."
        )
    finally:
        # Xóa file upload tạm sau khi xử lý xong (kể cả khi OCR lỗi)
        if os.path.exists(session_upload_dir):
            try:
                shutil.rmtree(session_upload_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Lỗi khi xóa thư mục tạm upload '{session_upload_dir}': {e}")


@app.post("/api/certificate/process")
async def process_certificate(
    file: UploadFile = File(...),
    model: Optional[str] = Form(None),
    host: str = Form(DEFAULT_OLLAMA_HOST),
    db: Session = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Tiếp nhận ảnh chứng chỉ (JPG/PNG), trích xuất thông tin qua Ollama Vision
    và tự động so khớp với danh mục điều kiện tốt nghiệp bằng rapidfuzz.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Không có tên file.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng file '{ext}' không được hỗ trợ. Vui lòng tải lên file ảnh (.jpg, .png)."
        )

    session_id = str(uuid.uuid4())
    session_upload_dir = os.path.join(UPLOAD_DIR, "certificates", session_id)
    os.makedirs(session_upload_dir, exist_ok=True)

    input_file_path = os.path.join(session_upload_dir, file.filename)

    try:
        # Lưu file ảnh tải lên
        with open(input_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Đã nhận file chứng chỉ [{file.filename}], kích thước: {os.path.getsize(input_file_path)} bytes.")

        # 1. Gọi Ollama Vision trích xuất thông tin chứng chỉ
        from backend.certificate_extractor import extract_certificate_from_image
        from backend.certificate_matcher import match_certificate

        extracted = extract_certificate_from_image(
            image_input=input_file_path,
            model=model,
            host=host
        )

        # 2. So khớp mờ với điều kiện tốt nghiệp
        match_res = match_certificate(extracted)

        # 3. Chuẩn bị ảnh xem trước dạng Base64
        with open(input_file_path, "rb") as img_f:
            mime = "image/png" if ext == ".png" else "image/jpeg"
            preview_b64 = f"data:{mime};base64," + base64.b64encode(img_f.read()).decode("utf-8")

        # 4. Ghi nhận chứng chỉ vào student_certificates nếu người dùng là sinh viên có hồ sơ
        if current_user:
            stu_row = db.execute(
                text("SELECT id, full_name FROM students WHERE user_id = :uid"),
                {"uid": current_user["id"]}
            ).fetchone()
            if stu_row:
                student_id = stu_row.id
                raw_cert_name = extracted.get("ten_nguoi_duoc_cap")
                name_cert = " ".join(strip_accents(str(raw_cert_name or "")).lower().split()) if raw_cert_name else ""
                name_stu = " ".join(strip_accents(str(stu_row.full_name or "")).lower().split())

                is_name_matched = bool(name_cert and name_stu and name_cert == name_stu)
                is_auto = bool(match_res.get("tu_dong_cap_nhat") is True)
                cert_status = "valid" if (is_auto and is_name_matched) else "pending"

                cert_type = match_res.get("muc_tot_nghiep_khop") or extracted.get("loai_chung_chi") or "Ngoại ngữ"
                cert_name = extracted.get("ten_chung_chi_cu_the") or match_res.get("muc_tot_nghiep_khop") or extracted.get("loai_chung_chi") or "Chứng chỉ"
                issued_date = str(extracted.get("ngay_cap") or "")

                try:
                    check_tbl = db.execute(text("SELECT OBJECT_ID('student_certificates', 'U')")).scalar()
                    if check_tbl is not None:
                        existing = db.execute(
                            text("""
                                SELECT id FROM student_certificates 
                                WHERE student_id = :sid AND certificate_type = :ctype
                            """),
                            {"sid": student_id, "ctype": cert_type}
                        ).fetchone()

                        if existing:
                            db.execute(
                                text("""
                                    UPDATE student_certificates 
                                    SET certificate_name = :cname, issued_date = :idate, status = :status, created_at = SYSUTCDATETIME()
                                    WHERE id = :cid
                                """),
                                {"cid": existing.id, "cname": cert_name, "idate": issued_date, "status": cert_status}
                            )
                        else:
                            db.execute(
                                text("""
                                    INSERT INTO student_certificates (student_id, certificate_type, certificate_name, issued_date, status)
                                    VALUES (:sid, :ctype, :cname, :idate, :status)
                                """),
                                {"sid": student_id, "ctype": cert_type, "cname": cert_name, "idate": issued_date, "status": cert_status}
                            )
                        db.commit()
                        logger.info(f"Đã lưu chứng chỉ vào student_certificates: student_id={student_id}, type={cert_type}, status={cert_status}, is_name_matched={is_name_matched}")
                except Exception as db_err:
                    logger.error(f"Lỗi khi lưu student_certificates: {db_err}", exc_info=True)
                    db.rollback()

        return {
            "success": True,
            "session_id": session_id,
            "filename": file.filename,
            "extracted_data": extracted,
            "matching_result": match_res,
            "preview_image": preview_b64
        }

    except ConnectionError as conn_err:
        logger.error(f"Lỗi kết nối Ollama: {conn_err}")
        raise HTTPException(
            status_code=503,
            detail=f"Không thể kết nối với Ollama tại '{host}'. Vui lòng kiểm tra dịch vụ Ollama local."
        )
    except TimeoutError as timeout_err:
        logger.error(f"Quá thời gian chờ Ollama: {timeout_err}")
        raise HTTPException(
            status_code=504,
            detail="Quá thời gian phản hồi từ Ollama Vision khi phân tích chứng chỉ."
        )
    except Exception as e:
        logger.error(f"Lỗi xử lý chứng chỉ: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Đã xảy ra lỗi trong quá trình xử lý chứng chỉ. Vui lòng thử lại sau."
        )
    finally:
        # Xóa file upload tạm sau khi xử lý xong (kể cả khi OCR lỗi)
        if os.path.exists(session_upload_dir):
            try:
                shutil.rmtree(session_upload_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Lỗi khi xóa thư mục tạm upload chứng chỉ '{session_upload_dir}': {e}")


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
