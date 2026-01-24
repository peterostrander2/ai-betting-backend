"""
Pull Readiness System v10.73
============================
Deterministic scheduling + readiness gates for community picks.

Replaces "best pull time" guessing with data-driven readiness checks:
- Injury data freshness
- Splits/sharp money availability
- Props/lines posted status
- Time-to-start windows

Returns PULL_NOW decision with reason codes.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from enum import Enum
import pytz

EST = pytz.timezone("America/New_York")


class ReadinessStatus(str, Enum):
    READY = "READY"
    DEFERRED = "DEFERRED"
    PARTIAL = "PARTIAL"
    NOT_READY = "NOT_READY"


class GateStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"  # Gate not applicable


@dataclass
class GateResult:
    """Result of a single readiness gate check."""
    gate_name: str
    status: GateStatus
    reason: str
    details: Dict = field(default_factory=dict)
    checked_at: str = ""

    def __post_init__(self):
        if not self.checked_at:
            self.checked_at = datetime.now(EST).isoformat()


@dataclass
class PullWindow:
    """A recommended pull window."""
    start_time: str  # "HH:MM" EST
    end_time: str    # "HH:MM" EST
    label: str       # "primary", "refresh", "final"
    sport: str
    day_type: str    # "weekday", "saturday", "sunday"


@dataclass
class ReadinessResult:
    """Complete readiness assessment for a sport."""
    sport: str
    status: ReadinessStatus
    pull_now: bool
    gates: List[GateResult]
    recommended_windows: List[PullWindow]
    reason_codes: List[str]
    next_check_minutes: int = 15
    checked_at: str = ""

    def __post_init__(self):
        if not self.checked_at:
            self.checked_at = datetime.now(EST).isoformat()

    def to_dict(self) -> dict:
        return {
            "sport": self.sport,
            "status": self.status.value,
            "pull_now": self.pull_now,
            "gates": [
                {
                    "gate_name": g.gate_name,
                    "status": g.status.value,
                    "reason": g.reason,
                    "details": g.details,
                    "checked_at": g.checked_at
                }
                for g in self.gates
            ],
            "recommended_windows": [
                {
                    "start_time": w.start_time,
                    "end_time": w.end_time,
                    "label": w.label,
                    "day_type": w.day_type
                }
                for w in self.recommended_windows
            ],
            "reason_codes": self.reason_codes,
            "next_check_minutes": self.next_check_minutes,
            "checked_at": self.checked_at
        }


# ============================================================================
# PULL WINDOW CONFIGURATIONS (EST)
# ============================================================================

PULL_WINDOWS = {
    "ncaab": {
        "weekday": [
            PullWindow("11:15", "11:45", "primary", "ncaab", "weekday"),
            PullWindow("16:45", "17:15", "refresh", "ncaab", "weekday"),
        ],
        "saturday": [
            PullWindow("10:15", "10:45", "primary", "ncaab", "saturday"),
            PullWindow("13:45", "14:15", "midday", "ncaab", "saturday"),
            PullWindow("16:45", "17:15", "evening", "ncaab", "saturday"),
        ],
        "sunday": [
            PullWindow("11:15", "11:45", "primary", "ncaab", "sunday"),
            PullWindow("16:45", "17:15", "refresh", "ncaab", "sunday"),
        ],
    },
    "nba": {
        "weekday": [
            PullWindow("17:25", "17:55", "primary", "nba", "weekday"),
            PullWindow("18:10", "18:30", "refresh", "nba", "weekday"),
        ],
        "saturday": [
            PullWindow("17:25", "17:55", "primary", "nba", "saturday"),
            PullWindow("18:10", "18:30", "refresh", "nba", "saturday"),
        ],
        "sunday": [
            PullWindow("17:25", "17:55", "primary", "nba", "sunday"),
            PullWindow("18:10", "18:30", "refresh", "nba", "sunday"),
        ],
    },
    "nfl": {
        "sunday": [
            PullWindow("10:05", "10:35", "primary", "nfl", "sunday"),
            PullWindow("11:20", "11:50", "final", "nfl", "sunday"),
        ],
        "monday": [
            PullWindow("17:30", "18:00", "primary", "nfl", "monday"),
        ],
        "thursday": [
            PullWindow("17:30", "18:00", "primary", "nfl", "thursday"),
        ],
    },
    "mlb": {
        "weekday": [
            PullWindow("12:00", "12:30", "primary", "mlb", "weekday"),
            PullWindow("17:30", "18:00", "evening", "mlb", "weekday"),
        ],
        "saturday": [
            PullWindow("12:00", "12:30", "primary", "mlb", "saturday"),
            PullWindow("17:30", "18:00", "evening", "mlb", "saturday"),
        ],
        "sunday": [
            PullWindow("12:00", "12:30", "primary", "mlb", "sunday"),
        ],
    },
    "nhl": {
        "weekday": [
            PullWindow("17:30", "18:00", "primary", "nhl", "weekday"),
        ],
        "saturday": [
            PullWindow("17:30", "18:00", "primary", "nhl", "saturday"),
        ],
        "sunday": [
            PullWindow("17:30", "18:00", "primary", "nhl", "sunday"),
        ],
    },
}

# Time-to-start thresholds (minutes)
TIME_TO_START_CONFIG = {
    "nba": {"min": 90, "max": 360},      # 1.5 to 6 hours before
    "ncaab": {"min": 90, "max": 360},    # 1.5 to 6 hours before
    "nfl": {"min": 90, "max": 240},      # 1.5 to 4 hours before
    "mlb": {"min": 60, "max": 300},      # 1 to 5 hours before
    "nhl": {"min": 90, "max": 300},      # 1.5 to 5 hours before
}


# ============================================================================
# GATE CHECK FUNCTIONS
# ============================================================================

def check_injury_gate(
    sport: str,
    injury_data: Optional[Dict] = None,
    last_update: Optional[datetime] = None
) -> GateResult:
    """
    Check injury data freshness.

    Requirements:
    - NBA: Update within last 90 minutes
    - NFL: Sunday inactives must be available on game day
    - NCAAB: Less formal, 120 minute threshold
    """
    now = datetime.now(EST)

    # Freshness thresholds (minutes)
    thresholds = {
        "nba": 90,
        "ncaab": 120,
        "nfl": 90,
        "mlb": 120,
        "nhl": 90,
    }

    threshold = thresholds.get(sport.lower(), 120)

    if last_update is None:
        return GateResult(
            gate_name="INJURY_FRESHNESS",
            status=GateStatus.WARN,
            reason=f"No injury update timestamp available",
            details={"threshold_minutes": threshold, "data_available": injury_data is not None}
        )

    age_minutes = (now - last_update).total_seconds() / 60

    if age_minutes <= threshold:
        return GateResult(
            gate_name="INJURY_FRESHNESS",
            status=GateStatus.PASS,
            reason=f"Injury data fresh ({int(age_minutes)}m old, threshold {threshold}m)",
            details={"age_minutes": int(age_minutes), "threshold_minutes": threshold}
        )
    else:
        return GateResult(
            gate_name="INJURY_FRESHNESS",
            status=GateStatus.WARN,
            reason=f"Injury data stale ({int(age_minutes)}m old, threshold {threshold}m)",
            details={"age_minutes": int(age_minutes), "threshold_minutes": threshold}
        )


def check_splits_gate(
    sport: str,
    splits_data: Optional[List] = None,
    total_games: int = 0,
    last_update: Optional[datetime] = None
) -> GateResult:
    """
    Check splits/sharp money data availability.

    Requirements:
    - Data freshness within 30 minutes
    - At least 70% of games have splits data
    """
    now = datetime.now(EST)

    if splits_data is None or len(splits_data) == 0:
        return GateResult(
            gate_name="SPLITS_AVAILABILITY",
            status=GateStatus.FAIL,
            reason="No splits data available",
            details={"games_with_splits": 0, "total_games": total_games}
        )

    games_with_splits = len(splits_data)

    # Avoid misleading % when total_games is 0
    if total_games == 0:
        coverage_pct = 100.0 if games_with_splits > 0 else 0.0
    else:
        coverage_pct = (games_with_splits / total_games) * 100

    # Check freshness
    freshness_ok = True
    age_minutes = 0
    if last_update:
        age_minutes = (now - last_update).total_seconds() / 60
        freshness_ok = age_minutes <= 30

    if coverage_pct >= 70 and freshness_ok:
        return GateResult(
            gate_name="SPLITS_AVAILABILITY",
            status=GateStatus.PASS,
            reason=f"Splits available for {coverage_pct:.0f}% of games ({games_with_splits}/{total_games})",
            details={
                "games_with_splits": games_with_splits,
                "total_games": total_games,
                "coverage_pct": round(coverage_pct, 1),
                "age_minutes": int(age_minutes)
            }
        )
    elif coverage_pct >= 50:
        return GateResult(
            gate_name="SPLITS_AVAILABILITY",
            status=GateStatus.WARN,
            reason=f"Partial splits coverage ({coverage_pct:.0f}%)",
            details={
                "games_with_splits": games_with_splits,
                "total_games": total_games,
                "coverage_pct": round(coverage_pct, 1),
                "freshness_ok": freshness_ok
            }
        )
    else:
        return GateResult(
            gate_name="SPLITS_AVAILABILITY",
            status=GateStatus.FAIL,
            reason=f"Insufficient splits coverage ({coverage_pct:.0f}%)",
            details={
                "games_with_splits": games_with_splits,
                "total_games": total_games,
                "coverage_pct": round(coverage_pct, 1)
            }
        )


def check_props_gate(
    sport: str,
    props_data: Optional[List] = None,
    total_games: int = 0
) -> GateResult:
    """
    Check props availability.

    Requirements:
    - Props available for at least 60% of games
    """
    if props_data is None:
        props_count = 0
        games_with_props = 0
    else:
        props_count = len(props_data)
        # Estimate games with props (assume ~20 props per game average)
        games_with_props = min(total_games, props_count // 20) if props_count > 0 else 0

    if total_games == 0:
        return GateResult(
            gate_name="PROPS_AVAILABILITY",
            status=GateStatus.SKIP,
            reason="No games to check props for",
            details={"props_count": props_count}
        )

    coverage_pct = (games_with_props / total_games) * 100

    if props_count >= 10 and coverage_pct >= 60:
        return GateResult(
            gate_name="PROPS_AVAILABILITY",
            status=GateStatus.PASS,
            reason=f"Props available: {props_count} props across ~{games_with_props} games",
            details={"props_count": props_count, "estimated_games": games_with_props}
        )
    elif props_count >= 5:
        return GateResult(
            gate_name="PROPS_AVAILABILITY",
            status=GateStatus.WARN,
            reason=f"Limited props: {props_count} props",
            details={"props_count": props_count}
        )
    else:
        return GateResult(
            gate_name="PROPS_AVAILABILITY",
            status=GateStatus.FAIL,
            reason=f"Insufficient props: {props_count}",
            details={"props_count": props_count}
        )


def check_time_to_start_gate(
    sport: str,
    games: Optional[List[Dict]] = None
) -> GateResult:
    """
    Check if we're in the optimal window before game start.

    Target: 90-360 minutes before first game (varies by sport)
    """
    now = datetime.now(EST)
    config = TIME_TO_START_CONFIG.get(sport.lower(), {"min": 90, "max": 360})

    if not games or len(games) == 0:
        return GateResult(
            gate_name="TIME_TO_START",
            status=GateStatus.SKIP,
            reason="No games scheduled",
            details={}
        )

    # Find earliest game start time
    earliest_start = None
    for game in games:
        start_str = game.get("commence_time") or game.get("start_time") or game.get("startTime")
        if start_str:
            try:
                if isinstance(start_str, str):
                    # Parse ISO format
                    start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    start_dt = start_dt.astimezone(EST)
                    if earliest_start is None or start_dt < earliest_start:
                        earliest_start = start_dt
            except:
                pass

    if earliest_start is None:
        return GateResult(
            gate_name="TIME_TO_START",
            status=GateStatus.WARN,
            reason="Could not determine game start times",
            details={}
        )

    minutes_to_start = (earliest_start - now).total_seconds() / 60

    if minutes_to_start < 0:
        return GateResult(
            gate_name="TIME_TO_START",
            status=GateStatus.FAIL,
            reason=f"First game already started ({abs(int(minutes_to_start))}m ago)",
            details={"minutes_to_start": int(minutes_to_start), "first_game": earliest_start.strftime("%I:%M %p ET")}
        )
    elif minutes_to_start < config["min"]:
        return GateResult(
            gate_name="TIME_TO_START",
            status=GateStatus.WARN,
            reason=f"Close to game time ({int(minutes_to_start)}m until first tip)",
            details={"minutes_to_start": int(minutes_to_start), "min_threshold": config["min"]}
        )
    elif minutes_to_start <= config["max"]:
        return GateResult(
            gate_name="TIME_TO_START",
            status=GateStatus.PASS,
            reason=f"Optimal window: {int(minutes_to_start)}m until first tip",
            details={"minutes_to_start": int(minutes_to_start), "window": f"{config['min']}-{config['max']}m"}
        )
    else:
        return GateResult(
            gate_name="TIME_TO_START",
            status=GateStatus.WARN,
            reason=f"Too early: {int(minutes_to_start)}m until first tip (target: {config['max']}m max)",
            details={"minutes_to_start": int(minutes_to_start), "max_threshold": config["max"]}
        )


# ============================================================================
# MAIN READINESS CHECK
# ============================================================================

def get_day_type(now: datetime) -> str:
    """Get day type for pull window lookup."""
    weekday = now.weekday()
    if weekday == 5:  # Saturday
        return "saturday"
    elif weekday == 6:  # Sunday
        return "sunday"
    elif weekday == 0:  # Monday
        return "monday"
    elif weekday == 3:  # Thursday
        return "thursday"
    else:
        return "weekday"


def is_in_window(now: datetime, window: PullWindow) -> bool:
    """Check if current time is within a pull window."""
    start_h, start_m = map(int, window.start_time.split(":"))
    end_h, end_m = map(int, window.end_time.split(":"))

    start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

    return start <= now <= end


def get_recommended_pull_windows(sport: str, now: Optional[datetime] = None) -> List[PullWindow]:
    """Get recommended pull windows for a sport based on current day."""
    if now is None:
        now = datetime.now(EST)

    day_type = get_day_type(now)
    sport_lower = sport.lower()

    sport_windows = PULL_WINDOWS.get(sport_lower, {})
    windows = sport_windows.get(day_type, sport_windows.get("weekday", []))

    return windows


def check_readiness(
    sport: str,
    injury_data: Optional[Dict] = None,
    injury_last_update: Optional[datetime] = None,
    splits_data: Optional[List] = None,
    splits_last_update: Optional[datetime] = None,
    props_data: Optional[List] = None,
    games: Optional[List[Dict]] = None,
    total_games: int = 0,
    now: Optional[datetime] = None
) -> ReadinessResult:
    """
    Main readiness check. Evaluates all gates and returns pull decision.
    """
    if now is None:
        now = datetime.now(EST)

    sport_lower = sport.lower()

    # Run all gate checks
    gates = [
        check_injury_gate(sport_lower, injury_data, injury_last_update),
        check_splits_gate(sport_lower, splits_data, total_games, splits_last_update),
        check_props_gate(sport_lower, props_data, total_games),
        check_time_to_start_gate(sport_lower, games),
    ]

    # Collect reason codes
    reason_codes = []
    for gate in gates:
        if gate.status == GateStatus.FAIL:
            reason_codes.append(f"FAIL:{gate.gate_name}")
        elif gate.status == GateStatus.WARN:
            reason_codes.append(f"WARN:{gate.gate_name}")

    # Determine overall status
    fail_count = sum(1 for g in gates if g.status == GateStatus.FAIL)
    warn_count = sum(1 for g in gates if g.status == GateStatus.WARN)
    pass_count = sum(1 for g in gates if g.status == GateStatus.PASS)

    # Get recommended windows
    windows = get_recommended_pull_windows(sport_lower, now)

    # Check if we're in a pull window
    in_window = any(is_in_window(now, w) for w in windows)

    # Decision logic
    if fail_count >= 2:
        status = ReadinessStatus.NOT_READY
        pull_now = False
        next_check = 30
    elif fail_count == 1:
        status = ReadinessStatus.PARTIAL
        pull_now = in_window  # Pull if in window, but with warnings
        next_check = 15
    elif warn_count >= 2:
        status = ReadinessStatus.PARTIAL
        pull_now = in_window
        next_check = 15
    else:
        status = ReadinessStatus.READY
        pull_now = True
        next_check = 60

    # Override: if in a pull window and not completely failing, allow pull
    if in_window and fail_count < 2:
        pull_now = True
        if status == ReadinessStatus.NOT_READY:
            status = ReadinessStatus.PARTIAL

    return ReadinessResult(
        sport=sport.upper(),
        status=status,
        pull_now=pull_now,
        gates=gates,
        recommended_windows=windows,
        reason_codes=reason_codes,
        next_check_minutes=next_check
    )


# ============================================================================
# ENGINE COMPLETENESS VALIDATION
# ============================================================================

REQUIRED_ENGINES = [
    "AI_ENGINE",
    "RESEARCH_ENGINE",
    "ESOTERIC_EDGE",
    "JARVIS_ENGINE",
    "JASON_SIM"
]


@dataclass
class EngineAudit:
    """Audit result for engine completeness on a pick."""
    engines_expected: List[str]
    engines_ran: List[str]
    engines_missing: List[str]
    complete: bool
    completeness_pct: float

    def to_dict(self) -> dict:
        return {
            "engines_expected": self.engines_expected,
            "engines_ran": self.engines_ran,
            "engines_missing": self.engines_missing,
            "complete": self.complete,
            "completeness_pct": self.completeness_pct
        }


def audit_pick_engines(pick: Dict) -> EngineAudit:
    """
    Audit a pick for engine completeness.

    Checks reasons[] and scoring fields to determine which engines ran.
    """
    engines_ran = []
    reasons = pick.get("reasons", [])
    reasons_lower = " ".join(reasons).lower()

    # Check AI_ENGINE
    ai_indicators = ["ai engine", "ensemble", "lstm", "monte carlo", "matchup", "line movement", "rest", "injury", "betting edge"]
    if any(ind in reasons_lower for ind in ai_indicators) or pick.get("ai_score") is not None:
        engines_ran.append("AI_ENGINE")

    # Check RESEARCH_ENGINE
    research_indicators = ["research", "sharp", "rlm", "reverse line", "public fade", "hospital", "goldilocks", "pillar"]
    if any(ind in reasons_lower for ind in research_indicators) or pick.get("research_score") is not None:
        engines_ran.append("RESEARCH_ENGINE")

    # Check ESOTERIC_EDGE
    esoteric_indicators = ["esoteric", "void moon", "planetary", "fibonacci", "noosphere", "schumann", "astro"]
    if any(ind in reasons_lower for ind in esoteric_indicators) or pick.get("esoteric_score") is not None:
        engines_ran.append("ESOTERIC_EDGE")

    # Check JARVIS_ENGINE
    jarvis_indicators = ["jarvis", "gematria", "sacred", "trigger", "2178", "201", "33", "93", "322", "47", "88"]
    if any(ind in reasons_lower for ind in jarvis_indicators) or pick.get("jarvis_rs") is not None:
        engines_ran.append("JARVIS_ENGINE")

    # Check JASON_SIM
    jason_indicators = ["jason", "sim", "confluence", "boost", "downgrade", "block"]
    if any(ind in reasons_lower for ind in jason_indicators) or pick.get("jason_sim_applied"):
        engines_ran.append("JASON_SIM")

    engines_missing = [e for e in REQUIRED_ENGINES if e not in engines_ran]
    complete = len(engines_missing) == 0
    completeness_pct = (len(engines_ran) / len(REQUIRED_ENGINES)) * 100

    return EngineAudit(
        engines_expected=REQUIRED_ENGINES.copy(),
        engines_ran=engines_ran,
        engines_missing=engines_missing,
        complete=complete,
        completeness_pct=round(completeness_pct, 1)
    )


def validate_pick_pipeline(pick: Dict) -> Tuple[bool, str, EngineAudit]:
    """
    Validate that a pick went through the complete pipeline.

    Returns: (valid, fail_reason, audit)
    """
    audit = audit_pick_engines(pick)

    if audit.complete:
        return True, "", audit

    # Determine fail reason
    if "AI_ENGINE" not in audit.engines_ran:
        return False, "AI_ENGINE not executed", audit

    if "JARVIS_ENGINE" not in audit.engines_ran:
        return False, "JARVIS_ENGINE not executed", audit

    if "JASON_SIM" not in audit.engines_ran:
        return False, "JASON_SIM not executed", audit

    # Partial is acceptable for esoteric/research
    if audit.completeness_pct >= 60:
        return True, f"Partial: missing {', '.join(audit.engines_missing)}", audit

    return False, f"Incomplete pipeline: {', '.join(audit.engines_missing)}", audit
