import logging
import time
from msal import ConfidentialClientApplication
from azure.cosmos import CosmosClient, PartitionKey

from app.config import (
    COSMOS_DB_ENDPOINT, COSMOS_DB_KEY, 
    COSMOS_DATABASE_NAME, COSMOS_CONTAINER_NAME,
    PARTITION_KEY, TENANT_ID, CLIENT_ID, CLIENT_SECRET,
    DOCUMENT_TTL
)

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cosmos DB クライアントの初期化
cosmos_client = CosmosClient(COSMOS_DB_ENDPOINT, COSMOS_DB_KEY)
database = cosmos_client.create_database_if_not_exists(id=COSMOS_DATABASE_NAME)
container = database.create_container_if_not_exists(
    id=COSMOS_CONTAINER_NAME,
    partition_key=PartitionKey(path="/partitionKey"),
    offer_throughput=400,
    default_ttl=DOCUMENT_TTL
)

# Microsoft Graph API用のアクセストークン取得
def get_access_token() -> str:
    """
    Microsoft Graph API にアクセスするための認証トークンを取得
    """
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            scope = ["https://graph.microsoft.com/.default"]  # Graph API 全般の既定スコープ
            
            app = ConfidentialClientApplication(
                client_id=CLIENT_ID,
                client_credential=CLIENT_SECRET,
                authority=f"https://login.microsoftonline.com/{TENANT_ID}"
            )
            
            result = app.acquire_token_silent(scope, account=None)
            if not result:
                result = app.acquire_token_for_client(scopes=scope)
            
            if "access_token" in result:
                return result["access_token"]
            else:
                logger.error(f"トークン取得に失敗しました: {result.get('error_description')}")
                raise Exception(f"トークン取得失敗: {result.get('error_description')}")
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                logger.error(f"最大リトライ回数に達しました: {e}")
                raise
            time.sleep(2 ** retry_count)  # 指数バックオフ
