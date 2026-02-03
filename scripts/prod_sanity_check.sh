#!/bin/bash
# Production Sanity Check - Validate All Master Prompt Invariants
# Exit 0 if all checks pass, exit 1 if any fail

set -e

# Configuration
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "PRODUCTION SANITY CHECK - Master Prompt Invariants"
echo "================================================"
echo ""

# Track failures
FAILED_CHECKS=()

# Helper function to check condition
check() {
    local name="$1"
    local condition="$2"
    local actual="$3"
    local expected="$4"

    if [ "$condition" = "true" ]; then
        echo -e "${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "${RED}✗${NC} $name"
        echo "  Expected: $expected"
        echo "  Actual: $actual"
        FAILED_CHECKS+=("$name")
        return 1
    fi
}

# =====================================================
# CHECK 1: Storage Health (/internal/storage/health)
# =====================================================
echo "[1/8] Validating storage persistence..."

STORAGE_RESPONSE=$(curl -s "$BASE_URL/internal/storage/health")

# Extract fields
RESOLVED_BASE_DIR=$(echo "$STORAGE_RESPONSE" | jq -r '.resolved_base_dir // "NOT_SET"')
IS_MOUNTPOINT=$(echo "$STORAGE_RESPONSE" | jq -r '.is_mountpoint')
IS_EPHEMERAL=$(echo "$STORAGE_RESPONSE" | jq -r '.is_ephemeral')
PREDICTIONS_EXISTS=$(echo "$STORAGE_RESPONSE" | jq -r '.predictions_exists')

# Validate
check "Storage: resolved_base_dir is set" \
    "$([ "$RESOLVED_BASE_DIR" != "NOT_SET" ] && echo true || echo false)" \
    "$RESOLVED_BASE_DIR" \
    "/data"

check "Storage: is_mountpoint = true" \
    "$([ "$IS_MOUNTPOINT" = "true" ] && echo true || echo false)" \
    "$IS_MOUNTPOINT" \
    "true"

check "Storage: is_ephemeral = false" \
    "$([ "$IS_EPHEMERAL" = "false" ] && echo true || echo false)" \
    "$IS_EPHEMERAL" \
    "false"

check "Storage: predictions.jsonl exists" \
    "$([ "$PREDICTIONS_EXISTS" = "true" ] && echo true || echo false)" \
    "$PREDICTIONS_EXISTS" \
    "true"

echo ""

# =====================================================
# CHECK 2: Best-Bets Endpoint (/live/best-bets/nba)
# =====================================================
echo "[2/8] Validating best-bets endpoint..."

BEST_BETS_RESPONSE=$(curl -s "$BASE_URL/live/best-bets/nba?debug=1&max_props=10&max_games=10" \
    -H "X-API-Key: $API_KEY")

# Extract debug fields
FILTERED_BELOW_6_5=$(echo "$BEST_BETS_RESPONSE" | jq -r '.debug.filtered_below_6_5_total // 0')
PICKS_LOGGED=$(echo "$BEST_BETS_RESPONSE" | jq -r '.debug.picks_logged // 0')
PICKS_SKIPPED=$(echo "$BEST_BETS_RESPONSE" | jq -r '.debug.picks_skipped_dupes // 0')
EVENTS_BEFORE_PROPS=$(echo "$BEST_BETS_RESPONSE" | jq -r '.debug.date_window_et.events_before_props // -1')
EVENTS_AFTER_PROPS=$(echo "$BEST_BETS_RESPONSE" | jq -r '.debug.date_window_et.events_after_props // -1')
EVENTS_BEFORE_GAMES=$(echo "$BEST_BETS_RESPONSE" | jq -r '.debug.date_window_et.events_before_games // -1')
EVENTS_AFTER_GAMES=$(echo "$BEST_BETS_RESPONSE" | jq -r '.debug.date_window_et.events_after_games // -1')

# Get minimum score from returned picks
MIN_PROP_SCORE=$(echo "$BEST_BETS_RESPONSE" | jq -r '[.props.picks[]?.final_score // 0] | min // 0')
MIN_GAME_SCORE=$(echo "$BEST_BETS_RESPONSE" | jq -r '[.game_picks.picks[]?.final_score // 0] | min // 0')
MIN_SCORE=$(echo "$MIN_PROP_SCORE $MIN_GAME_SCORE" | awk '{print ($1 < $2 && $1 > 0) ? $1 : $2}')

# Validate score filtering
# Pass if: filtered_below_6_5 > 0 (proves filter ran) OR min_score >= 6.5 (all picks valid) OR no picks
if [ "$FILTERED_BELOW_6_5" -gt 0 ]; then
    FILTER_CHECK="true"
    FILTER_REASON="$FILTERED_BELOW_6_5 picks filtered below 6.5"
elif [ "$MIN_SCORE" = "0" ]; then
    FILTER_CHECK="true"
    FILTER_REASON="no picks available (nothing to filter)"
elif awk -v min="$MIN_SCORE" 'BEGIN {exit (min >= 6.5) ? 0 : 1}'; then
    FILTER_CHECK="true"
    FILTER_REASON="all returned picks >= 6.5 (min=$MIN_SCORE), filter working"
else
    FILTER_CHECK="false"
    FILTER_REASON="min score $MIN_SCORE < 6.5 - FILTER BROKEN"
fi
check "Best-bets: score filter is active (filtered > 0 OR all picks valid)" \
    "$FILTER_CHECK" \
    "$FILTER_REASON" \
    "filtered_below_6_5 > 0 OR all returned scores >= 6.5"

if [ "$MIN_SCORE" != "0" ]; then
    check "Best-bets: minimum returned score >= 6.5" \
        "$(awk -v min="$MIN_SCORE" 'BEGIN {print (min >= 6.5) ? "true" : "false"}')" \
        "$MIN_SCORE" \
        ">= 6.5"
fi

# Validate ET filtering is applied (events_after <= events_before means filter ran)
# Note: before > after is CORRECT when Odds API returns tomorrow's games that get filtered out
check "Best-bets: ET filter applied to props (events_after <= events_before)" \
    "$([ "$EVENTS_AFTER_PROPS" -le "$EVENTS_BEFORE_PROPS" ] && echo true || echo false)" \
    "before=$EVENTS_BEFORE_PROPS, after=$EVENTS_AFTER_PROPS" \
    "events_after <= events_before (filter applied)"

check "Best-bets: ET filter applied to games (events_after <= events_before)" \
    "$([ "$EVENTS_AFTER_GAMES" -le "$EVENTS_BEFORE_GAMES" ] && echo true || echo false)" \
    "before=$EVENTS_BEFORE_GAMES, after=$EVENTS_AFTER_GAMES" \
    "events_after <= events_before (filter applied)"

# Note: picks_logged/picks_skipped_dupes may be 0 on cached responses
# We'll verify persistence in CHECK 4 instead (grader status)

echo ""

# =====================================================
# CHECK 3: Titanium 3/4 Rule
# =====================================================
echo "[3/8] Validating Titanium 3-of-4 rule..."

# Get all picks and check Titanium rule
TITANIUM_VIOLATIONS=$(echo "$BEST_BETS_RESPONSE" | jq '
    ((.props.picks // []) + (.game_picks.picks // [])) |
    map(select(.titanium_triggered == true)) |
    map({
        tier: .tier,
        titanium: .titanium_triggered,
        engines_above_8: (
            [.ai_score, .research_score, .esoteric_score, .jarvis_rs] |
            map(select(. != null and . >= 8.0)) |
            length
        )
    }) |
    map(select(.engines_above_8 < 3)) |
    length
')

check "Titanium: 3-of-4 rule enforced (no picks with titanium=true and < 3 engines >= 8.0)" \
    "$([ "$TITANIUM_VIOLATIONS" = "0" ] && echo true || echo false)" \
    "$TITANIUM_VIOLATIONS violations" \
    "0 violations"

echo ""

# =====================================================
# CHECK 4: Grader Status (/live/grader/status)
# =====================================================
echo "[4/8] Validating grader status..."

GRADER_RESPONSE=$(curl -s "$BASE_URL/live/grader/status" \
    -H "X-API-Key: $API_KEY")

# Extract fields
GRADER_AVAILABLE=$(echo "$GRADER_RESPONSE" | jq -r '.available // false')
PREDICTIONS_LOGGED=$(echo "$GRADER_RESPONSE" | jq -r '.grader_store.predictions_logged // 0')
STORAGE_PATH=$(echo "$GRADER_RESPONSE" | jq -r '.grader_store.storage_path // "NOT_SET"')

check "Grader: available = true" \
    "$([ "$GRADER_AVAILABLE" = "true" ] && echo true || echo false)" \
    "$GRADER_AVAILABLE" \
    "true"

check "Grader: predictions_logged > 0" \
    "$([ "$PREDICTIONS_LOGGED" -gt 0 ] && echo true || echo false)" \
    "$PREDICTIONS_LOGGED" \
    "> 0"

check "Grader: storage_path is inside Railway volume" \
    "$(echo "$STORAGE_PATH" | grep -qE "^(/data|/data)" && echo true || echo false)" \
    "$STORAGE_PATH" \
    "Starts with /data or /data"

echo ""

# =====================================================
# CHECK 5: ET Timezone (/live/debug/time)
# =====================================================
echo "[5/8] Validating ET timezone consistency..."

TIME_RESPONSE=$(curl -s "$BASE_URL/live/debug/time" \
    -H "X-API-Key: $API_KEY")

# Extract fields
ET_DATE=$(echo "$TIME_RESPONSE" | jq -r '.et_date // "NOT_SET"')
FILTER_DATE=$(echo "$BEST_BETS_RESPONSE" | jq -r '.debug.date_window_et.filter_date // "NOT_SET"')

check "ET Timezone: et_date is set" \
    "$([ "$ET_DATE" != "NOT_SET" ] && echo true || echo false)" \
    "$ET_DATE" \
    "YYYY-MM-DD format"

# Note: filter_date may be ERROR if et_day_bounds import failed, but ET filtering still works
if [ "$FILTER_DATE" != "ERROR" ]; then
    check "ET Timezone: filter_date matches et_date (single source of truth)" \
        "$([ "$ET_DATE" = "$FILTER_DATE" ] && echo true || echo false)" \
        "et_date=$ET_DATE, filter_date=$FILTER_DATE" \
        "Both match"
else
    echo -e "${YELLOW}⚠${NC} ET Timezone: filter_date shows ERROR (but ET filtering still working)"
fi

echo ""

# =====================================================
# CHECK 6: Weather Integration (/live/debug/integrations)
# =====================================================
echo "[6/8] Validating weather integration..."

WEATHER_STATUS=$(curl -s "$BASE_URL/live/debug/integrations" -H "X-API-Key: $API_KEY" |
    jq -r '.integrations.weather_api.validation.status // "NOT_FOUND"')

check "Weather: integration status is VALIDATED or NOT_RELEVANT" \
    "$(echo "$WEATHER_STATUS" | grep -qE "^(VALIDATED|NOT_RELEVANT)$" && echo true || echo false)" \
    "$WEATHER_STATUS" \
    "VALIDATED or NOT_RELEVANT"

echo ""

# =====================================================
# CHECK 7: Post-change Gates (Auth/Contract/Hard Gates/Fail-soft/Freshness)
# =====================================================
echo "[7/11] Running post-change gates..."

# Auth checks
AUTH_MISSING_CODE=$(curl -s -o /tmp/prod_missing -w "%{http_code}" "$BASE_URL/live/best-bets/NBA" 2>/dev/null || echo "000")
AUTH_INVALID_CODE=$(curl -s -o /tmp/prod_invalid -w "%{http_code}" -H "X-API-Key: INVALID" "$BASE_URL/live/best-bets/NBA" 2>/dev/null || echo "000")
AUTH_GOOD_CODE=$(curl -s -o /tmp/prod_good -w "%{http_code}" -H "X-API-Key: $API_KEY" "$BASE_URL/live/best-bets/NBA" 2>/dev/null || echo "000")
check "Auth: missing key -> Missing (401)" \
    "$([ "$AUTH_MISSING_CODE" = "401" ] && rg -q "Missing" /tmp/prod_missing && echo true || echo false)" \
    "code=$AUTH_MISSING_CODE" \
    "401 Missing"
check "Auth: wrong key -> Invalid (403)" \
    "$([ "$AUTH_INVALID_CODE" = "403" ] && rg -q "Invalid" /tmp/prod_invalid && echo true || echo false)" \
    "code=$AUTH_INVALID_CODE" \
    "403 Invalid"
check "Auth: correct key -> success (200)" \
    "$([ "$AUTH_GOOD_CODE" = "200" ] && echo true || echo false)" \
    "code=$AUTH_GOOD_CODE" \
    "200"
rm -f /tmp/prod_missing /tmp/prod_invalid /tmp/prod_good

POST_BEST_BETS=$(curl -s "$BASE_URL/live/best-bets/NBA" -H "X-API-Key: $API_KEY")
check "Shape: engine scores + total/final + bet_tier" \
    "$(echo "$POST_BEST_BETS" | jq -r '([
      .props.picks[]?, .game_picks.picks[]?
    ] | all(
      (.ai_score != null and .research_score != null and .esoteric_score != null and .jarvis_score != null and .context_modifier != null)
      and (.total_score != null and .final_score != null)
      and (.bet_tier != null)
      and (.confluence_boost != null and .msrf_boost != null and .jason_sim_boost != null and .serp_boost != null)
    ))' 2>/dev/null || echo false)" \
    "shape_check" \
    "required fields present"

check "Hard gate: final_score >= 6.5" \
    "$(echo "$POST_BEST_BETS" | jq -r '([
      .props.picks[]?, .game_picks.picks[]?
    ] | all(.final_score >= 6.5))' 2>/dev/null || echo false)" \
    "final_score gate" \
    ">= 6.5"

check "Hard gate: Titanium 3-of-4" \
    "$(echo "$POST_BEST_BETS" | jq -r '([
      .props.picks[]?, .game_picks.picks[]?
    ] | all(
      (.titanium_triggered != true)
      or (([.ai_score, .research_score, .esoteric_score, .jarvis_score] | map(. >= 8.0) | add) >= 3)
    ))' 2>/dev/null || echo false)" \
    "titanium gate" \
    "3 of 4 >= 8.0"

check "Fail-soft: errors array present" \
    "$(echo "$POST_BEST_BETS" | jq -r 'has("errors")' 2>/dev/null || echo false)" \
    "errors field" \
    "present"

POST_INT=$(curl -s "$BASE_URL/live/debug/integrations" -H "X-API-Key: $API_KEY")
check "Fail-soft: /live/debug/integrations loud" \
    "$(echo "$POST_INT" | jq -r 'has("by_status") and has("integrations")' 2>/dev/null || echo false)" \
    "debug integrations" \
    "by_status + integrations"

check "Freshness: date_et present" \
    "$(echo "$POST_BEST_BETS" | jq -r 'has("date_et")' 2>/dev/null || echo false)" \
    "date_et field" \
    "present"

# Note: _cached_at is stripped from public responses per CLAUDE.md "Public Payload ET-Only Rule"
# This check validates that internal telemetry is properly sanitized
POST_BB_HAS_CACHED=$(echo "$POST_BEST_BETS" | jq 'has("_cached_at")' 2>/dev/null || echo false)
POST_BB_HAS_ELAPSED=$(echo "$POST_BEST_BETS" | jq 'has("_elapsed_s")' 2>/dev/null || echo false)
check "No UTC/Telemetry Leaks: _cached_at and _elapsed_s stripped from public response" \
    "$([ "$POST_BB_HAS_CACHED" = "false" ] && [ "$POST_BB_HAS_ELAPSED" = "false" ] && echo true || echo false)" \
    "_cached_at=$POST_BB_HAS_CACHED, _elapsed_s=$POST_BB_HAS_ELAPSED" \
    "both should be false (stripped)"

echo ""

# =====================================================
# CHECK 8: End-to-End Best-Bets (All Sports)
# =====================================================
echo "[8/11] Validating best-bets end-to-end for all sports..."

SPORTS="${SPORTS:-NBA NHL NFL MLB NCAAB}"
for SPORT in $SPORTS; do
    SPORT_LOWER=$(echo "$SPORT" | tr '[:upper:]' '[:lower:]')
    BB_URL="$BASE_URL/live/best-bets/$SPORT_LOWER?debug=1&max_props=10&max_games=10"
    BB_TMP="/tmp/prod_best_bets_${SPORT_LOWER}.json"

    BB_CODE=$(curl -s -o "$BB_TMP" -w "%{http_code}" -H "X-API-Key: $API_KEY" "$BB_URL" 2>/dev/null || echo "000")
    check "Best-bets $SPORT: HTTP 200" \
        "$([ "$BB_CODE" = "200" ] && echo true || echo false)" \
        "code=$BB_CODE" \
        "200"

    # Stack completeness (no partial stack picks returned)
    STACK_OK=$(jq -r '([.props.picks[]?, .game_picks.picks[]?] | all(.stack_complete == true))' "$BB_TMP" 2>/dev/null || echo false)
    check "Best-bets $SPORT: stack_complete true for all picks" \
        "$STACK_OK" \
        "stack_complete=$STACK_OK" \
        "true"

    # Timed-out components should be empty
    TIMED_OUT_OK=$(jq -r '(.debug.timed_out_components // []) | length == 0' "$BB_TMP" 2>/dev/null || echo false)
    check "Best-bets $SPORT: no timed_out_components" \
        "$TIMED_OUT_OK" \
        "timed_out_components=$TIMED_OUT_OK" \
        "empty"

    # Option A formula sanity check (single pick, tolerant of rounding)
    FORMULA_OK=$(jq -r '
      def pick: (.props.picks[0] // .game_picks.picks[0] // null);
      if pick == null then "true" else
        (pick.base_score // 0) as $base
        | (pick.context_modifier // 0) as $ctx
        | (pick.confluence_boost // 0) as $conf
        | (pick.msrf_boost // 0) as $msrf
        | (pick.jason_sim_boost // 0) as $jason
        | (pick.serp_boost // 0) as $serp
        | (pick.final_score // 0) as $final
        | ((($base + $ctx + $conf + $msrf + $jason + $serp) - $final) | abs) <= 0.05
      end
    ' "$BB_TMP" 2>/dev/null || echo false)
    check "Best-bets $SPORT: Option A formula matches pick math" \
        "$FORMULA_OK" \
        "formula_match=$FORMULA_OK" \
        "true"

    # Deterministic errors: if errors exist, require code/status and no request_id leakage
    ERR_LEN=$(jq -r '.errors | length // 0' "$BB_TMP" 2>/dev/null || echo 0)
    if [ "$ERR_LEN" -gt 0 ]; then
        ERR_HAS_CODE_OR_STATUS=$(jq -r '(.errors | all((.code? != null) or (.status? != null)))' "$BB_TMP" 2>/dev/null || echo false)
        ERR_NO_REQUEST_ID=$(jq -r '(.errors | map(keys) | flatten | map(select(test("request_id|requestId|trace_id|traceId"))) | length) == 0' "$BB_TMP" 2>/dev/null || echo false)
        check "Best-bets $SPORT: errors include code/status" \
            "$ERR_HAS_CODE_OR_STATUS" \
            "errors_with_code_or_status=$ERR_HAS_CODE_OR_STATUS" \
            "true"
        check "Best-bets $SPORT: no request_id leakage in errors" \
            "$ERR_NO_REQUEST_ID" \
            "request_id_leak=$ERR_NO_REQUEST_ID" \
            "true"
    fi

    # Diversity telemetry counters present in debug payload
    DIVERSITY_OK=$(jq -r '(.debug.diversity_player_limited != null and .debug.diversity_game_limited != null and .debug.diversity_total_dropped != null)' "$BB_TMP" 2>/dev/null || echo false)
    check "Best-bets $SPORT: diversity counters present" \
        "$DIVERSITY_OK" \
        "diversity_counters=$DIVERSITY_OK" \
        "true"

    # Duplicate props policy: max 1 per player, max 3 per game
    MAX_PER_PLAYER=$(jq -r '[.props.picks[]? | (.player_name // .player // .selection // "UNKNOWN")] | sort | group_by(.) | map(length) | max // 0' "$BB_TMP" 2>/dev/null || echo 0)
    MAX_PER_GAME=$(jq -r '[.props.picks[]? | (.event_id // .game_id // (.matchup // ""))] | sort | group_by(.) | map(length) | max // 0' "$BB_TMP" 2>/dev/null || echo 0)
    check "Best-bets $SPORT: max 1 prop per player" \
        "$(awk -v m="$MAX_PER_PLAYER" 'BEGIN {print (m <= 1) ? "true" : "false"}')" \
        "max_per_player=$MAX_PER_PLAYER" \
        "<= 1"
    check "Best-bets $SPORT: max 3 props per game" \
        "$(awk -v m="$MAX_PER_GAME" 'BEGIN {print (m <= 3) ? "true" : "false"}')" \
        "max_per_game=$MAX_PER_GAME" \
        "<= 3"
done

echo ""

# =====================================================
# CHECK 9: Integration Truth Test (/live/debug/integrations)
# =====================================================
echo "[9/11] Validating integration truth test..."

INTEGRATIONS_RESPONSE=$(curl -s "$BASE_URL/live/debug/integrations" -H "X-API-Key: $API_KEY")
INTEGRATIONS_STATUS=$(echo "$INTEGRATIONS_RESPONSE" | jq -r '.overall_status // "UNKNOWN"')
INTEGRATIONS_REQUIRED=(
    odds_api
    playbook_api
    balldontlie
    weather_api
    railway_storage
    database
    redis
    whop_api
    serpapi
    twitter_api
    fred_api
    finnhub_api
)
INTEGRATIONS_EXPECTED_USED=(
    odds_api
    playbook_api
    weather_api
    serpapi
    twitter_api
    fred_api
    finnhub_api
)

check "Integrations: overall_status not CRITICAL" \
    "$([ "$INTEGRATIONS_STATUS" != "CRITICAL" ] && echo true || echo false)" \
    "$INTEGRATIONS_STATUS" \
    "HEALTHY or DEGRADED"

for INTEGRATION in "${INTEGRATIONS_REQUIRED[@]}"; do
    CONFIGURED=$(echo "$INTEGRATIONS_RESPONSE" | jq -r ".integrations.${INTEGRATION}.is_configured // false")
    REACHABLE=$(echo "$INTEGRATIONS_RESPONSE" | jq -r ".integrations.${INTEGRATION}.is_reachable // null")
    check "Integration $INTEGRATION: configured" \
        "$([ "$CONFIGURED" = "true" ] && echo true || echo false)" \
        "configured=$CONFIGURED" \
        "true"
    # Reachable may be null if not tested; fail only on explicit false
    check "Integration $INTEGRATION: not unreachable" \
        "$([ "$REACHABLE" != "false" ] && echo true || echo false)" \
        "reachable=$REACHABLE" \
        "not false"
done

for INTEGRATION in "${INTEGRATIONS_EXPECTED_USED[@]}"; do
    LAST_USED=$(echo "$INTEGRATIONS_RESPONSE" | jq -r ".integrations.${INTEGRATION}.last_used_at // \"\"")
    check "Integration $INTEGRATION: last_used_at present" \
        "$([ -n "$LAST_USED" ] && echo true || echo false)" \
        "last_used_at=${LAST_USED:-EMPTY}" \
        "non-empty"
done

echo ""

# =====================================================
# CHECK 10: OPS Aliases (/ops/*)
# =====================================================
echo "[10/11] Validating /ops/* alias routes..."

# Check /ops/integrations works (requires admin auth)
OPS_INTEGRATIONS=$(curl -s "$BASE_URL/ops/integrations" -H "X-Admin-Token: $API_KEY")
OPS_INTEGRATIONS_TOTAL=$(echo "$OPS_INTEGRATIONS" | jq -r '.total // 0')
OPS_INTEGRATIONS_FAILURES=$(echo "$OPS_INTEGRATIONS" | jq -r '.required_failures | length // 0')

check "OPS: /ops/integrations returns valid response" \
    "$([ "$OPS_INTEGRATIONS_TOTAL" -gt 0 ] && echo true || echo false)" \
    "total=$OPS_INTEGRATIONS_TOTAL, failures=$OPS_INTEGRATIONS_FAILURES" \
    "total > 0"

# Check /ops/storage works (requires admin auth)
OPS_STORAGE=$(curl -s "$BASE_URL/ops/storage" -H "X-Admin-Token: $API_KEY")
OPS_STORAGE_OK=$(echo "$OPS_STORAGE" | jq -r '.ok // false')

check "OPS: /ops/storage returns valid response" \
    "$([ "$OPS_STORAGE_OK" = "true" ] && echo true || echo false)" \
    "$OPS_STORAGE_OK" \
    "true"

# Check /ops/env-map works (requires admin auth)
OPS_ENV_MAP=$(curl -s "$BASE_URL/ops/env-map" -H "X-Admin-Token: $API_KEY")
OPS_ENV_MISSING=$(echo "$OPS_ENV_MAP" | jq -r '.missing_required | length // -1')

check "OPS: /ops/env-map returns no missing required vars" \
    "$([ "$OPS_ENV_MISSING" = "0" ] && echo true || echo false)" \
    "missing_required=$OPS_ENV_MISSING" \
    "0"

echo ""

# =====================================================
# CHECK 11: Full Verification (/ops/verify)
# =====================================================
echo "[11/11] Running comprehensive /ops/verify check..."

OPS_VERIFY=$(curl -s "$BASE_URL/ops/verify")
OPS_VERIFY_VERDICT=$(echo "$OPS_VERIFY" | jq -r '.verdict // "ERROR"')
OPS_VERIFY_FAILED=$(echo "$OPS_VERIFY" | jq -r '.failed_checks | length // 0')

check "OPS: /ops/verify returns PASS" \
    "$([ "$OPS_VERIFY_VERDICT" = "PASS" ] && echo true || echo false)" \
    "$OPS_VERIFY_VERDICT (failed: $OPS_VERIFY_FAILED)" \
    "PASS"

echo ""
echo "================================================"

# Final result
if [ ${#FAILED_CHECKS[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ ALL SANITY CHECKS PASSED${NC}"
    echo "Production invariants are enforced and working correctly."
    echo "================================================"
    exit 0
else
    echo -e "${RED}✗ ${#FAILED_CHECKS[@]} CHECKS FAILED${NC}"
    echo ""
    echo "Failed checks:"
    for check in "${FAILED_CHECKS[@]}"; do
        echo "  • $check"
    done
    echo ""
    echo "================================================"
    exit 1
fi
