#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
from pathlib import Path

# frozen環境をシミュレートする
sys.frozen = True
sys._MEIPASS = os.path.dirname(os.path.abspath(__file__))

# fix_settings_patch.pyをインポート
from fix_settings_patch import get_app_paths, get_data_dir_from_env

# ロガー設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_frozen_environment():
    """frozen環境（.app）をシミュレートしてテスト"""
    logger.info("frozen環境のシミュレーションを開始します")
    
    # アプリケーションパスを取得
    paths = get_app_paths()
    print(f"バンドルディレクトリ: {paths['bundle_dir']}")
    print(f"データディレクトリ: {paths['data_dir']}")
    print(f"設定ファイル: {paths['settings_file']}")
    
    # サブディレクトリの確認
    subdirs = ['logs', 'drivers', 'backups', 'crawled_data']
    for subdir in subdirs:
        subdir_path = paths['data_dir'] / subdir
        print(f"サブディレクトリ {subdir}: {'存在します' if subdir_path.exists() else '存在しません'}")
    
    # 設定ファイルのディレクトリを確認
    settings_dir = paths['settings_file'].parent
    print(f"設定ファイルディレクトリ: {settings_dir}")
    print(f"設定ファイルディレクトリの存在: {'はい' if settings_dir.exists() else 'いいえ'}")
    
    # 環境変数からデータディレクトリを取得
    env_data_dir = get_data_dir_from_env()
    print(f"環境変数からのデータディレクトリ: {env_data_dir}")
    
    logger.info("テストが完了しました")

if __name__ == "__main__":
    test_frozen_environment() 