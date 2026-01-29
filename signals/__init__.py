"""
SIGNALS MODULE - Centralized Signal Calculations
=================================================
v15.0 - Single-calculation policy for signals

This module provides centralized signal calculations to prevent
double-counting across engines.

Modules:
- public_fade: Public betting fade signal (Research Engine owns boost)
- physics: Gann, Fibonacci, Schumann, Barometric, Hurst, Kp-Index signals
- hive_mind: Noosphere, Void Moon, Linguistic Divergence, Founder's Echo
- market: RLM, Teammate Void, Correlation Matrix, Steam Move
- math_glitch: Benford Anomaly, Golden Ratio, Prime Resonance, Numerical Symmetry

ALL SIGNAL MODULES RETURN:
- score: float (0-1 normalized)
- reason: str (explicit explanation or "NO_SIGNAL" reason)
- triggered: bool
"""

# Public Fade (Research Engine)
from .public_fade import (
    calculate_public_fade,
    get_public_fade_context,
    PublicFadeSignal,
)

# Physics Signals (Esoteric Engine)
from .physics import (
    calculate_gann_square,
    calculate_fib_retracement,
    get_schumann_resonance,
    get_barometric_drag,
    calculate_hurst_exponent,
    get_kp_index,
    get_physics_score,
    PHYSICS_ENABLED,
)

# Hive Mind Signals (Esoteric Engine)
from .hive_mind import (
    get_noosphere_velocity,
    get_void_moon,
    analyze_linguistic_divergence,
    get_founders_echo,
    get_hive_mind_score,
    HIVE_MIND_ENABLED,
)

# Market Signals (Research Engine)
from .market import (
    detect_rlm,
    check_teammate_void,
    get_prop_correlation,
    detect_steam_move,
    get_market_score,
    PROP_CORRELATIONS,
    MARKET_SIGNALS_ENABLED,
)

# Math Glitch Signals (Esoteric Engine)
from .math_glitch import (
    check_benford_anomaly,
    check_golden_ratio,
    check_prime_resonance,
    check_numerical_symmetry,
    get_math_glitch_score,
    PHI,
    PRIMES_TO_100,
    MATH_GLITCH_ENABLED,
)

__all__ = [
    # Public Fade
    "calculate_public_fade",
    "get_public_fade_context",
    "PublicFadeSignal",

    # Physics
    "calculate_gann_square",
    "calculate_fib_retracement",
    "get_schumann_resonance",
    "get_barometric_drag",
    "calculate_hurst_exponent",
    "get_kp_index",
    "get_physics_score",
    "PHYSICS_ENABLED",

    # Hive Mind
    "get_noosphere_velocity",
    "get_void_moon",
    "analyze_linguistic_divergence",
    "get_founders_echo",
    "get_hive_mind_score",
    "HIVE_MIND_ENABLED",

    # Market
    "detect_rlm",
    "check_teammate_void",
    "get_prop_correlation",
    "detect_steam_move",
    "get_market_score",
    "PROP_CORRELATIONS",
    "MARKET_SIGNALS_ENABLED",

    # Math Glitch
    "check_benford_anomaly",
    "check_golden_ratio",
    "check_prime_resonance",
    "check_numerical_symmetry",
    "get_math_glitch_score",
    "PHI",
    "PRIMES_TO_100",
    "MATH_GLITCH_ENABLED",
]
