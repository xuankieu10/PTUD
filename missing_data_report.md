# BÁO CÁO RÀ SOÁT DỮ LIỆU CÒN THIẾU HOẶC KHÔNG ĐẦY ĐỦ
**Dự án:** Trợ lý AI tư vấn học vụ (HocVuAI) – Trường Đại học Lạc Hồng  
**Ngày thực hiện:** 10/11/2026  
**Chế độ kiểm tra:** Đọc và phân tích tĩnh & động (Read-only, không can thiệp sửa/xóa mã nguồn)

---

## I. TỔNG QUAN PHẠM VI VÀ PHƯƠNG PHÁP KIỂM TRA

Đợt kiểm tra đã quét toàn bộ 395 tệp tin dự án (ngoại trừ các thư mục phụ thuộc `.git`, `venv`, `node_modules`, `.pytest_cache`), bao gồm:
1. **Kiểm tra tham chiếu:** Quét toàn bộ mã nguồn Python (`backend/`, `scripts/`), TypeScript/React (`frontend/`), tài liệu Word/PDF/Markdown, kịch bản SQL và file cấu hình để đối chiếu các file, folder, mô hình AI và URL được gọi.
2. **Kiểm tra tính toàn vẹn bên trong file dữ liệu:** Đọc và thống kê tỷ lệ Null/NaN/N/A trên tất cả các sheet của 6 file Excel trong `database/seed_data/`, kiểm tra tính hợp lệ của các file media ảnh/PDF bằng Pillow và pdfplumber.
3. **Kiểm tra phân bổ tập dữ liệu & bộ kiểm thử:** Đánh giá số lượng, độ cân bằng lớp và nguy cơ rò rỉ dữ liệu giữa các bộ câu hỏi kiểm thử (`07_bo_cau_hoi_kiem_thu.xlsx`, `scripts/eval_cases.json`, `backend/scripts/eval_qa.py`).
4. **Kiểm tra tài liệu & Metadata:** Rà soát License, Data Card, biến môi trường `.env`, cấu hình hệ thống so với yêu cầu thực tế của mã nguồn.

---

## II. DANH SÁCH CHI TIẾT CÁC VẤN ĐỀ THEO MỨC ĐỘ

### 1. MỨC ĐỘ: NGHIÊM TRỌNG (Code sẽ lỗi khi chạy)

Các vấn đề dưới đây trực tiếp làm gãy luồng thực thi (crash), gây ngoại lệ runtime (`ValidationError`, `ArgumentError`, `FileNotFoundError`, `404 Not Found`) khi khởi động ứng dụng hoặc chạy pipeline.

#### 1.1. Thiếu biến môi trường bắt buộc `JWT_SECRET` trong `.env`
- **Vị trí:** [`.env`](file:///d:/PTUD/.env#L1) và [`backend/app/config.py:6`](file:///d:/PTUD/backend/app/config.py#L6)
- **Hiện trạng:** Trong class `Settings` (`backend/app/config.py`), biến `JWT_SECRET: str` là trường bắt buộc (không có giá trị mặc định). Tuy nhiên, file `.env` thực tế ở thư mục gốc hoàn toàn KHÔNG có dòng khai báo `JWT_SECRET`.
- **Hậu quả:** Bất kỳ script nào import cấu hình hệ thống (như `from backend.app.config import settings`) hoặc khi khởi động FastAPI Server đều lập tức bị dừng với ngoại lệ:  
  `pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings -> JWT_SECRET: Field required`.
- **Đề xuất xử lý:** Bổ sung ngay vào file `.env`:  
  `JWT_SECRET=your-secret-key-change-in-production`

#### 1.2. Chuỗi kết nối CSDL `DATABASE_URL` trong `.env` bị cắt dở/sai định dạng
- **Vị trí:** [`.env:1`](file:///d:/PTUD/.env#L1) và [`backend/app/db.py:5`](file:///d:/PTUD/backend/app/db.py#L5)
- **Hiện trạng:** Giá trị của `DATABASE_URL` trong `.env` hiện tại chỉ ghi chuỗi dở: `DATABASE_URL=mssql+pyodb2`.
- **Hậu quả:** Khi SQLAlchemy khởi tạo engine (`create_engine(settings.DATABASE_URL)`), hệ thống ném lỗi:  
  `sqlalchemy.exc.ArgumentError: Could not parse SQLAlchemy URL from given URL string`. Backend hoàn toàn không thể kết nối tới cơ sở dữ liệu.
- **Đề xuất xử lý:** Cập nhật lại chuỗi kết nối đầy đủ trong `.env` theo mẫu:  
  `DATABASE_URL=mssql+pyodbc://@localhost/HocVuAI?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes`

#### 1.3. Mô hình Vision OCR `qwen2.5vl:3b` chưa được tải vào Ollama cục bộ
- **Vị trí:** [`backend/app/config.py:17`](file:///d:/PTUD/backend/app/config.py#L17) và [`README.md:192`](file:///d:/PTUD/README.md#L192)
- **Hiện trạng:** Code cấu hình mặc định `OLLAMA_VISION_MODEL = "qwen2.5vl:3b"`. Tuy nhiên, kiểm tra dịch vụ Ollama cục bộ qua API (`http://localhost:11434/api/tags`) cho thấy máy hiện tại chỉ có các model:  
  `['qwen2.5:3b', 'qwen2.5vl:7b', 'qwen2.5:7b', 'bge-m3:latest', 'nomic-embed-text:latest', 'qwen2.5:7b-instruct-q4_0']`.  
  Khi gọi thử model `qwen2.5vl:3b`, Ollama trả về HTTP 404: `{"error":"model 'qwen2.5vl:3b' not found"}`.
- **Hậu quả:** Mọi chức năng upload bảng điểm sinh viên qua OCR thị giác (`POST /transcripts/import` hoặc chat kèm ảnh) sẽ báo lỗi không tìm thấy model.
- **Đề xuất xử lý:** Chạy lệnh `ollama pull qwen2.5vl:3b` trên máy trạm, HOẶC sửa cấu hình biến môi trường trong `.env`:  
  `OLLAMA_VISION_MODEL=qwen2.5vl:7b` (tận dụng model 7b đã có sẵn).

#### 1.4. Đường dẫn file cứng không tồn tại trong script xác minh `scripts/verify_p3_rest.py`
- **Vị trí:** [`scripts/verify_p3_rest.py:38`](file:///d:/PTUD/scripts/verify_p3_rest.py#L38)
- **Hiện trạng:** Code gọi trực tiếp lệnh mở file: `with open("output/input.png", "rb") as f:`. Tuy nhiên, thư mục `output/` thực tế không hề có file `input.png`.
- **Hậu quả:** Chạy script xác minh `verify_p3_rest.py` sẽ gặp lỗi dừng chương trình `FileNotFoundError: [Errno 2] No such file or directory: 'output/input.png'`.
- **Đề xuất xử lý:** Cập nhật script sử dụng ảnh mẫu có sẵn tại [`samples/sample_transcript.png`](file:///d:/PTUD/samples/sample_transcript.png).

#### 1.5. Mất liên kết quan hệ (Orphan Records) giữa 53 môn học CTĐT và bảng CSDL `courses`
- **Vị trí:** [`database/seed.sql:59-83`](file:///d:/PTUD/database/seed.sql#L59-L83) và [`backend/scripts/seed_dataset.py:25-38`](file:///d:/PTUD/backend/scripts/seed_dataset.py#L25-L38)
- **Hiện trạng:**  
  - Trong `database/seed.sql`, bảng `courses` chỉ được nạp sẵn 12 môn học giả lập (tổng 39 tín chỉ).  
  - Trong khi đó, chương trình đào tạo chuẩn [`03_chuong_trinh_dao_tao.xlsx`](file:///d:/PTUD/database/seed_data/03_chuong_trinh_dao_tao.xlsx) có tới 59 môn học (chuẩn 150 tín chỉ).  
  - Khi script `seed_dataset.py` chạy để nạp bảng `program_courses`, chỉ có **6 môn** khớp tên với bảng `courses`.  
  - **53/59 môn còn lại (89.8%)** bị lưu với giá trị `course_id = NULL` trong bảng `program_courses`.
- **Hậu quả:** Tại [`backend/app/routers/students.py:60-66`](file:///d:/PTUD/backend/app/routers/students.py#L60-L66), endpoint kiểm tra tốt nghiệp sinh viên thực hiện truy vấn:  
  `SELECT c.id, c.code, c.name, c.credits FROM program_courses pc JOIN courses c ON pc.course_id = c.id WHERE pc.is_required = 1`.  
  Phép `INNER JOIN` này tự động loại bỏ toàn bộ 53 môn học có `course_id IS NULL`, dẫn đến việc hệ thống không thể phát hiện các môn bắt buộc sinh viên còn thiếu theo chuẩn 150 tín chỉ.
- **Đề xuất xử lý:** Bổ sung script tự động nạp đầy đủ danh mục 59 môn học từ `03_chuong_trinh_dao_tao.xlsx` vào bảng `courses`, sau đó cập nhật lại khóa ngoại `course_id` tương ứng trong `program_courses`.

#### 1.6. Toàn bộ 12 file ảnh giả lập trong `temp_uploads/` bị hỏng (Corrupted Files)
- **Vị trí:** Thư mục [`temp_uploads/`](file:///d:/PTUD/temp_uploads/) và [`temp_uploads/certificates/`](file:///d:/PTUD/temp_uploads/certificates/)
- **Hiện trạng:** Kiểm tra tính toàn vẹn nhị phân phát hiện:
  - 6 file `cert.jpg` (dung lượng 11 bytes): Thực chất là file văn bản chứa chuỗi `"dummy image"`.
  - 6 file `test.png` (dung lượng 19 bytes): Thực chất là file văn bản chứa chuỗi `"dummy image content"`.
- **Hậu quả:** Khi pipeline OpenCV (`cv2.imread`) hoặc thư viện Pillow mở các file này, hệ thống sẽ ném lỗi:  
  `UnidentifiedImageError: cannot identify image file`.
- **Đề xuất xử lý:** Xóa hoặc thay thế các file mock giả bằng các tệp ảnh nhị phân hợp lệ khi chạy test.

---

### 2. MỨC ĐỘ: CẢNH BÁO (Ảnh hưởng chất lượng và độ chính xác học vụ)

Các vấn đề làm sai lệch kết quả tính toán tín chỉ, thiếu hụt dữ liệu đầu vào của hệ thống RAG hoặc giảm độ bao phủ khi kiểm thử.

#### 2.1. Thiếu số tín chỉ (NULL) của 3 môn học tự chọn trong CTĐT
- **Vị trí:** [`database/seed_data/03_chuong_trinh_dao_tao.xlsx`](file:///d:/PTUD/database/seed_data/03_chuong_trinh_dao_tao.xlsx) (Sheet: `mon_hoc`)
- **Hiện trạng:**
  - Dòng 44: *Phân tích thiết kế hệ thống hướng quan hệ* (HK5 - Tự chọn) $\rightarrow$ `tin_chi = NULL` (Ghi chú: nhóm 3 tín chỉ).
  - Dòng 51: *Lập trình Python trong thị giác máy tính* (HK6 - Tự chọn) $\rightarrow$ `tin_chi = NULL` (Ghi chú: nhóm 2 tín chỉ).
  - Dòng 57: *Công nghệ Blockchain* (HK7 - Tự chọn) $\rightarrow$ `tin_chi = NULL` (Ghi chú: nhóm 3 tín chỉ).  
  *(Cùng với 4 môn điều kiện GDQP, GDTC 1, 2, 3 có `tin_chi = NULL` theo quy ước không tính tín chỉ tích lũy).*
- **Hậu quả:** Khi sinh viên tích lũy các môn tự chọn này, hệ thống cộng tổng tín chỉ bằng 0 hoặc bị lỗi `TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'` nếu không xử lý null an toàn.
- **Đề xuất xử lý:** Điền số tín chỉ cụ thể: 3 tín chỉ cho môn dòng 44; 2 tín chỉ cho môn dòng 51; 3 tín chỉ cho môn dòng 57.

#### 2.2. Dữ liệu sinh viên ẩn danh thiếu 100% cột và có tỷ lệ khuyết cực cao
- **Vị trí:** [`database/seed_data/05_sinh_vien_an_danh.xlsx`](file:///d:/PTUD/database/seed_data/05_sinh_vien_an_danh.xlsx) (Sheet: `sinh_vien`, 172 bản ghi)
- **Thống kê giá trị khuyết (Missing Values):**
  - Cột `dieukien_khac`: **172/172 dòng rỗng (100.0% Missing)**.
  - Cột `monhoc_knm`: 169/172 dòng rỗng (98.3% Missing).
  - Cột `monhoc_cb`: 156/172 dòng rỗng (90.7% Missing).
  - Cột `monhoc_cn`: 145/172 dòng rỗng (84.3% Missing).
  - Cột `dieukien_th`: 61/172 dòng rỗng (35.5% Missing).
  - Cột `dieukien_knm`: 51/172 dòng rỗng (29.7% Missing).
  - Cột `dieukien_nn`: 49/172 dòng rỗng (28.5% Missing).
  - Cột `dieukien_tc`: 17/172 dòng rỗng (9.9% Missing).
  - Cột `dieukien_qp`: 13/172 dòng rỗng (7.6% Missing).
- **Hậu quả:** File này hiện tại chưa được tích hợp vào database hay bất kỳ API nào; nếu dùng để phân tích hay huấn luyện sẽ gây sai lệch nghiêm trọng.
- **Đề xuất xử lý:** Khảo sát lại với phòng Đào tạo để chuẩn hóa định dạng và làm rõ quy ước giá trị.

#### 2.3. Dữ liệu lịch học và lịch thi trung tâm NNTH mới chỉ là dữ liệu mẫu (1 dòng)
- **Vị trí:** [`database/seed_data/06_lich_trung_tam.xlsx`](file:///d:/PTUD/database/seed_data/06_lich_trung_tam.xlsx)
- **Hiện trạng:**
  - Sheet `lich_hoc` chỉ có đúng **1 bản ghi** (lớp mẫu).
  - Sheet `lich_thi` chỉ có đúng **1 bản ghi** (kỳ thi mẫu).
- **Hậu quả:** Chatbot không thể trả lời chính xác các câu hỏi của sinh viên về lịch học, lịch thi thực tế của tháng hiện tại nếu chỉ dựa vào file tĩnh này.
- **Đề xuất xử lý:** Kích hoạt cron job chạy module [`backend/services/nnth_sync.py`](file:///d:/PTUD/backend/services/nnth_sync.py) để đồng bộ dữ liệu thời gian thực từ 3 API `tapi.lhu.edu.vn`.

#### 2.4. Số lượng câu hỏi kiểm thử không đạt mục tiêu và mất cân bằng nhóm nghiêm trọng
- **Vị trí:** [`database/seed_data/07_bo_cau_hoi_kiem_thu.xlsx`](file:///d:/PTUD/database/seed_data/07_bo_cau_hoi_kiem_thu.xlsx)
- **Hiện trạng:**
  - Tài liệu [`01_mo_ta_dataset.docx`](file:///d:/PTUD/database/seed_data/01_mo_ta_dataset.docx) đặt mục tiêu **40 câu hỏi**, nhưng file `07_bo_cau_hoi_kiem_thu.xlsx` chỉ có **19 câu hỏi** (đạt 47.5%).
  - Mất cân bằng nhóm: Nhóm *Điều kiện tốt nghiệp* chiếm 9 câu (47.4%), nhóm *Hồ sơ & thủ tục* chiếm 5 câu (26.3%), trong khi nhóm *Ngoài phạm vi (chặn/từ chối)* chỉ có vỏn vẹn **1 câu** (5.3%).
  - Hoàn toàn chưa có câu hỏi kiểm thử về prompt injection, câu hỏi tiếng Việt không dấu, hay câu hỏi trễ hạn đăng ký trong file kiểm thử này.
- **Đề xuất xử lý:** Bổ sung thêm tối thiểu 21 câu hỏi kiểm thử để đạt mốc 40 câu, tập trung vào các trường hợp biên và an toàn hệ thống.

#### 2.5. Nội dung văn bản quy chế bị cắt dở và bỏ trống trong `văn_bản_quy_định.docx`
- **Vị trí:** [`văn_bản_quy_định.docx`](file:///d:/PTUD/văn_bản_quy_định.docx)
- **Hiện trạng:**
  - Đoạn 81: Tên kỹ năng mềm thứ 3 bị cắt ngang câu:  
    `"-Kỹ năng viết CV điện tử và trả"` (mất vế sau của câu).
  - Đoạn 77: Dòng tiêu đề `"Giáo dục thể chất :"` bị để trống hoàn toàn, không có văn bản quy định đi kèm.
  - Đoạn 50: Đề cập `"Bảng quy đổi chứng chỉ ngoại ngữ, tin học tương đương dạng văn bản (nội dung Hình 1 và 2)"` nhưng bên dưới hoàn toàn không có bảng chi tiết.
- **Hậu quả:** Bot RAG không thể trích dẫn đầy đủ tên kỹ năng thứ 3 và phải gắn nhãn cảnh báo TODO.
- **Đề xuất xử lý:** Cập nhật lại bản Word hoàn chỉnh từ văn bản gốc của Trường.

#### 2.6. File mẫu chứng chỉ bị gán nhầm nội dung và sai phần mở rộng file ảnh
- **Vị trí:**  
  - [`temp_uploads/certificates/266aebbc-f7a9-4be3-83a8-8ed6181a6cb1/sample_cert.png`](file:///d:/PTUD/temp_uploads/certificates/266aebbc-f7a9-4be3-83a8-8ed6181a6cb1/sample_cert.png)
  - [`database/seed_data/images/hinh_3_cac_buoc_nop_ho_so.png`](file:///d:/PTUD/database/seed_data/images/hinh_3_cac_buoc_nop_ho_so.png)
- **Hiện trạng:**
  - Mã băm SHA256 của file `sample_cert.png` trùng 100% với `samples/sample_transcript.png` (bị copy nhầm từ ảnh bảng điểm). Dự án hoàn toàn KHÔNG có một ảnh mẫu chứng chỉ thực tế nào (TOEIC, VSTEP, MOS...).
  - File `hinh_3_cac_buoc_nop_ho_so.png` có phần mở rộng `.png` nhưng định dạng nhị phân bên trong là JPEG (`JFIF`).
- **Đề xuất xử lý:** Cung cấp ảnh chứng chỉ mẫu thật cho thư mục test; đổi tên `hinh_3_cac_buoc_nop_ho_so.png` thành `.jpg` hoặc chuyển đổi lại về PNG chuẩn.

#### 2.7. Thiếu dữ liệu chứng chỉ cho các sinh viên mẫu trong `database/seed.sql`
- **Vị trí:** [`database/seed.sql`](file:///d:/PTUD/database/seed.sql)
- **Hiện trạng:** Bảng `student_certificates` đã được tạo trong migration (`database/migration_student_certificates.sql`), nhưng file `seed.sql` không chèn bất kỳ bản ghi chứng chỉ nào cho 3 sinh viên mẫu (`sv01`, `sv02`, `sv03`).
- **Hậu quả:** Khi gọi API kiểm tra tốt nghiệp cho sinh viên mẫu, hệ thống luôn trả về trạng thái thiếu chứng chỉ ngoại ngữ và tin học.
- **Đề xuất xử lý:** Bổ sung dữ liệu chứng chỉ mẫu cho các tài khoản sinh viên thử nghiệm.

---

### 3. MỨC ĐỘ: THÔNG TIN (Thiếu tài liệu, Metadata và chuẩn hóa)

Các mục không làm dừng code nhưng thiếu tính chuyên nghiệp, thiếu khả năng truy vết và chuẩn mực kỹ thuật phần mềm.

#### 3.1. Thiếu file cấu hình môi trường cho Frontend (`frontend/.env`)
- **Vị trí:** [`frontend/src/services/api.ts:3`](file:///d:/PTUD/frontend/src/services/api.ts#L3) và [`frontend/src/components/Modals/ProfileModal.tsx:47`](file:///d:/PTUD/frontend/src/components/Modals/ProfileModal.tsx#L47)
- **Hiện trạng:** Code frontend đọc biến `import.meta.env.VITE_API_BASE_URL`, nhưng trong thư mục `frontend/` không có file `.env` hoặc `.env.example`.
- **Đề xuất:** Tạo file `frontend/.env.example` với nội dung: `VITE_API_BASE_URL=http://localhost:8000`.

#### 3.2. Biến môi trường `STUDENT_PASSWORD` chưa được khai báo trong `.env.example`
- **Vị trí:** [`scripts/set_passwords.py:16`](file:///d:/PTUD/scripts/set_passwords.py#L16) và [`.env.example`](file:///d:/PTUD/.env.example)
- **Hiện trạng:** Script đặt mật khẩu sử dụng `os.getenv("STUDENT_PASSWORD", "...")` nhưng `.env.example` ở thư mục gốc chỉ có `ADMIN_PASSWORD` mà thiếu `STUDENT_PASSWORD`.
- **Đề xuất:** Thêm `STUDENT_PASSWORD=change_me_student` vào `.env.example`.

#### 3.3. Bộ dữ liệu thiếu Data Card, License và Data Dictionary chính thức
- **Vị trí:** Thư mục [`database/seed_data/`](file:///d:/PTUD/database/seed_data/)
- **Hiện trạng:**  
  - Dự án không có file `LICENSE` cho bộ dữ liệu (chưa nêu rõ quyền tác giả, điều kiện trích dẫn hoặc sử dụng nội bộ).  
  - Chưa có file `DATA_CARD.md` chuẩn hóa theo cấu trúc của HuggingFace/MLCommons.  
  - File `05_sinh_vien_an_danh.xlsx` không có bảng mô tả ý nghĩa 13 trường dữ liệu.
- **Đề xuất:** Soạn thảo `DATA_CARD.md` và `LICENSE` trong `database/seed_data/`.

#### 3.4. Thiếu file văn bản gốc độc lập (scan có mộc) của QĐ 1013 và QĐ 22
- **Vị trí:** [`database/seed_data/02b_danh_muc_van_ban.xlsx`](file:///d:/PTUD/database/seed_data/02b_danh_muc_van_ban.xlsx) (Dòng 2 và Dòng 5)
- **Hiện trạng:** Ghi chú trong danh mục văn bản nêu rõ: QĐ 1013/QĐ-ĐHLH "Chưa có văn bản gốc" (chỉ có bản tóm tắt in từ website khoa); QĐ 22/QĐ-ĐHLH "Chưa có văn bản riêng" (phải trích từ trang 80-94 Niên giám).
- **Đề xuất:** Liên hệ Phòng Đào tạo để lưu trữ file PDF quyết định ban hành chính thức có mộc đỏ.

---

### 4. MỤC CẦN XÁC NHẬN (Cần thông tin từ Giáo vụ / Phòng Đào tạo)

Các điểm có sự mâu thuẫn hoặc chưa rõ ràng giữa các nguồn tài liệu và mã nguồn, cần sự xác nhận chính thức từ nhà trường:

1. **Ngưỡng điểm rớt môn và điều kiện thi lại lần 2 (< 4.0 hay < 5.0):**
   - *Văn bản quy chế:* Trong `văn_bản_quy_định.docx` (Điều 27) ghi: *"Tích lũy đủ số học phần quy định cho chương trình, không còn học phần bị điểm dưới 5"*.  
   - *Logic code hiện tại:* [`backend/grade_filter.py`](file:///d:/PTUD/backend/grade_filter.py) đang chia 3 nhánh:  
     - Điểm 0 hoặc cấm thi $\rightarrow$ Học lại.  
     - Điểm $< 4.0$ $\rightarrow$ Thi lại lần 2.  
     - Điểm $4.0 \le \text{điểm} < 5.0$ $\rightarrow$ Nhánh cần giáo vụ xác nhận.  
   - *Cần xác nhận:* Sinh viên đạt từ 4.0 đến 4.9 được thi lại lần 2 hay buộc phải học lại?

2. **Ý nghĩa các giá trị trong cột `dieukien_*` của file sinh viên ẩn danh:**
   - Trong `05_sinh_vien_an_danh.xlsx`, các cột này chỉ có giá trị `1.0` hoặc `NaN`.  
   - *Cần xác nhận:* Giá trị `NaN` là *"Chưa đạt"* hay *"Chưa có dữ liệu xét"*?

3. **Quy định áp dụng đối với các môn có gắn nhãn niên khóa trong CTĐT:**
   - Trong `03_chuong_trinh_dao_tao.xlsx` có các nhãn `{khóa 2022}`, `{khóa 2023}`, `{CNTT 2020}`.  
   - *Cần xác nhận:* Sinh viên các khóa khác có được đăng ký học môn này không, hay chương trình chỉ áp dụng riêng cho từng khóa nhập học cụ thể?

---

## III. BẢNG TỔNG HỢP VẤN ĐỀ

| Mức độ | Số lượng vấn đề | Tác động chính |
| :--- | :---: | :--- |
| **Nghiêm trọng** | **6** | Gây lỗi runtime dừng chương trình (`ValidationError`, `ArgumentError`, `FileNotFoundError`, `404 Not Found`, CSDL rỗng). |
| **Cảnh báo** | **7** | Sai lệch số tín chỉ CTĐT, thiếu hụt dữ liệu RAG, tập kiểm thử chưa đủ quy mô, file giả lập hỏng. |
| **Thông tin** | **4** | Thiếu file mẫu môi trường, thiếu Data Card, thiếu License, chưa có văn bản scan gốc. |
| **Cần xác nhận** | **3** | Mâu thuẫn ngưỡng điểm rớt môn (< 4.0 vs < 5.0), ý nghĩa cột dữ liệu ẩn danh, quy chế niên khóa. |
| **TỔNG CỘNG** | **20** | |

---

## IV. ĐỀ XUẤT 5 VIỆC ƯU TIÊN NÊN XỬ LÝ TRƯỚC

1. **Khắc phục ngay 2 biến môi trường trong file `.env`:**
   - Bổ sung biến bắt buộc `JWT_SECRET` để tránh lỗi Pydantic crash khi khởi động.
   - Sửa chuỗi `DATABASE_URL` bị dở (`mssql+pyodb2`) thành chuỗi kết nối SQL Server chuẩn để backend kết nối được CSDL.
2. **Đồng bộ cấu hình mô hình Vision OCR trong Ollama:**
   - Chạy lệnh `ollama pull qwen2.5vl:3b` trên máy chủ, HOẶC sửa biến môi trường thành `OLLAMA_VISION_MODEL=qwen2.5vl:7b` để khớp với mô hình 7B đã có sẵn trên máy.
3. **Nạp đầy đủ 59 môn học từ `03_chuong_trinh_dao_tao.xlsx` vào bảng CSDL `courses`:**
   - Khắc phục tình trạng 53 môn bị `course_id = NULL` trong `program_courses`, đảm bảo chức năng đối soát tốt nghiệp (`GET /students/me/graduation-check`) tính toán chính xác toàn bộ 150 tín chỉ.
4. **Điền số tín chỉ bị khuyết (NULL) cho 3 môn học tự chọn trong file CTĐT:**
   - Cập nhật số tín chỉ 3 TC cho môn HK5 (dòng 44), 2 TC cho môn HK6 (dòng 51) và 3 TC cho môn HK7 (dòng 57) trong file `03_chuong_trinh_dao_tao.xlsx` để việc tính toán tín chỉ tích lũy không bị thiếu hụt.
5. **Kích hoạt đồng bộ lịch thực tế từ API Trung tâm Ngoại ngữ - Tin học:**
   - Chạy module `backend/services/nnth_sync.py` để nạp dữ liệu lịch học và lịch thi thực tế từ API `tapi.lhu.edu.vn` vào bảng `center_schedules` và `center_exams`, thay thế cho 1 dòng dữ liệu mẫu hiện tại.

