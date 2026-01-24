"""
Canonical Pick Schema v10.80
============================
MASTER PROMPT COMPLIANT - Single source of truth for ALL pick output.

Every pick (spread, ML, total, prop) across ALL endpoints (nba/nhl/ncaab/nfl/mlb)
MUST conform to this schema. No exceptions.

Features:
- Pydantic validation
- Full scoring breakdown (AI, Research, Esoteric, Jarvis, Jason Sim)
- Titanium Rule + Harmonic Convergence
- TODAY-only EST validation
- Injury validation tracking
- Sportsbook + deep link support
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime, date
from enum import Enum
import hashlib
from zoneinfo import ZoneInfo

# =============================================================================
# ENUMS
# =============================================================================

class MarketType(str, Enum):
    SPREAD = "spread"
    MONEYLINE = "moneyline"
    TOTAL = "total"
    PLAYER_PROP = "player_prop"


class Tier(str, Enum):
    TITANIUM_SMASH = "TITANIUM_SMASH"
    GOLD_STAR = "GOLD_STAR"
    EDGE_LEAN = "EDGE_LEAN"
    MONITOR = "MONITOR"
    PASS = "PASS"


class GameStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINAL = "final"


class SourceFeed(str, Enum):
    PLAYBOOK = "playbook"
    ODDS_API = "odds_api"
    FALLBACK = "fallback"


# =============================================================================
# SUB-MODELS FOR SCORING BREAKDOWN
# =============================================================================

class AIEngineBreakdown(BaseModel):
    """AI Engine (8-model blend) breakdown."""
    score: float = Field(0.0, ge=0, le=10, description="AI engine score 0-10")
    models_fired: List[str] = Field(default_factory=list)
    model_contributions: Dict[str, float] = Field(default_factory=dict)
    raw_features: Dict[str, Any] = Field(default_factory=dict)


class ResearchEngineBreakdown(BaseModel):
    """Research Engine (market/human edges) breakdown."""
    score: float = Field(0.0, ge=0, le=10, description="Research engine score 0-10")
    pillars_fired: List[str] = Field(default_factory=list)
    signals_fired: List[str] = Field(default_factory=list)
    adjustments: List[str] = Field(default_factory=list)
    public_fade_applied: bool = Field(False, description="Public Fade lives ONLY here")
    sharp_split_boost: float = 0.0
    rlm_boost: float = 0.0
    hospital_fade_boost: float = 0.0


class EsotericEngineBreakdown(BaseModel):
    """Esoteric Engine (NON-JARVIS signals) breakdown."""
    score: float = Field(0.0, ge=0, le=10, description="Esoteric engine score 0-10")
    signals: List[str] = Field(default_factory=list)
    vedic_astro: Optional[Dict[str, Any]] = None
    fibonacci_phi: Optional[Dict[str, Any]] = None
    vortex_369: Optional[Dict[str, Any]] = None
    daily_edge: Optional[Dict[str, Any]] = None
    chrome_resonance: Optional[Dict[str, Any]] = None
    void_moon_active: bool = False


class JarvisEngineBreakdown(BaseModel):
    """Jarvis Engine (gematria + sacred triggers) breakdown."""
    score: float = Field(0.0, ge=0, le=10, description="Jarvis engine score 0-10")
    jarvis_active: bool = False
    jarvis_hits_count: int = 0
    jarvis_triggers_hit: List[int] = Field(default_factory=list)
    jarvis_reasons: List[str] = Field(default_factory=list)
    gematria_value: Optional[int] = None
    mid_spread_amplifier: float = 0.0
    trap_modifier: float = 0.0


class JasonSimBreakdown(BaseModel):
    """Jason Sim 2.0 confluence layer breakdown."""
    available: bool = False
    win_pct_home: Optional[float] = None
    win_pct_away: Optional[float] = None
    projected_total: Optional[float] = None
    projected_pace: Optional[float] = None
    variance_flag: Optional[str] = None  # "LOW", "MEDIUM", "HIGH"
    injury_state: str = "UNKNOWN"
    sim_count: int = 0
    boost_applied: float = 0.0
    boost_reason: Optional[str] = None
    blocked: bool = False
    block_reason: Optional[str] = None


class InjuryValidation(BaseModel):
    """Injury/prop validation gate results."""
    checked: bool = False
    provider: str = "none"
    player_active: Optional[bool] = None
    player_status: Optional[str] = None
    prop_listed: Optional[bool] = None
    books_offering: List[str] = Field(default_factory=list)
    mismatches: List[str] = Field(default_factory=list)
    blocked: bool = False
    reason: Optional[str] = None


class ScoringBreakdown(BaseModel):
    """Complete scoring breakdown - REQUIRED on every pick."""
    ai_engine: AIEngineBreakdown = Field(default_factory=AIEngineBreakdown)
    research_engine: ResearchEngineBreakdown = Field(default_factory=ResearchEngineBreakdown)
    esoteric_engine: EsotericEngineBreakdown = Field(default_factory=EsotericEngineBreakdown)
    jarvis_engine: JarvisEngineBreakdown = Field(default_factory=JarvisEngineBreakdown)
    jason_sim: JasonSimBreakdown = Field(default_factory=JasonSimBreakdown)
    injury_validation: InjuryValidation = Field(default_factory=InjuryValidation)

    # Weight configuration (for transparency)
    weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "ai": 0.25,
            "research": 0.35,
            "esoteric": 0.20,
            "jarvis": 0.20
        }
    )


# =============================================================================
# MAIN PICK SCHEMA
# =============================================================================

class CanonicalPick(BaseModel):
    """
    Canonical Pick Schema - MASTER PROMPT COMPLIANT

    Every pick returned by any endpoint MUST conform to this schema.
    """

    # -------------------------------------------------------------------------
    # IDENTIFICATION
    # -------------------------------------------------------------------------
    pick_id: str = Field(default="", description="Stable hash: sport + event_id + market + selection + line")

    # -------------------------------------------------------------------------
    # SPORT/LEAGUE
    # -------------------------------------------------------------------------
    sport: str = Field(..., description="Sport code: NBA, NFL, NHL, MLB, NCAAB")
    league: str = Field(..., description="League identifier")

    # -------------------------------------------------------------------------
    # EVENT INFO
    # -------------------------------------------------------------------------
    event_id: str = Field(..., description="Unique event identifier")
    game_time_utc: str = Field(..., description="ISO8601 UTC game time")
    game_time_est: str = Field(..., description="ISO8601 EST game time")
    display_game_time_est: str = Field("", description="Human readable: '7:00 PM ET'")

    # -------------------------------------------------------------------------
    # TODAY-ONLY VALIDATION (EST)
    # -------------------------------------------------------------------------
    is_today_est: bool = Field(..., description="Game is TODAY in America/New_York")
    has_started: bool = Field(False, description="Game has already started")
    started_minutes_ago: Optional[int] = Field(None, description="Minutes since game started, if started")
    status: GameStatus = Field(GameStatus.SCHEDULED, description="Game status")

    # -------------------------------------------------------------------------
    # TEAMS
    # -------------------------------------------------------------------------
    home_team: str = Field(..., description="Home team name")
    away_team: str = Field(..., description="Away team name")
    matchup_display: str = Field("", description="'Away @ Home' format")

    # -------------------------------------------------------------------------
    # MARKET INFO
    # -------------------------------------------------------------------------
    market_type: MarketType = Field(..., description="Market type")
    selection: str = Field(..., description="Team name or 'Player Over/Under'")
    line: Optional[float] = Field(None, description="Point spread or total line")

    # -------------------------------------------------------------------------
    # ODDS & SPORTSBOOK
    # -------------------------------------------------------------------------
    odds_american: Optional[int] = Field(None, description="American odds (-110, +150)")
    book_key: str = Field("", description="Sportsbook key: draftkings, fanduel, etc.")
    book_name: str = Field("", description="Human readable book name")
    book_link: Optional[str] = Field(None, description="Deep link to bet slip, null if unavailable")

    # -------------------------------------------------------------------------
    # DATA SOURCE
    # -------------------------------------------------------------------------
    source_feed: SourceFeed = Field(SourceFeed.FALLBACK, description="Data source")

    # -------------------------------------------------------------------------
    # NOTES/FLAGS
    # -------------------------------------------------------------------------
    notes: List[str] = Field(default_factory=list, description="Informational notes")

    # -------------------------------------------------------------------------
    # SCORING (ALL REQUIRED)
    # -------------------------------------------------------------------------
    final_score: float = Field(0.0, ge=0, le=10, description="Final composite score 0-10")
    tier: Tier = Field(Tier.PASS, description="Pick tier")

    ai_score: float = Field(0.0, ge=0, le=10, description="AI engine score")
    research_score: float = Field(0.0, ge=0, le=10, description="Research engine score")
    esoteric_score: float = Field(0.0, ge=0, le=10, description="Esoteric engine score (non-Jarvis)")
    jarvis_score: float = Field(0.0, ge=0, le=10, description="Jarvis engine score")
    jason_sim_boost: float = Field(0.0, description="Jason Sim confluence boost")

    # -------------------------------------------------------------------------
    # TITANIUM RULE + HARMONIC CONVERGENCE
    # -------------------------------------------------------------------------
    titanium_smash: bool = Field(False, description="3-of-4 glitch modules fired")
    titanium_count: int = Field(0, ge=0, le=4, description="Number of glitch modules fired")
    harmonic_convergence: bool = Field(False, description="AI >= 8.0 AND Esoteric >= 8.0")

    # -------------------------------------------------------------------------
    # TRANSPARENCY / BREAKDOWN
    # -------------------------------------------------------------------------
    scoring_breakdown: ScoringBreakdown = Field(
        default_factory=ScoringBreakdown,
        description="Full scoring component breakdown"
    )
    confluence_reasons: List[str] = Field(
        default_factory=list,
        description="Top human-readable reasons"
    )

    # -------------------------------------------------------------------------
    # DISPLAY HELPERS
    # -------------------------------------------------------------------------
    display_line: str = Field("", description="'Lakers -3.5 (-110) DraftKings'")
    display_pick: str = Field("", description="'LeBron PTS Over 25.5 (-105) FanDuel'")
    units: float = Field(0.0, ge=0, le=3, description="Recommended bet size")

    # -------------------------------------------------------------------------
    # VALIDATORS (Pydantic v2)
    # -------------------------------------------------------------------------

    @model_validator(mode='after')
    def compute_all_derived_fields(self):
        """Compute derived display fields after model creation."""
        # Generate pick_id if not provided
        if not self.pick_id:
            parts = [
                self.sport or '',
                self.event_id or '',
                str(self.market_type) if self.market_type else '',
                self.selection or '',
                str(self.line or '')
            ]
            hash_input = '|'.join(str(p) for p in parts)
            object.__setattr__(self, 'pick_id', hashlib.md5(hash_input.encode()).hexdigest()[:12])

        # Generate matchup display if not provided
        if not self.matchup_display and self.away_team and self.home_team:
            object.__setattr__(self, 'matchup_display', f"{self.away_team} @ {self.home_team}")

        # Upgrade tier for Titanium Smash
        if self.titanium_smash and self.final_score >= 7.5:
            object.__setattr__(self, 'tier', Tier.TITANIUM_SMASH)

        # Display line
        if not self.display_line:
            selection = self.selection or ''
            line_str = f"{self.line:+.1f}" if self.line is not None else ""
            odds_str = f"({self.odds_american:+d})" if self.odds_american else ""
            book = self.book_name or self.book_key or ''
            object.__setattr__(self, 'display_line', f"{selection} {line_str} {odds_str} {book}".strip())

        # Display pick (for props)
        if not self.display_pick and self.market_type == MarketType.PLAYER_PROP:
            object.__setattr__(self, 'display_pick', self.display_line or '')

        # Display game time
        if not self.display_game_time_est:
            try:
                if self.game_time_est:
                    dt = datetime.fromisoformat(self.game_time_est.replace('Z', '+00:00'))
                    object.__setattr__(self, 'display_game_time_est', dt.strftime("%-I:%M %p ET"))
            except Exception:
                pass

        return self

    model_config = {"use_enum_values": True}


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def generate_pick_id(sport: str, event_id: str, market_type: str, selection: str, line: float = None) -> str:
    """Generate a stable, deterministic pick_id."""
    parts = [sport, event_id, market_type, selection, str(line or '')]
    hash_input = '|'.join(parts)
    return hashlib.md5(hash_input.encode()).hexdigest()[:12]


def compute_today_est_fields(game_time_utc: str) -> Dict[str, Any]:
    """
    Compute TODAY-only EST validation fields.

    Returns:
        is_today_est: bool
        has_started: bool
        started_minutes_ago: int | None
        game_time_est: str (ISO)
        display_game_time_est: str
    """
    ET = ZoneInfo("America/New_York")
    now_et = datetime.now(ET)
    today_et = now_et.date()

    try:
        # Parse UTC time
        if game_time_utc.endswith('Z'):
            game_dt_utc = datetime.fromisoformat(game_time_utc.replace('Z', '+00:00'))
        else:
            game_dt_utc = datetime.fromisoformat(game_time_utc)

        # Convert to ET
        game_dt_et = game_dt_utc.astimezone(ET)
        game_date_et = game_dt_et.date()

        # Is today?
        is_today = game_date_et == today_et

        # Has started?
        has_started = now_et > game_dt_et

        # Minutes since start
        started_minutes_ago = None
        if has_started:
            delta = now_et - game_dt_et
            started_minutes_ago = int(delta.total_seconds() / 60)

        # Format display time
        display_time = game_dt_et.strftime("%-I:%M %p ET")

        return {
            "is_today_est": is_today,
            "has_started": has_started,
            "started_minutes_ago": started_minutes_ago,
            "game_time_est": game_dt_et.isoformat(),
            "display_game_time_est": display_time
        }
    except Exception as e:
        return {
            "is_today_est": False,
            "has_started": False,
            "started_minutes_ago": None,
            "game_time_est": "",
            "display_game_time_est": "TBD"
        }


def create_empty_breakdown() -> ScoringBreakdown:
    """Create an empty scoring breakdown with defaults."""
    return ScoringBreakdown()


def compute_tier(
    final_score: float,
    titanium_smash: bool = False
) -> Tier:
    """
    Compute tier from final score using tiering.py thresholds.

    GOLD_STAR >= 7.5
    EDGE_LEAN >= 6.5
    MONITOR >= 5.5
    PASS < 5.5

    If titanium_smash and final_score >= 7.5: TITANIUM_SMASH
    """
    if titanium_smash and final_score >= 7.5:
        return Tier.TITANIUM_SMASH
    elif final_score >= 7.5:
        return Tier.GOLD_STAR
    elif final_score >= 6.5:
        return Tier.EDGE_LEAN
    elif final_score >= 5.5:
        return Tier.MONITOR
    else:
        return Tier.PASS


def compute_units(tier: Tier) -> float:
    """Compute recommended bet units from tier."""
    units_map = {
        Tier.TITANIUM_SMASH: 2.5,
        Tier.GOLD_STAR: 2.0,
        Tier.EDGE_LEAN: 1.0,
        Tier.MONITOR: 0.0,
        Tier.PASS: 0.0
    }
    return units_map.get(tier, 0.0)


# =============================================================================
# BOOK CONFIGURATION
# =============================================================================

BOOK_ALLOWLIST = ["draftkings", "fanduel", "betmgm", "caesars", "pointsbet", "bet365", "wynnbet"]

BOOK_DISPLAY_NAMES = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
    "pointsbet": "PointsBet",
    "bet365": "Bet365",
    "wynnbet": "WynnBET",
}


def select_best_book(bookmakers: List[Dict], market_key: str = None) -> Dict[str, Any]:
    """
    Select best available book from allowlist.

    Returns:
        {
            "book_key": str,
            "book_name": str,
            "odds": int,
            "line": float | None,
            "book_link": str | None
        }
    """
    best = {
        "book_key": "",
        "book_name": "",
        "odds": None,
        "line": None,
        "book_link": None
    }

    if not bookmakers:
        return best

    # Find first allowed book with the market
    for book_pref in BOOK_ALLOWLIST:
        for bm in bookmakers:
            bm_key = bm.get("key", "").lower()
            if bm_key == book_pref:
                # Found a preferred book, extract odds
                markets = bm.get("markets", [])
                for market in markets:
                    if market_key and market.get("key") != market_key:
                        continue

                    outcomes = market.get("outcomes", [])
                    if outcomes:
                        outcome = outcomes[0]
                        best["book_key"] = bm_key
                        best["book_name"] = BOOK_DISPLAY_NAMES.get(bm_key, bm_key.title())
                        best["odds"] = outcome.get("price")
                        best["line"] = outcome.get("point")
                        # Deep link if available
                        best["book_link"] = bm.get("link") or bm.get("url")
                        return best

    # Fallback to first available
    if bookmakers:
        bm = bookmakers[0]
        best["book_key"] = bm.get("key", "")
        best["book_name"] = bm.get("title", bm.get("key", "").title())
        markets = bm.get("markets", [])
        if markets:
            outcomes = markets[0].get("outcomes", [])
            if outcomes:
                best["odds"] = outcomes[0].get("price")
                best["line"] = outcomes[0].get("point")

    return best


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def validate_pick_for_output(pick: CanonicalPick, allow_started: bool = False) -> tuple[bool, str]:
    """
    Validate a pick is ready for output.

    Returns:
        (is_valid, reason)
    """
    # Must be today
    if not pick.is_today_est:
        return False, "Game is not today (EST)"

    # Check if started
    if pick.has_started and not allow_started:
        return False, f"Game already started {pick.started_minutes_ago or 0} minutes ago"

    # Must have scoring
    if pick.final_score == 0 and pick.tier == Tier.PASS:
        return False, "No scoring data"

    # Injury validation for props
    if pick.market_type == MarketType.PLAYER_PROP:
        if pick.scoring_breakdown.injury_validation.blocked:
            return False, pick.scoring_breakdown.injury_validation.reason or "Blocked by injury validation"

    return True, "OK"


def filter_picks_today_only(
    picks: List[CanonicalPick],
    allow_started: bool = False
) -> List[CanonicalPick]:
    """
    Filter picks to TODAY only (EST), optionally excluding started games.
    """
    filtered = []
    for pick in picks:
        is_valid, reason = validate_pick_for_output(pick, allow_started)
        if is_valid:
            filtered.append(pick)
        elif pick.has_started and allow_started:
            pick.notes.append("GAME_ALREADY_STARTED — live bet only")
            filtered.append(pick)

    return filtered
