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


# ============================================================================
# v11.04: SLATE VALIDATION (Ghost Data Prevention)
# ============================================================================

def validate_today_slate(
    games: list,
    sport: str,
    tz: str = "America/New_York",
    strict: bool = True
) -> Dict[str, Any]:
    """
    Validate that games are from TODAY's official slate in the specified timezone.

    This is the guard against "ghost data" / "Lakers bug" - ensures a team can
    ONLY appear in picks if it's in today's official slate from the provider.

    Args:
        games: List of game dicts from Odds API / Playbook API
        sport: Sport code (NBA, NFL, NHL, etc.)
        tz: Timezone for "today" determination (default: America/New_York)
        strict: If True, reject games with missing/invalid start times

    Returns:
        Dict with:
            - valid_games: List of games that pass validation
            - rejected_games: List of games that failed validation with reasons
            - teams_in_slate: Set of team names that ARE playing today
            - validation_summary: Human-readable summary
    """
    import logging
    logger = logging.getLogger(__name__)

    target_tz = ZoneInfo(tz)
    now = datetime.now(target_tz)
    today = now.date()

    # Today's window: 12:01 AM → 11:59 PM in target timezone
    day_start = datetime.combine(today, time(0, 1), tzinfo=target_tz)
    day_end = datetime.combine(today, time(23, 59, 59), tzinfo=target_tz)

    valid_games = []
    rejected_games = []
    teams_in_slate = set()

    for game in games:
        game_id = game.get("id") or game.get("game_id") or "unknown"
        home_team = game.get("home_team") or game.get("homeTeam") or ""
        away_team = game.get("away_team") or game.get("awayTeam") or ""

        # Get start time from various possible field names
        start_time_raw = (
            game.get("commence_time") or
            game.get("start_time") or
            game.get("game_time") or
            game.get("startTime") or
            ""
        )

        # Validation: Must have start time
        if not start_time_raw:
            if strict:
                rejected_games.append({
                    "game_id": game_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "reason": "MISSING_START_TIME",
                    "raw_time": None
                })
                continue
            else:
                # Non-strict mode: include but log warning
                logger.warning(f"v11.04: Game {game_id} has no start_time - including anyway (non-strict)")
                valid_games.append(game)
                if home_team:
                    teams_in_slate.add(home_team)
                if away_team:
                    teams_in_slate.add(away_team)
                continue

        # Parse start time
        try:
            if isinstance(start_time_raw, str):
                if "Z" in start_time_raw:
                    game_dt = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
                elif "+" in start_time_raw or start_time_raw.endswith("-00:00"):
                    game_dt = datetime.fromisoformat(start_time_raw)
                else:
                    # Assume UTC if no timezone
                    game_dt = datetime.fromisoformat(start_time_raw)
                    if game_dt.tzinfo is None:
                        game_dt = game_dt.replace(tzinfo=UTC)
            elif isinstance(start_time_raw, datetime):
                game_dt = start_time_raw
                if game_dt.tzinfo is None:
                    game_dt = game_dt.replace(tzinfo=UTC)
            else:
                raise ValueError(f"Unexpected type: {type(start_time_raw)}")

            # Convert to target timezone
            game_dt_local = game_dt.astimezone(target_tz)

        except Exception as e:
            rejected_games.append({
                "game_id": game_id,
                "home_team": home_team,
                "away_team": away_team,
                "reason": f"PARSE_ERROR: {str(e)}",
                "raw_time": start_time_raw
            })
            continue

        # Validation: Must be within today's window
        if not (day_start <= game_dt_local <= day_end):
            rejected_games.append({
                "game_id": game_id,
                "home_team": home_team,
                "away_team": away_team,
                "reason": "NOT_TODAY",
                "raw_time": start_time_raw,
                "parsed_local": game_dt_local.isoformat(),
                "game_date": game_dt_local.date().isoformat(),
                "today_date": today.isoformat()
            })
            continue

        # Validation passed - add to valid games and teams
        valid_games.append(game)
        if home_team:
            teams_in_slate.add(home_team)
        if away_team:
            teams_in_slate.add(away_team)

    # Build summary
    summary_parts = [
        f"v11.04 Slate Validation ({sport.upper()})",
        f"Timezone: {tz}",
        f"Today: {today.isoformat()}",
        f"Window: {day_start.strftime('%I:%M %p')} - {day_end.strftime('%I:%M %p')} {tz}",
        f"Input games: {len(games)}",
        f"Valid games: {len(valid_games)}",
        f"Rejected: {len(rejected_games)}",
        f"Teams in slate: {len(teams_in_slate)}"
    ]

    if rejected_games:
        # Log rejection reasons summary
        rejection_reasons = {}
        for r in rejected_games:
            reason = r.get("reason", "UNKNOWN").split(":")[0]
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        summary_parts.append(f"Rejection breakdown: {rejection_reasons}")

    validation_summary = " | ".join(summary_parts)
    logger.info(validation_summary)

    return {
        "valid_games": valid_games,
        "rejected_games": rejected_games,
        "teams_in_slate": teams_in_slate,
        "validation_summary": validation_summary,
        "today": today.isoformat(),
        "timezone": tz
    }


def is_team_in_slate(team_name: str, teams_in_slate: set) -> bool:
    """
    Check if a team is in today's valid slate.

    This is the final guard against the "Lakers bug" - if Lakers aren't playing
    today, they cannot appear in any picks.

    Args:
        team_name: Team name to check
        teams_in_slate: Set of team names from validate_today_slate()

    Returns:
        True if team is playing today, False otherwise
    """
    if not team_name or not teams_in_slate:
        return False

    # Exact match
    if team_name in teams_in_slate:
        return True

    # Case-insensitive match
    team_lower = team_name.lower()
    for slate_team in teams_in_slate:
        if slate_team.lower() == team_lower:
            return True

    # Partial match (e.g., "Lakers" in "Los Angeles Lakers")
    for slate_team in teams_in_slate:
        if team_lower in slate_team.lower() or slate_team.lower() in team_lower:
            return True

    return False
