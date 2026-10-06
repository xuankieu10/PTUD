import requests
from sqlalchemy import create_engine, text
from backend.app.config import settings

BASE_URL = "http://127.0.0.1:8000"
engine = create_engine(settings.DATABASE_URL)

print("\n--- e. Validation ---")
admin_token = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "Admin@123"}).json()["access_token"]
headers = {"Authorization": f"Bearer {admin_token}"}
print("Rỗng:", requests.post(f"{BASE_URL}/chat", json={"message": ""}, headers=headers).status_code)
print("Toàn khoảng trắng:", requests.post(f"{BASE_URL}/chat", json={"message": "   \n "}, headers=headers).status_code)
long_msg = "A" * 10000
print("10000 ký tự:", requests.post(f"{BASE_URL}/chat", json={"message": long_msg}, headers=headers).status_code)

print("\n--- g. Phân quyền ---")
sv01_t = requests.post(f"{BASE_URL}/auth/login", json={"username": "sv01", "password": "Sv@12345"}).json()["access_token"]
sv02_t = requests.post(f"{BASE_URL}/auth/login", json={"username": "sv02", "password": "Sv@12345"}).json()["access_token"]
res = requests.post(f"{BASE_URL}/chat", json={"message": "test"}, headers={"Authorization": f"Bearer {sv01_t}"}).json()
sid = res.get("session_id")
st = requests.get(f"{BASE_URL}/chat/sessions/{sid}/messages", headers={"Authorization": f"Bearer {sv02_t}"}).status_code
print(f"SV02 xem session của SV01: Status {st}")

print("\n--- h. Graduation Check SQL Manual ---")
with engine.connect() as conn:
    sql1 = "SELECT SUM(c.credits) FROM grades g JOIN courses c ON g.course_id=c.id WHERE g.student_id=1 AND g.passed=1"
    passed = conn.execute(text(sql1)).scalar() or 0
    print(f"SQL passed credits: {passed}")
    res = requests.get(f"{BASE_URL}/students/1/graduation-check?explain=false", headers={"Authorization": f"Bearer {sv01_t}"}).json()
    print(f"API passed credits: {res.get('total_credits_passed')}")
    print(f"API eligible: {res.get('eligible')}")
