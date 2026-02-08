#!/bin/bash
# Auto Cleanup Script for ai-betting-backend
# Removes temp files, cache, and stale artifacts
# Usage: ./scripts/auto_cleanup.sh [--dry-run]

set -e
cd "$(dirname "$0")/.."

DRY_RUN=false
if [ "$1" == "--dry-run" ]; then
    DRY_RUN=true
    echo "DRY RUN MODE - No files will be deleted"
    echo ""
fi

echo "============================================"
echo "AUTO CLEANUP - ai-betting-backend"
echo "============================================"
echo "Started: $(date)"
echo ""

CLEANED=0

# 1. Clean Python cache
echo "[1/6] Cleaning Python cache..."
PYCACHE_COUNT=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
PYC_COUNT=$(find . -name "*.pyc" 2>/dev/null | wc -l | tr -d ' ')
echo "      Found: $PYCACHE_COUNT __pycache__ dirs, $PYC_COUNT .pyc files"
if [ "$DRY_RUN" = false ]; then
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    echo "      Cleaned!"
    CLEANED=$((CLEANED + PYCACHE_COUNT + PYC_COUNT))
fi

# 2. Clean pytest cache
echo "[2/6] Cleaning pytest cache..."
if [ -d ".pytest_cache" ]; then
    echo "      Found: .pytest_cache"
    if [ "$DRY_RUN" = false ]; then
        rm -rf .pytest_cache
        echo "      Cleaned!"
        CLEANED=$((CLEANED + 1))
    fi
else
    echo "      None found"
fi

# 3. Clean temp/log files
echo "[3/6] Cleaning temp and log files..."
TEMP_FILES=$(find . -name "*.tmp" -o -name "*.log" -o -name "*.bak" -o -name "*~" 2>/dev/null | grep -v ".git" | wc -l | tr -d ' ')
echo "      Found: $TEMP_FILES temp/log files"
if [ "$DRY_RUN" = false ] && [ "$TEMP_FILES" -gt 0 ]; then
    find . -name "*.tmp" -not -path "./.git/*" -delete 2>/dev/null || true
    find . -name "*.bak" -not -path "./.git/*" -delete 2>/dev/null || true
    find . -name "*~" -not -path "./.git/*" -delete 2>/dev/null || true
    # Keep logs but clean if older than 7 days
    find . -name "*.log" -not -path "./.git/*" -mtime +7 -delete 2>/dev/null || true
    echo "      Cleaned!"
    CLEANED=$((CLEANED + TEMP_FILES))
fi

# 4. Clean empty directories
echo "[4/6] Cleaning empty directories..."
EMPTY_DIRS=$(find . -type d -empty -not -path "./.git/*" 2>/dev/null | wc -l | tr -d ' ')
echo "      Found: $EMPTY_DIRS empty directories"
if [ "$DRY_RUN" = false ] && [ "$EMPTY_DIRS" -gt 0 ]; then
    find . -type d -empty -not -path "./.git/*" -delete 2>/dev/null || true
    echo "      Cleaned!"
    CLEANED=$((CLEANED + EMPTY_DIRS))
fi

# 5. Clean stale artifacts (older than 30 days)
echo "[5/6] Checking stale artifacts..."
if [ -d "./artifacts" ]; then
    STALE_ARTIFACTS=$(find ./artifacts -type f -mtime +30 2>/dev/null | wc -l | tr -d ' ')
    echo "      Found: $STALE_ARTIFACTS files older than 30 days in artifacts/"
    if [ "$DRY_RUN" = false ] && [ "$STALE_ARTIFACTS" -gt 0 ]; then
        echo "      (Keeping artifacts - manual review recommended)"
    fi
else
    echo "      No artifacts directory"
fi

# 6. Regenerate project map if script exists
echo "[6/6] Regenerating project map..."
if [ -f "./scripts/generate_project_map.sh" ]; then
    if [ "$DRY_RUN" = false ]; then
        ./scripts/generate_project_map.sh 2>/dev/null || echo "      (Map generation skipped)"
    else
        echo "      Would run: generate_project_map.sh"
    fi
else
    echo "      No project map script found"
fi

echo ""
echo "============================================"
echo "DISK USAGE SUMMARY"
echo "============================================"
echo "Project size: $(du -sh . 2>/dev/null | cut -f1)"
echo "Git size:     $(du -sh .git 2>/dev/null | cut -f1)"
if [ -d "./artifacts" ]; then
    echo "Artifacts:    $(du -sh ./artifacts 2>/dev/null | cut -f1)"
fi
if [ -d "./docs" ]; then
    echo "Docs:         $(du -sh ./docs 2>/dev/null | cut -f1)"
fi

echo ""
echo "============================================"
echo "CLEANUP COMPLETE"
echo "============================================"
echo "Finished: $(date)"
if [ "$DRY_RUN" = true ]; then
    echo "Mode: DRY RUN (no changes made)"
else
    echo "Items cleaned: $CLEANED"
fi
