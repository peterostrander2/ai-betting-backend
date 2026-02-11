"""
JARVIS Score API - Shared Scoring Entrypoint
=============================================

This module provides the SINGLE authoritative Jarvis scoring function.
Both live_data_router.py and hybrid engine import from here.

NO CIRCULAR IMPORTS: This module only imports from jarvis_savant_engine.py
which has no dependencies on live_data_router or hybrid.

Usage:
    from core.jarvis_score_api import calculate_jarvis_engine_score, get_savant_engine
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS (v16.0 Additive Scoring Model)
# =============================================================================

JARVIS_BASELINE = 4.5  # Baseline when inputs present

# Trigger contribution values (ADDITIVE to baseline)
TRIGGER_CONTRIBUTIONS = {
    2178: 3.5,   # IMMORTAL - highest
    201: 2.5,    # ORDER - high
    33: 2.0,     # MASTER - Gold-Star eligible
    93: 2.0,     # WILL - Gold-Star eligible
    322: 2.0,    # SOCIETY - Gold-Star eligible
    666: 1.5,    # BEAST - medium
    888: 1.5,    # JESUS - medium
    369: 1.5,    # TESLA KEY - medium
}

POWER_NUMBER_CONTRIB = 0.8
TESLA_REDUCTION_CONTRIB = 0.5
REDUCTION_MATCH_CONTRIB = 0.5
GEMATRIA_STRONG_CONTRIB = 1.5
GEMATRIA_MODERATE_CONTRIB = 0.8
GOLDILOCKS_CONTRIB = 0.5
STACKING_DECAY = 0.7  # Each additional trigger contributes 70% of previous

VERSION = "JARVIS_SAVANT_v11.08"

# Jarvis sacred triggers (for string fallback)
JARVIS_TRIGGERS = {
    2178: {"name": "THE IMMORTAL", "boost": 3.5, "tier": "LEGENDARY"},
    201: {"name": "THE ORDER", "boost": 2.5, "tier": "HIGH"},
    33: {"name": "THE MASTER", "boost": 2.0, "tier": "HIGH"},
    93: {"name": "THE WILL", "boost": 2.0, "tier": "HIGH"},
    322: {"name": "THE SOCIETY", "boost": 2.0, "tier": "HIGH"},
    666: {"name": "THE BEAST", "boost": 1.5, "tier": "MEDIUM"},
    888: {"name": "JESUS", "boost": 1.5, "tier": "MEDIUM"},
    369: {"name": "TESLA KEY", "boost": 1.5, "tier": "MEDIUM"},
}


# =============================================================================
# SAVANT ENGINE SINGLETON
# =============================================================================

_savant_engine = None


def get_savant_engine():
    """
    Get the JarvisSavantEngine singleton.

    This is the SINGLE source of truth for the savant engine instance.
    Both live_data_router and hybrid should call this function.
    """
    global _savant_engine
    if _savant_engine is None:
        try:
            from jarvis_savant_engine import get_jarvis_engine
            _savant_engine = get_jarvis_engine()
            logger.info("JarvisSavantEngine initialized via jarvis_score_api")
        except ImportError as e:
            logger.warning("JarvisSavantEngine not available: %s", e)
    return _savant_engine


# =============================================================================
# JARVIS SCORING FUNCTION (v16.0 Additive Model)
# =============================================================================

def calculate_jarvis_engine_score(
    jarvis_engine,
    game_str: str,
    player_name: str = "",
    home_team: str = "",
    away_team: str = "",
    spread: float = 0,
    total: float = 0,
    prop_line: float = 0,
    date_et: str = ""
) -> Dict[str, Any]:
    """
    JARVIS ENGINE (0-10 standalone) - v16.0 with ADDITIVE trigger scoring

    This is the SINGLE authoritative Jarvis scoring function.
    Returns standalone jarvis_score plus all required output fields.

    v16.0 GOLD_STAR FIX:
    - Baseline: 4.5 when inputs present but no triggers
    - Triggers ADD to baseline (not replace it)
    - 1 minor trigger => ~5.0-6.2
    - 1 strong trigger OR 2+ triggers => >=6.5 (GOLD_STAR eligible)
    - Stacked triggers => 8.5-10 (rare)
    - Full audit fields: jarvis_baseline, jarvis_trigger_contribs, jarvis_no_trigger_reason

    Trigger Contributions (ADDITIVE to baseline 4.5):
    - IMMORTAL (2178): +3.5 -> total 8.0
    - ORDER (201): +2.5 -> total 7.0
    - MASTER (33): +2.0 -> total 6.5
    - WILL (93): +2.0 -> total 6.5
    - SOCIETY (322): +2.0 -> total 6.5
    - BEAST (666): +1.5 -> total 6.0
    - JESUS (888): +1.5 -> total 6.0
    - TESLA KEY (369): +1.5 -> total 6.0
    - POWER_NUMBER: +0.8 -> total 5.3
    - TESLA_REDUCTION: +0.5 -> total 5.0
    - REDUCTION match: +0.5 -> total 5.0
    - Gematria strong: +1.5, moderate: +0.8
    - Mid-spread goldilocks: +0.5
    """
    jarvis_triggers_hit = []
    jarvis_trigger_contribs = {}  # {trigger_name: contribution}
    jarvis_fail_reasons = []
    jarvis_no_trigger_reason = None
    immortal_detected = False

    # Track inputs used for transparency
    jarvis_inputs_used = {
        "matchup_str": game_str if game_str else None,
        "date_et": date_et if date_et else None,
        "spread": spread if spread != 0 else None,
        "total": total if total != 0 else None,
        "player_line": prop_line if prop_line != 0 else None,
        "home_team": home_team if home_team else None,
        "away_team": away_team if away_team else None,
        "player_name": player_name if player_name else None
    }

    # Check if critical inputs are missing
    inputs_missing = not game_str or (not home_team and not away_team)

    if inputs_missing:
        # CRITICAL INPUTS MISSING - Cannot run Jarvis
        jarvis_fail_reasons.append("Missing critical inputs (matchup_str or teams)")
        return {
            "jarvis_rs": None,
            "jarvis_baseline": None,
            "jarvis_trigger_contribs": {},
            "jarvis_active": False,
            "jarvis_hits_count": 0,
            "jarvis_triggers_hit": [],
            "jarvis_reasons": ["Inputs missing - cannot run"],
            "jarvis_fail_reasons": jarvis_fail_reasons,
            "jarvis_no_trigger_reason": "INPUTS_MISSING",
            "jarvis_inputs_used": jarvis_inputs_used,
            "immortal_detected": False,
            "version": VERSION,
            "blend_type": "SAVANT",
        }

    # Start with baseline
    jarvis_rs = JARVIS_BASELINE
    total_trigger_contrib = 0.0
    gematria_contrib = 0.0
    goldilocks_contrib = 0.0
    trigger_count = 0

    if jarvis_engine:
        # 1. Sacred Triggers - ADDITIVE contributions
        trigger_result = jarvis_engine.check_jarvis_trigger(game_str)
        sorted_triggers = sorted(
            trigger_result.get("triggers_hit", []),
            key=lambda t: TRIGGER_CONTRIBUTIONS.get(t["number"], 0.5),
            reverse=True
        )

        for i, trig in enumerate(sorted_triggers):
            trigger_num = trig["number"]
            match_type = trig.get("match_type", "DIRECT")

            # Get base contribution
            if trigger_num in TRIGGER_CONTRIBUTIONS:
                base_contrib = TRIGGER_CONTRIBUTIONS[trigger_num]
            elif match_type == "POWER_NUMBER":
                base_contrib = POWER_NUMBER_CONTRIB
            elif match_type == "TESLA_REDUCTION":
                base_contrib = TESLA_REDUCTION_CONTRIB
            elif match_type == "REDUCTION":
                base_contrib = REDUCTION_MATCH_CONTRIB
            else:
                base_contrib = 0.5  # Default for unknown triggers

            # Apply stacking decay (70% for each subsequent trigger)
            decay_factor = STACKING_DECAY ** i
            actual_contrib = base_contrib * decay_factor

            jarvis_triggers_hit.append({
                "number": trigger_num,
                "name": trig["name"],
                "match_type": match_type,
                "base_contrib": round(base_contrib, 2),
                "actual_contrib": round(actual_contrib, 2),
                "decay_factor": round(decay_factor, 2)
            })
            jarvis_trigger_contribs[trig["name"]] = round(actual_contrib, 2)
            total_trigger_contrib += actual_contrib
            trigger_count += 1

            if trigger_num == 2178:
                immortal_detected = True

        # 2. Gematria Signal - ADDITIVE contribution
        if player_name and home_team:
            gematria = jarvis_engine.calculate_gematria_signal(player_name, home_team, away_team)
            signal_strength = gematria.get("signal_strength", 0)
            if signal_strength > 0.7:
                gematria_contrib = GEMATRIA_STRONG_CONTRIB
                jarvis_trigger_contribs["gematria_strong"] = gematria_contrib
            elif signal_strength > 0.4:
                gematria_contrib = GEMATRIA_MODERATE_CONTRIB
                jarvis_trigger_contribs["gematria_moderate"] = gematria_contrib

        # 3. Mid-Spread Goldilocks - ADDITIVE contribution
        mid_spread = jarvis_engine.calculate_mid_spread_signal(spread)
        if mid_spread.get("signal") == "GOLDILOCKS":
            goldilocks_contrib = GOLDILOCKS_CONTRIB
            jarvis_trigger_contribs["goldilocks_zone"] = goldilocks_contrib

    else:
        # Fallback: check triggers in game_str directly
        for trigger_num, trigger_data in JARVIS_TRIGGERS.items():
            if str(trigger_num) in game_str:
                base_contrib = TRIGGER_CONTRIBUTIONS.get(trigger_num, 0.5)
                decay_factor = STACKING_DECAY ** trigger_count
                actual_contrib = base_contrib * decay_factor

                jarvis_triggers_hit.append({
                    "number": trigger_num,
                    "name": trigger_data["name"],
                    "match_type": "STRING_MATCH",
                    "base_contrib": round(base_contrib, 2),
                    "actual_contrib": round(actual_contrib, 2),
                    "decay_factor": round(decay_factor, 2)
                })
                jarvis_trigger_contribs[trigger_data["name"]] = round(actual_contrib, 2)
                total_trigger_contrib += actual_contrib
                trigger_count += 1

                if trigger_num == 2178:
                    immortal_detected = True

    # Calculate final jarvis_rs = baseline + all contributions
    jarvis_rs = JARVIS_BASELINE + total_trigger_contrib + gematria_contrib + goldilocks_contrib

    # Cap at 0-10 range
    jarvis_rs = max(0, min(10, jarvis_rs))

    # Determine jarvis_active and build reasons
    jarvis_hits_count = len(jarvis_triggers_hit)
    has_any_contrib = total_trigger_contrib > 0 or gematria_contrib > 0 or goldilocks_contrib > 0

    if has_any_contrib:
        jarvis_active = True
        jarvis_reasons = list(jarvis_trigger_contribs.keys())
        jarvis_no_trigger_reason = None
    else:
        jarvis_active = True  # Inputs present, Jarvis ran
        jarvis_reasons = [f"Baseline {JARVIS_BASELINE} (no triggers)"]
        jarvis_no_trigger_reason = "NO_TRIGGER_BASELINE"
        jarvis_fail_reasons.append(f"No triggers fired - baseline {JARVIS_BASELINE}")

    return {
        "jarvis_rs": round(jarvis_rs, 2),
        "jarvis_baseline": JARVIS_BASELINE,
        "jarvis_trigger_contribs": jarvis_trigger_contribs,
        "jarvis_active": jarvis_active,
        "jarvis_hits_count": jarvis_hits_count,
        "jarvis_triggers_hit": jarvis_triggers_hit,
        "jarvis_reasons": jarvis_reasons,
        "jarvis_fail_reasons": jarvis_fail_reasons,
        "jarvis_no_trigger_reason": jarvis_no_trigger_reason,
        "jarvis_inputs_used": jarvis_inputs_used,
        "immortal_detected": immortal_detected,
        "version": VERSION,
        "blend_type": "SAVANT",
    }


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def score_jarvis(
    home_team: str,
    away_team: str,
    player_name: str = "",
    spread: float = 0.0,
    total: float = 0.0,
    prop_line: float = 0.0,
    game_str: str = "",
    date_et: str = "",
) -> Dict[str, Any]:
    """
    Convenience function that gets the engine and scores in one call.

    This is the recommended entrypoint for callers who just want a Jarvis score.
    """
    # Build game_str if not provided
    if not game_str and home_team and away_team:
        game_str = f"{away_team} @ {home_team}"
        if player_name:
            game_str = f"{player_name} {game_str}"

    engine = get_savant_engine()
    return calculate_jarvis_engine_score(
        jarvis_engine=engine,
        game_str=game_str,
        player_name=player_name,
        home_team=home_team,
        away_team=away_team,
        spread=spread,
        total=total,
        prop_line=prop_line,
        date_et=date_et,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Constants
    "JARVIS_BASELINE",
    "TRIGGER_CONTRIBUTIONS",
    "VERSION",
    # Functions
    "get_savant_engine",
    "calculate_jarvis_engine_score",
    "score_jarvis",
]
