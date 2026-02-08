#!/bin/bash
# verify_lstm_props.sh - Verify LSTM is being used for props when models exist
#
# Usage: ./scripts/verify_lstm_props.sh [SPORT]
#
# Checks:
# 1. LSTM model files exist for the sport
# 2. Props for that sport use LSTM (ai_mode == "ML_LSTM")
# 3. Fallbacks are properly documented (ai_reasons explain why)

set -e

SPORT="${1:-NBA}"
SPORT_UPPER=$(echo "$SPORT" | tr '[:lower:]' '[:upper:]')
SPORT_LOWER=$(echo "$SPORT" | tr '[:upper:]' '[:lower:]')

API_BASE="${API_BASE:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-}"

echo "================================================"
echo "LSTM Props Verification - $SPORT_UPPER"
echo "================================================"
echo ""

# Check 1: Model files exist locally
echo "[1/4] Checking local LSTM model files..."
MODEL_DIR="./models"
MODELS_FOUND=0
MODELS_MISSING=0

case "$SPORT_UPPER" in
    NBA)
        EXPECTED_MODELS=("points" "assists" "rebounds")
        ;;
    NFL)
        EXPECTED_MODELS=("passing_yards" "rushing_yards" "receiving_yards")
        ;;
    MLB)
        EXPECTED_MODELS=("hits" "total_bases" "strikeouts")
        ;;
    NHL)
        EXPECTED_MODELS=("points" "shots")
        ;;
    NCAAB)
        EXPECTED_MODELS=("points" "rebounds")
        ;;
    *)
        echo "Unknown sport: $SPORT_UPPER"
        exit 1
        ;;
esac

for stat in "${EXPECTED_MODELS[@]}"; do
    MODEL_FILE="$MODEL_DIR/lstm_${SPORT_LOWER}_${stat}.weights.h5"
    if [ -f "$MODEL_FILE" ]; then
        echo "  ✅ $MODEL_FILE exists"
        MODELS_FOUND=$((MODELS_FOUND + 1))
    else
        echo "  ❌ $MODEL_FILE MISSING"
        MODELS_MISSING=$((MODELS_MISSING + 1))
    fi
done

echo ""
echo "Models: $MODELS_FOUND found, $MODELS_MISSING missing"
echo ""

# Check 2: API returns props with LSTM
if [ -z "$API_KEY" ]; then
    echo "[2/4] Skipping API check (API_KEY not set)"
    echo "  Set API_KEY environment variable to check production"
    echo ""
else
    echo "[2/4] Checking $SPORT_UPPER props from API..."
    RESPONSE=$(curl -s "$API_BASE/live/best-bets/$SPORT_UPPER?debug=1" -H "X-API-Key: $API_KEY")

    PROPS_COUNT=$(echo "$RESPONSE" | jq '.props.count // 0')
    echo "  Props count: $PROPS_COUNT"

    if [ "$PROPS_COUNT" -gt 0 ]; then
        # Check ai_mode for each prop
        LSTM_COUNT=$(echo "$RESPONSE" | jq '[.props.picks[] | select(.ai_mode == "ML_LSTM")] | length')
        HEURISTIC_COUNT=$(echo "$RESPONSE" | jq '[.props.picks[] | select(.ai_mode == "HEURISTIC_FALLBACK")] | length')
        UNKNOWN_COUNT=$(echo "$RESPONSE" | jq '[.props.picks[] | select(.ai_mode == "UNKNOWN" or .ai_mode == null)] | length')

        echo "  LSTM (ML_LSTM): $LSTM_COUNT"
        echo "  Heuristic (HEURISTIC_FALLBACK): $HEURISTIC_COUNT"
        echo "  Unknown: $UNKNOWN_COUNT"
        echo ""

        # Show sample props
        echo "[3/4] Sample props (first 3):"
        echo "$RESPONSE" | jq -r '.props.picks[0:3][] | "  - \(.player_name // "Unknown"): \(.market) → ai_mode=\(.ai_mode // "N/A"), ai_reasons[0]=\(.ai_reasons[0] // "N/A")"'
        echo ""

        # Check for fallback reasons
        echo "[4/4] Fallback analysis:"
        FALLBACK_REASONS=$(echo "$RESPONSE" | jq -r '[.props.picks[] | select(.ai_mode == "HEURISTIC_FALLBACK") | .ai_reasons[0]] | unique | .[]')
        if [ -n "$FALLBACK_REASONS" ]; then
            echo "  Fallback reasons found:"
            echo "$FALLBACK_REASONS" | while read -r reason; do
                echo "    - $reason"
            done
        else
            echo "  No fallbacks (all props using LSTM) ✅"
        fi
    else
        echo "  No props available for $SPORT_UPPER today"
    fi
fi

echo ""
echo "================================================"
if [ "$MODELS_MISSING" -eq 0 ]; then
    echo "✅ All expected LSTM models exist for $SPORT_UPPER"
else
    echo "⚠️  $MODELS_MISSING models missing for $SPORT_UPPER"
fi
echo "================================================"
