import os
import json
import csv
import pytest
from backend.grade_filter import (
    evaluate_subject,
    filter_grades,
    export_to_json,
    export_to_csv
)


def test_evaluate_subject_grade_under_4():
    # Điểm 3.9 -> Không đạt
    res = evaluate_subject({"mon": "Toán rời rạc", "diem": 3.9})
    assert res["is_failed"] is True
    assert "Điểm < 4.0" in res["ly_do"]


def test_evaluate_subject_grade_passed():
    # Điểm 4.0 -> Đạt
    res = evaluate_subject({"mon": "Nhập môn lập trình", "diem": 4.0})
    assert res["is_failed"] is False
    assert res["trang_thai"] == "Đạt"


def test_evaluate_subject_marked_red_does_not_fail_if_high_grade():
    # Điểm 8.0 có dấu đỏ -> Vẫn ĐẠT (theo yêu cầu người dùng: chỉ điểm < 4 mới bị đánh không đạt)
    red_regions = [(100, 100, 80, 30)]
    subject = {
        "mon": "Lập trình Web",
        "diem": 8.0,
        "bbox": (105, 105, 175, 125)
    }
    res = evaluate_subject(subject, red_regions)
    assert res["is_failed"] is False
    assert res["trang_thai"] == "Đạt"


def test_filter_grades_combined():
    subjects = [
        {"mon": "Toán A1", "diem": 3.5},                     # rớt do điểm < 4
        {"mon": "Vật lý", "diem": 6.0},                      # đậu
        {"mon": "Hóa đại cương", "diem": 2.0, "is_marked_red": True}, # rớt do điểm < 4
        {"mon": "Tiếng Anh 1", "diem": 7.5, "is_marked_red": True},  # đậu vì điểm >= 4
    ]
    failed, all_eval = filter_grades(subjects)
    assert len(failed) == 2
    assert len(all_eval) == 4

    failed_names = [f["mon"] for f in failed]
    assert "Toán A1" in failed_names
    assert "Hóa đại cương" in failed_names
    assert "Tiếng Anh 1" not in failed_names
    assert "Vật lý" not in failed_names


def test_export_json_and_csv(tmp_path):
    sample_data = [
        {"mon": "Cấu trúc dữ liệu & Giải thuật", "diem": 3.2, "trang_thai": "Không đạt", "ly_do": "Điểm < 4.0"},
        {"mon": "Hệ điều hành", "diem": 5.0, "trang_thai": "Không đạt", "ly_do": "Được đánh dấu màu đỏ"}
    ]
    json_file = str(tmp_path / "test_failed.json")
    csv_file = str(tmp_path / "test_failed.csv")

    export_to_json(sample_data, json_file)
    export_to_csv(sample_data, csv_file)

    assert os.path.exists(json_file)
    assert os.path.exists(csv_file)

    # Đọc lại JSON kiểm tra tiếng Việt
    with open(json_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
        assert len(loaded) == 2
        assert loaded[0]["mon"] == "Cấu trúc dữ liệu & Giải thuật"

    # Đọc lại CSV kiểm tra encoding UTF-8-SIG
    with open(csv_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["Môn học"] == "Cấu trúc dữ liệu & Giải thuật"
