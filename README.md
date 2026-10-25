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

---

## 6. Trợ lý AI tư vấn học vụ (RAG Chatbot, SQL Server & Dataset)

Hệ thống tư vấn học vụ hỗ trợ sinh viên chuẩn bị tốt nghiệp dựa trên kỹ thuật **RAG (Retrieval-Augmented Generation)**, cơ sở dữ liệu **Microsoft SQL Server**, mô hình ngôn ngữ lớn **Qwen2.5:7b** và mô hình nhúng **BGE-M3** thông qua **Ollama**.

### 6.1. Chạy Migration CSDL (T-SQL)

Tệp migration nằm tại [database/migration_seed_dataset.sql](file:///d:/PTUD/database/migration_seed_dataset.sql), bổ sung:
- Bảng điều kiện tốt nghiệp: `graduation_conditions` (kèm View `dieu_kien_tot_nghiep`) với các trường: `ma`, `nhom`, `dieu_kien`, `mo_ta`, `ap_dung_chinh_quy`, `ap_dung_lien_thong_hoan_chinh`, `muc_tren_trang`.
- Bổ sung các cột cho `program_courses`: `hoc_ky`, `loai`, `nhom_tu_chon`, `nhan_tren_trang`, `ghi_chu`, `ten_mon`, `tin_chi`, hỗ trợ `course_id` nhận NULL khi môn học chưa có mã học phần trong `courses`.
- Bổ sung các cột lưu nguồn văn bản trong `documents`: `so_hieu`, `url`, `ngay_thu_thap` và metadata cho `document_chunks`.

Cách áp dụng migration:
- **Cách 1**: Mở và thực thi tệp `database/migration_seed_dataset.sql` trong **SQL Server Management Studio (SSMS)** hoặc **Azure Data Studio**.
- **Cách 2**: Chạy lệnh Python:
  ```powershell
  $env:PYTHONPATH="."
  python -c "import re; from sqlalchemy import create_engine, text; from backend.app.config import settings; engine=create_engine(settings.DATABASE_URL); batches=re.split(r'^\s*GO\s*$', open('database/migration_seed_dataset.sql', encoding='utf-8').read(), flags=re.M|re.I); conn=engine.connect(); [conn.execute(text(b.strip())) for b in batches if b.strip()]; conn.commit(); print('Migration OK!')"
  ```

### 6.2. Nạp dữ liệu Dataset & Knowledge Base (Seed Dataset)

Kịch bản nạp dữ liệu được viết tại [backend/scripts/seed_dataset.py](file:///d:/PTUD/backend/scripts/seed_dataset.py), có cơ chế kiểm tra idempotent (chạy lặp lại an toàn, không bị nhân đôi dữ liệu):
- Nạp danh mục môn học từ `03_chuong_trinh_dao_tao.xlsx` (sheet `mon_hoc`) vào bảng `program_courses`. Với các môn không ghi tín chỉ (như GDQP, GDTC), hệ thống giữ giá trị `NULL`, không tự điền.
- Nạp 11 điều kiện tốt nghiệp từ `04_dieu_kien_tot_nghiep.xlsx` (sheet `dieu_kien`) vào bảng `graduation_conditions`.
- Nạp danh mục văn bản từ `02b_danh_muc_van_ban.xlsx` vào bảng `documents` (chỉ nạp các bản ghi có trạng thái *"Đã đọc nội dung"*).
- Phân tách và làm sạch nội dung quy định xét tốt nghiệp (theo các mục A.1.1, A.1.2, A.2, A.3, A.4, A.5.1, A.5.2, B, C, D) cùng dữ liệu `ho_so_nop` và chương trình đào tạo; sau đó nhúng vector qua **BGE-M3** và lưu vào `document_chunks`.

Lệnh chạy:
```powershell
$env:PYTHONPATH="."
python backend/scripts/seed_dataset.py
```

### 6.3. Kiểm thử & Đánh giá tự động Chatbot QA (Evaluation)

Kịch bản đánh giá được viết tại [backend/scripts/eval_qa.py](file:///d:/PTUD/backend/scripts/eval_qa.py):
- Đọc 19 câu hỏi kiểm thử từ `database/seed_data/07_bo_cau_hoi_kiem_thu.xlsx` (sheet `cau_hoi`).
- Tự động gọi API Chatbot, đối chiếu câu trả lời với đáp án chuẩn theo các ý chính (ví dụ: điểm tích lũy 5.0, Tiếng Anh Bậc 3, lệ phí 100.000 VNĐ, từ chối câu hỏi ngoài học vụ, phản hồi chưa có dữ liệu đối với khoa khác...).
- Kiểm tra tính đầy đủ của nguồn trích dẫn.
- Xuất báo cáo CSV tại `output/eval_qa_report.csv` gồm 4 cột: `ma_cau_hoi`, `cau_tra_loi`, `dung/sai`, `co_nguon_hay_khong`.

Lệnh chạy:
```powershell
$env:PYTHONPATH="."
python backend/scripts/eval_qa.py
```

---

## 7. Đồng bộ Lịch học & Lịch thi Trung tâm Ngoại ngữ - Tin học (NNTH)

Hệ thống tích hợp module tự động đồng bộ lịch khai giảng và lịch thi chứng chỉ (Ngoại ngữ, Tin học) từ cổng API công khai của Trung tâm Ngoại ngữ - Tin học Trường ĐH Lạc Hồng (`tapi.lhu.edu.vn`).

### 7.1. Cấu trúc CSDL
- Bảng `center_schedules`: Lưu lịch các lớp/khóa học khai giảng (tên khóa, loại, ngày khai giảng, lịch học, hình thức, học phí, kỳ thi dự kiến). Khóa chống trùng: `lop_id UNIQUE`.
- Bảng `center_exams`: Lưu lịch thi chứng chỉ chính thức và dự kiến (tên kỳ thi, ngày thi, hạn đăng ký, tình trạng, lệ phí thi, lệ phí chứng chỉ). Khóa chống trùng: `(ky_thi_id, is_du_kien) UNIQUE`.
- Bảng `center_sync_history`: Nhật ký lịch sử các lần đồng bộ.

### 7.2. Migration & Lệnh chạy
- **Migration T-SQL**: [database/migration_center_schedules.sql](file:///d:/PTUD/database/migration_center_schedules.sql)
  ```powershell
  $env:PYTHONPATH="."
  .\venv\Scripts\python.exe -c "import re; from sqlalchemy import create_engine, text; from backend.app.config import settings; engine=create_engine(settings.DATABASE_URL); batches=re.split(r'^\s*GO\s*$', open('database/migration_center_schedules.sql', encoding='utf-8').read(), flags=re.M|re.I); conn=engine.connect(); [conn.execute(text(b.strip())) for b in batches if b.strip()]; conn.commit(); print('Migration center tables OK!')"
  ```
- **Chạy đồng bộ kiểm tra**:
  ```powershell
  $env:PYTHONPATH="."
  .\venv\Scripts\python.exe backend/scripts/test_nnth_sync.py
  ```

### 7.3. Các Endpoint API
- `POST /admin/sync-nnth`: Chạy đồng bộ thủ công từ API NNTH vào SQL Server (chạy lặp lại an toàn, không nhân đôi).
- `GET /api/center/schedules?loai=...&from_today=true`: Lấy danh sách lịch khai giảng sắp tới (hỗ trợ lọc theo loại Ngoại ngữ / Tin học).
- `GET /api/center/exams?loai=...&is_du_kien=...&from_today=true`: Lấy danh sách lịch thi sắp tới (hỗ trợ lọc loại, kỳ thi chính thức / dự kiến).
- `GET /api/center/summary`: Thống kê tổng quan số lượng lịch học và kỳ thi sắp tới.

### 7.4. Cơ chế đồng bộ nền & Chatbot
- **Tác vụ nền**: Hệ thống chạy ngầm định kỳ **6 giờ/lần** khi ứng dụng FastAPI khởi động để cập nhật dữ liệu mới nhất mà không gọi API trường mỗi lần sinh viên truy vấn.
- **Tư vấn qua Chatbot**: Khi người dùng hỏi về lịch thi hoặc lịch học trung tâm, hệ thống cung cấp thông tin mới nhất kèm dòng trích dẫn:
  `Dữ liệu cập nhật lúc <ngay_lay_du_lieu>, xem lịch mới nhất tại nnth.lhu.edu.vn`.
  (Nếu lần đồng bộ gần nhất lỗi, chatbot sẽ nêu rõ chưa lấy được lịch mới).
