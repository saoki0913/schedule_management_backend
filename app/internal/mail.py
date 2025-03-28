import logging
from app.config import SYSTEM_SENDER_EMAIL, BACKEND_URL
from app.internal.graph_api import send_email_graph
from app.utils.formatters import format_candidate_date

logger = logging.getLogger(__name__)


def send_confirmation_emails(access_token: str, appointment_req, meeting_url: list) -> None:
    """
    内部向けおよび先方向けの確認メール送信処理をまとめる。
    
    Parameters:
        access_token: Microsoft Graph APIのアクセストークン
        appointment_req: 予約リクエストオブジェクト
        meeting_url: Teams会議URL
    """
    send_appointment_emails(access_token, appointment_req, meeting_url)
    send_appointment_emails_client(access_token, appointment_req, meeting_url)


def send_appointment_emails(access_token, appointment_request, meeting_url):
    """
    AppointmentRequest オブジェクトの情報を利用して、リクエストに含まれるすべてのユーザーにメールを送信する関数

    Parameters:
        access_token: アクセストークン
        appointment_request: 以下の属性を持つオブジェクト
            - candidate: 選択された日程（例："2025-03-13T09:00:00, 2025-03-13T09:30:00"）
            - users: 送信先メールアドレスのリスト
            - lastname: 姓
            - firstname: 名
            - company: 所属
            - email: 申込者のメールアドレス
            - token: フォームの情報を復元するトークン（アクセストークンではない）
        meeting_url: 会議URL
    """
    # meeting_urlがリストの場合、最初の要素を使用して余計なかっこを除去する
    if isinstance(meeting_url, list):
        meeting_url = meeting_url[0]

    # 件名の作成
    subject = f"【{appointment_request.company}/{appointment_request.lastname}{appointment_request.firstname}様】日程確定"

    # 本文の作成
    body = (
        "日程調整が完了しました。詳細は下記の通りです。\n\n"
        f"・氏名\n{appointment_request.lastname} {appointment_request.firstname}\n"
        f"・所属\n{appointment_request.company}\n"
        f"・メールアドレス\n{appointment_request.email}\n"
        f"・日程\n{format_candidate_date(appointment_request.candidate)}\n"
        f"・会議URL\n{meeting_url}"
    )

    # リスト内の各送信先へメールを送信
    for to_email in appointment_request.users:
        send_email_graph(access_token, SYSTEM_SENDER_EMAIL, to_email, subject, body)


def send_appointment_emails_client(access_token, appointment_request, meeting_url):
    """
    先方向けに、AppointmentRequest オブジェクトの情報を元にメールを送信する関数

    Parameters:
        access_token: アクセストークン
        appointment_request: 以下の属性を持つオブジェクト
            - candidate: 選択された日程
            - users: 送信先メールアドレスのリスト
            - lastname: 姓
            - firstname: 名
            - company: 所属
            - email: 申込者のメールアドレス
            - token: フォームの情報を復元するトークン（アクセストークンではない）
        meeting_url: 会議URL
    """
    # meeting_urlがリストの場合、最初の要素を使用して余計なかっこを除去する
    if isinstance(meeting_url, list):
        meeting_url = meeting_url[0]

    # 件名の作成
    subject = "日程確定（インテリジェントフォース）"

    # 再調整用リンクの作成
    # ※クリック時に元の予定を自動削除する処理が連携される前提
    reschedule_link = f"{BACKEND_URL}/reschedule?token={appointment_request.token}"

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
    send_email_graph(access_token, SYSTEM_SENDER_EMAIL, appointment_request.email, subject, body)
