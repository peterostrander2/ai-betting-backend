#!/bin/bash
# Option A Drift Scan - Fail fast on forbidden scoring patterns

set -e

SCORING_FILES=(
  "core/scoring_contract.py"
  "core/scoring_pipeline.py"
  "live_data_router.py"
  "core/invariants.py"
)

FORBIDDEN_PATTERNS=(
  "BASE_5"
  "ENGINE_WEIGHTS\\[\\s*\"context\"\\s*\\]"
  "ENGINE_WEIGHTS\\[\\s*'context'\\s*\\]"
  "ENGINE_WEIGHT_CONTEXT"
  "CONTEXT_WEIGHT"
  "context(_score|_modifier)?\\s*\\*\\s*(ENGINE_WEIGHTS|context_weight|weight)"
)

FOUND=0

if command -v rg >/dev/null 2>&1; then
  for pat in "${FORBIDDEN_PATTERNS[@]}"; do
    if rg -n -P "$pat" "${SCORING_FILES[@]}"; then
      FOUND=1
    fi
  done
else
  for pat in "${FORBIDDEN_PATTERNS[@]}"; do
    if grep -nE "$pat" "${SCORING_FILES[@]}"; then
      FOUND=1
    fi
  done
fi

if [ "$FOUND" -ne 0 ]; then
  echo "ERROR: Option A drift detected (forbidden scoring pattern found)."
  exit 1
fi

echo "Option A drift scan: PASS"
