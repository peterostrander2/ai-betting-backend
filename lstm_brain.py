"""
LSTM Brain - The Neural Core of Bookie-o-em
============================================
Real TensorFlow LSTM inference for sports betting predictions.

Input Shape: (15, 6) - 15 game history, 6 context features per game
Features (aligned with spec):
    0: stat (player's stat value for that game, normalized)
    1: mins (minutes played, normalized 0-1)
    2: home_away (0 = away, 1 = home)
    3: vacuum (0-1, usage redistribution factor)
    4: def_rank (opponent defense rank 1-32, normalized 0-1)
    5: pace (game pace factor, normalized 0-1)

Output: Prediction adjustment value for the waterfall
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
import os

# Silence TensorFlow/CUDA noise BEFORE import (must be set before TF loads)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")  # Suppress TF INFO/WARN/ERROR
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")   # Force CPU-only (no GPU probing)
os.environ.setdefault("XLA_FLAGS", "--xla_gpu_cuda_data_dir=")  # Reduce XLA GPU probing

# TensorFlow import with fallback
try:
    import tensorflow as tf
    tf.get_logger().setLevel('ERROR')  # Additional Python-level suppression
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization, Bidirectional
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("⚠️ TensorFlow not available - using numpy fallback")


class LSTMBrain:
    """
    The Neural Core - Real LSTM inference for sports betting predictions.
    
    Architecture:
        Input: (batch, 15, 6) - 15 timesteps of 6 context features
        LSTM: Bidirectional with 64 units
        Dense: 32 units with ReLU
        Output: Single prediction adjustment value
    """
    
    # Input specifications
    SEQUENCE_LENGTH = 15  # Number of historical games
    NUM_FEATURES = 6      # Features per game
    INPUT_SHAPE = (SEQUENCE_LENGTH, NUM_FEATURES)
    
    # Feature indices for reference (ALIGNED WITH SPEC)
    FEATURE_NAMES = [
        "stat",       # 0: Player's stat value (normalized by player avg)
        "mins",       # 1: Minutes played (normalized 0-1, max ~48 NBA, ~60 NFL, etc)
        "home_away",  # 2: 0 = away, 1 = home
        "vacuum",     # 3: Usage vacuum (0-1)
        "def_rank",   # 4: Opponent defense rank (1-32 normalized to 0-1)
        "pace"        # 5: Game pace factor (normalized 0-1)
    ]
    
    # Feature weights for fallback inference
    FEATURE_WEIGHTS = {
        "stat": 0.25,      # Historical performance matters most
        "mins": 0.10,      # Minutes = opportunity
        "home_away": 0.10, # Home court advantage
        "vacuum": 0.20,    # Injury opportunity
        "def_rank": 0.20,  # Matchup quality
        "pace": 0.15       # Game tempo
    }
    
    def __init__(self, model_path: Optional[str] = None, sport: str = "NBA"):
        """
        Initialize LSTM Brain.
        
        Args:
            model_path: Path to saved model weights (optional)
            sport: Sport for sport-specific model loading
        """
        self.sport = sport.upper()
        self.model = None
        self.model_path = model_path
        self.is_trained = False
        
        if TF_AVAILABLE:
            self._build_model()
            if model_path and os.path.exists(model_path):
                self._load_weights(model_path)
        else:
            print(f"🧠 LSTM Brain ({sport}) initialized in numpy fallback mode")
    
    def _build_model(self) -> None:
        """Build the LSTM architecture."""
        if not TF_AVAILABLE:
            return
            
        self.model = Sequential([
            # Bidirectional LSTM for temporal pattern recognition
            Bidirectional(
                LSTM(64, return_sequences=True, dropout=0.2, recurrent_dropout=0.1),
                input_shape=self.INPUT_SHAPE
            ),
            BatchNormalization(),
            
            # Second LSTM layer
            Bidirectional(
                LSTM(32, return_sequences=False, dropout=0.2, recurrent_dropout=0.1)
            ),
            BatchNormalization(),
            
            # Dense layers for final prediction
            Dense(32, activation='relu'),
            Dropout(0.3),
            Dense(16, activation='relu'),
            Dropout(0.2),
            
            # Output: single prediction adjustment value
            Dense(1, activation='tanh')  # tanh keeps output in -1 to 1 range
        ])
        
        self.model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='mse',
            metrics=['mae']
        )
        
        print(f"🧠 LSTM Brain ({self.sport}) built: {self.INPUT_SHAPE} -> 1")
    
    def _load_weights(self, path: str) -> bool:
        """Load pre-trained weights."""
        try:
            self.model.load_weights(path)
            self.is_trained = True
            print(f"✅ Loaded weights from {path}")
            return True
        except Exception as e:
            print(f"⚠️ Could not load weights: {e}")
            return False
    
    def save_weights(self, path: str) -> bool:
        """Save model weights."""
        try:
            self.model.save_weights(path)
            print(f"✅ Saved weights to {path}")
            return True
        except Exception as e:
            print(f"⚠️ Could not save weights: {e}")
            return False
    
    def normalize_features(self, lstm_features: Dict, sport: str = "NBA") -> np.ndarray:
        """
        Convert lstm_features dict to normalized numpy array.
        
        Args:
            lstm_features: Dict with stat, mins, home_away, vacuum, def_rank, pace
            sport: Sport for sport-specific normalization
            
        Returns:
            (6,) numpy array with normalized features [stat, mins, home_away, vacuum, def_rank, pace]
        """
        # Extract values with defaults
        stat = lstm_features.get("stat", 0.0)  # Raw stat value
        player_avg = lstm_features.get("player_avg", 20.0)  # For normalization
        mins = lstm_features.get("mins", 30.0)  # Minutes played
        home_away = lstm_features.get("home_away", 0.5)  # 0=away, 1=home, 0.5=neutral
        vacuum = lstm_features.get("vacuum", 0.0)  # Usage vacuum
        def_rank = lstm_features.get("def_rank", lstm_features.get("defense_rank", 16))  # Defense rank
        pace = lstm_features.get("pace", 100.0)  # Game pace
        
        # Sport-specific normalization ranges
        normalization = {
            "NBA": {"pace_min": 95, "pace_max": 105, "rank_max": 30, "mins_max": 48},
            "NFL": {"pace_min": 55, "pace_max": 75, "rank_max": 32, "mins_max": 60},
            "MLB": {"pace_min": 85, "pace_max": 115, "rank_max": 30, "mins_max": 9},  # Innings for pitchers
            "NHL": {"pace_min": 28, "pace_max": 36, "rank_max": 32, "mins_max": 25},  # TOI
            "NCAAB": {"pace_min": 60, "pace_max": 75, "rank_max": 400, "mins_max": 40}
        }
        
        norms = normalization.get(sport.upper(), normalization["NBA"])
        
        # Normalize stat by player average (ratio: 1.0 = at avg, >1 = above avg)
        stat_norm = np.clip(stat / max(player_avg, 1.0), 0, 2) / 2  # 0-2 range -> 0-1
        
        # Normalize minutes (0-1)
        mins_norm = np.clip(mins / norms["mins_max"], 0, 1)
        
        # Home/away is already 0 or 1
        home_away_norm = np.clip(float(home_away), 0, 1)
        
        # Vacuum is already 0-1
        vacuum_norm = np.clip(vacuum, 0, 1)
        
        # Normalize defense rank (1-32 -> 0-1, where 0=best defense, 1=worst)
        def_rank_norm = np.clip((def_rank - 1) / (norms["rank_max"] - 1), 0, 1)
        
        # Normalize pace
        pace_norm = np.clip(
            (pace - norms["pace_min"]) / (norms["pace_max"] - norms["pace_min"]), 
            0, 1
        )
        
        # Return in spec order: [stat, mins, home_away, vacuum, def_rank, pace]
        return np.array([
            stat_norm,
            mins_norm,
            home_away_norm,
            vacuum_norm,
            def_rank_norm,
            pace_norm
        ], dtype=np.float32)
    
    def build_sequence(
        self, 
        historical_features: List[Dict], 
        current_features: Dict,
        sport: str = "NBA"
    ) -> np.ndarray:
        """
        Build (15, 6) sequence from historical + current features.
        
        Args:
            historical_features: List of up to 14 past game lstm_features dicts
            current_features: Current game's lstm_features dict
            sport: Sport for normalization
            
        Returns:
            (15, 6) numpy array ready for LSTM input
        """
        sequence = np.zeros((self.SEQUENCE_LENGTH, self.NUM_FEATURES), dtype=np.float32)
        
        # Fill historical data (pad with zeros if < 14 games)
        for i, features in enumerate(historical_features[-14:]):  # Take last 14
            if i >= 14:
                break
            idx = 14 - len(historical_features[-14:]) + i
            sequence[idx] = self.normalize_features(features, sport)
        
        # Current game is the last timestep
        sequence[14] = self.normalize_features(current_features, sport)
        
        return sequence
    
    def predict(
        self, 
        sequence: np.ndarray,
        scale_factor: float = 5.0
    ) -> Dict:
        """
        Run LSTM inference on input sequence.
        
        Args:
            sequence: (15, 6) or (batch, 15, 6) numpy array
            scale_factor: Multiplier to convert -1/1 output to point adjustment
            
        Returns:
            Dict with prediction adjustment and confidence
        """
        # Ensure 3D input (batch, seq, features)
        if sequence.ndim == 2:
            sequence = np.expand_dims(sequence, axis=0)
        
        # Validate shape
        if sequence.shape[1:] != self.INPUT_SHAPE:
            raise ValueError(f"Expected shape (batch, 15, 6), got {sequence.shape}")
        
        if TF_AVAILABLE and self.model is not None:
            # Real TensorFlow inference
            raw_output = self.model.predict(sequence, verbose=0)
            adjustment = float(raw_output[0, 0]) * scale_factor
            
            # Calculate confidence from output magnitude
            confidence = min(abs(raw_output[0, 0]) * 100, 100)
            
            return {
                "adjustment": round(adjustment, 2),
                "raw_output": float(raw_output[0, 0]),
                "confidence": round(confidence, 1),
                "method": "tensorflow_lstm",
                "is_trained": self.is_trained
            }
        else:
            # Numpy fallback - weighted feature analysis
            return self._numpy_fallback_predict(sequence, scale_factor)
    
    def _numpy_fallback_predict(
        self, 
        sequence: np.ndarray, 
        scale_factor: float
    ) -> Dict:
        """
        Fallback prediction using numpy when TensorFlow unavailable.
        Uses weighted moving average of context features.
        
        Features: [stat, mins, home_away, vacuum, def_rank, pace]
        """
        # Recent game weights (more recent = more weight)
        weights = np.linspace(0.5, 1.5, self.SEQUENCE_LENGTH)
        weights = weights / weights.sum()
        
        # Feature importance weights (aligned with spec)
        # [stat, mins, home_away, vacuum, def_rank, pace]
        feature_weights = np.array([
            0.25,  # stat - historical performance matters most
            0.10,  # mins - minutes = opportunity
            0.10,  # home_away - home court advantage
            0.20,  # vacuum - injury opportunity (high importance)
            0.20,  # def_rank - matchup quality (high importance)
            0.15   # pace - game tempo
        ])
        
        # Weighted feature averages across time
        weighted_features = np.average(sequence[0], axis=0, weights=weights)
        
        # Combined score
        raw_score = np.sum(weighted_features * feature_weights)
        
        # Transform to -1 to 1 range (features are normalized 0-1)
        # For interpretation:
        # - High stat (>0.5) = historically performing well = positive
        # - High def_rank (>0.5) = weak defense = positive (OVER)
        # - High vacuum (>0.5) = more opportunity = positive
        # - High pace (>0.5) = faster game = positive
        # - Home (1) = advantage = slight positive
        centered = (raw_score - 0.5) * 2
        adjustment = centered * scale_factor
        
        return {
            "adjustment": round(adjustment, 2),
            "raw_output": round(centered, 4),
            "confidence": round(abs(centered) * 100, 1),
            "method": "numpy_fallback",
            "is_trained": False,
            "feature_analysis": {
                "stat_signal": round(weighted_features[0], 3),
                "mins_signal": round(weighted_features[1], 3),
                "home_away_signal": round(weighted_features[2], 3),
                "vacuum_signal": round(weighted_features[3], 3),
                "def_rank_signal": round(weighted_features[4], 3),
                "pace_signal": round(weighted_features[5], 3)
            }
        }
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2,
        epochs: int = 100,
        batch_size: int = 32,
        save_path: Optional[str] = None
    ) -> Dict:
        """
        Train LSTM on historical data.
        
        Args:
            X: (n_samples, 15, 6) training sequences
            y: (n_samples,) target adjustments
            validation_split: Fraction for validation
            epochs: Maximum training epochs
            batch_size: Training batch size
            save_path: Path to save best weights
            
        Returns:
            Training history dict
        """
        if not TF_AVAILABLE:
            return {"error": "TensorFlow not available"}
        
        callbacks = [
            EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True
            )
        ]
        
        if save_path:
            callbacks.append(
                ModelCheckpoint(
                    save_path,
                    monitor='val_loss',
                    save_best_only=True,
                    save_weights_only=True
                )
            )
        
        history = self.model.fit(
            X, y,
            validation_split=validation_split,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callbacks,
            verbose=1
        )
        
        self.is_trained = True
        
        return {
            "final_loss": float(history.history['loss'][-1]),
            "final_val_loss": float(history.history['val_loss'][-1]),
            "epochs_trained": len(history.history['loss']),
            "best_val_loss": float(min(history.history['val_loss']))
        }
    
    def predict_from_context(
        self,
        current_features: Dict,
        historical_features: Optional[List[Dict]] = None,
        sport: str = "NBA",
        scale_factor: float = 5.0
    ) -> Dict:
        """
        High-level prediction from context layer features.
        
        Args:
            current_features: Current game's lstm_features dict
            historical_features: List of past game lstm_features (optional)
            sport: Sport for normalization
            scale_factor: Output scaling multiplier
            
        Returns:
            Prediction dict with adjustment, confidence, etc.
        """
        if historical_features is None:
            historical_features = []
        
        # Build sequence
        sequence = self.build_sequence(historical_features, current_features, sport)
        
        # Run prediction
        result = self.predict(sequence, scale_factor)
        result["sport"] = sport
        result["sequence_length"] = len(historical_features) + 1
        result["has_history"] = len(historical_features) > 0
        
        return result


class MultiSportLSTMBrain:
    """
    Manager for sport-specific LSTM models.
    """
    
    def __init__(self, models_dir: str = "./models"):
        """Initialize with directory for sport-specific models."""
        self.models_dir = models_dir
        self.brains: Dict[str, LSTMBrain] = {}
        
        # Initialize brains for all supported sports
        for sport in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
            model_path = os.path.join(models_dir, f"lstm_{sport.lower()}.weights.h5")
            self.brains[sport] = LSTMBrain(
                model_path=model_path if os.path.exists(model_path) else None,
                sport=sport
            )
    
    def predict(
        self,
        sport: str,
        current_features: Dict,
        historical_features: Optional[List[Dict]] = None,
        scale_factor: float = 5.0
    ) -> Dict:
        """
        Route prediction to sport-specific LSTM.
        """
        sport = sport.upper()
        if sport not in self.brains:
            raise ValueError(f"Unknown sport: {sport}")
        
        return self.brains[sport].predict_from_context(
            current_features=current_features,
            historical_features=historical_features,
            sport=sport,
            scale_factor=scale_factor
        )
    
    def get_status(self) -> Dict:
        """Get status of all sport models."""
        return {
            sport: {
                "initialized": brain.model is not None or not TF_AVAILABLE,
                "is_trained": brain.is_trained,
                "method": "tensorflow_lstm" if TF_AVAILABLE and brain.model else "numpy_fallback"
            }
            for sport, brain in self.brains.items()
        }


# ============================================
# INTEGRATION HELPER
# ============================================

def integrate_lstm_prediction(
    context_result: Dict,
    historical_features: Optional[List[Dict]] = None,
    brain: Optional[LSTMBrain] = None
) -> Dict:
    """
    Integrate LSTM prediction into context layer result.
    
    Args:
        context_result: Result from ContextGenerator.generate_context()
        historical_features: Past game features for sequence
        brain: Optional pre-initialized LSTMBrain
        
    Returns:
        Updated context_result with LSTM adjustment added
    """
    sport = context_result.get("sport", "NBA")
    lstm_features = context_result.get("lstm_features", {})
    
    # Initialize brain if not provided
    if brain is None:
        brain = LSTMBrain(sport=sport)
    
    # Get LSTM prediction
    lstm_result = brain.predict_from_context(
        current_features=lstm_features,
        historical_features=historical_features or [],
        sport=sport
    )
    
    # Add to waterfall
    waterfall = context_result.get("waterfall", {})
    current_final = waterfall.get("finalPrediction", context_result.get("player_avg", 0))
    
    adjustment = lstm_result["adjustment"]
    new_final = round(current_final + adjustment, 1)
    
    # Update waterfall
    waterfall["adjustments"] = waterfall.get("adjustments", [])
    waterfall["adjustments"].append({
        "factor": "lstm_brain",
        "value": adjustment,
        "reason": f"LSTM neural prediction ({lstm_result['method']})"
    })
    waterfall["finalPrediction"] = new_final
    
    # Add LSTM result to context
    context_result["lstm_prediction"] = lstm_result
    context_result["waterfall"] = waterfall
    
    # Add brain badge if significant adjustment
    if abs(adjustment) >= 1.0:
        badges = context_result.get("badges", [])
        badges.append({
            "icon": "🧠",
            "label": "brain",
            "active": True,
            "confidence": lstm_result["confidence"]
        })
        context_result["badges"] = badges
    
    return context_result


# ============================================
# TESTING
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧠 LSTM BRAIN TEST")
    print("=" * 60)
    
    # Test basic initialization
    brain = LSTMBrain(sport="NBA")
    
    # Test feature normalization
    test_features = {
        "defense_rank": 5,
        "defense_context": 0.15,
        "pace": 102.5,
        "pace_context": 0.08,
        "vacuum": 0.25,
        "vacuum_context": 0.12
    }
    
    normalized = brain.normalize_features(test_features, "NBA")
    print(f"\n📊 Feature normalization test:")
    print(f"   Input: {test_features}")
    print(f"   Normalized: {normalized}")
    
    # Test sequence building
    historical = [
        {"defense_rank": 10, "defense_context": 0.1, "pace": 100, 
         "pace_context": 0.0, "vacuum": 0.1, "vacuum_context": 0.05}
        for _ in range(10)
    ]
    
    sequence = brain.build_sequence(historical, test_features, "NBA")
    print(f"\n📈 Sequence shape: {sequence.shape}")
    print(f"   Expected: (15, 6)")
    
    # Test prediction
    result = brain.predict(sequence)
    print(f"\n🎯 Prediction result:")
    print(f"   Adjustment: {result['adjustment']}")
    print(f"   Confidence: {result['confidence']}%")
    print(f"   Method: {result['method']}")
    
    # Test high-level predict_from_context
    result2 = brain.predict_from_context(
        current_features=test_features,
        historical_features=historical,
        sport="NBA"
    )
    print(f"\n🏀 Full prediction from context:")
    print(f"   Result: {result2}")
    
    # Test MultiSportLSTMBrain
    print(f"\n🌐 Multi-sport brain status:")
    multi_brain = MultiSportLSTMBrain()
    status = multi_brain.get_status()
    for sport, info in status.items():
        print(f"   {sport}: {info}")
    
    print("\n" + "=" * 60)
    print("✅ LSTM Brain tests complete!")
    print("=" * 60)
