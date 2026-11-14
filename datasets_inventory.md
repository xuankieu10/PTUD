# BẢNG TỔNG HỢP DANH MỤC NGUỒN DỮ LIỆU (DATASETS INVENTORY)
## Dự án: HocVuAI - Trợ lý AI Tư vấn Học vụ & OCR Bảng điểm Sinh viên (ĐH Lạc Hồng)

*Ngày lập kiểm kê:* 09/11/2026  
*Phạm vi quét:* Toàn bộ mã nguồn backend, frontend, database, scripts, tài liệu docs, tests và các cấu hình liên quan.

---

## 1. TỔNG QUAN PHÂN LOẠI NGUỒN DỮ LIỆU

Hệ thống **HocVuAI** vận hành theo kiến trúc kết hợp RAG (Retrieval-Augmented Generation) và OCR thị giác máy tính. Toàn bộ dữ liệu của hệ thống được cấu thành từ **23 nguồn dữ liệu** thuộc 4 nhóm chính:

1. **File dữ liệu hạt giống và kiểm thử cục bộ (Local Seed & Test Files):** 13 nguồn (file Excel, Word, PDF, PNG, JSON).
2. **Nguồn dữ liệu mạng, Crawler & Web API (Web & APIs):** 6 nguồn (website đào tạo LHU, Niên giám, API trung tâm NN-TH).
3. **Trọng số mô hình AI nguồn mở (AI Pretrained Weights Hubs):** 3 mô hình (BGE-M3, Qwen2.5-3B, Qwen2.5-VL-3B).
4. **Cơ sở dữ liệu quan hệ (Relational Database):** 1 hệ quản trị (SQL Server chứa 12 bảng thực thể).

---

## 2. BẢNG DANH MỤC CHI TIẾT CÁC NGUỒN DATASET

| ID | Tên Dataset / Nguồn dữ liệu | Loại / Định dạng | Đường dẫn / URL gốc | File & Dòng code sử dụng | Mục đích sử dụng | Kích thước | Bản quyền / License |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DS01** | Đặc tả Bộ dữ liệu Học vụ AI | DOCX | `database/seed_data/01_mo_ta_dataset.docx` | `01_mo_ta_dataset.docx` | Đặc tả cấu trúc, nguồn gốc, quy tắc bảo mật dữ liệu | 13.6 KB | Nội bộ ĐH Lạc Hồng (Khoa CNTT) |
| **DS02** | Văn bản Quy định Xét tốt nghiệp PDF | PDF | `database/seed_data/02_van_ban_quy_dinh.pdf` | `02b_danh_muc_van_ban.xlsx:L2`, `documents.py` | Bản in lưu trữ làm căn cứ kiểm chứng quy định tốt nghiệp | 560.4 KB (4 trang) | Công khai nội bộ ĐH Lạc Hồng |
| **DS03** | Danh mục Văn bản Học vụ | Excel (XLSX) | `database/seed_data/02b_danh_muc_van_ban.xlsx` | `seed_dataset.py:L142` (`seed_documents_catalog`) | Seed danh mục văn bản vào bảng `documents` | 6.6 KB (8 dòng) | Nội bộ ĐH Lạc Hồng |
| **DS04** | Khung Chương trình Đào tạo CNTT 150 tín chỉ | Excel (XLSX) | `database/seed_data/03_chuong_trinh_dao_tao.xlsx` (Nguồn: `lhu.edu.vn`) | `seed_dataset.py:L31` (`seed_program_courses`), `L387` | Seed môn học 8 học kỳ và tạo chunk tri thức RAG CTĐT | 13.1 KB (3 sheets) | Công khai (ĐH Lạc Hồng) |
| **DS05** | Điều kiện Tốt nghiệp & Chứng chỉ Tương đương | Excel (XLSX) | `database/seed_data/04_dieu_kien_tot_nghiep.xlsx` (Nguồn: `cs.lhu.edu.vn`) | `seed_dataset.py:L78`, `L210`, `certificate_matcher.py` | Seed 11 điều kiện, 18 chuẩn chứng chỉ tương đương, 10 hồ sơ | 13.9 KB (6 sheets) | Công khai (Khoa CNTT - LHU) |
| **DS06** | Dữ liệu Sinh viên Ẩn danh (5 lớp 22CT111–22CT115) | Excel (XLSX) | `database/seed_data/05_sinh_vien_an_danh.xlsx` | `seed_dataset.py`, `schema.sql` (bảng `students`) | Dữ liệu kiểm thử hồ sơ học tập và tư vấn học vụ cá nhân | 16.5 KB (173 dòng) | Ẩn danh nội bộ (Bảo mật PII) |
| **DS07** | Lịch Mẫu Trung tâm Ngoại ngữ - Tin học | Excel (XLSX) | `database/seed_data/06_lich_trung_tam.xlsx` (Nguồn: `nnth.lhu.edu.vn`) | `nnth_sync.py:L1-L25`, `center.py` | Dữ liệu mẫu ban đầu về lịch học/lịch thi và đặc tả API | 11.7 KB (3 sheets) | Công khai (Trung tâm NN-TH LHU) |
| **DS08** | Bộ Câu hỏi Kiểm thử Chuẩn Ground-Truth | Excel (XLSX) | `database/seed_data/07_bo_cau_hoi_kiem_thu.xlsx` | `eval_qa.py:L89` (`load_all_questions`), `test_graduation_and_chat_ocr.py` | Benchmark kiểm thử độ chính xác truy xuất RAG và Chatbot | 8.8 KB (20 dòng) | Bản quyền nhóm tác giả 23CT111 |
| **DS09** | Toàn văn Quy chế Đào tạo Tín chỉ (QĐ 22/QĐ-ĐHLH) | DOCX | `database/seed_data/văn bản quy định.docx` (Trích Niên giám 2023) | `ingest_quy_dinh.py:L31` (`parse_docx_chunks`), `L120` | Nạp cơ sở tri thức chống ảo giác vào bảng `document_chunks` | 368.3 KB | Quyết định Trường ĐH Lạc Hồng |
| **DS10** | Bộ ảnh Biểu đồ Chuẩn Chứng chỉ & Thủ tục | PNG Images | `database/seed_data/images/` (`hinh_1`, `hinh_2`, `hinh_3`) | `chat.py:L1400-L1480`, `MessageItem.tsx` | Trả về hình ảnh trực quan chứng chỉ tương đương trong chat | 444.9 KB (3 ảnh) | Khoa CNTT - ĐH Lạc Hồng |
| **DS11** | Bảng điểm Mẫu Kiểm thử OCR | PNG & PDF | `samples/sample_transcript.png`, `sample_transcript_scan.pdf` | `test_ocr_parser.py:L15`, `test_pdf_processor.py:L20` | Unit test pipeline OCR bảng điểm, phát hiện môn rớt chữ đỏ | 75.5 KB (2 files) | Mock test data (Không có PII) |
| **DS12** | Bộ Test Cases Đánh giá RAG | JSON | `scripts/eval_cases.json` | `eval_rag.py:L52-L65` | Đánh giá độ chính xác và khả năng từ chối câu ngoài luồng | 2.1 KB (12 cases) | Nhóm tác giả đề tài |
| **DS13** | Cấu hình Danh mục Nguồn Tri thức | JSON | `backend/app/config/sources.json` | `chat.py:L45` | Cấu hình whitelist URL tin cậy và blacklist từ khóa | 555 bytes | Nội bộ dự án |
| **DS14** | Cổng Xét Tốt nghiệp Trực tuyến LHU | Web Portal | `https://graduate.lhu.edu.vn/` | `crawler.py:L15` (`crawl_page`), `seed_dataset.py` | Thu thập quy trình, thời hạn nộp hồ sơ tốt nghiệp | Động (HTML) | Bản quyền Trường ĐH Lạc Hồng |
| **DS15** | Trang Quy định Tốt nghiệp Khoa CNTT | Web Article | `https://cs.lhu.edu.vn/724/44104/Dieu-kien-Thu-tuc-quy-trinh-xet-cap-bang-Tot-nghiep-Dai-hoc.html` | `02b_danh_muc_van_ban.xlsx:L2`, `seed_dataset.py` | Nguồn gốc 11 điều kiện xét tốt nghiệp và bảng quy đổi | ~4 trang web A4 | Bản quyền Khoa CNTT - LHU |
| **DS16** | Trang CTĐT Ngành CNTT LHU | Web Article | `https://lhu.edu.vn/106/45268/Cong-nghe-thong-tin.html` | `02b_danh_muc_van_ban.xlsx:L4`, `seed_dataset.py:L35` | Nguồn đối soát danh mục 150 tín chỉ toàn khóa | 1 trang web A4 | Bản quyền Trường ĐH Lạc Hồng |
| **DS17** | Niên giám Sinh viên & File Quy chế PDF | Web / PDF | `https://sinhviendanghoc.lhu.edu.vn/483/Nien-giam.html` và file PDF Niên giám 2023 | `crawler.py:L86`, `ingest_quy_dinh.py:L15` | Nguồn gốc Quyết định 22/QĐ-ĐHLH (trang 80–94 Niên giám 2023) | PDF gốc ~15MB | Bản quyền Trường ĐH Lạc Hồng |
| **DS18** | API Lịch Khai giảng Trung tâm NN-TH | JSON REST API | `https://tapi.lhu.edu.vn//NNTH/AUTH/LichKhaiGiang_Select` | `nnth_sync.py:L40` (`API_LICH_KHAI_GIANG`), `center.py` | Đồng bộ tự động lịch khai giảng khóa học VSTEP, TOEIC | Động (JSON) | Trung tâm NN-TH LHU (Không ghi license mở) |
| **DS19** | API Lịch Thi Chứng chỉ Trung tâm NN-TH | JSON REST API | `https://tapi.lhu.edu.vn//NNTH/AUTH/LichThi_Thang_Nam` và `LichThiDuKien_Thang_Nam` | `nnth_sync.py:L41-L42` (`API_LICH_THI`), `center.py` | Đồng bộ tự động các kỳ thi chứng chỉ ngoại ngữ, tin học | Động (JSON) | Trung tâm NN-TH LHU (Không ghi license mở) |
| **DS20** | Trọng số Nhúng BGE-M3 (BAAI FlagEmbedding) | Pretrained Model | Ollama: `bge-m3` / HuggingFace: `BAAI/bge-m3` | `embedding.py:L11`, `config.py:L9` (`EMBEDDING_MODEL`) | Biểu diễn vector 1024 chiều phục vụ tìm kiếm ngữ nghĩa RAG | ~2.2 GB | Apache-2.0 |
| **DS21** | Mô hình Ngôn ngữ Qwen2.5-3B Instruct | Pretrained LLM | Ollama: `qwen2.5:3b` / HuggingFace: `Qwen/Qwen2.5-3B-Instruct` | `chat.py:L1667`, `config.py:L10` (`LLM_MODEL`) | Sinh câu trả lời tư vấn học vụ từ context tài liệu | ~1.9 GB | Apache-2.0 |
| **DS22** | Mô hình Thị giác Qwen2.5-VL-3B Instruct | Pretrained Vision | Ollama: `qwen2.5vl:3b` / HuggingFace: `Qwen/Qwen2.5-VL-3B-Instruct` | `ocr_extractor.py:L23`, `pdf_processor.py`, `config.py:L17` | OCR bảng điểm, phát hiện môn rớt và trích xuất chứng chỉ | ~1.9 GB | Apache-2.0 |
| **DS23** | Database Quan hệ SQL Server (HocVuAI) | RDBMS | `mssql+pyodbc://.../HocVuAI` (qua `DATABASE_URL`) | `db.py:L5-L15`, `schema.sql`, `migration_*.sql` | Lưu trữ sinh viên, điểm, điều kiện, chứng chỉ, chunk RAG, chat | CSDL cục bộ | Bản quyền nội bộ dự án |

---

## 3. CHI TIẾT SỬ DỤNG VÀ DÒNG CODE THAM CHIẾU

### 3.1. Dữ liệu Hạt giống (Seed Data) & Vector Tri thức RAG
- `database/seed_data/03_chuong_trinh_dao_tao.xlsx`: Được nạp trong script `backend/scripts/seed_dataset.py` (hàm `seed_program_courses` tại dòng 31) qua thư viện `openpyxl`. Nạp các bảng `courses`, `program_courses`. Đồng thời hàm `build_knowledge_base_chunks()` tại dòng 387 tổng hợp thành các đoạn văn bản tri thức nạp vào `knowledge_base_chunks`.
- `database/seed_data/04_dieu_kien_tot_nghiep.xlsx`: Được nạp tại dòng 78 (`seed_graduation_conditions`), đọc 11 điều kiện nạp vào bảng `graduation_conditions`. Dòng 210 đọc các sheet `chung_chi_tuong_duong`, `ho_so_nop`, `quy_trinh_online` và `lien_he` để tạo vector chunk.
- `database/seed_data/văn bản quy định.docx`: Được đọc trong script `backend/scripts/ingest_quy_dinh.py` (hàm `parse_docx_chunks` tại dòng 31) bằng `python-docx`. Tự động phân tách từng Điều/Khoản trong QĐ 22/QĐ-ĐHLH, nhúng vector bằng `bge-m3` và nạp vào bảng `document_chunks`.

### 3.2. Dữ liệu Động từ Web và API Trung tâm NN-TH
- `backend/services/nnth_sync.py`: Định nghĩa 3 endpoint API động:
  - `API_LICH_KHAI_GIANG = "https://tapi.lhu.edu.vn//NNTH/AUTH/LichKhaiGiang_Select"` (dòng 40)
  - `API_LICH_THI = "https://tapi.lhu.edu.vn//NNTH/AUTH/LichThi_Thang_Nam"` (dòng 41)
  - `API_LICH_THI_DU_KIEN = "https://tapi.lhu.edu.vn//NNTH/AUTH/LichThiDuKien_Thang_Nam"` (dòng 42)
  Dữ liệu trả về qua phương thức POST (JSON payload), được phân loại tự động thành môn Tin học hay Ngoại ngữ qua regex và lưu vào `center_schedules`, `center_exams`.
- `backend/app/services/crawler.py`: Hàm `crawl_page()` tại dòng 15 quét nội dung các trang web trường và tự động tải các file đính kèm PDF vào `tmp_downloads/` để phân tích nội dung.

### 3.3. Dữ liệu Kiểm thử (Test Benchmarks)
- `database/seed_data/07_bo_cau_hoi_kiem_thu.xlsx`: 20 câu hỏi đánh giá chất lượng chatbot. Được tải trong `backend/scripts/eval_qa.py` (hàm `load_all_questions()` tại dòng 89).
- `samples/sample_transcript.png` & `sample_transcript_scan.pdf`: Bảng điểm mẫu thực tế được dùng trong bộ kiểm thử pytest (`test_ocr_parser.py`, `test_pdf_processor.py`) để kiểm tra tính năng phát hiện môn điểm F chữ đỏ và trích xuất bảng điểm.

---

## 4. TỔNG KẾT & DANH SÁCH NGUỒN CẦN LƯU Ý

### 4.1. Thống kê
- **Tổng số nguồn dữ liệu ghi nhận:** **23 nguồn**.
- **Nguồn có license nguồn mở rõ ràng:** 3 nguồn (Các mô hình AI `bge-m3`, `qwen2.5:3b`, `qwen2.5vl:3b` thuộc giấy phép **Apache-2.0**).
- **Nguồn bản quyền chính thức thuộc Nhà trường / Khoa:** 14 nguồn (các văn bản quy chế, biểu mẫu, website chính thức của ĐH Lạc Hồng).
- **Nguồn tự xây dựng / Synthetic test data:** 6 nguồn (bộ câu hỏi kiểm thử 07, eval_cases.json, bảng điểm test samples, sources.json, schema SQL).

### 4.2. Các nguồn thiếu thông tin (Cần lưu ý về License / Văn bản gốc)
1. **Quyết định 1013/QĐ-ĐHLH ngày 09/10/2023:**
   - Được trích dẫn làm căn cứ trong `02b_danh_muc_van_ban.xlsx` và trang web Khoa CNTT, nhưng trong mã nguồn hiện chưa có file văn bản gốc trực tiếp (chỉ có bản trích nội dung trên trang web). Cần bổ sung file toàn văn khi phòng Đào tạo cấp.
2. **Các API Lịch thi / Lịch học (`tapi.lhu.edu.vn`):**
   - Không có tài liệu mô tả License mở (Open API License). Đây là endpoint API nội bộ của Trung tâm Ngoại ngữ - Tin học Trường ĐH Lạc Hồng, hệ thống đang gọi với Header `Origin: https://nnth.lhu.edu.vn` phục vụ học tập/nghiên cứu.
3. **Dữ liệu sinh viên ẩn danh (`05_sinh_vien_an_danh.xlsx`):**
   - Được lấy từ dữ liệu sinh viên thật của 5 lớp 22CT111–22CT115 nhưng đã được nhóm thực hiện ẩn danh hóa hoàn toàn (thay bằng mã giả `SV0001`–`SV0172`, bỏ toàn bộ họ tên, ngày sinh). Dữ liệu này không có license công khai và phải được giữ bảo mật theo quy định bảo vệ dữ liệu cá nhân.

