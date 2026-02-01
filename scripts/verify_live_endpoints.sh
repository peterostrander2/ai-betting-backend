#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"
API_KEY="${API_KEY:-}"

if [ -z "$BASE_URL" ] || [ -z "$API_KEY" ]; then
  echo "Usage: BASE_URL=... API_KEY=... bash scripts/verify_live_endpoints.sh"
  exit 2
fi

function check_endpoint() {
  local path="$1"
  local label="$2"

  echo "== $label ($path) =="
  resp=$(curl -sS -H "X-API-Key: $API_KEY" "$BASE_URL$path" || true)
  echo "$resp" | jq . >/dev/null 2>&1 || { echo "Invalid JSON for $path"; exit 1; }

  source=$(echo "$resp" | jq -r '.source // ""')
  generated=$(echo "$resp" | jq -r '.generated_at // ""')
  data_len=$(echo "$resp" | jq -r 'if (.data|type)=="array" then (.data|length) else if (.data|type)=="object" then ("object") else "" end')
  errors_len=$(echo "$resp" | jq -r '.errors | length // 0')

  echo "source: $source"
  echo "generated_at: $generated"
  echo "data_len: $data_len"
  echo "errors: $errors_len"
  echo ""

  if [ "$path" = "/live/best-bets/NBA" ]; then
    if [ -z "$source" ] || [ -z "$generated" ]; then
      echo "Missing required fields in $path"; exit 1; 
    fi
  fi
}

echo "== health (/health) =="
health_resp=$(curl -sS -H "X-API-Key: $API_KEY" "$BASE_URL/health" || true)
echo "$health_resp" | jq . >/dev/null 2>&1 || { echo "Invalid JSON for /health"; exit 1; }
echo "status: $(echo "$health_resp" | jq -r '.status // "unknown"')"
echo ""

check_endpoint "/ops/storage" "ops storage"
check_endpoint "/ops/integrations" "ops integrations"
check_endpoint "/live/best-bets/NBA" "best bets NBA"
