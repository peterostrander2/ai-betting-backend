#!/bin/bash
# Dependency Vulnerability Scan - Run pip-audit + npm audit
# Usage: ./scripts/dependency_vuln_scan.sh
# Cron: 0 10 * * 0 (weekly on Sunday at 10 AM)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$HOME/bookie-member-app"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/vuln_scan.log"

mkdir -p "$LOG_DIR"

echo "============================================" >> "$LOG_FILE"
echo "DEPENDENCY VULNERABILITY SCAN - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

ISSUES=0

# Python dependencies (pip-audit)
echo "" >> "$LOG_FILE"
echo "[PYTHON DEPENDENCIES - ai-betting-backend]" >> "$LOG_FILE"
cd "$PROJECT_DIR"

if command -v pip-audit &> /dev/null; then
    PIP_RESULT=$(pip-audit 2>&1 || true)
    if echo "$PIP_RESULT" | grep -q "No known vulnerabilities"; then
        echo "  ✅ No known vulnerabilities" >> "$LOG_FILE"
    else
        VULN_COUNT=$(echo "$PIP_RESULT" | grep -c "VULN" || echo "0")
        if [ "$VULN_COUNT" -gt 0 ]; then
            echo "  🔴 $VULN_COUNT vulnerabilities found:" >> "$LOG_FILE"
            echo "$PIP_RESULT" | grep "VULN" | head -10 | sed 's/^/    /' >> "$LOG_FILE"
            ISSUES=$((ISSUES + VULN_COUNT))
        else
            echo "  ✅ No vulnerabilities detected" >> "$LOG_FILE"
        fi
    fi
else
    echo "  ⚠️  pip-audit not installed. Install with: pip install pip-audit" >> "$LOG_FILE"

    # Fallback: check for known problematic packages
    echo "  Running basic package check..." >> "$LOG_FILE"
    if [ -f "requirements.txt" ]; then
        # Check for packages with known issues
        RISKY_PACKAGES=("pyyaml<5.4" "requests<2.20" "urllib3<1.26" "cryptography<3.3")
        for pkg in "${RISKY_PACKAGES[@]}"; do
            PKG_NAME=$(echo "$pkg" | cut -d'<' -f1)
            if grep -qi "$PKG_NAME" requirements.txt; then
                echo "    ⚠️  Found $PKG_NAME - verify version is current" >> "$LOG_FILE"
            fi
        done
    fi
fi

# Node.js dependencies (npm audit)
echo "" >> "$LOG_FILE"
echo "[NODE DEPENDENCIES - bookie-member-app]" >> "$LOG_FILE"
if [ -d "$FRONTEND_DIR" ]; then
    cd "$FRONTEND_DIR"

    if [ -f "package-lock.json" ]; then
        NPM_RESULT=$(npm audit --json 2>/dev/null || echo "{}")

        CRITICAL=$(echo "$NPM_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('metadata',{}).get('vulnerabilities',{}).get('critical',0))" 2>/dev/null || echo "0")
        HIGH=$(echo "$NPM_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('metadata',{}).get('vulnerabilities',{}).get('high',0))" 2>/dev/null || echo "0")
        MODERATE=$(echo "$NPM_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('metadata',{}).get('vulnerabilities',{}).get('moderate',0))" 2>/dev/null || echo "0")

        echo "  Critical: $CRITICAL" >> "$LOG_FILE"
        echo "  High: $HIGH" >> "$LOG_FILE"
        echo "  Moderate: $MODERATE" >> "$LOG_FILE"

        if [ "$CRITICAL" -gt 0 ] || [ "$HIGH" -gt 0 ]; then
            echo "  🔴 Security vulnerabilities need attention!" >> "$LOG_FILE"
            ISSUES=$((ISSUES + CRITICAL + HIGH))
        else
            echo "  ✅ No critical/high vulnerabilities" >> "$LOG_FILE"
        fi
    else
        echo "  ⚠️  No package-lock.json found" >> "$LOG_FILE"
    fi
else
    echo "  ⚠️  Frontend directory not found: $FRONTEND_DIR" >> "$LOG_FILE"
fi

# Check for outdated packages
echo "" >> "$LOG_FILE"
echo "[OUTDATED PACKAGES]" >> "$LOG_FILE"
cd "$PROJECT_DIR"
if command -v pip &> /dev/null; then
    OUTDATED=$(pip list --outdated 2>/dev/null | tail -n +3 | wc -l | tr -d ' ')
    echo "  Python packages with updates available: $OUTDATED" >> "$LOG_FILE"
fi

# Summary
echo "" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"
if [ "$ISSUES" -gt 0 ]; then
    echo "🔴 VULN SCAN: $ISSUES issues require attention" >> "$LOG_FILE"
else
    echo "✅ VULN SCAN: No critical vulnerabilities" >> "$LOG_FILE"
fi
echo "============================================" >> "$LOG_FILE"

tail -35 "$LOG_FILE"

exit $((ISSUES > 0 ? 1 : 0))
