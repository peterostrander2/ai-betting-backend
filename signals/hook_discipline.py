"""
Hook Discipline Signal - Key Number Management
==============================================

Post-scoring filter that applies penalties for bad hooks and bonuses for key numbers.

NFL Key Numbers (% of games landing on these margins):
- 3: ~15% of games
- 7: ~9% of games
- 10: ~5% of games
- 14: ~3% of games

Bad Hooks (AVOID these):
- -3.5: Worst hook in football - crosses the most common margin
- -7.5: Second worst - crosses second most common margin
- -6.5: Crosses 7
- -10.5: Crosses 10

NBA Key Numbers:
- 5, 7 (less impactful than NFL)

Adjustments are bounded and auditable per CLAUDE.md guardrails.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================
# CONSTANTS (Single Source of Truth)
# ============================================

# NFL: Percentage of games landing on each margin (historical data)
NFL_KEY_NUMBER_FREQUENCY = {
    3: 0.148,   # ~15% of games
    7: 0.092,   # ~9% of games
    6: 0.056,   # ~6% of games
    10: 0.051,  # ~5% of games
    14: 0.034,  # ~3% of games
    4: 0.032,
    17: 0.031,
    13: 0.028,
    1: 0.027,
    21: 0.026,
}

# Bad hooks and their penalties (negative = penalize the pick)
# v20.3 Codex refinement: worst hook capped at -0.25 (was -0.35)
NFL_BAD_HOOKS = {
    3.5: -0.25,   # Worst hook - crosses 3 (capped at HOOK_PENALTY_CAP)
    7.5: -0.20,   # Second worst - crosses 7
    6.5: -0.15,   # Crosses 7
    10.5: -0.10,  # Crosses 10
    13.5: -0.05,  # Crosses 14
    14.5: -0.05,  # Crosses 14
}

# Good positions (on key numbers for favorites)
NFL_KEY_NUMBER_BONUS = {
    3: 0.15,   # On 3 is great for favorite
    7: 0.10,   # On 7 is good
    10: 0.05,  # On 10 is okay
}

# NBA has less key number significance
NBA_KEY_NUMBERS = {5, 7}
NBA_BAD_HOOKS = {
    5.5: -0.10,
    7.5: -0.10,
}

# Caps (INVARIANT: bounded adjustments)
# v20.3 Codex refinement: -0.25 penalty cap (was -0.35)
# Reasoning: -0.35 was too aggressive; -0.25 keeps hook discipline meaningful
# without over-penalizing. Bonus cap stays at 0.15 for key number favorites.
HOOK_PENALTY_CAP = -0.25  # Max penalty (Codex recommendation)
HOOK_BONUS_CAP = 0.15     # Max bonus


@dataclass
class HookAnalysis:
    """Result of hook discipline analysis."""
    adjustment: float          # Bounded adjustment to apply
    is_bad_hook: bool         # True if at a bad hook
    is_key_number: bool       # True if on a favorable key number
    hook_value: float         # The actual hook/line value
    reasons: List[str]        # Audit trail
    warnings: List[str]       # User-facing warnings


def analyze_hook_discipline(
    line: float,
    sport: str,
    bet_side: str = "favorite",  # "favorite", "underdog", "over", "under"
    bet_type: str = "spread",    # "spread", "total", "prop"
) -> HookAnalysis:
    """
    Analyze if a line is at a bad hook or favorable key number.

    Args:
        line: The spread/total line (e.g., -3.5, 220.5)
        sport: Sport code (NFL, NBA, NHL, MLB, NCAAB)
        bet_side: Which side is being bet
        bet_type: Type of bet (spread, total, prop)

    Returns:
        HookAnalysis with bounded adjustment and audit info
    """
    sport_upper = sport.upper()
    abs_line = abs(line)
    is_half_point = (abs_line % 1) == 0.5
    whole_number = int(abs_line)

    adjustment = 0.0
    is_bad_hook = False
    is_key_number = False
    reasons = []
    warnings = []

    # Only analyze spreads for key number significance
    if bet_type != "spread":
        return HookAnalysis(
            adjustment=0.0,
            is_bad_hook=False,
            is_key_number=False,
            hook_value=abs_line,
            reasons=[f"Hook analysis N/A for {bet_type}"],
            warnings=[]
        )

    # NFL-specific analysis (highest impact)
    if sport_upper == "NFL":
        # Check for bad hooks
        if abs_line in NFL_BAD_HOOKS:
            penalty = NFL_BAD_HOOKS[abs_line]
            adjustment = max(HOOK_PENALTY_CAP, penalty)  # Cap the penalty
            is_bad_hook = True

            # Different warning severity based on hook
            if abs_line == 3.5:
                warnings.append(f"WORST HOOK: -{abs_line} crosses 3 (~15% of games)")
                reasons.append(f"Hook penalty: {adjustment:+.2f} (line at -{abs_line}, worst NFL hook)")
            elif abs_line == 7.5:
                warnings.append(f"Bad hook: -{abs_line} crosses 7 (~9% of games)")
                reasons.append(f"Hook penalty: {adjustment:+.2f} (line at -{abs_line}, crosses key number 7)")
            else:
                warnings.append(f"Unfavorable hook at -{abs_line}")
                reasons.append(f"Hook penalty: {adjustment:+.2f} (line at -{abs_line})")

        # Check for favorable key numbers (for favorites)
        elif not is_half_point and whole_number in NFL_KEY_NUMBER_BONUS:
            if bet_side == "favorite":
                bonus = NFL_KEY_NUMBER_BONUS[whole_number]
                adjustment = min(HOOK_BONUS_CAP, bonus)  # Cap the bonus
                is_key_number = True
                freq_pct = NFL_KEY_NUMBER_FREQUENCY.get(whole_number, 0) * 100
                reasons.append(f"Key number bonus: {adjustment:+.2f} (on {whole_number}, {freq_pct:.1f}% frequency)")
            else:
                # Underdog at key number - slight negative (hook working against)
                adjustment = -0.05
                reasons.append(f"Underdog at key number {whole_number}: {adjustment:+.2f}")

        else:
            reasons.append(f"NFL line at {line}: no key number impact")

    # NBA analysis (less impactful)
    elif sport_upper == "NBA":
        if abs_line in NBA_BAD_HOOKS:
            adjustment = NBA_BAD_HOOKS[abs_line]
            is_bad_hook = True
            warnings.append(f"NBA hook at {abs_line}")
            reasons.append(f"NBA hook penalty: {adjustment:+.2f}")
        else:
            reasons.append(f"NBA line at {line}: minimal hook impact")

    # Other sports - no significant key numbers
    else:
        reasons.append(f"{sport_upper} line at {line}: key numbers N/A")

    return HookAnalysis(
        adjustment=adjustment,
        is_bad_hook=is_bad_hook,
        is_key_number=is_key_number,
        hook_value=abs_line,
        reasons=reasons,
        warnings=warnings
    )


def get_hook_adjustment(
    line: float,
    sport: str,
    bet_side: str = "favorite",
    bet_type: str = "spread",
) -> Tuple[float, List[str]]:
    """
    Convenience function returning just (adjustment, reasons).

    This is the main integration point for live_data_router.py.
    """
    analysis = analyze_hook_discipline(line, sport, bet_side, bet_type)
    return analysis.adjustment, analysis.reasons


# ============================================
# QUICK TEST
# ============================================

if __name__ == "__main__":
    print("Hook Discipline Tests")
    print("=" * 50)

    # NFL bad hooks
    test_cases = [
        (-3.5, "NFL", "favorite", "spread"),   # Worst hook
        (-7.5, "NFL", "favorite", "spread"),   # Second worst
        (-3.0, "NFL", "favorite", "spread"),   # On key number (good)
        (-7.0, "NFL", "favorite", "spread"),   # On key number (good)
        (-3.0, "NFL", "underdog", "spread"),   # Key number but underdog
        (-5.5, "NFL", "favorite", "spread"),   # Neutral
        (-3.5, "NBA", "favorite", "spread"),   # NBA (less impact)
        (220.5, "NBA", "over", "total"),       # Total (N/A)
    ]

    for line, sport, side, bet_type in test_cases:
        analysis = analyze_hook_discipline(line, sport, side, bet_type)
        status = "⚠️ BAD" if analysis.is_bad_hook else ("✅ KEY" if analysis.is_key_number else "—")
        print(f"{sport} {line:+.1f} ({side}/{bet_type}): {status} adj={analysis.adjustment:+.2f}")
        for r in analysis.reasons:
            print(f"    {r}")
        for w in analysis.warnings:
            print(f"    ⚠️ {w}")
        print()
