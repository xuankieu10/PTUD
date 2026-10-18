import json
import logging
import os
import shutil
import uuid
import requests
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict, Any

from backend.app.db import get_db
from backend.app.deps import get_current_user
from backend.app.config import settings
from backend.app.services.retrieval import search_chunks
from backend.app.prompts import (
    SYSTEM_PROMPT, NO_CONTEXT_RESPONSE, REFUSAL_RESPONSE,
    LANG_REMINDER, LANG_RETRY_SYSTEM,
    is_injection, has_vietnamese, mixed_language
)
from backend.app.routers.students import graduation_check

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


def _call_ollama(messages: list, timeout: int) -> str:
    """Gọi Ollama và trả về nội dung trả lời. Ném HTTPException nếu lỗi."""
    try:
        res = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.LLM_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=timeout,
        )
        res.raise_for_status()
        return res.json()["message"]["content"]
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

    # ── 3. Retrieval ──────────────────────────────────────────────────────────
    is_convo = req.message.strip().lower() in _CONVO_QUERIES
    query_for_embedding = req.message
    chunks = [] if is_convo else search_chunks(db, query_for_embedding)

    max_score = max((c["score"] for c in chunks), default=0.0)
    
    msg_lower = req.message.lower()
    personal_kws = ["điểm", "tín chỉ", "tốt nghiệp", "lịch học", "thời khóa biểu", "điểm rèn luyện", "học phí", "môn", "rớt", "nợ", "dưới"]
    personal_refs = ["tôi", "của tôi", "mình", "em", "bản thân", "của em"]
    academic_kws = ["quy chế", "quy định", "thông báo", "học vụ", "niên giám", "buộc thôi học", "cảnh báo", "học bổng", "nghỉ học", "bảo lưu"]
    
    has_personal_kw = any(kw in msg_lower for kw in personal_kws)
    has_personal_ref = any(ref in msg_lower for ref in personal_refs)
    has_acad_kw = any(kw in msg_lower for kw in academic_kws)
    
    if has_personal_kw and has_personal_ref:
        intent = "personal"
    elif has_acad_kw or max_score >= settings.MIN_SCORE_THRESHOLD:
        intent = "general"
    elif is_convo:
        intent = "convo"
    else:
        intent = "off_topic"

    if intent == "off_topic":
        answer = REFUSAL_RESPONSE
        sources_data = []
        # Save and return
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
            text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"),
            {"sid": session_id, "content": answer, "sources": "[]"},
        )
        db.commit()
        return {"session_id": session_id, "answer": answer, "sources": []}

    sources_data = []
    context_text = ""
    seen_sources = set()
    for c in chunks:
        # Check if source has source_url and fetched_at from document
        # Wait, chunks from search_chunks include document_id, title, score, chunk_index, content
        # We need source_url and fetched_at
        # Let's get it from the DB
        doc = db.execute(
            text("SELECT source_url, fetched_at FROM documents WHERE id = :did"),
            {"did": c["document_id"]}
        ).fetchone()
        
        source_url = doc.source_url if doc and hasattr(doc, "source_url") else None
        fetched_at = doc.fetched_at if doc and hasattr(doc, "fetched_at") else None
        
        sources_data.append({
            "document_id": c["document_id"],
            "title": c["title"],
            "chunk_index": c["chunk_index"],
            "score": c["score"],
            "snippet": c["content"][:200],
            "source_url": source_url,
            "fetched_at": str(fetched_at) if fetched_at else None
        })
        context_text += f"\n--- Tài liệu: {c['title']} ---\n{c['content']}\n"
        
        if source_url and fetched_at:
            seen_sources.add(f"Nguồn: {c['title']} ({source_url}, cập nhật {fetched_at})")
        else:
            seen_sources.add(f"Nguồn: {c['title']}")

    # ── 4. Lưu câu hỏi gốc vào DB ────────────────────────────────────────────
    db.execute(
        text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"),
        {"sid": session_id, "content": req.message},
    )
    db.commit()

    # ── 5. Trả NO_CONTEXT nếu không có RAG và không phải câu hội thoại ───────
    if not chunks and not is_convo and not has_acad_kw:
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

        # Remove "Nguồn:" generated by LLM if present
        answer = re.sub(r'(?i)\n*Nguồn:.*$', '', answer).strip()
        
        if has_acad_kw and answer == REFUSAL_RESPONSE:
            answer = NO_CONTEXT_RESPONSE
            sources_data = []
            seen_sources = set()

        if answer not in (REFUSAL_RESPONSE, NO_CONTEXT_RESPONSE):
            ans_words = set(re.findall(r'\w+', answer.lower()))
            stop_words = {"là", "và", "của", "có", "trong", "các", "một", "cho", "với", "không", "những", "được", "người", "về", "từ", "đó", "đây", "cũng", "như", "sẽ", "lại", "tại", "đã", "ra", "hay", "đến", "để", "nhưng", "còn", "này", "lúc", "nào", "rồi", "phải", "đang", "do", "thế", "nên", "tôi", "bạn", "chỉ", "hỗ", "trợ", "tư", "vấn", "dựa", "trên", "tài", "liệu", "xin", "lỗi", "không", "tìm", "thấy", "thông", "tin", "vui", "lòng", "liên", "hệ", "theo", "của", "nhà", "trường", "dựa"}
            content_words = ans_words - stop_words
            
            if content_words:
                chunk_text_lower = " ".join([c["content"] for c in chunks]).lower()
                matched = sum(1 for w in content_words if w in chunk_text_lower)
                if matched / len(content_words) < 0.3:
                    answer = NO_CONTEXT_RESPONSE
                    sources_data = []
                    seen_sources = set()
        
        # Append our own sources
        if seen_sources and answer not in (REFUSAL_RESPONSE, NO_CONTEXT_RESPONSE):
            answer += "\n\n" + "\n".join(seen_sources)

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
        results.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
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
    if clean_msg:
        context_str = "\n\n".join(file_summaries)
        combined_prompt = (
            f"{clean_msg}\n\n"
            f"[THÔNG TIN CÁC TỆP ĐÍNH KÈM ĐÃ PHÂN TÍCH]:\n{context_str}\n\n"
            f"Hãy trả lời câu hỏi của người dùng dựa trên thông tin các tệp trên một cách ngắn gọn, súc tích và chính xác bằng tiếng Việt."
        )
        try:
            messages_llm = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": combined_prompt}
            ]
            answer = _call_ollama(messages_llm, settings.OLLAMA_TIMEOUT_CHAT)
        except Exception:
            answer = f"Tôi đã phân tích các tệp bạn gửi:\n\n{context_str}\n\nĐối với câu hỏi '{clean_msg}': Vui lòng xem thông tin chi tiết các môn học và chứng chỉ ở trên."
    else:
        answer = "Tôi đã tiếp nhận và phân tích các tệp bạn tải lên:\n\n" + "\n\n".join(file_summaries)

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
            "sources": json.dumps(file_attachments_meta, ensure_ascii=False),
        },
    )
    db.commit()

    return {
        "session_id": session_id,
        "answer": answer,
        "sources": file_attachments_meta,
        "files": file_attachments_meta,
    }
