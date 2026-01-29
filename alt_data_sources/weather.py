"""
WEATHER MODULE - Weather data for outdoor sports

STATUS: Real integration with WeatherAPI.com
FEATURE FLAG: WEATHER_ENABLED (default: false)

REQUIREMENTS:
- Must provide temperature, wind, precipitation
- Must return deterministic "data missing" reason when unavailable
- NEVER breaks scoring pipeline
- Caching by stadium_id with 10-15 min TTL

DATA SOURCE:
- WeatherAPI.com (https://api.weatherapi.com)
- Requires WEATHER_API_KEY environment variable

INTEGRATION:
- Set WEATHER_ENABLED=true and WEATHER_API_KEY to enable
- Returns {available: false, reason: "FEATURE_DISABLED"} when disabled
- Returns bounded weather_modifier capped at ±1.0
"""

from typing import Dict, Any, Optional, Tuple
import logging
import os
import time
import asyncio

logger = logging.getLogger("weather")

# Feature flag
WEATHER_ENABLED = os.getenv("WEATHER_ENABLED", "false").lower() == "true"
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")

# Weather constants
DEFAULT_TEMPERATURE = 72.0  # Neutral temperature (°F)
DEFAULT_WIND_SPEED = 5.0    # Light wind (mph)
DEFAULT_PRECIPITATION = 0.0  # No precipitation

# Cache configuration
CACHE_TTL_SECONDS = 600  # 10 minutes
_weather_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

# WeatherAPI.com configuration
WEATHER_API_BASE_URL = "https://api.weatherapi.com/v1/current.json"
FETCH_TIMEOUT_SECONDS = 5.0  # Never block more than 5 seconds


def _get_cache(stadium_id: str) -> Optional[Dict[str, Any]]:
    """Get cached weather data if valid."""
    if stadium_id in _weather_cache:
        cached_time, cached_data = _weather_cache[stadium_id]
        if time.time() - cached_time < CACHE_TTL_SECONDS:
            logger.debug("Weather cache HIT for %s", stadium_id)
            return cached_data
        else:
            # Expired
            del _weather_cache[stadium_id]
            logger.debug("Weather cache EXPIRED for %s", stadium_id)
    return None


def _set_cache(stadium_id: str, data: Dict[str, Any]) -> None:
    """Cache weather data."""
    _weather_cache[stadium_id] = (time.time(), data)
    logger.debug("Weather cache SET for %s (TTL=%ds)", stadium_id, CACHE_TTL_SECONDS)


async def fetch_weather_from_api(
    lat: float,
    lon: float,
    stadium_id: str
) -> Dict[str, Any]:
    """
    Fetch weather from OpenWeather API with caching.

    NEVER blocks - returns error dict on failure.
    Cached by stadium_id with 10-minute TTL.

    Args:
        lat: Latitude
        lon: Longitude
        stadium_id: Stadium ID for caching

    Returns:
        Weather data dict with temperature, wind_speed, precipitation, conditions
    """
    # Check cache first
    cached = _get_cache(stadium_id)
    if cached:
        return cached

    # Feature flag check
    if not WEATHER_ENABLED:
        return {
            "available": False,
            "reason": "FEATURE_DISABLED",
            "message": "Weather analysis feature is disabled",
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION,
            "conditions": "UNKNOWN",
            "weather_modifier": 0.0,
            "weather_reasons": []
        }

    # API key check
    if not WEATHER_API_KEY:
        return {
            "available": False,
            "reason": "API_KEY_MISSING",
            "message": "Weather API key not configured",
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION,
            "conditions": "UNKNOWN",
            "weather_modifier": 0.0,
            "weather_reasons": []
        }

    # Import httpx here to avoid import errors if not installed
    try:
        import httpx
    except ImportError:
        logger.error("httpx not installed - cannot fetch weather")
        return {
            "available": False,
            "reason": "DEPENDENCY_MISSING",
            "message": "httpx library not installed",
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION,
            "conditions": "UNKNOWN",
            "weather_modifier": 0.0,
            "weather_reasons": []
        }

    # Fetch from WeatherAPI.com
    try:
        params = {
            "key": WEATHER_API_KEY,
            "q": f"{lat},{lon}",
            "aqi": "no"
        }

        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS) as client:
            response = await client.get(WEATHER_API_BASE_URL, params=params)

            if response.status_code != 200:
                logger.warning("WeatherAPI error: %d - %s", response.status_code, response.text[:200])
                return {
                    "available": False,
                    "reason": "API_ERROR",
                    "message": f"WeatherAPI returned {response.status_code}",
                    "temperature": DEFAULT_TEMPERATURE,
                    "wind_speed": DEFAULT_WIND_SPEED,
                    "precipitation": DEFAULT_PRECIPITATION,
                    "conditions": "UNKNOWN",
                    "weather_modifier": 0.0,
                    "weather_reasons": []
                }

            data = response.json()

            # Parse WeatherAPI.com response
            current = data.get("current", {})
            temp_f = current.get("temp_f", DEFAULT_TEMPERATURE)
            wind_mph = current.get("wind_mph", DEFAULT_WIND_SPEED)

            # Precipitation in inches
            precip_in = current.get("precip_in", 0.0)

            # Weather conditions
            condition = current.get("condition", {})
            conditions = condition.get("text", "Clear")
            description = conditions

            result = {
                "available": True,
                "reason": "SUCCESS",
                "message": f"Weather fetched for {stadium_id}",
                "temperature": round(temp_f, 1),
                "wind_speed": round(wind_mph, 1),
                "precipitation": round(precip_in, 2),
                "conditions": conditions,
                "description": description,
                "humidity": current.get("humidity", 50),
                "source": "weatherapi",
                "fetched_at": time.time()
            }

            # Calculate weather modifier
            modifier_result = calculate_weather_modifier(
                temp_f=temp_f,
                wind_mph=wind_mph,
                precip_in=precip_in,
                sport="NFL"  # Default, will be overridden by caller
            )
            result["weather_modifier"] = modifier_result["weather_modifier"]
            result["weather_reasons"] = modifier_result["reasons"]
            result["weather_score"] = modifier_result["weather_score"]

            # Cache the result
            _set_cache(stadium_id, result)

            logger.info("Weather fetched for %s: %.1f°F, %.1f mph wind, %.2f in precip, %s",
                       stadium_id, temp_f, wind_mph, precip_in, conditions)

            return result

    except asyncio.TimeoutError:
        logger.warning("Weather API timeout for %s", stadium_id)
        return {
            "available": False,
            "reason": "FETCH_TIMEOUT",
            "message": f"Weather fetch timed out after {FETCH_TIMEOUT_SECONDS}s",
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION,
            "conditions": "UNKNOWN",
            "weather_modifier": 0.0,
            "weather_reasons": []
        }
    except Exception as e:
        logger.exception("Weather fetch failed for %s: %s", stadium_id, e)
        return {
            "available": False,
            "reason": "FETCH_FAILED",
            "message": str(e)[:100],
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION,
            "conditions": "UNKNOWN",
            "weather_modifier": 0.0,
            "weather_reasons": []
        }


def calculate_weather_modifier(
    temp_f: float,
    wind_mph: float,
    precip_in: float,
    sport: str = "NFL"
) -> Dict[str, Any]:
    """
    Calculate weather impact modifier for scoring.

    Returns weather_modifier capped at ±1.0 and human-readable reasons.

    Modifier rules:
    - Cold (<32°F): -0.5
    - Hot (>90°F): -0.2
    - High wind (>20 mph): -0.4
    - Heavy rain (>0.5 in): -0.6
    - Combined cap: ±1.0
    - Indoor venue: 0.0

    Args:
        temp_f: Temperature in Fahrenheit
        wind_mph: Wind speed in mph
        precip_in: Precipitation in inches
        sport: Sport code (NFL, MLB, etc.)

    Returns:
        Dict with weather_modifier, weather_score (0-10), and reasons
    """
    modifier = 0.0
    reasons = []

    # Temperature impact
    if temp_f < 32:
        modifier -= 0.5
        reasons.append(f"Weather: Cold temps ({temp_f:.0f}°F) reduce scoring")
    elif temp_f < 40:
        modifier -= 0.3
        reasons.append(f"Weather: Chilly temps ({temp_f:.0f}°F) may affect passing")
    elif temp_f > 95:
        modifier -= 0.3
        reasons.append(f"Weather: Extreme heat ({temp_f:.0f}°F) fatigues players")
    elif temp_f > 90:
        modifier -= 0.2
        reasons.append(f"Weather: Hot temps ({temp_f:.0f}°F) may fatigue players")

    # Wind impact
    if wind_mph > 25:
        modifier -= 0.5
        reasons.append(f"Weather: Very high winds ({wind_mph:.0f} mph) affect passing/kicking")
    elif wind_mph > 20:
        modifier -= 0.4
        reasons.append(f"Weather: High winds ({wind_mph:.0f} mph) affect passing and kicking")
    elif wind_mph > 15:
        modifier -= 0.2
        reasons.append(f"Weather: Moderate winds ({wind_mph:.0f} mph) may affect passing")

    # Precipitation impact
    if precip_in > 0.5:
        modifier -= 0.6
        reasons.append(f"Weather: Heavy precipitation ({precip_in:.2f} in) reduces scoring")
    elif precip_in > 0.25:
        modifier -= 0.4
        reasons.append(f"Weather: Moderate precipitation ({precip_in:.2f} in) affects play")
    elif precip_in > 0.1:
        modifier -= 0.2
        reasons.append(f"Weather: Light precipitation ({precip_in:.2f} in) may affect game")

    # Cap modifier at ±1.0
    capped_modifier = max(-1.0, min(1.0, modifier))

    # Weather score (0-10, where 5 is neutral, 0 is worst conditions, 10 is perfect)
    # Convert modifier (-1 to +1) to score (0 to 10)
    weather_score = 5.0 + (capped_modifier * 5.0)
    weather_score = max(0.0, min(10.0, weather_score))

    # Add positive reason if good weather
    if not reasons and temp_f >= 60 and temp_f <= 75 and wind_mph < 10 and precip_in == 0:
        reasons.append(f"Weather: Ideal conditions ({temp_f:.0f}°F, light wind, no rain)")

    return {
        "weather_modifier": round(capped_modifier, 2),
        "weather_score": round(weather_score, 1),
        "reasons": reasons,
        "raw_modifier": round(modifier, 2),  # Before capping
        "components": {
            "temp_impact": round(-0.5 if temp_f < 32 else (-0.3 if temp_f < 40 else (-0.3 if temp_f > 95 else (-0.2 if temp_f > 90 else 0.0))), 2),
            "wind_impact": round(-0.5 if wind_mph > 25 else (-0.4 if wind_mph > 20 else (-0.2 if wind_mph > 15 else 0.0)), 2),
            "precip_impact": round(-0.6 if precip_in > 0.5 else (-0.4 if precip_in > 0.25 else (-0.2 if precip_in > 0.1 else 0.0)), 2)
        }
    }


def get_weather_for_game(
    sport: str,
    home_team: str,
    venue: str = "",
    game_time: str = ""
) -> Dict[str, Any]:
    """
    Get weather conditions for a game (SYNC wrapper).

    For async usage, call fetch_weather_from_api directly.

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
            "conditions": "UNKNOWN",
            "weather_modifier": 0.0,
            "weather_reasons": []
        }

    if not WEATHER_API_KEY:
        return {
            "available": False,
            "reason": "API_KEY_MISSING",
            "message": "Weather API key not configured",
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION,
            "conditions": "UNKNOWN",
            "weather_modifier": 0.0,
            "weather_reasons": []
        }

    # Try to get venue coordinates from stadium registry
    try:
        from alt_data_sources.stadium import get_venue_for_weather
        venue_info = get_venue_for_weather(home_team, sport)

        if not venue_info:
            logger.info("Weather: No venue info for %s @ %s", sport, home_team)
            return {
                "available": False,
                "reason": "VENUE_NOT_FOUND",
                "message": f"No venue data for {home_team}",
                "temperature": DEFAULT_TEMPERATURE,
                "wind_speed": DEFAULT_WIND_SPEED,
                "precipitation": DEFAULT_PRECIPITATION,
                "conditions": "UNKNOWN",
                "weather_modifier": 0.0,
                "weather_reasons": []
            }

        # Check if outdoor venue
        if not venue_info.get("is_outdoor", True):
            return {
                "available": True,
                "reason": "INDOOR_VENUE",
                "message": f"{venue_info.get('name', 'Stadium')} is indoor/dome",
                "temperature": 72.0,  # Climate controlled
                "wind_speed": 0.0,
                "precipitation": 0.0,
                "conditions": "DOME",
                "weather_modifier": 0.0,
                "weather_reasons": ["Weather: Indoor venue - weather neutral"]
            }

        # For async fetch, we need to run in event loop
        # This sync wrapper is for backwards compatibility
        lat = venue_info.get("lat", 0.0)
        lon = venue_info.get("lon", 0.0)
        stadium_id = venue_info.get("stadium_id", f"{sport}_{home_team}")

        # Check cache synchronously
        cached = _get_cache(stadium_id)
        if cached:
            return cached

        # Return pending result - actual fetch should use async
        logger.info("Weather: Sync call for %s - use async fetch_weather_from_api for live data", stadium_id)
        return {
            "available": False,
            "reason": "SYNC_CALL",
            "message": "Use async fetch_weather_from_api for live data",
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION,
            "conditions": "UNKNOWN",
            "weather_modifier": 0.0,
            "weather_reasons": [],
            "venue_info": venue_info
        }

    except ImportError:
        logger.warning("Stadium module not available for weather lookup")
        return {
            "available": False,
            "reason": "STADIUM_MODULE_MISSING",
            "message": "Stadium module not available",
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION,
            "conditions": "UNKNOWN",
            "weather_modifier": 0.0,
            "weather_reasons": []
        }


async def get_weather_modifier(
    sport: str,
    home_team: str,
    venue: str = "",
    game_time: str = ""
) -> Dict[str, Any]:
    """
    Get weather modifier for scoring integration (ASYNC).

    This is the primary function for scoring pipeline integration.
    Always executes, returns 0.0 modifier if unavailable.

    Args:
        sport: Sport code (NFL, MLB)
        home_team: Home team name
        venue: Venue name (optional)
        game_time: Game start time (optional)

    Returns:
        Dict with weather_modifier, weather_reasons, available, etc.
    """
    # Check if outdoor sport
    if not is_outdoor_sport(sport):
        return {
            "available": True,
            "reason": "INDOOR_SPORT",
            "message": f"{sport} is an indoor sport",
            "weather_modifier": 0.0,
            "weather_reasons": [f"Weather: {sport} is indoor sport - weather not applicable"],
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION
        }

    # Get venue info
    try:
        from alt_data_sources.stadium import get_venue_for_weather
        venue_info = get_venue_for_weather(home_team, sport)
    except ImportError:
        venue_info = {}

    if not venue_info:
        return {
            "available": False,
            "reason": "VENUE_NOT_FOUND",
            "message": f"No venue data for {home_team}",
            "weather_modifier": 0.0,
            "weather_reasons": ["Weather: Venue not found - using neutral"],
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION
        }

    # Check if indoor venue
    if not venue_info.get("is_outdoor", True):
        return {
            "available": True,
            "reason": "INDOOR_VENUE",
            "message": f"{venue_info.get('name', 'Stadium')} is indoor/dome",
            "weather_modifier": 0.0,
            "weather_reasons": ["Weather: Indoor venue - weather neutral"],
            "temperature": 72.0,
            "wind_speed": 0.0,
            "precipitation": 0.0,
            "conditions": "DOME"
        }

    # Fetch weather data
    lat = venue_info.get("lat", 0.0)
    lon = venue_info.get("lon", 0.0)
    stadium_id = venue_info.get("stadium_id", f"{sport}_{home_team}")

    if lat == 0.0 and lon == 0.0:
        return {
            "available": False,
            "reason": "NO_COORDINATES",
            "message": "Venue coordinates not available",
            "weather_modifier": 0.0,
            "weather_reasons": ["Weather: No venue coordinates - using neutral"],
            "temperature": DEFAULT_TEMPERATURE,
            "wind_speed": DEFAULT_WIND_SPEED,
            "precipitation": DEFAULT_PRECIPITATION
        }

    # Fetch from API (with caching)
    weather_data = await fetch_weather_from_api(lat, lon, stadium_id)

    # Ensure weather_modifier is present
    if "weather_modifier" not in weather_data:
        weather_data["weather_modifier"] = 0.0
    if "weather_reasons" not in weather_data:
        weather_data["weather_reasons"] = []

    return weather_data


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
        "caesars superdome",
        "sofi stadium",
        "lucas oil stadium",
        "u.s. bank stadium",
        "allegiant stadium",
        "state farm stadium",
        "ford field",
        "nrg stadium",
        "mercedes-benz stadium"
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
    Calculate weather impact on game (legacy function).

    For new integrations, use calculate_weather_modifier instead.

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


def clear_weather_cache() -> int:
    """
    Clear the weather cache.

    Returns:
        Number of entries cleared
    """
    global _weather_cache
    count = len(_weather_cache)
    _weather_cache = {}
    logger.info("Weather cache cleared: %d entries", count)
    return count


def get_cache_stats() -> Dict[str, Any]:
    """
    Get weather cache statistics.

    Returns:
        Dict with cache stats
    """
    now = time.time()
    valid_count = 0
    expired_count = 0

    for stadium_id, (cached_time, _) in _weather_cache.items():
        if now - cached_time < CACHE_TTL_SECONDS:
            valid_count += 1
        else:
            expired_count += 1

    return {
        "total_entries": len(_weather_cache),
        "valid_entries": valid_count,
        "expired_entries": expired_count,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "enabled": WEATHER_ENABLED,
        "api_key_configured": bool(WEATHER_API_KEY)
    }
