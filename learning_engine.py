"""
v10.31 Learning Engine - Conservative Self-Correction Loop

Responsibilities:
1. Analyze performance over rolling window (7 days default)
2. Make conservative tuning adjustments to config
3. Respect drift limits (max 15% from factory)
4. Log all changes with metrics snapshot

Rules (safe + small steps):
1. Defense: If GOLD_STAR 7d ROI < -5%, increase threshold by +0.05
2. Expansion: If GOLD_STAR 7d ROI > +15% AND avg picks/day < 2, decrease by -0.05
3. Weight shift: If Research correlation > Esoteric, shift weight +0.01
4. Clamp: Total drift from factory must be <= 15%
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from database import (
    PickLedger, PickResult, get_db,
    get_settled_picks, load_sport_config, save_sport_config,
    FACTORY_SPORT_PROFILES
)

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

MIN_SETTLED_PICKS = 10  # Minimum picks required before tuning
MAX_DRIFT_PERCENT = 0.15  # 15% max drift from factory
WEIGHT_STEP = 0.01  # Small step for weight adjustments
THRESHOLD_STEP = 0.05  # Small step for threshold adjustments
MIN_RESEARCH_WEIGHT = 0.55  # Floor for research weight
MAX_RESEARCH_WEIGHT = 0.80  # Cap for research weight


@dataclass
class PerformanceMetrics:
    """Performance metrics for analysis."""
    total_picks: int = 0
    wins: int = 0
    losses: int = 0
    pushes: int = 0
    net_units: float = 0.0
    roi: float = 0.0
    hit_rate: float = 0.0

    # By tier
    gold_star_picks: int = 0
    gold_star_wins: int = 0
    gold_star_roi: float = 0.0
    edge_lean_picks: int = 0
    edge_lean_wins: int = 0
    edge_lean_roi: float = 0.0

    # By confidence grade
    grade_a_picks: int = 0
    grade_a_wins: int = 0
    grade_a_roi: float = 0.0
    grade_b_picks: int = 0
    grade_b_wins: int = 0
    grade_b_roi: float = 0.0
    grade_c_picks: int = 0
    grade_c_wins: int = 0
    grade_c_roi: float = 0.0

    # Correlation proxies (research vs esoteric contribution to profit)
    avg_research_score_win: float = 0.0
    avg_research_score_loss: float = 0.0
    avg_esoteric_score_win: float = 0.0
    avg_esoteric_score_loss: float = 0.0
    research_edge: float = 0.0  # research contribution to wins
    esoteric_edge: float = 0.0  # esoteric contribution to wins


# ============================================================================
# PERFORMANCE ANALYSIS
# ============================================================================

def analyze_performance(sport: str, window_days: int = 7) -> PerformanceMetrics:
    """
    Analyze performance for a sport over the rolling window.

    Args:
        sport: Sport code (NBA, NFL, etc.)
        window_days: Days to look back (default: 7)

    Returns:
        PerformanceMetrics with all calculated stats
    """
    picks = get_settled_picks(sport, window_days)

    if not picks:
        return PerformanceMetrics()

    metrics = PerformanceMetrics()
    metrics.total_picks = len(picks)

    # Running totals for averages
    research_win_sum = 0.0
    research_win_count = 0
    research_loss_sum = 0.0
    research_loss_count = 0
    esoteric_win_sum = 0.0
    esoteric_win_count = 0
    esoteric_loss_sum = 0.0
    esoteric_loss_count = 0

    total_units_wagered = 0.0
    gold_units_wagered = 0.0
    edge_units_wagered = 0.0
    grade_a_units = 0.0
    grade_b_units = 0.0
    grade_c_units = 0.0

    for pick in picks:
        units = pick.recommended_units or 0.5
        total_units_wagered += units

        # Overall metrics
        if pick.result == PickResult.WIN:
            metrics.wins += 1
        elif pick.result == PickResult.LOSS:
            metrics.losses += 1
        else:
            metrics.pushes += 1

        metrics.net_units += pick.profit_units or 0.0

        # By tier
        tier = (pick.tier or "").upper()
        if tier == "GOLD_STAR":
            metrics.gold_star_picks += 1
            gold_units_wagered += units
            if pick.result == PickResult.WIN:
                metrics.gold_star_wins += 1
        elif tier == "EDGE_LEAN":
            metrics.edge_lean_picks += 1
            edge_units_wagered += units
            if pick.result == PickResult.WIN:
                metrics.edge_lean_wins += 1

        # By confidence grade
        grade = (pick.confidence_grade or "C").upper()
        if grade == "A":
            metrics.grade_a_picks += 1
            grade_a_units += units
            if pick.result == PickResult.WIN:
                metrics.grade_a_wins += 1
        elif grade == "B":
            metrics.grade_b_picks += 1
            grade_b_units += units
            if pick.result == PickResult.WIN:
                metrics.grade_b_wins += 1
        else:  # C
            metrics.grade_c_picks += 1
            grade_c_units += units
            if pick.result == PickResult.WIN:
                metrics.grade_c_wins += 1

        # Correlation analysis (score contribution to wins vs losses)
        research = pick.research_score or 5.0
        esoteric = pick.esoteric_score or 5.0

        if pick.result == PickResult.WIN:
            research_win_sum += research
            research_win_count += 1
            esoteric_win_sum += esoteric
            esoteric_win_count += 1
        elif pick.result == PickResult.LOSS:
            research_loss_sum += research
            research_loss_count += 1
            esoteric_loss_sum += esoteric
            esoteric_loss_count += 1

    # Calculate derived metrics
    if metrics.total_picks > 0:
        metrics.hit_rate = metrics.wins / metrics.total_picks * 100

    if total_units_wagered > 0:
        metrics.roi = (metrics.net_units / total_units_wagered) * 100

    # Tier ROI calculations
    if gold_units_wagered > 0:
        gold_profit = sum(p.profit_units for p in picks if (p.tier or "").upper() == "GOLD_STAR")
        metrics.gold_star_roi = (gold_profit / gold_units_wagered) * 100

    if edge_units_wagered > 0:
        edge_profit = sum(p.profit_units for p in picks if (p.tier or "").upper() == "EDGE_LEAN")
        metrics.edge_lean_roi = (edge_profit / edge_units_wagered) * 100

    # Grade ROI calculations
    if grade_a_units > 0:
        grade_a_profit = sum(p.profit_units for p in picks if (p.confidence_grade or "").upper() == "A")
        metrics.grade_a_roi = (grade_a_profit / grade_a_units) * 100

    if grade_b_units > 0:
        grade_b_profit = sum(p.profit_units for p in picks if (p.confidence_grade or "").upper() == "B")
        metrics.grade_b_roi = (grade_b_profit / grade_b_units) * 100

    if grade_c_units > 0:
        grade_c_profit = sum(p.profit_units for p in picks if (p.confidence_grade or "").upper() == "C")
        metrics.grade_c_roi = (grade_c_profit / grade_c_units) * 100

    # Score analysis for correlation proxy
    if research_win_count > 0:
        metrics.avg_research_score_win = research_win_sum / research_win_count
    if research_loss_count > 0:
        metrics.avg_research_score_loss = research_loss_sum / research_loss_count
    if esoteric_win_count > 0:
        metrics.avg_esoteric_score_win = esoteric_win_sum / esoteric_win_count
    if esoteric_loss_count > 0:
        metrics.avg_esoteric_score_loss = esoteric_loss_sum / esoteric_loss_count

    # Calculate edge (how much higher are scores for wins vs losses)
    metrics.research_edge = metrics.avg_research_score_win - metrics.avg_research_score_loss
    metrics.esoteric_edge = metrics.avg_esoteric_score_win - metrics.avg_esoteric_score_loss

    return metrics


def metrics_to_dict(metrics: PerformanceMetrics) -> Dict[str, Any]:
    """Convert PerformanceMetrics to dict for JSON serialization."""
    return {
        "total_picks": metrics.total_picks,
        "wins": metrics.wins,
        "losses": metrics.losses,
        "pushes": metrics.pushes,
        "net_units": round(metrics.net_units, 2),
        "roi": round(metrics.roi, 2),
        "hit_rate": round(metrics.hit_rate, 2),
        "gold_star": {
            "picks": metrics.gold_star_picks,
            "wins": metrics.gold_star_wins,
            "roi": round(metrics.gold_star_roi, 2)
        },
        "edge_lean": {
            "picks": metrics.edge_lean_picks,
            "wins": metrics.edge_lean_wins,
            "roi": round(metrics.edge_lean_roi, 2)
        },
        "by_grade": {
            "A": {"picks": metrics.grade_a_picks, "wins": metrics.grade_a_wins, "roi": round(metrics.grade_a_roi, 2)},
            "B": {"picks": metrics.grade_b_picks, "wins": metrics.grade_b_wins, "roi": round(metrics.grade_b_roi, 2)},
            "C": {"picks": metrics.grade_c_picks, "wins": metrics.grade_c_wins, "roi": round(metrics.grade_c_roi, 2)}
        },
        "correlation_proxy": {
            "research_edge": round(metrics.research_edge, 3),
            "esoteric_edge": round(metrics.esoteric_edge, 3)
        }
    }


# ============================================================================
# CONSERVATIVE TUNING
# ============================================================================

def calculate_drift(current_value: float, factory_value: float) -> float:
    """Calculate percentage drift from factory value."""
    if factory_value == 0:
        return 0.0
    return abs(current_value - factory_value) / factory_value


def check_total_drift(config: Dict[str, Any], factory_config: Dict[str, Any]) -> Dict[str, float]:
    """Check drift for all tunable values."""
    drifts = {}

    # Weights drift
    current_research = config.get("weights", {}).get("research", 0.67)
    factory_research = factory_config.get("weights", {}).get("research", 0.67)
    drifts["research_weight"] = calculate_drift(current_research, factory_research)

    # Tier threshold drifts
    for tier_name in ["GOLD_STAR", "EDGE_LEAN", "MONITOR"]:
        current_thresh = config.get("tiers", {}).get(tier_name, 0)
        factory_thresh = factory_config.get("tiers", {}).get(tier_name, 0)
        drifts[f"{tier_name}_threshold"] = calculate_drift(current_thresh, factory_thresh)

    return drifts


def tune_config_conservatively(sport: str, window_days: int = 7) -> Dict[str, Any]:
    """
    Apply conservative tuning to sport config based on performance.

    Rules:
    1. Defense: If GOLD_STAR ROI < -5%, tighten threshold (+0.05)
    2. Expansion: If GOLD_STAR ROI > +15% AND avg picks/day < 2, loosen (-0.05)
    3. Weight shift: If research edge > esoteric edge by 0.5+, shift +0.01 to research
    4. Clamp: Reset to factory if any drift exceeds 15%

    Args:
        sport: Sport code
        window_days: Analysis window

    Returns:
        Tuning result summary
    """
    metrics = analyze_performance(sport, window_days)

    if metrics.total_picks < MIN_SETTLED_PICKS:
        return {
            "sport": sport,
            "tuned": False,
            "reason": f"Insufficient data: {metrics.total_picks} picks (need {MIN_SETTLED_PICKS})",
            "metrics": metrics_to_dict(metrics)
        }

    # Load current config
    config = load_sport_config(sport)
    factory_config = FACTORY_SPORT_PROFILES.get(sport.upper(), FACTORY_SPORT_PROFILES["NBA"])

    changes = []
    original_config = json.loads(json.dumps(config))  # Deep copy

    # Check drift before tuning
    drifts = check_total_drift(config, factory_config)
    over_drift = [k for k, v in drifts.items() if v > MAX_DRIFT_PERCENT]

    if over_drift:
        # Reset to factory - drift too high
        logger.warning(f"[{sport}] Drift exceeded 15% on {over_drift}, resetting to factory")
        config = json.loads(json.dumps(factory_config))
        changes.append(f"RESET: Drift exceeded 15% on {', '.join(over_drift)}")
    else:
        # Apply tuning rules

        # Rule 1: Defense - Tighten GOLD_STAR if losing
        if metrics.gold_star_roi < -5.0 and metrics.gold_star_picks >= 5:
            current_thresh = config.get("tiers", {}).get("GOLD_STAR", 7.5)
            new_thresh = current_thresh + THRESHOLD_STEP
            config["tiers"]["GOLD_STAR"] = round(new_thresh, 2)
            changes.append(f"DEFENSE: GOLD_STAR threshold {current_thresh:.2f} → {new_thresh:.2f} (ROI: {metrics.gold_star_roi:.1f}%)")
            logger.info(f"[{sport}] Tightened GOLD_STAR: {current_thresh} → {new_thresh}")

        # Rule 2: Expansion - Loosen GOLD_STAR if profitable and underproducing
        avg_picks_per_day = metrics.gold_star_picks / window_days
        if metrics.gold_star_roi > 15.0 and avg_picks_per_day < 2.0:
            current_thresh = config.get("tiers", {}).get("GOLD_STAR", 7.5)
            new_thresh = current_thresh - THRESHOLD_STEP
            # Don't go below EDGE_LEAN
            min_thresh = config.get("tiers", {}).get("EDGE_LEAN", 6.5) + 0.5
            if new_thresh >= min_thresh:
                config["tiers"]["GOLD_STAR"] = round(new_thresh, 2)
                changes.append(f"EXPANSION: GOLD_STAR threshold {current_thresh:.2f} → {new_thresh:.2f} (ROI: {metrics.gold_star_roi:.1f}%, avg/day: {avg_picks_per_day:.1f})")
                logger.info(f"[{sport}] Loosened GOLD_STAR: {current_thresh} → {new_thresh}")

        # Rule 3: Weight shift based on edge correlation
        edge_diff = metrics.research_edge - metrics.esoteric_edge
        if abs(edge_diff) >= 0.5:  # Meaningful difference
            current_research = config.get("weights", {}).get("research", 0.67)
            current_esoteric = config.get("weights", {}).get("esoteric", 0.33)

            if edge_diff > 0:
                # Research has better edge - shift toward research
                new_research = min(MAX_RESEARCH_WEIGHT, current_research + WEIGHT_STEP)
                new_esoteric = 1.0 - new_research
            else:
                # Esoteric has better edge - shift toward esoteric
                new_research = max(MIN_RESEARCH_WEIGHT, current_research - WEIGHT_STEP)
                new_esoteric = 1.0 - new_research

            if new_research != current_research:
                config["weights"]["research"] = round(new_research, 2)
                config["weights"]["esoteric"] = round(new_esoteric, 2)
                direction = "research" if edge_diff > 0 else "esoteric"
                changes.append(f"WEIGHT SHIFT: research {current_research:.2f} → {new_research:.2f} (edge favors {direction}: {edge_diff:.3f})")
                logger.info(f"[{sport}] Weight shift toward {direction}: {current_research} → {new_research}")

    # Save if changes were made
    if changes:
        metrics_snapshot = metrics_to_dict(metrics)
        reason = "; ".join(changes)
        save_sport_config(sport, config, reason, metrics_snapshot)

        return {
            "sport": sport,
            "tuned": True,
            "changes": changes,
            "metrics": metrics_snapshot,
            "old_config": original_config,
            "new_config": config
        }
    else:
        return {
            "sport": sport,
            "tuned": False,
            "reason": "No tuning needed - performance within acceptable range",
            "metrics": metrics_to_dict(metrics)
        }


def run_daily_tuning() -> Dict[str, Any]:
    """
    Run tuning for all sports.

    Returns:
        Combined tuning results
    """
    sports = ["NBA", "NFL", "MLB", "NHL", "NCAAB"]
    results = {}
    tuned_count = 0

    for sport in sports:
        result = tune_config_conservatively(sport)
        results[sport] = result
        if result.get("tuned"):
            tuned_count += 1

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "sports_tuned": tuned_count,
        "by_sport": results
    }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_current_config_status(sport: str) -> Dict[str, Any]:
    """Get current config with drift analysis."""
    config = load_sport_config(sport)
    factory = FACTORY_SPORT_PROFILES.get(sport.upper(), FACTORY_SPORT_PROFILES["NBA"])
    drifts = check_total_drift(config, factory)

    return {
        "sport": sport,
        "config": config,
        "factory": factory,
        "drifts": {k: f"{v*100:.1f}%" for k, v in drifts.items()},
        "max_drift": f"{max(drifts.values())*100:.1f}%",
        "at_risk": any(v > MAX_DRIFT_PERCENT * 0.8 for v in drifts.values())  # 80% of limit
    }


def reset_config_to_factory(sport: str) -> Dict[str, Any]:
    """
    Reset a sport's config to factory defaults.

    Args:
        sport: Sport code

    Returns:
        Reset result
    """
    factory = FACTORY_SPORT_PROFILES.get(sport.upper(), FACTORY_SPORT_PROFILES["NBA"])
    save_sport_config(
        sport,
        factory,
        "Manual reset to factory defaults",
        {"reset_trigger": "manual"}
    )

    return {
        "sport": sport,
        "reset": True,
        "new_config": factory
    }


# ============================================================================
# v10.32 MICRO-WEIGHT TUNING
# ============================================================================

# Micro-weight tuning constants
MICRO_WEIGHT_MIN = 0.85  # Floor for micro-weights
MICRO_WEIGHT_MAX = 1.15  # Cap for micro-weights
MICRO_WEIGHT_STEP = 0.01  # Small step per adjustment
UPLIFT_THRESHOLD_POSITIVE = 0.08  # 8% ROI uplift required to increase
UPLIFT_THRESHOLD_NEGATIVE = -0.08  # -8% ROI uplift required to decrease
MIN_SIGNAL_COUNT = 10  # Minimum occurrences for adjustment
MAX_ADJUSTMENTS_PER_DAY = 3  # Maximum signals to adjust per day per sport
CIRCUIT_BREAKER_RATIO = 0.25  # Reset if 25% of signals at limits


def tune_micro_weights_from_attribution(sport: str, window_days: int = 7) -> Dict[str, Any]:
    """
    v10.32: Tune micro-weights based on signal attribution analysis.

    Rules (SAFE):
    - Only adjust signals with count_present >= 10
    - If uplift >= +8% ROI AND net_units positive: micro_weights[S] += 0.01 (cap 1.15)
    - If uplift <= -8% ROI AND net_units negative: micro_weights[S] -= 0.01 (floor 0.85)
    - No more than 3 signals adjusted per day per sport
    - Circuit breaker: Reset all to 1.00 if 25%+ at limits

    Args:
        sport: Sport code
        window_days: Analysis window

    Returns:
        Tuning result summary
    """
    from signal_attribution import compute_signal_uplift
    from database import DEFAULT_MICRO_WEIGHTS

    # Get attribution data
    attribution = compute_signal_uplift(sport, window_days, min_count=MIN_SIGNAL_COUNT)

    if attribution.get("error"):
        return {
            "sport": sport,
            "tuned": False,
            "reason": attribution.get("error"),
            "micro_weights": {}
        }

    baseline = attribution.get("baseline", {})
    signals = attribution.get("signals", [])

    if baseline.get("picks", 0) < MIN_SETTLED_PICKS:
        return {
            "sport": sport,
            "tuned": False,
            "reason": f"Insufficient data: {baseline.get('picks', 0)} picks (need {MIN_SETTLED_PICKS})",
            "micro_weights": {}
        }

    # Load current config
    config = load_sport_config(sport)
    current_micro_weights = config.get("micro_weights", DEFAULT_MICRO_WEIGHTS.copy())

    # Track changes
    changes = []
    adjustments_made = 0

    # Process signals sorted by absolute uplift (most impactful first)
    signals_sorted = sorted(signals, key=lambda x: abs(x.get("uplift", 0)), reverse=True)

    for signal_data in signals_sorted:
        if adjustments_made >= MAX_ADJUSTMENTS_PER_DAY:
            break

        signal = signal_data.get("signal")
        if not signal:
            continue

        uplift = signal_data.get("uplift", 0) / 100  # Convert to decimal
        net_units = signal_data.get("net_units_present", 0)
        count = signal_data.get("count_present", 0)

        if count < MIN_SIGNAL_COUNT:
            continue

        current_weight = current_micro_weights.get(signal, 1.00)

        # Rule: Increase weight for positive signals
        if uplift >= UPLIFT_THRESHOLD_POSITIVE and net_units > 0:
            new_weight = min(MICRO_WEIGHT_MAX, current_weight + MICRO_WEIGHT_STEP)
            if new_weight != current_weight:
                current_micro_weights[signal] = round(new_weight, 3)
                changes.append({
                    "signal": signal,
                    "old": current_weight,
                    "new": round(new_weight, 3),
                    "direction": "increase",
                    "reason": f"7d uplift +{uplift*100:.1f}%, net +{net_units:.2f}u"
                })
                adjustments_made += 1

        # Rule: Decrease weight for negative signals
        elif uplift <= UPLIFT_THRESHOLD_NEGATIVE and net_units < 0:
            new_weight = max(MICRO_WEIGHT_MIN, current_weight - MICRO_WEIGHT_STEP)
            if new_weight != current_weight:
                current_micro_weights[signal] = round(new_weight, 3)
                changes.append({
                    "signal": signal,
                    "old": current_weight,
                    "new": round(new_weight, 3),
                    "direction": "decrease",
                    "reason": f"7d uplift {uplift*100:.1f}%, net {net_units:.2f}u"
                })
                adjustments_made += 1

    # Circuit breaker check
    at_limits = sum(
        1 for v in current_micro_weights.values()
        if v <= MICRO_WEIGHT_MIN or v >= MICRO_WEIGHT_MAX
    )
    total_signals = len(current_micro_weights)

    if total_signals > 0 and at_limits / total_signals >= CIRCUIT_BREAKER_RATIO:
        # Reset all micro-weights to 1.00
        current_micro_weights = DEFAULT_MICRO_WEIGHTS.copy()
        changes = [{
            "signal": "ALL",
            "old": "mixed",
            "new": 1.00,
            "direction": "reset",
            "reason": f"Circuit breaker: {at_limits}/{total_signals} signals at limits"
        }]
        logger.warning(f"[{sport}] Micro-weights circuit breaker triggered, resetting all to 1.00")

    # Save if changes were made
    if changes:
        config["micro_weights"] = current_micro_weights

        # Build update reason
        if len(changes) == 1 and changes[0].get("signal") == "ALL":
            reason = "v10.32: CIRCUIT_BREAKER_RESET - micro-weights reset to 1.00"
        else:
            reason_parts = [f"v10.32: micro_weight {c['direction']} on {c['signal']} ({c['reason']})" for c in changes[:3]]
            reason = "; ".join(reason_parts)

        save_sport_config(sport, config, reason, {"attribution": attribution.get("baseline")})

        return {
            "sport": sport,
            "tuned": True,
            "adjustments": len(changes),
            "changes": changes,
            "micro_weights": current_micro_weights,
            "circuit_breaker_triggered": changes[0].get("signal") == "ALL" if changes else False
        }
    else:
        return {
            "sport": sport,
            "tuned": False,
            "reason": "No signals qualified for adjustment",
            "micro_weights": current_micro_weights,
            "signals_analyzed": len(signals)
        }


def run_micro_weight_tuning() -> Dict[str, Any]:
    """
    v10.32: Run micro-weight tuning for all sports.

    Returns:
        Combined tuning results
    """
    sports = ["NBA", "NFL", "MLB", "NHL", "NCAAB"]
    results = {}
    tuned_count = 0

    for sport in sports:
        try:
            result = tune_micro_weights_from_attribution(sport)
            results[sport] = result
            if result.get("tuned"):
                tuned_count += 1
        except Exception as e:
            logger.exception(f"Error tuning micro-weights for {sport}: {e}")
            results[sport] = {"error": str(e)}

    return {
        "version": "v10.32",
        "timestamp": datetime.utcnow().isoformat(),
        "sports_tuned": tuned_count,
        "by_sport": results
    }


def get_micro_weight_status(sport: str) -> Dict[str, Any]:
    """
    Get current micro-weight status for a sport.

    Returns:
        Current micro-weights with drift analysis
    """
    from database import DEFAULT_MICRO_WEIGHTS

    config = load_sport_config(sport)
    current_micro_weights = config.get("micro_weights", DEFAULT_MICRO_WEIGHTS.copy())

    # Calculate stats
    at_limits = sum(
        1 for v in current_micro_weights.values()
        if v <= MICRO_WEIGHT_MIN or v >= MICRO_WEIGHT_MAX
    )

    boosted = {k: v for k, v in current_micro_weights.items() if v > 1.00}
    reduced = {k: v for k, v in current_micro_weights.items() if v < 1.00}
    neutral = {k: v for k, v in current_micro_weights.items() if v == 1.00}

    return {
        "sport": sport.upper(),
        "micro_weights": current_micro_weights,
        "summary": {
            "total_signals": len(current_micro_weights),
            "boosted": len(boosted),
            "reduced": len(reduced),
            "neutral": len(neutral),
            "at_limits": at_limits
        },
        "boosted_signals": boosted,
        "reduced_signals": reduced,
        "limits": {
            "min": MICRO_WEIGHT_MIN,
            "max": MICRO_WEIGHT_MAX,
            "step": MICRO_WEIGHT_STEP
        }
    }
