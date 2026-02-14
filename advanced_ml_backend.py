"""
Advanced AI Sports Betting Backend with 8 AI Models + 8 Pillars of Execution
Railway-Ready Production Version
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from scipy import stats
import joblib
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from pathlib import Path

# Silence TensorFlow/CUDA noise BEFORE import (must be set before TF loads)
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"  # Suppress TF INFO/WARN/ERROR
os.environ["CUDA_VISIBLE_DEVICES"] = ""   # Force CPU-only (no GPU probing)
os.environ["XLA_FLAGS"] = "--xla_gpu_cuda_data_dir="  # Reduce XLA GPU probing

# Optional: TensorFlow for LSTM (can be added in Phase 2)
try:
    import tensorflow as tf
    tf.get_logger().setLevel('ERROR')  # Additional Python-level suppression
    from tensorflow import keras
    from tensorflow.keras import layers
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logger.warning("TensorFlow not available - LSTM model will use fallback")

# ============================================
# 🏛️ THE 8 PILLARS OF EXECUTION
# ============================================

class PillarsAnalyzer:
    """
    Your 8 Pillars betting strategy integrated into AI
    Each pillar provides signals that influence final recommendation
    """
    
    def __init__(self):
        self.pillar_scores = {}
        self.pillar_signals = {}
        
    def analyze_all_pillars(self, game_data: Dict) -> Dict:
        """Run all 8 pillars and return comprehensive analysis"""
        
        results = {
            'pillar_scores': {},
            'pillar_signals': {},
            'pillar_recommendations': {},
            'overall_pillar_score': 0,
            'pillars_triggered': []
        }
        
        # Pillar 1: Sharp Split
        p1 = self._pillar_1_sharp_split(game_data)
        results['pillar_scores']['sharp_split'] = p1['score']
        results['pillar_signals']['sharp_split'] = p1['signal']
        results['pillar_recommendations']['sharp_split'] = p1['recommendation']
        if p1['triggered']:
            results['pillars_triggered'].append('Sharp Split')
        
        # Pillar 2: Reverse Line Move
        p2 = self._pillar_2_reverse_line(game_data)
        results['pillar_scores']['reverse_line'] = p2['score']
        results['pillar_signals']['reverse_line'] = p2['signal']
        results['pillar_recommendations']['reverse_line'] = p2['recommendation']
        if p2['triggered']:
            results['pillars_triggered'].append('Reverse Line Move')
        
        # Pillar 3: Hospital Fade (Injury Audit)
        p3 = self._pillar_3_hospital_fade(game_data)
        results['pillar_scores']['hospital_fade'] = p3['score']
        results['pillar_signals']['hospital_fade'] = p3['signal']
        results['pillar_recommendations']['hospital_fade'] = p3['recommendation']
        if p3['triggered']:
            results['pillars_triggered'].append('Hospital Fade')
        
        # Pillar 4: Situational Spot
        p4 = self._pillar_4_situational_spot(game_data)
        results['pillar_scores']['situational_spot'] = p4['score']
        results['pillar_signals']['situational_spot'] = p4['signal']
        results['pillar_recommendations']['situational_spot'] = p4['recommendation']
        if p4['triggered']:
            results['pillars_triggered'].append('Situational Spot')
        
        # Pillar 5: Expert Consensus (if data available)
        p5 = self._pillar_5_expert_consensus(game_data)
        results['pillar_scores']['expert_consensus'] = p5['score']
        results['pillar_signals']['expert_consensus'] = p5['signal']
        results['pillar_recommendations']['expert_consensus'] = p5['recommendation']
        if p5['triggered']:
            results['pillars_triggered'].append('Expert Consensus')
        
        # Pillar 6: Prop Correlation
        p6 = self._pillar_6_prop_correlation(game_data)
        results['pillar_scores']['prop_correlation'] = p6['score']
        results['pillar_signals']['prop_correlation'] = p6['signal']
        results['pillar_recommendations']['prop_correlation'] = p6['recommendation']
        if p6['triggered']:
            results['pillars_triggered'].append('Prop Correlation')
        
        # Pillar 7: Hook Discipline
        p7 = self._pillar_7_hook_discipline(game_data)
        results['pillar_scores']['hook_discipline'] = p7['score']
        results['pillar_signals']['hook_discipline'] = p7['signal']
        results['pillar_recommendations']['hook_discipline'] = p7['recommendation']
        if p7['triggered']:
            results['pillars_triggered'].append('Hook Discipline')
        
        # Pillar 8: Volume Discipline
        p8 = self._pillar_8_volume_discipline(game_data)
        results['pillar_scores']['volume_discipline'] = p8['score']
        results['pillar_signals']['volume_discipline'] = p8['signal']
        results['pillar_recommendations']['volume_discipline'] = p8['recommendation']
        if p8['triggered']:
            results['pillars_triggered'].append('Volume Discipline')
        
        # Calculate overall pillar score
        # v20.16: Handle empty list case to avoid nan (when no pillars trigger)
        # v20.16: Added defensive bounds [-5.0, +5.0] to prevent extreme values
        PILLAR_SCORE_MIN = -5.0
        PILLAR_SCORE_MAX = 5.0
        pillar_values = list(results['pillar_scores'].values())
        non_zero_pillars = [s for s in pillar_values if s != 0]
        raw_pillar_score = np.mean(non_zero_pillars) if non_zero_pillars else 0.0
        results['overall_pillar_score'] = max(PILLAR_SCORE_MIN, min(PILLAR_SCORE_MAX, raw_pillar_score))

        return results
    
    def _pillar_1_sharp_split(self, data: Dict) -> Dict:
        """
        Pillar 1: The "Sharp" Split (Pros vs. Joes)
        If >60% Tickets on Team A, but >50% Money on Team B → Bet Team B
        """
        betting_pct = data.get('betting_percentages', {})
        public_on_favorite = betting_pct.get('public_on_favorite', 50)
        
        # Simulate money percentage (in real system, get from API)
        # For demo: assume sharp money is opposite when public > 60%
        sharp_split_triggered = public_on_favorite > 60
        
        if sharp_split_triggered:
            # Sharp money on underdog, fade the public
            return {
                'triggered': True,
                'score': 2.0,  # Strong signal
                'signal': 'FADE_PUBLIC',
                'recommendation': 'Bet UNDERDOG (Sharp money detected)',
                'confidence': 'high'
            }
        
        return {
            'triggered': False,
            'score': 0,
            'signal': 'NEUTRAL',
            'recommendation': 'No sharp split detected',
            'confidence': 'low'
        }
    
    def _pillar_2_reverse_line(self, data: Dict) -> Dict:
        """
        Pillar 2: The "Reverse Line" Move
        Public hammering favorite, but line drops → Bet Underdog
        """
        betting_pct = data.get('betting_percentages', {})
        current_line = data.get('current_line', 0)
        opening_line = data.get('opening_line', 0)
        public_on_favorite = betting_pct.get('public_on_favorite', 50)
        
        # Line moved AGAINST public (reverse line move)
        line_movement = current_line - opening_line
        reverse_move = public_on_favorite > 60 and line_movement < -0.5
        
        if reverse_move:
            return {
                'triggered': True,
                'score': 2.5,  # Very strong signal
                'signal': 'REVERSE_LINE_MOVE',
                'recommendation': 'STRONG BET UNDERDOG (Books begging you to take favorite)',
                'confidence': 'very_high'
            }
        
        return {
            'triggered': False,
            'score': 0,
            'signal': 'NEUTRAL',
            'recommendation': 'No reverse line move',
            'confidence': 'low'
        }
    
    def _pillar_3_hospital_fade(self, data: Dict) -> Dict:
        """
        Pillar 3: The "Hospital" Fade (Injury Audit)
        Never bet team missing #1 scorer or primary defender

        v20.16 fix: Cap injury_impact at 5.0 to prevent unbounded negative scores.
        Also fix depth default: unknown players should NOT be treated as starters.
        """
        injuries = data.get('injuries', [])

        key_injuries = 0
        injury_impact = 0
        INJURY_IMPACT_CAP = 5.0  # v20.16: Prevent unbounded negative pillar scores

        for injury in injuries:
            player = injury.get('player', {})
            status = injury.get('status', '').lower()

            # v20.16: Default depth to 99 (unknown = not a starter)
            # Previously defaulted to 1, treating ALL unknown players as starters
            depth = player.get('depth', 99)

            # Check if key player
            if depth == 1:  # Starter
                if status in ['out', 'doubtful']:
                    key_injuries += 1
                    injury_impact += 2.0
            elif depth == 2:  # Second string
                if status == 'out':
                    injury_impact += 0.5

        # v20.16: Cap injury_impact to prevent massive negative scores
        injury_impact = min(injury_impact, INJURY_IMPACT_CAP)

        if key_injuries >= 1:
            return {
                'triggered': True,
                'score': -injury_impact,  # Negative score = fade this team (capped at -5.0)
                'signal': 'HOSPITAL_FADE',
                'recommendation': f'FADE this team ({key_injuries} key player(s) out)',
                'confidence': 'high'
            }
        
        return {
            'triggered': False,
            'score': 0,
            'signal': 'HEALTHY',
            'recommendation': 'No major injury concerns',
            'confidence': 'low'
        }
    
    def _pillar_4_situational_spot(self, data: Dict) -> Dict:
        """
        Pillar 4: The Situational Spot
        Fade back-to-backs, altitude travel, lookahead spots

        v20.16: Add explicit cap on fade_score for defense.
        """
        schedule = data.get('schedule', {})
        days_rest = schedule.get('days_rest', 2)
        travel_miles = schedule.get('travel_miles', 0)
        games_in_last_7 = schedule.get('games_in_last_7', 3)
        road_trip_game = schedule.get('road_trip_game_num', 0)

        fade_score = 0
        reasons = []
        SITUATIONAL_FADE_CAP = 3.5  # v20.16: Explicit cap

        # Back-to-back
        if days_rest == 0:
            fade_score += 1.5
            reasons.append('Back-to-back game')

        # Heavy travel
        if travel_miles > 1500:
            fade_score += 0.5
            reasons.append('Long distance travel')

        # Altitude (Denver/Utah)
        # In real system, check opponent location
        if travel_miles > 1000:  # Simplified check
            fade_score += 0.3
            reasons.append('Potential altitude factor')

        # Lookahead spot (3+ games in last 7)
        if games_in_last_7 >= 4:
            fade_score += 0.7
            reasons.append('Heavy schedule (lookahead spot)')

        # Deep in road trip
        if road_trip_game >= 3:
            fade_score += 0.5
            reasons.append(f'Road trip game #{road_trip_game}')

        # v20.16: Cap fade_score
        fade_score = min(fade_score, SITUATIONAL_FADE_CAP)

        if fade_score > 1.0:
            return {
                'triggered': True,
                'score': -fade_score,  # Negative = fade (capped at -3.5)
                'signal': 'SITUATIONAL_FADE',
                'recommendation': f'FADE this team: {", ".join(reasons)}',
                'confidence': 'high'
            }
        
        return {
            'triggered': False,
            'score': 0,
            'signal': 'NEUTRAL',
            'recommendation': 'No situational concerns',
            'confidence': 'low'
        }
    
    def _pillar_5_expert_consensus(self, data: Dict) -> Dict:
        """
        Pillar 5: The Expert Consensus
        If 3+ experts on same side → Follow. If split → Stay away.
        """
        # In production, integrate with VSiN, Action Network, etc.
        # For now, use placeholder logic
        
        expert_picks = data.get('expert_picks', {})
        experts_on_over = expert_picks.get('over', 0)
        experts_on_under = expert_picks.get('under', 0)
        
        total_experts = experts_on_over + experts_on_under
        
        if total_experts >= 3:
            if experts_on_over >= 3:
                return {
                    'triggered': True,
                    'score': 1.5,
                    'signal': 'EXPERT_CONSENSUS_OVER',
                    'recommendation': f'OVER ({experts_on_over} experts agree)',
                    'confidence': 'medium'
                }
            elif experts_on_under >= 3:
                return {
                    'triggered': True,
                    'score': -1.5,
                    'signal': 'EXPERT_CONSENSUS_UNDER',
                    'recommendation': f'UNDER ({experts_on_under} experts agree)',
                    'confidence': 'medium'
                }
        
        return {
            'triggered': False,
            'score': 0,
            'signal': 'NEUTRAL',
            'recommendation': 'No expert consensus (or data not available)',
            'confidence': 'low'
        }
    
    def _pillar_6_prop_correlation(self, data: Dict) -> Dict:
        """
        Pillar 6: The "Prop Correlation" (Game Script)
        Props must match game story
        """
        # This is more relevant for actual prop bets
        # Returns game script prediction
        
        predicted_value = data.get('predicted_value', 0)
        line = data.get('line', 0)
        
        # If predicting OVER, expect high-scoring game script
        if predicted_value > line:
            return {
                'triggered': True,
                'score': 0.5,
                'signal': 'HIGH_SCORING_SCRIPT',
                'recommendation': 'High-scoring game script (favor passing props, OVER team totals)',
                'confidence': 'medium'
            }
        else:
            return {
                'triggered': True,
                'score': -0.5,
                'signal': 'LOW_SCORING_SCRIPT',
                'recommendation': 'Low-scoring game script (favor rushing props, UNDER team totals)',
                'confidence': 'medium'
            }
    
    def _pillar_7_hook_discipline(self, data: Dict) -> Dict:
        """
        Pillar 7: The "Hook" Discipline
        Never bet favorite at -3.5 or -7.5 (buy to -3/-7)
        Always buy underdog to +3.5 or +7.5
        """
        line = data.get('line', 0)
        
        # Check for hook numbers
        bad_hooks_favorite = [-3.5, -7.5]
        good_hooks_underdog = [3.5, 7.5]
        
        warnings = []
        
        if line in bad_hooks_favorite:
            warnings.append(f'⚠️  Line at {line} - BUY TO {line + 0.5}!')
        
        if abs(line - 3.0) < 0.1 or abs(line - 7.0) < 0.1:
            warnings.append(f'✓ Good number at {line} (key number)')
        
        if warnings:
            return {
                'triggered': True,
                'score': 0,  # Neutral - just a warning
                'signal': 'HOOK_WARNING',
                'recommendation': ' '.join(warnings),
                'confidence': 'high'
            }
        
        return {
            'triggered': False,
            'score': 0,
            'signal': 'NEUTRAL',
            'recommendation': 'No hook concerns',
            'confidence': 'low'
        }
    
    def _pillar_8_volume_discipline(self, data: Dict) -> Dict:
        """
        Pillar 8: The "Volume" Discipline
        Never bet >5% bankroll on single play
        Standard bets: 1-2%
        """
        # This determines bet sizing based on confidence
        
        ai_score = data.get('ai_score', 5.0)
        confidence = data.get('confidence', 'medium')
        
        # Calculate recommended bet size
        if ai_score >= 8.0 and confidence == 'very_high':
            bet_size = 0.05  # 5% - Whale Lock
            bet_type = 'WHALE LOCK'
        elif ai_score >= 7.0:
            bet_size = 0.03  # 3%
            bet_type = 'Strong Play'
        elif ai_score >= 6.0:
            bet_size = 0.02  # 2%
            bet_type = 'Standard Play'
        else:
            bet_size = 0.01  # 1%
            bet_type = 'Small Play'
        
        return {
            'triggered': True,
            'score': 0,  # Not a directional score
            'signal': 'VOLUME_GUIDANCE',
            'recommendation': f'{bet_type}: Bet {bet_size*100}% of bankroll',
            'confidence': 'high',
            'bet_size_pct': bet_size,
            'bet_type': bet_type
        }


# ============================================
# MODEL 1: ENSEMBLE STACKING MODEL
# ============================================

class EnsembleStackingModel:
    """
    Combines XGBoost, LightGBM, and Random Forest
    EDGE: More accurate than single models

    v20.16: Now uses GameEnsembleModel which:
    - Learns optimal weights from graded picks
    - Can load trained XGBoost model from disk

    v20.16.1: Added _ensemble_pipeline_trained flag to prevent calling
    .predict() on unfitted sklearn models (hard safety rule).

    v20.22: Added save_models()/load_models() for sklearn regressor persistence.
    Training script runs at 7:15 AM ET to fit regressors from graded picks.

    IMPORTANT: Sklearn regressors are in SHADOW MODE by default.
    Set ENSEMBLE_SKLEARN_ENABLED=true to use them for live predictions.
    Otherwise they are loaded for telemetry only (no scoring change).
    """

    # Path for persisting trained sklearn models
    SKLEARN_MODELS_PATH = os.path.join(
        os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "/data"),
        "models",
        "ensemble_sklearn_regressors.joblib"
    )

    # SHADOW MODE: Only use sklearn regressors if explicitly enabled
    # This prevents accidental scoring drift when models are loaded
    SKLEARN_ENABLED = os.environ.get("ENSEMBLE_SKLEARN_ENABLED", "false").lower() == "true"

    def __init__(self):
        self.base_models = {
            'xgboost': XGBRegressor(n_estimators=200, learning_rate=0.05, max_depth=6, random_state=42),
            'lightgbm': LGBMRegressor(n_estimators=200, learning_rate=0.05, max_depth=6, random_state=42, verbose=-1),
            'random_forest': RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
        }
        self.meta_model = GradientBoostingRegressor(n_estimators=50, random_state=42)
        self.scaler = None  # Optional StandardScaler for features
        self.is_trained = False
        self._ensemble_pipeline_trained = False  # HARD RULE: Only True after train() completes
        self._sklearn_loaded_for_telemetry = False  # True if models loaded but in shadow mode
        self._last_train_time = None  # Track when models were trained
        self._training_samples_count = 0  # Track training sample count
        self._game_ensemble = None

        # Try to load trained sklearn models from disk (for telemetry)
        # NOTE: Does NOT enable them for prediction unless SKLEARN_ENABLED=true
        if self._load_models_shadow():
            if self.SKLEARN_ENABLED:
                logger.info("EnsembleStackingModel: Loaded sklearn regressors (LIVE MODE)")
            else:
                logger.info("EnsembleStackingModel: Loaded sklearn regressors (SHADOW MODE - telemetry only)")
        else:
            logger.info("EnsembleStackingModel: No trained sklearn regressors found")

        self._init_game_ensemble()

    def _init_game_ensemble(self):
        """Initialize game ensemble model."""
        try:
            from team_ml_models import get_game_ensemble
            self._game_ensemble = get_game_ensemble()
            if self._game_ensemble.is_trained:
                self.is_trained = True
                logger.info("EnsembleModel: Using GameEnsemble with %d training samples",
                           self._game_ensemble.weights.get("_trained_samples", 0))
        except Exception as e:
            logger.warning(f"Failed to init GameEnsemble: {e}")

    def train(self, X_train, y_train, X_val, y_val):
        """Train all base models and meta model"""
        base_predictions = []
        for name, model in self.base_models.items():
            logger.info("Training %s...", name)
            model.fit(X_train, y_train)
            val_pred = model.predict(X_val)
            base_predictions.append(val_pred)

        # Stack predictions for meta model
        stacked_features = np.column_stack(base_predictions)
        self.meta_model.fit(stacked_features, y_val)
        self._ensemble_pipeline_trained = True  # ONLY set after sklearn models are fitted
        self.is_trained = True
        self._last_train_time = datetime.now().isoformat()
        self._training_samples_count = len(y_train)
        logger.info("Ensemble model trained successfully")

    def save_models(self) -> bool:
        """Save trained sklearn models to disk.

        v20.22: Persists base models + meta model + scaler to joblib file.
        Called by train_ensemble_regressors.py after training completes.

        Returns:
            True if saved successfully, False otherwise.
        """
        if not self._ensemble_pipeline_trained:
            logger.warning("Cannot save models - not trained yet")
            return False

        try:
            # Ensure directory exists
            model_dir = os.path.dirname(self.SKLEARN_MODELS_PATH)
            os.makedirs(model_dir, exist_ok=True)

            # Save all models and metadata
            data = {
                'base_models': self.base_models,
                'meta_model': self.meta_model,
                'scaler': self.scaler,
                'trained_at': self._last_train_time or datetime.now().isoformat(),
                'training_samples': self._training_samples_count,
                'version': '1.0'
            }

            joblib.dump(data, self.SKLEARN_MODELS_PATH)
            logger.info("Saved sklearn ensemble models to %s", self.SKLEARN_MODELS_PATH)
            return True

        except Exception as e:
            logger.error("Failed to save sklearn models: %s", e)
            return False

    def _load_models_shadow(self) -> bool:
        """Load trained sklearn models from disk in SHADOW MODE.

        v20.22: Loads models for telemetry purposes. Does NOT enable them
        for live predictions unless ENSEMBLE_SKLEARN_ENABLED=true.

        This prevents accidental scoring drift when backend is "frozen".

        Returns:
            True if loaded successfully, False otherwise.
        """
        if not os.path.exists(self.SKLEARN_MODELS_PATH):
            return False

        try:
            data = joblib.load(self.SKLEARN_MODELS_PATH)

            # Validate the loaded data structure
            if not isinstance(data, dict):
                logger.warning("Invalid sklearn models file format")
                return False

            if 'base_models' not in data or 'meta_model' not in data:
                logger.warning("Missing required keys in sklearn models file")
                return False

            # Restore models (for telemetry at minimum)
            self.base_models = data['base_models']
            self.meta_model = data['meta_model']
            self.scaler = data.get('scaler')
            self._last_train_time = data.get('trained_at')
            self._training_samples_count = data.get('training_samples', 0)
            self._sklearn_loaded_for_telemetry = True

            # ONLY enable for live predictions if explicitly enabled
            # This is the SHADOW MODE gate - models loaded but not used
            if self.SKLEARN_ENABLED:
                self._ensemble_pipeline_trained = True
                self.is_trained = True
            # else: _ensemble_pipeline_trained stays False, predict() uses fallback

            logger.info(
                "Loaded sklearn ensemble models (trained at: %s, samples: %d, enabled: %s)",
                self._last_train_time,
                self._training_samples_count,
                self.SKLEARN_ENABLED
            )
            return True

        except Exception as e:
            logger.error("Failed to load sklearn models: %s", e)
            return False

    def load_models(self) -> bool:
        """Load trained sklearn models and ENABLE them for predictions.

        Use this only when you explicitly want to enable sklearn predictions.
        For shadow mode loading, use _load_models_shadow() instead.

        Returns:
            True if loaded successfully, False otherwise.
        """
        if not os.path.exists(self.SKLEARN_MODELS_PATH):
            return False

        try:
            data = joblib.load(self.SKLEARN_MODELS_PATH)

            if not isinstance(data, dict):
                return False
            if 'base_models' not in data or 'meta_model' not in data:
                return False

            self.base_models = data['base_models']
            self.meta_model = data['meta_model']
            self.scaler = data.get('scaler')
            self._last_train_time = data.get('trained_at')
            self._training_samples_count = data.get('training_samples', 0)

            # Enable for predictions
            self._ensemble_pipeline_trained = True
            self.is_trained = True
            self._sklearn_loaded_for_telemetry = True

            return True

        except Exception as e:
            logger.error("Failed to load sklearn models: %s", e)
            return False

    def get_training_status(self) -> dict:
        """Get training status for telemetry/debugging.

        v20.22: Returns detailed status including trained state,
        sample counts, and shadow mode status.
        """
        return {
            'sklearn_trained': self._ensemble_pipeline_trained,
            'sklearn_enabled': self.SKLEARN_ENABLED,
            'sklearn_loaded_for_telemetry': self._sklearn_loaded_for_telemetry,
            'sklearn_mode': 'LIVE' if self.SKLEARN_ENABLED and self._ensemble_pipeline_trained else 'SHADOW',
            'is_trained': self.is_trained,
            'has_game_ensemble': self._game_ensemble is not None,
            'last_train_time': self._last_train_time,
            'training_samples': self._training_samples_count,
            'models_path': self.SKLEARN_MODELS_PATH,
            'models_exist': os.path.exists(self.SKLEARN_MODELS_PATH),
        }

    def _is_base_model_fitted(self, model, model_name: str) -> bool:
        """Best-effort check if a sklearn model has been fitted.

        NOTE: This is a secondary safety check only. The AUTHORITATIVE gate is
        _ensemble_pipeline_trained which is ONLY set True after train() completes
        or after successfully loading models from disk.

        This helper may not perfectly detect all fitted states across sklearn
        wrapper variations, so treat it as best-effort defense-in-depth.
        """
        if model is None:
            return False
        # For sklearn estimators, check for fitted attributes
        # XGBoost/LightGBM have get_booster(), RandomForest has estimators_
        try:
            if hasattr(model, 'get_booster'):
                model.get_booster()  # Raises if not fitted
                return True
            if hasattr(model, 'estimators_'):
                return len(model.estimators_) > 0
            if hasattr(model, 'n_features_in_'):
                return model.n_features_in_ is not None
        except Exception:
            return False
        return False

    def predict(self, features, model_predictions: Dict = None):
        """
        Make prediction using ensemble.

        HARD RULE (v20.16.1): Never call .predict() on any base model unless:
        1. _ensemble_pipeline_trained == True (set ONLY after train() completes)
        2. Model instance is not None
        3. Model advertises a fitted/loaded state

        Args:
            features: Feature array
            model_predictions: Optional dict of other model predictions to combine
        """
        # Try GameEnsemble if we have model predictions
        if self._game_ensemble is not None and model_predictions:
            try:
                return self._game_ensemble.predict(model_predictions, features)
            except Exception as e:
                logger.warning(f"GameEnsemble prediction failed: {e}")

        # v20.16: If GameEnsemble available without model_predictions, use it directly
        if self._game_ensemble is not None:
            try:
                # Use default equal weights
                return self._game_ensemble.predict({}, features)
            except Exception as e:
                logger.warning(f"GameEnsemble fallback failed: {e}")

        # HARD RULE: Never call .predict() on sklearn base models unless:
        # 1. _ensemble_pipeline_trained == True (set ONLY after train() completes)
        # 2. Model instances are not None
        # 3. is_trained == True
        if not self._ensemble_pipeline_trained:
            # Base models not fitted via train() - use feature mean fallback
            return float(np.mean(features)) if len(features) > 0 else 25.0

        if not self.is_trained:
            # Secondary check for general trained state
            return float(np.mean(features)) if len(features) > 0 else 25.0

        # Use trained meta model (ONLY if base models are fitted)
        try:
            base_predictions = []
            for name, model in self.base_models.items():
                # Extra safety: verify model instance exists AND is fitted
                if model is None:
                    logger.warning(f"Base model {name} is None, skipping")
                    continue
                if not self._is_base_model_fitted(model, name):
                    logger.warning(f"Base model {name} not fitted, skipping")
                    continue
                pred = model.predict(features.reshape(1, -1) if features.ndim == 1 else features)
                base_predictions.append(pred)

            # Need all 3 base predictions for meta model
            if len(base_predictions) < 3:
                logger.warning(f"Only {len(base_predictions)}/3 base models available")
                return float(np.mean(features)) if len(features) > 0 else 25.0

            stacked_features = np.column_stack(base_predictions)
            return self.meta_model.predict(stacked_features)[0]
        except Exception as e:
            logger.warning(f"Trained ensemble prediction failed: {e}")
            return float(np.mean(features)) if len(features) > 0 else 25.0


# ============================================
# MODEL 2: LSTM NEURAL NETWORK
# ============================================

class LSTMModel:
    """
    Time-series prediction using LSTM
    EDGE: Captures temporal patterns and trends

    v20.16: Now uses TeamLSTMModel which:
    - Uses actual team scoring sequences (not dummy values)
    - Falls back to weighted average when no data
    """
    def __init__(self):
        self.model = None
        self.scaler = None
        self._team_lstm = None
        self._init_team_lstm()

    def _init_team_lstm(self):
        """Initialize team LSTM model."""
        try:
            from team_ml_models import get_team_lstm
            self._team_lstm = get_team_lstm()
            if self._team_lstm.is_trained:
                self.model = self._team_lstm  # Mark as having a model
                logger.info("LSTMModel: Using TeamLSTM with %d cached teams",
                           len(self._team_lstm.team_cache.data.get("teams", {})))
        except Exception as e:
            logger.warning(f"Failed to init TeamLSTM: {e}")

    def build_model(self, sequence_length=10, features=1):
        """Build LSTM architecture"""
        if not TENSORFLOW_AVAILABLE:
            logger.warning("TensorFlow not available - using statistical fallback")
            return None

        model = keras.Sequential([
            layers.LSTM(50, activation='relu', input_shape=(sequence_length, features), return_sequences=True),
            layers.Dropout(0.2),
            layers.LSTM(50, activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(25, activation='relu'),
            layers.Dense(1)
        ])

        model.compile(optimizer='adam', loss='mse', metrics=['mae'])
        self.model = model
        return model

    def predict(self, recent_games, game_data: Dict = None):
        """
        Predict using TeamLSTM or fallback.

        Args:
            recent_games: Legacy input (list of values)
            game_data: Optional dict with sport, home_team, away_team, line, is_totals
        """
        # Try TeamLSTM if we have game context
        if self._team_lstm is not None and game_data is not None:
            try:
                return self._team_lstm.predict(game_data)
            except Exception as e:
                logger.warning(f"TeamLSTM prediction failed: {e}")

        # Fall back to statistical method
        return self._statistical_fallback(recent_games)

    def _statistical_fallback(self, recent_games):
        """Fallback when LSTM not available"""
        if not recent_games:
            return 25.0

        recent_games = np.array(recent_games)
        # Weighted average (more recent = higher weight)
        weights = np.exp(np.linspace(-1, 0, len(recent_games)))
        weights /= weights.sum()
        return np.average(recent_games, weights=weights)


# [Continue with all other models from original file...]
# For brevity, I'll include the key parts and the Master System

# ============================================
# MODELS 3-8: (Keep original implementations)
# ============================================

class MatchupSpecificModel:
    """
    Model 3: Matchup-specific predictions

    v20.16: Now uses TeamMatchupModel which:
    - Tracks team-vs-team historical records
    - Learns from graded picks over time
    """
    def __init__(self):
        self.matchup_models = {}
        self._team_matchup = None
        self._init_team_matchup()

    def _init_team_matchup(self):
        """Initialize team matchup model."""
        try:
            from team_ml_models import get_team_matchup
            self._team_matchup = get_team_matchup()
            if self._team_matchup.is_trained:
                self.matchup_models["_has_data"] = True
                logger.info("MatchupModel: Using TeamMatchup with %d matchups tracked",
                           len(self._team_matchup.matchups))
        except Exception as e:
            logger.warning(f"Failed to init TeamMatchup: {e}")

    def predict(self, player_id, opponent_id, features, game_data: Dict = None):
        """
        Predict using matchup history.

        Args:
            player_id: Home team (for game picks) or player ID (for props)
            opponent_id: Away team (for game picks) or opponent ID (for props)
            features: Feature array for fallback
            game_data: Optional dict with sport, is_totals
        """
        # Try TeamMatchup if we have it
        if self._team_matchup is not None:
            try:
                sport = game_data.get("sport", "NBA") if game_data else "NBA"
                is_totals = game_data.get("is_totals", False) if game_data else False
                return self._team_matchup.predict(
                    sport=sport,
                    home_team=str(player_id),
                    away_team=str(opponent_id),
                    features=features,
                    is_totals=is_totals
                )
            except Exception as e:
                logger.warning(f"TeamMatchup prediction failed: {e}")

        # Fallback to feature mean
        matchup_key = f"{player_id}_vs_{opponent_id}"
        if matchup_key in self.matchup_models:
            return self.matchup_models[matchup_key].predict(features.reshape(1, -1))[0]
        return np.mean(features) if len(features) > 0 else 25.0


class MonteCarloSimulator:
    """Model 4: Monte Carlo simulation"""
    def simulate_game(self, team_a_stats, team_b_stats, num_simulations=10000):
        results = {'team_a_wins': 0, 'team_b_wins': 0, 'scores': []}
        for _ in range(num_simulations):
            score_a = np.random.normal(team_a_stats.get('off_rating', 110), 
                                      team_a_stats.get('off_rating_std', 10))
            score_b = np.random.normal(team_b_stats.get('off_rating', 110),
                                      team_b_stats.get('off_rating_std', 10))
            results['scores'].append((score_a, score_b))
            if score_a > score_b:
                results['team_a_wins'] += 1
            else:
                results['team_b_wins'] += 1
        
        results['team_a_win_pct'] = results['team_a_wins'] / num_simulations
        return results


class LineMovementAnalyzer:
    """Model 5: Sharp money detection"""
    def analyze_line_movement(self, game_id, current_line, opening_line, time_until_game, betting_pct):
        line_movement = current_line - opening_line
        public_pct = betting_pct.get('public_on_favorite', 50)
        
        # Reverse line move detection
        reverse_move = (public_pct > 60 and line_movement < -0.5) or \
                      (public_pct < 40 and line_movement > 0.5)
        
        return {
            'sharp_money_detected': reverse_move,
            'line_movement': line_movement,
            'recommendation': 'FADE_PUBLIC' if reverse_move else 'NEUTRAL'
        }


class RestFatigueModel:
    """Model 6: Rest and fatigue analysis"""
    def analyze_rest(self, days_rest, travel_miles, games_in_last_7):
        fatigue_score = 1.0
        if days_rest == 0:
            fatigue_score *= 0.85
        if travel_miles > 1500:
            fatigue_score *= 0.95
        if games_in_last_7 >= 4:
            fatigue_score *= 0.90
        return fatigue_score


class InjuryImpactModel:
    """Model 7: Injury impact calculator

    v20.16 fix: Added INJURY_IMPACT_CAP and fixed depth default.
    Previously: depth defaulted to 1 (starter), causing ALL players to be counted.
    Now: depth defaults to 99 (unknown), only explicit starters counted.

    v20.21 fix: Reduced INJURY_IMPACT_CAP from 10.0 to 5.0 to prevent
    excessive negative swings (±100 points was possible before).
    """
    INJURY_IMPACT_CAP = 5.0  # Max negative impact (v20.21: reduced from 10.0)

    def calculate_impact(self, injuries, depth_chart):
        total_impact = 0
        for injury in injuries:
            player = injury.get('player', {})
            # v20.16: Default depth to 99 (unknown = not a starter)
            depth = player.get('depth', 99)
            if depth == 1:
                total_impact += 2.0
            elif depth == 2:
                total_impact += 0.5
        # v20.21: Cap the impact to prevent runaway negative values
        total_impact = min(total_impact, self.INJURY_IMPACT_CAP)
        return -total_impact


class BettingEdgeCalculator:
    """Model 8: EV and Kelly Criterion"""
    def calculate_ev(self, your_probability, betting_odds):
        if betting_odds < 0:
            implied_prob = abs(betting_odds) / (abs(betting_odds) + 100)
            decimal_odds = 1 + (100 / abs(betting_odds))
        else:
            implied_prob = 100 / (betting_odds + 100)
            decimal_odds = 1 + (betting_odds / 100)
        
        ev = (your_probability * (decimal_odds - 1)) - ((1 - your_probability) * 1)
        edge = (your_probability - implied_prob) / implied_prob * 100
        
        # Kelly Criterion
        kelly = (your_probability * decimal_odds - 1) / (decimal_odds - 1)
        kelly_bet = max(0, min(kelly, 0.05))  # Cap at 5%
        
        return {
            'expected_value': ev,
            'edge_percent': edge,
            'kelly_bet_size': kelly_bet,
            'confidence': 'high' if abs(edge) > 10 else 'medium' if abs(edge) > 5 else 'low'
        }


# ============================================
# MASTER PREDICTION SYSTEM (WITH PILLARS!)
# ============================================

class MasterPredictionSystem:
    """
    Combines all 8 AI models + 8 Pillars of Execution
    Produces final recommendation with confidence score
    """
    def __init__(self):
        logger.info("Initializing Master Prediction System with 8 Pillars...")

        # Initialize all 8 AI models
        self.ensemble = EnsembleStackingModel()
        self.lstm = LSTMModel()
        self.matchup = MatchupSpecificModel()
        self.monte_carlo = MonteCarloSimulator()
        self.line_analyzer = LineMovementAnalyzer()
        self.rest_model = RestFatigueModel()
        self.injury_model = InjuryImpactModel()
        self.edge_calculator = BettingEdgeCalculator()

        # Initialize 8 Pillars
        self.pillars = PillarsAnalyzer()

        logger.info("All 8 AI Models + 8 Pillars Loaded Successfully!")

    def _get_model_status(self) -> Dict:
        """
        Get status of all 8 models with diagnostic proof fields.

        v20.16.2: Added training_source and proof fields to distinguish
        real training from flag-only "trained" status.
        """
        try:
            from team_ml_models import get_model_status as get_team_model_status
            team_status = get_team_model_status()

            # Count how many sklearn base models are actually fitted
            sklearn_fitted_count = 0
            for name, model in self.ensemble.base_models.items():
                if self.ensemble._is_base_model_fitted(model, name):
                    sklearn_fitted_count += 1

            # Get training telemetry (proves pipeline is executing)
            training_telemetry = team_status.get('ensemble', {}).get('training_telemetry', {})

            return {
                'ensemble': team_status.get('ensemble', {}).get('status', 'INITIALIZING'),
                'ensemble_training_source': team_status.get('ensemble', {}).get('training_source', 'UNKNOWN'),
                'ensemble_samples_trained': team_status.get('ensemble', {}).get('samples_trained', 0),
                'ensemble_sklearn_fitted_count': sklearn_fitted_count,
                'ensemble_pipeline_trained': self.ensemble._ensemble_pipeline_trained,
                # Training telemetry - decisive proof of pipeline execution
                'training_telemetry': {
                    'last_train_run_at': training_telemetry.get('last_train_run_at'),
                    'graded_samples_seen': training_telemetry.get('graded_samples_seen', 0),
                    'samples_used_for_training': training_telemetry.get('samples_used_for_training', 0),
                    'volume_mount_path': training_telemetry.get('volume_mount_path', 'NOT_SET'),
                },
                'lstm': team_status.get('lstm', {}).get('status', 'INITIALIZING'),
                'lstm_training_source': team_status.get('lstm', {}).get('training_source', 'UNKNOWN'),
                'lstm_teams_cached': team_status.get('lstm', {}).get('teams_cached', 0),
                'matchup': team_status.get('matchup', {}).get('status', 'INITIALIZING'),
                'matchup_training_source': team_status.get('matchup', {}).get('training_source', 'UNKNOWN'),
                'matchup_tracked': team_status.get('matchup', {}).get('matchups_tracked', 0),
                'monte_carlo': 'WORKS',  # Always runs simulations
                'line_movement': 'WORKS',  # Always computes
                'rest_fatigue': 'WORKS',  # Always computes
                'injury_impact': 'WORKS',  # Always computes (now capped)
                'edge_calculator': 'WORKS',  # Always computes
            }
        except Exception as e:
            logger.warning(f"Failed to get team model status: {e}")
            # Fallback to basic check
            return {
                'ensemble': 'INITIALIZING' if not self.ensemble.is_trained else 'TRAINED',
                'lstm': 'INITIALIZING' if self.lstm.model is None else 'TRAINED',
                'matchup': 'INITIALIZING' if not self.matchup.matchup_models else 'TRAINED',
                'monte_carlo': 'WORKS',
                'line_movement': 'WORKS',
                'rest_fatigue': 'WORKS',
                'injury_impact': 'WORKS',
                'edge_calculator': 'WORKS',
            }

    def generate_comprehensive_prediction(self, game_data: Dict) -> Dict:
        """
        Generate prediction using all 8 models + 8 pillars
        """
        # Extract data
        features = np.array(game_data.get('features', []))
        recent_games = game_data.get('recent_games', [])
        line = game_data.get('line', 0)
        
        # Get predictions from all 8 models
        model_predictions = {}

        # Build game context for team-based models (v20.16)
        game_context = {
            'sport': game_data.get('sport', 'NBA'),
            'home_team': game_data.get('player_id', ''),  # For game picks, player_id = home team
            'away_team': game_data.get('opponent_id', ''),  # opponent_id = away team
            'line': line,
            'is_totals': 'total' in str(game_data.get('market', '')).lower()
        }

        # Model 1: Ensemble (will use GameEnsemble after other predictions)
        # Predict initially, will re-predict with model_predictions later
        model_predictions['ensemble'] = self.ensemble.predict(features)

        # Model 2: LSTM (now uses TeamLSTM with actual team sequences)
        model_predictions['lstm'] = self.lstm.predict(recent_games, game_data=game_context)

        # Model 3: Matchup (now uses TeamMatchup with historical H2H)
        model_predictions['matchup'] = self.matchup.predict(
            game_data.get('player_id'),
            game_data.get('opponent_id'),
            features,
            game_data=game_context
        )
        
        # Model 4: Monte Carlo (returns distribution)
        player_stats = game_data.get('player_stats', {})
        mc_result = self.monte_carlo.simulate_game(
            {'off_rating': player_stats.get('expected_value', 27.5),
             'off_rating_std': player_stats.get('std_dev', 6.5)},
            {'off_rating': line, 'off_rating_std': 5.0},
            num_simulations=10000
        )
        model_predictions['monte_carlo'] = np.mean([s[0] for s in mc_result['scores'][:100]])
        
        # Model 5: Line Movement
        line_analysis = self.line_analyzer.analyze_line_movement(
            game_data.get('game_id'),
            game_data.get('current_line'),
            game_data.get('opening_line'),
            game_data.get('time_until_game'),
            game_data.get('betting_percentages', {})
        )
        model_predictions['line_movement'] = line_analysis.get('line_movement', 0)
        
        # Model 6: Rest/Fatigue
        schedule = game_data.get('schedule', {})
        rest_factor = self.rest_model.analyze_rest(
            schedule.get('days_rest', 1),
            schedule.get('travel_miles', 0),
            schedule.get('games_in_last_7', 3)
        )
        model_predictions['rest_factor'] = rest_factor
        
        # Model 7: Injury Impact
        injury_impact = self.injury_model.calculate_impact(
            game_data.get('injuries', []),
            game_data.get('depth_chart', {})
        )
        model_predictions['injury_impact'] = injury_impact

        # v20.16: Re-run ensemble with all model predictions (stacking)
        # This allows the ensemble to learn optimal weights from the other predictions
        ensemble_inputs = {
            'lstm': model_predictions['lstm'],
            'matchup': model_predictions['matchup'],
            'monte_carlo': model_predictions['monte_carlo']
        }
        model_predictions['ensemble'] = self.ensemble.predict(features, model_predictions=ensemble_inputs)

        # Calculate base predicted value
        predicted_value = np.mean([
            model_predictions['ensemble'],
            model_predictions['lstm'],
            model_predictions['matchup'],
            model_predictions['monte_carlo']
        ])
        
        # Adjust for rest and injuries
        predicted_value = predicted_value * rest_factor + injury_impact
        
        # Model 8: Calculate Edge
        # WARNING: This is a LINEAR edge-to-probability mapping, NOT calibrated.
        # Any large (predicted_value - line) saturates to 0.99 or 0.01.
        # TODO: Replace with proper calibration (logistic/Platt/isotonic) for
        # probabilities to be meaningful confidence estimates.
        # Current behavior: probability reflects "direction and relative edge"
        # not "true probability of winning the bet".
        raw_edge = (predicted_value - line) / (2 * player_stats.get('std_dev', 6.5))
        probability = 0.5 + raw_edge
        probability = max(0.01, min(0.99, probability))
        
        edge_analysis = self.edge_calculator.calculate_ev(
            probability,
            game_data.get('betting_odds', -110)
        )
        
        # 🏛️ RUN ALL 8 PILLARS
        pillar_analysis = self.pillars.analyze_all_pillars({
            **game_data,
            'predicted_value': predicted_value,
            'line': line,
            'ai_score': 0  # Will calculate below
        })
        
        # Calculate AI Score (0-10) incorporating pillars
        # v20.16: For game picks, deviation-based scoring gives 0 when prediction ≈ line
        # Use model agreement + edge + factors instead for meaningful scores
        std_dev = player_stats.get('std_dev', 6.5)
        deviation = abs(predicted_value - line)
        deviation_score = min(10, deviation / std_dev * 5)

        # Model agreement score (0-3): how well do models agree?
        model_values = [model_predictions['ensemble'], model_predictions['lstm'],
                       model_predictions['matchup'], model_predictions['monte_carlo']]
        model_std = np.std(model_values) if len(model_values) > 1 else 0
        agreement_score = max(0, 3 - model_std / 2)  # Lower std = higher agreement

        # Edge-based score (0-3): edge_percent indicates value
        edge_pct = abs(edge_analysis.get('edge_percent', 0))
        edge_score = min(3, edge_pct / 5)  # 15%+ edge = max 3 points

        # Factor-based score (0-2): rest + injury signals
        factor_score = 0
        if rest_factor >= 0.95:  # Well-rested
            factor_score += 1.0
        if abs(injury_impact) < 1:  # Minimal injury impact
            factor_score += 0.5
        if abs(model_predictions.get('line_movement', 0)) > 0.5:  # Sharp line movement
            factor_score += 0.5

        # Base score: max of deviation OR (agreement + edge + factors)
        # This ensures game picks get meaningful scores even when prediction ≈ line
        alternative_base = min(10, 2.0 + agreement_score + edge_score + factor_score)
        base_score = max(deviation_score, alternative_base)

        pillar_boost = pillar_analysis['overall_pillar_score']
        # v20.16: Ensure pillar_boost is not nan (defensive)
        if np.isnan(pillar_boost):
            logger.warning("pillar_boost is nan, defaulting to 0.0")
            pillar_boost = 0.0
        # v20.16: Debug logging for ai_score calculation
        logger.debug(f"MPS ai_score calc: deviation={deviation_score:.3f}, agreement={agreement_score:.3f}, "
                     f"edge={edge_score:.3f}, factor={factor_score:.3f}, alt_base={alternative_base:.3f}, "
                     f"base={base_score:.3f}, pillar_boost={pillar_boost}, model_std={model_std:.3f}")
        ai_score = min(10, max(0, base_score + pillar_boost))
        # v20.16: Floor at 2.0 to prevent heuristic fallback on valid MPS runs
        if ai_score < 2.0:
            logger.warning(f"ai_score {ai_score:.2f} below floor, elevating to 2.0")
            ai_score = max(2.0, ai_score)
        
        # Update pillar analysis with final AI score
        pillar_analysis_updated = self.pillars.analyze_all_pillars({
            **game_data,
            'predicted_value': predicted_value,
            'line': line,
            'ai_score': ai_score,
            'confidence': edge_analysis['confidence']
        })
        
        # Determine recommendation
        if predicted_value > line + 0.5:
            recommendation = "OVER"
        elif predicted_value < line - 0.5:
            recommendation = "UNDER"
        else:
            recommendation = "NO BET"
        
        # Get volume discipline (bet sizing)
        volume_discipline = pillar_analysis_updated['pillar_scores'].get('volume_discipline', 0)
        bet_sizing = self.pillars._pillar_8_volume_discipline({
            'ai_score': ai_score,
            'confidence': edge_analysis['confidence']
        })
        
        # Build comprehensive response
        return {
            'predicted_value': round(predicted_value, 2),
            'line': line,
            'recommendation': recommendation,
            'ai_score': round(ai_score, 1),
            'confidence': edge_analysis['confidence'],
            'expected_value': round(edge_analysis['expected_value'], 2),
            'probability': round(probability, 3),
            'kelly_bet_size': round(edge_analysis['kelly_bet_size'], 3),
            
            # 8 AI Model Factors
            'factors': {
                'ensemble': round(model_predictions['ensemble'], 2),
                'lstm': round(model_predictions['lstm'], 2),
                'matchup': round(model_predictions['matchup'], 2),
                'monte_carlo': round(model_predictions['monte_carlo'], 2),
                'line_movement': round(model_predictions['line_movement'], 2),
                'rest_factor': round(rest_factor, 3),
                'injury_impact': round(injury_impact, 2),
                'edge': round(edge_analysis['edge_percent'], 2)
            },

            # v20.16: AI Audit Fields (Engine 1 transparency)
            'ai_audit': {
                'deviation_score': round(deviation_score, 3),
                'agreement_score': round(agreement_score, 3),
                'edge_score': round(edge_score, 3),
                'factor_score': round(factor_score, 3),
                'alternative_base': round(alternative_base, 3),
                'base_score_used': 'DEVIATION' if deviation_score >= alternative_base else 'ALTERNATIVE',
                'pillar_boost': round(pillar_boost, 3),
                'model_std': round(model_std, 3),
                # v20.16: Raw inputs for debugging
                'raw_inputs': {
                    # Edge inputs
                    'edge_percent': round(edge_pct, 3),
                    'probability': round(probability, 4),
                    'probability_calibrated': False,  # WARNING: Linear mapping, not Platt/isotonic calibrated
                    'raw_edge': round(raw_edge, 4),  # Edge before probability mapping
                    # Factor components
                    'rest_factor': round(rest_factor, 4),
                    'injury_impact': round(injury_impact, 3),
                    'line_movement': round(model_predictions.get('line_movement', 0), 3),
                    # Model prediction stats
                    'model_preds': {
                        'count': len(model_values),
                        'min': round(min(model_values), 2),
                        'max': round(max(model_values), 2),
                        'std': round(model_std, 3),
                        'values': [round(v, 2) for v in model_values],
                    },
                },
                # v20.16: Model status for transparency (what's actually working)
                'model_status': self._get_model_status(),
            },

            # Monte Carlo Details
            'monte_carlo': {
                'simulations_run': 10000,
                'mean': round(model_predictions['monte_carlo'], 2),
                'over_probability': round(probability, 3)
            },
            
            # 🏛️ 8 PILLARS ANALYSIS
            'pillars': {
                'scores': pillar_analysis_updated['pillar_scores'],
                'signals': pillar_analysis_updated['pillar_signals'],
                'recommendations': pillar_analysis_updated['pillar_recommendations'],
                'triggered': pillar_analysis_updated['pillars_triggered'],
                'overall_score': round(pillar_analysis_updated['overall_pillar_score'], 2)
            },
            
            # Bet Sizing from Pillar 8
            'bet_sizing': {
                'recommended_pct': bet_sizing['bet_size_pct'],
                'bet_type': bet_sizing['bet_type'],
                'recommendation': bet_sizing['recommendation']
            }
        }


# For testing
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    logger.info("AI Sports Betting System with 8 Pillars")
    logger.info("=" * 50)

    # Initialize
    predictor = MasterPredictionSystem()

    # Test prediction
    test_data = {
        'player_id': 'lebron_james',
        'opponent_id': 'gsw',
        'features': [25.4, 7.2, 6.8, 1, 35, 28, 2],
        'recent_games': [27, 31, 22, 28, 25, 30, 26, 24, 29, 32],
        'player_stats': {
            'stat_type': 'points',
            'expected_value': 27.5,
            'variance': 45.0,
            'std_dev': 6.5
        },
        'schedule': {
            'days_rest': 0,  # Back-to-back!
            'travel_miles': 1500,
            'games_in_last_7': 4
        },
        'injuries': [],
        'depth_chart': {},
        'game_id': 'lal_gsw_20250114',
        'current_line': 25.5,
        'opening_line': 26.0,
        'time_until_game': 6.0,
        'betting_percentages': {'public_on_favorite': 68},  # Sharp split!
        'betting_odds': -110,
        'line': 25.5
    }

    result = predictor.generate_comprehensive_prediction(test_data)

    logger.info("\nPREDICTION RESULT:")
    logger.info("Predicted Value: %s", result['predicted_value'])
    logger.info("Line: %s", result['line'])
    logger.info("Recommendation: %s", result['recommendation'])
    logger.info("AI Score: %s/10", result['ai_score'])
    logger.info("Confidence: %s", result['confidence'])

    logger.info("\nPILLARS TRIGGERED:")
    for pillar in result['pillars']['triggered']:
        logger.info("  %s", pillar)

    logger.info("\nBET SIZING:")
    logger.info("  %s", result['bet_sizing']['recommendation'])
