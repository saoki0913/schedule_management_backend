from unittest.mock import MagicMock, patch

def mock_cosmos_client():
    """Cosmos DBクライアントのモック"""
    mock_container = MagicMock()
    mock_container.query_items.return_value = []
    mock_container.create_item.return_value = {"id": "test-token"}
    mock_container.read_item.return_value = {
        "id": "test-token",
        "start_date": "2025-01-10",
        "end_date": "2025-01-15",
        "start_time": "09:00",
        "end_time": "18:00",
        "selected_days": ["Monday", "Tuesday"],
        "duration_minutes": 60,
        "users": [{"email": "test@example.com"}],
        "time_zone": "Tokyo Standard Time",
        "isConfirmed": False
    }
    mock_container.replace_item.return_value = None

    mock_client = MagicMock()
    mock_client.get_database_client.return_value.get_container_client.return_value = mock_container
    return mock_client

def mock_graph_api():
    """Graph APIのモック"""
    mock_schedule = {
        "value": [
            {
                "scheduleItems": [
                    {
                        "start": {"dateTime": "2025-01-10T10:00:00", "timeZone": "Tokyo Standard Time"},
                        "end": {"dateTime": "2025-01-10T11:00:00", "timeZone": "Tokyo Standard Time"}
                    }
                ]
            }
        ]
    }
    return mock_schedule

def mock_event_creation():
    """イベント作成のモック"""
    mock_event = {
        "id": "test-event-id",
        "subject": "面接: 山田 太郎",
        "onlineMeeting": {"joinUrl": "https://teams.microsoft.com/l/meetup-join/..."}
    }
    return mock_event 