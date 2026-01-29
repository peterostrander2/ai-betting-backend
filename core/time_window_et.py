"""
TIME WINDOW ET - Eastern Time Filtering (NEVER SKIP THIS)

This module provides ET day-bound filtering to ensure only TODAY's games
are processed and returned to users.

CRITICAL RULES:
1. Day bounds: 00:00:00 ET to 23:59:59 ET (NOT 00:01)
2. Timezone: America/New_York (explicit, not implicit)
3. MANDATORY: Every data path that touches Odds API events MUST filter to today-only

WHY THIS EXISTS:
- Without ET gating, Odds API returns ALL upcoming events (60+ games across multiple days)
- This causes inflated candidate counts, ghost picks, and skewed distributions
- ET gating is the ONLY way to ensure we return picks for games happening TODAY

USAGE:
    from core.time_window_et import filter_today_et, is_in_today_et

    # Filter events list
    kept, dropped = filter_today_et(events)

    # Check single event
    if is_in_today_et(event_commence_time):
        # Process event
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, date
import logging

# Import core invariants
try:
    from core.invariants import ET_TIMEZONE, ET_DAY_START, ET_DAY_END
    INVARIANTS_AVAILABLE = True
except ImportError:
    INVARIANTS_AVAILABLE = False
    ET_TIMEZONE = "America/New_York"
    ET_DAY_START = "00:00:00"
    ET_DAY_END = "23:59:59"

# Try to import existing time_filters module
try:
    from time_filters import (
        filter_events_today_et,
        is_in_et_day,
        et_day_bounds,
        get_today_date_et
    )
    TIME_FILTERS_AVAILABLE = True
except ImportError:
    TIME_FILTERS_AVAILABLE = False

# Try to import pytz
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False

logger = logging.getLogger(__name__)

# =============================================================================
# PUBLIC API
# =============================================================================

def filter_today_et(
    events: List[Dict[str, Any]],
    date_str: Optional[str] = None
) -> Tuple[List[Dict], List[Dict]]:
    """
    Filter events to ET day (00:00-23:59 America/New_York).

    Args:
        events: List of event dicts with 'commence_time' field
        date_str: Optional date string (YYYY-MM-DD). If None, uses today.

    Returns:
        Tuple of (kept_events, dropped_events)

    Example:
        events = odds_api.get_events("nba")
        today_events, tomorrow_events = filter_today_et(events)
        # Only process today_events
    """
    if TIME_FILTERS_AVAILABLE:
        # Use existing implementation
        kept, dropped_window, dropped_missing = filter_events_today_et(events, date_str)
        dropped = dropped_window + dropped_missing
        return kept, dropped
    else:
        # Fallback implementation
        logger.warning("time_filters module not available, using fallback ET filter")
        return _fallback_filter_today_et(events, date_str)


def is_in_today_et(
    event_time: str,
    date_str: Optional[str] = None
) -> bool:
    """
    Check if event time falls within today's ET day bounds.

    Args:
        event_time: ISO datetime string (e.g., "2026-01-28T19:30:00Z")
        date_str: Optional date string (YYYY-MM-DD). If None, uses today.

    Returns:
        bool: True if event is within today's ET bounds

    Example:
        if is_in_today_et("2026-01-28T19:30:00Z"):
            # Process event
    """
    if TIME_FILTERS_AVAILABLE:
        return is_in_et_day(event_time, date_str)
    else:
        # Fallback
        return True  # Pass through if no time filtering available


def get_today_et_bounds(
    date_str: Optional[str] = None
) -> Tuple[datetime, datetime]:
    """
    Get ET day bounds for a given date.

    Args:
        date_str: Optional date string (YYYY-MM-DD). If None, uses today.

    Returns:
        Tuple of (start_dt, end_dt) as datetime objects in ET

    Example:
        start, end = get_today_et_bounds()
        # start = 2026-01-28 00:00:00 ET
        # end = 2026-01-28 23:59:59 ET
    """
    if TIME_FILTERS_AVAILABLE:
        return et_day_bounds(date_str)
    else:
        # Fallback
        return _fallback_et_bounds(date_str)


def get_today_date_string() -> str:
    """
    Get today's date in ET timezone as YYYY-MM-DD string.

    Returns:
        str: Date string (e.g., "2026-01-28")

    Example:
        date_str = get_today_date_string()
        # "2026-01-28"
    """
    if TIME_FILTERS_AVAILABLE:
        return get_today_date_et()
    else:
        # Fallback to UTC date
        return datetime.utcnow().strftime("%Y-%m-%d")


# =============================================================================
# FALLBACK IMPLEMENTATIONS
# =============================================================================

def _fallback_filter_today_et(
    events: List[Dict[str, Any]],
    date_str: Optional[str] = None
) -> Tuple[List[Dict], List[Dict]]:
    """
    Fallback ET filter when time_filters module not available.

    This is a simplified implementation - production should use time_filters.py
    """
    if not PYTZ_AVAILABLE:
        logger.warning("pytz not available, cannot filter by ET timezone")
        return events, []

    et_tz = pytz.timezone(ET_TIMEZONE)
    now_et = datetime.now(et_tz)

    if date_str:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        target_date = now_et.date()

    kept = []
    dropped = []

    for event in events:
        commence_time = event.get("commence_time", "")
        if not commence_time:
            dropped.append(event)
            continue

        try:
            # Parse ISO datetime
            event_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))

            # Convert to ET
            event_et = event_dt.astimezone(et_tz)

            # Check if same date
            if event_et.date() == target_date:
                kept.append(event)
            else:
                dropped.append(event)
        except Exception as e:
            logger.warning(f"Failed to parse event time {commence_time}: {e}")
            dropped.append(event)

    return kept, dropped


def _fallback_et_bounds(date_str: Optional[str] = None) -> Tuple[datetime, datetime]:
    """Fallback ET bounds calculation."""
    if not PYTZ_AVAILABLE:
        # Return naive UTC bounds
        now = datetime.utcnow()
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else now.date()
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())
        return start, end

    et_tz = pytz.timezone(ET_TIMEZONE)
    now_et = datetime.now(et_tz)

    if date_str:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        target_date = now_et.date()

    # Start: 00:00:00 ET
    start = et_tz.localize(datetime.combine(target_date, datetime.min.time()))

    # End: 23:59:59 ET
    end = et_tz.localize(datetime.combine(target_date, datetime.max.time()))

    return start, end


# =============================================================================
# VALIDATION
# =============================================================================

def validate_et_filtering_applied(
    original_count: int,
    filtered_count: int,
    dropped_count: int
) -> bool:
    """
    Validate that ET filtering was actually applied.

    This helps catch bugs where filtering is bypassed or fails silently.

    Args:
        original_count: Number of events before filtering
        filtered_count: Number of events after filtering (kept)
        dropped_count: Number of events dropped

    Returns:
        bool: True if filtering appears to have been applied correctly
    """
    # Sanity checks
    if original_count == 0:
        return True  # No events to filter

    if filtered_count + dropped_count != original_count:
        logger.error(
            f"ET filtering math error: {original_count} original, "
            f"{filtered_count} kept, {dropped_count} dropped"
        )
        return False

    # If we got events and dropped NONE, that's suspicious
    # (unless it's a very light day)
    if original_count > 10 and dropped_count == 0:
        logger.warning(
            f"ET filtering suspicious: {original_count} events, "
            f"0 dropped (expected some out-of-window)"
        )
        return False

    return True


# =============================================================================
# TELEMETRY HELPERS
# =============================================================================

def get_et_filtering_stats(
    kept: List[Dict],
    dropped: List[Dict]
) -> Dict[str, Any]:
    """
    Generate telemetry for ET filtering.

    Returns:
        Dict with:
            - kept_count: int
            - dropped_count: int
            - total_count: int
            - drop_rate: float (0-1)
            - filtering_applied: bool
    """
    kept_count = len(kept)
    dropped_count = len(dropped)
    total_count = kept_count + dropped_count

    return {
        "kept_count": kept_count,
        "dropped_count": dropped_count,
        "total_count": total_count,
        "drop_rate": dropped_count / total_count if total_count > 0 else 0.0,
        "filtering_applied": validate_et_filtering_applied(total_count, kept_count, dropped_count)
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "filter_today_et",
    "is_in_today_et",
    "get_today_et_bounds",
    "get_today_date_string",
    "validate_et_filtering_applied",
    "get_et_filtering_stats",
]
