"""
validators/prop_integrity.py - Prop Data Integrity Validator
Version: 1.0

Hard-blocks props with missing required data or team mismatch.
Runs BEFORE tiering, BEFORE caps/correlation/UNDER penalty.

DOES NOT MUTATE INPUT - works on copies only.
"""

import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("prop_integrity")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Required keys - prop is INVALID if ANY of these are missing/empty
REQUIRED_KEYS = [
    "sport",
    "player_name",
    "market",
    "line",
    "side",
    "game_id",
]

# Soft-required keys - validation runs ONLY if present
# (player_id, team_id, home_team_id, away_team_id checked for team membership)
TEAM_MEMBERSHIP_KEYS = ["team_id", "home_team_id", "away_team_id"]

# =============================================================================
# VALIDATORS
# =============================================================================

def _normalize_value(val: Any) -> Any:
    """Normalize value for comparison (strip strings, lowercase)."""
    if isinstance(val, str):
        return val.strip().lower()
    return val


def _is_empty(val: Any) -> bool:
    """Check if value is empty/None."""
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def validate_prop_integrity(prop: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate prop data integrity.

    Checks:
    1. All required keys present and non-empty
    2. Team membership (player's team in game's teams)
    3. Optional stat validity checks (if fields exist)

    Args:
        prop: Prop dict (NOT mutated)

    Returns:
        Tuple of (is_valid, reason_if_invalid)
        - (True, None) if valid
        - (False, "REASON_CODE") if invalid
    """
    if not prop or not isinstance(prop, dict):
        return (False, "INVALID_PROP_OBJECT")

    # -------------------------------------------------------------------------
    # 1. Required keys check
    # -------------------------------------------------------------------------
    for key in REQUIRED_KEYS:
        val = prop.get(key)
        if _is_empty(val):
            return (False, f"MISSING_REQUIRED_{key.upper()}")

    # -------------------------------------------------------------------------
    # 2. Team membership check (only if team IDs are present)
    # -------------------------------------------------------------------------
    team_id = prop.get("team_id")
    home_team_id = prop.get("home_team_id")
    away_team_id = prop.get("away_team_id")

    # Also check string team names as fallback
    team_name = prop.get("team") or prop.get("team_name")
    home_team = prop.get("home_team")
    away_team = prop.get("away_team")

    # If we have team_id and game team IDs, verify membership
    if team_id is not None and home_team_id is not None and away_team_id is not None:
        team_id_str = str(team_id).strip().lower()
        home_id_str = str(home_team_id).strip().lower()
        away_id_str = str(away_team_id).strip().lower()

        if team_id_str not in (home_id_str, away_id_str):
            return (False, "TEAM_NOT_IN_GAME")

    # Fallback: check team names if IDs not present
    elif team_name and home_team and away_team:
        team_norm = _normalize_value(team_name)
        home_norm = _normalize_value(home_team)
        away_norm = _normalize_value(away_team)

        # Check if team_name is a substring match (handles abbreviations)
        if not (team_norm in home_norm or home_norm in team_norm or
                team_norm in away_norm or away_norm in team_norm):
            # Also check exact match
            if team_norm != home_norm and team_norm != away_norm:
                return (False, "TEAM_NOT_IN_GAME")

    # -------------------------------------------------------------------------
    # 3. Optional validity checks (only if fields exist)
    # -------------------------------------------------------------------------

    # Games played check
    games_played = prop.get("games_played_season")
    if games_played is not None:
        try:
            if float(games_played) <= 0:
                return (False, "NO_GAMES_PLAYED")
        except (ValueError, TypeError):
            pass  # Skip if not numeric

    # Minutes played check
    minutes = prop.get("minutes_last_5")
    if minutes is not None:
        try:
            if float(minutes) <= 0:
                return (False, "NO_MINUTES_PLAYED")
        except (ValueError, TypeError):
            pass  # Skip if not numeric

    # Active status check
    active_status = prop.get("active_status")
    if active_status is not None:
        status_norm = _normalize_value(active_status)
        valid_statuses = {"true", "active", "1", "yes", "a"}
        if status_norm not in valid_statuses:
            return (False, "PLAYER_INACTIVE")

    # -------------------------------------------------------------------------
    # All checks passed
    # -------------------------------------------------------------------------
    return (True, None)


def validate_props_batch(
    props: list,
    log_drops: bool = True,
    max_log_drops: int = 20
) -> Tuple[list, list, Dict[str, int]]:
    """
    Validate a batch of props.

    Args:
        props: List of prop dicts
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
        is_valid, reason = validate_prop_integrity(prop)

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
