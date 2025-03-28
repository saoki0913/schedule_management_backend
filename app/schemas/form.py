from pydantic import BaseModel, Field
from typing import List


class User(BaseModel):
    """ユーザー情報を表すスキーマ"""
    email: str = Field(..., description="ユーザーのメールアドレス")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }


class ScheduleRequest(BaseModel):
    """スケジュールリクエストを表すスキーマ"""
    start_date: str = Field(..., description="開始日 (YYYY-MM-DD形式)")
    end_date: str = Field(..., description="終了日 (YYYY-MM-DD形式)")
    start_time: str = Field(..., description="開始時間 (HH:MM形式)")
    end_time: str = Field(..., description="終了時間 (HH:MM形式)")
    selected_days: List[str] = Field(..., description="選択された曜日のリスト")
    duration_minutes: int = Field(..., description="打合せ時間（分）")
    users: List[User] = Field(..., description="面接担当者のリスト")
    time_zone: str = Field(
        default="Tokyo Standard Time",
        description="タイムゾーン"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2025-01-10",
                "end_date": "2025-01-15",
                "start_time": "09:00",
                "end_time": "18:00",
                "selected_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "duration_minutes": 60,
                "users": [
                    {"email": "interviewer1@example.com"},
                    {"email": "interviewer2@example.com"}
                ],
                "time_zone": "Tokyo Standard Time"
            }
        }


class FormData(BaseModel):
    """フォームデータを表すスキーマ"""
    start_date: str
    end_date: str
    start_time: str
    end_time: str
    selected_days: List[str]
    duration_minutes: int
    users: List[User]
    time_zone: str = "Tokyo Standard Time"
    isConfirmed: bool = False
    candidates: List[List[str]] | None = None
    event_ids: dict | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2025-01-10",
                "end_date": "2025-01-15",
                "start_time": "09:00",
                "end_time": "18:00",
                "selected_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "duration_minutes": 60,
                "users": [
                    {"email": "interviewer1@example.com"},
                    {"email": "interviewer2@example.com"}
                ],
                "time_zone": "Tokyo Standard Time",
                "isConfirmed": False,
                "candidates": [
                    ["2025-01-10T10:00:00", "2025-01-10T11:00:00"],
                    ["2025-01-10T14:00:00", "2025-01-10T15:00:00"]
                ],
                "event_ids": None
            }
        } 