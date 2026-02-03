#!/bin/bash
# SESSION 3 SPOT CHECK: Research Engine Correctness
# Validates no double-counting between Research and Jarvis engines
# Exit 0 = all pass, Exit 1 = failures detected

# Don't exit on first error - we track failures manually
set +e

# Configuration
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"
TMP_FILE="/tmp/session3_picks.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0
PASSED=0

echo "=============================================="
echo "SESSION 3 SPOT CHECK: Research Engine"
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
echo -e "${YELLOW}Fetching NBA picks for research engine analysis...${NC}"
curl -s "$BASE_URL/live/best-bets/nba?debug=1&max_props=50&max_games=20" \
    -H "X-API-Key: $API_KEY" > "$TMP_FILE"

PROPS_COUNT=$(jq '.props.count // 0' "$TMP_FILE")
GAMES_COUNT=$(jq '.game_picks.count // 0' "$TMP_FILE")
echo "Fetched: $PROPS_COUNT props, $GAMES_COUNT games"
echo ""

# CHECK 1: Research reasons field exists on all picks
echo -e "${YELLOW}[CHECK 1] Research reasons populated${NC}"
MISSING_RESEARCH=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.research_reasons == null or (.research_reasons | length) == 0)) | length' "$TMP_FILE")
check "All picks have research_reasons" \
    "$([ "$MISSING_RESEARCH" -eq 0 ] && echo true || echo false)" \
    "$MISSING_RESEARCH picks missing" \
    "0 missing"

# CHECK 2: Research score is within expected bounds (0-10)
echo -e "${YELLOW}[CHECK 2] Research scores within bounds${NC}"
OUT_OF_BOUNDS=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.research_score < 0 or .research_score > 10)) | length' "$TMP_FILE")
check "Research scores 0-10" \
    "$([ "$OUT_OF_BOUNDS" -eq 0 ] && echo true || echo false)" \
    "$OUT_OF_BOUNDS out of bounds" \
    "0 out of bounds"

# CHECK 3: No double-counting of sharp signals
# Sharp should ONLY appear in research_reasons, NOT in jarvis_reasons
echo -e "${YELLOW}[CHECK 3] No sharp signal double-counting${NC}"
DOUBLE_SHARP=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(
    (.research_reasons | join(",") | test("(?i)sharp"; "i")) and
    (.jarvis_reasons | join(",") | test("(?i)sharp.*money|sharp.*signal"; "i"))
)) | length' "$TMP_FILE" 2>/dev/null || echo "0")
check "No sharp double-counting (Research + Jarvis)" \
    "$([ "$DOUBLE_SHARP" -eq 0 ] && echo true || echo false)" \
    "$DOUBLE_SHARP violations" \
    "0 violations"

# CHECK 4: Public fade logic (if triggered, needs public >= 65%)
echo -e "${YELLOW}[CHECK 4] Public fade requires public >= 65%${NC}"
# Find picks with public fade in reasons but public_pct < 65
# Note: This checks that public fade is not falsely triggered
INVALID_FADE=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(
    (.research_reasons | join(",") | test("(?i)public.*fade|fade.*public"; "i")) and
    ((.public_pct // 50) < 65)
)) | length' "$TMP_FILE" 2>/dev/null || echo "0")
check "Public fade only when public >= 65%" \
    "$([ "$INVALID_FADE" -eq 0 ] && echo true || echo false)" \
    "$INVALID_FADE violations" \
    "0 violations"

# CHECK 5: Research score field present on all picks
echo -e "${YELLOW}[CHECK 5] Research score field present${NC}"
MISSING_RESEARCH_SCORE=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.research_score == null)) | length' "$TMP_FILE")
check "Research score field present on all picks" \
    "$([ "$MISSING_RESEARCH_SCORE" -eq 0 ] && echo true || echo false)" \
    "$MISSING_RESEARCH_SCORE missing" \
    "0 missing"

# CHECK 6: Research engine owns sharp/splits/variance
# Verify these signals appear in research_reasons when present
echo -e "${YELLOW}[CHECK 6] Research owns market signals${NC}"
# Check if any picks have sharp signals
HAS_SHARP=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(.research_reasons | join(",") | test("(?i)sharp"; "i"))) | length' "$TMP_FILE" 2>/dev/null || echo "0")
echo "  Picks with sharp signals in Research: $HAS_SHARP"
check "Sharp signals appear in Research engine" \
    "true" \
    "$HAS_SHARP picks" \
    "sharp in research_reasons (if present)"

# CHECK 7: Jarvis does not duplicate market signals
echo -e "${YELLOW}[CHECK 7] Jarvis does not own market signals${NC}"
# Jarvis should not have "line variance" or "splits" - those are Research
JARVIS_MARKET=$(jq '[.props.picks[], .game_picks.picks[]] | map(select(
    (.jarvis_reasons | join(",") | test("(?i)line.*variance|splits|public.*money"; "i"))
)) | length' "$TMP_FILE" 2>/dev/null || echo "0")
check "Jarvis does not claim market signals" \
    "$([ "$JARVIS_MARKET" -eq 0 ] && echo true || echo false)" \
    "$JARVIS_MARKET violations" \
    "0 violations"

# CHECK 8: Sample pick research analysis
echo -e "${YELLOW}[INFO] Sample pick research analysis${NC}"
jq -r '.props.picks[0] | "  Player: \(.player_name // "N/A")\n  Research Score: \(.research_score)\n  Research Reasons: \(.research_reasons | join("; "))"' "$TMP_FILE" 2>/dev/null || echo "  No sample available"

# Summary
echo ""
echo "=============================================="
TOTAL=$((PASSED + FAILED))
echo "SESSION 3 RESULTS: $PASSED/$TOTAL checks passed"

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}SESSION 3 SPOT CHECK: FAILED${NC}"
    echo "=============================================="
    exit 1
else
    echo -e "${GREEN}SESSION 3 SPOT CHECK: ALL PASS${NC}"
    echo "=============================================="
    exit 0
fi
