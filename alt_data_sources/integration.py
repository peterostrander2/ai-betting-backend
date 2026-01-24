"""
Alternative Data Integration - v10.68
=====================================
Combines all alternative data sources into unified context
for the scoring pipeline.

Integration Points:
1. Injury alerts → Hospital Fade pillar boost
2. Finnhub sentiment → Alternative sharp signal
3. News trending → Public sentiment indicator
4. FRED economics → Esoteric score component
5. ESPN lineups → Starter confirmation + referee tendencies
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .twitter_api import (
    get_twitter_injury_alerts,
    get_twitter_sentiment,
    is_twitter_configured
)
from .finnhub_api import (
    get_sportsbook_sentiment,
    get_market_sentiment,
    is_finnhub_configured
)
from .serpapi_news import (
    get_injury_news,
    get_trending_news,
    is_serpapi_configured
)
from .fred_api import (
    get_economic_sentiment,
    get_consumer_confidence,
    is_fred_configured
)
from .espn_lineups import (
    get_lineups_for_game,
    get_referee_impact,
    get_espn_status
)

logger = logging.getLogger(__name__)

# Cache for combined context
_context_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 600  # 10 minutes


def get_alt_data_status() -> Dict[str, Any]:
    """Get status of all alternative data sources."""
    espn_status = get_espn_status()
    return {
        "twitter": {
            "configured": is_twitter_configured(),
            "features": ["injury_alerts", "sentiment"]
        },
        "finnhub": {
            "configured": is_finnhub_configured(),
            "features": ["sportsbook_sentiment", "market_sentiment"]
        },
        "serpapi": {
            "configured": is_serpapi_configured(),
            "features": ["injury_news", "trending"]
        },
        "fred": {
            "configured": is_fred_configured(),
            "features": ["economic_sentiment", "consumer_confidence"]
        },
        "espn": {
            "configured": espn_status.get("configured", True),  # ESPN is always free
            "features": espn_status.get("features", [])
        },
        "any_configured": any([
            is_twitter_configured(),
            is_finnhub_configured(),
            is_serpapi_configured(),
            is_fred_configured(),
            True  # ESPN always available
        ])
    }


async def get_alternative_data_context(
    sport: str,
    teams: List[str] = None,
    include_injuries: bool = True,
    include_sentiment: bool = True,
    include_economic: bool = True,
    include_lineups: bool = True
) -> Dict[str, Any]:
    """
    Fetch all alternative data in parallel and return unified context.

    Args:
        sport: Sport code (nba, nfl, mlb, nhl)
        teams: Optional list of team names to focus on [home, away]
        include_injuries: Include Twitter/SerpAPI injury alerts
        include_sentiment: Include Finnhub/Twitter sentiment
        include_economic: Include FRED economic data
        include_lineups: Include ESPN lineups and referee data

    Returns:
        {
            "available": bool,
            "injury_alerts": {
                "combined": [...],  # Merged from all sources
                "twitter_count": int,
                "serpapi_count": int,
                "high_confidence": [...]  # Confidence >= 0.7
            },
            "sentiment": {
                "sportsbook": {...},  # Finnhub
                "market": {...},  # Finnhub
                "social": {...},  # Twitter
                "composite": float  # -1 to 1
            },
            "economic": {
                "sentiment": float,
                "risk_appetite": str,
                "consumer_confidence": float
            },
            "lineups": {
                "available": bool,
                "starters": {...},
                "officials": [...],
                "referee_analysis": {...}
            },
            "edge_signals": {
                "institutional_move": bool,
                "breaking_news_strength": float,
                "economic_tailwind": bool,
                "volume_spike": bool,
                "referee_over_lean": bool
            },
            "scoring_adjustments": {
                "hospital_fade_boost": float,  # Extra boost for injury pillar
                "sharp_alternative": float,  # Alternative sharp signal
                "esoteric_alt_data": float,  # Component for esoteric score
                "referee_adjustment": float  # Adjustment based on ref tendencies
            }
        }
    """
    cache_key = f"alt_context:{sport}:{'-'.join(teams or [])}"

    # Check cache
    if cache_key in _context_cache:
        entry = _context_cache[cache_key]
        if datetime.now().timestamp() < entry.get("expires_at", 0):
            return entry.get("data")

    # Default response
    result = {
        "available": False,
        "injury_alerts": {
            "combined": [],
            "twitter_count": 0,
            "serpapi_count": 0,
            "high_confidence": []
        },
        "sentiment": {
            "sportsbook": {},
            "market": {},
            "social": {},
            "composite": 0.0
        },
        "economic": {
            "sentiment": 0.0,
            "risk_appetite": "MEDIUM",
            "consumer_confidence": 70.0
        },
        "lineups": {
            "available": False,
            "starters": {"home": [], "away": []},
            "officials": [],
            "referee_analysis": {}
        },
        "edge_signals": {
            "institutional_move": False,
            "breaking_news_strength": 0.0,
            "economic_tailwind": False,
            "volume_spike": False,
            "referee_over_lean": False
        },
        "scoring_adjustments": {
            "hospital_fade_boost": 0.0,
            "sharp_alternative": 0.0,
            "esoteric_alt_data": 0.0,
            "referee_adjustment": 0.0
        },
        "sources_used": [],
        "fetch_time": datetime.now().isoformat()
    }

    # Prepare tasks
    tasks = []
    task_names = []

    if include_injuries:
        if is_twitter_configured():
            tasks.append(get_twitter_injury_alerts(sport, teams))
            task_names.append("twitter_injuries")
        if is_serpapi_configured():
            tasks.append(get_injury_news(sport, teams))
            task_names.append("serpapi_injuries")

    if include_sentiment:
        if is_finnhub_configured():
            tasks.append(get_sportsbook_sentiment())
            task_names.append("finnhub_sportsbook")
            tasks.append(get_market_sentiment())
            task_names.append("finnhub_market")
        if is_twitter_configured() and teams and len(teams) >= 2:
            tasks.append(get_twitter_sentiment(sport, teams[0], teams[1]))
            task_names.append("twitter_sentiment")

    if include_economic and is_fred_configured():
        tasks.append(get_economic_sentiment())
        task_names.append("fred_economic")

    # ESPN lineups and referees (always available - free API)
    if include_lineups and teams and len(teams) >= 2:
        tasks.append(get_lineups_for_game(sport, teams[0], teams[1]))
        task_names.append("espn_lineups")

    if not tasks:
        logger.debug("No alternative data sources configured")
        return result

    # Execute all fetches in parallel
    try:
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Process responses
        twitter_injuries = []
        serpapi_injuries = []
        sportsbook_sentiment = {}
        market_sentiment = {}
        social_sentiment = {}
        economic_data = {}
        espn_lineups_data = {}

        for name, response in zip(task_names, responses):
            if isinstance(response, Exception):
                logger.debug(f"Alt data source {name} failed: {response}")
                continue

            if not response.get("available", False):
                continue

            result["sources_used"].append(name)

            if name == "twitter_injuries":
                twitter_injuries = response.get("alerts", [])
            elif name == "serpapi_injuries":
                serpapi_injuries = response.get("injuries", [])
            elif name == "finnhub_sportsbook":
                sportsbook_sentiment = response
            elif name == "finnhub_market":
                market_sentiment = response
            elif name == "twitter_sentiment":
                social_sentiment = response
            elif name == "fred_economic":
                economic_data = response
            elif name == "espn_lineups":
                espn_lineups_data = response

        # Combine injury alerts
        all_injuries = twitter_injuries + serpapi_injuries
        high_confidence = [inj for inj in all_injuries if inj.get("confidence", 0) >= 0.7]

        result["injury_alerts"] = {
            "combined": all_injuries,
            "twitter_count": len(twitter_injuries),
            "serpapi_count": len(serpapi_injuries),
            "high_confidence": high_confidence
        }

        # Process sentiment
        result["sentiment"] = {
            "sportsbook": sportsbook_sentiment,
            "market": market_sentiment,
            "social": social_sentiment,
            "composite": _calculate_composite_sentiment(
                sportsbook_sentiment,
                market_sentiment,
                social_sentiment
            )
        }

        # Process economic data
        if economic_data:
            result["economic"] = {
                "sentiment": economic_data.get("sentiment", 0),
                "risk_appetite": economic_data.get("risk_appetite", "MEDIUM"),
                "consumer_confidence": economic_data.get("consumer_confidence", 70)
            }

        # Process ESPN lineups and referees
        if espn_lineups_data:
            ref_analysis = espn_lineups_data.get("referee_analysis", {})
            result["lineups"] = {
                "available": True,
                "starters": espn_lineups_data.get("starters", {"home": [], "away": []}),
                "starters_count": espn_lineups_data.get("starters_count", {}),
                "officials": espn_lineups_data.get("officials", []),
                "referee_analysis": ref_analysis
            }

        # Calculate edge signals
        ref_analysis = result.get("lineups", {}).get("referee_analysis", {})
        result["edge_signals"] = {
            "institutional_move": sportsbook_sentiment.get("institutional_move", False),
            "breaking_news_strength": len(high_confidence) / 10.0,  # 0-1 scale
            "economic_tailwind": economic_data.get("sentiment", 0) > 0.3,
            "volume_spike": sportsbook_sentiment.get("volume_spike", False),
            "referee_over_lean": ref_analysis.get("over_tendency", 0.5) > 0.52
        }

        # Calculate scoring adjustments
        result["scoring_adjustments"] = _calculate_scoring_adjustments(result)

        result["available"] = len(result["sources_used"]) > 0

        # Cache result
        _context_cache[cache_key] = {
            "data": result,
            "expires_at": datetime.now().timestamp() + CACHE_TTL_SECONDS
        }

        logger.info(f"Alt data: {len(result['sources_used'])} sources, "
                   f"{len(all_injuries)} injuries, "
                   f"sentiment={result['sentiment']['composite']:.2f}")

        return result

    except Exception as e:
        logger.warning(f"Alternative data context failed: {e}")
        return result


def _calculate_composite_sentiment(
    sportsbook: Dict,
    market: Dict,
    social: Dict
) -> float:
    """Calculate weighted composite sentiment from all sources."""
    sentiment = 0.0
    weight_total = 0.0

    if sportsbook.get("available"):
        sentiment += sportsbook.get("sentiment", 0) * 0.4
        weight_total += 0.4

    if market.get("available"):
        # Convert market mood to number
        mood = market.get("market_mood", "NEUTRAL")
        mood_value = {"RISK_ON": 0.5, "RISK_OFF": -0.5, "NEUTRAL": 0}.get(mood, 0)
        sentiment += mood_value * 0.3
        weight_total += 0.3

    if social.get("available"):
        # Social sentiment edge
        edge = social.get("sentiment_edge", "NEUTRAL")
        edge_value = {"HOME": 0.3, "AWAY": -0.3, "NEUTRAL": 0}.get(edge, 0)
        sentiment += edge_value * 0.3
        weight_total += 0.3

    if weight_total > 0:
        return sentiment / weight_total
    return 0.0


def _calculate_scoring_adjustments(context: Dict) -> Dict[str, float]:
    """
    Calculate how alternative data should adjust pick scores.

    Returns adjustments that can be applied in calculate_pick_score():
    - hospital_fade_boost: Extra points for Hospital Fade pillar when injuries detected
    - sharp_alternative: Alternative sharp signal when Finnhub shows institutional move
    - esoteric_alt_data: Component for esoteric score
    - referee_adjustment: Adjustment based on referee tendencies (for totals)
    """
    adjustments = {
        "hospital_fade_boost": 0.0,
        "sharp_alternative": 0.0,
        "esoteric_alt_data": 0.0,
        "referee_adjustment": 0.0
    }

    edge_signals = context.get("edge_signals", {})
    sentiment = context.get("sentiment", {})
    economic = context.get("economic", {})
    injuries = context.get("injury_alerts", {})
    lineups = context.get("lineups", {})

    # Hospital Fade Boost
    # If we detect breaking injury news with high confidence, boost hospital fade
    high_conf_injuries = len(injuries.get("high_confidence", []))
    if high_conf_injuries >= 3:
        adjustments["hospital_fade_boost"] = 0.5  # +0.5 to hospital fade pillar
    elif high_conf_injuries >= 1:
        adjustments["hospital_fade_boost"] = 0.25

    # Sharp Alternative
    # If Finnhub shows institutional movement and no traditional sharp signal
    if edge_signals.get("institutional_move"):
        adjustments["sharp_alternative"] = 1.0  # Acts as MODERATE sharp signal

    if edge_signals.get("volume_spike"):
        adjustments["sharp_alternative"] += 0.5

    # Esoteric Alt Data Component
    # Combines economic sentiment + news momentum
    econ_sentiment = economic.get("sentiment", 0)
    news_strength = edge_signals.get("breaking_news_strength", 0)

    if econ_sentiment > 0.3:
        adjustments["esoteric_alt_data"] += 0.25
    elif econ_sentiment < -0.3:
        adjustments["esoteric_alt_data"] -= 0.15

    if news_strength > 0.5:
        adjustments["esoteric_alt_data"] += 0.2

    # Referee Adjustment (for totals bets)
    # High-foul refs = slight over lean, lets-them-play refs = slight under lean
    ref_analysis = lineups.get("referee_analysis", {})
    if ref_analysis.get("foul_tendency") == "HIGH_FOUL":
        adjustments["referee_adjustment"] = 0.15  # Slight boost to overs
    elif ref_analysis.get("foul_tendency") == "LOW_FOUL":
        adjustments["referee_adjustment"] = -0.10  # Slight lean to unders

    # Cap adjustments
    adjustments["hospital_fade_boost"] = min(0.5, adjustments["hospital_fade_boost"])
    adjustments["sharp_alternative"] = min(1.5, adjustments["sharp_alternative"])
    adjustments["esoteric_alt_data"] = max(-0.3, min(0.5, adjustments["esoteric_alt_data"]))
    adjustments["referee_adjustment"] = max(-0.2, min(0.2, adjustments["referee_adjustment"]))

    return adjustments


async def get_injury_context_for_player(
    player_name: str,
    sport: str,
    teams: List[str] = None
) -> Dict[str, Any]:
    """
    Check if a specific player has injury news from alternative sources.

    Returns:
        {
            "has_alert": bool,
            "status": str,  # OUT, DOUBTFUL, GTD, etc.
            "confidence": float,
            "source": str,
            "details": str
        }
    """
    default = {
        "has_alert": False,
        "status": "",
        "confidence": 0.0,
        "source": "",
        "details": ""
    }

    # Get all injury alerts
    context = await get_alternative_data_context(
        sport=sport,
        teams=teams,
        include_injuries=True,
        include_sentiment=False,
        include_economic=False
    )

    injuries = context.get("injury_alerts", {}).get("combined", [])

    # Search for player
    player_lower = player_name.lower()

    for injury in injuries:
        alert_player = injury.get("player_name", "").lower()
        if player_lower in alert_player or alert_player in player_lower:
            return {
                "has_alert": True,
                "status": injury.get("status", "QUESTIONABLE"),
                "confidence": injury.get("confidence", 0.5),
                "source": injury.get("source", "unknown"),
                "details": injury.get("headline", injury.get("tweet_text", ""))[:100]
            }

    return default
