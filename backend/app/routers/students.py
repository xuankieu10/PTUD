from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import requests

from backend.app.db import get_db
from backend.app.deps import get_current_user
from backend.app.config import settings

router = APIRouter(prefix="/students", tags=["students"])

@router.get("/{student_id}/graduation-check")
def graduation_check(student_id: int, explain: bool = False, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # 1. Check permission
    if current_user["role"] != "admin":
        stu = db.execute(text("SELECT id FROM students WHERE user_id = :uid"), {"uid": current_user["id"]}).fetchone()
        if not stu or stu.id != student_id:
            raise HTTPException(status_code=403, detail="Not enough permissions")
            
    # 2. Get student info
    student = db.execute(text("SELECT id, student_code, full_name, major, cohort FROM students WHERE id = :sid"), {"sid": student_id}).fetchone()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    student_data = {
        "id": student.id,
        "student_code": student.student_code,
        "full_name": student.full_name,
        "major": student.major,
        "cohort": student.cohort
    }
    
    # 3. Get all courses passed (distinct by course_id in case of retakes)
    passed_courses_sql = """
        SELECT DISTINCT c.id, c.code, c.name, c.credits
        FROM grades g
        JOIN courses c ON g.course_id = c.id
        WHERE g.student_id = :sid AND g.passed = 1
    """
    passed_rows = db.execute(text(passed_courses_sql), {"sid": student_id}).fetchall()
    passed_course_ids = set([r.id for r in passed_rows])
    total_credits_passed = sum([r.credits for r in passed_rows])
    
    # 4. Get missing required courses
    required_sql = """
        SELECT c.id, c.code, c.name, c.credits
        FROM program_courses pc
        JOIN courses c ON pc.course_id = c.id
        WHERE pc.major = :major AND pc.is_required = 1
    """
    required_rows = db.execute(text(required_sql), {"major": student.major}).fetchall()
    
    missing_required = []
    for r in required_rows:
        if r.id not in passed_course_ids:
            missing_required.append({"code": r.code, "name": r.name, "credits": r.credits})
            
    # 5. Get failed courses (courses with passed=0 and not in passed_course_ids)
    failed_sql = """
        SELECT DISTINCT c.id, c.code, c.name, c.credits
        FROM grades g
        JOIN courses c ON g.course_id = c.id
        WHERE g.student_id = :sid AND g.passed = 0
    """
    failed_rows = db.execute(text(failed_sql), {"sid": student_id}).fetchall()
    
    failed_courses = []
    for f in failed_rows:
        if f.id not in passed_course_ids:
            failed_courses.append({"code": f.code, "name": f.name, "credits": f.credits})
            
    # 6. Check eligibility
    required_credits = settings.REQUIRED_CREDITS
    credits_missing = max(0, required_credits - total_credits_passed)
    
    eligible = False
    if total_credits_passed >= required_credits and len(missing_required) == 0:
        eligible = True
        
    notes = "Đủ điều kiện tốt nghiệp" if eligible else "Chưa đủ điều kiện tốt nghiệp"
    
    response_data = {
        "student": student_data,
        "total_credits_passed": total_credits_passed,
        "required_credits": required_credits,
        "credits_missing": credits_missing,
        "missing_required_courses": missing_required,
        "failed_courses": failed_courses,
        "eligible": eligible,
        "notes": notes
    }
    
    # 7. LLM Explain (Optional)
    if explain:
        prompt = f"""
Bạn là chuyên viên tư vấn học vụ. Dựa vào số liệu sau, hãy giải thích ngắn gọn bằng tiếng Việt (không dùng định dạng markdown phức tạp, chỉ text thuần) cho sinh viên {student.full_name} vì sao họ {'ĐỦ' if eligible else 'CHƯA ĐỦ'} điều kiện tốt nghiệp.
- Tổng tín chỉ yêu cầu: {required_credits}
- Tổng tín chỉ tích lũy: {total_credits_passed}
- Số môn bắt buộc còn thiếu: {len(missing_required)} (gồm: {', '.join([m['name'] for m in missing_required]) if missing_required else 'Không'})
- Số môn đang nợ (điểm F): {len(failed_courses)} (gồm: {', '.join([f['name'] for f in failed_courses]) if failed_courses else 'Không'})
        """
        try:
            res = requests.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.LLM_MODEL,
                    "prompt": prompt,
                    "stream": False
                }
            )
            res.raise_for_status()
            response_data["explanation"] = res.json()["response"]
        except Exception as e:
            response_data["explanation"] = f"Lỗi gọi LLM giải thích: {str(e)}"

    return response_data
