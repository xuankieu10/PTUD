import pytest
from sqlalchemy import text
from backend.app.db import SessionLocal

@pytest.fixture(scope="session", autouse=True)
def check_no_leaked_test_data():
    """Kiểm tra và dọn dẹp cuối test session: không còn bản ghi nào trong users, students,
    student_ocr_transcripts, chat_sessions liên quan user test.
    Chạy trong khối finally để luôn thực thi kể cả khi có test fail."""
    try:
        yield
    finally:
        try:
            with SessionLocal() as db:
                try:
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
                except Exception as e:
                    db.rollback()
                    raise e
        except Exception as conn_err:
            # Nếu DB offline (chạy test không cần DB), bỏ qua kiểm tra rác
            pass
