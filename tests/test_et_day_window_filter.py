"""
Test: ET Day Window Filter (TODAY-ONLY Gate)

REQUIREMENT: ALL picks MUST be for games in today's ET window ONLY.
Window: 12:01 AM ET (00:01:00) to 11:59 PM ET (23:59:00) - INCLUSIVE bounds

Single Source of Truth: core/time_et.py

Tests verify:
1. Day bounds are 00:00:00 to 23:59:59 ET
2. Events outside today's window are dropped
3. Events inside today's window are kept
4. Missing commence_time events are dropped
5. filter_events_et returns (kept, dropped_window, dropped_missing)
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.time_et import (
    now_et,
    et_day_bounds,
    is_in_et_day,
    filter_events_et,
)


ET = ZoneInfo("America/New_York")


class TestETDayBounds:
    """Test ET day boundary calculations"""

    def test_et_day_bounds_returns_correct_timezone(self):
        """Day bounds should be in America/New_York timezone"""
        start, end, date_str = et_day_bounds()

        assert start.tzinfo == ET, "Start should be in ET timezone"
        assert end.tzinfo == ET, "End should be in ET timezone"

    def test_et_day_bounds_starts_at_midnight(self):
        """Day should start at 00:00:00 ET"""
        start, end, date_str = et_day_bounds()

        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0

    def test_et_day_bounds_ends_at_next_midnight(self):
        """Day should end at 00:00:00 next day (exclusive upper bound)"""
        start, end, date_str = et_day_bounds()

        assert end.hour == 0
        assert end.minute == 0
        assert end.second == 0
        assert (end - start).days == 1, "Should span exactly 24 hours"

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


class TestIsInETDay:
    """Test is_in_et_day boundary checks"""

    def test_noon_is_in_today(self):
        """Noon ET should be in today's window"""
        start, end, today = et_day_bounds()
        noon = start.replace(hour=12, minute=0, second=0)

        assert is_in_et_day(noon.isoformat()) is True

    def test_midnight_start_is_in_today(self):
        """00:00:00 ET (start of day) should be in window"""
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

    def test_before_midnight_start_is_not_in_today(self):
        """23:59:59 previous day should NOT be in window"""
        start, end, today = et_day_bounds()
        before = start - timedelta(seconds=1)

        assert is_in_et_day(before.isoformat()) is False


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
