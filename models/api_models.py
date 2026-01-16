"""
Pydantic models for API request/response validation.
Provides type safety, automatic validation, and OpenAPI documentation.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
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
