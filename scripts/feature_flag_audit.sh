#!/bin/bash
# Feature Flag Audit - List active flags, find stale ones
# Usage: ./scripts/feature_flag_audit.sh
# Cron: 0 9 * * 1 (weekly on Monday at 9 AM)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/feature_flags.log"

# How old before a flag is considered stale (days)
STALE_THRESHOLD_DAYS=30

mkdir -p "$LOG_DIR"

echo "============================================" >> "$LOG_FILE"
echo "FEATURE FLAG AUDIT - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

cd "$PROJECT_DIR"

# Common feature flag patterns
FLAG_PATTERNS=(
    "FEATURE_"
    "ENABLE_"
    "USE_"
    "FLAG_"
    "TOGGLE_"
    "EXPERIMENT_"
    "is_enabled"
    "feature_enabled"
)

echo "" >> "$LOG_FILE"
echo "[FEATURE FLAGS IN CODE]" >> "$LOG_FILE"

TOTAL_FLAGS=0
for pattern in "${FLAG_PATTERNS[@]}"; do
    FLAGS=$(grep -rn "$pattern" --include="*.py" --include="*.env*" . 2>/dev/null | \
            grep -v __pycache__ | grep -v ".git" | grep -v tests || true)

    if [ -n "$FLAGS" ]; then
        COUNT=$(echo "$FLAGS" | wc -l | tr -d ' ')
        TOTAL_FLAGS=$((TOTAL_FLAGS + COUNT))
        echo "  Pattern '$pattern': $COUNT occurrences" >> "$LOG_FILE"
    fi
done

echo "  Total flag references: $TOTAL_FLAGS" >> "$LOG_FILE"

# List all unique flags
echo "" >> "$LOG_FILE"
echo "[UNIQUE FLAGS FOUND]" >> "$LOG_FILE"
UNIQUE_FLAGS=$(grep -rohE "(FEATURE_|ENABLE_|USE_|FLAG_)[A-Z_]+" --include="*.py" --include="*.env*" . 2>/dev/null | \
               grep -v __pycache__ | sort -u || true)

if [ -n "$UNIQUE_FLAGS" ]; then
    echo "$UNIQUE_FLAGS" | while read -r flag; do
        # Count usages
        USAGE=$(grep -rn "$flag" --include="*.py" . 2>/dev/null | grep -v __pycache__ | wc -l | tr -d ' ')
        echo "  $flag (used $USAGE times)" >> "$LOG_FILE"
    done
else
    echo "  No feature flags found" >> "$LOG_FILE"
fi

# Check .env files for flags
echo "" >> "$LOG_FILE"
echo "[FLAGS IN ENVIRONMENT]" >> "$LOG_FILE"
for env_file in .env .env.local .env.production; do
    if [ -f "$env_file" ]; then
        ENV_FLAGS=$(grep -E "^(FEATURE_|ENABLE_|USE_|FLAG_)" "$env_file" 2>/dev/null || true)
        if [ -n "$ENV_FLAGS" ]; then
            echo "  $env_file:" >> "$LOG_FILE"
            echo "$ENV_FLAGS" | sed 's/^/    /' >> "$LOG_FILE"
        fi
    fi
done

# Check Railway environment if available
if command -v railway &> /dev/null; then
    echo "" >> "$LOG_FILE"
    echo "[RAILWAY ENV FLAGS]" >> "$LOG_FILE"
    RAILWAY_FLAGS=$(railway variables 2>/dev/null | grep -E "(FEATURE_|ENABLE_|USE_|FLAG_)" || true)
    if [ -n "$RAILWAY_FLAGS" ]; then
        echo "$RAILWAY_FLAGS" | sed 's/^/    /' >> "$LOG_FILE"
    else
        echo "  No feature flags in Railway env" >> "$LOG_FILE"
    fi
fi

# Find potentially stale flags (defined but never actually checked)
echo "" >> "$LOG_FILE"
echo "[POTENTIALLY STALE FLAGS]" >> "$LOG_FILE"
STALE_COUNT=0

if [ -n "$UNIQUE_FLAGS" ]; then
    echo "$UNIQUE_FLAGS" | while read -r flag; do
        # Check if flag is used in conditionals
        CONDITIONAL_USE=$(grep -rn "if.*$flag\|$flag.*:" --include="*.py" . 2>/dev/null | \
                          grep -v __pycache__ | grep -v "^#" | wc -l | tr -d ' ')

        if [ "$CONDITIONAL_USE" -eq 0 ]; then
            echo "  ⚠️  $flag - defined but never checked conditionally" >> "$LOG_FILE"
        fi
    done
fi

# Check for TODO/FIXME near flags
echo "" >> "$LOG_FILE"
echo "[FLAGS WITH TODO COMMENTS]" >> "$LOG_FILE"
TODO_FLAGS=$(grep -rn -B2 -A2 "FEATURE_\|ENABLE_\|FLAG_" --include="*.py" . 2>/dev/null | \
             grep -i "TODO\|FIXME\|HACK\|REMOVE" | head -5 || true)
if [ -n "$TODO_FLAGS" ]; then
    echo "$TODO_FLAGS" | sed 's/^/  /' >> "$LOG_FILE"
else
    echo "  ✅ No TODOs found near feature flags" >> "$LOG_FILE"
fi

# Summary
echo "" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"
echo "Recommendation: Review flags quarterly and remove unused ones" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

tail -50 "$LOG_FILE"
