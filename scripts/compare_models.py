import os
import sys
import re
import io
import json
import time
from typing import List, Dict, Any, Tuple

# Đảm bảo in tiếng Việt chuẩn trên Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.api import app
from backend.app.config import settings
from backend.app.security import create_access_token
from backend.app.services.retrieval import strip_accents

client = TestClient(app)

def get_auth_headers():
    token = create_access_token(subject=1, role="admin")
    return {"Authorization": f"Bearer {token}"}

# ─── BỘ CÂU HỎI CHUẨN 20 CÂU (17 TRONG PHẠM VI + 3 NGOÀI PHẠM VI) ──────────
EVAL_QUESTIONS = [
    {
        "id": "QD01",
        "nhom": "Điều kiện tốt nghiệp",
        "cau_hoi": "Điểm trung bình tích lũy tối thiểu để được xét tốt nghiệp là bao nhiêu?",
        "dap_an_chuan": "Từ 5.0 trở lên (loại trung bình trở lên).",
        "keywords_required": ["5.0", "trung bình"]
    },
    {
        "id": "QD02",
        "nhom": "Điều kiện tốt nghiệp",
        "cau_hoi": "Sinh viên chính quy cần chứng chỉ ngoại ngữ trình độ nào để tốt nghiệp?",
        "dap_an_chuan": "Tiếng Anh Bậc 3 theo Khung năng lực Ngoại ngữ 6 bậc, hoặc chứng chỉ tương đương.",
        "keywords_required": ["Bậc 3", "Tiếng Anh"]
    },
    {
        "id": "QD03",
        "nhom": "Điều kiện tốt nghiệp",
        "cau_hoi": "Điều kiện về tin học để xét tốt nghiệp là gì?",
        "dap_an_chuan": "Chứng nhận đạt Sát hạch tin học do Khoa CNTT tổ chức, hoặc chứng chỉ ứng dụng CNTT tương đương.",
        "keywords_required": ["sát hạch", "Khoa CNTT"]
    },
    {
        "id": "QD04",
        "nhom": "Điều kiện tốt nghiệp",
        "cau_hoi": "Tôi có cần đạt Giáo dục quốc phòng và Giáo dục thể chất để tốt nghiệp không?",
        "dap_an_chuan": "Có. Sinh viên hệ chính quy phải đạt cả hai học phần GDQP và GDTC.",
        "keywords_required": ["GDQP", "GDTC"]
    },
    {
        "id": "QD05",
        "nhom": "Điều kiện tốt nghiệp",
        "cau_hoi": "Cần có bao nhiêu chứng chỉ kỹ năng mềm để tốt nghiệp?",
        "dap_an_chuan": "4 kỹ năng mềm do Trường Đại học Lạc Hồng cấp.",
        "keywords_required": ["4", "kỹ năng mềm"]
    },
    {
        "id": "QD06",
        "nhom": "Điều kiện tốt nghiệp",
        "cau_hoi": "Còn nợ học phí thì có được xét tốt nghiệp không?",
        "dap_an_chuan": "Không. Điều kiện xét tốt nghiệp yêu cầu không nợ học phí.",
        "keywords_required": ["không", "học phí"]
    },
    {
        "id": "QD07",
        "nhom": "Điều kiện tốt nghiệp",
        "cau_hoi": "Chưa trả sách ở thư viện thì có được xét tốt nghiệp không?",
        "dap_an_chuan": "Không. Điều kiện xét tốt nghiệp yêu cầu không nợ tài liệu học tập tại thư viện.",
        "keywords_required": ["không", "thư viện"]
    },
    {
        "id": "QD08",
        "nhom": "Điều kiện tốt nghiệp",
        "cau_hoi": "Đang bị kỷ luật đình chỉ học tập thì có được xét tốt nghiệp không?",
        "dap_an_chuan": "Không. Tại thời điểm xét tốt nghiệp, sinh viên không được đang trong thời gian bị kỷ luật đình chỉ.",
        "keywords_required": ["không", "đình chỉ"]
    },
    {
        "id": "QD09",
        "nhom": "Điều kiện tốt nghiệp",
        "cau_hoi": "Sinh viên hệ liên thông có cần chứng chỉ GDQP, ngoại ngữ, tin học để tốt nghiệp không?",
        "dap_an_chuan": "Không yêu cầu GDQP, GDTC, KNM, ngoại ngữ, tin học cho hệ liên thông.",
        "keywords_required": ["không", "liên thông"]
    },
    {
        "id": "TT01",
        "nhom": "Hồ sơ và thủ tục",
        "cau_hoi": "Nộp hồ sơ xét tốt nghiệp ở đâu?",
        "dap_an_chuan": "Truy cập graduate.lhu.edu.vn và tải các file hồ sơ lên.",
        "keywords_required": ["graduate.lhu.edu.vn"]
    },
    {
        "id": "TT02",
        "nhom": "Hồ sơ và thủ tục",
        "cau_hoi": "Lệ phí xét tốt nghiệp là bao nhiêu và đóng ở đâu?",
        "dap_an_chuan": "100.000 VNĐ, đóng tại phòng Đào tạo (B101, Cơ sở 1).",
        "keywords_required": ["100.000", "B101"]
    },
    {
        "id": "TT03",
        "nhom": "Hồ sơ và thủ tục",
        "cau_hoi": "Hồ sơ xét tốt nghiệp của sinh viên chính quy gồm những file nào?",
        "dap_an_chuan": "Chứng chỉ GDTC, GDQP, kỹ năng mềm (4 kỹ năng), ngoại ngữ, tin học, bằng tốt nghiệp THPT.",
        "keywords_required": ["GDQP", "GDTC", "kỹ năng mềm", "ngoại ngữ", "tin học"]
    },
    {
        "id": "TT04",
        "nhom": "Hồ sơ và thủ tục",
        "cau_hoi": "Đủ tín chỉ nhưng thiếu các điều kiện khác thì được cấp giấy gì?",
        "dap_an_chuan": "Giấy chứng nhận hoàn thành khóa học. Liên hệ phòng Đào tạo (B101, Cơ sở 1).",
        "keywords_required": ["hoàn thành khóa học", "B101"]
    },
    {
        "id": "TT05",
        "nhom": "Hồ sơ và thủ tục",
        "cau_hoi": "Lấy chứng chỉ GDQP, GDTC, kỹ năng mềm ở đâu?",
        "dap_an_chuan": "Liên hệ tại phòng Đào tạo (Bộ phận học vụ), Cơ sở 1.",
        "keywords_required": ["Đào tạo", "Cơ sở 1"]
    },
    {
        "id": "CT01",
        "nhom": "Chương trình đào tạo",
        "cau_hoi": "Chương trình đào tạo ngành CNTT có tổng cộng bao nhiêu tín chỉ?",
        "dap_an_chuan": "150 tín chỉ toàn khóa, chia thành 8 học kỳ.",
        "keywords_required": ["150", "tín chỉ"]
    },
    {
        "id": "CT02",
        "nhom": "Chương trình đào tạo",
        "cau_hoi": "Môn Tốt nghiệp bao nhiêu tín chỉ và học ở học kỳ nào?",
        "dap_an_chuan": "8 tín chỉ, học ở học kỳ 8.",
        "keywords_required": ["8", "học kỳ 8"]
    },
    {
        "id": "CT03",
        "nhom": "Chương trình đào tạo",
        "cau_hoi": "Học kỳ 7 có những môn nào và tổng bao nhiêu tín chỉ?",
        "dap_an_chuan": "English 7 (4), Kiểm thử (3), Quản trị website (2), Phát triển ứng dụng (9), tự chọn (3). Tổng 21 tín chỉ.",
        "keywords_required": ["21", "tín chỉ"]
    },
    # 3 câu ngoài phạm vi để kiểm tra từ chối
    {
        "id": "NP01",
        "nhom": "Ngoài phạm vi",
        "cau_hoi": "Cho tôi công thức nấu phở bò ngon tại nhà.",
        "dap_an_chuan": "Chatbot từ chối lịch sự, nói rằng chỉ hỗ trợ tư vấn học vụ.",
        "keywords_required": ["tư vấn học vụ"]
    },
    {
        "id": "NP02",
        "nhom": "Ngoài phạm vi (Khoa khác)",
        "cau_hoi": "Quy định xét tốt nghiệp của Khoa Kinh tế như thế nào?",
        "dap_an_chuan": "Chatbot nói chưa có dữ liệu khoa khác; hiện chỉ hỗ trợ khoa CNTT.",
        "keywords_required": ["chưa có dữ liệu", "Khoa Công nghệ thông tin"]
    },
    {
        "id": "NP03",
        "nhom": "Ngoài phạm vi",
        "cau_hoi": "Giá bitcoin hôm nay bao nhiêu và có nên đầu tư không?",
        "dap_an_chuan": "Chatbot từ chối lịch sự và chỉ hỗ trợ học vụ.",
        "keywords_required": ["tư vấn học vụ"]
    },
]

def check_keywords_score(answer: str, required_keywords: List[str]) -> Tuple[int, int, float]:
    """Kiểm tra số lượng từ khóa bắt buộc xuất hiện trong câu trả lời."""
    ans_norm = strip_accents(answer.lower())
    matched = 0
    for kw in required_keywords:
        kw_norm = strip_accents(kw.lower())
        if kw_norm in ans_norm:
            matched += 1
    total = len(required_keywords)
    ratio = matched / total if total > 0 else 1.0
    return matched, total, ratio

def normalize_number(num_str: str) -> str:
    """Chuẩn hoá số: 100.000 hoặc 100,000 -> 100000; giữ nguyên số thập phân như 5.0."""
    return re.sub(r'(?<=\d)[.,](?=\d{3}(?:\D|$))', '', num_str)

def clean_url_entity(url: str) -> str:
    """Bỏ dấu câu cuối URL (. , ; : ) ] và dấu / thừa) và hạ chữ thường."""
    u = url.strip()
    u = re.sub(r'[\.,;:)\/\\]+$', '', u)
    u = u.rstrip('/').lower()
    return u

def check_hallucinations(answer: str, rag_context: str) -> Tuple[bool, List[str]]:
    """
    Trích mọi con số, mã phòng, địa chỉ web, email trong câu trả lời.
    Kiểm tra có xuất hiện trong ngữ cảnh RAG đã đưa vào prompt hay không.
    Đã chuẩn hoá:
    1. Bỏ dấu câu cuối URL (. , ; : ) ] và dấu / thừa), hạ chữ thường.
    2. Chuẩn hoá số (100.000 và 100000 coi như nhau).
    """
    if not rag_context:
        return False, []

    ans_clean = answer
    # Bỏ qua các số thứ tự dạng gạch đầu dòng "1.", "2.", "3."
    ans_clean = re.sub(r'^\s*\d+\.\s*', '', ans_clean, flags=re.MULTILINE)

    raw_numbers = re.findall(r'\b\d+(?:[.,]\d+)+\b|\b\d{2,}\b', ans_clean)
    rooms = re.findall(r'\b[A-Za-z]\d{3}\b', ans_clean)
    raw_urls = re.findall(r'(?:https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.edu\.vn\b)', ans_clean)
    emails = re.findall(r'[\w.-]+@[\w.-]+\.\w+', ans_clean)

    urls = [clean_url_entity(u) for u in raw_urls if len(clean_url_entity(u)) > 3]

    rag_lower = rag_context.lower()
    rag_norm_numbers = normalize_number(rag_lower)

    unsupported_entities = []

    for url in set(urls):
        domain = re.sub(r'^https?://', '', url).split('/')[0]
        if (url not in rag_lower) and (domain not in rag_lower):
            unsupported_entities.append(url)

    for r in set(rooms):
        if r.lower() not in rag_lower:
            unsupported_entities.append(r)

    for em in set(emails):
        if em.lower() not in rag_lower:
            unsupported_entities.append(em)

    for n in set(raw_numbers):
        norm_n = normalize_number(n)
        if norm_n.isdigit() and int(norm_n) <= 10:
            continue
        if (n.lower() not in rag_lower) and (norm_n not in rag_norm_numbers):
            unsupported_entities.append(n)

    has_flag = len(unsupported_entities) > 0
    return has_flag, unsupported_entities

def run_evaluation_for_config(
    model_name: str,
    top_k: int,
    max_chunk_chars: int,
    questions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Chạy đánh giá cho một cấu hình mô hình."""
    print(f"\n{'='*80}")
    print(f"ĐÁNH GIÁ CẤU HÌNH: MODEL={model_name} | TOP_K={top_k} | MAX_CHUNK_CHARS={max_chunk_chars}")
    print(f"{'='*80}")

    # Áp dụng cấu hình
    settings.LLM_MODEL = model_name
    settings.TOP_K = top_k
    settings.MAX_CHUNK_CHARS = max_chunk_chars

    headers = get_auth_headers()
    results = []
    total_matched_kw = 0
    total_expected_kw = 0
    total_hallucination_flags = 0
    total_elapsed = 0.0

    for idx, item in enumerate(questions, 1):
        qid = item["id"]
        q_text = item["cau_hoi"]
        req_kw = item["keywords_required"]

        t0 = time.perf_counter()
        res = client.post("/chat", json={"message": q_text}, headers=headers)
        elapsed = time.perf_counter() - t0
        total_elapsed += elapsed

        if res.status_code != 200:
            print(f"[{qid}] LỖI {res.status_code}: {res.text}")
            results.append({
                "id": qid,
                "question": q_text,
                "elapsed": elapsed,
                "sources_count": 0,
                "matched_kw": 0,
                "total_kw": len(req_kw),
                "kw_ratio": 0.0,
                "hallucination": False,
                "hallucination_items": [],
                "answer_preview": f"Error {res.status_code}"
            })
            continue

        data = res.json()
        ans = data.get("answer", "")
        sources = data.get("sources", [])

        # Ghép text context từ sources
        rag_ctx = " ".join([s.get("snippet", "") for s in sources])

        matched, total_kw, ratio = check_keywords_score(ans, req_kw)
        total_matched_kw += matched
        total_expected_kw += total_kw

        is_hal, hal_items = check_hallucinations(ans, rag_ctx)
        if is_hal:
            total_hallucination_flags += 1

        ans_short = ans[:90].replace("\n", " ")
        hal_str = f"CỜ BỊA: {hal_items}" if is_hal else "OK"
        print(f"[{qid:<4}] {elapsed:>5.2f}s | Nguồn: {len(sources)} | Từ khóa: {matched}/{total_kw} ({ratio*100:>3.0f}%) | {hal_str:<25} | {ans_short}...")

        results.append({
            "id": qid,
            "question": q_text,
            "elapsed": elapsed,
            "sources_count": len(sources),
            "matched_kw": matched,
            "total_kw": total_kw,
            "kw_ratio": ratio,
            "hallucination": is_hal,
            "hallucination_items": hal_items,
            "answer": ans
        })

    overall_kw_rate = (total_matched_kw / total_expected_kw) * 100 if total_expected_kw > 0 else 0.0
    avg_time = total_elapsed / len(questions) if questions else 0.0

    print(f"\n--- TỔNG KẾT [{model_name} | TOP_K={top_k} | MAX_CHARS={max_chunk_chars}] ---")
    print(f"  + Tỉ lệ khớp từ khóa bắt buộc: {overall_kw_rate:.1f}% ({total_matched_kw}/{total_expected_kw})")
    print(f"  + Tổng số cờ nghi bịa:         {total_hallucination_flags}")
    print(f"  + Thời gian trung bình/câu:    {avg_time:.2f}s (Tổng: {total_elapsed:.1f}s)")

    return {
        "model": model_name,
        "top_k": top_k,
        "max_chunk_chars": max_chunk_chars,
        "overall_kw_rate": overall_kw_rate,
        "total_matched_kw": total_matched_kw,
        "total_expected_kw": total_expected_kw,
        "total_hallucination_flags": total_hallucination_flags,
        "avg_time": avg_time,
        "total_elapsed": total_elapsed,
        "details": results
    }

def main():
    print("=" * 85)
    print("CHƯƠNG TRÌNH SO SÁNH QWEN2.5:3B VÀ QWEN2.5:7B TRÊN BỘ CÂU HỎI CHUẨN")
    print("=" * 85)

    # 1. In danh sách câu hỏi kèm từ khóa bắt buộc để người dùng duyệt
    print("\nDANH SÁCH 20 CÂU HỎI VÀ TỪ KHÓA BẮT BUỘC:")
    for q in EVAL_QUESTIONS:
        print(f"  [{q['id']}] ({q['nhom']}): {q['cau_hoi']}")
        print(f"        -> Từ khóa bắt buộc: {q['keywords_required']}")

    # Chạy lần lượt 4 cấu hình:
    # Cấu hình 1: 3b mặc định (TOP_K=3, MAX_CHARS=600)
    cfg_3b_default = run_evaluation_for_config("qwen2.5:3b", top_k=3, max_chunk_chars=600, questions=EVAL_QUESTIONS)

    # Cấu hình 2: 7b chuẩn (TOP_K=3, MAX_CHARS=600)
    cfg_7b_default = run_evaluation_for_config("qwen2.5:7b", top_k=3, max_chunk_chars=600, questions=EVAL_QUESTIONS)

    # Cấu hình 3: 3b giảm trễ (a) (TOP_K=2, MAX_CHARS=600)
    cfg_3b_topk2 = run_evaluation_for_config("qwen2.5:3b", top_k=2, max_chunk_chars=600, questions=EVAL_QUESTIONS)

    # Cấu hình 4: 3b giảm trễ (b) (TOP_K=2, MAX_CHARS=400)
    cfg_3b_topk2_c400 = run_evaluation_for_config("qwen2.5:3b", top_k=2, max_chunk_chars=400, questions=EVAL_QUESTIONS)

    # In Bảng tổng hợp so sánh
    print("\n\n" + "=" * 95)
    print("BẢNG SO SÁNH TỔNG HỢP CÁC CẤU HÌNH")
    print("=" * 95)
    print(f"{'Cấu hình':<35} | {'Thời gian TB':<14} | {'Tỉ lệ từ khóa':<15} | {'Cờ nghi bịa':<12} | {'Đánh giá'}")
    print("-" * 95)

    configs = [
        ("qwen2.5:3b (mặc định K=3, 600ch)", cfg_3b_default),
        ("qwen2.5:7b (mốc chuẩn K=3, 600ch)", cfg_7b_default),
        ("qwen2.5:3b (giảm trễ a: K=2, 600ch)", cfg_3b_topk2),
        ("qwen2.5:3b (giảm trễ b: K=2, 400ch)", cfg_3b_topk2_c400),
    ]

    ref_7b_rate = cfg_7b_default["overall_kw_rate"]
    ref_7b_hal = cfg_7b_default["total_hallucination_flags"]

    for name, c in configs:
        rate = c["overall_kw_rate"]
        hal = c["total_hallucination_flags"]
        t_avg = f"{c['avg_time']:.2f}s"
        diff_kw = rate - ref_7b_rate
        diff_str = f"({diff_kw:+.1f}%)" if name != "qwen2.5:7b (mốc chuẩn K=3, 600ch)" else "(Chuẩn)"
        rate_str = f"{rate:.1f}% {diff_str}"
        
        # Đánh giá theo quy tắc
        if name == "qwen2.5:7b (mốc chuẩn K=3, 600ch)":
            eval_tag = "Mốc đối chiếu"
        elif diff_kw >= -10.0 and hal <= ref_7b_hal:
            eval_tag = "ĐẠT TIÊU CHUẨN"
        else:
            eval_tag = "KHÔNG ĐẠT"

        print(f"{name:<35} | {t_avg:<14} | {rate_str:<15} | {hal:<12} | {eval_tag}")

    print("=" * 95)

    # Lưu kết quả ra file JSON
    out_path = "scripts/compare_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "cfg_3b_default": cfg_3b_default,
            "cfg_7b_default": cfg_7b_default,
            "cfg_3b_topk2": cfg_3b_topk2,
            "cfg_3b_topk2_c400": cfg_3b_topk2_c400,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nĐã lưu toàn bộ kết quả chi tiết vào: {out_path}")

if __name__ == "__main__":
    main()
