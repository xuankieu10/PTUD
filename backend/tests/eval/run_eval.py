"""
backend/tests/eval/run_eval.py
Script chạy kiểm thử đánh giá chất lượng (eval) bộ câu hỏi quy định học vụ:
- Đọc danh sách câu hỏi từ questions.json
- Gửi từng câu hỏi vào endpoint /chat thông qua TestClient
- Kiểm tra các tiêu chí must_contain (bắt buộc có) và must_not_contain (tuyệt đối không được có)
- In bảng tổng kết PASS / FAIL chi tiết từng câu kèm câu trả lời thực tế nếu FAIL.
"""

import sys
import os
import json
import re
from pathlib import Path

# Đảm bảo UTF-8 cho console Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.api import app
from backend.app.security import create_access_token

client = TestClient(app)


def make_headers():
    token = create_access_token(subject=1, role="student")
    return {"Authorization": f"Bearer {token}"}


def normalize_str(s: str) -> str:
    """Chuẩn hóa chuỗi để so khớp không phân biệt hoa thường và khoảng trắng."""
    return re.sub(r'\s+', ' ', (s or '').lower()).strip()


def evaluate_question(item: dict, headers: dict) -> dict:
    """Đánh giá 1 câu hỏi."""
    qid = item["id"]
    category = item.get("category", "")
    question = item["question"]
    must_contain = item.get("must_contain", [])
    must_not_contain = item.get("must_not_contain", [])

    answer_text = ""
    error_msg = None

    try:
        res = client.post("/chat", json={"message": question}, headers=headers)
        if res.status_code == 200:
            data = res.json()
            answer_text = data.get("answer") or data.get("response") or ""
        else:
            error_msg = f"HTTP {res.status_code}: {res.text}"
            answer_text = f"ERROR: {error_msg}"
    except Exception as e:
        error_msg = str(e)
        answer_text = f"ERROR: {e}"

    norm_answer = normalize_str(answer_text)

    # Kiểm tra must_contain
    missing = []
    for mc in must_contain:
        if normalize_str(mc) not in norm_answer:
            missing.append(mc)

    # Kiểm tra must_not_contain
    forbidden_found = []
    for mnc in must_not_contain:
        if normalize_str(mnc) in norm_answer:
            forbidden_found.append(mnc)

    passed = (len(missing) == 0 and len(forbidden_found) == 0 and error_msg is None)

    return {
        "id": qid,
        "category": category,
        "question": question,
        "passed": passed,
        "missing": missing,
        "forbidden_found": forbidden_found,
        "error": error_msg,
        "actual_answer": answer_text
    }


def main():
    questions_file = CURRENT_DIR / "questions.json"
    if not questions_file.exists():
        print(f"Lỗi: Không tìm thấy tệp {questions_file}", file=sys.stderr)
        sys.exit(1)

    with open(questions_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    headers = make_headers()

    print(f"=== BẮT ĐẦU CHẠY BỘ ĐÁNH GIÁ (EVAL) QUY ĐỊNH HỌC VỤ: {len(questions)} CÂU ===")
    print("=" * 115)
    print(f"{'ID':<3} | {'Chủ đề':<25} | {'Trạng thái':<8} | {'Chi tiết lỗi (Missing / Forbidden)':<65}")
    print("-" * 115)

    results = []
    failed_items = []

    for item in questions:
        res = evaluate_question(item, headers)
        results.append(res)

        status_str = "PASS" if res["passed"] else "FAIL"
        err_details = []
        if res["error"]:
            err_details.append(f"HTTP/DB Error: {res['error']}")
        if res["missing"]:
            err_details.append(f"Thiếu: {', '.join(res['missing'])}")
        if res["forbidden_found"]:
            err_details.append(f"Chứa từ cấm: {', '.join(res['forbidden_found'])}")

        detail_str = "; ".join(err_details) if err_details else "Đạt tất cả tiêu chí"
        print(f"{res['id']:<3} | {res['category'][:25]:<25} | {status_str:<8} | {detail_str[:65]:<65}")

        if not res["passed"]:
            failed_items.append(res)

    print("=" * 115)
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    pass_rate = (passed / total) * 100 if total > 0 else 0

    print(f"TỔNG KẾT EVAL: {passed}/{total} PASS ({pass_rate:.1f}%), {failed} FAIL\n")

    if failed_items:
        print("=== DANH SÁCH CHI TIẾT CÁC CÂU FAIL ===")
        for f_item in failed_items:
            print(f"\n[CÂU {f_item['id']}] - Chủ đề: {f_item['category']}")
            print(f"Câu hỏi: {f_item['question']}")
            if f_item["missing"]:
                print(f"  * Thiếu cụm từ bắt buộc: {f_item['missing']}")
            if f_item["forbidden_found"]:
                print(f"  * Chứa cụm từ cấm: {f_item['forbidden_found']}")
            print("  * Câu trả lời thực tế của hệ thống:")
            print("    " + f_item["actual_answer"].replace("\n", "\n    "))
            print("-" * 80)


if __name__ == "__main__":
    main()
