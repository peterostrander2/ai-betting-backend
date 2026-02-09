"""
Auto-Grader - The Feedback Loop ("Audit")
==========================================
Dynamically adjusts prediction weights based on yesterday's bias.

This is the learning mechanism that makes Bookie-o-em self-improving:
1. Tracks prediction vs actual outcomes
2. Calculates bias (over-predicting vs under-predicting)
3. Adjusts weights to correct systematic errors
4. Persists learned weights for next session

All 5 Sports: NBA, NFL, MLB, NHL, NCAAB

INTERPRETING BIAS RESULTS:
==========================
* Drift Detection:
  - If `vacuum_bias` is consistently positive (e.g., +4.0), the model is 
    UNDER-reacting to injuries. Safe to INCREASE vacuum weight.
  - If `vacuum_bias` is consistently negative (e.g., -3.0), the model is 
    OVER-reacting to injuries. Safe to DECREASE vacuum weight.
  - Same logic applies to defense_bias, pace_bias, lstm_bias, officials_bias.

* Over-fitting Warning:
  - If Global MAE is high (>5.0) but training error was low, the model 
    might be memorizing the past rather than predicting the future.
  - Solution: Reduce learning_rate, add more regularization, or use more 
    diverse training data.

* Healthy Bias Range:
  - Bias between -1.0 and +1.0 is acceptable (normal variance)
  - Bias between -2.0 and -1.0 or +1.0 and +2.0 warrants monitoring
  - Bias beyond ±2.0 requires immediate weight adjustment

* Target Metrics:
  - MAE < 3.0 for NBA/NCAAB points
  - MAE < 15.0 for NFL passing yards
  - Hit Rate > 52% (profitable threshold with -110 odds)
"""

import json
import os
import logging
import fcntl
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import numpy as np

# v19.1: Import grader_store as SINGLE SOURCE OF TRUTH for predictions
try:
    from grader_store import load_predictions as grader_store_load_predictions
    GRADER_STORE_AVAILABLE = True
except ImportError:
    GRADER_STORE_AVAILABLE = False

# v20.1: Import ET timezone helpers for consistent datetime handling
try:
    from core.time_et import now_et, ET
    TIME_ET_AVAILABLE = True
except ImportError:
    TIME_ET_AVAILABLE = False
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)

# ============================================
# DATA STRUCTURES
# ============================================

@dataclass
class PredictionRecord:
    """Single prediction record for grading."""
    prediction_id: str
    sport: str
    player_name: str
    stat_type: str
    predicted_value: float
    actual_value: Optional[float] = None
    line: Optional[float] = None
    timestamp: str = ""

    # Pick type for differentiated learning (PROP, SPREAD, TOTAL, MONEYLINE, SHARP)
    pick_type: str = ""

    # Context features used (Pillars 13-15)
    defense_adjustment: float = 0.0
    pace_adjustment: float = 0.0
    vacuum_adjustment: float = 0.0
    lstm_adjustment: float = 0.0
    officials_adjustment: float = 0.0

    # Research engine signals (GAP 1 fix: sharp money, public fade, line variance)
    sharp_money_adjustment: float = 0.0
    public_fade_adjustment: float = 0.0
    line_variance_adjustment: float = 0.0

    # GLITCH Protocol signals (GAP 2 fix: esoteric signal tracking)
    # Keys: chrome_resonance, void_moon, noosphere, hurst, kp_index, benford
    glitch_signals: Optional[Dict[str, float]] = None

    # Esoteric engine contributions (GAP 2 fix: track all esoteric signals)
    # Keys: numerology, astro, fib_alignment, fib_retracement, vortex, daily_edge,
    #       biorhythms, gann_square, founders_echo, lunar, mercury, rivalry, streak, solar
    esoteric_contributions: Optional[Dict[str, float]] = None

    # Outcome tracking
    hit: Optional[bool] = None  # Did prediction beat the line correctly?
    error: Optional[float] = None  # predicted - actual

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        # Initialize dicts to empty if None (for dataclass field default)
        if self.glitch_signals is None:
            self.glitch_signals = {}
        if self.esoteric_contributions is None:
            self.esoteric_contributions = {}


@dataclass
class WeightConfig:
    """Dynamic weight configuration per sport/stat type."""
    defense: float = 0.15
    pace: float = 0.12
    vacuum: float = 0.18
    lstm: float = 0.20
    officials: float = 0.08
    park_factor: float = 0.10  # MLB only
    
    # Learning rate for weight adjustments
    learning_rate: float = 0.05
    
    # Bounds to prevent extreme weights
    min_weight: float = 0.05
    max_weight: float = 0.35


# ============================================
# AUTO-GRADER ENGINE
# ============================================

class AutoGrader:
    """
    The Feedback Loop - Grades predictions and adjusts weights.
    
    Flow:
    1. Log predictions as they're made
    2. Grade predictions when actuals come in
    3. Calculate bias per factor
    4. Adjust weights to correct bias
    5. Persist for next session
    """

    SUPPORTED_SPORTS = ["NBA", "NFL", "MLB", "NHL", "NCAAB"]  # Kept in sync with data_dir.SUPPORTED_SPORTS

    def __init__(self, storage_path: str = None):
        if storage_path is None:
            from data_dir import GRADER_DATA
            storage_path = GRADER_DATA
        self.storage_path = storage_path
        self.predictions: Dict[str, List[PredictionRecord]] = defaultdict(list)
        self.weights: Dict[str, Dict[str, WeightConfig]] = {}
        self.bias_history: Dict[str, List[Dict]] = defaultdict(list)
        
        # Initialize weights for all sports
        self._initialize_weights()
        
        # Load persisted data
        self._load_state()
    
    def _initialize_weights(self):
        """Initialize default weights for all sports and stat types."""
        # v20.2: PROP stat types (player-level predictions)
        prop_stat_types = {
            "NBA": ["points", "rebounds", "assists", "threes", "steals", "blocks", "pra"],
            "NFL": ["passing_yards", "rushing_yards", "receiving_yards", "receptions", "touchdowns"],
            "MLB": ["hits", "runs", "rbis", "strikeouts", "total_bases", "walks"],
            "NHL": ["goals", "assists", "points", "shots", "saves", "blocks"],
            "NCAAB": ["points", "rebounds", "assists", "threes"]
        }

        # v20.2: GAME stat types (game-level predictions: spread, total, moneyline, sharp)
        # These are stored with these stat_type values when picks are persisted
        game_stat_types = ["spread", "total", "moneyline", "sharp"]

        for sport in self.SUPPORTED_SPORTS:
            self.weights[sport] = {}

            # Initialize PROP stat types
            for stat in prop_stat_types.get(sport, ["points"]):
                self.weights[sport][stat] = WeightConfig()

                # Sport-specific default adjustments for props
                if sport == "MLB":
                    self.weights[sport][stat].park_factor = 0.15
                    self.weights[sport][stat].pace = 0.08  # Less relevant for MLB
                elif sport == "NFL":
                    self.weights[sport][stat].vacuum = 0.22  # Injuries huge in NFL
                elif sport == "NHL":
                    self.weights[sport][stat].pace = 0.18  # Pace matters in hockey

            # v20.2: Initialize GAME stat types (spread, total, moneyline, sharp)
            for stat in game_stat_types:
                self.weights[sport][stat] = WeightConfig()

                # Sport-specific default adjustments for game picks
                if sport == "MLB":
                    self.weights[sport][stat].park_factor = 0.15
                    self.weights[sport][stat].pace = 0.08
                elif sport == "NFL":
                    self.weights[sport][stat].vacuum = 0.22
                elif sport == "NHL":
                    self.weights[sport][stat].pace = 0.18
    
    def _load_state(self):
        """Load persisted weights and prediction history from grader_store."""
        # Load weights (still from weights.json - learned weights persist here)
        weights_file = os.path.join(self.storage_path, "weights.json")
        if os.path.exists(weights_file):
            try:
                with open(weights_file, 'r') as f:
                    data = json.load(f)
                    for sport, stat_weights in data.items():
                        if sport in self.weights:
                            for stat, w in stat_weights.items():
                                if stat in self.weights[sport]:
                                    self.weights[sport][stat] = WeightConfig(**w)
                logger.info("Loaded weights from %s", weights_file)
            except Exception as e:
                logger.warning("Could not load weights: %s", e)

        # v19.1: Load predictions from grader_store (SINGLE SOURCE OF TRUTH)
        self._load_predictions_from_grader_store()

    def _load_predictions_from_grader_store(self):
        """
        Load predictions from grader_store and convert to PredictionRecord format.

        v19.1: grader_store is the SINGLE SOURCE OF TRUTH for picks.
        This replaces the legacy predictions.json loading.
        """
        if not GRADER_STORE_AVAILABLE:
            logger.warning("grader_store not available, predictions will be empty")
            return

        try:
            try:
                from core.scoring_contract import MIN_FINAL_SCORE
            except Exception:
                MIN_FINAL_SCORE = 6.5

            # Load all predictions from grader_store
            raw_predictions = grader_store_load_predictions()
            count = 0
            seen_ids = set()
            drop_stats = {
                "unsupported_sport": 0,
                "below_score_threshold": 0,
                "duplicate_id": 0,
                "missing_pick_id": 0,
                "conversion_failed": 0,
            }

            for pick in raw_predictions:
                sport = pick.get("sport", "").upper()
                if sport not in self.SUPPORTED_SPORTS:
                    drop_stats["unsupported_sport"] += 1
                    continue
                score = pick.get("final_score", 0.0)
                if isinstance(score, (int, float)) and score < MIN_FINAL_SCORE:
                    drop_stats["below_score_threshold"] += 1
                    continue
                pick_id = pick.get("pick_id", "")
                if not pick_id:
                    drop_stats["missing_pick_id"] += 1
                    continue
                if pick_id in seen_ids:
                    drop_stats["duplicate_id"] += 1
                    continue
                seen_ids.add(pick_id)

                # Convert grader_store pick to PredictionRecord
                record = self._convert_pick_to_record(pick)
                if record:
                    self.predictions[sport].append(record)
                    count += 1
                else:
                    drop_stats["conversion_failed"] += 1

            self.last_drop_stats = drop_stats
            total_dropped = sum(drop_stats.values())
            logger.info("Loaded %d predictions from grader_store (dropped %d: %s)",
                        count, total_dropped,
                        {k: v for k, v in drop_stats.items() if v > 0})
        except Exception as e:
            logger.exception("Failed to load from grader_store: %s", e)

    def _convert_pick_to_record(self, pick: Dict) -> Optional[PredictionRecord]:
        """
        Convert a grader_store pick dict to PredictionRecord.

        Maps grader_store fields to PredictionRecord fields for learning.
        """
        try:
            # Determine player_name/stat_type based on pick type
            pick_type = pick.get("pick_type", pick.get("market", "")).upper()

            if pick_type in ("PROP", "PLAYER_PROP"):
                player_name = pick.get("player_name", pick.get("description", "Unknown"))
                raw_stat = pick.get("stat_type", pick.get("prop_type", "unknown"))
                stat_type = raw_stat.replace("player_", "") if raw_stat else "unknown"
            else:
                # For game picks (spread, total, moneyline), use matchup
                player_name = pick.get("matchup", f"{pick.get('away_team', '')} @ {pick.get('home_team', '')}")
                stat_type = pick_type.lower() if pick_type else "game"

            # Extract predicted value (final_score is our prediction confidence)
            predicted_value = pick.get("final_score", 0.0)

            # Extract actual result if graded
            actual_value = None
            hit = None
            error = None

            grade_status = pick.get("grade_status", "PENDING")
            if grade_status == "GRADED":
                result = pick.get("result", "").upper()
                hit = result == "WIN"
                actual_value = pick.get("actual_value", 0.0)
                # Error = prediction confidence - outcome (1 for win, 0 for loss)
                error = predicted_value - (10.0 if hit else 0.0)

            # Extract signal contributions
            context_layer = pick.get("context_layer", {})
            esoteric_contrib = pick.get("esoteric_contributions", {})
            glitch_sigs = pick.get("glitch_signals", {})

            # Handle nested glitch_signals (may have sub-dicts like void_moon: {is_void: true})
            flat_glitch = {}
            for key, val in glitch_sigs.items():
                if isinstance(val, dict):
                    # Extract a numeric value from the dict
                    flat_glitch[key] = val.get("score", val.get("boost", val.get("confidence", 0.0)))
                else:
                    flat_glitch[key] = float(val) if val else 0.0

            # Get timestamp from pick
            timestamp = pick.get("persisted_at", pick.get("created_at", datetime.now().isoformat()))

            return PredictionRecord(
                prediction_id=pick.get("pick_id", pick.get("id", "")),
                sport=pick.get("sport", "").upper(),
                player_name=player_name,
                stat_type=stat_type,
                predicted_value=predicted_value,
                actual_value=actual_value,
                line=pick.get("line", None),
                timestamp=timestamp,
                pick_type=pick_type,
                # Context layer signals
                defense_adjustment=context_layer.get("def_rank_adjustment", context_layer.get("defense", 0.0)),
                pace_adjustment=context_layer.get("pace_adjustment", context_layer.get("pace", 0.0)),
                vacuum_adjustment=context_layer.get("vacuum_adjustment", context_layer.get("vacuum", 0.0)),
                lstm_adjustment=context_layer.get("lstm_adjustment", 0.0),
                officials_adjustment=context_layer.get("officials_adjustment", 0.0),
                # Research signals (pick payload uses sharp_boost/public_boost/line_boost)
                sharp_money_adjustment=pick.get("research_breakdown", {}).get("sharp_boost", pick.get("research_breakdown", {}).get("sharp_money", 0.0)),
                public_fade_adjustment=pick.get("research_breakdown", {}).get("public_boost", pick.get("research_breakdown", {}).get("public_fade", 0.0)),
                line_variance_adjustment=pick.get("research_breakdown", {}).get("line_boost", pick.get("research_breakdown", {}).get("line_variance", 0.0)),
                # GLITCH signals
                glitch_signals=flat_glitch,
                # Esoteric contributions
                esoteric_contributions=esoteric_contrib,
                # Outcome
                hit=hit,
                error=error
            )
        except Exception as e:
            logger.warning("Failed to convert pick %s: %s", pick.get("pick_id", "unknown"), e)
            return None
    
    def _save_state(self):
        """
        Persist weights to disk.

        v19.1: Predictions are now saved via grader_store (single source of truth).
        This method ONLY saves learned weights.
        """
        os.makedirs(self.storage_path, exist_ok=True)

        # Save weights
        weights_file = os.path.join(self.storage_path, "weights.json")
        weights_data = {}
        for sport, stat_weights in self.weights.items():
            weights_data[sport] = {}
            for stat, config in stat_weights.items():
                weights_data[sport][stat] = asdict(config)

        lock_file = weights_file + ".lock"
        tmp_file = weights_file + ".tmp"
        with open(lock_file, 'w') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                with open(tmp_file, 'w') as f:
                    json.dump(weights_data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_file, weights_file)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        logger.info("Saved weights to %s", weights_file)
    
    # ============================================
    # PREDICTION LOGGING
    # ============================================
    
    def log_prediction(
        self,
        sport: str,
        player_name: str,
        stat_type: str,
        predicted_value: float,
        line: Optional[float] = None,
        adjustments: Optional[Dict] = None,
        pick_type: str = "",
        glitch_signals: Optional[Dict[str, float]] = None,
        esoteric_contributions: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Log a prediction to in-memory store for bias calculations.

        v19.1 NOTE: This method updates the in-memory predictions dict ONLY.
        Actual pick persistence is handled by grader_store.persist_pick() in
        live_data_router.py. This method is used for:
        - Test scenarios
        - Manual prediction logging during development
        - Populating in-memory dict for bias calculation (loaded from grader_store on startup)

        Args:
            sport: Sport code (NBA, NFL, etc.)
            player_name: Player name for props, team for games
            stat_type: Stat being predicted (points, spread, total, etc.)
            predicted_value: Model's predicted value
            line: Betting line
            adjustments: Dict of adjustment values from scoring pipeline
            pick_type: PROP, SPREAD, TOTAL, MONEYLINE, SHARP
            glitch_signals: GLITCH protocol signal contributions
            esoteric_contributions: Esoteric engine signal breakdown

        Returns prediction_id for tracking.
        """
        sport = sport.upper()
        prediction_id = f"{sport}_{player_name}_{stat_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Extract adjustment values
        adj = adjustments or {}

        record = PredictionRecord(
            prediction_id=prediction_id,
            sport=sport,
            player_name=player_name,
            stat_type=stat_type,
            predicted_value=predicted_value,
            line=line,
            pick_type=pick_type,
            # Context features (Pillars 13-15)
            defense_adjustment=adj.get("defense", 0.0),
            pace_adjustment=adj.get("pace", 0.0),
            vacuum_adjustment=adj.get("vacuum", 0.0),
            lstm_adjustment=adj.get("lstm_brain", 0.0),
            officials_adjustment=adj.get("officials", 0.0),
            # Research engine signals (GAP 1)
            sharp_money_adjustment=adj.get("sharp_money", 0.0),
            public_fade_adjustment=adj.get("public_fade", 0.0),
            line_variance_adjustment=adj.get("line_variance", 0.0),
            # GLITCH Protocol signals (GAP 2)
            glitch_signals=glitch_signals or {},
            # Esoteric contributions (GAP 2)
            esoteric_contributions=esoteric_contributions or {}
        )
        
        self.predictions[sport].append(record)

        # v19.1: Predictions are persisted via grader_store from live_data_router.py
        # This method only updates the in-memory dict for bias calculations
        # Do NOT call _save_predictions() - grader_store is single source of truth

        return prediction_id
    
    def grade_prediction(
        self,
        prediction_id: str,
        actual_value: float
    ) -> Optional[Dict]:
        """
        Grade a prediction with actual outcome.

        Returns grading result with error analysis.
        Error metric aligned with _convert_pick_to_record():
        error = predicted_value - (10.0 if hit else 0.0)
        """
        # Find the prediction
        for sport, records in self.predictions.items():
            for record in records:
                if record.prediction_id == prediction_id:
                    record.actual_value = actual_value

                    # Determine if it "hit" (beat the line correctly)
                    if record.line is not None:
                        predicted_over = record.predicted_value > record.line
                        actual_over = actual_value > record.line
                        record.hit = predicted_over == actual_over
                    else:
                        # For picks without a line, compare predicted vs actual directly
                        record.hit = record.predicted_value > actual_value if actual_value > 0 else False

                    # Error metric aligned with _convert_pick_to_record() (line 332)
                    # This measures how far off the confidence score was from the ideal:
                    # - If hit: ideal was 10.0 (max confidence justified)
                    # - If miss: ideal was 0.0 (should have had no confidence)
                    record.error = record.predicted_value - (10.0 if record.hit else 0.0)

                    # v19.1: Grading updates go to grader_store via mark_graded()
                    # Update in-memory only here - grader_store handles persistence

                    return {
                        "prediction_id": prediction_id,
                        "predicted": record.predicted_value,
                        "actual": actual_value,
                        "error": record.error,
                        "hit": record.hit,
                        "bias_direction": "OVER" if record.error > 0 else "UNDER"
                    }

        return None
    
    def bulk_grade(
        self,
        sport: str,
        results: List[Dict]
    ) -> Dict:
        """
        Grade multiple predictions at once.
        
        Args:
            sport: Sport to grade
            results: List of {"player_name": str, "stat_type": str, "actual": float}
        """
        graded = []
        not_found = []
        
        sport = sport.upper()
        today = datetime.now().strftime('%Y%m%d')
        
        for result in results:
            found = False
            for record in self.predictions.get(sport, []):
                if (record.player_name == result["player_name"] and
                    record.stat_type == result["stat_type"] and
                    today in record.prediction_id):
                    
                    grade = self.grade_prediction(record.prediction_id, result["actual"])
                    if grade:
                        graded.append(grade)
                        found = True
                        break
            
            if not found:
                not_found.append(result)
        
        return {
            "graded_count": len(graded),
            "not_found_count": len(not_found),
            "graded": graded,
            "not_found": not_found
        }
    
    # ============================================
    # BIAS CALCULATION
    # ============================================
    
    def calculate_bias(
        self,
        sport: str,
        stat_type: str = "all",
        days_back: int = 1,
        pick_type: str = "all",
        apply_confidence_decay: bool = True
    ) -> Dict:
        """
        Calculate prediction bias for a sport/stat combination.

        v19.1: Expanded to include all signals for complete learning:
        - Research signals: sharp_money, public_fade, line_variance
        - GLITCH signals: chrome_resonance, void_moon, noosphere, hurst, kp_index, benford
        - Esoteric signals: all 14 esoteric contributions
        - Confidence decay: older picks weighted less (70% decay per day)
        - Pick type separation: PROP vs GAME picks analyzed separately

        Returns bias metrics per adjustment factor.
        """
        sport = sport.upper()
        # v20.1: Use ET timezone for consistent datetime handling
        if TIME_ET_AVAILABLE:
            now = now_et()
        else:
            now = datetime.now(timezone.utc).astimezone(ET)
        cutoff = now - timedelta(days=days_back)

        # Filter relevant predictions
        relevant = []
        weights = []  # Confidence decay weights
        for record in self.predictions.get(sport, []):
            if record.actual_value is None:
                continue

            # v20.1: Parse timestamp, handling both aware and naive formats
            record_date = datetime.fromisoformat(record.timestamp)
            if record_date.tzinfo is None:
                # If timestamp is naive, assume UTC then convert to ET
                record_date = record_date.replace(tzinfo=timezone.utc).astimezone(ET)
            else:
                # Convert to ET for consistent comparison
                record_date = record_date.astimezone(ET)
            if record_date < cutoff:
                continue

            if stat_type != "all" and record.stat_type != stat_type:
                continue

            # GAP 3 fix: Filter by pick_type for differentiated learning
            if pick_type != "all" and record.pick_type and record.pick_type.upper() != pick_type.upper():
                continue

            relevant.append(record)

            # GAP 5 fix: Confidence decay - older picks weighted less
            if apply_confidence_decay:
                days_old = (now - record_date).days
                weight = 0.7 ** days_old  # 70% decay per day (1.0 today, 0.7 yesterday, 0.49 2 days ago)
                weights.append(weight)
            else:
                weights.append(1.0)

        if not relevant:
            return {"error": "No graded predictions found", "sample_size": 0}

        # Calculate overall bias (with optional weighting)
        errors = [r.error for r in relevant]
        if apply_confidence_decay and sum(weights) > 0:
            weighted_errors = [e * w for e, w in zip(errors, weights)]
            mean_error = sum(weighted_errors) / sum(weights)
        else:
            mean_error = np.mean(errors)

        std_error = np.std(errors)
        hit_rate = sum(1 for r in relevant if r.hit) / len(relevant) if relevant else 0

        # Calculate bias contribution per factor
        factor_bias = {}

        # ===== CONTEXT LAYER SIGNALS (Pillars 13-15) =====
        # Defense bias: correlation between defense_adjustment and error
        defense_adj = [r.defense_adjustment for r in relevant]
        if any(a != 0 for a in defense_adj):
            factor_bias["defense"] = self._calculate_factor_bias(defense_adj, errors, weights)

        # Pace bias
        pace_adj = [r.pace_adjustment for r in relevant]
        if any(a != 0 for a in pace_adj):
            factor_bias["pace"] = self._calculate_factor_bias(pace_adj, errors, weights)

        # Vacuum bias
        vacuum_adj = [r.vacuum_adjustment for r in relevant]
        if any(a != 0 for a in vacuum_adj):
            factor_bias["vacuum"] = self._calculate_factor_bias(vacuum_adj, errors, weights)

        # LSTM bias
        lstm_adj = [r.lstm_adjustment for r in relevant]
        if any(a != 0 for a in lstm_adj):
            factor_bias["lstm"] = self._calculate_factor_bias(lstm_adj, errors, weights)

        # Officials bias
        officials_adj = [r.officials_adjustment for r in relevant]
        if any(a != 0 for a in officials_adj):
            factor_bias["officials"] = self._calculate_factor_bias(officials_adj, errors, weights)

        # ===== GAP 1 FIX: RESEARCH ENGINE SIGNALS =====
        # Sharp money bias
        sharp_adj = [r.sharp_money_adjustment for r in relevant]
        if any(a != 0 for a in sharp_adj):
            factor_bias["sharp_money"] = self._calculate_factor_bias(sharp_adj, errors, weights)

        # Public fade bias
        fade_adj = [r.public_fade_adjustment for r in relevant]
        if any(a != 0 for a in fade_adj):
            factor_bias["public_fade"] = self._calculate_factor_bias(fade_adj, errors, weights)

        # Line variance bias
        variance_adj = [r.line_variance_adjustment for r in relevant]
        if any(a != 0 for a in variance_adj):
            factor_bias["line_variance"] = self._calculate_factor_bias(variance_adj, errors, weights)

        # ===== GAP 2 FIX: GLITCH PROTOCOL SIGNALS =====
        glitch_bias = {}
        glitch_signal_names = ["chrome_resonance", "void_moon", "noosphere", "hurst", "kp_index", "benford"]
        for signal_name in glitch_signal_names:
            signal_adj = [r.glitch_signals.get(signal_name, 0.0) for r in relevant]
            if any(a != 0 for a in signal_adj):
                glitch_bias[signal_name] = self._calculate_factor_bias(signal_adj, errors, weights)
        if glitch_bias:
            factor_bias["glitch"] = glitch_bias

        # ===== GAP 2 FIX: ESOTERIC ENGINE SIGNALS =====
        esoteric_bias = {}
        esoteric_signal_names = [
            "numerology", "astro", "fib_alignment", "fib_retracement", "vortex", "daily_edge",
            "biorhythms", "gann_square", "founders_echo", "lunar", "mercury", "rivalry", "streak", "solar"
        ]
        for signal_name in esoteric_signal_names:
            signal_adj = [r.esoteric_contributions.get(signal_name, 0.0) for r in relevant]
            if any(a != 0 for a in signal_adj):
                esoteric_bias[signal_name] = self._calculate_factor_bias(signal_adj, errors, weights)
        if esoteric_bias:
            factor_bias["esoteric"] = esoteric_bias

        # ===== GAP 3 FIX: PICK TYPE BREAKDOWN =====
        pick_type_stats = {}
        for pt in ["PROP", "SPREAD", "TOTAL", "MONEYLINE", "SHARP"]:
            pt_records = [r for r in relevant if r.pick_type and r.pick_type.upper() == pt]
            if pt_records:
                pt_hits = sum(1 for r in pt_records if r.hit)
                pt_errors = [r.error for r in pt_records]
                pick_type_stats[pt] = {
                    "count": len(pt_records),
                    "hit_rate": round((pt_hits / len(pt_records)) * 100, 1),
                    "mean_error": round(np.mean(pt_errors), 3),
                    "std_error": round(np.std(pt_errors), 3)
                }
        
        return {
            "sport": sport,
            "stat_type": stat_type,
            "pick_type_filter": pick_type,
            "sample_size": len(relevant),
            "days_analyzed": days_back,
            "confidence_decay_applied": apply_confidence_decay,
            "overall": {
                "mean_error": round(mean_error, 3),
                "std_error": round(std_error, 3),
                "hit_rate": round(hit_rate * 100, 1),
                "bias_direction": "OVER" if mean_error > 0 else "UNDER"
            },
            "factor_bias": factor_bias,
            "pick_type_breakdown": pick_type_stats if pick_type_stats else None
        }

    def _calculate_factor_bias(
        self,
        adjustments: List[float],
        errors: List[float],
        weights: Optional[List[float]] = None
    ) -> Dict:
        """
        Calculate how much a factor contributes to prediction error.

        v19.1: Added optional weights for confidence decay support.

        Args:
            adjustments: List of adjustment values for this factor
            errors: List of prediction errors
            weights: Optional confidence weights (1.0 = today, 0.7 = yesterday, etc.)

        Returns:
            Dict with correlation, mean_when_over, mean_when_under, suggested_adjustment
        """
        if not adjustments or not errors:
            return {"contribution": 0, "correlation": 0}

        # Use uniform weights if not provided
        if weights is None:
            weights = [1.0] * len(adjustments)

        # Weighted correlation between adjustment and error
        if np.std(adjustments) > 0 and np.std(errors) > 0:
            # Weighted covariance / (weighted std_adj * weighted std_err)
            total_weight = sum(weights)
            if total_weight > 0:
                weighted_mean_adj = sum(a * w for a, w in zip(adjustments, weights)) / total_weight
                weighted_mean_err = sum(e * w for e, w in zip(errors, weights)) / total_weight

                weighted_cov = sum(w * (a - weighted_mean_adj) * (e - weighted_mean_err)
                                   for a, e, w in zip(adjustments, errors, weights)) / total_weight
                weighted_var_adj = sum(w * (a - weighted_mean_adj) ** 2
                                       for a, w in zip(adjustments, weights)) / total_weight
                weighted_var_err = sum(w * (e - weighted_mean_err) ** 2
                                       for e, w in zip(errors, weights)) / total_weight

                if weighted_var_adj > 0 and weighted_var_err > 0:
                    correlation = weighted_cov / (np.sqrt(weighted_var_adj) * np.sqrt(weighted_var_err))
                else:
                    correlation = 0
            else:
                correlation = np.corrcoef(adjustments, errors)[0, 1]
        else:
            correlation = 0

        # Mean adjustment when error was positive vs negative (weighted)
        pos_pairs = [(a, w) for a, e, w in zip(adjustments, errors, weights) if e > 0]
        neg_pairs = [(a, w) for a, e, w in zip(adjustments, errors, weights) if e < 0]

        if pos_pairs:
            total_pos_weight = sum(w for _, w in pos_pairs)
            mean_pos = sum(a * w for a, w in pos_pairs) / total_pos_weight if total_pos_weight > 0 else 0
        else:
            mean_pos = 0

        if neg_pairs:
            total_neg_weight = sum(w for _, w in neg_pairs)
            mean_neg = sum(a * w for a, w in neg_pairs) / total_neg_weight if total_neg_weight > 0 else 0
        else:
            mean_neg = 0

        return {
            "correlation": round(correlation, 3) if not np.isnan(correlation) else 0,
            "mean_when_over": round(mean_pos, 3),
            "mean_when_under": round(mean_neg, 3),
            "suggested_adjustment": round(-correlation * 0.1, 4) if not np.isnan(correlation) else 0  # Damped correction
        }
    
    # ============================================
    # WEIGHT ADJUSTMENT
    # ============================================
    
    def adjust_weights(
        self,
        sport: str,
        stat_type: str = "points",
        days_back: int = 1,
        apply_changes: bool = True
    ) -> Dict:
        """
        Adjust weights based on calculated bias.
        
        This is the core learning mechanism.
        """
        sport = sport.upper()
        
        # Get current weights
        if stat_type not in self.weights.get(sport, {}):
            stat_type = "points"  # Default

        # Ensure sport and stat_type exist in weights
        if sport not in self.weights or stat_type not in self.weights[sport]:
            return {"error": f"No weights found for {sport}/{stat_type}", "weights_unchanged": True}

        current = self.weights[sport][stat_type]
        
        # Calculate bias
        bias = self.calculate_bias(sport, stat_type, days_back)
        
        if "error" in bias:
            return {"error": bias["error"], "weights_unchanged": True}
        
        # Calculate new weights
        adjustments = {}
        new_weights = {}
        
        for factor in ["defense", "pace", "vacuum", "lstm", "officials"]:
            old_weight = getattr(current, factor)
            
            if factor in bias.get("factor_bias", {}):
                suggested = bias["factor_bias"][factor].get("suggested_adjustment", 0)
                # Apply learning rate
                delta = suggested * current.learning_rate
                new_weight = np.clip(
                    old_weight + delta,
                    current.min_weight,
                    current.max_weight
                )
            else:
                new_weight = old_weight
                delta = 0
            
            adjustments[factor] = {
                "old": round(old_weight, 4),
                "delta": round(delta, 4),
                "new": round(new_weight, 4)
            }
            new_weights[factor] = new_weight
        
        # Apply changes if requested
        if apply_changes:
            for factor, value in new_weights.items():
                setattr(current, factor, value)
            
            # Save to disk
            self._save_state()
            
            # Log to bias history
            self.bias_history[f"{sport}_{stat_type}"].append({
                "timestamp": datetime.now().isoformat(),
                "bias": bias,
                "adjustments": adjustments
            })
        
        return {
            "sport": sport,
            "stat_type": stat_type,
            "bias_analysis": bias,
            "weight_adjustments": adjustments,
            "applied": apply_changes,
            "reconciliation": None
        }

    # ============================================
    # GAP 4 FIX: TRAP-AUTOGRADER RECONCILIATION
    # ============================================

    def check_trap_reconciliation(
        self,
        engine: str,
        parameter: str,
        hours_back: int = 24
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if Trap Learning Loop recently adjusted this parameter.

        v19.1: Prevents AutoGrader from conflicting with trap adjustments.

        Args:
            engine: Engine name (context, ai, etc. - maps to trap engines)
            parameter: Parameter being adjusted
            hours_back: Look back window

        Returns:
            (should_skip, trap_info) - True if AutoGrader should skip this adjustment
        """
        try:
            from trap_learning_loop import get_trap_loop
            trap_loop = get_trap_loop()

            # Map AutoGrader factor names to trap engine/parameter names
            factor_to_trap = {
                "defense": ("context", "weight_def_rank"),
                "pace": ("context", "weight_pace"),
                "vacuum": ("context", "weight_vacuum"),
                "lstm": ("ai", "lstm_weight"),
                "officials": ("research", "weight_officials"),  # If added to traps
            }

            # Check if this factor maps to a trap-adjustable parameter
            trap_mapping = factor_to_trap.get(parameter)
            if trap_mapping:
                trap_engine, trap_param = trap_mapping
                has_recent, last_adj = trap_loop.has_recent_trap_adjustment(
                    trap_engine, trap_param, hours_back
                )
                if has_recent:
                    logger.info(
                        "RECONCILIATION: Skipping AutoGrader adjustment for %s/%s - "
                        "trap %s adjusted it %s ago",
                        engine, parameter, last_adj.get("trap_id"), last_adj.get("applied_at")
                    )
                    return True, last_adj

            return False, None

        except ImportError:
            # Trap learning loop not available
            return False, None
        except Exception as e:
            logger.warning("Trap reconciliation check failed: %s", e)
            return False, None

    def adjust_weights_with_reconciliation(
        self,
        sport: str,
        stat_type: str = "points",
        days_back: int = 1,
        apply_changes: bool = True,
        reconcile_with_traps: bool = True
    ) -> Dict:
        """
        Adjust weights based on calculated bias WITH trap reconciliation.

        v19.1: Checks for recent trap adjustments before applying changes
        to prevent AutoGrader from overriding hypothesis-driven learning.

        Args:
            sport: Sport code
            stat_type: Stat type to analyze
            days_back: Days of data to analyze
            apply_changes: Whether to apply changes
            reconcile_with_traps: Whether to skip factors recently adjusted by traps
        """
        sport = sport.upper()

        # Get current weights
        if stat_type not in self.weights.get(sport, {}):
            stat_type = "points"

        if sport not in self.weights or stat_type not in self.weights[sport]:
            return {"error": f"No weights found for {sport}/{stat_type}", "weights_unchanged": True}

        current = self.weights[sport][stat_type]

        # Calculate bias
        bias = self.calculate_bias(sport, stat_type, days_back)

        if "error" in bias:
            return {"error": bias["error"], "weights_unchanged": True}

        # Calculate new weights with reconciliation
        adjustments = {}
        new_weights = {}
        reconciliation_results = {}

        for factor in ["defense", "pace", "vacuum", "lstm", "officials"]:
            old_weight = getattr(current, factor)

            # GAP 4 FIX: Check trap reconciliation
            if reconcile_with_traps:
                should_skip, trap_info = self.check_trap_reconciliation("context", factor)
                if should_skip:
                    reconciliation_results[factor] = {
                        "skipped": True,
                        "reason": "recent_trap_adjustment",
                        "trap_info": trap_info
                    }
                    adjustments[factor] = {
                        "old": round(old_weight, 4),
                        "delta": 0,
                        "new": round(old_weight, 4),
                        "skipped_reason": "trap_reconciliation"
                    }
                    new_weights[factor] = old_weight
                    continue

            # Normal adjustment logic
            if factor in bias.get("factor_bias", {}):
                suggested = bias["factor_bias"][factor].get("suggested_adjustment", 0)
                delta = suggested * current.learning_rate
                new_weight = np.clip(
                    old_weight + delta,
                    current.min_weight,
                    current.max_weight
                )
            else:
                new_weight = old_weight
                delta = 0

            adjustments[factor] = {
                "old": round(old_weight, 4),
                "delta": round(delta, 4),
                "new": round(new_weight, 4)
            }
            new_weights[factor] = new_weight

        # Apply changes if requested
        if apply_changes:
            for factor, value in new_weights.items():
                setattr(current, factor, value)

            self._save_state()

            self.bias_history[f"{sport}_{stat_type}"].append({
                "timestamp": datetime.now().isoformat(),
                "bias": bias,
                "adjustments": adjustments,
                "reconciliation": reconciliation_results
            })

        return {
            "sport": sport,
            "stat_type": stat_type,
            "bias_analysis": bias,
            "weight_adjustments": adjustments,
            "reconciliation": reconciliation_results,
            "applied": apply_changes
        }

    def run_daily_audit(self, days_back: int = 1) -> Dict:
        """
        Run full audit across all sports and stat types.

        Call this daily after games complete.
        """
        # v20.1: Reload predictions from grader_store to get freshly graded picks
        # This is critical because picks are graded by result_fetcher AFTER auto_grader startup
        logger.info("Reloading predictions from grader_store before audit...")
        self.predictions.clear()
        self._load_predictions_from_grader_store()

        results = {}

        # v20.3: Separate stat types for PROP picks vs GAME picks
        # PROP stat types - MUST MATCH _initialize_weights() to audit all prop types
        prop_stat_types = {
            "NBA": ["points", "rebounds", "assists", "threes", "steals", "blocks", "pra"],
            "NFL": ["passing_yards", "rushing_yards", "receiving_yards", "receptions", "touchdowns"],
            "MLB": ["hits", "runs", "rbis", "strikeouts", "total_bases", "walks"],
            "NHL": ["goals", "assists", "points", "shots", "saves", "blocks"],
            "NCAAB": ["points", "rebounds", "assists", "threes"]
        }

        # GAME stat types (game-level predictions - spread, total, moneyline)
        game_stat_types = ["spread", "total", "moneyline", "sharp"]

        for sport in self.SUPPORTED_SPORTS:
            results[sport] = {}
            # Audit PROP picks
            for stat in prop_stat_types.get(sport, ["points"]):
                result = self.adjust_weights(sport, stat, days_back, apply_changes=True)
                results[sport][stat] = result

            # v20.1: Also audit GAME picks (spread, total, moneyline)
            for stat in game_stat_types:
                result = self.adjust_weights(sport, stat, days_back, apply_changes=True)
                results[sport][stat] = result
        
        return {
            "audit_date": datetime.now().isoformat(),
            "days_analyzed": days_back,
            "results": results
        }
    
    # ============================================
    # WEIGHT RETRIEVAL (FOR PREDICTION ENGINE)
    # ============================================
    
    def get_weights(self, sport: str, stat_type: str = "points") -> Dict[str, float]:
        """
        Get current weights for use in predictions.
        
        This is what the prediction engine calls.
        """
        sport = sport.upper()
        
        if sport not in self.weights:
            sport = "NBA"  # Default
        
        if stat_type not in self.weights[sport]:
            stat_type = list(self.weights[sport].keys())[0]
        
        config = self.weights[sport][stat_type]
        
        return {
            "defense": config.defense,
            "pace": config.pace,
            "vacuum": config.vacuum,
            "lstm": config.lstm,
            "officials": config.officials,
            "park_factor": config.park_factor if sport == "MLB" else 0.0
        }
    
    def get_all_weights(self) -> Dict:
        """Get all weights for all sports (for API endpoint)."""
        result = {}
        for sport, stat_weights in self.weights.items():
            result[sport] = {}
            for stat, config in stat_weights.items():
                result[sport][stat] = {
                    "defense": config.defense,
                    "pace": config.pace,
                    "vacuum": config.vacuum,
                    "lstm": config.lstm,
                    "officials": config.officials,
                    "park_factor": config.park_factor
                }
        return result

    # ============================================
    # SPEC COMPLIANCE METHOD ALIASES (v12.0)
    # ============================================

    def apply_updates(self, learning_rate: float = 0.05) -> Dict:
        """
        Alias for adjust_weights with custom learning rate.

        Per EsotericLearningLoop spec compliance.
        """
        results = {}
        for sport in self.SUPPORTED_SPORTS:
            results[sport] = self.adjust_weights(sport, days_back=1, apply_changes=True)
        return results

    def snapshot(self) -> Dict:
        """
        Save current state and return snapshot data.

        Per EsotericLearningLoop spec compliance.
        """
        self._save_state()
        return {
            "weights": self.get_all_weights(),
            "timestamp": datetime.now().isoformat(),
            "predictions_count": sum(len(p) for p in self.predictions.values())
        }

    def load_snapshot(self, path: str = None) -> bool:
        """
        Load state from snapshot.

        Per EsotericLearningLoop spec compliance.
        """
        if path:
            self.storage_path = path
        self._load_state()
        return True

    # ============================================
    # JSONL DAILY STORAGE (v12.0)
    # ============================================

    def save_daily_grading_jsonl(self, date_str: str = None) -> str:
        """
        Save graded picks to JSONL file for daily tracking.

        Args:
            date_str: Date string (YYYY-MM-DD), defaults to today in ET

        Returns:
            Path to JSONL file
        """
        import json
        from core.time_et import now_et
        from zoneinfo import ZoneInfo

        et_tz = ZoneInfo("America/New_York")

        if date_str is None:
            date_str = now_et().strftime("%Y-%m-%d")

        # Ensure graded_picks directory exists
        graded_dir = os.path.join(self.storage_path, "graded_picks")
        os.makedirs(graded_dir, exist_ok=True)

        path = os.path.join(graded_dir, f"graded_{date_str}.jsonl")

        # Get all graded predictions from this date using ET-aware cutoffs
        cutoff = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=et_tz)
        cutoff_end = cutoff + timedelta(days=1)

        graded_count = 0
        # Use write mode ('w') instead of append ('a') to prevent duplicates
        with open(path, 'w') as f:
            for sport, records in self.predictions.items():
                for record in records:
                    # Only include graded predictions from this date
                    if record.actual_value is None:
                        continue

                    try:
                        record_date = datetime.fromisoformat(record.timestamp)
                        # Handle both naive and aware timestamps
                        if record_date.tzinfo is None:
                            record_date = record_date.replace(tzinfo=et_tz)
                        if cutoff <= record_date < cutoff_end:
                            f.write(json.dumps(asdict(record)) + "\n")
                            graded_count += 1
                    except (ValueError, TypeError):
                        continue

        logger.info(f"Saved {graded_count} graded picks to {path}")
        return path

    def load_daily_grading_jsonl(self, date_str: str) -> List[Dict]:
        """
        Load graded picks from JSONL file.

        Args:
            date_str: Date string (YYYY-MM-DD)

        Returns:
            List of graded prediction records
        """
        import json

        path = os.path.join(self.storage_path, "graded_picks", f"graded_{date_str}.jsonl")

        if not os.path.exists(path):
            return []

        records = []
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return records

    def get_performance_history(self, days_back: int = 7) -> Dict:
        """
        Get performance history from JSONL files.

        Returns:
            Performance metrics by date
        """
        history = {}

        for i in range(days_back):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")

            records = self.load_daily_grading_jsonl(date_str)

            if records:
                hits = sum(1 for r in records if r.get("hit"))
                total = len(records)
                errors = [abs(r.get("error", 0)) for r in records if r.get("error") is not None]

                history[date_str] = {
                    "total_picks": total,
                    "hits": hits,
                    "hit_rate": round((hits / total * 100) if total > 0 else 0, 1),
                    "mae": round(sum(errors) / len(errors) if errors else 0, 2)
                }
            else:
                history[date_str] = {"total_picks": 0, "hits": 0, "hit_rate": 0, "mae": 0}

        return history

    def get_audit_summary(self, sport: str, days_back: int = 1) -> Dict:
        """
        Get audit summary for a sport.

        Returns summary stats about predictions and performance.
        Called by DailyScheduler after grading.
        """
        sport = sport.upper()
        # v20.1: Use ET timezone for consistent datetime handling
        if TIME_ET_AVAILABLE:
            now = now_et()
        else:
            now = datetime.now(timezone.utc).astimezone(ET)
        cutoff = now - timedelta(days=days_back)

        predictions = self.predictions.get(sport, [])

        # Filter to recent predictions
        recent = []
        for p in predictions:
            # v20.1: Parse timestamp, handling both aware and naive formats
            record_date = datetime.fromisoformat(p.timestamp)
            if record_date.tzinfo is None:
                # If timestamp is naive, assume UTC then convert to ET
                record_date = record_date.replace(tzinfo=timezone.utc).astimezone(ET)
            else:
                # Convert to ET for consistent comparison
                record_date = record_date.astimezone(ET)
            if record_date >= cutoff:
                recent.append(p)

        # Count graded predictions
        graded = [p for p in recent if p.actual_value is not None]
        ungraded = [p for p in recent if p.actual_value is None]

        # Calculate hit rate
        hits = sum(1 for p in graded if p.hit)
        hit_rate = (hits / len(graded)) if graded else 0

        # Calculate MAE
        errors = [abs(p.error) for p in graded if p.error is not None]
        mae = sum(errors) / len(errors) if errors else 0

        return {
            "sport": sport,
            "days_analyzed": days_back,
            "total_predictions": len(recent),
            "total_graded": len(graded),
            "total_ungraded": len(ungraded),
            "hits": hits,
            "misses": len(graded) - hits,
            "hit_rate": round(hit_rate * 100, 1),
            "mae": round(mae, 2),
            "profitable": hit_rate > 0.52,
            "timestamp": datetime.now().isoformat()
        }


# ============================================
# CONTEXT FEATURE CALCULATOR (Nano Banana Upgrade)
# ============================================

class ContextFeatureCalculator:
    """
    Calculates context features for MasterPredictionEngine.
    
    This bridges the Context Layer with the prediction models.
    """
    
    LEAGUE_AVG_PACE = {
        "NBA": 99.5,
        "NFL": 64.0,
        "MLB": 100.0,  # Not really applicable
        "NHL": 32.0,
        "NCAAB": 68.0
    }
    
    @staticmethod
    def calculate_context_features(
        sport: str,
        team_id: str,
        injuries: List[Dict],
        game_stats: Dict
    ) -> Dict:
        """
        NANO BANANA UPGRADE: Calculates the "Eyes" of the system.
        
        Args:
            sport: Sport code
            team_id: Team identifier
            injuries: List of injury dicts with player info
            game_stats: Dict with pace, totals, etc.
            
        Returns:
            Dict with vacuum, pace_vector, is_smash_spot
        """
        sport = sport.upper()
        
        # 1. CALCULATE USAGE VACUUM
        # Logic: Sum of (Usage% * Mins) for all OUT players
        total_usage_void = 0.0
        
        for player in injuries:
            if player.get('status', '').upper() == 'OUT':
                # Get player stats
                stats = player.get('stats', {})
                
                # Sport-specific usage calculation
                if sport == "NBA":
                    p_usage = stats.get('usage_pct', 0.20)
                    p_mins = stats.get('avg_minutes', 25)
                    total_usage_void += (p_usage * (p_mins / 48.0)) * 100
                    
                elif sport == "NFL":
                    # Target share for pass catchers, snap % for others
                    target_share = stats.get('target_share', 0.15)
                    snap_pct = stats.get('snap_pct', 0.60)
                    total_usage_void += (target_share * snap_pct) * 100
                    
                elif sport == "MLB":
                    # Plate appearances and batting order position
                    pa_share = stats.get('pa_share', 0.11)  # ~1/9
                    lineup_pos = stats.get('lineup_position', 5)
                    weight = 1.0 + (0.1 * (5 - lineup_pos))  # Top of order = more weight
                    total_usage_void += (pa_share * weight) * 100
                    
                elif sport == "NHL":
                    toi_pct = stats.get('toi_pct', 0.25)
                    total_usage_void += toi_pct * 100
                    
                elif sport == "NCAAB":
                    p_usage = stats.get('usage_pct', 0.18)
                    p_mins = stats.get('avg_minutes', 28)
                    total_usage_void += (p_usage * (p_mins / 40.0)) * 100
        
        # 2. CALCULATE PACE VECTOR
        # Logic: (Team_Pace + Opp_Pace) / 2 - League_Avg
        league_avg_pace = ContextFeatureCalculator.LEAGUE_AVG_PACE.get(sport, 99.5)
        
        team_pace = game_stats.get('home_pace', league_avg_pace)
        opp_pace = game_stats.get('away_pace', league_avg_pace)
        
        pace_vector = ((team_pace + opp_pace) / 2) - league_avg_pace
        
        # 3. DETERMINE SMASH SPOT
        # High vacuum + positive pace = smash spot
        vacuum_threshold = {
            "NBA": 20.0,
            "NFL": 15.0,
            "MLB": 10.0,
            "NHL": 15.0,
            "NCAAB": 18.0
        }.get(sport, 20.0)
        
        pace_threshold = {
            "NBA": 2.0,
            "NFL": 3.0,
            "MLB": 5.0,  # Less relevant
            "NHL": 1.5,
            "NCAAB": 2.5
        }.get(sport, 2.0)
        
        is_smash_spot = (total_usage_void > vacuum_threshold and pace_vector > pace_threshold)
        
        return {
            "vacuum": round(total_usage_void, 2),
            "pace_vector": round(pace_vector, 2),
            "is_smash_spot": is_smash_spot,
            "sport": sport,
            "thresholds": {
                "vacuum": vacuum_threshold,
                "pace": pace_threshold
            }
        }


# ============================================
# SINGLETON INSTANCE
# ============================================

# Global grader instance for API use
_grader_instance: Optional[AutoGrader] = None

def get_grader() -> AutoGrader:
    """Get or create the singleton AutoGrader instance."""
    global _grader_instance
    if _grader_instance is None:
        _grader_instance = AutoGrader()
    return _grader_instance


# ============================================
# LEARNING LOOP CONVENIENCE CLASS (v14.11)
# ============================================

class LearningLoop:
    """
    Convenience wrapper for learning loop functionality.

    Provides a simple interface that the master prompt references:
        from auto_grader import learning
        weights = learning.get_weights()

    v14.11: Ensures learning loop never 500s endpoints by catching errors.
    """

    def get_weights(self, sport: str = "NBA", stat_type: str = "points") -> Dict[str, Any]:
        """
        Get current learned weights.

        Returns:
            Dict with weights and metadata, or defaults on error
        """
        try:
            grader = get_grader()
            weights = grader.get_weights(sport.upper(), stat_type)
            return {
                "sport": sport.upper(),
                "stat_type": stat_type,
                "weights": weights,
                "source": "learned"
            }
        except Exception as e:
            logger.warning("Learning loop error in get_weights: %s", e)
            # Return defaults - never 500
            return {
                "sport": sport.upper(),
                "stat_type": stat_type,
                "weights": {
                    "defense": 0.15,
                    "pace": 0.12,
                    "vacuum": 0.18,
                    "lstm": 0.10,
                    "officials": 0.05,
                    "park_factor": 0.10
                },
                "source": "default",
                "error": str(e)
            }

    def get_all_weights(self) -> Dict[str, Any]:
        """Get all weights for all sports."""
        try:
            grader = get_grader()
            return grader.get_all_weights()
        except Exception as e:
            logger.warning("Learning loop error in get_all_weights: %s", e)
            return {"error": str(e), "source": "default"}

    def get_daily_summary(self, sport: str = None, days_back: int = 1) -> Dict[str, Any]:
        """
        Get daily summary of what changed, why, and rollback info.

        Returns:
            Dict with changes, reasons, and rollback ability
        """
        try:
            grader = get_grader()

            if sport:
                bias = grader.calculate_bias(sport.upper(), "points", days_back)
                history = grader.bias_history.get(f"{sport.upper()}_points", [])
            else:
                # Aggregate across sports
                bias = {}
                history = []
                for s in grader.SUPPORTED_SPORTS:
                    s_bias = grader.calculate_bias(s, "points", days_back)
                    if "error" not in s_bias:
                        bias[s] = s_bias
                    s_history = grader.bias_history.get(f"{s}_points", [])
                    history.extend(s_history[-3:])  # Last 3 per sport

            # Build summary
            return {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "days_analyzed": days_back,
                "sport": sport.upper() if sport else "ALL",
                "bias_analysis": bias,
                "recent_changes": history[-10:] if history else [],
                "rollback_available": len(history) > 0,
                "can_rollback_to": history[-2]["timestamp"] if len(history) > 1 else None
            }
        except Exception as e:
            logger.warning("Learning loop error in get_daily_summary: %s", e)
            return {"error": str(e), "rollback_available": False}

    def rollback_weights(self, sport: str, to_timestamp: str) -> Dict[str, Any]:
        """
        Rollback weights to a previous state.

        Args:
            sport: Sport to rollback
            to_timestamp: ISO timestamp to rollback to

        Returns:
            Dict with success status
        """
        try:
            grader = get_grader()
            sport = sport.upper()

            # Find the historical state
            history = grader.bias_history.get(f"{sport}_points", [])
            target_state = None
            for entry in history:
                if entry["timestamp"] == to_timestamp:
                    target_state = entry
                    break

            if not target_state:
                return {"error": f"State not found for {to_timestamp}"}

            # Restore weights from that state
            adjustments = target_state.get("adjustments", {})
            current = grader.weights.get(sport, {}).get("points")
            if not current:
                return {"error": f"No weights found for {sport}"}

            for factor, adj in adjustments.items():
                old_weight = adj.get("old", getattr(current, factor, 0.15))
                setattr(current, factor, old_weight)

            grader._save_state()

            return {
                "success": True,
                "sport": sport,
                "rolled_back_to": to_timestamp,
                "weights_restored": adjustments
            }
        except Exception as e:
            logger.warning("Learning loop error in rollback_weights: %s", e)
            return {"error": str(e), "success": False}


# Module-level learning instance
learning = LearningLoop()


# ============================================
# TESTING
# ============================================

if __name__ == "__main__":
    # Configure logging for test mode
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    logger.info("=" * 60)
    logger.info("AUTO-GRADER TEST")
    logger.info("=" * 60)

    grader = AutoGrader(storage_path="./test_grader_data")

    # Test weight retrieval
    logger.info("\nDefault Weights:")
    for sport in ["NBA", "NFL", "MLB"]:
        weights = grader.get_weights(sport, "points" if sport != "MLB" else "hits")
        logger.info(f"  {sport}: {weights}")

    # Test prediction logging
    logger.info("\nLogging test predictions...")
    pred_id = grader.log_prediction(
        sport="NBA",
        player_name="LeBron James",
        stat_type="points",
        predicted_value=27.5,
        line=26.5,
        adjustments={
            "defense": 1.2,
            "pace": 0.8,
            "vacuum": 2.1,
            "lstm_brain": -1.5
        }
    )
    logger.info(f"  Logged: {pred_id}")

    # Test grading
    logger.info("\nGrading prediction...")
    grade = grader.grade_prediction(pred_id, actual_value=29.0)
    logger.info(f"  Result: {grade}")

    # Test context feature calculation
    logger.info("\nContext Feature Calculation:")
    context = ContextFeatureCalculator.calculate_context_features(
        sport="NBA",
        team_id="LAL",
        injuries=[
            {"status": "OUT", "stats": {"usage_pct": 0.28, "avg_minutes": 35}},
            {"status": "OUT", "stats": {"usage_pct": 0.18, "avg_minutes": 28}}
        ],
        game_stats={"home_pace": 102.5, "away_pace": 98.5}
    )
    logger.info(f"  {context}")

    logger.info("\n" + "=" * 60)
    logger.info("Auto-Grader tests complete!")
    logger.info("=" * 60)
