"""
NOAA Space Weather Client - Real-time Kp-Index Data

GLITCH Protocol integration for geomagnetic activity signals.
Fetches real Kp-Index from NOAA Space Weather Prediction Center.

API: https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json
Cost: FREE (public API, no key needed)
Rate limit: None specified, but cache for 3 hours (Kp updates every 3h)
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("noaa")

# Feature flag
NOAA_ENABLED = os.getenv("NOAA_ENABLED", "true").lower() == "true"

# Cache settings (Kp-Index updates every 3 hours)
_kp_cache: Dict[str, Any] = {}
_kp_cache_time: float = 0
KP_CACHE_TTL = 3 * 60 * 60  # 3 hours in seconds

# NOAA API endpoint
NOAA_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"


def fetch_kp_index_live() -> Dict[str, Any]:
    """
    Fetch real-time Kp-Index from NOAA Space Weather API.

    Returns latest Kp value and storm level assessment.
    Caches for 3 hours since Kp-Index updates every 3 hours.

    Returns:
        Dict with kp_value, storm_level, timestamp, source
    """
    global _kp_cache, _kp_cache_time

    if not NOAA_ENABLED:
        return {
            "kp_value": 3.0,
            "storm_level": "QUIET",
            "source": "disabled",
            "reason": "NOAA_DISABLED"
        }

    # Check cache
    now = time.time()
    if _kp_cache and (now - _kp_cache_time) < KP_CACHE_TTL:
        return {**_kp_cache, "source": "cache"}

    try:
        import httpx

        with httpx.Client(timeout=10.0) as client:
            response = client.get(NOAA_KP_URL)
            response.raise_for_status()
            data = response.json()

        # NOAA returns array of arrays:
        # [["time_tag", "Kp", "Kp_fraction", "a_running", "station_count"], ...]
        # First row is header, last row is most recent
        if not data or len(data) < 2:
            raise ValueError("Invalid NOAA response format")

        # Get most recent reading (last row)
        latest = data[-1]
        # Kp value is in index 1
        kp_value = float(latest[1])
        timestamp = latest[0]

        # Determine storm level
        if kp_value >= 8:
            storm_level = "EXTREME"
        elif kp_value >= 7:
            storm_level = "SEVERE"
        elif kp_value >= 6:
            storm_level = "STRONG"
        elif kp_value >= 5:
            storm_level = "MODERATE"
        elif kp_value >= 4:
            storm_level = "MINOR"
        elif kp_value >= 3:
            storm_level = "UNSETTLED"
        else:
            storm_level = "QUIET"

        result = {
            "kp_value": round(kp_value, 1),
            "storm_level": storm_level,
            "timestamp": timestamp,
            "source": "noaa_live",
            "fetched_at": datetime.utcnow().isoformat()
        }

        # Update cache
        _kp_cache = result
        _kp_cache_time = now

        logger.info("NOAA Kp-Index fetched: %.1f (%s)", kp_value, storm_level)
        return result

    except Exception as e:
        logger.warning("NOAA API error, using fallback: %s", e)
        # Return fallback (average quiet conditions)
        return {
            "kp_value": 3.0,
            "storm_level": "QUIET",
            "source": "fallback",
            "error": str(e)
        }


def get_kp_betting_signal(game_time: datetime = None) -> Dict[str, Any]:
    """
    Get Kp-Index with betting signal interpretation.

    Geomagnetic storms may affect human behavior and decision-making.
    - Quiet (Kp 0-2): Stable conditions, normal analysis
    - Unsettled (Kp 3-4): Slight volatility increase
    - Storm (Kp 5+): Increased emotional betting, potential value in contrarian plays

    Args:
        game_time: Game start time (for logging)

    Returns:
        Dict with score (0-1), reason, triggered, kp_value, storm_level, recommendation
    """
    kp_data = fetch_kp_index_live()
    kp_value = kp_data.get("kp_value", 3.0)
    storm_level = kp_data.get("storm_level", "QUIET")

    # Score interpretation for betting
    # Quiet conditions = stable = good for analysis (high score)
    # Storm conditions = volatile = reduce confidence (lower score)
    if kp_value <= 2:
        score = 0.8
        reason = f"KP_QUIET_{kp_value}"
        triggered = True
        recommendation = "Optimal conditions for analytical betting"
    elif kp_value <= 3:
        score = 0.7
        reason = f"KP_CALM_{kp_value}"
        triggered = False
        recommendation = "Normal conditions"
    elif kp_value <= 4:
        score = 0.5
        reason = f"KP_UNSETTLED_{kp_value}"
        triggered = False
        recommendation = "Slightly elevated volatility"
    elif kp_value <= 5:
        score = 0.4
        reason = f"KP_ACTIVE_{kp_value}"
        triggered = True
        recommendation = "Consider reducing position sizes"
    else:
        score = 0.3
        reason = f"KP_STORM_{kp_value}"
        triggered = True
        recommendation = "Geomagnetic storm - public may bet emotionally, contrarian value possible"

    return {
        "score": score,
        "reason": reason,
        "triggered": triggered,
        "kp_value": kp_value,
        "storm_level": storm_level,
        "recommendation": recommendation,
        "source": kp_data.get("source", "unknown"),
        "timestamp": kp_data.get("timestamp")
    }


def get_space_weather_summary() -> Dict[str, Any]:
    """
    Get comprehensive space weather summary for daily esoteric reading.

    Returns:
        Dict with kp_index, storm_activity, betting_outlook
    """
    kp_signal = get_kp_betting_signal()

    # Determine overall outlook
    if kp_signal["score"] >= 0.7:
        outlook = "FAVORABLE"
        outlook_reason = "Quiet geomagnetic conditions support clear analysis"
    elif kp_signal["score"] >= 0.5:
        outlook = "NEUTRAL"
        outlook_reason = "Normal space weather conditions"
    else:
        outlook = "CAUTION"
        outlook_reason = f"Elevated geomagnetic activity (Kp={kp_signal['kp_value']})"

    return {
        "kp_index": kp_signal,
        "betting_outlook": outlook,
        "outlook_reason": outlook_reason,
        "recommendations": [kp_signal["recommendation"]]
    }


# =============================================================================
# SOLAR X-RAY FLUX (v18.2) - Solar Flare Detection
# =============================================================================

# NOAA X-ray Flux API (GOES satellite data)
NOAA_XRAY_URL = "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json"

# Cache for X-ray flux (updates every minute, cache for 1 hour)
_xray_cache: Dict[str, Any] = {}
_xray_cache_time: float = 0
XRAY_CACHE_TTL = 60 * 60  # 1 hour


def get_solar_xray_flux() -> Dict[str, Any]:
    """
    Fetch real-time solar X-ray flux from NOAA GOES satellite (v18.2).

    X-ray flux indicates solar flare activity:
    - X-class: flux >= 1e-4 W/m² (major flare)
    - M-class: flux >= 1e-5 W/m² (moderate flare)
    - C-class: flux >= 1e-6 W/m² (minor flare)
    - B-class: flux >= 1e-7 W/m² (background)
    - A-class: flux < 1e-7 W/m² (quiet)

    Returns:
        Dict with current_flux, flare_class, source
    """
    global _xray_cache, _xray_cache_time

    if not NOAA_ENABLED:
        return {
            "current_flux": 0,
            "flare_class": "QUIET",
            "source": "disabled"
        }

    # Check cache
    now = time.time()
    if _xray_cache and (now - _xray_cache_time) < XRAY_CACHE_TTL:
        return {**_xray_cache, "source": "cache"}

    try:
        import httpx

        with httpx.Client(timeout=10.0) as client:
            response = client.get(NOAA_XRAY_URL)
            response.raise_for_status()
            data = response.json()

        if not data or len(data) < 1:
            raise ValueError("Invalid NOAA X-ray response")

        # Get most recent reading (last item)
        # Format: {"time_tag": "...", "flux": 2.53e-07, "energy": "0.1-0.8nm", ...}
        latest = data[-1]
        current_flux = float(latest.get("flux", 0))
        timestamp = latest.get("time_tag", "")

        # Determine flare class
        if current_flux >= 1e-4:
            flare_class = "X"
        elif current_flux >= 1e-5:
            flare_class = "M"
        elif current_flux >= 1e-6:
            flare_class = "C"
        elif current_flux >= 1e-7:
            flare_class = "B"
        else:
            flare_class = "A"

        result = {
            "current_flux": current_flux,
            "flare_class": flare_class,
            "timestamp": timestamp,
            "source": "noaa_live",
            "fetched_at": datetime.utcnow().isoformat()
        }

        # Update cache
        _xray_cache = result
        _xray_cache_time = now

        logger.info("NOAA X-ray flux fetched: %.2e (%s-class)", current_flux, flare_class)
        return result

    except Exception as e:
        logger.warning("NOAA X-ray API error: %s", e)
        return {
            "current_flux": 0,
            "flare_class": "QUIET",
            "source": "fallback",
            "error": str(e)
        }


# Export for integration
__all__ = [
    "fetch_kp_index_live",
    "get_kp_betting_signal",
    "get_space_weather_summary",
    "get_solar_xray_flux",
    "NOAA_ENABLED",
]
