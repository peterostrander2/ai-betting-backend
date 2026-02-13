#!/usr/bin/env bash
# =============================================================================
# CI GOLDEN GATE - v20.21 Regression Prevention
# =============================================================================
#
# Single script that enforces ALL frozen contracts. Use in:
# - Pre-commit hooks
# - GitHub Actions
# - Pre-deploy gates
#
# Exit codes:
#   0 = All gates pass (safe to deploy)
#   1 = Gate failure (BLOCK DEPLOY)
#
# Usage:
#   ./scripts/ci_golden_gate.sh              # Unit tests only (no API)
#   API_KEY=xxx ./scripts/ci_golden_gate.sh  # Unit tests + live validation
#
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
API_KEY="${API_KEY:-}"
API_BASE="${API_BASE:-https://web-production-7b2a.up.railway.app}"
SKIP_LIVE="${SKIP_LIVE:-}"
RAILWAY_VOLUME_MOUNT_PATH="${RAILWAY_VOLUME_MOUNT_PATH:-/tmp}"
export RAILWAY_VOLUME_MOUNT_PATH

echo ""
echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}CI GOLDEN GATE - v20.21 Regression Prevention${NC}"
echo -e "${CYAN}================================================${NC}"
echo ""

FAILED=0
PASSED=0
SKIPPED=0

pass() {
    echo -e "${GREEN}  PASS${NC}: $1"
    PASSED=$((PASSED + 1))
}

fail() {
    echo -e "${RED}  FAIL${NC}: $1"
    FAILED=$((FAILED + 1))
}

skip() {
    echo -e "${YELLOW}  SKIP${NC}: $1"
    SKIPPED=$((SKIPPED + 1))
}

# =============================================================================
# GATE 1: Golden Run Unit Tests
# =============================================================================
echo -e "${YELLOW}[1/4] Golden Run Unit Tests${NC}"

if python -m pytest tests/test_golden_run.py -q --tb=line 2>&1; then
    pass "Golden run contract tests (weights, tiers, thresholds)"
else
    fail "Golden run contract tests failed"
fi

# =============================================================================
# GATE 2: Output Boundary Tests
# =============================================================================
echo ""
echo -e "${YELLOW}[2/4] Output Boundary Hardening Tests${NC}"

if python -m pytest tests/test_debug_telemetry.py -q --tb=line 2>&1; then
    pass "Output boundary and telemetry tests"
else
    fail "Output boundary tests failed"
fi

# =============================================================================
# GATE 3: Integration Contract Tests
# =============================================================================
echo ""
echo -e "${YELLOW}[3/4] Integration Contract Tests${NC}"

if python -m pytest tests/test_integration_validation.py -q --tb=line 2>&1; then
    pass "Integration registry contract tests"
else
    fail "Integration contract tests failed"
fi

# =============================================================================
# GATE 4: Live Validation (Optional - requires API_KEY)
# =============================================================================
echo ""
echo -e "${YELLOW}[4/4] Live Golden Run Validation${NC}"

if [[ -n "$SKIP_LIVE" ]]; then
    skip "Live validation (SKIP_LIVE set)"
elif [[ -z "$API_KEY" ]]; then
    skip "Live validation (API_KEY not set)"
else
    if API_KEY="$API_KEY" python3 scripts/golden_run.py validate 2>&1; then
        pass "Live golden run validation against $API_BASE"
    else
        fail "Live golden run validation failed"
    fi
fi

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo -e "${CYAN}================================================${NC}"
echo -e "${CYAN}SUMMARY${NC}"
echo -e "${CYAN}================================================${NC}"
echo -e "  Passed:  ${GREEN}$PASSED${NC}"
echo -e "  Failed:  ${RED}$FAILED${NC}"
echo -e "  Skipped: ${YELLOW}$SKIPPED${NC}"
echo ""

if [[ $FAILED -gt 0 ]]; then
    echo -e "${RED}================================================${NC}"
    echo -e "${RED}CI GOLDEN GATE FAILED${NC}"
    echo -e "${RED}$FAILED gate(s) failed - BLOCK DEPLOY${NC}"
    echo -e "${RED}================================================${NC}"
    exit 1
else
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}CI GOLDEN GATE PASSED${NC}"
    echo -e "${GREEN}All gates passed - safe to deploy${NC}"
    echo -e "${GREEN}================================================${NC}"
    exit 0
fi
