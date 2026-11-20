"""
backend/app/services/query_rewriter.py
Module viết lại câu hỏi (Query Rewriting) dựa trên lịch sử hội thoại và hồ sơ sinh viên.

Quy tắc:
1. CHỈ chạy rewriter khi:
   - Có lịch sử trò chuyện (history >= 1 tin nhắn), VÀ
   - Câu hỏi ngắn (<= 25 từ) hoặc chứa từ ngữ phụ thuộc ngữ cảnh ("môn đó", "môn này", "nó", "còn...", "kỳ nào", "bao nhiêu").
2. Nếu câu hỏi đã độc lập, đầy đủ ngữ cảnh hoặc không có lịch sử: BỎ QUA, trả về câu hỏi gốc ngay lập tức.
3. Khi gọi LLM: Sử dụng REWRITE_MODEL (mặc định cấu hình), temperature = 0.0, prompt ngắn gọn.
"""

import re
import logging
import requests
from typing import List, Dict, Any, Optional

from backend.app.config import settings

logger = logging.getLogger(__name__)

# Các từ khóa / đại từ phụ thuộc ngữ cảnh hội thoại trước
CONTEXT_DEPENDENT_TRIGGERS = [
    "môn đó", "mon do", "môn này", "mon nay", "môn kia", "mon kia",
    "môn đấy", "mon day", "môn ấy", "mon ay",
    "nó", "no", "còn môn", "con mon", "thế còn", "the con",
    "kỳ nào", "ky nao", "kỳ mấy", "ky may", "học kỳ nào", "hoc ky nao",
    "bao nhiêu", "bao nhieu", "được không", "duoc khong", "sao ạ", "sao a",
    "học lại thế nào", "hoc lai the nao", "thi lại thế nào", "thi lai the nao",
    "tiên quyết", "tien quyet", "bị chặn", "bi chan"
]


def needs_rewriting(query: str, history: List[Dict[str, str]]) -> bool:
    """
    Kiểm tra xem câu hỏi có cần viết lại hay không:
    - Bắt buộc phải có ít nhất 1 tin nhắn lịch sử phía trước.
    - Câu hỏi ngắn (<= 25 từ) HOẶC chứa từ khóa phụ thuộc ngữ cảnh.
    """
    if not query or not history:
        return False

    q_clean = query.strip()
    words = q_clean.split()

    # Nếu câu hỏi quá dài (> 25 từ) và không chứa từ ngữ phụ thuộc ngữ cảnh thì đã đủ thông tin
    is_short = len(words) <= 25
    q_lower = q_clean.lower()
    has_trigger = any(tr in q_lower for tr in CONTEXT_DEPENDENT_TRIGGERS)

    return is_short or has_trigger


def rewrite_academic_query(
    query: str,
    history: List[Dict[str, str]],
    profile: Optional[Dict[str, Any]] = None,
    timeout: int = 20
) -> str:
    """
    Viết lại câu hỏi ngắn/mơ hồ thành câu hỏi học vụ đầy đủ, độc lập.
    Nếu không thỏa điều kiện thì trả về nguyên bản query.
    """
    if not needs_rewriting(query, history):
        return query

    # Lấy 2-4 lượt tin nhắn gần nhất để làm ngữ cảnh
    recent_history = history[-4:]
    history_lines = []
    for m in recent_history:
        role = "Sinh viên" if m.get("role") == "user" else "Trợ lý"
        content = m.get("content", "").strip()
        # Rút ngắn nếu tin nhắn trước quá dài
        if len(content) > 150:
            content = content[:150] + "..."
        history_lines.append(f"{role}: {content}")
    history_context = "\n".join(history_lines)

    # Lấy thông tin các môn học được nhắc tới trong profile (nếu có)
    profile_summary = ""
    if profile:
        courses = profile.get("courses") or profile.get("failed_courses") or []
        course_names = []
        for c in courses[:6]:
            c_name = c.get("ten_mon") or c.get("mon") or c.get("course_name") or ""
            c_code = c.get("ma_mon") or c.get("course_code") or ""
            if c_name:
                course_names.append(f"{c_name} ({c_code})" if c_code else c_name)
        if course_names:
            profile_summary = "Môn học liên quan của sinh viên: " + ", ".join(course_names)

    prompt = (
        "Bạn là trợ lý viết lại câu hỏi học vụ. Nhiệm vụ: Viết lại câu hỏi sau của sinh viên thành một câu hỏi ĐỘC LẬP, RÕ RÀNG, ĐẦY ĐỦ TÊN MÔN HỌC hoặc chủ đề học vụ dựa trên đoạn hội thoại trước đó.\n"
        "Quy tắc tuyệt đối:\n"
        "1. CHỈ xuất ra câu hỏi đã viết lại, không thêm lời chào, không giải thích.\n"
        "2. Giữ nguyên ý định của sinh viên.\n"
        "3. Nếu câu hỏi đã rõ ràng, hãy giữ nguyên.\n\n"
        f"Lịch sử hội thoại gần nhất:\n{history_context}\n"
    )
    if profile_summary:
        prompt += f"{profile_summary}\n"
    prompt += f"\nCâu hỏi cần viết lại: {query}\nCâu hỏi độc lập hoàn chỉnh:"

    try:
        model = getattr(settings, "REWRITE_MODEL", getattr(settings, "LLM_MODEL", "qwen2.5:3b"))
        res = requests.post(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": getattr(settings, "REWRITE_TEMPERATURE", 0.0),
                    "num_predict": 100,
                    "num_ctx": 1024
                },
                "keep_alive": getattr(settings, "KEEP_ALIVE", "15m")
            },
            timeout=timeout
        )
        if res.status_code == 200:
            data = res.json()
            rewritten = data.get("response") or data.get("message", {}).get("content", "")
            rewritten = str(rewritten).strip()
            # Làm sạch các ký tự bao quanh như ngoặc kép
            rewritten = re.sub(r'^["\']|["\']$', '', rewritten).strip()
            if rewritten and len(rewritten) > 3 and not rewritten.lower().startswith("câu hỏi"):
                logger.info(f"Query rewriter: '{query}' -> '{rewritten}'")
                return rewritten
    except Exception as e:
        logger.warning(f"Lỗi khi gọi query rewriter: {e}. Sử dụng câu hỏi gốc.")

    return query
