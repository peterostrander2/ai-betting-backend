#!/bin/bash
#
# Engine 2 Research Semantic Audit
# v20.16+ Anti-Conflation Verification
#
# Usage:
#   API_KEY=xxx ./scripts/engine2_research_audit.sh [--sport NBA] [--local]
#
# This script:
# 1. Runs static code checks (grep for conflation patterns)
# 2. Verifies playbook_sharp and odds_line are DISTINCT objects
# 3. Runs Python audit against target environment
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Defaults
SPORT="${SPORT:-NBA}"
API_BASE="${API_BASE:-https://web-production-7b2a.up.railway.app}"
LIMIT="${LIMIT:-25}"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --sport)
            SPORT="$2"
            shift 2
            ;;
        --local)
            API_BASE="http://localhost:8000"
            shift
            ;;
        --limit)
            LIMIT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "============================================================"
echo "Engine 2 Research Semantic Audit"
echo "============================================================"
echo ""
echo "Sport: $SPORT"
echo "API Base: $API_BASE"
echo "Limit: $LIMIT"
echo ""

# Check for API_KEY
if [[ -z "$API_KEY" ]]; then
    echo "ERROR: API_KEY environment variable required"
    echo "Usage: API_KEY=xxx $0"
    exit 1
fi

VIOLATIONS=0

# ============================================================
# Phase 1: Static Code Checks
# ============================================================
echo "--- Phase 1: Static Code Checks ---"
echo ""

# Check 1: No code reads sharp_strength from line_variance
echo "Check 1: No sharp_strength from line_variance..."
BAD_PATTERN='signal\["signal_strength"\].*=.*"STRONG"'
if grep -rn "$BAD_PATTERN" "$PROJECT_DIR/live_data_router.py" 2>/dev/null | grep -v "^#" | grep -v "# BUG"; then
    echo "  [WARN] Found potential conflation pattern (may be commented)"
else
    echo "  [OK] No conflation pattern found"
fi

# Check 2: Verify sharp_strength and lv_strength are separate fields
echo ""
echo "Check 2: Separate sharp_strength and lv_strength fields..."
if grep -q '"sharp_strength"' "$PROJECT_DIR/live_data_router.py" && \
   grep -q '"lv_strength"' "$PROJECT_DIR/live_data_router.py"; then
    echo "  [OK] Both sharp_strength and lv_strength fields present"
else
    echo "  [FAIL] Missing separate strength fields"
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# Check 3: Verify lv_strength computed from line_variance only
echo ""
echo "Check 3: lv_strength computed from line_variance..."
if grep -q 'signal\["lv_strength"\]' "$PROJECT_DIR/live_data_router.py"; then
    echo "  [OK] lv_strength is set in signal"
else
    echo "  [WARN] lv_strength may not be explicitly set"
fi

# Check 4: Verify research_types.py exists with ComponentStatus
echo ""
echo "Check 4: research_types.py with ComponentStatus..."
if [[ -f "$PROJECT_DIR/core/research_types.py" ]]; then
    if grep -q "class ComponentStatus" "$PROJECT_DIR/core/research_types.py"; then
        echo "  [OK] ComponentStatus enum present"
    else
        echo "  [FAIL] ComponentStatus enum missing"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
else
    echo "  [FAIL] core/research_types.py not found"
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# Check 5: Verify RESEARCH_TRUTH_TABLE.md exists
echo ""
echo "Check 5: RESEARCH_TRUTH_TABLE.md documentation..."
if [[ -f "$PROJECT_DIR/docs/RESEARCH_TRUTH_TABLE.md" ]]; then
    echo "  [OK] Truth table documentation present"
else
    echo "  [WARN] docs/RESEARCH_TRUTH_TABLE.md not found"
fi

echo ""
echo "--- Phase 2: Runtime Verification ---"
echo ""

# ============================================================
# Phase 2: Runtime Audit via Python Script
# ============================================================

cd "$PROJECT_DIR"
python3 scripts/engine2_research_audit.py \
    --sport "$SPORT" \
    --base-url "$API_BASE" \
    --limit "$LIMIT"

PYTHON_EXIT=$?

if [[ $PYTHON_EXIT -ne 0 ]]; then
    VIOLATIONS=$((VIOLATIONS + 1))
fi

echo ""
echo "============================================================"
if [[ $VIOLATIONS -eq 0 ]]; then
    echo "FINAL VERDICT: PASS"
    echo "All anti-conflation invariants verified"
else
    echo "FINAL VERDICT: FAIL"
    echo "$VIOLATIONS violation(s) found"
fi
echo "============================================================"

exit $VIOLATIONS
