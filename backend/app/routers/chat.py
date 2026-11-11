import json
import logging
import os
import re
import shutil
import uuid
import requests
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from datetime import datetime

from backend.app.db import get_db
from backend.app.deps import get_current_user
from backend.app.config import settings
from backend.app.services.retrieval import search_chunks, strip_accents
from backend.app.prompts import (
    SYSTEM_PROMPT, NO_CONTEXT_RESPONSE, REFUSAL_RESPONSE, FACULTY_NOT_SUPPORTED_RESPONSE,
    LANG_REMINDER, LANG_RETRY_SYSTEM,
    is_injection, has_vietnamese, mixed_language
)
from backend.app.routers.students import graduation_check, calculate_graduation_data
from backend.services.nnth_sync import (
    get_upcoming_schedules,
    get_upcoming_exams,
    get_last_sync_info
)

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

# Header chống buffer cho Server-Sent Events (SSE) stream
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

# ─── Câu hỏi chỉ hỏi về hội thoại (không cần RAG) ───────────────────────────
_CONVO_QUERIES = frozenset([
    "tôi vừa nói gì?", "tôi vừa hỏi gì?",
])

GREETING_RESPONSE = (
    "Xin chào! Tôi là Trợ lý AI tư vấn học vụ dành cho sinh viên Khoa Công nghệ Thông tin - Trường Đại học Lạc Hồng (LHU).\n\n"
    "Tôi có thể hỗ trợ bạn các thông tin học vụ sau:\n"
    "• Tra cứu và kiểm tra điều kiện tốt nghiệp, tiến độ tích lũy tín chỉ.\n"
    "• Quy định chuẩn đầu ra Ngoại ngữ và Tin học.\n"
    "• Danh sách môn chưa đạt (nợ môn, điểm F) và hướng dẫn đăng ký học lại/cải thiện.\n"
    "• Lịch khai giảng khóa học và lịch thi chứng chỉ tại Trung tâm Ngoại ngữ - Tin học.\n\n"
    "Một số câu hỏi mẫu bạn có thể hỏi tôi:\n"
    "1. \"Điều kiện xét tốt nghiệp của Khoa CNTT gồm những gì?\"\n"
    "2. \"Tôi còn nợ môn nào, cần làm gì để tốt nghiệp?\"\n"
    "3. \"Lịch thi chứng chỉ tin học và ngoại ngữ gần nhất là khi nào?\""
)

THANKS_RESPONSE = (
    "Không có chi! Rất vui được hỗ trợ bạn. "
    "Nếu bạn có bất kỳ thắc mắc nào về học vụ hoặc lịch thi chứng chỉ, hãy nhắn cho tôi nhé!"
)

FAREWELL_RESPONSE = (
    "Tạm biệt bạn! Chúc bạn học tập tốt và gặt hái nhiều kết quả cao tại Khoa CNTT - Đại học Lạc Hồng."
)


def get_smalltalk_response(msg: str) -> Optional[str]:
    """
    Nhận diện câu chào hỏi và xã giao đơn giản, trả về phản hồi định sẵn không cần gọi LLM/RAG.
    Chỉ coi là xã giao khi câu ngắn (<= 7 từ) và KHÔNG chứa yêu cầu học vụ hay injection.
    """
    if not msg:
        return None
    raw = msg.strip().lower()
    clean = re.sub(r'[\.,!\?:;~\-_]+', ' ', raw)
    words = clean.split()
    if not words or len(words) > 7:
        return None

    norm = " ".join(words)
    norm_unaccent = strip_accents(norm)

    # Chặn nếu có từ khóa học vụ hoặc yêu cầu kỹ thuật/khác
    academic_and_action_keywords = [
        "tot nghiep", "tin chi", "hoc phan", "mon", "diem", "rot", "no", "chua dat",
        "bang diem", "hoc vu", "chuan dau ra", "lich thi", "lich hoc", "khai giang",
        "khoa", "cntt", "gpa", "hoc phi", "viet code", "viet", "code", "lap trinh",
        "nau an", "tho", "tim", "tra cuu", "xem"
    ]
    if any(k in norm_unaccent for k in academic_and_action_keywords):
        return None

    # 1. Cảm ơn
    thanks_set = {
        "cam on", "cam on ban", "cam on nha", "cam on nhe", "cam on ad", "cam on bot",
        "cam on nhieu", "thanks", "thank you", "thank", "tks", "ok cam on", "da cam on",
        "em cam on", "toi cam on"
    }
    if norm_unaccent in thanks_set:
        return THANKS_RESPONSE

    # 2. Tạm biệt
    farewell_set = {
        "tam biet", "bye", "bye bye", "goodbye", "hen gap lai", "chao tam biet", "bai bai"
    }
    if norm_unaccent in farewell_set:
        return FAREWELL_RESPONSE

    # 3. Lời chào / Giới thiệu bản thân
    greeting_set = {
        "xin chao", "chao", "chao ban", "chao bot", "chao ad", "chao admin", "chao em",
        "chao anh", "chao chi", "chao thay", "chao co", "hi", "hello", "hey", "halo", "helo",
        "alo", "hi bot", "hello bot", "hi ban", "hello ban", "xin chao ban", "xin chao bot",
        "ban la ai", "may la ai", "cau la ai", "ai day", "who are you",
        "ban lam duoc gi", "ban giup duoc gi", "ban co the lam gi", "ban lam gi duoc",
        "chuc nang cua ban", "giup duoc gi", "ban giup gi duoc", "chuc nang la gi"
    }
    if norm_unaccent in greeting_set:
        return GREETING_RESPONSE

    greeting_pattern = re.compile(
        r"^(xin\s+)?ch[aà]o(\s+(b[aạ]n|ad|admin|bot|c[aậ]u|em|th[aà]y|c[oô]))?$",
        re.IGNORECASE
    )
    if greeting_pattern.match(clean.strip()):
        return GREETING_RESPONSE

    return None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[int] = None

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty or just whitespace")
        return v


def check_guardrails(msg: str) -> Optional[tuple[str, str]]:
    """
    Kiểm tra xem câu hỏi có thuộc phạm vi khoa khác, ngoài lề hoặc vi phạm dữ liệu riêng tư không.
    Chuẩn hóa hạ chữ thường, bỏ dấu và gom khoảng trắng để chặn cả câu không dấu.
    Trả về (answer_text, guardrail_type) nếu vi phạm, hoặc None nếu hợp lệ.
    """
    msg_clean = re.sub(r'\s+', ' ', msg.lower()).strip()
    msg_unaccent = strip_accents(msg_clean)

    # 1. Kiểm tra yêu cầu tra cứu điểm / dữ liệu của sinh viên khác (Bảo mật quyền riêng tư)
    privacy_other_kws = ["sinh vien khac", "nguoi khac", "ban khac", "nguoi ta", "ai do"]
    privacy_data_kws = ["diem", "bang diem", "ket qua", "thong tin", "gpa", "hoc luc", "tra cuu diem", "xem diem"]
    if any(k in msg_unaccent for k in privacy_other_kws) and any(d in msg_unaccent for d in privacy_data_kws):
        privacy_refusal = (
            "Xin lỗi, vì lý do bảo mật thông tin và quyền riêng tư, tôi không thể cung cấp điểm số "
            "hoặc dữ liệu học tập của sinh viên khác. Bạn chỉ có thể tra cứu thông tin của chính mình khi đã đăng nhập."
        )
        return privacy_refusal, "privacy_violation"

    # 2. Kiểm tra câu hỏi ngoài lề (off-topic)
    off_topic_patterns = [
        "nau pho", "cong thuc nau", "cach nau", "mon an", "bong da", "thoi tiet",
        "choi game", "ca si", "dien vien", "tho tinh", "to tinh", "che bien",
        "banh mi", "lam banh", "cong thuc lam", "cach lam banh", "nau an",
        "thuc don", "pha che", "chung khoan", "tien ao", "bitcoin", "tu vi", "boi toan"
    ]
    if any(pat in msg_unaccent for pat in off_topic_patterns):
        return REFUSAL_RESPONSE, "off_topic"

    # 3. Kiểm tra hỏi về khoa/ngành khác (Hệ thống chỉ hỗ trợ Khoa CNTT LHU)
    it_keywords = ["cong nghe thong tin", "cntt", "tin hoc", "it", "phan mem", "an toan thong tin", "mang may tinh", "khoa hoc may tinh"]
    is_it_query = any(k in msg_unaccent for k in it_keywords)

    if not is_it_query:
        # Danh sách các động từ và từ chỉ hành động học vụ theo sau để nhận diện câu hỏi học vụ hợp lệ
        # (tránh chặn nhầm 'được'/'dược', 'luật'/'kỷ luật' khi người dùng gõ không dấu hoặc hỏi quy chế chung)
        ACADEMIC_ACTION_VERBS = [
            "xet", "nop", "mien", "thi", "hoc", "cap", "dang ky", "to chuc",
            "nhan", "bao luu", "tot nghiep", "cong nhan", "khai giang", "sat hach",
            "canh bao", "thoi hoc", "dieu kien", "hoan thanh", "ho so", "quyet dinh"
        ]

        other_faculties_map = [
            ("dược", "duoc"),
            ("luật", "luat"),
            ("kinh tế", "kinh te"),
            ("du lịch", "du lich"),
            ("y khoa", "y khoa"),
            ("y học", "y hoc"),
            ("cơ điện", "co dien"),
            ("điện tử", "dien tu"),
            ("ngôn ngữ", "ngon ngu"),
            ("đông phương", "dong phuong"),
            ("tài chính", "tai chinh"),
            ("ngân hàng", "ngan hang"),
            ("kế toán", "ke toan"),
            ("quản trị", "quan tri"),
            ("môi trường", "moi truong"),
            ("thực phẩm", "thuc pham"),
            ("hóa học", "hoa hoc"),
            ("xây dựng", "xay dung"),
            ("khoa khác", "khoa khac"),
            ("ngành khác", "nganh khac"),
        ]

        is_accented = has_vietnamese(msg)

        if is_accented:
            # Phân nhánh 1: Câu CÓ DẤU -> so khớp chính xác theo dạng có dấu, không nhầm "dược" với "được"
            for fac_vi, _ in other_faculties_map:
                if fac_vi == "dược":
                    if re.search(r'\b(khoa|ngành|sinh viên|bộ môn)\s+dược\b', msg_clean) or re.search(r'\b(dược sĩ|dược học)\b', msg_clean):
                        return FACULTY_NOT_SUPPORTED_RESPONSE, "other_faculty"
                    if re.search(r'\b(tốt nghiệp|chuẩn đầu ra)\s+(?:của\s+)?(?:khoa\s+)?dược\b', msg_clean):
                        return FACULTY_NOT_SUPPORTED_RESPONSE, "other_faculty"
                elif fac_vi == "luật":
                    # Chỉ chặn khi đề cập Khoa/Ngành Luật; loại trừ "kỷ luật", "quy luật", "pháp luật", "luật giáo dục"
                    if re.search(r'(?<!kỷ\s)(?<!quy\s)(?<!pháp\s)(?<!bộ\s)\b(khoa|ngành|sinh viên khoa)\s+luật\b', msg_clean):
                        return FACULTY_NOT_SUPPORTED_RESPONSE, "other_faculty"
                    if re.search(r'\b(khoa luật|ngành luật)\b', msg_clean):
                        return FACULTY_NOT_SUPPORTED_RESPONSE, "other_faculty"
                    if re.search(r'\bsinh viên\s+khoa\s+luật\b', msg_clean):
                        return FACULTY_NOT_SUPPORTED_RESPONSE, "other_faculty"
                    if re.search(r'\b(tốt nghiệp|chuẩn đầu ra)\s+(?:của\s+)?(?:khoa\s+)?luật\b', msg_clean):
                        return FACULTY_NOT_SUPPORTED_RESPONSE, "other_faculty"
                else:
                    if f"khoa {fac_vi}" in msg_clean or f"ngành {fac_vi}" in msg_clean:
                        return FACULTY_NOT_SUPPORTED_RESPONSE, "other_faculty"
                    if fac_vi in ["kinh tế", "du lịch"] and f" {fac_vi}" in msg_clean and any(w in msg_clean for w in ["tốt nghiệp", "điều kiện", "xét", "chuẩn đầu ra", "ngoại ngữ"]):
                        return FACULTY_NOT_SUPPORTED_RESPONSE, "other_faculty"
        else:
            # Phân nhánh 2: Câu KHÔNG DẤU -> chỉ chặn khi cụm đứng như tên khoa (không theo sau bởi động từ học vụ)
            # Điểm đánh đổi: các câu mơ hồ như "khoa duoc tot nghiep..." nếu không chặn sẽ đi tiếp vào RAG;
            # vì hệ thống chỉ lưu tài liệu Khoa CNTT nên tối đa chatbot sẽ báo không có dữ liệu, không gây hại.
            for fac_vi, fac_ascii in other_faculties_map:
                for prefix in ["khoa ", "nganh ", "sinh vien khoa "]:
                    target_phrase = f"{prefix}{fac_ascii}"
                    if target_phrase in msg_unaccent:
                        pattern = rf'\b{re.escape(target_phrase)}\s+(\w+)'
                        m = re.search(pattern, msg_unaccent)
                        if m:
                            next_word = m.group(1).lower()
                            if next_word in ACADEMIC_ACTION_VERBS:
                                # Trợ động từ hoặc hành động học vụ đi liền sau (ví dụ: 'khoa được xét', 'khoa được tổ chức')
                                continue
                        return FACULTY_NOT_SUPPORTED_RESPONSE, "other_faculty"

                if fac_ascii in ["du lich", "kinh te"]:
                    if f" {fac_ascii}" in msg_unaccent and any(w in msg_unaccent for w in ["tot nghiep", "dieu kien", "xet", "chuan dau ra", "ngoai ngu"]):
                        return FACULTY_NOT_SUPPORTED_RESPONSE, "other_faculty"

    return None


def clean_source_text(text: str) -> str:
    """
    Hậu xử lý xóa các dòng bắt đầu bằng 'Nguồn:', '- Nguồn:', '* Nguồn:', 'Tham khảo:',
    và các dòng chỉ chứa URL cs.lhu.edu.vn hoặc link tham khảo.
    """
    if not text:
        return ""
    lines = text.split("\n")
    cleaned_lines = []

    source_prefix_pattern = re.compile(
        r"^\s*([-*•]|\d+\.)?\s*(Nguồn|Tham khảo|Tài liệu tham khảo)\s*:",
        re.IGNORECASE
    )
    url_only_pattern = re.compile(
        r"^\s*https?://\S+\s*$",
        re.IGNORECASE
    )

    in_source_block = False
    for line in lines:
        stripped = line.strip()
        if source_prefix_pattern.match(stripped):
            in_source_block = True
            continue
        if in_source_block:
            if url_only_pattern.match(stripped) or "cs.lhu.edu.vn" in stripped:
                continue
            if re.match(r"^\s*([-*•]|\d+\.)\s+", stripped) and any(w in stripped.lower() for w in ["mục", "điều kiện", "quy định", "thủ tục", "căn cứ", "qd", "qđ"]):
                continue
            if not stripped:
                continue
            in_source_block = False

        if "cs.lhu.edu.vn" in stripped and url_only_pattern.match(stripped):
            continue

        cleaned_lines.append(line)

    res = "\n".join(cleaned_lines)
    res = re.sub(r'\n{3,}', '\n\n', res).strip()
    return res


def get_student_academic_and_ocr_context(db: Session, user_id: int) -> tuple[str, Optional[dict], Optional[dict]]:
    """
    Truy vấn kết quả OCR mới nhất và hồ sơ học vụ (graduation-check) của chính sinh viên đó.
    Đảm bảo cô lập tuyệt đối dữ liệu theo user_id (không để dữ liệu sinh viên này lọt sang sinh viên khác).
    Trả về: (context_text, ocr_dict, grad_dict)
    """
    ctx_parts = []
    ocr_info = None
    grad_info = None

    # 1. Lấy kết quả OCR mới nhất của chính sinh viên này từ bảng student_ocr_transcripts
    try:
        ocr_row = db.execute(
            text("""
                SELECT TOP 1 id, filename, total_subjects, passed_count, failed_count, courses_data, summary_text, created_at
                FROM student_ocr_transcripts
                WHERE user_id = :uid
                ORDER BY id DESC
            """),
            {"uid": user_id}
        ).fetchone()

        if ocr_row:
            try:
                courses = json.loads(ocr_row.courses_data)
                failed_courses = []
                failed_courses_structured = []
                passed_courses = []
                for c in courses:
                    mon = c.get("course_name") or c.get("mon") or c.get("name") or "Chưa rõ tên môn"
                    code = c.get("course_code") or c.get("ma_mon") or ""
                    diem = c.get("grade") if c.get("grade") is not None else c.get("diem", 0.0)
                    ly_do = c.get("filter_reason") or c.get("ly_do") or ""
                    is_red = bool(c.get("is_red_marked") is True or "đỏ" in str(ly_do).lower() or "red" in str(ly_do).lower())
                    is_failed = (
                        c.get("status") == "failed" or
                        c.get("is_failed") is True or
                        (diem is not None and float(diem) < 4.0) or
                        is_red
                    )

                    code_str = f" ({code})" if code else ""
                    ly_do_str = f" - Lý do: {ly_do}" if ly_do else ""
                    course_line = f"  + {mon}{code_str}: Điểm {diem}{ly_do_str}"

                    if is_failed:
                        failed_courses.append(course_line)
                        failed_courses_structured.append({
                            "code": code,
                            "name": mon,
                            "grade": float(diem) if diem is not None else 0.0,
                            "filter_reason": ly_do,
                            "is_red_marked": is_red,
                            "source": "OCR"
                        })
                    else:
                        passed_courses.append(course_line)

                ocr_info = {
                    "filename": ocr_row.filename,
                    "total_subjects": ocr_row.total_subjects,
                    "passed_count": ocr_row.passed_count,
                    "failed_count": ocr_row.failed_count,
                    "failed_courses": failed_courses,
                    "failed_courses_structured": failed_courses_structured,
                    "summary_text": ocr_row.summary_text
                }

                ocr_lines = [
                    f"\n--- [KẾT QUẢ BẢNG ĐIỂM ĐÃ QUÉT (OCR) CỦA BẠN - Tệp: {ocr_row.filename}] ---",
                    f"Tổng số môn trích xuất: {ocr_row.total_subjects} môn (ĐẠT: {ocr_row.passed_count}, CHƯA ĐẠT: {ocr_row.failed_count})"
                ]
                if failed_courses:
                    ocr_lines.append("Danh sách các môn CHƯA ĐẠT (môn rớt / điểm < 4.0 / đánh dấu đỏ):")
                    ocr_lines.extend(failed_courses)
                else:
                    ocr_lines.append("Tất cả các môn trong bảng điểm OCR đều ĐẠT (>= 4.0).")

                ctx_parts.append("\n".join(ocr_lines))
            except Exception as e:
                logger.error(f"Lỗi parse dữ liệu OCR bảng điểm cho user {user_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Lỗi truy vấn bảng student_ocr_transcripts cho user {user_id}: {e}", exc_info=True)

    # 2. Lấy dữ liệu hồ sơ học vụ & điều kiện tốt nghiệp (graduation-check)
    try:
        stu_row = db.execute(
            text("SELECT id, user_id, student_code, full_name, major, cohort FROM students WHERE user_id = :uid"),
            {"uid": user_id}
        ).fetchone()

        if stu_row:
            try:
                grad = calculate_graduation_data(stu_row.id, db, explain=False)
                grad_info = grad
                stu_nested = grad.get("student") if isinstance(grad.get("student"), dict) else {}
                student_name = stu_nested.get("full_name") or stu_row.full_name
                student_code = stu_nested.get("student_code") or stu_row.student_code

                total_credits_passed = grad.get("total_credits_passed", grad.get("total_credits_earned", 0))
                required_credits = grad.get("required_credits", grad.get("total_credits_required", settings.REQUIRED_CREDITS))
                credits_missing = grad.get("credits_missing", max(0, required_credits - total_credits_passed))
                total_credits_failed = grad.get("total_credits_failed", 0)
                notes = grad.get("notes", "Chưa đủ điều kiện tốt nghiệp")

                grad_lines = [
                    f"\n--- [HỒ SƠ HỌC VỤ & TIẾN ĐỘ TỐT NGHIỆP CỦA SINH VIÊN {student_name} (MSSV: {student_code})] ---",
                    f"- Tín chỉ tích lũy: {total_credits_passed} / {required_credits} tín chỉ",
                    f"- Tín chỉ còn thiếu: {credits_missing} tín chỉ",
                    f"- Tín chỉ chưa đạt (nợ điểm): {total_credits_failed} tín chỉ",
                    f"- Trạng thái tốt nghiệp: {notes}"
                ]
                if grad.get("certificates"):
                    certs = grad["certificates"]
                    grad_lines.append(f"- Chứng chỉ Ngoại ngữ: {certs.get('english', 'chưa có dữ liệu, cần nộp')}")
                    grad_lines.append(f"- Chứng chỉ Tin học: {certs.get('it', 'chưa có dữ liệu, cần nộp')}")
                if grad.get("missing_required_courses"):
                    m_names = ", ".join([f"{m['name']} ({m.get('credits', 0)} TC)" for m in grad["missing_required_courses"]])
                    grad_lines.append(f"- Các môn bắt buộc theo CTĐT còn thiếu ({len(grad['missing_required_courses'])} môn): {m_names}")
                if grad.get("failed_courses"):
                    f_names = ", ".join([f"{f['name']} (Điểm {f.get('grade', 0.0)})" for f in grad["failed_courses"]])
                    grad_lines.append(f"- Các môn chưa đạt trong hệ thống ({len(grad['failed_courses'])} môn): {f_names}")

                ctx_parts.append("\n".join(grad_lines))
            except Exception as e:
                logger.error(f"Lỗi lấy dữ liệu graduation-check trong chat cho user {user_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Lỗi truy vấn bảng students cho user {user_id}: {e}", exc_info=True)

    full_student_ctx = "\n\n".join(ctx_parts).strip()
    return full_student_ctx, ocr_info, grad_info


SAFE_MIXED_WORDS = {
    "powerpoint", "javascript", "elearning", "typescript", "iphone", "phd",
    "mssv", "github", "linkedin", "chatgpt", "openai", "youtube", "facebook",
    "tiktok", "nodejs", "reactjs", "vuejs", "nextjs", "gitlab", "bitbucket",
    "vscode", "devops", "fastapi", "sqlserver", "postgresql", "mongodb",
    "appme", "zalo", "vstep", "cefr", "toefl", "ielts", "google", "gmail"
}
VIETNAMESE_ACCENTED_CHARS = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"


def has_stuck_mixed_language(text: str) -> bool:
    """Kiểm tra từ bị dính chữ thường và chữ hoa (như việcDismissal).
    Chỉ coi là lỗi khi ký tự trước là chữ có dấu tiếng Việt hoặc cả cụm
    vừa dính nhau vừa nằm ngoài danh sách an toàn (PowerPoint, JavaScript...).
    Bỏ qua liên kết URL (thường chứa chuỗi ngẫu nhiên hoa thường).
    """
    text_no_url = re.sub(r"https?://\S+", "", text)

    # 1. Ký tự ngay trước chữ hoa là chữ có dấu tiếng Việt (vd: kỹNăng, đồÁn...)
    if re.search(rf"[{VIETNAMESE_ACCENTED_CHARS}][A-Z]", text_no_url):
        return True

    # 2. Cả cụm vừa dính nhau ([a-z][A-Z]) vừa nằm ngoài danh sách an toàn
    words = re.findall(r"\b[a-zA-Z0-9_à-ỹÀ-Ỹ]*[a-z][A-Z][a-zA-Z0-9_à-ỹÀ-Ỹ]*\b", text_no_url)
    for w in words:
        clean_w = re.sub(r"[^a-zA-Z0-9à-ỹÀ-Ỹ]", "", w).strip()
        if clean_w.lower() not in SAFE_MIXED_WORDS:
            return True

    return False


def normalize_subject_name(name: str) -> str:
    """Chuẩn hóa tên môn học: bỏ dấu, hạ chữ thường, bỏ khoảng trắng thừa, chuẩn hóa các biến thể phổ biến."""
    if not name:
        return ""
    unaccented = strip_accents(str(name)).lower()
    unaccented = re.sub(r'\bmarx\b', 'mac', unaccented)
    clean = re.sub(r'[\.,!\?:;~\-_\(\)\[\]\{\}]+', ' ', unaccented)
    return " ".join(clean.split())


def normalize_subject_code(code: str) -> str:
    """Chuẩn hóa mã môn: chữ hoa, bỏ khoảng trắng và gạch nối."""
    if not code:
        return ""
    return re.sub(r'[\s\-_]+', '', str(code)).upper()


def format_course_grade_source(item: dict) -> str:
    """Định dạng nguồn điểm: hệ thống hoặc OCR; nếu lệch điểm thì hiện cả hai kèm ghi chú."""
    name_str = item["name"]
    code_str = f" ({item['code']})" if item.get("code") else ""
    sys_g = item.get("system_grade")
    ocr_g = item.get("ocr_grade")

    if sys_g is not None and ocr_g is not None:
        if item.get("is_differing_grades"):
            grade_info = f"Điểm hệ thống {sys_g}, Điểm OCR {ocr_g} (chênh lệch điểm giữa hệ thống và OCR)"
        else:
            grade_info = f"Điểm {sys_g} (hệ thống & OCR)"
    elif sys_g is not None:
        grade_info = f"Điểm hệ thống {sys_g}"
    elif ocr_g is not None:
        grade_info = f"Điểm OCR {ocr_g}"
    else:
        grade_info = "Chưa có thông tin điểm"

    return f"{name_str}{code_str}: {grade_info}"


def format_failed_course_guidance(course: dict) -> str:
    """
    Phân loại hướng dẫn xử lý môn không đạt thành 3 nhánh theo Quy chế đào tạo (Chương III – Điều 19 & Chương II – Điều 12):
    1. Bị cấm thi (vắng > 20% hoặc điểm thành phần < 2.0 hoặc có ghi chú cấm thi):
       -> 'Bị cấm thi, cần đăng ký học lại (không được thi lần 2)'
    2. Đủ điều kiện dự thi (điểm không đạt nhưng đủ điều kiện dự thi):
       -> 'Được đăng ký thi lần 2 (đầu học kỳ sau) hoặc học lại'
    3. Không đủ dữ liệu để phân biệt:
       -> 'Cần học lại hoặc thi lại (xem chi tiết trên cổng sinh viên hoặc liên hệ giáo vụ)'
    """
    from backend.grade_filter import classify_failure_reason
    reason = classify_failure_reason(course)
    if reason == "Bị cấm thi, cần đăng ký học lại":
        return "Bị cấm thi, cần đăng ký học lại (không được thi lần 2)"
    elif reason == "Được đăng ký thi lần 2 (đầu học kỳ sau) hoặc học lại":
        return "Được đăng ký thi lần 2 (đầu học kỳ sau) hoặc học lại"
    else:
        return "Cần học lại hoặc thi lại (xem chi tiết trên cổng sinh viên hoặc liên hệ giáo vụ)"


REGISTRATION_LINKS_NOTE = (
    "Lưu ý: Điểm chuyên cần và kiểm tra giữa kỳ không có thi lần 2. "
    "Link đăng ký học lại: https://forms.gle/iBk3hNwG4SCGKMEFA, "
    "group Zalo hỗ trợ: https://zalo.me/g/ar6b85p9opfxctwhxwpd"
)


def clean_academic_regulation_answer(answer: str, user_message: str) -> str:
    """
    Hậu kiểm chống bịa khi trả lời quy chế:
    - Câu điều kiện xét tốt nghiệp: loại bỏ các ý tự thêm về hạnh kiểm, học phí ngoài văn bản.
    - Câu cấm thi: chỉ trả 2 lý do (vắng quá 20% số tiết, điểm thành phần dưới 2.0). Thêm lưu ý thông tin chưa xác nhận chính thức từ VB2.
    - Câu học vét: không tự định nghĩa; nói rõ chưa có văn bản riêng về lớp học vét, hướng dẫn đăng ký học lại theo chunk.
    - Điểm xung đột Mục 8: trả lời theo VB1 và nhắc có văn bản khác ghi khác.
    """
    msg_l = (user_message or "").lower()

    # 1. Câu hỏi cấm thi
    if "cấm thi" in msg_l or "cam thi" in msg_l:
        lines = answer.split("\n")
        kept = []
        for line in lines:
            line_l = line.lower()
            if any(k in line_l for k in ["cảnh báo học vụ", "canh bao hoc vu", "buộc thôi học", "buoc thoi hoc", "dưới ngưỡng quy định", "2 học kỳ"]):
                continue
            kept.append(line)
        cleaned = "\n".join(kept).strip()
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        if len(cleaned) > 20:
            answer = cleaned

        # Đảm bảo nêu ĐỦ CẢ 2 ĐIỀU KIỆN cấm thi theo Chunk Mục 2
        has_cond_absent = any(k in answer.lower() for k in ["20%", "vắng mặt", "vắng quá", "số tiết"])
        has_cond_score = any(k in answer.lower() for k in ["2.0", "2,0", "thành phần", "bộ phận", "chuyên cần", "giữa kỳ"])
        if not has_cond_score:
            cond_score_text = "- Điểm đánh giá bộ phận / điểm thành phần (chuyên cần, kiểm tra giữa kỳ) dưới 2.0 (thang 10) thì không đủ điều kiện dự thi."
            if "20%" in answer:
                answer = re.sub(r"(.*20%[^\.\n]*[\.\n])", r"\1\n" + cond_score_text + "\n", answer, count=1)
            else:
                answer += f"\n{cond_score_text}"
        if not has_cond_absent:
            cond_absent_text = "- Vắng mặt quá 20% số tiết của học phần (lý thuyết hoặc thực hành)."
            answer = f"{cond_absent_text}\n" + answer

        if "chưa được xác nhận chính thức" not in answer.lower() and "chưa kiểm chứng" not in answer.lower():
            answer += "\n\n(Lưu ý: Thông tin điều kiện cấm thi này chưa được xác nhận chính thức trong Niên giám, bạn nên hỏi giáo vụ khoa để được hướng dẫn chính xác nhất)."

    # 2. Câu hỏi điều kiện xét tốt nghiệp (không phải cá nhân hoá điểm)
    if any(k in msg_l for k in ["điều kiện xét tốt nghiệp", "dieu kien xet tot nghiep", "điều kiện tốt nghiệp", "dieu kien tot nghiep"]) and not any(k in msg_l for k in ["của tôi", "của em", "tôi cần", "em cần"]):
        lines = answer.split("\n")
        kept = []
        for line in lines:
            line_l = line.lower()
            # Chỉ loại bỏ các ý thực sự bịa đặt ngoài văn bản (như hạnh kiểm, học phí tốt nghiệp).
            # KHÔNG loại bỏ các điều kiện từ Document 79 (đình chỉ học tập, ĐTBCTL >= 5.0 thang 10).
            if any(k in line_l for k in ["hạnh kiểm", "hanh kiem", "học phí tốt nghiệp"]):
                continue
            kept.append(line)
        cleaned = "\n".join(kept).strip()
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        if len(cleaned) > 20:
            answer = cleaned
        # Không tự quy đổi sang thang 4: chuẩn hóa về >= 5.0 (thang 10) nếu LLM xuất hiện 2.00 (thang 4)
        answer = re.sub(r'\b2(?:\.00?|\,00?)\s*(?:/\s*4(?:\.0)?|\(thang 4\)|thang 4)\b', '5.0 (thang 10)', answer, flags=re.IGNORECASE)
        # Bổ sung ý "không còn học phần không đạt" nếu chưa có
        if "không còn học phần không đạt" not in answer.lower():
            if "150 tín chỉ" in answer:
                answer = re.sub(
                    r"(150 tín chỉ[^\.\n]*)",
                    r"\1 (không còn học phần không đạt)",
                    answer,
                    count=1
                )
            else:
                answer += "\n- Không còn học phần không đạt (không còn môn điểm F dưới 4.0)."

    # 3. Câu hỏi về học vét
    if "học vét" in msg_l or "hoc vet" in msg_l:
        note_prefix = "Hiện tại tài liệu hiện có không đề cập riêng về lớp học vét; sinh viên có nhu cầu học lại thực hiện theo quy trình đăng ký học lại thông thường."
        answer = re.sub(r"Hiện tại,? Nhà trường chưa có văn bản quy định riêng về lớp học vét", "Hiện tại tài liệu hiện có không đề cập riêng về lớp học vét", answer, flags=re.IGNORECASE)
        answer = re.sub(r"Nhà trường chưa có văn bản quy định riêng về lớp học vét", "tài liệu hiện có không đề cập riêng về lớp học vét", answer, flags=re.IGNORECASE)
        if "tài liệu hiện có không đề cập riêng" not in answer.lower():
            answer = re.sub(r"^Học vét là[^\.\n]+\.", note_prefix, answer, flags=re.IGNORECASE)
            if note_prefix not in answer:
                answer = f"{note_prefix}\n\n{answer}"

    # 4. Câu hỏi về kỹ năng mềm
    if any(k in msg_l for k in ["kỹ năng mềm", "ky nang mem", "kĩ năng mềm", "ki nang mem"]):
        answer = re.sub(r",?\s*(?:của|thuộc)\s*Khoa\s*(?:Công nghệ thông tin|CNTT),?", "", answer, flags=re.IGNORECASE)
        answer = re.sub(r"\bKhoa\s*(?:Công nghệ thông tin|CNTT)\s*–?\s*", "", answer, flags=re.IGNORECASE)
        answer = re.sub(
            r"Kỹ năng viết CV điện tử và (?:trả lời phỏng vấn|phỏng vấn tìm việc làm|phỏng vấn xin việc|phỏng vấn)",
            "Kỹ năng viết CV điện tử và trả (văn bản gốc bị cắt, chưa xác nhận tên đầy đủ)",
            answer,
            flags=re.IGNORECASE
        )
        if "Kỹ năng viết CV điện tử và trả" in answer and "chưa xác nhận tên đầy đủ" not in answer:
            answer = re.sub(
                r"Kỹ năng viết CV điện tử và trả(?:\s*\[.*?\])?",
                "Kỹ năng viết CV điện tử và trả (văn bản gốc bị cắt, chưa xác nhận tên đầy đủ)",
                answer,
                flags=re.IGNORECASE
            )
        # Chống ảo giác học phí kỹ năng mềm: chuẩn hóa 500.000 VNĐ / môn theo Mục 7.4
        answer = answer.replace("300.000", "500.000")

    # 5. Xử lý các điểm xung đột (Mục 8)
    # 5a. Ngưỡng F / điểm không đạt: theo VB1 là < 4.0; nhắc thêm văn bản khác ghi < 5.0
    if any(k in msg_l for k in ["ngưỡng điểm f", "nguong diem f", "ngưỡng f", "nguong f", "điểm f là", "diem f la", "ngưỡng không đạt", "nguong khong dat"]) or (("điểm f" in msg_l or "diem f" in msg_l) and ("mấy" in msg_l or "bao nhiêu" in msg_l or "ngưỡng" in msg_l)):
        # Chuẩn hoá số điều khoản theo metadata chunk (Điều 11 Khoản 5, Điều 12 Khoản 2)
        answer = re.sub(r"Điều 10\b", "Điều 11 Khoản 5, Điều 12 Khoản 2 (QĐ 22 - VB1)", answer)
        if "văn bản khác" not in answer.lower() and "xác nhận với giáo vụ" not in answer.lower():
            answer += "\n\n(Lưu ý theo Mục 8: Theo Niên giám chính thức VB1, điểm F là dưới 4.0 (thang 10); tuy nhiên có văn bản khác ghi dưới 5 phải học lại. Bạn nên xác nhận với giáo vụ khoa)."

    # 5b. Thi lại / kỳ thi phụ: theo VB1 sớm nhất 2 tuần sau thi chính
    if any(k in msg_l for k in ["thi lại", "thi lai", "thi phụ", "thi phu", "thi lần 2", "thi lan 2"]) and any(k in msg_l for k in ["khi nào", "thời gian", "bao giờ", "tổ chức"]):
        # Chuẩn hoá số điều khoản theo metadata chunk (Điều 11 Khoản 5 điểm đ)
        answer = re.sub(r"Điều 9(?:\s*(?:&|và)\s*Điều 10)?\b", "Điều 11 Khoản 5 điểm đ (QĐ 22 - VB1)", answer)
        if "văn bản khác" not in answer.lower() and "2 tuần" in answer.lower() and "đầu học kỳ mới" not in answer.lower():
            answer += "\n\n(Lưu ý theo Mục 8: Niên giám chính thức VB1 quy định kỳ thi phụ tổ chức sớm nhất 02 tuần sau kỳ thi chính; có văn bản khác ghi thi lần 2 vào đầu học kỳ mới. Bạn nên theo dõi thông báo của Phòng Đào tạo hoặc hỏi giáo vụ khoa)."

    # 5c. Loại bỏ từ cụt dở ở cuối dòng mới nếu bị ngắt do giới hạn token LLM (ví dụ: dòng mới chỉ có 1 từ như "Đi")
    answer = re.sub(r'\n{1,2}[A-Za-zÀ-ỹ]{1,4}\s*$', '', answer).strip()

    return answer


def check_deadline(now: Optional[datetime] = None, deadline: Optional[datetime] = None) -> bool:
    """
    Kiểm tra xem đã quá hạn đăng ký môn học hay chưa (Việc 3).
    - Trả về True nếu ĐÃ QUÁ HẠN (now > deadline).
    - Trả về False nếu CÒN HẠN.
    - Placeholder: nếu chưa cấu hình deadline cụ thể, mặc định trả về True để hướng dẫn quy trình trễ hạn.
    """
    if deadline is None:
        return True
    if now is None:
        now = datetime.now()
    return now > deadline


REGISTRATION_OVERDUE_RESPONSE = (
    "Thời hạn đăng ký môn học được thực hiện theo thông báo cụ thể của Phòng Đào tạo cho từng học kỳ.\n\n"
    "Nếu đã quá thời hạn đăng ký trực tuyến, bạn cần thực hiện như sau:\n"
    "1. Theo dõi thông báo về đợt học lại tiếp theo trên app ME.\n"
    "2. Tham gia Group Zalo để biết thêm chi tiết: https://zalo.me/g/ar6b85p9opfxctwhxwpd\n"
    "3. Liên hệ Văn phòng Khoa Công nghệ thông tin để được hỗ trợ:\n"
    "   - Số điện thoại: 02513.952.251\n"
    "   - Email: cntt@lhu.edu.vn\n"
    "   - Địa chỉ: Phòng B301 - B302, Cơ sở 1 (Số 10 Huỳnh Văn Nghệ, Biên Hòa, Đồng Nai)\n"
    "   - Giờ làm việc: Thứ Hai - Thứ Sáu (Sáng: 7h30 – 11h30 | Chiều: 13h00 – 16h30 / 17h00)\n\n"
    "[Văn bản quy định học vụ, Khoa Công nghệ thông tin – Hướng dẫn đăng ký học vụ]"
)

REGISTRATION_OVERDUE_SOURCES = [
    {
        "document_id": 9001,
        "title": "Quy chế đào tạo & Quy định học vụ",
        "section": "Hướng dẫn đăng ký học vụ",
        "chunk_index": 5,
        "score": 1.0,
        "snippet": "Nếu mẫu đơn đã quá thời hạn đăng ký, vui lòng theo dõi trên app ME về đợt học lại tiếp theo. Sinh viên tham gia Group Zalo https://zalo.me/g/ar6b85p9opfxctwhxwpd và liên hệ Khoa CNTT (02513.952.251, B301-B302 CS1, Số 10 Huỳnh Văn Nghệ, Biên Hòa, Đồng Nai).",
        "url": "http://cs.lhu.edu.vn",
        "so_hieu": "Quy chế đào tạo LHU"
    }
]


def check_and_build_center_context(
    message: str, db: Session
) -> tuple[bool, str, list[dict[str, Any]]]:
    """
    Kiểm tra truy vấn người dùng có liên quan đến Lịch học / Lịch thi của Trung tâm NNTH hay không.
    Nếu có, truy vấn lịch sắp tới từ database nội bộ và dựng chuỗi ngữ cảnh cùng thông tin nguồn.
    """
    msg_lower = message.lower()
    is_center_query = (
        any(k in msg_lower for k in [
            "lịch khai giảng", "lịch mở lớp", "khóa học ngoại ngữ", "khóa học tin học",
            "luyện thi vstep", "lớp vstep", "lớp tin học", "lịch thi tin học", "lịch thi ngoại ngữ",
            "lịch thi vstep", "lịch thi cntt", "kỳ thi tin học", "kỳ thi vstep", "kỳ thi ngoại ngữ",
            "lịch thi chứng chỉ", "lịch thi trung tâm", "trung tâm ngoại ngữ", "nnth"
        ]) or (
            ("lịch thi" in msg_lower or "lịch học" in msg_lower or "khai giảng" in msg_lower)
            and any(sub in msg_lower for sub in ["tin học", "ngoại ngữ", "tiếng anh", "vstep", "cntt", "chứng chỉ", "trung tâm", "nnth"])
        )
    )

    if not is_center_query:
        return False, "", []

    center_schedules = get_upcoming_schedules(db, from_today=True)
    center_exams = get_upcoming_exams(db, from_today=True)

    is_asking_exam = any(k in msg_lower for k in ["lịch thi", "kỳ thi", "ngày thi", "thi chứng chỉ", "hạn đăng ký", "lệ phí thi"])
    is_asking_course = any(k in msg_lower for k in ["khai giảng", "mở lớp", "khóa học", "lớp học", "luyện thi", "học phí"])

    center_lines = ["\n--- THÔNG TIN LỊCH TRUNG TÂM NGOẠI NGỮ - TIN HỌC (NNTH) LẠC HỒNG ---"]
    if (is_asking_course or not is_asking_exam) and center_schedules:
        center_lines.append("CÁC KHÓA HỌC / LỚP HỌC SẮP KHAI GIẢNG:")
        for s in center_schedules:
            center_lines.append(f"+ [{s['loai']}] {s['ten_khoa_hoc']}: Khai giảng {s['ngay_khai_giang_str']}, học {s['lich_hoc']}, hình thức {s['hinh_thuc']}, học phí {s['hoc_phi']} VNĐ, kỳ thi dự kiến {s['ky_thi_du_kien']}")
    if (is_asking_exam or not is_asking_course) and center_exams:
        center_lines.append("\nCÁC KỲ THI CHỨNG CHỈ SẮP DIỄN RA:")
        for ex in center_exams:
            status_dk = "Dự kiến" if ex["is_du_kien"] else "Chính thức"
            center_lines.append(f"+ [{ex['loai']} - {status_dk}] {ex['ten_ky_thi']}: Ngày thi {ex['ngay_thi_str']}, hạn đăng ký {ex['han_dang_ky']}, tình trạng: {ex['tinh_trang']}, lệ phí: {ex['le_phi_thi']} VNĐ")

    center_ctx = "\n".join(center_lines) + "\n"
    sources_data = [{
        "document_id": 9999,
        "title": "Trung tâm Ngoại ngữ - Tin học Lạc Hồng",
        "section": "Lịch học & Lịch thi",
        "chunk_index": 0,
        "score": 1.0,
        "snippet": center_ctx[:200],
        "url": "https://nnth.lhu.edu.vn",
        "so_hieu": "NNTH"
    }]

    return True, center_ctx, sources_data


def get_center_sync_note(db: Session) -> str:
    """Tạo ghi chú nguồn và thời gian đồng bộ dữ liệu NNTH gần nhất."""
    sync_info = get_last_sync_info(db)
    synced_time = sync_info.get("formatted_time", "chưa xác định")
    if sync_info.get("status") == "ERROR":
        return f"Hệ thống chưa lấy được lịch mới nhất từ trung tâm. Dữ liệu cập nhật lúc {synced_time}, xem lịch mới nhất tại nnth.lhu.edu.vn."
    return f"Dữ liệu cập nhật lúc {synced_time}, xem lịch mới nhất tại nnth.lhu.edu.vn."


def is_registration_deadline_query(message: str) -> bool:
    """Nhận diện câu hỏi về trễ hạn / hết hạn / quá hạn đăng ký môn học / học phần / học lại."""
    msg = (message or "").lower()
    has_register = any(k in msg for k in ["đăng ký", "dang ky", "đk môn", "dk mon", "đk học phần", "dk hoc phan", "học lại", "hoc lai", "học vét", "hoc vet", "môn học", "học phần"])
    has_overdue = any(k in msg for k in [
        "hết hạn", "het han", "quá hạn", "qua han", "trễ hạn", "tre han", "muộn", "muon",
        "hạn chót", "han chot", "thời hạn", "thoi han", "hết đợt", "het dot", "bỏ lỡ", "bo lo",
        "chưa kịp đăng ký", "chua kip dang ky", "không kịp đăng ký", "khong kip dang ky"
    ])
    return has_register and has_overdue


def build_verified_academic_data(grad_info: Optional[dict], ocr_info: Optional[dict] = None) -> dict:
    """Xây dựng khối dữ liệu học vụ xác thực từ graduation-check và OCR.
    - Gộp môn trùng khi hợp nhất dữ liệu hệ thống và OCR: chuẩn hoá tên và mã môn để nhận ra cùng một môn.
    - Nếu trùng, mỗi môn chỉ hiện một dòng; ghi rõ nguồn điểm (hệ thống hoặc OCR) và nếu hai điểm khác nhau thì hiện cả hai kèm ghi chú.
    - Tách nhóm: 'môn chưa đạt (điểm < 4.0)' cần học lại/thi lại, và 'môn bị đánh dấu đỏ nhưng điểm >= 4.0' cần sinh viên xác nhận với giáo vụ, không khuyên học lại.
    - Lấy thông tin chứng chỉ từ grad_info.
    """
    if not grad_info:
        return {}

    stu = grad_info.get("student") or {}
    student_name = stu.get("full_name", "")
    student_code = stu.get("student_code", "")

    total_credits_passed = grad_info.get("total_credits_passed", grad_info.get("total_credits_earned", 0))
    required_credits = grad_info.get("required_credits", grad_info.get("total_credits_required", settings.REQUIRED_CREDITS))
    credits_missing = grad_info.get("credits_missing", max(0, required_credits - total_credits_passed))
    total_credits_failed = grad_info.get("total_credits_failed", 0)
    notes = grad_info.get("notes", "Chưa đủ điều kiện tốt nghiệp")
    certificates = grad_info.get("certificates", {})

    # 1. Hợp nhất và gộp môn trùng giữa hệ thống và OCR
    system_failed = grad_info.get("failed_courses", [])
    ocr_structured = ocr_info.get("failed_courses_structured", []) if ocr_info else []

    merged_courses = []
    matched_ocr_indices = set()

    for s in system_failed:
        s_code = s.get("code", "")
        s_name = s.get("name", "")
        s_norm_code = normalize_subject_code(s_code)
        s_norm_name = normalize_subject_name(s_name)
        s_grade = float(s["grade"]) if s.get("grade") is not None else None

        # Tìm môn tương ứng trong OCR
        matched_ocr = None
        for idx, o in enumerate(ocr_structured):
            if idx in matched_ocr_indices:
                continue
            o_code = o.get("code", "")
            o_name = o.get("name", "")
            o_norm_code = normalize_subject_code(o_code)
            o_norm_name = normalize_subject_name(o_name)

            # Khớp theo mã môn (nếu cả 2 đều có mã)
            is_match = False
            if s_norm_code and o_norm_code and s_norm_code == o_norm_code:
                is_match = True
            # Khớp theo tên môn đã chuẩn hóa (bỏ dấu, hạ chữ thường, bỏ khoảng trắng thừa)
            elif s_norm_name and o_norm_name and s_norm_name == o_norm_name:
                is_match = True
            elif s_norm_name and o_norm_name and (s_norm_name in o_norm_name or o_norm_name in s_norm_name) and len(min(s_norm_name, o_norm_name, key=len)) >= 10:
                is_match = True

            if is_match:
                matched_ocr = o
                matched_ocr_indices.add(idx)
                break

        if matched_ocr:
            ocr_g = float(matched_ocr["grade"]) if matched_ocr.get("grade") is not None else None
            is_diff = bool(s_grade is not None and ocr_g is not None and abs(s_grade - ocr_g) >= 0.05)
            merged_courses.append({
                "code": s_code or matched_ocr.get("code", ""),
                "name": s_name or matched_ocr.get("name", ""),
                "credits": s.get("credits", 0) or matched_ocr.get("credits", 0),
                "system_grade": s_grade,
                "ocr_grade": ocr_g,
                "grade": s_grade if s_grade is not None else ocr_g,
                "is_red_marked": bool(matched_ocr.get("is_red_marked")),
                "filter_reason": matched_ocr.get("filter_reason", "") or s.get("filter_reason", ""),
                "cam_thi": matched_ocr.get("cam_thi") if matched_ocr.get("cam_thi") is not None else s.get("cam_thi"),
                "vang_qua_20": matched_ocr.get("vang_qua_20") if matched_ocr.get("vang_qua_20") is not None else s.get("vang_qua_20"),
                "duoc_thi_lai": matched_ocr.get("duoc_thi_lai") if matched_ocr.get("duoc_thi_lai") is not None else s.get("duoc_thi_lai"),
                "diem_thanh_phan": matched_ocr.get("diem_thanh_phan") or s.get("diem_thanh_phan") or matched_ocr.get("diem_qua_trinh"),
                "sources": ["hệ thống", "OCR"],
                "is_differing_grades": is_diff
            })
        else:
            merged_courses.append({
                "code": s_code,
                "name": s_name,
                "credits": s.get("credits", 0),
                "system_grade": s_grade,
                "ocr_grade": None,
                "grade": s_grade,
                "is_red_marked": False,
                "filter_reason": s.get("filter_reason", ""),
                "cam_thi": s.get("cam_thi"),
                "vang_qua_20": s.get("vang_qua_20"),
                "duoc_thi_lai": s.get("duoc_thi_lai"),
                "diem_thanh_phan": s.get("diem_thanh_phan") or s.get("diem_qua_trinh"),
                "sources": ["hệ thống"],
                "is_differing_grades": False
            })

    # Thêm các môn OCR chưa được khớp với hệ thống
    for idx, o in enumerate(ocr_structured):
        if idx in matched_ocr_indices:
            continue
        ocr_g = float(o["grade"]) if o.get("grade") is not None else None
        merged_courses.append({
            "code": o.get("code", ""),
            "name": o.get("name", ""),
            "credits": o.get("credits", 0),
            "system_grade": None,
            "ocr_grade": ocr_g,
            "grade": ocr_g,
            "is_red_marked": bool(o.get("is_red_marked")),
            "filter_reason": o.get("filter_reason", ""),
            "cam_thi": o.get("cam_thi"),
            "vang_qua_20": o.get("vang_qua_20"),
            "duoc_thi_lai": o.get("duoc_thi_lai"),
            "diem_thanh_phan": o.get("diem_thanh_phan") or o.get("diem_qua_trinh"),
            "sources": ["OCR"],
            "is_differing_grades": False
        })

    # 2. Tách nhóm:
    # Nhóm 1: "môn chưa đạt (điểm < 4.0)" cần học lại/thi lại
    # Nhóm 2: "môn bị đánh dấu đỏ nhưng điểm >= 4.0" cần sinh viên xác nhận với giáo vụ, không khuyên học lại
    failed_courses_under_4 = []
    red_marked_courses_ge_4 = []

    for m in merged_courses:
        has_grade_under_4 = (
            (m["system_grade"] is not None and m["system_grade"] < 4.0) or
            (m["ocr_grade"] is not None and m["ocr_grade"] < 4.0) or
            (m["grade"] is not None and m["grade"] < 4.0)
        )
        if has_grade_under_4:
            failed_courses_under_4.append(m)
        elif m.get("is_red_marked") or any(k in str(m.get("filter_reason", "")).lower() for k in ["đỏ", "do", "red"]):
            red_marked_courses_ge_4.append(m)

    # 3. Danh sách môn bắt buộc theo CTĐT chưa học (loại các môn đã nằm trong nhóm 1 và nhóm 2)
    known_course_keys = set()
    for item in failed_courses_under_4 + red_marked_courses_ge_4:
        if item.get("code"):
            known_course_keys.add(normalize_subject_code(item["code"]))
        if item.get("name"):
            known_course_keys.add(normalize_subject_name(item["name"]))

    unstudied_courses = []
    for m in grad_info.get("missing_required_courses", []):
        m_code = normalize_subject_code(m.get("code", ""))
        m_name = normalize_subject_name(m.get("name", ""))
        if (m_code and m_code in known_course_keys) or (m_name and m_name in known_course_keys):
            continue
        unstudied_courses.append({
            "code": m.get("code", ""),
            "name": m.get("name", ""),
            "credits": m.get("credits", 0)
        })

    allowed_credit_numbers = {
        total_credits_passed,
        required_credits,
        credits_missing,
        total_credits_failed,
    }
    for c in failed_courses_under_4 + red_marked_courses_ge_4 + unstudied_courses:
        if c.get("credits"):
            allowed_credit_numbers.add(c["credits"])

    return {
        "student_name": student_name,
        "student_code": student_code,
        "total_credits_passed": total_credits_passed,
        "required_credits": required_credits,
        "credits_missing": credits_missing,
        "total_credits_failed": total_credits_failed,
        "failed_courses_under_4": failed_courses_under_4,
        "red_marked_courses_ge_4": red_marked_courses_ge_4,
        "failed_courses": failed_courses_under_4,  # Để tương thích ngược với các logic cũ
        "unstudied_courses": unstudied_courses,
        "certificates": certificates,
        "allowed_credit_numbers": allowed_credit_numbers,
        "notes": notes,
        "eligible": grad_info.get("eligible", False)
    }


def generate_verified_academic_template(verified: dict, user_message: str = "") -> str:
    """Tạo câu trả lời mẫu chính xác từ dữ liệu xác thực:
    - Gộp môn trùng khi hợp nhất dữ liệu hệ thống và OCR thành một dòng, ghi rõ nguồn điểm và chênh lệch (nếu có).
    - Tách nhóm: 'môn chưa đạt (điểm < 4.0)' cần học lại/thi lại, và 'môn bị đánh dấu đỏ nhưng điểm >= 4.0' cần sinh viên xác nhận với giáo vụ, không khuyên học lại.
    - Phần chứng chỉ: lấy trạng thái thật từ bảng chứng chỉ ('Đã có' hoặc 'Chưa có dữ liệu, cần nộp', bỏ ví dụ TOEIC/B1).
    """
    if not verified:
        return "Xin lỗi, hiện tại hệ thống chưa có đủ thông tin học vụ của bạn để tư vấn chi tiết."

    msg_l = (user_message or "").lower()
    is_failed_query = (
        any(k in msg_l for k in ["rớt môn nào", "nợ môn nào", "môn rớt", "môn nợ"])
        and not any(k in msg_l for k in ["tốt nghiệp", "cần làm gì để tốt nghiệp", "tiến độ tốt nghiệp", "xét tốt nghiệp"])
    )

    failed_courses_under_4 = verified.get("failed_courses_under_4", verified.get("failed_courses", []))
    red_marked_courses_ge_4 = verified.get("red_marked_courses_ge_4", [])
    unstudied_courses = verified.get("unstudied_courses", [])
    credits_passed = verified.get("total_credits_passed", 0)
    credits_required = verified.get("required_credits", settings.REQUIRED_CREDITS)
    credits_missing = verified.get("credits_missing", 0)
    certs = verified.get("certificates", {})

    # Trường hợp câu hỏi hỏi về môn rớt: "tôi rớt môn nào, cần làm gì?"
    if is_failed_query:
        if not failed_courses_under_4 and not red_marked_courses_ge_4:
            return "Theo hồ sơ học vụ hiện tại, bạn không có môn nào bị rớt hoặc nợ điểm (tất cả các môn đã học đều đạt)."

        lines = ["Danh sách các môn học cần lưu ý của bạn:"]

        if failed_courses_under_4:
            lines.append(f"\n1. Môn chưa đạt (điểm < 4.0) cần học lại / thi lại ({len(failed_courses_under_4)} môn):")
            for f in failed_courses_under_4:
                c_line = format_course_grade_source(f)
                guidance = format_failed_course_guidance(f)
                lines.append(f"- {c_line}. Hướng dẫn: {guidance}.")
            lines.append(f"\n{REGISTRATION_LINKS_NOTE}")

        if red_marked_courses_ge_4:
            lines.append(f"\n2. Môn bị đánh dấu đỏ trên bảng điểm (điểm ≥ 4.0) cần xác nhận với giáo vụ ({len(red_marked_courses_ge_4)} môn):")
            for r in red_marked_courses_ge_4:
                c_line = format_course_grade_source(r)
                lines.append(f"- {c_line} (Vùng điểm bị đánh dấu đỏ). Hướng dẫn: Điểm tổng kết đạt (≥ 4.0), sinh viên cần liên hệ Văn phòng Giáo vụ / Khoa để kiểm tra và xác nhận lại tình trạng học phần, không cần đăng ký học lại.")

        return "\n".join(lines).strip()

    # Trường hợp câu hỏi hỏi về tốt nghiệp: "tôi cần làm gì để tốt nghiệp?"
    lines = []
    lines.append("Để xét tốt nghiệp, bạn cần hoàn thành các điều kiện sau:")
    lines.append("\n1. Tiến độ tín chỉ:")
    if credits_passed >= credits_required and credits_missing == 0:
        lines.append(f"- Bạn đã tích lũy đủ {credits_passed}/{credits_required} tín chỉ theo yêu cầu.")
    else:
        lines.append(f"- Tín chỉ tích lũy hiện tại: {credits_passed}/{credits_required} tín chỉ (chưa đủ).")
        lines.append(f"- Số tín chỉ còn thiếu cần tích lũy thêm: {credits_missing} tín chỉ.")

    lines.append("\n2. Môn chưa đạt (điểm < 4.0) cần học lại / thi lại:")
    if failed_courses_under_4:
        for f in failed_courses_under_4:
            c_line = format_course_grade_source(f)
            guidance = format_failed_course_guidance(f)
            lines.append(f"- {c_line} - {guidance}.")
        lines.append(f"- {REGISTRATION_LINKS_NOTE}")
    else:
        lines.append("- Bạn không có môn nào bị rớt hoặc nợ điểm (điểm < 4.0).")

    if red_marked_courses_ge_4:
        lines.append("\n3. Môn bị đánh dấu đỏ trên bảng điểm (điểm ≥ 4.0) cần xác nhận với giáo vụ:")
        for r in red_marked_courses_ge_4:
            c_line = format_course_grade_source(r)
            lines.append(f"- {c_line} (Vùng điểm bị đánh dấu đỏ) - Điểm tổng kết đạt (≥ 4.0), sinh viên cần liên hệ Văn phòng Giáo vụ / Khoa để kiểm tra và xác nhận lại tình trạng học phần, không cần đăng ký học lại.")

    sec_idx = 4 if red_marked_courses_ge_4 else 3
    lines.append(f"\n{sec_idx}. Môn học bắt buộc theo chương trình đào tạo cần đăng ký học:")
    if unstudied_courses:
        for m in unstudied_courses:
            cr_str = f" ({m.get('credits', 0)} tín chỉ)" if m.get('credits') else ""
            c_str = f" ({m['code']})" if m.get('code') else ""
            lines.append(f"- {m['name']}{c_str}{cr_str}: Cần đăng ký học trong các học kỳ tiếp theo.")
    else:
        lines.append("- Đã hoàn thành đầy đủ các môn học bắt buộc theo chương trình đào tạo.")

    sec_idx += 1
    lines.append(f"\n{sec_idx}. Chuẩn đầu ra và chứng chỉ theo quy định:")
    eng_status = "Đã có" if certs.get("has_english") else "Chưa có dữ liệu, cần nộp"
    it_status = "Đã có" if certs.get("has_it") else "Chưa có dữ liệu, cần nộp"
    lines.append(f"- Chứng chỉ Ngoại ngữ: {eng_status}.")
    lines.append(f"- Chứng chỉ Tin học: {it_status}.")

    lines.append("\nHướng dẫn tiếp theo:")
    if failed_courses_under_4 or unstudied_courses:
        lines.append("- Đăng ký học lại/thi lại các môn chưa đạt (điểm < 4.0) và đăng ký các môn bắt buộc còn thiếu trong các đợt đăng ký học phần.")
    if red_marked_courses_ge_4:
        lines.append("- Liên hệ Văn phòng Giáo vụ / Khoa để kiểm tra và xác nhận tình trạng các môn bị đánh dấu đỏ.")
    if not certs.get("has_english") or not certs.get("has_it"):
        lines.append("- Nộp đầy đủ chứng chỉ chuẩn đầu ra trước các đợt xét tốt nghiệp theo thông báo của Phòng Đào tạo.")
    else:
        lines.append("- Theo dõi các thông báo của Phòng Đào tạo về các đợt xét tốt nghiệp.")

    return "\n".join(lines).strip()


def validate_academic_answer(answer: str, verified: dict) -> bool:
    """Kiểm tra câu trả lời của LLM:
    - Không được dùng 'đổi điểm', 'giấy chứng nhận', 'đã đăng ký học'
    - Không được dùng từ 'đủ' khi tín chỉ tích lũy < yêu cầu (ví dụ: 'đã tích lũy đủ 17/120')
    - Môn nằm trong danh sách rớt không được xuất hiện trong nhóm 'chưa học' hoặc 'cần đăng ký học'
    - Không được sai số tín chỉ ngoài allowed_credit_numbers
    - Không được bịa môn GDQP / GDTC nếu không có trong dữ liệu xác thực
    - Không được bảo 'học lại' môn chưa từng học
    """
    if not verified:
        return True

    ans_lower = answer.lower()

    # 1. Cấm dùng các cụm từ sai lệch
    forbidden_phrases = [
        "đổi điểm", "doi diem",
        "giấy chứng nhận", "giay chung nhan",
        "đã đăng ký học", "da dang ky hoc"
    ]
    for p in forbidden_phrases:
        if p in ans_lower:
            logger.warning("Academic answer validation failed: contains '%s'", p)
            return False

    # 2. Không dùng từ "đủ" khi tín chỉ tích luỹ < yêu cầu
    credits_passed = verified.get("total_credits_passed", 0)
    credits_required = verified.get("required_credits", settings.REQUIRED_CREDITS)
    if credits_passed < credits_required:
        if re.search(r"(?:tích lũy|đạt|có)\s+đủ\s+\d+", ans_lower) or re.search(r"đủ\s+\d+/\d+", ans_lower) or re.search(r"đủ\s+\d+\s*(?:tín chỉ|tc)", ans_lower):
            logger.warning("Academic answer validation failed: says 'đủ' while credits < required (%d < %d)", credits_passed, credits_required)
            return False

    # 3. Môn nằm trong danh sách rớt/đỏ không được xuất hiện trong nhóm 'chưa học/cần đăng ký học'
    all_not_passed = verified.get("failed_courses_under_4", []) + verified.get("red_marked_courses_ge_4", [])
    failed_names = [f["name"].lower() for f in all_not_passed if f.get("name")]
    failed_codes = [f["code"].lower() for f in all_not_passed if f.get("code")]
    unstudied_blocks = re.findall(r"(?:chưa học|cần đăng ký học|đăng ký học)[^.\n]*", ans_lower)
    for blk in unstudied_blocks:
        for fname in failed_names:
            if fname in blk:
                logger.warning("Academic answer validation failed: failed course '%s' found in unstudied block '%s'", fname, blk)
                return False
        for fcode in failed_codes:
            if fcode in blk:
                logger.warning("Academic answer validation failed: failed course code '%s' found in unstudied block '%s'", fcode, blk)
                return False

    # 4. Kiểm tra số tín chỉ
    matches = re.findall(r"(\d+)\s*(?:tín chỉ|tc\b)", ans_lower)
    for m in matches:
        val = int(m)
        if val not in verified.get("allowed_credit_numbers", set()):
            logger.warning("Academic answer validation failed: credit number %d not in allowed credits %s", val, verified.get("allowed_credit_numbers"))
            return False

    # 5. Kiểm tra môn bịa GDQP / GDTC
    known_course_texts = " ".join([
        c.get("name", "").lower() + " " + c.get("code", "").lower()
        for c in verified.get("failed_courses_under_4", []) + verified.get("red_marked_courses_ge_4", []) + verified.get("unstudied_courses", [])
    ])
    if ("giáo dục quốc phòng" in ans_lower or "gdqp" in ans_lower) and "giáo dục quốc phòng" not in known_course_texts:
        logger.warning("Academic answer validation failed: fabricated course GDQP found")
        return False
    if ("giáo dục thể chất" in ans_lower or "gdtc" in ans_lower) and "giáo dục thể chất" not in known_course_texts:
        logger.warning("Academic answer validation failed: fabricated course GDTC found")
        return False

    # 6. Kiểm tra môn đỏ (>= 4.0) không được khuyên học lại
    for r in verified.get("red_marked_courses_ge_4", []):
        r_name = r.get("name", "").lower()
        r_code = r.get("code", "").lower()
        if r_name and (f"học lại {r_name}" in ans_lower or f"thi lại {r_name}" in ans_lower):
            logger.warning("Academic answer validation failed: advises retaking red-marked course '%s'", r_name)
            return False
        if r_code and (f"học lại {r_code}" in ans_lower or f"thi lại {r_code}" in ans_lower):
            logger.warning("Academic answer validation failed: advises retaking red-marked course code '%s'", r_code)
            return False

    # 7. Kiểm tra bảo "học lại" môn chưa từng học
    for u in verified.get("unstudied_courses", []):
        u_name = u["name"].lower()
        if f"học lại {u_name}" in ans_lower or f"học lại môn {u_name}" in ans_lower:
            logger.warning("Academic answer validation failed: instructed student to re-take unstudied course '%s'", u_name)
            return False

    return True


def _build_ollama_options() -> dict:
    """Tạo dictionary options cho Ollama, hỗ trợ cấu hình num_thread, num_batch và num_ctx."""
    opts = {
        "temperature": 0.0,
        "top_p": 0.9,
        "num_predict": settings.OLLAMA_NUM_PREDICT,
        "num_ctx": settings.OLLAMA_NUM_CTX,
    }
    if getattr(settings, "OLLAMA_NUM_THREAD", None):
        opts["num_thread"] = settings.OLLAMA_NUM_THREAD
    if getattr(settings, "OLLAMA_NUM_BATCH", None):
        opts["num_batch"] = settings.OLLAMA_NUM_BATCH
    return opts

def _call_ollama(messages: list, timeout: int) -> str:
    """Gọi Ollama và trả về nội dung trả lời. Ném HTTPException nếu lỗi."""
    try:
        res = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.LLM_MODEL,
                "messages": messages,
                "stream": False,
                "keep_alive": settings.OLLAMA_KEEP_ALIVE,  # Giữ model trong RAM tránh nạp lại
                "options": _build_ollama_options(),
            },
            timeout=timeout,
        )
        res.raise_for_status()
        data = res.json()
        prompt_eval = data.get("prompt_eval_count")
        eval_count = data.get("eval_count")
        done_reason = data.get("done_reason")
        logger.info(
            "Ollama response metrics: prompt_eval_count=%s, eval_count=%s, done_reason=%s",
            prompt_eval, eval_count, done_reason
        )
        if done_reason == "length":
            logger.warning(
                "Ollama hit token limit (done_reason='length'): eval_count=%s, prompt_eval_count=%s. Response might be truncated!",
                eval_count, prompt_eval
            )
        return data["message"]["content"]
    except requests.exceptions.Timeout:
        logger.exception("Ollama timeout in chat")
        raise HTTPException(status_code=504, detail="Hệ thống đang quá tải, vui lòng thử lại sau.")
    except requests.exceptions.ConnectionError:
        logger.exception("Ollama connection error in chat")
        raise HTTPException(status_code=503, detail="Hệ thống AI đang bảo trì, vui lòng thử lại sau.")
    except Exception:
        logger.exception("Ollama unknown error in chat")
        raise HTTPException(status_code=500, detail="Lỗi hệ thống nội bộ.")


@router.post("")
def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]

    # ── 1. Kiểm tra injection TRƯỚC khi làm bất cứ điều gì ──────────────────
    if is_injection(req.message):
        # Vẫn cần session để lưu log
        session_id = req.session_id
        if not session_id:
            title = req.message[:40] + ("..." if len(req.message) > 40 else "")
            session_id = db.execute(
                text("INSERT INTO chat_sessions (user_id, title, updated_at) OUTPUT INSERTED.id VALUES (:uid, :title, SYSDATETIME())"),
                {"uid": user_id, "title": title},
            ).scalar()
            db.commit()
        else:
            sess = db.execute(
                text("SELECT id FROM chat_sessions WHERE id = :sid AND user_id = :uid"),
                {"sid": session_id, "uid": user_id},
            ).fetchone()
            if not sess:
                raise HTTPException(status_code=403, detail="Cuộc trò chuyện không tồn tại hoặc không có quyền truy cập")
            db.execute(text("UPDATE chat_sessions SET updated_at = SYSDATETIME() WHERE id = :sid"), {"sid": session_id})
            db.commit()

        # Lưu câu hỏi + câu từ chối
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"),
            {"sid": session_id, "content": req.message},
        )
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"),
            {"sid": session_id, "content": REFUSAL_RESPONSE, "sources": "[]"},
        )
        db.commit()
        logger.info("Injection detected, returning REFUSAL_RESPONSE")
        return {"session_id": session_id, "answer": REFUSAL_RESPONSE, "sources": []}

    # ── 2. Quản lý Session ────────────────────────────────────────────────────
    session_id = req.session_id
    if not session_id:
        title = req.message[:40] + ("..." if len(req.message) > 40 else "")
        session_id = db.execute(
            text("INSERT INTO chat_sessions (user_id, title, updated_at) OUTPUT INSERTED.id VALUES (:uid, :title, SYSDATETIME())"),
            {"uid": user_id, "title": title},
        ).scalar()
        db.commit()
    else:
        sess = db.execute(
            text("SELECT id FROM chat_sessions WHERE id = :sid AND user_id = :uid"),
            {"sid": session_id, "uid": user_id},
        ).fetchone()
        if not sess:
            raise HTTPException(status_code=403, detail="Cuộc trò chuyện không tồn tại hoặc không có quyền truy cập")
        db.execute(text("UPDATE chat_sessions SET updated_at = SYSDATETIME() WHERE id = :sid"), {"sid": session_id})
        db.commit()

    # ── 3. Early detection: khoa khác & ngoài phạm vi ────────────────────────
    msg_lower = req.message.lower()
    guard = check_guardrails(req.message)
    if guard:
        answer, _ = guard
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"),
            {"sid": session_id, "content": req.message},
        )
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"),
            {"sid": session_id, "content": answer, "sources": "[]"},
        )
        db.commit()
        return {"session_id": session_id, "answer": answer, "sources": []}

    # ── 3.5. Nhận diện câu chào hỏi và xã giao đơn giản (không gọi LLM/RAG) ─────
    smalltalk_ans = get_smalltalk_response(req.message)
    if smalltalk_ans:
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"),
            {"sid": session_id, "content": req.message},
        )
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"),
            {"sid": session_id, "content": smalltalk_ans, "sources": "[]"},
        )
        db.commit()
        return {"session_id": session_id, "answer": smalltalk_ans, "sources": []}

    # ── 3.6. Xử lý câu hỏi trễ hạn / hết hạn đăng ký môn học (Việc 3) ────────────
    if is_registration_deadline_query(req.message):
        is_overdue = check_deadline()
        if is_overdue:
            db.execute(
                text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"),
                {"sid": session_id, "content": req.message},
            )
            db.execute(
                text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"),
                {"sid": session_id, "content": REGISTRATION_OVERDUE_RESPONSE, "sources": json.dumps(REGISTRATION_OVERDUE_SOURCES, ensure_ascii=False)},
            )
            db.commit()
            return {"session_id": session_id, "answer": REGISTRATION_OVERDUE_RESPONSE, "sources": REGISTRATION_OVERDUE_SOURCES}

    # ── 4. Retrieval ──────────────────────────────────────────────────────────
    is_convo = req.message.strip().lower() in _CONVO_QUERIES
    query_for_embedding = req.message
    chunks = [] if is_convo else search_chunks(db, query_for_embedding)

    max_score = max((c["score"] for c in chunks), default=0.0)

    academic_kws = ["quy chế", "quy định", "thông báo", "học vụ", "niên giám", "buộc thôi học", "cảnh báo", "học bổng", "nghỉ học", "bảo lưu", "tốt nghiệp", "tín chỉ", "học phần", "chứng chỉ", "tiếng anh", "ngoại ngữ", "tin học", "lệ phí", "hồ sơ", "học kỳ", "thi lại", "thi phụ", "cấm thi", "học lại", "học vét"]
    has_acad_kw = any(kw in msg_lower for kw in academic_kws)

    # Nhận diện câu hỏi liên quan đến hồ sơ cá nhân / điểm / môn rớt / tốt nghiệp
    personal_explicit = [
        "điểm của tôi", "điểm của em", "bảng điểm của tôi", "bảng điểm của em",
        "tôi đã tích lũy bao nhiêu", "em đã tích lũy bao nhiêu",
        "tôi có bị rớt môn", "em có bị rớt môn", "danh sách môn rớt của tôi",
        "tôi đã đủ điều kiện tốt nghiệp chưa", "em đã đủ điều kiện tốt nghiệp chưa",
        "kiểm tra tốt nghiệp cho tôi", "xét tốt nghiệp của tôi",
        "tôi rớt môn nào", "em rớt môn nào", "tôi nợ môn nào", "em nợ môn nào",
        "tôi rớt môn", "em rớt môn", "hồ sơ của tôi", "hồ sơ của em",
        "môn nào tôi", "môn nào em", "tôi đang bị", "em đang bị", "tôi bị f", "em bị f",
        "tôi còn thiếu", "em còn thiếu", "tôi thiếu bao nhiêu", "em thiếu bao nhiêu",
        "thiếu bao nhiêu tín chỉ", "còn thiếu bao nhiêu tín chỉ"
    ]
    is_personal_query = any(p in msg_lower for p in personal_explicit) or (
        any(kw in msg_lower for kw in ["rớt", "nợ", "chưa đạt", "không đạt", "điểm", "bảng điểm", "tốt nghiệp", "tín chỉ", "bị f", "điểm f"]) and
        any(sub in msg_lower for sub in ["tôi", "em", "mình", "của tôi", "của em"])
    )
    # Phân biệt câu hỏi quy chế chung (ví dụ: "cách tính điểm khi học lại như thế nào?", "điều kiện tốt nghiệp là gì?")
    is_general_reg = (
        any(w in msg_lower for w in ["như thế nào", "thế nào", "mấy điểm", "là mấy", "cách tính", "quy định", "là gì"]) and
        not any(sub in msg_lower for sub in ["của tôi", "của em", "của mình", "bảng điểm của tôi", "bảng điểm của em", "tôi đã", "em đã", "cho tôi", "cho em", "tôi còn", "em còn", "tôi đang", "em đang", "môn nào tôi", "môn nào em"])
    )
    if is_general_reg:
        is_personal_query = False

    if is_personal_query:
        intent = "personal"
    elif has_acad_kw or max_score >= settings.MIN_SCORE_THRESHOLD:
        intent = "general"
    elif is_convo:
        intent = "convo"
    else:
        intent = "off_topic"

    if intent == "off_topic":
        answer = REFUSAL_RESPONSE
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"),
            {"sid": session_id, "content": req.message},
        )
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"),
            {"sid": session_id, "content": answer, "sources": "[]"},
        )
        db.commit()
        return {"session_id": session_id, "answer": answer, "sources": []}

    if intent == "personal":
        # Tích hợp kết quả OCR của chính sinh viên + dữ liệu graduation-check + RAG quy chế học vụ
        student_ctx, ocr_info, grad_info = get_student_academic_and_ocr_context(db, user_id)
        sources_data = []

        # Tìm kiếm các đoạn quy chế học vụ liên quan (học lại môn rớt, điểm F, đăng ký học kỳ hè, điều kiện tốt nghiệp)
        academic_rag_query = req.message + " quy định học lại điểm F đăng ký học kỳ hè tốt nghiệp"
        academic_rag_chunks = search_chunks(db, academic_rag_query)
        rag_lines = []
        seen_sources = []
        for c in academic_rag_chunks:
            title = c["title"]
            section = c.get("section")
            so_hieu = c.get("so_hieu")
            url = c.get("url")

            src_label_parts = [title]
            if section:
                src_label_parts.append(f"Mục {section}")
            if so_hieu:
                src_label_parts.append(so_hieu)
            src_str = " - ".join(src_label_parts)
            if url:
                src_str += f" ({url})"
            if src_str not in seen_sources:
                seen_sources.append(src_str)

            sources_data.append({
                "document_id": c["document_id"],
                "title": title,
                "section": section,
                "chunk_index": c["chunk_index"],
                "score": c["score"],
                "snippet": c["content"][:200],
                "url": url,
                "so_hieu": so_hieu
            })
            chunk_c = c["content"]
            if len(chunk_c) > settings.MAX_CHUNK_CHARS:
                chunk_c = chunk_c[:settings.MAX_CHUNK_CHARS] + "..."
            rag_lines.append(f"\n--- Quy chế: {title} (Mục {section or 'Chung'}) ---\n{chunk_c}\n")

        if ocr_info:
            sources_data.insert(0, {
                "document_id": 9998,
                "title": f"Bảng điểm OCR ({ocr_info['filename']})",
                "section": "Kết quả trích xuất điểm",
                "chunk_index": 0,
                "score": 1.0,
                "snippet": f"Đọc được {ocr_info['total_subjects']} môn, gồm {ocr_info['failed_count']} môn chưa đạt.",
                "url": None,
                "so_hieu": "OCR"
            })

        full_context_parts = []
        if student_ctx:
            full_context_parts.append(student_ctx)
        if rag_lines:
            full_context_parts.append("".join(rag_lines))
        combined_context = "\n\n".join(full_context_parts)

        # Xây dựng danh sách tin nhắn cho LLM
        history = db.execute(
            text("SELECT role, content FROM chat_messages WHERE session_id = :sid ORDER BY id DESC OFFSET 0 ROWS FETCH NEXT 6 ROWS ONLY"),
            {"sid": session_id},
        ).fetchall()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in reversed(history):
            if msg.role == "user" and msg.content == req.message:
                continue
            messages.append({"role": msg.role, "content": msg.content})

        # 1. Phần số liệu và danh sách môn luôn do code dựng bằng template từ graduation-check + OCR
        verified = build_verified_academic_data(grad_info, ocr_info)
        template_text = generate_verified_academic_template(verified, req.message)

        # 2. LLM chỉ được dùng để diễn giải phần quy chế từ RAG (ngắn, có nguồn), nối sau phần template
        llm_regulation_note = ""
        if rag_lines or student_ctx:
            student_context_prefix = f"Thông tin học vụ và bảng điểm của sinh viên:\n{student_ctx}\n\n" if student_ctx else ""
            rag_part = f"Dựa vào các trích đoạn quy chế sau:\n{''.join(rag_lines)[:1500]}\n\n" if rag_lines else ""
            prompt_regulation = (
                f"{student_context_prefix}"
                f"{rag_part}"
                f"Hãy tóm tắt thật ngắn gọn (1-2 câu) quy định về thời gian nộp hồ sơ hoặc thủ tục xét tốt nghiệp.\n"
                f"Quy tắc tuyệt đối:\n"
                f"- KHÔNG được nhắc bất kỳ con số tín chỉ nào.\n"
                f"- KHÔNG được nhắc tên bất kỳ môn học nào.\n"
                f"- KHÔNG dùng các cụm từ: 'đã đăng ký học', 'đổi điểm', 'giấy chứng nhận'.\n"
                f"{LANG_REMINDER}"
            )
            try:
                exp_messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_regulation}
                ]
                raw_note = _call_ollama(exp_messages, settings.OLLAMA_TIMEOUT_CHAT)
                raw_note = clean_source_text(raw_note).replace("<ngu_canh>", "").replace("</ngu_canh>", "").strip()
                raw_note = re.sub(r'[ \t]+', ' ', raw_note).strip()
                raw_note = re.sub(r'\n{3,}', '\n\n', raw_note)

                # Kiểm tra nghiêm ngặt: nếu phần LLM chứa số tín chỉ, tên môn, hay cụm cấm -> bỏ phần LLM, chỉ giữ template
                contains_credits = bool(re.search(r"\d+\s*(?:tín chỉ|tc\b)", raw_note, re.IGNORECASE))
                contains_forbidden = any(p in raw_note.lower() for p in ["đã đăng ký học", "da dang ky hoc", "giấy chứng nhận", "giay chung nhan", "đổi điểm", "doi diem"])
                contains_courses = False
                for c in verified.get("failed_courses_under_4", []) + verified.get("red_marked_courses_ge_4", []) + verified.get("unstudied_courses", []):
                    if c.get("name") and c["name"].lower() in raw_note.lower():
                        contains_courses = True
                        break
                    if c.get("code") and c["code"].lower() in raw_note.lower():
                        contains_courses = True
                        break

                if not contains_credits and not contains_forbidden and not contains_courses and len(raw_note) > 10:
                    llm_regulation_note = raw_note
                else:
                    logger.info("Bỏ phần LLM do chứa số liệu/tên môn hoặc cụm từ cấm, chỉ giữ template.")
            except Exception as e:
                logger.warning("Lỗi gọi LLM diễn giải quy chế: %s", e)

        if llm_regulation_note:
            answer = f"{template_text}\n\nThông tin quy chế bổ sung:\n{llm_regulation_note}"
        else:
            answer = template_text

        # Lưu tin nhắn người dùng và câu trả lời vào DB
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"),
            {"sid": session_id, "content": req.message},
        )
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"),
            {"sid": session_id, "content": answer, "sources": json.dumps(sources_data, ensure_ascii=False)},
        )
        db.commit()
        return {"session_id": session_id, "answer": answer, "sources": sources_data}

    sources_data = []
    context_text = ""
    seen_sources = []
    seen_keys = set()
    for c in chunks:
        title = c["title"]
        section = c.get("section")
        so_hieu = c.get("so_hieu")
        url = c.get("url")
        
        source_label_parts = [title]
        if section:
            source_label_parts.append(f"Mục {section}")
        if so_hieu:
            source_label_parts.append(so_hieu)
            
        src_key = f"{title}_{section}"
        if src_key not in seen_keys:
            seen_keys.add(src_key)
            src_str = " - ".join(source_label_parts)
            if url:
                src_str += f" ({url})"
            seen_sources.append(src_str)

        sources_data.append({
            "document_id": c["document_id"],
            "title": title,
            "section": section,
            "chunk_index": c["chunk_index"],
            "score": c["score"],
            "snippet": c["content"][:200],
            "url": url,
            "so_hieu": so_hieu
        })
        chunk_content = c['content']
        # Cắt ngắn chunk quá dài để giảm kích thước prompt và tăng tốc suy luận CPU
        if len(chunk_content) > settings.MAX_CHUNK_CHARS:
            chunk_content = chunk_content[:settings.MAX_CHUNK_CHARS] + "..."
        context_text += f"\n--- Tài liệu: {title} (Mục {section or 'Chung'}) ---\n{chunk_content}\n"

    # ── 3.6. Kiểm tra truy vấn Lịch học / Lịch thi Trung tâm NNTH ────────────
    is_center_query, center_ctx, center_sources = check_and_build_center_context(req.message, db)
    if is_center_query:
        # Khi hỏi về lịch trung tâm, xóa chunks quy chế để prompt ngắn gọn, phản hồi nhanh
        chunks = []
        sources_data = list(center_sources)
        seen_sources = ["Trung tâm Ngoại ngữ - Tin học Lạc Hồng (https://nnth.lhu.edu.vn)"]
        seen_keys = set()
        context_text = center_ctx

    # ── 4. Lưu câu hỏi gốc vào DB ────────────────────────────────────────────
    db.execute(
        text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"),
        {"sid": session_id, "content": req.message},
    )
    db.commit()

    # ── 5. Trả NO_CONTEXT nếu không có RAG và không phải câu hội thoại ───────
    if not chunks and not is_convo and not has_acad_kw and not is_center_query:
        answer = NO_CONTEXT_RESPONSE
    else:
        # ── 6. Xây dựng danh sách messages ─────────────────────────────────
        # Lấy lịch sử (tối đa 6 tin nhắn gần nhất, KHÔNG bao gồm tin vừa lưu)
        history = db.execute(
            text(
                "SELECT role, content FROM chat_messages "
                "WHERE session_id = :sid ORDER BY id DESC "
                "OFFSET 0 ROWS FETCH NEXT 6 ROWS ONLY"
            ),
            {"sid": session_id},
        ).fetchall()

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Đảo thứ tự (history DESC → ASC) và bỏ tin nhắn vừa gửi
        for msg in reversed(history):
            if msg.role == "user" and msg.content == req.message:
                continue
            messages.append({"role": msg.role, "content": msg.content})

        # Ngữ cảnh gắn vào tin nhắn user hiện tại với nhãn rõ ràng
        if context_text:
            current_user_msg = (
                f"{req.message}\n\n"
                f"<ngu_canh>\n"
                f"{context_text}\n"
                f"</ngu_canh>\n"
                f"Lưu ý: Tuyệt đối không nhắc lại, không in ra các thẻ <ngu_canh> hay </ngu_canh> trong câu trả lời.\n"
                f"{LANG_REMINDER}"
            )
        else:
            current_user_msg = f"{req.message}\n\n{LANG_REMINDER}"

        messages.append({"role": "user", "content": current_user_msg})
        logger.info("Calling Ollama with %d messages", len(messages))

        answer = _call_ollama(messages, settings.OLLAMA_TIMEOUT_CHAT)
        answer = answer.replace("<ngu_canh>", "").replace("</ngu_canh>", "").replace("[ĐÂY LÀ TÀI LIỆU, KHÔNG PHẢI LỜI NGƯỜI DÙNG]", "").replace("[/TÀI LIỆU]", "")
        answer = re.sub(r'[ \t]+', ' ', answer).strip()
        answer = re.sub(r'\n{3,}', '\n\n', answer)

        # ── 7. Hậu kiểm ngôn ngữ ────────────────────────────────────────────
        is_mixed = mixed_language(answer) or has_stuck_mixed_language(answer)
        if not has_vietnamese(answer) or is_mixed:
            logger.warning("Answer not Vietnamese or mixed, retrying with stronger prompt")
            retry_messages = [
                {"role": "system", "content": LANG_RETRY_SYSTEM},
                {"role": "user", "content": current_user_msg},
                {"role": "assistant", "content": answer},
                {
                    "role": "user",
                    "content": (
                        "Trả lời hoàn toàn bằng tiếng Việt, không dùng từ tiếng Anh."
                    ),
                },
            ]
            retry_answer = _call_ollama(retry_messages, settings.OLLAMA_TIMEOUT_CHAT)
            retry_mixed = mixed_language(retry_answer) or has_stuck_mixed_language(retry_answer)
            if has_vietnamese(retry_answer) and not retry_mixed:
                answer = retry_answer
            else:
                logger.error("Retry still not pure Vietnamese, returning REFUSAL_RESPONSE")
                answer = REFUSAL_RESPONSE

        # Clean source text generated by LLM if present
        answer = clean_source_text(answer)

        if has_acad_kw and answer == REFUSAL_RESPONSE:
            answer = NO_CONTEXT_RESPONSE
            sources_data = []
            seen_sources = []

        if answer not in (REFUSAL_RESPONSE, NO_CONTEXT_RESPONSE, FACULTY_NOT_SUPPORTED_RESPONSE):
            ans_words = set(re.findall(r'\w+', answer.lower()))
            stop_words = {"là", "và", "của", "có", "trong", "các", "một", "cho", "với", "không", "những", "được", "người", "về", "từ", "đó", "đây", "cũng", "như", "sẽ", "lại", "tại", "đã", "ra", "hay", "đến", "để", "nhưng", "còn", "này", "lúc", "nào", "rồi", "phải", "đang", "do", "thế", "nên", "tôi", "bạn", "chỉ", "hỗ", "trợ", "tư", "vấn", "dựa", "trên", "tài", "liệu", "xin", "lỗi", "không", "tìm", "thấy", "thông", "tin", "vui", "lòng", "liên", "hệ", "theo", "của", "nhà", "trường", "dựa"}
            content_words = ans_words - stop_words

            if content_words:
                chunk_text_lower = (" ".join([c["content"] for c in chunks]) + " " + center_ctx).lower()
                matched = sum(1 for w in content_words if w in chunk_text_lower)
                if matched / len(content_words) < 0.2:
                    answer = NO_CONTEXT_RESPONSE
                    sources_data = []
                    seen_sources = []

        # Ensure answer does not contain source strings (sources are kept in sources_data)
        answer = clean_source_text(answer)
        answer = clean_academic_regulation_answer(answer, req.message)

        # Yêu cầu 6: Thêm thông tin thời điểm cập nhật lịch NNTH
        if is_center_query and answer not in (REFUSAL_RESPONSE, NO_CONTEXT_RESPONSE, FACULTY_NOT_SUPPORTED_RESPONSE):
            sync_note = get_center_sync_note(db)
            if "Dữ liệu cập nhật lúc" not in answer:
                answer = f"{answer}\n\n*{sync_note}*"

    # ── 8. Lưu câu trả lời gốc (không lưu RAG context) ──────────────────────
    db.execute(
        text(
            "INSERT INTO chat_messages (session_id, role, content, sources) "
            "VALUES (:sid, 'assistant', :content, :sources)"
        ),
        {
            "sid": session_id,
            "content": answer,
            "sources": json.dumps(sources_data, ensure_ascii=False),
        },
    )
    db.commit()

    return {"session_id": session_id, "answer": answer, "sources": sources_data}


@router.post("/stream")
def chat_stream(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]

    if is_injection(req.message):
        session_id = req.session_id
        if not session_id:
            title = req.message[:40] + ("..." if len(req.message) > 40 else "")
            session_id = db.execute(
                text("INSERT INTO chat_sessions (user_id, title, updated_at) OUTPUT INSERTED.id VALUES (:uid, :title, SYSDATETIME())"),
                {"uid": user_id, "title": title},
            ).scalar()
            db.commit()
        db.execute(text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"), {"sid": session_id, "content": req.message})
        db.execute(text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"), {"sid": session_id, "content": REFUSAL_RESPONSE, "sources": "[]"})
        db.commit()

        def gen_inj():
            yield f"data: {json.dumps({'token': REFUSAL_RESPONSE, 'done': False}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'answer': REFUSAL_RESPONSE, 'sources': []}, ensure_ascii=False)}\n\n"
        return StreamingResponse(gen_inj(), media_type="text/event-stream", headers=SSE_HEADERS)

    session_id = req.session_id
    if not session_id:
        title = req.message[:40] + ("..." if len(req.message) > 40 else "")
        session_id = db.execute(
            text("INSERT INTO chat_sessions (user_id, title, updated_at) OUTPUT INSERTED.id VALUES (:uid, :title, SYSDATETIME())"),
            {"uid": user_id, "title": title},
        ).scalar()
        db.commit()
    else:
        sess = db.execute(text("SELECT id FROM chat_sessions WHERE id = :sid AND user_id = :uid"), {"sid": session_id, "uid": user_id}).fetchone()
        if not sess:
            raise HTTPException(status_code=403, detail="Cuộc trò chuyện không tồn tại hoặc không có quyền truy cập")
        db.execute(text("UPDATE chat_sessions SET updated_at = SYSDATETIME() WHERE id = :sid"), {"sid": session_id})
        db.commit()

    msg_lower = req.message.lower()
    guard = check_guardrails(req.message)
    if guard:
        answer, _ = guard
        db.execute(text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"), {"sid": session_id, "content": req.message})
        db.execute(text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"), {"sid": session_id, "content": answer, "sources": "[]"})
        db.commit()
        def gen_guard():
            yield f"data: {json.dumps({'token': answer, 'done': False}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'answer': answer, 'sources': []}, ensure_ascii=False)}\n\n"
        return StreamingResponse(gen_guard(), media_type="text/event-stream", headers=SSE_HEADERS)

    # ── 3.5. Nhận diện câu chào hỏi và xã giao đơn giản (không gọi LLM/RAG) ─────
    smalltalk_ans = get_smalltalk_response(req.message)
    if smalltalk_ans:
        db.execute(text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"), {"sid": session_id, "content": req.message})
        db.execute(text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"), {"sid": session_id, "content": smalltalk_ans, "sources": "[]"})
        db.commit()
        def gen_smalltalk():
            yield f"data: {json.dumps({'token': smalltalk_ans, 'done': False}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'answer': smalltalk_ans, 'sources': []}, ensure_ascii=False)}\n\n"
        return StreamingResponse(gen_smalltalk(), media_type="text/event-stream", headers=SSE_HEADERS)

    # ── 3.6. Xử lý câu hỏi trễ hạn / hết hạn đăng ký môn học (Việc 3) ────────────
    if is_registration_deadline_query(req.message):
        is_overdue = check_deadline()
        if is_overdue:
            db.execute(text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"), {"sid": session_id, "content": req.message})
            db.execute(text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"), {"sid": session_id, "content": REGISTRATION_OVERDUE_RESPONSE, "sources": json.dumps(REGISTRATION_OVERDUE_SOURCES, ensure_ascii=False)})
            db.commit()
            def gen_deadline():
                yield f"data: {json.dumps({'token': REGISTRATION_OVERDUE_RESPONSE, 'done': False}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'answer': REGISTRATION_OVERDUE_RESPONSE, 'sources': REGISTRATION_OVERDUE_SOURCES}, ensure_ascii=False)}\n\n"
            return StreamingResponse(gen_deadline(), media_type="text/event-stream", headers=SSE_HEADERS)

    is_convo = req.message.strip().lower() in _CONVO_QUERIES
    academic_kws = ["quy chế", "quy định", "thông báo", "học vụ", "niên giám", "buộc thôi học", "cảnh báo", "học bổng", "nghỉ học", "bảo lưu", "tốt nghiệp", "tín chỉ", "học phần", "chứng chỉ", "tiếng anh", "ngoại ngữ", "tin học", "lệ phí", "hồ sơ", "học kỳ", "thi lại", "thi phụ", "cấm thi", "học lại", "học vét"]
    has_acad_kw = any(kw in msg_lower for kw in academic_kws)

    # Nhận diện câu hỏi học vụ cá nhân / môn rớt / bảng điểm
    personal_explicit = [
        "điểm của tôi", "điểm của em", "bảng điểm của tôi", "bảng điểm của em",
        "tôi đã tích lũy bao nhiêu", "em đã tích lũy bao nhiêu",
        "tôi có bị rớt môn", "em có bị rớt môn", "danh sách môn rớt của tôi",
        "tôi đã đủ điều kiện tốt nghiệp chưa", "em đã đủ điều kiện tốt nghiệp chưa",
        "kiểm tra tốt nghiệp cho tôi", "xét tốt nghiệp của tôi",
        "tôi rớt môn nào", "em rớt môn nào", "tôi nợ môn nào", "em nợ môn nào",
        "tôi rớt môn", "em rớt môn", "môn rớt", "môn nợ", "rớt môn", "nợ môn",
        "học lại", "cần làm gì", "phải làm gì", "hồ sơ của tôi", "hồ sơ của em"
    ]
    is_personal_query = any(p in msg_lower for p in personal_explicit) or (
        any(kw in msg_lower for kw in ["rớt", "nợ", "chưa đạt", "không đạt", "điểm", "bảng điểm", "tốt nghiệp"]) and
        any(sub in msg_lower for sub in ["tôi", "em", "mình", "của tôi", "của em", "làm gì"])
    )

    student_ctx = ""
    ocr_info = None
    grad_info = None
    verified = None
    if is_personal_query:
        student_ctx, ocr_info, grad_info = get_student_academic_and_ocr_context(db, user_id)
        verified = build_verified_academic_data(grad_info, ocr_info)

    # Kiểm tra truy vấn Lịch học / Lịch thi Trung tâm NNTH và tính sẵn sync_note khi db session còn mở
    is_center_query, center_ctx, center_sources = check_and_build_center_context(req.message, db)
    center_sync_note = get_center_sync_note(db) if is_center_query else ""

    query_to_search = (req.message + " quy định học lại điểm F đăng ký học kỳ hè tốt nghiệp") if is_personal_query else req.message
    chunks = [] if (is_convo or is_center_query) else search_chunks(db, query_to_search)

    # Save user message
    db.execute(text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"), {"sid": session_id, "content": req.message})
    db.commit()

    if not chunks and not is_convo and not has_acad_kw and not student_ctx and not is_center_query:
        answer = NO_CONTEXT_RESPONSE
        db.execute(text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"), {"sid": session_id, "content": answer, "sources": "[]"})
        db.commit()
        def gen_noc():
            yield f"data: {json.dumps({'token': answer, 'done': False}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'answer': answer, 'sources': []}, ensure_ascii=False)}\n\n"
        return StreamingResponse(gen_noc(), media_type="text/event-stream", headers=SSE_HEADERS)

    sources_data = list(center_sources) if is_center_query else []
    context_text = ""
    seen_sources = []
    seen_keys = set()

    if ocr_info:
        sources_data.append({
            "document_id": 9998,
            "title": f"Bảng điểm OCR ({ocr_info['filename']})",
            "section": "Kết quả trích xuất điểm",
            "chunk_index": 0,
            "score": 1.0,
            "snippet": f"Đọc được {ocr_info['total_subjects']} môn, gồm {ocr_info['failed_count']} môn chưa đạt.",
            "url": None,
            "so_hieu": "OCR"
        })

    if student_ctx:
        context_text += student_ctx + "\n\n"

    # Nối thêm center_ctx vào context_text thay vì ghi đè student_ctx
    if is_center_query:
        context_text += center_ctx + "\n\n"

    for c in chunks:
        title = c["title"]
        section = c.get("section")
        so_hieu = c.get("so_hieu")
        url = c.get("url")
        src_label_parts = [title]
        if section: src_label_parts.append(f"Mục {section}")
        if so_hieu: src_label_parts.append(so_hieu)
        src_key = f"{title}_{section}"
        if src_key not in seen_keys:
            seen_keys.add(src_key)
            src_str = " - ".join(src_label_parts)
            if url: src_str += f" ({url})"
            seen_sources.append(src_str)
        sources_data.append({
            "document_id": c["document_id"], "title": title, "section": section,
            "chunk_index": c["chunk_index"], "score": c["score"], "snippet": c["content"][:200],
            "url": url, "so_hieu": so_hieu
        })
        chunk_content = c['content']
        # Cắt ngắn chunk quá dài để phản hồi sớm trong stream
        if len(chunk_content) > settings.MAX_CHUNK_CHARS:
            chunk_content = chunk_content[:settings.MAX_CHUNK_CHARS] + "..."
        context_text += f"\n--- Tài liệu: {title} (Mục {section or 'Chung'}) ---\n{chunk_content}\n"

    history = db.execute(
        text("SELECT role, content FROM chat_messages WHERE session_id = :sid ORDER BY id DESC OFFSET 0 ROWS FETCH NEXT 6 ROWS ONLY"),
        {"sid": session_id},
    ).fetchall()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in reversed(history):
        if msg.role == "user" and msg.content == req.message:
            continue
        messages.append({"role": msg.role, "content": msg.content})

    if is_personal_query and verified:
        template_text = generate_verified_academic_template(verified, req.message)

        # Lưu câu trả lời chuẩn vào DB
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"),
            {"sid": session_id, "content": template_text, "sources": json.dumps(sources_data, ensure_ascii=False)},
        )
        db.commit()

        def gen_personal_stream():
            paragraphs = template_text.split("\n\n")
            for i, p in enumerate(paragraphs):
                p_text = p + ("\n\n" if i < len(paragraphs) - 1 else "")
                yield f"data: {json.dumps({'token': p_text, 'done': False}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'answer': template_text, 'sources': sources_data}, ensure_ascii=False)}\n\n"

        return StreamingResponse(gen_personal_stream(), media_type="text/event-stream", headers=SSE_HEADERS)

    elif context_text:
        current_user_msg = (
            f"{req.message}\n\n"
            f"<ngu_canh>\n"
            f"{context_text}\n"
            f"</ngu_canh>\n"
            f"Lưu ý: Tuyệt đối không nhắc lại, không in ra các thẻ <ngu_canh> hay </ngu_canh> trong câu trả lời.\n"
            f"{LANG_REMINDER}"
        )
    else:
        current_user_msg = f"{req.message}\n\n{LANG_REMINDER}"
    messages.append({"role": "user", "content": current_user_msg})

    def stream_generator():
        import re
        full_text = ""
        try:
            res = requests.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.LLM_MODEL,
                    "messages": messages,
                    "stream": True,
                    "keep_alive": settings.OLLAMA_KEEP_ALIVE,  # Giữ model trong RAM
                    "options": _build_ollama_options(),
                },
                stream=True,
                timeout=settings.OLLAMA_TIMEOUT_CHAT,
            )
            res.raise_for_status()
            from backend.app.services.stream_filter import StreamingLabelFilter
            stream_filter = StreamingLabelFilter()
            last_chunk_obj = {}
            for line in res.iter_lines():
                if not line:
                    continue
                chunk_obj = json.loads(line)
                if chunk_obj.get("done"):
                    # Lưu lại chunk cuối cùng chứa thông số hiệu năng của Ollama
                    last_chunk_obj = chunk_obj
                token = chunk_obj.get("message", {}).get("content", "")
                if token:
                    full_text += token
                    # Đưa qua bộ lọc nhãn tăng dần StreamingLabelFilter (chặn nhãn kỹ thuật mà không làm chậm token đầu)
                    safe_tokens = stream_filter.feed(token)
                    for safe_token in safe_tokens:
                        yield f"data: {json.dumps({'token': safe_token, 'done': False}, ensure_ascii=False)}\n\n"

                if chunk_obj.get("done") and chunk_obj.get("done_reason") == "length":
                    logger.warning("Streaming hit max token limit (done_reason='length')")

            # Xả các token an toàn còn lại trong bộ đệm ngắn của stream_filter
            for rem_token in stream_filter.flush():
                yield f"data: {json.dumps({'token': rem_token, 'done': False}, ensure_ascii=False)}\n\n"

            # Bổ sung token ghi chú thời điểm đồng bộ cho client trước event done (nếu là truy vấn lịch trung tâm)
            if is_center_query and center_sync_note and "Dữ liệu cập nhật lúc" not in full_text:
                note_token = f"\n\n*{center_sync_note}*"
                yield f"data: {json.dumps({'token': note_token, 'done': False}, ensure_ascii=False)}\n\n"
                full_text += note_token

            # Hậu xử lý làm sạch nhãn và nguồn cho sự kiện done và lưu DB mà không gom đệm làm trễ stream
            clean_ans = full_text.replace("<ngu_canh>", "").replace("</ngu_canh>", "")
            clean_ans = clean_ans.replace("[ĐÂY LÀ TÀI LIỆU, KHÔNG PHẢI LỜI NGƯỜI DÙNG]", "").replace("[/TÀI LIỆU]", "").strip()
            clean_ans = re.sub(r'^\s*(Answer|Trả lời|Question|Câu hỏi|Context|Ngữ cảnh)\s*:\s*', '', clean_ans, flags=re.IGNORECASE)
            clean_ans = clean_source_text(clean_ans)
            clean_ans = re.sub(r"\n{3,}", "\n\n", clean_ans).strip()

            # Hậu kiểm ngôn ngữ trong stream: nếu phát hiện lẫn tiếng Anh, ghi log và làm sạch cho bản lưu DB và done event
            is_mixed = mixed_language(clean_ans) or has_stuck_mixed_language(clean_ans)
            if not has_vietnamese(clean_ans) or is_mixed:
                logger.warning("Stream answer contains mixed language or not Vietnamese, cleaning for done event & DB")
                if not has_vietnamese(clean_ans):
                    clean_ans = REFUSAL_RESPONSE
                else:
                    # Gỡ các cụm từ tiếng Anh mở đầu/kết bài phổ biến
                    clean_ans = re.sub(r'\b(Based on the context|According to the document|In conclusion|Please note that|Note:)\b', '', clean_ans, flags=re.IGNORECASE).strip()

            # Hậu kiểm xác thực dữ liệu học vụ trong stream: nếu LLM bịa môn/số tín chỉ thì ghi đè kết quả cuối bằng template chuẩn
            if verified and not validate_academic_answer(clean_ans, verified):
                clean_ans = generate_verified_academic_template(verified, req.message)

            clean_ans = clean_academic_regulation_answer(clean_ans, req.message)

            from backend.app.db import SessionLocal
            save_db = SessionLocal()
            try:
                save_db.execute(
                    text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"),
                    {"sid": session_id, "content": clean_ans, "sources": json.dumps(sources_data, ensure_ascii=False)},
                )
                save_db.commit()
            finally:
                save_db.close()

            # Bổ sung các thông số đo lường hiệu năng từ Ollama vào sự kiện done
            done_payload = {
                "done": True,
                "session_id": session_id,
                "answer": clean_ans,
                "sources": sources_data,
            }
            if last_chunk_obj:
                for metric_key in ["prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration", "load_duration", "total_duration"]:
                    if metric_key in last_chunk_obj:
                        done_payload[metric_key] = last_chunk_obj[metric_key]

            yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception("Error in stream_generator: %s", e)
            err_msg = "\n[Lỗi kết nối AI]"
            yield f"data: {json.dumps({'token': err_msg, 'done': True, 'session_id': session_id, 'answer': full_text + err_msg, 'sources': []}, ensure_ascii=False)}\n\n"

    # Trả về StreamingResponse với header chống buffer (Cache-Control: no-cache, X-Accel-Buffering: no)
    return StreamingResponse(stream_generator(), media_type="text/event-stream", headers=SSE_HEADERS)


class RenameSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


@router.get("/sessions")
def get_sessions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    sql = "SELECT id, user_id, title, created_at, updated_at FROM chat_sessions WHERE user_id = :uid ORDER BY COALESCE(updated_at, created_at) DESC"
    sessions = db.execute(text(sql), {"uid": user_id}).fetchall()
    return [
        {
            "id": s.id,
            "user_id": s.user_id,
            "title": s.title,
            "created_at": str(s.created_at) if s.created_at else None,
            "updated_at": str(s.updated_at) if getattr(s, "updated_at", None) else (str(s.created_at) if s.created_at else None),
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages")
def get_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]

    sess = db.execute(
        text("SELECT user_id FROM chat_sessions WHERE id = :sid"), {"sid": session_id}
    ).fetchone()
    if not sess:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện")

    if current_user["role"] != "admin" and sess.user_id != user_id:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập cuộc trò chuyện này")

    messages = db.execute(
        text(
            "SELECT id, role, content, sources, created_at "
            "FROM chat_messages WHERE session_id = :sid ORDER BY id ASC"
        ),
        {"sid": session_id},
    ).fetchall()

    results = []
    for m in messages:
        src = []
        if m.sources:
            try:
                src = json.loads(m.sources)
            except Exception:
                pass
        cleaned_content = clean_source_text(m.content) if m.role == "assistant" else m.content
        results.append({
            "id": m.id,
            "role": m.role,
            "content": cleaned_content,
            "sources": src,
            "created_at": str(m.created_at) if m.created_at else None,
        })
    return results


@router.patch("/sessions/{session_id}")
def rename_session(
    session_id: int,
    req: RenameSessionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    sess = db.execute(
        text("SELECT user_id FROM chat_sessions WHERE id = :sid"), {"sid": session_id}
    ).fetchone()
    if not sess:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện")

    if current_user["role"] != "admin" and sess.user_id != user_id:
        raise HTTPException(status_code=403, detail="Không có quyền chỉnh sửa cuộc trò chuyện này")

    new_title = req.title.strip()
    db.execute(
        text("UPDATE chat_sessions SET title = :title, updated_at = SYSDATETIME() WHERE id = :sid"),
        {"title": new_title, "sid": session_id},
    )
    db.commit()
    return {"success": True, "id": session_id, "title": new_title}


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    sess = db.execute(
        text("SELECT user_id FROM chat_sessions WHERE id = :sid"), {"sid": session_id}
    ).fetchone()
    if not sess:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện")

    if current_user["role"] != "admin" and sess.user_id != user_id:
        raise HTTPException(status_code=403, detail="Không có quyền xoá cuộc trò chuyện này")

    db.execute(text("DELETE FROM chat_messages WHERE session_id = :sid"), {"sid": session_id})
    db.execute(text("DELETE FROM chat_sessions WHERE id = :sid"), {"sid": session_id})
    db.commit()
    return {"success": True, "message": "Đã xoá cuộc trò chuyện"}


@router.post("/upload")
async def chat_upload(
    files: List[UploadFile] = File(...),
    message: Optional[str] = Form(""),
    session_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]

    if not files:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất một tệp để tải lên.")
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Chỉ được tải lên tối đa 5 tệp cùng lúc.")

    allowed_exts = {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".txt"}
    max_file_size = 10 * 1024 * 1024  # 10MB
    upload_root = os.path.abspath("temp_uploads")
    session_upload_dir = os.path.join(upload_root, "chat_uploads", str(uuid.uuid4()))
    os.makedirs(session_upload_dir, exist_ok=True)

    file_summaries = []
    file_attachments_meta = []
    transcript_confirm_messages = []

    try:
        # Lấy thông tin student_id liên kết với user_id (nếu có)
        stu_row = db.execute(
            text("SELECT id, full_name FROM students WHERE user_id = :uid"),
            {"uid": user_id}
        ).fetchone()
        current_student_id = stu_row.id if stu_row else None

        clean_msg = (message or "").strip()

        # Quản lý Session trước nếu chưa có để gắn với kết quả OCR
        if not session_id:
            title_text = clean_msg if clean_msg else f"Tệp: {files[0].filename}"
            title = title_text[:40] + ("..." if len(title_text) > 40 else "")
            session_id = db.execute(
                text("INSERT INTO chat_sessions (user_id, title, updated_at) OUTPUT INSERTED.id VALUES (:uid, :title, SYSDATETIME())"),
                {"uid": user_id, "title": title},
            ).scalar()
            db.commit()
        else:
            sess = db.execute(
                text("SELECT id FROM chat_sessions WHERE id = :sid AND user_id = :uid"),
                {"sid": session_id, "uid": user_id},
            ).fetchone()
            if not sess:
                raise HTTPException(status_code=403, detail="Cuộc trò chuyện không tồn tại hoặc không có quyền truy cập")
            db.execute(text("UPDATE chat_sessions SET updated_at = SYSDATETIME() WHERE id = :sid"), {"sid": session_id})
            db.commit()

        for f in files:
            ext = os.path.splitext(f.filename)[1].lower() if f.filename else ""
            if ext not in allowed_exts:
                raise HTTPException(
                    status_code=400,
                    detail=f"Định dạng tệp '{f.filename}' không được hỗ trợ. Vui lòng tải lên PNG, JPG, PDF, DOCX hoặc TXT.",
                )

            content = await f.read()
            if len(content) > max_file_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tệp '{f.filename}' vượt quá dung lượng tối đa cho phép (10MB).",
                )

            save_path = os.path.join(session_upload_dir, f.filename)
            with open(save_path, "wb") as out_f:
                out_f.write(content)

            file_type = "document"
            summary = ""

            # Tự động phân loại và xử lý tệp
            if ext == ".txt":
                text_str = content.decode("utf-8", errors="ignore")
                summary = f"📄 Tệp văn bản '{f.filename}':\n{text_str[:1200]}"
                file_type = "txt"
            elif ext == ".docx":
                try:
                    import docx
                    doc = docx.Document(save_path)
                    doc_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                    summary = f"📄 Tài liệu Word '{f.filename}':\n{doc_text[:1200]}"
                    file_type = "docx"
                except Exception as e:
                    summary = f"📄 Tài liệu Word '{f.filename}' (Lỗi đọc docx: {str(e)})"
                    file_type = "docx"
            elif ext in {".png", ".jpg", ".jpeg", ".pdf"}:
                cert_kws = ["chứng chỉ", "chung chi", "certificate", "toeic", "ielts", "tin học", "mos", "b1", "b2", "vstep"]
                check_text = f"{f.filename} {message or ''}".lower()
                is_cert = any(kw in check_text for kw in cert_kws)

                if is_cert and ext != ".pdf":
                    try:
                        from backend.certificate_extractor import extract_certificate_from_image
                        from backend.certificate_matcher import match_certificate
                        extracted = extract_certificate_from_image(image_input=save_path)
                        match_res = match_certificate(extracted)
                        summary = (
                            f"📜 Chứng chỉ '{f.filename}':\n"
                            f"- Loại: {extracted.get('loai_chung_chi', 'Chưa rõ')} - {extracted.get('ten_chung_chi_cu_the', 'Chưa rõ')}\n"
                            f"- Người được cấp: {extracted.get('ten_nguoi_duoc_cap') or 'Không rõ'}\n"
                            f"- Trạng thái xét tốt nghiệp: {match_res.get('trang_thai_cap_nhat')} "
                            f"({match_res.get('muc_tot_nghiep_khop') or 'Chưa đạt chuẩn'})\n"
                            f"- Đánh giá: {match_res.get('ly_do', '')}"
                        )
                        file_type = "certificate"

                        # Lưu vào student_certificates nếu là sinh viên có hồ sơ
                        if current_student_id:
                            is_auto = bool(match_res.get("tu_dong_cap_nhat") is True)
                            raw_cert_name = extracted.get("ten_nguoi_duoc_cap")
                            name_cert = " ".join(strip_accents(str(raw_cert_name or "")).lower().split()) if raw_cert_name else ""
                            name_stu = " ".join(strip_accents(str(stu_row.full_name if stu_row else "")).lower().split())
                            is_name_matched = bool(name_cert and name_stu and name_cert == name_stu)
                            cert_status = "valid" if (is_auto and is_name_matched) else "pending"
                            cert_type = match_res.get("muc_tot_nghiep_khop") or extracted.get("loai_chung_chi") or "Ngoại ngữ"
                            cert_name = extracted.get("ten_chung_chi_cu_the") or match_res.get("muc_tot_nghiep_khop") or extracted.get("loai_chung_chi") or "Chứng chỉ"
                            issued_date = str(extracted.get("ngay_cap") or "")
                            try:
                                check_tbl = db.execute(text("SELECT OBJECT_ID('student_certificates', 'U')")).scalar()
                                if check_tbl is not None:
                                    existing = db.execute(
                                        text("SELECT id FROM student_certificates WHERE student_id = :sid AND certificate_type = :ctype"),
                                        {"sid": current_student_id, "ctype": cert_type}
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
                                            {"sid": current_student_id, "ctype": cert_type, "cname": cert_name, "idate": issued_date, "status": cert_status}
                                        )
                                    db.commit()
                            except Exception as cert_db_err:
                                logger.error(f"Lỗi khi lưu student_certificates trong chat_upload: {cert_db_err}", exc_info=True)
                                db.rollback()
                    except TimeoutError as timeout_err:
                        logger.error(f"Quá thời gian phân tích chứng chỉ '{f.filename}': {timeout_err}")
                        summary = f"📜 Chứng chỉ '{f.filename}' (Quá thời gian phản hồi từ hệ thống AI đọc ảnh)"
                        transcript_confirm_messages.append(f"⏱️ Quá thời gian xử lý khi đọc chứng chỉ '{f.filename}' (timeout). Vui lòng thử lại với hình ảnh rõ nét hơn.")
                        file_type = "certificate"
                    except Exception as cert_err:
                        summary = f"📜 Chứng chỉ '{f.filename}' (Lỗi phân tích: {str(cert_err)})"
                        file_type = "certificate"
                else:
                    try:
                        from backend.pipeline import run_pipeline
                        pipe_out = os.path.join("output", "chat_" + str(uuid.uuid4()))
                        result = run_pipeline(input_path=save_path, output_dir=pipe_out)

                        failed_subjects = result.get("failed_subjects", [])
                        
                        # Thống nhất phân loại môn:
                        # 1. Môn chưa đạt (môn rớt): điểm < 4.0
                        # 2. Môn bị đánh dấu đỏ nhưng điểm >= 4.0: môn bị đánh dấu đỏ, cần xác nhận với giáo vụ
                        failed_under_4 = []
                        red_marked_ge_4 = []

                        for s in failed_subjects:
                            diem_val = s.get("diem")
                            try:
                                d = float(diem_val)
                            except (ValueError, TypeError):
                                d = 0.0

                            if d < 4.0:
                                failed_under_4.append(s)
                            else:
                                red_marked_ge_4.append(s)

                        failed_under_4_names = [s.get("mon") or s.get("name") or "Chưa rõ" for s in failed_under_4]
                        red_marked_ge_4_names = [s.get("mon") or s.get("name") or "Chưa rõ" for s in red_marked_ge_4]
                        failed_under_4_list = [f"{s.get('mon') or s.get('name')} ({s.get('diem')})" for s in failed_under_4]
                        red_marked_ge_4_list = [f"{s.get('mon') or s.get('name')} ({s.get('diem')})" for s in red_marked_ge_4]

                        # Tóm tắt xác nhận cho sinh viên
                        msg_lines = [f"📊 Tôi đã đọc bảng điểm '{f.filename}' của bạn: Đọc được {result.get('total_subjects', 0)} môn."]
                        details = []
                        if failed_under_4_names:
                            details.append(f"có {len(failed_under_4_names)} môn chưa đạt (môn rớt, điểm < 4.0): {', '.join(failed_under_4_names)}")
                        if red_marked_ge_4_names:
                            details.append(f"có {len(red_marked_ge_4_names)} môn bị đánh dấu đỏ, cần xác nhận với giáo vụ (điểm ≥ 4.0): {', '.join(red_marked_ge_4_names)}")

                        if details:
                            msg_lines.append("Trong đó " + "; ".join(details) + ".\n👉 Bạn vui lòng kiểm tra lại. Bạn có thể hỏi tôi: 'tôi rớt môn nào, cần làm gì?' để được tư vấn lộ trình học bù và xét tốt nghiệp!")
                        else:
                            msg_lines.append("Tất cả các môn đều ĐẠT (>= 4.0).\n👉 Bạn có thể hỏi tôi để kiểm tra điều kiện tốt nghiệp!")

                        confirm_msg = "\n".join(msg_lines)
                        transcript_confirm_messages.append(confirm_msg)

                        # Lưu kết quả có cấu trúc vào bảng student_ocr_transcripts
                        db.execute(
                            text("""
                                INSERT INTO student_ocr_transcripts
                                (user_id, student_id, session_id, filename, total_subjects, passed_count, failed_count, courses_data, summary_text)
                                VALUES (:uid, :sid, :sess_id, :fname, :total, :passed, :failed, :data, :summary)
                            """),
                            {
                                "uid": user_id,
                                "sid": current_student_id,
                                "sess_id": session_id,
                                "fname": f.filename,
                                "total": result.get("total_subjects", 0),
                                "passed": result.get("passed_count", 0),
                                "failed": len(failed_under_4),
                                "data": json.dumps(result.get("all_subjects", []), ensure_ascii=False),
                                "summary": confirm_msg,
                            }
                        )
                        db.commit()

                        summary_lines = [
                            f"📊 Bảng điểm '{f.filename}':",
                            f"- Tổng số môn: {result.get('total_subjects', 0)}",
                            f"- Số môn ĐẠT: {result.get('passed_count', 0)}",
                            f"- Số môn CHƯA ĐẠT (điểm < 4.0): {len(failed_under_4)}"
                        ]
                        if red_marked_ge_4:
                            summary_lines.append(f"- Môn bị đánh dấu đỏ, cần xác nhận với giáo vụ (điểm ≥ 4.0): {len(red_marked_ge_4)}")
                        if result.get("red_regions_count", 0) > 0:
                            summary_lines.append(f"- Vùng đánh dấu đỏ: {result.get('red_regions_count')}")

                        if failed_under_4_list:
                            summary_lines.append(f"- Môn chưa đạt (điểm < 4.0): {', '.join(failed_under_4_list[:8])}")
                        if red_marked_ge_4_list:
                            summary_lines.append(f"- Môn bị đánh dấu đỏ, cần xác nhận với giáo vụ: {', '.join(red_marked_ge_4_list[:8])}")

                        summary = "\n".join(summary_lines)
                        file_type = "transcript"
                    except TimeoutError as timeout_err:
                        logger.error(f"Quá thời gian chạy OCR bảng điểm cho file '{f.filename}': {timeout_err}")
                        err_msg = (
                            f"⏱️ Quá thời gian xử lý khi đọc bảng điểm '{f.filename}'. "
                            "Hãy dùng ảnh rõ nét, dưới 2MB, hoặc chỉ gửi trang có bảng điểm."
                        )
                        transcript_confirm_messages.append(err_msg)
                        summary = f"⚠️ Bảng điểm '{f.filename}': Quá thời gian xử lý khi đọc bảng điểm. Hãy dùng ảnh rõ nét, dưới 2MB, hoặc chỉ gửi trang có bảng điểm."
                        file_type = "transcript"
                    except ConnectionError as conn_err:
                        logger.error(f"Lỗi kết nối dịch vụ OCR cho file '{f.filename}': {conn_err}")
                        err_msg = (
                            f"⚠️ Không thể kết nối với dịch vụ nhận diện ảnh cho '{f.filename}'. "
                            "Vui lòng kiểm tra lại hệ thống AI (Ollama)."
                        )
                        transcript_confirm_messages.append(err_msg)
                        summary = f"⚠️ Bảng điểm '{f.filename}': Không thể kết nối dịch vụ AI đọc ảnh."
                        file_type = "transcript"
                    except Exception as pipe_err:
                        logger.warning(f"Lỗi chạy pipeline OCR cho file '{f.filename}': {pipe_err}")
                        err_msg = (
                            f"⚠️ Chưa thể đọc được nội dung bảng điểm '{f.filename}'. "
                            "Bạn vui lòng kiểm tra lại định dạng hoặc độ rõ nét của ảnh."
                        )
                        transcript_confirm_messages.append(err_msg)
                        summary = f"⚠️ Bảng điểm '{f.filename}' (Lỗi phân tích hình ảnh)"
                        file_type = "transcript"

            file_summaries.append(summary)
            file_attachments_meta.append({
                "filename": f.filename,
                "size": len(content),
                "type": file_type,
                "summary": summary,
            })

        # Chuẩn bị câu trả lời cho chat
        file_context_str = "\n\n".join(file_summaries)
        combined_sources = list(file_attachments_meta)

        if clean_msg:
            # Tích hợp RAG: Tìm kiếm các chunk quy định phù hợp với câu hỏi
            rag_chunks = search_chunks(db, clean_msg)
            rag_context_lines = []
            seen_rag_sources = []
            for c in rag_chunks:
                title = c["title"]
                section = c.get("section")
                so_hieu = c.get("so_hieu")
                url = c.get("url")

                src_label_parts = [title]
                if section:
                    src_label_parts.append(f"Mục {section}")
                if so_hieu:
                    src_label_parts.append(so_hieu)
                src_str = " - ".join(src_label_parts)
                if url:
                    src_str += f" ({url})"
                if src_str not in seen_rag_sources:
                    seen_rag_sources.append(src_str)

                combined_sources.append({
                    "document_id": c["document_id"],
                    "title": title,
                    "section": section,
                    "chunk_index": c["chunk_index"],
                    "score": c["score"],
                    "snippet": c["content"][:200],
                    "url": url,
                    "so_hieu": so_hieu,
                })
                rag_context_lines.append(f"\n--- Tài liệu: {title} (Mục {section or 'Chung'}) ---\n{c['content']}\n")

            rag_context_str = "".join(rag_context_lines)

            full_context = ""
            if rag_context_str:
                full_context += f"<ngu_canh>\n{rag_context_str}\n</ngu_canh>\n\n"
            if file_context_str:
                full_context += f"[THÔNG TIN TỆP ĐÍNH KÈM ĐÃ PHÂN TÍCH]:\n{file_context_str}\n\n"

            combined_prompt = (
                f"{clean_msg}\n\n"
                f"{full_context}"
                f"Lưu ý: Hãy trả lời câu hỏi dựa trên các tài liệu và thông tin trên một cách đầy đủ, chính xác. "
                f"Tuyệt đối không suy đoán, không in lại các thẻ <ngu_canh>."
            )
            try:
                messages_llm = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": combined_prompt}
                ]
                answer = _call_ollama(messages_llm, settings.OLLAMA_TIMEOUT_CHAT)
                answer = answer.replace("<ngu_canh>", "").replace("</ngu_canh>", "").strip()
                answer = clean_source_text(answer)
            except Exception as e:
                logger.exception("Error in chat_upload LLM call: %s", e)
                answer = f"Tôi đã phân tích các tệp bạn gửi:\n\n{file_context_str}\n\nĐối với câu hỏi '{clean_msg}': Vui lòng xem thông tin chi tiết các môn học và chứng chỉ ở trên."
        else:
            if transcript_confirm_messages:
                answer = "\n\n".join(transcript_confirm_messages)
            else:
                answer = "Tôi đã tiếp nhận và phân tích các tệp bạn tải lên:\n\n" + file_context_str

        answer = clean_source_text(answer)

        # Lưu tin nhắn người dùng
        user_display = clean_msg if clean_msg else f"Đã tải lên {len(files)} tệp."
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'user', :content, :sources)"),
            {
                "sid": session_id,
                "content": user_display,
                "sources": json.dumps(file_attachments_meta, ensure_ascii=False),
            },
        )

        # Lưu tin nhắn trợ lý
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"),
            {
                "sid": session_id,
                "content": answer,
                "sources": json.dumps(combined_sources, ensure_ascii=False),
            },
        )
        db.commit()

        return {
            "session_id": session_id,
            "answer": answer,
            "sources": combined_sources,
            "files": file_attachments_meta,
        }

    finally:
        # Xóa file upload gốc sau khi xử lý xong, kể cả khi OCR lỗi (Yêu cầu 5 - Bảo mật)
        if os.path.exists(session_upload_dir):
            try:
                shutil.rmtree(session_upload_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Lỗi khi xóa thư mục tạm upload: {e}")
