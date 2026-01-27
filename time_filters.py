"""
TIME_FILTERS.PY - TODAY-ONLY SLATE GATING
==========================================
v11.08 - Production time filtering for America/New_York timezone

This module enforces TODAY-only slate gating:
- Only games between 12:01 AM ET and 11:59 PM ET are valid
- Ghost games (teams not playing today) are blocked
- Tomorrow games from APIs are excluded

Usage:
    from time_filters import (
        is_game_today,
        is_team_in_slate,
        validate_today_slate,
        get_today_range_et,
        filter_today_games
    )
"""

from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Any, Optional, Tuple, Set
import logging

# Try to import pytz for timezone handling
try:
    import pytz
    PYTZ_AVAILABLE = True
    ET = pytz.timezone("America/New_York")
    UTC = pytz.UTC
except ImportError:
    PYTZ_AVAILABLE = False
    ET = None
    UTC = None

logger = logging.getLogger("time_filters")


# =============================================================================
# TIMEZONE HELPERS
# =============================================================================

def get_now_et() -> datetime:
    """
    Get current datetime in America/New_York timezone.

    Returns:
        datetime in ET timezone (or naive datetime if pytz unavailable)
    """
    if PYTZ_AVAILABLE and ET:
        return datetime.now(ET)
    else:
        # Fallback: assume server is in ET or use UTC-5
        return datetime.now()


def get_today_range_et(date_str: Optional[str] = None) -> Tuple[datetime, datetime]:
    """
    Get today's valid time range in ET.

    Args:
        date_str: Optional date string (YYYY-MM-DD). If None, uses today.

    Returns:
        Tuple of (start_of_day, end_of_day) in ET
        Start: 00:00:00 ET
        End: 11:59:59 PM ET
    """
    if date_str:
        today = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        now_et = get_now_et()
        today = now_et.date()

    if PYTZ_AVAILABLE and ET:
        start = ET.localize(datetime.combine(today, dt_time(0, 0, 0)))  # 00:00:00
        end = ET.localize(datetime.combine(today, dt_time(23, 59, 59)))  # 11:59 PM
    else:
        start = datetime.combine(today, dt_time(0, 0, 0))
        end = datetime.combine(today, dt_time(23, 59, 59))

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

        # If naive datetime, assume UTC and localize
        if dt.tzinfo is None and PYTZ_AVAILABLE and UTC:
            dt = UTC.localize(dt)

        # Convert to ET
        if PYTZ_AVAILABLE and ET and dt.tzinfo:
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
    if PYTZ_AVAILABLE and ET:
        if game_dt.tzinfo is None:
            game_dt = ET.localize(game_dt)
        game_dt = game_dt.astimezone(ET)

    is_today = start_et <= game_dt <= end_et

    if not is_today:
        logger.debug("Game at %s is not today (ET range: %s - %s)",
                    game_dt, start_et, end_et)

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
    if PYTZ_AVAILABLE and ET:
        if game_dt.tzinfo is None:
            game_dt = ET.localize(game_dt)
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
    if PYTZ_AVAILABLE and ET:
        if game_dt.tzinfo is None:
            game_dt = ET.localize(game_dt)
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

    if PYTZ_AVAILABLE and ET:
        if game_dt.tzinfo is None:
            game_dt = ET.localize(game_dt)
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
    if PYTZ_AVAILABLE and ET:
        if game_dt.tzinfo is None:
            game_dt = ET.localize(game_dt)
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

def et_day_bounds(date_str: Optional[str] = None) -> Tuple[datetime, datetime]:
    """
    Get ET day bounds. If date_str None, use today.

    Args:
        date_str: Optional date string (YYYY-MM-DD)

    Returns:
        Tuple of (start, end) datetimes in ET
    """
    if date_str:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        day = get_now_et().date()

    if PYTZ_AVAILABLE and ET:
        start = ET.localize(datetime.combine(day, dt_time(0, 0, 0)))
        end = ET.localize(datetime.combine(day, dt_time(23, 59, 59)))
    else:
        start = datetime.combine(day, dt_time(0, 0, 0))
        end = datetime.combine(day, dt_time(23, 59, 59))

    return start, end


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
    start, end = et_day_bounds(date_str)
    if PYTZ_AVAILABLE and ET:
        if game_dt.tzinfo is None:
            game_dt = ET.localize(game_dt)
        game_dt = game_dt.astimezone(ET)
    else:
        # Without pytz, bounds are naive — strip tzinfo for comparison
        if game_dt.tzinfo is not None:
            # Approximate ET as UTC-5 offset
            from datetime import timezone, timedelta as _td
            et_offset = timezone(_td(hours=-5))
            game_dt = game_dt.astimezone(et_offset).replace(tzinfo=None)
    return start <= game_dt <= end


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
