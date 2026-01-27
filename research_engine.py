"""
RESEARCH ENGINE v1.0 - ALL MARKET PILLARS
==========================================
Production hardened research scoring engine with ALL market pillars.

This engine is responsible for:
- Public Fade (>= 70% threshold) - MOVED FROM JARVIS
- Mid-Spread/Goldilocks zone - MOVED FROM JARVIS
- Trap Gates - MOVED FROM JARVIS
- Sharp split / sharp money / handle vs tickets
- Reverse Line Movement (RLM)
- Hook discipline
- Hospital fade
- Multi-pillar confluence

Output: research_score (0-10), research_reasons[], pillars_fired[]

IMPORTANT: This is the ONLY place market pillars should be calculated.
No double-counting with Esoteric or Jarvis engines.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

# Configure logging
logger = logging.getLogger("research_engine")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)


# =============================================================================
# ENGINE VERSION
# =============================================================================
ENGINE_VERSION = "1.0"


# =============================================================================
# PILLAR WEIGHTS
# =============================================================================

PILLAR_WEIGHTS = {
    "sharp_split": 0.20,           # 20% - Sharp money analysis
    "reverse_line_move": 0.15,     # 15% - RLM detection
    "public_fade": 0.15,           # 15% - Public fade signal
    "hook_discipline": 0.10,       # 10% - Hook/line value
    "goldilocks_zone": 0.15,       # 15% - Mid-spread analysis
    "hospital_fade": 0.10,         # 10% - Injury impact
    "trap_gate": 0.10,             # 10% - Large spread trap
    "multi_pillar": 0.05,          # 5% - Confluence bonus
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PillarResult:
    """Result from a single pillar analysis."""
    name: str
    fired: bool
    score: float  # 0-10 scale
    weight: float
    reason: str
    signal: str  # STRONG, MODERATE, WEAK, NEUTRAL, NEGATIVE


@dataclass
class ResearchResult:
    """Complete research engine output."""
    research_score: float
    research_reasons: List[str]
    pillars_fired: List[str]
    pillar_details: List[Dict[str, Any]]
    confluence_level: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "research_score": round(self.research_score, 2),
            "research_reasons": self.research_reasons,
            "pillars_fired": self.pillars_fired,
            "pillar_details": self.pillar_details,
            "confluence_level": self.confluence_level
        }


# =============================================================================
# PILLAR 1: PUBLIC FADE (MOVED FROM JARVIS)
# =============================================================================

def calculate_public_fade_signal(public_pct: float) -> Dict[str, Any]:
    """
    Calculate public fade signal with graduated adjustments.

    PUBLIC FADE CRUSH ZONE (v12.0 spec):
    >= 80% public on chalk  ->  -0.95 influence (FADE strongly)
    >= 75% public on chalk  ->  -0.85 influence
    >= 70% public on chalk  ->  -0.75 influence (threshold for FADE)
    >= 65% public on chalk  ->  -0.65 influence

    THIS SIGNAL BELONGS TO RESEARCH ENGINE ONLY.
    """
    if public_pct >= 80:
        signal = "FADE_PUBLIC"
        adjustment = -0.95
        is_crush_zone = True
        score = 8.5  # Strong fade signal = high research score
        explanation = f"Public at {public_pct}% - MAXIMUM CRUSH ZONE. Strong fade."
    elif public_pct >= 75:
        signal = "FADE_PUBLIC"
        adjustment = -0.85
        is_crush_zone = True
        score = 7.5
        explanation = f"Public at {public_pct}% - HIGH CRUSH ZONE. Fade recommended."
    elif public_pct >= 70:
        signal = "FADE_PUBLIC"
        adjustment = -0.75
        is_crush_zone = True
        score = 7.0
        explanation = f"Public at {public_pct}% - CRUSH ZONE threshold. Fade the public side."
    elif public_pct >= 65:
        signal = "FADE_PUBLIC"
        adjustment = -0.65
        is_crush_zone = True
        score = 6.0
        explanation = f"Public at {public_pct}% - EARLY CRUSH. Consider fading."
    elif public_pct <= 20:
        signal = "FOLLOW_PUBLIC"
        adjustment = 0.20
        is_crush_zone = True
        score = 8.0
        explanation = f"Public at {public_pct}% - Extreme contrarian. Public side has value."
    elif public_pct <= 25:
        signal = "FOLLOW_PUBLIC"
        adjustment = 0.15
        is_crush_zone = True
        score = 7.5
        explanation = f"Public at {public_pct}% - Strong contrarian value."
    elif public_pct <= 30:
        signal = "LEAN_PUBLIC"
        adjustment = 0.10
        is_crush_zone = False
        score = 6.5
        explanation = f"Public at {public_pct}% - Contrarian lean."
    else:
        signal = "NEUTRAL"
        adjustment = 0.0
        is_crush_zone = False
        score = 5.0
        explanation = f"Public at {public_pct}% - No strong fade signal."

    return {
        "public_pct": public_pct,
        "is_crush_zone": is_crush_zone,
        "signal": signal,
        "adjustment": adjustment,
        "influence": adjustment,
        "score": score,
        "explanation": explanation,
        "fired": is_crush_zone
    }


# =============================================================================
# PILLAR 2: MID-SPREAD / GOLDILOCKS ZONE (MOVED FROM JARVIS)
# =============================================================================

def calculate_goldilocks_signal(spread: float) -> Dict[str, Any]:
    """
    Calculate mid-spread (Goldilocks zone) signal.

    Goldilocks zone (spread between +4 and +9) = most predictable range.
    THIS SIGNAL BELONGS TO RESEARCH ENGINE ONLY.
    """
    abs_spread = abs(spread) if spread else 0

    if 4 <= abs_spread <= 9:
        signal = "GOLDILOCKS"
        score = 8.0
        adjustment = 0.20
        explanation = f"Spread {spread} in Goldilocks zone (+4 to +9). Most predictable range."
        fired = True
    elif abs_spread < 4:
        signal = "PICKEM"
        score = 5.0
        adjustment = 0.0
        explanation = f"Spread {spread} is pick'em territory. High variance."
        fired = False
    elif abs_spread >= 14:
        signal = "TRAP_ZONE"
        score = 3.0
        adjustment = -0.20
        explanation = f"Spread {spread} in trap zone. Fade large favorites."
        fired = False
    elif abs_spread > 9:
        signal = "BLOWOUT"
        score = 4.0
        adjustment = -0.10
        explanation = f"Spread {spread} indicates potential blowout. Garbage time risk."
        fired = False
    else:
        signal = "STANDARD"
        score = 5.5
        adjustment = 0.05
        explanation = f"Spread {spread} in standard range."
        fired = False

    return {
        "spread": spread,
        "abs_spread": abs_spread,
        "signal": signal,
        "score": score,
        "adjustment": adjustment,
        "modifier": adjustment,
        "explanation": explanation,
        "fired": fired
    }


# =============================================================================
# PILLAR 3: TRAP GATE (MOVED FROM JARVIS)
# =============================================================================

def calculate_trap_gate_signal(spread: float, total: float = 220) -> Dict[str, Any]:
    """
    Calculate large spread trap signal.

    -20% trap gate for spreads > 14 (likely trap games).
    THIS SIGNAL BELONGS TO RESEARCH ENGINE ONLY.
    """
    abs_spread = abs(spread) if spread else 0

    if abs_spread >= 14:
        signal = "TRAP_GATE"
        score = 3.0
        adjustment = -0.20
        is_trap = True
        explanation = f"Spread {spread} > 14. TRAP GATE active. Large favorites cover < 50% historically."
    elif abs_spread >= 10:
        signal = "CAUTION"
        score = 4.5
        adjustment = -0.10
        is_trap = False
        explanation = f"Spread {spread} in caution zone. Monitor for trap."
    else:
        signal = "CLEAR"
        score = 5.5
        adjustment = 0.0
        is_trap = False
        explanation = f"Spread {spread} not in trap territory."

    return {
        "spread": spread,
        "abs_spread": abs_spread,
        "total": total,
        "signal": signal,
        "score": score,
        "adjustment": adjustment,
        "is_trap": is_trap,
        "explanation": explanation,
        "fired": is_trap
    }


# =============================================================================
# PILLAR 4: SHARP SPLIT / SHARP MONEY
# =============================================================================

def calculate_sharp_split_signal(
    sharp_money_pct: float = 50,
    public_money_pct: float = 50,
    handle_pct: float = 50,
    tickets_pct: float = 50
) -> Dict[str, Any]:
    """
    Calculate sharp split signal.

    Sharp money signal fires when:
    - Sharp money > 60% on one side
    - OR Handle% significantly differs from Tickets% (professional vs recreational)
    """
    # Handle vs tickets divergence (sharps bet larger amounts)
    divergence = abs(handle_pct - tickets_pct)

    # Sharp money threshold
    sharp_threshold = 60

    if sharp_money_pct >= 70:
        signal = "SHARP_HEAVY"
        score = 9.0
        explanation = f"Sharp money at {sharp_money_pct}% - Heavy sharp action."
        fired = True
    elif sharp_money_pct >= sharp_threshold:
        signal = "SHARP_LEAN"
        score = 7.5
        explanation = f"Sharp money at {sharp_money_pct}% - Sharp lean detected."
        fired = True
    elif divergence >= 15:
        # Handle > Tickets = sharps (larger bets), Tickets > Handle = public
        if handle_pct > tickets_pct:
            signal = "SHARP_DIVERGENCE"
            score = 7.0
            explanation = f"Handle/Ticket divergence {divergence}% - Sharps loading."
            fired = True
        else:
            signal = "PUBLIC_DIVERGENCE"
            score = 4.0
            explanation = f"Handle/Ticket divergence {divergence}% - Public heavy."
            fired = False
    else:
        signal = "NEUTRAL"
        score = 5.0
        explanation = "No significant sharp signal."
        fired = False

    return {
        "sharp_money_pct": sharp_money_pct,
        "public_money_pct": public_money_pct,
        "handle_pct": handle_pct,
        "tickets_pct": tickets_pct,
        "divergence": divergence,
        "signal": signal,
        "score": score,
        "explanation": explanation,
        "fired": fired
    }


# =============================================================================
# PILLAR 5: REVERSE LINE MOVEMENT (RLM)
# =============================================================================

def calculate_rlm_signal(
    opening_line: float,
    current_line: float,
    public_side: str,
    movement_direction: str = None
) -> Dict[str, Any]:
    """
    Calculate Reverse Line Movement signal.

    RLM fires when:
    - Line moves AGAINST public betting
    - Example: Public on Lakers -3, line moves to Lakers -2.5
    """
    line_movement = current_line - opening_line

    if line_movement == 0:
        return {
            "opening_line": opening_line,
            "current_line": current_line,
            "line_movement": 0,
            "signal": "NO_MOVEMENT",
            "score": 5.0,
            "explanation": "No line movement.",
            "fired": False
        }

    # Determine if movement is against public
    # Negative movement = line getting smaller (less favorite)
    # If public on favorite and line shrinks = RLM (sharps on underdog)
    public_on_favorite = public_side.upper() in ["FAVORITE", "FAV", "CHALK"]

    if public_on_favorite and line_movement < 0:
        # Line moving toward underdog despite public on favorite = RLM
        signal = "RLM_CONFIRMED"
        score = 8.5
        explanation = f"RLM: Line moved {line_movement} against public favorite action."
        fired = True
    elif not public_on_favorite and line_movement > 0:
        # Line moving toward favorite despite public on underdog = RLM
        signal = "RLM_CONFIRMED"
        score = 8.5
        explanation = f"RLM: Line moved {line_movement} against public underdog action."
        fired = True
    elif abs(line_movement) >= 2:
        signal = "SIGNIFICANT_MOVEMENT"
        score = 6.5
        explanation = f"Significant line movement: {line_movement}"
        fired = False
    else:
        signal = "MINOR_MOVEMENT"
        score = 5.0
        explanation = f"Minor line movement: {line_movement}"
        fired = False

    return {
        "opening_line": opening_line,
        "current_line": current_line,
        "line_movement": line_movement,
        "public_side": public_side,
        "signal": signal,
        "score": score,
        "explanation": explanation,
        "fired": fired
    }


# =============================================================================
# PILLAR 6: HOOK DISCIPLINE
# =============================================================================

def calculate_hook_discipline_signal(
    line: float,
    is_spread: bool = True
) -> Dict[str, Any]:
    """
    Calculate hook discipline signal.

    Key numbers in NFL/NCAAB: 3, 7
    Key numbers in NBA: 1, 2, 3, 4, 5, 6, 7

    Hook = 0.5 difference from key number
    """
    abs_line = abs(line) if line else 0

    # Key numbers
    nfl_key = [3, 7, 10, 14, 17, 21]
    nba_key = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    # Check for hook value (0.5 off key number)
    on_key_number = any(abs(abs_line - k) == 0 for k in nfl_key)
    has_hook = abs_line % 1 == 0.5
    near_key = any(abs(abs_line - k) <= 0.5 for k in nfl_key)

    if on_key_number:
        signal = "KEY_NUMBER"
        score = 7.0
        explanation = f"Line {line} is on a key number."
        fired = True
    elif has_hook and near_key:
        signal = "HOOK_VALUE"
        score = 7.5
        explanation = f"Line {line} has hook value near key number."
        fired = True
    elif has_hook:
        signal = "HAS_HOOK"
        score = 6.0
        explanation = f"Line {line} has hook but not near key number."
        fired = False
    else:
        signal = "NO_HOOK"
        score = 5.0
        explanation = f"Line {line} - no hook discipline signal."
        fired = False

    return {
        "line": line,
        "abs_line": abs_line,
        "on_key_number": on_key_number,
        "has_hook": has_hook,
        "signal": signal,
        "score": score,
        "explanation": explanation,
        "fired": fired
    }


# =============================================================================
# PILLAR 7: HOSPITAL FADE
# =============================================================================

def calculate_hospital_fade_signal(
    injury_impact_pct: float = 0,
    key_player_out: bool = False,
    injury_count: int = 0
) -> Dict[str, Any]:
    """
    Calculate hospital fade signal based on injury impact.

    Hospital fade fires when:
    - Key player OUT
    - OR injury impact > 15%
    """
    if key_player_out:
        signal = "KEY_PLAYER_OUT"
        score = 8.5
        explanation = "Key player OUT - significant fade signal."
        fired = True
    elif injury_impact_pct >= 20:
        signal = "HEAVY_INJURIES"
        score = 8.0
        explanation = f"Injury impact {injury_impact_pct}% - fade heavily."
        fired = True
    elif injury_impact_pct >= 15:
        signal = "MODERATE_INJURIES"
        score = 7.0
        explanation = f"Injury impact {injury_impact_pct}% - consider fade."
        fired = True
    elif injury_impact_pct >= 10:
        signal = "MINOR_INJURIES"
        score = 6.0
        explanation = f"Injury impact {injury_impact_pct}% - monitor situation."
        fired = False
    else:
        signal = "HEALTHY"
        score = 5.0
        explanation = "No significant injury impact."
        fired = False

    return {
        "injury_impact_pct": injury_impact_pct,
        "key_player_out": key_player_out,
        "injury_count": injury_count,
        "signal": signal,
        "score": score,
        "explanation": explanation,
        "fired": fired
    }


# =============================================================================
# PILLAR 8: MULTI-PILLAR CONFLUENCE
# =============================================================================

def calculate_multi_pillar_confluence(
    pillars_fired: List[str],
    pillar_scores: Dict[str, float]
) -> Dict[str, Any]:
    """
    Calculate multi-pillar confluence bonus.

    Confluence levels:
    - 5+ pillars fired = PERFECT STORM (bonus +2.0)
    - 4 pillars fired = STRONG (bonus +1.5)
    - 3 pillars fired = MODERATE (bonus +1.0)
    - 2 pillars fired = SLIGHT (bonus +0.5)
    - 1 or fewer = NO CONFLUENCE (no bonus)
    """
    count = len(pillars_fired)
    avg_score = sum(pillar_scores.values()) / len(pillar_scores) if pillar_scores else 5.0

    if count >= 5:
        confluence_level = "PERFECT_STORM"
        bonus = 2.0
        explanation = f"{count} pillars aligned - PERFECT STORM!"
    elif count >= 4:
        confluence_level = "STRONG"
        bonus = 1.5
        explanation = f"{count} pillars aligned - Strong confluence."
    elif count >= 3:
        confluence_level = "MODERATE"
        bonus = 1.0
        explanation = f"{count} pillars aligned - Moderate confluence."
    elif count >= 2:
        confluence_level = "SLIGHT"
        bonus = 0.5
        explanation = f"{count} pillars aligned - Slight confluence."
    else:
        confluence_level = "NONE"
        bonus = 0.0
        explanation = "Insufficient pillar alignment."

    return {
        "pillars_fired_count": count,
        "pillars_fired": pillars_fired,
        "average_pillar_score": round(avg_score, 2),
        "confluence_level": confluence_level,
        "bonus": bonus,
        "explanation": explanation
    }


# =============================================================================
# MAIN RESEARCH ENGINE CLASS
# =============================================================================

class ResearchEngine:
    """
    Research Engine - ALL market pillars for betting analysis.

    This is the ONLY place market pillar calculations should occur.
    """

    VERSION = ENGINE_VERSION

    def __init__(self):
        self.weights = PILLAR_WEIGHTS
        logger.info("ResearchEngine v%s initialized", self.VERSION)

    def calculate_research_score(
        self,
        # Public/sharp data
        public_pct: float = 50,
        sharp_money_pct: float = 50,
        handle_pct: float = 50,
        tickets_pct: float = 50,
        # Line data
        spread: float = 0,
        total: float = 220,
        opening_line: float = None,
        current_line: float = None,
        public_side: str = "NEUTRAL",
        # Injury data
        injury_impact_pct: float = 0,
        key_player_out: bool = False,
        injury_count: int = 0,
        # Optional context
        sport: str = "NBA"
    ) -> ResearchResult:
        """
        Calculate comprehensive research score using all 8 pillars.

        Returns:
            ResearchResult with score, reasons, and pillar details
        """
        pillar_results = []
        pillar_scores = {}
        pillars_fired = []
        reasons = []

        # Opening line defaults to current if not provided
        if opening_line is None:
            opening_line = spread
        if current_line is None:
            current_line = spread

        # =====================================================================
        # PILLAR 1: Public Fade
        # =====================================================================
        public_fade = calculate_public_fade_signal(public_pct)
        pillar_scores["public_fade"] = public_fade["score"]
        if public_fade["fired"]:
            pillars_fired.append("PUBLIC_FADE")
            reasons.append(public_fade["explanation"])
        pillar_results.append({
            "pillar": "PUBLIC_FADE",
            "weight": self.weights["public_fade"],
            **public_fade
        })

        # =====================================================================
        # PILLAR 2: Goldilocks Zone (Mid-Spread)
        # =====================================================================
        goldilocks = calculate_goldilocks_signal(spread)
        pillar_scores["goldilocks_zone"] = goldilocks["score"]
        if goldilocks["fired"]:
            pillars_fired.append("GOLDILOCKS_ZONE")
            reasons.append(goldilocks["explanation"])
        pillar_results.append({
            "pillar": "GOLDILOCKS_ZONE",
            "weight": self.weights["goldilocks_zone"],
            **goldilocks
        })

        # =====================================================================
        # PILLAR 3: Trap Gate
        # =====================================================================
        trap_gate = calculate_trap_gate_signal(spread, total)
        pillar_scores["trap_gate"] = trap_gate["score"]
        if trap_gate["fired"]:
            pillars_fired.append("TRAP_GATE")
            reasons.append(trap_gate["explanation"])
        pillar_results.append({
            "pillar": "TRAP_GATE",
            "weight": self.weights["trap_gate"],
            **trap_gate
        })

        # =====================================================================
        # PILLAR 4: Sharp Split
        # =====================================================================
        sharp_split = calculate_sharp_split_signal(
            sharp_money_pct, 100 - sharp_money_pct, handle_pct, tickets_pct
        )
        pillar_scores["sharp_split"] = sharp_split["score"]
        if sharp_split["fired"]:
            pillars_fired.append("SHARP_SPLIT")
            reasons.append(sharp_split["explanation"])
        pillar_results.append({
            "pillar": "SHARP_SPLIT",
            "weight": self.weights["sharp_split"],
            **sharp_split
        })

        # =====================================================================
        # PILLAR 5: Reverse Line Movement
        # =====================================================================
        rlm = calculate_rlm_signal(opening_line, current_line, public_side)
        pillar_scores["reverse_line_move"] = rlm["score"]
        if rlm["fired"]:
            pillars_fired.append("REVERSE_LINE_MOVE")
            reasons.append(rlm["explanation"])
        pillar_results.append({
            "pillar": "REVERSE_LINE_MOVE",
            "weight": self.weights["reverse_line_move"],
            **rlm
        })

        # =====================================================================
        # PILLAR 6: Hook Discipline
        # =====================================================================
        hook = calculate_hook_discipline_signal(spread, is_spread=True)
        pillar_scores["hook_discipline"] = hook["score"]
        if hook["fired"]:
            pillars_fired.append("HOOK_DISCIPLINE")
            reasons.append(hook["explanation"])
        pillar_results.append({
            "pillar": "HOOK_DISCIPLINE",
            "weight": self.weights["hook_discipline"],
            **hook
        })

        # =====================================================================
        # PILLAR 7: Hospital Fade
        # =====================================================================
        hospital = calculate_hospital_fade_signal(injury_impact_pct, key_player_out, injury_count)
        pillar_scores["hospital_fade"] = hospital["score"]
        if hospital["fired"]:
            pillars_fired.append("HOSPITAL_FADE")
            reasons.append(hospital["explanation"])
        pillar_results.append({
            "pillar": "HOSPITAL_FADE",
            "weight": self.weights["hospital_fade"],
            **hospital
        })

        # =====================================================================
        # PILLAR 8: Multi-Pillar Confluence
        # =====================================================================
        confluence = calculate_multi_pillar_confluence(pillars_fired, pillar_scores)
        pillar_scores["multi_pillar"] = confluence["bonus"] * 2.5 + 5  # Scale bonus to score
        if confluence["bonus"] > 0:
            reasons.append(confluence["explanation"])
        pillar_results.append({
            "pillar": "MULTI_PILLAR_CONFLUENCE",
            "weight": self.weights["multi_pillar"],
            **confluence
        })

        # =====================================================================
        # CALCULATE FINAL RESEARCH SCORE
        # =====================================================================
        weighted_score = 0
        for pillar_name, score in pillar_scores.items():
            weight = self.weights.get(pillar_name, 0.1)
            weighted_score += score * weight

        # Add confluence bonus
        weighted_score += confluence["bonus"]

        # Clamp to 0-10
        final_score = max(0, min(10, weighted_score))

        # Generate summary reason
        if not reasons:
            reasons.append(f"Research score: {final_score:.1f}/10 (no major pillars fired)")
        else:
            reasons.insert(0, f"Research score: {final_score:.1f}/10 ({len(pillars_fired)} pillars fired)")

        return ResearchResult(
            research_score=final_score,
            research_reasons=reasons,
            pillars_fired=pillars_fired,
            pillar_details=pillar_results,
            confluence_level=confluence["confluence_level"]
        )


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_research_engine_instance = None


def get_research_engine() -> ResearchEngine:
    """Get or create singleton ResearchEngine instance."""
    global _research_engine_instance
    if _research_engine_instance is None:
        _research_engine_instance = ResearchEngine()
    return _research_engine_instance


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_research_score(
    public_pct: float = 50,
    sharp_money_pct: float = 50,
    spread: float = 0,
    total: float = 220,
    injury_impact_pct: float = 0,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to get research score.

    Returns dict with research_score, research_reasons, pillars_fired.
    """
    engine = get_research_engine()
    result = engine.calculate_research_score(
        public_pct=public_pct,
        sharp_money_pct=sharp_money_pct,
        spread=spread,
        total=total,
        injury_impact_pct=injury_impact_pct,
        **kwargs
    )
    return result.to_dict()


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RESEARCH ENGINE v1.0 - TEST")
    print("=" * 60)

    engine = get_research_engine()

    # Test 1: High public fade scenario
    print("\nTest 1: High Public Fade (80% public)")
    result = engine.calculate_research_score(
        public_pct=80,
        sharp_money_pct=65,
        spread=-5.5,
        total=220,
        injury_impact_pct=5
    )
    print(f"  Score: {result.research_score}")
    print(f"  Pillars: {result.pillars_fired}")
    print(f"  Confluence: {result.confluence_level}")

    # Test 2: Perfect storm scenario
    print("\nTest 2: Perfect Storm (multiple pillars)")
    result = engine.calculate_research_score(
        public_pct=75,
        sharp_money_pct=70,
        spread=-7,
        opening_line=-6,
        current_line=-7,
        public_side="UNDERDOG",
        injury_impact_pct=20,
        key_player_out=True
    )
    print(f"  Score: {result.research_score}")
    print(f"  Pillars: {result.pillars_fired}")
    print(f"  Confluence: {result.confluence_level}")

    # Test 3: Trap game scenario
    print("\nTest 3: Trap Game (large spread)")
    result = engine.calculate_research_score(
        public_pct=55,
        spread=-15.5,
        total=215
    )
    print(f"  Score: {result.research_score}")
    print(f"  Pillars: {result.pillars_fired}")

    print("\n" + "=" * 60)
    print("Tests complete!")
    print("=" * 60)
