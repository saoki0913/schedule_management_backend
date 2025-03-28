import logging
import uuid
import time
from azure.cosmos import exceptions
from fastapi import HTTPException
from dateutil.parser import parse

from app.dependencies import container
from app.config import PARTITION_KEY

logger = logging.getLogger(__name__)


def create_form_data(payload: dict) -> str:
    """
    クライアントから送信されたフォームデータをCosmosDBに保存する
    
    Parameters:
        payload: フォームデータ
        
    Returns:
        str: 生成されたトークン
        
    Raises:
        HTTPException: 保存に失敗した場合
    """
    token = str(uuid.uuid4())
    # Cosmos DB では id と PartitionKey が必要
    data = {
        "id": token,
        "partitionKey": PARTITION_KEY,
        **payload
    }
    try:
        container.create_item(body=data)
        return token
    except Exception as e:
        logger.error(f"フォームデータの保存に失敗しました: {e}")
        raise HTTPException(status_code=500, detail="Failed to store form data")


def get_form_data(token: str) -> dict:
    """
    指定されたトークンからCosmosDBにフォームデータを取得する
    
    Parameters:
        token: フォームデータのトークン
        
    Returns:
        dict: フォームデータ
        
    Raises:
        HTTPException: データが見つからない場合
    """
    try:
        # PartitionKey は "FormData" 固定で設定
        item = container.read_item(item=token, partition_key=PARTITION_KEY)
        # 不要なシステムプロパティを削除
        for key in ["_rid", "_self", "_etag", "_ts"]:
            item.pop(key, None)
        return item
    except Exception as e:
        logger.error(f"Token が見つかりません: {e}")
        raise HTTPException(status_code=404, detail="Token not found")


def update_form_with_events(token: str, event_ids: dict) -> None:
    """
    フォームデータにイベントIDを追加する
    
    Parameters:
        token: フォームデータのトークン
        event_ids: イベントID辞書
        
    Raises:
        Exception: 更新に失敗した場合
    """
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            form = container.read_item(item=token, partition_key=PARTITION_KEY)
            form["event_ids"] = event_ids
            container.replace_item(item=form["id"], body=form)
            return
        except exceptions.CosmosHttpResponseError as e:
            retry_count += 1
            if retry_count >= max_retries:
                logger.error(f"Cosmos DB更新に失敗: {e}")
                raise
            time.sleep(2 ** retry_count)  # 指数バックオフ


def remove_candidate_from_other_forms(selected_token: str, selected_candidate: list):
    """
    選択された候補日が含まれる他のフォームからその候補日を削除する
    
    Parameters:
        selected_token: 選択されたフォームのトークン
        selected_candidate: 選択された候補日
    """
    # Cosmos DB の SQL クエリを作成
    # 候補日は配列の中の配列で保存されているので、ARRAY_CONTAINS を使って一致するものを検索する
    query = """
    SELECT * FROM c 
    WHERE c.partitionKey = @partitionKey 
      AND c.id != @currentToken
      AND ARRAY_CONTAINS(c.candidates, @selectedCandidate)
    """
    parameters = [
        {"name": "@partitionKey", "value": PARTITION_KEY},
        {"name": "@currentToken", "value": selected_token},
        {"name": "@selectedCandidate", "value": selected_candidate},
    ]

    # クエリ実行
    forms = list(container.query_items(query=query, parameters=parameters))
    
    for form in forms:
        # フォームの candidates 配列から選択された候補日と一致するものを削除
        updated_candidates = [
            c for c in form["candidates"]
            if not (parse(c[0]) == parse(selected_candidate[0]) and parse(c[1]) == parse(selected_candidate[1]))
        ]
        form["candidates"] = updated_candidates   
        # 余計なシステムプロパティを削除（更新前に行う）
        for key in ["_rid", "_self", "_attachments", "_ts"]:
            form.pop(key, None)
        # ドキュメントを更新
        container.replace_item(item=form["id"], body=form)


def confirm_form(selected_token: str):
    """
    フォームを確定状態に更新する
    
    Parameters:
        selected_token: 確定するフォームのトークン
    """
    # 指定されたフォーム（selected_token）のドキュメントを取得するためのSQLクエリを作成
    query = """
    SELECT * FROM c
    WHERE c.partitionKey = @partitionKey
      AND c.id = @currentToken
    """
    parameters = [
        {"name": "@partitionKey", "value": PARTITION_KEY},
        {"name": "@currentToken", "value": selected_token},
    ]
    
    # クエリ実行してフォームを取得
    forms = list(container.query_items(query=query, parameters=parameters))
    
    for form in forms:
        # フォームの isConfirmed フィールドを True に設定
        form["isConfirmed"] = True
        
        # 更新前に余計なシステムプロパティを削除
        for key in ["_rid", "_self", "_attachments", "_ts"]:
            form.pop(key, None)
        
        # ドキュメントを更新
        container.replace_item(item=form["id"], body=form)


def finalize_form(token: str, selected_candidate: list) -> None:
    """
    他のフォームから使用された候補日を削除し、対象フォームを使用済みにする。
    
    Parameters:
        token: フォームデータのトークン
        selected_candidate: 選択された候補日
    """
    try:
        remove_candidate_from_other_forms(token, selected_candidate)
        confirm_form(token)
    except Exception as e:
        logger.error(f"候補日の削除に失敗しました: {e}")
        raise
