"""
Finnhub Market Data Client

Provides market sentiment signals for Engine 3 (Esoteric).
Stock market conditions correlate with public betting behavior.

API: https://finnhub.io/docs/api
Cost: Free tier = 60 API calls/minute
Rate limit: 60 calls/minute on free tier

Key Endpoints:
- /quote: Real-time stock quotes (SPY for market proxy)
- /news: Market news sentiment
- /market-status: Market open/close status
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger("finnhub")

# Config
FINNHUB_KEY = os.getenv("FINNHUB_KEY") or os.getenv("FINNHUB_API_KEY", "")
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
FINNHUB_ENABLED = bool(FINNHUB_KEY)

# Cache
_finnhub_cache: Dict[str, Any] = {}
_finnhub_cache_time: Dict[str, float] = {}
FINNHUB_CACHE_TTL = 15 * 60  # 15 minutes (market data updates frequently)


def _mark_finnhub_used() -> None:
    """Mark Finnhub integration as used."""
    try:
        from integration_registry import mark_integration_used
        mark_integration_used("finnhub")
    except Exception as e:
        logger.debug("finnhub mark_integration_used failed: %s", str(e))


def get_finnhub_auth_context() -> Dict[str, Any]:
    """Get Finnhub auth context for semantic audit."""
    return {
        "auth_type": "api_key",
        "key_present": FINNHUB_ENABLED,
        "key_source": "env:FINNHUB_KEY" if FINNHUB_ENABLED else "none",
        "enabled": FINNHUB_ENABLED,
    }


def _fetch_finnhub(endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Make a request to Finnhub API.

    Args:
        endpoint: API endpoint (e.g., "/quote")
        params: Query parameters

    Returns:
        API response as dict
    """
    if not FINNHUB_ENABLED:
        return {"error": "FINNHUB_KEY not set", "status": "DISABLED"}

    try:
        import httpx

        url = f"{FINNHUB_BASE_URL}{endpoint}"
        request_params = {"token": FINNHUB_KEY}
        if params:
            request_params.update(params)

        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=request_params)
            response.raise_for_status()
            return response.json()

    except Exception as e:
        logger.warning("Finnhub API error for %s: %s", endpoint, e)
        return {"error": str(e), "status": "ERROR"}


def get_market_quote(symbol: str = "SPY") -> Dict[str, Any]:
    """
    Get real-time quote for a symbol.

    Default to SPY (S&P 500 ETF) as market proxy.

    Returns:
        Dict with current price, change, percent change
    """
    cache_key = f"quote_{symbol}"
    now = time.time()

    if cache_key in _finnhub_cache and (now - _finnhub_cache_time.get(cache_key, 0)) < FINNHUB_CACHE_TTL:
        _mark_finnhub_used()
        return {**_finnhub_cache[cache_key], "from_cache": True}

    data = _fetch_finnhub("/quote", {"symbol": symbol})

    if "error" in data:
        return {
            "symbol": symbol,
            "status": data.get("status", "ERROR"),
            "error": data.get("error"),
            "current_price": None,
            "change_percent": None
        }

    # Finnhub quote response: c=current, d=change, dp=percent change, h=high, l=low, o=open
    current = data.get("c", 0)
    change = data.get("d", 0)
    change_pct = data.get("dp", 0)

    result = {
        "symbol": symbol,
        "status": "SUCCESS",
        "current_price": current,
        "change": change,
        "change_percent": change_pct,
        "high": data.get("h"),
        "low": data.get("l"),
        "open": data.get("o"),
        "previous_close": data.get("pc"),
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "from_cache": False
    }

    _finnhub_cache[cache_key] = result
    _finnhub_cache_time[cache_key] = now

    _mark_finnhub_used()
    logger.info("Finnhub %s: $%.2f (%.2f%%)", symbol, current, change_pct)
    return result


def get_market_sentiment() -> Dict[str, Any]:
    """
    Get market sentiment based on SPY performance.

    Market performance affects betting behavior:
    - Big down day = fear/stress = emotional betting
    - Big up day = optimism = recreational bettors active
    - Flat = normal conditions

    Returns:
        Dict with sentiment score, market state, betting interpretation
    """
    quote = get_market_quote("SPY")

    if quote.get("status") != "SUCCESS":
        return {
            "sentiment_score": 0.5,
            "status": quote.get("status", "ERROR"),
            "market_state": "UNKNOWN",
            "triggered": False,
            "reason": quote.get("error", "Market data unavailable")
        }

    change_pct = quote.get("change_percent", 0)

    # Interpret market move
    if change_pct <= -2.5:
        score = 0.9
        state = "CRASH"
        reason = f"Market down {change_pct:.1f}% - extreme fear, emotional betting likely"
        triggered = True
    elif change_pct <= -1.5:
        score = 0.75
        state = "SELLOFF"
        reason = f"Market down {change_pct:.1f}% - elevated fear, contrarian value"
        triggered = True
    elif change_pct <= -0.5:
        score = 0.6
        state = "RED"
        reason = f"Market slightly down ({change_pct:.1f}%)"
        triggered = False
    elif change_pct < 0.5:
        score = 0.5
        state = "FLAT"
        reason = f"Market flat ({change_pct:+.1f}%) - normal conditions"
        triggered = False
    elif change_pct < 1.5:
        score = 0.55
        state = "GREEN"
        reason = f"Market up ({change_pct:+.1f}%) - optimistic mood"
        triggered = False
    elif change_pct < 2.5:
        score = 0.65
        state = "RALLY"
        reason = f"Market rally ({change_pct:+.1f}%) - recreational bettors active"
        triggered = True
    else:
        score = 0.75
        state = "EUPHORIA"
        reason = f"Market surging ({change_pct:+.1f}%) - high optimism, fade public"
        triggered = True

    return {
        "sentiment_score": score,
        "status": "SUCCESS",
        "market_state": state,
        "change_percent": change_pct,
        "triggered": triggered,
        "reason": reason,
        "betting_signal": "CONTRARIAN" if triggered else "NEUTRAL",
        "source": "finnhub_spy",
        "quote": quote
    }


def get_market_news_sentiment(category: str = "general") -> Dict[str, Any]:
    """
    Get market news for sentiment analysis.

    Categories: general, forex, crypto, merger

    Returns:
        Dict with recent headlines and sentiment indicators
    """
    cache_key = f"news_{category}"
    now = time.time()

    if cache_key in _finnhub_cache and (now - _finnhub_cache_time.get(cache_key, 0)) < FINNHUB_CACHE_TTL:
        _mark_finnhub_used()
        return {**_finnhub_cache[cache_key], "from_cache": True}

    data = _fetch_finnhub("/news", {"category": category})

    if isinstance(data, dict) and "error" in data:
        return {
            "status": data.get("status", "ERROR"),
            "error": data.get("error"),
            "headlines": [],
            "news_count": 0
        }

    # data is a list of news items
    if not isinstance(data, list):
        return {
            "status": "ERROR",
            "error": "Unexpected response format",
            "headlines": [],
            "news_count": 0
        }

    # Extract headlines (last 10)
    headlines = []
    for item in data[:10]:
        headlines.append({
            "headline": item.get("headline", ""),
            "source": item.get("source", ""),
            "datetime": item.get("datetime", 0),
            "url": item.get("url", "")
        })

    result = {
        "status": "SUCCESS",
        "category": category,
        "news_count": len(data),
        "headlines": headlines,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "from_cache": False
    }

    _finnhub_cache[cache_key] = result
    _finnhub_cache_time[cache_key] = now

    _mark_finnhub_used()
    logger.info("Finnhub news: %d items in %s", len(data), category)
    return result


def get_market_betting_signal() -> Dict[str, Any]:
    """
    Get combined market signal for betting.

    Aggregates market performance into an esoteric signal.

    Returns:
        Dict with score, market state, and betting recommendation
    """
    sentiment = get_market_sentiment()

    score = sentiment.get("sentiment_score", 0.5)
    triggered = sentiment.get("triggered", False)
    market_state = sentiment.get("market_state", "UNKNOWN")

    # Build recommendation
    if market_state in ["CRASH", "SELLOFF"]:
        recommendation = "Market fear - public betting emotionally, look for contrarian value"
    elif market_state in ["RALLY", "EUPHORIA"]:
        recommendation = "Market optimism - recreational bettors active, consider fading public"
    else:
        recommendation = "Normal market conditions"

    return {
        "score": round(score, 3),
        "triggered": triggered,
        "market_state": market_state,
        "recommendation": recommendation,
        "components": {
            "market_sentiment": sentiment
        },
        "status": sentiment.get("status", "ERROR"),
        "source": "finnhub_market"
    }


# Export
__all__ = [
    "FINNHUB_ENABLED",
    "get_finnhub_auth_context",
    "get_market_quote",
    "get_market_sentiment",
    "get_market_news_sentiment",
    "get_market_betting_signal",
]
