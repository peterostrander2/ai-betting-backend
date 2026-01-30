#!/bin/bash
# SESSION 6 SPOT CHECK: Tier Assignment Verification
# Validates TITANIUM 3/4 rule and GOLD_STAR hard gates
# Exit 0 = all pass, Exit 1 = failures detected

set -e

# Configuration
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"
TMP_FILE="/tmp/nba_picks.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0

echo "=============================================="
echo "SESSION 6 SPOT CHECK: Tier Assignment"
echo "=============================================="
echo "Base URL: $BASE_URL"
echo "Date: $(date)"
echo ""

# Step 1: Fetch data once and save to file
echo -e "${YELLOW}Fetching NBA picks...${NC}"
curl -s "$BASE_URL/live/best-bets/nba?debug=1&max_props=100" \
    -H "X-API-Key: $API_KEY" > "$TMP_FILE"

PROPS_COUNT=$(jq '.props.count' "$TMP_FILE")
GAMES_COUNT=$(jq '.game_picks.count' "$TMP_FILE")
echo "Fetched: $PROPS_COUNT props, $GAMES_COUNT games"
echo ""

# Check 1: False Titanium detector
echo -e "${YELLOW}[CHECK 1] False Titanium (titanium=true but engines < 3)${NC}"
VIOLATIONS=$(jq '[.props.picks[], .game_picks.picks[]] | map({
    player: (.player_name // .player // "UNKNOWN"),
    titanium: (.titanium_triggered // false),
    engines_gte_8: ([.ai_score, .research_score, .esoteric_score, .jarvis_rs] | map(select(. >= 8.0)) | length)
}) | map(select(.titanium == true and .engines_gte_8 < 3)) | length' "$TMP_FILE")

if [ "$VIOLATIONS" -eq 0 ]; then
    echo -e "${GREEN}PASS${NC}: No false Titanium (0 violations)"
else
    echo -e "${RED}FAIL${NC}: $VIOLATIONS picks have titanium=true with < 3 engines >= 8.0"
    jq -r '[.props.picks[], .game_picks.picks[]] | map({
        player: (.player_name // .player // "UNKNOWN"),
        titanium: (.titanium_triggered // false),
        engines_gte_8: ([.ai_score, .research_score, .esoteric_score, .jarvis_rs] | map(select(. >= 8.0)) | length),
        ai: .ai_score,
        research: .research_score,
        esoteric: .esoteric_score,
        jarvis: .jarvis_rs
    }) | map(select(.titanium == true and .engines_gte_8 < 3)) | .[] | "  \(.engines_gte_8) engines: \(.player) (ai=\(.ai), res=\(.research), eso=\(.esoteric), jar=\(.jarvis))"' "$TMP_FILE"
    FAILED=1
fi
echo ""

# Check 2: TITANIUM_SMASH tier consistency
echo -e "${YELLOW}[CHECK 2] TITANIUM_SMASH tier consistency${NC}"
TIER_VIOLATIONS=$(jq '[.props.picks[], .game_picks.picks[]] | map({
    player: (.player_name // .player // "UNKNOWN"),
    tier: .tier,
    titanium: (.titanium_triggered // false)
}) | map(select(.tier == "TITANIUM_SMASH" and .titanium != true)) | length' "$TMP_FILE")

if [ "$TIER_VIOLATIONS" -eq 0 ]; then
    echo -e "${GREEN}PASS${NC}: No TITANIUM_SMASH without titanium_triggered=true"
else
    echo -e "${RED}FAIL${NC}: $TIER_VIOLATIONS picks have tier=TITANIUM_SMASH but titanium_triggered != true"
    jq -r '[.props.picks[], .game_picks.picks[]] | map({
        player: (.player_name // .player // "UNKNOWN"),
        tier: .tier,
        titanium: (.titanium_triggered // false),
        final: .final_score
    }) | map(select(.tier == "TITANIUM_SMASH" and .titanium != true)) | .[] | "  \(.player): tier=\(.tier), titanium=\(.titanium), final=\(.final)"' "$TMP_FILE"
    FAILED=1
fi
echo ""

# Check 3: Gold-star gate audit
echo -e "${YELLOW}[CHECK 3] Gold-star gate audit (final >= 7.5 but not GOLD_STAR)${NC}"
GATE_FAILURES=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.final_score >= 7.5 and .tier != "GOLD_STAR" and .tier != "TITANIUM_SMASH")) | length' "$TMP_FILE")

echo "Picks with final >= 7.5 that are EDGE_LEAN (not GOLD_STAR): $GATE_FAILURES"
if [ "$GATE_FAILURES" -gt 0 ]; then
    echo "Gate failure breakdown (showing up to 10):"
    jq -r '[.props.picks[], .game_picks.picks[]] | map(select(.final_score >= 7.5 and .tier != "GOLD_STAR" and .tier != "TITANIUM_SMASH")) | .[0:10] | .[] | "  \(.player_name // .player // "UNKNOWN"): final=\(.final_score) tier=\(.tier) | ai=\(.ai_score) (>=6.8: \(.ai_score >= 6.8)) res=\(.research_score) (>=5.5: \(.research_score >= 5.5)) eso=\(.esoteric_score) (>=4.0: \(.esoteric_score >= 4.0)) jar=\(.jarvis_rs) (>=6.5: \(.jarvis_rs >= 6.5))"' "$TMP_FILE"

    # Check if all gate failures have a valid reason (at least one gate false)
    UNEXPLAINED=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.final_score >= 7.5 and .tier != "GOLD_STAR" and .tier != "TITANIUM_SMASH")) | map(select(.ai_score >= 6.8 and .research_score >= 5.5 and .esoteric_score >= 4.0 and .jarvis_rs >= 6.5)) | length' "$TMP_FILE")

    if [ "$UNEXPLAINED" -eq 0 ]; then
        echo -e "${GREEN}PASS${NC}: All gate failures have valid reason (at least one gate < threshold)"
    else
        echo -e "${RED}FAIL${NC}: $UNEXPLAINED picks pass all gates but are not GOLD_STAR"
        FAILED=1
    fi
else
    echo -e "${GREEN}PASS${NC}: No picks with score >= 7.5 that fail gates"
fi
echo ""

# Check 4: Top picks by engine count (informational)
echo -e "${YELLOW}[INFO] Top 10 picks by engines >= 8.0${NC}"
jq -r '[.props.picks[], .game_picks.picks[]] | map({
    player: (.player_name // .player // "UNKNOWN"),
    tier: .tier,
    titanium: (.titanium_triggered // false),
    engines_gte_8: ([.ai_score, .research_score, .esoteric_score, .jarvis_rs] | map(select(. >= 8.0)) | length),
    final: .final_score,
    ai: .ai_score,
    research: .research_score,
    esoteric: .esoteric_score,
    jarvis: .jarvis_rs
}) | sort_by(-.engines_gte_8, -.final) | .[0:10] | .[] | "\(.engines_gte_8) engines | TIT=\(.titanium) | \(.tier) | final=\(.final) | ai=\(.ai) res=\(.research) eso=\(.esoteric) jar=\(.jarvis) | \(.player)"' "$TMP_FILE"
echo ""

# Summary
echo "=============================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}SESSION 6 SPOT CHECK: ALL PASS${NC}"
    echo "=============================================="
    exit 0
else
    echo -e "${RED}SESSION 6 SPOT CHECK: FAILED${NC}"
    echo "=============================================="
    exit 1
fi
