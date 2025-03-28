import logging
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import JSONResponse

from app.internal.cosmos import create_form_data, get_form_data
from app.internal.graph_api import get_schedules, parse_availability
from app.utils.time_utils import time_string_to_float, slot_to_time, find_common_availability
from app.schemas import ScheduleRequest, FormData

router = APIRouter(tags=["forms"])
logger = logging.getLogger(__name__)


@router.post("/storeFormData", response_model=dict)
def store_form_data(payload: FormData = Body(...)):
    """
    クライアントから送信されたフォームデータを Cosmos DB に保存し、一意のトークン（id）を返すエンドポイント
    payload には、users, candidates, start_time, end_time, duration_minutes などが含まれる前提
    """
    try:
        token = create_form_data(payload.model_dump())
        return JSONResponse(content={"token": token})
    except Exception as e:
        logger.error(f"フォームデータの保存に失敗しました: {e}")
        raise HTTPException(status_code=500, detail="Failed to store form data")


@router.get("/retrieveFormData", response_model=FormData)
def retrieve_form_data(token: str = Query(..., description="保存済みフォームデータのトークン")):
    """
    指定されたトークンから Cosmos DB に保存されたフォームデータ（JSON）を復元して返すエンドポイント。
    また、面接担当者の最新の空き時間も取得して返します。
    """
    try:
        item = get_form_data(token)
        
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
                logger.error(f"空き時間の取得に失敗しました: {e}")

        return FormData(**item)
    except Exception as e:
        logger.error(f"Token が見つかりません: {e}")
        raise HTTPException(status_code=404, detail="Token not found")
