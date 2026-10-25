import sys
import json
from fastapi.testclient import TestClient
from backend.api import app

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

client = TestClient(app)
results = {}

# 1. Đăng nhập
try:
    res = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    if res.status_code == 200:
        token = res.json()["access_token"]
        results["POST /auth/login"] = ("HOẠT ĐỘNG", f"200 OK (Token: {token[:15]}...)")
        auth_header = {"Authorization": f"Bearer {token}"}
    else:
        results["POST /auth/login"] = ("CHẠY NHƯNG LỖI", f"Status {res.status_code}: {res.text}")
        auth_header = {}
except Exception as e:
    results["POST /auth/login"] = ("CHẠY NHƯNG LỖI", str(e))
    auth_header = {}

# 2. Thông tin người dùng
try:
    res = client.get("/auth/me", headers=auth_header)
    if res.status_code == 200:
        results["GET /auth/me"] = ("HOẠT ĐỘNG", f"200 OK (User: {res.json().get('username')})")
    else:
        results["GET /auth/me"] = ("CHẠY NHƯNG LỖI", f"Status {res.status_code}: {res.text}")
except Exception as e:
    results["GET /auth/me"] = ("CHẠY NHƯNG LỖI", str(e))

# 3. Quản lý tài liệu
try:
    res = client.get("/documents", headers=auth_header)
    if res.status_code == 200:
        docs = res.json()
        results["GET /documents"] = ("HOẠT ĐỘNG", f"200 OK (Số tài liệu: {len(docs)})")
    else:
        results["GET /documents"] = ("CHẠY NHƯNG LỖI", f"Status {res.status_code}: {res.text}")
except Exception as e:
    results["GET /documents"] = ("CHẠY NHƯNG LỖI", str(e))

# 4. Kiểm tra điều kiện tốt nghiệp
try:
    res = client.get("/students/1/graduation-check?explain=true", headers=auth_header)
    if res.status_code == 200:
        data = res.json()
        results["GET /students/{id}/graduation-check"] = ("HOẠT ĐỘNG", f"200 OK (Credits: {data.get('total_credits_passed')}, Eligible: {data.get('eligible')})")
    else:
        results["GET /students/{id}/graduation-check"] = ("CHẠY NHƯNG LỖI", f"Status {res.status_code}: {res.text}")
except Exception as e:
    results["GET /students/{id}/graduation-check"] = ("CHẠY NHƯNG LỖI", str(e))

# 5. Đồng bộ NNTH
try:
    res = client.post("/admin/sync-nnth", headers=auth_header)
    if res.status_code == 200:
        results["POST /admin/sync-nnth"] = ("HOẠT ĐỘNG", f"200 OK ({res.json().get('message')})")
    else:
        results["POST /admin/sync-nnth"] = ("CHẠY NHƯNG LỖI", f"Status {res.status_code}: {res.text}")
except Exception as e:
    results["POST /admin/sync-nnth"] = ("CHẠY NHƯNG LỖI", str(e))

# 6. Lịch học & Lịch thi
try:
    res_sched = client.get("/api/center/schedules")
    res_exams = client.get("/api/center/exams")
    if res_sched.status_code == 200 and res_exams.status_code == 200:
        results["GET /api/center/schedules & /exams"] = ("HOẠT ĐỘNG", f"200 OK (Lịch học: {res_sched.json().get('total')}, Lịch thi: {res_exams.json().get('total')})")
    else:
        results["GET /api/center/schedules & /exams"] = ("CHẠY NHƯNG LỖI", f"Schedules: {res_sched.status_code}, Exams: {res_exams.status_code}")
except Exception as e:
    results["GET /api/center/schedules & /exams"] = ("CHẠY NHƯNG LỖI", str(e))

# 7. Chat
try:
    res = client.post("/chat", json={"message": "Xin chào"}, headers=auth_header)
    if res.status_code == 200:
        results["POST /chat"] = ("HOẠT ĐỘNG", f"200 OK (Answer: {res.json().get('answer')[:60]}...)")
    else:
        results["POST /chat"] = ("CHẠY NHƯNG LỖI", f"Status {res.status_code}: {res.text}")
except Exception as e:
    results["POST /chat"] = ("CHẠY NHƯNG LỖI", str(e))

print("=== BÁO CÁO KIỂM THỬ CÁC ENDPOINT BACKEND ===")
for ep, (status, detail) in results.items():
    print(f"[{status}] {ep}: {detail}")
