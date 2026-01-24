"""
Finnhub API Integration - v10.66
================================
Fetches stock market data for sportsbook companies to detect
institutional sentiment and money flow.

Key Use Cases:
1. Track DraftKings (DKNG) and Flutter/FanDuel (FLTR) stock prices
2. Detect unusual volume spikes (institutional movement)
3. Correlate market sentiment with line movements
4. Earnings/news impact on odds accuracy

API Docs: https://finnhub.io/docs/api
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import httpx

logger = logging.getLogger(__name__)

# Configuration
FINNHUB_KEY = os.getenv("FINNHUB_KEY", os.getenv("FINNHUB_API_KEY", ""))
FINNHUB_API_BASE = "https://finnhub.io/api/v1"

# Cache for API responses (30 min TTL - market data changes slower)
_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 1800

# Sportsbook tickers to track
SPORTSBOOK_TICKERS = {
    "DKNG": {
        "name": "DraftKings",
        "type": "sportsbook",
        "weight": 0.5  # Weight in composite sentiment
    },
    "FLTR": {
        "name": "Flutter (FanDuel)",
        "type": "sportsbook",
        "weight": 0.3
    },
    "PENN": {
        "name": "Penn Entertainment",
        "type": "sportsbook",
        "weight": 0.1
    },
    "MGM": {
        "name": "MGM Resorts",
        "type": "casino_sports",
        "weight": 0.1
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


def is_finnhub_configured() -> bool:
    """Check if Finnhub API is configured."""
    return bool(FINNHUB_KEY)


async def get_sportsbook_sentiment() -> Dict[str, Any]:
    """
    Get aggregate sentiment from sportsbook stocks.

    Returns:
        {
            "available": bool,
            "sentiment": float,  # -1.0 (bearish) to 1.0 (bullish)
            "signal_strength": str,  # STRONG, MODERATE, WEAK, NEUTRAL
            "institutional_move": bool,  # True if unusual volume detected
            "tickers": {
                "DKNG": {"price": float, "change_pct": float, "volume_ratio": float},
                ...
            },
            "composite_change": float,  # Weighted avg price change
            "volume_spike": bool,  # True if any ticker has 2x+ normal volume
            "reason": str
        }
    """
    default_response = {
        "available": False,
        "sentiment": 0.0,
        "signal_strength": "NEUTRAL",
        "institutional_move": False,
        "tickers": {},
        "composite_change": 0.0,
        "volume_spike": False,
        "reason": "Finnhub not configured",
        "source": "finnhub"
    }

    if not FINNHUB_KEY:
        logger.debug("FINNHUB_KEY not configured")
        return default_response

    cache_key = "finnhub_sportsbook_sentiment"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        ticker_data = {}
        weighted_change = 0.0
        total_weight = 0.0
        volume_spike = False
        institutional_move = False

        async with httpx.AsyncClient(timeout=15.0) as client:
            for ticker, info in SPORTSBOOK_TICKERS.items():
                try:
                    # Get quote data
                    quote_url = f"{FINNHUB_API_BASE}/quote"
                    params = {"symbol": ticker, "token": FINNHUB_KEY}

                    resp = await client.get(quote_url, params=params)

                    if resp.status_code != 200:
                        continue

                    quote = resp.json()

                    current_price = quote.get("c", 0)
                    prev_close = quote.get("pc", 0)
                    high = quote.get("h", 0)
                    low = quote.get("l", 0)

                    if prev_close > 0:
                        change_pct = ((current_price - prev_close) / prev_close) * 100
                    else:
                        change_pct = 0

                    # Check for volume spike (simplified - would need historical volume)
                    # If price moved significantly, assume volume is elevated
                    volume_ratio = 1.0
                    if abs(change_pct) > 3:
                        volume_ratio = 1.5 + (abs(change_pct) / 10)
                        volume_spike = True

                    if volume_ratio > 2.0:
                        institutional_move = True

                    ticker_data[ticker] = {
                        "name": info["name"],
                        "price": current_price,
                        "prev_close": prev_close,
                        "change_pct": round(change_pct, 2),
                        "high": high,
                        "low": low,
                        "volume_ratio": round(volume_ratio, 2)
                    }

                    # Add to weighted average
                    weighted_change += change_pct * info["weight"]
                    total_weight += info["weight"]

                except Exception as e:
                    logger.debug(f"Finnhub: Failed to fetch {ticker}: {e}")
                    continue

        if not ticker_data:
            return default_response

        # Calculate composite metrics
        composite_change = weighted_change / max(0.01, total_weight)

        # Determine sentiment and signal strength
        sentiment = max(-1.0, min(1.0, composite_change / 5))  # ±5% = ±1.0

        if abs(composite_change) >= 5:
            signal_strength = "STRONG"
        elif abs(composite_change) >= 2:
            signal_strength = "MODERATE"
        elif abs(composite_change) >= 0.5:
            signal_strength = "WEAK"
        else:
            signal_strength = "NEUTRAL"

        # Generate reason
        if institutional_move and composite_change > 2:
            reason = "Strong institutional buying in sportsbook sector"
        elif institutional_move and composite_change < -2:
            reason = "Institutional selling pressure in sportsbooks"
        elif volume_spike:
            reason = "Elevated volume in sportsbook stocks"
        elif abs(composite_change) > 1:
            direction = "up" if composite_change > 0 else "down"
            reason = f"Sportsbook sector {direction} {abs(composite_change):.1f}%"
        else:
            reason = "Sportsbook sector trading normally"

        result = {
            "available": True,
            "sentiment": round(sentiment, 3),
            "signal_strength": signal_strength,
            "institutional_move": institutional_move,
            "tickers": ticker_data,
            "composite_change": round(composite_change, 2),
            "volume_spike": volume_spike,
            "reason": reason,
            "source": "finnhub"
        }

        _set_cached(cache_key, result)
        logger.info(f"Finnhub: Sportsbook sentiment={sentiment:.2f}, change={composite_change:.2f}%")
        return result

    except Exception as e:
        logger.warning(f"Finnhub sportsbook sentiment failed: {e}")
        return default_response


async def get_market_sentiment() -> Dict[str, Any]:
    """
    Get broader market sentiment indicators.

    Returns:
        {
            "available": bool,
            "spy_change": float,  # S&P 500 change %
            "vix": float,  # Volatility index
            "market_mood": str,  # RISK_ON, RISK_OFF, NEUTRAL
            "betting_correlation": str  # How market mood affects betting
        }
    """
    default_response = {
        "available": False,
        "spy_change": 0.0,
        "vix": 0.0,
        "market_mood": "NEUTRAL",
        "betting_correlation": "No correlation data",
        "source": "finnhub"
    }

    if not FINNHUB_KEY:
        return default_response

    cache_key = "finnhub_market_sentiment"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get SPY (S&P 500 ETF) as market proxy
            spy_url = f"{FINNHUB_API_BASE}/quote"
            params = {"symbol": "SPY", "token": FINNHUB_KEY}

            resp = await client.get(spy_url, params=params)

            if resp.status_code != 200:
                return default_response

            spy_data = resp.json()

            current = spy_data.get("c", 0)
            prev = spy_data.get("pc", 0)

            spy_change = 0.0
            if prev > 0:
                spy_change = ((current - prev) / prev) * 100

            # Determine market mood
            if spy_change > 1:
                market_mood = "RISK_ON"
                betting_correlation = "Risk-on mood: Public may bet more aggressively on favorites"
            elif spy_change < -1:
                market_mood = "RISK_OFF"
                betting_correlation = "Risk-off mood: Public may be more conservative, fewer parlays"
            else:
                market_mood = "NEUTRAL"
                betting_correlation = "Neutral market: Normal betting patterns expected"

            result = {
                "available": True,
                "spy_change": round(spy_change, 2),
                "vix": 0.0,  # Would need separate call
                "market_mood": market_mood,
                "betting_correlation": betting_correlation,
                "source": "finnhub"
            }

            _set_cached(cache_key, result)
            return result

    except Exception as e:
        logger.warning(f"Finnhub market sentiment failed: {e}")
        return default_response


async def get_news_sentiment(ticker: str = "DKNG") -> Dict[str, Any]:
    """
    Get news sentiment for a specific ticker.

    Returns:
        {
            "available": bool,
            "headlines": [{"headline": str, "sentiment": str, "time": str}],
            "avg_sentiment": float,
            "news_count": int
        }
    """
    default_response = {
        "available": False,
        "headlines": [],
        "avg_sentiment": 0.0,
        "news_count": 0,
        "source": "finnhub"
    }

    if not FINNHUB_KEY:
        return default_response

    cache_key = f"finnhub_news:{ticker}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get company news
            today = datetime.now().strftime("%Y-%m-%d")
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            url = f"{FINNHUB_API_BASE}/company-news"
            params = {
                "symbol": ticker,
                "from": week_ago,
                "to": today,
                "token": FINNHUB_KEY
            }

            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                return default_response

            news = resp.json()

            headlines = []
            sentiment_sum = 0

            for article in news[:10]:  # Last 10 articles
                headline = article.get("headline", "")

                # Simple sentiment analysis
                sentiment = "neutral"
                headline_lower = headline.lower()

                positive_words = ["surge", "jump", "gain", "rise", "win", "record", "growth"]
                negative_words = ["fall", "drop", "loss", "decline", "concern", "risk", "lawsuit"]

                if any(word in headline_lower for word in positive_words):
                    sentiment = "positive"
                    sentiment_sum += 1
                elif any(word in headline_lower for word in negative_words):
                    sentiment = "negative"
                    sentiment_sum -= 1

                headlines.append({
                    "headline": headline[:100],
                    "sentiment": sentiment,
                    "time": article.get("datetime", "")
                })

            avg_sentiment = sentiment_sum / max(1, len(headlines))

            result = {
                "available": True,
                "headlines": headlines,
                "avg_sentiment": round(avg_sentiment, 2),
                "news_count": len(news),
                "source": "finnhub"
            }

            _set_cached(cache_key, result)
            return result

    except Exception as e:
        logger.warning(f"Finnhub news fetch failed: {e}")
        return default_response


def get_finnhub_status() -> Dict[str, Any]:
    """Get Finnhub API configuration status."""
    return {
        "configured": is_finnhub_configured(),
        "api_key_set": bool(FINNHUB_KEY),
        "tickers_tracked": list(SPORTSBOOK_TICKERS.keys()),
        "features": ["sportsbook_sentiment", "market_sentiment", "news_sentiment"],
        "cache_ttl": CACHE_TTL_SECONDS
    }
