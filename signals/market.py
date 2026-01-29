"""
MARKET SIGNALS MODULE - Market structure and betting pattern signals

This module provides market-based signals for the research engine.
Each function returns a score + explicit reason string.

SIGNALS:
1. Reverse Line Movement (RLM) - Line moves against public
2. Teammate Void - Same-team prop cannibalization
3. Correlation Matrix - Prop correlation analysis
4. Steam Move Detection - Sharp action indicators

ALL SIGNALS MUST RETURN:
- score: float (0-1 normalized)
- reason: str (explicit explanation or "NO_SIGNAL" reason)
- triggered: bool
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("market")

# Feature flags
MARKET_SIGNALS_ENABLED = os.getenv("MARKET_SIGNALS_ENABLED", "true").lower() == "true"


# =============================================================================
# REVERSE LINE MOVEMENT (RLM)
# =============================================================================

def detect_rlm(
    opening_line: float,
    current_line: float,
    public_pct: float,
    money_pct: float = None
) -> Dict[str, Any]:
    """
    Detect Reverse Line Movement - when line moves against public betting.

    RLM occurs when:
    - Public bets heavily on one side (>65%)
    - Line moves in favor of the OTHER side
    - Indicates sharp money on less popular side

    Args:
        opening_line: Opening spread/total
        current_line: Current spread/total
        public_pct: Public betting percentage on favorite/over
        money_pct: Money percentage (if available)

    Returns:
        Dict with score, reason, triggered, rlm_strength, sharp_side
    """
    if not MARKET_SIGNALS_ENABLED:
        return {
            "score": 0.5,
            "reason": "MARKET_SIGNALS_DISABLED",
            "triggered": False,
            "rlm_strength": None,
            "sharp_side": None
        }

    if opening_line is None or current_line is None or public_pct is None:
        return {
            "score": 0.5,
            "reason": "INSUFFICIENT_LINE_DATA",
            "triggered": False,
            "rlm_strength": None,
            "sharp_side": None
        }

    try:
        line_move = current_line - opening_line
        public_heavy_favorite = public_pct >= 65
        public_heavy_underdog = public_pct <= 35

        # For spreads: negative = favorite, line moving more negative = favorite getting points
        # RLM: Public on favorite but line moves toward underdog

        rlm_detected = False
        sharp_side = None
        rlm_strength = 0

        if public_heavy_favorite and line_move > 0:
            # Public on favorite, line moving toward underdog
            rlm_detected = True
            sharp_side = "UNDERDOG"
            rlm_strength = min(1.0, (public_pct - 50) / 50 * abs(line_move))

        elif public_heavy_underdog and line_move < 0:
            # Public on underdog, line moving toward favorite
            rlm_detected = True
            sharp_side = "FAVORITE"
            rlm_strength = min(1.0, (50 - public_pct) / 50 * abs(line_move))

        # Enhance with money divergence if available
        if money_pct is not None:
            money_divergence = abs(public_pct - money_pct)
            if money_divergence >= 10:
                rlm_strength = min(1.0, rlm_strength + 0.2)

        if rlm_detected and rlm_strength >= 0.3:
            score = 0.8 + (rlm_strength * 0.2)  # 0.8-1.0
            reason = f"RLM_STRONG_{sharp_side}_strength={rlm_strength:.2f}"
            triggered = True
        elif rlm_detected:
            score = 0.6
            reason = f"RLM_WEAK_{sharp_side}_strength={rlm_strength:.2f}"
            triggered = True
        else:
            score = 0.5
            reason = "NO_RLM_DETECTED"
            triggered = False

        return {
            "score": round(score, 3),
            "reason": reason,
            "triggered": triggered,
            "rlm_strength": round(rlm_strength, 3) if rlm_strength else None,
            "sharp_side": sharp_side,
            "line_move": round(line_move, 2),
            "public_pct": public_pct
        }

    except Exception as e:
        logger.warning("RLM detection error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "rlm_strength": None,
            "sharp_side": None
        }


# =============================================================================
# TEAMMATE VOID
# =============================================================================

def check_teammate_void(
    player_name: str,
    prop_type: str,
    all_props: List[Dict[str, Any]] = None,
    team: str = None
) -> Dict[str, Any]:
    """
    Check for teammate void - when multiple props on same team cannibalize.

    Examples:
    - Two players from same team both have points over
    - If one hits, the other may be less likely

    Args:
        player_name: Player name for the prop
        prop_type: Type of prop (points, assists, rebounds)
        all_props: All props in the slate
        team: Player's team

    Returns:
        Dict with score, reason, triggered, conflicting_props
    """
    if not MARKET_SIGNALS_ENABLED:
        return {
            "score": 0.5,
            "reason": "MARKET_SIGNALS_DISABLED",
            "triggered": False,
            "conflicting_props": []
        }

    if not all_props or not team:
        return {
            "score": 0.5,
            "reason": "NO_PROP_DATA",
            "triggered": False,
            "conflicting_props": []
        }

    try:
        # Find same-team, same-type props
        conflicting = []

        for prop in all_props:
            if prop.get("player_name") == player_name:
                continue  # Skip self

            prop_team = prop.get("team", "")
            if team.lower() in prop_team.lower() or prop_team.lower() in team.lower():
                if prop.get("prop_type", "").lower() == prop_type.lower():
                    conflicting.append({
                        "player": prop.get("player_name"),
                        "prop_type": prop.get("prop_type"),
                        "line": prop.get("line")
                    })

        if len(conflicting) >= 2:
            score = 0.3  # Strong cannibalization risk
            reason = f"TEAMMATE_VOID_HIGH_{len(conflicting)}_conflicts"
            triggered = True
        elif len(conflicting) == 1:
            score = 0.5
            reason = f"TEAMMATE_VOID_MODERATE_1_conflict"
            triggered = True
        else:
            score = 0.7
            reason = "NO_TEAMMATE_CONFLICT"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "conflicting_props": conflicting
        }

    except Exception as e:
        logger.warning("Teammate void check error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "conflicting_props": []
        }


# =============================================================================
# CORRELATION MATRIX
# =============================================================================

# Static correlation data for same-game props
PROP_CORRELATIONS = {
    # NBA correlations
    ("points", "field_goals_made"): 0.95,
    ("points", "three_pointers_made"): 0.70,
    ("points", "free_throws_made"): 0.60,
    ("assists", "points"): 0.45,
    ("rebounds", "points"): 0.35,
    ("rebounds", "blocks"): 0.50,
    ("assists", "turnovers"): 0.55,
    ("steals", "deflections"): 0.65,
    ("minutes", "points"): 0.75,
    ("minutes", "rebounds"): 0.70,
    ("minutes", "assists"): 0.65,

    # NFL correlations
    ("passing_yards", "passing_touchdowns"): 0.70,
    ("passing_yards", "completions"): 0.85,
    ("passing_attempts", "passing_yards"): 0.80,
    ("rushing_yards", "rushing_attempts"): 0.75,
    ("rushing_yards", "rushing_touchdowns"): 0.55,
    ("receiving_yards", "receptions"): 0.85,
    ("receiving_yards", "receiving_touchdowns"): 0.50,
    ("targets", "receptions"): 0.90,

    # MLB correlations
    ("hits", "total_bases"): 0.80,
    ("hits", "runs"): 0.60,
    ("strikeouts_pitcher", "outs"): 0.65,
    ("earned_runs", "hits_allowed"): 0.70,
}


def get_prop_correlation(
    prop_type_a: str,
    prop_type_b: str,
    sport: str = "NBA"
) -> Dict[str, Any]:
    """
    Get correlation between two prop types.

    High correlation = if one hits, other likely hits (or misses)
    Low correlation = independent outcomes

    Args:
        prop_type_a: First prop type
        prop_type_b: Second prop type
        sport: Sport code

    Returns:
        Dict with score, reason, triggered, correlation, interpretation
    """
    if not MARKET_SIGNALS_ENABLED:
        return {
            "score": 0.5,
            "reason": "MARKET_SIGNALS_DISABLED",
            "triggered": False,
            "correlation": None,
            "interpretation": None
        }

    try:
        # Normalize prop types
        a = prop_type_a.lower().replace("player_", "")
        b = prop_type_b.lower().replace("player_", "")

        # Look up correlation (check both orderings)
        correlation = PROP_CORRELATIONS.get((a, b))
        if correlation is None:
            correlation = PROP_CORRELATIONS.get((b, a))

        if correlation is None:
            return {
                "score": 0.5,
                "reason": "UNKNOWN_CORRELATION",
                "triggered": False,
                "correlation": None,
                "interpretation": "No data for this prop pair"
            }

        # Interpret correlation
        if correlation >= 0.8:
            score = 0.3  # Highly correlated = risky to parlay
            reason = f"HIGH_CORRELATION_{correlation:.2f}"
            interpretation = "Very correlated - avoid parlaying"
            triggered = True
        elif correlation >= 0.6:
            score = 0.5
            reason = f"MODERATE_CORRELATION_{correlation:.2f}"
            interpretation = "Moderately correlated - caution"
            triggered = True
        elif correlation >= 0.4:
            score = 0.6
            reason = f"LOW_CORRELATION_{correlation:.2f}"
            interpretation = "Weakly correlated - acceptable"
            triggered = False
        else:
            score = 0.8
            reason = f"INDEPENDENT_{correlation:.2f}"
            interpretation = "Independent outcomes - good for parlays"
            triggered = True

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "correlation": correlation,
            "interpretation": interpretation,
            "prop_pair": (prop_type_a, prop_type_b)
        }

    except Exception as e:
        logger.warning("Correlation lookup error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "correlation": None,
            "interpretation": None
        }


# =============================================================================
# STEAM MOVE DETECTION
# =============================================================================

def detect_steam_move(
    line_history: List[Tuple[datetime, float]] = None,
    time_window_minutes: int = 30
) -> Dict[str, Any]:
    """
    Detect steam moves - rapid line movement indicating sharp action.

    Steam move characteristics:
    - Line moves 0.5+ points in <30 minutes
    - Multiple books move simultaneously
    - Indicates coordinated sharp betting

    Args:
        line_history: List of (timestamp, line) tuples
        time_window_minutes: Window to check for steam

    Returns:
        Dict with score, reason, triggered, steam_direction, velocity
    """
    if not MARKET_SIGNALS_ENABLED:
        return {
            "score": 0.5,
            "reason": "MARKET_SIGNALS_DISABLED",
            "triggered": False,
            "steam_direction": None,
            "velocity": None
        }

    if not line_history or len(line_history) < 2:
        return {
            "score": 0.5,
            "reason": "INSUFFICIENT_LINE_HISTORY",
            "triggered": False,
            "steam_direction": None,
            "velocity": None
        }

    try:
        # Sort by timestamp
        sorted_history = sorted(line_history, key=lambda x: x[0])

        # Check most recent window
        latest_time = sorted_history[-1][0]
        latest_line = sorted_history[-1][1]

        # Find line from time_window_minutes ago
        window_start = latest_time - timedelta(minutes=time_window_minutes)

        old_line = None
        for ts, line in sorted_history:
            if ts >= window_start:
                old_line = line
                break

        if old_line is None:
            old_line = sorted_history[0][1]

        # Calculate movement
        line_move = latest_line - old_line
        velocity = abs(line_move) / (time_window_minutes / 60)  # Points per hour

        # Steam thresholds
        if abs(line_move) >= 1.0 and velocity >= 2.0:
            score = 0.9
            steam_direction = "FAVORITE" if line_move < 0 else "UNDERDOG"
            reason = f"STEAM_MOVE_STRONG_{steam_direction}_velocity={velocity:.1f}"
            triggered = True
        elif abs(line_move) >= 0.5 and velocity >= 1.0:
            score = 0.75
            steam_direction = "FAVORITE" if line_move < 0 else "UNDERDOG"
            reason = f"STEAM_MOVE_MODERATE_{steam_direction}_velocity={velocity:.1f}"
            triggered = True
        else:
            score = 0.5
            steam_direction = None
            reason = "NO_STEAM_DETECTED"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "steam_direction": steam_direction,
            "velocity": round(velocity, 2),
            "line_move": round(line_move, 2)
        }

    except Exception as e:
        logger.warning("Steam detection error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "steam_direction": None,
            "velocity": None
        }


# =============================================================================
# AGGREGATE MARKET SCORE
# =============================================================================

def get_market_score(
    opening_line: float = None,
    current_line: float = None,
    public_pct: float = None,
    money_pct: float = None,
    line_history: List[Tuple[datetime, float]] = None
) -> Dict[str, Any]:
    """
    Calculate aggregate market score from all signals.

    Returns:
        Dict with overall score, all signal breakdowns, and reasons
    """
    results = {
        "rlm": detect_rlm(opening_line, current_line, public_pct, money_pct),
        "steam": detect_steam_move(line_history),
    }

    # Weights for each signal
    weights = {
        "rlm": 0.60,
        "steam": 0.40,
    }

    # Calculate weighted score
    total_score = sum(
        results[key]["score"] * weights[key]
        for key in weights
    )

    # Collect triggered signals
    triggered_signals = [
        key for key, result in results.items()
        if result.get("triggered", False)
    ]

    # Collect reasons
    reasons = [
        f"{key.upper()}: {results[key]['reason']}"
        for key in results
    ]

    return {
        "market_score": round(total_score, 3),
        "triggered_count": len(triggered_signals),
        "triggered_signals": triggered_signals,
        "reasons": reasons,
        "breakdown": results,
        "enabled": MARKET_SIGNALS_ENABLED
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "detect_rlm",
    "check_teammate_void",
    "get_prop_correlation",
    "detect_steam_move",
    "get_market_score",
    "PROP_CORRELATIONS",
    "MARKET_SIGNALS_ENABLED",
]
