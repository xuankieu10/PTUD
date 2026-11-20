import pytest
import json
from backend.app.services.retrieval import (
    normalize_cohort,
    filter_chunk_indices_by_metadata,
)

def test_normalize_cohort():
    assert normalize_cohort("K2021") == "2021"
    assert normalize_cohort("K21") == "2021"
    assert normalize_cohort("2021") == "2021"
    assert normalize_cohort("Khóa 22") == "2022"
    assert normalize_cohort("") == ""
    assert normalize_cohort(None) == ""


def test_metadata_filtering_verified_strict_and_null_preserved():
    """
    Yêu cầu F.9:
    1. verified=True lọc cứng: Mặc định loại bỏ chunk verified=False (VB2).
    2. metadata null KHÔNG bị loại.
    """
    chunks = [
        {"id": 1, "section": "1.1", "verified": True, "metadata": None}, # null metadata -> GIỮ
        {"id": 2, "section": "1.2", "verified": True, "metadata": json.dumps({"loai_van_ban": "quy_che", "het_hieu_luc": False})}, # GIỮ
        {"id": 3, "section": "2.1", "verified": False, "metadata": json.dumps({"loai_van_ban": "chua_kiem_chung"})}, # verified=False -> LOẠI
        {"id": 4, "section": "3.1", "verified": True, "metadata": json.dumps({"het_hieu_luc": True})}, # het_hieu_luc=True -> LOẠI
    ]

    valid_indices = filter_chunk_indices_by_metadata(chunks, allow_unverified=False)

    # Chỉ giữ chunk 1 (metadata=None) và chunk 2 (verified=True, het_hieu_luc=False)
    assert valid_indices == [0, 1]
    assert 2 not in valid_indices # Chunk VB2 bị loại
    assert 3 not in valid_indices # Chunk hết hiệu lực bị loại


def test_metadata_filtering_cohort_matching_and_ctdt_all():
    """
    Yêu cầu F.9:
    - khoa_ap_dung của CTĐT để 'all' khớp với mọi khóa sinh viên.
    - Chunks có khóa cụ thể chỉ khớp với khóa đó.
    """
    chunks = [
        # CTĐT áp dụng cho mọi khóa
        {"id": 1, "section": "CTDT", "verified": True, "metadata": json.dumps({"loai_van_ban": "ctdt", "khoa_ap_dung": ["all"]})},
        # Quy định riêng cho khóa 2021, 2022
        {"id": 2, "section": "QD_21_22", "verified": True, "metadata": json.dumps({"khoa_ap_dung": ["2021", "2022"]})},
        # Quy định riêng cho khóa 2024
        {"id": 3, "section": "QD_24", "verified": True, "metadata": json.dumps({"khoa_ap_dung": ["2024"]})},
        # Chunk chưa có metadata
        {"id": 4, "section": "NO_META", "verified": True, "metadata": None},
    ]

    # Sinh viên khóa 2021 (K21)
    res_k21 = filter_chunk_indices_by_metadata(chunks, student_cohort="K21")
    # Phải giữ chunk 1 (all), chunk 2 (2021), chunk 4 (null meta); loại chunk 3 (2024)
    assert 0 in res_k21
    assert 1 in res_k21
    assert 3 in res_k21
    assert 2 not in res_k21


def test_metadata_filtering_fallback_when_cohort_empty():
    """
    Khi lọc theo cohort bị rỗng (ví dụ sinh viên thuộc khóa chưa có quy định riêng):
    Tự động nới lỏng bỏ lọc khóa để không bị mất kết quả.
    """
    chunks = [
        {"id": 1, "section": "QD_OLD", "verified": True, "metadata": json.dumps({"khoa_ap_dung": ["2018"]})},
    ]

    # Sinh viên khóa 2025 (không khớp 2018)
    res_fallback = filter_chunk_indices_by_metadata(chunks, student_cohort="2025")
    # Fallback an toàn: giữ lại chunk
    assert res_fallback == [0]


def test_metadata_filtering_fallback_unverified_marks_flag():
    """
    Khi không có bất kỳ chunk verified=True nào, hệ thống nới lỏng sang VB2
    và đánh dấu is_unverified_fallback = True.
    """
    chunks = [
        {"id": 1, "section": "VB2_1", "verified": False, "metadata": json.dumps({"loai_van_ban": "chua_kiem_chung"})},
    ]

    res = filter_chunk_indices_by_metadata(chunks, allow_unverified=False)
    assert res == [0]
    assert chunks[0].get("is_unverified_fallback") is True
