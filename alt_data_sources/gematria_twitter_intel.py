"""
GEMATRIA TWITTER INTELLIGENCE - Community Wisdom Aggregator
============================================================
Monitors sports gematria accounts on X/Twitter to extract:
- Sacred numbers they're flagging
- Games/players they're decoding
- Consensus picks across multiple accounts

Accounts tracked (from gematria sports community):
- @GematriaClub - Daily decodes, triggers, rigged outcomes
- @ScriptLeaker - MLB/NFL picks, venue echoes, milestones
- @GematriaEffect - Zach Hubbard, foundational gematria
- @HitaLickPicks - Futures, daily plays
- @psgematria - Pro sports focused decodes
- @GiveMeCloutBets - Gematria sheets/stats
- @archaix138 - Phoenix chronology, 2178, simulacrum

Integration: Adds "community consensus" signal to Research engine
"""

import os
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import json

logger = logging.getLogger("gematria_intel")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Feature flag
GEMATRIA_INTEL_ENABLED = os.getenv("GEMATRIA_INTEL_ENABLED", "true").lower() == "true"

# Accounts to monitor (handle without @)
GEMATRIA_ACCOUNTS = [
    # Sports Gematria - Daily Picks
    {"handle": "GematriaClub", "weight": 1.0, "focus": "daily_decodes"},
    {"handle": "ScriptLeaker", "weight": 1.0, "focus": "mlb_nfl_scripts"},
    {"handle": "HitaLickPicks", "weight": 0.9, "focus": "futures"},
    {"handle": "psgematria", "weight": 0.9, "focus": "pro_sports"},
    {"handle": "GiveMeCloutBets", "weight": 0.8, "focus": "sheets_stats"},

    # Foundational Gematria - Zach Hubbard
    {"handle": "GematriaEffect", "weight": 1.0, "focus": "foundational"},
    {"handle": "GematriaEffectNews", "weight": 1.0, "focus": "foundational"},
    {"handle": "ZachHubbard", "weight": 1.0, "focus": "gematria_effect_sports"},

    # Esoteric/Numerology Research
    {"handle": "archaix138", "weight": 0.9, "focus": "phoenix_chronology"},
    {"handle": "GemcodeMatrix", "weight": 0.8, "focus": "gematria_codes"},
    {"handle": "DerekTikkuri", "weight": 0.8, "focus": "numerology_sacred_geometry"},
    {"handle": "CodesUniverse", "weight": 0.7, "focus": "number_patterns"},
]

# Sacred numbers to detect in posts
SACRED_NUMBERS = {
    # Jarvis triggers (highest priority)
    2178: {"name": "IMMORTAL", "weight": 2.0},
    1656: {"name": "PHOENIX", "weight": 1.8},
    552: {"name": "PHOENIX_FRAGMENT", "weight": 1.5},
    201: {"name": "ORDER", "weight": 1.5},
    138: {"name": "PLASMA_CYCLE", "weight": 1.5},
    33: {"name": "MASTER", "weight": 1.3},
    93: {"name": "WILL", "weight": 1.3},
    322: {"name": "SOCIETY", "weight": 1.3},
    666: {"name": "BEAST", "weight": 1.2},
    888: {"name": "JESUS", "weight": 1.2},
    369: {"name": "TESLA", "weight": 1.2},

    # Common gematria values
    47: {"name": "FOUNDATION", "weight": 1.0},
    74: {"name": "REVERSE_FOUNDATION", "weight": 1.0},
    59: {"name": "SLAVE", "weight": 1.0},
    95: {"name": "REVERSE_SLAVE", "weight": 1.0},
    42: {"name": "FREEMASON", "weight": 1.0},
    48: {"name": "ILLUMINATI", "weight": 1.0},
    84: {"name": "REVERSE_ILLUMINATI", "weight": 1.0},
    56: {"name": "CHAMPIONSHIP", "weight": 1.0},
    65: {"name": "REVERSE_CHAMPIONSHIP", "weight": 1.0},
    58: {"name": "FREEMASONRY", "weight": 1.0},
    85: {"name": "REVERSE_FREEMASONRY", "weight": 1.0},

    # Power numbers
    11: {"name": "MASTER_11", "weight": 0.8},
    22: {"name": "MASTER_22", "weight": 0.8},
    44: {"name": "KILL", "weight": 0.9},
    55: {"name": "SACRIFICE", "weight": 0.9},
    77: {"name": "CHRIST", "weight": 0.8},
    99: {"name": "COMPLETION", "weight": 0.8},
    111: {"name": "TRIPLE_1", "weight": 1.0},
    222: {"name": "TRIPLE_2", "weight": 1.0},
    333: {"name": "TRIPLE_3", "weight": 1.0},
    444: {"name": "TRIPLE_4", "weight": 1.0},
    555: {"name": "TRIPLE_5", "weight": 1.0},
    777: {"name": "TRIPLE_7", "weight": 1.1},
}

# Sport keywords for context detection
SPORT_KEYWORDS = {
    "NBA": ["nba", "basketball", "lakers", "celtics", "warriors", "nets", "bulls", "heat", "knicks", "bucks", "suns", "76ers", "sixers", "mavs", "mavericks", "nuggets", "clippers", "lebron", "curry", "durant", "giannis", "jokic", "tatum", "doncic"],
    "NFL": ["nfl", "football", "chiefs", "eagles", "bills", "cowboys", "49ers", "niners", "ravens", "lions", "packers", "dolphins", "bengals", "jets", "patriots", "steelers", "raiders", "broncos", "mahomes", "allen", "hurts", "burrow", "super bowl", "superbowl"],
    "MLB": ["mlb", "baseball", "yankees", "dodgers", "mets", "braves", "astros", "phillies", "padres", "rangers", "cubs", "red sox", "redsox", "cardinals", "mariners", "orioles", "twins", "world series"],
    "NHL": ["nhl", "hockey", "bruins", "rangers", "avalanche", "panthers", "oilers", "lightning", "maple leafs", "leafs", "canadiens", "habs", "penguins", "capitals", "caps", "stanley cup"],
    "NCAAB": ["ncaa", "college basketball", "march madness", "duke", "kentucky", "kansas", "unc", "tar heels", "ucla", "gonzaga", "villanova", "purdue", "uconn", "final four"],
}

# Pick direction keywords
DIRECTION_KEYWORDS = {
    "over": ["over", "o/u over", "total over", "hit the over", "points over", "scoring over"],
    "under": ["under", "o/u under", "total under", "hit the under", "points under", "scoring under"],
    "favorite": ["favorite", "fav", "chalk", "cover", "ats cover", "spread cover", "-"],
    "underdog": ["underdog", "dog", "upset", "fade", "against the spread", "+"],
    "home": ["home", "home team", "home win"],
    "away": ["away", "road", "visitor", "away team"],
}

# Cache settings
CACHE_TTL_MINUTES = 30
_cache: Dict[str, Any] = {}
_cache_timestamps: Dict[str, datetime] = {}


# =============================================================================
# SERPAPI INTEGRATION
# =============================================================================

def _get_serpapi_key() -> Optional[str]:
    """Get SerpAPI key from environment."""
    return os.getenv("SERPAPI_KEY") or os.getenv("SERP_API_KEY")


def _search_twitter_direct(query: str, num_results: int = 20) -> List[Dict[str, Any]]:
    """
    Search Twitter/X via direct Twitter API v2.

    Preferred over SerpAPI to avoid quota burn.
    Returns results in same format as _search_twitter_via_serp for compatibility.
    """
    try:
        from alt_data_sources.twitter import search_tweets, TWITTER_ENABLED
        if not TWITTER_ENABLED:
            return []

        result = search_tweets(query, max_results=num_results, include_metrics=True)
        if result.get("status") != "SUCCESS":
            return []

        # Convert to same format as SerpAPI results
        converted = []
        for tweet in result.get("tweets", []):
            converted.append({
                "title": tweet.get("text", "")[:100],
                "snippet": tweet.get("text", ""),
                "link": f"https://twitter.com/i/status/{tweet.get('id', '')}",
                "source": "twitter_api_direct",
                "engagement": tweet.get("engagement", 0),
                "metrics": tweet.get("metrics", {}),
            })
        logger.info("Twitter direct search: %d results for '%s'", len(converted), query[:30])
        return converted

    except ImportError:
        logger.debug("Twitter direct module not available")
        return []
    except Exception as e:
        logger.warning("Twitter direct search failed: %s", e)
        return []


def _search_twitter_via_serp(query: str, num_results: int = 20) -> List[Dict[str, Any]]:
    """
    Search Twitter/X via SerpAPI (fallback).

    Uses Google search with site:twitter.com or site:x.com
    NOTE: Prefer _search_twitter_direct when TWITTER_BEARER is available.
    """
    api_key = _get_serpapi_key()
    if not api_key:
        logger.warning("SerpAPI key not configured")
        return []

    try:
        import requests

        # Search both twitter.com and x.com
        full_query = f"site:twitter.com OR site:x.com {query}"

        params = {
            "q": full_query,
            "api_key": api_key,
            "engine": "google",
            "num": num_results,
            "tbm": "nws",  # News/recent results
        }

        response = requests.get(
            "https://serpapi.com/search",
            params=params,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get("organic_results", []) + data.get("news_results", [])
            return results
        else:
            logger.warning("SerpAPI returned status %d", response.status_code)
            return []

    except Exception as e:
        logger.error("SerpAPI search failed: %s", e)
        return []


def _search_twitter(query: str, num_results: int = 20) -> List[Dict[str, Any]]:
    """
    Search Twitter/X - prefers direct API, falls back to SerpAPI.

    This is the main entry point for Twitter search in gematria intel.
    """
    # Try direct Twitter API first (no quota burn)
    results = _search_twitter_direct(query, num_results)
    if results:
        return results

    # Fall back to SerpAPI
    logger.debug("Falling back to SerpAPI for Twitter search")
    return _search_twitter_via_serp(query, num_results)


def fetch_account_posts(handle: str, days_back: int = 3) -> List[Dict[str, Any]]:
    """
    Fetch recent posts from a Twitter/X account.

    Args:
        handle: Twitter handle (without @)
        days_back: How many days back to search

    Returns:
        List of post dicts with text, date, url
    """
    cache_key = f"posts_{handle}_{days_back}"

    # Check cache
    if cache_key in _cache:
        cache_time = _cache_timestamps.get(cache_key)
        if cache_time and datetime.now() - cache_time < timedelta(minutes=CACHE_TTL_MINUTES):
            return _cache[cache_key]

    # Search for account's posts
    query = f"from:{handle}"
    results = _search_twitter(query, num_results=30)

    posts = []
    cutoff = datetime.now() - timedelta(days=days_back)

    for result in results:
        post = {
            "handle": handle,
            "text": result.get("snippet", "") or result.get("title", ""),
            "url": result.get("link", ""),
            "date": result.get("date", ""),
            "source": "serpapi"
        }

        # Try to parse date and filter
        try:
            if post["date"]:
                # SerpAPI dates are often relative ("2 days ago") or formatted
                post["parsed_date"] = _parse_relative_date(post["date"])
                if post["parsed_date"] and post["parsed_date"] < cutoff:
                    continue
        except Exception:
            pass

        if post["text"]:
            posts.append(post)

    # Cache results
    _cache[cache_key] = posts
    _cache_timestamps[cache_key] = datetime.now()

    logger.info("Fetched %d posts from @%s", len(posts), handle)
    return posts


def _parse_relative_date(date_str: str) -> Optional[datetime]:
    """Parse relative date strings like '2 days ago'."""
    if not date_str:
        return None

    date_str = date_str.lower()
    now = datetime.now()

    if "hour" in date_str:
        match = re.search(r"(\d+)\s*hour", date_str)
        if match:
            hours = int(match.group(1))
            return now - timedelta(hours=hours)
    elif "day" in date_str:
        match = re.search(r"(\d+)\s*day", date_str)
        if match:
            days = int(match.group(1))
            return now - timedelta(days=days)
    elif "week" in date_str:
        match = re.search(r"(\d+)\s*week", date_str)
        if match:
            weeks = int(match.group(1))
            return now - timedelta(weeks=weeks)
    elif "yesterday" in date_str:
        return now - timedelta(days=1)
    elif "today" in date_str:
        return now

    return None


# =============================================================================
# POST ANALYSIS
# =============================================================================

def extract_numbers_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Extract sacred/significant numbers from post text.

    Returns list of {number, name, weight, context}
    """
    if not text:
        return []

    found_numbers = []
    text_lower = text.lower()

    # Find all numbers in text
    numbers = re.findall(r'\b(\d+)\b', text)

    for num_str in numbers:
        try:
            num = int(num_str)

            # Check if it's a sacred number
            if num in SACRED_NUMBERS:
                info = SACRED_NUMBERS[num]
                found_numbers.append({
                    "number": num,
                    "name": info["name"],
                    "weight": info["weight"],
                    "context": _get_number_context(text, num_str)
                })
            # Check for significant patterns even if not in our list
            elif num in [num for num in range(100, 1000) if sum(int(d) for d in str(num)) in [9, 18, 27]]:
                # Numbers that reduce to 9 (completion)
                found_numbers.append({
                    "number": num,
                    "name": "REDUCES_TO_9",
                    "weight": 0.6,
                    "context": _get_number_context(text, num_str)
                })

        except ValueError:
            continue

    return found_numbers


def _get_number_context(text: str, number: str, window: int = 50) -> str:
    """Get surrounding context for a number mention."""
    idx = text.find(number)
    if idx == -1:
        return ""

    start = max(0, idx - window)
    end = min(len(text), idx + len(number) + window)
    return text[start:end].strip()


def detect_sport(text: str) -> Optional[str]:
    """Detect which sport a post is about."""
    if not text:
        return None

    text_lower = text.lower()

    sport_scores = {}
    for sport, keywords in SPORT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            sport_scores[sport] = score

    if sport_scores:
        return max(sport_scores, key=sport_scores.get)
    return None


def detect_pick_direction(text: str) -> Dict[str, float]:
    """
    Detect betting direction from post text.

    Returns dict with confidence scores for each direction.
    """
    if not text:
        return {}

    text_lower = text.lower()
    directions = {}

    for direction, keywords in DIRECTION_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            directions[direction] = min(1.0, score * 0.3)

    return directions


def extract_teams_players(text: str, sport: str = None) -> Dict[str, List[str]]:
    """
    Extract team and player mentions from text.

    Returns {teams: [...], players: [...]}
    """
    if not text:
        return {"teams": [], "players": []}

    teams = []
    players = []
    text_lower = text.lower()

    # Check sport-specific keywords that are team names
    if sport:
        keywords = SPORT_KEYWORDS.get(sport, [])
        for kw in keywords:
            if kw in text_lower and len(kw) > 3:  # Avoid short words
                teams.append(kw.title())

    # Look for "vs" or "@" patterns for matchups
    vs_pattern = re.search(r'(\w+(?:\s+\w+)?)\s+(?:vs\.?|@|at)\s+(\w+(?:\s+\w+)?)', text, re.IGNORECASE)
    if vs_pattern:
        teams.extend([vs_pattern.group(1).strip(), vs_pattern.group(2).strip()])

    return {"teams": list(set(teams)), "players": list(set(players))}


def analyze_post(post: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full analysis of a single post.

    Returns structured analysis with numbers, sport, direction, teams.
    """
    text = post.get("text", "")

    analysis = {
        "handle": post.get("handle"),
        "text": text[:500],  # Truncate for storage
        "url": post.get("url"),
        "numbers": extract_numbers_from_text(text),
        "sport": detect_sport(text),
        "directions": detect_pick_direction(text),
        "entities": extract_teams_players(text),
        "analyzed_at": datetime.now().isoformat(),
    }

    # Calculate post significance score
    num_weight = sum(n["weight"] for n in analysis["numbers"])
    has_direction = bool(analysis["directions"])
    has_sport = bool(analysis["sport"])

    analysis["significance"] = (
        num_weight * 0.5 +
        (1.0 if has_direction else 0) * 0.25 +
        (1.0 if has_sport else 0) * 0.25
    )

    return analysis


# =============================================================================
# CONSENSUS DETECTION
# =============================================================================

def aggregate_community_signals(
    sport: str = None,
    days_back: int = 2
) -> Dict[str, Any]:
    """
    Aggregate signals across all tracked gematria accounts.

    Returns:
        - hot_numbers: Numbers being flagged by multiple accounts
        - consensus_picks: Picks with multi-account agreement
        - account_activity: Summary per account
    """
    if not GEMATRIA_INTEL_ENABLED:
        return {
            "enabled": False,
            "reason": "GEMATRIA_INTEL_ENABLED=false"
        }

    all_analyses = []
    account_activity = {}

    # Fetch and analyze posts from all accounts
    for account in GEMATRIA_ACCOUNTS:
        handle = account["handle"]
        posts = fetch_account_posts(handle, days_back=days_back)

        analyses = [analyze_post(p) for p in posts]

        # Filter by sport if specified
        if sport:
            analyses = [a for a in analyses if a["sport"] == sport or a["sport"] is None]

        all_analyses.extend(analyses)
        account_activity[handle] = {
            "posts_found": len(posts),
            "posts_analyzed": len(analyses),
            "weight": account["weight"],
            "focus": account["focus"]
        }

    # Aggregate numbers across all posts
    number_counts = defaultdict(lambda: {"count": 0, "accounts": set(), "contexts": []})
    for analysis in all_analyses:
        for num_info in analysis.get("numbers", []):
            num = num_info["number"]
            number_counts[num]["count"] += 1
            number_counts[num]["accounts"].add(analysis["handle"])
            number_counts[num]["contexts"].append(num_info.get("context", "")[:100])
            number_counts[num]["name"] = num_info["name"]
            number_counts[num]["weight"] = num_info["weight"]

    # Find hot numbers (mentioned by multiple accounts)
    hot_numbers = []
    for num, data in number_counts.items():
        if len(data["accounts"]) >= 2 or data["count"] >= 3:
            hot_numbers.append({
                "number": num,
                "name": data["name"],
                "weight": data["weight"],
                "mention_count": data["count"],
                "account_count": len(data["accounts"]),
                "accounts": list(data["accounts"]),
                "consensus_score": len(data["accounts"]) * data["weight"]
            })

    # Sort by consensus score
    hot_numbers.sort(key=lambda x: x["consensus_score"], reverse=True)

    # Aggregate direction signals
    direction_signals = defaultdict(lambda: {"count": 0, "accounts": set()})
    for analysis in all_analyses:
        for direction, confidence in analysis.get("directions", {}).items():
            if confidence > 0.3:
                direction_signals[direction]["count"] += 1
                direction_signals[direction]["accounts"].add(analysis["handle"])

    # Find consensus directions
    consensus_directions = {}
    for direction, data in direction_signals.items():
        if len(data["accounts"]) >= 2:
            consensus_directions[direction] = {
                "count": data["count"],
                "accounts": list(data["accounts"])
            }

    return {
        "enabled": True,
        "sport_filter": sport,
        "days_analyzed": days_back,
        "total_posts_analyzed": len(all_analyses),
        "hot_numbers": hot_numbers[:10],  # Top 10
        "consensus_directions": consensus_directions,
        "account_activity": account_activity,
        "generated_at": datetime.now().isoformat()
    }


def get_gematria_consensus_boost(
    sport: str,
    home_team: str = None,
    away_team: str = None,
    spread: float = None,
    total: float = None,
    player_name: str = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Get consensus boost for a specific pick.

    Checks if the pick aligns with what the gematria community is flagging.

    Args:
        sport: Sport code (NBA, NFL, etc.)
        home_team: Home team name
        away_team: Away team name
        spread: Current spread
        total: Current total
        player_name: Player name (for props)

    Returns:
        Tuple of (boost, metadata)
        - boost: 0.0 to 0.5 based on community consensus
        - metadata: Full analysis for debugging
    """
    if not GEMATRIA_INTEL_ENABLED:
        return 0.0, {"enabled": False}

    try:
        # Get community signals
        signals = aggregate_community_signals(sport=sport, days_back=2)

        if not signals.get("enabled"):
            return 0.0, signals

        hot_numbers = signals.get("hot_numbers", [])
        if not hot_numbers:
            return 0.0, {
                "enabled": True,
                "reason": "no_hot_numbers",
                "signals": signals
            }

        # Check if our values match any hot numbers
        matches = []
        values_to_check = []

        if spread:
            values_to_check.append(("spread", abs(spread)))
            values_to_check.append(("spread_int", int(abs(spread))))
        if total:
            values_to_check.append(("total", total))
            values_to_check.append(("total_int", int(total)))

        for hot in hot_numbers:
            hot_num = hot["number"]
            for value_type, value in values_to_check:
                # Direct match
                if value == hot_num:
                    matches.append({
                        "type": value_type,
                        "value": value,
                        "matched_number": hot_num,
                        "name": hot["name"],
                        "consensus_score": hot["consensus_score"]
                    })
                # Check if total contains the number
                elif value_type == "total" and str(hot_num) in str(int(value)):
                    matches.append({
                        "type": f"{value_type}_contains",
                        "value": value,
                        "matched_number": hot_num,
                        "name": hot["name"],
                        "consensus_score": hot["consensus_score"] * 0.5
                    })

        # Calculate boost
        if matches:
            total_consensus = sum(m["consensus_score"] for m in matches)
            boost = min(0.5, total_consensus * 0.1)  # Cap at 0.5

            return boost, {
                "enabled": True,
                "boost": boost,
                "matches": matches,
                "hot_numbers_checked": len(hot_numbers),
                "reason": f"matched {len(matches)} hot numbers"
            }

        return 0.0, {
            "enabled": True,
            "boost": 0.0,
            "matches": [],
            "hot_numbers_checked": len(hot_numbers),
            "reason": "no_matches"
        }

    except Exception as e:
        logger.error("Gematria consensus check failed: %s", e)
        return 0.0, {"enabled": True, "error": str(e)}


# =============================================================================
# DAILY DIGEST
# =============================================================================

def generate_daily_digest(sport: str = None) -> Dict[str, Any]:
    """
    Generate a daily digest of gematria community activity.

    Useful for manual review and learning.
    """
    signals = aggregate_community_signals(sport=sport, days_back=1)

    digest = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "sport": sport or "ALL",
        "summary": {
            "posts_analyzed": signals.get("total_posts_analyzed", 0),
            "hot_numbers_count": len(signals.get("hot_numbers", [])),
            "active_accounts": sum(
                1 for a in signals.get("account_activity", {}).values()
                if a.get("posts_found", 0) > 0
            )
        },
        "top_5_numbers": signals.get("hot_numbers", [])[:5],
        "consensus_directions": signals.get("consensus_directions", {}),
        "account_breakdown": signals.get("account_activity", {}),
        "generated_at": datetime.now().isoformat()
    }

    return digest


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "GEMATRIA_INTEL_ENABLED",
    "GEMATRIA_ACCOUNTS",
    "SACRED_NUMBERS",
    "fetch_account_posts",
    "analyze_post",
    "aggregate_community_signals",
    "get_gematria_consensus_boost",
    "generate_daily_digest",
]
