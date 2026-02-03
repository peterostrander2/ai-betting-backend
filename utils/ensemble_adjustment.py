from __future__ import annotations

from typing import Tuple, List


def apply_ensemble_adjustment(final_score: float, hit_prob: float) -> Tuple[float, List[str]]:
    """
    Apply ensemble-based adjustment to final_score.

    Rules:
    - hit_prob > 0.60 => +0.5
    - hit_prob < 0.40 => -0.5
    - otherwise => 0.0
    """
    reasons: List[str] = []
    adjusted = final_score
    if hit_prob > 0.60:
        adjusted = min(10.0, final_score + 0.5)
        reasons.append("Ensemble boost: +0.5 (prob > 60%)")
    elif hit_prob < 0.40:
        adjusted = max(0.0, final_score - 0.5)
        reasons.append("Ensemble penalty: -0.5 (prob < 40%)")
    return adjusted, reasons
