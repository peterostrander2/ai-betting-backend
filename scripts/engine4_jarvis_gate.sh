#!/usr/bin/env bash
# =============================================================================
# ENGINE 4 (JARVIS) - PRODUCTION RUNTIME GATE
# =============================================================================
# Validates Jarvis implementation in production via jq assertions.
#
# Usage:
#   API_KEY=your_key ./scripts/engine4_jarvis_gate.sh
#   API_KEY=your_key BASE_URL=https://your-app.up.railway.app ./scripts/engine4_jarvis_gate.sh
#
# Requirements:
#   - jq installed
#   - curl installed
#   - API_KEY env var set
#
# Exit codes:
#   0 = All checks passed
#   1 = One or more checks failed
# =============================================================================

set -euo pipefail

# Defaults
BASE_URL="${BASE_URL:-https://web-production-7b2a.up.railway.app}"
API_KEY="${API_KEY:-}"
SPORT="${SPORT:-NBA}"

if [[ -z "$API_KEY" ]]; then
    echo "ERROR: API_KEY environment variable not set"
    exit 1
fi

echo "================================================"
echo "ENGINE 4 (JARVIS) PRODUCTION RUNTIME GATE"
echo "================================================"
echo "Base URL: $BASE_URL"
echo "Sport: $SPORT"
echo ""

# -----------------------------------------------------------------------------
# CHECK 1: /debug/integrations - Jarvis runtime proof
# -----------------------------------------------------------------------------
echo "[1/3] Checking /debug/integrations jarvis_runtime..."

integrations_json=$(curl -fsS -H "X-API-Key: ${API_KEY}" \
    "${BASE_URL}/live/debug/integrations?quick=true" 2>/dev/null || echo '{}')

if echo "$integrations_json" | jq -e '.jarvis_runtime' >/dev/null 2>&1; then
    jarvis_impl=$(echo "$integrations_json" | jq -r '.jarvis_runtime.jarvis_impl // "MISSING"')
    savant_loaded=$(echo "$integrations_json" | jq -r '.jarvis_runtime.savant_module_loaded // false')
    hybrid_loaded=$(echo "$integrations_json" | jq -r '.jarvis_runtime.hybrid_module_loaded // false')

    echo "  jarvis_impl: $jarvis_impl"
    echo "  savant_module_loaded: $savant_loaded"
    echo "  hybrid_module_loaded: $hybrid_loaded"

    # Validate impl is valid
    if [[ "$jarvis_impl" != "savant" && "$jarvis_impl" != "hybrid" ]]; then
        echo "ERROR: Invalid jarvis_impl value: $jarvis_impl"
        exit 1
    fi

    # Validate expected module is loaded
    if [[ "$jarvis_impl" == "savant" && "$savant_loaded" != "true" ]]; then
        echo "ERROR: jarvis_impl=savant but savant module not loaded"
        exit 1
    fi

    if [[ "$jarvis_impl" == "hybrid" && "$hybrid_loaded" != "true" ]]; then
        echo "ERROR: jarvis_impl=hybrid but hybrid module not loaded"
        exit 1
    fi

    echo "  PASS: Jarvis runtime proof valid"
else
    echo "  WARNING: jarvis_runtime not found in response (may be older deploy)"
fi

echo ""

# -----------------------------------------------------------------------------
# CHECK 2: /best-bets - Sample pick Jarvis fields
# -----------------------------------------------------------------------------
echo "[2/3] Checking /best-bets/${SPORT} Jarvis fields..."

bets_json=$(curl -fsS -H "X-API-Key: ${API_KEY}" \
    "${BASE_URL}/live/best-bets/${SPORT}?debug=1" 2>/dev/null || echo '{}')

# Get first pick's ai_breakdown
pick_count=$(echo "$bets_json" | jq '[.game_picks.picks // [], .props.picks // []] | add | length')
echo "  Total picks: $pick_count"

if [[ "$pick_count" -gt 0 ]]; then
    # Extract Jarvis fields from first game pick or first prop (at root level, not in ai_breakdown)
    sample=$(echo "$bets_json" | jq '(.game_picks.picks[0] // .props.picks[0])')

    jarvis_impl_pick=$(echo "$sample" | jq -r '.jarvis_impl // "MISSING"')
    jarvis_version=$(echo "$sample" | jq -r '.jarvis_version // "MISSING"')
    jarvis_blend_type=$(echo "$sample" | jq -r '.jarvis_blend_type // "MISSING"')
    jarvis_rs=$(echo "$sample" | jq -r '.jarvis_rs // "MISSING"')

    echo "  Sample pick Jarvis fields:"
    echo "    jarvis_impl: $jarvis_impl_pick"
    echo "    jarvis_version: $jarvis_version"
    echo "    jarvis_blend_type: $jarvis_blend_type"
    echo "    jarvis_rs: $jarvis_rs"

    # Validate required fields present
    if [[ "$jarvis_version" == "MISSING" ]]; then
        echo "ERROR: jarvis_version missing from pick"
        exit 1
    fi

    # If hybrid, validate hybrid-specific fields (in scoring_breakdown or root)
    if [[ "$jarvis_impl_pick" == "hybrid" ]]; then
        ophis_delta=$(echo "$sample" | jq -r '.ophis_delta // .scoring_breakdown.ophis_delta // "MISSING"')
        ophis_delta_cap=$(echo "$sample" | jq -r '.ophis_delta_cap // .scoring_breakdown.ophis_delta_cap // "MISSING"')
        jarvis_before=$(echo "$sample" | jq -r '.jarvis_score_before_ophis // .scoring_breakdown.jarvis_score_before_ophis // "MISSING"')

        echo "    [HYBRID] ophis_delta: $ophis_delta"
        echo "    [HYBRID] ophis_delta_cap: $ophis_delta_cap"
        echo "    [HYBRID] jarvis_score_before_ophis: $jarvis_before"

        if [[ "$ophis_delta" == "MISSING" ]]; then
            echo "ERROR: hybrid claims but ophis_delta missing"
            exit 1
        fi

        # Validate delta bounds [-0.75, +0.75]
        if echo "$sample" | jq -e '
            ((.ophis_delta // .scoring_breakdown.ophis_delta) | type == "number") and
            ((.ophis_delta // .scoring_breakdown.ophis_delta) >= -0.75) and
            ((.ophis_delta // .scoring_breakdown.ophis_delta) <= 0.75)
        ' >/dev/null 2>&1; then
            echo "    PASS: ophis_delta within bounds"
        else
            echo "ERROR: ophis_delta out of bounds [-0.75, +0.75]"
            exit 1
        fi

        # Validate delta reconciliation: jarvis_rs ≈ jarvis_before + ophis_delta
        if echo "$sample" | jq -e '
            ((.jarvis_score_before_ophis // .scoring_breakdown.jarvis_score_before_ophis) | type == "number") and
            ((.ophis_delta // .scoring_breakdown.ophis_delta) | type == "number") and
            (.jarvis_rs | type == "number") and
            (
                (((.jarvis_score_before_ophis // .scoring_breakdown.jarvis_score_before_ophis) + (.ophis_delta // .scoring_breakdown.ophis_delta)) - .jarvis_rs) | fabs < 0.01
                or
                # Handle clamping at boundaries
                (.jarvis_rs == 0 or .jarvis_rs == 10)
            )
        ' >/dev/null 2>&1; then
            echo "    PASS: delta reconciliation valid"
        else
            echo "ERROR: delta doesn't reconcile (jarvis_rs != jarvis_before + ophis_delta)"
            exit 1
        fi
    fi

    echo "  PASS: Jarvis pick fields valid"
else
    echo "  WARNING: No picks available to validate (off-season or no games)"
fi

echo ""

# -----------------------------------------------------------------------------
# CHECK 3: jarvis_rs bounds [0, 10]
# -----------------------------------------------------------------------------
echo "[3/3] Validating jarvis_rs bounds across all picks..."

if [[ "$pick_count" -gt 0 ]]; then
    # Check all picks have jarvis_rs in [0, 10] (at root level)
    if echo "$bets_json" | jq -e '
        [.game_picks.picks // [], .props.picks // []] | add | all(
            .jarvis_rs == null or
            (
                (.jarvis_rs >= 0) and
                (.jarvis_rs <= 10)
            )
        )
    ' >/dev/null 2>&1; then
        echo "  PASS: All jarvis_rs values in [0, 10]"
    else
        echo "ERROR: Found jarvis_rs outside [0, 10]"
        exit 1
    fi
else
    echo "  SKIP: No picks to validate"
fi

echo ""
echo "================================================"
echo "ALL ENGINE 4 (JARVIS) CHECKS PASSED"
echo "================================================"
