#!/bin/bash
# Test Coverage Report - Generate coverage %, flag uncovered code
# Usage: ./scripts/test_coverage_report.sh
# Cron: 0 8 * * 1 (weekly on Monday at 8 AM)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/test_coverage.log"
COVERAGE_DIR="$PROJECT_DIR/htmlcov"

# Thresholds
MIN_COVERAGE=70
WARN_COVERAGE=80

mkdir -p "$LOG_DIR"

echo "============================================" >> "$LOG_FILE"
echo "TEST COVERAGE REPORT - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

cd "$PROJECT_DIR"

# Check if pytest-cov is available
if ! python3 -c "import pytest_cov" 2>/dev/null; then
    echo "Installing pytest-cov..." >> "$LOG_FILE"
    pip install pytest-cov --quiet 2>/dev/null || true
fi

# Run tests with coverage
echo "" >> "$LOG_FILE"
echo "[RUNNING TESTS WITH COVERAGE]" >> "$LOG_FILE"
echo "This may take a few minutes..." >> "$LOG_FILE"

COVERAGE_OUTPUT=$(python3 -m pytest tests/ --cov=. --cov-report=term-missing --cov-report=html -q 2>&1 || true)

# Extract coverage percentage
TOTAL_COVERAGE=$(echo "$COVERAGE_OUTPUT" | grep "TOTAL" | awk '{print $NF}' | tr -d '%' || echo "0")

echo "" >> "$LOG_FILE"
echo "[COVERAGE SUMMARY]" >> "$LOG_FILE"
echo "$COVERAGE_OUTPUT" | grep -E "^(TOTAL|Name|---|[a-zA-Z_/]+\.py)" | head -30 >> "$LOG_FILE"

echo "" >> "$LOG_FILE"
echo "[COVERAGE RESULT]" >> "$LOG_FILE"
if [ -n "$TOTAL_COVERAGE" ] && [ "$TOTAL_COVERAGE" != "0" ]; then
    if [ "$TOTAL_COVERAGE" -lt "$MIN_COVERAGE" ]; then
        echo "  🔴 Coverage: ${TOTAL_COVERAGE}% (BELOW MINIMUM ${MIN_COVERAGE}%)" >> "$LOG_FILE"
    elif [ "$TOTAL_COVERAGE" -lt "$WARN_COVERAGE" ]; then
        echo "  🟡 Coverage: ${TOTAL_COVERAGE}% (below target ${WARN_COVERAGE}%)" >> "$LOG_FILE"
    else
        echo "  ✅ Coverage: ${TOTAL_COVERAGE}%" >> "$LOG_FILE"
    fi
else
    echo "  ⚠️  Could not determine coverage percentage" >> "$LOG_FILE"
fi

# Find files with zero coverage
echo "" >> "$LOG_FILE"
echo "[FILES WITH LOW/NO COVERAGE]" >> "$LOG_FILE"
echo "$COVERAGE_OUTPUT" | grep -E "^\S+\.py\s+[0-9]+\s+[0-9]+\s+[0-9]+%" | awk '$NF ~ /^[0-3][0-9]%$/ || $NF == "0%" {print "  ⚠️  " $1 ": " $NF}' | head -15 >> "$LOG_FILE"

# Critical files that should have high coverage
echo "" >> "$LOG_FILE"
echo "[CRITICAL FILE COVERAGE]" >> "$LOG_FILE"
CRITICAL_FILES=("scoring_contract.py" "tiering.py" "best_bets_router.py" "main.py")
for file in "${CRITICAL_FILES[@]}"; do
    FILE_COV=$(echo "$COVERAGE_OUTPUT" | grep "$file" | awk '{print $NF}' || echo "N/A")
    if [ -n "$FILE_COV" ] && [ "$FILE_COV" != "N/A" ]; then
        echo "  $file: $FILE_COV" >> "$LOG_FILE"
    fi
done

# Test results summary
echo "" >> "$LOG_FILE"
echo "[TEST RESULTS]" >> "$LOG_FILE"
PASSED=$(echo "$COVERAGE_OUTPUT" | grep -oE "[0-9]+ passed" | head -1 || echo "0 passed")
FAILED=$(echo "$COVERAGE_OUTPUT" | grep -oE "[0-9]+ failed" | head -1 || echo "0 failed")
ERRORS=$(echo "$COVERAGE_OUTPUT" | grep -oE "[0-9]+ error" | head -1 || echo "0 errors")
echo "  $PASSED, $FAILED, $ERRORS" >> "$LOG_FILE"

echo "" >> "$LOG_FILE"
echo "HTML report available at: $COVERAGE_DIR/index.html" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

tail -40 "$LOG_FILE"
