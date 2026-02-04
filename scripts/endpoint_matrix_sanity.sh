#!/bin/bash
# Endpoint matrix sanity - prod endpoint verification across sports

set -e

BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-}"
SPORTS="${SPORTS:-NBA NFL NHL MLB NCAAB}"
SKIP_NETWORK="${SKIP_NETWORK:-0}"

fail() {
  echo "ERROR: $1"
  exit 1
}

if [ "$SKIP_NETWORK" = "1" ]; then
  echo "SKIP_NETWORK=1 set; skipping endpoint matrix sanity."
  exit 0
fi

if [ -z "$API_KEY" ]; then
  fail "API_KEY is required (or set SKIP_NETWORK=1)."
fi

CONTEXT_CAP=$(python3 - <<'PY'
from core.scoring_contract import CONTEXT_MODIFIER_CAP
print(CONTEXT_MODIFIER_CAP)
PY
)

check_best_bets() {
  local sport="$1"
  local url="$BASE_URL/live/best-bets/$sport?debug=1&max_props=1&max_games=1"

  local resp_file
  resp_file=$(mktemp)
  local http_code
  http_code=$(curl -sS -o "$resp_file" -w "%{http_code}" "$url" -H "X-API-Key: $API_KEY")
  curl_rc=$?
  if [ $curl_rc -ne 0 ]; then
    echo "NETWORK_UNAVAILABLE: curl rc=$curl_rc url=$url"
    cat "$resp_file" 2>/dev/null || true
    exit 20
  fi
  if [ "$http_code" = "404" ]; then
    echo "Live endpoint /live/in-play/$sport not found (404) — SKIPPED"
    rm -f "$resp_file"
    return 0
  fi

  if [ "$http_code" != "200" ]; then
    local err_code
    err_code=$(jq -r '.detail.code // empty' "$resp_file" 2>/dev/null || true)
    if [ -z "$err_code" ]; then
      echo "Best-bets $sport returned HTTP $http_code without structured error."
      cat "$resp_file"
      fail "best-bets failed for $sport"
    fi
  fi

  local has_shape
  has_shape=$(jq -r 'has("props") and has("game_picks") and has("meta")' "$resp_file" 2>/dev/null || echo false)
  if [ "$has_shape" != "true" ]; then
    fail "best-bets $sport missing props/game_picks/meta"
  fi

  # Check required fields if picks exist
  local req='["base_4_score","context_modifier","confluence_boost","msrf_boost","jason_sim_boost","serp_boost","ensemble_adjustment","live_adjustment","final_score","serp_status","msrf_status","context_reasons","confluence_reasons"]'
  local game_count
  game_count=$(jq -r '.game_picks.picks | length' "$resp_file" 2>/dev/null || echo 0)
  if [ "$game_count" -gt 0 ]; then
    local ok
    ok=$(jq -r --argjson req "$req" '.game_picks.picks[0] as $p | [$req[] | . as $key | $p | has($key)] | all' "$resp_file" 2>/dev/null || echo false)
    if [ "$ok" != "true" ]; then
      fail "best-bets $sport missing required fields in game pick"
    fi

    # Caps check for context_modifier
    local ctx
    ctx=$(jq -r '.game_picks.picks[0].context_modifier' "$resp_file" 2>/dev/null || echo 0)
    python3 - <<PY
cap = float("$CONTEXT_CAP")
val = float("$ctx")
if abs(val) > cap + 1e-6:
    raise SystemExit(2)
PY
    if [ $? -ne 0 ]; then
      fail "best-bets $sport context_modifier exceeds cap"
    fi

    # Final score math check (with cap at 10.0)
    local diff
    diff=$(jq -r '
      .game_picks.picks[0] as $p |
      ($p.base_4_score + $p.context_modifier + $p.confluence_boost + $p.msrf_boost + $p.jason_sim_boost + $p.serp_boost + ($p.ensemble_adjustment // 0) + ($p.live_adjustment // 0)) as $raw |
      ($raw | if . > 10 then 10 else . end) as $capped |
      ($p.final_score - $capped) | abs
    ' "$resp_file" 2>/dev/null || echo 0)

    python3 - <<PY
val = float("$diff")
if val > 0.02:
    raise SystemExit(2)
PY
    if [ $? -ne 0 ]; then
      fail "best-bets $sport final_score math mismatch"
    fi
  fi

  local prop_count
  prop_count=$(jq -r '.props.picks | length' "$resp_file" 2>/dev/null || echo 0)
  if [ "$prop_count" -gt 0 ]; then
    local ok
    ok=$(jq -r --argjson req "$req" '.props.picks[0] as $p | [$req[] | . as $key | $p | has($key)] | all' "$resp_file" 2>/dev/null || echo false)
    if [ "$ok" != "true" ]; then
      fail "best-bets $sport missing required fields in prop pick"
    fi
  fi

  rm -f "$resp_file"
}

check_live_endpoints() {
  local sport="$1"

  # /live/in-play/{sport}
  local url="$BASE_URL/live/in-play/$sport"
  local resp_file
  resp_file=$(mktemp)
  local http_code
  http_code=$(curl -sS -o "$resp_file" -w "%{http_code}" "$url" -H "X-API-Key: $API_KEY")
  curl_rc=$?
  if [ $curl_rc -ne 0 ]; then
    echo "NETWORK_UNAVAILABLE: curl rc=$curl_rc url=$url"
    cat "$resp_file" 2>/dev/null || true
    exit 20
  fi
  if [ "$http_code" = "404" ]; then
    echo "Live endpoint /in-game/$sport not found (404) — SKIPPED"
    rm -f "$resp_file"
    return 0
  fi
  if [ "$http_code" != "200" ]; then
    local err_code
    err_code=$(jq -r '.detail.code // empty' "$resp_file" 2>/dev/null || true)
    if [ -z "$err_code" ]; then
      echo "Live endpoint /live/in-play/$sport returned HTTP $http_code without structured error."
      cat "$resp_file"
      fail "live endpoint failed: /live/in-play/$sport"
    fi
  fi

  local count
  count=$(jq -r '.live_games_count // 0' "$resp_file" 2>/dev/null || echo 0)
  if [ "$count" -gt 0 ]; then
    local ok
    ok=$(jq -r '
      .picks[0] as $p |
      $p | has("base_4_score") and has("context_modifier") and has("confluence_boost") and has("msrf_boost") and has("jason_sim_boost") and has("serp_boost") and has("final_score") and has("live_adjustment")
    ' "$resp_file" 2>/dev/null || echo false)
    if [ "$ok" != "true" ]; then
      fail "live endpoint /live/in-play/$sport missing required fields"
    fi
  fi
  rm -f "$resp_file"

  # /in-game/{sport}
  url="$BASE_URL/in-game/$sport"
  resp_file=$(mktemp)
  http_code=$(curl -sS -o "$resp_file" -w "%{http_code}" "$url" -H "X-API-Key: $API_KEY")
  curl_rc=$?
  if [ $curl_rc -ne 0 ]; then
    echo "NETWORK_UNAVAILABLE: curl rc=$curl_rc url=$url"
    cat "$resp_file" 2>/dev/null || true
    exit 20
  fi
  if [ "$http_code" != "200" ]; then
    local err_code
    err_code=$(jq -r '.detail.code // empty' "$resp_file" 2>/dev/null || true)
    if [ -z "$err_code" ]; then
      echo "Live endpoint /in-game/$sport returned HTTP $http_code without structured error."
      cat "$resp_file"
      fail "live endpoint failed: /in-game/$sport"
    fi
  fi

  local game_count
  game_count=$(jq -r '.live_game_picks.count // 0' "$resp_file" 2>/dev/null || echo 0)
  if [ "$game_count" -gt 0 ]; then
    local ok
    ok=$(jq -r '
      .live_game_picks.picks[0] as $p |
      $p | has("base_4_score") and has("context_modifier") and has("confluence_boost") and has("msrf_boost") and has("jason_sim_boost") and has("serp_boost") and has("final_score") and has("live_adjustment")
    ' "$resp_file" 2>/dev/null || echo false)
    if [ "$ok" != "true" ]; then
      fail "live endpoint /in-game/$sport missing required fields in live_game_picks"
    fi
  fi

  local prop_count
  prop_count=$(jq -r '.live_props.count // 0' "$resp_file" 2>/dev/null || echo 0)
  if [ "$prop_count" -gt 0 ]; then
    local ok
    ok=$(jq -r '
      .live_props.picks[0] as $p |
      $p | has("base_4_score") and has("context_modifier") and has("confluence_boost") and has("msrf_boost") and has("jason_sim_boost") and has("serp_boost") and has("final_score") and has("live_adjustment")
    ' "$resp_file" 2>/dev/null || echo false)
    if [ "$ok" != "true" ]; then
      fail "live endpoint /in-game/$sport missing required fields in live_props"
    fi
  fi
  rm -f "$resp_file"
}

for sport in $SPORTS; do
  echo "Checking best-bets: $sport"
  check_best_bets "$sport"
  echo "Checking live endpoints: $sport"
  check_live_endpoints "$sport"
  echo "OK: $sport"
  echo "----"

done

echo "Endpoint matrix sanity: PASS"
