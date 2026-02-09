#!/usr/bin/env bash
set -euo pipefail

API_BASE=${API_BASE:-"https://web-production-7b2a.up.railway.app"}
API_KEY=${API_KEY:-""}
SPORTS=${SPORTS:-"NBA NFL NHL MLB"}

if [[ -z "${API_KEY}" ]]; then
  echo "ERROR: API_KEY is required" >&2
  exit 1
fi

now_et=$(TZ=America/New_York date "+%Y-%m-%d %I:%M %p ET")

printf "============================================================\n"
printf "DAILY SANITY REPORT (ET)\n"
printf "Generated: %s\n" "$now_et"
printf "Base URL: %s\n" "$API_BASE"
printf "============================================================\n\n"

# Health
printf "[HEALTH]\n"
health=$(curl -sS "$API_BASE/health" -H "X-API-Key: $API_KEY" || true)
if [[ -n "$health" ]]; then
  echo "$health" | jq '{status, version, build_sha, deploy_version, database}'
else
  echo "ERROR: /health returned empty" >&2
fi
printf "\n"

# Live endpoints per sport
for sport in $SPORTS; do
  printf "[BEST-BETS %s]\n" "$sport"
  resp_file=$(mktemp)
  http_code=$(curl -sS -o "$resp_file" -w "%{http_code}" \
    "$API_BASE/live/best-bets/$sport?debug=1" \
    -H "X-API-Key: $API_KEY" 2>&1)
  curl_rc=$?

  resp=$(cat "$resp_file" 2>/dev/null || true)
  rm -f "$resp_file"

  if [ $curl_rc -ne 0 ] || [ -z "$resp" ]; then
    echo "$sport: ERROR curl_rc=$curl_rc http_code=$http_code"
    echo "resp_head: $(echo "$resp" | head -c 200)"
    printf "\n"
    continue
  fi

  # verify JSON before parsing
  if ! echo "$resp" | jq -e . >/dev/null 2>&1; then
    echo "$sport: ERROR non_json http_code=$http_code"
    echo "resp_head: $(echo "$resp" | head -c 200)"
    printf "\n"
    continue
  fi

  echo "$resp" | jq -r '{
    sport: .sport,
    source: .source,
    date_et: .date_et,
    run_timestamp_et: .run_timestamp_et,
    generated_at: .generated_at,
    errors_count: (.errors | length),
    props_count: (.props.count // .data.props.count),
    game_picks_count: (.game_picks.count // .data.game_picks.count)
  }'

  # Sample pick spot checks
  echo "$resp" | jq -r '
    def pick_summary(p): {
      id: (p.id // p.pick_id),
      bet: p.bet_string,
      pick_type: p.pick_type,
      selection: p.selection,
      line_signed: p.line_signed,
      odds_american: p.odds_american,
      units: p.recommended_units,
      start_time_et: (p.start_time_et // p.start_time),
      rest_days: (p.rest_days.value // null),
      book_count: (p.book_count // null),
      market_book_count: (p.market_book_count // null)
    };
    {
      top_game_pick: (if (.game_picks.picks // .data.game_picks.picks) | length > 0 then pick_summary((.game_picks.picks // .data.game_picks.picks)[0]) else null end),
      top_prop_pick: (if (.props.picks // .data.props.picks) | length > 0 then pick_summary((.props.picks // .data.props.picks)[0]) else null end)
    }'

  # Check for forbidden UTC/telemetry keys
  leak=$(echo "$resp" | egrep -n '"(_cached_at|generated_at|persisted_at|start_time_utc|start_time_iso|.*_utc|.*_iso|run_timestamp_et|timestamp)"' | head -n 1 || true)
  if [[ -n "$leak" ]]; then
    echo "WARN: Found forbidden/telemetry key in response: $leak"
  else
    echo "ET-only payload: OK"
  fi

  printf "\n"

done

# Cache headers check
printf "[CACHE HEADERS]\n"
for sport in $SPORTS; do
  hdrs=$(curl -sSI "$API_BASE/live/best-bets/$sport" -H "X-API-Key: $API_KEY" | egrep -i "cache-control|pragma|expires|etag|age|date|vary" || true)
  printf "%s\n%s\n\n" "${sport}:" "$hdrs"
done

printf "DONE\n"
