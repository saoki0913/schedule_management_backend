import os

# 環境変数から設定を取得
COSMOS_DB_ENDPOINT = os.getenv("COSMOS_DB_ENDPOINT")
COSMOS_DB_KEY = os.getenv("COSMOS_DB_KEY")
COSMOS_DATABASE_NAME = "FormDataDB"
COSMOS_CONTAINER_NAME = "FormDataContainer"
USER_ID = os.getenv("userId")
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# パーティションキー
PARTITION_KEY = "FormData"

# URL設定
# ローカル開発用
# BACKEND_URL = "http://localhost:7071"
# FRONT_URL = "http://localhost:3000"

# 本番環境用
BACKEND_URL = "https://func-schedule.azurewebsites.net"
FRONT_URL = "https://blue-desert-046191c00.6.azurestaticapps.net"

# メール設定
SYSTEM_SENDER_EMAIL = "crawler01@intelligentforce.co.jp"

# TTL設定（秒）
DOCUMENT_TTL = 36000  # 10時間
