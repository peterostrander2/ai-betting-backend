#!/bin/bash
# CI SANITY CHECK - Hard Gate Validation for Sessions 1-8
# Runs all session spot checks in order, fails on first failure
# Exit 0 = all sessions pass, Exit 1 = at least one session failed

set -e

# Configuration
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Export for child scripts
export BASE_URL
export API_KEY

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================================"
echo "       CI SANITY CHECK - Backend Hard Gates"
echo "========================================================"
echo "Base URL: $BASE_URL"
echo "Date: $(date)"
echo "========================================================"
echo ""

# Track results
declare -a SESSION_RESULTS
TOTAL_SESSIONS=8
SESSIONS_PASSED=0
SESSIONS_FAILED=0

# Function to run a session and track result
run_session() {
    local session_num=$1
    local session_name=$2
    local script_path="$SCRIPT_DIR/spot_check_session${session_num}.sh"

    echo ""
    echo -e "${BLUE}========================================================"
    echo "  RUNNING SESSION $session_num: $session_name"
    echo -e "========================================================${NC}"

    if [ ! -f "$script_path" ]; then
        echo -e "${RED}ERROR: Script not found: $script_path${NC}"
        SESSION_RESULTS[$session_num]="MISSING"
        ((SESSIONS_FAILED++))
        return 1
    fi

    if [ ! -x "$script_path" ]; then
        echo -e "${YELLOW}Making script executable: $script_path${NC}"
        chmod +x "$script_path"
    fi

    # Run the session script
    set +e
    "$script_path"
    local exit_code=$?
    set -e

    if [ $exit_code -eq 0 ]; then
        SESSION_RESULTS[$session_num]="PASS"
        ((SESSIONS_PASSED++))
        return 0
    else
        SESSION_RESULTS[$session_num]="FAIL"
        ((SESSIONS_FAILED++))
        echo ""
        echo -e "${RED}SESSION $session_num FAILED - Stopping CI${NC}"
        return 1
    fi
}

# Pre-flight: Check API is reachable
echo -e "${YELLOW}Pre-flight: Checking API health...${NC}"
HEALTH=$(curl -s --max-time 10 "$BASE_URL/health" 2>/dev/null || echo "UNREACHABLE")

if [ "$HEALTH" = "UNREACHABLE" ]; then
    echo -e "${RED}ERROR: API unreachable at $BASE_URL${NC}"
    echo "Cannot proceed with CI sanity checks."
    exit 1
fi

HEALTH_STATUS=$(echo "$HEALTH" | jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")
if [ "$HEALTH_STATUS" != "healthy" ] && [ "$HEALTH_STATUS" != "ok" ]; then
    echo -e "${RED}WARNING: API health status: $HEALTH_STATUS${NC}"
fi
echo -e "${GREEN}API is reachable${NC}"
echo ""

# Run sessions in order - fail on first failure
SESSION_NAMES=(
    ""  # Index 0 unused
    "ET Window Correctness"
    "Persistence / Storage"
    "Research Engine"
    "Integrations"
    "Tiering + Filters"
    "Gold Star + Jarvis"
    "Output Filtering Pipeline"
    "Grading & Multi-Sport"
)

for i in $(seq 1 $TOTAL_SESSIONS); do
    if ! run_session $i "${SESSION_NAMES[$i]}"; then
        # Session failed - print summary and exit
        echo ""
        echo "========================================================"
        echo "                   CI SANITY SUMMARY"
        echo "========================================================"
        echo ""
        for j in $(seq 1 $TOTAL_SESSIONS); do
            result="${SESSION_RESULTS[$j]:-NOT_RUN}"
            case $result in
                "PASS")
                    echo -e "  Session $j (${SESSION_NAMES[$j]}): ${GREEN}PASS${NC}"
                    ;;
                "FAIL")
                    echo -e "  Session $j (${SESSION_NAMES[$j]}): ${RED}FAIL${NC}"
                    ;;
                "MISSING")
                    echo -e "  Session $j (${SESSION_NAMES[$j]}): ${RED}MISSING${NC}"
                    ;;
                *)
                    echo -e "  Session $j (${SESSION_NAMES[$j]}): ${YELLOW}NOT_RUN${NC}"
                    ;;
            esac
        done
        echo ""
        echo "========================================================"
        echo -e "${RED}CI SANITY CHECK FAILED${NC}"
        echo "Sessions passed: $SESSIONS_PASSED / $TOTAL_SESSIONS"
        echo "========================================================"
        exit 1
    fi
done

# All sessions passed
echo ""
echo "========================================================"
echo "                   CI SANITY SUMMARY"
echo "========================================================"
echo ""
for i in $(seq 1 $TOTAL_SESSIONS); do
    echo -e "  Session $i (${SESSION_NAMES[$i]}): ${GREEN}PASS${NC}"
done
echo ""
echo "========================================================"
echo -e "${GREEN}ALL $TOTAL_SESSIONS SESSIONS PASSED${NC}"
echo "========================================================"
echo ""
echo "Backend invariants validated:"
echo "  [1] ET window: 00:01:00 ET to 00:00:00 next day (exclusive)"
echo "  [2] Persistence: Railway volume mounted and writable"
echo "  [3] Research: No double-counting, proper signal ownership"
echo "  [4] Integrations: All required APIs VALIDATED"
echo "  [5] Tiering: Titanium 3/4 rule, 6.5 minimum, contradiction gate"
echo "  [6] Gold Star: Hard gates + Jarvis v16.0 additive scoring"
echo "  [7] Output filtering: Dedup, score filter, contradiction gate, top-N"
echo "  [8] Grading: Storage, BDL integration, multi-sport endpoints"
echo ""
echo "Safe to deploy."
exit 0
