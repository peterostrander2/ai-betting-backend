#!/bin/bash
# Complexity Report - Flag functions with high cyclomatic complexity
# Usage: ./scripts/complexity_report.sh
# Cron: 0 7 * * 1 (weekly on Monday at 7 AM)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/complexity.log"

# Thresholds
COMPLEXITY_WARN=10
COMPLEXITY_CRIT=15
MAX_FUNC_LINES=100

mkdir -p "$LOG_DIR"

echo "============================================" >> "$LOG_FILE"
echo "COMPLEXITY REPORT - $(date)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

cd "$PROJECT_DIR"

# Check if radon is available
if ! command -v radon &> /dev/null; then
    echo "Installing radon..." >> "$LOG_FILE"
    pip install radon --quiet 2>/dev/null || true
fi

# Run radon for cyclomatic complexity
echo "" >> "$LOG_FILE"
echo "[CYCLOMATIC COMPLEXITY]" >> "$LOG_FILE"
if command -v radon &> /dev/null; then
    # Get functions with complexity > threshold
    COMPLEX_FUNCS=$(radon cc . -a -nc --exclude "__pycache__,tests,venv,.git" 2>/dev/null | \
                    grep -E "^\s+[A-Z]\s" | \
                    awk -v warn="$COMPLEXITY_WARN" '$NF ~ /\(.*\)/ {gsub(/[()]/, "", $NF); if ($NF+0 >= warn) print}' | \
                    head -20 || true)

    if [ -n "$COMPLEX_FUNCS" ]; then
        echo "  Functions with complexity >= $COMPLEXITY_WARN:" >> "$LOG_FILE"
        echo "$COMPLEX_FUNCS" | while read -r line; do
            COMPLEXITY=$(echo "$line" | grep -oE "[0-9]+$" || echo "0")
            if [ "$COMPLEXITY" -ge "$COMPLEXITY_CRIT" ]; then
                echo "    🔴 $line (CRITICAL)" >> "$LOG_FILE"
            else
                echo "    🟡 $line" >> "$LOG_FILE"
            fi
        done
    else
        echo "  ✅ No functions with complexity >= $COMPLEXITY_WARN" >> "$LOG_FILE"
    fi

    # Average complexity
    echo "" >> "$LOG_FILE"
    AVG_COMPLEXITY=$(radon cc . -a --exclude "__pycache__,tests,venv,.git" 2>/dev/null | \
                     grep "Average complexity" | awk '{print $NF}' || echo "N/A")
    echo "  Average complexity: $AVG_COMPLEXITY" >> "$LOG_FILE"
else
    echo "  ⚠️  radon not available" >> "$LOG_FILE"
fi

# Maintainability Index
echo "" >> "$LOG_FILE"
echo "[MAINTAINABILITY INDEX]" >> "$LOG_FILE"
if command -v radon &> /dev/null; then
    LOW_MI=$(radon mi . -s --exclude "__pycache__,tests,venv,.git" 2>/dev/null | \
             grep -E "^.+ - [CF]" | head -10 || true)

    if [ -n "$LOW_MI" ]; then
        echo "  Files with low maintainability (C/F rating):" >> "$LOG_FILE"
        echo "$LOW_MI" | sed 's/^/    ⚠️  /' >> "$LOG_FILE"
    else
        echo "  ✅ All files have acceptable maintainability" >> "$LOG_FILE"
    fi
fi

# Long functions (line count)
echo "" >> "$LOG_FILE"
echo "[LONG FUNCTIONS (>$MAX_FUNC_LINES lines)]" >> "$LOG_FILE"

# Find long function definitions
python3 << 'EOF' 2>/dev/null >> "$LOG_FILE" || echo "  Could not analyze function lengths" >> "$LOG_FILE"
import os
import ast

def get_function_lengths(directory):
    results = []
    for root, dirs, files in os.walk(directory):
        # Skip unwanted directories
        dirs[:] = [d for d in dirs if d not in ['__pycache__', 'tests', 'venv', '.git']]

        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        tree = ast.parse(f.read())

                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            length = node.end_lineno - node.lineno + 1
                            if length > 100:
                                results.append((filepath, node.name, length))
                except:
                    pass

    return sorted(results, key=lambda x: x[2], reverse=True)[:10]

for filepath, func, length in get_function_lengths('.'):
    print(f"  🟡 {filepath}: {func}() - {length} lines")

if not get_function_lengths('.'):
    print("  ✅ No functions exceed 100 lines")
EOF

# Deeply nested code
echo "" >> "$LOG_FILE"
echo "[DEEP NESTING (>4 levels)]" >> "$LOG_FILE"
DEEP_NESTING=$(grep -rn "^                    " --include="*.py" . 2>/dev/null | \
               grep -v __pycache__ | grep -v tests | head -10 || true)
if [ -n "$DEEP_NESTING" ]; then
    echo "  Files with deep nesting:" >> "$LOG_FILE"
    echo "$DEEP_NESTING" | cut -d: -f1 | sort -u | head -5 | sed 's/^/    ⚠️  /' >> "$LOG_FILE"
else
    echo "  ✅ No deeply nested code detected" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"
tail -50 "$LOG_FILE"
