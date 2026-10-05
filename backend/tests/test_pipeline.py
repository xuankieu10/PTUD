import os
import pytest
from unittest.mock import patch, MagicMock
from backend.pipeline import run_pipeline
from PIL import Image

@pytest.fixture
def dummy_image(tmp_path):
    img_path = tmp_path / "dummy_image.png"
    img = Image.new("RGB", (200, 200), color="white")
    img.save(img_path)
    return str(img_path)

@patch("backend.pipeline.detect_red_regions")
@patch("backend.pipeline.extract_grades_from_image")
@patch("backend.pipeline.export_to_json")
@patch("backend.pipeline.export_to_csv")
@patch("backend.pipeline.annotate_red_regions")
def test_run_pipeline_image(
    mock_annotate, mock_csv, mock_json, mock_extract, mock_detect, dummy_image, tmp_path
):
    mock_detect.return_value = [(10, 10, 50, 50)]
    mock_extract.return_value = [
        {"mon": "Toán", "diem": 3.0, "bbox": (15, 15, 20, 20)},
        {"mon": "Lý", "diem": 8.0, "bbox": (100, 100, 20, 20)}
    ]
    
    out_dir = str(tmp_path / "output")
    result = run_pipeline(dummy_image, output_dir=out_dir)
    
    assert result["total_subjects"] == 2
    assert result["failed_count"] == 1
    assert result["passed_count"] == 1
    assert result["red_regions_count"] == 1
    
    assert mock_json.called
    assert mock_csv.called
    assert mock_annotate.called

@patch("backend.pipeline.has_text_layer")
@patch("backend.pipeline.extract_grades_from_pdf_text_layer")
@patch("backend.pipeline.detect_red_regions")
@patch("backend.pipeline.export_to_json")
@patch("backend.pipeline.export_to_csv")
@patch("backend.pipeline.annotate_red_regions")
def test_run_pipeline_pdf_text_layer(
    mock_annotate, mock_csv, mock_json, mock_detect, mock_extract_pdf, mock_has_text, tmp_path
):
    pdf_path = str(tmp_path / "dummy.pdf")
    with open(pdf_path, "w") as f:
        f.write("dummy")

    mock_has_text.return_value = True
    mock_img = Image.new("RGB", (100, 100))
    mock_extract_pdf.return_value = (
        [{"mon": "Văn", "diem": 2.0}],
        [mock_img]
    )
    mock_detect.return_value = []
    
    out_dir = str(tmp_path / "output")
    result = run_pipeline(pdf_path, output_dir=out_dir)
    
    assert result["total_subjects"] == 1
    assert result["failed_count"] == 1
    assert result["passed_count"] == 0

@patch("backend.pipeline.has_text_layer")
@patch("backend.pipeline.convert_pdf_to_images")
@patch("backend.pipeline.extract_grades_from_image")
@patch("backend.pipeline.detect_red_regions")
@patch("backend.pipeline.export_to_json")
@patch("backend.pipeline.export_to_csv")
@patch("backend.pipeline.annotate_red_regions")
def test_run_pipeline_pdf_scan(
    mock_annotate, mock_csv, mock_json, mock_detect, mock_extract, mock_convert, mock_has_text, tmp_path
):
    pdf_path = str(tmp_path / "dummy_scan.pdf")
    with open(pdf_path, "w") as f:
        f.write("dummy")

    mock_has_text.return_value = False
    mock_img = Image.new("RGB", (100, 100))
    mock_convert.return_value = [mock_img]
    mock_detect.return_value = []
    mock_extract.return_value = [{"mon": "Văn", "diem": 5.0}]
    
    out_dir = str(tmp_path / "output")
    result = run_pipeline(pdf_path, output_dir=out_dir)
    
    assert result["total_subjects"] == 1
    assert result["failed_count"] == 0
    assert result["passed_count"] == 1


