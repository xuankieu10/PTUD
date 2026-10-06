import requests
from sqlalchemy import create_engine, text
from backend.app.config import settings

BASE_URL = "http://127.0.0.1:8000"
engine = create_engine(settings.DATABASE_URL)

admin_token = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "Admin@123"}).json()["access_token"]
headers = {"Authorization": f"Bearer {admin_token}"}

print("\n--- d. Import ---")
# Tạo ảnh png giả
img_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

r_imp1 = requests.post(f"{BASE_URL}/transcripts/import", data={"student_id": 1}, files={"file": ("in.png", img_data, "image/png")}, headers=headers)
with engine.connect() as conn:
    c1 = conn.execute(text("SELECT COUNT(*) FROM grades WHERE source='ocr'")).scalar()
    print("Grades OCR count sau lần 1:", c1)

r_imp2 = requests.post(f"{BASE_URL}/transcripts/import", data={"student_id": 1}, files={"file": ("in.png", img_data, "image/png")}, headers=headers)
with engine.connect() as conn:
    c2 = conn.execute(text("SELECT COUNT(*) FROM grades WHERE source='ocr'")).scalar()
    print("Grades OCR count sau lần 2:", c2)
    
print("Import file txt:", requests.post(f"{BASE_URL}/transcripts/import", data={"student_id": 1}, files={"file": ("in.txt", b"text", "text/plain")}, headers=headers).status_code)
print("Sinh viên import cho người khác:", requests.post(f"{BASE_URL}/transcripts/import", data={"student_id": 2}, files={"file": ("in.png", img_data, "image/png")}, headers={"Authorization": f"Bearer {requests.post(f'{BASE_URL}/auth/login', json={'username': 'sv01', 'password': 'Sv@12345'}).json()['access_token']}"}).status_code)

print("\n--- e. Phân quyền graduation ---")
sv01_t = requests.post(f"{BASE_URL}/auth/login", json={"username": "sv01", "password": "Sv@12345"}).json()["access_token"]
print("SV1 xem SV2:", requests.get(f"{BASE_URL}/students/3/graduation-check", headers={"Authorization": f"Bearer {sv01_t}"}).status_code)
print("SV1 xem ko tồn tại:", requests.get(f"{BASE_URL}/students/999/graduation-check", headers={"Authorization": f"Bearer {sv01_t}"}).status_code)
print("Admin xem SV2:", requests.get(f"{BASE_URL}/students/3/graduation-check?explain=false", headers=headers).status_code)
