#!/bin/bash
# Contract Sync Check - Verifies frontend and backend contracts match
# Usage: ./scripts/contract_sync_check.sh

set -e

BACKEND_DIR="$HOME/ai-betting-backend"
FRONTEND_DIR="$HOME/bookie-member-app"

echo "============================================"
echo "CONTRACT SYNC CHECK"
echo "============================================"
echo "Time: $(date)"
echo ""

ISSUES=0

# 1. Check tier thresholds match
echo "[1/4] Checking tier thresholds..."

BACKEND_GOLD=$(grep -o "GOLD_STAR_THRESHOLD = [0-9.]*" "$BACKEND_DIR/core/scoring_contract.py" 2>/dev/null | grep -o "[0-9.]*")
FRONTEND_GOLD=$(grep -o "GOLD_STAR_THRESHOLD = [0-9.]*" "$FRONTEND_DIR/core/frontend_scoring_contract.js" 2>/dev/null | grep -o "[0-9.]*")

if [ "$BACKEND_GOLD" = "$FRONTEND_GOLD" ]; then
    echo "  ✅ GOLD_STAR_THRESHOLD: $BACKEND_GOLD"
else
    echo "  ❌ GOLD_STAR_THRESHOLD mismatch: backend=$BACKEND_GOLD, frontend=$FRONTEND_GOLD"
    ISSUES=$((ISSUES + 1))
fi

BACKEND_MIN=$(grep -o "MIN_FINAL_SCORE = [0-9.]*" "$BACKEND_DIR/core/scoring_contract.py" 2>/dev/null | grep -o "[0-9.]*")
FRONTEND_MIN=$(grep -o "MIN_FINAL_SCORE = [0-9.]*" "$FRONTEND_DIR/core/frontend_scoring_contract.js" 2>/dev/null | grep -o "[0-9.]*")

if [ "$BACKEND_MIN" = "$FRONTEND_MIN" ]; then
    echo "  ✅ MIN_FINAL_SCORE: $BACKEND_MIN"
else
    echo "  ❌ MIN_FINAL_SCORE mismatch: backend=$BACKEND_MIN, frontend=$FRONTEND_MIN"
    ISSUES=$((ISSUES + 1))
fi

# 2. Check API endpoints exist
echo ""
echo "[2/4] Checking API endpoints..."

API_URL="https://web-production-7b2a.up.railway.app"

for endpoint in "/health" "/esoteric/today-energy"; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL$endpoint" 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
        echo "  ✅ $endpoint: $STATUS"
    else
        echo "  ❌ $endpoint: $STATUS"
        ISSUES=$((ISSUES + 1))
    fi
done

# 3. Check required frontend files exist
echo ""
echo "[3/4] Checking required frontend files..."

REQUIRED_FILES=(
    "core/frontend_scoring_contract.js"
    "api.js"
    "App.jsx"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$FRONTEND_DIR/$file" ]; then
        echo "  ✅ $file exists"
    else
        echo "  ❌ $file missing"
        ISSUES=$((ISSUES + 1))
    fi
done

# 4. Check for engine weight consistency
echo ""
echo "[4/4] Checking engine weights..."

# Extract weights from frontend contract
FRONTEND_WEIGHTS=$(grep -A5 "ENGINE_WEIGHTS" "$FRONTEND_DIR/core/frontend_scoring_contract.js" 2>/dev/null | grep -o "[0-9]\.[0-9]*" | head -4 | tr '\n' ' ')
echo "  Frontend weights: $FRONTEND_WEIGHTS"

# Check they sum to 1.0
WEIGHT_SUM=$(echo "$FRONTEND_WEIGHTS" | awk '{sum=0; for(i=1;i<=NF;i++) sum+=$i; print sum}')
if [ "$(echo "$WEIGHT_SUM == 1" | bc 2>/dev/null)" = "1" ] || [ "$WEIGHT_SUM" = "1" ]; then
    echo "  ✅ Weights sum to 1.0"
else
    echo "  ⚠️  Weights sum to $WEIGHT_SUM (expected 1.0)"
fi

echo ""
echo "============================================"
if [ "$ISSUES" -gt 0 ]; then
    echo "❌ SYNC CHECK FAILED: $ISSUES issues found"
    exit 1
else
    echo "✅ SYNC CHECK PASSED: All contracts aligned"
    exit 0
fi
