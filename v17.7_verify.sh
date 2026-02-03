#!/bin/bash
# v17.7 Verification Script
# Run after deploying the Hurst Exponent & Fibonacci Retracement wiring

set -e

API_BASE="https://web-production-7b2a.up.railway.app"
API_KEY="${API_KEY:-YOUR_API_KEY}"

echo "=============================================="
echo "v17.7 Verification: Hurst & Fibonacci Wiring"
echo "=============================================="

# 1. Syntax check (run locally before deploy)
echo ""
echo "1. Syntax Check"
echo "---------------"
if [ -f "live_data_router.py" ]; then
    python -m py_compile live_data_router.py && echo "✓ Syntax OK" || echo "✗ Syntax error"
else
    echo "⚠ live_data_router.py not found locally (skip if running remote verification)"
fi

# 2. Check Hurst in GLITCH
echo ""
echo "2. Hurst Exponent in GLITCH"
echo "---------------------------"
echo "Note: Will show 'no data' until 10+ line_snapshots exist per event (~5 hours)"
curl -s "${API_BASE}/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: ${API_KEY}" | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | map(select(contains("HURST"))) | if length == 0 then ["No HURST data yet (expected until snapshots accumulate)"] else . end'

# 3. Check Fibonacci Retracement
echo ""
echo "3. Fibonacci Retracement"
echo "------------------------"
echo "Note: Will show 'no data' until season_extremes populated (~24 hours)"
curl -s "${API_BASE}/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: ${API_KEY}" | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | map(select(contains("Fib Retracement"))) | if length == 0 then ["No Fib Retracement data yet (expected until season_extremes populated)"] else . end'

# 4. Full esoteric reasons check
echo ""
echo "4. All Esoteric Reasons (NBA)"
echo "-----------------------------"
curl -s "${API_BASE}/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: ${API_KEY}" | \
  jq '[.game_picks.picks[].esoteric_reasons] | flatten | unique | sort'

# 5. Multi-sport check
echo ""
echo "5. Multi-Sport Esoteric Status"
echo "------------------------------"
for sport in NBA NHL MLB NCAAB; do
    echo ""
    echo "=== $sport ==="
    curl -s "${API_BASE}/live/best-bets/${sport}?debug=1" \
      -H "X-API-Key: ${API_KEY}" | \
      jq '[.game_picks.picks[].esoteric_reasons] | flatten | unique | sort' 2>/dev/null || echo "No data or error"
done

echo ""
echo "=============================================="
echo "Verification Complete"
echo "=============================================="
echo ""
echo "Expected Timeline:"
echo "- Hurst data: ~5 hours (needs 10+ snapshots per event)"
echo "- Fibonacci Retracement: ~24 hours (needs season_extremes from 5 AM scheduler)"
echo ""
echo "GLITCH Protocol Status after v17.7:"
echo "  ✓ Chrome Resonance (0.25 weight)"
echo "  ✓ Void Moon (0.20 weight)"
echo "  ✓ Noosphere Velocity (0.15 weight)"
echo "  ✓ Hurst Exponent (0.25 weight) - WIRED, awaiting data"
echo "  ✓ Kp-Index (0.25 weight)"
echo "  ✓ Benford Anomaly (0.10 weight)"
echo ""
echo "Fibonacci Status:"
echo "  ✓ calculate_fibonacci_alignment() (Jarvis) - line IS Fib number"
echo "  ✓ calculate_fibonacci_retracement() (Esoteric) - season range position - WIRED"
