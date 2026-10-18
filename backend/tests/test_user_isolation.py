import io
import pytest
from datetime import datetime, timezone, timedelta
from jose import jwt
from fastapi.testclient import TestClient
from sqlalchemy import text
from backend.api import app
from backend.app.config import settings
from backend.app.db import SessionLocal

from backend.app.security import get_password_hash

client = TestClient(app)

def make_token(user_id: int, role: str = "student") -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

@pytest.fixture
def test_user1():
    db = SessionLocal()
    db.execute(text("DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM chat_sessions WHERE user_id IN (SELECT id FROM users WHERE username = 'test_isolation_1'))"))
    db.execute(text("DELETE FROM chat_sessions WHERE user_id IN (SELECT id FROM users WHERE username = 'test_isolation_1')"))
    db.execute(text("DELETE FROM users WHERE username = 'test_isolation_1'"))
    db.commit()

    pwd_hash = get_password_hash("Test@123")
    res = db.execute(
        text("INSERT INTO users (username, password_hash, role) OUTPUT INSERTED.id VALUES ('test_isolation_1', :pwd, 'student')"),
        {"pwd": pwd_hash}
    )
    uid = res.fetchone()[0]
    db.commit()
    db.close()

    yield uid

    db = SessionLocal()
    db.execute(text("DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM chat_sessions WHERE user_id = :uid)"), {"uid": uid})
    db.execute(text("DELETE FROM chat_sessions WHERE user_id = :uid"), {"uid": uid})
    db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})
    db.commit()
    db.close()

@pytest.fixture
def test_user2():
    db = SessionLocal()
    db.execute(text("DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM chat_sessions WHERE user_id IN (SELECT id FROM users WHERE username = 'test_isolation_2'))"))
    db.execute(text("DELETE FROM chat_sessions WHERE user_id IN (SELECT id FROM users WHERE username = 'test_isolation_2')"))
    db.execute(text("DELETE FROM users WHERE username = 'test_isolation_2'"))
    db.commit()

    pwd_hash = get_password_hash("Test@123")
    res = db.execute(
        text("INSERT INTO users (username, password_hash, role) OUTPUT INSERTED.id VALUES ('test_isolation_2', :pwd, 'student')"),
        {"pwd": pwd_hash}
    )
    uid = res.fetchone()[0]
    db.commit()
    db.close()

    yield uid

    db = SessionLocal()
    db.execute(text("DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM chat_sessions WHERE user_id = :uid)"), {"uid": uid})
    db.execute(text("DELETE FROM chat_sessions WHERE user_id = :uid"), {"uid": uid})
    db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})
    db.commit()
    db.close()

@pytest.fixture
def auth_headers_user1(test_user1):
    token = make_token(test_user1, "student")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def auth_headers_user2(test_user2):
    token = make_token(test_user2, "student")
    return {"Authorization": f"Bearer {token}"}

def test_user_session_isolation(test_user1, test_user2, auth_headers_user1, auth_headers_user2):
    db = SessionLocal()
    sess_id = None
    try:
        # User 1 creates a session
        sess_id = db.execute(
            text("INSERT INTO chat_sessions (user_id, title, updated_at) OUTPUT INSERTED.id VALUES (:uid, 'Test01 Session', SYSDATETIME())"),
            {"uid": test_user1}
        ).scalar()
        db.execute(
            text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, 'user', 'Hello from test01')"),
            {"sid": sess_id}
        )
        db.commit()

        # 1. User 1 can list their own session
        res1 = client.get("/chat/sessions", headers=auth_headers_user1)
        assert res1.status_code == 200
        user1_sess_ids = [s["id"] for s in res1.json()]
        assert sess_id in user1_sess_ids

        # 2. User 2 cannot see user 1's session in their list
        res2 = client.get("/chat/sessions", headers=auth_headers_user2)
        assert res2.status_code == 200
        user2_sess_ids = [s["id"] for s in res2.json()]
        assert sess_id not in user2_sess_ids

        # 3. User 2 cannot access messages of user 1's session (must return 403 Forbidden)
        res_forbidden = client.get(f"/chat/sessions/{sess_id}/messages", headers=auth_headers_user2)
        assert res_forbidden.status_code == 403

        # 4. User 2 cannot rename user 1's session
        res_rename_forbidden = client.patch(
            f"/chat/sessions/{sess_id}",
            json={"title": "Hacked Title"},
            headers=auth_headers_user2,
        )
        assert res_rename_forbidden.status_code == 403

        # 5. User 2 cannot delete user 1's session
        res_del_forbidden = client.delete(f"/chat/sessions/{sess_id}", headers=auth_headers_user2)
        assert res_del_forbidden.status_code == 403

        # 6. User 1 can rename their session
        res_rename_ok = client.patch(
            f"/chat/sessions/{sess_id}",
            json={"title": "Tên mới hợp lệ"},
            headers=auth_headers_user1,
        )
        assert res_rename_ok.status_code == 200

        # 7. User 1 can delete their session
        res_del_ok = client.delete(f"/chat/sessions/{sess_id}", headers=auth_headers_user1)
        assert res_del_ok.status_code == 200

    finally:
        if sess_id:
            db.execute(text("DELETE FROM chat_messages WHERE session_id = :sid"), {"sid": sess_id})
            db.execute(text("DELETE FROM chat_sessions WHERE id = :sid"), {"sid": sess_id})
            db.commit()
        db.close()

def test_chat_upload_validation(auth_headers_user1):
    # Test uploading > 5 files
    files = [("files", (f"file_{i}.txt", io.BytesIO(b"content"), "text/plain")) for i in range(6)]
    res = client.post("/chat/upload", files=files, headers=auth_headers_user1)
    assert res.status_code == 400
    assert "tối đa 5 tệp" in res.json()["detail"]

    # Test invalid extension
    invalid_file = [("files", ("script.exe", io.BytesIO(b"echo 1"), "application/octet-stream"))]
    res_inv = client.post("/chat/upload", files=invalid_file, headers=auth_headers_user1)
    assert res_inv.status_code == 400
    assert "không được hỗ trợ" in res_inv.json()["detail"]
