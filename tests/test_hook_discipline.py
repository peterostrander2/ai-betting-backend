"""
Tests for Hook Discipline Signal - Key Number Management
========================================================

v20.3 - Tests verify:
1. NFL bad hooks get correct penalties
2. Key number bonuses work correctly
3. Adjustments are bounded by caps
4. NBA hooks have less impact
5. Non-spread bets return zero adjustment
"""

import pytest
from signals.hook_discipline import (
    analyze_hook_discipline,
    get_hook_adjustment,
    HookAnalysis,
    NFL_BAD_HOOKS,
    NFL_KEY_NUMBER_BONUS,
    HOOK_PENALTY_CAP,
    HOOK_BONUS_CAP,
)


class TestNFLBadHooks:
    """Test NFL bad hook penalties."""

    def test_worst_hook_3_5(self):
        """3.5 is the worst hook in football - crosses 3."""
        analysis = analyze_hook_discipline(-3.5, "NFL", "favorite", "spread")

        assert analysis.is_bad_hook is True
        assert analysis.adjustment == -0.25  # Codex refinement: capped at -0.25
        assert "WORST HOOK" in analysis.warnings[0]
        assert "15%" in analysis.warnings[0]  # 3 occurs in ~15% of games

    def test_second_worst_hook_7_5(self):
        """7.5 is the second worst hook - crosses 7."""
        analysis = analyze_hook_discipline(-7.5, "NFL", "favorite", "spread")

        assert analysis.is_bad_hook is True
        assert analysis.adjustment == -0.20  # Adjusted per Codex
        assert "7" in analysis.warnings[0]

    def test_bad_hook_6_5(self):
        """6.5 crosses 7."""
        analysis = analyze_hook_discipline(-6.5, "NFL", "favorite", "spread")

        assert analysis.is_bad_hook is True
        assert analysis.adjustment == -0.15  # Adjusted per Codex

    def test_bad_hook_10_5(self):
        """10.5 crosses 10."""
        analysis = analyze_hook_discipline(-10.5, "NFL", "favorite", "spread")

        assert analysis.is_bad_hook is True
        assert analysis.adjustment == -0.10  # Adjusted per Codex


class TestNFLKeyNumbers:
    """Test NFL key number bonuses for favorites."""

    def test_key_number_3_favorite(self):
        """On 3 is great for favorites - most common margin."""
        analysis = analyze_hook_discipline(-3.0, "NFL", "favorite", "spread")

        assert analysis.is_key_number is True
        assert analysis.adjustment == 0.15  # Max bonus
        assert "Key number bonus" in analysis.reasons[0]

    def test_key_number_7_favorite(self):
        """On 7 is good for favorites - second most common margin."""
        analysis = analyze_hook_discipline(-7.0, "NFL", "favorite", "spread")

        assert analysis.is_key_number is True
        assert analysis.adjustment == 0.10

    def test_key_number_10_favorite(self):
        """On 10 is okay for favorites."""
        analysis = analyze_hook_discipline(-10.0, "NFL", "favorite", "spread")

        assert analysis.is_key_number is True
        assert analysis.adjustment == 0.05

    def test_key_number_underdog_negative(self):
        """Underdog at key number gets slight negative - hook working against."""
        analysis = analyze_hook_discipline(-3.0, "NFL", "underdog", "spread")

        assert analysis.adjustment == -0.05
        assert "Underdog at key number" in analysis.reasons[0]


class TestBounds:
    """Test that adjustments are properly bounded."""

    def test_penalty_cap_enforced(self):
        """Penalties should not exceed HOOK_PENALTY_CAP."""
        for line, penalty in NFL_BAD_HOOKS.items():
            analysis = analyze_hook_discipline(line, "NFL", "favorite", "spread")
            assert analysis.adjustment >= HOOK_PENALTY_CAP

    def test_bonus_cap_enforced(self):
        """Bonuses should not exceed HOOK_BONUS_CAP."""
        for line, bonus in NFL_KEY_NUMBER_BONUS.items():
            analysis = analyze_hook_discipline(-float(line), "NFL", "favorite", "spread")
            assert analysis.adjustment <= HOOK_BONUS_CAP


class TestNBAHooks:
    """Test NBA has less hook impact than NFL."""

    def test_nba_hook_5_5(self):
        """NBA hook at 5.5 has less impact than NFL."""
        analysis = analyze_hook_discipline(-5.5, "NBA", "favorite", "spread")

        assert analysis.is_bad_hook is True
        assert analysis.adjustment == -0.10  # Less than NFL's worst

    def test_nba_hook_7_5(self):
        """NBA hook at 7.5 has less impact than NFL."""
        analysis = analyze_hook_discipline(-7.5, "NBA", "favorite", "spread")

        assert analysis.is_bad_hook is True
        assert analysis.adjustment == -0.10  # Less than NFL's 7.5


class TestNonSpreadBets:
    """Test that non-spread bets return zero adjustment."""

    def test_totals_no_adjustment(self):
        """Totals should have no hook adjustment."""
        analysis = analyze_hook_discipline(220.5, "NFL", "over", "total")

        assert analysis.adjustment == 0.0
        assert "N/A" in analysis.reasons[0]

    def test_props_no_adjustment(self):
        """Props should have no hook adjustment."""
        analysis = analyze_hook_discipline(25.5, "NBA", "over", "prop")

        assert analysis.adjustment == 0.0


class TestNeutralLines:
    """Test lines that are neither bad hooks nor key numbers."""

    def test_neutral_nfl_line(self):
        """A neutral line like -5.5 should have no adjustment."""
        analysis = analyze_hook_discipline(-5.5, "NFL", "favorite", "spread")

        assert analysis.is_bad_hook is False
        assert analysis.is_key_number is False
        assert analysis.adjustment == 0.0

    def test_neutral_nfl_4_5(self):
        """4.5 is not a key number or bad hook."""
        analysis = analyze_hook_discipline(-4.5, "NFL", "favorite", "spread")

        assert analysis.adjustment == 0.0


class TestConvenienceFunction:
    """Test the get_hook_adjustment convenience function."""

    def test_returns_tuple(self):
        """get_hook_adjustment should return (adjustment, reasons) tuple."""
        adj, reasons = get_hook_adjustment(-3.5, "NFL", "favorite", "spread")

        assert isinstance(adj, float)
        assert isinstance(reasons, list)
        assert adj == -0.25  # Codex refinement: capped at -0.25

    def test_reasons_populated(self):
        """Reasons should explain the adjustment."""
        adj, reasons = get_hook_adjustment(-7.0, "NFL", "favorite", "spread")

        assert len(reasons) > 0
        assert "Key number" in reasons[0] or "bonus" in reasons[0]


class TestOtherSports:
    """Test that other sports have no key number impact."""

    def test_mlb_no_impact(self):
        """MLB spreads don't have key numbers."""
        analysis = analyze_hook_discipline(-1.5, "MLB", "favorite", "spread")

        assert analysis.adjustment == 0.0
        assert "N/A" in analysis.reasons[0]

    def test_ncaab_no_impact(self):
        """NCAAB uses same as NBA (minimal impact)."""
        analysis = analyze_hook_discipline(-3.5, "NCAAB", "favorite", "spread")

        # NCAAB not explicitly handled, falls to "other sports"
        assert analysis.adjustment == 0.0


class TestHookAnalysisDataclass:
    """Test HookAnalysis dataclass fields."""

    def test_all_fields_present(self):
        """HookAnalysis should have all required fields."""
        analysis = analyze_hook_discipline(-3.5, "NFL", "favorite", "spread")

        assert hasattr(analysis, "adjustment")
        assert hasattr(analysis, "is_bad_hook")
        assert hasattr(analysis, "is_key_number")
        assert hasattr(analysis, "hook_value")
        assert hasattr(analysis, "reasons")
        assert hasattr(analysis, "warnings")

    def test_hook_value_is_absolute(self):
        """hook_value should be the absolute value of the line."""
        analysis = analyze_hook_discipline(-7.5, "NFL", "favorite", "spread")

        assert analysis.hook_value == 7.5  # Not -7.5
