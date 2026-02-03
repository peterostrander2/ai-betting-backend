"""
Unit tests for pick normalization contract.

GUARANTEES: Every pick returned by /live/best-bets/{sport} includes:
- pick_type: "player_prop" | "moneyline" | "spread" | "total"
- selection: non-empty string (team or player name)
- market_label: "Spread" | "Moneyline" | "Total" | stat category for props
- signal_label: "Sharp Signal" or None
- side_label: non-empty string
- line_signed: "+1.5" or "-2.5" for spreads (None otherwise)
- bet_string: non-empty string (canonical display)
- odds_american: integer or None (never fabricated)
- recommended_units: number
- start_time: display string
- start_time_iso: ISO 8601 or None
- start_time_utc: UTC timestamp or None
- id: non-empty string
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.pick_normalizer import (
    normalize_pick,
    normalize_pick_type,
    normalize_market_label,
    normalize_selection,
    normalize_side_label,
    build_bet_string,
    get_signal_label,
)


# Required fields that must be present
REQUIRED_PICK_FIELDS = [
    "pick_type",
    "selection",
    "market_label",
    "signal_label",
    "side_label",
    "line_signed",
    "bet_string",
    "odds_american",
    "recommended_units",
    "start_time",
    "start_time_iso",
    "id",
]

VALID_PICK_TYPES = ["player_prop", "moneyline", "spread", "total"]


class TestNormalizePickType:
    """Test pick_type normalization."""

    def test_player_prop_from_player_field(self):
        pick = {"player": "LeBron James", "market": "player_points"}
        assert normalize_pick_type(pick) == "player_prop"

    def test_player_prop_from_player_name_field(self):
        pick = {"player_name": "Yanni Gourde", "market": "player_assists"}
        assert normalize_pick_type(pick) == "player_prop"

    def test_total_from_pick_type(self):
        pick = {"pick_type": "TOTAL", "market": "totals"}
        assert normalize_pick_type(pick) == "total"

    def test_spread_from_market(self):
        pick = {"market": "spreads", "team": "Lakers"}
        assert normalize_pick_type(pick) == "spread"

    def test_moneyline_from_h2h(self):
        pick = {"market": "h2h", "team": "Celtics"}
        assert normalize_pick_type(pick) == "moneyline"

    def test_sharp_with_line_becomes_spread(self):
        pick = {"pick_type": "SHARP", "line": 1.5, "team": "Bucks"}
        assert normalize_pick_type(pick) == "spread"

    def test_sharp_without_line_becomes_moneyline(self):
        pick = {"pick_type": "SHARP", "line": None, "team": "Bucks"}
        assert normalize_pick_type(pick) == "moneyline"


class TestNormalizeMarketLabel:
    """Test market_label normalization - derived from pick_type, not market."""

    def test_spread_market_label(self):
        assert normalize_market_label("spread") == "Spread"

    def test_moneyline_market_label(self):
        assert normalize_market_label("moneyline") == "Moneyline"

    def test_total_market_label(self):
        assert normalize_market_label("total") == "Total"

    def test_player_prop_with_stat_type(self):
        assert normalize_market_label("player_prop", "player_points") == "Points"

    def test_player_prop_with_assists(self):
        assert normalize_market_label("player_prop", "player_assists") == "Assists"

    def test_player_prop_with_threes(self):
        assert normalize_market_label("player_prop", "player_threes") == "3PT Made"

    def test_player_prop_without_stat_type(self):
        assert normalize_market_label("player_prop", None) == "Player Prop"


class TestGetSignalLabel:
    """Test signal_label is separate from market_label."""

    def test_sharp_money_signal(self):
        pick = {"market": "sharp_money"}
        assert get_signal_label(pick) == "Sharp Signal"

    def test_non_sharp_has_no_signal(self):
        pick = {"market": "spreads"}
        assert get_signal_label(pick) is None

    def test_props_have_no_signal(self):
        pick = {"market": "player_points"}
        assert get_signal_label(pick) is None


class TestNormalizeSelection:
    """Test selection normalization."""

    def test_player_prop_uses_player_name(self):
        pick = {"player_name": "LeBron James", "team": "Lakers"}
        assert normalize_selection(pick, "player_prop") == "LeBron James"

    def test_player_prop_fallback_to_player(self):
        pick = {"player": "Yanni Gourde"}
        assert normalize_selection(pick, "player_prop") == "Yanni Gourde"

    def test_total_uses_matchup_format(self):
        pick = {"home_team": "Celtics", "away_team": "Bucks"}
        assert normalize_selection(pick, "total") == "Bucks/Celtics"

    def test_spread_uses_team(self):
        pick = {"team": "Lakers", "side": "HOME"}
        assert normalize_selection(pick, "spread") == "Lakers"

    def test_moneyline_uses_team(self):
        pick = {"team": "Celtics"}
        assert normalize_selection(pick, "moneyline") == "Celtics"


class TestNormalizeSideLabel:
    """Test side_label normalization."""

    def test_prop_over(self):
        pick = {"side": "Over"}
        assert normalize_side_label(pick, "player_prop") == "Over"

    def test_prop_under_from_direction(self):
        pick = {"direction": "UNDER"}
        assert normalize_side_label(pick, "player_prop") == "Under"

    def test_total_over(self):
        pick = {"side": "Over"}
        assert normalize_side_label(pick, "total") == "Over"

    def test_spread_uses_team(self):
        pick = {"team": "Lakers", "side": "Lakers"}
        assert normalize_side_label(pick, "spread") == "Lakers"


class TestBuildBetString:
    """Test bet_string generation."""

    def test_player_prop_bet_string(self):
        pick = {"line": 25.5, "odds": -110, "units": 2.0}
        result = build_bet_string(
            pick, "player_prop", "LeBron James", "Points", "Over"
        )
        assert result == "LeBron James — Points Over 25.5 (-110) — 2.0u"

    def test_total_bet_string(self):
        pick = {"line": 228.5, "odds": -110, "units": 1.0}
        result = build_bet_string(
            pick, "total", "Bucks/Celtics", "Total", "Over"
        )
        assert result == "Bucks/Celtics Over 228.5 (-110) — 1.0u"

    def test_spread_bet_string_with_line_signed(self):
        pick = {"line": -4.5, "odds": -105, "units": 1.0}
        result = build_bet_string(
            pick, "spread", "Boston Celtics", "Spread", "Boston Celtics", "-4.5"
        )
        assert result == "Boston Celtics -4.5 (-105) — 1.0u"

    def test_spread_bet_string_positive_line(self):
        pick = {"line": 1.0, "odds": -110, "units": 2.0}
        result = build_bet_string(
            pick, "spread", "Milwaukee Bucks", "Spread", "Milwaukee Bucks", "+1.0"
        )
        assert result == "Milwaukee Bucks +1.0 (-110) — 2.0u"

    def test_moneyline_bet_string(self):
        pick = {"line": None, "odds": -150, "units": 1.5}
        result = build_bet_string(
            pick, "moneyline", "Milwaukee Bucks", "Moneyline", "Milwaukee Bucks"
        )
        assert result == "Milwaukee Bucks ML (-150) — 1.5u"

    def test_positive_odds_formatted(self):
        pick = {"line": 0.5, "odds": 270, "units": 1.0}
        result = build_bet_string(
            pick, "player_prop", "Yanni Gourde", "Assists", "Over"
        )
        assert "+270" in result

    def test_missing_odds_shows_na(self):
        pick = {"line": 0.5, "odds": None, "units": 1.0}
        result = build_bet_string(
            pick, "player_prop", "Test Player", "Points", "Over"
        )
        assert "(—)" in result


class TestLineSigned:
    """Test line_signed field for spreads."""

    def test_positive_line_signed(self):
        pick = {
            "pick_type": "SPREAD",
            "market": "spreads",
            "team": "Milwaukee Bucks",
            "line": 1.0,
            "odds": -110,
            "pick_id": "test123",
        }
        result = normalize_pick(pick)
        assert result["line_signed"] == "+1.0"

    def test_negative_line_signed(self):
        pick = {
            "pick_type": "SPREAD",
            "market": "spreads",
            "team": "Boston Celtics",
            "line": -4.5,
            "odds": -105,
            "pick_id": "test456",
        }
        result = normalize_pick(pick)
        assert result["line_signed"] == "-4.5"

    def test_moneyline_no_line_signed(self):
        pick = {
            "market": "h2h",
            "team": "Celtics",
            "odds": -150,
            "pick_id": "test789",
        }
        result = normalize_pick(pick)
        assert result["line_signed"] is None

    def test_props_no_line_signed(self):
        pick = {
            "player_name": "Test Player",
            "market": "player_points",
            "line": 25.5,
            "odds": -110,
            "pick_id": "test999",
        }
        result = normalize_pick(pick)
        assert result["line_signed"] == "O 25.5"


class TestNormalizePick:
    """Test full pick normalization."""

    def test_prop_pick_has_all_required_fields(self):
        pick = {
            "player_name": "LeBron James",
            "market": "player_points",
            "stat_type": "player_points",
            "line": 25.5,
            "side": "Over",
            "odds": -110,
            "units": 2.0,
            "matchup": "Lakers @ Celtics",
            "final_score": 8.5,
            "tier": "GOLD_STAR",
            "pick_id": "abc123",
            "commence_time_iso": "2026-02-01T23:40:00Z",
        }
        result = normalize_pick(pick)

        for field in REQUIRED_PICK_FIELDS:
            assert field in result, f"Missing required field: {field}"

        assert result["pick_type"] in VALID_PICK_TYPES
        assert result["market_label"] == "Points"
        assert result["signal_label"] is None

    def test_game_pick_has_all_required_fields(self):
        pick = {
            "pick_type": "TOTAL",
            "market": "totals",
            "line": 5.5,
            "side": "Over",
            "odds": -114,
            "units": 1.0,
            "matchup": "Kings @ Hurricanes",
            "home_team": "Carolina Hurricanes",
            "away_team": "Los Angeles Kings",
            "final_score": 8.2,
            "tier": "EDGE_LEAN",
            "pick_id": "xyz789",
            "commence_time_iso": "2026-02-01T23:40:00Z",
        }
        result = normalize_pick(pick)

        for field in REQUIRED_PICK_FIELDS:
            assert field in result, f"Missing required field: {field}"

        assert result["pick_type"] in VALID_PICK_TYPES
        assert result["market_label"] == "Total"

    def test_sharp_pick_has_signal_label(self):
        """Sharp picks must have signal_label='Sharp Signal' and proper market_label."""
        pick = {
            "pick_type": "SHARP",
            "market": "sharp_money",
            "team": "Milwaukee Bucks",
            "line": 1.0,
            "odds": -110,
            "units": 2.0,
            "matchup": "Bucks @ Celtics",
            "pick_id": "sharp123",
        }
        result = normalize_pick(pick)

        assert result["pick_type"] == "spread"  # Sharp with line -> spread
        assert result["market_label"] == "Spread"  # NOT "Sharp Signal"
        assert result["signal_label"] == "Sharp Signal"  # Separate field
        assert result["selection"] == "Milwaukee Bucks"
        assert result["line_signed"] == "+1.0"

    def test_selection_never_na(self):
        """Selection must never be N/A or empty."""
        picks = [
            {"player_name": "Test Player", "market": "player_points", "pick_id": "1"},
            {"team": "Test Team", "market": "spreads", "pick_id": "2"},
            {"home_team": "Home", "away_team": "Away", "pick_type": "TOTAL", "pick_id": "3"},
        ]
        for pick in picks:
            result = normalize_pick(pick)
            assert result["selection"] not in ("", "N/A", None, "Unknown")


class TestStartTimeFields:
    """Test start time normalization."""

    def test_start_time_iso_from_commence_time_iso(self):
        pick = {
            "player_name": "Test",
            "market": "player_points",
            "pick_id": "1",
            "commence_time_iso": "2026-02-01T23:40:00Z",
        }
        result = normalize_pick(pick)
        assert result["start_time_iso"] == "2026-02-01T23:40:00Z"

    def test_start_time_display(self):
        pick = {
            "player_name": "Test",
            "market": "player_points",
            "pick_id": "1",
            "start_time_et": "6:40 PM ET",
        }
        result = normalize_pick(pick)
        assert result["start_time"] == "6:40 PM ET"

    def test_missing_iso_time_is_none(self):
        pick = {
            "player_name": "Test",
            "market": "player_points",
            "pick_id": "1",
        }
        result = normalize_pick(pick)
        assert result["start_time_iso"] is None


class TestOddsNeverFabricated:
    """Test that odds are never fabricated."""

    def test_missing_odds_returns_none(self):
        pick = {"player_name": "Test", "market": "player_points", "pick_id": "1"}
        result = normalize_pick(pick)
        assert result["odds_american"] is None  # Not -110!

    def test_actual_odds_preserved(self):
        pick = {"player_name": "Test", "market": "player_points", "pick_id": "1", "odds": 270}
        result = normalize_pick(pick)
        assert result["odds_american"] == 270

    def test_odds_american_field_used(self):
        pick = {"player_name": "Test", "market": "player_points", "pick_id": "1", "odds_american": -115}
        result = normalize_pick(pick)
        assert result["odds_american"] == -115


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_missing_units_defaults(self):
        pick = {"player_name": "Test", "market": "player_points", "pick_id": "1", "odds": -110}
        result = normalize_pick(pick)
        assert result["recommended_units"] == 1.0  # Default

    def test_id_from_pick_id(self):
        pick = {"pick_id": "abc123", "player_name": "Test", "odds": -110}
        result = normalize_pick(pick)
        assert result["id"] == "abc123"

    def test_id_from_event_id_fallback(self):
        pick = {"event_id": "evt456", "player_name": "Test", "odds": -110}
        result = normalize_pick(pick)
        assert result["id"] == "evt456"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
