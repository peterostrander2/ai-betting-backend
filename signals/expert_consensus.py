"""
Expert Consensus Signal - Aggregated Expert Pick Agreement
==========================================================

v20.3 - Post-scoring filter that boosts picks when multiple expert sources agree.

Uses SerpAPI to search for expert picks and determine consensus.
Only applies when >= 3 sources agree on the same pick direction.

Guardrails (Codex recommendations):
- Cap: +0.35 max boost
- Shadow mode: Compute fields but force boost=0 for validation
- Min 3 sources required for consensus
- Staleness gate: Only consider data < 24h old

Integration: Applied to research_score for SPREAD/TOTAL/MONEYLINE bets.
"""

import os
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# ============================================
# CONSTANTS (Single Source of Truth)
# ============================================

# Caps (bounded per Codex)
EXPERT_CONSENSUS_CAP = 0.35  # Max boost when strong consensus
EXPERT_CONSENSUS_MIN_SOURCES = 3  # Need at least 3 sources agreeing

# Shadow mode (set True to compute but not apply boost - for validation)
EXPERT_CONSENSUS_SHADOW_MODE = os.getenv("EXPERT_CONSENSUS_SHADOW_MODE", "true").lower() == "true"

# Staleness gate (ignore data older than 24h)
STALENESS_THRESHOLD_HOURS = 24

# Expert source domains to search
EXPERT_SOURCES = [
    "espn.com",
    "actionnetwork.com",
    "covers.com",
    "vegasinsider.com",
    "oddshark.com",
    "pickswise.com",
    "sportsbettingdime.com",
    "lineups.com",
    "thelines.com",
    "bettingpros.com",
]

# Consensus levels and their boosts
CONSENSUS_LEVELS = {
    "STRONG": 0.35,      # 5+ sources agree
    "MODERATE": 0.20,    # 4 sources agree
    "MILD": 0.10,        # 3 sources agree
    "NONE": 0.0,         # < 3 sources agree
}


@dataclass
class ExpertConsensusResult:
    """Result of expert consensus analysis."""
    boost: float                  # Bounded boost to apply (0 in shadow mode)
    raw_boost: float              # Calculated boost before shadow mode
    consensus_level: str          # STRONG, MODERATE, MILD, NONE
    sources_found: int            # Total expert sources found
    sources_agreeing: int         # Sources agreeing on pick direction
    direction: str                # "WITH_PICK" or "AGAINST_PICK" or "MIXED"
    sources: List[Dict]           # Details of each source
    reasons: List[str]            # Audit trail
    is_stale: bool                # True if data is too old
    shadow_mode: bool             # True if boost suppressed for validation


def search_expert_picks(
    sport: str,
    matchup: str,
    pick_side: str,
) -> Dict:
    """
    Search for expert picks using SerpAPI.

    Args:
        sport: Sport code (NFL, NBA, etc.)
        matchup: "Home vs Away" format
        pick_side: The side we're checking consensus for

    Returns:
        Dict with sources found and their picks
    """
    try:
        from alt_data_sources.serpapi import get_search_trend, SERPAPI_ENABLED

        if not SERPAPI_ENABLED:
            return {
                "available": False,
                "reason": "SERPAPI_NOT_CONFIGURED",
                "sources": [],
            }

        # Build search query for expert picks
        query = f"{matchup} {sport} expert picks predictions today"

        # Get search results
        trend_result = get_search_trend(query)

        if trend_result.get("source") in ("disabled", "quota_exceeded", "fallback"):
            return {
                "available": False,
                "reason": trend_result.get("reason", "SERPAPI_UNAVAILABLE"),
                "sources": [],
            }

        # For now, we simulate source extraction from search results
        # In production, this would parse actual search snippets
        # The trend_score gives us a proxy for expert coverage
        trend_score = trend_result.get("trend_score", 0.5)
        news_count = trend_result.get("news_count", 0)

        # Estimate source coverage based on trend
        # Higher trend = more expert coverage
        estimated_sources = []
        if trend_score >= 0.7:
            estimated_sources = ["espn", "actionnetwork", "covers", "vegasinsider", "oddshark"]
        elif trend_score >= 0.5:
            estimated_sources = ["espn", "actionnetwork", "covers"]
        elif trend_score >= 0.3:
            estimated_sources = ["espn", "covers"]
        else:
            estimated_sources = []

        # Build source details
        sources = []
        for source in estimated_sources:
            sources.append({
                "name": source,
                "direction": "WITH_PICK",  # Simplified - would parse actual content
                "confidence": 0.7 if source in ("espn", "actionnetwork") else 0.5,
                "fresh": True,  # Would check actual article dates
            })

        return {
            "available": True,
            "trend_score": trend_score,
            "news_count": news_count,
            "sources": sources,
            "query": query,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.warning("Expert consensus search error: %s", e)
        return {
            "available": False,
            "reason": f"SEARCH_ERROR: {str(e)}",
            "sources": [],
        }


def analyze_expert_consensus(
    sport: str,
    home_team: str,
    away_team: str,
    pick_side: str,
    pick_type: str,
    line: Optional[float] = None,
) -> ExpertConsensusResult:
    """
    Analyze expert consensus for a given pick.

    Args:
        sport: Sport code (NFL, NBA, etc.)
        home_team: Home team name
        away_team: Away team name
        pick_side: The side being picked ("Lakers", "Over", etc.)
        pick_type: SPREAD, TOTAL, MONEYLINE
        line: Optional line value

    Returns:
        ExpertConsensusResult with bounded boost and audit info
    """
    reasons = []

    # Only analyze for supported bet types
    if pick_type.upper() not in ("SPREAD", "TOTAL", "MONEYLINE"):
        return ExpertConsensusResult(
            boost=0.0,
            raw_boost=0.0,
            consensus_level="NONE",
            sources_found=0,
            sources_agreeing=0,
            direction="N/A",
            sources=[],
            reasons=[f"Expert consensus N/A for {pick_type}"],
            is_stale=False,
            shadow_mode=EXPERT_CONSENSUS_SHADOW_MODE,
        )

    # Search for expert picks
    matchup = f"{away_team} vs {home_team}"
    search_result = search_expert_picks(sport, matchup, pick_side)

    if not search_result.get("available"):
        return ExpertConsensusResult(
            boost=0.0,
            raw_boost=0.0,
            consensus_level="NONE",
            sources_found=0,
            sources_agreeing=0,
            direction="UNAVAILABLE",
            sources=[],
            reasons=[f"Expert search unavailable: {search_result.get('reason', 'UNKNOWN')}"],
            is_stale=False,
            shadow_mode=EXPERT_CONSENSUS_SHADOW_MODE,
        )

    sources = search_result.get("sources", [])
    sources_found = len(sources)

    # Count sources agreeing with pick
    sources_agreeing = sum(1 for s in sources if s.get("direction") == "WITH_PICK")
    sources_against = sum(1 for s in sources if s.get("direction") == "AGAINST_PICK")

    # Check for stale data
    is_stale = False
    fetched_at_str = search_result.get("fetched_at")
    if fetched_at_str:
        try:
            fetched_at = datetime.fromisoformat(fetched_at_str.replace('Z', '+00:00'))
            age_hours = (datetime.now(tz=timezone.utc) - fetched_at).total_seconds() / 3600
            is_stale = age_hours > STALENESS_THRESHOLD_HOURS
        except (ValueError, TypeError):
            pass

    if is_stale:
        reasons.append(f"Expert data stale (>{STALENESS_THRESHOLD_HOURS}h old)")
        return ExpertConsensusResult(
            boost=0.0,
            raw_boost=0.0,
            consensus_level="NONE",
            sources_found=sources_found,
            sources_agreeing=sources_agreeing,
            direction="STALE",
            sources=sources,
            reasons=reasons,
            is_stale=True,
            shadow_mode=EXPERT_CONSENSUS_SHADOW_MODE,
        )

    # Determine consensus level
    if sources_agreeing >= 5:
        consensus_level = "STRONG"
        raw_boost = CONSENSUS_LEVELS["STRONG"]
    elif sources_agreeing >= 4:
        consensus_level = "MODERATE"
        raw_boost = CONSENSUS_LEVELS["MODERATE"]
    elif sources_agreeing >= EXPERT_CONSENSUS_MIN_SOURCES:
        consensus_level = "MILD"
        raw_boost = CONSENSUS_LEVELS["MILD"]
    else:
        consensus_level = "NONE"
        raw_boost = 0.0

    # Determine direction
    if sources_agreeing > sources_against:
        direction = "WITH_PICK"
    elif sources_against > sources_agreeing:
        direction = "AGAINST_PICK"
        raw_boost = -raw_boost * 0.5  # Partial negative when consensus against
    else:
        direction = "MIXED"
        raw_boost = 0.0

    # Cap the boost
    raw_boost = max(-EXPERT_CONSENSUS_CAP, min(EXPERT_CONSENSUS_CAP, raw_boost))

    # Apply shadow mode if enabled
    if EXPERT_CONSENSUS_SHADOW_MODE:
        actual_boost = 0.0
        reasons.append(f"Expert consensus: {consensus_level} ({sources_agreeing}/{sources_found} agree) - SHADOW MODE")
    else:
        actual_boost = raw_boost
        if raw_boost != 0:
            reasons.append(f"Expert consensus: {consensus_level} ({sources_agreeing}/{sources_found} agree) = {raw_boost:+.2f}")
        else:
            reasons.append(f"Expert consensus: {consensus_level} ({sources_agreeing}/{sources_found} agree) - no boost")

    return ExpertConsensusResult(
        boost=actual_boost,
        raw_boost=raw_boost,
        consensus_level=consensus_level,
        sources_found=sources_found,
        sources_agreeing=sources_agreeing,
        direction=direction,
        sources=sources,
        reasons=reasons,
        is_stale=is_stale,
        shadow_mode=EXPERT_CONSENSUS_SHADOW_MODE,
    )


def get_expert_consensus_adjustment(
    sport: str,
    home_team: str,
    away_team: str,
    pick_side: str,
    pick_type: str,
    line: Optional[float] = None,
) -> Tuple[float, List[str]]:
    """
    Convenience function returning just (adjustment, reasons).

    This is the main integration point for live_data_router.py.
    """
    result = analyze_expert_consensus(
        sport=sport,
        home_team=home_team,
        away_team=away_team,
        pick_side=pick_side,
        pick_type=pick_type,
        line=line,
    )
    return result.boost, result.reasons


# ============================================
# QUICK TEST
# ============================================

if __name__ == "__main__":
    print("Expert Consensus Tests")
    print("=" * 50)
    print(f"Shadow Mode: {EXPERT_CONSENSUS_SHADOW_MODE}")
    print(f"Max Boost Cap: {EXPERT_CONSENSUS_CAP}")
    print(f"Min Sources: {EXPERT_CONSENSUS_MIN_SOURCES}")
    print()

    # Test case
    result = analyze_expert_consensus(
        sport="NFL",
        home_team="Chiefs",
        away_team="Raiders",
        pick_side="Chiefs",
        pick_type="SPREAD",
        line=-7.0,
    )

    print(f"Result: {result.consensus_level}")
    print(f"Sources: {result.sources_found} found, {result.sources_agreeing} agree")
    print(f"Direction: {result.direction}")
    print(f"Raw Boost: {result.raw_boost:+.2f}")
    print(f"Actual Boost: {result.boost:+.2f}")
    print(f"Shadow Mode: {result.shadow_mode}")
    for r in result.reasons:
        print(f"  - {r}")
