import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Body
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
import urllib.parse
import requests

from app.config import FRONT_URL, BACKEND_URL
from app.dependencies import get_access_token
from app.internal.cosmos import get_form_data, update_form_with_events, finalize_form
from app.internal.graph_api import get_schedules, parse_availability, create_event_payload, register_event_with_retry
from app.internal.mail import send_confirmation_emails
from app.utils.time_utils import time_string_to_float, slot_to_time, find_common_availability
from app.utils.formatters import parse_candidate
from app.schemas import (
    ScheduleRequest,
    AppointmentRequest,
    AppointmentResponse,
    AvailabilityResponse
)

router = APIRouter(tags=["schedule"])
logger = logging.getLogger(__name__)


@router.post("/get_availability", response_model=AvailabilityResponse)
def get_availability(schedule_req: ScheduleRequest):
    """
    指定されたユーザリストと日付・時間帯における空き時間候補を返す
    """
    schedule_info = get_schedules(schedule_req)
    start_hour = time_string_to_float(schedule_req.start_time)
    end_hour = time_string_to_float(schedule_req.end_time)
    free_slots_list = parse_availability(
        schedule_info, 
        start_hour,
        end_hour
    )
    common_slots = find_common_availability(free_slots_list, schedule_req.duration_minutes)
    common_times = slot_to_time(schedule_req.start_date, common_slots)
    return AvailabilityResponse(common_availability=common_times)


@router.post("/appointment", response_model=AppointmentResponse)
def create_appointment(
    background_tasks: BackgroundTasks,
    appointment_req: AppointmentRequest = Body(...)
):
    """
    クライアントから送信された候補情報をもとに、面接担当者の予定表に Outlook の予定を登録する。
    candidate が null（または "none"）の場合は予定登録せずメッセージを返す。
    candidate が有効な場合は "開始日時, 終了日時" の形式で渡されるものとする。
    """
    try:
        # candidate が "none" または None の場合は、予定登録せずその旨返す
        if appointment_req.candidate is None or appointment_req.candidate.lower() == "none":
            return AppointmentResponse(
                message="候補として '可能な日程がない' が選択されました。予定は登録されません。",
                subjects=[],
                meeting_urls=[],
                users=appointment_req.users
            )

        # 候補文字列をパースして開始・終了時刻を取得
        start_str, end_str, selected_candidate = parse_candidate(appointment_req.candidate)

        # Outlook に登録するイベント情報の構築
        event = create_event_payload(appointment_req.model_dump(), start_str, end_str)

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
            appointment_req.model_dump(), 
            meeting_url
        )
        
        return AppointmentResponse(
            message="予定を登録しました。確認メールは別途送信されます。",
            subjects=subjects,
            meeting_urls=meeting_url,
            users=appointment_req.users
        )
    except Exception as e:
        # 詳細なエラーログ
        error_detail = str(e)
        logger.error(f"予定作成エラー: {error_detail}", exc_info=True)
        
        # クライアントに詳細なエラーメッセージを返す
        raise HTTPException(
            status_code=500,
            detail=f"予定作成中にエラーが発生しました: {error_detail}"
        )


@router.get("/reschedule")
def reschedule(
    token: str = Query(
        ...,
        description="再調整用のフォームのトークン",
        example="sample-token-123"
    ),
    confirm: bool = Query(
        False,
        description="キャンセル処理実行の確認フラグ",
        example=False
    )
):
    """
    リスケジュール用リンクにアクセスされた場合、Cosmos DB のフォームデータから
    作成済みのイベントID情報を取得し、各面接担当者のカレンダーから対象のイベントを削除する。
    その後、フォームの isConfirmed フィールドを False に戻し、フォームを再利用可能にする。
    
    ※ confirm が False の場合、確認画面を表示します。
    """
    # フォームデータを取得
    try:
        form = get_form_data(token)
    except Exception as e:
        logger.error(f"Token が見つかりません: {e}")
        raise HTTPException(status_code=404, detail="Token not found")

    # イベントが存在しなければキャンセル処理は不要 → そのままフォームへ遷移
    if "event_ids" not in form:
        redirect_url = f"{FRONT_URL}/appointment?token={token}"
        return RedirectResponse(url=redirect_url, status_code=302)

    # 未確認の場合、確認画面を表示する
    if not confirm:
        confirm_url = f"{BACKEND_URL}/reschedule?token={token}&confirm=true"
        cancel_url = f"{FRONT_URL}/appointment?token={token}"
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
        logger.error(f"トークン取得に失敗しました: {e}")
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
            logger.error(f"予定削除エラー for {user_email}: {response.status_code} {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"ユーザー {user_email} の予定削除エラー: {response.text}"
            )

    # フォームを再利用可能にするため、isConfirmed を False に戻し、event_ids を削除する
    form["isConfirmed"] = False
    form.pop("event_ids", None)
    # Cosmos DBのコンテナを直接使用
    from app.dependencies import container
    from app.config import PARTITION_KEY
    container.replace_item(item=form["id"], body=form)

    # 処理完了後、再調整用のリンクをボタンにして表示する
    link = f"{FRONT_URL}/appointment?token={token}"
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
