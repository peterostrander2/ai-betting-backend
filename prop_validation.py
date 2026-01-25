"""
Prop Validation Module v11.00
=============================
Validates player props against injury data and book availability.

If a player is OUT/DNP/not listed/not offered → prop is invalid.
This prevents betting on unavailable players.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

# Injury statuses that should BLOCK props
BLOCK_STATUSES = {
    "out", "o", "dnp", "injured reserve", "ir", "suspended",
    "not with team", "personal", "rest", "illness"
}

# Injury statuses that should WARN but not block
WARN_STATUSES = {
    "questionable", "q", "doubtful", "d", "day-to-day", "dtd",
    "probable", "p", "game time decision", "gtd"
}


class PropValidationResult:
    """Result of prop validation check."""

    def __init__(
        self,
        is_valid: bool,
        player_prop_listed: bool = True,
        injury_verified: bool = True,
        injury_status: Optional[str] = None,
        block_reason: Optional[str] = None,
        warning: Optional[str] = None,
        book_checked: Optional[str] = None
    ):
        self.is_valid = is_valid
        self.player_prop_listed = player_prop_listed
        self.injury_verified = injury_verified
        self.injury_status = injury_status
        self.block_reason = block_reason
        self.warning = warning
        self.book_checked = book_checked

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "player_prop_listed": self.player_prop_listed,
            "injury_verified": self.injury_verified,
            "injury_status": self.injury_status,
            "block_reason": self.block_reason,
            "warning": self.warning,
            "book_checked": self.book_checked
        }


def validate_prop(
    player_name: str,
    stat_type: str,
    injuries_data: List[Dict[str, Any]],
    available_props: Optional[List[Dict[str, Any]]] = None,
    book: str = "draftkings"
) -> PropValidationResult:
    """
    Validate a player prop against injury data and book availability.

    Args:
        player_name: Player name to validate
        stat_type: Stat type (e.g., "player_points")
        injuries_data: List of injury reports
        available_props: Optional list of props offered by book
        book: Sportsbook to check availability

    Returns:
        PropValidationResult with validation status
    """
    player_lower = player_name.lower().strip()

    # 1. Check injury status
    injury_status = None
    for injury in injuries_data:
        inj_player = (injury.get("player") or injury.get("name") or "").lower().strip()
        if player_lower in inj_player or inj_player in player_lower:
            injury_status = (injury.get("status") or injury.get("injury_status") or "").lower()
            break

    # Check if injury blocks the prop
    if injury_status and injury_status in BLOCK_STATUSES:
        return PropValidationResult(
            is_valid=False,
            player_prop_listed=False,
            injury_verified=True,
            injury_status=injury_status.upper(),
            block_reason=f"Player {player_name} is {injury_status.upper()} - prop blocked",
            book_checked=book
        )

    # 2. Check if prop is listed on book (if available_props provided)
    prop_listed = True
    if available_props is not None:
        prop_listed = False
        for prop in available_props:
            prop_player = (prop.get("player") or prop.get("player_name") or "").lower()
            prop_market = (prop.get("market") or prop.get("stat_type") or "").lower()

            if (player_lower in prop_player or prop_player in player_lower):
                if stat_type.lower() in prop_market or prop_market in stat_type.lower():
                    prop_listed = True
                    break

        if not prop_listed:
            return PropValidationResult(
                is_valid=False,
                player_prop_listed=False,
                injury_verified=injury_status is None,
                injury_status=injury_status.upper() if injury_status else None,
                block_reason=f"Player {player_name} {stat_type} not offered on {book}",
                book_checked=book
            )

    # 3. Check for warning statuses
    warning = None
    if injury_status and injury_status in WARN_STATUSES:
        warning = f"Player {player_name} is {injury_status.upper()} - proceed with caution"

    # Valid prop
    return PropValidationResult(
        is_valid=True,
        player_prop_listed=prop_listed,
        injury_verified=True,
        injury_status=injury_status.upper() if injury_status else "HEALTHY",
        warning=warning,
        book_checked=book
    )


def validate_props_batch(
    props: List[Dict[str, Any]],
    injuries_data: List[Dict[str, Any]],
    available_props: Optional[List[Dict[str, Any]]] = None,
    book: str = "draftkings"
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validate a batch of props and separate valid from invalid.

    Args:
        props: List of prop picks
        injuries_data: List of injury reports
        available_props: Optional list of props offered by book
        book: Sportsbook to check

    Returns:
        Tuple of (valid_props, invalid_props)
    """
    valid = []
    invalid = []

    for prop in props:
        player_name = prop.get("player_name") or prop.get("player") or ""
        stat_type = prop.get("stat_type") or prop.get("market") or ""

        result = validate_prop(
            player_name=player_name,
            stat_type=stat_type,
            injuries_data=injuries_data,
            available_props=available_props,
            book=book
        )

        # Add validation result to prop
        prop["validation"] = result.to_dict()
        prop["injury_verified"] = result.injury_verified
        prop["player_prop_listed"] = result.player_prop_listed

        if result.is_valid:
            if result.warning:
                prop["injury_warning"] = result.warning
            valid.append(prop)
        else:
            # Mark as blocked
            prop["tier"] = "PASS"
            prop["action"] = "SKIP"
            prop["block_reason"] = result.block_reason
            invalid.append(prop)

    logger.info(f"Prop validation: {len(valid)} valid, {len(invalid)} blocked")
    return valid, invalid


def get_injury_status(
    player_name: str,
    injuries_data: List[Dict[str, Any]]
) -> Optional[str]:
    """
    Get injury status for a player.

    Args:
        player_name: Player name
        injuries_data: List of injury reports

    Returns:
        Injury status string or None if not found
    """
    player_lower = player_name.lower().strip()

    for injury in injuries_data:
        inj_player = (injury.get("player") or injury.get("name") or "").lower().strip()
        if player_lower in inj_player or inj_player in player_lower:
            return (injury.get("status") or injury.get("injury_status") or "").upper()

    return None


def is_player_available(
    player_name: str,
    injuries_data: List[Dict[str, Any]]
) -> bool:
    """
    Check if a player is available to play.

    Args:
        player_name: Player name
        injuries_data: List of injury reports

    Returns:
        True if player is available (not OUT/DNP)
    """
    status = get_injury_status(player_name, injuries_data)
    if status is None:
        return True  # Assume available if not in injury report

    return status.lower() not in BLOCK_STATUSES
