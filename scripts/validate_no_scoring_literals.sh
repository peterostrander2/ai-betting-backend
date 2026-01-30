#!/bin/bash
# Prevents hardcoded scoring literals from reappearing in production code
# Focus: catch actual scoring logic, not comments/docstrings

set -e
EXIT_CODE=0

echo "🔍 Checking for forbidden scoring literals..."

# Only check main scoring files that should use contract
check_live_data_router() {
    local file="live_data_router.py"
    if [ ! -f "$file" ]; then return 0; fi

    # Engine weight multiplication patterns (ai_scaled * 0.25, etc)
    # Must use ENGINE_WEIGHTS["ai"] etc
    if grep -nE "\* 0\.(25|30|20|15)[^0-9]" "$file" | grep -vE "ENGINE_WEIGHTS|#|rng\.random"; then
        echo "❌ FAIL: Hardcoded engine weight multiplication in $file"
        return 1
    fi

    # Gold Star gate comparisons (ai_scaled >= 6.8, etc)
    # Must use GOLD_STAR_GATES[...]
    if grep -nE "(ai_scaled|research_score|jarvis_rs|esoteric_score) >= (6\.8|5\.5|6\.5|4\.0)" "$file" | grep -v "GOLD_STAR_GATES"; then
        echo "❌ FAIL: Hardcoded Gold Star gate in $file"
        return 1
    fi

    # Final score threshold (final_score >= 6.5 or 7.5)
    # Must use MIN_FINAL_SCORE or GOLD_STAR_THRESHOLD
    if grep -nE "final_score >= (6\.5|7\.5)" "$file" | grep -vE "MIN_FINAL_SCORE|GOLD_STAR_THRESHOLD"; then
        echo "❌ FAIL: Hardcoded final_score threshold in $file"
        return 1
    fi

    return 0
}

check_titanium() {
    local file="core/titanium.py"
    if [ ! -f "$file" ]; then return 0; fi

    # Check for hardcoded threshold=8.0 default (should use TITANIUM_RULE)
    if grep -nE "threshold.*=.*8\.0" "$file" | grep -v "TITANIUM_RULE"; then
        echo "❌ FAIL: Hardcoded titanium threshold in $file"
        return 1
    fi

    # Check for hardcoded >= 3 count (should use TITANIUM_RULE)
    if grep -nE "hits_count >= 3" "$file" | grep -v "TITANIUM_RULE"; then
        echo "❌ FAIL: Hardcoded titanium min count in $file"
        return 1
    fi

    return 0
}

# Run checks
FAILED=0

if ! check_live_data_router; then
    FAILED=1
fi

if ! check_titanium; then
    FAILED=1
fi

if [ $FAILED -eq 0 ]; then
    echo "✅ No forbidden scoring literals found in critical files"
else
    echo ""
    echo "Fix: Replace literals with imports from core/scoring_contract.py"
    exit 1
fi
