#!/usr/bin/env bash
# check_weights_sanity.sh - Check all sports weights for drift and small-sample issues
# v20.28.6: Diagnostic script for learning loop health
#
# Usage:
#   API_KEY=your_key ./scripts/check_weights_sanity.sh
#   API_KEY=your_key BASE_URL=https://api.bookiebot.pro ./scripts/check_weights_sanity.sh

set -euo pipefail

API_KEY="${API_KEY:?API_KEY required}"
BASE_URL="${BASE_URL:-https://api.bookiebot.pro}"
BASELINE_SUM="0.73"  # Sum of core weights (defense, pace, vacuum, lstm, officials)
DRIFT_THRESHOLD="0.05"  # Alert if weights drift more than 5% from baseline

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "WEIGHTS SANITY CHECK - All Sports"
echo "========================================"
echo "Base URL: $BASE_URL"
echo "Baseline sum: $BASELINE_SUM"
echo "Drift threshold: $DRIFT_THRESHOLD"
echo ""

SPORTS=("NBA" "NFL" "NHL" "MLB" "NCAAB")
FAILED=0
WARNINGS=0

for sport in "${SPORTS[@]}"; do
    echo "----------------------------------------"
    echo "Checking $sport weights..."

    # Fetch weights for this sport
    response=$(curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/live/grader/weights/$sport" 2>/dev/null || echo '{"error":"fetch_failed"}')

    if echo "$response" | jq -e '.error' > /dev/null 2>&1; then
        echo -e "${RED}[ERROR] Failed to fetch $sport weights${NC}"
        echo "$response" | jq -r '.error // .detail // "unknown error"' 2>/dev/null || echo "$response"
        FAILED=$((FAILED + 1))
        continue
    fi

    # Check if weights exist
    if ! echo "$response" | jq -e '.weights' > /dev/null 2>&1; then
        echo -e "${YELLOW}[WARN] No weights found for $sport${NC}"
        WARNINGS=$((WARNINGS + 1))
        continue
    fi

    # Extract all stat types and their weights
    echo "$response" | jq -r '
        .weights | to_entries[] |
        "  \(.key): defense=\(.value.defense // "N/A") pace=\(.value.pace // "N/A") vacuum=\(.value.vacuum // "N/A") lstm=\(.value.lstm // "N/A") officials=\(.value.officials // "N/A")"
    ' 2>/dev/null || echo "  (unable to parse weights)"

    # Calculate weight sums for each stat type
    echo ""
    echo "  Weight sum analysis:"

    stat_types=$(echo "$response" | jq -r '.weights | keys[]' 2>/dev/null)
    for stat_type in $stat_types; do
        # Sum the core weights (defense, pace, vacuum, lstm, officials)
        sum=$(echo "$response" | jq -r "
            .weights.\"$stat_type\" |
            ((.defense // 0) + (.pace // 0) + (.vacuum // 0) + (.lstm // 0) + (.officials // 0))
        " 2>/dev/null || echo "0")

        # Calculate drift from baseline
        drift=$(echo "$sum - $BASELINE_SUM" | bc -l 2>/dev/null || echo "0")
        drift_abs=$(echo "$drift" | sed 's/^-//')

        # Check if drift exceeds threshold
        is_drifted=$(echo "$drift_abs > $DRIFT_THRESHOLD" | bc -l 2>/dev/null || echo "0")

        if [ "$is_drifted" = "1" ]; then
            echo -e "    ${RED}[DRIFT] $stat_type: sum=$sum (drift=$drift from baseline $BASELINE_SUM)${NC}"
            WARNINGS=$((WARNINGS + 1))
        else
            echo -e "    ${GREEN}[OK] $stat_type: sum=$sum${NC}"
        fi
    done

    echo ""
done

echo "========================================"
echo "Checking bias samples (small-sample detection)..."
echo "========================================"

for sport in "${SPORTS[@]}"; do
    echo ""
    echo "--- $sport bias ---"

    # Fetch bias for this sport
    bias_response=$(curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/live/grader/bias/$sport" 2>/dev/null || echo '{"error":"fetch_failed"}')

    if echo "$bias_response" | jq -e '.error' > /dev/null 2>&1; then
        echo -e "${YELLOW}[WARN] No bias data for $sport${NC}"
        continue
    fi

    # Check sample sizes
    sample_size=$(echo "$bias_response" | jq -r '.sample_size // 0' 2>/dev/null || echo "0")
    hit_rate=$(echo "$bias_response" | jq -r '.hit_rate // 0' 2>/dev/null || echo "0")

    if [ "$sample_size" -lt 30 ]; then
        echo -e "${YELLOW}[WARN] Small sample size: $sample_size samples (min recommended: 30)${NC}"
        WARNINGS=$((WARNINGS + 1))
    else
        echo -e "${GREEN}[OK] Sample size: $sample_size samples${NC}"
    fi

    echo "  Hit rate: $hit_rate%"
done

echo ""
echo "========================================"
echo "SUMMARY"
echo "========================================"
if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}FAILED: $FAILED sports had errors${NC}"
fi
if [ "$WARNINGS" -gt 0 ]; then
    echo -e "${YELLOW}WARNINGS: $WARNINGS issues detected${NC}"
fi
if [ "$FAILED" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo -e "${GREEN}ALL CLEAR: No weight drift or small-sample issues detected${NC}"
fi

exit $FAILED
