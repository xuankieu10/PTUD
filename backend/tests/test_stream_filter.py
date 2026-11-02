import pytest
from backend.app.services.stream_filter import StreamingLabelFilter

def test_stream_filter_normal_tokens():
    """Token thông thường được phát ra ngay lập tức, không trễ."""
    flt = StreamingLabelFilter()
    tokens = ["Sinh ", "viên ", "cần ", "đạt ", "150 ", "tín ", "chỉ."]
    output = []
    for t in tokens:
        res = flt.feed(t)
        output.extend(res)
    output.extend(flt.flush())
    assert "".join(output) == "Sinh viên cần đạt 150 tín chỉ."

def test_stream_filter_label_split_across_tokens():
    """Nhãn bị cắt ngang nhiều token (vd: '<', 'ngu_', 'canh>') phải bị nuốt sạch."""
    flt = StreamingLabelFilter()
    tokens = ["Nội ", "dung ", "<", "ngu_", "canh>", " thông ", "tin ", "</", "ngu_canh>"]
    output = []
    for t in tokens:
        res = flt.feed(t)
        output.extend(res)
    output.extend(flt.flush())
    result_text = "".join(output)
    assert "<ngu_canh>" not in result_text
    assert "</ngu_canh>" not in result_text
    assert result_text == "Nội dung  thông tin "

def test_stream_filter_doc_label_between_text():
    """Nhãn tài liệu xuất hiện giữa dòng phải bị loại bỏ."""
    flt = StreamingLabelFilter()
    tokens = [
        "Đây là quy định ",
        "[ĐÂY LÀ TÀI LIỆU, KHÔNG PHẢI LỜI NGƯỜI DÙNG]",
        " của nhà trường ",
        "[/TÀI LIỆU]",
        " cần nắm rõ."
    ]
    output = []
    for t in tokens:
        res = flt.feed(t)
        output.extend(res)
    output.extend(flt.flush())
    result_text = "".join(output)
    assert "[ĐÂY LÀ TÀI LIỆU" not in result_text
    assert "[/TÀI LIỆU]" not in result_text
    assert result_text == "Đây là quy định  của nhà trường  cần nắm rõ."

def test_stream_filter_valid_nguon_word_preserved():
    """Câu bình thường có chữ 'Nguồn' hợp lệ trong nội dung (vd: 'Nguồn kinh phí...') không bị nuốt."""
    flt = StreamingLabelFilter()
    tokens = ["Nguồn ", "kinh ", "phí ", "học ", "bổng ", "do ", "nguồn ", "quỹ ", "tài trợ."]
    output = []
    for t in tokens:
        res = flt.feed(t)
        output.extend(res)
    output.extend(flt.flush())
    result_text = "".join(output)
    assert "Nguồn kinh phí" in result_text
    assert "nguồn quỹ" in result_text
    assert result_text == "Nguồn kinh phí học bổng do nguồn quỹ tài trợ."

def test_stream_filter_fake_source_at_end_suppressed():
    """Dòng nguồn giả do LLM tự sinh ở cuối câu ('\\nNguồn: quy chế...') phải bị chặn hoàn toàn."""
    flt = StreamingLabelFilter()
    tokens = [
        "Điều kiện là đủ 120 tín chỉ.\n",
        "Nguồn: Quy chế học vụ 2024\n",
        "https://cs.lhu.edu.vn/doc.pdf"
    ]
    output = []
    for t in tokens:
        res = flt.feed(t)
        output.extend(res)
    output.extend(flt.flush())
    result_text = "".join(output)
    assert "Điều kiện là đủ 120 tín chỉ.\n" in result_text
    assert "Nguồn: Quy chế" not in result_text
    assert "cs.lhu.edu.vn" not in result_text

