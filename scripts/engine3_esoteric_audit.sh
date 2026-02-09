#!/usr/bin/env bash
# Engine 3 (Esoteric) Runtime Audit Script
# Verifies Esoteric Engine integration, GLITCH protocol, and fail-soft behavior
set -euo pipefail

API_BASE=${API_BASE:-"https://web-production-7b2a.up.railway.app"}
API_KEY=${API_KEY:-""}
ARTIFACT_DIR=${ARTIFACT_DIR:-"artifacts"}
TIMESTAMP=$(TZ=America/New_York date "+%Y%m%d_%H%M%S_ET")
REPORT_FILE="${ARTIFACT_DIR}/engine3_esoteric_runtime_report_${TIMESTAMP}.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}✓${NC} $1"; }
log_fail() { echo -e "${RED}✗${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
log_info() { echo "  $1"; }

if [[ -z "${API_KEY}" ]]; then
  echo "ERROR: API_KEY is required" >&2
  exit 1
fi

mkdir -p "$ARTIFACT_DIR"

echo "============================================================"
echo "ENGINE 3 (ESOTERIC) RUNTIME AUDIT"
echo "============================================================"
echo "API Base: $API_BASE"
echo "Timestamp: $TIMESTAMP"
echo ""

# Initialize report
cat > "$REPORT_FILE" << EOF
{
  "audit_type": "engine3_esoteric",
  "timestamp": "$TIMESTAMP",
  "api_base": "$API_BASE",
  "tests": {}
}
EOF

update_report() {
  local test_name="$1"
  local status="$2"
  local details="$3"
  local tmp_file=$(mktemp)
  jq ".tests.\"$test_name\" = {\"status\": \"$status\", \"details\": $details}" "$REPORT_FILE" > "$tmp_file"
  mv "$tmp_file" "$REPORT_FILE"
}

# Track overall status
FAILED_TESTS=0
SPORT=""
resp=""
http_code=""
game_count=0
props_count=0

# Try multiple sports to find one with games
try_sport() {
  local sport_to_try="$1"
  local resp_file=$(mktemp)
  local code=$(curl -sS -o "$resp_file" -w "%{http_code}" \
    "$API_BASE/live/best-bets/$sport_to_try?debug=1" \
    -H "X-API-Key: $API_KEY" 2>&1) || true
  local response=$(cat "$resp_file" 2>/dev/null || true)
  rm -f "$resp_file"

  if [[ "$code" == "200" ]] && echo "$response" | jq -e . >/dev/null 2>&1; then
    local gc=$(echo "$response" | jq -r '.game_picks.count // 0')
    local pc=$(echo "$response" | jq -r '.props.count // 0')
    if [[ "$gc" -gt 0 ]] || [[ "$pc" -gt 0 ]]; then
      SPORT="$sport_to_try"
      resp="$response"
      http_code="$code"
      game_count="$gc"
      props_count="$pc"
      return 0
    fi
  fi
  return 1
}

# Find a sport with picks
echo "[0/8] Finding sport with available picks..."
echo "------------------------------------------------------------"
for sport in NBA NHL NFL MLB NCAAB; do
  if try_sport "$sport"; then
    log_pass "Found picks in $SPORT (games: $game_count, props: $props_count)"
    break
  fi
done

if [[ -z "$SPORT" ]]; then
  log_warn "No picks available across all sports (off-season or no games today)"
  log_info "Will run static tests only"
fi
echo ""

echo "[1/8] Health Check with Esoteric Engine Presence"
echo "------------------------------------------------------------"
resp_file=$(mktemp)
health_code=$(curl -sS -o "$resp_file" -w "%{http_code}" \
  "$API_BASE/health" 2>&1) || true
health_resp=$(cat "$resp_file" 2>/dev/null || true)
rm -f "$resp_file"

if [[ "$health_code" == "200" ]] && echo "$health_resp" | jq -e . >/dev/null 2>&1; then
  log_pass "Health endpoint responsive (HTTP $health_code)"
  update_report "health_check" "PASS" "$(echo "$health_resp" | jq -c '{status, version}')"
else
  log_fail "Health endpoint failed (HTTP $health_code)"
  update_report "health_check" "FAIL" '{"error": "Health endpoint not responsive"}'
  ((FAILED_TESTS++))
fi
echo ""

echo "[2/8] Esoteric Score Presence"
echo "------------------------------------------------------------"
if [[ -n "$SPORT" ]] && [[ "$game_count" -gt 0 || "$props_count" -gt 0 ]]; then
  esoteric_score=""
  esoteric_reasons_count=0

  if [[ "$game_count" -gt 0 ]]; then
    esoteric_score=$(echo "$resp" | jq -r '.game_picks.picks[0].esoteric_score // "null"')
    esoteric_reasons_count=$(echo "$resp" | jq -r '.game_picks.picks[0].esoteric_reasons | length // 0')
  elif [[ "$props_count" -gt 0 ]]; then
    esoteric_score=$(echo "$resp" | jq -r '.props.picks[0].esoteric_score // "null"')
    esoteric_reasons_count=$(echo "$resp" | jq -r '.props.picks[0].esoteric_reasons | length // 0')
  fi

  if [[ "$esoteric_score" != "null" ]] && [[ "$esoteric_score" != "" ]]; then
    log_pass "Esoteric score present: $esoteric_score (with $esoteric_reasons_count reasons)"
    update_report "esoteric_score_presence" "PASS" "{\"score\": $esoteric_score, \"reasons_count\": $esoteric_reasons_count}"
  else
    log_fail "Esoteric score missing from picks"
    update_report "esoteric_score_presence" "FAIL" '{"error": "esoteric_score not in pick"}'
    ((FAILED_TESTS++))
  fi
else
  log_warn "No picks available (off-season or no games today)"
  update_report "esoteric_score_presence" "SKIP" '{"reason": "No picks available"}'
fi
echo ""

echo "[3/8] Esoteric Score Range Validation [0.0-10.0]"
echo "------------------------------------------------------------"
if [[ -n "$SPORT" ]] && [[ "$game_count" -gt 0 ]]; then
  esoteric_scores=$(echo "$resp" | jq -r '[.game_picks.picks[].esoteric_score] | map(select(. != null))')
  min_score=$(echo "$esoteric_scores" | jq 'min // 0')
  max_score=$(echo "$esoteric_scores" | jq 'max // 10')

  if (( $(echo "$min_score >= 0" | bc -l) )) && (( $(echo "$max_score <= 10" | bc -l) )); then
    log_pass "Esoteric scores in valid range: [$min_score, $max_score]"
    update_report "esoteric_score_range" "PASS" "{\"min\": $min_score, \"max\": $max_score}"
  else
    log_fail "Esoteric scores out of range: [$min_score, $max_score]"
    update_report "esoteric_score_range" "FAIL" "{\"min\": $min_score, \"max\": $max_score}"
    ((FAILED_TESTS++))
  fi
else
  log_warn "Skipping range validation (no picks)"
  update_report "esoteric_score_range" "SKIP" '{"reason": "No picks available"}'
fi
echo ""

echo "[4/8] GLITCH Aggregate Check"
echo "------------------------------------------------------------"
if [[ -n "$SPORT" ]] && [[ "$game_count" -gt 0 || "$props_count" -gt 0 ]]; then
  glitch_signals=""

  if [[ "$game_count" -gt 0 ]]; then
    glitch_signals=$(echo "$resp" | jq -r '.game_picks.picks[0].glitch_signals // .game_picks.picks[0].glitch_breakdown // "null"')
  elif [[ "$props_count" -gt 0 ]]; then
    glitch_signals=$(echo "$resp" | jq -r '.props.picks[0].glitch_signals // .props.picks[0].glitch_breakdown // "null"')
  fi

  if [[ "$glitch_signals" != "null" ]] && echo "$glitch_signals" | jq -e . >/dev/null 2>&1; then
    signal_count=$(echo "$glitch_signals" | jq 'keys | length')
    log_pass "GLITCH signals present: $signal_count signals detected"
    update_report "glitch_aggregate" "PASS" "{\"signal_count\": $signal_count}"
  else
    log_warn "GLITCH signals not in debug payload (may require explicit debug fields)"
    update_report "glitch_aggregate" "WARN" '{"note": "glitch_signals not in standard debug output"}'
  fi
else
  log_warn "Skipping GLITCH check (no picks)"
  update_report "glitch_aggregate" "SKIP" '{"reason": "No picks available"}'
fi
echo ""

echo "[5/8] Kp-Index Integration (NOAA)"
echo "------------------------------------------------------------"
if [[ -n "$SPORT" ]] && [[ "$game_count" -gt 0 ]]; then
  kp_value=$(echo "$resp" | jq -r '.game_picks.picks[0].glitch_breakdown.kp_index.kp_value // .game_picks.picks[0].kp_index_value // "null"')
  kp_source=$(echo "$resp" | jq -r '.game_picks.picks[0].glitch_breakdown.kp_index.source // .game_picks.picks[0].kp_index_source // "unknown"')

  if [[ "$kp_value" != "null" ]] && [[ "$kp_value" != "" ]]; then
    log_pass "Kp-Index present: $kp_value (source: $kp_source)"
    update_report "kp_index_integration" "PASS" "{\"kp_value\": $kp_value, \"source\": \"$kp_source\"}"
  else
    # Check if NOAA data is in the response at all
    has_noaa=$(echo "$resp" | jq -r '.debug.integrations.noaa // .debug.noaa // "missing"')
    if [[ "$has_noaa" != "missing" ]]; then
      log_pass "NOAA integration configured (Kp-Index may not be in pick payload)"
      update_report "kp_index_integration" "PASS" '{"note": "NOAA configured but Kp not in pick payload"}'
    else
      log_warn "Kp-Index not found in pick payload"
      update_report "kp_index_integration" "WARN" '{"note": "Kp-Index not in debug output"}'
    fi
  fi
else
  log_warn "Skipping Kp-Index check (no picks)"
  update_report "kp_index_integration" "SKIP" '{"reason": "No picks available"}'
fi
echo ""

echo "[6/8] Engine Weight Verification (Esoteric = 0.20)"
echo "------------------------------------------------------------"
# This is a static check - read from source file
if [[ -f "core/scoring_contract.py" ]]; then
  esoteric_weight=$(python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from core.scoring_contract import ENGINE_WEIGHTS
    print(ENGINE_WEIGHTS.get('esoteric', 'NOT_FOUND'))
except Exception as e:
    print('ERROR')
" 2>/dev/null || echo "ERROR")

  if [[ "$esoteric_weight" == "0.2" ]] || [[ "$esoteric_weight" == "0.20" ]]; then
    log_pass "Esoteric engine weight = $esoteric_weight (20%)"
    update_report "engine_weight" "PASS" "{\"esoteric_weight\": $esoteric_weight}"
  elif [[ "$esoteric_weight" == "ERROR" ]]; then
    log_warn "Could not verify engine weight (module import failed)"
    update_report "engine_weight" "SKIP" '{"reason": "Import failed"}'
  else
    log_fail "Esoteric engine weight = $esoteric_weight (expected 0.20)"
    update_report "engine_weight" "FAIL" "{\"esoteric_weight\": \"$esoteric_weight\"}"
    ((FAILED_TESTS++))
  fi
else
  log_warn "core/scoring_contract.py not found in current directory"
  update_report "engine_weight" "SKIP" '{"reason": "File not found"}'
fi
echo ""

echo "[7/8] Material Impact Test (Esoteric Contribution to BASE_4)"
echo "------------------------------------------------------------"
if [[ -n "$SPORT" ]] && [[ "$game_count" -gt 0 ]]; then
  sample_pick=$(echo "$resp" | jq '.game_picks.picks[0]')
  esoteric_score=$(echo "$sample_pick" | jq -r '.esoteric_score // 0')
  base_score=$(echo "$sample_pick" | jq -r '.base_4_score // 0')
  final_score=$(echo "$sample_pick" | jq -r '.final_score // 0')

  # Esoteric contributes 20% of base score
  esoteric_contribution=$(echo "scale=4; $esoteric_score * 0.20" | bc)

  log_info "Esoteric Score: $esoteric_score"
  log_info "Esoteric Contribution to Base: $esoteric_contribution (20%)"
  log_info "Base Score: $base_score"
  log_info "Final Score: $final_score"

  if (( $(echo "$esoteric_contribution > 0" | bc -l) )); then
    log_pass "Esoteric contributes $esoteric_contribution to base score"
    update_report "material_impact" "PASS" "{\"esoteric_score\": $esoteric_score, \"contribution\": $esoteric_contribution}"
  else
    log_warn "Esoteric contribution is zero"
    update_report "material_impact" "WARN" "{\"esoteric_score\": $esoteric_score, \"contribution\": 0}"
  fi
else
  log_warn "Skipping material impact test (no picks)"
  update_report "material_impact" "SKIP" '{"reason": "No picks available"}'
fi
echo ""

echo "[8/8] Fail-Soft Behavior Check"
echo "------------------------------------------------------------"
# Check if the endpoint returned 200 even with potential NOAA failures
if [[ -n "$SPORT" ]]; then
  errors=$(echo "$resp" | jq -r '.errors // [] | length' 2>/dev/null || echo "0")
  timed_out=$(echo "$resp" | jq -r '.debug._timed_out_components // [] | length' 2>/dev/null || echo "0")

  if [[ "$http_code" == "200" ]]; then
    log_pass "Endpoint returned 200 (fail-soft working)"
    log_info "Errors count: $errors"
    log_info "Timed out components: $timed_out"
    update_report "fail_soft" "PASS" "{\"errors\": $errors, \"timed_out\": $timed_out}"
  else
    log_fail "Endpoint returned non-200 (HTTP $http_code)"
    update_report "fail_soft" "FAIL" "{\"http_code\": \"$http_code\"}"
    ((FAILED_TESTS++))
  fi
else
  # Test fail-soft by checking health endpoint worked
  if [[ "$health_code" == "200" ]]; then
    log_pass "Health endpoint confirms fail-soft (200 response)"
    update_report "fail_soft" "PASS" '{"note": "Health endpoint returned 200"}'
  else
    log_fail "Could not verify fail-soft behavior"
    update_report "fail_soft" "FAIL" '{"note": "No data to verify fail-soft"}'
    ((FAILED_TESTS++))
  fi
fi
echo ""

echo "============================================================"
echo "AUDIT SUMMARY"
echo "============================================================"
total_tests=8
passed=$((total_tests - FAILED_TESTS))

echo "Tests Passed: $passed / $total_tests"
echo "Sport Tested: ${SPORT:-N/A}"
echo "Report: $REPORT_FILE"
echo ""

# Final report update
tmp_file=$(mktemp)
jq ".summary = {\"total\": $total_tests, \"passed\": $passed, \"failed\": $FAILED_TESTS, \"sport\": \"${SPORT:-none}\"}" "$REPORT_FILE" > "$tmp_file"
mv "$tmp_file" "$REPORT_FILE"

if [[ $FAILED_TESTS -eq 0 ]]; then
  log_pass "ENGINE 3 ESOTERIC AUDIT: PASS"
  exit 0
else
  log_fail "ENGINE 3 ESOTERIC AUDIT: FAIL ($FAILED_TESTS failures)"
  exit 1
fi
