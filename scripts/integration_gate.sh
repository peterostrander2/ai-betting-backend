#!/usr/bin/env bash
# =============================================================================
# INTEGRATION GATE - Production Wire-Level Verification
# =============================================================================
# Validates all integrations are properly configured AND wired to correct endpoints
#
# Usage:
#   API_KEY=your_key ./scripts/integration_gate.sh
#   API_KEY=your_key BASE_URL=https://... ./scripts/integration_gate.sh
#
# Exit codes:
#   0 = All checks passed
#   1 = Critical integration missing/unreachable
#   2 = Degraded (optional integrations failing)
# =============================================================================

set -euo pipefail

# Configuration
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-}"

if [[ -z "$API_KEY" ]]; then
    echo "ERROR: API_KEY environment variable required"
    exit 1
fi

PASS=0
WARN=0
FAIL=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_pass() { echo -e "${GREEN}✓${NC} $1"; ((PASS++)); }
log_warn() { echo -e "${YELLOW}⚠${NC} $1"; ((WARN++)); }
log_fail() { echo -e "${RED}✗${NC} $1"; ((FAIL++)); }

echo "=============================================="
echo "INTEGRATION GATE - Wire-Level Verification"
echo "Base URL: $BASE_URL"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# STEP 1: Fetch /debug/integrations
# -----------------------------------------------------------------------------
echo "[1/5] Fetching integration status..."

INTEGRATIONS=$(curl -fsS -H "X-API-Key: $API_KEY" "$BASE_URL/live/debug/integrations" 2>/dev/null) || {
    log_fail "Cannot reach /debug/integrations endpoint"
    exit 1
}

# Parse overall status
OVERALL_STATUS=$(echo "$INTEGRATIONS" | jq -r '.overall_status // "UNKNOWN"')
TOTAL=$(echo "$INTEGRATIONS" | jq -r '.total_integrations // 0')
VALIDATED=$(echo "$INTEGRATIONS" | jq -r '.status_counts.VALIDATED // 0')
CONFIGURED=$(echo "$INTEGRATIONS" | jq -r '.status_counts.CONFIGURED // 0')
UNREACHABLE=$(echo "$INTEGRATIONS" | jq -r '.status_counts.UNREACHABLE // 0')
NOT_CONFIGURED=$(echo "$INTEGRATIONS" | jq -r '.status_counts.NOT_CONFIGURED // 0')

echo "  Overall: $OVERALL_STATUS | Total: $TOTAL | Validated: $VALIDATED | Configured: $CONFIGURED"
echo ""

# -----------------------------------------------------------------------------
# STEP 2: Validate CRITICAL integrations
# -----------------------------------------------------------------------------
echo "[2/5] Validating CRITICAL integrations..."

CRITICAL_INTEGRATIONS=("odds_api" "playbook_api" "balldontlie" "railway_storage" "database")

for name in "${CRITICAL_INTEGRATIONS[@]}"; do
    status=$(echo "$INTEGRATIONS" | jq -r --arg n "$name" '.integrations[$n].status_category // "MISSING"')
    case "$status" in
        VALIDATED|CONFIGURED)
            log_pass "$name: $status"
            ;;
        UNREACHABLE)
            log_fail "$name: UNREACHABLE (CRITICAL - will block production)"
            ;;
        *)
            log_fail "$name: $status (CRITICAL - must be configured)"
            ;;
    esac
done
echo ""

# -----------------------------------------------------------------------------
# STEP 3: Validate DEGRADED-OK integrations
# -----------------------------------------------------------------------------
echo "[3/5] Validating DEGRADED-OK integrations..."

DEGRADED_OK_INTEGRATIONS=("redis" "whop_api")

for name in "${DEGRADED_OK_INTEGRATIONS[@]}"; do
    status=$(echo "$INTEGRATIONS" | jq -r --arg n "$name" '.integrations[$n].status_category // "MISSING"')
    case "$status" in
        VALIDATED|CONFIGURED)
            log_pass "$name: $status"
            ;;
        *)
            log_warn "$name: $status (system will degrade but continue)"
            ;;
    esac
done
echo ""

# -----------------------------------------------------------------------------
# STEP 4: Validate OPTIONAL integrations (informational)
# -----------------------------------------------------------------------------
echo "[4/5] Validating OPTIONAL integrations (informational)..."

OPTIONAL_INTEGRATIONS=("weather_api" "serpapi" "twitter_api" "fred_api" "finnhub_api" "astronomy_api" "noaa_space_weather")

for name in "${OPTIONAL_INTEGRATIONS[@]}"; do
    status=$(echo "$INTEGRATIONS" | jq -r --arg n "$name" '.integrations[$n].status_category // "MISSING"')
    case "$status" in
        VALIDATED|CONFIGURED|NOT_RELEVANT)
            log_pass "$name: $status"
            ;;
        *)
            log_warn "$name: $status (optional, won't block)"
            ;;
    esac
done
echo ""

# -----------------------------------------------------------------------------
# STEP 5: Validate sport→integration wiring
# -----------------------------------------------------------------------------
echo "[5/5] Validating sport→integration wiring..."

# Test NBA path (should use BallDontLie + Odds API + Playbook)
echo "  Testing NBA path..."
NBA_RESPONSE=$(curl -fsS -H "X-API-Key: $API_KEY" "$BASE_URL/live/best-bets/NBA?debug=1" 2>/dev/null) || {
    log_warn "NBA endpoint returned error (may be off-season)"
    NBA_RESPONSE="{}"
}

# Check if integrations were actually used
if echo "$NBA_RESPONSE" | jq -e '.debug.used_integrations // empty' >/dev/null 2>&1; then
    USED=$(echo "$NBA_RESPONSE" | jq -r '.debug.used_integrations | keys | join(", ")')
    if [[ "$USED" == *"odds_api"* ]]; then
        log_pass "NBA: odds_api wired and used"
    else
        log_warn "NBA: odds_api not in used_integrations (may be cached)"
    fi
else
    log_warn "NBA: used_integrations not in debug output (add ?debug=1)"
fi

# Test NFL path (should use Weather API for outdoor sports)
echo "  Testing NFL/MLB path (outdoor sports - weather required)..."
# Weather API should be CONFIGURED or VALIDATED, not DISABLED
WEATHER_STATUS=$(echo "$INTEGRATIONS" | jq -r '.integrations.weather_api.status_category // "MISSING"')
if [[ "$WEATHER_STATUS" == "VALIDATED" || "$WEATHER_STATUS" == "CONFIGURED" ]]; then
    log_pass "Weather API: $WEATHER_STATUS (ready for NFL/MLB)"
elif [[ "$WEATHER_STATUS" == "NOT_RELEVANT" ]]; then
    log_pass "Weather API: NOT_RELEVANT (no outdoor games today)"
else
    log_warn "Weather API: $WEATHER_STATUS (outdoor sports may lack weather context)"
fi

echo ""

# -----------------------------------------------------------------------------
# SUMMARY
# -----------------------------------------------------------------------------
echo "=============================================="
echo "INTEGRATION GATE SUMMARY"
echo "=============================================="
echo -e "  ${GREEN}PASS${NC}: $PASS"
echo -e "  ${YELLOW}WARN${NC}: $WARN"
echo -e "  ${RED}FAIL${NC}: $FAIL"
echo ""

if [[ $FAIL -gt 0 ]]; then
    echo -e "${RED}GATE FAILED${NC} - Critical integrations missing/unreachable"
    echo "Fix the issues above before deploying."
    exit 1
elif [[ $WARN -gt 0 ]]; then
    echo -e "${YELLOW}GATE DEGRADED${NC} - Optional integrations have issues"
    echo "System will run but with reduced functionality."
    exit 2
else
    echo -e "${GREEN}GATE PASSED${NC} - All integrations healthy"
    exit 0
fi
