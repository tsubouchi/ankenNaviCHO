#!/bin/bash

# テスト環境のセットアップスクリプト

echo "テスト環境をセットアップしています..."

# 必要なライブラリをインストール
pip install psutil flask requests

echo "テスト環境のセットアップが完了しました"

# 実行権限を設定
chmod +x test_process_management.py
chmod +x test_app.py
chmod +x check_processes.sh

echo "テストを実行するには以下のコマンドを実行してください:"
echo "./test_process_management.py"
echo ""
echo "プロセス状態を確認するには以下のコマンドを実行してください:"
echo "./check_processes.sh" 