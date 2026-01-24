"""
Glitch Protocol: Market Module v1.0
===================================
Market-based signals for edge detection.

Features:
- Reverse Line Movement (RLM) detection
- Teammate Void (parlay correlation)
- Correlation Matrix (SGP analysis)
- Benford Anomaly (streak detection)
- Steam Move Detection

Master Audit File: market.py - HIGH PRIORITY
"""

import math
from datetime import datetime, date
from typing import Dict, Any, List, Optional

# =============================================================================
# BENFORD'S LAW ANOMALY DETECTION
# =============================================================================
# Natural data follows Benford distribution for leading digits.
# Violations indicate "Mathematical Imposters" - fade the streak.

BENFORD_EXPECTED = {
    1: 0.301, 2: 0.176, 3: 0.125, 4: 0.097,
    5: 0.079, 6: 0.067, 7: 0.058, 8: 0.051, 9: 0.046
}


def check_benford_anomaly(
    recent_stats: List[float],
    threshold: float = 0.15
) -> Dict[str, Any]:
    """
    Check if recent stats violate Benford's Law.

    If leading digits don't follow natural distribution, the streak is artificial.
    Returns anomaly signal to fade the streak.

    Args:
        recent_stats: List of recent statistical values (e.g., scores, yards)
        threshold: Average deviation threshold to trigger anomaly (default 0.15)

    Returns:
        Dict with anomaly detection and fade signal
    """
    if not recent_stats or len(recent_stats) < 5:
        return {
            "available": False,
            "module": "market",
            "signal_type": "BENFORD_ANOMALY",
            "is_anomaly": False,
            "reason": "Insufficient data (need at least 5 values)"
        }

    # Extract leading digits
    leading_digits = []
    for stat in recent_stats:
        if stat > 0:
            # Get first non-zero digit
            stat_str = str(abs(stat)).lstrip('0').lstrip('.')
            if stat_str and stat_str[0].isdigit():
                leading = int(stat_str[0])
                if 1 <= leading <= 9:
                    leading_digits.append(leading)

    if len(leading_digits) < 5:
        return {
            "available": False,
            "module": "market",
            "signal_type": "BENFORD_ANOMALY",
            "is_anomaly": False,
            "reason": "Insufficient valid digits extracted"
        }

    # Calculate observed distribution
    observed = {d: 0 for d in range(1, 10)}
    for d in leading_digits:
        observed[d] += 1

    total = len(leading_digits)
    observed_pct = {d: count / total for d, count in observed.items()}

    # Calculate deviation from Benford
    total_deviation = sum(
        abs(observed_pct[d] - BENFORD_EXPECTED[d])
        for d in range(1, 10)
    )
    avg_deviation = total_deviation / 9

    is_anomaly = avg_deviation > threshold

    if is_anomaly:
        # Strong anomaly = stronger fade signal
        if avg_deviation > threshold * 2:
            signal = "STRONG_FADE"
            boost = 0.30
        else:
            signal = "FADE_STREAK"
            boost = 0.15
    else:
        signal = "NATURAL"
        boost = 0.0

    return {
        "available": True,
        "module": "market",
        "signal_type": "BENFORD_ANOMALY",
        "is_anomaly": is_anomaly,
        "deviation": round(avg_deviation, 4),
        "threshold": threshold,
        "sample_size": total,
        "signal": signal,
        "boost": boost,
        "reason": f"Benford deviation {avg_deviation:.3f} {'> threshold - ANOMALY' if is_anomaly else '< threshold - natural pattern'}"
    }


# =============================================================================
# REVERSE LINE MOVEMENT (RLM)
# =============================================================================

def detect_rlm(
    opening_line: float,
    current_line: float,
    public_pct: float,
    threshold_movement: float = 0.5,
    threshold_public: float = 55.0
) -> Dict[str, Any]:
    """
    Detect Reverse Line Movement.

    RLM occurs when the line moves OPPOSITE to public betting.
    This indicates sharp money on the opposite side.

    Args:
        opening_line: Opening spread/total
        current_line: Current spread/total
        public_pct: Percentage of public bets on favorite/over
        threshold_movement: Minimum line movement to consider (default 0.5)
        threshold_public: Minimum public % to consider lopsided (default 55%)

    Returns:
        Dict with RLM detection and direction
    """
    line_movement = current_line - opening_line

    # Not enough movement
    if abs(line_movement) < threshold_movement:
        return {
            "available": True,
            "module": "market",
            "signal_type": "RLM",
            "rlm_detected": False,
            "line_movement": round(line_movement, 1),
            "public_pct": public_pct,
            "boost": 0.0,
            "reason": f"Line movement {line_movement:.1f} below threshold"
        }

    # Public heavily on one side?
    public_lopsided = public_pct > threshold_public or public_pct < (100 - threshold_public)

    if not public_lopsided:
        return {
            "available": True,
            "module": "market",
            "signal_type": "RLM",
            "rlm_detected": False,
            "line_movement": round(line_movement, 1),
            "public_pct": public_pct,
            "boost": 0.0,
            "reason": f"Public not lopsided ({public_pct:.0f}%)"
        }

    # Check for RLM
    # If public on favorite (>55%) but line moves toward favorite = NO RLM
    # If public on favorite (>55%) but line moves toward dog = RLM
    public_on_favorite = public_pct > 50
    line_toward_favorite = line_movement < 0  # Spread shrinking = favorite getting more action

    rlm_detected = public_on_favorite != line_toward_favorite

    if rlm_detected:
        # Direction of sharp money
        if line_toward_favorite:
            direction = "FAVORITE"
        else:
            direction = "UNDERDOG"

        # Boost based on movement magnitude
        movement_factor = min(2.0, 1.0 + abs(line_movement) / 2.0)
        boost = 0.20 * movement_factor

        return {
            "available": True,
            "module": "market",
            "signal_type": "RLM",
            "rlm_detected": True,
            "direction": direction,
            "opening_line": opening_line,
            "current_line": current_line,
            "line_movement": round(line_movement, 1),
            "public_pct": public_pct,
            "movement_factor": round(movement_factor, 2),
            "boost": round(boost, 3),
            "signal": f"RLM_{direction}",
            "reason": f"RLM detected: Public {public_pct:.0f}% but line moved {line_movement:+.1f} toward {direction}"
        }

    return {
        "available": True,
        "module": "market",
        "signal_type": "RLM",
        "rlm_detected": False,
        "line_movement": round(line_movement, 1),
        "public_pct": public_pct,
        "boost": 0.0,
        "reason": "Line moving with public money"
    }


# =============================================================================
# TEAMMATE VOID (Parlay Correlation)
# =============================================================================

def check_teammate_void(legs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check for same-team props that cannibalize each other in parlays.

    Returns warnings for correlated legs that reduce parlay EV.

    Args:
        legs: List of parlay legs with player/team info

    Returns:
        Dict with warnings and correlation penalties
    """
    warnings = []
    teams = {}
    total_penalty = 0.0

    for i, leg in enumerate(legs):
        player_team = leg.get("team") or leg.get("player_team")
        player_name = leg.get("player") or leg.get("player_name", f"Player {i+1}")
        stat_type = leg.get("stat_type", "prop")
        description = leg.get("description") or f"{player_name} {leg.get('selection', stat_type)}"

        if player_team:
            if player_team in teams:
                existing = teams[player_team]

                # Check for specific cannibalization patterns
                correlation = -0.35  # Base negative correlation

                # Same stat type = stronger correlation
                if existing.get("stat_type") == stat_type:
                    correlation = -0.50

                # Points/assists cannibalize each other
                if {stat_type, existing.get("stat_type")} <= {"points", "assists"}:
                    correlation = -0.45

                warnings.append({
                    "type": "TEAMMATE_VOID",
                    "legs": [existing["description"], description],
                    "players": [existing["player"], player_name],
                    "team": player_team,
                    "correlation": correlation,
                    "penalty": abs(correlation) * 0.5,
                    "reason": f"Same-team props ({player_team}) cannibalize each other"
                })

                total_penalty += abs(correlation) * 0.5
            else:
                teams[player_team] = {
                    "description": description,
                    "player": player_name,
                    "stat_type": stat_type
                }

    return {
        "available": True,
        "module": "market",
        "signal_type": "TEAMMATE_VOID",
        "warnings": warnings,
        "warning_count": len(warnings),
        "total_penalty": round(total_penalty, 3),
        "boost": -total_penalty if warnings else 0.0,
        "recommendation": "Consider removing one leg" if warnings else "No teammate conflicts"
    }


# =============================================================================
# CORRELATION MATRIX (SGP Analysis)
# =============================================================================

# Prop correlations for same-game parlays
PROP_CORRELATIONS = {
    ("points", "rebounds"): 0.15,    # Slight positive
    ("points", "assists"): 0.25,     # Moderate positive
    ("rebounds", "assists"): -0.10,  # Slight negative
    ("points", "threes"): 0.60,      # Strong positive
    ("assists", "threes"): 0.10,     # Slight positive
    ("rebounds", "blocks"): 0.35,    # Moderate positive
    ("steals", "assists"): 0.20,     # Slight positive
    ("points", "turnovers"): 0.30,   # Moderate positive (high usage)
    ("assists", "turnovers"): 0.40,  # Strong positive (ball handler)
}


def get_prop_correlation(prop1: str, prop2: str) -> float:
    """Get correlation between two prop types."""
    # Normalize prop names
    p1 = prop1.lower().replace("player_", "")
    p2 = prop2.lower().replace("player_", "")

    # Check both orderings
    key1 = (p1, p2)
    key2 = (p2, p1)

    return PROP_CORRELATIONS.get(key1, PROP_CORRELATIONS.get(key2, 0.0))


def analyze_sgp_correlation(legs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze correlation structure of a same-game parlay.

    Returns correlation matrix and overall parlay assessment.
    """
    n = len(legs)
    if n < 2:
        return {
            "available": False,
            "reason": "Need at least 2 legs for correlation analysis"
        }

    correlations = []
    total_correlation = 0.0

    for i in range(n):
        for j in range(i + 1, n):
            leg1 = legs[i]
            leg2 = legs[j]

            prop1 = leg1.get("stat_type", "unknown")
            prop2 = leg2.get("stat_type", "unknown")

            # Same player = strong positive correlation
            if leg1.get("player") == leg2.get("player"):
                corr = 0.70
            # Same team = moderate correlation
            elif leg1.get("team") == leg2.get("team"):
                corr = get_prop_correlation(prop1, prop2)
                corr = corr * 1.5 if corr > 0 else corr * 0.5  # Amplify same-team
            else:
                corr = get_prop_correlation(prop1, prop2) * 0.3  # Dampen cross-team

            correlations.append({
                "leg1": f"{leg1.get('player', 'Unknown')} {prop1}",
                "leg2": f"{leg2.get('player', 'Unknown')} {prop2}",
                "correlation": round(corr, 2)
            })
            total_correlation += corr

    avg_correlation = total_correlation / len(correlations) if correlations else 0.0

    # Assessment
    if avg_correlation > 0.40:
        assessment = "HIGH_CORRELATION"
        boost = -0.25  # Penalty for correlated legs
        recommendation = "High correlation reduces EV - consider diversifying"
    elif avg_correlation > 0.20:
        assessment = "MODERATE_CORRELATION"
        boost = -0.10
        recommendation = "Some correlation present - acceptable for SGP"
    elif avg_correlation < -0.10:
        assessment = "NEGATIVE_CORRELATION"
        boost = 0.15  # Bonus for anti-correlated legs
        recommendation = "Negative correlation provides hedge - good structure"
    else:
        assessment = "LOW_CORRELATION"
        boost = 0.0
        recommendation = "Legs relatively independent - standard SGP"

    return {
        "available": True,
        "module": "market",
        "signal_type": "CORRELATION_MATRIX",
        "leg_count": n,
        "correlations": correlations,
        "avg_correlation": round(avg_correlation, 3),
        "assessment": assessment,
        "boost": boost,
        "recommendation": recommendation
    }


# =============================================================================
# STEAM MOVE DETECTION
# =============================================================================

def detect_steam_move(
    line_history: List[Dict[str, Any]],
    time_window_minutes: int = 30,
    movement_threshold: float = 1.0
) -> Dict[str, Any]:
    """
    Detect steam moves - rapid line movement from sharp action.

    Steam moves occur when multiple sharp bettors hit multiple books
    simultaneously, causing rapid line movement.

    Args:
        line_history: List of {timestamp, line} dicts
        time_window_minutes: Window to detect rapid movement
        movement_threshold: Minimum movement to qualify as steam
    """
    if not line_history or len(line_history) < 2:
        return {
            "available": False,
            "module": "market",
            "signal_type": "STEAM_MOVE",
            "steam_detected": False,
            "reason": "Insufficient line history"
        }

    # Sort by timestamp
    sorted_history = sorted(line_history, key=lambda x: x.get("timestamp", ""))

    # Check for rapid movement
    for i in range(1, len(sorted_history)):
        prev = sorted_history[i-1]
        curr = sorted_history[i]

        try:
            prev_time = datetime.fromisoformat(prev["timestamp"])
            curr_time = datetime.fromisoformat(curr["timestamp"])

            time_diff = (curr_time - prev_time).total_seconds() / 60
            line_diff = abs(curr["line"] - prev["line"])

            # Steam = significant movement in short time
            if time_diff <= time_window_minutes and line_diff >= movement_threshold:
                direction = "TOWARD_FAVORITE" if curr["line"] < prev["line"] else "TOWARD_DOG"

                return {
                    "available": True,
                    "module": "market",
                    "signal_type": "STEAM_MOVE",
                    "steam_detected": True,
                    "direction": direction,
                    "movement": round(line_diff, 1),
                    "time_minutes": round(time_diff, 1),
                    "boost": 0.35,
                    "signal": f"STEAM_{direction}",
                    "reason": f"Steam move detected: {line_diff:.1f} points in {time_diff:.0f} minutes"
                }
        except:
            continue

    return {
        "available": True,
        "module": "market",
        "signal_type": "STEAM_MOVE",
        "steam_detected": False,
        "boost": 0.0,
        "reason": "No steam move detected in time window"
    }


# =============================================================================
# AGGREGATED MARKET SCORE
# =============================================================================

def get_market_signals(
    opening_line: float = None,
    current_line: float = None,
    public_pct: float = None,
    recent_stats: List[float] = None,
    parlay_legs: List[Dict[str, Any]] = None,
    line_history: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Aggregate all market signals for a matchup.

    Returns individual signals plus combined market score.
    """
    signals = {}
    total_boost = 0.0
    fired_modules = []

    # RLM Detection (if line data provided)
    if opening_line is not None and current_line is not None and public_pct is not None:
        rlm = detect_rlm(opening_line, current_line, public_pct)
        signals["rlm"] = rlm
        if rlm["boost"] != 0:
            total_boost += rlm["boost"]
            fired_modules.append("RLM")

    # Benford Anomaly (if stats provided)
    if recent_stats:
        benford = check_benford_anomaly(recent_stats)
        signals["benford"] = benford
        if benford.get("boost", 0) != 0:
            total_boost += benford["boost"]
            fired_modules.append("BENFORD")

    # Teammate Void (if parlay legs provided)
    if parlay_legs:
        teammate = check_teammate_void(parlay_legs)
        signals["teammate_void"] = teammate
        if teammate["boost"] != 0:
            total_boost += teammate["boost"]
            fired_modules.append("TEAMMATE_VOID")

        # Also run SGP correlation
        sgp = analyze_sgp_correlation(parlay_legs)
        signals["sgp_correlation"] = sgp
        if sgp.get("boost", 0) != 0:
            total_boost += sgp["boost"]
            fired_modules.append("SGP_CORRELATION")

    # Steam Move (if line history provided)
    if line_history:
        steam = detect_steam_move(line_history)
        signals["steam_move"] = steam
        if steam.get("boost", 0) != 0:
            total_boost += steam["boost"]
            fired_modules.append("STEAM")

    return {
        "available": True,
        "module": "market",
        "signals": signals,
        "total_boost": round(total_boost, 3),
        "fired_modules": fired_modules,
        "modules_fired_count": len(fired_modules)
    }
