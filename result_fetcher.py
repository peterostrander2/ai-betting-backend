"""
RESULT_FETCHER.PY - Automatic Game Results & Pick Grading
=========================================================
v1.0 - Production result fetching and auto-grading

This module automatically:
1. Fetches completed game scores from Odds API
2. Fetches actual player stats from free APIs (balldontlie for NBA)
3. Grades logged picks against actual results
4. Updates pick_logger with WIN/LOSS/PUSH outcomes

Runs every 30 minutes via scheduler or can be triggered manually.
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import httpx
import pytz

# Configure logging
logger = logging.getLogger(__name__)

# Import identity resolver for canonical player ID matching
try:
    from identity import (
        normalize_player_name,
        normalize_team_name,
        get_player_resolver,
        resolve_player,
    )
    IDENTITY_RESOLVER_AVAILABLE = True
except ImportError:
    IDENTITY_RESOLVER_AVAILABLE = False

    def normalize_player_name(name):
        """Fallback normalizer."""
        return name.lower().replace(".", "").replace("'", "").strip() if name else ""

    def normalize_team_name(name):
        """Fallback team normalizer."""
        return name.lower().strip() if name else ""

# Import BallDontLie integration for NBA stats
try:
    from alt_data_sources.balldontlie import (
        get_player_game_stats as bdl_get_player_game_stats,
        grade_nba_prop as bdl_grade_nba_prop,
        get_games_by_date as bdl_get_games_by_date,
        is_balldontlie_configured,
    )
    BALLDONTLIE_MODULE_AVAILABLE = True
except ImportError:
    BALLDONTLIE_MODULE_AVAILABLE = False
    logger.warning("balldontlie module not available - using fallback")

# =============================================================================
# CONFIGURATION
# =============================================================================

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE = os.getenv("ODDS_API_BASE", "https://api.the-odds-api.com/v4")

# Timezone
ET = pytz.timezone("America/New_York")

# Sport mappings for Odds API
ODDS_API_SPORTS = {
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "MLB": "baseball_mlb",
    "NHL": "icehockey_nhl",
    "NCAAB": "basketball_ncaab"
}

# Stat type mappings for grading
STAT_TYPE_MAP = {
    # NBA
    "player_points": "points",
    "player_rebounds": "rebounds",
    "player_assists": "assists",
    "player_threes": "three_pointers_made",
    "player_steals": "steals",
    "player_blocks": "blocks",
    "player_turnovers": "turnovers",
    "player_points_rebounds_assists": "pra",
    "player_points_rebounds": "pr",
    "player_points_assists": "pa",
    "player_rebounds_assists": "ra",
    # NHL
    "player_goals": "goals",
    "player_shots": "shots",
    "player_saves": "saves",
    # NFL
    "player_pass_yds": "passing_yards",
    "player_rush_yds": "rushing_yards",
    "player_rec_yds": "receiving_yards",
    "player_pass_tds": "passing_touchdowns",
    "player_rush_tds": "rushing_touchdowns",
    "player_receptions": "receptions",
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class GameResult:
    """Completed game result."""
    game_id: str
    sport: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    completed: bool
    commence_time: str
    last_update: str


@dataclass
class PlayerStatline:
    """Player's actual stats from a game."""
    player_name: str
    team: str
    game_id: str
    sport: str
    stats: Dict[str, float] = field(default_factory=dict)
    # Common stats
    points: float = 0
    rebounds: float = 0
    assists: float = 0
    three_pointers_made: float = 0
    steals: float = 0
    blocks: float = 0
    turnovers: float = 0
    minutes: float = 0


@dataclass
class GradeResult:
    """Result of grading a pick."""
    pick_id: str
    result: str  # WIN, LOSS, PUSH
    actual_value: float
    line: float
    side: str
    player_name: str
    stat_type: str
    graded_at: str


# =============================================================================
# ODDS API - GAME SCORES
# =============================================================================

async def fetch_completed_games(sport: str, days_back: int = 1) -> List[GameResult]:
    """
    Fetch completed games from Odds API scores endpoint.

    Args:
        sport: Sport code (NBA, NFL, etc.)
        days_back: How many days back to check

    Returns:
        List of completed GameResult objects
    """
    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not set - cannot fetch scores")
        return []

    sport_key = ODDS_API_SPORTS.get(sport.upper())
    if not sport_key:
        logger.warning("Unknown sport: %s", sport)
        return []

    url = f"{ODDS_API_BASE}/sports/{sport_key}/scores"
    params = {
        "apiKey": ODDS_API_KEY,
        "daysFrom": days_back
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)

            if resp.status_code == 401:
                logger.error("Odds API auth failed")
                return []

            if resp.status_code != 200:
                logger.error("Odds API scores error: %d", resp.status_code)
                return []

            data = resp.json()

            results = []
            for game in data:
                if game.get("completed"):
                    scores = game.get("scores", [])
                    home_score = 0
                    away_score = 0

                    for score in scores:
                        if score.get("name") == game.get("home_team"):
                            home_score = int(score.get("score", 0))
                        elif score.get("name") == game.get("away_team"):
                            away_score = int(score.get("score", 0))

                    results.append(GameResult(
                        game_id=game.get("id", ""),
                        sport=sport.upper(),
                        home_team=game.get("home_team", ""),
                        away_team=game.get("away_team", ""),
                        home_score=home_score,
                        away_score=away_score,
                        completed=True,
                        commence_time=game.get("commence_time", ""),
                        last_update=game.get("last_update", "")
                    ))

            logger.info("Fetched %d completed %s games", len(results), sport)
            return results

    except Exception as e:
        logger.error("Error fetching scores: %s", e)
        return []


# =============================================================================
# CLOSING LINE VALUE (CLV) - v14.10
# =============================================================================

async def fetch_closing_odds(
    sport: str,
    event_id: str,
    market: str = "player_points"
) -> Optional[Dict[str, Any]]:
    """
    Fetch closing odds from Odds API historical endpoint.

    NOTE: This requires Odds API Historical tier subscription.
    If unavailable, returns None and CLV is not calculated.

    Args:
        sport: Sport code (NBA, NFL, etc.)
        event_id: Odds API event ID
        market: Market type (player_points, spreads, totals)

    Returns:
        Dict with closing_line, closing_odds, book, timestamp, or None if unavailable
    """
    if not ODDS_API_KEY:
        logger.debug("ODDS_API_KEY not set - CLV unavailable")
        return None

    sport_key = ODDS_API_SPORTS.get(sport.upper())
    if not sport_key:
        return None

    # Historical odds endpoint (requires subscription)
    url = f"{ODDS_API_BASE}/historical/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "markets": market,
        "bookmakers": "draftkings,fanduel",
        "oddsFormat": "american"
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)

            if resp.status_code == 404:
                logger.debug("Historical odds not available for event %s", event_id)
                return None

            if resp.status_code == 403:
                logger.warning("Historical odds API requires subscription upgrade")
                return None

            if resp.status_code == 402:
                logger.warning("Historical odds API requires payment/upgrade")
                return None

            if resp.status_code != 200:
                logger.warning("Historical odds API error: %d", resp.status_code)
                return None

            data = resp.json()

            # Extract closing line from response
            if not data.get("data"):
                return None

            # Get the last (closing) snapshot
            if isinstance(data["data"], list):
                closing_snapshot = data["data"][-1]
            else:
                closing_snapshot = data["data"]

            bookmakers = closing_snapshot.get("bookmakers", [])
            if not bookmakers:
                return None

            # Prefer DraftKings, fall back to FanDuel
            book = next((b for b in bookmakers if b.get("key") == "draftkings"), None)
            if not book:
                book = next((b for b in bookmakers if b.get("key") == "fanduel"), None)
            if not book:
                book = bookmakers[0]

            markets = book.get("markets", [])
            if not markets:
                return None

            market_data = markets[0]
            outcomes = market_data.get("outcomes", [])

            if outcomes:
                return {
                    "book": book.get("key"),
                    "market": market,
                    "line": outcomes[0].get("point"),
                    "odds": outcomes[0].get("price"),
                    "timestamp": closing_snapshot.get("timestamp")
                }

            return None

    except Exception as e:
        logger.error("Error fetching closing odds: %s", e)
        return None


def calculate_clv(
    line_at_bet: float,
    closing_line: float,
    side: str
) -> float:
    """
    Calculate Closing Line Value.

    CLV measures how much value you captured vs the closing line.
    Positive CLV = beat the market (good)
    Negative CLV = worse than closing (bad)

    For OVER bets: CLV = closing_line - line_at_bet
        (Closing higher than your bet = you got value)
    For UNDER bets: CLV = line_at_bet - closing_line
        (Closing lower than your bet = you got value)

    For spreads (taking points):
        CLV = closing_spread - spread_at_bet
        (Getting more points than closing = value)

    Args:
        line_at_bet: The line when the bet was placed
        closing_line: The closing line at game time
        side: Bet side (Over, Under, or team name for spreads)

    Returns:
        CLV value (positive = beat the market)
    """
    side_upper = side.upper()

    if side_upper == "OVER":
        # For overs, higher closing line = you got value
        return closing_line - line_at_bet
    elif side_upper == "UNDER":
        # For unders, lower closing line = you got value
        return line_at_bet - closing_line
    else:
        # For spreads, assume positive CLV if you got more points
        # (This is simplified - real spread CLV depends on context)
        return closing_line - line_at_bet


# =============================================================================
# PLAYBOOK API - PLAYER STATS (PRIMARY SOURCE)
# =============================================================================

PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "")
PLAYBOOK_API_BASE = os.getenv("PLAYBOOK_API_BASE", "https://api.playbook-api.com/v1")

# Sport mappings for Playbook API
PLAYBOOK_SPORTS = {
    "NBA": "NBA",
    "NFL": "NFL",
    "MLB": "MLB",
    "NHL": "NHL",
    "NCAAB": "CFB"
}


async def fetch_player_stats_playbook(
    sport: str,
    player_names: List[str],
    date: str
) -> List[PlayerStatline]:
    """
    Fetch player stats from Playbook API game logs.

    Args:
        sport: Sport code (NBA, NFL, etc.)
        player_names: List of player names to fetch
        date: Date string in YYYY-MM-DD format

    Returns:
        List of PlayerStatline objects
    """
    if not PLAYBOOK_API_KEY:
        logger.warning("PLAYBOOK_API_KEY not set")
        return []

    sport_key = PLAYBOOK_SPORTS.get(sport.upper(), sport.upper())
    all_stats = []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for player_name in player_names:
                url = f"{PLAYBOOK_API_BASE}/players/{sport_key}/gamelog"
                params = {
                    "player": player_name,
                    "api_key": PLAYBOOK_API_KEY
                }

                resp = await client.get(url, params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    games = data.get("games", data.get("data", []))

                    # Find the game matching our date
                    for game in games:
                        game_date = game.get("date", game.get("game_date", ""))[:10]
                        if game_date == date:
                            # Extract stats based on sport
                            if sport.upper() == "NBA":
                                pts = float(game.get("pts", game.get("points", 0)) or 0)
                                reb = float(game.get("reb", game.get("rebounds", 0)) or 0)
                                ast = float(game.get("ast", game.get("assists", 0)) or 0)
                                stl = float(game.get("stl", game.get("steals", 0)) or 0)
                                blk = float(game.get("blk", game.get("blocks", 0)) or 0)
                                tov = float(game.get("tov", game.get("turnovers", 0)) or 0)
                                fg3m = float(game.get("fg3m", game.get("three_pointers_made", 0)) or 0)

                                statline = PlayerStatline(
                                    player_name=player_name,
                                    team=game.get("team", ""),
                                    game_id=str(game.get("game_id", "")),
                                    sport=sport.upper(),
                                    points=pts,
                                    rebounds=reb,
                                    assists=ast,
                                    steals=stl,
                                    blocks=blk,
                                    turnovers=tov,
                                    three_pointers_made=fg3m,
                                    stats={
                                        "points": pts,
                                        "rebounds": reb,
                                        "assists": ast,
                                        "pra": pts + reb + ast,
                                        "pr": pts + reb,
                                        "pa": pts + ast,
                                        "ra": reb + ast,
                                        "steals": stl,
                                        "blocks": blk,
                                        "turnovers": tov,
                                        "three_pointers_made": fg3m,
                                    }
                                )
                                all_stats.append(statline)
                                logger.debug("Found stats for %s: %d pts", player_name, pts)
                            break

                elif resp.status_code == 404:
                    logger.debug("Player not found in Playbook: %s", player_name)
                else:
                    logger.warning("Playbook API error for %s: %d", player_name, resp.status_code)

        logger.info("Fetched %d player stats from Playbook for %s", len(all_stats), date)
        return all_stats

    except Exception as e:
        logger.error("Error fetching Playbook stats: %s", e)
        return []


# =============================================================================
# BALLDONTLIE API - NBA PLAYER STATS (GOAT TIER - PRIMARY FOR NBA)
# =============================================================================

# GOAT Tier subscription key - premium access for all NBA grading
BALLDONTLIE_API_KEY = os.getenv(
    "BALLDONTLIE_API_KEY",
    "1cbb16a0-3060-4caf-ac17-ff11352540bc"  # GOAT tier key
)
BALLDONTLIE_BASE_URL = "https://api.balldontlie.io/v1"


async def fetch_nba_player_stats(date: str) -> List[PlayerStatline]:
    """
    Fetch NBA player stats - tries Playbook first, then balldontlie, then ESPN.

    Args:
        date: Date string in YYYY-MM-DD format

    Returns:
        List of PlayerStatline objects
    """
    # balldontlie.io API - backup source
    url = "https://api.balldontlie.io/stats"

    if not BALLDONTLIE_API_KEY:
        logger.info("No BALLDONTLIE_API_KEY - using ESPN backup")
        return await fetch_nba_stats_espn(date)

    # Need to paginate through results
    all_stats = []
    cursor = None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                params = {
                    "dates[]": date,
                    "per_page": 100
                }
                if cursor:
                    params["cursor"] = cursor

                # Auth via Authorization header
                headers = {
                    "Authorization": BALLDONTLIE_API_KEY
                }

                resp = await client.get(url, params=params, headers=headers)

                if resp.status_code == 401:
                    logger.warning("balldontlie auth failed - trying ESPN backup")
                    return await fetch_nba_stats_espn(date)

                if resp.status_code != 200:
                    logger.warning("balldontlie API error: %d - trying ESPN backup", resp.status_code)
                    return await fetch_nba_stats_espn(date)

                data = resp.json()
                stats_data = data.get("data", [])

                for stat in stats_data:
                    player = stat.get("player", {})
                    player_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
                    team = stat.get("team", {}).get("full_name", "")
                    game = stat.get("game", {})

                    # Calculate combo stats
                    pts = float(stat.get("pts", 0) or 0)
                    reb = float(stat.get("reb", 0) or 0)
                    ast = float(stat.get("ast", 0) or 0)

                    statline = PlayerStatline(
                        player_name=player_name,
                        team=team,
                        game_id=str(game.get("id", "")),
                        sport="NBA",
                        points=pts,
                        rebounds=reb,
                        assists=ast,
                        three_pointers_made=float(stat.get("fg3m", 0) or 0),
                        steals=float(stat.get("stl", 0) or 0),
                        blocks=float(stat.get("blk", 0) or 0),
                        turnovers=float(stat.get("turnover", 0) or 0),
                        minutes=float(str(stat.get("min", "0")).split(":")[0] or 0),
                        stats={
                            "points": pts,
                            "rebounds": reb,
                            "assists": ast,
                            "pra": pts + reb + ast,
                            "pr": pts + reb,
                            "pa": pts + ast,
                            "ra": reb + ast,
                            "three_pointers_made": float(stat.get("fg3m", 0) or 0),
                            "steals": float(stat.get("stl", 0) or 0),
                            "blocks": float(stat.get("blk", 0) or 0),
                            "turnovers": float(stat.get("turnover", 0) or 0),
                        }
                    )
                    all_stats.append(statline)

                # Check for more pages
                meta = data.get("meta", {})
                cursor = meta.get("next_cursor")
                if not cursor:
                    break

        logger.info("Fetched %d NBA player statlines for %s", len(all_stats), date)
        return all_stats

    except Exception as e:
        logger.error("Error fetching NBA stats: %s", e)
        return []


# =============================================================================
# BACKUP: ESPN API FOR PLAYER STATS
# =============================================================================

async def fetch_nba_stats_espn(date: str) -> List[PlayerStatline]:
    """
    Backup: Fetch NBA stats from ESPN's unofficial API.

    Args:
        date: Date string in YYYY-MM-DD format

    Returns:
        List of PlayerStatline objects
    """
    # ESPN scoreboard endpoint - fetch without date to get completed games
    # Then filter by the date we need
    all_stats = []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # First try with specific date
            formatted_date = date.replace("-", "")
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={formatted_date}"
            resp = await client.get(url)

            if resp.status_code != 200:
                logger.warning("ESPN API error: %d", resp.status_code)
                return []

            data = resp.json()
            events = data.get("events", [])

            # If no completed games for that date, try fetching recent completed games
            completed_events = [e for e in events if e.get("status", {}).get("type", {}).get("completed", False)]

            if not completed_events:
                logger.info("No completed games for %s, trying recent games", date)
                url_recent = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
                resp_recent = await client.get(url_recent)
                if resp_recent.status_code == 200:
                    data_recent = resp_recent.json()
                    events = data_recent.get("events", [])

            for event in events:
                # Check if game is completed
                status = event.get("status", {}).get("type", {}).get("completed", False)
                if not status:
                    continue

                game_id = event.get("id", "")

                # Fetch boxscore for this game
                boxscore_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
                box_resp = await client.get(boxscore_url)

                if box_resp.status_code != 200:
                    continue

                box_data = box_resp.json()
                boxscore = box_data.get("boxscore", {})

                for team_data in boxscore.get("players", []):
                    team_name = team_data.get("team", {}).get("displayName", "")

                    for category in team_data.get("statistics", []):
                        # Process all categories (starters, bench, or unnamed)
                        athletes = category.get("athletes", [])
                        if not athletes:
                            continue

                        for athlete in athletes:
                            player = athlete.get("athlete", {})
                            player_name = player.get("displayName", "")
                            stats_raw = athlete.get("stats", [])

                            # ESPN stat order: MIN, PTS, FG, 3PT, FT, REB, AST, TO, STL, BLK, OREB, DREB, PF, +/-
                            if len(stats_raw) >= 10:
                                try:
                                    pts = float(stats_raw[1] or 0)
                                    reb = float(stats_raw[5] or 0)
                                    ast = float(stats_raw[6] or 0)
                                    stl = float(stats_raw[8] or 0)
                                    blk = float(stats_raw[9] or 0)
                                    tov = float(stats_raw[7] or 0)
                                    # 3PT format is "made-attempted"
                                    fg3m = float(str(stats_raw[3]).split("-")[0]) if stats_raw[3] else 0

                                    statline = PlayerStatline(
                                        player_name=player_name,
                                        team=team_name,
                                        game_id=game_id,
                                        sport="NBA",
                                        points=pts,
                                        rebounds=reb,
                                        assists=ast,
                                        three_pointers_made=fg3m,
                                        steals=stl,
                                        blocks=blk,
                                        turnovers=tov,
                                        stats={
                                            "points": pts,
                                            "rebounds": reb,
                                            "assists": ast,
                                            "pra": pts + reb + ast,
                                            "pr": pts + reb,
                                            "pa": pts + ast,
                                            "ra": reb + ast,
                                            "steals": stl,
                                            "blocks": blk,
                                            "turnovers": tov,
                                            "three_pointers_made": fg3m,
                                        }
                                    )
                                    all_stats.append(statline)
                                except (ValueError, IndexError) as e:
                                    logger.debug("Error parsing stats for %s: %s", player_name, e)

        logger.info("Fetched %d NBA player statlines from ESPN for %s", len(all_stats), date)
        return all_stats

    except Exception as e:
        logger.error("Error fetching ESPN stats: %s", e)
        return []


# =============================================================================
# PICK GRADING LOGIC
# =============================================================================

def normalize_player_name(name: str) -> str:
    """Normalize player name for matching."""
    if not name:
        return ""
    # Remove Jr., Sr., III, etc.
    name = name.lower().strip()
    for suffix in [" jr.", " sr.", " iii", " ii", " iv"]:
        name = name.replace(suffix, "")
    # Remove periods and extra spaces
    name = name.replace(".", "").replace("  ", " ")
    return name


def match_player_stats(
    player_name: str,
    stat_type: str,
    all_stats: List[PlayerStatline]
) -> Optional[float]:
    """
    Find a player's actual stat value from the statlines.

    Args:
        player_name: Player name to match
        stat_type: Stat type (player_points, player_assists, etc.)
        all_stats: List of all player statlines

    Returns:
        Actual stat value or None if not found
    """
    normalized_name = normalize_player_name(player_name)
    stat_key = STAT_TYPE_MAP.get(stat_type, stat_type.replace("player_", ""))

    for statline in all_stats:
        if normalize_player_name(statline.player_name) == normalized_name:
            # Check if we have this stat
            if stat_key in statline.stats:
                return statline.stats[stat_key]
            # Try direct attribute
            if hasattr(statline, stat_key):
                return getattr(statline, stat_key, None)

    return None


def grade_prop_pick(
    line: float,
    side: str,
    actual_value: float,
    push_margin: float = 0.0
) -> str:
    """
    Grade a prop pick as WIN, LOSS, or PUSH.

    Args:
        line: The betting line
        side: Over or Under
        actual_value: Actual stat value
        push_margin: Margin for push (default 0 for exact)

    Returns:
        WIN, LOSS, or PUSH
    """
    side_upper = side.upper() if side else ""

    # Exact hit = PUSH
    if actual_value == line:
        return "PUSH"

    if side_upper == "OVER":
        return "WIN" if actual_value > line else "LOSS"
    elif side_upper == "UNDER":
        return "WIN" if actual_value < line else "LOSS"
    else:
        # Unknown side
        return "PUSH"


def grade_game_pick(
    pick_type: str,
    pick_side: str,
    line: float,
    home_score: int,
    away_score: int,
    home_team: str,
    away_team: str,
    picked_team: str = ""
) -> Tuple[str, float]:
    """
    Grade a game pick (spread, total, ML).

    Args:
        pick_type: spread, total, or moneyline
        pick_side: The side picked
        line: The line/spread/total
        home_score: Home team final score
        away_score: Away team final score
        home_team: Home team name
        away_team: Away team name
        picked_team: Team name picked (for spread/ML)

    Returns:
        Tuple of (result: str, actual_value: float)
    """
    total = home_score + away_score
    spread = home_score - away_score  # Home perspective

    pick_type_lower = pick_type.lower() if pick_type else ""
    side_upper = (pick_side or "").upper()

    if "total" in pick_type_lower:
        # Over/Under total
        if total == line:
            return "PUSH", float(total)
        if side_upper == "OVER":
            return ("WIN" if total > line else "LOSS"), float(total)
        else:  # Under
            return ("WIN" if total < line else "LOSS"), float(total)

    elif "spread" in pick_type_lower:
        # Spread bet
        # Determine if we picked home or away
        picked_home = normalize_player_name(picked_team) in normalize_player_name(home_team)

        if picked_home:
            # Home team must cover the spread
            adjusted = home_score + line  # line is usually negative for favorite
            if adjusted == away_score:
                return "PUSH", float(spread)
            return ("WIN" if adjusted > away_score else "LOSS"), float(spread)
        else:
            # Away team must cover
            adjusted = away_score + line
            if adjusted == home_score:
                return "PUSH", float(-spread)
            return ("WIN" if adjusted > home_score else "LOSS"), float(-spread)

    elif "moneyline" in pick_type_lower or "ml" in pick_type_lower:
        # Moneyline bet
        picked_home = normalize_player_name(picked_team) in normalize_player_name(home_team)

        if home_score == away_score:
            return "PUSH", float(spread)

        if picked_home:
            return ("WIN" if home_score > away_score else "LOSS"), float(spread)
        else:
            return ("WIN" if away_score > home_score else "LOSS"), float(-spread)

    return "PUSH", 0.0


# =============================================================================
# MAIN AUTO-GRADING FUNCTION
# =============================================================================

async def auto_grade_picks(
    date: Optional[str] = None,
    sports: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Main function to auto-grade all pending picks for a date.

    Args:
        date: Date to grade (default: today ET)
        sports: List of sports to grade (default: all)

    Returns:
        Summary of grading results
    """
    # Import pick_logger here to avoid circular imports
    try:
        from pick_logger import get_pick_logger, get_today_picks
        PICK_LOGGER_AVAILABLE = True
    except ImportError:
        logger.error("pick_logger not available")
        return {"error": "pick_logger not available"}

    # Default to today in ET
    if not date:
        now_et = datetime.now(ET)
        date = now_et.strftime("%Y-%m-%d")

    # Default sports
    if not sports:
        sports = ["NBA", "NHL", "NFL", "MLB", "NCAAB"]

    logger.info("Starting auto-grade for %s, sports: %s", date, sports)

    results = {
        "date": date,
        "sports": sports,
        "games_fetched": 0,
        "stats_fetched": 0,
        "picks_graded": 0,
        "picks_failed": 0,
        "graded_picks": [],
        "errors": []
    }

    pick_logger = get_pick_logger()

    # Get all pending picks for the date
    pending_picks = [p for p in pick_logger.get_picks_for_date(date) if not p.result]
    logger.info("Found %d pending picks to grade", len(pending_picks))

    if not pending_picks:
        results["message"] = "No pending picks to grade"
        return results

    # Fetch completed games for each sport
    all_games: Dict[str, List[GameResult]] = {}
    all_player_stats: Dict[str, List[PlayerStatline]] = {}

    # Collect player names from prop picks for targeted Playbook lookup
    prop_players_by_sport: Dict[str, List[str]] = {}
    for pick in pending_picks:
        if pick.player_name:
            sport = pick.sport.upper()
            if sport not in prop_players_by_sport:
                prop_players_by_sport[sport] = []
            if pick.player_name not in prop_players_by_sport[sport]:
                prop_players_by_sport[sport].append(pick.player_name)

    for sport in sports:
        games = await fetch_completed_games(sport, days_back=2)
        all_games[sport] = games
        results["games_fetched"] += len(games)

        # Fetch player stats for prop grading
        player_names = prop_players_by_sport.get(sport, [])
        if player_names:
            # Try Playbook API first (we already pay for it)
            stats = await fetch_player_stats_playbook(sport, player_names, date)

            # Fallback to balldontlie/ESPN for NBA if Playbook didn't return data
            if not stats and sport == "NBA":
                logger.info("Playbook returned no stats, trying balldontlie/ESPN")
                stats = await fetch_nba_player_stats(date)
                if not stats:
                    stats = await fetch_nba_stats_espn(date)

            all_player_stats[sport] = stats
            results["stats_fetched"] += len(stats)

    # Grade each pending pick
    for pick in pending_picks:
        try:
            sport = pick.sport.upper()

            # Determine if this is a prop or game pick
            # Skip picks that already FAILED (max retries exceeded)
            MAX_GRADE_RETRIES = 5
            if getattr(pick, 'grade_status', '') == "FAILED":
                results["picks_failed"] += 1
                continue

            # Track retry attempt
            pick.retry_count = getattr(pick, 'retry_count', 0) + 1
            pick.last_attempt_at = datetime.now(ET).isoformat()

            if pick.player_name:
                # PROP PICK - need player stats
                stats = all_player_stats.get(sport, [])

                actual_value = match_player_stats(
                    pick.player_name,
                    pick.prop_type or pick.stat_type or "",
                    stats
                )

                if actual_value is None:
                    logger.debug("Could not find stats for %s (attempt %d)", pick.player_name, pick.retry_count)
                    pick.last_error = f"Stats not found for {pick.player_name}"
                    if pick.retry_count >= MAX_GRADE_RETRIES:
                        pick.grade_status = "FAILED"
                    else:
                        pick.grade_status = "WAITING_FINAL"
                    results["picks_failed"] += 1
                    continue

                # Grade the prop
                result = grade_prop_pick(
                    line=pick.line,
                    side=pick.side,
                    actual_value=actual_value
                )

            else:
                # GAME PICK - need game scores
                games = all_games.get(sport, [])

                # Find matching game
                matched_game = None
                for game in games:
                    if (normalize_player_name(game.home_team) in normalize_player_name(pick.matchup) or
                        normalize_player_name(game.away_team) in normalize_player_name(pick.matchup)):
                        matched_game = game
                        break

                if not matched_game:
                    logger.debug("Could not find game for %s (attempt %d)", pick.matchup, pick.retry_count)
                    pick.last_error = f"Game not found for {pick.matchup}"
                    if pick.retry_count >= MAX_GRADE_RETRIES:
                        pick.grade_status = "FAILED"
                    else:
                        pick.grade_status = "WAITING_FINAL"
                    results["picks_failed"] += 1
                    continue

                # Grade the game pick
                result, actual_value = grade_game_pick(
                    pick_type=pick.pick_type or "",
                    pick_side=pick.side or "",
                    line=pick.line,
                    home_score=matched_game.home_score,
                    away_score=matched_game.away_score,
                    home_team=matched_game.home_team,
                    away_team=matched_game.away_team
                )

            # Update the pick in pick_logger
            grade_result = pick_logger.grade_pick(
                pick_id=pick.pick_id,
                result=result,
                actual_value=actual_value
            )

            if grade_result:
                results["picks_graded"] += 1
                results["graded_picks"].append({
                    "pick_id": pick.pick_id,
                    "player": pick.player_name or "Game",
                    "line": pick.line,
                    "side": pick.side,
                    "actual": actual_value,
                    "result": result,
                    "tier": pick.tier,
                    "units": pick.units
                })
                logger.info("Graded %s: %s %.1f %s -> Actual: %.1f = %s",
                           pick.player_name or pick.matchup, pick.side, pick.line,
                           pick.prop_type or pick.pick_type, actual_value, result)
            else:
                results["picks_failed"] += 1

        except Exception as e:
            logger.error("Error grading pick %s: %s", pick.pick_id, e)
            results["picks_failed"] += 1
            results["errors"].append(str(e))

    # Persist retry state back to canonical log
    try:
        pick_logger._rewrite_pick_log(date)
    except Exception as e:
        logger.error("Failed to persist retry state: %s", e)

    # Calculate summary stats
    graded = results["graded_picks"]
    if graded:
        wins = sum(1 for g in graded if g["result"] == "WIN")
        losses = sum(1 for g in graded if g["result"] == "LOSS")
        pushes = sum(1 for g in graded if g["result"] == "PUSH")

        results["summary"] = {
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "hit_rate": f"{(wins / (wins + losses) * 100):.1f}%" if (wins + losses) > 0 else "N/A",
            "units_won": sum(g["units"] for g in graded if g["result"] == "WIN"),
            "units_lost": sum(g["units"] for g in graded if g["result"] == "LOSS")
        }

    logger.info("Auto-grade complete: %d graded, %d failed",
                results["picks_graded"], results["picks_failed"])

    return results


# =============================================================================
# SCHEDULER INTEGRATION
# =============================================================================

async def scheduled_auto_grade():
    """
    Scheduled task to run auto-grading.
    Called by the scheduler every 30 minutes.
    """
    logger.info("Running scheduled auto-grade...")

    # Grade today's picks
    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    # Also grade yesterday if it's early morning
    dates_to_grade = [today]
    if now_et.hour < 12:
        yesterday = (now_et - timedelta(days=1)).strftime("%Y-%m-%d")
        dates_to_grade.append(yesterday)

    all_results = []
    for date in dates_to_grade:
        result = await auto_grade_picks(date=date)
        all_results.append(result)

    return all_results


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_result_fetcher_instance = None


def get_result_fetcher():
    """Get or create the singleton result fetcher."""
    global _result_fetcher_instance
    if _result_fetcher_instance is None:
        _result_fetcher_instance = True  # Marker that module is initialized
    return _result_fetcher_instance


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    import sys

    async def main():
        date = sys.argv[1] if len(sys.argv) > 1 else None
        result = await auto_grade_picks(date=date)
        print(f"\nAuto-grade results:")
        print(f"  Games fetched: {result['games_fetched']}")
        print(f"  Stats fetched: {result['stats_fetched']}")
        print(f"  Picks graded: {result['picks_graded']}")
        print(f"  Picks failed: {result['picks_failed']}")

        if result.get("summary"):
            s = result["summary"]
            print(f"\nSummary:")
            print(f"  Record: {s['wins']}-{s['losses']}-{s['pushes']}")
            print(f"  Hit rate: {s['hit_rate']}")

        if result.get("graded_picks"):
            print(f"\nGraded picks:")
            for g in result["graded_picks"][:10]:
                print(f"  {g['player']}: {g['line']} {g['side']} -> {g['actual']} = {g['result']}")

    asyncio.run(main())
