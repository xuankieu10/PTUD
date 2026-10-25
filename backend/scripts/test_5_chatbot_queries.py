import sys
import json
from fastapi.testclient import TestClient
from backend.api import app
from backend.app.deps import get_current_user

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "admin", "role": "admin"}
client = TestClient(app)

queries = [
    ("Quy định 1", "Điểm trung bình tích lũy tối thiểu để được xét tốt nghiệp là bao nhiêu?"),
    ("Quy định 2", "Cần đạt chuẩn ngoại ngữ và tin học như thế nào để tốt nghiệp?"),
    ("Quy định 3", "Còn nợ học phí thì có được xét tốt nghiệp không?"),
    ("Ngoài học vụ", "Hướng dẫn tôi cách nấu phở bò Hà Nội chuẩn vị."),
    ("Khoa khác", "Điều kiện xét tốt nghiệp của sinh viên Khoa Kinh tế như thế nào?")
]

print("=== CHẠY THỬ 5 CÂU HỎI CHATBOT ===")
for category, q in queries:
    print(f"\n--- [{category}] Câu hỏi: {q} ---")
    res = client.post("/chat", json={"message": q})
    if res.status_code == 200:
        data = res.json()
        ans = data.get("answer", "")
        sources = data.get("sources", [])
        has_sources = len(sources) > 0 or "Nguồn:" in ans
        print("Trạng thái: 200 OK")
        print(f"Câu trả lời:\n{ans}")
        print(f"Có kèm nguồn: {'CÓ' if has_sources else 'KHÔNG'}")
    else:
        print(f"LỖI: Status {res.status_code}: {res.text}")
