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


def test_evaluate_subject_marked_red_fails():
    # Điểm 8.0 có dấu đỏ -> KHÔNG ĐẠT (theo luật ưu tiên khoanh đỏ)
    red_regions = [(100, 100, 80, 30)]
    subject = {
        "mon": "Lập trình Web",
        "diem": 8.0,
        "bbox": (105, 105, 70, 20)
    }
    res = evaluate_subject(subject, red_regions)
    assert res["is_failed"] is True
    assert res["is_red_marked"] is True
    assert "Được đánh dấu màu đỏ" in res["ly_do"]


def test_evaluate_subject_invalid_grade():
    invalid_grades = ["M", "Vắng", "", None, "8,5", " 7.0 "]
    
    # Test valid string floats
    res = evaluate_subject({"mon": "Nhập môn", "diem": "8,5"})
    assert res["diem"] == 8.5
    assert res["is_failed"] is False

    res = evaluate_subject({"mon": "Nhập môn", "diem": " 7.0 "})
    assert res["diem"] == 7.0
    assert res["is_failed"] is False

    # Test invalid values that fail parsing
    for val in ["M", "Vắng", "", None]:
        res = evaluate_subject({"mon": "Nhập môn", "diem": val})
        assert res["diem"] == 0.0
        assert res["is_failed"] is True
        assert "Điểm không xác định" in res["ly_do"]


def test_filter_grades_combined():
    red_regions = [(10, 10, 50, 50)]
    subjects = [
        {"mon": "Toán A1", "diem": 3.5},                     # rớt do điểm < 4
        {"mon": "Vật lý", "diem": 6.0},                      # đậu
        {"mon": "Hóa đại cương", "diem": 2.0, "bbox": (10, 20, 40, 50)}, # rớt do điểm < 4 và đỏ
        {"mon": "Tiếng Anh 1", "diem": 7.5, "bbox": (10, 20, 40, 50)},  # rớt vì khoanh đỏ dù điểm > 4
    ]
    failed, all_eval = filter_grades(subjects, red_regions)
    assert len(failed) == 3
    assert len(all_eval) == 4

    failed_names = [f["mon"] for f in failed]
    assert "Toán A1" in failed_names
    assert "Hóa đại cương" in failed_names
    assert "Tiếng Anh 1" in failed_names
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
