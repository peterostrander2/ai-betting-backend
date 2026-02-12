"""
COMPUTE FINAL SCORE - Single Source of Truth for Option A Scoring
==================================================================
Contract Version: 20.1

This is THE ONLY file that computes final_score. All other files must call
these functions. DO NOT duplicate scoring logic elsewhere.

Formula (Option A):
    final_score = clamp(
        base_4
      + context_modifier           (cap: ±0.35)
      + confluence_boost            (cap: 0..10)
      + jason_sim_boost             (cap: ±2.0)
      + ensemble_boost              (cap: 0..1.0)
      + hook_penalty                (cap: -0.5..0)
      + expert_consensus_boost      (cap: 0..0.75)
      + prop_correlation_adjustment (cap: ±0.5)
      + totals_calibration_adj      (cap: ±0.5)
      , 0.0, 10.0
    )

    BASE_4 = ai_score       × 0.25
           + research_score  × 0.35
           + esoteric_score  × 0.15   (v20.19: reduced from 0.20)
           + jarvis_score    × 0.25   (v20.19: increased from 0.20)

CRITICAL RULES:
1. Engine scores are NEVER mutated after base_score is computed.
2. This function is the single source of truth for final_score.
3. Every term in the sum is surfaced in the pick payload.
4. Every term is bounded by caps from scoring_contract.py.
5. SERP and MSRF post-base are DISABLED (forced to 0.0).
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SCORING CONTRACT CONSTANTS (v20.1)
# =============================================================================

ENGINE_WEIGHTS = {
    "ai": 0.25,
    "research": 0.35,
    "esoteric": 0.15,  # v20.19: reduced from 0.20
    "jarvis": 0.25,    # v20.19: increased from 0.20
}

# Validate weights sum to 1.0 on import
_weight_sum = sum(ENGINE_WEIGHTS.values())
assert abs(_weight_sum - 1.0) < 0.001, f"Engine weights must sum to 1.0, got {_weight_sum}"

# Boost caps (v20.1)
CONTEXT_MODIFIER_CAP = 0.35
CONFLUENCE_BOOST_CAP = 10.0  # Theoretical max from cascade
JASON_SIM_BOOST_CAP = 2.0    # Raised from 1.5 in v20.1
ENSEMBLE_BOOST_CAP = 1.0
HOOK_PENALTY_CAP = 0.5       # Max magnitude (actual range: -0.5..0)
EXPERT_CONSENSUS_CAP = 0.75
PROP_CORRELATION_CAP = 0.5   # Max magnitude (actual range: ±0.5)
TOTALS_CALIBRATION_CAP = 0.5 # Max magnitude (actual range: ±0.5)

# DISABLED post-base boosts (v20.1)
MSRF_BOOST_CAP = 0.0         # MSRF now lives INSIDE Jarvis engine
SERP_BOOST_CAP_TOTAL = 0.0   # SERP disabled (no paid API)

# Status flags (v20.1)
MSRF_ENABLED = False         # MSRF moved into Jarvis
SERP_ENABLED = False         # SERP disabled

# Jarvis MSRF component cap (when inside Jarvis)
JARVIS_MSRF_COMPONENT_CAP = 2.0

# Gold Star gates
GOLD_STAR_GATES = {
    "ai_score": 6.5,
    "research_score": 5.5,
    "jarvis_score": 6.0,
    "esoteric_score": 4.0,
}

# Titanium rule
TITANIUM_RULE = {
    "min_engines_ge_threshold": 3,
    "threshold": 8.0,
}

# Confluence levels (for reference)
CONFLUENCE_LEVELS = {
    "IMMORTAL": 10.0,
    "JARVIS_PERFECT": 7.0,
    "PERFECT": 5.0,
    "HARMONIC_CONVERGENCE": 4.5,
    "STRONG": 3.0,
    "MODERATE": 1.0,
    "DIVERGENT": 0.0,
}


# =============================================================================
# BASE SCORE CALCULATION
# =============================================================================

def compute_base_score(
    ai_score: float,
    research_score: float,
    esoteric_score: float,
    jarvis_score: float,
) -> Dict[str, Any]:
    """
    Compute BASE_4 from the four engine scores using frozen weights.

    BASE_4 = ai*0.25 + research*0.35 + esoteric*0.15 + jarvis*0.25

    Args:
        ai_score: AI engine score (0-10)
        research_score: Research engine score (0-10)
        esoteric_score: Esoteric engine score (0-10)
        jarvis_score: Jarvis engine score (0-10)

    Returns:
        Dict with base_score and individual contributions
    """
    ai_contrib = ai_score * ENGINE_WEIGHTS["ai"]
    research_contrib = research_score * ENGINE_WEIGHTS["research"]
    esoteric_contrib = esoteric_score * ENGINE_WEIGHTS["esoteric"]
    jarvis_contrib = jarvis_score * ENGINE_WEIGHTS["jarvis"]

    base_score = ai_contrib + research_contrib + esoteric_contrib + jarvis_contrib

    return {
        "base_score": round(base_score, 4),
        "contributions": {
            "ai": round(ai_contrib, 4),
            "research": round(research_contrib, 4),
            "esoteric": round(esoteric_contrib, 4),
            "jarvis": round(jarvis_contrib, 4),
        },
        "weights": ENGINE_WEIGHTS.copy(),
        "engine_scores": {
            "ai": ai_score,
            "research": research_score,
            "esoteric": esoteric_score,
            "jarvis": jarvis_score,
        },
    }


# =============================================================================
# FINAL SCORE CALCULATION (Option A)
# =============================================================================

def compute_final_score_option_a(
    ai_score: float,
    research_score: float,
    esoteric_score: float,
    jarvis_score: float,
    context_modifier: float = 0.0,
    confluence_boost: float = 0.0,
    jason_sim_boost: float = 0.0,
    ensemble_boost: float = 0.0,
    hook_penalty: float = 0.0,
    expert_consensus_boost: float = 0.0,
    prop_correlation_adjustment: float = 0.0,
    totals_calibration_adj: float = 0.0,
    # DISABLED boosts - forced to 0.0 regardless of input
    msrf_boost: float = 0.0,
    serp_boost: float = 0.0,
    # Jason audit fields
    jason_status: str = "NEUTRAL",
    jason_reasons: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Compute final score using Option A formula.

    This is THE SINGLE SOURCE OF TRUTH for final_score calculation.
    All picks MUST use this function.

    Args:
        ai_score: AI engine score (0-10)
        research_score: Research engine score (0-10)
        esoteric_score: Esoteric engine score (0-10)
        jarvis_score: Jarvis engine score (0-10)
        context_modifier: Context modifier (capped ±0.35)
        confluence_boost: Confluence boost (capped 0..10)
        jason_sim_boost: Jason Sim boost (capped ±2.0)
        ensemble_boost: Ensemble boost (capped 0..1.0)
        hook_penalty: Hook penalty (capped -0.5..0)
        expert_consensus_boost: Expert consensus boost (capped 0..0.75)
        prop_correlation_adjustment: Prop correlation adjustment (capped ±0.5)
        totals_calibration_adj: Totals calibration adjustment (capped ±0.5)
        msrf_boost: DISABLED - always forced to 0.0
        serp_boost: DISABLED - always forced to 0.0
        jason_status: Jason status string
        jason_reasons: Jason reason strings

    Returns:
        Dict with final_score, all terms, reconciliation check, tier info
    """
    # Compute base score
    base_detail = compute_base_score(ai_score, research_score, esoteric_score, jarvis_score)
    base_score = base_detail["base_score"]

    # Apply caps to all boost terms
    context_modifier = max(-CONTEXT_MODIFIER_CAP, min(CONTEXT_MODIFIER_CAP, context_modifier))
    confluence_boost = max(0.0, min(CONFLUENCE_BOOST_CAP, confluence_boost))
    jason_sim_boost = max(-JASON_SIM_BOOST_CAP, min(JASON_SIM_BOOST_CAP, jason_sim_boost))
    ensemble_boost = max(0.0, min(ENSEMBLE_BOOST_CAP, ensemble_boost))
    hook_penalty = max(-HOOK_PENALTY_CAP, min(0.0, hook_penalty))  # Must be <=0
    expert_consensus_boost = max(0.0, min(EXPERT_CONSENSUS_CAP, expert_consensus_boost))
    prop_correlation_adjustment = max(-PROP_CORRELATION_CAP, min(PROP_CORRELATION_CAP, prop_correlation_adjustment))
    totals_calibration_adj = max(-TOTALS_CALIBRATION_CAP, min(TOTALS_CALIBRATION_CAP, totals_calibration_adj))

    # DISABLED boosts - FORCE to 0.0 regardless of input
    msrf_boost = 0.0  # MSRF is now inside Jarvis engine
    serp_boost = 0.0  # SERP is disabled

    # Build terms dict for reconciliation
    terms = {
        "base_score": base_score,
        "context_modifier": round(context_modifier, 4),
        "confluence_boost": round(confluence_boost, 4),
        "jason_sim_boost": round(jason_sim_boost, 4),
        "ensemble_boost": round(ensemble_boost, 4),
        "hook_penalty": round(hook_penalty, 4),
        "expert_consensus_boost": round(expert_consensus_boost, 4),
        "prop_correlation_adjustment": round(prop_correlation_adjustment, 4),
        "totals_calibration_adj": round(totals_calibration_adj, 4),
        "msrf_boost": 0.0,  # Always 0.0
        "serp_boost": 0.0,  # Always 0.0
    }

    # Calculate raw sum (before clamp)
    raw_sum = (
        base_score
        + context_modifier
        + confluence_boost
        + jason_sim_boost
        + ensemble_boost
        + hook_penalty
        + expert_consensus_boost
        + prop_correlation_adjustment
        + totals_calibration_adj
        # msrf_boost and serp_boost are 0.0
    )

    # Clamp final score to [0, 10]
    final_score = max(0.0, min(10.0, raw_sum))

    # Reconciliation check
    recomputed_sum = sum(terms.values())
    reconciliation_delta = abs(final_score - max(0.0, min(10.0, recomputed_sum)))
    reconciliation_pass = reconciliation_delta <= 0.02

    # Determine tier
    tier, tier_detail = _determine_tier(
        ai_score, research_score, esoteric_score, jarvis_score,
        final_score
    )

    return {
        "final_score": round(final_score, 2),
        "raw_sum": round(raw_sum, 4),
        "terms": terms,
        "base_score_detail": base_detail,
        "tier": tier,
        "tier_detail": tier_detail,
        "reconciliation_pass": reconciliation_pass,
        "reconciliation_delta": round(reconciliation_delta, 4),
        # Status fields
        "msrf_status": "IN_JARVIS",  # MSRF component is now inside Jarvis
        "serp_status": "DISABLED",   # SERP is disabled
        # Jason fields
        "jason_status": jason_status,
        "jason_reasons": jason_reasons or [],
    }


# =============================================================================
# TIER DETERMINATION
# =============================================================================

def _determine_tier(
    ai_score: float,
    research_score: float,
    esoteric_score: float,
    jarvis_score: float,
    final_score: float,
) -> tuple:
    """
    Determine tier based on engine scores and final score.

    Tiers (in priority order):
    1. TITANIUM: 3+ engines >= 8.0
    2. GOLD_STAR: final >= 7.5 AND passes all gates
    3. EDGE_LEAN: final >= 6.5
    4. NO_PICK: final < 6.5

    Returns:
        Tuple of (tier_name, tier_detail_dict)
    """
    # Count engines >= 8.0 for Titanium
    scores = {
        "ai_score": ai_score,
        "research_score": research_score,
        "esoteric_score": esoteric_score,
        "jarvis_score": jarvis_score,
    }

    engines_ge_8 = [name for name, score in scores.items() if score >= TITANIUM_RULE["threshold"]]
    titanium_triggered = len(engines_ge_8) >= TITANIUM_RULE["min_engines_ge_threshold"]

    # Check Gold Star gates
    failed_gates = []
    for gate_name, threshold in GOLD_STAR_GATES.items():
        if scores[gate_name] < threshold:
            failed_gates.append(gate_name)

    gold_star_eligible = len(failed_gates) == 0 and final_score >= 7.5

    # Determine tier
    if titanium_triggered:
        tier = "TITANIUM"
    elif gold_star_eligible:
        tier = "GOLD_STAR"
    elif final_score >= 6.5:
        tier = "EDGE_LEAN"
    else:
        tier = "NO_PICK"

    tier_detail = {
        "titanium_triggered": titanium_triggered,
        "titanium_count": len(engines_ge_8),
        "titanium_engines": engines_ge_8,
        "gold_star_eligible": gold_star_eligible,
        "failed_gates": failed_gates,
        "gates_checked": list(GOLD_STAR_GATES.keys()),
    }

    return tier, tier_detail


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Constants
    "ENGINE_WEIGHTS",
    "CONTEXT_MODIFIER_CAP",
    "CONFLUENCE_BOOST_CAP",
    "JASON_SIM_BOOST_CAP",
    "ENSEMBLE_BOOST_CAP",
    "HOOK_PENALTY_CAP",
    "EXPERT_CONSENSUS_CAP",
    "PROP_CORRELATION_CAP",
    "TOTALS_CALIBRATION_CAP",
    "MSRF_BOOST_CAP",
    "SERP_BOOST_CAP_TOTAL",
    "MSRF_ENABLED",
    "SERP_ENABLED",
    "JARVIS_MSRF_COMPONENT_CAP",
    "GOLD_STAR_GATES",
    "TITANIUM_RULE",
    "CONFLUENCE_LEVELS",
    # Functions
    "compute_base_score",
    "compute_final_score_option_a",
]
