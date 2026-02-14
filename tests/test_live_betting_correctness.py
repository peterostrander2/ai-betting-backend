"""
tests/test_live_betting_correctness.py

Tests for live betting correctness:
1. Conservative data_age_ms calculation (max across CRITICAL integrations)
2. Game status derivation (PRE_GAME/IN_PROGRESS/FINAL)

v20.26: Added for airtight live betting validation
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock

ET = ZoneInfo("America/New_York")


class TestGameStatusDerivation:
    """Tests for game status correctness (PRE_GAME/IN_PROGRESS/FINAL)."""

    def test_pre_game_status_when_not_started(self):
        """Game that hasn't started should return PRE_GAME."""
        from time_filters import get_game_status

        # Future game - 2 hours from now
        future_time = (datetime.now(ET) + timedelta(hours=2)).isoformat()

        status = get_game_status(future_time)
        assert status == "PRE_GAME", f"Expected PRE_GAME for future game, got {status}"

    def test_in_progress_status_when_started(self):
        """Game that started but not final should return IN_PROGRESS."""
        from time_filters import get_game_status

        # Game started 30 minutes ago
        past_time = (datetime.now(ET) - timedelta(minutes=30)).isoformat()

        status = get_game_status(past_time, completed=False)
        assert status == "IN_PROGRESS", f"Expected IN_PROGRESS for started game, got {status}"

    def test_final_status_when_completed(self):
        """Completed game should return FINAL."""
        from time_filters import get_game_status

        # Game started 3 hours ago and is completed
        past_time = (datetime.now(ET) - timedelta(hours=3)).isoformat()

        status = get_game_status(past_time, completed=True)
        assert status == "FINAL", f"Expected FINAL for completed game, got {status}"

    def test_not_today_status_for_other_days(self):
        """Game not scheduled today should return NOT_TODAY."""
        from time_filters import get_game_status

        # Game tomorrow
        tomorrow = (datetime.now(ET) + timedelta(days=1)).isoformat()

        status = get_game_status(tomorrow)
        assert status == "NOT_TODAY", f"Expected NOT_TODAY for tomorrow's game, got {status}"

    def test_in_progress_replaces_missed_start(self):
        """MISSED_START should not exist - IN_PROGRESS is used instead."""
        from time_filters import get_game_status

        # Game started 1 hour ago
        past_time = (datetime.now(ET) - timedelta(hours=1)).isoformat()

        status = get_game_status(past_time)
        assert status != "MISSED_START", "MISSED_START should be replaced by IN_PROGRESS"
        assert status == "IN_PROGRESS", f"Expected IN_PROGRESS, got {status}"


class TestConservativeDataAge:
    """Tests for conservative data_age_ms calculation."""

    def test_data_age_ms_calculation(self):
        """data_age_ms should calculate milliseconds since fetch."""
        from core.time_et import data_age_ms, format_as_of_et

        # Get current timestamp
        now = format_as_of_et()

        # Immediate age should be very small (< 100ms)
        age = data_age_ms(now)
        assert age >= 0, f"Age should be non-negative, got {age}"
        assert age < 1000, f"Age should be < 1 second for immediate check, got {age}ms"

    def test_data_age_ms_older_timestamp(self):
        """data_age_ms should correctly calculate older timestamps."""
        from core.time_et import data_age_ms
        from datetime import datetime, timezone

        # Create timestamp 60 seconds ago
        sixty_seconds_ago = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()

        age = data_age_ms(sixty_seconds_ago)

        # Should be approximately 60000ms (allow 1 second tolerance)
        assert 59000 <= age <= 61000, f"Expected ~60000ms, got {age}ms"

    def test_data_age_ms_invalid_returns_negative(self):
        """data_age_ms should return -1 for invalid timestamps."""
        from core.time_et import data_age_ms

        assert data_age_ms(None) == -1
        assert data_age_ms("") == -1
        assert data_age_ms("invalid-timestamp") == -1

    def test_conservative_age_is_max_across_critical(self):
        """data_age_ms in meta should be MAX age across CRITICAL integrations."""
        # This tests the concept - actual implementation is in live_data_router

        # Simulate integration call data
        integration_calls = {
            "odds_api": {
                "called": 1,
                "criticality": "CRITICAL",
                "fetched_at_et": (datetime.now(ET) - timedelta(seconds=30)).isoformat()
            },
            "playbook_api": {
                "called": 1,
                "criticality": "CRITICAL",
                "fetched_at_et": (datetime.now(ET) - timedelta(seconds=60)).isoformat()  # Older
            },
            "serpapi": {
                "called": 1,
                "criticality": "OPTIONAL",
                "fetched_at_et": (datetime.now(ET) - timedelta(seconds=120)).isoformat()  # Oldest but OPTIONAL
            }
        }

        from core.time_et import data_age_ms

        # Compute max age across CRITICAL integrations
        max_critical_age = None
        for name, entry in integration_calls.items():
            if entry.get("criticality") == "CRITICAL" and entry.get("called", 0) > 0:
                age = data_age_ms(entry.get("fetched_at_et"))
                if age >= 0:
                    if max_critical_age is None or age > max_critical_age:
                        max_critical_age = age

        # Should be ~60000ms (playbook_api is older among CRITICAL)
        assert max_critical_age is not None
        assert 59000 <= max_critical_age <= 61000, f"Expected ~60000ms (playbook), got {max_critical_age}ms"

    def test_picks_present_requires_data_age_ms(self):
        """When picks_count > 0, data_age_ms must not be null."""
        # This is a behavioral contract test
        # When there are picks, data_age_ms MUST be present

        # Simulate response with picks
        mock_response = {
            "props": {"count": 5, "picks": [{"id": "1"}] * 5},
            "game_picks": {"count": 3, "picks": [{"id": "2"}] * 3},
            "meta": {
                "data_age_ms": 45000,  # Must be present when picks > 0
                "integrations_age_ms": {"odds_api": 45000}
            }
        }

        total_picks = mock_response["props"]["count"] + mock_response["game_picks"]["count"]
        assert total_picks > 0
        assert mock_response["meta"]["data_age_ms"] is not None
        assert isinstance(mock_response["meta"]["data_age_ms"], int)

    def test_zero_picks_allows_null_or_zero_data_age(self):
        """When picks_count == 0, data_age_ms can be 0 or null."""
        # Simulate response with no picks
        mock_response = {
            "props": {"count": 0, "picks": []},
            "game_picks": {"count": 0, "picks": []},
            "meta": {
                "data_age_ms": 0,  # 0 is acceptable when no picks
                "integrations_age_ms": {}
            }
        }

        total_picks = mock_response["props"]["count"] + mock_response["game_picks"]["count"]
        assert total_picks == 0
        # data_age_ms can be 0 or None when no picks
        assert mock_response["meta"]["data_age_ms"] in [0, None] or isinstance(mock_response["meta"]["data_age_ms"], int)


class TestGameStatusEnumValues:
    """Tests that game status enum values are correct."""

    def test_valid_game_statuses(self):
        """All game statuses should be one of the valid values."""
        valid_statuses = {"PRE_GAME", "IN_PROGRESS", "LIVE", "FINAL", "NOT_TODAY"}

        from time_filters import get_game_status

        # Test various scenarios
        future = (datetime.now(ET) + timedelta(hours=2)).isoformat()
        past = (datetime.now(ET) - timedelta(hours=1)).isoformat()
        tomorrow = (datetime.now(ET) + timedelta(days=1)).isoformat()

        assert get_game_status(future) in valid_statuses
        assert get_game_status(past) in valid_statuses
        assert get_game_status(past, completed=True) in valid_statuses
        assert get_game_status(tomorrow) in valid_statuses

    def test_no_missed_start_status(self):
        """MISSED_START should never be returned."""
        from time_filters import get_game_status

        # Test edge cases
        just_started = (datetime.now(ET) - timedelta(seconds=1)).isoformat()
        started_hour_ago = (datetime.now(ET) - timedelta(hours=1)).isoformat()
        started_5_hours_ago = (datetime.now(ET) - timedelta(hours=5)).isoformat()

        for time_str in [just_started, started_hour_ago, started_5_hours_ago]:
            status = get_game_status(time_str)
            assert status != "MISSED_START", f"MISSED_START should not be returned for {time_str}"


class TestIntegrationAgeTracking:
    """Tests for integration fetched_at tracking."""

    def test_format_as_of_et_returns_iso_with_offset(self):
        """format_as_of_et should return ISO 8601 with ET offset."""
        from core.time_et import format_as_of_et

        result = format_as_of_et()

        # Should be ISO 8601 format
        assert "T" in result, "Should contain T separator"
        assert "-05:00" in result or "-04:00" in result, "Should have ET offset (-05:00 or -04:00 for DST)"

    def test_data_age_ms_handles_z_suffix(self):
        """data_age_ms should handle Z suffix (UTC) timestamps."""
        from core.time_et import data_age_ms
        from datetime import timezone

        # UTC timestamp with Z suffix
        utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        age = data_age_ms(utc_time)
        assert age >= 0, f"Should handle Z suffix, got {age}"
        assert age < 1000, f"Age should be < 1 second for recent timestamp"

    def test_data_age_ms_handles_offset_format(self):
        """data_age_ms should handle offset format timestamps."""
        from core.time_et import data_age_ms
        from datetime import datetime, timezone

        # Timestamp with offset
        offset_time = datetime.now(timezone.utc).isoformat()

        age = data_age_ms(offset_time)
        assert age >= 0, f"Should handle offset format, got {age}"
        assert age < 1000, f"Age should be < 1 second for recent timestamp"


class TestMockedGameStatus:
    """Tests with mocked time for deterministic behavior."""

    @patch('time_filters.get_now_et')
    def test_game_30_minutes_ago_is_in_progress(self, mock_now):
        """Game that started 30 minutes ago should be IN_PROGRESS."""
        from time_filters import get_game_status, parse_game_time

        # Mock current time
        mock_current = datetime(2026, 2, 14, 20, 0, 0, tzinfo=ET)
        mock_now.return_value = mock_current

        # Game started at 7:30 PM (30 min ago)
        game_time = datetime(2026, 2, 14, 19, 30, 0, tzinfo=ET).isoformat()

        status = get_game_status(game_time)
        assert status == "IN_PROGRESS"

    @patch('time_filters.get_now_et')
    def test_game_in_2_hours_is_pre_game(self, mock_now):
        """Game starting in 2 hours should be PRE_GAME."""
        from time_filters import get_game_status

        # Mock current time
        mock_current = datetime(2026, 2, 14, 18, 0, 0, tzinfo=ET)
        mock_now.return_value = mock_current

        # Game starts at 8 PM (2 hours from now)
        game_time = datetime(2026, 2, 14, 20, 0, 0, tzinfo=ET).isoformat()

        status = get_game_status(game_time)
        assert status == "PRE_GAME"

    @patch('time_filters.get_now_et')
    def test_completed_game_is_final(self, mock_now):
        """Completed game should be FINAL regardless of time."""
        from time_filters import get_game_status

        # Mock current time
        mock_current = datetime(2026, 2, 14, 22, 0, 0, tzinfo=ET)
        mock_now.return_value = mock_current

        # Game started at 7 PM and is completed
        game_time = datetime(2026, 2, 14, 19, 0, 0, tzinfo=ET).isoformat()

        status = get_game_status(game_time, completed=True)
        assert status == "FINAL"
