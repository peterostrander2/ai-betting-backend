"""
Test: ET Day Window Filter (TODAY-ONLY Gate)

REQUIREMENT: ALL picks MUST be for games in today's ET window ONLY.

CANONICAL ET SLATE WINDOW (HARD RULE):
    Start: 00:01:00 America/New_York (12:01 AM ET) - inclusive
    End:   00:00:00 America/New_York next day (midnight) - exclusive
    Interval: [start, end)

Single Source of Truth: core/time_et.py

Tests verify:
1. Day bounds start at 00:01:00 ET (NOT midnight)
2. Day bounds end at 00:00:00 next day (exclusive)
3. Events outside today's window are dropped
4. Events inside today's window are kept
5. Events at exactly 00:00:00 (midnight) are EXCLUDED (belong to previous day)
6. Events at 00:00:30 are EXCLUDED (before 00:01:00 start)
7. Events at 00:01:00 are INCLUDED
8. filter_events_et returns (kept, dropped_window, dropped_missing)
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.time_et import (
    now_et,
    et_day_bounds,
    is_in_et_day,
    filter_events_et,
    within_et_bounds,
    assert_et_bounds,
    ET_SLATE_START_TIME,
)


ET = ZoneInfo("America/New_York")


class TestETDayBounds:
    """Test ET day boundary calculations"""

    def test_et_day_bounds_returns_correct_timezone(self):
        """Day bounds should be in America/New_York timezone"""
        start, end, date_str = et_day_bounds()

        assert start.tzinfo == ET, "Start should be in ET timezone"
        assert end.tzinfo == ET, "End should be in ET timezone"

    def test_et_day_bounds_starts_at_0001(self):
        """CANONICAL: Day should start at 00:01:00 ET (NOT midnight)"""
        start, end, date_str = et_day_bounds()

        assert start.hour == 0
        assert start.minute == 1
        assert start.second == 0

    def test_et_day_bounds_ends_at_next_midnight(self):
        """Day should end at 00:00:00 next day (exclusive upper bound)"""
        start, end, date_str = et_day_bounds()

        assert end.hour == 0
        assert end.minute == 0
        assert end.second == 0
        # Duration: 23 hours 59 minutes (from 00:01:00 to next day 00:00:00)
        duration = end - start
        assert duration.total_seconds() == 23 * 3600 + 59 * 60, "Should span 23h 59m"

    def test_et_day_bounds_returns_date_string(self):
        """Should return date string in YYYY-MM-DD format"""
        start, end, date_str = et_day_bounds()

        assert isinstance(date_str, str)
        assert len(date_str) == 10, "Date should be YYYY-MM-DD format"
        assert date_str.count("-") == 2

    def test_et_day_bounds_for_specific_date(self):
        """Can get bounds for a specific date"""
        start, end, date_str = et_day_bounds("2026-01-29")

        assert date_str == "2026-01-29"
        assert start.year == 2026
        assert start.month == 1
        assert start.day == 29
        assert start.hour == 0
        assert start.minute == 1  # 00:01:00 start


class TestIsInETDay:
    """Test is_in_et_day boundary checks"""

    def test_noon_is_in_today(self):
        """Noon ET should be in today's window"""
        start, end, today = et_day_bounds()
        noon = start.replace(hour=12, minute=0, second=0)

        assert is_in_et_day(noon.isoformat()) is True

    def test_0001_start_is_in_today(self):
        """00:01:00 ET (canonical start of day) should be in window"""
        start, end, today = et_day_bounds()

        assert is_in_et_day(start.isoformat()) is True

    def test_just_before_midnight_is_in_today(self):
        """23:59:59 ET should be in window"""
        start, end, today = et_day_bounds()
        just_before = end - timedelta(seconds=1)

        assert is_in_et_day(just_before.isoformat()) is True

    def test_midnight_end_is_not_in_today(self):
        """00:00:00 next day (end) should NOT be in window (exclusive)"""
        start, end, today = et_day_bounds()

        assert is_in_et_day(end.isoformat()) is False

    def test_after_midnight_is_not_in_today(self):
        """00:00:01 next day should NOT be in window"""
        start, end, today = et_day_bounds()
        after = end + timedelta(seconds=1)

        assert is_in_et_day(after.isoformat()) is False

    def test_before_0001_is_not_in_today(self):
        """00:00:59 same day (before 00:01:00 start) should NOT be in window"""
        start, end, today = et_day_bounds()
        before = start - timedelta(seconds=1)  # 00:00:59

        assert is_in_et_day(before.isoformat()) is False

    def test_midnight_exactly_is_not_in_today(self):
        """CRITICAL: 00:00:00 ET should NOT be in window (belongs to previous day)"""
        start, end, today = et_day_bounds()
        midnight = start.replace(hour=0, minute=0, second=0)

        assert is_in_et_day(midnight.isoformat()) is False

    def test_00_00_30_is_not_in_today(self):
        """CRITICAL: 00:00:30 ET should NOT be in window (before 00:01:00 start)"""
        start, end, today = et_day_bounds()
        time_00_00_30 = start.replace(hour=0, minute=0, second=30)

        assert is_in_et_day(time_00_00_30.isoformat()) is False

    def test_00_01_00_is_in_today(self):
        """CRITICAL: 00:01:00 ET should be in window (canonical start)"""
        start, end, today = et_day_bounds()
        time_00_01_00 = start.replace(hour=0, minute=1, second=0)

        assert is_in_et_day(time_00_01_00.isoformat()) is True


class TestAssertETBounds:
    """Test assert_et_bounds validation function"""

    def test_valid_bounds_pass_all_checks(self):
        """Correctly formed bounds should pass all validation checks"""
        start, end, _ = et_day_bounds()
        result = assert_et_bounds(start, end)

        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["checks"]["start_is_0001"] is True
        assert result["checks"]["end_is_midnight"] is True
        assert result["checks"]["spans_to_next_day"] is True

    def test_invalid_start_time_fails(self):
        """Start time not at 00:01:00 should fail validation"""
        from datetime import time
        day = now_et().date()
        # Wrong start time: 00:00:00 instead of 00:01:00
        bad_start = datetime.combine(day, time(0, 0, 0), tzinfo=ET)
        end = datetime.combine(day + timedelta(days=1), time(0, 0, 0), tzinfo=ET)

        result = assert_et_bounds(bad_start, end)

        assert result["valid"] is False
        assert result["checks"]["start_is_0001"] is False


class TestFilterEventsET:
    """Test filter_events_et function"""

    def test_filter_keeps_today_events(self):
        """Events within today's ET window should be kept"""
        start, end, today = et_day_bounds()

        events = [
            {
                "id": "game1",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "commence_time": (start + timedelta(hours=12)).isoformat()
            },
            {
                "id": "game2",
                "home_team": "Heat",
                "away_team": "Bulls",
                "commence_time": (start + timedelta(hours=19)).isoformat()
            },
        ]

        kept, dropped_window, dropped_missing = filter_events_et(events, today)

        assert len(kept) == 2
        assert len(dropped_window) == 0
        assert len(dropped_missing) == 0

    def test_filter_drops_tomorrow_events(self):
        """Events after today's window should be dropped"""
        start, end, today = et_day_bounds()

        events = [
            {
                "id": "tomorrow_game",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "commence_time": (end + timedelta(hours=12)).isoformat()
            },
        ]

        kept, dropped_window, dropped_missing = filter_events_et(events, today)

        assert len(kept) == 0
        assert len(dropped_window) == 1
        assert dropped_window[0]["id"] == "tomorrow_game"

    def test_filter_drops_yesterday_events(self):
        """Events before today's window should be dropped"""
        start, end, today = et_day_bounds()

        events = [
            {
                "id": "yesterday_game",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "commence_time": (start - timedelta(hours=12)).isoformat()
            },
        ]

        kept, dropped_window, dropped_missing = filter_events_et(events, today)

        assert len(kept) == 0
        assert len(dropped_window) == 1

    def test_filter_drops_missing_commence_time(self):
        """Events with missing commence_time should go to dropped_missing"""
        events = [
            {"id": "no_time", "home_team": "A", "away_team": "B", "commence_time": ""},
            {"id": "null_time", "home_team": "C", "away_team": "D"},  # Missing key
        ]

        kept, dropped_window, dropped_missing = filter_events_et(events)

        assert len(kept) == 0
        assert len(dropped_missing) == 2

    def test_filter_mixed_events(self):
        """Test filtering with mix of today/tomorrow/missing"""
        start, end, today = et_day_bounds()

        events = [
            # Today - KEEP
            {"id": "today1", "commence_time": (start + timedelta(hours=12)).isoformat()},
            {"id": "today2", "commence_time": (start + timedelta(hours=19)).isoformat()},
            # Tomorrow - DROP (window)
            {"id": "tomorrow", "commence_time": (end + timedelta(hours=5)).isoformat()},
            # Yesterday - DROP (window)
            {"id": "yesterday", "commence_time": (start - timedelta(hours=5)).isoformat()},
            # Missing - DROP (missing)
            {"id": "missing", "commence_time": ""},
        ]

        kept, dropped_window, dropped_missing = filter_events_et(events, today)

        assert len(kept) == 2
        assert len(dropped_window) == 2  # tomorrow + yesterday
        assert len(dropped_missing) == 1

        kept_ids = [e["id"] for e in kept]
        assert "today1" in kept_ids
        assert "today2" in kept_ids

    def test_filter_returns_three_lists(self):
        """filter_events_et should return tuple of 3 lists"""
        result = filter_events_et([])

        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], list)  # kept
        assert isinstance(result[1], list)  # dropped_window
        assert isinstance(result[2], list)  # dropped_missing


class TestETFilterIntegration:
    """Test ET filtering integration with real-world scenarios"""

    def test_late_night_game_handling(self):
        """Late night games (10 PM ET) should be included"""
        start, end, today = et_day_bounds()
        late_game = start.replace(hour=22, minute=0)  # 10 PM ET

        events = [{"id": "late", "commence_time": late_game.isoformat()}]
        kept, dropped_window, dropped_missing = filter_events_et(events, today)

        assert len(kept) == 1, "10 PM game should be in today's window"

    def test_early_morning_game_handling(self):
        """Early morning games (6 AM ET) should be included"""
        start, end, today = et_day_bounds()
        early_game = start.replace(hour=6, minute=0)  # 6 AM ET

        events = [{"id": "early", "commence_time": early_game.isoformat()}]
        kept, dropped_window, dropped_missing = filter_events_et(events, today)

        assert len(kept) == 1, "6 AM game should be in today's window"

    def test_utc_time_converted_correctly(self):
        """UTC times should be converted to ET for comparison"""
        start, end, today = et_day_bounds()

        # Create a UTC time that's noon ET
        utc_time = start.astimezone(ZoneInfo("UTC")) + timedelta(hours=12)

        events = [{"id": "utc_game", "commence_time": utc_time.isoformat()}]
        kept, dropped_window, dropped_missing = filter_events_et(events, today)

        assert len(kept) == 1, "UTC time should be converted to ET correctly"


class TestCanonicalBoundaryEdgeCases:
    """
    Test canonical boundary edge cases: 00:00:30 (EXCLUDE), 00:01:00 (INCLUDE)

    These tests verify the HARD RULE:
        Start: 00:01:00 ET (inclusive)
        End:   00:00:00 ET next day (exclusive)
    """

    def test_00_00_30_et_excluded(self):
        """CRITICAL: Event at 00:00:30 ET MUST be EXCLUDED (before 00:01:00 start)"""
        start, end, today = et_day_bounds()

        # Create event at 00:00:30 ET on the same day
        event_time = start.replace(hour=0, minute=0, second=30)

        events = [{"id": "early_bird", "commence_time": event_time.isoformat()}]
        kept, dropped_window, dropped_missing = filter_events_et(events, today)

        assert len(kept) == 0, "00:00:30 ET should be EXCLUDED"
        assert len(dropped_window) == 1, "00:00:30 ET should be in dropped_window"

    def test_00_01_00_et_included(self):
        """CRITICAL: Event at exactly 00:01:00 ET MUST be INCLUDED"""
        start, end, today = et_day_bounds()

        # The start IS 00:01:00
        events = [{"id": "first_minute", "commence_time": start.isoformat()}]
        kept, dropped_window, dropped_missing = filter_events_et(events, today)

        assert len(kept) == 1, "00:01:00 ET should be INCLUDED"
        assert kept[0]["id"] == "first_minute"

    def test_23_59_59_et_included(self):
        """Event at 23:59:59 ET MUST be INCLUDED"""
        start, end, today = et_day_bounds()

        # 1 second before end
        last_second = end - timedelta(seconds=1)

        events = [{"id": "last_second", "commence_time": last_second.isoformat()}]
        kept, dropped_window, dropped_missing = filter_events_et(events, today)

        assert len(kept) == 1, "23:59:59 ET should be INCLUDED"

    def test_00_00_00_next_day_excluded(self):
        """CRITICAL: Event at 00:00:00 next day MUST be EXCLUDED (end is exclusive)"""
        start, end, today = et_day_bounds()

        # The end is midnight next day
        events = [{"id": "midnight_next", "commence_time": end.isoformat()}]
        kept, dropped_window, dropped_missing = filter_events_et(events, today)

        assert len(kept) == 0, "00:00:00 next day should be EXCLUDED"
        assert len(dropped_window) == 1

    def test_within_et_bounds_function_directly(self):
        """Test within_et_bounds helper function"""
        start, end, today = et_day_bounds()

        # Test various times
        noon = start.replace(hour=12, minute=0, second=0)
        before_start = start - timedelta(seconds=1)
        at_end = end

        assert within_et_bounds(noon.isoformat(), start, end) is True
        assert within_et_bounds(before_start.isoformat(), start, end) is False
        assert within_et_bounds(at_end.isoformat(), start, end) is False

    def test_fetch_filters_events_by_et_bounds(self):
        """
        Integration test: Mocked provider events around boundaries.

        Events:
        - 00:00:30 ET (must EXCLUDE)
        - 00:01:00 ET (INCLUDE)
        - 23:59:59 ET (INCLUDE)
        - 00:00:00 next day (EXCLUDE)
        """
        start, end, today = et_day_bounds()

        events = [
            # EXCLUDE: Before canonical start
            {"id": "too_early", "commence_time": start.replace(hour=0, minute=0, second=30).isoformat()},
            # INCLUDE: Exactly at canonical start
            {"id": "first_valid", "commence_time": start.isoformat()},
            # INCLUDE: Last valid second
            {"id": "last_valid", "commence_time": (end - timedelta(seconds=1)).isoformat()},
            # EXCLUDE: At exclusive end
            {"id": "next_day", "commence_time": end.isoformat()},
        ]

        kept, dropped_window, dropped_missing = filter_events_et(events, today)

        # Check counts
        assert len(kept) == 2, f"Expected 2 kept, got {len(kept)}"
        assert len(dropped_window) == 2, f"Expected 2 dropped, got {len(dropped_window)}"

        # Check which events were kept
        kept_ids = [e["id"] for e in kept]
        assert "first_valid" in kept_ids
        assert "last_valid" in kept_ids

        # Check which events were dropped
        dropped_ids = [e["id"] for e in dropped_window]
        assert "too_early" in dropped_ids
        assert "next_day" in dropped_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
