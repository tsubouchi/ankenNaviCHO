from __future__ import annotations

"""案件履歴・チェック状態関連ユーティリティ"""

from pathlib import Path
from typing import Dict, List
import json
import glob
import os
import re
from datetime import datetime, timedelta

from utils.common import app_paths, logger

DATA_DIR: Path = app_paths["data_dir"]
CRAWLED_DIR: Path = DATA_DIR / "crawled_data"
CHECKS_FILE: Path = CRAWLED_DIR / "checked_jobs.json"

# ------------------------------------------------------------
# チェック状態
# ------------------------------------------------------------

def load_checks() -> Dict[str, Dict]:
    if CHECKS_FILE.exists():
        try:
            return json.loads(CHECKS_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("checked_jobs.json 読み込み失敗: %s", exc)
    return {}


def save_checks(checks: Dict[str, Dict]) -> None:
    CHECKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKS_FILE.write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")

# ------------------------------------------------------------
# 履歴ファイルユーティリティ
# ------------------------------------------------------------

def get_all_filtered_json_files() -> List[Dict]:
    json_files = glob.glob(str(CRAWLED_DIR / "*_filtered.json"))
    if not json_files:
        return []
    file_info: List[Dict] = []
    for file_path in json_files:
        file_name = os.path.basename(file_path)
        match = re.search(r"jobs_(\d{8})_(\d{6})_filtered\.json", file_name)
        if not match:
            continue
        date_str, time_str = match.groups()
        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
        try:
            job_count = len(json.loads(Path(file_path).read_text(encoding="utf-8")))
        except Exception:
            job_count = 0
        file_info.append(
            {
                "path": file_path,
                "name": file_name,
                "date": formatted_date,
                "timestamp": f"{date_str}_{time_str}",
                "job_count": job_count,
            }
        )
    file_info.sort(key=lambda x: x["timestamp"], reverse=True)
    return file_info


def load_filtered_json(file_path: str):
    try:
        return json.loads(Path(file_path).read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("filtered json 読み込み失敗: %s", exc)
        return []

# ------------------------------------------------------------
# 古いデータ削除
# ------------------------------------------------------------

def clear_old_job_data(days: int = 14) -> int:
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0
    for path in glob.glob(str(CRAWLED_DIR / "jobs_*.json")):
        m = re.search(r"jobs_(\d{8})_(\d{6})", os.path.basename(path))
        if not m:
            continue
        ts_str = f"{m.group(1)}_{m.group(2)}"
        try:
            file_dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            if file_dt < cutoff:
                os.remove(path)
                removed += 1
        except Exception:
            continue
    return removed

# ------------------------------------------------------------
# データ削除ユーティリティ
# ------------------------------------------------------------

def clear_job_data(file_path: str | None = None) -> int:
    """履歴データを削除
    :param file_path: 特定ファイルのみ削除する場合パスを指定
    :return: 削除したファイル数
    """
    if file_path:
        safe_name = os.path.basename(file_path)
        target_path = CRAWLED_DIR / safe_name
        if target_path.exists():
            target_path.unlink()
            raw_file = Path(str(target_path).replace("_filtered.json", ".json"))
            if raw_file.exists():
                raw_file.unlink()
            return 1
        return 0
    # 全削除 (settings.json / checked_jobs.json を除く)
    count = 0
    for p in CRAWLED_DIR.glob("*.json"):
        if p.name.endswith(("settings.json", "checked_jobs.json")):
            continue
        p.unlink()
        count += 1
    return count 