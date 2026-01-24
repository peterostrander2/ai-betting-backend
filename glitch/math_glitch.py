"""
Glitch Protocol: Math Glitch Module v1.0
========================================
Core mathematical utilities and the Titanium Rule enforcement.

Features:
- JARVIS Sacred Triggers (gematria codes)
- Titanium Rule (3-of-4 modules = Titanium Smash)
- Harmonic Convergence (Math + Magic alignment)
- Power Number Detection
- Tesla Sequence Analysis

Master Audit File: math_glitch.py - CRITICAL PRIORITY
"""

from typing import Dict, Any, List, Tuple, Optional

# =============================================================================
# JARVIS SACRED TRIGGERS
# =============================================================================

JARVIS_TRIGGERS = {
    2178: {
        "name": "THE IMMORTAL",
        "boost": 20,
        "tier": "LEGENDARY",
        "description": "Only number where n^4=reverse AND n^4=66^4. Never collapses.",
        "mathematical": True
    },
    201: {
        "name": "THE ORDER",
        "boost": 12,
        "tier": "HIGH",
        "description": "Jesuit Order gematria. The Event of 201.",
        "mathematical": False
    },
    33: {
        "name": "THE MASTER",
        "boost": 10,
        "tier": "HIGH",
        "description": "Highest master number. Masonic significance.",
        "mathematical": False
    },
    47: {
        "name": "THE AGENT",
        "boost": 8,
        "tier": "MEDIUM",
        "description": "Agent of chaos. Discordian prime. High variance indicator.",
        "mathematical": False
    },
    88: {
        "name": "THE INFINITE",
        "boost": 8,
        "tier": "MEDIUM",
        "description": "Double infinity. Mercury retrograde resonance. Cycle completion.",
        "mathematical": False
    },
    93: {
        "name": "THE WILL",
        "boost": 10,
        "tier": "HIGH",
        "description": "Thelema sacred number. Will and Love.",
        "mathematical": False
    },
    322: {
        "name": "THE SOCIETY",
        "boost": 10,
        "tier": "HIGH",
        "description": "Skull & Bones. Genesis 3:22.",
        "mathematical": False
    }
}

POWER_NUMBERS = [11, 22, 33, 44, 55, 66, 77, 88, 99]
TESLA_NUMBERS = [3, 6, 9]


def check_jarvis_trigger(value: int) -> Dict[str, Any]:
    """
    Check if a value triggers a JARVIS sacred number.

    Returns trigger info if matched, None if not.
    """
    if value in JARVIS_TRIGGERS:
        trigger = JARVIS_TRIGGERS[value]
        return {
            "triggered": True,
            "value": value,
            "name": trigger["name"],
            "boost": trigger["boost"],
            "tier": trigger["tier"],
            "description": trigger["description"],
            "mathematical": trigger["mathematical"]
        }
    return {"triggered": False, "value": value}


def check_power_number(value: int) -> Dict[str, Any]:
    """Check if value is a power number (11, 22, 33, etc.)."""
    if value in POWER_NUMBERS:
        return {
            "is_power": True,
            "value": value,
            "boost": 0.15,
            "reason": f"Power number {value} detected"
        }
    return {"is_power": False, "value": value, "boost": 0.0}


def check_tesla_sequence(values: List[int]) -> Dict[str, Any]:
    """
    Check if values follow Tesla's 3-6-9 pattern.

    Tesla believed these numbers held the key to the universe.
    """
    tesla_count = sum(1 for v in values if v % 3 == 0)
    total = len(values)

    if total == 0:
        return {"available": False}

    tesla_ratio = tesla_count / total

    if tesla_ratio > 0.6:
        return {
            "available": True,
            "tesla_ratio": round(tesla_ratio, 2),
            "signal": "TESLA_DOMINANT",
            "boost": 0.20,
            "reason": f"Tesla sequence dominant ({tesla_ratio:.0%} divisible by 3)"
        }
    elif tesla_ratio < 0.2:
        return {
            "available": True,
            "tesla_ratio": round(tesla_ratio, 2),
            "signal": "ANTI_TESLA",
            "boost": -0.10,
            "reason": f"Anti-Tesla pattern ({tesla_ratio:.0%} divisible by 3)"
        }

    return {
        "available": True,
        "tesla_ratio": round(tesla_ratio, 2),
        "signal": "NEUTRAL",
        "boost": 0.0,
        "reason": "Normal Tesla distribution"
    }


# =============================================================================
# SIMPLE/REVERSE GEMATRIA
# =============================================================================

SIMPLE_GEMATRIA = {chr(i): i - 96 for i in range(97, 123)}  # a=1, b=2, ...
REVERSE_GEMATRIA = {chr(i): 123 - i for i in range(97, 123)}  # a=26, b=25, ...


def calculate_simple_gematria(text: str) -> int:
    """Calculate simple gematria (A=1, B=2, etc.)."""
    text_lower = text.lower().replace(" ", "")
    return sum(SIMPLE_GEMATRIA.get(c, 0) for c in text_lower)


def calculate_reverse_gematria(text: str) -> int:
    """Calculate reverse gematria (A=26, B=25, etc.)."""
    text_lower = text.lower().replace(" ", "")
    return sum(REVERSE_GEMATRIA.get(c, 0) for c in text_lower)


def full_gematria_analysis(text: str) -> Dict[str, Any]:
    """
    Full gematria analysis including simple, reverse, and JARVIS trigger check.
    """
    simple = calculate_simple_gematria(text)
    reverse = calculate_reverse_gematria(text)

    # Check for JARVIS triggers
    triggers_found = []
    for value in [simple, reverse]:
        trigger = check_jarvis_trigger(value)
        if trigger["triggered"]:
            triggers_found.append(trigger)

    # Also check reduced values
    simple_reduced = simple
    while simple_reduced > 99:
        simple_reduced = sum(int(d) for d in str(simple_reduced))

    trigger = check_jarvis_trigger(simple_reduced)
    if trigger["triggered"]:
        triggers_found.append({**trigger, "source": "reduced"})

    total_boost = sum(t["boost"] for t in triggers_found) / 10  # Scale down

    return {
        "available": True,
        "text": text,
        "simple_gematria": simple,
        "reverse_gematria": reverse,
        "reduced": simple_reduced,
        "triggers_found": triggers_found,
        "trigger_count": len(triggers_found),
        "boost": round(min(total_boost, 1.0), 3)  # Cap at 1.0
    }


# =============================================================================
# TITANIUM RULE - 3-of-4 Module Trigger
# =============================================================================

def check_titanium_rule(
    esoteric_fired: List[str],
    physics_fired: List[str],
    hive_mind_fired: List[str],
    market_fired: List[str]
) -> Dict[str, Any]:
    """
    Check if Titanium Rule is triggered.

    TITANIUM RULE: If 3 of 4 Glitch Protocol modules fire signals,
    the pick becomes a "Titanium Smash" - highest confidence.

    Args:
        esoteric_fired: List of fired esoteric module signals
        physics_fired: List of fired physics module signals
        hive_mind_fired: List of fired hive mind module signals
        market_fired: List of fired market module signals

    Returns:
        Dict with titanium status and combined boost
    """
    modules_fired = []

    if esoteric_fired:
        modules_fired.append("ESOTERIC")
    if physics_fired:
        modules_fired.append("PHYSICS")
    if hive_mind_fired:
        modules_fired.append("HIVE_MIND")
    if market_fired:
        modules_fired.append("MARKET")

    titanium_count = len(modules_fired)
    titanium_smash = titanium_count >= 3

    if titanium_smash:
        if titanium_count == 4:
            boost = 1.50
            tier = "PERFECT_TITANIUM"
            reason = "ALL 4 Glitch Protocol modules fired - PERFECT TITANIUM"
        else:
            boost = 1.00
            tier = "TITANIUM_SMASH"
            reason = f"3/4 Glitch Protocol modules fired ({', '.join(modules_fired)})"
    else:
        boost = 0.0
        tier = "STANDARD"
        reason = f"Only {titanium_count}/4 modules fired"

    return {
        "available": True,
        "titanium_smash": titanium_smash,
        "modules_fired": modules_fired,
        "titanium_count": titanium_count,
        "tier": tier,
        "boost": boost,
        "reason": reason,
        "esoteric_signals": esoteric_fired,
        "physics_signals": physics_fired,
        "hive_mind_signals": hive_mind_fired,
        "market_signals": market_fired
    }


# =============================================================================
# HARMONIC CONVERGENCE - Math + Magic Alignment
# =============================================================================

def check_harmonic_convergence(
    ai_score: float,
    esoteric_score: float,
    threshold: float = 8.0
) -> Dict[str, Any]:
    """
    Check for Harmonic Convergence - when both Math (AI) and Magic (Esoteric)
    are highly aligned.

    v10.69: Golden Boost when both scores >= threshold.

    Args:
        ai_score: AI/LSTM model score (0-10 scale)
        esoteric_score: Esoteric signals score (0-10 scale)
        threshold: Minimum score for both to trigger (default 8.0)

    Returns:
        Dict with harmonic status and golden boost
    """
    ai_fires = ai_score >= threshold
    esoteric_fires = esoteric_score >= threshold

    harmonic = ai_fires and esoteric_fires

    if harmonic:
        # Calculate convergence strength
        avg_score = (ai_score + esoteric_score) / 2
        convergence_factor = (avg_score - threshold) / (10 - threshold)
        boost = 0.75 + (convergence_factor * 0.25)  # 0.75 to 1.0

        return {
            "available": True,
            "harmonic_convergence": True,
            "ai_score": round(ai_score, 2),
            "esoteric_score": round(esoteric_score, 2),
            "avg_score": round(avg_score, 2),
            "boost": round(boost, 3),
            "tier": "GOLDEN",
            "reason": f"HARMONIC CONVERGENCE: Math={ai_score:.1f}, Magic={esoteric_score:.1f} (both >= {threshold})"
        }

    return {
        "available": True,
        "harmonic_convergence": False,
        "ai_score": round(ai_score, 2),
        "esoteric_score": round(esoteric_score, 2),
        "boost": 0.0,
        "tier": "STANDARD",
        "reason": f"No convergence: Math={ai_score:.1f}, Magic={esoteric_score:.1f} (need both >= {threshold})"
    }


# =============================================================================
# COMBINED GLITCH SCORE
# =============================================================================

def calculate_glitch_score(
    esoteric_result: Dict[str, Any],
    physics_result: Dict[str, Any],
    hive_mind_result: Dict[str, Any],
    market_result: Dict[str, Any],
    ai_score: float = None,
    esoteric_score: float = None
) -> Dict[str, Any]:
    """
    Calculate combined Glitch Protocol score.

    Aggregates all module boosts and applies Titanium Rule.

    Returns:
        Dict with combined score, tier, and breakdown
    """
    # Extract fired modules
    esoteric_fired = esoteric_result.get("fired_modules", [])
    physics_fired = physics_result.get("fired_modules", [])
    hive_mind_fired = hive_mind_result.get("fired_modules", [])
    market_fired = market_result.get("fired_modules", [])

    # Base boosts from each module
    esoteric_boost = esoteric_result.get("total_boost", 0)
    physics_boost = physics_result.get("total_boost", 0)
    hive_mind_boost = hive_mind_result.get("total_boost", 0)
    market_boost = market_result.get("total_boost", 0)

    base_boost = esoteric_boost + physics_boost + hive_mind_boost + market_boost

    # Check Titanium Rule
    titanium = check_titanium_rule(
        esoteric_fired, physics_fired, hive_mind_fired, market_fired
    )

    # Check Harmonic Convergence (if scores provided)
    harmonic = {"harmonic_convergence": False, "boost": 0}
    if ai_score is not None and esoteric_score is not None:
        harmonic = check_harmonic_convergence(ai_score, esoteric_score)

    # Total boost
    total_boost = base_boost + titanium["boost"] + harmonic.get("boost", 0)

    # Determine tier
    if titanium["tier"] == "PERFECT_TITANIUM":
        tier = "PERFECT_TITANIUM"
    elif titanium["titanium_smash"]:
        tier = "TITANIUM_SMASH"
    elif harmonic.get("harmonic_convergence"):
        tier = "GOLDEN_HARMONIC"
    elif total_boost >= 1.0:
        tier = "STRONG_GLITCH"
    elif total_boost >= 0.5:
        tier = "MODERATE_GLITCH"
    elif total_boost > 0:
        tier = "WEAK_GLITCH"
    else:
        tier = "NO_GLITCH"

    return {
        "available": True,
        "glitch_score": round(total_boost, 3),
        "tier": tier,
        "breakdown": {
            "esoteric": {
                "boost": round(esoteric_boost, 3),
                "fired": esoteric_fired
            },
            "physics": {
                "boost": round(physics_boost, 3),
                "fired": physics_fired
            },
            "hive_mind": {
                "boost": round(hive_mind_boost, 3),
                "fired": hive_mind_fired
            },
            "market": {
                "boost": round(market_boost, 3),
                "fired": market_fired
            }
        },
        "titanium": titanium,
        "harmonic": harmonic,
        "total_modules_fired": (
            len(esoteric_fired) + len(physics_fired) +
            len(hive_mind_fired) + len(market_fired)
        )
    }
