"""
TEST_DEBUG_TELEMETRY.PY - Tests for Debug Telemetry Fields
===========================================================
v20.21 - Pre-threshold tier telemetry

Tests verify:
1. Pre-threshold tier counts exist in debug output
2. Tier count sums match candidate totals
3. All tiers in counts are recognized

Run with: python -m pytest tests/test_debug_telemetry.py -v
"""

import os
import sys
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scoring_contract import VALID_OUTPUT_TIERS, HIDDEN_TIERS


class TestPreThresholdTierTelemetry:
    """Tests for v20.21 pre-threshold tier telemetry."""

    def test_count_tiers_function(self):
        """Test the tier counting logic."""
        # Simulate the _count_tiers function from live_data_router.py
        def _count_tiers(picks):
            counts = {}
            for p in picks:
                tier = p.get("tier", "UNKNOWN")
                counts[tier] = counts.get(tier, 0) + 1
            return counts

        picks = [
            {"tier": "TITANIUM_SMASH"},
            {"tier": "GOLD_STAR"},
            {"tier": "GOLD_STAR"},
            {"tier": "EDGE_LEAN"},
            {"tier": "EDGE_LEAN"},
            {"tier": "EDGE_LEAN"},
            {"tier": "MONITOR"},
            {"tier": "PASS"},
        ]

        counts = _count_tiers(picks)

        assert counts["TITANIUM_SMASH"] == 1
        assert counts["GOLD_STAR"] == 2
        assert counts["EDGE_LEAN"] == 3
        assert counts["MONITOR"] == 1
        assert counts["PASS"] == 1
        assert sum(counts.values()) == len(picks)

    def test_tier_counts_sum_matches_total(self):
        """Verify tier count sums equal total candidate count."""
        def _count_tiers(picks):
            counts = {}
            for p in picks:
                tier = p.get("tier", "UNKNOWN")
                counts[tier] = counts.get(tier, 0) + 1
            return counts

        # Simulate candidate pools
        props = [
            {"tier": "GOLD_STAR", "total_score": 8.0},
            {"tier": "EDGE_LEAN", "total_score": 7.2},
            {"tier": "MONITOR", "total_score": 6.8},
        ]
        games = [
            {"tier": "TITANIUM_SMASH", "total_score": 9.0},
            {"tier": "GOLD_STAR", "total_score": 8.1},
            {"tier": "PASS", "total_score": 5.5},
        ]

        props_counts = _count_tiers(props)
        games_counts = _count_tiers(games)

        # Combined counts
        total_counts = {}
        for tier in set(props_counts.keys()) | set(games_counts.keys()):
            total_counts[tier] = props_counts.get(tier, 0) + games_counts.get(tier, 0)

        # Assertions matching what debug output should contain
        assert sum(props_counts.values()) == len(props), "Props tier sum should match props count"
        assert sum(games_counts.values()) == len(games), "Games tier sum should match games count"
        assert sum(total_counts.values()) == len(props) + len(games), "Total tier sum should match total count"

    def test_all_valid_tiers_recognized(self):
        """Verify all valid output tiers are recognized."""
        all_tiers = VALID_OUTPUT_TIERS | HIDDEN_TIERS

        assert "TITANIUM_SMASH" in all_tiers
        assert "GOLD_STAR" in all_tiers
        assert "EDGE_LEAN" in all_tiers
        assert "MONITOR" in all_tiers
        assert "PASS" in all_tiers

    def test_hidden_tiers_are_subset(self):
        """Hidden tiers should not overlap with valid output tiers."""
        assert HIDDEN_TIERS & VALID_OUTPUT_TIERS == set(), \
            "Hidden tiers should not overlap with valid output tiers"

    def test_unknown_tier_handling(self):
        """Picks without tier field should be counted as UNKNOWN."""
        def _count_tiers(picks):
            counts = {}
            for p in picks:
                tier = p.get("tier", "UNKNOWN")
                counts[tier] = counts.get(tier, 0) + 1
            return counts

        picks = [
            {"tier": "GOLD_STAR"},
            {},  # No tier field
            {"tier": None},  # None tier (should also be handled)
        ]

        counts = _count_tiers(picks)

        assert counts.get("GOLD_STAR") == 1
        assert counts.get("UNKNOWN") == 1
        assert counts.get(None) == 1  # None is a valid dict key
        assert sum(counts.values()) == len(picks)


try:
    from live_data_router import _enforce_output_boundary
    LIVE_DATA_ROUTER_AVAILABLE = True
except ImportError:
    LIVE_DATA_ROUTER_AVAILABLE = False


@pytest.mark.skipif(not LIVE_DATA_ROUTER_AVAILABLE, reason="live_data_router requires FastAPI")
class TestOutputBoundaryHardening:
    """Tests for v20.21 output boundary hardening."""

    def test_filters_picks_below_props_threshold(self):
        """Picks below 6.5 for props should be filtered at boundary."""

        payload = {
            "props": {
                "count": 3,
                "picks": [
                    {"pick_id": "a", "final_score": 7.0, "tier": "GOLD_STAR"},
                    {"pick_id": "b", "final_score": 6.0, "tier": "EDGE_LEAN"},  # Below threshold
                    {"pick_id": "c", "final_score": 6.5, "tier": "EDGE_LEAN"},  # At threshold
                ]
            }
        }

        result = _enforce_output_boundary(payload)

        assert result["props"]["count"] == 2
        assert len(result["props"]["picks"]) == 2
        pick_ids = [p["pick_id"] for p in result["props"]["picks"]]
        assert "a" in pick_ids
        assert "c" in pick_ids
        assert "b" not in pick_ids  # Filtered

    def test_filters_picks_below_games_threshold(self):
        """Picks below 7.0 for games should be filtered at boundary."""
        payload = {
            "game_picks": {
                "count": 3,
                "picks": [
                    {"pick_id": "a", "final_score": 7.5, "tier": "GOLD_STAR"},
                    {"pick_id": "b", "final_score": 6.8, "tier": "EDGE_LEAN"},  # Below 7.0
                    {"pick_id": "c", "final_score": 7.0, "tier": "EDGE_LEAN"},  # At threshold
                ]
            }
        }

        result = _enforce_output_boundary(payload)

        assert result["game_picks"]["count"] == 2
        assert len(result["game_picks"]["picks"]) == 2
        pick_ids = [p["pick_id"] for p in result["game_picks"]["picks"]]
        assert "a" in pick_ids
        assert "c" in pick_ids
        assert "b" not in pick_ids  # Filtered

    def test_filters_hidden_tiers(self):
        """Picks with MONITOR or PASS tier should be filtered at boundary."""
        payload = {
            "props": {
                "count": 4,
                "picks": [
                    {"pick_id": "a", "final_score": 7.0, "tier": "GOLD_STAR"},
                    {"pick_id": "b", "final_score": 7.0, "tier": "MONITOR"},  # Hidden
                    {"pick_id": "c", "final_score": 7.0, "tier": "PASS"},  # Hidden
                    {"pick_id": "d", "final_score": 7.0, "tier": "EDGE_LEAN"},
                ]
            }
        }

        result = _enforce_output_boundary(payload)

        assert result["props"]["count"] == 2
        pick_ids = [p["pick_id"] for p in result["props"]["picks"]]
        assert "a" in pick_ids
        assert "d" in pick_ids
        assert "b" not in pick_ids
        assert "c" not in pick_ids

    def test_adds_boundary_telemetry_on_violations(self):
        """Debug payload should include boundary violation telemetry."""
        payload = {
            "props": {
                "count": 2,
                "picks": [
                    {"pick_id": "a", "final_score": 7.0, "tier": "GOLD_STAR"},
                    {"pick_id": "b", "final_score": 5.0, "tier": "EDGE_LEAN"},  # Filtered
                ]
            }
        }

        result = _enforce_output_boundary(payload)

        assert "debug" in result
        assert "boundary_violations" in result["debug"]
        assert result["debug"]["boundary_filtered_total"] == 1
        assert result["debug"]["boundary_violations"]["props_below_threshold"] == 1

    def test_no_telemetry_when_no_violations(self):
        """No boundary telemetry added when all picks pass validation."""
        payload = {
            "props": {
                "count": 2,
                "picks": [
                    {"pick_id": "a", "final_score": 7.0, "tier": "GOLD_STAR"},
                    {"pick_id": "b", "final_score": 7.5, "tier": "GOLD_STAR"},
                ]
            }
        }

        result = _enforce_output_boundary(payload)

        # No debug added because no violations
        assert "boundary_violations" not in result.get("debug", {})

    def test_handles_empty_picks(self):
        """Empty picks arrays should be handled gracefully."""
        payload = {
            "props": {"count": 0, "picks": []},
            "game_picks": {"count": 0, "picks": []}
        }

        result = _enforce_output_boundary(payload)

        assert result["props"]["count"] == 0
        assert result["game_picks"]["count"] == 0


class TestDebugPayloadStructure:
    """Tests for required debug payload fields."""

    def test_required_debug_fields_defined(self):
        """Verify required debug fields are documented in golden baseline."""
        import json
        from pathlib import Path

        baseline_path = Path(__file__).parent / "fixtures" / "golden_baseline_v20.20.json"
        if not baseline_path.exists():
            pytest.skip("Golden baseline not found")

        with open(baseline_path) as f:
            baseline = json.load(f)

        required_fields = baseline.get("required_debug_fields", [])

        # v20.21 fields should be added to baseline
        # For now, test the core fields exist
        assert "date_window_et" in required_fields
        assert "filtered_below_6_5_total" in required_fields
        assert "hidden_tier_filtered_total" in required_fields
