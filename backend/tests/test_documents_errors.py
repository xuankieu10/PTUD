import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from backend.api import app
from backend.app.db import SessionLocal
from backend.app.security import create_access_token
import io
from sqlalchemy import text

client = TestClient(app)

def make_headers():
    token = create_access_token(subject=1, role="admin")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def cleanup_failed_doc():
    yield
    # Cleanup any failed documents
    db = SessionLocal()
    db.execute(text("DELETE FROM documents WHERE status = 'failed'"))
    db.commit()
    db.close()

@pytest.mark.parametrize("mock_exception,expected_status", [
    (HTTPException(status_code=503, detail="Service Unavailable"), 503),
    (HTTPException(status_code=504, detail="Gateway Timeout"), 504),
])
def test_document_upload_fail(mock_exception, expected_status, cleanup_failed_doc):
    with patch("backend.app.routers.documents.get_embeddings_batch") as mock_emb:
        mock_emb.side_effect = mock_exception
        
        headers = make_headers()
        file_content = b"Some test content for document"
        files = {"file": ("test_fail.txt", file_content, "text/plain")}
        data = {"title": "Test Fail Doc"}
        
        res = client.post("/documents", files=files, data=data, headers=headers)
        
        assert res.status_code == expected_status
        
        # Verify status is 'failed' in DB
        db = SessionLocal()
        doc = db.execute(text("SELECT status FROM documents WHERE title = 'Test Fail Doc'")).fetchone()
        assert doc is not None
        assert doc.status == 'failed'
        db.close()
