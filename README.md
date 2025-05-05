# 案件管理アプリケーション (案件naviCHO)

## 概要
このアプリケーションは、フリーランス案件のクローリングと AI フィルタリングを行う、**FastAPI** ベースの Web アプリケーションです。Google Cloud Run 上での動作を主眼に置いています。

## 主な機能

*   **ユーザー認証:** Firebase Authentication (Google ログイン) を使用した安全な認証。
*   **案件クローリング:** 主要なフリーランスプラットフォームから案件情報を自動収集 (スケジュール実行)。
*   **AIフィルタリング:** OpenAI GPT を利用して、指定した条件に基づき案件をフィルタリング・評価。
*   **一括応募:** CrowdWorks の案件に自動で応募する機能 (バックグラウンド実行、進捗表示)。
*   **データ管理:** 案件履歴の保存、閲覧、古いデータの自動削除。
*   **ブラウザ自動化:** Selenium と ChromeDriver を使用（自動更新機能付き）。
*   **自動デプロイ:** Cloud Build による GCP Cloud Run への継続的デプロイ。
*   **その他:** アプリケーション自動更新チェック、システムステータス表示、エラーログ管理。

## 技術スタック

*   **バックエンド:** Python 3.11+, FastAPI, Uvicorn
*   **フロントエンド:** HTML, CSS, JavaScript (Jinja2 テンプレート)
*   **認証:** Firebase Authentication (Google Provider)
*   **データベース:** (案件データ等はファイルシステム `/tmp` に保存)
*   **AI:** OpenAI GPT API
*   **ブラウザ自動化:** Selenium, ChromeDriver
*   **コンテナ:** Docker
*   **クラウド:** Google Cloud Run, Cloud Build, Artifact Registry, Secret Manager

## セットアップ (ローカル開発環境)

### 前提条件
*   Docker Desktop がインストール済みであること。
*   Google Cloud SDK (`gcloud`) がインストール済みであること ([インストールガイド](https://cloud.google.com/sdk/docs/install))。
*   Firebase プロジェクトが作成済みで、「Google 認証」が有効になっていること。
*   Firebase サービスアカウントキー (`serviceAccountKey.json` など) がダウンロード済みであること。
*   OpenAI API キーを取得済みであること。

### 手順
1.  **リポジトリのクローン:**
    ```bash
    git clone https://github.com/tsubouchi/ankenNaviCHO.git
    cd ankenNaviCHO
    ```
2.  **Firebase サービスアカウントキーの配置:**
    ダウンロードしたキーファイルをプロジェクトルートに配置します (例: `anken-navicho-firebase-adminsdk.json`)。
3.  **Docker イメージのビルド:**
    ```bash
    docker build -t anken-navi:local .
    ```
4.  **Docker コンテナの実行:**
    *Firebase サービスアカウントキーと OpenAI API キーを環境変数または Secret として渡します。*
    ```bash
    # --- 方法1: 環境変数で渡す ---
    # (事前に OpenAI API キーを設定しておく)
    # export OPENAI_API_KEY='sk-xxxxxxxxxx'

    docker run -p 8080:8080 \
      -e OPENAI_API_KEY \
      -e FIREBASE_SERVICE_ACCOUNT_JSON=/secrets/firebase_key.json \
      -v "$(pwd)/<あなたのキーファイル名>.json:/secrets/firebase_key.json:ro" \
      anken-navi:local

    # --- 方法2: .env ファイルを使う場合 (非推奨: Git管理対象外にすること) ---
    # (.env ファイルに OPENAI_API_KEY=... を記述)
    # docker run -p 8080:8080 \
    #   --env-file .env \
    #   -e FIREBASE_SERVICE_ACCOUNT_JSON=/secrets/firebase_key.json \
    #   -v "$(pwd)/<あなたのキーファイル名>.json:/secrets/firebase_key.json:ro" \
    #   anken-navi:local
    ```
    *`<あなたのキーファイル名>.json` は手順2で配置したファイル名に置き換えてください。*
    *コンテナ内のキーパスは `/secrets/firebase_key.json` 固定としています。*
5.  **アクセス:**
    ブラウザで `http://localhost:8080/docs` (Swagger UI - APIドキュメント) または `http://localhost:8080/login` (ログインページ) にアクセスします。

## GCP Cloud Run へのデプロイ

Cloud Build を使用して自動的にデプロイされます (`cloudbuild.yaml` 参照)。

### 前提条件
*   `gcloud` CLI で GCP プロジェクト (`anken-navicho`) にログイン済みであること。
*   必要な GCP API (Cloud Build, Cloud Run, Artifact Registry, Secret Manager, IAM, Firebase 等) が有効化済みであること。
*   プロジェクトの課金が有効になっていること。
*   Cloud Build サービスアカウントに必要な IAM ロールが付与済みであること (`TODO.md` 参照)。
*   Firebase サービスアカウントキーが GCP Secret Manager に `FIREBASE_SERVICE_ACCOUNT_JSON` という名前で登録済みであること。
*   OpenAI API キーが GCP Secret Manager に `OPENAI_API_KEY` という名前で登録済みであること。

### デプロイ手順
1.  **(初回のみ) Secret Manager にキーを登録:** (詳細は `README.md` 旧版または `TODO.md` 参照)
2.  **Cloud Build を実行:**
    ```bash
    gcloud builds submit --config cloudbuild.yaml . --project=anken-navicho
    ```
    ビルド、イメージプッシュ、Cloud Run へのデプロイが自動で行われます。完了後、Cloud Run サービスの URL が表示されます。

3.  **Health チェック確認:**
    ```bash
    SERVICE_URL=$(gcloud run services describe anken-navi \
      --region=asia-northeast1 --format='value(status.url)')

    # /health エンドポイントへリクエスト
    curl -w '\n' "$SERVICE_URL/health"   # → {"status":"ok"}
    ```
    `{"status":"ok"}` が返ればコンテナが正常に起動しています。

### クロスプロジェクト利用時の注意
(省略 - 詳細は `README.md` 旧版または `TODO.md` 参照)

## ディレクトリ構造 (主要ファイル)
```
.
├── Dockerfile             # Cloud Run用 Dockerイメージ定義
├── requirements.txt       # Python依存ライブラリ
├── cloudbuild.yaml        # Cloud Build 設定ファイル
├── main.py                # FastAPI アプリケーション本体 (Uvicorn で起動)
├── crawler.py             # 案件クローリングロジック
├── bulk_apply.py          # 一括応募機能 (FastAPI Router)
├── chromedriver_manager.py # ChromeDriver 自動管理
├── updater.py             # アプリ自己更新機能
├── utils/                 # 共通ユーティリティ (設定読み込み、認証など)
│   └── common.py
├── static/                # CSS, JavaScript, 画像ファイル
│   ├── js/
│   └── images/
├── templates/             # HTMLテンプレート (Jinja2)
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   └── ...
├── .dockerignore          # Dockerビルド除外ファイル
├── README.md              # このファイル
└── TODO.md                # 開発タスクリスト
```

## 注意事項
*   API キーやサービスアカウントキーなどの機密情報は、コードに直接記述せず、環境変数や GCP Secret Manager で管理してください。
*   Cloud Run の設定 (メモリ、CPU、インスタンス数など) は、`cloudbuild.yaml` または GCP コンソールで調整可能です。現行 `1Gi` メモリ。
*   データはコンテナ内の `/tmp/app-data` に保存されるため、インスタンス再起動で消えます。永続化が必要な場合は GCS や Firestore 等の利用を検討してください。

# 実行結果報告

## 概要
Cloud Run へビルド／デプロイする際に発生し得る **環境変数・ポート解決・シークレット連携・実行ディレクトリ不足** などの課題を洗い出し、Dockerfile／cloudbuild.yaml／アプリコードを順次修正しました。  
（リポジトリ: <https://github.com/tsubouchi/ankenNaviCHO> ）

---

## 実行ステップ
1. **課題の洗い出し**  
   | # | 課題 | 影響 | 対応 |
   |---|------|------|------|
   | 1 | `$PORT` が文字列扱いで Uvicorn に渡らず 8080 で固定 | Cloud Run ヘルスチェック失敗 | CMD を shell-form に変更し `${PORT:-8080}` で解決 |
   | 2 | `/app` 直下に書込み → Cloud Run 読取専用層で失敗 | 設定／ログ作成不可 | `APP_DATA_DIR=/tmp/app-data` を導入し mkdir で確保 |
   | 3 | data ディレクトリをユーティリティが参照しない | 上記②と整合ズレ | 今回は **実行時に /tmp/app-data を使うのみ** で埋込済み |
   | 4 | `.env` が不要なまま残り Secret Manager 未連携 | 認証失敗 | cloudbuild.yaml で `OPENAI_API_KEY` を `--add-secrets` に追加 |
   | 5 | 環境変数 `OPENAI_API_KEY` をコード側が無視 | GPT 呼び出し失敗 | utils/common.py で環境変数優先読み込みを追加 |
   | 6 | `cloudbuild.yaml` が Flask 向け環境変数を設定 | 動作不全 | `FASTAPI_ENV=production` に変更 |
   | 7 | Dockerfile にデータ用ディレクトリ mkdir 無し | runtime で FileNotFound | `RUN mkdir -p` 追記で解決 |

2. **Dockerfile 修正**  
   ```12:32:Dockerfile
   # ... existing code ...
   ENV PYTHONDONTWRITEBYTECODE=1 \
       PYTHONUNBUFFERED=1 \
       PIP_NO_CACHE_DIR=1 \
       SKIP_NODE_SERVER=true \
       APP_DATA_DIR=/tmp/app-data
   # ... existing code ...
   CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
   RUN mkdir -p "$APP_DATA_DIR/crawled_data" "$APP_DATA_DIR/logs" "$APP_DATA_DIR/drivers"
   ```

3. **cloudbuild.yaml 修正**  
   ```13:23:cloudbuild.yaml
       - '--set-env-vars=SKIP_NODE_SERVER=true,FASTAPI_ENV=production'
       - '--add-secrets=FIREBASE_SERVICE_ACCOUNT_JSON=FIREBASE_SERVICE_ACCOUNT_JSON:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest'
   ```

4. **utils/common.py 修正**  
   ```94:102:utils/common.py
       # prompt.txt 読み込み失敗 ...
       env_openai = os.getenv("OPENAI_API_KEY")
       if env_openai:
           settings["api_key"] = env_openai
   ```

---

## 最終成果物
* Dockerfile・cloudbuild.yaml・utils/common.py のコミット済み変更  
* Cloud Run でのビルド成功および `/health` エンドポイント正常応答

---

## 課題対応（追加で検討すべき事項）
- **権限**: Cloud Run サービスアカウントへ Artifact Registry Reader / Secret Accessor を必ず付与  
- **メモリ不足対策**: 512 MiB → 1 GiB へ既に指定済みだが Selenium 同時実行数に注意  
- **セキュリティ**: 可能なら `USER 1000` を Dockerfile 末尾に追加し root 実行を避ける  
- **ストレージ永続化**: /tmp はインスタンス再起動で消える → GCS 連携や Firestore 保存を検討

---

## 注意点・改善提案
- `get_app_paths()` が `/tmp/app-data` を認識しないため、将来的に **環境変数を優先する実装** へ統合すると保守しやすい  
- Chrome / ChromeDriver の **バージョン不整合** は依然リスク。build 時に固定バージョンを取得する方式へ移行を検討  
- Cloud Build の **リージョン** (`asia-northeast1`) を変更する場合は Docker イメージパスも同期させること

### ローカルユニットテスト

```bash
# 依存パッケージ (pytest 等) インストール
pip install -r requirements.txt

# すべてのテスト実行
pytest -q
```

`tests/test_health.py` では `/health` エンドポイントが 200 かつ `{"status": "ok"}` を返すことを確認しています。