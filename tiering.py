"""
TIERING.PY - SINGLE SOURCE OF TRUTH FOR BET TIERS
=================================================
v12.0 - Production hardened tier system with Titanium support

This module is the ONLY place tier configurations should be defined.
All other files should import from here via:
    from tiering import tier_from_score, get_tier_config, check_titanium_rule

TIER HIERARCHY (highest to lowest):
1. TITANIUM_SMASH - Rare conviction tier (3/4 engines >= 8.0 AND final_score >= 8.0)
2. GOLD_STAR - Maximum confidence (final_score >= 7.5)
3. EDGE_LEAN - Strong edge (final_score >= 6.5)
4. ML_DOG_LOTTO - NHL Dog Protocol special
5. MONITOR - Track only (final_score >= 5.5)
6. PASS - No action (final_score < 5.5)

COMMUNITY OUTPUT FILTER: Only picks with final_score >= 6.5 are shown to community.
"""

from typing import Dict, Any, List, Optional, Tuple

# =============================================================================
# ENGINE VERSION
# =============================================================================
ENGINE_VERSION = "12.0"

# =============================================================================
# TITANIUM THRESHOLD CONFIGURATION
# =============================================================================
TITANIUM_THRESHOLD = 8.0  # STRICT: Each engine must score >= 8.0 to qualify
TITANIUM_FINAL_SCORE_MIN = 8.0  # Final score must also be >= 8.0
TITANIUM_MIN_ENGINES = 3  # Minimum engines meeting threshold (out of 4)
TITANIUM_REQUIRES_JARVIS = True  # Prefer Jarvis as one of the qualifying engines

# =============================================================================
# COMMUNITY OUTPUT FILTER
# =============================================================================
COMMUNITY_MIN_SCORE = 6.5  # Only show picks >= 6.5 to community

# =============================================================================
# TIER CONFIGURATION - SINGLE SOURCE OF TRUTH
# =============================================================================
TIER_CONFIG = {
    "TITANIUM_SMASH": {
        "units": 2.5,           # Base units (or Kelly * 1.25)
        "kelly_multiplier": 1.25,
        "action": "SMASH",
        "badge": "TITANIUM SMASH",
        "priority": 1,          # Highest priority
        "threshold": None,      # Special rule: 3/4 engines >= 8.0 AND final_score >= 8.0
        "description": "Rare conviction - 3 of 4 engines >= 8.0 + final >= 8.0"
    },
    "GOLD_STAR": {
        "units": 2.0,
        "kelly_multiplier": 1.0,
        "action": "SMASH",
        "badge": "GOLD STAR",
        "priority": 2,
        "threshold": 7.5,       # Changed from 9.0 per production hardening spec
        "description": "Maximum confidence - all signals aligned"
    },
    "EDGE_LEAN": {
        "units": 1.0,
        "kelly_multiplier": 1.0,
        "action": "PLAY",
        "badge": "EDGE LEAN",
        "priority": 3,
        "threshold": 6.5,       # Changed from 7.5 per production hardening spec
        "description": "Strong edge - most signals agree"
    },
    "ML_DOG_LOTTO": {
        "units": 0.5,
        "kelly_multiplier": 1.0,
        "action": "LOTTO",
        "badge": "ML DOG LOTTO",
        "priority": 4,
        "threshold": None,      # Special rule: NHL Dog Protocol
        "description": "NHL underdog protocol triggered"
    },
    "MONITOR": {
        "units": 0.0,
        "kelly_multiplier": 0.0,
        "action": "WATCH",
        "badge": "MONITOR",
        "priority": 5,
        "threshold": 5.5,       # Changed from 6.0 per production hardening spec
        "description": "Track but no action recommended"
    },
    "PASS": {
        "units": 0.0,
        "kelly_multiplier": 0.0,
        "action": "SKIP",
        "badge": "PASS",
        "priority": 6,
        "threshold": None,      # Everything below MONITOR
        "description": "Insufficient edge - no action"
    }
}

# =============================================================================
# TIER HELPER FUNCTIONS
# =============================================================================

def get_tier_config(tier: str) -> Dict[str, Any]:
    """
    Get full configuration for a tier.

    Args:
        tier: Tier name (e.g., "GOLD_STAR", "TITANIUM_SMASH")

    Returns:
        Dict with units, action, badge, kelly_multiplier, etc.
    """
    return TIER_CONFIG.get(tier, TIER_CONFIG["PASS"])


def check_titanium_rule(
    ai_score: float,
    research_score: float,
    esoteric_score: float,
    jarvis_score: float,
    final_score: float = None
) -> Tuple[bool, str, List[str]]:
    """
    Check if Titanium tier is triggered.

    TITANIUM RULE (MANDATORY - SINGLE SOURCE OF TRUTH):
    Uses core.titanium.compute_titanium_flag() - the ONLY function that determines Titanium status.

    RULE: titanium_triggered=true ONLY when >= 3 of 4 engines >= 8.0 (STRICT)

    Args:
        ai_score: AI model score (0-10 scale)
        research_score: Research score (0-10 scale)
        esoteric_score: Esoteric score (0-10 scale)
        jarvis_score: Jarvis raw score (0-10 scale)
        final_score: Final blended score (0-10 scale) - used for prerequisite check

    Returns:
        Tuple of (triggered: bool, explanation: str, qualifying_engines: List[str])
    """
    # Import the SINGLE SOURCE OF TRUTH for Titanium computation
    from core.titanium import compute_titanium_flag

    # NEW: Final score prerequisite (mandatory)
    if final_score is not None and final_score < TITANIUM_FINAL_SCORE_MIN:
        return False, f"Titanium: Final score {final_score:.1f} < {TITANIUM_FINAL_SCORE_MIN} (prerequisite not met)", []

    # Use the SINGLE SOURCE OF TRUTH - core.titanium.compute_titanium_flag
    titanium_triggered, diagnostics = compute_titanium_flag(
        ai_score=ai_score,
        research_score=research_score,
        esoteric_score=esoteric_score,
        jarvis_score=jarvis_score,
        threshold=8.0  # STRICT: Must be 8.0 (not 6.5)
    )

    # Extract info from diagnostics
    qualifying_engines = diagnostics.get("titanium_engines_hit", [])
    explanation = diagnostics.get("titanium_reason", "Unknown")

    # Return the result from the single source of truth
    return titanium_triggered, explanation, qualifying_engines


def tier_from_score(
    final_score: float,
    confluence: Dict[str, Any] = None,
    nhl_dog_protocol: bool = False,
    titanium_triggered: bool = False
) -> Dict[str, Any]:
    """
    Determine bet tier based on final score and special conditions.

    SINGLE SOURCE OF TRUTH for tier determination.

    Priority order:
    1. Titanium (if titanium_triggered=True)
    2. NHL Dog Protocol (if nhl_dog_protocol=True)
    3. Score-based tiers (GOLD_STAR, EDGE_LEAN, MONITOR, PASS)

    Args:
        final_score: The calculated final score (0-10 scale)
        confluence: Optional confluence data with level and boost
        nhl_dog_protocol: Whether NHL dog protocol is triggered
        titanium_triggered: Whether Titanium rule is triggered (3/4 engines >= 8.0 STRICT)

    Returns:
        Dict with tier, units, action, badge, explanation
    """
    confluence = confluence or {}
    confluence_level = confluence.get("level", "DIVERGENT")

    # PRIORITY 1: Titanium (overrides everything except when explicitly not triggered)
    if titanium_triggered:
        config = TIER_CONFIG["TITANIUM_SMASH"]
        return {
            "tier": "TITANIUM_SMASH",
            "unit_size": config["units"],
            "units": config["units"],
            "action": config["action"],
            "badge": config["badge"],
            "kelly_multiplier": config["kelly_multiplier"],
            "explanation": f"TITANIUM SMASH - Rare conviction. {config['units']} unit play.",
            "final_score": round(final_score, 2),
            "confluence_level": confluence_level,
            "nhl_dog_protocol": nhl_dog_protocol,
            "titanium_triggered": True
        }

    # PRIORITY 2: NHL Dog Protocol
    if nhl_dog_protocol:
        config = TIER_CONFIG["ML_DOG_LOTTO"]
        return {
            "tier": "ML_DOG_LOTTO",
            "unit_size": config["units"],
            "units": config["units"],
            "action": config["action"],
            "badge": config["badge"],
            "kelly_multiplier": config["kelly_multiplier"],
            "explanation": f"NHL Dog Protocol triggered. {config['units']} unit ML dog lotto play.",
            "final_score": round(final_score, 2),
            "confluence_level": confluence_level,
            "nhl_dog_protocol": True,
            "titanium_triggered": False
        }

    # PRIORITY 3: Score-based tiers (v12.0 thresholds)
    if final_score >= 7.5:
        tier = "GOLD_STAR"
    elif final_score >= 6.5:
        tier = "EDGE_LEAN"
    elif final_score >= 5.5:
        tier = "MONITOR"
    else:
        tier = "PASS"

    config = TIER_CONFIG[tier]
    return {
        "tier": tier,
        "unit_size": config["units"],
        "units": config["units"],
        "action": config["action"],
        "badge": config["badge"],
        "kelly_multiplier": config["kelly_multiplier"],
        "explanation": f"{config['badge']} - {config['description']}. {config['units']} unit play." if config['units'] > 0 else f"{config['badge']} - {config['description']}.",
        "final_score": round(final_score, 2),
        "confluence_level": confluence_level,
        "nhl_dog_protocol": nhl_dog_protocol,
        "titanium_triggered": False
    }


def calculate_kelly_units(
    base_units: float,
    tier: str,
    kelly_bet_size: Optional[float] = None,
    odds: Optional[int] = None
) -> float:
    """
    Calculate final unit size using Kelly criterion if available.

    For TITANIUM_SMASH: Apply 1.25x multiplier to Kelly units
    For other tiers: Use Kelly units or fall back to tier-based units

    Args:
        base_units: Default units from tier config
        tier: The tier name
        kelly_bet_size: Kelly optimal bet size (0-1 range, e.g., 0.05 = 5%)
        odds: American odds (for Kelly calculation context)

    Returns:
        Final unit size
    """
    config = get_tier_config(tier)

    if kelly_bet_size is not None and kelly_bet_size > 0:
        # Convert Kelly percentage to units (assuming 1% bankroll = 0.5 units baseline)
        kelly_units = kelly_bet_size * 50  # 5% Kelly = 2.5 units base

        # Apply tier-specific multiplier
        multiplier = config.get("kelly_multiplier", 1.0)
        final_units = kelly_units * multiplier

        # Cap at reasonable maximum
        max_units = 5.0 if tier == "TITANIUM_SMASH" else 3.0
        return min(final_units, max_units)

    # Fallback to tier-based units
    return base_units


def scale_ai_score_to_10(ai_score: float, max_ai: float = 8.0) -> float:
    """
    Scale AI score from 0-8 range to 0-10 range for Titanium comparison.

    Args:
        ai_score: Raw AI score (0-8 range)
        max_ai: Maximum possible AI score (default 8.0)

    Returns:
        Scaled score (0-10 range)
    """
    return (ai_score / max_ai) * 10.0


def scale_jarvis_score_to_10(jarvis_score: float, max_jarvis: float = 2.0) -> float:
    """
    Scale Jarvis score from 0-2 range to 0-10 range for Titanium comparison.

    Args:
        jarvis_score: Raw Jarvis score (0-2 range typically)
        max_jarvis: Maximum possible Jarvis score (default 2.0)

    Returns:
        Scaled score (0-10 range)
    """
    return (jarvis_score / max_jarvis) * 10.0


# =============================================================================
# CONFIDENCE MAPPING (backwards compatibility)
# =============================================================================
CONFIDENCE_MAP = {
    "TITANIUM_SMASH": "SMASH",
    "GOLD_STAR": "SMASH",
    "EDGE_LEAN": "HIGH",
    "ML_DOG_LOTTO": "MEDIUM",
    "MONITOR": "MEDIUM",
    "PASS": "LOW"
}

CONFIDENCE_SCORE_MAP = {
    "SMASH": 95,
    "HIGH": 80,
    "MEDIUM": 60,
    "LOW": 30
}


def get_confidence_from_tier(tier: str) -> Tuple[str, int]:
    """
    Get confidence level and score from tier name.

    Returns:
        Tuple of (confidence_level: str, confidence_score: int)
    """
    confidence = CONFIDENCE_MAP.get(tier, "LOW")
    score = CONFIDENCE_SCORE_MAP.get(confidence, 30)
    return confidence, score


# =============================================================================
# INJURY ENFORCEMENT
# =============================================================================

# Injury statuses that INVALIDATE a prop (must be excluded)
INVALID_INJURY_STATUSES = {"OUT", "DOUBTFUL", "SUSPENDED", "DNP", "INACTIVE"}

# Injury statuses that DOWNGRADE tier by one level
DOWNGRADE_INJURY_STATUSES = {"QUESTIONABLE", "PROBABLE", "GTD"}

# Tier downgrade mapping
TIER_DOWNGRADE_MAP = {
    "TITANIUM_SMASH": "GOLD_STAR",
    "GOLD_STAR": "EDGE_LEAN",
    "EDGE_LEAN": "MONITOR",
    "MONITOR": "PASS",
    "PASS": "PASS",
    "ML_DOG_LOTTO": "MONITOR"
}


def check_injury_validity(injury_status: str) -> Tuple[bool, str]:
    """
    Check if a prop is valid based on injury status.

    Args:
        injury_status: Player's injury status string

    Returns:
        Tuple of (is_valid: bool, reason: str)
    """
    if not injury_status:
        return True, "HEALTHY"

    status_upper = injury_status.upper().strip()

    if status_upper in INVALID_INJURY_STATUSES:
        return False, f"INVALID_INJURY: {status_upper}"

    if status_upper in DOWNGRADE_INJURY_STATUSES:
        return True, f"DOWNGRADE: {status_upper}"

    return True, "HEALTHY"


def apply_injury_downgrade(tier: str, injury_status: str) -> Tuple[str, bool]:
    """
    Apply tier downgrade if player has QUESTIONABLE/PROBABLE status.

    Args:
        tier: Current tier
        injury_status: Player's injury status

    Returns:
        Tuple of (new_tier: str, was_downgraded: bool)
    """
    if not injury_status:
        return tier, False

    status_upper = injury_status.upper().strip()

    if status_upper in DOWNGRADE_INJURY_STATUSES:
        new_tier = TIER_DOWNGRADE_MAP.get(tier, tier)
        return new_tier, new_tier != tier

    return tier, False


def is_prop_invalid_injury(injury_status: str) -> bool:
    """
    Quick check if prop should be excluded due to injury.

    Args:
        injury_status: Player's injury status

    Returns:
        True if prop should be excluded
    """
    if not injury_status:
        return False

    return injury_status.upper().strip() in INVALID_INJURY_STATUSES


# =============================================================================
# COMMUNITY OUTPUT FILTERING
# =============================================================================

def filter_for_community(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter picks for community output - only show >= COMMUNITY_MIN_SCORE (6.5).

    Args:
        picks: List of pick dictionaries with 'final_score' key

    Returns:
        Filtered list of picks meeting community threshold
    """
    return [p for p in picks if p.get("final_score", 0) >= COMMUNITY_MIN_SCORE]


def is_community_worthy(final_score: float) -> bool:
    """
    Check if a pick meets community output threshold.

    Args:
        final_score: The pick's final score

    Returns:
        True if pick should be shown to community
    """
    return final_score >= COMMUNITY_MIN_SCORE


# =============================================================================
# DEFAULT VALUES
# =============================================================================

# Default Jarvis score when no triggers hit (ensures jarvis_rs always exists)
DEFAULT_JARVIS_RS = 5.0

# Default stack values
DEFAULT_STACK_COMPLETE = True
DEFAULT_PARTIAL_STACK_REASONS: List[str] = []


# =============================================================================
# PROP AVAILABILITY CHECK (Phase 8)
# =============================================================================

def validate_prop_availability(
    player_name: str,
    available_props: List[Dict[str, Any]]
) -> Tuple[bool, str]:
    """
    Check if player is offered on any book - if not, treat as unavailable.

    Args:
        player_name: Player name to check
        available_props: List of available props with 'player' key

    Returns:
        Tuple of (is_available: bool, reason: str)
    """
    if not available_props:
        return False, f"No props available - cannot validate {player_name}"

    # Normalize player name for comparison
    player_lower = player_name.lower().strip()

    # Check if player is in available props
    for prop in available_props:
        prop_player = prop.get("player", "").lower().strip()
        if prop_player == player_lower or player_lower in prop_player or prop_player in player_lower:
            return True, "Available"

    return False, f"Player {player_name} not offered - likely unavailable"
