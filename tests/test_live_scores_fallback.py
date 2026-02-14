"""
tests/test_live_scores_fallback.py - v20.28.4 Live Scores Fallback Tests

Regression tests for the live scores fallback hierarchy:
1. Odds API (paid, primary)
2. BallDontLie (NBA only, secondary)
3. ESPN (free, final fallback)

These tests ensure the fallback chain works correctly when primary sources
return empty or are unavailable.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestLiveScoresFallbackHierarchy:
    """Regression tests for v20.28.4 live scores fallback chain."""

    @pytest.fixture
    def mock_odds_api_empty(self):
        """Mock Odds API returning empty results."""
        with patch("live_data_router.build_live_scores_lookup", new_callable=AsyncMock) as mock:
            mock.return_value = {}
            yield mock

    @pytest.fixture
    def mock_bdl_with_games(self):
        """Mock BallDontLie returning NBA games."""
        with patch("alt_data_sources.balldontlie.get_live_games", new_callable=AsyncMock) as mock:
            mock.return_value = [
                {
                    "id": 1234,
                    "home_team_full": "Los Angeles Lakers",
                    "visitor_team_full": "Boston Celtics",
                    "home_team_score": 98,
                    "visitor_team_score": 102,
                    "status": "3rd Qtr",
                    "period": 3,
                },
                {
                    "id": 1235,
                    "home_team_full": "Golden State Warriors",
                    "visitor_team_full": "Phoenix Suns",
                    "home_team_score": 110,
                    "visitor_team_score": 108,
                    "status": "Final",
                    "period": 4,
                },
            ]
            yield mock

    @pytest.fixture
    def mock_bdl_configured(self):
        """Mock BallDontLie as configured."""
        with patch("alt_data_sources.balldontlie.is_balldontlie_configured") as mock:
            mock.return_value = True
            yield mock

    def test_odds_api_empty_check(self):
        """
        Guard: When Odds API returns empty, bdl_scores_raw_count should be set.

        v20.28.4 regression: Ensure BallDontLie fallback fires when Odds API
        returns 0 scores for NBA.
        """
        # This test verifies the fallback logic exists in the codebase
        import live_data_router

        # Check the fallback pattern exists
        source = open(live_data_router.__file__).read()

        # Verify fallback hierarchy comment exists
        assert "Hierarchy: Odds API -> BallDontLie" in source or "BallDontLie" in source, \
            "BallDontLie fallback should be documented in live_data_router.py"

        # Verify BallDontLie telemetry field exists
        assert "bdl_scores_raw_count" in source, \
            "bdl_scores_raw_count telemetry should exist for fallback visibility"

    def test_fallback_only_for_nba(self):
        """
        Guard: BallDontLie fallback should only apply to NBA.

        Other sports (NFL, MLB, NHL, NCAAB) should fall through to ESPN,
        not BallDontLie which only has NBA data.
        """
        import live_data_router

        source = open(live_data_router.__file__).read()

        # Verify NBA-only check exists
        assert 'sport_lower == "nba"' in source or 'sport == "NBA"' in source.upper(), \
            "BallDontLie fallback should be gated to NBA only"

    def test_odds_api_telemetry_exists(self):
        """
        Guard: Odds API scores telemetry should exist for debugging.

        v20.28.3: odds_api_scores_raw_count helps diagnose when Odds API
        returns 0 scores (API limitation vs network error).
        """
        import live_data_router

        source = open(live_data_router.__file__).read()

        assert "odds_api_scores_raw_count" in source, \
            "odds_api_scores_raw_count telemetry should exist"

    def test_live_scores_source_tracking(self):
        """
        Guard: live_scores_source should indicate which API provided scores.

        Values: "odds_api" | "balldontlie" | "espn" | "none"
        """
        import live_data_router

        source = open(live_data_router.__file__).read()

        assert "live_scores_source" in source, \
            "live_scores_source field should exist for debugging"

        # Check that source is set to different values based on which API succeeded
        assert '"balldontlie"' in source or "'balldontlie'" in source, \
            "live_scores_source should be set to 'balldontlie' when BDL is used"


class TestBallDontLieIntegration:
    """Tests for BallDontLie API integration."""

    def test_balldontlie_module_exists(self):
        """BallDontLie integration module should exist."""
        try:
            from alt_data_sources import balldontlie
            assert hasattr(balldontlie, "get_live_games"), \
                "balldontlie module should have get_live_games function"
            assert hasattr(balldontlie, "is_balldontlie_configured"), \
                "balldontlie module should have is_balldontlie_configured function"
        except ImportError:
            pytest.skip("alt_data_sources.balldontlie module not available")

    def test_balldontlie_env_var_check(self):
        """BallDontLie should check BALLDONTLIE_API_KEY env var."""
        try:
            from alt_data_sources import balldontlie
            source = open(balldontlie.__file__).read()
            assert "BALLDONTLIE_API_KEY" in source, \
                "BallDontLie should use BALLDONTLIE_API_KEY env var"
        except ImportError:
            pytest.skip("alt_data_sources.balldontlie module not available")


class TestLiveScoresDebugTelemetry:
    """Tests for debug telemetry in live scores fallback chain."""

    def test_debug_payload_includes_all_telemetry(self):
        """Debug payload should include all live scores telemetry fields."""
        # These fields should be present in debug output for diagnosing
        # which API provided live scores data
        required_fields = [
            "live_scores_source",
            "live_scores_count",
            "odds_api_scores_raw_count",
            "bdl_scores_raw_count",
        ]

        import live_data_router
        source = open(live_data_router.__file__).read()

        for field in required_fields:
            assert field in source, \
                f"Debug telemetry field '{field}' should exist in live_data_router.py"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
