#!/bin/bash
# Prune Old Data - Clean up stale predictions, old logs
# Usage: ./scripts/prune_old_data.sh
# Cron: 0 5 * * 0 (weekly on Sunday at 5 AM)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/prune.log"

# Retention periods
LOG_RETENTION_DAYS=30
CACHE_RETENTION_DAYS=7
BACKUP_RETENTION_DAYS=14

mkdir -p "$LOG_DIR"

echo "============================================" >> "$LOG_FILE"
echo "PRUNE OLD DATA - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

FREED_SPACE=0

# Prune old log files
echo "[LOG FILES]" >> "$LOG_FILE"
OLD_LOGS=$(find "$LOG_DIR" -name "*.log" -mtime +$LOG_RETENTION_DAYS 2>/dev/null || true)
if [ -n "$OLD_LOGS" ]; then
    for logfile in $OLD_LOGS; do
        SIZE=$(du -k "$logfile" | cut -f1)
        FREED_SPACE=$((FREED_SPACE + SIZE))
        echo "  Removing: $(basename "$logfile") (${SIZE}KB)" >> "$LOG_FILE"
        rm -f "$logfile"
    done
else
    echo "  No logs older than $LOG_RETENTION_DAYS days" >> "$LOG_FILE"
fi

# Truncate large log files (keep last 10000 lines)
echo "" >> "$LOG_FILE"
echo "[TRUNCATING LARGE LOGS]" >> "$LOG_FILE"
for logfile in "$LOG_DIR"/*.log; do
    if [ -f "$logfile" ]; then
        LINES=$(wc -l < "$logfile" | tr -d ' ')
        if [ "$LINES" -gt 10000 ]; then
            echo "  Truncating $(basename "$logfile"): $LINES -> 10000 lines" >> "$LOG_FILE"
            tail -10000 "$logfile" > "${logfile}.tmp" && mv "${logfile}.tmp" "$logfile"
        fi
    fi
done

# Prune cache directories
echo "" >> "$LOG_FILE"
echo "[CACHE FILES]" >> "$LOG_FILE"
CACHE_DIRS=$(find "$PROJECT_DIR" -type d -name "*cache*" 2>/dev/null | grep -v __pycache__ | grep -v ".git" || true)
for cache_dir in $CACHE_DIRS; do
    OLD_CACHE=$(find "$cache_dir" -type f -mtime +$CACHE_RETENTION_DAYS 2>/dev/null || true)
    if [ -n "$OLD_CACHE" ]; then
        COUNT=$(echo "$OLD_CACHE" | wc -l | tr -d ' ')
        SIZE=$(echo "$OLD_CACHE" | xargs du -ck 2>/dev/null | tail -1 | cut -f1)
        echo "  Removing $COUNT files from $cache_dir (${SIZE}KB)" >> "$LOG_FILE"
        echo "$OLD_CACHE" | xargs rm -f 2>/dev/null || true
        FREED_SPACE=$((FREED_SPACE + SIZE))
    fi
done

# Prune __pycache__ directories
echo "" >> "$LOG_FILE"
echo "[PYTHON CACHE]" >> "$LOG_FILE"
PYCACHE_SIZE=$(find "$PROJECT_DIR" -type d -name "__pycache__" -exec du -ck {} + 2>/dev/null | tail -1 | cut -f1 || echo "0")
if [ "$PYCACHE_SIZE" -gt 10000 ]; then
    echo "  Clearing __pycache__ directories (${PYCACHE_SIZE}KB)" >> "$LOG_FILE"
    find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    FREED_SPACE=$((FREED_SPACE + PYCACHE_SIZE))
else
    echo "  __pycache__ size OK (${PYCACHE_SIZE}KB)" >> "$LOG_FILE"
fi

# Prune old backups
echo "" >> "$LOG_FILE"
echo "[BACKUP FILES]" >> "$LOG_FILE"
if [ -d "$PROJECT_DIR/backups" ]; then
    OLD_BACKUPS=$(find "$PROJECT_DIR/backups" -name "*.tar.gz" -mtime +$BACKUP_RETENTION_DAYS 2>/dev/null || true)
    if [ -n "$OLD_BACKUPS" ]; then
        for backup in $OLD_BACKUPS; do
            SIZE=$(du -k "$backup" | cut -f1)
            FREED_SPACE=$((FREED_SPACE + SIZE))
            echo "  Removing: $(basename "$backup") (${SIZE}KB)" >> "$LOG_FILE"
            rm -f "$backup"
        done
    else
        echo "  No backups older than $BACKUP_RETENTION_DAYS days" >> "$LOG_FILE"
    fi
fi

# Summary
echo "" >> "$LOG_FILE"
FREED_MB=$((FREED_SPACE / 1024))
echo "============================================" >> "$LOG_FILE"
echo "✅ PRUNE COMPLETE - Freed ${FREED_MB}MB" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

tail -25 "$LOG_FILE"
