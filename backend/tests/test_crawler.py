import pytest
from backend.app.services.crawler import is_garbage_text

def test_is_garbage_text_cid():
    text = "B(cid:189) GIÁO D(cid:201)(cid:23)" * 20
    is_garbage, reason = is_garbage_text(text)
    assert is_garbage == True
    assert "Too many (cid:" in reason

def test_is_garbage_text_no_vietnamese():
    text = "This is a completely English text that has no Vietnamese characters at all. " * 10
    is_garbage, reason = is_garbage_text(text)
    assert is_garbage == True
    assert "Almost no valid Vietnamese characters" in reason

def test_is_garbage_text_valid_vietnamese():
    text = "Trường Đại học Lạc Hồng là cơ sở giáo dục đại học đào tạo nguồn nhân lực chất lượng cao. Sinh viên cần đáp ứng các điều kiện và quy chế nghiêm ngặt để tốt nghiệp đúng hạn." * 5
    is_garbage, reason = is_garbage_text(text)
    assert is_garbage == False
    assert reason == "Valid"

def test_is_garbage_text_mojibake():
    text = "B½ GIÁO DÉ )Z rZ\" 'ŠO '%{Á!rŠI H±C LŠC H·NG NIÊN GIÁM r°a ch®: S¶ 10 Hux=7 )q= !67¬, P. BÒu Long" * 10
    is_garbage, reason = is_garbage_text(text)
    assert is_garbage == True
    assert "Too few meaningful words" in reason or "Almost no valid Vietnamese" in reason
