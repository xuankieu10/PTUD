import pytest
from backend.ocr_extractor import clean_and_parse_json


def test_clean_and_parse_pure_json():
    raw = '[{"mon": "Toán cao cấp", "diem": 3.5}, {"mon": "Tin học đại cương", "diem": 8.0}]'
    parsed = clean_and_parse_json(raw)
    assert len(parsed) == 2
    assert parsed[0]["mon"] == "Toán cao cấp"
    assert parsed[0]["diem"] == 3.5
    assert parsed[1]["mon"] == "Tin học đại cương"
    assert parsed[1]["diem"] == 8.0


def test_clean_and_parse_markdown_fence():
    raw = """
    Dưới đây là danh sách điểm số tôi đọc được từ ảnh:
    ```json
    [
        {"mon": "Giải tích 2", "diem": 2.5},
        {"mon": "Đại số tuyến tính", "diem": 7.0}
    ]
    ```
    Hy vọng giúp ích cho bạn!
    """
    parsed = clean_and_parse_json(raw)
    assert len(parsed) == 2
    assert parsed[0]["mon"] == "Giải tích 2"
    assert parsed[0]["diem"] == 2.5


def test_clean_and_parse_vietnamese_comma_numbers_and_synonyms():
    # Điểm có dấu phẩy '3,5' và các key đồng nghĩa 'mon_hoc', 'score'
    raw = '[{"mon_hoc": "Triết học Mác - Lênin", "score": "3,5"}, {"ten_mon": "Pháp luật đại cương", "grade": 9}]'
    parsed = clean_and_parse_json(raw)
    assert len(parsed) == 2
    assert parsed[0]["mon"] == "Triết học Mác - Lênin"
    assert parsed[0]["diem"] == 3.5
    assert parsed[1]["mon"] == "Pháp luật đại cương"
    assert parsed[1]["diem"] == 9.0


def test_clean_and_parse_single_object_with_trailing_question_mark():
    # Đúng trường hợp mô hình trả về 1 môn đơn lẻ có dấu hỏi thừa
    raw = '{ "mon": "Cấu trúc dữ liệu và giải thuật (khóa 2022)", "diem": 8.6 }?'
    parsed = clean_and_parse_json(raw)
    assert len(parsed) == 1
    assert parsed[0]["mon"] == "Cấu trúc dữ liệu và giải thuật (khóa 2022)"
    assert parsed[0]["diem"] == 8.6


def test_clean_and_parse_invalid_format_raises_error():
    # Văn bản không có cấu trúc mảng JSON
    raw = "Tôi không thể đọc được bảng điểm này vì ảnh quá mờ."
    with pytest.raises(Exception):
        clean_and_parse_json(raw)
