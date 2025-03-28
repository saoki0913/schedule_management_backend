from dateutil.parser import parse

def parse_candidate(candidate: str):
    """
    "開始日時, 終了日時" の形式の文字列をパースして開始日時、終了日時、
    及び候補リスト（[開始日時, 終了日時]）を返す。
    
    Parameters:
        candidate (str): "YYYY-MM-DDTHH:MM:SS, YYYY-MM-DDTHH:MM:SS"形式の文字列
        
    Returns:
        tuple: (開始日時文字列, 終了日時文字列, [開始日時, 終了日時]のリスト)
    
    Raises:
        ValueError: フォーマットが正しくない場合
    """
    try:
        start_str, end_str = [s.strip() for s in candidate.split(",")]
        selected_candidate = [start_str, end_str]
        return start_str, end_str, selected_candidate
    except Exception as e:
        raise ValueError("候補情報の形式が不正です。'開始日時, 終了日時' の形式で入力してください。")


def format_candidate_date(candidate: str) -> str:
    """
    候補日程文字列を整形する関数。
    
    入力例:
        "2025-03-10T10:00:00, 2025-03-10T10:30:00"
    
    出力例:
        "3/10（月）10:00~10:30"
        
    Parameters:
        candidate (str): "YYYY-MM-DDTHH:MM:SS, YYYY-MM-DDTHH:MM:SS"形式の文字列
        
    Returns:
        str: "M/D（曜日）HH:MM~HH:MM"形式の文字列
        
    Raises:
        ValueError: フォーマットが正しくない場合
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
