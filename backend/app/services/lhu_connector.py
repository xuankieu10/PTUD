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
_FAILED_ATTEMPTS: Dict[str, Dict[str, Any]] = {}
_CACHED_DATA: Dict[int, Dict[str, Any]] = {}


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


def _check_and_update_lockout(student_id: str, is_success: bool = False) -> None:
    """Kiểm tra và quản lý khóa tạm 15 phút sau 5 lần sai mật khẩu."""
    now = time.time()
    record = _FAILED_ATTEMPTS.get(student_id)

    if is_success:
        if student_id in _FAILED_ATTEMPTS:
            del _FAILED_ATTEMPTS[student_id]
        return

    if record:
        locked_until = record.get("locked_until", 0)
        if locked_until and now < locked_until:
            rem_minutes = max(1, int((locked_until - now) / 60) + 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Tài khoản tạm thời bị khóa 15 phút do nhập sai mật khẩu quá 5 lần. Vui lòng thử lại sau {rem_minutes} phút."
            )
        elif locked_until and now >= locked_until:
            # Hết thời gian khóa, reset bộ đếm
            _FAILED_ATTEMPTS[student_id] = {"count": 0, "locked_until": 0}


def _record_failed_attempt(student_id: str) -> None:
    """Ghi nhận một lần đăng nhập thất bại."""
    now = time.time()
    record = _FAILED_ATTEMPTS.setdefault(student_id, {"count": 0, "locked_until": 0})
    record["count"] += 1
    max_attempts = getattr(settings, "LHU_LOCKOUT_ATTEMPTS", 5)
    lock_duration = getattr(settings, "LHU_LOCKOUT_SECONDS", 900)

    if record["count"] >= max_attempts:
        record["locked_until"] = now + lock_duration
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Tài khoản tạm thời bị khóa 15 phút do nhập sai mật khẩu quá 5 lần."
        )


# ==================== CORE LHU CONNECTOR METHODS ====================

def login(
    student_id: str,
    password: str,
    user_id: int = 0,
    client: Optional[httpx.Client] = None
) -> LHUSession:
    """
    Đăng nhập vào cổng LHU lấy Token xác thực.
    - POST {BASE}/Security/SignIn (Origin/Referer của app: https://app.lhu.edu.vn)
    - Body: {"UserID": "<mssv>", "Password": "<mk>", "DeviceInfo": "{0}{WebAuth}{LHU AI Advisor}"}
    - Token CHỈ lưu trong RAM, TTL 30 phút.
    - Tuyệt đối không log mật khẩu hoặc body request.
    - Khóa tạm 15 phút sau 5 lần sai mật khẩu liên tiếp.
    - Chỉ đọc đúng khóa "Token". Không có Token = sai đăng nhập (HTTP 401).
    """
    clean_sid = str(student_id).strip()
    clean_pwd = str(password).strip()

    if not clean_sid or not clean_pwd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã số sinh viên và mật khẩu không được để trống."
        )

    # 1. Kiểm tra lockout
    _check_and_update_lockout(clean_sid, is_success=False)

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
        _record_failed_attempt(clean_sid)
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
        _record_failed_attempt(clean_sid)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã số sinh viên hoặc mật khẩu cổng trường không chính xác."
        )

    # Đăng nhập thành công -> Reset trạng thái khóa
    _check_and_update_lockout(clean_sid, is_success=True)

    # Trích xuất thông tin sinh viên từ phản hồi đăng nhập
    full_name = data.get("UserName")
    stu_info = data.get("student") or data.get("Student") or {}
    if not full_name:
        full_name = stu_info.get("full_name") or stu_info.get("HoTen")
    major = stu_info.get("major") or stu_info.get("Nganh")
    cohort = stu_info.get("cohort") or stu_info.get("Khoa")

    session_ttl = getattr(settings, "LHU_SESSION_TTL_SECONDS", 1800)
    session = LHUSession(
        token=token,
        student_id=clean_sid,
        user_id=user_id,
        full_name=full_name,
        major=major,
        cohort=cohort,
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
            "major": student_meta.get("major") or session.major or "Công nghệ thông tin",
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
