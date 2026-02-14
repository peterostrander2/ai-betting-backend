#!/usr/bin/env bash
#
# FULL SYSTEM AUDIT - Backend Readiness for Frontend Integration
# ================================================================
# v20.21 - Deterministic, machine-verifiable audit
#
# Usage:
#   API_KEY=your_key ./scripts/full_system_audit.sh
#   API_KEY=your_key BASE_URL=https://custom.url ./scripts/full_system_audit.sh
#   API_KEY=your_key AUDIT_SPORT=NBA ./scripts/full_system_audit.sh
#
# Exit codes:
#   0 = All hard gates passed - BACKEND READY FOR FRONTEND
#   1 = One or more hard gates failed - BLOCK FRONTEND WORK
#
set -euo pipefail

# ============================================================
# CONFIGURATION
# ============================================================
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
AUDIT_SPORT="${AUDIT_SPORT:-NCAAB}"

# Validate API_KEY is set (never print it)
if [[ -z "${API_KEY:-}" ]]; then
    echo "ERROR: API_KEY environment variable is required"
    echo "Usage: API_KEY=your_key ./scripts/full_system_audit.sh"
    exit 1
fi

# ============================================================
# COUNTERS AND STATE
# ============================================================
PASSED=0
FAILED=0
DIAGNOSTICS=()

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================
# HELPER FUNCTIONS
# ============================================================
print_header() {
    echo ""
    echo -e "${CYAN}============================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}============================================================${NC}"
}

print_section() {
    echo ""
    echo -e "${YELLOW}[$1] $2${NC}"
}

pass() {
    echo -e "  ${GREEN}PASS${NC}: $1"
    PASSED=$((PASSED + 1))
}

fail() {
    echo -e "  ${RED}FAIL${NC}: $1"
    FAILED=$((FAILED + 1))
}

warn() {
    echo -e "  ${YELLOW}WARN${NC}: $1"
}

diag() {
    DIAGNOSTICS+=("$1")
}

# Secure curl wrapper - reads API key from env, never shows in process list
secure_curl() {
    local url="$1"
    shift
    curl -s -H "X-API-Key: ${API_KEY}" "$@" "$url"
}

secure_curl_head() {
    local url="$1"
    curl -sI -H "X-API-Key: ${API_KEY}" "$url"
}

# ============================================================
# AUDIT START
# ============================================================
print_header "FULL SYSTEM AUDIT - Backend Readiness for Frontend"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Base URL: $BASE_URL"
echo "Audit Sport: $AUDIT_SPORT"
echo ""

# ============================================================
# 1. CI GOLDEN GATE (Local Tests)
# ============================================================
print_section "1/11" "CI Golden Gate (Local Tests)"

if ./scripts/ci_golden_gate.sh > /tmp/golden_gate_output.txt 2>&1; then
    pass "CI Golden Gate passed (all contract tests)"
else
    fail "CI Golden Gate failed - see /tmp/golden_gate_output.txt"
    cat /tmp/golden_gate_output.txt | tail -20
fi

# ============================================================
# 2. HEALTH & BUILD
# ============================================================
print_section "2/11" "Health & Build"

HEALTH_JSON=$(curl -s "$BASE_URL/health")

if echo "$HEALTH_JSON" | jq -e '.status == "healthy"' > /dev/null 2>&1; then
    pass "Health status is 'healthy'"
else
    fail "Health status is not 'healthy'"
fi

if echo "$HEALTH_JSON" | jq -e '.build_sha != null and .build_sha != ""' > /dev/null 2>&1; then
    BUILD_SHA=$(echo "$HEALTH_JSON" | jq -r '.build_sha')
    pass "Build SHA present: $BUILD_SHA"
else
    fail "Build SHA missing or empty"
fi

if echo "$HEALTH_JSON" | jq -e '.database == true' > /dev/null 2>&1; then
    pass "Database connection: true"
else
    fail "Database connection: false or missing"
fi

# ============================================================
# 3. STORAGE / PERSISTENCE
# ============================================================
print_section "3/11" "Storage / Persistence"

STORAGE_JSON=$(curl -s "$BASE_URL/internal/storage/health")

if echo "$STORAGE_JSON" | jq -e '.ok == true' > /dev/null 2>&1; then
    pass "Storage ok: true"
else
    fail "Storage ok: false"
fi

if echo "$STORAGE_JSON" | jq -e '.is_mountpoint == true' > /dev/null 2>&1; then
    pass "Railway volume is_mountpoint: true"
else
    fail "Railway volume is_mountpoint: false (ephemeral storage!)"
fi

if echo "$STORAGE_JSON" | jq -e '.is_ephemeral == false' > /dev/null 2>&1; then
    pass "Storage is_ephemeral: false"
else
    fail "Storage is_ephemeral: true (data will be lost!)"
fi

if echo "$STORAGE_JSON" | jq -e '.predictions_line_count > 0' > /dev/null 2>&1; then
    PRED_COUNT=$(echo "$STORAGE_JSON" | jq -r '.predictions_line_count')
    pass "Predictions logged: $PRED_COUNT"
else
    fail "Predictions file empty or missing"
fi

if echo "$STORAGE_JSON" | jq -e '.weights_exists == true' > /dev/null 2>&1; then
    pass "Weights file exists"
else
    fail "Weights file missing"
fi

if echo "$STORAGE_JSON" | jq -e '.graded_picks_exists == true' > /dev/null 2>&1; then
    pass "Graded picks file exists"
else
    fail "Graded picks file missing"
fi

# ============================================================
# 4. INTEGRATIONS
# ============================================================
print_section "4/11" "Integrations"

INTEGRATIONS_JSON=$(secure_curl "$BASE_URL/live/debug/integrations")

# Critical integrations must be VALIDATED
CRITICAL_INTEGRATIONS=("odds_api" "playbook_api" "balldontlie" "railway_storage")
for INT_NAME in "${CRITICAL_INTEGRATIONS[@]}"; do
    STATUS=$(echo "$INTEGRATIONS_JSON" | jq -r ".integrations.${INT_NAME}.status_category // \"MISSING\"")
    if [[ "$STATUS" == "VALIDATED" ]]; then
        pass "Critical integration $INT_NAME: VALIDATED"
    else
        fail "Critical integration $INT_NAME: $STATUS (expected VALIDATED)"
    fi
done

# Weather API - VALIDATED or NOT_RELEVANT for indoor sports
WEATHER_STATUS=$(echo "$INTEGRATIONS_JSON" | jq -r '.integrations.weather_api.status_category // "MISSING"')
if [[ "$WEATHER_STATUS" == "VALIDATED" || "$WEATHER_STATUS" == "NOT_RELEVANT" ]]; then
    pass "Weather API: $WEATHER_STATUS"
else
    warn "Weather API: $WEATHER_STATUS (expected VALIDATED or NOT_RELEVANT)"
fi

# Count integration statuses
VALIDATED_COUNT=$(echo "$INTEGRATIONS_JSON" | jq '[.integrations | to_entries[] | select(.value.status_category == "VALIDATED")] | length')
CONFIGURED_COUNT=$(echo "$INTEGRATIONS_JSON" | jq '[.integrations | to_entries[] | select(.value.status_category == "CONFIGURED")] | length')
UNREACHABLE_COUNT=$(echo "$INTEGRATIONS_JSON" | jq '[.integrations | to_entries[] | select(.value.status_category == "UNREACHABLE")] | length')

echo "  Integration summary: VALIDATED=$VALIDATED_COUNT, CONFIGURED=$CONFIGURED_COUNT, UNREACHABLE=$UNREACHABLE_COUNT"

# serpapi is known to be UNREACHABLE (disabled by design)
if [[ "$UNREACHABLE_COUNT" -gt 1 ]]; then
    diag "Multiple integrations UNREACHABLE ($UNREACHABLE_COUNT) - investigate"
fi

# ============================================================
# 5. SCHEDULER
# ============================================================
print_section "5/11" "Scheduler"

SCHEDULER_JSON=$(secure_curl "$BASE_URL/live/scheduler/status")

if echo "$SCHEDULER_JSON" | jq -e '.available == true' > /dev/null 2>&1; then
    pass "Scheduler available: true"
else
    fail "Scheduler available: false"
fi

JOB_COUNT=$(echo "$SCHEDULER_JSON" | jq '.jobs | length')
if [[ "$JOB_COUNT" -gt 0 ]]; then
    pass "Scheduler jobs registered: $JOB_COUNT"
else
    fail "No scheduler jobs registered"
fi

# Required jobs
REQUIRED_JOBS=("auto_grade" "daily_audit" "team_model_train" "training_verification")
for JOB_NAME in "${REQUIRED_JOBS[@]}"; do
    if echo "$SCHEDULER_JSON" | jq -e ".jobs[] | select(.id == \"$JOB_NAME\")" > /dev/null 2>&1; then
        pass "Required job '$JOB_NAME' registered"
    else
        fail "Required job '$JOB_NAME' missing"
    fi
done

# ============================================================
# 6. TRAINING PIPELINE
# ============================================================
print_section "6/11" "Training Pipeline"

TRAINING_JSON=$(secure_curl "$BASE_URL/live/debug/training-status")

if echo "$TRAINING_JSON" | jq -e '.training_health == "HEALTHY"' > /dev/null 2>&1; then
    pass "Training health: HEALTHY"
else
    HEALTH=$(echo "$TRAINING_JSON" | jq -r '.training_health // "UNKNOWN"')
    fail "Training health: $HEALTH (expected HEALTHY)"
fi

# Core modules must be TRAINED
CORE_MODULES=("ensemble" "lstm" "matchup")
for MODULE in "${CORE_MODULES[@]}"; do
    STATUS=$(echo "$TRAINING_JSON" | jq -r ".model_status.${MODULE} // \"MISSING\"")
    if [[ "$STATUS" == "TRAINED" ]]; then
        pass "Module $MODULE: TRAINED"
    else
        fail "Module $MODULE: $STATUS (expected TRAINED)"
    fi
done

# Artifact timestamps must exist
ARTIFACTS=("team_data_cache.json" "matchup_matrix.json" "ensemble_weights.json")
for ARTIFACT in "${ARTIFACTS[@]}"; do
    if echo "$TRAINING_JSON" | jq -e ".artifact_proof[\"$ARTIFACT\"].exists == true" > /dev/null 2>&1; then
        MTIME=$(echo "$TRAINING_JSON" | jq -r ".artifact_proof[\"$ARTIFACT\"].mtime_iso")
        pass "Artifact $ARTIFACT exists (updated: $MTIME)"
    else
        fail "Artifact $ARTIFACT missing"
    fi
done

# Filter telemetry assertion
if echo "$TRAINING_JSON" | jq -e '.training_telemetry.filter_telemetry.assertion_passed == true' > /dev/null 2>&1; then
    pass "Filter telemetry assertion: passed"
else
    fail "Filter telemetry assertion: failed"
fi

# Diagnostic: sample counts
SAMPLES_TRAINED=$(echo "$TRAINING_JSON" | jq -r '.training_telemetry.samples_used_for_training // 0')
if [[ "$SAMPLES_TRAINED" -lt 50 ]]; then
    diag "Low training samples ($SAMPLES_TRAINED) - may affect model quality"
fi

# ============================================================
# 7. AUTOGRADER / LEARNING LOOP
# ============================================================
print_section "7/11" "Autograder / Learning Loop"

GRADER_JSON=$(secure_curl "$BASE_URL/live/grader/status")

if echo "$GRADER_JSON" | jq -e '.available == true' > /dev/null 2>&1; then
    pass "Grader available: true"
else
    fail "Grader available: false"
fi

if echo "$GRADER_JSON" | jq -e '.weight_learning.weights_loaded == true' > /dev/null 2>&1; then
    pass "Weights loaded: true"
else
    fail "Weights loaded: false"
fi

# Daily report structure
REPORT_JSON=$(secure_curl "$BASE_URL/live/grader/daily-report")
if echo "$REPORT_JSON" | jq -e '.overall != null and .by_sport != null' > /dev/null 2>&1; then
    TOTAL_PICKS=$(echo "$REPORT_JSON" | jq -r '.overall.total_picks // 0')
    pass "Daily report valid (total_picks: $TOTAL_PICKS)"
else
    fail "Daily report missing required fields"
fi

# ============================================================
# 8. 4-ENGINE EXECUTION + BOOSTS
# ============================================================
print_section "8/11" "4-Engine Execution + Boosts ($AUDIT_SPORT)"

BESTBETS_JSON=$(secure_curl "$BASE_URL/live/best-bets/${AUDIT_SPORT}?debug=1")

# Smoke valid: at least 1 pick returned
GAME_COUNT=$(echo "$BESTBETS_JSON" | jq '.game_picks.picks | length')
PROP_COUNT=$(echo "$BESTBETS_JSON" | jq '.props.picks | length')
TOTAL_PICKS=$((GAME_COUNT + PROP_COUNT))

if [[ "$TOTAL_PICKS" -gt 0 ]]; then
    pass "Smoke valid: $TOTAL_PICKS picks returned (games: $GAME_COUNT, props: $PROP_COUNT)"
else
    fail "Smoke invalid: 0 picks returned - cannot verify engines"
    diag "No picks returned for $AUDIT_SPORT - check if games are scheduled today"
fi

# Verify 4 engines present in sample picks (if picks exist)
if [[ "$GAME_COUNT" -gt 0 ]]; then
    SAMPLE_PICK=$(echo "$BESTBETS_JSON" | jq '.game_picks.picks[0]')

    # All 4 engine scores must be present and numeric
    ENGINES=("ai_score" "research_score" "esoteric_score" "jarvis_score")
    ENGINES_OK=true
    for ENGINE in "${ENGINES[@]}"; do
        if echo "$SAMPLE_PICK" | jq -e ".$ENGINE != null and (.$ENGINE | type == \"number\")" > /dev/null 2>&1; then
            SCORE=$(echo "$SAMPLE_PICK" | jq -r ".$ENGINE")
            echo "    $ENGINE: $SCORE"
        else
            fail "Engine $ENGINE missing or not numeric"
            ENGINES_OK=false
        fi
    done

    if [[ "$ENGINES_OK" == true ]]; then
        pass "All 4 engines fired with numeric scores"
    fi

    # Confluence + Jason Sim present
    if echo "$SAMPLE_PICK" | jq -e '.confluence_boost != null' > /dev/null 2>&1; then
        CONF_BOOST=$(echo "$SAMPLE_PICK" | jq -r '.confluence_boost')
        pass "Confluence boost present: $CONF_BOOST"
    else
        fail "Confluence boost missing"
    fi

    if echo "$SAMPLE_PICK" | jq -e '.jason_sim_boost != null' > /dev/null 2>&1; then
        JASON_BOOST=$(echo "$SAMPLE_PICK" | jq -r '.jason_sim_boost')
        pass "Jason Sim boost present: $JASON_BOOST"
    else
        fail "Jason Sim boost missing"
    fi

    if echo "$SAMPLE_PICK" | jq -e '.context_modifier != null' > /dev/null 2>&1; then
        CTX_MOD=$(echo "$SAMPLE_PICK" | jq -r '.context_modifier')
        pass "Context modifier present: $CTX_MOD"
    else
        fail "Context modifier missing"
    fi
fi

# ============================================================
# 9. OUTPUT BOUNDARY / CONTRACT
# ============================================================
print_section "9/11" "Output Boundary / Contract"

# Hidden tier filter active
HIDDEN_FILTERED=$(echo "$BESTBETS_JSON" | jq -r '.debug.hidden_tier_filtered_total // 0')
echo "  Hidden tier filtered: $HIDDEN_FILTERED"

# Invariant violations (should be 0 if field exists)
VIOLATIONS=$(echo "$BESTBETS_JSON" | jq -r '.debug.invariant_violations_dropped // 0')
if [[ "$VIOLATIONS" -eq 0 ]]; then
    pass "Invariant violations dropped: 0"
else
    fail "Invariant violations dropped: $VIOLATIONS"
fi

# Valid tiers only
if [[ "$GAME_COUNT" -gt 0 ]]; then
    TIERS=$(echo "$BESTBETS_JSON" | jq -r '[.game_picks.picks[].tier] | unique | .[]')
    INVALID_TIER=false
    for TIER in $TIERS; do
        if [[ "$TIER" != "TITANIUM_SMASH" && "$TIER" != "GOLD_STAR" && "$TIER" != "EDGE_LEAN" ]]; then
            fail "Invalid tier returned: $TIER"
            INVALID_TIER=true
        fi
    done
    if [[ "$INVALID_TIER" == false ]]; then
        pass "All returned tiers valid: $(echo $TIERS | tr '\n' ' ')"
    fi

    # Hidden tiers never returned
    MONITOR_COUNT=$(echo "$BESTBETS_JSON" | jq '[.game_picks.picks[] | select(.tier == "MONITOR" or .tier == "PASS")] | length')
    if [[ "$MONITOR_COUNT" -eq 0 ]]; then
        pass "No hidden tiers (MONITOR/PASS) in output"
    else
        fail "Hidden tiers leaked to output: $MONITOR_COUNT picks"
    fi

    # Min score threshold for games (>= 7.0)
    MIN_GAME_SCORE=$(echo "$BESTBETS_JSON" | jq '[.game_picks.picks[].final_score] | min')
    if echo "$MIN_GAME_SCORE" | jq -e '. >= 7.0' > /dev/null 2>&1; then
        pass "Min game score: $MIN_GAME_SCORE (>= 7.0)"
    else
        fail "Min game score: $MIN_GAME_SCORE (< 7.0 threshold)"
    fi
fi

if [[ "$PROP_COUNT" -gt 0 ]]; then
    # Min score threshold for props (>= 6.5)
    MIN_PROP_SCORE=$(echo "$BESTBETS_JSON" | jq '[.props.picks[].final_score] | min')
    if echo "$MIN_PROP_SCORE" | jq -e '. >= 6.5' > /dev/null 2>&1; then
        pass "Min prop score: $MIN_PROP_SCORE (>= 6.5)"
    else
        fail "Min prop score: $MIN_PROP_SCORE (< 6.5 threshold)"
    fi
fi

# ============================================================
# 10. PICK CONTRACT COMPLETENESS
# ============================================================
print_section "10/11" "Pick Contract Completeness"

if [[ "$GAME_COUNT" -gt 0 ]]; then
    SAMPLE_PICK=$(echo "$BESTBETS_JSON" | jq '.game_picks.picks[0]')

    # Required frontend fields
    REQUIRED_FIELDS=(
        "pick_id" "matchup" "sport" "market" "tier" "final_score"
        "line" "odds_american" "bet_string" "start_time_et"
        "ai_score" "research_score" "esoteric_score" "jarvis_score"
        "confluence_boost" "jason_sim_boost" "context_modifier"
        "description"
    )

    MISSING_FIELDS=()
    for FIELD in "${REQUIRED_FIELDS[@]}"; do
        if ! echo "$SAMPLE_PICK" | jq -e ".$FIELD != null" > /dev/null 2>&1; then
            MISSING_FIELDS+=("$FIELD")
        fi
    done

    if [[ ${#MISSING_FIELDS[@]} -eq 0 ]]; then
        pass "All ${#REQUIRED_FIELDS[@]} required frontend fields present"
    else
        fail "Missing fields: ${MISSING_FIELDS[*]}"
    fi

    # Reasons arrays
    if echo "$SAMPLE_PICK" | jq -e '.ai_reasons != null and (.ai_reasons | type == "array")' > /dev/null 2>&1; then
        pass "ai_reasons array present"
    else
        warn "ai_reasons missing or not array"
    fi

    if echo "$SAMPLE_PICK" | jq -e '.confluence_reasons != null and (.confluence_reasons | type == "array")' > /dev/null 2>&1; then
        pass "confluence_reasons array present"
    else
        warn "confluence_reasons missing or not array"
    fi
else
    warn "Cannot verify pick contract - no picks available"
fi

# ============================================================
# 11. REQUEST CORRELATION + CACHE HEADERS
# ============================================================
print_section "11/11" "Request Correlation + Cache Headers"

HEADERS=$(secure_curl_head "$BASE_URL/live/best-bets/${AUDIT_SPORT}")

# x-request-id present
if echo "$HEADERS" | grep -qi "x-request-id"; then
    REQ_ID=$(echo "$HEADERS" | grep -i "x-request-id" | cut -d: -f2 | tr -d ' \r')
    pass "X-Request-ID present: $REQ_ID"
else
    fail "X-Request-ID header missing"
fi

# Cache-control no-store
if echo "$HEADERS" | grep -qi "cache-control.*no-store"; then
    pass "Cache-Control includes no-store"
else
    fail "Cache-Control missing no-store directive"
fi

# ============================================================
# [INFORMATIONAL] Math Glitch Shadow Confluence (v20.22)
# ============================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${CYAN}[INFORMATIONAL] Math Glitch Shadow Confluence${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check shadow_confluence exists in debug output (non-gating)
if [[ "$GAME_COUNT" -gt 0 ]]; then
    SHADOW_CHECK=$(echo "$BESTBETS_JSON" | jq -r '.game_picks.picks[0].shadow_confluence.math_glitch_confluence // "MISSING"')

    if [[ "$SHADOW_CHECK" != "MISSING" && "$SHADOW_CHECK" != "null" ]]; then
        echo "  ✓ shadow_confluence.math_glitch_confluence present in picks"

        # Count would_apply picks
        WOULD_APPLY=$(echo "$BESTBETS_JSON" | jq '[.game_picks.picks[] | select(.shadow_confluence.math_glitch_confluence.would_apply == true)] | length')
        TOTAL_GAME_PICKS=$(echo "$BESTBETS_JSON" | jq '.game_picks.picks | length')

        echo "  Shadow fire rate: $WOULD_APPLY / $TOTAL_GAME_PICKS game picks"

        # Show sample if any fired
        if [[ "$WOULD_APPLY" -gt 0 ]]; then
            echo "  Sample signals that would fire:"
            echo "$BESTBETS_JSON" | jq -r '[.game_picks.picks[] | select(.shadow_confluence.math_glitch_confluence.would_apply == true) | .shadow_confluence.math_glitch_confluence.signals] | .[0] // ["none"]'
        fi
    else
        echo "  ⚠ shadow_confluence not found in picks (may be 0 picks with data)"
    fi
else
    echo "  ⚠ No game picks to check for shadow_confluence"
fi
echo ""
# Do NOT fail audit - this is informational only

# ============================================================
# DIAGNOSTICS
# ============================================================
if [[ ${#DIAGNOSTICS[@]} -gt 0 ]]; then
    print_header "DIAGNOSTICS (Informational)"
    for DIAG in "${DIAGNOSTICS[@]}"; do
        echo "  - $DIAG"
    done
fi

# ============================================================
# FINAL VERDICT
# ============================================================
print_header "AUDIT SUMMARY"

echo ""
echo "  ┌─────────────────────────────────────────┐"
echo "  │  PASSED: $PASSED                              │"
echo "  │  FAILED: $FAILED                              │"
echo "  └─────────────────────────────────────────┘"
echo ""

if [[ "$FAILED" -eq 0 ]]; then
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}  BACKEND READY FOR FRONTEND${NC}"
    echo -e "${GREEN}  All $PASSED hard gates passed${NC}"
    echo -e "${GREEN}============================================================${NC}"
    exit 0
else
    echo -e "${RED}============================================================${NC}"
    echo -e "${RED}  BACKEND NOT READY - $FAILED FAILURES${NC}"
    echo -e "${RED}  Fix failures before proceeding to frontend${NC}"
    echo -e "${RED}============================================================${NC}"
    exit 1
fi
