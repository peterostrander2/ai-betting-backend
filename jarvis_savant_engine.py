"""
JARVIS SAVANT ENGINE v7.9 – STANDALONE JARVIS SCORING
Production-Clean Implementation – January 24, 2026

JARVIS ENGINE outputs ONLY:
- jarvis_rs (0-10): Ritual score
- jarvis_active (bool): Any trigger hit
- jarvis_hits_count (int): Number of triggers
- jarvis_triggers_hit (array): Trigger details
- jarvis_reasons (array): Explanation strings

JARVIS CONTAINS (exclusive to this engine):
- Gematria (dominant 52% weight)
- Sacred triggers: 2178, 201, 33, 47, 88, 93, 322
- Mid-spread amplifier (Goldilocks +4 to +9) - JARVIS ONLY
- Trap gate penalties (spread > 15) - JARVIS ONLY
- Boss instinct priority flags

JARVIS DOES NOT CONTAIN:
- Public Fade (lives in Research Engine)
- Vedic/Moon phase (lives in Esoteric Edge Engine)
- Sharp money/RLM (lives in Research Engine)

Author: Built with Boss through grind – standalone Jarvis.
"""

import logging
from typing import Dict, List, Any, Union, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# JARVIS TRIGGERS - THE PROVEN EDGE NUMBERS
# Weight: boost / 5 = max contribution to RS
# =============================================================================
JARVIS_TRIGGERS = {
    2178: {"name": "THE_IMMORTAL", "boost": 20, "tier": "LEGENDARY", "desc": "n × 4 = reverse(n). Digital root 9."},
    201: {"name": "THE_ORDER", "boost": 12, "tier": "HIGH", "desc": "Jesuit Order gematria."},
    33: {"name": "THE_MASTER", "boost": 10, "tier": "HIGH", "desc": "Highest master number."},
    47: {"name": "THE_AGENT", "boost": 8, "tier": "MEDIUM", "desc": "Agent of chaos. Discordian prime."},
    88: {"name": "THE_INFINITE", "boost": 8, "tier": "MEDIUM", "desc": "Double infinity. Cycle completion."},
    93: {"name": "THE_WILL", "boost": 10, "tier": "HIGH", "desc": "Thelema sacred number."},
    322: {"name": "THE_SOCIETY", "boost": 10, "tier": "HIGH", "desc": "Skull & Bones. Genesis 3:22."},
}

POWER_NUMBERS = [11, 22, 33, 44, 55, 66, 77, 88, 99]
TESLA_NUMBERS = [3, 6, 9]

# =============================================================================
# GEMATRIA CALCULATION
# =============================================================================
GEMATRIA_VALUES = {
    'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8, 'I': 9,
    'J': 10, 'K': 11, 'L': 12, 'M': 13, 'N': 14, 'O': 15, 'P': 16, 'Q': 17,
    'R': 18, 'S': 19, 'T': 20, 'U': 21, 'V': 22, 'W': 23, 'X': 24, 'Y': 25, 'Z': 26
}


def calculate_gematria(text: str) -> int:
    """Calculate simple gematria value for text."""
    if not text:
        return 0
    return sum(GEMATRIA_VALUES.get(c.upper(), 0) for c in text if c.isalpha())


def calculate_digital_root(n: int) -> int:
    """Calculate digital root (Tesla/Vortex math)."""
    if n == 0:
        return 0
    return 1 + (n - 1) % 9


def reduce_to_single_digit(n: int) -> int:
    """Reduce number to single digit."""
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


# =============================================================================
# SPORT PROFILES - JARVIS WEIGHTS ONLY
# =============================================================================
JARVIS_SPORT_WEIGHTS = {
    "nba": 0.20,    # Standard
    "nhl": 0.22,    # High variance sport
    "nfl": 0.17,    # Sharper lines
    "mlb": 0.15,    # Lowest Jarvis weight
    "ncaab": 0.22,  # College variance
}

JARVIS_VARIANCE_FACTORS = {
    "nba": 1.0,
    "nhl": 1.15,
    "nfl": 0.9,
    "mlb": 1.1,
    "ncaab": 1.2,
}


# =============================================================================
# JARVIS SAVANT ENGINE - STANDALONE
# =============================================================================
class JarvisSavantEngine:
    """
    JARVIS SAVANT ENGINE v7.9 - Standalone Ritual Scoring

    Outputs:
    - jarvis_rs (0-10)
    - jarvis_active (bool)
    - jarvis_hits_count (int)
    - jarvis_triggers_hit (array)
    - jarvis_reasons (array)
    """

    def __init__(self):
        self.version = "v7.9"
        self.triggers = JARVIS_TRIGGERS
        self.power_numbers = POWER_NUMBERS
        self.tesla_numbers = TESLA_NUMBERS

        # Jarvis-only weights (gematria dominant)
        self.gematria_weight = 0.52
        self.mid_spread_amplifier = 0.20  # Goldilocks zone (+4 to +9)
        self.trap_gate_penalty = -0.20    # Large spreads (>15)

    def check_jarvis_triggers(self, text: str) -> Dict[str, Any]:
        """
        Check text for JARVIS sacred trigger hits.

        Returns dict with: triggered, triggers_hit, total_boost
        """
        triggers_hit = []
        gematria_value = calculate_gematria(text)
        digital_root = calculate_digital_root(gematria_value)

        # Direct trigger matches (gematria value)
        if gematria_value in self.triggers:
            t = self.triggers[gematria_value]
            triggers_hit.append({
                "number": gematria_value,
                "name": t["name"],
                "boost": t["boost"],
                "match_type": "GEMATRIA_DIRECT",
            })

        # Check if gematria contains trigger numbers
        gem_str = str(gematria_value)
        for trigger_num, trigger_data in self.triggers.items():
            if str(trigger_num) in gem_str and trigger_num != gematria_value:
                triggers_hit.append({
                    "number": trigger_num,
                    "name": trigger_data["name"],
                    "boost": trigger_data["boost"] * 0.5,  # Partial match
                    "match_type": "CONTAINS",
                })

        # Check text for trigger number substrings
        text_digits = ''.join(c for c in text if c.isdigit())
        if text_digits:
            for trigger_num, trigger_data in self.triggers.items():
                if str(trigger_num) in text_digits:
                    triggers_hit.append({
                        "number": trigger_num,
                        "name": trigger_data["name"],
                        "boost": trigger_data["boost"] * 0.75,
                        "match_type": "TEXT_CONTAINS",
                    })

        # Power number check
        power_hits = [p for p in self.power_numbers if p == gematria_value]

        # Tesla alignment (digital root in 3, 6, 9)
        is_tesla = digital_root in self.tesla_numbers

        total_boost = sum(t["boost"] for t in triggers_hit)

        return {
            "triggered": len(triggers_hit) > 0 or is_tesla,
            "triggers_hit": triggers_hit,
            "triggers_count": len(triggers_hit),
            "total_boost": total_boost,
            "gematria_value": gematria_value,
            "digital_root": digital_root,
            "is_tesla_aligned": is_tesla,
            "power_numbers_hit": power_hits,
        }

    def calculate_jarvis_rs(
        self,
        matchup: str = "",
        player: str = "",
        team: str = "",
        opponent: str = "",
        spread: float = 0,
        gematria_hits: int = 0,
        sport: str = "nba",
    ) -> Dict[str, Any]:
        """
        Calculate JARVIS Ritual Score (0-10).

        This is the STANDALONE Jarvis engine output.

        Returns:
            {
                "jarvis_rs": float (0-10),
                "jarvis_active": bool,
                "jarvis_hits_count": int,
                "jarvis_triggers_hit": list,
                "jarvis_reasons": list
            }
        """
        variance_factor = JARVIS_VARIANCE_FACTORS.get(sport.lower(), 1.0)
        reasons = []

        # Base score
        rs = 5.0

        # =================================================================
        # GEMATRIA COMPONENT (dominant - 52% weight)
        # =================================================================
        # Check all text inputs for triggers
        combined_text = f"{matchup} {player} {team} {opponent}".strip()
        trigger_result = self.check_jarvis_triggers(combined_text)

        # Gematria hits from game data
        if gematria_hits >= 4:
            boost = 2.0 * variance_factor
            rs += boost
            reasons.append(f"JARVIS: Gematria 4+ alignments +{boost:.2f}")
        elif gematria_hits >= 3:
            boost = 1.5 * variance_factor
            rs += boost
            reasons.append(f"JARVIS: Gematria 3 alignments +{boost:.2f}")
        elif gematria_hits >= 2:
            boost = 0.8 * variance_factor
            rs += boost
            reasons.append(f"JARVIS: Gematria 2 alignments +{boost:.2f}")

        # =================================================================
        # SACRED TRIGGER BOOSTS
        # =================================================================
        for trigger in trigger_result["triggers_hit"]:
            boost = min(trigger["boost"] / 10, 1.5)  # Cap individual trigger
            rs += boost
            reasons.append(f"JARVIS: Trigger {trigger['number']} ({trigger['name']}) +{boost:.2f}")

        # Tesla alignment bonus
        if trigger_result["is_tesla_aligned"]:
            rs += 0.5
            reasons.append(f"JARVIS: Tesla aligned (root={trigger_result['digital_root']}) +0.50")

        # =================================================================
        # MID-SPREAD AMPLIFIER (Goldilocks zone - JARVIS ONLY)
        # =================================================================
        abs_spread = abs(spread)
        if 4 <= abs_spread <= 9:
            boost = self.mid_spread_amplifier * 10 * variance_factor
            rs += boost
            reasons.append(f"JARVIS: Goldilocks zone (spread {abs_spread}) +{boost:.2f}")

        # =================================================================
        # TRAP GATE PENALTY (JARVIS ONLY)
        # =================================================================
        if abs_spread > 15:
            penalty = abs(self.trap_gate_penalty) * 5
            rs -= penalty
            reasons.append(f"JARVIS: Trap gate (spread {abs_spread}) -{penalty:.2f}")

        # Clamp to 0-10
        rs = max(0.0, min(10.0, rs))

        return {
            "jarvis_rs": round(rs, 2),
            "jarvis_active": trigger_result["triggered"] or gematria_hits >= 2,
            "jarvis_hits_count": trigger_result["triggers_count"] + (1 if gematria_hits >= 2 else 0),
            "jarvis_triggers_hit": trigger_result["triggers_hit"],
            "jarvis_reasons": reasons,
            # Additional metadata
            "gematria_value": trigger_result["gematria_value"],
            "digital_root": trigger_result["digital_root"],
            "is_tesla_aligned": trigger_result["is_tesla_aligned"],
            "sport": sport.upper(),
            "variance_factor": variance_factor,
        }

    def validate_2178(self) -> Dict[str, Any]:
        """Validate 2178 as THE IMMORTAL number."""
        n = 2178
        reverse_n = 8712
        times_four = n * 4
        digital_root = calculate_digital_root(n)

        return {
            "number": n,
            "name": "THE_IMMORTAL",
            "proof": {
                "n_times_4": times_four,
                "reverse_n": reverse_n,
                "is_reverse_product": times_four == reverse_n,
                "digital_root": digital_root,
                "is_tesla_complete": digital_root == 9,
            },
            "validated": (times_four == reverse_n) and (digital_root == 9),
        }


# =============================================================================
# SINGLETON & FACTORY
# =============================================================================
_jarvis_engine: Optional[JarvisSavantEngine] = None


def get_jarvis_engine() -> JarvisSavantEngine:
    """Get singleton JarvisSavantEngine instance."""
    global _jarvis_engine
    if _jarvis_engine is None:
        _jarvis_engine = JarvisSavantEngine()
        logger.info(f"JarvisSavantEngine {_jarvis_engine.version} initialized")
    return _jarvis_engine


# =============================================================================
# CONVENIENCE FUNCTION FOR LIVE_DATA_ROUTER
# =============================================================================
def compute_jarvis_score(
    matchup: str = "",
    player: str = "",
    team: str = "",
    opponent: str = "",
    spread: float = 0,
    gematria_hits: int = 0,
    sport: str = "nba",
) -> Dict[str, Any]:
    """
    Compute Jarvis score - convenience wrapper.

    Returns standardized output:
    {
        "jarvis_rs": float,
        "jarvis_active": bool,
        "jarvis_hits_count": int,
        "jarvis_triggers_hit": list,
        "jarvis_reasons": list
    }
    """
    engine = get_jarvis_engine()
    return engine.calculate_jarvis_rs(
        matchup=matchup,
        player=player,
        team=team,
        opponent=opponent,
        spread=spread,
        gematria_hits=gematria_hits,
        sport=sport,
    )


# =============================================================================
# MODULE TEST
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("JARVIS SAVANT ENGINE v7.9 - STANDALONE TEST")
    print("=" * 60)

    engine = get_jarvis_engine()

    # Test 2178 validation
    validation = engine.validate_2178()
    print(f"\n2178 Validation: {validation['validated']}")
    print(f"  2178 × 4 = {validation['proof']['n_times_4']} == {validation['proof']['reverse_n']}")

    # Test Jarvis scoring for different sports
    test_cases = [
        {"matchup": "Lakers vs Celtics", "sport": "nba", "spread": 5.5, "gematria_hits": 3},
        {"matchup": "Sharks vs Flames", "sport": "nhl", "spread": 1.5, "gematria_hits": 4},
        {"matchup": "Chiefs vs Bills", "sport": "nfl", "spread": 3.0, "gematria_hits": 2},
        {"matchup": "Yankees vs Red Sox", "sport": "mlb", "spread": 1.5, "gematria_hits": 1},
    ]

    print("\n" + "=" * 60)
    print("JARVIS RS BY SPORT:")
    print("=" * 60)

    for tc in test_cases:
        result = engine.calculate_jarvis_rs(**tc)
        print(f"\n{tc['sport'].upper()}: {tc['matchup']}")
        print(f"  jarvis_rs: {result['jarvis_rs']}")
        print(f"  jarvis_active: {result['jarvis_active']}")
        print(f"  jarvis_hits_count: {result['jarvis_hits_count']}")
        print(f"  reasons: {result['jarvis_reasons'][:3]}...")  # First 3 reasons

    # Test sacred trigger detection
    print("\n" + "=" * 60)
    print("TRIGGER DETECTION:")
    print("=" * 60)

    trigger_test = engine.check_jarvis_triggers("Game 33 Championship")
    print(f"\n'Game 33 Championship':")
    print(f"  triggered: {trigger_test['triggered']}")
    print(f"  gematria: {trigger_test['gematria_value']}")
    print(f"  triggers_hit: {trigger_test['triggers_hit']}")
