#!/bin/bash
# Memory Profiler - Track memory usage, alert on potential leaks
# Usage: ./scripts/memory_profiler.sh
# Cron: 0 */4 * * * (every 4 hours)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/memory_profiler.log"
ALERT_THRESHOLD_MB=500

mkdir -p "$LOG_DIR"

echo "============================================" >> "$LOG_FILE"
echo "MEMORY PROFILE - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

# Check Python process memory (if running locally)
PYTHON_PROCS=$(ps aux | grep -E "python.*main\.py|uvicorn" | grep -v grep || true)
if [ -n "$PYTHON_PROCS" ]; then
    echo "[LOCAL PYTHON PROCESSES]" >> "$LOG_FILE"
    echo "$PYTHON_PROCS" | awk '{printf "  PID %s: %s MB (RSS), %s%% CPU\n", $2, $6/1024, $3}' >> "$LOG_FILE"

    # Check for high memory usage
    TOTAL_MB=$(echo "$PYTHON_PROCS" | awk '{sum+=$6} END {print sum/1024}')
    if (( $(echo "$TOTAL_MB > $ALERT_THRESHOLD_MB" | bc -l) )); then
        echo "  ⚠️  HIGH MEMORY: ${TOTAL_MB}MB exceeds ${ALERT_THRESHOLD_MB}MB threshold" >> "$LOG_FILE"
    else
        echo "  ✅ Memory OK: ${TOTAL_MB}MB" >> "$LOG_FILE"
    fi
else
    echo "[NO LOCAL PYTHON PROCESSES]" >> "$LOG_FILE"
fi

# Check system memory
echo "" >> "$LOG_FILE"
echo "[SYSTEM MEMORY]" >> "$LOG_FILE"
if command -v vm_stat &> /dev/null; then
    # macOS
    FREE_PAGES=$(vm_stat | grep "Pages free" | awk '{print $3}' | tr -d '.')
    INACTIVE_PAGES=$(vm_stat | grep "Pages inactive" | awk '{print $3}' | tr -d '.')
    PAGE_SIZE=4096
    FREE_MB=$(( (FREE_PAGES + INACTIVE_PAGES) * PAGE_SIZE / 1024 / 1024 ))
    echo "  Available: ~${FREE_MB}MB" >> "$LOG_FILE"
elif command -v free &> /dev/null; then
    # Linux
    free -m | grep Mem | awk '{printf "  Total: %sMB, Used: %sMB, Free: %sMB\n", $2, $3, $4}' >> "$LOG_FILE"
fi

# Track Python object sizes in codebase (static analysis)
echo "" >> "$LOG_FILE"
echo "[LARGE DATA STRUCTURES]" >> "$LOG_FILE"
cd "$PROJECT_DIR"
grep -rn "= \[\]" --include="*.py" | grep -v test | grep -v __pycache__ | wc -l | xargs -I {} echo "  Empty lists initialized: {}" >> "$LOG_FILE"
grep -rn "= {}" --include="*.py" | grep -v test | grep -v __pycache__ | wc -l | xargs -I {} echo "  Empty dicts initialized: {}" >> "$LOG_FILE"

# Check for potential memory leaks (growing caches without limits)
UNBOUNDED_CACHES=$(grep -rn "@cache\|@lru_cache\|functools.cache" --include="*.py" | grep -v "maxsize" | grep -v __pycache__ || true)
if [ -n "$UNBOUNDED_CACHES" ]; then
    echo "  ⚠️  Unbounded caches found (no maxsize):" >> "$LOG_FILE"
    echo "$UNBOUNDED_CACHES" | head -5 | sed 's/^/    /' >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
echo "Profile complete." >> "$LOG_FILE"

# Show last entry
tail -25 "$LOG_FILE"
