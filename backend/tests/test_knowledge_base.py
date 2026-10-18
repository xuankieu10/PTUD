import pytest
from fastapi.testclient import TestClient
from backend.api import app
from backend.app.services.chunking import chunk_text

client = TestClient(app)

def test_chunk_text():
    text = "Đây là câu 1. Đây là câu 2. Đây là câu 3."
    chunks = chunk_text(text, chunk_size=30, chunk_overlap=10)
    assert len(chunks) > 0

from unittest.mock import patch

def test_login_wrong_credentials():
    response = client.post("/auth/login", json={"username": "admin", "password": "wrong_password"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

def test_verify_password_real_hash():
    """Kiểm tra verify_password hoạt động tốt với hash thật."""
    from backend.app.security import get_password_hash, verify_password
    real_hash = get_password_hash("my_real_password")
    assert verify_password("my_real_password", real_hash) is True
    assert verify_password("wrong", real_hash) is False

def test_get_documents_no_token():
    response = client.get("/documents")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
