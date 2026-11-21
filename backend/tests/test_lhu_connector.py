"""
backend/tests/test_lhu_connector.py
Bộ kiểm thử toàn diện module LHU Connector:
1. Đăng nhập đúng -> lưu session vào RAM, đúng TTL 30 phút.
2. Đăng nhập sai thông tin -> 401.
3. Không có trường Token trong response -> 502.
4. LHU không phản hồi hoặc lỗi mạng -> 502.
5. Khóa tạm 15 phút sau 5 lần sai mật khẩu liên tiếp -> 429.
6. Hết hạn phiên (TTL > 30 phút) -> 401.
7. Chuẩn hóa bảng điểm và xử lý môn thi lại (quy ước ưu tiên đạt, điểm cao nhất, mới nhất).
8. Môn có dat=False hoặc điểm 0 chưa học không tính vào tín chỉ tích lũy.
9. Đối chiếu tín chỉ (HeSo vs CTĐT trong DB): ưu tiên DB, ghi log warning (không chứa PII).
10. Chứng chỉ hoàn tất (hoan_tat=True) vs chưa hoàn tất (hoan_tat=False).
11. Cô lập dữ liệu: User A không đọc được dữ liệu của User B.
12. Tích hợp Chat: Ưu tiên LHU khi session active, fallback OCR khi không liên kết hoặc hết hạn.
"""

import time
import json
import logging
from typing import Dict, Any

import pytest
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api import app
from backend.app.services.lhu_connector import (
    LHUSession,
    login,
    fetch_transcript,
    fetch_certificates,
    reconcile_and_deduplicate_lhu_courses,
    get_active_session,
    clear_user_session,
    _SESSIONS,
    _FAILED_ATTEMPTS,
    _CACHED_DATA,
)
from backend.app.routers.chat import get_student_academic_and_ocr_context
from backend.app.routers.students import calculate_graduation_data


# ==================== FIXTURES & MOCKS ====================

@pytest.fixture(autouse=True)
def clean_lhu_state():
    """Tự động dọn sạch RAM session và failed attempts trước và sau mỗi test."""
    _SESSIONS.clear()
    _FAILED_ATTEMPTS.clear()
    _CACHED_DATA.clear()
    yield
    _SESSIONS.clear()
    _FAILED_ATTEMPTS.clear()
    _CACHED_DATA.clear()


def make_mock_transport(handler_func) -> httpx.MockTransport:
    """Tạo httpx.MockTransport với handler tùy chỉnh."""
    return httpx.MockTransport(handler_func)


# ==================== UNIT TESTS: LOGIN & AUTH ====================

def test_login_success():
    """Kiểm tra đăng nhập LHU thành công: lưu session vào RAM, token không rỗng, TTL 30 phút."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/Security/SignIn"
        assert request.headers["Accept"] == "application/json, text/javascript, */*; q=0.01"
        assert "application/json" in request.headers["Content-Type"]
        assert request.headers["Origin"] == "https://app.lhu.edu.vn"
        assert request.headers["Referer"] == "https://app.lhu.edu.vn/"

        body = json.loads(request.content)
        assert body["UserID"] == "SV123456"
        assert body["Password"] == "valid_password"
        assert body["DeviceInfo"] == "{0}{WebAuth}{LHU AI Advisor}"

        return httpx.Response(200, json={
            "Token": "mock_jwt_token_ram_only_12345",
            "UserName": "Nguyen Van A",
            "UserID": "SV123456"
        })

    client = httpx.Client(transport=make_mock_transport(handler))
    session = login(student_id="SV123456", password="valid_password", user_id=1, client=client)

    assert isinstance(session, LHUSession)
    assert session.token == "mock_jwt_token_ram_only_12345"
    assert session.student_id == "SV123456"
    assert session.user_id == 1
    assert session.full_name == "Nguyen Van A"
    assert not session.is_expired()
    assert session.expires_at - session.created_at >= 1799


def test_login_wrong_credentials_raises_401():
    """Kiểm tra đăng nhập sai mật khẩu -> ném HTTPException 401."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Invalid credentials"})

    client = httpx.Client(transport=make_mock_transport(handler))
    with pytest.raises(HTTPException) as exc_info:
        login(student_id="SV123456", password="wrong_password", user_id=1, client=client)

    assert exc_info.value.status_code == 401
    assert "không chính xác" in exc_info.value.detail


def test_login_response_missing_token_raises_401():
    """Kiểm tra phản hồi 200 nhưng không có trường Token -> coi như sai đăng nhập (HTTP 401)."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": "Success without token", "data": {}})

    client = httpx.Client(transport=make_mock_transport(handler))
    with pytest.raises(HTTPException) as exc_info:
        login(student_id="SV123456", password="valid_password", user_id=1, client=client)

    assert exc_info.value.status_code == 401
    assert "không chính xác" in exc_info.value.detail


def test_login_portal_offline_raises_502():
    """Kiểm tra LHU portal không phản hồi hoặc lỗi kết nối -> ném HTTPException 502."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    client = httpx.Client(transport=make_mock_transport(handler))
    with pytest.raises(HTTPException) as exc_info:
        login(student_id="SV123456", password="valid_password", user_id=1, client=client)

    assert exc_info.value.status_code == 502
    assert "không phản hồi" in exc_info.value.detail.lower()


def test_lockout_after_five_failed_attempts():
    """Kiểm tra cơ chế khóa tạm 15 phút sau 5 lần sai mật khẩu liên tiếp -> HTTP 429."""
    def handler_fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    client = httpx.Client(transport=make_mock_transport(handler_fail))

    # 4 lần đầu tiên: trả về 401
    for i in range(4):
        with pytest.raises(HTTPException) as exc:
            login(student_id="SV_LOCKED", password=f"wrong_{i}", user_id=1, client=client)
        assert exc.value.status_code == 401

    # Lần thứ 5: bị khóa tạm và trả về 429
    with pytest.raises(HTTPException) as exc5:
        login(student_id="SV_LOCKED", password="wrong_5", user_id=1, client=client)
    assert exc5.value.status_code == 429
    assert "khóa 15 phút" in exc5.value.detail

    # Lần thứ 6 (chưa hết 15 phút): chặn ngay lập tức mà không gọi mạng
    with pytest.raises(HTTPException) as exc6:
        login(student_id="SV_LOCKED", password="any_password", user_id=1, client=client)
    assert exc6.value.status_code == 429


def test_session_expired_raises_401():
    """Kiểm tra phiên hết hạn (TTL 30 phút) -> ném 401 khi gọi fetch_transcript/certificates."""
    expired_session = LHUSession(
        token="expired_token",
        student_id="SV123456",
        user_id=1,
        created_at=time.time() - 3600,
        expires_at=time.time() - 10  # Đã hết hạn
    )

    with pytest.raises(HTTPException) as exc1:
        fetch_transcript(expired_session)
    assert exc1.value.status_code == 401
    assert "hết hạn" in exc1.value.detail

    with pytest.raises(HTTPException) as exc2:
        fetch_certificates(expired_session)
    assert exc2.value.status_code == 401
    assert "hết hạn" in exc2.value.detail


# ==================== UNIT TESTS: FETCH & NORMALIZATION ====================

def test_fetch_transcript_and_certificates():
    """Kiểm tra fetch_transcript và fetch_certificates đúng đặc tả API LHU thật."""
    session = LHUSession(
        token="valid_token_xyz",
        student_id="123000999",
        user_id=1,
        expires_at=time.time() + 1800
    )

    def handler_transcript(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/mark/MarkViewer_GetBangDiem"
        assert request.headers["Authorization"] == "Bearer valid_token_xyz"
        assert request.headers["Accept"] == "application/json, text/javascript, */*; q=0.01"
        assert "application/json" in request.headers["Content-Type"]
        assert request.headers["Origin"] == "https://mark.lhu.edu.vn"
        assert request.headers["Referer"] == "https://mark.lhu.edu.vn/"
        # Không có body
        assert request.content == b""

        return httpx.Response(200, json={
            "StudentID": "123000999",
            "HoTen": "Tran Van B",
            "LopID": "22CT111",
            "TinhTrang": "Đang học",
            "DiemTB": 3.25,
            "data": [
                {
                    "HocKy": "Học kỳ 1",
                    "KyThiID": 1,
                    "MonHocID": "102014",
                    "TenMH": "Tin học đại cương",
                    "HeSo": 3,
                    "DiemTBMon": 8.0,
                    "SoLanThi": 1,
                    "Dau": True,
                    "KyThiThayThe": None,
                    "DangKyThiLai": False,
                    "UpdateTime": "2023-01-10",
                    "DiemThanhPhan": []
                }
            ]
        })

    client_t = httpx.Client(transport=make_mock_transport(handler_transcript))
    t_data = fetch_transcript(session, client=client_t)

    assert t_data["student"]["student_id"] == "123000999"
    assert t_data["student"]["full_name"] == "Tran Van B"
    assert t_data["gpa_portal"] == 3.25
    assert len(t_data["courses"]) == 1
    assert t_data["courses"][0]["ma_mon"] == "102014"
    assert t_data["courses"][0]["ten_mon"] == "Tin học đại cương"
    assert t_data["courses"][0]["tin_chi"] == 3
    assert t_data["courses"][0]["diem"] == 8.0
    assert t_data["courses"][0]["dat"] is True

    def handler_certs(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        # Đường dẫn phải giữ đúng 2 dấu slash //
        assert request.url.raw_path == b"/gm//ChungChi_New_SelectChungChiSinhVien" or "/gm//ChungChi_New_SelectChungChiSinhVien" in str(request.url)
        assert request.headers["Authorization"] == "Bearer valid_token_xyz"
        assert request.headers["Accept"] == "application/json, text/javascript, */*; q=0.01"
        assert "application/json" in request.headers["Content-Type"]
        assert request.headers["Origin"] == "https://graduate.lhu.edu.vn"
        assert request.headers["Referer"] == "https://graduate.lhu.edu.vn/"

        # MSSV phải lấy từ session.student_id trong body JSON, không nhận từ client
        body = json.loads(request.content)
        assert body["StudentID"] == "123000999"

        return httpx.Response(200, json={
            "data": [
                {
                    "TenChungChiCan": "TOEIC 450",
                    "TenLoaiChungChi": "Ngoại ngữ",
                    "TinhTrang": "Đã hoàn tất",
                    "TinhTrangXet": 2,
                    "DuyetChungChi": True
                },
                {
                    "TenChungChiCan": "Chuẩn đầu ra Tin học MOS",
                    "TenLoaiChungChi": "Tin học",
                    "TinhTrang": "Chưa hoàn tất",
                    "TinhTrangXet": 1,
                    "DuyetChungChi": False
                }
            ]
        })

    client_c = httpx.Client(transport=make_mock_transport(handler_certs))
    c_data = fetch_certificates(session, client=client_c)

    assert len(c_data) == 2
    assert c_data[0]["ten"] == "TOEIC 450"
    assert c_data[0]["loai"] == "Ngoại ngữ"
    assert c_data[0]["hoan_tat"] is True
    assert c_data[1]["ten"] == "Chuẩn đầu ra Tin học MOS"
    assert c_data[1]["hoan_tat"] is False


def test_reconcile_and_deduplicate_retaken_courses():
    """
    Kiểm tra quy ước chọn dòng khi thi lại:
    - Môn 111062 thi 3 lần: lần 1 (3.0, dat=False), lần 2 (8.0, dat=True), lần 3 (6.5, dat=True).
      -> Phải chọn lần 2 (điểm cao nhất đạt: 8.0).
    - Môn 111059 thi 2 lần đều hỏng: lần 1 (2.0), lần 2 (3.5).
      -> Phải giữ lần điểm cao hơn nhưng status='failed', is_failed=True, dat=False.
    - Môn đăng ký nhưng điểm 0 / chưa học: status='failed', is_failed=True, dat=False.
    """
    raw_courses = [
        # Môn 111062 (Cấu trúc dữ liệu và giải thuật)
        {"ma_mon": "111062", "ten_mon": "CTDL & GT", "tin_chi": 3, "diem": 3.0, "dat": False, "so_lan_thi": 1, "cap_nhat": "2023-01-01"},
        {"ma_mon": "111062", "ten_mon": "CTDL & GT", "tin_chi": 3, "diem": 8.0, "dat": True, "so_lan_thi": 2, "cap_nhat": "2023-06-01"},
        {"ma_mon": "111062", "ten_mon": "CTDL & GT", "tin_chi": 3, "diem": 6.5, "dat": True, "so_lan_thi": 3, "cap_nhat": "2023-12-01"},

        # Môn 111059 (Cơ sở dữ liệu) - 2 lần đều rớt
        {"ma_mon": "111059", "ten_mon": "Cơ sở dữ liệu", "tin_chi": 3, "diem": 2.0, "dat": False, "so_lan_thi": 1, "cap_nhat": "2023-01-01"},
        {"ma_mon": "111059", "ten_mon": "Cơ sở dữ liệu", "tin_chi": 3, "diem": 3.5, "dat": False, "so_lan_thi": 2, "cap_nhat": "2023-06-01"},

        # Môn 112061 (Mạng máy tính) - điểm 0 chưa học
        {"ma_mon": "112061", "ten_mon": "Mạng máy tính", "tin_chi": 2, "diem": 0.0, "dat": False, "so_lan_thi": 1, "cap_nhat": "2024-01-01"},
    ]

    reconciled = reconcile_and_deduplicate_lhu_courses(raw_courses)

    # Sau khi deduplicate phải còn đúng 3 môn
    assert len(reconciled) == 3
    by_code = {c["ma_mon"]: c for c in reconciled}

    # 1. CTDL & GT: Chọn lần 8.0, status='passed'
    ctdl = by_code["111062"]
    assert ctdl["diem"] == 8.0
    assert ctdl["status"] == "passed"
    assert ctdl["is_failed"] is False
    assert ctdl["dat"] is True
    assert ctdl["retake_count"] == 2

    # 2. Cơ sở dữ liệu: Chọn lần 3.5, nhưng status='failed'
    csdl = by_code["111059"]
    assert csdl["diem"] == 3.5
    assert csdl["status"] == "failed"
    assert csdl["is_failed"] is True
    assert csdl["dat"] is False

    # 3. Mạng máy tính: điểm 0 -> status='failed'
    mmt = by_code["112061"]
    assert mmt["diem"] == 0.0
    assert mmt["status"] == "failed"
    assert mmt["is_failed"] is True


def test_credit_reconciliation_he_so_vs_db(caplog):
    """
    Kiểm tra đối chiếu tín chỉ:
    Nếu HeSo từ API khác tín chỉ CTĐT trong DB -> ưu tiên tín chỉ DB, ghi log warning.
    Warning không chứa thông tin cá nhân (PII).
    """
    raw_courses = [
        # Môn 111059 (Cơ sở dữ liệu) trong CTĐT chuẩn là 3 TC. Giả sử HeSo từ API bị sai là 2.
        {"ma_mon": "111059", "ten_mon": "Cơ sở dữ liệu", "tin_chi": 2, "diem": 7.5, "dat": True, "so_lan_thi": 1}
    ]

    with caplog.at_level(logging.WARNING):
        reconciled = reconcile_and_deduplicate_lhu_courses(raw_courses)

    assert len(reconciled) == 1
    c = reconciled[0]

    # Ưu tiên tín chỉ trong CTĐT DB (3 tín chỉ)
    assert c["tin_chi"] == 3
    assert c["credits"] == 3

    # Kiểm tra log warning xuất hiện
    assert any("Lệch tín chỉ môn" in record.message for record in caplog.records)
    # Tuyệt đối không chứa PII sinh viên trong log
    for r in caplog.records:
        assert "MSSV" not in r.message
        assert "SV1" not in r.message


def test_schema_mapping_compatibility():
    """
    Kiểm tra danh sách môn sau khi chuyển đổi có đầy đủ các trường song song
    tương thích tuyệt đối với các module hiện có (OCR, GraduationChecker, Normalize).
    """
    raw_courses = [
        {"ma_mon": "102014", "ten_mon": "Tin học đại cương", "tin_chi": 3, "diem": 8.5, "dat": True, "so_lan_thi": 1}
    ]
    reconciled = reconcile_and_deduplicate_lhu_courses(raw_courses)
    course = reconciled[0]

    # Tương thích với chat OCR:
    assert course["course_name"] == "Tin học đại cương"
    assert course["name"] == "Tin học đại cương"
    assert course["course_code"] == "102014"
    assert course["code"] == "102014"
    assert course["grade"] == 8.5
    assert course["diem"] == 8.5
    assert course["credits"] == 3
    assert course["tin_chi"] == 3
    assert course["status"] == "passed"
    assert course["is_failed"] is False
    assert course["source"] == "LHU"


# ==================== INTEGRATION TESTS: API ENDPOINTS & ISOLATION ====================

def test_api_link_status_and_isolation():
    """
    Kiểm tra toàn bộ luồng REST API qua FastAPI TestClient:
    - User A liên kết tài khoản LHU thành công.
    - User A tra cứu status -> linked=True.
    - User B tra cứu status -> linked=False (Cô lập dữ liệu tuyệt đối theo user_id).
    - User B gọi GET /lhu/transcript -> 401.
    - User A gọi DELETE /lhu/link -> hủy liên kết thành công.
    """
    from backend.app.deps import get_current_user
    client = TestClient(app)

    # Giả lập User A đang đăng nhập
    user_a = {"id": 101, "username": "student_a", "role": "student"}
    user_b = {"id": 202, "username": "student_b", "role": "student"}

    app.dependency_overrides[get_current_user] = lambda: user_a

    # Mock LHU portal endpoints cho User A
    def mock_lhu_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/Security/SignIn" in url_str:
            return httpx.Response(200, json={
                "Token": "token_a_123",
                "UserName": "Sinh Vien A",
                "UserID": "SV_A_001"
            })
        elif "/mark/MarkViewer_GetBangDiem" in url_str:
            return httpx.Response(200, json={
                "StudentID": "SV_A_001",
                "HoTen": "Sinh Vien A",
                "DiemTB": 3.4,
                "data": [
                    {
                        "HocKy": "Học kỳ 1",
                        "MonHocID": "102014",
                        "TenMH": "Tin học đại cương",
                        "HeSo": 3,
                        "DiemTBMon": 8.0,
                        "Dau": True
                    }
                ]
            })
        elif "/gm//ChungChi_New_SelectChungChiSinhVien" in url_str or "ChungChi_New_SelectChungChiSinhVien" in url_str:
            return httpx.Response(200, json={
                "data": [
                    {
                        "TenChungChiCan": "TOEIC 550",
                        "TenLoaiChungChi": "Ngoại ngữ",
                        "TinhTrang": "Đã hoàn tất",
                        "TinhTrangXet": 2,
                        "DuyetChungChi": True
                    }
                ]
            })
        return httpx.Response(404)

    # Monkeypatch httpx.Client trong module lhu_connector để dùng MockTransport
    import backend.app.services.lhu_connector as conn_mod
    orig_client_cls = httpx.Client
    try:
        conn_mod.httpx.Client = lambda **kwargs: orig_client_cls(transport=make_mock_transport(mock_lhu_handler), **kwargs)

        # 1. User A liên kết LHU
        res_link = client.post("/lhu/link", json={"student_id": "SV_A_001", "password": "pass_a"})
        assert res_link.status_code == 200
        data_link = res_link.json()
        assert data_link["success"] is True
        assert data_link["total_courses"] == 1
        assert "token" not in data_link  # Tuyệt đối không trả token về client!

        # 2. User A kiểm tra trạng thái
        res_status_a = client.get("/lhu/status")
        assert res_status_a.status_code == 200
        assert res_status_a.json()["linked"] is True
        assert res_status_a.json()["student_id"] == "SV_A_001"

        # 3. User B kiểm tra trạng thái (Cô lập user_id)
        app.dependency_overrides[get_current_user] = lambda: user_b
        res_status_b = client.get("/lhu/status")
        assert res_status_b.status_code == 200
        assert res_status_b.json()["linked"] is False

        # User B không đọc được bảng điểm của User A
        res_trans_b = client.get("/lhu/transcript")
        assert res_trans_b.status_code == 401

        # 4. User A hủy liên kết
        app.dependency_overrides[get_current_user] = lambda: user_a
        res_unlink = client.delete("/lhu/link")
        assert res_unlink.status_code == 200
        assert client.get("/lhu/status").json()["linked"] is False

    finally:
        conn_mod.httpx.Client = orig_client_cls
        app.dependency_overrides.clear()


def test_graduation_check_with_lhu_certificates():
    """
    Kiểm tra đưa kết quả certificates từ LHU vào graduation-check:
    - Chứng chỉ có hoan_tat=True -> đã có/hoàn tất.
    - Chứng chỉ có hoan_tat=False -> chỉ báo 'chưa hoàn tất' cho chứng chỉ này.
    """
    lhu_data = {
        "reconciled_courses": [
            {"ma_mon": "102014", "ten_mon": "Tin học đại cương", "tin_chi": 3, "diem": 8.0, "status": "passed"}
        ],
        "certificates": [
            {"ten": "TOEIC 500", "loai": "Ngoại ngữ", "tinh_trang": "Đạt", "hoan_tat": True, "da_duyet": True},
            {"ten": "MOS Excel", "loai": "Tin học", "tinh_trang": "Chưa hoàn tất", "hoan_tat": False, "da_duyet": False}
        ]
    }

    # Giả lập DB session rỗng (không cần DB thật)
    class DummyDB:
        def execute(self, *args, **kwargs):
            class DummyResult:
                def fetchone(self):
                    class DummyStudent:
                        id = 1
                        user_id = 101
                        student_code = "SV_TEST"
                        full_name = "Nguyen Van Test"
                        major = "Công nghệ thông tin"
                        cohort = "2021"
                    return DummyStudent()
                def fetchall(self):
                    return []
                def scalar(self):
                    return None
            return DummyResult()

    res = calculate_graduation_data(target_student_id=1, db=DummyDB(), explain=False, lhu_data=lhu_data)

    assert res["certificates"]["has_english"] is True
    assert res["certificates"]["english"] == "đã có"

    # Chứng chỉ Tin học có hoan_tat=False -> chỉ báo chưa hoàn tất
    assert res["certificates"]["has_it"] is False
    assert "chưa hoàn tất" in res["certificates"]["it"]
    assert any("chưa hoàn tất" in m and "Tin học" in m for m in res["missing_criteria"])


def test_chat_prioritizes_lhu_and_falls_back_to_ocr():
    """
    Kiểm tra Chat:
    - Khi có phiên LHU active: get_student_academic_and_ocr_context lấy dữ liệu từ LHU (source='LHU').
    - Khi hủy liên kết (hoặc hết hạn): fallback về dữ liệu OCR.
    """
    class DummyDB:
        def execute(self, query, params=None):
            class DummyResult:
                def fetchone(self):
                    query_str = str(query)
                    if "student_ocr_transcripts" in query_str:
                        class DummyOCR:
                            filename = "bang_diem_ocr.png"
                            total_subjects = 1
                            passed_count = 1
                            failed_count = 0
                            courses_data = json.dumps([
                                {"course_name": "Lập trình C", "grade": 7.0, "status": "passed"}
                            ])
                            summary_text = "1 môn Đạt"
                        return DummyOCR()
                    elif "students" in query_str:
                        class DummyStudent:
                            id = 1
                            user_id = 999
                            student_code = "123000999"
                            full_name = "Le Van C"
                            major = "Công nghệ thông tin"
                            cohort = "2021"
                        return DummyStudent()
                    return None

                def fetchall(self):
                    return []

                def scalar(self):
                    return None
            return DummyResult()

    user_id = 999

    # 1. Khi chưa liên kết LHU: fallback về OCR
    clear_user_session(user_id)
    ctx_text, ocr_info, grad_info = get_student_academic_and_ocr_context(db=DummyDB(), user_id=user_id)

    assert ocr_info is not None
    assert ocr_info.get("filename") == "bang_diem_ocr.png"
    assert "bang_diem_ocr.png" in ctx_text

    # 2. Khi đã liên kết LHU: ưu tiên dữ liệu LHU
    session = LHUSession(token="tok_ram", student_id="123000999", user_id=user_id)
    _SESSIONS[user_id] = session
    _CACHED_DATA[user_id] = {
        "transcript": {"gpa_portal": 3.6},
        "reconciled_courses": [
            {"ma_mon": "111070", "ten_mon": "Lập trình hướng đối tượng", "tin_chi": 3, "diem": 9.0, "status": "passed", "is_failed": False}
        ],
        "certificates": []
    }

    ctx_lhu, ocr_lhu, grad_lhu = get_student_academic_and_ocr_context(db=DummyDB(), user_id=user_id)

    assert ocr_lhu is not None
    assert ocr_lhu["source"] == "LHU"
    assert "Cổng trường LHU" in ocr_lhu["filename"]
    assert "KẾT QUẢ BẢNG ĐIỂM TRÍCH XUẤT TỪ CỔNG TRƯỜNG LHU" in ctx_lhu
    assert "Lập trình hướng đối tượng" in ctx_lhu


def test_lhu_connector_request_specification():
    """
    Kiểm tra độc lập và tường minh toàn bộ HTTP request gửi đi:
    1. Đăng nhập: POST {BASE}/Security/SignIn
       - Header: Origin https://app.lhu.edu.vn, Referer https://app.lhu.edu.vn/
       - Header: Accept application/json, text/javascript, */*; q=0.01, Content-Type: application/json; charset=utf-8
       - Body: {"UserID": "221000123", "Password": "mypassword", "DeviceInfo": "{0}{WebAuth}{LHU AI Advisor}"}
    2. Bảng điểm: POST {BASE}/mark/MarkViewer_GetBangDiem
       - Header: Authorization: Bearer <token>
       - Header: Origin https://mark.lhu.edu.vn, Referer https://mark.lhu.edu.vn/
       - Body: RỖNG (content == b"")
    3. Chứng chỉ: POST {BASE}/gm//ChungChi_New_SelectChungChiSinhVien (giữ đúng 2 dấu //)
       - Header: Authorization: Bearer <token>
       - Header: Origin https://graduate.lhu.edu.vn, Referer https://graduate.lhu.edu.vn/
       - Body: {"StudentID": "<mssv>"}
    """
    captured_requests = []

    def mock_all_endpoints(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        url_path = request.url.path
        raw_path = request.url.raw_path.decode("utf-8")

        if url_path == "/Security/SignIn":
            return httpx.Response(200, json={
                "Token": "sample_bearer_token_xyz_999",
                "UserName": "Le Thi C",
                "UserID": "221000123"
            })
        elif url_path == "/mark/MarkViewer_GetBangDiem":
            return httpx.Response(200, json={
                "StudentID": "221000123",
                "HoTen": "Le Thi C",
                "LopID": "22CT111",
                "TinhTrang": "Đang học",
                "DiemTB": 3.75,
                "data": [
                    {
                        "HocKy": "Học kỳ 1",
                        "MonHocID": "111070",
                        "TenMH": "Lập trình hướng đối tượng",
                        "HeSo": 3,
                        "DiemTBMon": 9.0,
                        "SoLanThi": 1,
                        "Dau": True,
                        "UpdateTime": "2023-01-15"
                    }
                ]
            })
        elif "ChungChi_New_SelectChungChiSinhVien" in raw_path:
            return httpx.Response(200, json={
                "data": [
                    {
                        "TenChungChiCan": "Chứng chỉ Tiếng Anh B1",
                        "TenLoaiChungChi": "Ngoại ngữ",
                        "TinhTrang": "Đã hoàn tất",
                        "TinhTrangXet": 2,
                        "DuyetChungChi": True
                    }
                ]
            })
        return httpx.Response(404)

    client = httpx.Client(transport=make_mock_transport(mock_all_endpoints))

    # 1. Gọi login
    session = login(student_id="221000123", password="mypassword", user_id=42, client=client)
    assert len(captured_requests) == 1
    req_login = captured_requests[0]
    assert req_login.method == "POST"
    assert req_login.url.path == "/Security/SignIn"
    assert req_login.headers["Accept"] == "application/json, text/javascript, */*; q=0.01"
    assert "application/json" in req_login.headers["Content-Type"]
    assert req_login.headers["Origin"] == "https://app.lhu.edu.vn"
    assert req_login.headers["Referer"] == "https://app.lhu.edu.vn/"
    assert "Authorization" not in req_login.headers
    body_login = json.loads(req_login.content)
    assert body_login == {
        "UserID": "221000123",
        "Password": "mypassword",
        "DeviceInfo": "{0}{WebAuth}{LHU AI Advisor}"
    }

    # 2. Gọi fetch_transcript
    transcript = fetch_transcript(session, client=client)
    assert len(captured_requests) == 2
    req_transcript = captured_requests[1]
    assert req_transcript.method == "POST"
    assert req_transcript.url.path == "/mark/MarkViewer_GetBangDiem"
    assert req_transcript.headers["Accept"] == "application/json, text/javascript, */*; q=0.01"
    assert "application/json" in req_transcript.headers["Content-Type"]
    assert req_transcript.headers["Origin"] == "https://mark.lhu.edu.vn"
    assert req_transcript.headers["Referer"] == "https://mark.lhu.edu.vn/"
    assert req_transcript.headers["Authorization"] == "Bearer sample_bearer_token_xyz_999"
    assert req_transcript.content == b""  # Không có body, content rỗng b""
    assert transcript["gpa_portal"] == 3.75

    # 3. Gọi fetch_certificates
    certs = fetch_certificates(session, client=client)
    assert len(captured_requests) == 3
    req_certs = captured_requests[2]
    assert req_certs.method == "POST"
    # Kiểm tra URL giữ đúng 2 dấu slash //
    raw_path_certs = req_certs.url.raw_path.decode("utf-8")
    assert "/gm//ChungChi_New_SelectChungChiSinhVien" in raw_path_certs
    assert req_certs.headers["Accept"] == "application/json, text/javascript, */*; q=0.01"
    assert "application/json" in req_certs.headers["Content-Type"]
    assert req_certs.headers["Origin"] == "https://graduate.lhu.edu.vn"
    assert req_certs.headers["Referer"] == "https://graduate.lhu.edu.vn/"
    assert req_certs.headers["Authorization"] == "Bearer sample_bearer_token_xyz_999"
    body_certs = json.loads(req_certs.content)
    assert body_certs == {"StudentID": "221000123"}
    assert len(certs) == 1
    assert certs[0]["hoan_tat"] is True


def test_api_401_403_raises_session_expired():
    """Kiểm tra khi LHU portal trả về 401 hoặc 403 ở fetch transcript/certificates -> raise HTTPException 401."""
    session = LHUSession(token="invalid_token", student_id="221000123", user_id=1)

    for status_code in [401, 403]:
        def handler_err(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code, json={"message": "Unauthorized or Forbidden"})

        client = httpx.Client(transport=make_mock_transport(handler_err))

        with pytest.raises(HTTPException) as exc_t:
            fetch_transcript(session, client=client)
        assert exc_t.value.status_code == 401
        assert "hết hạn" in exc_t.value.detail

        with pytest.raises(HTTPException) as exc_c:
            fetch_certificates(session, client=client)
        assert exc_c.value.status_code == 401
        assert "hết hạn" in exc_c.value.detail


def test_certificate_completion_conditions():
    """Kiểm tra logic hoàn tất chứng chỉ: TinhTrangXet == 2 HOẶC TinhTrang == 'Đã hoàn tất'."""
    session = LHUSession(token="tok", student_id="SV001", user_id=1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "data": [
                {"TenChungChiCan": "CC1", "TinhTrang": "Đã hoàn tất", "TinhTrangXet": 0},   # TinhTrang == "Đã hoàn tất"
                {"TenChungChiCan": "CC2", "TinhTrang": "Chờ duyệt", "TinhTrangXet": 2},      # TinhTrangXet == 2
                {"TenChungChiCan": "CC3", "TinhTrang": "Chưa hoàn tất", "TinhTrangXet": 1},  # Chưa đạt cả 2 -> False
                {"TenChungChiCan": "CC4", "TinhTrang": "Hết hạn", "TinhTrangXet": 3},        # False
            ]
        })

    client = httpx.Client(transport=make_mock_transport(handler))
    certs = fetch_certificates(session, client=client)

    assert certs[0]["hoan_tat"] is True
    assert certs[1]["hoan_tat"] is True
    assert certs[2]["hoan_tat"] is False
    assert certs[3]["hoan_tat"] is False


def test_api_get_summary_success_without_pii():
    """
    Kiểm tra endpoint GET /lhu/summary:
    - Trả về đúng: gpa_portal, gpa (tính bằng code hệ thống), total_accumulated_credits, debt_courses_count.
    - Trả về danh sách credit_discrepancies (mã môn, HeSo, db_credits).
    - Trả về danh sách certificates và trạng thái hoàn tất.
    - TUYỆT ĐỐI KHÔNG chứa thông tin cá nhân (MSSV, Họ tên, Ngày sinh, Token).
    """
    from backend.app.deps import get_current_user
    client = TestClient(app)

    user_test = {"id": 888, "username": "student_test_summary", "role": "student"}
    app.dependency_overrides[get_current_user] = lambda: user_test

    try:
        session = LHUSession(
            token="secret_token_12345",
            student_id="221009999",
            user_id=888,
            full_name="Bui Van An Ninh",
            expires_at=time.time() + 1800
        )
        _SESSIONS[888] = session

        # Giả lập bảng điểm có:
        # 1. Môn 102014 đạt: 3 tín chỉ, điểm 8.0
        # 2. Môn 111059 lệch tín chỉ: HeSo API = 2, trong khi CTĐT DB = 3 tín chỉ (điểm 7.0 đạt)
        # 3. Môn 111062 rớt: 3 tín chỉ, điểm 3.0 (nợ môn)
        raw_courses = [
            {"ma_mon": "102014", "ten_mon": "Tin học đại cương", "tin_chi": 3, "diem": 8.0, "dat": True},
            {"ma_mon": "111059", "ten_mon": "Cơ sở dữ liệu", "tin_chi": 2, "diem": 7.0, "dat": True},
            {"ma_mon": "111062", "ten_mon": "CTDL & GT", "tin_chi": 3, "diem": 3.0, "dat": False},
        ]
        reconciled = reconcile_and_deduplicate_lhu_courses(raw_courses)

        certs = [
            {"ten": "TOEIC 500", "loai": "Ngoại ngữ", "tinh_trang": "Đạt", "hoan_tat": True, "da_duyet": True},
            {"ten": "Tin học MOS", "loai": "Tin học", "tinh_trang": "Chưa hoàn tất", "hoan_tat": False, "da_duyet": False}
        ]

        _CACHED_DATA[888] = {
            "transcript": {
                "student": {"student_id": "221009999", "full_name": "Bui Van An Ninh"},
                "gpa_portal": 3.12,
                "courses": raw_courses
            },
            "reconciled_courses": reconciled,
            "certificates": certs,
            "cached_at": time.time()
        }

        # Gọi endpoint GET /lhu/summary
        res = client.get("/lhu/summary")
        assert res.status_code == 200
        data = res.json()

        # 1. Kiểm tra số liệu tính toán
        assert data["gpa_portal"] == 3.12
        assert isinstance(data["gpa"], float)
        assert data["gpa"] > 0
        assert data["total_accumulated_credits"] == 6  # 3 TC môn Tin học ĐC + 3 TC môn CSDL (đối chiếu DB)
        assert data["debt_courses_count"] == 1  # 1 môn CTDL & GT rớt

        # 2. Kiểm tra lệch tín chỉ môn CSDL (HeSo=2 vs DB=3)
        discrepancies = data["credit_discrepancies"]
        assert len(discrepancies) == 1
        disc = discrepancies[0]
        assert disc["ma_mon"] == "111059"
        assert disc["he_so"] == 2 or disc["HeSo"] == 2
        assert disc["db_credits"] == 3

        # 3. Kiểm tra danh sách chứng chỉ
        assert len(data["certificates"]) == 2
        assert data["certificates"][0]["ten"] == "TOEIC 500"
        assert data["certificates"][0]["hoan_tat"] is True
        assert data["certificates"][1]["ten"] == "Tin học MOS"
        assert data["certificates"][1]["hoan_tat"] is False

        # 4. KHẲNG ĐỊNH TUYỆT ĐỐI KHÔNG CÓ THÔNG TIN CÁ NHÂN (PII)
        assert "student_id" not in data
        assert "student_code" not in data
        assert "mssv" not in data
        assert "full_name" not in data
        assert "ho_ten" not in data
        assert "date_of_birth" not in data
        assert "ngay_sinh" not in data
        assert "token" not in data
        assert "token" not in str(data).lower()
        assert "221009999" not in str(data)
        assert "Bui Van An Ninh" not in str(data)

    finally:
        app.dependency_overrides.clear()


def test_api_get_summary_unauthorized_when_not_linked():
    """Kiểm tra khi chưa liên kết hoặc phiên hết hạn -> GET /lhu/summary trả về 401."""
    from backend.app.deps import get_current_user
    client = TestClient(app)

    user_unlinked = {"id": 9999, "username": "student_unlinked", "role": "student"}
    app.dependency_overrides[get_current_user] = lambda: user_unlinked

    try:
        clear_user_session(9999)
        res = client.get("/lhu/summary")
        assert res.status_code == 401
        assert "hết hạn hoặc chưa liên kết" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()
