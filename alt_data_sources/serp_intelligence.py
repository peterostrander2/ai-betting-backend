"""
SERP Betting Intelligence - Sport-Specific Search Signal Analysis

Provides betting intelligence signals derived from Google search trends via SerpAPI.
Each signal maps to one of the 5 scoring engines with capped boost values.

Signals:
- Silent Spike (AI): High search volume + low news coverage = potential insider activity
- Sharp Chatter (Research): Mentions of sharp money, RLM, professional bettors
- Narrative (Jarvis): Revenge games, rivalries, playoff implications
- Situational (Context): Back-to-back, rest advantage, weather
- Esoteric (Esoteric): Noosphere velocity, trend momentum

All signals are subject to shadow mode and boost caps from serp_guardrails.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("serp_intelligence")

# Import base SerpAPI functions
try:
    from alt_data_sources.serpapi import (
        get_search_trend,
        get_team_buzz,
        get_player_buzz,
        SERPAPI_ENABLED,
    )
    SERPAPI_AVAILABLE = True
except ImportError:
    SERPAPI_AVAILABLE = False
    logger.warning("serpapi module not available")

# Import guardrails for boost management
try:
    from core.serp_guardrails import (
        cap_boost,
        cap_total_boost,
        apply_shadow_mode,
        is_serp_available,
        SERP_BOOST_CAPS,
    )
    GUARDRAILS_AVAILABLE = True
except ImportError:
    GUARDRAILS_AVAILABLE = False
    logger.warning("serp_guardrails module not available")

# =============================================================================
# SPORT-SPECIFIC QUERY TEMPLATES
# =============================================================================

SPORT_QUERIES = {
    "NBA": {
        "sharp": [
            "{team} sharp money",
            "{team} reverse line movement",
            "{team} professional bettors",
            "{team} betting line",
        ],
        "narrative": [
            "{team1} vs {team2} rivalry",
            "{team} revenge game",
            "{team} playoff race",
            "{team} streak",
        ],
        "situational": [
            "{team} back to back",
            "{team} rest advantage",
            "{team} travel fatigue",
        ],
        "general": [
            "{team} game today",
            "{team} injury report",
        ],
    },
    "NFL": {
        "sharp": [
            "{team} sharp action",
            "{team} reverse line movement NFL",
            "{team} betting trends",
        ],
        "narrative": [
            "{team1} vs {team2} rivalry NFL",
            "{team} revenge game",
            "{team} playoff implications",
            "{team} primetime",
        ],
        "situational": [
            "{team} weather game",
            "{team} dome team outdoors",
            "{team} west coast trip",
            "{team} short week",
        ],
        "general": [
            "{team} game today",
            "{team} injury report NFL",
        ],
    },
    "MLB": {
        "sharp": [
            "{team} sharp money MLB",
            "{team} reverse line movement baseball",
            "{team} betting odds",
        ],
        "narrative": [
            "{team1} vs {team2} rivalry",
            "{team} pennant race",
            "{team} wild card",
        ],
        "situational": [
            "{team} day game after night game",
            "{team} travel",
            "{team} bullpen tired",
        ],
        "general": [
            "{team} game today",
            "{team} starting pitcher",
        ],
    },
    "NHL": {
        "sharp": [
            "{team} sharp money NHL",
            "{team} betting line hockey",
        ],
        "narrative": [
            "{team1} vs {team2} rivalry NHL",
            "{team} playoff push",
        ],
        "situational": [
            "{team} back to back NHL",
            "{team} travel schedule",
        ],
        "general": [
            "{team} game today",
            "{team} injury report NHL",
        ],
    },
    "NCAAB": {
        "sharp": [
            "{team} sharp money college basketball",
            "{team} betting trends NCAAB",
        ],
        "narrative": [
            "{team1} vs {team2} rivalry college",
            "{team} tournament",
            "{team} conference championship",
        ],
        "situational": [
            "{team} travel",
            "{team} exam week",
        ],
        "general": [
            "{team} game today college",
        ],
    },
}

# Default queries for unknown sports
DEFAULT_QUERIES = {
    "sharp": ["{team} sharp money", "{team} betting line"],
    "narrative": ["{team1} vs {team2} rivalry", "{team} streak"],
    "situational": ["{team} rest", "{team} travel"],
    "general": ["{team} game today"],
}

# =============================================================================
# SIGNAL DETECTION FUNCTIONS
# =============================================================================

def detect_silent_spike(
    team: str,
    sport: str,
    news_count_threshold: int = 2
) -> Dict[str, Any]:
    """
    Detect Silent Spike: High search volume with low news coverage.

    This may indicate insider activity or sharp money accumulation
    that hasn't hit mainstream media yet.

    Maps to: AI Engine (max boost: 0.8)

    Args:
        team: Team name
        sport: Sport code (NBA, NFL, etc.)
        news_count_threshold: Max news results to qualify as "silent"

    Returns:
        Dict with triggered, boost, confidence, reason
    """
    if not SERPAPI_AVAILABLE:
        return _empty_signal("serpapi_unavailable")

    try:
        # Search for team game
        trend = get_search_trend(f"{team} game today")

        # Check for high volume + low news
        trend_score = trend.get("trend_score", 0.5)
        news_count = trend.get("news_count", 0)

        triggered = trend_score >= 0.7 and news_count <= news_count_threshold

        if triggered:
            # Calculate boost based on how extreme the spike is
            spike_intensity = (trend_score - 0.7) / 0.3  # 0-1 scale
            raw_boost = 0.4 + (spike_intensity * 0.4)  # 0.4-0.8 range
            boost = cap_boost("ai", raw_boost) if GUARDRAILS_AVAILABLE else min(0.8, raw_boost)
            confidence = min(90, int(spike_intensity * 50 + 50))
            reason = f"Silent spike: {trend_score:.0%} trend, only {news_count} news items"
        else:
            boost = 0.0
            confidence = 0
            reason = f"No spike: {trend_score:.0%} trend, {news_count} news items"

        return {
            "signal": "silent_spike",
            "engine": "ai",
            "triggered": triggered,
            "boost": boost,
            "confidence": confidence,
            "reason": reason,
            "raw_data": {
                "trend_score": trend_score,
                "news_count": news_count,
                "source": trend.get("source", "unknown"),
            }
        }

    except Exception as e:
        logger.warning("Silent spike detection failed: %s", e)
        return _empty_signal(f"error: {e}")


def detect_sharp_chatter(
    team: str,
    sport: str
) -> Dict[str, Any]:
    """
    Detect Sharp Chatter: Mentions of sharp money, RLM, professional bettors.

    Searches for betting-specific terms that indicate sharp action
    on a particular team.

    Maps to: Research Engine (max boost: 1.3)

    Args:
        team: Team name
        sport: Sport code (NBA, NFL, etc.)

    Returns:
        Dict with triggered, boost, confidence, reason
    """
    if not SERPAPI_AVAILABLE:
        return _empty_signal("serpapi_unavailable")

    try:
        queries = SPORT_QUERIES.get(sport, DEFAULT_QUERIES).get("sharp", [])

        # Check multiple sharp-related queries
        sharp_signals = []
        for query_template in queries[:2]:  # Limit to 2 queries to conserve quota
            query = query_template.format(team=team)
            trend = get_search_trend(query)

            if trend.get("trend_score", 0) >= 0.6:
                sharp_signals.append({
                    "query": query,
                    "score": trend.get("trend_score", 0),
                    "news": trend.get("news_count", 0),
                })

        triggered = len(sharp_signals) > 0

        if triggered:
            # Calculate boost based on signal strength
            avg_score = sum(s["score"] for s in sharp_signals) / len(sharp_signals)
            raw_boost = avg_score * 1.3  # Max 1.3 at score=1.0
            boost = cap_boost("research", raw_boost) if GUARDRAILS_AVAILABLE else min(1.3, raw_boost)
            confidence = min(85, int(avg_score * 80))
            reason = f"Sharp chatter detected ({len(sharp_signals)} signals, avg {avg_score:.0%})"
        else:
            boost = 0.0
            confidence = 0
            reason = "No significant sharp chatter found"

        return {
            "signal": "sharp_chatter",
            "engine": "research",
            "triggered": triggered,
            "boost": boost,
            "confidence": confidence,
            "reason": reason,
            "raw_data": {
                "signals": sharp_signals,
                "queries_checked": len(queries[:2]),
            }
        }

    except Exception as e:
        logger.warning("Sharp chatter detection failed: %s", e)
        return _empty_signal(f"error: {e}")


def detect_narrative(
    home_team: str,
    away_team: str,
    sport: str
) -> Dict[str, Any]:
    """
    Detect Narrative signals: Revenge games, rivalries, playoff implications.

    Strong narratives can influence player motivation and performance
    beyond what statistics predict.

    Maps to: Jarvis Engine (max boost: 0.7)

    Args:
        home_team: Home team name
        away_team: Away team name
        sport: Sport code (NBA, NFL, etc.)

    Returns:
        Dict with triggered, boost, confidence, reason, narratives_found
    """
    if not SERPAPI_AVAILABLE:
        return _empty_signal("serpapi_unavailable")

    try:
        queries = SPORT_QUERIES.get(sport, DEFAULT_QUERIES).get("narrative", [])
        narratives_found = []

        # Check rivalry query
        rivalry_query = f"{home_team} vs {away_team} rivalry"
        rivalry = get_search_trend(rivalry_query)
        if rivalry.get("trend_score", 0) >= 0.65:
            narratives_found.append({
                "type": "rivalry",
                "score": rivalry.get("trend_score", 0),
                "query": rivalry_query,
            })

        # Check revenge game (one team beat other recently)
        revenge_query = f"{home_team} revenge game {away_team}"
        revenge = get_search_trend(revenge_query)
        if revenge.get("trend_score", 0) >= 0.55:
            narratives_found.append({
                "type": "revenge",
                "score": revenge.get("trend_score", 0),
                "query": revenge_query,
            })

        triggered = len(narratives_found) > 0

        if triggered:
            # Strongest narrative drives boost
            best_score = max(n["score"] for n in narratives_found)
            narrative_types = [n["type"] for n in narratives_found]

            raw_boost = best_score * 0.7
            boost = cap_boost("jarvis", raw_boost) if GUARDRAILS_AVAILABLE else min(0.7, raw_boost)
            confidence = min(80, int(best_score * 75))
            reason = f"Narratives: {', '.join(narrative_types)} ({best_score:.0%} strength)"
        else:
            boost = 0.0
            confidence = 0
            reason = "No strong narratives detected"

        return {
            "signal": "narrative",
            "engine": "jarvis",
            "triggered": triggered,
            "boost": boost,
            "confidence": confidence,
            "reason": reason,
            "narratives_found": narratives_found,
            "raw_data": {
                "home_team": home_team,
                "away_team": away_team,
            }
        }

    except Exception as e:
        logger.warning("Narrative detection failed: %s", e)
        return _empty_signal(f"error: {e}")


def detect_situational(
    team: str,
    sport: str,
    is_back_to_back: bool = False,
    opponent_rest_days: int = None
) -> Dict[str, Any]:
    """
    Detect Situational signals: B2B, rest advantage, travel, weather.

    Situational factors that create edges not fully priced by markets.

    Maps to: Context Engine (max boost: 0.9)

    Args:
        team: Team name
        sport: Sport code (NBA, NFL, etc.)
        is_back_to_back: Known B2B status (optional)
        opponent_rest_days: Opponent's rest days (optional)

    Returns:
        Dict with triggered, boost, confidence, reason, factors
    """
    if not SERPAPI_AVAILABLE:
        return _empty_signal("serpapi_unavailable")

    try:
        factors = []
        queries = SPORT_QUERIES.get(sport, DEFAULT_QUERIES).get("situational", [])

        # Check B2B / rest queries
        for query_template in queries[:2]:
            query = query_template.format(team=team)
            trend = get_search_trend(query)

            if trend.get("trend_score", 0) >= 0.5:
                # Extract factor type from query
                factor_type = "b2b" if "back to back" in query.lower() else "situational"
                factors.append({
                    "type": factor_type,
                    "query": query,
                    "score": trend.get("trend_score", 0),
                })

        # Add known situational factors
        if is_back_to_back:
            factors.append({
                "type": "b2b_confirmed",
                "score": 0.8,
                "source": "schedule",
            })

        if opponent_rest_days is not None and opponent_rest_days >= 3:
            factors.append({
                "type": "opponent_rested",
                "score": 0.6 + (min(opponent_rest_days - 3, 3) * 0.1),
                "rest_days": opponent_rest_days,
            })

        triggered = len(factors) > 0

        if triggered:
            # Weight factors by importance
            weighted_score = sum(f["score"] * (1.2 if f["type"] in ["b2b", "b2b_confirmed"] else 1.0) for f in factors)
            weighted_score = min(1.0, weighted_score / max(1, len(factors)))

            raw_boost = weighted_score * 0.9
            boost = cap_boost("context", raw_boost) if GUARDRAILS_AVAILABLE else min(0.9, raw_boost)
            confidence = min(85, int(weighted_score * 80))
            factor_types = list(set(f["type"] for f in factors))
            reason = f"Situational: {', '.join(factor_types)}"
        else:
            boost = 0.0
            confidence = 0
            reason = "No situational factors detected"

        return {
            "signal": "situational",
            "engine": "context",
            "triggered": triggered,
            "boost": boost,
            "confidence": confidence,
            "reason": reason,
            "factors": factors,
        }

    except Exception as e:
        logger.warning("Situational detection failed: %s", e)
        return _empty_signal(f"error: {e}")


def detect_noosphere(
    home_team: str,
    away_team: str,
    player_name: str = None
) -> Dict[str, Any]:
    """
    Detect Noosphere Velocity: Collective consciousness momentum via search trends.

    Measures relative buzz between teams/player as a proxy for
    collective attention and energy flow.

    Maps to: Esoteric Engine (max boost: 0.6)

    Args:
        home_team: Home team name
        away_team: Away team name
        player_name: Optional player name for prop bets

    Returns:
        Dict with triggered, boost, confidence, reason, velocity
    """
    if not SERPAPI_AVAILABLE:
        return _empty_signal("serpapi_unavailable")

    try:
        # Get team buzz comparison
        team_buzz = get_team_buzz(home_team, away_team)
        velocity = team_buzz.get("velocity", 0)

        # Player buzz for props
        player_velocity = 0
        if player_name:
            player_buzz = get_player_buzz(player_name)
            player_velocity = (player_buzz.get("buzz_score", 0.5) - 0.5) * 2

        # Combine velocities
        combined_velocity = velocity
        if player_name:
            combined_velocity = (velocity + player_velocity) / 2

        triggered = abs(combined_velocity) >= 0.2

        if triggered:
            direction = "positive" if combined_velocity > 0 else "negative"
            intensity = abs(combined_velocity)

            raw_boost = intensity * 0.6
            boost = cap_boost("esoteric", raw_boost) if GUARDRAILS_AVAILABLE else min(0.6, raw_boost)
            confidence = min(75, int(intensity * 70))

            if combined_velocity > 0:
                favored = home_team
            else:
                favored = away_team
            reason = f"Noosphere {direction} toward {favored} ({intensity:.0%})"
        else:
            boost = 0.0
            confidence = 0
            reason = f"Noosphere neutral (velocity {combined_velocity:.2f})"

        return {
            "signal": "noosphere",
            "engine": "esoteric",
            "triggered": triggered,
            "boost": boost,
            "confidence": confidence,
            "reason": reason,
            "velocity": combined_velocity,
            "raw_data": {
                "team_velocity": velocity,
                "player_velocity": player_velocity if player_name else None,
                "direction": team_buzz.get("direction", "NEUTRAL"),
            }
        }

    except Exception as e:
        logger.warning("Noosphere detection failed: %s", e)
        return _empty_signal(f"error: {e}")


# =============================================================================
# MAIN INTELLIGENCE FUNCTIONS
# =============================================================================

def get_serp_betting_intelligence(
    sport: str,
    home_team: str,
    away_team: str,
    pick_side: str = None,
    is_back_to_back: bool = False,
    opponent_rest_days: int = None
) -> Dict[str, Any]:
    """
    Get comprehensive SERP betting intelligence for a game.

    Aggregates all signal types and returns engine-mapped boosts
    with shadow mode applied if enabled.

    Args:
        sport: Sport code (NBA, NFL, MLB, NHL, NCAAB)
        home_team: Home team name
        away_team: Away team name
        pick_side: Which side we're betting (home_team or away_team)
        is_back_to_back: Known B2B status
        opponent_rest_days: Opponent's rest advantage

    Returns:
        Dict with boosts by engine, signals, metadata
    """
    if not is_serp_available() if GUARDRAILS_AVAILABLE else not SERPAPI_AVAILABLE:
        return _empty_intelligence("serp_unavailable")

    signals = []
    boosts = {
        "ai": 0.0,
        "research": 0.0,
        "esoteric": 0.0,
        "jarvis": 0.0,
        "context": 0.0,
    }

    # Determine which team to analyze based on pick_side
    target_team = pick_side if pick_side in [home_team, away_team] else home_team

    # Run all signal detections
    try:
        # 1. Silent Spike (AI)
        spike = detect_silent_spike(target_team, sport)
        if spike["triggered"]:
            boosts["ai"] += spike["boost"]
            signals.append(spike)

        # 2. Sharp Chatter (Research)
        sharp = detect_sharp_chatter(target_team, sport)
        if sharp["triggered"]:
            boosts["research"] += sharp["boost"]
            signals.append(sharp)

        # 3. Narrative (Jarvis)
        narrative = detect_narrative(home_team, away_team, sport)
        if narrative["triggered"]:
            boosts["jarvis"] += narrative["boost"]
            signals.append(narrative)

        # 4. Situational (Context)
        situational = detect_situational(
            target_team, sport,
            is_back_to_back=is_back_to_back,
            opponent_rest_days=opponent_rest_days
        )
        if situational["triggered"]:
            boosts["context"] += situational["boost"]
            signals.append(situational)

        # 5. Noosphere (Esoteric)
        noosphere = detect_noosphere(home_team, away_team)
        if noosphere["triggered"]:
            boosts["esoteric"] += noosphere["boost"]
            signals.append(noosphere)

    except Exception as e:
        logger.error("SERP intelligence collection failed: %s", e)
        return _empty_intelligence(f"error: {e}")

    # Apply total cap across engines
    if GUARDRAILS_AVAILABLE:
        boosts = cap_total_boost(boosts)

    # Apply shadow mode (zeros boosts if enabled)
    if GUARDRAILS_AVAILABLE:
        boosts_applied = apply_shadow_mode(boosts)
    else:
        boosts_applied = boosts

    return {
        "available": True,
        "boosts": boosts_applied,
        "boosts_raw": boosts,  # Pre-shadow-mode values for logging
        "signals_triggered": len(signals),
        "signals": signals,
        "target_team": target_team,
        "metadata": {
            "sport": sport,
            "home_team": home_team,
            "away_team": away_team,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }


def get_serp_prop_intelligence(
    sport: str,
    player_name: str,
    home_team: str,
    away_team: str,
    market: str = None,
    prop_line: float = None
) -> Dict[str, Any]:
    """
    Get SERP intelligence for player prop bets.

    Focuses on player buzz, public sentiment, and contrarian opportunities.

    Args:
        sport: Sport code
        player_name: Player name
        home_team: Home team name
        away_team: Away team name
        market: Prop market type (player_points, player_assists, etc.)
        prop_line: Prop line value

    Returns:
        Dict with boosts by engine, signals, metadata
    """
    if not is_serp_available() if GUARDRAILS_AVAILABLE else not SERPAPI_AVAILABLE:
        return _empty_intelligence("serp_unavailable")

    signals = []
    boosts = {
        "ai": 0.0,
        "research": 0.0,
        "esoteric": 0.0,
        "jarvis": 0.0,
        "context": 0.0,
    }

    try:
        # Player buzz for contrarian signal
        player_buzz = get_player_buzz(player_name)

        if player_buzz.get("contrarian_signal"):
            # High buzz = potential fade opportunity
            boosts["research"] += cap_boost("research", 0.5) if GUARDRAILS_AVAILABLE else 0.5
            signals.append({
                "signal": "player_contrarian",
                "engine": "research",
                "triggered": True,
                "boost": 0.5,
                "reason": player_buzz.get("contrarian_reason", "High player buzz"),
                "confidence": 70,
            })

        # Noosphere with player focus
        noosphere = detect_noosphere(home_team, away_team, player_name=player_name)
        if noosphere["triggered"]:
            boosts["esoteric"] += noosphere["boost"]
            signals.append(noosphere)

        # Silent spike on player
        player_trend = get_search_trend(f"{player_name} props today")
        if player_trend.get("trend_score", 0) >= 0.7 and player_trend.get("news_count", 0) <= 2:
            boost = cap_boost("ai", 0.5) if GUARDRAILS_AVAILABLE else 0.5
            boosts["ai"] += boost
            signals.append({
                "signal": "player_silent_spike",
                "engine": "ai",
                "triggered": True,
                "boost": boost,
                "reason": f"Player prop spike: {player_trend.get('trend_score', 0):.0%}",
                "confidence": 65,
            })

    except Exception as e:
        logger.error("SERP prop intelligence failed: %s", e)
        return _empty_intelligence(f"error: {e}")

    # Apply caps and shadow mode
    if GUARDRAILS_AVAILABLE:
        boosts = cap_total_boost(boosts)
        boosts_applied = apply_shadow_mode(boosts)
    else:
        boosts_applied = boosts

    return {
        "available": True,
        "boosts": boosts_applied,
        "boosts_raw": boosts,
        "signals_triggered": len(signals),
        "signals": signals,
        "player_name": player_name,
        "metadata": {
            "sport": sport,
            "player_name": player_name,
            "home_team": home_team,
            "away_team": away_team,
            "market": market,
            "prop_line": prop_line,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _empty_signal(reason: str) -> Dict[str, Any]:
    """Return empty signal structure."""
    return {
        "signal": None,
        "engine": None,
        "triggered": False,
        "boost": 0.0,
        "confidence": 0,
        "reason": reason,
    }


def _empty_intelligence(reason: str) -> Dict[str, Any]:
    """Return empty intelligence structure."""
    return {
        "available": False,
        "boosts": {
            "ai": 0.0,
            "research": 0.0,
            "esoteric": 0.0,
            "jarvis": 0.0,
            "context": 0.0,
        },
        "boosts_raw": None,
        "signals_triggered": 0,
        "signals": [],
        "reason": reason,
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Signal detectors
    "detect_silent_spike",
    "detect_sharp_chatter",
    "detect_narrative",
    "detect_situational",
    "detect_noosphere",
    # Main intelligence functions
    "get_serp_betting_intelligence",
    "get_serp_prop_intelligence",
    # Query templates
    "SPORT_QUERIES",
]
