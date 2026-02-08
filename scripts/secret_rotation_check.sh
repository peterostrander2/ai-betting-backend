#!/bin/bash
# Secret Rotation Check - Alert on old API keys/tokens
# Usage: ./scripts/secret_rotation_check.sh
# Cron: 0 9 * * 1 (weekly on Monday at 9 AM)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/secret_rotation.log"

# How old is too old (days)
ROTATION_WARN_DAYS=60
ROTATION_CRIT_DAYS=90

mkdir -p "$LOG_DIR"

echo "============================================" >> "$LOG_FILE"
echo "SECRET ROTATION CHECK - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

ISSUES=0

# Check .env file age
echo "[ENV FILE AGE]" >> "$LOG_FILE"
ENV_FILES=(".env" ".env.local" ".env.production")
for env_file in "${ENV_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$env_file" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            FILE_AGE_DAYS=$(( ($(date +%s) - $(stat -f %m "$PROJECT_DIR/$env_file")) / 86400 ))
        else
            FILE_AGE_DAYS=$(( ($(date +%s) - $(stat -c %Y "$PROJECT_DIR/$env_file")) / 86400 ))
        fi

        if [ "$FILE_AGE_DAYS" -gt "$ROTATION_CRIT_DAYS" ]; then
            echo "  🔴 $env_file: $FILE_AGE_DAYS days old (ROTATE NOW)" >> "$LOG_FILE"
            ISSUES=$((ISSUES + 1))
        elif [ "$FILE_AGE_DAYS" -gt "$ROTATION_WARN_DAYS" ]; then
            echo "  🟡 $env_file: $FILE_AGE_DAYS days old (consider rotating)" >> "$LOG_FILE"
        else
            echo "  ✅ $env_file: $FILE_AGE_DAYS days old" >> "$LOG_FILE"
        fi
    fi
done

# Check for hardcoded secrets in code (security scan)
echo "" >> "$LOG_FILE"
echo "[HARDCODED SECRET SCAN]" >> "$LOG_FILE"

cd "$PROJECT_DIR"
HARDCODED_SECRETS=""

# Look for common secret patterns
PATTERNS=(
    "api[_-]?key\s*=\s*['\"][a-zA-Z0-9]"
    "secret[_-]?key\s*=\s*['\"][a-zA-Z0-9]"
    "password\s*=\s*['\"][^'\"]*['\"]"
    "token\s*=\s*['\"][a-zA-Z0-9]"
    "Bearer\s+[a-zA-Z0-9._-]+"
)

for pattern in "${PATTERNS[@]}"; do
    MATCHES=$(grep -rniE "$pattern" --include="*.py" --include="*.js" --include="*.ts" 2>/dev/null | grep -v test | grep -v __pycache__ | grep -v node_modules | grep -v ".env" | head -5 || true)
    if [ -n "$MATCHES" ]; then
        HARDCODED_SECRETS="${HARDCODED_SECRETS}${MATCHES}\n"
    fi
done

if [ -n "$HARDCODED_SECRETS" ]; then
    echo "  ⚠️  Potential hardcoded secrets found:" >> "$LOG_FILE"
    echo -e "$HARDCODED_SECRETS" | head -10 | sed 's/^/    /' >> "$LOG_FILE"
    ISSUES=$((ISSUES + 1))
else
    echo "  ✅ No obvious hardcoded secrets found" >> "$LOG_FILE"
fi

# Check for exposed .env in git
echo "" >> "$LOG_FILE"
echo "[GIT SECRET EXPOSURE]" >> "$LOG_FILE"
if git ls-files | grep -q "\.env$"; then
    echo "  🔴 .env file is tracked in git!" >> "$LOG_FILE"
    ISSUES=$((ISSUES + 1))
else
    echo "  ✅ .env files not tracked in git" >> "$LOG_FILE"
fi

# Check .gitignore includes secrets
if [ -f "$PROJECT_DIR/.gitignore" ]; then
    if grep -q "\.env" "$PROJECT_DIR/.gitignore"; then
        echo "  ✅ .env in .gitignore" >> "$LOG_FILE"
    else
        echo "  ⚠️  .env not in .gitignore" >> "$LOG_FILE"
    fi
fi

# Railway environment variables (if CLI available)
echo "" >> "$LOG_FILE"
echo "[RAILWAY SECRETS]" >> "$LOG_FILE"
if command -v railway &> /dev/null; then
    echo "  Run 'railway variables' manually to audit production secrets" >> "$LOG_FILE"
else
    echo "  Railway CLI not installed" >> "$LOG_FILE"
fi

# Summary
echo "" >> "$LOG_FILE"
if [ "$ISSUES" -gt 0 ]; then
    echo "⚠️  SECRET ROTATION: $ISSUES issues need attention" >> "$LOG_FILE"
else
    echo "✅ SECRET ROTATION: All checks passed" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
tail -30 "$LOG_FILE"

exit $ISSUES
