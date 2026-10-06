"""
Chương trình dòng lệnh (CLI) chạy toàn bộ pipeline đọc bảng điểm học sinh và lọc môn không đạt.

Cách dùng:
    python backend/main.py --input path/to/transcript.png
    python backend/main.py --input path/to/transcript.pdf --output-dir my_results --model llama3.2-vision
"""

import argparse
import logging
import os
import sys



# Thêm đường dẫn thư mục gốc vào sys.path để import chuẩn
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from backend.pipeline import run_pipeline
from backend.ocr_extractor import DEFAULT_VISION_MODEL, DEFAULT_OLLAMA_HOST


def setup_logging():
    """
    Cấu hình logging định dạng trực quan có timestamp và cấp độ thông báo.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def main():
    setup_logging()
    logger = logging.getLogger("GradePipelineCLI")

    parser = argparse.ArgumentParser(
        description="Pipeline đọc bảng điểm (ảnh/PDF) và lọc môn không đạt sử dụng Ollama Vision & OpenCV"
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Đường dẫn tới 1 file ảnh/PDF hoặc 1 thư mục chứa nhiều bảng điểm để test hàng loạt"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="output",
        help="Thư mục xuất kết quả JSON, CSV và ảnh annotated (mặc định: ./output)"
    )
    parser.add_argument(
        "-m", "--model",
        default=DEFAULT_VISION_MODEL,
        help=f"Tên mô hình Ollama Vision sử dụng (mặc định: {DEFAULT_VISION_MODEL})"
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_OLLAMA_HOST,
        help=f"Địa chỉ host Ollama (mặc định: {DEFAULT_OLLAMA_HOST})"
    )

    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        logger.error(f"Đường dẫn đầu vào không tồn tại: {input_path}")
        sys.exit(1)

    # Thu thập danh sách file cần xử lý
    valid_extensions = {".jpg", ".jpeg", ".png", ".pdf"}
    if os.path.isdir(input_path):
        files_to_process = [
            os.path.join(input_path, f)
            for f in sorted(os.listdir(input_path))
            if os.path.splitext(f)[1].lower() in valid_extensions
        ]
        if not files_to_process:
            logger.warning(f"Không tìm thấy file ảnh hoặc PDF nào trong thư mục: {input_path}")
            sys.exit(0)
        logger.info(f"Phát hiện thư mục với {len(files_to_process)} bảng điểm cần kiểm thử hàng loạt.")
    else:
        files_to_process = [input_path]

    try:
        for idx_file, target_file in enumerate(files_to_process, start=1):
            file_name = os.path.basename(target_file)
            print(f"\n{'='*70}")
            print(f"  [{idx_file}/{len(files_to_process)}] ĐANG XỬ LÝ BẢNG ĐIỂM: {file_name}")
            print(f"{'='*70}")

            result = run_pipeline(
                input_path=target_file,
                output_dir=args.output_dir,
                model=args.model,
                host=args.host
            )

            print("-" * 70)
            print(f"Tổng số môn: {result['total_subjects']} | ĐẠT: {result['passed_count']} | KHÔNG ĐẠT: {result['failed_count']} | Vùng đỏ: {result['red_regions_count']}")
            print("-" * 70)

            if result["failed_subjects"]:
                print(f"{'STT':<4} | {'Tên môn học':<30} | {'Điểm':<6} | {'Lý do không đạt'}")
                print("-" * 70)
                for idx, item in enumerate(result["failed_subjects"], start=1):
                    print(f"{idx:<4} | {item['mon'][:30]:<30} | {item['diem']:<6} | {item.get('ly_do', '')}")
            else:
                print("-> Tất cả các môn đều đạt (>= 4.0 và không có đánh dấu đỏ).")

            print("-" * 70)
            print(f"File JSON kết quả: {result['json_path']}")
            print(f"File CSV kết quả:  {result['csv_path']}")
            print(f"Ảnh vẽ vùng đỏ:   {result['annotated_image_path']}")
            print("=" * 70)

    except ConnectionError as conn_err:
        logger.error(f"Lỗi kết nối Ollama: {conn_err}")
        print("\n[GỢI Ý] Vui lòng đảm bảo Ollama đang chạy tại http://localhost:11434")
        print("Kiểm tra bằng lệnh: ollama list\n")
        sys.exit(2)
    except Exception as e:
        logger.exception(f"Lỗi trong quá trình thực thi pipeline: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()
