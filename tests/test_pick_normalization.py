"""
Unit tests for pick normalization contract.

GUARANTEES: Every pick returned by /live/best-bets/{sport} includes:
- pick_type: "player_prop" | "moneyline" | "spread" | "total"
- selection: non-empty string (team or player name)
- market_label: non-empty string (human-readable market)
- side_label: non-empty string
- bet_string: non-empty string (canonical display)
- odds_american: integer
- recommended_units: number
- id: non-empty string
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.pick_normalizer import (
    normalize_pick as _normalize_pick,
    normalize_pick_type as _normalize_pick_type,
    normalize_market_label as _normalize_market_label,
    normalize_selection as _normalize_selection,
    normalize_side_label as _normalize_side_label,
    build_bet_string as _build_bet_string,
)


# Required fields that must be present and non-empty
REQUIRED_PICK_FIELDS = [
    "pick_type",
    "selection",
    "market_label",
    "side_label",
    "bet_string",
    "odds_american",
    "recommended_units",
    "id",
]

VALID_PICK_TYPES = ["player_prop", "moneyline", "spread", "total"]


class TestNormalizePickType:
    """Test pick_type normalization."""

    def test_player_prop_from_player_field(self):
        pick = {"player": "LeBron James", "market": "player_points"}
        assert _normalize_pick_type(pick) == "player_prop"

    def test_player_prop_from_player_name_field(self):
        pick = {"player_name": "Yanni Gourde", "market": "player_assists"}
        assert _normalize_pick_type(pick) == "player_prop"

    def test_total_from_pick_type(self):
        pick = {"pick_type": "TOTAL", "market": "totals"}
        assert _normalize_pick_type(pick) == "total"

    def test_spread_from_market(self):
        pick = {"market": "spreads", "team": "Lakers"}
        assert _normalize_pick_type(pick) == "spread"

    def test_moneyline_from_h2h(self):
        pick = {"market": "h2h", "team": "Celtics"}
        assert _normalize_pick_type(pick) == "moneyline"

    def test_sharp_with_line_becomes_spread(self):
        pick = {"pick_type": "SHARP", "line": 1.5, "team": "Bucks"}
        assert _normalize_pick_type(pick) == "spread"

    def test_sharp_without_line_becomes_moneyline(self):
        pick = {"pick_type": "SHARP", "line": None, "team": "Bucks"}
        assert _normalize_pick_type(pick) == "moneyline"


class TestNormalizeMarketLabel:
    """Test market_label normalization."""

    def test_player_points(self):
        assert _normalize_market_label("player_points") == "Points"

    def test_player_assists(self):
        assert _normalize_market_label("player_assists") == "Assists"

    def test_player_threes(self):
        assert _normalize_market_label("player_threes") == "3PT Made"

    def test_spreads(self):
        assert _normalize_market_label("spreads") == "Spread"

    def test_totals(self):
        assert _normalize_market_label("totals") == "Total"

    def test_h2h(self):
        assert _normalize_market_label("h2h") == "Moneyline"

    def test_unknown_market_uses_stat_type(self):
        assert _normalize_market_label("unknown", "player_rebounds") == "Rebounds"


class TestNormalizeSelection:
    """Test selection normalization."""

    def test_player_prop_uses_player_name(self):
        pick = {"player_name": "LeBron James", "team": "Lakers"}
        assert _normalize_selection(pick, "player_prop") == "LeBron James"

    def test_player_prop_fallback_to_player(self):
        pick = {"player": "Yanni Gourde"}
        assert _normalize_selection(pick, "player_prop") == "Yanni Gourde"

    def test_total_uses_matchup_format(self):
        pick = {"home_team": "Celtics", "away_team": "Bucks"}
        assert _normalize_selection(pick, "total") == "Bucks/Celtics"

    def test_spread_uses_team(self):
        pick = {"team": "Lakers", "side": "HOME"}
        assert _normalize_selection(pick, "spread") == "Lakers"

    def test_moneyline_uses_team(self):
        pick = {"team": "Celtics"}
        assert _normalize_selection(pick, "moneyline") == "Celtics"


class TestNormalizeSideLabel:
    """Test side_label normalization."""

    def test_prop_over(self):
        pick = {"side": "Over"}
        assert _normalize_side_label(pick, "player_prop") == "Over"

    def test_prop_under_from_direction(self):
        pick = {"direction": "UNDER"}
        assert _normalize_side_label(pick, "player_prop") == "Under"

    def test_total_over(self):
        pick = {"side": "Over"}
        assert _normalize_side_label(pick, "total") == "Over"

    def test_spread_uses_team(self):
        pick = {"team": "Lakers", "side": "Lakers"}
        assert _normalize_side_label(pick, "spread") == "Lakers"


class TestBuildBetString:
    """Test bet_string generation."""

    def test_player_prop_bet_string(self):
        pick = {"line": 25.5, "odds": -110, "units": 2.0}
        result = _build_bet_string(
            pick, "player_prop", "LeBron James", "Points", "Over"
        )
        assert result == "LeBron James — Points Over 25.5 (-110) — 2.0u"

    def test_total_bet_string(self):
        pick = {"line": 228.5, "odds": -110, "units": 1.0}
        result = _build_bet_string(
            pick, "total", "Bucks/Celtics", "Total", "Over"
        )
        assert result == "Bucks/Celtics Over 228.5 (-110) — 1.0u"

    def test_spread_bet_string(self):
        pick = {"line": -4.5, "odds": -105, "units": 1.0}
        result = _build_bet_string(
            pick, "spread", "Boston Celtics", "Spread", "Boston Celtics"
        )
        assert result == "Boston Celtics -4.5 (-105) — 1.0u"

    def test_moneyline_bet_string(self):
        pick = {"line": None, "odds": -150, "units": 1.5}
        result = _build_bet_string(
            pick, "moneyline", "Milwaukee Bucks", "Moneyline", "Milwaukee Bucks"
        )
        assert result == "Milwaukee Bucks Moneyline (-150) — 1.5u"

    def test_positive_odds_formatted(self):
        pick = {"line": 0.5, "odds": 270, "units": 1.0}
        result = _build_bet_string(
            pick, "player_prop", "Yanni Gourde", "Assists", "Over"
        )
        assert "+270" in result


class TestNormalizePick:
    """Test full pick normalization."""

    def test_prop_pick_has_all_required_fields(self):
        pick = {
            "player_name": "LeBron James",
            "market": "player_points",
            "line": 25.5,
            "side": "Over",
            "odds": -110,
            "units": 2.0,
            "matchup": "Lakers @ Celtics",
            "final_score": 8.5,
            "tier": "GOLD_STAR",
            "pick_id": "abc123",
        }
        result = _normalize_pick(pick)

        for field in REQUIRED_PICK_FIELDS:
            assert field in result, f"Missing required field: {field}"
            assert result[field] is not None, f"Field {field} is None"
            if isinstance(result[field], str):
                assert result[field] != "", f"Field {field} is empty string"
                assert result[field] != "N/A", f"Field {field} is N/A"

        assert result["pick_type"] in VALID_PICK_TYPES

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
        }
        result = _normalize_pick(pick)

        for field in REQUIRED_PICK_FIELDS:
            assert field in result, f"Missing required field: {field}"
            assert result[field] is not None, f"Field {field} is None"
            if isinstance(result[field], str):
                assert result[field] != "", f"Field {field} is empty string"
                assert result[field] != "N/A", f"Field {field} is N/A"

        assert result["pick_type"] in VALID_PICK_TYPES

    def test_sharp_pick_normalized(self):
        """Sharp picks must be normalized to spread or moneyline."""
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
        result = _normalize_pick(pick)

        assert result["pick_type"] in ["spread", "moneyline"]
        assert result["selection"] == "Milwaukee Bucks"
        assert "Milwaukee Bucks" in result["bet_string"]

    def test_selection_never_na(self):
        """Selection must never be N/A or empty."""
        picks = [
            {"player_name": "Test Player", "market": "player_points", "pick_id": "1"},
            {"team": "Test Team", "market": "spreads", "pick_id": "2"},
            {"home_team": "Home", "away_team": "Away", "pick_type": "TOTAL", "pick_id": "3"},
        ]
        for pick in picks:
            result = _normalize_pick(pick)
            assert result["selection"] not in ("", "N/A", None, "Unknown")


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_missing_odds_defaults(self):
        pick = {"player_name": "Test", "market": "player_points", "pick_id": "1"}
        result = _normalize_pick(pick)
        assert result["odds_american"] == -110  # Default

    def test_missing_units_defaults(self):
        pick = {"player_name": "Test", "market": "player_points", "pick_id": "1"}
        result = _normalize_pick(pick)
        assert result["recommended_units"] == 1.0  # Default

    def test_id_from_pick_id(self):
        pick = {"pick_id": "abc123", "player_name": "Test"}
        result = _normalize_pick(pick)
        assert result["id"] == "abc123"

    def test_id_from_event_id_fallback(self):
        pick = {"event_id": "evt456", "player_name": "Test"}
        result = _normalize_pick(pick)
        assert result["id"] == "evt456"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
