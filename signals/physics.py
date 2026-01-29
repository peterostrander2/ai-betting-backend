"""
PHYSICS SIGNALS MODULE - Quantitative physics-based betting signals

This module provides physics/mathematics-based signals for the esoteric engine.
Each function returns a score + explicit reason string.

SIGNALS:
1. Gann Square of Nine - Angular resonance for spreads/totals
2. 50% Fibonacci Retracement - Support/resistance zones
3. Schumann Resonance - Earth's electromagnetic frequency
4. Barometric Drag - Atmospheric pressure impact
5. Hurst Exponent - Trending vs mean-reverting detection
6. Kp-Index - Geomagnetic activity impact

ALL SIGNALS MUST RETURN:
- score: float (0-1 normalized)
- reason: str (explicit explanation or "NO_SIGNAL" reason)
- triggered: bool
"""

import os
import math
import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

logger = logging.getLogger("physics")

# Feature flags
PHYSICS_ENABLED = os.getenv("PHYSICS_ENABLED", "true").lower() == "true"


# =============================================================================
# GANN SQUARE OF NINE
# =============================================================================

def calculate_gann_square(spread: float, total: float) -> Dict[str, Any]:
    """
    Calculate Gann Square of Nine angular resonance.

    The Gann Square maps numbers to angles. Key angles (45°, 90°, 180°, 360°)
    indicate potential support/resistance.

    Args:
        spread: Point spread
        total: Game total

    Returns:
        Dict with score, reason, triggered, angle
    """
    if not PHYSICS_ENABLED:
        return {
            "score": 0.5,
            "reason": "PHYSICS_DISABLED",
            "triggered": False,
            "angle": None
        }

    if spread == 0 and total == 0:
        return {
            "score": 0.5,
            "reason": "NO_INPUT_DATA",
            "triggered": False,
            "angle": None
        }

    # Use spread if available, else total
    value = abs(spread) if spread != 0 else abs(total)

    # Gann angle calculation: angle = (sqrt(value) - 1) * 180 / 2
    try:
        sqrt_val = math.sqrt(value)
        angle = ((sqrt_val - 1) * 180 / 2) % 360

        # Key Gann angles
        key_angles = [0, 45, 90, 135, 180, 225, 270, 315, 360]

        # Find closest key angle
        min_diff = min(abs(angle - ka) for ka in key_angles)

        # Score based on proximity to key angle (within 5 degrees = strong)
        if min_diff <= 5:
            score = 1.0
            reason = f"GANN_STRONG_ANGLE_{int(angle)}deg"
            triggered = True
        elif min_diff <= 15:
            score = 0.7
            reason = f"GANN_MODERATE_ANGLE_{int(angle)}deg"
            triggered = True
        elif min_diff <= 30:
            score = 0.5
            reason = f"GANN_WEAK_ANGLE_{int(angle)}deg"
            triggered = False
        else:
            score = 0.3
            reason = "NO_GANN_ALIGNMENT"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "angle": round(angle, 2)
        }

    except Exception as e:
        logger.warning("Gann calculation error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "angle": None
        }


# =============================================================================
# FIBONACCI RETRACEMENT
# =============================================================================

def calculate_fib_retracement(
    current_line: float,
    season_high: float = None,
    season_low: float = None
) -> Dict[str, Any]:
    """
    Calculate 50% Fibonacci retracement zone strength.

    The 50% level is considered the most significant retracement zone.

    Args:
        current_line: Current line value
        season_high: Season high for the metric
        season_low: Season low for the metric

    Returns:
        Dict with score, reason, triggered, fib_level
    """
    if not PHYSICS_ENABLED:
        return {
            "score": 0.5,
            "reason": "PHYSICS_DISABLED",
            "triggered": False,
            "fib_level": None
        }

    # Default range if not provided
    if season_high is None:
        season_high = abs(current_line) * 1.5 if current_line != 0 else 10
    if season_low is None:
        season_low = abs(current_line) * 0.5 if current_line != 0 else 1

    if season_high == season_low:
        return {
            "score": 0.5,
            "reason": "NO_RANGE_DATA",
            "triggered": False,
            "fib_level": None
        }

    try:
        # Calculate position in range
        range_size = season_high - season_low
        position = (abs(current_line) - season_low) / range_size

        # Fibonacci levels
        fib_levels = {
            0.236: "FIB_23.6",
            0.382: "FIB_38.2",
            0.500: "FIB_50.0",
            0.618: "FIB_61.8",
            0.786: "FIB_78.6"
        }

        # Find closest fib level
        closest_level = min(fib_levels.keys(), key=lambda x: abs(position - x))
        distance = abs(position - closest_level)

        # 50% level is strongest
        if closest_level == 0.5 and distance <= 0.05:
            score = 1.0
            reason = "FIB_50_PERFECT_ZONE"
            triggered = True
        elif distance <= 0.03:
            score = 0.8
            reason = f"{fib_levels[closest_level]}_STRONG"
            triggered = True
        elif distance <= 0.08:
            score = 0.6
            reason = f"{fib_levels[closest_level]}_MODERATE"
            triggered = True
        else:
            score = 0.4
            reason = "NO_FIB_ALIGNMENT"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "fib_level": round(closest_level, 3),
            "position": round(position, 3)
        }

    except Exception as e:
        logger.warning("Fibonacci calculation error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "fib_level": None
        }


# =============================================================================
# SCHUMANN RESONANCE
# =============================================================================

def get_schumann_resonance(game_time: datetime = None) -> Dict[str, Any]:
    """
    Get Schumann resonance factor based on Earth's electromagnetic frequency.

    The Schumann resonance is approximately 7.83 Hz. Variations correlate
    with collective human behavior patterns.

    Args:
        game_time: Game start time (uses current if None)

    Returns:
        Dict with score, reason, triggered, frequency
    """
    if not PHYSICS_ENABLED:
        return {
            "score": 0.5,
            "reason": "PHYSICS_DISABLED",
            "triggered": False,
            "frequency": None
        }

    # TODO: Integrate with NOAA space weather API for real data
    # For now, use time-based approximation

    if game_time is None:
        game_time = datetime.now()

    try:
        # Schumann resonance varies with solar activity
        # Base frequency: 7.83 Hz
        hour = game_time.hour
        day_of_year = game_time.timetuple().tm_yday

        # Simulate daily variation (±0.5 Hz)
        daily_factor = math.sin(2 * math.pi * hour / 24) * 0.5

        # Simulate seasonal variation (±0.3 Hz)
        seasonal_factor = math.sin(2 * math.pi * day_of_year / 365) * 0.3

        frequency = 7.83 + daily_factor + seasonal_factor

        # Optimal range: 7.5-8.0 Hz
        if 7.7 <= frequency <= 7.9:
            score = 1.0
            reason = "SCHUMANN_OPTIMAL"
            triggered = True
        elif 7.5 <= frequency <= 8.1:
            score = 0.7
            reason = "SCHUMANN_FAVORABLE"
            triggered = True
        else:
            score = 0.5
            reason = "SCHUMANN_NEUTRAL"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "frequency": round(frequency, 2),
            "note": "SIMULATED - integrate NOAA for real data"
        }

    except Exception as e:
        logger.warning("Schumann calculation error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "frequency": None
        }


# =============================================================================
# BAROMETRIC DRAG
# =============================================================================

def get_barometric_drag(
    venue: str = "",
    elevation_ft: float = None,
    humidity_pct: float = None
) -> Dict[str, Any]:
    """
    Calculate barometric/atmospheric drag factor for outdoor sports.

    Higher elevation = less air resistance = balls travel farther.
    High humidity = denser air = more drag.

    Args:
        venue: Venue name
        elevation_ft: Venue elevation in feet
        humidity_pct: Humidity percentage

    Returns:
        Dict with score, reason, triggered, drag_factor
    """
    if not PHYSICS_ENABLED:
        return {
            "score": 0.5,
            "reason": "PHYSICS_DISABLED",
            "triggered": False,
            "drag_factor": 1.0
        }

    # Known high-altitude venues
    HIGH_ALTITUDE_VENUES = {
        "denver": 5280,
        "mile high": 5280,
        "coors field": 5280,
        "salt lake": 4226,
        "vivint": 4226,
        "delta center": 4226,
        "mexico city": 7380,
        "estadio azteca": 7380,
        "phoenix": 1086,
        "chase field": 1086,
    }

    # Get elevation from venue name if not provided
    if elevation_ft is None:
        venue_lower = venue.lower()
        for venue_key, elev in HIGH_ALTITUDE_VENUES.items():
            if venue_key in venue_lower:
                elevation_ft = elev
                break
        else:
            elevation_ft = 500  # Default sea-level-ish

    if humidity_pct is None:
        humidity_pct = 50  # Default moderate

    try:
        # Air density decreases ~3% per 1000ft elevation
        elevation_factor = 1 - (elevation_ft / 1000 * 0.03)

        # Humidity: higher = denser air (slight effect)
        humidity_factor = 1 + ((humidity_pct - 50) / 100 * 0.02)

        drag_factor = elevation_factor * humidity_factor

        # High altitude = significant advantage
        if elevation_ft >= 5000:
            score = 1.0
            reason = f"HIGH_ALTITUDE_{int(elevation_ft)}ft"
            triggered = True
        elif elevation_ft >= 3000:
            score = 0.7
            reason = f"MODERATE_ALTITUDE_{int(elevation_ft)}ft"
            triggered = True
        else:
            score = 0.5
            reason = "SEA_LEVEL_NEUTRAL"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "drag_factor": round(drag_factor, 3),
            "elevation_ft": elevation_ft,
            "humidity_pct": humidity_pct
        }

    except Exception as e:
        logger.warning("Barometric calculation error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "drag_factor": 1.0
        }


# =============================================================================
# HURST EXPONENT
# =============================================================================

def calculate_hurst_exponent(price_series: list = None) -> Dict[str, Any]:
    """
    Calculate Hurst exponent to determine trending vs mean-reverting behavior.

    H < 0.5: Mean-reverting (fade recent movement)
    H = 0.5: Random walk (no edge)
    H > 0.5: Trending (follow recent movement)

    Args:
        price_series: List of historical values

    Returns:
        Dict with score, reason, triggered, hurst_value, interpretation
    """
    if not PHYSICS_ENABLED:
        return {
            "score": 0.5,
            "reason": "PHYSICS_DISABLED",
            "triggered": False,
            "hurst_value": None,
            "interpretation": None
        }

    if not price_series or len(price_series) < 10:
        return {
            "score": 0.5,
            "reason": "INSUFFICIENT_DATA",
            "triggered": False,
            "hurst_value": None,
            "interpretation": "UNKNOWN"
        }

    try:
        # Simplified R/S analysis for Hurst exponent
        n = len(price_series)

        # Calculate returns
        returns = [price_series[i] - price_series[i-1] for i in range(1, n)]

        if not returns:
            return {
                "score": 0.5,
                "reason": "NO_RETURNS_DATA",
                "triggered": False,
                "hurst_value": None,
                "interpretation": "UNKNOWN"
            }

        # Mean and standard deviation
        mean_return = sum(returns) / len(returns)
        std_return = math.sqrt(sum((r - mean_return) ** 2 for r in returns) / len(returns))

        if std_return == 0:
            return {
                "score": 0.5,
                "reason": "ZERO_VARIANCE",
                "triggered": False,
                "hurst_value": 0.5,
                "interpretation": "RANDOM_WALK"
            }

        # Cumulative deviations
        cumdev = []
        running_sum = 0
        for r in returns:
            running_sum += (r - mean_return)
            cumdev.append(running_sum)

        # Range / Standard deviation
        R = max(cumdev) - min(cumdev)
        RS = R / std_return if std_return > 0 else 0

        # Hurst approximation: H = log(R/S) / log(n)
        if RS > 0 and n > 1:
            hurst = math.log(RS) / math.log(n)
            hurst = max(0, min(1, hurst))  # Clamp to [0, 1]
        else:
            hurst = 0.5

        # Interpret
        if hurst > 0.6:
            score = 0.8
            reason = "TRENDING_MARKET"
            interpretation = "TRENDING"
            triggered = True
        elif hurst < 0.4:
            score = 0.8
            reason = "MEAN_REVERTING"
            interpretation = "MEAN_REVERTING"
            triggered = True
        else:
            score = 0.5
            reason = "RANDOM_WALK"
            interpretation = "RANDOM"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "hurst_value": round(hurst, 3),
            "interpretation": interpretation
        }

    except Exception as e:
        logger.warning("Hurst calculation error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "hurst_value": None,
            "interpretation": None
        }


# =============================================================================
# KP-INDEX (Geomagnetic Activity)
# =============================================================================

def get_kp_index(game_time: datetime = None) -> Dict[str, Any]:
    """
    Get Kp-index for geomagnetic activity impact.

    The Kp-index measures planetary geomagnetic activity (0-9).
    Higher values indicate geomagnetic storms which may affect
    human behavior and decision-making.

    Args:
        game_time: Game start time

    Returns:
        Dict with score, reason, triggered, kp_value, storm_level
    """
    if not PHYSICS_ENABLED:
        return {
            "score": 0.5,
            "reason": "PHYSICS_DISABLED",
            "triggered": False,
            "kp_value": None,
            "storm_level": None
        }

    # TODO: Integrate with NOAA Space Weather API
    # https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json

    if game_time is None:
        game_time = datetime.now()

    try:
        # Simulate Kp-index based on time (real integration needed)
        # Kp typically ranges 0-9, average ~2-3
        hour = game_time.hour
        day_of_year = game_time.timetuple().tm_yday

        # Base Kp + variations
        base_kp = 2.5
        hourly_var = math.sin(2 * math.pi * hour / 24) * 1.0
        seasonal_var = math.sin(2 * math.pi * day_of_year / 365) * 0.5

        kp_value = max(0, min(9, base_kp + hourly_var + seasonal_var))

        # Storm levels
        if kp_value >= 7:
            storm_level = "SEVERE"
            score = 0.3  # Avoid betting during storms
            reason = "KP_STORM_SEVERE"
            triggered = True
        elif kp_value >= 5:
            storm_level = "MODERATE"
            score = 0.5
            reason = "KP_STORM_MODERATE"
            triggered = True
        elif kp_value <= 2:
            storm_level = "QUIET"
            score = 0.8
            reason = "KP_QUIET_OPTIMAL"
            triggered = True
        else:
            storm_level = "UNSETTLED"
            score = 0.6
            reason = "KP_UNSETTLED"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "kp_value": round(kp_value, 1),
            "storm_level": storm_level,
            "note": "SIMULATED - integrate NOAA Space Weather API"
        }

    except Exception as e:
        logger.warning("Kp-index calculation error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "kp_value": None,
            "storm_level": None
        }


# =============================================================================
# AGGREGATE PHYSICS SCORE
# =============================================================================

def get_physics_score(
    spread: float = 0,
    total: float = 0,
    venue: str = "",
    game_time: datetime = None,
    line_history: list = None
) -> Dict[str, Any]:
    """
    Calculate aggregate physics score from all signals.

    Returns:
        Dict with overall score, all signal breakdowns, and reasons
    """
    results = {
        "gann": calculate_gann_square(spread, total),
        "fibonacci": calculate_fib_retracement(spread if spread else total),
        "schumann": get_schumann_resonance(game_time),
        "barometric": get_barometric_drag(venue),
        "hurst": calculate_hurst_exponent(line_history),
        "kp_index": get_kp_index(game_time),
    }

    # Weights for each signal
    weights = {
        "gann": 0.20,
        "fibonacci": 0.20,
        "schumann": 0.15,
        "barometric": 0.15,
        "hurst": 0.15,
        "kp_index": 0.15,
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
        "physics_score": round(total_score, 3),
        "triggered_count": len(triggered_signals),
        "triggered_signals": triggered_signals,
        "reasons": reasons,
        "breakdown": results,
        "enabled": PHYSICS_ENABLED
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "calculate_gann_square",
    "calculate_fib_retracement",
    "get_schumann_resonance",
    "get_barometric_drag",
    "calculate_hurst_exponent",
    "get_kp_index",
    "get_physics_score",
    "PHYSICS_ENABLED",
]
