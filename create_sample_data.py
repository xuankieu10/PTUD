"""
Tạo dữ liệu bảng điểm mẫu (Ảnh PNG và PDF) phục vụ việc chạy thử nghiệm và kiểm thử hệ thống.
Bao gồm cả môn điểm < 4.0, môn điểm cao bình thường, và môn bị khoanh đỏ / gạch đỏ.
"""

import os
import sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def create_sample_image(output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    width, height = 900, 700
    # Nền trắng
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Thử nạp font hệ thống Windows nếu có, hoặc dùng default
    font_title = ImageFont.load_default()
    font_body = ImageFont.load_default()

    # Vẽ khung bảng
    draw.rectangle([(50, 40), (850, 620)], outline=(180, 180, 180), width=2)
    draw.rectangle([(50, 40), (850, 110)], fill=(240, 244, 248), outline=(180, 180, 180), width=1)

    # Tiêu đề
    draw.text((300, 55), "TRUONG DAI HOC - BANG DIEM HOC TAP", fill=(20, 50, 100), font=font_title)
    draw.text((330, 80), "Hoc ky 1 - Nam hoc 2025 - 2026", fill=(80, 80, 80), font=font_body)

    # Header bảng
    headers = [("STT", 60), ("Ten mon hoc", 120), ("So TC", 520), ("Diem tong ket", 620), ("Ghi chu", 740)]
    draw.rectangle([(50, 110), (850, 150)], fill=(230, 235, 242), outline=(180, 180, 180), width=1)
    for title, x in headers:
        draw.text((x, 125), title, fill=(0, 0, 0), font=font_body)

    # Dữ liệu môn học
    subjects = [
        (1, "Toan roi rac", 3, "7.5", "Dat"),
        (2, "Cau truc du lieu va Giai thuat", 4, "3.2", "Thi lai"),
        (3, "Kien truc may tinh", 3, "6.0", "Dat"),
        (4, "He quan tri Co so du lieu", 3, "5.5", "Canh bao"),
        (5, "Lap trinh Web nang cao", 3, "8.5", "Dat"),
        (6, "Triet hoc Mac - Lenin", 2, "2.0", "Hoc lai"),
    ]

    y = 150
    row_height = 50
    for idx, name, tc, diem, note in subjects:
        # Đường kẻ ngang từng dòng
        draw.line([(50, y + row_height), (850, y + row_height)], fill=(210, 210, 210), width=1)
        draw.text((65, y + 18), str(idx), fill=(0, 0, 0), font=font_body)
        draw.text((120, y + 18), name, fill=(0, 0, 0), font=font_body)
        draw.text((535, y + 18), str(tc), fill=(0, 0, 0), font=font_body)
        draw.text((645, y + 18), diem, fill=(0, 0, 0), font=font_body)
        draw.text((745, y + 18), note, fill=(60, 60, 60), font=font_body)
        y += row_height

    # Chuyển sang mảng numpy BGR để vẽ dấu đỏ bằng OpenCV
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    # 1. Dấu đỏ số 1: Khoanh tròn màu đỏ quanh điểm môn số 4 (Hệ quản trị CSDL, điểm 5.5) tại dòng y ≈ 300 - 350
    # BGR của đỏ tươi: (0, 0, 240)
    cv2.circle(cv_img, (655, 325), 24, (20, 20, 230), 3)

    # 2. Dấu đỏ số 2: Nét gạch chân màu đỏ dưới điểm môn số 6 (Triết học, điểm 2.0) tại dòng y ≈ 400 - 450
    cv2.rectangle(cv_img, (635, 435), (675, 442), (10, 10, 240), -1)

    # Lưu ảnh mẫu
    cv2.imwrite(output_path, cv_img)
    print(f"Đã tạo ảnh mẫu thành công: {output_path}")

    # Tạo thêm 1 file PDF từ ảnh này (dạng PDF scan)
    pdf_path = os.path.splitext(output_path)[0] + "_scan.pdf"
    pil_result = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
    pil_result.save(pdf_path, "PDF", resolution=150.0)
    print(f"Đã tạo PDF scan mẫu thành công: {pdf_path}")


if __name__ == "__main__":
    create_sample_image("samples/sample_transcript.png")
