"""
tiering.py - Single Source of Truth for Tier Assignment

v1.0: Consolidated tier logic to eliminate inconsistencies across the codebase.

Tier Thresholds (non-overlapping):
- GOLD_STAR: score >= 7.5   (2 units, SMASH)
- EDGE_LEAN: 6.5 <= score < 7.5   (1 unit, PLAY)
- MONITOR:   5.5 <= score < 6.5   (0 units, WATCH)
- PASS:      score < 5.5   (0 units, SKIP)
"""

from typing import Tuple, Dict, Optional

# =============================================================================
# DEFAULT TIER THRESHOLDS - SINGLE SOURCE OF TRUTH
# =============================================================================

DEFAULT_TIERS: Dict[str, float] = {
    "GOLD_STAR": 7.5,
    "EDGE_LEAN": 6.5,
    "MONITOR": 5.5,
    "PASS": 0.0,  # Explicit floor - anything below MONITOR is PASS
}

TIER_CONFIG: Dict[str, Dict] = {
    "TITANIUM_SMASH": {"units": 2.5, "action": "SMASH", "badge": "TITANIUM SMASH"},
    "GOLD_STAR": {"units": 2.0, "action": "SMASH", "badge": "GOLD STAR"},
    "EDGE_LEAN": {"units": 1.0, "action": "PLAY", "badge": "EDGE LEAN"},
    "MONITOR": {"units": 0.0, "action": "WATCH", "badge": "MONITOR"},
    "PASS": {"units": 0.0, "action": "SKIP", "badge": "PASS"},
}


def clamp_score(x) -> float:
    """Clamp score to 0.0-10.0 range."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        x = 0.0
    return max(0.0, min(10.0, x))


def tier_from_score(score: float, tiers: Optional[Dict[str, float]] = None) -> Tuple[str, str]:
    """
    Return (tier, badge) from score. Single source of truth for tier assignment.

    Args:
        score: The final score (0.0-10.0)
        tiers: Optional per-sport tier thresholds. NOT mutated.

    Returns:
        Tuple of (tier_name, badge_text)

    Thresholds (default):
        - GOLD_STAR: >= 7.5
        - EDGE_LEAN: >= 6.5
        - MONITOR:   >= 5.5
        - PASS:      < 5.5
    """
    # Use defaults, merge with custom if provided (don't mutate input)
    effective_tiers = DEFAULT_TIERS.copy()
    if tiers is not None:
        effective_tiers.update(tiers)

    score = clamp_score(score)

    if score >= effective_tiers.get("GOLD_STAR", 7.5):
        return ("GOLD_STAR", "GOLD STAR")
    if score >= effective_tiers.get("EDGE_LEAN", 6.5):
        return ("EDGE_LEAN", "EDGE LEAN")
    if score >= effective_tiers.get("MONITOR", 5.5):
        return ("MONITOR", "MONITOR")
    return ("PASS", "PASS")


def get_tier_config(tier: str) -> Dict:
    """Get unit sizing and action for a tier."""
    return TIER_CONFIG.get(tier, TIER_CONFIG["PASS"]).copy()


def get_units_for_tier(tier: str) -> float:
    """Get recommended unit size for a tier."""
    return TIER_CONFIG.get(tier, {}).get("units", 0.0)


def get_action_for_tier(tier: str) -> str:
    """Get recommended action for a tier."""
    return TIER_CONFIG.get(tier, {}).get("action", "SKIP")
