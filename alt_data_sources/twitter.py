"""
Twitter/X API Client (Direct)

Provides direct Twitter search for Engine 4 (Jarvis) gematria intelligence.
Replaces SerpAPI-based Twitter search to avoid quota burn.

API: https://developer.twitter.com/en/docs/twitter-api
Cost: Free tier = 500K tweets/month read, 10K tweets/month search
Rate limit: 450 requests/15 min (user auth), 180/15 min (app auth)

Note: Uses Twitter API v2 with Bearer Token authentication.
"""

import os
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

logger = logging.getLogger("twitter")

# Config
TWITTER_BEARER = os.getenv("TWITTER_BEARER") or os.getenv("TWITTER_BEARER_TOKEN", "")
TWITTER_BASE_URL = "https://api.twitter.com/2"
TWITTER_ENABLED = bool(TWITTER_BEARER)

# Cache
_twitter_cache: Dict[str, Any] = {}
_twitter_cache_time: Dict[str, float] = {}
TWITTER_CACHE_TTL = 30 * 60  # 30 minutes (social sentiment changes slowly)


def _mark_twitter_used() -> None:
    """Mark Twitter integration as used."""
    try:
        from integration_registry import mark_integration_used
        mark_integration_used("twitter")
    except Exception as e:
        logger.debug("twitter mark_integration_used failed: %s", str(e))


def get_twitter_auth_context() -> Dict[str, Any]:
    """Get Twitter auth context for semantic audit."""
    return {
        "auth_type": "bearer_token",
        "key_present": TWITTER_ENABLED,
        "key_source": "env:TWITTER_BEARER" if TWITTER_ENABLED else "none",
        "enabled": TWITTER_ENABLED,
    }


def _fetch_twitter(endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Make a request to Twitter API v2.

    Args:
        endpoint: API endpoint (e.g., "/tweets/search/recent")
        params: Query parameters

    Returns:
        API response as dict
    """
    if not TWITTER_ENABLED:
        return {"error": "TWITTER_BEARER not set", "status": "DISABLED"}

    try:
        import httpx

        url = f"{TWITTER_BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {TWITTER_BEARER}",
            "Content-Type": "application/json"
        }

        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("Twitter rate limit hit")
            return {"error": "Rate limit exceeded", "status": "RATE_LIMITED"}
        logger.warning("Twitter API HTTP error: %s", e)
        return {"error": str(e), "status": "ERROR"}
    except Exception as e:
        logger.warning("Twitter API error: %s", e)
        return {"error": str(e), "status": "ERROR"}


def search_tweets(
    query: str,
    max_results: int = 20,
    include_metrics: bool = True
) -> Dict[str, Any]:
    """
    Search recent tweets (last 7 days).

    Args:
        query: Search query (supports Twitter search operators)
        max_results: Number of results (10-100)
        include_metrics: Include engagement metrics

    Returns:
        Dict with tweets, metadata, and search info
    """
    # Cache key based on query
    cache_key = f"search_{hash(query)}_{max_results}"
    now = time.time()

    if cache_key in _twitter_cache and (now - _twitter_cache_time.get(cache_key, 0)) < TWITTER_CACHE_TTL:
        _mark_twitter_used()
        return {**_twitter_cache[cache_key], "from_cache": True}

    # Build params
    params = {
        "query": query,
        "max_results": min(max(10, max_results), 100),  # API limits: 10-100
        "tweet.fields": "created_at,author_id,text,public_metrics" if include_metrics else "created_at,author_id,text"
    }

    data = _fetch_twitter("/tweets/search/recent", params)

    if "error" in data:
        return {
            "query": query,
            "status": data.get("status", "ERROR"),
            "error": data.get("error"),
            "tweets": [],
            "count": 0
        }

    tweets = data.get("data", [])
    meta = data.get("meta", {})

    # Process tweets
    processed_tweets = []
    for tweet in tweets:
        processed = {
            "id": tweet.get("id"),
            "text": tweet.get("text", ""),
            "created_at": tweet.get("created_at"),
            "author_id": tweet.get("author_id"),
        }
        if include_metrics and "public_metrics" in tweet:
            metrics = tweet["public_metrics"]
            processed["metrics"] = {
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "replies": metrics.get("reply_count", 0),
                "quotes": metrics.get("quote_count", 0),
            }
            processed["engagement"] = sum(processed["metrics"].values())
        processed_tweets.append(processed)

    result = {
        "query": query,
        "status": "SUCCESS",
        "tweets": processed_tweets,
        "count": len(processed_tweets),
        "result_count": meta.get("result_count", 0),
        "newest_id": meta.get("newest_id"),
        "oldest_id": meta.get("oldest_id"),
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "from_cache": False
    }

    _twitter_cache[cache_key] = result
    _twitter_cache_time[cache_key] = now

    _mark_twitter_used()
    logger.info("Twitter search '%s': %d tweets", query[:30], len(processed_tweets))
    return result


def search_sports_betting_tweets(
    team: str = None,
    player: str = None,
    sport: str = None,
    hashtags: List[str] = None
) -> Dict[str, Any]:
    """
    Search for sports betting related tweets.

    Args:
        team: Team name (e.g., "Lakers")
        player: Player name (e.g., "LeBron")
        sport: Sport (e.g., "NBA")
        hashtags: Additional hashtags to include

    Returns:
        Dict with relevant tweets and sentiment signals
    """
    # Build query
    query_parts = []

    if team:
        query_parts.append(f'"{team}"')
    if player:
        query_parts.append(f'"{player}"')
    if sport:
        query_parts.append(f"#{sport}")

    # Add betting-related terms
    query_parts.append("(bet OR betting OR spread OR odds OR pick OR lock)")

    if hashtags:
        for tag in hashtags:
            query_parts.append(f"#{tag.lstrip('#')}")

    # Exclude retweets for cleaner signal
    query_parts.append("-is:retweet")

    query = " ".join(query_parts)

    return search_tweets(query, max_results=30, include_metrics=True)


def get_gematria_twitter_intel(
    query: str,
    num_results: int = 20
) -> Dict[str, Any]:
    """
    Search Twitter for gematria/numerology related content.

    This is a drop-in replacement for _search_twitter_via_serp in gematria_twitter_intel.py

    Args:
        query: Gematria search query
        num_results: Number of results

    Returns:
        Dict with tweets formatted for gematria analysis
    """
    # Add numerology/gematria context to query
    enhanced_query = f"{query} (gematria OR numerology OR 33 OR 322 OR 666 OR sacred OR ritual)"

    result = search_tweets(enhanced_query, max_results=num_results)

    if result.get("status") != "SUCCESS":
        return {
            "status": result.get("status", "ERROR"),
            "error": result.get("error"),
            "intel": [],
            "total_engagement": 0
        }

    # Format for gematria analysis
    intel = []
    total_engagement = 0

    for tweet in result.get("tweets", []):
        engagement = tweet.get("engagement", 0)
        total_engagement += engagement

        intel.append({
            "text": tweet.get("text", ""),
            "engagement": engagement,
            "created_at": tweet.get("created_at"),
            "metrics": tweet.get("metrics", {}),
            "source": "twitter_direct"
        })

    # Sort by engagement
    intel.sort(key=lambda x: x.get("engagement", 0), reverse=True)

    return {
        "status": "SUCCESS",
        "query": query,
        "intel": intel,
        "total_engagement": total_engagement,
        "tweet_count": len(intel),
        "fetched_at": result.get("fetched_at"),
        "source": "twitter_api_v2"
    }


def get_public_sentiment(topic: str) -> Dict[str, Any]:
    """
    Get public sentiment on a topic from Twitter.

    Args:
        topic: Topic to analyze (team, player, game, etc.)

    Returns:
        Dict with sentiment score and supporting data
    """
    result = search_tweets(
        query=f'"{topic}" -is:retweet lang:en',
        max_results=50,
        include_metrics=True
    )

    if result.get("status") != "SUCCESS":
        return {
            "sentiment_score": 0.5,
            "status": result.get("status", "ERROR"),
            "error": result.get("error"),
            "volume": 0
        }

    tweets = result.get("tweets", [])
    volume = len(tweets)

    if volume == 0:
        return {
            "sentiment_score": 0.5,
            "status": "NO_DATA",
            "volume": 0,
            "reason": "No tweets found for topic"
        }

    # Calculate engagement-weighted sentiment proxy
    # (More engagement = stronger signal, positive/negative determined by context)
    total_engagement = sum(t.get("engagement", 0) for t in tweets)
    avg_engagement = total_engagement / volume if volume else 0

    # High volume + high engagement = strong public interest
    if volume >= 40 and avg_engagement >= 50:
        score = 0.8
        signal = "HIGH_BUZZ"
    elif volume >= 25 or avg_engagement >= 25:
        score = 0.6
        signal = "MODERATE_BUZZ"
    elif volume >= 10:
        score = 0.5
        signal = "LOW_BUZZ"
    else:
        score = 0.4
        signal = "MINIMAL"

    return {
        "sentiment_score": score,
        "status": "SUCCESS",
        "volume": volume,
        "total_engagement": total_engagement,
        "avg_engagement": round(avg_engagement, 1),
        "signal": signal,
        "topic": topic,
        "source": "twitter_api_v2"
    }


# Export
__all__ = [
    "TWITTER_ENABLED",
    "get_twitter_auth_context",
    "search_tweets",
    "search_sports_betting_tweets",
    "get_gematria_twitter_intel",
    "get_public_sentiment",
]
