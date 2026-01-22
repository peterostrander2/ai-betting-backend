# publish_gate.py - Quality Gate (No Caps) + Dominance Dedup
# Version: 1.0
#
# This module implements:
# A) Dominance-based deduplication (keep best pick per player per cluster)
# B) Dynamic quality gate (escalate thresholds, not cap counts)
# C) Correlation penalty (penalize crowded games)
#
# Applies to: NBA, NFL, MLB, NHL, NCAAB (props + games)

import logging
from typing import Dict, Any, List, Tuple
from collections import defaultdict

logger = logging.getLogger("publish_gate")

# ============================================================================
# CONFIGURATION
# ============================================================================

# Cluster map by stat_type
STAT_CLUSTERS = {
    # SCORING cluster
    "player_points": "SCORING",
    "player_threes": "SCORING",
    "player_pts": "SCORING",
    "player_3pt": "SCORING",
    "points": "SCORING",
    "threes": "SCORING",

    # FACILITATION cluster
    "player_assists": "FACILITATION",
    "player_ast": "FACILITATION",
    "assists": "FACILITATION",

    # HUSTLE cluster
    "player_rebounds": "HUSTLE",
    "player_reb": "HUSTLE",
    "rebounds": "HUSTLE",

    # DEFENSE cluster
    "player_steals": "DEFENSE",
    "player_blocks": "DEFENSE",
    "player_stl": "DEFENSE",
    "player_blk": "DEFENSE",
    "steals": "DEFENSE",
    "blocks": "DEFENSE",

    # COMBO cluster
    "player_pra": "COMBO",
    "player_points_rebounds_assists": "COMBO",
    "player_double_double": "COMBO",
    "player_triple_double": "COMBO",

    # NFL-specific
    "player_pass_yds": "PASSING",
    "player_pass_tds": "PASSING",
    "player_rush_yds": "RUSHING",
    "player_rush_tds": "RUSHING",
    "player_rec_yds": "RECEIVING",
    "player_receptions": "RECEIVING",
    "player_rec_tds": "RECEIVING",

    # MLB-specific
    "pitcher_strikeouts": "PITCHING",
    "pitcher_outs": "PITCHING",
    "batter_hits": "BATTING",
    "batter_rbis": "BATTING",
    "batter_runs": "BATTING",
    "batter_total_bases": "BATTING",

    # NHL-specific
    "player_goals": "GOALS",
    "player_assists_nhl": "ASSISTS_NHL",
    "player_points_nhl": "POINTS_NHL",
    "player_shots": "SHOTS",
    "goalie_saves": "GOALIE",
}

# Default cluster for unknown stat types
DEFAULT_CLUSTER = "OTHER"

# Correlation penalty by pick count from same game
CORRELATION_PENALTIES = {
    1: 0.0,    # First pick from game: no penalty
    2: -0.05,  # Second pick: -0.05
    3: -0.10,  # Third pick: -0.10
    4: -0.20,  # Fourth+ pick: -0.20
}
MAX_CORRELATION_PENALTY = -0.20

# Dynamic threshold escalation steps
EDGE_LEAN_THRESHOLDS = [7.05, 7.15, 7.25, 7.35]
GOLD_STAR_THRESHOLDS = [7.50, 7.70, 7.85]

# Target pick count (heuristic for "too many")
TARGET_MAX_PICKS = 20


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_cluster(stat_type: str) -> str:
    """Get cluster for a stat type."""
    if not stat_type:
        return DEFAULT_CLUSTER
    stat_lower = stat_type.lower().strip()
    return STAT_CLUSTERS.get(stat_lower, DEFAULT_CLUSTER)


def get_score(pick: Dict[str, Any]) -> float:
    """Get the score from a pick (handles multiple field names)."""
    return float(pick.get("smash_score", pick.get("total_score", pick.get("final_score", 0))))


def get_player_name(pick: Dict[str, Any]) -> str:
    """Get normalized player name from pick."""
    name = pick.get("player_name", pick.get("player", ""))
    return name.lower().strip() if name else ""


def get_game_id(pick: Dict[str, Any]) -> str:
    """Get game identifier from pick."""
    return pick.get("game_id", pick.get("game_key", pick.get("game", "")))


def get_stat_type(pick: Dict[str, Any]) -> str:
    """Get stat type from pick."""
    return pick.get("stat_type", pick.get("market", ""))


# ============================================================================
# PART A: DOMINANCE DEDUPLICATION
# ============================================================================

def apply_dominance_dedup(picks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Apply dominance-based deduplication.

    For each player, keep ONLY the highest smash_score pick per cluster.

    Returns:
        Tuple of (deduped_picks, stats)
    """
    # Group picks by (player, cluster)
    player_cluster_best: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for pick in picks:
        player = get_player_name(pick)
        stat_type = get_stat_type(pick)
        cluster = get_cluster(stat_type)
        score = get_score(pick)

        key = (player, cluster)

        if key not in player_cluster_best:
            player_cluster_best[key] = pick
        else:
            existing_score = get_score(player_cluster_best[key])
            if score > existing_score:
                player_cluster_best[key] = pick

    deduped = list(player_cluster_best.values())

    # Sort by score descending
    deduped.sort(key=lambda x: get_score(x), reverse=True)

    stats = {
        "input_count": len(picks),
        "output_count": len(deduped),
        "removed_count": len(picks) - len(deduped),
        "unique_players": len(set(get_player_name(p) for p in deduped)),
        "clusters_used": list(set(get_cluster(get_stat_type(p)) for p in deduped))
    }

    return deduped, stats


# ============================================================================
# PART C: CORRELATION PENALTY
# ============================================================================

def apply_correlation_penalty(picks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Apply correlation penalty for picks from the same game.

    - 2nd pick from same game: -0.05
    - 3rd pick: -0.10
    - 4th+ pick: -0.20

    Returns:
        Tuple of (penalized_picks, stats)
    """
    # Count picks per game
    game_pick_counts: Dict[str, int] = defaultdict(int)

    # Sort by score first (so higher scores get counted first = lower penalty)
    sorted_picks = sorted(picks, key=lambda x: get_score(x), reverse=True)

    penalized_picks = []
    total_penalty_applied = 0.0
    games_with_penalty = set()

    for pick in sorted_picks:
        game_id = get_game_id(pick)
        game_pick_counts[game_id] += 1
        count = game_pick_counts[game_id]

        # Get penalty for this position
        penalty = CORRELATION_PENALTIES.get(count, MAX_CORRELATION_PENALTY)

        if penalty != 0:
            # Apply penalty
            original_score = get_score(pick)
            new_score = original_score + penalty  # penalty is negative

            # Update the pick (make a copy to avoid mutating original)
            pick_copy = pick.copy()
            pick_copy["smash_score"] = round(new_score, 2)
            pick_copy["total_score"] = round(new_score, 2)
            pick_copy["correlation_penalty"] = penalty
            pick_copy["correlation_position"] = count

            # Add reason
            reasons = pick_copy.get("reasons", [])
            reasons.append(f"PUBLISH_GATE: Correlation penalty {penalty} (pick #{count} from {game_id})")
            pick_copy["reasons"] = reasons

            penalized_picks.append(pick_copy)
            total_penalty_applied += abs(penalty)
            games_with_penalty.add(game_id)
        else:
            penalized_picks.append(pick)

    # Re-sort after penalties
    penalized_picks.sort(key=lambda x: get_score(x), reverse=True)

    stats = {
        "picks_penalized": len([p for p in penalized_picks if p.get("correlation_penalty", 0) != 0]),
        "total_penalty_applied": round(total_penalty_applied, 2),
        "games_with_multiple_picks": len(games_with_penalty)
    }

    return penalized_picks, stats


# ============================================================================
# PART B: DYNAMIC QUALITY GATE
# ============================================================================

def apply_quality_gate(
    picks: List[Dict[str, Any]],
    target_max: int = TARGET_MAX_PICKS
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Apply dynamic quality gate.

    - Publish all GOLD_STAR
    - Publish EDGE_LEAN only if score >= threshold
    - Escalate threshold if too many picks remain

    Returns:
        Tuple of (gated_picks, stats)
    """
    # Start with default thresholds
    edge_lean_threshold = EDGE_LEAN_THRESHOLDS[0]
    gold_star_threshold = GOLD_STAR_THRESHOLDS[0]

    edge_lean_step = 0
    gold_star_step = 0

    def filter_picks(el_thresh: float, gs_thresh: float) -> List[Dict[str, Any]]:
        """Filter picks based on thresholds."""
        result = []
        for pick in picks:
            tier = pick.get("tier", "")
            score = get_score(pick)

            if tier == "GOLD_STAR":
                if score >= gs_thresh:
                    result.append(pick)
            elif tier == "EDGE_LEAN":
                if score >= el_thresh:
                    result.append(pick)
            # MONITOR and below are not published (unless fallback)
        return result

    # Initial filter
    gated = filter_picks(edge_lean_threshold, gold_star_threshold)

    # Escalate EDGE_LEAN threshold if too many picks
    while len(gated) > target_max and edge_lean_step < len(EDGE_LEAN_THRESHOLDS) - 1:
        edge_lean_step += 1
        edge_lean_threshold = EDGE_LEAN_THRESHOLDS[edge_lean_step]
        gated = filter_picks(edge_lean_threshold, gold_star_threshold)

    # If still too many, escalate GOLD_STAR threshold (last resort)
    while len(gated) > target_max and gold_star_step < len(GOLD_STAR_THRESHOLDS) - 1:
        gold_star_step += 1
        gold_star_threshold = GOLD_STAR_THRESHOLDS[gold_star_step]
        gated = filter_picks(edge_lean_threshold, gold_star_threshold)

    # Add publish gate info to remaining picks
    for pick in gated:
        pick["publish_gate_passed"] = True
        reasons = pick.get("reasons", [])
        tier = pick.get("tier", "")
        if tier == "EDGE_LEAN" and edge_lean_threshold > EDGE_LEAN_THRESHOLDS[0]:
            reasons.append(f"PUBLISH_GATE: Passed escalated EDGE_LEAN threshold ({edge_lean_threshold})")
        pick["reasons"] = reasons

    stats = {
        "input_count": len(picks),
        "output_count": len(gated),
        "edge_lean_threshold": edge_lean_threshold,
        "edge_lean_step": edge_lean_step,
        "gold_star_threshold": gold_star_threshold,
        "gold_star_step": gold_star_step,
        "gold_star_count": len([p for p in gated if p.get("tier") == "GOLD_STAR"]),
        "edge_lean_count": len([p for p in gated if p.get("tier") == "EDGE_LEAN"]),
        "threshold_escalated": edge_lean_step > 0 or gold_star_step > 0
    }

    return gated, stats


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def apply_publish_gate(
    picks: List[Dict[str, Any]],
    target_max: int = TARGET_MAX_PICKS,
    apply_dedup: bool = True,
    apply_penalty: bool = True,
    apply_gate: bool = True
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Apply full publish gate pipeline.

    Order:
    1. Dominance deduplication (per player per cluster)
    2. Correlation penalty (same game)
    3. Dynamic quality gate (threshold escalation)

    Args:
        picks: List of scored picks
        target_max: Target maximum picks (for quality gate)
        apply_dedup: Whether to apply dominance dedup
        apply_penalty: Whether to apply correlation penalty
        apply_gate: Whether to apply quality gate

    Returns:
        Tuple of (final_picks, debug_stats)
    """
    debug = {
        "input_picks": len(picks),
        "after_dedup": 0,
        "after_corr_penalty": 0,
        "publish_threshold_edge_lean": EDGE_LEAN_THRESHOLDS[0],
        "publish_threshold_gold_star": GOLD_STAR_THRESHOLDS[0],
        "published_total": 0,
        "dedup_stats": {},
        "penalty_stats": {},
        "gate_stats": {}
    }

    current_picks = picks

    # Step 1: Dominance deduplication
    if apply_dedup:
        current_picks, dedup_stats = apply_dominance_dedup(current_picks)
        debug["after_dedup"] = len(current_picks)
        debug["dedup_stats"] = dedup_stats
    else:
        debug["after_dedup"] = len(current_picks)

    # Step 2: Correlation penalty
    if apply_penalty:
        current_picks, penalty_stats = apply_correlation_penalty(current_picks)
        debug["after_corr_penalty"] = len(current_picks)
        debug["penalty_stats"] = penalty_stats
    else:
        debug["after_corr_penalty"] = len(current_picks)

    # Step 3: Quality gate
    if apply_gate:
        current_picks, gate_stats = apply_quality_gate(current_picks, target_max)
        debug["publish_threshold_edge_lean"] = gate_stats["edge_lean_threshold"]
        debug["publish_threshold_gold_star"] = gate_stats["gold_star_threshold"]
        debug["gate_stats"] = gate_stats

    debug["published_total"] = len(current_picks)

    return current_picks, debug


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "apply_publish_gate",
    "apply_dominance_dedup",
    "apply_correlation_penalty",
    "apply_quality_gate",
    "get_cluster",
    "STAT_CLUSTERS",
    "EDGE_LEAN_THRESHOLDS",
    "GOLD_STAR_THRESHOLDS",
    "TARGET_MAX_PICKS",
]
