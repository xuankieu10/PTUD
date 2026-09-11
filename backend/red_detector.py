"""
Module nhận diện vùng màu đỏ (khoanh tròn, gạch chân, chữ đỏ) trên ảnh bảng điểm bằng OpenCV.
Sử dụng không gian màu HSV để phân đoạn ngưỡng đỏ và xác định bounding box các vùng đánh dấu.
"""

import logging
from typing import List, Tuple, Union, Optional, Dict, Any
import numpy as np
import cv2
from PIL import Image

logger = logging.getLogger(__name__)


def load_image(image_input: Union[str, np.ndarray, Image.Image]) -> np.ndarray:
    """
    Chuẩn hóa ảnh đầu vào về dạng BGR numpy array (OpenCV format).
    """
    if isinstance(image_input, str):
        img = cv2.imread(image_input)
        if img is None:
            raise FileNotFoundError(f"Không thể đọc file ảnh: {image_input}")
        return img
    elif isinstance(image_input, Image.Image):
        # Chuyển PIL Image sang OpenCV BGR
        rgb = np.array(image_input.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    elif isinstance(image_input, np.ndarray):
        return image_input.copy()
    else:
        raise ValueError(f"Định dạng ảnh không được hỗ trợ: {type(image_input)}")


def detect_red_regions(
    image_input: Union[str, np.ndarray, Image.Image],
    min_area: int = 40,
    max_area: Optional[int] = None
) -> List[Tuple[int, int, int, int]]:
    """
    Phát hiện các vùng màu đỏ trong ảnh bằng OpenCV trong không gian màu HSV.
    
    Args:
        image_input: Đường dẫn ảnh, mảng numpy BGR, hoặc PIL Image.
        min_area: Diện tích tối thiểu của contour để loại bỏ nhiễu hạt (pixel).
        max_area: Diện tích tối đa (nếu cần giới hạn).
        
    Returns:
        Danh sách các bounding box dạng (x, y, w, h) của các vùng màu đỏ phát hiện được.
    """
    img = load_image(image_input)
    h, w = img.shape[:2]
    if max_area is None:
        max_area = int(h * w * 0.95)

    # 1. Chuyển đổi sang không gian màu HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 2. Ngưỡng màu đỏ trong HSV (màu đỏ nằm ở 2 đầu dải Hue: 0-10 và 165-180)
    # Kết hợp kiểm tra kênh Red vượt trội (Red Dominance):
    # - R phải đủ sáng (R >= 135)
    # - R vượt trội rõ rệt so với G và B ít nhất 50 đơn vị để loại trừ triệt để viền chữ xám/đen (antialiasing)
    lower_red1 = np.array([0, 70, 80])
    upper_red1 = np.array([12, 255, 255])
    
    lower_red2 = np.array([165, 70, 80])
    upper_red2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    hsv_mask = cv2.bitwise_or(mask1, mask2)

    # Lọc kiểm tra độ nổi trội thực sự của màu đỏ trong không gian BGR
    b, g, r = cv2.split(img)
    color_dominance = (r >= 135) & (r.astype(int) - g.astype(int) > 50) & (r.astype(int) - b.astype(int) > 50)
    red_mask = cv2.bitwise_and(hsv_mask, hsv_mask, mask=color_dominance.astype(np.uint8) * 255)

    # 3. Phép biến đổi hình thái học (Morphological Operations)
    # Bước 3a: Mở (OPEN) với kernel 2x2 để triệt tiêu hoàn toàn nhiễu răng cưa phụ ClearType (1-2px)
    kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    mask_opened = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel_open)

    # Bước 3b: Đóng (CLOSE) với kernel 5x5 để nối liền các nét vẽ, chữ số màu đỏ
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask_closed = cv2.morphologyEx(mask_opened, cv2.MORPH_CLOSE, kernel_close)

    # 4. Tìm các đường bao (Contours)
    contours, _ = cv2.findContours(mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    red_regions: List[Tuple[int, int, int, int]] = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        x, y, bw, bh = cv2.boundingRect(cnt)
        # Bắt buộc diện tích >= min_area và kích thước thực tế >= 5px để loại bỏ hạt nhiễu
        if min_area <= area <= max_area and bw >= 5 and bh >= 5:
            red_regions.append((x, y, bw, bh))

    logger.info(f"Phát hiện {len(red_regions)} vùng màu đỏ tiềm năng trên ảnh kích thước {w}x{h}.")
    return red_regions


def normalize_bbox(bbox: Any) -> Optional[Tuple[int, int, int, int]]:
    """
    Chuẩn hóa các định dạng bounding box khác nhau về dạng tọa độ chuẩn (x1, y1, x2, y2).
    
    Hỗ trợ:
    - [x1, y1, x2, y2]
    - (x, y, w, h) khi được chỉ định
    - dict {'x0', 'top', 'x1', 'bottom'} (từ pdfplumber)
    - dict {'x', 'y', 'w', 'h'}
    - dict {'ymin', 'xmin', 'ymax', 'xmax'} (từ LLM Vision nếu có)
    """
    if bbox is None:
        return None

    if isinstance(bbox, dict):
        if "x0" in bbox and "top" in bbox:
            return (int(bbox["x0"]), int(bbox["top"]), int(bbox.get("x1", bbox["x0"])), int(bbox.get("bottom", bbox["top"])))
        if "x" in bbox and "y" in bbox:
            x, y = int(bbox["x"]), int(bbox["y"])
            w, h = int(bbox.get("w", 0)), int(bbox.get("h", 0))
            return (x, y, x + w, y + h)
        if "ymin" in bbox and "xmin" in bbox:
            return (int(bbox["xmin"]), int(bbox["ymin"]), int(bbox["xmax"]), int(bbox["ymax"]))
        return None

    if isinstance(bbox, (list, tuple)):
        if len(bbox) == 4:
            b0, b1, b2, b3 = [int(v) for v in bbox]
            if b2 < b0 or b3 < b1:
                return (b0, b1, b0 + b2, b1 + b3)
            return (b0, b1, b2, b3)
    
    return None


def is_marked_red(
    bbox: Any,
    red_regions: List[Tuple[int, int, int, int]],
    tolerance: int = 3
) -> bool:
    """
    Kiểm tra xem vùng text (bbox) có khớp hoặc bị đánh dấu bởi bất kỳ vùng màu đỏ nào không.
    So khớp dựa trên tâm tung độ (vertical center) của vùng đỏ hoặc nét gạch chân ngang.
    
    Args:
        bbox: Bounding box của dòng text / điểm số (x1, y1, x2, y2) hoặc dict.
        red_regions: Danh sách các vùng đỏ dạng (rx, ry, rw, rh).
        tolerance: Dung sai khoảng cách (pixel).
        
    Returns:
        True nếu có vùng đỏ khớp hoặc bao quanh/gạch chân text, ngược lại False.
    """
    norm_box = normalize_bbox(bbox)
    if norm_box is None or not red_regions:
        return False

    bx1, by1, bx2, by2 = norm_box
    if bx2 <= bx1 or by2 <= by1:
        return False

    for rx, ry, rw, rh in red_regions:
        rx1 = rx
        ry1 = ry
        rx2 = rx + rw
        ry2 = ry + rh
        r_cy = ry + rh / 2.0  # Tung độ tâm của vùng đỏ

        # 1. Kiểm tra phần giao theo phương ngang (X overlap)
        x_overlap = max(0, min(bx2, rx2) - max(bx1, rx1))
        if x_overlap <= 0:
            continue

        # 2. Tâm của vùng đỏ nằm trọn trong khoảng dòng chữ [by1, by2] (kèm dung sai nhỏ)
        if (by1 - tolerance) <= r_cy <= (by2 + tolerance):
            logger.debug(f"Phát hiện khớp đỏ (theo tâm dòng): text_box={norm_box}, red_box={(rx1, ry1, rx2, ry2)}")
            return True

        # 3. Giao thoa diện tích đáng kể (Intersection Over Area >= 30% diện tích vùng đỏ)
        inter_x1 = max(bx1, rx1)
        inter_y1 = max(by1, ry1)
        inter_x2 = min(bx2, rx2)
        inter_y2 = min(by2, ry2)

        if inter_x2 > inter_x1 and inter_y2 > inter_y1:
            inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
            red_area = rw * rh
            if inter_area >= red_area * 0.30:
                logger.debug(f"Phát hiện khớp đỏ (giao thoa diện tích): text_box={norm_box}, red_box={(rx1, ry1, rx2, ry2)}")
                return True

        # 4. Trường hợp nét gạch chân đỏ (Underline): Nét gạch phải có dạng thanh ngang (rộng >= 2 lần cao)
        if rw >= rh * 2.0:
            is_underneath = (by2 - 4) <= ry1 <= (by2 + tolerance)
            if is_underneath:
                logger.debug(f"Phát hiện gạch chân đỏ: text_box={norm_box}, red_box={(rx1, ry1, rx2, ry2)}")
                return True

    return False


def annotate_red_regions(
    image_input: Union[str, np.ndarray, Image.Image],
    red_regions: List[Tuple[int, int, int, int]],
    flagged_bboxes: Optional[List[Any]] = None,
    output_path: Optional[str] = None
) -> np.ndarray:
    """
    Vẽ các bounding box màu đỏ và các ô điểm không đạt lên ảnh để làm bằng chứng trực quan.
    
    Args:
        image_input: Ảnh gốc.
        red_regions: Danh sách các vùng đỏ phát hiện được (x, y, w, h).
        flagged_bboxes: Danh sách các text bbox bị đánh dấu không đạt.
        output_path: (Tùy chọn) Lưu ảnh đã vẽ ra file.
        
    Returns:
        Mảng numpy BGR của ảnh đã được chú thích.
    """
    img = load_image(image_input)

    # 1. Vẽ tất cả các vùng màu đỏ phát hiện bằng màu đỏ thắm (BGR: 0, 0, 255)
    for x, y, w, h in red_regions:
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cv2.putText(
            img,
            "RED",
            (x, max(15, y - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (0, 0, 255),
            1,
            cv2.LINE_AA
        )

    # 2. Vẽ các text bbox bị đánh dấu (môn không đạt / cảnh báo) bằng màu cam/vàng
    if flagged_bboxes:
        for bbox in flagged_bboxes:
            norm = normalize_bbox(bbox)
            if norm:
                x1, y1, x2, y2 = norm
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 165, 255), 2)

    if output_path:
        cv2.imwrite(output_path, img)
        logger.info(f"Đã lưu ảnh trực quan hóa vùng đỏ tại: {output_path}")

    return img
