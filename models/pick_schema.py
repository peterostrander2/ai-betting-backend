"""
Unified Pick Output Schema - v15.0
Ensures 100% clarity and consistency for community-ready output.
"""
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class MarketType(str, Enum):
    """Standardized market types"""
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    MONEYLINE = "MONEYLINE"
    PROP = "PROP"


class GameStatus(str, Enum):
    """Game status for live betting context"""
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    FINAL = "FINAL"


class TierLevel(str, Enum):
    """Pick tier levels"""
    TITANIUM_SMASH = "TITANIUM_SMASH"
    GOLD_STAR = "GOLD_STAR"
    EDGE_LEAN = "EDGE_LEAN"
    MONITOR = "MONITOR"
    PASS = "PASS"


class PickOutputSchema(BaseModel):
    """
    Unified output schema for all pick endpoints.
    MUST be used by:
    - /live/best-bets/{sport}
    - /live/picks/today
    - /live/picks/grading-summary
    - All props endpoints
    """

    # ==========================================
    # HUMAN-READABLE FIELDS (ALWAYS PRESENT)
    # ==========================================

    description: str = Field(
        ...,
        description="Full readable sentence for community sharing. "
                    "Examples: 'Jamal Murray Assists Over 3.5', "
                    "'Bucks @ 76ers — Total Under 246.5'"
    )

    pick_detail: str = Field(
        ...,
        description="Compact readable bet string. "
                    "Examples: 'Assists Over 3.5', 'Total Under 246.5', 'Spread 76ers +6.5'"
    )

    matchup: str = Field(
        ...,
        description="Always 'Away @ Home' format for games. For props, includes game context."
    )

    sport: str = Field(
        ...,
        description="NBA, NHL, NFL, MLB, NCAAB"
    )

    market: MarketType = Field(
        ...,
        description="One of: SPREAD, TOTAL, MONEYLINE, PROP"
    )

    side: str = Field(
        ...,
        description="Over/Under for totals/props; TeamName for spread/ML; "
                    "Never empty - always clear what was picked"
    )

    line: float = Field(
        ...,
        description="Numeric line (e.g., 246.5, 6.5, 18.5)"
    )

    odds_american: int = Field(
        ...,
        description="American odds format (e.g., -110, +120)"
    )

    book: str = Field(
        ...,
        description="Sportsbook key: draftkings, fanduel, caesars, betmgm, etc"
    )

    sportsbook_url: Optional[str] = Field(
        None,
        description="Deep link to bet if available"
    )

    start_time_et: str = Field(
        ...,
        description="ISO string in America/New_York timezone"
    )

    game_status: GameStatus = Field(
        ...,
        description="SCHEDULED, LIVE, or FINAL"
    )

    is_live_bet_candidate: bool = Field(
        False,
        description="True if LIVE and model triggers >= threshold"
    )

    was_game_already_started: bool = Field(
        False,
        description="True if pick created after start_time_et (community can live bet)"
    )

    # ==========================================
    # PICK CONTEXT (OPTIONAL BUT RECOMMENDED)
    # ==========================================

    player_name: Optional[str] = Field(
        None,
        description="For props only. Null for game picks."
    )

    home_team: str = Field(..., description="Home team name")
    away_team: str = Field(..., description="Away team name")

    prop_type: Optional[str] = Field(
        None,
        description="For props: points, rebounds, assists, etc. Null for game picks."
    )

    # ==========================================
    # CANONICAL MACHINE FIELDS (STABLE)
    # ==========================================

    pick_id: str = Field(
        ...,
        description="Unique 12-char deterministic ID for deduplication"
    )

    event_id: str = Field(
        ...,
        description="Provider event ID"
    )

    player_id: Optional[str] = Field(
        None,
        description="Canonical internal player ID. Null for game picks."
    )

    team_id: Optional[str] = Field(
        None,
        description="Team ID if applicable"
    )

    source_ids: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider IDs: playbook_event_id, odds_api_event_id, "
                    "balldontlie_game_id, dk_event_id"
    )

    # ==========================================
    # TIMESTAMPS
    # ==========================================

    created_at: str = Field(
        ...,
        description="ISO timestamp when pick was created"
    )

    published_at: Optional[str] = Field(
        None,
        description="ISO timestamp when pick was published"
    )

    graded_at: Optional[str] = Field(
        None,
        description="ISO timestamp when pick was graded. Null if pending."
    )

    # ==========================================
    # SCORING & TIER
    # ==========================================

    final_score: float = Field(
        ...,
        ge=6.5,
        description="Final composite score. MUST be >= 6.5 to be returned."
    )

    base_score: float = Field(
        ...,
        description="Score before Jason Sim boost"
    )

    tier: TierLevel = Field(
        ...,
        description="Pick tier: TITANIUM_SMASH, GOLD_STAR, EDGE_LEAN, MONITOR, PASS"
    )

    units: float = Field(
        ...,
        description="Recommended unit size based on tier"
    )

    titanium_flag: bool = Field(
        False,
        description="True if Titanium criteria met (3/4 engines + score >= 8.0)"
    )

    titanium_modules_hit: List[str] = Field(
        default_factory=list,
        description="Modules that contributed to Titanium: ['AI', 'Research', 'Jarvis']"
    )

    titanium_reasons: List[str] = Field(
        default_factory=list,
        description="Human-readable reasons for Titanium designation"
    )

    # ==========================================
    # ENGINE BREAKDOWN (4 ENGINES SEPARATED)
    # ==========================================

    ai_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="AI Engine score (8-model blend): 0-10"
    )

    research_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Research Engine score (market inefficiencies + pillars): 0-10"
    )

    esoteric_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Esoteric Engine score (Vedic, Fib, Vortex, numerology): 0-10"
    )

    jarvis_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Jarvis Engine score (gematria + sacred triggers): 0-10"
    )

    # Detailed breakdowns
    research_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Research pillars breakdown"
    )

    esoteric_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Esoteric components breakdown"
    )

    jarvis_breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Jarvis triggers and ritual score"
    )

    # ==========================================
    # JASON SIM 2.0 (POST-PICK CONFLUENCE)
    # ==========================================

    jason_ran: bool = Field(
        False,
        description="True if Jason Sim executed successfully"
    )

    jason_sim_boost: float = Field(
        0.0,
        description="Points added/subtracted by Jason Sim"
    )

    jason_blocked: bool = Field(
        False,
        description="True if Jason Sim blocked the pick"
    )

    jason_win_pct_home: float = Field(
        50.0,
        ge=0.0,
        le=100.0,
        description="Simulated home team win percentage"
    )

    jason_win_pct_away: float = Field(
        50.0,
        ge=0.0,
        le=100.0,
        description="Simulated away team win percentage"
    )

    jason_projected_total: Optional[float] = Field(
        None,
        description="Simulated game total"
    )

    jason_variance_flag: Optional[str] = Field(
        None,
        description="HIGH, MED, or LOW variance"
    )

    jason_injury_state: str = Field(
        "CONFIRMED_ONLY",
        description="Injury handling mode for sim"
    )

    jason_sim_count: int = Field(
        0,
        description="Number of simulations run"
    )

    confluence_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons for confluence boosts (includes Jason signals)"
    )

    # ==========================================
    # GRADING (FILLED AFTER GAME)
    # ==========================================

    result: Optional[str] = Field(
        None,
        description="WIN, LOSS, or PUSH. Null if not graded yet."
    )

    actual_value: Optional[float] = Field(
        None,
        description="Actual stat/score value after game"
    )

    units_won_lost: Optional[float] = Field(
        None,
        description="Units won or lost (accounting for odds)"
    )

    # CLV (Closing Line Value)
    bet_line_at_post: float = Field(
        ...,
        description="Line when pick was posted"
    )

    closing_line: Optional[float] = Field(
        None,
        description="Line at game start (closing)"
    )

    clv: Optional[float] = Field(
        None,
        description="Closing Line Value. Positive = beat the closing line"
    )

    beat_clv: Optional[bool] = Field(
        None,
        description="True if we got a better line than closing"
    )

    process_grade: Optional[str] = Field(
        None,
        description="Process evaluation: EXCELLENT, GOOD, FAIR, POOR"
    )

    # ==========================================
    # VALIDATION & INTEGRITY
    # ==========================================

    injury_status: str = Field(
        "HEALTHY",
        description="HEALTHY, QUESTIONABLE, OUT, DOUBTFUL"
    )

    book_validated: bool = Field(
        True,
        description="True if prop/line confirmed available at book"
    )

    prop_available_at_books: List[str] = Field(
        default_factory=list,
        description="Books where prop was confirmed available"
    )

    validation_errors: List[str] = Field(
        default_factory=list,
        description="Any validation warnings or errors"
    )

    contradiction_blocked: bool = Field(
        False,
        description="True if this pick was blocked due to contradiction with higher-scoring opposite side"
    )

    # ==========================================
    # METADATA
    # ==========================================

    date: str = Field(
        ...,
        description="Date in ET timezone: YYYY-MM-DD"
    )

    run_id: Optional[str] = Field(
        None,
        description="UUID for batch tracking"
    )

    pick_hash: Optional[str] = Field(
        None,
        description="SHA256 hash for deterministic uniqueness"
    )

    grade_status: str = Field(
        "PENDING",
        description="PENDING, WAITING_FINAL, GRADED, FAILED, UNRESOLVED"
    )

    class Config:
        use_enum_values = True


class PickOutputBatch(BaseModel):
    """Batch response with picks and metadata"""

    sport: str
    date_et: str
    total_picks: int
    props: List[PickOutputSchema]
    game_picks: List[PickOutputSchema]

    # Debug/analytics
    total_candidates: int = 0
    filtered_below_6_5: int = 0
    filtered_contradictions: int = 0
    filtered_out_of_window: int = 0
    filtered_missing_time: int = 0

    timestamp: str
    cache_hit: bool = False

    class Config:
        use_enum_values = True
