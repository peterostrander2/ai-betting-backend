#!/bin/bash
#
# RELEASE GATE SCRIPT - "NEVER BREAK AGAIN"
#
# This script must pass before any deployment is allowed.
# Run this locally before pushing to main.
# Should be integrated into CI/CD pipeline.
#
# Exit codes:
# 0 - All checks passed (safe to deploy)
# 1 - One or more checks failed (BLOCK DEPLOY)

set -e  # Exit on first error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "RELEASE GATE - Backend Reliability Checks"
echo "================================================"
echo

# =============================================================================
# CHECK 1: Run all tests
# =============================================================================
echo "${YELLOW}[1/5] Running test suite...${NC}"
if python -m pytest -q tests/test_titanium_invariants.py tests/test_jarvis_transparency.py tests/test_titanium_strict.py; then
    echo "${GREEN}✓ Tests passed${NC}"
else
    echo "${RED}✗ FAIL: Tests failed${NC}"
    exit 1
fi
echo

# =============================================================================
# CHECK 2: Verify health endpoint responds
# =============================================================================
echo "${YELLOW}[2/5] Checking /health endpoint...${NC}"
if curl -s --fail https://web-production-7b2a.up.railway.app/health > /dev/null; then
    HEALTH=$(curl -s https://web-production-7b2a.up.railway.app/health)
    echo "${GREEN}✓ Health endpoint responding${NC}"
    echo "  Response: $HEALTH"
else
    echo "${RED}✗ FAIL: Health endpoint not responding${NC}"
    exit 1
fi
echo

# =============================================================================
# CHECK 3: Verify best-bets endpoint with invariant checks
# =============================================================================
echo "${YELLOW}[3/5] Checking /live/best-bets/NBA endpoint...${NC}"

# Fetch NBA picks
NBA_RESPONSE=$(curl -s "https://web-production-7b2a.up.railway.app/live/best-bets/NBA?max_props=5&max_games=5" \
    -H "X-API-Key: bookie-prod-2026-xK9mP2nQ7vR4" 2>/dev/null || echo '{}')

if [ "$NBA_RESPONSE" = "{}" ]; then
    echo "${RED}✗ FAIL: Could not fetch NBA picks${NC}"
    exit 1
fi

# Check deploy_version is present
DEPLOY_VERSION=$(echo "$NBA_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('deploy_version', 'MISSING'))" 2>/dev/null || echo "MISSING")

if [ "$DEPLOY_VERSION" = "MISSING" ]; then
    echo "${RED}✗ FAIL: deploy_version missing from response${NC}"
    exit 1
else
    echo "${GREEN}✓ Best-bets endpoint responding${NC}"
    echo "  Deploy version: $DEPLOY_VERSION"
fi
echo

# =============================================================================
# CHECK 4: Validate no picks < 6.5 returned
# =============================================================================
echo "${YELLOW}[4/5] Validating score threshold (no picks < 6.5)...${NC}"

# Check minimum scores
MIN_SCORE=$(echo "$NBA_RESPONSE" | python3 -c "
import json, sys
d = json.load(sys.stdin)
props = d.get('props', {}).get('picks', [])
games = d.get('game_picks', {}).get('picks', [])
all_picks = props + games
if all_picks:
    scores = [p.get('final_score', p.get('total_score', 10)) for p in all_picks]
    print(min(scores))
else:
    print('10.0')
" 2>/dev/null || echo "ERROR")

if [ "$MIN_SCORE" = "ERROR" ]; then
    echo "${RED}✗ FAIL: Could not parse scores${NC}"
    exit 1
fi

# Compare minimum score to threshold
if python3 -c "import sys; sys.exit(0 if float('$MIN_SCORE') >= 6.5 else 1)" 2>/dev/null; then
    echo "${GREEN}✓ All picks >= 6.5 (min: $MIN_SCORE)${NC}"
else
    echo "${RED}✗ FAIL: Found pick with score < 6.5 (min: $MIN_SCORE)${NC}"
    exit 1
fi
echo

# =============================================================================
# CHECK 5: Validate Jarvis transparency fields
# =============================================================================
echo "${YELLOW}[5/5] Validating Jarvis transparency (7 required fields)...${NC}"

JARVIS_CHECK=$(echo "$NBA_RESPONSE" | python3 -c "
import json, sys
d = json.load(sys.stdin)
props = d.get('props', {}).get('picks', [])
if not props:
    print('NO_PICKS')
    sys.exit(0)

pick = props[0]
required = ['jarvis_rs', 'jarvis_active', 'jarvis_hits_count', 'jarvis_triggers_hit',
            'jarvis_reasons', 'jarvis_fail_reasons', 'jarvis_inputs_used']
missing = [f for f in required if f not in pick]

if missing:
    print('MISSING: ' + ', '.join(missing))
else:
    print('OK')
" 2>/dev/null || echo "ERROR")

if [ "$JARVIS_CHECK" = "OK" ] || [ "$JARVIS_CHECK" = "NO_PICKS" ]; then
    echo "${GREEN}✓ Jarvis transparency fields present${NC}"
elif [ "$JARVIS_CHECK" = "ERROR" ]; then
    echo "${RED}✗ FAIL: Could not validate Jarvis fields${NC}"
    exit 1
else
    echo "${RED}✗ FAIL: $JARVIS_CHECK${NC}"
    exit 1
fi
echo

# =============================================================================
# ALL CHECKS PASSED
# =============================================================================
echo "${GREEN}================================================${NC}"
echo "${GREEN}ALL RELEASE GATE CHECKS PASSED${NC}"
echo "${GREEN}✓ Safe to deploy${NC}"
echo "${GREEN}================================================${NC}"
exit 0
