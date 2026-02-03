"""
TEST_TIERING.PY - Tests for Tier Threshold Changes
===================================================
v12.0 - Production hardening tier verification

Tests verify:
1. Tier boundaries: 5.4, 5.5, 6.4, 6.5, 7.4, 7.5, 8.0
2. Titanium rule: final_score >= 8.0 + 3/4 engines >= 6.5
3. Community filter: Only >= 6.5 shown

Run with: python -m pytest tests/test_tiering.py -v
"""

import os
import sys
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tiering import (
    tier_from_score,
    check_titanium_rule,
    filter_for_community,
    is_community_worthy,
    validate_prop_availability,
    TIER_CONFIG,
    COMMUNITY_MIN_SCORE,
    TITANIUM_THRESHOLD,
    TITANIUM_FINAL_SCORE_MIN,
    ENGINE_VERSION
)


# =============================================================================
# VERSION TESTS
# =============================================================================

class TestVersion:
    """Test version is updated."""

    def test_engine_version(self):
        """Test engine version is 12.0."""
        assert ENGINE_VERSION == "12.0"


# =============================================================================
# TIER THRESHOLD TESTS
# =============================================================================

class TestTierThresholds:
    """Test tier threshold boundaries."""

    def test_config_gold_star_threshold(self):
        """Test GOLD_STAR threshold is 7.5."""
        assert TIER_CONFIG["GOLD_STAR"]["threshold"] == 7.5

    def test_config_edge_lean_threshold(self):
        """Test EDGE_LEAN threshold is 6.5."""
        assert TIER_CONFIG["EDGE_LEAN"]["threshold"] == 6.5

    def test_config_monitor_threshold(self):
        """Test MONITOR threshold is 5.5."""
        assert TIER_CONFIG["MONITOR"]["threshold"] == 5.5

    def test_score_5_4_is_pass(self):
        """Test score 5.4 is PASS tier."""
        result = tier_from_score(5.4)
        assert result["tier"] == "PASS"

    def test_score_5_5_is_monitor(self):
        """Test score 5.5 is MONITOR tier."""
        result = tier_from_score(5.5)
        assert result["tier"] == "MONITOR"

    def test_score_6_4_is_monitor(self):
        """Test score 6.4 is still MONITOR tier."""
        result = tier_from_score(6.4)
        assert result["tier"] == "MONITOR"

    def test_score_6_5_is_edge_lean(self):
        """Test score 6.5 is EDGE_LEAN tier."""
        result = tier_from_score(6.5)
        assert result["tier"] == "EDGE_LEAN"

    def test_score_7_4_is_edge_lean(self):
        """Test score 7.4 is still EDGE_LEAN tier."""
        result = tier_from_score(7.4)
        assert result["tier"] == "EDGE_LEAN"

    def test_score_7_5_is_gold_star(self):
        """Test score 7.5 is GOLD_STAR tier."""
        result = tier_from_score(7.5)
        assert result["tier"] == "GOLD_STAR"

    def test_score_8_0_is_gold_star(self):
        """Test score 8.0 is still GOLD_STAR tier."""
        result = tier_from_score(8.0)
        assert result["tier"] == "GOLD_STAR"


# =============================================================================
# TITANIUM RULE TESTS
# =============================================================================

class TestTitaniumRule:
    """Test Titanium rule with final_score requirement."""

    def test_titanium_threshold_is_8_0(self):
        """Test TITANIUM_THRESHOLD is 8.0."""
        assert TITANIUM_THRESHOLD == 8.0

    def test_titanium_final_score_min_is_8_0(self):
        """Test TITANIUM_FINAL_SCORE_MIN is 8.0."""
        assert TITANIUM_FINAL_SCORE_MIN == 8.0

    def test_titanium_not_triggered_final_score_7_9(self):
        """Test Titanium NOT triggered when final_score=7.9 even with all engines=10."""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=10.0,
            research_score=10.0,
            esoteric_score=10.0,
            jarvis_score=10.0,
            final_score=7.9
        )
        assert triggered == False
        assert "prerequisite not met" in explanation

    def test_titanium_triggered_final_8_5_engines_8_8_8_4(self):
        """Test Titanium IS triggered when final=8.5 and engines=[8,8,8,4]."""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=8.0,
            research_score=8.0,
            esoteric_score=8.0,
            jarvis_score=4.0,
            final_score=8.5
        )
        assert triggered == True
        assert len(qualifying) == 3  # AI, Research, Esoteric qualify

    def test_titanium_not_triggered_engines_8_8_4_4(self):
        """Test Titanium NOT triggered with only 2 engines >= 6.5."""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=8.0,
            research_score=8.0,
            esoteric_score=4.0,
            jarvis_score=4.0,
            final_score=8.5
        )
        assert triggered == False
        assert len(qualifying) == 2

    def test_titanium_with_threshold(self):
        """Test 3 engines at 8.0 triggers Titanium."""
        triggered, explanation, qualifying = check_titanium_rule(
            ai_score=8.0,
            research_score=8.0,
            esoteric_score=8.0,
            jarvis_score=5.0,
            final_score=8.0
        )
        assert triggered == True
        assert len(qualifying) == 3


# =============================================================================
# COMMUNITY FILTER TESTS
# =============================================================================

class TestCommunityFilter:
    """Test community output filter."""

    def test_community_min_score_is_6_5(self):
        """Test COMMUNITY_MIN_SCORE is 6.5."""
        assert COMMUNITY_MIN_SCORE == 6.5

    def test_is_community_worthy_6_5(self):
        """Test 6.5 is community worthy."""
        assert is_community_worthy(6.5) == True

    def test_is_community_worthy_6_4(self):
        """Test 6.4 is NOT community worthy."""
        assert is_community_worthy(6.4) == False

    def test_filter_for_community_removes_low_scores(self):
        """Test filter_for_community removes picks below 6.5."""
        picks = [
            {"name": "Pick A", "final_score": 8.0},
            {"name": "Pick B", "final_score": 6.5},
            {"name": "Pick C", "final_score": 6.4},
            {"name": "Pick D", "final_score": 5.0},
        ]

        filtered = filter_for_community(picks)

        assert len(filtered) == 2
        assert filtered[0]["name"] == "Pick A"
        assert filtered[1]["name"] == "Pick B"


# =============================================================================
# PROP AVAILABILITY TESTS
# =============================================================================

class TestPropAvailability:
    """Test prop availability validation."""

    def test_validate_prop_available(self):
        """Test player found in available props."""
        available = [
            {"player": "LeBron James"},
            {"player": "Stephen Curry"},
        ]

        is_available, reason = validate_prop_availability("LeBron James", available)

        assert is_available == True
        assert reason == "Available"

    def test_validate_prop_not_available(self):
        """Test player not found in available props."""
        available = [
            {"player": "LeBron James"},
            {"player": "Stephen Curry"},
        ]

        is_available, reason = validate_prop_availability("Unknown Player", available)

        assert is_available == False
        assert "not offered" in reason

    def test_validate_prop_empty_list(self):
        """Test with empty props list."""
        is_available, reason = validate_prop_availability("Any Player", [])

        assert is_available == False
        assert "No props available" in reason


# =============================================================================
# TITANIUM TRIGGERED VIA TIER_FROM_SCORE
# =============================================================================

class TestTitaniumViaTierFromScore:
    """Test Titanium via tier_from_score."""

    def test_tier_from_score_titanium_triggered(self):
        """Test tier_from_score returns TITANIUM_SMASH when triggered."""
        result = tier_from_score(
            final_score=8.5,
            titanium_triggered=True
        )

        assert result["tier"] == "TITANIUM_SMASH"
        assert result["units"] == 2.5
        assert result["titanium_triggered"] == True

    def test_tier_from_score_titanium_not_triggered_returns_gold(self):
        """Test tier_from_score returns GOLD_STAR when not triggered but high score."""
        result = tier_from_score(
            final_score=8.5,
            titanium_triggered=False
        )

        assert result["tier"] == "GOLD_STAR"
        assert result["titanium_triggered"] == False


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
