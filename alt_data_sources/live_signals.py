"""
LIVE IN-GAME SIGNALS MODULE - Score momentum and line movement detection (v20.0 Phase 9)

FEATURE FLAG: Live in-game signal analysis

REQUIREMENTS:
- Must detect blowouts, comebacks, momentum shifts
- Must detect sharp money via live line movement
- Combined boost cap: ±0.50
- Only applies to game_status == "LIVE" picks
- NEVER breaks scoring pipeline

DATA SOURCES:
- ESPN scoreboard data (scores, period, game_status)
- LineSnapshot table for line history
"""

from typing import Dict, Any, Optional, List
import logging
import os

logger = logging.getLogger("live_signals")

# Feature flag
LIVE_SIGNALS_ENABLED = os.getenv("PHASE9_LIVE_SIGNALS_ENABLED", "false").lower() == "true"

# Boost caps
MAX_MOMENTUM_BOOST = 0.25
MAX_LINE_MOVEMENT_BOOST = 0.30
MAX_COMBINED_LIVE_BOOST = 0.50

# Sport-specific thresholds
BLOWOUT_THRESHOLDS = {
    "NBA": {"points": 20, "min_period": 3},
    "NFL": {"points": 21, "min_period": 3},
    "NHL": {"points": 4, "min_period": 2},
    "MLB": {"points": 6, "min_inning": 6},
    "NCAAB": {"points": 18, "min_period": 2},
    "NCAAF": {"points": 21, "min_period": 3},
}

COMEBACK_THRESHOLDS = {
    "NBA": {"points": 15, "min_period": 3},
    "NFL": {"points": 14, "min_period": 3},
    "NHL": {"points": 2, "min_period": 2},
    "MLB": {"points": 4, "min_inning": 7},
    "NCAAB": {"points": 12, "min_period": 2},
    "NCAAF": {"points": 14, "min_period": 3},
}

# Line movement thresholds (in points)
STEAM_THRESHOLD = 1.5  # 1.5+ point move indicates sharp action
MAJOR_STEAM_THRESHOLD = 2.5  # 2.5+ point move is major steam


def calculate_score_momentum(
    home_score: int,
    away_score: int,
    period: int,
    sport: str,
    pick_side: str,
    is_home_pick: bool = True
) -> Dict[str, Any]:
    """
    Detect blowouts, comebacks, and momentum shifts.

    Args:
        home_score: Current home team score
        away_score: Current away team score
        period: Current period/quarter/inning
        sport: Sport code (NBA, NFL, NHL, MLB, NCAAB, NCAAF)
        pick_side: The side being picked (team name or OVER/UNDER)
        is_home_pick: True if picking home team

    Returns:
        Dict with boost, signal type, and reasons
    """
    if not LIVE_SIGNALS_ENABLED:
        return {
            "boost": 0.0,
            "signal": "DISABLED",
            "reasons": [],
            "available": False
        }

    sport_upper = sport.upper()
    result = {
        "boost": 0.0,
        "signal": "NEUTRAL",
        "reasons": [],
        "available": True
    }

    # Calculate score differential
    diff = home_score - away_score
    picked_team_diff = diff if is_home_pick else -diff

    # Get thresholds for this sport
    blowout = BLOWOUT_THRESHOLDS.get(sport_upper)
    comeback = COMEBACK_THRESHOLDS.get(sport_upper)

    if not blowout or not comeback:
        return result

    # Determine period check (MLB uses innings)
    if sport_upper == "MLB":
        period_key = "min_inning"
    else:
        period_key = "min_period"

    min_period = blowout.get(period_key, 2)

    # Check for blowout (picked team is getting blown out)
    if period >= min_period:
        if picked_team_diff <= -blowout["points"]:
            # Our picked team is losing badly - NEGATIVE boost
            result["boost"] = -MAX_MOMENTUM_BOOST
            result["signal"] = "BLOWOUT_AGAINST"
            result["reasons"].append(
                f"Live: Blowout risk ({abs(picked_team_diff)} pt deficit in P{period})"
            )
        elif picked_team_diff >= blowout["points"]:
            # Our picked team has big lead - slight positive (garbage time risk)
            result["boost"] = 0.10
            result["signal"] = "BLOWOUT_FOR"
            result["reasons"].append(
                f"Live: Big lead ({picked_team_diff} pts), garbage time possible"
            )

    # Check for comeback potential
    comeback_period = comeback.get(period_key, 2)
    if period >= comeback_period:
        # Team was down big but is rallying
        if -comeback["points"] <= picked_team_diff < 0:
            # Down but within comeback range - momentum could shift
            result["boost"] = 0.05
            result["signal"] = "COMEBACK_RANGE"
            result["reasons"].append(
                f"Live: Within comeback range ({abs(picked_team_diff)} pts down)"
            )

    # Close game in late period - high volatility
    if period >= min_period and abs(diff) <= 5:
        if sport_upper in ("NBA", "NCAAB"):
            result["boost"] = max(result["boost"], 0.05)
            result["signal"] = "CLOSE_LATE"
            if "Close game" not in str(result["reasons"]):
                result["reasons"].append(f"Live: Close game in P{period} ({abs(diff)} pt margin)")
        elif sport_upper in ("NFL", "NCAAF") and abs(diff) <= 7:
            result["boost"] = max(result["boost"], 0.05)
            result["signal"] = "CLOSE_LATE"
            if "Close game" not in str(result["reasons"]):
                result["reasons"].append(f"Live: Close game in Q{period} ({abs(diff)} pt margin)")

    # Cap the boost
    result["boost"] = max(-MAX_MOMENTUM_BOOST, min(MAX_MOMENTUM_BOOST, result["boost"]))

    return result


def detect_live_line_movement(
    event_id: str,
    current_line: float,
    market_type: str = "spread",
    db_session=None
) -> Dict[str, Any]:
    """
    Detect sharp money entering during a live game via line movement.

    A 1.5+ point move indicates steam (sharp money).
    A 2.5+ point move is major steam.

    Args:
        event_id: The event/game ID
        current_line: Current line value
        market_type: Type of market (spread, total)
        db_session: Database session for querying line history

    Returns:
        Dict with boost, signal type, and reasons
    """
    if not LIVE_SIGNALS_ENABLED:
        return {
            "boost": 0.0,
            "signal": "DISABLED",
            "reasons": [],
            "available": False
        }

    result = {
        "boost": 0.0,
        "signal": "STABLE",
        "reasons": [],
        "available": True,
        "movement": 0.0
    }

    if not db_session:
        result["signal"] = "NO_SESSION"
        return result

    try:
        # Import here to avoid circular imports
        from database import get_line_history_values

        # Get line history for this event
        history = get_line_history_values(db_session, event_id, market_type)

        if not history or len(history) < 2:
            result["signal"] = "INSUFFICIENT_HISTORY"
            return result

        # Get the most recent movement
        previous_line = history[-2]
        movement = current_line - previous_line
        result["movement"] = movement

        # Check for steam (sharp money)
        if abs(movement) >= MAJOR_STEAM_THRESHOLD:
            # Major steam - very significant
            if movement > 0:
                direction = "steaming UP"
                result["boost"] = MAX_LINE_MOVEMENT_BOOST
            else:
                direction = "steaming DOWN"
                result["boost"] = -MAX_LINE_MOVEMENT_BOOST

            result["signal"] = "MAJOR_STEAM"
            result["reasons"].append(
                f"Live: Line {direction} {abs(movement):.1f} pts (major sharp action)"
            )

        elif abs(movement) >= STEAM_THRESHOLD:
            # Regular steam
            if movement > 0:
                direction = "moving UP"
                result["boost"] = 0.20
            else:
                direction = "moving DOWN"
                result["boost"] = -0.20

            result["signal"] = "STEAM"
            result["reasons"].append(
                f"Live: Line {direction} {abs(movement):.1f} pts (sharp action detected)"
            )

        elif abs(movement) >= 1.0:
            # Moderate movement - worth noting but smaller boost
            if movement > 0:
                direction = "drifting UP"
                result["boost"] = 0.10
            else:
                direction = "drifting DOWN"
                result["boost"] = -0.10

            result["signal"] = "DRIFT"
            result["reasons"].append(
                f"Live: Line {direction} {abs(movement):.1f} pts"
            )

    except ImportError:
        logger.warning("Could not import database module for line history")
        result["signal"] = "IMPORT_ERROR"
    except Exception as e:
        logger.warning("Error detecting line movement: %s", str(e))
        result["signal"] = "ERROR"

    # Cap the boost
    result["boost"] = max(-MAX_LINE_MOVEMENT_BOOST, min(MAX_LINE_MOVEMENT_BOOST, result["boost"]))

    return result


def get_combined_live_signals(
    event_id: str,
    home_score: int,
    away_score: int,
    period: int,
    sport: str,
    pick_side: str,
    is_home_pick: bool,
    current_line: float,
    market_type: str = "spread",
    db_session=None
) -> Dict[str, Any]:
    """
    Get combined live signal analysis for a pick.

    Combines score momentum and line movement detection.
    Total boost is capped at ±0.50.

    Args:
        event_id: The event/game ID
        home_score: Current home team score
        away_score: Current away team score
        period: Current period/quarter/inning
        sport: Sport code
        pick_side: The side being picked
        is_home_pick: True if picking home team
        current_line: Current line value
        market_type: Type of market
        db_session: Database session

    Returns:
        Combined analysis dict with total boost and all reasons
    """
    if not LIVE_SIGNALS_ENABLED:
        return {
            "available": False,
            "reason": "FEATURE_DISABLED",
            "total_boost": 0.0,
            "momentum_boost": 0.0,
            "line_boost": 0.0,
            "signals": [],
            "reasons": []
        }

    # Get momentum analysis
    momentum = calculate_score_momentum(
        home_score=home_score,
        away_score=away_score,
        period=period,
        sport=sport,
        pick_side=pick_side,
        is_home_pick=is_home_pick
    )

    # Get line movement analysis
    line_movement = detect_live_line_movement(
        event_id=event_id,
        current_line=current_line,
        market_type=market_type,
        db_session=db_session
    )

    # Combine boosts (capped)
    total_boost = momentum["boost"] + line_movement["boost"]
    total_boost = max(-MAX_COMBINED_LIVE_BOOST, min(MAX_COMBINED_LIVE_BOOST, total_boost))

    # Combine reasons
    all_reasons = momentum.get("reasons", []) + line_movement.get("reasons", [])

    # Combine signals
    signals = []
    if momentum["signal"] not in ("NEUTRAL", "DISABLED"):
        signals.append(momentum["signal"])
    if line_movement["signal"] not in ("STABLE", "DISABLED", "NO_SESSION", "INSUFFICIENT_HISTORY"):
        signals.append(line_movement["signal"])

    return {
        "available": True,
        "total_boost": total_boost,
        "momentum_boost": momentum["boost"],
        "line_boost": line_movement["boost"],
        "momentum_signal": momentum["signal"],
        "line_signal": line_movement["signal"],
        "signals": signals,
        "reasons": all_reasons
    }


def is_live_signals_enabled() -> bool:
    """Check if live signals feature is enabled."""
    return LIVE_SIGNALS_ENABLED
