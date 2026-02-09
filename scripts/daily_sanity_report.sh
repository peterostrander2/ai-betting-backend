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
  resp=$(curl -sS "$API_BASE/live/best-bets/$sport" -H "X-API-Key: $API_KEY" || true)
  if [[ -z "$resp" ]]; then
    echo "ERROR: empty response" >&2
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

  # v20.12: ENGINE STARVATION SENTINEL
  # Detects when engines may be starved (low scores + missing data vs no edge found)
  printf "\n[ENGINE STARVATION CHECK %s]\n" "$sport"
  echo "$resp" | jq -r '
    def score_health(name; score; min_healthy):
      if score == null then "\(name): MISSING ⚠️"
      elif score < min_healthy then "\(name): LOW (\(score)) ⚠️"
      else "\(name): OK (\(score))"
      end;

    def glitch_health:
      if .glitch_signals == null then "GLITCH: MISSING ⚠️"
      elif .glitch_signals.status == "FAILED" then "GLITCH: FAILED ⚠️"
      elif .glitch_signals.status == "PARTIAL" then "GLITCH: PARTIAL (check components)"
      elif .glitch_signals.status == "SUCCESS" then "GLITCH: OK"
      else "GLITCH: UNKNOWN (\(.glitch_signals.status // "no_status"))"
      end;

    def check_starvation(picks):
      if (picks | length) == 0 then
        {status: "NO_PICKS", message: "No picks to analyze"}
      else
        (picks | map(.ai_score // 0) | add / length) as $avg_ai |
        (picks | map(.research_score // 0) | add / length) as $avg_research |
        (picks | map(.esoteric_score // 0) | add / length) as $avg_esoteric |
        (picks | map(.jarvis_score // 0) | add / length) as $avg_jarvis |
        (picks | map(.final_score // 0) | add / length) as $avg_final |
        (picks | map(select(.final_score >= 7.0)) | length) as $pass_count |
        ([$avg_ai < 4.0, $avg_research < 4.0, $avg_esoteric < 3.0, $avg_jarvis < 4.0] | map(select(. == true)) | length) as $low_engines |
        {
          avg_ai: ($avg_ai | . * 100 | round / 100),
          avg_research: ($avg_research | . * 100 | round / 100),
          avg_esoteric: ($avg_esoteric | . * 100 | round / 100),
          avg_jarvis: ($avg_jarvis | . * 100 | round / 100),
          avg_final: ($avg_final | . * 100 | round / 100),
          picks_analyzed: (picks | length),
          passed_threshold: $pass_count,
          low_engine_count: $low_engines,
          status: (if $low_engines >= 3 then "STARVED ⚠️" elif $low_engines >= 2 then "DEGRADED" else "HEALTHY" end)
        }
      end;

    {
      game_picks: check_starvation(.game_picks.picks // []),
      props: check_starvation(.props.picks // []),
      glitch_sample: ((.game_picks.picks // [])[0] | glitch_health)
    }
  '

  printf "\n"

done

# Cache headers check
printf "[CACHE HEADERS]\n"
for sport in $SPORTS; do
  hdrs=$(curl -sSI "$API_BASE/live/best-bets/$sport" -H "X-API-Key: $API_KEY" | egrep -i "cache-control|pragma|expires|etag|age|date|vary" || true)
  printf "%s\n%s\n\n" "${sport}:" "$hdrs"
done

printf "DONE\n"
