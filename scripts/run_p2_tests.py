import requests
import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE_URL = "http://127.0.0.1:8000"

def print_res(res, title=""):
    print(f"\n=== {title} ===")
    print(f"{res.request.method} {res.request.url}")
    print(f"Status: {res.status_code}")
    if res.status_code == 200:
        print(f"Response: {json.dumps(res.json(), ensure_ascii=False, indent=2)}")
    else:
        print(f"Response: {res.text}")

# 1. Login
r_login = requests.post(f"{BASE_URL}/auth/login", json={"username": "sv01", "password": "Sv@12345"})
print_res(r_login, "1. Login SV01")
token = r_login.json().get("access_token")
sv_id = r_login.json().get("user_id") # Note: this is user_id, not student_id
headers = {"Authorization": f"Bearer {token}"}

# Get student_id from db
from sqlalchemy import create_engine, text
from backend.app.config import settings
engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    student_id = conn.execute(text("SELECT id FROM students WHERE user_id = :uid"), {"uid": sv_id}).scalar()
    print(f"\n=> Resolved student_id: {student_id}")

# 2. Graduation Check
r_grad = requests.get(f"{BASE_URL}/students/{student_id}/graduation-check?explain=true", headers=headers)
print_res(r_grad, "2. Graduation Check (SV01)")

# 3. Chat (có trong ngữ cảnh - 'Tài liệu 1' có chứa 'tiếng Việt')
r_chat_1 = requests.post(f"{BASE_URL}/chat", headers=headers, json={"message": "Tài liệu 1 có chứa tiếng Việt không?"})
print_res(r_chat_1, "3. Chat (có ngữ cảnh)")

# 4. Chat (không có ngữ cảnh)
session_id = r_chat_1.json().get("session_id") if r_chat_1.status_code == 200 else None
r_chat_2 = requests.post(f"{BASE_URL}/chat", headers=headers, json={"message": "Cách chế tạo bom?", "session_id": session_id})
print_res(r_chat_2, "4. Chat (không ngữ cảnh)")

# 5. Lấy lịch sử session
if session_id:
    r_history = requests.get(f"{BASE_URL}/chat/sessions/{session_id}/messages", headers=headers)
    print_res(r_history, "5. Chat History")
