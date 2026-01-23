"""
test_pick_filter.py - Unit tests for pick filter module

Tests:
- Player/game correlation limits enforced
- Daily caps enforced
- UNDER penalty causes re-tier when score crosses threshold
- Deterministic output ordering (highest score first)
"""

import unittest
from pick_filter import (
    filter_best_bets,
    _apply_under_penalty,
    _normalize_player_name,
    MAX_GOLD_STAR,
    MAX_EDGE_LEAN,
    MAX_TOTAL,
    MAX_PICKS_PER_PLAYER,
    MAX_PICKS_PER_GAME,
    UNDER_PENALTY
)


class TestUnderPenalty(unittest.TestCase):
    """Test UNDER penalty application."""

    def test_under_penalty_applied(self):
        """UNDER picks get -0.15 penalty."""
        pick = {
            "player_name": "Test Player",
            "smash_score": 7.60,
            "tier": "GOLD_STAR",
            "over_under": "UNDER"
        }
        result = _apply_under_penalty(pick)
        self.assertEqual(result["smash_score"], 7.45)
        self.assertTrue(result.get("under_penalty_applied"))

    def test_over_no_penalty(self):
        """OVER picks get no penalty."""
        pick = {
            "player_name": "Test Player",
            "smash_score": 7.60,
            "tier": "GOLD_STAR",
            "over_under": "OVER"
        }
        result = _apply_under_penalty(pick)
        self.assertEqual(result["smash_score"], 7.60)
        self.assertFalse(result.get("under_penalty_applied", False))

    def test_under_supported_no_penalty(self):
        """UNDER with under_supported=True gets no penalty."""
        pick = {
            "player_name": "Test Player",
            "smash_score": 7.60,
            "tier": "GOLD_STAR",
            "over_under": "UNDER",
            "under_supported": True
        }
        result = _apply_under_penalty(pick)
        self.assertEqual(result["smash_score"], 7.60)

    def test_under_penalty_causes_retier(self):
        """UNDER penalty at threshold causes tier change."""
        # 7.55 - 0.15 = 7.40 -> should drop from GOLD_STAR to EDGE_LEAN
        pick = {
            "player_name": "Test Player",
            "smash_score": 7.55,
            "tier": "GOLD_STAR",
            "over_under": "UNDER"
        }
        result = _apply_under_penalty(pick)
        self.assertEqual(result["smash_score"], 7.40)
        self.assertEqual(result["tier"], "EDGE_LEAN")

    def test_under_penalty_edge_to_monitor(self):
        """UNDER penalty drops EDGE_LEAN to MONITOR."""
        # 6.60 - 0.15 = 6.45 -> should drop to MONITOR
        pick = {
            "player_name": "Test Player",
            "smash_score": 6.60,
            "tier": "EDGE_LEAN",
            "over_under": "UNDER"
        }
        result = _apply_under_penalty(pick)
        self.assertEqual(result["smash_score"], 6.45)
        self.assertEqual(result["tier"], "MONITOR")


class TestPlayerLimits(unittest.TestCase):
    """Test player correlation limits."""

    def test_max_picks_per_player(self):
        """Max 2 picks per player enforced."""
        picks = [
            {"player_name": "LeBron James", "smash_score": 8.0, "tier": "GOLD_STAR", "game": "LAL vs BOS", "over_under": "OVER"},
            {"player_name": "LeBron James", "smash_score": 7.8, "tier": "GOLD_STAR", "game": "LAL vs BOS", "over_under": "OVER"},
            {"player_name": "LeBron James", "smash_score": 7.6, "tier": "GOLD_STAR", "game": "LAL vs BOS", "over_under": "OVER"},
        ]
        result = filter_best_bets(picks, "NBA")
        lebron_picks = [p for p in result if p["player_name"] == "LeBron James"]
        self.assertLessEqual(len(lebron_picks), MAX_PICKS_PER_PLAYER)

    def test_max_gold_star_per_player(self):
        """Max 1 GOLD_STAR per player enforced."""
        picks = [
            {"player_name": "Giannis", "smash_score": 8.5, "tier": "GOLD_STAR", "game": "MIL vs CHI", "over_under": "OVER"},
            {"player_name": "Giannis", "smash_score": 8.3, "tier": "GOLD_STAR", "game": "MIL vs CHI", "over_under": "OVER"},
        ]
        result = filter_best_bets(picks, "NBA")
        giannis_gs = [p for p in result if p["player_name"] == "Giannis" and p["tier"] == "GOLD_STAR"]
        self.assertEqual(len(giannis_gs), 1)
        # Should keep the highest (8.5)
        self.assertEqual(giannis_gs[0]["smash_score"], 8.5)


class TestGameLimits(unittest.TestCase):
    """Test game correlation limits."""

    def test_max_picks_per_game(self):
        """Max 3 picks per game enforced."""
        picks = [
            {"player_name": "Player A", "smash_score": 8.0, "tier": "GOLD_STAR", "game": "LAL vs BOS", "over_under": "OVER"},
            {"player_name": "Player B", "smash_score": 7.9, "tier": "GOLD_STAR", "game": "LAL vs BOS", "over_under": "OVER"},
            {"player_name": "Player C", "smash_score": 7.8, "tier": "GOLD_STAR", "game": "LAL vs BOS", "over_under": "OVER"},
            {"player_name": "Player D", "smash_score": 7.7, "tier": "GOLD_STAR", "game": "LAL vs BOS", "over_under": "OVER"},
            {"player_name": "Player E", "smash_score": 7.6, "tier": "GOLD_STAR", "game": "LAL vs BOS", "over_under": "OVER"},
        ]
        result = filter_best_bets(picks, "NBA")
        lal_bos_picks = [p for p in result if "lal" in p["game"].lower()]
        self.assertLessEqual(len(lal_bos_picks), MAX_PICKS_PER_GAME)


class TestDailyCaps(unittest.TestCase):
    """Test daily output caps."""

    def test_gold_star_cap(self):
        """Max 5 GOLD_STAR picks."""
        picks = [
            {"player_name": f"Player {i}", "smash_score": 8.0 + i*0.1, "tier": "GOLD_STAR", "game": f"Game {i}", "over_under": "OVER"}
            for i in range(10)
        ]
        result = filter_best_bets(picks, "NBA")
        gold_stars = [p for p in result if p["tier"] == "GOLD_STAR"]
        self.assertLessEqual(len(gold_stars), MAX_GOLD_STAR)

    def test_edge_lean_cap(self):
        """Max 8 EDGE_LEAN picks."""
        picks = [
            {"player_name": f"Player {i}", "smash_score": 7.0 + i*0.01, "tier": "EDGE_LEAN", "game": f"Game {i}", "over_under": "OVER"}
            for i in range(15)
        ]
        result = filter_best_bets(picks, "NBA")
        edge_leans = [p for p in result if p["tier"] == "EDGE_LEAN"]
        self.assertLessEqual(len(edge_leans), MAX_EDGE_LEAN)

    def test_total_cap(self):
        """Max 13 total picks."""
        picks = [
            {"player_name": f"Player {i}", "smash_score": 8.0 - i*0.05, "tier": "GOLD_STAR" if i < 10 else "EDGE_LEAN", "game": f"Game {i}", "over_under": "OVER"}
            for i in range(25)
        ]
        result = filter_best_bets(picks, "NBA")
        self.assertLessEqual(len(result), MAX_TOTAL)


class TestOrdering(unittest.TestCase):
    """Test deterministic ordering."""

    def test_highest_score_first(self):
        """Picks are ordered by score descending."""
        picks = [
            {"player_name": "Player A", "smash_score": 7.2, "tier": "EDGE_LEAN", "game": "Game 1", "over_under": "OVER"},
            {"player_name": "Player B", "smash_score": 8.5, "tier": "GOLD_STAR", "game": "Game 2", "over_under": "OVER"},
            {"player_name": "Player C", "smash_score": 7.8, "tier": "GOLD_STAR", "game": "Game 3", "over_under": "OVER"},
        ]
        result = filter_best_bets(picks, "NBA")
        scores = [p["smash_score"] for p in result]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_deterministic_output(self):
        """Same input produces same output."""
        picks = [
            {"player_name": "Player A", "smash_score": 7.5, "tier": "GOLD_STAR", "game": "Game 1", "over_under": "OVER"},
            {"player_name": "Player B", "smash_score": 7.5, "tier": "GOLD_STAR", "game": "Game 2", "over_under": "OVER"},
            {"player_name": "Player C", "smash_score": 7.5, "tier": "GOLD_STAR", "game": "Game 3", "over_under": "OVER"},
        ]
        result1 = filter_best_bets(picks, "NBA")
        result2 = filter_best_bets(picks, "NBA")
        self.assertEqual(
            [p["player_name"] for p in result1],
            [p["player_name"] for p in result2]
        )


class TestEdgeCases(unittest.TestCase):
    """Test edge cases."""

    def test_empty_input(self):
        """Empty input returns empty output."""
        result = filter_best_bets([], "NBA")
        self.assertEqual(result, [])

    def test_monitor_picks_excluded(self):
        """MONITOR tier picks are excluded from output."""
        picks = [
            {"player_name": "Player A", "smash_score": 5.8, "tier": "MONITOR", "game": "Game 1", "over_under": "OVER"},
            {"player_name": "Player B", "smash_score": 7.5, "tier": "GOLD_STAR", "game": "Game 2", "over_under": "OVER"},
        ]
        result = filter_best_bets(picks, "NBA")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tier"], "GOLD_STAR")

    def test_pass_picks_excluded(self):
        """PASS tier picks are excluded from output."""
        picks = [
            {"player_name": "Player A", "smash_score": 5.0, "tier": "PASS", "game": "Game 1", "over_under": "OVER"},
        ]
        result = filter_best_bets(picks, "NBA")
        self.assertEqual(len(result), 0)


if __name__ == "__main__":
    unittest.main()
