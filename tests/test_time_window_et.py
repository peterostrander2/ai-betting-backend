"""
Test: TODAY-ONLY ET window filtering.

CANONICAL ET SLATE WINDOW (HARD RULE):
    Start: 00:00:00 America/New_York (midnight ET) - inclusive
    End:   00:00:00 America/New_York next day (midnight) - exclusive
    Interval: [start, end)

Events must be filtered to this window before generating picks.
No tomorrow/yesterday leakage.
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from core.time_et import now_et, et_day_bounds, is_in_et_day, filter_events_et


def test_et_day_bounds_returns_0001_to_next_midnight():
    """CANONICAL: ET day bounds are [00:00:00, 00:00:00 next day) exclusive."""
    start, end, start_utc, end_utc = et_day_bounds()
    date_str = start.date().isoformat()

    assert start.tzinfo == ZoneInfo("America/New_York")
    assert end.tzinfo == ZoneInfo("America/New_York")
    assert start.hour == 0
    assert start.minute == 0  # CANONICAL: 00:00:00 start
    assert start.second == 0
    assert end.hour == 0
    assert end.minute == 0
    assert end.second == 0
    # Duration: 24 hours
    duration = end - start
    assert duration.total_seconds() == 24 * 3600


def test_filter_events_today_only():
    """Filter keeps only events in today's ET window."""
    start, end, start_utc, end_utc = et_day_bounds()
    today = start.date().isoformat()

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


def test_is_in_et_day_canonical_boundaries():
    """Test canonical boundaries: 00:00:00 start (inclusive), 00:00:00 next day (exclusive)."""
    start, end, start_utc, end_utc = et_day_bounds()
    today = start.date().isoformat()

    # Start of day at 00:00:00 (inclusive)
    assert is_in_et_day(start.isoformat()) is True

    # 1 second before end (still in day)
    just_before_end = end - timedelta(seconds=1)
    assert is_in_et_day(just_before_end.isoformat()) is True

    # Exactly end (exclusive)
    assert is_in_et_day(end.isoformat()) is False

    # After end
    after_end = end + timedelta(seconds=1)
    assert is_in_et_day(after_end.isoformat()) is False

    # Before start (23:59:30 previous day - should be excluded)
    before_start = start - timedelta(seconds=30)
    assert is_in_et_day(before_start.isoformat()) is False


def test_filter_events_handles_missing_commence_time():
    """Events with missing commence_time are dropped."""
    events = [
        {"id": "1", "home_team": "A", "away_team": "B", "commence_time": ""},
        {"id": "2", "home_team": "C", "away_team": "D"}  # Missing key
    ]

    kept, dropped_window, dropped_missing = filter_events_et(events)

    assert len(kept) == 0
    assert len(dropped_missing) == 2


def test_midnight_included_in_window():
    """CANONICAL: 00:00:00 ET should be INCLUDED (midnight start)."""
    start, end, start_utc, end_utc = et_day_bounds()
    today = start.date().isoformat()

    # Create midnight timestamp
    midnight = start.replace(hour=0, minute=0, second=0)

    assert is_in_et_day(midnight.isoformat()) is True


def test_canonical_boundary_events():
    """Test events at canonical boundary times."""
    start, end, start_utc, end_utc = et_day_bounds()
    today = start.date().isoformat()

    events = [
        # INCLUDE: 00:00:30 (after midnight start)
        {"id": "after_start", "commence_time": start.replace(hour=0, minute=0, second=30).isoformat()},
        # INCLUDE: 00:00:00 (exactly at start)
        {"id": "at_start", "commence_time": start.isoformat()},
        # INCLUDE: noon
        {"id": "noon", "commence_time": start.replace(hour=12, minute=0).isoformat()},
        # INCLUDE: 23:59:59 (last valid second)
        {"id": "last_second", "commence_time": (end - timedelta(seconds=1)).isoformat()},
        # EXCLUDE: 00:00:00 next day (exclusive end)
        {"id": "at_end", "commence_time": end.isoformat()},
    ]

    kept, dropped_window, dropped_missing = filter_events_et(events, today)

    assert len(kept) == 4
    assert len(dropped_window) == 1

    kept_ids = [e["id"] for e in kept]
    assert "after_start" in kept_ids
    assert "at_start" in kept_ids
    assert "noon" in kept_ids
    assert "last_second" in kept_ids

    dropped_ids = [e["id"] for e in dropped_window]
    assert "at_end" in dropped_ids
