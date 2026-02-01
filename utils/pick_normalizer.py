"""
Pick Normalization Utilities

Normalizes pick objects to ensure consistent frontend rendering.
Every pick gets these guaranteed fields:
- pick_type: "player_prop" | "moneyline" | "spread" | "total"
- selection: team name or player name
- market_label: human readable ("Points", "Spread", etc.)
- side_label: "Over"/"Under" or team name
- bet_string: canonical display string
- odds_american: standardized odds field
- recommended_units: standardized units field
- id: stable identifier
"""


def normalize_market_label(market: str, stat_type: str = None) -> str:
    """Convert internal market codes to human-readable labels."""
    market_labels = {
        # Props
        "player_points": "Points",
        "player_rebounds": "Rebounds",
        "player_assists": "Assists",
        "player_threes": "3PT Made",
        "player_steals": "Steals",
        "player_blocks": "Blocks",
        "player_turnovers": "Turnovers",
        "player_pts_rebs": "Pts + Rebs",
        "player_pts_asts": "Pts + Asts",
        "player_rebs_asts": "Rebs + Asts",
        "player_pts_rebs_asts": "Pts + Rebs + Asts",
        "player_double_double": "Double Double",
        "player_triple_double": "Triple Double",
        "player_first_td": "First TD Scorer",
        "player_anytime_td": "Anytime TD",
        "player_goals": "Goals",
        "player_shots": "Shots on Goal",
        "player_saves": "Saves",
        # Game markets
        "spreads": "Spread",
        "spread": "Spread",
        "h2h": "Moneyline",
        "moneyline": "Moneyline",
        "totals": "Total",
        "total": "Total",
        "sharp_money": "Sharp Signal",
    }
    label = market_labels.get(market or "", market or "Unknown")
    if label == market and stat_type:
        label = market_labels.get(stat_type, stat_type.replace("_", " ").title())
    return label


def normalize_pick_type(pick: dict) -> str:
    """Determine normalized pick_type from pick data."""
    existing = pick.get("pick_type", "").upper()
    market = pick.get("market", "").lower()

    # Already normalized
    if existing in ("PLAYER_PROP", "MONEYLINE", "SPREAD", "TOTAL"):
        return existing.lower()

    # Props detection
    if pick.get("player") or pick.get("player_name") or "player_" in market:
        return "player_prop"

    # Game pick type detection
    if existing == "TOTAL" or market in ("totals", "total"):
        return "total"
    if existing == "SPREAD" or market in ("spreads", "spread"):
        return "spread"
    if existing in ("ML", "MONEYLINE", "H2H") or market in ("h2h", "moneyline"):
        return "moneyline"
    if existing == "SHARP" or market == "sharp_money":
        # Sharp picks are typically spread or ML based on line
        line = pick.get("line")
        if line is not None and line != 0:
            return "spread"
        return "moneyline"

    # Default based on presence of player
    return "spread" if pick.get("team") else "player_prop"


def normalize_selection(pick: dict, pick_type: str) -> str:
    """Get the selection (who/what to bet on) from pick data."""
    if pick_type == "player_prop":
        return pick.get("player_name") or pick.get("player") or "Unknown Player"
    if pick_type == "total":
        home = pick.get("home_team", "Home")
        away = pick.get("away_team", "Away")
        return f"{away}/{home}"
    # Spread or ML - return team
    return pick.get("team") or pick.get("side") or pick.get("home_team") or "Unknown Team"


def normalize_side_label(pick: dict, pick_type: str) -> str:
    """Get the side label for the bet."""
    side = pick.get("side", "")
    direction = pick.get("direction", "")
    over_under = pick.get("over_under", "")

    if pick_type in ("player_prop", "total"):
        # For props and totals, use Over/Under
        if side.lower() in ("over", "under"):
            return side.title()
        if direction.upper() in ("OVER", "UNDER"):
            return direction.title()
        if over_under.lower() in ("over", "under"):
            return over_under.title()
        return "Over"  # Default

    # For spread/ML, use team name
    return pick.get("team") or pick.get("side") or "Unknown"


def build_bet_string(pick: dict, pick_type: str, selection: str, market_label: str, side_label: str) -> str:
    """Build canonical bet display string."""
    line = pick.get("line")
    odds = pick.get("odds", pick.get("odds_american", -110))
    units = pick.get("units", 1.0)

    # Format odds
    odds_str = f"+{odds}" if odds > 0 else str(odds)
    units_str = f"{units}u"

    if pick_type == "player_prop":
        # "Sam Hauser — 3PT Made Over 4.5 (+130) — 2u"
        line_str = f" {line}" if line is not None else ""
        return f"{selection} — {market_label} {side_label}{line_str} ({odds_str}) — {units_str}"

    if pick_type == "total":
        # "Bucks/Celtics Over 228.5 (-110) — 1u"
        line_str = f" {line}" if line is not None else ""
        return f"{selection} {side_label}{line_str} ({odds_str}) — {units_str}"

    if pick_type == "spread":
        # "Boston Celtics -4.5 (-105) — 1u"
        if line is not None:
            line_str = f"+{line}" if line > 0 else str(line)
            return f"{selection} {line_str} ({odds_str}) — {units_str}"
        return f"{selection} ({odds_str}) — {units_str}"

    # Moneyline: "Milwaukee Bucks Moneyline (-110) — 1u"
    return f"{selection} Moneyline ({odds_str}) — {units_str}"


def normalize_pick(pick: dict) -> dict:
    """Add normalized fields to a pick for frontend rendering.

    Adds these guaranteed fields:
    - pick_type: "player_prop" | "moneyline" | "spread" | "total"
    - selection: team name or player name
    - market_label: human readable ("Points", "Spread", etc.)
    - side_label: "Over"/"Under" or team name
    - bet_string: canonical display string
    - odds_american: standardized odds field
    - recommended_units: standardized units field
    """
    if not isinstance(pick, dict):
        return pick

    # Derive normalized values
    pick_type = normalize_pick_type(pick)
    market = pick.get("market", pick.get("prop_type", pick.get("stat_type", "")))
    stat_type = pick.get("stat_type", pick.get("prop_type", ""))
    market_label = normalize_market_label(market, stat_type)
    selection = normalize_selection(pick, pick_type)
    side_label = normalize_side_label(pick, pick_type)
    bet_string = build_bet_string(pick, pick_type, selection, market_label, side_label)

    # Add normalized fields (keep originals for backward compat)
    pick["pick_type"] = pick_type
    pick["selection"] = selection
    pick["market_label"] = market_label
    pick["side_label"] = side_label
    pick["bet_string"] = bet_string
    pick["odds_american"] = pick.get("odds", pick.get("odds_american", -110))
    pick["recommended_units"] = pick.get("units", 1.0)

    # Ensure id exists
    if "id" not in pick:
        pick["id"] = pick.get("pick_id", pick.get("event_id", "unknown"))

    return pick


def normalize_best_bets_response(payload: dict) -> dict:
    """Normalize all picks in a best-bets response."""
    if not isinstance(payload, dict):
        return payload

    # Normalize props picks
    props = payload.get("props", {})
    if isinstance(props, dict) and "picks" in props:
        props["picks"] = [normalize_pick(p) for p in props.get("picks", [])]

    # Normalize game picks
    game_picks = payload.get("game_picks", {})
    if isinstance(game_picks, dict) and "picks" in game_picks:
        game_picks["picks"] = [normalize_pick(p) for p in game_picks.get("picks", [])]

    return payload
