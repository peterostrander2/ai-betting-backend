"""
Time Filters Module v11.00
==========================
Single source of truth for TODAY-ONLY ET filtering across all endpoints.

All daily slate pulling, grading, and pick generation MUST use these functions
to ensure consistent America/New_York timezone handling.

Daily window: 12:01 AM ET → 11:59 PM ET
"""

from datetime import datetime, date, time, timedelta
from typing import Tuple, Optional, Dict, Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def get_now_et() -> datetime:
    """Get current datetime in America/New_York timezone."""
    return datetime.now(ET)


def get_today_et() -> date:
    """Get today's date in America/New_York timezone."""
    return get_now_et().date()


def get_today_et_window() -> Tuple[datetime, datetime]:
    """
    Get the start and end datetimes for today in America/New_York.

    Returns:
        Tuple of (start, end) where:
        - start = 12:01 AM ET today
        - end = 11:59 PM ET today
    """
    today = get_today_et()
    start = datetime.combine(today, time(0, 1), tzinfo=ET)  # 12:01 AM
    end = datetime.combine(today, time(23, 59, 59), tzinfo=ET)  # 11:59 PM
    return start, end


def is_today_et(dt: Any) -> bool:
    """
    Check if a datetime/date is today in ET timezone.

    Args:
        dt: datetime, date, or ISO string

    Returns:
        True if the date is today ET
    """
    if dt is None:
        return False

    try:
        # Handle string input
        if isinstance(dt, str):
            dt = parse_to_et(dt)
            if dt is None:
                return False

        # Handle date input
        if isinstance(dt, date) and not isinstance(dt, datetime):
            return dt == get_today_et()

        # Handle datetime input
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                # Assume UTC if no timezone
                dt = dt.replace(tzinfo=UTC)
            dt_et = dt.astimezone(ET)
            return dt_et.date() == get_today_et()

        return False
    except Exception:
        return False


def within_today_window(dt: Any, grace_minutes: int = 0) -> bool:
    """
    Check if a datetime falls within today's ET window.

    Args:
        dt: datetime, date, or ISO string
        grace_minutes: Minutes of grace period before start of day

    Returns:
        True if within today's window
    """
    if dt is None:
        return False

    try:
        # Parse to ET datetime
        if isinstance(dt, str):
            dt = parse_to_et(dt)
            if dt is None:
                return False
        elif isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime.combine(dt, time(12, 0), tzinfo=ET)
        elif isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            dt = dt.astimezone(ET)
        else:
            return False

        start, end = get_today_et_window()

        # Apply grace period
        if grace_minutes > 0:
            start = start - timedelta(minutes=grace_minutes)

        return start <= dt <= end
    except Exception:
        return False


def parse_to_et(time_str: Optional[str]) -> Optional[datetime]:
    """
    Parse an ISO time string to ET datetime.

    Args:
        time_str: ISO format datetime string

    Returns:
        datetime in ET timezone, or None if parsing fails
    """
    if not time_str:
        return None

    try:
        # Handle various formats
        if isinstance(time_str, datetime):
            dt = time_str
        elif "Z" in time_str:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        elif "+" in time_str or time_str.endswith("-00:00"):
            dt = datetime.fromisoformat(time_str)
        else:
            # Assume UTC if no timezone
            dt = datetime.fromisoformat(time_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)

        return dt.astimezone(ET)
    except Exception:
        return None


def normalize_start_time(game: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a game dict to include ET-aware start time fields.

    Adds/updates:
        - start_time_et: ISO string in ET
        - is_today_et: bool
        - is_started: bool
        - game_status: "scheduled" | "live" | "final"

    Args:
        game: Game dictionary with start_time or commence_time

    Returns:
        Game dict with normalized time fields
    """
    # Get start time from various possible fields
    start_time_raw = (
        game.get("start_time") or
        game.get("commence_time") or
        game.get("game_time") or
        ""
    )

    dt_et = parse_to_et(start_time_raw)
    now_et = get_now_et()

    if dt_et:
        game["start_time_et"] = dt_et.isoformat()
        game["is_today_et"] = is_today_et(dt_et)

        # Determine if started (with 5 min grace)
        minutes_since_start = (now_et - dt_et).total_seconds() / 60
        game["is_started"] = minutes_since_start > 5

        # Determine game status
        existing_status = game.get("status", "").lower()
        if existing_status in ("final", "finished", "completed", "post"):
            game["game_status"] = "final"
        elif game["is_started"] or existing_status in ("live", "in_progress", "in progress"):
            game["game_status"] = "live"
        else:
            game["game_status"] = "scheduled"
    else:
        # Can't determine - use safe defaults
        game["start_time_et"] = None
        game["is_today_et"] = False
        game["is_started"] = False
        game["game_status"] = "unknown"

    return game


def filter_today_only(games: list, key: str = None) -> list:
    """
    Filter a list of games/picks to today ET only.

    Args:
        games: List of game/pick dicts
        key: Optional key name for the start time field

    Returns:
        Filtered list containing only today's games
    """
    result = []
    for game in games:
        # Normalize first
        normalized = normalize_start_time(game)
        if normalized.get("is_today_et", False):
            result.append(normalized)
    return result


def get_grading_window(target_date: Optional[date] = None) -> Tuple[datetime, datetime]:
    """
    Get the grading window for a specific date.

    If no date provided, defaults to today ET.

    Args:
        target_date: Specific date to grade, or None for today

    Returns:
        Tuple of (start, end) datetimes for the grading window
    """
    if target_date is None:
        target_date = get_today_et()

    start = datetime.combine(target_date, time(0, 1), tzinfo=ET)
    end = datetime.combine(target_date, time(23, 59, 59), tzinfo=ET)
    return start, end


def format_et_display(dt: Any) -> str:
    """
    Format a datetime for display in ET.

    Args:
        dt: datetime, date, or ISO string

    Returns:
        Formatted string like "7:30 PM ET" or "Jan 25, 7:30 PM ET"
    """
    if dt is None:
        return "TBD"

    try:
        if isinstance(dt, str):
            dt = parse_to_et(dt)
        elif isinstance(dt, date) and not isinstance(dt, datetime):
            return dt.strftime("%b %d")
        elif isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            dt = dt.astimezone(ET)

        if dt is None:
            return "TBD"

        # Check if today
        if dt.date() == get_today_et():
            return dt.strftime("%-I:%M %p ET")
        else:
            return dt.strftime("%b %d, %-I:%M %p ET")
    except Exception:
        return "TBD"
