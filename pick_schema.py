"""
PickCard Schema - Canonical pick format for all market types
v10.72: Unified pick normalization

Every pick (spread, ML, total, prop) is converted to this single schema
before rendering. This ensures consistent output format.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from enum import Enum

# v10.75: Import time status module
from time_status import compute_time_status, format_time_status, TimeState


class MarketType(str, Enum):
    SPREAD = "SPREAD"
    ML = "ML"
    TOTAL = "TOTAL"
    PROP = "PROP"


class Tier(str, Enum):
    GOLD_STAR = "GOLD_STAR"
    EDGE_LEAN = "EDGE_LEAN"
    MONITOR = "MONITOR"
    PASS = "PASS"


@dataclass
class PickCard:
    """
    Canonical pick format. ALL picks must be normalized to this schema.
    """
    # Game info
    sport: str
    league: str
    game: str  # "Away @ Home" format
    start_time: str  # ISO format or "TBD"

    # Market info
    market_type: MarketType  # SPREAD | ML | TOTAL | PROP
    selection_name: str  # Team name or player name
    selection_detail: str  # "+1.5" or "Over 221.5" or "Points Over 18.5"

    # Odds info
    odds: int  # American odds (-110, +150, etc.)
    odds_display: str  # "-110" formatted string

    # Sportsbook info
    book: str = "—"  # DK | FD | MGM | etc.
    book_url: Optional[str] = None
    book_status: str = "no_link"  # "linked" | "no_link" | "not_offered"

    # Scoring
    score: float = 0.0
    tier: Tier = Tier.PASS
    units: float = 0.0

    # Signals
    signals_fired: List[str] = field(default_factory=list)  # Compact: ["SHARP", "RLM", "LSTM"]
    reasons: List[str] = field(default_factory=list)  # Verbose: ["AI ENGINE: LSTM +0.6", ...]

    # Metadata
    pick_id: Optional[str] = None
    event_id: Optional[str] = None
    market_id: Optional[str] = None
    selection_id: Optional[str] = None

    # v10.75: Time status fields
    start_time_et: Optional[str] = None  # ISO format, ET timezone
    pulled_at_et: Optional[str] = None   # ISO format, ET timezone
    status_time: Optional[Dict] = None   # Full time status object

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["market_type"] = self.market_type.value
        d["tier"] = self.tier.value
        return d

    def to_compact(self) -> str:
        """One-line display format for tables."""
        book_info = f"{self.book}" if self.book != "—" else ""
        link_info = "🔗" if self.book_url else ""
        # v10.75: Include time status
        time_str = format_time_status(self.status_time) if self.status_time else ""
        return f"{self.tier.value:10} {self.score:.2f}  {self.game:35} {self.selection_name} {self.selection_detail} ({self.odds_display}) {book_info} {link_info} [{time_str}]"


def normalize_game_pick(raw: dict, sport: str = "—") -> PickCard:
    """
    Normalize a game pick (spread/ML/total) to PickCard format.

    Expected raw fields:
    - game, home_team, away_team
    - pick_type (SPREAD/ML/TOTAL)
    - side, spread, total, odds
    - final_score, tier, units
    - reasons[]
    """
    # Determine market type
    pick_type = raw.get("pick_type", raw.get("market_type", "SPREAD")).upper()
    if pick_type in ["SPREAD", "ATS"]:
        market_type = MarketType.SPREAD
    elif pick_type in ["ML", "MONEYLINE", "H2H"]:
        market_type = MarketType.ML
    elif pick_type in ["TOTAL", "OU", "OVER_UNDER"]:
        market_type = MarketType.TOTAL
    else:
        market_type = MarketType.SPREAD  # Default

    # Extract game info
    game = raw.get("game", "")
    if not game:
        home = raw.get("home_team", raw.get("home", "—"))
        away = raw.get("away_team", raw.get("away", "—"))
        game = f"{away} @ {home}"

    # Extract selection info based on market type
    side = raw.get("side", raw.get("pick", ""))
    home_team = raw.get("home_team", raw.get("home", ""))
    away_team = raw.get("away_team", raw.get("away", ""))

    if market_type == MarketType.SPREAD:
        spread_val = raw.get("spread", raw.get("line", 0))
        spread_str = f"+{spread_val}" if spread_val > 0 else str(spread_val)
        selection_name = side if side else (home_team if spread_val < 0 else away_team)
        selection_detail = spread_str
    elif market_type == MarketType.ML:
        selection_name = side if side else home_team
        selection_detail = "ML"
    elif market_type == MarketType.TOTAL:
        total_val = raw.get("total", raw.get("line", 0))
        over_under = raw.get("over_under", raw.get("side", "Over"))
        selection_name = over_under.capitalize()
        selection_detail = f"{over_under.capitalize()} {total_val}"
    else:
        selection_name = side
        selection_detail = "—"

    # Extract odds
    odds = raw.get("odds", -110)
    if isinstance(odds, str):
        try:
            odds = int(odds.replace("+", ""))
        except:
            odds = -110
    odds_display = f"+{odds}" if odds > 0 else str(odds)

    # Extract scoring
    score = raw.get("final_score", raw.get("score", raw.get("smash_score", 0)))
    tier_str = raw.get("tier", "PASS").upper()
    tier = Tier[tier_str] if tier_str in Tier.__members__ else Tier.PASS
    units = raw.get("units", raw.get("unit_size", 0))

    # Extract signals
    reasons = raw.get("reasons", [])
    signals_fired = extract_signals_from_reasons(reasons)

    # v10.75: Compute time status
    raw_start_time = raw.get("start_time", raw.get("commence_time", raw.get("game_time")))
    game_state = raw.get("game_state", raw.get("status"))
    time_status = compute_time_status(raw_start_time, game_state=game_state)

    return PickCard(
        sport=sport.upper(),
        league=raw.get("league", sport.upper()),
        game=game,
        start_time=raw.get("start_time", raw.get("commence_time", raw.get("game_time", "TBD"))),
        market_type=market_type,
        selection_name=selection_name,
        selection_detail=selection_detail,
        odds=odds,
        odds_display=odds_display,
        book=raw.get("book", raw.get("sportsbook", "—")),
        book_url=raw.get("book_url", raw.get("bet_url", None)),
        book_status="linked" if raw.get("book_url") else "no_link",
        score=score,
        tier=tier,
        units=units,
        signals_fired=signals_fired,
        reasons=reasons,
        pick_id=raw.get("pick_id", raw.get("id")),
        event_id=raw.get("event_id", raw.get("game_id")),
        market_id=raw.get("market_id"),
        selection_id=raw.get("selection_id"),
        start_time_et=time_status.get("start_time_et"),
        pulled_at_et=time_status.get("pulled_at_et"),
        status_time=time_status,
    )


def normalize_prop_pick(raw: dict, sport: str = "—") -> PickCard:
    """
    Normalize a prop pick to PickCard format.

    Expected raw fields:
    - player_name, stat_type
    - line, over_under, odds
    - smash_score, tier
    - game, game_time
    - reasons[], badges[]
    """
    # Player and prop info
    player = raw.get("player_name", raw.get("player", "—"))
    stat_type = raw.get("stat_type", raw.get("prop_type", raw.get("market", "—")))
    line = raw.get("line", raw.get("point", 0))
    over_under = raw.get("over_under", raw.get("side", "over")).capitalize()

    # Clean up stat type for display
    stat_display = format_stat_type(stat_type)
    selection_detail = f"{stat_display} {over_under} {line}"

    # Extract game info
    game = raw.get("game", "")
    if not game:
        home = raw.get("home_team", "")
        away = raw.get("away_team", "")
        if home and away:
            game = f"{away} @ {home}"
        else:
            game = "—"

    # Extract odds
    odds = raw.get("odds", raw.get("price", -110))
    if isinstance(odds, str):
        try:
            odds = int(odds.replace("+", ""))
        except:
            odds = -110
    odds_display = f"+{odds}" if odds > 0 else str(odds)

    # Extract scoring
    score = raw.get("smash_score", raw.get("score", raw.get("final_score", 0)))
    tier_str = raw.get("tier", "PASS").upper()
    tier = Tier[tier_str] if tier_str in Tier.__members__ else Tier.PASS
    units = raw.get("units", raw.get("unit_size", 0))

    # Extract signals from reasons or badges
    reasons = raw.get("reasons", [])
    badges = raw.get("badges", [])
    signals_fired = extract_signals_from_reasons(reasons) + badges
    signals_fired = list(set(signals_fired))  # Dedupe

    # v10.75: Compute time status
    raw_start_time = raw.get("game_time", raw.get("start_time", raw.get("commence_time")))
    game_state = raw.get("game_state", raw.get("status"))
    time_status = compute_time_status(raw_start_time, game_state=game_state)

    return PickCard(
        sport=sport.upper(),
        league=raw.get("league", sport.upper()),
        game=game,
        start_time=raw.get("game_time", raw.get("start_time", raw.get("commence_time", "TBD"))),
        market_type=MarketType.PROP,
        selection_name=player,
        selection_detail=selection_detail,
        odds=odds,
        odds_display=odds_display,
        book=raw.get("book", raw.get("sportsbook", "—")),
        book_url=raw.get("book_url", raw.get("bet_url", None)),
        book_status="linked" if raw.get("book_url") else "no_link",
        score=score,
        tier=tier,
        units=units,
        signals_fired=signals_fired,
        reasons=reasons,
        pick_id=raw.get("pick_id", raw.get("id")),
        event_id=raw.get("event_id", raw.get("game_id")),
        market_id=raw.get("market_id"),
        selection_id=raw.get("selection_id"),
        start_time_et=time_status.get("start_time_et"),
        pulled_at_et=time_status.get("pulled_at_et"),
        status_time=time_status,
    )


def normalize_pick(raw: dict, sport: str = "—") -> PickCard:
    """
    Auto-detect pick type and normalize to PickCard.

    Detection logic:
    - If has 'player_name' or 'stat_type' → prop
    - If has 'pick_type' of SPREAD/ML/TOTAL → game pick
    - Default → game pick
    """
    # Detect prop picks
    if raw.get("player_name") or raw.get("player") or raw.get("stat_type") or raw.get("prop_type"):
        return normalize_prop_pick(raw, sport)

    # Otherwise treat as game pick
    return normalize_game_pick(raw, sport)


def normalize_picks(raw_picks: list, sport: str = "—") -> List[PickCard]:
    """Normalize a list of picks."""
    return [normalize_pick(p, sport) for p in raw_picks]


def extract_signals_from_reasons(reasons: List[str]) -> List[str]:
    """
    Extract compact signal names from verbose reasons.

    "AI ENGINE: LSTM (strong line movement trend) +0.6" → "LSTM"
    "RESEARCH: Sharp Split (Game) +3.0" → "SHARP"
    """
    signal_map = {
        "lstm": "LSTM",
        "ensemble": "ENSEMBLE",
        "monte carlo": "MONTE_CARLO",
        "matchup": "MATCHUP",
        "line movement": "LINE_MVT",
        "rest": "REST",
        "injury": "INJURY",
        "betting edge": "BET_EDGE",
        "sharp": "SHARP",
        "rlm": "RLM",
        "reverse line": "RLM",
        "public fade": "PUB_FADE",
        "hospital": "HOSPITAL",
        "goldilocks": "GOLDILOCKS",
        "void moon": "VOID_MOON",
        "jarvis": "JARVIS",
        "gematria": "GEMATRIA",
        "harmonic": "HARMONIC",
        "confluence": "CONFLUENCE",
        "noosphere": "NOOSPHERE",
        "fibonacci": "FIB",
    }

    signals = []
    for reason in reasons:
        reason_lower = reason.lower()
        for key, signal in signal_map.items():
            if key in reason_lower and signal not in signals:
                signals.append(signal)

    return signals


def format_stat_type(stat_type: str) -> str:
    """
    Format stat type for display.

    "player_points" → "PTS"
    "player_rebounds" → "REB"
    """
    stat_map = {
        "player_points": "PTS",
        "player_rebounds": "REB",
        "player_assists": "AST",
        "player_threes": "3PT",
        "player_steals": "STL",
        "player_blocks": "BLK",
        "player_turnovers": "TO",
        "player_points_rebounds_assists": "PRA",
        "player_points_rebounds": "P+R",
        "player_points_assists": "P+A",
        "player_rebounds_assists": "R+A",
        "player_double_double": "DD",
        "player_pass_yds": "PASS YDS",
        "player_pass_tds": "PASS TD",
        "player_rush_yds": "RUSH YDS",
        "player_receptions": "REC",
        "player_reception_yds": "REC YDS",
        "batter_hits": "HITS",
        "batter_total_bases": "TB",
        "pitcher_strikeouts": "K",
        "player_shots_on_goal": "SOG",
        "player_anytime_goalscorer": "GOAL",
    }

    return stat_map.get(stat_type.lower(), stat_type.replace("player_", "").upper())


def picks_to_table(picks: List[PickCard]) -> str:
    """
    Render picks as a formatted table string.
    v10.75: Added time status column.
    """
    if not picks:
        return "No picks available."

    lines = []
    header = f"{'Tier':<12} {'Score':>6}  {'Game':<30} {'Pick':<25} {'Odds':>8} {'Time Status':<25}"
    lines.append(header)
    lines.append("=" * len(header))

    for p in picks:
        pick_str = f"{p.selection_name} {p.selection_detail}"
        if len(pick_str) > 25:
            pick_str = pick_str[:22] + "..."
        game_str = p.game if len(p.game) <= 30 else p.game[:27] + "..."

        # v10.75: Format time status
        time_str = format_time_status(p.status_time) if p.status_time else "UNKNOWN"
        if len(time_str) > 25:
            time_str = time_str[:22] + "..."

        line = f"{p.tier.value:<12} {p.score:>6.2f}  {game_str:<30} {pick_str:<25} {p.odds_display:>8} {time_str:<25}"
        lines.append(line)

    return "\n".join(lines)
