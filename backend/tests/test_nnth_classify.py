import pytest
from unittest.mock import MagicMock, patch
from backend.services.nnth_sync import _classify_subject
from backend.app.routers.chat import check_and_build_center_context

# ==================== TESTS FOR _classify_subject ====================

def test_classify_english():
    assert _classify_subject("Lớp Luyện thi VSTEP B1-B2 cấp tốc") == "Ngoại ngữ"
    assert _classify_subject("Tiếng Anh giao tiếp Quốc tế TOEIC 500+") == "Ngoại ngữ"
    assert _classify_subject("IELTS General 6.5") == "Ngoại ngữ"

def test_classify_korean_japanese():
    assert _classify_subject("Khóa học Tiếng Hàn sơ cấp 1 (TOPIK I)") == "Ngoại ngữ"
    assert _classify_subject("Ôn thi JLPT N3 tiếng Nhật") == "Ngoại ngữ"
    assert _classify_subject("Luyện thi JLPT N2") == "Ngoại ngữ"

def test_classify_chinese_french_german():
    assert _classify_subject("Lớp Tiếng Trung giao tiếp HSK 3") == "Ngoại ngữ"
    assert _classify_subject("Khóa học Tiếng Pháp DELF B1") == "Ngoại ngữ"
    assert _classify_subject("Tiếng Đức cơ bản trình độ Goethe A2") == "Ngoại ngữ"

def test_classify_word_excel():
    assert _classify_subject("Kỹ năng soạn thảo văn bản Word nâng cao") == "Tin học"
    assert _classify_subject("Phân tích dữ liệu với Excel và MOS") == "Tin học"
    assert _classify_subject("Thiết kế bài giảng điện tử PowerPoint chuyên nghiệp") == "Tin học"
    assert _classify_subject("Chứng chỉ Tin học Quốc tế IC3") == "Tin học"

def test_classify_programming_language_priority():
    # Cụm từ "lập trình" được ưu tiên nhận diện là Tin học
    assert _classify_subject("Ngôn ngữ lập trình Python cơ bản đến nâng cao") == "Tin học"
    assert _classify_subject("Lập trình Java Web Spring Boot") == "Tin học"

def test_classify_user_requested_cases():
    # 1. "Excel và quản lý password" -> Tin học (chứa Excel, password không bị nhận nhầm word)
    assert _classify_subject("Excel và quản lý password") == "Tin học"
    # 2. "Lập trình Python cho người học tiếng Anh" -> Tin học (ưu tiên lập trình)
    assert _classify_subject("Lập trình Python cho người học tiếng Anh") == "Tin học"
    # 3. "Hội thảo quản trị password" -> Khác (không dính Word nhờ \b)
    assert _classify_subject("Hội thảo Quản trị password an toàn thông tin") == "Khác"

def test_classify_unknown():
    assert _classify_subject("Khóa đào tạo Kỹ năng Thuyết trình trước đám đông") == "Khác"
    assert _classify_subject("Lớp Nghiệp vụ Sư phạm và Kỹ năng mềm") == "Khác"


# ==================== TESTS FOR check_and_build_center_context ====================

@patch("backend.app.routers.chat.get_upcoming_exams")
@patch("backend.app.routers.chat.get_upcoming_schedules")
def test_check_and_build_center_context_positive(mock_schedules, mock_exams):
    mock_db = MagicMock()
    mock_schedules.return_value = [
        {
            "loai": "Ngoại ngữ",
            "ten_khoa_hoc": "Lớp Ôn thi VSTEP B1",
            "ngay_khai_giang_str": "15/12/2026",
            "lich_hoc": "Tối 2-4-6",
            "hinh_thuc": "Trực tiếp",
            "hoc_phi": "1.500.000",
            "ky_thi_du_kien": "Kỳ thi VSTEP tháng 1"
        }
    ]
    mock_exams.return_value = []

    # Câu hỏi: "lịch khai giảng vstep" -> True
    is_match, ctx, sources = check_and_build_center_context("lịch khai giảng vstep khi nào vậy ạ?", mock_db)
    assert is_match is True
    assert "Lớp Ôn thi VSTEP B1" in ctx
    assert len(sources) == 1
    assert sources[0]["document_id"] == 9999
    assert sources[0]["so_hieu"] == "NNTH"

@patch("backend.app.routers.chat.get_upcoming_exams")
@patch("backend.app.routers.chat.get_upcoming_schedules")
def test_check_and_build_center_context_negative(mock_schedules, mock_exams):
    mock_db = MagicMock()
    
    # Câu hỏi: "quy chế học lại điểm F" -> False
    is_match, ctx, sources = check_and_build_center_context("quy chế học lại điểm F", mock_db)
    assert is_match is False
    assert ctx == ""
    assert sources == []
    mock_schedules.assert_not_called()
    mock_exams.assert_not_called()

