"""
Tests for PlayerDataService - v20.23

Tests the unified NBA player data service that provides:
- Season averages for props line difficulty assessment
- Birth dates for biorhythm calculations
- Player context for all engines

Covers:
- Cache behavior (sync/async)
- BallDontLie integration
- Static data fallback
- Line difficulty calculation
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_bdl_player():
    """Mock BallDontLie player response."""
    return {
        "id": 237,
        "first_name": "LeBron",
        "last_name": "James",
        "position": "F",
        "team": "Los Angeles Lakers",
        "team_abbreviation": "LAL",
        "birth_date": "1984-12-30",
    }


@pytest.fixture
def mock_bdl_season_avg():
    """Mock BallDontLie season averages response."""
    return {
        "pts": 25.7,
        "reb": 7.3,
        "ast": 8.3,
        "stl": 1.3,
        "blk": 0.5,
        "fg_pct": 0.540,
        "fg3_pct": 0.410,
        "fg3m": 2.1,
        "games_played": 55,
    }


@pytest.fixture
def mock_static_player():
    """Mock static player data."""
    return {
        "birth_date": "1984-12-30",
        "position": "F",
        "team": "LAL",
    }


# =============================================================================
# IMPORT TESTS
# =============================================================================

def test_player_data_service_import():
    """Test that PlayerDataService can be imported."""
    from services.player_data_service import (
        PlayerDataService,
        PlayerContext,
        calculate_line_difficulty,
    )
    assert PlayerDataService is not None
    assert PlayerContext is not None
    assert calculate_line_difficulty is not None


def test_player_context_dataclass():
    """Test PlayerContext dataclass initialization."""
    from services.player_data_service import PlayerContext

    ctx = PlayerContext(
        player_name="LeBron James",
        player_id=237,
        birth_date="1984-12-30",
        season_pts=25.7,
        season_reb=7.3,
        season_ast=8.3,
        data_source="test",
    )

    assert ctx.player_name == "LeBron James"
    assert ctx.player_id == 237
    assert ctx.birth_date == "1984-12-30"
    assert ctx.season_pts == 25.7
    assert ctx.has_season_data is True
    assert ctx.has_birth_date is True


def test_player_context_empty():
    """Test PlayerContext.empty() returns valid empty context."""
    from services.player_data_service import PlayerContext

    ctx = PlayerContext.empty("Unknown Player")

    assert ctx.player_name == "Unknown Player"
    assert ctx.data_source == "empty"
    assert ctx.has_season_data is False
    assert ctx.has_birth_date is False


def test_player_context_get_stat_average():
    """Test PlayerContext.get_stat_average() stat lookup."""
    from services.player_data_service import PlayerContext

    ctx = PlayerContext(
        player_name="Test Player",
        season_pts=20.5,
        season_reb=8.0,
        season_ast=5.0,
        season_threes=2.5,
        data_source="test",
    )

    # Various stat type aliases
    assert ctx.get_stat_average("points") == 20.5
    assert ctx.get_stat_average("pts") == 20.5
    assert ctx.get_stat_average("rebounds") == 8.0
    assert ctx.get_stat_average("reb") == 8.0
    assert ctx.get_stat_average("assists") == 5.0
    assert ctx.get_stat_average("threes") == 2.5
    assert ctx.get_stat_average("unknown_stat") is None


# =============================================================================
# LINE DIFFICULTY TESTS
# =============================================================================

def test_calculate_line_difficulty_soft_line():
    """Test line difficulty calculation for soft lines."""
    from services.player_data_service import calculate_line_difficulty

    # Line 16% below average = SOFT (threshold is < -15%)
    result = calculate_line_difficulty(
        prop_line=21.0,  # 16% below 25.0
        season_average=25.0,
        stat_type="points"
    )

    assert result["assessment"] == "SOFT"
    assert result["difficulty"] < 0
    assert result["adjustment"] > 0  # Positive adjustment for soft lines


def test_calculate_line_difficulty_hard_line():
    """Test line difficulty calculation for hard lines."""
    from services.player_data_service import calculate_line_difficulty

    # Line 20% above average = HARD
    result = calculate_line_difficulty(
        prop_line=30.0,  # 20% above 25.0
        season_average=25.0,
        stat_type="points"
    )

    assert result["assessment"] == "HARD"
    assert result["difficulty"] > 0
    assert result["adjustment"] < 0  # Negative adjustment for hard lines


def test_calculate_line_difficulty_fair_line():
    """Test line difficulty calculation for fair lines."""
    from services.player_data_service import calculate_line_difficulty

    # Line at average = FAIR
    result = calculate_line_difficulty(
        prop_line=25.0,
        season_average=25.0,
        stat_type="points"
    )

    assert result["assessment"] == "FAIR"
    assert abs(result["difficulty"]) < 0.1  # Near zero
    assert abs(result["adjustment"]) < 0.1  # Near zero


def test_calculate_line_difficulty_zero_average():
    """Test line difficulty handles zero average gracefully."""
    from services.player_data_service import calculate_line_difficulty

    result = calculate_line_difficulty(
        prop_line=10.0,
        season_average=0.0,
        stat_type="points"
    )

    assert result["assessment"] == "UNKNOWN"
    assert result["adjustment"] == 0.0


# =============================================================================
# SYNC CONTEXT TESTS
# =============================================================================

@patch("services.player_data_service.STATIC_DATA_AVAILABLE", True)
@patch("services.player_data_service.get_player_data")
def test_get_player_context_sync_static_fallback(mock_get_player):
    """Test sync context retrieval falls back to static data."""
    from services.player_data_service import PlayerDataService

    mock_get_player.return_value = {
        "birth_date": "1984-12-30",
        "position": "F",
        "team": "LAL",
    }

    # Clear cache for clean test
    PlayerDataService._cache.clear()

    ctx = PlayerDataService.get_player_context_sync("LeBron James", "NBA")

    assert ctx is not None
    assert ctx.player_name == "LeBron James"
    assert ctx.birth_date == "1984-12-30"
    # Static data doesn't have season averages
    assert ctx.data_source in ("static", "fallback", "cached")


def test_get_player_context_sync_non_nba():
    """Test sync context returns empty for non-NBA sports."""
    from services.player_data_service import PlayerDataService

    ctx = PlayerDataService.get_player_context_sync("Patrick Mahomes", "NFL")

    assert ctx is not None
    assert ctx.data_source == "empty"
    assert ctx.has_season_data is False


# =============================================================================
# LRU CACHE TESTS
# =============================================================================

def test_lru_cache_sync():
    """Test LRU cache sync operations."""
    from services.player_data_service import LRUCache, PlayerContext

    cache = LRUCache(max_size=3, ttl_seconds=3600)

    # Test set and get
    ctx1 = PlayerContext(player_name="Player 1", data_source="test")
    cache.set_sync("Player 1", ctx1)

    retrieved = cache.get_sync("Player 1")
    assert retrieved is not None
    assert retrieved.player_name == "Player 1"


def test_lru_cache_eviction():
    """Test LRU cache evicts oldest entries."""
    from services.player_data_service import LRUCache, PlayerContext

    cache = LRUCache(max_size=2, ttl_seconds=3600)

    # Add 3 items to cache with size 2
    for i in range(3):
        ctx = PlayerContext(player_name=f"Player {i}", data_source="test")
        cache.set_sync(f"Player {i}", ctx)

    # First player should be evicted
    assert cache.get_sync("Player 0") is None
    assert cache.get_sync("Player 1") is not None
    assert cache.get_sync("Player 2") is not None


def test_lru_cache_normalize_key():
    """Test cache normalizes player names."""
    from services.player_data_service import LRUCache, PlayerContext

    cache = LRUCache(max_size=10, ttl_seconds=3600)

    ctx = PlayerContext(player_name="LeBron James", data_source="test")
    cache.set_sync("LeBron James", ctx)

    # Should retrieve with different case/spacing
    assert cache.get_sync("lebron james") is not None
    assert cache.get_sync("LEBRON JAMES") is not None
    assert cache.get_sync(" lebron james ") is not None


# =============================================================================
# TELEMETRY TESTS
# =============================================================================

def test_telemetry_tracking():
    """Test service tracks telemetry correctly."""
    from services.player_data_service import PlayerDataService

    # Reset telemetry
    PlayerDataService.reset_telemetry()

    telemetry = PlayerDataService.get_telemetry()

    assert "cache_hits" in telemetry
    assert "static_fallbacks" in telemetry
    assert "empty_returns" in telemetry
    assert "cache_size" in telemetry


# =============================================================================
# TO_DICT TESTS
# =============================================================================

def test_player_context_to_dict():
    """Test PlayerContext serializes to dict correctly."""
    from services.player_data_service import PlayerContext

    ctx = PlayerContext(
        player_name="LeBron James",
        player_id=237,
        birth_date="1984-12-30",
        season_pts=25.7,
        season_reb=7.3,
        season_ast=8.3,
        season_pra=41.3,
        data_source="test",
    )

    d = ctx.to_dict()

    assert d["player_name"] == "LeBron James"
    assert d["player_id"] == 237
    assert d["birth_date"] == "1984-12-30"
    assert d["season_pts"] == 25.7
    assert d["has_season_data"] is True
    assert d["has_birth_date"] is True
    assert d["data_source"] == "test"


# =============================================================================
# EDGE CASES
# =============================================================================

def test_empty_player_name():
    """Test handling of empty player name."""
    from services.player_data_service import PlayerDataService

    ctx = PlayerDataService.get_player_context_sync("", "NBA")

    # Should return empty context for empty name
    assert ctx is not None
    assert ctx.data_source in ("empty", "fallback")


def test_special_characters_in_name():
    """Test handling of special characters in player names."""
    from services.player_data_service import PlayerDataService

    # Players with accents/special chars
    ctx = PlayerDataService.get_player_context_sync("Nikola Jokić", "NBA")

    assert ctx is not None  # Should not crash


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
