FROM python:3.11-slim

# 環境変数
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SKIP_NODE_SERVER=true

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
ENV PORT=8080
EXPOSE 8080

# Uvicorn(ASGI)で起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$PORT"] 