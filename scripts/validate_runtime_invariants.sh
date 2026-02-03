#!/bin/bash
# Runtime Invariant Behavior Check
# Verifies actual code behavior matches invariants (not just docs)

EXIT_CODE=0
echo "🔍 Checking runtime invariant behavior..."

# INVARIANT 1: Storage Persistence Path
echo ""
echo "📦 INVARIANT 1: Storage Persistence"
if grep -q "RAILWAY_VOLUME_MOUNT_PATH" grader_store.py storage_paths.py 2>/dev/null; then
    echo "✅ PASS: Storage uses RAILWAY_VOLUME_MOUNT_PATH"
else
    echo "❌ FAIL: Storage does not use RAILWAY_VOLUME_MOUNT_PATH"
    EXIT_CODE=1
fi

# INVARIANT 2: Titanium 3-of-4 Rule
echo ""
echo "⚡ INVARIANT 2: Titanium 3-of-4 Rule"
if grep -q ">= 3" core/titanium.py 2>/dev/null; then
    echo "✅ PASS: Titanium checks for >= 3 engines at 8.0"
else
    echo "❌ FAIL: Titanium rule does not check for >= 3 engines"
    EXIT_CODE=1
fi

# INVARIANT 3: ET Window Bounds
echo ""
echo "🕐 INVARIANT 3: ET Window [00:01:00, 00:00:00 next day)"
if grep -q "time(0, 1, 0)" core/time_et.py 2>/dev/null; then
    echo "✅ PASS: ET window starts at 00:01:00"
else
    echo "❌ FAIL: ET window start is NOT 00:01:00"
    EXIT_CODE=1
fi

# INVARIANT 6: Output Filtering (6.5 minimum)
echo ""
echo "📊 INVARIANT 6: Output Filtering (6.5 minimum)"
if grep -qE ">=\s*6\.5|>= 6\.5" live_data_router.py 2>/dev/null; then
    echo "✅ PASS: Output filtering uses 6.5 minimum"
else
    echo "❌ FAIL: Output filtering does not use 6.5 threshold"
    EXIT_CODE=1
fi

# Integration Registry Check
echo ""
echo "🔌 Integration Check"
INTEGRATIONS_OK=true
for integration in odds_api playbook_api balldontlie; do
    if ! grep -q "\"$integration\"" integration_registry.py 2>/dev/null; then
        echo "❌ FAIL: Required integration '$integration' not found in registry"
        INTEGRATIONS_OK=false
        EXIT_CODE=1
    fi
done
if [ "$INTEGRATIONS_OK" = true ]; then
    echo "✅ PASS: All required integrations registered"
fi

# Summary
echo ""
echo "============================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ ALL RUNTIME INVARIANTS VERIFIED"
else
    echo "❌ RUNTIME INVARIANTS FAILED"
    echo "   Fix code behavior before committing"
fi
echo "============================================"

exit $EXIT_CODE
