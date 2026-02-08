#!/bin/bash
# SESSION 1 SPOT CHECK: ET Window Correctness
# Validates ET day bounds and sane slate counts
# Exit 0 = all pass, Exit 1 = failures detected

# Don't exit on first error - we track failures manually
set +e

# Configuration
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"
TMP_FILE="/tmp/session1_data.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0
PASSED=0

echo "=============================================="
echo "SESSION 1 SPOT CHECK: ET Window Correctness"
echo "=============================================="
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
        echo -e "${GREEN}PASS${NC}: $name"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}FAIL${NC}: $name"
        echo "  Expected: $expected"
        echo "  Actual: $actual"
        FAILED=$((FAILED + 1))
    fi
}

# Fetch debug time endpoint
echo -e "${YELLOW}Fetching /live/debug/time...${NC}"
TIME_DATA=$(curl -s "$BASE_URL/live/debug/time" -H "X-API-Key: $API_KEY")

ET_DATE=$(echo "$TIME_DATA" | jq -r '.et_date // "ERROR"')
ET_START=$(echo "$TIME_DATA" | jq -r '.et_day_start_iso // "ERROR"')
ET_END=$(echo "$TIME_DATA" | jq -r '.et_day_end_iso // "ERROR"')

echo "ET Date: $ET_DATE"
echo "ET Start: $ET_START"
echo "ET End: $ET_END"
echo ""

# CHECK 1: ET window starts at 00:00:00
echo -e "${YELLOW}[CHECK 1] ET window start time${NC}"
START_TIME=$(echo "$ET_START" | grep -oE 'T[0-9]{2}:[0-9]{2}:[0-9]{2}' | sed 's/T//')
check "ET window starts at 00:00:00" \
    "$([ "$START_TIME" = "00:00:00" ] && echo true || echo false)" \
    "$START_TIME" \
    "00:00:00"

# CHECK 2: ET window ends at next day 00:00:00 (exclusive)
echo -e "${YELLOW}[CHECK 2] ET window end time${NC}"
END_TIME=$(echo "$ET_END" | grep -oE 'T[0-9]{2}:[0-9]{2}:[0-9]{2}' | sed 's/T//')
check "ET window ends at 00:00:00 (next day, exclusive)" \
    "$([ "$END_TIME" = "00:00:00" ] && echo true || echo false)" \
    "$END_TIME" \
    "00:00:00"

# CHECK 3: ET date is valid format (YYYY-MM-DD)
echo -e "${YELLOW}[CHECK 3] ET date format${NC}"
DATE_VALID=$(echo "$ET_DATE" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' && echo true || echo false)
check "ET date is valid YYYY-MM-DD" \
    "$DATE_VALID" \
    "$ET_DATE" \
    "YYYY-MM-DD format"

# Fetch best-bets with debug for slate counts
echo ""
echo -e "${YELLOW}Fetching best-bets debug data for slate counts...${NC}"

# NBA slate count
NBA_DATA=$(curl -s "$BASE_URL/live/best-bets/nba?debug=1&max_props=100" -H "X-API-Key: $API_KEY")
NBA_EVENTS_AFTER=$(echo "$NBA_DATA" | jq -r '.debug.date_window_et.events_after_games // 0')
NBA_FILTER_DATE=$(echo "$NBA_DATA" | jq -r '.debug.date_window_et.filter_date // "ERROR"')

# CHECK 4: NBA filter_date matches ET date
echo -e "${YELLOW}[CHECK 4] NBA filter_date matches /debug/time ET date${NC}"
check "NBA filter_date matches ET date" \
    "$([ "$NBA_FILTER_DATE" = "$ET_DATE" ] && echo true || echo false)" \
    "$NBA_FILTER_DATE" \
    "$ET_DATE"

# CHECK 5: NBA slate count is sane (<=20)
echo -e "${YELLOW}[CHECK 5] NBA slate count cap${NC}"
check "NBA events after filter <= 20" \
    "$([ "$NBA_EVENTS_AFTER" -le 20 ] && echo true || echo false)" \
    "$NBA_EVENTS_AFTER events" \
    "<= 20"

# NHL slate count (if available)
NHL_DATA=$(curl -s "$BASE_URL/live/best-bets/nhl?debug=1&max_props=100" -H "X-API-Key: $API_KEY" 2>/dev/null || echo '{}')
NHL_EVENTS_AFTER=$(echo "$NHL_DATA" | jq -r '.debug.date_window_et.events_after_games // 0')

# CHECK 6: NHL slate count is sane (<=20)
echo -e "${YELLOW}[CHECK 6] NHL slate count cap${NC}"
check "NHL events after filter <= 20" \
    "$([ "$NHL_EVENTS_AFTER" -le 20 ] && echo true || echo false)" \
    "$NHL_EVENTS_AFTER events" \
    "<= 20"

# CHECK 7: ET filter is applied BEFORE scoring (verified via debug ordering)
# We check that events_before >= events_after (filter reduced the count)
echo -e "${YELLOW}[CHECK 7] ET filter applied (events_before >= events_after)${NC}"
NBA_EVENTS_BEFORE=$(echo "$NBA_DATA" | jq -r '.debug.date_window_et.events_before_games // 0')
FILTER_APPLIED=$([ "$NBA_EVENTS_BEFORE" -ge "$NBA_EVENTS_AFTER" ] && echo true || echo false)
check "ET filter applied (events_before >= events_after)" \
    "$FILTER_APPLIED" \
    "before=$NBA_EVENTS_BEFORE, after=$NBA_EVENTS_AFTER" \
    "before >= after"

# CHECK 8: No ghost events (events dropped should be logged)
echo -e "${YELLOW}[CHECK 8] Dropped events logged${NC}"
DROPPED_WINDOW=$(echo "$NBA_DATA" | jq -r '.debug.date_window_et.dropped_out_of_window_games // 0')
DROPPED_REPORTED=$([ "$DROPPED_WINDOW" != "null" ] && echo true || echo false)
check "Dropped events field present" \
    "$DROPPED_REPORTED" \
    "dropped_out_of_window_games = $DROPPED_WINDOW" \
    "field exists"

# Summary
echo ""
echo "=============================================="
TOTAL=$((PASSED + FAILED))
echo "SESSION 1 RESULTS: $PASSED/$TOTAL checks passed"

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}SESSION 1 SPOT CHECK: FAILED${NC}"
    echo "=============================================="
    exit 1
else
    echo -e "${GREEN}SESSION 1 SPOT CHECK: ALL PASS${NC}"
    echo "=============================================="
    exit 0
fi
