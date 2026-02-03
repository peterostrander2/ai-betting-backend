"""
Esoteric Engine v1.0
Comprehensive esoteric signals for sports betting analysis.

10 Signals across 4 categories:
- JARVIS/Symbolic: Founder's Echo, Life Path Sync, Biorhythms
- Arcane Physics: Gann's Square, 50% Retracement, Schumann, Atmospheric, Hurst
- Collective/Sentiment: Noosphere Velocity, Void Moon
- Parlay: Teammate Void, Correlation Matrix
"""

import math
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
import random
import hashlib

# Import comprehensive player birth data
from player_birth_data import get_all_players, get_player_data, get_players_by_sport, PLAYER_COUNTS

# Import astronomical calculations for accurate moon data
from astronomical_api import (
    get_live_moon_data,
    get_moon_sign_now,
    is_void_moon_now,
    get_moon_betting_signal,
    calculate_void_of_course,
    calculate_moon_phase
)

# =============================================================================
# TEAM FOUNDING YEARS DATABASE
# =============================================================================

TEAM_FOUNDING_YEARS = {
    # NBA
    "Lakers": 1947, "Celtics": 1946, "Warriors": 1946, "Bulls": 1966,
    "Heat": 1988, "Knicks": 1946, "Nets": 1967, "76ers": 1946,
    "Bucks": 1968, "Suns": 1968, "Mavericks": 1980, "Nuggets": 1967,
    "Clippers": 1970, "Grizzlies": 1995, "Pelicans": 2002, "Spurs": 1967,
    "Hawks": 1946, "Cavaliers": 1970, "Pistons": 1941, "Pacers": 1967,
    "Magic": 1989, "Wizards": 1961, "Hornets": 1988, "Raptors": 1995,
    "Timberwolves": 1989, "Trail Blazers": 1970, "Thunder": 1967,
    "Jazz": 1974, "Kings": 1945, "Rockets": 1967,
    # NFL
    "Chiefs": 1960, "49ers": 1946, "Eagles": 1933, "Bills": 1960,
    "Cowboys": 1960, "Dolphins": 1966, "Patriots": 1960, "Ravens": 1996,
    "Packers": 1919, "Steelers": 1933, "Broncos": 1960, "Raiders": 1960,
    "Chargers": 1960, "Jets": 1960, "Giants": 1925, "Bears": 1919,
    "Lions": 1930, "Vikings": 1961, "Saints": 1967, "Buccaneers": 1976,
    "Falcons": 1966, "Panthers": 1995, "Seahawks": 1976, "Cardinals": 1898,
    "Rams": 1936, "Browns": 1946, "Bengals": 1968, "Titans": 1960,
    "Colts": 1953, "Texans": 2002, "Jaguars": 1995, "Commanders": 1932,
    # MLB
    "Yankees": 1901, "Red Sox": 1901, "Dodgers": 1883, "Cubs": 1876,
    "Giants": 1883, "Cardinals": 1882, "Braves": 1871, "Astros": 1962,
    "Mets": 1962, "Phillies": 1883, "White Sox": 1901, "Tigers": 1901,
    "Twins": 1901, "Indians": 1901, "Guardians": 1901, "Athletics": 1901,
    "Mariners": 1977, "Rangers": 1961, "Blue Jays": 1977, "Rays": 1998,
    "Marlins": 1993, "Rockies": 1993, "Diamondbacks": 1998, "Padres": 1969,
    "Reds": 1881, "Brewers": 1969, "Pirates": 1882, "Royals": 1969,
    "Orioles": 1901, "Angels": 1961, "Nationals": 1969,
    # NHL
    "Bruins": 1924, "Blackhawks": 1926, "Red Wings": 1926, "Rangers": 1926,
    "Maple Leafs": 1917, "Canadiens": 1909, "Penguins": 1967, "Flyers": 1967,
    "Blues": 1967, "Kings": 1967, "Sharks": 1991, "Avalanche": 1972,
    "Lightning": 1992, "Stars": 1967, "Oilers": 1972, "Flames": 1972,
    "Canucks": 1970, "Senators": 1992, "Panthers": 1993, "Hurricanes": 1972,
    "Devils": 1974, "Islanders": 1972, "Capitals": 1974, "Predators": 1998,
    "Wild": 2000, "Blue Jackets": 2000, "Coyotes": 1972, "Jets": 1999,
    "Golden Knights": 2017, "Kraken": 2021, "Ducks": 1993, "Sabres": 1970,
}

# Player data loaded from player_birth_data.py
# Contains 200+ real player birth dates across NBA, NFL, MLB, NHL, NCAAB
SAMPLE_PLAYERS = get_all_players()  # Backwards compatible alias

# Venue elevations (feet above sea level)
VENUE_ELEVATIONS = {
    "Denver": 5280, "Salt Lake City": 4226, "Phoenix": 1086,
    "Las Vegas": 2001, "Atlanta": 1050, "Dallas": 430,
    "Los Angeles": 285, "New York": 33, "Miami": 6,
    "Boston": 141, "Chicago": 594, "Detroit": 600,
    "Houston": 80, "San Francisco": 52, "Seattle": 520,
}


# =============================================================================
# 1. BIORHYTHMS (esoteric.py - High Priority)
# =============================================================================

def calculate_biorhythms(birth_date_str: str, target_date: date = None) -> Dict[str, Any]:
    """
    Calculate physical, emotional, and intellectual biorhythm cycles.

    Physical cycle: 23 days
    Emotional cycle: 28 days
    Intellectual cycle: 33 days
    """
    if target_date is None:
        target_date = date.today()

    try:
        if isinstance(birth_date_str, str):
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        else:
            birth_date = birth_date_str
    except:
        # Default to a sample date if parsing fails
        birth_date = date(1990, 1, 1)

    days_alive = (target_date - birth_date).days

    physical = math.sin(2 * math.pi * days_alive / 23) * 100
    emotional = math.sin(2 * math.pi * days_alive / 28) * 100
    intellectual = math.sin(2 * math.pi * days_alive / 33) * 100

    # Overall biorhythm score
    overall = (physical + emotional + intellectual) / 3

    # Determine status
    if overall > 50:
        status = "PEAK"
    elif overall > 0:
        status = "RISING"
    elif overall > -50:
        status = "FALLING"
    else:
        status = "LOW"

    return {
        "physical": round(physical, 1),
        "emotional": round(emotional, 1),
        "intellectual": round(intellectual, 1),
        "overall": round(overall, 1),
        "status": status,
        "days_alive": days_alive
    }


# =============================================================================
# 2. VOID MOON FILTER (hive_mind.py - High Priority)
# =============================================================================

def calculate_void_moon(target_date: date = None) -> Dict[str, Any]:
    """
    Calculate void-of-course moon periods using astronomical ephemeris.
    Moon is void when it makes no major aspects before leaving its sign.

    Now uses high-accuracy calculations from astronomical_api module.
    """
    if target_date is None:
        target_date = date.today()

    # Use astronomical calculations
    dt = datetime.combine(target_date, datetime.now().time())
    voc_data = calculate_void_of_course(dt)
    phase_data = calculate_moon_phase(dt)

    return {
        "is_void": voc_data["is_void"],
        "void_start": voc_data["void_start"],
        "void_end": voc_data["void_end"],
        "confidence": voc_data["confidence"],
        "warning": voc_data["warning"],
        "moon_sign": voc_data["moon_sign"],
        "degree_in_sign": voc_data["degree_in_sign"],
        "hours_until_sign_change": voc_data["hours_until_sign_change"],
        "next_sign": voc_data["next_sign"],
        "phase": phase_data["phase_name"],
        "illumination": phase_data["illumination"],
        "source": "astronomical_ephemeris"
    }


def get_current_moon_sign(target_date: date = None) -> str:
    """Get current moon sign using astronomical calculations."""
    if target_date is None:
        return get_moon_sign_now()

    dt = datetime.combine(target_date, datetime.now().time())
    voc = calculate_void_of_course(dt)
    return voc["moon_sign"]


# =============================================================================
# 3. TEAMMATE VOID (parlay_architect.py - High Priority)
# =============================================================================

def check_teammate_void(legs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Check for same-team props that cannibalize each other.
    Returns warnings for correlated legs.
    """
    warnings = []
    teams = {}

    for i, leg in enumerate(legs):
        player_team = leg.get("team") or leg.get("player_team")
        player_name = leg.get("player") or leg.get("player_name", f"Player {i+1}")
        description = leg.get("description") or f"{player_name} {leg.get('selection', 'prop')}"

        if player_team:
            if player_team in teams:
                warnings.append({
                    "type": "TEAMMATE_VOID",
                    "legs": [teams[player_team]["description"], description],
                    "players": [teams[player_team]["player"], player_name],
                    "team": player_team,
                    "reason": "Same-team props cannibalize each other",
                    "correlation": -0.35,
                    "recommendation": "Consider removing one leg"
                })
            else:
                teams[player_team] = {"description": description, "player": player_name}

    return warnings


# =============================================================================
# 4. GANN'S SQUARE OF NINE (physics.py - Medium Priority)
# =============================================================================

def calculate_gann_square(value: float) -> Dict[str, Any]:
    """
    Calculate Gann's Square of Nine angles.
    Key angles: 0°, 45°, 90°, 180°, 270°, 360°
    """
    sqrt_val = math.sqrt(abs(value))
    angle = (sqrt_val - int(sqrt_val)) * 360

    # Check for resonant angles (within 10 degrees of key angles)
    key_angles = [0, 45, 90, 135, 180, 225, 270, 315, 360]
    resonant = any(abs(angle - ka) < 10 or abs(angle - ka) > 350 for ka in key_angles)

    # Determine which angle is closest
    closest_angle = min(key_angles, key=lambda x: min(abs(angle - x), abs(angle - x + 360), abs(angle - x - 360)))

    return {
        "input_value": value,
        "sqrt_value": round(sqrt_val, 4),
        "angle": round(angle, 1),
        "resonant": resonant,
        "closest_key_angle": closest_angle,
        "signal": "STRONG" if resonant and closest_angle in [180, 360] else "MODERATE" if resonant else "WEAK"
    }


def analyze_spread_gann(spread: float, total: float) -> Dict[str, Any]:
    """Analyze both spread and total using Gann's Square."""
    spread_gann = calculate_gann_square(spread)
    total_gann = calculate_gann_square(total)

    return {
        "spread": spread_gann,
        "total": total_gann,
        "combined_resonance": spread_gann["resonant"] and total_gann["resonant"],
        "recommendation": "Strong Gann alignment" if spread_gann["resonant"] and total_gann["resonant"] else None
    }


# =============================================================================
# 5. FOUNDER'S ECHO (esoteric.py - Medium Priority)
# =============================================================================

def calculate_gematria(text: str) -> int:
    """Simple gematria calculation (A=1, B=2, etc.)"""
    text = text.upper().replace(" ", "")
    return sum(ord(c) - 64 for c in text if c.isalpha())


def check_founders_echo(team_name: str, target_date: date = None) -> Dict[str, Any]:
    """
    Check if team name gematria resonates with founding year.
    """
    if target_date is None:
        target_date = date.today()

    # Get founding year
    founding_year = TEAM_FOUNDING_YEARS.get(team_name, 1900)

    # Calculate gematria of team name
    team_gematria = calculate_gematria(team_name)

    # Check various resonance patterns
    year_sum = sum(int(d) for d in str(founding_year))
    current_year_sum = sum(int(d) for d in str(target_date.year))

    # Resonance checks
    direct_match = team_gematria == year_sum
    harmonic_match = team_gematria % year_sum == 0 if year_sum > 0 else False
    year_alignment = (target_date.year - founding_year) % team_gematria == 0 if team_gematria > 0 else False

    resonance = direct_match or harmonic_match or year_alignment

    return {
        "team": team_name,
        "founding_year": founding_year,
        "team_gematria": team_gematria,
        "year_sum": year_sum,
        "direct_match": direct_match,
        "harmonic_match": harmonic_match,
        "year_alignment": year_alignment,
        "resonance": resonance,
        "boost": 5 if resonance else 0
    }


# =============================================================================
# 6. HURST EXPONENT (physics.py - Medium Priority)
# =============================================================================

def calculate_hurst_exponent(time_series: List[float]) -> Dict[str, Any]:
    """
    Calculate Hurst Exponent to determine if series is trending or mean-reverting.
    H > 0.5: Trending (momentum)
    H < 0.5: Mean-reverting
    H ≈ 0.5: Random walk

    Simplified R/S analysis implementation.
    """
    if len(time_series) < 20:
        # Not enough data, return neutral
        return {
            "h_value": 0.5,
            "regime": "INSUFFICIENT_DATA",
            "confidence": 0.0
        }

    n = len(time_series)

    # Calculate returns
    returns = [time_series[i] - time_series[i-1] for i in range(1, n)]

    # Mean and std
    mean_return = sum(returns) / len(returns)

    # Cumulative deviation from mean
    cum_dev = []
    running_sum = 0
    for r in returns:
        running_sum += (r - mean_return)
        cum_dev.append(running_sum)

    # Range
    R = max(cum_dev) - min(cum_dev)

    # Standard deviation
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    S = math.sqrt(variance) if variance > 0 else 1

    # R/S ratio
    RS = R / S if S > 0 else 0

    # Estimate H (simplified - full implementation uses multiple scales)
    H = math.log(RS + 1) / math.log(n) if RS > 0 and n > 1 else 0.5
    H = max(0, min(1, H))  # Clamp to [0, 1]

    # Determine regime
    if H > 0.55:
        regime = "TRENDING"
    elif H < 0.45:
        regime = "MEAN_REVERTING"
    else:
        regime = "RANDOM_WALK"

    return {
        "h_value": round(H, 3),
        "regime": regime,
        "confidence": abs(H - 0.5) * 2,  # How far from random
        "recommendation": "Follow momentum" if regime == "TRENDING" else "Fade extremes" if regime == "MEAN_REVERTING" else "No edge"
    }


# =============================================================================
# 7. SCHUMANN FREQUENCY (physics.py - Low Priority)
# =============================================================================

def get_schumann_frequency(target_date: date = None) -> Dict[str, Any]:
    """
    Earth's Schumann resonance is 7.83 Hz.
    Deviations can indicate global electromagnetic disturbances.

    In production, fetch from a real-time API.
    This simulation creates deterministic daily values.
    """
    if target_date is None:
        target_date = date.today()

    # Deterministic "random" based on date
    seed = int(target_date.strftime("%Y%m%d"))
    random.seed(seed)

    # Base frequency with daily variation ±0.5 Hz
    base_freq = 7.83
    deviation = (random.random() - 0.5) * 1.0  # ±0.5 Hz
    current_freq = base_freq + deviation

    random.seed()  # Reset

    # Determine status
    if abs(deviation) < 0.1:
        status = "NORMAL"
    elif abs(deviation) < 0.3:
        status = "SLIGHTLY_ELEVATED" if deviation > 0 else "SLIGHTLY_DEPRESSED"
    else:
        status = "ELEVATED" if deviation > 0 else "DEPRESSED"

    return {
        "base_hz": base_freq,
        "current_hz": round(current_freq, 2),
        "deviation": round(deviation, 2),
        "status": status,
        "betting_impact": "Increased volatility expected" if abs(deviation) > 0.3 else "Normal conditions"
    }


# =============================================================================
# 8. ATMOSPHERIC DRAG (physics.py - Sport-Specific)
# =============================================================================

def calculate_atmospheric_drag(city: str, humidity_pct: float = None) -> Dict[str, Any]:
    """
    Calculate atmospheric effects on outdoor sports.
    Higher elevation = less air resistance = more offense (MLB/NFL)
    Higher humidity = heavier air = less offense
    """
    elevation = VENUE_ELEVATIONS.get(city, 500)

    if humidity_pct is None:
        # Default based on city
        humid_cities = ["Miami", "Houston", "New Orleans", "Atlanta"]
        dry_cities = ["Denver", "Phoenix", "Las Vegas", "Salt Lake City"]
        if city in humid_cities:
            humidity_pct = 75
        elif city in dry_cities:
            humidity_pct = 30
        else:
            humidity_pct = 50

    # Air density factor (lower = less drag)
    # At sea level = 1.0, decreases with elevation
    air_density = math.exp(-elevation / 29000)  # Simplified barometric formula

    # Humidity effect
    humidity_factor = 1 + (humidity_pct - 50) / 200  # Slight effect

    # Combined drag coefficient
    drag_coeff = air_density * humidity_factor

    # Offense boost (inverse of drag)
    offense_boost = round((1 - drag_coeff) * 10, 1)

    return {
        "city": city,
        "elevation_ft": elevation,
        "humidity_pct": humidity_pct,
        "air_density": round(air_density, 3),
        "drag_coefficient": round(drag_coeff, 3),
        "offense_boost": offense_boost,
        "recommendation": "Lean OVER" if offense_boost > 0.5 else "Lean UNDER" if offense_boost < -0.5 else "Neutral"
    }


# =============================================================================
# 9. GENERIC NUMEROLOGY (v12.0 - Required in Esoteric Engine)
# =============================================================================

def calculate_generic_numerology(value: any, context: str = "general") -> Dict[str, Any]:
    """
    Calculate generic numerology signals for any numeric value.

    This is DISTINCT from Jarvis numerology (sacred triggers like 2178, 201, 33).
    Generic numerology covers:
    - Life path numbers
    - Master numbers (11, 22, 33)
    - Tesla numbers (3, 6, 9)
    - Pythagorean reduction
    - Expression numbers

    Args:
        value: Any value to analyze (number or string)
        context: Context for numerology ("player", "game", "spread", "total", "general")

    Returns:
        Dict with numerology analysis
    """
    # Convert value to number if string
    if isinstance(value, str):
        # Calculate expression number from string
        char_values = {chr(i): (i - 96) % 9 or 9 for i in range(97, 123)}
        numeric_value = sum(char_values.get(c, 0) for c in value.lower() if c.isalpha())
    else:
        numeric_value = int(abs(value)) if value else 0

    # Pythagorean reduction (reduce to single digit or master number)
    reduced = numeric_value
    while reduced > 9 and reduced not in [11, 22, 33]:
        reduced = sum(int(d) for d in str(reduced))

    # Check for special numbers
    is_master_number = reduced in [11, 22, 33]
    is_tesla_number = reduced in [3, 6, 9]
    is_power_number = numeric_value in [11, 22, 33, 44, 55, 66, 77, 88, 99]

    # Calculate signal strength
    signal_strength = 0.0
    signals_hit = []

    if is_master_number:
        signal_strength += 0.3
        signals_hit.append(f"Master Number {reduced}")

    if is_tesla_number:
        signal_strength += 0.2
        signals_hit.append(f"Tesla Number {reduced}")

    if is_power_number:
        signal_strength += 0.15
        signals_hit.append(f"Power Number {numeric_value}")

    # Digital root analysis
    digital_root = reduced if reduced <= 9 else sum(int(d) for d in str(reduced))

    # Context-specific bonuses
    if context == "spread" and 3 <= numeric_value <= 7:
        signal_strength += 0.1
        signals_hit.append("Goldilocks spread zone")
    elif context == "total" and digital_root == 9:
        signal_strength += 0.1
        signals_hit.append("Total reduces to completion (9)")

    return {
        "input_value": value,
        "numeric_value": numeric_value,
        "pythagorean_reduction": reduced,
        "digital_root": digital_root,
        "is_master_number": is_master_number,
        "is_tesla_number": is_tesla_number,
        "is_power_number": is_power_number,
        "signal_strength": round(signal_strength, 2),
        "signals_hit": signals_hit,
        "context": context,
        "score": round(5.0 + signal_strength * 10, 1)  # Convert to 0-10 scale centered at 5
    }


def calculate_life_path(birth_date_str: str) -> int:
    """Calculate numerology life path number from birth date."""
    try:
        if isinstance(birth_date_str, str):
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d")
        else:
            birth_date = birth_date_str

        # Sum all digits until single digit (or master number)
        date_str = birth_date.strftime("%Y%m%d")
        total = sum(int(d) for d in date_str)

        while total > 9 and total not in [11, 22, 33]:
            total = sum(int(d) for d in str(total))

        return total
    except:
        return 5  # Default


def check_life_path_sync(player_name: str, birth_date_str: str, jersey_number: int) -> Dict[str, Any]:
    """
    Check alignment between player's life path number and jersey number.
    """
    life_path = calculate_life_path(birth_date_str)

    # Jersey number reduction
    jersey_reduced = jersey_number
    while jersey_reduced > 9 and jersey_reduced not in [11, 22, 33]:
        jersey_reduced = sum(int(d) for d in str(jersey_reduced))

    # Sync score calculation
    if life_path == jersey_reduced:
        sync_score = 100
        sync_type = "PERFECT_MATCH"
    elif life_path + jersey_reduced == 9:
        sync_score = 75
        sync_type = "COMPLEMENTARY"
    elif abs(life_path - jersey_reduced) <= 2:
        sync_score = 50
        sync_type = "HARMONIC"
    else:
        sync_score = 25
        sync_type = "NEUTRAL"

    return {
        "player": player_name,
        "birth_date": birth_date_str,
        "life_path": life_path,
        "jersey_number": jersey_number,
        "jersey_reduced": jersey_reduced,
        "sync_score": sync_score,
        "sync_type": sync_type
    }


# =============================================================================
# 10. NOOSPHERE VELOCITY (hive_mind.py - Low Priority)
# =============================================================================

def calculate_noosphere_velocity(target_date: date = None) -> Dict[str, Any]:
    """
    Measure collective consciousness sentiment velocity.
    In production, would integrate with social media APIs.

    This simulation creates deterministic daily sentiment.
    """
    if target_date is None:
        target_date = date.today()

    # Deterministic based on date
    seed = int(target_date.strftime("%Y%m%d"))
    random.seed(seed)

    # Sentiment velocity (-5 to +5)
    velocity = (random.random() - 0.5) * 10

    # Direction
    if velocity > 1.5:
        direction = "BULLISH"
    elif velocity < -1.5:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    # Confidence based on magnitude
    confidence = min(abs(velocity) / 5, 1.0)

    random.seed()  # Reset

    return {
        "sentiment_velocity": round(velocity, 2),
        "trending_direction": direction,
        "confidence": round(confidence, 2),
        "collective_mood": "Optimistic" if direction == "BULLISH" else "Pessimistic" if direction == "BEARISH" else "Mixed",
        "betting_bias": "Favorites may be overvalued" if direction == "BULLISH" else "Underdogs may have value" if direction == "BEARISH" else "No clear bias"
    }


# =============================================================================
# 50% RETRACEMENT (physics.py - Bonus)
# =============================================================================

def calculate_fibonacci_retracement(current_line: float, season_high: float, season_low: float) -> Dict[str, Any]:
    """
    Check if current line is near Fibonacci retracement levels.
    Key levels: 23.6%, 38.2%, 50%, 61.8%, 78.6%
    """
    if season_high == season_low:
        return {"error": "No range to calculate"}

    range_size = season_high - season_low
    retracement_pct = ((current_line - season_low) / range_size) * 100

    fib_levels = [23.6, 38.2, 50.0, 61.8, 78.6]

    # Find closest fib level
    closest_fib = min(fib_levels, key=lambda x: abs(retracement_pct - x))
    distance_to_fib = abs(retracement_pct - closest_fib)

    near_fib = distance_to_fib < 3  # Within 3%

    return {
        "current_line": current_line,
        "season_high": season_high,
        "season_low": season_low,
        "retracement_pct": round(retracement_pct, 1),
        "closest_fib_level": closest_fib,
        "near_fib_level": near_fib,
        "signal": "REVERSAL_ZONE" if near_fib and closest_fib == 50.0 else "FIB_SUPPORT" if near_fib else "NO_SIGNAL"
    }


# =============================================================================
# 11. VORTEX ENERGY (Tesla 3-6-9 Resonance)
# =============================================================================

def calculate_vortex_energy(value: float, context: str = "general") -> Dict[str, Any]:
    """
    Calculate vortex energy using Tesla's 3-6-9 sacred geometry.

    Tesla believed 3, 6, and 9 were keys to the universe.
    When a value's digital root is 3, 6, or 9, it has inherent harmonic resonance.

    Vortex patterns:
    - Digital root 3/6/9: Tesla alignment (strong)
    - Contains 369/396/639/693/936/963: Perfect vortex (very strong)
    - Phi ratio (1.618) alignment: Golden vortex (moderate)

    Args:
        value: The numeric value to analyze (spread, total, prop line)
        context: "spread", "total", "prop", or "general"

    Returns:
        Dict with vortex_score (0-10), digital_root, tesla_aligned, triggered
    """
    if value is None or value == 0:
        return {
            "vortex_score": 5.0,
            "digital_root": 0,
            "is_tesla_aligned": False,
            "is_perfect_vortex": False,
            "is_golden_vortex": False,
            "triggered": False,
            "signal": "NO_VALUE",
            "confidence": 0.0,
        }

    # Calculate digital root (reduce to single digit)
    abs_val = abs(value)
    str_val = str(abs_val).replace(".", "").replace("-", "")

    digit_sum = sum(int(d) for d in str_val if d.isdigit())
    while digit_sum > 9:
        digit_sum = sum(int(d) for d in str(digit_sum))
    digital_root = digit_sum

    # Check Tesla alignment (3, 6, 9)
    is_tesla = digital_root in [3, 6, 9]

    # Check for perfect vortex patterns (contains 369 sequence)
    vortex_patterns = ["369", "396", "639", "693", "936", "963"]
    str_check = str(int(abs_val * 10))  # Include one decimal
    is_perfect_vortex = any(p in str_check for p in vortex_patterns)

    # Check golden ratio alignment (within 5% of phi multiples)
    PHI = 1.618033988749
    phi_multiples = [PHI, PHI * 2, PHI * 3, PHI * 10, PHI * 100]
    is_golden = any(abs(abs_val - pm) / pm < 0.05 for pm in phi_multiples if pm > 0)

    # Calculate vortex score (0-10)
    vortex_score = 5.0  # Baseline

    if is_perfect_vortex:
        vortex_score = 9.0  # Very strong
    elif is_tesla and is_golden:
        vortex_score = 8.5  # Strong combination
    elif is_tesla:
        vortex_score = 7.5  # Tesla alignment
    elif is_golden:
        vortex_score = 6.5  # Golden ratio
    elif digital_root in [1, 4, 7]:  # Secondary harmony
        vortex_score = 5.5

    # Context-specific adjustments
    if context == "spread" and abs_val in [3, 6, 9, 3.5, 6.5, 9.5]:
        vortex_score += 0.5  # Key spread numbers
    elif context == "total" and digital_root == 9:
        vortex_score += 0.3  # 9 is completion energy for totals

    triggered = vortex_score >= 7.0

    return {
        "value": value,
        "digital_root": digital_root,
        "is_tesla_aligned": is_tesla,
        "is_perfect_vortex": is_perfect_vortex,
        "is_golden_vortex": is_golden,
        "vortex_score": min(10.0, round(vortex_score, 2)),
        "triggered": triggered,
        "signal": "PERFECT_VORTEX" if is_perfect_vortex else "TESLA_ALIGNED" if is_tesla else "GOLDEN_RATIO" if is_golden else "NEUTRAL",
        "confidence": 0.9 if is_perfect_vortex else 0.7 if is_tesla else 0.5 if is_golden else 0.3,
    }


# =============================================================================
# 12. PHOENIX CHRONOLOGY (Archaix - Jason Breshears Research)
# =============================================================================
# Phoenix Cycles from Archaix research:
# - 1656 years: Major Phoenix/destruction cycle (Rashi wrote "world destroyed every 1656 years")
# - 552 years: Sub-cycle (1656 / 3), Anno Domini Reset interval
# - 138 years: Plasma/regional apocalypse cycle (2178 AD = 138 years after 2040 Phoenix)
#
# The 2178 Immortal Loop: Mathematical constant that never collapses
# - 2178 × 4 = 8712 (its own reverse)
# - 2178 - 8712 = 6534, 6534 - 4356 = 2178 (infinite loop)
#
# Historical Phoenix dates: 3895 BC, 2239 BC, 1687 BC, 31 BC, 522 AD, 2178 AD

PHOENIX_CYCLES = {
    1656: {"name": "THE PHOENIX", "strength": 1.0, "description": "Major destruction cycle"},
    552: {"name": "PHOENIX FRAGMENT", "strength": 0.8, "description": "Sub-cycle (1656/3)"},
    138: {"name": "PLASMA CYCLE", "strength": 0.7, "description": "Regional cataclysm interval"},
}

# Key Phoenix historical dates (years only, using approximate values)
PHOENIX_ANCHOR_YEARS = [
    -3895,  # Genesis Reset cataclysm
    -2239,  # Great Flood, Vapor Canopy collapse
    -1687,  # Bronze Age collapse, Phoenix in sky
    -31,    # Ancient Americas devastation
    522,    # Anno Domini Reset
    2040,   # Projected Phoenix (from Archaix)
    2178,   # Portal/Terminus (138 years after 2040)
]


def calculate_phoenix_resonance(game_date: date = None) -> Dict[str, Any]:
    """
    Calculate Phoenix cycle resonance for a game date.

    Checks if the current year aligns with Phoenix cycles (138, 552, 1656)
    from historical anchor dates.

    Based on Archaix research by Jason Breshears:
    - Every 1656 years: Major Phoenix destruction cycle
    - Every 552 years: Sub-cycle (1656/3)
    - Every 138 years: Regional plasma events

    Args:
        game_date: Date to check (default: today)

    Returns:
        Dict with:
        - phoenix_score: 0-10 resonance score
        - cycles_hit: List of matching cycles
        - closest_anchor: Nearest Phoenix anchor date
        - triggered: True if significant resonance
        - boost: Suggested score boost (0.0 to 0.5)
    """
    from datetime import date as date_type

    if game_date is None:
        game_date = date_type.today()

    current_year = game_date.year
    cycles_hit = []
    best_resonance = 0.0

    # Check alignment with each Phoenix cycle from each anchor
    for anchor_year in PHOENIX_ANCHOR_YEARS:
        years_diff = abs(current_year - anchor_year)

        for cycle_years, cycle_info in PHOENIX_CYCLES.items():
            # Check if years_diff is a multiple of cycle (with tolerance)
            if years_diff == 0:
                continue

            remainder = years_diff % cycle_years
            # Allow 0-2 year tolerance for alignment
            if remainder <= 2 or remainder >= (cycle_years - 2):
                cycles_complete = years_diff // cycle_years
                alignment_strength = 1.0 - (min(remainder, cycle_years - remainder) / cycle_years)

                cycles_hit.append({
                    "cycle": cycle_years,
                    "name": cycle_info["name"],
                    "anchor_year": anchor_year,
                    "cycles_complete": cycles_complete,
                    "alignment": round(alignment_strength, 3),
                    "strength": cycle_info["strength"]
                })

                resonance = alignment_strength * cycle_info["strength"]
                if resonance > best_resonance:
                    best_resonance = resonance

    # Calculate phoenix score (0-10)
    if not cycles_hit:
        phoenix_score = 5.0  # Neutral
        triggered = False
        boost = 0.0
    else:
        # Score based on number of cycles hit and their strength
        unique_cycles = len(set(c["cycle"] for c in cycles_hit))
        phoenix_score = 5.0 + (unique_cycles * 1.0) + (best_resonance * 2.0)
        phoenix_score = min(10.0, phoenix_score)

        # Major resonance: hitting 1656 cycle or multiple cycles
        if any(c["cycle"] == 1656 for c in cycles_hit):
            phoenix_score += 0.5
            triggered = True
            boost = 0.3
        elif unique_cycles >= 2:
            triggered = True
            boost = 0.2
        elif best_resonance >= 0.9:
            triggered = True
            boost = 0.15
        else:
            triggered = False
            boost = 0.0

    # Find closest anchor for context
    closest_anchor = min(PHOENIX_ANCHOR_YEARS, key=lambda y: abs(current_year - y))

    # Build signal string
    if cycles_hit:
        top_cycle = max(cycles_hit, key=lambda c: c["strength"] * c["alignment"])
        signal = f"PHOENIX_{top_cycle['name'].replace(' ', '_').upper()}"
    else:
        signal = "NO_PHOENIX_ALIGNMENT"

    return {
        "game_date": game_date.isoformat(),
        "current_year": current_year,
        "phoenix_score": round(phoenix_score, 2),
        "cycles_hit": cycles_hit[:5],  # Top 5 for brevity
        "cycles_hit_count": len(cycles_hit),
        "closest_anchor": closest_anchor,
        "years_to_closest": abs(current_year - closest_anchor),
        "best_resonance": round(best_resonance, 3),
        "triggered": triggered,
        "boost": boost,
        "signal": signal,
        "confidence": best_resonance if cycles_hit else 0.0,
    }


# =============================================================================
# PLANETARY HOURS (Bonus)
# =============================================================================

PLANETARY_RULERS = {
    0: ("Moon", "intuition, emotions"),
    1: ("Mars", "aggression, competition"),
    2: ("Mercury", "communication, speed"),
    3: ("Jupiter", "expansion, luck"),
    4: ("Venus", "harmony, value"),
    5: ("Saturn", "discipline, limits"),
    6: ("Sun", "vitality, success"),
}


def get_planetary_hour(target_datetime: datetime = None) -> Dict[str, Any]:
    """
    Calculate current planetary hour ruler.
    Day ruler + hour offset determines current planetary influence.
    """
    if target_datetime is None:
        target_datetime = datetime.now()

    day_of_week = target_datetime.weekday()
    hour = target_datetime.hour

    # Planetary hour sequence (Chaldean order)
    chaldean_order = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

    # Day ruler
    day_rulers = {
        0: "Moon",     # Monday
        1: "Mars",     # Tuesday
        2: "Mercury",  # Wednesday
        3: "Jupiter",  # Thursday
        4: "Venus",    # Friday
        5: "Saturn",   # Saturday
        6: "Sun",      # Sunday
    }

    day_ruler = day_rulers[day_of_week]
    day_ruler_idx = chaldean_order.index(day_ruler)

    # Current planetary hour (simplified - assumes 12-hour day/night)
    hour_offset = hour % 12
    current_ruler_idx = (day_ruler_idx + hour_offset) % 7
    current_ruler = chaldean_order[current_ruler_idx]

    favorable_activities = {
        "Saturn": "patience, discipline",
        "Jupiter": "expansion, big bets",
        "Mars": "aggressive plays, favorites",
        "Sun": "confidence, star players",
        "Venus": "value plays, unders",
        "Mercury": "props, quick decisions",
        "Moon": "intuition, live betting",
    }

    return {
        "current_ruler": current_ruler,
        "day_ruler": day_ruler,
        "favorable_for": favorable_activities.get(current_ruler, "general"),
        "hour": hour
    }


# =============================================================================
# MAIN AGGREGATION FUNCTIONS
# =============================================================================

def get_daily_esoteric_reading(target_date: date = None) -> Dict[str, Any]:
    """
    Get comprehensive daily esoteric reading.
    Used by GET /esoteric/today-energy
    """
    if target_date is None:
        target_date = date.today()

    void_moon = calculate_void_moon(target_date)
    schumann = get_schumann_frequency(target_date)
    noosphere = calculate_noosphere_velocity(target_date)
    planetary = get_planetary_hour()

    # Calculate overall energy (0-10 scale)
    energy_score = 5.0

    # Void moon penalty
    if void_moon["is_void"]:
        energy_score -= 1.5

    # Schumann effects
    if schumann["status"] == "ELEVATED":
        energy_score += 0.5
    elif schumann["status"] == "DEPRESSED":
        energy_score -= 0.5

    # Noosphere effects
    if noosphere["trending_direction"] == "BULLISH":
        energy_score += 1.0
    elif noosphere["trending_direction"] == "BEARISH":
        energy_score -= 0.5

    # Planetary hour effects
    lucky_planets = ["Jupiter", "Sun", "Venus"]
    if planetary["current_ruler"] in lucky_planets:
        energy_score += 0.5

    energy_score = max(0, min(10, energy_score))

    # Determine outlook
    if energy_score >= 7:
        outlook = "FAVORABLE"
    elif energy_score >= 4:
        outlook = "NEUTRAL"
    else:
        outlook = "UNFAVORABLE"

    return {
        "date": target_date.isoformat(),
        "betting_outlook": outlook,
        "overall_energy": round(energy_score, 1),
        "void_moon": void_moon,
        "schumann_reading": schumann,
        "noosphere": noosphere,
        "planetary_hours": planetary,
        "recommendation": generate_daily_recommendation(outlook, void_moon, noosphere)
    }


def generate_daily_recommendation(outlook: str, void_moon: Dict, noosphere: Dict) -> str:
    """Generate human-readable daily recommendation."""
    if void_moon["is_void"]:
        return f"Void moon active until {void_moon['void_end']}. Avoid new positions."
    elif outlook == "FAVORABLE":
        return "Energy aligned. Trust your analysis today."
    elif outlook == "UNFAVORABLE":
        return "Challenging cosmic conditions. Reduce position sizes."
    else:
        return "Mixed signals. Stick to high-conviction plays only."


def get_game_esoteric_signals(game_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get esoteric signals for a specific game.
    """
    home_team = game_data.get("home_team", "Home")
    away_team = game_data.get("away_team", "Away")
    spread = game_data.get("spread", 0)
    total = game_data.get("total", 200)
    city = game_data.get("city", "Unknown")

    return {
        "founders_echo": {
            "home": check_founders_echo(home_team),
            "away": check_founders_echo(away_team)
        },
        "gann_square": analyze_spread_gann(spread, total),
        "atmospheric": calculate_atmospheric_drag(city),
    }


def get_player_esoteric_signals(player_name: str) -> Dict[str, Any]:
    """
    Get esoteric signals for a specific player.
    Uses get_player_data for fuzzy matching (last name, case-insensitive).
    """
    player_data = get_player_data(player_name)
    if not player_data:
        # Fallback for unknown players
        player_data = {
            "birth_date": "1990-01-01",
            "jersey": 0,
            "team": "Unknown"
        }

    return {
        "biorhythms": calculate_biorhythms(player_data["birth_date"]),
        "life_path_sync": check_life_path_sync(
            player_name,
            player_data["birth_date"],
            player_data["jersey"]
        )
    }


def analyze_parlay_correlations(legs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze parlay for esoteric correlations and warnings.
    """
    teammate_warnings = check_teammate_void(legs)

    # Calculate aggregate biorhythm if players provided
    player_bios = []
    for leg in legs:
        if leg.get("player_name"):
            player_data = get_player_data(leg["player_name"])
            if player_data:
                bio = calculate_biorhythms(player_data["birth_date"])
                player_bios.append(bio["overall"])

    avg_biorhythm = sum(player_bios) / len(player_bios) if player_bios else None

    return {
        "teammate_void_warnings": teammate_warnings,
        "has_warnings": len(teammate_warnings) > 0,
        "warning_count": len(teammate_warnings),
        "average_biorhythm": round(avg_biorhythm, 1) if avg_biorhythm else None,
        "biorhythm_alignment": "FAVORABLE" if avg_biorhythm and avg_biorhythm > 25 else "UNFAVORABLE" if avg_biorhythm and avg_biorhythm < -25 else "NEUTRAL"
    }


# =============================================================================
# 11. CHROME RESONANCE (GLITCH Protocol - Chromatic Harmony)
# =============================================================================

def calculate_chrome_resonance(birth_date_str: str, game_date: date = None) -> Dict[str, Any]:
    """
    Calculate chromatic resonance between player birth date and game date.

    Based on chromatic scale theory - each date has a frequency signature.
    The 12-note chromatic scale maps to day-of-year positions.

    Perfect intervals (unison, fifth, fourth) = high resonance
    Dissonant intervals (tritone, minor second) = low resonance

    Args:
        birth_date_str: Player birth date (YYYY-MM-DD format)
        game_date: Game date (defaults to today)

    Returns:
        Dict with score (0-1), reason, triggered, interval_name, resonance_type
    """
    if game_date is None:
        game_date = date.today()

    try:
        # Parse birth date
        if isinstance(birth_date_str, str):
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        elif isinstance(birth_date_str, date):
            birth_date = birth_date_str
        else:
            return {
                "score": 0.5,
                "reason": "INVALID_BIRTH_DATE",
                "triggered": False,
                "interval_name": None,
                "resonance_type": None
            }

        # Map day-of-year to chromatic note (0-11)
        # This creates a 12-tone cycle based on position in year
        birth_day_of_year = birth_date.timetuple().tm_yday
        game_day_of_year = game_date.timetuple().tm_yday

        birth_note = birth_day_of_year % 12
        game_note = game_day_of_year % 12

        # Calculate interval (semitones apart)
        interval = abs(game_note - birth_note)
        if interval > 6:
            interval = 12 - interval  # Use smaller interval

        # Chromatic interval names and resonance values
        # Based on music theory consonance/dissonance
        interval_data = {
            0: ("Unison", 1.0, "PERFECT"),           # Same note - perfect resonance
            1: ("Minor 2nd", 0.3, "DISSONANT"),      # Half step - tension
            2: ("Major 2nd", 0.5, "MILD"),           # Whole step - neutral
            3: ("Minor 3rd", 0.65, "CONSONANT"),     # Minor third - emotional
            4: ("Major 3rd", 0.7, "CONSONANT"),      # Major third - bright
            5: ("Perfect 4th", 0.85, "STRONG"),      # Fourth - stable
            6: ("Tritone", 0.25, "DISSONANT"),       # Tritone - unstable
            7: ("Perfect 5th", 0.9, "STRONG"),       # Fifth - power
        }

        # Get interval data (default to neutral for any edge cases)
        interval_name, resonance, resonance_type = interval_data.get(
            interval, ("Unknown", 0.5, "NEUTRAL")
        )

        # Determine if triggered (strong or perfect resonance)
        triggered = resonance >= 0.7

        # Build reason string
        if resonance >= 0.85:
            reason = f"CHROME_PERFECT_{interval_name.upper().replace(' ', '_')}"
        elif resonance >= 0.65:
            reason = f"CHROME_CONSONANT_{interval_name.upper().replace(' ', '_')}"
        elif resonance <= 0.35:
            reason = f"CHROME_DISSONANT_{interval_name.upper().replace(' ', '_')}"
        else:
            reason = f"CHROME_NEUTRAL_{interval_name.upper().replace(' ', '_')}"

        return {
            "score": resonance,
            "reason": reason,
            "triggered": triggered,
            "interval_name": interval_name,
            "interval_semitones": interval,
            "resonance_type": resonance_type,
            "birth_note": birth_note,
            "game_note": game_note,
            "birth_day": birth_day_of_year,
            "game_day": game_day_of_year
        }

    except Exception as e:
        return {
            "score": 0.5,
            "reason": f"CHROME_ERROR: {str(e)}",
            "triggered": False,
            "interval_name": None,
            "resonance_type": None
        }


# =============================================================================
# 12. GLITCH AGGREGATE SCORE
# =============================================================================

def get_glitch_aggregate(
    birth_date_str: str = None,
    game_date: date = None,
    game_time: datetime = None,
    line_history: list = None,
    value_for_benford: list = None,
    primary_value: float = None
) -> Dict[str, Any]:
    """
    Calculate aggregate GLITCH Protocol score from all orphaned signals.

    Combines:
    - Chrome Resonance (if birth_date provided) - weight 0.25
    - Void Moon (always) - weight 0.20
    - Noosphere Velocity (if SerpAPI enabled) - weight 0.15
    - Hurst Exponent (if line_history provided) - weight 0.25
    - Kp-Index / Schumann (always) - weight 0.25
    - Benford Anomaly (if value_for_benford provided) - weight 0.10

    Returns aggregated score and breakdown for esoteric engine integration.
    """
    results = {}
    total_weight = 0
    weighted_score = 0
    triggered_signals = []
    reasons = []

    # 1. Chrome Resonance (weight: 0.25)
    if birth_date_str:
        chrome = calculate_chrome_resonance(birth_date_str, game_date)
        results["chrome_resonance"] = chrome
        weight = 0.25
        weighted_score += chrome["score"] * weight
        total_weight += weight
        if chrome["triggered"]:
            triggered_signals.append("chrome_resonance")
        reasons.append(f"CHROME: {chrome['reason']}")

    # 2. Void Moon (weight: 0.20)
    void_moon = calculate_void_moon(game_date)
    results["void_moon"] = void_moon
    weight = 0.20
    # Void moon: is_void = bad (lower score)
    void_score = 0.3 if void_moon["is_void"] else 0.7
    weighted_score += void_score * weight
    total_weight += weight
    if void_moon["is_void"]:
        triggered_signals.append("void_moon_warning")
        reasons.append(f"VOID_MOON: Active until {void_moon.get('void_end', 'unknown')}")
    else:
        reasons.append(f"VOID_MOON: Clear - {void_moon.get('moon_sign', 'unknown')}")

    # 2b. Noosphere Velocity from SerpAPI (weight: 0.15) - real search trends
    noosphere_data = None
    try:
        from alt_data_sources.serpapi import get_noosphere_data, SERPAPI_ENABLED
        if SERPAPI_ENABLED:
            # Extract team names if available (would need to be passed in)
            noosphere_data = get_noosphere_data(teams=None, player=None)
    except ImportError:
        pass

    if noosphere_data and noosphere_data.get("source") == "serpapi_live":
        results["noosphere"] = noosphere_data
        weight = 0.15
        # Convert velocity to score (0-1)
        velocity = noosphere_data.get("velocity", 0.0)
        noosphere_score = 0.5 + (velocity * 0.3)  # -1 to 1 -> 0.2 to 0.8
        weighted_score += noosphere_score * weight
        total_weight += weight
        if noosphere_data.get("triggered"):
            triggered_signals.append(f"noosphere_{noosphere_data.get('direction', 'unknown').lower()}")
        reasons.append(f"NOOSPHERE: {noosphere_data.get('direction', 'NEUTRAL')} (v={velocity:.2f})")

    # 3. Hurst Exponent (weight: 0.25)
    if line_history and len(line_history) >= 10:
        hurst = calculate_hurst_exponent(line_history)
        results["hurst"] = hurst
        weight = 0.25
        # Hurst away from 0.5 = stronger signal
        hurst_score = 0.5 + abs(hurst["h_value"] - 0.5)
        weighted_score += hurst_score * weight
        total_weight += weight
        if hurst["regime"] != "RANDOM_WALK":
            triggered_signals.append(f"hurst_{hurst['regime'].lower()}")
        reasons.append(f"HURST: {hurst['regime']} (H={hurst['h_value']:.2f})")

    # 4. Kp-Index from NOAA (weight: 0.25) - Falls back to Schumann if unavailable
    kp_data = None
    try:
        from alt_data_sources.noaa import get_kp_betting_signal, NOAA_ENABLED
        if NOAA_ENABLED:
            kp_data = get_kp_betting_signal(game_time)
    except ImportError:
        pass  # NOAA module not available, use Schumann fallback

    if kp_data and kp_data.get("source") != "fallback":
        # Use real NOAA Kp-Index data
        results["kp_index"] = kp_data
        weight = 0.25
        kp_score = kp_data["score"]
        weighted_score += kp_score * weight
        total_weight += weight
        if kp_data["triggered"]:
            triggered_signals.append(f"kp_{kp_data['storm_level'].lower()}")
        reasons.append(f"KP: {kp_data['storm_level']} (Kp={kp_data['kp_value']})")
    else:
        # Fallback to Schumann simulation
        schumann = get_schumann_frequency(game_date)
        results["schumann"] = schumann
        weight = 0.25
        # Normal conditions = good, elevated = potentially volatile
        if schumann["status"] == "NORMAL":
            schumann_score = 0.7
        elif "ELEVATED" in schumann["status"]:
            schumann_score = 0.5
            triggered_signals.append("schumann_elevated")
        else:
            schumann_score = 0.6
        weighted_score += schumann_score * weight
        total_weight += weight
        reasons.append(f"SCHUMANN: {schumann['status']} ({schumann['current_hz']}Hz)")

    # 5. Benford Anomaly (weight: 0.10) - detect statistical manipulation in lines
    if value_for_benford and len(value_for_benford) >= 10:
        try:
            from signals.math_glitch import check_benford_anomaly
            benford = check_benford_anomaly(value_for_benford)
            results["benford"] = benford
            weight = 0.10
            benford_score = benford.get("score", 0.5)
            weighted_score += benford_score * weight
            total_weight += weight
            if benford.get("triggered"):
                triggered_signals.append(f"benford_anomaly_{benford.get('deviation', 0):.2f}")
            reasons.append(f"BENFORD: {benford.get('reason', 'UNKNOWN')}")
        except ImportError:
            pass  # signals module not available

    # Normalize score if we have weights
    if total_weight > 0:
        final_score = weighted_score / total_weight
    else:
        final_score = 0.5

    return {
        "glitch_score": round(final_score, 3),
        "glitch_score_10": round(final_score * 10, 2),  # 0-10 scale for engine
        "triggered_count": len(triggered_signals),
        "triggered_signals": triggered_signals,
        "reasons": reasons,
        "breakdown": results,
        "weights_used": round(total_weight, 2)
    }


# =============================================================================
# PHASE 8 (v18.2): NEW ESOTERIC SIGNALS
# =============================================================================

def calculate_lunar_phase_intensity(game_datetime: datetime = None) -> Dict[str, Any]:
    """
    Calculate lunar phase impact on game scoring (v18.2).

    Full moon (phase 0.5) → boost OVER picks (chaos energy)
    New moon (phase 0.0) → boost UNDER picks (subdued energy)
    Quarter moons (0.25, 0.75) → neutral

    Args:
        game_datetime: Game datetime (defaults to now)

    Returns:
        Dict with phase, boost_over, boost_under, reason
    """
    if game_datetime is None:
        game_datetime = datetime.now()

    try:
        # Use astronomical API for accurate moon phase
        phase_data = calculate_moon_phase(game_datetime)
        phase = phase_data.get("phase_decimal", 0.5)  # 0.0-1.0
    except Exception:
        # Fallback: simple calculation based on lunar cycle (~29.5 days)
        # Reference new moon: Jan 1, 2000 at 18:14 UTC
        ref_date = datetime(2000, 1, 1, 18, 14)
        days_since = (game_datetime - ref_date).total_seconds() / 86400
        lunar_cycle = 29.530588853
        phase = (days_since % lunar_cycle) / lunar_cycle

    # Full moon window (0.45 - 0.55)
    if 0.45 <= phase <= 0.55:
        return {
            "phase": "FULL",
            "phase_decimal": round(phase, 3),
            "boost_over": 0.25,
            "boost_under": -0.15,
            "triggered": True,
            "reason": f"Full moon ({phase:.0%}) - chaos energy boost"
        }
    # New moon window (0.0-0.05 or 0.95-1.0)
    elif phase <= 0.05 or phase >= 0.95:
        return {
            "phase": "NEW",
            "phase_decimal": round(phase, 3),
            "boost_over": -0.15,
            "boost_under": 0.2,
            "triggered": True,
            "reason": f"New moon ({phase:.0%}) - subdued energy"
        }
    # First quarter (0.20-0.30)
    elif 0.20 <= phase <= 0.30:
        return {
            "phase": "FIRST_QUARTER",
            "phase_decimal": round(phase, 3),
            "boost_over": 0.1,
            "boost_under": 0.0,
            "triggered": False,
            "reason": f"First quarter moon ({phase:.0%})"
        }
    # Last quarter (0.70-0.80)
    elif 0.70 <= phase <= 0.80:
        return {
            "phase": "LAST_QUARTER",
            "phase_decimal": round(phase, 3),
            "boost_over": 0.0,
            "boost_under": 0.1,
            "triggered": False,
            "reason": f"Last quarter moon ({phase:.0%})"
        }
    # Neutral
    else:
        return {
            "phase": "WAXING" if phase < 0.5 else "WANING",
            "phase_decimal": round(phase, 3),
            "boost_over": 0.0,
            "boost_under": 0.0,
            "triggered": False,
            "reason": None
        }


def check_mercury_retrograde(game_date: date = None) -> Dict[str, Any]:
    """
    Check if game date falls during Mercury retrograde (v18.2).

    Mercury retrograde periods cause communication/travel disruptions.
    Apply variance boost (slight negative adjustment) during retrograde
    to account for unpredictable outcomes.

    Args:
        game_date: Game date to check

    Returns:
        Dict with is_retrograde, adjustment, reason
    """
    if game_date is None:
        game_date = date.today()

    # Mercury retrograde periods for 2025-2027
    # Format: (start_date, end_date)
    RETROGRADE_PERIODS = [
        # 2025
        (date(2025, 3, 15), date(2025, 4, 7)),
        (date(2025, 7, 18), date(2025, 8, 11)),
        (date(2025, 11, 9), date(2025, 11, 29)),
        # 2026
        (date(2026, 3, 14), date(2026, 4, 7)),
        (date(2026, 7, 17), date(2026, 8, 11)),
        (date(2026, 11, 9), date(2026, 11, 29)),
        # 2027
        (date(2027, 2, 25), date(2027, 3, 20)),
        (date(2027, 6, 29), date(2027, 7, 23)),
        (date(2027, 10, 24), date(2027, 11, 13)),
    ]

    # Check shadow periods (1 week before and after retrograde)
    SHADOW_BUFFER_DAYS = 7

    for start, end in RETROGRADE_PERIODS:
        # Direct retrograde period
        if start <= game_date <= end:
            return {
                "is_retrograde": True,
                "is_shadow": False,
                "adjustment": -0.15,
                "triggered": True,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "reason": f"Mercury retrograde ({start.strftime('%b %d')} - {end.strftime('%b %d')}) - expect upsets"
            }
        # Pre-shadow period
        shadow_start = start - timedelta(days=SHADOW_BUFFER_DAYS)
        if shadow_start <= game_date < start:
            return {
                "is_retrograde": False,
                "is_shadow": True,
                "adjustment": -0.08,
                "triggered": True,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "reason": f"Mercury pre-shadow (retrograde starts {start.strftime('%b %d')}) - caution advised"
            }
        # Post-shadow period
        shadow_end = end + timedelta(days=SHADOW_BUFFER_DAYS)
        if end < game_date <= shadow_end:
            return {
                "is_retrograde": False,
                "is_shadow": True,
                "adjustment": -0.05,
                "triggered": True,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "reason": f"Mercury post-shadow (retrograde ended {end.strftime('%b %d')}) - stabilizing"
            }

    return {
        "is_retrograde": False,
        "is_shadow": False,
        "adjustment": 0.0,
        "triggered": False,
        "reason": None
    }


def calculate_rivalry_intensity(
    sport: str,
    home_team: str,
    away_team: str
) -> Dict[str, Any]:
    """
    Calculate rivalry intensity score (v18.2).

    Major rivalries tend to be lower-scoring, more defensive games
    with higher variance. This signal boosts UNDER picks for rivalries.

    Args:
        sport: Sport code (NBA, NFL, NHL, MLB)
        home_team: Home team name
        away_team: Away team name

    Returns:
        Dict with is_rivalry, intensity, under_boost, reason
    """
    # Major rivalries database
    # Each entry: ({team1_keywords}, {team2_keywords}, intensity_level)
    MAJOR_RIVALRIES = {
        "NBA": [
            ({"celtics", "boston"}, {"lakers", "los angeles lakers", "la lakers"}, "HIGH"),
            ({"bulls", "chicago"}, {"pistons", "detroit"}, "HIGH"),
            ({"heat", "miami"}, {"knicks", "new york"}, "MEDIUM"),
            ({"warriors", "golden state"}, {"cavaliers", "cleveland"}, "MEDIUM"),
            ({"lakers", "los angeles lakers"}, {"clippers", "los angeles clippers"}, "MEDIUM"),
            ({"mavericks", "dallas"}, {"spurs", "san antonio"}, "MEDIUM"),
            ({"sixers", "76ers", "philadelphia"}, {"celtics", "boston"}, "MEDIUM"),
        ],
        "NFL": [
            ({"packers", "green bay"}, {"bears", "chicago"}, "HIGH"),
            ({"cowboys", "dallas"}, {"eagles", "philadelphia"}, "HIGH"),
            ({"cowboys", "dallas"}, {"commanders", "washington"}, "HIGH"),
            ({"ravens", "baltimore"}, {"steelers", "pittsburgh"}, "HIGH"),
            ({"patriots", "new england"}, {"jets", "new york jets"}, "MEDIUM"),
            ({"49ers", "san francisco"}, {"seahawks", "seattle"}, "MEDIUM"),
            ({"chiefs", "kansas city"}, {"raiders", "las vegas"}, "MEDIUM"),
            ({"giants", "new york giants"}, {"eagles", "philadelphia"}, "MEDIUM"),
            ({"broncos", "denver"}, {"raiders", "las vegas"}, "MEDIUM"),
        ],
        "NHL": [
            ({"bruins", "boston"}, {"canadiens", "montreal"}, "HIGH"),
            ({"penguins", "pittsburgh"}, {"flyers", "philadelphia"}, "HIGH"),
            ({"rangers", "new york rangers"}, {"islanders", "new york islanders"}, "HIGH"),
            ({"blackhawks", "chicago"}, {"red wings", "detroit"}, "MEDIUM"),
            ({"avalanche", "colorado"}, {"red wings", "detroit"}, "MEDIUM"),
            ({"maple leafs", "toronto"}, {"canadiens", "montreal"}, "HIGH"),
            ({"kings", "los angeles"}, {"sharks", "san jose"}, "MEDIUM"),
            ({"oilers", "edmonton"}, {"flames", "calgary"}, "HIGH"),
        ],
        "MLB": [
            ({"yankees", "new york yankees"}, {"red sox", "boston"}, "HIGH"),
            ({"dodgers", "los angeles dodgers"}, {"giants", "san francisco"}, "HIGH"),
            ({"cubs", "chicago cubs"}, {"cardinals", "st. louis"}, "HIGH"),
            ({"mets", "new york mets"}, {"phillies", "philadelphia"}, "MEDIUM"),
            ({"white sox", "chicago white sox"}, {"cubs", "chicago cubs"}, "MEDIUM"),
            ({"braves", "atlanta"}, {"mets", "new york mets"}, "MEDIUM"),
        ],
        "NCAAB": [
            ({"duke", "blue devils"}, {"north carolina", "tar heels", "unc"}, "HIGH"),
            ({"kentucky", "wildcats"}, {"louisville", "cardinals"}, "HIGH"),
            ({"kansas", "jayhawks"}, {"missouri", "tigers"}, "MEDIUM"),
            ({"michigan", "wolverines"}, {"michigan state", "spartans", "msu"}, "HIGH"),
            ({"indiana", "hoosiers"}, {"purdue", "boilermakers"}, "MEDIUM"),
        ],
    }

    home_lower = home_team.lower()
    away_lower = away_team.lower()

    rivalries = MAJOR_RIVALRIES.get(sport.upper(), [])

    for team1_set, team2_set, intensity in rivalries:
        home_match_1 = any(t in home_lower for t in team1_set)
        home_match_2 = any(t in home_lower for t in team2_set)
        away_match_1 = any(t in away_lower for t in team1_set)
        away_match_2 = any(t in away_lower for t in team2_set)

        # Check if both teams are in this rivalry (either order)
        if (home_match_1 and away_match_2) or (home_match_2 and away_match_1):
            # High intensity rivalries get bigger under boost
            if intensity == "HIGH":
                under_boost = 0.25
                over_penalty = -0.15
            else:  # MEDIUM
                under_boost = 0.15
                over_penalty = -0.08

            return {
                "is_rivalry": True,
                "intensity": intensity,
                "under_boost": under_boost,
                "over_penalty": over_penalty,
                "triggered": True,
                "reason": f"{intensity} rivalry - defensive intensity expected"
            }

    return {
        "is_rivalry": False,
        "intensity": "NONE",
        "under_boost": 0.0,
        "over_penalty": 0.0,
        "triggered": False,
        "reason": None
    }


def calculate_streak_momentum(
    team: str,
    current_streak: int,
    streak_type: str = "W"
) -> Dict[str, Any]:
    """
    Calculate streak momentum signal (v18.2).

    Teams on long streaks (5+) tend to regress.
    Teams on short streaks (2-4) may continue.
    This affects spread/moneyline picks.

    Args:
        team: Team name
        current_streak: Length of current streak (positive number)
        streak_type: "W" for winning streak, "L" for losing streak

    Returns:
        Dict with momentum type, boost values, reason
    """
    streak = abs(current_streak)
    streak_type = streak_type.upper()

    # Long winning streak (5+) - regression expected
    if streak >= 5 and streak_type == "W":
        return {
            "momentum": "REGRESSION_DUE",
            "streak": streak,
            "streak_type": streak_type,
            "against_boost": 0.25,  # Boost betting against them
            "for_boost": -0.15,     # Penalty for betting on them
            "triggered": True,
            "reason": f"{team} on {streak}W streak - regression due"
        }

    # Long losing streak (5+) - bounce expected
    elif streak >= 5 and streak_type == "L":
        return {
            "momentum": "BOUNCE_DUE",
            "streak": streak,
            "streak_type": streak_type,
            "against_boost": -0.1,  # Penalty for betting against them
            "for_boost": 0.2,       # Boost betting on them
            "triggered": True,
            "reason": f"{team} on {streak}L streak - bounce expected"
        }

    # Medium winning streak (3-4) - momentum continues
    elif 3 <= streak <= 4 and streak_type == "W":
        return {
            "momentum": "CONTINUING",
            "streak": streak,
            "streak_type": streak_type,
            "against_boost": -0.05,
            "for_boost": 0.15,
            "triggered": True,
            "reason": f"{team} on {streak}W streak - momentum continuing"
        }

    # Medium losing streak (3-4) - still struggling
    elif 3 <= streak <= 4 and streak_type == "L":
        return {
            "momentum": "STRUGGLING",
            "streak": streak,
            "streak_type": streak_type,
            "against_boost": 0.1,
            "for_boost": -0.1,
            "triggered": False,  # Not strong enough to trigger
            "reason": f"{team} on {streak}L streak - struggling"
        }

    # Short streak (1-2) - no signal
    else:
        return {
            "momentum": "NONE",
            "streak": streak,
            "streak_type": streak_type,
            "against_boost": 0.0,
            "for_boost": 0.0,
            "triggered": False,
            "reason": None
        }


def get_solar_flare_status(game_time: datetime = None) -> Dict[str, Any]:
    """
    Get solar flare status for chaos/volatility signal (v18.2).

    X-class and M-class solar flares correlate with electromagnetic
    disturbances that may affect human performance and outcomes.
    This enhances the GLITCH protocol with real-time space weather.

    Args:
        game_time: Game datetime

    Returns:
        Dict with flare_class, chaos_boost, reason
    """
    if game_time is None:
        game_time = datetime.now()

    try:
        # Try to get real NOAA data
        from alt_data_sources.noaa import get_solar_xray_flux, NOAA_ENABLED
        if NOAA_ENABLED:
            flux_data = get_solar_xray_flux()
            if flux_data and flux_data.get("source") == "noaa_live":
                current_flux = flux_data.get("current_flux", 0)

                # X-class flare (flux >= 1e-4)
                if current_flux >= 1e-4:
                    return {
                        "flare_class": "X",
                        "flux": current_flux,
                        "chaos_boost": 0.3,
                        "triggered": True,
                        "source": "noaa_live",
                        "reason": f"X-class solar flare (flux={current_flux:.2e}) - high chaos"
                    }
                # M-class flare (flux >= 1e-5)
                elif current_flux >= 1e-5:
                    return {
                        "flare_class": "M",
                        "flux": current_flux,
                        "chaos_boost": 0.15,
                        "triggered": True,
                        "source": "noaa_live",
                        "reason": f"M-class solar flare (flux={current_flux:.2e}) - moderate chaos"
                    }
                # C-class or below (quiet)
                else:
                    return {
                        "flare_class": "QUIET",
                        "flux": current_flux,
                        "chaos_boost": 0.0,
                        "triggered": False,
                        "source": "noaa_live",
                        "reason": None
                    }
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: use Kp-index based estimate
    # High Kp (>= 5) suggests elevated solar activity
    try:
        from alt_data_sources.noaa import get_kp_betting_signal
        kp_data = get_kp_betting_signal(game_time)
        if kp_data and kp_data.get("kp_value", 0) >= 5:
            kp_val = kp_data["kp_value"]
            return {
                "flare_class": "ELEVATED_KP",
                "flux": None,
                "kp_value": kp_val,
                "chaos_boost": 0.1 if kp_val >= 7 else 0.05,
                "triggered": kp_val >= 6,
                "source": "kp_fallback",
                "reason": f"Elevated Kp-Index ({kp_val}) - geomagnetic activity"
            }
    except Exception:
        pass

    # No solar activity detected
    return {
        "flare_class": "QUIET",
        "flux": None,
        "chaos_boost": 0.0,
        "triggered": False,
        "source": "unavailable",
        "reason": None
    }


# =============================================================================
# PHASE 8 (v18.2): AGGREGATE FUNCTION FOR NEW SIGNALS
# =============================================================================

def get_phase8_esoteric_signals(
    game_datetime: datetime = None,
    game_date: date = None,
    sport: str = None,
    home_team: str = None,
    away_team: str = None,
    pick_type: str = None,
    pick_side: str = None,
    home_streak: int = 0,
    home_streak_type: str = "W",
    away_streak: int = 0,
    away_streak_type: str = "W"
) -> Dict[str, Any]:
    """
    Aggregate all Phase 8 (v18.2) esoteric signals.

    Combines:
    - Lunar Phase Intensity
    - Mercury Retrograde
    - Rivalry Intensity
    - Streak Momentum
    - Solar Flare Status

    Args:
        game_datetime: Game datetime
        game_date: Game date
        sport: Sport code
        home_team: Home team name
        away_team: Away team name
        pick_type: PROP, SPREAD, TOTAL, MONEYLINE
        pick_side: Over/Under/Team name
        home_streak: Home team current streak length
        home_streak_type: W or L
        away_streak: Away team current streak length
        away_streak_type: W or L

    Returns:
        Dict with all signal results and combined boost
    """
    if game_datetime is None:
        game_datetime = datetime.now()
    if game_date is None:
        game_date = game_datetime.date() if isinstance(game_datetime, datetime) else date.today()

    results = {}
    total_boost = 0.0
    reasons = []
    triggered_signals = []

    # 1. Lunar Phase
    lunar = calculate_lunar_phase_intensity(game_datetime)
    results["lunar_phase"] = lunar
    if lunar.get("triggered"):
        triggered_signals.append("lunar_phase")
        if pick_type and pick_type.upper() == "TOTAL":
            side_lower = (pick_side or "").lower()
            if "over" in side_lower:
                total_boost += lunar.get("boost_over", 0)
            elif "under" in side_lower:
                total_boost += lunar.get("boost_under", 0)
        if lunar.get("reason"):
            reasons.append(f"Lunar: {lunar['reason']}")

    # 2. Mercury Retrograde
    mercury = check_mercury_retrograde(game_date)
    results["mercury_retrograde"] = mercury
    if mercury.get("triggered"):
        triggered_signals.append("mercury_retrograde" if mercury.get("is_retrograde") else "mercury_shadow")
        total_boost += mercury.get("adjustment", 0)
        if mercury.get("reason"):
            reasons.append(f"Mercury: {mercury['reason']}")

    # 3. Rivalry Intensity (for game picks)
    if sport and home_team and away_team:
        rivalry = calculate_rivalry_intensity(sport, home_team, away_team)
        results["rivalry"] = rivalry
        if rivalry.get("triggered"):
            triggered_signals.append("rivalry")
            if pick_type and pick_type.upper() == "TOTAL":
                side_lower = (pick_side or "").lower()
                if "under" in side_lower:
                    total_boost += rivalry.get("under_boost", 0)
                elif "over" in side_lower:
                    total_boost += rivalry.get("over_penalty", 0)
            if rivalry.get("reason"):
                reasons.append(f"Rivalry: {rivalry['reason']}")

    # 4. Streak Momentum (for spread/ML picks)
    if home_team and home_streak:
        home_momentum = calculate_streak_momentum(home_team, home_streak, home_streak_type)
        results["home_streak"] = home_momentum
        if home_momentum.get("triggered"):
            triggered_signals.append("home_streak")
            # If picking home team
            side_lower = (pick_side or "").lower()
            if home_team.lower() in side_lower or "home" in side_lower:
                total_boost += home_momentum.get("for_boost", 0)
            else:
                total_boost += home_momentum.get("against_boost", 0)
            if home_momentum.get("reason"):
                reasons.append(f"Streak: {home_momentum['reason']}")

    if away_team and away_streak:
        away_momentum = calculate_streak_momentum(away_team, away_streak, away_streak_type)
        results["away_streak"] = away_momentum
        if away_momentum.get("triggered"):
            triggered_signals.append("away_streak")
            # If picking away team
            side_lower = (pick_side or "").lower()
            if away_team.lower() in side_lower or "away" in side_lower:
                total_boost += away_momentum.get("for_boost", 0)
            else:
                total_boost += away_momentum.get("against_boost", 0)
            if away_momentum.get("reason"):
                reasons.append(f"Streak: {away_momentum['reason']}")

    # 5. Solar Flare Status (universal chaos signal)
    solar = get_solar_flare_status(game_datetime)
    results["solar_flare"] = solar
    if solar.get("triggered"):
        triggered_signals.append("solar_flare")
        # Solar flare adds chaos - slight boost to underdogs/overs
        total_boost += solar.get("chaos_boost", 0) * 0.5  # Scaled down
        if solar.get("reason"):
            reasons.append(f"Solar: {solar['reason']}")

    # Cap total boost at ±0.5
    total_boost = max(-0.5, min(0.5, total_boost))

    return {
        "phase8_boost": round(total_boost, 3),
        "triggered_count": len(triggered_signals),
        "triggered_signals": triggered_signals,
        "reasons": reasons,
        "breakdown": results
    }
