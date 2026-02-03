"""
PERSISTENCE - Pick Storage & Retrieval (AutoGrader Compatible)

This module provides pick envelope storage to Railway volume with
all required fields for autograder compatibility.

CRITICAL RULES:
1. Every pick >= 6.5 MUST be written to persistent storage
2. Storage MUST survive container restart (Railway volume)
3. All required fields MUST be present for AutoGrader
4. Atomic writes (temp + rename) to prevent corruption
5. JSONL format for append-only performance

STORAGE PATH:
    Production: /data/pick_logs/picks_{YYYY-MM-DD}.jsonl
    Local: ./grader_data/pick_logs/picks_{YYYY-MM-DD}.jsonl

REQUIRED FIELDS (from core.invariants.PICK_STORAGE_REQUIRED_FIELDS):
    - prediction_id (stable hash)
    - sport, market_type, line_at_bet, odds_at_bet, book
    - event_start_time_et, created_at
    - final_score, tier
    - ai_score, research_score, esoteric_score, jarvis_score
    - ai_reasons, research_reasons, esoteric_reasons, jarvis_reasons

USAGE:
    from core.persistence import save_pick, load_pending_picks

    # Save pick
    pick_id = save_pick(pick_envelope)

    # Load pending picks for grading
    pending = load_pending_picks(date_str="2026-01-28")
"""

from typing import Dict, List, Any, Optional, Tuple
import logging
import os

# Import core invariants
try:
    from core.invariants import (
        PICK_STORAGE_REQUIRED_FIELDS,
        COMMUNITY_MIN_SCORE,
        validate_pick_storage,
    )
    INVARIANTS_AVAILABLE = True
except ImportError:
    INVARIANTS_AVAILABLE = False
    PICK_STORAGE_REQUIRED_FIELDS = [
        "prediction_id", "sport", "market_type", "line_at_bet", "odds_at_bet",
        "book", "event_start_time_et", "created_at", "final_score", "tier",
        "ai_score", "research_score", "esoteric_score", "jarvis_score",
        "ai_reasons", "research_reasons", "esoteric_reasons", "jarvis_reasons",
    ]
    COMMUNITY_MIN_SCORE = 6.5

# Try to import pick_logger
try:
    from pick_logger import PickLogger, get_pick_logger, get_today_date_et
    PICK_LOGGER_AVAILABLE = True
except ImportError:
    PICK_LOGGER_AVAILABLE = False

logger = logging.getLogger(__name__)

# =============================================================================
# GLOBAL PICK LOGGER INSTANCE
# =============================================================================

_pick_logger_singleton = None

def get_persistence() -> 'PickLogger':
    """
    Get singleton pick logger instance.

    Returns:
        PickLogger: Singleton instance for pick storage
    """
    global _pick_logger_singleton

    if _pick_logger_singleton is None:
        if PICK_LOGGER_AVAILABLE:
            _pick_logger_singleton = get_pick_logger()
        else:
            logger.error("pick_logger module not available, persistence disabled")
            _pick_logger_singleton = _FallbackPersistence()

    return _pick_logger_singleton


# =============================================================================
# PUBLIC API
# =============================================================================

def save_pick(
    pick_envelope: Dict[str, Any],
    validate: bool = True
) -> Dict[str, Any]:
    """
    Save pick envelope to persistent storage.

    Args:
        pick_envelope: Dict with all required fields
        validate: If True, validate required fields before saving

    Returns:
        Dict with:
            - pick_id: str (prediction_id from envelope)
            - logged: bool (True if saved, False if skipped)
            - skipped: bool (True if duplicate, False otherwise)
            - reason: str (skip reason if skipped)

    Raises:
        ValueError: If pick missing required fields and validate=True
    """
    # Validate required fields
    if validate and INVARIANTS_AVAILABLE:
        is_valid, error = validate_pick_storage(pick_envelope)
        if not is_valid:
            raise ValueError(error)

    # Check minimum score threshold
    final_score = pick_envelope.get("final_score", 0)
    if final_score < COMMUNITY_MIN_SCORE:
        return {
            "pick_id": pick_envelope.get("prediction_id", ""),
            "logged": False,
            "skipped": True,
            "reason": f"final_score {final_score} < {COMMUNITY_MIN_SCORE}"
        }

    # Get persistence instance
    persistence = get_persistence()

    if PICK_LOGGER_AVAILABLE:
        # Use real pick logger
        result = persistence.log_pick(
            pick_data=pick_envelope,
            game_start_time=pick_envelope.get("event_start_time_et", "")
        )
        return result
    else:
        # Fallback
        logger.warning("pick_logger not available, pick not persisted")
        return {
            "pick_id": pick_envelope.get("prediction_id", ""),
            "logged": False,
            "skipped": False,
            "reason": "pick_logger not available"
        }


def load_pending_picks(
    date_str: Optional[str] = None,
    sport: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Load pending picks for grading.

    Args:
        date_str: Optional date string (YYYY-MM-DD). If None, uses today.
        sport: Optional sport filter (NBA, NFL, etc.)

    Returns:
        List of pick envelopes with grade_status="PENDING"
    """
    persistence = get_persistence()

    if PICK_LOGGER_AVAILABLE:
        picks = persistence.get_picks_for_grading(date_str=date_str)

        # Filter by sport if specified
        if sport:
            picks = [p for p in picks if p.get("sport", "").upper() == sport.upper()]

        return picks
    else:
        logger.warning("pick_logger not available, no picks loaded")
        return []


def load_all_picks(
    date_str: Optional[str] = None,
    sport: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Load all picks for a given date (pending + graded).

    Args:
        date_str: Optional date string (YYYY-MM-DD). If None, uses today.
        sport: Optional sport filter

    Returns:
        List of all pick envelopes
    """
    persistence = get_persistence()

    if PICK_LOGGER_AVAILABLE:
        picks = persistence.get_picks_for_date(date_str=date_str)

        # Filter by sport if specified
        if sport:
            picks = [p for p in picks if p.get("sport", "").upper() == sport.upper()]

        return picks
    else:
        return []


def get_storage_stats() -> Dict[str, Any]:
    """
    Get persistence storage statistics.

    Returns:
        Dict with:
            - storage_path: str
            - total_predictions: int
            - pending_predictions: int
            - graded_predictions: int
            - last_prediction_time: str
            - by_sport: Dict[sport, count]
            - file_sizes: Dict[date, size_bytes]
    """
    persistence = get_persistence()

    if PICK_LOGGER_AVAILABLE:
        # Get today's date
        today = get_today_date_et()

        # Load all picks
        all_picks = persistence.get_picks_for_date(today)

        # Count by status
        pending = [p for p in all_picks if p.get("grade_status") == "PENDING"]
        graded = [p for p in all_picks if p.get("grade_status") in ["WIN", "LOSS", "PUSH"]]

        # Count by sport
        by_sport = {}
        for pick in all_picks:
            sport = pick.get("sport", "UNKNOWN")
            by_sport[sport] = by_sport.get(sport, 0) + 1

        # Get storage path
        storage_path = persistence.storage_path

        # Get last prediction time
        last_time = ""
        if all_picks:
            last_time = all_picks[-1].get("published_at", "")

        # Get file sizes
        file_sizes = {}
        if os.path.exists(storage_path):
            for filename in os.listdir(storage_path):
                if filename.endswith(".jsonl"):
                    filepath = os.path.join(storage_path, filename)
                    file_sizes[filename] = os.path.getsize(filepath)

        return {
            "storage_path": storage_path,
            "total_predictions": len(all_picks),
            "pending_predictions": len(pending),
            "graded_predictions": len(graded),
            "last_prediction_time": last_time,
            "by_sport": by_sport,
            "file_sizes": file_sizes,
        }
    else:
        return {
            "storage_path": "unavailable",
            "total_predictions": 0,
            "pending_predictions": 0,
            "graded_predictions": 0,
            "last_prediction_time": "",
            "by_sport": {},
            "file_sizes": {},
        }


def validate_storage_writable() -> Tuple[bool, str]:
    """
    Validate that storage path is writable.

    Returns:
        Tuple of (is_writable: bool, error_message: str)
    """
    persistence = get_persistence()

    if not PICK_LOGGER_AVAILABLE:
        return False, "pick_logger module not available"

    try:
        storage_path = persistence.storage_path

        # Check if directory exists
        if not os.path.exists(storage_path):
            os.makedirs(storage_path, exist_ok=True)

        # Try to write a test file
        test_file = os.path.join(storage_path, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")

        # Clean up test file
        os.remove(test_file)

        return True, ""

    except Exception as e:
        return False, f"Storage write test failed: {str(e)}"


# =============================================================================
# FALLBACK IMPLEMENTATION
# =============================================================================

class _FallbackPersistence:
    """
    Fallback persistence when pick_logger not available.

    This is a no-op implementation that prevents crashes but logs warnings.
    """

    def __init__(self):
        self.storage_path = "unavailable"

    def log_pick(self, pick_data, game_start_time=""):
        logger.warning("pick_logger not available, pick not saved")
        return {
            "pick_id": "",
            "logged": False,
            "skipped": False,
            "reason": "pick_logger not available"
        }

    def get_picks_for_grading(self, date_str=None):
        return []

    def get_picks_for_date(self, date_str=None):
        return []


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "save_pick",
    "load_pending_picks",
    "load_all_picks",
    "get_storage_stats",
    "validate_storage_writable",
    "get_persistence",
]
