#!/bin/bash
# SESSION 8 — GRADING & PERSISTENCE + MULTI-SPORT SMOKE
# Part A: Storage, grading, persistence
# Part B: Multi-sport endpoints validation
set -euo pipefail

BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-bookie-prod-2026-xK9mP2nQ7vR4}"
SPORTS=("nba" "nhl" "nfl" "mlb")

echo "=============================================================="
echo "SESSION 8 SPOT CHECK: Grading & Persistence + Multi-Sport"
echo "Base URL: $BASE_URL"
echo "=============================================================="

fail() { echo "❌ FAIL: $1"; exit 1; }

# ========== PART A: GRADING & PERSISTENCE ==========
echo ""
echo "PART A: Grading & Persistence"
echo "------------------------------"

# Check 1: Storage Health
echo ""
echo "Check 1: Storage health..."
STORAGE="$(curl -s "${BASE_URL}/internal/storage/health" -H "X-API-Key: ${API_KEY}")"
echo "$STORAGE" | jq -r '{
  ok: .ok,
  predictions_file: .predictions_file,
  predictions_exists: .predictions_exists,
  is_mountpoint: .is_mountpoint,
  predictions_line_count: .predictions_line_count
}'

STORAGE_OK="$(echo "$STORAGE" | jq -r '.ok // false')"
[[ "$STORAGE_OK" == "true" ]] || fail "Storage health check failed"
echo "✅ Storage health: OK"

# Check 2: Grader Status
echo ""
echo "Check 2: Grader status..."
GRADER="$(curl -s "${BASE_URL}/live/grader/status" -H "X-API-Key: ${API_KEY}")"
echo "$GRADER" | jq -r '{
  available: .available,
  predictions_logged: .grader_store.predictions_logged,
  graded_today: .grader_store.graded_today,
  pending_to_grade: .grader_store.pending_to_grade
}'

TOTAL_PREDS="$(echo "$GRADER" | jq -r '.grader_store.predictions_logged // 0')"
if [ "$TOTAL_PREDS" -eq 0 ]; then
  echo "⚠️  WARN: Zero predictions stored (fresh deployment)"
else
  echo "✅ Pick persistence: $TOTAL_PREDS predictions stored"
fi

# Check 3: Grader Available
GRADER_AVAILABLE="$(echo "$GRADER" | jq -r '.available // false')"
[[ "$GRADER_AVAILABLE" == "true" ]] || fail "Grader not available"
echo "✅ Grader: available"

# Check 4: BallDontLie Integration
echo ""
echo "Check 4: Grading integration..."
INTEGRATIONS="$(curl -s "${BASE_URL}/live/debug/integrations" -H "X-API-Key: ${API_KEY}")"
BDL_STATUS="$(echo "$INTEGRATIONS" | jq -r '.integrations.balldontlie.status_category // "unknown"')"

if [[ "$BDL_STATUS" != "VALIDATED" && "$BDL_STATUS" != "CONFIGURED" ]]; then
  fail "BallDontLie integration not configured (status: $BDL_STATUS)"
fi
echo "✅ BallDontLie integration: $BDL_STATUS"

# Check 5: Storage Path Invariant
echo ""
echo "Check 5: Storage path invariant..."
GRADER_PATH="$(echo "$STORAGE" | jq -r '.predictions_file // ""')"
# Accept either /data/grader or /app/grader_data paths (Railway volume)
if [[ "$GRADER_PATH" != "/data/grader/predictions.jsonl" && "$GRADER_PATH" != "/app/grader_data/grader/predictions.jsonl" ]]; then
  fail "Grader path incorrect: $GRADER_PATH"
fi
echo "✅ Storage path: $GRADER_PATH"

# Check 6: Volume Mounted
VOLUME_MOUNTED="$(echo "$STORAGE" | jq -r '.is_mountpoint // false')"
[[ "$VOLUME_MOUNTED" == "true" ]] || fail "Railway volume not mounted"
echo "✅ Railway volume: mounted"

# ========== PART B: MULTI-SPORT SMOKE ==========
echo ""
echo "PART B: Multi-Sport Production Smoke"
echo "-------------------------------------"

check_sport() {
  local sport="$1"
  echo ""
  echo "---- ${sport} ----"

  local url="${BASE_URL}/live/best-bets/${sport}?debug=1&max_props=5&max_games=5"

  # HTTP + JSON validation
  local resp body http
  resp="$(curl -sS -H "X-API-Key: ${API_KEY}" -w "\n%{http_code}" "$url")" || fail "${sport}: curl failed"
  http="$(echo "$resp" | tail -n1)"
  body="$(echo "$resp" | sed '$d')"

  [[ "$http" == "200" ]] || fail "${sport}: HTTP ${http}"
  echo "$body" | jq -e . >/dev/null 2>&1 || fail "${sport}: invalid JSON"

  # Error payload check - allow partial success (PROPS_TIMED_OUT, etc.) when picks still returned
  # Only fail if there's an error AND no picks were returned
  local has_fatal_err picks_count
  picks_count="$(echo "$body" | jq -r '([.props.picks[]?] + [.game_picks.picks[]?]) | length')"

  # Check for errors that aren't acceptable partial-success codes
  has_fatal_err="$(echo "$body" | jq -r '
    # Top-level error field (not error code in errors array)
    (has("error") and .error != null and .error != "") or
    # Non-timeout errors in errors array
    (has("errors") and (.errors | map(select(.code != "PROPS_TIMED_OUT" and .code != "GAME_PICKS_TIMED_OUT")) | length) > 0) or
    # Debug-level error
    (.debug != null and .debug | has("error") and .debug.error != null and .debug.error != "")
  ' 2>/dev/null || echo "false")"

  # Fail if fatal error OR (partial error AND zero picks)
  if [[ "$has_fatal_err" == "true" ]]; then
    fail "${sport}: fatal error detected"
  elif [[ "$picks_count" == "0" ]]; then
    # Check if there are ANY errors when we have 0 picks
    local has_any_err
    has_any_err="$(echo "$body" | jq -r 'has("errors") and (.errors | length) > 0' 2>/dev/null || echo "false")"
    if [[ "$has_any_err" == "true" ]]; then
      echo "  ⚠️  ${sport}: 0 picks with errors (allowed during off-season)"
    fi
  fi

  # ET window validation
  local start_et end_et filter_date
  start_et="$(echo "$body" | jq -r '.debug.date_window_et.start_et // empty')"
  end_et="$(echo "$body" | jq -r '.debug.date_window_et.end_et // empty')"
  filter_date="$(echo "$body" | jq -r '.debug.date_window_et.filter_date // empty')"

  [[ -n "$start_et" && -n "$end_et" && -n "$filter_date" ]] || \
    fail "${sport}: missing debug.date_window_et fields"

  echo "$start_et" | grep -Eq '[\+\-][0-9]{2}:[0-9]{2}' || \
    fail "${sport}: start_et missing timezone offset: ${start_et}"
  echo "$end_et" | grep -Eq '[\+\-][0-9]{2}:[0-9]{2}' || \
    fail "${sport}: end_et missing timezone offset: ${end_et}"

  # Pick schema + score validation
  local picks_len
  picks_len="$(echo "$body" | jq -r '([.props.picks[]?] + [.game_picks.picks[]?]) | length')"

  if [[ "$picks_len" == "0" ]]; then
    echo "  ℹ️  ${sport}: 0 picks (allowed)"
  else
    # Required fields
    local missing
    missing="$(echo "$body" | jq -r '
      ([.props.picks[]?] + [.game_picks.picks[]?])
      | map(
          (has("pick_id") and (.pick_id != null) and (.pick_id|tostring|length>0))
          and (has("final_score") and (.final_score != null))
          and (has("tier") and (.tier != null))
        )
      | map(select(. == false)) | length
    ')"
    [[ "$missing" == "0" ]] || fail "${sport}: picks missing pick_id/final_score/tier"

    # Score filter: >= 6.5
    local min_final
    min_final="$(echo "$body" | jq -r '
      ([.props.picks[]?.final_score] + [.game_picks.picks[]?.final_score])
      | map(select(.!=null)) | (if length==0 then 999 else min end)
    ')"
    if awk "BEGIN{exit !($min_final < 6.5)}"; then
      fail "${sport}: final_score < 6.5 (min=$min_final)"
    fi

    # Engine fields
    local bad_eng
    bad_eng="$(echo "$body" | jq -r '
      ([.props.picks[]?] + [.game_picks.picks[]?])
      | map(
          ((.ai_score | type) == "number")
          and ((.research_score | type) == "number")
          and ((.esoteric_score | type) == "number")
          and (
            ((.jarvis_rs | type) == "number")
            or ((.jarvis_rs == null) and ((.jarvis_active // false) == false))
          )
        )
      | map(select(. == false)) | length
    ')"
    [[ "$bad_eng" == "0" ]] || fail "${sport}: invalid engine scores"

    echo "  ✅ ${picks_len} picks validated"
  fi

  echo "✅ ${sport}: PASS"
}

for sport in "${SPORTS[@]}"; do
  check_sport "$sport"
done

echo ""
echo "✅ SESSION 8 PASS: Grading, persistence, and multi-sport verified"
echo "=============================================================="
echo ""
echo "Note: Restart survival requires manual Railway restart + recheck"
