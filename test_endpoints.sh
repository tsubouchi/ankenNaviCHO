#!/usr/bin/env bash
# ==============================================
# anken-navi Cloud Run エンドポイント総合テスト
# ----------------------------------------------
#   実行例: ./test_endpoints.sh \
#              https://anken-navi-267332925025.asia-northeast1.run.app \
#              "YOUR_FIREBASE_IDTOKEN"
#   第1引数: ベースURL
#   第2引数: Firebase IDトークン（省略可）
# ==============================================

set -e

BASE_URL="${1:-https://example.run.app}"
ID_TOKEN="${2:-}"

# 共通関数 ----------------------------------------------------
sep () { printf "\n%s\n" "----------------------------------------------"; }
show () { echo -e "\e[1;34m$@\e[0m"; }            # 青色ヘッダ
curl_cmd () { echo "+ curl -s -o /dev/null -w '%{http_code}\\n' $*"; }

# 1. /health --------------------------------------------------
show "1) /health (GET)"
curl_cmd "${BASE_URL}/health"
curl -i "${BASE_URL}/health"
sep

# 2. /top -----------------------------------------------------
show "2) /top (GET)"
curl_cmd "${BASE_URL}/top"
curl -i "${BASE_URL}/top"
sep

# 3. /login ---------------------------------------------------
show "3) /login (GET)"
curl_cmd "${BASE_URL}/login"
curl -i "${BASE_URL}/login"
sep

# 4. /api/placeholder (認証必須) ------------------------------
show "4) /api/placeholder (GET, 要 Firebase IDToken)"
if [[ -z "$ID_TOKEN" ]]; then
  echo "   ※ID_TOKEN 未指定のためスキップ"
else
  curl_cmd -H "Authorization: Bearer ${ID_TOKEN}" \
           "${BASE_URL}/api/placeholder"
  curl -i -H "Authorization: Bearer ${ID_TOKEN}" \
       "${BASE_URL}/api/placeholder"
fi
sep

# 5. /api/login (POST, Cookie 設定) ---------------------------
show "5) /api/login (POST)"
if [[ -z "$ID_TOKEN" ]]; then
  echo "   ※ID_TOKEN 未指定のためスキップ"
else
  curl_cmd -X POST -H "Content-Type: application/json" \
           -d "{\"idToken\":\"${ID_TOKEN}\"}" \
           "${BASE_URL}/api/login"
  curl -i -X POST -H "Content-Type: application/json" \
       -d "{\"idToken\":\"${ID_TOKEN}\"}" \
       "${BASE_URL}/api/login"
fi
sep

# 6. /api/get_checks (GET, Cookie 認証) -----------------------
show "6) /api/get_checks (GET, Cookie 認証)"
if [[ -z "$ID_TOKEN" ]]; then
  echo "   ※ID_TOKEN 未指定のためスキップ"
else
  curl_cmd --cookie "idToken=${ID_TOKEN}" \
           "${BASE_URL}/api/get_checks"
  curl -i --cookie "idToken=${ID_TOKEN}" \
       "${BASE_URL}/api/get_checks"
fi
sep

echo "テスト完了"