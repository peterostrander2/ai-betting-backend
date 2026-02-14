#!/usr/bin/env bash
# scripts/live_betting_audit_all_sports.sh
#
# Cross-Sport Live Betting Correctness Audit (v20.28)
# Runs live_betting_audit.sh for ALL supported sports
#
# Usage:
#   API_KEY=your_key ./scripts/live_betting_audit_all_sports.sh
#   API_KEY=your_key API_BASE=https://custom.url ./scripts/live_betting_audit_all_sports.sh
#
# Exit codes:
#   0 = All sports passed (or NOT_APPLICABLE_NO_SLATE)
#   1 = One or more sports failed critical checks

set -euo pipefail

API_KEY="${API_KEY:-}"
API_BASE="${API_BASE:-https://web-production-7b2a.up.railway.app}"

if [[ -z "$API_KEY" ]]; then
    echo "ERROR: API_KEY is required"
    echo "Usage: API_KEY=your_key ./scripts/live_betting_audit_all_sports.sh"
    exit 1
fi

# Sports to audit
SPORTS=("NBA" "NCAAB" "NFL" "MLB" "NHL")

# Counters
PASSED_SPORTS=0
FAILED_SPORTS=0
NO_SLATE_SPORTS=0

echo "=============================================="
echo "CROSS-SPORT LIVE BETTING AUDIT (v20.28)"
echo "=============================================="
echo "API_BASE: $API_BASE"
echo "Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo ""

for SPORT in "${SPORTS[@]}"; do
    echo "----------------------------------------------"
    echo "AUDITING: $SPORT"
    echo "----------------------------------------------"

    # Fetch best-bets with debug mode
    RESPONSE=$(curl -sS -H "X-API-Key: $API_KEY" "$API_BASE/live/best-bets/$SPORT?debug=1" 2>&1 || echo '{"error": "curl_failed"}')

    # Check for curl failure
    if echo "$RESPONSE" | grep -q "curl_failed"; then
        echo "  ERROR: Failed to fetch $SPORT best-bets"
        FAILED_SPORTS=$((FAILED_SPORTS + 1))
        continue
    fi

    # Check for valid JSON
    if ! echo "$RESPONSE" | jq -e . > /dev/null 2>&1; then
        echo "  ERROR: Invalid JSON response for $SPORT"
        FAILED_SPORTS=$((FAILED_SPORTS + 1))
        continue
    fi

    # Check for API error response
    if echo "$RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
        echo "  ERROR: API returned error for $SPORT: $(echo "$RESPONSE" | jq -r '.error')"
        FAILED_SPORTS=$((FAILED_SPORTS + 1))
        continue
    fi

    # Get pick counts
    PROPS_COUNT=$(echo "$RESPONSE" | jq -r '.props.count // 0')
    GAMES_COUNT=$(echo "$RESPONSE" | jq -r '.game_picks.count // 0')
    TOTAL_PICKS=$((PROPS_COUNT + GAMES_COUNT))

    # Check if no slate (no games today)
    CANDIDATES_PROPS=$(echo "$RESPONSE" | jq -r '.debug.ai_variance_stats.props.count // 0')
    CANDIDATES_GAMES=$(echo "$RESPONSE" | jq -r '.debug.ai_variance_stats.games.count // 0')
    TOTAL_CANDIDATES=$((CANDIDATES_PROPS + CANDIDATES_GAMES))

    if [[ "$TOTAL_CANDIDATES" -eq 0 ]]; then
        echo "  NOT_APPLICABLE_NO_SLATE: No games scheduled for $SPORT today"

        # Still verify endpoint returns 200 with correct structure
        HAS_PROPS=$(echo "$RESPONSE" | jq -e '.props' > /dev/null 2>&1 && echo "yes" || echo "no")
        HAS_GAMES=$(echo "$RESPONSE" | jq -e '.game_picks' > /dev/null 2>&1 && echo "yes" || echo "no")
        HAS_META=$(echo "$RESPONSE" | jq -e '.meta' > /dev/null 2>&1 && echo "yes" || echo "no")

        if [[ "$HAS_PROPS" == "yes" && "$HAS_GAMES" == "yes" && "$HAS_META" == "yes" ]]; then
            echo "  PASS: Response structure valid (props, game_picks, meta present)"
            NO_SLATE_SPORTS=$((NO_SLATE_SPORTS + 1))
        else
            echo "  FAIL: Invalid response structure"
            FAILED_SPORTS=$((FAILED_SPORTS + 1))
        fi
        continue
    fi

    # --- CRITICAL CHECKS (must pass) ---
    SPORT_PASSED=0
    SPORT_FAILED=0

    # Check 1: meta.as_of_et exists and is ISO 8601 with ET offset
    AS_OF_ET=$(echo "$RESPONSE" | jq -r '.meta.as_of_et // empty')
    if [[ -n "$AS_OF_ET" ]]; then
        if [[ "$AS_OF_ET" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?[-+][0-9]{2}:[0-9]{2}$ ]]; then
            echo "  PASS: meta.as_of_et format valid"
            SPORT_PASSED=$((SPORT_PASSED + 1))
        else
            echo "  FAIL: meta.as_of_et format invalid: $AS_OF_ET"
            SPORT_FAILED=$((SPORT_FAILED + 1))
        fi
    else
        echo "  FAIL: meta.as_of_et missing"
        SPORT_FAILED=$((SPORT_FAILED + 1))
    fi

    # Check 2: meta.data_age_ms is int when picks > 0
    DATA_AGE_MS=$(echo "$RESPONSE" | jq -r '.meta.data_age_ms // "null"')
    if [[ "$TOTAL_PICKS" -gt 0 ]]; then
        if [[ "$DATA_AGE_MS" != "null" ]] && [[ "$DATA_AGE_MS" =~ ^[0-9]+$ ]]; then
            echo "  PASS: meta.data_age_ms = ${DATA_AGE_MS}ms"
            SPORT_PASSED=$((SPORT_PASSED + 1))
        else
            echo "  FAIL: meta.data_age_ms invalid when picks > 0 (got: $DATA_AGE_MS)"
            SPORT_FAILED=$((SPORT_FAILED + 1))
        fi
    else
        echo "  SKIP: No picks - data_age_ms check skipped"
    fi

    # Check 3: No MISSED_START status
    MISSED_START_COUNT=$(echo "$RESPONSE" | jq -r '[.props.picks[]?, .game_picks.picks[]?] | map(select(.game_status == "MISSED_START")) | length')
    if [[ "$MISSED_START_COUNT" -eq 0 ]]; then
        echo "  PASS: No deprecated MISSED_START status"
        SPORT_PASSED=$((SPORT_PASSED + 1))
    else
        echo "  FAIL: Found $MISSED_START_COUNT picks with MISSED_START"
        SPORT_FAILED=$((SPORT_FAILED + 1))
    fi

    # Check 4: AI score variance (only if >= 5 candidates)
    if [[ "$CANDIDATES_GAMES" -ge 5 ]]; then
        UNIQUE_AI_SCORES=$(echo "$RESPONSE" | jq -r '.debug.ai_variance_stats.games.unique_ai_scores // 0')
        AI_STDDEV=$(echo "$RESPONSE" | jq -r '.debug.ai_variance_stats.games.ai_score_stddev // 0')

        if [[ "$UNIQUE_AI_SCORES" -ge 4 ]]; then
            # Check stddev using bc for float comparison
            if [[ $(echo "$AI_STDDEV >= 0.15" | bc -l 2>/dev/null || echo "0") -eq 1 ]]; then
                echo "  PASS: AI variance OK (unique=$UNIQUE_AI_SCORES, stddev=$AI_STDDEV)"
                SPORT_PASSED=$((SPORT_PASSED + 1))
            else
                echo "  FAIL: AI stddev too low ($AI_STDDEV < 0.15)"
                SPORT_FAILED=$((SPORT_FAILED + 1))
            fi
        else
            echo "  FAIL: AI scores degenerate (only $UNIQUE_AI_SCORES unique for $CANDIDATES_GAMES games)"
            SPORT_FAILED=$((SPORT_FAILED + 1))
        fi
    else
        echo "  SKIP: Not enough candidates ($CANDIDATES_GAMES < 5) for variance check"
    fi

    # Check 5: market_counts_by_type present
    MARKET_COUNTS=$(echo "$RESPONSE" | jq -r '.debug.market_counts_by_type // empty')
    if [[ -n "$MARKET_COUNTS" ]] && [[ "$MARKET_COUNTS" != "null" ]]; then
        SPREAD_COUNT=$(echo "$RESPONSE" | jq -r '.debug.market_counts_by_type.SPREAD // 0')
        ML_COUNT=$(echo "$RESPONSE" | jq -r '.debug.market_counts_by_type.MONEYLINE // 0')
        TOTAL_COUNT=$(echo "$RESPONSE" | jq -r '.debug.market_counts_by_type.TOTAL // 0')
        echo "  PASS: market_counts_by_type present (SPREAD=$SPREAD_COUNT, ML=$ML_COUNT, TOTAL=$TOTAL_COUNT)"
        SPORT_PASSED=$((SPORT_PASSED + 1))
    else
        echo "  FAIL: market_counts_by_type missing"
        SPORT_FAILED=$((SPORT_FAILED + 1))
    fi

    # Check 6: 4 engine scores present on picks
    if [[ "$TOTAL_PICKS" -gt 0 ]]; then
        # Check first pick for all 4 engine scores
        FIRST_PICK=$(echo "$RESPONSE" | jq -r '.game_picks.picks[0] // .props.picks[0] // empty')
        if [[ -n "$FIRST_PICK" ]]; then
            HAS_AI=$(echo "$FIRST_PICK" | jq -e '.ai_score' > /dev/null 2>&1 && echo "yes" || echo "no")
            HAS_RESEARCH=$(echo "$FIRST_PICK" | jq -e '.research_score' > /dev/null 2>&1 && echo "yes" || echo "no")
            HAS_ESOTERIC=$(echo "$FIRST_PICK" | jq -e '.esoteric_score' > /dev/null 2>&1 && echo "yes" || echo "no")
            HAS_JARVIS=$(echo "$FIRST_PICK" | jq -e '.jarvis_score // .jarvis_rs' > /dev/null 2>&1 && echo "yes" || echo "no")

            if [[ "$HAS_AI" == "yes" && "$HAS_RESEARCH" == "yes" && "$HAS_ESOTERIC" == "yes" && "$HAS_JARVIS" == "yes" ]]; then
                echo "  PASS: All 4 engine scores present on picks"
                SPORT_PASSED=$((SPORT_PASSED + 1))
            else
                echo "  FAIL: Missing engine scores (AI=$HAS_AI, Research=$HAS_RESEARCH, Esoteric=$HAS_ESOTERIC, Jarvis=$HAS_JARVIS)"
                SPORT_FAILED=$((SPORT_FAILED + 1))
            fi
        fi
    else
        echo "  SKIP: No picks to check for engine scores"
    fi

    # Sport summary
    echo ""
    echo "  $SPORT Summary: $SPORT_PASSED passed, $SPORT_FAILED failed (candidates=$TOTAL_CANDIDATES, picks=$TOTAL_PICKS)"

    if [[ "$SPORT_FAILED" -eq 0 ]]; then
        PASSED_SPORTS=$((PASSED_SPORTS + 1))
    else
        FAILED_SPORTS=$((FAILED_SPORTS + 1))
    fi
done

# Final summary
echo ""
echo "=============================================="
echo "CROSS-SPORT AUDIT SUMMARY"
echo "=============================================="
echo "Sports Passed:    $PASSED_SPORTS"
echo "Sports Failed:    $FAILED_SPORTS"
echo "Sports No Slate:  $NO_SLATE_SPORTS"
echo ""

if [[ "$FAILED_SPORTS" -eq 0 ]]; then
    echo "RESULT: ALL SPORTS PASSED (or NO_SLATE)"
    exit 0
else
    echo "RESULT: $FAILED_SPORTS SPORT(S) FAILED"
    exit 1
fi
