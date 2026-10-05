import pytest
from unittest.mock import patch, MagicMock
from PIL import Image
from backend.pdf_processor import (
    has_text_layer,
    convert_pdf_to_images,
    extract_grades_from_pdf_text_layer
)

@patch("backend.pdf_processor.pdfplumber.open")
def test_has_text_layer_true(mock_pdfplumber_open):
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    # Provide enough characters to pass the >30 min_chars check
    mock_page.extract_text.return_value = "This is a dummy text layer with enough characters to pass the threshold."
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    assert has_text_layer("dummy.pdf", min_chars=30) is True


@patch("backend.pdf_processor.pdfplumber.open")
def test_has_text_layer_false_due_to_few_chars(mock_pdfplumber_open):
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    # Not enough characters
    mock_page.extract_text.return_value = "Too short"
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    assert has_text_layer("dummy.pdf", min_chars=30) is False


@patch("backend.pdf_processor.pdfplumber.open")
def test_has_text_layer_exception(mock_pdfplumber_open):
    mock_pdfplumber_open.side_effect = Exception("Corrupt PDF")
    # Should handle exception and return False safely
    assert has_text_layer("dummy.pdf") is False


@patch("pdf2image.convert_from_path")
def test_convert_pdf_to_images_pdf2image(mock_convert):
    mock_img = Image.new("RGB", (100, 100))
    mock_convert.return_value = [mock_img, mock_img]
    
    images = convert_pdf_to_images("dummy.pdf")
    assert len(images) == 2
    mock_convert.assert_called_once_with("dummy.pdf", dpi=200)


@patch("pdf2image.convert_from_path")
@patch("pypdfium2.PdfDocument")
def test_convert_pdf_to_images_fallback_pypdfium2(mock_pdfium, mock_convert):
    # Make pdf2image fail
    mock_convert.side_effect = Exception("Poppler missing")
    
    # Mock pypdfium2
    mock_pdf = MagicMock()
    mock_pdf.__len__.return_value = 1
    mock_page = MagicMock()
    mock_bitmap = MagicMock()
    mock_img = Image.new("RGB", (100, 100))
    mock_bitmap.to_pil.return_value = mock_img
    mock_page.render.return_value = mock_bitmap
    mock_pdf.__getitem__.return_value = mock_page
    mock_pdfium.return_value = mock_pdf

    images = convert_pdf_to_images("dummy.pdf")
    assert len(images) == 1
    assert images[0] == mock_img
    mock_pdfium.assert_called_once_with("dummy.pdf")


@patch("backend.pdf_processor.convert_pdf_to_images")
@patch("backend.pdf_processor.pdfplumber.open")
def test_extract_grades_from_pdf_text_layer_tables(mock_pdfplumber_open, mock_convert):
    mock_img = Image.new("RGB", (100, 100))
    mock_convert.return_value = [mock_img]

    mock_pdf = MagicMock()
    mock_page = MagicMock()
    
    # Mock table extraction
    mock_page.extract_tables.return_value = [
        [
            ["STT", "Tên môn học", "Số tín chỉ", "Điểm tổng kết"],
            ["1", "Toán rời rạc", "3", "8.5"],
            ["2", "Lập trình web", "3", "3.0"]
        ]
    ]
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    subjects, images = extract_grades_from_pdf_text_layer("dummy.pdf")
    
    assert len(images) == 1
    assert len(subjects) == 2
    assert subjects[0]["mon"] == "Toán rời rạc"
    assert subjects[0]["diem"] == 8.5
    assert subjects[1]["mon"] == "Lập trình web"
    assert subjects[1]["diem"] == 3.0


@patch("backend.pdf_processor.convert_pdf_to_images")
@patch("backend.pdf_processor.pdfplumber.open")
def test_extract_grades_from_pdf_text_layer_text_lines(mock_pdfplumber_open, mock_convert):
    mock_convert.return_value = []
    
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    
    # No tables
    mock_page.extract_tables.return_value = []
    # Text lines fallback
    mock_page.extract_text.return_value = "Toán cao cấp 1:3.5\nGiải tích 1    7.0\nInvalid Line No Grade"
    
    mock_pdf.pages = [mock_page]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf

    subjects, images = extract_grades_from_pdf_text_layer("dummy.pdf")
    
    assert len(subjects) == 2
    assert subjects[0]["mon"] == "Toán cao cấp 1"
    assert subjects[0]["diem"] == 3.5
    assert subjects[1]["mon"] == "Giải tích 1"
    assert subjects[1]["diem"] == 7.0

