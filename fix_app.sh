#!/bin/bash

# エラーが発生したら終了
set -e

# アプリケーション名
APP_NAME="ankenNaviCHO"

# カレントディレクトリを取得
CURRENT_DIR=$(pwd)

# アプリケーションのインストール先をカレントディレクトリに変更
INSTALL_DIR="$CURRENT_DIR/${APP_NAME}_mac.app"
CONTENTS_DIR="$INSTALL_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
FRAMEWORKS_DIR="$CONTENTS_DIR/Frameworks"

# カラー表示の設定
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ヘッダーを表示
echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}      ${APP_NAME} 修正スクリプト      ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo ""

# インストール先ディレクトリが既に存在する場合の確認
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${RED}警告: $INSTALL_DIR は既に存在します。${NC}"
    read -p "上書きしますか？ (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "修正を中止しました。"
        exit 1
    fi
    echo "既存のアプリケーションをバックアップしています..."
    BACKUP_DIR="$CURRENT_DIR/backups/backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cp -R "$INSTALL_DIR" "$BACKUP_DIR/"
    echo "バックアップが完了しました: $BACKUP_DIR"
else
    echo "新規にアプリケーションを作成します..."
    mkdir -p "$INSTALL_DIR"
fi

echo "アプリケーションを修正しています..."

# ディレクトリ構造を作成
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"
mkdir -p "$FRAMEWORKS_DIR"

# 必要なファイルをコピー
echo "ファイルをコピーしています..."

# リソースファイルをコピー
cp -R app.py "$RESOURCES_DIR/"
cp -R chromedriver_manager.py "$RESOURCES_DIR/"
cp -R bulk_apply.py "$RESOURCES_DIR/"
cp -R crawler.py "$RESOURCES_DIR/"
cp -R updater.py "$RESOURCES_DIR/"
cp -R supabase_stripe_handler.py "$RESOURCES_DIR/"

# 設定ファイルパスパッチをコピー
cp -R fix_settings_patch.py "$RESOURCES_DIR/"

if [ -f ".env" ]; then
    cp -R .env "$RESOURCES_DIR/"
fi
if [ -f "requirements.txt" ]; then
    cp -R requirements.txt "$RESOURCES_DIR/"
fi
if [ -d "templates" ]; then
    cp -R templates "$RESOURCES_DIR/"
fi
if [ -d "static" ]; then
    cp -R static "$RESOURCES_DIR/"
fi

# ディレクトリを作成
mkdir -p "$RESOURCES_DIR/logs"
mkdir -p "$RESOURCES_DIR/drivers"
mkdir -p "$RESOURCES_DIR/backups"

# crawled_dataディレクトリの処理を改善
if [ -d "crawled_data" ]; then
    # crawled_dataディレクトリが存在する場合でも、中身はコピーせず空のディレクトリだけを作成
    echo "空のcrawled_dataディレクトリを作成します..."
    mkdir -p "$RESOURCES_DIR/crawled_data"
    echo "crawled_dataディレクトリを作成しました（中身はコピーしません）"
else
    # crawled_dataディレクトリが存在しない場合も、空のディレクトリを作成
    mkdir -p "$RESOURCES_DIR/crawled_data"
fi

# ChromeDriverをコピー
if [ -d "drivers" ]; then
    cp -R drivers "$RESOURCES_DIR/"
fi

# app_launcher.pyをコピー
cp app_launcher.py "$RESOURCES_DIR/"

# アイコンの処理
echo "アプリケーションアイコンを作成しています..."
ICON_CREATED=false

# 1. original_icon.png から生成
if [ -f "original_icon.png" ]; then
    echo "original_icon.png からアイコンを作成します..."
    if command -v sips &> /dev/null && command -v iconutil &> /dev/null; then
        # 一時的なiconsetディレクトリを作成
        TEMP_ICONSET_DIR="tmp_icon_gen.iconset"
        mkdir -p "$TEMP_ICONSET_DIR"

        # sips を使用して必要なサイズのアイコンを生成
        sips -z 16 16     original_icon.png --out "$TEMP_ICONSET_DIR/icon_16x16.png" > /dev/null 2>&1
        sips -z 32 32     original_icon.png --out "$TEMP_ICONSET_DIR/icon_16x16@2x.png" > /dev/null 2>&1
        sips -z 32 32     original_icon.png --out "$TEMP_ICONSET_DIR/icon_32x32.png" > /dev/null 2>&1
        sips -z 64 64     original_icon.png --out "$TEMP_ICONSET_DIR/icon_32x32@2x.png" > /dev/null 2>&1
        sips -z 128 128   original_icon.png --out "$TEMP_ICONSET_DIR/icon_128x128.png" > /dev/null 2>&1
        sips -z 256 256   original_icon.png --out "$TEMP_ICONSET_DIR/icon_128x128@2x.png" > /dev/null 2>&1
        sips -z 256 256   original_icon.png --out "$TEMP_ICONSET_DIR/icon_256x256.png" > /dev/null 2>&1
        sips -z 512 512   original_icon.png --out "$TEMP_ICONSET_DIR/icon_256x256@2x.png" > /dev/null 2>&1
        sips -z 512 512   original_icon.png --out "$TEMP_ICONSET_DIR/icon_512x512.png" > /dev/null 2>&1
        # sips -z 1024 1024 original_icon.png --out "$TEMP_ICONSET_DIR/icon_512x512@2x.png" > /dev/null 2>&1 # 1024pxはオプション

        # iconutil を使用して .icns ファイルを作成
        iconutil -c icns "$TEMP_ICONSET_DIR" -o "$RESOURCES_DIR/AppIcon.icns"
        
        # 一時ディレクトリを削除
        rm -rf "$TEMP_ICONSET_DIR"
        
        echo "アイコンファイルを作成しました: $RESOURCES_DIR/AppIcon.icns"
        ICON_CREATED=true
    else
        echo "警告: アイコン生成に必要な sips または iconutil コマンドが見つかりません。アイコン作成をスキップします。"
    fi
# 2. 既存の AppIcon.icns を使用
elif [ -f "AppIcon.icns" ] && [ "$ICON_CREATED" != true ]; then
    # 既存のicnsファイルを使用
    echo "既存のアイコンファイルを使用します: AppIcon.icns"
    cp AppIcon.icns "$RESOURCES_DIR/"
    ICON_CREATED=true
# 3. temp_icons/AppIcon.iconset から生成
elif [ -d "temp_icons/AppIcon.iconset" ] && [ "$(ls -A temp_icons/AppIcon.iconset)" ] && [ "$ICON_CREATED" != true ]; then
    echo "既存のアイコンセットからアイコンファイルを作成します..."
    
    # 一時的なディレクトリを作成
    mkdir -p "tmp_iconset"
    
    # アイコンを正しい名前でコピー (既存のロジックを流用)
    if [ -f "temp_icons/AppIcon.iconset/Icon-App-40x40@1x.png" ]; then cp "temp_icons/AppIcon.iconset/Icon-App-40x40@1x.png" "tmp_iconset/icon_16x16@2x.png"; fi
    if [ -f "temp_icons/AppIcon.iconset/Icon-App-20x20@1x.png" ]; then cp "temp_icons/AppIcon.iconset/Icon-App-20x20@1x.png" "tmp_iconset/icon_16x16.png"; fi
    if [ -f "temp_icons/AppIcon.iconset/Icon-App-40x40@1x.png" ]; then cp "temp_icons/AppIcon.iconset/Icon-App-40x40@1x.png" "tmp_iconset/icon_32x32.png"; fi
    if [ -f "temp_icons/AppIcon.iconset/Icon-App-76x76@1x.png" ]; then 
        cp "temp_icons/AppIcon.iconset/Icon-App-76x76@1x.png" "tmp_iconset/icon_32x32@2x.png"; 
        cp "temp_icons/AppIcon.iconset/Icon-App-76x76@1x.png" "tmp_iconset/icon_128x128.png"; 
    fi
    if [ -f "temp_icons/AppIcon.iconset/Icon-App-83.5x83.5@2x.png" ]; then 
        cp "temp_icons/AppIcon.iconset/Icon-App-83.5x83.5@2x.png" "tmp_iconset/icon_128x128@2x.png"; 
        cp "temp_icons/AppIcon.iconset/Icon-App-83.5x83.5@2x.png" "tmp_iconset/icon_256x256.png"; 
    fi
    if [ -f "temp_icons/AppIcon.iconset/ItunesArtwork@2x.png" ]; then 
        cp "temp_icons/AppIcon.iconset/ItunesArtwork@2x.png" "tmp_iconset/icon_256x256@2x.png"; 
        cp "temp_icons/AppIcon.iconset/ItunesArtwork@2x.png" "tmp_iconset/icon_512x512.png"; 
        cp "temp_icons/AppIcon.iconset/ItunesArtwork@2x.png" "tmp_iconset/icon_512x512@2x.png"; 
    fi
    
    # icnsファイルを作成
    if command -v iconutil &> /dev/null; then
        iconutil -c icns "tmp_iconset" -o "tmp_AppIcon.icns"
        cp "tmp_AppIcon.icns" "$RESOURCES_DIR/AppIcon.icns"
        echo "アイコンファイルを作成しました: $RESOURCES_DIR/AppIcon.icns"
        ICON_CREATED=true
        
        # 一時ファイル削除
        rm -rf "tmp_iconset" "tmp_AppIcon.icns"
    else
        echo "警告: iconutilがインストールされていないため、アイコンファイルの作成をスキップします。"
    fi
fi

# アイコンが作成されなかった場合のフォールバックメッセージ
if [ "$ICON_CREATED" != true ]; then
    echo "有効なアイコンソースが見つからなかったため、アイコンの作成をスキップします。"
fi

# Pythonランタイムの同梱を削除 - システムPythonを使用する方針に変更
echo "Pythonランタイムは同梱せず、システムのPythonを使用します..."

# 起動スクリプトを作成（シンプル版）
cat > "$MACOS_DIR/run" << 'EOF_RUN'
#!/bin/bash

# --- アーキテクチャチェックと再実行 ---
if [[ "$(arch)" != "arm64" ]]; then
  # arm64でなければ、arm64を指定してスクリプト自身を再実行
  echo "アーキテクチャ $(arch) を検出しました。arm64で再実行します..." >&2 # エラー出力へ
  exec arch -arm64 "$0" "$@"
  # exec はプロセスを置き換えるため、ここから下は再実行されたarm64プロセスでのみ実行される
fi
echo "arm64アーキテクチャで実行中..." >&2 # 確認用ログ

# --- ログ設定 ---
# スクリプト自身の絶対パスを取得し、そのディレクトリを SCRIPT_DIR とする
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
CONTENTS_DIR="$SCRIPT_DIR/.."
RESOURCES_DIR="$CONTENTS_DIR/Resources"
LOG_DIR="$RESOURCES_DIR/logs"
LAUNCHER_LOG_FILE="$LOG_DIR/launcher.log"
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LAUNCHER_LOG_FILE") 2>&1
echo "--- ランチャースクリプト開始: $(date) ---"
echo "実行アーキテクチャ: $(arch)"

# --- 変数定義 ---
VENV_DIR="$HOME/Library/Application Support/ankenNaviCHO/venv"
SUPPORT_DIR="$HOME/Library/Application Support/ankenNaviCHO"
SETUP_DONE_FLAG="$SUPPORT_DIR/.setup_done"

# エラーハンドリング関数
handle_error() {
    ERROR_MESSAGE=$1
    /usr/bin/osascript -e "display dialog \"エラーが発生しました:\\n\\n$ERROR_MESSAGE\\n\\n詳細はログファイルを確認してください。\\n$LAUNCHER_LOG_FILE\" buttons {\"OK\"} default button \"OK\" with title \"エラー\" with icon stop"
    exit 1
}

# Pythonが存在し、バージョンが適切か確認する関数
check_python_version() {
    # Pythonが存在するかチェック
    if ! command -v python3 &> /dev/null; then
        echo "Python3が見つかりません。ダウンロードを促します。"
        DOWNLOAD_RESULT=$(/usr/bin/osascript -e 'display dialog "Python3が見つかりません。\n\nアプリケーションの実行には Python 3.11 以上が必要です。\n\nPython をダウンロードしますか？" buttons {"キャンセル","ダウンロード"} default button "ダウンロード" with title "Python環境のセットアップ" with icon caution')
        if [[ "$DOWNLOAD_RESULT" == *"ダウンロード"* ]]; then
            open "https://www.python.org/downloads/"
            /usr/bin/osascript -e 'display dialog "ダウンロードが完了したら、インストーラを実行してPythonをインストールしてください。\n\nインストール完了後、アプリケーションを再度起動してください。" buttons {"OK"} default button "OK" with title "Python環境のセットアップ"'
        fi
        return 1
    fi

    # バージョンチェックは不要のためコメントアウト
    : <<'NO_VERSION_CHECK'
    # 以下、Pythonバージョンを検証する処理を一時的に無効化
    # PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    # PYTHON_MAJOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f1)
    # PYTHON_MINOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f2)
    # echo "検出されたPythonバージョン: $PYTHON_VERSION"
    # if [ "$PYTHON_MAJOR_VERSION" -lt 3 ] || ([ "$PYTHON_MAJOR_VERSION" -eq 3 ] && [ "$PYTHON_MINOR_VERSION" -le 11 ]); then
    #     echo "Pythonバージョンが古いため、新しいバージョンのダウンロードを促します。"
    #     DOWNLOAD_RESULT=$(/usr/bin/osascript <<EOF_DIALOG
    #         display dialog "検出されたPythonバージョン ($PYTHON_VERSION) は古いバージョンです。\n\nアプリケーションの実行には Python 3.11 以上が推奨されます。\n\nPython 3.13.3 をダウンロードしますか？" buttons {"このまま続行", "ダウンロード"} default button "ダウンロード" with title "Python環境のセットアップ" with icon caution
    # EOF_DIALOG
    #     )
    #     if [[ "$DOWNLOAD_RESULT" == *"ダウンロード"* ]]; then
    #         open "https://www.python.org/downloads/"
    #         /usr/bin/osascript -e 'display dialog "ダウンロードが完了したら、インストーラを実行してPythonをインストールしてください。\n\nインストール完了後、アプリケーションを再度起動してください。" buttons {"OK"} default button "OK" with title "Python環境のセットアップ"'
    #         return 1
    #     fi
    #     echo "ユーザーが古いバージョンのPythonでの続行を選択しました。"
    # fi
NO_VERSION_CHECK

    return 0
}

# Pythonバージョンをチェック
check_python_version
if [ $? -ne 0 ]; then
    echo "Pythonのセットアップが必要です。アプリケーションを終了します。"
    exit 0
fi

# セットアップ済みかチェック
if [ ! -f "$SETUP_DONE_FLAG" ]; then
  RESULT=$(/usr/bin/osascript -e 'display dialog "初回セットアップが必要です。実行しますか？" buttons {"キャンセル","実行して通知を待つ"} default button "実行して通知を待つ" with title "ankenNaviCHO セットアップ" with icon caution')

  # キャンセルしたら終了
  if [[ "$RESULT" != *"実行"* ]]; then
    exit 1
  fi

  # 初回環境構築を実行 (エラーハンドリング付き)
  "$SCRIPT_DIR/setup" || handle_error "セットアップスクリプトの実行に失敗しました。"

  # セットアップ後はメッセージを表示して終了
  /usr/bin/osascript -e 'display dialog "環境構築が完了しました。再度アプリケーションを起動してください。" buttons {"OK"} default button "OK" with title "ankenNaviCHO セットアップ完了"'
  exit 0
fi

# セットアップ済みなら直接アプリを起動
echo "仮想環境をアクティベートしています: $VENV_DIR/bin/activate"
source "$VENV_DIR/bin/activate" || handle_error "仮想環境のアクティベートに失敗しました。"

echo "リソースディレクトリに移動しています: $RESOURCES_DIR"
cd "$RESOURCES_DIR" || handle_error "リソースディレクトリへの移動に失敗しました。"

echo "アプリケーションランチャーを実行しています: python3 $RESOURCES_DIR/app_launcher.py"
python3 "$RESOURCES_DIR/app_launcher.py" || handle_error "アプリケーションランチャーの実行に失敗しました。"

echo "アプリケーションが終了しました。"
EOF_RUN

# セットアップスクリプトを作成
cat > "$MACOS_DIR/setup" << 'EOF_SETUP'
#!/bin/bash
# スクリプト自身の絶対パスを取得し、そのディレクトリを SCRIPT_DIR とする
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
CONTENTS_DIR="$SCRIPT_DIR/.."
RESOURCES_DIR="$CONTENTS_DIR/Resources"
VENV_DIR="$HOME/Library/Application Support/ankenNaviCHO/venv"
SUPPORT_DIR="$HOME/Library/Application Support/ankenNaviCHO"
SETUP_DONE_FLAG="$SUPPORT_DIR/.setup_done"
LOG_FILE="$RESOURCES_DIR/logs/setup.log"

# ログディレクトリ作成
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "セットアップを開始します: $(date)"
echo "実行アーキテクチャ: $(arch)"

# Pythonのバージョンチェック
check_python_version() {
    # Pythonが存在するかチェック
    if ! command -v python3 &> /dev/null; then
        echo "エラー: Python3が見つかりません。"
        /usr/bin/osascript -e 'display dialog "Python3が見つかりません。セットアップを実行できません。\n\nPython 3.11以上をインストールしてください。\n\nPython 3.13.3のダウンロードページを開きますか？" buttons {"キャンセル", "ダウンロードページを開く"} default button "ダウンロードページを開く" with title "エラー" with icon stop'
        if [[ $? -eq 0 ]]; then
            open "https://www.python.org/downloads/"
        fi
        return 1
    fi

    # バージョンチェックは不要のためコメントアウト
    : <<'NO_VERSION_CHECK'
    # 以下、Pythonバージョンを検証する処理を一時的に無効化
    # PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    # PYTHON_MAJOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f1)
    # PYTHON_MINOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f2)
    # echo "検出されたPythonバージョン: $PYTHON_VERSION"
    # if [ "$PYTHON_MAJOR_VERSION" -lt 3 ] || ([ "$PYTHON_MAJOR_VERSION" -eq 3 ] && [ "$PYTHON_MINOR_VERSION" -le 11 ]); then
    #     echo "警告: Pythonバージョンが推奨より古いです。"
    #     RESULT=$(/usr/bin/osascript <<EOF_DIALOG
    #         display dialog "検出されたPythonバージョン ($PYTHON_VERSION) は古いバージョンです。\n\nアプリケーションの実行には Python 3.11 以上が推奨されます。\n\n続行しますか？" buttons {"キャンセル", "ダウンロードページを開く", "続行"} default button "ダウンロードページを開く" with title "警告" with icon caution
    # EOF_DIALOG
    #     )
    #     if [[ "$RESULT" == *"キャンセル"* ]]; then
    #         return 1
    #     elif [[ "$RESULT" == *"ダウンロード"* ]]; then
    #         open "https://www.python.org/downloads/"
    #         /usr/bin/osascript -e 'display dialog "ダウンロードが完了したら、インストーラを実行してPythonをインストールしてください。\n\nインストール完了後、アプリケーションを再度起動してください。" buttons {"OK"} default button "OK" with title "Python環境のセットアップ"'
    #         return 1
    #     fi
    #     echo "ユーザーが古いバージョンのPythonでの続行を選択しました。"
    # fi
NO_VERSION_CHECK

    return 0
}

# Pythonバージョンチェックの実行
check_python_version
if [ $? -ne 0 ]; then
    echo "Pythonのセットアップが必要です。セットアップを中止します。"
    exit 1
fi

# エラーハンドリング関数
handle_error() {
    ERROR_MESSAGE=$1
    echo "エラー発生: $ERROR_MESSAGE"
    # LOG_FILE変数が既に定義されているので、それを使う
    /usr/bin/osascript -e "display dialog \"セットアップ中にエラーが発生しました:\\n\\n$ERROR_MESSAGE\\n\\n詳細はログファイルを確認してください:\\n$LOG_FILE\" buttons {\"OK\"} default button \"OK\" with title \"セットアップエラー\" with icon stop"
    exit 1
}

# 既存の環境を削除
echo "既存の仮想環境を削除しています: $VENV_DIR"
rm -rf "$VENV_DIR" || echo "既存の仮想環境の削除に失敗しましたが、続行します。"

# アプリケーションサポートディレクトリを作成
echo "アプリケーションサポートディレクトリを作成しています: $SUPPORT_DIR"
mkdir -p "$SUPPORT_DIR"
if [ $? -ne 0 ]; then
  handle_error "サポートディレクトリの作成に失敗しました。\\n'$SUPPORT_DIR'\\n権限を確認してください。"
fi

# 仮想環境を作成
echo "仮想環境を作成しています: $VENV_DIR (使用するPython: $(which python3))"
python3 -m venv "$VENV_DIR"
if [ $? -ne 0 ]; then
  handle_error "仮想環境の作成に失敗しました。\\nPythonが正しくインストールされているか、またはvenvモジュールが利用可能か確認してください。"
fi

# pipのアップグレードと依存関係のインストール
echo "仮想環境をアクティベートします..."
source "$VENV_DIR/bin/activate"
if [ $? -ne 0 ]; then
  handle_error "仮想環境のアクティベートに失敗しました。"
fi

echo "pipをアップグレードしています..."
"$VENV_DIR/bin/pip" install --upgrade pip
if [ $? -ne 0 ]; then
  handle_error "pipのアップグレードに失敗しました。インターネット接続を確認してください。"
fi

echo "依存関係をインストールしています ($RESOURCES_DIR/requirements.txt)..."
"$VENV_DIR/bin/pip" install --only-binary :all: -r "$RESOURCES_DIR/requirements.txt"
if [ $? -ne 0 ]; then
  handle_error "依存関係のインストールに失敗しました。\\nrequirements.txtの内容、またはインターネット接続を確認してください。"
fi

echo "仮想環境のセットアップが完了しました。"

# .envファイルの妥当性確認 (もし存在する場合)
if [ -f "$RESOURCES_DIR/.env" ]; then
  echo ".envファイルを確認しています..."
  if ! grep -q "API_KEY" "$RESOURCES_DIR/.env" || ! grep -q "SUPABASE_URL" "$RESOURCES_DIR/.env"; then
    echo "警告: .envファイルの内容が不完全または存在しません。"
    /usr/bin/osascript -e 'display dialog ".envファイルの内容が不完全です。\\nアプリケーションの動作に必要なAPIキーなどが設定されていない可能性があります。\\n\\n続行しますが、設定を確認してください。" buttons {"OK"} default button "OK" with icon caution with title "警告"'
  fi

  # PORT環境変数を.envファイルに設定
  PORT_VALUE=$(grep "^PORT=" "$RESOURCES_DIR/.env" | cut -d '=' -f2)
  if [ -z "$PORT_VALUE" ]; then
      echo "PORT=8080" >> "$RESOURCES_DIR/.env"
      echo ".envにデフォルトポート(8080)を追加しました。"
  fi

  # FLASK_DEBUGを強制的に0に設定
  if grep -q "^FLASK_DEBUG=" "$RESOURCES_DIR/.env"; then
      sed -i '' 's/^FLASK_DEBUG=.*/FLASK_DEBUG=0/' "$RESOURCES_DIR/.env"
      echo ".envのFLASK_DEBUGを0に設定しました。"
  else
      echo "FLASK_DEBUG=0" >> "$RESOURCES_DIR/.env"
      echo ".envにFLASK_DEBUG=0を追加しました。"
  fi

  # SKIP_NODE_SERVER設定を追加（npmエラー対策）
  if ! grep -q "^SKIP_NODE_SERVER=" "$RESOURCES_DIR/.env"; then
      echo "SKIP_NODE_SERVER=1" >> "$RESOURCES_DIR/.env"
      echo ".envにSKIP_NODE_SERVER=1を追加しました。"
  fi

  # CHROMEDRIVER_PRECACHE設定を追加（起動高速化）
  if ! grep -q "^CHROMEDRIVER_PRECACHE=" "$RESOURCES_DIR/.env"; then
      echo "CHROMEDRIVER_PRECACHE=1" >> "$RESOURCES_DIR/.env"
      echo ".envにCHROMEDRIVER_PRECACHE=1を追加しました。"
  fi

  # DISABLE_CHROMEDRIVER_BACKGROUND_UPDATE設定を追加（起動高速化）
  if ! grep -q "^DISABLE_CHROMEDRIVER_BACKGROUND_UPDATE=" "$RESOURCES_DIR/.env"; then
      echo "DISABLE_CHROMEDRIVER_BACKGROUND_UPDATE=1" >> "$RESOURCES_DIR/.env"
      echo ".envにDISABLE_CHROMEDRIVER_BACKGROUND_UPDATE=1を追加しました。"
  fi
  echo ".envファイルの確認と設定が完了しました。"
else
    echo ".envファイルが見つかりません。スキップします。"
fi

# 事前にChromeDriverをキャッシュして起動を高速化
if [ -f "$RESOURCES_DIR/chromedriver_manager.py" ]; then
  echo "ChromeDriverを事前にキャッシュしています..."
  CACHE_SCRIPT=$(cat <<'END_SCRIPT'
import sys
import os
import time
import subprocess
import re

# Chromeのバージョンを取得
def get_chrome_version():
    # MacOSのChromeバージョン取得
    try:
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if not os.path.exists(chrome_path):
            chrome_path = os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        
        if os.path.exists(chrome_path):
            # archコマンド削除
            version = subprocess.check_output([chrome_path, '--version'], stderr=subprocess.STDOUT)
            match = re.search(r"Google Chrome ([\d.]+)", version.decode("utf-8"))
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Chromeバージョン取得エラー: {e}")
    return None

# モジュールのインポートパスを設定
sys.path.insert(0, os.getcwd())

try:
    from chromedriver_manager import setup_driver
    
    # 現在のChromeバージョンを取得
    chrome_version = get_chrome_version()
    print(f"検出されたChromeバージョン: {chrome_version}")
    
    # ChromeDriverを事前にセットアップして結果をキャッシュ
    driver_path = setup_driver()
    
    if not driver_path:
        raise Exception("ChromeDriverのセットアップが失敗しました")
        
    print(f"ChromeDriverを事前キャッシュしました: {driver_path}")
    
    # セットアップ後の情報をファイルに保存（Chromeバージョン含む）
    cache_info_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chromedriver_cache_info")
    with open(cache_info_path, "w") as f:
        f.write(f"PATH={driver_path}\\n")
        f.write(f"TIMESTAMP={int(time.time())}\\n")
        if chrome_version:
            f.write(f"CHROME_VERSION={chrome_version}\\n")
    
except Exception as e:
    print(f"ChromeDriverのキャッシュ中にエラーが発生しました: {e}")
    sys.exit(1)
END_SCRIPT
)
  
  # スクリプトを一時ファイルに書き出して実行
  TEMP_SCRIPT_FILE="$RESOURCES_DIR/.temp_chromedriver_cache.py"
  echo "$CACHE_SCRIPT" > "$TEMP_SCRIPT_FILE"
  python3 "$TEMP_SCRIPT_FILE"
  CACHE_EXIT_CODE=$?
  rm -f "$TEMP_SCRIPT_FILE"

  if [ $CACHE_EXIT_CODE -ne 0 ]; then
      handle_error "ChromeDriverの事前キャッシュに失敗しました。\nChromeがインストールされているか確認してください。"
  fi
  echo "ChromeDriverのキャッシュが完了しました。"
fi

# セットアップ完了フラグを作成
echo "セットアップ完了フラグを作成しています: $SETUP_DONE_FLAG"
touch "$SETUP_DONE_FLAG"
if [ $? -ne 0 ]; then
  handle_error "セットアップ完了フラグの作成に失敗しました。\n'$SUPPORT_DIR'への書き込み権限を確認してください。"
fi

echo "セットアップが正常に完了しました: $(date)"
EOF_SETUP

# app_launcher.pyに最適化パッチを適用（事前キャッシュ情報を利用するため）
if [ -f "app_launcher.py" ]; then
    # パッチ内容を一時ファイルに保存
    PATCH_CONTENT=$(cat <<'EOF_PATCH'
# ... (app_launcher.py の内容は基本的に変更なし、ただしPYTHON_EXECの概念は不要) ...
# ... ただし、Pythonインタプリタパスの取得方法を修正する必要がある ...

# (app_launcher.py内の修正が必要な箇所)
# 実行する Python インタプリタパスを取得 (runスクリプトでvenvがactivateされる前提)
# venv_dir = os.path.expanduser("~/Library/Application Support/ankenNaviCHO/venv")
# python_path = os.path.join(venv_dir, "bin", "python3") # この行は不要になるか、sys.executableを使う

# (app_launcher.pyの他の部分は変更なし)
EOF_PATCH
)

    # 既存のapp_launcher.pyを上書き (※app_launcher.py自体の修正も必要になる可能性)
    # echo "$PATCH_CONTENT" > "$RESOURCES_DIR/app_launcher.py" # 一旦コメントアウト。app_launcher.pyの修正が必要
    echo "app_launcher.pyへのパッチ適用をスキップしました (別途修正が必要な可能性があります)。"
fi

# 起動スクリプトとセットアップスクリプトに実行権限を付与
chmod +x "$MACOS_DIR/run"
chmod +x "$MACOS_DIR/setup"

# Info.plistを作成
cat > "$CONTENTS_DIR/Info.plist" << EOF_PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>LSArchitecturePriority</key>
    <array>
        <string>arm64</string>
        <string>x86_64</string>
    </array>
    <key>CFBundleExecutable</key>
    <string>run</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.anken.navicho</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.14</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright © 2024 YourCompany. All rights reserved.</string>
</dict>
</plist>
EOF_PLIST

echo -e "${GREEN}アプリケーションの修正が完了しました！${NC}"
echo -e "アプリケーションは以下の場所に作成されました:"
echo -e "${BLUE}$INSTALL_DIR${NC}"

echo -e "\n${GREEN}アプリケーションの起動方法:${NC}"
echo -e "Finderから ${BLUE}$INSTALL_DIR${NC} をダブルクリックします。"
echo -e "※初回起動時は環境構築が実行され、完了後に再度起動が必要です。"
echo -e "※2回目以降はすぐにアプリケーションが起動します。"

echo -e "\n${GREEN}ログファイルの場所:${NC}"
echo -e "${BLUE}$RESOURCES_DIR/logs/${NC}"

echo ""
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}修正が正常に完了しました！${NC}"
echo -e "${BLUE}====================================================${NC}"

# アプリケーションの配布方法の説明
echo -e "\n${BLUE}配布方法:${NC}"
echo -e "1. ${BLUE}${APP_NAME}_mac.app${NC} をzipファイルに圧縮します:"
echo -e "   ${GREEN}zip -r ${APP_NAME}_mac.zip ${APP_NAME}_mac.app${NC}"
echo -e "2. zipファイルを配布先に提供します。"
echo -e "3. ユーザーはzipファイルを解凍し、アプリケーションをダブルクリックして実行します。"

