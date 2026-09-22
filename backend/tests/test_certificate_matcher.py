import pytest
from backend.certificate_matcher import match_certificate, DEFAULT_REQUIRED_CATEGORIES
from backend.certificate_extractor import clean_and_parse_certificate_json


def test_match_english_high_confidence():
    """Chứng chỉ tiếng Anh / TOEIC với độ tin cậy cao -> Tự động hoàn tất mục Ngoại ngữ."""
    extracted = {
        "loai_chung_chi": "Tiếng Anh",  # Model trả tên hơi khác
        "ten_chung_chi_cu_the": "Chứng chỉ TOEIC 650 điểm",
        "ten_nguoi_duoc_cap": "Nguyễn Văn A",
        "ngay_cap": "15/06/2024",
        "do_tin_cay": "cao"
    }
    result = match_certificate(extracted)
    assert result["muc_tot_nghiep_khop"] == "Ngoại ngữ"
    assert result["trang_thai_cap_nhat"] == "Đã hoàn tất"
    assert result["tu_dong_cap_nhat"] is True
    assert result["do_tuong_dong"] >= 70.0


def test_match_it_high_confidence():
    """Chứng chỉ MOS / Tin học với độ tin cậy cao -> Tự động hoàn tất mục Tin học."""
    extracted = {
        "loai_chung_chi": "Tin học",
        "ten_chung_chi_cu_the": "Microsoft Office Specialist (MOS) - Excel 2019",
        "ten_nguoi_duoc_cap": "Trần Thị B",
        "ngay_cap": "20/08/2023",
        "do_tin_cay": "cao"
    }
    result = match_certificate(extracted)
    assert result["muc_tot_nghiep_khop"] == "Tin học"
    assert result["trang_thai_cap_nhat"] == "Đã hoàn tất"
    assert result["tu_dong_cap_nhat"] is True


def test_match_defense_high_confidence():
    """Giấy chứng nhận GDQP -> Tự động hoàn tất mục Quốc phòng."""
    extracted = {
        "loai_chung_chi": "Quân sự",  # Model trả tên đồng nghĩa
        "ten_chung_chi_cu_the": "Giấy chứng nhận Giáo dục quốc phòng và an ninh",
        "ten_nguoi_duoc_cap": "Lê Văn C",
        "ngay_cap": "10/01/2024",
        "do_tin_cay": "cao"
    }
    result = match_certificate(extracted)
    assert result["muc_tot_nghiep_khop"] == "Quốc phòng"
    assert result["trang_thai_cap_nhat"] == "Đã hoàn tất"
    assert result["tu_dong_cap_nhat"] is True


def test_match_pe_high_confidence():
    """Giấy chứng nhận GDTC -> Tự động hoàn tất mục Thể chất."""
    extracted = {
        "loai_chung_chi": "Thể chất",
        "ten_chung_chi_cu_the": "Chứng chỉ hoàn thành môn học Giáo dục thể chất - Bơi lội",
        "ten_nguoi_duoc_cap": "Phạm Thị D",
        "ngay_cap": "05/05/2024",
        "do_tin_cay": "cao"
    }
    result = match_certificate(extracted)
    assert result["muc_tot_nghiep_khop"] == "Thể chất"
    assert result["trang_thai_cap_nhat"] == "Đã hoàn tất"
    assert result["tu_dong_cap_nhat"] is True


def test_match_low_confidence_requires_manual_review():
    """Độ tin cậy 'thap' (ảnh mờ, mất góc) -> BẮT BUỘC cần xác nhận thủ công, không tự động duyệt."""
    extracted = {
        "loai_chung_chi": "Ngoại ngữ",
        "ten_chung_chi_cu_the": "IELTS Certificate (mờ góc)",
        "ten_nguoi_duoc_cap": "Nguyễn Văn E",
        "ngay_cap": None,
        "do_tin_cay": "thap"
    }
    result = match_certificate(extracted)
    assert result["trang_thai_cap_nhat"] == "Cần xác nhận thủ công"
    assert result["tu_dong_cap_nhat"] is False
    assert "Độ tin cậy" in result["ly_do"]


def test_match_medium_confidence_requires_manual_review():
    """Độ tin cậy 'trung binh' -> Yêu cầu xác nhận thủ công để an toàn."""
    extracted = {
        "loai_chung_chi": "Tin học",
        "ten_chung_chi_cu_the": "Ứng dụng CNTT cơ bản",
        "ten_nguoi_duoc_cap": None,
        "ngay_cap": "2024",
        "do_tin_cay": "trung binh"
    }
    result = match_certificate(extracted)
    assert result["trang_thai_cap_nhat"] == "Cần xác nhận thủ công"
    assert result["tu_dong_cap_nhat"] is False


def test_match_unknown_type_requires_manual_review():
    """Loại chứng chỉ 'Không xác định' -> BẮT BUỘC cần xác nhận thủ công."""
    extracted = {
        "loai_chung_chi": "Không xác định",
        "ten_chung_chi_cu_the": "Văn bản không rõ nội dung",
        "ten_nguoi_duoc_cap": None,
        "ngay_cap": None,
        "do_tin_cay": "thap"
    }
    result = match_certificate(extracted)
    assert result["trang_thai_cap_nhat"] == "Cần xác nhận thủ công"
    assert result["tu_dong_cap_nhat"] is False


def test_match_unrelated_document_requires_manual_review():
    """Tải lên giấy phép lái xe hoặc văn bằng không nằm trong điều kiện tốt nghiệp."""
    extracted = {
        "loai_chung_chi": "Giao thông",
        "ten_chung_chi_cu_the": "Giấy phép lái xe ô tô hạng B2",
        "ten_nguoi_duoc_cap": "Võ Văn G",
        "ngay_cap": "12/12/2023",
        "do_tin_cay": "cao"
    }
    result = match_certificate(extracted)
    assert result["muc_tot_nghiep_khop"] is None
    assert result["trang_thai_cap_nhat"] == "Cần xác nhận thủ công"
    assert result["tu_dong_cap_nhat"] is False


def test_clean_and_parse_certificate_json_markdown():
    """Kiểm tra parser xử lý khối markdown code fence và chuẩn hóa trường."""
    raw = """
    Phản hồi từ AI:
    ```json
    {
      "loai_chung_chi": "Ngoại ngữ",
      "ten_chung_chi_cu_the": "Chứng chỉ VSTEP B1",
      "ten_nguoi_duoc_cap": "Đặng Thị H",
      "ngay_cap": "01/04/2024",
      "do_tin_cay": "cao"
    }
    ```
    """
    parsed = clean_and_parse_certificate_json(raw)
    assert parsed["loai_chung_chi"] == "Ngoại ngữ"
    assert parsed["ten_chung_chi_cu_the"] == "Chứng chỉ VSTEP B1"
    assert parsed["ten_nguoi_duoc_cap"] == "Đặng Thị H"
    assert parsed["do_tin_cay"] == "cao"


def test_clean_and_parse_certificate_json_invalid_raises():
    """Chuỗi không phải JSON ném lỗi để kích hoạt retry."""
    raw = "Ảnh này là ảnh selfie, không có chứng chỉ nào."
    with pytest.raises(ValueError):
        clean_and_parse_certificate_json(raw)
