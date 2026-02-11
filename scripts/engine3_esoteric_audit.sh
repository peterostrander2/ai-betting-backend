#!/usr/bin/env bash
#
# Engine 3 Esoteric Semantic Audit Shell Wrapper (v20.18)
#
# Runs static code checks + Python audit script for Engine 3 truthfulness.
# This wrapper verifies semantic truthfulness of Engine 3 output.
#
# Usage:
#     ./scripts/engine3_esoteric_audit.sh --local
#     API_KEY=xxx ./scripts/engine3_esoteric_audit.sh --production
#     API_KEY=xxx ./scripts/engine3_esoteric_audit.sh --local --production
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "ENGINE 3 ESOTERIC SEMANTIC AUDIT (v20.18)"
echo "=============================================="
echo ""

# Parse args
LOCAL_MODE=0
PRODUCTION_MODE=0

for arg in "$@"; do
    case $arg in
        --local)
            LOCAL_MODE=1
            ;;
        --production)
            PRODUCTION_MODE=1
            ;;
        *)
            ;;
    esac
done

# Default to local if no mode specified
if [[ $LOCAL_MODE -eq 0 && $PRODUCTION_MODE -eq 0 ]]; then
    LOCAL_MODE=1
fi

ERRORS=0

# =============================================================================
# STATIC CODE CHECKS
# =============================================================================

echo "=== STATIC CODE CHECKS ==="
echo ""

# 1. Check that NOAA uses contextvars for request-scoped proof
echo "[1/6] Checking NOAA contextvars pattern..."
if grep -q "contextvars.ContextVar.*noaa_request_proof" "$PROJECT_ROOT/alt_data_sources/noaa.py"; then
    echo -e "  ${GREEN}✓${NC} NOAA uses contextvars for request-local proof"
else
    echo -e "  ${RED}✗${NC} NOAA missing contextvars pattern"
    ERRORS=$((ERRORS + 1))
fi

# 2. Check that NOAA auth_context returns auth_type: "none"
echo ""
echo "[2/6] Checking NOAA auth_context pattern..."
if grep -q '"auth_type": "none"' "$PROJECT_ROOT/alt_data_sources/noaa.py"; then
    echo -e "  ${GREEN}✓${NC} NOAA auth_context has auth_type: 'none'"
else
    echo -e "  ${RED}✗${NC} NOAA auth_context missing auth_type: 'none'"
    ERRORS=$((ERRORS + 1))
fi

# Check that NOAA does NOT have key_present
if grep -q "key_present" "$PROJECT_ROOT/alt_data_sources/noaa.py"; then
    echo -e "  ${RED}✗${NC} NOAA has 'key_present' (should not for public API)"
    ERRORS=$((ERRORS + 1))
else
    echo -e "  ${GREEN}✓${NC} NOAA does not have 'key_present' (correct for public API)"
fi

# 3. Check that esoteric_engine has build_esoteric_breakdown_with_provenance
echo ""
echo "[3/6] Checking esoteric_engine provenance function..."
if grep -q "def build_esoteric_breakdown_with_provenance" "$PROJECT_ROOT/esoteric_engine.py"; then
    echo -e "  ${GREEN}✓${NC} esoteric_engine has build_esoteric_breakdown_with_provenance()"
else
    echo -e "  ${RED}✗${NC} esoteric_engine missing build_esoteric_breakdown_with_provenance()"
    ERRORS=$((ERRORS + 1))
fi

# 4. Check that debug endpoint exists
echo ""
echo "[4/6] Checking debug endpoint..."
if grep -q "/debug/esoteric-candidates" "$PROJECT_ROOT/live_data_router.py"; then
    echo -e "  ${GREEN}✓${NC} Debug endpoint /debug/esoteric-candidates exists"
else
    echo -e "  ${RED}✗${NC} Debug endpoint /debug/esoteric-candidates not found"
    ERRORS=$((ERRORS + 1))
fi

# 5. Check truth table exists with YAML block
echo ""
echo "[5/6] Checking truth table..."
if [[ -f "$PROJECT_ROOT/docs/ESOTERIC_TRUTH_TABLE.md" ]]; then
    if grep -q "wired_signals:" "$PROJECT_ROOT/docs/ESOTERIC_TRUTH_TABLE.md"; then
        WIRED_COUNT=$(grep -A 100 "wired_signals:" "$PROJECT_ROOT/docs/ESOTERIC_TRUTH_TABLE.md" | grep "^  - " | wc -l | tr -d ' ')
        echo -e "  ${GREEN}✓${NC} Truth table exists with YAML block ($WIRED_COUNT wired signals)"
    else
        echo -e "  ${YELLOW}⚠${NC} Truth table exists but missing YAML block"
    fi
else
    echo -e "  ${RED}✗${NC} Truth table not found at docs/ESOTERIC_TRUTH_TABLE.md"
    ERRORS=$((ERRORS + 1))
fi

# 6. Check that per-signal provenance fields are defined
echo ""
echo "[6/6] Checking per-signal provenance fields..."
REQUIRED_FIELDS=("value" "status" "source_api" "source_type" "raw_inputs_summary" "call_proof" "triggered" "contribution")
FOUND_FIELDS=0

for field in "${REQUIRED_FIELDS[@]}"; do
    if grep -q "\"$field\":" "$PROJECT_ROOT/esoteric_engine.py" 2>/dev/null; then
        FOUND_FIELDS=$((FOUND_FIELDS + 1))
    fi
done

if [[ $FOUND_FIELDS -ge 6 ]]; then
    echo -e "  ${GREEN}✓${NC} Per-signal provenance fields found ($FOUND_FIELDS/8 required fields)"
else
    echo -e "  ${YELLOW}⚠${NC} Some per-signal provenance fields may be missing ($FOUND_FIELDS/8)"
fi

echo ""
echo "=== STATIC CHECKS COMPLETE ==="
echo ""

# =============================================================================
# RUN PYTHON AUDIT
# =============================================================================

echo "=== PYTHON AUDIT ==="
echo ""

cd "$PROJECT_ROOT"

PYTHON_ERRORS=0

if [[ $LOCAL_MODE -eq 1 ]]; then
    echo "Running local audit..."
    if python3 scripts/engine3_esoteric_audit.py --local; then
        echo ""
        echo -e "${GREEN}✓${NC} Local audit passed"
    else
        PYTHON_ERRORS=$((PYTHON_ERRORS + 1))
        echo ""
        echo -e "${RED}✗${NC} Local audit failed"
    fi
fi

if [[ $PRODUCTION_MODE -eq 1 ]]; then
    echo ""
    echo "Running production audit..."

    if [[ -z "${API_KEY:-}" ]]; then
        echo -e "${RED}ERROR: API_KEY required for production audit${NC}"
        echo "Set API_KEY environment variable"
        PYTHON_ERRORS=$((PYTHON_ERRORS + 1))
    else
        if python3 scripts/engine3_esoteric_audit.py --production --api-key "$API_KEY"; then
            echo ""
            echo -e "${GREEN}✓${NC} Production audit passed"
        else
            PYTHON_ERRORS=$((PYTHON_ERRORS + 1))
            echo ""
            echo -e "${RED}✗${NC} Production audit failed"
        fi
    fi
fi

TOTAL_ERRORS=$((ERRORS + PYTHON_ERRORS))

echo ""
echo "=============================================="
if [[ $TOTAL_ERRORS -eq 0 ]]; then
    echo -e "${GREEN}ENGINE 3 SEMANTIC AUDIT: ALL CHECKS PASSED${NC}"
    exit 0
else
    echo -e "${RED}ENGINE 3 SEMANTIC AUDIT: $TOTAL_ERRORS CHECKS FAILED${NC}"
    echo ""
    echo "Static check errors: $ERRORS"
    echo "Python audit errors: $PYTHON_ERRORS"
    exit 1
fi
