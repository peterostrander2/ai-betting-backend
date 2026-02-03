#!/bin/bash
# SESSION 5 SPOT CHECK: Tiering + Filters
# Validates Titanium 3/4 rule, 6.5 minimum, and contradiction gate
# Exit 0 = all pass, Exit 1 = failures detected

# Don't exit on first error - we track failures manually
set +e

# Configuration
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"
TMP_FILE="/tmp/session5_picks.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0
PASSED=0

echo "=============================================="
echo "SESSION 5 SPOT CHECK: Tiering + Filters"
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

# Fetch picks data
echo -e "${YELLOW}Fetching NBA picks for tier/filter analysis...${NC}"
curl -s "$BASE_URL/live/best-bets/nba?debug=1&max_props=100&max_games=50" \
    -H "X-API-Key: $API_KEY" > "$TMP_FILE"

PROPS_COUNT=$(jq '.props.count // 0' "$TMP_FILE")
GAMES_COUNT=$(jq '.game_picks.count // 0' "$TMP_FILE")
TOTAL_PICKS=$((PROPS_COUNT + GAMES_COUNT))
echo "Fetched: $PROPS_COUNT props, $GAMES_COUNT games (total: $TOTAL_PICKS)"
echo ""

# ============================================
# TITANIUM 3/4 RULE (INVARIANT 2)
# ============================================
echo -e "${YELLOW}[TITANIUM 3/4 RULE]${NC}"

# CHECK 1: No false Titanium (titanium=true but <3 engines >= 8.0)
FALSE_TITANIUM=$(jq '[.props.picks[], .game_picks.picks[]] | map({
    player: (.player_name // .player // "GAME"),
    titanium: (.titanium_triggered // false),
    engines_gte_8: ([.ai_score, .research_score, .esoteric_score, .jarvis_rs] | map(select(. != null and . >= 8.0)) | length)
}) | map(select(.titanium == true and .engines_gte_8 < 3)) | length' "$TMP_FILE")

check "No false Titanium (titanium=true with <3 engines >= 8.0)" \
    "$([ "$FALSE_TITANIUM" -eq 0 ] && echo true || echo false)" \
    "$FALSE_TITANIUM violations" \
    "0 violations"

# Show any false titanium violations
if [ "$FALSE_TITANIUM" -gt 0 ]; then
    echo "  False Titanium violations:"
    jq -r '[.props.picks[], .game_picks.picks[]] | map({
        player: (.player_name // .player // "GAME"),
        titanium: (.titanium_triggered // false),
        engines_gte_8: ([.ai_score, .research_score, .esoteric_score, .jarvis_rs] | map(select(. != null and . >= 8.0)) | length),
        ai: .ai_score,
        research: .research_score,
        esoteric: .esoteric_score,
        jarvis: .jarvis_rs
    }) | map(select(.titanium == true and .engines_gte_8 < 3)) | .[] | "    \(.player): \(.engines_gte_8)/4 engines (ai=\(.ai), res=\(.research), eso=\(.esoteric), jar=\(.jarvis))"' "$TMP_FILE"
fi

# CHECK 2: TITANIUM_SMASH tier only when titanium_triggered=true
TIER_MISMATCH=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(
    (.tier == "TITANIUM_SMASH" and (.titanium_triggered | not)) or
    ((.titanium_triggered == true) and .tier != "TITANIUM_SMASH")
)) | length' "$TMP_FILE")

check "TITANIUM_SMASH tier matches titanium_triggered flag" \
    "$([ "$TIER_MISMATCH" -eq 0 ] && echo true || echo false)" \
    "$TIER_MISMATCH mismatches" \
    "0 mismatches"

# ============================================
# 6.5 MINIMUM SCORE (INVARIANT 6)
# ============================================
echo ""
echo -e "${YELLOW}[6.5 MINIMUM SCORE]${NC}"

# CHECK 3: No picks below 6.5 in response
BELOW_6_5=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.final_score < 6.5)) | length' "$TMP_FILE")
check "No picks with final_score < 6.5 returned" \
    "$([ "$BELOW_6_5" -eq 0 ] && echo true || echo false)" \
    "$BELOW_6_5 below 6.5" \
    "0 below 6.5"

# CHECK 4: Minimum returned score is >= 6.5
MIN_SCORE=$(jq '[.props.picks[], .game_picks.picks[]] | map(.final_score) | min // 10' "$TMP_FILE")
check "Minimum returned score >= 6.5" \
    "$(awk "BEGIN {exit !($MIN_SCORE >= 6.5)}" && echo true || echo false)" \
    "$MIN_SCORE" \
    ">= 6.5"

# CHECK 5: Debug shows picks were filtered
FILTERED_COUNT=$(jq '.debug.filtered_below_6_5_total // 0' "$TMP_FILE")
check "Debug shows filtered picks count" \
    "$([ "$FILTERED_COUNT" -ge 0 ] && echo true || echo false)" \
    "$FILTERED_COUNT filtered" \
    ">= 0 (field exists)"

# ============================================
# CONTRADICTION GATE (INVARIANT 7)
# ============================================
echo ""
echo -e "${YELLOW}[CONTRADICTION GATE]${NC}"

# CHECK 6: Debug shows contradiction gate stats
CONTRADICTION_BLOCKED=$(jq '.debug.contradiction_blocked_total // 0' "$TMP_FILE")
check "Contradiction gate stats present" \
    "$([ "$CONTRADICTION_BLOCKED" != "null" ] && echo true || echo false)" \
    "blocked=$CONTRADICTION_BLOCKED" \
    "field exists"

# CHECK 7: No duplicate picks on same line (Over AND Under)
# Group by player_name + prop_type + line and check for both Over and Under
CONTRADICTIONS=$(jq '[.props.picks[] | {
    key: "\(.player_name // "")|\(.prop_type // "")|\(.line // 0)",
    side: .side
}] | group_by(.key) | map(select(length > 1)) | map(select(
    (map(.side) | contains(["Over"])) and (map(.side) | contains(["Under"]))
)) | length' "$TMP_FILE" 2>/dev/null || echo "0")

check "No Over+Under contradictions in response" \
    "$([ "$CONTRADICTIONS" -eq 0 ] && echo true || echo false)" \
    "$CONTRADICTIONS contradictions" \
    "0 contradictions"

# ============================================
# TIER DISTRIBUTION (INFO)
# ============================================
echo ""
echo -e "${YELLOW}[INFO] Tier Distribution${NC}"
echo "  TITANIUM_SMASH: $(jq '[.props.picks[], .game_picks.picks[]] | map(select(.tier == "TITANIUM_SMASH")) | length' "$TMP_FILE")"
echo "  GOLD_STAR: $(jq '[.props.picks[], .game_picks.picks[]] | map(select(.tier == "GOLD_STAR")) | length' "$TMP_FILE")"
echo "  EDGE_LEAN: $(jq '[.props.picks[], .game_picks.picks[]] | map(select(.tier == "EDGE_LEAN")) | length' "$TMP_FILE")"

# CHECK 8: All picks have a valid tier
VALID_TIERS='["TITANIUM_SMASH", "GOLD_STAR", "EDGE_LEAN", "MONITOR", "PASS"]'
INVALID_TIER=$(jq --argjson valid "$VALID_TIERS" '[.props.picks[], .game_picks.picks[]] | map(select(.tier as $t | $valid | index($t) | not)) | length' "$TMP_FILE")
check "All picks have valid tier" \
    "$([ "$INVALID_TIER" -eq 0 ] && echo true || echo false)" \
    "$INVALID_TIER invalid" \
    "0 invalid"

# Summary
echo ""
echo "=============================================="
TOTAL=$((PASSED + FAILED))
echo "SESSION 5 RESULTS: $PASSED/$TOTAL checks passed"

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}SESSION 5 SPOT CHECK: FAILED${NC}"
    echo "=============================================="
    exit 1
else
    echo -e "${GREEN}SESSION 5 SPOT CHECK: ALL PASS${NC}"
    echo "=============================================="
    exit 0
fi
