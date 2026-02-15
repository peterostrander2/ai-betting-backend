"""
PickContract v1 - Pick Normalization Utilities

Normalizes pick objects to ensure consistent frontend rendering.
This is the SINGLE SOURCE OF TRUTH for the pick contract.

CORE IDENTITY FIELDS:
- id: stable unique pick_id
- sport, league
- event_id
- matchup, home_team, away_team
- start_time_et (display string)
- start_time_iso (ISO string or null)
- status/has_started/is_live flags

BET INSTRUCTION FIELDS:
- pick_type: "spread" | "moneyline" | "total" | "player_prop"
- market_label: human label ("Spread", "Points", etc.)
- selection: exactly what user bets (team OR player)
- selection_home_away: "HOME" | "AWAY" | null
- line: numeric line value (null for pure ML)
- line_signed: "+1.0" / "-2.5" / "O 220.5" / "U 220.5"
- odds_american: number or null (NEVER fabricated)
- units: recommended bet units
- bet_string: final human-readable instruction
- book, book_link

REASONING FIELDS:
- tier, score, confidence_label
- signals_fired, confluence_reasons
- engine_breakdown
"""

from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:
    _ET = None

try:
    from core.time_et import get_game_start_time_et
    _TIME_ET_AVAILABLE = True
except Exception:
    _TIME_ET_AVAILABLE = False


def normalize_market_label(pick_type: str, stat_type: str = None) -> str:
    """Derive market_label from pick_type. For props, use stat category."""
    if pick_type == "player_prop":
        stat_labels = {
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
        }
        if stat_type:
            return stat_labels.get(stat_type, stat_type.replace("_", " ").replace("player ", "").title())
        return "Player Prop"
    elif pick_type == "spread":
        return "Spread"
    elif pick_type == "moneyline":
        return "Moneyline"
    elif pick_type == "total":
        return "Total"
    return "Unknown"


def get_signal_label(pick: dict) -> str:
    """Get signal label (e.g., 'Sharp Signal') separate from market type."""
    market = pick.get("market", "").lower()
    if market == "sharp_money":
        return "Sharp Signal"
    return None


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
        # Sharp picks: determine type based on line
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
        if isinstance(side, str) and side.lower() in ("over", "under"):
            return side.title()
        if isinstance(direction, str) and direction.upper() in ("OVER", "UNDER"):
            return direction.title()
        if isinstance(over_under, str) and over_under.lower() in ("over", "under"):
            return over_under.title()
        return "Over"  # Default

    # For spread/ML, use team name
    return pick.get("team") or pick.get("side") or "Unknown"

def resolve_home_away_intent(pick: dict) -> str:
    """Derive intended HOME/AWAY from pick_side hints."""
    pick_side = (pick.get("pick_side") or "").lower()
    if not pick_side:
        return ""
    if "home" in pick_side:
        return "HOME"
    if "away" in pick_side or "visitor" in pick_side:
        return "AWAY"
    return ""

def enforce_home_away_consistency(pick: dict) -> dict:
    """Final enforcement: align selection with HOME/AWAY intent for game picks."""
    pick_type = pick.get("pick_type")
    if pick_type not in ("spread", "moneyline"):
        return pick

    home_team = pick.get("home_team") or ""
    away_team = pick.get("away_team") or ""
    if not home_team or not away_team:
        return pick

    intent = resolve_home_away_intent(pick)
    if not intent:
        return pick

    desired_team = home_team if intent == "HOME" else away_team
    if not desired_team:
        return pick

    if pick.get("selection") != desired_team:
        correction_flags = pick.get("correction_flags") or []
        correction_flags.append("FIELD_CONTRADICTION_CORRECTED")
        pick["correction_flags"] = correction_flags
        pick["selection"] = desired_team
        pick["team"] = desired_team
        pick["side_label"] = desired_team
        pick["selection_home_away"] = intent

        # Rebuild bet_string with corrected selection
        market_label = pick.get("market_label") or normalize_market_label(pick_type, pick.get("stat_type", ""))
        line_signed = pick.get("line_signed")
        pick["bet_string"] = build_bet_string(
            pick,
            pick_type,
            desired_team,
            market_label,
            desired_team,
            line_signed if pick_type == "spread" else None
        )

    return pick


def get_team_abbrev(team_name: str) -> str:
    """Convert team name to 3-letter abbreviation."""
    if not team_name:
        return ""

    # Common team abbreviations
    abbrevs = {
        # NBA
        "atlanta hawks": "ATL", "boston celtics": "BOS", "brooklyn nets": "BKN",
        "charlotte hornets": "CHA", "chicago bulls": "CHI", "cleveland cavaliers": "CLE",
        "dallas mavericks": "DAL", "denver nuggets": "DEN", "detroit pistons": "DET",
        "golden state warriors": "GSW", "houston rockets": "HOU", "indiana pacers": "IND",
        "los angeles clippers": "LAC", "la clippers": "LAC", "los angeles lakers": "LAL",
        "la lakers": "LAL", "memphis grizzlies": "MEM", "miami heat": "MIA",
        "milwaukee bucks": "MIL", "minnesota timberwolves": "MIN", "new orleans pelicans": "NOP",
        "new york knicks": "NYK", "oklahoma city thunder": "OKC", "orlando magic": "ORL",
        "philadelphia 76ers": "PHI", "phoenix suns": "PHX", "portland trail blazers": "POR",
        "sacramento kings": "SAC", "san antonio spurs": "SAS", "toronto raptors": "TOR",
        "utah jazz": "UTA", "washington wizards": "WAS",
        # NHL
        "anaheim ducks": "ANA", "arizona coyotes": "ARI", "boston bruins": "BOS",
        "buffalo sabres": "BUF", "calgary flames": "CGY", "carolina hurricanes": "CAR",
        "chicago blackhawks": "CHI", "colorado avalanche": "COL", "columbus blue jackets": "CBJ",
        "dallas stars": "DAL", "detroit red wings": "DET", "edmonton oilers": "EDM",
        "florida panthers": "FLA", "los angeles kings": "LAK", "minnesota wild": "MIN",
        "montreal canadiens": "MTL", "nashville predators": "NSH", "new jersey devils": "NJD",
        "new york islanders": "NYI", "new york rangers": "NYR", "ottawa senators": "OTT",
        "philadelphia flyers": "PHI", "pittsburgh penguins": "PIT", "san jose sharks": "SJS",
        "seattle kraken": "SEA", "st. louis blues": "STL", "st louis blues": "STL",
        "tampa bay lightning": "TBL", "toronto maple leafs": "TOR", "vancouver canucks": "VAN",
        "vegas golden knights": "VGK", "washington capitals": "WSH", "winnipeg jets": "WPG",
        # NFL
        "arizona cardinals": "ARI", "atlanta falcons": "ATL", "baltimore ravens": "BAL",
        "buffalo bills": "BUF", "carolina panthers": "CAR", "chicago bears": "CHI",
        "cincinnati bengals": "CIN", "cleveland browns": "CLE", "dallas cowboys": "DAL",
        "denver broncos": "DEN", "detroit lions": "DET", "green bay packers": "GB",
        "houston texans": "HOU", "indianapolis colts": "IND", "jacksonville jaguars": "JAX",
        "kansas city chiefs": "KC", "las vegas raiders": "LV", "los angeles chargers": "LAC",
        "los angeles rams": "LAR", "miami dolphins": "MIA", "minnesota vikings": "MIN",
        "new england patriots": "NE", "new orleans saints": "NO", "new york giants": "NYG",
        "new york jets": "NYJ", "philadelphia eagles": "PHI", "pittsburgh steelers": "PIT",
        "san francisco 49ers": "SF", "seattle seahawks": "SEA", "tampa bay buccaneers": "TB",
        "tennessee titans": "TEN", "washington commanders": "WAS",
        # MLB
        "arizona diamondbacks": "ARI", "atlanta braves": "ATL", "baltimore orioles": "BAL",
        "boston red sox": "BOS", "chicago cubs": "CHC", "chicago white sox": "CWS",
        "cincinnati reds": "CIN", "cleveland guardians": "CLE", "colorado rockies": "COL",
        "detroit tigers": "DET", "houston astros": "HOU", "kansas city royals": "KC",
        "los angeles angels": "LAA", "los angeles dodgers": "LAD", "miami marlins": "MIA",
        "milwaukee brewers": "MIL", "minnesota twins": "MIN", "new york mets": "NYM",
        "new york yankees": "NYY", "oakland athletics": "OAK", "philadelphia phillies": "PHI",
        "pittsburgh pirates": "PIT", "san diego padres": "SD", "san francisco giants": "SF",
        "seattle mariners": "SEA", "st. louis cardinals": "STL", "st louis cardinals": "STL",
        "tampa bay rays": "TB", "texas rangers": "TEX", "toronto blue jays": "TOR",
        "washington nationals": "WAS",
    }

    key = team_name.lower().strip()
    return abbrevs.get(key, team_name[:3].upper())


def build_bet_string(pick: dict, pick_type: str, selection: str, market_label: str, side_label: str, line_signed: str = None) -> str:
    """Build canonical bet display string."""
    line = pick.get("line")
    odds = pick.get("odds") or pick.get("odds_american")
    units = pick.get("units", 1.0)

    # Format odds - don't fabricate if missing
    if odds is not None:
        odds_str = f"+{odds}" if odds > 0 else str(odds)
    else:
        odds_str = "—"
    units_str = f"{units}u"

    if pick_type == "player_prop":
        # "Sam Hauser (BOS) — 3PT Made Over 4.5 (+130) — 2u"
        player_team = pick.get("player_team") or ""

        # Fallback: extract team from canonical_player_id (e.g., "NBA:NAME:sam_hauser|boston_celtics")
        if not player_team:
            canonical_id = pick.get("canonical_player_id") or ""
            if "|" in canonical_id:
                team_part = canonical_id.split("|")[-1]  # "boston_celtics"
                player_team = team_part.replace("_", " ").title()  # "Boston Celtics"

        team_abbrev = get_team_abbrev(player_team)
        team_str = f" ({team_abbrev})" if team_abbrev else ""
        line_str = f" {line}" if line is not None else ""
        return f"{selection}{team_str} — {market_label} {side_label}{line_str} ({odds_str}) — {units_str}"

    if pick_type == "total":
        # "Bucks/Celtics Over 228.5 (-110) — 1u"
        line_str = f" {line}" if line is not None else ""
        return f"{selection} {side_label}{line_str} ({odds_str}) — {units_str}"

    if pick_type == "spread":
        # "Boston Celtics -4.5 (-105) — 1u"
        if line_signed:
            return f"{selection} {line_signed} ({odds_str}) — {units_str}"
        return f"{selection} ({odds_str}) — {units_str}"

    # Moneyline: "Milwaukee Bucks ML (-110) — 1u"
    return f"{selection} ML ({odds_str}) — {units_str}"


def normalize_pick(pick: dict) -> dict:
    """
    PickContract v1: Normalize pick to guarantee all required fields.
    """
    if not isinstance(pick, dict):
        return pick

    # === CORE IDENTITY ===
    pick["id"] = pick.get("id") or pick.get("pick_id") or pick.get("event_id") or "unknown"
    pick["sport"] = (pick.get("sport") or "").upper() or "UNKNOWN"
    pick["league"] = pick.get("league") or pick.get("sport", "").upper() or "UNKNOWN"
    pick["event_id"] = pick.get("event_id") or pick.get("game_id") or pick["id"]

    home_team = pick.get("home_team") or ""
    away_team = pick.get("away_team") or ""
    pick["home_team"] = home_team
    pick["away_team"] = away_team
    pick["matchup"] = pick.get("matchup") or pick.get("game") or f"{away_team} @ {home_team}"

    # === START TIME ===
    start_time_display = pick.get("start_time") or pick.get("start_time_et") or pick.get("game_time")
    pick["start_time_et"] = start_time_display
    pick["start_time"] = start_time_display
    pick["start_time_timezone"] = "ET"

    commence_iso = pick.get("commence_time_iso") or pick.get("commence_time")
    pick["start_time_iso"] = commence_iso if commence_iso else None

    if commence_iso and isinstance(commence_iso, str) and commence_iso.endswith("Z"):
        pick["start_time_utc"] = commence_iso
    elif commence_iso:
        try:
            dt = datetime.fromisoformat(str(commence_iso).replace("Z", "+00:00"))
            pick["start_time_utc"] = dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            pick["start_time_utc"] = commence_iso
    else:
        pick["start_time_utc"] = None
    # Do not expose UTC fields to clients (ET only)
    pick.pop("start_time_utc", None)

    # Fallback: derive ET display time from commence_time if missing
    if not start_time_display and commence_iso:
        try:
            if _TIME_ET_AVAILABLE:
                start_time_display = get_game_start_time_et(commence_iso)
            elif _ET is not None:
                dt = datetime.fromisoformat(str(commence_iso).replace("Z", "+00:00"))
                start_time_display = dt.astimezone(_ET).strftime("%-I:%M %p ET")
        except Exception:
            start_time_display = ""
        pick["start_time_et"] = start_time_display
        pick["start_time"] = start_time_display
        pick["start_time_timezone"] = "ET"

    if not start_time_display or start_time_display == "TBD ET":
        start_time_display = "TBD ET"
        pick["start_time_et"] = start_time_display
        pick["start_time"] = start_time_display
        pick["start_time_timezone"] = "ET"
        pick["start_time_status"] = "UNAVAILABLE"
    else:
        pick["start_time_status"] = "OK"

    # === STATUS FLAGS ===
    pick["status"] = pick.get("status") or pick.get("game_status") or "unknown"
    pick["has_started"] = pick.get("has_started", False)
    pick["is_started_already"] = pick.get("is_started_already", pick.get("has_started", False))
    pick["is_live"] = pick.get("is_live", False)
    pick["is_live_bet_candidate"] = pick.get("is_live_bet_candidate", False)

    # === BET INSTRUCTION FIELDS ===
    pick_type = normalize_pick_type(pick)
    stat_type = pick.get("stat_type", pick.get("prop_type", ""))
    market_label = normalize_market_label(pick_type, stat_type)
    signal_label = get_signal_label(pick)
    selection = normalize_selection(pick, pick_type)
    side_label = normalize_side_label(pick, pick_type)

    # Ensure line exists
    line = pick.get("line")
    if line is None:
        for key in ("point", "spread", "total", "line_value", "player_line"):
            if pick.get(key) is not None:
                line = pick.get(key)
                pick["line"] = line
                break

    # Build line_signed
    line_signed = None
    if pick_type == "spread" and line is not None:
        line_signed = f"+{line}" if line > 0 else str(line)
    elif pick_type == "total" and line is not None:
        prefix = "O" if side_label.lower() == "over" else "U"
        line_signed = f"{prefix} {line}"
    elif pick_type == "player_prop" and line is not None:
        prefix = "O" if side_label.lower() == "over" else "U"
        line_signed = f"{prefix} {line}"

    # Get actual odds - NEVER fabricate
    raw_odds = pick.get("odds") or pick.get("odds_american")
    odds_american = raw_odds if raw_odds is not None else None

    # Enforce canonical side resolution for game picks (HOME/AWAY)
    correction_flags = pick.get("correction_flags") or []
    if pick_type in ("spread", "moneyline"):
        intent = resolve_home_away_intent(pick)
        if intent and home_team and away_team:
            desired_team = home_team if intent == "HOME" else away_team
            if selection and desired_team and selection.strip() != desired_team:
                correction_flags.append("FIELD_CONTRADICTION_CORRECTED")
                selection = desired_team
                pick["team"] = desired_team
                side_label = desired_team
    pick["correction_flags"] = correction_flags

    # Build canonical bet string
    bet_string = build_bet_string(
        pick,
        pick_type,
        selection,
        market_label,
        side_label,
        line_signed if pick_type == "spread" else None
    )

    # Compute selection_home_away
    selection_home_away = None
    if selection and home_team and away_team:
        sel_lower = selection.lower().strip()
        home_lower = home_team.lower().strip()
        away_lower = away_team.lower().strip()
        if sel_lower == home_lower or home_lower in sel_lower or sel_lower in home_lower:
            selection_home_away = "HOME"
        elif sel_lower == away_lower or away_lower in sel_lower or sel_lower in away_lower:
            selection_home_away = "AWAY"

    # Set all bet instruction fields
    pick["pick_type"] = pick_type
    pick["market_label"] = market_label
    pick["signal_label"] = signal_label
    pick["selection"] = selection
    pick["selection_home_away"] = selection_home_away
    pick["side_label"] = side_label
    pick["line"] = line
    pick["line_signed"] = line_signed
    pick["odds_american"] = odds_american
    pick["units"] = pick.get("units", 1.0)
    pick["recommended_units"] = pick.get("units", 1.0)
    pick["bet_string"] = bet_string
    pick["book"] = pick.get("book") or pick.get("sportsbook_name") or "Consensus"
    pick["book_link"] = pick.get("book_link") or pick.get("sportsbook_event_url") or ""

    # === REASONING FIELDS ===
    pick["tier"] = pick.get("tier") or pick.get("bet_tier", {}).get("tier") or "EDGE_LEAN"
    pick["score"] = pick.get("score") or pick.get("final_score") or pick.get("total_score") or 0
    pick["confidence_label"] = pick.get("confidence_label") or pick.get("confidence") or pick.get("action") or "PLAY"
    pick["signals_fired"] = pick.get("signals_fired") or pick.get("signals_firing") or []
    pick["confluence_reasons"] = pick.get("confluence_reasons") or []
    pick["engine_breakdown"] = pick.get("engine_breakdown") or {
        "ai": pick.get("ai_score", 0),
        "research": pick.get("research_score", 0),
        "esoteric": pick.get("esoteric_score", 0),
        "jarvis": pick.get("jarvis_score") or pick.get("jarvis_rs", 0)
    }

    # === v20.28.9: ENGINE DIVERGENCE WARNINGS ===
    # Flag when any core engine is weak (<5.5) but pick still outputs
    ENGINE_WEAK_THRESHOLD = 5.5
    warnings = pick.get("warnings") or []
    engine_breakdown = pick["engine_breakdown"]
    weak_engines = []

    for engine_name, score in engine_breakdown.items():
        if isinstance(score, (int, float)) and score < ENGINE_WEAK_THRESHOLD:
            weak_engines.append(f"{engine_name}={score:.1f}")

    if weak_engines:
        warnings.append(f"ENGINE_DIVERGENCE: {', '.join(weak_engines)} below {ENGINE_WEAK_THRESHOLD}")

    pick["warnings"] = warnings

    # === DESCRIPTION (human-readable pick summary) ===
    if not pick.get("description"):
        player_name = pick.get("player_name") or pick.get("player")
        matchup = pick.get("matchup") or f"{away_team} @ {home_team}"
        if player_name:
            prop_label = (pick.get("prop_type") or pick.get("stat_type") or "Prop").replace("_", " ").title()
            pick["description"] = f"{player_name} {prop_label} {side_label} {line}" if line is not None else f"{player_name} {prop_label}"
        elif pick_type == "moneyline" or "MONEYLINE" in (market_label or "").upper() or "ML" in (market_label or "").upper():
            odds_str = f" {odds_american:+d}" if odds_american else ""
            pick["description"] = f"{matchup} — {selection or side_label} ML{odds_str}"
        elif selection or side_label:
            pick["description"] = f"{matchup} — {market_label} {side_label} {line}" if line is not None else f"{matchup} — {market_label} {side_label}"
        else:
            pick["description"] = f"{matchup} — {market_label} {line}" if line is not None else matchup

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
        game_picks["picks"] = [enforce_home_away_consistency(normalize_pick(p)) for p in game_picks.get("picks", [])]

    return payload
