#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
シンプルなテスト用Flaskアプリケーション
プロセス管理機能のテスト用
"""

from flask import Flask, jsonify, request
import os
import signal
import time
import threading
import logging
import fcntl
import errno
import psutil
from pathlib import Path

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# アプリケーション初期化
app = Flask(__name__)

# グローバル変数
LOCK_FILE = None
LOCK_FD = None

# ロックファイルのパスを取得
def get_lock_file():
    global LOCK_FILE
    if LOCK_FILE is None:
        home = Path.home()
        data_dir = home / "anken_navi_data"
        data_dir.mkdir(parents=True, exist_ok=True)
        LOCK_FILE = data_dir / "anken_navi.lock"
    return LOCK_FILE

# ロックファイルをロック
def acquire_lock(lock_file):
    global LOCK_FD
    try:
        # ロックファイルパスの親ディレクトリが存在することを確認
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        
        # ロックファイルをオープン
        lock_fd = open(lock_file, 'w')
        
        try:
            # 排他ロックを取得
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # ロック成功
            LOCK_FD = lock_fd
            return True
        except IOError:
            # ロック失敗（ファイルが既にロックされている）
            try:
                if lock_fd:
                    lock_fd.close()
            except:
                pass
            return False
    except Exception as e:
        logger.error(f"ロック取得中にエラー: {str(e)}")
        return False

# ロックファイルの解除
def release_lock():
    global LOCK_FD, LOCK_FILE
    if LOCK_FD:
        try:
            # ロック解除
            fcntl.flock(LOCK_FD, fcntl.LOCK_UN)
            
            # ファイルを閉じる
            LOCK_FD.close()
            
            # ロックファイルを削除
            try:
                if LOCK_FILE and LOCK_FILE.exists():
                    LOCK_FILE.unlink()
            except:
                pass
                
            logger.info("アプリケーションロックを解除しました")
        except Exception as e:
            logger.error(f"ロック解除中にエラー: {str(e)}")
        finally:
            LOCK_FD = None

# サーバーをシャットダウンする関数
def shutdown_server():
    """Flask サーバーを明示的に終了する"""
    try:
        logger.info("サーバーのシャットダウンを開始します")
        
        # ロックファイルを解放
        release_lock()
        
        # リクエストコンテキスト内でのみ実行
        if hasattr(request, 'environ'):
            # Werkzeugサーバーの終了関数を取得
            func = request.environ.get("werkzeug.server.shutdown")
            if func is None:
                logger.warning("Werkzeugサーバーの終了関数が見つかりません。別の方法で終了します。")
                # 非同期で終了させる
                threading.Timer(0.1, lambda: os._exit(0)).start()
            else:
                logger.info("Werkzeugサーバーを終了します")
                func()
                logger.info("サーバーのシャットダウンが完了しました")
        else:
            logger.warning("リクエストコンテキスト外で終了関数が呼び出されました。別の方法で終了します。")
            # 非同期で終了させる
            threading.Timer(0.1, lambda: os._exit(0)).start()
            
    except Exception as e:
        logger.error(f"サーバー終了処理中にエラー: {str(e)}")
        # エラーが発生した場合も強制終了（少し待ってから）
        threading.Timer(0.1, lambda: os._exit(1)).start()

# ルート
@app.route('/')
def index():
    return "テスト用サーバーが正常に動作しています"

# シャットダウンAPI
@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    """サーバーを終了するAPI"""
    logger.info("サーバー終了APIが呼び出されました")
    
    # レスポンスを返す
    response = jsonify({'status': 'success', 'message': 'サーバーを終了しています'})
    
    # リクエストが完了した後に非同期でシャットダウンを実行
    @response.call_on_close
    def on_close():
        logger.info("レスポンス送信後、シャットダウンを実行します")
        threading.Timer(0.1, shutdown_server).start()
        
    return response

# シグナルハンドラを設定
def signal_handler(sig, frame):
    """シグナル受信時の処理（SIGTERM, SIGINT）"""
    signame = {signal.SIGTERM: "SIGTERM", signal.SIGINT: "SIGINT"}.get(sig, str(sig))
    logger.info(f"シグナル {signame} を受信しました。終了処理を開始します。")
    
    # ロックファイルの解放
    release_lock()
    
    # 終了
    os._exit(0)

# 既存のプロセスを強制終了する関数
def kill_existing_process(pid):
    """指定されたPIDのプロセスを強制終了する"""
    try:
        logger.info(f"既存のプロセス {pid} を終了します")
        process = psutil.Process(pid)
        
        # プロセスを終了（SIGTERM）
        process.terminate()
        
        # プロセスが終了するまで待機（最大5秒）
        try:
            process.wait(timeout=5)
            logger.info(f"プロセス {pid} は正常に終了しました")
            return True
        except psutil.TimeoutExpired:
            # タイムアウトした場合は強制終了（SIGKILL）
            logger.warning(f"プロセス {pid} が応答しないため強制終了します")
            process.kill()
            return True
    except psutil.NoSuchProcess:
        logger.info(f"プロセス {pid} は既に終了しています")
        return True
    except Exception as e:
        logger.error(f"プロセス {pid} の終了に失敗しました: {e}")
        return False

# ロックファイルに記録されたプロセスを強制終了する
def kill_if_running(lock_file):
    """ロックファイルに記録されたプロセスを検出し、終了させる"""
    if not lock_file.exists():
        return True
    
    logger.info(f"既存のロックファイルを検出: {lock_file}")
    
    try:
        # ロックファイルの内容を読み取り
        content = lock_file.read_text().strip()
        if not content:
            logger.warning("ロックファイルが空です")
            lock_file.unlink(missing_ok=True)
            return True
        
        # PIDとポートを取得
        parts = content.split(",")
        if len(parts) < 1:
            logger.warning("ロックファイルの形式が不正です")
            lock_file.unlink(missing_ok=True)
            return True
        
        try:
            # PIDを取得して終了
            pid = int(parts[0])
            if kill_existing_process(pid):
                # プロセスの終了に成功したらロックファイルを削除
                lock_file.unlink(missing_ok=True)
                return True
            else:
                return False
        except ValueError:
            logger.warning(f"不正なPID: {parts[0]}")
            lock_file.unlink(missing_ok=True)
            return True
    except Exception as e:
        logger.error(f"ロックファイル処理中にエラー: {e}")
        try:
            lock_file.unlink(missing_ok=True)
        except:
            pass
        return False

# メインエントリーポイント
if __name__ == "__main__":
    try:
        # ポート番号を取得
        port = int(os.environ.get('PORT', 8080))
        
        # ロックファイル取得
        lock_file = get_lock_file()
        
        # シグナルハンドラを登録
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        logger.info("シグナルハンドラを登録しました")
        
        # 既存プロセスの確認と終了
        if lock_file.exists():
            logger.info("既存のロックファイルを検出しました")
            if not kill_if_running(lock_file):
                logger.error("既存プロセスの終了に失敗しました。終了します。")
                exit(1)
            logger.info("既存のプロセスを終了し、ロックファイルを削除しました")
        
        # ロック取得
        if acquire_lock(lock_file):
            # ロック成功 - PIDとポート情報をロックファイルに書き込む
            if LOCK_FD:
                LOCK_FD.write(f"{os.getpid()},{port}")
                LOCK_FD.flush()
                
            logger.info(f"アプリケーションロックを取得しました: {lock_file}")
            logger.info(f"テスト用サーバーを起動しています (ポート: {port})")
            
            # サーバー終了時にロックを解除
            import atexit
            atexit.register(release_lock)
            
            # サーバーを起動
            app.run(
                host='0.0.0.0', 
                port=port, 
                debug=False,
                use_reloader=False
            )
        else:
            logger.error("ロックファイルを取得できません。別のインスタンスが実行中の可能性があります。")
            exit(1)
    except Exception as e:
        logger.error(f"アプリケーション起動エラー: {str(e)}")
        # エラー終了時にもロックを解放
        release_lock()
        exit(1) 