"""
Prop Correlation Signal - Rule-Based Player Prop Correlations
==============================================================

v20.3 - Post-scoring filter that adjusts props based on correlated outcomes.

When multiple props from the same game align directionally, this signal
boosts confidence. When they contradict, it reduces confidence.

Examples:
- QB passing yards OVER + WR receiving yards OVER = positive correlation
- RB rushing yards OVER + QB passing yards OVER = negative correlation (game script)
- High total (OVER) + offensive player props OVER = positive correlation

Guardrails (Codex recommendations):
- Cap: ±0.20 max adjustment
- Post-base adjustment (applies to research_score)
- Rule-based only (no ML in v1)
- Must be auditable with explicit reason strings

Integration: Applied to research_score for PROP bets only.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set

logger = logging.getLogger(__name__)

# ============================================
# CONSTANTS (Single Source of Truth)
# ============================================

# Caps (bounded per Codex)
PROP_CORRELATION_CAP = 0.20  # Max adjustment (±0.20)

# Correlation strength levels
CORRELATION_BOOSTS = {
    "STRONG_POSITIVE": 0.20,    # 3+ correlated props align
    "MODERATE_POSITIVE": 0.10,  # 2 correlated props align
    "WEAK_POSITIVE": 0.05,      # 1 correlated prop aligns
    "NEUTRAL": 0.0,             # No correlation found
    "WEAK_NEGATIVE": -0.05,     # 1 contradiction found
    "MODERATE_NEGATIVE": -0.10, # 2 contradictions found
    "STRONG_NEGATIVE": -0.15,   # 3+ contradictions (capped at -0.15, not full -0.20)
}

# ============================================
# CORRELATION RULES (Sport-Specific)
# ============================================

# NFL Correlations: Prop type → List of (correlated_prop, direction)
# direction: "same" = both OVER or both UNDER is good
#            "opposite" = one OVER, one UNDER is good
NFL_PROP_CORRELATIONS = {
    # QB passing correlates with WR/TE receiving
    "player_pass_yds": [
        ("player_reception_yds", "same"),      # QB yards up → WR yards up
        ("player_receptions", "same"),          # QB yards up → WR catches up
        ("player_pass_tds", "same"),            # More yards → more TDs usually
        ("player_rush_yds", "opposite"),        # Pass-heavy → less rushing
    ],
    "player_pass_tds": [
        ("player_reception_yds", "same"),
        ("player_pass_yds", "same"),
        ("player_anytime_td", "same"),          # More TDs → WR TD likely
    ],
    # WR/TE receiving correlates with QB passing
    "player_reception_yds": [
        ("player_pass_yds", "same"),
        ("player_receptions", "same"),
        ("player_rush_yds", "opposite"),        # Pass-heavy game script
    ],
    "player_receptions": [
        ("player_reception_yds", "same"),
        ("player_pass_yds", "same"),
    ],
    # RB rushing has inverse correlation with passing (game script)
    "player_rush_yds": [
        ("player_pass_yds", "opposite"),        # Run-heavy → less passing
        ("player_rush_attempts", "same"),
        ("player_reception_yds", "opposite"),
    ],
    "player_rush_attempts": [
        ("player_rush_yds", "same"),
        ("player_pass_yds", "opposite"),
    ],
    # Rushing TDs correlate with rushing volume
    "player_rush_tds": [
        ("player_rush_yds", "same"),
        ("player_rush_attempts", "same"),
        ("player_anytime_td", "same"),
    ],
    # Anytime TD scorer correlates with volume stats
    "player_anytime_td": [
        ("player_reception_yds", "same"),
        ("player_rush_yds", "same"),
        ("player_pass_tds", "same"),
    ],
}

# NBA Correlations
NBA_PROP_CORRELATIONS = {
    # Points correlate with shots and minutes
    "player_points": [
        ("player_assists", "same"),             # High usage → both up
        ("player_threes", "same"),              # More shots → more 3s
        ("player_pra", "same"),                 # Points + Rebounds + Assists
        ("player_rebounds", "weak_same"),       # Slight positive
    ],
    "player_assists": [
        ("player_points", "same"),              # Ball handler scores too
        ("player_pra", "same"),
    ],
    "player_rebounds": [
        ("player_points", "weak_same"),         # Big men score inside
        ("player_pra", "same"),
        ("player_blocks", "same"),              # Defensive presence
    ],
    "player_threes": [
        ("player_points", "same"),
        ("player_assists", "weak_same"),        # Shooters sometimes facilitate
    ],
    "player_pra": [
        ("player_points", "same"),
        ("player_assists", "same"),
        ("player_rebounds", "same"),
    ],
    "player_steals": [
        ("player_assists", "weak_same"),        # Active hands on both ends
        ("player_points", "weak_same"),         # Transition points
    ],
    "player_blocks": [
        ("player_rebounds", "same"),            # Rim protectors rebound
    ],
}

# MLB Correlations
MLB_PROP_CORRELATIONS = {
    "player_hits": [
        ("player_total_bases", "same"),
        ("player_runs", "same"),
        ("player_rbis", "same"),
    ],
    "player_total_bases": [
        ("player_hits", "same"),
        ("player_home_runs", "same"),
        ("player_runs", "same"),
    ],
    "player_runs": [
        ("player_hits", "same"),
        ("player_total_bases", "same"),
    ],
    "player_rbis": [
        ("player_hits", "same"),
        ("player_total_bases", "same"),
    ],
    "player_home_runs": [
        ("player_total_bases", "same"),
        ("player_rbis", "same"),
    ],
    "player_strikeouts_pitcher": [
        ("player_outs_recorded", "same"),       # Pitcher going deep
        ("player_earned_runs", "opposite"),     # Good pitching → less runs
    ],
}

# NHL Correlations
NHL_PROP_CORRELATIONS = {
    "player_points": [
        ("player_assists", "same"),
        ("player_goals", "same"),
        ("player_shots", "same"),
    ],
    "player_goals": [
        ("player_shots", "same"),
        ("player_points", "same"),
        ("player_assists", "same"),             # Goals and assists correlate (linemates)
    ],
    "player_assists": [
        ("player_points", "same"),
        ("player_goals", "same"),               # Assists and goals correlate
    ],
    "player_shots": [
        ("player_goals", "same"),
        ("player_points", "same"),
    ],
    "player_saves": [
        ("player_goals_against", "opposite"),   # More saves, less goals against
    ],
}

# NCAAB uses same correlations as NBA
NCAAB_PROP_CORRELATIONS = NBA_PROP_CORRELATIONS.copy()

# Master correlation map
SPORT_CORRELATIONS = {
    "NFL": NFL_PROP_CORRELATIONS,
    "NBA": NBA_PROP_CORRELATIONS,
    "MLB": MLB_PROP_CORRELATIONS,
    "NHL": NHL_PROP_CORRELATIONS,
    "NCAAB": NCAAB_PROP_CORRELATIONS,
}


@dataclass
class PropCorrelationResult:
    """Result of prop correlation analysis."""
    adjustment: float                 # Bounded adjustment to apply (±0.20)
    correlation_level: str            # STRONG_POSITIVE, MODERATE_POSITIVE, etc.
    correlations_found: int           # Number of correlated props found
    alignments: int                   # Props that align with our pick
    contradictions: int               # Props that contradict our pick
    correlated_props: List[Dict]      # Details of each correlated prop
    reasons: List[str]                # Audit trail


def _normalize_prop_type(prop_type: str) -> str:
    """Normalize prop type to standard format."""
    if not prop_type:
        return ""

    # Remove common suffixes
    normalized = prop_type.lower().strip()
    for suffix in ["_over_under", "_alternate", "_odds"]:
        normalized = normalized.replace(suffix, "")

    # Map common variations
    variations = {
        "passing_yards": "player_pass_yds",
        "rushing_yards": "player_rush_yds",
        "receiving_yards": "player_reception_yds",
        "pass_yards": "player_pass_yds",
        "rush_yards": "player_rush_yds",
        "recv_yards": "player_reception_yds",
        "points": "player_points",
        "rebounds": "player_rebounds",
        "assists": "player_assists",
        "threes": "player_threes",
        "three_pointers": "player_threes",
        "steals": "player_steals",
        "blocks": "player_blocks",
        "pts_rebs_asts": "player_pra",
        "pra": "player_pra",
    }

    return variations.get(normalized, normalized)


def _get_correlation_rules(sport: str, prop_type: str) -> List[Tuple[str, str]]:
    """Get correlation rules for a prop type in a sport."""
    sport_rules = SPORT_CORRELATIONS.get(sport.upper(), {})
    normalized_type = _normalize_prop_type(prop_type)
    return sport_rules.get(normalized_type, [])


def analyze_prop_correlation(
    sport: str,
    player_name: str,
    prop_type: str,
    pick_side: str,  # "Over" or "Under"
    other_props: List[Dict],  # List of other props in same game
) -> PropCorrelationResult:
    """
    Analyze correlation between a prop pick and other props in the same game.

    Args:
        sport: Sport code (NFL, NBA, etc.)
        player_name: Player name for the prop
        prop_type: Type of prop (player_points, player_pass_yds, etc.)
        pick_side: "Over" or "Under"
        other_props: List of other prop picks in the same game
                     Each should have: player_name, prop_type, side, final_score

    Returns:
        PropCorrelationResult with bounded adjustment and audit info
    """
    reasons = []
    alignments = 0
    contradictions = 0
    correlated_props = []

    # Get correlation rules for this prop type
    rules = _get_correlation_rules(sport, prop_type)

    if not rules:
        return PropCorrelationResult(
            adjustment=0.0,
            correlation_level="NEUTRAL",
            correlations_found=0,
            alignments=0,
            contradictions=0,
            correlated_props=[],
            reasons=[f"No correlation rules for {prop_type} in {sport}"]
        )

    pick_is_over = pick_side.lower() == "over"

    # Check each other prop for correlations
    for other in other_props:
        other_type = _normalize_prop_type(other.get("prop_type", ""))
        other_side = other.get("side", "").lower()
        other_player = other.get("player_name", "")
        other_score = other.get("final_score", 0)

        if not other_type or not other_side:
            continue

        # Check if this other prop is in our correlation rules
        for correlated_type, direction in rules:
            if other_type == correlated_type or correlated_type in other_type:
                other_is_over = other_side == "over"

                # Determine if this is an alignment or contradiction
                if direction == "same":
                    # Same direction = both OVER or both UNDER
                    is_aligned = (pick_is_over == other_is_over)
                elif direction == "opposite":
                    # Opposite direction = one OVER, one UNDER
                    is_aligned = (pick_is_over != other_is_over)
                elif direction == "weak_same":
                    # Weak same - only count as half
                    is_aligned = (pick_is_over == other_is_over)
                else:
                    continue

                # Weight by the other prop's confidence (final_score)
                weight = 1.0
                if other_score >= 8.0:
                    weight = 1.5  # High confidence prop
                elif other_score >= 7.0:
                    weight = 1.0
                elif other_score >= 6.5:
                    weight = 0.5  # Lower confidence
                else:
                    weight = 0.25  # Marginal prop

                if "weak" in direction:
                    weight *= 0.5

                correlated_props.append({
                    "player": other_player,
                    "prop_type": other_type,
                    "side": other_side,
                    "direction": direction,
                    "aligned": is_aligned,
                    "weight": weight,
                    "score": other_score,
                })

                if is_aligned:
                    alignments += weight
                    reasons.append(
                        f"Correlation: {other_player} {other_type} {other_side.upper()} "
                        f"aligns ({direction}) - weight {weight:.1f}"
                    )
                else:
                    contradictions += weight
                    reasons.append(
                        f"Contradiction: {other_player} {other_type} {other_side.upper()} "
                        f"conflicts ({direction}) - weight {weight:.1f}"
                    )

    # Calculate net alignment
    net_alignment = alignments - contradictions

    # Determine correlation level and adjustment
    if net_alignment >= 3.0:
        level = "STRONG_POSITIVE"
    elif net_alignment >= 2.0:
        level = "MODERATE_POSITIVE"
    elif net_alignment >= 1.0:
        level = "WEAK_POSITIVE"
    elif net_alignment <= -3.0:
        level = "STRONG_NEGATIVE"
    elif net_alignment <= -2.0:
        level = "MODERATE_NEGATIVE"
    elif net_alignment <= -1.0:
        level = "WEAK_NEGATIVE"
    else:
        level = "NEUTRAL"

    raw_adjustment = CORRELATION_BOOSTS[level]

    # Cap the adjustment
    adjustment = max(-PROP_CORRELATION_CAP, min(PROP_CORRELATION_CAP, raw_adjustment))

    if adjustment != 0:
        reasons.append(
            f"Prop correlation: {level} (net={net_alignment:.1f}) = {adjustment:+.2f}"
        )
    else:
        reasons.append(f"Prop correlation: {level} (net={net_alignment:.1f}) - no adjustment")

    return PropCorrelationResult(
        adjustment=adjustment,
        correlation_level=level,
        correlations_found=len(correlated_props),
        alignments=int(alignments),
        contradictions=int(contradictions),
        correlated_props=correlated_props,
        reasons=reasons,
    )


def get_prop_correlation_adjustment(
    sport: str,
    player_name: str,
    prop_type: str,
    pick_side: str,
    other_props: List[Dict],
) -> Tuple[float, List[str]]:
    """
    Convenience function returning just (adjustment, reasons).

    This is the main integration point for live_data_router.py.
    """
    result = analyze_prop_correlation(
        sport=sport,
        player_name=player_name,
        prop_type=prop_type,
        pick_side=pick_side,
        other_props=other_props,
    )
    return result.adjustment, result.reasons


# ============================================
# GAME TOTAL CORRELATION
# ============================================

def get_total_correlation_adjustment(
    sport: str,
    game_total: float,
    game_total_side: Optional[str],  # "Over" or "Under" for game total pick, or None
    prop_type: str,
    prop_side: str,  # "Over" or "Under" for this prop
) -> Tuple[float, List[str]]:
    """
    Adjust prop based on game total correlation.

    High-scoring games (OVER) correlate with offensive player props.
    Low-scoring games (UNDER) correlate with defensive stats / lower props.

    Args:
        sport: Sport code
        game_total: The game total line (e.g., 220.5)
        game_total_side: Whether we picked OVER or UNDER on the total, or None if no pick
        prop_type: The prop type being analyzed
        prop_side: The side we picked for this prop

    Returns:
        (adjustment, reasons) tuple
    """
    reasons = []
    adjustment = 0.0

    # Handle None or empty game_total_side
    if not game_total_side:
        return 0.0, ["No game total side picked - no correlation adjustment"]

    # Offensive props that correlate with high-scoring games
    offensive_props = {
        "NFL": ["player_pass_yds", "player_pass_tds", "player_rush_yds",
                "player_reception_yds", "player_receptions", "player_anytime_td"],
        "NBA": ["player_points", "player_assists", "player_threes", "player_pra"],
        "MLB": ["player_hits", "player_total_bases", "player_runs", "player_rbis"],
        "NHL": ["player_points", "player_goals", "player_assists", "player_shots"],
        "NCAAB": ["player_points", "player_assists", "player_threes", "player_pra"],
    }

    # Defensive/pitcher props that correlate with low-scoring games
    defensive_props = {
        "NFL": [],  # Most NFL props are offensive
        "NBA": ["player_blocks", "player_steals"],
        "MLB": ["player_strikeouts_pitcher", "player_outs_recorded"],
        "NHL": ["player_saves"],
        "NCAAB": ["player_blocks", "player_steals"],
    }

    normalized_prop = _normalize_prop_type(prop_type)
    sport_upper = sport.upper()

    is_offensive_prop = normalized_prop in offensive_props.get(sport_upper, [])
    is_defensive_prop = normalized_prop in defensive_props.get(sport_upper, [])

    total_is_over = game_total_side.lower() == "over"
    prop_is_over = prop_side.lower() == "over"

    if is_offensive_prop:
        # Offensive props correlate POSITIVELY with game total
        # High total + offensive OVER = aligned
        if total_is_over and prop_is_over:
            adjustment = 0.10
            reasons.append(f"Game total OVER correlates with {normalized_prop} OVER (+0.10)")
        elif not total_is_over and not prop_is_over:
            adjustment = 0.10
            reasons.append(f"Game total UNDER correlates with {normalized_prop} UNDER (+0.10)")
        elif total_is_over and not prop_is_over:
            adjustment = -0.05
            reasons.append(f"Game total OVER conflicts with {normalized_prop} UNDER (-0.05)")
        elif not total_is_over and prop_is_over:
            adjustment = -0.05
            reasons.append(f"Game total UNDER conflicts with {normalized_prop} OVER (-0.05)")

    elif is_defensive_prop:
        # Defensive props correlate INVERSELY with game total
        # High total + defensive UNDER = aligned (more scoring, less saves/Ks)
        if total_is_over and not prop_is_over:
            adjustment = 0.05
            reasons.append(f"Game total OVER correlates with {normalized_prop} UNDER (+0.05)")
        elif not total_is_over and prop_is_over:
            adjustment = 0.05
            reasons.append(f"Game total UNDER correlates with {normalized_prop} OVER (+0.05)")

    else:
        reasons.append(f"No game total correlation for {normalized_prop}")

    # Cap the adjustment
    adjustment = max(-PROP_CORRELATION_CAP, min(PROP_CORRELATION_CAP, adjustment))

    return adjustment, reasons


# ============================================
# QUICK TEST
# ============================================

if __name__ == "__main__":
    print("Prop Correlation Tests")
    print("=" * 50)
    print(f"Max Adjustment Cap: ±{PROP_CORRELATION_CAP}")
    print()

    # Test case 1: QB + WR correlation (same game, aligned)
    print("Test 1: QB passing + WR receiving (aligned)")
    other_props = [
        {"player_name": "Ja'Marr Chase", "prop_type": "player_reception_yds",
         "side": "Over", "final_score": 7.8},
        {"player_name": "Tee Higgins", "prop_type": "player_receptions",
         "side": "Over", "final_score": 7.2},
    ]
    result = analyze_prop_correlation(
        sport="NFL",
        player_name="Joe Burrow",
        prop_type="player_pass_yds",
        pick_side="Over",
        other_props=other_props,
    )
    print(f"  Level: {result.correlation_level}")
    print(f"  Adjustment: {result.adjustment:+.2f}")
    print(f"  Alignments: {result.alignments}, Contradictions: {result.contradictions}")
    for r in result.reasons:
        print(f"    - {r}")
    print()

    # Test case 2: QB passing + RB rushing (conflicting game script)
    print("Test 2: QB passing OVER + RB rushing OVER (contradicting game script)")
    other_props = [
        {"player_name": "Joe Mixon", "prop_type": "player_rush_yds",
         "side": "Over", "final_score": 7.5},
    ]
    result = analyze_prop_correlation(
        sport="NFL",
        player_name="Joe Burrow",
        prop_type="player_pass_yds",
        pick_side="Over",
        other_props=other_props,
    )
    print(f"  Level: {result.correlation_level}")
    print(f"  Adjustment: {result.adjustment:+.2f}")
    for r in result.reasons:
        print(f"    - {r}")
    print()

    # Test case 3: NBA PRA correlation
    print("Test 3: NBA Points + Assists + PRA (aligned)")
    other_props = [
        {"player_name": "LeBron James", "prop_type": "player_assists",
         "side": "Over", "final_score": 8.2},
        {"player_name": "LeBron James", "prop_type": "player_pra",
         "side": "Over", "final_score": 8.5},
    ]
    result = analyze_prop_correlation(
        sport="NBA",
        player_name="LeBron James",
        prop_type="player_points",
        pick_side="Over",
        other_props=other_props,
    )
    print(f"  Level: {result.correlation_level}")
    print(f"  Adjustment: {result.adjustment:+.2f}")
    for r in result.reasons:
        print(f"    - {r}")
    print()

    # Test case 4: Game total correlation
    print("Test 4: Game Total OVER + Points OVER (aligned)")
    adj, reasons = get_total_correlation_adjustment(
        sport="NBA",
        game_total=230.5,
        game_total_side="Over",
        prop_type="player_points",
        prop_side="Over",
    )
    print(f"  Adjustment: {adj:+.2f}")
    for r in reasons:
        print(f"    - {r}")
    print()

    print("✓ Prop Correlation module working!")
