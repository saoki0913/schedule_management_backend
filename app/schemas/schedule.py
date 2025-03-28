from pydantic import BaseModel, Field
from typing import List


class AppointmentRequest(BaseModel):
    """面接予約リクエストを表すスキーマ"""
    candidate: str | None = Field(
        None,
        description="選択された候補日時（'none' または '開始日時,終了日時' の形式）"
    )
    users: List[str] = Field(..., description="面接担当者のメールアドレスリスト")
    lastname: str = Field(..., description="候補者の姓")
    firstname: str = Field(..., description="候補者の名")
    company: str = Field(..., description="候補者の所属会社")
    email: str = Field(..., description="候補者のメールアドレス")
    token: str = Field(..., description="フォームデータのトークン")

    class Config:
        json_schema_extra = {
            "example": {
                "candidate": "2025-01-10T10:00:00,2025-01-10T11:00:00",
                "users": ["interviewer1@example.com", "interviewer2@example.com"],
                "lastname": "山田",
                "firstname": "太郎",
                "company": "株式会社サンプル",
                "email": "candidate@example.com",
                "token": "sample-token-123"
            }
        }


class AppointmentResponse(BaseModel):
    """面接予約レスポンスを表すスキーマ"""
    message: str = Field(..., description="処理結果のメッセージ")
    subjects: List[str] = Field(..., description="作成された予定の件名リスト")
    meeting_urls: List[str | None] = Field(..., description="オンライン会議のURLリスト")
    users: List[str] = Field(..., description="面接担当者のメールアドレスリスト")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "予定を登録しました。確認メールは別途送信されます。",
                "subjects": ["面接: 山田 太郎 (株式会社サンプル)"],
                "meeting_urls": ["https://teams.microsoft.com/l/meetup-join/..."],
                "users": ["interviewer1@example.com", "interviewer2@example.com"]
            }
        }


class AvailabilityResponse(BaseModel):
    """空き時間候補のレスポンスを表すスキーマ"""
    common_availability: List[tuple] = Field(
        ...,
        description="共通の空き時間候補のリスト（(開始日時, 終了日時)のタプルのリスト）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "common_availability": [
                    ("2025-01-10T10:00:00", "2025-01-10T11:00:00"),
                    ("2025-01-10T14:00:00", "2025-01-10T15:00:00")
                ]
            }
        } 