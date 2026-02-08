"""
SCORING PIPELINE - Single Source of Truth for Pick Scoring

This module provides ONE function to score candidates:
    score_candidate(candidate, context) -> Dict

NEVER duplicate scoring logic. All scoring MUST go through this pipeline.

v18.0 Option A (4-Engine Base + Context Modifier):
    ENGINE 1: AI Score (25%) - 8 AI Models
    ENGINE 2: Research Score (35%) - Sharp money, line variance, public fade
    ENGINE 3: Esoteric Score (20%) - Numerology, astro, fib, vortex, daily
    ENGINE 4: Jarvis Score (20%) - Gematria, triggers, mid-spread

    CONTEXT_MOD (bounded): optional modifier in [-0.35, +0.35]

    POST-BASE BOOSTS (all capped, combined via TOTAL_BOOST_CAP):
    - confluence_boost, msrf_boost, jason_sim_boost, serp_boost
    - ensemble_adjustment, totals_calibration_adj

    v20.3 POST-BASE SIGNALS (8 Pillars of Execution):
    - hook_penalty: <=0, max magnitude -0.25 (NFL/NBA spread key numbers)
    - expert_consensus_boost: >=0, max 0.35 (aggregated expert agreement)
    - prop_correlation_adjustment: signed, max magnitude 0.20 (player prop correlations)

    FINAL = clamp(0..10, BASE_4 + CONTEXT_MOD + boosts + hook_penalty + expert_boost + prop_corr)

    CRITICAL: No signal may mutate engine scores. Post-base additive fields ONLY.
"""

from typing import Dict, Any, Optional, Tuple
import logging

# Import invariants for engine weights
try:
    from core.invariants import (
        ENGINE_WEIGHT_AI,
        ENGINE_WEIGHT_RESEARCH,
        ENGINE_WEIGHT_ESOTERIC,
        ENGINE_WEIGHT_JARVIS,
        COMMUNITY_MIN_SCORE,
        JARVIS_BASELINE_FLOOR,
        validate_score_threshold,
    )
    INVARIANTS_AVAILABLE = True
except ImportError:
    INVARIANTS_AVAILABLE = False
    ENGINE_WEIGHT_AI = 0.25
    ENGINE_WEIGHT_RESEARCH = 0.35
    ENGINE_WEIGHT_ESOTERIC = 0.20
    ENGINE_WEIGHT_JARVIS = 0.20
    COMMUNITY_MIN_SCORE = 6.5
    JARVIS_BASELINE_FLOOR = 4.5

logger = logging.getLogger(__name__)

# =============================================================================
# OPTION A HELPERS (SINGLE SOURCE OF FINAL SCORE MATH)
# =============================================================================

def clamp_context_modifier(value: float, cap: Optional[float] = None) -> float:
    """Clamp context modifier to ±CONTEXT_MODIFIER_CAP."""
    if cap is None:
        try:
            from core.scoring_contract import CONTEXT_MODIFIER_CAP
            cap = CONTEXT_MODIFIER_CAP
        except Exception:
            cap = 0.35
    return max(-cap, min(cap, value))


def compute_final_score_option_a(
    base_score: float,
    context_modifier: float,
    confluence_boost: float,
    msrf_boost: float,
    jason_sim_boost: float,
    serp_boost: float,
    cap: Optional[float] = None,
    ensemble_adjustment: float = 0.0,
    totals_calibration_adj: float = 0.0,
    # v20.3 Post-base signals (8 Pillars of Execution)
    hook_penalty: float = 0.0,
    expert_consensus_boost: float = 0.0,
    prop_correlation_adjustment: float = 0.0,
) -> Tuple[float, float]:
    """
    Option A final score formula:
    FINAL = clamp(0..10, BASE_4 + CONTEXT_MOD + capped_boosts + hook + expert + prop_corr)

    v20.3: Added explicit post-base signal parameters:
    - hook_penalty: <=0, max magnitude -HOOK_PENALTY_CAP (NFL/NBA key numbers)
    - expert_consensus_boost: >=0, max EXPERT_CONSENSUS_CAP (expert agreement)
    - prop_correlation_adjustment: signed, max magnitude ±PROP_CORRELATION_CAP

    CRITICAL: These are post-base only. No engine score mutation allowed.
    """
    context_modifier = clamp_context_modifier(context_modifier, cap=cap)

    # Import caps for validation
    try:
        from core.scoring_contract import (
            MSRF_BOOST_CAP, SERP_BOOST_CAP_TOTAL, JASON_SIM_BOOST_CAP,
            HOOK_PENALTY_CAP, EXPERT_CONSENSUS_CAP, PROP_CORRELATION_CAP,
        )
        msrf_boost = max(-MSRF_BOOST_CAP, min(MSRF_BOOST_CAP, msrf_boost))
        serp_boost = max(0.0, min(SERP_BOOST_CAP_TOTAL, serp_boost))
        jason_sim_boost = max(-JASON_SIM_BOOST_CAP, min(JASON_SIM_BOOST_CAP, jason_sim_boost))
        # v20.3: Cap post-base signals
        hook_penalty = max(-HOOK_PENALTY_CAP, min(0.0, hook_penalty))  # Must be <=0
        expert_consensus_boost = max(0.0, min(EXPERT_CONSENSUS_CAP, expert_consensus_boost))  # Must be >=0
        prop_correlation_adjustment = max(-PROP_CORRELATION_CAP, min(PROP_CORRELATION_CAP, prop_correlation_adjustment))
    except Exception:
        # Fallback caps if import fails
        hook_penalty = max(-0.25, min(0.0, hook_penalty))
        expert_consensus_boost = max(0.0, min(0.35, expert_consensus_boost))
        prop_correlation_adjustment = max(-0.20, min(0.20, prop_correlation_adjustment))

    # Cap total boosts (confluence + msrf + jason_sim + serp + ensemble + totals_cal) to prevent score inflation
    # Note: hook/expert/prop are NOT included in TOTAL_BOOST_CAP - they have their own caps
    total_boosts = confluence_boost + msrf_boost + jason_sim_boost + serp_boost + ensemble_adjustment + totals_calibration_adj
    try:
        from core.scoring_contract import TOTAL_BOOST_CAP
        if total_boosts > TOTAL_BOOST_CAP:
            total_boosts = TOTAL_BOOST_CAP
    except Exception:
        pass

    # v20.3: Final score includes all post-base signals explicitly
    final_score = (
        base_score
        + context_modifier
        + total_boosts
        + hook_penalty
        + expert_consensus_boost
        + prop_correlation_adjustment
    )

    # Clamp final score to [0, 10]
    final_score = max(0.0, min(10.0, final_score))
    return final_score, context_modifier


def compute_harmonic_boost(research_score: float, esoteric_score: float) -> float:
    """Return harmonic convergence boost when both scores meet threshold."""
    try:
        from core.scoring_contract import HARMONIC_CONVERGENCE_THRESHOLD, HARMONIC_BOOST
    except Exception:
        HARMONIC_CONVERGENCE_THRESHOLD = 7.5
        HARMONIC_BOOST = 1.0  # v20.11: Lowered from 1.5 to match recalibration
    if research_score >= HARMONIC_CONVERGENCE_THRESHOLD and esoteric_score >= HARMONIC_CONVERGENCE_THRESHOLD:
        return HARMONIC_BOOST
    return 0.0

# =============================================================================
# LEGACY/UNUSED — score_candidate() is NOT called in production.
#
# Production scoring happens in live_data_router.py:calculate_jarvis_engine_score()
# (lines 2819-3037) which computes real jarvis_rs from sacred number triggers,
# gematria signals, and mid-spread goldilocks. That function feeds into the
# BASE_4 formula via the JarvisSavantEngine singleton.
#
# This function is a dormant demo/reference implementation. The hardcoded
# jarvis_score below is a placeholder — the real engine produces jarvis_rs
# values starting at JARVIS_BASELINE_FLOOR (4.5) with additive trigger
# contributions. Most picks get 4.5 because sacred number triggers are
# statistically rare by design:
#
#   Sacred triggers and their rarity:
#     IMMORTAL (2178): +3.5 → 8.0  — requires gematria sum = 2178 (very rare)
#     ORDER (201):     +2.5 → 7.0  — gematria sum = 201
#     MASTER/WILL/SOCIETY (33/93/322): +2.0 → 6.5
#     BEAST/JESUS/TESLA (666/888/369): +1.5 → 6.0
#
#   Simple gematria (a=1..z=26) produces player+team sums typically in the
#   100-400 range, so most matchups don't match ANY sacred number. This is
#   intentional: Jarvis should only boost when genuine alignment exists.
#   The GOLD_STAR gate (jarvis_rs >= 6.5) therefore requires at minimum a
#   +2.0 trigger, making GOLD_STAR picks rare — correct behavior.
# =============================================================================

def score_candidate(
    candidate: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    LEGACY/UNUSED — Score a single candidate (game or prop pick).

    NOT called in production. Production uses compute_final_score_option_a()
    for the final score math and live_data_router.py for engine scoring.

    Args:
        candidate: Normalized candidate dict with required fields:
            - game_str: str (e.g., "LAL @ BOS")
            - player_name: str (empty for game picks)
            - pick_type: str (PROP, SPREAD, TOTAL, MONEYLINE, SHARP)
            - line: float
            - side: str
            - spread: float (for context)
            - total: float (for context)
            - odds: int (American odds)

        context: Optional context dict with:
            - sharp_signal: Dict (from research engine)
            - public_pct: float
            - injury_status: str
            - event_id: str
            - home_team: str
            - away_team: str

    Returns:
        Dict with scored pick:
            - ai_score: float (0-10)
            - research_score: float (0-10)
            - esoteric_score: float (0-10)
            - jarvis_score: float (0-10)
            - base_score: float (weighted sum before confluence)
            - confluence_boost: float (0-3)
            - jason_sim_boost: float (can be negative)
            - final_score: float (total score)
            - tier: str (TITANIUM_SMASH, GOLD_STAR, EDGE_LEAN, MONITOR, PASS)
            - ai_reasons: list
            - research_reasons: list
            - esoteric_reasons: list
            - jarvis_reasons: list
            - jason_sim_reasons: list
            - scoring_breakdown: dict (detailed component scores)

    Raises:
        ValueError: If candidate missing required fields
    """
    # Validate required fields
    _validate_candidate(candidate)

    # Extract candidate fields
    game_str = candidate.get("game_str", "")
    player_name = candidate.get("player_name", "")
    pick_type = candidate.get("pick_type", "GAME")
    line = candidate.get("line", 0)
    side = candidate.get("side", "")
    spread = candidate.get("spread", 0)
    total = candidate.get("total", 220)
    prop_line = candidate.get("prop_line", line)  # For props, line and prop_line are same

    # Extract context
    if context is None:
        context = {}

    sharp_signal = context.get("sharp_signal", {})
    public_pct = context.get("public_pct", 50)
    home_team = context.get("home_team", "")
    away_team = context.get("away_team", "")

    # =========================================================================
    # ENGINE 1: AI SCORE (0-10)
    # =========================================================================
    base_ai = 5.0 if player_name else 4.5  # Props start higher
    ai_boost = 0.0

    # Sharp signal present: +0.5
    if sharp_signal:
        ai_boost += 0.5

    # Signal strength: +1.0 / +0.5 / +0.25
    sig_strength = sharp_signal.get("signal_strength", "NONE")
    if sig_strength == "STRONG":
        ai_boost += 1.0
    elif sig_strength == "MODERATE":
        ai_boost += 0.5
    elif sig_strength == "MILD":
        ai_boost += 0.25

    # Favorable spread: +0.5
    if 3 <= abs(spread) <= 10:
        ai_boost += 0.5

    # Player data: +0.25
    if player_name:
        ai_boost += 0.25

    ai_score = min(10.0, base_ai + ai_boost)
    ai_reasons = [f"Base AI: {base_ai}, Boost: {ai_boost:.2f}"]

    # =========================================================================
    # ENGINE 2: RESEARCH SCORE (0-10)
    # =========================================================================
    research_score = 0.0
    research_reasons = []

    # Sharp money (0-3 pts)
    sharp_boost = 0.0
    if sig_strength == "STRONG":
        sharp_boost = 3.0
        research_reasons.append("Sharp signal STRONG (+3.0)")
    elif sig_strength == "MODERATE":
        sharp_boost = 1.5
        research_reasons.append("Sharp signal MODERATE (+1.5)")
    elif sig_strength == "MILD":
        sharp_boost = 0.5
        research_reasons.append("Sharp signal MILD (+0.5)")

    # Line variance (0-3 pts)
    line_variance = sharp_signal.get("line_variance", 0)
    line_boost = 0.0
    if line_variance > 1.5:
        line_boost = 3.0
        research_reasons.append(f"Line variance {line_variance:.1f}pts (strong)")
    elif line_variance > 0.5:
        line_boost = 1.5
        research_reasons.append(f"Line variance {line_variance:.1f}pts (moderate)")

    # Public fade (0-2 pts)
    public_boost = 0.0
    if public_pct >= 75:
        public_boost = 2.0
        research_reasons.append(f"Public at {public_pct}% (fade signal)")
    elif public_pct >= 65:
        public_boost = 1.0
        research_reasons.append(f"Public at {public_pct}% (mild fade)")

    # Base research (2-3 pts)
    base_research = 2.0
    has_real_splits = sharp_signal and (sharp_signal.get("ticket_pct") is not None or sharp_signal.get("money_pct") is not None)
    if has_real_splits:
        mt_diff = abs((sharp_signal.get("money_pct") or 50) - (sharp_signal.get("ticket_pct") or 50))
        if mt_diff >= 3:
            base_research = 3.0
            research_reasons.append(f"Real splits present (m/t diff={mt_diff:.0f}%)")

    research_score = min(10.0, base_research + sharp_boost + line_boost + public_boost)

    # =========================================================================
    # ENGINE 3: ESOTERIC SCORE (0-10)
    # =========================================================================
    # NOTE: For props, use prop_line FIRST for magnitude (not spread=0)
    # For games, use spread/total

    if player_name:
        # PROP: Use prop_line first
        eso_magnitude = abs(prop_line) if prop_line else 0
        if eso_magnitude == 0 and spread:
            eso_magnitude = abs(spread)
    else:
        # GAME: Use spread/total
        eso_magnitude = abs(spread) if spread else abs(total / 10) if total else 0

    # Esoteric components (simplified - real implementation would call esoteric engine)
    esoteric_score = 3.5  # Default median
    esoteric_reasons = [
        f"Magnitude: {eso_magnitude:.1f}",
        "Numerology: 35%",
        "Astro: 25%",
        "Fib/Vortex: 30%",
        "Daily: 10%"
    ]

    # =========================================================================
    # ENGINE 4: JARVIS SCORE (0-10)
    # =========================================================================
    # Placeholder — production uses calculate_jarvis_engine_score() in
    # live_data_router.py which computes real triggers from gematria sums.
    jarvis_score = JARVIS_BASELINE_FLOOR + 0.5  # Baseline floor + small offset
    jarvis_reasons = ["Gematria triggers", "Mid-spread check"]

    # =========================================================================
    # BASE SCORE CALCULATION
    # =========================================================================
    base_score = (
        (ai_score * ENGINE_WEIGHT_AI) +
        (research_score * ENGINE_WEIGHT_RESEARCH) +
        (esoteric_score * ENGINE_WEIGHT_ESOTERIC) +
        (jarvis_score * ENGINE_WEIGHT_JARVIS)
    )

    # =========================================================================
    # CONFLUENCE BOOST
    # =========================================================================
    # Calculate alignment between research and esoteric
    alignment = 1.0 - abs(research_score - esoteric_score) / 10.0

    # Check if at least one active signal present
    jarvis_active = jarvis_score >= 6.5
    research_sharp_present = sharp_signal.get("signal_strength") in ["STRONG", "MODERATE", "MILD"]
    has_active_signal = jarvis_active or research_sharp_present

    # Confluence logic
    confluence_boost = 0.0
    confluence_label = "DIVERGENT"

    if alignment >= 0.80 and has_active_signal:
        confluence_boost = 3.0
        confluence_label = "STRONG"
    elif alignment >= 0.70:
        confluence_boost = 1.0
        confluence_label = "MODERATE"
    elif alignment >= 0.60:
        confluence_boost = 1.0
        confluence_label = "MODERATE"

    # =========================================================================
    # JASON SIM 2.0 (Post-Pick Confluence)
    # =========================================================================
    jason_sim_boost = 0.0
    jason_sim_reasons = []
    jason_sim_available = False

    # Simplified - real implementation would call jason_sim_confluence
    # For now, placeholder

    # =========================================================================
    # FINAL SCORE (with optional context modifier)
    # =========================================================================
    context_modifier = 0.0
    msrf_boost = 0.0
    serp_boost = 0.0
    if isinstance(context, dict):
        try:
            context_modifier = float(context.get("context_modifier", 0.0))
        except Exception:
            context_modifier = 0.0
        try:
            msrf_boost = float(context.get("msrf_boost", 0.0))
        except Exception:
            msrf_boost = 0.0
        try:
            serp_boost = float(context.get("serp_boost", 0.0))
        except Exception:
            serp_boost = 0.0

    final_score, context_modifier = compute_final_score_option_a(
        base_score=base_score,
        context_modifier=context_modifier,
        confluence_boost=confluence_boost,
        msrf_boost=msrf_boost,
        jason_sim_boost=jason_sim_boost,
        serp_boost=serp_boost,
    )

    # =========================================================================
    # TIER ASSIGNMENT
    # =========================================================================
    # Check Titanium first (overrides all) - strict 3/4 via single helper
    try:
        from core.titanium import evaluate_titanium
        titanium_triggered, _, qualifying_engines = evaluate_titanium(
            ai_score=ai_score,
            research_score=research_score,
            esoteric_score=esoteric_score,
            jarvis_score=jarvis_score,
            final_score=final_score,
            threshold=8.0
        )
    except Exception:
        qualifying_engines = [name for name, score in {
            "ai": ai_score,
            "research": research_score,
            "esoteric": esoteric_score,
            "jarvis": jarvis_score,
        }.items() if score >= 8.0]
        titanium_triggered = len(qualifying_engines) >= 3

    if titanium_triggered:
        tier = "TITANIUM_SMASH"
    elif final_score >= 7.5:
        # Check GOLD_STAR gates
        from core.scoring_contract import GOLD_STAR_GATES
        gold_star_eligible = (
            ai_score >= GOLD_STAR_GATES["ai_score"] and
            research_score >= GOLD_STAR_GATES["research_score"] and
            jarvis_score >= GOLD_STAR_GATES["jarvis_score"] and
            esoteric_score >= GOLD_STAR_GATES["esoteric_score"]
        )
        tier = "GOLD_STAR" if gold_star_eligible else "EDGE_LEAN"
    elif final_score >= 6.5:
        tier = "EDGE_LEAN"
    elif final_score >= 5.5:
        tier = "MONITOR"
    else:
        tier = "PASS"

    # Validate score threshold
    if INVARIANTS_AVAILABLE and final_score >= COMMUNITY_MIN_SCORE:
        is_valid, error = validate_score_threshold(final_score, tier)
        if not is_valid:
            logger.error(f"Score validation failed: {error}")

    # =========================================================================
    # RETURN SCORED PICK
    # =========================================================================
    return {
        # Engine scores
        "ai_score": round(ai_score, 2),
        "research_score": round(research_score, 2),
        "esoteric_score": round(esoteric_score, 2),
        "jarvis_score": round(jarvis_score, 2),

        # Score components
        "base_score": round(base_score, 2),
        "context_modifier": round(context_modifier, 3),
        "confluence_boost": round(confluence_boost, 2),
        "confluence_label": confluence_label,
        "jason_sim_boost": round(jason_sim_boost, 2),
        "msrf_boost": round(msrf_boost, 2),
        "serp_boost": round(serp_boost, 2),
        "final_score": round(final_score, 2),

        # Tier
        "tier": tier,
        "titanium_triggered": titanium_triggered,
        "qualifying_engines": qualifying_engines,

        # Reasons
        "ai_reasons": ai_reasons,
        "research_reasons": research_reasons,
        "esoteric_reasons": esoteric_reasons,
        "jarvis_reasons": jarvis_reasons,
        "jason_sim_reasons": jason_sim_reasons,

        # Breakdown
        "scoring_breakdown": {
            "ai": {
                "base": base_ai,
                "boost": round(ai_boost, 2),
                "total": round(ai_score, 2),
            },
            "research": {
                "sharp": round(sharp_boost, 2),
                "line_variance": round(line_boost, 2),
                "public_fade": round(public_boost, 2),
                "base": base_research,
                "total": round(research_score, 2),
            },
            "esoteric": {
                "magnitude": round(eso_magnitude, 2),
                "total": round(esoteric_score, 2),
            },
            "jarvis": {
                "total": round(jarvis_score, 2),
            },
            "confluence": {
                "alignment": round(alignment, 2),
                "has_active_signal": has_active_signal,
                "boost": round(confluence_boost, 2),
                "label": confluence_label,
            },
            "msrf": {
                "boost": round(msrf_boost, 2),
            },
            "jason_sim": {
                "available": jason_sim_available,
                "boost": round(jason_sim_boost, 2),
            },
            "serp": {
                "boost": round(serp_boost, 2),
            },
        }
    }


# =============================================================================
# VALIDATION
# =============================================================================

def _validate_candidate(candidate: Dict[str, Any]) -> None:
    """Validate candidate has required fields."""
    required = ["game_str", "pick_type"]
    missing = [f for f in required if f not in candidate]

    if missing:
        raise ValueError(f"Candidate missing required fields: {missing}")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Active production functions
    "clamp_context_modifier",
    "compute_final_score_option_a",
    "compute_harmonic_boost",
    # Legacy/reference (not used in production)
    "score_candidate",
]
