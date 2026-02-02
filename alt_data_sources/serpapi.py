"""
SerpAPI Client - Google Search Trends for Noosphere Velocity

GLITCH Protocol integration for real search trend data.
Used for Noosphere Velocity signal (collective consciousness momentum).

API: https://serpapi.com/
Cost: Already configured in Railway (SERPAPI_KEY)
Rate limit: Depends on plan (usually 100-5000 searches/month)
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("serpapi")

# Configuration
SERPAPI_KEY = os.getenv("SERPAPI_KEY") or os.getenv("SERP_API_KEY")
SERPAPI_ENABLED = bool(SERPAPI_KEY)

# Cache settings (search trends don't change rapidly)
_trend_cache: Dict[str, Any] = {}
_cache_time: Dict[str, float] = {}
CACHE_TTL = 30 * 60  # 30 minutes

# SerpAPI endpoints
SERPAPI_BASE = "https://serpapi.com/search"


def get_search_trend(query: str, location: str = "United States") -> Dict[str, Any]:
    """
    Get Google search trend data for a query.

    Args:
        query: Search query (e.g., "Lakers vs Celtics", "LeBron James")
        location: Location for search (default: United States)

    Returns:
        Dict with trend_score, result_count, news_count, interest_level
    """
    if not SERPAPI_ENABLED:
        return {
            "trend_score": 0.5,
            "source": "disabled",
            "reason": "SERPAPI_NOT_CONFIGURED"
        }

    # Check cache
    cache_key = f"{query}|{location}"
    now = time.time()
    if cache_key in _trend_cache and (now - _cache_time.get(cache_key, 0)) < CACHE_TTL:
        return {**_trend_cache[cache_key], "source": "cache"}

    try:
        import httpx

        params = {
            "engine": "google",
            "q": query,
            "location": location,
            "api_key": SERPAPI_KEY,
            "num": 10,  # Only need count, not full results
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.get(SERPAPI_BASE, params=params)
            response.raise_for_status()
            data = response.json()

        # Extract trend signals
        search_info = data.get("search_information", {})
        total_results = search_info.get("total_results", 0)

        # Count news results
        news_results = data.get("news_results", [])
        news_count = len(news_results)

        # Organic results for recency check
        organic = data.get("organic_results", [])
        recent_count = 0
        for result in organic[:5]:
            # Check if result mentions recent time (today, hours ago, etc.)
            snippet = result.get("snippet", "").lower()
            if any(term in snippet for term in ["today", "hour", "minute", "just", "breaking"]):
                recent_count += 1

        # Calculate trend score (0-1)
        # High results + news + recency = high trend
        if total_results > 1000000000:  # 1B+ results = very popular
            base_score = 0.9
        elif total_results > 100000000:  # 100M+ results = popular
            base_score = 0.7
        elif total_results > 10000000:  # 10M+ results = moderate
            base_score = 0.5
        else:
            base_score = 0.3

        # Boost for news presence
        news_boost = min(0.1, news_count * 0.02)

        # Boost for recent content
        recency_boost = min(0.1, recent_count * 0.03)

        trend_score = min(1.0, base_score + news_boost + recency_boost)

        result = {
            "trend_score": round(trend_score, 3),
            "total_results": total_results,
            "news_count": news_count,
            "recent_mentions": recent_count,
            "interest_level": "HIGH" if trend_score >= 0.7 else "MODERATE" if trend_score >= 0.5 else "LOW",
            "source": "serpapi_live",
            "query": query,
            "fetched_at": datetime.utcnow().isoformat()
        }

        # Update cache
        _trend_cache[cache_key] = result
        _cache_time[cache_key] = now

        logger.info("SerpAPI trend: '%s' = %.2f (%s)", query, trend_score, result["interest_level"])
        return result

    except Exception as e:
        logger.warning("SerpAPI error for '%s': %s", query, e)
        return {
            "trend_score": 0.5,
            "source": "fallback",
            "error": str(e)
        }


def get_team_buzz(team1: str, team2: str) -> Dict[str, Any]:
    """
    Get relative buzz/interest between two teams.

    Used for Noosphere Velocity to determine which team has momentum.

    Args:
        team1: First team name
        team2: Second team name

    Returns:
        Dict with team1_score, team2_score, velocity (positive = team1 momentum)
    """
    if not SERPAPI_ENABLED:
        return {
            "velocity": 0.0,
            "direction": "NEUTRAL",
            "source": "disabled"
        }

    # Get trends for both teams
    trend1 = get_search_trend(f"{team1} game today")
    trend2 = get_search_trend(f"{team2} game today")

    score1 = trend1.get("trend_score", 0.5)
    score2 = trend2.get("trend_score", 0.5)

    # Calculate velocity (-1 to +1, positive = team1 has more buzz)
    if score1 + score2 > 0:
        velocity = (score1 - score2) / max(score1, score2)
    else:
        velocity = 0.0

    # Determine direction
    if velocity > 0.2:
        direction = f"BULLISH_{team1.upper()}"
    elif velocity < -0.2:
        direction = f"BULLISH_{team2.upper()}"
    else:
        direction = "NEUTRAL"

    return {
        "team1": team1,
        "team2": team2,
        "team1_score": score1,
        "team2_score": score2,
        "velocity": round(velocity, 3),
        "direction": direction,
        "source": "serpapi" if SERPAPI_ENABLED else "fallback"
    }


def get_player_buzz(player_name: str) -> Dict[str, Any]:
    """
    Get buzz/interest level for a specific player.

    Used for prop betting - high buzz may indicate public overvaluation.

    Args:
        player_name: Player name

    Returns:
        Dict with buzz_score, interest_level, contrarian_signal
    """
    if not SERPAPI_ENABLED:
        return {
            "buzz_score": 0.5,
            "interest_level": "MODERATE",
            "contrarian_signal": False,
            "source": "disabled"
        }

    trend = get_search_trend(f"{player_name} props today")
    buzz_score = trend.get("trend_score", 0.5)

    # High buzz = potential contrarian opportunity (public overvaluation)
    contrarian_signal = buzz_score >= 0.75

    return {
        "player": player_name,
        "buzz_score": buzz_score,
        "interest_level": trend.get("interest_level", "MODERATE"),
        "contrarian_signal": contrarian_signal,
        "contrarian_reason": "High public interest - line may be inflated" if contrarian_signal else None,
        "source": trend.get("source", "unknown")
    }


def get_noosphere_data(teams: List[str] = None, player: str = None) -> Dict[str, Any]:
    """
    Get Noosphere Velocity data from real search trends.

    Replaces simulation in hive_mind.py with real SerpAPI data.

    Args:
        teams: List of team names [home, away]
        player: Optional player name (for props)

    Returns:
        Dict with velocity, direction, confidence for hive_mind integration
    """
    if not SERPAPI_ENABLED:
        return {
            "velocity": 0.0,
            "direction": "NEUTRAL",
            "confidence": 0.0,
            "source": "disabled",
            "reason": "SERPAPI_NOT_CONFIGURED"
        }

    velocity = 0.0
    confidence = 0.0
    signals = []

    # Team buzz if teams provided
    if teams and len(teams) >= 2:
        team_buzz = get_team_buzz(teams[0], teams[1])
        velocity = team_buzz.get("velocity", 0.0)
        signals.append(("team_buzz", team_buzz.get("direction", "NEUTRAL")))
        confidence += 0.5

    # Player buzz if player provided
    if player:
        player_buzz = get_player_buzz(player)
        player_score = (player_buzz.get("buzz_score", 0.5) - 0.5) * 2  # Normalize to -1 to 1
        velocity = (velocity + player_score) / 2 if signals else player_score
        if player_buzz.get("contrarian_signal"):
            signals.append(("player_contrarian", player))
        confidence += 0.3

    # Determine final direction
    if velocity > 0.3:
        direction = "STRONG_POSITIVE"
    elif velocity > 0.1:
        direction = "POSITIVE"
    elif velocity < -0.3:
        direction = "STRONG_NEGATIVE"
    elif velocity < -0.1:
        direction = "NEGATIVE"
    else:
        direction = "NEUTRAL"

    return {
        "velocity": round(velocity, 3),
        "direction": direction,
        "confidence": round(min(1.0, confidence), 2),
        "signals_used": [s[0] for s in signals],
        "source": "serpapi_live",
        "triggered": abs(velocity) > 0.2
    }


# Export for integration
__all__ = [
    "get_search_trend",
    "get_team_buzz",
    "get_player_buzz",
    "get_noosphere_data",
    "SERPAPI_ENABLED",
]
