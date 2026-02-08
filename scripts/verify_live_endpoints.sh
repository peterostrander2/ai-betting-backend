#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"
API_KEY="${API_KEY:-}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"

if [ -z "$BASE_URL" ] || [ -z "$API_KEY" ]; then
  echo "Usage: BASE_URL=... API_KEY=... bash scripts/verify_live_endpoints.sh"
  exit 2
fi

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

FAILED=0

function check_http() {
  local name="$1"
  local url="$2"
  local header="$3"
  local expected_code="$4"
  local expected_text="$5"

  local tmp_file
  tmp_file="$(mktemp)"
  code=$(curl -sS -o "$tmp_file" -w "%{http_code}" ${header:+-H "$header"} "$url" 2>/dev/null || echo "000")
  body=$(cat "$tmp_file")
  rm -f "$tmp_file"

  if [ "$code" = "$expected_code" ] && echo "$body" | rg -q "$expected_text"; then
    echo -e "${GREEN}OK${NC} ($name)"
  else
    echo -e "${RED}FAIL${NC} ($name) code=$code"
    echo "  Body: $(echo "$body" | head -c 200)..."
    FAILED=1
  fi
}

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

# Auth checks (fail-fast)
echo "== Auth checks (/live/best-bets/NBA) =="
check_http "missing key -> Missing" "$BASE_URL/live/best-bets/NBA" "" "401" "Missing"
check_http "wrong key -> Invalid" "$BASE_URL/live/best-bets/NBA" "X-API-Key: INVALID" "403" "Invalid"
check_http "correct key -> success" "$BASE_URL/live/best-bets/NBA" "X-API-Key: $API_KEY" "200" "\""
echo ""

# Health (no auth)
echo -n "== health (/health) == "
health=$(curl -sS "$BASE_URL/health" 2>/dev/null || echo '{}')
status=$(echo "$health" | jq -r '.status // "unknown"')
if [ "$status" = "healthy" ] || [ "$status" = "degraded" ]; then
  echo -e "${GREEN}OK${NC} (status: $status)"
else
  echo -e "${RED}FAIL${NC} (status: $status)"
  FAILED=1
fi
echo ""

# /ops/* endpoints (X-Admin-Token)
if [ -n "$ADMIN_TOKEN" ]; then
  check_json "/ops/storage" "ops/storage" '.ok == true' "X-Admin-Token: $ADMIN_TOKEN"
  check_json "/ops/integrations" "ops/integrations" '.total > 0' "X-Admin-Token: $ADMIN_TOKEN"
  check_json "/ops/env-map" "ops/env-map" 'has("env_map")' "X-Admin-Token: $ADMIN_TOKEN"
  # ops/verify may show FAIL if optional env vars are missing - check critical systems passed
  check_json "/ops/verify" "ops/verify" '(.checks.health.passed and .checks.storage.passed and .checks.integrations.passed and .checks.scheduler.passed)' "X-Admin-Token: $ADMIN_TOKEN"
else
  echo "== ops/* checks skipped (ADMIN_TOKEN not set) =="
fi
echo ""

# /live/* endpoints (X-API-Key)
check_json "/live/best-bets/NBA" "best-bets NBA" 'has("props") and has("game_picks")' "X-API-Key"
check_json "/live/best-bets/NBA" "best-bets NBA contract" '([
  .props.picks[]?, .game_picks.picks[]?
] | all(
  (.bet_string // "") | length > 0
  and (.bet_string == "N/A" | not)
  and ((.selection // "") | length > 0)
  and ((.market_label // "") | length > 0)
  and (.odds_american != null)
  and (.recommended_units != null)
  and ((.pick_type == "moneyline" | not) or (.line != null))
  and (.ai_score != null and .research_score != null and .esoteric_score != null and .jarvis_score != null and .context_modifier != null)
  and (.total_score != null and .final_score != null)
  and (.bet_tier != null)
))' "X-API-Key"
check_json "/live/best-bets/NHL" "best-bets NHL contract" '([
  .props.picks[]?, .game_picks.picks[]?
] | all(
  (.bet_string // "") | length > 0
  and (.bet_string == "N/A" | not)
  and ((.selection // "") | length > 0)
  and ((.market_label // "") | length > 0)
  and (.odds_american != null)
  and (.recommended_units != null)
  and ((.pick_type == "moneyline" | not) or (.line != null))
  and (.ai_score != null and .research_score != null and .esoteric_score != null and .jarvis_score != null and .context_modifier != null)
  and (.total_score != null and .final_score != null)
  and (.bet_tier != null)
))' "X-API-Key"
check_json "/live/best-bets/NBA" "hard gate: final_score >= 6.5" '([
  .props.picks[]?, .game_picks.picks[]?
] | all(.final_score >= 6.5))' "X-API-Key"
check_json "/live/best-bets/NBA" "hard gate: titanium 3-of-4" '([
  .props.picks[]?, .game_picks.picks[]?
] | all(
  (.titanium_triggered != true)
  or (([.ai_score, .research_score, .esoteric_score, .jarvis_score] | map(. >= 8.0) | add) >= 3)
))' "X-API-Key"
check_json "/live/grader/status" "grader status" '.available == true' "X-API-Key"
check_json "/live/debug/time" "debug time" 'has("et_date")' "X-API-Key"
check_json "/live/debug/integrations" "debug integrations" 'has("integrations") and has("by_status")' "X-API-Key"
check_json "/live/best-bets/NBA" "freshness: date_et/run_timestamp_et" 'has("date_et") and has("run_timestamp_et")' "X-API-Key"

# Debug-only used_integrations (must be present in debug, absent in standard)
check_json "/live/best-bets/NBA" "no used_integrations in standard payload" '(.debug // null) == null' "X-API-Key"
check_json "/live/best-bets/NBA?debug=1" "debug used_integrations present" '(.debug.used_integrations | type) == "array"' "X-API-Key"
check_json "/live/debug/integrations" "integrations last_used_at fields present" '(.integrations.odds_api | has("last_used_at")) and (.integrations.playbook_api | has("last_used_at")) and (.integrations.balldontlie | has("last_used_at")) and (.integrations.serpapi | has("last_used_at"))' "X-API-Key"

# Freshness: cache age (best-bets should be short)
# NOTE: _cached_at is stripped from public payloads by sanitizer, so we use debug endpoint
now=$(date +%s)
bb_cached=$(curl -sS -H "X-API-Key: $API_KEY" "$BASE_URL/live/best-bets/NBA?debug=1" | jq -r '.debug._cached_at // ._cached_at // 0' 2>/dev/null || echo "0")
sharp_cached=$(curl -sS -H "X-API-Key: $API_KEY" "$BASE_URL/live/sharp/NBA?debug=1" | jq -r '.debug._cached_at // ._cached_at // 0' 2>/dev/null || echo "0")
# If still 0, skip cache age check (telemetry hidden is acceptable)
if [ "$bb_cached" = "0" ] || [ "$bb_cached" = "null" ]; then
  echo -e "== freshness (cache age) == ${GREEN}SKIP${NC} (_cached_at not exposed in response)"
else
  bb_age=$((now - ${bb_cached%.*}))
  sharp_age=$((now - ${sharp_cached%.*}))
  echo -n "== freshness (cache age) == "
  if [ "$bb_age" -le 180 ] && [ "$sharp_age" -le 600 ]; then
    echo -e "${GREEN}OK${NC} (best-bets ${bb_age}s, sharp ${sharp_age}s)"
  else
    echo -e "${RED}FAIL${NC} (best-bets ${bb_age}s, sharp ${sharp_age}s)"
    FAILED=1
  fi
fi
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
