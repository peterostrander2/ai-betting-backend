"""
SerpAPI News Integration - v10.66
=================================
Fetches trending news and injury stories via Google Search.

Key Use Cases:
1. Aggregate injury news from multiple sources
2. Detect trending player names (breakout games)
3. Monitor "upset" buzz before games
4. Get news that Twitter might miss

API Docs: https://serpapi.com/search-api
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
import httpx
import re

logger = logging.getLogger(__name__)

# Configuration
SERPAPI_KEY = os.getenv("SERPAPI_KEY", os.getenv("SERP_API_KEY", ""))
SERPAPI_BASE = "https://serpapi.com/search"

# Cache for API responses (20 min TTL)
_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 1200


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


def is_serpapi_configured() -> bool:
    """Check if SerpAPI is configured."""
    return bool(SERPAPI_KEY)


async def get_injury_news(
    sport: str,
    teams: List[str] = None,
    hours_back: int = 24
) -> Dict[str, Any]:
    """
    Search Google News for injury-related stories.

    Returns:
        {
            "available": bool,
            "injuries": [
                {
                    "player_name": str,
                    "team": str,
                    "status": str,
                    "headline": str,
                    "source": str,
                    "url": str,
                    "snippet": str,
                    "confidence": float
                }
            ],
            "news_count": int,
            "sources": [str]
        }
    """
    default_response = {
        "available": False,
        "injuries": [],
        "news_count": 0,
        "sources": [],
        "source": "serpapi"
    }

    if not SERPAPI_KEY:
        logger.debug("SERPAPI_KEY not configured")
        return default_response

    cache_key = f"serpapi_injuries:{sport}:{'-'.join(teams or [])}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        # Build search query
        sport_league = {
            "nba": "NBA",
            "nfl": "NFL",
            "mlb": "MLB",
            "nhl": "NHL"
        }.get(sport.lower(), sport.upper())

        team_filter = ""
        if teams:
            team_filter = f" ({' OR '.join(teams)})"

        query = f"{sport_league} injury{team_filter} out ruled questionable"

        params = {
            "engine": "google_news",
            "q": query,
            "api_key": SERPAPI_KEY,
            "gl": "us",
            "hl": "en",
            "tbm": "nws",  # News search
            "tbs": "qdr:d"  # Last 24 hours
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(SERPAPI_BASE, params=params)

            if resp.status_code == 401:
                logger.warning("SerpAPI auth failed")
                return default_response

            if resp.status_code != 200:
                logger.warning(f"SerpAPI error: {resp.status_code}")
                return default_response

            data = resp.json()

            injuries = []
            sources = set()
            news_results = data.get("news_results", [])

            for article in news_results[:20]:
                title = article.get("title", "")
                snippet = article.get("snippet", "")
                source = article.get("source", {}).get("name", "")
                link = article.get("link", "")

                sources.add(source)

                # Parse injury info from headline/snippet
                injury_info = _parse_injury_from_news(title, snippet, sport)

                if injury_info:
                    # Calculate confidence based on source reliability
                    confidence = 0.6
                    reliable_sources = ["ESPN", "Yahoo Sports", "CBS Sports", "Bleacher Report",
                                       "The Athletic", "NBC Sports", "Fox Sports"]
                    if any(src.lower() in source.lower() for src in reliable_sources):
                        confidence = 0.85

                    injuries.append({
                        "player_name": injury_info.get("player", ""),
                        "team": injury_info.get("team", ""),
                        "status": injury_info.get("status", "QUESTIONABLE"),
                        "headline": title[:150],
                        "source": source,
                        "url": link,
                        "snippet": snippet[:200],
                        "confidence": confidence
                    })

            result = {
                "available": True,
                "injuries": injuries,
                "news_count": len(news_results),
                "sources": list(sources),
                "source": "serpapi"
            }

            _set_cached(cache_key, result)
            logger.info(f"SerpAPI: Found {len(injuries)} injury stories from {len(news_results)} articles")
            return result

    except Exception as e:
        logger.warning(f"SerpAPI injury news failed: {e}")
        return default_response


def _parse_injury_from_news(title: str, snippet: str, sport: str) -> Optional[Dict[str, str]]:
    """Parse player name and injury status from news article."""
    text = f"{title} {snippet}".upper()

    # Check for injury indicators
    status = None
    if "RULED OUT" in text or "WILL NOT PLAY" in text or "SIDELINED" in text:
        status = "OUT"
    elif "DOUBTFUL" in text:
        status = "DOUBTFUL"
    elif "QUESTIONABLE" in text or "GAME-TIME" in text or "GTD" in text:
        status = "GTD"
    elif "DAY-TO-DAY" in text or "EXPECTED TO PLAY" in text:
        status = "PROBABLE"

    if not status:
        return None

    # Try to extract player name
    # Look for patterns like "Player Name ruled out" or "Player Name injury"
    name_pattern = r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\s+(?:ruled|is|has|will|injury|out|questionable|doubtful))"
    match = re.search(name_pattern, title)

    player_name = ""
    if match:
        player_name = match.group(1)

    if player_name:
        return {
            "player": player_name,
            "team": "",
            "status": status
        }

    return None


async def get_trending_news(
    sport: str,
    topic: str = "betting"
) -> Dict[str, Any]:
    """
    Get trending sports betting news.

    Returns:
        {
            "available": bool,
            "trending": [
                {"title": str, "source": str, "trend_score": float}
            ],
            "hot_topics": [str],
            "upset_buzz": float  # 0-1 scale of upset mentions
        }
    """
    default_response = {
        "available": False,
        "trending": [],
        "hot_topics": [],
        "upset_buzz": 0.0,
        "source": "serpapi"
    }

    if not SERPAPI_KEY:
        return default_response

    cache_key = f"serpapi_trending:{sport}:{topic}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        sport_league = {
            "nba": "NBA",
            "nfl": "NFL",
            "mlb": "MLB",
            "nhl": "NHL"
        }.get(sport.lower(), sport.upper())

        query = f"{sport_league} {topic} today"

        params = {
            "engine": "google_news",
            "q": query,
            "api_key": SERPAPI_KEY,
            "gl": "us",
            "hl": "en",
            "tbm": "nws",
            "tbs": "qdr:d"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(SERPAPI_BASE, params=params)

            if resp.status_code != 200:
                return default_response

            data = resp.json()

            trending = []
            hot_topics = set()
            upset_mentions = 0
            total_articles = 0

            for article in data.get("news_results", [])[:15]:
                title = article.get("title", "")
                source = article.get("source", {}).get("name", "")

                # Extract hot topics from titles
                words = title.split()
                for word in words:
                    if word.isupper() and len(word) > 2:
                        hot_topics.add(word)

                # Count upset mentions
                if any(w in title.lower() for w in ["upset", "underdog", "shocking", "stunner"]):
                    upset_mentions += 1
                total_articles += 1

                trending.append({
                    "title": title[:100],
                    "source": source,
                    "trend_score": 0.5  # Would calculate from engagement
                })

            result = {
                "available": True,
                "trending": trending[:10],
                "hot_topics": list(hot_topics)[:10],
                "upset_buzz": upset_mentions / max(1, total_articles),
                "source": "serpapi"
            }

            _set_cached(cache_key, result)
            return result

    except Exception as e:
        logger.warning(f"SerpAPI trending news failed: {e}")
        return default_response


async def get_player_buzz(player_name: str, sport: str) -> Dict[str, Any]:
    """
    Check news buzz level for a specific player.

    Returns:
        {
            "available": bool,
            "buzz_level": float,  # 0-1, higher = more news
            "sentiment": float,  # -1 to 1
            "recent_headlines": [str],
            "injury_mentioned": bool
        }
    """
    default_response = {
        "available": False,
        "buzz_level": 0.0,
        "sentiment": 0.0,
        "recent_headlines": [],
        "injury_mentioned": False,
        "source": "serpapi"
    }

    if not SERPAPI_KEY:
        return default_response

    cache_key = f"serpapi_player:{player_name}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        sport_league = {"nba": "NBA", "nfl": "NFL", "mlb": "MLB", "nhl": "NHL"}.get(sport.lower(), "")

        params = {
            "engine": "google_news",
            "q": f'"{player_name}" {sport_league}',
            "api_key": SERPAPI_KEY,
            "gl": "us",
            "hl": "en",
            "tbm": "nws",
            "tbs": "qdr:d"  # Last 24 hours
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(SERPAPI_BASE, params=params)

            if resp.status_code != 200:
                return default_response

            data = resp.json()
            articles = data.get("news_results", [])

            headlines = [a.get("title", "")[:100] for a in articles[:5]]

            # Calculate buzz level (more articles = higher buzz)
            buzz_level = min(1.0, len(articles) / 10)

            # Check for injury mentions
            injury_mentioned = any(
                word in " ".join(headlines).lower()
                for word in ["injury", "hurt", "out", "questionable", "doubtful"]
            )

            # Simple sentiment
            positive_words = ["breakout", "career", "dominate", "star", "hot", "streak"]
            negative_words = ["struggle", "slump", "concern", "injury", "out"]

            sentiment = 0.0
            all_text = " ".join(headlines).lower()
            for word in positive_words:
                if word in all_text:
                    sentiment += 0.2
            for word in negative_words:
                if word in all_text:
                    sentiment -= 0.2

            result = {
                "available": True,
                "buzz_level": round(buzz_level, 2),
                "sentiment": max(-1, min(1, sentiment)),
                "recent_headlines": headlines,
                "injury_mentioned": injury_mentioned,
                "source": "serpapi"
            }

            _set_cached(cache_key, result)
            return result

    except Exception as e:
        logger.warning(f"SerpAPI player buzz failed: {e}")
        return default_response


def get_serpapi_status() -> Dict[str, Any]:
    """Get SerpAPI configuration status."""
    return {
        "configured": is_serpapi_configured(),
        "api_key_set": bool(SERPAPI_KEY),
        "features": ["injury_news", "trending_news", "player_buzz"],
        "cache_ttl": CACHE_TTL_SECONDS
    }
