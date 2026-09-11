# Pipeline Lọc Môn Không Đạt Từ Bảng Điểm (Ollama Vision + OpenCV)

Hệ thống đọc bảng điểm học sinh / sinh viên (từ file ảnh hoặc file PDF scan / text layer), trích xuất danh sách môn học và điểm số qua mô hình thị giác AI cục bộ (**Ollama Vision**), kết hợp thuật toán thị giác máy tính **OpenCV (HSV)** để phát hiện các dấu vết khoanh đỏ, gạch đỏ của giáo viên, và lọc ra các môn không đạt theo luật thuần Python.

Dự án được thiết kế chuẩn modular với **Backend FastAPI** và **Frontend React (TypeScript + Tailwind CSS)** riêng biệt, đồng thời hỗ trợ giao diện dòng lệnh **CLI**.

---

## 1. Tính năng nổi bật

- **Xử lý đa định dạng đầu vào**: Hỗ trợ ảnh (`.png`, `.jpg`, `.jpeg`) và tài liệu (`.pdf`).
- **Phân nhánh PDF thông minh**:
  - Dùng `pdfplumber` trích xuất text layer và cấu trúc bảng trực tiếp nếu có.
  - Nếu là PDF scan (không có text layer), tự động chuyển đổi các trang thành ảnh bằng `pdf2image` (kèm cơ chế dự phòng `pypdfium2` không cần cài Poppler bên ngoài trên Windows).
- **Trích xuất cục bộ qua Ollama Vision**:
  - Mặc định sử dụng mô hình thị giác local `llama3.2-vision` (hoặc `qwen2.5vl:7b`) tại `http://localhost:11434`.
  - Ép kiểu định dạng JSON chuẩn: `[{"mon": string, "diem": number}]`.
  - Bộ parser chịu lỗi cao, xử lý markdown fence và tự động **retry 1 lần** với prompt nghiêm ngặt nếu model trả sai cú pháp.
- **Phát hiện vùng màu đỏ bằng OpenCV**:
  - Chuyển đổi sang không gian màu HSV, lấy ngưỡng 2 dải màu đỏ (0-10 và 165-180).
  - Áp dụng Morphology để nối liền nét vẽ khoanh tròn hoặc gạch chân.
  - Hàm `is_marked_red(bbox, red_regions)` so khớp tọa độ dòng chữ với các vùng đỏ phát hiện được.
- **Luật lọc thuần Python**:
  - Một môn bị coi là **"Không đạt"** nếu: `điểm < 4.0` **HOẶC** `được đánh dấu màu đỏ`.
  - Không dựa vào phán đoán chủ quan của AI.
- **Xuất kết quả đa dạng**:
  - File `JSON` định dạng chuẩn.
  - File `CSV` chuẩn mã hóa `UTF-8-SIG` (mở trên Excel tiếng Việt không bị lỗi font).
  - Ảnh trực quan hóa (`annotated.png`) vẽ rõ bounding box vùng đỏ phát hiện bởi OpenCV.

---

## 2. Cấu trúc thư mục

```
PTUD/
├── backend/
│   ├── __init__.py
│   ├── ocr_extractor.py      # Gọi Ollama Vision API, cơ chế retry & parse JSON chịu lỗi
│   ├── red_detector.py       # OpenCV HSV thresholding, contour & hàm is_marked_red
│   ├── pdf_processor.py      # pdfplumber trích text layer vs pdf2image chuyển PDF scan sang ảnh
│   ├── grade_filter.py       # Logic lọc điểm < 4.0 hoặc dấu đỏ, xuất JSON/CSV
│   ├── pipeline.py           # Bộ điều phối kết nối toàn bộ luồng xử lý
│   ├── main.py               # CLI runner thực thi pipeline từ dòng lệnh
│   ├── api.py                # REST API FastAPI phục vụ upload và giao tiếp frontend
│   ├── requirements.txt      # Danh sách thư viện Python
│   └── tests/                # Bộ kiểm thử tự động pytest
│       ├── test_red_detector.py
│       ├── test_grade_filter.py
│       └── test_ocr_parser.py
│
├── frontend/                 # Giao diện Web SPA (React + TypeScript + Tailwind CSS)
│   ├── src/
│   │   ├── components/
│   │   │   ├── FileUploader.tsx      # Vùng kéo thả file & chọn model Ollama
│   │   │   ├── ResultSummary.tsx     # Thống kê tổng môn, đạt, không đạt, vùng đỏ
│   │   │   ├── TranscriptTable.tsx   # Bảng danh sách môn không đạt, tải CSV/JSON
│   │   │   └── VisualPreview.tsx     # Xem trước ảnh gốc kèm bounding box đỏ
│   │   ├── types.ts                  # Khai báo TypeScript types
│   │   └── App.tsx                   # Màn hình điều khiển chính
│   ├── package.json
│   └── vite.config.ts
│
├── samples/                  # Dữ liệu bảng điểm mẫu (Ảnh & PDF scan)
├── main.py                   # Wrapper chạy CLI từ thư mục gốc
├── requirements.txt          # File cài đặt dependencies ở thư mục gốc
└── README.md
```

---

## 3. Hướng dẫn cài đặt & Chuẩn bị môi trường

### Bước 1: Kéo model Ollama Vision local
Đảm bảo bạn đã cài đặt [Ollama](https://ollama.com/) trên máy và dịch vụ đang chạy:

```bash
# Kéo mô hình llama3.2-vision theo yêu cầu
ollama pull llama3.2-vision

# Khởi động dịch vụ Ollama (nếu chưa chạy nền)
ollama serve
```

*(Lưu ý: Hệ thống cũng hỗ trợ các model Vision khác đã cài sẵn trên máy bạn như `qwen2.5vl:7b`)*

### Bước 2: Cài đặt thư viện Python (Backend)
Mở terminal tại thư mục gốc `PTUD/`:

```bash
pip install -r requirements.txt
```

---

## 4. Hướng dẫn chạy chương trình

### Cách 1: Chạy trực tiếp qua dòng lệnh (CLI)
Chạy pipeline trên file ảnh hoặc file PDF với lệnh:

```bash
# Chạy với file ảnh mẫu (dùng model llama3.2-vision mặc định)
python backend/main.py --input samples/sample_transcript.png

# Hoặc chạy từ thư mục gốc và chỉ định model tùy chọn
python main.py --input samples/sample_transcript.png --model qwen2.5vl:7b

# Chạy với file PDF scan
python main.py --input samples/sample_transcript_scan.pdf --output-dir my_output
```

Kết quả sẽ được in trực tiếp ra bảng điều khiển terminal và tự động lưu 3 tệp vào thư mục `output/`:
- `<tên_file>_failed.json`
- `<tên_file>_failed.csv`
- `<tên_file>_annotated.png` (Ảnh có vẽ khung đỏ OpenCV)

---

### Cách 2: Khởi chạy Giao diện Web (Tách biệt Frontend & Backend)

#### 1. Chạy Backend API (FastAPI)
Mở một cửa sổ Terminal:
```bash
# Khởi chạy máy chủ API tại http://127.0.0.1:8000
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload
```

Tài liệu Swagger API tự động xem tại: `http://127.0.0.1:8000/docs`

#### 2. Chạy Frontend (React + Vite)
Mở một cửa sổ Terminal khác:
```bash
cd frontend
npm install
npm run dev
```

Truy cập ứng dụng tại:
```
http://localhost:3000
```

Tại giao diện Web, bạn có thể:
1. Theo dõi trạng thái kết nối tới Ollama local.
2. Chọn mô hình Vision (`llama3.2-vision` hoặc model khác trong máy).
3. Kéo thả file ảnh hoặc PDF bảng điểm để phân tích.
4. Xem bảng thống kê số môn đạt / không đạt.
5. Xem ảnh giám sát trực quan các vùng đỏ do OpenCV khoanh vùng.
6. Tải xuống báo cáo kết quả định dạng **CSV (Excel)** hoặc **JSON**.

---

## 5. Chạy kiểm thử tự động (Unit Tests)

Bộ kiểm thử bao gồm kiểm tra thuật toán OpenCV HSV, logic lọc môn không đạt, các ca biên điểm số và parser JSON chịu lỗi:

```bash
python -m pytest backend/tests -v
```
