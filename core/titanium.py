"""
Titanium Rule (FIX 2)

RULE: titanium=true ONLY when >= 3 of 4 engines are >= 8.0

Single source of truth - NO duplicate logic allowed.
"""

from core.scoring_contract import TITANIUM_RULE

from typing import Dict, Tuple, List, Any, Optional


def compute_titanium_flag(
    ai_score: float,
    research_score: float,
    esoteric_score: float,
    jarvis_score: float,
    threshold: float = TITANIUM_RULE["threshold"]
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
    titanium = hits_count >= TITANIUM_RULE["min_engines_ge_threshold"]

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


def evaluate_titanium(
    ai_score: float,
    research_score: float,
    esoteric_score: float,
    jarvis_score: float,
    final_score: Optional[float] = None,
    threshold: float = TITANIUM_RULE["threshold"],
    min_final_score: Optional[float] = None,
) -> Tuple[bool, str, List[str]]:
    """
    Unified Titanium evaluation helper.

    Context is intentionally excluded: Titanium is STRICT 3-of-4 engines only.

    Args:
        ai_score, research_score, esoteric_score, jarvis_score: 0-10 engine scores
        final_score: optional final score (for prerequisite checks)
        threshold: engine threshold (default 8.0)
        min_final_score: optional minimum final score prerequisite

    Returns:
        (triggered, explanation, qualifying_engines)
    """
    if min_final_score is None:
        try:
            from tiering import TITANIUM_FINAL_SCORE_MIN
            min_final_score = TITANIUM_FINAL_SCORE_MIN
        except Exception:
            min_final_score = None

    if min_final_score is not None and final_score is not None and final_score < min_final_score:
        return False, f"Titanium: Final score {final_score:.1f} < {min_final_score} (prerequisite not met)", []

    titanium_triggered, diagnostics = compute_titanium_flag(
        ai_score=ai_score,
        research_score=research_score,
        esoteric_score=esoteric_score,
        jarvis_score=jarvis_score,
        threshold=threshold,
    )
    qualifying_engines = diagnostics.get("titanium_engines_hit", [])
    explanation = diagnostics.get("titanium_reason", "")
    return titanium_triggered, explanation, qualifying_engines
