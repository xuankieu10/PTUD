import time
import secrets
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.config import settings
from backend.app.db import get_db
from backend.app.security import verify_password, get_password_hash, create_access_token
from backend.app.deps import get_current_user
from backend.app.services.lhu_connector import (
    login as lhu_login,
    fetch_transcript,
    fetch_certificates,
    reconcile_and_deduplicate_lhu_courses,
    deduce_major_from_class_id,
    SessionStore,
    mark_lhu_user,
    _CACHED_DATA
)

logger = logging.getLogger("AuthRouter")

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginLhuRequest(BaseModel):
    student_id: str = Field(..., description="Mã số sinh viên (MSSV)")
    password: str = Field(..., description="Mật khẩu Cổng trường LHU (me.lhu.edu.vn)")

@router.post("/login-lhu")
def login_lhu(
    req: LoginLhuRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Đăng nhập bằng tài khoản Cổng trường LHU (MSSV + mật khẩu me.lhu.edu.vn).
    - Gọi SignIn của tapi.lhu.edu.vn lấy Token phiên LHU (lưu trong RAM, TTL 30 phút).
    - MSSV lấy từ UserID trong response của LHU, KHÔNG dùng giá trị client gửi.
    - Lần đầu: tạo user mới role student, mật khẩu app là chuỗi ngẫu nhiên không dùng được.
    - Các lần sau: tái sử dụng user đó.
    - Khớp hoặc tạo bản ghi students chuẩn xác theo users.id.
    - Cấp JWT app có thời hạn đúng bằng phiên LHU (30 phút).
    - Khóa sai mật khẩu theo (MSSV + IP): tối đa 5 lần trong 10 phút -> HTTP 429.
    - Tuyệt đối không log mật khẩu, body request hay token.
    """
    clean_sid = req.student_id.strip()
    clean_pwd = req.password.strip()

    if not clean_sid or not clean_pwd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã số sinh viên và mật khẩu không được để trống."
        )

    client_ip = request.client.host if (request and request.client) else "127.0.0.1"

    # 1. Gọi login() trong lhu_connector
    session = lhu_login(
        student_id=clean_sid,
        password=clean_pwd,
        user_id=0,
        client_ip=client_ip
    )

    # 2. MSSV lấy từ UserID trong response của LHU, KHÔNG dùng giá trị client gửi
    lhu_student_id = session.student_id

    # 3. Lần đầu: tạo user mới role student, mật khẩu app là chuỗi ngẫu nhiên không dùng được
    #    Các lần sau: dùng lại user đó nếu đúng role student và auth_provider="lhu".
    user = db.execute(
        text("SELECT id, username, password_hash, role, auth_provider FROM users WHERE username = :usr"),
        {"usr": lhu_student_id}
    ).fetchone()

    if not user:
        dummy_hash = get_password_hash(secrets.token_urlsafe(32))
        try:
            res = db.execute(
                text("INSERT INTO users (username, password_hash, role, auth_provider) OUTPUT INSERTED.id VALUES (:usr, :pwd, 'student', 'lhu')"),
                {"usr": lhu_student_id, "pwd": dummy_hash}
            )
            user_id = res.scalar()
            db.commit()
        except Exception:
            db.rollback()
            db.execute(
                text("INSERT INTO users (username, password_hash, role, auth_provider) VALUES (:usr, :pwd, 'student', 'lhu')"),
                {"usr": lhu_student_id, "pwd": dummy_hash}
            )
            db.commit()
            u = db.execute(text("SELECT id FROM users WHERE username = :usr"), {"usr": lhu_student_id}).fetchone()
            user_id = u[0] if isinstance(u, tuple) else u.id
    else:
        role_val = getattr(user, "role", None) or (user[3] if isinstance(user, tuple) and len(user) > 3 else None)
        provider_val = getattr(user, "auth_provider", None) or (user[4] if isinstance(user, tuple) and len(user) > 4 else None)

        if role_val != "student":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản này đã tồn tại với vai trò không phải sinh viên. Không thể đăng nhập qua luồng Sinh viên LHU."
            )
        if provider_val != "lhu":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản này được tạo bằng phương thức nội bộ/cũ, không thể đăng nhập qua luồng Cổng trường LHU."
            )

        user_id = user[0] if isinstance(user, tuple) else user.id

    # Khớp hoặc tạo bản ghi students theo MSSV chuẩn, chú ý khớp users.id tránh lỗi 403
    stu = db.execute(
        text("SELECT id, user_id FROM students WHERE student_code = :scode"),
        {"scode": lhu_student_id}
    ).fetchone()

    full_name = session.full_name or lhu_student_id
    deduced_major = deduce_major_from_class_id(session.class_id) if session.class_id else None
    major = session.major or deduced_major or "Chưa xác định ngành"
    cohort = session.cohort or ""

    if stu:
        stu_id = stu[0] if isinstance(stu, tuple) else stu.id
        db.execute(
            text("UPDATE students SET user_id = :uid, full_name = COALESCE(:fname, full_name), major = CASE WHEN :major NOT IN ('Chưa cập nhật', 'Chưa xác định ngành') THEN :major ELSE major END WHERE id = :sid"),
            {"uid": user_id, "fname": full_name, "major": major, "sid": stu_id}
        )
        db.commit()
    else:
        try:
            db.execute(
                text("INSERT INTO students (user_id, student_code, full_name, major, cohort) VALUES (:uid, :scode, :fname, :major, :cohort)"),
                {"uid": user_id, "scode": lhu_student_id, "fname": full_name, "major": major, "cohort": cohort}
            )
            db.commit()
        except Exception:
            db.rollback()

    # Lưu phiên LHU vào SessionStore (RAM, TTL 30 phút) theo id user app
    session.user_id = user_id
    SessionStore.set(user_id, session)
    mark_lhu_user(user_id)

    # Tải trước và cache dữ liệu bảng điểm / chứng chỉ vào RAM (best-effort)
    try:
        raw_transcript = fetch_transcript(session)
        if session.major and session.major not in ["Chưa cập nhật", "Chưa xác định ngành"]:
            db.execute(
                text("UPDATE students SET major = :major WHERE user_id = :uid"),
                {"major": session.major, "uid": user_id}
            )
            db.commit()
        raw_certs = fetch_certificates(session)
        reconciled = reconcile_and_deduplicate_lhu_courses(raw_transcript.get("courses", []), db=db)
        _CACHED_DATA[user_id] = {
            "transcript": raw_transcript,
            "certificates": raw_certs,
            "reconciled_courses": reconciled,
            "cached_at": time.time()
        }
    except Exception as e:
        logger.warning("Không thể tải trước dữ liệu LHU: %s", type(e).__name__)

    # Cấp JWT app như /auth/login, JWT không sống lâu hơn phiên LHU (TTL 30 phút)
    ttl_seconds = getattr(settings, "LHU_SESSION_TTL_SECONDS", 1800)
    access_token = create_access_token(
        subject=user_id,
        role="student",
        expires_delta=timedelta(seconds=ttl_seconds),
        auth_provider="lhu"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": "student",
        "user_id": user_id,
        "student_id": lhu_student_id
    }

@router.post("/register")
def register():
    """Vô hiệu hóa endpoint đăng ký công khai theo quy định mới."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Tính năng đăng ký công khai đã bị vô hiệu hóa. Sinh viên vui lòng đăng nhập bằng tài khoản Cổng trường LHU (me.lhu.edu.vn)."
    )

@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(text("SELECT id, username, password_hash, role FROM users WHERE username = :usr"), {"usr": request.username}).fetchone()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(subject=user.id, role=user.role)
    return {"access_token": access_token, "token_type": "bearer", "role": user.role, "user_id": user.id}
from fastapi.security import OAuth2PasswordRequestForm

@router.post("/token")
def login_for_access_token(request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.execute(text("SELECT id, username, password_hash, role FROM users WHERE username = :usr"), {"usr": request.username}).fetchone()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(subject=user.id, role=user.role)
    return {"access_token": access_token, "token_type": "bearer"}
@router.get("/me")
def read_users_me(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    res = {
        "id": current_user["id"],
        "user_id": current_user["id"],
        "username": current_user["username"],
        "role": current_user["role"],
    }
    stu = db.execute(
        text("SELECT id, student_code, full_name, major, cohort FROM students WHERE user_id = :uid"),
        {"uid": current_user["id"]}
    ).fetchone()
    if stu:
        res["student_id"] = stu.id
        res["student_code"] = stu.student_code
        res["full_name"] = stu.full_name
        res["major"] = stu.major
        res["cohort"] = stu.cohort
    else:
        res["student_id"] = None
        if current_user["role"] == "admin":
            res["student_code"] = "ADMIN"
            res["full_name"] = "Quản trị viên"
            res["major"] = "Phòng Đào tạo"
        else:
            res["student_code"] = current_user["username"]
            res["full_name"] = current_user["username"]
            res["major"] = "Chưa cập nhật"
    return res
