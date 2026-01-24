"""
Twitter/X API Integration - v10.66
==================================
Fetches breaking injury news and sentiment from Twitter/X.

Key Use Cases:
1. Breaking injury alerts (often 15-30 min before official)
2. Beat reporter tweets for each team
3. Player social media activity before games
4. Public sentiment on matchups

API Docs: https://developer.twitter.com/en/docs/twitter-api
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import httpx

logger = logging.getLogger(__name__)

# Configuration
TWITTER_BEARER = os.getenv("TWITTER_BEARER", "")
TWITTER_API_BASE = "https://api.twitter.com/2"

# Cache for API responses (15 min TTL)
_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 900

# Beat reporters by team (curated list of reliable injury sources)
BEAT_REPORTERS = {
    # NBA
    "lakers": ["@mcaboricua", "@LakersReporter", "@RyanWardLA"],
    "celtics": ["@ChrisBHaynes", "@AdamHimmelsbach"],
    "warriors": ["@MontePozor", "@WarriorsWorld"],
    "nets": ["@NetsDaily", "@AlexSchiffer"],
    "heat": ["@IraHeatBeat", "@MiamiHEAT"],
    "bucks": ["@JimOwczarski", "@Matt_& Velazquez"],
    "76ers": ["@PompeyOnSixers", "@KyleNeubeck"],
    "suns": ["@DuaneRankin", "@KellanOlson"],
    # NFL
    "chiefs": ["@TerezPaylor", "@mattderrick"],
    "eagles": ["@JimmyKempski", "@ZachBerman"],
    "49ers": ["@MaioccoNBCS", "@LombardiHimself"],
    "cowboys": ["@toddarcher", "@jonmachota"],
    "bills": ["@SalSports", "@JoeBuscaglia"],
    # MLB
    "yankees": ["@BryanHoch", "@lindseyadler"],
    "dodgers": ["@FabianArdaya", "@McCaboricua"],
    "astros": ["@braboricua", "@Chandler_Rome"],
    # NHL
    "bruins": ["@FlutoShinzawa", "@GlobeKPD"],
    "rangers": ["@VinceZMercogliano", "@MolsNHL"],
    "oilers": ["@DNBsports", "@JasonGregor"],
}

# Injury-related keywords to search for
INJURY_KEYWORDS = [
    "OUT", "DNP", "ruled out", "will not play", "scratched",
    "questionable", "doubtful", "GTD", "game-time decision",
    "injury", "injured", "hurt", "sidelined", "ankle", "knee",
    "concussion", "hamstring", "illness", "rest", "load management"
]


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


def is_twitter_configured() -> bool:
    """Check if Twitter API is configured."""
    return bool(TWITTER_BEARER)


async def get_twitter_injury_alerts(
    sport: str,
    teams: List[str] = None,
    hours_back: int = 4
) -> Dict[str, Any]:
    """
    Fetch breaking injury alerts from Twitter.

    Returns:
        {
            "available": bool,
            "alerts": [
                {
                    "player_name": str,
                    "team": str,
                    "status": str,  # OUT, DOUBTFUL, GTD, etc.
                    "injury": str,
                    "source": "twitter",
                    "tweet_text": str,
                    "tweet_time": str,
                    "confidence": float,  # 0.0-1.0 based on source reliability
                    "reporter": str
                }
            ],
            "search_query": str,
            "tweets_analyzed": int
        }
    """
    default_response = {
        "available": False,
        "alerts": [],
        "search_query": "",
        "tweets_analyzed": 0,
        "source": "twitter"
    }

    if not TWITTER_BEARER:
        logger.debug("TWITTER_BEARER not configured")
        return default_response

    cache_key = f"twitter_injuries:{sport}:{'-'.join(teams or [])}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        # Build search query
        query_parts = []

        # Add injury keywords
        injury_query = " OR ".join([f'"{kw}"' for kw in INJURY_KEYWORDS[:5]])
        query_parts.append(f"({injury_query})")

        # Add sport-specific terms
        sport_terms = {
            "nba": "NBA basketball",
            "nfl": "NFL football",
            "mlb": "MLB baseball",
            "nhl": "NHL hockey"
        }
        query_parts.append(sport_terms.get(sport.lower(), sport))

        # Add team filters if provided
        if teams:
            team_query = " OR ".join(teams)
            query_parts.append(f"({team_query})")

        query = " ".join(query_parts)

        # Calculate time range
        start_time = (datetime.utcnow() - timedelta(hours=hours_back)).isoformat() + "Z"

        # Twitter API v2 search
        url = f"{TWITTER_API_BASE}/tweets/search/recent"
        params = {
            "query": query,
            "max_results": 100,
            "start_time": start_time,
            "tweet.fields": "created_at,author_id,public_metrics",
            "expansions": "author_id",
            "user.fields": "username,verified"
        }

        headers = {
            "Authorization": f"Bearer {TWITTER_BEARER}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params, headers=headers)

            if resp.status_code == 401:
                logger.warning("Twitter API auth failed")
                return default_response

            if resp.status_code == 429:
                logger.warning("Twitter API rate limited")
                return default_response

            if resp.status_code != 200:
                logger.warning(f"Twitter API error: {resp.status_code}")
                return default_response

            data = resp.json()

            # Parse tweets for injury alerts
            alerts = []
            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

            for tweet in tweets:
                author = users.get(tweet.get("author_id"), {})
                username = author.get("username", "")
                is_verified = author.get("verified", False)

                # Parse injury info from tweet text
                text = tweet.get("text", "")
                injury_info = _parse_injury_from_tweet(text, sport)

                if injury_info:
                    # Calculate confidence based on source
                    confidence = 0.5  # Base confidence
                    if is_verified:
                        confidence += 0.2
                    if any(username.lower() in r.lower() for r in sum(BEAT_REPORTERS.values(), [])):
                        confidence += 0.25

                    alerts.append({
                        "player_name": injury_info.get("player", ""),
                        "team": injury_info.get("team", ""),
                        "status": injury_info.get("status", "QUESTIONABLE"),
                        "injury": injury_info.get("injury", ""),
                        "source": "twitter",
                        "tweet_text": text[:200],
                        "tweet_time": tweet.get("created_at", ""),
                        "confidence": min(1.0, confidence),
                        "reporter": f"@{username}"
                    })

            result = {
                "available": True,
                "alerts": alerts,
                "search_query": query,
                "tweets_analyzed": len(tweets),
                "source": "twitter"
            }

            _set_cached(cache_key, result)
            logger.info(f"Twitter: Found {len(alerts)} injury alerts from {len(tweets)} tweets")
            return result

    except Exception as e:
        logger.warning(f"Twitter injury fetch failed: {e}")
        return default_response


def _parse_injury_from_tweet(text: str, sport: str) -> Optional[Dict[str, str]]:
    """
    Parse player name, status, and injury from tweet text.

    Uses pattern matching to extract structured data from unstructured tweets.
    """
    text_upper = text.upper()

    # Check for injury indicators
    status = None
    if "RULED OUT" in text_upper or "WILL NOT PLAY" in text_upper or "OUT FOR" in text_upper:
        status = "OUT"
    elif "DOUBTFUL" in text_upper:
        status = "DOUBTFUL"
    elif "QUESTIONABLE" in text_upper or "GTD" in text_upper or "GAME-TIME" in text_upper:
        status = "GTD"
    elif "DAY-TO-DAY" in text_upper:
        status = "DAY_TO_DAY"

    if not status:
        return None

    # Try to extract player name (basic heuristic)
    # Look for capitalized names before injury keywords
    import re

    # Pattern: "Player Name" is/has/will be [status]
    name_pattern = r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:is|has been|will be|has|was)"
    match = re.search(name_pattern, text)

    player_name = ""
    if match:
        player_name = match.group(1)

    # Try to extract injury type
    injury_types = ["ankle", "knee", "hamstring", "groin", "back", "shoulder",
                    "concussion", "illness", "rest", "personal"]
    injury = ""
    for inj in injury_types:
        if inj.lower() in text.lower():
            injury = inj.title()
            break

    if player_name:
        return {
            "player": player_name,
            "team": "",  # Would need additional context
            "status": status,
            "injury": injury
        }

    return None


async def get_twitter_sentiment(
    sport: str,
    home_team: str,
    away_team: str,
    hours_back: int = 6
) -> Dict[str, Any]:
    """
    Analyze Twitter sentiment for a matchup.

    Returns:
        {
            "available": bool,
            "home_sentiment": float,  # -1.0 to 1.0
            "away_sentiment": float,
            "volume_home": int,
            "volume_away": int,
            "volume_ratio": float,  # away/home ratio
            "trending_players": [str],
            "sentiment_edge": str  # "HOME", "AWAY", "NEUTRAL"
        }
    """
    default_response = {
        "available": False,
        "home_sentiment": 0.0,
        "away_sentiment": 0.0,
        "volume_home": 0,
        "volume_away": 0,
        "volume_ratio": 1.0,
        "trending_players": [],
        "sentiment_edge": "NEUTRAL",
        "source": "twitter"
    }

    if not TWITTER_BEARER:
        return default_response

    cache_key = f"twitter_sentiment:{sport}:{home_team}:{away_team}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        # Fetch tweets for both teams in parallel
        home_data, away_data = await asyncio.gather(
            _fetch_team_tweets(home_team, sport, hours_back),
            _fetch_team_tweets(away_team, sport, hours_back),
            return_exceptions=True
        )

        if isinstance(home_data, Exception):
            home_data = {"tweets": [], "sentiment": 0}
        if isinstance(away_data, Exception):
            away_data = {"tweets": [], "sentiment": 0}

        volume_home = len(home_data.get("tweets", []))
        volume_away = len(away_data.get("tweets", []))

        # Calculate sentiment edge
        home_sentiment = home_data.get("sentiment", 0)
        away_sentiment = away_data.get("sentiment", 0)

        sentiment_edge = "NEUTRAL"
        if home_sentiment > away_sentiment + 0.2:
            sentiment_edge = "HOME"
        elif away_sentiment > home_sentiment + 0.2:
            sentiment_edge = "AWAY"

        result = {
            "available": True,
            "home_sentiment": home_sentiment,
            "away_sentiment": away_sentiment,
            "volume_home": volume_home,
            "volume_away": volume_away,
            "volume_ratio": volume_away / max(1, volume_home),
            "trending_players": [],
            "sentiment_edge": sentiment_edge,
            "source": "twitter"
        }

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.warning(f"Twitter sentiment fetch failed: {e}")
        return default_response


async def _fetch_team_tweets(team: str, sport: str, hours_back: int) -> Dict[str, Any]:
    """Fetch tweets about a specific team."""
    try:
        query = f"{team} {sport} -is:retweet lang:en"
        start_time = (datetime.utcnow() - timedelta(hours=hours_back)).isoformat() + "Z"

        url = f"{TWITTER_API_BASE}/tweets/search/recent"
        params = {
            "query": query,
            "max_results": 50,
            "start_time": start_time,
            "tweet.fields": "public_metrics"
        }

        headers = {
            "Authorization": f"Bearer {TWITTER_BEARER}"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params, headers=headers)

            if resp.status_code != 200:
                return {"tweets": [], "sentiment": 0}

            data = resp.json()
            tweets = data.get("data", [])

            # Simple sentiment analysis based on engagement
            total_sentiment = 0
            for tweet in tweets:
                metrics = tweet.get("public_metrics", {})
                likes = metrics.get("like_count", 0)
                retweets = metrics.get("retweet_count", 0)

                # Higher engagement = more positive sentiment (simplified)
                if likes + retweets > 100:
                    total_sentiment += 0.5
                elif likes + retweets > 20:
                    total_sentiment += 0.2

            avg_sentiment = total_sentiment / max(1, len(tweets))

            return {
                "tweets": tweets,
                "sentiment": min(1.0, max(-1.0, avg_sentiment))
            }

    except Exception:
        return {"tweets": [], "sentiment": 0}


def get_twitter_status() -> Dict[str, Any]:
    """Get Twitter API configuration status."""
    return {
        "configured": is_twitter_configured(),
        "bearer_set": bool(TWITTER_BEARER),
        "features": ["injury_alerts", "sentiment_analysis", "beat_reporters"],
        "cache_ttl": CACHE_TTL_SECONDS
    }
