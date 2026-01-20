"""
v10.32 Signal Attribution Engine

Responsibilities:
1. Parse reasons[] into normalized fired_signals[]
2. Compute ROI uplift per signal
3. Produce ranked attribution output per sport

This module enables the system to identify which signals actually predict wins
and provides data for micro-weight tuning.
"""
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from database import (
    get_db, get_graded_picks_for_window, PickLedger, PickResult,
    DEFAULT_MICRO_WEIGHTS
)

logger = logging.getLogger(__name__)

# ============================================================================
# SIGNAL NORMALIZATION MAPPING
# ============================================================================

# Prefix patterns for reason string matching
SIGNAL_PATTERNS = {
    # RESEARCH/PILLAR signals
    r"RESEARCH:\s*Sharp\s*Split": "PILLAR_SHARP_SPLIT",
    r"RESEARCH:\s*Reverse\s*Line\s*Move": "PILLAR_RLM",
    r"RESEARCH:\s*RLM": "PILLAR_RLM",
    r"RESEARCH:\s*Hospital\s*Fade": "PILLAR_HOSPITAL_FADE",
    r"RESEARCH:\s*Situational": "PILLAR_SITUATIONAL",
    r"RESEARCH:\s*Expert\s*Consensus": "PILLAR_EXPERT_CONSENSUS",
    r"RESEARCH:\s*Public\s*Fade": "SIGNAL_PUBLIC_FADE",
    r"RESEARCH:\s*Line\s*Value": "SIGNAL_LINE_VALUE",
    r"RESEARCH:\s*Hook\s*Discipline": "PILLAR_HOOK_DISCIPLINE",
    r"RESEARCH:\s*Prop\s*Correlation": "PILLAR_PROP_CORRELATION",
    r"RESEARCH:\s*Volume": "PILLAR_VOLUME_DISCIPLINE",
    r"RESEARCH:\s*Goldilocks": "SIGNAL_GOLDILOCKS",
    r"RESEARCH:\s*Trap\s*Gate": "SIGNAL_TRAP_GATE",
    r"RESEARCH:\s*High\s*Total": "SIGNAL_HIGH_TOTAL",
    r"RESEARCH:\s*Multi-Pillar": "SIGNAL_MULTI_PILLAR",

    # ESOTERIC signals
    r"ESOTERIC:\s*Gematria": "ESOTERIC_GEMATRIA",
    r"ESOTERIC:\s*Jarvis\s*Trigger": "ESOTERIC_JARVIS_TRIGGER",
    r"ESOTERIC:\s*Jarvis": "ESOTERIC_JARVIS_TRIGGER",
    r"ESOTERIC:\s*Astrology": "ESOTERIC_ASTRO",
    r"ESOTERIC:\s*Astro": "ESOTERIC_ASTRO",
    r"ESOTERIC:\s*Fibonacci": "ESOTERIC_FIBONACCI",
    r"ESOTERIC:\s*Numerology": "ESOTERIC_NUMEROLOGY",
    r"ESOTERIC:\s*Moon": "ESOTERIC_MOON_PHASE",
    r"ESOTERIC:\s*Tesla": "ESOTERIC_TESLA",
    r"ESOTERIC:\s*Daily\s*Energy": "ESOTERIC_DAILY_ENERGY",
    r"ESOTERIC:\s*Power\s*Number": "ESOTERIC_POWER_NUMBER",

    # CONFLUENCE signals
    r"CONFLUENCE:": "CONFLUENCE_BONUS",
    r"CONFLUENCE_LADDER:": "CONFLUENCE_BONUS",

    # CORRELATION signals
    r"CORRELATION:\s*ALIGNED": "CORRELATION_ALIGNED",
    r"CORRELATION:\s*CONFLICT": "CORRELATION_CONFLICT",
    r"CORRELATION:\s*NO_SIGNAL": "CORRELATION_NO_SIGNAL",

    # MAPPING signals
    r"MAPPING:": "MAPPING_TEAM",
}

# Patterns to IGNORE (system/admin messages)
IGNORE_PATTERNS = [
    r"RESOLVER:",
    r"GOVERNOR:",
    r"SYSTEM:",
    r"DEBUG:",
    r"WARNING:",
    r"FILTER:",
    r"VOLUME_CAP:",
]


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================

def normalize_reason_to_signal(reason: str) -> Optional[str]:
    """
    Convert a reason string to a normalized signal key.

    Args:
        reason: Raw reason string like "RESEARCH: Sharp Split (GAME) +0.5"

    Returns:
        Normalized signal key like "PILLAR_SHARP_SPLIT" or None if not a signal
    """
    if not reason or not isinstance(reason, str):
        return None

    # Check ignore patterns first
    for ignore_pattern in IGNORE_PATTERNS:
        if re.search(ignore_pattern, reason, re.IGNORECASE):
            return None

    # Try to match signal patterns
    for pattern, signal_key in SIGNAL_PATTERNS.items():
        if re.search(pattern, reason, re.IGNORECASE):
            return signal_key

    return None


def extract_fired_signals(pick: Dict[str, Any]) -> List[str]:
    """
    Extract and normalize all fired signals from a pick's reasons.

    Args:
        pick: Pick dictionary with 'reasons' field (list of strings)

    Returns:
        Sorted unique list of normalized signal keys
    """
    reasons = pick.get("reasons", [])

    # Handle JSON string if needed
    if isinstance(reasons, str):
        try:
            reasons = json.loads(reasons)
        except (json.JSONDecodeError, TypeError):
            reasons = []

    if not isinstance(reasons, list):
        reasons = []

    fired = set()
    for reason in reasons:
        signal_key = normalize_reason_to_signal(reason)
        if signal_key:
            fired.add(signal_key)

    return sorted(list(fired))


def extract_components(pick: Dict[str, Any]) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Extract research and esoteric component weights from pick reasons.

    Returns:
        Tuple of (research_components dict, esoteric_components dict)
    """
    reasons = pick.get("reasons", [])

    if isinstance(reasons, str):
        try:
            reasons = json.loads(reasons)
        except (json.JSONDecodeError, TypeError):
            reasons = []

    research_components = {}
    esoteric_components = {}

    for reason in reasons:
        if not isinstance(reason, str):
            continue

        signal_key = normalize_reason_to_signal(reason)
        if not signal_key:
            continue

        # Try to extract the boost value from the reason
        # Format: "RESEARCH: Sharp Split (GAME ALIGNED x0.50) +0.52"
        boost_match = re.search(r'[+-]?(\d+\.?\d*)\s*$', reason)
        boost_value = float(boost_match.group(1)) if boost_match else 0.0

        # Categorize by signal type
        if signal_key.startswith("PILLAR_") or signal_key.startswith("SIGNAL_"):
            research_components[signal_key] = boost_value
        elif signal_key.startswith("ESOTERIC_"):
            esoteric_components[signal_key] = boost_value
        elif signal_key == "CONFLUENCE_BONUS":
            # Could go either way, put in research
            research_components[signal_key] = boost_value
        elif signal_key.startswith("CORRELATION_"):
            research_components[signal_key] = boost_value

    return research_components, esoteric_components


# ============================================================================
# ROI CALCULATION
# ============================================================================

def compute_signal_uplift(
    sport: str,
    window_days: int = 7,
    min_count: int = 8
) -> Dict[str, Any]:
    """
    Compute ROI uplift for each signal based on graded picks.

    For each signal S:
    - ROI_when_present = net_units / units_wagered (picks where S fired)
    - ROI_when_absent = net_units / units_wagered (picks where S didn't fire)
    - uplift = ROI_present - ROI_absent

    Args:
        sport: Sport code (NBA, NFL, etc.)
        window_days: Rolling window in days
        min_count: Minimum occurrences for a signal to be included

    Returns:
        Dict with baseline stats and signal uplifts
    """
    with get_db() as db:
        if db is None:
            return {"error": "Database not available"}

        picks = get_graded_picks_for_window(sport, window_days, db)

    if not picks:
        return {
            "sport": sport.upper(),
            "window_days": window_days,
            "baseline": {"picks": 0, "net_units": 0, "units_wagered": 0, "roi": 0},
            "signals": [],
            "message": "No graded picks found for this period"
        }

    # Parse fired signals from each pick
    pick_data = []
    for pick in picks:
        try:
            fired_signals_raw = pick.fired_signals
            if isinstance(fired_signals_raw, str):
                fired_signals = json.loads(fired_signals_raw) if fired_signals_raw else []
            else:
                fired_signals = fired_signals_raw or []

            # Fallback: parse from reasons if fired_signals not populated
            if not fired_signals and pick.reasons:
                reasons = json.loads(pick.reasons) if isinstance(pick.reasons, str) else pick.reasons
                fired_signals = extract_fired_signals({"reasons": reasons})

            units = pick.recommended_units or 0.5
            profit = pick.profit_units or 0.0

            pick_data.append({
                "pick_uid": pick.pick_uid,
                "fired_signals": set(fired_signals),
                "units_wagered": units,
                "profit_units": profit,
                "result": pick.result.value if pick.result else "PENDING",
                "confidence_grade": pick.confidence_grade,
                "confluence_level": pick.confluence_level,
            })
        except Exception as e:
            logger.debug(f"Error parsing pick {pick.pick_uid}: {e}")
            continue

    if not pick_data:
        return {
            "sport": sport.upper(),
            "window_days": window_days,
            "baseline": {"picks": 0, "net_units": 0, "units_wagered": 0, "roi": 0},
            "signals": [],
            "message": "No valid pick data found"
        }

    # Calculate baseline
    total_units = sum(p["units_wagered"] for p in pick_data)
    total_profit = sum(p["profit_units"] for p in pick_data)
    baseline_roi = (total_profit / total_units * 100) if total_units > 0 else 0

    baseline = {
        "picks": len(pick_data),
        "units_wagered": round(total_units, 2),
        "net_units": round(total_profit, 2),
        "roi": round(baseline_roi, 2)
    }

    # Collect all unique signals
    all_signals = set()
    for p in pick_data:
        all_signals.update(p["fired_signals"])

    # Calculate uplift for each signal
    signal_uplifts = []
    for signal in all_signals:
        # Picks where signal fired
        present_picks = [p for p in pick_data if signal in p["fired_signals"]]
        # Picks where signal didn't fire
        absent_picks = [p for p in pick_data if signal not in p["fired_signals"]]

        if len(present_picks) < min_count:
            continue

        # ROI when present
        present_units = sum(p["units_wagered"] for p in present_picks)
        present_profit = sum(p["profit_units"] for p in present_picks)
        roi_present = (present_profit / present_units * 100) if present_units > 0 else 0

        # ROI when absent
        absent_units = sum(p["units_wagered"] for p in absent_picks)
        absent_profit = sum(p["profit_units"] for p in absent_picks)
        roi_absent = (absent_profit / absent_units * 100) if absent_units > 0 else 0

        # Uplift
        uplift = roi_present - roi_absent

        # Win rate when present
        present_wins = len([p for p in present_picks if p["result"] == "WIN"])
        win_rate = (present_wins / len(present_picks) * 100) if present_picks else 0

        signal_uplifts.append({
            "signal": signal,
            "count_present": len(present_picks),
            "count_absent": len(absent_picks),
            "roi_present": round(roi_present, 2),
            "roi_absent": round(roi_absent, 2),
            "uplift": round(uplift, 2),
            "net_units_present": round(present_profit, 2),
            "win_rate": round(win_rate, 1),
        })

    # Sort by uplift (descending)
    signal_uplifts.sort(key=lambda x: x["uplift"], reverse=True)

    return {
        "sport": sport.upper(),
        "window_days": window_days,
        "baseline": baseline,
        "signals": signal_uplifts,
        "timestamp": datetime.utcnow().isoformat()
    }


def compute_feature_table(sport: str, window_days: int = 7) -> Dict[str, Any]:
    """
    Compute comprehensive attribution report for a sport.

    Returns:
        Dict with baseline, top signals, confluence performance, grade performance
    """
    with get_db() as db:
        if db is None:
            return {"error": "Database not available"}

        picks = get_graded_picks_for_window(sport, window_days, db)

    if not picks:
        return {
            "sport": sport.upper(),
            "window_days": window_days,
            "baseline": {"picks": 0, "net_units": 0, "roi": 0},
            "top_positive_signals": [],
            "top_negative_signals": [],
            "confluence_performance": {},
            "grade_performance": {},
            "message": "No graded picks found"
        }

    # Get signal uplift data
    uplift_data = compute_signal_uplift(sport, window_days)

    # Separate positive and negative signals
    positive_signals = [s for s in uplift_data.get("signals", []) if s["uplift"] > 0]
    negative_signals = [s for s in uplift_data.get("signals", []) if s["uplift"] < 0]

    # Sort negative by worst first
    negative_signals.sort(key=lambda x: x["uplift"])

    # Performance by confluence level
    confluence_performance = {}
    for pick in picks:
        level = pick.confluence_level or "NONE"
        if level not in confluence_performance:
            confluence_performance[level] = {"picks": 0, "units": 0, "profit": 0}

        units = pick.recommended_units or 0.5
        profit = pick.profit_units or 0.0

        confluence_performance[level]["picks"] += 1
        confluence_performance[level]["units"] += units
        confluence_performance[level]["profit"] += profit

    # Calculate ROI for each confluence level
    for level, data in confluence_performance.items():
        data["roi"] = round((data["profit"] / data["units"] * 100) if data["units"] > 0 else 0, 2)
        data["units"] = round(data["units"], 2)
        data["profit"] = round(data["profit"], 2)

    # Performance by confidence grade
    grade_performance = {}
    for pick in picks:
        grade = pick.confidence_grade or "C"
        if grade not in grade_performance:
            grade_performance[grade] = {"picks": 0, "units": 0, "profit": 0, "wins": 0}

        units = pick.recommended_units or 0.5
        profit = pick.profit_units or 0.0

        grade_performance[grade]["picks"] += 1
        grade_performance[grade]["units"] += units
        grade_performance[grade]["profit"] += profit
        if pick.result == PickResult.WIN:
            grade_performance[grade]["wins"] += 1

    # Calculate ROI and win rate for each grade
    for grade, data in grade_performance.items():
        data["roi"] = round((data["profit"] / data["units"] * 100) if data["units"] > 0 else 0, 2)
        data["win_rate"] = round((data["wins"] / data["picks"] * 100) if data["picks"] > 0 else 0, 1)
        data["units"] = round(data["units"], 2)
        data["profit"] = round(data["profit"], 2)

    return {
        "sport": sport.upper(),
        "window_days": window_days,
        "baseline": uplift_data.get("baseline", {}),
        "top_positive_signals": positive_signals[:10],
        "top_negative_signals": negative_signals[:10],
        "confluence_performance": confluence_performance,
        "grade_performance": grade_performance,
        "total_signals_analyzed": len(uplift_data.get("signals", [])),
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# HELPER FUNCTIONS FOR PICK ENRICHMENT
# ============================================================================

def enrich_pick_with_signals(pick: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add fired_signals and components to a pick before returning it.

    This should be called before saving a pick to the ledger.
    """
    # Extract fired signals
    fired_signals = extract_fired_signals(pick)
    pick["fired_signals"] = fired_signals
    pick["fired_signal_count"] = len(fired_signals)

    # Extract component breakdowns
    research_components, esoteric_components = extract_components(pick)
    pick["research_components"] = research_components
    pick["esoteric_components"] = esoteric_components

    return pick


def get_signal_summary(signals: List[str]) -> str:
    """
    Get a human-readable summary of fired signals.
    """
    if not signals:
        return "No signals fired"

    pillar_count = len([s for s in signals if s.startswith("PILLAR_")])
    esoteric_count = len([s for s in signals if s.startswith("ESOTERIC_")])
    other_count = len(signals) - pillar_count - esoteric_count

    parts = []
    if pillar_count > 0:
        parts.append(f"{pillar_count} pillars")
    if esoteric_count > 0:
        parts.append(f"{esoteric_count} esoteric")
    if other_count > 0:
        parts.append(f"{other_count} other")

    return ", ".join(parts)
