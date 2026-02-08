#!/bin/bash
# Session Start Script - Run this when you begin working
# Usage: ./scripts/session_start.sh

cd "$(dirname "$0")/.."

echo "============================================"
echo "SESSION START - ai-betting-backend"
echo "============================================"
echo "Time: $(date)"
echo ""

# 1. Git status
echo "[GIT STATUS]"
BRANCH=$(git branch --show-current)
echo "Branch: $BRANCH"

UNCOMMITTED=$(git status --porcelain | wc -l | tr -d ' ')
if [ "$UNCOMMITTED" -gt 0 ]; then
    echo "⚠️  Uncommitted changes: $UNCOMMITTED files"
    git status --porcelain | head -5
    [ "$UNCOMMITTED" -gt 5 ] && echo "   ... and $((UNCOMMITTED - 5)) more"
else
    echo "✅ Working tree clean"
fi

LAST_COMMIT=$(git log -1 --format="%ar - %s" 2>/dev/null)
echo "Last commit: $LAST_COMMIT"
echo ""

# 2. Check recent health logs
echo "[HEALTH STATUS]"
if [ -f "logs/health_check.log" ]; then
    LAST_HEALTH=$(tail -1 logs/health_check.log 2>/dev/null | grep -o "Status:.*\|Issues found:.*" | head -1)
    HEALTH_TIME=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" logs/health_check.log 2>/dev/null)
    echo "Last health check: $HEALTH_TIME"
    echo "Result: ${LAST_HEALTH:-Unknown}"
else
    echo "No health check logs yet"
fi

if [ -f "logs/live_check.log" ]; then
    LIVE_TIME=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" logs/live_check.log 2>/dev/null)
    LIVE_STATUS=$(tail -20 logs/live_check.log 2>/dev/null | grep -o "✅\|❌" | tail -1)
    echo "Last live check: $LIVE_TIME ${LIVE_STATUS:-}"
fi
echo ""

# 3. Check for stale TODOs
echo "[STALE TODOS]"
TODO_COUNT=$(grep -rn "TODO\|FIXME" --include="*.py" . 2>/dev/null | grep -v __pycache__ | wc -l | tr -d ' ')
echo "Total TODOs: $TODO_COUNT"
if [ "$TODO_COUNT" -gt 10 ]; then
    echo "⚠️  Consider addressing some TODOs"
fi
echo ""

# 4. Quick stats
echo "[PROJECT STATS]"
echo "Python files: $(find . -name '*.py' -not -path './__pycache__/*' -not -path './.git/*' | wc -l | tr -d ' ')"
echo "Test files: $(find ./tests -name 'test_*.py' 2>/dev/null | wc -l | tr -d ' ')"
echo "Scripts: $(find ./scripts -name '*.sh' 2>/dev/null | wc -l | tr -d ' ')"
echo ""

# 5. Reminders
echo "[REMINDERS]"
echo "• Run health check: ./scripts/daily_health_check.sh"
echo "• Run tests: pytest tests/ -v --tb=short"
echo "• Check tasks: cat tasks/todo.md"
echo ""

echo "============================================"
echo "Ready to work! 🚀"
echo "============================================"
