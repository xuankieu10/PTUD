import os
import sys
import json
import time
from fastapi.testclient import TestClient
from backend.api import app
from backend.app.deps import get_current_user

# Setup client
app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "admin", "role": "admin"}
client = TestClient(app)

new_8_questions = [
    {
        "id": "NEW_01_A1",
        "topic": "Mục A.1 (Tín chỉ & GPA)",
        "question": "Sinh viên ngành Công nghệ thông tin cần hoàn thành tối thiểu bao nhiêu tín chỉ và đạt điểm trung bình tích lũy bao nhiêu để đủ điều kiện xét tốt nghiệp?",
        "keywords": ["150", "5.0"]
    },
    {
        "id": "NEW_02_A2_A3",
        "topic": "Mục A.2 & A.3 (GDQP, GDTC & Kỹ năng mềm)",
        "question": "Để đủ điều kiện tốt nghiệp chính quy, sinh viên có bắt buộc phải hoàn thành chứng chỉ GDTC, GDQP và bao nhiêu kỹ năng mềm?",
        "keywords": ["giáo dục thể chất", "giáo dục quốc phòng", "4 kỹ năng mềm"]
    },
    {
        "id": "NEW_03_A4",
        "topic": "Mục A.4 (Kỷ luật & Nghĩa vụ)",
        "question": "Sinh viên đang trong thời gian bị kỷ luật ở mức đình chỉ học tập hoặc còn nợ sách thư viện thì có được xét tốt nghiệp không?",
        "keywords": ["không được", "đình chỉ", "thư viện"]
    },
    {
        "id": "NEW_04_B",
        "topic": "Mục B (Hệ liên thông)",
        "question": "Sinh viên học hệ liên thông từ trung cấp/cao đẳng lên đại học có phải nộp chứng chỉ tiếng Anh Bậc 3 và sát hạch tin học để tốt nghiệp không?",
        "keywords": ["không", "liên thông"]
    },
    {
        "id": "NEW_05_C",
        "topic": "Mục C (Nộp hồ sơ & Lệ phí)",
        "question": "Sinh viên nộp hồ sơ xét tốt nghiệp trực tuyến ở trang web nào và đóng lệ phí bao nhiêu tiền, ở phòng nào?",
        "keywords": ["graduate.lhu.edu.vn", "100.000", "b101"]
    },
    {
        "id": "NEW_06_D",
        "topic": "Mục D (Giấy chứng nhận)",
        "question": "Nếu sinh viên đã tích lũy đủ 150 tín chỉ nhưng chưa nộp đủ chứng chỉ ngoại ngữ và tin học thì được Nhà trường cấp loại giấy chứng nhận nào?",
        "keywords": ["hoàn thành khóa học", "b101"]
    },
    {
        "id": "NEW_07_HINH1",
        "topic": "Hình 1 (Ngoại ngữ tương đương)",
        "question": "Theo quy định bảng ngoại ngữ tương đương (Hình 1), chứng chỉ TOEIC 4 kỹ năng cần đạt tối thiểu bao nhiêu điểm cho từng kỹ năng để tương đương Tiếng Anh Bậc 3?",
        "keywords": ["toeic", "200", "120"]
    },
    {
        "id": "NEW_08_HINH2",
        "topic": "Hình 2 (Tin học tương đương)",
        "question": "Theo danh mục chứng chỉ tin học tương đương (Hình 2), sinh viên có chứng chỉ tin học văn phòng MOS hoặc chứng chỉ mạng Cisco nào thì được thay thế Sát hạch tin học?",
        "keywords": ["mos", "microsoft", "cisco", "ccna"]
    }
]

print("=== BẮT ĐẦU KIỂM THỬ 8 CÂU HỎI MỚI (MỤC 4) ===")
results = []
for idx, item in enumerate(new_8_questions, start=1):
    q_id = item["id"]
    topic = item["topic"]
    question = item["question"]
    print(f"\n[{idx}/8] [{q_id}] {topic}")
    print(f"Câu hỏi: {question}")
    
    t0 = time.time()
    resp = client.post("/chat", json={"message": question})
    elapsed = time.time() - t0
    
    data = resp.json()
    ans = data.get("response", "")
    sources = data.get("sources", [])
    
    # Đánh giá bằng từ khóa bắt buộc
    ans_lower = ans.lower()
    has_source = len(sources) > 0
    matched_kw = [kw for kw in item["keywords"] if kw.lower() in ans_lower]
    is_correct = len(matched_kw) >= (len(item["keywords"]) - 1)  # Khớp đa số từ khóa
    
    status_str = "ĐÚNG" if is_correct else "SAI"
    print(f"   -> Thời gian: {elapsed:.2f}s | Đánh giá: {status_str} | Số nguồn: {len(sources)}")
    print(f"   -> Trả lời: {ans[:200]}...")
    
    results.append({
        "id": q_id,
        "topic": topic,
        "question": question,
        "answer": ans,
        "sources": sources,
        "is_correct": is_correct,
        "status": status_str,
        "elapsed_seconds": elapsed
    })

os.makedirs("output", exist_ok=True)
with open("output/eval_8_new_questions.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

passed = sum(1 for r in results if r["is_correct"])
print(f"\n=== KẾT THÚC KIỂM THỬ 8 CÂU HỎI MỚI ===")
print(f"Kết quả: {passed}/8 câu ĐÚNG ({passed/8*100:.1f}%)")
