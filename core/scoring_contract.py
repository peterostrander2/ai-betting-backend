"""
Scoring Contract - Single Source of Truth
All scoring logic MUST reference these constants (no duplicated literals).
"""

# Engine Weights (sum = 0.90; remaining headroom is reserved for post-base modifiers
# such as confluence + Jason Sim + bounded context modifiers, as implemented).
# v17.1: Added Context engine at 30% per spec, rebalanced others proportionally
ENGINE_WEIGHTS = {
    "ai": 0.15,        # was 0.25 - 8 AI models
    "research": 0.20,  # was 0.30 - Sharp money, splits, variance
    "esoteric": 0.15,  # was 0.20 - Numerology, astro, fib, vortex
    "jarvis": 0.10,    # was 0.15 - Gematria, sacred triggers
    "context": 0.30,   # NEW - Pillars 13-15: Defensive Rank, Pace, Vacuum
}

# Output/visibility threshold (hard invariant)
MIN_FINAL_SCORE = 6.5

# Tier thresholds
GOLD_STAR_THRESHOLD = 7.5

# Titanium Rule (hard invariant)
TITANIUM_RULE = {
    "min_engines_ge_threshold": 3,
    "threshold": 8.0,
}

# Gold Star hard gates (hard invariant)
# v17.1: Added context_score gate for 5-engine architecture
GOLD_STAR_GATES = {
    "ai_score": 6.8,
    "research_score": 5.5,
    "jarvis_score": 6.5,
    "esoteric_score": 4.0,
    "context_score": 4.0,  # NEW - Pillars 13-15 must contribute
}

# Confluence boost levels (must match production implementation)
# v17.0: Added HARMONIC_CONVERGENCE for Math+Magic alignment
# v17.3: Lowered HARMONIC_CONVERGENCE threshold from 8.0 to 7.5 for more triggers
CONFLUENCE_LEVELS = {
    "IMMORTAL": 10.0,
    "JARVIS_PERFECT": 7.0,
    "PERFECT": 5.0,
    "HARMONIC_CONVERGENCE": 4.5,  # Research + Esoteric both >= threshold
    "STRONG": 3.0,
    "MODERATE": 1.0,
    "DIVERGENT": 0.0,
}

# v17.3: Harmonic Convergence threshold (lowered from 8.0 for better trigger rate)
HARMONIC_CONVERGENCE_THRESHOLD = 7.5

# Status enums used in outputs (must be deterministic)
WEATHER_STATUS = ["APPLIED", "NOT_RELEVANT", "UNAVAILABLE", "ERROR"]

# Canonical contract object for validation
SCORING_CONTRACT = {
    "engine_weights": ENGINE_WEIGHTS,
    "min_final_score": MIN_FINAL_SCORE,
    "gold_star_threshold": GOLD_STAR_THRESHOLD,
    "titanium_rule": TITANIUM_RULE,
    "gold_star_gates": GOLD_STAR_GATES,
    "confluence_levels": CONFLUENCE_LEVELS,
    "weather_status_enum": WEATHER_STATUS,
    "harmonic_convergence_threshold": HARMONIC_CONVERGENCE_THRESHOLD,  # v17.3
}
