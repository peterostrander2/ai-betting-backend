"""
Best-Bets Response Contract (FIX 1)

Guarantees NO KeyErrors - all keys always present.
"""

from typing import List, Dict, Any


def build_best_bets_response(
    sport: str,
    props_picks: List[Dict] = None,
    game_picks: List[Dict] = None,
    total_props_analyzed: int = 0,
    total_games_analyzed: int = 0,
    **kwargs
) -> Dict[str, Any]:
    """
    Single response builder used by all code paths.

    GUARANTEES:
    - props, games, meta keys ALWAYS present (never KeyError)
    - Empty arrays [] when no picks (not missing keys)
    - Works for all sports (NBA, NHL, NFL, MLB, NCAAB)

    Args:
        sport: Sport code (NBA, NHL, etc.)
        props_picks: List of prop pick dicts (defaults to [])
        game_picks: List of game pick dicts (defaults to [])
        total_props_analyzed: Total prop candidates analyzed
        total_games_analyzed: Total game candidates analyzed
        **kwargs: Optional fields (source, scoring_system, etc.)

    Returns:
        Dict with GUARANTEED keys: props, games, meta
    """
    # Default to empty lists (FIX 1: never None)
    if props_picks is None:
        props_picks = []
    if game_picks is None:
        game_picks = []

    # Build response with REQUIRED KEYS (FIX 1)
    response = {
        "sport": sport.upper(),
        "mode": kwargs.get("mode", "standard"),
        "source": kwargs.get("source", "jarvis_savant_v12.0"),
        "scoring_system": kwargs.get("scoring_system", "Phase 1-3 Integrated + Titanium v11.08"),
        "engine_version": kwargs.get("engine_version", "12.0"),
        "deploy_version": kwargs.get("deploy_version", "15.1"),
        "build_sha": kwargs.get("build_sha", "local"),
        "identity_resolver": kwargs.get("identity_resolver", False),
        "date_et": kwargs.get("date_et", ""),
        "run_timestamp_et": kwargs.get("run_timestamp_et", ""),

        # REQUIRED KEYS (FIX 1) - ALWAYS present
        "props": {
            "count": len(props_picks),
            "total_analyzed": total_props_analyzed,
            "picks": props_picks
        },
        "games": {
            "count": len(game_picks),
            "total_analyzed": total_games_analyzed,
            "picks": game_picks
        },
        "meta": kwargs.get("meta", {}),
    }

    # Optional fields (add if provided)
    if "esoteric" in kwargs:
        response["esoteric"] = kwargs["esoteric"]
    if "timestamp" in kwargs:
        response["timestamp"] = kwargs["timestamp"]
    if "debug" in kwargs:
        response["debug"] = kwargs["debug"]

    return response
