# HocVuAI - Trợ Lý AI Tư Vấn Học Vụ & Pipeline Bảng Điểm

![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4-38B2AC?logo=tailwind-css&logoColor=white)
![SQL Server](https://img.shields.io/badge/Database-SQL_Server-CC292B?logo=microsoftsqlserver&logoColor=white)
![Ollama](https://img.shields.io/badge/AI_Engine-Ollama_Local-black?logo=ollama&logoColor=white)

---

## 1. Giới thiệu

**HocVuAI** là hệ thống trợ lý học vụ thông minh hỗ trợ sinh viên chuẩn bị tốt nghiệp tại Trường Đại học Lạc Hồng (LHU), đặc biệt tối ưu cho chương trình đào tạo ngành Công nghệ thông tin. Hệ thống kết hợp mô hình ngôn ngữ lớn chạy cục bộ (Ollama Local), kỹ thuật truy xuất tăng cường (RAG) và thị giác máy tính đa phương thức (Vision LLM kết hợp OpenCV HSV) để tự động hóa việc tư vấn quy chế, đối chiếu điều kiện tốt nghiệp cá nhân hóa và đọc phân tích bảng điểm học tập an toàn, bảo mật.

---

## 2. Tính năng chính

- **Trợ lý AI tư vấn quy chế đào tạo (RAG Chatbot):**
  - Tra cứu chính xác điều kiện tốt nghiệp (150 tín chỉ, điểm trung bình tích lũy $\ge 5.0$, chuẩn GDQP-AN, GDTC, 4 chứng chỉ kỹ năng mềm, chuẩn đầu ra Ngoại ngữ và Tin học) theo Niên giám 2023 và Quyết định 22/QĐ-ĐHLH.
  - Hướng dẫn xử lý khi rớt môn, học lại, thi lại lần 2, học vét, rút bớt học phần và hạn chót đăng ký trên hệ thống.
  - Trích dẫn minh bạch số Điều/Khoản và văn bản nguồn trong từng câu trả lời.
  - Nhận diện linh hoạt câu hỏi tiếng Việt không dấu và từ ngữ khẩu ngữ sinh viên (`rớt môn`, `trả nợ môn`, `học vét`...).
  - Tích hợp lớp phòng vệ (Guardrails) chống prompt injection và từ chối các chủ đề ngoài phạm vi đào tạo.
  - Hỗ trợ phản hồi thời gian thực qua Server-Sent Events (SSE Streaming).
- **Hồ sơ học vụ & Đánh giá tốt nghiệp cá nhân hóa:**
  - Tự động đối chiếu dữ liệu điểm và chứng chỉ của sinh viên đăng nhập (`GET /students/me/graduation-check`).
  - Tổng hợp số tín chỉ đã tích lũy, số tín chỉ còn thiếu, danh sách các môn bắt buộc chưa hoàn thành.
  - Phân quyền bảo mật nghiêm ngặt theo JWT Token, ngăn chặn tuyệt đối việc sinh viên truy cập chéo hồ sơ của nhau.
- **Pipeline OCR & Phân tích bảng điểm đa phương thức:**
  - Tiếp nhận bảng điểm định dạng ảnh (`.png`, `.jpg`, `.jpeg`) và tài liệu PDF (`.pdf`).
  - Hỗ trợ cả file PDF có text layer lẫn PDF scan thuần ảnh (tự động chuyển đổi trang qua `pdfplumber`, `pdf2image`, `pypdfium2`).
  - Tiền xử lý tối ưu: tự động nén JPEG chất lượng 85, resize cạnh dài tối đa 1600px và giới hạn tối đa 3 trang đầu PDF nhằm tiết kiệm tài nguyên.
  - Nhận diện vùng đánh dấu đỏ bằng OpenCV không gian màu HSV để phát hiện các môn cần lưu ý đặc biệt.
  - Trích xuất bảng điểm bằng mô hình thị giác AI cục bộ (`qwen2.5vl:3b`) với KV cache cố định `num_ctx=2048`, tối ưu chạy mượt mà trên laptop có GPU rời 4GB VRAM (như RTX 3050).
  - Phân loại lý do rớt môn theo 3 nhánh rõ ràng: Điểm 0/cấm thi $\rightarrow$ Phải học lại; Điểm $< 4.0$ $\rightarrow$ Được đăng ký thi lại lần 2; Điểm $\ge 4.0$ có đánh dấu đỏ $\rightarrow$ Cần liên hệ giáo vụ xác nhận.
- **Tích hợp lịch học & lịch thi Trung tâm Ngoại ngữ - Tin học (NNTH):**
  - Tự động đồng bộ và tra cứu lịch khai giảng các lớp ôn luyện (VSTEP, TOEIC, IC3, MOS, CNTT cơ bản) và lịch thi chứng chỉ sắp diễn ra.

---

## 3. Công nghệ sử dụng

### Backend
- **Ngôn ngữ:** Python 3.10 - 3.13
- **Web Framework:** FastAPI 0.110+, Uvicorn (ASGI Server), Pydantic v2
- **ORM & Database Client:** SQLAlchemy 2.0+, PyODBC 5.0+
- **Xác thực & Bảo mật:** JWT (`python-jose[cryptography]`), mã hóa mật khẩu `passlib[bcrypt]` / `bcrypt 3.2.2`
- **Xử lý tài liệu:** `python-docx`, `openpyxl`, `pdfplumber`, `pdf2image`, `pypdfium2`
- **Xử lý ảnh & Thị giác máy tính:** OpenCV (`opencv-python`), Pillow (`PIL`), NumPy
- **NLP & Khớp chuỗi:** `rapidfuzz`, `beautifulsoup4`

### AI & Mô hình cục bộ (Ollama)
- **Engine:** [Ollama](https://ollama.com/) (Chạy 100% offline trên máy chủ/máy trạm)
- **Chat LLM:** `qwen2.5:3b` (mô hình ngôn ngữ gọn nhẹ, tốc độ cao trên CPU và GPU)
- **Vector Embedding:** `bge-m3` (mô hình nhúng ngữ nghĩa đa ngôn ngữ 1024 chiều)
- **Vision OCR:** `qwen2.5vl:3b` (mô hình thị giác đa phương thức, tối ưu cho VRAM 4GB)

### Frontend
- **Framework:** React 19, TypeScript 5, Vite 8
- **Giao diện & Styling:** Tailwind CSS v4, Lucide React (Icons)
- **Kiểm thử giao diện:** Vitest, Testing Library

### Cơ sở dữ liệu
- **Hệ quản trị CSDL:** Microsoft SQL Server 2017+ / SQL Server Express
- **Kết nối driver:** ODBC Driver 17 for SQL Server hoặc ODBC Driver 18 for SQL Server

---

## 4. Cấu trúc thư mục

```text
PTUD/
├── backend/                              # Mã nguồn Backend FastAPI
│   ├── api.py                            # API Server chính & định tuyến tổng thể
│   ├── ocr_extractor.py                  # Module giao tiếp Ollama Vision & trích xuất JSON
│   ├── certificate_extractor.py          # Module OCR thông tin chứng chỉ ngoại ngữ/tin học
│   ├── pdf_processor.py                  # Xử lý text layer và chuyển đổi trang PDF sang ảnh
│   ├── pipeline.py                       # Pipeline tích hợp OCR Vision + OpenCV nhận diện vùng đỏ
│   ├── red_detector.py                   # Phát hiện màu đỏ bằng OpenCV HSV và tính toán IoU
│   ├── grade_filter.py                   # Phân loại học lại / thi lại / xác nhận giáo vụ
│   ├── normalize.py                      # Chuẩn hóa tên môn học, mã môn và thang điểm
│   ├── priority_engine.py                # Xếp hạng thứ tự ưu tiên học lại môn theo tín chỉ
│   ├── app/
│   │   ├── config.py                     # Quản lý biến môi trường Pydantic BaseSettings
│   │   ├── db.py                         # Khởi tạo kết nối SQLAlchemy Engine & Session
│   │   ├── deps.py                       # Dependency injection kiểm tra quyền và giải mã JWT
│   │   ├── prompts.py                    # Hệ thống System Prompts, từ điển đồng nghĩa & Guardrails
│   │   ├── routers/                      # Các router phân hệ
│   │   │   ├── auth.py                   # Đăng nhập, cấp phát JWT và xem thông tin user (/auth)
│   │   │   ├── chat.py                   # Hội thoại tư vấn RAG, SSE stream, upload tài liệu (/chat)
│   │   │   ├── students.py               # Kiểm tra chuẩn tốt nghiệp cá nhân hóa (/students)
│   │   │   ├── transcripts.py            # Quản lý và nhập bảng điểm sinh viên (/transcripts)
│   │   │   ├── center.py                 # Lịch học và lịch thi Trung tâm NNTH (/api/center)
│   │   │   └── documents.py              # Quản lý danh mục tài liệu quy chế (/documents)
│   │   └── services/
│   │       ├── embedding.py              # Tạo vector nhúng văn bản bằng mô hình bge-m3
│   │       ├── retrieval.py              # Thuật toán tìm kiếm cosine similarity cho RAG
│   │       ├── chunking.py               # Phân tách văn bản thành các đoạn ngữ nghĩa
│   │       ├── synonyms.py               # Từ điển đồng nghĩa, chuẩn hóa tiếng Việt không dấu
│   │       └── stream_filter.py          # Bộ lọc token thời gian thực trong luồng SSE
│   ├── services/
│   │   └── nnth_sync.py                  # Crawler đồng bộ dữ liệu lịch mở lớp và lịch thi NNTH
│   ├── scripts/                          # Scripts quản trị và nạp dữ liệu
│   │   ├── ingest_quy_dinh.py            # Phân đoạn và nhúng tài liệu quy định vào CSDL
│   │   ├── seed_dataset.py               # Nạp khung CTĐT, điều kiện tốt nghiệp từ Excel
│   │   ├── test_all_endpoints.py         # Kiểm tra tính sẵn sàng của toàn bộ endpoint
│   │   └── test_nnth_sync.py             # Kiểm tra crawler đồng bộ dữ liệu NNTH
│   └── tests/                            # Bộ kiểm thử tự động (Unit & Integration Tests)
│
├── frontend/                             # Mã nguồn Frontend (React + TypeScript + Vite)
│   ├── src/
│   │   ├── components/                   # UI Components (Chat, Sidebar, Modals, Composer)
│   │   ├── services/api.ts               # Tầng gọi API Backend (Fetch + SSE Reader)
│   │   ├── types.ts                      # Khai báo kiểu dữ liệu TypeScript
│   │   ├── App.tsx                       # Component chính điều phối ứng dụng
│   │   └── main.tsx                      # Entry point React DOM
│   └── package.json                      # Cấu hình gói và dependencies của frontend
│
├── database/                             # Cơ sở dữ liệu và kịch bản SQL
│   ├── schema.sql                        # Schema bảng CSDL gốc (users, students, grades...)
│   ├── migration_center_schedules.sql    # Migration bảng lịch học/thi trung tâm NNTH
│   ├── migration_student_certificates.sql# Migration bảng chứng chỉ ngoại ngữ - tin học
│   └── seed_data/                        # Thư mục chứa bảng dữ liệu Excel nguồn
│
├── docs/                                 # Tài liệu kiểm thử và đánh giá dự án
│   └── BAO_CAO_KIEM_TRA.md               # Báo cáo kết quả kiểm tra 17 yêu cầu học vụ
│
├── start_all.bat                         # Kịch bản khởi động song song Backend và Frontend (Windows)
├── requirements.txt                      # Danh sách thư viện Python phụ thuộc
├── pytest.ini                            # Cấu hình kiểm thử Pytest
├── .env.example                          # File mẫu cấu hình biến môi trường
└── README.md                             # Tài liệu hướng dẫn dự án
```

---

## 5. Yêu cầu hệ thống

- **Hệ điều hành:** Windows 10/11 (64-bit), Ubuntu Linux 20.04+, hoặc macOS.
- **Python:** Phiên bản `3.10` trở lên (đã kiểm thử tương thích tốt trên Python 3.11, 3.12, 3.13).
- **Node.js:** Phiên bản `v18.0.0` trở lên và công cụ `npm`.
- **Cơ sở dữ liệu:** Microsoft SQL Server (2017, 2019, 2022 hoặc SQL Server Express).
  - Đã cài đặt **ODBC Driver 17 for SQL Server** hoặc **ODBC Driver 18 for SQL Server**.
- **Ollama Engine:** Đã cài đặt [Ollama](https://ollama.com/) và khởi chạy dịch vụ (`ollama serve`).
- **Phần cứng đề xuất:**
  - **RAM:** Tối thiểu 8 GB (khuyến nghị 16 GB).
  - **GPU:** NVIDIA GPU hỗ trợ CUDA với VRAM $\ge$ 4 GB (ví dụ: GTX 1650, RTX 3050 trở lên) để chạy mô hình Vision OCR dưới 15 giây. (Nếu chạy trên CPU, pipeline vẫn hoạt động bình thường nhờ cơ chế tối ưu resize ảnh).

---

## 6. Cài đặt

### Bước 1: Clone mã nguồn
```bash
git clone <URL_REPOSITORY>
cd PTUD
```

### Bước 2: Thiết lập môi trường ảo Python và cài đặt thư viện
```powershell
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt môi trường ảo (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Nâng cấp pip và cài đặt dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Bước 3: Cài đặt dependencies cho Frontend
```powershell
cd frontend
npm install
cd ..
```

### Bước 4: Tải các mô hình AI trong Ollama
Mở terminal riêng và chạy các lệnh sau để tải 3 mô hình cần thiết:
```bash
# 1. Mô hình Chat RAG tiếng Việt (dung lượng ~2.0 GB)
ollama pull qwen2.5:3b

# 2. Mô hình sinh vector nhúng cho RAG (dung lượng ~1.1 GB)
ollama pull bge-m3

# 3. Mô hình thị giác Vision OCR đọc bảng điểm (dung lượng ~2.9 GB)
ollama pull qwen2.5vl:3b
```

---

## 7. Cấu hình biến môi trường

Tạo file cấu hình `.env` tại thư mục gốc dự án:
```powershell
Copy-Item .env.example .env
```

Bảng danh mục các biến cấu hình trong [`backend/app/config.py`](file:///backend/app/config.py):

| Tên biến | Mô tả | Giá trị mặc định | Bắt buộc |
| :--- | :--- | :---: | :---: |
| `DATABASE_URL` | Chuỗi kết nối SQLAlchemy tới SQL Server qua ODBC | *(Không có)* | **Có** |
| `JWT_SECRET` | Khóa bảo mật ký và giải mã JSON Web Token | *(Không có)* | **Có** |
| `JWT_EXPIRE_MINUTES` | Thời gian hết hạn của Access Token (phút) | `60` | Không |
| `OLLAMA_BASE_URL` | Địa chỉ máy chủ dịch vụ Ollama local | `http://localhost:11434` | Không |
| `LLM_MODEL` | Tên mô hình ngôn ngữ lớn dùng cho chat tư vấn | `qwen2.5:3b` | Không |
| `EMBEDDING_MODEL` | Tên mô hình sinh vector nhúng cho RAG | `bge-m3` | Không |
| `OLLAMA_VISION_MODEL` | Tên mô hình thị giác đọc bảng điểm / chứng chỉ | `qwen2.5vl:3b` | Không |
| `OCR_TIMEOUT_SECONDS` | Thời gian chờ tối đa khi xử lý OCR hình ảnh (giây) | `300` | Không |
| `OLLAMA_TIMEOUT_CHAT` | Thời gian chờ tối đa khi sinh câu trả lời chat (giây) | `300` | Không |
| `OLLAMA_TIMEOUT_EMBED`| Thời gian chờ tối đa khi nhúng vector (giây) | `180` | Không |
| `REQUIRED_CREDITS` | Tổng số tín chỉ tích lũy xét tốt nghiệp (CNTT) | `150` | Không |
| `CHUNK_SIZE` | Độ dài tối đa mỗi chunk văn bản RAG | `600` | Không |
| `CHUNK_OVERLAP` | Độ dài gối đầu giữa các chunk liền kề | `80` | Không |
| `TOP_K` | Số lượng đoạn tài liệu liên quan nhất trích xuất cho LLM | `3` | Không |
| `SIMILARITY_THRESHOLD`| Ngưỡng tương đồng cosine tối thiểu để chấp nhận chunk | `0.35` | Không |
| `OLLAMA_NUM_CTX` | Kích thước ngữ cảnh (Context Window) cho chat | `4096` | Không |
| `OLLAMA_KEEP_ALIVE` | Thời gian duy trì model trong RAM tránh tải lại | `30m` | Không |

> [!TIP]
> **Ví dụ cấu hình `DATABASE_URL` hợp lệ trên Windows:**
> - Dùng ODBC Driver 17:  
>   `DATABASE_URL=mssql+pyodbc://@localhost/HocVuAI?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes`
> - Dùng ODBC Driver 18 (SQL Server Express):  
>   `DATABASE_URL=mssql+pyodbc://@localhost\SQLEXPRESS/HocVuAI?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes`

---

## 8. Khởi tạo dữ liệu (Database & Ingestion)

Trước khi chạy ứng dụng lần đầu, hãy nạp cấu trúc bảng và bộ dữ liệu quy định:

### 8.1. Chạy Schema và Migrations
```powershell
# 1. Khởi tạo cơ sở dữ liệu và các bảng chính
python -c "from backend.app.db import engine; from sqlalchemy import text; f=open('database/schema.sql', encoding='utf-8').read(); conn=engine.connect(); [conn.execute(text(b.strip())) for b in f.split('GO') if b.strip()]; conn.commit(); print('Schema OK!')"

# 2. Bổ sung bảng chứng chỉ sinh viên
python -c "from backend.app.db import engine; from sqlalchemy import text; f=open('database/migration_student_certificates.sql', encoding='utf-8').read(); conn=engine.connect(); [conn.execute(text(b.strip())) for b in f.split('GO') if b.strip()]; conn.commit(); print('Migration certificates OK!')"

# 3. Bổ sung bảng lịch học và lịch thi trung tâm NNTH
python -c "from backend.app.db import engine; from sqlalchemy import text; f=open('database/migration_center_schedules.sql', encoding='utf-8').read(); conn=engine.connect(); [conn.execute(text(b.strip())) for b in f.split('GO') if b.strip()]; conn.commit(); print('Migration center schedules OK!')"
```

### 8.2. Nạp văn bản quy chế đào tạo tín chỉ (DOCX $\rightarrow$ Vector Database)
```powershell
python backend/scripts/ingest_quy_dinh.py
```
*Script sẽ đọc tài liệu `văn_bản_quy_định.docx`, phân tích thành 16 chunks quy chuẩn (Điều kiện tốt nghiệp, cấm thi, học lại, thi lại lần 2, học vét, chuẩn Kỹ năng mềm, GDQP, GDTC) và tạo vector embedding qua `bge-m3`.*

### 8.3. Nạp bộ dữ liệu chương trình đào tạo & sinh viên mẫu
```powershell
python backend/scripts/seed_dataset.py
```

---

## 9. Cách chạy ứng dụng

### Cách 1: Khởi động tự động bằng Script (Khuyên dùng trên Windows)
Nhấp đúp chuột vào file [`start_all.bat`](file:///start_all.bat) hoặc chạy từ terminal:
```powershell
.\start_all.bat
```
Script sẽ tự động kích hoạt môi trường ảo, bật Backend FastAPI tại cổng 8000, bật Frontend Vite tại cổng 3000 và mở trình duyệt web.

### Cách 2: Khởi động thủ công từng phần

#### 1. Khởi động Backend API
```powershell
.\venv\Scripts\Activate.ps1
uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload
```
- API Docs tương tác (Swagger UI): `http://127.0.0.1:8000/docs`
- Kiểm tra trạng thái máy chủ: `http://127.0.0.1:8000/api/health`

#### 2. Khởi động Frontend
Mở một cửa sổ terminal mới:
```powershell
cd frontend
npm run dev
```
Truy cập giao diện tại: `http://localhost:3000`

### 8.3. Build sản phẩm Frontend (Production)
```powershell
cd frontend
npm run build
```
Thư mục xuất tĩnh `frontend/dist/` sẵn sàng để phục vụ qua Nginx hoặc web server tĩnh.

### 8.4. Chạy kiểm thử tự động (Testing)

- **Chạy kiểm thử đơn vị OCR & Pipeline (không cần kết nối CSDL):**
  ```powershell
  python -c "import backend.tests.test_ocr_parser as a, backend.tests.test_red_detector as b, backend.tests.test_grade_filter_3branches as c, backend.tests.test_pdf_processor as d; [getattr(m, f)() for m in [a,b,c,d] for f in dir(m) if f.startswith('test_')]; print('All unit tests passed!')"
  ```
- **Chạy toàn bộ test suite kiểm định hệ thống (khi CSDL đang chạy):**
  ```powershell
  python -m pytest backend/tests/ -v
  ```
- **Chạy kiểm thử Frontend:**
  ```powershell
  cd frontend
  npm test
  ```

---

## 10. Hướng dẫn sử dụng & Ví dụ API

### 10.1. Tài khoản thử nghiệm có sẵn trong hệ thống

| Tên đăng nhập | Mật khẩu mặc định | Vai trò | Tình trạng học tập mẫu |
| :--- | :---: | :---: | :--- |
| `sv01` | `123456` | Sinh viên | Khóa 2022, tích lũy 17/150 tín chỉ, nợ 1 môn (3.5đ), thiếu môn IT3100 |
| `sv02` | `123456` | Sinh viên | Khóa 2022, tích lũy 20/150 tín chỉ, không nợ môn |
| `sv03` | `123456` | Sinh viên | Khóa 2022, tiến độ học tập bình thường |
| `admin` | `admin123` | Quản trị viên | Toàn quyền kiểm tra hồ sơ và đồng bộ dữ liệu |

### 10.2. Ví dụ gọi REST API

#### 1. Đăng nhập lấy Bearer Token
```bash
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"sv01\", \"password\": \"123456\"}"
```
*Response mẫu:*
```json
{
  "access_token": "eyJhbGciOiJIUzI1Ni...",
  "token_type": "bearer",
  "user": {
    "id": 2,
    "username": "sv01",
    "role": "student"
  }
}
```

#### 2. Kiểm tra tiến độ tốt nghiệp cá nhân hóa
```bash
curl -X GET "http://127.0.0.1:8000/students/me/graduation-check" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
*Response mẫu:*
```json
{
  "student_code": "sv01",
  "full_name": "Sinh viên 01",
  "major": "Công nghệ thông tin",
  "credits_accumulated": 17,
  "credits_required": 150,
  "credits_remaining": 133,
  "gpa": 7.2,
  "is_qualified": false,
  "missing_mandatory_courses": ["Lập trình hướng đối tượng"],
  "failed_courses": [
    {
      "course_name": "Cấu trúc dữ liệu và giải thuật",
      "score": 3.5,
      "recommendation": "Đăng ký thi lại lần 2 hoặc học lại"
    }
  ],
  "certificates_status": {
    "ngoai_ngu": "Chưa đạt",
    "tin_hoc": "Chưa đạt",
    "gdtc": "Đạt",
    "gdqp": "Đạt",
    "ky_nang_mem": "Thiếu 2/4 kỹ năng"
  }
}
```

#### 3. Gửi tin nhắn hỏi đáp học vụ qua Chat
```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Em bị điểm 3.5 môn Cấu trúc dữ liệu thì có được thi lại lần 2 không?\"}"
```

#### 4. Upload bảng điểm chạy OCR trực tiếp
```bash
curl -X POST "http://127.0.0.1:8000/api/process" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -F "file=@bang_diem_ky_1.png"
```

---

## 11. Đóng góp phát triển (Contributing)

Mọi đóng góp nhằm nâng cao độ chính xác của trợ lý học vụ và hiệu năng pipeline đều được hoan nghênh:

1. **Fork** repository về tài khoản cá nhân.
2. Tạo nhánh tính năng mới (`git checkout -b feature/tinh-nang-moi`).
3. Cam kết các thay đổi với commit message rõ ràng (`git commit -m "feat: bo sung nhan dien diem liet hoc phan"`).
4. Kiểm tra đảm bảo vượt qua toàn bộ unit test (`pytest backend/tests/`).
5. Đẩy nhánh lên remote (`git push origin feature/tinh-nang-moi`).
6. Tạo **Pull Request** kèm mô tả chi tiết các thay đổi.

---

## 12. Giấy phép & Thông tin liên hệ

- **Đơn vị phát triển:** Dự án Ứng dụng AI cho sinh viên - Khoa Công nghệ thông tin, Trường Đại học Lạc Hồng (LHU).
- **Giấy phép (License):** <!-- TODO: bổ sung giấy phép bản quyền chính thức (ví dụ: MIT License hoặc Internal Educational License) -->
- **Hỗ trợ & Liên hệ:**
  - Giáo vụ Khoa CNTT (LHU): `cntt@lhu.edu.vn`
  - Hotline hỗ trợ học vụ: `0251 3952 251` (Phòng B301 - B302, Cơ sở 1, ĐH Lạc Hồng)
