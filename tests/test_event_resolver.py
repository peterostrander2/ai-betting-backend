"""
Tests for Event ID Resolver (v14.10)
====================================

Tests the cross-provider event ID mapping functionality.
"""

import pytest
from datetime import datetime

# Import the event resolver
import sys
sys.path.insert(0, '/Users/apple/Documents/ai-betting-backend')

from identity.event_resolver import (
    EventResolver,
    ResolvedEvent,
    EventMatchMethod,
    get_event_resolver,
    resolve_event,
)


class TestEventResolver:
    """Tests for EventResolver class."""

    def setup_method(self):
        """Create a fresh resolver for each test."""
        self.resolver = EventResolver()

    def test_resolve_with_odds_api_id(self):
        """Test resolution with known Odds API ID returns confidence 1.0."""
        result = self.resolver.resolve_event(
            sport="NBA",
            home_team="Los Angeles Lakers",
            away_team="Boston Celtics",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="abc123def456"
        )

        assert result.is_resolved
        assert result.canonical_event_id == "NBA:ODDS:abc123def456"
        assert result.match_method == EventMatchMethod.EXACT_ID
        assert result.confidence == 1.0
        assert result.provider_ids["odds_api"] == "abc123def456"

    def test_resolve_without_odds_api_id(self):
        """Test resolution generates time-based ID when no Odds API ID."""
        result = self.resolver.resolve_event(
            sport="NBA",
            home_team="Los Angeles Lakers",
            away_team="Boston Celtics",
            commence_time="2026-01-26T19:00:00Z"
        )

        assert result.is_resolved
        assert result.canonical_event_id.startswith("NBA:TIME:")
        assert result.match_method == EventMatchMethod.TEAM_TIME_MATCH
        assert result.confidence == 0.85

    def test_cache_hit_with_same_odds_api_id(self):
        """Test that cached events are returned for same Odds API ID."""
        result1 = self.resolver.resolve_event(
            sport="NBA",
            home_team="Lakers",
            away_team="Celtics",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="xyz789"
        )

        result2 = self.resolver.resolve_event(
            sport="NBA",
            home_team="LA Lakers",  # Different format
            away_team="Boston",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="xyz789"
        )

        # Should return the same cached event
        assert result1.canonical_event_id == result2.canonical_event_id

    def test_provider_context_preserved(self):
        """Test that provider context is preserved and updated."""
        result = self.resolver.resolve_event(
            sport="NBA",
            home_team="Lakers",
            away_team="Celtics",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="odds123",
            provider_context={"balldontlie": "12345", "playbook": "PLY-001"}
        )

        assert result.provider_ids["odds_api"] == "odds123"
        assert result.provider_ids["balldontlie"] == "12345"
        assert result.provider_ids["playbook"] == "PLY-001"

    def test_link_provider_id(self):
        """Test linking additional provider IDs to existing event."""
        result = self.resolver.resolve_event(
            sport="NBA",
            home_team="Lakers",
            away_team="Celtics",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="odds123"
        )

        success = self.resolver.link_provider_id(
            result.canonical_event_id,
            "balldontlie",
            "12345"
        )

        assert success
        assert result.provider_ids["balldontlie"] == "12345"

    def test_link_provider_id_not_found(self):
        """Test linking to non-existent canonical ID returns False."""
        success = self.resolver.link_provider_id(
            "NONEXISTENT:ODDS:fake123",
            "balldontlie",
            "12345"
        )

        assert not success

    def test_get_by_provider_id(self):
        """Test lookup by provider ID."""
        self.resolver.resolve_event(
            sport="NBA",
            home_team="Lakers",
            away_team="Celtics",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="odds123",
            provider_context={"balldontlie": "12345"}
        )

        result = self.resolver.get_by_provider_id("balldontlie", "12345")
        assert result is not None
        assert "balldontlie" in result.provider_ids

        result2 = self.resolver.get_by_provider_id("odds_api", "odds123")
        assert result2 is not None

    def test_get_by_provider_id_not_found(self):
        """Test lookup for non-existent provider ID returns None."""
        result = self.resolver.get_by_provider_id("balldontlie", "nonexistent")
        assert result is None

    def test_different_sports_different_ids(self):
        """Test same team matchup in different sports gets different IDs."""
        nba_result = self.resolver.resolve_event(
            sport="NBA",
            home_team="Lakers",
            away_team="Celtics",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="nba123"
        )

        # Hypothetical same team names in different sport
        nfl_result = self.resolver.resolve_event(
            sport="NFL",
            home_team="Lakers",
            away_team="Celtics",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="nfl123"
        )

        assert nba_result.canonical_event_id != nfl_result.canonical_event_id
        assert nba_result.sport == "NBA"
        assert nfl_result.sport == "NFL"

    def test_update_event_status(self):
        """Test updating event status and scores."""
        result = self.resolver.resolve_event(
            sport="NBA",
            home_team="Lakers",
            away_team="Celtics",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="odds123"
        )

        assert result.status == "scheduled"

        success = self.resolver.update_event_status(
            result.canonical_event_id,
            status="final",
            home_score=110,
            away_score=105
        )

        assert success
        assert result.status == "final"
        assert result.home_score == 110
        assert result.away_score == 105

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = self.resolver.resolve_event(
            sport="NBA",
            home_team="Lakers",
            away_team="Celtics",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="odds123"
        )

        d = result.to_dict()

        assert d["canonical_event_id"] == "NBA:ODDS:odds123"
        assert d["sport"] == "NBA"
        assert d["home_team"] == "Lakers"
        assert d["away_team"] == "Celtics"
        assert d["match_method"] == "exact_id"
        assert d["confidence"] == 1.0

    def test_clear_cache(self):
        """Test clearing the cache."""
        self.resolver.resolve_event(
            sport="NBA",
            home_team="Lakers",
            away_team="Celtics",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="odds123"
        )

        stats_before = self.resolver.get_stats()
        assert stats_before["cached_events"] == 1

        self.resolver.clear()

        stats_after = self.resolver.get_stats()
        assert stats_after["cached_events"] == 0

    def test_get_stats(self):
        """Test getting resolver statistics."""
        self.resolver.resolve_event(
            sport="NBA",
            home_team="Lakers",
            away_team="Celtics",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="odds123"
        )

        stats = self.resolver.get_stats()

        assert "cached_events" in stats
        assert "time_index_size" in stats
        assert "provider_index_size" in stats
        assert stats["cached_events"] == 1


class TestEventResolverSingleton:
    """Tests for singleton and convenience functions."""

    def test_get_event_resolver_singleton(self):
        """Test that get_event_resolver returns singleton."""
        resolver1 = get_event_resolver()
        resolver2 = get_event_resolver()
        assert resolver1 is resolver2

    def test_resolve_event_convenience_function(self):
        """Test the resolve_event convenience function."""
        result = resolve_event(
            sport="NFL",
            home_team="Kansas City Chiefs",
            away_team="Buffalo Bills",
            commence_time="2026-01-26T16:30:00Z",
            odds_api_id="nfl_game_123"
        )

        assert result.is_resolved
        assert result.sport == "NFL"
        assert result.canonical_event_id == "NFL:ODDS:nfl_game_123"


class TestCanonicalIdFormat:
    """Tests for canonical ID format consistency."""

    def setup_method(self):
        self.resolver = EventResolver()

    def test_odds_id_format(self):
        """Test Odds API ID format: {SPORT}:ODDS:{id}"""
        result = self.resolver.resolve_event(
            sport="nba",  # lowercase input
            home_team="Lakers",
            away_team="Celtics",
            commence_time="2026-01-26T19:00:00Z",
            odds_api_id="abc123"
        )

        # Sport should be uppercase in canonical ID
        assert result.canonical_event_id == "NBA:ODDS:abc123"

    def test_time_based_id_format(self):
        """Test time-based ID format: {SPORT}:TIME:{away}@{home}:{epoch}"""
        result = self.resolver.resolve_event(
            sport="NBA",
            home_team="Los Angeles Lakers",
            away_team="Boston Celtics",
            commence_time="2026-01-26T19:00:00Z"
        )

        # Should be TIME-based with normalized team names
        assert result.canonical_event_id.startswith("NBA:TIME:")
        assert "@" in result.canonical_event_id

    def test_all_sports_supported(self):
        """Test all supported sports generate valid IDs."""
        sports = ["NBA", "NFL", "MLB", "NHL", "NCAAB"]

        for sport in sports:
            result = self.resolver.resolve_event(
                sport=sport,
                home_team="Home Team",
                away_team="Away Team",
                commence_time="2026-01-26T19:00:00Z",
                odds_api_id=f"{sport.lower()}_123"
            )

            assert result.is_resolved
            assert result.canonical_event_id.startswith(f"{sport}:ODDS:")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
