import pytest
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
root_dir = Path(__file__).parent.parent.parent
sys.path.append(str(root_dir))

from fastapi.testclient import TestClient
from app import app as fastapi_app
from app.schemas import ScheduleRequest, AppointmentRequest, User

client = TestClient(fastapi_app)

def test_get_availability():
    """空き時間取得エンドポイントのテスト"""
    # テストデータの準備
    schedule_data = {
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
    response = client.post("/api/get_availability", json=schedule_data)

    # レスポンスの検証
    assert response.status_code == 200
    assert "common_availability" in response.json()

def test_create_appointment():
    """予約作成エンドポイントのテスト"""
    # テストデータの準備
    appointment_data = {
        "candidate": "2025-01-10T10:00:00,2025-01-10T11:00:00",
        "users": ["test@example.com"],
        "lastname": "山田",
        "firstname": "太郎",
        "company": "株式会社テスト",
        "email": "candidate@example.com",
        "token": "test-token-123"
    }

    # リクエストの実行
    response = client.post("/api/appointment", json=appointment_data)

    # レスポンスの検証
    assert response.status_code == 200
    response_data = response.json()
    assert "message" in response_data
    assert "subjects" in response_data
    assert "meeting_urls" in response_data
    assert "users" in response_data

def test_create_appointment_no_candidate():
    """候補日時なしでの予約作成テスト"""
    # テストデータの準備
    appointment_data = {
        "candidate": None,
        "users": ["test@example.com"],
        "lastname": "山田",
        "firstname": "太郎",
        "company": "株式会社テスト",
        "email": "candidate@example.com",
        "token": "test-token-123"
    }

    # リクエストの実行
    response = client.post("/api/appointment", json=appointment_data)

    # レスポンスの検証
    assert response.status_code == 200
    response_data = response.json()
    assert "message" in response_data
    assert "subjects" in response_data
    assert "meeting_urls" in response_data
    assert "users" in response_data
    assert len(response_data["subjects"]) == 0
    assert len(response_data["meeting_urls"]) == 0

def test_reschedule():
    """予定再調整エンドポイントのテスト"""
    # 確認画面の表示テスト
    response = client.get("/api/reschedule?token=test-token-123")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    # 確認後の処理テスト
    response = client.get("/api/reschedule?token=test-token-123&confirm=true")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_get_availability_invalid():
    """無効なデータでの空き時間取得テスト"""
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
    response = client.post("/api/get_availability", json=invalid_data)
    assert response.status_code == 422  # Validation Error

def test_create_appointment_invalid():
    """無効なデータでの予約作成テスト"""
    invalid_data = {
        "candidate": "invalid-date",
        "users": ["invalid-email"],
        "lastname": "",  # 空の文字列
        "firstname": "太郎",
        "company": "株式会社テスト",
        "email": "invalid-email",
        "token": "test-token-123"
    }
    response = client.post("/api/appointment", json=invalid_data)
    assert response.status_code == 422  # Validation Error 