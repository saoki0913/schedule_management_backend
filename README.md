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
│   ├── core/                # コア機能の実装
│   │   ├── security.py      # 認証・認可関連
│   │   └── exceptions.py    # カスタム例外クラス
│   │
│   ├── models/              # データモデルの定義
│   │   └── schemas.py       # Pydanticモデル
│   │
│   ├── services/            # ビジネスロジックの実装
│   │   ├── calendar.py      # カレンダー関連の処理
│   │   ├── email.py         # メール送信関連の処理
│   │   └── cosmos.py        # データベース関連の処理
│   │
│   └── api/                 # APIエンドポイントの実装
│       └── endpoints/       # 各エンドポイントの実装
│           ├── form.py      # フォーム関連のエンドポイント
│           └── schedule.py  # スケジュール関連のエンドポイント
│
└── tests/                   # テストコード
```

## セットアップ

### 前提条件

- Python 3.9以上
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
        "BACKEND_URL": "http://localhost:7071",
        "FRONT_URL": "http://localhost:3000"
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

#### POST /api/storeFormData
フォームデータを保存し、一意のトークンを返す

```json
{
    "users": ["user1@example.com", "user2@example.com"],
    "candidates": ["2024-03-20 10:00", "2024-03-20 11:00"],
    "start_time": "09:00",
    "end_time": "18:00",
    "duration_minutes": 60
}
```

#### GET /api/retrieveFormData
保存されたフォームデータを取得

```
Query Parameters:
- token: フォームデータのトークン
```

#### GET /api/reschedule
予定の再調整

```
Query Parameters:
- token: フォームデータのトークン
- confirm: 確認フラグ（boolean）
```

### スケジュール関連

#### POST /api/get_availability
空き時間の取得

```json
{
    "start_date": "2024-03-20",
    "end_date": "2024-03-25",
    "start_time": "09:00",
    "end_time": "18:00",
    "selected_days": ["Monday", "Tuesday", "Wednesday"],
    "duration_minutes": 60,
    "users": [
        {"email": "user1@example.com"},
        {"email": "user2@example.com"}
    ]
}
```

#### POST /api/appointment
面接予定の作成

```json
{
    "candidate": "2024-03-20 10:00, 2024-03-20 11:00",
    "users": ["user1@example.com", "user2@example.com"],
    "lastname": "山田",
    "firstname": "太郎",
    "company": "株式会社テスト",
    "email": "candidate@example.com",
    "token": "form-token"
}
```

## エラーハンドリング

APIは以下のカスタム例外を使用してエラーを処理します：

- `TokenNotFoundError`: トークンが見つからない場合
- `AuthenticationError`: 認証に失敗した場合
- `DatabaseError`: データベース操作に失敗した場合
- `CalendarError`: カレンダー操作に失敗した場合
- `EmailError`: メール送信に失敗した場合

## テスト

```bash
# テストの実行
pytest

# カバレッジレポートの生成
pytest --cov=app tests/
```

## 開発ガイドライン

1. **コードスタイル**
   - PEP 8に準拠
   - 型ヒントの使用
   - ドキュメンテーション文字列の追加

2. **コミットメッセージ**
   - 変更内容を明確に説明
   - 関連するIssue番号の参照
   - 変更の種類（feat, fix, docs, style, refactor, test, chore）の明示

3. **ブランチ戦略**
   - main: 本番環境用
   - develop: 開発用
   - feature/*: 新機能開発用
   - fix/*: バグ修正用

## トラブルシューティング

### よくある問題と解決方法

1. **認証エラー**
   - 環境変数が正しく設定されているか確認
   - Azure ADの設定を確認

2. **データベース接続エラー**
   - Cosmos DBの接続文字列を確認
   - ネットワーク設定を確認

3. **カレンダー同期エラー**
   - Graph APIの権限を確認
   - アクセストークンの有効期限を確認

## ライセンス

このプロジェクトは[MITライセンス](LICENSE)の下で公開されています。 