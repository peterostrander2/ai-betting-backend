#!/bin/bash
# POST-DEPLOY VERIFICATION
# Run after every Railway deployment to catch runtime/env drift
# Usage: ./scripts/post_deploy_check.sh

set -euo pipefail

BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"

echo "============================================"
echo "POST-DEPLOY VERIFICATION"
echo "Base URL: $BASE_URL"
echo "Time: $(date)"
echo "============================================"
echo ""

PASS=0
FAIL=0

check() {
  local name="$1"
  local result="$2"
  if [ "$result" = "true" ]; then
    echo "✅ $name"
    PASS=$((PASS + 1))
  else
    echo "❌ $name"
    FAIL=$((FAIL + 1))
  fi
}

# 1. Health endpoint
echo "[1/4] Health endpoint..."
HEALTH=$(curl -s "$BASE_URL/health" -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")
HEALTH_OK=$(echo "$HEALTH" | jq -r '.status == "healthy"' 2>/dev/null || echo "false")
check "Health: status=healthy" "$HEALTH_OK"

# 2. Storage health
echo "[2/4] Storage health..."
STORAGE=$(curl -s "$BASE_URL/internal/storage/health" -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")
STORAGE_OK=$(echo "$STORAGE" | jq -r '.ok == true and .is_mountpoint == true and .predictions_exists == true' 2>/dev/null || echo "false")
PRED_COUNT=$(echo "$STORAGE" | jq -r '.predictions_line_count // 0' 2>/dev/null || echo "0")
check "Storage: mounted, predictions exist ($PRED_COUNT picks)" "$STORAGE_OK"

# 3. Integrations
echo "[3/4] Integrations..."
INTEGRATIONS=$(curl -s "$BASE_URL/live/debug/integrations" -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")
INT_STATUS=$(echo "$INTEGRATIONS" | jq -r '.overall_status' 2>/dev/null || echo "UNKNOWN")
VALIDATED=$(echo "$INTEGRATIONS" | jq -r '.by_status.validated | length' 2>/dev/null || echo "0")
NOT_CONFIGURED=$(echo "$INTEGRATIONS" | jq -r '.by_status.not_configured | length' 2>/dev/null || echo "0")
INT_OK=$([ "$INT_STATUS" = "HEALTHY" ] && [ "$NOT_CONFIGURED" = "0" ] && echo "true" || echo "false")
check "Integrations: $INT_STATUS ($VALIDATED validated, $NOT_CONFIGURED missing)" "$INT_OK"

# 4. Scheduler status
echo "[4/4] Scheduler status..."
SCHEDULER=$(curl -s "$BASE_URL/live/scheduler/status" -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")
SCHED_OK=$(echo "$SCHEDULER" | jq -r '.available == true and .apscheduler_available == true' 2>/dev/null || echo "false")
AUDIT_TIME=$(echo "$SCHEDULER" | jq -r '.audit_time // "unknown"' 2>/dev/null || echo "unknown")
check "Scheduler: available, audit at $AUDIT_TIME" "$SCHED_OK"

echo ""
echo "============================================"
if [ "$FAIL" -eq 0 ]; then
  echo "✅ ALL $PASS CHECKS PASSED"
  echo "Production is healthy after deploy."
  exit 0
else
  echo "❌ $FAIL CHECKS FAILED ($PASS passed)"
  echo "Investigate before proceeding!"
  exit 1
fi
