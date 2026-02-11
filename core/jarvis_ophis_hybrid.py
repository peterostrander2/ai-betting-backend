"""
JARVIS-OPHIS HYBRID ENGINE v2.1 "JARVIS PRIMARY + OPHIS DELTA"
==============================================================
Contract Version: 20.2

Engine 4 in the 4-engine scoring architecture.
Blend: Jarvis Primary + Bounded Ophis Delta (NOT weighted average)

Formula:
    hybrid_score = jarvis_score + ophis_delta
    where ophis_delta is bounded [-0.75, +0.75]

v2.1 FIX (Feb 11, 2026):
- jarvis_score_before_ophis now uses SAVANT engine scoring (same as production)
- Fixes A/B comparison bug where hybrid used simplified gematria logic
- Now includes: REDUCTION, POWER_NUMBER, TESLA_REDUCTION, Goldilocks Zone
- Guarantees: when ophis_delta=0, hybrid.jarvis_before == savant.jarvis_rs

MSRF is a CORE COMPONENT of this engine (not a post-base boost).
- Ophis Z-scan produces Z-values from matchup date temporal analysis
- Win dates are DEFERRED to Phase 2 (currently uses matchup_date only)
- MSRF contribution is clamped to JARVIS_MSRF_COMPONENT_CAP (2.0)
- Ophis raw [4.5, 6.5] maps to delta [-0.75, +0.75] centered at 5.5

Output: jarvis_score (0-10) with Jarvis as primary, Ophis as modifier
Payload fields:
- jarvis_rs (final hybrid score)
- jarvis_score_before_ophis (pure Jarvis - NOW matches savant!)
- ophis_raw, ophis_delta, ophis_delta_cap
- msrf_component, msrf_status = "IN_JARVIS"
- blend_type = "JARVIS_PRIMARY_OPHIS_DELTA"
- savant_version (audit trail for savant scoring used)

CRITICAL: Post-base msrf_boost is ALWAYS 0.0 - MSRF lives ONLY here.
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional, List
import logging
import math

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# v2.0 Delta model constants (NOT weighted average)
OPHIS_NEUTRAL = 5.5        # Center point where delta = 0
OPHIS_MIN = 4.5            # Minimum Ophis raw score
OPHIS_MAX = 6.5            # Maximum Ophis raw score
OPHIS_DELTA_CAP = 0.75     # Maximum adjustment ±0.75

# MSRF component cap inside Jarvis (prevents MSRF from dominating)
JARVIS_MSRF_COMPONENT_CAP = 2.0

# Version string
VERSION = "JARVIS_OPHIS_HYBRID_v2.1"

# Ophis mathematical constants
OPH_PI = 3.141592653589793
OPH_PHI = 1.618033988749895
OPH_CRV = 2.618033988749895   # phi^2 (curved growth)
OPH_HEP = 7.0                 # Heptagon constant

# MSRF sacred number sets (from signals/msrf_resonance.py)
MSRF_NORMAL = {
    12, 21, 24, 36, 40, 42, 48, 49, 51, 52, 54, 56, 59, 60, 63, 66, 70, 71, 72, 74,
    76, 77, 80, 84, 88, 90, 96, 98, 104, 105, 108, 110, 114, 116, 119, 120, 126, 129,
    132, 133, 135, 138, 140, 144, 147, 153, 154, 162, 168, 176, 180, 182, 186, 189,
    196, 204, 207, 210, 216, 218, 222, 223, 226, 231, 234, 238, 252, 253, 255, 259,
    260, 264, 270, 276, 279, 280, 286, 288, 294, 297, 301, 306, 308, 312, 315, 324,
    330, 336, 343, 351, 354, 360, 363, 364, 365, 372, 378, 385, 390, 394, 396, 405,
    414, 420, 432, 433, 434, 441, 444, 447, 453, 459, 460, 463, 468, 476, 480, 490,
    493, 495, 504, 509, 520, 525, 526, 531, 534, 539, 540, 544, 552, 555, 558, 563,
    565, 567, 572, 573, 576, 582, 588, 591, 594, 600, 612, 618, 621, 630, 640, 648,
    657, 660, 666, 669, 670, 672, 674, 675, 679, 681, 686, 690, 691, 693, 701, 702,
    708, 720, 726, 728, 730, 732, 735, 744, 756, 765, 770, 774, 777, 780, 789, 791,
    792, 800, 801, 807, 810, 816, 819, 828, 831, 840, 846, 855, 861, 864, 866, 868,
    882, 888, 918, 920, 930, 936, 945, 952, 954, 960, 966, 972, 980, 990, 1000, 1008,
    2178,  # THE IMMORTAL
}

MSRF_IMPORTANT = {
    138, 144, 207, 210, 216, 414, 432, 552, 612, 618, 621, 630, 720, 777, 828, 864, 888,
    936, 945, 990, 1008, 1080, 1116, 1224, 1260, 1332, 1440, 1512, 1620, 1656, 1728, 1800,
    1944, 2016, 2070, 2160, 2178, 2520,
}

# Jarvis sacred triggers (gematria)
JARVIS_TRIGGERS = {
    2178: {"name": "THE IMMORTAL", "boost": 3.5, "tier": "LEGENDARY"},
    201: {"name": "THE ORDER", "boost": 2.5, "tier": "HIGH"},
    33: {"name": "THE MASTER", "boost": 2.0, "tier": "HIGH"},
    93: {"name": "THE WILL", "boost": 2.0, "tier": "HIGH"},
    322: {"name": "THE SOCIETY", "boost": 2.0, "tier": "HIGH"},
    666: {"name": "THE BEAST", "boost": 1.5, "tier": "MEDIUM"},
    888: {"name": "JESUS", "boost": 1.5, "tier": "MEDIUM"},
    369: {"name": "TESLA KEY", "boost": 1.5, "tier": "MEDIUM"},
    1656: {"name": "THE PHOENIX", "boost": 2.0, "tier": "HIGH"},
    552: {"name": "PHOENIX FRAGMENT", "boost": 1.5, "tier": "MEDIUM"},
    138: {"name": "PLASMA CYCLE", "boost": 1.5, "tier": "MEDIUM"},
}

# Jarvis baseline
JARVIS_BASELINE = 4.5

# v2.1: TRIGGER_CONTRIBUTIONS - MUST match live_data_router.py exactly!
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

# Simple gematria tables
SIMPLE_GEMATRIA = {chr(i): i - 96 for i in range(97, 123)}  # a=1, b=2, etc.


# =============================================================================
# OPHIS Z-SCAN (Temporal Analysis)
# =============================================================================

def _ophis_round(n: float) -> int:
    """Round to nearest integer."""
    return round(n)


def _ophis_flip(n: int) -> int:
    """Reverse digits of a number."""
    if n == 0:
        return 0
    return int(str(abs(n))[::-1])


def _score_z_value(z: float) -> float:
    """Score a Z-value against MSRF sacred number sets."""
    z_int = int(_ophis_round(z))

    # Check against sacred sets
    if z_int in MSRF_IMPORTANT:
        return 2.0  # Important sacred number
    if z_int in MSRF_NORMAL:
        return 1.0  # Normal resonant number

    # Check flipped value
    z_flipped = _ophis_flip(z_int)
    if z_flipped in MSRF_IMPORTANT:
        return 1.5
    if z_flipped in MSRF_NORMAL:
        return 0.75

    return 0.0


def score_msrf_from_z_values(z_values: List[float]) -> Dict[str, Any]:
    """
    Score MSRF contribution from Ophis Z-values.

    This implements the MSRF scoring that was previously a post-base boost,
    now integrated INTO the Jarvis engine.

    Args:
        z_values: List of Z-values from Ophis temporal analysis

    Returns:
        Dict with raw_score, clamped_score, and hit details
    """
    if not z_values:
        return {
            "raw_score": 0.0,
            "clamped_score": 0.0,
            "hits": [],
            "reason": "NO_Z_VALUES",
        }

    total_score = 0.0
    hits = []

    for z in z_values:
        score = _score_z_value(z)
        if score > 0:
            total_score += score
            hits.append({
                "z_value": round(z, 2),
                "z_int": int(_ophis_round(z)),
                "score": score,
                "is_important": int(_ophis_round(z)) in MSRF_IMPORTANT,
            })

    # Clamp to JARVIS_MSRF_COMPONENT_CAP
    clamped_score = min(total_score, JARVIS_MSRF_COMPONENT_CAP)

    return {
        "raw_score": round(total_score, 4),
        "clamped_score": round(clamped_score, 4),
        "hits": hits[:5],  # Top 5 for brevity
        "hit_count": len(hits),
        "was_clamped": total_score > JARVIS_MSRF_COMPONENT_CAP,
        "reason": f"MSRF_HIT_{len(hits)}" if hits else "MSRF_NO_HIT",
    }


def generate_z_values_from_date(matchup_date: date, home_team: str, away_team: str) -> List[float]:
    """
    Generate Z-values from matchup date using Ophis operations.

    Uses the date's temporal properties to generate mathematically
    significant intervals that are then scored against MSRF sets.
    """
    if matchup_date is None:
        return []

    # Base intervals from date
    day_of_year = matchup_date.timetuple().tm_yday
    days_from_epoch = (matchup_date - date(2000, 1, 1)).days

    # Generate Z-values using Ophis operations
    z_values = []

    # Direct transformations
    z_values.append(float(day_of_year))
    z_values.append(float(days_from_epoch % 1000))

    # Phi transformations
    z_values.append(day_of_year * OPH_PHI)
    z_values.append(day_of_year / OPH_PHI)

    # Pi transformations
    z_values.append(day_of_year * OPH_PI / 2)
    z_values.append(days_from_epoch / OPH_PI)

    # Curved growth (phi^2)
    z_values.append(day_of_year / OPH_CRV)

    # Heptagon constant
    z_values.append(day_of_year * OPH_HEP / 10)

    # Flip operations
    z_values.append(float(_ophis_flip(day_of_year)))

    # Team-derived Z (simple hash)
    team_sum = sum(SIMPLE_GEMATRIA.get(c, 0) for c in (home_team + away_team).lower().replace(" ", ""))
    z_values.append(float(team_sum))
    z_values.append(team_sum * OPH_PHI / 10)

    return [z for z in z_values if 0 < z < 10000]  # Filter valid range


# =============================================================================
# JARVIS GEMATRIA SCORING
# =============================================================================

def calculate_gematria(text: str) -> int:
    """Calculate simple gematria value for text."""
    return sum(SIMPLE_GEMATRIA.get(c, 0) for c in text.lower().replace(" ", ""))


def check_jarvis_triggers(gematria_value: int) -> List[Dict[str, Any]]:
    """Check if a gematria value triggers any sacred numbers."""
    triggers_hit = []

    # Direct match
    if gematria_value in JARVIS_TRIGGERS:
        trigger = JARVIS_TRIGGERS[gematria_value]
        triggers_hit.append({
            "number": gematria_value,
            "match_type": "DIRECT",
            "name": trigger["name"],
            "boost": trigger["boost"],
            "tier": trigger["tier"],
        })

    # Check digit sum reduction for master numbers
    digit_sum = sum(int(d) for d in str(gematria_value))
    if digit_sum in [11, 22, 33]:
        if 33 in JARVIS_TRIGGERS:
            trigger = JARVIS_TRIGGERS[33]
            triggers_hit.append({
                "number": digit_sum,
                "match_type": "REDUCTION",
                "name": f"MASTER_{digit_sum}",
                "boost": trigger["boost"] * 0.5,  # Half boost for reduction
                "tier": "MEDIUM",
            })

    return triggers_hit


def calculate_jarvis_gematria_score(
    home_team: str,
    away_team: str,
    player_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate Jarvis gematria-based score.

    Computes gematria for teams/players and checks for sacred trigger hits.
    """
    # Calculate gematria values
    home_gem = calculate_gematria(home_team)
    away_gem = calculate_gematria(away_team)
    combined_gem = home_gem + away_gem

    player_gem = 0
    if player_name:
        player_gem = calculate_gematria(player_name)
        combined_gem += player_gem

    # Check triggers
    all_triggers = []
    all_triggers.extend(check_jarvis_triggers(combined_gem))
    all_triggers.extend(check_jarvis_triggers(home_gem))
    all_triggers.extend(check_jarvis_triggers(away_gem))
    if player_gem:
        all_triggers.extend(check_jarvis_triggers(player_gem))

    # Calculate boost from triggers
    total_boost = sum(t["boost"] for t in all_triggers)

    # Detect IMMORTAL (2178)
    immortal_detected = any(t["number"] == 2178 for t in all_triggers)

    return {
        "gematria": {
            "home": home_gem,
            "away": away_gem,
            "player": player_gem,
            "combined": combined_gem,
        },
        "triggers_hit": all_triggers,
        "total_boost": round(total_boost, 2),
        "immortal_detected": immortal_detected,
    }


# =============================================================================
# v2.1: SAVANT ENGINE SCORING (SAME AS live_data_router.py)
# =============================================================================

def _calculate_savant_jarvis_score(
    home_team: str,
    away_team: str,
    player_name: Optional[str] = None,
    spread: float = 0.0,
    total: float = 0.0,
    prop_line: float = 0.0,
    game_str: str = "",
    matchup_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Calculate Jarvis score using the SAME logic as savant engine.

    v2.1 FIX: This ensures hybrid's jarvis_before matches savant's jarvis_rs.

    Uses lazy import to avoid circular dependency with live_data_router.py.
    """
    # Lazy import savant engine to avoid circular dependency
    try:
        from jarvis_savant_engine import get_jarvis_engine
        jarvis_engine = get_jarvis_engine()
    except ImportError:
        jarvis_engine = None
        logger.warning("JarvisSavantEngine not available, falling back to simplified scoring")

    # Build matchup string if not provided
    if not game_str and home_team and away_team:
        game_str = f"{away_team} @ {home_team}"
        if player_name:
            game_str = f"{player_name} {game_str}"

    # Track inputs used
    jarvis_inputs_used = {
        "matchup_str": game_str if game_str else None,
        "date_et": matchup_date.isoformat() if matchup_date else None,
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
        return {
            "jarvis_rs": None,
            "jarvis_baseline": None,
            "jarvis_trigger_contribs": {},
            "jarvis_active": False,
            "jarvis_hits_count": 0,
            "jarvis_triggers_hit": [],
            "jarvis_reasons": ["Inputs missing - cannot run"],
            "jarvis_fail_reasons": ["Missing critical inputs (matchup_str or teams)"],
            "jarvis_no_trigger_reason": "INPUTS_MISSING",
            "jarvis_inputs_used": jarvis_inputs_used,
            "immortal_detected": False,
            "version": "JARVIS_SAVANT_v11.08",
            "blend_type": "SAVANT",
        }

    # Initialize scoring
    jarvis_triggers_hit = []
    jarvis_trigger_contribs = {}
    jarvis_fail_reasons = []
    jarvis_no_trigger_reason = None
    immortal_detected = False
    total_trigger_contrib = 0.0
    gematria_contrib = 0.0
    goldilocks_contrib = 0.0
    trigger_count = 0

    if jarvis_engine:
        # 1. Sacred Triggers - ADDITIVE contributions (SAME as live_data_router.py)
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
            gematria = jarvis_engine.calculate_gematria_signal(player_name, home_team, away_team or "")
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
        # Fallback: use simplified gematria (when savant engine unavailable)
        fallback_result = calculate_jarvis_gematria_score(home_team, away_team, player_name)
        total_trigger_contrib = fallback_result.get("total_boost", 0.0)
        immortal_detected = fallback_result.get("immortal_detected", False)
        for trig in fallback_result.get("triggers_hit", []):
            jarvis_triggers_hit.append(trig)
            jarvis_trigger_contribs[trig["name"]] = trig["boost"]

    # Calculate final jarvis_rs = baseline + all contributions
    jarvis_rs = JARVIS_BASELINE + total_trigger_contrib + gematria_contrib + goldilocks_contrib

    # Cap at 0-10 range
    jarvis_rs = max(0.0, min(10.0, jarvis_rs))

    # Determine jarvis_active and build reasons
    jarvis_hits_count = len(jarvis_triggers_hit)
    has_any_contrib = total_trigger_contrib > 0 or gematria_contrib > 0 or goldilocks_contrib > 0

    if has_any_contrib:
        jarvis_reasons = list(jarvis_trigger_contribs.keys())
        jarvis_no_trigger_reason = None
    else:
        jarvis_reasons = [f"Baseline {JARVIS_BASELINE} (no triggers)"]
        jarvis_no_trigger_reason = "NO_TRIGGER_BASELINE"
        jarvis_fail_reasons.append(f"No triggers fired - baseline {JARVIS_BASELINE}")

    return {
        "jarvis_rs": round(jarvis_rs, 2),
        "jarvis_baseline": JARVIS_BASELINE,
        "jarvis_trigger_contribs": jarvis_trigger_contribs,
        "jarvis_active": True,
        "jarvis_hits_count": jarvis_hits_count,
        "jarvis_triggers_hit": jarvis_triggers_hit,
        "jarvis_reasons": jarvis_reasons,
        "jarvis_fail_reasons": jarvis_fail_reasons,
        "jarvis_no_trigger_reason": jarvis_no_trigger_reason,
        "jarvis_inputs_used": jarvis_inputs_used,
        "immortal_detected": immortal_detected,
        "version": "JARVIS_SAVANT_v11.08",
        "blend_type": "SAVANT",
    }


# =============================================================================
# MAIN HYBRID CALCULATION
# =============================================================================

def calculate_hybrid_jarvis_score(
    home_team: str,
    away_team: str,
    spread: Optional[float] = None,
    odds: Optional[int] = None,
    public_pct: Optional[float] = None,
    sport: str = "NBA",
    matchup_date: Optional[date] = None,
    player_name: Optional[str] = None,
    total: Optional[float] = None,
    prop_line: Optional[float] = None,
    game_str: str = "",
) -> Dict[str, Any]:
    """
    Calculate hybrid Jarvis-Ophis score with MSRF integrated.

    v2.0 Blend: Jarvis Primary + Bounded Ophis Delta (NOT weighted average)

    Formula:
        hybrid_score = jarvis_score + ophis_delta
        where ophis_delta = clamp((ophis_raw - 5.5) / 1.0 * 0.75, -0.75, +0.75)

    This is THE Engine 4 implementation for the 4-engine scoring architecture.
    MSRF contribution is INSIDE this engine, not a post-base boost.

    Args:
        home_team: Home team name
        away_team: Away team name
        spread: Game spread (optional)
        odds: American odds (optional)
        public_pct: Public betting percentage (optional)
        sport: Sport code
        matchup_date: Date of the matchup
        player_name: Player name for props (optional)
        total: Game total (optional)
        prop_line: Prop line (optional)
        game_str: Matchup string for gematria (optional)

    Returns:
        Dict with jarvis_rs (0-10), Jarvis + Ophis delta components, and full audit trail
    """
    # Handle missing inputs
    if not home_team and not away_team:
        return {
            # Required output fields (same as savant)
            "jarvis_rs": None,
            "jarvis_baseline": JARVIS_BASELINE,
            "jarvis_trigger_contribs": {},
            "jarvis_active": False,
            "jarvis_hits_count": 0,
            "jarvis_triggers_hit": [],
            "jarvis_reasons": [],
            "jarvis_fail_reasons": ["MISSING_TEAMS"],
            "jarvis_no_trigger_reason": "INPUTS_MISSING",
            "jarvis_inputs_used": {},
            "immortal_detected": False,
            # Version and blend info
            "version": VERSION,
            "blend_type": "JARVIS_PRIMARY_OPHIS_DELTA",
            "whisper_tier": "SILENT",
            # v2.0 Delta model transparency fields
            "jarvis_score_before_ophis": None,
            "jarvis_component": None,
            "ophis_raw": None,
            "ophis_delta": 0.0,
            "ophis_delta_cap": OPHIS_DELTA_CAP,
            "ophis_component": None,
            "msrf_component": 0.0,
            "jarvis_msrf_component": 0.0,
            "jarvis_msrf_component_raw": 0.0,
            "msrf_status": "IN_JARVIS",
            "gematria": {},
        }

    # Default matchup date to today
    if matchup_date is None:
        matchup_date = date.today()

    # =========================================================================
    # OPHIS COMPONENT (Delta Modifier)
    # =========================================================================
    # Generate Z-values and score against MSRF sets
    z_values = generate_z_values_from_date(matchup_date, home_team, away_team)
    msrf_result = score_msrf_from_z_values(z_values)

    # MSRF component (raw and clamped)
    msrf_component_raw = msrf_result["raw_score"]
    msrf_component = msrf_result["clamped_score"]

    # Ophis raw: JARVIS_BASELINE + MSRF component (range: [4.5, 6.5])
    ophis_raw = JARVIS_BASELINE + msrf_component

    # =========================================================================
    # JARVIS COMPONENT (Primary Scorer) - v2.1: Uses SAVANT engine for base
    # =========================================================================
    # v2.1 FIX: Call savant scoring to get the TRUE jarvis_score_before_ophis
    # This ensures hybrid's base matches what savant would produce.
    savant_result = _calculate_savant_jarvis_score(
        home_team=home_team,
        away_team=away_team,
        player_name=player_name,
        spread=spread or 0.0,
        total=total or 0.0,
        prop_line=prop_line or 0.0,
        game_str=game_str,
        matchup_date=matchup_date,
    )

    # Extract savant's jarvis_rs as our base score
    jarvis_score_before_ophis = savant_result.get("jarvis_rs") or JARVIS_BASELINE
    immortal_detected = savant_result.get("immortal_detected", False)

    # Propagate savant's trigger contributions for transparency
    jarvis_trigger_contribs = savant_result.get("jarvis_trigger_contribs", {})

    # =========================================================================
    # v2.0 BLEND: Jarvis Primary + Bounded Ophis Delta (NOT weighted average)
    # =========================================================================
    # Map ophis_raw [4.5, 6.5] to delta [-0.75, +0.75] centered at 5.5
    # ophis_raw = 5.5 → delta = 0 (neutral)
    # ophis_raw = 6.5 → delta = +0.75 (max boost)
    # ophis_raw = 4.5 → delta = -0.75 (max penalty)
    ophis_delta_unbounded = ((ophis_raw - OPHIS_NEUTRAL) / (OPHIS_MAX - OPHIS_NEUTRAL)) * OPHIS_DELTA_CAP
    ophis_delta = max(-OPHIS_DELTA_CAP, min(OPHIS_DELTA_CAP, ophis_delta_unbounded))

    # Final hybrid score = Jarvis + bounded delta
    jarvis_rs = jarvis_score_before_ophis + ophis_delta
    jarvis_rs = max(0.0, min(10.0, jarvis_rs))  # Clamp to 0-10

    # =========================================================================
    # COLLECT TRIGGERS AND REASONS - v2.1: Use savant_result
    # =========================================================================
    # Start with savant's triggers
    triggers_hit = list(savant_result.get("jarvis_triggers_hit", []))

    # Add MSRF Z-scan hits
    if msrf_result["hits"]:
        for hit in msrf_result["hits"]:
            triggers_hit.append({
                "number": hit["z_int"],
                "match_type": "MSRF_Z_SCAN",
                "name": "MSRF_RESONANCE",
                "boost": hit["score"],
                "tier": "HIGH" if hit["is_important"] else "MEDIUM",
            })

    # Build reasons from savant + MSRF
    reasons = list(savant_result.get("jarvis_reasons", []))
    if immortal_detected:
        if "IMMORTAL_2178_DETECTED" not in reasons:
            reasons.insert(0, "IMMORTAL_2178_DETECTED")
    if msrf_component > 0:
        reasons.append(f"MSRF_COMPONENT_{round(msrf_component, 2)}")

    # Determine whisper tier
    if jarvis_rs >= 8.0:
        whisper_tier = "LEGENDARY"
    elif jarvis_rs >= 7.0:
        whisper_tier = "STRONG"
    elif jarvis_rs >= 6.0:
        whisper_tier = "MODERATE"
    elif jarvis_rs >= 5.0:
        whisper_tier = "MILD"
    else:
        whisper_tier = "SILENT"

    # =========================================================================
    # BUILD OUTPUT (v2.0 schema with required fields + hybrid additional fields)
    # =========================================================================
    return {
        # Required output fields (same as savant - schema contract)
        "jarvis_rs": round(jarvis_rs, 2),
        "jarvis_baseline": JARVIS_BASELINE,
        "jarvis_trigger_contribs": jarvis_trigger_contribs,
        "jarvis_active": True,
        "jarvis_hits_count": len(triggers_hit),
        "jarvis_triggers_hit": triggers_hit[:10],  # Top 10
        "jarvis_reasons": reasons,
        "jarvis_fail_reasons": savant_result.get("jarvis_fail_reasons", []),
        "jarvis_no_trigger_reason": savant_result.get("jarvis_no_trigger_reason"),
        "jarvis_inputs_used": {
            "home_team": home_team,
            "away_team": away_team,
            "player_name": player_name,
            "spread": spread,
            "total": total,
            "prop_line": prop_line,
            "odds": odds,
            "public_pct": public_pct,
            "sport": sport,
            "matchup_date": matchup_date.isoformat() if matchup_date else None,
            "game_str": game_str,
        },
        "immortal_detected": immortal_detected,

        # Version and blend info
        "version": VERSION,
        "blend_type": "JARVIS_PRIMARY_OPHIS_DELTA",
        "whisper_tier": whisper_tier,

        # v2.0 Delta model transparency fields (hybrid additional)
        "jarvis_score_before_ophis": round(jarvis_score_before_ophis, 4),
        "jarvis_component": round(jarvis_score_before_ophis, 4),  # Alias for clarity
        "ophis_raw": round(ophis_raw, 4),
        "ophis_delta": round(ophis_delta, 4),
        "ophis_delta_cap": OPHIS_DELTA_CAP,
        "ophis_component": round(ophis_raw, 4),  # Alias for clarity

        # MSRF components (CRITICAL - must be in payload)
        "msrf_component": round(msrf_component, 4),
        "jarvis_msrf_component": round(msrf_component, 4),  # Alias
        "jarvis_msrf_component_raw": round(msrf_component_raw, 4),
        "msrf_status": "IN_JARVIS",  # MSRF is inside Jarvis, not post-base

        # Gematria details (simple values for debugging)
        "gematria": {
            "home": calculate_gematria(home_team),
            "away": calculate_gematria(away_team),
            "player": calculate_gematria(player_name) if player_name else 0,
            "combined": calculate_gematria(home_team) + calculate_gematria(away_team) + (calculate_gematria(player_name) if player_name else 0),
        },
        # v2.1: Savant version for audit trail
        "savant_version": savant_result.get("version", "UNKNOWN"),

        # MSRF Z-scan details
        "msrf_z_values": z_values[:5] if z_values else [],
        "msrf_hit_count": msrf_result["hit_count"],
        "msrf_was_clamped": msrf_result["was_clamped"],
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Constants (v2.1 delta model)
    "OPHIS_NEUTRAL",
    "OPHIS_MIN",
    "OPHIS_MAX",
    "OPHIS_DELTA_CAP",
    "JARVIS_MSRF_COMPONENT_CAP",
    "JARVIS_BASELINE",
    "JARVIS_TRIGGERS",
    "MSRF_NORMAL",
    "MSRF_IMPORTANT",
    "VERSION",
    # Functions
    "calculate_hybrid_jarvis_score",
    "score_msrf_from_z_values",
    "generate_z_values_from_date",
    "calculate_jarvis_gematria_score",
    "calculate_gematria",
    "check_jarvis_triggers",
]
