import os
import shutil
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.db import get_db
from backend.app.deps import get_current_user
from backend.pipeline import run_pipeline
from backend.normalize import normalize_transcript
from backend.ocr_extractor import DEFAULT_VISION_MODEL, DEFAULT_OLLAMA_HOST

router = APIRouter(prefix="/transcripts", tags=["transcripts"])
UPLOAD_DIR = os.path.abspath("temp_uploads")

@router.post("/import")
async def import_transcript(
    student_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    model: str = Form(DEFAULT_VISION_MODEL),
    host: str = Form(DEFAULT_OLLAMA_HOST),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Check permissions
    if current_user["role"] == "student":
        stu = db.execute(text("SELECT id FROM students WHERE user_id = :uid"), {"uid": current_user["id"]}).fetchone()
        if not stu:
            raise HTTPException(status_code=403, detail="Student record not found")
        # If student didn't provide student_id, use their own. If they provided one, it must match.
        if student_id is not None and stu.id != student_id:
            raise HTTPException(status_code=403, detail="Not enough permissions to import for this student")
        student_id = stu.id
    else:
        # Admin must provide student_id
        if student_id is None:
            raise HTTPException(status_code=400, detail="Admin must provide student_id")
            
    # Check if student exists
    stu_check = db.execute(text("SELECT id FROM students WHERE id = :sid"), {"sid": student_id}).fetchone()
    if not stu_check:
        raise HTTPException(status_code=404, detail="Student not found")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
        raise HTTPException(status_code=400, detail="Invalid file format")

    session_id = str(uuid.uuid4())
    session_upload_dir = os.path.join(UPLOAD_DIR, session_id)
    session_output_dir = os.path.join(os.path.abspath("output"), session_id)
    os.makedirs(session_upload_dir, exist_ok=True)
    os.makedirs(session_output_dir, exist_ok=True)

    input_file_path = os.path.join(session_upload_dir, file.filename)

    try:
        with open(input_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Run old OCR pipeline
        result = run_pipeline(
            input_path=input_file_path,
            output_dir=session_output_dir,
            model=model,
            host=host
        )

        normalized_data = normalize_transcript(result["all_subjects"])
        parsed_courses = normalized_data.get("courses", [])

        # Match with DB courses and upsert to grades
        imported = []
        unmatched = []

        db_courses = db.execute(text("SELECT id, code, name FROM courses")).fetchall()
        course_map = {c.code.upper(): c.id for c in db_courses}
        # Also try to match by name
        course_name_map = {c.name.lower(): c.id for c in db_courses}

        for c in parsed_courses:
            code = c.get("code", "").upper()
            name = c.get("name", "").lower()
            grade = float(c.get("grade", 0))
            semester = c.get("semester", "Unknown")
            passed = 1 if not c.get("is_failed") else 0
            
            c_id = course_map.get(code)
            if not c_id:
                c_id = course_name_map.get(name)
                
            if c_id:
                # Upsert
                upsert_sql = """
                    MERGE grades AS target
                    USING (SELECT :sid AS student_id, :cid AS course_id, :sem AS semester) AS source
                    ON (target.student_id = source.student_id AND target.course_id = source.course_id AND target.semester = source.semester)
                    WHEN MATCHED THEN
                        UPDATE SET score = :score, passed = :passed, source = 'ocr'
                    WHEN NOT MATCHED THEN
                        INSERT (student_id, course_id, score, semester, passed, source)
                        VALUES (:sid, :cid, :score, :sem, :passed, 'ocr');
                """
                db.execute(text(upsert_sql), {
                    "sid": student_id, "cid": c_id, "sem": semester,
                    "score": grade, "passed": passed
                })
                imported.append(c)
            else:
                unmatched.append(c)
                
        db.commit()

        return {
            "success": True,
            "imported_count": len(imported),
            "unmatched_count": len(unmatched),
            "imported": imported,
            "unmatched": unmatched
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

