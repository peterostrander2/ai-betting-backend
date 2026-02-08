#!/bin/bash
# Database Integrity Check - Verify data consistency
# Usage: ./scripts/db_integrity_check.sh
# Cron: 0 4 * * * (daily at 4 AM)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/db_integrity.log"
DATA_DIR="${DATA_DIR:-$PROJECT_DIR/data}"

mkdir -p "$LOG_DIR"

echo "============================================" >> "$LOG_FILE"
echo "DB INTEGRITY CHECK - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

ISSUES=0

# Check JSON files for validity
echo "[JSON FILE INTEGRITY]" >> "$LOG_FILE"
if [ -d "$DATA_DIR" ]; then
    for json_file in "$DATA_DIR"/*.json; do
        if [ -f "$json_file" ]; then
            BASENAME=$(basename "$json_file")
            if python3 -c "import json; json.load(open('$json_file'))" 2>/dev/null; then
                SIZE=$(du -h "$json_file" | cut -f1)
                echo "  ✅ $BASENAME ($SIZE)" >> "$LOG_FILE"
            else
                echo "  ❌ $BASENAME - INVALID JSON" >> "$LOG_FILE"
                ISSUES=$((ISSUES + 1))
            fi
        fi
    done
else
    echo "  No data directory found at $DATA_DIR" >> "$LOG_FILE"
fi

# Check SQLite databases if any
echo "" >> "$LOG_FILE"
echo "[SQLITE DATABASES]" >> "$LOG_FILE"
SQLITE_FILES=$(find "$PROJECT_DIR" -name "*.db" -o -name "*.sqlite" 2>/dev/null | grep -v __pycache__ || true)
if [ -n "$SQLITE_FILES" ]; then
    for db_file in $SQLITE_FILES; do
        BASENAME=$(basename "$db_file")
        if sqlite3 "$db_file" "PRAGMA integrity_check;" 2>/dev/null | grep -q "ok"; then
            SIZE=$(du -h "$db_file" | cut -f1)
            echo "  ✅ $BASENAME ($SIZE)" >> "$LOG_FILE"
        else
            echo "  ❌ $BASENAME - INTEGRITY CHECK FAILED" >> "$LOG_FILE"
            ISSUES=$((ISSUES + 1))
        fi
    done
else
    echo "  No SQLite databases found" >> "$LOG_FILE"
fi

# Check pickle files
echo "" >> "$LOG_FILE"
echo "[PICKLE FILES]" >> "$LOG_FILE"
PICKLE_FILES=$(find "$PROJECT_DIR" -name "*.pkl" -o -name "*.pickle" 2>/dev/null | grep -v __pycache__ || true)
if [ -n "$PICKLE_FILES" ]; then
    for pkl_file in $PICKLE_FILES; do
        BASENAME=$(basename "$pkl_file")
        if python3 -c "import pickle; pickle.load(open('$pkl_file', 'rb'))" 2>/dev/null; then
            SIZE=$(du -h "$pkl_file" | cut -f1)
            echo "  ✅ $BASENAME ($SIZE)" >> "$LOG_FILE"
        else
            echo "  ❌ $BASENAME - CANNOT LOAD" >> "$LOG_FILE"
            ISSUES=$((ISSUES + 1))
        fi
    done
else
    echo "  No pickle files found" >> "$LOG_FILE"
fi

# Check for orphaned cache entries
echo "" >> "$LOG_FILE"
echo "[CACHE CONSISTENCY]" >> "$LOG_FILE"
CACHE_DIRS=$(find "$PROJECT_DIR" -type d -name "*cache*" 2>/dev/null | grep -v __pycache__ | grep -v ".git" || true)
for cache_dir in $CACHE_DIRS; do
    FILE_COUNT=$(find "$cache_dir" -type f 2>/dev/null | wc -l | tr -d ' ')
    DIR_SIZE=$(du -sh "$cache_dir" 2>/dev/null | cut -f1)
    echo "  $cache_dir: $FILE_COUNT files ($DIR_SIZE)" >> "$LOG_FILE"
done

# Summary
echo "" >> "$LOG_FILE"
if [ "$ISSUES" -gt 0 ]; then
    echo "❌ INTEGRITY CHECK FAILED: $ISSUES issues found" >> "$LOG_FILE"
else
    echo "✅ INTEGRITY CHECK PASSED" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
tail -30 "$LOG_FILE"

exit $ISSUES
