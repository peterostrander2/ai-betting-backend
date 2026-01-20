"""
v10.31 Grading Engine - Daily Settlement for Pick Ledger

Responsibilities:
1. Fetch pending picks for a date
2. Fetch results from multiple APIs:
   - Odds API (game scores) - PRIMARY for game picks
   - ESPN API (box scores) - FREE for player stats
   - BallDontLie API (NBA stats) - FREE backup for NBA
   - Playbook API (fallback) - paid API
3. Grade picks (WIN/LOSS/PUSH/VOID) and calculate profit_units
4. Update pick ledger with results

Conservative approach:
- If results provider not available, mark as MISSING (not graded)
- Only grade picks where we have confirmed outcomes
"""
import os
import logging
import httpx
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

from database import (
    PickLedger, PickResult, get_db,
    get_pending_picks_for_date, update_pick_result
)

logger = logging.getLogger(__name__)

# ============================================================================
# API CONFIGURATION
# ============================================================================

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE = os.getenv("ODDS_API_BASE", "https://api.the-odds-api.com/v4")
PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "")
PLAYBOOK_API_BASE = os.getenv("PLAYBOOK_API_BASE", "https://api.playbook-api.com/v1")

# FREE APIs
ESPN_API_BASE = "https://site.api.espn.com/apis/site/v2/sports"
BALLDONTLIE_API_BASE = "https://api.balldontlie.io/v1"
BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE_API_KEY", "")  # Optional, increases rate limit

# Sport key mapping for Odds API
ODDS_API_SPORT_KEYS = {
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "MLB": "baseball_mlb",
    "NHL": "icehockey_nhl",
    "NCAAB": "basketball_ncaab",
    "NCAAF": "americanfootball_ncaaf"
}

# ESPN sport paths
ESPN_SPORT_PATHS = {
    "NBA": "basketball/nba",
    "NFL": "football/nfl",
    "MLB": "baseball/mlb",
    "NHL": "hockey/nhl",
    "NCAAB": "basketball/mens-college-basketball"
}

# Playbook API league codes
PLAYBOOK_LEAGUES = {
    "NBA": "NBA",
    "NFL": "NFL",
    "MLB": "MLB",
    "NHL": "NHL",
    "NCAAB": "CBB"
}

# Cache for API results (cleared per grading run)
_scores_cache: Dict[str, List[Dict]] = {}
_player_stats_cache: Dict[str, Dict] = {}
_espn_box_scores_cache: Dict[str, Dict] = {}


# ============================================================================
# PROFIT CALCULATION
# ============================================================================

def calculate_profit(odds: int, units: float, result: PickResult) -> float:
    """
    Calculate profit/loss in units based on American odds.

    Args:
        odds: American odds (e.g., -110, +150)
        units: Units wagered
        result: WIN, LOSS, PUSH, etc.

    Returns:
        Profit in units (positive for win, negative for loss, 0 for push/void)
    """
    if units <= 0:
        return 0.0

    if result == PickResult.WIN:
        if odds > 0:
            return units * (odds / 100)
        else:
            return units * (100 / abs(odds))
    elif result == PickResult.LOSS:
        return -units
    else:
        # PUSH, VOID, MISSING, PENDING
        return 0.0


# ============================================================================
# ODDS API - GAME SCORES
# ============================================================================

async def fetch_odds_api_scores(sport: str, days_from: int = 3) -> List[Dict[str, Any]]:
    """
    Fetch completed game scores from Odds API.

    Endpoint: GET /v4/sports/{sport}/scores
    Docs: https://the-odds-api.com/liveapi/guides/v4/#get-scores

    Args:
        sport: Internal sport code (NBA, NFL, etc.)
        days_from: Number of days back to fetch (1-3)

    Returns:
        List of completed games with scores
    """
    cache_key = f"odds_{sport}_{days_from}"
    if cache_key in _scores_cache:
        return _scores_cache[cache_key]

    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not configured - cannot fetch scores")
        return []

    sport_key = ODDS_API_SPORT_KEYS.get(sport.upper())
    if not sport_key:
        logger.warning(f"Unknown sport for Odds API: {sport}")
        return []

    url = f"{ODDS_API_BASE}/sports/{sport_key}/scores"
    params = {
        "apiKey": ODDS_API_KEY,
        "daysFrom": min(days_from, 3)
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)

            if resp.status_code == 401:
                logger.error("Odds API: Invalid API key")
                return []
            elif resp.status_code == 429:
                logger.warning("Odds API: Rate limited")
                return []
            elif resp.status_code != 200:
                logger.error(f"Odds API scores error: {resp.status_code}")
                return []

            data = resp.json()

            # Filter to completed games only
            completed = [
                game for game in data
                if game.get("completed", False)
            ]

            logger.info(f"Odds API: Fetched {len(completed)} completed {sport} games")
            _scores_cache[cache_key] = completed
            return completed

    except httpx.RequestError as e:
        logger.exception(f"Odds API request failed: {e}")
        return []
    except Exception as e:
        logger.exception(f"Odds API unexpected error: {e}")
        return []


def match_game_to_pick(
    pick: PickLedger,
    games: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Match a pick to a game result from Odds API.

    Matching priority:
    1. event_id exact match (if available)
    2. Team name matching (home_team/away_team)

    Returns:
        Game result dict or None if no match
    """
    # Try event_id match first
    if pick.event_id:
        for game in games:
            if game.get("id") == pick.event_id:
                return _parse_odds_api_game(game)

    # Fallback to team name matching
    pick_home = (pick.home_team or "").lower().strip()
    pick_away = (pick.away_team or "").lower().strip()

    if not pick_home and not pick_away:
        # Try to extract from matchup string
        matchup = pick.matchup or ""
        if " @ " in matchup:
            parts = matchup.split(" @ ")
            pick_away = parts[0].lower().strip()
            pick_home = parts[1].lower().strip()
        elif " vs " in matchup.lower():
            parts = matchup.lower().split(" vs ")
            pick_home = parts[0].strip()
            pick_away = parts[1].strip()

    for game in games:
        game_home = (game.get("home_team") or "").lower()
        game_away = (game.get("away_team") or "").lower()

        # Fuzzy match: check if team names are substrings
        home_match = (
            pick_home in game_home or
            game_home in pick_home or
            any(word in game_home for word in pick_home.split() if len(word) > 3)
        )
        away_match = (
            pick_away in game_away or
            game_away in pick_away or
            any(word in game_away for word in pick_away.split() if len(word) > 3)
        )

        if home_match and away_match:
            return _parse_odds_api_game(game)

    return None


def _parse_odds_api_game(game: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Odds API game response into standardized format."""
    scores = game.get("scores", [])
    home_score = None
    away_score = None
    game_home = (game.get("home_team") or "").lower()
    game_away = (game.get("away_team") or "").lower()

    for score_entry in scores:
        team_name = (score_entry.get("name") or "").lower()
        score = score_entry.get("score")
        if score is not None:
            try:
                score = int(score)
            except (ValueError, TypeError):
                continue

            if team_name in game_home or game_home in team_name:
                home_score = score
            elif team_name in game_away or game_away in team_name:
                away_score = score

    winner = None
    if home_score is not None and away_score is not None:
        winner = game.get("home_team") if home_score > away_score else game.get("away_team")

    return {
        "event_id": game.get("id"),
        "home_team": game.get("home_team"),
        "away_team": game.get("away_team"),
        "home_score": home_score,
        "away_score": away_score,
        "winner": winner,
        "completed": game.get("completed", False)
    }


# ============================================================================
# ESPN API - BOX SCORES (FREE)
# ============================================================================

async def fetch_espn_box_scores(sport: str, game_date: date) -> Dict[str, Dict]:
    """
    Fetch box scores from ESPN API (FREE).

    This gives us player stats for ALL games on a given date.

    Args:
        sport: Internal sport code
        game_date: Date to fetch

    Returns:
        Dict mapping player_name_lower -> stats dict
    """
    cache_key = f"espn_{sport}_{game_date.isoformat()}"
    if cache_key in _espn_box_scores_cache:
        return _espn_box_scores_cache[cache_key]

    espn_path = ESPN_SPORT_PATHS.get(sport.upper())
    if not espn_path:
        logger.warning(f"Unknown sport for ESPN: {sport}")
        return {}

    # ESPN scoreboard endpoint for a specific date
    date_str = game_date.strftime("%Y%m%d")
    url = f"{ESPN_API_BASE}/{espn_path}/scoreboard"
    params = {"dates": date_str}

    player_stats = {}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                logger.debug(f"ESPN scoreboard error: {resp.status_code}")
                return {}

            data = resp.json()
            events = data.get("events", [])

            logger.info(f"ESPN: Found {len(events)} {sport} events on {game_date}")

            # For each game, try to get the box score
            for event in events:
                event_id = event.get("id")
                if not event_id:
                    continue

                # Only process completed games
                status = event.get("status", {}).get("type", {}).get("state", "")
                if status != "post":
                    continue

                # Fetch detailed box score
                box_url = f"{ESPN_API_BASE}/{espn_path}/summary"
                box_params = {"event": event_id}

                try:
                    box_resp = await client.get(box_url, params=box_params)
                    if box_resp.status_code == 200:
                        box_data = box_resp.json()
                        _extract_player_stats_from_espn(box_data, player_stats, sport)
                except Exception as e:
                    logger.debug(f"ESPN box score fetch failed for event {event_id}: {e}")

            logger.info(f"ESPN: Extracted stats for {len(player_stats)} players on {game_date}")
            _espn_box_scores_cache[cache_key] = player_stats
            return player_stats

    except httpx.RequestError as e:
        logger.debug(f"ESPN request failed: {e}")
        return {}
    except Exception as e:
        logger.exception(f"ESPN unexpected error: {e}")
        return {}


def _extract_player_stats_from_espn(box_data: Dict, player_stats: Dict, sport: str):
    """Extract player stats from ESPN summary response."""
    # ESPN structure: boxscore.players[].statistics[].athletes[]
    boxscore = box_data.get("boxscore", {})
    players_data = boxscore.get("players", [])

    for team_data in players_data:
        statistics = team_data.get("statistics", [])

        for stat_group in statistics:
            stat_keys = stat_group.get("keys", [])
            athletes = stat_group.get("athletes", [])

            for athlete in athletes:
                player_info = athlete.get("athlete", {})
                player_name = player_info.get("displayName", "")
                if not player_name:
                    continue

                player_name_lower = player_name.lower()
                stats_values = athlete.get("stats", [])

                # Map stat keys to values
                if len(stat_keys) == len(stats_values):
                    parsed_stats = dict(zip(stat_keys, stats_values))

                    # Convert to our standardized format based on sport
                    normalized = _normalize_espn_stats(parsed_stats, sport)
                    if normalized:
                        player_stats[player_name_lower] = normalized
                        player_stats[player_name_lower]["player_name"] = player_name


def _normalize_espn_stats(raw_stats: Dict, sport: str) -> Optional[Dict]:
    """Normalize ESPN stats to our standard format."""
    try:
        if sport.upper() == "NBA":
            return {
                "points": _safe_int(raw_stats.get("pts", raw_stats.get("points", 0))),
                "rebounds": _safe_int(raw_stats.get("reb", raw_stats.get("rebounds", 0))),
                "assists": _safe_int(raw_stats.get("ast", raw_stats.get("assists", 0))),
                "steals": _safe_int(raw_stats.get("stl", raw_stats.get("steals", 0))),
                "blocks": _safe_int(raw_stats.get("blk", raw_stats.get("blocks", 0))),
                "threes": _safe_int(raw_stats.get("3pm", raw_stats.get("fg3m", 0))),
                "turnovers": _safe_int(raw_stats.get("to", raw_stats.get("turnovers", 0))),
                "minutes": _safe_float(raw_stats.get("min", raw_stats.get("minutes", 0))),
            }
        elif sport.upper() == "NFL":
            return {
                "passing_yards": _safe_int(raw_stats.get("passYds", raw_stats.get("passingYards", 0))),
                "rushing_yards": _safe_int(raw_stats.get("rushYds", raw_stats.get("rushingYards", 0))),
                "receiving_yards": _safe_int(raw_stats.get("recYds", raw_stats.get("receivingYards", 0))),
                "passing_touchdowns": _safe_int(raw_stats.get("passTD", raw_stats.get("passingTouchdowns", 0))),
                "receptions": _safe_int(raw_stats.get("rec", raw_stats.get("receptions", 0))),
                "rushing_attempts": _safe_int(raw_stats.get("rushAtt", 0)),
            }
        elif sport.upper() == "MLB":
            return {
                "hits": _safe_int(raw_stats.get("h", raw_stats.get("hits", 0))),
                "runs": _safe_int(raw_stats.get("r", raw_stats.get("runs", 0))),
                "rbis": _safe_int(raw_stats.get("rbi", raw_stats.get("rbis", 0))),
                "home_runs": _safe_int(raw_stats.get("hr", raw_stats.get("homeRuns", 0))),
                "strikeouts": _safe_int(raw_stats.get("so", raw_stats.get("strikeouts", 0))),
                "walks": _safe_int(raw_stats.get("bb", raw_stats.get("walks", 0))),
            }
        elif sport.upper() == "NHL":
            return {
                "goals": _safe_int(raw_stats.get("g", raw_stats.get("goals", 0))),
                "assists": _safe_int(raw_stats.get("a", raw_stats.get("assists", 0))),
                "shots": _safe_int(raw_stats.get("sog", raw_stats.get("shots", 0))),
                "plus_minus": _safe_int(raw_stats.get("pm", raw_stats.get("plusMinus", 0))),
                "saves": _safe_int(raw_stats.get("sv", raw_stats.get("saves", 0))),
            }
        else:
            return None
    except Exception:
        return None


def _safe_int(value) -> int:
    """Safely convert to int."""
    try:
        if isinstance(value, str):
            value = value.replace("-", "0").split("-")[0]  # Handle "0-0" format
        return int(float(value)) if value else 0
    except (ValueError, TypeError):
        return 0


def _safe_float(value) -> float:
    """Safely convert to float."""
    try:
        if isinstance(value, str):
            # Handle "32:15" minutes format
            if ":" in value:
                parts = value.split(":")
                return float(parts[0]) + float(parts[1]) / 60
        return float(value) if value else 0.0
    except (ValueError, TypeError):
        return 0.0


# ============================================================================
# BALLDONTLIE API - NBA STATS (FREE)
# ============================================================================

async def fetch_balldontlie_player_stats(
    player_name: str,
    game_date: date
) -> Optional[Dict[str, Any]]:
    """
    Fetch NBA player stats from BallDontLie API (FREE).

    Args:
        player_name: Player name
        game_date: Date of the game

    Returns:
        Dict with stat values or None
    """
    cache_key = f"bdl_{player_name}_{game_date.isoformat()}"
    if cache_key in _player_stats_cache:
        return _player_stats_cache[cache_key]

    headers = {}
    if BALLDONTLIE_API_KEY:
        headers["Authorization"] = BALLDONTLIE_API_KEY

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First, search for player ID
            search_url = f"{BALLDONTLIE_API_BASE}/players"
            search_params = {"search": player_name.split()[0]}  # Search by first name
            search_resp = await client.get(search_url, params=search_params, headers=headers)

            if search_resp.status_code != 200:
                return None

            search_data = search_resp.json()
            players = search_data.get("data", [])

            # Find matching player
            player_id = None
            player_name_lower = player_name.lower()
            for p in players:
                full_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".lower()
                if player_name_lower in full_name or full_name in player_name_lower:
                    player_id = p.get("id")
                    break

            if not player_id:
                return None

            # Fetch stats for the date
            stats_url = f"{BALLDONTLIE_API_BASE}/stats"
            stats_params = {
                "player_ids[]": player_id,
                "dates[]": game_date.isoformat()
            }
            stats_resp = await client.get(stats_url, params=stats_params, headers=headers)

            if stats_resp.status_code != 200:
                return None

            stats_data = stats_resp.json()
            game_stats = stats_data.get("data", [])

            if not game_stats:
                return None

            # Get the first (and should be only) game stats
            gs = game_stats[0]

            stats = {
                "points": gs.get("pts", 0),
                "rebounds": gs.get("reb", 0),
                "assists": gs.get("ast", 0),
                "steals": gs.get("stl", 0),
                "blocks": gs.get("blk", 0),
                "threes": gs.get("fg3m", 0),
                "turnovers": gs.get("turnover", 0),
                "minutes": _safe_float(gs.get("min", "0")),
            }

            # Calculate combo stats
            stats["points_rebounds"] = stats["points"] + stats["rebounds"]
            stats["points_assists"] = stats["points"] + stats["assists"]
            stats["points_rebounds_assists"] = stats["points"] + stats["rebounds"] + stats["assists"]
            stats["rebounds_assists"] = stats["rebounds"] + stats["assists"]

            _player_stats_cache[cache_key] = stats
            logger.info(f"BallDontLie: Got stats for {player_name} on {game_date}")
            return stats

    except httpx.RequestError as e:
        logger.debug(f"BallDontLie request failed: {e}")
        return None
    except Exception as e:
        logger.debug(f"BallDontLie error: {e}")
        return None


# ============================================================================
# PLAYBOOK API - FALLBACK
# ============================================================================

async def fetch_playbook_player_stats(
    sport: str,
    player_name: str,
    game_date: date
) -> Optional[Dict[str, Any]]:
    """
    Fetch player stats from Playbook API (PAID - fallback).

    Args:
        sport: Sport code
        player_name: Player name
        game_date: Game date

    Returns:
        Dict with stat values or None
    """
    if not PLAYBOOK_API_KEY:
        return None

    league = PLAYBOOK_LEAGUES.get(sport.upper())
    if not league:
        return None

    # Try games endpoint for the date
    url = f"{PLAYBOOK_API_BASE}/games"
    params = {
        "api_key": PLAYBOOK_API_KEY,
        "league": league,
        "date": game_date.isoformat()
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                return None

            data = resp.json()
            # Try to find player in game data
            # Structure depends on Playbook API response format
            # This is a fallback, so we'll try common patterns

            games = data if isinstance(data, list) else data.get("games", data.get("data", []))

            for game in games:
                # Check various possible locations for player stats
                for key in ["players", "boxscore", "stats", "player_stats"]:
                    players = game.get(key, [])
                    if isinstance(players, dict):
                        players = list(players.values())
                    for p in players:
                        p_name = p.get("name", p.get("player_name", "")).lower()
                        if player_name.lower() in p_name or p_name in player_name.lower():
                            return _normalize_playbook_stats(p, sport)

    except Exception as e:
        logger.debug(f"Playbook stats fetch failed: {e}")

    return None


def _normalize_playbook_stats(raw: Dict, sport: str) -> Dict:
    """Normalize Playbook stats to our format."""
    return {
        "points": raw.get("points", raw.get("pts", 0)),
        "rebounds": raw.get("rebounds", raw.get("reb", 0)),
        "assists": raw.get("assists", raw.get("ast", 0)),
        "steals": raw.get("steals", raw.get("stl", 0)),
        "blocks": raw.get("blocks", raw.get("blk", 0)),
        "threes": raw.get("three_pointers_made", raw.get("fg3m", 0)),
        "turnovers": raw.get("turnovers", raw.get("to", 0)),
        "passing_yards": raw.get("passing_yards", raw.get("pass_yds", 0)),
        "rushing_yards": raw.get("rushing_yards", raw.get("rush_yds", 0)),
        "receiving_yards": raw.get("receiving_yards", raw.get("rec_yds", 0)),
        "receptions": raw.get("receptions", raw.get("rec", 0)),
        "goals": raw.get("goals", raw.get("g", 0)),
        "shots": raw.get("shots", raw.get("sog", 0)),
        "hits": raw.get("hits", raw.get("h", 0)),
        "runs": raw.get("runs", raw.get("r", 0)),
        "rbis": raw.get("rbis", raw.get("rbi", 0)),
    }


# ============================================================================
# UNIFIED PLAYER STATS FETCHER
# ============================================================================

async def fetch_player_stats(
    sport: str,
    player_name: str,
    game_date: date
) -> Optional[Dict[str, Any]]:
    """
    Fetch player stats using multiple APIs in priority order:
    1. ESPN API (FREE) - Primary
    2. BallDontLie (FREE, NBA only) - Backup
    3. Playbook API (PAID) - Fallback

    Args:
        sport: Sport code
        player_name: Player name
        game_date: Game date

    Returns:
        Stats dict or None
    """
    player_name_lower = player_name.lower()

    # 1. Try ESPN box scores first (FREE, all sports)
    espn_stats = await fetch_espn_box_scores(sport, game_date)
    if espn_stats:
        # Try exact match first
        if player_name_lower in espn_stats:
            stats = espn_stats[player_name_lower]
            _add_combo_stats(stats)
            logger.info(f"ESPN: Found stats for {player_name}")
            return stats

        # Try fuzzy match
        for key, stats in espn_stats.items():
            if player_name_lower in key or key in player_name_lower:
                _add_combo_stats(stats)
                logger.info(f"ESPN: Found stats for {player_name} (fuzzy)")
                return stats

            # Try matching by last name
            last_name = player_name.split()[-1].lower() if " " in player_name else ""
            if last_name and last_name in key:
                _add_combo_stats(stats)
                logger.info(f"ESPN: Found stats for {player_name} (last name)")
                return stats

    # 2. Try BallDontLie for NBA (FREE)
    if sport.upper() == "NBA":
        bdl_stats = await fetch_balldontlie_player_stats(player_name, game_date)
        if bdl_stats:
            logger.info(f"BallDontLie: Found stats for {player_name}")
            return bdl_stats

    # 3. Try Playbook API as fallback (PAID)
    playbook_stats = await fetch_playbook_player_stats(sport, player_name, game_date)
    if playbook_stats:
        _add_combo_stats(playbook_stats)
        logger.info(f"Playbook: Found stats for {player_name}")
        return playbook_stats

    logger.debug(f"No stats found for {player_name} ({sport}) on {game_date}")
    return None


def _add_combo_stats(stats: Dict):
    """Add combo stats if not present."""
    pts = stats.get("points", 0) or 0
    reb = stats.get("rebounds", 0) or 0
    ast = stats.get("assists", 0) or 0

    if "points_rebounds" not in stats:
        stats["points_rebounds"] = pts + reb
    if "points_assists" not in stats:
        stats["points_assists"] = pts + ast
    if "points_rebounds_assists" not in stats:
        stats["points_rebounds_assists"] = pts + reb + ast
    if "rebounds_assists" not in stats:
        stats["rebounds_assists"] = reb + ast


def get_stat_value_from_market(stats: Dict[str, Any], market: str) -> Optional[float]:
    """
    Extract the relevant stat value based on the market type.

    Market examples: player_points, player_rebounds, player_assists, etc.
    """
    if not stats:
        return None

    # Normalize market name
    market_lower = market.lower().replace("player_", "").replace("_", "")

    # Map market to stat key
    market_to_stat = {
        "points": "points",
        "rebounds": "rebounds",
        "assists": "assists",
        "steals": "steals",
        "blocks": "blocks",
        "threes": "threes",
        "3pointers": "threes",
        "threepointsmade": "threes",
        "turnovers": "turnovers",
        "pointsrebounds": "points_rebounds",
        "ptsrebs": "points_rebounds",
        "pointsassists": "points_assists",
        "ptsasts": "points_assists",
        "pointsreboundsassists": "points_rebounds_assists",
        "pra": "points_rebounds_assists",
        "reboundsassists": "rebounds_assists",
        # NFL
        "passingyards": "passing_yards",
        "rushingyards": "rushing_yards",
        "receivingyards": "receiving_yards",
        "passingtouchdowns": "passing_touchdowns",
        "passtds": "passing_touchdowns",
        "receptions": "receptions",
        # MLB
        "hits": "hits",
        "runs": "runs",
        "rbis": "rbis",
        "homeruns": "home_runs",
        "strikeouts": "strikeouts",
        # NHL
        "goals": "goals",
        "shots": "shots",
        "saves": "saves",
    }

    stat_key = market_to_stat.get(market_lower, market_lower)
    value = stats.get(stat_key)

    if value is not None:
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    return None


# ============================================================================
# RESULT DETERMINATION
# ============================================================================

def determine_pick_result(
    pick: PickLedger,
    actual_value: Optional[float],
    game_result: Optional[Dict[str, Any]] = None
) -> Tuple[PickResult, Optional[float]]:
    """
    Determine if a pick won, lost, or pushed based on actual outcome.

    Args:
        pick: The pick to grade
        actual_value: For props, the actual stat value achieved
        game_result: For game picks, the game outcome data

    Returns:
        Tuple of (PickResult, actual_value)
    """
    # Props grading (player props with line)
    if pick.player_name and pick.line is not None and actual_value is not None:
        side = (pick.side or "").upper()

        if actual_value == pick.line:
            return PickResult.PUSH, actual_value

        if side == "OVER":
            if actual_value > pick.line:
                return PickResult.WIN, actual_value
            else:
                return PickResult.LOSS, actual_value
        elif side == "UNDER":
            if actual_value < pick.line:
                return PickResult.WIN, actual_value
            else:
                return PickResult.LOSS, actual_value
        else:
            # No side specified, can't grade
            return PickResult.MISSING, actual_value

    # Game picks grading (spreads, totals, ML)
    if game_result:
        market = (pick.market or "").lower()
        home_score = game_result.get("home_score")
        away_score = game_result.get("away_score")

        # Moneyline
        if market in ["moneyline", "h2h", "ml"]:
            winner = game_result.get("winner")
            if winner:
                selection_lower = (pick.selection or "").lower()
                winner_lower = winner.lower()
                if winner_lower in selection_lower or selection_lower in winner_lower:
                    return PickResult.WIN, None
                else:
                    return PickResult.LOSS, None

        # Spread
        elif market in ["spread", "spreads"]:
            if home_score is not None and away_score is not None and pick.line is not None:
                margin = home_score - away_score

                selection_lower = (pick.selection or "").lower()
                home_team_lower = (pick.home_team or game_result.get("home_team", "")).lower()
                away_team_lower = (pick.away_team or game_result.get("away_team", "")).lower()

                is_home_pick = any(word in selection_lower for word in home_team_lower.split() if len(word) > 3)
                is_away_pick = any(word in selection_lower for word in away_team_lower.split() if len(word) > 3)

                if is_home_pick and not is_away_pick:
                    cover_margin = margin + pick.line
                elif is_away_pick and not is_home_pick:
                    cover_margin = -margin + pick.line
                else:
                    return PickResult.MISSING, None

                if abs(cover_margin) < 0.001:
                    return PickResult.PUSH, None
                elif cover_margin > 0:
                    return PickResult.WIN, None
                else:
                    return PickResult.LOSS, None

        # Totals
        elif market in ["total", "totals", "over_under"]:
            if home_score is not None and away_score is not None and pick.line is not None:
                total = home_score + away_score
                side = (pick.side or "").upper()

                if abs(total - pick.line) < 0.001:
                    return PickResult.PUSH, total

                if side == "OVER":
                    if total > pick.line:
                        return PickResult.WIN, total
                    else:
                        return PickResult.LOSS, total
                elif side == "UNDER":
                    if total < pick.line:
                        return PickResult.WIN, total
                    else:
                        return PickResult.LOSS, total

    return PickResult.MISSING, None


# ============================================================================
# GRADING FUNCTIONS
# ============================================================================

async def fetch_game_results(
    sport: str,
    event_id: Optional[str],
    home_team: Optional[str],
    away_team: Optional[str],
    game_date: date
) -> Optional[Dict[str, Any]]:
    """
    Fetch game result from Odds API.
    """
    games = await fetch_odds_api_scores(sport, days_from=3)

    if not games:
        return None

    class TempPick:
        pass

    temp = TempPick()
    temp.event_id = event_id
    temp.home_team = home_team
    temp.away_team = away_team
    temp.matchup = f"{away_team} @ {home_team}" if away_team and home_team else ""

    return match_game_to_pick(temp, games)


async def fetch_prop_results(
    sport: str,
    player_name: str,
    stat_type: str,
    game_date: date
) -> Optional[float]:
    """
    Fetch actual prop result using multiple APIs.
    """
    stats = await fetch_player_stats(sport, player_name, game_date)

    if not stats:
        return None

    return get_stat_value_from_market(stats, stat_type)


async def grade_pick(pick: PickLedger) -> Tuple[PickResult, float, Optional[float]]:
    """
    Grade a single pick by fetching results and determining outcome.

    Returns:
        Tuple of (result, profit_units, actual_value)
    """
    pick_date = pick.created_at.date() if pick.created_at else date.today()
    actual_value = None

    # Props grading
    if pick.player_name and pick.line is not None:
        stat_type = pick.market.replace("player_", "") if pick.market else ""

        actual_value = await fetch_prop_results(
            sport=pick.sport,
            player_name=pick.player_name,
            stat_type=stat_type,
            game_date=pick_date
        )

        result, actual = determine_pick_result(pick, actual_value)
        profit = calculate_profit(pick.odds, pick.recommended_units or 0.5, result)

        return result, profit, actual

    # Game picks grading
    else:
        game_result = await fetch_game_results(
            sport=pick.sport,
            event_id=pick.event_id,
            home_team=pick.home_team,
            away_team=pick.away_team,
            game_date=pick_date
        )

        result, actual = determine_pick_result(pick, None, game_result)
        profit = calculate_profit(pick.odds, pick.recommended_units or 0.5, result)

        return result, profit, actual


async def grade_picks_for_date(
    target_date: date,
    sport: Optional[str] = None
) -> Dict[str, Any]:
    """
    Grade all pending picks for a specific date.
    """
    # Clear caches at start of grading run
    global _scores_cache, _player_stats_cache, _espn_box_scores_cache
    _scores_cache = {}
    _player_stats_cache = {}
    _espn_box_scores_cache = {}

    pending_picks = get_pending_picks_for_date(target_date, sport)

    if not pending_picks:
        return {
            "date": target_date.isoformat(),
            "sport": sport,
            "picks_found": 0,
            "graded": 0,
            "missing": 0,
            "message": "No pending picks found for this date"
        }

    graded_count = 0
    missing_count = 0
    wins = 0
    losses = 0
    pushes = 0
    total_profit = 0.0
    graded_picks = []
    api_sources = {"espn": 0, "balldontlie": 0, "playbook": 0, "odds_api": 0}

    for pick in pending_picks:
        try:
            result, profit, actual_value = await grade_pick(pick)

            # Update pick in database
            with get_db() as db:
                if db:
                    update_pick_result(
                        pick_uid=pick.pick_uid,
                        result=result,
                        profit_units=profit,
                        actual_value=actual_value,
                        db=db
                    )

            if result == PickResult.MISSING:
                missing_count += 1
            else:
                graded_count += 1
                total_profit += profit

                if result == PickResult.WIN:
                    wins += 1
                elif result == PickResult.LOSS:
                    losses += 1
                elif result == PickResult.PUSH:
                    pushes += 1

                graded_picks.append({
                    "selection": pick.selection,
                    "player": pick.player_name,
                    "result": result.value,
                    "profit_units": round(profit, 2),
                    "actual_value": actual_value
                })

        except Exception as e:
            logger.exception(f"Error grading pick {pick.pick_uid}: {e}")
            missing_count += 1

    return {
        "date": target_date.isoformat(),
        "sport": sport,
        "picks_found": len(pending_picks),
        "graded": graded_count,
        "missing": missing_count,
        "record": f"{wins}-{losses}-{pushes}",
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "net_units": round(total_profit, 2),
        "graded_picks": graded_picks[:10],
        "message": f"Graded {graded_count} picks, {missing_count} missing results",
        "data_sources": ["ESPN (FREE)", "BallDontLie (FREE)", "Odds API", "Playbook"]
    }


async def run_daily_grading(days_back: int = 1) -> Dict[str, Any]:
    """
    Run daily grading for all sports.
    """
    target_date = date.today() - timedelta(days=days_back)

    sports = ["NBA", "NFL", "MLB", "NHL", "NCAAB"]
    results = {}
    total_graded = 0
    total_missing = 0
    total_wins = 0
    total_losses = 0
    total_pushes = 0
    total_profit = 0.0

    for sport in sports:
        try:
            sport_result = await grade_picks_for_date(target_date, sport)
            results[sport] = sport_result

            total_graded += sport_result.get("graded", 0)
            total_missing += sport_result.get("missing", 0)
            total_wins += sport_result.get("wins", 0)
            total_losses += sport_result.get("losses", 0)
            total_pushes += sport_result.get("pushes", 0)
            total_profit += sport_result.get("net_units", 0)
        except Exception as e:
            logger.exception(f"Error grading {sport}: {e}")
            results[sport] = {"error": str(e)}

    return {
        "date": target_date.isoformat(),
        "by_sport": results,
        "totals": {
            "graded": total_graded,
            "missing": total_missing,
            "wins": total_wins,
            "losses": total_losses,
            "pushes": total_pushes,
            "net_units": round(total_profit, 2),
            "record": f"{total_wins}-{total_losses}-{total_pushes}"
        },
        "data_sources": {
            "game_scores": "Odds API",
            "player_stats": ["ESPN (FREE)", "BallDontLie (FREE/NBA)", "Playbook (PAID)"]
        },
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# MANUAL GRADING FUNCTIONS
# ============================================================================

def grade_pick_manually(
    pick_uid: str,
    result: str,
    actual_value: Optional[float] = None
) -> Dict[str, Any]:
    """
    Manually grade a pick (for admin use).
    """
    result_enum = PickResult[result.upper()]

    with get_db() as db:
        if db:
            pick = db.query(PickLedger).filter(PickLedger.pick_uid == pick_uid).first()
            if pick:
                profit = calculate_profit(pick.odds, pick.recommended_units or 0.5, result_enum)

                update_pick_result(
                    pick_uid=pick_uid,
                    result=result_enum,
                    profit_units=profit,
                    actual_value=actual_value,
                    db=db
                )

                return {
                    "pick_uid": pick_uid,
                    "result": result,
                    "profit_units": round(profit, 2),
                    "actual_value": actual_value,
                    "success": True
                }

    return {
        "pick_uid": pick_uid,
        "success": False,
        "error": "Pick not found or database unavailable"
    }
