import requests
import json
from sqlalchemy import create_engine, text
from backend.app.config import settings

BASE_URL = "http://127.0.0.1:8000"
engine = create_engine(settings.DATABASE_URL)

qs = [
    "Tài liệu này là gì?",
    "Ngôn ngữ của file test là gì?",
    "Có gì đặc biệt trong tài liệu này không?",
    "Học phí của sinh viên IT là bao nhiêu?",
    "Lịch thi cuối kỳ khi nào có?"
]

admin_token = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "Admin@123"}).json()["access_token"]

for i, q in enumerate(qs, 1):
    res = requests.post(f"{BASE_URL}/chat", json={"message": q}, headers={"Authorization": f"Bearer {admin_token}"}).json()
    print(f"\n--- Câu {i} ---")
    print(f"Hỏi: {q}")
    print(f"AI: {res.get('answer')}")
    sources = res.get('sources', [])
    if sources:
        print(f"Sources: {[s['score'] for s in sources]}")
        print(f"Top 1 snippet: {sources[0]['snippet']}")
    else:
        print("Sources: Rỗng")

with engine.connect() as conn:
    print(f"\nSố chunk trong DB: {conn.execute(text('SELECT COUNT(*) FROM document_chunks')).scalar()}")
