from __future__ import annotations

"""FastAPI エントリポイント (main.py)
Flask 実装を置き換えた最小構成。今後ここへ既存 API を徐々に移植する。
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import subprocess, sys, glob, time
from datetime import datetime
import logging
import json
import firebase_admin
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

from utils.common import (
    initialize_app_environment,
    verify_firebase_token,
    load_settings,
    logger,
    save_settings,
    acquire_app_lock,
)
from utils.job_history import (
    load_filtered_json,
    get_all_filtered_json_files,
    load_checks,
    save_checks,
    clear_old_job_data,
    clear_job_data,
)
import chromedriver_manager
from updater import check_for_updates, perform_update, get_update_status, start_background_update, stop_background_update
from bulk_apply import get_router

# デバッグログ設定（コンテナ起動問題のトラブルシューティング用）
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("anken-navi")

# アプリケーション初期化前のログ
logger.info(f"Starting application. Environment: {os.environ.get('FASTAPI_ENV', 'development')}")
logger.info(f"FIREBASE_SERVICE_ACCOUNT_JSON exists: {os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON') is not None}")
logger.info(f"OPENAI_API_KEY exists: {os.environ.get('OPENAI_API_KEY') is not None}")
logger.info(f"APP_DATA_DIR: {os.environ.get('APP_DATA_DIR', 'not set')}")

BASE_DIR = Path(__file__).resolve().parent

# ------------------------------------------------------------
# LifeSpan管理（アプリケーション初期化前に定義）
# ------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時
    logger.info("Application startup: initializing components")
    
    # ヘルスチェック用の基本設定のみ初期化
    try:
        # 基本的な初期化だけ行う
        logger.info("Basic initialization only for startup")
        initialize_app_environment()
    except Exception as e:
        logger.error(f"Error during basic initialization: {e}")
    
    # バックグラウンドサービスは別タスクで遅延起動（ヘルスチェック通過後に初期化）
    @app.on_event("startup")
    async def startup_background_services():
        # ロックファイル取得で多重起動を防止
        try:
            acquire_app_lock().__enter__()
        except BlockingIOError:
            logger.warning("Another instance is already running, shutdown.")
            import sys
            sys.exit(0)
        
        logger.info("Delayed startup of background services")
        try:
            # データディレクトリの準備
            from fix_settings_patch import get_app_paths
            app_paths = get_app_paths()
            logger.info(f"Using app data directory: {app_paths['data_dir']}")
            
            # バックグラウンドサービス起動
            if not os.environ.get("SKIP_CHROME_SETUP", ""):
                logger.info("Setting up ChromeDriver")
                try:
                    chromedriver_manager.setup_driver()
                except Exception as e:
                    logger.error(f"ChromeDriver setup error: {e}")
            
            if not os.environ.get("SKIP_UPDATES", ""):
                logger.info("Starting background update checker")
                try:
                    check_for_updates()
                except Exception as e:
                    logger.error(f"Update checker error: {e}")
                
            logger.info("All background services started successfully")
        except Exception as e:
            logger.error(f"Error starting background services: {e}")
    
    # LifeSpan管理を続行
    yield
    
    # 終了時
    logger.info("Application shutdown: cleaning up")
    try:
        if not os.environ.get("SKIP_UPDATES", ""):
            stop_background_update()
            logger.info("Background update checker stopped")
        
        if not os.environ.get("SKIP_CHROME_SETUP", ""):
            chromedriver_manager.cleanup()
            logger.info("ChromeDriver cleaned up")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# ------------------------------------------------------------
# FastAPI アプリケーション
# ------------------------------------------------------------

# アプリケーション設定の前に追加ロギング
logger.info("Initializing FastAPI application...")

# FastAPIアプリケーション初期化
app = FastAPI(
    title="案件ナビ", 
    description="案件管理アプリケーション",
    version="1.0.0",
    lifespan=lifespan,  # LifeSpan管理を接続
)

# static / templates マウント
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
# csrf_token 未使用でもテンプレエラー回避
templates.env.globals["csrf_token"] = lambda: ""

# ---------------------------------
# 公開トップページ
# ---------------------------------

@app.get("/top", response_class=HTMLResponse)
async def top(request: Request) -> HTMLResponse:
    """トップページ (公開)"""
    context = {"request": request, "settings": load_settings()}
    return templates.TemplateResponse("top.html", context)