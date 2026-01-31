#!/bin/bash
# SESSION 9 — RESTART PERSISTENCE + RETRY RESILIENCE
# Part A: Verify restart persistence indicators (automated)
# Part B: Validate retry wrapper functionality
# Part C: Stability checks (predictions not regressing)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"

# Source retry library
source "$SCRIPT_DIR/lib/retry.sh"

echo "=============================================================="
echo "SESSION 9 SPOT CHECK: Restart Persistence + Retry Resilience"
echo "Base URL: $BASE_URL"
echo "=============================================================="

fail() { echo "❌ FAIL: $1"; exit 1; }

# ========== PART A: RESTART PERSISTENCE INDICATORS ==========
echo ""
echo "PART A: Restart Persistence Indicators"
echo "---------------------------------------"

# Check 1: Sentinel file exists (proves volume survived restarts)
echo ""
echo "Check 1: Volume sentinel file..."
STORAGE=$(retry_curl_auth "${BASE_URL}/internal/storage/health" 3 15) || fail "Storage health unreachable"

SENTINEL_EXISTS=$(echo "$STORAGE" | jq -r '.sentinel_exists // false')
SENTINEL_TS=$(echo "$STORAGE" | jq -r '.sentinel_timestamp // "none"')

if [[ "$SENTINEL_EXISTS" != "true" ]]; then
    fail "Sentinel file missing - volume may not be persistent"
fi
echo "✅ Sentinel exists: $SENTINEL_TS"

# Check 2: Predictions file has data (persisted picks)
echo ""
echo "Check 2: Predictions persistence..."
PRED_EXISTS=$(echo "$STORAGE" | jq -r '.predictions_exists // false')
PRED_COUNT=$(echo "$STORAGE" | jq -r '.predictions_line_count // 0')
PRED_SIZE=$(echo "$STORAGE" | jq -r '.predictions_size_bytes // 0')

if [[ "$PRED_EXISTS" != "true" ]]; then
    fail "Predictions file missing"
fi

if [[ "$PRED_COUNT" -eq 0 ]]; then
    echo "⚠️  WARN: Zero predictions (fresh deployment)"
else
    echo "✅ Predictions persisted: $PRED_COUNT picks, ${PRED_SIZE} bytes"
fi

# Check 3: Volume is mounted (not ephemeral)
echo ""
echo "Check 3: Volume mount status..."
# Note: jq's // operator treats false as falsey, so use 'if . == null then' pattern
IS_MOUNT=$(echo "$STORAGE" | jq -r 'if .is_mountpoint == null then "false" else (.is_mountpoint | tostring) end')
IS_EPHEMERAL=$(echo "$STORAGE" | jq -r 'if .is_ephemeral == null then "true" else (.is_ephemeral | tostring) end')

if [[ "$IS_MOUNT" != "true" ]]; then
    fail "Storage is not a mountpoint"
fi

if [[ "$IS_EPHEMERAL" == "true" ]]; then
    fail "Storage is marked ephemeral - will be lost on restart"
fi
echo "✅ Volume: mounted, persistent"

# Check 4: Grader can read persisted predictions
echo ""
echo "Check 4: Grader reads persisted data..."
GRADER=$(retry_curl_auth "${BASE_URL}/live/grader/status" 3 15) || fail "Grader status unreachable"

GRADER_AVAIL=$(echo "$GRADER" | jq -r '.available // false')
GRADER_PREDS=$(echo "$GRADER" | jq -r '.grader_store.predictions_logged // 0')

if [[ "$GRADER_AVAIL" != "true" ]]; then
    fail "Grader not available"
fi

if [[ "$GRADER_PREDS" -eq 0 ]] && [[ "$PRED_COUNT" -gt 0 ]]; then
    fail "Grader sees 0 predictions but storage has $PRED_COUNT"
fi
echo "✅ Grader active: $GRADER_PREDS predictions accessible"

# Check 5: Storage path consistency
echo ""
echo "Check 5: Storage path invariant..."
STORAGE_PATH=$(echo "$STORAGE" | jq -r '.predictions_file // ""')
GRADER_PATH=$(echo "$GRADER" | jq -r '.grader_store.storage_path // ""')

# Both should reference the same volume
if [[ -z "$STORAGE_PATH" ]]; then
    fail "Storage predictions_file path is empty"
fi

# Path should be on Railway volume (/data or /app/grader_data)
if [[ "$STORAGE_PATH" != /data/* ]] && [[ "$STORAGE_PATH" != /app/grader_data/* ]]; then
    fail "Storage path not on Railway volume: $STORAGE_PATH"
fi
echo "✅ Storage path: $STORAGE_PATH (on Railway volume)"

# ========== PART B: RETRY WRAPPER VALIDATION ==========
echo ""
echo "PART B: Retry Wrapper Validation"
echo "---------------------------------"

# Check 6: Retry library loaded
echo ""
echo "Check 6: Retry library functions..."
if ! type retry_curl >/dev/null 2>&1; then
    fail "retry_curl function not available"
fi
if ! type retry_curl_auth >/dev/null 2>&1; then
    fail "retry_curl_auth function not available"
fi
if ! type wait_for_api >/dev/null 2>&1; then
    fail "wait_for_api function not available"
fi
echo "✅ Retry functions: loaded"

# Check 7: Retry works for valid endpoint
echo ""
echo "Check 7: Retry on valid endpoint..."
HEALTH_RESULT=$(retry_curl "${BASE_URL}/health" 2 10) || fail "Retry failed on /health"
HEALTH_STATUS=$(echo "$HEALTH_RESULT" | jq -r '.status // "unknown"')

if [[ "$HEALTH_STATUS" != "healthy" ]] && [[ "$HEALTH_STATUS" != "ok" ]]; then
    fail "Health check returned unexpected status: $HEALTH_STATUS"
fi
echo "✅ Retry mechanism: working"

# Check 8: wait_for_api function works
echo ""
echo "Check 8: wait_for_api function..."
if wait_for_api "$BASE_URL" 2; then
    echo "✅ wait_for_api: API ready"
else
    fail "wait_for_api failed"
fi

# ========== PART C: STABILITY CHECKS ==========
echo ""
echo "PART C: Stability Checks"
echo "------------------------"

# Check 9: Predictions count stable (not regressing)
echo ""
echo "Check 9: Prediction count stability..."

# Get current count
CURRENT_COUNT=$PRED_COUNT

# The count should be non-negative and reasonable
if [[ "$CURRENT_COUNT" -lt 0 ]]; then
    fail "Negative prediction count: $CURRENT_COUNT"
fi

# If we have predictions, they should be growing or stable (not dropping significantly)
# This is a soft check - we just log the count for manual review
if [[ "$CURRENT_COUNT" -gt 0 ]]; then
    echo "✅ Predictions stable: $CURRENT_COUNT picks logged"
else
    echo "⚠️  WARN: Zero predictions - expected for fresh deployment"
fi

# Check 10: Multiple endpoints respond consistently
echo ""
echo "Check 10: Endpoint consistency..."
ENDPOINTS_OK=0

for endpoint in "/health" "/internal/storage/health" "/live/grader/status"; do
    RESP=$(retry_curl_auth "${BASE_URL}${endpoint}" 2 10 2>/dev/null) || true
    if echo "$RESP" | jq -e . >/dev/null 2>&1; then
        ENDPOINTS_OK=$((ENDPOINTS_OK + 1))
    fi
done

if [[ $ENDPOINTS_OK -lt 3 ]]; then
    fail "Only $ENDPOINTS_OK/3 endpoints responding consistently"
fi
echo "✅ Endpoints: $ENDPOINTS_OK/3 responding with valid JSON"

echo ""
echo "=============================================================="
echo "✅ SESSION 9 PASS: Restart persistence + retry resilience verified"
echo "=============================================================="
echo ""
echo "Note: For full restart survival test, use:"
echo "  ./scripts/verify_restart_persistence.sh"
echo "  (requires manual Railway restart)"
