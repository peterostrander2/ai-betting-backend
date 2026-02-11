"""
FRED (Federal Reserve Economic Data) Client

Provides economic sentiment signals for Engine 3 (Esoteric).
Consumer sentiment and economic conditions affect public betting behavior.

API: https://api.stlouisfed.org/fred/series/observations
Cost: FREE (requires API key from https://fred.stlouisfed.org/docs/api/api_key.html)
Rate limit: 120 requests per minute

Key Series:
- UMCSENT: University of Michigan Consumer Sentiment (monthly)
- VIXCLS: CBOE Volatility Index (daily)
- UNRATE: Unemployment Rate (monthly)
"""

import os
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger("fred")

# Config
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_ENABLED = bool(FRED_API_KEY)

# Cache (economic data doesn't change frequently)
_fred_cache: Dict[str, Any] = {}
_fred_cache_time: Dict[str, float] = {}
FRED_CACHE_TTL = 6 * 60 * 60  # 6 hours

# Key economic series
ECONOMIC_SERIES = {
    "UMCSENT": {
        "name": "Consumer Sentiment",
        "frequency": "monthly",
        "interpretation": "High sentiment = more casual bettors = fade public"
    },
    "VIXCLS": {
        "name": "VIX Volatility Index",
        "frequency": "daily",
        "interpretation": "High VIX = fear/uncertainty = emotional betting"
    },
    "UNRATE": {
        "name": "Unemployment Rate",
        "frequency": "monthly",
        "interpretation": "Economic stress indicator"
    }
}


def _mark_fred_used() -> None:
    """Mark FRED integration as used."""
    try:
        from integration_registry import mark_integration_used
        mark_integration_used("fred")
    except Exception as e:
        logger.debug("fred mark_integration_used failed: %s", str(e))


def get_fred_auth_context() -> Dict[str, Any]:
    """Get FRED auth context for semantic audit."""
    return {
        "auth_type": "api_key",
        "key_present": FRED_ENABLED,
        "key_source": "env:FRED_API_KEY" if FRED_ENABLED else "none",
        "enabled": FRED_ENABLED,
    }


def fetch_fred_series(series_id: str, limit: int = 10) -> Dict[str, Any]:
    """
    Fetch recent observations from a FRED series.

    Args:
        series_id: FRED series ID (e.g., "UMCSENT", "VIXCLS")
        limit: Number of recent observations to fetch

    Returns:
        Dict with observations, latest_value, series_info
    """
    if not FRED_ENABLED:
        return {
            "series_id": series_id,
            "status": "DISABLED",
            "reason": "FRED_API_KEY not set",
            "latest_value": None
        }

    # Check cache
    cache_key = f"{series_id}_{limit}"
    now = time.time()
    if cache_key in _fred_cache and (now - _fred_cache_time.get(cache_key, 0)) < FRED_CACHE_TTL:
        _mark_fred_used()
        return {**_fred_cache[cache_key], "from_cache": True}

    try:
        import httpx

        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.get(FRED_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

        observations = data.get("observations", [])

        if not observations:
            return {
                "series_id": series_id,
                "status": "NO_DATA",
                "reason": "No observations returned",
                "latest_value": None
            }

        # Get latest non-null value
        latest_value = None
        latest_date = None
        for obs in observations:
            val = obs.get("value")
            if val and val != ".":
                try:
                    latest_value = float(val)
                    latest_date = obs.get("date")
                    break
                except ValueError:
                    continue

        result = {
            "series_id": series_id,
            "status": "SUCCESS",
            "latest_value": latest_value,
            "latest_date": latest_date,
            "observations": observations[:5],  # Last 5 for trend
            "series_info": ECONOMIC_SERIES.get(series_id, {}),
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            "from_cache": False
        }

        # Update cache
        _fred_cache[cache_key] = result
        _fred_cache_time[cache_key] = now

        _mark_fred_used()
        logger.info("FRED %s fetched: %.2f (%s)", series_id, latest_value or 0, latest_date)
        return result

    except Exception as e:
        logger.warning("FRED API error for %s: %s", series_id, e)
        return {
            "series_id": series_id,
            "status": "ERROR",
            "error": str(e),
            "latest_value": None
        }


def get_consumer_sentiment() -> Dict[str, Any]:
    """
    Get University of Michigan Consumer Sentiment Index.

    High sentiment (>100) = optimistic public = more recreational bettors
    Low sentiment (<80) = pessimistic = risk-averse betting behavior

    Returns:
        Dict with sentiment value, score (0-1), and betting interpretation
    """
    data = fetch_fred_series("UMCSENT", limit=5)

    if data.get("status") != "SUCCESS":
        return {
            "sentiment_value": None,
            "score": 0.5,  # Neutral default
            "status": data.get("status", "ERROR"),
            "triggered": False,
            "reason": data.get("reason") or data.get("error"),
            "betting_signal": "NEUTRAL"
        }

    sentiment = data.get("latest_value", 100)

    # Score interpretation:
    # High sentiment (>100) = public is optimistic = fade public plays (score closer to 1)
    # Low sentiment (<80) = public cautious = less value in fading (score closer to 0)
    if sentiment >= 105:
        score = 0.9
        signal = "FADE_PUBLIC"
        reason = f"Consumer sentiment very high ({sentiment}) - fade recreational bettors"
        triggered = True
    elif sentiment >= 95:
        score = 0.7
        signal = "SLIGHT_FADE"
        reason = f"Consumer sentiment elevated ({sentiment}) - slight public fade value"
        triggered = True
    elif sentiment >= 85:
        score = 0.5
        signal = "NEUTRAL"
        reason = f"Consumer sentiment normal ({sentiment})"
        triggered = False
    elif sentiment >= 75:
        score = 0.4
        signal = "CAUTIOUS_PUBLIC"
        reason = f"Consumer sentiment low ({sentiment}) - public betting cautiously"
        triggered = False
    else:
        score = 0.3
        signal = "FEAR"
        reason = f"Consumer sentiment very low ({sentiment}) - fear in markets"
        triggered = True

    return {
        "sentiment_value": sentiment,
        "score": score,
        "status": "SUCCESS",
        "triggered": triggered,
        "reason": reason,
        "betting_signal": signal,
        "latest_date": data.get("latest_date"),
        "source": "fred_umcsent"
    }


def get_vix_signal() -> Dict[str, Any]:
    """
    Get CBOE Volatility Index (VIX) signal.

    VIX measures market fear/uncertainty:
    - Low VIX (<15) = calm markets = normal betting patterns
    - High VIX (>25) = fear/volatility = emotional betting, contrarian value

    Returns:
        Dict with VIX value, score, and betting interpretation
    """
    data = fetch_fred_series("VIXCLS", limit=5)

    if data.get("status") != "SUCCESS":
        return {
            "vix_value": None,
            "score": 0.5,
            "status": data.get("status", "ERROR"),
            "triggered": False,
            "reason": data.get("reason") or data.get("error"),
            "market_state": "UNKNOWN"
        }

    vix = data.get("latest_value", 20)

    # Score interpretation:
    # High VIX = fear = emotional betting = contrarian value
    if vix >= 30:
        score = 0.9
        state = "EXTREME_FEAR"
        reason = f"VIX very high ({vix:.1f}) - extreme market fear, contrarian plays valuable"
        triggered = True
    elif vix >= 25:
        score = 0.75
        state = "ELEVATED_FEAR"
        reason = f"VIX elevated ({vix:.1f}) - market uncertainty, emotional betting likely"
        triggered = True
    elif vix >= 20:
        score = 0.55
        state = "NORMAL"
        reason = f"VIX normal ({vix:.1f}) - standard market conditions"
        triggered = False
    elif vix >= 15:
        score = 0.45
        state = "CALM"
        reason = f"VIX low ({vix:.1f}) - calm markets, rational betting"
        triggered = False
    else:
        score = 0.35
        state = "COMPLACENT"
        reason = f"VIX very low ({vix:.1f}) - market complacency"
        triggered = False

    return {
        "vix_value": vix,
        "score": score,
        "status": "SUCCESS",
        "triggered": triggered,
        "reason": reason,
        "market_state": state,
        "latest_date": data.get("latest_date"),
        "source": "fred_vixcls"
    }


def get_economic_betting_signal() -> Dict[str, Any]:
    """
    Get combined economic signal for betting.

    Aggregates consumer sentiment and VIX into a single esoteric signal.

    Returns:
        Dict with combined score, components, and betting recommendation
    """
    sentiment = get_consumer_sentiment()
    vix = get_vix_signal()

    # Weight: 60% sentiment, 40% VIX
    sentiment_score = sentiment.get("score", 0.5)
    vix_score = vix.get("score", 0.5)

    combined_score = (sentiment_score * 0.6) + (vix_score * 0.4)

    # Determine if signal is actionable
    triggered = sentiment.get("triggered", False) or vix.get("triggered", False)

    # Build recommendation
    if combined_score >= 0.75:
        recommendation = "Strong contrarian signal - public likely betting emotionally"
    elif combined_score >= 0.6:
        recommendation = "Moderate fade-public signal"
    elif combined_score <= 0.35:
        recommendation = "Public betting rationally - less contrarian value"
    else:
        recommendation = "Neutral economic conditions"

    return {
        "combined_score": round(combined_score, 3),
        "triggered": triggered,
        "recommendation": recommendation,
        "components": {
            "consumer_sentiment": sentiment,
            "vix": vix
        },
        "status": "SUCCESS" if (sentiment.get("status") == "SUCCESS" or vix.get("status") == "SUCCESS") else "PARTIAL",
        "source": "fred_economic"
    }


# Export
__all__ = [
    "FRED_ENABLED",
    "get_fred_auth_context",
    "fetch_fred_series",
    "get_consumer_sentiment",
    "get_vix_signal",
    "get_economic_betting_signal",
]
