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
# v20.12: Raised from 6.5 to 7.0 to reduce pick volume and increase quality
MIN_FINAL_SCORE = 7.0

# Tier thresholds
GOLD_STAR_THRESHOLD = 7.5

# Titanium Rule (hard invariant)
TITANIUM_RULE = {
    "min_engines_ge_threshold": 3,
    "threshold": 8.0,
}

# Gold Star hard gates (hard invariant)
# v20.12: Raised research (5.5→6.5) and esoteric (4.0→5.5) to reduce pick volume
GOLD_STAR_GATES = {
    "ai_score": 6.8,
    "research_score": 6.5,
    "jarvis_score": 6.5,
    "esoteric_score": 5.5,
}

# v20.12: Quality gates for reduced pick volume
# Base score gates (pre-boost quality check)
BASE_SCORE_GATES = {
    "edge_lean_min": 6.0,      # Minimum base_score for EDGE_LEAN (prevents boost-inflated weak picks)
    "gold_star_min": 6.8,      # Minimum base_score for GOLD_STAR (ensures strong foundation)
}

# Engine alignment gate (prevents 1 great + 3 terrible engine picks)
ENGINE_ALIGNMENT_GATE = {
    "min_engines_above_threshold": 2,  # At least 2 of 4 engines must be >= threshold
    "threshold": 6.5,                   # Engine minimum for alignment check
}

# Confluence minimum for EDGE_LEAN tier
EDGE_LEAN_CONFLUENCE_MINIMUM = "MODERATE"  # Must be at least MODERATE (not DIVERGENT)

# Confluence boost levels (must match production implementation)
# v17.0: Added HARMONIC_CONVERGENCE for Math+Magic alignment
# v17.3: Lowered HARMONIC_CONVERGENCE threshold from 8.0 to 7.5 for more triggers
# v20.10: Rescaled proportionally to work with TOTAL_BOOST_CAP=2.0
# v20.11: Further lowered to prevent score saturation (all picks at 10.0)
#         With lower confluence, SERP's +0.5-1.0 now creates visible differentiation
#         Picks spread across 7.5-9.5 instead of clustering at 10.0
CONFLUENCE_LEVELS = {
    "IMMORTAL": 1.5,
    "JARVIS_PERFECT": 1.5,
    "PERFECT": 1.5,
    "HARMONIC_CONVERGENCE": 1.5,  # Research + Esoteric both >= threshold
    "STRONG": 1.0,
    "MODERATE": 0.3,
    "DIVERGENT": 0.0,
}

# v17.3: Harmonic Convergence threshold (lowered from 8.0 for better trigger rate)
# v20.11: Lowered HARMONIC_BOOST to match CONFLUENCE_LEVELS recalibration
HARMONIC_CONVERGENCE_THRESHOLD = 7.5
HARMONIC_BOOST = 1.0

# Post-base boost caps (documented, bounded)
# Note: These are caps for the individual boost components (not engines).
CONFLUENCE_BOOST_CAP = max(CONFLUENCE_LEVELS.values())
MSRF_BOOST_CAP = 1.0  # MSRF boosts are 0.0, 0.25, 0.5, 1.0
SERP_BOOST_CAP_TOTAL = 4.3  # Must match core/serp_guardrails.py SERP_TOTAL_CAP
JASON_SIM_BOOST_CAP = 1.5  # Max absolute Jason boost/downgrade
# Total boost cap (sum of confluence + msrf + jason_sim + serp, excluding context modifier)
# Prevents score inflation from stacking multiple boosts on a mediocre base score.
# v20.11: Lowered from 2.0 to 1.5 to prevent score saturation at 10.0
#         This leaves headroom for SERP boosts to create visible differentiation
TOTAL_BOOST_CAP = 1.5
# Ensemble adjustment step (post-base)
ENSEMBLE_ADJUSTMENT_STEP = 0.5

# v20.4: Totals Side Calibration (OVER/UNDER bias correction)
# Based on learning loop data: OVER 19.1% vs UNDER 81.6% hit rate
# Applies score adjustment to correct observed bias toward OVER picks
# v20.11: DISABLED - Feb 5 data shows OVER 55% vs UNDER 44%, opposite of original data
TOTALS_SIDE_CALIBRATION = {
    "enabled": False,  # Disabled - data shows reverse bias now
    "over_penalty": -0.75,   # Penalty applied to OVER picks
    "under_boost": 0.75,     # Boost applied to UNDER picks
    "min_samples_required": 50,  # Min samples before calibration kicks in
    "last_updated": "2026-02-05",
}

# v20.11: Sport-Specific Totals Calibration
# Based on Feb 5, 2026 grading data:
# - NHL Totals: 6-17 (26% win rate) - CATASTROPHIC, model picks Under but games go Over
# - NBA Totals: 52% win rate - acceptable
# - NCAAB Totals: 46% win rate - slightly below breakeven
# Penalty is applied to ALL totals for that sport (before MIN_FINAL_SCORE filter)
# A 10.0 score with -4.0 penalty = 6.0, which is below MIN_FINAL_SCORE (6.5)
SPORT_TOTALS_CALIBRATION = {
    "enabled": True,
    "NHL": -4.0,    # BLOCK - 26% win rate is unacceptable, 10.0 → 6.0 (won't surface)
    "NCAAB": -0.75, # Moderate penalty - 46% win rate, 10.0 → 9.25
    "NBA": 0.0,     # No penalty - 52% win rate is acceptable
    "NFL": 0.0,     # No data yet
    "MLB": 0.0,     # No data yet
    "last_updated": "2026-02-05",
}

# v20.12: Pick concentration limits (quality over quantity)
# Prevents overexposure to single games/sports
CONCENTRATION_LIMITS = {
    "max_per_matchup": 2,         # Max picks per game (e.g., 2 picks for Lakers vs Celtics)
    "max_per_sport_per_day": 8,   # Max total picks per sport per day
    "max_props_per_player": 1,    # Max prop picks per individual player
}

# v20.12: Tier filter for persistence (quality over quantity)
# Only these tiers are worth persisting to the learning loop
# MONITOR and PASS tiers don't provide value for weight learning
PERSIST_TIERS = {"EDGE_LEAN", "GOLD_STAR", "TITANIUM_SMASH"}

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
        "total_boost_cap": TOTAL_BOOST_CAP,
    },
    "totals_side_calibration": TOTALS_SIDE_CALIBRATION,  # v20.4 (disabled v20.11)
    "sport_totals_calibration": SPORT_TOTALS_CALIBRATION,  # v20.11
    # v20.12: Quality gates for reduced pick volume
    "base_score_gates": BASE_SCORE_GATES,
    "engine_alignment_gate": ENGINE_ALIGNMENT_GATE,
    "edge_lean_confluence_minimum": EDGE_LEAN_CONFLUENCE_MINIMUM,
    "concentration_limits": CONCENTRATION_LIMITS,
    "persist_tiers": PERSIST_TIERS,  # v20.12: Only quality tiers saved to learning loop
}
