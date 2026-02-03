"""
BallDontLie API Integration - NBA Live Context Data
====================================================
v1.0 - January 2026

Provides NBA-specific live game data:
- Live game status / game clock / quarter
- Player availability / starters (if supported)
- Team stats pace proxy, foul trouble flags
- Props context

FEATURE FLAGGED: Only activates if BDL_API_KEY is set.
System continues to work normally without this API.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, date

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

logger = logging.getLogger("balldontlie")

# =============================================================================
# CONFIGURATION
# =============================================================================

# BallDontLie API Key - REQUIRED (no hardcoding)
# Set BALLDONTLIE_API_KEY or BDL_API_KEY in environment
BDL_API_KEY = os.getenv("BALLDONTLIE_API_KEY", os.getenv("BDL_API_KEY", ""))
BDL_BASE_URL = "https://api.balldontlie.io/v1"

# Feature flag - only enabled if API key is set in environment
BDL_ENABLED = bool(BDL_API_KEY and BDL_API_KEY not in ("", "your_key_here", "your_balldontlie_api_key_here"))


# Cache for API responses (in-memory, short TTL)
_cache: Dict[str, Any] = {}
_cache_timestamps: Dict[str, datetime] = {}
CACHE_TTL_SECONDS = 120  # 2 minutes


def is_balldontlie_configured() -> bool:
    """Check if BallDontLie API is configured and enabled."""
    return BDL_ENABLED


def get_balldontlie_status() -> Dict[str, Any]:
    """Get BallDontLie integration status."""
    return {
        "configured": BDL_ENABLED,
        "api_key_set": bool(BDL_API_KEY),
        "features": [
            "live_game_status",
            "game_clock_quarter",
            "player_availability",
            "team_pace_stats",
            "foul_trouble_detection",
        ] if BDL_ENABLED else [],
        "note": "Set BDL_API_KEY env var to enable" if not BDL_ENABLED else "Active",
    }


# =============================================================================
# HTTP HELPERS
# =============================================================================

async def _fetch_bdl(endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict]:
    """
    Fetch data from BallDontLie API.

    Returns None if API is not configured or request fails.
    """
    if not BDL_ENABLED:
        return None

    if not HTTPX_AVAILABLE:
        logger.warning("httpx not available for BallDontLie API calls")
        return None

    # Check cache
    cache_key = f"{endpoint}:{str(params)}"
    if cache_key in _cache:
        cached_at = _cache_timestamps.get(cache_key)
        if cached_at and (datetime.now() - cached_at).total_seconds() < CACHE_TTL_SECONDS:
            return _cache[cache_key]

    url = f"{BDL_BASE_URL}{endpoint}"
    headers = {
        "Authorization": BDL_API_KEY,
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params=params)

            if resp.status_code == 200:
                data = resp.json()
                _cache[cache_key] = data
                _cache_timestamps[cache_key] = datetime.now()
                try:
                    from integration_registry import mark_integration_used
                    mark_integration_used("balldontlie")
                except Exception:
                    pass
                return data
            elif resp.status_code == 401:
                logger.warning("BallDontLie API: Invalid API key")
                return None
            elif resp.status_code == 429:
                logger.warning("BallDontLie API: Rate limited")
                return None
            else:
                logger.warning(f"BallDontLie API: HTTP {resp.status_code}")
                return None

    except Exception as e:
        logger.warning(f"BallDontLie API error: {e}")
        return None


# =============================================================================
# LIVE GAME DATA
# =============================================================================

async def get_live_games() -> List[Dict[str, Any]]:
    """
    Get currently live NBA games.

    Returns list of games with:
    - game_id
    - status (in_progress, final, scheduled)
    - quarter
    - time_remaining
    - home_team, away_team
    - home_score, away_score
    """
    if not BDL_ENABLED:
        return []

    today = date.today().isoformat()

    data = await _fetch_bdl("/games", {"dates[]": today})
    if not data:
        return []

    games = data.get("data", [])
    live_games = []

    for game in games:
        status = game.get("status", "").lower()

        game_data = {
            "game_id": game.get("id"),
            "bdl_game_id": game.get("id"),
            "status": status,
            "period": game.get("period", 0),
            "time": game.get("time", ""),
            "home_team": game.get("home_team", {}).get("abbreviation", ""),
            "home_team_full": game.get("home_team", {}).get("full_name", ""),
            "away_team": game.get("visitor_team", {}).get("abbreviation", ""),
            "away_team_full": game.get("visitor_team", {}).get("full_name", ""),
            "home_score": game.get("home_team_score", 0),
            "away_score": game.get("visitor_team_score", 0),
            "is_live": status in ["in progress", "halftime"],
            "is_final": status == "final",
        }

        # Determine live window for triggering
        if game_data["is_live"]:
            period = game_data["period"]
            time_str = game_data["time"]

            # Parse time remaining
            minutes_remaining = 0
            if ":" in time_str:
                try:
                    mins, secs = time_str.split(":")
                    minutes_remaining = int(mins) + int(secs) / 60
                except:
                    pass

            # Determine trigger window
            game_data["live_quarter"] = period
            game_data["live_time_remaining"] = time_str
            game_data["trigger_window"] = _get_trigger_window(period, minutes_remaining)

        live_games.append(game_data)

    return live_games


def _get_trigger_window(quarter: int, minutes_remaining: float) -> Optional[str]:
    """
    Determine if game is in a valid live betting trigger window.

    Trigger windows:
    - halftime (Q2 end → start Q3)
    - Q4 10:00 → 0:00
    - overtime
    """
    if quarter == 2 and minutes_remaining <= 0:
        return "HALFTIME"
    if quarter == 3 and minutes_remaining >= 10:
        return "HALFTIME"  # Start of Q3
    if quarter == 4:
        return "LATE_GAME_Q4"
    if quarter >= 5:
        return "OVERTIME"
    return None


async def get_game_details(game_id: int) -> Optional[Dict[str, Any]]:
    """
    Get detailed game information including box score.
    """
    if not BDL_ENABLED:
        return None

    data = await _fetch_bdl(f"/games/{game_id}")
    if not data:
        return None

    return data.get("data", data)


# =============================================================================
# PLAYER DATA
# =============================================================================

async def get_player_stats_for_game(game_id: int) -> List[Dict[str, Any]]:
    """
    Get player stats for a specific game (box score).

    Useful for detecting foul trouble, minutes load, etc.
    """
    if not BDL_ENABLED:
        return []

    data = await _fetch_bdl("/stats", {"game_ids[]": game_id})
    if not data:
        return []

    stats = data.get("data", [])

    player_stats = []
    for stat in stats:
        player = stat.get("player", {})
        player_stats.append({
            "player_id": player.get("id"),
            "player_name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
            "team": stat.get("team", {}).get("abbreviation", ""),
            "minutes": stat.get("min", "0:00"),
            "points": stat.get("pts", 0),
            "rebounds": stat.get("reb", 0),
            "assists": stat.get("ast", 0),
            "steals": stat.get("stl", 0),
            "blocks": stat.get("blk", 0),
            "turnovers": stat.get("turnover", 0),
            "fouls": stat.get("pf", 0),
            "fgm": stat.get("fgm", 0),
            "fga": stat.get("fga", 0),
            "fg3m": stat.get("fg3m", 0),
            "fg3a": stat.get("fg3a", 0),
            "ftm": stat.get("ftm", 0),
            "fta": stat.get("fta", 0),
        })

    return player_stats


async def check_foul_trouble(game_id: int) -> Dict[str, List[str]]:
    """
    Check for players in foul trouble (4+ fouls).

    Returns dict with home and away team lists.
    """
    stats = await get_player_stats_for_game(game_id)

    foul_trouble = {"home": [], "away": []}

    for player in stats:
        if player.get("fouls", 0) >= 4:
            # Would need game context to determine home/away
            # For now just return all players in trouble
            foul_trouble["home"].append(f"{player['player_name']} ({player['fouls']} fouls)")

    return foul_trouble


# =============================================================================
# TEAM PACE STATS
# =============================================================================

async def get_team_season_stats(team_id: int = None, season: int = None) -> Dict[str, Any]:
    """
    Get team season statistics for pace estimation.

    Note: BallDontLie free tier may not have advanced stats.
    This provides basic stats that can be used as pace proxies.
    """
    if not BDL_ENABLED:
        return {}

    if season is None:
        season = datetime.now().year if datetime.now().month >= 10 else datetime.now().year - 1

    # Would need team games to calculate pace
    # This is a simplified version
    return {
        "team_id": team_id,
        "season": season,
        "pace_estimate": "unavailable",  # Placeholder
        "note": "Full pace stats require game-by-game analysis",
    }


# =============================================================================
# COMBINED LIVE CONTEXT
# =============================================================================

async def get_nba_live_context(home_team: str = None, away_team: str = None) -> Dict[str, Any]:
    """
    Get combined live context for NBA games.

    This is the main entry point for live pick generation.

    Returns:
    - live_games: List of live games matching teams (if provided)
    - trigger_windows: Which games are in valid trigger windows
    - foul_trouble_flags: Players in foul trouble
    """
    if not BDL_ENABLED:
        return {
            "available": False,
            "reason": "BallDontLie API not configured",
            "suggestion": "Set BDL_API_KEY environment variable",
        }

    try:
        live_games = await get_live_games()

        # Filter by teams if provided
        matching_games = live_games
        if home_team or away_team:
            matching_games = [
                g for g in live_games
                if (not home_team or home_team.upper() in g.get("home_team", "").upper() or
                    home_team.upper() in g.get("home_team_full", "").upper())
                and (not away_team or away_team.upper() in g.get("away_team", "").upper() or
                     away_team.upper() in g.get("away_team_full", "").upper())
            ]

        # Get games in trigger windows
        trigger_games = [g for g in matching_games if g.get("trigger_window")]

        return {
            "available": True,
            "live_games_count": len(live_games),
            "matching_games_count": len(matching_games),
            "games_in_trigger_window": len(trigger_games),
            "live_games": matching_games,
            "trigger_games": trigger_games,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.exception(f"Error getting NBA live context: {e}")
        return {
            "available": False,
            "reason": str(e),
        }


# =============================================================================
# PLAYER LOOKUP & GRADING (GOAT Features)
# =============================================================================

async def search_player(name: str) -> Optional[Dict[str, Any]]:
    """
    Search for a player by name.

    Returns the best matching player with full details.
    """
    if not BDL_ENABLED:
        return None

    data = await _fetch_bdl("/players", {"search": name})
    if not data:
        return None

    players = data.get("data", [])
    if not players:
        return None

    # Return first (best) match
    player = players[0]
    return {
        "id": player.get("id"),
        "first_name": player.get("first_name", ""),
        "last_name": player.get("last_name", ""),
        "full_name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
        "position": player.get("position", ""),
        "team": player.get("team", {}).get("full_name", ""),
        "team_abbreviation": player.get("team", {}).get("abbreviation", ""),
        "team_id": player.get("team", {}).get("id"),
    }


async def get_player_by_id(player_id: int) -> Optional[Dict[str, Any]]:
    """
    Get player details by BallDontLie ID.
    """
    if not BDL_ENABLED:
        return None

    data = await _fetch_bdl(f"/players/{player_id}")
    if not data:
        return None

    player = data.get("data", data)
    return {
        "id": player.get("id"),
        "first_name": player.get("first_name", ""),
        "last_name": player.get("last_name", ""),
        "full_name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
        "position": player.get("position", ""),
        "team": player.get("team", {}).get("full_name", ""),
        "team_abbreviation": player.get("team", {}).get("abbreviation", ""),
    }


async def get_player_season_averages(
    player_id: int,
    season: int = None
) -> Optional[Dict[str, Any]]:
    """
    Get player's season averages for a given season.

    GOAT tier feature - includes advanced stats.
    """
    if not BDL_ENABLED:
        return None

    if season is None:
        # Current season
        now = datetime.now()
        season = now.year if now.month >= 10 else now.year - 1

    data = await _fetch_bdl("/season_averages", {
        "player_ids[]": player_id,
        "season": season
    })

    if not data:
        return None

    averages = data.get("data", [])
    if not averages:
        return None

    avg = averages[0]
    return {
        "player_id": player_id,
        "season": season,
        "games_played": avg.get("games_played", 0),
        "minutes": avg.get("min", "0"),
        "points": avg.get("pts", 0.0),
        "rebounds": avg.get("reb", 0.0),
        "assists": avg.get("ast", 0.0),
        "steals": avg.get("stl", 0.0),
        "blocks": avg.get("blk", 0.0),
        "turnovers": avg.get("turnover", 0.0),
        "fg_pct": avg.get("fg_pct", 0.0),
        "fg3_pct": avg.get("fg3_pct", 0.0),
        "ft_pct": avg.get("ft_pct", 0.0),
        "fg3m": avg.get("fg3m", 0.0),
        "fgm": avg.get("fgm", 0.0),
        "fga": avg.get("fga", 0.0),
        "ftm": avg.get("ftm", 0.0),
        "fta": avg.get("fta", 0.0),
        # Calculated combo stats
        "pra": avg.get("pts", 0.0) + avg.get("reb", 0.0) + avg.get("ast", 0.0),
        "pr": avg.get("pts", 0.0) + avg.get("reb", 0.0),
        "pa": avg.get("pts", 0.0) + avg.get("ast", 0.0),
        "ra": avg.get("reb", 0.0) + avg.get("ast", 0.0),
    }


async def get_player_game_stats(
    player_id: int = None,
    player_name: str = None,
    game_date: str = None,
    game_id: int = None
) -> Optional[Dict[str, Any]]:
    """
    Get player's stats for a specific game.

    This is the PRIMARY function for grading NBA player props.

    Args:
        player_id: BallDontLie player ID (preferred)
        player_name: Player name for lookup if no ID
        game_date: Date in YYYY-MM-DD format
        game_id: Specific BallDontLie game ID

    Returns:
        Player's box score stats for the game
    """
    if not BDL_ENABLED:
        return None

    # If we only have player name, look up the ID
    if not player_id and player_name:
        player = await search_player(player_name)
        if player:
            player_id = player.get("id")
        else:
            logger.warning(f"Could not find player: {player_name}")
            return None

    if not player_id:
        return None

    # Build params
    params = {"player_ids[]": player_id}

    if game_id:
        params["game_ids[]"] = game_id
    elif game_date:
        params["dates[]"] = game_date

    data = await _fetch_bdl("/stats", params)
    if not data:
        return None

    stats = data.get("data", [])
    if not stats:
        return None

    # Get the most recent game stats (should be only one if game specified)
    stat = stats[0]
    player_data = stat.get("player", {})
    game_data = stat.get("game", {})

    return {
        "player_id": player_data.get("id"),
        "player_name": f"{player_data.get('first_name', '')} {player_data.get('last_name', '')}".strip(),
        "team": stat.get("team", {}).get("abbreviation", ""),
        "game_id": game_data.get("id"),
        "game_date": game_data.get("date", ""),
        "minutes": stat.get("min", "0:00"),
        # Core stats
        "points": stat.get("pts", 0),
        "rebounds": stat.get("reb", 0),
        "assists": stat.get("ast", 0),
        "steals": stat.get("stl", 0),
        "blocks": stat.get("blk", 0),
        "turnovers": stat.get("turnover", 0),
        "fouls": stat.get("pf", 0),
        # Shooting
        "fgm": stat.get("fgm", 0),
        "fga": stat.get("fga", 0),
        "fg3m": stat.get("fg3m", 0),
        "fg3a": stat.get("fg3a", 0),
        "ftm": stat.get("ftm", 0),
        "fta": stat.get("fta", 0),
        # Aliases for prop grading
        "three_pointers_made": stat.get("fg3m", 0),
        "three_pointers": stat.get("fg3m", 0),
        "threes": stat.get("fg3m", 0),
        # Combo stats (calculated)
        "pra": stat.get("pts", 0) + stat.get("reb", 0) + stat.get("ast", 0),
        "pr": stat.get("pts", 0) + stat.get("reb", 0),
        "pa": stat.get("pts", 0) + stat.get("ast", 0),
        "ra": stat.get("reb", 0) + stat.get("ast", 0),
        "pts_reb": stat.get("pts", 0) + stat.get("reb", 0),
        "pts_ast": stat.get("pts", 0) + stat.get("ast", 0),
        "reb_ast": stat.get("reb", 0) + stat.get("ast", 0),
        "pts_reb_ast": stat.get("pts", 0) + stat.get("reb", 0) + stat.get("ast", 0),
    }


async def get_box_score(game_id: int) -> Optional[Dict[str, Any]]:
    """
    Get full box score for a game.

    Returns all player stats for both teams.
    """
    if not BDL_ENABLED:
        return None

    # Get game details first
    game = await get_game_details(game_id)
    if not game:
        return None

    # Get all player stats for the game
    stats = await get_player_stats_for_game(game_id)

    home_team = game.get("home_team", {}).get("abbreviation", "")
    away_team = game.get("visitor_team", {}).get("abbreviation", "")

    home_players = [s for s in stats if s.get("team") == home_team]
    away_players = [s for s in stats if s.get("team") == away_team]

    return {
        "game_id": game_id,
        "date": game.get("date", ""),
        "status": game.get("status", ""),
        "home_team": home_team,
        "away_team": away_team,
        "home_score": game.get("home_team_score", 0),
        "away_score": game.get("visitor_team_score", 0),
        "home_players": home_players,
        "away_players": away_players,
        "all_players": stats,
    }


async def get_games_by_date(game_date: str) -> List[Dict[str, Any]]:
    """
    Get all NBA games for a specific date.

    Args:
        game_date: Date in YYYY-MM-DD format

    Returns:
        List of games with scores and status
    """
    if not BDL_ENABLED:
        return []

    data = await _fetch_bdl("/games", {"dates[]": game_date})
    if not data:
        return []

    games = data.get("data", [])
    result = []

    for game in games:
        result.append({
            "game_id": game.get("id"),
            "date": game.get("date", ""),
            "status": game.get("status", ""),
            "home_team": game.get("home_team", {}).get("abbreviation", ""),
            "home_team_full": game.get("home_team", {}).get("full_name", ""),
            "away_team": game.get("visitor_team", {}).get("abbreviation", ""),
            "away_team_full": game.get("visitor_team", {}).get("full_name", ""),
            "home_score": game.get("home_team_score", 0),
            "away_score": game.get("visitor_team_score", 0),
            "is_final": game.get("status", "").lower() == "final",
        })

    return result


# =============================================================================
# PROP GRADING HELPER
# =============================================================================

async def grade_nba_prop(
    player_name: str,
    prop_type: str,
    line: float,
    side: str,  # "Over" or "Under"
    game_date: str = None,
    player_id: int = None
) -> Optional[Dict[str, Any]]:
    """
    Grade an NBA player prop.

    This is the main function for auto-grading NBA props.

    Returns:
        {
            "actual_value": float,
            "line": float,
            "side": str,
            "result": "WIN" | "LOSS" | "PUSH",
            "margin": float,  # actual - line
            "player_stats": dict  # full box score
        }
    """
    stats = await get_player_game_stats(
        player_id=player_id,
        player_name=player_name,
        game_date=game_date
    )

    if not stats:
        return None

    # Map prop type to stat field
    prop_map = {
        "points": "points",
        "pts": "points",
        "rebounds": "rebounds",
        "reb": "rebounds",
        "assists": "assists",
        "ast": "assists",
        "steals": "steals",
        "stl": "steals",
        "blocks": "blocks",
        "blk": "blocks",
        "turnovers": "turnovers",
        "to": "turnovers",
        "three_pointers_made": "three_pointers_made",
        "threes": "three_pointers_made",
        "3pm": "three_pointers_made",
        "three_pointers": "three_pointers_made",
        "pra": "pra",
        "pts_reb_ast": "pra",
        "points_rebounds_assists": "pra",
        "pr": "pr",
        "pts_reb": "pr",
        "points_rebounds": "pr",
        "pa": "pa",
        "pts_ast": "pa",
        "points_assists": "pa",
        "ra": "ra",
        "reb_ast": "ra",
        "rebounds_assists": "ra",
    }

    stat_key = prop_map.get(prop_type.lower())
    if not stat_key:
        logger.warning(f"Unknown prop type: {prop_type}")
        return None

    actual_value = stats.get(stat_key, 0)
    margin = actual_value - line

    # Determine result
    if side.lower() == "over":
        if actual_value > line:
            result = "WIN"
        elif actual_value < line:
            result = "LOSS"
        else:
            result = "PUSH"
    else:  # Under
        if actual_value < line:
            result = "WIN"
        elif actual_value > line:
            result = "LOSS"
        else:
            result = "PUSH"

    return {
        "actual_value": actual_value,
        "line": line,
        "side": side,
        "result": result,
        "margin": margin,
        "prop_type": prop_type,
        "player_name": stats.get("player_name", player_name),
        "player_stats": stats,
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "is_balldontlie_configured",
    "get_balldontlie_status",
    "get_live_games",
    "get_game_details",
    "get_player_stats_for_game",
    "check_foul_trouble",
    "get_team_season_stats",
    "get_nba_live_context",
    # GOAT tier additions
    "search_player",
    "get_player_by_id",
    "get_player_season_averages",
    "get_player_game_stats",
    "get_box_score",
    "get_games_by_date",
    "grade_nba_prop",
    "BDL_API_KEY",
]
