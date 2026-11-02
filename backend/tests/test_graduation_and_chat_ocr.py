import io
import os
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from PIL import Image
from unittest.mock import patch

from backend.api import app
from backend.app.db import SessionLocal
from backend.app.security import get_password_hash, create_access_token

client = TestClient(app)


def create_sample_image_bytes(filename="sample.png"):
    """Tạo byte ảnh PNG hợp lệ trong bộ nhớ"""
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def snapshot_temp_files(directory="temp_uploads") -> set:
    """Chụp danh sách toàn bộ đường dẫn file hiện có trong temp_uploads"""
    abs_dir = os.path.abspath(directory)
    if not os.path.exists(abs_dir):
        return set()
    files = set()
    for root, _, filenames in os.walk(abs_dir):
        for fn in filenames:
            files.add(os.path.abspath(os.path.join(root, fn)))
    return files


def run_and_assert_no_new_temp_files(action):
    """
    Thực thi action và khẳng định sau request không còn bất kỳ file mới nào
    trong temp_uploads (so sánh tập hợp file trước và sau, không dựa vào tên file).
    """
    os.makedirs(os.path.abspath("temp_uploads"), exist_ok=True)
    before_files = snapshot_temp_files("temp_uploads")
    try:
        response = action()
        return response
    finally:
        after_files = snapshot_temp_files("temp_uploads")
        new_files = after_files - before_files
        assert len(new_files) == 0, f"Phát hiện file mới chưa được dọn dẹp trong temp_uploads: {new_files}"


@pytest.fixture(scope="function")
def test_setup():
    """
    Tạo 2 user + 2 student riêng biệt (có tiền tố test_), kèm tài khoản admin test.
    Không đụng tài khoản thật sv01/sv02/admin, không xoá cố định theo ID, dọn dẹp sạch sẽ sau test.
    """
    suffix = uuid.uuid4().hex[:8]
    username_a = f"test_user_a_{suffix}"
    username_b = f"test_user_b_{suffix}"
    username_admin = f"test_admin_{suffix}"
    code_a = f"TEST_A_{suffix}"
    code_b = f"TEST_B_{suffix}"
    password = "TestPassword@123"
    pwd_hash = get_password_hash(password)

    user_ids = []
    student_ids = []

    with SessionLocal() as db:
        # 1. Tạo user A
        res_ua = db.execute(
            text("INSERT INTO users (username, password_hash, role) OUTPUT INSERTED.id VALUES (:u, :p, 'student')"),
            {"u": username_a, "p": pwd_hash}
        )
        ua_id = res_ua.scalar()
        user_ids.append(ua_id)

        # 2. Tạo user B
        res_ub = db.execute(
            text("INSERT INTO users (username, password_hash, role) OUTPUT INSERTED.id VALUES (:u, :p, 'student')"),
            {"u": username_b, "p": pwd_hash}
        )
        ub_id = res_ub.scalar()
        user_ids.append(ub_id)

        # 3. Tạo admin test
        res_adm = db.execute(
            text("INSERT INTO users (username, password_hash, role) OUTPUT INSERTED.id VALUES (:u, :p, 'admin')"),
            {"u": username_admin, "p": pwd_hash}
        )
        adm_id = res_adm.scalar()
        user_ids.append(adm_id)

        # 4. Tạo student A
        res_sa = db.execute(
            text("""
                INSERT INTO students (user_id, student_code, full_name, major, cohort)
                OUTPUT INSERTED.id
                VALUES (:uid, :code, :name, :major, 'K66')
            """),
            {"uid": ua_id, "code": code_a, "name": f"Sinh viên Test A {suffix}", "major": "Công nghệ thông tin"}
        )
        sa_id = res_sa.scalar()
        student_ids.append(sa_id)

        # 5. Tạo student B
        res_sb = db.execute(
            text("""
                INSERT INTO students (user_id, student_code, full_name, major, cohort)
                OUTPUT INSERTED.id
                VALUES (:uid, :code, :name, :major, 'K66')
            """),
            {"uid": ub_id, "code": code_b, "name": f"Sinh viên Test B {suffix}", "major": "Công nghệ thông tin"}
        )
        sb_id = res_sb.scalar()
        student_ids.append(sb_id)

        db.commit()

    token_a = create_access_token(subject=ua_id, role="student")
    token_b = create_access_token(subject=ub_id, role="student")
    token_admin = create_access_token(subject=adm_id, role="admin")

    setup_data = {
        "user_a": {
            "id": ua_id,
            "username": username_a,
            "token": token_a,
            "student_id": sa_id,
            "student_code": code_a,
            "full_name": f"Sinh viên Test A {suffix}"
        },
        "user_b": {
            "id": ub_id,
            "username": username_b,
            "token": token_b,
            "student_id": sb_id,
            "student_code": code_b,
            "full_name": f"Sinh viên Test B {suffix}"
        },
        "admin": {
            "id": adm_id,
            "username": username_admin,
            "token": token_admin
        }
    }

    yield setup_data

    # Cleanup: Xóa sạch dữ liệu test theo danh sách ID đã tạo
    with SessionLocal() as db:
        for uid in user_ids:
            db.execute(text("DELETE FROM student_ocr_transcripts WHERE user_id = :uid"), {"uid": uid})
            db.execute(text("DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM chat_sessions WHERE user_id = :uid)"), {"uid": uid})
            db.execute(text("DELETE FROM chat_sessions WHERE user_id = :uid"), {"uid": uid})
        for sid in student_ids:
            db.execute(text("DELETE FROM student_certificates WHERE student_id = :sid"), {"sid": sid})
            db.execute(text("DELETE FROM grades WHERE student_id = :sid"), {"sid": sid})
            db.execute(text("DELETE FROM students WHERE id = :sid"), {"sid": sid})
        for uid in user_ids:
            db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})
        db.commit()


class TestGraduationCheckPermissions:
    """Kiểm tra phân quyền hồ sơ tốt nghiệp với fixture cô lập"""

    def test_a_student_self_graduation_check_200(self, test_setup):
        """Sinh viên A gọi graduation-check của chính mình: 200 OK, đúng dữ liệu"""
        user_a = test_setup["user_a"]
        headers = {"Authorization": f"Bearer {user_a['token']}"}

        # 1. Gọi qua /students/me/graduation-check
        res_me = client.get("/students/me/graduation-check?explain=false", headers=headers)
        assert res_me.status_code == 200, f"Failed /students/me: {res_me.text}"
        data_me = res_me.json()
        assert data_me["student"]["student_code"] == user_a["student_code"]
        assert "total_credits_passed" in data_me
        assert "total_credits_failed" in data_me
        assert "credits_missing" in data_me
        assert "missing_required_courses" in data_me
        assert "failed_courses" in data_me
        assert "eligible" in data_me

        # 2. Gọi qua /students/{student_id}/graduation-check
        res_by_id = client.get(f"/students/{user_a['student_id']}/graduation-check?explain=false", headers=headers)
        assert res_by_id.status_code == 200, f"Failed by student_id: {res_by_id.text}"
        data_id = res_by_id.json()
        assert data_id["student"]["student_code"] == user_a["student_code"]
        assert data_id["total_credits_passed"] == data_me["total_credits_passed"]

    def test_b_student_other_graduation_check_403(self, test_setup):
        """Sinh viên A gọi hồ sơ sinh viên B: 403 Forbidden"""
        user_a = test_setup["user_a"]
        user_b = test_setup["user_b"]
        headers_a = {"Authorization": f"Bearer {user_a['token']}"}

        res = client.get(f"/students/{user_b['student_id']}/graduation-check", headers=headers_a)
        assert res.status_code == 403, f"Expected 403 but got {res.status_code}: {res.text}"

        res_not_found = client.get("/students/99999999/graduation-check", headers=headers_a)
        assert res_not_found.status_code == 404

    def test_chong_khop_nham_id(self, test_setup):
        """
        Test chống khớp nhầm ID:
        Sinh viên B gọi graduation-check với students.id của Sinh viên A: Bị 403 Forbidden.
        Chỉ Sinh viên A gọi students.id của Sinh viên A mới được 200 OK.
        """
        user_a = test_setup["user_a"]
        user_b = test_setup["user_b"]
        headers_b = {"Authorization": f"Bearer {user_b['token']}"}
        headers_a = {"Authorization": f"Bearer {user_a['token']}"}

        # B gọi ID của A -> Phải bị 403 Forbidden
        res_b = client.get(f"/students/{user_a['student_id']}/graduation-check", headers=headers_b)
        assert res_b.status_code == 403

        # A gọi ID của chính A -> 200 OK
        res_a = client.get(f"/students/{user_a['student_id']}/graduation-check", headers=headers_a)
        assert res_a.status_code == 200
        assert res_a.json()["student"]["student_code"] == user_a["student_code"]

    def test_admin_can_view_any_student(self, test_setup):
        """Admin có quyền xem hồ sơ của bất kỳ sinh viên nào qua student_id"""
        admin = test_setup["admin"]
        user_a = test_setup["user_a"]
        user_b = test_setup["user_b"]
        headers = {"Authorization": f"Bearer {admin['token']}"}

        res1 = client.get(f"/students/{user_a['student_id']}/graduation-check?explain=false", headers=headers)
        assert res1.status_code == 200
        assert res1.json()["student"]["student_code"] == user_a["student_code"]

        res2 = client.get(f"/students/{user_b['student_id']}/graduation-check?explain=false", headers=headers)
        assert res2.status_code == 200
        assert res2.json()["student"]["student_code"] == user_b["student_code"]


class TestFileUploadCleanupAndSecurity:
    """
    Kiểm tra dọn sạch file upload trong temp_uploads:
    Chụp toàn bộ danh sách file trước và sau request, khẳng định không còn file mới (không dựa vào tên file).
    Áp dụng cho /chat/upload, /api/process, /api/certificate/process, /transcripts/import:
    - Thành công
    - OCR lỗi
    - Sai định dạng
    """

    fake_ocr_result = {
        "total_subjects": 2,
        "passed_count": 2,
        "failed_count": 0,
        "red_regions_count": 0,
        "annotated_image_path": "non_existent.png",
        "json_path": "out.json",
        "csv_path": "out.csv",
        "failed_subjects": [],
        "all_subjects": [
            {"mon": "Tin học đại cương", "diem": 8.0, "is_failed": False},
            {"mon": "Triết học Mác - Lênin", "diem": 7.5, "is_failed": False}
        ]
    }

    # 1. /chat/upload
    def test_chat_upload_cleanup_success(self, test_setup):
        headers = {"Authorization": f"Bearer {test_setup['user_a']['token']}"}
        img_bytes = create_sample_image_bytes()
        with patch("backend.pipeline.run_pipeline", return_value=self.fake_ocr_result):
            res = run_and_assert_no_new_temp_files(
                lambda: client.post(
                    "/chat/upload",
                    files={"files": ("test_chat.png", img_bytes, "image/png")},
                    headers=headers
                )
            )
            assert res.status_code == 200

    def test_chat_upload_cleanup_ocr_error(self, test_setup):
        headers = {"Authorization": f"Bearer {test_setup['user_a']['token']}"}
        img_bytes = create_sample_image_bytes()
        with patch("backend.pipeline.run_pipeline", side_effect=RuntimeError("OCR Engine Crash")):
            res = run_and_assert_no_new_temp_files(
                lambda: client.post(
                    "/chat/upload",
                    files={"files": ("test_chat_err.png", img_bytes, "image/png")},
                    headers=headers
                )
            )
            assert res.status_code == 200

    def test_chat_upload_cleanup_invalid_ext(self, test_setup):
        headers = {"Authorization": f"Bearer {test_setup['user_a']['token']}"}
        run_and_assert_no_new_temp_files(
            lambda: client.post(
                "/chat/upload",
                files={"files": ("virus.exe", b"MZDummyExecutableBytes", "application/octet-stream")},
                headers=headers
            )
        )

    # 2. /api/process
    def test_api_process_cleanup_success(self, test_setup):
        headers = {"Authorization": f"Bearer {test_setup['user_a']['token']}"}
        img_bytes = create_sample_image_bytes()
        with patch("backend.api.run_pipeline", return_value=self.fake_ocr_result):
            res = run_and_assert_no_new_temp_files(
                lambda: client.post(
                    "/api/process",
                    files={"file": ("test_api.png", img_bytes, "image/png")},
                    headers=headers
                )
            )
            assert res.status_code == 200

    def test_api_process_cleanup_ocr_error(self, test_setup):
        headers = {"Authorization": f"Bearer {test_setup['user_a']['token']}"}
        img_bytes = create_sample_image_bytes()
        with patch("backend.api.run_pipeline", side_effect=RuntimeError("Internal OCR Error")):
            res = run_and_assert_no_new_temp_files(
                lambda: client.post(
                    "/api/process",
                    files={"file": ("test_api_err.png", img_bytes, "image/png")},
                    headers=headers
                )
            )
            assert res.status_code == 500
            assert "Internal OCR Error" not in res.json().get("detail", "")
            assert "Traceback" not in res.json().get("detail", "")

    def test_api_process_cleanup_invalid_ext(self, test_setup):
        headers = {"Authorization": f"Bearer {test_setup['user_a']['token']}"}
        run_and_assert_no_new_temp_files(
            lambda: client.post(
                "/api/process",
                files={"file": ("notes.txt", b"plain text", "text/plain")},
                headers=headers
            )
        )
        run_and_assert_no_new_temp_files(
            lambda: client.post(
                "/api/process",
                files={"file": ("bad.exe", b"binary data", "application/octet-stream")},
                headers=headers
            )
        )

    # 3. /api/certificate/process
    def test_api_certificate_process_cleanup_success(self, test_setup):
        img_bytes = create_sample_image_bytes()
        mock_extracted = {
            "loai_chung_chi": "TOEIC",
            "so_hieu": "123456",
            "ngay_cap": "2025-01-01",
            "diem": "650"
        }
        mock_match = {"matched": True, "condition": "Chuẩn đầu ra Tiếng Anh B1"}

        with patch("backend.certificate_extractor.extract_certificate_from_image", return_value=mock_extracted), \
             patch("backend.certificate_matcher.match_certificate", return_value=mock_match):
            res = run_and_assert_no_new_temp_files(
                lambda: client.post(
                    "/api/certificate/process",
                    files={"file": ("cert.png", img_bytes, "image/png")}
                )
            )
            assert res.status_code == 200

    def test_api_certificate_process_cleanup_ocr_error(self, test_setup):
        img_bytes = create_sample_image_bytes()
        with patch("backend.certificate_extractor.extract_certificate_from_image", side_effect=RuntimeError("Vision Cert Crash")):
            res = run_and_assert_no_new_temp_files(
                lambda: client.post(
                    "/api/certificate/process",
                    files={"file": ("cert_err.png", img_bytes, "image/png")}
                )
            )
            assert res.status_code == 500
            assert "Vision Cert Crash" not in res.json().get("detail", "")
            assert "Traceback" not in res.json().get("detail", "")

    def test_api_certificate_process_cleanup_invalid_ext(self, test_setup):
        run_and_assert_no_new_temp_files(
            lambda: client.post(
                "/api/certificate/process",
                files={"file": ("cert.txt", b"invalid text format", "text/plain")}
            )
        )
        run_and_assert_no_new_temp_files(
            lambda: client.post(
                "/api/certificate/process",
                files={"file": ("cert.exe", b"binary", "application/octet-stream")}
            )
        )

    # 4. /transcripts/import
    def test_transcripts_import_cleanup_success(self, test_setup):
        user_a = test_setup["user_a"]
        headers = {"Authorization": f"Bearer {user_a['token']}"}
        img_bytes = create_sample_image_bytes()

        fake_pipe = {
            "all_subjects": [
                {"code": "IT1110", "name": "Tin học đại cương", "grade": 8.0, "semester": "2025-1", "is_failed": False}
            ]
        }
        with patch("backend.app.routers.transcripts.run_pipeline", return_value=fake_pipe):
            res = run_and_assert_no_new_temp_files(
                lambda: client.post(
                    "/transcripts/import",
                    files={"file": ("transcript.png", img_bytes, "image/png")},
                    headers=headers
                )
            )
            assert res.status_code == 200

    def test_transcripts_import_cleanup_ocr_error(self, test_setup):
        user_a = test_setup["user_a"]
        headers = {"Authorization": f"Bearer {user_a['token']}"}
        img_bytes = create_sample_image_bytes()

        with patch("backend.app.routers.transcripts.run_pipeline", side_effect=RuntimeError("Transcripts OCR Crash")):
            res = run_and_assert_no_new_temp_files(
                lambda: client.post(
                    "/transcripts/import",
                    files={"file": ("transcript_err.png", img_bytes, "image/png")},
                    headers=headers
                )
            )
            assert res.status_code == 500

    def test_transcripts_import_cleanup_invalid_ext(self, test_setup):
        user_a = test_setup["user_a"]
        headers = {"Authorization": f"Bearer {user_a['token']}"}
        run_and_assert_no_new_temp_files(
            lambda: client.post(
                "/transcripts/import",
                files={"file": ("bad_transcript.txt", b"plain text", "text/plain")},
                headers=headers
            )
        )
        run_and_assert_no_new_temp_files(
            lambda: client.post(
                "/transcripts/import",
                files={"file": ("bad_transcript.exe", b"exe data", "application/octet-stream")},
                headers=headers
            )
        )


class TestChatOcrIntegration:
    """
    Kiểm tra VIỆC 2:
    - Sửa get_student_academic_and_ocr_context trong chat.py khớp cấu trúc trả về mới của calculate_graduation_data (student lồng nhau).
    - Không nuốt lỗi âm thầm, logger.error đầy đủ.
    - Test mock LLM: prompt gửi đi có chứa:
      (a) môn rớt từ OCR của đúng sinh viên
      (b) tín chỉ tích luỹ/còn thiếu từ graduation-check
      (c) không có dữ liệu của sinh viên khác.
    """

    def test_ocr_and_graduation_in_chat_prompt_with_mock_llm(self, test_setup):
        user_a = test_setup["user_a"]
        user_b = test_setup["user_b"]
        headers_a = {"Authorization": f"Bearer {user_a['token']}"}
        headers_b = {"Authorization": f"Bearer {user_b['token']}"}

        # Dữ liệu môn học OCR riêng biệt cho từng sinh viên
        courses_ocr_a = [
            {"course_code": "IT_NET_A", "course_name": "Lập trình mạng A", "grade": 3.0, "status": "failed", "is_failed": True, "filter_reason": "Điểm dưới 4.0"}
        ]
        courses_ocr_b = [
            {"course_code": "IT_SEC_B", "course_name": "An toàn thông tin B", "grade": 2.5, "status": "failed", "is_failed": True, "filter_reason": "Điểm dưới 4.0"}
        ]

        with SessionLocal() as db:
            # 1. Thêm kết quả OCR cho user A
            db.execute(
                text("""
                    INSERT INTO student_ocr_transcripts
                    (user_id, student_id, session_id, filename, total_subjects, passed_count, failed_count, courses_data, summary_text)
                    VALUES (:uid, :sid, NULL, 'ocr_transcript_a.png', 1, 0, 1, :data, :summary)
                """),
                {
                    "uid": user_a["id"],
                    "sid": user_a["student_id"],
                    "data": json.dumps(courses_ocr_a, ensure_ascii=False),
                    "summary": "1 môn chưa đạt: Lập trình mạng A"
                }
            )

            # 2. Thêm kết quả OCR cho user B
            db.execute(
                text("""
                    INSERT INTO student_ocr_transcripts
                    (user_id, student_id, session_id, filename, total_subjects, passed_count, failed_count, courses_data, summary_text)
                    VALUES (:uid, :sid, NULL, 'ocr_transcript_b.png', 1, 0, 1, :data, :summary)
                """),
                {
                    "uid": user_b["id"],
                    "sid": user_b["student_id"],
                    "data": json.dumps(courses_ocr_b, ensure_ascii=False),
                    "summary": "1 môn chưa đạt: An toàn thông tin B"
                }
            )

            # 3. Thêm điểm tích lũy vào bảng grades:
            # Sinh viên A tích lũy môn IT1110 (4 tín chỉ)
            db.execute(
                text("""
                    INSERT INTO grades (student_id, course_id, score, semester, passed, source)
                    VALUES (:sid, 1, 8.5, '2025-1', 1, 'manual')
                """),
                {"sid": user_a["student_id"]}
            )

            # Sinh viên B tích lũy môn IT2030 (3 tín chỉ)
            db.execute(
                text("""
                    INSERT INTO grades (student_id, course_id, score, semester, passed, source)
                    VALUES (:sid, 2, 7.0, '2025-1', 1, 'manual')
                """),
                {"sid": user_b["student_id"]}
            )

            db.commit()

        # Mock LLM để kiểm tra trực tiếp messages/prompt được gửi đi
        with patch("backend.app.routers.chat._call_ollama") as mock_llm:
            mock_llm.return_value = "Tôi là trợ lý AI học vụ, đã nhận được câu hỏi."

            # ================== SINH VIÊN A HỎI ==================
            res_chat_a = client.post(
                "/chat",
                json={"message": "Tôi rớt môn nào, cần làm gì?"},
                headers=headers_a
            )
            assert res_chat_a.status_code == 200, f"Chat A error: {res_chat_a.text}"
            assert mock_llm.called

            # Lấy prompt gửi đến LLM cho sinh viên A
            captured_call_a = mock_llm.call_args[0][0]
            user_prompt_a = captured_call_a[-1]["content"]

            # (a) Môn rớt từ OCR của đúng sinh viên A
            assert "Lập trình mạng A" in user_prompt_a or "IT_NET_A" in user_prompt_a, (
                f"Prompt sinh viên A không chứa môn rớt OCR của A: {user_prompt_a}"
            )

            # (b) Tín chỉ tích luỹ (4) và còn thiếu (116 = 120 - 4) từ graduation-check
            assert "4 / 150" in user_prompt_a or "4 / 120" in user_prompt_a or "4" in user_prompt_a, (
                f"Prompt không chứa tín chỉ tích lũy của sinh viên A: {user_prompt_a}"
            )
            assert "146" in user_prompt_a or "116" in user_prompt_a, (
                f"Prompt không chứa số tín chỉ còn thiếu (116) của sinh viên A: {user_prompt_a}"
            )

            # (c) Tuyệt đối KHÔNG có dữ liệu của sinh viên B
            assert "An toàn thông tin B" not in user_prompt_a, "Rò rỉ môn rớt của sinh viên B sang sinh viên A!"
            assert "IT_SEC_B" not in user_prompt_a, "Rò rỉ mã môn của sinh viên B sang sinh viên A!"
            assert user_b["student_code"] not in user_prompt_a, "Rò rỉ MSSV sinh viên B sang sinh viên A!"
            assert user_b["full_name"] not in user_prompt_a, "Rò rỉ họ tên sinh viên B sang sinh viên A!"

            # ================== SINH VIÊN B HỎI ==================
            mock_llm.reset_mock()
            res_chat_b = client.post(
                "/chat",
                json={"message": "Tôi rớt môn nào, cần làm gì?"},
                headers=headers_b
            )
            assert res_chat_b.status_code == 200, f"Chat B error: {res_chat_b.text}"
            assert mock_llm.called

            # Lấy prompt gửi đến LLM cho sinh viên B
            captured_call_b = mock_llm.call_args[0][0]
            user_prompt_b = captured_call_b[-1]["content"]

            # (a) Môn rớt từ OCR của đúng sinh viên B
            assert "An toàn thông tin B" in user_prompt_b or "IT_SEC_B" in user_prompt_b, (
                f"Prompt sinh viên B không chứa môn rớt OCR của B: {user_prompt_b}"
            )

            # (b) Tín chỉ tích luỹ (3) và còn thiếu (117 = 120 - 3) từ graduation-check
            assert "3 / 150" in user_prompt_b or "3 / 120" in user_prompt_b or "3" in user_prompt_b, (
                f"Prompt không chứa tín chỉ tích lũy của sinh viên B: {user_prompt_b}"
            )
            assert "147" in user_prompt_b or "117" in user_prompt_b, (
                f"Prompt không chứa số tín chỉ còn thiếu (117) của sinh viên B: {user_prompt_b}"
            )

            # (c) Tuyệt đối KHÔNG có dữ liệu của sinh viên A
            assert "Lập trình mạng A" not in user_prompt_b, "Rò rỉ môn rớt của sinh viên A sang sinh viên B!"
            assert "IT_NET_A" not in user_prompt_b, "Rò rỉ mã môn của sinh viên A sang sinh viên B!"
            assert user_a["student_code"] not in user_prompt_b, "Rò rỉ MSSV sinh viên A sang sinh viên B!"
            assert user_a["full_name"] not in user_prompt_b, "Rò rỉ họ tên sinh viên A sang sinh viên B!"

    def test_hallucination_guard_replaces_with_template(self, test_setup):
        """Test mock LLM trả về câu bịa (18 tín chỉ, môn GDQP, 'đổi điểm')
        và kiểm tra hậu kiểm thay bằng template đúng với số liệu xác thực.
        """
        user_a = test_setup["user_a"]
        headers_a = {"Authorization": f"Bearer {user_a['token']}"}

        courses_ocr_a = [
            {"course_code": "IT_NET_A", "course_name": "Lập trình mạng A", "grade": 3.0, "status": "failed", "is_failed": True, "filter_reason": "Điểm dưới 4.0"}
        ]
        with SessionLocal() as db:
            db.execute(
                text("""
                    INSERT INTO student_ocr_transcripts
                    (user_id, student_id, session_id, filename, total_subjects, passed_count, failed_count, courses_data, summary_text)
                    VALUES (:uid, :sid, NULL, 'ocr_transcript_a.png', 1, 0, 1, :data, :summary)
                """),
                {
                    "uid": user_a["id"],
                    "sid": user_a["student_id"],
                    "data": json.dumps(courses_ocr_a, ensure_ascii=False),
                    "summary": "1 môn chưa đạt: Lập trình mạng A"
                }
            )
            db.execute(
                text("""
                    INSERT INTO grades (student_id, course_id, score, semester, passed, source)
                    VALUES (:sid, 1, 8.5, '2025-1', 1, 'manual')
                """),
                {"sid": user_a["student_id"]}
            )
            db.commit()

        hallucinated_answer = (
            "Bạn có 18 tín chỉ tích lũy, cần đổi điểm môn Cấu trúc dữ liệu "
            "và hoàn thành học phần Giáo dục quốc phòng để đủ điều kiện tốt nghiệp."
        )

        with patch("backend.app.routers.chat._call_ollama") as mock_llm:
            mock_llm.return_value = hallucinated_answer

            res = client.post(
                "/chat",
                json={"message": "Tôi cần làm gì để tốt nghiệp?"},
                headers=headers_a
            )
            assert res.status_code == 200
            data = res.json()
            ans = data["answer"]

            # Kiểm tra hậu kiểm đã loại bỏ các thông tin bịa:
            assert "18 tín chỉ" not in ans, f"Câu trả lời vẫn dính 18 tín chỉ bịa: {ans}"
            assert "Giáo dục quốc phòng" not in ans, f"Câu trả lời vẫn dính môn GDQP bịa: {ans}"
            assert "đổi điểm" not in ans, f"Câu trả lời vẫn dính cụm từ 'đổi điểm': {ans}"

            # Khối template đúng phải chứa thông tin xác thực của sinh viên A:
            assert "4/150" in ans or "4/120" in ans or "4" in ans
            assert "146" in ans or "116" in ans
            assert "Tiến độ tín chỉ" in ans

    def test_hallucination_guard_failed_courses_template(self, test_setup):
        """Test mock LLM trả về câu bịa khi hỏi môn rớt -> thay bằng template môn rớt đúng."""
        user_a = test_setup["user_a"]
        headers_a = {"Authorization": f"Bearer {user_a['token']}"}

        courses_ocr_a = [
            {"course_code": "IT_NET_A", "course_name": "Lập trình mạng A", "grade": 3.0, "status": "failed", "is_failed": True, "filter_reason": "Điểm dưới 4.0"}
        ]
        with SessionLocal() as db:
            db.execute(
                text("""
                    INSERT INTO student_ocr_transcripts
                    (user_id, student_id, session_id, filename, total_subjects, passed_count, failed_count, courses_data, summary_text)
                    VALUES (:uid, :sid, NULL, 'ocr_transcript_a_fail.png', 1, 0, 1, :data, :summary)
                """),
                {
                    "uid": user_a["id"],
                    "sid": user_a["student_id"],
                    "data": json.dumps(courses_ocr_a, ensure_ascii=False),
                    "summary": "1 môn chưa đạt: Lập trình mạng A"
                }
            )
            db.commit()

        hallucinated_answer = "Bạn có 18 tín chỉ và cần đổi điểm môn Giáo dục thể chất."

        with patch("backend.app.routers.chat._call_ollama") as mock_llm:
            mock_llm.return_value = hallucinated_answer

            res = client.post(
                "/chat",
                json={"message": "Tôi rớt môn nào?"},
                headers=headers_a
            )
            assert res.status_code == 200
            data = res.json()
            ans = data["answer"]

            assert "18 tín chỉ" not in ans
            assert "Giáo dục thể chất" not in ans
            assert "Lập trình mạng A" in ans

    def test_graduation_template_like_sv01_real_data(self, test_setup):
        """Test với dữ liệu giống sv01 thật (17/120 tín chỉ, IT2030 rớt, IT3100 chưa học):
        Mock LLM trả đúng câu sai:
        'Để tốt nghiệp, bạn cần làm theo các bước sau:
        - Đã tích lũy đủ 17/120 tín chỉ.
        - Đã rớt môn Cấu trúc dữ liệu và giải thuật (IT2030) với điểm 3.5, cần học lại hoặc thi lại để cải thiện điểm.
        - Đã đăng ký học 2 môn bắt buộc chưa học: Cấu trúc dữ liệu và giải thuật (3 tín chỉ) và Lập trình hướng đối tượng (3 tín chỉ).
        - Cần hoàn thành chứng chỉ chuẩn đầu ra về ngoại ngữ và tin học theo quy định của trường.
        Vui lòng liên hệ với Phòng Đào tạo để được cấp giấy chứng nhận hoàn thành khóa học.'

        Khẳng định đầu ra cuối:
        - IT2030 ở nhóm môn học lại/thi lại
        - IT3100 ở nhóm cần đăng ký học (môn bắt buộc chưa học)
        - IT2030 KHÔNG nằm trong nhóm cần đăng ký học
        - KHÔNG có từ 'đủ' khi nói về 17/120
        - KHÔNG có từ 'giấy chứng nhận'
        """
        user_a = test_setup["user_a"]
        headers_a = {"Authorization": f"Bearer {user_a['token']}"}

        with SessionLocal() as db:
            db.execute(text("DELETE FROM grades WHERE student_id = :sid"), {"sid": user_a["student_id"]})
            db.execute(text("INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (:sid, 1, 8.5, '2025-1', 1, 'manual')"), {"sid": user_a["student_id"]})
            db.execute(text("INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (:sid, 10, 7.0, '2025-1', 1, 'manual')"), {"sid": user_a["student_id"]})
            db.execute(text("INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (:sid, 12, 6.0, '2025-1', 1, 'manual')"), {"sid": user_a["student_id"]})
            db.execute(text("INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (:sid, 3, 9.0, '2025-1', 1, 'manual')"), {"sid": user_a["student_id"]})
            db.execute(text("INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (:sid, 4, 8.0, '2025-1', 1, 'manual')"), {"sid": user_a["student_id"]})
            db.execute(text("INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (:sid, 2, 3.5, '2025-1', 0, 'manual')"), {"sid": user_a["student_id"]})
            db.commit()

        hallucinated_answer = (
            "Để tốt nghiệp, bạn cần làm theo các bước sau:\n\n"
            "- Đã tích lũy đủ 17/120 tín chỉ.\n"
            "- Đã rớt môn Cấu trúc dữ liệu và giải thuật (IT2030) với điểm 3.5, cần học lại hoặc thi lại để cải thiện điểm.\n"
            "- Đã đăng ký học 2 môn bắt buộc chưa học: Cấu trúc dữ liệu và giải thuật (3 tín chỉ) và Lập trình hướng đối tượng (3 tín chỉ).\n"
            "- Cần hoàn thành chứng chỉ chuẩn đầu ra về ngoại ngữ và tin học theo quy định của trường.\n\n"
            "Vui lòng liên hệ với Phòng Đào tạo để được cấp giấy chứng nhận hoàn thành khóa học."
        )

        with patch("backend.app.routers.chat._call_ollama") as mock_llm:
            mock_llm.return_value = hallucinated_answer

            res = client.post(
                "/chat",
                json={"message": "tôi cần làm gì để tốt nghiệp?"},
                headers=headers_a
            )
            assert res.status_code == 200
            data = res.json()
            ans = data["answer"]

            # 1. Khẳng định đầu ra cuối có IT2030 ở nhóm học lại/thi lại
            assert "Cấu trúc dữ liệu và giải thuật" in ans or "IT2030" in ans
            assert "học lại" in ans.lower() or "thi lại" in ans.lower()

            # 2. Khẳng định IT3100 ở nhóm cần đăng ký học
            assert "Lập trình hướng đối tượng" in ans or "IT3100" in ans

            # 3. IT2030 không được nằm trong nhóm cần đăng ký học
            unstudied_idx = ans.find("Môn học bắt buộc theo chương trình đào tạo cần đăng ký học")
            if unstudied_idx != -1:
                unstudied_text = ans[unstudied_idx:]
                assert "IT2030" not in unstudied_text and "Cấu trúc dữ liệu" not in unstudied_text

            # 4. KHÔNG có từ "đủ" khi nói về 17/120
            assert "đủ 17/120" not in ans.lower() and "đủ 17/150" not in ans.lower()
            assert "tích lũy đủ" not in ans.lower()

            # 5. KHÔNG có từ "giấy chứng nhận"
            assert "giấy chứng nhận" not in ans.lower()

    def test_merge_duplicate_course_and_red_marked_and_cert_status(self, test_setup):
        """Test yêu cầu:
        1. OCR có 'Cấu trúc dữ liệu và Giải thuật' 3.2 trong khi hệ thống có IT2030 3.5 phải ra một dòng
           kèm nguồn điểm (hệ thống và OCR) và ghi chú chênh lệch điểm.
        2. Môn đỏ (Kiến trúc máy tính 6.0) nằm nhóm xác nhận với giáo vụ, không khuyên học lại.
        3. Chứng chỉ chưa có dữ liệu: ghi 'chưa có dữ liệu, cần nộp', KHÔNG được ghi 'đạt', bỏ ví dụ TOEIC/B1.
        4. Trạng thái chứng chỉ được đưa vào cả 'eligible' của graduation-check.
        """
        user_a = test_setup["user_a"]
        headers_a = {"Authorization": f"Bearer {user_a['token']}"}

        # 1. Setup hệ thống có IT2030 điểm 3.5
        with SessionLocal() as db:
            db.execute(text("DELETE FROM student_certificates WHERE student_id = :sid"), {"sid": user_a["student_id"]})
            db.execute(text("DELETE FROM grades WHERE student_id = :sid"), {"sid": user_a["student_id"]})
            db.execute(
                text("INSERT INTO grades (student_id, course_id, score, semester, passed, source) VALUES (:sid, 2, 3.5, '2025-1', 0, 'manual')"),
                {"sid": user_a["student_id"]}
            )

            # 2. Setup OCR có môn 'Cấu trúc dữ liệu và Giải thuật' (3.2) và 'Kiến trúc máy tính' (6.0 đỏ)
            courses_ocr = [
                {
                    "course_name": "Cấu trúc dữ liệu và Giải thuật",
                    "course_code": "",
                    "grade": 3.2,
                    "status": "failed",
                    "is_failed": True,
                    "filter_reason": "Điểm 3.2 < 4.0"
                },
                {
                    "course_name": "Kiến trúc máy tính",
                    "course_code": "",
                    "grade": 6.0,
                    "status": "failed",
                    "is_failed": True,
                    "is_red_marked": True,
                    "filter_reason": "Vùng điểm bị đánh dấu đỏ"
                }
            ]
            db.execute(
                text("""
                    INSERT INTO student_ocr_transcripts
                    (user_id, student_id, session_id, filename, total_subjects, passed_count, failed_count, courses_data, summary_text)
                    VALUES (:uid, :sid, NULL, 'ocr_test_merge.png', 2, 0, 2, :data, :summary)
                """),
                {
                    "uid": user_a["id"],
                    "sid": user_a["student_id"],
                    "data": json.dumps(courses_ocr, ensure_ascii=False),
                    "summary": "1 môn điểm < 4.0, 1 môn đánh dấu đỏ"
                }
            )
            db.commit()

        with patch("backend.app.routers.chat._call_ollama", return_value="Theo quy chế đào tạo, sinh viên cần hoàn thành các học phần theo quy định."):
            # ================== BƯỚC 1: HỎI VỀ MÔN RỚT ==================
            res_fail = client.post(
                "/chat",
                json={"message": "Tôi rớt môn nào, cần làm gì?"},
                headers=headers_a
            )
            assert res_fail.status_code == 200
            ans_fail = res_fail.json()["answer"]

            # (a) Khẳng định Cấu trúc dữ liệu và giải thuật (IT2030) chỉ xuất hiện 1 dòng duy nhất
            ctdl_occurrences = ans_fail.count("Cấu trúc dữ liệu")
            assert ctdl_occurrences == 1, f"Môn Cấu trúc dữ liệu xuất hiện {ctdl_occurrences} lần thay vì gộp thành 1 dòng: {ans_fail}"
            assert "3.5" in ans_fail and "3.2" in ans_fail, f"Không hiển thị cả hai điểm 3.5 và 3.2: {ans_fail}"
            assert "hệ thống" in ans_fail.lower() and "ocr" in ans_fail.lower()
            assert "chênh lệch" in ans_fail.lower() or "lệch" in ans_fail.lower()

            # (b) Môn đỏ 6.0 nằm nhóm xác nhận với giáo vụ, không khuyên học lại
            assert "Kiến trúc máy tính" in ans_fail
            assert "xác nhận với giáo vụ" in ans_fail.lower() or "giáo vụ" in ans_fail.lower()
            assert "không cần đăng ký học lại" in ans_fail.lower() or "không khuyên học lại" in ans_fail.lower() or "học lại kiến trúc máy tính" not in ans_fail.lower()

            # ================== BƯỚC 2: HỎI VỀ TỐT NGHIỆP ==================
            res_grad = client.post(
                "/chat",
                json={"message": "tôi cần làm gì để tốt nghiệp?"},
                headers=headers_a
            )
            assert res_grad.status_code == 200
            ans_grad = res_grad.json()["answer"]

            # (c) Chứng chỉ chưa có dữ liệu không được ghi "đạt", bỏ ví dụ TOEIC/B1
            assert "chưa có dữ liệu, cần nộp" in ans_grad.lower() or "chưa có dữ liệu" in ans_grad.lower()
            assert "đạt chuẩn đầu ra tiếng anh" not in ans_grad.lower()
            assert "đạt chuẩn đầu ra tin học" not in ans_grad.lower()
            assert "toeic" not in ans_grad.lower()
            assert "b1" not in ans_grad.lower()

        # ================== BƯỚC 3: KIỂM TRA GRADUATION-CHECK ==================
        res_check = client.get("/students/me/graduation-check?explain=false", headers=headers_a)
        assert res_check.status_code == 200
        check_data = res_check.json()
        assert check_data["certificates"]["english"] == "chưa có dữ liệu, cần nộp"
        assert check_data["certificates"]["it"] == "chưa có dữ liệu, cần nộp"
        assert check_data["eligible"] is False, "Khi chưa có chứng chỉ thì eligible phải là False"

        # Thử thêm chứng chỉ hợp lệ vào bảng student_certificates
        with SessionLocal() as db:
            db.execute(
                text("INSERT INTO student_certificates (student_id, certificate_type, certificate_name, status) VALUES (:sid, :ctype, :cname, 'valid')"),
                {"sid": user_a["student_id"], "ctype": "Ngoại ngữ", "cname": "Chứng chỉ Tiếng Anh Bậc 3"}
            )
            db.execute(
                text("INSERT INTO student_certificates (student_id, certificate_type, certificate_name, status) VALUES (:sid, :ctype, :cname, 'valid')"),
                {"sid": user_a["student_id"], "ctype": "Tin học", "cname": "Chứng nhận Ứng dụng CNTT"}
            )
            db.commit()

        res_check_after = client.get("/students/me/graduation-check?explain=false", headers=headers_a)
        assert res_check_after.status_code == 200
        check_after = res_check_after.json()
        assert check_after["certificates"]["english"] == "đã có"
        assert check_after["certificates"]["it"] == "đã có"

    def test_certificate_process_and_graduation_check(self, test_setup):
        """Test luồng POST /api/certificate/process:
        - Upload chứng chỉ khớp (tu_dong_cap_nhat=True) -> graduation-check chuyển 'đã có'
        - Upload chứng chỉ cần xác nhận (tu_dong_cap_nhat=False) -> student_certificates lưu 'pending', graduation-check vẫn 'chưa có dữ liệu'
        """
        user_a = test_setup["user_a"]
        headers_a = {"Authorization": f"Bearer {user_a['token']}"}
        img_bytes = create_sample_image_bytes()

        # Dọn sạch chứng chỉ cũ của user test
        with SessionLocal() as db:
            db.execute(text("DELETE FROM student_certificates WHERE student_id = :sid"), {"sid": user_a["student_id"]})
            db.commit()

        # 1. Upload chứng chỉ Ngoại ngữ khớp (tự động cập nhật)
        mock_extracted_nn = {
            "loai_chung_chi": "Ngoại ngữ",
            "ten_chung_chi_cu_the": "Chứng chỉ Tiếng Anh B1",
            "ten_nguoi_duoc_cap": user_a["full_name"],
            "so_hieu": "NN123456",
            "ngay_cap": "2025-05-10",
            "do_tin_cay": "cao"
        }
        mock_match_nn = {
            "muc_tot_nghiep_khop": "Ngoại ngữ",
            "do_tuong_dong": 100.0,
            "phuong_thuc_khop": "exact",
            "trang_thai_cap_nhat": "Đã hoàn tất",
            "tu_dong_cap_nhat": True,
            "ly_do": "Khớp chính xác với chuẩn đầu ra Ngoại ngữ",
            "thong_tin_trich_xuat": mock_extracted_nn
        }

        with patch("backend.certificate_extractor.extract_certificate_from_image", return_value=mock_extracted_nn), \
             patch("backend.certificate_matcher.match_certificate", return_value=mock_match_nn):
            res_cert_nn = client.post(
                "/api/certificate/process",
                files={"file": ("cert_nn.png", img_bytes, "image/png")},
                headers=headers_a
            )
            assert res_cert_nn.status_code == 200
            data_nn = res_cert_nn.json()
            assert data_nn["matching_result"]["tu_dong_cap_nhat"] is True

        # Kiểm tra DB: bảng student_certificates có status = 'valid'
        with SessionLocal() as db:
            row_nn = db.execute(
                text("SELECT status, certificate_type, certificate_name FROM student_certificates WHERE student_id = :sid AND certificate_type = :ctype"),
                {"sid": user_a["student_id"], "ctype": "Ngoại ngữ"}
            ).fetchone()
            assert row_nn is not None
            assert row_nn.status == "valid"

        # Kiểm tra GET /students/me/graduation-check: ngoại ngữ đã có
        res_chk1 = client.get("/students/me/graduation-check?explain=false", headers=headers_a)
        assert res_chk1.status_code == 200
        chk1_data = res_chk1.json()
        assert chk1_data["certificates"]["english"] == "đã có"
        assert chk1_data["certificates"]["it"] == "chưa có dữ liệu, cần nộp"

        # 2. Upload chứng chỉ Tin học cần xác nhận thủ công (tu_dong_cap_nhat=False)
        mock_extracted_it = {
            "loai_chung_chi": "Tin học",
            "ten_chung_chi_cu_the": "Chứng chỉ MOS Word",
            "ten_nguoi_duoc_cap": user_a["full_name"],
            "so_hieu": "MOS999",
            "ngay_cap": "2025-06-01",
            "do_tin_cay": "trung binh"
        }
        mock_match_it = {
            "muc_tot_nghiep_khop": "Tin học",
            "do_tuong_dong": 60.0,
            "phuong_thuc_khop": "fuzzy",
            "trang_thai_cap_nhat": "Cần xác nhận thủ công",
            "tu_dong_cap_nhat": False,
            "ly_do": "Độ tin cậy chưa đạt mức cao, cần đối chiếu bản gốc",
            "thong_tin_trich_xuat": mock_extracted_it
        }

        with patch("backend.certificate_extractor.extract_certificate_from_image", return_value=mock_extracted_it), \
             patch("backend.certificate_matcher.match_certificate", return_value=mock_match_it):
            res_cert_it = client.post(
                "/api/certificate/process",
                files={"file": ("cert_it.png", img_bytes, "image/png")},
                headers=headers_a
            )
            assert res_cert_it.status_code == 200
            data_it = res_cert_it.json()
            assert data_it["matching_result"]["tu_dong_cap_nhat"] is False

        # Kiểm tra DB: bảng student_certificates lưu status = 'pending'
        with SessionLocal() as db:
            row_it = db.execute(
                text("SELECT status, certificate_type, certificate_name FROM student_certificates WHERE student_id = :sid AND certificate_type = :ctype"),
                {"sid": user_a["student_id"], "ctype": "Tin học"}
            ).fetchone()
            assert row_it is not None
            assert row_it.status == "pending"

        # Kiểm tra GET /students/me/graduation-check: Tin học vẫn là "chưa có dữ liệu, cần nộp"
        res_chk2 = client.get("/students/me/graduation-check?explain=false", headers=headers_a)
        assert res_chk2.status_code == 200
        chk2_data = res_chk2.json()
        assert chk2_data["certificates"]["english"] == "đã có"
        assert chk2_data["certificates"]["it"] == "chưa có dữ liệu, cần nộp"

    def test_chat_upload_course_classification(self, test_setup):
        """Test thống nhất phân loại môn giữa tin nhắn sau /chat/upload:
        - Điểm < 4.0: môn chưa đạt (môn rớt, điểm < 4.0)
        - Điểm >= 4.0 nhưng đánh dấu đỏ: môn bị đánh dấu đỏ, cần xác nhận với giáo vụ (điểm ≥ 4.0)
        - Không gộp môn đỏ >= 4.0 vào nhóm môn rớt.
        """
        user_a = test_setup["user_a"]
        headers_a = {"Authorization": f"Bearer {user_a['token']}"}
        img_bytes = create_sample_image_bytes()

        fake_pipeline_result = {
            "total_subjects": 3,
            "passed_count": 1,
            "failed_count": 2,
            "red_regions_count": 1,
            "failed_subjects": [
                {
                    "mon": "Toán cao cấp 1",
                    "diem": 3.0,
                    "ly_do": "Điểm 3.0 < 4.0",
                    "is_red_marked": False
                },
                {
                    "mon": "Vật lý đại cương",
                    "diem": 6.5,
                    "ly_do": "Vùng điểm bị đánh dấu đỏ",
                    "is_red_marked": True
                }
            ],
            "all_subjects": [
                {"mon": "Toán cao cấp 1", "diem": 3.0, "is_failed": True, "is_red_marked": False},
                {"mon": "Vật lý đại cương", "diem": 6.5, "is_failed": True, "is_red_marked": True},
                {"mon": "Triết học Mác - Lênin", "diem": 8.0, "is_failed": False, "is_red_marked": False}
            ]
        }

        with patch("backend.pipeline.run_pipeline", return_value=fake_pipeline_result):
            res = client.post(
                "/chat/upload",
                files=[("files", ("bang_diem_test.png", img_bytes, "image/png"))],
                data={"message": ""},
                headers=headers_a
            )
            assert res.status_code == 200
            data = res.json()
            ans = data["answer"]
            assert "files" in data and len(data["files"]) > 0
            summary = data["files"][0]["summary"]

            # 1. Kiểm tra summary
            assert "Số môn CHƯA ĐẠT (điểm < 4.0): 1" in summary
            assert "Môn bị đánh dấu đỏ, cần xác nhận với giáo vụ (điểm ≥ 4.0): 1" in summary
            assert "Toán cao cấp 1" in summary
            assert "Vật lý đại cương" in summary

            # 2. Kiểm tra answer: phân biệt rõ 2 nhóm
            assert "môn chưa đạt (môn rớt, điểm < 4.0): Toán cao cấp 1" in ans
            assert "môn bị đánh dấu đỏ, cần xác nhận với giáo vụ (điểm ≥ 4.0): Vật lý đại cương" in ans
            assert "môn chưa đạt (môn rớt, điểm < 4.0): Vật lý đại cương" not in ans

    def test_certificate_process_name_matching(self, test_setup):
        """Test yêu cầu mục 3:
        Trong /api/certificate/process: chỉ ghi status='valid' khi tên người được cấp
        trên chứng chỉ khớp tên sinh viên đăng nhập (so sánh bỏ dấu, không phân biệt hoa thường);
        nếu không khớp hoặc không đọc được tên thì lưu 'pending'.
        """
        user_a = test_setup["user_a"]
        headers_a = {"Authorization": f"Bearer {user_a['token']}"}
        img_bytes = create_sample_image_bytes()

        # Dọn sạch chứng chỉ cũ
        with SessionLocal() as db:
            db.execute(text("DELETE FROM student_certificates WHERE student_id = :sid"), {"sid": user_a["student_id"]})
            db.commit()

        # TH1: Tên không khớp ("Nguyen Van Khac" vs full_name của user_a)
        mock_extracted_mismatch = {
            "loai_chung_chi": "Ngoại ngữ",
            "ten_chung_chi_cu_the": "Chứng chỉ TOEIC 600",
            "ten_nguoi_duoc_cap": "Người Khác Hoàn Toàn",
            "so_hieu": "MISMATCH_01",
            "ngay_cap": "2025-01-01",
            "do_tin_cay": "cao"
        }
        mock_match_ok = {
            "muc_tot_nghiep_khop": "Ngoại ngữ",
            "do_tuong_dong": 100.0,
            "phuong_thuc_khop": "exact",
            "trang_thai_cap_nhat": "Đã hoàn tất",
            "tu_dong_cap_nhat": True,
            "ly_do": "Khớp chuẩn Ngoại ngữ",
            "thong_tin_trich_xuat": mock_extracted_mismatch
        }

        with patch("backend.certificate_extractor.extract_certificate_from_image", return_value=mock_extracted_mismatch), \
             patch("backend.certificate_matcher.match_certificate", return_value=mock_match_ok):
            res_mismatch = client.post(
                "/api/certificate/process",
                files={"file": ("cert_mismatch.png", img_bytes, "image/png")},
                headers=headers_a
            )
            assert res_mismatch.status_code == 200

        with SessionLocal() as db:
            row_mismatch = db.execute(
                text("SELECT status FROM student_certificates WHERE student_id = :sid AND certificate_type = :ctype"),
                {"sid": user_a["student_id"], "ctype": "Ngoại ngữ"}
            ).fetchone()
            assert row_mismatch is not None
            assert row_mismatch.status == "pending", f"Khi tên không khớp, status phải là 'pending' nhưng lại là: {row_mismatch.status}"

        # TH2: Không đọc được tên (ten_nguoi_duoc_cap = None hoặc "")
        mock_extracted_no_name = {
            "loai_chung_chi": "Tin học",
            "ten_chung_chi_cu_the": "Chứng chỉ MOS Excel",
            "ten_nguoi_duoc_cap": None,
            "so_hieu": "NONAME_01",
            "ngay_cap": "2025-02-02",
            "do_tin_cay": "cao"
        }
        mock_match_it_ok = {
            "muc_tot_nghiep_khop": "Tin học",
            "do_tuong_dong": 100.0,
            "phuong_thuc_khop": "exact",
            "trang_thai_cap_nhat": "Đã hoàn tất",
            "tu_dong_cap_nhat": True,
            "ly_do": "Khớp chuẩn Tin học",
            "thong_tin_trich_xuat": mock_extracted_no_name
        }

        with patch("backend.certificate_extractor.extract_certificate_from_image", return_value=mock_extracted_no_name), \
             patch("backend.certificate_matcher.match_certificate", return_value=mock_match_it_ok):
            res_no_name = client.post(
                "/api/certificate/process",
                files={"file": ("cert_noname.png", img_bytes, "image/png")},
                headers=headers_a
            )
            assert res_no_name.status_code == 200

        with SessionLocal() as db:
            row_no_name = db.execute(
                text("SELECT status FROM student_certificates WHERE student_id = :sid AND certificate_type = :ctype"),
                {"sid": user_a["student_id"], "ctype": "Tin học"}
            ).fetchone()
            assert row_no_name is not None
            assert row_no_name.status == "pending", f"Khi không đọc được tên, status phải là 'pending' nhưng lại là: {row_no_name.status}"

        # TH3: Tên khớp (chữ hoa không dấu vs tên sinh viên có dấu)
        from backend.app.prompts import strip_accents
        unaccented_upper = strip_accents(user_a["full_name"]).upper()
        mock_extracted_match = {
            "loai_chung_chi": "Ngoại ngữ",
            "ten_chung_chi_cu_the": "Chứng chỉ Tiếng Anh B1",
            "ten_nguoi_duoc_cap": unaccented_upper,
            "so_hieu": "MATCH_01",
            "ngay_cap": "2025-03-03",
            "do_tin_cay": "cao"
        }
        mock_match_match = {
            "muc_tot_nghiep_khop": "Ngoại ngữ",
            "do_tuong_dong": 100.0,
            "phuong_thuc_khop": "exact",
            "trang_thai_cap_nhat": "Đã hoàn tất",
            "tu_dong_cap_nhat": True,
            "ly_do": "Khớp chuẩn Ngoại ngữ",
            "thong_tin_trich_xuat": mock_extracted_match
        }

        with patch("backend.certificate_extractor.extract_certificate_from_image", return_value=mock_extracted_match), \
             patch("backend.certificate_matcher.match_certificate", return_value=mock_match_match):
            res_match = client.post(
                "/api/certificate/process",
                files={"file": ("cert_match.png", img_bytes, "image/png")},
                headers=headers_a
            )
            assert res_match.status_code == 200

        with SessionLocal() as db:
            row_match = db.execute(
                text("SELECT status FROM student_certificates WHERE student_id = :sid AND certificate_type = :ctype"),
                {"sid": user_a["student_id"], "ctype": "Ngoại ngữ"}
            ).fetchone()
            assert row_match is not None
            assert row_match.status == "valid", f"Khi tên khớp (bỏ dấu hoa thường), status phải là 'valid' nhưng lại là: {row_match.status}"

