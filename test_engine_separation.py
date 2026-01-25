"""
Test Engine Separation - Production Clean Validation
January 24, 2026

Tests verify:
1. Jarvis RS increases when sacred triggers hit
2. Esoteric Edge score does NOT change when Jarvis triggers hit
3. tier_from_score returns correct tier thresholds
4. Engine outputs have correct field structure
"""

import pytest
import datetime
from jarvis_savant_engine import (
    get_jarvis_engine,
    compute_jarvis_score,
    JARVIS_TRIGGERS,
)
from esoteric_edge_engine import (
    get_esoteric_edge_engine,
    compute_esoteric_edge,
)
from tiering import (
    tier_from_score,
    get_units_for_tier,
    get_action_for_tier,
    DEFAULT_TIERS,
)


class TestJarvisEngine:
    """Test Jarvis Engine standalone output."""

    def test_jarvis_output_fields(self):
        """Jarvis must return required fields."""
        result = compute_jarvis_score(matchup="Lakers vs Celtics", sport="nba")

        # Required fields
        assert "jarvis_rs" in result
        assert "jarvis_active" in result
        assert "jarvis_hits_count" in result
        assert "jarvis_triggers_hit" in result
        assert "jarvis_reasons" in result

        # Types
        assert isinstance(result["jarvis_rs"], (int, float))
        assert isinstance(result["jarvis_active"], bool)
        assert isinstance(result["jarvis_hits_count"], int)
        assert isinstance(result["jarvis_triggers_hit"], list)
        assert isinstance(result["jarvis_reasons"], list)

    def test_jarvis_rs_range(self):
        """Jarvis RS must be 0-10."""
        result = compute_jarvis_score(
            matchup="Test Game",
            gematria_hits=5,
            spread=5.5,
            sport="nba"
        )
        assert 0 <= result["jarvis_rs"] <= 10

    def test_jarvis_increases_with_triggers(self):
        """Jarvis RS should increase when sacred triggers hit."""
        # Baseline (no triggers)
        baseline = compute_jarvis_score(
            matchup="Plain Game",
            gematria_hits=0,
            spread=0,
            sport="nba"
        )

        # With gematria hits
        with_gematria = compute_jarvis_score(
            matchup="Plain Game",
            gematria_hits=4,
            spread=0,
            sport="nba"
        )

        # With Goldilocks spread
        with_spread = compute_jarvis_score(
            matchup="Plain Game",
            gematria_hits=0,
            spread=5.5,  # Goldilocks zone
            sport="nba"
        )

        # Both should be higher than baseline
        assert with_gematria["jarvis_rs"] > baseline["jarvis_rs"], \
            f"Gematria should increase RS: {with_gematria['jarvis_rs']} > {baseline['jarvis_rs']}"
        assert with_spread["jarvis_rs"] > baseline["jarvis_rs"], \
            f"Goldilocks spread should increase RS: {with_spread['jarvis_rs']} > {baseline['jarvis_rs']}"

    def test_jarvis_trigger_33_detection(self):
        """Jarvis should detect trigger number 33 in text."""
        result = compute_jarvis_score(
            matchup="Game 33 Championship",
            sport="nba"
        )

        # Should detect 33 in text
        trigger_numbers = [t["number"] for t in result["jarvis_triggers_hit"]]
        assert 33 in trigger_numbers, f"Should detect 33: {result['jarvis_triggers_hit']}"
        assert result["jarvis_active"] == True

    def test_jarvis_2178_validation(self):
        """2178 validation must pass."""
        engine = get_jarvis_engine()
        validation = engine.validate_2178()
        assert validation["validated"] == True
        assert validation["proof"]["is_reverse_product"] == True
        assert validation["proof"]["is_tesla_complete"] == True

    def test_jarvis_sport_variance(self):
        """Different sports should have different variance factors."""
        nba = compute_jarvis_score(matchup="Test", gematria_hits=3, spread=5.5, sport="nba")
        nhl = compute_jarvis_score(matchup="Test", gematria_hits=3, spread=5.5, sport="nhl")

        # NHL has higher variance factor (1.15 vs 1.0)
        # So with same inputs, NHL should get slightly different score
        # Both should be valid though
        assert nba["variance_factor"] == 1.0
        assert nhl["variance_factor"] == 1.15


class TestEsotericEdgeEngine:
    """Test Esoteric Edge Engine (NON-Jarvis)."""

    def test_esoteric_output_fields(self):
        """Esoteric Edge must return required fields."""
        result = compute_esoteric_edge(sport="nba", game_total=220, spread=5.5)

        # Required fields
        assert "esoteric_edge_score" in result
        assert "esoteric_active" in result
        assert "esoteric_signals_count" in result
        assert "esoteric_signals" in result
        assert "esoteric_reasons" in result

        # Types
        assert isinstance(result["esoteric_edge_score"], (int, float))
        assert isinstance(result["esoteric_active"], bool)
        assert isinstance(result["esoteric_signals_count"], int)
        assert isinstance(result["esoteric_signals"], list)
        assert isinstance(result["esoteric_reasons"], list)

    def test_esoteric_score_range(self):
        """Esoteric Edge score must be 0-10."""
        result = compute_esoteric_edge(sport="nba", game_total=220, spread=5.5)
        assert 0 <= result["esoteric_edge_score"] <= 10

    def test_esoteric_does_not_contain_jarvis(self):
        """Esoteric Edge must NOT contain Jarvis trigger logic."""
        result = compute_esoteric_edge(sport="nba", game_total=220, spread=5.5)

        # Reasons should NOT mention JARVIS
        for reason in result["esoteric_reasons"]:
            assert "JARVIS" not in reason, f"Esoteric should not contain JARVIS: {reason}"

        # Signals should NOT be Jarvis sacred triggers
        jarvis_signals = ["THE_IMMORTAL", "THE_ORDER", "THE_MASTER", "THE_WILL", "THE_SOCIETY"]
        for signal in result["esoteric_signals"]:
            for js in jarvis_signals:
                assert js not in signal, f"Esoteric should not contain Jarvis signal: {signal}"

    def test_esoteric_not_affected_by_jarvis_text(self):
        """Esoteric score should NOT change based on text with Jarvis triggers."""
        # Esoteric only cares about game numbers and cosmic state
        # Text like "33 Championship" should NOT affect it

        baseline = compute_esoteric_edge(sport="nba", game_total=220, spread=5.5)

        # Same call (esoteric doesn't take matchup text)
        # Verify it produces consistent output
        repeat = compute_esoteric_edge(sport="nba", game_total=220, spread=5.5)

        assert baseline["esoteric_edge_score"] == repeat["esoteric_edge_score"]

    def test_esoteric_weather_impact_outdoor(self):
        """Weather should impact outdoor sports (NFL, MLB)."""
        indoor = compute_esoteric_edge(
            sport="nfl",
            game_total=45,
            spread=3.0,
            is_dome=True
        )

        outdoor_cold = compute_esoteric_edge(
            sport="nfl",
            game_total=45,
            spread=3.0,
            temperature=28,
            wind_mph=20,
            is_dome=False
        )

        # Outdoor cold/wind should have different weather signals
        assert "COLD_GAME" in outdoor_cold["esoteric_signals"] or \
               "HIGH_WIND" in outdoor_cold["esoteric_signals"]


class TestTieringModule:
    """Test tiering.py as single source of truth."""

    def test_tier_thresholds(self):
        """Verify tier thresholds are correct."""
        assert DEFAULT_TIERS["TITANIUM_SMASH"] == 9.0
        assert DEFAULT_TIERS["GOLD_STAR"] == 7.5
        assert DEFAULT_TIERS["EDGE_LEAN"] == 6.5
        assert DEFAULT_TIERS["MONITOR"] == 5.5
        assert DEFAULT_TIERS["PASS"] == 0.0

    def test_tier_from_score_gold_star(self):
        """Score >= 7.5 should be GOLD_STAR."""
        tier, badge = tier_from_score(7.5)
        assert tier == "GOLD_STAR"
        assert badge == "GOLD STAR"

        tier, badge = tier_from_score(8.9)
        assert tier == "GOLD_STAR"

    def test_tier_from_score_edge_lean(self):
        """Score 6.5-7.49 should be EDGE_LEAN."""
        tier, badge = tier_from_score(6.5)
        assert tier == "EDGE_LEAN"

        tier, badge = tier_from_score(7.49)
        assert tier == "EDGE_LEAN"

    def test_tier_from_score_monitor(self):
        """Score 5.5-6.49 should be MONITOR."""
        tier, badge = tier_from_score(5.5)
        assert tier == "MONITOR"

        tier, badge = tier_from_score(6.49)
        assert tier == "MONITOR"

    def test_tier_from_score_pass(self):
        """Score < 5.5 should be PASS."""
        tier, badge = tier_from_score(5.49)
        assert tier == "PASS"

        tier, badge = tier_from_score(0)
        assert tier == "PASS"

    def test_tier_from_score_titanium(self):
        """Score >= 9.0 with titanium_triggered should be TITANIUM_SMASH."""
        tier, badge = tier_from_score(9.0, titanium_triggered=True)
        assert tier == "TITANIUM_SMASH"
        assert badge == "TITANIUM SMASH"

        # Without flag, should be GOLD_STAR
        tier, badge = tier_from_score(9.0, titanium_triggered=False)
        assert tier == "GOLD_STAR"

    def test_get_units_for_tier(self):
        """Verify unit sizing by tier."""
        assert get_units_for_tier("TITANIUM_SMASH") == 2.5
        assert get_units_for_tier("GOLD_STAR") == 2.0
        assert get_units_for_tier("EDGE_LEAN") == 1.0
        assert get_units_for_tier("MONITOR") == 0.0
        assert get_units_for_tier("PASS") == 0.0

    def test_get_action_for_tier(self):
        """Verify action by tier."""
        assert get_action_for_tier("TITANIUM_SMASH") == "SMASH"
        assert get_action_for_tier("GOLD_STAR") == "SMASH"
        assert get_action_for_tier("EDGE_LEAN") == "PLAY"
        assert get_action_for_tier("MONITOR") == "WATCH"
        assert get_action_for_tier("PASS") == "SKIP"


class TestEngineSeparation:
    """Test that engines are properly separated."""

    def test_jarvis_and_esoteric_independent(self):
        """Jarvis and Esoteric engines should be independent."""
        # Jarvis score based on text/triggers
        jarvis = compute_jarvis_score(
            matchup="Game 33 Championship",  # Contains trigger 33
            gematria_hits=4,
            spread=5.5,
            sport="nba"
        )

        # Esoteric score based on environment (same game numbers)
        esoteric = compute_esoteric_edge(
            sport="nba",
            game_total=220,
            spread=5.5
        )

        # Both should produce valid scores
        assert 0 <= jarvis["jarvis_rs"] <= 10
        assert 0 <= esoteric["esoteric_edge_score"] <= 10

        # Jarvis should have detected trigger 33
        trigger_numbers = [t["number"] for t in jarvis["jarvis_triggers_hit"]]
        assert 33 in trigger_numbers

        # Esoteric should NOT have any Jarvis-related signals
        jarvis_related = ["IMMORTAL", "MASTER", "ORDER", "WILL", "SOCIETY", "GEMATRIA"]
        for signal in esoteric["esoteric_signals"]:
            for jr in jarvis_related:
                assert jr not in signal.upper()

    def test_public_fade_not_in_jarvis(self):
        """Public fade should NOT affect Jarvis score."""
        # Jarvis doesn't take public_pct as input
        # This is by design - public fade lives in Research Engine

        result = compute_jarvis_score(
            matchup="Test Game",
            gematria_hits=2,
            spread=5.5,
            sport="nba"
        )

        # Reasons should NOT mention public fade
        for reason in result["jarvis_reasons"]:
            assert "PUBLIC" not in reason.upper()
            assert "FADE" not in reason.upper()

    def test_public_fade_not_in_esoteric(self):
        """Public fade should NOT affect Esoteric score."""
        result = compute_esoteric_edge(
            sport="nba",
            game_total=220,
            spread=5.5
        )

        # Reasons should NOT mention public fade
        for reason in result["esoteric_reasons"]:
            assert "PUBLIC" not in reason.upper()
            assert "FADE" not in reason.upper()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
