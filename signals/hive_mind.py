"""
HIVE MIND SIGNALS MODULE - Collective consciousness and sentiment signals

This module provides hive mind / collective sentiment signals for the esoteric engine.
Each function returns a score + explicit reason string.

SIGNALS:
1. Noosphere Velocity - Collective consciousness momentum
2. Void Moon - Void-of-course moon periods (avoid new ventures)
3. Linguistic Divergence - Sentiment divergence across sources

ALL SIGNALS MUST RETURN:
- score: float (0-1 normalized)
- reason: str (explicit explanation or "NO_SIGNAL" reason)
- triggered: bool
"""

import os
import math
import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("hive_mind")

# Feature flags
HIVE_MIND_ENABLED = os.getenv("HIVE_MIND_ENABLED", "true").lower() == "true"


# =============================================================================
# NOOSPHERE VELOCITY
# =============================================================================

def get_noosphere_velocity(
    teams: List[str] = None,
    game_date: datetime = None,
    twitter_sentiment: float = None,
    news_sentiment: float = None,
    public_betting_pct: float = None
) -> Dict[str, Any]:
    """
    Calculate noosphere velocity - collective consciousness momentum.

    The noosphere represents the sphere of human thought. Velocity measures
    the rate of change in collective sentiment toward a team/game.

    Args:
        teams: List of team names
        game_date: Game date
        twitter_sentiment: Twitter sentiment score (-1 to 1)
        news_sentiment: News sentiment score (-1 to 1)
        public_betting_pct: Public betting percentage

    Returns:
        Dict with score, reason, triggered, velocity, direction
    """
    if not HIVE_MIND_ENABLED:
        return {
            "score": 0.5,
            "reason": "HIVE_MIND_DISABLED",
            "triggered": False,
            "velocity": None,
            "direction": None
        }

    if game_date is None:
        game_date = datetime.now()

    try:
        # Collect available signals
        signals = []

        if twitter_sentiment is not None:
            signals.append(("twitter", twitter_sentiment))

        if news_sentiment is not None:
            signals.append(("news", news_sentiment))

        if public_betting_pct is not None:
            # Normalize to -1 to 1 scale
            normalized_public = (public_betting_pct - 50) / 50
            signals.append(("public", normalized_public))

        # If no real data, use deterministic simulation based on inputs
        if not signals and teams:
            # Generate deterministic "velocity" from team names + date
            seed_str = f"{'-'.join(teams)}|{game_date.strftime('%Y-%m-%d')}"
            hash_val = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)
            simulated = ((hash_val % 200) - 100) / 100  # -1 to 1
            signals.append(("simulated", simulated))

        if not signals:
            return {
                "score": 0.5,
                "reason": "NO_SENTIMENT_DATA",
                "triggered": False,
                "velocity": 0,
                "direction": "NEUTRAL"
            }

        # Calculate aggregate velocity
        total_weight = len(signals)
        velocity = sum(s[1] for s in signals) / total_weight

        # Determine direction and score
        if velocity > 0.3:
            direction = "STRONG_POSITIVE"
            score = 0.8
            reason = f"NOOSPHERE_BULLISH_{abs(velocity):.2f}"
            triggered = True
        elif velocity > 0.1:
            direction = "POSITIVE"
            score = 0.65
            reason = f"NOOSPHERE_SLIGHTLY_BULLISH_{abs(velocity):.2f}"
            triggered = True
        elif velocity < -0.3:
            direction = "STRONG_NEGATIVE"
            score = 0.8  # Contrarian opportunity
            reason = f"NOOSPHERE_BEARISH_CONTRARIAN_{abs(velocity):.2f}"
            triggered = True
        elif velocity < -0.1:
            direction = "NEGATIVE"
            score = 0.6
            reason = f"NOOSPHERE_SLIGHTLY_BEARISH_{abs(velocity):.2f}"
            triggered = False
        else:
            direction = "NEUTRAL"
            score = 0.5
            reason = "NOOSPHERE_NEUTRAL"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "velocity": round(velocity, 3),
            "direction": direction,
            "signals_used": [s[0] for s in signals]
        }

    except Exception as e:
        logger.warning("Noosphere calculation error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "velocity": None,
            "direction": None
        }


# =============================================================================
# VOID MOON (Void-of-Course Moon)
# =============================================================================

def get_void_moon(game_time: datetime = None) -> Dict[str, Any]:
    """
    Check if game occurs during void-of-course moon period.

    Void-of-course moon occurs when the Moon makes no major aspects
    before leaving its current sign. Traditional astrology advises
    against starting new ventures during this time.

    Args:
        game_time: Game start time

    Returns:
        Dict with score, reason, triggered, is_void, void_duration
    """
    if not HIVE_MIND_ENABLED:
        return {
            "score": 0.5,
            "reason": "HIVE_MIND_DISABLED",
            "triggered": False,
            "is_void": None,
            "void_duration": None
        }

    if game_time is None:
        game_time = datetime.now()

    try:
        # TODO: Integrate with Astronomy API for real void moon data
        # For now, use simplified calculation based on lunar cycle

        # Moon changes signs approximately every 2.5 days
        # Void period typically lasts 2-24 hours before sign change

        # Approximate lunar position (0-360 degrees)
        # Full cycle ~27.3 days
        days_since_epoch = (game_time - datetime(2000, 1, 1)).days
        lunar_position = (days_since_epoch * (360 / 27.3)) % 360

        # Signs are 30 degrees each
        position_in_sign = lunar_position % 30

        # Void period: last 2 degrees of each sign (simplified)
        is_void = position_in_sign >= 28

        # Extended void check: also check hour of day
        # Void periods often occur in late evening / early morning
        hour = game_time.hour
        extended_void = is_void or (hour >= 23 or hour <= 4)

        if is_void:
            void_duration = (30 - position_in_sign) * 2  # Approx hours
            score = 0.3  # Avoid betting during void
            reason = f"VOID_MOON_ACTIVE_{void_duration:.1f}hrs_remaining"
            triggered = True
        elif extended_void:
            score = 0.4
            reason = "VOID_MOON_APPROACHING"
            triggered = True
            void_duration = None
        else:
            score = 0.7
            reason = "MOON_ACTIVE"
            triggered = False
            void_duration = None

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "is_void": is_void,
            "void_duration": void_duration,
            "lunar_position": round(lunar_position, 1),
            "note": "SIMULATED - integrate Astronomy API for precision"
        }

    except Exception as e:
        logger.warning("Void moon calculation error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "is_void": None,
            "void_duration": None
        }


# =============================================================================
# LINGUISTIC DIVERGENCE
# =============================================================================

def analyze_linguistic_divergence(
    twitter_text: List[str] = None,
    news_headlines: List[str] = None,
    expert_picks: List[str] = None
) -> Dict[str, Any]:
    """
    Analyze linguistic divergence between different information sources.

    High divergence = uncertainty = potential value in market
    Low divergence = consensus = likely priced in

    Args:
        twitter_text: Sample of relevant tweets
        news_headlines: Recent news headlines
        expert_picks: Expert pick text/reasoning

    Returns:
        Dict with score, reason, triggered, divergence_score, analysis
    """
    if not HIVE_MIND_ENABLED:
        return {
            "score": 0.5,
            "reason": "HIVE_MIND_DISABLED",
            "triggered": False,
            "divergence_score": None,
            "analysis": None
        }

    sources = []

    if twitter_text:
        sources.append(("twitter", twitter_text))
    if news_headlines:
        sources.append(("news", news_headlines))
    if expert_picks:
        sources.append(("experts", expert_picks))

    if len(sources) < 2:
        return {
            "score": 0.5,
            "reason": "INSUFFICIENT_SOURCES",
            "triggered": False,
            "divergence_score": None,
            "analysis": "Need at least 2 sources for divergence analysis"
        }

    try:
        # Simplified sentiment analysis using keyword matching
        positive_words = {"win", "beat", "strong", "confident", "lock", "hammer", "smash", "fire"}
        negative_words = {"lose", "weak", "fade", "avoid", "skip", "pass", "risky", "trap"}

        def analyze_sentiment(texts: List[str]) -> float:
            """Calculate simple sentiment score from texts."""
            if not texts:
                return 0

            pos_count = 0
            neg_count = 0

            for text in texts:
                words = text.lower().split()
                pos_count += sum(1 for w in words if w in positive_words)
                neg_count += sum(1 for w in words if w in negative_words)

            total = pos_count + neg_count
            if total == 0:
                return 0

            return (pos_count - neg_count) / total

        # Calculate sentiment for each source
        sentiments = {}
        for source_name, texts in sources:
            sentiments[source_name] = analyze_sentiment(texts)

        # Calculate divergence (variance of sentiments)
        mean_sentiment = sum(sentiments.values()) / len(sentiments)
        variance = sum((s - mean_sentiment) ** 2 for s in sentiments.values()) / len(sentiments)
        divergence = math.sqrt(variance)

        # Interpret divergence
        if divergence > 0.5:
            score = 0.8
            reason = "HIGH_LINGUISTIC_DIVERGENCE"
            analysis = "Strong disagreement - potential value"
            triggered = True
        elif divergence > 0.25:
            score = 0.65
            reason = "MODERATE_LINGUISTIC_DIVERGENCE"
            analysis = "Some disagreement - worth investigating"
            triggered = True
        else:
            score = 0.4
            reason = "LOW_LINGUISTIC_DIVERGENCE"
            analysis = "Consensus - likely priced in"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "divergence_score": round(divergence, 3),
            "analysis": analysis,
            "source_sentiments": {k: round(v, 3) for k, v in sentiments.items()}
        }

    except Exception as e:
        logger.warning("Linguistic divergence error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "divergence_score": None,
            "analysis": None
        }


# =============================================================================
# FOUNDER'S ECHO (Gematria Resonance)
# =============================================================================

def get_founders_echo(
    team_name: str,
    founding_year: int = None,
    game_date: datetime = None
) -> Dict[str, Any]:
    """
    Calculate founder's echo - gematria resonance with founding year.

    When team's founding year digits align with current date or
    game metrics, it may indicate favorable energy.

    Args:
        team_name: Team name
        founding_year: Year team was founded
        game_date: Game date

    Returns:
        Dict with score, reason, triggered, resonance_type
    """
    if not HIVE_MIND_ENABLED:
        return {
            "score": 0.5,
            "reason": "HIVE_MIND_DISABLED",
            "triggered": False,
            "resonance_type": None
        }

    # Known founding years (partial list)
    FOUNDING_YEARS = {
        "lakers": 1947,
        "celtics": 1946,
        "warriors": 1946,
        "knicks": 1946,
        "bulls": 1966,
        "heat": 1988,
        "spurs": 1967,
        "mavericks": 1980,
        "nuggets": 1967,
        "suns": 1968,
        "cowboys": 1960,
        "patriots": 1960,
        "packers": 1919,
        "bears": 1920,
        "steelers": 1933,
        "49ers": 1946,
        "chiefs": 1960,
        "eagles": 1933,
        "yankees": 1901,
        "dodgers": 1883,
        "red sox": 1901,
        "cubs": 1876,
    }

    if game_date is None:
        game_date = datetime.now()

    # Get founding year
    if founding_year is None:
        team_lower = team_name.lower()
        for key, year in FOUNDING_YEARS.items():
            if key in team_lower:
                founding_year = year
                break

    if founding_year is None:
        return {
            "score": 0.5,
            "reason": "UNKNOWN_FOUNDING_YEAR",
            "triggered": False,
            "resonance_type": None
        }

    try:
        # Calculate various resonances
        year_digits = sum(int(d) for d in str(founding_year))
        date_digits = sum(int(d) for d in game_date.strftime("%Y%m%d") if d.isdigit())
        day_of_year = game_date.timetuple().tm_yday

        resonances = []

        # Check if founding year digits match date digits (mod 9)
        if year_digits % 9 == date_digits % 9:
            resonances.append("NUMEROLOGY_MATCH")

        # Check anniversary alignment
        years_since = game_date.year - founding_year
        if years_since % 10 == 0 or years_since % 25 == 0:
            resonances.append("ANNIVERSARY_YEAR")

        # Check day alignment
        if day_of_year == founding_year % 365:
            resonances.append("DAY_ALIGNMENT")

        # Check master number in founding year
        if year_digits in [11, 22, 33]:
            resonances.append("MASTER_NUMBER_ORIGIN")

        if len(resonances) >= 2:
            score = 0.9
            reason = f"STRONG_FOUNDERS_ECHO_{'+'.join(resonances)}"
            triggered = True
        elif len(resonances) == 1:
            score = 0.7
            reason = f"FOUNDERS_ECHO_{resonances[0]}"
            triggered = True
        else:
            score = 0.5
            reason = "NO_FOUNDERS_RESONANCE"
            triggered = False

        return {
            "score": score,
            "reason": reason,
            "triggered": triggered,
            "resonance_type": resonances if resonances else None,
            "founding_year": founding_year,
            "year_digits": year_digits
        }

    except Exception as e:
        logger.warning("Founder's echo error: %s", e)
        return {
            "score": 0.5,
            "reason": f"CALCULATION_ERROR: {str(e)}",
            "triggered": False,
            "resonance_type": None
        }


# =============================================================================
# AGGREGATE HIVE MIND SCORE
# =============================================================================

def get_hive_mind_score(
    teams: List[str] = None,
    game_time: datetime = None,
    twitter_sentiment: float = None,
    news_sentiment: float = None,
    public_betting_pct: float = None
) -> Dict[str, Any]:
    """
    Calculate aggregate hive mind score from all signals.

    Returns:
        Dict with overall score, all signal breakdowns, and reasons
    """
    results = {
        "noosphere": get_noosphere_velocity(
            teams=teams,
            game_date=game_time,
            twitter_sentiment=twitter_sentiment,
            news_sentiment=news_sentiment,
            public_betting_pct=public_betting_pct
        ),
        "void_moon": get_void_moon(game_time),
        "founders_echo": get_founders_echo(
            team_name=teams[0] if teams else "",
            game_date=game_time
        ),
    }

    # Weights for each signal
    weights = {
        "noosphere": 0.40,
        "void_moon": 0.30,
        "founders_echo": 0.30,
    }

    # Calculate weighted score
    total_score = sum(
        results[key]["score"] * weights[key]
        for key in weights
    )

    # Collect triggered signals
    triggered_signals = [
        key for key, result in results.items()
        if result.get("triggered", False)
    ]

    # Collect reasons
    reasons = [
        f"{key.upper()}: {results[key]['reason']}"
        for key in results
    ]

    return {
        "hive_mind_score": round(total_score, 3),
        "triggered_count": len(triggered_signals),
        "triggered_signals": triggered_signals,
        "reasons": reasons,
        "breakdown": results,
        "enabled": HIVE_MIND_ENABLED
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "get_noosphere_velocity",
    "get_void_moon",
    "analyze_linguistic_divergence",
    "get_founders_echo",
    "get_hive_mind_score",
    "HIVE_MIND_ENABLED",
]
