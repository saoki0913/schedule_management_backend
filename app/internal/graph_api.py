import requests
import urllib.parse
import logging
from fastapi import HTTPException
import time

from app.dependencies import get_access_token
from app.config import SYSTEM_SENDER_EMAIL
from app.utils.formatters import format_candidate_date

logger = logging.getLogger(__name__)


def get_schedules(schedule_req):
    """
    Microsoft Graph API の getSchedule エンドポイントを使用して、ユーザーのスケジュール情報を取得
    
    Parameters:
        schedule_req: スケジュールリクエストオブジェクト
        
    Returns:
        dict: Graph APIからのレスポンス（ユーザーの空き時間情報）
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
    Graph API のレスポンスデータ（availabilityView）を解析し、指定された時間の空き時間を探す

    Parameters:
        response_json: Graph APIからのレスポンス
        start_hour: 開始時間（float形式）
        end_hour: 終了時間（float形式）
        
    Returns:
        list: 空き時間スロットのリスト
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
                slot_end = slot_start + slot_duration
                # タプルでリストに追加
                free_slots.append((slot_start, slot_end))

        free_slots_list.append(free_slots)
    return free_slots_list


def create_event_payload(appointment_req, start_str: str, end_str: str) -> dict:
    """
    AppointmentRequest の情報をもとに、Graph API に送信するイベント情報を作成する。
    
    Parameters:
        appointment_req: 予約リクエストオブジェクト
        start_str: 開始日時
        end_str: 終了日時
        
    Returns:
        dict: イベント作成用のペイロード
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
    
    Parameters:
        user_email: イベント登録対象のユーザーメールアドレス
        event: イベントデータ
        headers: APIリクエストヘッダー
        
    Returns:
        dict: APIレスポンス
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
        logger.error(f"予定登録エラー for {user_email}: {response.status_code}, {response.text}")
        raise HTTPException(
            status_code=response.status_code,
            detail=f"ユーザー {user_email} に対する予定登録エラー: {response.text}"
        )
    return response.json()


def register_event_with_retry(user_email: str, event: dict, headers: dict, max_retries=3) -> dict:
    """
    リトライ機能付きでイベント登録を行う関数
    
    Parameters:
        user_email: イベント登録対象のユーザーメールアドレス
        event: イベントデータ
        headers: APIリクエストヘッダー
        max_retries: 最大リトライ回数
        
    Returns:
        dict: APIレスポンス
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
    logger.error(f"最大リトライ回数に達しました: {user_email}")
    raise last_exception


def send_email_graph(access_token, sender_email, to_email, subject, body):
    """
    Microsoft Graph API を使ってメールを送信する関数
    
    Parameters:
        access_token: Microsoft Graph APIのアクセストークン
        sender_email: 送信元メールアドレス
        to_email: 宛先メールアドレス
        subject: メール件名
        body: メール本文
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
    
    response = requests.post(endpoint, headers=headers, json=email_data)
    response.raise_for_status()
    if response.status_code == 202:
        logger.info("メールが送信されました。")
    else:
        logger.error(f"メール送信に失敗しました: {response.text}")
