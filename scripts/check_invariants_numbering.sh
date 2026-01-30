#!/bin/bash
# Invariant Numbering Guardrail
# Ensures CLAUDE.md has contiguous invariant numbering and all other files reference valid invariants

set -e

CLAUDE_MD="CLAUDE.md"
EXIT_CODE=0

echo "🔍 Checking invariant numbering consistency..."

# 1. Extract invariant numbers from CLAUDE.md (canonical)
CANONICAL_INVARIANTS=$(grep -o "^### INVARIANT [0-9]\+" "$CLAUDE_MD" | grep -o "[0-9]\+" | sort -n)
CANONICAL_COUNT=$(echo "$CANONICAL_INVARIANTS" | wc -l | tr -d ' ')

echo "📋 Found $CANONICAL_COUNT invariants in CLAUDE.md"

# 2. Check for contiguous numbering (1, 2, 3, ... N with no gaps)
EXPECTED_SEQ=$(seq 1 "$CANONICAL_COUNT")
if [ "$CANONICAL_INVARIANTS" != "$EXPECTED_SEQ" ]; then
    echo "❌ FAIL: CLAUDE.md invariant numbering is NOT contiguous"
    echo "   Expected: $EXPECTED_SEQ"
    echo "   Found:    $CANONICAL_INVARIANTS"
    EXIT_CODE=1
else
    echo "✅ PASS: CLAUDE.md has contiguous numbering (1-$CANONICAL_COUNT)"
fi

# 3. Check all other markdown files for invalid invariant references
echo ""
echo "🔍 Checking references in other files..."

# Find all invariant references outside CLAUDE.md
INVALID_REFS=$(grep -rh "INVARIANT [0-9]\+" --include="*.md" . 2>/dev/null | \
    grep -v "^###" | \
    grep -o "INVARIANT [0-9]\+" | \
    grep -o "[0-9]\+" | \
    sort -u | \
    while read num; do
        if ! echo "$CANONICAL_INVARIANTS" | grep -q "^$num$"; then
            echo "$num"
        fi
    done)

if [ -n "$INVALID_REFS" ]; then
    echo "❌ FAIL: Found references to non-existent invariants:"
    echo "$INVALID_REFS" | while read num; do
        echo "   INVARIANT $num (not defined in CLAUDE.md)"
        grep -rn "INVARIANT $num" --include="*.md" . | grep -v CLAUDE.md
    done
    EXIT_CODE=1
else
    echo "✅ PASS: All invariant references are valid"
fi

# 4. Summary
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED"
    echo "   - CLAUDE.md has contiguous invariants (1-$CANONICAL_COUNT)"
    echo "   - All references point to valid invariants"
else
    echo "❌ CHECKS FAILED"
    echo "   Fix invariant numbering before committing"
fi

exit $EXIT_CODE
