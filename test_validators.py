"""
test_validators.py - Unit tests for prop validators

Tests:
- prop_integrity: required keys, team membership
- injury_guard: OUT, SUSPENDED, DOUBTFUL, GTD
- market_availability: DK market listing verification
"""

import unittest
from validators.prop_integrity import validate_prop_integrity, REQUIRED_KEYS
from validators.injury_guard import (
    validate_injury_status, build_injury_index,
    BLOCK_DOUBTFUL, BLOCK_GTD
)
from validators.market_availability import (
    validate_market_available, build_dk_market_index,
    _normalize_market, _normalize_name
)


class TestPropIntegrity(unittest.TestCase):
    """Test prop_integrity validation."""

    def test_valid_prop_passes(self):
        """Valid prop with all required fields passes."""
        prop = {
            "sport": "NBA",
            "player_name": "LeBron James",
            "market": "player_points",
            "line": 25.5,
            "side": "over",
            "game_id": "abc123",
        }
        is_valid, reason = validate_prop_integrity(prop)
        self.assertTrue(is_valid)
        self.assertIsNone(reason)

    def test_missing_required_key_fails(self):
        """Missing required key fails validation."""
        base_prop = {
            "sport": "NBA",
            "player_name": "LeBron James",
            "market": "player_points",
            "line": 25.5,
            "side": "over",
            "game_id": "abc123",
        }

        for key in REQUIRED_KEYS:
            prop = base_prop.copy()
            del prop[key]
            is_valid, reason = validate_prop_integrity(prop)
            self.assertFalse(is_valid, f"Should fail when missing {key}")
            self.assertIn(key.upper(), reason)

    def test_empty_required_key_fails(self):
        """Empty string for required key fails."""
        prop = {
            "sport": "NBA",
            "player_name": "",  # Empty
            "market": "player_points",
            "line": 25.5,
            "side": "over",
            "game_id": "abc123",
        }
        is_valid, reason = validate_prop_integrity(prop)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "MISSING_REQUIRED_PLAYER_NAME")

    def test_team_not_in_game_fails(self):
        """Player's team not in game teams fails."""
        prop = {
            "sport": "NBA",
            "player_name": "LeBron James",
            "market": "player_points",
            "line": 25.5,
            "side": "over",
            "game_id": "abc123",
            "team_id": "lakers",
            "home_team_id": "celtics",
            "away_team_id": "warriors",
        }
        is_valid, reason = validate_prop_integrity(prop)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "TEAM_NOT_IN_GAME")

    def test_team_in_game_passes(self):
        """Player's team in game teams passes."""
        prop = {
            "sport": "NBA",
            "player_name": "LeBron James",
            "market": "player_points",
            "line": 25.5,
            "side": "over",
            "game_id": "abc123",
            "team_id": "lakers",
            "home_team_id": "lakers",
            "away_team_id": "celtics",
        }
        is_valid, reason = validate_prop_integrity(prop)
        self.assertTrue(is_valid)

    def test_no_games_played_fails(self):
        """games_played_season <= 0 fails."""
        prop = {
            "sport": "NBA",
            "player_name": "Rookie Player",
            "market": "player_points",
            "line": 10.5,
            "side": "over",
            "game_id": "abc123",
            "games_played_season": 0,
        }
        is_valid, reason = validate_prop_integrity(prop)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "NO_GAMES_PLAYED")

    def test_inactive_player_fails(self):
        """active_status not valid fails."""
        prop = {
            "sport": "NBA",
            "player_name": "Inactive Player",
            "market": "player_points",
            "line": 10.5,
            "side": "over",
            "game_id": "abc123",
            "active_status": "inactive",
        }
        is_valid, reason = validate_prop_integrity(prop)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "PLAYER_INACTIVE")


class TestInjuryGuard(unittest.TestCase):
    """Test injury_guard validation."""

    def setUp(self):
        """Set up injury index for tests."""
        injuries = [
            {"player_name": "Out Player", "status": "out"},
            {"player_name": "Suspended Player", "status": "suspended"},
            {"player_name": "Doubtful Player", "status": "doubtful"},
            {"player_name": "GTD Player", "status": "questionable"},
            {"player_id": "123", "player_name": "ID Player", "status": "out"},
        ]
        self.injury_index = build_injury_index(injuries)

    def test_out_player_fails(self):
        """OUT player fails validation."""
        prop = {"player_name": "Out Player", "sport": "NBA"}
        is_valid, reason = validate_injury_status(prop, self.injury_index)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "INJURY_OUT")

    def test_suspended_player_fails(self):
        """SUSPENDED player fails validation."""
        prop = {"player_name": "Suspended Player", "sport": "NBA"}
        is_valid, reason = validate_injury_status(prop, self.injury_index)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "INJURY_SUSPENDED")

    def test_doubtful_player_fails_when_blocked(self):
        """DOUBTFUL player fails when BLOCK_DOUBTFUL=True."""
        prop = {"player_name": "Doubtful Player", "sport": "NBA"}
        is_valid, reason = validate_injury_status(prop, self.injury_index, block_doubtful=True)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "INJURY_DOUBTFUL")

    def test_doubtful_player_passes_when_allowed(self):
        """DOUBTFUL player passes when BLOCK_DOUBTFUL=False."""
        prop = {"player_name": "Doubtful Player", "sport": "NBA"}
        is_valid, reason = validate_injury_status(prop, self.injury_index, block_doubtful=False)
        self.assertTrue(is_valid)

    def test_gtd_player_passes_when_allowed(self):
        """GTD player passes when BLOCK_GTD=False."""
        prop = {"player_name": "GTD Player", "sport": "NBA"}
        is_valid, reason = validate_injury_status(prop, self.injury_index, block_gtd=False)
        self.assertTrue(is_valid)

    def test_gtd_player_fails_when_blocked(self):
        """GTD player fails when BLOCK_GTD=True."""
        prop = {"player_name": "GTD Player", "sport": "NBA"}
        is_valid, reason = validate_injury_status(prop, self.injury_index, block_gtd=True)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "INJURY_GTD")

    def test_healthy_player_passes(self):
        """Player not in injury index passes."""
        prop = {"player_name": "Healthy Player", "sport": "NBA"}
        is_valid, reason = validate_injury_status(prop, self.injury_index)
        self.assertTrue(is_valid)

    def test_player_id_lookup(self):
        """Player lookup by player_id works."""
        prop = {"player_id": "123", "player_name": "ID Player", "sport": "NBA"}
        is_valid, reason = validate_injury_status(prop, self.injury_index)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "INJURY_OUT")


class TestMarketAvailability(unittest.TestCase):
    """Test market_availability validation."""

    def setUp(self):
        """Set up DK market index for tests."""
        dk_props = [
            {
                "sport": "NBA",
                "game_id": "game1",
                "player_name": "LeBron James",
                "market": "player_points",
                "line": 25.5,
                "side": "over"
            },
            {
                "sport": "NBA",
                "game_id": "game1",
                "player_name": "LeBron James",
                "market": "player_assists",
                "line": 7.5,
                "side": "over"
            },
            {
                "sport": "NHL",
                "game_id": "game2",
                "player_id": "456",
                "player_name": "Connor McDavid",
                "market": "player_shots_on_goal",
                "line": 3.5,
                "side": "over"
            },
        ]
        self.dk_index = build_dk_market_index(dk_props)

    def test_listed_prop_passes(self):
        """Prop exists in DK feed passes."""
        prop = {
            "sport": "NBA",
            "game_id": "game1",
            "player_name": "LeBron James",
            "market": "player_points",
            "line": 25.5,
            "side": "over"
        }
        is_valid, reason = validate_market_available(prop, self.dk_index)
        self.assertTrue(is_valid)

    def test_unlisted_prop_fails(self):
        """Prop not in DK feed fails."""
        prop = {
            "sport": "NBA",
            "game_id": "game1",
            "player_name": "Deni Avdija",
            "market": "player_assists",
            "line": 5.5,
            "side": "under"
        }
        is_valid, reason = validate_market_available(prop, self.dk_index)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "DK_MARKET_NOT_LISTED")

    def test_name_normalization_fallback(self):
        """Name normalization works for matching."""
        prop = {
            "sport": "NBA",
            "game_id": "game1",
            "player_name": "LEBRON JAMES",  # Uppercase
            "market": "player_points",
            "line": 25.5,
            "side": "over"
        }
        is_valid, reason = validate_market_available(prop, self.dk_index)
        self.assertTrue(is_valid)

    def test_wrong_line_fails(self):
        """Prop with different line fails."""
        prop = {
            "sport": "NBA",
            "game_id": "game1",
            "player_name": "LeBron James",
            "market": "player_points",
            "line": 30.5,  # Wrong line
            "side": "over"
        }
        is_valid, reason = validate_market_available(prop, self.dk_index)
        self.assertFalse(is_valid)

    def test_wrong_side_fails(self):
        """Prop with different side fails."""
        prop = {
            "sport": "NBA",
            "game_id": "game1",
            "player_name": "LeBron James",
            "market": "player_points",
            "line": 25.5,
            "side": "under"  # Wrong side
        }
        is_valid, reason = validate_market_available(prop, self.dk_index)
        self.assertFalse(is_valid)

    def test_empty_index_allows_all(self):
        """Empty DK index allows all (graceful degradation)."""
        prop = {
            "sport": "NBA",
            "game_id": "game1",
            "player_name": "Anyone",
            "market": "player_points",
            "line": 10.5,
            "side": "over"
        }
        is_valid, reason = validate_market_available(prop, {})
        self.assertTrue(is_valid)


class TestMarketNormalization(unittest.TestCase):
    """Test market name normalization."""

    def test_normalize_market(self):
        """Market names normalize correctly."""
        self.assertEqual(_normalize_market("player_points"), "points")
        self.assertEqual(_normalize_market("player_assists"), "assists")
        self.assertEqual(_normalize_market("player_shots_on_goal"), "shots")
        self.assertEqual(_normalize_market("unknown_market"), "unknown_market")

    def test_normalize_name(self):
        """Player names normalize correctly."""
        self.assertEqual(_normalize_name("LeBron James"), "lebron james")
        self.assertEqual(_normalize_name("LeBron James Jr."), "lebron james")
        self.assertEqual(_normalize_name("  GIANNIS  "), "giannis")


if __name__ == "__main__":
    unittest.main()
