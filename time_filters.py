"""
TIME_FILTERS.PY - TODAY-ONLY SLATE GATING
==========================================
v15.4 - Production time filtering for America/New_York timezone

CANONICAL ET SLATE WINDOW (HARD RULE):
    Start: 00:00:00 America/New_York (midnight ET) - inclusive
    End:   00:00:00 America/New_York next day (midnight) - exclusive
    Interval: [start, end)

This module enforces TODAY-only slate gating:
- Only games between 00:00:00 ET and 00:00:00 ET next day are valid
- Ghost games (teams not playing today) are blocked
- Tomorrow games from APIs are excluded
- Events at exactly 00:00:00 (midnight) belong to PREVIOUS day

Usage:
    from time_filters import (
        is_game_today,
        is_team_in_slate,
        validate_today_slate,
        get_today_range_et,
        filter_today_games
    )
"""

from datetime import datetime, timedelta, time as dt_time, timezone
from typing import Dict, List, Any, Optional, Tuple, Set
import logging

# Use zoneinfo (Python 3.9+) - modern timezone handling
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    ZONEINFO_AVAILABLE = True
except ImportError:
    # Fallback to pytz for older Python versions
    try:
        import pytz
        ET = pytz.timezone("America/New_York")
        ZONEINFO_AVAILABLE = False
    except ImportError:
        ET = None
        ZONEINFO_AVAILABLE = False

logger = logging.getLogger("time_filters")


# =============================================================================
# TIMEZONE HELPERS
# =============================================================================

def get_now_et() -> datetime:
    """
    Get current datetime in America/New_York timezone.

    Always starts from UTC then converts -> avoids host-local ambiguity.

    Returns:
        datetime in ET timezone (or naive datetime if neither library available)
    """
    if ET:
        # Modern approach: UTC first, then convert
        return datetime.now(timezone.utc).astimezone(ET)
    else:
        # Fallback: naive datetime
        return datetime.now()


def get_today_range_et(date_str: Optional[str] = None) -> Tuple[datetime, datetime]:
    """
    Get today's valid time range in ET.

    CANONICAL ET SLATE WINDOW:
        Start: 00:00:00 ET (midnight) - inclusive
        End:   00:00:00 ET next day (midnight) - exclusive

    Args:
        date_str: Optional date string (YYYY-MM-DD). If None, uses today.

    Returns:
        Tuple of (start_of_day, end_of_day) in ET
        Start: 00:00:00 ET
        End: 00:00:00 ET next day (exclusive upper bound)
    """
    if date_str:
        today = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        now_et = get_now_et()
        today = now_et.date()

    if ET:
        # CANONICAL: midnight start, midnight next day end (exclusive)
        start = datetime.combine(today, dt_time(0, 0, 0), tzinfo=ET)
        end = datetime.combine(today + timedelta(days=1), dt_time(0, 0, 0), tzinfo=ET)
    else:
        # Fallback: naive datetimes
        start = datetime.combine(today, dt_time(0, 0, 0))
        end = datetime.combine(today + timedelta(days=1), dt_time(0, 0, 0))

    return start, end


def parse_game_time(time_str: str) -> Optional[datetime]:
    """
    Parse game time string to datetime.

    Handles ISO format, with or without timezone.

    Args:
        time_str: ISO format datetime string

    Returns:
        datetime object or None if parsing fails
    """
    if not time_str:
        return None

    try:
        # Try ISO format with timezone
        if "Z" in time_str:
            time_str = time_str.replace("Z", "+00:00")

        # Parse the datetime string
        dt = datetime.fromisoformat(time_str)

        # If naive datetime, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # Convert to ET if timezone support available
        if ET:
            dt = dt.astimezone(ET)

        return dt
    except (ValueError, AttributeError) as e:
        logger.warning("Failed to parse game time '%s': %s", time_str, e)
        return None


# =============================================================================
# GAME TIME VALIDATION
# =============================================================================

def is_game_today(commence_time: str) -> bool:
    """
    Check if a game is scheduled for today (ET timezone).

    Uses canonical ET slate window: [00:00:00 ET, 00:00:00 next day ET)

    Args:
        commence_time: ISO format datetime string

    Returns:
        True if game is today in ET, False otherwise
    """
    game_dt = parse_game_time(commence_time)
    if not game_dt:
        logger.warning("Could not parse commence_time: %s - excluding game", commence_time)
        return False

    start_et, end_et = get_today_range_et()

    # Make comparison timezone-aware if needed
    if ET:
        if game_dt.tzinfo is None:
            game_dt = game_dt.replace(tzinfo=ET)
        game_dt = game_dt.astimezone(ET)

    # CANONICAL: [start, end) - start inclusive, end exclusive
    is_today = start_et <= game_dt < end_et

    if not is_today:
        logger.debug("Game at %s is not today (ET range: [%s, %s))",
                    game_dt.isoformat(), start_et.isoformat(), end_et.isoformat())

    return is_today


def is_game_started(commence_time: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a game has already started.

    Args:
        commence_time: ISO format datetime string

    Returns:
        Tuple of (is_started: bool, started_at: str or None)
    """
    game_dt = parse_game_time(commence_time)
    if not game_dt:
        return False, None

    now_et = get_now_et()

    # Make comparison timezone-aware if needed
    if ET:
        if game_dt.tzinfo is None:
            game_dt = game_dt.replace(tzinfo=ET)
        game_dt = game_dt.astimezone(ET)

    is_started = now_et >= game_dt

    return is_started, game_dt.isoformat() if is_started else None


def is_game_tomorrow(commence_time: str) -> bool:
    """
    Check if a game is scheduled for tomorrow (should be excluded).

    Args:
        commence_time: ISO format datetime string

    Returns:
        True if game is tomorrow, False otherwise
    """
    game_dt = parse_game_time(commence_time)
    if not game_dt:
        return False

    now_et = get_now_et()
    tomorrow = now_et.date() + timedelta(days=1)

    # Get game date in ET
    if ET:
        if game_dt.tzinfo is None:
            game_dt = game_dt.replace(tzinfo=ET)
        game_dt = game_dt.astimezone(ET)

    return game_dt.date() == tomorrow


# =============================================================================
# SLATE VALIDATION
# =============================================================================

def build_today_slate(games: List[Dict]) -> Set[str]:
    """
    Build set of teams playing today from games list.

    Args:
        games: List of game dicts with home_team, away_team, commence_time

    Returns:
        Set of team names playing today
    """
    teams = set()

    for game in games:
        commence_time = game.get("commence_time", "")
        if is_game_today(commence_time):
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            if home:
                teams.add(home)
            if away:
                teams.add(away)

    return teams


def is_team_in_slate(team_name: str, slate: Set[str]) -> bool:
    """
    Check if a team is in today's slate.

    Args:
        team_name: Team name to check
        slate: Set of teams playing today

    Returns:
        True if team is in slate
    """
    if not team_name:
        return False

    # Direct match
    if team_name in slate:
        return True

    # Case-insensitive match
    team_lower = team_name.lower()
    for slate_team in slate:
        if slate_team.lower() == team_lower:
            return True

    # Partial match (e.g., "Lakers" matches "Los Angeles Lakers")
    for slate_team in slate:
        if team_lower in slate_team.lower() or slate_team.lower() in team_lower:
            return True

    return False


def validate_today_slate(
    games: List[Dict],
    log_excluded: bool = True
) -> Tuple[List[Dict], List[Dict]]:
    """
    Filter games to only include today's games.

    Args:
        games: List of game dicts
        log_excluded: Whether to log excluded games

    Returns:
        Tuple of (today_games, excluded_games)
    """
    today_games = []
    excluded_games = []

    for game in games:
        commence_time = game.get("commence_time", "")

        if is_game_today(commence_time):
            today_games.append(game)
        else:
            excluded_games.append(game)
            if log_excluded:
                home = game.get("home_team", "")
                away = game.get("away_team", "")
                reason = "tomorrow" if is_game_tomorrow(commence_time) else "not today"
                logger.info("GHOST PREVENTION: Excluding %s @ %s (%s, commence_time=%s)",
                          away, home, reason, commence_time)

    return today_games, excluded_games


def filter_today_games(games: List[Dict]) -> List[Dict]:
    """
    Convenience function to filter to today's games only.

    Args:
        games: List of game dicts

    Returns:
        List of games scheduled for today only
    """
    today_games, _ = validate_today_slate(games)
    return today_games


# =============================================================================
# PROP VALIDATION
# =============================================================================

def is_player_in_today_slate(
    player_name: str,
    team_name: str,
    slate: Set[str]
) -> bool:
    """
    Check if a player's team is in today's slate.

    Args:
        player_name: Player name (for logging)
        team_name: Player's team
        slate: Set of teams playing today

    Returns:
        True if player's team is in today's slate
    """
    if not team_name:
        logger.warning("GHOST PREVENTION: Player %s has no team - cannot validate", player_name)
        return False

    in_slate = is_team_in_slate(team_name, slate)

    if not in_slate:
        logger.info("GHOST PREVENTION: Excluding prop for %s (%s not in today's slate)",
                   player_name, team_name)

    return in_slate


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_game_start_time_et(commence_time: str) -> str:
    """
    Format game start time in ET for display.

    Args:
        commence_time: ISO format datetime string

    Returns:
        Formatted time string like "7:30 PM ET"
    """
    game_dt = parse_game_time(commence_time)
    if not game_dt:
        return "TBD"

    if ET:
        if game_dt.tzinfo is None:
            game_dt = game_dt.replace(tzinfo=ET)
        game_dt = game_dt.astimezone(ET)

    return game_dt.strftime("%-I:%M %p ET")


def get_today_date_str() -> str:
    """
    Get today's date formatted for display.

    Returns:
        Date string like "January 25, 2026"
    """
    now_et = get_now_et()
    return now_et.strftime("%B %d, %Y")


# =============================================================================
# GHOST DATA DETECTION
# =============================================================================

def detect_ghost_teams(
    requested_teams: List[str],
    slate: Set[str]
) -> List[str]:
    """
    Detect teams that are not in today's slate (ghost teams).

    Args:
        requested_teams: List of team names from API/request
        slate: Set of teams actually playing today

    Returns:
        List of ghost team names
    """
    ghost_teams = []

    for team in requested_teams:
        if not is_team_in_slate(team, slate):
            ghost_teams.append(team)
            logger.warning("GHOST DETECTED: %s is not in today's slate", team)

    return ghost_teams


def log_slate_summary(slate: Set[str], sport: str) -> None:
    """
    Log a summary of today's slate for debugging.

    Args:
        slate: Set of teams playing today
        sport: Sport name
    """
    logger.info("TODAY'S %s SLATE (%s): %d teams - %s",
               sport.upper(),
               get_today_date_str(),
               len(slate),
               ", ".join(sorted(slate)) if slate else "NO GAMES")


# =============================================================================
# v11.15: GAME START STATUS
# =============================================================================

def is_game_started(commence_time: str) -> bool:
    """
    Check if a game has already started.

    Args:
        commence_time: ISO format datetime string

    Returns:
        True if game has started (commence_time is in the past)
    """
    game_dt = parse_game_time(commence_time)
    if not game_dt:
        return False

    now_et = get_now_et()

    # Make comparison timezone-aware if needed
    if ET:
        if game_dt.tzinfo is None:
            game_dt = game_dt.replace(tzinfo=ET)
        game_dt = game_dt.astimezone(ET)

    return now_et > game_dt


def get_game_status(commence_time: str) -> str:
    """
    Get game status based on start time.

    Args:
        commence_time: ISO format datetime string

    Returns:
        "UPCOMING" | "MISSED_START" | "NOT_TODAY"
    """
    if not is_game_today(commence_time):
        return "NOT_TODAY"

    if is_game_started(commence_time):
        return "MISSED_START"

    return "UPCOMING"


# =============================================================================
# ET DAY BOUNDS — date_str-aware filtering (v15.1)
# =============================================================================

def et_day_bounds(date_str: Optional[str] = None) -> Tuple[datetime, datetime, datetime, datetime]:
    """
    Get ET day bounds. If date_str None, use today.

    CANONICAL ET SLATE WINDOW:
        Start: 00:00:00 ET (midnight) - inclusive
        End:   00:00:00 ET next day (midnight) - exclusive
        Interval: [start, end)

    Args:
        date_str: Optional date string (YYYY-MM-DD)

    Returns:
        Tuple of (start_et, end_et, start_utc, end_utc)
        - start_et: datetime at 00:00:00 ET
        - end_et: datetime at 00:00:00 ET next day (exclusive upper bound)
        - start_utc: UTC-converted start_et (for DB filtering)
        - end_utc: UTC-converted end_et (for DB filtering)
    """
    # Delegate to core.time_et (single source of truth)
    try:
        from core.time_et import et_day_bounds as core_et_day_bounds
        start_et, end_et, start_utc, end_utc = core_et_day_bounds(date_str=date_str)
        return start_et, end_et, start_utc, end_utc
    except Exception:
        # Fallback to local implementation if core not available
        if date_str:
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            day = get_now_et().date()

        if ET:
            start = datetime.combine(day, dt_time(0, 0, 0), tzinfo=ET)
            end = datetime.combine(day + timedelta(days=1), dt_time(0, 0, 0), tzinfo=ET)
        else:
            start = datetime.combine(day, dt_time(0, 0, 0))
            end = datetime.combine(day + timedelta(days=1), dt_time(0, 0, 0))

        start_utc = start.astimezone(timezone.utc) if start.tzinfo else start.replace(tzinfo=timezone.utc)
        end_utc = end.astimezone(timezone.utc) if end.tzinfo else end.replace(tzinfo=timezone.utc)
        return start, end, start_utc, end_utc


def is_in_et_day(commence_time: str, date_str: Optional[str] = None) -> bool:
    """
    Check if event is within ET day bounds.

    Args:
        commence_time: ISO format datetime string
        date_str: Optional date string (YYYY-MM-DD). If None, uses today.

    Returns:
        True if event falls within the ET day
    """
    game_dt = parse_game_time(commence_time)
    if not game_dt:
        return False
    start, end, _, _ = et_day_bounds(date_str)  # Ignore UTC bounds for filtering

    if ET:
        # Ensure game_dt is timezone-aware and in ET
        if game_dt.tzinfo is None:
            # Naive datetime - assume UTC
            game_dt = game_dt.replace(tzinfo=timezone.utc)
        game_dt = game_dt.astimezone(ET)
    else:
        # Fallback: strip timezone for naive comparison
        if game_dt.tzinfo is not None:
            game_dt = game_dt.replace(tzinfo=None)

    return start <= game_dt < end  # Use < end (exclusive upper bound)


def filter_events_today_et(
    events: List[Dict],
    date_str: Optional[str] = None
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Filter events to ET day.

    Args:
        events: List of event dicts with commence_time
        date_str: Optional date string (YYYY-MM-DD). If None, uses today.

    Returns:
        Tuple of (kept, dropped_out_of_window, dropped_missing_time)
    """
    kept, dropped_window, dropped_missing = [], [], []
    for e in events:
        ct = e.get("commence_time", "")
        if not ct:
            dropped_missing.append(e)
        elif is_in_et_day(ct, date_str):
            kept.append(e)
        else:
            dropped_window.append(e)
    return kept, dropped_window, dropped_missing
