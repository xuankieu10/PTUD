"""
backend/tests/test_auth_lhu.py
Bộ test xác thực toàn diện cho luồng Đăng nhập tài khoản Cổng trường LHU (me.lhu.edu.vn):
- login-lhu thành công lần đầu (tạo user role student, mật khẩu ngẫu nhiên, khớp students)
- login-lhu thành công lần sau (tái sử dụng user đó)
- sai mật khẩu -> HTTP 401
- response cổng trường thiếu trường Token -> HTTP 401
- cổng trường LHU gặp lỗi mạng hoặc 500 -> HTTP 502
- khóa tạm sau 5 lần sai mật khẩu theo (MSSV + IP) -> HTTP 429
- MSSV trích xuất từ trường UserID trong response LHU, KHÔNG dùng giá trị client gửi
- endpoint /auth/register bị vô hiệu hóa (HTTP 403)
- endpoint /auth/login cũ cho admin/test vẫn hoạt động bình thường
- khi phiên LHU hết hạn (TTL 30 phút) -> các endpoint /lhu/* và /chat trả về HTTP 401 rõ ràng
- bảo đảm cô lập dữ liệu: hai sinh viên không đọc được dữ liệu của nhau
- app.openapi() có đầy đủ các endpoint theo hợp đồng
"""

import time
import httpx
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from backend.api import app
from fastapi import HTTPException, Depends
from jose import jwt
from backend.app.config import settings
from backend.app.deps import get_db, get_current_user, oauth2_scheme
from backend.app.services.lhu_connector import (
    LHUSession,
    SessionStore,
    _SESSIONS,
    _CACHED_DATA,
    _FAILED_ATTEMPTS,
    _LHU_LOGGED_IN_USERS,
)
import backend.app.services.lhu_connector as conn_mod
from backend.app.security import get_password_hash


# ==================== IN-MEMORY DB CHO TEST ====================

class InMemoryTestDB:
    def __init__(self):
        self.users = {
            1: {
                "id": 1,
                "username": "admin",
                "password_hash": get_password_hash("change_me"),
                "role": "admin",
                "auth_provider": "local"
            }
        }
        self.students = {}
        self.chat_sessions = {}
        self.chat_messages = []
        self.next_user_id = 2
        self.next_student_id = 1

    def execute(self, query, params=None):
        q_str = str(query)
        params = params or {}
        mock_result = MagicMock()

        # 1. users query by username
        if "FROM users WHERE username =" in q_str:
            usr = params.get("usr")
            found = None
            for u in self.users.values():
                if u["username"] == usr:
                    found = u
                    break
            if found:
                mock_row = MagicMock()
                mock_row.id = found["id"]
                mock_row.username = found["username"]
                mock_row.password_hash = found["password_hash"]
                mock_row.role = found["role"]
                mock_row.auth_provider = found.get("auth_provider", "local")
                mock_row.__getitem__ = lambda s, i: [found["id"], found["username"], found["password_hash"], found["role"], found.get("auth_provider", "local")][i]
                mock_result.fetchone.return_value = mock_row
            else:
                mock_result.fetchone.return_value = None
            return mock_result

        # users query by id
        elif "FROM users WHERE id =" in q_str:
            uid = params.get("uid")
            found = self.users.get(uid)
            if found:
                mock_row = MagicMock()
                mock_row.id = found["id"]
                mock_row.username = found["username"]
                mock_row.password_hash = found["password_hash"]
                mock_row.role = found["role"]
                mock_row.auth_provider = found.get("auth_provider", "local")
                mock_row.__getitem__ = lambda s, i: [found["id"], found["username"], found["password_hash"], found["role"], found.get("auth_provider", "local")][i]
                mock_result.fetchone.return_value = mock_row
            else:
                mock_result.fetchone.return_value = None
            return mock_result

        elif "INSERT INTO users" in q_str:
            usr = params.get("usr")
            pwd = params.get("pwd")
            role = "student"
            auth_provider = params.get("auth_provider", "lhu")
            new_id = self.next_user_id
            self.next_user_id += 1
            self.users[new_id] = {
                "id": new_id,
                "username": usr,
                "password_hash": pwd,
                "role": role,
                "auth_provider": auth_provider
            }
            mock_result.scalar.return_value = new_id
            mock_row = MagicMock()
            mock_row.id = new_id
            mock_row.auth_provider = auth_provider
            mock_row.__getitem__ = lambda s, i: new_id
            mock_result.fetchone.return_value = mock_row
            return mock_result

        # 2. students query
        elif "FROM students WHERE student_code =" in q_str:
            scode = params.get("scode")
            found = None
            for s in self.students.values():
                if s["student_code"] == scode:
                    found = s
                    break
            if found:
                mock_row = MagicMock()
                mock_row.id = found["id"]
                mock_row.user_id = found["user_id"]
                mock_row.__getitem__ = lambda s, i: [found["id"], found["user_id"]][i]
                mock_result.fetchone.return_value = mock_row
            else:
                mock_result.fetchone.return_value = None
            return mock_result

        elif "FROM students WHERE user_id =" in q_str:
            uid = params.get("uid")
            found = None
            for s in self.students.values():
                if s["user_id"] == uid:
                    found = s
                    break
            if found:
                mock_row = MagicMock()
                mock_row.id = found["id"]
                mock_row.user_id = found["user_id"]
                mock_row.student_code = found["student_code"]
                mock_row.full_name = found["full_name"]
                mock_row.major = found["major"]
                mock_row.cohort = found["cohort"]
                mock_row.__getitem__ = lambda s, i: [found["id"], found["user_id"]][i]
                mock_result.fetchone.return_value = mock_row
            else:
                mock_result.fetchone.return_value = None
            return mock_result

        elif "FROM students WHERE id =" in q_str:
            sid = params.get("sid")
            found = self.students.get(sid)
            if found:
                mock_row = MagicMock()
                mock_row.id = found["id"]
                mock_row.user_id = found["user_id"]
                mock_row.student_code = found["student_code"]
                mock_row.full_name = found["full_name"]
                mock_row.major = found["major"]
                mock_row.cohort = found["cohort"]
                mock_result.fetchone.return_value = mock_row
            else:
                mock_result.fetchone.return_value = None
            return mock_result

        elif "INSERT INTO students" in q_str:
            sid = self.next_student_id
            self.next_student_id += 1
            self.students[sid] = {
                "id": sid,
                "user_id": params.get("uid"),
                "student_code": params.get("scode"),
                "full_name": params.get("fname"),
                "major": params.get("major"),
                "cohort": params.get("cohort")
            }
            mock_result.scalar.return_value = sid
            return mock_result

        elif "UPDATE students SET" in q_str:
            sid = params.get("sid")
            if sid in self.students:
                if "uid" in params:
                    self.students[sid]["user_id"] = params.get("uid")
                if "major" in params and params.get("major"):
                    self.students[sid]["major"] = params.get("major")
                if "fname" in params and params.get("fname"):
                    self.students[sid]["full_name"] = params.get("fname")
            return mock_result

        elif "SELECT DISTINCT major FROM program_courses" in q_str:
            mock_row = MagicMock()
            mock_row.major = "Công nghệ thông tin"
            mock_row.__getitem__ = lambda s, i: "Công nghệ thông tin"
            mock_result.fetchall.return_value = [("Công nghệ thông tin",)]
            return mock_result

        elif "FROM program_courses" in q_str:
            mock_c = MagicMock()
            mock_c.id = 1
            mock_c.code = "IT101"
            mock_c.name = "Nhập môn CNTT"
            mock_c.credits = 3
            mock_c.__getitem__ = lambda s, i: [1, "IT101", "Nhập môn CNTT", 3][i]
            mock_result.fetchall.return_value = [mock_c]
            return mock_result

        # 3. chat_sessions query
        elif "INSERT INTO chat_sessions" in q_str:
            sess_id = len(self.chat_sessions) + 1
            self.chat_sessions[sess_id] = {
                "id": sess_id,
                "user_id": params.get("uid"),
                "title": params.get("title")
            }
            mock_result.scalar.return_value = sess_id
            return mock_result

        elif "FROM chat_sessions" in q_str:
            mock_result.scalar.return_value = 1
            mock_result.fetchone.return_value = MagicMock(id=1, user_id=params.get("uid", 1))
            mock_result.fetchall.return_value = []
            return mock_result

        # Defaults
        mock_result.scalar.return_value = 1
        mock_result.fetchone.return_value = None
        mock_result.fetchall.return_value = []
        return mock_result

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture
def test_db():
    db = InMemoryTestDB()
    def override_get_db():
        yield db

    def override_get_current_user(token: str = Depends(oauth2_scheme)):
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
            uid = int(payload.get("sub"))
            role = payload.get("role")
            auth_prov = payload.get("auth_provider")
            user = db.users.get(uid)
            if user:
                return {
                    "id": uid,
                    "username": user["username"],
                    "role": user["role"],
                    "auth_provider": user.get("auth_provider", auth_prov or "local")
                }
            return {
                "id": uid,
                "username": str(uid),
                "role": role,
                "auth_provider": auth_prov or "local"
            }
        except Exception:
            raise HTTPException(status_code=401, detail="Could not validate credentials")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_lhu_in_memory_state():
    """Dọn dẹp sạch sẽ RAM Sessions và lockout trước và sau mỗi test."""
    _SESSIONS.clear()
    _CACHED_DATA.clear()
    _FAILED_ATTEMPTS.clear()
    _LHU_LOGGED_IN_USERS.clear()
    yield
    _SESSIONS.clear()
    _CACHED_DATA.clear()
    _FAILED_ATTEMPTS.clear()
    _LHU_LOGGED_IN_USERS.clear()


# ==================== MOCK TRANSPORT HANDLERS ====================

def make_mock_lhu_transport(handler):
    return httpx.MockTransport(handler)


def standard_mock_lhu_handler(request: httpx.Request) -> httpx.Response:
    url_str = str(request.url)

    # 1. SignIn
    if "/Security/SignIn" in url_str:
        import json
        body = json.loads(request.content.decode("utf-8")) if request.content else {}
        password = body.get("Password", "")
        uid = body.get("UserID", "")

        if password == "wrong_password":
            return httpx.Response(401, json={"message": "Unauthorized"})
        elif password == "missing_token":
            return httpx.Response(200, json={"UserName": "Thiếu Token", "UserID": uid})
        elif password == "lhu_error_500":
            return httpx.Response(500, json={"message": "Internal Error"})
        elif password == "network_error":
            raise httpx.RequestError("Network connection reset")

        # Thành công
        return httpx.Response(200, json={
            "Token": "mock_lhu_token_valid_123",
            "UserID": uid,
            "UserName": f"Sinh Viên {uid}",
            "student": {
                "full_name": f"Sinh Viên {uid}",
                "major": "Công nghệ thông tin",
                "cohort": "2021"
            }
        })

    # 2. MarkViewer_GetBangDiem
    elif "/mark/MarkViewer_GetBangDiem" in url_str:
        return httpx.Response(200, json={
            "StudentID": "211000123",
            "HoTen": "Sinh Viên LHU",
            "DiemTB": 3.25,
            "data": [
                {
                    "MonHocID": "IT101",
                    "TenMH": "Nhập môn CNTT",
                    "HeSo": 3,
                    "DiemTBMon": 8.0,
                    "Dau": True,
                    "SoLanThi": 1,
                    "DangKyThiLai": False,
                    "UpdateTime": "2026-01-01"
                }
            ]
        })

    # 3. ChungChi_New_SelectChungChiSinhVien
    elif "SelectChungChiSinhVien" in url_str:
        return httpx.Response(200, json={
            "data": [
                {
                    "TenChungChiCan": "Tin học MOS",
                    "TenLoaiChungChi": "Tin học",
                    "TinhTrang": "Đã hoàn tất",
                    "TinhTrangXet": 2,
                    "DuyetChungChi": True
                }
            ]
        })

    return httpx.Response(404)


# ==================== CÁC TEST CASES THEO YÊU CẦU ====================

def test_openapi_has_required_lhu_and_auth_paths():
    """Kiểm tra app.openapi() có đủ /lhu/link, /lhu/status, /lhu/transcript, /lhu/certificates, /lhu/summary, /auth/login-lhu."""
    openapi = app.openapi()
    paths = openapi.get("paths", {})
    assert "/lhu/link" in paths
    assert "/lhu/status" in paths
    assert "/lhu/transcript" in paths
    assert "/lhu/certificates" in paths
    assert "/lhu/summary" in paths
    assert "/auth/login-lhu" in paths
    assert "/auth/login" in paths
    assert "/auth/register" in paths


def test_login_lhu_first_time_creates_user_and_second_time_reuses_user(test_db, test_client, monkeypatch):
    """
    login-lhu thành công:
    - Lần đầu: tạo user mới role student, mật khẩu app là chuỗi ngẫu nhiên không dùng được (không lưu mật khẩu LHU), khớp students.
    - Lần sau: tái sử dụng đúng user đó.
    """
    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(standard_mock_lhu_handler), **kw))

    # Lần 1: Tạo mới user
    res1 = test_client.post("/auth/login-lhu", json={"student_id": "211000123", "password": "valid_pass"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["role"] == "student"
    assert "access_token" in data1
    assert "token" not in data1  # Tuyệt đối không trả token LHU về response
    user_id_1 = data1["user_id"]
    assert user_id_1 in test_db.users
    user_record = test_db.users[user_id_1]
    assert user_record["role"] == "student"
    assert user_record["username"] == "211000123"
    # Mật khẩu LHU tuyệt đối không được lưu
    assert user_record["password_hash"] != "valid_pass"

    # Kiểm tra students record khớp user_id
    student_records = [s for s in test_db.students.values() if s["user_id"] == user_id_1]
    assert len(student_records) == 1
    assert student_records[0]["student_code"] == "211000123"

    # Lần 2: Tái sử dụng user cũ
    res2 = test_client.post("/auth/login-lhu", json={"student_id": "211000123", "password": "valid_pass"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["user_id"] == user_id_1


def test_login_lhu_wrong_password_returns_401(test_db, test_client, monkeypatch):
    """Đăng nhập sai mật khẩu Cổng trường LHU -> HTTP 401."""
    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(standard_mock_lhu_handler), **kw))

    res = test_client.post("/auth/login-lhu", json={"student_id": "211000123", "password": "wrong_password"})
    assert res.status_code == 401
    assert "không chính xác" in res.json().get("detail", "").lower()


def test_login_lhu_missing_token_in_response_returns_401(test_db, test_client, monkeypatch):
    """Cổng trường phản hồi thành công nhưng thiếu trường Token -> HTTP 401."""
    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(standard_mock_lhu_handler), **kw))

    res = test_client.post("/auth/login-lhu", json={"student_id": "211000123", "password": "missing_token"})
    assert res.status_code == 401
    assert "không chính xác" in res.json().get("detail", "").lower()


def test_login_lhu_portal_error_returns_502(test_db, test_client, monkeypatch):
    """Cổng trường LHU gặp lỗi 500 hoặc rớt mạng -> HTTP 502."""
    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(standard_mock_lhu_handler), **kw))

    # LHU báo lỗi 500
    res500 = test_client.post("/auth/login-lhu", json={"student_id": "211000123", "password": "lhu_error_500"})
    assert res500.status_code == 502

    # LHU lỗi mạng
    res_net = test_client.post("/auth/login-lhu", json={"student_id": "211000123", "password": "network_error"})
    assert res_net.status_code == 502


def test_login_lhu_lockout_429(test_db, test_client, monkeypatch):
    """Khóa sai mật khẩu theo (MSSV + IP): tối đa 5 lần trong 10 phút -> HTTP 429."""
    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(standard_mock_lhu_handler), **kw))

    # 4 lần đầu nhập sai mật khẩu -> 401
    for _ in range(4):
        res = test_client.post("/auth/login-lhu", json={"student_id": "SV_LOCK_TEST", "password": "wrong_password"})
        assert res.status_code == 401

    # Lần thứ 5 sai -> Khóa tạm thời 10 phút, trả về 429
    res5 = test_client.post("/auth/login-lhu", json={"student_id": "SV_LOCK_TEST", "password": "wrong_password"})
    assert res5.status_code == 429
    assert "khóa" in res5.json().get("detail", "").lower()

    # Lần thứ 6 -> Chặn ngay lập tức
    res6 = test_client.post("/auth/login-lhu", json={"student_id": "SV_LOCK_TEST", "password": "any_password"})
    assert res6.status_code == 429


def test_login_lhu_mssv_taken_from_lhu_response_not_client(test_db, test_client, monkeypatch):
    """MSSV lấy từ trường UserID trong response của LHU, KHÔNG dùng giá trị client gửi."""
    def custom_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "Token": "mock_token_lhu",
            "UserID": "TRUTH_FROM_LHU_777",  # MSSV thật từ hệ thống trường
            "UserName": "Sinh Viên Thật",
            "student": {"full_name": "Sinh Viên Thật", "major": "CNTT", "cohort": "2021"}
        })

    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(custom_handler), **kw))

    # Client gửi MSSV giả tạo
    res = test_client.post("/auth/login-lhu", json={"student_id": "FAKE_CLIENT_TYPO", "password": "valid_pass"})
    assert res.status_code == 200
    data = res.json()
    assert data["student_id"] == "TRUTH_FROM_LHU_777"
    assert data["student_id"] != "FAKE_CLIENT_TYPO"

    # User trong DB phải mang username là TRUTH_FROM_LHU_777
    user_id = data["user_id"]
    assert test_db.users[user_id]["username"] == "TRUTH_FROM_LHU_777"


def test_register_endpoint_is_blocked(test_client):
    """Endpoint đăng ký công khai /auth/register bị chặn (HTTP 403 hoặc 404)."""
    res = test_client.post("/auth/register", json={"username": "sv_new", "password": "123"})
    assert res.status_code in [403, 404]


def test_old_auth_login_still_works(test_db, test_client):
    """Giữ nguyên endpoint /auth/login cũ cho tài khoản admin/test."""
    res = test_client.post("/auth/login", json={"username": "admin", "password": "change_me"})
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert res.json()["role"] == "admin"


def test_lhu_session_expired_returns_401(test_db, test_client, monkeypatch):
    """Khi phiên LHU hết hạn trong RAM -> các endpoint /lhu/* và chat dùng dữ liệu LHU trả 401 rõ ràng."""
    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(standard_mock_lhu_handler), **kw))

    # 1. Đăng nhập thành công
    res_login = test_client.post("/auth/login-lhu", json={"student_id": "211000123", "password": "valid_pass"})
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]
    user_id = res_login.json()["user_id"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Đang trong thời hạn -> gọi thành công
    res_status = test_client.get("/lhu/status", headers=auth_headers)
    assert res_status.status_code == 200

    # 2. Giả lập phiên hết hạn (TTL 30 phút đã trôi qua)
    session = SessionStore.get(user_id)
    assert session is not None
    session.expires_at = time.time() - 10  # Đã hết hạn

    # 3. Gọi /lhu/* -> Trả 401 rõ ràng
    res_exp_status = test_client.get("/lhu/status", headers=auth_headers)
    assert res_exp_status.status_code == 401
    assert "hết hạn" in res_exp_status.json().get("detail", "").lower()

    # Tái tạo phiên hết hạn để test transcript
    SessionStore.set(user_id, LHUSession(
        token="token_exp",
        student_id="211000123",
        user_id=user_id,
        expires_at=time.time() - 10
    ))
    res_exp_trans = test_client.get("/lhu/transcript", headers=auth_headers)
    assert res_exp_trans.status_code == 401

    # 4. Gọi /chat -> Trả 401 yêu cầu đăng nhập lại
    res_exp_chat = test_client.post("/chat", json={"message": "Tôi nợ những môn nào?"}, headers=auth_headers)
    assert res_exp_chat.status_code == 401
    assert "hết hạn" in res_exp_chat.json().get("detail", "").lower()


def test_two_students_cannot_read_each_others_data(test_db, test_client, monkeypatch):
    """Bảo đảm cách ly dữ liệu: hai sinh viên không đọc được dữ liệu của nhau."""
    def multi_student_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/Security/SignIn" in url_str:
            import json
            body = json.loads(request.content.decode("utf-8")) if request.content else {}
            uid = body.get("UserID", "")
            return httpx.Response(200, json={
                "Token": f"token_{uid}",
                "UserID": uid,
                "UserName": f"Sinh Viên {uid}",
                "student": {"full_name": f"Sinh Viên {uid}", "major": "CNTT", "cohort": "2021"}
            })
        elif "/mark/MarkViewer_GetBangDiem" in url_str:
            auth_header = request.headers.get("Authorization", "")
            if "token_SV_A" in auth_header:
                return httpx.Response(200, json={
                    "StudentID": "SV_A",
                    "HoTen": "Sinh Viên A",
                    "DiemTB": 3.8,
                    "data": [{"MonHocID": "MON_A", "TenMH": "Môn của A", "HeSo": 3, "DiemTBMon": 9.0, "Dau": True}]
                })
            else:
                return httpx.Response(200, json={
                    "StudentID": "SV_B",
                    "HoTen": "Sinh Viên B",
                    "DiemTB": 2.5,
                    "data": [{"MonHocID": "MON_B", "TenMH": "Môn của B", "HeSo": 3, "DiemTBMon": 5.0, "Dau": True}]
                })
        elif "SelectChungChiSinhVien" in url_str:
            return httpx.Response(200, json={"data": []})
        return httpx.Response(404)

    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(multi_student_handler), **kw))

    # Sinh viên A đăng nhập
    res_a = test_client.post("/auth/login-lhu", json={"student_id": "SV_A", "password": "pass"})
    token_a = res_a.json()["access_token"]
    user_id_a = res_a.json()["user_id"]

    # Sinh viên B đăng nhập
    res_b = test_client.post("/auth/login-lhu", json={"student_id": "SV_B", "password": "pass"})
    token_b = res_b.json()["access_token"]
    user_id_b = res_b.json()["user_id"]

    assert user_id_a != user_id_b

    # Sinh viên A đọc bảng điểm của chính mình -> Nhận MON_A
    trans_a = test_client.get("/lhu/transcript", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert trans_a["student"]["student_id"] == "SV_A"
    assert trans_a["courses"][0]["ma_mon"] == "MON_A"

    # Sinh viên B đọc bảng điểm của chính mình -> Nhận MON_B
    trans_b = test_client.get("/lhu/transcript", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert trans_b["student"]["student_id"] == "SV_B"
    assert trans_b["courses"][0]["ma_mon"] == "MON_B"

    # Sinh viên B không thể xem hồ sơ tốt nghiệp của Sinh viên A qua endpoint /students/{id}/graduation-check (trả về 403)
    student_a_record = [s for s in test_db.students.values() if s["user_id"] == user_id_a][0]
    res_grad = test_client.get(f"/students/{student_a_record['id']}/graduation-check", headers={"Authorization": f"Bearer {token_b}"})
    assert res_grad.status_code == 403


def test_login_lhu_rejects_existing_user_with_admin_role(test_db, test_client, monkeypatch):
    """
    Nếu username=MSSV đã tồn tại với role khác (ví dụ: admin)
    thì trả về HTTP 403 rõ ràng và không cho phép đăng nhập qua luồng LHU.
    """
    test_db.users[99] = {
        "id": 99,
        "username": "211000999",
        "password_hash": get_password_hash("admin_secret"),
        "role": "admin",
        "auth_provider": "local"
    }

    def custom_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "Token": "mock_token_admin_test",
            "UserID": "211000999",
            "UserName": "Admin LHU User",
            "student": {"full_name": "Admin LHU User", "major": "CNTT"}
        })

    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(custom_handler), **kw))

    res = test_client.post("/auth/login-lhu", json={"student_id": "211000999", "password": "pass"})
    assert res.status_code == 403
    assert "không phải sinh viên" in res.json().get("detail", "").lower()


def test_login_lhu_rejects_existing_user_created_by_old_local_flow(test_db, test_client, monkeypatch):
    """
    Nếu username=MSSV đã tồn tại nhưng được tạo bằng luồng cũ/nội bộ (auth_provider != 'lhu')
    thì trả về HTTP 403 rõ ràng và không cho phép đăng nhập vào tài khoản đó.
    """
    test_db.users[98] = {
        "id": 98,
        "username": "211000998",
        "password_hash": get_password_hash("local_pass"),
        "role": "student",
        "auth_provider": "local"
    }

    def custom_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "Token": "mock_token_local_test",
            "UserID": "211000998",
            "UserName": "Local Student",
            "student": {"full_name": "Local Student", "major": "CNTT"}
        })

    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(custom_handler), **kw))

    res = test_client.post("/auth/login-lhu", json={"student_id": "211000998", "password": "pass"})
    assert res.status_code == 403
    assert "nội bộ/cũ" in res.json().get("detail", "").lower() or "không thể đăng nhập qua luồng" in res.json().get("detail", "").lower()


def test_expired_lhu_session_only_affects_lhu_users_not_admin_or_local(test_db, test_client, monkeypatch):
    """
    Kiểm tra phiên LHU hết hạn chỉ trả 401 cho user đăng nhập bằng LHU;
    admin và tài khoản cũ vẫn chat bình thường.
    """
    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(standard_mock_lhu_handler), **kw))

    # 1. Admin đăng nhập luồng cũ /auth/login (không có phiên LHU)
    res_admin_login = test_client.post("/auth/login", json={"username": "admin", "password": "change_me"})
    assert res_admin_login.status_code == 200
    admin_token = res_admin_login.json()["access_token"]

    # Admin gọi /chat bình thường dù không có phiên LHU nào trong RAM
    res_admin_chat = test_client.post(
        "/chat",
        json={"message": "Xin chào"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin_chat.status_code == 200

    # 2. Tài khoản sinh viên cũ (auth_provider='local')
    test_db.users[50] = {
        "id": 50,
        "username": "sv_old",
        "password_hash": get_password_hash("sv_pass"),
        "role": "student",
        "auth_provider": "local"
    }
    test_db.students[50] = {
        "id": 50,
        "user_id": 50,
        "student_code": "sv_old",
        "full_name": "Sinh Viên Cũ",
        "major": "Công nghệ thông tin",
        "cohort": "2020"
    }
    res_sv_login = test_client.post("/auth/login", json={"username": "sv_old", "password": "sv_pass"})
    assert res_sv_login.status_code == 200
    sv_token = res_sv_login.json()["access_token"]

    # Sinh viên cũ gọi /chat bình thường mà không bị chặn 401
    res_sv_chat = test_client.post(
        "/chat",
        json={"message": "Xin chào"},
        headers={"Authorization": f"Bearer {sv_token}"}
    )
    assert res_sv_chat.status_code == 200

    # 3. Sinh viên đăng nhập qua luồng LHU
    res_lhu_login = test_client.post("/auth/login-lhu", json={"student_id": "211000123", "password": "valid_pass"})
    assert res_lhu_login.status_code == 200
    lhu_token = res_lhu_login.json()["access_token"]
    lhu_uid = res_lhu_login.json()["user_id"]

    # Làm hết hạn phiên LHU của sinh viên LHU
    session = SessionStore.get(lhu_uid)
    assert session is not None
    session.expires_at = time.time() - 10

    # Sinh viên LHU bị trả về 401 yêu cầu đăng nhập lại
    res_lhu_chat = test_client.post(
        "/chat",
        json={"message": "Tôi nợ môn nào?"},
        headers={"Authorization": f"Bearer {lhu_token}"}
    )
    assert res_lhu_chat.status_code == 401
    assert "hết hạn" in res_lhu_chat.json().get("detail", "").lower()


def test_lhu_student_with_unsupported_major_from_class_or_response(test_db, test_client, monkeypatch):
    """
    Khi tạo students mới, lấy LopID/ngành từ phản hồi LHU.
    Nếu không thuộc chương trình đào tạo đang có trong DB (ví dụ: Dược học, LopID: 21DS101):
    - graduation-check phải báo 'chưa hỗ trợ ngành này' (HTTP 400).
    - chat phải báo 'chưa hỗ trợ ngành này' và KHÔNG áp dụng CTĐT CNTT cho họ.
    """
    def pharmacy_lhu_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/Security/SignIn" in url_str:
            return httpx.Response(200, json={
                "Token": "mock_token_pharmacy",
                "UserID": "211009999",
                "UserName": "Nguyễn Văn Dược",
                "LopID": "21DS101",
                "student": {
                    "full_name": "Nguyễn Văn Dược",
                    "Nganh": "Dược học",
                    "LopID": "21DS101",
                    "cohort": "2021"
                }
            })
        elif "/mark/MarkViewer_GetBangDiem" in url_str:
            return httpx.Response(200, json={
                "StudentID": "211009999",
                "HoTen": "Nguyễn Văn Dược",
                "LopID": "21DS101",
                "DiemTB": 3.0,
                "data": [
                    {
                        "MonHocID": "DH101",
                        "TenMH": "Hóa dược 1",
                        "HeSo": 3,
                        "DiemTBMon": 7.5,
                        "Dau": True,
                        "SoLanThi": 1,
                        "DangKyThiLai": False,
                        "UpdateTime": "2026-01-01"
                    }
                ]
            })
        elif "SelectChungChiSinhVien" in url_str:
            return httpx.Response(200, json={"data": []})
        return httpx.Response(404)

    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(pharmacy_lhu_handler), **kw))

    # Đăng nhập bằng sinh viên ngành Dược
    res_login = test_client.post("/auth/login-lhu", json={"student_id": "211009999", "password": "valid_pass"})
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]
    user_id = res_login.json()["user_id"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Xác nhận ngành trong bản ghi students đã lưu là Dược học (không bị gán cứng CNTT)
    student_records = [s for s in test_db.students.values() if s["user_id"] == user_id]
    assert len(student_records) == 1
    pharmacy_student = student_records[0]
    assert pharmacy_student["major"] == "Dược học"

    # 1. graduation-check phải báo 'chưa hỗ trợ ngành này' (HTTP 400)
    res_grad = test_client.get(
        f"/students/{pharmacy_student['id']}/graduation-check",
        headers=auth_headers
    )
    assert res_grad.status_code == 400
    assert "chưa hỗ trợ ngành này" in res_grad.json().get("detail", "").lower()

    # 2. chat phải báo 'chưa hỗ trợ ngành này' và KHÔNG dùng CTĐT CNTT
    res_chat = test_client.post(
        "/chat",
        json={"message": "Tôi còn nợ những môn nào để tốt nghiệp?"},
        headers=auth_headers
    )
    assert res_chat.status_code == 200
    chat_resp = res_chat.json().get("response", "")
    assert "chưa hỗ trợ ngành này" in chat_resp.lower()
    # Tuyệt đối không dùng CTĐT CNTT cho sinh viên Dược (không bị gắn các môn CNTT như Toán CC1, Cấu trúc dữ liệu...)
    assert "toán cc" not in chat_resp.lower()
    assert "cấu trúc dữ liệu" not in chat_resp.lower()


def test_class_prefix_known_it_classes_including_23ct111(test_db, test_client, monkeypatch):
    """
    Lớp '23CT111' và '22CT115' phải được nhận là CNTT:
    - deduce_major_from_class_id('23CT111') trả về 'Công nghệ thông tin'
    - Đăng nhập sinh viên lớp 23CT111 được gán ngành 'Công nghệ thông tin'
    - graduation-check và chat hoạt động bình thường, áp dụng CTĐT CNTT
    """
    from backend.app.services.lhu_connector import deduce_major_from_class_id
    assert deduce_major_from_class_id("23CT111") == "Công nghệ thông tin"
    assert deduce_major_from_class_id("22CT115") == "Công nghệ thông tin"
    assert deduce_major_from_class_id("20CT111") == "Công nghệ thông tin"
    assert deduce_major_from_class_id("23CNTT01") == "Công nghệ thông tin"

    def it_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/Security/SignIn" in url_str:
            return httpx.Response(200, json={
                "Token": "mock_token_it_23ct111",
                "UserID": "231001111",
                "UserName": "Nguyễn Văn IT",
                "LopID": "23CT111",
                "student": {
                    "full_name": "Nguyễn Văn IT",
                    "LopID": "23CT111",
                    "cohort": "2023"
                }
            })
        elif "/mark/MarkViewer_GetBangDiem" in url_str:
            return httpx.Response(200, json={
                "StudentID": "231001111",
                "HoTen": "Nguyễn Văn IT",
                "LopID": "23CT111",
                "DiemTB": 3.5,
                "data": [
                    {
                        "MonHocID": "IT101",
                        "TenMH": "Nhập môn CNTT",
                        "HeSo": 3,
                        "DiemTBMon": 8.0,
                        "Dau": True,
                        "SoLanThi": 1,
                        "DangKyThiLai": False,
                        "UpdateTime": "2026-01-01"
                    }
                ]
            })
        elif "SelectChungChiSinhVien" in url_str:
            return httpx.Response(200, json={"data": []})
        return httpx.Response(404)

    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(it_handler), **kw))

    res_login = test_client.post("/auth/login-lhu", json={"student_id": "231001111", "password": "valid_pass"})
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]
    user_id = res_login.json()["user_id"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    student_records = [s for s in test_db.students.values() if s["user_id"] == user_id]
    assert len(student_records) == 1
    assert student_records[0]["major"] == "Công nghệ thông tin"

    # graduation-check hợp lệ (không bị từ chối 400 vì 23CT111 là CNTT)
    res_grad = test_client.get(f"/students/{student_records[0]['id']}/graduation-check", headers=auth_headers)
    assert res_grad.status_code == 200


def test_class_prefix_known_non_it_class_deduction():
    """Lớp ngành khác đã biết chắc KHÔNG phải CNTT (ví dụ '21DS101') suy ra 'Dược học'."""
    from backend.app.services.lhu_connector import deduce_major_from_class_id
    assert deduce_major_from_class_id("21DS101") == "Dược học"
    assert deduce_major_from_class_id("22DS112") == "Dược học"


def test_class_prefix_unknown_strange_neutral_handling(test_db, test_client, monkeypatch, caplog):
    """
    Tiền tố lạ hoặc không nhận diện được (ví dụ '99ZZ999', '21ABC123'):
    - deduce_major_from_class_id trả về None (không kết luận ngành).
    - Log WARNING chỉ chứa tiền tố lớp, tuyệt đối KHÔNG chứa MSSV hay họ tên.
    - Xử lý như 'chưa xác định ngành' với thông báo trung tính:
      + graduation-check trả 400 thông báo chưa xác định được CTĐT, không nói sai ngành.
      + chat trả 200 thông báo trung tính, không áp CTĐT CNTT.
    """
    import logging
    from backend.app.services.lhu_connector import deduce_major_from_class_id

    # 1. Kiểm tra suy luận và log WARNING chỉ chứa tiền tố lớp
    with caplog.at_level(logging.WARNING):
        result = deduce_major_from_class_id("99ZZ999")
        assert result is None
        # Log phải chứa tiền tố 'ZZ'
        assert any("ZZ" in record.message for record in caplog.records)
        # Tuyệt đối không chứa PII (MSSV, tên người)
        for record in caplog.records:
            assert "99ZZ999" not in record.message
            assert "sinh viên" not in record.message.lower()

    # 2. Đăng nhập với sinh viên có lớp mang tiền tố lạ
    def unknown_class_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/Security/SignIn" in url_str:
            return httpx.Response(200, json={
                "Token": "mock_token_strange_class",
                "UserID": "991008888",
                "UserName": "Trần Văn Lạ",
                "LopID": "99ZZ999",
                "student": {
                    "full_name": "Trần Văn Lạ",
                    "LopID": "99ZZ999",
                    "cohort": "1999"
                }
            })
        elif "/mark/MarkViewer_GetBangDiem" in url_str:
            return httpx.Response(200, json={
                "StudentID": "991008888",
                "HoTen": "Trần Văn Lạ",
                "LopID": "99ZZ999",
                "DiemTB": 2.8,
                "data": []
            })
        elif "SelectChungChiSinhVien" in url_str:
            return httpx.Response(200, json={"data": []})
        return httpx.Response(404)

    orig_client = httpx.Client
    monkeypatch.setattr(conn_mod.httpx, "Client", lambda **kw: orig_client(transport=make_mock_lhu_transport(unknown_class_handler), **kw))

    res_login = test_client.post("/auth/login-lhu", json={"student_id": "991008888", "password": "valid_pass"})
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]
    user_id = res_login.json()["user_id"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    student_records = [s for s in test_db.students.values() if s["user_id"] == user_id]
    assert len(student_records) == 1
    assert student_records[0]["major"] == "Chưa xác định ngành"

    # 3. graduation-check: thông báo trung tính, không nói sai ngành
    res_grad = test_client.get(f"/students/{student_records[0]['id']}/graduation-check", headers=auth_headers)
    assert res_grad.status_code == 400
    grad_detail = res_grad.json().get("detail", "").lower()
    assert "chưa xác định được" in grad_detail
    assert "dược" not in grad_detail  # Không nói sai ngành

    # 4. chat: thông báo trung tính, không áp CTĐT CNTT
    res_chat = test_client.post(
        "/chat",
        json={"message": "Tôi cần học gì để tốt nghiệp?"},
        headers=auth_headers
    )
    assert res_chat.status_code == 200
    chat_resp = res_chat.json().get("response", "").lower()
    assert "chưa xác định được" in chat_resp
    assert "toán cc" not in chat_resp
    assert "cấu trúc dữ liệu" not in chat_resp
    assert "dược" not in chat_resp  # Không nói sai tên ngành
