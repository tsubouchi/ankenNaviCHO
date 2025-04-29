from __future__ import annotations

"""共通ユーティリティ関数・定数
Flask 依存を排除し FastAPI/Crawler などから再利用する目的で切り出したモジュール。
"""

from pathlib import Path
import json
import os
import logging
from datetime import datetime
from typing import Any, Dict

from fix_settings_patch import get_app_paths  # 既存ユーティリティを再利用

# ------------------------------------------------------------
# ロガー設定
# ------------------------------------------------------------
app_paths = get_app_paths()
log_dir = app_paths["data_dir"] / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(log_dir / "utils.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# アプリ設定ファイル関連
# ------------------------------------------------------------
SETTINGS_FILE: Path = app_paths["settings_file"]
PROMPT_FILE: Path = app_paths["data_dir"] / "crawled_data" / "prompt.txt"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "model": "gpt-4o-mini",
    "api_key": "",
    "deepseek_api_key": "",
    "max_items": 100,
    "filter_prompt": "",
    "self_introduction": "",
    "crowdworks_email": "",
    "crowdworks_password": "",
    "coconala_email": "",
    "coconala_password": "",
}


def initialize_app_environment() -> None:
    """データディレクトリ / 設定ファイルなど初期化処理"""
    data_dir: Path = app_paths["data_dir"]

    # data_dir/crawled_data 等を作成
    (data_dir / "crawled_data").mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)

    # settings.json 初期化
    if not SETTINGS_FILE.exists():
        logger.info("デフォルト設定ファイルを作成します: %s", SETTINGS_FILE)
        save_settings(DEFAULT_SETTINGS)

    # checked_jobs.json 初期化
    checks_file = data_dir / "crawled_data" / "checked_jobs.json"
    if not checks_file.exists():
        logger.info("チェック状態ファイルを作成します: %s", checks_file)
        checks_file.write_text("{}", encoding="utf-8")

    # prompt.txt 初期化
    if not PROMPT_FILE.exists():
        logger.info("prompt.txt を初期化します: %s", PROMPT_FILE)
        prompt_config = {
            "model": "gpt-4o-mini",
            "prompt": "",
            "temperature": 0,
            "max_tokens": 100,
        }
        PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROMPT_FILE.write_text(json.dumps(prompt_config, ensure_ascii=False, indent=2), encoding="utf-8")


def load_settings() -> Dict[str, Any]:
    """設定を読み込む。存在しない場合は DEFAULT_SETTINGS を返却"""
    settings = DEFAULT_SETTINGS.copy()
    try:
        if SETTINGS_FILE.exists():
            loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            settings.update(loaded)
        else:
            logger.warning("設定ファイルが見つかりません: %s", SETTINGS_FILE)
    except Exception as exc:
        logger.error("設定読み込み失敗: %s", exc)
    # prompt.txt の反映
    try:
        if PROMPT_FILE.exists():
            prompt_conf = json.loads(PROMPT_FILE.read_text(encoding="utf-8"))
            settings["filter_prompt"] = prompt_conf.get("prompt", "")
    except Exception as exc:
        logger.error("prompt.txt 読み込み失敗: %s", exc)
    return settings


def save_settings(settings: Dict[str, Any]) -> None:
    """設定を保存し、prompt.txt も同期更新"""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("設定を保存しました: %s", SETTINGS_FILE)
        # prompt.txt 同期
        prompt_conf = {
            "model": settings.get("model", "gpt-4o-mini"),
            "prompt": settings.get("filter_prompt", ""),
            "temperature": 0,
            "max_tokens": 100,
        }
        PROMPT_FILE.write_text(json.dumps(prompt_conf, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.error("設定保存失敗: %s", exc)
        raise


# ------------------------------------------------------------
# Firebase トークン検証（FastAPI 用）
# ------------------------------------------------------------
from firebase_admin import auth as fb_auth, credentials, initialize_app, get_app  # type: ignore

_firebase_initialized = False


def _init_firebase() -> None:
    global _firebase_initialized
    if _firebase_initialized:
        return
    cred_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if not cred_path:
        # Cloud Run Secret Mgr では /secrets/FIREBASE_SERVICE_ACCOUNT_JSON にマウントされる想定
        default_path = "/secrets/FIREBASE_SERVICE_ACCOUNT_JSON"
        cred_path = default_path if Path(default_path).exists() else None
    if not cred_path:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON パスが設定されていません")
    cred = credentials.Certificate(cred_path)
    initialize_app(cred)
    _firebase_initialized = True


def verify_firebase_token(id_token: str):
    """ID トークンを検証してユーザー情報を返す (無効の場合 None)"""
    try:
        _init_firebase()
        decoded = fb_auth.verify_id_token(id_token)
        return decoded  # dict 形式
    except Exception as exc:
        logger.warning("Firebase トークン検証失敗: %s", exc)
        return None 