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
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import numpy as np

# v10.38: Timezone support for ET date calculations
try:
    from zoneinfo import ZoneInfo
    ET_TIMEZONE = ZoneInfo("America/New_York")
except ImportError:
    ET_TIMEZONE = None

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
    
    # Context features used
    defense_adjustment: float = 0.0
    pace_adjustment: float = 0.0
    vacuum_adjustment: float = 0.0
    lstm_adjustment: float = 0.0
    officials_adjustment: float = 0.0
    
    # Outcome tracking
    hit: Optional[bool] = None  # Did prediction beat the line correctly?
    error: Optional[float] = None  # predicted - actual
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


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
    
    SUPPORTED_SPORTS = ["NBA", "NFL", "MLB", "NHL", "NCAAB"]
    
    def __init__(self, storage_path: str = "./grader_data"):
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
        stat_types = {
            "NBA": ["points", "rebounds", "assists", "threes", "steals", "blocks", "pra"],
            "NFL": ["passing_yards", "rushing_yards", "receiving_yards", "receptions", "touchdowns"],
            "MLB": ["hits", "runs", "rbis", "strikeouts", "total_bases", "walks"],
            "NHL": ["goals", "assists", "points", "shots", "saves", "blocks"],
            "NCAAB": ["points", "rebounds", "assists", "threes"]
        }

        for sport in self.SUPPORTED_SPORTS:
            self.weights[sport] = {}
            for stat in stat_types.get(sport, ["points"]):
                self.weights[sport][stat] = WeightConfig()

                # Sport-specific default adjustments
                if sport == "MLB":
                    self.weights[sport][stat].park_factor = 0.15
                    self.weights[sport][stat].pace = 0.08  # Less relevant for MLB
                elif sport == "NFL":
                    self.weights[sport][stat].vacuum = 0.22  # Injuries huge in NFL
                elif sport == "NHL":
                    self.weights[sport][stat].pace = 0.18  # Pace matters in hockey

    def reset_weights_to_factory(self, sport: str = None) -> Dict:
        """
        v10.96: Reset weights to factory defaults.
        Use when grading was incorrect and weight adjustments need to be reverted.

        Args:
            sport: Specific sport to reset, or None for all sports

        Returns:
            Dict with reset status
        """
        import shutil
        from datetime import datetime

        # Backup current weights before reset
        weights_file = os.path.join(self.storage_path, "weights.json")
        if os.path.exists(weights_file):
            backup_file = os.path.join(
                self.storage_path,
                f"weights_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            try:
                shutil.copy2(weights_file, backup_file)
                print(f"✅ Backed up weights to {backup_file}")
            except Exception as e:
                print(f"⚠️ Could not backup weights: {e}")

        if sport:
            # Reset specific sport only
            sport = sport.upper()
            if sport in self.weights:
                stat_types = {
                    "NBA": ["points", "rebounds", "assists", "threes", "steals", "blocks", "pra"],
                    "NFL": ["passing_yards", "rushing_yards", "receiving_yards", "receptions", "touchdowns"],
                    "MLB": ["hits", "runs", "rbis", "strikeouts", "total_bases", "walks"],
                    "NHL": ["goals", "assists", "points", "shots", "saves", "blocks"],
                    "NCAAB": ["points", "rebounds", "assists", "threes"]
                }
                for stat in stat_types.get(sport, ["points"]):
                    self.weights[sport][stat] = WeightConfig()
                    # Sport-specific defaults
                    if sport == "MLB":
                        self.weights[sport][stat].park_factor = 0.15
                        self.weights[sport][stat].pace = 0.08
                    elif sport == "NFL":
                        self.weights[sport][stat].vacuum = 0.22
                    elif sport == "NHL":
                        self.weights[sport][stat].pace = 0.18
                print(f"✅ Reset {sport} weights to factory defaults")
        else:
            # Reset all sports
            self._initialize_weights()
            print("✅ Reset ALL weights to factory defaults")

        # Save the reset weights
        self._save_state()

        return {
            "reset": True,
            "sport": sport or "ALL",
            "message": f"Weights reset to factory defaults for {sport or 'ALL sports'}"
        }
    
    def _load_state(self):
        """Load persisted weights and prediction history."""
        # Load weights
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
                print(f"✅ Loaded weights from {weights_file}")
            except Exception as e:
                print(f"⚠️ Could not load weights: {e}")
        
        # Load predictions history
        predictions_file = os.path.join(self.storage_path, "predictions.json")
        if os.path.exists(predictions_file):
            try:
                with open(predictions_file, 'r') as f:
                    data = json.load(f)
                    for sport, records in data.items():
                        for record_dict in records:
                            self.predictions[sport].append(PredictionRecord(**record_dict))
                print(f"✅ Loaded {sum(len(p) for p in self.predictions.values())} predictions from {predictions_file}")
            except Exception as e:
                print(f"⚠️ Could not load predictions: {e}")
    
    def _save_state(self):
        """Persist weights and predictions to disk."""
        os.makedirs(self.storage_path, exist_ok=True)
        
        # Save weights
        weights_file = os.path.join(self.storage_path, "weights.json")
        weights_data = {}
        for sport, stat_weights in self.weights.items():
            weights_data[sport] = {}
            for stat, config in stat_weights.items():
                weights_data[sport][stat] = asdict(config)
        
        with open(weights_file, 'w') as f:
            json.dump(weights_data, f, indent=2)
        print(f"✅ Saved weights to {weights_file}")
        
        # Save predictions
        predictions_file = os.path.join(self.storage_path, "predictions.json")
        predictions_data = {}
        for sport, records in self.predictions.items():
            predictions_data[sport] = [asdict(r) for r in records]
        
        with open(predictions_file, 'w') as f:
            json.dump(predictions_data, f, indent=2)
        print(f"✅ Saved {sum(len(p) for p in self.predictions.values())} predictions to {predictions_file}")
    
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
        adjustments: Optional[Dict] = None
    ) -> str:
        """
        Log a prediction for later grading.
        
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
            defense_adjustment=adj.get("defense", 0.0),
            pace_adjustment=adj.get("pace", 0.0),
            vacuum_adjustment=adj.get("vacuum", 0.0),
            lstm_adjustment=adj.get("lstm_brain", 0.0),
            officials_adjustment=adj.get("officials", 0.0)
        )
        
        self.predictions[sport].append(record)
        
        # Auto-save predictions to disk (persist for tomorrow's audit)
        self._save_predictions()
        
        return prediction_id
    
    def _save_predictions(self):
        """Save predictions only (lightweight save for each log)."""
        os.makedirs(self.storage_path, exist_ok=True)
        predictions_file = os.path.join(self.storage_path, "predictions.json")
        predictions_data = {}
        for sport, records in self.predictions.items():
            predictions_data[sport] = [asdict(r) for r in records]
        
        with open(predictions_file, 'w') as f:
            json.dump(predictions_data, f, indent=2)
    
    def grade_prediction(
        self,
        prediction_id: str,
        actual_value: float
    ) -> Optional[Dict]:
        """
        Grade a prediction with actual outcome.
        
        Returns grading result with error analysis.
        """
        # Find the prediction
        for sport, records in self.predictions.items():
            for record in records:
                if record.prediction_id == prediction_id:
                    record.actual_value = actual_value
                    record.error = record.predicted_value - actual_value
                    
                    # Determine if it "hit" (beat the line correctly)
                    if record.line is not None:
                        predicted_over = record.predicted_value > record.line
                        actual_over = actual_value > record.line
                        record.hit = predicted_over == actual_over
                    
                    # Save graded prediction to disk
                    self._save_predictions()
                    
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
        days_back: int = 1
    ) -> Dict:
        """
        Calculate prediction bias for a sport/stat combination.
        
        Returns bias metrics per adjustment factor.
        """
        sport = sport.upper()
        cutoff = datetime.now() - timedelta(days=days_back)
        
        # Filter relevant predictions
        relevant = []
        for record in self.predictions.get(sport, []):
            if record.actual_value is None:
                continue
            
            record_date = datetime.fromisoformat(record.timestamp)
            if record_date < cutoff:
                continue
            
            if stat_type != "all" and record.stat_type != stat_type:
                continue
            
            relevant.append(record)
        
        if not relevant:
            return {"error": "No graded predictions found", "sample_size": 0}
        
        # Calculate overall bias
        errors = [r.error for r in relevant]
        mean_error = np.mean(errors)
        std_error = np.std(errors)
        hit_rate = sum(1 for r in relevant if r.hit) / len(relevant) if relevant else 0
        
        # Calculate bias contribution per factor
        factor_bias = {}
        
        # Defense bias: correlation between defense_adjustment and error
        defense_adj = [r.defense_adjustment for r in relevant]
        if any(a != 0 for a in defense_adj):
            factor_bias["defense"] = self._calculate_factor_bias(defense_adj, errors)
        
        # Pace bias
        pace_adj = [r.pace_adjustment for r in relevant]
        if any(a != 0 for a in pace_adj):
            factor_bias["pace"] = self._calculate_factor_bias(pace_adj, errors)
        
        # Vacuum bias
        vacuum_adj = [r.vacuum_adjustment for r in relevant]
        if any(a != 0 for a in vacuum_adj):
            factor_bias["vacuum"] = self._calculate_factor_bias(vacuum_adj, errors)
        
        # LSTM bias
        lstm_adj = [r.lstm_adjustment for r in relevant]
        if any(a != 0 for a in lstm_adj):
            factor_bias["lstm"] = self._calculate_factor_bias(lstm_adj, errors)
        
        # Officials bias
        officials_adj = [r.officials_adjustment for r in relevant]
        if any(a != 0 for a in officials_adj):
            factor_bias["officials"] = self._calculate_factor_bias(officials_adj, errors)
        
        return {
            "sport": sport,
            "stat_type": stat_type,
            "sample_size": len(relevant),
            "days_analyzed": days_back,
            "overall": {
                "mean_error": round(mean_error, 3),
                "std_error": round(std_error, 3),
                "hit_rate": round(hit_rate * 100, 1),
                "bias_direction": "OVER" if mean_error > 0 else "UNDER"
            },
            "factor_bias": factor_bias
        }
    
    def _calculate_factor_bias(
        self,
        adjustments: List[float],
        errors: List[float]
    ) -> Dict:
        """Calculate how much a factor contributes to prediction error."""
        if not adjustments or not errors:
            return {"contribution": 0, "correlation": 0}
        
        # Correlation between adjustment and error
        if np.std(adjustments) > 0 and np.std(errors) > 0:
            correlation = np.corrcoef(adjustments, errors)[0, 1]
        else:
            correlation = 0
        
        # Mean adjustment when error was positive vs negative
        pos_error_adj = [a for a, e in zip(adjustments, errors) if e > 0]
        neg_error_adj = [a for a, e in zip(adjustments, errors) if e < 0]
        
        mean_pos = np.mean(pos_error_adj) if pos_error_adj else 0
        mean_neg = np.mean(neg_error_adj) if neg_error_adj else 0
        
        return {
            "correlation": round(correlation, 3),
            "mean_when_over": round(mean_pos, 3),
            "mean_when_under": round(mean_neg, 3),
            "suggested_adjustment": round(-correlation * 0.1, 4)  # Damped correction
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
            "applied": apply_changes
        }
    
    def run_daily_audit(self, days_back: int = 1) -> Dict:
        """
        Run full audit across all sports and stat types.
        
        Call this daily after games complete.
        """
        results = {}
        
        stat_types = {
            "NBA": ["points", "rebounds", "assists"],
            "NFL": ["passing_yards", "rushing_yards", "receiving_yards"],
            "MLB": ["hits", "strikeouts", "total_bases"],
            "NHL": ["goals", "assists", "shots"],
            "NCAAB": ["points", "rebounds"]
        }
        
        for sport in self.SUPPORTED_SPORTS:
            results[sport] = {}
            for stat in stat_types.get(sport, ["points"]):
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

    def get_audit_summary(self, sport: str, days_back: int = 1) -> Dict:
        """
        Get audit summary for a sport.

        Returns summary stats about predictions and performance.
        Called by DailyScheduler after grading.
        """
        sport = sport.upper()
        cutoff = datetime.now() - timedelta(days=days_back)

        predictions = self.predictions.get(sport, [])

        # Filter to recent predictions
        recent = [
            p for p in predictions
            if datetime.fromisoformat(p.timestamp) >= cutoff
        ]

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
    # v10.38: JSONL PREDICTION LOGGING (Idempotent)
    # ============================================

    def _get_et_date(self) -> str:
        """Get current date in ET timezone as YYYY-MM-DD."""
        if ET_TIMEZONE:
            return datetime.now(ET_TIMEZONE).strftime("%Y-%m-%d")
        else:
            # Fallback: assume UTC-5
            return (datetime.utcnow() - timedelta(hours=5)).strftime("%Y-%m-%d")

    def _generate_prediction_id(self, sport: str, date_et: str, event_id: str,
                                 market: str, selection: str, line: float, odds: int) -> str:
        """Generate stable SHA256 hash for deduplication."""
        raw = f"{sport}|{date_et}|{event_id}|{market}|{selection}|{line}|{odds}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _get_prediction_log_path(self, sport: str, date_et: str) -> str:
        """Get path to JSONL prediction log file."""
        dir_path = os.path.join(self.storage_path, sport.upper(), "predictions")
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, f"{date_et}.jsonl")

    def _get_graded_log_path(self, sport: str, date_et: str) -> str:
        """Get path to JSONL graded log file."""
        dir_path = os.path.join(self.storage_path, sport.upper(), "graded")
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, f"{date_et}.jsonl")

    def _load_today_prediction_ids(self, sport: str, date_et: str) -> set:
        """Load existing prediction IDs for today to check duplicates."""
        log_path = self._get_prediction_log_path(sport, date_et)
        existing_ids = set()
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r') as f:
                    for line in f:
                        if line.strip():
                            record = json.loads(line)
                            existing_ids.add(record.get("prediction_id", ""))
            except Exception as e:
                print(f"⚠️ Error loading prediction log: {e}")
        return existing_ids

    def log_pick_jsonl(self, pick: Dict, sport: str, pick_type: str = "prop") -> Optional[str]:
        """
        Log a pick to JSONL file with deduplication.

        Args:
            pick: The pick dict from best-bets
            sport: Sport code (NBA, NFL, etc.)
            pick_type: "prop" or "game"

        Returns:
            prediction_id if logged, None if duplicate
        """
        sport = sport.upper()
        date_et = self._get_et_date()

        # Extract fields from pick
        event_id = pick.get("event_id") or pick.get("game", "")
        market = pick.get("stat_type") or pick.get("market", "")
        selection = pick.get("player_name") or pick.get("selection") or pick.get("pick", "")
        line = pick.get("line") or 0
        odds = pick.get("odds") or -110

        # Generate stable prediction ID
        prediction_id = self._generate_prediction_id(
            sport, date_et, event_id, market, selection, line, odds
        )

        # Check for duplicate
        existing_ids = self._load_today_prediction_ids(sport, date_et)
        if prediction_id in existing_ids:
            return None  # Already logged

        # Build prediction record
        record = {
            "prediction_id": prediction_id,
            "sport": sport,
            "date_et": date_et,
            "event_id": event_id,
            "pick_type": pick_type,
            "market": market,
            "stat_type": pick.get("stat_type", ""),
            "selection": selection,
            "player_name": pick.get("player_name", ""),
            "line": line,
            "odds": odds,
            "over_under": pick.get("over_under", ""),
            "tier": pick.get("tier", ""),
            "model_score": pick.get("smash_score") or pick.get("final_score") or 0,
            "confidence_grade": pick.get("confidence_grade", ""),
            "game": pick.get("game", ""),
            "game_time": pick.get("game_time", ""),
            "generated_at": datetime.now().isoformat(),
            # Grading fields (populated later)
            "graded": False,
            "result": None,  # WIN/LOSS/PUSH/VOID
            "actual_value": None,
            "graded_at": None
        }

        # Append to JSONL file
        log_path = self._get_prediction_log_path(sport, date_et)
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps(record) + "\n")
            return prediction_id
        except Exception as e:
            print(f"⚠️ Error writing prediction log: {e}")
            return None

    def log_picks_batch(self, picks: List[Dict], sport: str, pick_type: str = "prop") -> Dict:
        """
        Log multiple picks with deduplication.

        Returns:
            {"logged": N, "duplicates": N, "errors": N}
        """
        logged = 0
        duplicates = 0
        errors = 0

        for pick in picks:
            try:
                result = self.log_pick_jsonl(pick, sport, pick_type)
                if result:
                    logged += 1
                else:
                    duplicates += 1
            except Exception as e:
                print(f"⚠️ Error logging pick: {e}")
                errors += 1

        return {"logged": logged, "duplicates": duplicates, "errors": errors}

    def get_predictions_logged_count(self, sport: str = None, date_et: str = None) -> int:
        """Get total count of logged predictions."""
        if date_et is None:
            date_et = self._get_et_date()

        total = 0
        sports = [sport.upper()] if sport else self.SUPPORTED_SPORTS

        for s in sports:
            log_path = self._get_prediction_log_path(s, date_et)
            if os.path.exists(log_path):
                try:
                    with open(log_path, 'r') as f:
                        total += sum(1 for line in f if line.strip())
                except Exception:
                    pass

        return total

    def get_ungraded_predictions(self, sport: str, date_et: str = None) -> List[Dict]:
        """Load ungraded predictions for a sport/date."""
        if date_et is None:
            # Default to yesterday for grading
            if ET_TIMEZONE:
                yesterday = datetime.now(ET_TIMEZONE) - timedelta(days=1)
                date_et = yesterday.strftime("%Y-%m-%d")
            else:
                date_et = (datetime.utcnow() - timedelta(hours=5) - timedelta(days=1)).strftime("%Y-%m-%d")

        log_path = self._get_prediction_log_path(sport.upper(), date_et)
        ungraded = []

        if os.path.exists(log_path):
            try:
                with open(log_path, 'r') as f:
                    for line in f:
                        if line.strip():
                            record = json.loads(line)
                            if not record.get("graded", False):
                                ungraded.append(record)
            except Exception as e:
                print(f"⚠️ Error loading predictions: {e}")

        return ungraded

    def grade_predictions_batch(self, sport: str, results: List[Dict], date_et: str = None) -> Dict:
        """
        Grade predictions with actual results.

        Args:
            sport: Sport code
            results: List of {"event_id": str, "player_name": str, "stat_type": str, "actual": float}
            date_et: Date to grade (default: yesterday)

        Returns:
            {"graded": N, "wins": N, "losses": N, "pushes": N}
        """
        sport = sport.upper()
        if date_et is None:
            if ET_TIMEZONE:
                yesterday = datetime.now(ET_TIMEZONE) - timedelta(days=1)
                date_et = yesterday.strftime("%Y-%m-%d")
            else:
                date_et = (datetime.utcnow() - timedelta(hours=5) - timedelta(days=1)).strftime("%Y-%m-%d")

        log_path = self._get_prediction_log_path(sport, date_et)
        graded_path = self._get_graded_log_path(sport, date_et)

        if not os.path.exists(log_path):
            return {"graded": 0, "wins": 0, "losses": 0, "pushes": 0, "error": "No predictions found"}

        # Build results lookup
        results_lookup = {}
        for r in results:
            key = f"{r.get('event_id', '')}|{r.get('player_name', '')}|{r.get('stat_type', '')}"
            results_lookup[key] = r.get("actual")

        # Load and grade predictions
        graded_records = []
        wins = 0
        losses = 0
        pushes = 0

        try:
            with open(log_path, 'r') as f:
                lines = f.readlines()

            updated_lines = []
            for line in lines:
                if not line.strip():
                    continue
                record = json.loads(line)

                # Build lookup key
                key = f"{record.get('event_id', '')}|{record.get('player_name', '')}|{record.get('stat_type', '')}"

                if key in results_lookup and not record.get("graded"):
                    actual = results_lookup[key]
                    line_val = record.get("line", 0)
                    over_under = record.get("over_under", "over").lower()

                    # Determine result
                    if actual == line_val:
                        result = "PUSH"
                        pushes += 1
                    elif over_under == "over":
                        result = "WIN" if actual > line_val else "LOSS"
                    else:  # under
                        result = "WIN" if actual < line_val else "LOSS"

                    if result == "WIN":
                        wins += 1
                    elif result == "LOSS":
                        losses += 1

                    # Update record
                    record["graded"] = True
                    record["result"] = result
                    record["actual_value"] = actual
                    record["graded_at"] = datetime.now().isoformat()

                    graded_records.append(record)

                updated_lines.append(json.dumps(record) + "\n")

            # Write back updated predictions
            with open(log_path, 'w') as f:
                f.writelines(updated_lines)

            # Append to graded log
            if graded_records:
                with open(graded_path, 'a') as f:
                    for record in graded_records:
                        f.write(json.dumps(record) + "\n")

        except Exception as e:
            return {"graded": 0, "wins": 0, "losses": 0, "pushes": 0, "error": str(e)}

        return {
            "graded": len(graded_records),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "date_et": date_et
        }

    def get_grading_stats(self, sport: str = None, days_back: int = 7) -> Dict:
        """Get grading statistics across multiple days."""
        stats = {
            "total_predictions": 0,
            "total_graded": 0,
            "total_ungraded": 0,
            "wins": 0,
            "losses": 0,
            "pushes": 0,
            "hit_rate": 0.0,
            "by_sport": {}
        }

        sports = [sport.upper()] if sport else self.SUPPORTED_SPORTS

        for s in sports:
            sport_stats = {"predictions": 0, "graded": 0, "wins": 0, "losses": 0, "pushes": 0}

            for i in range(days_back):
                if ET_TIMEZONE:
                    day = datetime.now(ET_TIMEZONE) - timedelta(days=i)
                    date_et = day.strftime("%Y-%m-%d")
                else:
                    date_et = (datetime.utcnow() - timedelta(hours=5) - timedelta(days=i)).strftime("%Y-%m-%d")

                log_path = self._get_prediction_log_path(s, date_et)
                if os.path.exists(log_path):
                    try:
                        with open(log_path, 'r') as f:
                            for line in f:
                                if line.strip():
                                    record = json.loads(line)
                                    sport_stats["predictions"] += 1
                                    if record.get("graded"):
                                        sport_stats["graded"] += 1
                                        result = record.get("result", "")
                                        if result == "WIN":
                                            sport_stats["wins"] += 1
                                        elif result == "LOSS":
                                            sport_stats["losses"] += 1
                                        elif result == "PUSH":
                                            sport_stats["pushes"] += 1
                    except Exception:
                        pass

            stats["by_sport"][s] = sport_stats
            stats["total_predictions"] += sport_stats["predictions"]
            stats["total_graded"] += sport_stats["graded"]
            stats["total_ungraded"] += sport_stats["predictions"] - sport_stats["graded"]
            stats["wins"] += sport_stats["wins"]
            stats["losses"] += sport_stats["losses"]
            stats["pushes"] += sport_stats["pushes"]

        # Calculate hit rate
        total_decided = stats["wins"] + stats["losses"]
        if total_decided > 0:
            stats["hit_rate"] = round((stats["wins"] / total_decided) * 100, 1)

        return stats


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
# TESTING
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🎓 AUTO-GRADER TEST")
    print("=" * 60)
    
    grader = AutoGrader(storage_path="./test_grader_data")
    
    # Test weight retrieval
    print("\n📊 Default Weights:")
    for sport in ["NBA", "NFL", "MLB"]:
        weights = grader.get_weights(sport, "points" if sport != "MLB" else "hits")
        print(f"  {sport}: {weights}")
    
    # Test prediction logging
    print("\n📝 Logging test predictions...")
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
    print(f"  Logged: {pred_id}")
    
    # Test grading
    print("\n📈 Grading prediction...")
    grade = grader.grade_prediction(pred_id, actual_value=29.0)
    print(f"  Result: {grade}")
    
    # Test context feature calculation
    print("\n🔬 Context Feature Calculation:")
    context = ContextFeatureCalculator.calculate_context_features(
        sport="NBA",
        team_id="LAL",
        injuries=[
            {"status": "OUT", "stats": {"usage_pct": 0.28, "avg_minutes": 35}},
            {"status": "OUT", "stats": {"usage_pct": 0.18, "avg_minutes": 28}}
        ],
        game_stats={"home_pace": 102.5, "away_pace": 98.5}
    )
    print(f"  {context}")
    
    print("\n" + "=" * 60)
    print("✅ Auto-Grader tests complete!")
    print("=" * 60)
