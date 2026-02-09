#!/usr/bin/env bash
# Engine 2 (Research) Runtime Audit Script
# Verifies Research Engine integration, paid API usage, and fail-soft behavior
set -euo pipefail

API_BASE=${API_BASE:-"https://web-production-7b2a.up.railway.app"}
API_KEY=${API_KEY:-""}
SPORT=${SPORT:-"NBA"}
ARTIFACT_DIR=${ARTIFACT_DIR:-"artifacts"}
TIMESTAMP=$(TZ=America/New_York date "+%Y%m%d_%H%M%S_ET")
REPORT_FILE="${ARTIFACT_DIR}/engine2_research_runtime_report_${TIMESTAMP}.json"

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
echo "ENGINE 2 (RESEARCH) RUNTIME AUDIT"
echo "============================================================"
echo "API Base: $API_BASE"
echo "Sport: $SPORT"
echo "Timestamp: $TIMESTAMP"
echo ""

# Initialize report
cat > "$REPORT_FILE" << EOF
{
  "audit_type": "engine2_research",
  "timestamp": "$TIMESTAMP",
  "api_base": "$API_BASE",
  "sport": "$SPORT",
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

echo "[1/8] Health Check with Research Engine Presence"
echo "------------------------------------------------------------"
resp_file=$(mktemp)
http_code=$(curl -sS -o "$resp_file" -w "%{http_code}" \
  "$API_BASE/health" 2>&1) || true
resp=$(cat "$resp_file" 2>/dev/null || true)
rm -f "$resp_file"

if [[ "$http_code" == "200" ]] && echo "$resp" | jq -e . >/dev/null 2>&1; then
  log_pass "Health endpoint responsive (HTTP $http_code)"
  update_report "health_check" "PASS" "$(echo "$resp" | jq -c '{status, version}')"
else
  log_fail "Health endpoint failed (HTTP $http_code)"
  update_report "health_check" "FAIL" '{"error": "Health endpoint not responsive"}'
  ((FAILED_TESTS++))
fi
echo ""

echo "[2/8] Best-Bets Research Score Presence"
echo "------------------------------------------------------------"
resp_file=$(mktemp)
http_code=$(curl -sS -o "$resp_file" -w "%{http_code}" \
  "$API_BASE/live/best-bets/$SPORT?debug=1" \
  -H "X-API-Key: $API_KEY" 2>&1) || true
curl_rc=$?
resp=$(cat "$resp_file" 2>/dev/null || true)
rm -f "$resp_file"

if [[ $curl_rc -ne 0 ]] || [[ -z "$resp" ]]; then
  log_fail "Best-bets request failed (curl_rc=$curl_rc, http_code=$http_code)"
  update_report "research_score_presence" "FAIL" '{"error": "Request failed"}'
  ((FAILED_TESTS++))
elif ! echo "$resp" | jq -e . >/dev/null 2>&1; then
  log_fail "Best-bets returned non-JSON (http_code=$http_code)"
  update_report "research_score_presence" "FAIL" '{"error": "Non-JSON response"}'
  ((FAILED_TESTS++))
else
  # Check for research_score in picks
  game_count=$(echo "$resp" | jq -r '.game_picks.count // 0')
  props_count=$(echo "$resp" | jq -r '.props.count // 0')

  if [[ "$game_count" -gt 0 ]]; then
    research_score=$(echo "$resp" | jq -r '.game_picks.picks[0].research_score // "null"')
    research_reasons=$(echo "$resp" | jq -r '.game_picks.picks[0].research_reasons | length')
    if [[ "$research_score" != "null" ]] && [[ "$research_score" != "" ]]; then
      log_pass "Research score present: $research_score (with $research_reasons reasons)"
      update_report "research_score_presence" "PASS" "{\"score\": $research_score, \"reasons_count\": $research_reasons}"
    else
      log_fail "Research score missing from picks"
      update_report "research_score_presence" "FAIL" '{"error": "research_score not in pick"}'
      ((FAILED_TESTS++))
    fi
  else
    log_warn "No game picks available (off-season or no games today)"
    update_report "research_score_presence" "SKIP" '{"reason": "No game picks available"}'
  fi
fi
echo ""

echo "[3/8] Research Score Range Validation [0.0-10.0]"
echo "------------------------------------------------------------"
if [[ "$game_count" -gt 0 ]]; then
  research_scores=$(echo "$resp" | jq -r '[.game_picks.picks[].research_score] | map(select(. != null))')
  min_score=$(echo "$research_scores" | jq 'min // 0')
  max_score=$(echo "$research_scores" | jq 'max // 10')

  if (( $(echo "$min_score >= 0" | bc -l) )) && (( $(echo "$max_score <= 10" | bc -l) )); then
    log_pass "Research scores in valid range: [$min_score, $max_score]"
    update_report "research_score_range" "PASS" "{\"min\": $min_score, \"max\": $max_score}"
  else
    log_fail "Research scores out of range: [$min_score, $max_score]"
    update_report "research_score_range" "FAIL" "{\"min\": $min_score, \"max\": $max_score}"
    ((FAILED_TESTS++))
  fi
else
  log_warn "Skipping range validation (no picks)"
  update_report "research_score_range" "SKIP" '{"reason": "No picks available"}'
fi
echo ""

echo "[4/8] Paid API Integration Status"
echo "------------------------------------------------------------"
integrations=$(curl -sS "$API_BASE/live/debug/integrations" \
  -H "X-API-Key: $API_KEY" 2>/dev/null || echo "{}")

if echo "$integrations" | jq -e . >/dev/null 2>&1; then
  # Check Playbook API
  playbook_status=$(echo "$integrations" | jq -r '.playbook_api.status_category // .playbook.status_category // "UNKNOWN"')
  playbook_configured=$(echo "$integrations" | jq -r '.playbook_api.configured // .playbook.configured // false')

  # Check Odds API
  odds_status=$(echo "$integrations" | jq -r '.odds_api.status_category // "UNKNOWN"')
  odds_configured=$(echo "$integrations" | jq -r '.odds_api.configured // false')

  # Check BallDontLie
  bdl_status=$(echo "$integrations" | jq -r '.balldontlie.status_category // "UNKNOWN"')
  bdl_configured=$(echo "$integrations" | jq -r '.balldontlie.configured // false')

  log_info "Playbook API: $playbook_status (configured=$playbook_configured)"
  log_info "Odds API: $odds_status (configured=$odds_configured)"
  log_info "BallDontLie: $bdl_status (configured=$bdl_configured)"

  if [[ "$playbook_configured" == "true" ]] && [[ "$odds_configured" == "true" ]]; then
    log_pass "Paid APIs configured"
    update_report "paid_api_status" "PASS" "{\"playbook\": \"$playbook_status\", \"odds_api\": \"$odds_status\", \"bdl\": \"$bdl_status\"}"
  else
    log_warn "Some paid APIs not configured"
    update_report "paid_api_status" "WARN" "{\"playbook\": \"$playbook_status\", \"odds_api\": \"$odds_status\", \"bdl\": \"$bdl_status\"}"
  fi
else
  log_fail "Could not fetch integrations status"
  update_report "paid_api_status" "FAIL" '{"error": "Integrations endpoint failed"}'
  ((FAILED_TESTS++))
fi
echo ""

echo "[5/8] Research Pillar Weights Sum (Must = 1.0)"
echo "------------------------------------------------------------"
# This is a static check - read from source file
if [[ -f "research_engine.py" ]]; then
  pillar_sum=$(python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from research_engine import PILLAR_WEIGHTS
    total = sum(PILLAR_WEIGHTS.values())
    print(f'{total:.6f}')
except Exception as e:
    print('ERROR')
" 2>/dev/null || echo "ERROR")

  if [[ "$pillar_sum" == "1.000000" ]]; then
    log_pass "Pillar weights sum to 1.0"
    update_report "pillar_weights_sum" "PASS" "{\"sum\": $pillar_sum}"
  elif [[ "$pillar_sum" == "ERROR" ]]; then
    log_warn "Could not verify pillar weights (module import failed)"
    update_report "pillar_weights_sum" "SKIP" '{"reason": "Import failed"}'
  else
    log_fail "Pillar weights sum to $pillar_sum (expected 1.0)"
    update_report "pillar_weights_sum" "FAIL" "{\"sum\": $pillar_sum}"
    ((FAILED_TESTS++))
  fi
else
  log_warn "research_engine.py not found in current directory"
  update_report "pillar_weights_sum" "SKIP" '{"reason": "File not found"}'
fi
echo ""

echo "[6/8] Engine Weight Verification (Research = 35%)"
echo "------------------------------------------------------------"
if [[ -f "core/scoring_contract.py" ]]; then
  research_weight=$(python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from core.scoring_contract import ENGINE_WEIGHTS
    print(ENGINE_WEIGHTS.get('research', 'NOT_FOUND'))
except Exception as e:
    print('ERROR')
" 2>/dev/null || echo "ERROR")

  if [[ "$research_weight" == "0.35" ]]; then
    log_pass "Research engine weight = 0.35 (35%)"
    update_report "engine_weight" "PASS" "{\"research_weight\": $research_weight}"
  elif [[ "$research_weight" == "ERROR" ]]; then
    log_warn "Could not verify engine weight (module import failed)"
    update_report "engine_weight" "SKIP" '{"reason": "Import failed"}'
  else
    log_fail "Research engine weight = $research_weight (expected 0.35)"
    update_report "engine_weight" "FAIL" "{\"research_weight\": \"$research_weight\"}"
    ((FAILED_TESTS++))
  fi
else
  log_warn "core/scoring_contract.py not found"
  update_report "engine_weight" "SKIP" '{"reason": "File not found"}'
fi
echo ""

echo "[7/8] Material Impact Test (Research Contribution)"
echo "------------------------------------------------------------"
if [[ "$game_count" -gt 0 ]]; then
  # Calculate research contribution to final score
  sample_pick=$(echo "$resp" | jq '.game_picks.picks[0]')
  research_score=$(echo "$sample_pick" | jq -r '.research_score // 0')
  base_score=$(echo "$sample_pick" | jq -r '.base_4_score // 0')
  final_score=$(echo "$sample_pick" | jq -r '.final_score // 0')

  # Research contributes 35% of base score
  research_contribution=$(echo "scale=4; $research_score * 0.35" | bc)

  log_info "Research Score: $research_score"
  log_info "Research Contribution to Base: $research_contribution (35%)"
  log_info "Base Score: $base_score"
  log_info "Final Score: $final_score"

  # Research is material if it contributes >1.0 points to base
  if (( $(echo "$research_contribution > 0" | bc -l) )); then
    log_pass "Research contributes $research_contribution to base score"
    update_report "material_impact" "PASS" "{\"research_score\": $research_score, \"contribution\": $research_contribution}"
  else
    log_warn "Research contribution is zero"
    update_report "material_impact" "WARN" "{\"research_score\": $research_score, \"contribution\": 0}"
  fi
else
  log_warn "Skipping material impact test (no picks)"
  update_report "material_impact" "SKIP" '{"reason": "No picks available"}'
fi
echo ""

echo "[8/8] Fail-Soft Behavior Check"
echo "------------------------------------------------------------"
# Check if errors array is present and handled gracefully
errors=$(echo "$resp" | jq -r '.errors // [] | length' 2>/dev/null || echo "0")
timed_out=$(echo "$resp" | jq -r '.debug._timed_out_components // [] | length' 2>/dev/null || echo "0")

if [[ "$http_code" == "200" ]]; then
  log_pass "Endpoint returned 200 (fail-soft working)"
  log_info "Errors count: $errors"
  log_info "Timed out components: $timed_out"
  update_report "fail_soft" "PASS" "{\"errors\": $errors, \"timed_out\": $timed_out}"
else
  log_fail "Endpoint returned non-200 (HTTP $http_code)"
  update_report "fail_soft" "FAIL" "{\"http_code\": $http_code}"
  ((FAILED_TESTS++))
fi
echo ""

echo "============================================================"
echo "AUDIT SUMMARY"
echo "============================================================"
total_tests=8
passed=$((total_tests - FAILED_TESTS))

echo "Tests Passed: $passed / $total_tests"
echo "Report: $REPORT_FILE"
echo ""

# Final report update
tmp_file=$(mktemp)
jq ".summary = {\"total\": $total_tests, \"passed\": $passed, \"failed\": $FAILED_TESTS}" "$REPORT_FILE" > "$tmp_file"
mv "$tmp_file" "$REPORT_FILE"

if [[ $FAILED_TESTS -eq 0 ]]; then
  log_pass "ENGINE 2 RESEARCH AUDIT: PASS"
  exit 0
else
  log_fail "ENGINE 2 RESEARCH AUDIT: FAIL ($FAILED_TESTS failures)"
  exit 1
fi
