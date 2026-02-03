"""
REFEREE MODULE - Referee impact analysis

FEATURE FLAG: Referee tendencies and historical impact

REQUIREMENTS:
- Must provide referee name and historical stats
- Must return deterministic "data missing" reason when unavailable
- NEVER breaks scoring pipeline

DATA SOURCE:
- Referee data API (when implemented)
- For now: Stub with explicit "not implemented" status
"""

from typing import Dict, Any, Optional, List
import logging
import os

logger = logging.getLogger("refs")

# Feature flag
REFS_ENABLED = os.getenv("REFS_ENABLED", "false").lower() == "true"

# Default values
DEFAULT_FOUL_RATE = 20.0  # Neutral foul calls per game
DEFAULT_HOME_BIAS = 0.0   # No bias


def get_referee_for_game(
    sport: str,
    home_team: str,
    away_team: str,
    game_id: str = ""
) -> Dict[str, Any]:
    """
    Get referee assignment for a game.

    Args:
        sport: Sport code (NBA, NFL, NHL, MLB)
        home_team: Home team name
        away_team: Away team name
        game_id: Game identifier (optional)

    Returns:
        Referee data dict with status
    """
    if not REFS_ENABLED:
        return {
            "available": False,
            "reason": "FEATURE_DISABLED",
            "message": "Referee analysis feature is disabled",
            "referee_name": "Unknown",
            "foul_rate": DEFAULT_FOUL_RATE,
            "home_bias": DEFAULT_HOME_BIAS
        }

    # Future implementation: Call referee data API
    logger.info("Refs: Stub implementation - returning defaults for %s @ %s", away_team, home_team)

    return {
        "available": False,
        "reason": "NOT_IMPLEMENTED",
        "message": "Referee API integration pending implementation",
        "referee_name": "Unknown",
        "foul_rate": DEFAULT_FOUL_RATE,
        "home_bias": DEFAULT_HOME_BIAS
    }


def calculate_referee_impact(
    sport: str,
    referee_name: str,
    foul_rate: float,
    home_bias: float
) -> Dict[str, Any]:
    """
    Calculate referee impact on game.

    Args:
        sport: Sport code
        referee_name: Referee name
        foul_rate: Historical foul calls per game
        home_bias: Home team bias (-1 to +1)

    Returns:
        Impact assessment dict
    """
    impact = {
        "overall_impact": "NONE",
        "scoring_impact": 0.0,
        "pace_impact": 0.0,
        "home_advantage_boost": 0.0,
        "reasons": []
    }

    # NBA referee impact
    if sport.upper() == "NBA":
        # High foul rate slows game
        if foul_rate > 25:
            impact["overall_impact"] = "MEDIUM"
            impact["pace_impact"] = -0.3
            impact["scoring_impact"] = 0.1  # More FTs = more scoring
            impact["reasons"].append(f"High foul rate ({foul_rate}/game) slows pace, increases FTs")
        elif foul_rate < 15:
            impact["pace_impact"] = 0.2
            impact["reasons"].append(f"Low foul rate ({foul_rate}/game) increases pace")

        # Home bias
        if abs(home_bias) > 0.1:
            impact["overall_impact"] = "LOW"
            impact["home_advantage_boost"] = home_bias * 0.5
            if home_bias > 0:
                impact["reasons"].append(f"Referee favors home team (+{home_bias:.2f} bias)")
            else:
                impact["reasons"].append(f"Referee favors away team ({home_bias:.2f} bias)")

    # NFL referee impact
    elif sport.upper() == "NFL":
        # Flag-happy refs affect game flow
        if foul_rate > 15:
            impact["overall_impact"] = "MEDIUM"
            impact["pace_impact"] = -0.2
            impact["reasons"].append(f"High penalty rate ({foul_rate}/game) disrupts flow")

    return impact


def get_referee_history(
    sport: str,
    referee_name: str,
    last_n_games: int = 10
) -> Dict[str, Any]:
    """
    Get referee historical statistics.

    Args:
        sport: Sport code
        referee_name: Referee name
        last_n_games: Number of recent games to analyze

    Returns:
        Historical stats dict
    """
    if not REFS_ENABLED:
        return {
            "available": False,
            "reason": "FEATURE_DISABLED",
            "message": "Referee history feature is disabled"
        }

    return {
        "available": False,
        "reason": "NOT_IMPLEMENTED",
        "message": "Referee history API pending implementation",
        "games_analyzed": 0,
        "avg_foul_rate": DEFAULT_FOUL_RATE,
        "avg_home_bias": DEFAULT_HOME_BIAS
    }


# Known referee tendencies (placeholder data)
REFEREE_TENDENCIES = {
    "NBA": {
        # Example: Scott Foster (known for tight whistle)
        "scott_foster": {
            "foul_rate": 24.5,
            "home_bias": -0.05,
            "notes": "Tight whistle, calls fouls evenly"
        },
        # Example: Tony Brothers (known for home bias)
        "tony_brothers": {
            "foul_rate": 22.0,
            "home_bias": 0.15,
            "notes": "Slight home team advantage"
        }
    },
    "NFL": {
        # Placeholder
        "default": {
            "foul_rate": 12.0,
            "home_bias": 0.0
        }
    }
}


def lookup_referee_tendencies(sport: str, referee_name: str) -> Dict[str, Any]:
    """
    Lookup known referee tendencies.

    Args:
        sport: Sport code
        referee_name: Referee name

    Returns:
        Tendency dict or defaults
    """
    sport_upper = sport.upper()
    ref_lower = referee_name.lower().replace(" ", "_")

    if sport_upper not in REFEREE_TENDENCIES:
        return {
            "foul_rate": DEFAULT_FOUL_RATE,
            "home_bias": DEFAULT_HOME_BIAS,
            "notes": "No data available"
        }

    sport_refs = REFEREE_TENDENCIES[sport_upper]
    return sport_refs.get(ref_lower, sport_refs.get("default", {
        "foul_rate": DEFAULT_FOUL_RATE,
        "home_bias": DEFAULT_HOME_BIAS,
        "notes": "No data available"
    }))
