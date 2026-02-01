"""
JASON SIM CONFLUENCE - Win Probability Simulation Engine
=========================================================
v11.08 - Required confluence layer for all picks

Jason Sim runs AFTER base score is computed and BEFORE tier assignment.
It simulates game outcomes and adjusts scores based on win probability alignment.

RULES:
- Spread/ML: Boost if pick-side win% >= 61%, downgrade if <= 55%, block if <= 52% AND base_score < 7.2
- Totals: Reduce confidence if variance HIGH, increase if LOW/MED
- Props: Boost only if base_prop_score >= 6.8 AND environment supports the prop type

OUTPUT (must appear on every pick):
- jason_ran: bool
- jason_sim_boost: float
- jason_blocked: bool
- jason_win_pct_home: float
- jason_win_pct_away: float
- projected_total: float
- projected_pace: str
- variance_flag: str (LOW/MED/HIGH)
- injury_state: str
- confluence_reasons: array

FINAL SCORE = base_score + jason_sim_boost
"""

from typing import Dict, Any, List, Tuple, Optional
import logging
import hashlib
import random

logger = logging.getLogger("jason_sim")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Win percentage thresholds for spread/ML picks
WIN_PCT_BOOST_THRESHOLD = 61.0    # >= 61% = boost
WIN_PCT_DOWNGRADE_THRESHOLD = 55.0  # <= 55% = downgrade
WIN_PCT_BLOCK_THRESHOLD = 52.0    # <= 52% AND base < 7.2 = block

# Base score threshold for blocking
BASE_SCORE_BLOCK_THRESHOLD = 7.2

# Boost/downgrade amounts
SPREAD_ML_BOOST = 0.8           # Boost when win% >= 61%
SPREAD_ML_DOWNGRADE = -0.5      # Downgrade when win% <= 55%

# Total variance adjustments
TOTAL_HIGH_VARIANCE_PENALTY = -0.4
TOTAL_LOW_VARIANCE_BOOST = 0.3

# Prop requirements
PROP_MIN_BASE_SCORE = 6.8       # Props need >= 6.8 to get Jason boost
PROP_BOOST = 0.5                # Prop boost amount

# =============================================================================
# JASON SIM CLASS
# =============================================================================

class JasonSimConfluence:
    """
    Jason Simulation Confluence Engine.

    Simulates game outcomes using deterministic pseudo-random based on matchup.
    Applies boosts/downgrades based on win probability alignment.
    """

    def __init__(self):
        self.VERSION = "11.08"
        logger.info("JasonSimConfluence v%s initialized", self.VERSION)

    def _generate_deterministic_seed(self, matchup: str, date_str: str = "") -> int:
        """Generate deterministic seed from matchup for reproducible simulations."""
        seed_input = f"{matchup}:{date_str}".encode()
        return int(hashlib.sha256(seed_input).hexdigest()[:8], 16)

    def simulate_game(
        self,
        home_team: str,
        away_team: str,
        spread: float = 0,
        total: float = 220,
        home_implied_prob: float = 0.5,
        injury_impact: float = 0,
        num_sims: int = 1000
    ) -> Dict[str, Any]:
        """
        Simulate game outcomes to get win probabilities.

        Args:
            home_team: Home team name
            away_team: Away team name
            spread: Point spread (negative = home favored)
            total: Over/under total
            home_implied_prob: Implied probability from odds (0-1)
            injury_impact: Adjustment for injuries (-1 to 1)
            num_sims: Number of simulations

        Returns:
            Simulation results with win percentages
        """
        matchup = f"{away_team}@{home_team}"
        seed = self._generate_deterministic_seed(matchup)
        rng = random.Random(seed)

        # Base probabilities from spread and implied odds
        # Spread of -7 roughly equals 70% win probability
        spread_prob = 0.5 + (spread / -20.0)  # Each point ~2.5% change
        spread_prob = max(0.3, min(0.7, spread_prob))  # Clamp to reasonable range

        # Blend with implied probability from odds
        blended_prob = (spread_prob * 0.6) + (home_implied_prob * 0.4)

        # Apply injury impact
        blended_prob += injury_impact * 0.1
        blended_prob = max(0.25, min(0.75, blended_prob))

        # Run simulations
        home_wins = 0
        away_wins = 0
        home_covers = 0
        away_covers = 0
        total_scores = []

        for _ in range(num_sims):
            # Simulate if home wins
            if rng.random() < blended_prob:
                home_wins += 1
                # Home wins - simulate margin
                margin = rng.gauss(abs(spread) if spread < 0 else 3, 8)
                home_score = total / 2 + margin / 2 + rng.gauss(0, 5)
                away_score = total / 2 - margin / 2 + rng.gauss(0, 5)
            else:
                away_wins += 1
                # Away wins - simulate margin
                margin = rng.gauss(abs(spread) if spread > 0 else 3, 8)
                away_score = total / 2 + margin / 2 + rng.gauss(0, 5)
                home_score = total / 2 - margin / 2 + rng.gauss(0, 5)

            # Check spread coverage
            home_margin = home_score - away_score
            if home_margin > -spread:  # Home covers
                home_covers += 1
            else:
                away_covers += 1

            total_scores.append(home_score + away_score)

        # Calculate results
        home_win_pct = (home_wins / num_sims) * 100
        away_win_pct = (away_wins / num_sims) * 100
        home_cover_pct = (home_covers / num_sims) * 100
        away_cover_pct = (away_covers / num_sims) * 100

        projected_total = sum(total_scores) / len(total_scores)
        total_variance = sum((s - projected_total) ** 2 for s in total_scores) / len(total_scores)
        total_std = total_variance ** 0.5

        # Classify variance
        if total_std < 12:
            variance_flag = "LOW"
        elif total_std < 18:
            variance_flag = "MED"
        else:
            variance_flag = "HIGH"

        # Determine pace
        if projected_total > total + 5:
            projected_pace = "FAST"
        elif projected_total < total - 5:
            projected_pace = "SLOW"
        else:
            projected_pace = "NEUTRAL"

        return {
            "home_win_pct": round(home_win_pct, 1),
            "away_win_pct": round(away_win_pct, 1),
            "home_cover_pct": round(home_cover_pct, 1),
            "away_cover_pct": round(away_cover_pct, 1),
            "projected_total": round(projected_total, 1),
            "projected_pace": projected_pace,
            "variance_flag": variance_flag,
            "total_std": round(total_std, 2),
            "num_sims": num_sims
        }

    def evaluate_spread_ml(
        self,
        base_score: float,
        pick_side: str,
        home_team: str,
        away_team: str,
        sim_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate spread/ML picks using simulation results.

        Rules:
        - Boost if pick-side win% >= 61%
        - Downgrade if pick-side win% <= 55%
        - Block if pick-side win% <= 52% AND base_score < 7.2
        """
        reasons = []
        boost = 0.0
        blocked = False

        # Determine which team we're picking
        pick_is_home = pick_side.lower() in home_team.lower() or "home" in pick_side.lower()

        if pick_is_home:
            pick_win_pct = sim_results["home_win_pct"]
            pick_cover_pct = sim_results["home_cover_pct"]
        else:
            pick_win_pct = sim_results["away_win_pct"]
            pick_cover_pct = sim_results["away_cover_pct"]

        # Apply rules
        if pick_win_pct >= WIN_PCT_BOOST_THRESHOLD:
            boost = SPREAD_ML_BOOST
            reasons.append(f"Jason BOOST: Pick-side win% {pick_win_pct}% >= {WIN_PCT_BOOST_THRESHOLD}%")
        elif pick_win_pct <= WIN_PCT_BLOCK_THRESHOLD and base_score < BASE_SCORE_BLOCK_THRESHOLD:
            blocked = True
            boost = -1.5  # Strong downgrade
            reasons.append(f"Jason BLOCK: Win% {pick_win_pct}% <= {WIN_PCT_BLOCK_THRESHOLD}% AND base {base_score} < {BASE_SCORE_BLOCK_THRESHOLD}")
        elif pick_win_pct <= WIN_PCT_DOWNGRADE_THRESHOLD:
            boost = SPREAD_ML_DOWNGRADE
            reasons.append(f"Jason DOWNGRADE: Pick-side win% {pick_win_pct}% <= {WIN_PCT_DOWNGRADE_THRESHOLD}%")
        else:
            reasons.append(f"Jason NEUTRAL: Pick-side win% {pick_win_pct}% in normal range")

        return {
            "boost": boost,
            "blocked": blocked,
            "pick_win_pct": pick_win_pct,
            "pick_cover_pct": pick_cover_pct,
            "reasons": reasons
        }

    def evaluate_total(
        self,
        base_score: float,
        pick_side: str,  # "Over" or "Under"
        total_line: float,
        sim_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate total picks using simulation results.

        Rules:
        - Reduce confidence if variance HIGH
        - Increase confidence if variance LOW/MED and projection aligns with pick
        """
        reasons = []
        boost = 0.0
        blocked = False

        variance = sim_results["variance_flag"]
        projected = sim_results["projected_total"]

        # Check if projection aligns with pick
        pick_is_over = pick_side.lower() == "over"
        projection_agrees = (pick_is_over and projected > total_line) or (not pick_is_over and projected < total_line)

        if variance == "HIGH":
            boost = TOTAL_HIGH_VARIANCE_PENALTY
            reasons.append(f"Jason PENALTY: High variance ({sim_results['total_std']} std) on total")
        elif variance in ["LOW", "MED"] and projection_agrees:
            boost = TOTAL_LOW_VARIANCE_BOOST
            diff = abs(projected - total_line)
            reasons.append(f"Jason BOOST: {variance} variance, projection {projected} {'>' if pick_is_over else '<'} line {total_line} (diff: {diff:.1f})")
        else:
            reasons.append(f"Jason NEUTRAL: Variance {variance}, projection {projected} vs line {total_line}")

        return {
            "boost": boost,
            "blocked": blocked,
            "projection_agrees": projection_agrees,
            "reasons": reasons
        }

    def evaluate_prop(
        self,
        base_score: float,
        player_name: str,
        prop_type: str,
        prop_line: float,
        sim_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate prop picks.

        Rules:
        - Boost only if base_score >= 6.8 AND environment supports the prop type
        - Fast pace = boost scoring props (points, yards, etc.)
        - Slow pace = boost defensive props (rebounds, assists in some contexts)
        """
        reasons = []
        boost = 0.0
        blocked = False

        pace = sim_results["projected_pace"]
        variance = sim_results["variance_flag"]

        # Check base score requirement
        if base_score < PROP_MIN_BASE_SCORE:
            reasons.append(f"Jason SKIP: Prop base score {base_score} < {PROP_MIN_BASE_SCORE} threshold")
            return {
                "boost": 0.0,
                "blocked": False,
                "reasons": reasons
            }

        # Scoring props benefit from fast pace
        scoring_props = ["points", "pts", "yards", "passing", "rushing", "receiving", "goals", "shots"]
        is_scoring_prop = any(sp in prop_type.lower() for sp in scoring_props)

        # Volume props benefit from slower pace (more possessions, methodical play)
        volume_props = ["rebounds", "assists", "rebs", "asts", "saves"]
        is_volume_prop = any(vp in prop_type.lower() for vp in volume_props)

        if is_scoring_prop and pace == "FAST":
            boost = PROP_BOOST
            reasons.append(f"Jason BOOST: {prop_type} prop + FAST pace environment")
        elif is_volume_prop and pace in ["SLOW", "NEUTRAL"]:
            boost = PROP_BOOST * 0.75
            reasons.append(f"Jason BOOST: {prop_type} prop + {pace} pace favors volume")
        elif variance == "LOW":
            boost = PROP_BOOST * 0.5
            reasons.append(f"Jason BOOST: LOW variance game favors prop consistency")
        else:
            reasons.append(f"Jason NEUTRAL: {prop_type} prop, {pace} pace, {variance} variance")

        return {
            "boost": boost,
            "blocked": blocked,
            "reasons": reasons
        }

    def run_confluence(
        self,
        base_score: float,
        pick_type: str,  # "SPREAD", "ML", "TOTAL", "PROP"
        pick_side: str,
        home_team: str,
        away_team: str,
        spread: float = 0,
        total: float = 220,
        prop_line: float = 0,
        player_name: str = "",
        injury_state: str = "CONFIRMED_ONLY"
    ) -> Dict[str, Any]:
        """
        Run full Jason Sim Confluence for a pick.

        This is the main entry point. Call this after base score is computed.

        Returns all jason_* fields required by the output spec.
        """
        # Run simulation
        sim_results = self.simulate_game(
            home_team=home_team,
            away_team=away_team,
            spread=spread,
            total=total,
            injury_impact=0  # Could be enhanced with actual injury data
        )

        # Normalize pick_type to canonical categories
        # Map various input formats to the 4 canonical types
        normalized_type = pick_type.upper()
        type_mapping = {
            "SPREAD": "SPREAD",
            "SPREADS": "SPREAD",
            "ML": "SPREAD_ML",
            "MONEYLINE": "SPREAD_ML",
            "H2H": "SPREAD_ML",
            "TOTAL": "TOTAL",
            "TOTALS": "TOTAL",
            "PROP": "PROP",
            "PLAYER_PROP": "PROP",
            # SHARP picks: determine type based on spread value
            "SHARP": "SPREAD" if spread != 0 else "SPREAD_ML",
            "SHARP_MONEY": "SPREAD" if spread != 0 else "SPREAD_ML",
        }
        canonical_type = type_mapping.get(normalized_type, "SPREAD_ML")

        # Evaluate based on canonical pick type
        if canonical_type in ["SPREAD", "SPREAD_ML"]:
            eval_result = self.evaluate_spread_ml(
                base_score=base_score,
                pick_side=pick_side,
                home_team=home_team,
                away_team=away_team,
                sim_results=sim_results
            )
        elif canonical_type == "TOTAL":
            eval_result = self.evaluate_total(
                base_score=base_score,
                pick_side=pick_side,
                total_line=total,
                sim_results=sim_results
            )
        elif canonical_type == "PROP":
            eval_result = self.evaluate_prop(
                base_score=base_score,
                player_name=player_name,
                prop_type=pick_side,  # For props, pick_side is the prop type
                prop_line=prop_line,
                sim_results=sim_results
            )
        else:
            # Fallback - should never reach here with proper mapping
            eval_result = self.evaluate_spread_ml(
                base_score=base_score,
                pick_side=pick_side,
                home_team=home_team,
                away_team=away_team,
                sim_results=sim_results
            )

        # Build final output
        jason_sim_boost = eval_result["boost"]
        final_score = base_score + jason_sim_boost

        return {
            # Required fields (v14.11 output contract)
            "jason_ran": True,
            "jason_sim_available": True,  # v14.11: Explicit availability flag
            "jason_sim_boost": round(jason_sim_boost, 2),
            "jason_blocked": eval_result["blocked"],
            "jason_win_pct_home": sim_results["home_win_pct"],
            "jason_win_pct_away": sim_results["away_win_pct"],
            "projected_total": sim_results["projected_total"],
            "projected_pace": sim_results["projected_pace"],
            "variance_flag": sim_results["variance_flag"],
            "injury_state": injury_state,
            "sim_count": sim_results.get("num_sims", 1000),  # v14.11: Simulation count
            "confluence_reasons": eval_result["reasons"],
            # Additional fields
            "home_cover_pct": sim_results.get("home_cover_pct", 50.0),
            "away_cover_pct": sim_results.get("away_cover_pct", 50.0),
            "total_std": sim_results.get("total_std", 15.0),
            "num_sims": sim_results.get("num_sims", 1000),
            # Computed final
            "base_score": round(base_score, 2),
            "final_score_with_jason": round(final_score, 2)
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_jason_instance: Optional[JasonSimConfluence] = None


def get_jason_sim() -> JasonSimConfluence:
    """Get singleton Jason Sim instance."""
    global _jason_instance
    if _jason_instance is None:
        _jason_instance = JasonSimConfluence()
    return _jason_instance


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def run_jason_confluence(
    base_score: float,
    pick_type: str,
    pick_side: str,
    home_team: str,
    away_team: str,
    spread: float = 0,
    total: float = 220,
    prop_line: float = 0,
    player_name: str = "",
    injury_state: str = "CONFIRMED_ONLY"
) -> Dict[str, Any]:
    """
    Convenience function to run Jason confluence.

    Usage:
        jason_result = run_jason_confluence(
            base_score=7.5,
            pick_type="SPREAD",
            pick_side="Lakers -4.5",
            home_team="Los Angeles Lakers",
            away_team="Boston Celtics",
            spread=-4.5
        )
        final_score = base_score + jason_result["jason_sim_boost"]
    """
    jason = get_jason_sim()
    return jason.run_confluence(
        base_score=base_score,
        pick_type=pick_type,
        pick_side=pick_side,
        home_team=home_team,
        away_team=away_team,
        spread=spread,
        total=total,
        prop_line=prop_line,
        player_name=player_name,
        injury_state=injury_state
    )


def get_default_jason_output() -> Dict[str, Any]:
    """
    Get default Jason output when Jason doesn't run.

    This ensures jason_* fields always exist even on error.
    v14.11: Added jason_sim_available and sim_count for complete contract.
    """
    return {
        "jason_ran": False,
        "jason_sim_available": False,  # v14.11: Explicit availability flag
        "jason_sim_boost": 0.0,
        "jason_blocked": False,
        "jason_win_pct_home": 50.0,
        "jason_win_pct_away": 50.0,
        "projected_total": 220.0,
        "projected_pace": "NEUTRAL",
        "variance_flag": "MED",
        "injury_state": "CONFIRMED_ONLY",  # v14.11: Default to CONFIRMED_ONLY
        "sim_count": 0,  # v14.11: Number of simulations run
        "confluence_reasons": ["Jason did not run"],
        "base_score": 0.0,
        "final_score_with_jason": 0.0
    }
