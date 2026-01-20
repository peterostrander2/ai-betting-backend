"""
v10.31 Grading Engine - Daily Settlement for Pick Ledger

Responsibilities:
1. Fetch pending picks for a date
2. Attempt to fetch results from providers (Odds API / Playbook)
3. Grade picks (WIN/LOSS/PUSH/VOID) and calculate profit_units
4. Update pick ledger with results

Conservative approach:
- If results provider not available, mark as MISSING (not graded)
- Only grade picks where we have confirmed outcomes
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

from database import (
    PickLedger, PickResult, get_db,
    get_pending_picks_for_date, update_pick_result
)

logger = logging.getLogger(__name__)


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

        # Moneyline
        if market in ["moneyline", "h2h"]:
            winner = game_result.get("winner")
            if winner:
                # Check if our selection matches the winner
                selection_lower = (pick.selection or "").lower()
                if winner.lower() in selection_lower or selection_lower in winner.lower():
                    return PickResult.WIN, None
                else:
                    return PickResult.LOSS, None

        # Spread
        elif market in ["spread", "spreads"]:
            home_score = game_result.get("home_score")
            away_score = game_result.get("away_score")
            if home_score is not None and away_score is not None and pick.line is not None:
                margin = home_score - away_score

                # Determine if pick was on home or away
                is_home_pick = pick.home_team and pick.home_team.lower() in (pick.selection or "").lower()

                if is_home_pick:
                    # Home team spread: they need to win by more than the line (if negative)
                    # or lose by less than the line (if positive)
                    cover_margin = margin + pick.line  # line is typically negative for favorite
                else:
                    # Away team spread: margin is inverted
                    cover_margin = -margin + pick.line

                if abs(cover_margin) < 0.001:  # Push (landed exactly on spread)
                    return PickResult.PUSH, None
                elif cover_margin > 0:
                    return PickResult.WIN, None
                else:
                    return PickResult.LOSS, None

        # Totals
        elif market in ["total", "totals"]:
            home_score = game_result.get("home_score")
            away_score = game_result.get("away_score")
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
# RESULTS FETCHING (STUB - Implement with real providers)
# ============================================================================

async def fetch_prop_results(
    sport: str,
    player_name: str,
    stat_type: str,
    game_date: date
) -> Optional[float]:
    """
    Fetch actual prop result from provider.

    STUB: Returns None (MISSING). Implement with Odds API / Playbook.

    Args:
        sport: NBA, NFL, etc.
        player_name: Player name
        stat_type: points, assists, rebounds, etc.
        game_date: Date of the game

    Returns:
        Actual stat value or None if not available
    """
    # TODO: Implement with Odds API historical results
    # Example endpoint: https://api.the-odds-api.com/v4/historical/sports/.../scores
    logger.info(f"STUB: Would fetch prop result for {player_name} {stat_type} on {game_date}")
    return None


async def fetch_game_results(
    sport: str,
    event_id: Optional[str],
    home_team: Optional[str],
    away_team: Optional[str],
    game_date: date
) -> Optional[Dict[str, Any]]:
    """
    Fetch game result from provider.

    STUB: Returns None (MISSING). Implement with Odds API / Playbook.

    Args:
        sport: NBA, NFL, etc.
        event_id: Odds API event ID if available
        home_team: Home team name
        away_team: Away team name
        game_date: Date of the game

    Returns:
        Dict with home_score, away_score, winner or None
    """
    # TODO: Implement with Odds API scores endpoint
    # https://api.the-odds-api.com/v4/sports/{sport}/scores
    logger.info(f"STUB: Would fetch game result for {away_team} @ {home_team} on {game_date}")
    return None


# ============================================================================
# GRADING FUNCTIONS
# ============================================================================

async def grade_pick(pick: PickLedger) -> Tuple[PickResult, float]:
    """
    Grade a single pick by fetching results and determining outcome.

    Returns:
        Tuple of (result, profit_units)
    """
    pick_date = pick.created_at.date() if pick.created_at else date.today()

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
        profit = calculate_profit(pick.odds, pick.recommended_units, result)

        return result, profit

    # Game picks grading
    else:
        game_result = await fetch_game_results(
            sport=pick.sport,
            event_id=pick.event_id,
            home_team=pick.home_team,
            away_team=pick.away_team,
            game_date=pick_date
        )

        result, _ = determine_pick_result(pick, None, game_result)
        profit = calculate_profit(pick.odds, pick.recommended_units, result)

        return result, profit


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

    for pick in pending_picks:
        result, profit = await grade_pick(pick)

        # Update pick in database
        with get_db() as db:
            if db:
                update_pick_result(
                    pick_uid=pick.pick_uid,
                    result=result,
                    profit_units=profit,
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
    total_profit = 0.0

    for sport in sports:
        sport_result = await grade_picks_for_date(target_date, sport)
        results[sport] = sport_result

        total_graded += sport_result.get("graded", 0)
        total_missing += sport_result.get("missing", 0)
        total_wins += sport_result.get("wins", 0)
        total_losses += sport_result.get("losses", 0)
        total_profit += sport_result.get("net_units", 0)

    return {
        "date": target_date.isoformat(),
        "by_sport": results,
        "totals": {
            "graded": total_graded,
            "missing": total_missing,
            "wins": total_wins,
            "losses": total_losses,
            "net_units": round(total_profit, 2),
            "record": f"{total_wins}-{total_losses}"
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
                profit = calculate_profit(pick.odds, pick.recommended_units, result_enum)

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
                    "profit_units": profit,
                    "actual_value": actual_value,
                    "success": True
                }

    return {
        "pick_uid": pick_uid,
        "success": False,
        "error": "Pick not found or database unavailable"
    }
