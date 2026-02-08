#!/bin/bash
# Backup Data - Backup /data persistent storage
# Usage: ./scripts/backup_data.sh
# Cron: 0 3 * * * (daily at 3 AM)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/backup.log"
BACKUP_DIR="$PROJECT_DIR/backups"
DATA_DIR="${DATA_DIR:-/data}"
MAX_BACKUPS=7  # Keep 7 days of backups

mkdir -p "$LOG_DIR" "$BACKUP_DIR"

echo "============================================" >> "$LOG_FILE"
echo "BACKUP - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="backup_${TIMESTAMP}.tar.gz"

# Check if data directory exists
if [ -d "$DATA_DIR" ]; then
    echo "Source: $DATA_DIR" >> "$LOG_FILE"

    # Calculate size before backup
    SIZE_BEFORE=$(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)
    echo "Data size: $SIZE_BEFORE" >> "$LOG_FILE"

    # Create backup
    echo "Creating backup: $BACKUP_NAME" >> "$LOG_FILE"
    tar -czf "$BACKUP_DIR/$BACKUP_NAME" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")" 2>> "$LOG_FILE"

    BACKUP_SIZE=$(du -sh "$BACKUP_DIR/$BACKUP_NAME" | cut -f1)
    echo "✅ Backup created: $BACKUP_SIZE" >> "$LOG_FILE"

    # Cleanup old backups
    echo "" >> "$LOG_FILE"
    echo "Cleaning up old backups (keeping last $MAX_BACKUPS)..." >> "$LOG_FILE"
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | wc -l | tr -d ' ')

    if [ "$BACKUP_COUNT" -gt "$MAX_BACKUPS" ]; then
        REMOVE_COUNT=$((BACKUP_COUNT - MAX_BACKUPS))
        ls -1t "$BACKUP_DIR"/backup_*.tar.gz | tail -n "$REMOVE_COUNT" | while read -r old_backup; do
            echo "  Removing: $(basename "$old_backup")" >> "$LOG_FILE"
            rm -f "$old_backup"
        done
    else
        echo "  No cleanup needed ($BACKUP_COUNT backups)" >> "$LOG_FILE"
    fi
else
    echo "⚠️  Data directory not found: $DATA_DIR" >> "$LOG_FILE"
    echo "  This is expected in local dev environment" >> "$LOG_FILE"

    # Backup local data files instead
    if [ -d "$PROJECT_DIR/data" ]; then
        echo "  Backing up local ./data directory instead" >> "$LOG_FILE"
        tar -czf "$BACKUP_DIR/$BACKUP_NAME" -C "$PROJECT_DIR" "data" 2>> "$LOG_FILE"
        echo "✅ Local backup created" >> "$LOG_FILE"
    fi
fi

# List current backups
echo "" >> "$LOG_FILE"
echo "[CURRENT BACKUPS]" >> "$LOG_FILE"
ls -lh "$BACKUP_DIR"/*.tar.gz 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}' >> "$LOG_FILE" || echo "  No backups found" >> "$LOG_FILE"

echo "" >> "$LOG_FILE"
tail -20 "$LOG_FILE"
