"""
Diversity Filter - Prevents props concentration on single players or games.

Ensures we don't recommend multiple props from the same player or flood
picks from a single game.

Fixes the recurring issue: "Svi Mykhailiuk 4 times" appearing in picks.

Rules:
- Max 1 prop per player (keeps highest score)
- Max 3 props per game (spreads diversity across multiple games)
"""
from typing import List, Dict, Tuple, Any
from collections import defaultdict
import re
import logging

logger = logging.getLogger(__name__)

# Configuration
MAX_PROPS_PER_PLAYER = 1  # Only best line per player
MAX_PROPS_PER_GAME = 3    # Spread picks across games


def _normalize_name(value: str) -> str:
    cleaned = re.sub(r"[^\w\s]", "", value or "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip().lower()


def get_player_key(pick: Dict) -> str:
    """
    Create player identifier for deduplication.

    Uses canonical_player_id if available, falls back to player_name.
    """
    canonical_id = pick.get("canonical_player_id") or pick.get("canonical_id") or ""
    if canonical_id:
        # Format may be "NBA:NAME:player_name|team" or a stable ID
        parts = canonical_id.split("|")[0]
        return parts.lower().strip()

    player_id = pick.get("player_id") or pick.get("athlete_id") or ""
    if player_id:
        return str(player_id).lower().strip()

    player_name = pick.get("player_name") or pick.get("player") or pick.get("selection") or ""
    return _normalize_name(player_name)


def get_game_key(pick: Dict) -> str:
    """
    Create game identifier.

    Uses event_id or matchup for grouping.
    """
    event_id = pick.get("event_id") or pick.get("canonical_event_id") or ""
    if event_id:
        return str(event_id).lower().strip()

    matchup = pick.get("matchup") or pick.get("game", "")
    return _normalize_name(matchup)


def apply_diversity_limits(
    picks: List[Dict],
    max_per_player: int = MAX_PROPS_PER_PLAYER,
    max_per_game: int = MAX_PROPS_PER_GAME,
    debug: bool = False
) -> Tuple[List[Dict], Dict[str, Any]]:
    """
    Apply diversity limits to props list.

    Limits concentration of picks on single players and games.
    Must be applied AFTER contradiction gate, BEFORE final slice.

    Args:
        picks: List of prop picks (already sorted by score DESC)
        max_per_player: Maximum props per player (default 1)
        max_per_game: Maximum props per game (default 3)
        debug: Include detailed debug info

    Returns:
        Tuple of (filtered_picks, debug_info)
    """
    if not picks:
        return [], {"player_limited": 0, "game_limited": 0, "total_dropped": 0}

    # Ensure sorted by score DESC
    sorted_picks = sorted(
        picks,
        key=lambda p: p.get("total_score", 0) or p.get("final_score", 0),
        reverse=True
    )

    player_counts: Dict[str, int] = defaultdict(int)
    game_counts: Dict[str, int] = defaultdict(int)

    kept_picks = []
    dropped_by_player = []
    dropped_by_game = []

    for pick in sorted_picks:
        player_key = get_player_key(pick)
        game_key = get_game_key(pick)

        # Skip if player already at limit
        if player_key and player_counts[player_key] >= max_per_player:
            dropped_by_player.append({
                "player": player_key,
                "pick_id": pick.get("pick_id", ""),
                "score": pick.get("total_score", 0),
                "line": pick.get("line", 0),
                "reason": f"Player limit ({max_per_player})"
            })
            continue

        # Skip if game already at limit (for props)
        pick_type = (pick.get("pick_type") or pick.get("market") or "").upper()
        if pick_type in ["PROP", "PLAYER_PROP", "PLAYER_POINTS", "PLAYER_ASSISTS",
                         "PLAYER_REBOUNDS", "PLAYER_THREES", "PLAYER_PRA"]:
            if game_key and game_counts[game_key] >= max_per_game:
                dropped_by_game.append({
                    "game": game_key,
                    "player": player_key,
                    "pick_id": pick.get("pick_id", ""),
                    "score": pick.get("total_score", 0),
                    "reason": f"Game limit ({max_per_game})"
                })
                continue

        # Keep this pick
        kept_picks.append(pick)

        # Update counts
        if player_key:
            player_counts[player_key] += 1
        if game_key:
            game_counts[game_key] += 1

    total_dropped = len(dropped_by_player) + len(dropped_by_game)

    # Log summary
    if total_dropped > 0:
        logger.info(
            "DIVERSITY_FILTER: Kept %d, dropped %d (player_limit=%d, game_limit=%d)",
            len(kept_picks), total_dropped, len(dropped_by_player), len(dropped_by_game)
        )

        # Log sample of dropped picks
        if dropped_by_player:
            sample = dropped_by_player[:3]
            for d in sample:
                logger.debug("  Dropped by player: %s (score=%.2f, line=%.1f)",
                           d["player"], d["score"], d["line"])

    debug_info = {
        "player_limited": len(dropped_by_player),
        "game_limited": len(dropped_by_game),
        "total_dropped": total_dropped,
        "kept": len(kept_picks),
        "original": len(picks),
    }

    if debug:
        debug_info["dropped_by_player"] = dropped_by_player[:10]  # Limit for response size
        debug_info["dropped_by_game"] = dropped_by_game[:10]
        debug_info["player_counts"] = dict(player_counts)
        debug_info["game_counts"] = dict(game_counts)

    return kept_picks, debug_info


def apply_diversity_gate(
    props: List[Dict],
    game_picks: List[Dict],
    debug: bool = False
) -> Tuple[List[Dict], List[Dict], Dict[str, Any]]:
    """
    Apply diversity gate to both props and game picks.

    Only props get player-level limiting. Game picks are passed through unchanged
    since spreads/totals/ML are inherently game-level (not player-level).

    Args:
        props: List of prop picks
        game_picks: List of game picks
        debug: Include detailed debug info

    Returns:
        Tuple of (filtered_props, filtered_game_picks, combined_debug_info)
    """
    # Apply diversity limits to props
    filtered_props, props_debug = apply_diversity_limits(props, debug=debug)

    # Game picks don't need player-level filtering, but we still log
    # Note: Could add max-per-game-for-game-picks in future if needed

    combined_debug = {
        "props_player_limited": props_debug["player_limited"],
        "props_game_limited": props_debug["game_limited"],
        "props_total_dropped": props_debug["total_dropped"],
        "games_total_dropped": 0,  # No game pick filtering currently
        "total_dropped": props_debug["total_dropped"]
    }

    if debug:
        combined_debug["props_debug"] = props_debug

    return filtered_props, game_picks, combined_debug
