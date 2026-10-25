import sys
import os
import json
import requests
from fastapi.testclient import TestClient

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.api import app
from backend.app.deps import get_current_user

# 1. Test via TestClient (direct module import)
app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "admin", "role": "admin"}
client = TestClient(app)

print("==================================================")
print("TEST 1: CÂU HỎI HỌC VỤ (Direct TestClient)")
print("Question: 'Điều kiện để được xét tốt nghiệp đại học gồm những gì?'")
print("==================================================")
res1 = client.post("/chat", json={"message": "Điều kiện để được xét tốt nghiệp đại học gồm những gì?"})
print(f"Status Code: {res1.status_code}")
data1 = res1.json()
answer1 = data1.get("answer", "")
sources1 = data1.get("sources", [])

print("--- Answer ---")
print(answer1)
print("\n--- Sources Count ---")
print(len(sources1))
print("--- Sources Detail ---")
for s in sources1:
    print(f"  * {s.get('title')} (Mục {s.get('section')}) -> {s.get('url')}")

print("\n--- Verification Test 1 ---")
has_nguon_str1 = "Nguồn:" in answer1 or "- Nguồn:" in answer1 or "* Nguồn:" in answer1
has_url_str1 = "cs.lhu.edu.vn" in answer1
print(f"Contains 'Nguồn:' in answer text? {has_nguon_str1} (Expect: False)")
print(f"Contains 'cs.lhu.edu.vn' in answer text? {has_url_str1} (Expect: False)")
print(f"Sources metadata list non-empty? {len(sources1) > 0} (Expect: True)")

print("\n==================================================")
print("TEST 2: CÂU HỎI NGOÀI LỀ (Direct TestClient)")
print("Question: 'Thời tiết hôm nay thế nào?'")
print("==================================================")
res2 = client.post("/chat", json={"message": "Thời tiết hôm nay thế nào?"})
print(f"Status Code: {res2.status_code}")
data2 = res2.json()
answer2 = data2.get("answer", "")
sources2 = data2.get("sources", [])

print("--- Answer ---")
print(answer2)
print("\n--- Sources Count ---")
print(len(sources2))

print("\n--- Verification Test 2 ---")
has_nguon_str2 = "Nguồn:" in answer2
print(f"Contains 'Nguồn:' in answer text? {has_nguon_str2} (Expect: False)")
print(f"Sources is empty? {len(sources2) == 0} (Expect: True)")
print(f"Is refusal? {'trợ lý tư vấn học vụ' in answer2} (Expect: True)")
