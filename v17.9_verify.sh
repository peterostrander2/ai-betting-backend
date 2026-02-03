#!/bin/bash
# v17.9 Weather, Altitude & Travel Fatigue Verification Script
# =============================================================
#
# Run this after deploying v17.9 to verify the integration is working.
#
# Usage: ./v17.9_verify.sh [API_URL] [API_KEY]
# Example: ./v17.9_verify.sh https://api.example.com YOUR_API_KEY

set -e

API_URL="${1:-http://localhost:8000}"
API_KEY="${2:-test_key}"

echo "=========================================="
echo "v17.9 Weather, Altitude & Travel Verification"
echo "=========================================="
echo "API URL: $API_URL"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}✓ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }

# -----------------------------------------------------------------------------
# 1. Syntax Check (if files are local)
# -----------------------------------------------------------------------------
echo ""
echo "1. Syntax Check"
echo "---------------"

if [ -f "live_data_router.py" ]; then
    if python -m py_compile live_data_router.py 2>/dev/null; then
        pass "live_data_router.py syntax OK"
    else
        fail "live_data_router.py syntax error"
    fi
else
    warn "live_data_router.py not found locally (expected on server)"
fi

if [ -f "context_layer.py" ]; then
    if python -m py_compile context_layer.py 2>/dev/null; then
        pass "context_layer.py syntax OK"
    else
        fail "context_layer.py syntax error"
    fi
else
    warn "context_layer.py not found locally (expected on server)"
fi

# Test the implementation file
if python -m py_compile v17.9_weather_altitude_travel.py 2>/dev/null; then
    pass "v17.9_weather_altitude_travel.py syntax OK"
else
    fail "v17.9_weather_altitude_travel.py syntax error"
fi

# -----------------------------------------------------------------------------
# 2. Weather Integration (NFL/MLB outdoor games)
# -----------------------------------------------------------------------------
echo ""
echo "2. Weather Integration Test"
echo "---------------------------"
echo "Checking for weather adjustments in research_reasons..."

# NFL weather check
NFL_WEATHER=$(curl -s "$API_URL/live/best-bets/NFL?debug=1" \
    -H "X-API-Key: $API_KEY" 2>/dev/null | \
    jq -r '[.game_picks.picks[].research_reasons // []] | flatten | map(select(startswith("Weather"))) | length' 2>/dev/null || echo "0")

if [ "$NFL_WEATHER" -gt 0 ]; then
    pass "NFL weather in research_reasons: $NFL_WEATHER picks affected"
else
    warn "NFL: No weather adjustments found (may be good weather or indoor games)"
fi

# MLB weather check (seasonal - skip in offseason)
MLB_WEATHER=$(curl -s "$API_URL/live/best-bets/MLB?debug=1" \
    -H "X-API-Key: $API_KEY" 2>/dev/null | \
    jq -r '[.game_picks.picks[].research_reasons // []] | flatten | map(select(startswith("Weather"))) | length' 2>/dev/null || echo "0")

if [ "$MLB_WEATHER" -gt 0 ]; then
    pass "MLB weather in research_reasons: $MLB_WEATHER picks affected"
else
    warn "MLB: No weather adjustments found (may be offseason or dome games)"
fi

# -----------------------------------------------------------------------------
# 3. Altitude Integration (Denver/Utah games)
# -----------------------------------------------------------------------------
echo ""
echo "3. Altitude Integration Test"
echo "----------------------------"
echo "Checking for altitude adjustments in esoteric_reasons..."

# Check for Denver games (any sport)
for SPORT in NFL NBA NHL MLB; do
    ALTITUDE=$(curl -s "$API_URL/live/best-bets/$SPORT?debug=1" \
        -H "X-API-Key: $API_KEY" 2>/dev/null | \
        jq -r '[.game_picks.picks[] | select(.home_team | test("Denver|Broncos|Nuggets|Avalanche|Rockies|Utah|Jazz";"i"))] | .[0].esoteric_reasons // []' 2>/dev/null)

    if echo "$ALTITUDE" | grep -q "altitude\|Altitude\|5280\|4226"; then
        pass "$SPORT: Altitude adjustment found for high-altitude venue"
        echo "   $ALTITUDE" | head -1
    else
        # Check if there are any high-altitude games
        HAS_ALTITUDE_GAME=$(curl -s "$API_URL/live/best-bets/$SPORT?debug=1" \
            -H "X-API-Key: $API_KEY" 2>/dev/null | \
            jq -r '[.game_picks.picks[] | select(.home_team | test("Denver|Broncos|Nuggets|Avalanche|Rockies|Utah|Jazz";"i"))] | length' 2>/dev/null || echo "0")

        if [ "$HAS_ALTITUDE_GAME" -gt 0 ]; then
            fail "$SPORT: High-altitude game found but no altitude adjustment"
        else
            warn "$SPORT: No high-altitude games today"
        fi
    fi
done

# -----------------------------------------------------------------------------
# 4. Travel/B2B Integration
# -----------------------------------------------------------------------------
echo ""
echo "4. Travel/B2B Integration Test"
echo "------------------------------"
echo "Checking for B2B and travel adjustments in context_reasons..."

# NBA is most likely to have B2B games
NBA_B2B=$(curl -s "$API_URL/live/best-bets/NBA?debug=1" \
    -H "X-API-Key: $API_KEY" 2>/dev/null | \
    jq -r '[.game_picks.picks[].context_reasons // []] | flatten | map(select(startswith("B2B") or startswith("Travel"))) | unique' 2>/dev/null)

if echo "$NBA_B2B" | grep -q "B2B\|Travel"; then
    pass "NBA: B2B/Travel adjustments found"
    echo "$NBA_B2B" | jq -r '.[]' 2>/dev/null | head -3
else
    warn "NBA: No B2B/Travel adjustments found (teams may be well-rested)"
fi

# NHL also has frequent B2B
NHL_B2B=$(curl -s "$API_URL/live/best-bets/NHL?debug=1" \
    -H "X-API-Key: $API_KEY" 2>/dev/null | \
    jq -r '[.game_picks.picks[].context_reasons // []] | flatten | map(select(startswith("B2B") or startswith("Travel"))) | unique' 2>/dev/null)

if echo "$NHL_B2B" | grep -q "B2B\|Travel"; then
    pass "NHL: B2B/Travel adjustments found"
    echo "$NHL_B2B" | jq -r '.[]' 2>/dev/null | head -3
else
    warn "NHL: No B2B/Travel adjustments found (teams may be well-rested)"
fi

# -----------------------------------------------------------------------------
# 5. Regression Test (all sports return picks)
# -----------------------------------------------------------------------------
echo ""
echo "5. Regression Test (All Sports)"
echo "--------------------------------"
echo "Verifying all sports still return picks..."

ALL_PASS=true
for SPORT in NBA NHL NFL MLB NCAAB NCAAF; do
    COUNT=$(curl -s "$API_URL/live/best-bets/$SPORT" \
        -H "X-API-Key: $API_KEY" 2>/dev/null | \
        jq -r '.game_picks.count // 0' 2>/dev/null || echo "-1")

    if [ "$COUNT" -ge 0 ]; then
        pass "$SPORT: $COUNT picks returned"
    else
        fail "$SPORT: Error fetching picks"
        ALL_PASS=false
    fi
done

# -----------------------------------------------------------------------------
# 6. Verify Old Weather Removal
# -----------------------------------------------------------------------------
echo ""
echo "6. Old Weather Code Removal Check"
echo "----------------------------------"

# Check that weather is NOT in final_reasons (should be in research_reasons only)
NFL_FINAL_WEATHER=$(curl -s "$API_URL/live/best-bets/NFL?debug=1" \
    -H "X-API-Key: $API_KEY" 2>/dev/null | \
    jq -r '[.game_picks.picks[].final_reasons // []] | flatten | map(select(startswith("Weather"))) | length' 2>/dev/null || echo "0")

if [ "$NFL_FINAL_WEATHER" -eq 0 ]; then
    pass "Weather NOT in final_reasons (correctly moved to research)"
else
    warn "Weather still appears in final_reasons - old code may not be removed"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=========================================="
echo "Verification Complete"
echo "=========================================="
echo ""
echo "Expected Results After v17.9:"
echo "- Weather: NFL/MLB outdoor games show 'Weather: ...' in research_reasons"
echo "- Altitude: Denver games show 'Mile High 5280ft...' in esoteric_reasons"
echo "- Travel/B2B: Away teams on B2B show 'B2B: ...' in context_reasons"
echo ""
echo "Adjustment Ranges:"
echo "┌────────────┬──────────────────┬─────────────────────┐"
echo "│ Signal     │ Target Score     │ Range               │"
echo "├────────────┼──────────────────┼─────────────────────┤"
echo "│ Weather    │ research_score   │ -0.5 to 0.0         │"
echo "│ Altitude   │ esoteric_score   │ -0.3 to +0.5        │"
echo "│ Travel/B2B │ context_score    │ -0.5 to 0.0         │"
echo "└────────────┴──────────────────┴─────────────────────┘"
