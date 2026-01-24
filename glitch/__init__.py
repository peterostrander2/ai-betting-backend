"""
Glitch Protocol v1.0
====================
Modular esoteric/physics/hive-mind/market signal detection system.

Master Audit File Implementation:
- esoteric.py: Chrome Resonance, Bio-Sine Wave, Life Path Sync, Founder's Echo, Chaldean Clock
- physics.py: Gann Square, 50% Retracement, Schumann, Atmospheric Drag, Hurst, Kp-Index
- hive_mind.py: Noosphere Velocity, Void Moon Filter, Hate-Buy Trap, Crowd Wisdom
- market.py: RLM, Teammate Void, Correlation Matrix, Benford Anomaly, Steam Move
- math_glitch.py: JARVIS Triggers, Titanium Rule, Harmonic Convergence

TITANIUM RULE: If 3 of 4 modules fire signals, the pick is a "Titanium Smash".

Usage:
    from glitch import get_glitch_analysis

    result = get_glitch_analysis(
        home_team="Lakers",
        away_team="Celtics",
        spread=-3.5,
        total=220.5,
        public_pct=65,
        ...
    )
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

# Import all module functions
from .esoteric import (
    get_chrome_resonance,
    calculate_biorhythms,
    check_life_path_sync,
    check_founders_echo,
    check_chaldean_clock,
    get_esoteric_signals,
    TEAM_PRIMARY_COLORS,
    TEAM_FOUNDING_YEARS,
)

from .physics import (
    calculate_gann_square,
    analyze_spread_total_gann,
    calculate_fib_retracement,
    check_50_retracement,
    get_schumann_frequency,
    calculate_atmospheric_drag,
    calculate_elevation_drag,
    calculate_hurst_exponent,
    get_kp_index,
    get_physics_signals,
)

from .hive_mind import (
    calculate_noosphere_velocity,
    calculate_void_moon,
    get_moon_betting_signal,
    detect_hate_buy_trap,
    calculate_linguistic_divergence,
    calculate_crowd_wisdom,
    get_hive_mind_signals,
)

from .market import (
    check_benford_anomaly,
    detect_rlm,
    check_teammate_void,
    analyze_sgp_correlation,
    detect_steam_move,
    get_market_signals,
    BENFORD_EXPECTED,
    PROP_CORRELATIONS,
)

from .math_glitch import (
    check_jarvis_trigger,
    check_power_number,
    check_tesla_sequence,
    calculate_simple_gematria,
    calculate_reverse_gematria,
    full_gematria_analysis,
    check_titanium_rule,
    check_harmonic_convergence,
    calculate_glitch_score,
    JARVIS_TRIGGERS,
    POWER_NUMBERS,
    TESLA_NUMBERS,
)

__version__ = "1.0.0"
__all__ = [
    # Esoteric
    "get_chrome_resonance",
    "calculate_biorhythms",
    "check_life_path_sync",
    "check_founders_echo",
    "check_chaldean_clock",
    "get_esoteric_signals",
    "TEAM_PRIMARY_COLORS",
    "TEAM_FOUNDING_YEARS",
    # Physics
    "calculate_gann_square",
    "analyze_spread_total_gann",
    "calculate_fib_retracement",
    "check_50_retracement",
    "get_schumann_frequency",
    "calculate_atmospheric_drag",
    "calculate_elevation_drag",
    "calculate_hurst_exponent",
    "get_kp_index",
    "get_physics_signals",
    # Hive Mind
    "calculate_noosphere_velocity",
    "calculate_void_moon",
    "get_moon_betting_signal",
    "detect_hate_buy_trap",
    "calculate_linguistic_divergence",
    "calculate_crowd_wisdom",
    "get_hive_mind_signals",
    # Market
    "check_benford_anomaly",
    "detect_rlm",
    "check_teammate_void",
    "analyze_sgp_correlation",
    "detect_steam_move",
    "get_market_signals",
    "BENFORD_EXPECTED",
    "PROP_CORRELATIONS",
    # Math Glitch
    "check_jarvis_trigger",
    "check_power_number",
    "check_tesla_sequence",
    "calculate_simple_gematria",
    "calculate_reverse_gematria",
    "full_gematria_analysis",
    "check_titanium_rule",
    "check_harmonic_convergence",
    "calculate_glitch_score",
    "JARVIS_TRIGGERS",
    "POWER_NUMBERS",
    "TESLA_NUMBERS",
    # Main function
    "get_glitch_analysis",
]


def get_glitch_analysis(
    home_team: str,
    away_team: str,
    spread: float = None,
    total: float = None,
    opening_line: float = None,
    current_line: float = None,
    public_pct: float = None,
    money_pct: float = None,
    pressure_in: float = None,
    city: str = None,
    recent_stats: List[float] = None,
    sentiment_score: float = None,
    rlm_detected: bool = False,
    rlm_direction: str = None,
    parlay_legs: List[Dict[str, Any]] = None,
    ai_score: float = None,
    esoteric_score: float = None,
    game_time: datetime = None,
    player_birth_dates: Dict[str, str] = None
) -> Dict[str, Any]:
    """
    Main entry point for Glitch Protocol analysis.

    Runs all 4 modules and calculates combined Glitch Score with Titanium Rule.

    Args:
        home_team: Home team name
        away_team: Away team name
        spread: Point spread (negative = home favorite)
        total: Over/under total
        opening_line: Opening spread
        current_line: Current spread
        public_pct: Public betting percentage
        money_pct: Money percentage
        pressure_in: Barometric pressure (inHg)
        city: Venue city
        recent_stats: Recent statistical values for Benford/Hurst
        sentiment_score: Sentiment score (-1 to 1)
        rlm_detected: Whether RLM was detected
        rlm_direction: Direction of RLM ("HOME" or "AWAY")
        parlay_legs: Parlay leg data for correlation analysis
        ai_score: AI model score (for Harmonic Convergence)
        esoteric_score: Esoteric score (for Harmonic Convergence)
        game_time: Game start time (for Chaldean Clock)
        player_birth_dates: Dict of player -> birth date (for biorhythms)

    Returns:
        Complete Glitch Protocol analysis with all signals and combined score
    """
    # Run all 4 modules
    esoteric_result = get_esoteric_signals(
        home_team=home_team,
        away_team=away_team,
        game_time=game_time,
        player_birth_dates=player_birth_dates
    )

    physics_result = get_physics_signals(
        spread=spread,
        total=total,
        pressure_in=pressure_in,
        city=city,
        recent_scores=recent_stats
    )

    hive_mind_result = get_hive_mind_signals(
        public_pct=public_pct,
        money_pct=money_pct,
        sentiment_score=sentiment_score,
        rlm_detected=rlm_detected,
        rlm_direction=rlm_direction,
        sentiment_target="HOME" if sentiment_score and sentiment_score < 0 else "AWAY"
    )

    market_result = get_market_signals(
        opening_line=opening_line,
        current_line=current_line,
        public_pct=public_pct,
        recent_stats=recent_stats,
        parlay_legs=parlay_legs
    )

    # Calculate combined Glitch Score
    glitch_score = calculate_glitch_score(
        esoteric_result=esoteric_result,
        physics_result=physics_result,
        hive_mind_result=hive_mind_result,
        market_result=market_result,
        ai_score=ai_score,
        esoteric_score=esoteric_score
    )

    return {
        "version": __version__,
        "matchup": f"{away_team} @ {home_team}",
        "modules": {
            "esoteric": esoteric_result,
            "physics": physics_result,
            "hive_mind": hive_mind_result,
            "market": market_result
        },
        "glitch_score": glitch_score["glitch_score"],
        "tier": glitch_score["tier"],
        "titanium_smash": glitch_score["titanium"]["titanium_smash"],
        "titanium_count": glitch_score["titanium"]["titanium_count"],
        "harmonic_convergence": glitch_score["harmonic"].get("harmonic_convergence", False),
        "total_modules_fired": glitch_score["total_modules_fired"],
        "breakdown": glitch_score["breakdown"],
        "recommendations": _generate_recommendations(glitch_score)
    }


def _generate_recommendations(glitch_score: Dict[str, Any]) -> List[str]:
    """Generate betting recommendations based on Glitch Score."""
    recommendations = []

    tier = glitch_score["tier"]

    if tier == "PERFECT_TITANIUM":
        recommendations.append("PERFECT TITANIUM - All 4 modules aligned. Maximum confidence play.")
        recommendations.append("Consider 2-3 unit position.")
    elif tier == "TITANIUM_SMASH":
        recommendations.append("TITANIUM SMASH - 3/4 modules aligned. High confidence play.")
        recommendations.append("Consider 1.5-2 unit position.")
    elif tier == "GOLDEN_HARMONIC":
        recommendations.append("GOLDEN HARMONIC - Math and Magic aligned. Strong edge detected.")
        recommendations.append("Consider 1-1.5 unit position.")
    elif tier == "STRONG_GLITCH":
        recommendations.append("STRONG GLITCH signal detected. Standard 1 unit play.")
    elif tier == "MODERATE_GLITCH":
        recommendations.append("MODERATE GLITCH signal. Consider 0.5 unit lean.")
    elif tier == "WEAK_GLITCH":
        recommendations.append("WEAK GLITCH signal. Monitor only - no strong edge.")
    else:
        recommendations.append("NO GLITCH signals. Pass on this matchup.")

    return recommendations
