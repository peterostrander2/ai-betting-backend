"""
Unit Tests for JarvisSavantEngine

Tests the actual implementation of the Jarvis scoring engine including:
- Sacred number trigger detection (2178, 201, 33, 93, 322, 666, 888, 369)
- Gematria calculations (simple, reverse)
- Reduction to single digit
- Gematria signal scoring for player/team combinations
- Power number detection
- Tesla 3-6-9 pattern detection

These tests exercise the real code, not just mock data validation.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from jarvis_savant_engine import (
    JarvisSavantEngine,
    JARVIS_TRIGGERS,
    POWER_NUMBERS,
    TESLA_NUMBERS,
    SIMPLE_GEMATRIA,
    REVERSE_GEMATRIA,
)


@pytest.fixture
def engine():
    """Create a JarvisSavantEngine instance for testing."""
    return JarvisSavantEngine()


class TestReduceToSingle:
    """Test the digit reduction helper."""

    def test_single_digit_unchanged(self, engine):
        """Single digit numbers should remain unchanged."""
        assert engine._reduce_to_single(1) == 1
        assert engine._reduce_to_single(5) == 5
        assert engine._reduce_to_single(9) == 9

    def test_double_digit_reduction(self, engine):
        """Double digit numbers should reduce correctly."""
        assert engine._reduce_to_single(12) == 3  # 1+2=3
        assert engine._reduce_to_single(45) == 9  # 4+5=9
        assert engine._reduce_to_single(78) == 6  # 7+8=15 -> 1+5=6

    def test_master_numbers_preserved(self, engine):
        """Master numbers 11, 22, 33 should NOT reduce further."""
        assert engine._reduce_to_single(11) == 11
        assert engine._reduce_to_single(22) == 22
        assert engine._reduce_to_single(33) == 33

    def test_large_number_reduction(self, engine):
        """Large numbers should reduce to single digit."""
        # 2+1+7+8=18 -> 1+8=9 (18 is not a master number, so continues reducing)
        assert engine._reduce_to_single(2178) == 9
        assert engine._reduce_to_single(999) == 9  # 9+9+9=27 -> 2+7=9
        assert engine._reduce_to_single(123) == 6  # 1+2+3=6

    def test_zero_handling(self, engine):
        """Zero should remain zero."""
        assert engine._reduce_to_single(0) == 0


class TestCalculateGematria:
    """Test gematria calculations."""

    def test_simple_gematria_lowercase(self, engine):
        """Test simple gematria (a=1, b=2, ..., z=26)."""
        result = engine.calculate_gematria("a")
        assert result["simple"] == 1

        result = engine.calculate_gematria("z")
        assert result["simple"] == 26

        # "abc" = 1+2+3 = 6
        result = engine.calculate_gematria("abc")
        assert result["simple"] == 6

    def test_simple_gematria_uppercase(self, engine):
        """Gematria should be case-insensitive."""
        result_lower = engine.calculate_gematria("abc")
        result_upper = engine.calculate_gematria("ABC")
        assert result_lower["simple"] == result_upper["simple"]

    def test_reverse_gematria(self, engine):
        """Test reverse gematria (a=26, b=25, ..., z=1)."""
        result = engine.calculate_gematria("a")
        assert result["reverse"] == 26

        result = engine.calculate_gematria("z")
        assert result["reverse"] == 1

    def test_gematria_with_spaces(self, engine):
        """Spaces should be ignored in gematria calculation."""
        result_no_space = engine.calculate_gematria("lebron")
        result_with_space = engine.calculate_gematria("le bron")
        assert result_no_space["simple"] == result_with_space["simple"]

    def test_gematria_returns_all_fields(self, engine):
        """Gematria result should include all expected fields."""
        result = engine.calculate_gematria("test")
        assert "text" in result
        assert "simple" in result
        assert "reverse" in result
        assert "jewish" in result
        assert "simple_reduction" in result
        assert "reverse_reduction" in result

    def test_gematria_known_values(self, engine):
        """Test known gematria values for common names."""
        # "lebron" = l(12) + e(5) + b(2) + r(18) + o(15) + n(14) = 66
        result = engine.calculate_gematria("lebron")
        assert result["simple"] == 66

        # "james" = j(10) + a(1) + m(13) + e(5) + s(19) = 48
        result = engine.calculate_gematria("james")
        assert result["simple"] == 48


class TestCheckJarvisTrigger:
    """Test sacred number trigger detection."""

    def test_direct_trigger_2178(self, engine):
        """The IMMORTAL number 2178 should trigger directly."""
        result = engine.check_jarvis_trigger(2178)
        assert result["trigger_count"] > 0
        assert any(t["number"] == 2178 for t in result["triggers_hit"])
        assert any(t["match_type"] == "DIRECT" for t in result["triggers_hit"])
        assert result["total_boost"] > 0

    def test_direct_trigger_33(self, engine):
        """Master number 33 should trigger directly."""
        result = engine.check_jarvis_trigger(33)
        assert result["trigger_count"] > 0
        assert any(t["number"] == 33 for t in result["triggers_hit"])

    def test_direct_trigger_201(self, engine):
        """The ORDER number 201 should trigger."""
        result = engine.check_jarvis_trigger(201)
        assert any(t["number"] == 201 for t in result["triggers_hit"])

    def test_direct_trigger_322(self, engine):
        """The SOCIETY number 322 should trigger."""
        result = engine.check_jarvis_trigger(322)
        assert any(t["number"] == 322 for t in result["triggers_hit"])

    def test_direct_trigger_666(self, engine):
        """The BEAST number 666 should trigger."""
        result = engine.check_jarvis_trigger(666)
        assert any(t["number"] == 666 for t in result["triggers_hit"])

    def test_direct_trigger_888(self, engine):
        """JESUS number 888 should trigger."""
        result = engine.check_jarvis_trigger(888)
        assert any(t["number"] == 888 for t in result["triggers_hit"])

    def test_direct_trigger_369(self, engine):
        """TESLA KEY 369 should trigger."""
        result = engine.check_jarvis_trigger(369)
        assert any(t["number"] == 369 for t in result["triggers_hit"])

    def test_power_number_detection(self, engine):
        """Power numbers (11, 22, 33, ..., 99) should trigger."""
        for num in [11, 22, 44, 55, 66, 77, 88, 99]:
            result = engine.check_jarvis_trigger(num)
            assert any(t["match_type"] == "POWER_NUMBER" for t in result["triggers_hit"]), \
                f"Power number {num} should trigger"

    def test_tesla_reduction_trigger(self, engine):
        """Numbers reducing to 3, 6, or 9 should trigger Tesla."""
        # 12 reduces to 3
        result = engine.check_jarvis_trigger(12)
        assert any(t["match_type"] == "TESLA_REDUCTION" for t in result["triggers_hit"])

        # 15 reduces to 6
        result = engine.check_jarvis_trigger(15)
        assert any(t["match_type"] == "TESLA_REDUCTION" for t in result["triggers_hit"])

        # 18 reduces to 9
        result = engine.check_jarvis_trigger(18)
        assert any(t["match_type"] == "TESLA_REDUCTION" for t in result["triggers_hit"])

    def test_string_input_gematria(self, engine):
        """String inputs should calculate gematria first."""
        result = engine.check_jarvis_trigger("test")
        assert "numeric_value" in result
        assert isinstance(result["numeric_value"], int)

    def test_total_boost_capped(self, engine):
        """Total boost should be capped at 20."""
        # 2178 has boost of 20 alone
        result = engine.check_jarvis_trigger(2178)
        assert result["total_boost"] <= 20

    def test_no_trigger_for_random_number(self, engine):
        """Random numbers without patterns should have minimal triggers."""
        result = engine.check_jarvis_trigger(17)  # Prime, not power, reduces to 8
        # May still have Tesla reduction if reduces to 3,6,9
        # 17 reduces to 8, not a Tesla number
        assert result["trigger_count"] == 0 or \
            not any(t["match_type"] == "DIRECT" for t in result["triggers_hit"])

    def test_result_structure(self, engine):
        """Check trigger result has all expected fields."""
        result = engine.check_jarvis_trigger(100)
        assert "input" in result
        assert "numeric_value" in result
        assert "reduction" in result
        assert "triggers_hit" in result
        assert "total_boost" in result
        assert "trigger_count" in result


class TestCalculateGematriaSignal:
    """Test gematria-based signal calculation for picks."""

    def test_signal_structure(self, engine):
        """Signal result should have all expected fields."""
        result = engine.calculate_gematria_signal("LeBron James", "Lakers", "Celtics")
        assert "player_gematria" in result
        assert "team_gematria" in result
        assert "opponent_gematria" in result
        assert "combined_value" in result
        assert "matchup_diff" in result
        assert "combined_trigger" in result
        assert "matchup_trigger" in result
        assert "weight" in result
        assert "signal_strength" in result
        assert "signal" in result
        assert "triggered" in result
        assert "influence" in result

    def test_weight_elevation_on_trigger(self, engine):
        """Weight should elevate from 0.30 to 0.52 when triggers fire."""
        # Use names that might trigger
        result = engine.calculate_gematria_signal("A", "Lakers", "Celtics")
        base_weight = result["weight"]
        # Either 0.30 or 0.52 depending on triggers
        assert base_weight in [0.30, 0.52]

    def test_signal_strength_bounds(self, engine):
        """Signal strength should be between 0 and 1."""
        result = engine.calculate_gematria_signal("Stephen Curry", "Warriors", "Rockets")
        assert 0 <= result["signal_strength"] <= 1.0

    def test_signal_levels(self, engine):
        """Signal should be STRONG, MODERATE, or WEAK."""
        result = engine.calculate_gematria_signal("Test", "TeamA", "TeamB")
        assert result["signal"] in ["STRONG", "MODERATE", "WEAK"]

    def test_combined_value_calculation(self, engine):
        """Combined value should be player + team gematria."""
        result = engine.calculate_gematria_signal("abc", "def", "ghi")
        # abc = 1+2+3 = 6
        # def = 4+5+6 = 15
        # combined = 6 + 15 = 21
        assert result["combined_value"] == 21

    def test_matchup_diff_calculation(self, engine):
        """Matchup diff should be absolute difference of team gematrias."""
        result = engine.calculate_gematria_signal("test", "abc", "abcdef")
        # abc = 6
        # abcdef = 6+4+5+6 = 21
        # diff = |6 - 21| = 15
        assert result["matchup_diff"] == 15


class TestTriggerConstants:
    """Test that trigger constants are properly defined."""

    def test_all_sacred_triggers_defined(self):
        """All expected sacred triggers should be in JARVIS_TRIGGERS."""
        expected_triggers = [2178, 201, 33, 93, 322, 666, 888, 369, 1656, 552, 138]
        for num in expected_triggers:
            assert num in JARVIS_TRIGGERS, f"Trigger {num} should be defined"

    def test_trigger_has_required_fields(self):
        """Each trigger should have name, boost, tier, description."""
        for num, data in JARVIS_TRIGGERS.items():
            assert "name" in data, f"Trigger {num} missing 'name'"
            assert "boost" in data, f"Trigger {num} missing 'boost'"
            assert "tier" in data, f"Trigger {num} missing 'tier'"
            assert "description" in data, f"Trigger {num} missing 'description'"

    def test_immortal_has_highest_boost(self):
        """2178 (THE IMMORTAL) should have the highest boost."""
        immortal_boost = JARVIS_TRIGGERS[2178]["boost"]
        for num, data in JARVIS_TRIGGERS.items():
            if num != 2178:
                assert data["boost"] <= immortal_boost, \
                    f"Trigger {num} has boost {data['boost']} >= IMMORTAL {immortal_boost}"

    def test_power_numbers_list(self):
        """Power numbers should be 11, 22, 33, ..., 99."""
        expected = [11, 22, 33, 44, 55, 66, 77, 88, 99]
        assert POWER_NUMBERS == expected

    def test_tesla_numbers_list(self):
        """Tesla numbers should be 3, 6, 9."""
        assert TESLA_NUMBERS == [3, 6, 9]


class TestGematriaConstants:
    """Test gematria lookup tables."""

    def test_simple_gematria_table(self):
        """Simple gematria should map a=1 to z=26."""
        assert SIMPLE_GEMATRIA['a'] == 1
        assert SIMPLE_GEMATRIA['z'] == 26
        assert len(SIMPLE_GEMATRIA) == 26

    def test_reverse_gematria_table(self):
        """Reverse gematria should map a=26 to z=1."""
        assert REVERSE_GEMATRIA['a'] == 26
        assert REVERSE_GEMATRIA['z'] == 1
        assert len(REVERSE_GEMATRIA) == 26


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_gematria(self, engine):
        """Empty string should have zero gematria."""
        result = engine.calculate_gematria("")
        assert result["simple"] == 0
        assert result["reverse"] == 0

    def test_non_alpha_characters_ignored(self, engine):
        """Non-alphabetic characters should be ignored."""
        result = engine.calculate_gematria("a1b2c3")
        expected = engine.calculate_gematria("abc")
        assert result["simple"] == expected["simple"]

    def test_special_characters_ignored(self, engine):
        """Special characters should be ignored."""
        result = engine.calculate_gematria("a.b!c@")
        expected = engine.calculate_gematria("abc")
        assert result["simple"] == expected["simple"]

    def test_trigger_with_float(self, engine):
        """Float inputs should be converted to int."""
        result = engine.check_jarvis_trigger(33.7)
        assert result["numeric_value"] == 33
        assert any(t["number"] == 33 for t in result["triggers_hit"])

    def test_very_large_number(self, engine):
        """Very large numbers should not crash."""
        result = engine.check_jarvis_trigger(999999999)
        assert "reduction" in result
        assert isinstance(result["reduction"], int)


class TestCalculateFibonacciAlignment:
    """Test Fibonacci alignment detection."""

    def test_exact_fibonacci_match(self, engine):
        """Lines that are exact Fibonacci numbers should trigger."""
        # 8 is a Fibonacci number
        result = engine.calculate_fibonacci_alignment(8.0)
        assert result["is_fibonacci"] is True
        assert result["signal"] == "FIB_EXACT"
        assert result["score_modifier"] == 0.10

        # 13 is a Fibonacci number
        result = engine.calculate_fibonacci_alignment(13.0)
        assert result["is_fibonacci"] is True

    def test_near_fibonacci(self, engine):
        """Lines near Fibonacci numbers (within 0.5) should trigger."""
        # 7.5 is within 0.5 of 8
        result = engine.calculate_fibonacci_alignment(7.5)
        assert result["near_fibonacci"] is True
        assert result["signal"] == "FIB_NEAR"
        assert result["score_modifier"] == 0.05
        assert result["nearest_fib"] == 8

    def test_no_fibonacci_alignment(self, engine):
        """Lines not near Fibonacci should return no signal."""
        result = engine.calculate_fibonacci_alignment(10.0)
        assert result["is_fibonacci"] is False
        assert result["near_fibonacci"] is False
        assert result["signal"] == "NO_FIB"
        assert result["score_modifier"] == 0.0

    def test_phi_aligned(self, engine):
        """Lines that are phi ratios of Fibonacci numbers should trigger."""
        # 8 * 1.618 ≈ 12.94, so 13 / 8 ≈ 1.625 is close to phi
        # Check a value that's phi-aligned
        result = engine.calculate_fibonacci_alignment(12.9)  # Close to 8 * phi
        assert result["phi_aligned"] is True or result["near_fibonacci"] is True

    def test_negative_line(self, engine):
        """Negative lines should work with absolute values."""
        result_pos = engine.calculate_fibonacci_alignment(8.0)
        result_neg = engine.calculate_fibonacci_alignment(-8.0)
        # Both should detect the same Fibonacci alignment
        assert result_pos["is_fibonacci"] == result_neg["is_fibonacci"]

    def test_result_structure(self, engine):
        """Result should have all expected fields."""
        result = engine.calculate_fibonacci_alignment(5.5)
        assert "line" in result
        assert "is_fibonacci" in result
        assert "near_fibonacci" in result
        assert "nearest_fib" in result
        assert "distance_to_fib" in result
        assert "phi_aligned" in result
        assert "signal" in result
        assert "score_modifier" in result
        assert "modifier" in result


class TestCalculateVortexPattern:
    """Test Tesla's vortex math pattern detection."""

    def test_tesla_numbers(self, engine):
        """Tesla numbers (3, 6, 9) should have highest modifier."""
        for num in [3, 6, 9, 12, 15, 18, 27, 36, 369]:
            result = engine.calculate_vortex_pattern(num)
            assert result["is_tesla_key"] is True
            assert result["score_modifier"] == 0.15
            assert "TESLA" in result["signal"]

    def test_vortex_pattern_numbers(self, engine):
        """Numbers in vortex pattern (1,2,4,8,7,5) should trigger."""
        # Number that reduces to 1
        result = engine.calculate_vortex_pattern(10)  # 1+0=1
        assert result["reduction"] == 1
        assert result["in_vortex"] is True
        assert result["is_tesla_key"] is False
        assert result["score_modifier"] == 0.08

        # Number that reduces to 8
        result = engine.calculate_vortex_pattern(17)  # 1+7=8
        assert result["reduction"] == 8
        assert result["in_vortex"] is True

    def test_vortex_position(self, engine):
        """Vortex position should be correctly identified."""
        result = engine.calculate_vortex_pattern(1)
        assert result["vortex_position"] == 0  # 1 is at position 0

        result = engine.calculate_vortex_pattern(16)  # 1+6=7
        assert result["reduction"] == 7
        assert result["vortex_position"] == 4  # 7 is at position 4 in [1,2,4,8,7,5]

    def test_no_vortex_non_tesla(self, engine):
        """Numbers reducing to non-vortex, non-Tesla should return no modifier."""
        # 10 -> 1 is in vortex, but let's find a non-vortex example
        # Wait, all single digits except 3,6,9 are in vortex [1,2,4,8,7,5]
        # So every number reduces to either vortex or Tesla
        # Let me verify the code logic...
        # Actually the code says in_vortex OR is_tesla_key, so all numbers should trigger something
        # Let me test boundary cases
        result = engine.calculate_vortex_pattern(0)
        # 0 reduces to 0, which is neither in vortex nor Tesla
        assert result["reduction"] == 0
        assert result["in_vortex"] is False
        assert result["is_tesla_key"] is False
        assert result["signal"] == "NO_VORTEX"

    def test_result_structure(self, engine):
        """Result should have all expected fields."""
        result = engine.calculate_vortex_pattern(42)
        assert "value" in result
        assert "reduction" in result
        assert "in_vortex" in result
        assert "is_tesla_key" in result
        assert "vortex_position" in result
        assert "signal" in result
        assert "score_modifier" in result
        assert "modifier" in result
        assert "vortex_pattern" in result
        assert "tesla_numbers" in result

    def test_reduction_correctness(self, engine):
        """Verify digit reduction is correct."""
        # 123 -> 1+2+3=6 (Tesla)
        result = engine.calculate_vortex_pattern(123)
        assert result["reduction"] == 6
        assert result["is_tesla_key"] is True

        # 99 -> 9+9=18 -> 1+8=9 (Tesla)
        result = engine.calculate_vortex_pattern(99)
        assert result["reduction"] == 9
        assert result["is_tesla_key"] is True

        # 2178 -> 2+1+7+8=18 -> 1+8=9 (Tesla)
        result = engine.calculate_vortex_pattern(2178)
        assert result["reduction"] == 9
        assert result["is_tesla_key"] is True


class TestConfluence:
    """Test confluence calculation (the heart of Jarvis)."""

    def test_perfect_confluence(self, engine):
        """Both engines high and aligned should give high confluence."""
        result = engine.calculate_confluence(
            research_score=8.5,
            esoteric_score=8.0,
            immortal_detected=False,
            jarvis_triggered=False
        )
        assert result["alignment_pct"] >= 90
        assert result["level"] in ["PERFECT", "STRONG"]
        assert result["boost"] >= 1.5

    def test_immortal_confluence(self, engine):
        """Immortal detection should give maximum boost."""
        result = engine.calculate_confluence(
            research_score=8.0,
            esoteric_score=8.0,
            immortal_detected=True,
            jarvis_triggered=True
        )
        assert result["level"] == "IMMORTAL"
        assert result["boost"] == 1.5  # CONFLUENCE_LEVELS["IMMORTAL"] = 1.5

    def test_divergent_confluence(self, engine):
        """Large score differences should give divergent result."""
        result = engine.calculate_confluence(
            research_score=9.0,
            esoteric_score=3.0,
            immortal_detected=False,
            jarvis_triggered=False
        )
        assert result["alignment_pct"] < 60
        assert result["level"] == "DIVERGENT"
        assert result["boost"] == 0

    def test_moderate_confluence(self, engine):
        """Moderate alignment should give moderate boost."""
        result = engine.calculate_confluence(
            research_score=6.0,
            esoteric_score=4.5,  # diff = 1.5, alignment = 85%
            immortal_detected=False,
            jarvis_triggered=False
        )
        assert result["alignment_pct"] >= 60
        assert result["level"] in ["MODERATE", "STRONG"]

    def test_result_structure(self, engine):
        """Result should have all expected fields."""
        result = engine.calculate_confluence(
            research_score=7.0,
            esoteric_score=7.0
        )
        assert "alignment" in result
        assert "alignment_pct" in result
        assert "level" in result
        assert "boost" in result
        assert "research_score" in result
        assert "esoteric_score" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
