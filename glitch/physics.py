"""
Glitch Protocol: Physics Module v1.0
====================================
Arcane physics and mathematical signals for edge detection.

Features:
- Gann Square of Nine (price/spread angles)
- 50% Retracement (Fibonacci levels)
- Schumann Frequency (Earth resonance)
- Atmospheric Drag (barometric pressure)
- Hurst Exponent (trend detection)
- Kp-Index (geomagnetic activity)

Master Audit File: physics.py - MEDIUM PRIORITY
"""

import math
import random
from datetime import datetime, date
from typing import Dict, Any, List, Optional

# =============================================================================
# GANN SQUARE OF NINE
# =============================================================================

def calculate_gann_square(value: float) -> Dict[str, Any]:
    """
    Calculate Gann's Square of Nine angles.

    Key angles: 0°, 45°, 90°, 180°, 270°, 360°
    Values at these angles are considered support/resistance levels.

    Args:
        value: Spread, total, or other numerical value

    Returns:
        Dict with angle, resonance status, and signal strength
    """
    if value <= 0:
        return {
            "available": False,
            "reason": "Value must be positive"
        }

    sqrt_val = math.sqrt(abs(value))
    angle = (sqrt_val - int(sqrt_val)) * 360

    # Check for resonant angles (within 10 degrees of key angles)
    key_angles = [0, 45, 90, 135, 180, 225, 270, 315, 360]
    resonant = any(abs(angle - ka) < 10 or abs(angle - ka) > 350 for ka in key_angles)

    # Determine which angle is closest
    closest_angle = min(
        key_angles,
        key=lambda x: min(abs(angle - x), abs(angle - x + 360), abs(angle - x - 360))
    )

    # Signal strength based on angle
    if resonant and closest_angle in [180, 360, 0]:
        signal = "STRONG"
        boost = 0.25
    elif resonant and closest_angle in [90, 270]:
        signal = "MODERATE"
        boost = 0.15
    elif resonant:
        signal = "WEAK"
        boost = 0.05
    else:
        signal = "NONE"
        boost = 0.0

    return {
        "available": True,
        "module": "physics",
        "signal_type": "GANN_SQUARE",
        "input_value": value,
        "sqrt_value": round(sqrt_val, 4),
        "angle": round(angle, 1),
        "resonant": resonant,
        "closest_key_angle": closest_angle,
        "signal": signal,
        "boost": boost
    }


def analyze_spread_total_gann(spread: float, total: float) -> Dict[str, Any]:
    """
    Analyze both spread and total using Gann's Square.

    Combined resonance is especially powerful.
    """
    spread_gann = calculate_gann_square(abs(spread) if spread else 3.0)
    total_gann = calculate_gann_square(total if total else 200.0)

    combined_resonance = (
        spread_gann.get("resonant", False) and
        total_gann.get("resonant", False)
    )

    if combined_resonance:
        combined_boost = 0.35
        signal = "DOUBLE_RESONANCE"
    elif spread_gann.get("resonant") or total_gann.get("resonant"):
        combined_boost = max(
            spread_gann.get("boost", 0),
            total_gann.get("boost", 0)
        )
        signal = "SINGLE_RESONANCE"
    else:
        combined_boost = 0.0
        signal = "NO_RESONANCE"

    return {
        "available": True,
        "module": "physics",
        "signal_type": "GANN_COMBINED",
        "spread_analysis": spread_gann,
        "total_analysis": total_gann,
        "combined_resonance": combined_resonance,
        "signal": signal,
        "boost": combined_boost
    }


# =============================================================================
# 50% RETRACEMENT (Fibonacci)
# =============================================================================

FIBONACCI_LEVELS = [0.236, 0.382, 0.500, 0.618, 0.786, 1.000]


def calculate_fib_retracement(
    high: float,
    low: float,
    current: float
) -> Dict[str, Any]:
    """
    Calculate Fibonacci retracement level for current value.

    Common levels: 23.6%, 38.2%, 50%, 61.8%, 78.6%
    """
    if high <= low:
        return {"available": False, "reason": "High must be greater than low"}

    range_val = high - low
    retracement = (high - current) / range_val if range_val > 0 else 0.5

    # Find closest Fibonacci level
    closest_fib = min(FIBONACCI_LEVELS, key=lambda x: abs(x - retracement))
    distance_to_fib = abs(retracement - closest_fib)

    # At a Fibonacci level (within 2%)
    at_fib_level = distance_to_fib < 0.02

    if at_fib_level:
        if closest_fib == 0.500:
            signal = "GOLDEN_50"
            boost = 0.30
        elif closest_fib == 0.618:
            signal = "GOLDEN_RATIO"
            boost = 0.25
        elif closest_fib in [0.382, 0.786]:
            signal = "FIB_LEVEL"
            boost = 0.15
        else:
            signal = "MINOR_FIB"
            boost = 0.05
    else:
        signal = "NO_FIB"
        boost = 0.0

    return {
        "available": True,
        "module": "physics",
        "signal_type": "FIB_RETRACEMENT",
        "high": high,
        "low": low,
        "current": current,
        "retracement_pct": round(retracement * 100, 1),
        "closest_fib_level": closest_fib,
        "at_fib_level": at_fib_level,
        "signal": signal,
        "boost": boost
    }


def check_50_retracement(
    season_high: float,
    season_low: float,
    current_line: float
) -> Dict[str, Any]:
    """
    Check if current line is at the 50% retracement of season range.

    The 50% level is considered a key decision point.
    """
    return calculate_fib_retracement(season_high, season_low, current_line)


# =============================================================================
# SCHUMANN FREQUENCY
# =============================================================================

def get_schumann_frequency(target_date: date = None) -> Dict[str, Any]:
    """
    Earth's Schumann resonance baseline is 7.83 Hz.

    Deviations indicate global electromagnetic disturbances.
    Higher readings = increased volatility potential.

    In production, fetch from real-time API (e.g., heartmath.org).
    This implementation uses deterministic daily simulation.
    """
    if target_date is None:
        target_date = date.today()

    # Deterministic "random" based on date
    seed = int(target_date.strftime("%Y%m%d"))
    random.seed(seed)

    base_freq = 7.83
    deviation = (random.random() - 0.5) * 1.0  # ±0.5 Hz typical range
    current_freq = base_freq + deviation

    random.seed()  # Reset

    # Determine status and betting impact
    if abs(deviation) < 0.1:
        status = "NORMAL"
        boost = 0.0
        impact = "Standard conditions"
    elif deviation > 0.3:
        status = "ELEVATED"
        boost = 0.15
        impact = "Increased volatility - favor overs"
    elif deviation < -0.3:
        status = "DEPRESSED"
        boost = -0.10
        impact = "Decreased volatility - favor unders"
    elif deviation > 0:
        status = "SLIGHTLY_ELEVATED"
        boost = 0.05
        impact = "Mild volatility increase"
    else:
        status = "SLIGHTLY_DEPRESSED"
        boost = -0.05
        impact = "Mild volatility decrease"

    return {
        "available": True,
        "module": "physics",
        "signal_type": "SCHUMANN_FREQUENCY",
        "base_hz": base_freq,
        "current_hz": round(current_freq, 2),
        "deviation_hz": round(deviation, 2),
        "status": status,
        "boost": boost,
        "betting_impact": impact
    }


# =============================================================================
# ATMOSPHERIC DRAG (Barometric Pressure)
# =============================================================================

def calculate_atmospheric_drag(pressure_in: float) -> Dict[str, Any]:
    """
    Calculate atmospheric drag betting signal from barometric pressure.

    High pressure (>30.10 inHg) = heavy air = harder to throw/hit = UNDER
    Low pressure (<29.80 inHg) = thin air = ball travels easier = OVER

    Args:
        pressure_in: Barometric pressure in inches of mercury (inHg)

    Returns:
        Dict with signal direction and boost
    """
    if not pressure_in or pressure_in <= 0:
        return {
            "available": False,
            "signal": "NEUTRAL",
            "boost": 0.0,
            "reason": "No pressure data"
        }

    if pressure_in > 30.10:
        return {
            "available": True,
            "module": "physics",
            "signal_type": "ATMOSPHERIC_DRAG",
            "pressure_in": pressure_in,
            "signal": "HEAVY_AIR",
            "direction": "UNDER",
            "boost": 0.20,
            "reason": f"Atmospheric Drag: {pressure_in:.2f} inHg HEAVY AIR (bet under)"
        }
    elif pressure_in < 29.80:
        return {
            "available": True,
            "module": "physics",
            "signal_type": "ATMOSPHERIC_DRAG",
            "pressure_in": pressure_in,
            "signal": "THIN_AIR",
            "direction": "OVER",
            "boost": 0.20,
            "reason": f"Atmospheric Drag: {pressure_in:.2f} inHg THIN AIR (bet over)"
        }
    else:
        return {
            "available": True,
            "module": "physics",
            "signal_type": "ATMOSPHERIC_DRAG",
            "pressure_in": pressure_in,
            "signal": "NEUTRAL",
            "direction": None,
            "boost": 0.0,
            "reason": f"Atmospheric Drag: {pressure_in:.2f} inHg (neutral range)"
        }


def calculate_elevation_drag(city: str, humidity_pct: float = None) -> Dict[str, Any]:
    """
    Calculate atmospheric effects based on venue elevation.

    Higher elevation = less air resistance = more offense (MLB/NFL).
    Higher humidity = heavier air = less offense.
    """
    VENUE_ELEVATIONS = {
        "Denver": 5280, "Salt Lake City": 4226, "Phoenix": 1086,
        "Las Vegas": 2001, "Atlanta": 1050, "Dallas": 430,
        "Los Angeles": 285, "New York": 33, "Miami": 6,
        "Boston": 141, "Chicago": 594, "Detroit": 600,
        "Houston": 80, "San Francisco": 52, "Seattle": 520,
    }

    elevation = VENUE_ELEVATIONS.get(city, 500)

    if humidity_pct is None:
        humid_cities = ["Miami", "Houston", "New Orleans", "Atlanta"]
        dry_cities = ["Denver", "Phoenix", "Las Vegas", "Salt Lake City"]
        if city in humid_cities:
            humidity_pct = 75
        elif city in dry_cities:
            humidity_pct = 30
        else:
            humidity_pct = 50

    # Air density factor (lower = less drag)
    air_density = math.exp(-elevation / 29000)
    humidity_factor = 1 + (humidity_pct - 50) / 200
    drag_coeff = air_density * humidity_factor

    # Offense boost (inverse of drag)
    offense_boost = round((1 - drag_coeff) * 10, 1)

    if offense_boost > 0.5:
        signal = "OVER"
        boost = 0.15
    elif offense_boost < -0.5:
        signal = "UNDER"
        boost = -0.10
    else:
        signal = "NEUTRAL"
        boost = 0.0

    return {
        "available": True,
        "module": "physics",
        "signal_type": "ELEVATION_DRAG",
        "city": city,
        "elevation_ft": elevation,
        "humidity_pct": humidity_pct,
        "air_density": round(air_density, 3),
        "drag_coefficient": round(drag_coeff, 3),
        "offense_boost": offense_boost,
        "signal": signal,
        "boost": boost
    }


# =============================================================================
# HURST EXPONENT (Trend Detection)
# =============================================================================

def calculate_hurst_exponent(time_series: List[float]) -> Dict[str, Any]:
    """
    Calculate Hurst Exponent to determine if series is trending or mean-reverting.

    H > 0.5: Trending (momentum) - follow the streak
    H < 0.5: Mean-reverting - fade the streak
    H ≈ 0.5: Random walk - no edge

    Uses simplified R/S analysis.
    """
    if len(time_series) < 20:
        return {
            "available": False,
            "h_value": 0.5,
            "regime": "INSUFFICIENT_DATA",
            "boost": 0.0,
            "reason": "Need at least 20 data points"
        }

    n = len(time_series)

    # Calculate returns
    returns = [time_series[i] - time_series[i-1] for i in range(1, n)]

    if not returns:
        return {
            "available": False,
            "h_value": 0.5,
            "regime": "NO_RETURNS",
            "boost": 0.0
        }

    mean_return = sum(returns) / len(returns)

    # Cumulative deviation from mean
    cum_dev = []
    running_sum = 0
    for r in returns:
        running_sum += (r - mean_return)
        cum_dev.append(running_sum)

    # Range
    R = max(cum_dev) - min(cum_dev) if cum_dev else 0

    # Standard deviation
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    S = math.sqrt(variance) if variance > 0 else 1

    # R/S ratio
    RS = R / S if S > 0 else 0

    # Estimate H
    H = math.log(RS + 1) / math.log(n) if RS > 0 and n > 1 else 0.5
    H = max(0, min(1, H))

    # Determine regime and boost
    if H > 0.55:
        regime = "TRENDING"
        boost = 0.15
        recommendation = "Follow momentum - ride the streak"
    elif H < 0.45:
        regime = "MEAN_REVERTING"
        boost = 0.15
        recommendation = "Fade extremes - regression expected"
    else:
        regime = "RANDOM_WALK"
        boost = 0.0
        recommendation = "No statistical edge"

    return {
        "available": True,
        "module": "physics",
        "signal_type": "HURST_EXPONENT",
        "h_value": round(H, 3),
        "regime": regime,
        "confidence": round(abs(H - 0.5) * 2, 2),
        "boost": boost,
        "recommendation": recommendation,
        "sample_size": n
    }


# =============================================================================
# KP-INDEX (Geomagnetic Activity)
# =============================================================================

def get_kp_index(target_date: date = None) -> Dict[str, Any]:
    """
    Kp-Index measures geomagnetic activity (0-9 scale).

    High Kp (>5): Geomagnetic storm - increased volatility
    Low Kp (<2): Quiet conditions - normal variance

    In production, fetch from NOAA Space Weather.
    This implementation uses deterministic simulation.
    """
    if target_date is None:
        target_date = date.today()

    # Deterministic based on date
    seed = int(target_date.strftime("%Y%m%d")) + 42
    random.seed(seed)

    # Kp typically follows exponential distribution (most days are quiet)
    kp = random.expovariate(0.5)
    kp = min(9, max(0, kp))

    random.seed()

    if kp >= 5:
        status = "STORM"
        boost = 0.20
        impact = "Geomagnetic storm - expect volatility"
    elif kp >= 4:
        status = "ACTIVE"
        boost = 0.10
        impact = "Active conditions - slight volatility increase"
    elif kp >= 2:
        status = "UNSETTLED"
        boost = 0.0
        impact = "Normal conditions"
    else:
        status = "QUIET"
        boost = -0.05
        impact = "Quiet conditions - favor favorites"

    return {
        "available": True,
        "module": "physics",
        "signal_type": "KP_INDEX",
        "kp_value": round(kp, 1),
        "status": status,
        "boost": boost,
        "betting_impact": impact
    }


# =============================================================================
# AGGREGATED PHYSICS SCORE
# =============================================================================

def get_physics_signals(
    spread: float = None,
    total: float = None,
    pressure_in: float = None,
    city: str = None,
    recent_scores: List[float] = None
) -> Dict[str, Any]:
    """
    Aggregate all physics signals for a matchup.

    Returns individual signals plus combined physics score.
    """
    signals = {}
    total_boost = 0.0
    fired_modules = []

    # Gann Square (if spread/total provided)
    if spread is not None and total is not None:
        gann = analyze_spread_total_gann(spread, total)
        signals["gann_square"] = gann
        if gann["boost"] > 0:
            total_boost += gann["boost"]
            fired_modules.append("GANN")

    # Schumann Frequency (always available)
    schumann = get_schumann_frequency()
    signals["schumann"] = schumann
    if schumann["boost"] != 0:
        total_boost += schumann["boost"]
        fired_modules.append("SCHUMANN")

    # Atmospheric Drag (if pressure provided)
    if pressure_in:
        atmo = calculate_atmospheric_drag(pressure_in)
        signals["atmospheric_drag"] = atmo
        if atmo.get("boost", 0) != 0:
            total_boost += atmo["boost"]
            fired_modules.append("ATMOSPHERIC")

    # Elevation Drag (if city provided)
    if city:
        elevation = calculate_elevation_drag(city)
        signals["elevation_drag"] = elevation
        if elevation["boost"] != 0:
            total_boost += elevation["boost"]
            fired_modules.append("ELEVATION")

    # Hurst Exponent (if recent scores provided)
    if recent_scores and len(recent_scores) >= 20:
        hurst = calculate_hurst_exponent(recent_scores)
        signals["hurst"] = hurst
        if hurst.get("boost", 0) != 0:
            total_boost += hurst["boost"]
            fired_modules.append("HURST")

    # Kp-Index (always available)
    kp = get_kp_index()
    signals["kp_index"] = kp
    if kp["boost"] != 0:
        total_boost += kp["boost"]
        fired_modules.append("KP_INDEX")

    return {
        "available": True,
        "module": "physics",
        "signals": signals,
        "total_boost": round(total_boost, 3),
        "fired_modules": fired_modules,
        "modules_fired_count": len(fired_modules)
    }
