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

from utils.common import (
    initialize_app_environment,
    verify_firebase_token,
    load_settings,
    logger,
    save_settings,
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
from updater import check_for_updates, perform_update, get_update_status
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

BASE_DIR = Path(__file__).resolve().parent

# static / templates マウント
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ------------------------------------------------------------
# ライフサイクルイベント
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
        logger.info("Delayed startup of background services")
        try:
            # データディレクトリの準備
            app_paths = get_app_paths()
            logger.info(f"Using app data directory: {app_paths['data_dir']}")
            
            # バックグラウンドサービス起動
            if not os.environ.get("SKIP_CHROME_SETUP", ""):
                logger.info("Setting up ChromeDriver")
                chromedriver_manager.setup_driver()
            
            if not os.environ.get("SKIP_UPDATES", ""):
                logger.info("Starting background update checker")
                start_background_update()
                
            logger.info("All background services started successfully")
        except Exception as e:
            logger.error(f"Error starting background services: {e}")
    
    # LifeSpan管理を続行
    yield
    
    # 終了時
    logger.info("Application shutdown: cleaning up")
    try:
        stop_background_update()
        logger.info("Background update checker stopped")
        
        chromedriver_manager.cleanup()
        logger.info("ChromeDriver cleaned up")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# ------------------------------------------------------------
# 認証ユーティリティ
# ------------------------------------------------------------
async def get_current_user(request: Request) -> Dict[str, Any]:
    """Firebase ID Token を検証し、ユーザ情報を取得。未認証の場合 401"""
    id_token: Optional[str] = None

    # Authorization ヘッダー優先
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        id_token = auth_header.split(" ", 1)[1]
    else:
        # cookie に保存しているケース
        id_token = request.cookies.get("idToken")

    if not id_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user_info = verify_firebase_token(id_token)
    if not user_info:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return user_info


# ------------------------------------------------------------
# Pydantic モデル
# ------------------------------------------------------------
class UpdateSettingsPayload(BaseModel):
    model: Optional[str] = None
    max_items: Optional[int] = Field(None, ge=1, le=1000)
    api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    filter_prompt: Optional[str] = None
    self_introduction: Optional[str] = None
    crowdworks_email: Optional[str] = None
    crowdworks_password: Optional[str] = None
    coconala_email: Optional[str] = None
    coconala_password: Optional[str] = None


class FetchNewDataPayload(BaseModel):
    # 現状ボディ不要だが拡張用
    dummy: Optional[str] = None


# ------------------------------------------------------------
# ルーティング
# ------------------------------------------------------------

@app.get("/health", response_class=JSONResponse)
async def health() -> Dict[str, str]:
    """ヘルスチェックエンドポイント"""
    logger.info("Health check endpoint called")
    return {"status": "ok"}


@app.get("/", response_class=RedirectResponse, status_code=302)
async def index() -> RedirectResponse:
    """トップページへリダイレクト"""
    return RedirectResponse(url="/top")


@app.get("/top", response_class=HTMLResponse)
async def top(request: Request, user_info: Dict[str, Any] = Depends(get_current_user)) -> HTMLResponse:
    """トップページ表示 (認証必須)"""
    context = {"request": request, "user": user_info, "settings": load_settings()}
    return templates.TemplateResponse("top.html", context)


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    """ログインページ表示"""
    return templates.TemplateResponse("login.html", {"request": request})


# ------------------------------------------------------------
# プレースホルダ API (今後 Flask API をここへ移行)
# ------------------------------------------------------------

@app.get("/api/placeholder", response_class=JSONResponse)
async def placeholder_api(user_info: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {"message": "This is a placeholder endpoint.", "email": user_info.get("email")}


# ------------------------------------------------------------
# API 移植 (一部)
# ------------------------------------------------------------

@app.post("/api/update_settings", response_class=JSONResponse)
async def update_settings_api(
    payload: UpdateSettingsPayload,
    user_info: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """設定更新 API (Flask `/update_settings` 相当)"""
    try:
        settings = load_settings()
        data = payload.dict(exclude_unset=True)
        settings.update({k: v for k, v in data.items() if v is not None})
        # max_items 型チェックは Pydantic で済む
        save_settings(settings)
        return {"status": "success", "message": "設定を更新しました"}
    except Exception as exc:
        logger.error("設定更新エラー: %s", exc)
        raise HTTPException(status_code=500, detail="設定更新に失敗しました")


class CheckAuthPayload(BaseModel):
    service: str


@app.post("/api/check_auth", response_class=JSONResponse)
async def check_auth_api(
    payload: CheckAuthPayload,
    user_info: Dict[str, Any] = Depends(get_current_user),
):
    """サービス認証情報の有無をチェック"""
    service = payload.service
    settings = load_settings()
    if service == "crowdworks":
        authenticated = bool(settings.get("crowdworks_email")) and bool(settings.get("crowdworks_password"))
    elif service == "coconala":
        authenticated = bool(settings.get("coconala_email")) and bool(settings.get("coconala_password"))
    else:
        raise HTTPException(status_code=400, detail="Unknown service")
    return {"status": "success", "authenticated": authenticated}


@app.post("/api/fetch_new_data", response_class=JSONResponse)
async def fetch_new_data_api(
    payload: FetchNewDataPayload | None = None,
    user_info: Dict[str, Any] = Depends(get_current_user),
):
    """クローラーを実行し最新のフィルタリング済みデータを返却"""
    crawler_path = BASE_DIR / "crawler.py"
    if not crawler_path.exists():
        raise HTTPException(status_code=500, detail="crawler.py not found")

    python_executable = sys.executable
    logger.info("クローラー実行: %s %s", python_executable, crawler_path)

    proc = subprocess.run(
        [python_executable, str(crawler_path)], capture_output=True, text=True
    )

    if proc.returncode != 0:
        logger.error("クローラー失敗: %s", proc.stderr)
        raise HTTPException(status_code=500, detail=f"Crawler error: {proc.stderr}")

    # 少し待機してファイルが書き出されるのを待つ
    time.sleep(1)

    files = get_all_filtered_json_files()
    if not files:
        raise HTTPException(status_code=404, detail="No filtered data found")

    latest_file = files[0]["path"]
    jobs = load_filtered_json(latest_file)

    return {
        "status": "success",
        "file": latest_file,
        "job_count": len(jobs),
        "jobs": jobs,
        "crawler_stdout": proc.stdout,
    }


@app.get("/api/job_history/files", response_class=JSONResponse)
async def job_history_files(user_info: Dict[str, Any] = Depends(get_current_user)):
    return {"success": True, "job_files": get_all_filtered_json_files()}


@app.get("/api/job_history/content", response_class=JSONResponse)
async def job_history_content(file: str, user_info: Dict[str, Any] = Depends(get_current_user)):
    safe_name = os.path.basename(file)
    target_path = str((BASE_DIR / "crawled_data") / safe_name)
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="File not found")
    jobs = load_filtered_json(target_path)
    return {"success": True, "jobs": jobs, "job_count": len(jobs)}


class ClearJobPayload(BaseModel):
    file: Optional[str] = None


@app.post("/api/job_history/clear", response_class=JSONResponse)
async def job_history_clear(payload: ClearJobPayload, user_info: Dict[str, Any] = Depends(get_current_user)):
    count = clear_job_data(payload.file)  # None -> all
    return {"success": True, "deleted": count}


class ClearOldDataPayload(BaseModel):
    days: int = Field(14, ge=1)


@app.post("/api/clear_old_data", response_class=JSONResponse)
async def clear_old_data_api(payload: ClearOldDataPayload, user_info: Dict[str, Any] = Depends(get_current_user)):
    deleted = clear_old_job_data(payload.days)
    return {"success": True, "deleted": deleted}


@app.get("/api/get_checks", response_class=JSONResponse)
async def get_checks_api(user_info: Dict[str, Any] = Depends(get_current_user)):
    return {"success": True, "checks": load_checks()}


class UpdateCheckPayload(BaseModel):
    url: str
    checked: bool


@app.post("/api/update_check", response_class=JSONResponse)
async def update_check_api(payload: UpdateCheckPayload, user_info: Dict[str, Any] = Depends(get_current_user)):
    checks = load_checks()
    checks[payload.url] = {"checked": payload.checked, "updated_at": datetime.utcnow().isoformat()}
    save_checks(checks)
    return {"status": "success"}

# ---------------------- Update endpoints ----------------------

@app.post("/api/check_updates", response_class=JSONResponse)
async def check_updates_api(user_info: Dict[str, Any] = Depends(get_current_user)):
    try:
        update_available = check_for_updates()
        return get_update_status()
    except Exception as exc:
        logger.error("check updates error: %s", exc)
        raise HTTPException(status_code=500, detail="Update check failed")


@app.post("/api/perform_update", response_class=JSONResponse)
async def perform_update_api(user_info: Dict[str, Any] = Depends(get_current_user)):
    try:
        os.environ["UPDATING"] = "1"
        result = perform_update()
        os.environ["UPDATING"] = "0"
        return result
    except Exception as exc:
        os.environ["UPDATING"] = "0"
        logger.error("perform update error: %s", exc)
        raise HTTPException(status_code=500, detail="Update failed")


@app.get("/api/update_status", response_class=JSONResponse)
async def update_status_api(user_info: Dict[str, Any] = Depends(get_current_user)):
    try:
        return get_update_status()
    except Exception as exc:
        logger.error("update status error: %s", exc)
        raise HTTPException(status_code=500, detail="Status error")

# ---------------------- ChromeDriver endpoints ----------------------

@app.get("/api/chromedriver/status", response_class=JSONResponse)
async def chromedriver_status_api():
    try:
        manager = chromedriver_manager.get_instance()
        cfg = manager.config
        status = {
            "chrome_version": cfg.get("chrome_version", "unknown"),
            "driver_version": cfg.get("driver_version", "unknown"),
            "driver_path": cfg.get("driver_path", "unknown"),
            "last_check": cfg.get("last_check", "none"),
            "last_update": cfg.get("last_update", "none"),
            "is_update_running": manager.update_thread is not None and manager.update_thread.is_alive(),
        }
        return {"status": "success", "data": status}
    except Exception as exc:
        logger.error("chromedriver status error: %s", exc)
        raise HTTPException(status_code=500, detail="ChromeDriver status error")


class ChromeUpdatePayload(BaseModel):
    dummy: Optional[str] = None


@app.post("/api/chromedriver/update", response_class=JSONResponse)
async def chromedriver_update_api(payload: ChromeUpdatePayload | None = None):
    try:
        driver_path = chromedriver_manager.setup_driver()
        if driver_path:
            os.environ["SELENIUM_DRIVER_PATH"] = driver_path
            return {"status": "success", "driver_path": driver_path}
        raise HTTPException(status_code=500, detail="ChromeDriver update failed")
    except Exception as exc:
        logger.error("chromedriver update error: %s", exc)
        raise HTTPException(status_code=500, detail="ChromeDriver update error")

# --------------------- Chromedriver error template route ---------------------

@app.get("/chromedriver_error", response_class=HTMLResponse)
async def chromedriver_error(request: Request, message: str = "ChromeDriver error"):
    context = {"request": request, "error_message": message}
    return templates.TemplateResponse("error.html", context)

app.include_router(get_router(), prefix="/api")

async def get_firebase_app():
    """Firebase アプリを初期化して返す"""
    try:
        logger.info("Initializing Firebase App...")
        # Secret Managerシークレットのパスを確認
        firebase_json_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
        
        # Cloud Runでのシークレットマウント確認
        if firebase_json_path:
            logger.info(f"Using Firebase credentials from environment variable")
            try:
                # 環境変数から直接JSONとして読み込む試行
                creds = json.loads(firebase_json_path)
                logger.info("Successfully parsed Firebase JSON from environment")
            except json.JSONDecodeError:
                # 環境変数がJSONではない場合はファイルパスとして扱う
                logger.info(f"Treating as file path: {firebase_json_path}")
                if os.path.exists(firebase_json_path):
                    with open(firebase_json_path, 'r') as f:
                        creds = json.load(f)
                else:
                    logger.error(f"Firebase credentials file not found at {firebase_json_path}")
                    # Fallback to default file search
                    firebase_json_path = None
        
        if not firebase_json_path:
            # ローカル開発用にファイルを検索
            logger.info("Searching for Firebase credentials file...")
            firebase_files = glob.glob("*firebase*.json")
            if firebase_files:
                firebase_json_path = firebase_files[0]
                logger.info(f"Found Firebase credentials file: {firebase_json_path}")
                with open(firebase_json_path, 'r') as f:
                    creds = json.load(f)
            else:
                logger.error("No Firebase credentials file found")
                raise HTTPException(status_code=500, detail="Firebase credentials not available")
        
        # 認証情報を使用してFirebaseアプリを初期化
        app = firebase_admin.initialize_app(firebase_admin.credentials.Certificate(creds))
        logger.info("Firebase App initialized successfully")
        return app
    except Exception as e:
        logger.error(f"Error initializing Firebase: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Firebase initialization error: {str(e)}") 