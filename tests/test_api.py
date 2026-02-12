import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_root():
    """Rootエンドポイントのテスト"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "AI Legal Checker API is running"}

def test_compliance_check():
    """コンプライアンスチェックAPIのテスト（ダミー）"""
    test_payload = {
        "content": {
            "type": "text",
            "data": "テスト投稿内容"
        },
        "options": {
            "target_laws": ["pharmaceutical_affairs_act"]
        }
    }
    
    response = client.post("/api/v1/compliance/check", json=test_payload)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "success"