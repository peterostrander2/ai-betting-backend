"""
Contradiction Gate - Prevents both sides of same bet from being returned.

Ensures we never recommend both Over AND Under on the same line,
or both sides of a spread/ML on the same game.

Master Prompt Requirement #11:
- Define unique_key: (sport, date_et, event_id, market, prop_type, player_id/team_id, line)
- If conflict occurs, keep the higher final_score; drop the other; log contradiction_blocked=true
"""
from typing import List, Dict, Tuple, Any
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


def make_unique_key(pick) -> str:
    """
    Create unique key for contradiction detection.

    Key format: {sport}|{date}|{event_id}|{market}|{prop_type}|{player/team}|{line}

    Examples:
    - "NBA|2026-01-28|abc123|PROP|points|LeBron James|25.5"
    - "NBA|2026-01-28|def456|TOTAL||Game|235.5"
    - "NBA|2026-01-28|ghi789|SPREAD||Lakers|-7.5"
    """
    sport = pick.sport.upper()
    date_et = pick.date
    event_id = pick.canonical_event_id or pick.event_id if hasattr(pick, 'event_id') else pick.matchup
    market = (pick.market or pick.pick_type or "").upper()
    prop_type = (pick.prop_type or "").lower()

    # For props: use player name
    # For game picks: use "Game" or team name for spreads/ML
    if pick.player_name:
        subject = pick.player_name
    elif market in ["SPREAD", "MONEYLINE", "ML"]:
        subject = pick.side if pick.side else "Game"
    else:
        subject = "Game"

    line_str = f"{pick.line:.1f}"

    key = f"{sport}|{date_et}|{event_id}|{market}|{prop_type}|{subject}|{line_str}"
    return key


def is_opposite_side(side_a: str, side_b: str, market: str) -> bool:
    """
    Check if two picks are opposite sides of the same bet.

    Returns True if:
    - Total/Prop: One is Over, other is Under
    - Spread/ML: Different teams picked
    """
    if not side_a or not side_b:
        return False

    side_a_upper = side_a.upper()
    side_b_upper = side_b.upper()

    market_upper = market.upper()

    if "TOTAL" in market_upper or "PROP" in market_upper:
        # Over vs Under
        return (side_a_upper == "OVER" and side_b_upper == "UNDER") or \
               (side_a_upper == "UNDER" and side_b_upper == "OVER")
    elif "SPREAD" in market_upper or "MONEYLINE" in market_upper or "ML" in market_upper:
        # Different teams
        return side_a_upper != side_b_upper
    else:
        return False


def detect_contradictions(picks: List[Any]) -> Dict[str, List[Any]]:
    """
    Group picks by unique_key to detect contradictions.

    Returns:
        Dict mapping unique_key -> list of picks with that key
        Only includes keys with 2+ picks (contradictions)
    """
    groups = defaultdict(list)

    for pick in picks:
        key = make_unique_key(pick)
        groups[key].append(pick)

    # Filter to only contradiction groups (2+ picks)
    contradictions = {k: v for k, v in groups.items() if len(v) >= 2}

    return contradictions


def filter_contradictions(picks: List[Any], debug: bool = False) -> Tuple[List[Any], Dict[str, Any]]:
    """
    Filter out contradictory picks, keeping only the highest-scoring pick per unique_key.

    Rules:
    1. Group picks by unique_key
    2. Within each group, check if sides are opposite
    3. If opposite sides exist, keep only the highest final_score
    4. Mark dropped picks with contradiction_blocked=True
    5. Log contradiction details

    Args:
        picks: List of pick objects (PublishedPick or PickOutputSchema)
        debug: If True, include detailed contradiction info in return

    Returns:
        Tuple of (filtered_picks, debug_info)
    """
    if not picks:
        return [], {}

    contradictions = detect_contradictions(picks)

    kept_picks = []
    dropped_picks = []
    contradiction_groups = []

    # Track picks we've already processed to avoid duplicates
    processed_pick_ids = set()

    for pick in picks:
        pick_id = pick.pick_id

        # Skip if already processed
        if pick_id in processed_pick_ids:
            continue

        key = make_unique_key(pick)

        # No contradiction for this key - keep it
        if key not in contradictions:
            kept_picks.append(pick)
            processed_pick_ids.add(pick_id)
            continue

        # Contradiction exists - need to resolve
        group = contradictions[key]

        # Check if there are actually opposite sides in this group
        market = (pick.market or pick.pick_type or "").upper()
        sides = [p.side for p in group]
        has_opposites = any(
            is_opposite_side(sides[i], sides[j], market)
            for i in range(len(sides))
            for j in range(i + 1, len(sides))
        )

        if not has_opposites:
            # No actual contradiction (maybe same side at different books)
            # Keep all picks in group
            for p in group:
                if p.pick_id not in processed_pick_ids:
                    kept_picks.append(p)
                    processed_pick_ids.add(p.pick_id)
            continue

        # Real contradiction with opposite sides - keep highest score only
        sorted_group = sorted(group, key=lambda p: p.final_score, reverse=True)
        winner = sorted_group[0]
        losers = sorted_group[1:]

        # Keep the winner
        if winner.pick_id not in processed_pick_ids:
            kept_picks.append(winner)
            processed_pick_ids.add(winner.pick_id)

        # Mark and drop the losers
        for loser in losers:
            if loser.pick_id not in processed_pick_ids:
                # Mark as contradiction blocked
                if hasattr(loser, 'contradiction_blocked'):
                    loser.contradiction_blocked = True
                dropped_picks.append(loser)
                processed_pick_ids.add(loser.pick_id)

        # Log contradiction
        if debug or True:  # Always log contradictions
            contradiction_info = {
                "key": key,
                "kept_pick_id": winner.pick_id,
                "kept_score": winner.final_score,
                "kept_side": winner.side,
                "dropped_pick_ids": [p.pick_id for p in losers],
                "dropped_scores": [p.final_score for p in losers],
                "dropped_sides": [p.side for p in losers]
            }
            contradiction_groups.append(contradiction_info)

            logger.info(
                f"Contradiction blocked: {key} | "
                f"Kept: {winner.side} ({winner.final_score:.2f}) | "
                f"Dropped: {[f'{p.side} ({p.final_score:.2f})' for p in losers]}"
            )

    debug_info = {
        "contradictions_detected": len(contradictions),
        "picks_dropped": len(dropped_picks),
        "contradiction_groups": contradiction_groups if debug else []
    }

    return kept_picks, debug_info


def apply_contradiction_gate(props: List[Any], game_picks: List[Any], debug: bool = False) -> Tuple[List[Any], List[Any], Dict[str, Any]]:
    """
    Apply contradiction gate to both props and game picks separately.

    Args:
        props: List of prop picks
        game_picks: List of game picks
        debug: Include detailed debug info

    Returns:
        Tuple of (filtered_props, filtered_game_picks, combined_debug_info)
    """
    filtered_props, props_debug = filter_contradictions(props, debug)
    filtered_game_picks, games_debug = filter_contradictions(game_picks, debug)

    combined_debug = {
        "props_contradictions": props_debug["contradictions_detected"],
        "props_dropped": props_debug["picks_dropped"],
        "games_contradictions": games_debug["contradictions_detected"],
        "games_dropped": games_debug["picks_dropped"],
        "total_contradictions": props_debug["contradictions_detected"] + games_debug["contradictions_detected"],
        "total_dropped": props_debug["picks_dropped"] + games_debug["picks_dropped"]
    }

    if debug:
        combined_debug["props_groups"] = props_debug["contradiction_groups"]
        combined_debug["games_groups"] = games_debug["contradiction_groups"]

    return filtered_props, filtered_game_picks, combined_debug
