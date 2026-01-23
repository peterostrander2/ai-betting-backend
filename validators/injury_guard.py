"""
validators/injury_guard.py - Injury Status Validator
Version: 1.0

Blocks props for players who are OUT, SUSPENDED, or optionally DOUBTFUL.
Runs BEFORE tiering, BEFORE caps/correlation/UNDER penalty.

DOES NOT MUTATE INPUT - works on copies only.
"""

import logging
from typing import Dict, Any, Tuple, Optional, List

logger = logging.getLogger("injury_guard")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Block DOUBTFUL players (default: True - block them)
BLOCK_DOUBTFUL = True

# Block GTD (Game-Time Decision) players (default: False - allow but can tag)
BLOCK_GTD = False

# Status values that indicate OUT
OUT_STATUSES = {"out", "o", "inactive", "inj", "injured"}

# Status values that indicate SUSPENDED
SUSPENDED_STATUSES = {"suspended", "susp", "sus"}

# Status values that indicate DOUBTFUL
DOUBTFUL_STATUSES = {"doubtful", "d"}

# Status values that indicate GTD (Game-Time Decision)
GTD_STATUSES = {"gtd", "game-time", "gametime", "game time decision", "questionable", "q", "probable", "p"}


# =============================================================================
# INDEX BUILDER
# =============================================================================

def build_injury_index(injuries: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Build injury lookup index from injury API response.

    Keys by player_id if present, else normalized player_name.

    Args:
        injuries: List of injury records from API

    Returns:
        Dict mapping player_key -> injury info
    """
    index = {}

    for inj in injuries:
        # Determine key (prefer player_id, fallback to name)
        player_id = inj.get("player_id")
        player_name = inj.get("player") or inj.get("name") or inj.get("player_name")

        if player_id:
            key = f"id:{player_id}"
        elif player_name:
            key = f"name:{player_name.strip().lower()}"
        else:
            continue  # Skip if no identifier

        # Normalize status
        status_raw = inj.get("status") or inj.get("injury_status") or ""
        status = status_raw.strip().lower()

        # Determine flags
        is_out = status in OUT_STATUSES or inj.get("is_out", False)
        is_suspended = status in SUSPENDED_STATUSES or inj.get("is_suspended", False)
        is_doubtful = status in DOUBTFUL_STATUSES or inj.get("is_doubtful", False)
        is_gtd = status in GTD_STATUSES or inj.get("is_gtd", False)

        index[key] = {
            "player_id": player_id,
            "player_name": player_name,
            "status": status,
            "status_raw": status_raw,
            "is_out": is_out,
            "is_suspended": is_suspended,
            "is_doubtful": is_doubtful,
            "is_gtd": is_gtd,
            "injury": inj.get("injury") or inj.get("injury_type") or "",
            "team": inj.get("team") or ""
        }

    return index


def _lookup_player_in_index(
    prop: Dict[str, Any],
    injury_index: Dict[str, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Look up player in injury index.

    Tries player_id first, then normalized player_name.
    """
    # Try by player_id
    player_id = prop.get("player_id")
    if player_id:
        key = f"id:{player_id}"
        if key in injury_index:
            return injury_index[key]

    # Try by player_name
    player_name = prop.get("player_name")
    if player_name:
        key = f"name:{player_name.strip().lower()}"
        if key in injury_index:
            return injury_index[key]

    return None


# =============================================================================
# VALIDATOR
# =============================================================================

def validate_injury_status(
    prop: Dict[str, Any],
    injury_index: Dict[str, Dict[str, Any]],
    block_doubtful: bool = None,
    block_gtd: bool = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate player injury status.

    Checks:
    1. OUT -> HARD BLOCK
    2. SUSPENDED -> HARD BLOCK
    3. DOUBTFUL -> Block if BLOCK_DOUBTFUL=True
    4. GTD -> Block if BLOCK_GTD=True (default: allow)

    Args:
        prop: Prop dict (NOT mutated)
        injury_index: Built from build_injury_index()
        block_doubtful: Override BLOCK_DOUBTFUL config
        block_gtd: Override BLOCK_GTD config

    Returns:
        Tuple of (is_valid, reason_if_invalid)
    """
    if block_doubtful is None:
        block_doubtful = BLOCK_DOUBTFUL
    if block_gtd is None:
        block_gtd = BLOCK_GTD

    # Look up player in injury index
    injury_info = _lookup_player_in_index(prop, injury_index)

    if injury_info is None:
        # Player not in injury report = healthy
        return (True, None)

    # Check injury flags in priority order
    if injury_info.get("is_out"):
        return (False, "INJURY_OUT")

    if injury_info.get("is_suspended"):
        return (False, "INJURY_SUSPENDED")

    if injury_info.get("is_doubtful") and block_doubtful:
        return (False, "INJURY_DOUBTFUL")

    if injury_info.get("is_gtd") and block_gtd:
        return (False, "INJURY_GTD")

    # Player is on injury report but not blocked
    return (True, None)


def validate_props_batch_injury(
    props: list,
    injury_index: Dict[str, Dict[str, Any]],
    log_drops: bool = True,
    max_log_drops: int = 20
) -> Tuple[list, list, Dict[str, int]]:
    """
    Validate a batch of props against injury index.

    Args:
        props: List of prop dicts
        injury_index: Built from build_injury_index()
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
        is_valid, reason = validate_injury_status(prop, injury_index)

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
