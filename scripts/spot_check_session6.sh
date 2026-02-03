#!/bin/bash
# SESSION 6 SPOT CHECK: Gold Star + Jarvis Validation
# Validates Jarvis always returns required fields, Gold Star gates, and Jason Sim presence
# Exit 0 = all pass, Exit 1 = failures detected

# Don't exit on first error - we track failures manually
set +e

# Configuration
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"
TMP_FILE="/tmp/session6_picks.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0
PASSED=0

echo "=============================================="
echo "SESSION 6 SPOT CHECK: Gold Star + Jarvis"
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

# Fetch data once
echo -e "${YELLOW}Fetching NBA picks...${NC}"
curl -s "$BASE_URL/live/best-bets/nba?debug=1&max_props=100&max_games=50" \
    -H "X-API-Key: $API_KEY" > "$TMP_FILE"

PROPS_COUNT=$(jq '.props.count // 0' "$TMP_FILE")
GAMES_COUNT=$(jq '.game_picks.count // 0' "$TMP_FILE")
TOTAL_PICKS=$((PROPS_COUNT + GAMES_COUNT))
echo "Fetched: $PROPS_COUNT props, $GAMES_COUNT games (total: $TOTAL_PICKS)"
echo ""

# ============================================
# JARVIS REQUIRED FIELDS (INVARIANT 5)
# ============================================
echo -e "${YELLOW}[JARVIS REQUIRED FIELDS]${NC}"

# CHECK 1: jarvis_active field present on all picks
MISSING_JARVIS_ACTIVE=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.jarvis_active == null)) | length' "$TMP_FILE")
check "jarvis_active field present on all picks" \
    "$([ "$MISSING_JARVIS_ACTIVE" -eq 0 ] && echo true || echo false)" \
    "$MISSING_JARVIS_ACTIVE missing" \
    "0 missing"

# CHECK 2: jarvis_rs field present (can be null if inactive, but field must exist)
MISSING_JARVIS_RS=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(has("jarvis_rs") | not)) | length' "$TMP_FILE")
check "jarvis_rs field present on all picks" \
    "$([ "$MISSING_JARVIS_RS" -eq 0 ] && echo true || echo false)" \
    "$MISSING_JARVIS_RS missing" \
    "0 missing"

# CHECK 3: jarvis_reasons field present (even if empty array)
MISSING_JARVIS_REASONS=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.jarvis_reasons == null)) | length' "$TMP_FILE")
check "jarvis_reasons field present on all picks" \
    "$([ "$MISSING_JARVIS_REASONS" -eq 0 ] && echo true || echo false)" \
    "$MISSING_JARVIS_REASONS missing" \
    "0 missing"

# CHECK 4: When jarvis_active=true, jarvis_rs must be non-null
ACTIVE_BUT_NULL=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.jarvis_active == true and .jarvis_rs == null)) | length' "$TMP_FILE")
check "jarvis_active=true implies jarvis_rs is non-null" \
    "$([ "$ACTIVE_BUT_NULL" -eq 0 ] && echo true || echo false)" \
    "$ACTIVE_BUT_NULL violations" \
    "0 violations"

# CHECK 5: jarvis_triggers_hit field present
MISSING_TRIGGERS_HIT=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(has("jarvis_triggers_hit") | not)) | length' "$TMP_FILE")
check "jarvis_triggers_hit field present" \
    "$([ "$MISSING_TRIGGERS_HIT" -eq 0 ] && echo true || echo false)" \
    "$MISSING_TRIGGERS_HIT missing" \
    "0 missing"

# ============================================
# GOLD_STAR HARD GATES
# ============================================
echo ""
echo -e "${YELLOW}[GOLD_STAR HARD GATES]${NC}"

# CHECK 6: No GOLD_STAR with failed gates
# GOLD_STAR requires: ai>=6.8, research>=5.5, esoteric>=4.0, jarvis>=6.5
GOLD_STAR_WITH_FAILED_GATE=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(
    .tier == "GOLD_STAR" and (
        .ai_score < 6.8 or
        .research_score < 5.5 or
        .esoteric_score < 4.0 or
        (.jarvis_rs == null or .jarvis_rs < 6.5)
    )
)) | length' "$TMP_FILE")

check "No GOLD_STAR with failed engine gates" \
    "$([ "$GOLD_STAR_WITH_FAILED_GATE" -eq 0 ] && echo true || echo false)" \
    "$GOLD_STAR_WITH_FAILED_GATE violations" \
    "0 violations"

# CHECK 7: GOLD_STAR picks have final_score >= 7.5
GOLD_STAR_LOW_SCORE=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.tier == "GOLD_STAR" and .final_score < 7.5)) | length' "$TMP_FILE")
check "GOLD_STAR picks have final_score >= 7.5" \
    "$([ "$GOLD_STAR_LOW_SCORE" -eq 0 ] && echo true || echo false)" \
    "$GOLD_STAR_LOW_SCORE violations" \
    "0 violations"

# CHECK 8: Picks with final >= 7.5 + all gates pass = GOLD_STAR (not downgraded incorrectly)
# This checks that picks meeting all criteria ARE Gold Star
SHOULD_BE_GOLD=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(
    .final_score >= 7.5 and
    .tier != "GOLD_STAR" and
    .tier != "TITANIUM_SMASH" and
    .ai_score >= 6.8 and
    .research_score >= 5.5 and
    .esoteric_score >= 4.0 and
    .jarvis_rs != null and
    .jarvis_rs >= 6.5
)) | length' "$TMP_FILE")

check "Picks meeting all Gold Star criteria are GOLD_STAR tier" \
    "$([ "$SHOULD_BE_GOLD" -eq 0 ] && echo true || echo false)" \
    "$SHOULD_BE_GOLD incorrectly downgraded" \
    "0 incorrectly downgraded"

# ============================================
# JASON SIM 2.0 FIELDS
# ============================================
echo ""
echo -e "${YELLOW}[JASON SIM 2.0 FIELDS]${NC}"

# CHECK 9: jason_sim_boost field present (can be 0)
MISSING_JASON_BOOST=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(has("jason_sim_boost") | not)) | length' "$TMP_FILE")
check "jason_sim_boost field present on all picks" \
    "$([ "$MISSING_JASON_BOOST" -eq 0 ] && echo true || echo false)" \
    "$MISSING_JASON_BOOST missing" \
    "0 missing"

# CHECK 10: jason_ran field present (shows Jason Sim executed)
MISSING_JASON_RAN=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(has("jason_ran") | not)) | length' "$TMP_FILE")
check "jason_ran field present" \
    "$([ "$MISSING_JASON_RAN" -eq 0 ] && echo true || echo false)" \
    "$MISSING_JASON_RAN missing" \
    "0 missing"

# ============================================
# CONFLUENCE FIELDS
# ============================================
echo ""
echo -e "${YELLOW}[CONFLUENCE FIELDS]${NC}"

# CHECK 11: confluence_level field present
MISSING_CONFLUENCE_LEVEL=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.confluence_level == null)) | length' "$TMP_FILE")
check "confluence_level field present" \
    "$([ "$MISSING_CONFLUENCE_LEVEL" -eq 0 ] && echo true || echo false)" \
    "$MISSING_CONFLUENCE_LEVEL missing" \
    "0 missing"

# CHECK 12: confluence_reasons field present (even if empty)
MISSING_CONF_REASONS=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.confluence_reasons == null)) | length' "$TMP_FILE")
check "confluence_reasons field present" \
    "$([ "$MISSING_CONF_REASONS" -eq 0 ] && echo true || echo false)" \
    "$MISSING_CONF_REASONS missing" \
    "0 missing"

# ============================================
# JARVIS v16.0 ADDITIVE SCORING
# ============================================
echo ""
echo -e "${YELLOW}[JARVIS v16.0 ADDITIVE SCORING]${NC}"

# CHECK 13: jarvis_baseline field present when jarvis_active=true
MISSING_BASELINE=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.jarvis_active == true and .jarvis_baseline == null)) | length' "$TMP_FILE")
check "jarvis_baseline present when active" \
    "$([ "$MISSING_BASELINE" -eq 0 ] && echo true || echo false)" \
    "$MISSING_BASELINE missing" \
    "0 missing"

# CHECK 14: jarvis_rs >= 4.5 when jarvis_active=true (baseline minimum)
LOW_JARVIS=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.jarvis_active == true and .jarvis_rs != null and .jarvis_rs < 4.5)) | length' "$TMP_FILE")
check "jarvis_rs >= 4.5 baseline when active" \
    "$([ "$LOW_JARVIS" -eq 0 ] && echo true || echo false)" \
    "$LOW_JARVIS below baseline" \
    "0 below baseline"

# ============================================
# INFO: TIER DISTRIBUTION
# ============================================
echo ""
echo -e "${YELLOW}[INFO] Tier Distribution${NC}"
GOLD_COUNT=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.tier == "GOLD_STAR")) | length' "$TMP_FILE")
TITANIUM_COUNT=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.tier == "TITANIUM_SMASH")) | length' "$TMP_FILE")
EDGE_COUNT=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.tier == "EDGE_LEAN")) | length' "$TMP_FILE")

echo "  TITANIUM_SMASH: $TITANIUM_COUNT / $TOTAL_PICKS"
echo "  GOLD_STAR: $GOLD_COUNT / $TOTAL_PICKS"
echo "  EDGE_LEAN: $EDGE_COUNT / $TOTAL_PICKS"

# Show sample GOLD_STAR picks if any
if [ "$GOLD_COUNT" -gt 0 ]; then
    echo ""
    echo "Sample GOLD_STAR picks (up to 5):"
    jq -r '[.props.picks[], .game_picks.picks[]] | map(select(.tier == "GOLD_STAR")) | .[0:5] | .[] | "  \(.player_name // .player // "GAME"): final=\(.final_score) | ai=\(.ai_score) res=\(.research_score) eso=\(.esoteric_score) jar=\(.jarvis_rs)"' "$TMP_FILE"
fi

# Show top Jarvis picks
echo ""
echo "Top 5 picks by jarvis_rs:"
jq -r '[.props.picks[], .game_picks.picks[]] | sort_by(-.jarvis_rs) | .[0:5] | .[] | "  jar=\(.jarvis_rs // 0) | \(.player_name // .player // "GAME") | triggers=\(.jarvis_triggers_hit // [] | length)"' "$TMP_FILE"

# Summary
echo ""
echo "=============================================="
TOTAL=$((PASSED + FAILED))
echo "SESSION 6 RESULTS: $PASSED/$TOTAL checks passed"

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}SESSION 6 SPOT CHECK: FAILED${NC}"
    echo "=============================================="
    exit 1
else
    echo -e "${GREEN}SESSION 6 SPOT CHECK: ALL PASS${NC}"
    echo "=============================================="
    exit 0
fi
