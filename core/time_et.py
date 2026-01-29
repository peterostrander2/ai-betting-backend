"""
TIME_ET.PY - Single Source of Truth for ET Timezone Handling

RULES:
1. Server clock is UTC
2. All app logic enforces ET (America/New_York)
3. Only two functions exist:
   - now_et(): UTC -> ET conversion
   - et_day_bounds(): Returns [start_et, end_et) and et_date
4. NO other date helpers allowed
5. Uses zoneinfo (Python 3.9+) ONLY - no pytz

Usage:
    from core.time_et import now_et, et_day_bounds

    # Get current ET time
    current = now_et()

    # Get ET day bounds
    start, end, et_date = et_day_bounds()
    # start = 2026-01-28 00:00:00 ET
    # end = 2026-01-29 00:00:00 ET (exclusive)
    # et_date = "2026-01-28"
"""

from datetime import datetime, time, timedelta, timezone
from typing import Tuple
from zoneinfo import ZoneInfo

# America/New_York timezone
ET = ZoneInfo("America/New_York")


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

    Args:
        date_str: Optional date "YYYY-MM-DD". If None, uses today in ET.

    Returns:
        Tuple of (start_et, end_et, et_date)
        - start_et: datetime at 00:00:00 ET
        - end_et: datetime at 00:00:00 ET next day (EXCLUSIVE upper bound)
        - et_date: "YYYY-MM-DD" format

    Example:
        >>> start, end, et_date = et_day_bounds("2026-01-28")
        >>> et_date
        "2026-01-28"
        >>> start
        datetime(2026, 1, 28, 0, 0, 0, tzinfo=ZoneInfo('America/New_York'))
        >>> end
        datetime(2026, 1, 29, 0, 0, 0, tzinfo=ZoneInfo('America/New_York'))
        >>> start <= some_event < end  # Exclusive upper bound
    """
    # Get target date
    if date_str:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        day = now_et().date()

    # Start of day in ET
    start = datetime.combine(day, time(0, 0, 0), tzinfo=ET)

    # End is start of NEXT day (exclusive upper bound)
    end = start + timedelta(days=1)

    # ISO date string
    et_date = day.isoformat()

    return start, end, et_date


def is_in_et_day(event_time: str, date_str: str = None) -> bool:
    """
    Check if event time falls within ET day bounds.

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
    """
    # Parse event time
    if not event_time:
        return False

    try:
        # Handle 'Z' suffix
        if event_time.endswith('Z'):
            event_time = event_time[:-1] + '+00:00'

        # Parse ISO format
        event_dt = datetime.fromisoformat(event_time)

        # If naive, assume UTC
        if event_dt.tzinfo is None:
            event_dt = event_dt.replace(tzinfo=timezone.utc)

        # Convert to ET
        event_et = event_dt.astimezone(ET)

        # Get day bounds
        start, end, _ = et_day_bounds(date_str)

        # Check if in bounds [start, end)
        return start <= event_et < end

    except (ValueError, AttributeError):
        return False


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


# Export only these functions - no other date helpers allowed
__all__ = [
    'now_et',
    'et_day_bounds',
    'is_in_et_day',
    'filter_events_et',
]
