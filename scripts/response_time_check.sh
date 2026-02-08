#!/bin/bash
# Response Time Check - Monitor API latency, flag slow endpoints
# Usage: ./scripts/response_time_check.sh
# Cron: */30 * * * * (every 30 minutes)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/response_times.log"

API_URL="${API_URL:-https://web-production-7b2a.up.railway.app}"
SLOW_THRESHOLD_MS=2000
CRITICAL_THRESHOLD_MS=5000

mkdir -p "$LOG_DIR"

echo "============================================" >> "$LOG_FILE"
echo "RESPONSE TIME CHECK - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"
echo "Target: $API_URL" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

ISSUES=0

# Endpoints to check with expected max response times
declare -A ENDPOINTS
ENDPOINTS["/health"]=500
ENDPOINTS["/esoteric/today-energy"]=3000
ENDPOINTS["/best-bets"]=5000
ENDPOINTS["/api/games"]=3000

for endpoint in "${!ENDPOINTS[@]}"; do
    EXPECTED_MAX=${ENDPOINTS[$endpoint]}

    # Measure response time
    START=$(date +%s%N)
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$API_URL$endpoint" 2>/dev/null || echo "000")
    END=$(date +%s%N)

    DURATION_MS=$(( (END - START) / 1000000 ))

    if [ "$HTTP_CODE" = "000" ]; then
        echo "  ❌ $endpoint: TIMEOUT/UNREACHABLE" >> "$LOG_FILE"
        ISSUES=$((ISSUES + 1))
    elif [ "$HTTP_CODE" != "200" ]; then
        echo "  ❌ $endpoint: HTTP $HTTP_CODE (${DURATION_MS}ms)" >> "$LOG_FILE"
        ISSUES=$((ISSUES + 1))
    elif [ "$DURATION_MS" -gt "$CRITICAL_THRESHOLD_MS" ]; then
        echo "  🔴 $endpoint: ${DURATION_MS}ms CRITICAL (>${CRITICAL_THRESHOLD_MS}ms)" >> "$LOG_FILE"
        ISSUES=$((ISSUES + 1))
    elif [ "$DURATION_MS" -gt "$EXPECTED_MAX" ]; then
        echo "  🟡 $endpoint: ${DURATION_MS}ms SLOW (expected <${EXPECTED_MAX}ms)" >> "$LOG_FILE"
    else
        echo "  ✅ $endpoint: ${DURATION_MS}ms" >> "$LOG_FILE"
    fi
done

echo "" >> "$LOG_FILE"

# Summary
if [ "$ISSUES" -gt 0 ]; then
    echo "⚠️  $ISSUES endpoint(s) need attention" >> "$LOG_FILE"
else
    echo "✅ All endpoints responding within thresholds" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"

# Show results
tail -20 "$LOG_FILE"

exit $ISSUES
