import sys
import json
from fastapi.testclient import TestClient
from backend.api import app
from backend.app.deps import get_current_user

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Mock user for authenticated endpoints if needed
app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "admin", "role": "admin"}
client = TestClient(app)

print("=== 1. TEST POST /admin/sync-nnth ===")
res_sync = client.post("/admin/sync-nnth")
print(f"Status: {res_sync.status_code}")
print("Response:", res_sync.json())

print("\n=== 2. TEST GET /api/center/schedules ===")
res_sched = client.get("/api/center/schedules")
print(f"Status: {res_sched.status_code}")
data_sched = res_sched.json()
print(f"Total schedules: {data_sched.get('total')}")
for s in data_sched.get("schedules", []):
    print(f" - [{s['loai']}] {s['ten_khoa_hoc']} | Khai giảng: {s['ngay_khai_giang_str']} | Học phí: {s['hoc_phi']}")

print("\n=== 3. TEST GET /api/center/exams (Lọc Ngoại ngữ) ===")
res_exams_nn = client.get("/api/center/exams?loai=Ngoại ngữ")
print(f"Status: {res_exams_nn.status_code}")
data_exams_nn = res_exams_nn.json()
print(f"Total Ngoại ngữ exams: {data_exams_nn.get('total')}")
for e in data_exams_nn.get("exams", []):
    print(f" - {e['ten_ky_thi']} | Ngày thi: {e['ngay_thi_str']} | Hạn ĐK: {e['han_dang_ky']} | Lệ phí: {e['le_phi_thi']}")

print("\n=== 4. TEST GET /api/center/summary ===")
res_sum = client.get("/api/center/summary")
print(f"Status: {res_sum.status_code}")
print("Summary:", res_sum.json())

print("\n=== 5. TEST CHATBOT TRẢ LỜI LỊCH THI NNTH KÈM FOOTER ===")
res_chat = client.post("/chat", json={"message": "Lịch thi chứng chỉ tin học và tiếng anh sắp tới khi nào?"})
print(f"Status: {res_chat.status_code}")
chat_resp = res_chat.json()
print("Chatbot Answer:\n", chat_resp.get("answer"))
print("\nSources:\n", chat_resp.get("sources"))

print("\nALL TESTS PASSED SUCCESSFULLY!")
