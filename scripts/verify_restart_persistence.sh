#!/bin/bash
# Verify pick persistence survives Railway restart
set -euo pipefail

BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"

echo "=============================================================="
echo "RESTART PERSISTENCE TEST"
echo "=============================================================="

# Get count before
BEFORE="$(curl -s "${BASE_URL}/live/grader/status" -H "X-API-Key: ${API_KEY}" | jq -r '.grader_store.predictions_logged // 0')"
echo "Predictions before restart: $BEFORE"

echo ""
echo "ACTION REQUIRED:"
echo "1. Restart Railway container (Dashboard > Deployments > Restart)"
echo "2. Wait 2 minutes for restart to complete"
echo "3. Press ENTER to verify persistence"
read -r

# Get count after
AFTER="$(curl -s "${BASE_URL}/live/grader/status" -H "X-API-Key: ${API_KEY}" | jq -r '.grader_store.predictions_logged // 0')"
echo "Predictions after restart: $AFTER"

if [ "$BEFORE" -ne "$AFTER" ]; then
  echo "❌ FAIL: Predictions lost during restart ($BEFORE → $AFTER)"
  exit 1
fi

echo "✅ PASS: Predictions survived restart ($BEFORE = $AFTER)"
