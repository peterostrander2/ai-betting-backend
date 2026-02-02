"""
ESPN HIDDEN API - Lineups, Referees, and Game Details
======================================================
FREE API - No authentication required

Endpoints used:
- Scoreboard: https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard
- Game Details: https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={id}
- Officials: https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/events/{id}/competitions/{id}/officials

Sport/League mapping:
- NBA: basketball/nba
- NFL: football/nfl
- MLB: baseball/mlb
- NHL: hockey/nhl
- NCAAB: basketball/mens-college-basketball
"""

import httpx
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger("espn")

# ESPN Sport/League mapping
SPORT_MAPPING = {
    "NBA": {"sport": "basketball", "league": "nba"},
    "NFL": {"sport": "football", "league": "nfl"},
    "MLB": {"sport": "baseball", "mlb": "mlb"},
    "NHL": {"sport": "hockey", "league": "nhl"},
    "NCAAB": {"sport": "basketball", "league": "mens-college-basketball"},
}

# Cache for ESPN data (TTL managed by caller)
_espn_cache: Dict[str, Any] = {}
_cache_timestamps: Dict[str, float] = {}
CACHE_TTL = 300  # 5 minutes


def _is_cache_valid(key: str) -> bool:
    """Check if cache entry is still valid."""
    if key not in _cache_timestamps:
        return False
    return (datetime.now().timestamp() - _cache_timestamps[key]) < CACHE_TTL


def _cache_set(key: str, value: Any) -> None:
    """Set cache entry with timestamp."""
    _espn_cache[key] = value
    _cache_timestamps[key] = datetime.now().timestamp()


def _cache_get(key: str) -> Optional[Any]:
    """Get cache entry if valid."""
    if _is_cache_valid(key):
        return _espn_cache.get(key)
    return None


async def get_espn_scoreboard(sport: str, date: str = None) -> Dict[str, Any]:
    """
    Fetch ESPN scoreboard for a sport.

    Args:
        sport: Sport code (NBA, NFL, MLB, NHL, NCAAB)
        date: Optional date in YYYY-MM-DD format

    Returns:
        Scoreboard data with events list
    """
    mapping = SPORT_MAPPING.get(sport.upper())
    if not mapping:
        return {"events": [], "error": f"Unknown sport: {sport}"}

    cache_key = f"scoreboard_{sport}_{date or 'today'}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        base_url = f"https://site.api.espn.com/apis/site/v2/sports/{mapping['sport']}/{mapping['league']}/scoreboard"
        params = {}
        if date:
            params["dates"] = date.replace("-", "")

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(base_url, params=params)

            if resp.status_code != 200:
                logger.warning("ESPN scoreboard error: %d for %s", resp.status_code, sport)
                return {"events": [], "error": f"HTTP {resp.status_code}"}

            data = resp.json()
            _cache_set(cache_key, data)
            return data

    except Exception as e:
        logger.error("ESPN scoreboard exception for %s: %s", sport, e)
        return {"events": [], "error": str(e)}


async def get_espn_event_id(sport: str, home_team: str, away_team: str, date: str = None) -> Optional[str]:
    """
    Find ESPN event ID by matching home/away teams.

    Args:
        sport: Sport code
        home_team: Home team name (partial match)
        away_team: Away team name (partial match)
        date: Optional date in YYYY-MM-DD format

    Returns:
        ESPN event ID or None if not found
    """
    scoreboard = await get_espn_scoreboard(sport, date)
    events = scoreboard.get("events", [])

    home_lower = home_team.lower()
    away_lower = away_team.lower()

    for event in events:
        competitions = event.get("competitions", [])
        if not competitions:
            continue

        comp = competitions[0]
        competitors = comp.get("competitors", [])

        # Find home and away teams
        home_found = False
        away_found = False

        for team_data in competitors:
            team_name = team_data.get("team", {}).get("displayName", "").lower()
            short_name = team_data.get("team", {}).get("shortDisplayName", "").lower()
            abbrev = team_data.get("team", {}).get("abbreviation", "").lower()

            is_home = team_data.get("homeAway") == "home"

            # Check for match
            if home_lower in team_name or home_lower in short_name or home_lower == abbrev:
                if is_home:
                    home_found = True
            if away_lower in team_name or away_lower in short_name or away_lower == abbrev:
                if not is_home:
                    away_found = True

        if home_found and away_found:
            return event.get("id")

    return None


async def get_officials_for_event(sport: str, event_id: str) -> Dict[str, Any]:
    """
    Fetch officials (referees) for an ESPN event.

    Uses the ESPN Core API (Hidden API):
    https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/events/{id}/competitions/{id}/officials

    Args:
        sport: Sport code (NBA, NFL, MLB, NHL, NCAAB)
        event_id: ESPN event ID

    Returns:
        Officials data with referee names and positions
    """
    mapping = SPORT_MAPPING.get(sport.upper())
    if not mapping:
        return {"available": False, "error": f"Unknown sport: {sport}"}

    cache_key = f"officials_{sport}_{event_id}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        # ESPN Core API for officials
        url = f"https://sports.core.api.espn.com/v2/sports/{mapping['sport']}/leagues/{mapping['league']}/events/{event_id}/competitions/{event_id}/officials"

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)

            if resp.status_code == 404:
                # Officials not yet assigned or endpoint different for this sport
                return {
                    "available": False,
                    "reason": "NOT_ASSIGNED",
                    "message": "Officials not yet assigned for this game",
                    "officials": []
                }

            if resp.status_code != 200:
                logger.warning("ESPN officials error: %d for event %s", resp.status_code, event_id)
                return {
                    "available": False,
                    "error": f"HTTP {resp.status_code}",
                    "officials": []
                }

            data = resp.json()

            # Parse officials from response
            officials = []
            items = data.get("items", [])

            # ESPN returns $ref links, need to fetch each
            for item in items:
                ref = item.get("$ref", "")
                if ref:
                    # Fetch official details
                    try:
                        off_resp = await client.get(ref)
                        if off_resp.status_code == 200:
                            off_data = off_resp.json()
                            officials.append({
                                "name": off_data.get("displayName", "Unknown"),
                                "position": off_data.get("position", {}).get("displayName", "Official"),
                                "id": off_data.get("id", "")
                            })
                    except Exception as e:
                        logger.debug("Error fetching official detail: %s", e)

            result = {
                "available": len(officials) > 0,
                "source": "espn_live",
                "event_id": event_id,
                "officials": officials,
                "lead_official": officials[0]["name"] if officials else None,
                "official_2": officials[1]["name"] if len(officials) > 1 else None,
                "official_3": officials[2]["name"] if len(officials) > 2 else None,
            }

            _cache_set(cache_key, result)
            return result

    except Exception as e:
        logger.error("ESPN officials exception for event %s: %s", event_id, e)
        return {
            "available": False,
            "error": str(e),
            "officials": []
        }


async def get_officials_for_game(
    sport: str,
    home_team: str,
    away_team: str,
    date: str = None
) -> Dict[str, Any]:
    """
    Get officials for a game by team names.

    Args:
        sport: Sport code (NBA, NFL, MLB, NHL, NCAAB)
        home_team: Home team name
        away_team: Away team name
        date: Optional date in YYYY-MM-DD format

    Returns:
        Officials data or error info
    """
    # First find the ESPN event ID
    event_id = await get_espn_event_id(sport, home_team, away_team, date)

    if not event_id:
        return {
            "available": False,
            "reason": "GAME_NOT_FOUND",
            "message": f"Could not find ESPN event for {away_team} @ {home_team}",
            "officials": []
        }

    # Then fetch officials for that event
    return await get_officials_for_event(sport, event_id)


async def get_todays_games(sport: str) -> List[Dict[str, Any]]:
    """
    Get list of today's games with basic info.

    Args:
        sport: Sport code

    Returns:
        List of game dicts with id, home, away, time
    """
    scoreboard = await get_espn_scoreboard(sport)
    events = scoreboard.get("events", [])

    games = []
    for event in events:
        competitions = event.get("competitions", [])
        if not competitions:
            continue

        comp = competitions[0]
        competitors = comp.get("competitors", [])

        home_team = None
        away_team = None

        for team_data in competitors:
            team_info = team_data.get("team", {})
            if team_data.get("homeAway") == "home":
                home_team = team_info.get("displayName")
            else:
                away_team = team_info.get("displayName")

        if home_team and away_team:
            games.append({
                "id": event.get("id"),
                "home_team": home_team,
                "away_team": away_team,
                "date": event.get("date"),
                "status": event.get("status", {}).get("type", {}).get("name", "Unknown")
            })

    return games


async def get_game_details(sport: str, event_id: str) -> Dict[str, Any]:
    """
    Get detailed game information from ESPN summary endpoint.

    Args:
        sport: Sport code
        event_id: ESPN event ID

    Returns:
        Game details including lineups, odds, officials if available
    """
    mapping = SPORT_MAPPING.get(sport.upper())
    if not mapping:
        return {"error": f"Unknown sport: {sport}"}

    cache_key = f"details_{sport}_{event_id}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/{mapping['sport']}/{mapping['league']}/summary"
        params = {"event": event_id}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            data = resp.json()
            _cache_set(cache_key, data)
            return data

    except Exception as e:
        logger.error("ESPN game details error: %s", e)
        return {"error": str(e)}


def get_lineups_for_game(sport: str, home_team: str, away_team: str) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper for getting lineups (placeholder).

    For now returns empty - full lineup implementation would need async call.
    """
    return []


def get_referee_impact(sport: str, referee_name: str) -> Dict[str, Any]:
    """
    Get referee impact analysis.

    This is a placeholder that uses local tendency data.
    Full implementation would fetch from ESPN historical data.
    """
    # Use local tendencies from refs.py
    from .refs import lookup_referee_tendencies, calculate_referee_impact

    tendencies = lookup_referee_tendencies(sport, referee_name)
    return calculate_referee_impact(
        sport,
        referee_name,
        tendencies.get("foul_rate", 20.0),
        tendencies.get("home_bias", 0.0)
    )


def get_espn_status() -> Dict[str, Any]:
    """Get ESPN integration status."""
    return {
        "configured": True,
        "available": True,
        "source": "espn_hidden_api",
        "endpoints": {
            "scoreboard": "site.api.espn.com",
            "officials": "sports.core.api.espn.com"
        }
    }


# Synchronous wrappers for compatibility
def get_officials_sync(sport: str, home_team: str, away_team: str, date: str = None) -> Dict[str, Any]:
    """Synchronous wrapper for get_officials_for_game."""
    try:
        return asyncio.get_event_loop().run_until_complete(
            get_officials_for_game(sport, home_team, away_team, date)
        )
    except RuntimeError:
        # No event loop running, create new one
        return asyncio.run(get_officials_for_game(sport, home_team, away_team, date))
