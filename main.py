import azure.functions as func

# FastAPI 関連
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse

# 標準ライブラリ
import os
import logging
import urllib.parse
import uuid
from datetime import datetime, timedelta
import time

# サードパーティライブラリ
from pydantic import BaseModel
import requests
from msal import ConfidentialClientApplication
from dateutil.parser import parse
from azure.cosmos import CosmosClient, PartitionKey, exceptions

# デバッグ用（本番環境では削除推奨）
import ipdb

# 環境変数から設定を取得
cosmos_endpoint = os.getenv("COSMOS_DB_ENDPOINT")
cosmos_key = os.getenv("COSMOS_DB_KEY")
cosmos_database_name = "FormDataDB"
cosmos_container_name = "FormDataContainer"
userId = os.getenv("userId")
tenant_id = os.getenv("TENANT_ID")
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")

partition_key = "FormData"

# Cosmos DB クライアントの初期化
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.create_database_if_not_exists(id=cosmos_database_name)
container = database.create_container_if_not_exists(
    id=cosmos_container_name,
    partition_key=PartitionKey(path="/partitionKey"),
    offer_throughput=400,
    default_ttl=36000 # アイテムの TTL を 36000 秒（10時間）に設定
)

# FastAPI アプリケーションの初期化
app = FastAPI()

# ベースのURLを設定
# backend_url = "http://localhost:7071"
backend_url = "https://func-sche.azurewebsites.net"

# front_url = "http://localhost:3000"
front_url = "https://purple-water-0b7f3e600.6.azurestaticapps.net"


# リクエストボディのスキーマ定義
class User(BaseModel):
    email: str

class ScheduleRequest(BaseModel):
    start_date: str    # "2025-01-10"
    end_date: str      # "2025-01-15"
    start_time: str    # "09:00"
    end_time: str      # "18:00"
    selected_days: list[str]
    duration_minutes: int  # 打合せ時間(分)
    users: list[User]      # 社内ユーザー
    time_zone: str = "Tokyo Standard Time"

class AppointmentRequest(BaseModel):
    candidate: str | None  # "none" または "開始日時, 終了日時" の文字列
    users: list[str]
    lastname: str
    firstname: str
    company: str
    email: str
    token: str

# フォームデータを保存するエンドポイント
@app.post("/storeFormData")
def store_form_data(payload: dict):
    """
    クライアントから送信されたフォームデータを Cosmos DB に保存し、一意のトークン（id）を返すエンドポイント
    payload には、users, candidates, start_time, end_time, duration_minutes などが含まれる前提
    """
    token = str(uuid.uuid4())
    # Cosmos DB では id と PartitionKey が必要（ここでは PartitionKey を固定値 "FormData" に設定）
    data = {
        "id": token,
        "partitionKey": "FormData",
        **payload
    }
    try:
        container.create_item(body=data)
    except Exception as e:
        logging.error(f"フォームデータの保存に失敗しました: {e}")
        raise HTTPException(status_code=500, detail="Failed to store form data")
    return JSONResponse(content={"token": token})

# トークンからフォームデータを復元するエンドポイント
@app.get("/retrieveFormData")
def retrieve_form_data(token: str = Query(..., description="保存済みフォームデータのトークン")):
    """
    指定されたトークンから Cosmos DB に保存されたフォームデータ（JSON）を復元して返すエンドポイント。
    また、面接担当者の最新の空き時間も取得して返します。
    """
    try:
        # PartitionKey は "FormData" 固定で設定
        item = container.read_item(item=token, partition_key="FormData")
        # 不要なシステムプロパティを削除
        for key in ["_rid", "_self", "_etag", "_ts"]:
            item.pop(key, None)
        # フォームが未確定の場合のみ、最新の空き時間を取得
        if not item.get("isConfirmed", False):           
            try:
                # フォームデータから ScheduleRequest を作成
                schedule_request = ScheduleRequest(
                    start_date=item["start_date"],  
                    end_date=item["end_date"], 
                    start_time=item["start_time"],
                    end_time=item["end_time"],
                    selected_days=item["selected_days"],
                    duration_minutes=item["duration_minutes"],
                    users=item["users"],
                    time_zone="Tokyo Standard Time"       
                )                

                # 最新の空き時間を取得
                schedule_info = get_schedules(schedule_request)
                start_hour = time_string_to_float(schedule_request.start_time)
                end_hour = time_string_to_float(schedule_request.end_time)
                free_slots_list = parse_availability(schedule_info, start_hour, end_hour)
                common_slots = find_common_availability(free_slots_list, schedule_request.duration_minutes)
                common_times = slot_to_time(schedule_request.start_date, common_slots)
                
                # datetime オブジェクトを文字列に変換
                formatted_candidates = []
                for start_dt, end_dt in common_times:
                    formatted_candidates.append([
                        start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                        end_dt.strftime("%Y-%m-%dT%H:%M:%S")
                    ])
                
                # フォームデータに最新の空き時間を追加
                item["candidates"] = formatted_candidates
            except Exception as e:
                logging.error(f"空き時間の取得に失敗しました: {e}")

        return JSONResponse(content=item)
    except Exception as e:
        logging.error(f"フォームデータの取得に失敗しました: {e}")
        raise HTTPException(status_code=500, detail="フォームデータの取得に失敗しました")

# 候補日を取得するエンドポイント
@app.post("/get_availability")
def get_availability(schedule_req: ScheduleRequest):
    """
    指定されたユーザリストと日付・時間帯における空き時間候補を返す
    """
    try:
        schedule_info = get_schedules(schedule_req)
        start_hour = time_string_to_float(schedule_req.start_time)
        end_hour = time_string_to_float(schedule_req.end_time)
        free_slots_list= parse_availability(
            schedule_info, 
            start_hour,
            end_hour
        )
        common_slots = find_common_availability(free_slots_list, schedule_req.duration_minutes)
        common_times = slot_to_time(schedule_req.start_date, common_slots)
    except Exception as e:
        logging.error(f"候補日の取得に失敗しました: {e}")
        raise HTTPException(status_code=500, detail="候補日の取得に失敗しました")
    return {"comon_availability": common_times}

@app.post("/appointment")
def create_appointment(appointment_req: AppointmentRequest, background_tasks: BackgroundTasks):
    """
    クライアントから送信された候補情報をもとに、面接担当者の予定表に Outlook の予定を登録する。
    candidate が null（または "none"）の場合は予定登録せずメッセージを返す。
    candidate が有効な場合は "開始日時, 終了日時" の形式で渡されるものとする。
    """
    try:
        # candidate が "none" または None の場合は、予定登録せずその旨返す
        if appointment_req.candidate is None or appointment_req.candidate.lower() == "none":
            return JSONResponse(content={
                "message": "候補として '可能な日程がない' が選択されました。予定は登録されません。"
            })

        # 候補文字列をパースして開始・終了時刻を取得
        start_str, end_str, selected_candidate = parse_candidate(appointment_req.candidate)

        # Outlook に登録するイベント情報の構築
        event = create_event_payload(appointment_req, start_str, end_str)

        # アクセストークン取得
        access_token = get_access_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        created_events = []
        event_ids = {}  # ユーザー毎のイベントIDを格納する辞書

        # 各面接担当者の予定表にイベントを登録
        for user_email in appointment_req.users:
            event_resp = register_event_with_retry(user_email, event, headers)
            created_events.append(event_resp)
            # イベント登録に成功した場合、Graph API のレスポンスからイベントIDを取得
            event_id = event_resp.get("id")
            if event_id:
                event_ids[user_email] = event_id

        # イベントIDをフォームデータに保存しておく（後でキャンセル時に利用）
        update_form_with_events(appointment_req.token, event_ids)

        # Outlook への登録完了後、他フォームから候補日の削除およびフォームの確定処理を実行
        finalize_form(appointment_req.token, selected_candidate)

        # 作成された各イベントから件名とオンライン会議のURLを抽出
        subjects = [evt.get("subject") for evt in created_events]
        meeting_url = [evt.get("onlineMeeting", {}).get("joinUrl") for evt in created_events]

        # 非重要な処理は非同期で行う
        background_tasks.add_task(
            send_confirmation_emails, 
            access_token, 
            appointment_req, 
            meeting_url
        )
        
        return JSONResponse(content={
            "message": "予定を登録しました。確認メールは別途送信されます。",
            "subjects": subjects,
            "meeting_urls": meeting_url,
            "users": appointment_req.users
        })
    except Exception as e:
        error_detail = str(e)
        logging.error(f"予定登録エラー: {error_detail}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"予定登録中にエラーが発生しました: {error_detail}"
        )


@app.get("/reschedule")
def reschedule(
    token: str = Query(..., description="再調整用のフォームのトークン"),
    confirm: bool = Query(False, description="キャンセル処理実行の確認フラグ")
):
    """
    リスケジュール用リンクにアクセスされた場合、Cosmos DB のフォームデータから
    作成済みのイベントID情報を取得し、各面接担当者のカレンダーから対象のイベントを削除する。
    その後、フォームの isConfirmed フィールドを False に戻し、フォームを再利用可能にする。
    
    ※ confirm が False の場合、確認画面を表示します。
    """
    # フォームデータを取得
    try:
        form = container.read_item(item=token, partition_key="FormData")
    except Exception as e:
        logging.error(f"Token が見つかりません: {e}")
        raise HTTPException(status_code=404, detail="Token not found")

    # イベントが存在しなければキャンセル処理は不要 → そのままフォームへ遷移
    if "event_ids" not in form:
        redirect_url = f"{front_url}/appointment?token={token}"
        return RedirectResponse(url=redirect_url, status_code=302)

    # 未確認の場合、確認画面を表示する
    if not confirm:
        confirm_url = f"{backend_url}/reschedule?token={token}&confirm=true"
        cancel_url = f"{front_url}/appointment?token={token}"
        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>日程再調整の確認</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-100 flex items-center justify-center min-h-screen">
            <div class="bg-white shadow-xl rounded-lg p-12 max-w-xl text-center">
            <h1 class="text-3xl font-bold mb-6">日程再調整の確認</h1>
            <p class="mb-8 text-lg">
                本当に日程の再調整を行いますか？<br>
                ※この操作を実行すると、既存の予定が削除されます。
            </p>
            <div class="flex justify-center space-x-6">
                <a href="{confirm_url}" class="inline-block bg-red-500 hover:bg-red-700 text-white font-bold py-3 px-6 rounded text-xl">
                    再調整する
                </a>
                <a href="{cancel_url}" class="inline-block bg-gray-500 hover:bg-gray-700 text-white font-bold py-3 px-6 rounded text-xl">
                    キャンセル
                </a>
            </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=200)

    # 確認済みの場合、処理を実行する
    try:
        access_token = get_access_token()
    except Exception as e:
        logging.error(f"認証トークンの取得に失敗しました: {e}")
        raise HTTPException(status_code=500, detail="認証トークンの取得に失敗しました。")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    event_ids = form["event_ids"]
    # 各面接担当者のカレンダーから該当イベントを削除する
    for user_email, event_id in event_ids.items():
        encoded_email = urllib.parse.quote(user_email)
        encoded_event_id = urllib.parse.quote(event_id, safe='')
        delete_url = f"https://graph.microsoft.com/v1.0/users/{encoded_email}/calendar/events/{encoded_event_id}"
        response = requests.delete(delete_url, headers=headers)
        if response.status_code >= 400:
            logging.error(f"予定削除エラー for {user_email}: {response.status_code} {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"ユーザー {user_email} の予定削除エラー: {response.text}"
            )

    # フォームを再利用可能にするため、isConfirmed を False に戻し、event_ids を削除する
    form["isConfirmed"] = False
    form.pop("event_ids", None)
    container.replace_item(item=form["id"], body=form)

    # 処理完了後、再調整用のリンクをボタンにして表示する
    link = f"{front_url}/appointment?token={token}"
    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>再調整完了</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100 flex items-center justify-center min-h-screen">
        <div class="bg-white shadow-xl rounded-lg p-12 max-w-xl text-center">
        <h1 class="text-3xl font-bold mb-6">キャンセル処理完了</h1>
        <p class="mb-8 text-lg">
            既存の予定は削除されました。<br>
            以下のボタンから新たに日程をご入力ください。
        </p>
        <a href="{link}" class="inline-block bg-blue-500 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded text-xl">
            日程再調整画面へ
        </a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)



def update_form_with_events(token: str, event_ids: dict) -> None:
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            form = container.read_item(item=token, partition_key="FormData")
            form["event_ids"] = event_ids
            container.replace_item(item=form["id"], body=form)
            return
        except exceptions.CosmosHttpResponseError as e:
            retry_count += 1
            if retry_count >= max_retries:
                logging.error(f"Cosmos DB更新に失敗: {e}")
                raise
            time.sleep(2 ** retry_count)  # 指数バックオフ

def parse_candidate(candidate: str):
    """
    "開始日時, 終了日時" の形式の文字列をパースして開始日時、終了日時、
    及び候補リスト（[開始日時, 終了日時]）を返す。
    """
    try:
        start_str, end_str = [s.strip() for s in candidate.split(",")]
        selected_candidate = [start_str, end_str]
        return start_str, end_str, selected_candidate
    except Exception as e:
        logging.error(f"開始日時, 終了日時の形式の文字列をパースに失敗しました: {e}")
        raise HTTPException(status_code=400, detail="開始日時, 終了日時の形式の文字列をパースに失敗しました.")


def create_event_payload(appointment_req: AppointmentRequest, start_str: str, end_str: str) -> dict:
    """
    AppointmentRequest の情報をもとに、Graph API に送信するイベント情報を作成する。
    """
    return {
        "subject": f"【{appointment_req.company}/{appointment_req.lastname}{appointment_req.firstname}様】日程確定",
        "body": {
            "contentType": "HTML",
            "content": (
                "日程調整が完了しました。詳細は下記の通りです。<br><br>"
                "・氏名<br>"
                f"{appointment_req.lastname} {appointment_req.firstname}<br><br>"
                "・所属<br>"
                f"{appointment_req.company}<br><br>"
                "・メールアドレス<br>"
                f"{appointment_req.email}<br><br>"
                "・日程<br>"
                f"{format_candidate_date(appointment_req.candidate)}<br><br>"
            )
        },
        "start": {
            "dateTime": start_str,
            "timeZone": "Tokyo Standard Time"
        },
        "end": {
            "dateTime": end_str,
            "timeZone": "Tokyo Standard Time"
        },
        "allowNewTimeProposals": True,
        "isOnlineMeeting": True,
        "onlineMeetingProvider": "teamsForBusiness"
    }


def register_event_for_user(user_email: str, event: dict, headers: dict) -> dict:
    """
    指定された user_email の予定表に対して、Graph API を使用してイベントを登録する。
    登録に失敗した場合は HTTPException を発生させる。
    """
    encoded_email = urllib.parse.quote(user_email)
    graph_url = f"https://graph.microsoft.com/beta/users/{encoded_email}/calendar/events"
    
    # タイムアウト設定を延長（30秒→60秒）
    response = requests.post(
        graph_url, 
        headers=headers, 
        json=event, 
        timeout=60
    )
    if response.status_code >= 400:
        logging.error(f"予定登録エラー for {user_email}: {response.status_code}, {response.text}")
        raise HTTPException(
            status_code=response.status_code,
            detail=f"ユーザー {user_email} に対する予定登録エラー: {response.text}"
        )
    return response.json()

def register_event_with_retry(user_email: str, event: dict, headers: dict, max_retries=3) -> dict:
    """
    リトライ機能付きでイベント登録を行う関数
    """
    retry_count = 0
    last_exception = None
    
    while retry_count < max_retries:
        try:
            return register_event_for_user(user_email, event, headers)
        except Exception as e:
            last_exception = e
            retry_count += 1
            # 指数バックオフ（リトライ間隔を徐々に広げる）
            time.sleep(2 ** retry_count)  # 2秒、4秒、8秒...
    
    # リトライ上限に達した場合
    logging.error(f"最大リトライ回数に達しました: {user_email}")
    raise last_exception

def finalize_form(token: str, selected_candidate: list) -> None:
    """
    他のフォームから使用された候補日を削除し、対象フォームを使用済みにする。
    """
    try:
        remove_candidate_from_other_forms(token, selected_candidate)
        confirm_form(token)
    except Exception as e:
        logging.error(f"候補日の削除に失敗しました: {e}")


def send_confirmation_emails(access_token: str, appointment_req: AppointmentRequest, meeting_url: list) -> None:
    """
    内部向けおよび先方向けの確認メール送信処理をまとめる。
    """
    try:
        send_appointment_emails(access_token, appointment_req, meeting_url)
    except Exception as e:
        logging.error(f"内部向け確認メール送信に失敗しました: {e}")
    try:
        send_appointment_emails_client(access_token, appointment_req, meeting_url)
    except Exception as e:
        logging.error(f"先方向け確認メール送信に失敗しました: {e}")


def send_email_graph(access_token, sender_email, to_email, subject, body):
    """
    Microsoft Graph API を使ってメールを送信する関数
    """
    endpoint = f"https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail"
    
    # 署名の前に本文を配置するための特殊な区切り文字を追加
    modified_body = (
        "<div style=\"font-family: Calibri, Arial, Helvetica, sans-serif;\">"
        "<!--BeginSignature-->\n"  # 署名の前に配置するための特殊タグ
        f"{body}\n"
        "<!--EndSignature-->\n"
        "</div>"
    )  
    email_data = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",  # テキストからHTMLに変更
                "content": modified_body
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": to_email
                    }
                }
            ]
        }
    }   
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }  
    try:
        response = requests.post(endpoint, headers=headers, json=email_data)
        response.raise_for_status()
        if response.status_code == 202:
            logging.info(f"メールが送信されました（送信先: {to_email}）。")
        else:
            logging.error(f"メール送信に失敗しました（送信先: {to_email}）: {response.text}")
    except Exception as e:
        logging.error(f"send_email_graph で送信先 {to_email} にメール送信中にエラーが発生しました: {e}")
        raise  # 必要に応じて再送出


def send_appointment_emails(access_token, appointment_request, meeting_url):
    """
    AppointmentRequest オブジェクトの情報を利用して、リクエストに含まれるすべてのユーザーにメールを送信する関数
    """
    system_sender_email = "crawler01@intelligentforce.co.jp"
    if isinstance(meeting_url, list):
        meeting_url = meeting_url[0]
    subject = f"【{appointment_request.company}/{appointment_request.lastname}{appointment_request.firstname}様】日程確定"
    body = (
        "日程調整が完了しました。詳細は下記の通りです。\n\n"
        f"・氏名\n{appointment_request.lastname} {appointment_request.firstname}\n"
        f"・所属\n{appointment_request.company}\n"
        f"・メールアドレス\n{appointment_request.email}\n"
        f"・日程\n{format_candidate_date(appointment_request.candidate)}\n"
        f"・会議URL\n{meeting_url}"
    )
    
    failed_emails = []
    for to_email in appointment_request.users:
        try:
            send_email_graph(access_token, system_sender_email, to_email, subject, body)
        except Exception as e:
            logging.error(f"メール送信に失敗しました（送信先: {to_email}）: {e}")
            failed_emails.append(to_email)
    
    if failed_emails:
        logging.error(f"以下のメールアドレスへの送信が失敗しました: {failed_emails}")

def send_appointment_emails_client(access_token, appointment_request, meeting_url):
    """
    先方向けに、AppointmentRequest オブジェクトの情報を元にメールを送信する関数

    Parameters:
    - access_token: アクセストークン
    - appointment_request: 以下の属性を持つオブジェクト
        - candidate: 選択された日程
        - users: 送信先メールアドレスのリスト
        - lastname: 姓
        - firstname: 名
        - company: 所属
        - email: 申込者のメールアドレス
        - token: フォームの情報を復元するトークン（アクセストークンではない）
    - meeting_url: 会議URL
    """
    # 送信元システムアドレスを指定 "system@intelligentforce.co.jp"
    system_sender_email = "crawler01@intelligentforce.co.jp"

    # meeting_urlがリストの場合、最初の要素を使用して余計なかっこを除去する
    if isinstance(meeting_url, list):
        meeting_url = meeting_url[0]

    # 件名の作成
    subject = "日程確定（インテリジェントフォース）"

    # 再調整用リンクの作成
    # ※クリック時に元の予定を自動削除する処理が連携される前提
    reschedule_link = f"{backend_url}/reschedule?token={appointment_request.token}"

    # 本文の作成（HTMLフォーマット）
    body = (
        f"{appointment_request.lastname}様<br><br>"
        "この度は日程を調整いただきありがとうございます。<br>"
        "ご登録いただいた内容、および当日の会議URLは下記の通りです。<br><br>"
        f"・氏名<br>{appointment_request.lastname} {appointment_request.firstname}<br><br>"
        f"・所属<br>{appointment_request.company}<br><br>"
        f"・メールアドレス<br>{appointment_request.email}<br><br>"
        f"・日程<br>{format_candidate_date(appointment_request.candidate)}<br><br>"
        f"・会議URL<br>{meeting_url}<br><br>"
        "※日程の再調整が必要な場合はこちらからご対応ください：<br>"
        f"{reschedule_link}<br>"
        "再調整のご対応後は、元の予定は自動的に削除されます。<br><br>"
        "以上になります。<br>"
        "当日はどうぞよろしくお願いいたします。"
    )

    # リスト内の各送信先へメールを送信
    try:
        send_email_graph(access_token, system_sender_email, appointment_request.email, subject, body)
    except Exception as e:
        logging.error(f"先方へのメール送信中にエラーが発生しました: {e}")


def remove_candidate_from_other_forms(selected_token: str, selected_candidate: list):
    # Cosmos DB の SQL クエリを作成
    # 候補日は配列の中の配列で保存されているので、ARRAY_CONTAINS を使って一致するものを検索する
    query = """
    SELECT * FROM c 
    WHERE c.partitionKey = @partitionKey 
      AND c.id != @currentToken
      AND ARRAY_CONTAINS(c.candidates, @selectedCandidate)
    """
    parameters = [
        {"name": "@partitionKey", "value": partition_key},
        {"name": "@currentToken", "value": selected_token},
        {"name": "@selectedCandidate", "value": selected_candidate},
    ]

    # クエリ実行（必要に応じて enable_cross_partition_query=True も設定しますが、ここでは同一パーティションなので不要）
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
    # 指定されたフォーム（selected_token）のドキュメントを取得するための SQL クエリを作成
    query = """
    SELECT * FROM c
    WHERE c.partitionKey = @partitionKey
      AND c.id = @currentToken
    """
    parameters = [
        {"name": "@partitionKey", "value": partition_key},  # partition_key はグローバル変数または適宜設定
        {"name": "@currentToken", "value": selected_token},
    ]
    
    # クエリ実行してフォームを取得（同一パーティション内の場合、enable_cross_partition_query は不要）
    forms = list(container.query_items(query=query, parameters=parameters))
    
    for form in forms:
        # フォームの isConfirmed フィールドを True に設定
        form["isConfirmed"] = True
        
        # 更新前に余計なシステムプロパティを削除
        for key in ["_rid", "_self", "_attachments", "_ts"]:
            form.pop(key, None)
        
        # ドキュメントを更新（replace_item を使用）
        container.replace_item(item=form["id"], body=form)

def time_string_to_float(time_str: str) -> float:
    """
    'HH:MM' 形式の文字列を、例えば "22:00" -> 22.0 のように
    小数の時間数(float)へ変換する関数。
    例:
        "17:30" -> 17.5
        "09:15" -> 9.25
        "22:00" -> 22.0
    """
    hour_str, minute_str = time_str.split(":")
    hour = int(hour_str)
    minute = int(minute_str)
    return hour + minute / 60.0


def parse_time_str_to_datetime(start_date: str, float_hour: float) -> datetime:
    """
    start_date : "YYYY-MM-DD" の形式
    float_hour: 例) 21.5 → 21時30分, 25.0 → 翌日1時0分 (24h超)
    戻り値: 上記に基づいて日付時刻を調整した datetime オブジェクト
    """
    # 1. 日付部分をパースして date オブジェクトに変換
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()  # date型

    # 2. float_hour の値から「何日先か」「何時何分か」を計算
    day_offset = int(float_hour // 24)  # 24H 以上の場合、翌日以降へ
    remainder_hours = float_hour % 24   # 24 で割った余り(0~23.999..)

    hour = int(remainder_hours)              # 時
    minute = int(round((remainder_hours - hour) * 60))  # 分 (小数点以下を分に変換)

    # 3. base_dt に day_offset 日足して (year, month, day, hour, minute) を datetime化
    new_date = start_dt + timedelta(days=day_offset)
    dt = datetime(new_date.year, new_date.month, new_date.day, hour, minute)
    return dt

def parse_slot(start_date: str, comon_slot: str):
    """
    comon_slot: "21.5 - 22.5" のような文字列をパースし、
                開始datetime, 終了datetime をタプルで返す
    """
    start_str, end_str = comon_slot.split("-")
    start_str = start_str.strip()  # "21.5"
    end_str   = end_str.strip()    # "22.5"

    # float に変換
    start_hour = float(start_str)
    end_hour   = float(end_str)

    start_dt = parse_time_str_to_datetime(start_date, start_hour)
    end_dt   = parse_time_str_to_datetime(start_date, end_hour)

    return start_dt, end_dt

# MSAL を用いたトークン取得のユーティリティ
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
                client_id=client_id,
                client_credential=client_secret,
                authority=f"https://login.microsoftonline.com/{tenant_id}"
            )
            
            result = app.acquire_token_silent(scope, account=None)
            if not result:
                result = app.acquire_token_for_client(scopes=scope)
            
            if "access_token" in result:
                return result["access_token"]
            else:
                logging.error(f"トークン取得に失敗しました: {result.get('error_description')}")
                raise Exception(f"トークン取得失敗: {result.get('error_description')}")
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                logging.error(f"最大リトライ回数に達しました: {e}")
                raise
            time.sleep(2 ** retry_count)  # 指数バックオフ

# Graph API を呼び出して空き時間情報を取得する 
def get_schedules(schedule_req: ScheduleRequest):
    """
    Microsoft Graph API の getSchedule エンドポイントを使用して、ユーザーのスケジュール情報を取得
    """
    access_token = get_access_token()
    # 特定ユーザーのスケジュールを取得したい場合
    target_user_data = schedule_req.users
    # メールアドレスのみを抽出
    target_user_email = target_user_data[0].email
    target_user_email = urllib.parse.quote(target_user_email)
    url = f"https://graph.microsoft.com/v1.0/users/{target_user_email}/calendar/getSchedule"


    body = {
        "schedules": [user.email for user in schedule_req.users],
        "startTime": {
            "dateTime": f"{schedule_req.start_date}T{schedule_req.start_time}:00",
            "timeZone": schedule_req.time_zone
        },
        "endTime": {
            "dateTime": f"{schedule_req.end_date}T{schedule_req.end_time}:00",
            "timeZone": schedule_req.time_zone
        },
        "availabilityViewInterval": 30
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    return response.json()


def parse_availability(response_json, start_hour: float, end_hour: float):
    """
    Graph API のレスポンスデータ（availabilityView）を解析し、指定された時間（duration_minutes）の空き時間を探す

    availability_view: 例) "022200002222220000"(入力の時間範囲によって、出力範囲が変化)
        - 30分ごとに '0'(空き), '1'(不明), '2'(埋まり) ... が並んだ文字列
    start_hour: float
        - 例) 9.0 (9時)
    end_hour: float
        - 例) 22.0 (22時)

    Returns: list of tuple
        - 例) [(9.0, 9.5), (12.0, 12.5), (12.5, 13.0), ...]
          空いている（'0'の）スロットだけ 30分刻みで返す
    """
    # response_json の中に schedules 配列があり、各ユーザーの availabilityView が返却される
    # availabilityView が '0' (空き), '1' (不明), '2' (埋まり) ... と 30分区切りで入っている
    # 例: '022200002222220000' などの文字列 (入力の時間範囲によって、出力範囲が変化)


    schedules_info = response_json.get("value", [])
    availabilityView_list = []
    free_slots_list = []
    # 1つのスロットが何時間か (通常 0.5 時間 = 30分)
    slot_duration = 0.5
    
    for schedule in schedules_info:
        user_email = schedule.get("scheduleId")
        availability_view = schedule.get("availabilityView")
        availabilityView_list.append(availability_view)

    for availability_view in availabilityView_list:
        # 全体で何回の 30分枠があるか
        increments = len(availability_view)
        # (終わり時刻 - 開始時刻) のなかに increments 回の30分枠が入っているはず
        total_hours = increments * slot_duration
        
        free_slots = []
        for i, c in enumerate(availability_view):
            # '0' のときだけ "空いている" と判断
            if c == '0':
                # i 番目のスロットの開始・終了時刻を計算
                slot_start = start_hour + i * slot_duration
                slot_end   = slot_start + slot_duration
                # タプルでリストに追加
                free_slots.append((slot_start, slot_end))

        free_slots_list.append(free_slots)
    return free_slots_list


def find_common_availability(free_slots_list, duration_minutes):
    """
    全ユーザーが共通して空き時間を確保できるスロットを探す関数。
    幅優先検索(BFS)を用いて、共通の連続スロットを列挙し、
    必要なスロット数を満たす時間帯を抽出する。

    Parameters:
        free_slots_list (list): すべてのユーザーのスケジュール情報。
          例: [
                [(9.0, 9.5), (11.0, 11.5), ...],  # ユーザー1の空き時間
                [(9.0, 9.5), (12.0, 12.5), ...], # ユーザー2の空き時間
                ...
              ]
        duration_minutes (int): 必要な空き時間の長さ (分)。

    Returns:
        list: 共通の空き時間スロット (文字列) のリスト。
    """
    #-------------------------------------
    # 1. 必要な連続スロット数を算出 (30分単位)
    #-------------------------------------
    required_slots = duration_minutes // 30

    #-------------------------------------
    # 2. 各ユーザーの空き時間を set 化
    #-------------------------------------
    user_availability_sets = [set(slots) for slots in free_slots_list]



    #-------------------------------------
    # 3. 全ユーザー共通の空き時間を取得
    #-------------------------------------
    if len(user_availability_sets) == 0:
        return []
    common_slots = set.intersection(*user_availability_sets)

    #-------------------------------------
    # 4. 開始時刻でソート
    #-------------------------------------
    sorted_common_slots = sorted(common_slots, key=lambda slot: slot[0])

    #-------------------------------------
    # 5. "隣接"関係(連続しているか)をもとにグラフを作る
    #    ここでは slot -> [次の連続slot, ...] の辞書を作る
    #-------------------------------------
    adjacency = {}
    for slot in sorted_common_slots:
        adjacency[slot] = []

    # ソートしたスロットを順番に見て、連続していれば互いに結びつける
    # "あるスロットが、次のスロットへ連続しているかどうか"を確認して、隣接するスロットをリストに入れる
    for i in range(len(sorted_common_slots) - 1):
        curr_slot = sorted_common_slots[i]
        next_slot = sorted_common_slots[i + 1]
        # curr_slot=(s1,e1), next_slot=(s2,e2)
        # 連続の条件: e1 == s2
        if abs(curr_slot[1] - next_slot[0]) < 1e-2:
            adjacency[curr_slot].append(next_slot)
        # 逆に next_slot から curr_slot が連続のとき (e2 == s1) も考慮する場合
        if abs(next_slot[1] - curr_slot[0]) < 1e-2:
            adjacency[next_slot].append(curr_slot)

    #-------------------------------------
    # 6. BFS を使って"連続スロットのかたまり(連続コンポーネント)"を探索
    #-------------------------------------
    visited = set()
    connected_components = []  # 連続スロット群を入れる

    for slot in sorted_common_slots:
        if slot not in visited:
            # 新たな連続かたまりを探す
            queue = [slot]
            visited.add(slot)
            connected_component = []

            # 幅優先検索 (BFS)
            while queue:
                # pop(0) でリストの先頭から取り出す形で擬似的にキューとして動作
                current = queue.pop(0) 
                connected_component.append(current)
                # 隣接する(連続する)スロットを順番に探索
                # そのスロットに隣接しているスロット群 (adjacency[current]) の中から未訪問のものをキューに追加
                for neighbor in adjacency[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            # 発見した連続コンポーネントをソート (開始時刻順に並ぶように)
            connected_component.sort(key=lambda x: x[0])
            connected_components.append(connected_component)

    #-------------------------------------
    # 7. 必要な連続スロット数を満たす部分を抽出
    #-------------------------------------
    result = []
    for component in connected_components:
        # 例えば [slotA, slotB, slotC, slotD] とあり、
        # required_slots=2 なら A,B や B,C や C,D のペアが候補になる
        for i in range(len(component) - required_slots + 1):
            start = component[i][0]
            end   = component[i + required_slots - 1][1]
            # スロットを文字列としてまとめる
            result.append(f"{start} - {end}")

    #-------------------------------------
    # 8. 結果を開始時刻で再ソートして重複削除する
    #-------------------------------------
    result = list(sorted(set(result), key=lambda x: float(x.split(" - ")[0])))

    return result

def slot_to_time(start_date: str, comon_slots: list) -> list:
    """
     ['21.5 - 22.5', '22.0 - 23.0', '22.5 - 23.5', '23.0 - 24.0', 
     '23.5 - 24.5', '24.0 - 25.0', '24.5 - 25.5', '25.0 - 26.0', 
     '25.5 - 26.5', '26.0 - 27.0', '26.5 - 27.5', '27.0 - 28.0', 
     '27.5 - 28.5', '28.0 - 29.0', '28.5 - 29.5', '29.0 - 30.0', 
     '29.5 - 30.5', '30.0 - 31.0', '30.5 - 31.5', '31.0 - 32.0', 
     '31.5 - 32.5', '32.0 - 33.0', '32.5 - 33.5', '44.0 - 45.0', 
     '44.5 - 45.5', '45.0 - 46.0']
    """
    comon_time_list = []
    for comon_slot in comon_slots:
        comon_time_list.append(parse_slot(start_date, comon_slot))
    
    return comon_time_list


def format_candidate_date(candidate: str) -> str:
    """
    候補日程文字列を整形する関数。
    
    入力例:
        "2025-03-10T10:00:00, 2025-03-10T10:30:00"
    
    出力例:
        "3/10（月）10:00~10:30"
    """
    # Python の weekday() は月曜日が 0 なので、対応する日本語の曜日を定義
    day_map = {0: "月", 1: "火", 2: "水", 3: "木", 4: "金", 5: "土", 6: "日"}
    
    try:
        # カンマで分割して開始日時と終了日時を取得
        start_str, end_str = [s.strip() for s in candidate.split(",")]
        start_dt = parse(start_str)
        end_dt = parse(end_str)
        
        # 曜日は start_dt.weekday() で取得（月：0〜日：6）
        formatted_date = (
            f"{start_dt.month}/{start_dt.day}({day_map[start_dt.weekday()]}) "
            f"{start_dt.strftime('%H:%M')}~{end_dt.strftime('%H:%M')}"
        )
        return formatted_date
    except Exception as e:
        raise ValueError("候補情報の形式が不正です。'開始日時, 終了日時' の形式で入力してください。") from e

