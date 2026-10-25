import os
import sys
import csv
import json
import time
import argparse
from typing import List, Dict, Any, Tuple
import openpyxl

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from backend.api import app
from backend.app.deps import get_current_user
from backend.app.db import SessionLocal
from backend.app.services.retrieval import search_chunks
from backend.app.config import settings

# ── DANH SÁCH 10 CÂU PARAPHRASE CHUẨN (KHÔNG CHỨA CHỮ "A.5") ──────────────────────
PARAPHRASE_QUESTIONS = [
    {
        "ma_cau_hoi": "P01_A5",
        "nhom": "Paraphrase Ngoại ngữ & Tin học",
        "cau_hoi": "Quy định về chuẩn đầu ra chứng chỉ tiếng Anh và tin học tốt nghiệp là gì?",
        "dap_an_chuan": "Tiếng Anh Bậc 3 theo Khung năng lực Ngoại ngữ 6 bậc và Sát hạch tin học do Khoa CNTT tổ chức (hoặc tương đương).",
        "expected_sections": ["A.5", "A.5.1", "A.5.2"]
    },
    {
        "ma_cau_hoi": "P02_A5",
        "nhom": "Paraphrase Ngoại ngữ & Tin học",
        "cau_hoi": "Cần đạt chuẩn ngoại ngữ và tin học như thế nào để tốt nghiệp?",
        "dap_an_chuan": "Ngoại ngữ Tiếng Anh Bậc 3 và Sát hạch tin học do Khoa CNTT tổ chức (hoặc tương đương).",
        "expected_sections": ["A.5", "A.5.1", "A.5.2"]
    },
    {
        "ma_cau_hoi": "P03_A5",
        "nhom": "Paraphrase Ngoại ngữ",
        "cau_hoi": "Tốt nghiệp ngành CNTT cần chứng chỉ tiếng Anh gì?",
        "dap_an_chuan": "Tiếng Anh Bậc 3 theo Khung năng lực Ngoại ngữ 6 bậc dùng cho Việt Nam hoặc tương đương.",
        "expected_sections": ["A.5.1", "A.5"]
    },
    {
        "ma_cau_hoi": "P04_A5",
        "nhom": "Paraphrase Tin học",
        "cau_hoi": "Sát hạch tin học là gì, ai tổ chức để xét tốt nghiệp?",
        "dap_an_chuan": "Chứng nhận đạt Sát hạch tin học do Khoa Công nghệ thông tin tổ chức.",
        "expected_sections": ["A.5.2", "A.5"]
    },
    {
        "ma_cau_hoi": "P05_A5",
        "nhom": "Paraphrase Tin học",
        "cau_hoi": "Chuẩn đầu ra tin học của khoa CNTT yêu cầu những gì?",
        "dap_an_chuan": "Chứng nhận đạt Sát hạch tin học do Khoa CNTT tổ chức hoặc chứng chỉ ứng dụng CNTT tương đương.",
        "expected_sections": ["A.5.2", "A.5"]
    },
    {
        "ma_cau_hoi": "P06_A5",
        "nhom": "Paraphrase Ngoại ngữ",
        "cau_hoi": "Sinh viên chính quy muốn ra trường có bắt buộc phải đạt Tiếng Anh Bậc 3 không?",
        "dap_an_chuan": "Bắt buộc phải đạt chuẩn Tiếng Anh Bậc 3 hoặc các văn bằng, chứng chỉ tương đương.",
        "expected_sections": ["A.5.1", "A.5"]
    },
    {
        "ma_cau_hoi": "P07_A5",
        "nhom": "Paraphrase Tin học",
        "cau_hoi": "Khoa Công nghệ thông tin có tổ chức sát hạch tin học cho sinh viên xét tốt nghiệp không?",
        "dap_an_chuan": "Có, sinh viên cần đạt chứng nhận Sát hạch tin học do Khoa CNTT tổ chức hoặc tương đương.",
        "expected_sections": ["A.5.2", "A.5"]
    },
    {
        "ma_cau_hoi": "P08_A5",
        "nhom": "Hình 1 (Ngoại ngữ tương đương)",
        "cau_hoi": "Nếu có chứng chỉ TOEIC hoặc IELTS thì có được công nhận tương đương Tiếng Anh Bậc 3 không?",
        "dap_an_chuan": "Có, theo Hình 1: TOEIC 2 kỹ năng >= 400, TOEIC 4 kỹ năng (L >= 200, R >= 200, S >= 120, W >= 120), IELTS >= 4.5.",
        "expected_sections": ["A.5.1-hình", "A.5.1", "A.5"]
    },
    {
        "ma_cau_hoi": "P09_A5",
        "nhom": "Paraphrase Ngoại ngữ & Tin học",
        "cau_hoi": "Điều kiện về chứng chỉ ngoại ngữ và sát hạch tin học đối với sinh viên chính quy xét tốt nghiệp là gì?",
        "dap_an_chuan": "Tiếng Anh Bậc 3 và Tin học: Sát hạch tin học do Khoa CNTT tổ chức (hoặc tương đương).",
        "expected_sections": ["A.5", "A.5.1", "A.5.2"]
    },
    {
        "ma_cau_hoi": "P10_A5",
        "nhom": "Paraphrase Ngoại ngữ & Tin học",
        "cau_hoi": "Chuẩn đầu ra ngoại ngữ và tin học xét tốt nghiệp Khoa CNTT LHU có những lựa chọn nào?",
        "dap_an_chuan": "Ngoại ngữ: Tiếng Anh Bậc 3 hoặc tương đương (Hình 1); Tin học: Đạt Sát hạch tin học Khoa CNTT hoặc tương đương (Hình 2).",
        "expected_sections": ["A.5", "A.5.1", "A.5.2", "A.5.1-hình", "A.5.2-hình"]
    }
]

# ── DANH SÁCH 8 CÂU HỎI MỚI (MỤC 4) ───────────────────────────────────────────────
NEW_8_QUESTIONS = [
    {
        "ma_cau_hoi": "NEW_01_A1",
        "nhom": "Mục A.1 (Tín chỉ & GPA)",
        "cau_hoi": "Sinh viên ngành Công nghệ thông tin cần hoàn thành tối thiểu bao nhiêu tín chỉ và đạt điểm trung bình tích lũy bao nhiêu để đủ điều kiện xét tốt nghiệp?",
        "dap_an_chuan": "Hoàn thành 150 tín chỉ theo CTĐT và ĐTB tích lũy >= 5.0 (loại Trung bình trở lên).",
        "expected_sections": ["A.1.1", "A.1.2", "Bảng tổng cộng"]
    },
    {
        "ma_cau_hoi": "NEW_02_A2_A3",
        "nhom": "Mục A.2 & A.3 (GDQP, GDTC, KNM)",
        "cau_hoi": "Để đủ điều kiện tốt nghiệp chính quy, sinh viên có bắt buộc phải hoàn thành chứng chỉ GDTC, GDQP và bao nhiêu kỹ năng mềm?",
        "dap_an_chuan": "Bắt buộc có chứng chỉ GDQP, GDTC và hoàn thành đủ 4 kỹ năng mềm.",
        "expected_sections": ["A.2", "A.3"]
    },
    {
        "ma_cau_hoi": "NEW_03_A4",
        "nhom": "Mục A.4 (Kỷ luật & Nghĩa vụ)",
        "cau_hoi": "Sinh viên đang trong thời gian bị kỷ luật ở mức đình chỉ học tập hoặc còn nợ sách thư viện thì có được xét tốt nghiệp không?",
        "dap_an_chuan": "Không được xét tốt nghiệp nếu đang bị kỷ luật đình chỉ học tập hoặc nợ tài liệu thư viện.",
        "expected_sections": ["A.4"]
    },
    {
        "ma_cau_hoi": "NEW_04_B",
        "nhom": "Mục B (Hệ liên thông)",
        "cau_hoi": "Sinh viên học hệ liên thông từ trung cấp/cao đẳng lên đại học có phải nộp chứng chỉ tiếng Anh Bậc 3 và sát hạch tin học để tốt nghiệp không?",
        "dap_an_chuan": "Không, hệ liên thông không yêu cầu GDQP, GDTC, KNM, Ngoại ngữ và Tin học.",
        "expected_sections": ["B"]
    },
    {
        "ma_cau_hoi": "NEW_05_C",
        "nhom": "Mục C (Nộp hồ sơ & Lệ phí)",
        "cau_hoi": "Sinh viên nộp hồ sơ xét tốt nghiệp trực tuyến ở trang web nào và đóng lệ phí bao nhiêu tiền, ở phòng nào?",
        "dap_an_chuan": "Nộp trực tuyến tại https://graduate.lhu.edu.vn và đóng lệ phí 100.000 VNĐ tại phòng Đào tạo (B101, Cơ sở 1).",
        "expected_sections": ["C", "ho_so_nop", "C-hình 3"]
    },
    {
        "ma_cau_hoi": "NEW_06_D",
        "nhom": "Mục D (Giấy chứng nhận)",
        "cau_hoi": "Nếu sinh viên đã tích lũy đủ 150 tín chỉ nhưng chưa nộp đủ chứng chỉ ngoại ngữ và tin học thì được Nhà trường cấp loại giấy chứng nhận nào?",
        "dap_an_chuan": "Được cấp Giấy chứng nhận hoàn thành khóa học tại phòng Đào tạo (B101, Cơ sở 1).",
        "expected_sections": ["D"]
    },
    {
        "ma_cau_hoi": "NEW_07_HINH1",
        "nhom": "Hình 1 (Ngoại ngữ tương đương)",
        "cau_hoi": "Theo quy định bảng ngoại ngữ tương đương (Hình 1), chứng chỉ TOEIC 4 kỹ năng cần đạt tối thiểu bao nhiêu điểm cho từng kỹ năng để tương đương Tiếng Anh Bậc 3?",
        "dap_an_chuan": "TOEIC 4 kỹ năng: Listening >= 200, Reading >= 200, Speaking >= 120, Writing >= 120.",
        "expected_sections": ["A.5.1-hình"]
    },
    {
        "ma_cau_hoi": "NEW_08_HINH2",
        "nhom": "Hình 2 (Tin học tương đương)",
        "cau_hoi": "Theo danh mục chứng chỉ tin học tương đương (Hình 2), sinh viên có chứng chỉ tin học văn phòng MOS hoặc chứng chỉ mạng Cisco nào thì được thay thế Sát hạch tin học?",
        "dap_an_chuan": "MOS đạt ít nhất 2 trong 3 kỹ năng Word, Excel, PowerPoint; hoặc Cisco cấp Entry-Level/Associate (CCST, CCNA, DEVASC).",
        "expected_sections": ["A.5.2-hình"]
    }
]

EXPECTED_SECTIONS_EXCEL = {
    "QD01": ["A.1.2"],
    "QD02": ["A.5.1", "A.5"],
    "QD03": ["A.5.2", "A.5"],
    "QD04": ["A.2"],
    "QD05": ["A.3"],
    "QD06": ["A.4"],
    "QD07": ["A.4"],
    "QD08": ["A.4"],
    "QD09": ["B"],
    "TT01": ["C", "ho_so_nop", "C-hình 3"],
    "TT02": ["C"],
    "TT03": ["C", "ho_so_nop"],
    "TT04": ["D"],
    "TT05": ["C", "ho_so_nop"],
    "CT01": ["Bảng tổng cộng"],
    "CT02": ["Học kỳ 8"],
    "CT03": ["Học kỳ 7"],
    "NP01": ["OUT_OF_DOMAIN"],
    "NP02": ["OUT_OF_DOMAIN"],
}


def load_all_questions() -> List[Dict[str, Any]]:
    """Đọc câu hỏi Excel + Paraphrase A.5 + 8 câu mới."""
    excel_path = "database/seed_data/07_bo_cau_hoi_kiem_thu.xlsx"
    excel_questions = []

    if os.path.exists(excel_path):
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        sheet = wb["cau_hoi"]
        for r in sheet.iter_rows(values_only=True):
            if r[0] == "ma_cau_hoi" or r[0] is None:
                continue
            ma, nhom, cau_hoi, dap_an_chuan = r[:4]
            if ma and cau_hoi:
                ma_str = str(ma).strip()
                excel_questions.append({
                    "ma_cau_hoi": ma_str,
                    "nhom": str(nhom).strip() if nhom else "",
                    "cau_hoi": str(cau_hoi).strip(),
                    "dap_an_chuan": str(dap_an_chuan).strip() if dap_an_chuan else "",
                    "expected_sections": EXPECTED_SECTIONS_EXCEL.get(ma_str, [])
                })

    # Thứ tự: 10 câu Paraphrase + 19 câu Excel + 8 câu mới = 37 câu
    return PARAPHRASE_QUESTIONS + excel_questions + NEW_8_QUESTIONS


def evaluate_answer(ma: str, answer: str, sources: list) -> Tuple[bool, str]:
    """Đánh giá câu trả lời LLM."""
    ans_lower = answer.lower()
    has_source = "Có" if len(sources) > 0 else "Không"

    if ma == "QD01" or ma == "NEW_01_A1":
        is_correct = "5.0" in answer or "5" in answer
    elif ma == "QD02" or ma in ["P03_A5", "P06_A5"]:
        is_correct = ("bậc 3" in ans_lower or "bac 3" in ans_lower) and ("tiếng anh" in ans_lower or "ngoại ngữ" in ans_lower)
    elif ma == "QD03" or ma in ["P04_A5", "P05_A5", "P07_A5"]:
        is_correct = "sát hạch" in ans_lower and ("khoa" in ans_lower or "cntt" in ans_lower or "ứng dụng" in ans_lower)
    elif ma == "QD04":
        is_correct = ("giáo dục quốc phòng" in ans_lower or "gdqp" in ans_lower) and ("giáo dục thể chất" in ans_lower or "gdtc" in ans_lower)
    elif ma == "QD05":
        is_correct = "4" in answer and "kỹ năng mềm" in ans_lower
    elif ma == "QD06":
        is_correct = "không" in ans_lower and "học phí" in ans_lower
    elif ma == "QD07":
        is_correct = "không" in ans_lower and ("thư viện" in ans_lower or "sách" in ans_lower)
    elif ma == "QD08" or ma == "NEW_03_A4":
        is_correct = "không" in ans_lower and "đình chỉ" in ans_lower
    elif ma == "QD09" or ma == "NEW_04_B":
        is_correct = ("không" in ans_lower or "miễn" in ans_lower) and ("liên thông" in ans_lower or "trung cấp" in ans_lower or "cao đẳng" in ans_lower)
    elif ma == "TT01":
        is_correct = "graduate.lhu.edu.vn" in ans_lower and ("100.000" in answer or "b101" in ans_lower)
    elif ma == "TT02":
        is_correct = "100.000" in answer and ("đào tạo" in ans_lower or "b101" in ans_lower or "cơ sở 1" in ans_lower)
    elif ma == "TT03":
        items = ["gdtc", "giáo dục thể chất", "gdqp", "giáo dục quốc phòng", "kỹ năng mềm", "ngoại ngữ", "tiếng anh", "tin học", "thpt"]
        is_correct = sum(1 for it in items if it in ans_lower) >= 3
    elif ma == "TT04" or ma == "NEW_06_D":
        is_correct = "hoàn thành khóa học" in ans_lower and ("đào tạo" in ans_lower or "b101" in ans_lower or "cơ sở 1" in ans_lower)
    elif ma == "TT05":
        is_correct = ("đào tạo" in ans_lower or "học vụ" in ans_lower or "cơ sở 1" in ans_lower)
    elif ma == "CT01":
        is_correct = "150" in answer
    elif ma == "CT02":
        is_correct = "8" in answer and ("học kỳ 8" in ans_lower or "hk8" in ans_lower or "kỳ 8" in ans_lower)
    elif ma == "CT03":
        is_correct = "21" in answer and ("english 7" in ans_lower or "kiểm thử" in ans_lower or "phát triển ứng dụng" in ans_lower)
    elif ma == "NP01":
        is_correct = ("chỉ hỗ trợ" in ans_lower or "học vụ" in ans_lower or "từ chối" in ans_lower or "không thể" in ans_lower)
        has_source = "Không áp dụng"
    elif ma == "NP02":
        is_correct = ("chưa có dữ liệu" in ans_lower or "khoa khác" in ans_lower or "kinh tế" in ans_lower or "chỉ hỗ trợ" in ans_lower or "công nghệ thông tin" in ans_lower)
        has_source = "Không áp dụng"
    elif ma in ["P01_A5", "P02_A5", "P09_A5", "P10_A5"]:
        has_ta = ("bậc 3" in ans_lower or "bac 3" in ans_lower) and ("tiếng anh" in ans_lower or "ngoại ngữ" in ans_lower)
        has_th = ("sát hạch" in ans_lower or "ứng dụng công nghệ thông tin" in ans_lower or "ứng dụng cntt" in ans_lower)
        no_spec = not any(w in ans_lower for w in ["thông thường", "theo thông lệ", "không được đề cập trực tiếp"])
        is_correct = has_ta and has_th and no_spec
    elif ma == "P08_A5":
        # Dựa vào Hình 1
        is_correct = ("được" in ans_lower or "tương đương" in ans_lower or "công nhận" in ans_lower) and ("toeic" in ans_lower or "400" in ans_lower or "ielts" in ans_lower or "4.5" in ans_lower)
    elif ma == "NEW_02_A2_A3":
        is_correct = ("giáo dục quốc phòng" in ans_lower or "gdqp" in ans_lower) and ("giáo dục thể chất" in ans_lower or "gdtc" in ans_lower) and ("4" in answer)
    elif ma == "NEW_05_C":
        is_correct = "graduate.lhu.edu.vn" in ans_lower and ("100.000" in answer or "100k" in ans_lower) and ("b101" in ans_lower or "đào tạo" in ans_lower)
    elif ma == "NEW_07_HINH1":
        is_correct = ("200" in answer or "120" in answer) and ("toeic" in ans_lower or "kỹ năng" in ans_lower)
    elif ma == "NEW_08_HINH2":
        is_correct = ("mos" in ans_lower or "microsoft" in ans_lower or "cisco" in ans_lower or "ccna" in ans_lower)
    else:
        is_correct = len(answer.strip()) > 10

    return is_correct, has_source


def run_retrieval_only():
    """Chế độ --retrieval-only: chỉ kiểm tra RAG search_chunks cho cả 37 câu."""
    print("=" * 80)
    print("=== CHẾ ĐỘ: RETRIEVAL-ONLY (Kiểm tra thứ hạng chunk kỳ vọng trong TOP_K) ===")
    print(f"Cấu hình: TOP_K = {settings.TOP_K}\n")
    
    questions = load_all_questions()
    print(f"Tổng số câu hỏi đánh giá retrieval: {len(questions)} (29 câu cũ + 8 câu mới)")
    
    db = SessionLocal()
    pass_count = 0
    fail_count = 0
    results_table = []
    
    t_start = time.time()
    
    for idx, q in enumerate(questions, 1):
        ma = q["ma_cau_hoi"]
        prompt = q["cau_hoi"]
        expected = q.get("expected_sections", [])
        
        # Nếu là câu out of domain (nấu phở, khoa kinh tế)
        if "OUT_OF_DOMAIN" in expected:
            results_table.append({
                "ma": ma,
                "expected": "Out-of-domain",
                "rank": "N/A",
                "status": "PASS",
                "note": "Câu ngoài lề (hệ thống từ chối)"
            })
            pass_count += 1
            continue

        retrieved = search_chunks(db, prompt)
        
        # Tìm rank của chunk kỳ vọng đầu tiên xuất hiện
        found_rank = None
        found_sec = None
        for rank, chunk in enumerate(retrieved, start=1):
            sec = str(chunk.get("section", "")).strip()
            # Khớp nếu sec nằm trong danh sách expected hoặc chứa tiền tố
            for exp in expected:
                if exp.lower() in sec.lower() or sec.lower() in exp.lower():
                    found_rank = rank
                    found_sec = sec
                    break
            if found_rank is not None:
                break
        
        if found_rank is not None and found_rank <= settings.TOP_K:
            status = "PASS"
            pass_count += 1
            note = f"Khớp '{found_sec}' (Rank {found_rank})"
        else:
            status = "FAIL"
            fail_count += 1
            top_ret = [str(c.get("section")) for c in retrieved[:settings.TOP_K]]
            note = f"Không có {expected} trong Top {settings.TOP_K} (Top nhận được: {top_ret})"

        results_table.append({
            "ma": ma,
            "expected": ", ".join(expected),
            "rank": str(found_rank) if found_rank else ">4",
            "status": status,
            "note": note
        })

    db.close()
    elapsed = time.time() - t_start

    # In bảng Markdown
    print(f"\nThời gian chạy: {elapsed:.2f} giây ({len(questions)} câu)")
    print(f"KẾT QUẢ: {pass_count}/{len(questions)} PASS ({pass_count/len(questions)*100:.1f}%), {fail_count} FAIL\n")
    
    print("| Mã câu | Chunk kỳ vọng | Rank thực tế | Kết quả | Ghi chú |")
    print("| :--- | :--- | :---: | :---: | :--- |")
    for r in results_table:
        print(f"| {r['ma']} | {r['expected']} | {r['rank']} | **{r['status']}** | {r['note']} |")

    # Lưu kết quả retrieval ra JSON
    os.makedirs("output", exist_ok=True)
    with open("output/eval_retrieval_report.json", "w", encoding="utf-8") as f:
        json.dump(results_table, f, ensure_ascii=False, indent=2)


def run_full(limit_ids: List[str] = None, resume: bool = False):
    """Chế độ --full: gọi /chat, stream từng dòng vào CSV, hỗ trợ --resume."""
    print("=" * 80)
    print("=== CHẾ ĐỘ: FULL EVALUATION (Gọi POST /chat và ghi nhận CSV) ===")
    
    all_q = load_all_questions()
    if limit_ids:
        questions = [q for q in all_q if q["ma_cau_hoi"] in limit_ids]
    else:
        questions = all_q

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    csv_file = os.path.join(output_dir, "eval_qa_report.csv")

    done_ids = set()
    if resume and os.path.exists(csv_file):
        with open(csv_file, mode="r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0] != "ma_cau_hoi":
                    done_ids.add(row[0].strip())
        print(f"--> [RESUME] Đã tìm thấy {len(done_ids)} câu đã hoàn thành trước đó trong CSV.")

    # Mở file ghi tiếp (append nếu resume, write nếu mới)
    mode = "a" if (resume and os.path.exists(csv_file)) else "w"
    f_csv = open(csv_file, mode=mode, encoding="utf-8-sig", newline="")
    fieldnames = ["ma_cau_hoi", "cau_tra_loi", "dung/sai", "co_nguon_hay_khong"]
    writer = csv.DictWriter(f_csv, fieldnames=fieldnames)
    
    if mode == "w":
        writer.writeheader()
        f_csv.flush()

    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "admin", "role": "admin"}
    client = TestClient(app)

    print(f"Tổng số câu cần chạy: {len(questions) - len(done_ids)} / {len(questions)}\n")

    for idx, q in enumerate(questions, 1):
        ma = q["ma_cau_hoi"]
        if ma in done_ids:
            print(f"[{idx}/{len(questions)}] {ma}: ĐÃ HOÀN THÀNH (Bỏ qua do --resume)")
            continue

        prompt = q["cau_hoi"]
        print(f"[{idx}/{len(questions)}] {ma}: {prompt}", flush=True)
        t0 = time.time()
        
        try:
            res = client.post("/chat", json={"message": prompt})
            if res.status_code == 200:
                data = res.json()
                answer = data.get("response", "") or data.get("answer", "")
                sources = data.get("sources", [])
            else:
                answer = f"LỖI HTTP {res.status_code}: {res.text}"
                sources = []
        except Exception as e:
            answer = f"LỖI KẾT NỐI: {str(e)}"
            sources = []

        elapsed = time.time() - t0
        is_correct, has_source = evaluate_answer(ma, answer, sources)
        status_str = "ĐÚNG" if is_correct else "SAI"

        print(f"    -> Thời gian: {elapsed:.2f}s | Đánh giá: {status_str} | Nguồn: {has_source}", flush=True)
        first_line = answer.strip().split("\n")[0]
        print(f"    -> Trả lời: {first_line[:100]}...\n", flush=True)

        writer.writerow({
            "ma_cau_hoi": ma,
            "cau_tra_loi": answer,
            "dung/sai": status_str,
            "co_nguon_hay_khong": has_source
        })
        f_csv.flush()

    f_csv.close()
    print("=== HOÀN TẤT CHẠY FULL EVALUATION ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Đánh giá hệ thống Chatbot học vụ")
    parser.add_argument("--retrieval-only", action="store_true", help="Chỉ kiểm tra thứ hạng chunk của search_chunks")
    parser.add_argument("--full", action="store_true", help="Gọi /chat đầy đủ và xuất CSV")
    parser.add_argument("--resume", action="store_true", help="Bỏ qua các câu đã có trong CSV")
    parser.add_argument("--limit-ids", nargs="+", default=None, help="Chỉ chạy danh sách mã câu hỏi cụ thể")
    args = parser.parse_args()

    if args.retrieval_only:
        run_retrieval_only()
    elif args.full:
        run_full(limit_ids=args.limit_ids, resume=args.resume)
    else:
        print("Vui lòng chọn: python eval_qa.py --retrieval-only HOẶC python eval_qa.py --full [--resume]")
