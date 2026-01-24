"""
RotoWire API Integration - v10.61
=================================
Fetches starting lineups, referee assignments, and injury news from RotoWire.

Key data for improving picks:
1. Starting Lineups - Know who's actually playing
2. Referee Assignments - Wire into OfficialsService for ref tendencies
3. Injury News - Real-time injury updates

API Docs: https://www.rotowire.com/api/
"""

import os
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional, List
import httpx

logger = logging.getLogger(__name__)

# Configuration
ROTOWIRE_API_KEY = os.getenv("ROTOWIRE_API_KEY", "")
ROTOWIRE_API_BASE = os.getenv("ROTOWIRE_API_BASE", "https://api.rotowire.com")

# Cache for API responses (15 min TTL)
_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 900


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


# Sport mapping for RotoWire API
ROTOWIRE_SPORTS = {
    "nba": "nba",
    "nfl": "nfl",
    "mlb": "mlb",
    "nhl": "nhl",
    "ncaab": "cbb",
    "ncaaf": "cfb"
}


async def get_starting_lineups(sport: str, game_date: date = None) -> Dict[str, Any]:
    """
    Fetch confirmed starting lineups from RotoWire.

    Returns:
        {
            "available": bool,
            "sport": str,
            "date": str,
            "games": [
                {
                    "game_id": str,
                    "home_team": str,
                    "away_team": str,
                    "home_starters": [{"name": str, "position": str, "status": str}],
                    "away_starters": [{"name": str, "position": str, "status": str}]
                }
            ]
        }
    """
    default_response = {
        "available": False,
        "sport": sport.upper(),
        "date": (game_date or date.today()).isoformat(),
        "games": [],
        "source": "rotowire"
    }

    if not ROTOWIRE_API_KEY:
        logger.debug("ROTOWIRE_API_KEY not configured")
        return default_response

    sport_key = ROTOWIRE_SPORTS.get(sport.lower())
    if not sport_key:
        logger.warning(f"Unknown sport for RotoWire: {sport}")
        return default_response

    if game_date is None:
        game_date = date.today()

    cache_key = f"rotowire_lineups:{sport}:{game_date.isoformat()}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        # RotoWire lineup endpoint
        url = f"{ROTOWIRE_API_BASE}/{sport_key}/lineups"
        params = {
            "key": ROTOWIRE_API_KEY,
            "date": game_date.strftime("%Y-%m-%d")
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)

            if resp.status_code == 401:
                logger.warning("RotoWire API key invalid or expired")
                return default_response

            if resp.status_code != 200:
                logger.warning(f"RotoWire lineups API error: {resp.status_code}")
                return default_response

            data = resp.json()

            # Parse response into standardized format
            games = []
            for game in data.get("games", data.get("lineups", [])):
                parsed_game = {
                    "game_id": game.get("game_id", game.get("id", "")),
                    "home_team": game.get("home_team", game.get("home", {}).get("team", "")),
                    "away_team": game.get("away_team", game.get("away", {}).get("team", "")),
                    "game_time": game.get("game_time", game.get("start_time", "")),
                    "home_starters": _parse_starters(game.get("home_starters", game.get("home", {}).get("lineup", []))),
                    "away_starters": _parse_starters(game.get("away_starters", game.get("away", {}).get("lineup", []))),
                }
                games.append(parsed_game)

            result = {
                "available": True,
                "sport": sport.upper(),
                "date": game_date.isoformat(),
                "games": games,
                "game_count": len(games),
                "source": "rotowire"
            }

            _set_cached(cache_key, result)
            logger.info(f"RotoWire: Fetched {len(games)} {sport.upper()} lineups for {game_date}")
            return result

    except Exception as e:
        logger.warning(f"RotoWire lineups fetch failed: {e}")
        return default_response


def _parse_starters(starters: List) -> List[Dict]:
    """Parse starter list into standardized format."""
    result = []
    for player in starters:
        if isinstance(player, dict):
            result.append({
                "name": player.get("name", player.get("player_name", "")),
                "position": player.get("position", player.get("pos", "")),
                "status": player.get("status", "CONFIRMED"),
                "jersey": player.get("jersey", player.get("number", ""))
            })
        elif isinstance(player, str):
            result.append({
                "name": player,
                "position": "",
                "status": "CONFIRMED",
                "jersey": ""
            })
    return result


async def get_referee_assignments(sport: str, game_date: date = None) -> Dict[str, Any]:
    """
    Fetch referee/official assignments from RotoWire.

    This is the KEY data needed to activate OfficialsService!

    Returns:
        {
            "available": bool,
            "sport": str,
            "date": str,
            "games": [
                {
                    "game_id": str,
                    "home_team": str,
                    "away_team": str,
                    "officials": {
                        "lead_official": str,
                        "official_2": str,
                        "official_3": str,
                        "umpires": [str]  # MLB
                    }
                }
            ]
        }
    """
    default_response = {
        "available": False,
        "sport": sport.upper(),
        "date": (game_date or date.today()).isoformat(),
        "games": [],
        "source": "rotowire"
    }

    if not ROTOWIRE_API_KEY:
        logger.debug("ROTOWIRE_API_KEY not configured")
        return default_response

    sport_key = ROTOWIRE_SPORTS.get(sport.lower())
    if not sport_key:
        return default_response

    if game_date is None:
        game_date = date.today()

    cache_key = f"rotowire_refs:{sport}:{game_date.isoformat()}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        # RotoWire officials/referees endpoint
        url = f"{ROTOWIRE_API_BASE}/{sport_key}/officials"
        params = {
            "key": ROTOWIRE_API_KEY,
            "date": game_date.strftime("%Y-%m-%d")
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                logger.warning(f"RotoWire officials API error: {resp.status_code}")
                return default_response

            data = resp.json()

            games = []
            for game in data.get("games", data.get("officials", [])):
                officials = game.get("officials", game.get("referees", {}))

                # Normalize official names based on sport
                parsed_officials = _parse_officials(officials, sport.lower())

                parsed_game = {
                    "game_id": game.get("game_id", game.get("id", "")),
                    "home_team": game.get("home_team", game.get("home", "")),
                    "away_team": game.get("away_team", game.get("away", "")),
                    "game_time": game.get("game_time", game.get("start_time", "")),
                    "officials": parsed_officials
                }
                games.append(parsed_game)

            result = {
                "available": True,
                "sport": sport.upper(),
                "date": game_date.isoformat(),
                "games": games,
                "game_count": len(games),
                "source": "rotowire"
            }

            _set_cached(cache_key, result)
            logger.info(f"RotoWire: Fetched officials for {len(games)} {sport.upper()} games")
            return result

    except Exception as e:
        logger.warning(f"RotoWire officials fetch failed: {e}")
        return default_response


def _parse_officials(officials: Any, sport: str) -> Dict[str, Any]:
    """Parse officials data into standardized format."""
    result = {
        "lead_official": "",
        "official_2": "",
        "official_3": "",
        "all_officials": []
    }

    if isinstance(officials, list):
        # List of official names
        if len(officials) >= 1:
            result["lead_official"] = officials[0]
        if len(officials) >= 2:
            result["official_2"] = officials[1]
        if len(officials) >= 3:
            result["official_3"] = officials[2]
        result["all_officials"] = officials

    elif isinstance(officials, dict):
        # Named officials
        if sport == "nba":
            result["lead_official"] = officials.get("crew_chief", officials.get("referee_1", ""))
            result["official_2"] = officials.get("referee", officials.get("referee_2", ""))
            result["official_3"] = officials.get("umpire", officials.get("referee_3", ""))
        elif sport == "nfl":
            result["lead_official"] = officials.get("referee", officials.get("head_referee", ""))
            result["official_2"] = officials.get("umpire", "")
            result["official_3"] = officials.get("head_linesman", officials.get("down_judge", ""))
        elif sport == "mlb":
            result["lead_official"] = officials.get("home_plate", officials.get("hp_umpire", ""))
            result["official_2"] = officials.get("first_base", officials.get("1b_umpire", ""))
            result["official_3"] = officials.get("second_base", officials.get("2b_umpire", ""))
        elif sport == "nhl":
            result["lead_official"] = officials.get("referee_1", officials.get("referee", ""))
            result["official_2"] = officials.get("referee_2", "")
            result["official_3"] = officials.get("linesman_1", "")
        else:
            # Generic fallback
            result["lead_official"] = officials.get("referee", officials.get("official", ""))

        result["all_officials"] = [v for v in officials.values() if isinstance(v, str) and v]

    return result


async def get_injury_news(sport: str, hours_back: int = 24) -> Dict[str, Any]:
    """
    Fetch latest injury news from RotoWire.

    Returns:
        {
            "available": bool,
            "sport": str,
            "news": [
                {
                    "player_name": str,
                    "team": str,
                    "status": str,  # OUT, DOUBTFUL, QUESTIONABLE, PROBABLE
                    "injury": str,
                    "headline": str,
                    "updated": str
                }
            ]
        }
    """
    default_response = {
        "available": False,
        "sport": sport.upper(),
        "news": [],
        "source": "rotowire"
    }

    if not ROTOWIRE_API_KEY:
        return default_response

    sport_key = ROTOWIRE_SPORTS.get(sport.lower())
    if not sport_key:
        return default_response

    cache_key = f"rotowire_injuries:{sport}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        url = f"{ROTOWIRE_API_BASE}/{sport_key}/injuries"
        params = {
            "key": ROTOWIRE_API_KEY,
            "hours": hours_back
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                logger.warning(f"RotoWire injuries API error: {resp.status_code}")
                return default_response

            data = resp.json()

            news = []
            for item in data.get("injuries", data.get("news", [])):
                news.append({
                    "player_name": item.get("player", item.get("player_name", "")),
                    "team": item.get("team", ""),
                    "status": item.get("status", "UNKNOWN").upper(),
                    "injury": item.get("injury", item.get("injury_type", "")),
                    "headline": item.get("headline", item.get("news", "")),
                    "updated": item.get("updated", item.get("date", ""))
                })

            result = {
                "available": True,
                "sport": sport.upper(),
                "news": news,
                "count": len(news),
                "source": "rotowire"
            }

            _set_cached(cache_key, result)
            logger.info(f"RotoWire: Fetched {len(news)} injury updates for {sport.upper()}")
            return result

    except Exception as e:
        logger.warning(f"RotoWire injuries fetch failed: {e}")
        return default_response


def is_rotowire_configured() -> bool:
    """Check if RotoWire API is configured."""
    return bool(ROTOWIRE_API_KEY)


def get_rotowire_status() -> Dict[str, Any]:
    """Get RotoWire API configuration status."""
    return {
        "configured": is_rotowire_configured(),
        "api_key_set": bool(ROTOWIRE_API_KEY),
        "base_url": ROTOWIRE_API_BASE,
        "supported_sports": list(ROTOWIRE_SPORTS.keys()),
        "features": ["starting_lineups", "referee_assignments", "injury_news"]
    }


# ============================================================================
# INTEGRATION HELPERS (for live_data_router.py)
# ============================================================================

async def get_officials_for_game(sport: str, home_team: str, away_team: str, game_date: date = None) -> Optional[Dict]:
    """
    Get officials for a specific game.

    Returns officials dict ready for OfficialsService.get_adjustment()
    """
    refs_data = await get_referee_assignments(sport, game_date)

    if not refs_data.get("available"):
        return None

    # Find matching game
    home_lower = home_team.lower()
    away_lower = away_team.lower()

    for game in refs_data.get("games", []):
        game_home = game.get("home_team", "").lower()
        game_away = game.get("away_team", "").lower()

        # Match by team name (fuzzy)
        if (home_lower in game_home or game_home in home_lower) and \
           (away_lower in game_away or game_away in away_lower):
            return game.get("officials")

    return None


async def is_player_in_lineup(sport: str, player_name: str, game_date: date = None) -> Dict[str, Any]:
    """
    Check if a player is in the starting lineup.

    Returns:
        {
            "in_lineup": bool,
            "status": str,  # CONFIRMED, EXPECTED, NOT_FOUND
            "team": str,
            "position": str
        }
    """
    lineups = await get_starting_lineups(sport, game_date)

    if not lineups.get("available"):
        return {"in_lineup": False, "status": "NO_DATA", "team": "", "position": ""}

    player_lower = player_name.lower()

    for game in lineups.get("games", []):
        # Check home starters
        for starter in game.get("home_starters", []):
            if player_lower in starter.get("name", "").lower():
                return {
                    "in_lineup": True,
                    "status": starter.get("status", "CONFIRMED"),
                    "team": game.get("home_team", ""),
                    "position": starter.get("position", "")
                }

        # Check away starters
        for starter in game.get("away_starters", []):
            if player_lower in starter.get("name", "").lower():
                return {
                    "in_lineup": True,
                    "status": starter.get("status", "CONFIRMED"),
                    "team": game.get("away_team", ""),
                    "position": starter.get("position", "")
                }

    return {"in_lineup": False, "status": "NOT_FOUND", "team": "", "position": ""}
