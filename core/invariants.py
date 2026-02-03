"""
SYSTEM INVARIANTS - Single Source of Truth

This module defines all core system invariants that MUST hold true.
Any violation of these invariants should cause tests to fail and prevent deployment.

These constants are used by:
1. Runtime code (scoring, tiering, filtering)
2. Tests (invariant validation)
3. Release gates (deployment checks)
"""

from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# TITANIUM INVARIANTS (MANDATORY - v15.0)
# =============================================================================

# There are exactly 4 engines used for Titanium gating
TITANIUM_ENGINE_COUNT = 4
TITANIUM_ENGINE_NAMES = ["ai", "research", "esoteric", "jarvis"]

# Qualifying engine threshold
TITANIUM_ENGINE_THRESHOLD = 8.0

# Minimum engines that must qualify for Titanium
TITANIUM_MIN_ENGINES = 3

# Titanium rule: tier == "TITANIUM_SMASH" iff titanium_triggered is True
# It is a BUG if: "TITANIUM: 1/4" and tier is TITANIUM_SMASH


# =============================================================================
# SCORE FILTERING (COMMUNITY FEED)
# =============================================================================

# Never return any pick with final_score < 6.5
COMMUNITY_MIN_SCORE = 6.5

# Picks below this threshold should not be stored as "community picks"
# (they may be stored as internal candidates for analysis)


# =============================================================================
# JARVIS CONTRACT (v15.1 - MANDATORY TRANSPARENCY)
# =============================================================================

# Jarvis must ALWAYS output these 7 fields for every pick
JARVIS_REQUIRED_FIELDS = [
    "jarvis_rs",           # 0-10 or None
    "jarvis_active",       # bool
    "jarvis_hits_count",   # int
    "jarvis_triggers_hit", # array
    "jarvis_reasons",      # array
    "jarvis_fail_reasons", # array
    "jarvis_inputs_used",  # dict
]

# Jarvis baseline floor when inputs present but no triggers
JARVIS_BASELINE_FLOOR = 4.5

# Jarvis rules:
# - If critical inputs missing → jarvis_rs=None, jarvis_active=False
# - If inputs present but no triggers → jarvis_rs=4.5 (baseline floor)
# - If triggers hit → jarvis_rs > 4.5
# - jarvis_rs=None must never contribute to final_score
# - jarvis_rs=None must never count toward Titanium


# =============================================================================
# ESOTERIC RULES (PROPS)
# =============================================================================

# Props must use game_context spread/total for Fib/Vortex (not prop spread=0)
ESOTERIC_PROP_REQUIRES_GAME_CONTEXT = True

# Numerology must include daily + prop-line components
ESOTERIC_PROP_NUMEROLOGY_COMPONENTS = ["daily", "prop_line"]


# =============================================================================
# TIME WINDOW (AMERICA/NEW_YORK)
# =============================================================================

# Timezone for "today" filtering
ET_TIMEZONE = "America/New_York"

# Day boundaries in ET (midnight to midnight, exclusive end)
ET_DAY_START = "00:00"  # 12:00 AM ET
ET_DAY_END = "00:00"    # Next day midnight (exclusive)

# Maximum reasonable event count for single sport "today" slate
# (used for sanity check warnings)
MAX_REASONABLE_EVENTS_PER_SPORT = 60


# =============================================================================
# PICK PERSISTENCE (AUTOGRADER REQUIREMENT)
# =============================================================================

# Every returned pick >= 6.5 must be written to persistent storage with these fields
PICK_STORAGE_REQUIRED_FIELDS = [
    "prediction_id",      # Stable hash
    "sport",
    "market_type",        # "game" or "prop"
    "line_at_bet",
    "odds_at_bet",
    "book",
    "event_start_time_et",
    "created_at",
    "final_score",
    "tier",
    # Engine scores
    "ai_score",
    "research_score",
    "esoteric_score",
    "jarvis_score",
    # Reasons
    "ai_reasons",
    "research_reasons",
    "esoteric_reasons",
    "jarvis_reasons",
]

# Storage must survive container restart (Railway volume)
PICK_STORAGE_PATH_ENV = "RAILWAY_VOLUME_MOUNT_PATH"
PICK_STORAGE_SUBPATH = "pick_logs"


# =============================================================================
# ENGINE WEIGHTS (SCORING FORMULA)
# =============================================================================

# BASE_SCORE = (ai × 0.25) + (research × 0.35) + (esoteric × 0.20) + (jarvis × 0.20)
# Note: Weights sum to 1.00; post-base boosts are additive (context modifier, confluence, Jason, etc.)
from core.scoring_contract import ENGINE_WEIGHTS
ENGINE_WEIGHT_AI = ENGINE_WEIGHTS["ai"]
ENGINE_WEIGHT_RESEARCH = ENGINE_WEIGHTS["research"]
ENGINE_WEIGHT_ESOTERIC = ENGINE_WEIGHTS["esoteric"]
ENGINE_WEIGHT_JARVIS = ENGINE_WEIGHTS["jarvis"]

# Verify weights sum to 1.00 (boosts are additive)
assert abs((ENGINE_WEIGHT_AI + ENGINE_WEIGHT_RESEARCH + ENGINE_WEIGHT_ESOTERIC + ENGINE_WEIGHT_JARVIS) - 1.00) < 0.01


# =============================================================================
# JASON SIM CONTRACT (POST-PICK CONFLUENCE)
# =============================================================================

# Jason Sim required output fields
JASON_SIM_REQUIRED_FIELDS = [
    "jason_sim_available",  # bool
    "jason_sim_boost",      # float (can be negative)
    "jason_sim_reasons",    # array
]

# Jason Sim rules (locked):
# - Spread/ML boost if pick-side win% >= 61%
# - Downgrade if <= 55%
# - Block if <= 52% AND base_score < 7.2
# - Totals: reduce confidence if variance HIGH; increase if LOW/MED
# - Props: only boost if base_prop_score >= 6.8 AND environment supports prop type


# =============================================================================
# VALIDATION FUNCTIONS (RUNTIME GUARDS)
# =============================================================================

def validate_titanium_assignment(
    tier: str,
    titanium_triggered: bool,
    qualifying_engines: List[str],
    engine_scores: Dict[str, float]
) -> Tuple[bool, str]:
    """
    Validate Titanium tier assignment follows invariants.

    Rules:
    1. tier == "TITANIUM_SMASH" iff titanium_triggered is True
    2. titanium_triggered is True iff len(qualifying_engines) >= 3
    3. qualifying_engines contains only engines with score >= 8.0

    Returns:
        (is_valid: bool, error_message: str)
    """
    # Rule 1: Tier and titanium_triggered must match
    if tier == "TITANIUM_SMASH" and not titanium_triggered:
        return False, f"INVARIANT VIOLATION: tier=TITANIUM_SMASH but titanium_triggered=False"

    if tier != "TITANIUM_SMASH" and titanium_triggered:
        return False, f"INVARIANT VIOLATION: titanium_triggered=True but tier={tier} (not TITANIUM_SMASH)"

    # Rule 2: Qualifying engines count
    if titanium_triggered and len(qualifying_engines) < TITANIUM_MIN_ENGINES:
        return False, f"INVARIANT VIOLATION: titanium_triggered=True but only {len(qualifying_engines)}/4 engines qualify (need {TITANIUM_MIN_ENGINES})"

    if not titanium_triggered and len(qualifying_engines) >= TITANIUM_MIN_ENGINES:
        # Check if all qualifying engines are actually >= 8.0
        # (it's possible qualifying_engines list is wrong)
        actual_qualifiers = [
            name for name in TITANIUM_ENGINE_NAMES
            if engine_scores.get(name, 0) >= TITANIUM_ENGINE_THRESHOLD
        ]
        if len(actual_qualifiers) >= TITANIUM_MIN_ENGINES:
            return False, f"INVARIANT VIOLATION: {len(actual_qualifiers)}/4 engines >= 8.0 but titanium_triggered=False"

    # Rule 3: Qualifying engines must actually score >= 8.0
    for engine_name in qualifying_engines:
        score = engine_scores.get(engine_name, 0)
        if score < TITANIUM_ENGINE_THRESHOLD:
            return False, f"INVARIANT VIOLATION: {engine_name} in qualifying_engines but score {score:.2f} < 8.0"

    return True, ""


def validate_jarvis_output(jarvis_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate Jarvis output follows v15.1 contract.

    Rules:
    1. All 7 required fields must be present
    2. If jarvis_rs is None, jarvis_active must be False
    3. If jarvis_rs is None, jarvis_fail_reasons must explain why
    4. If jarvis_active is True, jarvis_rs must not be None

    Returns:
        (is_valid: bool, error_message: str)
    """
    # Rule 1: All required fields present
    for field in JARVIS_REQUIRED_FIELDS:
        if field not in jarvis_data:
            return False, f"INVARIANT VIOLATION: Jarvis missing required field '{field}'"

    jarvis_rs = jarvis_data.get("jarvis_rs")
    jarvis_active = jarvis_data.get("jarvis_active")
    jarvis_fail_reasons = jarvis_data.get("jarvis_fail_reasons", [])

    # Rule 2: jarvis_rs=None implies jarvis_active=False
    if jarvis_rs is None and jarvis_active is not False:
        return False, f"INVARIANT VIOLATION: jarvis_rs=None but jarvis_active={jarvis_active} (should be False)"

    # Rule 3: jarvis_rs=None must have fail_reasons
    if jarvis_rs is None and not jarvis_fail_reasons:
        return False, f"INVARIANT VIOLATION: jarvis_rs=None but jarvis_fail_reasons is empty (must explain why)"

    # Rule 4: jarvis_active=True implies jarvis_rs is not None
    if jarvis_active is True and jarvis_rs is None:
        return False, f"INVARIANT VIOLATION: jarvis_active=True but jarvis_rs=None"

    return True, ""


def validate_pick_storage(pick_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate pick has all required fields for storage/grading.

    Returns:
        (is_valid: bool, error_message: str)
    """
    for field in PICK_STORAGE_REQUIRED_FIELDS:
        if field not in pick_data:
            return False, f"INVARIANT VIOLATION: Pick missing required storage field '{field}'"

    return True, ""


def validate_score_threshold(final_score: float, tier: str) -> Tuple[bool, str]:
    """
    Validate pick meets minimum score threshold.

    Rules:
    1. final_score >= 6.5 for any returned pick
    2. If tier is assigned (not PASS), final_score >= 6.5

    Returns:
        (is_valid: bool, error_message: str)
    """
    if final_score < COMMUNITY_MIN_SCORE:
        return False, f"INVARIANT VIOLATION: final_score {final_score:.2f} < {COMMUNITY_MIN_SCORE} (should not be returned)"

    if tier != "PASS" and final_score < COMMUNITY_MIN_SCORE:
        return False, f"INVARIANT VIOLATION: tier={tier} but final_score {final_score:.2f} < {COMMUNITY_MIN_SCORE}"

    return True, ""


# =============================================================================
# RUNTIME GUARD HELPER
# =============================================================================

def enforce_invariant(is_valid: bool, error_message: str, pick_id: str = None):
    """
    Enforce an invariant - log error and optionally raise exception.

    In production: Log ERROR but don't crash (allow degraded operation)
    In tests: Raise AssertionError to fail the test

    Args:
        is_valid: Whether invariant holds
        error_message: Error message if violated
        pick_id: Optional pick identifier for logging
    """
    if not is_valid:
        log_msg = f"{error_message}"
        if pick_id:
            log_msg += f" | pick_id={pick_id}"

        logger.error(log_msg)

        # In test environment, raise exception to fail tests
        import os
        if os.getenv("PYTEST_CURRENT_TEST"):
            raise AssertionError(error_message)

        # In production, just log (degraded operation)
        # Could also set health endpoint to degraded status


# =============================================================================
# HEALTH STATUS
# =============================================================================

# Global health status (can be set by runtime guards)
_health_degraded = False
_health_errors = []


def set_health_degraded(reason: str):
    """Mark system health as degraded"""
    global _health_degraded, _health_errors
    _health_degraded = True
    _health_errors.append(reason)
    logger.error(f"HEALTH DEGRADED: {reason}")


def get_health_status() -> Tuple[bool, List[str]]:
    """Get current health status"""
    return _health_degraded, _health_errors


def reset_health_status():
    """Reset health status (for testing)"""
    global _health_degraded, _health_errors
    _health_degraded = False
    _health_errors = []
