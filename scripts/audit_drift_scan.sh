#!/bin/bash
# Audit drift scan - scoring and payload contract checks (fail-fast)

set -e

BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-}"
SKIP_NETWORK="${SKIP_NETWORK:-0}"

SCORING_PATHS=(
  core
  live_data_router.py
  tiering.py
  core/scoring_pipeline.py
  core/scoring_contract.py
)

fail() {
  echo "ERROR: $1"
  exit 1
}

# 1) BASE_5 usage in scoring paths
rg -n "\bBASE_5\b" "${SCORING_PATHS[@]}" >/tmp/audit_base5_matches 2>/dev/null || true
if [ -s /tmp/audit_base5_matches ]; then
  echo "Found BASE_5 usage in scoring paths:"
  cat /tmp/audit_base5_matches
  fail "BASE_5 usage detected"
fi

# 2) Context engine weights / context weighting
rg -n "ENGINE_WEIGHTS\[\s*['\"]context['\"]\s*\]|context_weight|context\s*\*\s*ENGINE_WEIGHTS" "${SCORING_PATHS[@]}" >/tmp/audit_context_weight_matches 2>/dev/null || true
if [ -s /tmp/audit_context_weight_matches ]; then
  echo "Found context weighting usage in scoring paths:"
  cat /tmp/audit_context_weight_matches
  fail "Context weighting detected"
fi

# 3) Additive literal +/-0.5 applied to final_score outside ensemble adjustment
rg -n "final_score\s*=.*[+-]\s*0\.5" "${SCORING_PATHS[@]}" >/tmp/audit_final_score_literals 2>/dev/null || true
if [ -s /tmp/audit_final_score_literals ]; then
  # Filter out the allowed ensemble adjustment in live_data_router.py and utils/ensemble_adjustment.py
  FILTERED=$(cat /tmp/audit_final_score_literals | \
    rg -v "utils/ensemble_adjustment.py" | \
    rg -v "live_data_router.py:475[34]" | \
    rg -v "live_data_router.py:475[67]" || true)
  if [ -n "$FILTERED" ]; then
    echo "Found additive final_score +/-0.5 outside allowed ensemble adjustment:"
    echo "$FILTERED"
    fail "Unexpected literal +/-0.5 applied to final_score"
  fi
fi

# 4) Required fields in best-bets debug payload
if [ "$SKIP_NETWORK" = "1" ]; then
  echo "SKIP_NETWORK=1 set; skipping payload checks."
  exit 0
fi

if [ -z "$API_KEY" ]; then
  fail "API_KEY is required for payload checks (or set SKIP_NETWORK=1)."
fi

url="$BASE_URL/live/best-bets/NBA?debug=1&max_props=1&max_games=1"
resp_file="$(mktemp)"
http_code="$(curl -sS -o "$resp_file" -w "%{http_code}" "$url" -H "X-API-Key: $API_KEY")"
curl_rc=$?

if [ $curl_rc -ne 0 ]; then
  echo "NETWORK_UNAVAILABLE: curl rc=$curl_rc url=$url"
  cat "$resp_file" 2>/dev/null || true
  exit 20
fi

if [ "$http_code" != "200" ]; then
  echo "HTTP $http_code returned from best-bets endpoint"
  cat "$resp_file" 2>/dev/null || true
  fail "Best-bets endpoint returned HTTP $http_code"
fi

RESP="$(cat "$resp_file")"
if [ -z "$RESP" ]; then
  fail "Empty response from best-bets endpoint (HTTP $http_code)"
fi

# Must have props, game_picks, meta and picks arrays
HAS_SHAPE=$(echo "$RESP" | jq -r 'has("props") and has("game_picks") and has("meta") and (.props.picks | type == "array") and (.game_picks.picks | type == "array")' 2>/dev/null || echo false)
if [ "$HAS_SHAPE" != "true" ]; then
  fail "Best-bets payload missing props/game_picks/meta or picks arrays"
fi

REQUIRED_FIELDS='["base_4_score","context_modifier","confluence_boost","msrf_boost","jason_sim_boost","serp_boost","final_score","serp_status","msrf_status","context_reasons","confluence_reasons"]'

# Check first game pick if present
GAME_COUNT=$(echo "$RESP" | jq -r '.game_picks.picks | length' 2>/dev/null || echo 0)
if [ "$GAME_COUNT" -gt 0 ]; then
  GAME_OK=$(echo "$RESP" | jq -r --argjson req "$REQUIRED_FIELDS" '
    .game_picks.picks[0] as $p | [$req[] | . as $key | $p | has($key)] | all
  ' 2>/dev/null || echo false)
  if [ "$GAME_OK" != "true" ]; then
    fail "Missing required fields in game_picks.picks[0]"
  fi
fi

# Check first prop pick if present
PROP_COUNT=$(echo "$RESP" | jq -r '.props.picks | length' 2>/dev/null || echo 0)
if [ "$PROP_COUNT" -gt 0 ]; then
  PROP_OK=$(echo "$RESP" | jq -r --argjson req "$REQUIRED_FIELDS" '
    .props.picks[0] as $p | [$req[] | . as $key | $p | has($key)] | all
  ' 2>/dev/null || echo false)
  if [ "$PROP_OK" != "true" ]; then
    fail "Missing required fields in props.picks[0]"
  fi
fi

echo "Audit drift scan: PASS"
