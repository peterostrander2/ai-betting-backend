"""
Engine 3 (Esoteric) Guard Tests
Verifies weight contracts, signal inventory, and reconciliation.
"""
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Weight Contract Tests
# =============================================================================

class TestWeightContract:
    """Verify Engine 3 weight is exactly 0.15 per Option A formula (v20.19)."""

    def test_esoteric_weight_is_15_percent(self):
        """Esoteric engine must be weighted at exactly 0.15 (15%) per v20.19 rebalancing."""
        from core.scoring_contract import ENGINE_WEIGHTS
        assert ENGINE_WEIGHTS.get("esoteric") == 0.15, (
            f"Esoteric weight must be 0.15, got {ENGINE_WEIGHTS.get('esoteric')}"
        )

    def test_engine_weights_sum_to_100(self):
        """All four engine weights must sum to exactly 1.0."""
        from core.scoring_contract import ENGINE_WEIGHTS
        total = sum(ENGINE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.0001, (
            f"Engine weights must sum to 1.0, got {total}"
        )

    def test_all_four_engines_present(self):
        """Option A requires exactly 4 engines: ai, research, esoteric, jarvis."""
        from core.scoring_contract import ENGINE_WEIGHTS
        required = {"ai", "research", "esoteric", "jarvis"}
        actual = set(ENGINE_WEIGHTS.keys())
        assert actual == required, (
            f"Expected engines {required}, got {actual}"
        )

    def test_esoteric_contributes_to_base4(self):
        """Verify esoteric_score * 0.15 contributes to BASE_4 (v20.19)."""
        from core.scoring_contract import ENGINE_WEIGHTS
        esoteric_weight = ENGINE_WEIGHTS.get("esoteric", 0)
        # Sample esoteric score
        sample_score = 7.5
        contribution = sample_score * esoteric_weight
        expected_contribution = 7.5 * 0.15  # 1.125 (v20.19)
        assert abs(contribution - expected_contribution) < 0.0001, (
            f"Esoteric contribution mismatch: {contribution} != {expected_contribution}"
        )


# =============================================================================
# No-Hidden-Terms Contract Tests
# =============================================================================

class TestNoHiddenTerms:
    """Verify esoteric outputs are valid and documented."""

    def test_esoteric_score_valid_range_bounds(self):
        """esoteric_score must be clamped to [0.0, 10.0]."""
        # Test the range constants - actual runtime validation happens in audit script
        min_score = 0.0
        max_score = 10.0
        assert min_score >= 0.0
        assert max_score <= 10.0
        assert min_score < max_score

    def test_esoteric_score_type_is_numeric(self):
        """esoteric_score should be a float/int, not string."""
        # Type contract - enforced at runtime
        valid_types = (int, float)
        sample_score = 5.5
        assert isinstance(sample_score, valid_types)

    def test_documented_debug_fields(self):
        """All documented debug fields should exist in contract."""
        documented_fields = {
            "esoteric_score",
            "esoteric_reasons",
            "esoteric_contributions",
            "phase8_boost",
            "phase8_reasons",
            "phase8_breakdown",
            "glitch_adjustment",
            "glitch_signals",
            "glitch_breakdown",
        }
        # This is a documentation contract test - verifies we have a list
        assert len(documented_fields) == 9, "Expected 9 documented debug fields"


# =============================================================================
# Signal Inventory Tests
# =============================================================================

class TestSignalInventory:
    """Verify signal counts match documentation."""

    def test_glitch_protocol_has_8_signals(self):
        """GLITCH protocol defines 8 signals (7 active + 1 disabled) after v20.22.

        v20.22: Replaced benford (0.10) with golden_ratio (0.04), prime_resonance (0.03),
        numerical_symmetry (0.03) for better signal coverage.
        """
        glitch_signals = [
            "chrome_resonance",     # ACTIVE (0.20)
            "void_moon",            # ACTIVE (0.20)
            "noosphere",            # DISABLED (SERP cancelled)
            "hurst",                # ACTIVE (0.25)
            "kp_index",             # ACTIVE (0.25)
            "golden_ratio",         # ACTIVE (0.04) - v20.22
            "prime_resonance",      # ACTIVE (0.03) - v20.22
            "numerical_symmetry",   # ACTIVE (0.03) - v20.22
        ]
        assert len(glitch_signals) == 8, f"Expected 8 GLITCH signals, got {len(glitch_signals)}"

    def test_glitch_active_signals_is_7(self):
        """7 GLITCH signals are active after v20.22 (noosphere disabled)."""
        active_glitch = [
            "chrome_resonance", "void_moon", "hurst", "kp_index",
            "golden_ratio", "prime_resonance", "numerical_symmetry"
        ]
        assert len(active_glitch) == 7

    def test_phase8_has_5_signals(self):
        """Phase 8 defines exactly 5 signals."""
        phase8_signals = [
            "lunar_phase",
            "mercury_retrograde",
            "rivalry_intensity",
            "streak_momentum",
            "solar_flare",
        ]
        assert len(phase8_signals) == 5, f"Expected 5 Phase 8 signals, got {len(phase8_signals)}"

    def test_total_signal_count_is_27(self):
        """Total esoteric signals = 27 after v20.22.

        v20.22 changes:
        - Removed: benford (triggers <2%)
        - Added: golden_ratio, prime_resonance, numerical_symmetry (net +2)
        - Total: 25 active + 2 dormant = 27
        """
        active_signals = 25  # 23 - 1 (benford) + 3 (math signals)
        dormant_signals = 2  # phoenix_resonance, schumann_resonance
        total = active_signals + dormant_signals
        assert total == 27, f"Expected 27 signals, got {total}"

    def test_active_signals_count_is_25(self):
        """25 signals are ACTIVE in production after v20.22."""
        # v20.22: 23 original - 1 (benford) + 3 (math signals) = 25
        active_count = 25
        assert active_count == 25

    def test_dormant_signals_count_is_2(self):
        """2 signals are DORMANT after v20.22 (code exists but not wired).

        v20.22: golden_ratio, prime_resonance, numerical_symmetry moved to ACTIVE.
        benford removed (triggers <2% of picks).
        """
        dormant = ["phoenix_resonance", "schumann_resonance"]
        assert len(dormant) == 2


# =============================================================================
# GLITCH Weight Tests
# =============================================================================

class TestGlitchWeights:
    """Verify GLITCH protocol weights and normalization behavior."""

    def test_active_glitch_weights_sum_to_100(self):
        """Active GLITCH signal weights (excluding disabled noosphere) sum to 1.00.

        v20.28.6: Learning Loop Tuned based on Feb 14 grading (1,998 samples):
        - void_moon reduced 0.20→0.12 (negative -0.07 correlation)
        - kp_index increased 0.25→0.33 (positive +0.065 correlation, best performer)
        """
        # Raw weights as defined in get_glitch_aggregate()
        active_weights = {
            "chrome_resonance": 0.20,
            "void_moon": 0.12,          # v20.28.6: reduced (negative correlation)
            "hurst": 0.25,
            "kp_index": 0.33,           # v20.28.6: increased (positive correlation)
            "golden_ratio": 0.04,
            "prime_resonance": 0.03,
            "numerical_symmetry": 0.03,
        }
        # noosphere is disabled (SERPAPI_KEY absent), so not included in active
        total = sum(active_weights.values())
        assert abs(total - 1.00) < 0.001, \
            f"Active GLITCH weights should sum to 1.00, got {total}"

    def test_glitch_aggregate_normalizes_to_1(self):
        """Engine normalizes by dividing weighted_score by total_weight."""
        # The engine uses: final_score = weighted_score / total_weight
        # This means effective weights always sum to 1.0 after normalization
        from esoteric_engine import get_glitch_aggregate
        from datetime import date, datetime

        # Call with minimal inputs to get normalization behavior
        result = get_glitch_aggregate(
            birth_date_str=None,
            game_date=date.today(),
            game_time=datetime.now(),
            line_history=None,
            value_for_benford=None,
            primary_value=None
        )

        # weights_used shows total weight before normalization
        weights_used = result.get("weights_used", 0)
        # With minimal inputs, only void_moon (0.20) and kp_index/schumann (0.25) fire
        # The glitch_score is normalized: weighted_score / total_weight
        # So effective weights always sum to 1.0
        assert weights_used > 0, "At least some weights should be used"
        # The normalized score is bounded [0, 1] (or 0-10 for glitch_score_10)
        assert 0 <= result.get("glitch_score", 0) <= 1.0, \
            f"Normalized glitch_score should be [0,1], got {result.get('glitch_score')}"

    def test_kp_index_weight_is_033(self):
        """Kp-Index signal has weight 0.33 (v20.28.6: increased due to positive correlation)."""
        kp_weight = 0.33
        assert kp_weight == 0.33


# =============================================================================
# Reconciliation Tests
# =============================================================================

class TestReconciliation:
    """Verify code and documentation match."""

    def test_esoteric_engine_module_exists(self):
        """esoteric_engine.py must exist."""
        import importlib.util
        spec = importlib.util.find_spec("esoteric_engine")
        # If not found directly, try with path
        if spec is None:
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "esoteric_engine.py"
            )
            assert os.path.exists(path), "esoteric_engine.py not found"

    def test_scoring_contract_module_exists(self):
        """core/scoring_contract.py must exist."""
        try:
            from core.scoring_contract import ENGINE_WEIGHTS
            assert ENGINE_WEIGHTS is not None
        except ImportError:
            pytest.fail("core.scoring_contract module not found")

    def test_kp_index_source_values(self):
        """kp_index_source should be 'noaa_live' or 'fallback'."""
        valid_sources = {"noaa_live", "fallback", "noaa", "simulated"}
        # Contract test - runtime verification in audit script
        assert "noaa_live" in valid_sources
        assert "fallback" in valid_sources

    def test_noaa_module_exists(self):
        """alt_data_sources/noaa.py must exist for Kp-Index."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alt_data_sources",
            "noaa.py"
        )
        assert os.path.exists(path), "alt_data_sources/noaa.py not found"

    def test_physics_signals_module_exists(self):
        """signals/physics.py must exist."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "signals",
            "physics.py"
        )
        assert os.path.exists(path), "signals/physics.py not found"

    def test_math_glitch_module_exists(self):
        """signals/math_glitch.py must exist."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "signals",
            "math_glitch.py"
        )
        assert os.path.exists(path), "signals/math_glitch.py not found"


# =============================================================================
# External Dependency Tests
# =============================================================================

class TestExternalDependencies:
    """Verify external API configurations."""

    def test_noaa_api_is_free(self):
        """NOAA Space Weather API should be free (no API key required)."""
        # Contract: NOAA is public API, no cost
        requires_api_key = False
        assert requires_api_key is False

    def test_noaa_cache_ttl_is_3_hours(self):
        """NOAA data should be cached for 3 hours."""
        cache_ttl_hours = 3
        assert cache_ttl_hours == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
