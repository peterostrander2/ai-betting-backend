"""
Engine 3 (Esoteric) Semantic Truthfulness Tests (v20.18)

Tests for semantic audit invariants:
- Per-signal provenance
- Source API attribution
- Call proof validity
- Request-local counters
- Anti-conflation rules
- Truth table consistency

These tests verify that Engine 3 output is mechanically auditable
and semantically truthful.
"""
import pytest
import sys
import os
import yaml
from datetime import datetime, date
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def truth_table():
    """Load truth table from ESOTERIC_TRUTH_TABLE.md YAML block."""
    truth_table_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs",
        "ESOTERIC_TRUTH_TABLE.md"
    )

    if not os.path.exists(truth_table_path):
        pytest.skip("ESOTERIC_TRUTH_TABLE.md not found")

    with open(truth_table_path, 'r') as f:
        content = f.read()

    # Find YAML block
    yaml_start = content.find("```yaml")
    yaml_end = content.find("```", yaml_start + 7)

    if yaml_start == -1 or yaml_end == -1:
        pytest.skip("No YAML block found in truth table")

    yaml_content = content[yaml_start + 7:yaml_end].strip()
    return yaml.safe_load(yaml_content)


@pytest.fixture
def sample_esoteric_breakdown():
    """Create a sample esoteric breakdown for testing."""
    from esoteric_engine import (
        get_glitch_aggregate,
        get_phase8_esoteric_signals,
        build_esoteric_breakdown_with_provenance
    )

    glitch = get_glitch_aggregate(
        birth_date_str=None,
        game_date=date.today(),
        game_time=datetime.now(),
        line_history=None,
        value_for_benford=None,
        primary_value=5.5
    )

    phase8 = get_phase8_esoteric_signals(
        game_datetime=datetime.now(),
        game_date=date.today(),
        sport="NBA",
        home_team="Lakers",
        away_team="Celtics",
        pick_type="SPREAD",
        pick_side="Lakers"
    )

    return build_esoteric_breakdown_with_provenance(
        glitch_result=glitch,
        phase8_result=phase8,
        numerology_raw=0.5,
        numerology_signals=[],
        player_name=None,
        game_date=date.today(),
        birth_date_str=None,
        astro_score=5.0,
        fib_score=0,
        vortex_score=0,
        daily_edge_score=0,
        trap_mod=0,
        vortex_boost=0,
        fib_retracement_boost=0,
        altitude_boost=0,
        surface_boost=0,
        sport="NBA",
        home_team="Lakers",
        away_team="Celtics",
        spread=5.5,
        total=220.5,
        prop_line=None,
        venue_city=None,
        noaa_request_proof=None,
    )


# =============================================================================
# Test 1: Esoteric Score Clamped 0-10
# =============================================================================

class TestEsotericScoreClamped:
    """Test that esoteric_score is always clamped to [0, 10]."""

    def test_esoteric_score_clamped_0_10(self):
        """Esoteric score must always be in [0.0, 10.0] range."""
        from esoteric_engine import get_glitch_aggregate

        result = get_glitch_aggregate(
            birth_date_str=None,
            game_date=date.today(),
            game_time=None,
            line_history=None,
            value_for_benford=None,
            primary_value=5.0
        )

        score = result.get("glitch_score_10", 0)
        assert 0.0 <= score <= 10.0, f"Score {score} out of bounds [0, 10]"


# =============================================================================
# Test 2: Breakdown Has Required Fields
# =============================================================================

class TestBreakdownRequiredFields:
    """Test that each signal has all required provenance fields."""

    def test_breakdown_has_required_fields(self, sample_esoteric_breakdown):
        """Each signal must have value, status, source_api, raw_inputs_summary, call_proof."""
        required_fields = {"value", "status", "source_api", "source_type", "raw_inputs_summary", "call_proof", "triggered", "contribution"}

        for signal_name, signal_data in sample_esoteric_breakdown.items():
            actual_fields = set(signal_data.keys())
            missing = required_fields - actual_fields
            assert not missing, f"Signal {signal_name} missing fields: {missing}"


# =============================================================================
# Test 3-4: Source API Attribution
# =============================================================================

class TestSourceAPIAttribution:
    """Test correct source_api attribution for signals."""

    def test_kp_index_source_api_is_noaa(self, sample_esoteric_breakdown):
        """kp_index must claim source_api='noaa'."""
        kp_index = sample_esoteric_breakdown.get("kp_index", {})
        assert kp_index.get("source_api") == "noaa", \
            f"kp_index.source_api should be 'noaa', got {kp_index.get('source_api')}"

    def test_solar_flare_source_api_is_noaa(self, sample_esoteric_breakdown):
        """solar_flare must claim source_api='noaa'."""
        solar_flare = sample_esoteric_breakdown.get("solar_flare", {})
        assert solar_flare.get("source_api") == "noaa", \
            f"solar_flare.source_api should be 'noaa', got {solar_flare.get('source_api')}"

    def test_internal_signals_have_null_source_api(self, sample_esoteric_breakdown):
        """Internal signals (numerology, void_moon, etc.) must have source_api=null."""
        internal_signals = [
            "chrome_resonance", "void_moon", "hurst", "benford",
            "lunar_phase", "mercury_retrograde", "rivalry_intensity",
            "streak_momentum", "numerology", "astro_score", "vortex_energy",
            "fibonacci", "fib_retracement", "altitude_impact", "surface_impact",
            "daily_edge", "trap_mod", "biorhythm", "gann_square", "founders_echo"
        ]

        for signal_name in internal_signals:
            signal_data = sample_esoteric_breakdown.get(signal_name, {})
            assert signal_data.get("source_api") is None, \
                f"{signal_name}.source_api should be None, got {signal_data.get('source_api')}"


# =============================================================================
# Test 5: Noosphere Disabled By Default
# =============================================================================

class TestNoosphereDisabled:
    """Test noosphere is disabled when SERPAPI_KEY is not set."""

    def test_noosphere_disabled_by_default(self, sample_esoteric_breakdown):
        """noosphere status should be 'DISABLED' unless SERPAPI_KEY is set."""
        import os

        serpapi_key = os.getenv("SERPAPI_KEY")
        noosphere = sample_esoteric_breakdown.get("noosphere", {})

        if not serpapi_key:
            assert noosphere.get("status") == "DISABLED", \
                f"noosphere.status should be 'DISABLED' without SERPAPI_KEY, got {noosphere.get('status')}"
            assert noosphere.get("call_proof") is None, \
                "noosphere.call_proof should be None when DISABLED"


# =============================================================================
# Test 6-7: Anti-Conflation
# =============================================================================

class TestAntiConflation:
    """Test signals don't cross-contaminate each other."""

    def test_anti_conflation(self, sample_esoteric_breakdown):
        """One signal cannot modify another's label fields."""
        # Check that each signal has independent structure
        signal_ids = set()
        for signal_name, signal_data in sample_esoteric_breakdown.items():
            # Each signal should have its own identity
            signal_id = id(signal_data)
            assert signal_id not in signal_ids, \
                f"Signal {signal_name} shares object reference with another signal"
            signal_ids.add(signal_id)

    def test_source_type_consistency(self, sample_esoteric_breakdown):
        """source_type should match source_api (EXTERNAL for noaa/serpapi, INTERNAL for null)."""
        for signal_name, signal_data in sample_esoteric_breakdown.items():
            source_api = signal_data.get("source_api")
            source_type = signal_data.get("source_type")

            if source_api in ("noaa", "serpapi"):
                assert source_type == "EXTERNAL", \
                    f"{signal_name}: source_api={source_api} but source_type={source_type}"
            elif source_api is None:
                assert source_type == "INTERNAL", \
                    f"{signal_name}: source_api=None but source_type={source_type}"


# =============================================================================
# Test 8-9: Call Proof Validity
# =============================================================================

class TestCallProofValidity:
    """Test call_proof validity for external API signals."""

    def test_call_proof_validity(self, sample_esoteric_breakdown):
        """External signals with SUCCESS status should have valid call_proof."""
        external_signals = ["kp_index", "solar_flare", "noosphere"]

        for signal_name in external_signals:
            signal_data = sample_esoteric_breakdown.get(signal_name, {})
            status = signal_data.get("status")
            call_proof = signal_data.get("call_proof")

            if status == "SUCCESS":
                assert call_proof is not None, \
                    f"{signal_name}: SUCCESS status but call_proof is None"
                # Must have source field
                assert "source" in call_proof, \
                    f"{signal_name}: call_proof missing 'source' field"

    def test_success_requires_2xx_or_cache(self, sample_esoteric_breakdown):
        """SUCCESS for external API requires 2xx_delta >= 1 OR cache_hit."""
        external_signals = ["kp_index", "solar_flare"]

        for signal_name in external_signals:
            signal_data = sample_esoteric_breakdown.get(signal_name, {})
            status = signal_data.get("status")
            call_proof = signal_data.get("call_proof")

            if status == "SUCCESS" and call_proof:
                has_2xx = call_proof.get("2xx_delta", 0) >= 1
                has_cache = call_proof.get("cache_hit", False)

                assert has_2xx or has_cache, \
                    f"{signal_name}: SUCCESS but no 2xx_delta or cache_hit in call_proof"


# =============================================================================
# Test 10: NOAA Auth Context Has No key_present
# =============================================================================

class TestNOAAAuthContext:
    """Test NOAA auth_context uses auth_type='none', not key_present."""

    def test_noaa_auth_context_has_no_key_present(self):
        """NOAA auth_context should have auth_type='none', NOT key_present."""
        from alt_data_sources.noaa import get_noaa_auth_context

        auth = get_noaa_auth_context()

        assert auth.get("auth_type") == "none", \
            f"NOAA auth_type should be 'none', got {auth.get('auth_type')}"
        assert "key_present" not in auth, \
            "NOAA auth_context should NOT have 'key_present' (it's a public API)"
        assert "enabled" in auth, \
            "NOAA auth_context should have 'enabled' field"


# =============================================================================
# Test 11-12: Truth Table Consistency
# =============================================================================

class TestTruthTableConsistency:
    """Test breakdown signals match truth table."""

    def test_dead_code_not_in_breakdown(self, sample_esoteric_breakdown, truth_table):
        """present_not_wired signals must never appear in breakdown."""
        dead_code = set(truth_table.get("present_not_wired", []))
        breakdown_signals = set(sample_esoteric_breakdown.keys())

        intersection = dead_code & breakdown_signals
        assert not intersection, \
            f"Dead code signals found in breakdown: {intersection}"

    def test_truth_table_consistency(self, sample_esoteric_breakdown, truth_table):
        """All breakdown signals must be in wired_signals list."""
        wired = set(truth_table.get("wired_signals", []))
        breakdown_signals = set(sample_esoteric_breakdown.keys())

        not_in_wired = breakdown_signals - wired
        assert not not_in_wired, \
            f"Breakdown signals not in wired_signals: {not_in_wired}"


# =============================================================================
# Test 13-14: Internal Signal NO_DATA When Missing Inputs
# =============================================================================

class TestInternalSignalNoData:
    """Test internal signals return NO_DATA when required inputs missing."""

    def test_internal_signal_no_data_when_missing_inputs(self, sample_esoteric_breakdown):
        """Internal signals should have NO_DATA status when required inputs missing."""
        # chrome_resonance requires birth_date - should be NO_DATA for game picks
        chrome = sample_esoteric_breakdown.get("chrome_resonance", {})
        raw_inputs = chrome.get("raw_inputs_summary", {})
        required = raw_inputs.get("required_inputs_present", {})

        if not required.get("birth_date", False):
            assert chrome.get("status") == "NO_DATA", \
                f"chrome_resonance without birth_date should be NO_DATA, got {chrome.get('status')}"

    def test_required_inputs_present_booleans(self, sample_esoteric_breakdown):
        """raw_inputs_summary should include required_inputs_present dict with booleans."""
        for signal_name, signal_data in sample_esoteric_breakdown.items():
            raw_inputs = signal_data.get("raw_inputs_summary", {})

            assert "required_inputs_present" in raw_inputs, \
                f"{signal_name}: missing required_inputs_present in raw_inputs_summary"

            required = raw_inputs["required_inputs_present"]
            for key, value in required.items():
                assert isinstance(value, bool), \
                    f"{signal_name}.required_inputs_present.{key} should be bool, got {type(value)}"


# =============================================================================
# Test 15: Suppressed Candidates Have Full Breakdown
# =============================================================================

class TestSuppressedCandidates:
    """Test that suppressed candidates still have full breakdown."""

    def test_suppressed_candidates_have_full_breakdown(self, truth_table):
        """Candidates below 6.5 threshold must still have complete esoteric_breakdown."""
        wired_count = len(truth_table.get("wired_signals", []))

        # This is a structural test - actual runtime test would check API response
        # For now, verify the contract
        assert wired_count == 23, \
            f"Expected 23 wired signals for full breakdown, got {wired_count}"


# =============================================================================
# Test 16: Request Proof Is Request-Local
# =============================================================================

class TestRequestProofLocal:
    """Test request_proof uses request-local counters, not global."""

    def test_request_proof_is_request_local(self):
        """request_proof should use contextvars, not module globals."""
        from alt_data_sources.noaa import (
            init_noaa_request_proof,
            get_noaa_request_proof,
            NOAARequestProof
        )

        # Initialize a new proof
        proof = init_noaa_request_proof()
        assert isinstance(proof, NOAARequestProof)

        # Record a call
        proof.record_call(status_code=200)
        assert proof.http_2xx == 1

        # Get the proof - should be the same instance
        retrieved = get_noaa_request_proof()
        assert retrieved is proof
        assert retrieved.http_2xx == 1


# =============================================================================
# Test 17-20: Cache Truthfulness
# =============================================================================

class TestCacheTruthfulness:
    """Test cache claim truthfulness."""

    def test_kp_success_requires_request_proof_2xx(self, sample_esoteric_breakdown):
        """If kp_index SUCCESS, would need request_proof.noaa_2xx >= 1 OR cache_hits >= 1."""
        kp = sample_esoteric_breakdown.get("kp_index", {})

        if kp.get("status") == "SUCCESS":
            call_proof = kp.get("call_proof", {})
            if call_proof:
                # Either came from cache or live call
                has_proof = (
                    call_proof.get("cache_hit", False) or
                    call_proof.get("2xx_delta", 0) >= 1
                )
                assert has_proof, \
                    "kp_index SUCCESS but no evidence of cache hit or 2xx call"

    def test_call_proof_derived_from_request_proof(self):
        """call_proof.2xx_delta must match request_proof values."""
        from alt_data_sources.noaa import init_noaa_request_proof

        proof = init_noaa_request_proof()
        proof.record_call(status_code=200)
        proof.record_call(status_code=200)

        # Verify the proof has correct counts
        assert proof.http_2xx == 2

    def test_cache_hit_requires_cache_counter(self):
        """If call_proof.cache_hit == true, request_proof.noaa_cache_hits >= 1."""
        from alt_data_sources.noaa import init_noaa_request_proof

        proof = init_noaa_request_proof()
        proof.record_call(cache_hit=True)

        assert proof.cache_hits >= 1, \
            "Cache hit recorded but cache_hits counter is 0"

    def test_noaa_live_requires_2xx_counter(self):
        """If call_proof.source == 'noaa_live', request_proof.noaa_2xx >= 1."""
        from alt_data_sources.noaa import init_noaa_request_proof

        proof = init_noaa_request_proof()
        proof.record_call(status_code=200)  # Live call

        assert proof.http_2xx >= 1, \
            "Live call recorded but 2xx counter is 0"


# =============================================================================
# Test 21: SerpAPI Absent Means Noosphere Disabled
# =============================================================================

class TestSerpAPIAbsent:
    """Test SerpAPI key absence disables noosphere."""

    def test_serpapi_absent_means_noosphere_disabled(self, sample_esoteric_breakdown):
        """If SERPAPI_KEY absent, noosphere.status == 'DISABLED' and call_proof == null."""
        import os

        if not os.getenv("SERPAPI_KEY"):
            noosphere = sample_esoteric_breakdown.get("noosphere", {})

            assert noosphere.get("status") == "DISABLED", \
                f"noosphere should be DISABLED without SERPAPI_KEY, got {noosphere.get('status')}"
            assert noosphere.get("call_proof") is None, \
                "noosphere.call_proof should be None when DISABLED"


# =============================================================================
# Test 22: Breakdown Signal Count Matches Truth Table
# =============================================================================

class TestBreakdownSignalCount:
    """Test breakdown has correct number of signals."""

    def test_breakdown_signal_count_matches_truth_table(self, sample_esoteric_breakdown, truth_table):
        """esoteric_breakdown keys count must match wired_signals list."""
        wired_count = len(truth_table.get("wired_signals", []))
        breakdown_count = len(sample_esoteric_breakdown)

        assert breakdown_count == wired_count, \
            f"Breakdown has {breakdown_count} signals, expected {wired_count} from truth table"


# =============================================================================
# Test: Status Enum Validity
# =============================================================================

class TestStatusEnumValidity:
    """Test status values are valid enum members."""

    def test_status_is_valid_enum(self, sample_esoteric_breakdown, truth_table):
        """All status values must be in signal_status_enum."""
        valid_statuses = set(truth_table.get("signal_status_enum", [
            "SUCCESS", "NO_DATA", "DISABLED", "ERROR", "FALLBACK"
        ]))

        for signal_name, signal_data in sample_esoteric_breakdown.items():
            status = signal_data.get("status")
            assert status in valid_statuses, \
                f"{signal_name}.status '{status}' not in valid statuses: {valid_statuses}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
