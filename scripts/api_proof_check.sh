#!/bin/bash
# API proof check - ensure critical integrations are validated and status fields present

set -e

BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-}"
SKIP_NETWORK="${SKIP_NETWORK:-0}"

fail() {
  echo "ERROR: $1"
  exit 1
}

if [ "$SKIP_NETWORK" = "1" ]; then
  echo "SKIP_NETWORK=1 set; skipping API proof checks."
  exit 0
fi

if [ -z "$API_KEY" ]; then
  fail "API_KEY is required (or set SKIP_NETWORK=1)."
fi

url="$BASE_URL/live/debug/integrations"
resp_file="$(mktemp)"
http_code="$(curl -sS -o "$resp_file" -w "%{http_code}" "$url" -H "X-API-Key: $API_KEY")"
curl_rc=$?
if [ $curl_rc -ne 0 ]; then
  echo "NETWORK_UNAVAILABLE: curl rc=$curl_rc url=$url"
  cat "$resp_file" 2>/dev/null || true
  exit 20
fi
RESP="$(cat "$resp_file")"
if [ -z "$RESP" ]; then
  fail "Empty response from /live/debug/integrations"
fi

REQUIRED=("balldontlie" "odds_api" "playbook_api" "serpapi" "railway_storage")
for name in "${REQUIRED[@]}"; do
  ok=$(echo "$RESP" | jq -r --arg name "$name" '.by_status.validated | index($name) != null' 2>/dev/null || echo false)
  if [ "$ok" != "true" ]; then
    status=$(echo "$RESP" | jq -r --arg name "$name" '.integrations[$name].status_category // "MISSING"' 2>/dev/null || echo "MISSING")
    fail "Integration $name not VALIDATED (status=$status)"
  fi
done

# Ensure status fields appear in debug pick payloads
url="$BASE_URL/live/best-bets/NBA?debug=1&max_props=3&max_games=3"
resp_file="$(mktemp)"
http_code="$(curl -sS -o "$resp_file" -w "%{http_code}" "$url" -H "X-API-Key: $API_KEY")"
curl_rc=$?
if [ $curl_rc -ne 0 ]; then
  echo "NETWORK_UNAVAILABLE: curl rc=$curl_rc url=$url"
  cat "$resp_file" 2>/dev/null || true
  exit 20
fi
PICK="$(cat "$resp_file")"
if [ -z "$PICK" ]; then
  fail "Empty response from best-bets debug"
fi

required_fields='["serp_status","msrf_status","jason_status"]'
count=$(echo "$PICK" | jq -r '.game_picks.picks | length' 2>/dev/null || echo 0)
if [ "$count" -gt 0 ]; then
  ok=$(echo "$PICK" | jq -r --argjson req "$required_fields" '.game_picks.picks[0] as $p | ($req | all($p | has(.)))' 2>/dev/null || echo false)
  if [ "$ok" != "true" ]; then
    fail "Missing status fields in game_picks.picks[0]"
  fi
fi

count=$(echo "$PICK" | jq -r '.props.picks | length' 2>/dev/null || echo 0)
if [ "$count" -gt 0 ]; then
  ok=$(echo "$PICK" | jq -r --argjson req "$required_fields" '.props.picks[0] as $p | ($req | all($p | has(.)))' 2>/dev/null || echo false)
  if [ "$ok" != "true" ]; then
    fail "Missing status fields in props.picks[0]"
  fi
fi

echo "API proof check: PASS"
