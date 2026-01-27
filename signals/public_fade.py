"""
PUBLIC_FADE.PY - Centralized Public Fade Signal Calculation
============================================================
v14.11 - Single-calculation policy to prevent double-counting

This module calculates the public fade signal ONCE and returns:
1. The canonical boost value (for Research Engine ONLY)
2. A context flag (for Jarvis/Esoteric to reference, NOT apply numerically)

The public fade signal indicates when heavy public betting action
creates a contrarian opportunity (fading the public).

Usage:
    from signals.public_fade import calculate_public_fade, PublicFadeSignal

    signal = calculate_public_fade(
        public_pct=75.0,
        ticket_pct=72.0,
        money_pct=45.0
    )

    # Research Engine: Apply the boost
    research_score += signal.research_boost

    # Esoteric/Jarvis: Only use as context flag
    if signal.is_fade_opportunity:
        esoteric_reasons.append("Public overload detected (context only)")
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PublicFadeSignal:
    """
    Canonical public fade signal result.

    Attributes:
        public_pct: Raw public betting percentage
        ticket_pct: Ticket percentage (if available)
        money_pct: Money percentage (if available)
        direction: 'FADE' or 'FOLLOW' or 'NEUTRAL'
        strength: Signal strength (0.0 to 1.0)
        research_boost: Numeric boost for Research Engine ONLY (0.0 to 2.0)
        is_fade_opportunity: Boolean flag for other engines (context only)
        is_strong_fade: Strong fade signal (public >= 75%)
        is_extreme_fade: Extreme fade signal (public >= 80%)
        reason: Human-readable description
    """
    public_pct: float
    ticket_pct: Optional[float] = None
    money_pct: Optional[float] = None
    direction: str = "NEUTRAL"
    strength: float = 0.0
    research_boost: float = 0.0
    is_fade_opportunity: bool = False
    is_strong_fade: bool = False
    is_extreme_fade: bool = False
    reason: str = ""

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "public_pct": self.public_pct,
            "ticket_pct": self.ticket_pct,
            "money_pct": self.money_pct,
            "direction": self.direction,
            "strength": self.strength,
            "research_boost": self.research_boost,
            "is_fade_opportunity": self.is_fade_opportunity,
            "is_strong_fade": self.is_strong_fade,
            "is_extreme_fade": self.is_extreme_fade,
            "reason": self.reason,
        }


def calculate_public_fade(
    public_pct: float,
    ticket_pct: Optional[float] = None,
    money_pct: Optional[float] = None
) -> PublicFadeSignal:
    """
    Calculate the canonical public fade signal.

    This function is the SINGLE SOURCE OF TRUTH for public fade calculations.
    The returned research_boost should ONLY be applied in the Research Engine.
    Other engines (Esoteric, Jarvis) may reference is_fade_opportunity but
    MUST NOT apply any additional numeric modifiers.

    Thresholds (v14.11 spec):
    - >= 80% public: Extreme fade (2.0 boost)
    - >= 75% public: Strong fade (2.0 boost)
    - >= 70% public: Moderate fade (1.5 boost)
    - >= 65% public: Mild fade (1.0 boost)
    - < 65% public: No fade signal

    Smart money divergence (ticket vs money):
    - If ticket_pct > 60% but money_pct < 45%: Sharp money fade boost +0.5

    Args:
        public_pct: Public betting percentage (0-100)
        ticket_pct: Ticket percentage if available
        money_pct: Money percentage if available

    Returns:
        PublicFadeSignal with canonical values
    """
    # Normalize public_pct
    public_pct = max(0, min(100, float(public_pct)))

    # Initialize signal
    signal = PublicFadeSignal(
        public_pct=public_pct,
        ticket_pct=ticket_pct,
        money_pct=money_pct,
    )

    # Determine fade opportunity based on public percentage
    if public_pct >= 80:
        # EXTREME FADE - Heavy public, maximum contrarian value
        signal.direction = "FADE"
        signal.strength = 1.0
        signal.research_boost = 2.0
        signal.is_fade_opportunity = True
        signal.is_strong_fade = True
        signal.is_extreme_fade = True
        signal.reason = f"Extreme public at {public_pct:.0f}% (fade signal)"

    elif public_pct >= 75:
        # STRONG FADE
        signal.direction = "FADE"
        signal.strength = 0.9
        signal.research_boost = 2.0
        signal.is_fade_opportunity = True
        signal.is_strong_fade = True
        signal.reason = f"Public at {public_pct:.0f}% (strong fade signal)"

    elif public_pct >= 70:
        # MODERATE FADE
        signal.direction = "FADE"
        signal.strength = 0.7
        signal.research_boost = 1.5
        signal.is_fade_opportunity = True
        signal.reason = f"Public at {public_pct:.0f}% (moderate fade)"

    elif public_pct >= 65:
        # MILD FADE
        signal.direction = "FADE"
        signal.strength = 0.5
        signal.research_boost = 1.0
        signal.is_fade_opportunity = True
        signal.reason = f"Public at {public_pct:.0f}% (mild fade)"

    else:
        # NO FADE SIGNAL
        signal.direction = "NEUTRAL"
        signal.strength = 0.0
        signal.research_boost = 0.0
        signal.is_fade_opportunity = False
        signal.reason = ""

    # Smart money divergence bonus
    # If tickets are heavy but money is lighter, sharps are fading
    if ticket_pct is not None and money_pct is not None:
        divergence = abs(ticket_pct - money_pct)
        if ticket_pct > 60 and money_pct < 45 and divergence >= 20:
            # Strong sharp money divergence
            signal.research_boost = min(2.5, signal.research_boost + 0.5)
            signal.strength = min(1.0, signal.strength + 0.2)
            signal.is_fade_opportunity = True
            if signal.reason:
                signal.reason += f" + Sharp divergence ({divergence:.0f}%)"
            else:
                signal.reason = f"Sharp money divergence (tickets {ticket_pct:.0f}%, money {money_pct:.0f}%)"
        elif divergence >= 5 and not signal.is_fade_opportunity:
            # v15.2: Mild ticket-money divergence — sharps may be positioning
            signal.research_boost = min(2.0, signal.research_boost + 0.5)
            signal.is_fade_opportunity = True
            signal.direction = "LEAN_MONEY"
            signal.reason = f"Ticket-money divergence {divergence:.0f}% (t={ticket_pct:.0f}% m={money_pct:.0f}%)"

    return signal


def get_public_fade_context(signal: PublicFadeSignal) -> dict:
    """
    Get context dict for engines that should NOT apply numeric modifiers.

    This is what Esoteric and Jarvis engines receive. They can reference
    these flags for conditional logic but MUST NOT apply the research_boost.

    Returns:
        Dict with boolean flags only (no numeric modifiers)
    """
    return {
        "public_overload": signal.is_fade_opportunity,
        "is_strong_fade": signal.is_strong_fade,
        "is_extreme_fade": signal.is_extreme_fade,
        "direction": signal.direction,
        "public_pct": signal.public_pct,
        # Explicitly NOT including research_boost here
    }
