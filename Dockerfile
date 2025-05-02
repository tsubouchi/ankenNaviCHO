FROM python:3.11-slim

# 環境変数
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    SKIP_NODE_SERVER=true \
    APP_DATA_DIR=/tmp/app-data \
    SKIP_CHROME_SETUP=false \
    SKIP_UPDATES=false \
    PORT=8080

# 必要なシステムパッケージ & Google Chrome（ヘッドレス用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl wget gnupg \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 \
    libxrandr2 libxi6 libasound2 libpangocairo-1.0-0 \
    libatk1.0-0 libatk-bridge2.0-0 libgbm1 libgtk-3-0 \
    ca-certificates fonts-liberation libappindicator3-1 xdg-utils \
    && curl -L -o /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y /tmp/google-chrome.deb \
    && rm /tmp/google-chrome.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Chromeパスを環境変数に設定
ENV GOOGLE_CHROME_BIN=/usr/bin/google-chrome \
    CHROME_BIN=/usr/bin/google-chrome

# 作業ディレクトリ
WORKDIR /app

# Python依存ライブラリ
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# アプリケーションコード
COPY . /app

# Cloud RunではPORT環境変数が自動付与される
EXPOSE 8080

# シークレットマウント用ディレクトリ作成
RUN mkdir -p /secrets

# データディレクトリ作成（クローリングデータ、ログ、ドライバー）
RUN mkdir -p "$APP_DATA_DIR/crawled_data" "$APP_DATA_DIR/logs" "$APP_DATA_DIR/drivers"

# Uvicorn(ASGI)で起動 - デバッグオプション追加
CMD ["sh", "-c", "echo 'Starting app on port ${PORT}' && PYTHONUNBUFFERED=1 uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level debug --timeout-keep-alive 75"] 