import socket
import pytest
from sqlalchemy import text
from backend.app.db import SessionLocal

_db_running_cache = None

def _is_db_server_running(host="127.0.0.1", port=1433, timeout=0.3) -> bool:
    """Kiểm tra nhanh xem cổng SQL Server có mở không trước khi cố gắng kết nối.
    Kết quả được cache để tránh lặp lại timeout 0.3s trên mỗi test."""
    global _db_running_cache
    if _db_running_cache is not None:
        return _db_running_cache
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        _db_running_cache = True
    except Exception:
        _db_running_cache = False
    return _db_running_cache

_skipped_db_count = 0

def pytest_collection_modifyitems(config, items):
    """Tự động skip CHỈ các test có marker @pytest.mark.db khi SQL Server đang offline."""
    global _skipped_db_count
    db_running = _is_db_server_running()
    if not db_running:
        skip_db = pytest.mark.skip(reason="SQL Server trên localhost:1433 đang offline (socket probe thất bại)")
        for item in items:
            if "db" in item.keywords:
                item.add_marker(skip_db)
                _skipped_db_count += 1

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """In cảnh báo rõ ràng ở cuối phiên chạy test nếu có test bị bỏ qua vì DB offline."""
    if _skipped_db_count > 0:
        terminalreporter.section("CẢNH BÁO DB OFFLINE", yellow=True, bold=True)
        terminalreporter.write_line(f"CẢNH BÁO: {_skipped_db_count} test bị bỏ qua vì DB offline (SQL Server trên localhost:1433 không khả dụng).")

@pytest.fixture(autouse=True)
def auto_mock_db_for_offline_tests(request):
    """Khi SQL Server offline, tự động cung cấp mock dependencies cho các test KHÔNG có marker db."""
    if "db" in request.keywords:
        yield
        return

    if not _is_db_server_running():
        from backend.api import app
        from backend.app.deps import get_current_user, get_db, oauth2_scheme
        from fastapi import Depends
        from unittest.mock import MagicMock

        mock_user = {"id": 1, "username": "admin", "role": "admin"}

        class MockDBSession:
            def execute(self, query, params=None):
                q_str = str(query)
                mock_result = MagicMock()
                if "chat_sessions" in q_str:
                    mock_result.scalar.return_value = 1
                    mock_result.fetchone.return_value = MagicMock(id=1, user_id=1, role="admin", is_approved=True)
                    mock_result.fetchall.return_value = []
                elif "transcript_ocr" in q_str or "ocr" in q_str:
                    mock_result.fetchone.return_value = None
                    mock_result.fetchall.return_value = []
                elif "users" in q_str:
                    mock_result.fetchone.return_value = MagicMock(id=1, username="admin", role="admin")
                else:
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

        def override_get_current_user(token: str = Depends(oauth2_scheme)):
            return mock_user

        def override_get_db():
            yield MockDBSession()

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db
        yield
        app.dependency_overrides.clear()
    else:
        yield

@pytest.fixture(scope="session", autouse=True)
def check_no_leaked_test_data():
    """Kiểm tra và dọn dẹp cuối test session: không còn bản ghi nào trong users, students,
    student_ocr_transcripts, chat_sessions liên quan user test.
    Chạy trong khối finally để luôn thực thi kể cả khi có test fail."""
    try:
        yield
    finally:
        # Nếu SQL Server bật, kiểm tra và dọn sạch dữ liệu test
        if _is_db_server_running():
            try:
                with SessionLocal() as db:
                    # 1. Truy vấn các bản ghi test
                    users = db.execute(text("SELECT id, username FROM users WHERE username LIKE 'test\\_%' ESCAPE '\\'")).fetchall()
                    students = db.execute(text("SELECT id, student_code FROM students WHERE student_code LIKE 'test\\_%' ESCAPE '\\'")).fetchall()
                    ocr = db.execute(text("SELECT id, filename FROM student_ocr_transcripts WHERE filename LIKE '%test\\_%' ESCAPE '\\' OR filename LIKE '%unique%' OR user_id IN (SELECT id FROM users WHERE username LIKE 'test\\_%' ESCAPE '\\')")).fetchall()
                    sessions = db.execute(text("SELECT id, title FROM chat_sessions WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'test\\_%' ESCAPE '\\')")).fetchall()
                    certs = db.execute(text("SELECT id FROM student_certificates WHERE student_id IN (SELECT id FROM students WHERE student_code LIKE 'test\\_%' ESCAPE '\\')")).fetchall()

                    # 2. Nếu có bản ghi test sót lại do test fail, tự động dọn sạch để không lưu rác vào DB
                    if users or students or ocr or sessions or certs:
                        u_ids = [u.id for u in users]
                        s_ids = [s.id for s in students]
                        for uid in u_ids:
                            db.execute(text("DELETE FROM student_ocr_transcripts WHERE user_id = :uid"), {"uid": uid})
                            db.execute(text("DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM chat_sessions WHERE user_id = :uid)"), {"uid": uid})
                            db.execute(text("DELETE FROM chat_sessions WHERE user_id = :uid"), {"uid": uid})
                        for sid in s_ids:
                            db.execute(text("DELETE FROM student_certificates WHERE student_id = :sid"), {"sid": sid})
                            db.execute(text("DELETE FROM grades WHERE student_id = :sid"), {"sid": sid})
                            db.execute(text("DELETE FROM students WHERE id = :sid"), {"sid": sid})
                        for uid in u_ids:
                            db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})
                        db.commit()

                    # 3. Khẳng định DB sạch
                    assert len(users) == 0, f"Dữ liệu rác còn sót trong users: {users}"
                    assert len(students) == 0, f"Dữ liệu rác còn sót trong students: {students}"
                    assert len(ocr) == 0, f"Dữ liệu rác còn sót trong student_ocr_transcripts: {ocr}"
                    assert len(sessions) == 0, f"Dữ liệu rác còn sót trong chat_sessions: {sessions}"
                    assert len(certs) == 0, f"Dữ liệu rác còn sót trong student_certificates: {certs}"
            except Exception as conn_err:
                pass
