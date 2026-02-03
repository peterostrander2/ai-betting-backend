#!/bin/bash
# Live betting sanity check - network optional

set -e

BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-}"
SKIP_NETWORK="${SKIP_NETWORK:-0}"
SPORTS="${SPORTS:-NBA NFL NHL MLB NCAAB}"

fail() {
  echo "ERROR: $1"
  exit 1
}

if [ "$SKIP_NETWORK" = "1" ]; then
  echo "SKIP_NETWORK=1 set; skipping live betting checks."
  exit 0
fi

if [ -z "$API_KEY" ]; then
  fail "API_KEY is required for live betting checks."
fi

REQUIRED_FIELDS='["base_4_score","context_modifier","confluence_boost","msrf_boost","jason_sim_boost","serp_boost","final_score","serp_status","msrf_status","context_reasons","confluence_reasons","live_adjustment","live_reasons"]'

for SPORT in $SPORTS; do
  SPORT_LOWER=$(echo "$SPORT" | tr '[:upper:]' '[:lower:]')

  # /live/in-play/{sport}
  resp_file="$(mktemp)"
  url="$BASE_URL/live/in-play/$SPORT_LOWER"
  http_code="$(curl -sS -o "$resp_file" -w "%{http_code}" "$url" -H "X-API-Key: $API_KEY")"
  curl_rc=$?
  if [ $curl_rc -ne 0 ]; then
    echo "NETWORK_UNAVAILABLE: curl rc=$curl_rc url=$url"
    cat "$resp_file" 2>/dev/null || true
    exit 20
  fi
  RESP="$(cat "$resp_file")"
  CODE=$(echo "$RESP" | jq -r '.error // empty' 2>/dev/null || true)
  if [ -z "$RESP" ]; then
    fail "Empty response from /live/in-play/$SPORT_LOWER"
  fi
  PICKS_LEN=$(echo "$RESP" | jq -r '.picks | length' 2>/dev/null || echo 0)
  if [ "$PICKS_LEN" -gt 0 ]; then
    OK=$(echo "$RESP" | jq -r --argjson req "$REQUIRED_FIELDS" '.picks[0] as $p | ($req | all($p | has(.)))' 2>/dev/null || echo false)
    if [ "$OK" != "true" ]; then
      fail "Missing required fields in /live/in-play/$SPORT_LOWER pick payload"
    fi
  fi

  # /in-game/{sport}
  resp_file="$(mktemp)"
  url="$BASE_URL/in-game/$SPORT_LOWER"
  http_code="$(curl -sS -o "$resp_file" -w "%{http_code}" "$url" -H "X-API-Key: $API_KEY")"
  curl_rc=$?
  if [ $curl_rc -ne 0 ]; then
    echo "NETWORK_UNAVAILABLE: curl rc=$curl_rc url=$url"
    cat "$resp_file" 2>/dev/null || true
    exit 20
  fi
  RESP2="$(cat "$resp_file")"
  if [ -z "$RESP2" ]; then
    fail "Empty response from /in-game/$SPORT_LOWER"
  fi
  P2_LEN=$(echo "$RESP2" | jq -r '.live_picks | length' 2>/dev/null || echo 0)
  if [ "$P2_LEN" -gt 0 ]; then
    OK2=$(echo "$RESP2" | jq -r --argjson req "$REQUIRED_FIELDS" '.live_picks[0] as $p | ($req | all($p | has(.)))' 2>/dev/null || echo false)
    if [ "$OK2" != "true" ]; then
      fail "Missing required fields in /in-game/$SPORT_LOWER live_picks payload"
    fi
  fi

done

echo "Live sanity check: PASS"
