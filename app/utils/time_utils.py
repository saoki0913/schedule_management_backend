from datetime import datetime, timedelta
from typing import List

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


def parse_slot(start_date: str, common_slot: str):
    """
    common_slot: "21.5 - 22.5" のような文字列をパースし、
                開始datetime, 終了datetime をタプルで返す
    """
    start_str, end_str = common_slot.split("-")
    start_str = start_str.strip()  # "21.5"
    end_str = end_str.strip()    # "22.5"

    # float に変換
    start_hour = float(start_str)
    end_hour = float(end_str)

    start_dt = parse_time_str_to_datetime(start_date, start_hour)
    end_dt = parse_time_str_to_datetime(start_date, end_hour)

    return start_dt, end_dt


def slot_to_time(start_date: str, common_slots: list) -> list:
    """
    文字列形式のスロット情報をdatetimeオブジェクトに変換する
    
    例：
     ['21.5 - 22.5', '22.0 - 23.0', '22.5 - 23.5', '23.0 - 24.0', 
     '23.5 - 24.5', '24.0 - 25.0', '24.5 - 25.5', '25.0 - 26.0', 
     '25.5 - 26.5', '26.0 - 27.0', '26.5 - 27.5', '27.0 - 28.0', 
     '27.5 - 28.5', '28.0 - 29.0', '28.5 - 29.5', '29.0 - 30.0', 
     '29.5 - 30.5', '30.0 - 31.0', '30.5 - 31.5', '31.0 - 32.0', 
     '31.5 - 32.5', '32.0 - 33.0', '32.5 - 33.5', '44.0 - 45.0', 
     '44.5 - 45.5', '45.0 - 46.0']
    """
    common_time_list = []
    for common_slot in common_slots:
        common_time_list.append(parse_slot(start_date, common_slot))
    
    return common_time_list


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

    # 1. 必要な連続スロット数を算出 (30分単位)
    required_slots = duration_minutes // 30

    # 2. 各ユーザーの空き時間を set 化
    user_availability_sets = [set(slots) for slots in free_slots_list]

    # 3. 全ユーザー共通の空き時間を取得
    if len(user_availability_sets) == 0:
        return []
    common_slots = set.intersection(*user_availability_sets)

    # 4. 開始時刻でソート
    sorted_common_slots = sorted(common_slots, key=lambda slot: slot[0])

    # 5. "隣接"関係(連続しているか)をもとにグラフを作る
    #    ここでは slot -> [次の連続slot, ...] の辞書を作る
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

    # 6. BFS を使って"連続スロットのかたまり(連続コンポーネント)"を探索
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

    # 7. 必要な連続スロット数を満たす部分を抽出
    result = []
    for component in connected_components:
        # 例えば [slotA, slotB, slotC, slotD] とあり、
        # required_slots=2 なら A,B や B,C や C,D のペアが候補になる
        for i in range(len(component) - required_slots + 1):
            start = component[i][0]
            end = component[i + required_slots - 1][1]
            # スロットを文字列としてまとめる
            result.append(f"{start} - {end}")

    # 8. 結果を開始時刻で再ソートして重複削除する
    result = list(sorted(set(result), key=lambda x: float(x.split(" - ")[0])))
    
    return result


def find_common_availability_participants(free_slots_list, duration_minutes, required_participants, users):
    """
    指定された人数(required_participants)以上のユーザーが空いている時間帯の
    共通スロットを探す関数。

    Parameters:
        free_slots_list (list): すべてのユーザーのスケジュール情報。
            例: [
                    [(9.0, 9.5), (11.0, 11.5), ...],  # ユーザー1の空き時間
                    [(9.0, 9.5), (12.0, 12.5), ...],    # ユーザー2の空き時間
                    ...
                ]
        duration_minutes (int): 必要な空き時間の長さ (分)。
        required_participants (int): この時間帯に空いている必要があるユーザーの最低人数。
        users (list): ユーザーのリスト。

    Returns:
        list: 空き時間のスロット(文字列)と、その時間帯に空いているユーザーの情報のタプルのリスト。
              例: [('9.0 - 9.5', [user1, user2, user3]), ('10.0 - 10.5', [user2, user3, user4]), ...]
    """
    if not free_slots_list or required_participants <= 0:
        return []

    # 各スロットで空いているユーザーを記録
    slot_users = {}
    for i, user_slots in enumerate(free_slots_list):
        user = users[i] if i < len(users) else f"User-{i}"
        for slot in user_slots:
            if slot not in slot_users:
                slot_users[slot] = []
            slot_users[slot].append(user)

    # 必要人数以上が空いているスロットだけ抽出
    available_slots = []
    for slot, available_users in slot_users.items():
        if len(available_users) >= required_participants:
            available_slots.append((slot, available_users))

    # スロットを開始時間でソート
    available_slots.sort(key=lambda x: x[0][0])

    if not available_slots:
        return []

    # 連続したスロットを見つける
    result = []
    # 30分単位で必要なスロット数（切り上げ）
    required_slots = (duration_minutes + 29) // 30  

    # 連続したスロットの集まりを探す
    continuous_groups = []
    current_group = [available_slots[0]]

    for i in range(1, len(available_slots)):
        prev_slot, prev_users = current_group[-1]
        curr_slot, curr_users = available_slots[i]

        # 前のスロットと連続しているか
        if abs(prev_slot[1] - curr_slot[0]) < 1e-2:
            current_group.append(available_slots[i])
        else:
            # 連続していない場合は新しいグループを開始
            if len(current_group) >= required_slots:
                continuous_groups.append(current_group)
            current_group = [available_slots[i]]

    # 最後のグループをチェック
    if len(current_group) >= required_slots:
        continuous_groups.append(current_group)

    # 連続しているスロットのグループから、必要な時間枠を抽出
    for group in continuous_groups:
        for i in range(len(group) - required_slots + 1):
            # i から required_slots 区画分を抜き出し
            window = group[i : i + required_slots]
            
            # 最初のスロット利用者を起点にセットで共通ユーザーを計算
            # Userオブジェクトとstringの両方に対応できるよう修正
            common_users = set()
            for user in window[0][1]:
                # Userオブジェクトの場合はemailフィールドを取得、文字列の場合はそのまま使用
                if hasattr(user, 'email'):
                    common_users.add(user.email)
                else:
                    common_users.add(user)
                    
            # 残りのウィンドウで共通ユーザーを絞り込む
            for _, users_list in window[1:]:
                current_users = set()
                for user in users_list:
                    if hasattr(user, 'email'):
                        current_users.add(user.email)
                    else:
                        current_users.add(user)
                common_users &= current_users
                
            if len(common_users) >= required_participants:
                # スロットを文字列形式に変換
                start_slot = window[0][0]
                end_slot = window[required_slots-1][0]
                slot_str = f"{start_slot[0]} - {end_slot[1]}"
                
                # (スロット文字列, 共通ユーザー一覧) を結果に追加
                result.append((slot_str, list(common_users)))
                
    return result
