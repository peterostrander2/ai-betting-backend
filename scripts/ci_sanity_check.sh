#!/bin/bash
# CI Sanity Check Script - Hard Gate Validation
# Fails non-zero if ANY invariant is broken
# Run before deploy or as part of CI/CD pipeline

# Don't exit on first error - we want to run all checks
set +e

# Configuration
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED=0
PASSED=0

echo "================================================"
echo "CI SANITY CHECK - Backend Invariant Validation"
echo "================================================"
echo "Base URL: $BASE_URL"
echo "Date: $(date)"
echo ""

# Helper function
check() {
    local name="$1"
    local condition="$2"
    local actual="$3"
    local expected="$4"

    if [ "$condition" = "true" ]; then
        echo -e "${GREEN}✓${NC} $name"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} $name"
        echo "  Expected: $expected"
        echo "  Actual: $actual"
        ((FAILED++))
    fi
}

# ============================================
# SESSION 1: ET Window Correctness
# ============================================
echo ""
echo -e "${YELLOW}[SESSION 1] ET Window Correctness${NC}"

ET_DATA=$(curl -s "$BASE_URL/live/best-bets/nba?debug=1&max_games=50&max_props=50" \
    -H "X-API-Key: $API_KEY" | jq -r '.debug.date_window_et')

START_ET=$(echo "$ET_DATA" | jq -r '.start_et // empty')
END_ET=$(echo "$ET_DATA" | jq -r '.end_et // empty')
GAMES_AFTER=$(echo "$ET_DATA" | jq -r '.events_after_games // 0')
PROPS_AFTER=$(echo "$ET_DATA" | jq -r '.events_after_props // 0')

# Check start_et contains 00:01:00
check "ET window starts at 00:01:00" \
    "$(echo "$START_ET" | grep -q 'T00:01:00' && echo true || echo false)" \
    "$START_ET" \
    "*T00:01:00*"

# Check end_et is next day 00:00:00
check "ET window ends at next day 00:00:00" \
    "$(echo "$END_ET" | grep -q 'T00:00:00' && echo true || echo false)" \
    "$END_ET" \
    "*T00:00:00*"

# ============================================
# SESSION 2: Research Engine (No Double Counting)
# ============================================
echo ""
echo -e "${YELLOW}[SESSION 2] Research Engine Signals${NC}"

RESEARCH_DATA=$(curl -s "$BASE_URL/live/best-bets/nba?debug=1&max_props=3" \
    -H "X-API-Key: $API_KEY" | jq -r '.props.picks[0].research_reasons // []')

# Check research_reasons exists and has content
HAS_RESEARCH=$(echo "$RESEARCH_DATA" | jq -r 'length > 0')
check "Research reasons populated" \
    "$HAS_RESEARCH" \
    "$(echo "$RESEARCH_DATA" | jq -r 'length')" \
    "> 0"

# ============================================
# SESSION 3: Filtering + Tiers
# ============================================
echo ""
echo -e "${YELLOW}[SESSION 3] Filtering + Tier Assignment${NC}"

FILTER_DATA=$(curl -s "$BASE_URL/live/best-bets/nba?debug=1" \
    -H "X-API-Key: $API_KEY")

FILTERED_BELOW=$(echo "$FILTER_DATA" | jq -r '.debug.filtered_below_6_5_total // 0')
MIN_SCORE=$(echo "$FILTER_DATA" | jq -r '[.props.picks[].final_score, .game_picks.picks[].final_score] | min // 10')

check "Picks filtered below 6.5" \
    "$([ "$FILTERED_BELOW" -gt 0 ] && echo true || echo false)" \
    "$FILTERED_BELOW" \
    "> 0"

check "Minimum returned score >= 6.5" \
    "$(awk "BEGIN {exit !($MIN_SCORE >= 6.5)}" && echo true || echo false)" \
    "$MIN_SCORE" \
    ">= 6.5"

# Titanium check: no pick with titanium=true and <3 engines >= 8.0
TITANIUM_VIOLATION=$(echo "$FILTER_DATA" | jq -r '
    [.props.picks[], .game_picks.picks[]] |
    map(select(.titanium_triggered == true)) |
    map(select(([.ai_score, .research_score, .esoteric_score, .jarvis_rs] | map(select(. >= 8.0)) | length) < 3)) |
    length
')

check "Titanium 3-of-4 rule enforced" \
    "$([ "$TITANIUM_VIOLATION" -eq 0 ] && echo true || echo false)" \
    "$TITANIUM_VIOLATION violations" \
    "0 violations"

# ============================================
# SESSION 4: Context Modifiers
# ============================================
echo ""
echo -e "${YELLOW}[SESSION 4] Context Modifiers${NC}"

# Check NBA (indoor) - should be NOT_RELEVANT
NBA_WEATHER=$(curl -s "$BASE_URL/live/best-bets/nba?debug=1&max_props=1" \
    -H "X-API-Key: $API_KEY" | jq -r '.props.picks[0].weather_context.status // "MISSING"')

check "NBA weather is NOT_RELEVANT (indoor)" \
    "$([ "$NBA_WEATHER" = "NOT_RELEVANT" ] && echo true || echo false)" \
    "$NBA_WEATHER" \
    "NOT_RELEVANT"

# Check NFL (outdoor) - should be VALIDATED or NOT_RELEVANT (dome), NOT "UNAVAILABLE" due to sync
NFL_WEATHER=$(curl -s "$BASE_URL/live/best-bets/nfl?debug=1&max_games=1" \
    -H "X-API-Key: $API_KEY" | jq -r '.game_picks.picks[0].weather_context.status // "MISSING"')

NFL_REASON=$(curl -s "$BASE_URL/live/best-bets/nfl?debug=1&max_games=1" \
    -H "X-API-Key: $API_KEY" | jq -r '.game_picks.picks[0].weather_context.reason // ""')

# NFL should NOT be UNAVAILABLE with "sync cache only" reason
SYNC_CACHE_BUG=$(echo "$NFL_REASON" | grep -qi "sync\|cache only" && echo true || echo false)

check "NFL weather uses async fetch (not sync cache-only)" \
    "$([ "$SYNC_CACHE_BUG" = "false" ] && echo true || echo false)" \
    "$NFL_WEATHER: $NFL_REASON" \
    "VALIDATED or NOT_RELEVANT (not sync cache bug)"

# ============================================
# SESSION 5: Persistence
# ============================================
echo ""
echo -e "${YELLOW}[SESSION 5] Persistence & Grading${NC}"

STORAGE_HEALTH=$(curl -s "$BASE_URL/internal/storage/health" \
    -H "X-API-Key: $API_KEY")

# Note: jq's // operator treats false as falsy, so we use explicit type checks
IS_MOUNT=$(echo "$STORAGE_HEALTH" | jq -r 'if .is_mountpoint == true then "true" else "false" end')
IS_EPHEMERAL=$(echo "$STORAGE_HEALTH" | jq -r 'if .is_ephemeral == true then "true" else "false" end')
PRED_COUNT=$(echo "$STORAGE_HEALTH" | jq -r '.predictions_line_count // 0')

check "Storage is mounted volume" \
    "$IS_MOUNT" \
    "$IS_MOUNT" \
    "true"

check "Storage is NOT ephemeral" \
    "$([ "$IS_EPHEMERAL" != "true" ] && echo true || echo false)" \
    "$IS_EPHEMERAL" \
    "not true"

check "Predictions exist on volume" \
    "$([ "$PRED_COUNT" -gt 0 ] && echo true || echo false)" \
    "$PRED_COUNT predictions" \
    "> 0"

# ============================================
# SESSION 6: Integrations
# ============================================
echo ""
echo -e "${YELLOW}[SESSION 6] Integration Connectivity${NC}"

INTEGRATIONS=$(curl -s "$BASE_URL/live/debug/integrations" \
    -H "X-API-Key: $API_KEY")

# Check critical integrations are VALIDATED
for INT in odds_api playbook_api balldontlie weather_api railway_storage; do
    STATUS=$(echo "$INTEGRATIONS" | jq -r ".integrations.$INT.status_category // \"NOT_FOUND\"")
    check "$INT is VALIDATED" \
        "$([ "$STATUS" = "VALIDATED" ] && echo true || echo false)" \
        "$STATUS" \
        "VALIDATED"
done

# ============================================
# SUMMARY
# ============================================
echo ""
echo "================================================"
TOTAL=$((PASSED + FAILED))
echo "RESULTS: $PASSED/$TOTAL checks passed"

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}FAILED: $FAILED invariants broken${NC}"
    echo "================================================"
    exit 1
else
    echo -e "${GREEN}ALL CHECKS PASSED${NC}"
    echo "================================================"
    exit 0
fi
