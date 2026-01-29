"""
Titanium Rule (FIX 2)

RULE: titanium=true ONLY when >= 3 of 4 engines are >= 8.0

Single source of truth - NO duplicate logic allowed.
"""

from typing import Dict, Tuple, List, Any


def compute_titanium_flag(
    ai_score: float,
    research_score: float,
    esoteric_score: float,
    jarvis_score: float,
    threshold: float = 8.0
) -> Tuple[bool, Dict[str, Any]]:
    """
    Compute Titanium flag using 3-of-4 rule.

    Args:
        ai_score: AI engine score (0-10)
        research_score: Research engine score (0-10)
        esoteric_score: Esoteric engine score (0-10)
        jarvis_score: Jarvis engine score (0-10)
        threshold: Minimum score to qualify (default 8.0)

    Returns:
        (titanium_flag, diagnostics)

        titanium_flag: True if >= 3 engines >= threshold
        diagnostics: {
            "titanium": bool,
            "titanium_hits_count": int,
            "titanium_engines_hit": List[str],
            "titanium_reason": str,
            "titanium_threshold": float,
            "engine_scores": Dict[str, float]
        }

    Examples:
        >>> compute_titanium_flag(8.5, 8.2, 8.1, 7.0)
        (True, {"titanium": True, "titanium_hits_count": 3, ...})

        >>> compute_titanium_flag(8.5, 7.0, 6.0, 5.0)
        (False, {"titanium": False, "titanium_hits_count": 1, ...})
    """
    engines = {
        "ai": ai_score,
        "research": research_score,
        "esoteric": esoteric_score,
        "jarvis": jarvis_score
    }

    # Count engines >= threshold
    qualifying = [name for name, score in engines.items() if score >= threshold]
    hits_count = len(qualifying)

    # 3-of-4 rule
    titanium = hits_count >= 3

    # Build diagnostics
    if titanium:
        reason = f"{hits_count}/4 engines >= {threshold} (TITANIUM)"
    else:
        reason = f"Only {hits_count}/4 engines >= {threshold} (need 3+)"

    diagnostics = {
        "titanium": titanium,
        "titanium_hits_count": hits_count,
        "titanium_engines_hit": qualifying,
        "titanium_reason": reason,
        "titanium_threshold": threshold,
        "engine_scores": engines
    }

    return titanium, diagnostics
