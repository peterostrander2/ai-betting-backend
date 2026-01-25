"""
v10.92 Growth Ledger - The Fused Learning Loop
===============================================
Every result. Every upgrade. Every learning step.
Every Boss instinct call. Every back-and-forth. All growth fused.

This module captures the complete evolution of the system:
1. RESULTS - Every win/loss with full context
2. UPGRADES - Every threshold/weight change
3. LEARNING - Every bias correction and tuning step
4. BOSS CALLS - High-confidence picks (GOLD_STAR) outcomes
5. EVOLUTION - System state changes over time

All data persisted to JSONL for complete auditability.
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

try:
    from zoneinfo import ZoneInfo
    ET_TIMEZONE = ZoneInfo("America/New_York")
except ImportError:
    ET_TIMEZONE = None

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class EventType(str, Enum):
    """Types of learning events captured."""
    PICK_LOGGED = "pick_logged"           # New pick generated
    PICK_GRADED = "pick_graded"           # Pick result recorded
    BOSS_CALL_HIT = "boss_call_hit"       # GOLD_STAR pick won
    BOSS_CALL_MISS = "boss_call_miss"     # GOLD_STAR pick lost
    WEIGHT_ADJUSTED = "weight_adjusted"   # Micro-weight changed
    THRESHOLD_TUNED = "threshold_tuned"   # Tier threshold changed
    BIAS_CORRECTED = "bias_corrected"     # Bias adjustment made
    CONFIG_RESET = "config_reset"         # Config reset to factory
    CIRCUIT_BREAKER = "circuit_breaker"   # Emergency reset triggered
    STREAK_DETECTED = "streak_detected"   # Win/loss streak detected
    PATTERN_LEARNED = "pattern_learned"   # New pattern identified
    DAILY_SUMMARY = "daily_summary"       # End of day summary


LEDGER_PATH = os.getenv("GROWTH_LEDGER_PATH", "./grader_data/growth_ledger.jsonl")


# ============================================================================
# GROWTH EVENT STRUCTURE
# ============================================================================

@dataclass
class GrowthEvent:
    """A single learning/growth event."""
    event_type: str
    timestamp: str
    sport: str
    details: Dict[str, Any]

    # Context
    engine_version: str = "v10.92"
    session_id: str = ""

    # Metrics at time of event
    metrics_snapshot: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "sport": self.sport,
            "details": self.details,
            "engine_version": self.engine_version,
            "session_id": self.session_id,
            "metrics_snapshot": self.metrics_snapshot
        }


# ============================================================================
# GROWTH LEDGER - THE FUSED LEARNING LOOP
# ============================================================================

class GrowthLedger:
    """
    Captures every moment of system growth and learning.

    This is the complete audit trail of how the system evolves:
    - What picks were made and why
    - What results came in
    - What was learned from each result
    - What adjustments were made
    - How the system changed over time
    """

    def __init__(self, ledger_path: str = LEDGER_PATH):
        self.ledger_path = ledger_path
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.engine_version = "v10.92"

        # In-memory buffers for quick access
        self._today_events: List[GrowthEvent] = []
        self._boss_calls: List[Dict] = []
        self._learning_steps: List[Dict] = []

        # Stats
        self._session_wins = 0
        self._session_losses = 0
        self._session_boss_hits = 0
        self._session_boss_misses = 0

        # Ensure directory exists
        os.makedirs(os.path.dirname(ledger_path), exist_ok=True)

        logger.info(f"GrowthLedger initialized: session={self.session_id}")

    def _get_timestamp(self) -> str:
        """Get current timestamp in ET."""
        if ET_TIMEZONE:
            return datetime.now(ET_TIMEZONE).isoformat()
        return datetime.now().isoformat()

    def _append_to_ledger(self, event: GrowthEvent):
        """Append event to JSONL ledger file."""
        try:
            with open(self.ledger_path, 'a') as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to ledger: {e}")

        self._today_events.append(event)

    # ========================================================================
    # RESULT LOGGING
    # ========================================================================

    def log_pick(self, sport: str, pick_data: Dict[str, Any]) -> str:
        """
        Log a new pick being generated.

        Args:
            sport: Sport code
            pick_data: Full pick details including scores, reasons, etc.

        Returns:
            Event ID for tracking
        """
        event = GrowthEvent(
            event_type=EventType.PICK_LOGGED,
            timestamp=self._get_timestamp(),
            sport=sport.upper(),
            details={
                "pick_id": pick_data.get("pick_id", ""),
                "player_name": pick_data.get("player_name", ""),
                "game": pick_data.get("game", ""),
                "pick_type": pick_data.get("pick_type", ""),
                "line": pick_data.get("line"),
                "tier": pick_data.get("tier", ""),
                "smash_score": pick_data.get("smash_score"),
                "research_score": pick_data.get("research_score"),
                "esoteric_score": pick_data.get("esoteric_score"),
                "reasons": pick_data.get("reasons", []),
                "signals_active": pick_data.get("signals_active", []),
                "is_boss_call": pick_data.get("tier") == "GOLD_STAR"
            },
            engine_version=self.engine_version,
            session_id=self.session_id
        )

        self._append_to_ledger(event)

        if pick_data.get("tier") == "GOLD_STAR":
            self._boss_calls.append({
                "pick_id": pick_data.get("pick_id"),
                "logged_at": event.timestamp,
                "sport": sport.upper()
            })

        return event.timestamp

    def log_result(self, sport: str, pick_id: str, result: str,
                   actual_value: Optional[float] = None,
                   profit_units: float = 0.0,
                   pick_context: Optional[Dict] = None) -> None:
        """
        Log the result of a graded pick.

        Args:
            sport: Sport code
            pick_id: Pick identifier
            result: WIN, LOSS, or PUSH
            actual_value: Actual stat value (for props)
            profit_units: Units won/lost
            pick_context: Original pick data for analysis
        """
        is_win = result.upper() == "WIN"
        is_loss = result.upper() == "LOSS"

        # Track session stats
        if is_win:
            self._session_wins += 1
        elif is_loss:
            self._session_losses += 1

        # Check if this was a Boss call
        tier = (pick_context or {}).get("tier", "")
        is_boss_call = tier == "GOLD_STAR"

        if is_boss_call:
            if is_win:
                self._session_boss_hits += 1
                event_type = EventType.BOSS_CALL_HIT
            else:
                self._session_boss_misses += 1
                event_type = EventType.BOSS_CALL_MISS
        else:
            event_type = EventType.PICK_GRADED

        event = GrowthEvent(
            event_type=event_type,
            timestamp=self._get_timestamp(),
            sport=sport.upper(),
            details={
                "pick_id": pick_id,
                "result": result.upper(),
                "actual_value": actual_value,
                "profit_units": profit_units,
                "tier": tier,
                "smash_score": (pick_context or {}).get("smash_score"),
                "is_boss_call": is_boss_call,
                "session_record": f"{self._session_wins}-{self._session_losses}",
                "session_boss_record": f"{self._session_boss_hits}-{self._session_boss_misses}"
            },
            engine_version=self.engine_version,
            session_id=self.session_id,
            metrics_snapshot={
                "session_wins": self._session_wins,
                "session_losses": self._session_losses,
                "session_hit_rate": self._session_wins / max(1, self._session_wins + self._session_losses) * 100,
                "boss_hits": self._session_boss_hits,
                "boss_misses": self._session_boss_misses
            }
        )

        self._append_to_ledger(event)

        # Log special message for Boss calls
        if is_boss_call:
            status = "🔥 HIT" if is_win else "❌ MISS"
            logger.info(f"BOSS CALL {status}: {pick_id} ({tier}) - {result}")

    # ========================================================================
    # LEARNING STEP LOGGING
    # ========================================================================

    def log_weight_adjustment(self, sport: str, signal: str,
                              old_weight: float, new_weight: float,
                              reason: str) -> None:
        """Log a micro-weight adjustment."""
        event = GrowthEvent(
            event_type=EventType.WEIGHT_ADJUSTED,
            timestamp=self._get_timestamp(),
            sport=sport.upper(),
            details={
                "signal": signal,
                "old_weight": old_weight,
                "new_weight": new_weight,
                "change": round(new_weight - old_weight, 4),
                "direction": "increase" if new_weight > old_weight else "decrease",
                "reason": reason
            },
            engine_version=self.engine_version,
            session_id=self.session_id
        )

        self._append_to_ledger(event)
        self._learning_steps.append(event.to_dict())

        logger.info(f"LEARNING: {sport} {signal} weight {old_weight:.3f} → {new_weight:.3f} ({reason})")

    def log_threshold_tuning(self, sport: str, tier: str,
                             old_threshold: float, new_threshold: float,
                             reason: str, metrics: Optional[Dict] = None) -> None:
        """Log a tier threshold adjustment."""
        event = GrowthEvent(
            event_type=EventType.THRESHOLD_TUNED,
            timestamp=self._get_timestamp(),
            sport=sport.upper(),
            details={
                "tier": tier,
                "old_threshold": old_threshold,
                "new_threshold": new_threshold,
                "change": round(new_threshold - old_threshold, 3),
                "direction": "tightened" if new_threshold > old_threshold else "loosened",
                "reason": reason
            },
            engine_version=self.engine_version,
            session_id=self.session_id,
            metrics_snapshot=metrics
        )

        self._append_to_ledger(event)
        self._learning_steps.append(event.to_dict())

        direction = "TIGHTENED" if new_threshold > old_threshold else "LOOSENED"
        logger.info(f"LEARNING: {sport} {tier} {direction} {old_threshold:.2f} → {new_threshold:.2f}")

    def log_bias_correction(self, sport: str, bias_type: str,
                            bias_value: float, correction: str,
                            before_state: Dict, after_state: Dict) -> None:
        """Log a bias correction from the auto-grader."""
        event = GrowthEvent(
            event_type=EventType.BIAS_CORRECTED,
            timestamp=self._get_timestamp(),
            sport=sport.upper(),
            details={
                "bias_type": bias_type,
                "bias_value": bias_value,
                "correction": correction,
                "before_state": before_state,
                "after_state": after_state
            },
            engine_version=self.engine_version,
            session_id=self.session_id
        )

        self._append_to_ledger(event)
        self._learning_steps.append(event.to_dict())

        logger.info(f"BIAS CORRECTION: {sport} {bias_type}={bias_value:.2f} → {correction}")

    def log_circuit_breaker(self, sport: str, trigger_reason: str,
                            affected_signals: List[str]) -> None:
        """Log a circuit breaker event (emergency reset)."""
        event = GrowthEvent(
            event_type=EventType.CIRCUIT_BREAKER,
            timestamp=self._get_timestamp(),
            sport=sport.upper(),
            details={
                "trigger_reason": trigger_reason,
                "affected_signals": affected_signals,
                "action": "RESET_TO_FACTORY"
            },
            engine_version=self.engine_version,
            session_id=self.session_id
        )

        self._append_to_ledger(event)

        logger.warning(f"⚠️ CIRCUIT BREAKER: {sport} - {trigger_reason}")

    def log_pattern_learned(self, sport: str, pattern_type: str,
                            pattern_details: Dict, confidence: float) -> None:
        """Log a newly identified pattern."""
        event = GrowthEvent(
            event_type=EventType.PATTERN_LEARNED,
            timestamp=self._get_timestamp(),
            sport=sport.upper(),
            details={
                "pattern_type": pattern_type,
                "pattern_details": pattern_details,
                "confidence": confidence
            },
            engine_version=self.engine_version,
            session_id=self.session_id
        )

        self._append_to_ledger(event)

        logger.info(f"PATTERN LEARNED: {sport} {pattern_type} (confidence: {confidence:.1%})")

    # ========================================================================
    # DAILY SUMMARY
    # ========================================================================

    def generate_daily_summary(self) -> Dict[str, Any]:
        """
        Generate end-of-day summary of all growth and learning.

        Returns:
            Complete summary of the day's evolution
        """
        summary = {
            "session_id": self.session_id,
            "timestamp": self._get_timestamp(),
            "engine_version": self.engine_version,

            # Results
            "results": {
                "total_picks": self._session_wins + self._session_losses,
                "wins": self._session_wins,
                "losses": self._session_losses,
                "hit_rate": self._session_wins / max(1, self._session_wins + self._session_losses) * 100
            },

            # Boss Calls (GOLD_STAR)
            "boss_calls": {
                "total": self._session_boss_hits + self._session_boss_misses,
                "hits": self._session_boss_hits,
                "misses": self._session_boss_misses,
                "hit_rate": self._session_boss_hits / max(1, self._session_boss_hits + self._session_boss_misses) * 100
            },

            # Learning
            "learning_steps": len(self._learning_steps),
            "learning_details": self._learning_steps[-10:],  # Last 10 steps

            # Events count by type
            "events_by_type": self._count_events_by_type(),

            # Total events today
            "total_events": len(self._today_events)
        }

        # Log the summary
        event = GrowthEvent(
            event_type=EventType.DAILY_SUMMARY,
            timestamp=self._get_timestamp(),
            sport="ALL",
            details=summary,
            engine_version=self.engine_version,
            session_id=self.session_id
        )

        self._append_to_ledger(event)

        return summary

    def _count_events_by_type(self) -> Dict[str, int]:
        """Count events by type for today."""
        counts = {}
        for event in self._today_events:
            event_type = event.event_type
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts

    # ========================================================================
    # QUERY METHODS
    # ========================================================================

    def get_recent_boss_calls(self, limit: int = 20) -> List[Dict]:
        """Get recent GOLD_STAR pick outcomes."""
        boss_events = [
            e.to_dict() for e in self._today_events
            if e.event_type in [EventType.BOSS_CALL_HIT, EventType.BOSS_CALL_MISS]
        ]
        return boss_events[-limit:]

    def get_learning_history(self, limit: int = 50) -> List[Dict]:
        """Get recent learning steps."""
        return self._learning_steps[-limit:]

    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session statistics."""
        return {
            "session_id": self.session_id,
            "wins": self._session_wins,
            "losses": self._session_losses,
            "hit_rate": self._session_wins / max(1, self._session_wins + self._session_losses) * 100,
            "boss_hits": self._session_boss_hits,
            "boss_misses": self._session_boss_misses,
            "boss_hit_rate": self._session_boss_hits / max(1, self._session_boss_hits + self._session_boss_misses) * 100,
            "learning_steps": len(self._learning_steps),
            "total_events": len(self._today_events)
        }

    def read_ledger(self, days_back: int = 7,
                    event_types: Optional[List[str]] = None) -> List[Dict]:
        """
        Read events from the ledger file.

        Args:
            days_back: How many days to look back
            event_types: Filter by event types (optional)

        Returns:
            List of matching events
        """
        events = []
        cutoff = datetime.now() - timedelta(days=days_back)

        if not os.path.exists(self.ledger_path):
            return events

        try:
            with open(self.ledger_path, 'r') as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())

                        # Date filter
                        event_time = datetime.fromisoformat(event.get("timestamp", "").replace("Z", "+00:00"))
                        if event_time.replace(tzinfo=None) < cutoff:
                            continue

                        # Type filter
                        if event_types and event.get("event_type") not in event_types:
                            continue

                        events.append(event)
                    except:
                        continue
        except Exception as e:
            logger.error(f"Failed to read ledger: {e}")

        return events


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_growth_ledger: Optional[GrowthLedger] = None


def get_growth_ledger() -> GrowthLedger:
    """Get or create the singleton GrowthLedger instance."""
    global _growth_ledger
    if _growth_ledger is None:
        _growth_ledger = GrowthLedger()
    return _growth_ledger


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def log_pick(sport: str, pick_data: Dict) -> str:
    """Convenience function to log a pick."""
    return get_growth_ledger().log_pick(sport, pick_data)


def log_result(sport: str, pick_id: str, result: str, **kwargs) -> None:
    """Convenience function to log a result."""
    get_growth_ledger().log_result(sport, pick_id, result, **kwargs)


def log_learning(sport: str, learning_type: str, details: Dict) -> None:
    """Convenience function to log any learning event."""
    ledger = get_growth_ledger()

    if learning_type == "weight":
        ledger.log_weight_adjustment(
            sport,
            details.get("signal", ""),
            details.get("old", 1.0),
            details.get("new", 1.0),
            details.get("reason", "")
        )
    elif learning_type == "threshold":
        ledger.log_threshold_tuning(
            sport,
            details.get("tier", ""),
            details.get("old", 0),
            details.get("new", 0),
            details.get("reason", ""),
            details.get("metrics")
        )
    elif learning_type == "bias":
        ledger.log_bias_correction(
            sport,
            details.get("bias_type", ""),
            details.get("bias_value", 0),
            details.get("correction", ""),
            details.get("before", {}),
            details.get("after", {})
        )


def get_daily_summary() -> Dict[str, Any]:
    """Generate and return daily summary."""
    return get_growth_ledger().generate_daily_summary()


def get_session_stats() -> Dict[str, Any]:
    """Get current session statistics."""
    return get_growth_ledger().get_session_stats()
