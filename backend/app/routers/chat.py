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

from backend.app.db import get_db
from backend.app.deps import get_current_user
from backend.app.config import settings
from backend.app.services.retrieval import search_chunks
from backend.app.prompts import (
    SYSTEM_PROMPT, NO_CONTEXT_RESPONSE, REFUSAL_RESPONSE, FACULTY_NOT_SUPPORTED_RESPONSE,
    LANG_REMINDER, LANG_RETRY_SYSTEM,
    is_injection, has_vietnamese, mixed_language
)
from backend.app.routers.students import graduation_check
from backend.services.nnth_sync import (
    get_upcoming_schedules,
    get_upcoming_exams,
    get_last_sync_info
)

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

# ─── Câu hỏi chỉ hỏi về hội thoại (không cần RAG) ───────────────────────────
_CONVO_QUERIES = frozenset([
    "tôi vừa nói gì?", "tôi vừa hỏi gì?",
    "xin chào", "chào bạn", "hello", "hi",
])


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
    Kiểm tra xem câu hỏi có thuộc phạm vi khoa khác hoặc ngoài lề không.
    Trả về (answer_text, guardrail_type) nếu vi phạm, hoặc None nếu hợp lệ.
    """
    msg_lower = msg.lower()

    # 1. Kiểm tra hỏi về khoa/ngành khác (Hệ thống chỉ hỗ trợ Khoa CNTT)
    other_faculties = [
        "luật", "du lịch", "kinh tế", "dược", "y khoa", "y học", "cơ điện", "điện tử",
        "ngôn ngữ", "đông phương", "tài chính", "ngân hàng", "kế toán", "quản trị",
        "môi trường", "thực phẩm", "hóa học", "xây dựng", "khoa khác", "ngành khác"
    ]
    for fac in other_faculties:
        if f"khoa {fac}" in msg_lower or f"ngành {fac}" in msg_lower or (fac in ["luật", "du lịch", "kinh tế", "dược"] and f" {fac}" in msg_lower and any(w in msg_lower for w in ["tốt nghiệp", "điều kiện", "xét"])):
            return FACULTY_NOT_SUPPORTED_RESPONSE, "other_faculty"

    # 2. Kiểm tra câu hỏi ngoài lề (off-topic)
    off_topic_patterns = [
        "nấu phở", "công thức nấu", "cách nấu", "món ăn", "bóng đá", "thời tiết",
        "chơi game", "ca sĩ", "diễn viên", "thơ tình", "tỏ tình", "chế biến",
        "bánh mì", "làm bánh", "công thức làm", "cách làm bánh", "nấu ăn",
        "thực đơn", "pha chế", "chứng khoán", "tiền ảo", "bitcoin", "tử vi", "bói toán"
    ]
    if any(pat in msg_lower for pat in off_topic_patterns):
        return REFUSAL_RESPONSE, "off_topic"

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


def _call_ollama(messages: list, timeout: int) -> str:
    """Gọi Ollama và trả về nội dung trả lời. Ném HTTPException nếu lỗi."""
    try:
        res = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.LLM_MODEL,
                "messages": messages,
                "stream": False,
                "keep_alive": -1,
                "options": {
                    "temperature": 0.2,
                    "top_p": 0.9,
                    "num_predict": 300,
                    "num_ctx": 4096,
                },
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

    # ── 4. Retrieval ──────────────────────────────────────────────────────────
    is_convo = req.message.strip().lower() in _CONVO_QUERIES
    query_for_embedding = req.message
    chunks = [] if is_convo else search_chunks(db, query_for_embedding)

    max_score = max((c["score"] for c in chunks), default=0.0)

    academic_kws = ["quy chế", "quy định", "thông báo", "học vụ", "niên giám", "buộc thôi học", "cảnh báo", "học bổng", "nghỉ học", "bảo lưu", "tốt nghiệp", "tín chỉ", "học phần", "chứng chỉ", "tiếng anh", "ngoại ngữ", "tin học", "lệ phí", "hồ sơ", "học kỳ"]
    has_acad_kw = any(kw in msg_lower for kw in academic_kws)

    # Chỉ xem là personal khi thực sự hỏi về điểm/hồ sơ cá nhân của mình
    personal_explicit = [
        "điểm của tôi", "điểm của em", "bảng điểm của tôi", "bảng điểm của em",
        "tôi đã tích lũy bao nhiêu", "em đã tích lũy bao nhiêu",
        "tôi có bị rớt môn", "em có bị rớt môn", "danh sách môn rớt của tôi",
        "tôi đã đủ điều kiện tốt nghiệp chưa", "em đã đủ điều kiện tốt nghiệp chưa",
        "kiểm tra tốt nghiệp cho tôi", "xét tốt nghiệp của tôi"
    ]
    is_personal_query = any(p in msg_lower for p in personal_explicit)

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
        # Call graduation_check logic directly
        stu = db.execute(text("SELECT id FROM students WHERE user_id = :uid"), {"uid": current_user["id"]}).fetchone()
        if not stu:
            answer = "Tài khoản chưa liên kết hồ sơ sinh viên"
        else:
            try:
                pers_data = graduation_check(stu.id, explain=True, db=db, current_user=current_user)
                gpa_line = f"- GPA: {pers_data['gpa']}\n" if "gpa" in pers_data else ""
                
                # Danh sách môn rớt / dưới 4.0 từ bảng grades
                is_asking_failed = any(kw in msg_lower for kw in ["rớt", "nợ", "dưới", "chưa đạt", "không đạt", "trượt"])
                failed_section = ""
                if is_asking_failed:
                    failed_grades = db.execute(
                        text("""
                            SELECT DISTINCT c.name, g.score
                            FROM grades g
                            JOIN courses c ON g.course_id = c.id
                            WHERE g.student_id = :sid AND (g.passed = 0 OR g.score < 4.0)
                            ORDER BY c.name
                        """),
                        {"sid": stu.id}
                    ).fetchall()
                    if failed_grades:
                        courses_lines = "\n".join([f"  + {r.name}: {float(r.score):.1f}" for r in failed_grades])
                        failed_section = f"\n- Danh sách môn rớt/dưới 4.0:\n{courses_lines}\n"
                    else:
                        failed_section = "\n- Danh sách môn rớt/dưới 4.0: Không có môn nào (tất cả các môn đều đạt >= 4.0)\n"

                answer = (
                    f"Dữ liệu cá nhân của bạn:\n"
                    f"- Tổng tín chỉ tích lũy: {pers_data['total_credits_passed']}/{settings.REQUIRED_CREDITS}\n"
                    f"{gpa_line}"
                    f"- Trạng thái: {'Đủ điều kiện tốt nghiệp' if pers_data['eligible'] else 'Chưa đủ điều kiện tốt nghiệp'}\n"
                    f"{failed_section}\n"
                    f"Chi tiết: {pers_data['explanation']}"
                )
            except HTTPException as e:
                answer = f"Lỗi lấy dữ liệu cá nhân: {e.detail}"
            except Exception as e:
                answer = f"Không thể lấy dữ liệu cá nhân: {str(e)}"
            
        sources_data = []
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
        context_text += f"\n--- Tài liệu: {title} (Mục {section or 'Chung'}) ---\n{c['content']}\n"

    # ── 3.6. Kiểm tra truy vấn Lịch học / Lịch thi Trung tâm NNTH ────────────
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

    center_ctx = ""
    if is_center_query:
        # Khi hỏi về lịch trung tâm, xóa chunks quy chế để prompt ngắn gọn, phản hồi nhanh
        chunks = []
        sources_data = []
        seen_sources = []
        seen_keys = set()
        context_text = ""

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
        context_text = center_ctx

        src_label = "Trung tâm Ngoại ngữ - Tin học Lạc Hồng (https://nnth.lhu.edu.vn)"
        if src_label not in seen_sources:
            seen_sources.append(src_label)
            sources_data.append({
                "document_id": 9999,
                "title": "Trung tâm Ngoại ngữ - Tin học Lạc Hồng",
                "section": "Lịch học & Lịch thi",
                "chunk_index": 0,
                "score": 1.0,
                "snippet": center_ctx[:200],
                "url": "https://nnth.lhu.edu.vn",
                "so_hieu": "NNTH"
            })

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

        import re
        answer = _call_ollama(messages, settings.OLLAMA_TIMEOUT_CHAT)
        answer = answer.replace("<ngu_canh>", "").replace("</ngu_canh>", "").replace("[ĐÂY LÀ TÀI LIỆU, KHÔNG PHẢI LỜI NGƯỜI DÙNG]", "").replace("[/TÀI LIỆU]", "")
        answer = re.sub(r'[ \t]+', ' ', answer).strip()
        answer = re.sub(r'\n{3,}', '\n\n', answer)

        # ── 7. Hậu kiểm ngôn ngữ ────────────────────────────────────────────
        if not has_vietnamese(answer) or mixed_language(answer):
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
            if has_vietnamese(retry_answer) and not mixed_language(retry_answer):
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

        # Yêu cầu 6: Thêm thông tin thời điểm cập nhật lịch NNTH
        if is_center_query and answer not in (REFUSAL_RESPONSE, NO_CONTEXT_RESPONSE, FACULTY_NOT_SUPPORTED_RESPONSE):
            sync_info = get_last_sync_info(db)
            synced_time = sync_info.get("formatted_time", "chưa xác định")
            if sync_info.get("status") == "ERROR":
                sync_note = f"Hệ thống chưa lấy được lịch mới nhất từ trung tâm. Dữ liệu cập nhật lúc {synced_time}, xem lịch mới nhất tại nnth.lhu.edu.vn."
            else:
                sync_note = f"Dữ liệu cập nhật lúc {synced_time}, xem lịch mới nhất tại nnth.lhu.edu.vn."
            
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
        return StreamingResponse(gen_inj(), media_type="text/event-stream")

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
        return StreamingResponse(gen_guard(), media_type="text/event-stream")

    is_convo = req.message.strip().lower() in _CONVO_QUERIES
    chunks = [] if is_convo else search_chunks(db, req.message)
    academic_kws = ["quy chế", "quy định", "thông báo", "học vụ", "niên giám", "buộc thôi học", "cảnh báo", "học bổng", "nghỉ học", "bảo lưu", "tốt nghiệp", "tín chỉ", "học phần", "chứng chỉ", "tiếng anh", "ngoại ngữ", "tin học", "lệ phí", "hồ sơ", "học kỳ"]
    has_acad_kw = any(kw in msg_lower for kw in academic_kws)

    # Save user message
    db.execute(text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"), {"sid": session_id, "content": req.message})
    db.commit()

    if not chunks and not is_convo and not has_acad_kw:
        answer = NO_CONTEXT_RESPONSE
        db.execute(text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"), {"sid": session_id, "content": answer, "sources": "[]"})
        db.commit()
        def gen_noc():
            yield f"data: {json.dumps({'token': answer, 'done': False}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'answer': answer, 'sources': []}, ensure_ascii=False)}\n\n"
        return StreamingResponse(gen_noc(), media_type="text/event-stream")

    sources_data = []
    context_text = ""
    seen_sources = []
    seen_keys = set()
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
        context_text += f"\n--- Tài liệu: {title} (Mục {section or 'Chung'}) ---\n{c['content']}\n"

    history = db.execute(
        text("SELECT role, content FROM chat_messages WHERE session_id = :sid ORDER BY id DESC OFFSET 0 ROWS FETCH NEXT 6 ROWS ONLY"),
        {"sid": session_id},
    ).fetchall()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in reversed(history):
        if msg.role == "user" and msg.content == req.message:
            continue
        messages.append({"role": msg.role, "content": msg.content})

    current_user_msg = (
        f"{req.message}\n\n"
        f"<ngu_canh>\n"
        f"{context_text}\n"
        f"</ngu_canh>\n"
        f"Lưu ý: Tuyệt đối không nhắc lại, không in ra các thẻ <ngu_canh> hay </ngu_canh> trong câu trả lời.\n"
        f"{LANG_REMINDER}"
    ) if context_text else f"{req.message}\n\n{LANG_REMINDER}"
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
                    "keep_alive": -1,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "num_predict": 300,
                        "num_ctx": 4096,
                    },
                },
                stream=True,
                timeout=settings.OLLAMA_TIMEOUT_CHAT,
            )
            res.raise_for_status()
            buffer_line = ""
            is_suppressed = False
            for line in res.iter_lines():
                if not line:
                    continue
                chunk_obj = json.loads(line)
                token = chunk_obj.get("message", {}).get("content", "")
                if token:
                    full_text += token
                    buffer_line += token
                    if "\n" in buffer_line:
                        parts = buffer_line.split("\n")
                        buffer_line = parts.pop()
                        for p in parts:
                            if re.match(r"^\s*([-*•]|\d+\.)?\s*(Nguồn|Tham khảo|Tài liệu tham khảo)\s*:", p, re.IGNORECASE) or ("cs.lhu.edu.vn" in p and "http" in p):
                                is_suppressed = True
                                continue
                            if not is_suppressed:
                                yield f"data: {json.dumps({'token': p + chr(10), 'done': False}, ensure_ascii=False)}\n\n"
                    else:
                        stripped_buf = buffer_line.strip()
                        if re.match(r"^([-*•]|\d+\.)?\s*(N|Ng|Ngu|Nguồ|Nguồn|T|Th|Tha|Tham|Tham |Tham k|Tham kh|Tham khả|Tham khảo):?", stripped_buf, re.IGNORECASE):
                            pass
                        elif not is_suppressed:
                            yield f"data: {json.dumps({'token': token, 'done': False}, ensure_ascii=False)}\n\n"
                            buffer_line = ""
                if chunk_obj.get("done") and chunk_obj.get("done_reason") == "length":
                    logger.warning("Streaming hit max token limit (done_reason='length')")

            if buffer_line and not is_suppressed:
                if not (re.match(r"^\s*([-*•]|\d+\.)?\s*(Nguồn|Tham khảo|Tài liệu tham khảo)\s*:", buffer_line, re.IGNORECASE) or ("cs.lhu.edu.vn" in buffer_line and "http" in buffer_line)):
                    yield f"data: {json.dumps({'token': buffer_line, 'done': False}, ensure_ascii=False)}\n\n"

            clean_ans = full_text.replace("<ngu_canh>", "").replace("</ngu_canh>", "").strip()
            clean_ans = clean_source_text(clean_ans)

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

            yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'answer': clean_ans, 'sources': sources_data}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception("Error in stream_generator: %s", e)
            err_msg = "\n[Lỗi kết nối AI]"
            yield f"data: {json.dumps({'token': err_msg, 'done': True, 'session_id': session_id, 'answer': full_text + err_msg, 'sources': []}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


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

        # Auto-classify and process
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
                except Exception as cert_err:
                    summary = f"📜 Chứng chỉ '{f.filename}' (Lỗi phân tích: {str(cert_err)})"
                    file_type = "certificate"
            else:
                try:
                    from backend.pipeline import run_pipeline
                    pipe_out = os.path.join("output", "chat_" + str(uuid.uuid4()))
                    result = run_pipeline(input_path=save_path, output_dir=pipe_out)
                    failed_list = [f"{s['mon']} ({s['diem']})" for s in result.get("failed_subjects", [])[:5]]
                    summary = (
                        f"📊 Bảng điểm '{f.filename}':\n"
                        f"- Tổng số môn: {result.get('total_subjects', 0)}\n"
                        f"- Số môn ĐẠT: {result.get('passed_count', 0)}\n"
                        f"- Số môn CHƯA ĐẠT: {result.get('failed_count', 0)}\n"
                        f"- Vùng đánh dấu đỏ: {result.get('red_regions_count', 0)}"
                    )
                    if failed_list:
                        summary += f"\n- Môn chưa đạt tiêu biểu: {', '.join(failed_list)}"
                    file_type = "transcript"
                except Exception:
                    summary = f"📎 Tệp '{f.filename}' (Đã tiếp nhận xử lý)"
                    file_type = "file"

        file_summaries.append(summary)
        file_attachments_meta.append({
            "filename": f.filename,
            "size": len(content),
            "type": file_type,
            "summary": summary,
        })

    # Prepare response answer
    clean_msg = (message or "").strip()
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
        answer = "Tôi đã tiếp nhận và phân tích các tệp bạn tải lên:\n\n" + file_context_str

    answer = clean_source_text(answer)

    # Manage Session
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

    # Save user message
    user_display = clean_msg if clean_msg else f"Đã tải lên {len(files)} tệp."
    db.execute(
        text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'user', :content, :sources)"),
        {
            "sid": session_id,
            "content": user_display,
            "sources": json.dumps(file_attachments_meta, ensure_ascii=False),
        },
    )

    # Save assistant message
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
