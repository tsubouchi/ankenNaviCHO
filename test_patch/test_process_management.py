#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
プロセス管理とロックファイル機能のテストスクリプト
"""

import os
import sys
import time
import signal
import psutil
import subprocess
import requests
import json
from pathlib import Path

# テスト設定
TEST_PORT = 8081  # テスト用ポート番号
APP_PATH = "test_app.py"  # テスト用アプリケーションのパス
TEST_DURATION = 5  # テスト実行時間（秒）

# データディレクトリを取得する関数
def get_data_dir():
    # 環境変数からデータディレクトリを取得
    data_dir = os.environ.get("ANKEN_NAVI_DATA_DIR")
    if data_dir:
        return Path(data_dir)
    
    # 環境変数が設定されていない場合はデフォルトパス
    home = Path.home()
    return home / "anken_navi_data"

# プロセスを起動する関数
def start_process():
    print(f"📝 アプリケーションを起動します（ポート: {TEST_PORT}）...")
    
    # 環境変数を設定
    env = os.environ.copy()
    env["PORT"] = str(TEST_PORT)
    env["SKIP_NODE_SERVER"] = "1"  # テスト用にNodeサーバーはスキップ
    env["FLASK_DEBUG"] = "False"
    env["TESTING"] = "True"  # テストモードを有効化
    
    # サブプロセスとしてアプリケーションを起動
    process = subprocess.Popen(
        [sys.executable, APP_PATH],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # 行バッファリング
        universal_newlines=True
    )
    
    print(f"✅ アプリケーションを起動しました（PID: {process.pid}）")
    
    # 非同期でログを読み取るスレッド
    def read_output(stream, prefix):
        for line in stream:
            print(f"{prefix} {line.strip()}")
    
    # 標準出力と標準エラー出力を非同期で読み取る
    import threading
    threading.Thread(target=read_output, args=(process.stdout, "[アプリ出力]"), daemon=True).start()
    threading.Thread(target=read_output, args=(process.stderr, "[アプリエラー]"), daemon=True).start()
    
    # サーバーが起動するまで少し待機
    print("📝 サーバーの起動を待機しています...")
    start_time = time.time()
    max_wait_time = 10  # 最大待機時間（秒）
    
    while time.time() - start_time < max_wait_time:
        if process.poll() is not None:
            print(f"❌ アプリケーションが起動直後に終了しました（終了コード: {process.poll()}）")
            stdout, stderr = process.communicate()
            if stdout:
                print(f"[標準出力]\n{stdout}")
            if stderr:
                print(f"[標準エラー]\n{stderr}")
            return process
        
        # サーバーが応答するか確認
        try:
            response = requests.get(f"http://localhost:{TEST_PORT}")
            if response.status_code == 200 or response.status_code == 302:
                print(f"✅ サーバーが応答しました（ステータス: {response.status_code}）")
                break
        except requests.exceptions.ConnectionError:
            # まだ接続できない - 待機継続
            pass
        
        time.sleep(0.5)
    
    # 最終確認
    if process.poll() is not None:
        print(f"❌ アプリケーションが起動に失敗しました（終了コード: {process.poll()}）")
    else:
        print(f"✅ アプリケーションが正常に起動しています（PID: {process.pid}）")
    
    return process

# プロセスとその子プロセスを検索する関数
def find_processes(parent_pid):
    result = []
    try:
        parent = psutil.Process(parent_pid)
        result.append(parent)
        
        # 子プロセスを取得
        try:
            children = parent.children(recursive=True)
            result.extend(children)
        except:
            pass
    except psutil.NoSuchProcess:
        pass
    
    return result

# テスト1: 通常起動と終了
def test_normal_startup_shutdown():
    print("\n==== テスト1: 通常起動と終了 ====")
    
    # アプリケーションを起動
    process = start_process()
    
    # サーバーが起動するまで少し待機
    time.sleep(2)
    
    # プロセスが実行中か確認
    if process.poll() is not None:
        print("❌ アプリケーションが起動していません")
        return False
    
    print(f"✅ アプリケーションが正常に起動しています")
    
    # ロックファイルをチェック
    lock_file = get_data_dir() / "anken_navi.lock"
    if not lock_file.exists():
        print(f"❌ ロックファイルが見つかりません: {lock_file}")
        return False
    
    print(f"✅ ロックファイルが作成されました: {lock_file}")
    
    # シャットダウンリクエストを送信
    try:
        response = requests.post(f"http://localhost:{TEST_PORT}/api/shutdown")
        if response.status_code != 200:
            print(f"❌ シャットダウンAPIが失敗しました: {response.status_code}")
            process.terminate()
            return False
        
        print("✅ シャットダウンリクエストを送信しました")
    except Exception as e:
        print(f"❌ リクエスト中にエラーが発生しました: {str(e)}")
        process.terminate()
        return False
    
    # 終了するまで少し待機
    time.sleep(3)
    
    # プロセスが終了したか確認
    if process.poll() is None:
        print("❌ アプリケーションが終了していません")
        process.terminate()
        return False
    
    print("✅ アプリケーションが正常に終了しました")
    
    # ロックファイルが削除されたか確認
    if lock_file.exists():
        print(f"❌ ロックファイルが残っています: {lock_file}")
        return False
    
    print("✅ ロックファイルが正常に削除されました")
    return True

# テスト2: プロセス強制終了
def test_force_process_termination():
    print("\n==== テスト2: プロセス強制終了 ====")
    
    # アプリケーションを起動
    process = start_process()
    
    # サーバーが起動するまで少し待機
    time.sleep(2)
    
    # プロセスが実行中か確認
    if process.poll() is not None:
        print("❌ アプリケーションが起動していません")
        return False
    
    print(f"✅ アプリケーションが正常に起動しています")
    
    # ロックファイルをチェック
    lock_file = get_data_dir() / "anken_navi.lock"
    if not lock_file.exists():
        print(f"❌ ロックファイルが見つかりません: {lock_file}")
        process.terminate()
        return False
    
    print(f"✅ ロックファイルが作成されました: {lock_file}")
    
    # プロセスを強制終了
    print(f"📝 プロセスを強制終了します（PID: {process.pid}）...")
    process.terminate()
    
    # 終了するまで少し待機
    time.sleep(2)
    
    # ロックファイルが削除されたか確認
    if lock_file.exists():
        print(f"❌ ロックファイルが残っています: {lock_file}")
        return False
    
    print("✅ ロックファイルが正常に削除されました")
    return True

# テスト3: 既存プロセスの強制終了
def test_existing_process_termination():
    print("\n==== テスト3: 既存プロセスの強制終了 ====")
    
    # 1つ目のプロセスを起動
    process1 = start_process()
    
    # サーバーが起動するまで少し待機
    time.sleep(2)
    
    # プロセスが実行中か確認
    if process1.poll() is not None:
        print("❌ 1つ目のアプリケーションが起動していません")
        return False
    
    print(f"✅ 1つ目のアプリケーションが正常に起動しています（PID: {process1.pid}）")
    
    # 2つ目のプロセスを起動（同じポート）
    print("📝 2つ目のアプリケーションを起動します（同じポート）...")
    process2 = start_process()
    
    # 起動されるまで少し待機
    time.sleep(3)
    
    # 1つ目のプロセスが終了したか確認
    if process1.poll() is None:
        print("❌ 1つ目のアプリケーションが終了していません")
        process1.terminate()
        process2.terminate()
        return False
    
    print("✅ 1つ目のアプリケーションが正常に終了しました")
    
    # 2つ目のプロセスが実行中か確認
    if process2.poll() is not None:
        print("❌ 2つ目のアプリケーションが起動していません")
        process2.terminate()
        return False
    
    print(f"✅ 2つ目のアプリケーションが正常に起動しています（PID: {process2.pid}）")
    
    # 2つ目のプロセスも終了
    print("📝 2つ目のアプリケーションを終了します...")
    process2.terminate()
    
    # 終了するまで少し待機
    time.sleep(2)
    
    return True

# メイン処理
def main():
    print("==== プロセス管理テスト ====")
    
    # テスト1を実行
    if not test_normal_startup_shutdown():
        print("❌ テスト1が失敗しました")
    else:
        print("✅ テスト1が成功しました")
    
    # テスト2を実行
    if not test_force_process_termination():
        print("❌ テスト2が失敗しました")
    else:
        print("✅ テスト2が成功しました")
    
    # テスト3を実行
    if not test_existing_process_termination():
        print("❌ テスト3が失敗しました")
    else:
        print("✅ テスト3が成功しました")
    
    print("\n==== テスト完了 ====")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ テストが中断されました")
    except Exception as e:
        print(f"\n❌ テスト実行中にエラーが発生しました: {str(e)}")
    finally:
        # 残っているプロセスをクリーンアップ
        print("\n📝 残っているプロセスをクリーンアップしています...")
        for proc in psutil.process_iter():
            try:
                # Pythonプロセスかつapp.pyを実行しているプロセスを終了
                if "python" in proc.name().lower() and any("app.py" in cmd.lower() for cmd in proc.cmdline()):
                    print(f"📝 プロセスを終了: PID={proc.pid}")
                    proc.terminate()
            except:
                pass 