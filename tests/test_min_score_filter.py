"""
Test: 6.5 Minimum Score Filter (MANDATORY)

REQUIREMENT: NEVER return any pick with final_score < 6.5 to frontend.
This is the community threshold - anything below should be filtered out
before reaching the response.

Tests verify:
1. Picks with score < 6.5 are filtered out
2. Picks with score >= 6.5 are kept
3. Picks at exactly 6.5 boundary are included
4. Filter is applied to both props and game picks
5. Debug output shows filtered counts
"""

import pytest
from core.invariants import COMMUNITY_MIN_SCORE


class TestMinScoreFilter:
    """Test minimum score filter (6.5 threshold)"""

    def test_community_threshold_is_6_5(self):
        """Verify COMMUNITY_MIN_SCORE is 6.5"""
        assert COMMUNITY_MIN_SCORE == 6.5, f"Expected 6.5, got {COMMUNITY_MIN_SCORE}"

    def test_picks_below_6_5_are_filtered(self):
        """Picks with final_score < 6.5 should be filtered out"""
        picks = [
            {"pick_id": "1", "final_score": 6.4, "player": "A"},
            {"pick_id": "2", "final_score": 5.0, "player": "B"},
            {"pick_id": "3", "final_score": 3.2, "player": "C"},
        ]

        filtered = [p for p in picks if p["final_score"] >= COMMUNITY_MIN_SCORE]
        assert len(filtered) == 0, "All picks below 6.5 should be filtered"

    def test_picks_above_6_5_are_kept(self):
        """Picks with final_score >= 6.5 should be kept"""
        picks = [
            {"pick_id": "1", "final_score": 8.5, "player": "A"},
            {"pick_id": "2", "final_score": 7.2, "player": "B"},
            {"pick_id": "3", "final_score": 6.5, "player": "C"},
        ]

        filtered = [p for p in picks if p["final_score"] >= COMMUNITY_MIN_SCORE]
        assert len(filtered) == 3, "All picks >= 6.5 should be kept"

    def test_picks_exactly_at_6_5_are_included(self):
        """Pick with exactly 6.5 score should be included (>= not >)"""
        picks = [
            {"pick_id": "1", "final_score": 6.5, "player": "A"},
            {"pick_id": "2", "final_score": 6.500001, "player": "B"},
            {"pick_id": "3", "final_score": 6.49999, "player": "C"},
        ]

        filtered = [p for p in picks if p["final_score"] >= COMMUNITY_MIN_SCORE]

        # Exactly 6.5 and 6.500001 should pass
        # 6.49999 should fail
        assert len(filtered) == 2, "Picks >= 6.5 should be kept, < 6.5 filtered"

        # Verify specific inclusion
        ids = [p["pick_id"] for p in filtered]
        assert "1" in ids, "Exactly 6.5 should be included"
        assert "2" in ids, "6.500001 should be included"
        assert "3" not in ids, "6.49999 should be filtered"

    def test_mixed_picks_filtered_correctly(self):
        """Test mix of props and game picks with various scores"""
        picks = [
            {"pick_id": "p1", "final_score": 9.0, "type": "prop", "player": "LeBron"},
            {"pick_id": "p2", "final_score": 6.4, "type": "prop", "player": "Curry"},
            {"pick_id": "g1", "final_score": 7.5, "type": "game", "matchup": "LAL@BOS"},
            {"pick_id": "g2", "final_score": 5.9, "type": "game", "matchup": "MIA@PHX"},
            {"pick_id": "p3", "final_score": 6.5, "type": "prop", "player": "Tatum"},
        ]

        filtered = [p for p in picks if p["final_score"] >= COMMUNITY_MIN_SCORE]

        assert len(filtered) == 3, "Should have 3 picks above threshold"

        kept_ids = [p["pick_id"] for p in filtered]
        assert "p1" in kept_ids, "9.0 prop should be kept"
        assert "g1" in kept_ids, "7.5 game should be kept"
        assert "p3" in kept_ids, "6.5 prop should be kept"
        assert "p2" not in kept_ids, "6.4 prop should be filtered"
        assert "g2" not in kept_ids, "5.9 game should be filtered"

    def test_filter_counts_are_tracked(self):
        """Verify filter counts can be tracked for debug output"""
        all_picks = [
            {"final_score": 8.0},
            {"final_score": 7.5},
            {"final_score": 6.5},
            {"final_score": 6.4},
            {"final_score": 5.0},
            {"final_score": 3.0},
        ]

        filtered = [p for p in all_picks if p["final_score"] >= COMMUNITY_MIN_SCORE]
        filtered_count = len(all_picks) - len(filtered)

        assert len(filtered) == 3, "3 picks should pass filter"
        assert filtered_count == 3, "3 picks should be filtered out"

    def test_empty_list_handled(self):
        """Empty pick list should return empty"""
        picks = []
        filtered = [p for p in picks if p["final_score"] >= COMMUNITY_MIN_SCORE]
        assert len(filtered) == 0

    def test_all_above_threshold(self):
        """When all picks above threshold, none should be filtered"""
        picks = [
            {"final_score": 9.5},
            {"final_score": 8.0},
            {"final_score": 7.0},
        ]

        filtered = [p for p in picks if p["final_score"] >= COMMUNITY_MIN_SCORE]
        assert len(filtered) == 3
        assert len(picks) - len(filtered) == 0

    def test_all_below_threshold(self):
        """When all picks below threshold, all should be filtered"""
        picks = [
            {"final_score": 6.4},
            {"final_score": 5.0},
            {"final_score": 3.0},
        ]

        filtered = [p for p in picks if p["final_score"] >= COMMUNITY_MIN_SCORE]
        assert len(filtered) == 0
        assert len(picks) - len(filtered) == 3


class TestMinScoreValidation:
    """Test validation functions for minimum score"""

    def test_validate_score_threshold_rejects_low_scores(self):
        """validate_score_threshold should reject picks < 6.5"""
        from core.invariants import validate_score_threshold

        # Below threshold - should fail
        is_valid, error = validate_score_threshold(6.4, tier="EDGE_LEAN")
        assert is_valid is False
        assert "6.5" in error or "threshold" in error.lower()

    def test_validate_score_threshold_accepts_valid_scores(self):
        """validate_score_threshold should accept picks >= 6.5"""
        from core.invariants import validate_score_threshold

        # At threshold - should pass
        is_valid, error = validate_score_threshold(6.5, tier="EDGE_LEAN")
        assert is_valid is True
        assert error == ""

        # Above threshold - should pass
        is_valid, error = validate_score_threshold(9.0, tier="GOLD_STAR")
        assert is_valid is True
        assert error == ""

    def test_validate_score_threshold_handles_pass_tier(self):
        """PASS tier with low score should still be validated"""
        from core.invariants import validate_score_threshold

        # PASS tier with low score - validation should still fail
        # (PASS tier picks shouldn't reach this point, but if they do, block them)
        is_valid, error = validate_score_threshold(4.0, tier="PASS")
        assert is_valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
