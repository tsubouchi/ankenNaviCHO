# 案件管理アプリケーション (案件naviCHO)

## 概要
このアプリケーションは、フリーランス案件のクローリングと AI フィルタリングを行う、Google Cloud Run 上で動作する **FastAPI** ベースの Web アプリケーションです。

## 主な機能

*   **ユーザー認証:** Firebase Authentication (Google ログイン) を使用した安全な認証。
*   **案件クローリング:** 主要なフリーランスプラットフォームから案件情報を自動収集 (スケジュール実行)。
*   **AIフィルタリング:** OpenAI GPT を利用して、指定した条件に基づき案件をフィルタリング・評価。
*   **データ管理:** 案件履歴の保存、閲覧、古いデータの自動削除。
*   **ブラウザ自動化:** Selenium と ChromeDriver を使用（自動更新機能付き）。
*   **自動デプロイ:** Cloud Build による GCP Cloud Run への継続的デプロイ。
*   **その他:** アプリケーション自動更新チェック、システムステータス表示、エラーログ管理。

## 技術スタック

*   **バックエンド:** Python 3.11+, FastAPI, Uvicorn
*   **フロントエンド:** HTML, CSS, JavaScript
*   **認証:** Firebase Authentication (Google Provider)
*   **データベース:** (案件データ等はファイルシステムに保存)
*   **AI:** OpenAI GPT API
*   **ブラウザ自動化:** Selenium, ChromeDriver
*   **コンテナ:** Docker
*   **クラウド:** Google Cloud Run, Cloud Build, Artifact Registry, Secret Manager

## セットアップ (ローカル開発環境)

### 前提条件
*   Docker Desktop がインストール済みであること。
*   Google Cloud SDK (`gcloud`) がインストール済みであること ([インストールガイド](https://cloud.google.com/sdk/docs/install))。
*   Firebase プロジェクトが作成済みで、「Google 認証」が有効になっていること。
*   Firebase サービスアカウントキー (`serviceAccountKey.json`) がダウンロード済みであること。
*   OpenAI API キーを取得済みであること。

### 手順
1.  **リポジトリのクローン:**
    ```bash
    git clone <リポジトリURL>
    cd ankenNaviCHO
    ```
2.  **Firebase サービスアカウントキーの配置:**
    ダウンロードした `serviceAccountKey.json` (または任意の名前に変更) をプロジェクトルートに配置します。
3.  **環境変数ファイルの作成 (`.env`):**
    プロジェクトルートに `.env` ファイルを作成し、以下の内容を記述します。
    ```dotenv
    # FastAPI 関連
    APP_SECRET_KEY='<強力なランダム文字列を生成して設定>' # 例: openssl rand -hex 32
    FASTAPI_ENV=development

    # Firebase
    # FIREBASE_SERVICE_ACCOUNT_JSON='/path/to/your/serviceAccountKey.json' # Docker外で動かす場合
    # Dockerfile内では /secrets/ 以下のパスをデフォルト参照

    # OpenAI
    OPENAI_API_KEY='sk-xxxxxxxxxx'

    # (任意) クローラー認証情報 (ローカルでクローラーをテストする場合)
    # CROWDWORKS_EMAIL=
    # CROWDWORKS_PASSWORD=
    # COCONALA_EMAIL=
    # COCONALA_PASSWORD=

    # (任意) Supabase (もし支払い機能等で利用継続する場合)
    # SUPABASE_URL=
    # SUPABASE_ANON_KEY=

    # Docker実行時の設定
    SKIP_NODE_SERVER=true # Node.js 開発サーバーは使用しない
    ```
4.  **Docker イメージのビルド:**
    ```bash
    docker build -t anken-navi:local .
    ```
5.  **Docker コンテナの実行:**
    *Firebase サービスアカウントキーを Secret としてマウントします。*
    ```bash
    # 絶対パスを指定
    docker run -p 8080:8080 \\
      --env-file .env \\
      -v "$(pwd)/<あなたのキーファイル名>.json:/secrets/FIREBASE_SERVICE_ACCOUNT_JSON:ro" \\
      anken-navi:local
    ```
    *`<あなたのキーファイル名>.json` は手順2で配置したファイル名に置き換えてください。*
6.  **アクセス:**
    ブラウザで `http://localhost:8080/docs` (Swagger UI) または `http://localhost:8080` (トップページ) にアクセスします。

## GCP Cloud Run へのデプロイ

Cloud Build を使用して自動的にデプロイされます。

### 前提条件
*   `gcloud` CLI で GCP プロジェクト (`anken-navicho`) にログイン済みであること。
*   必要な GCP API (Cloud Build, Cloud Run, Artifact Registry, Secret Manager, IAM, Firebase 等) が有効化済みであること。
*   プロジェクトの課金が有効になっていること。
*   Cloud Build サービスアカウントに必要な IAM ロールが付与済みであること (詳細は `TODO.md` の履歴参照)。
*   Firebase サービスアカウントキーが GCP Secret Manager に `FIREBASE_SERVICE_ACCOUNT_JSON` という名前で登録済みであること。
*   OpenAI API キーが GCP Secret Manager に `OPENAI_API_KEY` という名前で登録済みであること (推奨)。

### デプロイ手順
1.  **(初回のみ) OpenAI API キーを Secret Manager に登録:**
    ```bash
    echo -n "sk-xxxxxxxxxx" | gcloud secrets create OPENAI_API_KEY --data-file=- --project=anken-navicho
    # Cloud Run サービスにバインド (cloudbuild.yamlで指定も可)
    # gcloud run services update anken-navi --region=asia-northeast1 --add-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest" --project=anken-navicho
    ```
2.  **Cloud Build を実行:**
    ```bash
    gcloud builds submit --config cloudbuild.yaml . --project=anken-navicho
    ```
    ビルド、イメージプッシュ、Cloud Run へのデプロイが自動で行われます。完了後、Cloud Run サービスの URL が表示されます。

### クロスプロジェクト利用時の注意
Cloud Run を **別プロジェクト (例: `specsheet-generator`)** で動かし、
Artifact Registry にあるイメージを **`anken-navicho`** から Pull する場合は次の追加手順が必要です。

1. **Cloud Run サービス エージェントに Reader 権限を付与**
   ```bash
   # IMAGE_PROJECT = イメージを保持するプロジェクト
   IMAGE_PROJECT=anken-navicho
   REPO=anken-docker-repo
   REGION=asia-northeast1
   RUN_SA="service-XXXXXXXXXXXX@serverless-robot-prod.iam.gserviceaccount.com" # Cloud Run 側の SA

   gcloud artifacts repositories add-iam-policy-binding ${REPO} \
     --location=${REGION} \
     --project=${IMAGE_PROJECT} \
     --member="serviceAccount:${RUN_SA}" \
     --role="roles/artifactregistry.reader"
   ```
2. **必要な Secret を Cloud Run プロジェクト側でも作成**  
   `FIREBASE_SERVICE_ACCOUNT_JSON`, `OPENAI_API_KEY` などを
   `gcloud secrets create ...` で同じ名前で登録しておく。

これらが揃っていない場合、デプロイ時に 403 (image pull) や 404 (secret not found) エラーになります。

## ディレクトリ構造 (主要ファイル)
```
.
├── Dockerfile             # Cloud Run用 Dockerイメージ定義
├── requirements.txt       # Python依存ライブラリ
├── cloudbuild.yaml        # Cloud Build 設定ファイル
├── main.py                # FastAPI アプリケーション本体
├── crawler.py             # 案件クローリングロジック
├── chromedriver_manager.py # ChromeDriver 自動管理
├── updater.py             # アプリ自己更新機能
├── bulk_apply.py          # 一括応募機能 (現状未使用？)
├── fix_settings_patch.py  # 設定ファイル関連ユーティリティ
├── static/                # CSS, JavaScript, 画像ファイル
│   ├── js/
│   └── images/
├── templates/             # HTMLテンプレート
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── top.html
│   └── ...
├── .env.example           # 環境変数設定例 (Git管理推奨)
├── .dockerignore          # Dockerビルド除外ファイル
├── README.md              # このファイル
└── ... (その他設定ファイル、ログディレクトリ等)
```

## 注意事項
*   API キーやサービスアカウントキーなどの機密情報は、`.env` ファイルやコードに直接記述せず、GCP Secret Manager などの安全な方法で管理してください。
*   Cloud Run の設定 (メモリ、CPU、インスタンス数など) は、`cloudbuild.yaml` または GCP コンソールで調整可能です。