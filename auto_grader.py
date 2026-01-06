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
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import numpy as np

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
    
    def _load_state(self):
        """Load persisted weights and prediction history."""
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
    
    def _save_state(self):
        """Persist weights to disk."""
        os.makedirs(self.storage_path, exist_ok=True)
        weights_file = os.path.join(self.storage_path, "weights.json")
        
        # Convert to serializable format
        data = {}
        for sport, stat_weights in self.weights.items():
            data[sport] = {}
            for stat, config in stat_weights.items():
                data[sport][stat] = asdict(config)
        
        with open(weights_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Saved weights to {weights_file}")
    
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
        return prediction_id
    
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
