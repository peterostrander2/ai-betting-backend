"""
Scoring Contract - Single Source of Truth
All scoring logic MUST reference these constants (no duplicated literals).
"""

# Engine Weights (sum = 1.00; post-base modifiers remain additive
# such as confluence + Jason Sim + bounded context modifiers, as implemented).
# v18.0: Option A — 4-engine base weights. Context is a bounded modifier layer.
ENGINE_WEIGHTS = {
    "ai": 0.25,        # 8 AI models
    "research": 0.35,  # Sharp money, splits, variance
    "esoteric": 0.20,  # Numerology, astro, fib, vortex
    "jarvis": 0.20,    # Gematria, sacred triggers
}

# Context modifier cap (applied as bounded boost, NOT a weighted engine)
CONTEXT_MODIFIER_CAP = 0.35


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
HARMONIC_BOOST = 1.5

# Post-base boost caps (documented, bounded)
# Note: These are caps for the individual boost components (not engines).
CONFLUENCE_BOOST_CAP = max(CONFLUENCE_LEVELS.values())
MSRF_BOOST_CAP = 1.0  # MSRF boosts are 0.0, 0.25, 0.5, 1.0
SERP_BOOST_CAP_TOTAL = 4.3  # Must match core/serp_guardrails.py SERP_TOTAL_CAP
JASON_SIM_BOOST_CAP = 1.5  # Max absolute Jason boost/downgrade
# Ensemble adjustment step (post-base)
ENSEMBLE_ADJUSTMENT_STEP = 0.5

# v20.4: Totals Side Calibration (OVER/UNDER bias correction)
# Based on learning loop data: OVER 19.1% vs UNDER 81.6% hit rate
# Applies score adjustment to correct observed bias toward OVER picks
TOTALS_SIDE_CALIBRATION = {
    "enabled": True,
    "over_penalty": -0.75,   # Penalty applied to OVER picks
    "under_boost": 0.75,     # Boost applied to UNDER picks
    "min_samples_required": 50,  # Min samples before calibration kicks in
    "last_updated": "2026-02-04",
}

# Odds staleness threshold for live betting endpoints (seconds)
# If odds data is older than this, live picks are marked STALE and live_adjustment is suppressed
ODDS_STALENESS_THRESHOLD_SECONDS = 120

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
    "harmonic_boost": HARMONIC_BOOST,
    "boost_caps": {
        "confluence_boost_cap": CONFLUENCE_BOOST_CAP,
        "msrf_boost_cap": MSRF_BOOST_CAP,
        "serp_boost_cap_total": SERP_BOOST_CAP_TOTAL,
        "jason_sim_boost_cap": JASON_SIM_BOOST_CAP,
    },
}
