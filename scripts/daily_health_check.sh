#!/bin/bash
# Daily Health Check Script for ai-betting-backend
# Run time: ~60 seconds
# Usage: ./scripts/daily_health_check.sh

set -e
cd "$(dirname "$0")/.."

echo "============================================"
echo "DAILY HEALTH CHECK - ai-betting-backend"
echo "============================================"
echo "Started: $(date)"
echo ""

ISSUES=0

# 1. Check for unused Python imports
echo "[1/6] Checking for unused imports..."
UNUSED_IMPORTS=$(grep -r "^import \|^from " --include="*.py" . 2>/dev/null | grep -v __pycache__ | grep -v ".pyc" | wc -l | tr -d ' ')
echo "      Total import statements: $UNUSED_IMPORTS"

# 2. Find duplicate function definitions
echo "[2/6] Checking for duplicate function names..."
DUPE_FUNCS=$(grep -rh "^def \|^async def " --include="*.py" . 2>/dev/null | grep -v __pycache__ | sort | uniq -d | head -5)
if [ -n "$DUPE_FUNCS" ]; then
    echo "      WARNING: Potential duplicate functions found:"
    echo "$DUPE_FUNCS" | while read line; do echo "        - $line"; done
    ISSUES=$((ISSUES + 1))
else
    echo "      OK - No duplicate function names"
fi

# 3. Find large files (>100KB)
echo "[3/6] Checking for large files (>100KB)..."
LARGE_FILES=$(find . -name "*.py" -size +100k -not -path "./.git/*" -not -path "./__pycache__/*" 2>/dev/null)
if [ -n "$LARGE_FILES" ]; then
    echo "      Large Python files found (consider splitting):"
    echo "$LARGE_FILES" | while read f; do
        SIZE=$(ls -lh "$f" | awk '{print $5}')
        echo "        - $f ($SIZE)"
    done
else
    echo "      OK - No oversized files"
fi

# 4. Find TODO/FIXME/HACK comments
echo "[4/6] Checking for TODO/FIXME/HACK comments..."
TODO_COUNT=$(grep -rn "TODO\|FIXME\|HACK\|XXX" --include="*.py" . 2>/dev/null | grep -v __pycache__ | wc -l | tr -d ' ')
if [ "$TODO_COUNT" -gt 0 ]; then
    echo "      Found $TODO_COUNT TODO/FIXME/HACK comments"
    echo "      Top 5:"
    grep -rn "TODO\|FIXME\|HACK\|XXX" --include="*.py" . 2>/dev/null | grep -v __pycache__ | head -5 | while read line; do
        echo "        - $line"
    done
else
    echo "      OK - No pending TODOs"
fi

# 5. Check for stale .pyc and __pycache__
echo "[5/6] Checking for stale cache files..."
CACHE_COUNT=$(find . -name "*.pyc" -o -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
if [ "$CACHE_COUNT" -gt 10 ]; then
    echo "      $CACHE_COUNT cache files/dirs found - consider cleanup"
else
    echo "      OK - Cache is minimal"
fi

# 6. Check for missing __init__.py
echo "[6/6] Checking package structure..."
MISSING_INIT=$(find . -type d -not -path "./.git/*" -not -path "./__pycache__/*" -not -path "./artifacts/*" -not -path "./docs/*" -not -name "." | while read dir; do
    if [ -n "$(find "$dir" -maxdepth 1 -name "*.py" 2>/dev/null)" ] && [ ! -f "$dir/__init__.py" ]; then
        echo "$dir"
    fi
done)
if [ -n "$MISSING_INIT" ]; then
    echo "      Directories with .py files but missing __init__.py:"
    echo "$MISSING_INIT" | head -5 | while read d; do echo "        - $d"; done
else
    echo "      OK - Package structure intact"
fi

echo ""
echo "============================================"
echo "QUICK STATS"
echo "============================================"
echo "Python files:    $(find . -name "*.py" -not -path "./.git/*" | wc -l | tr -d ' ')"
echo "Test files:      $(find ./tests -name "test_*.py" 2>/dev/null | wc -l | tr -d ' ')"
echo "Script files:    $(find ./scripts -name "*.sh" 2>/dev/null | wc -l | tr -d ' ')"
echo "Doc files:       $(find . -name "*.md" -not -path "./.git/*" | wc -l | tr -d ' ')"
echo ""

# Run existing sanity check if available
if [ -f "./scripts/daily_sanity_report.sh" ]; then
    echo "Running existing daily_sanity_report.sh..."
    ./scripts/daily_sanity_report.sh 2>/dev/null || true
fi

echo ""
echo "============================================"
echo "HEALTH CHECK COMPLETE"
echo "============================================"
echo "Finished: $(date)"
if [ "$ISSUES" -gt 0 ]; then
    echo "Issues found: $ISSUES (review above)"
    exit 1
else
    echo "Status: HEALTHY"
    exit 0
fi
