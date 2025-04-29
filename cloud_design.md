# GCP クラウド展開設計書 (cloud_design.md)

## 1. 目的
本ドキュメントでは、ローカル実行を前提としている Python アプリケーション (requirements.txt 参照) を Google Cloud Platform (GCP) 上へデプロイし、クラウドサービスとして運用するための設計指針と注意事項を整理する。特に Selenium を利用するために必要となる Chrome / ChromeDriver まわりの構成・運用ポイントに焦点を当てる。

---

## 2. アーキテクチャ候補
| サービス | 特徴 | 適合度 |
|----------|------|--------|
| **Cloud Run** | コンテナベースのフルマネージド実行環境。CPU/メモリサイズを柔軟に選択でき、コンテナ内でヘッドレス Chrome を起動可能。 | ◎ 最有力 |
| App Engine (Flex) | CPU 常時起動が必要な場合に便利。インスタンス単価が高め。 | ○ |
| Compute Engine | フル操作可能な VM。OS レイヤから Chrome をセットアップできるが、運用負荷が高い。 | △ |
| Cloud Functions | 実行時間上限 60 分、/tmp 上限 512 MB。ChromeDriver を内包したデプロイも可能だが Selenium の起動/終了コストが高い。 | △ |

> **推奨:** Cloud Run (Container) を前提とし、Selenium に必要な Chrome/ChromeDriver をコンテナに組み込む。

---

## 3. コンテナ設計
### 3.1 ベースイメージ
* `python:3.12-slim` または `gcr.io/distroless/python3-debian12` を推奨。
* apt で `google-chrome-stable` と `chromium-chromedriver` (または `chromedriver`) をインストール。
* Chrome と ChromeDriver の **バージョン整合性** が最重要。Mismatch があると `SessionNotCreatedException` が発生する。
* アプリケーションサーバーは **Gunicorn → Uvicorn (ASGI)** へ変更。
* エントリポイントは `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$PORT"]`

### 3.2 Dockerfile サンプル
```Dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS build

# === OS パッケージ ===
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget gnupg ca-certificates unzip \
        fonts-liberation libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
        libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 libxrandr2 libxss1 libxtst6 \
        libgbm1 libgtk-3-0 && \
    rm -rf /var/lib/apt/lists/*

# === Google Chrome & ChromeDriver ===
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-linux-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-keyring.gpg] https://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable && \
    CHROME_VERSION=$(google-chrome --version | awk '{print $3}') && \
    MAJOR_VERSION=${CHROME_VERSION%%.*} && \
    wget -q https://chromedriver.storage.googleapis.com/${MAJOR_VERSION}.0.0/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip -d /usr/local/bin && \
    rm chromedriver_linux64.zip && \
    chmod +x /usr/local/bin/chromedriver && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# === Python deps ===
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# === Application ===
COPY . /app
ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    TZ=Asia/Tokyo

# Cloud Run expects to listen on $PORT
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$PORT"]
```

### 3.3 イメージサイズ最適化
* multi-stage build により、`pip install` 専用レイヤを分離。
* 不要なキャッシュ (`rm -rf /root/.cache/pip`) を削除して最終イメージを軽量化。

---

## 4. Selenium / ChromeDriver 運用の注意点
1. **バージョン同期**  
   * Chrome 更新が自動で行われる場合、同一 major version の ChromeDriver が必須。  
   * 固定バージョンをインストールするか、起動時スクリプトでバージョン取得 → 対応 ChromeDriver ダウンロードの自動化を検討。
2. **ヘッドレスモード起動**  
   ```python
   from selenium import webdriver
   from selenium.webdriver.chrome.options import Options

   chrome_options = Options()
   chrome_options.add_argument("--headless=new")
   chrome_options.add_argument("--no-sandbox")
   chrome_options.add_argument("--disable-dev-shm-usage")
   driver = webdriver.Chrome(options=chrome_options)
   ```
3. **リソース制限**  
   * Cloud Run のメモリ不足により Chrome が `SIGKILL` されるケース有。  
   * 必要に応じてメモリを 512 MiB → 1 GiB へ引き上げる。
4. **ローカルブラウザ起動 (`webbrowser.open`)**  
   * サーバ側では不要。GUI が無い環境で例外になるため、本番ビルド時は WebBrowser 呼び出しを無効化 (環境変数でスキップ) する。
5. **TIME_ZONE / 日本語サイト**  
   * `Asia/Tokyo` 設定により JST ログ取得可。日本語 PDF 等の取得時、フォント不足エラーがあれば `fonts-noto-cjk` を追加。

---

## 5. その他の設計ポイント
### 5.1 環境変数と Secret Manager
| 区分 | 格納先 | 備考 |
|------|--------|------|
| DB/Supabase URL, API_KEY | Secret Manager | Cloud Build → Cloud Run で `--set-secrets`|
| Flask `SECRET_KEY` | Secret Manager | セキュアなランダム値を登録 |
| その他設定 (`MODE`, `DEBUG`) | Cloud Run 環境変数 | GUI 無効化フラグも含む |

### 5.2 スケジュール & バッチ
* **Cloud Scheduler + Pub/Sub** で HTTP トリガーを呼び出し、アプリ内 APScheduler を簡素化。

### 5.3 ビルド & デプロイ パイプライン
```bash
# 手動例 (要 gcloud  CLI)
gcloud builds submit --tag gcr.io/<PROJECT_ID>/anknavicho:latest

gcloud run deploy ank-nav-service \
  --image gcr.io/<PROJECT_ID>/anknavicho:latest \
  --platform managed \
  --region asia-northeast1 \
  --port 8080 \
  --set-env-vars PORT=8080
```
* Cloud Build Trigger (main ブランチ push 時) を設定すると CI/CD が自動化。

### 5.4 ログ・モニタリング
* Cloud Logging に自動連携。`uvicorn` などを使う場合、`--access-log` を標準出力に統一。
* Cloud Monitoring Alert で CPU/メモリ閾値を監視。

### 5.5 コスト試算
| 項目 | 想定単価 (東京リージョン) | 備考 |
|------|---------------------------|------|
| Cloud Run (0.25 vCPU / 512 MiB) | 約 0.000024 US$/秒 | 無通信で scale-to-zero 時は無料 |
| Cloud SQL / Firestore など | オプション | 省略 |
| Secret Manager | 0.03 US$/10 万 call | 低コスト |

---

## 6. まとめ
* **Cloud Run コンテナ** + **ヘッドレス Chrome** の組み合わせで Selenium を利用可能。
* Chrome と ChromeDriver のバージョン整合性、およびメモリ使用量に注意。
* `webbrowser.open` など GUI 依存コードはデプロイフラグで無効化すること。
* **FastAPI** では `/health` など軽量エンドポイントを実装し、Cloud Run 健康チェックに指定する。
* CI/CD → Cloud Build + Cloud Run Trigger、Secrets → Secret Manager で安全に運用。

> この設計書を基に、詳細タスク (Dockerfile 作成・コード調整・CI 設定) を進めてください。 