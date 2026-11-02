# Trợ Lý AI Tư Vấn Học Vụ & Pipeline Bảng Điểm (HocVuAI)

Hệ thống **HocVuAI** là giải pháp toàn diện hỗ trợ sinh viên chuẩn bị tốt nghiệp:
1. **Trợ lý AI tư vấn học vụ (RAG Chatbot)**: Tư vấn quy chế đào tạo tín chỉ, chuẩn đầu ra (150 tín chỉ, GDQP, GDTC, 4 kỹ năng mềm), quy định rớt môn/học lại/thi lại lần 2/học vét, hạn đăng ký học phần và lịch thi/lớp học từ Trung tâm Ngoại ngữ - Tin học (NNTH).
2. **Hồ sơ học vụ & Đánh giá tốt nghiệp cá nhân hóa**: Tự động đối chiếu tín chỉ tích lũy, các môn học bắt buộc còn thiếu, trạng thái chứng chỉ ngoại ngữ - tin học theo từng sinh viên (`/students/me/graduation-check`).
3. **Pipeline OCR Bảng Điểm (Vision LLM + OpenCV)**: Đọc file ảnh/PDF bảng điểm, phát hiện vùng đánh dấu đỏ bằng OpenCV HSV và trích xuất điểm số bằng mô hình thị giác AI cục bộ.

---

## 1. Yêu cầu môi trường

- **Hệ điều hành**: Windows 10/11, Linux, hoặc macOS.
- **Python**: Phiên bản `3.10` trở lên (khuyên dùng Python 3.11 - 3.12).
- **Cơ sở dữ liệu**: Microsoft SQL Server (hỗ trợ SQL Server 2017+ hoặc SQL Server Express), yêu cầu cài đặt **ODBC Driver 17 for SQL Server**.
- **Node.js** (cho Frontend): Node.js 18+ và npm/yarn.
- **Ollama Local**: Cài đặt [Ollama](https://ollama.com/) và tải đủ 3 mô hình sau:
  ```bash
  # 1. Mô hình ngôn ngữ lớn chat chính thức (tối ưu hóa tốc độ trên CPU)
  ollama pull qwen2.5:3b

  # 2. Mô hình embedding nhúng vector 1024 chiều phục vụ RAG
  ollama pull bge-m3

  # 3. Mô hình thị giác Vision OCR đọc bảng điểm
  ollama pull qwen2.5vl:7b
  ```

---

## 2. Cài đặt & Cấu hình

### 2.1. Cài đặt môi trường Python
Tại thư mục gốc dự án:
```powershell
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt môi trường ảo (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt
```

### 2.2. Cấu hình biến môi trường
Tạo file `.env` từ file mẫu [.env.example](file:///.env.example):
```powershell
Copy-Item .env.example .env
```
Điều chỉnh chuỗi kết nối `DATABASE_URL` trong `.env` cho phù hợp với SQL Server của bạn:
```env
DATABASE_URL=mssql+pyodbc://@localhost/HocVuAI?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes
JWT_SECRET=your-secret-key-here-change-in-production
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=bge-m3
LLM_MODEL=qwen2.5:3b
VISION_MODEL=qwen2.5vl:7b
REQUIRED_CREDITS=150
```

### 2.3. Khởi tạo Cơ sở dữ liệu (Migrations)
Chạy toàn bộ schema cơ sở dữ liệu và các bản cập nhật migration:
```powershell
# 1. Chạy schema gốc
python -c "from backend.app.db import engine; from sqlalchemy import text; f=open('database/schema.sql', encoding='utf-8').read(); conn=engine.connect(); [conn.execute(text(b.strip())) for b in f.split('GO') if b.strip()]; conn.commit(); print('Schema OK!')"

# 2. Chạy migration chứng chỉ sinh viên
python -c "from backend.app.db import engine; from sqlalchemy import text; f=open('database/migration_student_certificates.sql', encoding='utf-8').read(); conn=engine.connect(); [conn.execute(text(b.strip())) for b in f.split('GO') if b.strip()]; conn.commit(); print('Migration certificates OK!')"

# 3. Chạy migration lịch trung tâm NNTH
python -c "from backend.app.db import engine; from sqlalchemy import text; f=open('database/migration_center_schedules.sql', encoding='utf-8').read(); conn=engine.connect(); [conn.execute(text(b.strip())) for b in f.split('GO') if b.strip()]; conn.commit(); print('Migration center schedules OK!')"
```

---

## 3. Nạp Dữ Liệu Học Vụ & Văn Bản Quy Định (Data Ingestion)

### 3.1. Nạp văn bản quy chế đào tạo tín chỉ (DOCX $\rightarrow$ RAG)
Script [backend/scripts/ingest_quy_dinh.py](file:///backend/scripts/ingest_quy_dinh.py) sẽ đọc file `văn_bản_quy_định.docx`, phân tách thành 16 chunks quy chuẩn (Điều 27 tốt nghiệp, Điều 19 cấm thi, Điều 12 học lại, thi lại lần 2, học vét, 4 kỹ năng mềm, GDQP, GDTC, liên hệ giáo vụ) và nhúng vector bằng mô hình `bge-m3`:
```powershell
python backend/scripts/ingest_quy_dinh.py
```
*(Script được thiết kế idempotent: chạy lại an toàn, tự động làm sạch bản ghi cũ của document 9001).*

### 3.2. Nạp dữ liệu nền tảng (Chương trình đào tạo, sinh viên, điều kiện tốt nghiệp)
```powershell
python backend/scripts/seed_dataset.py
```

---

## 4. Chạy Kiểm Thử Tự Động (Unit & Integration Tests)

Dự án sở hữu bộ test toàn diện 202 tests bao gồm: kiểm thử guardrail chống injection, chống bịa quy chế, phân loại 3 nhánh điểm rớt, kiểm thử bảo mật phân quyền chéo ID, cleanup file upload và luồng RAG:
```powershell
python -m pytest backend/tests/ -q
```
*Yêu cầu kết quả:* **202 passed** (100%).

---

## 5. Khởi Chạy Ứng Dụng

### 5.1. Khởi chạy Backend API (FastAPI)
```powershell
uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload
```
- Tài liệu API tương tác (Swagger UI): `http://127.0.0.1:8000/docs`
- Luồng chat tư vấn học vụ: `POST /chat` và `POST /chat/stream`
- Luồng kiểm tra tốt nghiệp: `GET /students/me/graduation-check`
- Luồng tải bảng điểm OCR: `POST /api/process` hoặc `POST /chat/upload`

### 5.2. Khởi chạy Giao diện Frontend (React + Vite + Tailwind CSS)
Mở một terminal mới:
```powershell
cd frontend
npm install
npm run dev
```
Truy cập giao diện Web tại: `http://localhost:3000`

---

## 6. Cấu Trúc Thư Mục Dự Án

```
PTUD/
├── backend/
│   ├── api.py                    # API Server chính FastAPI (auth, upload, chat, graduation)
│   ├── grade_filter.py           # Phân loại lý do rớt môn 3 nhánh (học lại, thi lại, xác nhận GV)
│   ├── app/
│   │   ├── config.py             # Cấu hình Pydantic Settings (150 tín chỉ, timeout Ollama)
│   │   ├── deps.py               # Dependency injection & xác thực JWT
│   │   ├── prompts.py            # Prompt RAG chống bịa, Điều 27, cấm thi, học vét
│   │   ├── routers/
│   │   │   ├── auth.py           # Đăng nhập, cấp JWT token
│   │   │   ├── chat.py           # Chatbot RAG, intent cá nhân hóa, stream filter
│   │   │   ├── students.py       # Graduation check & quản lý hồ sơ sinh viên
│   │   │   └── center.py         # Lịch thi, lịch học trung tâm NNTH
│   │   └── services/
│   │       ├── embedding.py      # Sinh vector embedding bge-m3
│   │       ├── synonyms.py       # Từ điển đồng nghĩa, chuẩn hóa không dấu và khẩu ngữ
│   │       ├── stream_filter.py  # Lọc stream bảo vệ token cấm
│   │       ├── vision_ocr.py     # Gọi Ollama Vision trích xuất bảng điểm
│   │       └── red_detector.py   # OpenCV HSV phát hiện vùng đánh dấu đỏ
│   ├── scripts/
│   │   ├── ingest_quy_dinh.py    # Script nạp docx quy định vào RAG
│   │   └── seed_dataset.py       # Script nạp dataset CTĐT và sinh viên
│   └── tests/                    # Bộ 202 unit & integration tests tự động
│
├── database/                     # Schema và migration SQL Server
│   ├── schema.sql
│   ├── migration_student_certificates.sql
│   └── seed_data/                # Dữ liệu mẫu & văn bản quy định
│
├── docs/                         # Tài liệu nghiệm thu & kiểm định
│   └── BAO_CAO_KIEM_TRA.md       # Báo cáo đánh giá chất lượng 17 yêu cầu
│
├── frontend/                     # Giao diện người dùng Web SPA (React + TypeScript)
├── văn_bản_quy_định.docx         # Văn bản quy chế đào tạo chuẩn
├── requirements.txt              # Danh sách thư viện Python
├── .env.example                  # Mẫu cấu hình môi trường
└── .gitignore                    # Bộ lọc file an toàn cho Git
```

---

## 7. Báo Cáo Đánh Giá & Kiểm Định Chất Lượng

Chi tiết kết quả đo đạc thực nghiệm trên 17 yêu cầu của hệ thống (bảo mật, tốc độ phản hồi, độ chính xác quy chế, phân quyền và dọn dẹp file tạm) được ghi nhận chi tiết tại [docs/BAO_CAO_KIEM_TRA.md](file:///docs/BAO_CAO_KIEM_TRA.md).
