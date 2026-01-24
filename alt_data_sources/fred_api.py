"""
FRED API Integration - v10.66
=============================
Fetches Federal Reserve Economic Data for sentiment analysis.

Key Use Cases:
1. Consumer Sentiment Index - correlates with betting behavior
2. Economic cycle detection - affects discretionary spending
3. Unemployment data - impacts betting volume
4. Alternative signal for esoteric scoring

API Docs: https://fred.stlouisfed.org/docs/api/fred/
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

# Configuration - use centralized env_config
try:
    from env_config import Config
    FRED_API_KEY = Config.FRED_API_KEY or ""
except ImportError:
    FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_API_BASE = "https://api.stlouisfed.org/fred"

# Cache for API responses (6 hours - economic data updates slowly)
_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 21600

# Key economic indicators to track
INDICATORS = {
    "UMCSENT": {
        "name": "Consumer Sentiment Index",
        "description": "University of Michigan consumer sentiment",
        "betting_impact": "High sentiment = more aggressive public betting"
    },
    "UNRATE": {
        "name": "Unemployment Rate",
        "description": "Civilian unemployment rate",
        "betting_impact": "Higher unemployment = less discretionary betting"
    },
    "CPIAUCSL": {
        "name": "Consumer Price Index",
        "description": "CPI for all urban consumers",
        "betting_impact": "High inflation = cautious spending on betting"
    },
    "VIXCLS": {
        "name": "VIX Volatility Index",
        "description": "CBOE volatility index",
        "betting_impact": "High VIX = risk-off, fewer parlays"
    }
}


def _get_cached(key: str) -> Optional[Dict[str, Any]]:
    """Get cached result if not expired."""
    if key in _cache:
        entry = _cache[key]
        if datetime.now().timestamp() < entry.get("expires_at", 0):
            return entry.get("data")
    return None


def _set_cached(key: str, data: Any):
    """Cache result with TTL."""
    _cache[key] = {
        "data": data,
        "expires_at": datetime.now().timestamp() + CACHE_TTL_SECONDS
    }


def is_fred_configured() -> bool:
    """Check if FRED API is configured."""
    return bool(FRED_API_KEY)


async def get_economic_sentiment() -> Dict[str, Any]:
    """
    Get aggregate economic sentiment from key indicators.

    Returns:
        {
            "available": bool,
            "sentiment": float,  # -1.0 (bearish) to 1.0 (bullish)
            "consumer_confidence": float,  # 0-100 scale
            "risk_appetite": str,  # HIGH, MEDIUM, LOW
            "betting_outlook": str,  # How economics affects betting
            "indicators": {
                "consumer_sentiment": float,
                "unemployment": float,
                "inflation": float
            }
        }
    """
    default_response = {
        "available": False,
        "sentiment": 0.0,
        "consumer_confidence": 50.0,
        "risk_appetite": "MEDIUM",
        "betting_outlook": "FRED not configured",
        "indicators": {},
        "source": "fred"
    }

    if not FRED_API_KEY:
        logger.debug("FRED_API_KEY not configured")
        return default_response

    cache_key = "fred_economic_sentiment"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        indicators = {}

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Fetch Consumer Sentiment (most important for betting)
            sentiment_data = await _fetch_series(client, "UMCSENT")
            if sentiment_data:
                indicators["consumer_sentiment"] = sentiment_data.get("value", 0)
                indicators["consumer_sentiment_change"] = sentiment_data.get("change", 0)

            # Fetch Unemployment
            unemployment_data = await _fetch_series(client, "UNRATE")
            if unemployment_data:
                indicators["unemployment"] = unemployment_data.get("value", 0)
                indicators["unemployment_change"] = unemployment_data.get("change", 0)

        if not indicators:
            return default_response

        # Calculate composite sentiment
        # Consumer sentiment: 70-80 = neutral, >90 = bullish, <60 = bearish
        consumer_sent = indicators.get("consumer_sentiment", 70)
        unemployment = indicators.get("unemployment", 4.0)

        # Normalize to -1 to 1 scale
        # Consumer sentiment: 50 = -1, 70 = 0, 90 = 1
        sent_normalized = (consumer_sent - 70) / 20  # -1 to 1

        # Unemployment: 3% = 1, 5% = 0, 7% = -1
        unemp_normalized = (5 - unemployment) / 2  # -1 to 1

        # Weighted composite (consumer sentiment more important)
        composite_sentiment = (sent_normalized * 0.7) + (unemp_normalized * 0.3)
        composite_sentiment = max(-1.0, min(1.0, composite_sentiment))

        # Determine risk appetite
        if composite_sentiment > 0.3:
            risk_appetite = "HIGH"
            betting_outlook = "Strong consumer confidence: Public likely betting more aggressively on favorites and parlays"
        elif composite_sentiment < -0.3:
            risk_appetite = "LOW"
            betting_outlook = "Weak consumer confidence: Public may be more conservative, fewer max bets"
        else:
            risk_appetite = "MEDIUM"
            betting_outlook = "Neutral economic conditions: Normal betting patterns expected"

        result = {
            "available": True,
            "sentiment": round(composite_sentiment, 3),
            "consumer_confidence": consumer_sent,
            "risk_appetite": risk_appetite,
            "betting_outlook": betting_outlook,
            "indicators": indicators,
            "source": "fred"
        }

        _set_cached(cache_key, result)
        logger.info(f"FRED: Economic sentiment={composite_sentiment:.2f}, risk={risk_appetite}")
        return result

    except Exception as e:
        logger.warning(f"FRED economic sentiment failed: {e}")
        return default_response


async def _fetch_series(client: httpx.AsyncClient, series_id: str) -> Optional[Dict[str, float]]:
    """Fetch a single FRED data series."""
    try:
        url = f"{FRED_API_BASE}/series/observations"

        # Get last 2 observations to calculate change
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
            "sort_order": "desc",
            "limit": 2
        }

        resp = await client.get(url, params=params)

        if resp.status_code != 200:
            return None

        data = resp.json()
        observations = data.get("observations", [])

        if not observations:
            return None

        # Get latest value
        latest = observations[0]
        value = float(latest.get("value", 0))

        # Calculate change from previous
        change = 0.0
        if len(observations) > 1:
            prev = float(observations[1].get("value", value))
            if prev > 0:
                change = ((value - prev) / prev) * 100

        return {
            "value": value,
            "change": round(change, 2),
            "date": latest.get("date", "")
        }

    except Exception as e:
        logger.debug(f"FRED series {series_id} fetch failed: {e}")
        return None


async def get_consumer_confidence() -> Dict[str, Any]:
    """
    Get consumer confidence indicator specifically.

    Returns:
        {
            "available": bool,
            "value": float,  # Index value (typically 50-110)
            "trend": str,  # UP, DOWN, STABLE
            "percentile": float,  # Historical percentile (0-100)
            "betting_impact": str
        }
    """
    default_response = {
        "available": False,
        "value": 70.0,
        "trend": "STABLE",
        "percentile": 50.0,
        "betting_impact": "FRED not configured",
        "source": "fred"
    }

    if not FRED_API_KEY:
        return default_response

    cache_key = "fred_consumer_confidence"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            data = await _fetch_series(client, "UMCSENT")

            if not data:
                return default_response

            value = data.get("value", 70)
            change = data.get("change", 0)

            # Determine trend
            if change > 2:
                trend = "UP"
            elif change < -2:
                trend = "DOWN"
            else:
                trend = "STABLE"

            # Calculate percentile (historical range roughly 50-110)
            percentile = ((value - 50) / 60) * 100
            percentile = max(0, min(100, percentile))

            # Betting impact
            if value > 85:
                betting_impact = "High confidence: Expect heavier public action on favorites"
            elif value > 70:
                betting_impact = "Normal confidence: Standard betting patterns"
            else:
                betting_impact = "Low confidence: Public may be more selective with bets"

            result = {
                "available": True,
                "value": value,
                "trend": trend,
                "change_pct": change,
                "percentile": round(percentile, 1),
                "betting_impact": betting_impact,
                "source": "fred"
            }

            _set_cached(cache_key, result)
            return result

    except Exception as e:
        logger.warning(f"FRED consumer confidence failed: {e}")
        return default_response


def get_fred_status() -> Dict[str, Any]:
    """Get FRED API configuration status."""
    return {
        "configured": is_fred_configured(),
        "api_key_set": bool(FRED_API_KEY),
        "indicators_tracked": list(INDICATORS.keys()),
        "features": ["economic_sentiment", "consumer_confidence"],
        "cache_ttl": CACHE_TTL_SECONDS
    }
