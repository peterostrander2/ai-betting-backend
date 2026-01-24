"""
pick_filter.py - Post-Processing Pick Filter Layer
Version: 1.0

Runs AFTER picks are scored and tiered to enforce:
- Daily output caps (GOLD_STAR: 5, EDGE_LEAN: 8, Total: 13)
- Correlation limits (1 GOLD_STAR/player, 2 total/player, 3/game)
- UNDER penalty (-0.15 unless under_supported flag)
- Highest-score-wins ordering

This module does NOT change tier thresholds - only filters and re-orders.
"""

from typing import List, Dict, Any
from collections import defaultdict
import logging

from tiering import tier_from_score

logger = logging.getLogger("pick_filter")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Daily output caps
MAX_GOLD_STAR = 5
MAX_EDGE_LEAN = 8
MAX_TOTAL = 13

# Correlation limits
MAX_GOLD_STAR_PER_PLAYER = 1
MAX_PICKS_PER_PLAYER = 2
MAX_PICKS_PER_GAME = 3

# UNDER penalty
UNDER_PENALTY = 0.15


def _normalize_player_name(name: str) -> str:
    """Normalize player name for deduplication."""
    if not name:
        return ""
    return name.lower().strip()


def _normalize_game_key(pick: Dict[str, Any]) -> str:
    """Extract a normalized game key for correlation tracking."""
    # Try different field names used across the codebase
    game = pick.get("game") or pick.get("matchup") or pick.get("game_id") or ""
    return game.lower().strip()


def _apply_under_penalty(pick: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply UNDER penalty to pick if applicable.

    Reduces final_score by 0.15 for UNDER picks unless under_supported=True.
    Re-tiers after penalty application.

    v10.57: Skip penalty for game picks (totals UNDER is legitimate strategy).

    Returns a new dict (does not mutate original).
    """
    pick = pick.copy()

    # v10.57: Skip UNDER penalty for game picks (no player_name = game pick)
    is_game_pick = not (pick.get("player_name") or pick.get("stat_type"))
    if is_game_pick:
        return pick

    side = (pick.get("side") or pick.get("over_under") or "").upper()
    under_supported = pick.get("under_supported", False)

    if side == "UNDER" and not under_supported:
        # Get the score field (different names used)
        score_field = "smash_score" if "smash_score" in pick else "final_score"
        original_score = pick.get(score_field, 0)

        # Apply penalty
        new_score = original_score - UNDER_PENALTY
        pick[score_field] = round(new_score, 2)

        # Re-tier
        new_tier, _ = tier_from_score(new_score)
        pick["tier"] = new_tier

        # Track that penalty was applied
        pick["under_penalty_applied"] = True
        pick["original_score"] = original_score

    return pick


def _get_score(pick: Dict[str, Any]) -> float:
    """Get the score value from a pick (handles different field names)."""
    return pick.get("smash_score") or pick.get("final_score") or 0


def filter_best_bets(picks: List[Dict[str, Any]], sport: str = "NBA") -> List[Dict[str, Any]]:
    """
    Filter and rank picks to enforce caps and correlation limits.

    Pipeline:
    1. Apply UNDER penalty + re-tier
    2. Sort by final_score descending
    3. Enforce correlation limits (player/game)
    4. Enforce daily caps (GOLD_STAR/EDGE_LEAN/total)
    5. Return surviving picks

    Args:
        picks: List of pick dicts with final_score, tier, player_name, game, side
        sport: Sport code (for logging)

    Returns:
        Filtered list of picks respecting all constraints
    """
    if not picks:
        return []

    # Step 1: Apply UNDER penalty + re-tier
    penalized_picks = [_apply_under_penalty(p) for p in picks]

    # Step 2: Sort by score descending (highest first)
    sorted_picks = sorted(penalized_picks, key=lambda p: _get_score(p), reverse=True)

    # Step 3 & 4: Filter with constraints
    result = []

    # Tracking counters
    gold_star_count = 0
    edge_lean_count = 0
    player_gold_star: Dict[str, int] = defaultdict(int)
    player_total: Dict[str, int] = defaultdict(int)
    game_total: Dict[str, int] = defaultdict(int)

    for pick in sorted_picks:
        tier = pick.get("tier", "PASS")
        player = _normalize_player_name(pick.get("player_name", ""))
        game = _normalize_game_key(pick)

        # Skip non-actionable tiers
        if tier not in ("GOLD_STAR", "EDGE_LEAN"):
            continue

        # Check total cap first
        if len(result) >= MAX_TOTAL:
            logger.debug(f"[{sport}] Total cap reached ({MAX_TOTAL}), stopping")
            break

        # Check tier-specific caps
        if tier == "GOLD_STAR":
            if gold_star_count >= MAX_GOLD_STAR:
                logger.debug(f"[{sport}] GOLD_STAR cap reached, skipping {player}")
                continue
        elif tier == "EDGE_LEAN":
            if edge_lean_count >= MAX_EDGE_LEAN:
                logger.debug(f"[{sport}] EDGE_LEAN cap reached, skipping {player}")
                continue

        # Check player correlation limits
        if player:
            # GOLD_STAR per player limit
            if tier == "GOLD_STAR" and player_gold_star[player] >= MAX_GOLD_STAR_PER_PLAYER:
                logger.debug(f"[{sport}] Player {player} GOLD_STAR limit reached, skipping")
                continue

            # Total per player limit
            if player_total[player] >= MAX_PICKS_PER_PLAYER:
                logger.debug(f"[{sport}] Player {player} total limit reached, skipping")
                continue

        # Check game correlation limit
        if game and game_total[game] >= MAX_PICKS_PER_GAME:
            logger.debug(f"[{sport}] Game {game} limit reached, skipping")
            continue

        # Pick passes all filters - add it
        result.append(pick)

        # Update counters
        if tier == "GOLD_STAR":
            gold_star_count += 1
            if player:
                player_gold_star[player] += 1
        elif tier == "EDGE_LEAN":
            edge_lean_count += 1

        if player:
            player_total[player] += 1
        if game:
            game_total[game] += 1

    logger.info(
        f"[{sport}] Pick filter: {len(picks)} candidates -> {len(result)} final "
        f"(GS:{gold_star_count}, EL:{edge_lean_count})"
    )

    return result


def get_filter_stats(
    before_picks: List[Dict[str, Any]],
    after_picks: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate stats comparing before/after filtering.
    Useful for debugging and transparency.
    """
    def count_tiers(picks):
        tiers = defaultdict(int)
        for p in picks:
            tiers[p.get("tier", "UNKNOWN")] += 1
        return dict(tiers)

    def count_players(picks):
        players = defaultdict(int)
        for p in picks:
            name = _normalize_player_name(p.get("player_name", ""))
            if name:
                players[name] += 1
        return dict(players)

    before_tiers = count_tiers(before_picks)
    after_tiers = count_tiers(after_picks)

    # Count players with multiple picks before/after
    before_players = count_players(before_picks)
    after_players = count_players(after_picks)

    multi_player_before = sum(1 for c in before_players.values() if c > 1)
    multi_player_after = sum(1 for c in after_players.values() if c > 1)

    return {
        "before_count": len(before_picks),
        "after_count": len(after_picks),
        "removed": len(before_picks) - len(after_picks),
        "before_tiers": before_tiers,
        "after_tiers": after_tiers,
        "players_with_multiple_before": multi_player_before,
        "players_with_multiple_after": multi_player_after,
        "caps": {
            "gold_star_max": MAX_GOLD_STAR,
            "edge_lean_max": MAX_EDGE_LEAN,
            "total_max": MAX_TOTAL
        }
    }
