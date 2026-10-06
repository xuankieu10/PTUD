import requests
import time

admin_token = requests.post("http://127.0.0.1:8000/auth/login", json={"username": "admin", "password": "Admin@123"}).json()["access_token"]
headers = {"Authorization": f"Bearer {admin_token}"}

t0 = time.time()
res = requests.post("http://127.0.0.1:8000/chat", json={"message": "Xin chào"}, headers=headers)
print(f"Status Code: {res.status_code}")
print(f"Body: {res.text}")
print(f"Time: {time.time() - t0:.2f}s")
