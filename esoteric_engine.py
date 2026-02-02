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
    - Chrome Resonance (if birth_date provided)
    - Void Moon (always)
    - Hurst Exponent (if line_history provided)
    - Kp-Index / Schumann (always)

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
