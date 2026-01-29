"""
Test Titanium Tier STRICT enforcement (v15.0)

TITANIUM RULE:
- 3 of 4 engines must score >= 8.0 (NOT 6.5)
- final_score must be >= 8.0
- If titanium_hits < 3, tier CANNOT be TITANIUM_SMASH

Tests verify:
1. If tier == "TITANIUM_SMASH" then titanium_hits >= 3 (mandatory)
2. If titanium_hits < 3 then tier != "TITANIUM_SMASH" (mandatory)
3. tier_reason reflects actual hits and required threshold
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from tiering import (
    check_titanium_rule,
    tier_from_score,
    TITANIUM_THRESHOLD,
    TITANIUM_MIN_ENGINES
)


class TestTitaniumStrictEnforcement:
    """Test STRICT Titanium enforcement: 3/4 engines >= 8.0"""

    def test_titanium_threshold_is_8_0(self):
        """Verify TITANIUM_THRESHOLD is 8.0 (not 6.5)"""
        assert TITANIUM_THRESHOLD == 8.0, "TITANIUM_THRESHOLD must be 8.0"
        assert TITANIUM_MIN_ENGINES == 3, "TITANIUM_MIN_ENGINES must be 3"

    def test_titanium_triggered_with_3_engines_above_8(self):
        """PASS: 3 engines >= 8.0 triggers Titanium"""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=8.5,
            research_score=8.2,
            esoteric_score=8.0,
            jarvis_score=7.0,  # Below 8.0
            final_score=9.0
        )

        assert triggered is True, "Titanium should trigger with 3/4 engines >= 8.0"
        assert len(qualifying) == 3, f"Expected 3 qualifying engines, got {len(qualifying)}"
        assert "AI" in qualifying
        assert "Research" in qualifying
        assert "Esoteric" in qualifying
        assert "Jarvis" not in qualifying

    def test_titanium_not_triggered_with_2_engines_above_8(self):
        """FAIL: Only 2 engines >= 8.0 does NOT trigger Titanium"""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=8.5,
            research_score=8.2,
            esoteric_score=7.0,  # Below 8.0
            jarvis_score=6.5,    # Below 8.0
            final_score=9.0
        )

        assert triggered is False, "Titanium should NOT trigger with only 2/4 engines >= 8.0"
        assert len(qualifying) == 2, f"Expected 2 qualifying engines, got {len(qualifying)}"
        assert "2/4" in explanation or "need 3" in explanation.lower()

    def test_titanium_not_triggered_with_1_engine_above_8(self):
        """FAIL: Only 1 engine >= 8.0 does NOT trigger Titanium"""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=8.5,  # Only this one above 8.0
            research_score=7.0,
            esoteric_score=6.0,
            jarvis_score=5.0,
            final_score=9.0
        )

        assert triggered is False, "Titanium should NOT trigger with only 1/4 engines >= 8.0"
        assert len(qualifying) == 1, f"Expected 1 qualifying engine, got {len(qualifying)}"

    def test_titanium_triggered_with_all_4_engines_above_8(self):
        """PASS: All 4 engines >= 8.0 triggers Titanium (perfect score)"""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=9.0,
            research_score=8.5,
            esoteric_score=8.2,
            jarvis_score=8.0,
            final_score=9.5
        )

        assert triggered is True, "Titanium should trigger with 4/4 engines >= 8.0"
        assert len(qualifying) == 4, f"Expected 4 qualifying engines, got {len(qualifying)}"

    def test_titanium_fails_if_final_score_below_8(self):
        """FAIL: Even if 3 engines >= 8.0, final_score < 8.0 blocks Titanium"""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=8.5,
            research_score=8.2,
            esoteric_score=8.0,
            jarvis_score=7.0,
            final_score=7.8  # Below 8.0!
        )

        assert triggered is False, "Titanium should fail when final_score < 8.0"
        assert "7.8 < 8" in explanation or "prerequisite" in explanation.lower()

    def test_titanium_boundary_exactly_8_0(self):
        """PASS: Engines exactly at 8.0 should qualify"""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=8.0,
            research_score=8.0,
            esoteric_score=8.0,
            jarvis_score=7.9,  # Just below
            final_score=8.0
        )

        assert triggered is True, "Titanium should trigger when exactly 3 engines == 8.0"
        assert len(qualifying) == 3

    def test_titanium_boundary_just_below_8_0(self):
        """FAIL: 7.99 does not qualify as >= 8.0"""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=7.99,
            research_score=7.99,
            esoteric_score=7.99,
            jarvis_score=7.99,
            final_score=9.0
        )

        assert triggered is False, "7.99 should NOT qualify (must be >= 8.0)"
        assert len(qualifying) == 0

    def test_tier_assignment_titanium_smash_requires_3_hits(self):
        """Integration: tier_from_score assigns TITANIUM only if titanium_triggered=True"""
        # Case 1: titanium_triggered=True → TITANIUM_SMASH
        tier_data = tier_from_score(
            final_score=9.0,
            titanium_triggered=True
        )
        assert tier_data["tier"] == "TITANIUM_SMASH", "Should assign TITANIUM_SMASH when titanium_triggered=True"

        # Case 2: titanium_triggered=False → NOT TITANIUM (even with high score)
        tier_data = tier_from_score(
            final_score=9.0,
            titanium_triggered=False
        )
        assert tier_data["tier"] != "TITANIUM_SMASH", "Should NOT assign TITANIUM_SMASH when titanium_triggered=False"
        assert tier_data["tier"] == "GOLD_STAR", "Should fall back to GOLD_STAR for score 9.0 without Titanium"

    def test_tier_reason_reflects_titanium_hits(self):
        """Verify tier_reason shows correct engine hit count"""
        # This test validates the output format
        # In production, tier_reason should show: "TITANIUM: 3/4 engines >= 8.0"

        # 3 engines qualify
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=8.5,
            research_score=8.2,
            esoteric_score=8.0,
            jarvis_score=7.0,
            final_score=9.0
        )
        assert "3/4" in explanation, f"Explanation should show '3/4 engines', got: {explanation}"

        # 2 engines qualify (fail)
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=8.5,
            research_score=8.0,
            esoteric_score=7.0,
            jarvis_score=6.0,
            final_score=9.0
        )
        assert "2/4" in explanation, f"Explanation should show '2/4 engines', got: {explanation}"


class TestTitaniumFailureReasons:
    """Test that tier_reason explains WHY Titanium failed"""

    def test_titanium_fail_reason_shows_which_engines_failed(self):
        """tier_reason should list which engines didn't meet 8.0 threshold"""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=8.5,  # PASS
            research_score=7.5,  # FAIL
            esoteric_score=6.0,  # FAIL
            jarvis_score=5.0,  # FAIL
            final_score=9.0
        )

        assert triggered is False
        assert len(qualifying) == 1  # Only AI qualified
        assert "AI" in qualifying
        assert "Research" not in qualifying
        assert "Esoteric" not in qualifying
        assert "Jarvis" not in qualifying

    def test_titanium_fail_when_final_score_low(self):
        """tier_reason should say 'final_score < 8.0' when that's the blocker"""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=8.5,
            research_score=8.2,
            esoteric_score=8.0,
            jarvis_score=8.0,  # All 4 pass!
            final_score=7.5  # But final_score fails
        )

        assert triggered is False
        assert "7.5 < 8" in explanation or "prerequisite" in explanation.lower()


class TestTitaniumEdgeCases:
    """Test edge cases and special scenarios"""

    def test_zero_engines_above_threshold(self):
        """All engines below 8.0 → definitely no Titanium"""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=7.0,
            research_score=7.0,
            esoteric_score=7.0,
            jarvis_score=7.0,
            final_score=9.0
        )

        assert triggered is False
        assert len(qualifying) == 0

    def test_negative_scores_dont_qualify(self):
        """Negative scores should not count toward Titanium"""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=-1.0,
            research_score=-5.0,
            esoteric_score=8.0,
            jarvis_score=8.0,
            final_score=9.0
        )

        assert triggered is False
        assert len(qualifying) == 2  # Only Esoteric + Jarvis

    def test_very_high_scores_still_require_3_engines(self):
        """Even with perfect final_score, need 3 engines >= 8.0"""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=10.0,
            research_score=7.9,  # Just below
            esoteric_score=7.9,  # Just below
            jarvis_score=7.9,  # Just below
            final_score=10.0  # Perfect final score
        )

        assert triggered is False, "Even with perfect final_score, need 3 engines >= 8.0"
        assert len(qualifying) == 1  # Only AI


class TestBackwardCompatibility:
    """Ensure v15.0 changes don't break existing code"""

    def test_check_titanium_rule_returns_tuple(self):
        """Function should return (bool, str, list)"""
        result = check_titanium_rule(
            ai_score=8.0,
            research_score=8.0,
            esoteric_score=8.0,
            jarvis_score=8.0,
            final_score=8.0
        )

        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)
        assert isinstance(result[2], list)

    def test_tier_from_score_still_works(self):
        """tier_from_score should still return dict with expected keys"""
        tier_data = tier_from_score(
            final_score=8.5,
            titanium_triggered=True
        )

        assert "tier" in tier_data
        assert "units" in tier_data
        assert "action" in tier_data
        assert "badge" in tier_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
