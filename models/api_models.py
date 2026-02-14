"""
Pydantic models for API request/response validation.
Provides type safety, automatic validation, and OpenAPI documentation.

v12.0 - Production hardened with StandardPickOutput schema
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class Sport(str, Enum):
    NBA = "nba"
    NFL = "nfl"
    MLB = "mlb"
    NHL = "nhl"


class BetType(str, Enum):
    SPREAD = "spread"
    MONEYLINE = "moneyline"
    TOTAL = "total"
    OVER = "over"
    UNDER = "under"
    PROP = "prop"
    PLAYER_PROP = "player_prop"


class BetResult(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"


class BetStatus(str, Enum):
    PENDING = "PENDING"
    GRADED = "GRADED"


# ============================================================================
# BASE RESPONSE MODEL
# ============================================================================

class APIResponse(BaseModel):
    """Standardized API response wrapper."""
    status: str = "ok"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    class Config:
        extra = "allow"  # Allow additional fields


class ErrorResponse(BaseModel):
    """Standardized error response."""
    status: str = "error"
    error: str
    detail: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================================
# BET TRACKING MODELS
# ============================================================================

class TrackBetRequest(BaseModel):
    """Request model for tracking a bet."""
    user_id: str = Field(default="anonymous", description="User identifier")
    sport: str = Field(..., description="Sport code (NBA, NFL, MLB, NHL)")
    game_id: str = Field(..., description="Unique game identifier")
    game: str = Field(default="Unknown Game", description="Game description")
    bet_type: str = Field(..., description="Type of bet (spread, moneyline, total, prop)")
    selection: str = Field(..., description="Selected outcome")
    line: Optional[float] = Field(None, description="Point spread or total line")
    odds: int = Field(..., description="American odds format (-110, +150, etc.)")
    sportsbook: str = Field(..., description="Sportsbook name")
    stake: float = Field(default=0, ge=0, description="Bet amount")
    ai_score: Optional[float] = Field(None, ge=0, le=20, description="AI confidence score")
    confluence_level: Optional[str] = Field(None, description="Signal confluence level")

    @validator('sport')
    def validate_sport(cls, v):
        valid = ['nba', 'nfl', 'mlb', 'nhl', 'NBA', 'NFL', 'MLB', 'NHL']
        if v.lower() not in [s.lower() for s in valid]:
            raise ValueError(f'Invalid sport: {v}. Must be one of: NBA, NFL, MLB, NHL')
        return v.upper()

    @validator('odds')
    def validate_odds(cls, v):
        if v == 0 or (v > -100 and v < 100):
            raise ValueError('Invalid odds. American odds must be <= -100 or >= 100')
        return v


class TrackBetResponse(APIResponse):
    """Response model for tracked bet."""
    bet_id: str
    bet: Dict[str, Any]


class GradeBetRequest(BaseModel):
    """Request model for grading a bet."""
    result: BetResult = Field(..., description="Bet result: WIN, LOSS, or PUSH")
    actual_score: Optional[str] = Field(None, description="Final score or outcome")


# ============================================================================
# PARLAY MODELS
# ============================================================================

class ParlayLegRequest(BaseModel):
    """Request model for adding a parlay leg."""
    user_id: str = Field(..., description="User identifier")
    sport: str = Field(..., description="Sport code")
    game_id: str = Field(..., description="Game identifier")
    game: str = Field(default="Unknown Game", description="Game description")
    bet_type: str = Field(..., description="Bet type")
    selection: str = Field(..., description="Selected outcome")
    line: Optional[float] = Field(None, description="Line value")
    odds: int = Field(..., description="American odds")
    ai_score: Optional[float] = Field(None, description="AI score")

    @validator('sport')
    def validate_sport(cls, v):
        return v.upper()

    @validator('odds')
    def validate_odds(cls, v):
        if v == 0 or (v > -100 and v < 100):
            raise ValueError('Invalid odds format')
        return v


class PlaceParlayRequest(BaseModel):
    """Request model for placing a parlay."""
    user_id: str = Field(default="anonymous", description="User identifier")
    sportsbook: str = Field(..., description="Target sportsbook")
    stake: float = Field(default=0, ge=0, description="Bet amount")
    use_current_slip: bool = Field(default=True, description="Use current parlay slip")
    legs: Optional[List[Dict[str, Any]]] = Field(None, description="Manual legs if not using slip")


class GradeParlayRequest(BaseModel):
    """Request model for grading a parlay."""
    result: BetResult = Field(..., description="Parlay result: WIN, LOSS, or PUSH")


class ParlayCalculateRequest(BaseModel):
    """Request model for parlay odds calculation."""
    legs: List[Dict[str, Any]] = Field(..., min_items=2, description="Parlay legs with odds")
    stake: float = Field(default=0, ge=0, description="Stake amount for payout calculation")


# ============================================================================
# USER PREFERENCES MODELS
# ============================================================================

class NotificationPreferences(BaseModel):
    """User notification settings."""
    smash_alerts: bool = True
    odds_movement: bool = True
    bet_results: bool = True


class UserPreferencesRequest(BaseModel):
    """Request model for user preferences."""
    favorite_books: List[str] = Field(
        default=["draftkings", "fanduel", "betmgm"],
        description="Preferred sportsbooks in order"
    )
    default_bet_amount: float = Field(default=25, ge=0, description="Default stake")
    auto_best_odds: bool = Field(default=True, description="Auto-select best odds")
    notifications: NotificationPreferences = Field(
        default_factory=NotificationPreferences,
        description="Notification settings"
    )


# ============================================================================
# GRADER MODELS
# ============================================================================

class RunAuditRequest(BaseModel):
    """Request model for running grader audit."""
    days_back: int = Field(default=1, ge=1, le=30, description="Days to audit")
    apply_changes: bool = Field(default=False, description="Apply weight adjustments")
    sports: Optional[List[str]] = Field(None, description="Specific sports to audit")


class AdjustWeightsRequest(BaseModel):
    """Request model for manual weight adjustment."""
    weight_name: str = Field(..., description="Name of weight to adjust")
    adjustment: float = Field(..., ge=-1.0, le=1.0, description="Adjustment value")
    reason: Optional[str] = Field(None, description="Reason for adjustment")


# ============================================================================
# LEARNING MODELS
# ============================================================================

class LogPickRequest(BaseModel):
    """Request model for logging a pick."""
    sport: str = Field(..., description="Sport code")
    game_id: str = Field(..., description="Game identifier")
    player: Optional[str] = Field(None, description="Player name for props")
    market: str = Field(..., description="Market type")
    line: float = Field(..., description="Line value")
    prediction: str = Field(..., description="Over/Under/Home/Away")
    ai_score: float = Field(..., ge=0, le=20, description="AI confidence")
    factors: Optional[Dict[str, Any]] = Field(None, description="Scoring factors used")


class GradePickRequest(BaseModel):
    """Request model for grading a pick."""
    pick_id: str = Field(..., description="Pick identifier")
    actual_value: float = Field(..., description="Actual stat/outcome")
    result: BetResult = Field(..., description="WIN, LOSS, or PUSH")


# ============================================================================
# COMMUNITY MODELS
# ============================================================================

class CommunityVoteRequest(BaseModel):
    """Request model for community voting."""
    user_id: str = Field(..., description="User identifier")
    game_id: str = Field(..., description="Game identifier")
    vote: str = Field(..., description="Vote selection (home/away/over/under)")
    confidence: int = Field(default=5, ge=1, le=10, description="Confidence level 1-10")


# ============================================================================
# AFFILIATE MODELS
# ============================================================================

class AffiliateConfigRequest(BaseModel):
    """Request model for affiliate link configuration."""
    sportsbook: str = Field(..., description="Sportsbook identifier")
    affiliate_code: str = Field(..., description="Affiliate tracking code")
    custom_url: Optional[str] = Field(None, description="Custom affiliate URL")


# ============================================================================
# STANDARDIZED PICK OUTPUT (v12.0 Production Hardened)
# ============================================================================

class PickStatus(str, Enum):
    """Pick status enumeration."""
    PRE_GAME = "PRE_GAME"
    IN_PROGRESS = "IN_PROGRESS"
    LIVE = "LIVE"
    FINAL = "FINAL"
    # Deprecated aliases for backwards compatibility
    UPCOMING = "PRE_GAME"
    STARTED = "IN_PROGRESS"


class MarketType(str, Enum):
    """Market type enumeration."""
    SPREAD = "spread"
    MONEYLINE = "moneyline"
    TOTAL = "total"
    PLAYER_PROP = "player_prop"


class JasonSimBlock(BaseModel):
    """Jason Sim confluence analysis block."""
    research_score: float = Field(..., ge=0, le=10, description="Research engine score (0-10)")
    esoteric_score: float = Field(..., ge=0, le=10, description="Esoteric engine score (0-10)")
    alignment_pct: float = Field(default=0, ge=0, le=100, description="Engine alignment percentage")
    confluence_level: str = Field(default="DIVERGENT", description="IMMORTAL|JARVIS_PERFECT|PERFECT|STRONG|MODERATE|DIVERGENT")
    confluence_boost: float = Field(default=0, description="Confluence bonus points")


class EngineScores(BaseModel):
    """All 4 engine scores block."""
    ai_score: float = Field(..., ge=0, le=10, description="AI engine score (0-10)")
    research_score: float = Field(..., ge=0, le=10, description="Research engine score (0-10)")
    esoteric_score: float = Field(..., ge=0, le=10, description="Esoteric engine score (0-10)")
    jarvis_rs: float = Field(..., ge=0, le=10, description="Jarvis engine score (0-10)")


class StandardPickOutput(BaseModel):
    """
    Standardized pick output schema per production hardening spec.

    ALL pick-generating endpoints should return picks in this format.
    """
    # Required event identification
    sport: str = Field(..., description="Sport code (NBA, NFL, MLB, NHL)")
    league: str = Field(default="", description="League name")
    event_id: str = Field(..., description="Unique event identifier")
    start_time_et: str = Field(..., description="Game start time in ET timezone")
    status: PickStatus = Field(default=PickStatus.UPCOMING, description="UPCOMING|LIVE|STARTED|FINAL")

    # Market details
    market: MarketType = Field(..., description="spread|moneyline|total|player_prop")
    selection: str = Field(..., description="Selected outcome/side")
    line: Optional[float] = Field(None, description="Line value (spread/total)")

    # Best odds info
    best_book: str = Field(default="", description="Sportsbook with best odds")
    best_odds_american: int = Field(default=-110, description="Best available American odds")
    book_links: Dict[str, Optional[str]] = Field(default_factory=dict, description="Sportsbook deeplinks")

    # Engine scores (all 0-10)
    ai_score: float = Field(..., ge=0, le=10, description="AI engine score (0-10)")
    research_score: float = Field(..., ge=0, le=10, description="Research engine score (0-10)")
    esoteric_score: float = Field(..., ge=0, le=10, description="Esoteric engine score (0-10)")
    jarvis_rs: float = Field(..., ge=0, le=10, description="Jarvis engine score (0-10)")

    # Engine reasons
    ai_reasons: List[str] = Field(default_factory=list, description="AI engine reasoning")
    research_reasons: List[str] = Field(default_factory=list, description="Research engine reasoning")
    esoteric_reasons: List[str] = Field(default_factory=list, description="Esoteric engine reasoning")
    jarvis_reasons: List[str] = Field(default_factory=list, description="Jarvis engine reasoning")

    # Jason Sim confluence block
    jason_sim: JasonSimBlock = Field(default_factory=lambda: JasonSimBlock(
        research_score=5.0, esoteric_score=5.0
    ), description="Jason Sim confluence analysis")

    # Final scoring
    base_score: float = Field(..., ge=0, le=10, description="Base score before confluence")
    final_score: float = Field(..., ge=0, le=10, description="Final blended score (0-10)")
    tier: str = Field(..., description="TITANIUM_SMASH|GOLD_STAR|EDGE_LEAN|MONITOR|PASS")
    unit_size: float = Field(default=0, ge=0, description="Recommended unit size")

    # Titanium (mandatory when triggered)
    titanium: bool = Field(default=False, description="Whether Titanium tier triggered")
    titanium_reasons: List[str] = Field(default_factory=list, description="Titanium qualifying engines")

    # Explanation
    reasons: List[str] = Field(default_factory=list, description="Combined reasoning")
    data_quality_flags: List[str] = Field(default_factory=list, description="Data quality warnings")

    # Optional player prop fields
    player_name: Optional[str] = Field(None, description="Player name for props")
    player_team: Optional[str] = Field(None, description="Player team for props")
    prop_type: Optional[str] = Field(None, description="Prop type (points, rebounds, etc.)")
    prop_line: Optional[float] = Field(None, description="Prop line value")

    # Metadata
    jarvis_active: bool = Field(default=False, description="Whether Jarvis triggers fired")
    jarvis_hits_count: int = Field(default=0, description="Number of Jarvis triggers hit")
    jarvis_triggers_hit: List[Dict[str, Any]] = Field(default_factory=list, description="Jarvis trigger details")

    # Timestamps
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Pick generation timestamp")

    class Config:
        extra = "allow"  # Allow additional fields for backwards compatibility


class CommunityPickOutput(BaseModel):
    """
    Community-filtered pick output.

    Only includes picks with final_score >= 6.5 (COMMUNITY_MIN_SCORE).
    Inherits from StandardPickOutput but validates community threshold.
    """
    picks: List[StandardPickOutput] = Field(..., description="Community-worthy picks (>= 6.5)")
    total_analyzed: int = Field(default=0, description="Total picks analyzed")
    filtered_count: int = Field(default=0, description="Picks meeting community threshold")
    filter_threshold: float = Field(default=6.5, description="Minimum score threshold")

    @validator('picks')
    def validate_community_threshold(cls, v):
        # All picks must meet community threshold
        return [p for p in v if p.final_score >= 6.5]


class LiveBetOutput(BaseModel):
    """
    Live betting pick output.

    For games currently in progress.
    """
    sport: str = Field(..., description="Sport code")
    type: str = Field(default="LIVE_BETS", description="Output type")
    picks: List[StandardPickOutput] = Field(..., description="Live betting picks")
    live_games_count: int = Field(default=0, description="Number of live games")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    @validator('picks')
    def validate_live_status(cls, v):
        # Ensure all picks have LIVE or STARTED status
        for pick in v:
            if pick.status not in [PickStatus.LIVE, PickStatus.STARTED]:
                pick.status = PickStatus.LIVE
        return v
