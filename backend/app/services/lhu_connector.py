"""
backend/app/services/lhu_connector.py
Module kết nối Cổng thông tin đào tạo Đại học Lạc Hồng (LHU Portal):
- Đăng nhập xác thực tài khoản sinh viên (Token chỉ lưu trong RAM, TTL 30 phút).
- Cơ chế bảo vệ khóa tạm 15 phút sau 5 lần nhập sai liên tiếp.
- Lấy bảng điểm trực tiếp và chuẩn hóa sang schema hiện có của hệ thống.
- Xử lý môn học lại / thi lại theo quy ước nhất quán (ưu tiên đạt, điểm cao nhất, mới nhất).
- Đối chiếu tín chỉ (HeSo vs CTĐT trong DB): ưu tiên CTĐT trong DB, cảnh báo lệch tín chỉ không chứa PII.
- Lấy danh sách chứng chỉ (Ngoại ngữ, Tin học, ...) từ cổng trường.
- Cung cấp FastAPI APIRouter để tích hợp vào ứng dụng.
"""

import time
import logging
import unicodedata
import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.config import settings
from backend.app.db import get_db

logger = logging.getLogger("LHUConnector")

# ==================== DATA STRUCTURES ====================

@dataclass
class LHUSession:
    token: str
    student_id: str
    user_id: int
    full_name: Optional[str] = None
    major: Optional[str] = None
    cohort: Optional[str] = None
    class_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + getattr(settings, "LHU_SESSION_TTL_SECONDS", 1800))

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


# Chuẩn header chung cho các API LHU
LHU_COMMON_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json; charset=utf-8",
}

# In-memory storage (RAM ONLY - Tuyệt đối không lưu DB, log hay file)
_SESSIONS: Dict[int, LHUSession] = {}
_FAILED_ATTEMPTS: Dict[str, Any] = {}
_CACHED_DATA: Dict[int, Dict[str, Any]] = {}
_LHU_LOGGED_IN_USERS: set[int] = set()


class SessionStore:
    """Bộ nhớ RAM quản lý phiên LHU (TTL 30 phút)."""
    @staticmethod
    def set(user_id: int, session: LHUSession) -> None:
        _SESSIONS[user_id] = session

    @staticmethod
    def get(user_id: int) -> Optional[LHUSession]:
        return get_active_session(user_id)

    @staticmethod
    def is_expired(user_id: int) -> bool:
        session = _SESSIONS.get(user_id)
        if not session:
            return True
        return session.is_expired()

    @staticmethod
    def clear(user_id: int) -> None:
        clear_user_session(user_id)


def mark_lhu_user(user_id: int) -> None:
    """Ghi nhận user đăng nhập qua luồng LHU."""
    _LHU_LOGGED_IN_USERS.add(user_id)


def is_lhu_user(user_id: int) -> bool:
    return user_id in _LHU_LOGGED_IN_USERS or user_id in _SESSIONS


def check_lhu_session_validity(
    user_id: int,
    role: Optional[str] = None,
    auth_provider: Optional[str] = None,
    db: Optional[Session] = None
) -> None:
    """
    Kiểm tra phiên LHU của user:
    Chỉ áp dụng cho user đăng nhập bằng LHU (auth_provider == 'lhu').
    Admin và tài khoản cũ (auth_provider != 'lhu') được bỏ qua và vẫn chat bình thường.
    Nếu user đăng nhập qua LHU mà phiên đã hết hạn (TTL 30 phút) hoặc không còn trong RAM,
    ném HTTP 401 rõ ràng để frontend yêu cầu đăng nhập lại.
    """
    if role == "admin":
        return

    if auth_provider is None and db is not None:
        try:
            row = db.execute(
                text("SELECT role, auth_provider FROM users WHERE id = :uid"),
                {"uid": user_id}
            ).fetchone()
            if row:
                role = getattr(row, "role", None) or (row[0] if isinstance(row, tuple) else None)
                auth_provider = getattr(row, "auth_provider", None) or (row[1] if isinstance(row, tuple) and len(row) > 1 else None)
        except Exception:
            pass

    if role == "admin":
        return

    # Chỉ kiểm tra bắt buộc phiên LHU nếu user đăng nhập bằng LHU
    if auth_provider == "lhu" or (auth_provider is None and user_id in _LHU_LOGGED_IN_USERS):
        session = _SESSIONS.get(user_id)
        if not session or session.is_expired():
            _SESSIONS.pop(user_id, None)
            _CACHED_DATA.pop(user_id, None)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên làm việc LHU đã hết hạn. Vui lòng đăng nhập lại."
            )


# ==================== HELPER FUNCTIONS ====================

def normalize_text(text_val: Optional[str]) -> str:
    """Chuẩn hóa chuỗi text tiếng Việt không phân biệt hoa thường, dấu."""
    if not text_val:
        return ""
    text_val = str(text_val).strip().lower()
    text_val = re.sub(r'\{[^}]*\}', '', text_val)
    text_val = text_val.replace("-", " ")
    norm = unicodedata.normalize('NFKD', text_val)
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = norm.replace("đ", "d").replace("Đ", "d")
    norm = re.sub(r'\s+', ' ', norm).strip()
    norm = norm.replace("may hoc", "hoc may")
    return norm


# 1. Nhóm ngành Công nghệ thông tin (CÓ CĂN CỨ VỮNG CHẮC TRONG REPO)
# Căn cứ: database/seed_data/05_sinh_vien_an_danh.xlsx (lớp 22CT111-22CT115 thuộc KCT/CNTT),
# datasets_inventory.md (lớp 23CT111, 22CT111-22CT115), database/schema.sql.
KNOWN_IT_PREFIXES = {"CT", "CNTT"}

# 2. Nhóm ngành đã biết chắc KHÔNG phải CNTT (CÓ CĂN CỨ TỪ TEST & GUARDRAIL)
# Căn cứ: backend/tests/test_auth_lhu.py (lớp 21DS101), guardrail Khoa Dược trong chat.py.
KNOWN_NON_IT_PREFIXES = {
    "DS": "Dược học",
}


def extract_class_prefix(class_id: Optional[str]) -> Optional[str]:
    """Trích xuất tiền tố mã ngành từ mã lớp (ví dụ: '23CT111' -> 'CT', '21DS101' -> 'DS')."""
    if not class_id:
        return None
    cid = str(class_id).strip().upper()
    m = re.search(r'^\d*([A-Z]{2,4})', cid)
    if m:
        return m.group(1)
    m_alpha = re.search(r'([A-Z]{2,4})', cid)
    return m_alpha.group(1) if m_alpha else None


def deduce_major_from_class_id(class_id: Optional[str]) -> Optional[str]:
    """
    Suy luận ngành học từ mã lớp (LopID):
    - Tiền tố CNTT đã biết (CT, CNTT, ví dụ '23CT111') -> 'Công nghệ thông tin'.
    - Tiền tố ngành khác đã biết chắc KHÔNG phải CNTT (DS, ví dụ '21DS101') -> 'Dược học'.
    - Tiền tố lạ hoặc không nhận diện được: KHÔNG được kết luận ngành (trả về None),
      ghi log WARNING CHỈ chứa tiền tố lớp (tuyệt đối không chứa MSSV hay họ tên).
    """
    if not class_id:
        return None
    prefix = extract_class_prefix(class_id)
    if not prefix:
        logger.warning("Không nhận diện được tiền tố mã lớp: %s", class_id)
        return None

    if prefix in KNOWN_IT_PREFIXES:
        return "Công nghệ thông tin"

    if prefix in KNOWN_NON_IT_PREFIXES:
        return KNOWN_NON_IT_PREFIXES[prefix]

    # Tiền tố lạ / không nhận diện được -> KHÔNG kết luận ngành
    # Log WARNING CHỈ chứa tiền tố lớp, không chứa MSSV hay họ tên
    logger.warning("Không nhận diện được ngành từ tiền tố mã lớp: %s", prefix)
    return None


def get_active_session(user_id: int) -> Optional[LHUSession]:
    """Lấy phiên đăng nhập LHU còn hiệu lực trong RAM của user_id."""
    session = _SESSIONS.get(user_id)
    if not session:
        return None
    if session.is_expired():
        logger.info("Phiên làm việc LHU của user %s đã hết hạn (TTL 30 phút). Tự động dọn dẹp RAM.", user_id)
        _SESSIONS.pop(user_id, None)
        _CACHED_DATA.pop(user_id, None)
        return None
    return session


def clear_user_session(user_id: int) -> None:
    """Xóa phiên và dữ liệu cache LHU của user_id trong RAM."""
    _SESSIONS.pop(user_id, None)
    _CACHED_DATA.pop(user_id, None)


def get_active_lhu_data(user_id: int) -> Optional[Dict[str, Any]]:
    """Lấy dữ liệu LHU đã cache nếu phiên của user_id còn hoạt động."""
    session = get_active_session(user_id)
    if not session:
        return None
    return _CACHED_DATA.get(user_id)


def _check_and_update_lockout(
    student_id: str,
    client_ip: Optional[str] = None,
    is_success: bool = False
) -> None:
    """Kiểm tra và quản lý khóa tạm sau 5 lần sai mật khẩu liên tiếp theo (MSSV + IP)."""
    now = time.time()
    clean_sid = str(student_id).strip()
    key = f"{clean_sid}@{client_ip}" if client_ip else clean_sid

    if is_success:
        if key in _FAILED_ATTEMPTS:
            del _FAILED_ATTEMPTS[key]
        return

    record = _FAILED_ATTEMPTS.get(key)
    if record:
        locked_until = record.get("locked_until", 0)
        if locked_until and now < locked_until:
            rem_minutes = max(1, int((locked_until - now) / 60) + 1)
            duration_txt = "10 phút" if client_ip else "15 phút"
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Tài khoản tạm thời bị khóa {duration_txt} do nhập sai mật khẩu quá 5 lần. Vui lòng thử lại sau {rem_minutes} phút."
            )
        elif locked_until and now >= locked_until:
            _FAILED_ATTEMPTS[key] = {"count": 0, "locked_until": 0}


def _record_failed_attempt(
    student_id: str,
    client_ip: Optional[str] = None
) -> None:
    """Ghi nhận một lần đăng nhập thất bại theo (MSSV + IP). Khóa tối đa 5 lần trong 10 phút."""
    now = time.time()
    clean_sid = str(student_id).strip()
    key = f"{clean_sid}@{client_ip}" if client_ip else clean_sid

    record = _FAILED_ATTEMPTS.setdefault(key, {"count": 0, "locked_until": 0})
    record["count"] += 1
    max_attempts = getattr(settings, "LHU_LOCKOUT_ATTEMPTS", 5)
    lock_duration = 600 if client_ip else getattr(settings, "LHU_LOCKOUT_SECONDS", 900)

    if record["count"] >= max_attempts:
        record["locked_until"] = now + lock_duration
        duration_txt = "10 phút" if client_ip else "15 phút"
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Tài khoản tạm thời bị khóa {duration_txt} do nhập sai mật khẩu quá 5 lần."
        )


# ==================== CORE LHU CONNECTOR METHODS ====================

def login(
    student_id: str,
    password: str,
    user_id: int = 0,
    client: Optional[httpx.Client] = None,
    client_ip: Optional[str] = None
) -> LHUSession:
    """
    Đăng nhập vào cổng LHU lấy Token xác thực.
    - POST {BASE}/Security/SignIn (Origin/Referer của app: https://app.lhu.edu.vn)
    - Body: {"UserID": "<mssv>", "Password": "<mk>", "DeviceInfo": "{0}{WebAuth}{LHU AI Advisor}"}
    - Token CHỈ lưu trong RAM, TTL 30 phút.
    - Tuyệt đối không log mật khẩu hoặc body request.
    - Khóa tạm 10 phút sau 5 lần sai mật khẩu liên tiếp theo (MSSV + IP).
    - Chỉ đọc đúng khóa "Token". Không có Token = sai đăng nhập (HTTP 401).
    - MSSV lấy từ UserID trong response của LHU, KHÔNG dùng giá trị client gửi.
    """
    clean_sid = str(student_id).strip()
    clean_pwd = str(password).strip()

    if not clean_sid or not clean_pwd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã số sinh viên và mật khẩu không được để trống."
        )

    # 1. Kiểm tra lockout
    _check_and_update_lockout(clean_sid, client_ip=client_ip, is_success=False)

    portal_url = getattr(settings, "LHU_PORTAL_URL", "https://tapi.lhu.edu.vn").rstrip("/")
    login_url = f"{portal_url}/Security/SignIn"

    headers = {
        **LHU_COMMON_HEADERS,
        "Origin": "https://app.lhu.edu.vn",
        "Referer": "https://app.lhu.edu.vn/",
    }

    payload = {
        "UserID": clean_sid,
        "Password": clean_pwd,
        "DeviceInfo": "{0}{WebAuth}{LHU AI Advisor}",
    }

    should_close_client = False
    if client is None:
        client = httpx.Client(timeout=15.0)
        should_close_client = True

    try:
        resp = client.post(login_url, json=payload, headers=headers)
    except httpx.RequestError as e:
        logger.error("Lỗi mạng khi kết nối tới cổng trường LHU: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không thể kết nối đến hệ thống trường (LHU Portal không phản hồi)."
        )
    finally:
        if should_close_client:
            client.close()

    # 2. Xử lý phản hồi từ portal
    if resp.status_code in [400, 401]:
        _record_failed_attempt(clean_sid, client_ip=client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã số sinh viên hoặc mật khẩu cổng trường không chính xác."
        )

    if resp.status_code != 200:
        logger.error("Cổng trường trả về mã lỗi HTTP %s", resp.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Hệ thống trường phản hồi mã lỗi {resp.status_code}."
        )

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Hệ thống trường trả về định dạng dữ liệu không hợp lệ."
        )

    # 3. Trích xuất Token: Chỉ đọc đúng khóa "Token". Không có Token = sai đăng nhập (HTTP 401).
    token = data.get("Token")
    if not token:
        logger.error("Phản hồi đăng nhập từ cổng trường thiếu trường Token.")
        _record_failed_attempt(clean_sid, client_ip=client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã số sinh viên hoặc mật khẩu cổng trường không chính xác."
        )

    # Đăng nhập thành công -> Reset trạng thái khóa
    _check_and_update_lockout(clean_sid, client_ip=client_ip, is_success=True)

    # MSSV lấy từ UserID trong response của LHU, KHÔNG dùng giá trị client gửi
    lhu_user_id = data.get("UserID") or data.get("StudentID") or data.get("userid")
    resolved_student_id = str(lhu_user_id).strip() if lhu_user_id else clean_sid

    # Trích xuất thông tin sinh viên từ phản hồi đăng nhập
    full_name = data.get("UserName")
    stu_info = data.get("student") or data.get("Student") or {}
    if not full_name:
        full_name = stu_info.get("full_name") or stu_info.get("HoTen") or data.get("HoTen")
    class_id = data.get("LopID") or stu_info.get("LopID") or stu_info.get("class_id") or data.get("ClassID") or stu_info.get("ClassID")
    major = stu_info.get("major") or stu_info.get("Nganh") or data.get("Nganh") or data.get("Major")
    if not major and class_id:
        major = deduce_major_from_class_id(class_id)
    cohort = stu_info.get("cohort") or stu_info.get("Khoa") or data.get("Khoa") or data.get("Cohort")

    session_ttl = getattr(settings, "LHU_SESSION_TTL_SECONDS", 1800)
    session = LHUSession(
        token=token,
        student_id=resolved_student_id,
        user_id=user_id,
        full_name=full_name,
        major=major,
        cohort=cohort,
        class_id=class_id,
        created_at=time.time(),
        expires_at=time.time() + session_ttl
    )
    return session


def fetch_transcript(
    session: LHUSession,
    client: Optional[httpx.Client] = None
) -> Dict[str, Any]:
    """
    Lấy bảng điểm trực tiếp từ cổng LHU bằng Bearer Token trong session:
    - POST {BASE}/mark/MarkViewer_GetBangDiem (Origin/Referer của mark)
    - KHÔNG có body (content=b"", Content-Length: 0), chứng thực hoàn toàn qua Bearer token.
    - Response: {"StudentID", "HoTen", "LopID", "TinhTrang", "DiemTB", "data": [{"HocKy", "KyThiID", "MonHocID", "TenMH", "HeSo", "DiemTBMon", "SoLanThi", "Dau", "KyThiThayThe", "DangKyThiLai", "UpdateTime", "DiemThanhPhan"}]}
    - Map: ma_mon=MonHocID, ten_mon=TenMH, tin_chi=HeSo (đối chiếu DB), diem=DiemTBMon, dat=Dau, hoc_ky=HocKy, so_lan_thi=SoLanThi, cap_nhat=UpdateTime.
    - Trả về định dạng:
    {
      "student": {"student_id", "full_name", "major", "cohort"},
      "gpa_portal": float,
      "courses": [
        {"hoc_ky", "ma_mon", "ten_mon", "tin_chi", "diem", "dat", "so_lan_thi", "dang_ky_thi_lai", "cap_nhat"}
      ]
    }
    """
    if session.is_expired():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên làm việc LHU đã hết hạn. Vui lòng liên kết lại."
        )

    portal_url = getattr(settings, "LHU_PORTAL_URL", "https://tapi.lhu.edu.vn").rstrip("/")
    transcript_url = f"{portal_url}/mark/MarkViewer_GetBangDiem"

    headers = {
        **LHU_COMMON_HEADERS,
        "Authorization": f"Bearer {session.token}",
        "Origin": "https://mark.lhu.edu.vn",
        "Referer": "https://mark.lhu.edu.vn/",
    }
    should_close_client = False
    if client is None:
        client = httpx.Client(timeout=15.0)
        should_close_client = True

    try:
        resp = client.post(transcript_url, headers=headers, content=b"")
    except httpx.RequestError as e:
        logger.error("Lỗi kết nối khi tải bảng điểm từ cổng trường: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không thể tải bảng điểm từ cổng trường LHU (hệ thống không phản hồi)."
        )
    finally:
        if should_close_client:
            client.close()

    if resp.status_code in [401, 403]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên làm việc LHU đã hết hạn trên cổng trường. Vui lòng liên kết lại."
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cổng trường báo lỗi khi tải bảng điểm ({resp.status_code})."
        )

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Dữ liệu bảng điểm từ cổng trường không hợp lệ."
        )

    raw_courses = data.get("data") if isinstance(data, dict) and "data" in data else (data.get("courses") or data.get("DanhSachDiem") or [])
    student_meta = data.get("student") or data.get("SinhVien") or {}
    full_name_resp = data.get("HoTen") or student_meta.get("full_name") or session.full_name or "Sinh viên"
    student_id_resp = data.get("StudentID") or session.student_id

    # Cập nhật LopID và ngành nếu có trong phản hồi bảng điểm
    lop_id = data.get("LopID") or student_meta.get("LopID") or student_meta.get("class_id")
    if lop_id:
        session.class_id = str(lop_id).strip()
        if not session.major or session.major == "Chưa cập nhật":
            session.major = deduce_major_from_class_id(session.class_id)
    transcript_major = student_meta.get("major") or student_meta.get("Nganh") or data.get("Nganh")
    if transcript_major:
        session.major = transcript_major

    # Trích xuất GPA cổng trường (DiemTB)
    gpa_portal = data.get("DiemTB") if data.get("DiemTB") is not None else (data.get("gpa_portal") or data.get("DiemTichLuy") or data.get("gpa"))
    try:
        gpa_portal_val = round(float(str(gpa_portal).replace(",", ".")), 2) if gpa_portal is not None else 0.0
    except (ValueError, TypeError):
        gpa_portal_val = 0.0

    parsed_courses = []
    for c in raw_courses:
        ma_mon = str(c.get("MonHocID") or c.get("ma_mon") or c.get("MaMon") or c.get("MaHocPhan") or c.get("code") or "").strip().upper()
        ten_mon = str(c.get("TenMH") or c.get("ten_mon") or c.get("TenMon") or c.get("TenHocPhan") or c.get("name") or "").strip()
        
        # Hệ số / tín chỉ map từ HeSo của API
        raw_he_so = c.get("HeSo") if c.get("HeSo") is not None else (c.get("tin_chi") if c.get("tin_chi") is not None else c.get("credits"))
        try:
            tin_chi_val = int(raw_he_so) if raw_he_so is not None else 0
        except (ValueError, TypeError):
            try:
                tin_chi_val = int(float(str(raw_he_so).replace(",", ".")))
            except Exception:
                tin_chi_val = 0

        # Điểm số map từ DiemTBMon
        raw_diem = c.get("DiemTBMon") if c.get("DiemTBMon") is not None else (c.get("diem") if c.get("diem") is not None else (c.get("Diem") if c.get("Diem") is not None else (c.get("DiemSo") if c.get("DiemSo") is not None else c.get("grade"))))
        try:
            diem_val = round(float(str(raw_diem).replace(",", ".")), 2) if raw_diem is not None else None
        except (ValueError, TypeError):
            diem_val = None

        # Cờ đạt map từ Dau
        raw_dat = c.get("Dau") if c.get("Dau") is not None else (c.get("dat") if c.get("dat") is not None else (c.get("Dat") if c.get("Dat") is not None else c.get("is_passed")))
        if raw_dat is not None:
            dat_val = bool(raw_dat)
        elif diem_val is not None:
            dat_val = bool(diem_val >= 4.0)
        else:
            dat_val = False

        # Số lần thi map từ SoLanThi
        so_lan_thi_raw = c.get("SoLanThi") if c.get("SoLanThi") is not None else (c.get("so_lan_thi") or 1)
        try:
            so_lan_thi = int(so_lan_thi_raw)
        except (ValueError, TypeError):
            so_lan_thi = 1

        dang_ky_thi_lai = bool(c.get("DangKyThiLai") if c.get("DangKyThiLai") is not None else (c.get("dang_ky_thi_lai") or False))
        cap_nhat = str(c.get("UpdateTime") or c.get("cap_nhat") or c.get("NgayCapNhat") or "").strip()
        hoc_ky = str(c.get("HocKy") or c.get("hoc_ky") or c.get("semester") or "").strip()

        parsed_courses.append({
            "hoc_ky": hoc_ky,
            "ma_mon": ma_mon,
            "ten_mon": ten_mon,
            "tin_chi": tin_chi_val,
            "diem": diem_val,
            "dat": dat_val,
            "so_lan_thi": so_lan_thi,
            "dang_ky_thi_lai": dang_ky_thi_lai,
            "cap_nhat": cap_nhat
        })

    return {
        "student": {
            "student_id": student_id_resp,
            "full_name": full_name_resp,
            "major": student_meta.get("major") or session.major or (deduce_major_from_class_id(session.class_id) if session.class_id else None) or "Chưa cập nhật",
            "cohort": student_meta.get("cohort") or session.cohort or ""
        },
        "gpa_portal": gpa_portal_val,
        "courses": parsed_courses
    }


def fetch_certificates(
    session: LHUSession,
    client: Optional[httpx.Client] = None
) -> List[Dict[str, Any]]:
    """
    Lấy danh sách chứng chỉ từ cổng trường LHU:
    - POST {BASE}/gm//ChungChi_New_SelectChungChiSinhVien (giữ đúng 2 dấu / liên tiếp; Origin/Referer của graduate)
    - Body: {"StudentID": "<mssv lấy từ phiên đăng nhập, không nhận từ client>"}
    - Response: {"data": [{"TenChungChiCan", "TenLoaiChungChi", "TinhTrang", "TinhTrangXet", "DuyetChungChi"}]}
    - Hoàn tất khi TinhTrangXet == 2 hoặc TinhTrang == "Đã hoàn tất".
    - Trả về: [{ten, loai, tinh_trang, hoan_tat, da_duyet}]
    """
    if session.is_expired():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên làm việc LHU đã hết hạn. Vui lòng liên kết lại."
        )

    portal_url = getattr(settings, "LHU_PORTAL_URL", "https://tapi.lhu.edu.vn").rstrip("/")
    cert_url = f"{portal_url}/gm//ChungChi_New_SelectChungChiSinhVien"

    headers = {
        **LHU_COMMON_HEADERS,
        "Authorization": f"Bearer {session.token}",
        "Origin": "https://graduate.lhu.edu.vn",
        "Referer": "https://graduate.lhu.edu.vn/",
    }
    payload = {"StudentID": session.student_id}

    should_close_client = False
    if client is None:
        client = httpx.Client(timeout=15.0)
        should_close_client = True

    try:
        resp = client.post(cert_url, headers=headers, json=payload)
    except httpx.RequestError as e:
        logger.error("Lỗi kết nối khi tải chứng chỉ từ cổng trường: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không thể tải chứng chỉ từ cổng trường LHU (hệ thống không phản hồi)."
        )
    finally:
        if should_close_client:
            client.close()

    if resp.status_code in [401, 403]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên làm việc LHU đã hết hạn trên cổng trường. Vui lòng liên kết lại."
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cổng trường báo lỗi khi tải chứng chỉ ({resp.status_code})."
        )

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Dữ liệu chứng chỉ từ cổng trường không hợp lệ."
        )

    raw_certs = data.get("data") if isinstance(data, dict) and "data" in data else (data if isinstance(data, list) else (data.get("certificates") or data.get("DanhSachChungChi") or []))
    parsed_certs = []

    for item in raw_certs:
        ten = str(item.get("TenChungChiCan") or item.get("ten") or item.get("TenChungChi") or item.get("name") or "").strip()
        loai = str(item.get("TenLoaiChungChi") or item.get("loai") or item.get("LoaiChungChi") or item.get("type") or "").strip()
        tinh_trang = str(item.get("TinhTrang") or item.get("tinh_trang") or item.get("status") or "").strip()

        tinh_trang_xet = item.get("TinhTrangXet")
        if tinh_trang_xet is not None or "TinhTrang" in item:
            hoan_tat = bool(tinh_trang_xet == 2 or tinh_trang == "Đã hoàn tất")
        elif item.get("hoan_tat") is not None:
            hoan_tat = bool(item.get("hoan_tat"))
        elif item.get("HoanTat") is not None:
            hoan_tat = bool(item.get("HoanTat"))
        else:
            hoan_tat = bool(tinh_trang_xet == 2 or tinh_trang == "Đã hoàn tất")

        raw_da_duyet = item.get("DuyetChungChi") if item.get("DuyetChungChi") is not None else (item.get("da_duyet") if item.get("da_duyet") is not None else (item.get("DaDuyet") if item.get("DaDuyet") is not None else True))
        da_duyet = bool(raw_da_duyet)

        parsed_certs.append({
            "ten": ten,
            "loai": loai,
            "tinh_trang": tinh_trang,
            "hoan_tat": hoan_tat,
            "da_duyet": da_duyet
        })

    return parsed_certs


# ==================== RECONCILIATION & DEDUPLICATION ====================

def reconcile_and_deduplicate_lhu_courses(
    courses: List[Dict[str, Any]],
    db: Optional[Session] = None
) -> List[Dict[str, Any]]:
    """
    Chuẩn hóa và chuyển đổi danh sách môn từ LHU sang schema đồng bộ cho hệ thống:
    1. ĐỐI CHIẾU TÍN CHỈ (HeSo vs CTĐT trong DB):
       - Tra cứu theo mã môn (code) hoặc tên môn chuẩn hóa trong CTĐT.
       - Nếu tín chỉ trong DB khác HeSo, ưu tiên DB và ghi log warning (không ghi PII).
    2. QUY ƯỚC CHỌN DÒNG KHI THI LẠI (Deduplication):
       - Một môn có thể có nhiều lần học/thi lại.
       - Sắp xếp ưu tiên:
         + Lần thi ĐẠT (dat=True hoặc diem >= 4.0) ưu tiên hơn lần thi hỏng.
         + Điểm số (diem) cao nhất.
         + Thời gian cập nhật (cap_nhat / UpdateTime) mới nhất.
         + Số lần thi (so_lan_thi) lớn nhất.
       - Môn có dat=False hoặc điểm 0 chưa học -> đánh dấu status="failed", is_failed=True, dat=False.
         Tín chỉ của môn này KHÔNG được tính vào tín chỉ tích lũy đạt.
    3. SCHEMA ÁNH XẠ:
       - Cung cấp đầy đủ các trường song song:
         ma_mon / code / course_code
         ten_mon / name / course_name
         tin_chi / credits
         diem / grade
         hoc_ky / semester
         status ("passed" | "failed"), is_failed, dat
         so_lan_thi, retake_count, dang_ky_thi_lai, cap_nhat, source="LHU"
    """
    # 1. Tải bảng tra CTĐT từ DB (hoặc fallback CTĐT mặc định)
    curriculum_by_code: Dict[str, int] = {}
    curriculum_by_name: Dict[str, int] = {}

    if db is not None:
        try:
            sql = """
                SELECT c.code, c.name, c.credits
                FROM program_courses pc
                JOIN courses c ON pc.course_id = c.id
            """
            rows = db.execute(text(sql)).fetchall()
            for r in rows:
                if r.code:
                    curriculum_by_code[str(r.code).strip().upper()] = int(r.credits)
                if r.name:
                    curriculum_by_name[normalize_text(r.name)] = int(r.credits)
        except Exception as e:
            logger.warning("Không thể truy vấn program_courses từ DB (%s). Dùng bảng CTĐT mặc định.", e)

    # Nếu DB không có hoặc truy vấn lỗi, dùng DEFAULT_CNTT_CURRICULUM
    if not curriculum_by_code:
        try:
            from backend.app.services.graduation_checker import DEFAULT_CNTT_CURRICULUM
            for item in DEFAULT_CNTT_CURRICULUM:
                c_code = str(item.get("ma_mon", "")).strip().upper()
                c_name = str(item.get("ten_mon", "")).strip()
                c_tc = item.get("tin_chi")
                if c_tc is not None:
                    if c_code:
                        curriculum_by_code[c_code] = int(c_tc)
                    if c_name:
                        curriculum_by_name[normalize_text(c_name)] = int(c_tc)
        except Exception:
            pass

    # 2. Gom nhóm các dòng theo môn học (mã môn hoặc tên môn)
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for c in courses:
        ma = str(c.get("ma_mon") or c.get("code") or "").strip().upper()
        ten = str(c.get("ten_mon") or c.get("name") or "").strip()
        norm_ten = normalize_text(ten)

        # Khóa nhóm duy nhất
        group_key = ma if ma else norm_ten
        if not group_key:
            continue

        # Lấy số tín chỉ HeSo hiện tại
        raw_he_so = c.get("tin_chi") if c.get("tin_chi") is not None else c.get("credits")
        try:
            he_so_val = int(raw_he_so) if raw_he_so is not None else 0
        except (ValueError, TypeError):
            he_so_val = 0

        # Đối chiếu với CTĐT trong DB
        db_credits = curriculum_by_code.get(ma)
        if db_credits is None:
            db_credits = curriculum_by_name.get(norm_ten)

        is_discrepancy = False
        if db_credits is not None:
            if he_so_val > 0 and db_credits != he_so_val:
                is_discrepancy = True
                # Cảnh báo lệch tín chỉ, TUYỆT ĐỐI không ghi PII
                logger.warning(
                    "Lệch tín chỉ môn '%s' (Mã: %s): HeSo=%s, DB=%s. Ưu tiên tín chỉ từ CTĐT trong DB.",
                    ten or ma, ma or "N/A", he_so_val, db_credits
                )
            resolved_credits = db_credits
        else:
            resolved_credits = he_so_val

        # Sao chép và gán tín chỉ đã đối chiếu
        c_copy = dict(c)
        c_copy["tin_chi"] = resolved_credits
        c_copy["credits"] = resolved_credits
        c_copy["he_so"] = he_so_val
        c_copy["db_credits"] = db_credits
        c_copy["is_credit_discrepancy"] = is_discrepancy

        grouped.setdefault(group_key, []).append(c_copy)

    # 3. Áp dụng quy ước thi lại trên từng nhóm môn
    reconciled_list = []

    for group_key, attempts in grouped.items():
        if len(attempts) == 1:
            best_attempt = attempts[0]
        else:
            # Sắp xếp các lần thi theo quy ước ưu tiên
            def _attempt_sort_key(item: Dict[str, Any]):
                diem = item.get("diem")
                diem_score = float(diem) if diem is not None else -1.0
                dat = bool(item.get("dat") or (diem is not None and diem >= 4.0))
                # Ưu tiên:
                # 1. Đạt (1) hơn Chưa đạt (0)
                # 2. Điểm số cao nhất
                # 3. Ngày cập nhật mới nhất (chuỗi ISO / date)
                # 4. Số lần thi lớn nhất
                cap_nhat_str = str(item.get("cap_nhat") or "")
                so_lan = int(item.get("so_lan_thi") or 1)
                return (1 if dat else 0, diem_score, cap_nhat_str, so_lan)

            best_attempt = max(attempts, key=_attempt_sort_key)

        # 4. Quyết định trạng thái đạt / không đạt cuối cùng của môn
        diem_val = best_attempt.get("diem")
        raw_dat = best_attempt.get("dat")
        so_lan_thi = int(best_attempt.get("so_lan_thi") or len(attempts))
        dang_ky_thi_lai = bool(best_attempt.get("dang_ky_thi_lai", False))

        is_passed = bool(raw_dat is True or (diem_val is not None and diem_val >= 4.0))
        # Môn có dat=False hoặc điểm 0 chưa học hoặc diem < 4.0 -> failed
        if raw_dat is False or diem_val is None or diem_val < 4.0 or diem_val == 0.0:
            is_passed = False

        status_str = "passed" if is_passed else "failed"

        ma_mon = best_attempt.get("ma_mon") or best_attempt.get("code") or ""
        ten_mon = best_attempt.get("ten_mon") or best_attempt.get("name") or ""
        tin_chi = best_attempt.get("tin_chi", 0)
        hoc_ky = best_attempt.get("hoc_ky") or best_attempt.get("semester") or ""
        cap_nhat = best_attempt.get("cap_nhat") or ""

        reconciled_course = {
            # Chuẩn mã môn
            "ma_mon": ma_mon,
            "code": ma_mon,
            "course_code": ma_mon,
            # Chuẩn tên môn
            "ten_mon": ten_mon,
            "name": ten_mon,
            "course_name": ten_mon,
            # Chuẩn số tín chỉ
            "tin_chi": tin_chi,
            "credits": tin_chi,
            "he_so": best_attempt.get("he_so", tin_chi),
            "db_credits": best_attempt.get("db_credits"),
            "is_credit_discrepancy": bool(best_attempt.get("is_credit_discrepancy", False)),
            # Chuẩn điểm số
            "diem": diem_val,
            "grade": diem_val,
            # Học kỳ
            "hoc_ky": hoc_ky,
            "semester": hoc_ky,
            # Trạng thái
            "status": status_str,
            "is_failed": not is_passed,
            "dat": is_passed,
            # Lịch sử thi lại
            "so_lan_thi": so_lan_thi,
            "retake_count": max(0, len(attempts) - 1),
            "dang_ky_thi_lai": dang_ky_thi_lai,
            "cap_nhat": cap_nhat,
            "source": "LHU"
        }
        reconciled_list.append(reconciled_course)

    return reconciled_list


# ==================== FASTAPI ROUTER BUILDER ====================

class LHULinkRequest(BaseModel):
    student_id: str = Field(..., description="Mã số sinh viên (MSSV)")
    password: str = Field(..., description="Mật khẩu cổng trường LHU")


def build_router(get_user_id: Callable[..., int]) -> APIRouter:
    """
    Xây dựng FastAPI Router phục vụ Liên kết tài khoản LHU.
    - Nhận get_user_id dependency để lấy users.id của phiên đăng nhập hiện tại.
    - Tuyệt đối không trả về token LHU hay mật khẩu trong các API response.
    """
    router = APIRouter(prefix="/lhu", tags=["lhu"])

    @router.post("/link")
    def link_account(
        req: LHULinkRequest,
        user_id: int = Depends(get_user_id),
        db: Session = Depends(get_db)
    ):
        """
        Liên kết tài khoản LHU bằng MSSV + mật khẩu.
        - Đăng nhập lấy Token LHU (lưu trong RAM server, TTL 30 phút).
        - Ngay lập tức tải bảng điểm + chứng chỉ để lưu cache trong RAM.
        - Xóa mật khẩu khỏi bộ nhớ ngay sau khi xử lý.
        """
        # 1. Đăng nhập LHU Portal
        session = login(student_id=req.student_id, password=req.password, user_id=user_id)
        _SESSIONS[user_id] = session

        # 2. Tải bảng điểm và chứng chỉ
        transcript_data = fetch_transcript(session)
        certs_data = fetch_certificates(session)

        # 3. Đối chiếu tín chỉ và xử lý môn thi lại
        reconciled_courses = reconcile_and_deduplicate_lhu_courses(
            transcript_data.get("courses", []),
            db=db
        )

        # 4. Lưu cache vào RAM
        _CACHED_DATA[user_id] = {
            "transcript": transcript_data,
            "certificates": certs_data,
            "reconciled_courses": reconciled_courses,
            "cached_at": time.time()
        }

        passed_count = sum(1 for c in reconciled_courses if c.get("status") == "passed")
        failed_count = sum(1 for c in reconciled_courses if c.get("status") == "failed")
        expires_in = max(0, int(session.expires_at - time.time()))

        return {
            "success": True,
            "message": "Liên kết tài khoản LHU thành công.",
            "student": transcript_data.get("student") or {
                "student_id": session.student_id,
                "full_name": session.full_name,
                "major": session.major,
                "cohort": session.cohort
            },
            "gpa_portal": transcript_data.get("gpa_portal", 0.0),
            "total_courses": len(reconciled_courses),
            "passed_courses_count": passed_count,
            "failed_courses_count": failed_count,
            "certificates_count": len(certs_data),
            "expires_in_seconds": expires_in
        }

    @router.get("/status")
    def get_link_status(user_id: int = Depends(get_user_id)):
        """Kiểm tra trạng thái liên kết tài khoản LHU của người dùng hiện tại."""
        raw_session = _SESSIONS.get(user_id)
        if raw_session and raw_session.is_expired():
            _SESSIONS.pop(user_id, None)
            _CACHED_DATA.pop(user_id, None)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên làm việc LHU đã hết hạn. Vui lòng đăng nhập lại."
            )

        session = get_active_session(user_id)
        if not session:
            return {
                "linked": False,
                "expired": False,
                "student_id": None,
                "expires_in_seconds": 0,
                "has_cached_data": False
            }

        expires_in = max(0, int(session.expires_at - time.time()))
        has_cached = user_id in _CACHED_DATA

        return {
            "linked": True,
            "expired": False,
            "student_id": session.student_id,
            "full_name": session.full_name,
            "expires_at": session.expires_at,
            "expires_in_seconds": expires_in,
            "has_cached_data": has_cached
        }

    @router.get("/transcript")
    def get_transcript(
        user_id: int = Depends(get_user_id),
        db: Session = Depends(get_db)
    ):
        """Lấy bảng điểm đã trích xuất và chuẩn hóa từ LHU."""
        session = get_active_session(user_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên làm việc LHU đã hết hạn hoặc chưa liên kết."
            )

        cached = _CACHED_DATA.get(user_id)
        if cached and "transcript" in cached and "reconciled_courses" in cached:
            return {
                "student": cached["transcript"].get("student"),
                "gpa_portal": cached["transcript"].get("gpa_portal"),
                "courses": cached["reconciled_courses"]
            }

        # Nếu chưa cache, fetch fresh
        raw_transcript = fetch_transcript(session)
        reconciled = reconcile_and_deduplicate_lhu_courses(raw_transcript.get("courses", []), db=db)
        _CACHED_DATA.setdefault(user_id, {})["transcript"] = raw_transcript
        _CACHED_DATA[user_id]["reconciled_courses"] = reconciled

        return {
            "student": raw_transcript.get("student"),
            "gpa_portal": raw_transcript.get("gpa_portal"),
            "courses": reconciled
        }

    @router.get("/certificates")
    def get_certificates(user_id: int = Depends(get_user_id)):
        """Lấy danh sách chứng chỉ từ cổng trường LHU."""
        session = get_active_session(user_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên làm việc LHU đã hết hạn hoặc chưa liên kết."
            )

        cached = _CACHED_DATA.get(user_id)
        if cached and "certificates" in cached:
            return cached["certificates"]

        certs = fetch_certificates(session)
        _CACHED_DATA.setdefault(user_id, {})["certificates"] = certs
        return certs

    @router.get("/summary")
    def get_summary(
        user_id: int = Depends(get_user_id),
        db: Session = Depends(get_db)
    ):
        """
        Kiểm tra nhanh thông tin tổng kết học vụ từ LHU (không chứa PII: không MSSV, họ tên, ngày sinh):
        - gpa_portal, gpa tính bằng code của hệ thống (gpa_system)
        - tổng tín chỉ tích lũy (total_accumulated_credits)
        - số môn nợ (debt_courses_count)
        - danh sách môn có tín chỉ lệch giữa HeSo và DB (credit_discrepancies: mã môn, HeSo, db_credits)
        - danh sách chứng chỉ và trạng thái hoàn tất (certificates)
        """
        session = get_active_session(user_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên làm việc LHU đã hết hạn hoặc chưa liên kết."
            )

        cached = _CACHED_DATA.get(user_id)
        if not cached or "reconciled_courses" not in cached or "transcript" not in cached or "certificates" not in cached:
            raw_transcript = fetch_transcript(session)
            reconciled = reconcile_and_deduplicate_lhu_courses(raw_transcript.get("courses", []), db=db)
            raw_certs = fetch_certificates(session)
            cached = {
                "transcript": raw_transcript,
                "reconciled_courses": reconciled,
                "certificates": raw_certs,
                "cached_at": time.time()
            }
            _CACHED_DATA[user_id] = cached

        transcript = cached.get("transcript", {})
        reconciled_courses = cached.get("reconciled_courses", [])
        raw_certs = cached.get("certificates", [])

        # Tính toán bằng code hệ thống chuẩn xác
        from backend.app.services.graduation_checker import calculate_academic_summary
        summary_code = calculate_academic_summary(reconciled_courses)

        gpa_portal = transcript.get("gpa_portal", 0.0)
        gpa_system = summary_code.get("gpa_10", 0.0)
        total_accumulated_credits = summary_code.get("passed_credits", 0)
        debt_courses_count = sum(1 for c in reconciled_courses if c.get("status") == "failed" or c.get("is_failed") is True)

        credit_discrepancies = [
            {
                "ma_mon": c.get("ma_mon"),
                "HeSo": c.get("he_so", c.get("tin_chi")),
                "he_so": c.get("he_so", c.get("tin_chi")),
                "db_credits": c.get("db_credits")
            }
            for c in reconciled_courses
            if c.get("is_credit_discrepancy")
        ]

        certs_list = [
            {
                "ten": c.get("ten", ""),
                "loai": c.get("loai", ""),
                "hoan_tat": bool(c.get("hoan_tat")),
                "tinh_trang": c.get("tinh_trang", "")
            }
            for c in raw_certs
        ]

        # Tuyệt đối KHÔNG trả MSSV, họ tên, ngày sinh, token
        return {
            "gpa_portal": gpa_portal,
            "gpa": gpa_system,
            "gpa_system": gpa_system,
            "gpa_system_4": summary_code.get("gpa_4", 0.0),
            "total_accumulated_credits": total_accumulated_credits,
            "debt_courses_count": debt_courses_count,
            "credit_discrepancies": credit_discrepancies,
            "certificates": certs_list
        }

    @router.delete("/link")
    def unlink_account(user_id: int = Depends(get_user_id)):
        """Hủy liên kết tài khoản LHU, xóa Token và dữ liệu tạm khỏi RAM."""
        clear_user_session(user_id)
        return {
            "success": True,
            "message": "Đã hủy liên kết tài khoản LHU thành công."
        }

    return router
