#!/bin/bash
# POST-DEPLOY VERIFICATION
# Run after every Railway deployment to catch runtime/env drift
# Usage: ./scripts/post_deploy_check.sh

set -euo pipefail

BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-}"

echo "============================================"
echo "POST-DEPLOY VERIFICATION"
echo "Base URL: $BASE_URL"
echo "Time: $(date)"
echo "============================================"
echo ""

PASS=0
FAIL=0

check() {
  local name="$1"
  local result="$2"
  if [ "$result" = "true" ]; then
    echo "✅ $name"
    PASS=$((PASS + 1))
  else
    echo "❌ $name"
    FAIL=$((FAIL + 1))
  fi
}

# 0. Require API_KEY for authenticated checks
if [ -z "$API_KEY" ]; then
  echo "❌ API_KEY is not set. Export API_KEY and rerun."
  exit 1
fi

# 1. Health endpoint
echo "[1/4] Health endpoint..."
HEALTH=$(curl -s "$BASE_URL/health" -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")
HEALTH_OK=$(echo "$HEALTH" | jq -r '.status != "critical"' 2>/dev/null || echo "false")
check "Health: status != critical" "$HEALTH_OK"

# 2. Storage health
echo "[2/4] Storage health..."
STORAGE=$(curl -s "$BASE_URL/internal/storage/health" -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")
STORAGE_OK=$(echo "$STORAGE" | jq -r '.ok == true and .is_mountpoint == true and .predictions_exists == true' 2>/dev/null || echo "false")
PRED_COUNT=$(echo "$STORAGE" | jq -r '.predictions_line_count // 0' 2>/dev/null || echo "0")
check "Storage: mounted, predictions exist ($PRED_COUNT picks)" "$STORAGE_OK"

# 3. Integrations
echo "[3/4] Integrations..."
INTEGRATIONS=$(curl -s "$BASE_URL/live/debug/integrations" -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")
INT_STATUS=$(echo "$INTEGRATIONS" | jq -r '.overall_status' 2>/dev/null || echo "UNKNOWN")
VALIDATED=$(echo "$INTEGRATIONS" | jq -r '.by_status.validated | length' 2>/dev/null || echo "0")
NOT_CONFIGURED=$(echo "$INTEGRATIONS" | jq -r '.by_status.not_configured | length' 2>/dev/null || echo "0")
INT_OK=$([ "$INT_STATUS" = "HEALTHY" ] && [ "$NOT_CONFIGURED" = "0" ] && echo "true" || echo "false")
check "Integrations: $INT_STATUS ($VALIDATED validated, $NOT_CONFIGURED missing)" "$INT_OK"

# 4. Scheduler status
echo "[4/4] Scheduler status..."
SCHEDULER=$(curl -s "$BASE_URL/live/scheduler/status" -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")
SCHED_OK=$(echo "$SCHEDULER" | jq -r '.available == true and .apscheduler_available == true' 2>/dev/null || echo "false")
AUDIT_TIME=$(echo "$SCHEDULER" | jq -r '.audit_time // "unknown"' 2>/dev/null || echo "unknown")
check "Scheduler: available, audit at $AUDIT_TIME" "$SCHED_OK"

# 5. Post-change gates
echo "[5/5] Post-change gates..."

# Auth: missing / wrong / correct
MISSING_CODE=$(curl -s -o /tmp/health_missing -w "%{http_code}" "$BASE_URL/live/best-bets/NBA" 2>/dev/null || echo "000")
INVALID_CODE=$(curl -s -o /tmp/health_invalid -w "%{http_code}" -H "X-API-Key: INVALID" "$BASE_URL/live/best-bets/NBA" 2>/dev/null || echo "000")
GOOD_CODE=$(curl -s -o /tmp/health_good -w "%{http_code}" -H "X-API-Key: $API_KEY" "$BASE_URL/live/best-bets/NBA" 2>/dev/null || echo "000")
MISSING_OK=$([ "$MISSING_CODE" = "401" ] && rg -q "Missing" /tmp/health_missing && echo "true" || echo "false")
INVALID_OK=$([ "$INVALID_CODE" = "403" ] && rg -q "Invalid" /tmp/health_invalid && echo "true" || echo "false")
GOOD_OK=$([ "$GOOD_CODE" = "200" ] && echo "true" || echo "false")
check "Auth: missing key -> Missing (401)" "$MISSING_OK"
check "Auth: wrong key -> Invalid (403)" "$INVALID_OK"
check "Auth: correct key -> success (200)" "$GOOD_OK"
rm -f /tmp/health_missing /tmp/health_invalid /tmp/health_good

# Shape + gates
BEST_BETS=$(curl -s "$BASE_URL/live/best-bets/NBA" -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")
SHAPE_OK=$(echo "$BEST_BETS" | jq -r '([
  .props.picks[]?, .game_picks.picks[]?
] | all(
  (.ai_score != null and .research_score != null and .esoteric_score != null and .jarvis_score != null and .context_modifier != null)
  and (.total_score != null and .final_score != null)
  and (.bet_tier != null)
))' 2>/dev/null || echo "false")
check "Shape: engine scores + total/final + bet_tier" "$SHAPE_OK"

GATE_SCORE_OK=$(echo "$BEST_BETS" | jq -r '([
  .props.picks[]?, .game_picks.picks[]?
] | all(.final_score >= 6.5))' 2>/dev/null || echo "false")
check "Hard gate: final_score >= 6.5" "$GATE_SCORE_OK"

TITANIUM_OK=$(echo "$BEST_BETS" | jq -r '([
  .props.picks[]?, .game_picks.picks[]?
] | all(
  (.titanium_triggered != true)
  or (([.ai_score, .research_score, .esoteric_score, .jarvis_score] | map(. >= 8.0) | add) >= 3)
))' 2>/dev/null || echo "false")
check "Hard gate: Titanium 3-of-4" "$TITANIUM_OK"

FAILSOFT_OK=$(echo "$BEST_BETS" | jq -r 'has("errors")' 2>/dev/null || echo "false")
check "Fail-soft: errors array present" "$FAILSOFT_OK"

INT_DEBUG=$(curl -s "$BASE_URL/live/debug/integrations" -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")
INT_LOUD_OK=$(echo "$INT_DEBUG" | jq -r 'has("by_status") and has("integrations")' 2>/dev/null || echo "false")
check "Fail-soft: /live/debug/integrations loud" "$INT_LOUD_OK"
INT_LAST_USED_OK=$(echo "$INT_DEBUG" | jq -r '(.integrations.odds_api | has("last_used_at")) and (.integrations.playbook_api | has("last_used_at")) and (.integrations.balldontlie | has("last_used_at")) and (.integrations.serpapi | has("last_used_at"))' 2>/dev/null || echo "false")
check "Integrations: last_used_at fields present" "$INT_LAST_USED_OK"

FRESH_OK=$(echo "$BEST_BETS" | jq -r 'has("date_et") and has("run_timestamp_et")' 2>/dev/null || echo "false")
check "Freshness: date_et + run_timestamp_et" "$FRESH_OK"

# Debug-only used_integrations must exist only in debug payload
DEBUG_BB=$(curl -s "$BASE_URL/live/best-bets/NBA?debug=1" -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")
USED_PRESENT=$(echo "$DEBUG_BB" | jq -r '(.debug.used_integrations | type) == "array"' 2>/dev/null || echo "false")
USED_ABSENT=$(echo "$BEST_BETS" | jq -r '(.debug // null) == null' 2>/dev/null || echo "false")
check "Debug: used_integrations present (debug=1)" "$USED_PRESENT"
check "Debug: used_integrations absent (debug=0)" "$USED_ABSENT"

NOW=$(date +%s)
BB_CACHED=$(echo "$BEST_BETS" | jq -r '._cached_at // 0' 2>/dev/null || echo "0")
SHARP=$(curl -s "$BASE_URL/live/sharp/NBA" -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")
SHARP_CACHED=$(echo "$SHARP" | jq -r '._cached_at // 0' 2>/dev/null || echo "0")
BB_AGE=$((NOW - ${BB_CACHED%.*}))
SHARP_AGE=$((NOW - ${SHARP_CACHED%.*}))
TTL_OK=$([ "$BB_CACHED" != "0" ] && [ "$SHARP_CACHED" != "0" ] && [ "$BB_AGE" -le 180 ] && [ "$SHARP_AGE" -le 600 ] && echo "true" || echo "false")
check "Freshness: cache age (best-bets < sharp)" "$TTL_OK"

echo ""
echo "============================================"
if [ "$FAIL" -eq 0 ]; then
  echo "✅ ALL $PASS CHECKS PASSED"
  echo "Production is healthy after deploy."
  exit 0
else
  echo "❌ $FAIL CHECKS FAILED ($PASS passed)"
  echo "Investigate before proceeding!"
  exit 1
fi
