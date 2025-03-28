import pytest
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
root_dir = Path(__file__).parent.parent.parent
sys.path.append(str(root_dir))

from fastapi.testclient import TestClient
from app import app as fastapi_app
from app.schemas import FormData, User

client = TestClient(fastapi_app)

def test_store_form_data():
    """フォームデータの保存エンドポイントのテスト"""
    # テストデータの準備
    form_data = {
        "start_date": "2025-01-10",
        "end_date": "2025-01-15",
        "start_time": "09:00",
        "end_time": "18:00",
        "selected_days": ["Monday", "Tuesday"],
        "duration_minutes": 60,
        "users": [
            {"email": "test@example.com"}
        ],
        "time_zone": "Tokyo Standard Time"
    }

    # リクエストの実行
    response = client.post("/api/storeFormData", json=form_data)

    # レスポンスの検証
    assert response.status_code == 200
    assert "token" in response.json()

def test_retrieve_form_data():
    """フォームデータの取得エンドポイントのテスト"""
    # まずフォームデータを保存
    form_data = {
        "start_date": "2025-01-10",
        "end_date": "2025-01-15",
        "start_time": "09:00",
        "end_time": "18:00",
        "selected_days": ["Monday", "Tuesday"],
        "duration_minutes": 60,
        "users": [
            {"email": "test@example.com"}
        ],
        "time_zone": "Tokyo Standard Time"
    }
    store_response = client.post("/api/storeFormData", json=form_data)
    token = store_response.json()["token"]

    # 保存したデータを取得
    response = client.get(f"/api/retrieveFormData?token={token}")

    # レスポンスの検証
    assert response.status_code == 200
    retrieved_data = response.json()
    assert retrieved_data["start_date"] == form_data["start_date"]
    assert retrieved_data["end_date"] == form_data["end_date"]
    assert retrieved_data["start_time"] == form_data["start_time"]
    assert retrieved_data["end_time"] == form_data["end_time"]
    assert retrieved_data["selected_days"] == form_data["selected_days"]
    assert retrieved_data["duration_minutes"] == form_data["duration_minutes"]
    assert retrieved_data["users"] == form_data["users"]
    assert retrieved_data["time_zone"] == form_data["time_zone"]
    assert retrieved_data["isConfirmed"] is False

def test_retrieve_form_data_not_found():
    """存在しないトークンでのフォームデータ取得テスト"""
    response = client.get("/api/retrieveFormData?token=non-existent-token")
    assert response.status_code == 404
    assert response.json()["detail"] == "Token not found"

def test_store_form_data_invalid():
    """無効なデータでのフォームデータ保存テスト"""
    invalid_data = {
        "start_date": "invalid-date",
        "end_date": "2025-01-15",
        "start_time": "09:00",
        "end_time": "18:00",
        "selected_days": ["Monday"],
        "duration_minutes": 60,
        "users": [
            {"email": "invalid-email"}
        ]
    }
    response = client.post("/api/storeFormData", json=invalid_data)
    assert response.status_code == 422  # Validation Error 