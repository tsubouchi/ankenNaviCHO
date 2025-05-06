import os
import sys
import json
import shutil
import tempfile
import logging
import requests
import zipfile
import semver
from pathlib import Path
import subprocess
from datetime import datetime

# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/updater.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 現在のアプリバージョン
CURRENT_VERSION = "0.6.4"

# GitHubリポジトリ情報
# 注意: このリポジトリが存在しないか、リリースがない場合は404エラーになります
GITHUB_REPO_OWNER = "FoundD-oka"
GITHUB_REPO_NAME = "ankenNaviCHO"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"

# バックアップディレクトリ
BACKUP_DIR = Path("backups")

class Updater:
    def __init__(self):
        """アップデーターの初期化"""
        self.current_version = CURRENT_VERSION
        self.latest_version = None
        self.latest_download_url = None
        self.update_available = False
        self.progress = 0
        self.status = "準備完了"
        self.backup_path = None
        
        # バックアップディレクトリの作成
        if not BACKUP_DIR.exists():
            BACKUP_DIR.mkdir(parents=True)
    
    def check_for_updates(self):
        """GitHubから最新バージョン情報を取得"""
        try:
            self.status = "更新を確認中..."
            self.progress = 10
            
            # GitHubリリースAPIを呼び出す
            try:
                response = requests.get(GITHUB_API_URL, timeout=10)
                response.raise_for_status()  # HTTPエラーを例外として発生させる
                
                release_info = response.json()
                self.latest_version = release_info["tag_name"].lstrip("v")
                
                # バージョン比較（エラーハンドリングを強化）
                try:
                    # バージョン文字列が有効かチェック
                    current_v = self.current_version
                    latest_v = self.latest_version
                    
                    # semverに準拠していない場合は標準化
                    if not current_v.count('.') >= 2:
                        current_v = current_v + '.0' * (2 - current_v.count('.'))
                    if not latest_v.count('.') >= 2:
                        latest_v = latest_v + '.0' * (2 - latest_v.count('.'))
                        
                    is_newer = semver.compare(latest_v, current_v) > 0
                    logger.info(f"バージョン比較: 現在={current_v}, 最新={latest_v}, 新しいバージョンあり={is_newer}")
                    
                    if is_newer:
                        self.update_available = True
                        self.latest_download_url = release_info["zipball_url"]
                        self.status = f"新しいバージョン {self.latest_version} が利用可能です"
                        logger.info(f"新しいバージョン {self.latest_version} が見つかりました（現在: {self.current_version}）")
                    else:
                        self.update_available = False
                        self.status = "最新バージョンを使用中です"
                        logger.info(f"使用中のバージョン {self.current_version} は最新です")
                except ValueError as ve:
                    # semverパースエラー
                    logger.error(f"バージョン比較エラー: {ve}")
                    self.status = f"バージョン形式エラー: {ve}"
                    self.update_available = False
                    return False
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    # 404エラー：リリースが存在しない
                    logger.error(f"GitHubリリース情報が見つかりません: {e}")
                    self.status = f"リリース情報が見つかりません"
                    self.update_available = False
                    self.latest_version = None
                else:
                    # その他のHTTPエラー
                    logger.error(f"GitHub APIアクセスエラー: {e}")
                    self.status = f"GitHub APIアクセスエラー: {e}"
                    raise e
            except requests.exceptions.RequestException as e:
                # ネットワーク関連エラー
                logger.error(f"ネットワークエラー: {e}")
                self.status = f"ネットワーク接続エラー: {e}"
                self.update_available = False
                self.latest_version = None
            
            self.progress = 20
            return self.update_available
            
        except Exception as e:
            logger.error(f"更新の確認中にエラーが発生しました: {str(e)}")
            self.status = f"エラー: {str(e)}"
            self.progress = 0
            return False
    
    def create_backup(self):
        """現在のアプリケーションのバックアップを作成"""
        try:
            self.status = "バックアップを作成中..."
            self.progress = 30
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = BACKUP_DIR / f"backup_{self.current_version}_{timestamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 重要なファイルとディレクトリをバックアップ
            # .git, __pycache__, logs, backups, crawled_data, chromedriverを除外
            exclude_dirs = ['.git', '__pycache__', 'logs', 'backups', 'crawled_data', 'chromedriver']
            
            # バックアップ操作をログに記録
            logger.info(f"バックアップを作成中: {backup_dir}")
            
            for item in Path('.').iterdir():
                if item.name in exclude_dirs or item.name.startswith('.'):
                    continue
                
                if item.is_file():
                    shutil.copy2(item, backup_dir / item.name)
                    logger.info(f"ファイルをバックアップ: {item.name}")
                elif item.is_dir():
                    shutil.copytree(item, backup_dir / item.name, 
                                   ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                    logger.info(f"ディレクトリをバックアップ: {item.name}")
            
            self.backup_path = backup_dir
            self.progress = 40
            self.status = "バックアップ完了"
            logger.info(f"バックアップ完了: {backup_dir}")
            return True
            
        except Exception as e:
            logger.error(f"バックアップ作成中にエラーが発生しました: {str(e)}")
            self.status = f"バックアップエラー: {str(e)}"
            self.progress = 30
            return False
    
    def download_update(self):
        """最新バージョンをダウンロード"""
        try:
            self.status = "更新をダウンロード中..."
            self.progress = 50
            
            # 一時ディレクトリを作成
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                zip_path = temp_dir_path / "update.zip"
                
                # ダウンロード
                response = requests.get(self.latest_download_url, stream=True)
                response.raise_for_status()
                
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                self.progress = 60
                self.status = "ダウンロード完了、展開中..."
                
                # ZIPファイルを展開
                extract_dir = temp_dir_path / "extracted"
                extract_dir.mkdir()
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # 展開されたディレクトリを特定（通常は単一のディレクトリ）
                extracted_items = list(extract_dir.iterdir())
                if not extracted_items:
                    raise Exception("更新パッケージが空です")
                
                source_dir = extracted_items[0] if extracted_items[0].is_dir() else extract_dir
                
                self.progress = 70
                self.status = "ファイルを更新中..."
                
                # 現在のディレクトリにファイルをコピー
                # .git, __pycache__, logs, backups, crawled_data, chromedriverを除外
                exclude_dirs = ['.git', '__pycache__', 'logs', 'backups', 'crawled_data', 'chromedriver']
                
                # 更新操作をログに記録
                logger.info(f"ファイル更新を開始します。ソース: {source_dir}")
                
                # 更新ファイルを一時的なファイルリストに保存
                update_files = []
                for item in source_dir.iterdir():
                    if item.name in exclude_dirs:
                        continue
                    
                    update_files.append((item, Path('.') / item.name))
                
                # 再起動を防ぐために、Python実行ファイルを最後に更新
                python_files = [file_tuple for file_tuple in update_files if file_tuple[0].name.endswith('.py')]
                non_python_files = [file_tuple for file_tuple in update_files if not file_tuple[0].name.endswith('.py')]
                
                # まず非Pythonファイルを更新
                for src, dest in non_python_files:
                    if src.is_file():
                        shutil.copy2(src, dest)
                        logger.info(f"ファイルを更新: {src.name}")
                    elif src.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(src, dest, 
                                      ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                        logger.info(f"ディレクトリを更新: {src.name}")
                
                # 依存関係のインストール（Pythonファイル更新前に実行）
                logger.info("ファイル更新プロセスを行った後に依存関係をインストールします")

                # 最後にPythonファイルを更新
                for src, dest in python_files:
                    if src.is_file():
                        shutil.copy2(src, dest)
                        logger.info(f"Pythonファイルを更新: {src.name}")
                
            self.progress = 80
            self.status = "更新ファイルのインストール完了"
            return True
            
        except Exception as e:
            logger.error(f"更新のダウンロード中にエラーが発生しました: {str(e)}")
            self.status = f"ダウンロードエラー: {str(e)}"
            self.progress = 50
            return False
    
    def perform_update(self):
        """更新プロセス全体を実行"""
        try:
            # 更新の確認
            if not self.check_for_updates():
                # 更新が必要ない場合も成功として返す
                if self.status == "最新バージョンを使用中です":
                    return {"success": True, "message": self.status}
                
                # それ以外のエラー
                return {"success": False, "message": self.status}
            
            # バックアップの作成
            if not self.create_backup():
                logger.error(f"バックアップの作成に失敗しました: {self.status}")
                return {"success": False, "message": self.status}
            
            # 更新のダウンロードとインストール
            try:
                if not self.download_update():
                    # ロールバック処理
                    logger.error("更新に失敗したためロールバックを実行します")
                    if not self.rollback():
                        logger.error("ロールバックに失敗しました")
                        return {"success": False, "message": f"{self.status} - ロールバックにも失敗しました"}
                    else:
                        logger.info("ロールバック完了")
                        return {"success": False, "message": f"{self.status} - ロールバックしました"}
            except Exception as download_error:
                logger.error(f"更新ダウンロード中に例外が発生しました: {str(download_error)}")
                # ロールバック処理
                if not self.rollback():
                    logger.error("ロールバックに失敗しました")
                    return {"success": False, "message": f"ダウンロードエラー: {str(download_error)} - ロールバックにも失敗しました"}
                else:
                    return {"success": False, "message": f"ダウンロードエラー: {str(download_error)} - ロールバックしました"}
            
            # 依存関係のインストール
            try:
                if not self.install_dependencies():
                    # ロールバック処理
                    logger.error("依存関係のインストールに失敗したためロールバックを実行します")
                    if not self.rollback():
                        logger.error("ロールバックに失敗しました")
                        return {"success": False, "message": f"{self.status} - ロールバックにも失敗しました"}
                    else:
                        logger.info("ロールバック完了")
                        return {"success": False, "message": f"{self.status} - ロールバックしました"}
            except Exception as dep_error:
                logger.error(f"依存関係インストール中に例外が発生しました: {str(dep_error)}")
                # ロールバック処理
                if not self.rollback():
                    logger.error("ロールバックに失敗しました")
                    return {"success": False, "message": f"依存関係エラー: {str(dep_error)} - ロールバックにも失敗しました"}
                else:
                    return {"success": False, "message": f"依存関係エラー: {str(dep_error)} - ロールバックしました"}
            
            # 更新の最終段階を完了
            self.progress = 100
            self.status = f"バージョン {self.latest_version} への更新が完了しました"
            # 最後に現在のバージョンを更新
            try:
                # CURRENT_VERSIONの値を新しいバージョンに更新
                with open(__file__, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 正規表現でCURRENT_VERSION行を探す
                import re
                pattern = r'CURRENT_VERSION\s*=\s*["\'](.+?)["\']'
                new_content = re.sub(pattern, f'CURRENT_VERSION = "{self.latest_version}"', content)
                
                # 更新されたファイルを書き込む
                with open(__file__, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                logger.info(f"現在のバージョンを {self.latest_version} に更新しました")
            except Exception as ver_error:
                logger.error(f"バージョン情報の更新に失敗: {str(ver_error)}")
                # バージョン更新に失敗しても致命的ではないので続行
                
            return {"success": True, "message": self.status, "version": self.latest_version}
            
        except Exception as e:
            logger.error(f"更新プロセス中にエラーが発生しました: {str(e)}")
            self.status = f"更新エラー: {str(e)}"
            
            # エラーが発生した場合はロールバック
            try:
                logger.error("予期せぬエラーが発生したためロールバックを実行します")
                if not self.rollback():
                    logger.error("ロールバックに失敗しました")
                    return {"success": False, "message": f"{self.status} - ロールバックにも失敗しました"}
                else:
                    logger.info("ロールバック完了")
                    return {"success": False, "message": f"{self.status} - ロールバックしました"}
            except Exception as rollback_error:
                logger.error(f"ロールバック中に例外が発生しました: {str(rollback_error)}")
                return {"success": False, "message": f"{self.status} - ロールバックにも失敗しました"}
    
    def install_dependencies(self):
        """依存関係をインストール"""
        try:
            self.status = "依存関係をインストール中..."
            self.progress = 85
            
            # requirements.txtが存在する場合、依存関係をインストール
            req_file = Path("requirements.txt")
            if req_file.exists():
                logger.info("requirements.txtを使用して依存関係をインストールします")
                
                # 一時ディレクトリにrequirements.txtをコピー
                # これにより元のファイルの監視によるリロードを防止
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_req_path = Path(temp_dir) / "temp_requirements.txt"
                    shutil.copy2(req_file, temp_req_path)
                    
                    logger.info(f"依存関係のインストールに一時ファイルを使用: {temp_req_path}")
                    
                    # アプリケーション再起動を防ぐためにサブプロセスを分離して実行
                    # --no-deps オプションと --no-cache-dir オプションを追加して最小限のインストールを実行
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-r", str(temp_req_path), "--no-deps", "--no-cache-dir"], 
                        check=False, capture_output=True, text=True
                    )
                
                # 結果の詳細ログ記録
                logger.info(f"pip install 終了コード: {result.returncode}")
                if result.stdout:
                    logger.info(f"pip install 結果: {result.stdout}")
                if result.stderr:
                    logger.warning(f"pip install 警告/エラー: {result.stderr}")
                
                # エラーチェック
                if result.returncode != 0:
                    logger.error(f"依存関係のインストールが失敗しました（コード: {result.returncode}）")
                    raise Exception(f"依存関係のインストールが失敗しました: {result.stderr}")
                
                logger.info("依存関係のインストールが正常に完了しました")
            else:
                logger.info("requirements.txtが見つからないため依存関係のインストールをスキップします")
            
            self.progress = 90
            self.status = "依存関係のインストール完了"
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"依存関係のインストール中にプロセスエラーが発生しました: {e}")
            logger.error(f"標準出力: {e.stdout}")
            logger.error(f"標準エラー: {e.stderr}")
            self.status = f"依存関係エラー: {e}"
            self.progress = 85
            return False
        except Exception as e:
            logger.error(f"依存関係のインストール中にエラーが発生しました: {str(e)}")
            self.status = f"依存関係エラー: {str(e)}"
            self.progress = 85
            return False
    
    def rollback(self):
        """更新に失敗した場合、バックアップから復元"""
        try:
            if not self.backup_path or not self.backup_path.exists():
                logger.error("バックアップパスが指定されていないか、存在しません")
                raise Exception("バックアップが見つかりません")
            
            self.status = "ロールバック中..."
            self.progress = 95
            
            # バックアップから復元
            # .git, __pycache__, logs, backups, crawled_data, chromedriverを除外
            exclude_dirs = ['.git', '__pycache__', 'logs', 'backups', 'crawled_data', 'chromedriver']
            
            logger.info(f"ロールバックを開始します: {self.backup_path}")
            
            for item in self.backup_path.iterdir():
                if item.name in exclude_dirs:
                    continue
                
                dest_path = Path('.') / item.name
                
                if item.is_file():
                    shutil.copy2(item, dest_path)
                    logger.info(f"ファイルを復元: {item.name}")
                elif item.is_dir():
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    shutil.copytree(item, dest_path)
                    logger.info(f"ディレクトリを復元: {item.name}")
            
            self.status = "ロールバック完了"
            self.progress = 100
            logger.info("ロールバック処理が完了しました")
            return True
            
        except Exception as e:
            logger.error(f"ロールバック中にエラーが発生しました: {str(e)}")
            self.status = f"ロールバックエラー: {str(e)}"
            return False
    
    def get_status(self):
        """現在の更新ステータスを取得"""
        status_data = {
            "progress": self.progress,
            "status": self.status,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "update_available": self.update_available
        }
        
        # 新しいバージョンが利用可能な場合は、成功ステータスを追加
        if self.update_available:
            status_data["status"] = "success"
            status_data["message"] = f"新しいバージョン {self.latest_version} が利用可能です"
        
        return status_data

# グローバルインスタンス
updater = Updater()

# 更新の確認
def check_for_updates():
    return updater.check_for_updates()

# 更新の実行
def perform_update():
    return updater.perform_update()

# ステータスの取得
def get_update_status():
    return updater.get_status() 

# ------------------------------------------------------------
# 互換性プレースホルダ (main.py からインポートされる関数)
# ------------------------------------------------------------

_update_thread = None  # type: ignore

def start_background_update():
    """バックグラウンドで定期的に update チェックを回すプレースホルダ。Cloud Run では未使用。"""
    import threading, time
    global _update_thread
    if _update_thread and _update_thread.is_alive():
        return  # すでに起動済み

    def _loop():
        while True:
            try:
                check_for_updates()
            except Exception as exc:  # pragma: no cover
                logger.warning("background update check failed: %s", exc)
            time.sleep(3600)  # 1 時間おき

    _update_thread = threading.Thread(target=_loop, daemon=True)
    _update_thread.start()


def stop_background_update():
    """バックグラウンドスレッドを停止 (簡易版)"""
    global _update_thread
    _update_thread = None 