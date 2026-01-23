"""
validators/market_availability.py - DraftKings Market Availability Validator
Version: 1.0

Verifies that a prop is actually available on DraftKings before including it.
Runs BEFORE tiering, BEFORE caps/correlation/UNDER penalty.

DOES NOT MUTATE INPUT - works on copies only.
"""

import logging
from typing import Dict, Any, Tuple, Optional, List, Set
import math

logger = logging.getLogger("market_availability")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Market name normalization map (our names -> canonical names for matching)
MARKET_CANONICAL_MAP = {
    # NBA
    "player_points": "points",
    "player_rebounds": "rebounds",
    "player_assists": "assists",
    "player_threes": "threes",
    "player_steals": "steals",
    "player_blocks": "blocks",
    "player_pts": "points",
    "player_reb": "rebounds",
    "player_ast": "assists",
    "player_3pt": "threes",
    "player_pra": "pra",
    "player_points_rebounds_assists": "pra",
    "player_double_double": "double_double",
    "player_triple_double": "triple_double",
    "player_turnovers": "turnovers",

    # NFL
    "player_pass_yds": "pass_yards",
    "player_pass_tds": "pass_tds",
    "player_rush_yds": "rush_yards",
    "player_rush_tds": "rush_tds",
    "player_rec_yds": "rec_yards",
    "player_receptions": "receptions",
    "player_rec_tds": "rec_tds",

    # NHL
    "player_shots_on_goal": "shots",
    "player_goals": "goals",
    "player_assists_nhl": "assists",
    "player_points_nhl": "points",
    "player_saves": "saves",
    "player_shots": "shots",

    # MLB
    "pitcher_strikeouts": "strikeouts",
    "batter_hits": "hits",
    "batter_total_bases": "total_bases",
    "batter_rbis": "rbis",
    "batter_runs": "runs",
}

# Line tolerance for floating point comparison
LINE_TOLERANCE = 0.01


# =============================================================================
# INDEX BUILDER
# =============================================================================

def _normalize_market(market: str) -> str:
    """Normalize market name to canonical form."""
    if not market:
        return ""
    market_lower = market.strip().lower()
    return MARKET_CANONICAL_MAP.get(market_lower, market_lower)


def _normalize_name(name: str) -> str:
    """Normalize player name for comparison."""
    if not name:
        return ""
    # Lowercase, strip whitespace, remove common suffixes
    name = name.strip().lower()
    # Remove Jr., Sr., III, etc.
    for suffix in [" jr.", " sr.", " jr", " sr", " iii", " ii", " iv"]:
        name = name.replace(suffix, "")
    return name.strip()


def _normalize_side(side: str) -> str:
    """Normalize side (over/under) for comparison."""
    if not side:
        return ""
    side_lower = side.strip().lower()
    if side_lower in ("over", "o"):
        return "over"
    if side_lower in ("under", "u"):
        return "under"
    return side_lower


def _lines_match(line1: Any, line2: Any) -> bool:
    """Compare lines with floating point tolerance."""
    try:
        l1 = float(line1)
        l2 = float(line2)
        return abs(l1 - l2) <= LINE_TOLERANCE
    except (ValueError, TypeError):
        return str(line1) == str(line2)


def _generate_prop_key(
    sport: str,
    game_id: str,
    player_id: Optional[str],
    player_name: str,
    market: str,
    line: Any,
    side: str
) -> str:
    """Generate a unique key for a prop."""
    sport_norm = (sport or "").strip().lower()
    game_norm = (game_id or "").strip().lower()
    market_norm = _normalize_market(market)
    side_norm = _normalize_side(side)

    # Use player_id if available, else normalized name
    if player_id:
        player_key = f"id:{player_id}"
    else:
        player_key = f"name:{_normalize_name(player_name)}"

    # Round line to 1 decimal for consistency
    try:
        line_norm = round(float(line), 1)
    except (ValueError, TypeError):
        line_norm = line

    return f"{sport_norm}|{game_norm}|{player_key}|{market_norm}|{line_norm}|{side_norm}"


def build_dk_market_index(props_feed: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Build DraftKings market availability index from props feed.

    Args:
        props_feed: List of props from DK/Odds API feed

    Returns:
        Dict mapping prop_key -> prop details
    """
    index = {}

    for prop in props_feed:
        sport = prop.get("sport") or prop.get("league", "")
        game_id = prop.get("game_id") or prop.get("event_id", "")
        player_id = prop.get("player_id")
        player_name = prop.get("player_name") or prop.get("player", "")
        market = prop.get("market") or prop.get("stat_type", "")
        line = prop.get("line") or prop.get("point", "")
        side = prop.get("side") or prop.get("over_under", "")

        # Generate primary key
        key = _generate_prop_key(sport, game_id, player_id, player_name, market, line, side)
        index[key] = prop

        # Also generate name-based key if we have player_id (for fallback matching)
        if player_id and player_name:
            name_key = _generate_prop_key(sport, game_id, None, player_name, market, line, side)
            if name_key not in index:
                index[name_key] = prop

    return index


def build_dk_market_index_from_events(events: List[Dict[str, Any]], sport: str = "") -> Dict[str, Dict[str, Any]]:
    """
    Build DraftKings market index from events with nested props.

    Handles format: [{game_id, props: [{player_name, market, line, side, ...}]}]
    """
    index = {}

    for event in events:
        game_id = event.get("game_id") or event.get("id", "")
        event_sport = sport or event.get("sport") or event.get("league", "")

        props = event.get("props") or event.get("markets") or []

        for prop in props:
            player_id = prop.get("player_id")
            player_name = prop.get("player_name") or prop.get("player", "") or prop.get("description", "")
            market = prop.get("market") or prop.get("stat_type") or prop.get("name", "")
            line = prop.get("line") or prop.get("point") or prop.get("handicap", "")

            # Handle outcomes with over/under
            outcomes = prop.get("outcomes") or []
            for outcome in outcomes:
                side = outcome.get("name") or outcome.get("side", "")
                if not side:
                    continue

                key = _generate_prop_key(event_sport, game_id, player_id, player_name, market, line, side)
                index[key] = {
                    "game_id": game_id,
                    "player_id": player_id,
                    "player_name": player_name,
                    "market": market,
                    "line": line,
                    "side": side,
                    "odds": outcome.get("price") or outcome.get("odds"),
                    "sport": event_sport
                }

                # Name-based fallback key
                if player_id and player_name:
                    name_key = _generate_prop_key(event_sport, game_id, None, player_name, market, line, side)
                    if name_key not in index:
                        index[name_key] = index[key]

            # If no outcomes, just index the prop itself
            if not outcomes:
                side = prop.get("side") or prop.get("over_under", "over")
                key = _generate_prop_key(event_sport, game_id, player_id, player_name, market, line, side)
                index[key] = {
                    "game_id": game_id,
                    "player_id": player_id,
                    "player_name": player_name,
                    "market": market,
                    "line": line,
                    "side": side,
                    "sport": event_sport
                }

    return index


# =============================================================================
# VALIDATOR
# =============================================================================

def validate_market_available(
    prop: Dict[str, Any],
    dk_market_index: Dict[str, Dict[str, Any]]
) -> Tuple[bool, Optional[str]]:
    """
    Validate that prop exists in DraftKings market feed.

    Matching rules:
    1. Exact match by (sport, game_id, player_id, market, line, side)
    2. Fallback to normalized player_name if player_id not available

    Args:
        prop: Prop dict (NOT mutated)
        dk_market_index: Built from build_dk_market_index()

    Returns:
        Tuple of (is_valid, reason_if_invalid)
    """
    if not dk_market_index:
        # If no index provided, allow all (graceful degradation)
        logger.warning("DK market index is empty - skipping availability check")
        return (True, None)

    sport = prop.get("sport", "")
    game_id = prop.get("game_id") or prop.get("event_id", "")
    player_id = prop.get("player_id")
    player_name = prop.get("player_name", "")
    market = prop.get("market") or prop.get("stat_type", "")
    line = prop.get("line", "")
    side = prop.get("side") or prop.get("over_under", "")

    # Try primary key (with player_id if available)
    primary_key = _generate_prop_key(sport, game_id, player_id, player_name, market, line, side)
    if primary_key in dk_market_index:
        return (True, None)

    # Try name-only key as fallback
    name_key = _generate_prop_key(sport, game_id, None, player_name, market, line, side)
    if name_key in dk_market_index:
        return (True, None)

    # Try with canonical market name
    canonical_market = _normalize_market(market)
    if canonical_market != market:
        canonical_key = _generate_prop_key(sport, game_id, player_id, player_name, canonical_market, line, side)
        if canonical_key in dk_market_index:
            return (True, None)

        canonical_name_key = _generate_prop_key(sport, game_id, None, player_name, canonical_market, line, side)
        if canonical_name_key in dk_market_index:
            return (True, None)

    # Not found in DK feed
    return (False, "DK_MARKET_NOT_LISTED")


def validate_props_batch_market(
    props: list,
    dk_market_index: Dict[str, Dict[str, Any]],
    log_drops: bool = True,
    max_log_drops: int = 20
) -> Tuple[list, list, Dict[str, int]]:
    """
    Validate a batch of props against DK market index.

    Args:
        props: List of prop dicts
        dk_market_index: Built from build_dk_market_index()
        log_drops: Whether to log dropped props
        max_log_drops: Max number of drops to log

    Returns:
        Tuple of (valid_props, dropped_props, drop_counts_by_reason)
    """
    valid = []
    dropped = []
    drop_counts: Dict[str, int] = {}
    logged_count = 0

    for prop in props:
        is_valid, reason = validate_market_available(prop, dk_market_index)

        if is_valid:
            valid.append(prop)
        else:
            dropped.append({"prop": prop, "reason": reason})
            drop_counts[reason] = drop_counts.get(reason, 0) + 1

            if log_drops and logged_count < max_log_drops:
                sport = prop.get("sport", "?")
                player = prop.get("player_name", "?")
                market = prop.get("market", "?")
                line = prop.get("line", "?")
                side = prop.get("side", "?")
                logger.warning(
                    f"[DROPPED] {sport} | {player} | {market} | {line} | {side} | {reason}"
                )
                logged_count += 1

    if log_drops and len(dropped) > max_log_drops:
        logger.warning(f"... and {len(dropped) - max_log_drops} more dropped")

    return (valid, dropped, drop_counts)
