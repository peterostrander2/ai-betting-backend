"""
MSRF - Mathematical Sequence Resonance Framework
================================================
Calculates turn date resonance using Pi, Phi, and sacred number sequences.

This system identifies mathematically significant "turn dates" based on:
- Time intervals between significant past events
- 16 operations using Pi, Phi, Phi², and Heptagon constants
- Matching against sacred number sequences (MSRF lists)

Integration: Used as a CONFLUENCE BOOST when high resonance detected.
- Resonance >= 8 points: +1.0 boost (MSRF_EXTREME)
- Resonance >= 5 points: +0.5 boost (MSRF_HIGH)
- Resonance >= 3 points: +0.25 boost (MSRF_MODERATE)
- Below 3: No boost

Data Sources:
- Player performance history (BallDontLie for NBA)
- Our stored predictions (high-confidence hits)
- Team significant game dates
"""

import datetime as dt
from datetime import timedelta, date
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple
import logging
import os
import asyncio

logger = logging.getLogger("msrf")


def _run_async_safely(coro):
    """
    Run an async coroutine from sync context.

    Handles the case where we're already in an async event loop
    (e.g., called from FastAPI endpoint).
    """
    try:
        # Try to get running loop - if we're in async context, this succeeds
        loop = asyncio.get_running_loop()
        # We're in an async context - can't use asyncio.run()
        # Just return None and skip the async call
        return None
    except RuntimeError:
        # No running loop - safe to use asyncio.run()
        try:
            return asyncio.run(coro)
        except Exception:
            return None

# Feature flag
MSRF_ENABLED = os.getenv("MSRF_ENABLED", "true").lower() == "true"

# -----------------------
# MATHEMATICAL CONSTANTS
# -----------------------
OPH_PI = 3.141592653589793
OPH_PHI = 1.618033988749895
OPH_CRV = 2.618033988749895   # phi^2 (curved growth)
OPH_HEP = 7.0                 # Heptagon constant

# -----------------------
# MSRF NUMBER LISTS
# -----------------------
MSRF_NORMAL = [
    12, 21, 24, 36, 40, 42, 48, 49, 51, 52, 54, 56, 59, 60, 63, 66, 70, 71, 72, 74,
    76, 77, 80, 84, 88, 90, 96, 98, 104, 105, 108, 110, 114, 116, 119, 120, 126, 129,
    132, 133, 135, 138, 140, 144, 147, 153, 154, 162, 168, 176, 180, 182, 186, 189,
    196, 204, 207, 210, 216, 218, 222, 223, 226, 231, 234, 238, 252, 253, 255, 259,
    260, 264, 270, 276, 279, 280, 286, 288, 294, 297, 301, 306, 308, 312, 315, 324,
    330, 336, 343, 351, 354, 360, 363, 364, 365, 372, 378, 385, 390, 394, 396, 405,
    414, 420, 432, 433, 434, 441, 444, 447, 453, 459, 460, 463, 468, 476, 480, 490,
    493, 495, 504, 509, 520, 525, 526, 531, 534, 539, 540, 544, 552, 555, 558, 563,
    565, 567, 572, 573, 576, 582, 588, 591, 594, 600, 612, 618, 621, 630, 640, 648,
    657, 660, 666, 669, 670, 672, 674, 675, 679, 681, 686, 690, 691, 693, 701, 702,
    708, 720, 726, 728, 730, 732, 735, 744, 756, 765, 770, 774, 777, 780, 789, 791,
    792, 800, 801, 807, 810, 816, 819, 828, 831, 840, 846, 855, 861, 864, 866, 868,
    882, 888, 918, 920, 930, 936, 945, 952, 954, 960, 966, 972, 980, 990, 1000, 1008,
    1019, 1035, 1040, 1042, 1050, 1052, 1056, 1062, 1071, 1074, 1080, 1083, 1089,
    1092, 1096, 1104, 1110, 1111, 1116, 1130, 1134, 1147, 1152, 1155, 1176, 1177,
    1184, 1188, 1190, 1200, 1224, 1242, 1253, 1260, 1279, 1292, 1296, 1300, 1302,
    1315, 1318, 1320, 1332, 1335, 1344, 1350, 1359, 1372, 1380, 1401, 1404, 1416,
    1428, 1440, 1441, 1446, 1449, 1461, 1470, 1485, 1486, 1488, 1512, 1513, 1518,
    1530, 1534, 1554, 1557, 1559, 1560, 1577, 1584, 1585, 1620, 1641, 1656, 1680,
    1683, 1701, 1715, 1728, 1736, 1738, 1764, 1770, 1776, 1785, 1786, 1794, 1800,
    1826, 1829, 1836, 1854, 1855, 1860, 1872, 1890, 1899, 1904, 1905, 1920, 1932,
    1944, 1960, 1972, 1980, 1998, 2016, 2046, 2047, 2070, 2080, 2100, 2103, 2112,
    2124, 2133, 2142, 2151, 2160, 2170, 2178, 2184, 2191, 2205, 2208, 2232, 2235,
    2244, 2268, 2269, 2277, 2288, 2292, 2293, 2294, 2295, 2304, 2310, 2322, 2333,
    2346, 2352, 2376, 2380, 2388, 2400, 2401, 2415, 2418, 2430, 2447, 2448, 2478,
    2483, 2484, 2506, 2520, 2556, 2558, 2559
]

# High-significance sacred numbers
# Phoenix Chronology (Archaix): 138 (Plasma cycle), 552 (sub-cycle), 1656 (main cycle), 2178 (Immortal/portal)
MSRF_IMPORTANT = [
    138, 144, 207, 210, 216, 414, 432, 552, 612, 618, 621, 630, 720, 777, 828, 864, 888,
    936, 945, 990, 1008, 1080, 1116, 1224, 1260, 1332, 1440, 1512, 1620, 1656, 1728, 1800,
    1944, 2016, 2070, 2160, 2178, 2520
]

# Decimal vortex points
MSRF_VORTEX = [
    21.7, 32.6, 43.5, 65.3, 76.2, 84.0, 87.1, 97.8, 123.6, 144.3, 178.9, 210.4,
    217.8, 231.7, 326.7, 435.6, 567.3, 762.3, 871.2
]

# Convert to set for O(1) lookup
MSRF_NORMAL_SET = set(MSRF_NORMAL)
MSRF_IMPORTANT_SET = set(MSRF_IMPORTANT)
MSRF_VORTEX_SET = set(MSRF_VORTEX)


# -----------------------
# HELPER FUNCTIONS
# -----------------------
def _oph_round(n: float) -> int:
    """Round to nearest integer."""
    return round(n)


def _oph_flip(n: int) -> int:
    """Reverse digits of a number."""
    if n == 0:
        return 0
    return int(str(abs(n))[::-1])


def _get_op_weight(index: int) -> float:
    """Alpha operations (stronger) vs Beta operations."""
    alpha_ops = [0, 1, 4, 5, 8, 9, 14, 15]
    return 1.0 if index in alpha_ops else 0.5


def _msrf_points(z: float) -> int:
    """Score a transformed interval against MSRF lists."""
    z_dec = round(z, 1)
    if z_dec in MSRF_VORTEX_SET:
        return 2  # Vortex match
    z_int = int(_oph_round(z))
    if z_int in MSRF_IMPORTANT_SET:
        return 2  # Important sacred number
    if z_int in MSRF_NORMAL_SET:
        return 1  # Normal resonant number
    return 0


def _to_datetime(d) -> dt.datetime:
    """Convert date to datetime if needed."""
    if isinstance(d, date) and not isinstance(d, dt.datetime):
        return dt.datetime(d.year, d.month, d.day)
    return d


# -----------------------
# 16 OPERATIONS
# -----------------------
# Each operation transforms a time interval Y using mathematical constants
# Format: (name, lambda, base_key, operation_index)
OPERATIONS = [
    ("O1",  lambda y: float(_oph_round(y)),              "X3", 0),   # Direct
    ("O2",  lambda y: float(_oph_flip(_oph_round(y))),   "X3", 1),   # Flip digits
    ("O3",  lambda y: y / OPH_CRV,                       "X3", 2),   # Divide by Phi²
    ("O4",  lambda y: (y / 2.0) * OPH_PI,                "X1", 3),   # Half × Pi
    ("O5",  lambda y: y / OPH_PHI,                       "X2", 4),   # Divide by Phi
    ("O6",  lambda y: (y / 2.0) * OPH_PHI,               "X2", 5),   # Half × Phi
    ("O7",  lambda y: (y / 2.0) * OPH_CRV,               "X1", 6),   # Half × Phi²
    ("O8",  lambda y: (y / 2.0) * OPH_PI,                "X2", 7),   # Half × Pi
    ("O9",  lambda y: y * OPH_PHI,                       "X2", 8),   # Multiply by Phi
    ("O10", lambda y: y * OPH_PI,                        "X1", 9),   # Multiply by Pi
    ("O11", lambda y: y * OPH_PI,                        "X3", 10),  # Multiply by Pi
    ("O12", lambda y: y * OPH_PHI,                       "X3", 11),  # Multiply by Phi
    ("O13", lambda y: y * OPH_CRV,                       "X3", 12),  # Multiply by Phi²
    ("O14", lambda y: y / OPH_HEP,                       "X3", 13),  # Divide by 7
    ("O15", lambda y: (y / 2.0) * OPH_HEP,               "X2", 14),  # Half × 7
    ("O16", lambda y: y * OPH_HEP,                       "X3", 15),  # Multiply by 7
]


# -----------------------
# CORE MSRF CALCULATION
# -----------------------
def calculate_msrf_resonance(
    significant_dates: List[date],
    target_date: date = None
) -> Dict[str, Any]:
    """
    Calculate MSRF resonance score for a target date.

    Uses the last 3 significant dates to project "turn dates" and checks
    if target_date aligns with any mathematically significant projection.

    Args:
        significant_dates: List of 3+ significant past dates
        target_date: Date to score (default: today)

    Returns:
        Dict with:
        - score: 0-1 normalized score
        - points: Raw resonance points
        - level: EXTREME/HIGH/MODERATE/MILD/NONE
        - triggered: True if boost-worthy
        - boost: Confluence boost value (0, 0.25, 0.5, or 1.0)
        - matching_operations: List of operations that hit
        - reason: Human-readable explanation
    """
    if not MSRF_ENABLED:
        return {
            "score": 0.5,
            "points": 0,
            "level": "DISABLED",
            "triggered": False,
            "boost": 0.0,
            "reason": "MSRF_DISABLED"
        }

    if not significant_dates or len(significant_dates) < 3:
        return {
            "score": 0.5,
            "points": 0,
            "level": "INSUFFICIENT_DATA",
            "triggered": False,
            "boost": 0.0,
            "reason": "Need 3+ significant dates"
        }

    # Default to today
    if target_date is None:
        target_date = date.today()

    # Sort and take last 3 dates
    dt_dates = [_to_datetime(d) for d in sorted(significant_dates)]
    X1, X2, X3 = dt_dates[-3:]

    # Calculate intervals
    Y1 = (X2 - X1).days
    Y2 = (X3 - X2).days
    Y3 = (X3 - X1).days
    Ys = [y for y in [Y1, Y2, Y3] if y != 0]

    if not Ys:
        return {
            "score": 0.5,
            "points": 0,
            "level": "ZERO_INTERVALS",
            "triggered": False,
            "boost": 0.0,
            "reason": "All intervals are zero"
        }

    bases = {"X1": X1, "X2": X2, "X3": X3}
    target_dt = _to_datetime(target_date)

    # Find operations that project to target_date
    total_points = 0.0
    matching_ops = []

    for op_name, op_func, base_key, op_idx in OPERATIONS:
        weight = _get_op_weight(op_idx)
        base = bases[base_key]

        for y in Ys:
            try:
                z = op_func(y)
                if abs(z) < 0.1:
                    continue

                # Project forward from base
                projected_dt = base + timedelta(days=z)
                projected_date = projected_dt.date()

                # Check if projection matches target date (±1 day tolerance)
                days_diff = abs((projected_date - target_date).days)
                if days_diff <= 1:
                    points = _msrf_points(z)
                    if points > 0:
                        weighted_points = points * weight
                        total_points += weighted_points
                        matching_ops.append({
                            "operation": op_name,
                            "interval": y,
                            "transformed": round(z, 2),
                            "points": points,
                            "weighted": weighted_points,
                            "base": base_key
                        })
            except Exception:
                continue

    # Determine level and boost
    if total_points >= 8:
        level = "EXTREME_RESONANCE"
        boost = 1.0
        triggered = True
        score = 0.95
    elif total_points >= 5:
        level = "HIGH_RESONANCE"
        boost = 0.5
        triggered = True
        score = 0.80
    elif total_points >= 3:
        level = "MODERATE_RESONANCE"
        boost = 0.25
        triggered = True
        score = 0.65
    elif total_points >= 1:
        level = "MILD_RESONANCE"
        boost = 0.0
        triggered = False
        score = 0.55
    else:
        level = "NO_RESONANCE"
        boost = 0.0
        triggered = False
        score = 0.50

    # Build reason string
    if matching_ops:
        top_op = max(matching_ops, key=lambda x: x["weighted"])
        reason = f"{level}: {len(matching_ops)} ops hit, best={top_op['operation']}({top_op['transformed']})"
    else:
        reason = f"{level}: No turn date alignment"

    return {
        "score": round(score, 3),
        "points": round(total_points, 2),
        "level": level,
        "triggered": triggered,
        "boost": boost,
        "matching_operations": matching_ops[:5],  # Top 5 for brevity
        "intervals_used": {"Y1": Y1, "Y2": Y2, "Y3": Y3},
        "target_date": target_date.isoformat(),
        "reason": reason
    }


# -----------------------
# DATA SOURCE: STORED PREDICTIONS
# -----------------------
def get_significant_dates_from_predictions(
    player_name: str = None,
    team: str = None,
    sport: str = None,
    days_back: int = 90,
    min_score: float = 7.5
) -> List[date]:
    """
    Get significant dates from our stored predictions.

    Finds dates where our predictions hit with high confidence.

    Args:
        player_name: Filter to specific player (for props)
        team: Filter to specific team (for game picks)
        sport: Filter to specific sport
        days_back: How many days back to look
        min_score: Minimum final_score to consider "significant"

    Returns:
        List of significant dates (most recent last)
    """
    try:
        from grader_store import load_predictions
        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(days=days_back)
        predictions = load_predictions()

        significant = []
        for pred in predictions:
            # Check filters
            if sport and pred.get("sport", "").upper() != sport.upper():
                continue
            if player_name and player_name.lower() not in pred.get("player_name", "").lower():
                continue
            if team:
                home = pred.get("home_team", "").lower()
                away = pred.get("away_team", "").lower()
                if team.lower() not in home and team.lower() not in away:
                    continue

            # Check if significant (hit with high score)
            if pred.get("result") == "HIT" and pred.get("final_score", 0) >= min_score:
                game_date = pred.get("game_date") or pred.get("event_start_time_et", "")[:10]
                if game_date:
                    try:
                        d = date.fromisoformat(game_date) if isinstance(game_date, str) else game_date
                        if _to_datetime(d) >= cutoff:
                            significant.append(d)
                    except Exception:
                        continue

        # Sort and dedupe
        significant = sorted(set(significant))
        return significant

    except Exception as e:
        logger.warning("Failed to load predictions for MSRF: %s", e)
        return []


# -----------------------
# DATA SOURCE: BALLDONTLIE (NBA)
# -----------------------
def get_significant_dates_from_player_history(
    player_name: str,
    sport: str = "NBA",
    threshold_pct: float = 1.5
) -> List[date]:
    """
    Get significant dates from player performance history.

    For NBA, uses BallDontLie to find games where player exceeded
    their average by threshold_pct (default 50% above average).

    Args:
        player_name: Player name
        sport: Sport (currently only NBA supported)
        threshold_pct: Multiplier for "significant" (1.5 = 50% above avg)

    Returns:
        List of dates where player had standout performances
    """
    if sport.upper() != "NBA":
        return []

    try:
        from alt_data_sources.balldontlie import search_player, get_player_game_stats

        # Search for player (async function - run safely)
        player = _run_async_safely(search_player(player_name))
        if not player or not player.get("id"):
            # Either in async context (can't call) or no player found
            return []

        player_id = player["id"]

        # Get recent game stats (async function - run safely)
        stats = _run_async_safely(get_player_game_stats(player_id, last_n_games=20))
        if not stats or not stats.get("games"):
            return []

        games = stats["games"]
        if len(games) < 5:
            return []

        # Calculate average points
        points_list = [g.get("pts", 0) for g in games if g.get("pts")]
        if not points_list:
            return []

        avg_pts = sum(points_list) / len(points_list)
        threshold = avg_pts * threshold_pct

        # Find standout games
        significant = []
        for game in games:
            if game.get("pts", 0) >= threshold:
                game_date = game.get("game", {}).get("date", "")[:10]
                if game_date:
                    try:
                        significant.append(date.fromisoformat(game_date))
                    except Exception:
                        continue

        return sorted(significant)

    except Exception as e:
        # In async context, _run_async_safely returns None which is handled above
        # Only log unexpected errors at debug level (not spam warnings)
        logger.debug("MSRF player history unavailable: %s", e)
        return []


# -----------------------
# COMBINED DATA SOURCE
# -----------------------
def get_significant_dates(
    player_name: str = None,
    team: str = None,
    sport: str = "NBA",
    home_team: str = None,
    away_team: str = None
) -> List[date]:
    """
    Get significant dates from all available sources.

    Combines:
    1. Our stored predictions (high-confidence hits)
    2. Player performance history (BallDontLie for NBA)

    Returns at least 3 dates if possible, or empty list.
    """
    all_dates = []

    # Source 1: Our predictions
    pred_dates = get_significant_dates_from_predictions(
        player_name=player_name,
        team=team or home_team or away_team,
        sport=sport
    )
    all_dates.extend(pred_dates)

    # Source 2: Player history (NBA only)
    if player_name and sport.upper() == "NBA":
        player_dates = get_significant_dates_from_player_history(player_name, sport)
        all_dates.extend(player_dates)

    # Dedupe and sort
    all_dates = sorted(set(all_dates))

    # Return last 5 for more data points
    return all_dates[-5:] if len(all_dates) >= 3 else []


# -----------------------
# MAIN INTEGRATION FUNCTION
# -----------------------
def get_msrf_confluence_boost(
    game_date: date,
    player_name: str = None,
    home_team: str = None,
    away_team: str = None,
    sport: str = "NBA"
) -> Tuple[float, Dict[str, Any]]:
    """
    Get MSRF confluence boost for a pick.

    This is the main integration point for live_data_router.py.

    Args:
        game_date: Date of the game
        player_name: Player name (for props)
        home_team: Home team name
        away_team: Away team name
        sport: Sport code

    Returns:
        Tuple of (boost_value, metadata_dict)
        - boost_value: 0.0, 0.25, 0.5, or 1.0
        - metadata: Full MSRF result for debugging
    """
    if not MSRF_ENABLED:
        return 0.0, {"source": "disabled", "reason": "MSRF_DISABLED"}

    # Get significant dates
    sig_dates = get_significant_dates(
        player_name=player_name,
        team=home_team or away_team,
        sport=sport,
        home_team=home_team,
        away_team=away_team
    )

    if len(sig_dates) < 3:
        return 0.0, {
            "source": "insufficient_data",
            "reason": f"Only {len(sig_dates)} significant dates found (need 3+)",
            "dates_found": [d.isoformat() for d in sig_dates]
        }

    # Calculate resonance
    result = calculate_msrf_resonance(sig_dates, game_date)
    result["source"] = "msrf_live"
    result["significant_dates_used"] = [d.isoformat() for d in sig_dates]

    logger.info("MSRF[%s vs %s]: %s, boost=%.2f, points=%.1f",
                home_team or "?", away_team or "?",
                result["level"], result["boost"], result["points"])

    return result["boost"], result


# -----------------------
# EXPORTS
# -----------------------
__all__ = [
    "calculate_msrf_resonance",
    "get_msrf_confluence_boost",
    "get_significant_dates",
    "get_significant_dates_from_predictions",
    "get_significant_dates_from_player_history",
    "MSRF_ENABLED",
    "MSRF_NORMAL",
    "MSRF_IMPORTANT",
    "MSRF_VORTEX",
]
