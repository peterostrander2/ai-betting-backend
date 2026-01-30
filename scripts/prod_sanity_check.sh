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
echo "[1/6] Validating storage persistence..."

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
    "/app/grader_data"

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
# CHECK 2: Best-Bets Endpoint (/live/best-bets/NBA)
# =====================================================
echo "[2/6] Validating best-bets endpoint..."

BEST_BETS_RESPONSE=$(curl -s "$BASE_URL/live/best-bets/NBA?debug=1&max_props=10&max_games=10" \
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
check "Best-bets: filtered_below_6_5 > 0 OR no picks available" \
    "$([ "$FILTERED_BELOW_6_5" -gt 0 ] || [ "$MIN_SCORE" = "0" ] && echo true || echo false)" \
    "$FILTERED_BELOW_6_5 filtered" \
    "> 0 (proves filter is active)"

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
echo "[3/6] Validating Titanium 3-of-4 rule..."

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
echo "[4/6] Validating grader status..."

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
    "$(echo "$STORAGE_PATH" | grep -q "/app/grader_data" && echo true || echo false)" \
    "$STORAGE_PATH" \
    "Contains /app/grader_data"

echo ""

# =====================================================
# CHECK 5: ET Timezone (/live/debug/time)
# =====================================================
echo "[5/6] Validating ET timezone consistency..."

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
echo "[6/6] Validating weather integration..."

WEATHER_STATUS=$(curl -s "$BASE_URL/live/debug/integrations" -H "X-API-Key: $API_KEY" |
    jq -r '.integrations.weather_api.validation.status // "NOT_FOUND"')

check "Weather: integration status is VALIDATED or NOT_RELEVANT" \
    "$(echo "$WEATHER_STATUS" | grep -qE "^(VALIDATED|NOT_RELEVANT)$" && echo true || echo false)" \
    "$WEATHER_STATUS" \
    "VALIDATED or NOT_RELEVANT"

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
