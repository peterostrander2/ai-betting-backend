"""
PickContract v1 Verification Tests

These tests ensure the /live/best-bets/{sport} endpoint returns picks
that conform to the PickContract v1 specification.

REQUIRED FIELDS:
- Core Identity: id, sport, league, event_id, matchup, home_team, away_team,
                 start_time_et, start_time_iso, status, has_started, is_live
- Bet Instruction: pick_type, market_label, selection, selection_home_away,
                   line, line_signed, odds_american, units, bet_string, book, book_link
- Reasoning: tier, score, confidence_label, signals_fired, confluence_reasons, engine_breakdown
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.pick_normalizer import normalize_pick, normalize_best_bets_response

# Sample pick markers that indicate fallback/sample data
SAMPLE_DATA_MARKERS = [
    "sample_1", "sample_2", "sample_3",
    "nba_sample", "nfl_sample", "mlb_sample", "nhl_sample",
    "Los Angeles Lakers",  # Common sample team
    "Boston Celtics",      # Common sample team (in certain contexts)
]


class TestPickContractV1:
    """Verify PickContract v1 compliance."""

    # Required fields for all picks
    CORE_IDENTITY_FIELDS = [
        "id", "sport", "league", "event_id", "matchup",
        "home_team", "away_team", "start_time_et",
        "status", "has_started", "is_live"
    ]

    BET_INSTRUCTION_FIELDS = [
        "pick_type", "market_label", "selection",
        "selection_home_away",  # Can be null but must exist
        "line",                 # Can be null for ML
        "line_signed",          # Can be null for ML
        "odds_american",        # Can be null if unavailable
        "units", "bet_string", "book", "book_link"
    ]

    REASONING_FIELDS = [
        "tier", "score", "confidence_label",
        "signals_fired", "confluence_reasons", "engine_breakdown"
    ]

    VALID_PICK_TYPES = ["spread", "moneyline", "total", "player_prop"]
    VALID_TIERS = ["TITANIUM_SMASH", "GOLD_STAR", "EDGE_LEAN", "MONITOR", "PASS"]

    def test_spread_pick_has_all_required_fields(self):
        """A spread pick must have all contract fields."""
        pick = {
            "pick_type": "SPREAD",
            "market": "spreads",
            "team": "Milwaukee Bucks",
            "home_team": "Boston Celtics",
            "away_team": "Milwaukee Bucks",
            "line": 1.5,
            "odds": -110,
            "units": 2.0,
            "pick_id": "spread123",
            "final_score": 8.5,
            "tier": "GOLD_STAR",
            "start_time_et": "7:30 PM ET",
        }
        result = normalize_pick(pick)

        # Check all required fields exist
        for field in self.CORE_IDENTITY_FIELDS:
            assert field in result, f"Missing core field: {field}"

        for field in self.BET_INSTRUCTION_FIELDS:
            assert field in result, f"Missing bet instruction field: {field}"

        for field in self.REASONING_FIELDS:
            assert field in result, f"Missing reasoning field: {field}"

        # Verify specific values
        assert result["pick_type"] == "spread"
        assert result["market_label"] == "Spread"
        assert result["selection"] == "Milwaukee Bucks"
        assert result["selection_home_away"] == "AWAY"
        assert result["line_signed"] == "+1.5"
        assert "Milwaukee Bucks" in result["bet_string"]
        assert "+1.5" in result["bet_string"]

    def test_moneyline_pick_has_all_required_fields(self):
        """A moneyline pick must have all contract fields."""
        pick = {
            "market": "h2h",
            "team": "Boston Celtics",
            "home_team": "Boston Celtics",
            "away_team": "Milwaukee Bucks",
            "odds": -150,
            "units": 1.5,
            "pick_id": "ml123",
            "final_score": 7.8,
            "tier": "EDGE_LEAN",
            "start_time_et": "7:30 PM ET",
        }
        result = normalize_pick(pick)

        # Check fields
        assert result["pick_type"] == "moneyline"
        assert result["market_label"] == "Moneyline"
        assert result["selection"] == "Boston Celtics"
        assert result["selection_home_away"] == "HOME"
        assert result["line"] is None or result["line_signed"] is None  # ML has no line
        assert "ML" in result["bet_string"] or "Moneyline" in result["bet_string"]

    def test_total_pick_has_all_required_fields(self):
        """A total pick must have all contract fields."""
        pick = {
            "pick_type": "TOTAL",
            "market": "totals",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "line": 220.5,
            "side": "Over",
            "odds": -110,
            "units": 1.0,
            "pick_id": "total123",
            "final_score": 7.2,
        }
        result = normalize_pick(pick)

        assert result["pick_type"] == "total"
        assert result["market_label"] == "Total"
        assert result["selection"] == "Celtics/Lakers"
        assert result["side_label"] == "Over"
        assert result["line_signed"] == "O 220.5"
        assert "Over" in result["bet_string"]
        assert "220.5" in result["bet_string"]

    def test_prop_pick_has_all_required_fields(self):
        """A prop pick must have all contract fields."""
        pick = {
            "player_name": "LeBron James",
            "market": "player_points",
            "stat_type": "player_points",
            "line": 25.5,
            "side": "Over",
            "odds": -120,
            "units": 1.0,
            "pick_id": "prop123",
            "final_score": 8.0,
            "home_team": "Lakers",
            "away_team": "Celtics",
            "commence_time_iso": "2026-02-01T23:00:00Z",
        }
        result = normalize_pick(pick)

        assert result["pick_type"] == "player_prop"
        assert result["market_label"] == "Points"
        assert result["selection"] == "LeBron James"
        assert result["side_label"] == "Over"
        assert result["line_signed"] == "O 25.5"
        assert "LeBron James" in result["bet_string"]
        assert "Points" in result["bet_string"]
        assert "Over" in result["bet_string"]
        assert result["start_time_iso"] == "2026-02-01T23:00:00Z"

    def test_sharp_pick_maps_to_spread_or_ml(self):
        """SHARP picks must be normalized to spread or moneyline."""
        # Sharp with line -> spread
        sharp_with_line = {
            "pick_type": "SHARP",
            "market": "sharp_money",
            "team": "Boston Celtics",
            "home_team": "Boston Celtics",
            "away_team": "Milwaukee Bucks",
            "line": 2.5,
            "odds": -110,
            "pick_id": "sharp1",
        }
        result = normalize_pick(sharp_with_line)
        assert result["pick_type"] == "spread"
        assert result["market_label"] == "Spread"
        assert result["signal_label"] == "Sharp Signal"

        # Sharp without line -> moneyline
        sharp_no_line = {
            "pick_type": "SHARP",
            "market": "sharp_money",
            "team": "Boston Celtics",
            "home_team": "Boston Celtics",
            "away_team": "Milwaukee Bucks",
            "line": None,
            "odds": -110,
            "pick_id": "sharp2",
        }
        result = normalize_pick(sharp_no_line)
        assert result["pick_type"] == "moneyline"
        assert result["signal_label"] == "Sharp Signal"

    def test_selection_home_away_computed_correctly(self):
        """selection_home_away must correctly identify HOME vs AWAY."""
        # Home team selection
        home_pick = {
            "team": "Boston Celtics",
            "home_team": "Boston Celtics",
            "away_team": "Milwaukee Bucks",
            "market": "spreads",
            "line": -3.5,
            "pick_id": "home1",
        }
        result = normalize_pick(home_pick)
        assert result["selection_home_away"] == "HOME"

        # Away team selection
        away_pick = {
            "team": "Milwaukee Bucks",
            "home_team": "Boston Celtics",
            "away_team": "Milwaukee Bucks",
            "market": "spreads",
            "line": 3.5,
            "pick_id": "away1",
        }
        result = normalize_pick(away_pick)
        assert result["selection_home_away"] == "AWAY"

    def test_no_sample_data_markers(self):
        """Normalized picks should not contain sample data markers."""
        pick = {
            "player_name": "Test Player",
            "market": "player_points",
            "pick_id": "real_pick_123",
            "home_team": "Real Home Team",
            "away_team": "Real Away Team",
        }
        result = normalize_pick(pick)

        # Check id doesn't contain sample markers
        for marker in ["sample_1", "sample_2", "nba_sample", "nfl_sample"]:
            assert marker not in str(result.get("id", "")).lower()
            assert marker not in str(result.get("event_id", "")).lower()

    def test_odds_never_fabricated(self):
        """odds_american must be actual value or null, never default -110."""
        # Pick without odds
        pick_no_odds = {
            "player_name": "Test",
            "market": "player_points",
            "pick_id": "no_odds",
        }
        result = normalize_pick(pick_no_odds)
        assert result["odds_american"] is None  # Not -110!

        # Pick with odds
        pick_with_odds = {
            "player_name": "Test",
            "market": "player_points",
            "pick_id": "with_odds",
            "odds": -125,
        }
        result = normalize_pick(pick_with_odds)
        assert result["odds_american"] == -125

    def test_confluence_reasons_no_unknown_pick_type(self):
        """confluence_reasons should not contain 'Unknown pick type'."""
        # This tests that the Jason Sim mapping is fixed
        pick = {
            "pick_type": "SHARP",
            "market": "sharp_money",
            "team": "Celtics",
            "home_team": "Celtics",
            "away_team": "Bucks",
            "line": 1.5,
            "pick_id": "sharp_test",
            "confluence_reasons": ["Jason: Some valid reason"],
        }
        result = normalize_pick(pick)

        for reason in result.get("confluence_reasons", []):
            assert "Unknown pick type" not in reason

    def test_bet_string_formats(self):
        """Verify bet_string format for each pick type."""
        # Spread format: "Team +1.5 (-110) — 2.0u"
        spread = normalize_pick({
            "market": "spreads",
            "team": "Bucks",
            "home_team": "Celtics",
            "away_team": "Bucks",
            "line": 1.5,
            "odds": -110,
            "units": 2.0,
            "pick_id": "s1",
        })
        assert spread["bet_string"] == "Bucks +1.5 (-110) — 2.0u"

        # Moneyline format: "Team ML (-150) — 1.0u"
        ml = normalize_pick({
            "market": "h2h",
            "team": "Celtics",
            "home_team": "Celtics",
            "away_team": "Bucks",
            "odds": -150,
            "units": 1.0,
            "pick_id": "m1",
        })
        assert "ML" in ml["bet_string"]
        assert "-150" in ml["bet_string"]

        # Total format: "Away/Home Over 220.5 (-110) — 1.0u"
        total = normalize_pick({
            "pick_type": "TOTAL",
            "market": "totals",
            "home_team": "Celtics",
            "away_team": "Bucks",
            "line": 220.5,
            "side": "Over",
            "odds": -110,
            "units": 1.0,
            "pick_id": "t1",
        })
        assert "Over" in total["bet_string"]
        assert "220.5" in total["bet_string"]

        # Prop format: "Player — Stat Over 25.5 (-110) — 1.0u"
        prop = normalize_pick({
            "player_name": "LeBron",
            "market": "player_points",
            "stat_type": "player_points",
            "line": 25.5,
            "side": "Over",
            "odds": -110,
            "units": 1.0,
            "pick_id": "p1",
        })
        assert "LeBron" in prop["bet_string"]
        assert "Points" in prop["bet_string"]
        assert "Over" in prop["bet_string"]


class TestBestBetsResponseNormalization:
    """Test full response normalization."""

    def test_empty_response_is_valid(self):
        """Empty picks should return empty arrays, not sample data."""
        response = {
            "sport": "NHL",
            "props": {"count": 0, "picks": []},
            "game_picks": {"count": 0, "picks": []},
        }
        result = normalize_best_bets_response(response)

        assert result["props"]["picks"] == []
        assert result["game_picks"]["picks"] == []

    def test_all_picks_normalized(self):
        """All picks in response should be normalized."""
        response = {
            "props": {
                "count": 1,
                "picks": [{"player_name": "Test", "market": "player_points", "pick_id": "p1"}]
            },
            "game_picks": {
                "count": 1,
                "picks": [{"team": "Celtics", "market": "spreads", "line": -3.5, "pick_id": "g1", "home_team": "Celtics", "away_team": "Bucks"}]
            }
        }
        result = normalize_best_bets_response(response)

        # Props normalized
        assert result["props"]["picks"][0]["pick_type"] == "player_prop"
        assert result["props"]["picks"][0]["bet_string"]

        # Game picks normalized
        assert result["game_picks"]["picks"][0]["pick_type"] == "spread"
        assert result["game_picks"]["picks"][0]["selection_home_away"] == "HOME"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
