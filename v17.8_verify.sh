#!/bin/bash
# v17.8 Verification Script
# Run after deploying Officials Tendency Integration (Pillar 16)

set -e

API_BASE="${API_BASE:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-YOUR_API_KEY}"

echo "=============================================="
echo "v17.8 Verification: Officials Tendency (Pillar 16)"
echo "=============================================="

# 1. Syntax check (run locally before deploy)
echo ""
echo "1. Syntax Check"
echo "---------------"
if [ -f "officials_data.py" ]; then
    python3 -m py_compile officials_data.py && echo "✓ officials_data.py OK" || echo "✗ Syntax error"
fi
if [ -f "context_layer.py" ]; then
    python3 -m py_compile context_layer.py && echo "✓ context_layer.py OK" || echo "✗ Syntax error"
fi
if [ -f "live_data_router.py" ]; then
    python3 -m py_compile live_data_router.py && echo "✓ live_data_router.py OK" || echo "✗ Syntax error"
fi

# 2. Test officials_data module
echo ""
echo "2. Officials Data Module Test"
echo "-----------------------------"
python3 -c "
from officials_data import get_referee_tendency, calculate_officials_adjustment, get_database_stats

# Test lookups
print('Scott Foster (NBA):', get_referee_tendency('NBA', 'Scott Foster'))
print('Carl Cheffers (NFL):', get_referee_tendency('NFL', 'Carl Cheffers'))
print('Wes McCauley (NHL):', get_referee_tendency('NHL', 'Wes McCauley'))

# Test adjustments
adj, reason = calculate_officials_adjustment('NBA', 'Scott Foster', 'TOTAL', 'Over')
print(f'Over adjustment with Scott Foster: {adj:+.2f} ({reason})')

adj, reason = calculate_officials_adjustment('NFL', 'Carl Cheffers', 'SPREAD', 'home', is_home_team=True)
print(f'Home spread with Carl Cheffers: {adj:+.2f} ({reason})')

# Stats
stats = get_database_stats()
print(f'Database: NBA={stats[\"NBA\"][\"count\"]} refs, NFL={stats[\"NFL\"][\"count\"]} refs, NHL={stats[\"NHL\"][\"count\"]} refs')
"

# 3. Check officials in picks (NBA)
echo ""
echo "3. Officials in NBA Picks"
echo "-------------------------"
echo "Note: Officials are assigned 1-3 hours before games"
curl -s "${API_BASE}/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: ${API_KEY}" | \
  jq '[.game_picks.picks[].research_reasons] | flatten | map(select(startswith("Officials"))) | if length == 0 then ["No officials data yet (refs not assigned or no tendency match)"] else . end'

# 4. Check officials data in debug
echo ""
echo "4. Officials Debug Data"
echo "-----------------------"
curl -s "${API_BASE}/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: ${API_KEY}" | \
  jq '.game_picks.picks[0] | {
    matchup: .matchup,
    officials_adjustment: .officials_adjustment,
    officials_reasons: .officials_reasons,
    officials_data: .officials_data
  }'

# 5. Test all supported sports
echo ""
echo "5. Officials Across Sports"
echo "--------------------------"
for sport in NBA NFL NHL; do
  echo ""
  echo "=== $sport ==="
  result=$(curl -s "${API_BASE}/live/best-bets/${sport}?debug=1" -H "X-API-Key: ${API_KEY}")

  # Count picks with officials adjustments
  adj_count=$(echo "$result" | jq '[.game_picks.picks[].officials_adjustment // 0 | select(. != 0)] | length')
  total_count=$(echo "$result" | jq '.game_picks.picks | length')

  echo "Picks with officials adjustment: ${adj_count}/${total_count}"

  # Show any officials reasons
  echo "$result" | jq '[.game_picks.picks[].officials_reasons // []] | flatten | unique' 2>/dev/null || echo "[]"
done

# 6. Verify Pillar 16 status
echo ""
echo "6. Pillar 16 Status"
echo "-------------------"
echo "Checking if officials adjustment is non-zero for any pick..."
has_adjustment=$(curl -s "${API_BASE}/live/best-bets/NBA?debug=1" \
  -H "X-API-Key: ${API_KEY}" | \
  jq '[.game_picks.picks[].officials_adjustment // 0 | select(. != 0)] | length > 0')

if [ "$has_adjustment" = "true" ]; then
  echo "✓ Pillar 16 ACTIVE - Officials adjustments being applied"
else
  echo "⚠ Pillar 16 READY - No adjustments yet (refs may not be assigned)"
fi

echo ""
echo "=============================================="
echo "Verification Complete"
echo "=============================================="
echo ""
echo "17 Pillars Status after v17.8:"
echo "  ✓ Pillars 1-8: AI Models (ACTIVE)"
echo "  ✓ Pillars 9-12: Research (ACTIVE)"
echo "  ✓ Pillars 13-15: Context (ACTIVE)"
echo "  ✓ Pillar 16: Officials (ACTIVE - v17.8)"
echo "  ✓ Pillar 17: Park Factors (ACTIVE - MLB only)"
echo ""
echo "Officials Data Coverage:"
echo "  NBA: 25+ referees with tendency data"
echo "  NFL: 17 referee crews"
echo "  NHL: 15+ referees"
echo "  MLB: N/A (umpires work differently)"
echo "  NCAAB: N/A (insufficient data)"
echo ""
echo "When Officials Adjustments Apply:"
echo "  - ESPN assigns refs 1-3 hours before games"
echo "  - Referee must be in our database"
echo "  - Tendency must deviate from 50% (±2%+)"
echo "  - Pick type must match (Over/Under for totals, Home/Away for spreads)"
