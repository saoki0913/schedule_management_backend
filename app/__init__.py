import azure.functions as func
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.routers import form, schedule

# FastAPI アプリケーションの初期化
app = FastAPI(
    title="Schedule Management API",
    description="面接・打ち合わせ等のスケジュール調整APIです",
    version="1.0.0"
)

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切なオリジンに制限することを推奨
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# ルーターの登録
app.include_router(form.router, prefix="", tags=["forms"])
app.include_router(schedule.router, prefix="", tags=["schedule"])

# ルートパスのエンドポイント
@app.get("/")
def read_root():
    return {"message": "Schedule Management API is running"}
