import numpy as np
import cv2
import pytest
from backend.red_detector import (
    detect_red_regions,
    is_marked_red,
    normalize_bbox
)


def create_synthetic_image_with_red():
    """Tạo ảnh nhân tạo trắng 400x400 có 1 hộp đỏ và 1 hộp xanh dương."""
    img = np.ones((400, 400, 3), dtype=np.uint8) * 255
    # Vẽ hộp màu đỏ thuần (BGR: 0, 0, 255) tại tọa độ x=50, y=50, w=100, h=40
    cv2.rectangle(img, (50, 50), (150, 90), (0, 0, 255), -1)
    # Vẽ hộp màu xanh dương (BGR: 255, 0, 0) tại x=200, y=200, w=100, h=40
    cv2.rectangle(img, (200, 200), (300, 240), (255, 0, 0), -1)
    return img


def test_detect_red_regions():
    img = create_synthetic_image_with_red()
    red_boxes = detect_red_regions(img, min_area=50)

    assert len(red_boxes) >= 1
    # Kiểm tra vùng đỏ đầu tiên nằm quanh (50, 50, 100, 40)
    rx, ry, rw, rh = red_boxes[0]
    assert abs(rx - 50) <= 5
    assert abs(ry - 50) <= 5
    assert abs(rw - 100) <= 5
    assert abs(rh - 40) <= 5


def test_is_marked_red_overlap():
    red_regions = [(50, 50, 100, 40)]  # x1=50, y1=50, x2=150, y2=90

    # Case 1: Text box giao thoa trực tiếp với vùng đỏ
    overlap_box = (60, 55, 140, 85)
    assert is_marked_red(overlap_box, red_regions) is True

    # Case 2: Text box ở xa, không giao thoa
    distant_box = (200, 200, 300, 240)
    assert is_marked_red(distant_box, red_regions) is False

    # Case 3: Nét gạch chân màu đỏ ngay dưới đáy dòng chữ
    # Text box ở (50, 30, 150, 48), vùng đỏ ở y=50 (cách đáy 2px)
    text_above_underline = (50, 25, 150, 48)
    assert is_marked_red(text_above_underline, red_regions, tolerance=10) is True


def test_normalize_bbox():
    # Dict dạng x, y, w, h
    assert normalize_bbox({"x": 10, "y": 20, "w": 100, "h": 50}) == (10, 20, 110, 70)
    # Dict dạng pdfplumber x0, top, x1, bottom
    assert normalize_bbox({"x0": 10, "top": 20, "x1": 110, "bottom": 70}) == (10, 20, 110, 70)
    # Tọa độ trực tiếp x1, y1, x2, y2
    assert normalize_bbox((10, 20, 110, 70)) == (10, 20, 110, 70)
    assert normalize_bbox(None) is None
