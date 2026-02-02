"""
ESPN HIDDEN API - Comprehensive Sports Data
============================================
FREE API - No authentication required

Endpoints used:
- Scoreboard: https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard
- Game Summary: https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={id}
- Officials: https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/events/{id}/competitions/{id}/officials
- Team Info: https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams/{abbrev}

Data available from summary endpoint:
- Officials (referees) - Pillar 16
- Odds (spread, ML, O/U) - Secondary validation
- Injuries - Inline with game data
- Venue/Weather - For outdoor sports
- Box scores - Player stats
- Attendance

Sport/League mapping:
- NBA: basketball/nba
- NFL: football/nfl
- MLB: baseball/mlb
- NHL: hockey/nhl
- NCAAB: basketball/mens-college-basketball

Reference: https://scrapecreators.com/blog/espn-api-free-sports-data
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
    "MLB": {"sport": "baseball", "league": "mlb"},
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


# ============================================================
# EXPANDED ESPN DATA EXTRACTION (from summary endpoint)
# ============================================================

async def get_espn_odds(sport: str, event_id: str) -> Dict[str, Any]:
    """
    Extract betting odds from ESPN game summary.

    ESPN includes odds data in the summary endpoint from various books.
    This provides secondary validation against our primary Odds API.

    Args:
        sport: Sport code (NBA, NFL, MLB, NHL, NCAAB)
        event_id: ESPN event ID

    Returns:
        Odds data with spread, moneyline, total
    """
    details = await get_game_details(sport, event_id)

    if "error" in details:
        return {"available": False, "error": details["error"]}

    try:
        # ESPN stores odds in pickcenter or odds sections
        odds_data = details.get("pickcenter", [])
        if not odds_data:
            odds_data = details.get("odds", [])

        if not odds_data:
            return {"available": False, "reason": "NO_ODDS_DATA"}

        # Parse the first odds provider (usually consensus)
        primary_odds = odds_data[0] if odds_data else {}

        result = {
            "available": True,
            "source": "espn_summary",
            "event_id": event_id,
            "spread": None,
            "spread_odds": None,
            "total": None,
            "over_odds": None,
            "under_odds": None,
            "home_ml": None,
            "away_ml": None,
            "provider": primary_odds.get("provider", {}).get("name", "ESPN"),
        }

        # Extract spread
        if "spread" in primary_odds:
            result["spread"] = primary_odds.get("spread")
            result["spread_odds"] = primary_odds.get("spreadOdds")

        # Extract total (over/under)
        if "overUnder" in primary_odds:
            result["total"] = primary_odds.get("overUnder")
            result["over_odds"] = primary_odds.get("overOdds")
            result["under_odds"] = primary_odds.get("underOdds")

        # Extract moneylines
        if "homeTeamOdds" in primary_odds:
            home_odds = primary_odds.get("homeTeamOdds", {})
            result["home_ml"] = home_odds.get("moneyLine")
        if "awayTeamOdds" in primary_odds:
            away_odds = primary_odds.get("awayTeamOdds", {})
            result["away_ml"] = away_odds.get("moneyLine")

        # Also check for detailed odds array
        for odds_item in odds_data:
            if odds_item.get("details"):
                for detail in odds_item.get("details", []):
                    if detail.get("type") == "spread" and not result["spread"]:
                        result["spread"] = detail.get("value")
                    elif detail.get("type") == "total" and not result["total"]:
                        result["total"] = detail.get("value")

        return result

    except Exception as e:
        logger.error("ESPN odds extraction error: %s", e)
        return {"available": False, "error": str(e)}


async def get_espn_injuries(sport: str, event_id: str = None, team_abbrev: str = None) -> Dict[str, Any]:
    """
    Get injuries from ESPN.

    Can fetch from game summary (if event_id provided) or team endpoint.

    Args:
        sport: Sport code
        event_id: Optional ESPN event ID for game-specific injuries
        team_abbrev: Optional team abbreviation for team injuries

    Returns:
        Injuries list with player names, status, and details
    """
    mapping = SPORT_MAPPING.get(sport.upper())
    if not mapping:
        return {"available": False, "error": f"Unknown sport: {sport}"}

    injuries = []

    # Try game summary first if event_id provided
    if event_id:
        details = await get_game_details(sport, event_id)
        if "error" not in details:
            # Check for injuries in game info
            game_info = details.get("gameInfo", {})
            for team_key in ["homeTeam", "awayTeam"]:
                team_data = game_info.get(team_key, {})
                team_injuries = team_data.get("injuries", [])
                for inj in team_injuries:
                    injuries.append({
                        "player": inj.get("athlete", {}).get("displayName", "Unknown"),
                        "team": team_data.get("team", {}).get("abbreviation", ""),
                        "status": inj.get("status", "Unknown"),
                        "type": inj.get("type", {}).get("text", ""),
                        "detail": inj.get("details", {}).get("detail", ""),
                    })

            # Also check boxscore for injury designations
            boxscore = details.get("boxscore", {})
            for player_section in boxscore.get("players", []):
                for stat_section in player_section.get("statistics", []):
                    for athlete in stat_section.get("athletes", []):
                        if athlete.get("didNotPlay") or athlete.get("ejected"):
                            injuries.append({
                                "player": athlete.get("athlete", {}).get("displayName", "Unknown"),
                                "team": player_section.get("team", {}).get("abbreviation", ""),
                                "status": "OUT" if athlete.get("didNotPlay") else "EJECTED",
                                "type": "DNP",
                                "detail": athlete.get("reason", ""),
                            })

    # Try team injuries endpoint
    if team_abbrev and not injuries:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{mapping['sport']}/{mapping['league']}/teams/{team_abbrev}"

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    team_data = resp.json()
                    team_injuries = team_data.get("team", {}).get("injuries", [])
                    for inj in team_injuries:
                        injuries.append({
                            "player": inj.get("athlete", {}).get("displayName", "Unknown"),
                            "team": team_abbrev,
                            "status": inj.get("status", "Unknown"),
                            "type": inj.get("type", {}).get("text", ""),
                            "detail": inj.get("details", {}).get("detail", ""),
                        })
        except Exception as e:
            logger.debug("ESPN team injuries fetch failed: %s", e)

    return {
        "available": len(injuries) > 0,
        "source": "espn",
        "count": len(injuries),
        "injuries": injuries
    }


async def get_espn_player_stats(sport: str, event_id: str) -> Dict[str, Any]:
    """
    Get player statistics from ESPN game summary.

    Useful for recent performance context on props.

    Args:
        sport: Sport code
        event_id: ESPN event ID

    Returns:
        Player stats organized by team
    """
    details = await get_game_details(sport, event_id)

    if "error" in details:
        return {"available": False, "error": details["error"]}

    try:
        boxscore = details.get("boxscore", {})
        players_data = boxscore.get("players", [])

        result = {
            "available": len(players_data) > 0,
            "source": "espn_boxscore",
            "event_id": event_id,
            "teams": []
        }

        for team_section in players_data:
            team_info = team_section.get("team", {})
            team_stats = {
                "team": team_info.get("displayName", "Unknown"),
                "abbreviation": team_info.get("abbreviation", ""),
                "players": []
            }

            for stat_section in team_section.get("statistics", []):
                stat_keys = stat_section.get("keys", [])
                stat_labels = stat_section.get("labels", [])

                for athlete in stat_section.get("athletes", []):
                    player_info = athlete.get("athlete", {})
                    stats_values = athlete.get("stats", [])

                    player_stats = {
                        "name": player_info.get("displayName", "Unknown"),
                        "id": player_info.get("id", ""),
                        "position": player_info.get("position", {}).get("abbreviation", ""),
                        "starter": athlete.get("starter", False),
                        "stats": {}
                    }

                    # Map stats to keys
                    for i, key in enumerate(stat_keys):
                        if i < len(stats_values):
                            player_stats["stats"][key] = stats_values[i]

                    team_stats["players"].append(player_stats)

            result["teams"].append(team_stats)

        return result

    except Exception as e:
        logger.error("ESPN player stats extraction error: %s", e)
        return {"available": False, "error": str(e)}


async def get_espn_venue_info(sport: str, event_id: str) -> Dict[str, Any]:
    """
    Get venue information from ESPN game summary.

    Useful for outdoor sports (weather impact) and home court advantage.

    Args:
        sport: Sport code
        event_id: ESPN event ID

    Returns:
        Venue data with name, location, capacity, weather if outdoor
    """
    details = await get_game_details(sport, event_id)

    if "error" in details:
        return {"available": False, "error": details["error"]}

    try:
        game_info = details.get("gameInfo", {})
        venue = game_info.get("venue", {})
        weather = game_info.get("weather", {})

        result = {
            "available": bool(venue),
            "source": "espn_summary",
            "event_id": event_id,
            "venue": {
                "name": venue.get("fullName", venue.get("shortName", "Unknown")),
                "city": venue.get("address", {}).get("city", ""),
                "state": venue.get("address", {}).get("state", ""),
                "capacity": venue.get("capacity"),
                "indoor": venue.get("indoor", True),  # Default to indoor
                "grass": venue.get("grass", False),
            }
        }

        # Add weather for outdoor venues
        if weather or not result["venue"]["indoor"]:
            result["weather"] = {
                "temperature": weather.get("temperature"),
                "condition": weather.get("displayValue", weather.get("conditionId", "")),
                "humidity": weather.get("humidity"),
                "wind_speed": weather.get("windSpeed"),
                "wind_direction": weather.get("windDirection"),
            }

        # Add attendance if available
        if game_info.get("attendance"):
            result["attendance"] = game_info.get("attendance")

        return result

    except Exception as e:
        logger.error("ESPN venue info extraction error: %s", e)
        return {"available": False, "error": str(e)}


async def get_game_summary_enriched(
    sport: str,
    home_team: str,
    away_team: str,
    date: str = None
) -> Dict[str, Any]:
    """
    Get comprehensive game data from ESPN in a single call.

    Combines: officials, odds, injuries, venue into one response.

    Args:
        sport: Sport code
        home_team: Home team name
        away_team: Away team name
        date: Optional date in YYYY-MM-DD format

    Returns:
        Enriched game data with all available ESPN information
    """
    # Find event ID
    event_id = await get_espn_event_id(sport, home_team, away_team, date)

    if not event_id:
        return {
            "available": False,
            "reason": "GAME_NOT_FOUND",
            "message": f"Could not find ESPN event for {away_team} @ {home_team}"
        }

    # Fetch all data in parallel
    officials_task = get_officials_for_event(sport, event_id)
    odds_task = get_espn_odds(sport, event_id)
    injuries_task = get_espn_injuries(sport, event_id)
    venue_task = get_espn_venue_info(sport, event_id)

    officials, odds, injuries, venue = await asyncio.gather(
        officials_task, odds_task, injuries_task, venue_task,
        return_exceptions=True
    )

    # Handle any exceptions from gather
    if isinstance(officials, Exception):
        officials = {"available": False, "error": str(officials)}
    if isinstance(odds, Exception):
        odds = {"available": False, "error": str(odds)}
    if isinstance(injuries, Exception):
        injuries = {"available": False, "error": str(injuries)}
    if isinstance(venue, Exception):
        venue = {"available": False, "error": str(venue)}

    return {
        "available": True,
        "source": "espn_enriched",
        "event_id": event_id,
        "matchup": f"{away_team} @ {home_team}",
        "officials": officials,
        "odds": odds,
        "injuries": injuries,
        "venue": venue,
    }


async def get_all_games_enriched(sport: str, date: str = None) -> List[Dict[str, Any]]:
    """
    Get enriched data for all games in a sport on a given date.

    Args:
        sport: Sport code
        date: Optional date in YYYY-MM-DD format

    Returns:
        List of enriched game data
    """
    games = await get_todays_games(sport) if not date else []

    if date:
        scoreboard = await get_espn_scoreboard(sport, date)
        events = scoreboard.get("events", [])
        for event in events:
            comp = event.get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])
            home = away = None
            for c in competitors:
                if c.get("homeAway") == "home":
                    home = c.get("team", {}).get("displayName")
                else:
                    away = c.get("team", {}).get("displayName")
            if home and away:
                games.append({
                    "id": event.get("id"),
                    "home_team": home,
                    "away_team": away
                })

    # Fetch enriched data for all games in parallel
    tasks = []
    for game in games:
        tasks.append(get_game_summary_enriched(
            sport,
            game["home_team"],
            game["away_team"],
            date
        ))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    enriched_games = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            enriched_games.append({
                "available": False,
                "error": str(result),
                "matchup": f"{games[i]['away_team']} @ {games[i]['home_team']}"
            })
        else:
            enriched_games.append(result)

    return enriched_games
