"""
ML Integration Module - Activates Dormant ML Infrastructure
============================================================

This module provides:
1. Lazy-loading of LSTM models for player prop predictions
2. Sport/stat-specific model routing
3. Feature building from prop context
4. Integration with the scoring pipeline

The 13 pre-trained LSTM weight files are loaded on-demand and cached.
"""

import os
import json
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================
# STAT TYPE MAPPING
# ============================================

# Map market names to their LSTM model identifiers (sport-specific to avoid key collisions)
# These must match the weight file names: lstm_{sport}_{stat}.weights.h5
# Structure: {sport: {market: stat_type}}
SPORT_MARKET_TO_STAT = {
    "NBA": {
        "player_points": "points",
        "player_points_over_under": "points",
        "player_assists": "assists",
        "player_assists_over_under": "assists",
        "player_rebounds": "rebounds",
        "player_rebounds_over_under": "rebounds",
        "player_threes": "points",  # Use points model as proxy
        "player_steals": "points",  # Use points model as proxy
        "player_blocks": "points",  # Use points model as proxy
    },
    "NFL": {
        "player_pass_yds": "passing_yards",
        "player_passing_yards": "passing_yards",
        "player_rush_yds": "rushing_yards",
        "player_rushing_yards": "rushing_yards",
        "player_rec_yds": "receiving_yards",
        "player_reception_yds": "receiving_yards",  # Odds API uses this spelling
        "player_receiving_yards": "receiving_yards",
        "player_pass_tds": "passing_yards",  # Use yards model as proxy
        "player_rush_tds": "rushing_yards",  # Use yards model as proxy
        "player_receptions": "receiving_yards",  # Use yards model as proxy
    },
    "MLB": {
        "batter_hits": "hits",
        "player_hits": "hits",
        "batter_total_bases": "total_bases",
        "player_total_bases": "total_bases",
        "pitcher_strikeouts": "strikeouts",
        "player_strikeouts": "strikeouts",
        "batter_rbis": "hits",  # Use hits model as proxy
        "batter_runs": "hits",  # Use hits model as proxy
    },
    "NHL": {
        "player_points": "points",
        "player_shots": "shots",
        "player_goals": "points",  # Use points model as proxy
        "player_assists": "points",  # Use points model as proxy (no NHL assists model)
        "player_saves": "shots",  # Use shots model for goalies
    },
    "NCAAB": {
        "player_points": "points",
        "player_points_ncaab": "points",
        "player_rebounds": "rebounds",
        "player_rebounds_ncaab": "rebounds",
        "player_assists": "points",  # Use points model as proxy (no NCAAB assists model)
        "player_assists_ncaab": "points",
    },
}

# Flat fallback for backward compatibility (uses NBA mappings for shared keys)
MARKET_TO_STAT = {
    market: stat
    for sport_map in SPORT_MARKET_TO_STAT.values()
    for market, stat in sport_map.items()
}

# Sports that have LSTM models available
SUPPORTED_SPORTS = {"NBA", "NFL", "MLB", "NHL", "NCAAB"}

# ============================================
# MULTISPORT LSTM MANAGER
# ============================================

class PropLSTMManager:
    """
    Manages sport+stat specific LSTM models with lazy loading.

    Models are loaded on first access and cached for subsequent predictions.
    This avoids loading all 13 models at startup (slow + memory intensive).
    """

    def __init__(self, models_dir: str = None):
        """
        Initialize the LSTM manager.

        Args:
            models_dir: Directory containing LSTM weight files.
                       Defaults to ./models in the app directory.
        """
        if models_dir is None:
            # Default to models directory relative to this file
            models_dir = os.path.join(os.path.dirname(__file__), "models")

        self.models_dir = models_dir
        self._models: Dict[str, "LSTMBrain"] = {}  # Cache: "nba_points" -> LSTMBrain
        self._load_errors: Dict[str, str] = {}  # Track failed loads
        self._load_times: Dict[str, datetime] = {}  # Track when loaded
        self._prediction_counts: Dict[str, int] = {}  # Track usage

        # Verify models directory exists
        if not os.path.exists(models_dir):
            logger.warning(f"Models directory not found: {models_dir}")

    def get_model_key(self, sport: str, stat_type: str) -> str:
        """Generate cache key for sport+stat combo."""
        return f"{sport.lower()}_{stat_type.lower()}"

    def get_weight_path(self, sport: str, stat_type: str) -> str:
        """Get path to weight file for sport+stat."""
        return os.path.join(self.models_dir, f"lstm_{sport.lower()}_{stat_type.lower()}.weights.h5")

    def has_model(self, sport: str, stat_type: str) -> bool:
        """Check if a model exists for the given sport+stat."""
        weight_path = self.get_weight_path(sport, stat_type)
        return os.path.exists(weight_path)

    def get_stat_type(self, market: str, sport: str = None) -> Optional[str]:
        """Map a market name to its corresponding stat type.

        Args:
            market: Market name from Odds API (e.g., "player_assists")
            sport: Sport name for sport-specific mapping (e.g., "NBA")

        Returns:
            Stat type for LSTM model lookup, or None if not mapped
        """
        market_lower = market.lower().replace("-", "_").replace(" ", "_")

        # Try sport-specific mapping first to avoid key collisions
        if sport:
            sport_upper = sport.upper()
            if sport_upper in SPORT_MARKET_TO_STAT:
                result = SPORT_MARKET_TO_STAT[sport_upper].get(market_lower)
                if result:
                    return result

        # Fall back to flat mapping for backward compatibility
        return MARKET_TO_STAT.get(market_lower)

    def _load_model(self, sport: str, stat_type: str) -> Optional["LSTMBrain"]:
        """
        Load a specific LSTM model.

        Args:
            sport: Sport name (NBA, NFL, etc.)
            stat_type: Stat type (points, assists, etc.)

        Returns:
            Loaded LSTMBrain or None if load fails.
        """
        model_key = self.get_model_key(sport, stat_type)
        weight_path = self.get_weight_path(sport, stat_type)

        # Check if already loaded
        if model_key in self._models:
            return self._models[model_key]

        # Check if we already tried and failed
        if model_key in self._load_errors:
            return None

        # Check if weight file exists
        if not os.path.exists(weight_path):
            self._load_errors[model_key] = f"Weight file not found: {weight_path}"
            logger.warning(f"LSTM weights not found: {weight_path}")
            return None

        try:
            # Import here to avoid circular imports and allow lazy TensorFlow loading
            from lstm_brain import LSTMBrain

            # Create and load the brain
            brain = LSTMBrain(model_path=weight_path, sport=sport.upper())

            if brain.is_trained or brain.model is not None:
                self._models[model_key] = brain
                self._load_times[model_key] = datetime.now()
                self._prediction_counts[model_key] = 0
                logger.info(f"✅ LSTM model loaded: {model_key} from {weight_path}")
                return brain
            else:
                self._load_errors[model_key] = "Model loaded but not trained"
                logger.warning(f"LSTM model loaded but not trained: {model_key}")
                return None

        except Exception as e:
            self._load_errors[model_key] = str(e)
            logger.error(f"Failed to load LSTM model {model_key}: {e}")
            return None

    def predict(
        self,
        sport: str,
        market: str,
        current_features: Dict,
        historical_features: Optional[List[Dict]] = None,
        scale_factor: float = 3.0
    ) -> Optional[Dict]:
        """
        Get LSTM prediction for a player prop.

        Args:
            sport: Sport name (NBA, NFL, etc.)
            market: Market name (player_points, player_assists, etc.)
            current_features: Current game context features
            historical_features: Optional list of past game features
            scale_factor: Multiplier for raw output (default 3.0 maps [-1,1] to [-3,3])

        Returns:
            Prediction dict with adjustment value, or None if no model available.
        """
        # Map market to stat type (sport-aware to avoid key collisions)
        stat_type = self.get_stat_type(market, sport)
        if stat_type is None:
            return None

        # Check if sport is supported
        if sport.upper() not in SUPPORTED_SPORTS:
            return None

        # Load model (lazy)
        brain = self._load_model(sport.upper(), stat_type)
        if brain is None:
            return None

        try:
            # Build the sequence and get prediction
            result = brain.predict_from_context(
                current_features=current_features,
                historical_features=historical_features or [],
                sport=sport.upper(),
                scale_factor=scale_factor
            )

            # Track usage
            model_key = self.get_model_key(sport, stat_type)
            self._prediction_counts[model_key] = self._prediction_counts.get(model_key, 0) + 1

            # Add metadata
            result["sport"] = sport.upper()
            result["stat_type"] = stat_type
            result["market"] = market
            result["model_key"] = model_key

            return result

        except Exception as e:
            logger.error(f"LSTM prediction error for {sport}/{market}: {e}")
            return None

    def get_status(self) -> Dict:
        """Get status of all models."""
        # Check all possible model files
        available_models = []
        missing_models = []

        for sport in SUPPORTED_SPORTS:
            # Check what stat types this sport might have
            for stat_type in ["points", "assists", "rebounds", "passing_yards",
                              "rushing_yards", "receiving_yards", "hits",
                              "total_bases", "strikeouts", "shots"]:
                weight_path = self.get_weight_path(sport, stat_type)
                model_key = self.get_model_key(sport, stat_type)

                if os.path.exists(weight_path):
                    available_models.append({
                        "model_key": model_key,
                        "sport": sport,
                        "stat_type": stat_type,
                        "loaded": model_key in self._models,
                        "predictions": self._prediction_counts.get(model_key, 0),
                        "loaded_at": self._load_times.get(model_key, None)
                    })

        return {
            "models_dir": self.models_dir,
            "available_models": available_models,
            "loaded_count": len(self._models),
            "total_predictions": sum(self._prediction_counts.values()),
            "load_errors": self._load_errors
        }


# ============================================
# GLOBAL SINGLETON (Lazy Loaded)
# ============================================

_lstm_manager: Optional[PropLSTMManager] = None


def get_lstm_manager() -> PropLSTMManager:
    """Get or create the global LSTM manager singleton."""
    global _lstm_manager
    if _lstm_manager is None:
        _lstm_manager = PropLSTMManager()
    return _lstm_manager


# ============================================
# FEATURE BUILDING HELPERS
# ============================================

def build_lstm_features_from_prop_context(
    player_name: str,
    market: str,
    line: float,
    home_team: str,
    away_team: str,
    player_team: Optional[str] = None,
    player_stats: Optional[Dict] = None,
    game_data: Optional[Dict] = None,
    sport: str = "NBA"
) -> Dict:
    """
    Build LSTM input features from prop scoring context.

    This creates the 6-feature vector needed for LSTM input:
    [stat, mins, home_away, vacuum, def_rank, pace]

    Args:
        player_name: Player name
        market: Prop market (e.g., "player_points")
        line: Prop line value
        home_team: Home team name
        away_team: Away team name
        player_team: Player's team (optional)
        player_stats: Optional player stats dict with averages
        game_data: Optional game context (pace, defense rank, etc.)
        sport: Sport name

    Returns:
        Dict with features ready for LSTMBrain.normalize_features()
    """
    # Default values (neutral)
    features = {
        "stat": line,  # Use prop line as proxy for expected stat
        "player_avg": line * 1.1,  # Assume line is ~10% below actual avg
        "mins": 30.0,  # Default minutes
        "home_away": 0.5,  # Default neutral
        "vacuum": 0.0,  # Default no vacuum (no injuries boosting usage)
        "def_rank": 16,  # Default middle of pack
        "pace": 100.0,  # Default neutral pace (NBA)
    }

    # Determine home/away
    if player_team:
        if player_team.upper() == home_team.upper():
            features["home_away"] = 1.0  # Home
        elif player_team.upper() == away_team.upper():
            features["home_away"] = 0.0  # Away

    # Use player stats if available
    if player_stats:
        if "average" in player_stats:
            features["player_avg"] = player_stats["average"]
        if "avg" in player_stats:
            features["player_avg"] = player_stats["avg"]
        if "minutes" in player_stats:
            features["mins"] = player_stats["minutes"]
        if "mpg" in player_stats:
            features["mins"] = player_stats["mpg"]

    # Use game data if available
    if game_data:
        if "pace" in game_data:
            features["pace"] = game_data["pace"]
        if "def_rank" in game_data:
            features["def_rank"] = game_data["def_rank"]
        if "defense_rank" in game_data:
            features["def_rank"] = game_data["defense_rank"]
        if "vacuum" in game_data:
            features["vacuum"] = game_data["vacuum"]
        if "injuries_impact" in game_data:
            # Injuries can create usage vacuum
            features["vacuum"] = min(game_data["injuries_impact"] / 10.0, 1.0)

    # Sport-specific defaults
    if sport.upper() == "NFL":
        features["mins"] = 60.0
        features["pace"] = 65.0
    elif sport.upper() == "MLB":
        features["mins"] = 4.0  # At-bats
        features["pace"] = 100.0
    elif sport.upper() == "NHL":
        features["mins"] = 18.0  # TOI
        features["pace"] = 32.0
    elif sport.upper() == "NCAAB":
        features["mins"] = 32.0
        features["pace"] = 68.0

    return features


def get_lstm_ai_score(
    sport: str,
    market: str,
    prop_line: float,
    player_name: str,
    home_team: str,
    away_team: str,
    player_team: Optional[str] = None,
    player_stats: Optional[Dict] = None,
    game_data: Optional[Dict] = None,
    base_ai: float = 5.0
) -> Tuple[float, Dict]:
    """
    Get AI score using LSTM prediction.

    This is the main integration point for the scoring pipeline.
    Returns an AI score in the 0-8 range (matching existing heuristic range).

    Args:
        sport: Sport name
        market: Prop market
        prop_line: Prop line value
        player_name: Player name
        home_team: Home team
        away_team: Away team
        player_team: Player's team
        player_stats: Optional player stats
        game_data: Optional game data
        base_ai: Base AI score to use as fallback

    Returns:
        Tuple of (ai_score, metadata_dict)
    """
    manager = get_lstm_manager()

    # Build features
    features = build_lstm_features_from_prop_context(
        player_name=player_name,
        market=market,
        line=prop_line,
        home_team=home_team,
        away_team=away_team,
        player_team=player_team,
        player_stats=player_stats,
        game_data=game_data,
        sport=sport
    )

    # Try to get LSTM prediction
    prediction = manager.predict(
        sport=sport,
        market=market,
        current_features=features,
        historical_features=None,  # TODO: Could add historical data lookup
        scale_factor=3.0  # Maps [-1, 1] to [-3, 3] adjustment
    )

    if prediction is None:
        # No model available, return base with heuristic flag
        return base_ai, {
            "source": "heuristic",
            "reason": "No LSTM model available for this sport/market"
        }

    # Convert LSTM adjustment to AI score
    # LSTM outputs adjustment in [-3, 3] range
    # We want AI score in [2, 8] range (centered on base_ai=5.0)
    adjustment = prediction.get("adjustment", 0.0)

    # Clamp adjustment to [-3, 3]
    adjustment = max(-3.0, min(3.0, adjustment))

    # Apply to base to get AI score in [2, 8]
    ai_score = base_ai + adjustment
    ai_score = max(2.0, min(8.0, ai_score))  # Clamp to valid range

    metadata = {
        "source": "lstm",
        "model_key": prediction.get("model_key"),
        "method": prediction.get("method"),
        "raw_output": prediction.get("raw_output"),
        "adjustment": adjustment,
        "confidence": prediction.get("confidence"),
        "is_trained": prediction.get("is_trained"),
        "features_used": features
    }

    return round(ai_score, 2), metadata


# ============================================
# ENSEMBLE MODEL MANAGER (For Game Picks)
# ============================================

class EnsembleModelManager:
    """
    Manages the trained ensemble model for game pick predictions.

    The ensemble model predicts hit probability based on scoring engine outputs.
    It's trained from graded predictions using scripts/train_ensemble.py.
    """

    def __init__(self, models_dir: str = None):
        """Initialize ensemble manager."""
        if models_dir is None:
            # Default to /data/models in production, ./models locally
            if os.path.exists("/data/models"):
                models_dir = "/data/models"
            else:
                models_dir = os.path.join(os.path.dirname(__file__), "models")

        self.models_dir = models_dir
        self.model = None
        self.metadata = None
        self.model_path = os.path.join(models_dir, "ensemble_hit_predictor.joblib")
        self.metadata_path = os.path.join(models_dir, "ensemble_hit_predictor_metadata.json")
        self._load_error = None
        self._prediction_count = 0

    def is_available(self) -> bool:
        """Check if ensemble model file exists."""
        return os.path.exists(self.model_path)

    def _load_model(self) -> bool:
        """Load the ensemble model."""
        if self.model is not None:
            return True

        if not self.is_available():
            self._load_error = "Model file not found"
            return False

        try:
            import joblib
            self.model = joblib.load(self.model_path)

            # Load metadata if available
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, 'r') as f:
                    self.metadata = json.load(f)

            logger.info(f"✅ Ensemble model loaded from {self.model_path}")
            return True

        except Exception as e:
            self._load_error = str(e)
            logger.error(f"Failed to load ensemble model: {e}")
            return False

    def predict_hit_probability(
        self,
        ai_score: float,
        research_score: float,
        esoteric_score: float,
        jarvis_score: float,
        line: float = 0.0,
        odds: int = -110,
        confluence_boost: float = 0.0,
        jason_sim_boost: float = 0.0,
        titanium_triggered: bool = False,
        sport: str = "NBA",
        pick_type: str = "GAME",
        side: str = "Home"
    ) -> Optional[Dict]:
        """
        Predict hit probability for a game pick.

        Returns dict with hit_probability and metadata, or None if model unavailable.
        """
        if not self._load_model():
            return None

        try:
            import numpy as np

            # Encode categorical variables
            sport_encoding = {"NBA": 0, "NFL": 1, "MLB": 2, "NHL": 3, "NCAAB": 4}
            sport_encoded = sport_encoding.get(sport.upper(), 0)

            if "PROP" in pick_type.upper():
                pick_type_encoded = 0
            elif "SPREAD" in pick_type.upper():
                pick_type_encoded = 1
            elif "TOTAL" in pick_type.upper():
                pick_type_encoded = 2
            else:
                pick_type_encoded = 3

            if side in ["Over", "OVER"]:
                side_encoded = 0
            elif side in ["Under", "UNDER"]:
                side_encoded = 1
            elif side == "Home":
                side_encoded = 2
            else:
                side_encoded = 3

            # Build feature vector
            features = np.array([[
                ai_score,
                research_score,
                esoteric_score,
                jarvis_score,
                float(line),
                float(odds),
                confluence_boost,
                jason_sim_boost,
                1.0 if titanium_triggered else 0.0,
                sport_encoded,
                pick_type_encoded,
                side_encoded
            ]], dtype=np.float32)

            # Predict
            hit_prob = self.model.predict_proba(features)[0][1]
            self._prediction_count += 1

            return {
                "hit_probability": round(float(hit_prob), 4),
                "predicted_hit": hit_prob >= 0.5,
                "confidence": round(abs(hit_prob - 0.5) * 200, 1),  # Scale to 0-100%
                "model_type": type(self.model).__name__,
                "trained_at": self.metadata.get("trained_at") if self.metadata else None
            }

        except Exception as e:
            logger.error(f"Ensemble prediction error: {e}")
            return None

    def get_status(self) -> Dict:
        """Get ensemble model status."""
        return {
            "available": self.is_available(),
            "loaded": self.model is not None,
            "model_path": self.model_path,
            "predictions": self._prediction_count,
            "load_error": self._load_error,
            "metadata": self.metadata
        }


# Global ensemble manager singleton
_ensemble_manager: Optional[EnsembleModelManager] = None


def get_ensemble_manager() -> EnsembleModelManager:
    """Get or create the global ensemble manager singleton."""
    global _ensemble_manager
    if _ensemble_manager is None:
        _ensemble_manager = EnsembleModelManager()
    return _ensemble_manager


def get_ensemble_ai_score(
    ai_score: float,
    research_score: float,
    esoteric_score: float,
    jarvis_score: float,
    line: float = 0.0,
    odds: int = -110,
    confluence_boost: float = 0.0,
    jason_sim_boost: float = 0.0,
    titanium_triggered: bool = False,
    sport: str = "NBA",
    pick_type: str = "GAME",
    side: str = "Home",
    base_ai: float = 4.5
) -> Tuple[float, Dict]:
    """
    Get AI score using ensemble model prediction for game picks.

    Converts hit probability to an AI score in [2, 8] range.
    Falls back to heuristic if ensemble model unavailable.
    """
    manager = get_ensemble_manager()
    prediction = manager.predict_hit_probability(
        ai_score=ai_score,
        research_score=research_score,
        esoteric_score=esoteric_score,
        jarvis_score=jarvis_score,
        line=line,
        odds=odds,
        confluence_boost=confluence_boost,
        jason_sim_boost=jason_sim_boost,
        titanium_triggered=titanium_triggered,
        sport=sport,
        pick_type=pick_type,
        side=side
    )

    if prediction is None:
        return base_ai, {
            "source": "heuristic",
            "reason": "Ensemble model not available"
        }

    # Convert hit probability to AI score
    # hit_prob 0.5 -> base_ai, 1.0 -> 8.0, 0.0 -> 2.0
    hit_prob = prediction["hit_probability"]
    adjusted_ai = base_ai + (hit_prob - 0.5) * 6.0  # Maps [0,1] to [-3, 3] adjustment
    adjusted_ai = max(2.0, min(8.0, adjusted_ai))

    metadata = {
        "source": "ensemble",
        "hit_probability": prediction["hit_probability"],
        "confidence": prediction["confidence"],
        "adjustment": round(adjusted_ai - base_ai, 2),
        "model_type": prediction["model_type"],
        "trained_at": prediction["trained_at"]
    }

    return round(adjusted_ai, 2), metadata


# ============================================
# STATUS CHECK FUNCTION
# ============================================

def get_ml_status() -> Dict:
    """Get comprehensive ML infrastructure status."""
    lstm_manager = get_lstm_manager()
    lstm_status = lstm_manager.get_status()

    ensemble_manager = get_ensemble_manager()
    ensemble_status = ensemble_manager.get_status()

    # Check TensorFlow availability
    try:
        from lstm_brain import TF_AVAILABLE
        tf_available = TF_AVAILABLE
    except ImportError:
        tf_available = False

    return {
        "timestamp": datetime.now().isoformat(),
        "tensorflow_available": tf_available,
        "lstm": lstm_status,
        "ensemble": ensemble_status,
        "supported_sports": list(SUPPORTED_SPORTS),
        "market_mappings": len(MARKET_TO_STAT)
    }
