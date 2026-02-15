"""
SPORTS.PY - Single Source of Truth for Sports Constants

This module provides:
1. Sport enum for type-safe sport references
2. SUPPORTED_SPORTS list for iteration
3. API-specific sport key mappings

Usage:
    from core.sports import Sport, SUPPORTED_SPORTS, ODDS_API_SPORTS, PLAYBOOK_LEAGUES

    # Type-safe sport reference
    sport = Sport.NBA

    # Iteration
    for sport in SUPPORTED_SPORTS:
        process_sport(sport)

    # API mappings
    odds_key = ODDS_API_SPORTS[Sport.NBA]  # "basketball_nba"
    playbook_league = PLAYBOOK_LEAGUES[Sport.NCAAB]  # "CFB"
"""

from enum import Enum
from typing import List, Dict, Set


class Sport(str, Enum):
    """
    Canonical sports enum - single source of truth.

    Inherits from str for JSON serialization compatibility.
    Use Sport.NBA.value to get "NBA" string.
    """
    NBA = "NBA"
    NFL = "NFL"
    MLB = "MLB"
    NHL = "NHL"
    NCAAB = "NCAAB"


# List of all supported sports (for iteration)
SUPPORTED_SPORTS: List[str] = [s.value for s in Sport]

# Set version for O(1) membership testing
SUPPORTED_SPORTS_SET: Set[str] = {s.value for s in Sport}


# Odds API sport keys
# Maps our internal Sport enum to Odds API sport identifiers
ODDS_API_SPORTS: Dict[Sport, str] = {
    Sport.NBA: "basketball_nba",
    Sport.NFL: "americanfootball_nfl",
    Sport.MLB: "baseball_mlb",
    Sport.NHL: "icehockey_nhl",
    Sport.NCAAB: "basketball_ncaab",
}


# Playbook API league identifiers
# Note: Playbook uses "CFB" for college basketball, not "NCAAB"
PLAYBOOK_LEAGUES: Dict[Sport, str] = {
    Sport.NBA: "NBA",
    Sport.NFL: "NFL",
    Sport.MLB: "MLB",
    Sport.NHL: "NHL",
    Sport.NCAAB: "CFB",  # Playbook uses CFB for college
}


# ESPN API sport identifiers
ESPN_SPORTS: Dict[Sport, str] = {
    Sport.NBA: "basketball/nba",
    Sport.NFL: "football/nfl",
    Sport.MLB: "baseball/mlb",
    Sport.NHL: "hockey/nhl",
    Sport.NCAAB: "basketball/mens-college-basketball",
}


def validate_sport(sport: str) -> Sport:
    """
    Validate and normalize sport string to enum.

    Args:
        sport: Sport string (case-insensitive)

    Returns:
        Sport enum value

    Raises:
        ValueError: If sport is not valid

    Example:
        >>> validate_sport("nba")
        Sport.NBA
        >>> validate_sport("INVALID")
        ValueError: Invalid sport: INVALID. Valid: ['NBA', 'NFL', 'MLB', 'NHL', 'NCAAB']
    """
    try:
        return Sport(sport.upper())
    except ValueError:
        raise ValueError(f"Invalid sport: {sport}. Valid: {SUPPORTED_SPORTS}")


def is_valid_sport(sport: str) -> bool:
    """
    Check if sport string is valid (case-insensitive).

    Args:
        sport: Sport string to check

    Returns:
        True if valid, False otherwise

    Example:
        >>> is_valid_sport("NBA")
        True
        >>> is_valid_sport("soccer")
        False
    """
    return sport.upper() in SUPPORTED_SPORTS_SET


def is_outdoor_sport(sport: Sport) -> bool:
    """
    Check if sport is played outdoors (weather-relevant).

    Used for weather_api relevance gating.

    Args:
        sport: Sport enum value

    Returns:
        True if outdoor sport (NFL, MLB), False otherwise
    """
    return sport in {Sport.NFL, Sport.MLB}


def is_indoor_sport(sport: Sport) -> bool:
    """
    Check if sport is played indoors.

    Indoor sports: NBA, NHL, NCAAB (most venues)

    Args:
        sport: Sport enum value

    Returns:
        True if indoor sport
    """
    return sport in {Sport.NBA, Sport.NHL, Sport.NCAAB}


# Export list
__all__ = [
    'Sport',
    'SUPPORTED_SPORTS',
    'SUPPORTED_SPORTS_SET',
    'ODDS_API_SPORTS',
    'PLAYBOOK_LEAGUES',
    'ESPN_SPORTS',
    'validate_sport',
    'is_valid_sport',
    'is_outdoor_sport',
    'is_indoor_sport',
]
