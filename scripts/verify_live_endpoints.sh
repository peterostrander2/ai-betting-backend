#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"
API_KEY="${API_KEY:-}"

if [ -z "$BASE_URL" ] || [ -z "$API_KEY" ]; then
  echo "Usage: BASE_URL=... API_KEY=... bash scripts/verify_live_endpoints.sh"
  exit 2
fi

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

FAILED=0

function check_json() {
  local path="$1"
  local label="$2"
  local jq_test="$3"
  local header="${4:-X-API-Key}"

  echo -n "== $label ($path) == "
  resp=$(curl -sS -H "$header: $API_KEY" "$BASE_URL$path" 2>/dev/null || echo '{}')

  # Check if valid JSON
  if ! echo "$resp" | jq . >/dev/null 2>&1; then
    echo -e "${RED}FAIL${NC} (invalid JSON)"
    FAILED=1
    return
  fi

  # Run jq test
  result=$(echo "$resp" | jq -r "$jq_test" 2>/dev/null || echo "false")
  if [ "$result" = "true" ]; then
    echo -e "${GREEN}OK${NC}"
  else
    echo -e "${RED}FAIL${NC}"
    echo "  Response: $(echo "$resp" | jq -c '.' | head -c 200)..."
    FAILED=1
  fi
}

echo "================================================"
echo "LIVE ENDPOINT VERIFICATION"
echo "Base URL: $BASE_URL"
echo "================================================"
echo ""

# Health (no auth)
echo -n "== health (/health) == "
health=$(curl -sS "$BASE_URL/health" 2>/dev/null || echo '{}')
status=$(echo "$health" | jq -r '.status // "unknown"')
if [ "$status" = "healthy" ]; then
  echo -e "${GREEN}OK${NC} (status: $status)"
else
  echo -e "${RED}FAIL${NC} (status: $status)"
  FAILED=1
fi
echo ""

# /ops/* endpoints (X-Admin-Token)
check_json "/ops/storage" "ops/storage" '.ok == true' "X-Admin-Token"
check_json "/ops/integrations" "ops/integrations" '.total > 0' "X-Admin-Token"
check_json "/ops/env-map" "ops/env-map" 'has("env_map")' "X-Admin-Token"
# ops/verify may show FAIL if optional env vars are missing - check critical systems passed
check_json "/ops/verify" "ops/verify" '(.checks.health.passed and .checks.storage.passed and .checks.integrations.passed and .checks.scheduler.passed)' "X-Admin-Token"
echo ""

# /live/* endpoints (X-API-Key)
check_json "/live/best-bets/NBA" "best-bets NBA" 'has("props") and has("game_picks")' "X-API-Key"
check_json "/live/grader/status" "grader status" '.available == true' "X-API-Key"
check_json "/live/debug/time" "debug time" 'has("et_date")' "X-API-Key"
check_json "/live/debug/integrations" "debug integrations" 'has("integrations")' "X-API-Key"
echo ""

# /internal/* endpoints (no auth)
check_json "/internal/storage/health" "storage health" '.is_mountpoint == true' "X-API-Key"
echo ""

echo "================================================"
if [ "$FAILED" -eq 0 ]; then
  echo -e "${GREEN}ALL ENDPOINTS OK${NC}"
  exit 0
else
  echo -e "${RED}SOME ENDPOINTS FAILED${NC}"
  exit 1
fi
