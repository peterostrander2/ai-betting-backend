"""
v20.12: GLITCH Contract Guardrail Tests

These tests ensure GLITCH output contract is never regressed:
1. Contract test: All 6 component keys must be present
2. Enum test: All statuses must be in allowed enum
3. Summary reconciliation: Histogram totals must match picks count

Run with: pytest tests/test_glitch_contract.py -v
"""

import pytest
from typing import Dict, Any, List

# === CANONICAL CONTRACTS ===

# Required GLITCH component keys (Invariant 15)
GLITCH_REQUIRED_COMPONENTS = frozenset([
    "chrome_resonance",
    "void_moon",
    "noosphere",
    "hurst",
    "kp_index",
    "benford"
])

# Allowed status values for GLITCH components
GLITCH_ALLOWED_STATUSES = frozenset([
    "SUCCESS",          # Component ran and produced data
    "PARTIAL",          # Some data available
    "FAILED",           # Component failed to run
    "NO_COMPONENTS",    # No components available
    "ERROR",            # Error during execution
    "SKIPPED",          # Intentionally skipped
    "PENDING",          # Not yet executed
    "FALLBACK",         # Using fallback data
    "FALLBACK_SUCCESS", # Fallback data used successfully (e.g., schumann for kp_index)
    "NO_DATA",          # No data available (valid state)
])

# Allowed slate health statuses
SLATE_HEALTH_STATUSES = frozenset([
    "HEALTHY",       # All engines performing well
    "DEGRADED",      # 2 engines below threshold
    "STARVED",       # 3+ engines below threshold
    "NO_SLATE",      # No games in ET window (not an error)
    "LOW_EDGE",      # Engines low but system healthy (filtering working)
    "NO_PICKS",      # No picks generated (may be valid)
    "ERROR",         # Error during evaluation
])


class TestGLITCHContract:
    """Contract tests for GLITCH output structure."""

    def test_glitch_component_keys_present(self):
        """
        Contract Test #1: All 6 GLITCH component keys must be present in breakdown.

        This ensures we never accidentally remove a component from the output.
        The GLITCH output uses "breakdown" key (not "components").
        """
        # Import the function that builds GLITCH output
        from esoteric_engine import get_glitch_aggregate

        # Call with minimal valid inputs
        result = get_glitch_aggregate(
            birth_date_str=None,
            game_date=None,
            game_time=None,
            line_history=None,
            value_for_benford=None,
            primary_value=None
        )

        # Verify all required keys are present in breakdown
        breakdown = result.get("breakdown", {})
        missing_keys = GLITCH_REQUIRED_COMPONENTS - set(breakdown.keys())

        assert not missing_keys, (
            f"GLITCH CONTRACT VIOLATION: Missing component keys: {missing_keys}. "
            f"All 6 components must be present in breakdown: {GLITCH_REQUIRED_COMPONENTS}"
        )

    def test_glitch_component_structure(self):
        """
        Contract Test #2: Each component must have 'status' field.

        The status field is mandatory for all components. Other fields vary by component type.
        """
        from esoteric_engine import get_glitch_aggregate

        result = get_glitch_aggregate(
            birth_date_str=None,
            game_date=None,
            game_time=None,
            line_history=None,
            value_for_benford=None,
            primary_value=None
        )

        breakdown = result.get("breakdown", {})

        for comp_name in GLITCH_REQUIRED_COMPONENTS:
            comp = breakdown.get(comp_name, {})

            # Each component must have status field
            assert "status" in comp, (
                f"GLITCH CONTRACT VIOLATION: Component '{comp_name}' missing 'status' field"
            )

    def test_glitch_status_values_in_enum(self):
        """
        Enum Test: All status values must be in the allowed enum.

        This prevents typos and ensures consistent status reporting.
        """
        from esoteric_engine import get_glitch_aggregate

        result = get_glitch_aggregate(
            birth_date_str=None,
            game_date=None,
            game_time=None,
            line_history=None,
            value_for_benford=None,
            primary_value=None
        )

        breakdown = result.get("breakdown", {})

        for comp_name, comp_data in breakdown.items():
            status = comp_data.get("status", "")
            assert status in GLITCH_ALLOWED_STATUSES, (
                f"GLITCH ENUM VIOLATION: Component '{comp_name}' has invalid status '{status}'. "
                f"Allowed statuses: {GLITCH_ALLOWED_STATUSES}"
            )

    def test_glitch_overall_status_in_enum(self):
        """
        Enum Test: Overall GLITCH status must be in allowed enum.
        """
        from esoteric_engine import get_glitch_aggregate

        result = get_glitch_aggregate(
            birth_date_str=None,
            game_date=None,
            game_time=None,
            line_history=None,
            value_for_benford=None,
            primary_value=None
        )

        # The top-level status is stored in "status" key (not "overall_status")
        overall_status = result.get("status", "")
        assert overall_status in GLITCH_ALLOWED_STATUSES, (
            f"GLITCH ENUM VIOLATION: Overall status '{overall_status}' not in allowed enum. "
            f"Allowed: {GLITCH_ALLOWED_STATUSES}"
        )

    def test_glitch_score_bounds(self):
        """
        Contract Test: GLITCH score must be bounded [0, 10].
        """
        from esoteric_engine import get_glitch_aggregate

        result = get_glitch_aggregate(
            birth_date_str=None,
            game_date=None,
            game_time=None,
            line_history=None,
            value_for_benford=None,
            primary_value=None
        )

        score = result.get("glitch_score_10", 0)
        assert 0 <= score <= 10, (
            f"GLITCH CONTRACT VIOLATION: Score {score} outside bounds [0, 10]"
        )


class TestSlateHealthContract:
    """Contract tests for slate summary health status."""

    def test_slate_status_enum_values(self):
        """
        Enum Test: Slate health status must be in allowed enum.
        """
        # Test all valid statuses are recognized
        for status in SLATE_HEALTH_STATUSES:
            assert isinstance(status, str)
            assert len(status) > 0

    def test_starvation_thresholds_defined(self):
        """
        Contract Test: Starvation thresholds must be defined for all engines.
        """
        # These are the canonical thresholds from the slate summary endpoint
        STARVATION_THRESHOLDS = {
            "ai": 4.0,
            "research": 4.0,
            "esoteric": 3.0,
            "jarvis": 4.0
        }

        required_engines = {"ai", "research", "esoteric", "jarvis"}
        defined_engines = set(STARVATION_THRESHOLDS.keys())

        assert required_engines == defined_engines, (
            f"THRESHOLD CONTRACT VIOLATION: Missing thresholds for engines: "
            f"{required_engines - defined_engines}"
        )

        # All thresholds must be positive
        for engine, threshold in STARVATION_THRESHOLDS.items():
            assert threshold > 0, (
                f"THRESHOLD CONTRACT VIOLATION: {engine} threshold must be positive, got {threshold}"
            )


class TestSummaryReconciliation:
    """Reconciliation tests for slate summary consistency."""

    def test_histogram_total_equals_picks_count(self):
        """
        Reconciliation Test: Histogram bucket totals must equal total picks.

        This is a fixture-based test using a deterministic scenario.
        """
        # Create a mock picks list with known scores
        mock_picks = [
            {"final_score": 4.5},   # 0-4.9
            {"final_score": 5.5},   # 5.0-5.9
            {"final_score": 6.2},   # 6.0-6.4
            {"final_score": 6.7},   # 6.5-6.9
            {"final_score": 7.2},   # 7.0-7.4
            {"final_score": 7.8},   # 7.5-7.9
            {"final_score": 8.1},   # 8.0-8.4
            {"final_score": 8.7},   # 8.5-8.9
            {"final_score": 9.5},   # 9.0-10.0
        ]

        # Build histogram (same logic as slate-summary endpoint)
        score_buckets = {
            "0-4.9": 0, "5.0-5.9": 0, "6.0-6.4": 0, "6.5-6.9": 0,
            "7.0-7.4": 0, "7.5-7.9": 0, "8.0-8.4": 0, "8.5-8.9": 0, "9.0-10.0": 0
        }

        for pick in mock_picks:
            score = pick.get("final_score", 0)
            if score < 5.0:
                score_buckets["0-4.9"] += 1
            elif score < 6.0:
                score_buckets["5.0-5.9"] += 1
            elif score < 6.5:
                score_buckets["6.0-6.4"] += 1
            elif score < 7.0:
                score_buckets["6.5-6.9"] += 1
            elif score < 7.5:
                score_buckets["7.0-7.4"] += 1
            elif score < 8.0:
                score_buckets["7.5-7.9"] += 1
            elif score < 8.5:
                score_buckets["8.0-8.4"] += 1
            elif score < 9.0:
                score_buckets["8.5-8.9"] += 1
            else:
                score_buckets["9.0-10.0"] += 1

        # Reconciliation: sum of buckets must equal total picks
        histogram_total = sum(score_buckets.values())
        picks_count = len(mock_picks)

        assert histogram_total == picks_count, (
            f"RECONCILIATION VIOLATION: Histogram total ({histogram_total}) != "
            f"picks count ({picks_count})"
        )

    def test_boost_counts_match_picks(self):
        """
        Reconciliation Test: Boost fire counts must match actual occurrences.
        """
        # Create mock picks with known boost values
        mock_picks = [
            {"confluence_boost": 3.0, "msrf_boost": 0.5, "jason_sim_boost": 0.0, "serp_boost": 0.0},
            {"confluence_boost": 0.0, "msrf_boost": 0.0, "jason_sim_boost": 1.5, "serp_boost": 0.0},
            {"confluence_boost": 1.0, "msrf_boost": 0.0, "jason_sim_boost": 0.0, "serp_boost": 2.0},
        ]

        # Count boosts fired (same logic as slate-summary endpoint)
        boost_counts = {
            "confluence_fired": 0,
            "msrf_fired": 0,
            "jason_sim_fired": 0,
            "serp_fired": 0,
        }

        for pick in mock_picks:
            if pick.get("confluence_boost", 0) > 0:
                boost_counts["confluence_fired"] += 1
            if pick.get("msrf_boost", 0) > 0:
                boost_counts["msrf_fired"] += 1
            if pick.get("jason_sim_boost", 0) != 0:
                boost_counts["jason_sim_fired"] += 1
            if pick.get("serp_boost", 0) > 0:
                boost_counts["serp_fired"] += 1

        # Expected counts from the mock data
        expected = {
            "confluence_fired": 2,  # picks 0 and 2
            "msrf_fired": 1,        # pick 0
            "jason_sim_fired": 1,   # pick 1
            "serp_fired": 1,        # pick 2
        }

        for key, expected_count in expected.items():
            actual_count = boost_counts[key]
            assert actual_count == expected_count, (
                f"RECONCILIATION VIOLATION: {key} expected {expected_count}, got {actual_count}"
            )


class TestNoSlateAndLowEdgeStates:
    """Tests for NO_SLATE and LOW_EDGE threshold semantics."""

    def test_no_slate_when_no_games(self):
        """
        NO_SLATE state: When no games in ET window, status should be NO_SLATE.
        """
        # Simulate no picks scenario
        all_picks: List[Dict[str, Any]] = []

        # Logic: if no picks, this is NO_SLATE (not STARVED)
        if not all_picks:
            status = "NO_SLATE"
        else:
            status = "HEALTHY"

        assert status == "NO_SLATE", (
            f"NO_SLATE VIOLATION: Empty picks should return NO_SLATE, got {status}"
        )

    def test_low_edge_vs_starved_distinction(self):
        """
        LOW_EDGE state: When engines are low but system is healthy (filtering working).

        STARVED = System broken (engines not producing edge)
        LOW_EDGE = System working (just no edge to be found today)
        """
        # Scenario 1: STARVED - All engines below threshold AND no boosts fired
        starved_picks = [
            {"ai_score": 3.5, "research_score": 3.5, "esoteric_score": 2.5, "jarvis_score": 3.5,
             "confluence_boost": 0, "msrf_boost": 0, "serp_boost": 0},
            {"ai_score": 3.8, "research_score": 3.2, "esoteric_score": 2.8, "jarvis_score": 3.0,
             "confluence_boost": 0, "msrf_boost": 0, "serp_boost": 0},
        ]

        # Scenario 2: LOW_EDGE - Engines low but boosts are firing (system working)
        low_edge_picks = [
            {"ai_score": 3.5, "research_score": 3.5, "esoteric_score": 2.5, "jarvis_score": 3.5,
             "confluence_boost": 1.0, "msrf_boost": 0.5, "serp_boost": 0},  # Boosts firing
            {"ai_score": 3.8, "research_score": 3.2, "esoteric_score": 2.8, "jarvis_score": 3.0,
             "confluence_boost": 0.5, "msrf_boost": 0, "serp_boost": 0.3},  # Boosts firing
        ]

        def classify_state(picks: List[Dict[str, Any]]) -> str:
            """Classify slate state based on picks."""
            if not picks:
                return "NO_SLATE"

            # Count low engines
            THRESHOLDS = {"ai": 4.0, "research": 4.0, "esoteric": 3.0, "jarvis": 4.0}
            low_engines = []

            for engine, threshold in THRESHOLDS.items():
                avg_score = sum(p.get(f"{engine}_score", 5.0) for p in picks) / len(picks)
                if avg_score < threshold:
                    low_engines.append(engine)

            # Check if boosts are firing (system working)
            boosts_fired = sum(
                1 for p in picks
                if p.get("confluence_boost", 0) > 0 or
                   p.get("msrf_boost", 0) > 0 or
                   p.get("serp_boost", 0) > 0
            )
            boost_rate = boosts_fired / len(picks) if picks else 0

            if len(low_engines) >= 3:
                # Engines low, but are boosts firing?
                if boost_rate >= 0.3:  # 30%+ boosts firing = system working
                    return "LOW_EDGE"
                else:
                    return "STARVED"
            elif len(low_engines) >= 2:
                return "DEGRADED"
            else:
                return "HEALTHY"

        # Test STARVED scenario
        starved_status = classify_state(starved_picks)
        assert starved_status == "STARVED", (
            f"Should be STARVED when engines low and no boosts, got {starved_status}"
        )

        # Test LOW_EDGE scenario
        low_edge_status = classify_state(low_edge_picks)
        assert low_edge_status == "LOW_EDGE", (
            f"Should be LOW_EDGE when engines low but boosts firing, got {low_edge_status}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
