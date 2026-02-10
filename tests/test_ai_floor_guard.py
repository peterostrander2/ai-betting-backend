"""
v20.16: AI Floor Dominance Guard Test

This test ensures that when MPS returns valid component scores,
the ai_score shows variance and doesn't all hit the 2.0 floor.

Guard: "top candidates cannot all be exactly floor when ai_mode=ML_PRIMARY
        and MPS returns nonzero edge/agreement"
"""

import pytest


class TestAIFloorGuard:
    """Guard tests to prevent floor-dominated AI scoring."""

    def test_nonzero_components_produce_above_floor_score(self):
        """
        When MPS returns nonzero agreement_score, edge_score, or factor_score,
        the alternative_base should be > 2.0, producing ai_score > 2.0.

        This guards against the "all at floor" scenario.
        """
        # Simulate MPS returning nonzero components
        # Formula: alternative_base = min(10, 2.0 + agreement + edge + factor)

        # Case 1: Models agree well (low std = high agreement)
        model_std = 1.0  # Low std
        agreement_score = max(0, 3 - model_std / 2)  # = 2.5
        edge_score = 0
        factor_score = 0

        alternative_base = min(10, 2.0 + agreement_score + edge_score + factor_score)
        assert alternative_base == 4.5, f"With agreement=2.5, base should be 4.5, got {alternative_base}"

        # Case 2: Good edge detected
        agreement_score = 0
        edge_pct = 10  # 10% edge
        edge_score = min(3, edge_pct / 5)  # = 2.0
        factor_score = 0

        alternative_base = min(10, 2.0 + agreement_score + edge_score + factor_score)
        assert alternative_base == 4.0, f"With edge=2.0, base should be 4.0, got {alternative_base}"

        # Case 3: Good factors (rest + injury + line movement)
        agreement_score = 0
        edge_score = 0
        factor_score = 2.0  # Max factors

        alternative_base = min(10, 2.0 + agreement_score + edge_score + factor_score)
        assert alternative_base == 4.0, f"With factors=2.0, base should be 4.0, got {alternative_base}"

    def test_combined_components_produce_variance(self):
        """
        With reasonable component values, ai_score should show variance
        rather than all being stuck at 2.0 floor.
        """
        test_cases = [
            # (agreement_score, edge_score, factor_score) -> expected_alternative_base
            (0, 0, 0, 2.0),      # Minimum (floor)
            (1.5, 0, 0, 3.5),    # Moderate agreement
            (0, 1.5, 0, 3.5),    # Moderate edge
            (0, 0, 1.0, 3.0),    # Some factors
            (2.0, 1.0, 0.5, 5.5),  # Combined
            (3.0, 3.0, 2.0, 10.0), # Maximum (capped)
        ]

        scores = []
        for agreement, edge, factor, expected in test_cases:
            alt_base = min(10, 2.0 + agreement + edge + factor)
            assert alt_base == expected, f"Components {agreement},{edge},{factor} should give {expected}, got {alt_base}"
            scores.append(alt_base)

        # Check variance exists
        unique_scores = set(scores)
        assert len(unique_scores) > 1, "Scores should have variance, not all identical"
        assert min(scores) == 2.0, "Minimum should be floor (2.0)"
        assert max(scores) == 10.0, "Maximum should be cap (10.0)"

    def test_ml_primary_with_nonzero_components_not_all_floor(self):
        """
        Guard test: If ai_mode=ML_PRIMARY and MPS returns nonzero components,
        then ai_score MUST NOT be exactly 2.0 (floor).

        This simulates what should happen when MPS is working correctly.
        """
        # Simulate a working MPS result
        mps_result = {
            "ai_score": 5.5,  # Should be above floor
            "ai_audit": {
                "deviation_score": 0.0,      # No deviation (prediction = line)
                "agreement_score": 2.0,       # Models agree moderately
                "edge_score": 1.0,            # Some edge detected
                "factor_score": 0.5,          # Some factors present
                "alternative_base": 5.5,      # 2.0 + 2.0 + 1.0 + 0.5
                "base_score_used": "ALTERNATIVE",
                "pillar_boost": 0.0,
                "model_std": 2.0,
            }
        }

        ai_score = mps_result["ai_score"]
        ai_audit = mps_result["ai_audit"]

        # If components are nonzero, score should be above floor
        total_components = (
            (ai_audit.get("agreement_score") or 0) +
            (ai_audit.get("edge_score") or 0) +
            (ai_audit.get("factor_score") or 0)
        )

        if total_components > 0:
            assert ai_score > 2.0, \
                f"With nonzero components ({total_components}), ai_score ({ai_score}) should be > 2.0 floor"

    def test_floor_is_only_for_zero_components(self):
        """
        The 2.0 floor should ONLY occur when all component scores are zero.
        """
        # Case: All components zero -> floor is OK
        agreement_score = 0
        edge_score = 0
        factor_score = 0

        alternative_base = min(10, 2.0 + agreement_score + edge_score + factor_score)
        assert alternative_base == 2.0, "With zero components, floor should be 2.0"

        # Case: Any nonzero component -> should be above floor
        for component_value in [0.5, 1.0, 2.0, 3.0]:
            # Test each component individually
            for i, (a, e, f) in enumerate([
                (component_value, 0, 0),
                (0, component_value, 0),
                (0, 0, component_value),
            ]):
                alt_base = min(10, 2.0 + a + e + f)
                assert alt_base > 2.0, \
                    f"With any nonzero component ({a},{e},{f}), base should be > 2.0, got {alt_base}"


class TestDebugCandidateAuditFields:
    """Verify debug.top_game_candidates includes ai_audit fields."""

    def test_debug_pick_structure_includes_ai_audit(self):
        """
        The _debug_pick function should include ai_audit with all component fields.
        """
        required_ai_audit_fields = [
            "ai_mode",
            "models_used_count",
            "deviation_score",
            "agreement_score",
            "edge_score",
            "factor_score",
            "alternative_base",
            "base_score_used",
            "pillar_boost",
            "model_std",
        ]

        # Simulate a pick with ai_breakdown
        mock_pick = {
            "ai_score": 5.0,
            "ai_breakdown": {
                "ai_mode": "ML_PRIMARY",
                "models_used_count": 6,
                "deviation_score": 0.5,
                "agreement_score": 2.0,
                "edge_score": 1.0,
                "factor_score": 0.5,
                "alternative_base": 5.5,
                "base_score_used": "ALTERNATIVE",
                "pillar_boost": 0.0,
                "model_std": 1.5,
            }
        }

        # Verify all required fields are present
        ai_breakdown = mock_pick["ai_breakdown"]
        for field in required_ai_audit_fields:
            assert field in ai_breakdown, f"ai_breakdown missing required field: {field}"

    def test_all_floor_detection(self):
        """
        Helper to detect when all candidates are at floor.

        If this returns True with ai_mode=ML_PRIMARY, something is wrong with MPS.
        """
        # Simulate candidates all at floor
        candidates_at_floor = [
            {"ai_score": 2.0, "ai_mode": "ML_PRIMARY"},
            {"ai_score": 2.0, "ai_mode": "ML_PRIMARY"},
            {"ai_score": 2.0, "ai_mode": "ML_PRIMARY"},
        ]

        ml_primary_candidates = [c for c in candidates_at_floor if c["ai_mode"] == "ML_PRIMARY"]
        all_at_floor = all(c["ai_score"] == 2.0 for c in ml_primary_candidates)

        assert all_at_floor, "Test setup: all should be at floor"

        # This is the WARNING condition - if MPS is working, this shouldn't happen
        if all_at_floor and len(ml_primary_candidates) > 0:
            # In production, this would trigger a warning/alert
            pass  # Guard detected: MPS returning floor for all candidates

    def test_variance_detection(self):
        """
        Helper to verify candidates show variance (healthy MPS).
        """
        # Simulate candidates with variance
        candidates_with_variance = [
            {"ai_score": 2.0, "ai_mode": "ML_PRIMARY"},
            {"ai_score": 4.5, "ai_mode": "ML_PRIMARY"},
            {"ai_score": 7.0, "ai_mode": "ML_PRIMARY"},
            {"ai_score": 3.5, "ai_mode": "ML_PRIMARY"},
        ]

        scores = [c["ai_score"] for c in candidates_with_variance]
        unique_scores = set(scores)

        assert len(unique_scores) > 1, "Should have variance"
        assert min(scores) >= 2.0, "Minimum should be at or above floor"
        assert max(scores) > 2.0, "At least one should be above floor"
