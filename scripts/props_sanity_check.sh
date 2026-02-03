#!/bin/bash
# Props Sanity Check - Verify props pipeline is producing picks when expected

set -e

BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-}"
PROPS_REQUIRED_SPORTS="${PROPS_REQUIRED_SPORTS:-NBA}"
REQUIRE_PROPS="${REQUIRE_PROPS:-0}"

if [ -z "$API_KEY" ]; then
  echo "ERROR: API_KEY is required for props sanity check."
  exit 1
fi

echo "Props Sanity Check (sports: $PROPS_REQUIRED_SPORTS, require_props=$REQUIRE_PROPS)"

for SPORT in $PROPS_REQUIRED_SPORTS; do
  SPORT_LOWER=$(echo "$SPORT" | tr '[:upper:]' '[:lower:]')
  RESP=$(curl -s "$BASE_URL/live/best-bets/$SPORT_LOWER?debug=1" -H "X-API-Key: $API_KEY")
  PROPS_COUNT=$(echo "$RESP" | jq -r '.props.count // 0')
  GAME_COUNT=$(echo "$RESP" | jq -r '.game_picks.count // 0')
  HAS_KEYS=$(echo "$RESP" | jq -r 'has("props") and has("game_picks") and has("meta")')

  echo "  $SPORT: props=$PROPS_COUNT, games=$GAME_COUNT, keys=$HAS_KEYS"

  if [ "$HAS_KEYS" != "true" ]; then
    echo "ERROR: Missing keys in best-bets payload for $SPORT"
    exit 1
  fi

  if [ "$REQUIRE_PROPS" = "1" ] && [ "$PROPS_COUNT" -le 0 ]; then
    echo "ERROR: Props required for $SPORT but props.count=0"
    exit 1
  fi
done

echo "Props sanity check: PASS"
