"""
Research Engine types - scoped to Engine 2 audit only.

v20.16+ Anti-Conflation Module

This module defines types for the Research Engine (Engine 2) semantic audit.
These types are intentionally scoped to Research only and do NOT modify
the global scoring contract in core/scoring_contract.py.

Anti-Conflation Invariants:
1. playbook_sharp and odds_line are NEVER merged
2. sharp_boost reads ONLY from playbook_sharp
3. line_boost reads ONLY from odds_line
4. If playbook_sharp.status != SUCCESS, sharp_strength MUST be NONE
"""

from enum import Enum
from typing import TypedDict, Optional, List, Dict, Any


class ComponentStatus(str, Enum):
    """Status values for Research engine components."""
    SUCCESS = "SUCCESS"      # API call succeeded, data present
    NO_DATA = "NO_DATA"      # API call succeeded but no relevant data
    ERROR = "ERROR"          # API call failed (timeout, 4xx, 5xx)
    DISABLED = "DISABLED"    # Feature flag disabled


class SharpStrength(str, Enum):
    """Sharp money signal strength levels."""
    STRONG = "STRONG"        # Divergence >= 20%
    MODERATE = "MODERATE"    # Divergence >= 10%
    MILD = "MILD"            # Divergence >= 5%
    NONE = "NONE"            # Divergence < 5% or no data


class LineStrength(str, Enum):
    """Line variance strength levels."""
    STRONG = "STRONG"        # Variance >= 2.0 pts
    MODERATE = "MODERATE"    # Variance >= 1.5 pts
    MILD = "MILD"            # Variance >= 0.5 pts
    NONE = "NONE"            # Variance < 0.5 pts or no data


# Source API constants - ONLY sources confirmed in deployed Research code
SOURCE_PLAYBOOK = "playbook_api"
SOURCE_ODDS_API = "odds_api"
SOURCE_ESPN = "espn_api"
SOURCE_INTERNAL = "internal"


# Boost thresholds (from live_data_router.py scoring)
SHARP_THRESHOLDS = {
    "STRONG": {"min_divergence": 20, "boost": 3.0},
    "MODERATE": {"min_divergence": 10, "boost": 1.5},
    "MILD": {"min_divergence": 5, "boost": 0.5},
    "NONE": {"min_divergence": 0, "boost": 0.0},
}

LINE_THRESHOLDS = {
    "STRONG": {"min_variance": 2.0, "boost": 3.0},
    "MODERATE": {"min_variance": 1.5, "boost": 1.5},
    "MILD": {"min_variance": 0.5, "boost": 1.5},
    "NONE": {"min_variance": 0.0, "boost": 0.0},
}

PUBLIC_THRESHOLDS = {
    "HIGH": {"min_pct": 75, "min_divergence": 5, "boost": 2.0},
    "MODERATE": {"min_pct": 65, "min_divergence": 5, "boost": 1.0},
    "NONE": {"min_pct": 0, "min_divergence": 0, "boost": 0.0},
}


class CallProof(TypedDict, total=False):
    """Proof that a real API call happened."""
    used_live_call: bool
    usage_counter_delta: int
    http_requests_delta: int
    two_xx_delta: int  # Named to avoid leading digit
    cache_hit: bool
    cache_policy_reason: Optional[str]


class RawInputsSummary(TypedDict, total=False):
    """Bounded summary of raw inputs (no secrets)."""
    ticket_pct: Optional[int]
    money_pct: Optional[int]
    divergence: Optional[int]
    sharp_side: Optional[str]
    line_open: Optional[float]
    line_current: Optional[float]
    line_variance: Optional[float]
    public_pct: Optional[int]


class ComponentBreakdown(TypedDict, total=False):
    """Per-component breakdown in research_breakdown."""
    value: float
    status: str  # ComponentStatus value
    source_api: str  # SOURCE_* constant
    raw_inputs_summary: RawInputsSummary
    call_proof: CallProof
    raw_signal_strength: Optional[str]  # For sharp/line strength
    raw_line_variance: Optional[float]  # For line component


class PlaybookSharp(TypedDict, total=False):
    """Playbook sharp money data - SEPARATE from odds_line."""
    status: str  # ComponentStatus
    sharp_strength: str  # SharpStrength
    ticket_pct: Optional[int]
    money_pct: Optional[int]
    divergence: Optional[int]
    sharp_side: Optional[str]


class OddsLine(TypedDict, total=False):
    """Odds API line variance data - SEPARATE from playbook_sharp."""
    status: str  # ComponentStatus
    line_strength: str  # LineStrength
    line_open: Optional[float]
    line_current: Optional[float]
    line_variance: float


class ResearchBreakdown(TypedDict, total=False):
    """Full research breakdown with anti-conflation components."""
    sharp_boost: ComponentBreakdown
    line_boost: ComponentBreakdown
    public_boost: ComponentBreakdown
    espn_odds_boost: ComponentBreakdown
    liquidity_boost: ComponentBreakdown
    base_research: float
    total: float


class AuthContext(TypedDict):
    """API key presence context."""
    key_present: bool
    key_source: str  # e.g., "env:PLAYBOOK_API_KEY"


class NetworkProof(TypedDict, total=False):
    """HTTP request deltas from real client wrappers."""
    playbook_http_requests_before: int
    playbook_http_requests_after: int
    playbook_http_requests_delta: int
    playbook_2xx_delta: int
    playbook_4xx_delta: int
    playbook_5xx_delta: int
    playbook_timeout_delta: int
    odds_http_requests_before: int
    odds_http_requests_after: int
    odds_http_requests_delta: int
    odds_2xx_delta: int
    odds_4xx_delta: int
    odds_5xx_delta: int
    odds_timeout_delta: int


class UsageCounters(TypedDict, total=False):
    """API usage counters."""
    playbook_calls: int
    odds_api_calls: int
    espn_calls: int


class CandidatePreFilter(TypedDict, total=False):
    """Pre-filter candidate with research breakdown."""
    pick_id: str
    final_score: float
    filtered_out_reason: Optional[str]
    research_breakdown: ResearchBreakdown


class ResearchCandidatesResponse(TypedDict, total=False):
    """Response shape for /debug/research-candidates/{sport}."""
    candidates_pre_filter: List[CandidatePreFilter]
    auth_context: Dict[str, AuthContext]
    network_proof: NetworkProof
    usage_counters_before: UsageCounters
    usage_counters_after: UsageCounters
    usage_counters_delta: UsageCounters
    total_candidates: int
    filtered_count: int


def compute_sharp_strength(divergence: Optional[int]) -> SharpStrength:
    """Compute sharp strength from money-ticket divergence."""
    if divergence is None or divergence < 5:
        return SharpStrength.NONE
    elif divergence >= 20:
        return SharpStrength.STRONG
    elif divergence >= 10:
        return SharpStrength.MODERATE
    else:
        return SharpStrength.MILD


def compute_line_strength(variance: Optional[float]) -> LineStrength:
    """Compute line strength from cross-book variance."""
    if variance is None or variance < 0.5:
        return LineStrength.NONE
    elif variance >= 2.0:
        return LineStrength.STRONG
    elif variance >= 1.5:
        return LineStrength.MODERATE
    else:
        return LineStrength.MILD


def get_sharp_boost(strength: SharpStrength) -> float:
    """Get boost value for sharp strength."""
    return SHARP_THRESHOLDS[strength.value]["boost"]


def get_line_boost(strength: LineStrength) -> float:
    """Get boost value for line strength."""
    return LINE_THRESHOLDS[strength.value]["boost"]


def validate_anti_conflation(
    sharp_boost_source: str,
    line_boost_source: str,
    sharp_status: str,
    sharp_reasons: List[str],
) -> List[str]:
    """
    Validate anti-conflation invariants.

    Returns list of violations (empty if all pass).
    """
    violations = []

    # Invariant 1: sharp_boost must read from playbook_api
    if sharp_boost_source != SOURCE_PLAYBOOK:
        violations.append(
            f"sharp_boost.source_api must be '{SOURCE_PLAYBOOK}', got '{sharp_boost_source}'"
        )

    # Invariant 2: line_boost must read from odds_api
    if line_boost_source != SOURCE_ODDS_API:
        violations.append(
            f"line_boost.source_api must be '{SOURCE_ODDS_API}', got '{line_boost_source}'"
        )

    # Invariant 3: If Playbook status != SUCCESS, no "Sharp" in reasons
    if sharp_status != ComponentStatus.SUCCESS.value:
        sharp_in_reasons = any("Sharp" in r for r in sharp_reasons)
        if sharp_in_reasons:
            violations.append(
                f"Reasons contain 'Sharp' but playbook_sharp.status={sharp_status}"
            )

    return violations
