"""
WEATHER MODULE - Weather data for outdoor sports

STATUS: EXPLICITLY DISABLED (WEATHER_ENABLED=false by default)
REASON: OpenWeather API not yet integrated

FEATURE FLAG: Weather analysis for outdoor games (NFL, MLB, NHL outdoor)

REQUIREMENTS:
- Must provide temperature, wind, precipitation
- Must return deterministic "data missing" reason when unavailable
- NEVER breaks scoring pipeline

DATA SOURCE:
- OpenWeather API (when implemented)
- Currently: Stub returns FEATURE_DISABLED with neutral defaults

INTEGRATION:
- Set WEATHER_ENABLED=true and OPENWEATHER_API_KEY to enable
- Until then, returns {"available": false, "reason": "FEATURE_DISABLED"}
"""

from typing import Dict, Any, Optional
import logging
import os

logger = logging.getLogger("weather")

# Feature flag
WEATHER_ENABLED = os.getenv("WEATHER_ENABLED", "false").lower() == "true"
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# Weather constants
DEFAULT_TEMPERATURE = 72.0  # Neutral temperature (°F)
DEFAULT_WIND_SPEED = 5.0    # Light wind (mph)
DEFAULT_PRECIPITATION = 0.0  # No precipitation


def get_weather_for_game(
    sport: str,
    home_team: str,
    venue: str = "",
    game_time: str = ""
) -> Dict[str, Any]:
    """
    Get weather conditions for a game.

    Args:
        sport: Sport code (NFL, MLB, NHL)
        home_team: Home team name
        venue: Venue name (optional)
        game_time: Game start time ISO format (optional)

    Returns:
        Weather data dict with status
    """
    if not WEATHER_ENABLED:
        return {
            "available": False,
            "reason": "FEATURE_DISABLED",
            "message": "Weather analysis feature is disabled",
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION,
            "conditions": "UNKNOWN"
        }

    if not OPENWEATHER_API_KEY:
        return {
            "available": False,
            "reason": "API_KEY_MISSING",
            "message": "OpenWeather API key not configured",
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION,
            "conditions": "UNKNOWN"
        }

    # Future implementation: Call OpenWeather API
    logger.info("Weather: Stub implementation - returning defaults for %s @ %s", sport, home_team)

    return {
        "available": False,
        "reason": "NOT_IMPLEMENTED",
        "message": "Weather API integration pending implementation",
        "temperature": DEFAULT_TEMPERATURE,
        "wind_speed": DEFAULT_WIND_SPEED,
        "precipitation": DEFAULT_PRECIPITATION,
        "conditions": "UNKNOWN"
    }


def is_outdoor_sport(sport: str) -> bool:
    """Check if sport is typically played outdoors."""
    outdoor_sports = {"NFL", "MLB", "NCAAF"}
    return sport.upper() in outdoor_sports


def is_weather_relevant(sport: str, venue: str = "") -> bool:
    """
    Check if weather is relevant for this game.

    Args:
        sport: Sport code
        venue: Venue name (to check if outdoor/dome)

    Returns:
        True if weather should be considered
    """
    if not is_outdoor_sport(sport):
        return False

    # Known domes (NFL)
    domes = {
        "at&t stadium",
        "mercedes-benz superdome",
        "sofi stadium",
        "lucas oil stadium",
        "u.s. bank stadium",
        "allegiant stadium",
        "state farm stadium"
    }

    venue_lower = venue.lower()
    if any(dome in venue_lower for dome in domes):
        return False

    return True


def calculate_weather_impact(
    sport: str,
    temperature: float,
    wind_speed: float,
    precipitation: float
) -> Dict[str, Any]:
    """
    Calculate weather impact on game.

    Args:
        sport: Sport code
        temperature: Temperature in °F
        wind_speed: Wind speed in mph
        precipitation: Precipitation in inches

    Returns:
        Impact assessment dict
    """
    impact = {
        "overall_impact": "NONE",
        "scoring_impact": 0.0,
        "passing_impact": 0.0,
        "kicking_impact": 0.0,
        "reasons": []
    }

    if not is_outdoor_sport(sport):
        impact["reasons"].append("Indoor sport - weather not relevant")
        return impact

    # Temperature impact
    if temperature < 32:
        impact["overall_impact"] = "HIGH"
        impact["scoring_impact"] = -0.3
        impact["passing_impact"] = -0.5
        impact["reasons"].append(f"Cold weather ({temperature}°F) reduces passing efficiency")
    elif temperature > 90:
        impact["overall_impact"] = "MEDIUM"
        impact["scoring_impact"] = -0.1
        impact["reasons"].append(f"Hot weather ({temperature}°F) may fatigue players")

    # Wind impact
    if wind_speed > 20:
        impact["overall_impact"] = "HIGH"
        impact["passing_impact"] = -0.8
        impact["kicking_impact"] = -0.6
        impact["reasons"].append(f"High winds ({wind_speed} mph) affect passing and kicking")
    elif wind_speed > 15:
        impact["overall_impact"] = "MEDIUM"
        impact["passing_impact"] = -0.4
        impact["kicking_impact"] = -0.3
        impact["reasons"].append(f"Moderate winds ({wind_speed} mph) affect passing game")

    # Precipitation impact
    if precipitation > 0.5:
        impact["overall_impact"] = "HIGH"
        impact["scoring_impact"] = -0.5
        impact["passing_impact"] = -0.6
        impact["reasons"].append(f"Heavy precipitation ({precipitation} in) reduces scoring")
    elif precipitation > 0.1:
        impact["overall_impact"] = "MEDIUM"
        impact["scoring_impact"] = -0.2
        impact["reasons"].append(f"Light precipitation ({precipitation} in) may affect game")

    return impact
