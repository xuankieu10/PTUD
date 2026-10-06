import requests
import json
import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"

def print_req(res, title=""):
    print(f"\n--- {title} ---")
    print(f"> {res.request.method} {res.request.url}")
    if res.request.body:
        b = str(res.request.body)
        print(f"> {b[:100]}..." if len(b) > 100 else f"> {b}")
    print(f"< {res.status_code}")
    print(f"< {res.text[:300]}")

# 1. POST /auth/login right admin
r1 = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "Admin@123"})
print_req(r1, "1. Login admin")
admin_token = r1.json().get("access_token")

# 2. POST /auth/login wrong pass
r2 = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "wrong"})
print_req(r2, "2. Login wrong pass")

# 3. POST /auth/login not exist
r3 = requests.post(f"{BASE_URL}/auth/login", json={"username": "notexist", "password": "wrong"})
print_req(r3, "3. Login not exist")

# 4. GET /auth/me with token
r4_1 = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
print_req(r4_1, "4.1 GET me with token")
r4_2 = requests.get(f"{BASE_URL}/auth/me")
print_req(r4_2, "4.2 GET me without token")

# 5. GET /documents without token
r5 = requests.get(f"{BASE_URL}/documents")
print_req(r5, "5. GET /documents without token")

# 6. POST /documents with student
r_sv = requests.post(f"{BASE_URL}/auth/login", json={"username": "sv01", "password": "Sv@12345"})
sv_token = r_sv.json().get("access_token")
r6 = requests.post(f"{BASE_URL}/documents", headers={"Authorization": f"Bearer {sv_token}"}, data={"title": "sv title"}, files={"file": ("test.txt", "abc")})
print_req(r6, "6. POST /documents with student token")

# 7. POST /documents with admin
with open("test.txt", "w", encoding="utf-8") as f:
    f.write("Đây là file test dài tiếng Việt. " * 50)
r7 = requests.post(f"{BASE_URL}/documents", headers={"Authorization": f"Bearer {admin_token}"}, data={"title": "Tài liệu 1"}, files={"file": open("test.txt", "rb")})
print_req(r7, "7. POST /documents Admin txt")
doc_id = None
if r7.status_code in [200, 201]:
    doc_id = r7.json()["id"]

# 9. GET /documents, GET /documents/{id}
r9_1 = requests.get(f"{BASE_URL}/documents", headers={"Authorization": f"Bearer {admin_token}"})
print_req(r9_1, "9.1 GET /documents")
if doc_id:
    r9_2 = requests.get(f"{BASE_URL}/documents/{doc_id}", headers={"Authorization": f"Bearer {admin_token}"})
    print_req(r9_2, "9.2 GET /documents/{id}")

# 10. PUT /documents/{id}
if doc_id:
    r10_1 = requests.put(f"{BASE_URL}/documents/{doc_id}", headers={"Authorization": f"Bearer {admin_token}"}, data={"title": "Đã sửa"})
    print_req(r10_1, "10.1 PUT title")
    with open("test2.txt", "w", encoding="utf-8") as f: f.write("nội dung mới")
    r10_2 = requests.put(f"{BASE_URL}/documents/{doc_id}", headers={"Authorization": f"Bearer {admin_token}"}, files={"file": open("test2.txt", "rb")})
    print_req(r10_2, "10.2 PUT new file")

# 11. POST /documents invalid format
r11 = requests.post(f"{BASE_URL}/documents", headers={"Authorization": f"Bearer {admin_token}"}, data={"title": "bad"}, files={"file": ("bad.exe", "fake")})
print_req(r11, "11. POST exe file")

# 12. POST /documents too large
with open("big.txt", "wb") as f:
    f.write(b"0" * (11 * 1024 * 1024))
r12 = requests.post(f"{BASE_URL}/documents", headers={"Authorization": f"Bearer {admin_token}"}, data={"title": "big"}, files={"file": open("big.txt", "rb")})
print_req(r12, "12. POST large file")

# 8. Check DB
import subprocess
print("\n--- 8. Check DB ---")
res = subprocess.run('powershell -Command "$env:PYTHONPATH=\\".\\"; python scripts/run_e8.py"', shell=True, capture_output=True, text=True)
print(res.stdout)

# 14. DELETE /documents/{id}
if doc_id:
    r14 = requests.delete(f"{BASE_URL}/documents/{doc_id}", headers={"Authorization": f"Bearer {admin_token}"})
    print_req(r14, "14. DELETE /documents")
