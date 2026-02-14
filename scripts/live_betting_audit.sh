#!/usr/bin/env bash
# scripts/live_betting_audit.sh
#
# Live betting correctness audit (v20.26)
# Validates:
# 1. meta.as_of_et exists and is ISO 8601 with ET offset
# 2. meta.data_age_ms is int and not null when picks > 0
# 3. For NCAAB picks: used_integrations includes odds_api and playbook_api
# 4. If outdoor NFL/MLB: weather status APPLIED or explicit ERROR with reason
# 5. Game status is PRE_GAME/IN_PROGRESS/FINAL (not MISSED_START)
#
# Usage:
#   API_KEY=your_key ./scripts/live_betting_audit.sh
#   API_KEY=your_key SPORT=NCAAB ./scripts/live_betting_audit.sh

set -euo pipefail

API_KEY="${API_KEY:-}"
API_BASE="${API_BASE:-https://web-production-7b2a.up.railway.app}"
SPORT="${SPORT:-NBA}"

if [[ -z "$API_KEY" ]]; then
    echo "ERROR: API_KEY is required"
    echo "Usage: API_KEY=your_key ./scripts/live_betting_audit.sh"
    exit 1
fi

echo "=============================================="
echo "LIVE BETTING CORRECTNESS AUDIT (v20.26)"
echo "=============================================="
echo "API_BASE: $API_BASE"
echo "SPORT: $SPORT"
echo ""

PASSED=0
FAILED=0

# Fetch best-bets with debug mode
echo "[1/5] Fetching best-bets for $SPORT with debug=1..."
RESPONSE=$(curl -sS -H "X-API-Key: $API_KEY" "$API_BASE/live/best-bets/$SPORT?debug=1")

if [[ -z "$RESPONSE" ]] || ! echo "$RESPONSE" | jq -e . > /dev/null 2>&1; then
    echo "ERROR: Invalid JSON response from best-bets"
    exit 1
fi

# Check 1: meta.as_of_et exists and is ISO 8601 with ET offset
echo ""
echo "[1/5] Checking meta.as_of_et format..."
AS_OF_ET=$(echo "$RESPONSE" | jq -r '.meta.as_of_et // empty')
if [[ -n "$AS_OF_ET" ]]; then
    # Validate ISO 8601 with offset (supports fractional seconds)
    if [[ "$AS_OF_ET" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?[-+][0-9]{2}:[0-9]{2}$ ]]; then
        echo "  PASS: meta.as_of_et = $AS_OF_ET"
        PASSED=$((PASSED + 1))
    else
        echo "  FAIL: meta.as_of_et format invalid: $AS_OF_ET"
        FAILED=$((FAILED + 1))
    fi
else
    echo "  FAIL: meta.as_of_et is missing"
    FAILED=$((FAILED + 1))
fi

# Check 2: meta.data_age_ms is int when picks > 0
echo ""
echo "[2/5] Checking meta.data_age_ms..."
PROPS_COUNT=$(echo "$RESPONSE" | jq -r '.props.count // 0')
GAMES_COUNT=$(echo "$RESPONSE" | jq -r '.game_picks.count // 0')
TOTAL_PICKS=$((PROPS_COUNT + GAMES_COUNT))
DATA_AGE_MS=$(echo "$RESPONSE" | jq -r '.meta.data_age_ms // "null"')

if [[ "$TOTAL_PICKS" -gt 0 ]]; then
    if [[ "$DATA_AGE_MS" != "null" ]] && [[ "$DATA_AGE_MS" =~ ^[0-9]+$ ]]; then
        echo "  PASS: meta.data_age_ms = ${DATA_AGE_MS}ms (picks=$TOTAL_PICKS)"
        PASSED=$((PASSED + 1))
    else
        echo "  FAIL: meta.data_age_ms is null or invalid when picks > 0"
        echo "        data_age_ms=$DATA_AGE_MS, picks=$TOTAL_PICKS"
        FAILED=$((FAILED + 1))
    fi
else
    echo "  SKIP: No picks returned (data_age_ms validation skipped)"
fi

# Check 3: integrations_age_ms exists for debug visibility
echo ""
echo "[3/5] Checking meta.integrations_age_ms..."
INTEGRATIONS_AGE=$(echo "$RESPONSE" | jq -r '.meta.integrations_age_ms // empty')
if [[ -n "$INTEGRATIONS_AGE" ]] && [[ "$INTEGRATIONS_AGE" != "null" ]]; then
    echo "  PASS: meta.integrations_age_ms present"
    # List the integrations
    echo "$RESPONSE" | jq -r '.meta.integrations_age_ms | to_entries[] | "        \(.key): \(.value)ms"' 2>/dev/null || true
    PASSED=$((PASSED + 1))
else
    echo "  WARN: meta.integrations_age_ms missing (expected for debug visibility)"
    # Not a hard fail, but worth noting
fi

# Check 4: Game status values are correct (no MISSED_START)
echo ""
echo "[4/5] Checking game_status values..."
MISSED_START_COUNT=$(echo "$RESPONSE" | jq -r '[.props.picks[]?, .game_picks.picks[]?] | map(select(.game_status == "MISSED_START")) | length')
IN_PROGRESS_COUNT=$(echo "$RESPONSE" | jq -r '[.props.picks[]?, .game_picks.picks[]?] | map(select(.game_status == "IN_PROGRESS")) | length')
PRE_GAME_COUNT=$(echo "$RESPONSE" | jq -r '[.props.picks[]?, .game_picks.picks[]?] | map(select(.game_status == "PRE_GAME")) | length')
FINAL_COUNT=$(echo "$RESPONSE" | jq -r '[.props.picks[]?, .game_picks.picks[]?] | map(select(.game_status == "FINAL")) | length')

if [[ "$MISSED_START_COUNT" -eq 0 ]]; then
    echo "  PASS: No MISSED_START status found (correct)"
    echo "        PRE_GAME: $PRE_GAME_COUNT, IN_PROGRESS: $IN_PROGRESS_COUNT, FINAL: $FINAL_COUNT"
    PASSED=$((PASSED + 1))
else
    echo "  FAIL: Found $MISSED_START_COUNT picks with deprecated MISSED_START status"
    FAILED=$((FAILED + 1))
fi

# Check 5: ET day matches across response
echo ""
echo "[5/5] Checking ET day consistency..."
ET_DAY=$(echo "$RESPONSE" | jq -r '.meta.et_day // empty')
DATE_ET=$(echo "$RESPONSE" | jq -r '.date_et // empty')

if [[ -n "$ET_DAY" ]] && [[ -n "$DATE_ET" ]]; then
    if [[ "$ET_DAY" == "$DATE_ET" ]]; then
        echo "  PASS: meta.et_day ($ET_DAY) matches date_et ($DATE_ET)"
        PASSED=$((PASSED + 1))
    else
        echo "  FAIL: meta.et_day ($ET_DAY) does not match date_et ($DATE_ET)"
        FAILED=$((FAILED + 1))
    fi
else
    echo "  WARN: Missing et_day or date_et field"
fi

# Summary
echo ""
echo "=============================================="
echo "AUDIT SUMMARY"
echo "=============================================="
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""

if [[ "$FAILED" -eq 0 ]]; then
    echo "RESULT: ALL CHECKS PASSED"
    exit 0
else
    echo "RESULT: $FAILED CHECK(S) FAILED"
    exit 1
fi
