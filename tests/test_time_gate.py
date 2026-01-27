"""
Tests for ET day boundary filtering (v15.1).
"""
import pytest
from time_filters import et_day_bounds, is_in_et_day, filter_events_today_et


def test_et_day_bounds_specific_date():
    """Bounds for a specific date should span 00:00:00 to 23:59:59 ET."""
    start, end = et_day_bounds("2026-01-27")
    assert start.hour == 0 and start.minute == 0 and start.second == 0
    assert end.hour == 23 and end.minute == 59 and end.second == 59
    assert start.date().isoformat() == "2026-01-27"
    assert end.date().isoformat() == "2026-01-27"


def test_et_day_bounds_today():
    """Calling with no date_str should not raise."""
    start, end = et_day_bounds()
    assert start < end


def test_is_in_et_day_in_window():
    """11:59 PM ET on Jan 27 should be in-window for Jan 27."""
    assert is_in_et_day("2026-01-27T23:59:00-05:00", "2026-01-27") is True


def test_is_in_et_day_out_of_window():
    """12:01 AM ET on Jan 28 should be out-of-window for Jan 27."""
    assert is_in_et_day("2026-01-28T00:01:00-05:00", "2026-01-27") is False


def test_is_in_et_day_utc_conversion():
    """5:00 AM UTC on Jan 28 = 12:00 AM ET Jan 28 — out for Jan 27."""
    assert is_in_et_day("2026-01-28T05:00:00+00:00", "2026-01-27") is False


def test_is_in_et_day_early_utc_in_window():
    """4:59 AM UTC on Jan 28 = 11:59 PM ET Jan 27 — in for Jan 27."""
    assert is_in_et_day("2026-01-28T04:59:00+00:00", "2026-01-27") is True


def test_filter_events_today_et():
    """Filter should separate kept, dropped-window, and dropped-missing."""
    events = [
        {"commence_time": "2026-01-27T23:59:00-05:00", "home_team": "A", "away_team": "B"},
        {"commence_time": "2026-01-28T00:01:00-05:00", "home_team": "C", "away_team": "D"},
        {"commence_time": "2026-01-28T01:00:00-05:00", "home_team": "E", "away_team": "F"},
        {},  # Missing commence_time
    ]
    kept, dropped_w, dropped_m = filter_events_today_et(events, "2026-01-27")
    assert len(kept) == 1
    assert len(dropped_w) == 2
    assert len(dropped_m) == 1


def test_filter_events_empty_list():
    """Empty list should return three empty lists."""
    kept, dropped_w, dropped_m = filter_events_today_et([], "2026-01-27")
    assert kept == []
    assert dropped_w == []
    assert dropped_m == []


def test_is_in_et_day_empty_string():
    """Empty commence_time should return False."""
    assert is_in_et_day("", "2026-01-27") is False


def test_is_in_et_day_midnight_boundary():
    """Exactly midnight (00:00:00) ET should be in-window."""
    assert is_in_et_day("2026-01-27T00:00:00-05:00", "2026-01-27") is True
