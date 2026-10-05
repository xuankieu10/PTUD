import os
import pytest
from fastapi.testclient import TestClient
from backend.api import app, SESSION_CACHE
from unittest.mock import patch, MagicMock

client = TestClient(app)

def test_health_endpoint():
    with patch("backend.api.requests.get") as mock_get:
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {"models": [{"name": "llama3.2-vision"}]}
        mock_get.return_value = mock_res
        
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "online"
        assert response.json()["ollama"]["online"] is True
        assert "llama3.2-vision" in response.json()["ollama"]["models"]

def test_health_endpoint_offline():
    with patch("backend.api.requests.get") as mock_get:
        mock_get.side_effect = Exception("Connection refused")
        
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["ollama"]["online"] is False
        assert response.json()["ollama"]["error"] == "Connection refused"

@patch("backend.api.run_pipeline")
def test_process_transcript_valid(mock_run, tmp_path):
    mock_run.return_value = {
        "json_path": "dummy.json",
        "csv_path": "dummy.csv",
        "annotated_image_path": "dummy.png",
        "all_subjects": [{"mon": "Toán", "diem": 9.0}],
        "failed_subjects": [],
        "total_subjects": 1,
        "failed_count": 0,
        "passed_count": 1,
        "red_regions_count": 0
    }
    
    file_path = tmp_path / "test.png"
    file_path.write_bytes(b"dummy image content")
    
    with open(file_path, "rb") as f:
        response = client.post("/api/process", files={"file": ("test.png", f, "image/png")})
    
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert res_json["filename"] == "test.png"
    assert len(res_json["all_subjects"]) == 1

def test_process_transcript_invalid_format():
    response = client.post(
        "/api/process",
        files={"file": ("test.txt", b"text content", "text/plain")}
    )
    assert response.status_code == 400
    assert "không được hỗ trợ" in response.json()["detail"]

def test_download_result_file(tmp_path):
    session_id = "test_session_123"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("STT,Môn học", encoding="utf-8-sig")
    
    # Inject into cache
    SESSION_CACHE[session_id] = {
        "csv_path": str(csv_file),
        "json_path": "invalid.json",
        "filename": "test.png"
    }
    
    response = client.get(f"/api/download/csv?session_id={session_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "STT,Môn học" in response.text
    
    response_invalid = client.get(f"/api/download/csv?session_id=not_exist")
    assert response_invalid.status_code == 404

@patch("backend.certificate_extractor.extract_certificate_from_image")
@patch("backend.certificate_matcher.match_certificate")
def test_process_certificate(mock_match, mock_extract, tmp_path):
    mock_extract.return_value = {"loai_chung_chi": "IELTS", "ten_chung_chi_cu_the": "IELTS", "ten_nguoi_duoc_cap": "A", "ngay_cap": "2023", "do_tin_cay": "cao"}
    mock_match.return_value = {"muc_tot_nghiep_khop": "A", "do_tuong_dong": 100, "phuong_thuc_khop": "Exact", "trang_thai_cap_nhat": "Đã hoàn tất", "tu_dong_cap_nhat": True, "ly_do": "", "thong_tin_trich_xuat": mock_extract.return_value}
    
    file_path = tmp_path / "cert.jpg"
    file_path.write_bytes(b"dummy image")
    
    with open(file_path, "rb") as f:
        response = client.post("/api/certificate/process", files={"file": ("cert.jpg", f, "image/jpeg")})
    
    assert response.status_code == 200
    assert response.json()["success"] is True

