"""
Time Status Module v10.75
=========================
Single source of truth for game/pick time state detection.

States:
- PREGAME: More than 5 minutes before game start (safe to bet)
- LOCKED: Within 5 minutes of start to 10 minutes after (caution)
- STARTED: More than 10 minutes after start (LIVE-BET ONLY)
- FINAL: Game completed (archive)
- UNKNOWN: Cannot determine time state

Used to label picks for live-bet eligibility across ALL sports.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import pytz

ET = pytz.timezone("America/New_York")


class TimeState:
    """Time state constants."""
    PREGAME = "PREGAME"
    LOCKED = "LOCKED"      # Within 5 min of start
    STARTED = "STARTED"
    FINAL = "FINAL"
    UNKNOWN = "UNKNOWN"


class Recommendation:
    """Recommendation constants."""
    PREGAME_OK = "PREGAME_OK"
    LIVE_ONLY = "LIVE_ONLY"
    ARCHIVE = "ARCHIVE"
    UNKNOWN = "UNKNOWN"


class LiveBand:
    """Live game bands."""
    EARLY = "EARLY"   # 0-15 min since start
    MID = "MID"       # 16-45 min since start
    LATE = "LATE"     # >45 min since start


def parse_time(time_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO time string to datetime with ET timezone."""
    if not time_str:
        return None

    try:
        # Handle various formats
        if isinstance(time_str, datetime):
            dt = time_str
        elif "Z" in time_str:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        elif "+" in time_str or time_str.endswith("-00:00"):
            dt = datetime.fromisoformat(time_str)
        else:
            # Assume UTC if no timezone
            dt = datetime.fromisoformat(time_str)
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)

        return dt.astimezone(ET)
    except Exception:
        return None


def compute_time_status(
    start_time: Optional[str],
    pulled_at: Optional[str] = None,
    game_state: Optional[str] = None
) -> Dict:
    """
    Compute time status for a pick.

    Args:
        start_time: Game start time (ISO string or datetime)
        pulled_at: Time when pick was pulled (defaults to now)
        game_state: Optional game state from score feed ("final", "in_progress", etc.)

    Returns:
        Dict with time status fields:
        - state: PREGAME | LOCKED | STARTED | FINAL | UNKNOWN
        - minutes_to_start: int (negative if started)
        - minutes_since_start: int (0 if not started)
        - live_eligible: bool
        - recommendation: PREGAME_OK | LIVE_ONLY | ARCHIVE | UNKNOWN
        - live_band: EARLY | MID | LATE | None
        - start_time_et: str (ISO)
        - pulled_at_et: str (ISO)
    """
    now_et = datetime.now(ET)

    # Parse pulled_at or use now
    if pulled_at:
        pulled_dt = parse_time(pulled_at)
        if pulled_dt is None:
            pulled_dt = now_et
    else:
        pulled_dt = now_et

    pulled_at_et = pulled_dt.isoformat()

    # Parse start time
    start_dt = parse_time(start_time)

    if start_dt is None:
        return {
            "state": TimeState.UNKNOWN,
            "minutes_to_start": 0,
            "minutes_since_start": 0,
            "live_eligible": False,
            "recommendation": Recommendation.UNKNOWN,
            "live_band": None,
            "start_time_et": None,
            "pulled_at_et": pulled_at_et
        }

    start_time_et = start_dt.isoformat()

    # Check if game is final from score feed
    if game_state:
        game_state_lower = game_state.lower()
        if game_state_lower in ("final", "finished", "completed", "post"):
            return {
                "state": TimeState.FINAL,
                "minutes_to_start": 0,
                "minutes_since_start": 0,
                "live_eligible": False,
                "recommendation": Recommendation.ARCHIVE,
                "live_band": None,
                "start_time_et": start_time_et,
                "pulled_at_et": pulled_at_et
            }

    # Calculate time difference
    diff = pulled_dt - start_dt
    diff_minutes = diff.total_seconds() / 60

    # Determine state based on time
    if diff_minutes < -5:
        # More than 5 minutes before start → PREGAME
        minutes_to_start = int(abs(diff_minutes))
        return {
            "state": TimeState.PREGAME,
            "minutes_to_start": minutes_to_start,
            "minutes_since_start": 0,
            "live_eligible": False,
            "recommendation": Recommendation.PREGAME_OK,
            "live_band": None,
            "start_time_et": start_time_et,
            "pulled_at_et": pulled_at_et
        }

    elif -5 <= diff_minutes <= 10:
        # Within 5 min before to 10 min after start → LOCKED
        if diff_minutes < 0:
            minutes_to_start = int(abs(diff_minutes))
            minutes_since_start = 0
        else:
            minutes_to_start = 0
            minutes_since_start = int(diff_minutes)

        return {
            "state": TimeState.LOCKED,
            "minutes_to_start": minutes_to_start,
            "minutes_since_start": minutes_since_start,
            "live_eligible": False,
            "recommendation": Recommendation.PREGAME_OK,
            "live_band": None,
            "start_time_et": start_time_et,
            "pulled_at_et": pulled_at_et
        }

    else:
        # More than 10 minutes after start → STARTED
        minutes_since_start = int(diff_minutes)

        # Determine live band
        if minutes_since_start <= 15:
            live_band = LiveBand.EARLY
        elif minutes_since_start <= 45:
            live_band = LiveBand.MID
        else:
            live_band = LiveBand.LATE

        return {
            "state": TimeState.STARTED,
            "minutes_to_start": -minutes_since_start,
            "minutes_since_start": minutes_since_start,
            "live_eligible": True,
            "recommendation": Recommendation.LIVE_ONLY,
            "live_band": live_band,
            "start_time_et": start_time_et,
            "pulled_at_et": pulled_at_et
        }


def format_time_status(status: Dict) -> str:
    """
    Format time status for terminal display.

    Returns human-readable string like:
    - "PREGAME (T-45m)"
    - "STARTED (+61m) → LIVE BET ONLY"
    - "FINAL → ARCHIVE"
    """
    state = status.get("state", TimeState.UNKNOWN)

    if state == TimeState.PREGAME:
        mins = status.get("minutes_to_start", 0)
        return f"PREGAME (T-{mins}m)"

    elif state == TimeState.LOCKED:
        mins_to = status.get("minutes_to_start", 0)
        mins_since = status.get("minutes_since_start", 0)
        if mins_to > 0:
            return f"LOCKED (T-{mins_to}m)"
        else:
            return f"LOCKED (+{mins_since}m)"

    elif state == TimeState.STARTED:
        mins = status.get("minutes_since_start", 0)
        band = status.get("live_band", "")
        band_str = f" [{band}]" if band else ""
        return f"STARTED (+{mins}m){band_str} → LIVE BET ONLY"

    elif state == TimeState.FINAL:
        return "FINAL → ARCHIVE"

    else:
        return "UNKNOWN"


def get_time_state_summary(picks: list) -> Dict:
    """
    Get summary counts of time states across picks.

    Returns:
        {
            "pregame_count": int,
            "locked_count": int,
            "started_count": int,
            "final_count": int,
            "unknown_count": int,
            "live_eligible_count": int
        }
    """
    counts = {
        "pregame_count": 0,
        "locked_count": 0,
        "started_count": 0,
        "final_count": 0,
        "unknown_count": 0,
        "live_eligible_count": 0
    }

    for pick in picks:
        status = pick.get("status_time", {})
        state = status.get("state", TimeState.UNKNOWN)

        if state == TimeState.PREGAME:
            counts["pregame_count"] += 1
        elif state == TimeState.LOCKED:
            counts["locked_count"] += 1
        elif state == TimeState.STARTED:
            counts["started_count"] += 1
        elif state == TimeState.FINAL:
            counts["final_count"] += 1
        else:
            counts["unknown_count"] += 1

        # Count live-eligible picks (STARTED state sets live_eligible=True)
        if status.get("live_eligible"):
            counts["live_eligible_count"] += 1

    return counts
