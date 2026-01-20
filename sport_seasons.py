"""
Sport Season Gating Module
==========================
v10.31: Mandatory sport season enforcement

Rules:
- If a sport is out of season -> endpoints return empty cleanly
- NFL is NOT optional: if in-season, it must be included
- If in-season but no games -> return empty (no filler)
"""

from datetime import datetime, date
from typing import Dict, Tuple, Optional
from loguru import logger


# Season definitions (month, day) for start and end
# NFL spans year boundary (Sept -> Feb)
SEASONS: Dict[str, Dict[str, Tuple[int, int]]] = {
    "NFL": {"start_mmdd": (9, 1), "end_mmdd": (2, 20)},      # Sept -> Feb (spans year)
    "NBA": {"start_mmdd": (10, 1), "end_mmdd": (6, 30)},     # Oct -> Jun
    "NHL": {"start_mmdd": (10, 1), "end_mmdd": (6, 30)},     # Oct -> Jun
    "MLB": {"start_mmdd": (3, 1), "end_mmdd": (11, 15)},     # Mar -> Nov
    "NCAAB": {"start_mmdd": (10, 15), "end_mmdd": (4, 15)},  # Oct -> Apr
}

# Friendly names for logging
SPORT_NAMES = {
    "NFL": "NFL Football",
    "NBA": "NBA Basketball",
    "NHL": "NHL Hockey",
    "MLB": "MLB Baseball",
    "NCAAB": "NCAA Basketball",
}


def is_in_season(sport: str, today: Optional[date] = None) -> bool:
    """
    Check if a sport is currently in season.

    Args:
        sport: Sport code (NFL, NBA, NHL, MLB, NCAAB)
        today: Date to check (defaults to current date)

    Returns:
        True if sport is in season, False otherwise

    Examples:
        >>> is_in_season("NFL", date(2026, 1, 15))  # Mid-January
        True
        >>> is_in_season("NFL", date(2026, 5, 15))  # Mid-May
        False
        >>> is_in_season("MLB", date(2026, 7, 4))   # July 4th
        True
    """
    sport = (sport or "").upper()

    if today is None:
        today = datetime.now().date()

    if sport not in SEASONS:
        logger.warning(f"Unknown sport '{sport}' - treating as out of season")
        return False

    season = SEASONS[sport]
    sm, sd = season["start_mmdd"]
    em, ed = season["end_mmdd"]

    start = date(today.year, sm, sd)
    end = date(today.year, em, ed)

    # Handle seasons spanning new year (NFL: Sept -> Feb)
    if end < start:
        # Season wraps around year boundary
        # In season if: today >= start (this year) OR today <= end (next year's end)
        return today >= start or today <= end

    # Normal season within same year
    return start <= today <= end


def get_in_season_sports(today: Optional[date] = None) -> list:
    """
    Get list of all sports currently in season.

    Args:
        today: Date to check (defaults to current date)

    Returns:
        List of sport codes that are in season
    """
    if today is None:
        today = datetime.now().date()

    return [sport for sport in SEASONS.keys() if is_in_season(sport, today)]


def get_season_info(sport: str, today: Optional[date] = None) -> dict:
    """
    Get detailed season information for a sport.

    Args:
        sport: Sport code
        today: Date to check

    Returns:
        Dict with season status and dates
    """
    sport = (sport or "").upper()

    if today is None:
        today = datetime.now().date()

    if sport not in SEASONS:
        return {
            "sport": sport,
            "valid": False,
            "in_season": False,
            "message": f"Unknown sport: {sport}"
        }

    season = SEASONS[sport]
    sm, sd = season["start_mmdd"]
    em, ed = season["end_mmdd"]

    in_season = is_in_season(sport, today)

    # Calculate next season start/end for messaging
    if em < sm:  # Spans year boundary
        if today.month >= sm:
            # We're in or past season start this year
            season_start = date(today.year, sm, sd)
            season_end = date(today.year + 1, em, ed)
        else:
            # We're before season start this year
            season_start = date(today.year - 1, sm, sd) if today <= date(today.year, em, ed) else date(today.year, sm, sd)
            season_end = date(today.year, em, ed)
    else:
        season_start = date(today.year, sm, sd)
        season_end = date(today.year, em, ed)

    return {
        "sport": sport,
        "sport_name": SPORT_NAMES.get(sport, sport),
        "valid": True,
        "in_season": in_season,
        "season_start": season_start.isoformat(),
        "season_end": season_end.isoformat(),
        "message": f"{SPORT_NAMES.get(sport, sport)} is {'IN SEASON' if in_season else 'OFF-SEASON'}",
        "checked_date": today.isoformat()
    }


def get_off_season_response(sport: str) -> dict:
    """
    Generate a clean off-season response for an endpoint.

    Args:
        sport: Sport code

    Returns:
        Standard off-season response dict
    """
    sport = (sport or "").upper()
    info = get_season_info(sport)

    return {
        "sport": sport,
        "source": "production_v10.31",
        "in_season": False,
        "game_picks": {
            "count": 0,
            "picks": []
        },
        "props": {
            "count": 0,
            "picks": []
        },
        "data_message": f"Sport off-season. No picks generated. {info.get('sport_name', sport)} season runs {info.get('season_start', 'N/A')} to {info.get('season_end', 'N/A')}.",
        "season_info": info,
        "timestamp": datetime.now().isoformat()
    }


# Module-level logging on import
logger.info(f"Sport season gating loaded. Currently in-season: {get_in_season_sports()}")
