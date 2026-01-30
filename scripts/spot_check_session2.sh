#!/bin/bash
# SESSION 2 SPOT CHECK: Persistence / Railway Volume
# Validates storage is on Railway persistent volume and survives restarts
# Exit 0 = all pass, Exit 1 = failures detected

# Don't exit on first error - we track failures manually
set +e

# Configuration
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0
PASSED=0

echo "=============================================="
echo "SESSION 2 SPOT CHECK: Persistence / Storage"
echo "=============================================="
echo "Base URL: $BASE_URL"
echo "Date: $(date)"
echo ""

# Helper function
check() {
    local name="$1"
    local condition="$2"
    local actual="$3"
    local expected="$4"

    if [ "$condition" = "true" ]; then
        echo -e "${GREEN}PASS${NC}: $name"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}FAIL${NC}: $name"
        echo "  Expected: $expected"
        echo "  Actual: $actual"
        FAILED=$((FAILED + 1))
    fi
}

# Fetch storage health
echo -e "${YELLOW}Fetching /internal/storage/health...${NC}"
STORAGE_DATA=$(curl -s "$BASE_URL/internal/storage/health" -H "X-API-Key: $API_KEY")

echo "Storage health response:"
echo "$STORAGE_DATA" | jq '.' 2>/dev/null || echo "$STORAGE_DATA"
echo ""

# CHECK 1: resolved_base_dir is set
echo -e "${YELLOW}[CHECK 1] Storage base directory resolved${NC}"
BASE_DIR=$(echo "$STORAGE_DATA" | jq -r '.resolved_base_dir // "NOT_SET"')
check "resolved_base_dir is set" \
    "$([ "$BASE_DIR" != "NOT_SET" ] && [ "$BASE_DIR" != "null" ] && echo true || echo false)" \
    "$BASE_DIR" \
    "non-empty path"

# CHECK 2: is_mountpoint = true (Railway volume mounted)
echo -e "${YELLOW}[CHECK 2] Storage is mounted volume${NC}"
# Use explicit equality check (not // operator which treats false as truthy)
IS_MOUNT=$(echo "$STORAGE_DATA" | jq -r 'if .is_mountpoint == true then "true" else "false" end')
check "is_mountpoint = true" \
    "$IS_MOUNT" \
    "$IS_MOUNT" \
    "true"

# CHECK 3: is_ephemeral = false (not wiped on restart)
echo -e "${YELLOW}[CHECK 3] Storage is NOT ephemeral${NC}"
IS_EPHEMERAL=$(echo "$STORAGE_DATA" | jq -r 'if .is_ephemeral == true then "true" else "false" end')
check "is_ephemeral = false" \
    "$([ "$IS_EPHEMERAL" = "false" ] && echo true || echo false)" \
    "$IS_EPHEMERAL" \
    "false"

# CHECK 4: predictions.jsonl exists with data
echo -e "${YELLOW}[CHECK 4] Predictions file exists${NC}"
PRED_COUNT=$(echo "$STORAGE_DATA" | jq -r '.predictions_line_count // 0')
check "predictions.jsonl has data" \
    "$([ "$PRED_COUNT" -gt 0 ] && echo true || echo false)" \
    "$PRED_COUNT lines" \
    "> 0 lines"

# CHECK 5: Storage path matches RAILWAY_VOLUME_MOUNT_PATH env var
echo -e "${YELLOW}[CHECK 5] Storage matches Railway volume mount path${NC}"
RAILWAY_PATH=$(echo "$STORAGE_DATA" | jq -r '.env_railway_volume_mount_path // "NOT_SET"')
# Check that resolved_base_dir starts with the Railway mount path
if [ "$RAILWAY_PATH" != "NOT_SET" ] && [ "$RAILWAY_PATH" != "null" ]; then
    PATH_MATCH=$(echo "$BASE_DIR" | grep -qE "^$RAILWAY_PATH" && echo true || echo false)
else
    PATH_MATCH="false"
fi
check "Storage path matches RAILWAY_VOLUME_MOUNT_PATH" \
    "$PATH_MATCH" \
    "base=$BASE_DIR, railway=$RAILWAY_PATH" \
    "base_dir starts with RAILWAY_VOLUME_MOUNT_PATH"

# CHECK 6: Write test passed (if available in response)
echo -e "${YELLOW}[CHECK 6] Write test verification${NC}"
WRITE_OK=$(echo "$STORAGE_DATA" | jq -r '.write_test_ok // .is_writable // "unknown"')
if [ "$WRITE_OK" = "unknown" ]; then
    # Try to infer from other fields
    WRITE_OK=$([ "$IS_MOUNT" = "true" ] && [ "$IS_EPHEMERAL" = "false" ] && echo "true" || echo "false")
fi
check "Storage is writable" \
    "$([ "$WRITE_OK" = "true" ] && echo true || echo false)" \
    "$WRITE_OK" \
    "true"

# CHECK 7: Verify grader status endpoint confirms storage
echo -e "${YELLOW}[CHECK 7] Grader status confirms storage${NC}"
GRADER_STATUS=$(curl -s "$BASE_URL/live/grader/status" -H "X-API-Key: $API_KEY" 2>/dev/null || echo '{}')
# Fields are in grader_store sub-object
GRADER_STORAGE=$(echo "$GRADER_STATUS" | jq -r '.grader_store.storage_path // .storage_path // "NOT_SET"')
GRADER_PREDS=$(echo "$GRADER_STATUS" | jq -r '.grader_store.predictions_logged // 0')
GRADER_AVAILABLE=$(echo "$GRADER_STATUS" | jq -r 'if .available == true then "true" else "false" end')

# Grader is working if storage path is set AND predictions are logged
GRADER_STORAGE_OK=$([ "$GRADER_STORAGE" != "NOT_SET" ] && [ "$GRADER_STORAGE" != "null" ] && echo true || echo false)
GRADER_HAS_PREDS=$([ "$GRADER_PREDS" -gt 0 ] 2>/dev/null && echo true || echo false)
GRADER_WORKING=$([ "$GRADER_STORAGE_OK" = "true" ] && [ "$GRADER_HAS_PREDS" = "true" ] && echo true || echo false)

check "Grader storage working with predictions" \
    "$GRADER_WORKING" \
    "storage=$GRADER_STORAGE, predictions=$GRADER_PREDS" \
    "storage path set AND predictions > 0"

# CHECK 8: Grader is available
echo -e "${YELLOW}[CHECK 8] Grader is available${NC}"
check "Grader available = true" \
    "$GRADER_AVAILABLE" \
    "$GRADER_AVAILABLE" \
    "true"

# Summary
echo ""
echo "=============================================="
TOTAL=$((PASSED + FAILED))
echo "SESSION 2 RESULTS: $PASSED/$TOTAL checks passed"

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}SESSION 2 SPOT CHECK: FAILED${NC}"
    echo "=============================================="
    exit 1
else
    echo -e "${GREEN}SESSION 2 SPOT CHECK: ALL PASS${NC}"
    echo "=============================================="
    exit 0
fi
