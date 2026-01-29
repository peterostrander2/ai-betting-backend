"""
PICK_LOGGER.PY - Production Pick Logging & Grading System
==========================================================
v14.11 - Full E2E verification with run_id and deduplication

Features:
- Log picks with full transparency fields
- Already_started detection for late pulls
- Today-only EST date enforcement
- Book availability validation
- Daily audit report generation
- run_id for batch tracking and deduplication
- pick_hash for deterministic uniqueness
- Grade-ready checklist for autograder validation

Usage:
    from pick_logger import (
        get_pick_logger,
        log_published_pick,
        grade_pick,
        run_daily_audit_report,
        check_grade_ready
    )
"""

import os
import json
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict, field, fields as dataclass_fields
from collections import defaultdict
import logging

# Try to import pytz for timezone handling
try:
    import pytz
    PYTZ_AVAILABLE = True
    ET = pytz.timezone("America/New_York")
    UTC = pytz.UTC
except ImportError:
    PYTZ_AVAILABLE = False
    ET = None
    UTC = None

logger = logging.getLogger("pick_logger")


# =============================================================================
# BOOK FIELD ENFORCEMENT (CRITICAL FIX)
# =============================================================================

def _ensure_book_fields(pick_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce book_key, book, sportsbook_name, sportsbook_event_url defaults.

    CRITICAL FIX: Never allow empty book_key (breaks grading).
    Fallback: "consensus" for all book fields if missing.

    Applied at:
    1. Serialization before API response
    2. Before writing to pick_logs
    3. When loading from pick_logs (auto-heal legacy rows)
    """
    book = pick_data.get("book", "")
    book_key = pick_data.get("book_key", "")

    # If book_key is empty, use fallback
    if not book_key:
        book_key = "consensus"

    # If book is empty, use fallback
    if not book:
        book = "Consensus"

    # Update pick_data with corrected values
    pick_data["book_key"] = book_key
    pick_data["book"] = book
    pick_data["sportsbook_name"] = pick_data.get("sportsbook_name") or book
    pick_data["sportsbook_event_url"] = pick_data.get("sportsbook_event_url") or ""

    return pick_data


# =============================================================================
# CONFIGURATION
# =============================================================================

from data_dir import PICK_LOGS, GRADED_PICKS

STORAGE_PATH = PICK_LOGS
GRADED_PATH = GRADED_PICKS

# Books we validate against
SUPPORTED_BOOKS = {
    "draftkings", "fanduel", "betmgm", "caesars", "pointsbet",
    "barstool", "wynnbet", "betrivers", "fanatics", "espnbet"
}

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PublishedPick:
    """Full pick record with v14.9 transparency fields."""
    # Identification
    pick_id: str
    date: str  # YYYY-MM-DD in ET
    sport: str

    # Pick details
    pick_type: str  # PROP, SPREAD, TOTAL, MONEYLINE, SHARP
    player_name: str = ""
    matchup: str = ""
    home_team: str = ""
    away_team: str = ""
    prop_type: str = ""
    line: float = 0.0
    side: str = ""  # Over/Under or team name
    odds: int = -110
    book: str = ""
    book_link: str = ""

    # Timing
    game_start_time_et: str = ""  # Human-readable time (e.g., "7:30 PM ET")
    commence_time_iso: str = ""  # Programmatic ISO timestamp (e.g., "2026-01-28T19:30:00Z")
    published_at: str = ""
    already_started: bool = False
    late_pull_reason: str = ""

    # Engine scores (0-10 scale)
    ai_score: float = 0.0
    research_score: float = 0.0
    esoteric_score: float = 0.0
    jarvis_score: float = 0.0
    final_score: float = 0.0

    # Tier
    tier: str = "PASS"
    titanium_flag: bool = False
    units: float = 0.0

    # Research breakdown
    research_breakdown: Dict = field(default_factory=dict)
    research_reasons: List[str] = field(default_factory=list)
    pillars_passed: List[str] = field(default_factory=list)
    pillars_failed: List[str] = field(default_factory=list)

    # Jason Sim fields
    jason_ran: bool = False
    jason_sim_boost: float = 0.0
    jason_blocked: bool = False
    jason_win_pct_home: float = 50.0
    jason_win_pct_away: float = 50.0
    confluence_reasons: List[str] = field(default_factory=list)

    # Jarvis fields
    jarvis_triggers_hit: List[Dict] = field(default_factory=list)
    jarvis_reasons: List[str] = field(default_factory=list)

    # Validation
    injury_status: str = "HEALTHY"
    book_validated: bool = True
    validation_errors: List[str] = field(default_factory=list)

    # Grading (filled in after game)
    result: Optional[str] = None  # WIN, LOSS, PUSH
    actual_value: Optional[float] = None
    units_won_lost: Optional[float] = None
    graded_at: Optional[str] = None

    # === NEW FIELDS FOR E2E VERIFICATION (v14.10) ===

    # Grading status
    graded: bool = False
    grade_result: Optional[str] = None  # WIN/LOSS/PUSH (alias of result)

    # Event identity (cross-provider mapping)
    canonical_event_id: str = ""
    provider_event_ids: Dict[str, str] = field(default_factory=dict)
    # {"odds_api": "abc123", "balldontlie": "12345", "playbook": "PLY-456"}

    # Player identity (for props)
    canonical_player_id: str = ""
    provider_player_ids: Dict[str, Any] = field(default_factory=dict)
    # {"balldontlie": 237, "odds_api": None, "playbook": "LBJ-001"}

    # Line/odds snapshot at bet time
    line_at_bet: float = 0.0
    odds_at_bet: int = -110
    timestamp_at_bet: str = ""

    # Closing line value
    closing_line: Optional[float] = None
    closing_odds: Optional[int] = None
    clv: Optional[float] = None  # Positive = beat the market

    # Event status tracking
    event_status: str = "NOT_STARTED"  # NOT_STARTED, IN_PROGRESS, FINAL

    # === NEW FIELDS FOR RUN TRACKING (v14.11) ===

    # Run ID for batch tracking and deduplication
    run_id: str = ""  # UUID for each best-bets execution

    # Pick hash for deterministic uniqueness
    pick_hash: str = ""  # SHA256 hash of pick key fields

    # Grade status for verification
    grade_status: str = "PENDING"  # PENDING, WAITING_FINAL, GRADED, FAILED, UNRESOLVED

    # Retry tracking for grading state machine
    retry_count: int = 0
    last_error: str = ""
    last_attempt_at: str = ""

    # Book/market fields for grade-ready checklist
    book_key: str = ""  # Canonical book identifier
    market: str = ""  # Market type (spread, total, moneyline, player_points, etc.)

    # Jason Sim v2 additional fields
    jason_sim_available: bool = False  # Whether sim ran successfully
    variance_flag: str = ""  # HIGH, MED, LOW
    injury_state: str = "CONFIRMED_ONLY"  # Injury handling mode
    sim_count: int = 0  # Number of simulations run

    # Signals and explainability
    signals_firing: List[str] = field(default_factory=list)
    engine_breakdown: Dict[str, Any] = field(default_factory=dict)
    vacuum_flags: List[str] = field(default_factory=list)
    titanium_reasons: List[str] = field(default_factory=list)

    # Live betting context
    is_live: bool = False
    live_context: Dict[str, Any] = field(default_factory=dict)
    is_started_already: bool = False  # Alias for already_started

    # Sportsbook details
    sportsbook_name: str = ""
    sportsbook_event_url: Optional[str] = None

    # League (for frontend display)
    league: str = ""  # Same as sport for now

    # Status for frontend
    status: str = "scheduled"  # scheduled, live, final

    # Base score (pre-jason)
    base_score: float = 0.0

    # Tier badge for frontend
    tier_badge: str = ""  # SMASH, GOLD, EDGE, etc.

    # === NEW FIELDS FOR v15.0 CLARITY (Master Prompt Requirements) ===

    # Human-readable output fields
    description: str = ""  # Full sentence: "Jamal Murray Assists Over 3.5"
    pick_detail: str = ""  # Compact: "Assists Over 3.5", "Total Under 246.5"

    # Game status (standardized)
    game_status: str = "SCHEDULED"  # SCHEDULED, LIVE, FINAL

    # Live betting flags
    is_live_bet_candidate: bool = False  # True if LIVE and triggers met
    was_game_already_started: bool = False  # Alias/replacement for already_started

    # Titanium modules tracking
    titanium_modules_hit: List[str] = field(default_factory=list)  # ['AI', 'Research', 'Jarvis']

    # Odds alias for consistency
    odds_american: int = -110  # Same as odds, but explicit naming

    # Jason Sim expanded fields
    jason_projected_total: Optional[float] = None  # Simulated game total
    jason_variance_flag: str = ""  # HIGH, MED, LOW (alias of variance_flag)

    # Prop availability tracking
    prop_available_at_books: List[str] = field(default_factory=list)  # Books where confirmed

    # Contradiction prevention
    contradiction_blocked: bool = False  # True if blocked due to opposite side existing

    # Engine breakdowns (separate from research_breakdown)
    esoteric_breakdown: Dict[str, Any] = field(default_factory=dict)
    jarvis_breakdown: Dict[str, Any] = field(default_factory=dict)

    # CLV grading
    beat_clv: Optional[bool] = None  # True if got better line than closing
    process_grade: Optional[str] = None  # EXCELLENT, GOOD, FAIR, POOR

    # v15.1 - Grading metadata
    game_time_utc: str = ""  # ISO UTC game start time
    minutes_since_start: int = 0  # Minutes since game start (0 if not started)
    raw_inputs_snapshot: Dict[str, Any] = field(default_factory=dict)  # Key features used


# =============================================================================
# TIMEZONE HELPERS
# =============================================================================

def get_now_et() -> datetime:
    """Get current datetime in America/New_York timezone."""
    if PYTZ_AVAILABLE and ET:
        return datetime.now(ET)
    return datetime.now()


def get_today_date_et() -> str:
    """Get today's date string in ET."""
    return get_now_et().strftime("%Y-%m-%d")


def parse_game_time_et(time_str: str) -> Optional[datetime]:
    """Parse game time string to ET datetime."""
    if not time_str:
        return None

    try:
        if "Z" in time_str:
            time_str = time_str.replace("Z", "+00:00")

        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))

        if PYTZ_AVAILABLE and ET:
            if dt.tzinfo is None:
                dt = UTC.localize(dt)
            dt = dt.astimezone(ET)

        return dt
    except (ValueError, AttributeError):
        return None


def is_game_started(game_start_time: str) -> Tuple[bool, str]:
    """
    Check if game has already started.

    Returns:
        Tuple of (already_started: bool, reason: str)
    """
    game_dt = parse_game_time_et(game_start_time)
    if not game_dt:
        return False, ""

    now_et = get_now_et()

    if PYTZ_AVAILABLE and ET:
        if game_dt.tzinfo is None:
            game_dt = ET.localize(game_dt)

    if now_et > game_dt:
        minutes_late = int((now_et - game_dt).total_seconds() / 60)
        return True, f"Game started {minutes_late} minutes ago - live-bet eligible only"

    return False, ""


def is_today_et(date_str: str) -> bool:
    """Check if a date string is today in ET."""
    today = get_today_date_et()

    # Handle various date formats
    if "T" in date_str:
        date_str = date_str.split("T")[0]

    return date_str == today


def get_today_boundaries_et() -> Tuple[datetime, datetime]:
    """
    Get today's grading boundaries in ET.

    Returns:
        Tuple of (start: 12:01 AM ET, end: 11:59 PM ET)
    """
    now_et = get_now_et()
    today = now_et.date()

    if PYTZ_AVAILABLE and ET:
        from datetime import time as dt_time
        start = ET.localize(datetime.combine(today, dt_time(0, 1, 0)))
        end = ET.localize(datetime.combine(today, dt_time(23, 59, 59)))
    else:
        from datetime import time as dt_time
        start = datetime.combine(today, dt_time(0, 1, 0))
        end = datetime.combine(today, dt_time(23, 59, 59))

    return start, end


# =============================================================================
# BOOK AVAILABILITY VALIDATION
# =============================================================================

def validate_book_availability(
    player_name: str,
    prop_type: str,
    book: str,
    available_props: Optional[List[Dict]] = None
) -> Tuple[bool, str]:
    """
    Validate that a player prop is actually available at the book.

    Args:
        player_name: Player name
        prop_type: Type of prop (points, rebounds, etc.)
        book: Sportsbook name
        available_props: Optional list of available props from API

    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    if not player_name:
        return True, ""  # Game picks don't need player validation

    book_lower = book.lower() if book else ""

    # If we have available props list, validate against it
    if available_props:
        player_found = False
        for prop in available_props:
            if prop.get("player", "").lower() == player_name.lower():
                player_found = True
                # Check if this specific prop type is available
                if prop.get("market", "").lower() == prop_type.lower():
                    return True, ""

        if not player_found:
            return False, f"Player {player_name} not found in {book} props - may be injured/inactive"
        else:
            return False, f"Prop type {prop_type} not available for {player_name} at {book}"

    # Without props list, we can only do basic validation
    return True, ""


def validate_injury_for_prop(injury_status: str) -> Tuple[bool, str]:
    """
    Check if injury status invalidates a prop.

    Returns:
        Tuple of (is_valid: bool, reason: str)
    """
    if not injury_status:
        return True, ""

    status_upper = injury_status.upper().strip()

    INVALID_STATUSES = {"OUT", "DOUBTFUL", "SUSPENDED", "DNP", "INACTIVE"}

    if status_upper in INVALID_STATUSES:
        return False, f"Player is {status_upper} - prop invalid"

    return True, ""


# =============================================================================
# PICK LOGGER CLASS
# =============================================================================

class PickLogger:
    """
    Production pick logger with full v14.11 support.

    Handles:
    - Logging published picks with transparency fields
    - Already_started detection
    - Book/injury validation
    - Today-only grading enforcement
    - Audit report generation
    - Run tracking with run_id
    - Deduplication with pick_hash
    - Grade-ready checklist validation
    """

    def __init__(self, storage_path: str = STORAGE_PATH):
        self.storage_path = storage_path
        self.graded_path = GRADED_PATH
        self.picks: Dict[str, List[PublishedPick]] = defaultdict(list)  # By date
        self.pick_hashes: Dict[str, Set[str]] = defaultdict(set)  # By date, set of hashes
        self.current_run_id: Optional[str] = None  # Current execution run
        self.runs: Dict[str, Dict[str, Any]] = {}  # run_id -> metadata

        os.makedirs(storage_path, exist_ok=True)
        os.makedirs(GRADED_PATH, exist_ok=True)

        self._load_today_picks()

    def start_run(self) -> str:
        """Start a new pick generation run. Returns run_id."""
        self.current_run_id = str(uuid.uuid4())
        self.runs[self.current_run_id] = {
            "started_at": get_now_et().isoformat(),
            "picks_inserted": 0,
            "picks_skipped": 0,
            "sports": set(),
        }
        logger.info("Started new run: %s", self.current_run_id)
        return self.current_run_id

    def end_run(self) -> Dict[str, Any]:
        """End current run and return summary."""
        if not self.current_run_id:
            return {"error": "No active run"}

        run_data = self.runs.get(self.current_run_id, {})
        run_data["ended_at"] = get_now_et().isoformat()
        run_data["sports"] = list(run_data.get("sports", set()))

        summary = {
            "run_id": self.current_run_id,
            **run_data
        }

        self.current_run_id = None
        logger.info("Ended run: %s", summary)
        return summary

    def get_run_id(self) -> str:
        """Get current run_id or start a new one."""
        if not self.current_run_id:
            return self.start_run()
        return self.current_run_id

    def _generate_pick_hash(self, pick_data: Dict) -> str:
        """
        Generate deterministic hash for pick uniqueness.

        Hash is based on: player + prop_type + line + side + matchup + date
        This allows same pick with different lines to be logged separately.
        """
        key_parts = [
            str(pick_data.get("player_name", pick_data.get("player", ""))).lower().strip(),
            str(pick_data.get("prop_type", pick_data.get("market", ""))).lower().strip(),
            str(pick_data.get("line", "")),
            str(pick_data.get("side", pick_data.get("over_under", ""))).lower().strip(),
            str(pick_data.get("matchup", pick_data.get("game", ""))).lower().strip(),
            str(pick_data.get("pick_type", "")).lower().strip(),
        ]
        hash_input = "|".join(key_parts).encode()
        return hashlib.sha256(hash_input).hexdigest()[:16]

    def is_duplicate(self, pick_hash: str, date: str, line: float = None, allow_line_change: bool = True) -> Tuple[bool, str]:
        """
        Check if a pick is a duplicate.

        Args:
            pick_hash: The pick's deterministic hash
            date: Date to check against
            line: Current line value (for material change detection)
            allow_line_change: If True, allows re-logging if line changed significantly

        Returns:
            Tuple of (is_duplicate: bool, reason: str)
        """
        if pick_hash not in self.pick_hashes.get(date, set()):
            return False, ""

        if allow_line_change and line is not None:
            # Check if line changed materially (>0.5 points)
            existing = self._find_pick_by_hash(date, pick_hash)
            if existing and abs(existing.line - line) > 0.5:
                return False, "LINE_CHANGED"

        return True, "DUPLICATE_PICK"

    def _find_pick_by_hash(self, date: str, pick_hash: str) -> Optional[PublishedPick]:
        """Find a pick by its hash."""
        for pick in self.picks.get(date, []):
            if getattr(pick, 'pick_hash', '') == pick_hash:
                return pick
        return None

    def _get_today_file(self) -> str:
        """Get today's pick log file path."""
        today = get_today_date_et()
        return os.path.join(self.storage_path, f"picks_{today}.jsonl")

    def _load_today_picks(self):
        """Load today's picks from disk."""
        today = get_today_date_et()
        today_file = self._get_today_file()

        if os.path.exists(today_file):
            valid_field_names = {f.name for f in dataclass_fields(PublishedPick)}
            try:
                with open(today_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            # Filter to known fields so schema changes don't crash
                            filtered = {k: v for k, v in data.items() if k in valid_field_names}
                            pick = PublishedPick(**filtered)
                            self.picks[today].append(pick)
                            # Build pick_hash index
                            if hasattr(pick, 'pick_hash') and pick.pick_hash:
                                self.pick_hashes[today].add(pick.pick_hash)
                logger.info("Loaded %d picks for %s (with %d unique hashes)",
                           len(self.picks[today]), today, len(self.pick_hashes[today]))
            except Exception as e:
                logger.error("Failed to load picks: %s", e)

    def _save_pick(self, pick: PublishedPick):
        """Append a pick to today's log file."""
        today_file = self._get_today_file()

        with open(today_file, 'a') as f:
            f.write(json.dumps(asdict(pick)) + "\n")

    def log_pick(
        self,
        pick_data: Dict[str, Any],
        game_start_time: str = "",
        available_props: Optional[List[Dict]] = None,
        run_id: Optional[str] = None,
        skip_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        Log a published pick with full v14.11 fields.

        Args:
            pick_data: Pick data from best-bets endpoint
            game_start_time: ISO format game start time
            available_props: Optional props list for book validation
            run_id: Optional run_id (uses current run if not specified)
            skip_duplicates: If True, skip duplicate picks (default True)

        Returns:
            Dict with pick_id, validation status, dedup info, and any warnings
        """
        # CRITICAL FIX: Enforce book_key defaults BEFORE processing
        pick_data = _ensure_book_fields(pick_data)

        today = get_today_date_et()
        now_et = get_now_et()

        # Use provided run_id or get current
        run_id = run_id or self.get_run_id()

        # Generate pick_hash for deduplication
        pick_hash = self._generate_pick_hash(pick_data)

        # Check for duplicates
        is_dup, dup_reason = self.is_duplicate(
            pick_hash, today,
            line=float(pick_data.get("line") or 0),
            allow_line_change=True
        )

        if is_dup and skip_duplicates:
            # Track skipped in run
            if run_id in self.runs:
                self.runs[run_id]["picks_skipped"] = self.runs[run_id].get("picks_skipped", 0) + 1

            return {
                "pick_id": None,
                "pick_hash": pick_hash,
                "logged": False,
                "skipped": True,
                "skip_reason": dup_reason,
                "run_id": run_id,
                "should_publish": False
            }

        # Generate pick_id if not present
        pick_id = pick_data.get("pick_id") or self._generate_pick_id(pick_data)

        # Check if already started
        already_started, late_reason = is_game_started(game_start_time)

        # Validate injury status for props
        player_name = pick_data.get("player_name", pick_data.get("player", ""))
        injury_status = pick_data.get("injury_status", "HEALTHY")
        injury_valid, injury_error = validate_injury_for_prop(injury_status)

        # Validate book availability
        book = pick_data.get("best_book", pick_data.get("book", ""))
        prop_type = pick_data.get("prop_type", pick_data.get("market", ""))
        book_valid, book_error = validate_book_availability(
            player_name, prop_type, book, available_props
        )

        # Collect validation errors
        validation_errors = []
        if not injury_valid:
            validation_errors.append(injury_error)
        if not book_valid:
            validation_errors.append(book_error)

        # Compute base_score (pre-jason)
        def _f(v, default=0): return float(v if v is not None else default)
        def _i(v, default=0): return int(v if v is not None else default)
        ai = _f(pick_data.get("ai_score", 0))
        research = _f(pick_data.get("research_score", 0))
        esoteric = _f(pick_data.get("esoteric_score", 0))
        jarvis = _f(pick_data.get("jarvis_score", pick_data.get("jarvis_rs", 0)))
        jason_boost = _f(pick_data.get("jason_sim_boost", 0))
        final = _f(pick_data.get("final_score", pick_data.get("total_score", 0)))
        base_score = final - jason_boost if jason_boost else final

        # Determine tier badge
        tier = pick_data.get("tier", "PASS")
        tier_badge_map = {
            "TITANIUM_SMASH": "SMASH",
            "GOLD_STAR": "GOLD",
            "EDGE_LEAN": "EDGE",
            "MONITOR": "WATCH",
            "PASS": ""
        }
        tier_badge = tier_badge_map.get(tier, tier)

        # Determine status
        status = "scheduled"
        if already_started:
            status = "live"
        if pick_data.get("event_status") == "FINAL":
            status = "final"

        # Create pick record
        pick = PublishedPick(
            pick_id=pick_id,
            date=today,
            sport=pick_data.get("sport", ""),
            pick_type=pick_data.get("pick_type", "PROP" if player_name else "GAME"),
            player_name=player_name,
            matchup=pick_data.get("matchup", pick_data.get("game", "")),
            home_team=pick_data.get("home_team", ""),
            away_team=pick_data.get("away_team", ""),
            prop_type=prop_type,
            line=_f(pick_data.get("line", 0)),
            side=pick_data.get("side", pick_data.get("over_under", "")),
            odds=_i(pick_data.get("odds", -110), -110),
            book=book,
            book_link=pick_data.get("best_book_link", ""),
            game_start_time_et=pick_data.get("start_time_et", ""),
            published_at=now_et.isoformat(),
            already_started=already_started,
            late_pull_reason=late_reason,
            ai_score=ai,
            research_score=research,
            esoteric_score=esoteric,
            jarvis_score=jarvis,
            final_score=final,
            tier=tier,
            titanium_flag=pick_data.get("titanium_triggered", False),
            units=_f(pick_data.get("units", 0)),
            research_breakdown=pick_data.get("research_breakdown", {}),
            research_reasons=pick_data.get("research_reasons", []),
            pillars_passed=pick_data.get("pillars_passed", []),
            pillars_failed=pick_data.get("pillars_failed", []),
            jason_ran=pick_data.get("jason_ran", False),
            jason_sim_boost=jason_boost,
            jason_blocked=pick_data.get("jason_blocked", False),
            jason_win_pct_home=_f(pick_data.get("jason_win_pct_home", 50), 50),
            jason_win_pct_away=_f(pick_data.get("jason_win_pct_away", 50), 50),
            confluence_reasons=pick_data.get("confluence_reasons", []),
            jarvis_triggers_hit=pick_data.get("jarvis_triggers_hit", []),
            jarvis_reasons=pick_data.get("jarvis_reasons", []),
            injury_status=injury_status,
            book_validated=book_valid and injury_valid,
            validation_errors=validation_errors,
            # v14.10 E2E verification fields
            graded=False,
            grade_result=None,
            canonical_event_id=pick_data.get("canonical_event_id", ""),
            provider_event_ids=pick_data.get("provider_event_ids", {}),
            canonical_player_id=pick_data.get("canonical_player_id", ""),
            provider_player_ids=pick_data.get("provider_player_ids", pick_data.get("provider_ids", {})),
            line_at_bet=_f(pick_data.get("line", 0)),
            odds_at_bet=_i(pick_data.get("odds", -110), -110),
            timestamp_at_bet=now_et.isoformat(),
            closing_line=None,
            closing_odds=None,
            clv=None,
            event_status=pick_data.get("event_status", "NOT_STARTED"),
            # v14.11 new fields
            run_id=run_id,
            pick_hash=pick_hash,
            grade_status="PENDING",
            book_key=pick_data.get("book_key", book.lower().replace(" ", "_") if book else ""),
            market=pick_data.get("market", prop_type or pick_data.get("pick_type", "")),
            jason_sim_available=pick_data.get("jason_sim_available", pick_data.get("jason_ran", False)),
            variance_flag=pick_data.get("variance_flag", ""),
            injury_state=pick_data.get("injury_state", "CONFIRMED_ONLY"),
            sim_count=_i(pick_data.get("sim_count", 1000 if pick_data.get("jason_ran") else 0)),
            signals_firing=pick_data.get("signals_firing", []),
            engine_breakdown=pick_data.get("engine_breakdown", {
                "ai_score": ai,
                "research_score": research,
                "esoteric_score": esoteric,
                "jarvis_score": jarvis,
                "jason_boost": jason_boost
            }),
            vacuum_flags=pick_data.get("vacuum_flags", []),
            titanium_reasons=pick_data.get("titanium_reasons", []),
            is_live=already_started,
            live_context=pick_data.get("live_context", {}),
            is_started_already=already_started,
            sportsbook_name=pick_data.get("sportsbook_name", book),
            sportsbook_event_url=pick_data.get("sportsbook_event_url"),
            league=pick_data.get("league", pick_data.get("sport", "")),
            status=status,
            base_score=base_score,
            tier_badge=tier_badge,
            # v15.1 grading metadata
            game_time_utc=pick_data.get("game_time_utc", ""),
            minutes_since_start=_i(pick_data.get("minutes_since_start", 0)),
            raw_inputs_snapshot=pick_data.get("raw_inputs_snapshot", {}),
        )

        # Store and persist
        self.picks[today].append(pick)
        self.pick_hashes[today].add(pick_hash)
        self._save_pick(pick)

        # Track in run
        if run_id in self.runs:
            self.runs[run_id]["picks_inserted"] = self.runs[run_id].get("picks_inserted", 0) + 1
            self.runs[run_id]["sports"].add(pick.sport.upper())

        return {
            "pick_id": pick_id,
            "pick_hash": pick_hash,
            "run_id": run_id,
            "logged": True,
            "skipped": False,
            "already_started": already_started,
            "late_pull_reason": late_reason,
            "book_validated": book_valid and injury_valid,
            "validation_errors": validation_errors,
            "should_publish": len(validation_errors) == 0
        }

    def _generate_pick_id(self, pick_data: Dict) -> str:
        """Generate deterministic pick ID."""
        key_parts = [
            str(pick_data.get("player_name", pick_data.get("player", ""))),
            str(pick_data.get("market", pick_data.get("prop_type", ""))),
            str(pick_data.get("line", "")),
            str(pick_data.get("side", pick_data.get("over_under", ""))),
            str(pick_data.get("matchup", pick_data.get("game", ""))),
            str(pick_data.get("pick_type", ""))
        ]
        hash_input = "|".join(key_parts).encode()
        return hashlib.sha256(hash_input).hexdigest()[:12]

    def get_today_picks(self, sport: Optional[str] = None) -> List[PublishedPick]:
        """Get all picks published today, optionally filtered by sport."""
        today = get_today_date_et()
        picks = self.picks.get(today, [])

        if sport:
            picks = [p for p in picks if p.sport.upper() == sport.upper()]

        return picks

    def get_picks_for_date(self, date: str, sport: Optional[str] = None) -> List[PublishedPick]:
        """
        Get all picks for a specific date.

        Args:
            date: Date string in YYYY-MM-DD format
            sport: Optional sport filter

        Returns:
            List of PublishedPick objects for that date
        """
        # Load from file if this date has never been loaded
        if date not in self.picks:
            self._load_picks_from_file(date)

        picks = self.picks.get(date, [])

        if sport:
            picks = [p for p in picks if p.sport.upper() == sport.upper()]

        return picks

    def _load_picks_from_file(self, date: str):
        """Load picks from JSONL file for a given date."""
        log_file = os.path.join(self.storage_path, f"picks_{date}.jsonl")
        if os.path.exists(log_file):
            valid_field_names = {f.name for f in dataclass_fields(PublishedPick)}
            picks = []
            with open(log_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        # Filter to known fields so schema changes don't crash loading
                        filtered = {k: v for k, v in data.items() if k in valid_field_names}
                        pick = PublishedPick(**filtered)
                        picks.append(pick)
                    except Exception as e:
                        logger.warning("Failed to parse pick line: %s", e)
                        continue
            self.picks[date] = picks

    def grade_pick(
        self,
        pick_id: str,
        result: str,
        actual_value: Optional[float] = None,
        date: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Grade a pick with actual result.

        Args:
            pick_id: The pick ID to grade
            result: WIN, LOSS, or PUSH
            actual_value: Optional actual stat value for props
            date: Date to search (default: today, also checks yesterday)

        Returns:
            Grading result or None if pick not found
        """
        # Search today and yesterday
        dates_to_search = []
        if date:
            dates_to_search.append(date)
        else:
            today = get_today_date_et()
            yesterday = (get_now_et() - timedelta(days=1)).strftime("%Y-%m-%d")
            dates_to_search = [today, yesterday]

        for search_date in dates_to_search:
            # Ensure picks are loaded for this date
            if search_date not in self.picks:
                self._load_picks_from_file(search_date)

            for pick in self.picks.get(search_date, []):
                if pick.pick_id == pick_id:
                    pick.result = result.upper()
                    pick.actual_value = actual_value
                    pick.graded_at = get_now_et().isoformat()
                    pick.graded = True
                    pick.grade_result = pick.result
                    pick.grade_status = "GRADED"

                    # Calculate units won/lost
                    if pick.result == "WIN":
                        if pick.odds > 0:
                            pick.units_won_lost = pick.units * (pick.odds / 100)
                        else:
                            pick.units_won_lost = pick.units * (100 / abs(pick.odds))
                    elif pick.result == "LOSS":
                        pick.units_won_lost = -pick.units
                    else:  # PUSH
                        pick.units_won_lost = 0

                    # Save to BOTH canonical log and graded file
                    self._rewrite_pick_log(search_date)
                    self._save_graded_picks(search_date)

                    return {
                        "pick_id": pick_id,
                        "result": pick.result,
                        "units_won_lost": pick.units_won_lost,
                        "graded_at": pick.graded_at
                    }

        return None

    def _rewrite_pick_log(self, date: str):
        """Rewrite the canonical pick log so graded status survives redeploy."""
        log_file = os.path.join(self.storage_path, f"picks_{date}.jsonl")
        picks = self.picks.get(date, [])
        if not picks:
            return
        with open(log_file, 'w') as f:
            for pick in picks:
                f.write(json.dumps(asdict(pick)) + "\n")

    def _save_graded_picks(self, date: str):
        """Save graded picks to separate file (secondary copy)."""
        graded_file = os.path.join(self.graded_path, f"graded_{date}.jsonl")

        graded = [p for p in self.picks.get(date, []) if p.result is not None]

        with open(graded_file, 'w') as f:
            for pick in graded:
                f.write(json.dumps(asdict(pick)) + "\n")

    def get_picks_for_grading(
        self,
        date: Optional[str] = None,
        sport: Optional[str] = None
    ) -> List[PublishedPick]:
        """
        Get picks that need grading (today only by default).

        Enforces today-only EST boundaries.
        """
        if date is None:
            date = get_today_date_et()

        # Enforce today-only
        if date != get_today_date_et():
            logger.warning("Attempted to grade picks for %s but today is %s",
                          date, get_today_date_et())
            # Allow yesterday for morning grading
            yesterday = (get_now_et() - timedelta(days=1)).strftime("%Y-%m-%d")
            if date != yesterday:
                return []

        picks = self.picks.get(date, [])

        # Load from disk if not in memory
        if not picks:
            pick_file = os.path.join(self.storage_path, f"picks_{date}.jsonl")
            if os.path.exists(pick_file):
                healed_picks = []
                needs_rewrite = False
                with open(pick_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            # AUTO-HEAL: Enforce book_key defaults on legacy rows
                            original_book_key = data.get("book_key", "")
                            data = _ensure_book_fields(data)
                            if original_book_key != data.get("book_key"):
                                needs_rewrite = True
                                logger.info(f"Auto-healed book_key: {data.get('pick_id', 'unknown')} -> {data.get('book_key')}")
                            healed_picks.append(PublishedPick(**data))

                # Rewrite file if any picks were healed (idempotent)
                if needs_rewrite:
                    logger.info(f"Rewriting {pick_file} with healed picks")
                    with open(pick_file, 'w') as f:
                        for pick in healed_picks:
                            f.write(json.dumps(asdict(pick)) + "\n")

                picks = healed_picks
                self.picks[date] = picks

        # Filter by sport if specified
        if sport:
            picks = [p for p in picks if p.sport.upper() == sport.upper()]

        # Return only ungraded picks
        return [p for p in picks if p.result is None]

    def generate_audit_report(
        self,
        date: Optional[str] = None,
        include_details: bool = True
    ) -> Dict[str, Any]:
        """
        Generate comprehensive audit report.

        Includes:
        - Record by tier and sport
        - ROI by tier
        - Top false positives (high score loses)
        - Top missed opportunities (low score wins)
        - Pillar hit-rate breakdown
        - Jarvis trigger performance
        - Jason sim accuracy
        """
        if date is None:
            # Default to yesterday for morning audit
            date = (get_now_et() - timedelta(days=1)).strftime("%Y-%m-%d")

        # Load picks for the date
        picks = []
        pick_file = os.path.join(self.storage_path, f"picks_{date}.jsonl")
        graded_file = os.path.join(self.graded_path, f"graded_{date}.jsonl")

        # Prefer graded file
        target_file = graded_file if os.path.exists(graded_file) else pick_file

        if os.path.exists(target_file):
            with open(target_file, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        picks.append(PublishedPick(**data))

        if not picks:
            return {"error": f"No picks found for {date}", "date": date}

        # Filter to graded picks only
        graded = [p for p in picks if p.result is not None]

        if not graded:
            return {
                "date": date,
                "total_picks": len(picks),
                "graded_picks": 0,
                "note": "No picks graded yet"
            }

        # Calculate metrics
        report = {
            "date": date,
            "generated_at": get_now_et().isoformat(),
            "total_picks": len(picks),
            "graded_picks": len(graded),
            "summary": self._calculate_summary(graded),
            "by_sport": self._calculate_by_sport(graded),
            "by_tier": self._calculate_by_tier(graded),
            "pillar_performance": self._calculate_pillar_performance(graded),
            "jarvis_performance": self._calculate_jarvis_performance(graded),
            "jason_sim_performance": self._calculate_jason_performance(graded)
        }

        if include_details:
            report["false_positives"] = self._get_false_positives(graded, limit=10)
            report["missed_opportunities"] = self._get_missed_opportunities(graded, limit=10)

        return report

    def _calculate_summary(self, picks: List[PublishedPick]) -> Dict:
        """Calculate overall summary stats."""
        wins = sum(1 for p in picks if p.result == "WIN")
        losses = sum(1 for p in picks if p.result == "LOSS")
        pushes = sum(1 for p in picks if p.result == "PUSH")

        total_units = sum(p.units_won_lost or 0 for p in picks)

        return {
            "record": f"{wins}-{losses}-{pushes}",
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0,
            "total_units": round(total_units, 2),
            "roi": round(total_units / sum(p.units for p in picks if p.units > 0) * 100, 1) if sum(p.units for p in picks) > 0 else 0
        }

    def _calculate_by_sport(self, picks: List[PublishedPick]) -> Dict:
        """Calculate stats by sport."""
        by_sport = defaultdict(list)
        for p in picks:
            by_sport[p.sport].append(p)

        return {
            sport: self._calculate_summary(sport_picks)
            for sport, sport_picks in by_sport.items()
        }

    def _calculate_by_tier(self, picks: List[PublishedPick]) -> Dict:
        """Calculate stats by tier."""
        by_tier = defaultdict(list)
        for p in picks:
            by_tier[p.tier].append(p)

        return {
            tier: self._calculate_summary(tier_picks)
            for tier, tier_picks in by_tier.items()
        }

    def _calculate_pillar_performance(self, picks: List[PublishedPick]) -> Dict:
        """Calculate win rate by pillar."""
        pillar_stats = defaultdict(lambda: {"wins": 0, "total": 0})

        for p in picks:
            for pillar in p.pillars_passed:
                pillar_stats[pillar]["total"] += 1
                if p.result == "WIN":
                    pillar_stats[pillar]["wins"] += 1

        return {
            pillar: {
                "win_rate": round(stats["wins"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0,
                "sample_size": stats["total"]
            }
            for pillar, stats in pillar_stats.items()
        }

    def _calculate_jarvis_performance(self, picks: List[PublishedPick]) -> Dict:
        """Calculate win rate by Jarvis trigger."""
        trigger_stats = defaultdict(lambda: {"wins": 0, "total": 0})

        for p in picks:
            for trigger in p.jarvis_triggers_hit:
                trigger_name = trigger.get("name", str(trigger.get("number", "Unknown")))
                trigger_stats[trigger_name]["total"] += 1
                if p.result == "WIN":
                    trigger_stats[trigger_name]["wins"] += 1

        return {
            trigger: {
                "win_rate": round(stats["wins"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0,
                "sample_size": stats["total"]
            }
            for trigger, stats in trigger_stats.items()
        }

    def _calculate_jason_performance(self, picks: List[PublishedPick]) -> Dict:
        """Calculate Jason Sim accuracy."""
        boosted = [p for p in picks if p.jason_sim_boost > 0]
        downgraded = [p for p in picks if p.jason_sim_boost < 0]
        blocked = [p for p in picks if p.jason_blocked]

        def calc_win_rate(plist):
            if not plist:
                return 0
            wins = sum(1 for p in plist if p.result == "WIN")
            return round(wins / len(plist) * 100, 1)

        return {
            "boosted": {
                "count": len(boosted),
                "win_rate": calc_win_rate(boosted),
                "avg_boost": round(sum(p.jason_sim_boost for p in boosted) / len(boosted), 2) if boosted else 0
            },
            "downgraded": {
                "count": len(downgraded),
                "win_rate": calc_win_rate(downgraded),
                "avg_downgrade": round(sum(p.jason_sim_boost for p in downgraded) / len(downgraded), 2) if downgraded else 0
            },
            "blocked": {
                "count": len(blocked),
                "note": "Blocked picks not published - validation only"
            },
            "neutral": {
                "count": len(picks) - len(boosted) - len(downgraded) - len(blocked),
                "win_rate": calc_win_rate([p for p in picks if p.jason_sim_boost == 0 and not p.jason_blocked])
            }
        }

    def _get_false_positives(self, picks: List[PublishedPick], limit: int = 10) -> List[Dict]:
        """Get top false positives (high score but lost)."""
        losses = [p for p in picks if p.result == "LOSS"]
        losses.sort(key=lambda p: p.final_score, reverse=True)

        return [
            {
                "pick_id": p.pick_id,
                "matchup": p.matchup,
                "player": p.player_name,
                "prop": f"{p.side} {p.line}" if p.player_name else p.side,
                "final_score": p.final_score,
                "tier": p.tier,
                "research_reasons": p.research_reasons[:3],
                "jason_sim_boost": p.jason_sim_boost
            }
            for p in losses[:limit]
        ]

    def _get_missed_opportunities(self, picks: List[PublishedPick], limit: int = 10) -> List[Dict]:
        """Get missed opportunities (low score but won)."""
        # Look at picks that were PASS tier but won
        low_score_wins = [p for p in picks if p.result == "WIN" and p.tier in ("PASS", "MONITOR")]
        low_score_wins.sort(key=lambda p: p.final_score)

        return [
            {
                "pick_id": p.pick_id,
                "matchup": p.matchup,
                "player": p.player_name,
                "prop": f"{p.side} {p.line}" if p.player_name else p.side,
                "final_score": p.final_score,
                "tier": p.tier,
                "pillars_failed": p.pillars_failed[:3]
            }
            for p in low_score_wins[:limit]
        ]

    def check_grade_ready(self, pick: PublishedPick) -> Dict[str, Any]:
        """
        Check if a pick is grade-ready for the autograder.

        Validates:
        - canonical_event_id exists (or matchup as fallback)
        - For props: canonical_player_id exists
        - book_key is set
        - market is set
        - line_at_bet and odds_at_bet are set
        - timestamp_at_bet is set

        Returns:
            Dict with status (READY, UNRESOLVED), missing fields, and reasons
        """
        missing_fields = []
        reasons = []

        # Check event resolution
        if not getattr(pick, 'canonical_event_id', '') and not pick.matchup:
            missing_fields.append("canonical_event_id")
            reasons.append("UNRESOLVED_EVENT")

        # Check player resolution (for props only)
        if pick.player_name and not getattr(pick, 'canonical_player_id', ''):
            missing_fields.append("canonical_player_id")
            reasons.append("UNRESOLVED_PLAYER")

        # Check required fields for grading
        if not getattr(pick, 'book_key', '') and not pick.book:
            missing_fields.append("book_key")
            reasons.append("MISSING_BOOK")

        if not getattr(pick, 'market', '') and not pick.prop_type:
            missing_fields.append("market")
            reasons.append("MISSING_MARKET")

        line_at_bet = getattr(pick, 'line_at_bet', 0.0)
        if line_at_bet == 0.0 and pick.line == 0.0 and pick.player_name:
            # Only flag missing line for prop picks; game picks can have line=0 (pick-em)
            missing_fields.append("line_at_bet")
            reasons.append("MISSING_LINE")

        odds_at_bet = getattr(pick, 'odds_at_bet', 0)
        if odds_at_bet == 0 and pick.odds == 0:
            missing_fields.append("odds_at_bet")
            reasons.append("MISSING_ODDS")

        timestamp = getattr(pick, 'timestamp_at_bet', '')
        if not timestamp and not pick.published_at:
            missing_fields.append("timestamp_at_bet")
            reasons.append("MISSING_TIMESTAMP")

        # Determine status
        if reasons:
            status = "UNRESOLVED"
        else:
            status = "READY"

        return {
            "pick_id": pick.pick_id,
            "status": status,
            "missing_fields": missing_fields,
            "reasons": reasons,
            "is_grade_ready": status == "READY"
        }

    def validate_all_picks_grade_ready(
        self,
        date: Optional[str] = None,
        sports: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Validate all picks for a date are grade-ready.

        This is the KEY function for proving tomorrow's autograder will work.

        Args:
            date: Date to check (default: today ET)
            sports: Optional list of sports to filter

        Returns:
            Dict with overall status, counts, and per-pick details
        """
        if not date:
            date = get_today_date_et()

        picks = self.get_picks_for_date(date)

        # Filter by sports if specified
        if sports:
            sport_set = set(s.upper() for s in sports)
            picks = [p for p in picks if p.sport.upper() in sport_set]

        # Validate each pick
        results = {
            "date": date,
            "total": len(picks),
            "ready": 0,
            "unresolved": 0,
            "graded": 0,
            "pending": 0,
            "by_reason": {},
            "unresolved_picks": []
        }

        for pick in picks:
            # Skip already graded
            if pick.result is not None or getattr(pick, 'graded', False):
                results["graded"] += 1
                continue

            check = self.check_grade_ready(pick)

            if check["is_grade_ready"]:
                results["ready"] += 1
                results["pending"] += 1
            else:
                results["unresolved"] += 1
                results["unresolved_picks"].append({
                    "pick_id": pick.pick_id,
                    "sport": pick.sport,
                    "player": pick.player_name,
                    "matchup": pick.matchup,
                    "reasons": check["reasons"],
                    "missing_fields": check["missing_fields"]
                })

                # Count by reason
                for reason in check["reasons"]:
                    results["by_reason"][reason] = results["by_reason"].get(reason, 0) + 1

        # Overall status
        if results["unresolved"] > 0:
            results["overall_status"] = "UNRESOLVED"
        elif results["pending"] > 0:
            results["overall_status"] = "PENDING"
        else:
            results["overall_status"] = "PASS"

        return results

    def get_picks_by_run(self, run_id: str, date: Optional[str] = None) -> List[PublishedPick]:
        """Get picks for a specific run_id."""
        if not date:
            date = get_today_date_et()

        picks = self.get_picks_for_date(date)
        return [p for p in picks if getattr(p, 'run_id', '') == run_id]

    def get_latest_run_id(self, date: Optional[str] = None) -> Optional[str]:
        """Get the most recent run_id for a date."""
        if not date:
            date = get_today_date_et()

        picks = self.get_picks_for_date(date)
        if not picks:
            return None

        # Find latest by published_at timestamp
        latest = max(picks, key=lambda p: p.published_at or "")
        return getattr(latest, 'run_id', None)

    def get_run_summary(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get summary of all runs for a date."""
        if not date:
            date = get_today_date_et()

        picks = self.get_picks_for_date(date)

        runs = {}
        for pick in picks:
            run_id = getattr(pick, 'run_id', 'unknown')
            if run_id not in runs:
                runs[run_id] = {
                    "run_id": run_id,
                    "pick_count": 0,
                    "sports": set(),
                    "first_pick": pick.published_at,
                    "last_pick": pick.published_at
                }
            runs[run_id]["pick_count"] += 1
            runs[run_id]["sports"].add(pick.sport.upper())
            if pick.published_at > runs[run_id]["last_pick"]:
                runs[run_id]["last_pick"] = pick.published_at

        # Convert sets to lists for JSON
        for r in runs.values():
            r["sports"] = list(r["sports"])

        return {
            "date": date,
            "total_runs": len(runs),
            "total_picks": len(picks),
            "runs": list(runs.values())
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_pick_logger_instance: Optional[PickLogger] = None


def get_pick_logger() -> PickLogger:
    """Get singleton PickLogger instance."""
    global _pick_logger_instance
    if _pick_logger_instance is None:
        _pick_logger_instance = PickLogger()
    return _pick_logger_instance


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def log_published_pick(pick_data: Dict[str, Any], game_start_time: str = "") -> Dict:
    """Log a published pick (convenience function)."""
    return get_pick_logger().log_pick(pick_data, game_start_time)


def grade_pick(pick_id: str, result: str, actual_value: Optional[float] = None) -> Optional[Dict]:
    """Grade a pick (convenience function)."""
    return get_pick_logger().grade_pick(pick_id, result, actual_value)


def run_daily_audit_report(date: Optional[str] = None) -> Dict:
    """Generate daily audit report (convenience function)."""
    return get_pick_logger().generate_audit_report(date)


def get_today_picks(sport: Optional[str] = None) -> List[PublishedPick]:
    """Get today's picks (convenience function)."""
    return get_pick_logger().get_today_picks(sport)


def check_grade_ready(date: Optional[str] = None, sports: Optional[List[str]] = None) -> Dict:
    """Validate all picks are grade-ready (convenience function)."""
    return get_pick_logger().validate_all_picks_grade_ready(date, sports)


def start_pick_run() -> str:
    """Start a new pick generation run (convenience function)."""
    return get_pick_logger().start_run()


def end_pick_run() -> Dict:
    """End current pick run and get summary (convenience function)."""
    return get_pick_logger().end_run()


def get_run_summary(date: Optional[str] = None) -> Dict:
    """Get summary of all runs for a date (convenience function)."""
    return get_pick_logger().get_run_summary(date)
