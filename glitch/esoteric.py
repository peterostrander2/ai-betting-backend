"""
Glitch Protocol: Esoteric Module v1.0
=====================================
Symbolic and numerological signals for edge detection.

Features:
- Chrome Resonance (jersey color psychology)
- Bio-Sine Wave (biorhythm cycles)
- Life Path Sync (numerology alignment)
- Founder's Echo (team gematria resonance)
- Chaldean Clock (time-based numerology)

Master Audit File: esoteric.py - HIGH PRIORITY
"""

import math
from datetime import datetime, date
from typing import Dict, Any, Optional

# =============================================================================
# CHROME RESONANCE - Jersey Color Psychology (v10.70)
# =============================================================================
# Red = Aggression (ATS strength), Black = Penalties/Fouls (fade in close games)
# Blue = Control/Defense, White = Neutrality, Green = Balance

TEAM_PRIMARY_COLORS = {
    # NBA
    "Bulls": "RED", "Heat": "RED", "Rockets": "RED", "Raptors": "RED", "Blazers": "RED",
    "Hawks": "RED", "Wizards": "RED", "Pistons": "RED", "Clippers": "RED",
    "Nets": "BLACK", "Spurs": "BLACK", "Kings": "BLACK",
    "Lakers": "GOLD", "Warriors": "GOLD", "Pacers": "GOLD", "Nuggets": "GOLD",
    "Celtics": "GREEN", "Bucks": "GREEN", "Jazz": "GREEN",
    "Knicks": "BLUE", "Mavericks": "BLUE", "Thunder": "BLUE", "Grizzlies": "BLUE",
    "76ers": "BLUE", "Timberwolves": "BLUE", "Magic": "BLUE", "Hornets": "BLUE",
    "Suns": "ORANGE", "Cavaliers": "WINE",
    # NFL
    "Chiefs": "RED", "49ers": "RED", "Cardinals": "RED", "Buccaneers": "RED",
    "Falcons": "RED", "Texans": "RED", "Patriots": "RED",
    "Raiders": "BLACK", "Ravens": "BLACK", "Saints": "BLACK", "Panthers": "BLACK",
    "Steelers": "BLACK", "Bengals": "BLACK", "Jaguars": "BLACK",
    "Cowboys": "BLUE", "Bills": "BLUE", "Colts": "BLUE", "Chargers": "BLUE",
    "Titans": "BLUE", "Lions": "BLUE", "Giants": "BLUE", "Seahawks": "BLUE",
    "Packers": "GREEN", "Eagles": "GREEN", "Jets": "GREEN",
    "Broncos": "ORANGE", "Bears": "ORANGE", "Browns": "ORANGE", "Dolphins": "ORANGE",
    "Commanders": "BURGUNDY", "Vikings": "PURPLE",
    # MLB
    "Cardinals": "RED", "Reds": "RED", "Angels": "RED", "Phillies": "RED",
    "Nationals": "RED", "Diamondbacks": "RED", "Guardians": "RED",
    "Giants": "BLACK", "Pirates": "BLACK", "White Sox": "BLACK", "Marlins": "BLACK",
    "Dodgers": "BLUE", "Cubs": "BLUE", "Royals": "BLUE", "Blue Jays": "BLUE",
    "Rays": "BLUE", "Brewers": "BLUE", "Mariners": "BLUE", "Rangers": "BLUE",
    "Athletics": "GREEN", "Padres": "GREEN",
    "Orioles": "ORANGE", "Astros": "ORANGE", "Tigers": "ORANGE", "Mets": "ORANGE",
    "Yankees": "NAVY", "Red Sox": "NAVY", "Twins": "NAVY", "Braves": "NAVY",
    "Rockies": "PURPLE",
    # NHL
    "Red Wings": "RED", "Hurricanes": "RED", "Flames": "RED", "Capitals": "RED",
    "Devils": "RED", "Senators": "RED", "Panthers": "RED",
    "Kings": "BLACK", "Ducks": "BLACK", "Bruins": "BLACK",
    "Blues": "BLUE", "Lightning": "BLUE", "Maple Leafs": "BLUE", "Jets": "BLUE",
    "Kraken": "BLUE", "Canucks": "BLUE", "Rangers": "BLUE", "Islanders": "BLUE",
    "Wild": "GREEN", "Stars": "GREEN", "Sharks": "GREEN",
    "Flyers": "ORANGE", "Oilers": "ORANGE", "Sabres": "ORANGE",
    "Avalanche": "BURGUNDY", "Coyotes": "BURGUNDY", "Canadiens": "BURGUNDY",
    "Penguins": "GOLD", "Predators": "GOLD", "Golden Knights": "GOLD",
}


def get_chrome_resonance(home_team: str, away_team: str) -> Dict[str, Any]:
    """
    Chrome Resonance - Analyze psychological impact of team colors.

    Red = Aggression (ATS edge), Black = Penalties (fade in close games)

    Returns:
        Dict with chrome_boost, chrome_signal, and reasoning
    """
    home_color = TEAM_PRIMARY_COLORS.get(home_team, "NEUTRAL")
    away_color = TEAM_PRIMARY_COLORS.get(away_team, "NEUTRAL")

    chrome_boost = 0.0
    chrome_signal = "NEUTRAL"
    chrome_reason = ""

    # Red vs non-Red = aggression advantage
    if home_color == "RED" and away_color != "RED":
        chrome_boost = 0.15
        chrome_signal = "HOME_AGGRESSION"
        chrome_reason = f"Chrome: {home_team} RED aggression vs {away_team}"
    elif away_color == "RED" and home_color != "RED":
        chrome_boost = -0.10  # Away red slightly less impactful
        chrome_signal = "AWAY_AGGRESSION"
        chrome_reason = f"Chrome: {away_team} RED aggression (road)"

    # Black = foul/penalty prone (fade in close spreads)
    if home_color == "BLACK" or away_color == "BLACK":
        chrome_signal = "PENALTY_RISK" if chrome_signal == "NEUTRAL" else chrome_signal
        chrome_reason = chrome_reason or f"Chrome: BLACK team penalty risk"

    # Gold vs Gold = high-scoring potential
    if home_color == "GOLD" and away_color == "GOLD":
        chrome_boost += 0.10
        chrome_signal = "GOLD_CLASH"
        chrome_reason = "Chrome: GOLD vs GOLD high-scoring potential"

    return {
        "available": True,
        "module": "esoteric",
        "signal_type": "CHROME_RESONANCE",
        "home_color": home_color,
        "away_color": away_color,
        "chrome_boost": chrome_boost,
        "chrome_signal": chrome_signal,
        "chrome_reason": chrome_reason
    }


# =============================================================================
# BIO-SINE WAVE - Biorhythm Cycles
# =============================================================================

def calculate_biorhythms(birth_date_str: str, target_date: date = None) -> Dict[str, Any]:
    """
    Calculate physical, emotional, and intellectual biorhythm cycles.

    Physical cycle: 23 days
    Emotional cycle: 28 days
    Intellectual cycle: 33 days

    Returns:
        Dict with cycle values (-100 to +100), overall score, and status
    """
    if target_date is None:
        target_date = date.today()

    try:
        if isinstance(birth_date_str, str):
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        else:
            birth_date = birth_date_str
    except:
        birth_date = date(1990, 1, 1)

    days_alive = (target_date - birth_date).days

    physical = math.sin(2 * math.pi * days_alive / 23) * 100
    emotional = math.sin(2 * math.pi * days_alive / 28) * 100
    intellectual = math.sin(2 * math.pi * days_alive / 33) * 100

    overall = (physical + emotional + intellectual) / 3

    if overall > 50:
        status = "PEAK"
        boost = 0.25
    elif overall > 0:
        status = "RISING"
        boost = 0.10
    elif overall > -50:
        status = "FALLING"
        boost = -0.10
    else:
        status = "LOW"
        boost = -0.20

    return {
        "available": True,
        "module": "esoteric",
        "signal_type": "BIO_SINE_WAVE",
        "physical": round(physical, 1),
        "emotional": round(emotional, 1),
        "intellectual": round(intellectual, 1),
        "overall": round(overall, 1),
        "status": status,
        "boost": boost,
        "days_alive": days_alive
    }


# =============================================================================
# LIFE PATH SYNC - Numerology Alignment
# =============================================================================

def calculate_life_path(birth_date_str: str) -> int:
    """Calculate numerology life path number from birth date."""
    try:
        if isinstance(birth_date_str, str):
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d")
        else:
            birth_date = birth_date_str

        date_str = birth_date.strftime("%Y%m%d")
        total = sum(int(d) for d in date_str)

        while total > 9 and total not in [11, 22, 33]:
            total = sum(int(d) for d in str(total))

        return total
    except:
        return 5


def check_life_path_sync(
    player_name: str,
    birth_date_str: str,
    jersey_number: int
) -> Dict[str, Any]:
    """
    Check alignment between player's life path number and jersey number.

    Master numbers (11, 22, 33) get extra weight.
    """
    life_path = calculate_life_path(birth_date_str)

    jersey_reduced = jersey_number
    while jersey_reduced > 9 and jersey_reduced not in [11, 22, 33]:
        jersey_reduced = sum(int(d) for d in str(jersey_reduced))

    # Check alignments
    exact_match = life_path == jersey_reduced
    master_match = life_path in [11, 22, 33] and jersey_number in [11, 22, 33]
    harmonic_match = jersey_reduced % life_path == 0 if life_path > 0 else False

    if exact_match or master_match:
        sync_level = "PERFECT"
        boost = 0.30
    elif harmonic_match:
        sync_level = "HARMONIC"
        boost = 0.15
    else:
        sync_level = "NONE"
        boost = 0.0

    return {
        "available": True,
        "module": "esoteric",
        "signal_type": "LIFE_PATH_SYNC",
        "player_name": player_name,
        "life_path": life_path,
        "jersey_number": jersey_number,
        "jersey_reduced": jersey_reduced,
        "sync_level": sync_level,
        "boost": boost,
        "is_master_number": life_path in [11, 22, 33]
    }


# =============================================================================
# FOUNDER'S ECHO - Team Gematria Resonance
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
    "Mets": 1962, "Phillies": 1883, "White Sox": 1901, "Tigers": 1901,
    "Twins": 1901, "Guardians": 1901, "Athletics": 1901,
    "Mariners": 1977, "Rangers": 1961, "Blue Jays": 1977, "Rays": 1998,
    "Marlins": 1993, "Rockies": 1993, "Diamondbacks": 1998, "Padres": 1969,
    "Reds": 1881, "Brewers": 1969, "Pirates": 1882, "Royals": 1969,
    "Orioles": 1901, "Angels": 1961, "Nationals": 1969, "Braves": 1871,
    "Astros": 1962,
    # NHL
    "Bruins": 1924, "Blackhawks": 1926, "Red Wings": 1926, "Rangers": 1926,
    "Maple Leafs": 1917, "Canadiens": 1909, "Penguins": 1967, "Flyers": 1967,
    "Blues": 1967, "Sharks": 1991, "Avalanche": 1972,
    "Lightning": 1992, "Stars": 1967, "Oilers": 1972, "Flames": 1972,
    "Canucks": 1970, "Senators": 1992, "Panthers": 1993, "Hurricanes": 1972,
    "Devils": 1974, "Islanders": 1972, "Capitals": 1974, "Predators": 1998,
    "Wild": 2000, "Blue Jackets": 2000, "Coyotes": 1972, "Jets": 1999,
    "Golden Knights": 2017, "Kraken": 2021, "Ducks": 1993, "Sabres": 1970,
}


def calculate_gematria(text: str) -> int:
    """Simple gematria calculation (A=1, B=2, etc.)"""
    text = text.upper().replace(" ", "")
    return sum(ord(c) - 64 for c in text if c.isalpha())


def check_founders_echo(team_name: str, target_date: date = None) -> Dict[str, Any]:
    """
    Check if team name gematria resonates with founding year.

    Resonance patterns:
    - Direct match (gematria == year_sum)
    - Harmonic match (gematria % year_sum == 0)
    - Anniversary alignment (years_since_founding % gematria == 0)
    """
    if target_date is None:
        target_date = date.today()

    founding_year = TEAM_FOUNDING_YEARS.get(team_name, 1900)
    team_gematria = calculate_gematria(team_name)

    year_sum = sum(int(d) for d in str(founding_year))

    direct_match = team_gematria == year_sum
    harmonic_match = team_gematria % year_sum == 0 if year_sum > 0 else False
    year_alignment = (target_date.year - founding_year) % team_gematria == 0 if team_gematria > 0 else False

    resonance = direct_match or harmonic_match or year_alignment

    if direct_match:
        boost = 0.25
        resonance_type = "DIRECT"
    elif harmonic_match:
        boost = 0.15
        resonance_type = "HARMONIC"
    elif year_alignment:
        boost = 0.10
        resonance_type = "ANNIVERSARY"
    else:
        boost = 0.0
        resonance_type = "NONE"

    return {
        "available": True,
        "module": "esoteric",
        "signal_type": "FOUNDERS_ECHO",
        "team": team_name,
        "founding_year": founding_year,
        "team_gematria": team_gematria,
        "year_sum": year_sum,
        "resonance": resonance,
        "resonance_type": resonance_type,
        "boost": boost
    }


# =============================================================================
# CHALDEAN CLOCK - Time-Based Numerology
# =============================================================================

CHALDEAN_VALUES = {
    'a': 1, 'i': 1, 'j': 1, 'q': 1, 'y': 1,
    'b': 2, 'k': 2, 'r': 2,
    'c': 3, 'g': 3, 'l': 3, 's': 3,
    'd': 4, 'm': 4, 't': 4,
    'e': 5, 'h': 5, 'n': 5, 'x': 5,
    'u': 6, 'v': 6, 'w': 6,
    'o': 7, 'z': 7,
    'f': 8, 'p': 8
}


def calculate_chaldean(text: str) -> int:
    """Calculate Chaldean numerology value (no 9s, different mappings)."""
    text = text.lower().replace(" ", "")
    return sum(CHALDEAN_VALUES.get(c, 0) for c in text)


def check_chaldean_clock(game_time: datetime, home_team: str, away_team: str) -> Dict[str, Any]:
    """
    Check if game time aligns with team Chaldean values.

    Hour of game + team values = potential resonance.
    """
    hour = game_time.hour
    minute = game_time.minute

    # Time numerology
    time_value = hour + minute
    while time_value > 9:
        time_value = sum(int(d) for d in str(time_value))

    home_chaldean = calculate_chaldean(home_team)
    away_chaldean = calculate_chaldean(away_team)

    # Reduce to single digit
    home_reduced = home_chaldean
    while home_reduced > 9:
        home_reduced = sum(int(d) for d in str(home_reduced))

    away_reduced = away_chaldean
    while away_reduced > 9:
        away_reduced = sum(int(d) for d in str(away_reduced))

    home_resonance = time_value == home_reduced
    away_resonance = time_value == away_reduced

    if home_resonance and not away_resonance:
        signal = "HOME_FAVORED"
        boost = 0.15
    elif away_resonance and not home_resonance:
        signal = "AWAY_FAVORED"
        boost = -0.10
    elif home_resonance and away_resonance:
        signal = "DOUBLE_RESONANCE"
        boost = 0.0
    else:
        signal = "NEUTRAL"
        boost = 0.0

    return {
        "available": True,
        "module": "esoteric",
        "signal_type": "CHALDEAN_CLOCK",
        "game_time": game_time.isoformat(),
        "time_value": time_value,
        "home_chaldean": home_chaldean,
        "away_chaldean": away_chaldean,
        "home_resonance": home_resonance,
        "away_resonance": away_resonance,
        "signal": signal,
        "boost": boost
    }


# =============================================================================
# AGGREGATED ESOTERIC SCORE
# =============================================================================

def get_esoteric_signals(
    home_team: str,
    away_team: str,
    game_time: datetime = None,
    player_birth_dates: Dict[str, str] = None
) -> Dict[str, Any]:
    """
    Aggregate all esoteric signals for a matchup.

    Returns individual signals plus combined esoteric score.
    """
    signals = {}
    total_boost = 0.0
    fired_modules = []

    # Chrome Resonance
    chrome = get_chrome_resonance(home_team, away_team)
    signals["chrome_resonance"] = chrome
    if chrome["chrome_boost"] != 0:
        total_boost += chrome["chrome_boost"]
        fired_modules.append("CHROME")

    # Founder's Echo (both teams)
    home_founders = check_founders_echo(home_team)
    away_founders = check_founders_echo(away_team)
    signals["founders_echo"] = {
        "home": home_founders,
        "away": away_founders
    }
    if home_founders["boost"] > 0:
        total_boost += home_founders["boost"]
        fired_modules.append("FOUNDERS_HOME")
    if away_founders["boost"] > 0:
        total_boost -= away_founders["boost"] * 0.5  # Away founders slightly negative for home
        fired_modules.append("FOUNDERS_AWAY")

    # Chaldean Clock (if game time provided)
    if game_time:
        chaldean = check_chaldean_clock(game_time, home_team, away_team)
        signals["chaldean_clock"] = chaldean
        if chaldean["boost"] != 0:
            total_boost += chaldean["boost"]
            fired_modules.append("CHALDEAN")

    # Biorhythms (if player birth dates provided)
    if player_birth_dates:
        bio_signals = {}
        for player, birth_date in player_birth_dates.items():
            bio = calculate_biorhythms(birth_date)
            bio_signals[player] = bio
            if bio["status"] in ["PEAK", "LOW"]:
                fired_modules.append(f"BIO_{player[:10]}")
        signals["biorhythms"] = bio_signals

    return {
        "available": True,
        "module": "esoteric",
        "signals": signals,
        "total_boost": round(total_boost, 3),
        "fired_modules": fired_modules,
        "modules_fired_count": len(fired_modules)
    }
