# jason_sim_confluence.py - Jason Sim 2.0 Post-Pick Confluence Layer
# Version: 1.0
#
# Jason Sim is a POST-PICK layer that can BOOST / DOWNGRADE / BLOCK existing picks.
# It CANNOT generate picks by itself - only modifies picks already produced by SMASH SPOT.
#
# STRICT RULES:
# - Do NOT use betting odds in Jason integration
# - Use ONLY injury-adjusted win% (win_pct_injury_adj) for decisions
# - Injury state must be CONFIRMED_ONLY (no speculative injury projections)
# - Final output must explain the Jason effect using confluence_reasons
# - final_score = base_score + jason_sim_boost (additive, NEVER overwrite)

import logging
from typing import Dict, Any, List, Optional, Tuple

# v10.55: Import tiering module - single source of truth for tier assignment
from tiering import tier_from_score as tiering_tier_from_score

logger = logging.getLogger("jason_sim")

# ============================================================================
# CONFIGURATION CONSTANTS (tunable)
# ============================================================================

# Variance thresholds for std_dev_total
VARIANCE_HIGH_THRESHOLD = 19.0
VARIANCE_LOW_THRESHOLD = 16.5

# Game pick boost/downgrade thresholds (win%)
WIN_PCT_BOOST_DOMINANT = 0.66  # +0.55
WIN_PCT_BOOST_STANDARD = 0.61  # +0.35
WIN_PCT_DOWNGRADE_MILD = 0.55  # -0.25
WIN_PCT_DOWNGRADE_SEVERE = 0.52  # -0.50
WIN_PCT_BLOCK_THRESHOLD = 0.52  # Block if < this AND base_score < 7.2

# Game pick boost values
BOOST_DOMINANT = 0.55
BOOST_STANDARD = 0.35
DOWNGRADE_MILD = -0.25
DOWNGRADE_SEVERE = -0.50

# Block threshold for base_score
BLOCK_BASE_SCORE_THRESHOLD = 7.2

# Totals thresholds
TOTALS_HIGH_PROJECTED = 228.0
TOTALS_LOW_PROJECTED = 222.0
TOTALS_BOOST = 0.20
TOTALS_DOWNGRADE = -0.20

# Props thresholds
PROP_BASE_SCORE_MIN = 6.8
PACE_HIGH_THRESHOLD = 99.0
PACE_LOW_THRESHOLD = 96.0
PROP_BOOST = 0.20
PROP_DOWNGRADE = -0.20

# Final score cap
FINAL_SCORE_CAP = 9.99


# ============================================================================
# NORMALIZATION: Convert Jason payload to internal fields
# ============================================================================

def normalize_jason_sim(
    game_id: str,
    home_team: str,
    away_team: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Normalize Jason Sim payload into internal SMASH SPOT format.

    Jason keys may come as TEAM_A/TEAM_B or actual team names.
    We map them correctly to home/away based on the matchup definition.

    Args:
        game_id: Unique game identifier
        home_team: Home team name/abbr
        away_team: Away team name/abbr
        payload: Raw Jason Sim JSON payload

    Returns:
        Normalized dict with standardized fields
    """
    if not payload:
        return {
            "game_id": game_id,
            "home_team": home_team,
            "away_team": away_team,
            "valid": False,
            "error": "Missing payload"
        }

    results = payload.get("results", {})

    # Extract win percentages (injury-adjusted ONLY)
    win_pct_adj = results.get("win_pct_injury_adj", {})

    # Map TEAM_A/TEAM_B to home/away
    # Convention: TEAM_A is typically the first team listed (home)
    # But we need to handle both conventions
    win_pct_home = None
    win_pct_away = None

    if home_team in win_pct_adj:
        win_pct_home = win_pct_adj.get(home_team)
        win_pct_away = win_pct_adj.get(away_team)
    elif "TEAM_A" in win_pct_adj:
        # TEAM_A = home, TEAM_B = away (standard convention)
        win_pct_home = win_pct_adj.get("TEAM_A")
        win_pct_away = win_pct_adj.get("TEAM_B")
    else:
        # Try to find any keys that might match
        for key, val in win_pct_adj.items():
            key_lower = key.lower()
            if home_team.lower() in key_lower or key_lower in home_team.lower():
                win_pct_home = val
            elif away_team.lower() in key_lower or key_lower in away_team.lower():
                win_pct_away = val

    # Extract score projection
    score_proj = results.get("score_projection", {})
    projected_total = score_proj.get("projected_total_points")
    projected_pace = score_proj.get("projected_pace")
    std_dev_total = score_proj.get("std_dev_total")
    std_dev_margin = score_proj.get("std_dev_margin")

    # Mean margin - map to home team
    mean_margin_home = score_proj.get("mean_margin_team_a")
    if mean_margin_home is None:
        mean_margin_home = score_proj.get("mean_margin_home")

    # Extract confidence labels
    confidence_data = results.get("confidence", {})
    confidence_label_home = None
    confidence_label_away = None

    if home_team in confidence_data:
        confidence_label_home = confidence_data[home_team].get("confidence_label")
    elif "TEAM_A" in confidence_data:
        confidence_label_home = confidence_data["TEAM_A"].get("confidence_label")

    if away_team in confidence_data:
        confidence_label_away = confidence_data[away_team].get("confidence_label")
    elif "TEAM_B" in confidence_data:
        confidence_label_away = confidence_data["TEAM_B"].get("confidence_label")

    # Compute variance flag
    variance_flag = compute_variance_flag(std_dev_total)

    # Check if we have minimum required fields
    valid = (
        win_pct_home is not None and
        win_pct_away is not None and
        projected_total is not None and
        std_dev_total is not None
    )

    return {
        "game_id": game_id,
        "home_team": home_team,
        "away_team": away_team,
        "valid": valid,

        "sim_count": payload.get("sim_runs_per_game", 10000),

        "win_pct_home": win_pct_home,
        "win_pct_away": win_pct_away,

        "projected_total": projected_total,
        "projected_pace": projected_pace,
        "mean_margin_home": mean_margin_home,
        "std_dev_margin": std_dev_margin,
        "std_dev_total": std_dev_total,

        "variance_flag": variance_flag,

        "confidence_label_home": confidence_label_home,
        "confidence_label_away": confidence_label_away,

        "injury_state": "CONFIRMED_ONLY"
    }


def compute_variance_flag(std_dev_total: Optional[float]) -> str:
    """
    Compute variance flag from std_dev_total.

    HIGH: std_dev_total >= 19.0
    LOW: std_dev_total <= 16.5
    MED: everything else
    """
    if std_dev_total is None:
        return "MED"  # Default when missing

    if std_dev_total >= VARIANCE_HIGH_THRESHOLD:
        return "HIGH"
    elif std_dev_total <= VARIANCE_LOW_THRESHOLD:
        return "LOW"
    else:
        return "MED"


# ============================================================================
# APPLY JASON SIM TO SINGLE PICK
# ============================================================================

def apply_jason_sim_to_pick(
    pick: Dict[str, Any],
    jason_game: Optional[Dict[str, Any]],
    pick_type: str = "game"  # "game", "total", "prop"
) -> Tuple[Dict[str, Any], bool]:
    """
    Apply Jason Sim confluence to a single pick.

    Returns:
        Tuple of (modified_pick, blocked)
        - blocked=True means pick should be removed from output
    """
    # Initialize Jason fields on pick
    pick["jason_sim_used"] = False
    pick["jason_sim_win_pct"] = None
    pick["jason_sim_confidence"] = None
    pick["jason_sim_projected_total"] = None
    pick["jason_sim_projected_pace"] = None
    pick["jason_sim_variance_flag"] = None
    pick["jason_sim_boost"] = 0.0

    # Ensure confluence_reasons exists
    if "confluence_reasons" not in pick:
        pick["confluence_reasons"] = []
    if "reasons" not in pick:
        pick["reasons"] = []

    # Handle missing payload
    if not jason_game or not jason_game.get("valid", False):
        pick["confluence_reasons"].append("JASON_SIM: missing payload -> no adjustment")
        return pick, False

    # Populate Jason fields
    pick["jason_sim_used"] = True
    pick["jason_sim_projected_total"] = jason_game.get("projected_total")
    pick["jason_sim_projected_pace"] = jason_game.get("projected_pace")
    pick["jason_sim_variance_flag"] = jason_game.get("variance_flag", "MED")

    # Get base score
    base_score = pick.get("total_score", pick.get("smash_score", 5.0))

    # Determine pick side for win% lookup
    pick_side = determine_pick_side(pick, jason_game)

    if pick_side == "home":
        pick["jason_sim_win_pct"] = jason_game.get("win_pct_home")
        pick["jason_sim_confidence"] = jason_game.get("confidence_label_home")
    elif pick_side == "away":
        pick["jason_sim_win_pct"] = jason_game.get("win_pct_away")
        pick["jason_sim_confidence"] = jason_game.get("confidence_label_away")

    # Determine pick category and apply appropriate logic
    market = pick.get("market", pick.get("stat_type", "")).lower()
    over_under = pick.get("over_under", pick.get("side", "")).lower()

    # Categorize the pick
    if "total" in market or market in ["over", "under"]:
        pick_category = "total"
    elif "spread" in market or "h2h" in market or "moneyline" in market or "ml" in market:
        pick_category = "game"
    elif any(x in market for x in ["points", "rebounds", "assists", "threes", "3pt", "passing", "rushing", "receiving", "goals", "hits"]):
        pick_category = "prop"
    else:
        pick_category = pick_type  # Use provided type as fallback

    # Apply category-specific logic
    boost = 0.0
    blocked = False

    if pick_category == "game":
        boost, blocked, reasons = apply_game_pick_logic(
            pick, jason_game, base_score
        )
    elif pick_category == "total":
        boost, reasons = apply_totals_logic(pick, jason_game, over_under)
    elif pick_category == "prop":
        boost, reasons = apply_prop_logic(pick, jason_game, base_score, over_under)
    else:
        reasons = ["JASON_SIM: unknown pick category -> no adjustment"]

    # Apply boost to pick
    pick["jason_sim_boost"] = round(boost, 2)
    pick["confluence_reasons"].extend(reasons)
    pick["reasons"].extend(reasons)

    # Recompute final_score
    if boost != 0:
        new_score = base_score + boost
        new_score = min(new_score, FINAL_SCORE_CAP)
        new_score = max(new_score, 0.0)
        pick["total_score"] = round(new_score, 2)
        pick["smash_score"] = round(new_score, 2)

        # Recompute tier
        pick["bet_tier"] = recompute_tier(new_score, pick.get("bet_tier", {}))

    return pick, blocked


def determine_pick_side(pick: Dict[str, Any], jason_game: Dict[str, Any]) -> Optional[str]:
    """
    Determine if pick is for home or away team.
    """
    home_team = jason_game.get("home_team", "").lower()
    away_team = jason_game.get("away_team", "").lower()

    # Check various pick fields for team indication
    pick_team = (
        pick.get("team", "") or
        pick.get("pick_team", "") or
        pick.get("side", "") or
        ""
    ).lower()

    # Check player team for props
    player_team = (pick.get("player_team", "") or "").lower()

    # Match against home/away
    for team_str in [pick_team, player_team]:
        if not team_str:
            continue
        if home_team and (home_team in team_str or team_str in home_team):
            return "home"
        if away_team and (away_team in team_str or team_str in away_team):
            return "away"

    # Default to home if can't determine
    return "home"


def apply_game_pick_logic(
    pick: Dict[str, Any],
    jason_game: Dict[str, Any],
    base_score: float
) -> Tuple[float, bool, List[str]]:
    """
    Apply Jason Sim logic for spread/moneyline picks.

    Uses injury-adjusted win% ALWAYS.

    Returns: (boost, blocked, reasons)
    """
    reasons = []
    boost = 0.0
    blocked = False

    win_pct = pick.get("jason_sim_win_pct")

    if win_pct is None:
        reasons.append("JASON_SIM: win_pct unavailable -> no adjustment")
        return boost, blocked, reasons

    # BOOST logic
    if win_pct >= WIN_PCT_BOOST_DOMINANT:
        boost = BOOST_DOMINANT
        reasons.append(f"JASON_SIM: win%={win_pct:.2%} -> DOMINANT BOOST (+{BOOST_DOMINANT})")
    elif win_pct >= WIN_PCT_BOOST_STANDARD:
        boost = BOOST_STANDARD
        reasons.append(f"JASON_SIM: win%={win_pct:.2%} -> BOOST (+{BOOST_STANDARD})")

    # DOWNGRADE logic
    elif win_pct <= WIN_PCT_DOWNGRADE_SEVERE:
        boost = DOWNGRADE_SEVERE
        reasons.append(f"JASON_SIM: win%={win_pct:.2%} -> SEVERE DOWNGRADE ({DOWNGRADE_SEVERE})")

        # BLOCK check
        if base_score < BLOCK_BASE_SCORE_THRESHOLD:
            blocked = True
            reasons.append(f"JASON_SIM: win%={win_pct:.2%} AND base_score={base_score:.2f} < {BLOCK_BASE_SCORE_THRESHOLD} -> BLOCKED")

    elif win_pct <= WIN_PCT_DOWNGRADE_MILD:
        boost = DOWNGRADE_MILD
        reasons.append(f"JASON_SIM: win%={win_pct:.2%} -> DOWNGRADE ({DOWNGRADE_MILD})")

    else:
        reasons.append(f"JASON_SIM: win%={win_pct:.2%} -> neutral (no adjustment)")

    return boost, blocked, reasons


def apply_totals_logic(
    pick: Dict[str, Any],
    jason_game: Dict[str, Any],
    over_under: str
) -> Tuple[float, List[str]]:
    """
    Apply Jason Sim logic for totals (over/under) picks.

    Uses projected_total + variance_flag.

    Returns: (boost, reasons)
    """
    reasons = []
    boost = 0.0

    projected_total = jason_game.get("projected_total")
    variance_flag = jason_game.get("variance_flag", "MED")

    if projected_total is None:
        reasons.append("JASON_SIM: projected_total unavailable -> no adjustment")
        return boost, reasons

    is_over = "over" in over_under.lower()
    is_under = "under" in over_under.lower()

    if is_over:
        # OVER logic
        if projected_total >= TOTALS_HIGH_PROJECTED and variance_flag != "HIGH":
            boost = TOTALS_BOOST
            reasons.append(f"JASON_SIM: projected_total={projected_total:.1f} variance={variance_flag} -> totals BOOST (+{TOTALS_BOOST})")
        elif projected_total <= TOTALS_LOW_PROJECTED:
            boost = TOTALS_DOWNGRADE
            reasons.append(f"JASON_SIM: projected_total={projected_total:.1f} low -> totals DOWNGRADE ({TOTALS_DOWNGRADE})")
        elif variance_flag == "HIGH":
            boost = TOTALS_DOWNGRADE
            reasons.append(f"JASON_SIM: variance HIGH -> totals DOWNGRADE ({TOTALS_DOWNGRADE})")
        else:
            reasons.append(f"JASON_SIM: projected_total={projected_total:.1f} variance={variance_flag} -> neutral")

    elif is_under:
        # UNDER logic
        if projected_total <= TOTALS_LOW_PROJECTED and variance_flag != "HIGH":
            boost = TOTALS_BOOST
            reasons.append(f"JASON_SIM: projected_total={projected_total:.1f} variance={variance_flag} -> totals BOOST (+{TOTALS_BOOST})")
        elif projected_total >= TOTALS_HIGH_PROJECTED:
            boost = TOTALS_DOWNGRADE
            reasons.append(f"JASON_SIM: projected_total={projected_total:.1f} high -> totals DOWNGRADE ({TOTALS_DOWNGRADE})")
        elif variance_flag == "HIGH":
            boost = TOTALS_DOWNGRADE
            reasons.append(f"JASON_SIM: variance HIGH -> totals DOWNGRADE ({TOTALS_DOWNGRADE})")
        else:
            reasons.append(f"JASON_SIM: projected_total={projected_total:.1f} variance={variance_flag} -> neutral")

    else:
        reasons.append("JASON_SIM: over_under not specified -> no adjustment")

    return boost, reasons


def apply_prop_logic(
    pick: Dict[str, Any],
    jason_game: Dict[str, Any],
    base_score: float,
    over_under: str
) -> Tuple[float, List[str]]:
    """
    Apply Jason Sim logic for player prop picks.

    Jason does NOT simulate player props - only uses game environment as confluence.
    Prop boost gated by base_prop_score >= 6.8.

    Returns: (boost, reasons)
    """
    reasons = []
    boost = 0.0

    # Gate: Only apply to quality props
    if base_score < PROP_BASE_SCORE_MIN:
        reasons.append(f"JASON_SIM: base_prop_score={base_score:.2f} < {PROP_BASE_SCORE_MIN} -> no boost applied")
        return boost, reasons

    projected_total = jason_game.get("projected_total")
    projected_pace = jason_game.get("projected_pace")

    if projected_total is None:
        reasons.append("JASON_SIM: projected_total unavailable -> no prop adjustment")
        return boost, reasons

    is_over = "over" in over_under.lower()
    is_under = "under" in over_under.lower()

    # Determine prop type (points/threes vs other)
    market = pick.get("market", pick.get("stat_type", "")).lower()
    is_scoring_prop = any(x in market for x in ["points", "threes", "3pt", "scoring"])

    if is_over and is_scoring_prop:
        # Points/threes OVER - benefits from high pace/total
        if projected_total >= TOTALS_HIGH_PROJECTED or (projected_pace and projected_pace >= PACE_HIGH_THRESHOLD):
            boost = PROP_BOOST
            pace_str = f" pace={projected_pace:.1f}" if projected_pace else ""
            reasons.append(f"JASON_SIM: environment supports OVER (total={projected_total:.1f}{pace_str}) -> +{PROP_BOOST}")
        elif projected_total <= TOTALS_LOW_PROJECTED and (not projected_pace or projected_pace <= PACE_LOW_THRESHOLD):
            boost = PROP_DOWNGRADE
            pace_str = f" pace={projected_pace:.1f}" if projected_pace else ""
            reasons.append(f"JASON_SIM: environment opposes OVER (total={projected_total:.1f}{pace_str}) -> {PROP_DOWNGRADE}")
        else:
            reasons.append(f"JASON_SIM: environment neutral for OVER prop")

    elif is_under and is_scoring_prop:
        # Points/threes UNDER - benefits from low pace/total
        if projected_total <= TOTALS_LOW_PROJECTED and (not projected_pace or projected_pace <= PACE_LOW_THRESHOLD):
            boost = PROP_BOOST
            pace_str = f" pace={projected_pace:.1f}" if projected_pace else ""
            reasons.append(f"JASON_SIM: environment supports UNDER (total={projected_total:.1f}{pace_str}) -> +{PROP_BOOST}")
        elif projected_total >= TOTALS_HIGH_PROJECTED or (projected_pace and projected_pace >= PACE_HIGH_THRESHOLD):
            boost = PROP_DOWNGRADE
            pace_str = f" pace={projected_pace:.1f}" if projected_pace else ""
            reasons.append(f"JASON_SIM: environment opposes UNDER (total={projected_total:.1f}{pace_str}) -> {PROP_DOWNGRADE}")
        else:
            reasons.append(f"JASON_SIM: environment neutral for UNDER prop")

    else:
        # Non-scoring props or unspecified direction
        reasons.append(f"JASON_SIM: non-scoring prop or direction unclear -> minimal environment impact")

    return boost, reasons


def recompute_tier(score: float, current_tier: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recompute bet tier based on new score.

    v10.55: Uses tiering module for consistent thresholds.
    """
    # v10.55: Use tiering module for consistent tier assignment
    tier, _ = tiering_tier_from_score(score)

    tier_map = {
        "GOLD_STAR": {"units": 2.0, "action": "SMASH"},
        "EDGE_LEAN": {"units": 1.0, "action": "PLAY"},
        "MONITOR": {"units": 0.0, "action": "WATCH"},
        "PASS": {"units": 0.0, "action": "SKIP"},
    }
    config = tier_map.get(tier, tier_map["PASS"])

    return {
        "tier": tier,
        "units": config["units"],
        "action": config["action"]
    }


# ============================================================================
# APPLY JASON SIM LAYER TO ALL PICKS
# ============================================================================

def apply_jason_sim_layer(
    picks: List[Dict[str, Any]],
    jason_payloads_by_game: Dict[str, Dict[str, Any]],
    pick_type: str = "game"
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Apply Jason Sim confluence layer to all picks.

    Args:
        picks: List of pick dicts from SMASH SPOT
        jason_payloads_by_game: Dict mapping game_id -> normalized Jason payload
        pick_type: Default pick type ("game", "total", "prop")

    Returns:
        Tuple of (modified_picks, debug_stats)
        - modified_picks: Picks with Jason adjustments (blocked picks removed)
        - debug_stats: Stats for debug output
    """
    debug_stats = {
        "games_checked": 0,
        "games_matched": 0,
        "boosted": 0,
        "downgraded": 0,
        "blocked": 0,
        "missing_payload": 0
    }

    modified_picks = []

    for pick in picks:
        # Get game identifier from pick
        game_id = get_game_id_from_pick(pick)
        debug_stats["games_checked"] += 1

        # Look up Jason payload
        jason_game = None
        if game_id and game_id in jason_payloads_by_game:
            jason_game = jason_payloads_by_game[game_id]
            debug_stats["games_matched"] += 1
        else:
            # Try alternate lookups
            for alt_id in generate_alternate_game_ids(pick):
                if alt_id in jason_payloads_by_game:
                    jason_game = jason_payloads_by_game[alt_id]
                    debug_stats["games_matched"] += 1
                    break

        if not jason_game:
            debug_stats["missing_payload"] += 1

        # Apply Jason Sim to pick
        modified_pick, blocked = apply_jason_sim_to_pick(
            pick.copy(),  # Don't mutate original
            jason_game,
            pick_type
        )

        if blocked:
            debug_stats["blocked"] += 1
            continue  # Remove blocked pick

        # Track boost/downgrade
        boost = modified_pick.get("jason_sim_boost", 0)
        if boost > 0:
            debug_stats["boosted"] += 1
        elif boost < 0:
            debug_stats["downgraded"] += 1

        modified_picks.append(modified_pick)

    return modified_picks, debug_stats


def get_game_id_from_pick(pick: Dict[str, Any]) -> Optional[str]:
    """
    Extract game identifier from pick dict.
    """
    # Try various fields
    game_id = (
        pick.get("game_id") or
        pick.get("event_id") or
        pick.get("game_key") or
        None
    )

    if not game_id:
        # Construct from teams
        home = pick.get("home_team", "")
        away = pick.get("away_team", "")
        if home and away:
            game_id = f"{away}@{home}"

    return game_id


def generate_alternate_game_ids(pick: Dict[str, Any]) -> List[str]:
    """
    Generate alternate game ID formats for lookup.
    """
    alternates = []

    home = pick.get("home_team", "")
    away = pick.get("away_team", "")
    game = pick.get("game", "")

    if home and away:
        alternates.append(f"{away}@{home}")
        alternates.append(f"{away} @ {home}")
        alternates.append(f"{away} at {home}")
        alternates.append(f"{home}_vs_{away}")
        alternates.append(f"{away}_at_{home}")

    if game:
        alternates.append(game)
        # Parse "Team A @ Team B" format
        if "@" in game:
            parts = game.split("@")
            if len(parts) == 2:
                alternates.append(f"{parts[0].strip()}@{parts[1].strip()}")

    return alternates


# ============================================================================
# BUILD JASON PAYLOADS LOOKUP
# ============================================================================

def build_jason_payloads_lookup(
    jason_payloads: List[Dict[str, Any]],
    games_metadata: Optional[Dict[str, Dict[str, str]]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Build a lookup dict from raw Jason payloads.

    Args:
        jason_payloads: List of raw Jason Sim payloads
        games_metadata: Optional dict mapping game_id -> {home_team, away_team}

    Returns:
        Dict mapping game_id -> normalized Jason payload
    """
    lookup = {}

    for idx, payload in enumerate(jason_payloads):
        # Extract game info
        game_id = payload.get("game_id")
        home_team = payload.get("home_team", "")
        away_team = payload.get("away_team", "")

        # If game_id missing, try to construct from teams
        if not game_id and home_team and away_team:
            game_id = f"{away_team}@{home_team}"

        # If still missing, try games_metadata
        if not game_id and games_metadata and idx < len(games_metadata):
            meta = list(games_metadata.values())[idx] if isinstance(games_metadata, dict) else None
            if meta:
                game_id = f"{meta.get('away_team', '')}@{meta.get('home_team', '')}"
                home_team = meta.get("home_team", home_team)
                away_team = meta.get("away_team", away_team)

        if not game_id:
            logger.warning(f"Jason payload {idx} missing game_id, skipping")
            continue

        # Normalize the payload
        normalized = normalize_jason_sim(
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            payload=payload
        )

        # Store under multiple keys for flexible lookup
        lookup[game_id] = normalized

        # Also store alternate formats
        if home_team and away_team:
            lookup[f"{away_team}@{home_team}"] = normalized
            lookup[f"{away_team} @ {home_team}"] = normalized
            lookup[f"{home_team}_vs_{away_team}"] = normalized

    return lookup


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "normalize_jason_sim",
    "apply_jason_sim_to_pick",
    "apply_jason_sim_layer",
    "build_jason_payloads_lookup",
    "compute_variance_flag",
    # Constants for external tuning
    "VARIANCE_HIGH_THRESHOLD",
    "VARIANCE_LOW_THRESHOLD",
    "WIN_PCT_BOOST_DOMINANT",
    "WIN_PCT_BOOST_STANDARD",
    "WIN_PCT_DOWNGRADE_MILD",
    "WIN_PCT_DOWNGRADE_SEVERE",
    "WIN_PCT_BLOCK_THRESHOLD",
]
