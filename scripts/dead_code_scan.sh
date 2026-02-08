#!/bin/bash
# Dead Code Scan - Find unused functions/imports
# Usage: ./scripts/dead_code_scan.sh
# Cron: 0 7 * * 0 (weekly on Sunday at 7 AM)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/dead_code.log"

mkdir -p "$LOG_DIR"

echo "============================================" >> "$LOG_FILE"
echo "DEAD CODE SCAN - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

cd "$PROJECT_DIR"

# Check if vulture is available
if ! command -v vulture &> /dev/null; then
    echo "Installing vulture..." >> "$LOG_FILE"
    pip install vulture --quiet 2>/dev/null || true
fi

# Run vulture for dead code detection
echo "" >> "$LOG_FILE"
echo "[VULTURE ANALYSIS]" >> "$LOG_FILE"
if command -v vulture &> /dev/null; then
    VULTURE_OUTPUT=$(vulture . --min-confidence 80 --exclude "__pycache__,tests,scripts,.git,venv" 2>&1 | head -50 || true)

    if [ -n "$VULTURE_OUTPUT" ]; then
        DEAD_COUNT=$(echo "$VULTURE_OUTPUT" | wc -l | tr -d ' ')
        echo "  Found $DEAD_COUNT potential dead code items:" >> "$LOG_FILE"
        echo "$VULTURE_OUTPUT" | head -20 | sed 's/^/    /' >> "$LOG_FILE"
        if [ "$DEAD_COUNT" -gt 20 ]; then
            echo "    ... and $((DEAD_COUNT - 20)) more" >> "$LOG_FILE"
        fi
    else
        echo "  ✅ No obvious dead code detected" >> "$LOG_FILE"
    fi
else
    echo "  ⚠️  vulture not available, using basic analysis" >> "$LOG_FILE"
fi

# Find unused imports manually
echo "" >> "$LOG_FILE"
echo "[POTENTIALLY UNUSED IMPORTS]" >> "$LOG_FILE"

# Look for imports that might not be used
UNUSED_IMPORTS=0
while IFS= read -r pyfile; do
    # Get all imported names
    IMPORTS=$(grep -E "^from .+ import |^import " "$pyfile" 2>/dev/null | \
              sed 's/from .* import //; s/import //; s/ as .*//; s/,/\n/g' | \
              tr -d ' ' | grep -v "^$" || true)

    for imp in $IMPORTS; do
        # Check if the import is used elsewhere in the file
        USAGE=$(grep -c "\b$imp\b" "$pyfile" 2>/dev/null || echo "0")
        if [ "$USAGE" -le 1 ]; then
            echo "  $pyfile: $imp (used $USAGE times)" >> "$LOG_FILE"
            UNUSED_IMPORTS=$((UNUSED_IMPORTS + 1))
            if [ "$UNUSED_IMPORTS" -ge 15 ]; then
                break 2
            fi
        fi
    done
done < <(find . -name "*.py" -not -path "./__pycache__/*" -not -path "./tests/*" -not -path "./venv/*" -not -path "./.git/*" | head -50)

# Find functions defined but never called
echo "" >> "$LOG_FILE"
echo "[POTENTIALLY UNUSED FUNCTIONS]" >> "$LOG_FILE"

# Get all function definitions
FUNC_DEFS=$(grep -rn "^def \|^async def " --include="*.py" . 2>/dev/null | \
            grep -v __pycache__ | grep -v tests | grep -v "__init__\|__str__\|__repr__" | \
            sed 's/.*def \([a-zA-Z_][a-zA-Z0-9_]*\).*/\1/' | sort -u | head -100)

UNUSED_FUNCS=0
for func in $FUNC_DEFS; do
    # Skip private functions and common names
    if [[ "$func" == _* ]] || [[ "$func" == "main" ]] || [[ "$func" == "setup" ]]; then
        continue
    fi

    # Count usages (excluding the definition line)
    USAGE=$(grep -rn "\b$func\b" --include="*.py" . 2>/dev/null | grep -v __pycache__ | grep -v "def $func" | wc -l | tr -d ' ')

    if [ "$USAGE" -eq 0 ]; then
        DEF_LINE=$(grep -rn "def $func" --include="*.py" . 2>/dev/null | grep -v __pycache__ | head -1)
        echo "  $DEF_LINE" >> "$LOG_FILE"
        UNUSED_FUNCS=$((UNUSED_FUNCS + 1))
        if [ "$UNUSED_FUNCS" -ge 10 ]; then
            echo "  ... (limited to 10 results)" >> "$LOG_FILE"
            break
        fi
    fi
done

# Summary
echo "" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"
echo "DEAD CODE SUMMARY" >> "$LOG_FILE"
echo "  Potential unused imports: $UNUSED_IMPORTS" >> "$LOG_FILE"
echo "  Potential unused functions: $UNUSED_FUNCS" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
echo "Note: Review manually - some may be used dynamically or via imports" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

tail -45 "$LOG_FILE"
