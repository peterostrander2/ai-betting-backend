#!/bin/bash
# Access Log Audit - Detect unusual API access patterns
# Usage: ./scripts/access_log_audit.sh
# Cron: 0 6 * * * (daily at 6 AM)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/access_audit.log"

# Thresholds
MAX_REQUESTS_PER_IP=1000      # Per hour
MAX_FAILED_AUTH=50            # Failed auth attempts
SUSPICIOUS_PATHS=("/admin" "/.env" "/config" "/debug" "/.git" "/wp-admin" "/phpmyadmin")

mkdir -p "$LOG_DIR"

echo "============================================" >> "$LOG_FILE"
echo "ACCESS LOG AUDIT - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

ISSUES=0

# Check Railway logs if available
echo "[API ACCESS PATTERNS]" >> "$LOG_FILE"
if command -v railway &> /dev/null; then
    echo "  Fetching Railway logs..." >> "$LOG_FILE"

    # Get logs from last hour
    LOGS=$(railway logs 2>/dev/null | head -500 || echo "")

    if [ -n "$LOGS" ]; then
        # Look for repeated IPs (potential abuse)
        echo "" >> "$LOG_FILE"
        echo "  [TOP REQUEST SOURCES]" >> "$LOG_FILE"
        IP_COUNTS=$(echo "$LOGS" | grep -oE "\b([0-9]{1,3}\.){3}[0-9]{1,3}\b" | sort | uniq -c | sort -rn | head -5)
        if [ -n "$IP_COUNTS" ]; then
            echo "$IP_COUNTS" | while read count ip; do
                if [ "$count" -gt "$MAX_REQUESTS_PER_IP" ]; then
                    echo "    🔴 $ip: $count requests (POTENTIAL ABUSE)" >> "$LOG_FILE"
                    ISSUES=$((ISSUES + 1))
                else
                    echo "    $ip: $count requests" >> "$LOG_FILE"
                fi
            done
        fi

        # Look for failed authentication
        echo "" >> "$LOG_FILE"
        echo "  [AUTHENTICATION FAILURES]" >> "$LOG_FILE"
        AUTH_FAILS=$(echo "$LOGS" | grep -ci "401\|403\|unauthorized\|forbidden" || echo "0")
        if [ "$AUTH_FAILS" -gt "$MAX_FAILED_AUTH" ]; then
            echo "    🔴 $AUTH_FAILS failed auth attempts (threshold: $MAX_FAILED_AUTH)" >> "$LOG_FILE"
            ISSUES=$((ISSUES + 1))
        else
            echo "    ✅ $AUTH_FAILS failed auth attempts" >> "$LOG_FILE"
        fi

        # Look for suspicious path access
        echo "" >> "$LOG_FILE"
        echo "  [SUSPICIOUS PATH ACCESS]" >> "$LOG_FILE"
        for path in "${SUSPICIOUS_PATHS[@]}"; do
            HITS=$(echo "$LOGS" | grep -c "$path" || echo "0")
            if [ "$HITS" -gt 0 ]; then
                echo "    ⚠️  $path: $HITS attempts" >> "$LOG_FILE"
            fi
        done

        # Look for SQL injection attempts
        echo "" >> "$LOG_FILE"
        echo "  [INJECTION ATTEMPTS]" >> "$LOG_FILE"
        SQL_PATTERNS="SELECT|UNION|INSERT|DELETE|DROP|--"
        INJECTION_ATTEMPTS=$(echo "$LOGS" | grep -ciE "$SQL_PATTERNS" || echo "0")
        if [ "$INJECTION_ATTEMPTS" -gt 10 ]; then
            echo "    🔴 $INJECTION_ATTEMPTS potential SQL injection attempts" >> "$LOG_FILE"
            ISSUES=$((ISSUES + 1))
        else
            echo "    ✅ No significant injection patterns detected" >> "$LOG_FILE"
        fi
    else
        echo "  No logs available from Railway" >> "$LOG_FILE"
    fi
else
    echo "  Railway CLI not installed - skipping remote log analysis" >> "$LOG_FILE"
fi

# Check local access logs if any
echo "" >> "$LOG_FILE"
echo "[LOCAL ACCESS LOGS]" >> "$LOG_FILE"
if [ -f "$LOG_DIR/access.log" ]; then
    UNIQUE_IPS=$(cut -d' ' -f1 "$LOG_DIR/access.log" 2>/dev/null | sort -u | wc -l | tr -d ' ')
    TOTAL_REQUESTS=$(wc -l < "$LOG_DIR/access.log" | tr -d ' ')
    echo "  Total requests: $TOTAL_REQUESTS" >> "$LOG_FILE"
    echo "  Unique IPs: $UNIQUE_IPS" >> "$LOG_FILE"
else
    echo "  No local access.log found" >> "$LOG_FILE"
fi

# Rate limiting check
echo "" >> "$LOG_FILE"
echo "[RATE LIMITING STATUS]" >> "$LOG_FILE"
cd "$PROJECT_DIR"
if grep -rq "RateLimiter\|slowapi\|rate.limit" --include="*.py" 2>/dev/null; then
    echo "  ✅ Rate limiting appears to be configured" >> "$LOG_FILE"
else
    echo "  ⚠️  No rate limiting detected in codebase" >> "$LOG_FILE"
fi

# Summary
echo "" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"
if [ "$ISSUES" -gt 0 ]; then
    echo "⚠️  ACCESS AUDIT: $ISSUES security concerns found" >> "$LOG_FILE"
else
    echo "✅ ACCESS AUDIT: No unusual patterns detected" >> "$LOG_FILE"
fi
echo "============================================" >> "$LOG_FILE"

tail -40 "$LOG_FILE"

exit $ISSUES
