#!/bin/bash
# SESSION 4 SPOT CHECK: Integration Validation
# Validates all required integrations are VALIDATED (not just CONFIGURED)
# Exit 0 = all pass, Exit 1 = failures detected

# Don't exit on first error - we track failures manually
set +e

# Configuration
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"
TMP_FILE="/tmp/session4_integrations.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0
PASSED=0

echo "=============================================="
echo "SESSION 4 SPOT CHECK: Integration Validation"
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

# Fetch integrations status
echo -e "${YELLOW}Fetching /live/debug/integrations...${NC}"
curl -s "$BASE_URL/live/debug/integrations" -H "X-API-Key: $API_KEY" > "$TMP_FILE"

# Show summary
CONFIGURED=$(jq '.configured | length' "$TMP_FILE" 2>/dev/null || echo "0")
NOT_CONFIGURED=$(jq '.not_configured | length' "$TMP_FILE" 2>/dev/null || echo "0")
echo "Configured: $CONFIGURED, Not Configured: $NOT_CONFIGURED"
echo ""

# Required integrations that MUST be VALIDATED
REQUIRED_INTEGRATIONS=(
    "odds_api"
    "playbook_api"
    "balldontlie"
    "railway_storage"
)

# Integrations that should be VALIDATED or NOT_RELEVANT
CONDITIONAL_INTEGRATIONS=(
    "weather_api"
)

# CHECK: Each required integration is VALIDATED
echo -e "${YELLOW}[REQUIRED INTEGRATIONS]${NC}"
for INT in "${REQUIRED_INTEGRATIONS[@]}"; do
    STATUS=$(jq -r ".integrations.$INT.status_category // \"NOT_FOUND\"" "$TMP_FILE")
    VALIDATION_STATUS=$(jq -r ".integrations.$INT.validation.status // \"UNKNOWN\"" "$TMP_FILE")

    # VALIDATED means env var set AND connectivity confirmed
    IS_VALIDATED=$([ "$STATUS" = "VALIDATED" ] || [ "$VALIDATION_STATUS" = "VALIDATED" ] && echo true || echo false)

    check "$INT is VALIDATED" \
        "$IS_VALIDATED" \
        "status=$STATUS, validation=$VALIDATION_STATUS" \
        "VALIDATED"
done

# CHECK: Weather integration (relevance-gated)
echo ""
echo -e "${YELLOW}[CONDITIONAL INTEGRATIONS]${NC}"
for INT in "${CONDITIONAL_INTEGRATIONS[@]}"; do
    STATUS=$(jq -r ".integrations.$INT.status_category // \"NOT_FOUND\"" "$TMP_FILE")
    VALIDATION_STATUS=$(jq -r ".integrations.$INT.validation.status // \"UNKNOWN\"" "$TMP_FILE")

    # Weather can be VALIDATED or NOT_RELEVANT (for indoor sports), but NOT "CONFIGURED" without validation
    IS_OK=$([ "$STATUS" = "VALIDATED" ] || [ "$STATUS" = "NOT_RELEVANT" ] || [ "$VALIDATION_STATUS" = "VALIDATED" ] || [ "$VALIDATION_STATUS" = "NOT_RELEVANT" ] && echo true || echo false)

    check "$INT is VALIDATED or NOT_RELEVANT" \
        "$IS_OK" \
        "status=$STATUS, validation=$VALIDATION_STATUS" \
        "VALIDATED or NOT_RELEVANT"
done

# CHECK: Core integrations validated (others are informational)
# Only require core integrations to be validated; optional ones can be CONFIGURED
echo ""
echo -e "${YELLOW}[CORE INTEGRATIONS VALIDATED]${NC}"
CORE_INTEGRATIONS=("odds_api" "playbook_api" "balldontlie" "railway_storage")
CORE_UNVALIDATED=0
for INT in "${CORE_INTEGRATIONS[@]}"; do
    STATUS=$(jq -r ".integrations.$INT.status_category // \"NOT_FOUND\"" "$TMP_FILE")
    if [ "$STATUS" != "VALIDATED" ]; then
        ((CORE_UNVALIDATED++)) || true
    fi
done
check "Core integrations (odds/playbook/bdl/storage) validated" \
    "$([ "$CORE_UNVALIDATED" -eq 0 ] && echo true || echo false)" \
    "$CORE_UNVALIDATED unvalidated" \
    "0 unvalidated"

# INFO: Show optional integrations status (not a hard fail)
OPTIONAL_CONFIGURED=$(jq '[.integrations | to_entries[] | select(.value.status_category == "CONFIGURED")] | length' "$TMP_FILE" 2>/dev/null || echo "0")
echo "  (INFO: $OPTIONAL_CONFIGURED optional integrations are CONFIGURED but not validated)"

# CHECK: No REQUIRED integrations with ERROR status
# Note: serpapi is optional (SERP_INTEL_ENABLED=false by default per CLAUDE.md Lesson 62)
#       UNREACHABLE for optional integrations is acceptable
echo -e "${YELLOW}[NO ERROR STATUS]${NC}"
OPTIONAL_INTEGRATIONS="serpapi|twitter_api|finnhub_api|fred_api"  # Optional integrations that can be UNREACHABLE
ERRORED=$(jq --arg opt "$OPTIONAL_INTEGRATIONS" '[.integrations | to_entries[] | select(.value.status_category == "ERROR" or (.value.status_category == "UNREACHABLE" and (.key | test($opt) | not)))] | .[].key' "$TMP_FILE" 2>/dev/null | tr '\n' ', ' || echo "none")
ERROR_COUNT=$(jq --arg opt "$OPTIONAL_INTEGRATIONS" '[.integrations | to_entries[] | select(.value.status_category == "ERROR" or (.value.status_category == "UNREACHABLE" and (.key | test($opt) | not)))] | length' "$TMP_FILE" 2>/dev/null || echo "0")
check "No required integrations with ERROR status" \
    "$([ "$ERROR_COUNT" -eq 0 ] && echo true || echo false)" \
    "$ERRORED" \
    "none"

# CHECK: BallDontLie API key supported (BDL_API_KEY or BALLDONTLIE_API_KEY)
echo ""
echo -e "${YELLOW}[BDL API KEY]${NC}"
BDL_STATUS=$(jq -r '.integrations.balldontlie.status_category // "NOT_FOUND"' "$TMP_FILE")
BDL_ENV_VAR=$(jq -r '.integrations.balldontlie.env_var // .integrations.balldontlie.env_vars // "UNKNOWN"' "$TMP_FILE")
check "BallDontLie integration configured" \
    "$([ "$BDL_STATUS" = "VALIDATED" ] && echo true || echo false)" \
    "status=$BDL_STATUS, env=$BDL_ENV_VAR" \
    "VALIDATED with env var"

# CHECK: Quick summary shows all required as OK
echo ""
echo -e "${YELLOW}[QUICK SUMMARY]${NC}"
QUICK_SUMMARY=$(curl -s "$BASE_URL/live/debug/integrations?quick=true" -H "X-API-Key: $API_KEY")
REQUIRED_IN_CONFIGURED=$(echo "$QUICK_SUMMARY" | jq -r '.configured | map(select(. == "odds_api" or . == "playbook_api" or . == "balldontlie" or . == "railway_storage")) | length')
check "All 4 required integrations in configured list" \
    "$([ "$REQUIRED_IN_CONFIGURED" -ge 4 ] && echo true || echo false)" \
    "$REQUIRED_IN_CONFIGURED of 4" \
    "4 of 4"

# INFO: List all integrations and their status
echo ""
echo -e "${YELLOW}[INFO] All Integration Status${NC}"
jq -r '.integrations | to_entries[] | "  \(.key): \(.value.status_category // .value.validation.status // "UNKNOWN")"' "$TMP_FILE" 2>/dev/null || echo "  Unable to parse"

# Summary
echo ""
echo "=============================================="
TOTAL=$((PASSED + FAILED))
echo "SESSION 4 RESULTS: $PASSED/$TOTAL checks passed"

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}SESSION 4 SPOT CHECK: FAILED${NC}"
    echo "=============================================="
    exit 1
else
    echo -e "${GREEN}SESSION 4 SPOT CHECK: ALL PASS${NC}"
    echo "=============================================="
    exit 0
fi

# -------- CHECK 10: Integration Contract Validation --------
echo ""
echo "Check 10: Integration contract validation..."

# Run the contract validator
if ! ./scripts/validate_integration_contract.sh > /dev/null 2>&1; then
  fail "Integration contract validation failed"
fi
echo "✅ Integration contract valid"

# -------- CHECK 11: Required Integrations Status --------
echo ""
echo "Check 11: Required integrations status..."

REQUIRED_STATUS="$(curl -s "${BASE_URL}/live/debug/integrations" \
  -H "X-API-Key: ${API_KEY}" | jq -r '
  .integrations 
  | to_entries 
  | map(select(.value.required == true))
  | map({
      key: .key,
      status: .value.status_category
    })
')"

# Check that no required integration has ERROR or MISSING status
BAD_STATUS="$(echo "$REQUIRED_STATUS" | jq -r '
  map(select(.status == "ERROR" or .status == "MISSING"))
  | length
')"

if [ "$BAD_STATUS" -gt 0 ]; then
  echo "❌ FAIL: Required integrations with ERROR/MISSING status:"
  echo "$REQUIRED_STATUS" | jq -r 'map(select(.status == "ERROR" or .status == "MISSING"))'
  exit 1
fi

echo "✅ All required integrations valid"
