"""
v10.31 Grading Engine - Daily Settlement for Pick Ledger

Responsibilities:
1. Fetch pending picks for a date
2. Fetch results from Odds API (scores) and Playbook API (player stats)
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

# Sport key mapping for Odds API
ODDS_API_SPORT_KEYS = {
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "MLB": "baseball_mlb",
    "NHL": "icehockey_nhl",
    "NCAAB": "basketball_ncaab",
    "NCAAF": "americanfootball_ncaaf"
}

# Playbook API league codes
PLAYBOOK_LEAGUES = {
    "NBA": "NBA",
    "NFL": "NFL",
    "MLB": "MLB",
    "NHL": "NHL",
    "NCAAB": "CBB"  # College Basketball
}

# Cache for API results (cleared per grading run)
_scores_cache: Dict[str, List[Dict]] = {}
_player_stats_cache: Dict[str, Dict] = {}


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
    cache_key = f"{sport}_{days_from}"
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
        "daysFrom": min(days_from, 3)  # API limit is 3 days
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
                return {
                    "event_id": game.get("id"),
                    "home_team": game.get("home_team"),
                    "away_team": game.get("away_team"),
                    "home_score": game.get("scores", [{}])[0].get("score") if game.get("scores") else None,
                    "away_score": game.get("scores", [{}])[1].get("score") if game.get("scores") and len(game.get("scores", [])) > 1 else None,
                    "completed": game.get("completed", False)
                }

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
            # Parse scores from Odds API format
            scores = game.get("scores", [])
            home_score = None
            away_score = None

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

            if home_score is not None and away_score is not None:
                winner = game.get("home_team") if home_score > away_score else game.get("away_team")
                return {
                    "event_id": game.get("id"),
                    "home_team": game.get("home_team"),
                    "away_team": game.get("away_team"),
                    "home_score": home_score,
                    "away_score": away_score,
                    "winner": winner,
                    "completed": True
                }

    return None


# ============================================================================
# PLAYBOOK API - PLAYER STATS
# ============================================================================

async def fetch_player_game_stats(
    sport: str,
    player_name: str,
    game_date: date
) -> Optional[Dict[str, Any]]:
    """
    Fetch player game stats from Playbook API.

    Endpoint: GET /v1/players/{league}/gamelog

    Args:
        sport: Internal sport code
        player_name: Player name
        game_date: Date of the game

    Returns:
        Dict with stat values or None
    """
    cache_key = f"{sport}_{player_name}_{game_date.isoformat()}"
    if cache_key in _player_stats_cache:
        return _player_stats_cache[cache_key]

    if not PLAYBOOK_API_KEY:
        logger.warning("PLAYBOOK_API_KEY not configured - cannot fetch player stats")
        return None

    league = PLAYBOOK_LEAGUES.get(sport.upper())
    if not league:
        logger.warning(f"Unknown sport for Playbook API: {sport}")
        return None

    # Playbook gamelog endpoint
    url = f"{PLAYBOOK_API_BASE}/players/{league}/gamelog"
    params = {
        "api_key": PLAYBOOK_API_KEY,
        "player_name": player_name,
        "date": game_date.isoformat()
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                logger.debug(f"Playbook gamelog not found for {player_name}: {resp.status_code}")
                return None

            data = resp.json()

            # Extract stats from response
            if isinstance(data, list) and len(data) > 0:
                game_log = data[0]  # Most recent game
            elif isinstance(data, dict):
                game_log = data
            else:
                return None

            # Normalize stat names
            stats = {
                "points": game_log.get("points") or game_log.get("pts") or game_log.get("PTS"),
                "rebounds": game_log.get("rebounds") or game_log.get("reb") or game_log.get("REB"),
                "assists": game_log.get("assists") or game_log.get("ast") or game_log.get("AST"),
                "steals": game_log.get("steals") or game_log.get("stl") or game_log.get("STL"),
                "blocks": game_log.get("blocks") or game_log.get("blk") or game_log.get("BLK"),
                "threes": game_log.get("three_pointers_made") or game_log.get("fg3m") or game_log.get("3PM"),
                "turnovers": game_log.get("turnovers") or game_log.get("to") or game_log.get("TOV"),
                # Combo stats
                "points_rebounds": None,
                "points_assists": None,
                "points_rebounds_assists": None,
                "rebounds_assists": None,
                # NFL stats
                "passing_yards": game_log.get("passing_yards") or game_log.get("pass_yds"),
                "rushing_yards": game_log.get("rushing_yards") or game_log.get("rush_yds"),
                "receiving_yards": game_log.get("receiving_yards") or game_log.get("rec_yds"),
                "passing_touchdowns": game_log.get("passing_tds") or game_log.get("pass_td"),
                "receptions": game_log.get("receptions") or game_log.get("rec"),
                # MLB stats
                "hits": game_log.get("hits") or game_log.get("H"),
                "runs": game_log.get("runs") or game_log.get("R"),
                "rbis": game_log.get("rbis") or game_log.get("RBI"),
                "strikeouts": game_log.get("strikeouts") or game_log.get("SO"),
                # NHL stats
                "goals": game_log.get("goals") or game_log.get("G"),
                "shots": game_log.get("shots") or game_log.get("SOG"),
                "saves": game_log.get("saves") or game_log.get("SV"),
            }

            # Calculate combo stats for NBA
            if stats.get("points") is not None:
                pts = stats["points"] or 0
                reb = stats.get("rebounds") or 0
                ast = stats.get("assists") or 0
                stats["points_rebounds"] = pts + reb
                stats["points_assists"] = pts + ast
                stats["points_rebounds_assists"] = pts + reb + ast
                stats["rebounds_assists"] = reb + ast

            _player_stats_cache[cache_key] = stats
            logger.info(f"Playbook: Got stats for {player_name} on {game_date}")
            return stats

    except httpx.RequestError as e:
        logger.debug(f"Playbook request failed for {player_name}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Playbook unexpected error: {e}")
        return None


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
                # Check if our selection matches the winner
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

                # Determine if pick was on home or away
                selection_lower = (pick.selection or "").lower()
                home_team_lower = (pick.home_team or game_result.get("home_team", "")).lower()
                away_team_lower = (pick.away_team or game_result.get("away_team", "")).lower()

                is_home_pick = any(word in selection_lower for word in home_team_lower.split() if len(word) > 3)
                is_away_pick = any(word in selection_lower for word in away_team_lower.split() if len(word) > 3)

                if is_home_pick and not is_away_pick:
                    # Home team spread
                    cover_margin = margin + pick.line
                elif is_away_pick and not is_home_pick:
                    # Away team spread
                    cover_margin = -margin + pick.line
                else:
                    # Can't determine side
                    return PickResult.MISSING, None

                if abs(cover_margin) < 0.001:  # Push
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

                if abs(total - pick.line) < 0.001:  # Push
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

    # Cannot determine result
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

    Args:
        sport: NBA, NFL, etc.
        event_id: Odds API event ID if available
        home_team: Home team name
        away_team: Away team name
        game_date: Date of the game

    Returns:
        Dict with home_score, away_score, winner or None
    """
    # Fetch scores from Odds API
    games = await fetch_odds_api_scores(sport, days_from=3)

    if not games:
        return None

    # Create a temporary pick-like object for matching
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
    Fetch actual prop result from Playbook API.

    Args:
        sport: NBA, NFL, etc.
        player_name: Player name
        stat_type: points, assists, rebounds, etc.
        game_date: Date of the game

    Returns:
        Actual stat value or None if not available
    """
    stats = await fetch_player_game_stats(sport, player_name, game_date)

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
        # Extract stat type from market
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

    Args:
        target_date: Date to grade picks for
        sport: Optional sport filter

    Returns:
        Summary of grading results
    """
    # Clear caches at start of grading run
    global _scores_cache, _player_stats_cache
    _scores_cache = {}
    _player_stats_cache = {}

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
        "graded_picks": graded_picks[:10],  # Top 10 for brevity
        "message": f"Graded {graded_count} picks, {missing_count} missing results"
    }


async def run_daily_grading(days_back: int = 1) -> Dict[str, Any]:
    """
    Run daily grading for all sports.

    Args:
        days_back: How many days back to grade (default: yesterday)

    Returns:
        Combined grading summary for all sports
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

    Args:
        pick_uid: The pick's unique identifier
        result: WIN, LOSS, PUSH, VOID
        actual_value: Optional actual stat value

    Returns:
        Grading result
    """
    result_enum = PickResult[result.upper()]

    # Get pick to calculate profit
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
