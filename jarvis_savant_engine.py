"""
JARVIS SAVANT ENGINE v7.8 – UNIVERSAL SPORTS IMPLEMENTATION
COMPLETE STATE AS OF JANUARY 24, 2026

This engine provides:
- Sport-agnostic scoring with calibrated weights per sport
- JARVIS trigger detection (2178, 201, 33, 47, 88, 93, 322)
- Gematria-dominant ritual scoring
- Vedic/Astro integration
- Learning loop for result-based adjustments

Philosophy: Competition + variance. Edges from esoteric resonance (gematria dominant)
+ exoteric inefficiencies (public fade crush). Straight betting only.

Author: Built with Boss through grind – universal evolution.
"""

import datetime
import logging
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)

# ============================================================================
# JARVIS TRIGGERS - THE PROVEN EDGE NUMBERS (Synced with live_data_router.py)
# ============================================================================
JARVIS_TRIGGERS = {
    2178: {"name": "THE IMMORTAL", "boost": 20, "tier": "LEGENDARY", "description": "Only number where n^4 contains n AND reverse(n)^4 contains reverse(n). Digital root 9.", "mathematical": True},
    201: {"name": "THE ORDER", "boost": 12, "tier": "HIGH", "description": "Jesuit Order gematria. The Event of 201.", "mathematical": False},
    33: {"name": "THE MASTER", "boost": 10, "tier": "HIGH", "description": "Highest master number. Masonic significance.", "mathematical": False},
    47: {"name": "THE AGENT", "boost": 8, "tier": "MEDIUM", "description": "Agent of chaos. Discordian prime. High variance indicator.", "mathematical": False},
    88: {"name": "THE INFINITE", "boost": 8, "tier": "MEDIUM", "description": "Double infinity. Mercury retrograde resonance. Cycle completion.", "mathematical": False},
    93: {"name": "THE WILL", "boost": 10, "tier": "HIGH", "description": "Thelema sacred number. Will and Love.", "mathematical": False},
    322: {"name": "THE SOCIETY", "boost": 10, "tier": "HIGH", "description": "Skull & Bones. Genesis 3:22.", "mathematical": False},
}

POWER_NUMBERS = [11, 22, 33, 44, 55, 66, 77, 88, 99]
TESLA_NUMBERS = [3, 6, 9]

# ============================================================================
# SPORT PROFILES - Calibrated weights per sport (synced with live_data_router.py)
# ============================================================================
SPORT_PROFILES = {
    "nba": {
        "weights": {"ai": 0.35, "research": 0.35, "esoteric": 0.10, "jarvis": 0.20},
        "tiers": {"PASS": 4.75, "MONITOR": 5.75, "EDGE_LEAN": 6.50, "GOLD_STAR": 7.50},
        "variance_factor": 1.0,  # Standard variance
        "dog_threshold_rs": 7.5,
        "dog_threshold_public": 70,
    },
    "nhl": {
        "weights": {"ai": 0.33, "research": 0.35, "esoteric": 0.10, "jarvis": 0.22},
        "tiers": {"PASS": 4.50, "MONITOR": 5.50, "EDGE_LEAN": 6.25, "GOLD_STAR": 7.25},
        "variance_factor": 1.15,  # High variance sport
        "dog_threshold_rs": 7.0,
        "dog_threshold_public": 72,
    },
    "nfl": {
        "weights": {"ai": 0.40, "research": 0.35, "esoteric": 0.08, "jarvis": 0.17},
        "tiers": {"PASS": 4.60, "MONITOR": 5.60, "EDGE_LEAN": 6.40, "GOLD_STAR": 7.40},
        "variance_factor": 0.9,  # Lower variance (sharper lines)
        "dog_threshold_rs": 7.8,
        "dog_threshold_public": 68,
    },
    "mlb": {
        "weights": {"ai": 0.42, "research": 0.35, "esoteric": 0.08, "jarvis": 0.15},
        "tiers": {"PASS": 4.60, "MONITOR": 5.60, "EDGE_LEAN": 6.35, "GOLD_STAR": 7.35},
        "variance_factor": 1.1,  # High variance (any team can win)
        "dog_threshold_rs": 7.2,
        "dog_threshold_public": 65,
    },
    "ncaab": {
        "weights": {"ai": 0.34, "research": 0.35, "esoteric": 0.09, "jarvis": 0.22},
        "tiers": {"PASS": 4.50, "MONITOR": 5.50, "EDGE_LEAN": 6.25, "GOLD_STAR": 7.25},
        "variance_factor": 1.2,  # Highest variance (college)
        "dog_threshold_rs": 6.8,
        "dog_threshold_public": 70,
    },
}

# ============================================================================
# GEMATRIA CALCULATION (Universal)
# ============================================================================
GEMATRIA_VALUES = {
    'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8, 'I': 9,
    'J': 10, 'K': 11, 'L': 12, 'M': 13, 'N': 14, 'O': 15, 'P': 16, 'Q': 17,
    'R': 18, 'S': 19, 'T': 20, 'U': 21, 'V': 22, 'W': 23, 'X': 24, 'Y': 25, 'Z': 26
}


def calculate_gematria(text: str) -> int:
    """Calculate simple gematria value for text."""
    return sum(GEMATRIA_VALUES.get(c.upper(), 0) for c in text if c.isalpha())


def reduce_to_single_digit(n: int) -> int:
    """Reduce number to single digit (digital root)."""
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


def calculate_digital_root(n: int) -> int:
    """Calculate digital root (Tesla/Vortex math)."""
    if n == 0:
        return 0
    return 1 + (n - 1) % 9


# ============================================================================
# JARVIS SAVANT ENGINE - Universal Implementation
# ============================================================================
class JarvisSavantEngine:
    """
    JARVIS SAVANT ENGINE v7.8

    Universal sports scoring engine with:
    - Sport-specific weight calibration
    - JARVIS trigger detection
    - Gematria-dominant ritual scoring
    - Public fade amplification
    - Learning loop integration
    """

    def __init__(self):
        self.version = "v7.8"
        self.straight_betting_only = True
        self.boss_instinct_priority = True

        # JARVIS triggers (expose as properties)
        self.triggers = JARVIS_TRIGGERS
        self.power_numbers = POWER_NUMBERS
        self.tesla_numbers = TESLA_NUMBERS

        # Core Weights (gematria dominant locked)
        self.rs_weights = {
            "gematria": 0.52,
            "numerology": 0.20,
            "astro": 0.13,
            "vedic": 0.10,
            "sacred": 0.05,
            "fib_phi": 0.05,
            "vortex": 0.05,
        }

        # Public Fade amplifier
        self.public_fade_multiplier = -0.32  # Applied when public >= 70%

        # Mid-spread amplifier (Goldilocks zone: +4 to +9)
        self.mid_spread_amplifier = 0.20

        # Trap gate penalty
        self.trap_gate_penalty = -0.20  # Large spreads (>15)

    def get_sport_profile(self, sport: str) -> Dict:
        """Get calibrated profile for sport."""
        return SPORT_PROFILES.get(sport.lower(), SPORT_PROFILES["nba"])

    def validate_2178(self) -> Dict[str, Any]:
        """
        Validate 2178 as THE IMMORTAL number.

        Mathematical proof:
        - 2178 × 4 = 8712 (its reverse!)
        - Only 4-digit number with this property
        - Digital root of 2178 = 9 (Tesla completion)
        - Sum of digits: 2+1+7+8 = 18 → 1+8 = 9
        """
        n = 2178
        reverse_n = 8712

        # Key property: 2178 × 4 = 8712 (reverse!)
        times_four = n * 4
        is_reverse_product = times_four == reverse_n

        # Digital root = 9 (Tesla completion)
        digital_root = calculate_digital_root(n)

        # Additional properties
        digit_sum = sum(int(d) for d in str(n))  # 2+1+7+8 = 18

        return {
            "number": n,
            "name": "THE IMMORTAL",
            "proof": {
                "n_times_4": times_four,
                "reverse_n": reverse_n,
                "is_reverse_product": is_reverse_product,
                "digit_sum": digit_sum,
                "digital_root": digital_root,
                "is_tesla_complete": digital_root == 9,
            },
            "validated": is_reverse_product and digital_root == 9,
            "description": "The only 4-digit number where n × 4 = reverse(n). Digital root = 9 (Tesla completion).",
        }

    def check_jarvis_trigger(self, value: Union[str, int]) -> Dict[str, Any]:
        """
        Check if a value triggers any JARVIS numbers.

        Supports:
        - Direct number matches
        - Gematria reduction of strings
        - Digital root matching
        """
        triggers_hit = []

        # Convert to number if string
        if isinstance(value, str):
            try:
                numeric_value = int(value)
            except ValueError:
                # Calculate gematria for text
                numeric_value = calculate_gematria(value)
        else:
            numeric_value = value

        # Check direct matches
        if numeric_value in self.triggers:
            trigger = self.triggers[numeric_value]
            triggers_hit.append({
                "number": numeric_value,
                "match_type": "DIRECT",
                **trigger
            })

        # Check gematria reduction
        gematria_reduced = reduce_to_single_digit(numeric_value)
        for trigger_num, trigger_data in self.triggers.items():
            if reduce_to_single_digit(trigger_num) == gematria_reduced and trigger_num != numeric_value:
                triggers_hit.append({
                    "number": trigger_num,
                    "match_type": "GEMATRIA_REDUCTION",
                    "original_value": numeric_value,
                    "reduced_to": gematria_reduced,
                    **trigger_data
                })

        # Check if value contains trigger numbers
        value_str = str(numeric_value)
        for trigger_num, trigger_data in self.triggers.items():
            if str(trigger_num) in value_str and trigger_num != numeric_value:
                triggers_hit.append({
                    "number": trigger_num,
                    "match_type": "CONTAINS",
                    "found_in": numeric_value,
                    **trigger_data
                })

        # Check power numbers
        power_hits = [p for p in self.power_numbers if p == numeric_value or str(p) in value_str]

        # Check Tesla numbers (digital root)
        digital_root = calculate_digital_root(numeric_value)
        is_tesla = digital_root in self.tesla_numbers

        total_boost = sum(t.get("boost", 0) for t in triggers_hit)

        return {
            "input": value,
            "numeric_value": numeric_value,
            "triggers_hit": triggers_hit,
            "power_numbers_hit": power_hits,
            "digital_root": digital_root,
            "is_tesla_aligned": is_tesla,
            "total_boost": total_boost,
            "triggered": len(triggers_hit) > 0 or is_tesla,
        }

    def calculate_rs(self, game_data: Dict, sport: str = "nba") -> float:
        """
        Calculate Ritual Score (0-10) with gematria boost.

        Sport-agnostic with calibrated thresholds.
        """
        profile = self.get_sport_profile(sport)
        variance_factor = profile.get("variance_factor", 1.0)

        rs = 5.0  # Base score
        reasons = []

        # Gematria component (dominant - 52% weight)
        gematria_hits = game_data.get("gematria_hits", 0)
        if gematria_hits >= 4:
            rs += 2.0 * variance_factor
            reasons.append(f"Gematria 4+ hits: +{2.0 * variance_factor:.2f}")
        elif gematria_hits >= 3:
            rs += 1.5 * variance_factor
            reasons.append(f"Gematria 3 hits: +{1.5 * variance_factor:.2f}")
        elif gematria_hits >= 2:
            rs += 0.8 * variance_factor
            reasons.append(f"Gematria 2 hits: +{0.8 * variance_factor:.2f}")

        # Mid-spread amplifier (Goldilocks zone)
        spread = abs(game_data.get("spread", 0))
        if 4 <= spread <= 9:
            boost = self.mid_spread_amplifier * 10 * variance_factor
            rs += boost
            reasons.append(f"Goldilocks spread ({spread}): +{boost:.2f}")

        # Public fade component
        public_pct = game_data.get("public_chalk", game_data.get("public_pct", 50))
        if public_pct >= 70:
            fade_boost = abs(self.public_fade_multiplier) * 5 * variance_factor
            rs += fade_boost
            reasons.append(f"Public fade ({public_pct}%): +{fade_boost:.2f}")

        # Trap gate (large spreads)
        if spread > 15:
            penalty = abs(self.trap_gate_penalty) * 5
            rs -= penalty
            reasons.append(f"Trap gate (spread {spread}): -{penalty:.2f}")

        # JARVIS trigger check
        matchup = game_data.get("matchup", "")
        trigger_result = self.check_jarvis_trigger(matchup)
        if trigger_result["triggered"]:
            trigger_boost = min(trigger_result["total_boost"] / 10, 2.0)  # Cap at 2.0
            rs += trigger_boost
            reasons.append(f"JARVIS trigger: +{trigger_boost:.2f}")

        # Tesla alignment
        if trigger_result.get("is_tesla_aligned"):
            rs += 0.5
            reasons.append("Tesla aligned: +0.50")

        # Cap at 10
        rs = min(max(rs, 0), 10.0)

        return rs

    def calculate_quant_p(self, game_data: Dict, sport: str = "nba") -> float:
        """
        Calculate Quant Probability (0-100) with public fade.
        """
        profile = self.get_sport_profile(sport)

        p = 55.0  # Base probability

        # Public fade amplification
        public_pct = game_data.get("public_chalk_percent", game_data.get("public_pct", 50))
        if public_pct >= 70:
            p += self.public_fade_multiplier * 30  # Fade boost
        elif public_pct >= 60:
            p += self.public_fade_multiplier * 15

        # Sharp money alignment
        if game_data.get("sharp_aligned", False):
            p += 10

        # RLM detected
        if game_data.get("rlm_detected", False):
            p += 8

        return min(max(p, 0), 100)

    def blended_probability(self, rs: float, quant_p: float, sport: str = "nba") -> float:
        """
        Calculate blended probability using sport-specific weights.

        Formula: (jarvis_weight * rs/10) + (research_weight * quant_p/100)
        """
        profile = self.get_sport_profile(sport)
        weights = profile["weights"]

        # Blend ritual score and quant probability
        jarvis_contrib = weights["jarvis"] * (rs / 10)
        research_contrib = weights["research"] * (quant_p / 100)

        # Normalize to 0-1 range
        blended = (jarvis_contrib + research_contrib) / (weights["jarvis"] + weights["research"])

        return blended

    def generate_picks(self, slate: List[Dict], sport: str = "nba") -> List[Dict]:
        """
        Generate picks for slate with sport-calibrated thresholds.
        """
        profile = self.get_sport_profile(sport)
        tiers = profile["tiers"]
        dog_threshold_rs = profile.get("dog_threshold_rs", 7.5)
        dog_threshold_public = profile.get("dog_threshold_public", 70)

        picks = []

        for game in slate:
            rs = self.calculate_rs(game, sport)
            quant_p = self.calculate_quant_p(game, sport)
            blended = self.blended_probability(rs, quant_p, sport)

            # Convert blended to score (0-10 scale)
            score = blended * 10

            # Determine tier
            if score >= tiers["GOLD_STAR"]:
                tier = "GOLD_STAR"
            elif score >= tiers["EDGE_LEAN"]:
                tier = "EDGE_LEAN"
            elif score >= tiers["MONITOR"]:
                tier = "MONITOR"
            else:
                tier = "PASS"

            pick = {
                "game": game.get("matchup", "Unknown"),
                "sport": sport.upper(),
                "blended": blended,
                "score": score,
                "rs": rs,
                "quant_p": quant_p,
                "tier": tier,
            }

            # Underdog lotto detection (sport-calibrated)
            is_underdog = game.get("is_underdog", False)
            public_chalk = game.get("public_chalk", game.get("public_pct", 50))

            if is_underdog and rs >= dog_threshold_rs and public_chalk >= dog_threshold_public:
                pick["bet_type"] = "ML_DOG_LOTTO"
                pick["units"] = 0.5
                pick["rationale"] = f"Underdog lotto: RS {rs:.1f} >= {dog_threshold_rs}, Public {public_chalk}% >= {dog_threshold_public}%"

            picks.append(pick)

        # Filter to actionable picks only
        actionable = [p for p in picks if p["tier"] in ("GOLD_STAR", "EDGE_LEAN")]
        actionable.sort(key=lambda x: x["score"], reverse=True)

        return actionable

    def learn_from_result(self, result: Dict):
        """
        Learning loop - log result for future weight adjustments.
        """
        if result.get("win"):
            logger.info(f"WIN on {result.get('pick')} - amplify edges (public fade, gematria)")
            return {"action": "AMPLIFY", "factors": ["public_fade", "gematria", "dog_ritual"]}
        else:
            logger.info(f"LOSS on {result.get('pick')} - apply gates (trap, variance)")
            return {"action": "GATE", "factors": ["trap_detection", "variance_adjust", "public_overest"]}


# ============================================================================
# VEDIC ASTRO ENGINE - Planetary Hour Calculations
# ============================================================================
class VedicAstroEngine:
    """
    Vedic astrology engine for planetary hour and nakshatra calculations.
    """

    PLANETARY_RULERS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

    def __init__(self):
        self.version = "v1.0"

    def get_planetary_hour(self, dt: datetime.datetime = None) -> Dict[str, Any]:
        """Get current planetary hour ruler."""
        if dt is None:
            dt = datetime.datetime.now()

        # Simplified planetary hour calculation
        day_of_week = dt.weekday()
        hour = dt.hour

        # Day rulers (Sunday=Sun, Monday=Moon, etc.)
        day_rulers = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]
        day_ruler = day_rulers[day_of_week]

        # Hour ruler cycles through from day ruler
        start_idx = self.PLANETARY_RULERS.index(day_ruler)
        hour_idx = (start_idx + hour) % 7
        hour_ruler = self.PLANETARY_RULERS[hour_idx]

        return {
            "day_ruler": day_ruler,
            "hour_ruler": hour_ruler,
            "hour": hour,
            "favorable_for": self._get_favorable_activities(hour_ruler),
        }

    def _get_favorable_activities(self, ruler: str) -> List[str]:
        """Get favorable betting activities for planetary ruler."""
        activities = {
            "Sun": ["favorites", "home_teams", "star_players"],
            "Moon": ["totals", "overs", "high_scoring"],
            "Mars": ["underdogs", "aggression", "comebacks"],
            "Mercury": ["props", "player_stats", "quick_decisions"],
            "Jupiter": ["parlays", "expansion", "large_bets"],
            "Venus": ["favorites", "chalk", "stability"],
            "Saturn": ["unders", "defense", "patience"],
        }
        return activities.get(ruler, [])

    def get_moon_phase_impact(self, moon_phase: str = None) -> Dict[str, Any]:
        """Get betting impact based on moon phase."""
        if moon_phase is None:
            # Simplified - would integrate with astronomy API
            day_of_month = datetime.datetime.now().day
            if day_of_month < 7:
                moon_phase = "new_moon"
            elif day_of_month < 14:
                moon_phase = "waxing"
            elif day_of_month < 21:
                moon_phase = "full_moon"
            else:
                moon_phase = "waning"

        impacts = {
            "new_moon": {"boost": 0.1, "favor": "underdogs", "avoid": "heavy_chalk"},
            "waxing": {"boost": 0.05, "favor": "overs", "avoid": None},
            "full_moon": {"boost": 0.15, "favor": "high_variance", "avoid": "safe_bets"},
            "waning": {"boost": -0.05, "favor": "unders", "avoid": "parlays"},
        }

        return {
            "phase": moon_phase,
            **impacts.get(moon_phase, {"boost": 0, "favor": None, "avoid": None})
        }


# ============================================================================
# ESOTERIC LEARNING LOOP - Result-Based Weight Adjustment
# ============================================================================
class EsotericLearningLoop:
    """
    Learning loop that adjusts weights based on betting results.
    """

    def __init__(self):
        self.version = "v1.0"
        self.results_log = []
        self.weight_adjustments = {}

    def log_result(self, pick: Dict, won: bool, sport: str = "nba"):
        """Log a betting result for learning."""
        result = {
            "pick": pick,
            "won": won,
            "sport": sport,
            "timestamp": datetime.datetime.now().isoformat(),
            "factors": pick.get("factors", []),
        }
        self.results_log.append(result)

        # Track factor performance
        for factor in result["factors"]:
            if factor not in self.weight_adjustments:
                self.weight_adjustments[factor] = {"wins": 0, "losses": 0}

            if won:
                self.weight_adjustments[factor]["wins"] += 1
            else:
                self.weight_adjustments[factor]["losses"] += 1

        return result

    def get_factor_performance(self) -> Dict[str, Any]:
        """Get win rate by factor."""
        performance = {}

        for factor, stats in self.weight_adjustments.items():
            total = stats["wins"] + stats["losses"]
            if total > 0:
                win_rate = stats["wins"] / total
                performance[factor] = {
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "total": total,
                    "win_rate": win_rate,
                    "recommendation": "AMPLIFY" if win_rate > 0.55 else "REDUCE" if win_rate < 0.45 else "MAINTAIN"
                }

        return performance

    def get_suggested_adjustments(self) -> Dict[str, float]:
        """Get suggested weight adjustments based on performance."""
        adjustments = {}
        performance = self.get_factor_performance()

        for factor, stats in performance.items():
            if stats["total"] >= 10:  # Minimum sample size
                if stats["recommendation"] == "AMPLIFY":
                    adjustments[factor] = 1.1  # +10%
                elif stats["recommendation"] == "REDUCE":
                    adjustments[factor] = 0.9  # -10%
                else:
                    adjustments[factor] = 1.0

        return adjustments


# ============================================================================
# FULL ESOTERIC ANALYSIS FUNCTION
# ============================================================================
def calculate_full_esoteric_analysis(
    player: str = "",
    team: str = "",
    opponent: str = "",
    sport: str = "nba",
    spread: float = 0,
    total: float = 220,
    public_pct: float = 50,
) -> Dict[str, Any]:
    """
    Calculate full esoteric analysis for a pick.

    Combines:
    - JARVIS trigger detection
    - Gematria analysis
    - Vedic planetary hours
    - Moon phase impact
    """
    engine = get_jarvis_engine()
    vedic = get_vedic_engine()

    # JARVIS triggers
    matchup = f"{team} vs {opponent}"
    jarvis_result = engine.check_jarvis_trigger(matchup)

    # Individual gematria
    player_gem = calculate_gematria(player) if player else 0
    team_gem = calculate_gematria(team) if team else 0
    opponent_gem = calculate_gematria(opponent) if opponent else 0

    # Digital roots
    player_root = calculate_digital_root(player_gem) if player_gem else 0
    team_root = calculate_digital_root(team_gem) if team_gem else 0

    # Vedic analysis
    planetary = vedic.get_planetary_hour()
    moon_impact = vedic.get_moon_phase_impact()

    # Calculate overall esoteric score
    esoteric_score = 5.0  # Base
    reasons = []

    # JARVIS boost
    if jarvis_result["triggered"]:
        boost = min(jarvis_result["total_boost"] / 10, 2.0)
        esoteric_score += boost
        reasons.append(f"JARVIS: +{boost:.2f}")

    # Tesla alignment
    if player_root in TESLA_NUMBERS or team_root in TESLA_NUMBERS:
        esoteric_score += 0.5
        reasons.append("Tesla aligned: +0.50")

    # Moon phase
    esoteric_score += moon_impact["boost"]
    if moon_impact["boost"] != 0:
        reasons.append(f"Moon phase ({moon_impact['phase']}): {moon_impact['boost']:+.2f}")

    # Cap score
    esoteric_score = min(max(esoteric_score, 0), 10.0)

    return {
        "esoteric_score": esoteric_score,
        "gematria": {
            "player": {"value": player_gem, "digital_root": player_root},
            "team": {"value": team_gem, "digital_root": team_root},
            "opponent": {"value": opponent_gem},
        },
        "jarvis": jarvis_result,
        "vedic": {
            "planetary_hour": planetary,
            "moon_phase": moon_impact,
        },
        "reasons": reasons,
        "sport": sport.upper(),
    }


# ============================================================================
# SINGLETON INSTANCES & FACTORY FUNCTIONS
# ============================================================================
_jarvis_engine = None
_vedic_engine = None
_learning_loop = None


def get_jarvis_engine() -> JarvisSavantEngine:
    """Get singleton JarvisSavantEngine instance."""
    global _jarvis_engine
    if _jarvis_engine is None:
        _jarvis_engine = JarvisSavantEngine()
        logger.info(f"JarvisSavantEngine {_jarvis_engine.version} initialized")
    return _jarvis_engine


def get_vedic_engine() -> VedicAstroEngine:
    """Get singleton VedicAstroEngine instance."""
    global _vedic_engine
    if _vedic_engine is None:
        _vedic_engine = VedicAstroEngine()
        logger.info(f"VedicAstroEngine {_vedic_engine.version} initialized")
    return _vedic_engine


def get_learning_loop() -> EsotericLearningLoop:
    """Get singleton EsotericLearningLoop instance."""
    global _learning_loop
    if _learning_loop is None:
        _learning_loop = EsotericLearningLoop()
        logger.info(f"EsotericLearningLoop {_learning_loop.version} initialized")
    return _learning_loop


# ============================================================================
# MODULE INITIALIZATION
# ============================================================================
if __name__ == "__main__":
    # Test the engine
    engine = get_jarvis_engine()
    vedic = get_vedic_engine()

    print(f"JARVIS SAVANT ENGINE {engine.version}")
    print(f"=" * 50)

    # Test 2178 validation
    validation = engine.validate_2178()
    print(f"\n2178 Validation: {validation['validated']}")

    # Test trigger check
    trigger = engine.check_jarvis_trigger("Lakers vs Celtics")
    print(f"\nTrigger check 'Lakers vs Celtics': {trigger['triggered']}")
    print(f"  Gematria value: {trigger['numeric_value']}")
    print(f"  Digital root: {trigger['digital_root']}")
    print(f"  Tesla aligned: {trigger['is_tesla_aligned']}")

    # Test pick generation
    test_slate = [
        {"matchup": "Lakers vs Celtics", "sport": "nba", "is_underdog": False, "public_chalk": 65, "gematria_hits": 3, "spread": 5.5},
        {"matchup": "Sharks vs Flames", "sport": "nhl", "is_underdog": True, "public_chalk": 78, "gematria_hits": 4, "spread": 1.5},
    ]

    print(f"\n{'='*50}")
    print("Testing NBA picks:")
    nba_picks = engine.generate_picks([test_slate[0]], "nba")
    for pick in nba_picks:
        print(f"  {pick['game']}: {pick['tier']} (score: {pick['score']:.2f})")

    print(f"\nTesting NHL picks:")
    nhl_picks = engine.generate_picks([test_slate[1]], "nhl")
    for pick in nhl_picks:
        print(f"  {pick['game']}: {pick['tier']} (score: {pick['score']:.2f})")

    # Test planetary hour
    print(f"\n{'='*50}")
    planetary = vedic.get_planetary_hour()
    print(f"Planetary Hour: {planetary['hour_ruler']} (Day: {planetary['day_ruler']})")
    print(f"Favorable for: {planetary['favorable_for']}")
