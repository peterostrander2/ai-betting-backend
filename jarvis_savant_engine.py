"""
JARVIS SAVANT ENGINE v7.4 - The Complete Scoring System
=========================================================
Phase 1: Confluence Core (Gematria, JARVIS Triggers, Confluence)
Phase 2: Vedic/Astro Module (Planetary Hours, Nakshatras, Retrograde)
Phase 3: Learning Loop (Result Tracking, Weight Adjustment)

THE FORMULA (v10.1 Spec Aligned):
┌─────────────────────────────────────────────────────────────┐
│                    BOOKIE-O-EM CONFLUENCE                    │
├─────────────────────────────────────────────────────────────┤
│  RESEARCH SCORE (0-10)              ESOTERIC SCORE (0-10)   │
│  ├─ 8 AI Models (0-8)               ├─ JARVIS RS (0-4)      │
│  └─ 8 Pillars (0-8)                 ├─ Gematria (52%)       │
│      scaled to 0-10                 ├─ Public Fade (-13%)   │
│                                     ├─ Mid-Spread (+20%)    │
│                                     └─ Esoteric Edge (0-2)  │
│                                                              │
│  Alignment = 1 - |research - esoteric| / 10                 │
│                                                              │
│  CONFLUENCE LEVELS:                                          │
│  IMMORTAL (+10): 2178 + both ≥7.5 + alignment ≥80%          │
│  JARVIS_PERFECT (+7): Trigger + both ≥7.5 + alignment ≥80%  │
│  PERFECT (+5): both ≥7.5 + alignment ≥80%                   │
│  STRONG (+3): Both high OR aligned ≥70%                     │
│  MODERATE (+1): Aligned ≥60%                                │
│  DIVERGENT (+0): Models disagree                            │
│                                                              │
│  FINAL = (research × 0.67) + (esoteric × 0.33) + boost      │
│                                                              │
│  BET TIERS:                                                  │
│  GOLD_STAR (2u): FINAL ≥ 9.0                                │
│  EDGE_LEAN (1u): FINAL ≥ 7.5                                │
│  ML_DOG_LOTTO (0.5u): NHL Dog Protocol                      │
│  MONITOR: FINAL ≥ 6.0                                        │
│  PASS: FINAL < 6.0                                           │
└─────────────────────────────────────────────────────────────┘

2178: THE IMMORTAL - Only number where n^4 = reverse AND n^4 = 66^4
"""

import os
import json
import math
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import hashlib

# ============================================================================
# LOGGING
# ============================================================================

logger = logging.getLogger("jarvis_savant")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)

# ============================================================================
# PHASE 1: CONFLUENCE CORE - CONSTANTS
# ============================================================================

# THE IMMORTAL NUMBER: 2178
# 2178^4 = 22,497,682,178,656 (contains 2178 at position 7-10)
# Reverse of 2178 = 8712
# 8712^4 = 57,596,201,768,256 (contains 8712 at position 7-10)
# Both equal 66^4 in concatenation = MATHEMATICAL PROOF

JARVIS_TRIGGERS = {
    2178: {
        "name": "THE IMMORTAL",
        "boost": 20,
        "tier": "LEGENDARY",
        "description": "Only number where n^4=reverse AND n^4=66^4. Never collapses.",
        "mathematical": True,
        "reduction": 18  # 2+1+7+8 = 18
    },
    201: {
        "name": "THE ORDER",
        "boost": 12,
        "tier": "HIGH",
        "description": "Jesuit Order gematria. The Event of 201.",
        "mathematical": False,
        "reduction": 3   # 2+0+1 = 3
    },
    33: {
        "name": "THE MASTER",
        "boost": 10,
        "tier": "HIGH",
        "description": "Highest master number. Masonic significance.",
        "mathematical": False,
        "reduction": 6   # 3+3 = 6
    },
    93: {
        "name": "THE WILL",
        "boost": 10,
        "tier": "HIGH",
        "description": "Thelema sacred number. Will and Love.",
        "mathematical": False,
        "reduction": 12  # 9+3 = 12
    },
    322: {
        "name": "THE SOCIETY",
        "boost": 10,
        "tier": "HIGH",
        "description": "Skull & Bones. Genesis 3:22.",
        "mathematical": False,
        "reduction": 7   # 3+2+2 = 7
    },
    666: {
        "name": "THE BEAST",
        "boost": 8,
        "tier": "MEDIUM",
        "description": "Number of the beast. Solar square sum.",
        "mathematical": False,
        "reduction": 18  # 6+6+6 = 18
    },
    888: {
        "name": "JESUS",
        "boost": 8,
        "tier": "MEDIUM",
        "description": "Greek gematria for Jesus. Divine counterbalance.",
        "mathematical": False,
        "reduction": 24  # 8+8+8 = 24
    },
    369: {
        "name": "TESLA KEY",
        "boost": 7,
        "tier": "MEDIUM",
        "description": "Tesla's universe key. Vortex mathematics.",
        "mathematical": False,
        "reduction": 18  # 3+6+9 = 18
    }
}

POWER_NUMBERS = [11, 22, 33, 44, 55, 66, 77, 88, 99]
TESLA_NUMBERS = [3, 6, 9]
FIBONACCI_SEQUENCE = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]
VORTEX_PATTERN = [1, 2, 4, 8, 7, 5]  # Tesla's vortex math: doubling sequence mod 9
PHI = 1.618033988749895  # Golden ratio

# Gematria tables
SIMPLE_GEMATRIA = {chr(i): i - 96 for i in range(97, 123)}  # a=1, b=2, etc.
REVERSE_GEMATRIA = {chr(i): 123 - i for i in range(97, 123)}  # a=26, b=25, etc.

# ============================================================================
# PHASE 2: VEDIC/ASTRO CONSTANTS
# ============================================================================

# 7 Planets in Chaldean Order (oldest to fastest)
PLANETS = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

# Planetary day rulers (Sunday=0 -> Sun, Monday=1 -> Moon, etc.)
DAY_RULERS = {
    6: "Sun",      # Sunday
    0: "Moon",     # Monday
    1: "Mars",     # Tuesday
    2: "Mercury",  # Wednesday
    3: "Jupiter",  # Thursday
    4: "Venus",    # Friday
    5: "Saturn"    # Saturday
}

# Chaldean hour order (for planetary hours)
CHALDEAN_ORDER = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

# 27 Nakshatras (Lunar Mansions)
NAKSHATRAS = [
    {"name": "Ashwini", "deity": "Ashwini Kumaras", "nature": "Swift", "quality": "Light"},
    {"name": "Bharani", "deity": "Yama", "nature": "Fierce", "quality": "Balanced"},
    {"name": "Krittika", "deity": "Agni", "nature": "Sharp", "quality": "Mixed"},
    {"name": "Rohini", "deity": "Brahma", "nature": "Fixed", "quality": "Soft"},
    {"name": "Mrigashira", "deity": "Soma", "nature": "Soft", "quality": "Light"},
    {"name": "Ardra", "deity": "Rudra", "nature": "Sharp", "quality": "Fierce"},
    {"name": "Punarvasu", "deity": "Aditi", "nature": "Moveable", "quality": "Light"},
    {"name": "Pushya", "deity": "Brihaspati", "nature": "Light", "quality": "Auspicious"},
    {"name": "Ashlesha", "deity": "Nagas", "nature": "Sharp", "quality": "Fierce"},
    {"name": "Magha", "deity": "Pitrs", "nature": "Fierce", "quality": "Fixed"},
    {"name": "Purva Phalguni", "deity": "Bhaga", "nature": "Fierce", "quality": "Balanced"},
    {"name": "Uttara Phalguni", "deity": "Aryaman", "nature": "Fixed", "quality": "Soft"},
    {"name": "Hasta", "deity": "Savitar", "nature": "Light", "quality": "Soft"},
    {"name": "Chitra", "deity": "Tvashtar", "nature": "Soft", "quality": "Balanced"},
    {"name": "Swati", "deity": "Vayu", "nature": "Moveable", "quality": "Light"},
    {"name": "Vishakha", "deity": "Indra-Agni", "nature": "Sharp", "quality": "Mixed"},
    {"name": "Anuradha", "deity": "Mitra", "nature": "Soft", "quality": "Auspicious"},
    {"name": "Jyeshtha", "deity": "Indra", "nature": "Sharp", "quality": "Fierce"},
    {"name": "Mula", "deity": "Nirriti", "nature": "Sharp", "quality": "Fierce"},
    {"name": "Purva Ashadha", "deity": "Apas", "nature": "Fierce", "quality": "Balanced"},
    {"name": "Uttara Ashadha", "deity": "Vishvedevas", "nature": "Fixed", "quality": "Soft"},
    {"name": "Shravana", "deity": "Vishnu", "nature": "Moveable", "quality": "Auspicious"},
    {"name": "Dhanishta", "deity": "Vasus", "nature": "Moveable", "quality": "Light"},
    {"name": "Shatabhisha", "deity": "Varuna", "nature": "Moveable", "quality": "Balanced"},
    {"name": "Purva Bhadrapada", "deity": "Aja Ekapad", "nature": "Fierce", "quality": "Mixed"},
    {"name": "Uttara Bhadrapada", "deity": "Ahir Budhnya", "nature": "Fixed", "quality": "Soft"},
    {"name": "Revati", "deity": "Pushan", "nature": "Soft", "quality": "Auspicious"}
]

# Retrograde periods (approximate 2024-2026 data)
# Format: [(start_date, end_date), ...]
RETROGRADE_PERIODS = {
    "Mercury": [
        ("2024-04-01", "2024-04-25"),
        ("2024-08-05", "2024-08-28"),
        ("2024-11-25", "2024-12-15"),
        ("2025-03-14", "2025-04-07"),
        ("2025-07-18", "2025-08-11"),
        ("2025-11-09", "2025-11-29"),
        ("2026-03-01", "2026-03-21"),
        ("2026-07-02", "2026-07-26"),
    ],
    "Venus": [
        ("2025-03-01", "2025-04-12"),
        ("2026-10-03", "2026-11-13"),
    ],
    "Mars": [
        ("2024-12-06", "2025-02-23"),
        ("2027-01-10", "2027-04-01"),
    ]
}


# ============================================================================
# PHASE 1: JARVIS SAVANT ENGINE CLASS
# ============================================================================

class JarvisSavantEngine:
    """
    The Confluence Core - Phase 1 Implementation

    Scoring Components:
    - Gematria: 52% weight when triggers fire (30% base)
    - Public Fade: -13% in crush zone
    - Mid Spread: +20% Goldilocks zone
    - Large Spread Trap: -20% trap gate
    - Confluence: THE HEART - 6 levels of signal agreement
    - Blended Probability: 67/33 formula (67% model, 33% esoteric)
    """

    VERSION = "7.4"

    def __init__(self):
        self.triggers = JARVIS_TRIGGERS
        self.power_numbers = POWER_NUMBERS
        self.tesla_numbers = TESLA_NUMBERS
        self.fibonacci = FIBONACCI_SEQUENCE
        logger.info("JarvisSavantEngine v%s initialized", self.VERSION)

    # ========================================================================
    # 2178: THE IMMORTAL PROOF
    # ========================================================================

    def validate_2178(self) -> Dict[str, Any]:
        """
        Properties of 2178 - THE IMMORTAL number.

        Sacred Properties:
        1. 2178 × 4 = 8712 (its own reverse!)
        2. 2+1+7+8 = 18 = 1+8 = 9 (Tesla completion)
        3. 8+7+1+2 = 18 = 1+8 = 9 (Mirror completion)
        4. Only 4-digit number where n × 4 = reverse(n)
        5. Self-referential palindromic multiplication
        """
        n = 2178
        n_reverse = 8712

        # The TRUE immortal property: 2178 × 4 = 8712 (its reverse!)
        n_times_4 = n * 4
        is_reverse_multiple = n_times_4 == n_reverse

        # Calculate reductions
        n_reduction = sum(int(d) for d in str(n))  # 2+1+7+8 = 18
        final_reduction = sum(int(d) for d in str(n_reduction))  # 1+8 = 9

        # Verify reverse also reduces to 9
        reverse_reduction = sum(int(d) for d in str(n_reverse))  # 8+7+1+2 = 18
        reverse_final = sum(int(d) for d in str(reverse_reduction))  # 1+8 = 9

        return {
            "number": n,
            "reverse": n_reverse,
            "n_times_4": n_times_4,
            "is_reverse_multiple": is_reverse_multiple,
            "digital_root": final_reduction,
            "reverse_digital_root": reverse_final,
            "is_immortal": is_reverse_multiple and final_reduction == 9,
            "proof": "2178 × 4 = 8712 (its own reverse). Only 4-digit number with this property.",
            "significance": "THE IMMORTAL - Self-referential through multiplication"
        }

    # ========================================================================
    # TRIGGER DETECTION
    # ========================================================================

    def check_jarvis_trigger(self, value: Any) -> Dict[str, Any]:
        """
        Check if a value triggers any JARVIS numbers.

        Supports:
        - Direct number matches
        - Reduction matches (sum of digits)
        - Gematria reduction of strings
        """
        triggers_hit = []
        total_boost = 0

        # Convert to number if needed
        if isinstance(value, str):
            # Calculate gematria
            gematria = self.calculate_gematria(value)
            value_num = gematria["simple"]
        else:
            value_num = int(value)

        # Check direct matches
        if value_num in self.triggers:
            trigger = self.triggers[value_num]
            triggers_hit.append({
                "number": value_num,
                "match_type": "DIRECT",
                "name": trigger["name"],
                "boost": trigger["boost"],
                "tier": trigger["tier"]
            })
            total_boost += trigger["boost"]

        # Check reduction matches
        reduction = self._reduce_to_single(value_num)
        for trigger_num, trigger_data in self.triggers.items():
            if trigger_data.get("reduction") == reduction and trigger_num not in [t["number"] for t in triggers_hit]:
                triggers_hit.append({
                    "number": trigger_num,
                    "match_type": "REDUCTION",
                    "reduction_value": reduction,
                    "name": trigger_data["name"],
                    "boost": trigger_data["boost"] * 0.5,  # Half boost for reduction match
                    "tier": trigger_data["tier"]
                })
                total_boost += trigger_data["boost"] * 0.5

        # Check for power numbers
        if value_num in self.power_numbers:
            triggers_hit.append({
                "number": value_num,
                "match_type": "POWER_NUMBER",
                "name": f"POWER {value_num}",
                "boost": 3,
                "tier": "LOW"
            })
            total_boost += 3

        # Check for Tesla numbers in reduction
        if reduction in self.tesla_numbers:
            triggers_hit.append({
                "number": reduction,
                "match_type": "TESLA_REDUCTION",
                "name": f"TESLA {reduction}",
                "boost": 2,
                "tier": "LOW"
            })
            total_boost += 2

        return {
            "input": value,
            "numeric_value": value_num,
            "reduction": reduction,
            "triggers_hit": triggers_hit,
            "total_boost": min(20, total_boost),  # Cap at 20
            "trigger_count": len(triggers_hit)
        }

    def _reduce_to_single(self, num: int) -> int:
        """Reduce a number to single digit (except master numbers)."""
        while num > 9 and num not in [11, 22, 33]:
            num = sum(int(d) for d in str(num))
        return num

    # ========================================================================
    # GEMATRIA CALCULATIONS
    # ========================================================================

    def calculate_gematria(self, text: str) -> Dict[str, int]:
        """
        Calculate Simple, Reverse, and Jewish gematria values.
        """
        text_lower = text.lower().replace(" ", "")

        simple = sum(SIMPLE_GEMATRIA.get(c, 0) for c in text_lower)
        reverse = sum(REVERSE_GEMATRIA.get(c, 0) for c in text_lower)

        # Jewish/Hebrew gematria (ordinal with adjustments)
        jewish = simple * 6 + len(text_lower)

        return {
            "text": text,
            "simple": simple,
            "reverse": reverse,
            "jewish": jewish,
            "simple_reduction": self._reduce_to_single(simple),
            "reverse_reduction": self._reduce_to_single(reverse)
        }

    def calculate_gematria_signal(self, player: str, team: str, opponent: str) -> Dict[str, Any]:
        """
        Calculate gematria-based signal for a pick.

        52% weight when triggers fire (30% base).
        """
        player_gem = self.calculate_gematria(player)
        team_gem = self.calculate_gematria(team)
        opponent_gem = self.calculate_gematria(opponent)

        # Combined value
        combined = player_gem["simple"] + team_gem["simple"]
        matchup_diff = abs(team_gem["simple"] - opponent_gem["simple"])

        # Check for triggers
        combined_trigger = self.check_jarvis_trigger(combined)
        matchup_trigger = self.check_jarvis_trigger(matchup_diff)

        # Calculate weight
        base_weight = 0.30
        if combined_trigger["trigger_count"] > 0 or matchup_trigger["trigger_count"] > 0:
            base_weight = 0.52  # Elevated weight when triggers fire

        # Calculate signal strength (0-1)
        signal_strength = min(1.0, (combined_trigger["total_boost"] + matchup_trigger["total_boost"]) / 20)

        # Determine if triggered (any JARVIS trigger hit)
        triggered = combined_trigger["trigger_count"] > 0 or matchup_trigger["trigger_count"] > 0

        # Calculate influence for scoring (-1 to 1 scale)
        influence = signal_strength if triggered else signal_strength * 0.5

        return {
            "player_gematria": player_gem,
            "team_gematria": team_gem,
            "opponent_gematria": opponent_gem,
            "combined_value": combined,
            "matchup_diff": matchup_diff,
            "combined_trigger": combined_trigger,
            "matchup_trigger": matchup_trigger,
            "weight": base_weight,
            "signal_strength": signal_strength,
            "signal": "STRONG" if signal_strength > 0.7 else "MODERATE" if signal_strength > 0.4 else "WEAK",
            "triggered": triggered,
            "influence": influence
        }

    # ========================================================================
    # PUBLIC FADE SIGNAL
    # ========================================================================

    def calculate_public_fade_signal(self, public_pct: float) -> Dict[str, Any]:
        """
        Calculate public fade signal with graduated adjustments.

        PUBLIC FADE CRUSH ZONE (v10.1 spec):
        ≥80% public on chalk  →  -0.95 influence
        ≥75% public on chalk  →  -0.85 influence
        ≥70% public on chalk  →  -0.75 influence
        ≥65% public on chalk  →  -0.65 influence
        """
        # Graduated fade based on public percentage
        if public_pct >= 80:
            signal = "FADE_PUBLIC"
            adjustment = -0.95
            is_crush_zone = True
            explanation = f"Public at {public_pct}% - MAXIMUM CRUSH ZONE. Strong fade."
        elif public_pct >= 75:
            signal = "FADE_PUBLIC"
            adjustment = -0.85
            is_crush_zone = True
            explanation = f"Public at {public_pct}% - HIGH CRUSH ZONE. Fade recommended."
        elif public_pct >= 70:
            signal = "FADE_PUBLIC"
            adjustment = -0.75
            is_crush_zone = True
            explanation = f"Public at {public_pct}% - CRUSH ZONE. Fade the public side."
        elif public_pct >= 65:
            signal = "FADE_PUBLIC"
            adjustment = -0.65
            is_crush_zone = True
            explanation = f"Public at {public_pct}% - EARLY CRUSH. Consider fading."
        elif public_pct <= 20:
            signal = "FOLLOW_PUBLIC"
            adjustment = -0.95
            is_crush_zone = True
            explanation = f"Public at {public_pct}% - Extreme contrarian. Follow public."
        elif public_pct <= 25:
            signal = "FOLLOW_PUBLIC"
            adjustment = -0.85
            is_crush_zone = True
            explanation = f"Public at {public_pct}% - Strong contrarian value."
        elif public_pct <= 30:
            signal = "FOLLOW_PUBLIC"
            adjustment = -0.75
            is_crush_zone = True
            explanation = f"Public at {public_pct}% - Contrarian value on public side."
        elif public_pct <= 35:
            signal = "LEAN_PUBLIC"
            adjustment = -0.65
            is_crush_zone = False
            explanation = f"Public at {public_pct}% - Slight contrarian lean."
        else:
            signal = "NEUTRAL"
            adjustment = 0.0
            is_crush_zone = False
            explanation = f"Public at {public_pct}% - No strong fade signal."

        return {
            "public_pct": public_pct,
            "is_crush_zone": is_crush_zone,
            "signal": signal,
            "adjustment": adjustment,
            "influence": adjustment,  # Alias for router compatibility
            "explanation": explanation
        }

    # ========================================================================
    # MID SPREAD SIGNAL (GOLDILOCKS ZONE)
    # ========================================================================

    def calculate_mid_spread_signal(self, spread: float) -> Dict[str, Any]:
        """
        Calculate mid-spread signal.

        +20% boost in Goldilocks zone (spread between +4 and +9) per v10.1 spec.
        """
        abs_spread = abs(spread)

        # Goldilocks zone: 4-9 points (most predictable range per spec)
        if 4 <= abs_spread <= 9:
            signal = "GOLDILOCKS"
            adjustment = 0.20
            explanation = f"Spread {spread} in Goldilocks zone (+4 to +9). Most predictable range."
        elif abs_spread < 4:
            signal = "PICKEM"
            adjustment = 0.0
            explanation = f"Spread {spread} is pick'em territory. High variance."
        elif abs_spread >= 14:
            signal = "TRAP_ZONE"
            adjustment = -0.20
            explanation = f"Spread {spread} in trap zone. Fade large favorites."
        elif abs_spread > 9:
            signal = "BLOWOUT"
            adjustment = -0.10
            explanation = f"Spread {spread} indicates potential blowout. Garbage time risk."
        else:
            signal = "STANDARD"
            adjustment = 0.05
            explanation = f"Spread {spread} in standard range."

        return {
            "spread": spread,
            "abs_spread": abs_spread,
            "signal": signal,
            "adjustment": adjustment,
            "modifier": adjustment,  # Alias for router compatibility
            "explanation": explanation
        }

    # ========================================================================
    # LARGE SPREAD TRAP
    # ========================================================================

    def calculate_large_spread_trap(self, spread: float, total: float) -> Dict[str, Any]:
        """
        Calculate large spread trap signal.

        -20% trap gate for spreads > 14 (likely trap games).
        """
        abs_spread = abs(spread)

        if abs_spread >= 14:
            signal = "TRAP_GATE"
            adjustment = -0.20
            is_trap = True
            explanation = f"Spread {spread} > 14. TRAP GATE active. Large favorites cover < 50% historically."
        elif abs_spread >= 10:
            signal = "CAUTION"
            adjustment = -0.10
            is_trap = False
            explanation = f"Spread {spread} in caution zone. Monitor for trap."
        else:
            signal = "CLEAR"
            adjustment = 0.0
            is_trap = False
            explanation = "Spread in normal range."

        # Additional check: High total + large spread = likely backdoor cover
        if total > 230 and abs_spread >= 10:
            adjustment -= 0.05
            explanation += " High total increases backdoor cover risk."

        return {
            "spread": spread,
            "total": total,
            "signal": signal,
            "is_trap": is_trap,
            "adjustment": adjustment,
            "modifier": adjustment,  # Alias for router compatibility
            "explanation": explanation
        }

    # ========================================================================
    # CONFLUENCE - THE HEART (v10.1 Dual-Score Alignment System)
    # ========================================================================

    def calculate_confluence(
        self,
        research_score: float,
        esoteric_score: float,
        immortal_detected: bool = False,
        jarvis_triggered: bool = False
    ) -> Dict[str, Any]:
        """
        THE HEART - Calculate confluence using dual-score alignment.

        v10.1 Spec Formula:
        Alignment = 1 - |research - esoteric| / 10

        CONFLUENCE LEVELS:
        - IMMORTAL (+10): 2178 + both ≥7.5 + alignment ≥80%
        - JARVIS_PERFECT (+7): Trigger + both ≥7.5 + alignment ≥80%
        - PERFECT (+5): both ≥7.5 + alignment ≥80%
        - STRONG (+3): Both high OR aligned ≥70%
        - MODERATE (+1): Aligned ≥60%
        - DIVERGENT (+0): Models disagree
        """
        # Calculate alignment percentage (0-100%)
        alignment = 1 - abs(research_score - esoteric_score) / 10
        alignment_pct = alignment * 100

        # Check conditions
        both_high = research_score >= 7.5 and esoteric_score >= 7.5
        either_high = research_score >= 7.5 or esoteric_score >= 7.5
        aligned_80 = alignment_pct >= 80
        aligned_70 = alignment_pct >= 70
        aligned_60 = alignment_pct >= 60

        # Determine confluence level based on v10.1 spec
        if immortal_detected and both_high and aligned_80:
            level = "IMMORTAL"
            boost = 10
            color = "rainbow"
            action = "IMMORTAL CONFLUENCE - MAXIMUM SMASH"
        elif jarvis_triggered and both_high and aligned_80:
            level = "JARVIS_PERFECT"
            boost = 7
            color = "gold"
            action = "JARVIS PERFECT - STRONG SMASH"
        elif both_high and aligned_80:
            level = "PERFECT"
            boost = 5
            color = "purple"
            action = "PERFECT CONFLUENCE - PLAY"
        elif (both_high or either_high) and aligned_70:
            level = "STRONG"
            boost = 3
            color = "green"
            action = "STRONG CONFLUENCE - LEAN"
        elif aligned_60:
            level = "MODERATE"
            boost = 1
            color = "blue"
            action = "MODERATE - MONITOR"
        else:
            level = "DIVERGENT"
            boost = 0
            color = "red"
            action = "DIVERGENT - PASS"

        return {
            "research_score": research_score,
            "esoteric_score": esoteric_score,
            "alignment": round(alignment, 4),
            "alignment_pct": round(alignment_pct, 1),
            "level": level,
            "boost": boost,
            "color": color,
            "action": action,
            "immortal_detected": immortal_detected,
            "jarvis_triggered": jarvis_triggered,
            "both_high": both_high,
            "aligned_80": aligned_80
        }

    def calculate_confluence_legacy(
        self,
        gematria_signal: Dict,
        public_fade: Dict,
        mid_spread: Dict,
        trap_signal: Dict,
        astro_score: Optional[Dict] = None,
        sharp_signal: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Legacy confluence calculation (signal counting method).
        Kept for backward compatibility.
        """
        signals = []

        if gematria_signal.get("signal") in ["STRONG", "MODERATE"]:
            signals.append("GEMATRIA")
        if public_fade.get("signal") == "FADE_PUBLIC":
            signals.append("PUBLIC_FADE")
        if mid_spread.get("signal") == "GOLDILOCKS":
            signals.append("GOLDILOCKS")
        if trap_signal.get("signal") == "CLEAR":
            signals.append("NO_TRAP")
        if astro_score and astro_score.get("overall_score", 0) > 60:
            signals.append("ASTRO")
        if sharp_signal and sharp_signal.get("signal_strength") == "STRONG":
            signals.append("SHARP")

        signal_count = len(signals)

        if signal_count >= 6:
            level, boost = "PERFECT", 5
        elif signal_count >= 4:
            level, boost = "STRONG", 3
        elif signal_count >= 3:
            level, boost = "MODERATE", 1
        else:
            level, boost = "DIVERGENT", 0

        return {
            "signals_hit": signals,
            "signal_count": signal_count,
            "level": level,
            "boost": boost
        }

    # ========================================================================
    # BLENDED PROBABILITY - 67/33 FORMULA
    # ========================================================================

    def calculate_blended_probability(
        self,
        model_probability: float,
        esoteric_score: float
    ) -> Dict[str, Any]:
        """
        67/33 Formula: Blend model and esoteric predictions.

        67% weight to AI/statistical model
        33% weight to esoteric signals
        """
        # Normalize esoteric score to probability (0-100 scale)
        esoteric_prob = esoteric_score * 10  # Convert 0-10 to 0-100

        # Apply 67/33 blend
        blended = (model_probability * 0.67) + (esoteric_prob * 0.33)

        # Calculate edge (blended vs implied odds)
        edge = blended - 50  # Simple edge calculation

        return {
            "model_probability": model_probability,
            "esoteric_score": esoteric_score,
            "esoteric_probability": esoteric_prob,
            "blended_probability": round(blended, 2),
            "model_weight": 0.67,
            "esoteric_weight": 0.33,
            "edge": round(edge, 2),
            "is_positive_edge": edge > 0
        }

    # ========================================================================
    # BET TIER DETERMINATION
    # ========================================================================

    def determine_bet_tier(
        self,
        final_score: float,
        confluence: Dict,
        nhl_dog_protocol: bool = False
    ) -> Dict[str, Any]:
        """
        Determine bet tier based on FINAL score (v10.1 spec).

        FINAL = (research × 0.67) + (esoteric × 0.33) + confluence_boost

        Tiers (v10.1 spec):
        - GOLD_STAR (2u): FINAL ≥ 9.0
        - EDGE_LEAN (1u): FINAL ≥ 7.5
        - ML_DOG_LOTTO (0.5u): NHL Dog Protocol triggered
        - MONITOR (0u): FINAL ≥ 6.0
        - PASS: FINAL < 6.0
        """
        confluence_level = confluence.get("level", "DIVERGENT")

        # NHL Dog Protocol takes precedence if triggered
        if nhl_dog_protocol:
            tier = "ML_DOG_LOTTO"
            unit_size = 0.5
            explanation = "NHL Dog Protocol triggered. ML dog lotto play."
        # Standard tier determination based on final score
        elif final_score >= 9.0:
            tier = "GOLD_STAR"
            unit_size = 2.0
            explanation = "GOLD STAR - Maximum confidence. 2 unit play."
        elif final_score >= 7.5:
            tier = "EDGE_LEAN"
            unit_size = 1.0
            explanation = "EDGE LEAN - Strong edge detected. 1 unit play."
        elif final_score >= 6.0:
            tier = "MONITOR"
            unit_size = 0.0
            explanation = "MONITOR - Track but no action."
        else:
            tier = "PASS"
            unit_size = 0.0
            explanation = "PASS - Insufficient edge."

        return {
            "tier": tier,
            "unit_size": unit_size,
            "explanation": explanation,
            "final_score": round(final_score, 2),
            "confluence_level": confluence_level,
            "nhl_dog_protocol": nhl_dog_protocol
        }

    # ========================================================================
    # NHL DOG PROTOCOL (v10.1 spec)
    # ========================================================================

    def calculate_nhl_dog_protocol(
        self,
        is_puck_line_dog: bool,
        research_score: float,
        public_on_favorite_pct: float
    ) -> Dict[str, Any]:
        """
        NHL Dog Protocol - Special trigger for ML dog plays.

        NHL DOG PROTOCOL TRIGGERS (v10.1 spec):
        ┌─────────────────────────────────────────────┐
        │ Puck line dog (+1.5)        ✓              │
        │ Research Score ≥9.3         ✓              │
        │ Public ≥65% on favorite     ✓              │
        │ All 3 = 0.5u ML DOG OF DAY                 │
        └─────────────────────────────────────────────┘
        """
        triggers = {
            "puck_line_dog": is_puck_line_dog,
            "research_score_high": research_score >= 9.3,
            "public_on_favorite": public_on_favorite_pct >= 65
        }

        all_triggered = all(triggers.values())
        trigger_count = sum(1 for v in triggers.values() if v)

        return {
            "triggers": triggers,
            "trigger_count": trigger_count,
            "all_triggered": all_triggered,
            "recommendation": "0.5u ML DOG OF DAY" if all_triggered else "NOT TRIGGERED",
            "research_score": research_score,
            "public_on_favorite_pct": public_on_favorite_pct,
            "explanation": (
                "NHL DOG PROTOCOL ACTIVE - Take the ML dog!" if all_triggered
                else f"NHL Dog Protocol: {trigger_count}/3 triggers hit"
            )
        }

    # ========================================================================
    # FIBONACCI LINE ALIGNMENT (Fix #7)
    # ========================================================================

    def calculate_fibonacci_alignment(self, line: float) -> Dict[str, Any]:
        """
        Check if a betting line aligns with Fibonacci numbers.

        Lines that align with Fibonacci (or Phi ratios) are considered
        more "harmonically balanced" and may indicate fair value.
        """
        abs_line = abs(line)

        # Check direct Fibonacci match
        is_fib = abs_line in FIBONACCI_SEQUENCE

        # Check if close to a Fibonacci number (within 0.5)
        nearest_fib = min(FIBONACCI_SEQUENCE, key=lambda x: abs(x - abs_line))
        distance_to_fib = abs(abs_line - nearest_fib)
        near_fib = distance_to_fib <= 0.5

        # Check Phi ratio alignment (line / PHI or line * PHI)
        phi_aligned = False
        phi_ratio = None
        for fib in FIBONACCI_SEQUENCE[:10]:
            if fib > 0:
                ratio = abs_line / fib
                if 1.5 <= ratio <= 1.7:  # Close to PHI (1.618)
                    phi_aligned = True
                    phi_ratio = round(ratio, 3)
                    break

        # Calculate score modifier
        if is_fib:
            score_mod = 0.10
            signal = "FIB_EXACT"
        elif near_fib:
            score_mod = 0.05
            signal = "FIB_NEAR"
        elif phi_aligned:
            score_mod = 0.07
            signal = "PHI_ALIGNED"
        else:
            score_mod = 0.0
            signal = "NO_FIB"

        return {
            "line": line,
            "is_fibonacci": is_fib,
            "near_fibonacci": near_fib,
            "nearest_fib": nearest_fib,
            "distance_to_fib": round(distance_to_fib, 2),
            "phi_aligned": phi_aligned,
            "phi_ratio": phi_ratio,
            "signal": signal,
            "score_modifier": score_mod,
            "modifier": score_mod  # Alias for router compatibility
        }

    # ========================================================================
    # VORTEX PATTERN CHECK (Fix #8)
    # ========================================================================

    def calculate_vortex_pattern(self, value: int) -> Dict[str, Any]:
        """
        Check if a value follows Tesla's vortex math pattern: 1-2-4-8-7-5

        The vortex pattern is the doubling sequence reduced to single digits:
        1 → 2 → 4 → 8 → 16(7) → 32(5) → 64(1) → repeat

        Values that reduce to 3, 6, or 9 are outside the vortex (Tesla's "key").
        """
        # Reduce to single digit
        reduction = value
        while reduction > 9:
            reduction = sum(int(d) for d in str(reduction))

        in_vortex = reduction in VORTEX_PATTERN
        is_tesla_key = reduction in TESLA_NUMBERS

        # Find position in vortex sequence
        vortex_position = None
        if in_vortex:
            vortex_position = VORTEX_PATTERN.index(reduction)

        # Calculate score modifier
        if is_tesla_key:
            score_mod = 0.15  # Tesla numbers are most powerful
            signal = f"TESLA_{reduction}"
        elif in_vortex:
            score_mod = 0.08
            signal = f"VORTEX_{reduction}"
        else:
            score_mod = 0.0
            signal = "NO_VORTEX"

        return {
            "value": value,
            "reduction": reduction,
            "in_vortex": in_vortex,
            "is_tesla_key": is_tesla_key,
            "vortex_position": vortex_position,
            "signal": signal,
            "score_modifier": score_mod,
            "modifier": score_mod,  # Alias for router compatibility
            "vortex_pattern": VORTEX_PATTERN,
            "tesla_numbers": TESLA_NUMBERS
        }


# ============================================================================
# PHASE 2: VEDIC/ASTRO MODULE
# ============================================================================

class VedicAstroEngine:
    """
    Phase 2: Vedic and Astrological Calculations

    Components:
    - Planetary Hours (Chaldean order)
    - Nakshatra (27 lunar mansions)
    - Retrograde Detection
    - Combined Astro Score
    """

    def __init__(self):
        self.planets = PLANETS
        self.nakshatras = NAKSHATRAS
        self.day_rulers = DAY_RULERS
        self.chaldean_order = CHALDEAN_ORDER
        self.retrograde_periods = RETROGRADE_PERIODS

    def calculate_planetary_hour(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Calculate the current planetary hour using Chaldean order.

        The day is divided into 24 hours (12 day + 12 night).
        Each hour is ruled by a planet in Chaldean order.
        """
        if dt is None:
            dt = datetime.now()

        # Get day ruler
        weekday = dt.weekday()
        day_ruler = self.day_rulers[weekday]

        # Find day ruler index in Chaldean order
        day_ruler_idx = self.chaldean_order.index(day_ruler)

        # Calculate hour of day (0-23)
        hour = dt.hour

        # Planetary hour = (day_ruler_idx + hour) % 7
        hour_ruler_idx = (day_ruler_idx + hour) % 7
        hour_ruler = self.chaldean_order[hour_ruler_idx]

        # Determine if favorable for betting
        favorable_planets = ["Jupiter", "Venus", "Sun"]
        is_favorable = hour_ruler in favorable_planets

        return {
            "datetime": dt.isoformat(),
            "day_of_week": dt.strftime("%A"),
            "day_ruler": day_ruler,
            "hour": hour,
            "hour_ruler": hour_ruler,
            "is_favorable": is_favorable,
            "influence": self._get_planet_influence(hour_ruler),
            "chaldean_order": self.chaldean_order
        }

    def _get_planet_influence(self, planet: str) -> Dict[str, str]:
        """Get betting influence of a planet."""
        influences = {
            "Saturn": {"nature": "Restrictive", "betting": "Underdogs, low totals", "score_mod": -0.5},
            "Jupiter": {"nature": "Expansive", "betting": "Favorites, overs", "score_mod": 1.0},
            "Mars": {"nature": "Aggressive", "betting": "High action, volatility", "score_mod": 0.5},
            "Sun": {"nature": "Dominant", "betting": "Favorites, strong plays", "score_mod": 0.8},
            "Venus": {"nature": "Harmonious", "betting": "Props, player performance", "score_mod": 0.7},
            "Mercury": {"nature": "Variable", "betting": "Live betting, quick decisions", "score_mod": 0.0},
            "Moon": {"nature": "Emotional", "betting": "Follow public, momentum", "score_mod": 0.3}
        }
        return influences.get(planet, {"nature": "Unknown", "betting": "Standard", "score_mod": 0.0})

    def calculate_nakshatra(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Calculate the current Nakshatra (lunar mansion).

        The Moon travels through all 27 Nakshatras in ~27.3 days.
        Each Nakshatra spans 13°20' of the zodiac.
        """
        if dt is None:
            dt = datetime.now()

        # Reference new moon (approximate)
        known_new_moon = datetime(2024, 1, 11)
        days_since = (dt - known_new_moon).days + (dt.hour / 24)

        # Lunar cycle is ~29.53 days
        lunar_cycle = 29.53

        # Moon traverses all 27 nakshatras in one lunar month
        # Each nakshatra = 29.53 / 27 = ~1.094 days
        nakshatra_duration = lunar_cycle / 27

        # Calculate current nakshatra index
        moon_age = days_since % lunar_cycle
        nakshatra_idx = int((moon_age / lunar_cycle) * 27) % 27

        nakshatra = self.nakshatras[nakshatra_idx]

        # Determine betting influence based on nakshatra nature
        nature = nakshatra.get("nature", "Neutral")
        if nature in ["Light", "Soft"]:
            betting_signal = "FAVORABLE"
            score_mod = 0.5
        elif nature in ["Fierce", "Sharp"]:
            betting_signal = "VOLATILE"
            score_mod = 0.0
        else:
            betting_signal = "NEUTRAL"
            score_mod = 0.2

        return {
            "datetime": dt.isoformat(),
            "nakshatra_index": nakshatra_idx + 1,
            "nakshatra_name": nakshatra["name"],
            "deity": nakshatra["deity"],
            "nature": nakshatra["nature"],
            "quality": nakshatra["quality"],
            "moon_age_days": round(moon_age, 2),
            "betting_signal": betting_signal,
            "score_modifier": score_mod
        }

    def is_planet_retrograde(self, planet: str, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Check if a planet is currently retrograde.

        Retrograde periods affect betting differently:
        - Mercury: Communication issues, misread lines
        - Venus: Value distortion
        - Mars: Delayed aggression, underdogs
        """
        if dt is None:
            dt = datetime.now()

        planet_title = planet.title()

        if planet_title not in self.retrograde_periods:
            return {
                "planet": planet_title,
                "is_retrograde": False,
                "note": f"No retrograde data for {planet_title}"
            }

        current_date = dt.strftime("%Y-%m-%d")
        is_retrograde = False
        period = None

        for start, end in self.retrograde_periods[planet_title]:
            if start <= current_date <= end:
                is_retrograde = True
                period = {"start": start, "end": end}
                break

        # Determine betting influence
        if is_retrograde:
            influences = {
                "Mercury": {"betting": "Avoid parlays, miscommunication likely", "score_mod": -0.3},
                "Venus": {"betting": "Value bets unreliable", "score_mod": -0.2},
                "Mars": {"betting": "Underdogs favored, delayed action", "score_mod": 0.1}
            }
            influence = influences.get(planet_title, {"betting": "Monitor", "score_mod": 0.0})
        else:
            influence = {"betting": "Normal conditions", "score_mod": 0.0}

        return {
            "planet": planet_title,
            "date": current_date,
            "is_retrograde": is_retrograde,
            "period": period,
            "influence": influence
        }

    def calculate_astro_score(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Calculate combined astro/vedic score.

        Components:
        - Planetary Hour: 40%
        - Nakshatra: 35%
        - Retrograde: 25%
        """
        if dt is None:
            dt = datetime.now()

        # Get components
        planetary_hour = self.calculate_planetary_hour(dt)
        nakshatra = self.calculate_nakshatra(dt)

        # Check retrogrades
        mercury_retro = self.is_planet_retrograde("Mercury", dt)
        venus_retro = self.is_planet_retrograde("Venus", dt)
        mars_retro = self.is_planet_retrograde("Mars", dt)

        # Calculate component scores (0-100 scale)
        hour_influence = self._get_planet_influence(planetary_hour["hour_ruler"])
        hour_score = 50 + (hour_influence.get("score_mod", 0) * 20)

        nakshatra_score = 50 + (nakshatra["score_modifier"] * 20)

        # Retrograde penalty
        retro_score = 70  # Base score
        if mercury_retro["is_retrograde"]:
            retro_score += mercury_retro["influence"].get("score_mod", 0) * 20
        if venus_retro["is_retrograde"]:
            retro_score += venus_retro["influence"].get("score_mod", 0) * 20
        if mars_retro["is_retrograde"]:
            retro_score += mars_retro["influence"].get("score_mod", 0) * 20

        # Weight components
        overall_score = (hour_score * 0.40) + (nakshatra_score * 0.35) + (retro_score * 0.25)

        return {
            "datetime": dt.isoformat(),
            "overall_score": round(overall_score, 1),
            "rating": "HIGH" if overall_score >= 65 else "MEDIUM" if overall_score >= 50 else "LOW",
            "components": {
                "planetary_hour": {
                    "score": round(hour_score, 1),
                    "weight": 0.40,
                    "ruler": planetary_hour["hour_ruler"],
                    "is_favorable": planetary_hour["is_favorable"]
                },
                "nakshatra": {
                    "score": round(nakshatra_score, 1),
                    "weight": 0.35,
                    "name": nakshatra["nakshatra_name"],
                    "nature": nakshatra["nature"]
                },
                "retrograde": {
                    "score": round(retro_score, 1),
                    "weight": 0.25,
                    "mercury": mercury_retro["is_retrograde"],
                    "venus": venus_retro["is_retrograde"],
                    "mars": mars_retro["is_retrograde"]
                }
            },
            "planetary_hour": planetary_hour,
            "nakshatra": nakshatra,
            "retrogrades": {
                "mercury": mercury_retro,
                "venus": venus_retro,
                "mars": mars_retro
            }
        }


# ============================================================================
# PHASE 3: LEARNING LOOP
# ============================================================================

@dataclass
class EsotericPickRecord:
    """Record of an esoteric pick for learning."""
    pick_id: str
    sport: str
    game_id: str
    pick_type: str  # spread, total, prop
    selection: str  # team name or over/under
    line: float
    odds: int
    timestamp: str

    # Esoteric signals that fired
    gematria_signal: str  # STRONG, MODERATE, WEAK
    gematria_weight: float
    public_fade_active: bool
    goldilocks_active: bool
    trap_active: bool
    confluence_level: str
    confluence_score: float
    astro_score: float
    planetary_hour_ruler: str
    nakshatra: str
    mercury_retrograde: bool

    # Scores
    total_esoteric_score: float
    blended_probability: float
    bet_tier: str

    # Outcome (filled in after grading)
    actual_result: Optional[str] = None  # WIN, LOSS, PUSH
    graded_at: Optional[str] = None


class EsotericLearningLoop:
    """
    Phase 3: Learning Loop for Esoteric System

    Tracks:
    - Pick outcomes
    - Which signals fired
    - Performance by signal type

    Adjusts:
    - Signal weights based on historical performance
    - Thresholds for activation
    """

    STORAGE_PATH = "./esoteric_learning_data"

    # Default weights (v10.1 spec aligned)
    DEFAULT_WEIGHTS = {
        "gematria": 0.52,        # 52% - Boss approved dominant weight
        "numerology": 0.20,      # 20% - Date-based
        "astro": 0.13,           # 13% - Moon phase
        "vedic": 0.10,           # 10% - Future expansion
        "sacred": 0.05,          # 5%  - Power numbers
        "fib_phi": 0.05,         # 5%  - Fibonacci alignment
        "vortex": 0.05           # 5%  - 3-6-9 and 1-2-4-8-7-5 patterns
    }
    # Note: Weights should sum to 1.10 to account for overlap - normalized on use

    def __init__(self):
        self.picks: List[EsotericPickRecord] = []
        self.weights = dict(self.DEFAULT_WEIGHTS)
        self.performance: Dict[str, Dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "pushes": 0})
        self._load_state()

    def _load_state(self):
        """Load saved state from disk."""
        os.makedirs(self.STORAGE_PATH, exist_ok=True)

        # Load weights
        weights_file = os.path.join(self.STORAGE_PATH, "weights.json")
        if os.path.exists(weights_file):
            try:
                with open(weights_file, 'r') as f:
                    self.weights = json.load(f)
                logger.info("Loaded learned weights from %s", weights_file)
            except Exception as e:
                logger.warning("Could not load weights: %s", e)

        # Load picks
        picks_file = os.path.join(self.STORAGE_PATH, "picks.json")
        if os.path.exists(picks_file):
            try:
                with open(picks_file, 'r') as f:
                    picks_data = json.load(f)
                    self.picks = [EsotericPickRecord(**p) for p in picks_data]
                logger.info("Loaded %d pick records", len(self.picks))
            except Exception as e:
                logger.warning("Could not load picks: %s", e)

        # Load performance
        perf_file = os.path.join(self.STORAGE_PATH, "performance.json")
        if os.path.exists(perf_file):
            try:
                with open(perf_file, 'r') as f:
                    self.performance = defaultdict(lambda: {"wins": 0, "losses": 0, "pushes": 0}, json.load(f))
                logger.info("Loaded performance data")
            except Exception as e:
                logger.warning("Could not load performance: %s", e)

    def _save_state(self):
        """Save state to disk."""
        os.makedirs(self.STORAGE_PATH, exist_ok=True)

        # Save weights
        weights_file = os.path.join(self.STORAGE_PATH, "weights.json")
        with open(weights_file, 'w') as f:
            json.dump(self.weights, f, indent=2)

        # Save picks
        picks_file = os.path.join(self.STORAGE_PATH, "picks.json")
        with open(picks_file, 'w') as f:
            json.dump([asdict(p) for p in self.picks], f, indent=2)

        # Save performance
        perf_file = os.path.join(self.STORAGE_PATH, "performance.json")
        with open(perf_file, 'w') as f:
            json.dump(dict(self.performance), f, indent=2)

        logger.info("Saved learning loop state")

    def log_pick(
        self,
        sport: str,
        game_id: str,
        pick_type: str,
        selection: str,
        line: float,
        odds: int,
        esoteric_analysis: Dict[str, Any]
    ) -> str:
        """
        Log a pick with all esoteric signals.

        Returns pick_id for later grading.
        """
        pick_id = f"ESO_{sport}_{game_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        record = EsotericPickRecord(
            pick_id=pick_id,
            sport=sport.upper(),
            game_id=game_id,
            pick_type=pick_type,
            selection=selection,
            line=line,
            odds=odds,
            timestamp=datetime.now().isoformat(),

            gematria_signal=esoteric_analysis.get("gematria", {}).get("signal", "WEAK"),
            gematria_weight=esoteric_analysis.get("gematria", {}).get("weight", 0.30),
            public_fade_active=esoteric_analysis.get("public_fade", {}).get("is_crush_zone", False),
            goldilocks_active=esoteric_analysis.get("mid_spread", {}).get("signal") == "GOLDILOCKS",
            trap_active=esoteric_analysis.get("trap", {}).get("is_trap", False),
            confluence_level=esoteric_analysis.get("confluence", {}).get("level", "AVOID"),
            confluence_score=esoteric_analysis.get("confluence", {}).get("confluence_score", 0),
            astro_score=esoteric_analysis.get("astro", {}).get("overall_score", 50),
            planetary_hour_ruler=esoteric_analysis.get("astro", {}).get("planetary_hour", {}).get("hour_ruler", "Unknown"),
            nakshatra=esoteric_analysis.get("astro", {}).get("nakshatra", {}).get("nakshatra_name", "Unknown"),
            mercury_retrograde=esoteric_analysis.get("astro", {}).get("retrogrades", {}).get("mercury", {}).get("is_retrograde", False),

            total_esoteric_score=esoteric_analysis.get("total_score", 5.0),
            blended_probability=esoteric_analysis.get("blended", {}).get("blended_probability", 50),
            bet_tier=esoteric_analysis.get("tier", {}).get("tier", "PASS")
        )

        self.picks.append(record)
        self._save_state()

        logger.info("Logged esoteric pick: %s", pick_id)
        return pick_id

    def grade_pick(self, pick_id: str, result: str) -> Optional[Dict[str, Any]]:
        """
        Grade a pick and update performance tracking.

        result: WIN, LOSS, or PUSH
        """
        result = result.upper()
        if result not in ["WIN", "LOSS", "PUSH"]:
            return {"error": f"Invalid result: {result}. Use WIN, LOSS, or PUSH."}

        # Find the pick
        for pick in self.picks:
            if pick.pick_id == pick_id:
                pick.actual_result = result
                pick.graded_at = datetime.now().isoformat()

                # Update performance tracking
                self._update_performance(pick)
                self._save_state()

                return {
                    "pick_id": pick_id,
                    "result": result,
                    "graded_at": pick.graded_at,
                    "signals_that_fired": self._get_active_signals(pick),
                    "confluence_level": pick.confluence_level,
                    "bet_tier": pick.bet_tier
                }

        return {"error": f"Pick not found: {pick_id}"}

    def _get_active_signals(self, pick: EsotericPickRecord) -> List[str]:
        """Get list of signals that were active for a pick."""
        signals = []

        if pick.gematria_signal in ["STRONG", "MODERATE"]:
            signals.append(f"GEMATRIA_{pick.gematria_signal}")
        if pick.public_fade_active:
            signals.append("PUBLIC_FADE")
        if pick.goldilocks_active:
            signals.append("GOLDILOCKS")
        if not pick.trap_active:
            signals.append("NO_TRAP")
        if pick.astro_score >= 60:
            signals.append("ASTRO_FAVORABLE")
        if pick.confluence_level in ["GODMODE", "LEGENDARY", "STRONG"]:
            signals.append(f"CONFLUENCE_{pick.confluence_level}")
        if pick.mercury_retrograde:
            signals.append("MERCURY_RETROGRADE")

        return signals

    def _update_performance(self, pick: EsotericPickRecord):
        """Update performance tracking for all active signals."""
        signals = self._get_active_signals(pick)
        result = pick.actual_result

        # Update global performance
        if result == "WIN":
            self.performance["global"]["wins"] += 1
        elif result == "LOSS":
            self.performance["global"]["losses"] += 1
        else:
            self.performance["global"]["pushes"] += 1

        # Update per-signal performance
        for signal in signals:
            if result == "WIN":
                self.performance[signal]["wins"] += 1
            elif result == "LOSS":
                self.performance[signal]["losses"] += 1
            else:
                self.performance[signal]["pushes"] += 1

        # Update by confluence level
        level_key = f"LEVEL_{pick.confluence_level}"
        if result == "WIN":
            self.performance[level_key]["wins"] += 1
        elif result == "LOSS":
            self.performance[level_key]["losses"] += 1
        else:
            self.performance[level_key]["pushes"] += 1

        # Update by bet tier
        tier_key = f"TIER_{pick.bet_tier}"
        if result == "WIN":
            self.performance[tier_key]["wins"] += 1
        elif result == "LOSS":
            self.performance[tier_key]["losses"] += 1
        else:
            self.performance[tier_key]["pushes"] += 1

    def get_performance(self, days_back: int = 30) -> Dict[str, Any]:
        """Get performance summary."""
        cutoff = datetime.now() - timedelta(days=days_back)

        # Filter picks by date
        recent_picks = [
            p for p in self.picks
            if p.actual_result and datetime.fromisoformat(p.timestamp) >= cutoff
        ]

        # Calculate summary
        summary = {
            "days_analyzed": days_back,
            "total_picks": len(recent_picks),
            "graded_picks": sum(1 for p in recent_picks if p.actual_result),
        }

        # Overall record
        wins = sum(1 for p in recent_picks if p.actual_result == "WIN")
        losses = sum(1 for p in recent_picks if p.actual_result == "LOSS")
        pushes = sum(1 for p in recent_picks if p.actual_result == "PUSH")

        total = wins + losses
        hit_rate = (wins / total * 100) if total > 0 else 0

        summary["overall"] = {
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "hit_rate": round(hit_rate, 1),
            "is_profitable": hit_rate > 52.38  # Break-even at -110
        }

        # Performance by signal
        signal_performance = {}
        for signal, data in self.performance.items():
            if signal.startswith("global"):
                continue
            total = data["wins"] + data["losses"]
            if total > 0:
                signal_performance[signal] = {
                    "wins": data["wins"],
                    "losses": data["losses"],
                    "pushes": data["pushes"],
                    "hit_rate": round(data["wins"] / total * 100, 1),
                    "sample_size": total
                }

        summary["by_signal"] = signal_performance

        return summary

    def adjust_weights(self, learning_rate: float = 0.05) -> Dict[str, Any]:
        """
        Adjust signal weights based on historical performance.

        Uses gradient-based adjustment:
        - Increase weights for signals with hit rate > 55%
        - Decrease weights for signals with hit rate < 48%
        - Keep stable for signals in 48-55% range
        """
        adjustments = {}

        # Signal to weight mapping
        signal_weight_map = {
            "GEMATRIA_STRONG": "gematria",
            "GEMATRIA_MODERATE": "gematria",
            "ASTRO_FAVORABLE": "astro",
            "CONFLUENCE_GODMODE": "gematria",  # Confluence boosts gematria
            "CONFLUENCE_LEGENDARY": "gematria",
            "MERCURY_RETROGRADE": "astro",
        }

        for signal, weight_key in signal_weight_map.items():
            if signal not in self.performance:
                continue

            data = self.performance[signal]
            total = data["wins"] + data["losses"]

            if total < 10:  # Minimum sample size
                continue

            hit_rate = data["wins"] / total
            current_weight = self.weights.get(weight_key, 0.10)

            # Calculate adjustment
            if hit_rate > 0.55:
                delta = learning_rate * (hit_rate - 0.50)
            elif hit_rate < 0.48:
                delta = -learning_rate * (0.50 - hit_rate)
            else:
                delta = 0.0

            # Apply bounds
            new_weight = max(0.05, min(0.55, current_weight + delta))

            if abs(delta) > 0.001:
                adjustments[weight_key] = {
                    "signal": signal,
                    "old_weight": current_weight,
                    "delta": round(delta, 4),
                    "new_weight": round(new_weight, 4),
                    "hit_rate": round(hit_rate * 100, 1),
                    "sample_size": total
                }
                self.weights[weight_key] = new_weight

        # Normalize weights to sum to 1.0
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            for key in self.weights:
                self.weights[key] = round(self.weights[key] / total_weight, 4)

        self._save_state()

        return {
            "adjustments": adjustments,
            "new_weights": dict(self.weights),
            "learning_rate": learning_rate,
            "timestamp": datetime.now().isoformat()
        }

    def get_weights(self) -> Dict[str, Any]:
        """Get current learned weights."""
        return {
            "weights": dict(self.weights),
            "default_weights": dict(self.DEFAULT_WEIGHTS),
            "is_learned": self.weights != self.DEFAULT_WEIGHTS,
            "timestamp": datetime.now().isoformat()
        }

    def get_recent_picks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent picks for review."""
        sorted_picks = sorted(self.picks, key=lambda p: p.timestamp, reverse=True)[:limit]
        return [asdict(p) for p in sorted_picks]


# ============================================================================
# COMBINED ENGINE (SINGLETON)
# ============================================================================

_jarvis_engine: Optional[JarvisSavantEngine] = None
_vedic_engine: Optional[VedicAstroEngine] = None
_learning_loop: Optional[EsotericLearningLoop] = None


def get_jarvis_engine() -> JarvisSavantEngine:
    """Get singleton JarvisSavantEngine."""
    global _jarvis_engine
    if _jarvis_engine is None:
        _jarvis_engine = JarvisSavantEngine()
    return _jarvis_engine


def get_vedic_engine() -> VedicAstroEngine:
    """Get singleton VedicAstroEngine."""
    global _vedic_engine
    if _vedic_engine is None:
        _vedic_engine = VedicAstroEngine()
    return _vedic_engine


def get_learning_loop() -> EsotericLearningLoop:
    """Get singleton EsotericLearningLoop."""
    global _learning_loop
    if _learning_loop is None:
        _learning_loop = EsotericLearningLoop()
    return _learning_loop


def calculate_full_esoteric_analysis(
    player: str,
    team: str,
    opponent: str,
    spread: float = 0,
    total: float = 220,
    public_pct: float = 50,
    model_probability: float = 50,
    sharp_signal: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Calculate complete esoteric analysis using all Phase 1-3 components.

    Returns a comprehensive analysis dict.
    """
    jarvis = get_jarvis_engine()
    vedic = get_vedic_engine()
    learning = get_learning_loop()

    # Phase 1: Confluence Core
    gematria = jarvis.calculate_gematria_signal(player, team, opponent)
    public_fade = jarvis.calculate_public_fade_signal(public_pct)
    mid_spread = jarvis.calculate_mid_spread_signal(spread)
    trap = jarvis.calculate_large_spread_trap(spread, total)

    # Phase 2: Vedic/Astro
    astro = vedic.calculate_astro_score()

    # Confluence calculation
    confluence = jarvis.calculate_confluence(
        gematria_signal=gematria,
        public_fade=public_fade,
        mid_spread=mid_spread,
        trap_signal=trap,
        astro_score=astro,
        sharp_signal=sharp_signal
    )

    # Calculate total esoteric score (0-10)
    weights = learning.get_weights()["weights"]

    esoteric_score = 5.0  # Base score
    esoteric_score += (gematria["signal_strength"] * 2 * weights.get("gematria", 0.40))
    esoteric_score += (astro["overall_score"] / 100 * 2 * weights.get("astro", 0.13))
    esoteric_score += (confluence["confluence_score"] / 100 * 2)

    if public_fade["is_crush_zone"]:
        esoteric_score += 0.5
    if mid_spread["signal"] == "GOLDILOCKS":
        esoteric_score += 0.5
    if trap["is_trap"]:
        esoteric_score -= 1.0

    esoteric_score = max(0, min(10, esoteric_score))

    # Blended probability
    blended = jarvis.calculate_blended_probability(model_probability, esoteric_score)

    # Bet tier
    tier = jarvis.determine_bet_tier(confluence, blended, esoteric_score)

    return {
        "gematria": gematria,
        "public_fade": public_fade,
        "mid_spread": mid_spread,
        "trap": trap,
        "astro": astro,
        "confluence": confluence,
        "total_score": round(esoteric_score, 2),
        "blended": blended,
        "tier": tier,
        "weights_used": weights,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("JARVIS SAVANT ENGINE v7.3 - TESTING")
    print("=" * 70)

    # Test Phase 1
    print("\n[PHASE 1: CONFLUENCE CORE]")
    jarvis = JarvisSavantEngine()

    # Test 2178 validation
    print("\n2178 Validation:")
    validation = jarvis.validate_2178()
    print(f"  Is Immortal: {validation['is_immortal']}")
    print(f"  Proof: {validation['proof']}")

    # Test trigger detection
    print("\nTrigger Detection:")
    trigger = jarvis.check_jarvis_trigger(2178)
    print(f"  Triggers Hit: {trigger['triggers_hit']}")
    print(f"  Total Boost: {trigger['total_boost']}")

    # Test gematria
    print("\nGematria Signal:")
    gematria = jarvis.calculate_gematria_signal("LeBron James", "Lakers", "Celtics")
    print(f"  Signal: {gematria['signal']}")
    print(f"  Weight: {gematria['weight']}")

    # Test Phase 2
    print("\n[PHASE 2: VEDIC/ASTRO]")
    vedic = VedicAstroEngine()

    print("\nPlanetary Hour:")
    hour = vedic.calculate_planetary_hour()
    print(f"  Day Ruler: {hour['day_ruler']}")
    print(f"  Hour Ruler: {hour['hour_ruler']}")
    print(f"  Favorable: {hour['is_favorable']}")

    print("\nNakshatra:")
    nakshatra = vedic.calculate_nakshatra()
    print(f"  Name: {nakshatra['nakshatra_name']}")
    print(f"  Nature: {nakshatra['nature']}")

    print("\nRetrograde Check:")
    retro = vedic.is_planet_retrograde("Mercury")
    print(f"  Mercury Retrograde: {retro['is_retrograde']}")

    print("\nAstro Score:")
    astro = vedic.calculate_astro_score()
    print(f"  Overall Score: {astro['overall_score']}")
    print(f"  Rating: {astro['rating']}")

    # Test Phase 3
    print("\n[PHASE 3: LEARNING LOOP]")
    learning = EsotericLearningLoop()

    print("\nCurrent Weights:")
    weights = learning.get_weights()
    for key, val in weights["weights"].items():
        print(f"  {key}: {val}")

    print("\nPerformance Summary:")
    perf = learning.get_performance()
    print(f"  Total Picks: {perf['total_picks']}")
    print(f"  Overall Record: {perf['overall']}")

    # Test full analysis
    print("\n[FULL ESOTERIC ANALYSIS]")
    analysis = calculate_full_esoteric_analysis(
        player="LeBron James",
        team="Lakers",
        opponent="Celtics",
        spread=-3.5,
        total=225,
        public_pct=72,
        model_probability=58
    )

    print(f"\n  Total Esoteric Score: {analysis['total_score']}/10")
    print(f"  Confluence Level: {analysis['confluence']['level']}")
    print(f"  Blended Probability: {analysis['blended']['blended_probability']}%")
    print(f"  Bet Tier: {analysis['tier']['tier']}")
    print(f"  Action: {analysis['tier']['explanation']}")

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)
