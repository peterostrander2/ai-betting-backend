"""
Glitch Protocol: Hive Mind Module v1.0
======================================
Collective consciousness and sentiment signals for edge detection.

Features:
- Noosphere Velocity (collective sentiment momentum)
- Void Moon Filter (lunar timing)
- Linguistic Divergence / Hate-Buy Trap (contrarian sentiment)
- Crowd Wisdom Indicator (public vs sharp divergence)

Master Audit File: hive_mind.py - HIGH PRIORITY
"""

import math
import random
import hashlib
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

# =============================================================================
# NOOSPHERE VELOCITY - Collective Sentiment Momentum
# =============================================================================

def calculate_noosphere_velocity(
    sentiment_readings: List[float] = None,
    target_date: date = None
) -> Dict[str, Any]:
    """
    Calculate Noosphere Velocity - the momentum of collective consciousness.

    Based on Teilhard de Chardin's noosphere concept.
    Measures the "velocity" of collective human thought/sentiment.

    Args:
        sentiment_readings: List of sentiment scores (-1 to 1) over recent period
        target_date: Date for deterministic simulation if no readings

    Returns:
        Dict with velocity, direction, and betting signal
    """
    if target_date is None:
        target_date = date.today()

    if sentiment_readings and len(sentiment_readings) >= 3:
        # Calculate actual velocity from readings
        velocities = [
            sentiment_readings[i] - sentiment_readings[i-1]
            for i in range(1, len(sentiment_readings))
        ]
        velocity = sum(velocities) / len(velocities)
        acceleration = velocities[-1] - velocities[0] if len(velocities) > 1 else 0
    else:
        # Deterministic simulation based on date
        seed = int(target_date.strftime("%Y%m%d")) + 777
        random.seed(seed)
        velocity = (random.random() - 0.5) * 0.4  # -0.2 to 0.2
        acceleration = (random.random() - 0.5) * 0.1
        random.seed()

    # Determine direction and signal
    if velocity > 0.1:
        direction = "ASCENDING"
        if acceleration > 0:
            signal = "STRONG_BULL"
            boost = 0.25
        else:
            signal = "WEAKENING_BULL"
            boost = 0.10
    elif velocity < -0.1:
        direction = "DESCENDING"
        if acceleration < 0:
            signal = "STRONG_BEAR"
            boost = -0.20
        else:
            signal = "WEAKENING_BEAR"
            boost = -0.05
    else:
        direction = "STABLE"
        signal = "NEUTRAL"
        boost = 0.0

    return {
        "available": True,
        "module": "hive_mind",
        "signal_type": "NOOSPHERE_VELOCITY",
        "velocity": round(velocity, 4),
        "acceleration": round(acceleration, 4),
        "direction": direction,
        "signal": signal,
        "boost": boost,
        "betting_impact": f"Collective momentum {direction.lower()} - {signal.replace('_', ' ').lower()}"
    }


# =============================================================================
# VOID MOON FILTER - Lunar Timing
# =============================================================================

MOON_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

VOID_MOON_BETTING_RULES = {
    "VOID_ACTIVE": {
        "signal": "AVOID_MAJOR",
        "boost": -0.30,
        "recommendation": "Avoid placing major bets during void moon"
    },
    "VOID_ENDING_SOON": {
        "signal": "CAUTION",
        "boost": -0.15,
        "recommendation": "Void moon ending soon - wait if possible"
    },
    "VOID_CLEAR": {
        "signal": "CLEAR",
        "boost": 0.0,
        "recommendation": "Moon not void - normal betting conditions"
    }
}


def calculate_void_moon(target_datetime: datetime = None) -> Dict[str, Any]:
    """
    Calculate void-of-course moon status.

    Moon is void when it makes no major aspects before leaving its sign.
    Traditional wisdom: Avoid starting new ventures during void moon.

    For betting: Picks made during void moon have higher uncertainty.
    """
    if target_datetime is None:
        target_datetime = datetime.now()

    # Deterministic calculation based on datetime
    # Real implementation would use astronomical ephemeris
    day_of_year = target_datetime.timetuple().tm_yday
    hour = target_datetime.hour

    # Moon changes sign roughly every 2.5 days
    moon_sign_index = (day_of_year * 24 + hour) // 60 % 12
    moon_sign = MOON_SIGNS[moon_sign_index]

    # Void moon typically lasts 2-48 hours before sign change
    # Simulate based on hour within "sign period"
    hours_in_sign = (day_of_year * 24 + hour) % 60
    is_void = hours_in_sign > 55  # Last ~5 hours before sign change

    hours_until_sign_change = 60 - hours_in_sign
    next_sign = MOON_SIGNS[(moon_sign_index + 1) % 12]

    # Determine void status
    if is_void:
        if hours_until_sign_change < 2:
            status = "VOID_ENDING_SOON"
        else:
            status = "VOID_ACTIVE"
    else:
        status = "VOID_CLEAR"

    rules = VOID_MOON_BETTING_RULES[status]

    return {
        "available": True,
        "module": "hive_mind",
        "signal_type": "VOID_MOON",
        "is_void": is_void,
        "moon_sign": moon_sign,
        "hours_until_sign_change": round(hours_until_sign_change, 1),
        "next_sign": next_sign,
        "status": status,
        "signal": rules["signal"],
        "boost": rules["boost"],
        "recommendation": rules["recommendation"]
    }


def get_moon_betting_signal(target_datetime: datetime = None) -> Dict[str, Any]:
    """
    Get comprehensive moon-based betting signal.

    Combines void moon status with moon sign characteristics.
    """
    void_data = calculate_void_moon(target_datetime)

    # Moon sign characteristics for betting
    SIGN_CHARACTERISTICS = {
        "Aries": {"element": "fire", "volatility": "high", "favors": "overs"},
        "Taurus": {"element": "earth", "volatility": "low", "favors": "unders"},
        "Gemini": {"element": "air", "volatility": "medium", "favors": "props"},
        "Cancer": {"element": "water", "volatility": "medium", "favors": "home"},
        "Leo": {"element": "fire", "volatility": "high", "favors": "favorites"},
        "Virgo": {"element": "earth", "volatility": "low", "favors": "unders"},
        "Libra": {"element": "air", "volatility": "low", "favors": "pushes"},
        "Scorpio": {"element": "water", "volatility": "high", "favors": "dogs"},
        "Sagittarius": {"element": "fire", "volatility": "high", "favors": "overs"},
        "Capricorn": {"element": "earth", "volatility": "low", "favors": "favorites"},
        "Aquarius": {"element": "air", "volatility": "medium", "favors": "dogs"},
        "Pisces": {"element": "water", "volatility": "medium", "favors": "totals"}
    }

    sign_info = SIGN_CHARACTERISTICS.get(
        void_data["moon_sign"],
        {"element": "unknown", "volatility": "medium", "favors": "neutral"}
    )

    return {
        **void_data,
        "sign_element": sign_info["element"],
        "expected_volatility": sign_info["volatility"],
        "sign_favors": sign_info["favors"]
    }


# =============================================================================
# LINGUISTIC DIVERGENCE / HATE-BUY TRAP
# =============================================================================

def detect_hate_buy_trap(
    sentiment_score: float,
    rlm_detected: bool,
    rlm_direction: str,
    sentiment_target: str
) -> Dict[str, Any]:
    """
    Detect "Hate-Buy" trap where sharps buy hated teams.

    If public hates a team (negative sentiment) BUT line moves toward them (RLM),
    sharps are loading up. Classic contrarian edge.

    Args:
        sentiment_score: -1 to 1 scale (negative = public hates)
        rlm_detected: Whether reverse line movement was detected
        rlm_direction: "HOME" or "AWAY"
        sentiment_target: Which team the sentiment is about

    Returns:
        Dict with trap detection and boost
    """
    if not rlm_detected:
        return {
            "available": True,
            "module": "hive_mind",
            "signal_type": "HATE_BUY_TRAP",
            "is_trap": False,
            "boost": 0.0,
            "reason": "No RLM detected - no hate-buy pattern"
        }

    # Negative sentiment (-0.3 or worse) indicates public hates the team
    is_negative = sentiment_score < -0.3

    # Check if RLM is toward the hated team
    rlm_matches_hated = (
        (sentiment_target == "HOME" and rlm_direction == "HOME") or
        (sentiment_target == "AWAY" and rlm_direction == "AWAY")
    )

    is_trap = is_negative and rlm_matches_hated

    if is_trap:
        # Stronger hate = stronger signal
        hate_intensity = abs(sentiment_score)
        boost = 0.25 + (hate_intensity * 0.2)  # 0.25 to 0.45

        return {
            "available": True,
            "module": "hive_mind",
            "signal_type": "HATE_BUY_TRAP",
            "is_trap": True,
            "sentiment_score": sentiment_score,
            "rlm_direction": rlm_direction,
            "hate_intensity": round(hate_intensity, 2),
            "boost": round(boost, 3),
            "signal": "HATE_BUY",
            "reason": f"Hate-Buy Trap: Public hates {sentiment_target} (sentiment {sentiment_score:.2f}) but sharps buying (RLM {rlm_direction})"
        }

    return {
        "available": True,
        "module": "hive_mind",
        "signal_type": "HATE_BUY_TRAP",
        "is_trap": False,
        "sentiment_score": sentiment_score,
        "rlm_direction": rlm_direction,
        "boost": 0.0,
        "signal": "NO_TRAP",
        "reason": "No hate-buy pattern detected"
    }


def calculate_linguistic_divergence(
    public_narrative: str,
    sharp_action: str
) -> Dict[str, Any]:
    """
    Calculate linguistic divergence between public narrative and sharp action.

    When public is bearish (negative words) but sharps are bullish,
    there's a divergence that creates edge.
    """
    # Simple sentiment analysis
    negative_words = ["bad", "terrible", "awful", "struggling", "injured", "cold", "slump"]
    positive_words = ["hot", "great", "amazing", "streak", "dominant", "healthy", "rolling"]

    public_lower = public_narrative.lower()
    public_negative = sum(1 for word in negative_words if word in public_lower)
    public_positive = sum(1 for word in positive_words if word in public_lower)

    public_sentiment = (public_positive - public_negative) / max(1, public_positive + public_negative)

    # Sharp action interpretation
    sharp_bullish = sharp_action.upper() in ["BUY", "BULLISH", "BACK", "FADE_PUBLIC"]

    # Divergence when public negative but sharps bullish
    divergence = public_sentiment < -0.3 and sharp_bullish

    if divergence:
        return {
            "available": True,
            "module": "hive_mind",
            "signal_type": "LINGUISTIC_DIVERGENCE",
            "public_sentiment": round(public_sentiment, 2),
            "sharp_action": sharp_action,
            "divergence_detected": True,
            "boost": 0.30,
            "signal": "CONTRARIAN_EDGE",
            "reason": "Linguistic divergence: Public bearish but sharps bullish"
        }

    return {
        "available": True,
        "module": "hive_mind",
        "signal_type": "LINGUISTIC_DIVERGENCE",
        "public_sentiment": round(public_sentiment, 2),
        "sharp_action": sharp_action,
        "divergence_detected": False,
        "boost": 0.0,
        "signal": "ALIGNED",
        "reason": "Public and sharp sentiment aligned"
    }


# =============================================================================
# CROWD WISDOM INDICATOR
# =============================================================================

def calculate_crowd_wisdom(
    public_pct: float,
    money_pct: float,
    threshold: float = 10.0
) -> Dict[str, Any]:
    """
    Calculate crowd wisdom indicator based on public vs money split.

    When money% significantly diverges from ticket%, sharps are involved.

    Args:
        public_pct: Percentage of tickets on one side (0-100)
        money_pct: Percentage of money on same side (0-100)
        threshold: Minimum divergence to trigger signal (default 10%)
    """
    divergence = money_pct - public_pct

    if abs(divergence) < threshold:
        return {
            "available": True,
            "module": "hive_mind",
            "signal_type": "CROWD_WISDOM",
            "public_pct": public_pct,
            "money_pct": money_pct,
            "divergence": round(divergence, 1),
            "signal": "ALIGNED",
            "boost": 0.0,
            "reason": f"Public and money aligned (divergence {divergence:.1f}%)"
        }

    if divergence > 0:
        # More money than tickets = sharp action
        signal = "SHARP_SIDE"
        boost = min(0.40, divergence / 50)  # Max 0.40 at 20%+ divergence
        reason = f"Sharp money detected: {money_pct:.0f}% money vs {public_pct:.0f}% tickets"
    else:
        # Less money than tickets = fade public
        signal = "FADE_PUBLIC"
        boost = min(0.30, abs(divergence) / 50)
        reason = f"Fade public: {public_pct:.0f}% tickets but only {money_pct:.0f}% money"

    return {
        "available": True,
        "module": "hive_mind",
        "signal_type": "CROWD_WISDOM",
        "public_pct": public_pct,
        "money_pct": money_pct,
        "divergence": round(divergence, 1),
        "signal": signal,
        "boost": round(boost, 3),
        "reason": reason
    }


# =============================================================================
# AGGREGATED HIVE MIND SCORE
# =============================================================================

def get_hive_mind_signals(
    sentiment_readings: List[float] = None,
    public_pct: float = None,
    money_pct: float = None,
    sentiment_score: float = None,
    rlm_detected: bool = False,
    rlm_direction: str = None,
    sentiment_target: str = None
) -> Dict[str, Any]:
    """
    Aggregate all hive mind signals for a matchup.

    Returns individual signals plus combined hive mind score.
    """
    signals = {}
    total_boost = 0.0
    fired_modules = []

    # Noosphere Velocity
    noosphere = calculate_noosphere_velocity(sentiment_readings)
    signals["noosphere"] = noosphere
    if noosphere["boost"] != 0:
        total_boost += noosphere["boost"]
        fired_modules.append("NOOSPHERE")

    # Void Moon
    void_moon = get_moon_betting_signal()
    signals["void_moon"] = void_moon
    if void_moon["boost"] != 0:
        total_boost += void_moon["boost"]
        fired_modules.append("VOID_MOON")

    # Hate-Buy Trap (if sentiment and RLM data provided)
    if sentiment_score is not None and rlm_direction:
        hate_buy = detect_hate_buy_trap(
            sentiment_score,
            rlm_detected,
            rlm_direction,
            sentiment_target or "HOME"
        )
        signals["hate_buy"] = hate_buy
        if hate_buy["boost"] != 0:
            total_boost += hate_buy["boost"]
            fired_modules.append("HATE_BUY")

    # Crowd Wisdom (if splits data provided)
    if public_pct is not None and money_pct is not None:
        crowd = calculate_crowd_wisdom(public_pct, money_pct)
        signals["crowd_wisdom"] = crowd
        if crowd["boost"] != 0:
            total_boost += crowd["boost"]
            fired_modules.append("CROWD_WISDOM")

    return {
        "available": True,
        "module": "hive_mind",
        "signals": signals,
        "total_boost": round(total_boost, 3),
        "fired_modules": fired_modules,
        "modules_fired_count": len(fired_modules)
    }
