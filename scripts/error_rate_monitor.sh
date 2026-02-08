#!/bin/bash
# Error Rate Monitor - Track 4xx/5xx rates from logs
# Usage: ./scripts/error_rate_monitor.sh
# Cron: 0 * * * * (every hour)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/error_rate.log"

# Thresholds
ERROR_RATE_WARN=5    # 5% error rate warning
ERROR_RATE_CRIT=10   # 10% error rate critical

mkdir -p "$LOG_DIR"

echo "============================================" >> "$LOG_FILE"
echo "ERROR RATE MONITOR - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

# Check Railway logs if available
if command -v railway &> /dev/null; then
    echo "[RAILWAY LOGS - Last Hour]" >> "$LOG_FILE"

    # Get recent logs
    LOGS=$(railway logs --json 2>/dev/null | tail -1000 || echo "")

    if [ -n "$LOGS" ]; then
        TOTAL=$(echo "$LOGS" | wc -l | tr -d ' ')
        ERRORS_5XX=$(echo "$LOGS" | grep -c '"status":5' || echo "0")
        ERRORS_4XX=$(echo "$LOGS" | grep -c '"status":4' || echo "0")

        if [ "$TOTAL" -gt 0 ]; then
            ERROR_RATE=$(echo "scale=2; ($ERRORS_5XX + $ERRORS_4XX) * 100 / $TOTAL" | bc)
            echo "  Total requests: $TOTAL" >> "$LOG_FILE"
            echo "  4xx errors: $ERRORS_4XX" >> "$LOG_FILE"
            echo "  5xx errors: $ERRORS_5XX" >> "$LOG_FILE"
            echo "  Error rate: ${ERROR_RATE}%" >> "$LOG_FILE"

            if (( $(echo "$ERROR_RATE > $ERROR_RATE_CRIT" | bc -l) )); then
                echo "  🔴 CRITICAL: Error rate exceeds ${ERROR_RATE_CRIT}%" >> "$LOG_FILE"
            elif (( $(echo "$ERROR_RATE > $ERROR_RATE_WARN" | bc -l) )); then
                echo "  🟡 WARNING: Error rate exceeds ${ERROR_RATE_WARN}%" >> "$LOG_FILE"
            else
                echo "  ✅ Error rate OK" >> "$LOG_FILE"
            fi
        fi
    else
        echo "  No logs available" >> "$LOG_FILE"
    fi
else
    echo "[RAILWAY CLI NOT INSTALLED]" >> "$LOG_FILE"
    echo "  Install with: npm i -g @railway/cli" >> "$LOG_FILE"
fi

# Check local log files if they exist
echo "" >> "$LOG_FILE"
echo "[LOCAL LOG FILES]" >> "$LOG_FILE"

for logfile in "$LOG_DIR"/*.log; do
    if [ -f "$logfile" ] && [ "$logfile" != "$LOG_FILE" ]; then
        BASENAME=$(basename "$logfile")
        ERRORS=$(grep -c -i "error\|exception\|failed\|traceback" "$logfile" 2>/dev/null || echo "0")
        LINES=$(wc -l < "$logfile" | tr -d ' ')
        echo "  $BASENAME: $ERRORS errors in $LINES lines" >> "$LOG_FILE"
    fi
done

echo "" >> "$LOG_FILE"

# Check for common error patterns in codebase
echo "[ERROR HANDLING COVERAGE]" >> "$LOG_FILE"
cd "$PROJECT_DIR"
TRY_BLOCKS=$(grep -rn "try:" --include="*.py" | grep -v test | grep -v __pycache__ | wc -l | tr -d ' ')
EXCEPT_BLOCKS=$(grep -rn "except" --include="*.py" | grep -v test | grep -v __pycache__ | wc -l | tr -d ' ')
BARE_EXCEPT=$(grep -rn "except:" --include="*.py" | grep -v test | grep -v __pycache__ | wc -l | tr -d ' ')

echo "  Try blocks: $TRY_BLOCKS" >> "$LOG_FILE"
echo "  Except blocks: $EXCEPT_BLOCKS" >> "$LOG_FILE"
if [ "$BARE_EXCEPT" -gt 0 ]; then
    echo "  ⚠️  Bare except clauses: $BARE_EXCEPT (consider specific exceptions)" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
tail -30 "$LOG_FILE"
