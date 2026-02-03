#!/bin/bash
# SESSION 7 — OUTPUT FILTERING PIPELINE
# Validates: Dedup → Score Filter → Contradiction Gate → Top-N
set -euo pipefail

BASE_URL="https://web-production-7b2a.up.railway.app"
API_KEY="bookie-prod-2026-xK9mP2nQ7vR4"

echo "=============================================================="
echo "SESSION 7 SPOT CHECK: Output Filtering Pipeline"
echo "=============================================================="

RAW="$(curl -s "${BASE_URL}/live/best-bets/nba?debug=1&max_props=100&max_games=50" \
  -H "X-API-Key: ${API_KEY}")"

echo "$RAW" | jq -r '{
  et_date: .debug.date_window_et.et_date,
  start_et: .debug.date_window_et.start_et,
  end_et: .debug.date_window_et.end_et,
  props_analyzed: .debug.date_window_et.events_after_props,
  props_returned: .props.count,
  games_analyzed: .debug.date_window_et.events_after_games,
  games_returned: .game_picks.count,
  filtered_below_6_5: .debug.filtered_below_6_5_total,
  contradictions_blocked: .debug.contradiction_blocked_total,
  dedupe_removed: (.debug.dedupe_removed_total // null),
  topN_props_cap: (.debug.max_props // null),
  topN_games_cap: (.debug.max_games // null)
}'

echo ""
echo "Running hard gates..."

# -------- HARD GATE 1: Top-N Cap Respected --------
# Note: events_after_props = games with props, props.count = individual picks (many per game)
PROPS_EVENTS="$(echo "$RAW" | jq -r '.debug.date_window_et.events_after_props // 0')"
PROPS_RETURNED="$(echo "$RAW" | jq -r '.props.count // 0')"
GAMES_EVENTS="$(echo "$RAW" | jq -r '.debug.date_window_et.events_after_games // 0')"
GAMES_RETURNED="$(echo "$RAW" | jq -r '.game_picks.count // 0')"
MAX_PROPS="$(echo "$RAW" | jq -r '.debug.max_props // 100')"
MAX_GAMES="$(echo "$RAW" | jq -r '.debug.max_games // 50')"

if [ "$PROPS_RETURNED" -gt "$MAX_PROPS" ]; then
  echo "❌ FAIL: props_returned ($PROPS_RETURNED) > max_props ($MAX_PROPS)"
  exit 1
fi

if [ "$GAMES_RETURNED" -gt "$MAX_GAMES" ]; then
  echo "❌ FAIL: games_returned ($GAMES_RETURNED) > max_games ($MAX_GAMES)"
  exit 1
fi

# If picks returned, events must exist
if [ "$PROPS_RETURNED" -gt 0 ] && [ "$PROPS_EVENTS" -eq 0 ]; then
  echo "❌ FAIL: props returned but no prop events analyzed"
  exit 1
fi

if [ "$GAMES_RETURNED" -gt 0 ] && [ "$GAMES_EVENTS" -eq 0 ]; then
  echo "❌ FAIL: games returned but no game events analyzed"
  exit 1
fi
echo "✅ Top-N cap: props=$PROPS_RETURNED/<=$MAX_PROPS, games=$GAMES_RETURNED/<=$MAX_GAMES"

# -------- HARD GATE 2: Score Filter (nothing < 6.5) --------
MIN_FINAL="$(echo "$RAW" | jq -r '
  ([.props.picks[].final_score] + [.game_picks.picks[].final_score])
  | map(select(. != null))
  | (if length==0 then 999 else min end)
')"

if [ "$(printf "%.1f" "$MIN_FINAL")" != "999.0" ] && awk "BEGIN{exit !($MIN_FINAL < 6.5)}"; then
  echo "❌ FAIL: Returned pick with final_score < 6.5 (min=$MIN_FINAL)"
  exit 1
fi
echo "✅ Score filter: all picks >= 6.5 (min=$MIN_FINAL)"

# -------- HARD GATE 3: Contradiction Gate Instrumented --------
HAS_CONTRA_FIELD="$(echo "$RAW" | jq -r 'has("debug") and (.debug | has("contradiction_blocked_total"))')"
if [ "$HAS_CONTRA_FIELD" != "true" ]; then
  echo "❌ FAIL: debug.contradiction_blocked_total missing"
  exit 1
fi
echo "✅ Contradiction gate: instrumented"

# -------- HARD GATE 4: Deduplication Active --------
DUPLICATE_IDS="$(echo "$RAW" | jq -r '
  ([.props.picks[].pick_id] + [.game_picks.picks[].pick_id])
  | group_by(.)
  | map(select(length > 1))
  | length
')"

if [ "$DUPLICATE_IDS" -gt 0 ]; then
  echo "❌ FAIL: Found $DUPLICATE_IDS duplicate pick_ids — deduplication broken"
  exit 1
fi
echo "✅ Deduplication: all pick_ids unique"

# -------- SOFT CHECK: Filters Active on Large Slates --------
FILTERED_BELOW="$(echo "$RAW" | jq -r '.debug.filtered_below_6_5_total // 0')"
CONTRA_BLOCKED="$(echo "$RAW" | jq -r '.debug.contradiction_blocked_total // 0')"

if [ "$PROPS_EVENTS" -gt 20 ] && [ "$FILTERED_BELOW" -eq 0 ] && [ "$CONTRA_BLOCKED" -eq 0 ]; then
  echo "⚠️  WARN: Large slate ($PROPS_EVENTS prop events) but no filtering activity"
  echo "         filtered_below_6_5=0, contradictions_blocked=0"
else
  echo "✅ Filter activity: filtered=$FILTERED_BELOW, contradictions=$CONTRA_BLOCKED"
fi

echo ""
echo "✅ SESSION 7 PASS: Output filtering pipeline verified"
echo "=============================================================="
