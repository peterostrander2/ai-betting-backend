#!/usr/bin/env bash
set -euo pipefail

# Validates frontend scoring contract matches backend
BACKEND_ROOT="$HOME/Desktop/ai-betting-backend-main"
FRONTEND_ROOT="$HOME/Desktop/bookie-member-app"

if [ ! -d "$FRONTEND_ROOT" ]; then
  echo "⚠️  Frontend repo not found at $FRONTEND_ROOT (skipping cross-repo sync check)"
  exit 0
fi

echo "Checking frontend/backend contract sync..."

# Extract values from backend
BACKEND_MIN=$(grep "MIN_FINAL_SCORE = " "$BACKEND_ROOT/core/scoring_contract.py" | grep -oE "[0-9.]+" | head -1)
BACKEND_GOLD=$(grep "GOLD_STAR_THRESHOLD = " "$BACKEND_ROOT/core/scoring_contract.py" | grep -oE "[0-9.]+" | head -1)
BACKEND_TITANIUM=$(grep "TITANIUM_MIN_ENGINES_GTE = " "$BACKEND_ROOT/core/scoring_contract.py" | grep -oE "[0-9]+" | head -1)

# Extract values from frontend
FRONTEND_MIN=$(grep "MIN_FINAL_SCORE" "$FRONTEND_ROOT/core/frontend_scoring_contract.js" 2>/dev/null | grep -oE "[0-9.]+" | head -1 || echo "")
FRONTEND_GOLD=$(grep "GOLD_STAR_THRESHOLD" "$FRONTEND_ROOT/core/frontend_scoring_contract.js" 2>/dev/null | grep -oE "[0-9.]+" | head -1 || echo "")
FRONTEND_TITANIUM=$(grep "minEnginesGte" "$FRONTEND_ROOT/core/frontend_scoring_contract.js" 2>/dev/null | grep -oE "[0-9]+" | head -1 || echo "")

# If frontend contract doesn't exist yet, skip
if [ -z "$FRONTEND_MIN" ]; then
  echo "⚠️  Frontend contract not found or empty (skipping sync check)"
  exit 0
fi

# Compare
ERRORS=0

if [ "$BACKEND_MIN" != "$FRONTEND_MIN" ]; then
  echo "❌ MIN_FINAL_SCORE mismatch: backend=$BACKEND_MIN, frontend=$FRONTEND_MIN"
  ERRORS=$((ERRORS + 1))
fi

if [ "$BACKEND_GOLD" != "$FRONTEND_GOLD" ]; then
  echo "❌ GOLD_STAR_THRESHOLD mismatch: backend=$BACKEND_GOLD, frontend=$FRONTEND_GOLD"
  ERRORS=$((ERRORS + 1))
fi

if [ -n "$FRONTEND_TITANIUM" ] && [ "$BACKEND_TITANIUM" != "$FRONTEND_TITANIUM" ]; then
  echo "❌ TITANIUM minEnginesGte mismatch: backend=$BACKEND_TITANIUM, frontend=$FRONTEND_TITANIUM"
  ERRORS=$((ERRORS + 1))
fi

if [ $ERRORS -eq 0 ]; then
  echo "✅ Frontend/backend contracts in sync"
  exit 0
else
  echo ""
  echo "❌ Frontend/backend contract mismatch detected!"
  exit 1
fi
