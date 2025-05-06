#!/usr/bin/env bash
# =============================================================
# anken-navi Cloud Run API 総合テストスクリプト
# -------------------------------------------------------------
#   使い方: ./test_endpoints.sh <BASE_URL> [ID_TOKEN]
#   BASE_URL : Cloud Run サービス URL (末尾スラッシュ不要)
#   ID_TOKEN : Firebase ID トークン (認証必須 API 用、省略可)
# =============================================================

set -euo pipefail

BASE_URL="${1:-}"
ID_TOKEN="${2:-}"

if [[ -z "$BASE_URL" ]]; then
  echo "Usage: $0 <BASE_URL> [ID_TOKEN]" >&2
  exit 1
fi

# -------- 共通関数 -------------------------------------------------
blue() { echo -e "\e[1;34m$*\e[0m"; }
sep()  { printf "\n%s\n" "----------------------------------------------"; }
code() { echo "+ curl -s -o /dev/null -w '%{http_code}\\n' $*"; }

# -------- テストケース定義 ----------------------------------------
# フォーマット: method|path|auth|body
#   auth = none|bearer|cookie
TESTS=(
  "GET|/health|none|"
  "GET|/top|none|"
  "GET|/login|none|"
  "POST|/api/login|none|{\"idToken\":\"${ID_TOKEN}\"}"
  "GET|/api/placeholder|bearer|"
  "POST|/api/update_settings|bearer|{}"
  "POST|/api/check_auth|bearer|{\"service\":\"crowdworks\"}"
  "POST|/api/fetch_new_data|bearer|{}"
  "GET|/api/job_history/files|bearer|"
  "GET|/api/get_checks|cookie|"
)

# -------- 実行ループ ----------------------------------------------
idx=1
for test in "${TESTS[@]}"; do
  IFS='|' read -r METHOD PATH AUTH BODY <<<"$test"

  blue "${idx}) ${PATH} (${METHOD}) [auth:${AUTH}]"

  URL="${BASE_URL}${PATH}"
  CURL_OPTS=("-s" "-o" "/dev/null" "-w" "%{http_code}\n")

  case "$AUTH" in
    bearer)
      if [[ -z "$ID_TOKEN" ]]; then echo "  ※ID_TOKEN 未指定、スキップ"; sep; ((idx++)); continue; fi
      CURL_OPTS+=("-H" "Authorization: Bearer ${ID_TOKEN}")
      ;;
    cookie)
      if [[ -z "$ID_TOKEN" ]]; then echo "  ※ID_TOKEN 未指定、スキップ"; sep; ((idx++)); continue; fi
      CURL_OPTS+=("--cookie" "idToken=${ID_TOKEN}")
      ;;
  esac

  [[ "$METHOD" == "POST" ]] && CURL_OPTS+=("-H" "Content-Type: application/json" "-d" "${BODY}")

  code "${CURL_OPTS[*]} $URL"
  HTTP_CODE=$(curl "${CURL_OPTS[@]}" "$URL")
  echo "HTTP ${HTTP_CODE}"

  # レスポンスボディも表示
  curl -i "${CURL_OPTS[@]/-s/}" "$URL"
  sep
  ((idx++))
done

echo "✅ テスト完了"