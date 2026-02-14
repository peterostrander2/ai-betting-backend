#!/usr/bin/env bash
#
# v20.22 Sklearn Shadow Mode Verification Script
#
# Purpose: Verify sklearn ensemble regressors are training correctly in shadow mode
#          and determine if they're ready for live production use.
#
# Run after 7+ days of shadow training (target date: Feb 21, 2026)
#
# Usage:
#   API_KEY=your_key ./scripts/verify_sklearn_shadow.sh
#
# Exit codes:
#   0 = Ready to enable (all checks passed)
#   1 = Not ready (insufficient data or training issues)
#   2 = Missing API_KEY

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BASE_URL="${API_BASE:-https://web-production-7b2a.up.railway.app}"

echo "============================================================"
echo "  v20.22 SKLEARN SHADOW MODE VERIFICATION"
echo "  Target: Engine 1 - Ensemble Stacking Model"
echo "  Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# Check API_KEY
if [[ -z "${API_KEY:-}" ]]; then
    echo -e "${RED}ERROR: API_KEY environment variable required${NC}"
    echo "Usage: API_KEY=your_key ./scripts/verify_sklearn_shadow.sh"
    exit 2
fi

PASSED=0
FAILED=0
WARNINGS=0

# Helper function for checks
check_pass() {
    echo -e "${GREEN}✓ $1${NC}"
    PASSED=$((PASSED + 1))
}

check_fail() {
    echo -e "${RED}✗ $1${NC}"
    FAILED=$((FAILED + 1))
}

check_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
    WARNINGS=$((WARNINGS + 1))
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}[1/5] Checking Training Status...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TRAINING_STATUS=$(curl -s "${BASE_URL}/live/debug/training-status" \
    -H "X-API-Key: ${API_KEY}" 2>/dev/null || echo '{"error": "fetch_failed"}')

# Extract sklearn status (nested under model_status.sklearn_status)
SKLEARN_MODE=$(echo "$TRAINING_STATUS" | jq -r '.model_status.sklearn_status.sklearn_mode // "UNKNOWN"')
SKLEARN_TRAINED=$(echo "$TRAINING_STATUS" | jq -r '.model_status.sklearn_status.sklearn_trained // false')
MODELS_EXIST=$(echo "$TRAINING_STATUS" | jq -r '.model_status.sklearn_status.models_exist // false')
LAST_TRAIN_TIME=$(echo "$TRAINING_STATUS" | jq -r '.model_status.sklearn_status.last_train_time // "never"')
TRAINING_SAMPLES=$(echo "$TRAINING_STATUS" | jq -r '.model_status.sklearn_status.training_samples // 0')

echo "  Sklearn Mode:      $SKLEARN_MODE"
echo "  Sklearn Trained:   $SKLEARN_TRAINED"
echo "  Models Exist:      $MODELS_EXIST"
echo "  Last Train Time:   $LAST_TRAIN_TIME"
echo "  Training Samples:  $TRAINING_SAMPLES"
echo ""

if [[ "$SKLEARN_MODE" == "SHADOW" ]]; then
    check_pass "Running in SHADOW mode (expected)"
elif [[ "$SKLEARN_MODE" == "LIVE" ]]; then
    check_warn "Already in LIVE mode - sklearn affecting scores"
else
    check_fail "Sklearn mode is $SKLEARN_MODE (expected SHADOW)"
fi

if [[ "$MODELS_EXIST" == "true" ]]; then
    check_pass "Sklearn models file exists"
else
    check_fail "Sklearn models file not found - training may not be running"
fi

if [[ "$TRAINING_SAMPLES" -ge 50 ]]; then
    check_pass "Sufficient training samples: $TRAINING_SAMPLES (min: 50)"
elif [[ "$TRAINING_SAMPLES" -gt 0 ]]; then
    check_warn "Low training samples: $TRAINING_SAMPLES (need 50+)"
else
    check_fail "No training samples recorded"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}[2/5] Checking Score Capture (Matchup Model Data)...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

GRADED_PICKS=$(curl -s "${BASE_URL}/live/picks/graded?limit=100" \
    -H "X-API-Key: ${API_KEY}" 2>/dev/null || echo '{"picks":[]}')

# Handle both array response and object with picks array
TOTAL_GRADED=$(echo "$GRADED_PICKS" | jq 'if type == "array" then length else (.picks // []) | length end')
WITH_SCORES=$(echo "$GRADED_PICKS" | jq 'if type == "array" then [.[] | select(.actual_home_score != null)] | length else [(.picks // [])[] | select(.actual_home_score != null)] | length end')

echo "  Total Graded Picks:     $TOTAL_GRADED"
echo "  Picks with Scores:      $WITH_SCORES"
echo ""

if [[ "$WITH_SCORES" -gt 0 ]]; then
    check_pass "Score capture working: $WITH_SCORES picks have actual scores"

    # Show sample
    echo ""
    echo "  Sample pick with scores:"
    echo "$GRADED_PICKS" | jq -r '
        (if type == "array" then . else (.picks // []) end) |
        [.[] | select(.actual_home_score != null)][0] // null |
        if . then "    Pick: \(.matchup // "N/A")\n    Result: \(.result // "N/A")\n    Home Score: \(.actual_home_score)\n    Away Score: \(.actual_away_score)" else "    (no sample available)" end
    ' 2>/dev/null || echo "    (no sample available)"
else
    check_warn "No picks with actual scores yet - need more graded games"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}[3/5] Checking Training Health...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TRAINING_HEALTH=$(echo "$TRAINING_STATUS" | jq -r '.training_health // "UNKNOWN"')
GRADED_SAMPLES_SEEN=$(echo "$TRAINING_STATUS" | jq -r '.training_telemetry.graded_samples_seen // 0')
SAMPLES_USED=$(echo "$TRAINING_STATUS" | jq -r '.training_telemetry.samples_used_for_training // 0')

echo "  Training Health:        $TRAINING_HEALTH"
echo "  Graded Samples Seen:    $GRADED_SAMPLES_SEEN"
echo "  Samples Used:           $SAMPLES_USED"
echo ""

if [[ "$TRAINING_HEALTH" == "HEALTHY" ]]; then
    check_pass "Training health is HEALTHY"
elif [[ "$TRAINING_HEALTH" == "STALE" ]]; then
    check_warn "Training is STALE - may need manual trigger"
else
    check_fail "Training health: $TRAINING_HEALTH"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}[4/5] Checking Model Artifacts...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check artifact proof
SKLEARN_ARTIFACT=$(echo "$TRAINING_STATUS" | jq -r '
    .artifact_proof | to_entries[] |
    select(.key | contains("sklearn") or contains("ensemble")) |
    "\(.key): exists=\(.value.exists // false), size=\(.value.size_bytes // 0)"
' 2>/dev/null || echo "not found")

if [[ -n "$SKLEARN_ARTIFACT" && "$SKLEARN_ARTIFACT" != "not found" ]]; then
    echo "  $SKLEARN_ARTIFACT"
    check_pass "Sklearn artifact info available"
else
    # Check models_exist from sklearn_status
    if [[ "$MODELS_EXIST" == "true" ]]; then
        echo "  Sklearn models file: exists"
        check_pass "Sklearn models exist (from status)"
    else
        check_warn "Sklearn artifact info not in response - check manually"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}[5/5] Days Since Shadow Mode Started...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Shadow mode started Feb 14, 2026
SHADOW_START="2026-02-14"
TODAY=$(date '+%Y-%m-%d')

# Calculate days (macOS compatible)
if command -v gdate &> /dev/null; then
    # GNU date available
    START_SEC=$(gdate -d "$SHADOW_START" +%s)
    TODAY_SEC=$(gdate -d "$TODAY" +%s)
else
    # macOS date
    START_SEC=$(date -j -f "%Y-%m-%d" "$SHADOW_START" +%s 2>/dev/null || echo "0")
    TODAY_SEC=$(date +%s)
fi

if [[ "$START_SEC" != "0" ]]; then
    DAYS_ELAPSED=$(( (TODAY_SEC - START_SEC) / 86400 ))
    echo "  Shadow mode started: $SHADOW_START"
    echo "  Days elapsed:        $DAYS_ELAPSED"
    echo ""

    if [[ "$DAYS_ELAPSED" -ge 7 ]]; then
        check_pass "7+ days of data accumulated ($DAYS_ELAPSED days)"
    else
        DAYS_REMAINING=$((7 - DAYS_ELAPSED))
        check_warn "Only $DAYS_ELAPSED days - wait $DAYS_REMAINING more days (target: 7)"
    fi
else
    echo "  Unable to calculate days (date parsing issue)"
    check_warn "Could not verify days elapsed"
fi

echo ""
echo "============================================================"
echo "  VERIFICATION SUMMARY"
echo "============================================================"
echo ""
echo -e "  ${GREEN}Passed:${NC}   $PASSED"
echo -e "  ${YELLOW}Warnings:${NC} $WARNINGS"
echo -e "  ${RED}Failed:${NC}   $FAILED"
echo ""

if [[ "$FAILED" -eq 0 && "$WARNINGS" -eq 0 ]]; then
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ READY TO ENABLE LIVE MODE${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  To enable sklearn for live predictions:"
    echo ""
    echo "  1. Go to Railway Dashboard → Variables"
    echo "  2. Add: ENSEMBLE_SKLEARN_ENABLED=true"
    echo "  3. Redeploy will happen automatically"
    echo ""
    echo "  After enabling, monitor:"
    echo "  - Score distribution (watch for drift)"
    echo "  - Pick quality metrics"
    echo "  - /live/debug/training-status (sklearn_mode should be LIVE)"
    echo ""
    exit 0
elif [[ "$FAILED" -eq 0 ]]; then
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  ⚠ ALMOST READY - Review warnings above${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  You can enable live mode, but address warnings first:"
    echo "  - Ensure sufficient training data accumulates"
    echo "  - Verify training is running daily at 7:15 AM ET"
    echo ""
    exit 0
else
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  ✗ NOT READY - Fix issues above before enabling${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Common fixes:"
    echo "  - Check Railway logs for training errors at 7:15 AM ET"
    echo "  - Verify dependencies (xgboost, lightgbm, scikit-learn)"
    echo "  - Check /data/models/ directory permissions"
    echo ""
    exit 1
fi
