from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import requests
import logging

from backend.app.db import get_db
from backend.app.deps import get_current_user
from backend.app.config import settings
from backend.app.services.retrieval import strip_accents

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/students", tags=["students"])


def is_supported_major(major: Optional[str], db: Session) -> bool:
    """Kiểm tra ngành học có thuộc chương trình đào tạo (program_courses) trong DB hay không."""
    if not major:
        return False
    norm_major = strip_accents(str(major).strip().lower())
    if not norm_major or norm_major in ["chua cap nhat", "chua xac dinh nganh", "chua xac dinh"]:
        return False

    supported = []
    try:
        rows = db.execute(text("SELECT DISTINCT major FROM program_courses")).fetchall()
        supported = [r[0] for r in rows if r and r[0]]
    except Exception as e:
        logger.warning("Không thể lấy danh sách ngành từ program_courses: %s", e)

    if not supported:
        supported = ["Công nghệ thông tin"]

    for s in supported:
        norm_s = strip_accents(str(s).strip().lower())
        if norm_major == norm_s:
            return True
        if norm_major in ["cntt", "it"] and "thong tin" in norm_s:
            return True

    return False


def calculate_graduation_data(
    target_student_id: int,
    db: Session,
    explain: bool = False,
    lhu_data: Optional[dict] = None
) -> dict:
    """
    Tính toán toàn bộ thông tin xét tốt nghiệp dựa trên students.id chuẩn:
    - Tín chỉ tích lũy đã đạt
    - Tín chỉ chưa đạt (nợ điểm/môn rớt)
    - Tín chỉ còn thiếu theo chuẩn CTĐT
    - Danh sách môn bắt buộc còn thiếu theo CTĐT
    - Danh sách môn chưa đạt (điểm F / passed=0)
    - Hỗ trợ ưu tiên dữ liệu trực tiếp từ Cổng trường LHU (lhu_data) khi sinh viên đã liên kết tài khoản.
    """
    # 1. Lấy thông tin sinh viên
    student = db.execute(
        text("SELECT id, user_id, student_code, full_name, major, cohort FROM students WHERE id = :sid"),
        {"sid": target_student_id}
    ).fetchone()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if not is_supported_major(student.major, db):
        major_str = str(student.major or "").strip()
        norm_major = strip_accents(major_str.lower())
        if not major_str or norm_major in ["chua cap nhat", "chua xac dinh nganh", "chua xac dinh"]:
            raise HTTPException(
                status_code=400,
                detail="Hệ thống hiện chưa xác định được chương trình đào tạo cho lớp/ngành của bạn. Vui lòng liên hệ Phòng Đào tạo hoặc Văn phòng Khoa để được hỗ trợ."
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Hệ thống hiện chưa hỗ trợ ngành này ({student.major}). Chương trình đào tạo chỉ áp dụng cho Khoa Công nghệ thông tin."
            )

    student_data = {
        "id": student.id,
        "user_id": student.user_id,
        "student_code": student.student_code,
        "full_name": student.full_name,
        "major": student.major,
        "cohort": student.cohort
    }

    # Lấy danh sách môn bắt buộc theo CTĐT
    required_sql = """
        SELECT c.id, c.code, c.name, c.credits
        FROM program_courses pc
        JOIN courses c ON pc.course_id = c.id
        WHERE pc.major = :major AND pc.is_required = 1
    """
    required_rows = db.execute(text(required_sql), {"major": student.major}).fetchall()

    if lhu_data and "reconciled_courses" in lhu_data:
        # NGUỒN ƯU TIÊN: Dữ liệu bảng điểm đã chuẩn hóa & đối chiếu từ LHU Portal
        lhu_courses = lhu_data["reconciled_courses"]
        passed_lhu = [c for c in lhu_courses if c.get("status") == "passed"]
        failed_lhu = [c for c in lhu_courses if c.get("status") == "failed"]

        passed_codes = {str(c.get("code") or c.get("ma_mon") or "").upper() for c in passed_lhu if (c.get("code") or c.get("ma_mon"))}
        passed_names = {strip_accents(str(c.get("name") or c.get("ten_mon") or "")).lower() for c in passed_lhu if (c.get("name") or c.get("ten_mon"))}

        total_credits_passed = sum(c.get("credits") or c.get("tin_chi") or 0 for c in passed_lhu)

        # Môn bắt buộc còn thiếu
        missing_required = []
        for r in required_rows:
            r_code = (getattr(r, "code", None) or (r[1] if isinstance(r, tuple) and len(r) > 1 else "") or "").upper()
            r_name = strip_accents(getattr(r, "name", None) or (r[2] if isinstance(r, tuple) and len(r) > 2 else "") or "").lower()
            r_credits = getattr(r, "credits", None) or (r[3] if isinstance(r, tuple) and len(r) > 3 else 0)
            if r_code not in passed_codes and r_name not in passed_names:
                missing_required.append({"code": r_code, "name": r_name, "credits": r_credits})

        # Môn chưa đạt (môn rớt chưa học lại đạt)
        failed_courses = []
        for f in failed_lhu:
            f_code = (f.get("code") or f.get("ma_mon") or "").upper()
            f_name = strip_accents(str(f.get("name") or f.get("ten_mon") or "")).lower()
            if f_code not in passed_codes and f_name not in passed_names:
                failed_courses.append({
                    "code": f.get("code") or f.get("ma_mon") or "",
                    "name": f.get("name") or f.get("ten_mon") or "",
                    "credits": f.get("credits") or f.get("tin_chi") or 0,
                    "grade": float(f.get("grade") if f.get("grade") is not None else (f.get("diem") or 0.0))
                })
        total_credits_failed = sum(f["credits"] for f in failed_courses)

    else:
        # FALLBACK: Lấy từ CSDL (bảng grades) như cũ
        passed_courses_sql = """
            SELECT DISTINCT c.id, c.code, c.name, c.credits
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            WHERE g.student_id = :sid AND g.passed = 1
        """
        passed_rows = db.execute(text(passed_courses_sql), {"sid": target_student_id}).fetchall()
        passed_course_ids = set([r.id for r in passed_rows])
        total_credits_passed = sum([r.credits for r in passed_rows])

        missing_required = []
        for r in required_rows:
            if r.id not in passed_course_ids:
                missing_required.append({"code": r.code, "name": r.name, "credits": r.credits})

        failed_sql = """
            SELECT DISTINCT c.id, c.code, c.name, c.credits, g.score
            FROM grades g
            JOIN courses c ON g.course_id = c.id
            WHERE g.student_id = :sid AND g.passed = 0
        """
        failed_rows = db.execute(text(failed_sql), {"sid": target_student_id}).fetchall()

        failed_courses = []
        for f in failed_rows:
            if f.id not in passed_course_ids:
                failed_courses.append({
                    "code": f.code,
                    "name": f.name,
                    "credits": f.credits,
                    "grade": float(f.score) if f.score is not None else 0.0
                })
        total_credits_failed = sum([f["credits"] for f in failed_courses])

    # 5. Kiểm tra chứng chỉ ngoại ngữ và tin học
    has_english_cert = False
    has_it_cert = False
    english_cert_name = None
    it_cert_name = None
    english_incomplete_name = None
    it_incomplete_name = None
    other_incomplete_certs = []

    if lhu_data and "certificates" in lhu_data:
        # NGUỒN ƯU TIÊN: Chứng chỉ từ Cổng trường LHU
        for c in lhu_data["certificates"]:
            c_name = str(c.get("ten") or "").strip()
            c_type = str(c.get("loai") or "").strip()
            c_norm = strip_accents(f"{c_name} {c_type}").lower()
            hoan_tat = bool(c.get("hoan_tat"))

            is_nn = any(k in c_norm for k in ["ngoai ngu", "tieng anh", "english", "nn", "toeic", "ielts", "b1"])
            is_it = any(k in c_norm for k in ["tin hoc", "cntt", "it", "th", "ic3", "mos", "tin hoc van phong"])

            if is_nn:
                if hoan_tat:
                    has_english_cert = True
                    english_cert_name = c_name or "Chứng chỉ Ngoại ngữ LHU"
                else:
                    english_incomplete_name = c_name
            elif is_it:
                if hoan_tat:
                    has_it_cert = True
                    it_cert_name = c_name or "Chứng chỉ Tin học LHU"
                else:
                    it_incomplete_name = c_name
            else:
                if not hoan_tat:
                    other_incomplete_certs.append(c_name)

    else:
        # FALLBACK: Kiểm tra từ bảng student_certificates trong DB
        try:
            check_table = db.execute(text("SELECT OBJECT_ID('student_certificates', 'U')")).scalar()
            if check_table is not None:
                cert_rows = db.execute(
                    text("""
                        SELECT certificate_type, certificate_name, status
                        FROM student_certificates
                        WHERE student_id = :sid
                    """),
                    {"sid": target_student_id}
                ).fetchall()
                for c in cert_rows:
                    c_type_raw = (c.certificate_type or "").strip()
                    c_name_raw = (c.certificate_name or "").strip()
                    c_type_norm = strip_accents(c_type_raw).lower()
                    c_name_norm = strip_accents(c_name_raw).lower()
                    c_status = (c.status or "valid").strip().lower()
                    is_valid = c_status in ["valid", "đạt", "dat", "passed", "hoàn thành", "hoan thanh", "active"]

                    if is_valid:
                        if any(k in c_type_norm or k in c_name_norm or k in c_type_raw.lower() or k in c_name_raw.lower() for k in ["ngoai ngu", "ngoại ngữ", "ngo?i ng?", "tieng anh", "tiếng anh", "ti?ng anh", "english", "nn", "toeic", "ielts", "b1"]):
                            has_english_cert = True
                            english_cert_name = c.certificate_name or "Chứng chỉ Ngoại ngữ"
                        if any(k in c_type_norm or k in c_name_norm or k in c_type_raw.lower() or k in c_name_raw.lower() for k in ["tin hoc", "tin học", "tin h?c", "cntt", "it", "th", "ic3", "mos", "tin hoc van phong"]):
                            has_it_cert = True
                            it_cert_name = c.certificate_name or "Chứng chỉ Tin học"
        except Exception as e:
            logger.error(f"Lỗi truy vấn student_certificates cho student {target_student_id}: {e}", exc_info=True)

    # 6. Kiểm tra điều kiện tốt nghiệp
    required_credits = settings.REQUIRED_CREDITS
    credits_missing = max(0, required_credits - total_credits_passed)

    eligible = bool(
        total_credits_passed >= required_credits
        and len(missing_required) == 0
        and has_english_cert
        and has_it_cert
    )
    notes = "Đủ điều kiện tốt nghiệp" if eligible else "Chưa đủ điều kiện tốt nghiệp"

    missing_criteria = []
    if credits_missing > 0:
        missing_criteria.append(f"Còn thiếu {credits_missing} tín chỉ tích lũy (đạt {total_credits_passed}/{required_credits}).")
    if missing_required:
        missing_names = ", ".join([m["name"] for m in missing_required])
        missing_criteria.append(f"Còn thiếu {len(missing_required)} môn bắt buộc theo CTĐT: {missing_names}.")
    if failed_courses:
        failed_names = ", ".join([f["name"] for f in failed_courses])
        missing_criteria.append(f"Còn {len(failed_courses)} môn chưa đạt cần học lại/thi lại: {failed_names}.")

    # Báo cáo tình trạng chứng chỉ: Chỉ báo "chưa hoàn tất" khi hoan_tat=False
    if not has_english_cert:
        if english_incomplete_name:
            missing_criteria.append(f"Chứng chỉ Ngoại ngữ ({english_incomplete_name}) chưa hoàn tất.")
        else:
            missing_criteria.append("Chưa có dữ liệu chứng chỉ Ngoại ngữ, cần nộp.")
    if not has_it_cert:
        if it_incomplete_name:
            missing_criteria.append(f"Chứng chỉ Tin học ({it_incomplete_name}) chưa hoàn tất.")
        else:
            missing_criteria.append("Chưa có dữ liệu chứng chỉ Tin học, cần nộp.")
    for o_name in other_incomplete_certs:
        missing_criteria.append(f"Chứng chỉ ({o_name}) chưa hoàn tất.")

    # Diễn giải trạng thái chứng chỉ
    def _format_cert_status(has_cert: bool, incomplete_name: Optional[str]) -> str:
        if has_cert:
            return "đã có"
        if incomplete_name:
            return f"chưa hoàn tất ({incomplete_name})"
        return "chưa có dữ liệu, cần nộp"

    response_data = {
        "student": student_data,
        "total_credits_passed": total_credits_passed,
        "total_credits_earned": total_credits_passed,
        "total_credits_failed": total_credits_failed,
        "required_credits": required_credits,
        "total_credits_required": required_credits,
        "credits_missing": credits_missing,
        "missing_required_courses": missing_required,
        "failed_courses": failed_courses,
        "certificates": {
            "english": _format_cert_status(has_english_cert, english_incomplete_name),
            "it": _format_cert_status(has_it_cert, it_incomplete_name),
            "has_english": has_english_cert,
            "has_it": has_it_cert,
            "english_certificate_name": english_cert_name,
            "it_certificate_name": it_cert_name
        },
        "missing_criteria": missing_criteria,
        "eligible": eligible,
        "is_eligible": eligible,
        "notes": notes
    }

    # 6. LLM Explain (Tùy chọn)
    if explain:
        prompt = f"""
Bạn là chuyên viên tư vấn học vụ. Dựa vào số liệu sau, hãy giải thích ngắn gọn bằng tiếng Việt (không dùng định dạng markdown phức tạp, chỉ text thuần) cho sinh viên {student.full_name} vì sao họ {'ĐỦ' if eligible else 'CHƯA ĐỦ'} điều kiện tốt nghiệp.
- Tổng tín chỉ yêu cầu: {required_credits}
- Tổng tín chỉ tích lũy: {total_credits_passed}
- Số tín chỉ còn nợ/chưa đạt: {total_credits_failed}
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
                },
                timeout=10
            )
            if res.status_code == 200:
                response_data["explanation"] = res.json().get("response", "").strip()
            else:
                response_data["explanation"] = notes
        except Exception as e:
            response_data["explanation"] = f"{notes}. (Không thể gọi LLM giải thích: {str(e)})"

    return response_data


@router.get("/me/graduation-check")
def my_graduation_check(
    explain: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Endpoint tiện ích cho sinh viên tra cứu hồ sơ xét tốt nghiệp của chính mình
    mà không cần truyền ID vào đường dẫn URL.
    Ưu tiên dữ liệu từ tài khoản LHU nếu đã liên kết.
    """
    stu = db.execute(
        text("SELECT id FROM students WHERE user_id = :uid"),
        {"uid": current_user["id"]}
    ).fetchone()
    if not stu:
        raise HTTPException(status_code=404, detail="Hồ sơ sinh viên chưa được liên kết với tài khoản này")

    # Kiểm tra dữ liệu LHU đã liên kết
    from backend.app.services.lhu_connector import get_active_lhu_data
    active_lhu = get_active_lhu_data(current_user["id"])

    return calculate_graduation_data(stu.id, db, explain=explain, lhu_data=active_lhu)


@router.get("/{student_id}/graduation-check")
def graduation_check(
    student_id: int,
    explain: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Endpoint xét tốt nghiệp:
    - Tra cứu bản ghi sinh viên DUY NHẤT theo students.id. Tuyệt đối không so khớp theo user_id để tránh khớp nhầm ID.
    - Sinh viên chỉ được xem khi students.user_id của bản ghi đó bằng users.id trong token. Nếu không khớp thì trả 403.
    - Admin/giáo vụ có quyền xem hồ sơ của bất kỳ sinh viên nào.
    - Luôn dùng students.id chuẩn cho các truy vấn tính toán điều kiện tốt nghiệp.
    - Ưu tiên dữ liệu LHU nếu sinh viên mục tiêu đã liên kết tài khoản.
    """
    # 1. Tra cứu bản ghi sinh viên theo students.id
    target_student = db.execute(
        text("SELECT id, user_id FROM students WHERE id = :sid"),
        {"sid": student_id}
    ).fetchone()

    if not target_student:
        raise HTTPException(status_code=404, detail="Hồ sơ sinh viên không tồn tại")

    # 2. Phân quyền: Sinh viên chỉ được xem hồ sơ của chính mình
    if current_user["role"] != "admin":
        if target_student.user_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="Không có quyền xem thông tin sinh viên này")

    from backend.app.services.lhu_connector import get_active_lhu_data
    active_lhu = get_active_lhu_data(target_student.user_id)

    # 3. Tính toán và trả về kết quả
    return calculate_graduation_data(target_student.id, db, explain=explain, lhu_data=active_lhu)

