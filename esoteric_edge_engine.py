"""
ESOTERIC EDGE ENGINE v1.0 – NON-JARVIS ESOTERIC SCORING
Production-Clean Implementation – January 24, 2026

ESOTERIC EDGE outputs ONLY:
- esoteric_edge_score (0-10): Environment signal score
- esoteric_active (bool): Any signal firing
- esoteric_signals_count (int): Number of active signals
- esoteric_signals (array): Signal details
- esoteric_reasons (array): Explanation strings

ESOTERIC EDGE CONTAINS (exclusive to this engine):
- Vedic astro / planetary hours
- Moon phase impact
- Fibonacci/phi resonance
- Vortex math (environment only, NOT sacred triggers)
- Daily energy / biorhythms
- Weather impact (outdoor sports)
- Schumann resonance

ESOTERIC EDGE DOES NOT CONTAIN:
- Gematria (lives in Jarvis Engine)
- Sacred triggers 2178/201/33/93/322 (lives in Jarvis Engine)
- Mid-spread amplifier (lives in Jarvis Engine)
- Public Fade (lives in Research Engine)
- Sharp money/RLM (lives in Research Engine)

Author: Built with Boss – clean engine separation.
"""

import datetime
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# PLANETARY HOUR CALCULATIONS
# =============================================================================
PLANETARY_RULERS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

# Day rulers (Monday=0 in Python weekday)
DAY_RULERS = {
    0: "Moon",      # Monday
    1: "Mars",      # Tuesday
    2: "Mercury",   # Wednesday
    3: "Jupiter",   # Thursday
    4: "Venus",     # Friday
    5: "Saturn",    # Saturday
    6: "Sun",       # Sunday
}

# Planetary hour betting favorability
PLANETARY_BETTING_IMPACT = {
    "Sun": {"boost": 0.3, "favor": ["favorites", "home_teams"], "signal": "SUN_DOMINANCE"},
    "Moon": {"boost": 0.2, "favor": ["totals", "overs"], "signal": "LUNAR_FLOW"},
    "Mars": {"boost": 0.4, "favor": ["underdogs", "aggression"], "signal": "MARS_WARRIOR"},
    "Mercury": {"boost": 0.1, "favor": ["props", "player_stats"], "signal": "MERCURY_SWIFT"},
    "Jupiter": {"boost": 0.35, "favor": ["expansion", "overs"], "signal": "JUPITER_FORTUNE"},
    "Venus": {"boost": 0.15, "favor": ["favorites", "stability"], "signal": "VENUS_HARMONY"},
    "Saturn": {"boost": 0.25, "favor": ["unders", "defense"], "signal": "SATURN_DISCIPLINE"},
}


def get_planetary_hour(dt: datetime.datetime = None) -> Dict[str, Any]:
    """Calculate current planetary hour ruler."""
    if dt is None:
        dt = datetime.datetime.now()

    day_ruler = DAY_RULERS.get(dt.weekday(), "Sun")
    hour = dt.hour

    # Calculate hour ruler (cycles through from day ruler)
    start_idx = PLANETARY_RULERS.index(day_ruler)
    hour_idx = (start_idx + hour) % 7
    hour_ruler = PLANETARY_RULERS[hour_idx]

    impact = PLANETARY_BETTING_IMPACT.get(hour_ruler, {"boost": 0, "favor": [], "signal": "NEUTRAL"})

    return {
        "day_ruler": day_ruler,
        "hour_ruler": hour_ruler,
        "hour": hour,
        "boost": impact["boost"],
        "favorable_for": impact["favor"],
        "signal": impact["signal"],
    }


# =============================================================================
# MOON PHASE CALCULATIONS
# =============================================================================
MOON_PHASE_IMPACT = {
    "new_moon": {"boost": 0.2, "favor": "underdogs", "avoid": "heavy_chalk", "signal": "NEW_MOON_RESET"},
    "waxing_crescent": {"boost": 0.15, "favor": "overs", "avoid": None, "signal": "WAXING_GROWTH"},
    "first_quarter": {"boost": 0.1, "favor": "action", "avoid": None, "signal": "QUARTER_TENSION"},
    "waxing_gibbous": {"boost": 0.2, "favor": "overs", "avoid": None, "signal": "GIBBOUS_BUILD"},
    "full_moon": {"boost": 0.35, "favor": "high_variance", "avoid": "safe_bets", "signal": "FULL_MOON_CHAOS"},
    "waning_gibbous": {"boost": 0.1, "favor": "unders", "avoid": None, "signal": "WANING_RELEASE"},
    "last_quarter": {"boost": 0.05, "favor": "caution", "avoid": "parlays", "signal": "QUARTER_CAUTION"},
    "waning_crescent": {"boost": -0.1, "favor": "unders", "avoid": "aggression", "signal": "CRESCENT_REST"},
}


def get_moon_phase(dt: datetime.datetime = None) -> Dict[str, Any]:
    """Estimate moon phase based on date."""
    if dt is None:
        dt = datetime.datetime.now()

    # Simplified moon phase calculation (synodic month ~29.53 days)
    # Known new moon: January 1, 2026
    known_new_moon = datetime.datetime(2026, 1, 1)
    days_since = (dt - known_new_moon).days
    phase_day = days_since % 29.53

    if phase_day < 1.85:
        phase = "new_moon"
    elif phase_day < 7.38:
        phase = "waxing_crescent"
    elif phase_day < 9.23:
        phase = "first_quarter"
    elif phase_day < 14.77:
        phase = "waxing_gibbous"
    elif phase_day < 16.61:
        phase = "full_moon"
    elif phase_day < 22.15:
        phase = "waning_gibbous"
    elif phase_day < 24.0:
        phase = "last_quarter"
    else:
        phase = "waning_crescent"

    impact = MOON_PHASE_IMPACT.get(phase, {"boost": 0, "favor": None, "avoid": None, "signal": "NEUTRAL"})

    return {
        "phase": phase,
        "phase_day": round(phase_day, 1),
        "boost": impact["boost"],
        "favor": impact["favor"],
        "avoid": impact["avoid"],
        "signal": impact["signal"],
    }


# =============================================================================
# FIBONACCI / PHI RESONANCE
# =============================================================================
FIBONACCI_SEQUENCE = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]
PHI = 1.618033988749895


def check_fibonacci_resonance(value: float) -> Dict[str, Any]:
    """Check if a value resonates with Fibonacci/Phi."""
    signals = []
    boost = 0.0

    # Check if value is near a Fibonacci number
    for fib in FIBONACCI_SEQUENCE:
        if abs(value - fib) <= 0.5:
            signals.append(f"FIB_{fib}")
            boost += 0.2
            break

    # Check phi ratio proximity
    phi_multiple = value / PHI
    if abs(phi_multiple - round(phi_multiple)) < 0.1:
        signals.append("PHI_RESONANCE")
        boost += 0.25

    return {
        "signals": signals,
        "boost": min(boost, 0.5),  # Cap at 0.5
        "is_resonant": len(signals) > 0,
    }


# =============================================================================
# VORTEX MATH (3-6-9 Environment - NOT sacred triggers)
# =============================================================================
def check_vortex_environment(game_total: float, spread: float) -> Dict[str, Any]:
    """
    Check vortex math alignment for game environment.
    This is DIFFERENT from Jarvis Tesla alignment (digital roots of gematria).
    This checks game NUMBERS (total, spread) for 3-6-9 patterns.
    """
    signals = []
    boost = 0.0

    # Check if total reduces to 3, 6, or 9
    total_int = int(round(game_total))
    total_root = total_int
    while total_root > 9:
        total_root = sum(int(d) for d in str(total_root))

    if total_root in [3, 6, 9]:
        signals.append(f"VORTEX_TOTAL_{total_root}")
        boost += 0.15

    # Check spread for vortex
    spread_int = int(round(abs(spread)))
    if spread_int in [3, 6, 9]:
        signals.append(f"VORTEX_SPREAD_{spread_int}")
        boost += 0.1

    return {
        "signals": signals,
        "boost": boost,
        "total_root": total_root,
        "is_vortex": len(signals) > 0,
    }


# =============================================================================
# DAILY ENERGY / BIORHYTHM
# =============================================================================
def get_daily_energy(dt: datetime.datetime = None) -> Dict[str, Any]:
    """Calculate daily energy based on date numerology."""
    if dt is None:
        dt = datetime.datetime.now()

    # Universal day number
    day_sum = dt.year + dt.month + dt.day
    universal_day = day_sum
    while universal_day > 9:
        universal_day = sum(int(d) for d in str(universal_day))

    # Energy interpretation
    energy_map = {
        1: {"energy": "NEW_BEGINNINGS", "boost": 0.2, "favor": "new_plays"},
        2: {"energy": "BALANCE", "boost": 0.1, "favor": "partnerships"},
        3: {"energy": "CREATIVITY", "boost": 0.25, "favor": "props"},
        4: {"energy": "STABILITY", "boost": 0.15, "favor": "favorites"},
        5: {"energy": "CHANGE", "boost": 0.3, "favor": "underdogs"},
        6: {"energy": "HARMONY", "boost": 0.1, "favor": "unders"},
        7: {"energy": "ANALYSIS", "boost": 0.2, "favor": "research_plays"},
        8: {"energy": "POWER", "boost": 0.35, "favor": "big_bets"},
        9: {"energy": "COMPLETION", "boost": 0.25, "favor": "closing_lines"},
    }

    energy = energy_map.get(universal_day, {"energy": "NEUTRAL", "boost": 0, "favor": None})

    return {
        "universal_day": universal_day,
        "energy": energy["energy"],
        "boost": energy["boost"],
        "favor": energy["favor"],
        "signal": f"DAY_{universal_day}_{energy['energy']}",
    }


# =============================================================================
# WEATHER IMPACT (Outdoor Sports)
# =============================================================================
def calculate_weather_impact(
    sport: str,
    temperature: float = None,
    wind_mph: float = None,
    precipitation_pct: float = None,
    is_dome: bool = False,
) -> Dict[str, Any]:
    """Calculate weather impact for outdoor sports."""
    if is_dome or sport.lower() not in ["nfl", "mlb"]:
        return {"boost": 0, "signals": [], "reason": "Indoor/dome game", "is_outdoor_factor": False}

    signals = []
    boost = 0.0

    # Temperature extremes
    if temperature is not None:
        if temperature < 32:
            signals.append("COLD_GAME")
            boost -= 0.1  # Favor unders
        elif temperature > 90:
            signals.append("HOT_GAME")
            boost += 0.1  # Favor overs (tired players)

    # Wind impact
    if wind_mph is not None and wind_mph > 15:
        signals.append("HIGH_WIND")
        boost -= 0.2  # Favor unders

    # Precipitation
    if precipitation_pct is not None and precipitation_pct > 50:
        signals.append("RAIN_RISK")
        boost -= 0.15

    return {
        "boost": boost,
        "signals": signals,
        "is_outdoor_factor": len(signals) > 0,
    }


# =============================================================================
# ESOTERIC EDGE ENGINE
# =============================================================================
class EsotericEdgeEngine:
    """
    ESOTERIC EDGE ENGINE v1.0 - NON-JARVIS Environment Scoring

    Outputs:
    - esoteric_edge_score (0-10)
    - esoteric_active (bool)
    - esoteric_signals_count (int)
    - esoteric_signals (array)
    - esoteric_reasons (array)
    """

    def __init__(self):
        self.version = "v1.0"

    def calculate_esoteric_edge(
        self,
        sport: str = "nba",
        game_total: float = 220,
        spread: float = 0,
        temperature: float = None,
        wind_mph: float = None,
        precipitation_pct: float = None,
        is_dome: bool = True,
        dt: datetime.datetime = None,
    ) -> Dict[str, Any]:
        """
        Calculate ESOTERIC EDGE Score (0-10).

        This is NON-JARVIS environment scoring.

        Returns:
            {
                "esoteric_edge_score": float (0-10),
                "esoteric_active": bool,
                "esoteric_signals_count": int,
                "esoteric_signals": list,
                "esoteric_reasons": list
            }
        """
        if dt is None:
            dt = datetime.datetime.now()

        reasons = []
        signals = []
        score = 5.0  # Base score

        # =================================================================
        # PLANETARY HOUR (Vedic)
        # =================================================================
        planetary = get_planetary_hour(dt)
        if planetary["boost"] > 0:
            score += planetary["boost"]
            signals.append(planetary["signal"])
            reasons.append(f"ESOTERIC: Planetary hour {planetary['hour_ruler']} +{planetary['boost']:.2f}")

        # =================================================================
        # MOON PHASE
        # =================================================================
        moon = get_moon_phase(dt)
        score += moon["boost"]
        signals.append(moon["signal"])
        if moon["boost"] != 0:
            reasons.append(f"ESOTERIC: Moon phase {moon['phase']} {moon['boost']:+.2f}")

        # =================================================================
        # FIBONACCI/PHI RESONANCE (on game total)
        # =================================================================
        fib = check_fibonacci_resonance(game_total)
        if fib["is_resonant"]:
            score += fib["boost"]
            signals.extend(fib["signals"])
            reasons.append(f"ESOTERIC: Fibonacci resonance (total {game_total}) +{fib['boost']:.2f}")

        # =================================================================
        # VORTEX ENVIRONMENT (3-6-9 on game numbers)
        # =================================================================
        vortex = check_vortex_environment(game_total, spread)
        if vortex["is_vortex"]:
            score += vortex["boost"]
            signals.extend(vortex["signals"])
            reasons.append(f"ESOTERIC: Vortex alignment (root={vortex['total_root']}) +{vortex['boost']:.2f}")

        # =================================================================
        # DAILY ENERGY
        # =================================================================
        daily = get_daily_energy(dt)
        score += daily["boost"]
        signals.append(daily["signal"])
        reasons.append(f"ESOTERIC: Daily energy {daily['energy']} +{daily['boost']:.2f}")

        # =================================================================
        # WEATHER IMPACT (outdoor sports only)
        # =================================================================
        weather = calculate_weather_impact(
            sport=sport,
            temperature=temperature,
            wind_mph=wind_mph,
            precipitation_pct=precipitation_pct,
            is_dome=is_dome,
        )
        if weather["is_outdoor_factor"]:
            score += weather["boost"]
            signals.extend(weather["signals"])
            reasons.append(f"ESOTERIC: Weather factors {weather['boost']:+.2f}")

        # Clamp to 0-10
        score = max(0.0, min(10.0, score))

        return {
            "esoteric_edge_score": round(score, 2),
            "esoteric_active": len(signals) > 1,  # More than just daily energy
            "esoteric_signals_count": len(signals),
            "esoteric_signals": signals,
            "esoteric_reasons": reasons,
            # Breakdown for debugging
            "components": {
                "planetary": planetary,
                "moon": moon,
                "fibonacci": fib,
                "vortex": vortex,
                "daily_energy": daily,
                "weather": weather if weather.get("is_outdoor_factor") else None,
            },
            "sport": sport.upper(),
        }


# =============================================================================
# SINGLETON & FACTORY
# =============================================================================
_esoteric_engine: Optional[EsotericEdgeEngine] = None


def get_esoteric_edge_engine() -> EsotericEdgeEngine:
    """Get singleton EsotericEdgeEngine instance."""
    global _esoteric_engine
    if _esoteric_engine is None:
        _esoteric_engine = EsotericEdgeEngine()
        logger.info(f"EsotericEdgeEngine {_esoteric_engine.version} initialized")
    return _esoteric_engine


# =============================================================================
# CONVENIENCE FUNCTION FOR LIVE_DATA_ROUTER
# =============================================================================
def compute_esoteric_edge(
    sport: str = "nba",
    game_total: float = 220,
    spread: float = 0,
    temperature: float = None,
    wind_mph: float = None,
    precipitation_pct: float = None,
    is_dome: bool = True,
) -> Dict[str, Any]:
    """
    Compute Esoteric Edge score - convenience wrapper.

    Returns standardized output:
    {
        "esoteric_edge_score": float,
        "esoteric_active": bool,
        "esoteric_signals_count": int,
        "esoteric_signals": list,
        "esoteric_reasons": list
    }
    """
    engine = get_esoteric_edge_engine()
    return engine.calculate_esoteric_edge(
        sport=sport,
        game_total=game_total,
        spread=spread,
        temperature=temperature,
        wind_mph=wind_mph,
        precipitation_pct=precipitation_pct,
        is_dome=is_dome,
    )


# =============================================================================
# MODULE TEST
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("ESOTERIC EDGE ENGINE v1.0 - NON-JARVIS TEST")
    print("=" * 60)

    engine = get_esoteric_edge_engine()

    # Test for different sports
    test_cases = [
        {"sport": "nba", "game_total": 221, "spread": 5.5},
        {"sport": "nhl", "game_total": 6.5, "spread": 1.5},
        {"sport": "nfl", "game_total": 45, "spread": 3.0, "temperature": 28, "wind_mph": 20, "is_dome": False},
        {"sport": "mlb", "game_total": 8.5, "spread": 1.5, "temperature": 75, "is_dome": False},
    ]

    print("\n" + "=" * 60)
    print("ESOTERIC EDGE BY SPORT:")
    print("=" * 60)

    for tc in test_cases:
        result = engine.calculate_esoteric_edge(**tc)
        print(f"\n{tc['sport'].upper()}: total={tc['game_total']}, spread={tc['spread']}")
        print(f"  esoteric_edge_score: {result['esoteric_edge_score']}")
        print(f"  esoteric_active: {result['esoteric_active']}")
        print(f"  signals: {result['esoteric_signals'][:4]}...")
        print(f"  reasons: {result['esoteric_reasons'][:2]}...")

    # Show current planetary/moon status
    print("\n" + "=" * 60)
    print("CURRENT COSMIC STATUS:")
    print("=" * 60)

    planetary = get_planetary_hour()
    print(f"\nPlanetary Hour: {planetary['hour_ruler']} (Day: {planetary['day_ruler']})")
    print(f"  Favorable for: {planetary['favorable_for']}")

    moon = get_moon_phase()
    print(f"\nMoon Phase: {moon['phase']} (day {moon['phase_day']})")
    print(f"  Favor: {moon['favor']}, Avoid: {moon['avoid']}")

    daily = get_daily_energy()
    print(f"\nDaily Energy: {daily['energy']} (Universal Day {daily['universal_day']})")
    print(f"  Favor: {daily['favor']}")
