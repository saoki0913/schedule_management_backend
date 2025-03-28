import pytest
import sys
from pathlib import Path
from datetime import datetime

# プロジェクトのルートディレクトリをPythonパスに追加
root_dir = Path(__file__).parent.parent.parent
sys.path.append(str(root_dir))

from app.schemas import (
    User,
    ScheduleRequest,
    AppointmentRequest,
    FormData,
    AppointmentResponse,
    AvailabilityResponse
)

def test_user_schema():
    """Userスキーマのバリデーションテスト"""
    # 正常なケース
    user = User(email="test@example.com")
    assert user.email == "test@example.com"

    # 無効なメールアドレス
    with pytest.raises(ValueError):
        User(email="invalid-email")

def test_schedule_request_schema():
    """ScheduleRequestスキーマのバリデーションテスト"""
    # 正常なケース
    schedule = ScheduleRequest(
        start_date="2025-01-10",
        end_date="2025-01-15",
        start_time="09:00",
        end_time="18:00",
        selected_days=["Monday", "Tuesday"],
        duration_minutes=60,
        users=[User(email="test@example.com")]
    )
    assert schedule.start_date == "2025-01-10"
    assert schedule.end_date == "2025-01-15"
    assert schedule.start_time == "09:00"
    assert schedule.end_time == "18:00"
    assert schedule.selected_days == ["Monday", "Tuesday"]
    assert schedule.duration_minutes == 60
    assert len(schedule.users) == 1
    assert schedule.time_zone == "Tokyo Standard Time"  # デフォルト値

    # 無効な日付形式
    with pytest.raises(ValueError):
        ScheduleRequest(
            start_date="invalid-date",
            end_date="2025-01-15",
            start_time="09:00",
            end_time="18:00",
            selected_days=["Monday"],
            duration_minutes=60,
            users=[User(email="test@example.com")]
        )

def test_appointment_request_schema():
    """AppointmentRequestスキーマのバリデーションテスト"""
    # 正常なケース
    appointment = AppointmentRequest(
        candidate="2025-01-10T10:00:00,2025-01-10T11:00:00",
        users=["test@example.com"],
        lastname="山田",
        firstname="太郎",
        company="株式会社テスト",
        email="candidate@example.com",
        token="test-token"
    )
    assert appointment.candidate == "2025-01-10T10:00:00,2025-01-10T11:00:00"
    assert appointment.users == ["test@example.com"]
    assert appointment.lastname == "山田"
    assert appointment.firstname == "太郎"
    assert appointment.company == "株式会社テスト"
    assert appointment.email == "candidate@example.com"
    assert appointment.token == "test-token"

    # candidateがNoneの場合
    appointment_none = AppointmentRequest(
        candidate=None,
        users=["test@example.com"],
        lastname="山田",
        firstname="太郎",
        company="株式会社テスト",
        email="candidate@example.com",
        token="test-token"
    )
    assert appointment_none.candidate is None

def test_form_data_schema():
    """FormDataスキーマのバリデーションテスト"""
    # 正常なケース
    form_data = FormData(
        start_date="2025-01-10",
        end_date="2025-01-15",
        start_time="09:00",
        end_time="18:00",
        selected_days=["Monday", "Tuesday"],
        duration_minutes=60,
        users=[User(email="test@example.com")]
    )
    assert form_data.start_date == "2025-01-10"
    assert form_data.end_date == "2025-01-15"
    assert form_data.start_time == "09:00"
    assert form_data.end_time == "18:00"
    assert form_data.selected_days == ["Monday", "Tuesday"]
    assert form_data.duration_minutes == 60
    assert len(form_data.users) == 1
    assert form_data.isConfirmed is False  # デフォルト値
    assert form_data.candidates is None  # デフォルト値
    assert form_data.event_ids is None  # デフォルト値

def test_appointment_response_schema():
    """AppointmentResponseスキーマのバリデーションテスト"""
    # 正常なケース
    response = AppointmentResponse(
        message="予定を登録しました",
        subjects=["面接: 山田 太郎"],
        meeting_urls=["https://teams.microsoft.com/l/meetup-join/..."],
        users=["test@example.com"]
    )
    assert response.message == "予定を登録しました"
    assert response.subjects == ["面接: 山田 太郎"]
    assert response.meeting_urls == ["https://teams.microsoft.com/l/meetup-join/..."]
    assert response.users == ["test@example.com"]

def test_availability_response_schema():
    """AvailabilityResponseスキーマのバリデーションテスト"""
    # 正常なケース
    common_times = [
        (datetime(2025, 1, 10, 10, 0), datetime(2025, 1, 10, 11, 0)),
        (datetime(2025, 1, 10, 14, 0), datetime(2025, 1, 10, 15, 0))
    ]
    response = AvailabilityResponse(common_availability=common_times)
    assert response.common_availability == common_times 