"""
Test: TODAY-ONLY ET window filtering.

REQUIREMENT: Events must be filtered to America/New_York day window [00:00:00, 23:59:59]
before generating picks. No tomorrow/yesterday leakage.
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from core.time_et import now_et, et_day_bounds, is_in_et_day, filter_events_et


def test_et_day_bounds_returns_midnight_to_midnight():
    """ET day bounds are [00:00:00, 00:00:00 next day) exclusive."""
    start, end, date_str = et_day_bounds()

    assert start.tzinfo == ZoneInfo("America/New_York")
    assert end.tzinfo == ZoneInfo("America/New_York")
    assert start.hour == 0
    assert start.minute == 0
    assert start.second == 0
    assert end.hour == 0
    assert end.minute == 0
    assert end.second == 0
    assert (end - start).days == 1


def test_filter_events_today_only():
    """Filter keeps only events in today's ET window."""
    start, end, today = et_day_bounds()

    # Event today at noon ET
    today_event = {
        "id": "1",
        "home_team": "Team A",
        "away_team": "Team B",
        "commence_time": (start + timedelta(hours=12)).isoformat()
    }

    # Event tomorrow
    tomorrow_event = {
        "id": "2",
        "home_team": "Team C",
        "away_team": "Team D",
        "commence_time": (end + timedelta(hours=1)).isoformat()
    }

    # Event yesterday
    yesterday_event = {
        "id": "3",
        "home_team": "Team E",
        "away_team": "Team F",
        "commence_time": (start - timedelta(hours=1)).isoformat()
    }

    events = [today_event, tomorrow_event, yesterday_event]
    kept, dropped_window, dropped_missing = filter_events_et(events)

    assert len(kept) == 1
    assert kept[0]["id"] == "1"
    assert len(dropped_window) == 2


def test_is_in_et_day_midnight_boundaries():
    """Test exact midnight boundaries (inclusive start, exclusive end)."""
    start, end, today = et_day_bounds()

    # Start of day (inclusive)
    assert is_in_et_day(start.isoformat()) is True

    # 1 second before end (still in day)
    just_before_end = end - timedelta(seconds=1)
    assert is_in_et_day(just_before_end.isoformat()) is True

    # Exactly end (exclusive)
    assert is_in_et_day(end.isoformat()) is False

    # After end
    after_end = end + timedelta(seconds=1)
    assert is_in_et_day(after_end.isoformat()) is False


def test_filter_events_handles_missing_commence_time():
    """Events with missing commence_time are dropped."""
    events = [
        {"id": "1", "home_team": "A", "away_team": "B", "commence_time": ""},
        {"id": "2", "home_team": "C", "away_team": "D"}  # Missing key
    ]

    kept, dropped_window, dropped_missing = filter_events_et(events)

    assert len(kept) == 0
    assert len(dropped_missing) == 2
