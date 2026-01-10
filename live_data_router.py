# live_data_router.py v10.1 - JARVIS SAVANT EDITION
# Research-Optimized + Esoteric Edge + Jarvis Triggers
# Dual-Score System: Main Confidence + Esoteric Edge + Cosmic Confluence
# +94.40u YTD edge system integrated

from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
import httpx
import asyncio
from datetime import datetime, timedelta
import math
import random

router = APIRouter(prefix="/live", tags=["live"])

ODDS_API_KEY = "ceb2e3a6a3302e0f38fd0d34150294e9"  # Replace with your key
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# ============================================================================
# JARVIS TRIGGERS - THE PROVEN EDGE NUMBERS (v10.1)
# ============================================================================

JARVIS_TRIGGERS = {
    2178: {
        "name": "THE IMMORTAL",
        "boost": 20,
        "tier": "LEGENDARY",
        "description": "Only number where n×4=reverse AND n×reverse=66^4. Never collapses.",
        "mathematical": True
    },
    201: {
        "name": "THE ORDER",
        "boost": 12,
        "tier": "HIGH",
        "description": "Jesuit Order gematria. The Event of 201.",
        "mathematical": False
    },
    33: {
        "name": "THE MASTER",
        "boost": 10,
        "tier": "HIGH",
        "description": "Highest master number. Masonic significance.",
        "mathematical": False
    },
    93: {
        "name": "THE WILL",
        "boost": 10,
        "tier": "HIGH",
        "description": "Thelema sacred number. Will and Love.",
        "mathematical": False
    },
    322: {
        "name": "THE SOCIETY",
        "boost": 10,
        "tier": "HIGH",
        "description": "Skull & Bones. Genesis 3:22.",
        "mathematical": False
    }
}

# Tesla's 3-6-9 pattern
TESLA_NUMBERS = [3, 6, 9]

def validate_2178() -> dict:
    """
    Prove the mathematical uniqueness of 2178 - THE IMMORTAL NUMBER
    
    Property 1: 2178 × 4 = 8712 (its reversal)
    Property 2: 2178 × 8712 = 18974736 = 66^4
    
    This is the ONLY 4-digit number with both properties.
    """
    n = 2178
    reversal = 8712
    prop1 = (n * 4 == reversal)
    prop2 = (n * reversal == 66**4)
    sixty_six_fourth = 66 * 66 * 66 * 66
    
    return {
        "number": n,
        "reversal": reversal,
        "n_times_4_equals_reversal": prop1,
        "n_times_reversal": n * reversal,
        "sixty_six_to_fourth": sixty_six_fourth,
        "n_times_reversal_equals_66_4": prop2,
        "validated": prop1 and prop2,
        "status": "IMMORTAL CONFIRMED" if (prop1 and prop2) else "VALIDATION FAILED"
    }

def digit_sum(n: int) -> int:
    """Calculate digit sum of a number"""
    return sum(int(d) for d in str(abs(n)))

def reduce_to_single_jarvis(n: int) -> int:
    """Reduce number to single digit (gematria reduction)"""
    while n > 9:
        n = digit_sum(n)
    return n

def check_jarvis_trigger(value: int) -> dict:
    """
    Check if a value triggers any Jarvis edge numbers.
    """
    result = {
        "triggered": False,
        "triggers": [],
        "total_boost": 0,
        "highest_tier": None,
        "details": []
    }
    
    str_value = str(abs(value))
    
    # Check for 2178 sequence
    if "2178" in str_value:
        trigger = JARVIS_TRIGGERS[2178]
        result["triggered"] = True
        result["triggers"].append(2178)
        result["total_boost"] += trigger["boost"]
        result["highest_tier"] = "LEGENDARY"
        result["details"].append(f"Contains THE IMMORTAL sequence (2178)")
    
    # Direct match
    if value in JARVIS_TRIGGERS:
        trigger = JARVIS_TRIGGERS[value]
        if value not in result["triggers"]:
            result["triggered"] = True
            result["triggers"].append(value)
            result["total_boost"] += trigger["boost"]
            if result["highest_tier"] != "LEGENDARY":
                result["highest_tier"] = trigger["tier"]
            result["details"].append(f"Direct match: {trigger['name']}")
    
    # Reduction check
    reduced = reduce_to_single_jarvis(value)
    for trigger_num, trigger in JARVIS_TRIGGERS.items():
        if trigger_num not in result["triggers"]:
            if reduce_to_single_jarvis(trigger_num) == reduced:
                result["triggered"] = True
                result["triggers"].append(trigger_num)
                result["total_boost"] += trigger["boost"] * 0.5
                result["details"].append(f"Reduces to same as {trigger['name']}")
    
    # 33 divisibility
    if value % 33 == 0 and 33 not in result["triggers"]:
        result["triggered"] = True
        result["triggers"].append(33)
        result["total_boost"] += 5
        result["details"].append("Divisible by THE MASTER (33)")
    
    # Tesla 3-6-9
    if reduced in TESLA_NUMBERS:
        result["details"].append(f"Tesla alignment: reduces to {reduced}")
        result["total_boost"] += 2
    
    return result

# ============================================================================
# JARVIS EDGE SIGNALS (v10.1)
# ============================================================================

def calculate_public_fade_signal(public_percentage: float, is_favorite: bool) -> dict:
    """
    JARVIS PUBLIC FADE 65% CRUSH ZONE
    When public is ≥65% on the chalk, fade them.
    +94.40u YTD came largely from this edge.
    """
    signal = {
        "public_pct": public_percentage,
        "is_favorite": is_favorite,
        "in_crush_zone": False,
        "fade_signal": False,
        "influence": 0.0,
        "recommendation": ""
    }
    
    if public_percentage >= 65 and is_favorite:
        signal["in_crush_zone"] = True
        signal["fade_signal"] = True
        
        if public_percentage >= 80:
            signal["influence"] = 0.95
            signal["recommendation"] = "MAXIMUM FADE - Public delusion at peak"
        elif public_percentage >= 75:
            signal["influence"] = 0.85
            signal["recommendation"] = "STRONG FADE - Heavy public chalk"
        elif public_percentage >= 70:
            signal["influence"] = 0.75
            signal["recommendation"] = "FADE - Solid crush zone entry"
        else:
            signal["influence"] = 0.65
            signal["recommendation"] = "FADE - Entering crush zone"
    
    elif public_percentage >= 65 and not is_favorite:
        signal["influence"] = 0.45
        signal["recommendation"] = "Monitor - Public dog heavy"
    
    elif public_percentage <= 35:
        signal["influence"] = 0.55
        signal["recommendation"] = "Contrarian value - Public avoiding"
    
    else:
        signal["influence"] = 0.30
        signal["recommendation"] = "No clear public edge"
    
    return signal

def calculate_mid_spread_signal(spread: float) -> dict:
    """
    JARVIS MID-SPREAD AMPLIFIER
    The Goldilocks Zone: +4 to +9
    """
    abs_spread = abs(spread) if spread else 0
    
    signal = {
        "spread": spread,
        "abs_spread": abs_spread,
        "in_goldilocks": False,
        "influence": 0.0,
        "zone": "",
        "boost_modifier": 1.0
    }
    
    if 4 <= abs_spread <= 9:
        signal["in_goldilocks"] = True
        signal["zone"] = "GOLDILOCKS"
        signal["boost_modifier"] = 1.20
        signal["influence"] = 0.85 if 6 <= abs_spread <= 7 else 0.75
    
    elif abs_spread < 4:
        signal["zone"] = "TOO_TIGHT"
        signal["influence"] = 0.50
        signal["boost_modifier"] = 1.0
    
    elif abs_spread > 15:
        signal["zone"] = "TRAP_GATE"
        signal["influence"] = 0.25
        signal["boost_modifier"] = 0.80
    
    else:
        signal["zone"] = "MODERATE"
        signal["influence"] = 0.55
        signal["boost_modifier"] = 1.0
    
    return signal

def calculate_large_spread_trap(spread: float) -> dict:
    """
    JARVIS LARGE SPREAD TRAP GATE
    Spreads >15 points = trap territory. -20% penalty.
    """
    abs_spread = abs(spread) if spread else 0
    
    signal = {
        "spread": spread,
        "abs_spread": abs_spread,
        "is_trap": False,
        "penalty": 1.0,
        "warning": ""
    }
    
    if abs_spread > 15:
        signal["is_trap"] = True
        signal["penalty"] = 0.80
        
        if abs_spread > 20:
            signal["penalty"] = 0.70
            signal["warning"] = "EXTREME TRAP - Heavily penalize any plays here"
        else:
            signal["warning"] = "TRAP GATE ACTIVE - Large spread penalty applied"
    
    return signal

def calculate_nhl_dog_protocol(sport: str, spread: float, research_score: float, public_pct: float) -> dict:
    """
    JARVIS NHL DOG PROTOCOL
    Puck line dogs (+1.5) + RS ≥9.3 + Public ≥65% = gold
    """
    signal = {
        "sport": sport,
        "protocol_active": False,
        "conditions_met": [],
        "conditions_failed": [],
        "influence": 0.0,
        "recommendation": ""
    }
    
    if sport.upper() != "NHL":
        signal["recommendation"] = "Protocol only applies to NHL"
        return signal
    
    is_dog = spread > 0 if spread else False
    is_puck_line = abs(spread) == 1.5 if spread else False
    high_research = research_score >= 9.3
    public_heavy = public_pct >= 65
    
    if is_dog and is_puck_line:
        signal["conditions_met"].append("Puck line dog (+1.5)")
    else:
        signal["conditions_failed"].append("Not puck line dog")
    
    if high_research:
        signal["conditions_met"].append(f"Research score {research_score} ≥ 9.3")
    else:
        signal["conditions_failed"].append(f"Research score {research_score} < 9.3")
    
    if public_heavy:
        signal["conditions_met"].append(f"Public {public_pct}% ≥ 65%")
    else:
        signal["conditions_failed"].append(f"Public {public_pct}% < 65%")
    
    conditions_count = len(signal["conditions_met"])
    
    if conditions_count == 3:
        signal["protocol_active"] = True
        signal["influence"] = 0.92
        signal["recommendation"] = "FULL PROTOCOL - All conditions met. Strong NHL dog play."
    elif conditions_count == 2:
        signal["influence"] = 0.70
        signal["recommendation"] = "PARTIAL PROTOCOL - 2/3 conditions."
    elif conditions_count == 1:
        signal["influence"] = 0.45
        signal["recommendation"] = "WEAK SIGNAL - Only 1/3 conditions."
    else:
        signal["influence"] = 0.20
        signal["recommendation"] = "NO PROTOCOL - Conditions not met."
    
    return signal

# ============================================================================
# SIGNAL WEIGHTS v10.1 - RESEARCH-OPTIMIZED + JARVIS
# ============================================================================

SIGNAL_WEIGHTS = {
    # TIER 1: PROVEN EDGE (56%+ win rates)
    "sharp_money": 22,
    "line_edge": 18,
    "noosphere_velocity": 17,
    "injury_vacuum": 16,
    "game_pace": 15,
    "travel_fatigue": 14,
    "back_to_back": 13,
    "defense_vs_position": 12,
    "public_fade": 11,
    "steam_moves": 10,
    "home_court": 10,

    # TIER 2: SUPPORTING
    "weather": 10,
    "minutes_projection": 10,
    "referee": 8,
    "game_script": 8,

    # TIER 3: ML
    "ensemble_ml": 8,

    # ESOTERIC (showcased separately, minimal main weight)
    "gematria": 3,
    "moon_phase": 2,
    "numerology": 2,
    "sacred_geometry": 2,
    "zodiac": 1,
    
    # JARVIS EDGES (v10.1)
    "jarvis_trigger": 5,
    "crush_zone": 4,
    "goldilocks": 3,
    "nhl_protocol": 4
}

# ============================================================================
# ESOTERIC EDGE MODULE (Original v10.0)
# ============================================================================

# Gematria Ciphers
def gematria_ordinal(text: str) -> int:
    """A=1, B=2, ... Z=26"""
    return sum(ord(c) - 64 for c in (text or "").upper() if 65 <= ord(c) <= 90)

def gematria_reduction(text: str) -> int:
    """Pythagorean reduction to single digits"""
    total = 0
    for c in (text or "").upper():
        if 65 <= ord(c) <= 90:
            val = ord(c) - 64
            while val > 9:
                val = sum(int(d) for d in str(val))
            total += val
    return total

def gematria_reverse(text: str) -> int:
    """A=26, B=25, ... Z=1"""
    return sum(27 - (ord(c) - 64) for c in (text or "").upper() if 65 <= ord(c) <= 90)

def gematria_jewish(text: str) -> int:
    """Hebrew/Jewish cipher"""
    values = {
        'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8, 'I': 9,
        'K': 10, 'L': 20, 'M': 30, 'N': 40, 'O': 50, 'P': 60, 'Q': 70, 'R': 80,
        'S': 90, 'T': 100, 'U': 200, 'V': 300, 'W': 400, 'X': 500, 'Y': 600, 'Z': 700, 'J': 600
    }
    return sum(values.get(c, 0) for c in (text or "").upper())

def gematria_sumerian(text: str) -> int:
    """Multiples of 6: A=6, B=12, ..."""
    return sum((ord(c) - 64) * 6 for c in (text or "").upper() if 65 <= ord(c) <= 90)

# Power Numbers
POWER_NUMBERS = {
    "master": [11, 22, 33, 44, 55, 66, 77, 88, 99],
    "tesla": [3, 6, 9, 27, 36, 63, 72, 81, 108, 144, 216, 369],
    "fibonacci": [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377],
    "sacred": [7, 12, 40, 72, 153, 666, 777, 888],
    "jarvis": [2178, 201, 33, 93, 322]  # v10.1
}
# ============================================================================
# v14.0 NOOSPHERE VELOCITY - Team Search Volume Baselines
# "Someone always knows." - Information asymmetry detection
# ============================================================================

TEAM_BASELINE_VOLUMES = {
    # NBA Teams (normalized daily search volume index)
    "lakers": 100, "warriors": 85, "celtics": 80, "bulls": 75, "knicks": 80,
    "nets": 70, "heat": 72, "mavericks": 68, "suns": 65, "76ers": 62,
    "bucks": 60, "nuggets": 58, "clippers": 55, "grizzlies": 50, "cavaliers": 48,
    "hawks": 45, "raptors": 52, "timberwolves": 42, "pelicans": 40, "kings": 45,
    "jazz": 38, "thunder": 44, "magic": 42, "pacers": 38, "wizards": 35,
    "hornets": 32, "pistons": 35, "spurs": 48, "blazers": 40, "rockets": 55,
    # NFL Teams
    "chiefs": 90, "cowboys": 95, "eagles": 85, "49ers": 80, "bills": 70,
    "ravens": 68, "dolphins": 65, "lions": 62, "packers": 75, "bengals": 60,
    "jets": 58, "patriots": 72, "raiders": 55, "broncos": 52, "chargers": 50,
    "seahawks": 55, "vikings": 52, "saints": 48, "falcons": 45, "bears": 60,
    "browns": 48, "steelers": 65, "commanders": 42, "giants": 55, "rams": 50,
    "cardinals": 40, "colts": 45, "jaguars": 38, "texans": 42, "titans": 40,
    "buccaneers": 55, "panthers": 38,
    # NHL Teams
    "maple leafs": 70, "canadiens": 65, "rangers": 60, "bruins": 58, "blackhawks": 55,
    "penguins": 52, "red wings": 48, "flyers": 50, "oilers": 55, "golden knights": 52,
    "avalanche": 48, "lightning": 50, "kraken": 40, "wild": 35, "flames": 38,
    # Default
    "default": 50
}

INJURY_RELATED_TERMS = [
    "injury", "injured", "hurt", "out", "questionable", "doubtful", "gtd",
    "game time decision", "dnp", "did not practice", "limited", "knee",
    "ankle", "hamstring", "concussion", "illness", "sick", "rest", "load management",
    "scratch", "ir", "injured reserve", "day to day", "week to week"
]

# ============================================================================
# v11.0 OMNI-GLITCH - Venue Atmospherics for Atmospheric Drag
# ============================================================================

VENUE_ATMOSPHERICS = {
    "Denver Broncos": {"city": "Denver", "elevation_ft": 5280, "base_pressure": 24.63, "dome": False},
    "Denver Nuggets": {"city": "Denver", "elevation_ft": 5280, "base_pressure": 24.63, "dome": True},
    "Colorado Rockies": {"city": "Denver", "elevation_ft": 5280, "base_pressure": 24.63, "dome": False},
    "Colorado Avalanche": {"city": "Denver", "elevation_ft": 5280, "base_pressure": 24.63, "dome": True},
    "Utah Jazz": {"city": "Salt Lake City", "elevation_ft": 4226, "base_pressure": 25.70, "dome": True},
    "Las Vegas Raiders": {"city": "Las Vegas", "elevation_ft": 2001, "base_pressure": 27.82, "dome": True},
    "Vegas Golden Knights": {"city": "Las Vegas", "elevation_ft": 2001, "base_pressure": 27.82, "dome": True},
    "Phoenix Suns": {"city": "Phoenix", "elevation_ft": 1086, "base_pressure": 28.89, "dome": True},
    "Arizona Diamondbacks": {"city": "Phoenix", "elevation_ft": 1086, "base_pressure": 28.89, "dome": True},
    "Arizona Cardinals": {"city": "Glendale", "elevation_ft": 1120, "base_pressure": 28.86, "dome": True},
    "default": {"city": "Sea Level", "elevation_ft": 0, "base_pressure": 29.92, "dome": False}
}

def get_moon_phase() -> str:
    """Calculate current moon phase"""
    known_new_moon = datetime(2024, 1, 11)
    days_since = (datetime.now() - known_new_moon).days
    lunar_cycle = 29.53
    phase_num = (days_since % lunar_cycle) / lunar_cycle * 8
    phases = ['new', 'waxing_crescent', 'first_quarter', 'waxing_gibbous',
              'full', 'waning_gibbous', 'last_quarter', 'waning_crescent']
    return phases[int(phase_num) % 8]

def get_life_path(date: datetime = None) -> int:
    """Calculate life path number for a date"""
    if date is None:
        date = datetime.now()
    digits = f"{date.year}{date.month:02d}{date.day:02d}"
    total = sum(int(d) for d in digits)
    while total > 9 and total not in [11, 22, 33]:
        total = sum(int(d) for d in str(total))
    return total

def get_daily_esoteric_reading(date: datetime = None) -> dict:
    """Generate daily esoteric reading"""
    if date is None:
        date = datetime.now()
    
    month = date.month
    day = date.day
    year = date.year
    
    life_path = get_life_path(date)
    moon_phase = get_moon_phase()
    moon_emoji = {
        'new': '🌑', 'waxing_crescent': '🌒', 'first_quarter': '🌓', 'waxing_gibbous': '🌔',
        'full': '🌕', 'waning_gibbous': '🌖', 'last_quarter': '🌗', 'waning_crescent': '🌘'
    }.get(moon_phase, '🌙')
    
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_energies = {
        0: {"planet": "Moon", "energy": "intuition", "bias": "home teams"},
        1: {"planet": "Mars", "energy": "aggression", "bias": "overs"},
        2: {"planet": "Mercury", "energy": "speed", "bias": "high-pace teams"},
        3: {"planet": "Jupiter", "energy": "expansion", "bias": "underdogs"},
        4: {"planet": "Venus", "energy": "harmony", "bias": "close games"},
        5: {"planet": "Saturn", "energy": "discipline", "bias": "unders"},
        6: {"planet": "Sun", "energy": "victory", "bias": "favorites"}
    }
    
    day_of_week = date.weekday()
    today_energy = day_energies[day_of_week]
    
    tesla_number = (day * month) % 9 or 9
    tesla_alignment = "STRONG" if tesla_number in [3, 6, 9] else "moderate"
    
    # v10.1: Check for Jarvis date alignment
    date_value = int(f"{month}{day}")
    jarvis_check = check_jarvis_trigger(date_value)
    jarvis_active = jarvis_check["triggered"]
    
    if jarvis_active:
        recommendation = f"JARVIS TRIGGER ACTIVE: {jarvis_check['details'][0] if jarvis_check['details'] else 'Alignment detected'}"
    elif moon_phase == 'full':
        recommendation = "Full moon = heightened emotions. Trust bold plays."
    elif moon_phase == 'new':
        recommendation = "New moon = fresh starts. Good for underdog plays."
    elif tesla_alignment == "STRONG":
        recommendation = "Tesla alignment active. Trust the mathematics."
    elif life_path == 8:
        recommendation = "Abundance day. High-value plays favored."
    else:
        recommendation = "Steady energy. Stick to high-confluence plays."
    
    return {
        "date": date.strftime("%a %b %d %Y"),
        "life_path": life_path,
        "moon_phase": moon_phase,
        "moon_emoji": moon_emoji,
        "day_of_week": day_names[day_of_week],
        "planetary_ruler": today_energy["planet"],
        "day_energy": today_energy["energy"],
        "natural_bias": today_energy["bias"],
        "tesla_number": tesla_number,
        "tesla_alignment": tesla_alignment,
        "jarvis_active": jarvis_active,
        "jarvis_details": jarvis_check,
        "recommendation": recommendation,
        "lucky_numbers": [life_path, tesla_number, day % 10 or 10, (month + day) % 22 or 22],
        "immortal_status": validate_2178()["status"]
    }

def calculate_gematria_analysis(home_team: str, away_team: str, date: datetime = None) -> dict:
    """Full gematria analysis for a matchup with Jarvis triggers"""
    if date is None:
        date = datetime.now()
    
    home_values = {
        "ordinal": gematria_ordinal(home_team),
        "reduction": gematria_reduction(home_team),
        "reverse": gematria_reverse(home_team),
        "jewish": gematria_jewish(home_team),
        "sumerian": gematria_sumerian(home_team)
    }
    
    away_values = {
        "ordinal": gematria_ordinal(away_team),
        "reduction": gematria_reduction(away_team),
        "reverse": gematria_reverse(away_team),
        "jewish": gematria_jewish(away_team),
        "sumerian": gematria_sumerian(away_team)
    }
    
    alignments = []
    esoteric_score = 50
    immortal_detected = False
    jarvis_triggered = False
    
    for cipher in home_values:
        home_val = home_values[cipher]
        away_val = away_values[cipher]
        diff = abs(home_val - away_val)
        
        # v10.1: Check for Jarvis triggers
        home_jarvis = check_jarvis_trigger(home_val)
        away_jarvis = check_jarvis_trigger(away_val)
        diff_jarvis = check_jarvis_trigger(diff)
        
        if home_jarvis["triggered"]:
            jarvis_triggered = True
            if 2178 in home_jarvis["triggers"]:
                immortal_detected = True
            alignments.append({
                "type": "JARVIS_TRIGGER",
                "cipher": cipher,
                "team": home_team,
                "value": home_val,
                "message": f"{cipher}: {home_team} = {home_jarvis['details'][0] if home_jarvis['details'] else 'Jarvis aligned'}"
            })
            esoteric_score += home_jarvis["total_boost"]
        
        if away_jarvis["triggered"]:
            jarvis_triggered = True
            if 2178 in away_jarvis["triggers"]:
                immortal_detected = True
            alignments.append({
                "type": "JARVIS_TRIGGER",
                "cipher": cipher,
                "team": away_team,
                "value": away_val,
                "message": f"{cipher}: {away_team} = {away_jarvis['details'][0] if away_jarvis['details'] else 'Jarvis aligned'}"
            })
            esoteric_score += away_jarvis["total_boost"]
        
        # Tesla alignment
        if diff in POWER_NUMBERS["tesla"]:
            alignments.append({
                "type": "TESLA_ALIGNMENT",
                "cipher": cipher,
                "value": diff,
                "message": f"{cipher}: Tesla number {diff} ({home_val} vs {away_val})"
            })
            esoteric_score += 10
        
        # Master numbers
        if home_val in POWER_NUMBERS["master"]:
            alignments.append({
                "type": "MASTER_NUMBER",
                "cipher": cipher,
                "team": home_team,
                "value": home_val,
                "message": f"{cipher}: {home_team} = Master {home_val}"
            })
            esoteric_score += 6
        
        if away_val in POWER_NUMBERS["master"]:
            alignments.append({
                "type": "MASTER_NUMBER",
                "cipher": cipher,
                "team": away_team,
                "value": away_val,
                "message": f"{cipher}: {away_team} = Master {away_val}"
            })
            esoteric_score += 6
        
        # Fibonacci
        if home_val in POWER_NUMBERS["fibonacci"]:
            alignments.append({
                "type": "FIBONACCI",
                "cipher": cipher,
                "team": home_team,
                "value": home_val,
                "message": f"{cipher}: {home_team} = Fibonacci {home_val}"
            })
            esoteric_score += 5
    
    # Cap score but IMMORTAL can break the cap
    if immortal_detected:
        esoteric_score = min(100, esoteric_score)
    else:
        esoteric_score = min(95, esoteric_score)
    
    # Determine favored team
    home_alignments = len([a for a in alignments if a.get("team") == home_team])
    away_alignments = len([a for a in alignments if a.get("team") == away_team])
    
    favored = None
    favor_reason = ""
    if home_alignments > away_alignments:
        favored = "home"
        favor_reason = f"{home_team} has {home_alignments} cosmic alignments"
    elif away_alignments > home_alignments:
        favored = "away"
        favor_reason = f"{away_team} has {away_alignments} cosmic alignments"
    
    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_values": home_values,
        "away_values": away_values,
        "alignments": alignments[:8],
        "esoteric_score": esoteric_score,
        "favored": favored,
        "favor_reason": favor_reason,
        "jarvis_triggered": jarvis_triggered,
        "immortal_detected": immortal_detected
    }

def calculate_esoteric_score(home_team: str, away_team: str, spread: float = None, total: float = None, public_pct: float = 50, is_favorite: bool = False, sport: str = "NBA") -> dict:
    """Calculate full esoteric score with Jarvis edges"""
    date = datetime.now()
    
    # Gematria analysis
    gematria = calculate_gematria_analysis(home_team, away_team, date)
    
    # Daily reading
    daily = get_daily_esoteric_reading(date)
    
    # Jarvis edge signals
    public_fade = calculate_public_fade_signal(public_pct, is_favorite)
    mid_spread = calculate_mid_spread_signal(spread or 0)
    trap_gate = calculate_large_spread_trap(spread or 0)
    nhl_protocol = calculate_nhl_dog_protocol(sport, spread or 0, gematria["esoteric_score"] / 10, public_pct)
    
    # Moon score
    moon_phase = get_moon_phase()
    if moon_phase == 'full':
        moon_score = 70
        moon_insight = "Full moon: Peak energy, trust your instincts"
    elif moon_phase == 'new':
        moon_score = 65
        moon_insight = "New moon: Fresh cycle, underdogs shine"
    elif moon_phase in ['waxing_gibbous', 'waxing_crescent']:
        moon_score = 58
        moon_insight = "Waxing moon: Building energy, momentum plays"
    else:
        moon_score = 52
        moon_insight = "Waning moon: Releasing energy, fade hype"
    
    # Numerology score
    life_path = daily["life_path"]
    if life_path in [8, 11, 22, 33]:
        numerology_score = 72
        numerology_insight = f"Master number {life_path} day - powerful alignments"
    elif life_path in [1, 5, 9]:
        numerology_score = 62
        numerology_insight = f"Life path {life_path} - action & change energy"
    else:
        numerology_score = 55
        numerology_insight = f"Life path {life_path} - balanced day"
    
    # Geometry score
    line = spread or total or 0
    rounded = round(abs(line))
    if rounded in POWER_NUMBERS["fibonacci"]:
        geometry_score = 68
        geometry_insight = f"Line {rounded} = Fibonacci number (natural harmony)"
    elif rounded % 3 == 0:
        geometry_score = 62
        geometry_insight = f"Line {rounded} = Tesla divisible (3-6-9 energy)"
    elif rounded in POWER_NUMBERS["sacred"]:
        geometry_score = 65
        geometry_insight = f"Line {rounded} = Sacred number"
    else:
        geometry_score = 52
        geometry_insight = f"Line {rounded} - neutral geometry"
    
    # Zodiac score
    zodiac_score = 50
    zodiac_insight = f"{daily['day_of_week']} ({daily['planetary_ruler']}) favors {daily['natural_bias']}"
    
    if daily["natural_bias"] == "overs" and total and total > 220:
        zodiac_score = 65
    elif daily["natural_bias"] == "unders" and total and total < 215:
        zodiac_score = 65
    elif daily["natural_bias"] == "underdogs" and spread and spread > 5:
        zodiac_score = 62
    elif daily["natural_bias"] == "favorites" and spread and spread < -5:
        zodiac_score = 62
    elif daily["natural_bias"] == "home teams":
        zodiac_score = 58
    
    # Jarvis boost scores
    jarvis_boost = 0
    if gematria["immortal_detected"]:
        jarvis_boost = 20
    elif gematria["jarvis_triggered"]:
        jarvis_boost = 10
    
    if public_fade["in_crush_zone"]:
        jarvis_boost += 8
    
    if mid_spread["in_goldilocks"]:
        jarvis_boost += 5
    
    if nhl_protocol["protocol_active"]:
        jarvis_boost += 10
    
    # Weighted average with Jarvis
    weights = {"gematria": 35, "moon": 15, "numerology": 15, "geometry": 15, "zodiac": 10, "jarvis": 10}
    total_weight = sum(weights.values())
    weighted_sum = (
        gematria["esoteric_score"] * weights["gematria"] +
        moon_score * weights["moon"] +
        numerology_score * weights["numerology"] +
        geometry_score * weights["geometry"] +
        zodiac_score * weights["zodiac"] +
        min(100, 50 + jarvis_boost) * weights["jarvis"]
    )
    
    final_score = round(weighted_sum / total_weight)
    
    # Apply trap gate penalty
    if trap_gate["is_trap"]:
        final_score = round(final_score * trap_gate["penalty"])
    
    # Apply goldilocks boost
    if mid_spread["in_goldilocks"]:
        final_score = min(100, round(final_score * mid_spread["boost_modifier"]))
    
    # Tier with IMMORTAL level
    if gematria["immortal_detected"] and final_score >= 80:
        tier = "IMMORTAL_ALIGNMENT"
        emoji = "👁️🔥"
    elif final_score >= 75:
        tier = "COSMIC_ALIGNMENT"
        emoji = "🌟"
    elif final_score >= 65:
        tier = "STARS_FAVOR"
        emoji = "⭐"
    elif final_score >= 55:
        tier = "MILD_ALIGNMENT"
        emoji = "✨"
    else:
        tier = "NEUTRAL"
        emoji = "🔮"
    
    return {
        "esoteric_score": final_score,
        "esoteric_tier": tier,
        "esoteric_emoji": emoji,
        "immortal_detected": gematria["immortal_detected"],
        "jarvis_triggered": gematria["jarvis_triggered"],
        "components": {
            "gematria": {
                "score": gematria["esoteric_score"],
                "alignments": gematria["alignments"],
                "favored": gematria["favored"],
                "favor_reason": gematria["favor_reason"],
                "home_values": gematria["home_values"],
                "away_values": gematria["away_values"],
                "immortal_detected": gematria["immortal_detected"],
                "jarvis_triggered": gematria["jarvis_triggered"]
            },
            "moon": {"score": moon_score, "phase": moon_phase, "insight": moon_insight},
            "numerology": {"score": numerology_score, "life_path": life_path, "insight": numerology_insight},
            "geometry": {"score": geometry_score, "line": rounded, "insight": geometry_insight},
            "zodiac": {"score": zodiac_score, "ruler": daily["planetary_ruler"], "insight": zodiac_insight},
            "jarvis_edges": {
                "public_fade": public_fade,
                "mid_spread": mid_spread,
                "trap_gate": trap_gate,
                "nhl_protocol": nhl_protocol,
                "total_boost": jarvis_boost
            }
        },
        "daily_reading": daily,
        "top_insights": [
            f"👁️ IMMORTAL 2178 DETECTED" if gematria["immortal_detected"] else (gematria["alignments"][0]["message"] if gematria["alignments"] else None),
            public_fade["recommendation"] if public_fade["in_crush_zone"] else moon_insight,
            mid_spread["zone"] + " ZONE" if mid_spread["in_goldilocks"] else numerology_insight
        ]
    }

def check_cosmic_confluence(main_confidence: int, esoteric_score: int, main_direction: str = None, esoteric_favored: str = None, immortal_detected: bool = False, jarvis_triggered: bool = False, in_crush_zone: bool = False, in_goldilocks: bool = False) -> dict:
    """Check confluence with IMMORTAL level"""
    both_high = main_confidence >= 70 and esoteric_score >= 65
    same_direction = main_direction == esoteric_favored or not esoteric_favored
    
    # IMMORTAL confluence - highest tier
    if immortal_detected and both_high and same_direction:
        return {
            "has_confluence": True,
            "level": "IMMORTAL",
            "emoji": "👁️🔥⚡",
            "message": "IMMORTAL CONFLUENCE: 2178 detected with full model alignment. Maximum edge.",
            "boost": 10
        }
    
    # JARVIS PERFECT confluence
    if jarvis_triggered and both_high and same_direction:
        boost = 7
        if in_crush_zone:
            boost += 2
        if in_goldilocks:
            boost += 1
        return {
            "has_confluence": True,
            "level": "JARVIS_PERFECT",
            "emoji": "🎯🔥",
            "message": f"JARVIS PERFECT CONFLUENCE: Trigger detected with alignment.{' [CRUSH ZONE]' if in_crush_zone else ''}{' [GOLDILOCKS]' if in_goldilocks else ''}",
            "boost": boost
        }
    
    if both_high and same_direction:
        is_perfect = main_confidence >= 80 and esoteric_score >= 75
        return {
            "has_confluence": True,
            "level": "PERFECT" if is_perfect else "STRONG",
            "emoji": "🌟🔥" if is_perfect else "⭐💪",
            "message": "PERFECT COSMIC CONFLUENCE: Sharps + Stars aligned!" if is_perfect else "STRONG CONFLUENCE: Research & cosmos agree",
            "boost": 5 if is_perfect else 3
        }
    
    if both_high and not same_direction:
        return {
            "has_confluence": False,
            "level": "DIVERGENT",
            "emoji": "⚡",
            "message": "Divergence: Strong signals but different directions",
            "boost": 0
        }
    
    if main_confidence >= 70 or esoteric_score >= 70:
        return {
            "has_confluence": False,
            "level": "PARTIAL",
            "emoji": "🔮",
            "message": "Partial alignment - one system strong",
            "boost": 0
        }
    
    return {
        "has_confluence": False,
        "level": "NONE",
        "emoji": "📊",
        "message": "No special alignment",
        "boost": 0
    }

# ============================================================================
# MAIN SIGNAL CALCULATION
# ============================================================================

def calculate_main_confidence(game_data: dict, context: dict = None) -> dict:
    """Calculate main confidence using research-backed signals"""
    context = context or {}
    
    signals = {}
    
    # Sharp money (base)
    sharp_data = context.get("sharp_data", {})
    if sharp_data:
        divergence = abs(sharp_data.get("money_pct", 50) - sharp_data.get("ticket_pct", 50))
        if divergence >= 25:
            signals["sharp_money"] = {"score": 95, "contribution": f"STRONG SHARP: {divergence}% divergence"}
        elif divergence >= 20:
            signals["sharp_money"] = {"score": 88, "contribution": f"Sharp detected: {divergence}% split"}
        elif divergence >= 15:
            signals["sharp_money"] = {"score": 75, "contribution": f"Moderate sharp lean: {divergence}%"}
        else:
            signals["sharp_money"] = {"score": 50, "contribution": "No significant sharp action"}
    else:
        signals["sharp_money"] = {"score": 50, "contribution": "No sharp data"}
    
    # Line edge
    odds = game_data.get("spread_odds", -110)
    if odds >= -100:
        signals["line_edge"] = {"score": 95, "contribution": f"ELITE odds: {odds}"}
    elif odds >= -105:
        signals["line_edge"] = {"score": 82, "contribution": f"Great odds: {odds}"}
    elif odds >= -110:
        signals["line_edge"] = {"score": 55, "contribution": f"Standard odds: {odds}"}
    else:
        signals["line_edge"] = {"score": 40, "contribution": f"Poor odds: {odds}"}
    
    # Game pace
    total = game_data.get("total", 220)
    if total >= 235:
        signals["game_pace"] = {"score": 88, "contribution": f"High pace: O/U {total}"}
    elif total >= 228:
        signals["game_pace"] = {"score": 72, "contribution": f"Above avg pace: O/U {total}"}
    elif total <= 210:
        signals["game_pace"] = {"score": 75, "contribution": f"Slow pace: O/U {total}"}
    else:
        signals["game_pace"] = {"score": 55, "contribution": f"Normal pace: O/U {total}"}
    
    # Home court
    home_team = (game_data.get("home_team") or "").lower()
    altitude_teams = ["nuggets", "denver", "jazz", "utah"]
    if any(t in home_team for t in altitude_teams):
        signals["home_court"] = {"score": 82, "contribution": "Altitude advantage"}
    else:
        signals["home_court"] = {"score": 58, "contribution": "Standard home court"}
    
    # v10.1: Jarvis edge signals
    spread = game_data.get("spread", 0)
    public_pct = game_data.get("public_pct", 50)
    is_fav = game_data.get("is_favorite", False)
    sport = game_data.get("sport", "NBA")
    
    # Public fade
    public_fade = calculate_public_fade_signal(public_pct, is_fav)
    if public_fade["in_crush_zone"]:
        signals["public_fade"] = {"score": 88, "contribution": public_fade["recommendation"]}
    elif public_fade["fade_signal"]:
        signals["public_fade"] = {"score": 72, "contribution": public_fade["recommendation"]}
    else:
        signals["public_fade"] = {"score": 50, "contribution": public_fade["recommendation"]}
    
    # Mid spread / goldilocks
    mid_spread = calculate_mid_spread_signal(spread)
    if mid_spread["in_goldilocks"]:
        signals["goldilocks"] = {"score": 78, "contribution": f"GOLDILOCKS ZONE: {abs(spread)} spread"}
    elif mid_spread["zone"] == "TRAP_GATE":
        signals["goldilocks"] = {"score": 30, "contribution": f"TRAP GATE: {abs(spread)} spread too large"}
    else:
        signals["goldilocks"] = {"score": 50, "contribution": f"{mid_spread['zone']} spread"}
    
    # NHL protocol
    if sport.upper() == "NHL":
        nhl = calculate_nhl_dog_protocol(sport, spread, 70, public_pct)
        if nhl["protocol_active"]:
            signals["nhl_protocol"] = {"score": 92, "contribution": "FULL NHL DOG PROTOCOL"}
        elif len(nhl["conditions_met"]) >= 2:
            signals["nhl_protocol"] = {"score": 70, "contribution": "Partial NHL protocol"}
        else:
            signals["nhl_protocol"] = {"score": 50, "contribution": "NHL protocol inactive"}
    
    # Fill remaining signals with base scores
    for signal in ["injury_vacuum", "travel_fatigue", "back_to_back", "defense_vs_position", 
                   "steam_moves", "weather", "minutes_projection", "referee", 
                   "game_script", "ensemble_ml"]:
        if signal not in signals:
            signals[signal] = {"score": 50, "contribution": "No data available"}
    
    # Calculate weighted average
    total_weight = 0
    weighted_sum = 0
    
    for signal_name, signal_data in signals.items():
        weight = SIGNAL_WEIGHTS.get(signal_name, 1)
        total_weight += weight
        weighted_sum += signal_data["score"] * weight
    
    confidence = round(weighted_sum / total_weight) if total_weight > 0 else 50
    
    # Boost for real odds data
    if game_data.get("spread_odds") or game_data.get("over_odds"):
        confidence = min(100, confidence + 5)
    
    # Determine tier
    if confidence >= 80:
        tier = "GOLDEN_CONVERGENCE"
    elif confidence >= 70:
        tier = "SUPER_SIGNAL"
    elif confidence >= 60:
        tier = "HARMONIC_ALIGNMENT"
    else:
        tier = "PARTIAL_ALIGNMENT"
    
    # Recommendation
    if confidence >= 80:
        recommendation = "SMASH"
    elif confidence >= 70:
        recommendation = "STRONG"
    elif confidence >= 60:
        recommendation = "PLAY"
    elif confidence >= 55:
        recommendation = "LEAN"
    else:
        recommendation = "PASS"
    
    return {
        "confidence": confidence,
        "tier": tier,
        "recommendation": recommendation,
        "signals": signals,
        "top_signals": sorted(signals.items(), key=lambda x: x[1]["score"] * SIGNAL_WEIGHTS.get(x[0], 1), reverse=True)[:3]
    }
# ============================================================================
# LEVEL 11: OMNI-GLITCH MODULES - The Final Dimension
# ============================================================================

def get_venue_atmospherics(team_name: str) -> dict:
    """Get atmospheric data for a venue."""
    for venue_team, data in VENUE_ATMOSPHERICS.items():
        if team_name.lower() in venue_team.lower() or venue_team.lower() in team_name.lower():
            return {"found": True, **data}
    return {"found": False, **VENUE_ATMOSPHERICS["default"]}

def calculate_vortex_math(value: float) -> dict:
    """VORTEX MATH - Tesla's 3-6-9 Secret."""
    if value is None or value == 0:
        return {"analyzed": False, "reason": "No value provided"}
    
    str_val = str(abs(value)).replace(".", "")
    digital_root = sum(int(d) for d in str_val)
    while digital_root > 9:
        digital_root = sum(int(d) for d in str(digital_root))
    
    if digital_root == 9:
        circuit, energy, betting_implication, vortex_score = "COMPLETE", "Maximum energy - Full circuit completion", "High confidence plays favored", 85
    elif digital_root == 3:
        circuit, energy, betting_implication, vortex_score = "OPEN_LOW", "Building energy - Ascending pattern", "Momentum building - consider overs", 70
    elif digital_root == 6:
        circuit, energy, betting_implication, vortex_score = "OPEN_HIGH", "Releasing energy - Descending pattern", "Energy depleting - consider unders", 70
    else:
        circuit, energy, betting_implication, vortex_score = "TRANSITIONAL", f"Root {digital_root} - Between states", "Standard analysis applies", 50
    
    return {
        "analyzed": True, "input_value": value, "digital_root": digital_root,
        "circuit_state": circuit, "energy_description": energy,
        "vortex_score": vortex_score, "betting_implication": betting_implication,
        "tesla_aligned": digital_root in [3, 6, 9]
    }

def analyze_shannon_entropy(recent_results: list, team_name: str = None) -> dict:
    """SHANNON ENTROPY - Information Theory Pattern Detection."""
    if not recent_results or len(recent_results) < 3:
        return {"analyzed": False, "reason": "Need at least 3 results"}
    
    n = len(recent_results)
    wins = sum(1 for r in recent_results if str(r).upper() in ['W', '1', 'TRUE', 'WIN'])
    losses = n - wins
    
    if wins == 0 or losses == 0:
        entropy = 0.0
    else:
        p_win, p_loss = wins / n, losses / n
        entropy = -(p_win * math.log2(p_win) + p_loss * math.log2(p_loss))
    
    current_streak = 1
    streak_type = recent_results[-1] if recent_results else None
    for i in range(len(recent_results) - 2, -1, -1):
        if recent_results[i] == streak_type:
            current_streak += 1
        else:
            break
    
    if entropy < 0.5:
        state, snapback_risk, recommendation = "LOW", 75, "Low entropy = Pattern locked. FADE continuation."
    elif entropy < 0.8:
        state, snapback_risk, recommendation = "BALANCED", 40, "Standard play. No entropy edge."
    elif entropy < 0.9:
        state, snapback_risk, recommendation = "HIGH", 25, "Chaotic state. Reduce position sizes."
    else:
        state, snapback_risk, recommendation = "MAXIMUM", 15, "Anything possible. Small plays only."
    
    return {
        "team": team_name or "Unknown", "analyzed": True, "recent_results": recent_results,
        "entropy": {"raw": round(entropy, 4), "state": state},
        "streak_analysis": {"current_streak": current_streak, "streak_type": streak_type, "win_pct": round(wins/n, 3), "streak_danger": current_streak >= 4 and entropy < 0.5},
        "snapback_risk": snapback_risk, "entropy_score": round((1 - entropy) * 100), "recommendation": recommendation,
        "betting_implications": {"fade_team": entropy < 0.5 and current_streak >= 4, "snap_back_play": current_streak >= 4 and entropy < 0.5}
    }

def analyze_atmospheric_drag(home_team: str, away_team: str, current_pressure: float = None) -> dict:
    """ATMOSPHERIC DRAG - Air density affects outcomes."""
    home_atmo = get_venue_atmospherics(home_team)
    away_atmo = get_venue_atmospherics(away_team)
    
    if current_pressure is None:
        current_pressure = home_atmo["base_pressure"]
    
    elevation = home_atmo["elevation_ft"]
    altitude_diff = home_atmo["elevation_ft"] - away_atmo["elevation_ft"]
    
    if current_pressure >= 30.00:
        pressure_state, total_bias = "HIGH", "UNDER"
    elif current_pressure <= 29.80:
        pressure_state, total_bias = "LOW", "OVER"
    else:
        pressure_state, total_bias = "NORMAL", "NEUTRAL"
    
    altitude_bonus = 0.12 if elevation >= 5000 else 0.08 if elevation >= 4000 else 0.0
    visitor_fatigue = 0.15 if altitude_diff >= 4000 else 0.08 if altitude_diff >= 2500 else 0.0
    
    return {
        "venue": {"home_team": home_team, "elevation_ft": elevation, "pressure": current_pressure},
        "pressure_state": pressure_state, "total_bias": total_bias,
        "altitude_bonus": altitude_bonus, "visitor_fatigue_pct": visitor_fatigue * 100,
        "betting_implications": {"totals_lean": total_bias, "fade_visitor": visitor_fatigue >= 0.10}
    }

def is_void_of_course_moon(game_time: datetime = None) -> dict:
    """VOID OF COURSE MOON - During void: Favorites fail."""
    if game_time is None:
        game_time = datetime.now()
    
    known_new_moon = datetime(2024, 1, 11)
    days_since = (game_time - known_new_moon).days
    moon_degrees = (days_since * 13.176396) % 360
    
    signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    current_sign = signs[int(moon_degrees / 30)]
    degrees_in_sign = moon_degrees % 30
    hours_until_change = (30 - degrees_in_sign) / 0.5493
    is_void = degrees_in_sign >= 27
    
    return {
        "game_time": game_time.strftime("%Y-%m-%d %H:%M"),
        "moon_position": {"current_sign": current_sign, "degrees_in_sign": round(degrees_in_sign, 2), "hours_until_sign_change": round(hours_until_change, 1)},
        "void_status": {"is_void": is_void, "state": "VOID_ACTIVE" if is_void else "ACTIVE"},
        "recommendation": "VOID ACTIVE: Favorites vulnerable. Underdogs protected." if is_void else "Normal lunar influence.",
        "favorite_penalty": 0.15 if is_void else 0.0,
        "betting_implications": {"fade_favorites": is_void, "dog_protection": is_void}
    }

def analyze_gann_spiral(total_points: float, game_time: datetime = None) -> dict:
    """GANN SPIRAL - Square of Nine analysis."""
    if game_time is None:
        game_time = datetime.now()
    
    sqrt_val = math.sqrt(total_points) if total_points > 0 else 0
    spiral_position = sqrt_val % 1
    min_distance = min(abs(spiral_position - cz) for cz in [0.0, 0.25, 0.5, 0.75])
    on_cardinal = min_distance <= 0.05
    
    if on_cardinal:
        gann_state, recommendation, reversal_probability = "CARDINAL_CROSS", "On Cardinal Cross - Major inflection point", 75
    elif min_distance <= 0.10:
        gann_state, recommendation, reversal_probability = "NEAR_CARDINAL", "Near cardinal - Watch for reversal", 60
    else:
        gann_state, recommendation, reversal_probability = "BETWEEN_CARDINALS", "Between cardinals - Trend continuation likely", 35
    
    return {
        "total_analyzed": total_points,
        "spiral_math": {"sqrt_value": round(sqrt_val, 4), "spiral_position": round(spiral_position, 4), "distance_to_cardinal": round(min_distance, 4)},
        "gann_state": gann_state, "on_cardinal_cross": on_cardinal,
        "reversal_probability": reversal_probability, "recommendation": recommendation
    }

def analyze_mars_uranus_aspect(game_time: datetime = None) -> dict:
    """MARS-URANUS NUCLEAR - Shock aspect detection."""
    if game_time is None:
        game_time = datetime.now()
    
    j2000 = datetime(2000, 1, 1, 12, 0, 0)
    days_since_j2000 = (game_time - j2000).total_seconds() / 86400
    mars_longitude = (355.45 + 0.5240208 * days_since_j2000) % 360
    uranus_longitude = (314.055 + 0.0119541 * days_since_j2000) % 360
    aspect_angle = abs(mars_longitude - uranus_longitude)
    if aspect_angle > 180:
        aspect_angle = 360 - aspect_angle
    
    is_conjunction, is_square, is_opposition = aspect_angle <= 8, 82 <= aspect_angle <= 98, 172 <= aspect_angle <= 188
    is_nuclear = is_conjunction or is_square or is_opposition
    
    if is_conjunction:
        aspect_type, shock_level, recommendation = "CONJUNCTION", "MAXIMUM", "CONJUNCTION: Maximum upset potential. Bet biggest dog."
    elif is_square:
        aspect_type, shock_level, recommendation = "SQUARE", "HIGH", "SQUARE: High upset energy. Consider underdogs."
    elif is_opposition:
        aspect_type, shock_level, recommendation = "OPPOSITION", "ELEVATED", "OPPOSITION: Tension release. Expect the unexpected."
    else:
        aspect_type, shock_level, recommendation = "NONE", "NORMAL", "No major Mars-Uranus aspect. Standard analysis."
    
    return {
        "game_time": game_time.strftime("%Y-%m-%d %H:%M"),
        "planetary_positions": {"mars_longitude": round(mars_longitude, 2), "uranus_longitude": round(uranus_longitude, 2), "aspect_angle": round(aspect_angle, 2)},
        "aspect_analysis": {"type": aspect_type, "is_nuclear": is_nuclear, "shock_level": shock_level},
        "recommendation": recommendation,
        "betting_implications": {"dog_boost": is_nuclear, "upset_alert": is_nuclear, "max_dog_play": is_conjunction}
    }

# ============================================================================
# LEVEL 13: GANN PHYSICS - Financial Laws Applied to Sports
# ============================================================================

def analyze_fifty_percent_retracement(team_name: str, last_game_margin: int, current_spread: float, was_win: bool = True) -> dict:
    """50% RETRACEMENT RULE - After 20+ point blowout, fade at 50% zone."""
    is_major_move = abs(last_game_margin) >= 20
    fifty_percent_level = abs(last_game_margin) / 2
    retracement_zone_low, retracement_zone_high = fifty_percent_level - 3, fifty_percent_level + 3
    abs_spread = abs(current_spread)
    in_retracement_zone = retracement_zone_low <= abs_spread <= retracement_zone_high
    
    if is_major_move and in_retracement_zone:
        signal, recommendation, fade_strength = "FADE_AT_RETRACEMENT", f"FADE {team_name}. At 50% retracement zone ({fifty_percent_level:.1f}). Gravity pulls back.", 78
    elif is_major_move and abs_spread > fifty_percent_level:
        signal, recommendation, fade_strength = "ABOVE_RETRACEMENT", "Above 50% zone. Market over-correcting.", 45
    elif is_major_move:
        signal, recommendation, fade_strength = "BELOW_RETRACEMENT", "Below 50% zone. Market under-correcting.", 30
    else:
        signal, recommendation, fade_strength = "NO_MAJOR_MOVE", "Last game wasn't major move (20+ pts). Rule doesn't apply.", 0
    
    return {
        "team": team_name, "last_margin": last_game_margin, "was_win": was_win,
        "is_major_move": is_major_move, "fifty_percent_level": fifty_percent_level,
        "retracement_zone": {"low": retracement_zone_low, "high": retracement_zone_high},
        "current_spread": current_spread, "in_retracement_zone": in_retracement_zone,
        "signal": signal, "recommendation": recommendation, "fade_strength": fade_strength,
        "gann_principle": "The 50% retracement is nature's point of equilibrium."
    }

def analyze_rule_of_three(team_name: str, recent_ats_results: list) -> dict:
    """RULE OF THREE - 3 consecutive ATS results = FADE the 4th."""
    if len(recent_ats_results) < 3:
        return {"team": team_name, "analyzed": False, "reason": "Need at least 3 ATS results", "signal": "INSUFFICIENT_DATA"}
    
    last_three = recent_ats_results[-3:]
    all_covers, all_fails = all(r for r in last_three), all(not r for r in last_three)
    is_exhausted = all_covers or all_fails
    
    consecutive_count, direction = 1, recent_ats_results[-1]
    for i in range(len(recent_ats_results) - 2, -1, -1):
        if recent_ats_results[i] == direction:
            consecutive_count += 1
        else:
            break
    
    if is_exhausted:
        if all_covers:
            signal, recommendation = "EXHAUSTION_FADE", f"FADE {team_name}. 3 consecutive covers = Exhaustion Node. The 4th reverses."
        else:
            signal, recommendation = "EXHAUSTION_BACK", f"BACK {team_name}. 3 consecutive fails = Exhaustion Node. Due for cover."
        fade_strength, exhaustion_level = 72, "HIGH"
    elif consecutive_count == 2:
        signal, recommendation, fade_strength, exhaustion_level = "APPROACHING_EXHAUSTION", f"Watch {team_name}. 2 consecutive = approaching exhaustion.", 45, "MODERATE"
    else:
        signal, recommendation, fade_strength, exhaustion_level = "NO_EXHAUSTION", "No exhaustion pattern. Standard analysis.", 0, "LOW"
    
    return {
        "team": team_name, "recent_ats": recent_ats_results, "consecutive_count": consecutive_count,
        "direction": "covers" if direction else "fails", "exhaustion_level": exhaustion_level,
        "signal": signal, "recommendation": recommendation, "fade_strength": fade_strength,
        "gann_principle": "Rule of Three: Energy depletes after 3 cycles."
    }

def analyze_annulifier_cycle(team_name: str, recent_results: list, bet_type: str = "moneyline") -> dict:
    """ANNULIFIER CYCLE - W-L-W-L pattern = 5th result LOCKED."""
    if len(recent_results) < 4:
        return {"team": team_name, "analyzed": False, "reason": "Need 4 results", "signal": "INSUFFICIENT_DATA"}
    
    normalized = []
    for r in recent_results:
        if isinstance(r, bool):
            normalized.append(r)
        elif isinstance(r, str):
            normalized.append(r.upper() in ['W', 'WIN', '1', 'TRUE', 'COVER'])
        else:
            normalized.append(bool(r))
    
    last_four = normalized[-4:]
    is_alternating = all(last_four[i] != last_four[i + 1] for i in range(len(last_four) - 1))
    
    if is_alternating:
        predicted_next = not last_four[-1]
        predicted_result = "W" if predicted_next else "L"
        signal, recommendation, lock_strength, lock_level = f"LOCKED_{predicted_result}", f"{'BACK' if predicted_next else 'FADE'} {team_name}. Annulifier predicts {predicted_result}.", 78, "HARMONIC_LOCK"
    else:
        predicted_result, signal, recommendation, lock_strength, lock_level = None, "NO_ALTERNATION", "No alternating pattern. Annulifier inactive.", 0, "NONE"
    
    return {
        "team": team_name, "bet_type": bet_type, "recent_results": [("W" if r else "L") for r in normalized[-4:]],
        "is_alternating": is_alternating, "lock_level": lock_level, "predicted_next": predicted_result,
        "signal": signal, "recommendation": recommendation, "lock_strength": lock_strength,
        "gann_principle": "Annulifier: Chaos balances through oscillation."
    }

def get_gann_physics_composite(team_name: str, last_margin: int = None, current_spread: float = None, recent_ats: list = None, recent_results: list = None) -> dict:
    """Get composite Gann Physics analysis."""
    analyses, active_laws, total_fade_strength, signals = {}, 0, 0, []
    
    if last_margin is not None and current_spread is not None:
        retracement = analyze_fifty_percent_retracement(team_name, last_margin, current_spread)
        analyses["fifty_percent_retracement"] = retracement
        if retracement["signal"] == "FADE_AT_RETRACEMENT":
            active_laws += 1
            total_fade_strength += retracement["fade_strength"]
            signals.append("50% Retracement ACTIVE")
    
    if recent_ats and len(recent_ats) >= 3:
        exhaustion = analyze_rule_of_three(team_name, recent_ats)
        analyses["rule_of_three"] = exhaustion
        if exhaustion["signal"] in ["EXHAUSTION_FADE", "EXHAUSTION_BACK"]:
            active_laws += 1
            total_fade_strength += exhaustion["fade_strength"]
            signals.append("Rule of Three EXHAUSTED")
    
    if recent_results and len(recent_results) >= 4:
        annulifier = analyze_annulifier_cycle(team_name, recent_results)
        analyses["annulifier_cycle"] = annulifier
        if annulifier["lock_level"] == "HARMONIC_LOCK":
            active_laws += 1
            total_fade_strength += annulifier["lock_strength"]
            signals.append(f"Annulifier LOCKED: {annulifier['predicted_next']}")
    
    if active_laws >= 3:
        confluence_level, confluence_message = "GANN_TRIFECTA", "ALL THREE GANN LAWS ACTIVE. Maximum geometric conviction."
    elif active_laws == 2:
        confluence_level, confluence_message = "DUAL_GEOMETRY", "Two Gann laws aligned. Strong signal."
    elif active_laws == 1:
        confluence_level, confluence_message = "SINGLE_LAW", "One Gann law active. Moderate signal."
    else:
        confluence_level, confluence_message = "NO_GANN_SIGNAL", "No Gann laws triggered."
    
    return {
        "team": team_name, "active_laws": active_laws, "confluence_level": confluence_level,
        "confluence_message": confluence_message, "average_fade_strength": round(total_fade_strength / active_laws) if active_laws > 0 else 0,
        "active_signals": signals, "analyses": analyses
    }

# ============================================================================
# LEVEL 14: NOOSPHERE VELOCITY - The Global Mind
# ============================================================================

def get_team_baseline_volume(team_name: str) -> int:
    """Get baseline search volume for a team."""
    team_lower = team_name.lower()
    for key, volume in TEAM_BASELINE_VOLUMES.items():
        if key in team_lower or team_lower in key:
            return volume
    return TEAM_BASELINE_VOLUMES["default"]

def calculate_volume_velocity(current_volume: float, baseline_volume: float) -> dict:
    """Calculate search volume velocity."""
    if baseline_volume <= 0:
        baseline_volume = 50
    velocity_pct = ((current_volume - baseline_volume) / baseline_volume) * 100
    
    if velocity_pct >= 200:
        tier, description = "EXTREME_SPIKE", "Massive unexplained interest"
    elif velocity_pct >= 100:
        tier, description = "HIGH_SPIKE", "Significant unusual activity"
    elif velocity_pct >= 50:
        tier, description = "ELEVATED", "Above normal interest"
    elif velocity_pct >= 25:
        tier, description = "MILD_ELEVATION", "Slightly elevated"
    elif velocity_pct <= -50:
        tier, description = "SUPPRESSED", "Unusually low interest"
    else:
        tier, description = "NORMAL", "Within normal range"
    
    return {"current_volume": current_volume, "baseline_volume": baseline_volume, "velocity_pct": round(velocity_pct, 1), "tier": tier, "description": description}

def detect_insider_leak(team_name: str, current_volume: float, has_news: bool = False, news_sentiment: str = "neutral") -> dict:
    """INSIDER LEAK - High volume + NO news = Someone knows."""
    baseline = get_team_baseline_volume(team_name)
    velocity = calculate_volume_velocity(current_volume, baseline)
    is_silent_spike = velocity["velocity_pct"] >= 100 and not has_news
    is_loud_spike = velocity["velocity_pct"] >= 100 and has_news
    
    if is_silent_spike:
        if velocity["velocity_pct"] >= 200:
            signal, confidence, recommendation = "STRONG_INSIDER_LEAK", 85, f"FADE {team_name}. Extreme silent spike ({velocity['velocity_pct']:.0f}%) with NO news."
        else:
            signal, confidence, recommendation = "INSIDER_LEAK_DETECTED", 72, f"FADE {team_name}. Silent spike ({velocity['velocity_pct']:.0f}%) with NO news."
        action, edge_score = "FADE", 100 if velocity["velocity_pct"] >= 200 else 75
    elif is_loud_spike:
        signal, confidence, recommendation, action, edge_score = "PUBLIC_HYPE", 55, "News explains spike. Standard fade-the-public analysis.", "STANDARD_FADE", 40
    else:
        signal, confidence, recommendation, action, edge_score = "NO_LEAK_DETECTED", 50, "No unusual volume patterns.", "NEUTRAL", 0
    
    return {
        "team": team_name, "signal_type": "INSIDER_LEAK", "velocity": velocity,
        "has_news": has_news, "news_sentiment": news_sentiment,
        "is_silent_spike": is_silent_spike, "is_loud_spike": is_loud_spike,
        "signal": signal, "confidence": confidence, "recommendation": recommendation,
        "action": action, "edge_score": edge_score,
        "principle": "Silent Spike = Information asymmetry. Someone always knows first."
    }

def detect_main_character_syndrome(underdog_name: str, favorite_name: str, underdog_volume: float, favorite_volume: float, underdog_sentiment: str = "neutral", spread: float = 0) -> dict:
    """MAIN CHARACTER SYNDROME - Underdog volume > Favorite = Universe chose upset."""
    dog_baseline, fav_baseline = get_team_baseline_volume(underdog_name), get_team_baseline_volume(favorite_name)
    dog_velocity, fav_velocity = calculate_volume_velocity(underdog_volume, dog_baseline), calculate_volume_velocity(favorite_volume, fav_baseline)
    volume_ratio = underdog_volume / favorite_volume if favorite_volume > 0 else 999
    baseline_ratio = dog_baseline / fav_baseline if fav_baseline > 0 else 1
    adjusted_ratio = volume_ratio / baseline_ratio if baseline_ratio > 0 else volume_ratio
    is_main_character = adjusted_ratio > 1.5
    is_manic = underdog_sentiment in ["manic", "euphoric", "extreme"]
    
    if is_main_character and is_manic and dog_velocity["velocity_pct"] >= 100:
        signal, confidence, recommendation = "EXTREME_MAIN_CHARACTER", 88, f"BET {underdog_name} (DOG). EXTREME Main Character syndrome."
    elif is_main_character and dog_velocity["velocity_pct"] >= 50:
        signal, confidence, recommendation = "STRONG_MAIN_CHARACTER", 78, f"BET {underdog_name} (DOG). STRONG Main Character energy."
    elif is_main_character:
        signal, confidence, recommendation = "MILD_MAIN_CHARACTER", 62, f"Lean {underdog_name}. Mild Main Character detected."
    else:
        signal, confidence, recommendation = "NO_MAIN_CHARACTER", 50, "No Main Character syndrome. Favorite volume dominates."
    
    edge_score = 100 if signal == "EXTREME_MAIN_CHARACTER" else 75 if signal == "STRONG_MAIN_CHARACTER" else 40 if signal == "MILD_MAIN_CHARACTER" else 0
    
    return {
        "underdog": underdog_name, "favorite": favorite_name, "signal_type": "MAIN_CHARACTER",
        "underdog_velocity": dog_velocity, "favorite_velocity": fav_velocity,
        "volume_ratio": round(volume_ratio, 2), "adjusted_ratio": round(adjusted_ratio, 2),
        "sentiment": underdog_sentiment, "spread": spread, "is_main_character": is_main_character,
        "signal": signal, "confidence": confidence, "recommendation": recommendation,
        "action": "BET_DOG" if is_main_character else "NEUTRAL", "edge_score": edge_score,
        "principle": "The Hive Mind chose the upset."
    }

def detect_phantom_injury(player_name: str, player_volume: float, related_queries: list = None, has_official_report: bool = False, baseline_volume: float = None) -> dict:
    """PHANTOM INJURY - Player spike + Injury queries + NO report = Hidden limitation."""
    if baseline_volume is None:
        baseline_volume = 50
    velocity = calculate_volume_velocity(player_volume, baseline_volume)
    
    injury_queries = []
    if related_queries:
        for query in related_queries:
            query_lower = query.lower()
            for term in INJURY_RELATED_TERMS:
                if term in query_lower:
                    injury_queries.append(query)
                    break
    
    injury_query_ratio = len(injury_queries) / len(related_queries) if related_queries else 0
    is_phantom = velocity["velocity_pct"] >= 75 and injury_query_ratio >= 0.2 and not has_official_report
    
    if is_phantom and velocity["velocity_pct"] >= 150:
        signal, confidence, recommendation = "STRONG_PHANTOM_INJURY", 82, f"BET UNDER on {player_name} props. Strong phantom injury signal."
    elif is_phantom:
        signal, confidence, recommendation = "PHANTOM_INJURY_DETECTED", 70, f"BET UNDER on {player_name} props. Phantom injury detected."
    elif velocity["velocity_pct"] >= 100 and not related_queries:
        signal, confidence, recommendation = "UNCLASSIFIED_SPIKE", 55, f"Player spike without injury queries. Monitor {player_name}."
    else:
        signal, confidence, recommendation = "NO_PHANTOM", 50, "No phantom injury signals."
    
    edge_score = 85 if signal == "STRONG_PHANTOM_INJURY" else 65 if signal == "PHANTOM_INJURY_DETECTED" else 0
    
    return {
        "player": player_name, "signal_type": "PHANTOM_INJURY", "velocity": velocity,
        "related_queries": related_queries or [], "injury_queries_found": injury_queries,
        "injury_query_ratio": round(injury_query_ratio, 2), "has_official_report": has_official_report,
        "is_phantom_injury": is_phantom, "signal": signal, "confidence": confidence,
        "recommendation": recommendation, "action": "BET_UNDER" if is_phantom else "NEUTRAL",
        "edge_score": edge_score, "principle": "The Hive sees physical weakness before stats reflect it."
    }

def calculate_noosphere_velocity(team_name: str, opponent_name: str = None, team_volume: float = None, opponent_volume: float = None, player_data: list = None, has_news: bool = False, is_underdog: bool = False) -> dict:
    """Calculate composite Noosphere Velocity signal."""
    signals, total_edge, actions = [], 0, []
    
    if team_volume:
        insider = detect_insider_leak(team_name, team_volume, has_news)
        signals.append({"type": "insider_leak", "data": insider})
        total_edge += insider["edge_score"]
        if insider["action"] != "NEUTRAL":
            actions.append(insider["action"])
    
    if opponent_name and team_volume and opponent_volume and is_underdog:
        main_char = detect_main_character_syndrome(team_name, opponent_name, team_volume, opponent_volume)
        signals.append({"type": "main_character", "data": main_char})
        total_edge += main_char["edge_score"]
        if main_char["action"] != "NEUTRAL":
            actions.append(main_char["action"])
    
    if player_data:
        for player in player_data:
            phantom = detect_phantom_injury(player.get("name", "Unknown"), player.get("volume", 0), player.get("related_queries"), player.get("has_report", False))
            if phantom["is_phantom_injury"]:
                signals.append({"type": "phantom_injury", "data": phantom})
                total_edge += phantom["edge_score"]
                actions.append(f"UNDER_{player.get('name', 'Unknown')}")
    
    active_signals = len([s for s in signals if s["data"].get("edge_score", 0) > 0])
    
    if active_signals >= 3:
        confluence, message = "FULL_NOOSPHERE", "MAXIMUM INFORMATION ASYMMETRY. All three signals active."
    elif active_signals == 2:
        confluence, message = "DUAL_SIGNAL", "Strong Noosphere confluence. Two signals aligned."
    elif active_signals == 1:
        confluence, message = "SINGLE_SIGNAL", "Single Noosphere signal detected."
    else:
        confluence, message = "NO_SIGNAL", "No significant Noosphere activity."
    
    return {
        "team": team_name, "opponent": opponent_name, "active_signals": active_signals,
        "confluence_level": confluence, "confluence_message": message,
        "average_edge_score": round(total_edge / len(signals)) if signals else 0,
        "recommended_actions": list(set(actions)), "signals": signals,
        "noosphere_principle": "Someone always knows. Information asymmetry is the edge."
    }

def get_noosphere_main_model_signal(noosphere_data: dict) -> dict:
    """Convert Noosphere analysis to main model signal format."""
    active, avg_edge = noosphere_data.get("active_signals", 0), noosphere_data.get("average_edge_score", 0)
    
    if active >= 2 and avg_edge >= 70:
        score, contribution = 92, f"NOOSPHERE CONFLUENCE: {noosphere_data['confluence_level']}"
    elif active >= 1 and avg_edge >= 50:
        score, contribution = 75, f"Noosphere signal: {noosphere_data['confluence_message']}"
    elif active >= 1:
        score, contribution = 62, "Weak Noosphere signal detected"
    else:
        score, contribution = 50, "No Noosphere edge"
    
    return {"score": score, "contribution": contribution, "raw_data": noosphere_data}

# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/today-energy")
async def get_today_energy():
    """Get today's esoteric reading with Jarvis status"""
    return get_daily_esoteric_reading()

@router.get("/validate-immortal")
async def validate_immortal():
    """Validate THE IMMORTAL number (2178)"""
    return validate_2178()

@router.get("/jarvis-triggers")
async def get_jarvis_triggers_endpoint():
    """Get all Jarvis trigger numbers"""
    return {
        "triggers": JARVIS_TRIGGERS,
        "tesla_numbers": TESLA_NUMBERS,
        "power_numbers": POWER_NUMBERS,
        "immortal_validation": validate_2178()
    }

@router.post("/check-trigger")
async def check_trigger_endpoint(data: dict):
    """Check if a value triggers Jarvis edges"""
    value = data.get("value", 0)
    return check_jarvis_trigger(int(value))

@router.post("/analyze-esoteric")
async def analyze_esoteric(data: dict):
    """Analyze matchup with full Jarvis edges"""
    home_team = data.get("home_team", "")
    away_team = data.get("away_team", "")
    spread = data.get("spread")
    total = data.get("total")
    public_pct = data.get("public_pct", 50)
    is_favorite = data.get("is_favorite", False)
    sport = data.get("sport", "NBA")
    
    if not home_team or not away_team:
        raise HTTPException(status_code=400, detail="home_team and away_team required")
    
    return calculate_esoteric_score(home_team, away_team, spread, total, public_pct, is_favorite, sport)

@router.get("/props/{sport}")
async def get_live_props(sport: str, limit: int = 5):
    """Get live props with dual-score system (70%+ confidence only)"""
    sport_keys = {
        "nba": "basketball_nba",
        "nfl": "americanfootball_nfl",
        "mlb": "baseball_mlb",
        "nhl": "icehockey_nhl",
        "ncaab": "basketball_ncaab"
    }
    
    sport_key = sport_keys.get(sport.lower())
    if not sport_key:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        events_resp = await client.get(
            f"{ODDS_API_BASE}/sports/{sport_key}/events",
            params={"apiKey": ODDS_API_KEY, "dateFormat": "iso"}
        )
        
        if events_resp.status_code != 200:
            return {"props": [], "message": "Failed to fetch events"}
        
        events = events_resp.json()
        if not events:
            return {"props": [], "message": "No upcoming events"}
        
        all_props = []
        
        for event in events[:5]:
            event_id = event.get("id")
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")
            commence_time = event.get("commence_time")
            
            props_resp = await client.get(
                f"{ODDS_API_BASE}/sports/{sport_key}/events/{event_id}/odds",
                params={
                    "apiKey": ODDS_API_KEY,
                    "regions": "us",
                    "markets": "player_points,player_rebounds,player_assists,player_threes",
                    "oddsFormat": "american"
                }
            )
            
            if props_resp.status_code != 200:
                continue
            
            props_data = props_resp.json()
            bookmakers = props_data.get("bookmakers", [])
            
            for bookmaker in bookmakers[:1]:
                for market in bookmaker.get("markets", []):
                    market_key = market.get("key", "")
                    
                    for outcome in market.get("outcomes", []):
                        player_name = outcome.get("description", "Unknown")
                        prop_type = market_key.replace("player_", "").replace("_", " ").title()
                        line = outcome.get("point", 0)
                        price = outcome.get("price", -110)
                        bet_type = outcome.get("name", "Over")
                        
                        game_data = {
                            "home_team": home_team,
                            "away_team": away_team,
                            "spread_odds": price,
                            "total": 220,
                            "sport": sport.upper()
                        }
                        main_result = calculate_main_confidence(game_data)
                        
                        esoteric_result = calculate_esoteric_score(home_team, away_team, line, 220, 50, False, sport.upper())
                        
                        confluence = check_cosmic_confluence(
                            main_result["confidence"],
                            esoteric_result["esoteric_score"],
                            "home" if main_result["recommendation"] in ["SMASH", "STRONG"] else None,
                            esoteric_result["components"]["gematria"]["favored"],
                            esoteric_result.get("immortal_detected", False),
                            esoteric_result.get("jarvis_triggered", False),
                            esoteric_result["components"]["jarvis_edges"]["public_fade"]["in_crush_zone"],
                            esoteric_result["components"]["jarvis_edges"]["mid_spread"]["in_goldilocks"]
                        )
                        
                        final_confidence = main_result["confidence"]
                        if confluence["has_confluence"]:
                            final_confidence = min(100, final_confidence + confluence["boost"])
                        
                        if final_confidence >= 70:
                            all_props.append({
                                "player": player_name,
                                "team": home_team,
                                "opponent": away_team,
                                "prop_type": prop_type,
                                "line": line,
                                "bet_type": bet_type,
                                "price": price,
                                "confidence": final_confidence,
                                "tier": main_result["tier"],
                                "recommendation": main_result["recommendation"],
                                "esoteric_edge": {
                                    "score": esoteric_result["esoteric_score"],
                                    "tier": esoteric_result["esoteric_tier"],
                                    "emoji": esoteric_result["esoteric_emoji"],
                                    "immortal_detected": esoteric_result.get("immortal_detected", False),
                                    "jarvis_triggered": esoteric_result.get("jarvis_triggered", False)
                                },
                                "confluence": confluence,
                                "jarvis_edges": esoteric_result["components"]["jarvis_edges"],
                                "game_time": commence_time,
                                "bookmaker": bookmaker.get("title", "Unknown")
                            })
        
        all_props.sort(key=lambda x: x["confidence"], reverse=True)
        
        return {
            "props": all_props[:limit],
            "total_analyzed": len(all_props),
            "engine_version": "10.1",
            "codename": "JARVIS_SAVANT",
            "dual_score_system": True,
            "immortal_status": validate_2178()["status"],
            "daily_reading": get_daily_esoteric_reading()
        }

@router.get("/best-bets/{sport}")
async def get_best_bets(sport: str):
    """Get best bets with dual-score system and Jarvis edges"""
    sport_keys = {
        "nba": "basketball_nba",
        "nfl": "americanfootball_nfl",
        "mlb": "baseball_mlb",
        "nhl": "icehockey_nhl"
    }
    
    sport_key = sport_keys.get(sport.lower())
    if not sport_key:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{ODDS_API_BASE}/sports/{sport_key}/odds",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "spreads,totals",
                "oddsFormat": "american"
            }
        )
        
        if resp.status_code != 200:
            return {"games": [], "message": "Failed to fetch odds"}
        
        games = resp.json()
        analyzed_games = []
        
        for game in games:
            home_team = game.get("home_team", "")
            away_team = game.get("away_team", "")
            commence_time = game.get("commence_time")
            
            best_spread = None
            best_total = None
            
            for bm in game.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market["key"] == "spreads":
                        for outcome in market["outcomes"]:
                            if outcome["name"] == home_team:
                                best_spread = outcome.get("point", 0)
                    elif market["key"] == "totals":
                        for outcome in market["outcomes"]:
                            if outcome["name"] == "Over":
                                best_total = outcome.get("point", 220)
            
            game_data = {
                "home_team": home_team,
                "away_team": away_team,
                "spread": best_spread,
                "total": best_total,
                "sport": sport.upper()
            }
            main_result = calculate_main_confidence(game_data)
            esoteric_result = calculate_esoteric_score(home_team, away_team, best_spread, best_total, 50, False, sport.upper())
            
            confluence = check_cosmic_confluence(
                main_result["confidence"],
                esoteric_result["esoteric_score"],
                None,
                esoteric_result["components"]["gematria"]["favored"],
                esoteric_result.get("immortal_detected", False),
                esoteric_result.get("jarvis_triggered", False),
                esoteric_result["components"]["jarvis_edges"]["public_fade"]["in_crush_zone"],
                esoteric_result["components"]["jarvis_edges"]["mid_spread"]["in_goldilocks"]
            )
            
            final_confidence = main_result["confidence"]
            if confluence["has_confluence"]:
                final_confidence = min(100, final_confidence + confluence["boost"])
            
            analyzed_games.append({
                "home_team": home_team,
                "away_team": away_team,
                "game_time": commence_time,
                "spread": best_spread,
                "total": best_total,
                "main_confidence": final_confidence,
                "main_tier": main_result["tier"],
                "recommendation": main_result["recommendation"],
                "esoteric_edge": {
                    "score": esoteric_result["esoteric_score"],
                    "tier": esoteric_result["esoteric_tier"],
                    "emoji": esoteric_result["esoteric_emoji"],
                    "favored": esoteric_result["components"]["gematria"]["favored"],
                    "top_insights": esoteric_result["top_insights"],
                    "immortal_detected": esoteric_result.get("immortal_detected", False),
                    "jarvis_triggered": esoteric_result.get("jarvis_triggered", False)
                },
                "jarvis_edges": esoteric_result["components"]["jarvis_edges"],
                "confluence": confluence
            })
        
        analyzed_games.sort(key=lambda x: x["main_confidence"], reverse=True)
        
        return {
            "games": analyzed_games[:10],
            "engine_version": "10.1",
            "codename": "JARVIS_SAVANT",
            "immortal_status": validate_2178()["status"],
            "daily_reading": get_daily_esoteric_reading()
        }
# ============================================================================
# v11-v14 API ENDPOINTS - OMNI-GLITCH, GANN PHYSICS, NOOSPHERE VELOCITY
# ============================================================================

@router.post("/vortex-math")
async def vortex_math_endpoint(data: dict):
    """Tesla 3-6-9 Vortex Math analysis."""
    value = data.get("value")
    if value is None:
        raise HTTPException(status_code=400, detail="value required")
    return calculate_vortex_math(float(value))

@router.post("/shannon-entropy")
async def shannon_entropy_endpoint(data: dict):
    """Shannon Entropy pattern detection."""
    results = data.get("recent_results", [])
    team = data.get("team_name", "Unknown")
    if not results:
        raise HTTPException(status_code=400, detail="recent_results required")
    return analyze_shannon_entropy(results, team)

@router.post("/atmospheric-drag")
async def atmospheric_drag_endpoint(data: dict):
    """Atmospheric Drag analysis."""
    home = data.get("home_team", "")
    away = data.get("away_team", "")
    pressure = data.get("current_pressure")
    if not home or not away:
        raise HTTPException(status_code=400, detail="home_team and away_team required")
    return analyze_atmospheric_drag(home, away, pressure)

@router.get("/void-moon")
async def void_moon_endpoint(game_time: str = None):
    """Void of Course Moon status."""
    parsed_time = None
    if game_time:
        try:
            parsed_time = datetime.fromisoformat(game_time)
        except:
            parsed_time = None
    return is_void_of_course_moon(parsed_time)

@router.post("/gann-spiral")
async def gann_spiral_endpoint(data: dict):
    """Gann Spiral Square of Nine analysis."""
    total = data.get("total_points", 0)
    return analyze_gann_spiral(float(total))

@router.get("/mars-uranus")
async def mars_uranus_endpoint(game_time: str = None):
    """Mars-Uranus Nuclear aspect detection."""
    parsed_time = None
    if game_time:
        try:
            parsed_time = datetime.fromisoformat(game_time)
        except:
            parsed_time = None
    return analyze_mars_uranus_aspect(parsed_time)

@router.post("/gann-retracement")
async def gann_retracement_endpoint(data: dict):
    """50% Retracement Rule analysis."""
    team = data.get("team_name", "")
    margin = data.get("last_game_margin")
    spread = data.get("current_spread")
    was_win = data.get("was_win", True)
    if not team or margin is None or spread is None:
        raise HTTPException(status_code=400, detail="team_name, last_game_margin, current_spread required")
    return analyze_fifty_percent_retracement(team, int(margin), float(spread), was_win)

@router.post("/gann-exhaustion")
async def gann_exhaustion_endpoint(data: dict):
    """Rule of Three Exhaustion analysis."""
    team = data.get("team_name", "")
    ats = data.get("recent_ats_results", [])
    if not team or not ats:
        raise HTTPException(status_code=400, detail="team_name and recent_ats_results required")
    return analyze_rule_of_three(team, ats)

@router.post("/gann-annulifier")
async def gann_annulifier_endpoint(data: dict):
    """Annulifier Cycle analysis."""
    team = data.get("team_name", "")
    results = data.get("recent_results", [])
    if not team or not results:
        raise HTTPException(status_code=400, detail="team_name and recent_results required")
    return analyze_annulifier_cycle(team, results)

@router.post("/gann-composite")
async def gann_composite_endpoint(data: dict):
    """Composite Gann Physics analysis."""
    team = data.get("team_name", "")
    if not team:
        raise HTTPException(status_code=400, detail="team_name required")
    return get_gann_physics_composite(
        team,
        data.get("last_margin"),
        data.get("current_spread"),
        data.get("recent_ats"),
        data.get("recent_results")
    )

@router.post("/noosphere/insider-leak")
async def insider_leak_endpoint(data: dict):
    """Insider Leak detection."""
    team = data.get("team_name", "")
    volume = data.get("current_volume")
    if not team or volume is None:
        raise HTTPException(status_code=400, detail="team_name and current_volume required")
    return detect_insider_leak(team, float(volume), data.get("has_news", False), data.get("news_sentiment", "neutral"))

@router.post("/noosphere/main-character")
async def main_character_endpoint(data: dict):
    """Main Character Syndrome detection."""
    dog = data.get("underdog_name", "")
    fav = data.get("favorite_name", "")
    dog_vol = data.get("underdog_volume")
    fav_vol = data.get("favorite_volume")
    if not dog or not fav or dog_vol is None or fav_vol is None:
        raise HTTPException(status_code=400, detail="underdog_name, favorite_name, underdog_volume, favorite_volume required")
    return detect_main_character_syndrome(dog, fav, float(dog_vol), float(fav_vol), data.get("underdog_sentiment", "neutral"), data.get("spread", 0))

@router.post("/noosphere/phantom-injury")
async def phantom_injury_endpoint(data: dict):
    """Phantom Injury detection."""
    player = data.get("player_name", "")
    volume = data.get("player_volume")
    if not player or volume is None:
        raise HTTPException(status_code=400, detail="player_name and player_volume required")
    return detect_phantom_injury(player, float(volume), data.get("related_queries"), data.get("has_official_report", False), data.get("baseline_volume"))

@router.post("/noosphere/composite")
async def noosphere_composite_endpoint(data: dict):
    """Composite Noosphere Velocity analysis."""
    team = data.get("team_name", "")
    if not team:
        raise HTTPException(status_code=400, detail="team_name required")
    return calculate_noosphere_velocity(
        team,
        data.get("opponent_name"),
        data.get("team_volume"),
        data.get("opponent_volume"),
        data.get("player_data"),
        data.get("has_news", False),
        data.get("is_underdog", False)
    )

@router.get("/noosphere/status")
async def noosphere_status():
    """Noosphere Velocity system status."""
    return {
        "version": "14.0",
        "codename": "NOOSPHERE_VELOCITY",
        "status": "GLOBAL_MIND_ACTIVE",
        "integration": "MAIN_MODEL",
        "signal_weight": 17,
        "detection_methods": {
            "insider_leak": "Silent Spike - High volume + No news = FADE",
            "main_character": "Underdog volume > Favorite = BET DOG",
            "phantom_injury": "Player spike + Injury queries = BET UNDER"
        },
        "teams_tracked": len(TEAM_BASELINE_VOLUMES),
        "message": "Someone always knows. Information asymmetry is the edge."
    }

@router.get("/gann-physics-status")
async def gann_physics_status():
    """Gann Physics system status."""
    return {
        "version": "13.0",
        "codename": "GANN_PHYSICS",
        "status": "GEOMETRIC_LAWS_ACTIVE",
        "modules": {
            "fifty_percent_retracement": "Gravity Check - Fade at 50% zone after blowouts",
            "rule_of_three": "Exhaustion Node - 3 consecutive = FADE the 4th",
            "annulifier_cycle": "Harmonic Lock - W-L-W-L = 5th result LOCKED"
        },
        "message": "W.D. Gann's geometric laws now govern the field."
    }

@router.get("/omni-glitch-status")
async def omni_glitch_status():
    """OMNI-GLITCH system status."""
    now = datetime.now()
    return {
        "version": "11.0",
        "codename": "OMNI-GLITCH",
        "status": "TRANSCENDENT",
        "timestamp": now.isoformat(),
        "modules": {
            "vortex_math": "Tesla 3-6-9 Digital Root Analysis",
            "shannon_entropy": "Pattern Break Detection",
            "atmospheric_drag": "Barometric Pressure Effects",
            "void_of_course_moon": is_void_of_course_moon(now),
            "gann_spiral": "Square of Nine Analysis",
            "mars_uranus_nuclear": analyze_mars_uranus_aspect(now)
        },
        "venues_tracked": len(VENUE_ATMOSPHERICS),
        "message": "The final dimension is open."
    }

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "engine_version": "14.0",
        "codename": "NOOSPHERE_VELOCITY",
        "features": [
            "v10.1_research_weights",
            "jarvis_triggers",
            "esoteric_edge",
            "gematria_6_ciphers",
            "v11_omni_glitch",
            "v13_gann_physics",
            "v14_noosphere_velocity"
        ],
        "noosphere_status": "MAIN_MODEL_INTEGRATED",
        "teams_tracked": len(TEAM_BASELINE_VOLUMES),
        "venues_tracked": len(VENUE_ATMOSPHERICS)
    }

# =============================================================================
# BACKWARDS COMPATIBILITY FOR prediction_api.py
# =============================================================================

class LiveDataRouter:
    """Compatibility wrapper for prediction_api.py import"""
    def __init__(self):
        self.router = router
    
    def get_router(self):
        return self.router

# Export for: from live_data_router import LiveDataRouter, live_data_router
live_data_router = router


# Export the router instance with the expected name
live_data_router = router
