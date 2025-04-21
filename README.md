# スケジュール管理API

面接スケジュール管理のためのAzure Functions + FastAPIベースのバックエンドAPI

## 概要

このプロジェクトは、面接スケジュール管理システムのバックエンドAPIを提供します。Azure FunctionsとFastAPIを組み合わせることで、サーバーレスアーキテクチャの利点を活かしながら、モダンなPython Webフレームワークの機能を活用します。

### 主な機能

- 面接担当者の予定表から空き時間の取得
- 面接予定の作成とTeamsミーティングの自動設定
- 予定の再調整機能
- メール通知機能

## 技術スタック

- Python 3.9+
- Azure Functions
- FastAPI
- Azure Cosmos DB
- Microsoft Graph API
- MSAL (Microsoft Authentication Library)

## プロジェクト構成

```
api/
├── app/                      # アプリケーションのメインディレクトリ
│   ├── main.py              # FastAPIアプリケーションのエントリーポイント
│   ├── config.py            # 設定値の管理
│   │
│   ├── routers/             # APIエンドポイントの実装
│   │   ├── form.py         # フォーム関連のエンドポイント
│   │   └── schedule.py     # スケジュール関連のエンドポイント
│   │
│   ├── schemas/             # リクエスト/レスポンスのスキーマ定義
│   │   ├── __init__.py     # スキーマのエクスポート
│   │   ├── form.py         # フォーム関連のスキーマ
│   │   └── schedule.py     # スケジュール関連のスキーマ
│   │
│   ├── internal/           # 内部モジュール
│   │   ├── cosmos.py      # Cosmos DB関連の処理
│   │   └── graph_api.py   # Graph API関連の処理
│   │
│   └── utils/             # ユーティリティ関数
│       └── time_utils.py  # 時間関連のユーティリティ
│
└── tests/                 # テストコード
```

## セットアップ

### 前提条件

- Python 3.10
- Azure Functions Core Tools
- Azure CLI（オプション：Azureリソースの管理用）

### 環境変数の設定

1. `local.settings.json`ファイルを作成し、以下の設定を追加：

```json
{
    "IsEncrypted": false,
    "Values": {
        "FUNCTIONS_WORKER_RUNTIME": "python",
        "COSMOS_DB_ENDPOINT": "your-cosmos-db-endpoint",
        "COSMOS_DB_KEY": "your-cosmos-db-key",
        "TENANT_ID": "your-tenant-id",
        "CLIENT_ID": "your-client-id",
        "CLIENT_SECRET": "your-client-secret",
        "userId": "your-userid",
    }
}
```

### 依存パッケージのインストール

```bash
# 仮想環境の作成と有効化
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# 依存パッケージのインストール
pip install -r requirements.txt
```

## 実行方法

### ローカル開発環境での実行

```bash
# Azure Functions Core Toolsを使用してローカルで実行
func start
```

### デプロイ

1. Azure Functionsへのデプロイ：

```bash
# Azure Functions Core Toolsを使用してデプロイ
func azure functionapp publish <function-app-name>
```

2. 環境変数の設定：
   - Azure PortalでFunction Appの設定に必要な環境変数を追加

## APIエンドポイント

### フォーム関連

#### POST /api/store_form_data
フォームデータを保存し、一意のトークンを返す

```json
{
    "start_date": "2025-01-10",
    "end_date": "2025-01-15",
    "start_time": "09:00",
    "end_time": "18:00",
    "selected_days": ["月", "火", "水", "木", "金"],
    "duration_minutes": 30,
    "users": [
        {"email": "interviewer1@example.com"},
        {"email": "interviewer2@example.com"}
    ],
    "time_zone": "Tokyo Standard Time"
}
```

#### GET /api/retrieve_form_data
保存されたフォームデータを取得

```
Query Parameters:
- token: フォームデータのトークン
```

### スケジュール関連

#### POST /api/get_availability
空き時間の取得

```json
{
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
```

#### POST /api/appointment
面接予定の作成

```json
{
    "candidate": "2025-01-10T10:00:00,2025-01-10T11:00:00",
    "users": ["interviewer1@example.com", "interviewer2@example.com"],
    "lastname": "山田",
    "firstname": "太郎",
    "company": "株式会社サンプル",
    "email": "candidate@example.com",
    "token": "sample-token-123"
}
```

#### GET /api/reschedule
予定の再調整

```
Query Parameters:
- token: フォームデータのトークン
- confirm: 確認フラグ（boolean）
```

## エラーハンドリング

APIは以下のカスタム例外を使用してエラーを処理します：

- `ScheduleManagementError`: スケジュール管理システムの基本例外クラス
- `ValidationError`: バリデーションエラー
- `DatabaseError`: データベース関連のエラー
- `APIError`: API関連のエラー

## テスト

```bash
# テストの実行
pytest

# カバレッジレポートの生成
pytest --cov=app tests/
```
