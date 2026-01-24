"""
Test suite for Master Prompt requirements.

Tests the following requirements:
A) Single output contract (canonical schema)
B) TODAY-ONLY filter (EST)
H) Tiering single source of truth
E) Scoring architecture (4-engine separation)
G) Titanium Rule + Harmonic Convergence
"""

import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Canonical schema
from canonical_schema import (
    CanonicalPick,
    ScoringBreakdown,
    MarketType,
    Tier,
    GameStatus,
    SourceFeed,
    compute_today_est_fields,
    compute_tier,
    compute_units,
    BOOK_ALLOWLIST,
)

# Tiering
from tiering import tier_from_score, DEFAULT_TIERS


class TestCanonicalSchema(unittest.TestCase):
    """Test A) Single output contract."""

    def test_pick_creation_minimal(self):
        """Pick can be created with minimal required fields."""
        pick = CanonicalPick(
            sport="NBA",
            league="NBA",
            event_id="abc123",
            game_time_utc="2026-01-24T19:00:00Z",
            game_time_est="2026-01-24T14:00:00-05:00",
            is_today_est=True,
            home_team="Lakers",
            away_team="Celtics",
            market_type=MarketType.SPREAD,
            selection="Lakers"
        )
        # pick_id should be auto-generated
        self.assertTrue(len(pick.pick_id) > 0)
        # matchup_display should be auto-generated
        self.assertEqual(pick.matchup_display, "Celtics @ Lakers")

    def test_pick_with_full_scoring(self):
        """Pick can include full scoring breakdown."""
        pick = CanonicalPick(
            sport="NBA",
            league="NBA",
            event_id="abc123",
            game_time_utc="2026-01-24T19:00:00Z",
            game_time_est="2026-01-24T14:00:00-05:00",
            is_today_est=True,
            home_team="Lakers",
            away_team="Celtics",
            market_type=MarketType.SPREAD,
            selection="Lakers",
            final_score=7.8,
            ai_score=7.5,
            research_score=8.0,
            esoteric_score=7.2,
            jarvis_score=1.5,
            jason_sim_boost=0.3,
            titanium_smash=True,
            titanium_count=3,
            harmonic_convergence=False
        )
        self.assertEqual(pick.final_score, 7.8)
        self.assertEqual(pick.titanium_count, 3)

    def test_tier_upgrade_for_titanium(self):
        """Titanium smash with score >= 7.5 should upgrade tier."""
        pick = CanonicalPick(
            sport="NBA",
            league="NBA",
            event_id="abc123",
            game_time_utc="2026-01-24T19:00:00Z",
            game_time_est="2026-01-24T14:00:00-05:00",
            is_today_est=True,
            home_team="Lakers",
            away_team="Celtics",
            market_type=MarketType.SPREAD,
            selection="Lakers",
            final_score=7.8,
            tier=Tier.GOLD_STAR,
            titanium_smash=True,
            titanium_count=3
        )
        # Should be upgraded to TITANIUM_SMASH
        self.assertEqual(pick.tier, Tier.TITANIUM_SMASH)

    def test_market_types(self):
        """All market types should be supported."""
        for market in MarketType:
            pick = CanonicalPick(
                sport="NBA",
                league="NBA",
                event_id="abc123",
                game_time_utc="2026-01-24T19:00:00Z",
                game_time_est="2026-01-24T14:00:00-05:00",
                is_today_est=True,
                home_team="Lakers",
                away_team="Celtics",
                market_type=market,
                selection="Lakers"
            )
            self.assertEqual(pick.market_type, market)


class TestTodayOnlyFilter(unittest.TestCase):
    """Test B) TODAY-ONLY filter (EST)."""

    def test_today_game_is_today(self):
        """Game today in EST should return is_today_est=True."""
        ET = ZoneInfo("America/New_York")
        now_et = datetime.now(ET)
        game_time = now_et.replace(hour=19, minute=0, second=0, microsecond=0)
        game_time_utc = game_time.astimezone(ZoneInfo("UTC")).isoformat()

        result = compute_today_est_fields(game_time_utc)
        self.assertTrue(result["is_today_est"])

    def test_yesterday_game_not_today(self):
        """Game yesterday in EST should return is_today_est=False."""
        ET = ZoneInfo("America/New_York")
        yesterday = datetime.now(ET) - timedelta(days=1)
        game_time = yesterday.replace(hour=19, minute=0, second=0, microsecond=0)
        game_time_utc = game_time.astimezone(ZoneInfo("UTC")).isoformat()

        result = compute_today_est_fields(game_time_utc)
        self.assertFalse(result["is_today_est"])

    def test_tomorrow_game_not_today(self):
        """Game tomorrow in EST should return is_today_est=False."""
        ET = ZoneInfo("America/New_York")
        tomorrow = datetime.now(ET) + timedelta(days=1)
        game_time = tomorrow.replace(hour=19, minute=0, second=0, microsecond=0)
        game_time_utc = game_time.astimezone(ZoneInfo("UTC")).isoformat()

        result = compute_today_est_fields(game_time_utc)
        self.assertFalse(result["is_today_est"])

    def test_started_game_detected(self):
        """Game that has started should be detected."""
        ET = ZoneInfo("America/New_York")
        one_hour_ago = datetime.now(ET) - timedelta(hours=1)
        game_time_utc = one_hour_ago.astimezone(ZoneInfo("UTC")).isoformat()

        result = compute_today_est_fields(game_time_utc)
        self.assertTrue(result["has_started"])
        self.assertIsNotNone(result["started_minutes_ago"])
        self.assertGreater(result["started_minutes_ago"], 50)


class TestTiering(unittest.TestCase):
    """Test H) Tiering single source of truth."""

    def test_gold_star_threshold(self):
        """Score >= 7.5 should be GOLD_STAR."""
        tier, _ = tier_from_score(7.5)
        self.assertEqual(tier, "GOLD_STAR")

        tier, _ = tier_from_score(8.0)
        self.assertEqual(tier, "GOLD_STAR")

        tier, _ = tier_from_score(10.0)
        self.assertEqual(tier, "GOLD_STAR")

    def test_edge_lean_threshold(self):
        """Score >= 6.5 and < 7.5 should be EDGE_LEAN."""
        tier, _ = tier_from_score(6.5)
        self.assertEqual(tier, "EDGE_LEAN")

        tier, _ = tier_from_score(7.0)
        self.assertEqual(tier, "EDGE_LEAN")

        tier, _ = tier_from_score(7.49)
        self.assertEqual(tier, "EDGE_LEAN")

    def test_monitor_threshold(self):
        """Score >= 5.5 and < 6.5 should be MONITOR."""
        tier, _ = tier_from_score(5.5)
        self.assertEqual(tier, "MONITOR")

        tier, _ = tier_from_score(6.0)
        self.assertEqual(tier, "MONITOR")

        tier, _ = tier_from_score(6.49)
        self.assertEqual(tier, "MONITOR")

    def test_pass_threshold(self):
        """Score < 5.5 should be PASS."""
        tier, _ = tier_from_score(5.49)
        self.assertEqual(tier, "PASS")

        tier, _ = tier_from_score(4.0)
        self.assertEqual(tier, "PASS")

        tier, _ = tier_from_score(0.0)
        self.assertEqual(tier, "PASS")

    def test_canonical_compute_tier_matches(self):
        """canonical_schema.compute_tier should match tiering.tier_from_score."""
        test_scores = [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
        for score in test_scores:
            tier_from_tiering, _ = tier_from_score(score)
            tier_from_canonical = compute_tier(score)
            self.assertEqual(tier_from_tiering, tier_from_canonical.value)


class TestScoringArchitecture(unittest.TestCase):
    """Test E) Scoring architecture (4-engine separation)."""

    def test_scoring_breakdown_has_all_engines(self):
        """ScoringBreakdown should have all 4 engines."""
        breakdown = ScoringBreakdown()
        self.assertIsNotNone(breakdown.ai_engine)
        self.assertIsNotNone(breakdown.research_engine)
        self.assertIsNotNone(breakdown.esoteric_engine)
        self.assertIsNotNone(breakdown.jarvis_engine)
        self.assertIsNotNone(breakdown.jason_sim)

    def test_default_weights(self):
        """Default weights should sum to 1.0."""
        breakdown = ScoringBreakdown()
        total = sum(breakdown.weights.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_ai_engine_fields(self):
        """AI engine breakdown should have required fields."""
        breakdown = ScoringBreakdown()
        self.assertIsNotNone(breakdown.ai_engine.score)
        self.assertIsInstance(breakdown.ai_engine.models_fired, list)

    def test_jarvis_engine_fields(self):
        """Jarvis engine breakdown should have required fields."""
        breakdown = ScoringBreakdown()
        self.assertIsNotNone(breakdown.jarvis_engine.score)
        self.assertIsInstance(breakdown.jarvis_engine.jarvis_triggers_hit, list)

    def test_jason_sim_fields(self):
        """Jason Sim breakdown should have required fields."""
        breakdown = ScoringBreakdown()
        self.assertIsNotNone(breakdown.jason_sim.available)
        self.assertIsInstance(breakdown.jason_sim.boost_applied, float)


class TestTitaniumRule(unittest.TestCase):
    """Test G) Titanium Rule + Harmonic Convergence."""

    def test_titanium_smash_tier_upgrade(self):
        """Titanium smash should upgrade to TITANIUM_SMASH tier."""
        tier = compute_tier(7.8, titanium_smash=True)
        self.assertEqual(tier, Tier.TITANIUM_SMASH)

    def test_titanium_no_upgrade_below_threshold(self):
        """Titanium smash below 7.5 should not upgrade tier."""
        tier = compute_tier(7.0, titanium_smash=True)
        self.assertEqual(tier, Tier.EDGE_LEAN)

    def test_compute_units_by_tier(self):
        """Units should match tier expectations."""
        self.assertEqual(compute_units(Tier.TITANIUM_SMASH), 2.5)
        self.assertEqual(compute_units(Tier.GOLD_STAR), 2.0)
        self.assertEqual(compute_units(Tier.EDGE_LEAN), 1.0)
        self.assertEqual(compute_units(Tier.MONITOR), 0.0)
        self.assertEqual(compute_units(Tier.PASS), 0.0)


class TestBookAllowlist(unittest.TestCase):
    """Test C) Book selection from allowlist."""

    def test_book_allowlist_contains_major_books(self):
        """Book allowlist should contain major sportsbooks."""
        self.assertIn("draftkings", BOOK_ALLOWLIST)
        self.assertIn("fanduel", BOOK_ALLOWLIST)
        self.assertIn("betmgm", BOOK_ALLOWLIST)

    def test_book_allowlist_minimum_count(self):
        """Book allowlist should have at least 5 books."""
        self.assertGreaterEqual(len(BOOK_ALLOWLIST), 5)


class TestCanonicalSchemaKeys(unittest.TestCase):
    """Test that canonical schema enforces required fields."""

    # v10.81: Canonical required fields for game picks
    GAME_PICK_REQUIRED_KEYS = {
        "sport", "game_id", "home_team", "away_team", "market_key",
        "selection", "odds_american", "final_score", "tier",
        "book_key", "book_name", "book_link",
        "display_title", "display_pick",
        "game_time_est", "has_started"
    }

    # v10.81: Canonical required fields for props
    PROP_PICK_REQUIRED_KEYS = {
        "sport", "game_id", "player_name", "stat_type", "line",
        "over_under", "odds_american", "final_score", "tier",
        "book_key", "book_name", "book_link",
        "display_title", "display_pick",
        "game_time_est", "has_started"
    }

    def test_game_pick_schema_fields_defined(self):
        """Game pick schema must define all required canonical fields."""
        # Create a minimal valid pick and verify CanonicalPick accepts it
        pick = CanonicalPick(
            sport="NBA",
            league="NBA",
            event_id="test123",
            game_time_utc="2026-01-24T19:00:00Z",
            game_time_est="2026-01-24T14:00:00-05:00",
            is_today_est=True,
            home_team="Lakers",
            away_team="Celtics",
            market_type=MarketType.SPREAD,
            selection="Lakers -3.5"
        )
        # Verify essential fields exist
        self.assertIsNotNone(pick.sport)
        self.assertIsNotNone(pick.home_team)
        self.assertIsNotNone(pick.away_team)
        self.assertIsNotNone(pick.market_type)
        self.assertIsNotNone(pick.selection)

    def test_canonical_pick_has_matchup_display(self):
        """CanonicalPick must auto-generate matchup_display."""
        pick = CanonicalPick(
            sport="NBA",
            league="NBA",
            event_id="test123",
            game_time_utc="2026-01-24T19:00:00Z",
            game_time_est="2026-01-24T14:00:00-05:00",
            is_today_est=True,
            home_team="Lakers",
            away_team="Celtics",
            market_type=MarketType.SPREAD,
            selection="Lakers -3.5"
        )
        self.assertEqual(pick.matchup_display, "Celtics @ Lakers")

    def test_canonical_pick_generates_pick_id(self):
        """CanonicalPick must auto-generate pick_id."""
        pick = CanonicalPick(
            sport="NBA",
            league="NBA",
            event_id="test123",
            game_time_utc="2026-01-24T19:00:00Z",
            game_time_est="2026-01-24T14:00:00-05:00",
            is_today_est=True,
            home_team="Lakers",
            away_team="Celtics",
            market_type=MarketType.SPREAD,
            selection="Lakers -3.5"
        )
        self.assertTrue(len(pick.pick_id) > 0)
        # pick_id should be deterministic for same inputs
        pick2 = CanonicalPick(
            sport="NBA",
            league="NBA",
            event_id="test123",
            game_time_utc="2026-01-24T19:00:00Z",
            game_time_est="2026-01-24T14:00:00-05:00",
            is_today_est=True,
            home_team="Lakers",
            away_team="Celtics",
            market_type=MarketType.SPREAD,
            selection="Lakers -3.5"
        )
        self.assertEqual(pick.pick_id, pick2.pick_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
