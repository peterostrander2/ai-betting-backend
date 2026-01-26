"""
tiering.py - Single Source of Truth for Tier Assignment

v11.10: TITANIUM_SMASH is a real tier (3/4 engines >= 8.0).

Tier Thresholds (non-overlapping):
- TITANIUM_SMASH: titanium_triggered=True (3/4 engines >= 8.0)
- GOLD_STAR: score >= 7.5   (2 units, SMASH)
- EDGE_LEAN: 6.5 <= score < 7.5   (1 unit, PLAY)
- MONITOR:   5.5 <= score < 6.5   (0 units, WATCH)
- PASS:      score < 5.5   (0 units, SKIP)
"""

from typing import Tuple, Dict, Optional, List

# =============================================================================
# DEFAULT TIER THRESHOLDS - SINGLE SOURCE OF TRUTH
# =============================================================================

DEFAULT_TIERS: Dict[str, float] = {
    "GOLD_STAR": 7.5,
    "EDGE_LEAN": 6.5,
    "MONITOR": 5.5,
    "PASS": 0.0,  # Explicit floor - anything below MONITOR is PASS
}

# Tier ordering for downgrade logic (lowest to highest)
TIER_ORDER: List[str] = ["PASS", "MONITOR", "EDGE_LEAN", "GOLD_STAR", "TITANIUM_SMASH"]

# Badges that should NOT appear in badges[] after tier downgrade
TIER_BADGES: set = {"GOLD_STAR", "EDGE_LEAN", "TITANIUM_SMASH", "MONITOR", "PASS"}

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


def tier_from_score(
    score: float,
    tiers: Optional[Dict[str, float]] = None,
    titanium_triggered: bool = False
) -> Tuple[str, str]:
    """
    Return (tier, badge) from score. Single source of truth for tier assignment.

    Args:
        score: The final score (0.0-10.0)
        tiers: Optional per-sport tier thresholds. NOT mutated.
        titanium_triggered: If True, return TITANIUM_SMASH tier

    Returns:
        Tuple of (tier_name, badge_text)

    Thresholds (default):
        - TITANIUM_SMASH: titanium_triggered=True (overrides score-based tier)
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

    # v11.10: TITANIUM_SMASH is a real tier - triggered by 3/4 engines >= 8.0
    if titanium_triggered:
        return ("TITANIUM_SMASH", "TITANIUM SMASH")
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


def normalize_confidence(confidence) -> Tuple[str, int]:
    """
    Normalize confidence to (label, pct) tuple.

    Args:
        confidence: Can be string ("HIGH", "MED", "LOW") or number (0-100)

    Returns:
        Tuple of (confidence_label, confidence_pct)
    """
    # If it's a string label
    if isinstance(confidence, str):
        label = confidence.upper()
        if label in ("HIGH", "SMASH"):
            return ("HIGH", 80)
        elif label in ("MED", "MEDIUM", "MODERATE"):
            return ("MED", 60)
        elif label in ("LOW",):
            return ("LOW", 40)
        else:
            return ("MED", 50)

    # If it's a number
    try:
        pct = int(confidence)
        pct = max(0, min(100, pct))
        if pct >= 70:
            return ("HIGH", pct)
        elif pct >= 50:
            return ("MED", pct)
        else:
            return ("LOW", pct)
    except (TypeError, ValueError):
        return ("MED", 50)


def filter_tier_badges(badges: list, current_tier: str) -> list:
    """
    Remove tier-like badges that contradict current tier.

    Args:
        badges: List of badge strings
        current_tier: The actual tier after all downgrades

    Returns:
        Filtered list with only non-tier badges
    """
    if not badges:
        return []

    # Remove any tier-like badges
    filtered = [b for b in badges if b not in TIER_BADGES]
    return filtered


def downgrade_tier(current_tier: str, steps: int = 1) -> str:
    """
    Downgrade tier by N steps.

    Args:
        current_tier: Current tier name
        steps: Number of steps to downgrade (default 1)

    Returns:
        New tier name after downgrade
    """
    if current_tier not in TIER_ORDER:
        return "PASS"

    current_idx = TIER_ORDER.index(current_tier)
    new_idx = max(0, current_idx - steps)
    return TIER_ORDER[new_idx]
