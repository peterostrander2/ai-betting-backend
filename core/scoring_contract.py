"""
Scoring Contract - Single Source of Truth
All scoring logic MUST reference these constants (no duplicated literals).
"""

# Engine Weights (sum = 0.90; remaining headroom is reserved for post-base modifiers
# such as confluence + Jason Sim + bounded context modifiers, as implemented).
ENGINE_WEIGHTS = {
    "ai": 0.25,
    "research": 0.30,
    "esoteric": 0.20,
    "jarvis": 0.15,
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
GOLD_STAR_GATES = {
    "ai_score": 6.8,
    "research_score": 5.5,
    "jarvis_score": 6.5,
    "esoteric_score": 4.0,
}

# Confluence boost levels (must match production implementation)
CONFLUENCE_LEVELS = {
    "IMMORTAL": 10.0,
    "JARVIS_PERFECT": 7.0,
    "PERFECT": 5.0,
    "STRONG": 3.0,
    "MODERATE": 1.0,
    "DIVERGENT": 0.0,
}

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
}
