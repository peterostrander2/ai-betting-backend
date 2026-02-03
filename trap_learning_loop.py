"""
Trap Learning Loop - Hypothesis-Driven Weight Adjustment (v19.0)
================================================================
Pre-game: Define conditional rules (traps)
Post-game: Evaluate conditions, apply adjustments

Uses JSONL storage at /data/trap_learning/
Integrates with daily_scheduler.py for automatic evaluation at 6:15 AM ET

Examples:
- "If Dallas wins by 20, adjust Public Fade weight down by 1%"
- "If Rangers lose on a '1' day, audit Name Sum vs City Sum cipher"
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json
import os
import logging
import hashlib
import fcntl

logger = logging.getLogger(__name__)

# ============================================
# CONFIGURATION
# ============================================

# Safety Guards
MAX_SINGLE_ADJUSTMENT = 0.05      # 5% max per trigger
MAX_CUMULATIVE_ADJUSTMENT = 0.15  # 15% lifetime cap per trap
DEFAULT_COOLDOWN_HOURS = 24       # Min time between triggers
DEFAULT_MAX_TRIGGERS_WEEK = 3     # Weekly rate limit
LEARNING_DECAY = 0.7              # Each trigger = 70% of previous

# Supported engines and their adjustable parameters
SUPPORTED_ENGINES = {
    "research": {
        "weight_public_fade": (0.0, 2.0),
        "weight_sharp_money": (0.0, 3.0),
        "weight_line_variance": (0.0, 3.0),
        "splits_base": (2.0, 3.0),
    },
    "esoteric": {
        "weight_gematria": (0.0, 1.0),
        "weight_astro": (0.0, 1.0),
        "weight_fib": (0.0, 1.0),
        "weight_vortex": (0.0, 1.0),
        "weight_daily_edge": (0.0, 1.0),
        "weight_glitch": (0.0, 1.0),
    },
    "jarvis": {
        "trigger_boost_2178": (0.0, 20.0),
        "trigger_boost_201": (0.0, 12.0),
        "trigger_boost_33": (0.0, 10.0),
        "trigger_boost_93": (0.0, 10.0),
        "trigger_boost_322": (0.0, 10.0),
        "trigger_boost_666": (0.0, 10.0),
        "trigger_boost_1656": (0.0, 15.0),
        "trigger_boost_552": (0.0, 12.0),
        "trigger_boost_138": (0.0, 12.0),
        "baseline_score": (3.0, 5.0),
    },
    "context": {
        "weight_def_rank": (0.1, 0.7),
        "weight_pace": (0.1, 0.5),
        "weight_vacuum": (0.1, 0.4),
    },
    "ai": {
        "lstm_weight": (0.1, 0.4),
        "ensemble_weight": (0.1, 0.4),
    },
}

# Supported condition fields
CONDITION_FIELDS = {
    # Game outcome fields
    "result": ["win", "loss", "push"],
    "margin": "numeric",  # Point differential (positive = win margin)
    "total_points": "numeric",
    "spread_result": ["covered", "lost", "push"],
    "spread_margin": "numeric",  # Margin vs spread
    "over_under_result": ["over", "under", "push"],

    # Date/time fields
    "day_number": "numeric",  # 1-31
    "day_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "month": "numeric",  # 1-12
    "numerology_day": "numeric",  # Date reduced to single digit (1-9)

    # Gematria fields
    "name_sum_cipher": "numeric",
    "city_sum_cipher": "numeric",
    "combined_cipher": "numeric",

    # Engine scores (at bet time)
    "ai_score_was": "numeric",
    "research_score_was": "numeric",
    "esoteric_score_was": "numeric",
    "jarvis_score_was": "numeric",
    "final_score_was": "numeric",

    # Team/matchup
    "team": "string",
    "home_team": "string",
    "away_team": "string",
    "is_home": "boolean",
}

COMPARATORS = ["==", "!=", ">=", "<=", ">", "<", "IN", "BETWEEN"]


# ============================================
# DATA CLASSES
# ============================================

@dataclass
class TrapDefinition:
    """Definition of a pre-game trap/hypothesis."""
    trap_id: str
    name: str
    sport: str  # NBA, NFL, MLB, NHL, NCAAB, ALL
    condition: Dict[str, Any]
    action: Dict[str, Any]
    target_engine: str
    target_parameter: str
    team: Optional[str] = None
    description: Optional[str] = None
    adjustment_cap: float = 0.05
    cooldown_hours: int = 24
    max_triggers_per_week: int = 3
    status: str = "ACTIVE"  # ACTIVE, PAUSED, RETIRED
    created_at: str = ""
    created_by: str = "system"
    expires_at: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        # Validate adjustment cap
        if self.adjustment_cap > MAX_SINGLE_ADJUSTMENT:
            self.adjustment_cap = MAX_SINGLE_ADJUSTMENT


@dataclass
class TrapEvaluation:
    """Result of evaluating a trap against a game outcome."""
    trap_id: str
    event_id: str
    sport: str
    game_date: str
    home_team: str
    away_team: str
    condition_met: bool
    condition_values: Dict[str, Any]
    action_taken: str  # APPLIED, SKIPPED_COOLDOWN, SKIPPED_CAP, SKIPPED_LIMIT, NONE
    adjustment_applied: Optional[float] = None
    adjustment_reason: Optional[str] = None
    evaluated_at: str = ""

    def __post_init__(self):
        if not self.evaluated_at:
            self.evaluated_at = datetime.now().isoformat()


@dataclass
class AdjustmentRecord:
    """Record of a weight adjustment made by a trap."""
    trap_id: str
    evaluation_id: str
    target_engine: str
    target_parameter: str
    old_value: float
    new_value: float
    delta: float
    reason: str
    cumulative_adjustment: float
    applied_at: str = ""

    def __post_init__(self):
        if not self.applied_at:
            self.applied_at = datetime.now().isoformat()


# ============================================
# TRAP LEARNING LOOP
# ============================================

class TrapLearningLoop:
    """
    The Pre-Game / Post-Game Learning System.

    Manages trap definitions, evaluates conditions against game outcomes,
    and applies weight adjustments with safety guards.
    """

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            # Use Railway volume path
            base = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "./grader_data")
            storage_path = os.path.join(base, "trap_learning")

        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)

        self.traps_file = os.path.join(storage_path, "traps.jsonl")
        self.evaluations_file = os.path.join(storage_path, "evaluations.jsonl")
        self.adjustments_file = os.path.join(storage_path, "adjustments.jsonl")

        self.traps: Dict[str, TrapDefinition] = {}
        self.evaluations: List[TrapEvaluation] = []
        self.adjustments: List[AdjustmentRecord] = []

        # Current engine weights (loaded from respective modules)
        self._engine_weights: Dict[str, Dict[str, float]] = {}

        self._load_state()
        logger.info("TrapLearningLoop initialized: %d traps loaded from %s",
                    len(self.traps), storage_path)

    # ===== TRAP MANAGEMENT =====

    def create_trap(self, trap_data: Dict[str, Any]) -> TrapDefinition:
        """Create a new trap definition."""
        # Generate trap_id if not provided
        if "trap_id" not in trap_data:
            trap_data["trap_id"] = self._generate_trap_id(trap_data)

        trap = TrapDefinition(**trap_data)

        # Validate
        self._validate_trap(trap)

        # Check for duplicates
        if trap.trap_id in self.traps:
            raise ValueError(f"Trap with ID '{trap.trap_id}' already exists")

        # Store
        self.traps[trap.trap_id] = trap
        self._save_traps()

        logger.info("Created trap: %s (%s)", trap.trap_id, trap.name)
        return trap

    def get_trap(self, trap_id: str) -> Optional[TrapDefinition]:
        """Get a trap by ID."""
        return self.traps.get(trap_id)

    def get_traps(self, sport: Optional[str] = None, status: str = "ACTIVE") -> List[TrapDefinition]:
        """Get traps, optionally filtered by sport and status."""
        traps = list(self.traps.values())

        if status:
            traps = [t for t in traps if t.status == status]

        if sport:
            traps = [t for t in traps if t.sport in [sport, "ALL"]]

        return traps

    def get_active_traps(self) -> List[TrapDefinition]:
        """Get all active traps."""
        return self.get_traps(status="ACTIVE")

    def update_status(self, trap_id: str, status: str) -> bool:
        """Update trap status (ACTIVE, PAUSED, RETIRED)."""
        if status not in ["ACTIVE", "PAUSED", "RETIRED"]:
            raise ValueError(f"Invalid status: {status}")

        trap = self.traps.get(trap_id)
        if not trap:
            return False

        trap.status = status
        self._save_traps()
        logger.info("Updated trap %s status to %s", trap_id, status)
        return True

    def delete_trap(self, trap_id: str) -> bool:
        """Delete a trap (actually retires it for audit trail)."""
        return self.update_status(trap_id, "RETIRED")

    def _generate_trap_id(self, trap_data: Dict) -> str:
        """Generate a deterministic trap ID."""
        key = f"{trap_data.get('sport', '')}|{trap_data.get('name', '')}|{trap_data.get('target_engine', '')}"
        return hashlib.sha1(key.encode()).hexdigest()[:12]

    def _validate_trap(self, trap: TrapDefinition):
        """Validate trap structure and safety bounds."""
        # Check engine
        if trap.target_engine not in SUPPORTED_ENGINES:
            raise ValueError(f"Invalid engine: {trap.target_engine}. "
                           f"Supported: {list(SUPPORTED_ENGINES.keys())}")

        # Check parameter
        engine_params = SUPPORTED_ENGINES[trap.target_engine]
        if trap.target_parameter not in engine_params and trap.action.get("type") != "AUDIT_TRIGGER":
            raise ValueError(f"Invalid parameter '{trap.target_parameter}' for engine '{trap.target_engine}'. "
                           f"Supported: {list(engine_params.keys())}")

        # Check sport
        valid_sports = ["NBA", "NFL", "MLB", "NHL", "NCAAB", "ALL"]
        if trap.sport not in valid_sports:
            raise ValueError(f"Invalid sport: {trap.sport}. Supported: {valid_sports}")

        # Validate condition structure
        self._validate_condition(trap.condition)

        # Check adjustment cap
        if trap.adjustment_cap > MAX_SINGLE_ADJUSTMENT:
            raise ValueError(f"Adjustment cap {trap.adjustment_cap} exceeds max {MAX_SINGLE_ADJUSTMENT}")

    def _validate_condition(self, condition: Dict):
        """Validate condition JSON structure."""
        if "operator" not in condition:
            raise ValueError("Condition must have 'operator' (AND/OR)")

        if condition["operator"] not in ["AND", "OR"]:
            raise ValueError("Operator must be AND or OR")

        if "conditions" not in condition or not isinstance(condition["conditions"], list):
            raise ValueError("Condition must have 'conditions' array")

        for cond in condition["conditions"]:
            required = ["field", "comparator", "value"]
            if not all(k in cond for k in required):
                raise ValueError(f"Sub-condition missing required fields: {required}")

            if cond["field"] not in CONDITION_FIELDS:
                raise ValueError(f"Unknown condition field: {cond['field']}. "
                               f"Supported: {list(CONDITION_FIELDS.keys())}")

            if cond["comparator"] not in COMPARATORS:
                raise ValueError(f"Unknown comparator: {cond['comparator']}. "
                               f"Supported: {COMPARATORS}")

    # ===== CONDITION EVALUATION =====

    def evaluate_trap(self, trap: TrapDefinition, game_result: Dict[str, Any],
                      dry_run: bool = False) -> TrapEvaluation:
        """Evaluate a single trap against game result."""
        # Check condition
        condition_met = self._check_condition(trap.condition, game_result)

        # Collect actual values used for each condition field
        condition_values = {}
        for cond in trap.condition.get("conditions", []):
            field = cond["field"]
            condition_values[field] = game_result.get(field)

        # Determine action
        action_taken = "NONE"
        adjustment_applied = None
        adjustment_reason = None

        if condition_met:
            if dry_run:
                action_taken = "DRY_RUN"
                adjustment_applied = self._calculate_adjustment(trap)
                adjustment_reason = "Would apply if not dry run"
            else:
                valid, reason = self._validate_adjustment_safety(trap)
                if valid:
                    adjustment_applied = self._apply_adjustment(trap, game_result)
                    action_taken = "APPLIED"
                    adjustment_reason = f"Condition met: {trap.name}"
                else:
                    action_taken = f"SKIPPED_{reason}"
                    adjustment_reason = reason

        evaluation = TrapEvaluation(
            trap_id=trap.trap_id,
            event_id=game_result.get("event_id", "unknown"),
            sport=trap.sport if trap.sport != "ALL" else game_result.get("sport", "unknown"),
            game_date=game_result.get("game_date", ""),
            home_team=game_result.get("home_team", ""),
            away_team=game_result.get("away_team", ""),
            condition_met=condition_met,
            condition_values=condition_values,
            action_taken=action_taken,
            adjustment_applied=adjustment_applied,
            adjustment_reason=adjustment_reason
        )

        if not dry_run:
            self.evaluations.append(evaluation)
            self._save_evaluations()

        return evaluation

    def _check_condition(self, condition: Dict, game_result: Dict) -> bool:
        """Check if condition is met."""
        operator = condition.get("operator", "AND")
        sub_conditions = condition.get("conditions", [])

        if not sub_conditions:
            return False

        results = []
        for cond in sub_conditions:
            field = cond["field"]
            comparator = cond["comparator"]
            expected = cond["value"]
            actual = game_result.get(field)

            result = self._compare(actual, comparator, expected)
            results.append(result)

            logger.debug("Condition check: %s %s %s (actual=%s) -> %s",
                        field, comparator, expected, actual, result)

        if operator == "AND":
            return all(results)
        elif operator == "OR":
            return any(results)

        return False

    def _compare(self, actual: Any, comparator: str, expected: Any) -> bool:
        """Perform comparison."""
        if actual is None:
            return False

        try:
            if comparator == "==":
                return actual == expected
            elif comparator == "!=":
                return actual != expected
            elif comparator == ">=":
                return float(actual) >= float(expected)
            elif comparator == "<=":
                return float(actual) <= float(expected)
            elif comparator == ">":
                return float(actual) > float(expected)
            elif comparator == "<":
                return float(actual) < float(expected)
            elif comparator == "IN":
                return actual in expected
            elif comparator == "BETWEEN":
                return expected[0] <= float(actual) <= expected[1]
        except (TypeError, ValueError) as e:
            logger.warning("Comparison error: %s %s %s - %s", actual, comparator, expected, e)
            return False

        return False

    # ===== SAFETY VALIDATION =====

    def _validate_adjustment_safety(self, trap: TrapDefinition) -> Tuple[bool, str]:
        """Validate that adjustment is safe to apply."""
        # 1. Check cooldown
        last_trigger = self._get_last_trigger_time(trap.trap_id)
        if last_trigger:
            hours_since = (datetime.now() - last_trigger).total_seconds() / 3600
            if hours_since < trap.cooldown_hours:
                return False, f"COOLDOWN ({trap.cooldown_hours - hours_since:.1f}h remaining)"

        # 2. Check weekly limit
        week_triggers = self._count_triggers_this_week(trap.trap_id)
        if week_triggers >= trap.max_triggers_per_week:
            return False, f"WEEKLY_LIMIT ({week_triggers}/{trap.max_triggers_per_week})"

        # 3. Check cumulative cap
        cumulative = self._get_cumulative_adjustment(trap.trap_id)
        proposed = self._calculate_adjustment(trap)
        if abs(cumulative + proposed) > MAX_CUMULATIVE_ADJUSTMENT:
            return False, f"CUMULATIVE_CAP ({abs(cumulative):.2%} + {abs(proposed):.2%} > {MAX_CUMULATIVE_ADJUSTMENT:.0%})"

        return True, "OK"

    def _get_last_trigger_time(self, trap_id: str) -> Optional[datetime]:
        """Get the last time this trap was triggered."""
        for eval_record in reversed(self.evaluations):
            if eval_record.trap_id == trap_id and eval_record.action_taken == "APPLIED":
                return datetime.fromisoformat(eval_record.evaluated_at)
        return None

    def _count_triggers_this_week(self, trap_id: str) -> int:
        """Count how many times this trap triggered in the last 7 days."""
        week_ago = datetime.now() - timedelta(days=7)
        count = 0
        for eval_record in self.evaluations:
            if eval_record.trap_id == trap_id and eval_record.action_taken == "APPLIED":
                eval_time = datetime.fromisoformat(eval_record.evaluated_at)
                if eval_time >= week_ago:
                    count += 1
        return count

    def _get_cumulative_adjustment(self, trap_id: str) -> float:
        """Get total cumulative adjustment for this trap."""
        total = 0.0
        for adj in self.adjustments:
            if adj.trap_id == trap_id:
                total += adj.delta
        return total

    # ===== ADJUSTMENT APPLICATION =====

    def _calculate_adjustment(self, trap: TrapDefinition) -> float:
        """Calculate the adjustment to apply (with decay)."""
        action = trap.action
        base_delta = action.get("delta", 0.01)

        # Apply direction if specified
        direction = action.get("direction", "decrease" if base_delta < 0 else "increase")
        if direction == "decrease" and base_delta > 0:
            base_delta = -base_delta
        elif direction == "increase" and base_delta < 0:
            base_delta = abs(base_delta)

        # Apply decay based on previous triggers
        trigger_count = self._count_triggers_this_week(trap.trap_id)
        decayed_delta = base_delta * (LEARNING_DECAY ** trigger_count)

        # Cap to adjustment_cap
        capped_delta = max(-trap.adjustment_cap, min(trap.adjustment_cap, decayed_delta))

        return capped_delta

    def _apply_adjustment(self, trap: TrapDefinition, game_result: Dict) -> float:
        """Apply weight adjustment based on trap action."""
        action = trap.action
        action_type = action.get("type", "WEIGHT_ADJUST")

        if action_type == "AUDIT_TRIGGER":
            # Log audit request but don't change weights
            logger.info("AUDIT TRIGGERED: %s - %s", trap.name, action.get("audit_type", "manual review"))
            return 0.0

        if action_type == "ALERT_ONLY":
            logger.info("ALERT: %s triggered for %s vs %s",
                       trap.name, game_result.get("home_team"), game_result.get("away_team"))
            return 0.0

        # Calculate adjustment
        delta = self._calculate_adjustment(trap)

        # Get current value
        old_value = self._get_engine_weight(trap.target_engine, trap.target_parameter)

        # Calculate new value (with bounds)
        param_bounds = SUPPORTED_ENGINES.get(trap.target_engine, {}).get(trap.target_parameter, (0, 1))
        new_value = max(param_bounds[0], min(param_bounds[1], old_value + delta))
        actual_delta = new_value - old_value

        # Apply to engine
        self._set_engine_weight(trap.target_engine, trap.target_parameter, new_value)

        # Record adjustment
        cumulative = self._get_cumulative_adjustment(trap.trap_id) + actual_delta
        adjustment = AdjustmentRecord(
            trap_id=trap.trap_id,
            evaluation_id=f"{trap.trap_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            target_engine=trap.target_engine,
            target_parameter=trap.target_parameter,
            old_value=old_value,
            new_value=new_value,
            delta=actual_delta,
            reason=f"Trap fired: {trap.name}",
            cumulative_adjustment=cumulative
        )
        self.adjustments.append(adjustment)
        self._save_adjustments()

        logger.info("TRAP ADJUSTMENT: %s.%s: %.4f -> %.4f (delta=%.4f, cumulative=%.4f)",
                   trap.target_engine, trap.target_parameter,
                   old_value, new_value, actual_delta, cumulative)

        return actual_delta

    def _get_engine_weight(self, engine: str, parameter: str) -> float:
        """Get current weight from engine."""
        # Check cache first
        if engine in self._engine_weights and parameter in self._engine_weights[engine]:
            return self._engine_weights[engine][parameter]

        # Load from engine modules
        try:
            if engine == "jarvis":
                from jarvis_savant_engine import JARVIS_TRIGGERS, DEFAULT_WEIGHTS
                if "trigger_boost" in parameter:
                    trigger_num = int(parameter.split("_")[-1])
                    return JARVIS_TRIGGERS.get(trigger_num, {}).get("boost", 10.0)
                return DEFAULT_WEIGHTS.get(parameter, 0.5)

            elif engine == "esoteric":
                from esoteric_engine import SIGNAL_WEIGHTS
                return SIGNAL_WEIGHTS.get(parameter.replace("weight_", ""), 0.5)

            elif engine == "research":
                # Research weights are hardcoded in live_data_router.py
                defaults = {
                    "weight_public_fade": 1.0,
                    "weight_sharp_money": 1.5,
                    "weight_line_variance": 1.0,
                    "splits_base": 2.0,
                }
                return defaults.get(parameter, 1.0)

            elif engine == "context":
                from context_layer import CONTEXT_WEIGHTS
                return CONTEXT_WEIGHTS.get(parameter.replace("weight_", ""), 0.3)

            elif engine == "ai":
                # AI weights from scoring contract
                defaults = {"lstm_weight": 0.25, "ensemble_weight": 0.25}
                return defaults.get(parameter, 0.25)

        except ImportError as e:
            logger.warning("Could not import %s engine: %s", engine, e)

        return 0.5  # Default

    def _set_engine_weight(self, engine: str, parameter: str, value: float):
        """Set weight in engine."""
        # Cache the new value
        if engine not in self._engine_weights:
            self._engine_weights[engine] = {}
        self._engine_weights[engine][parameter] = value

        # Persist to engine-specific storage
        try:
            if engine == "jarvis":
                from jarvis_savant_engine import esoteric_learning_loop
                if "trigger_boost" in parameter:
                    # Update trigger boost
                    trigger_num = int(parameter.split("_")[-1])
                    esoteric_learning_loop.adjust_trigger_boost(trigger_num, value)
                else:
                    esoteric_learning_loop.adjust_weight(parameter, value - self._get_engine_weight(engine, parameter))

            elif engine == "esoteric":
                from jarvis_savant_engine import esoteric_learning_loop
                esoteric_learning_loop.adjust_weight(parameter.replace("weight_", ""),
                                                     value - self._get_engine_weight(engine, parameter))

            # For research, context, ai - weights are applied at scoring time
            # via the cached values in self._engine_weights

        except Exception as e:
            logger.error("Failed to persist weight to %s engine: %s", engine, e)

    # ===== QUERY METHODS =====

    def get_evaluations(self, trap_id: Optional[str] = None,
                        days_back: int = 30) -> List[TrapEvaluation]:
        """Get evaluation history."""
        cutoff = datetime.now() - timedelta(days=days_back)

        results = []
        for eval_record in self.evaluations:
            if trap_id and eval_record.trap_id != trap_id:
                continue

            eval_time = datetime.fromisoformat(eval_record.evaluated_at)
            if eval_time >= cutoff:
                results.append(eval_record)

        return results

    def get_adjustment_history(self, engine: Optional[str] = None,
                               days_back: int = 30) -> List[Dict]:
        """Get adjustment history for an engine."""
        cutoff = datetime.now() - timedelta(days=days_back)

        results = []
        for adj in self.adjustments:
            if engine and adj.target_engine != engine:
                continue

            adj_time = datetime.fromisoformat(adj.applied_at)
            if adj_time >= cutoff:
                results.append(asdict(adj))

        return results

    def get_recent_parameter_adjustments(
        self,
        engine: str,
        parameter: str,
        hours_back: int = 24
    ) -> List[Dict]:
        """
        Get recent adjustments for a specific engine/parameter.

        Used by AutoGrader reconciliation to avoid conflicting adjustments.

        Args:
            engine: Target engine (research, esoteric, jarvis, context, ai)
            parameter: Specific parameter name
            hours_back: Look back window in hours (default 24)

        Returns:
            List of adjustment records for this engine/parameter
        """
        cutoff = datetime.now() - timedelta(hours=hours_back)

        results = []
        for adj in self.adjustments:
            if adj.target_engine != engine:
                continue
            if adj.target_parameter != parameter:
                continue

            adj_time = datetime.fromisoformat(adj.applied_at)
            if adj_time >= cutoff:
                results.append(asdict(adj))

        return results

    def has_recent_trap_adjustment(
        self,
        engine: str,
        parameter: str,
        hours_back: int = 24
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if there's a recent trap adjustment for this parameter.

        Returns:
            (has_recent, last_adjustment) - bool and the most recent adjustment dict
        """
        recent = self.get_recent_parameter_adjustments(engine, parameter, hours_back)
        if recent:
            # Return most recent
            return True, recent[-1]
        return False, None

    def get_trap_stats(self, trap_id: str) -> Dict[str, Any]:
        """Get statistics for a specific trap."""
        trap = self.traps.get(trap_id)
        if not trap:
            return {"error": "Trap not found"}

        evaluations = self.get_evaluations(trap_id=trap_id)
        adjustments = [a for a in self.adjustments if a.trap_id == trap_id]

        triggered = [e for e in evaluations if e.condition_met]
        applied = [e for e in evaluations if e.action_taken == "APPLIED"]

        return {
            "trap_id": trap_id,
            "name": trap.name,
            "status": trap.status,
            "total_evaluations": len(evaluations),
            "times_triggered": len(triggered),
            "times_applied": len(applied),
            "cumulative_adjustment": self._get_cumulative_adjustment(trap_id),
            "last_triggered": applied[-1].evaluated_at if applied else None,
            "adjustments": [asdict(a) for a in adjustments[-5:]],  # Last 5
        }

    # ===== PERSISTENCE =====

    def _load_state(self):
        """Load state from JSONL files."""
        # Load traps
        if os.path.exists(self.traps_file):
            with open(self.traps_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        trap = TrapDefinition(**data)
                        self.traps[trap.trap_id] = trap

        # Load evaluations (last 30 days only)
        if os.path.exists(self.evaluations_file):
            cutoff = datetime.now() - timedelta(days=30)
            with open(self.evaluations_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        eval_time = datetime.fromisoformat(data.get("evaluated_at", "2020-01-01"))
                        if eval_time >= cutoff:
                            self.evaluations.append(TrapEvaluation(**data))

        # Load adjustments (last 90 days)
        if os.path.exists(self.adjustments_file):
            cutoff = datetime.now() - timedelta(days=90)
            with open(self.adjustments_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        adj_time = datetime.fromisoformat(data.get("applied_at", "2020-01-01"))
                        if adj_time >= cutoff:
                            self.adjustments.append(AdjustmentRecord(**data))

    def _save_traps(self):
        """Save traps to JSONL (overwrite)."""
        with open(self.traps_file, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            for trap in self.traps.values():
                f.write(json.dumps(asdict(trap)) + "\n")
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _save_evaluations(self):
        """Append latest evaluation to JSONL."""
        if not self.evaluations:
            return

        latest = self.evaluations[-1]
        with open(self.evaluations_file, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(json.dumps(asdict(latest)) + "\n")
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _save_adjustments(self):
        """Append latest adjustment to JSONL."""
        if not self.adjustments:
            return

        latest = self.adjustments[-1]
        with open(self.adjustments_file, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(json.dumps(asdict(latest)) + "\n")
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


# ============================================
# SINGLETON ACCESS
# ============================================

_trap_loop_instance: Optional[TrapLearningLoop] = None


def get_trap_loop() -> TrapLearningLoop:
    """Get singleton TrapLearningLoop instance."""
    global _trap_loop_instance
    if _trap_loop_instance is None:
        _trap_loop_instance = TrapLearningLoop()
    return _trap_loop_instance


# ============================================
# HELPER FUNCTIONS
# ============================================

def calculate_numerology_day(date_str: str) -> int:
    """Calculate numerology day (reduce date to single digit 1-9)."""
    # Parse date
    if isinstance(date_str, str):
        parts = date_str.replace("-", "").replace("/", "")
        total = sum(int(d) for d in parts if d.isdigit())
    else:
        total = date_str.day + date_str.month + date_str.year

    # Reduce to single digit
    while total > 9:
        total = sum(int(d) for d in str(total))

    return total


def calculate_team_gematria(team_name: str) -> Dict[str, int]:
    """Calculate gematria values for team name."""
    # Simple ordinal sum (A=1, B=2, etc.)
    def ordinal_sum(text: str) -> int:
        return sum(ord(c.upper()) - ord('A') + 1 for c in text if c.isalpha())

    # Split city and team name (heuristic)
    parts = team_name.split()
    if len(parts) >= 2:
        # Assume last word(s) are team name, rest is city
        city = " ".join(parts[:-1])
        name = parts[-1]
    else:
        city = team_name
        name = team_name

    return {
        "name_sum_cipher": ordinal_sum(name),
        "city_sum_cipher": ordinal_sum(city),
        "combined_cipher": ordinal_sum(team_name),
    }


def enrich_game_result(game: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich game result with calculated fields for trap evaluation."""
    enriched = dict(game)

    # Calculate numerology day
    if "game_date" in game:
        enriched["numerology_day"] = calculate_numerology_day(game["game_date"])

    # Calculate day of week
    if "game_date" in game:
        try:
            date_obj = datetime.fromisoformat(game["game_date"].split("T")[0])
            enriched["day_of_week"] = date_obj.strftime("%A")
            enriched["day_number"] = date_obj.day
            enriched["month"] = date_obj.month
        except:
            pass

    # Calculate team gematria
    for team_field in ["home_team", "away_team"]:
        if team_field in game:
            gematria = calculate_team_gematria(game[team_field])
            prefix = "home_" if team_field == "home_team" else "away_"
            for k, v in gematria.items():
                enriched[prefix + k] = v

    # Calculate margin if not present
    if "margin" not in enriched and "home_score" in game and "away_score" in game:
        home_score = game["home_score"]
        away_score = game["away_score"]

        # For home team perspective
        enriched["home_margin"] = home_score - away_score
        enriched["away_margin"] = away_score - home_score

        # Generic margin (winner's margin)
        if home_score > away_score:
            enriched["margin"] = home_score - away_score
            enriched["winner"] = game.get("home_team")
        elif away_score > home_score:
            enriched["margin"] = away_score - home_score
            enriched["winner"] = game.get("away_team")
        else:
            enriched["margin"] = 0
            enriched["winner"] = None

    # Calculate total points
    if "total_points" not in enriched and "home_score" in game and "away_score" in game:
        enriched["total_points"] = game["home_score"] + game["away_score"]

    return enriched
