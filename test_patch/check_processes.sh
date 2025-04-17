#!/bin/bash

# プロセスとポートの状態を確認するスクリプト

# 色の定義
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}==== プロセスとポート状態チェック ====${NC}"
echo ""

# 1. アプリケーション関連プロセスの確認
echo -e "${YELLOW}1. アプリケーション関連プロセスの確認${NC}"
echo "実行中のPythonプロセス："
python_count=$(ps aux | grep -i python | grep -i ankenNaviCHO | grep -v grep | wc -l | tr -d ' ')
ps aux | grep -i python | grep -i ankenNaviCHO | grep -v grep

if [ "$python_count" -eq 0 ]; then
    echo -e "${GREEN}✓ Pythonプロセスは実行されていません${NC}"
else
    echo -e "${RED}✗ $python_count 件のPythonプロセスが実行中です${NC}"
fi

echo ""
echo "実行中のNodeプロセス："
node_count=$(ps aux | grep -i node | grep -v grep | wc -l | tr -d ' ')
ps aux | grep -i node | grep -v grep

if [ "$node_count" -eq 0 ]; then
    echo -e "${GREEN}✓ Nodeプロセスは実行されていません${NC}"
else
    echo -e "${RED}✗ $node_count 件のNodeプロセスが実行中です${NC}"
fi

echo ""

# 2. ポートの使用状況確認
echo -e "${YELLOW}2. ポートの使用状況確認${NC}"
echo "ポート8080の状態："
port_8080=$(lsof -i:8080 | wc -l | tr -d ' ')
lsof -i:8080

if [ "$port_8080" -eq 0 ]; then
    echo -e "${GREEN}✓ ポート8080は使用されていません${NC}"
else
    echo -e "${RED}✗ ポート8080は使用中です${NC}"
fi

echo ""

# 3. ロックファイルの確認
echo -e "${YELLOW}3. ロックファイルの確認${NC}"

# データディレクトリの場所を確認
HOME_DIR="$HOME"
DATA_DIR="$HOME_DIR/anken_navi_data"
LOCK_FILE="$DATA_DIR/anken_navi.lock"

if [ -f "$LOCK_FILE" ]; then
    echo -e "${RED}✗ ロックファイルが存在します: $LOCK_FILE${NC}"
    echo "ロックファイルの内容："
    cat "$LOCK_FILE"
else
    echo -e "${GREEN}✓ ロックファイルは存在しません${NC}"
fi

echo ""
echo -e "${YELLOW}==== チェック完了 ====${NC}" 