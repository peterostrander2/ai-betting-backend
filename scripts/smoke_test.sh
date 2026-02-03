#!/bin/bash
#
# smoke_test.sh - Basic smoke test for Bookie-o-em API
#
# Tests public endpoints (/health, /status) to verify basic system functionality.
# Does NOT require API key - suitable for health monitoring and quick checks.
#
# Usage:
#   ./scripts/smoke_test.sh                    # Test production
#   BASE_URL=http://localhost:8000 ./scripts/smoke_test.sh  # Test local
#
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed
#

set -e

# Configuration
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
TIMEOUT=10

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "SMOKE TEST - Bookie-o-em API"
echo "================================================"
echo "Target: $BASE_URL"
echo ""

PASSED=0
FAILED=0

# Helper function to check endpoint
check_endpoint() {
    local name="$1"
    local path="$2"
    local expected_status="${3:-200}"
    local check_body="$4"  # Optional: string to check in response body

    echo -n "[$name] $path ... "

    # Make request
    response=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$BASE_URL$path" 2>&1)
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    # Check status code
    if [ "$http_code" != "$expected_status" ]; then
        echo -e "${RED}FAIL${NC} (status: $http_code, expected: $expected_status)"
        FAILED=$((FAILED + 1))
        return 1
    fi

    # Check body content if specified
    if [ -n "$check_body" ]; then
        if echo "$body" | grep -q "$check_body"; then
            echo -e "${GREEN}PASS${NC}"
            PASSED=$((PASSED + 1))
        else
            echo -e "${RED}FAIL${NC} (missing: $check_body)"
            FAILED=$((FAILED + 1))
            return 1
        fi
    else
        echo -e "${GREEN}PASS${NC}"
        PASSED=$((PASSED + 1))
    fi
}

echo "[1/3] Testing public endpoints..."
echo ""

# Test /health endpoint
check_endpoint "Health Check" "/health" "200" "healthy"

# Test /status endpoint (HTML page)
check_endpoint "Status Page" "/status" "200" "Bookie-o-em Status"

# Test root endpoint
check_endpoint "Root API" "/" "200" "operational"

echo ""
echo "================================================"
echo "RESULTS"
echo "================================================"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All smoke tests passed${NC}"
    exit 0
else
    echo -e "${RED}✗ Some smoke tests failed${NC}"
    exit 1
fi
