import json
import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional

from backend.app.db import get_db
from backend.app.deps import get_current_user
from backend.app.config import settings
from backend.app.services.retrieval import search_chunks
from backend.app.prompts import SYSTEM_PROMPT, NO_CONTEXT_RESPONSE

router = APIRouter(prefix="/chat", tags=["chat"])

from pydantic import BaseModel, Field, field_validator

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[int] = None

    @field_validator('message')
    @classmethod
    def message_must_not_be_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty or just whitespace")
        return v

@router.post("")
def chat(req: ChatRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    
    # 1. Quản lý Session
    session_id = req.session_id
    if not session_id:
        title = req.message[:50] + ("..." if len(req.message) > 50 else "")
        session_id = db.execute(
            text("INSERT INTO chat_sessions (user_id, title) OUTPUT INSERTED.id VALUES (:uid, :title)"),
            {"uid": user_id, "title": title}
        ).scalar()
        db.commit()
    else:
        # Validate session belongs to user
        sess = db.execute(text("SELECT id FROM chat_sessions WHERE id = :sid AND user_id = :uid"), {"sid": session_id, "uid": user_id}).fetchone()
        if not sess:
            raise HTTPException(status_code=403, detail="Session not found or forbidden")
            
    # 2. Retrieval
    try:
        chunks = search_chunks(db, req.message)
    except Exception as e:
        raise HTTPException(status_code=504, detail=f"Ollama (embedding) không phản hồi hoặc quá tải: {str(e)}")
    
    sources_data = []
    context_text = ""
    for c in chunks:
        sources_data.append({
            "document_id": c["document_id"],
            "title": c["title"],
            "chunk_index": c["chunk_index"],
            "score": c["score"],
            "snippet": c["content"][:200]
        })
        context_text += f"\n--- Tài liệu: {c['title']} ---\n{c['content']}\n"
        
    # Lưu câu hỏi của User
    db.execute(
        text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', :content)"),
        {"sid": session_id, "content": req.message}
    )
    db.commit()
    
    # 3. Call LLM
    if not chunks:
        answer = NO_CONTEXT_RESPONSE
    else:
        # Lấy lịch sử (3 tin nhắn gần nhất)
        history = db.execute(
            text("SELECT role, content FROM chat_messages WHERE session_id = :sid ORDER BY id DESC OFFSET 0 ROWS FETCH NEXT 6 ROWS ONLY"),
            {"sid": session_id}
        ).fetchall()
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Đảo ngược lịch sử để đúng thứ tự
        for msg in reversed(history):
            if msg.role == "user" and msg.content == req.message:
                continue # bỏ qua tin nhắn vừa gửi vì sẽ custom lại
            messages.append({"role": msg.role, "content": msg.content})
            
        # Thêm câu hỏi kèm ngữ cảnh
        prompt_with_context = f"NGỮ CẢNH:\n{context_text}\n\nCÂU HỎI:\n{req.message}"
        messages.append({"role": "user", "content": prompt_with_context})
        
        try:
            res = requests.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.LLM_MODEL,
                    "messages": messages,
                    "stream": False
                },
                timeout=settings.OLLAMA_TIMEOUT_CHAT
            )
            res.raise_for_status()
            answer = res.json()["message"]["content"]
        except Exception as e:
            raise HTTPException(status_code=504, detail=f"Ollama không phản hồi hoặc quá tải: {str(e)}")
            
    # Lưu câu trả lời
    db.execute(
        text("INSERT INTO chat_messages (session_id, role, content, sources) VALUES (:sid, 'assistant', :content, :sources)"),
        {"sid": session_id, "content": answer, "sources": json.dumps(sources_data, ensure_ascii=False)}
    )
    db.commit()
    
    return {
        "session_id": session_id,
        "answer": answer,
        "sources": sources_data
    }

@router.get("/sessions")
def get_sessions(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if current_user["role"] == "admin":
        sql = "SELECT id, user_id, title, created_at FROM chat_sessions ORDER BY id DESC"
        params = {}
    else:
        sql = "SELECT id, user_id, title, created_at FROM chat_sessions WHERE user_id = :uid ORDER BY id DESC"
        params = {"uid": user_id}
        
    sessions = db.execute(text(sql), params).fetchall()
    return [{"id": s.id, "user_id": s.user_id, "title": s.title, "created_at": s.created_at} for s in sessions]

@router.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    
    # Check permission
    sess = db.execute(text("SELECT user_id FROM chat_sessions WHERE id = :sid"), {"sid": session_id}).fetchone()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if current_user["role"] != "admin" and sess.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    messages = db.execute(text("SELECT id, role, content, sources, created_at FROM chat_messages WHERE session_id = :sid ORDER BY id ASC"), {"sid": session_id}).fetchall()
    
    results = []
    for m in messages:
        src = []
        if m.sources:
            try:
                src = json.loads(m.sources)
            except:
                pass
        results.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "sources": src,
            "created_at": m.created_at
        })
    return results
