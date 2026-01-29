"""
Test Titanium Invariants (NEVER BREAK AGAIN)

TITANIUM RULE (MANDATORY):
- There are exactly 4 engines: ai, research, esoteric, jarvis
- Qualifying threshold: >= 8.0
- Titanium triggered iff 3 of 4 engines qualify
- tier == "TITANIUM_SMASH" iff titanium_triggered is True
- It is a BUG if: "TITANIUM: 1/4" and tier is TITANIUM_SMASH
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from core.invariants import (
    TITANIUM_ENGINE_COUNT,
    TITANIUM_ENGINE_THRESHOLD,
    TITANIUM_MIN_ENGINES,
    TITANIUM_ENGINE_NAMES,
    validate_titanium_assignment,
)


class TestTitaniumConstants:
    """Test that Titanium constants are correctly defined"""

    def test_engine_count_is_4(self):
        """There are exactly 4 engines"""
        assert TITANIUM_ENGINE_COUNT == 4

    def test_engine_names_match_count(self):
        """Engine names list matches count"""
        assert len(TITANIUM_ENGINE_NAMES) == TITANIUM_ENGINE_COUNT

    def test_engine_names_are_correct(self):
        """Engine names are: ai, research, esoteric, jarvis"""
        expected = ["ai", "research", "esoteric", "jarvis"]
        assert TITANIUM_ENGINE_NAMES == expected

    def test_threshold_is_8_0(self):
        """Qualifying threshold is 8.0 (STRICT)"""
        assert TITANIUM_ENGINE_THRESHOLD == 8.0

    def test_min_engines_is_3(self):
        """Minimum qualifying engines is 3"""
        assert TITANIUM_MIN_ENGINES == 3


class TestTitaniumValidation:
    """Test validate_titanium_assignment() enforces invariants"""

    def test_titanium_with_3_engines_qualifies(self):
        """3 engines >= 8.0 → titanium_triggered=True, tier=TITANIUM_SMASH"""
        engine_scores = {
            "ai": 8.5,
            "research": 8.2,
            "esoteric": 8.0,
            "jarvis": 7.0  # Below threshold
        }
        qualifying = ["ai", "research", "esoteric"]

        is_valid, error = validate_titanium_assignment(
            tier="TITANIUM_SMASH",
            titanium_triggered=True,
            qualifying_engines=qualifying,
            engine_scores=engine_scores
        )

        assert is_valid is True, f"Should be valid: {error}"

    def test_titanium_with_2_engines_fails(self):
        """Only 2 engines >= 8.0 → CANNOT be TITANIUM_SMASH"""
        engine_scores = {
            "ai": 8.5,
            "research": 8.0,
            "esoteric": 7.0,  # Below
            "jarvis": 6.0     # Below
        }
        qualifying = ["ai", "research"]

        # Should NOT be TITANIUM_SMASH
        is_valid, error = validate_titanium_assignment(
            tier="TITANIUM_SMASH",  # BUG: Tier says Titanium
            titanium_triggered=True,  # BUG: Triggered with only 2
            qualifying_engines=qualifying,
            engine_scores=engine_scores
        )

        assert is_valid is False, "Should detect invariant violation (only 2/4 engines)"
        assert "only 2/4 engines qualify" in error.lower()

    def test_titanium_triggered_but_tier_not_titanium(self):
        """If titanium_triggered=True, tier MUST be TITANIUM_SMASH"""
        engine_scores = {
            "ai": 8.5,
            "research": 8.2,
            "esoteric": 8.0,
            "jarvis": 7.0
        }
        qualifying = ["ai", "research", "esoteric"]

        is_valid, error = validate_titanium_assignment(
            tier="GOLD_STAR",  # BUG: Not TITANIUM_SMASH
            titanium_triggered=True,  # But triggered
            qualifying_engines=qualifying,
            engine_scores=engine_scores
        )

        assert is_valid is False, "Should detect mismatch"
        assert "titanium_triggered=true but tier=gold_star" in error.lower()

    def test_tier_titanium_but_not_triggered(self):
        """If tier=TITANIUM_SMASH, titanium_triggered MUST be True"""
        engine_scores = {
            "ai": 8.5,
            "research": 8.2,
            "esoteric": 8.0,
            "jarvis": 7.0
        }
        qualifying = ["ai", "research", "esoteric"]

        is_valid, error = validate_titanium_assignment(
            tier="TITANIUM_SMASH",  # Says Titanium
            titanium_triggered=False,  # BUG: Not triggered
            qualifying_engines=qualifying,
            engine_scores=engine_scores
        )

        assert is_valid is False, "Should detect mismatch"
        assert "tier=titanium_smash but titanium_triggered=false" in error.lower()

    def test_qualifying_engine_below_threshold(self):
        """Engines in qualifying_engines list must actually score >= 8.0"""
        engine_scores = {
            "ai": 8.5,
            "research": 7.5,  # Below 8.0!
            "esoteric": 8.0,
            "jarvis": 8.2
        }
        # BUG: Research is in qualifying list but scores < 8.0
        qualifying = ["ai", "research", "esoteric"]

        is_valid, error = validate_titanium_assignment(
            tier="TITANIUM_SMASH",
            titanium_triggered=True,
            qualifying_engines=qualifying,
            engine_scores=engine_scores
        )

        assert is_valid is False, "Should detect research < 8.0"
        assert "research" in error.lower() and "7.5" in error.lower()

    def test_all_4_engines_qualify(self):
        """All 4 engines >= 8.0 → valid TITANIUM_SMASH"""
        engine_scores = {
            "ai": 9.0,
            "research": 8.5,
            "esoteric": 8.2,
            "jarvis": 8.0
        }
        qualifying = ["ai", "research", "esoteric", "jarvis"]

        is_valid, error = validate_titanium_assignment(
            tier="TITANIUM_SMASH",
            titanium_triggered=True,
            qualifying_engines=qualifying,
            engine_scores=engine_scores
        )

        assert is_valid is True, f"All 4 engines should qualify: {error}"

    def test_exactly_3_engines_boundary(self):
        """Exactly 3 engines at 8.0 → valid"""
        engine_scores = {
            "ai": 8.0,
            "research": 8.0,
            "esoteric": 8.0,
            "jarvis": 7.99  # Just below
        }
        qualifying = ["ai", "research", "esoteric"]

        is_valid, error = validate_titanium_assignment(
            tier="TITANIUM_SMASH",
            titanium_triggered=True,
            qualifying_engines=qualifying,
            engine_scores=engine_scores
        )

        assert is_valid is True, f"Exactly 3 at 8.0 should qualify: {error}"

    def test_1_engine_cannot_be_titanium(self):
        """Only 1 engine >= 8.0 → CANNOT be TITANIUM_SMASH"""
        engine_scores = {
            "ai": 8.5,
            "research": 7.0,
            "esoteric": 6.0,
            "jarvis": 5.0
        }
        qualifying = ["ai"]

        is_valid, error = validate_titanium_assignment(
            tier="TITANIUM_SMASH",
            titanium_triggered=True,
            qualifying_engines=qualifying,
            engine_scores=engine_scores
        )

        assert is_valid is False, "1 engine cannot trigger Titanium"
        assert "only 1/4 engines" in error.lower()

    def test_0_engines_cannot_be_titanium(self):
        """0 engines >= 8.0 → CANNOT be TITANIUM_SMASH"""
        engine_scores = {
            "ai": 7.0,
            "research": 7.0,
            "esoteric": 6.0,
            "jarvis": 5.0
        }
        qualifying = []

        is_valid, error = validate_titanium_assignment(
            tier="TITANIUM_SMASH",
            titanium_triggered=True,
            qualifying_engines=qualifying,
            engine_scores=engine_scores
        )

        assert is_valid is False, "0 engines cannot trigger Titanium"


class TestTitaniumNonTitaniumTiers:
    """Test that non-Titanium tiers don't trigger Titanium logic"""

    def test_gold_star_with_3_engines_no_titanium_trigger(self):
        """If titanium_triggered=False, tier should not be TITANIUM even with 3 engines"""
        engine_scores = {
            "ai": 8.5,
            "research": 8.2,
            "esoteric": 8.0,
            "jarvis": 7.0
        }
        qualifying = ["ai", "research", "esoteric"]  # 3 qualify

        # Valid: titanium_triggered=False, tier=GOLD_STAR
        is_valid, error = validate_titanium_assignment(
            tier="GOLD_STAR",
            titanium_triggered=False,
            qualifying_engines=qualifying,
            engine_scores=engine_scores
        )

        # This should FAIL validation because 3 engines qualify but titanium_triggered=False
        # (the logic should detect this mismatch)
        assert is_valid is False, "Should detect that 3 engines qualify but not triggered"

    def test_edge_lean_with_2_engines_valid(self):
        """2 engines >= 8.0, tier=EDGE_LEAN, titanium_triggered=False → valid"""
        engine_scores = {
            "ai": 8.5,
            "research": 8.0,
            "esoteric": 7.0,
            "jarvis": 6.0
        }
        qualifying = ["ai", "research"]

        is_valid, error = validate_titanium_assignment(
            tier="EDGE_LEAN",
            titanium_triggered=False,
            qualifying_engines=qualifying,
            engine_scores=engine_scores
        )

        assert is_valid is True, f"2 engines with EDGE_LEAN should be valid: {error}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
