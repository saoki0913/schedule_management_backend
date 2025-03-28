import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# プロジェクトのルートディレクトリをPythonパスに追加
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from fastapi.testclient import TestClient
from app import app as fastapi_app
from app.schemas import ScheduleRequest, AppointmentRequest, User
from .mocks import mock_cosmos_client, mock_graph_api, mock_event_creation

@pytest.fixture(autouse=True)
def mock_dependencies():
    """テスト用の依存関係のモック"""
    with patch('app.dependencies.container', mock_cosmos_client()), \
         patch('app.internal.graph_api.get_schedule', return_value=mock_graph_api()), \
         patch('app.internal.graph_api.create_event', return_value=mock_event_creation()):
        yield

@pytest.fixture
def client():
    """テスト用のFastAPIクライアント"""
    return TestClient(fastapi_app)

@pytest.fixture
def sample_schedule_request():
    """サンプルのスケジュールリクエスト"""
    return ScheduleRequest(
        start_date="2025-01-10",
        end_date="2025-01-15",
        start_time="09:00",
        end_time="18:00",
        selected_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        duration_minutes=60,
        users=[
            User(email="interviewer1@example.com"),
            User(email="interviewer2@example.com")
        ],
        time_zone="Tokyo Standard Time"
    )

@pytest.fixture
def sample_appointment_request():
    """サンプルの予約リクエスト"""
    return AppointmentRequest(
        candidate="2025-01-10T10:00:00,2025-01-10T11:00:00",
        users=["interviewer1@example.com", "interviewer2@example.com"],
        lastname="山田",
        firstname="太郎",
        company="株式会社サンプル",
        email="candidate@example.com",
        token="sample-token-123"
    ) 