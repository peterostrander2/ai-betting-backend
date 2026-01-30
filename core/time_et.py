"""
TIME_ET.PY - Single Source of Truth for ET Timezone Handling

RULES:
1. Server clock is UTC
2. All app logic enforces ET (America/New_York)
3. Core functions:
   - now_et(): UTC -> ET conversion
   - et_day_bounds(): Returns [start_et, end_et) and et_date
   - within_et_bounds(): Check if event falls within bounds
   - assert_et_bounds(): Validate bounds invariants
4. NO other date helpers allowed
5. Uses zoneinfo (Python 3.9+) ONLY - no pytz

CANONICAL ET SLATE WINDOW (HARD RULE):
    Start: 00:01:00 America/New_York (12:01 AM ET)
    End:   00:00:00 America/New_York next day (midnight, exclusive)
    Interval: [start_et, end_et)

    Why 00:01:00? Avoids ambiguity at midnight boundary and ensures
    games at exactly 00:00:00 are NOT double-counted across days.

Usage:
    from core.time_et import now_et, et_day_bounds, within_et_bounds

    # Get current ET time
    current = now_et()

    # Get ET day bounds
    start, end, et_date = et_day_bounds()
    # start = 2026-01-28 00:01:00 ET
    # end = 2026-01-29 00:00:00 ET (exclusive)
    # et_date = "2026-01-28"

    # Check if event is in bounds
    if within_et_bounds(event_time, start, end):
        # Process event
"""

from datetime import datetime, time, timedelta, timezone
from typing import Tuple, Optional, Dict, Any, Union
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

# America/New_York timezone
ET = ZoneInfo("America/New_York")

# Canonical slate window start time: 00:01:00 ET (NOT midnight)
ET_SLATE_START_TIME = time(0, 1, 0)  # 12:01 AM ET


def now_et() -> datetime:
    """
    Get current datetime in ET timezone.

    Server clock is UTC, we convert to ET.

    Returns:
        datetime in America/New_York timezone

    Example:
        >>> now = now_et()
        >>> now.tzinfo
        ZoneInfo(key='America/New_York')
    """
    return datetime.now(timezone.utc).astimezone(ET)


def et_day_bounds(date_str: str = None) -> Tuple[datetime, datetime, str]:
    """
    Get ET day bounds [start, end) and date string.

    CANONICAL ET SLATE WINDOW:
        Start: 00:01:00 ET (12:01 AM) - inclusive
        End:   00:00:00 ET next day (midnight) - exclusive
        Interval: [start, end)

    Why 00:01:00? Events exactly at midnight (00:00:00) belong to the
    PREVIOUS day, avoiding double-counting across day boundaries.

    Args:
        date_str: Optional date "YYYY-MM-DD". If None, uses today in ET.

    Returns:
        Tuple of (start_et, end_et, et_date)
        - start_et: datetime at 00:01:00 ET (12:01 AM)
        - end_et: datetime at 00:00:00 ET next day (exclusive upper bound)
        - et_date: "YYYY-MM-DD" format

    Example:
        >>> start, end, et_date = et_day_bounds("2026-01-28")
        >>> et_date
        "2026-01-28"
        >>> start
        datetime(2026, 1, 28, 0, 1, 0, tzinfo=ZoneInfo('America/New_York'))
        >>> end
        datetime(2026, 1, 29, 0, 0, 0, tzinfo=ZoneInfo('America/New_York'))
        >>> start <= some_event < end  # start inclusive, end exclusive
    """
    # Get target date
    if date_str:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        day = now_et().date()

    # CANONICAL: 00:01:00 to next day 00:00:00 (start at 12:01 AM, end exclusive at midnight)
    start = datetime.combine(day, ET_SLATE_START_TIME, tzinfo=ET)  # 00:01:00 ET
    end = datetime.combine(day + timedelta(days=1), time(0, 0, 0), tzinfo=ET)  # Next day midnight

    # ISO date string
    et_date = day.isoformat()

    return start, end, et_date


def parse_event_time(event_time: Union[str, datetime]) -> Optional[datetime]:
    """
    Parse event time to timezone-aware datetime in ET.

    Args:
        event_time: ISO datetime string or datetime object

    Returns:
        datetime in ET timezone, or None if parsing fails

    Example:
        >>> parse_event_time("2026-01-28T19:30:00Z")
        datetime(2026, 1, 28, 14, 30, 0, tzinfo=ZoneInfo('America/New_York'))
    """
    if not event_time:
        return None

    try:
        if isinstance(event_time, datetime):
            event_dt = event_time
        else:
            # Handle 'Z' suffix
            if event_time.endswith('Z'):
                event_time = event_time[:-1] + '+00:00'

            # Parse ISO format
            event_dt = datetime.fromisoformat(event_time)

        # If naive, assume UTC
        if event_dt.tzinfo is None:
            event_dt = event_dt.replace(tzinfo=timezone.utc)

        # Convert to ET
        return event_dt.astimezone(ET)

    except (ValueError, AttributeError, TypeError) as e:
        logger.warning(f"Failed to parse event time '{event_time}': {e}")
        return None


def within_et_bounds(
    event_time: Union[str, datetime],
    start_et: datetime,
    end_et: datetime
) -> bool:
    """
    Check if event time falls within ET bounds [start, end).

    This is the canonical function for checking if an event is within
    the ET slate window. Use this instead of manual comparisons.

    Args:
        event_time: ISO datetime string or datetime object (any timezone)
        start_et: Start of window (inclusive), must be ET-aware
        end_et: End of window (exclusive), must be ET-aware

    Returns:
        bool: True if start_et <= event_time_et < end_et

    Example:
        >>> start, end, _ = et_day_bounds("2026-01-28")
        >>> within_et_bounds("2026-01-28T19:30:00Z", start, end)
        True
        >>> within_et_bounds("2026-01-28T00:00:30Z", start, end)
        False  # 00:00:30 ET is before 00:01:00 ET start
    """
    event_et = parse_event_time(event_time)
    if event_et is None:
        return False

    return start_et <= event_et < end_et


def is_in_et_day(event_time: str, date_str: str = None) -> bool:
    """
    Check if event time falls within ET day bounds.

    Uses the canonical slate window: [00:01:00 ET, 00:00:00 next day ET)

    Args:
        event_time: ISO datetime string (e.g., "2026-01-28T19:30:00Z")
        date_str: Optional date "YYYY-MM-DD". If None, uses today.

    Returns:
        bool: True if event is within [start, end) bounds

    Example:
        >>> is_in_et_day("2026-01-28T19:30:00Z", "2026-01-28")
        True
        >>> is_in_et_day("2026-01-29T05:00:00Z", "2026-01-28")
        False
        >>> is_in_et_day("2026-01-28T00:00:30-05:00", "2026-01-28")
        False  # 00:00:30 ET is before 00:01:00 ET start
    """
    if not event_time:
        return False

    # Get day bounds
    start, end, _ = et_day_bounds(date_str)

    # Use canonical within_et_bounds check
    return within_et_bounds(event_time, start, end)


def filter_events_et(events: list, date_str: str = None) -> Tuple[list, list, list]:
    """
    Filter events to ET day bounds.

    Args:
        events: List of event dicts with 'commence_time' field
        date_str: Optional date "YYYY-MM-DD". If None, uses today.

    Returns:
        Tuple of (kept, dropped_out_of_window, dropped_missing_time)

    Example:
        >>> kept, dropped, missing = filter_events_et(events, "2026-01-28")
        >>> len(kept)  # Events happening on 2026-01-28 in ET
    """
    kept = []
    dropped_window = []
    dropped_missing = []

    for event in events:
        commence_time = event.get('commence_time', '')

        if not commence_time:
            dropped_missing.append(event)
        elif is_in_et_day(commence_time, date_str):
            kept.append(event)
        else:
            dropped_window.append(event)

    return kept, dropped_window, dropped_missing


def assert_et_bounds(start: datetime, end: datetime) -> Dict[str, Any]:
    """
    Validate ET bounds invariants. Returns validation result.

    Invariants checked:
    1. end > start (positive duration)
    2. end.date() == start.date() + 1 day (spans exactly to next day)
    3. start.time() == 00:01:00 (canonical start time)
    4. end.time() == 00:00:00 (midnight end)
    5. Both have America/New_York timezone

    Args:
        start: Start datetime
        end: End datetime

    Returns:
        Dict with:
            - valid: bool - True if all invariants pass
            - checks: Dict[str, bool] - Individual check results
            - errors: List[str] - Error messages for failed checks

    Example:
        >>> start, end, _ = et_day_bounds()
        >>> result = assert_et_bounds(start, end)
        >>> result["valid"]
        True
    """
    checks = {}
    errors = []

    # Check 1: end > start
    checks["end_after_start"] = end > start
    if not checks["end_after_start"]:
        errors.append(f"end ({end}) must be after start ({start})")

    # Check 2: end.date() == start.date() + 1 day
    expected_end_date = start.date() + timedelta(days=1)
    checks["spans_to_next_day"] = end.date() == expected_end_date
    if not checks["spans_to_next_day"]:
        errors.append(f"end.date() ({end.date()}) must be start.date() + 1 ({expected_end_date})")

    # Check 3: start.time() == 00:01:00
    checks["start_is_0001"] = start.time() == ET_SLATE_START_TIME
    if not checks["start_is_0001"]:
        errors.append(f"start.time() ({start.time()}) must be 00:01:00")

    # Check 4: end.time() == 00:00:00
    checks["end_is_midnight"] = end.time() == time(0, 0, 0)
    if not checks["end_is_midnight"]:
        errors.append(f"end.time() ({end.time()}) must be 00:00:00")

    # Check 5: Both have ET timezone
    checks["start_has_et_tz"] = start.tzinfo is not None and str(start.tzinfo) == "America/New_York"
    checks["end_has_et_tz"] = end.tzinfo is not None and str(end.tzinfo) == "America/New_York"
    if not checks["start_has_et_tz"]:
        errors.append(f"start.tzinfo ({start.tzinfo}) must be America/New_York")
    if not checks["end_has_et_tz"]:
        errors.append(f"end.tzinfo ({end.tzinfo}) must be America/New_York")

    return {
        "valid": all(checks.values()),
        "checks": checks,
        "errors": errors,
        "start_iso": start.isoformat(),
        "end_iso": end.isoformat(),
    }


def get_et_debug_info() -> Dict[str, Any]:
    """
    Get debug information about current ET state.

    Returns comprehensive debug info including current time,
    bounds, and invariant validation.

    Returns:
        Dict with debug information for /debug/time endpoint

    Example:
        >>> info = get_et_debug_info()
        >>> info["et_date"]
        "2026-01-29"
    """
    now = now_et()
    start, end, et_date = et_day_bounds()
    validation = assert_et_bounds(start, end)

    return {
        "now_utc_iso": datetime.now(timezone.utc).isoformat(),
        "now_et_iso": now.isoformat(),
        "et_date": et_date,
        "et_day_start_iso": start.isoformat(),
        "et_day_end_iso": end.isoformat(),
        "window_display": f"{et_date} 00:01:00 to 23:59:59 ET",
        "canonical_window": {
            "start_time": "00:01:00",
            "end_time": "00:00:00 (next day, exclusive)",
            "interval_notation": "[start, end)",
        },
        "bounds_validation": validation,
        "timezone": "America/New_York",
    }


# Export only these functions - no other date helpers allowed
__all__ = [
    'ET',
    'ET_SLATE_START_TIME',
    'now_et',
    'et_day_bounds',
    'parse_event_time',
    'within_et_bounds',
    'is_in_et_day',
    'filter_events_et',
    'assert_et_bounds',
    'get_et_debug_info',
]
