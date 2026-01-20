"""
External Signals Module - v10.31 Multi-API Enrichment
=====================================================
Fetches external context data to enrich Jarvis scoring:
- Weather API: NFL/MLB outdoor game conditions
- Astronomy API: Moon phase, celestial events
- NOAA Space Weather: Solar flares, geomagnetic storms
- Planetary Hours: Traditional timing context

All functions fail closed (return empty/neutral on error).
Results are cached for 15 minutes to reduce API calls.
"""

import os
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION (ENV VARS ONLY - NO HARDCODED SECRETS)
# ============================================================================

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
WEATHER_API_BASE = os.getenv("WEATHER_API_BASE", "https://api.weatherapi.com/v1")

ASTRONOMY_API_ID = os.getenv("ASTRONOMY_API_ID", "")
ASTRONOMY_API_SECRET = os.getenv("ASTRONOMY_API_SECRET", "")
ASTRONOMY_API_BASE = os.getenv("ASTRONOMY_API_BASE", "https://api.astronomyapi.com/api/v2")

NOAA_BASE_URL = os.getenv("NOAA_BASE_URL", "https://services.swpc.noaa.gov")

PLANETARY_HOURS_API_URL = os.getenv("PLANETARY_HOURS_API_URL", "")

# Cache TTL (15 minutes)
CACHE_TTL_SECONDS = 900

# In-memory cache
_cache: Dict[str, Dict[str, Any]] = {}


def _get_cached(key: str) -> Optional[Dict[str, Any]]:
    """Get cached result if not expired."""
    if key in _cache:
        entry = _cache[key]
        if datetime.now() < entry.get("expires_at", datetime.min):
            return entry.get("data")
    return None


def _set_cached(key: str, data: Dict[str, Any]):
    """Cache result with TTL."""
    _cache[key] = {
        "data": data,
        "expires_at": datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS)
    }


# ============================================================================
# WEATHER API (for NFL/MLB outdoor games)
# ============================================================================

async def get_weather_context(city: str = None, lat: float = None, lon: float = None) -> Dict[str, Any]:
    """
    Fetch weather conditions for a location.

    Used for: NFL/MLB outdoor games where weather affects play.

    Returns:
        {
            "available": bool,
            "temp_f": float,
            "wind_mph": float,
            "humidity": int,
            "condition": str,
            "is_dome": False,
            "weather_impact": "NEUTRAL" | "FAVORABLE" | "UNFAVORABLE"
        }
    """
    default_response = {
        "available": False,
        "temp_f": None,
        "wind_mph": None,
        "humidity": None,
        "condition": None,
        "is_dome": False,
        "weather_impact": "NEUTRAL"
    }

    if not WEATHER_API_KEY:
        logger.debug("Weather API key not configured")
        return default_response

    # Build location query
    if lat and lon:
        location = f"{lat},{lon}"
    elif city:
        location = city
    else:
        return default_response

    cache_key = f"weather:{location}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        url = f"{WEATHER_API_BASE}/current.json"
        params = {
            "key": WEATHER_API_KEY,
            "q": location,
            "aqi": "no"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                logger.warning(f"Weather API error: {resp.status_code}")
                return default_response

            data = resp.json()
            current = data.get("current", {})

            result = {
                "available": True,
                "temp_f": current.get("temp_f"),
                "wind_mph": current.get("wind_mph", 0),
                "humidity": current.get("humidity"),
                "condition": current.get("condition", {}).get("text", ""),
                "is_dome": False,
                "weather_impact": _calculate_weather_impact(current)
            }

            _set_cached(cache_key, result)
            return result

    except Exception as e:
        logger.warning(f"Weather API failed: {e}")
        return default_response


def _calculate_weather_impact(weather: Dict) -> str:
    """Determine if weather is favorable/unfavorable for betting."""
    wind = weather.get("wind_mph", 0)
    temp = weather.get("temp_f", 70)
    condition = weather.get("condition", {}).get("text", "").lower()

    # High wind affects passing/kicking
    if wind > 20:
        return "UNFAVORABLE"

    # Extreme temps
    if temp < 20 or temp > 95:
        return "UNFAVORABLE"

    # Precipitation
    if any(w in condition for w in ["rain", "snow", "sleet", "storm"]):
        return "UNFAVORABLE"

    # Perfect conditions
    if 50 <= temp <= 75 and wind < 10 and "clear" in condition:
        return "FAVORABLE"

    return "NEUTRAL"


# ============================================================================
# ASTRONOMY API (Moon phase, celestial events)
# ============================================================================

async def get_astronomy_context(lat: float = 40.7128, lon: float = -74.0060) -> Dict[str, Any]:
    """
    Fetch astronomical data for esoteric scoring.

    Returns:
        {
            "available": bool,
            "moon_phase": str,
            "moon_phase_pct": float (0-100),
            "moon_rise": str,
            "moon_set": str,
            "sun_rise": str,
            "sun_set": str,
            "is_full_moon": bool,
            "is_new_moon": bool,
            "moon_score_modifier": float (-0.1 to +0.1)
        }
    """
    default_response = {
        "available": False,
        "moon_phase": None,
        "moon_phase_pct": None,
        "moon_rise": None,
        "moon_set": None,
        "sun_rise": None,
        "sun_set": None,
        "is_full_moon": False,
        "is_new_moon": False,
        "moon_score_modifier": 0.0
    }

    if not ASTRONOMY_API_ID or not ASTRONOMY_API_SECRET:
        logger.debug("Astronomy API credentials not configured")
        return default_response

    cache_key = f"astronomy:{lat}:{lon}:{datetime.now().strftime('%Y-%m-%d')}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        import base64

        # Astronomy API uses Basic Auth
        auth_str = f"{ASTRONOMY_API_ID}:{ASTRONOMY_API_SECRET}"
        auth_bytes = base64.b64encode(auth_str.encode()).decode()

        url = f"{ASTRONOMY_API_BASE}/bodies/positions/moon"
        headers = {
            "Authorization": f"Basic {auth_bytes}"
        }
        params = {
            "latitude": lat,
            "longitude": lon,
            "from_date": datetime.now().strftime("%Y-%m-%d"),
            "to_date": datetime.now().strftime("%Y-%m-%d"),
            "elevation": 0,
            "time": datetime.now().strftime("%H:%M:%S")
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params=params)

            if resp.status_code != 200:
                logger.warning(f"Astronomy API error: {resp.status_code}")
                return default_response

            data = resp.json()

            # Parse moon data
            moon_data = data.get("data", {}).get("table", {}).get("rows", [{}])[0]
            moon_phase = moon_data.get("cells", [{}])[0].get("extraInfo", {}).get("phase", {})

            phase_name = moon_phase.get("string", "Unknown")
            phase_pct = moon_phase.get("fraction", 0.5) * 100

            is_full = "full" in phase_name.lower()
            is_new = "new" in phase_name.lower()

            # Moon score modifier (esoteric: full moon = heightened energy)
            modifier = 0.0
            if is_full:
                modifier = 0.05  # Small boost for full moon energy
            elif is_new:
                modifier = -0.03  # Slight reduction for new moon
            elif phase_pct > 75:
                modifier = 0.03  # Waxing gibbous

            result = {
                "available": True,
                "moon_phase": phase_name,
                "moon_phase_pct": round(phase_pct, 1),
                "moon_rise": None,  # Would need separate endpoint
                "moon_set": None,
                "sun_rise": None,
                "sun_set": None,
                "is_full_moon": is_full,
                "is_new_moon": is_new,
                "moon_score_modifier": modifier
            }

            _set_cached(cache_key, result)
            return result

    except Exception as e:
        logger.warning(f"Astronomy API failed: {e}")
        return default_response


# ============================================================================
# NOAA SPACE WEATHER (Solar flares, geomagnetic storms)
# ============================================================================

async def get_noaa_space_weather() -> Dict[str, Any]:
    """
    Fetch NOAA space weather data.

    NOAA SWPC provides free JSON endpoints:
    - Solar flare activity
    - Geomagnetic storm scale (G1-G5)
    - Radio blackout scale (R1-R5)

    Returns:
        {
            "available": bool,
            "geomagnetic_scale": int (0-5),
            "solar_flare_scale": int (0-5),
            "radio_blackout_scale": int (0-5),
            "space_weather_impact": "CALM" | "ACTIVE" | "STORM"
            "space_weather_modifier": float (-0.05 to +0.05)
        }
    """
    default_response = {
        "available": False,
        "geomagnetic_scale": 0,
        "solar_flare_scale": 0,
        "radio_blackout_scale": 0,
        "space_weather_impact": "CALM",
        "space_weather_modifier": 0.0
    }

    cache_key = f"noaa:{datetime.now().strftime('%Y-%m-%d-%H')}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        # NOAA SWPC planetary K-index (geomagnetic activity)
        kp_url = f"{NOAA_BASE_URL}/products/noaa-planetary-k-index.json"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(kp_url)

            if resp.status_code != 200:
                logger.warning(f"NOAA API error: {resp.status_code}")
                return default_response

            data = resp.json()

            # Get latest Kp value (geomagnetic index 0-9)
            # Data is array of [time_tag, Kp, Kp_fraction, a_running, station_count]
            if len(data) > 1:
                latest = data[-1]  # Most recent reading
                kp_value = float(latest[1]) if len(latest) > 1 else 0
            else:
                kp_value = 0

            # Convert Kp to G-scale (0-5)
            # Kp 5 = G1, Kp 6 = G2, Kp 7 = G3, Kp 8 = G4, Kp 9 = G5
            if kp_value >= 9:
                g_scale = 5
            elif kp_value >= 8:
                g_scale = 4
            elif kp_value >= 7:
                g_scale = 3
            elif kp_value >= 6:
                g_scale = 2
            elif kp_value >= 5:
                g_scale = 1
            else:
                g_scale = 0

            # Determine impact
            if g_scale >= 3:
                impact = "STORM"
                modifier = -0.05  # Storms = chaotic energy (slight negative)
            elif g_scale >= 1:
                impact = "ACTIVE"
                modifier = 0.02  # Active = heightened energy
            else:
                impact = "CALM"
                modifier = 0.0

            result = {
                "available": True,
                "geomagnetic_scale": g_scale,
                "kp_index": kp_value,
                "solar_flare_scale": 0,  # Would need separate endpoint
                "radio_blackout_scale": 0,
                "space_weather_impact": impact,
                "space_weather_modifier": modifier
            }

            _set_cached(cache_key, result)
            return result

    except Exception as e:
        logger.warning(f"NOAA API failed: {e}")
        return default_response


# ============================================================================
# PLANETARY HOURS (Traditional timing)
# ============================================================================

async def get_planetary_hours(lat: float = 40.7128, lon: float = -74.0060) -> Dict[str, Any]:
    """
    Get current planetary hour ruler.

    Traditional system: Each hour of the day is ruled by a planet.
    Order: Saturn, Jupiter, Mars, Sun, Venus, Mercury, Moon (repeating)

    Returns:
        {
            "available": bool,
            "current_ruler": str (planet name),
            "hour_of_day": int,
            "is_day_hour": bool,
            "planetary_modifier": float (-0.03 to +0.03)
        }
    """
    default_response = {
        "available": False,
        "current_ruler": None,
        "hour_of_day": None,
        "is_day_hour": None,
        "planetary_modifier": 0.0
    }

    # If external API is configured, use it
    if PLANETARY_HOURS_API_URL:
        cache_key = f"planetary:{datetime.now().strftime('%Y-%m-%d-%H')}"
        cached = _get_cached(cache_key)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(PLANETARY_HOURS_API_URL, params={
                    "lat": lat,
                    "lon": lon
                })

                if resp.status_code == 200:
                    data = resp.json()
                    result = {
                        "available": True,
                        "current_ruler": data.get("current_ruler", "Unknown"),
                        "hour_of_day": data.get("hour", 0),
                        "is_day_hour": data.get("is_day", True),
                        "planetary_modifier": _get_planetary_modifier(data.get("current_ruler"))
                    }
                    _set_cached(cache_key, result)
                    return result
        except Exception as e:
            logger.warning(f"Planetary Hours API failed: {e}")

    # Fallback: Calculate locally using simplified method
    return _calculate_planetary_hour_local()


def _calculate_planetary_hour_local() -> Dict[str, Any]:
    """
    Calculate planetary hour using simplified local method.

    Traditional sequence starting from Sunday sunrise:
    Sun-Venus-Mercury-Moon-Saturn-Jupiter-Mars (repeating)
    """
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()  # 0=Monday, 6=Sunday

    # Day rulers (starting Sunday=6)
    day_rulers = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]
    day_ruler = day_rulers[weekday]

    # Planetary sequence
    planets = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

    # Find starting index for today's day ruler
    try:
        start_idx = planets.index(day_ruler)
    except ValueError:
        start_idx = 0

    # Current planetary hour (simplified: equal hours)
    hour_idx = (start_idx + hour) % 7
    current_ruler = planets[hour_idx]

    return {
        "available": True,
        "current_ruler": current_ruler,
        "hour_of_day": hour,
        "is_day_hour": 6 <= hour <= 18,
        "planetary_modifier": _get_planetary_modifier(current_ruler),
        "source": "local_calculation"
    }


def _get_planetary_modifier(ruler: str) -> float:
    """
    Get score modifier based on planetary ruler.

    Traditional associations:
    - Jupiter: Expansion, luck (+0.03)
    - Venus: Harmony, balance (+0.02)
    - Sun: Vitality, success (+0.02)
    - Moon: Intuition (+0.01)
    - Mercury: Communication (neutral)
    - Mars: Action, conflict (-0.01)
    - Saturn: Restriction, delay (-0.02)
    """
    modifiers = {
        "Jupiter": 0.03,
        "Venus": 0.02,
        "Sun": 0.02,
        "Moon": 0.01,
        "Mercury": 0.0,
        "Mars": -0.01,
        "Saturn": -0.02
    }
    return modifiers.get(ruler, 0.0)


# ============================================================================
# COMBINED EXTERNAL CONTEXT (Single entry point)
# ============================================================================

async def get_external_context(
    sport: str = None,
    city: str = None,
    lat: float = None,
    lon: float = None
) -> Dict[str, Any]:
    """
    Fetch all external context in parallel.

    Args:
        sport: Sport code (NBA, NFL, etc.) - weather only for NFL/MLB
        city: City name for weather
        lat/lon: Coordinates for astronomy/planetary

    Returns:
        Combined context dict with all external signals
    """
    import asyncio

    # Default coordinates (NYC)
    lat = lat or 40.7128
    lon = lon or -74.0060

    # Fetch all in parallel
    tasks = [
        get_astronomy_context(lat, lon),
        get_noaa_space_weather(),
        get_planetary_hours(lat, lon)
    ]

    # Only fetch weather for outdoor sports
    if sport and sport.upper() in ("NFL", "MLB") and city:
        tasks.append(get_weather_context(city=city))
    else:
        tasks.append(_empty_weather())

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle exceptions gracefully
    astronomy = results[0] if not isinstance(results[0], Exception) else {"available": False}
    noaa = results[1] if not isinstance(results[1], Exception) else {"available": False}
    planetary = results[2] if not isinstance(results[2], Exception) else {"available": False}
    weather = results[3] if not isinstance(results[3], Exception) else {"available": False}

    # Calculate combined modifier (capped at ±0.25)
    total_modifier = (
        astronomy.get("moon_score_modifier", 0) +
        noaa.get("space_weather_modifier", 0) +
        planetary.get("planetary_modifier", 0)
    )
    total_modifier = max(-0.25, min(0.25, total_modifier))

    return {
        "astronomy": astronomy,
        "noaa": noaa,
        "planetary": planetary,
        "weather": weather,
        "combined_modifier": round(total_modifier, 3),
        "fetched_at": datetime.now().isoformat()
    }


async def _empty_weather() -> Dict[str, Any]:
    """Return empty weather response for non-outdoor sports."""
    return {
        "available": False,
        "weather_impact": "N/A",
        "reason": "Weather not applicable for this sport"
    }


# ============================================================================
# MICRO-BOOST CALCULATOR (for Jarvis integration)
# ============================================================================

def calculate_external_micro_boost(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate bounded micro-boost from external context.

    Max total boost: ±0.25 (never dominates picks)

    Returns:
        {
            "total_boost": float,
            "breakdown": {
                "moon": float,
                "space_weather": float,
                "planetary": float,
                "weather": float
            },
            "reasons": [str]
        }
    """
    breakdown = {}
    reasons = []

    # Moon phase
    astronomy = context.get("astronomy", {})
    if astronomy.get("available"):
        moon_mod = astronomy.get("moon_score_modifier", 0)
        breakdown["moon"] = moon_mod
        if astronomy.get("is_full_moon"):
            reasons.append("EXTERNAL: Full Moon energy +0.05")
        elif astronomy.get("is_new_moon"):
            reasons.append("EXTERNAL: New Moon energy -0.03")
        elif moon_mod > 0:
            reasons.append(f"EXTERNAL: Waxing Moon +{moon_mod:.2f}")

    # Space weather
    noaa = context.get("noaa", {})
    if noaa.get("available"):
        space_mod = noaa.get("space_weather_modifier", 0)
        breakdown["space_weather"] = space_mod
        impact = noaa.get("space_weather_impact", "CALM")
        if impact == "STORM":
            reasons.append(f"EXTERNAL: Geomagnetic Storm (G{noaa.get('geomagnetic_scale', 0)}) -0.05")
        elif impact == "ACTIVE":
            reasons.append("EXTERNAL: Active Space Weather +0.02")

    # Planetary hours
    planetary = context.get("planetary", {})
    if planetary.get("available"):
        planet_mod = planetary.get("planetary_modifier", 0)
        breakdown["planetary"] = planet_mod
        ruler = planetary.get("current_ruler", "Unknown")
        if planet_mod > 0:
            reasons.append(f"EXTERNAL: {ruler} Hour +{planet_mod:.2f}")
        elif planet_mod < 0:
            reasons.append(f"EXTERNAL: {ruler} Hour {planet_mod:.2f}")

    # Weather (NFL/MLB only)
    weather = context.get("weather", {})
    if weather.get("available"):
        impact = weather.get("weather_impact", "NEUTRAL")
        if impact == "FAVORABLE":
            breakdown["weather"] = 0.03
            reasons.append("EXTERNAL: Favorable Weather +0.03")
        elif impact == "UNFAVORABLE":
            breakdown["weather"] = -0.05
            reasons.append("EXTERNAL: Unfavorable Weather -0.05")
        else:
            breakdown["weather"] = 0.0

    # Calculate total (capped)
    total = sum(breakdown.values())
    total = max(-0.25, min(0.25, total))

    return {
        "total_boost": round(total, 3),
        "breakdown": breakdown,
        "reasons": reasons
    }
