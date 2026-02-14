#!/usr/bin/env python3
"""
Ensemble Sklearn Regressor Training Script
v20.22: Trains XGBoost, LightGBM, RandomForest regressors from graded picks

This script:
1. Loads graded picks from /data/grader/predictions.jsonl
2. Extracts features: ai_score, research_score, esoteric_score, jarvis_score,
   line, odds, confluence_boost, jason_sim_boost, rest_factor, injury_impact, etc.
3. Target: binary hit outcome (WIN=1.0, LOSS=0.0)
4. Trains XGBoost, LightGBM, RandomForest regressors (used for probability estimation)
5. Trains meta-model (GradientBoosting) on stacked predictions
6. Saves to /data/models/ensemble_sklearn_regressors.joblib

Run daily at 7:15 AM ET (after team model training at 7 AM).

NOTE: Models are trained but run in SHADOW MODE by default.
Set ENSEMBLE_SKLEARN_ENABLED=true to use them for live predictions.

Usage:
    python scripts/train_ensemble_regressors.py [--days 7] [--min-samples 50]
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check for required dependencies
DEPS_AVAILABLE = True
MISSING_DEPS = []

try:
    import numpy as np
except ImportError:
    DEPS_AVAILABLE = False
    MISSING_DEPS.append('numpy')

try:
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error, r2_score
except ImportError:
    DEPS_AVAILABLE = False
    MISSING_DEPS.append('scikit-learn')

try:
    from xgboost import XGBRegressor
except ImportError:
    DEPS_AVAILABLE = False
    MISSING_DEPS.append('xgboost')

try:
    from lightgbm import LGBMRegressor
except ImportError:
    DEPS_AVAILABLE = False
    MISSING_DEPS.append('lightgbm')


# Feature schema for training (must match what's available in picks)
FEATURE_SCHEMA = [
    'ai_score',
    'research_score',
    'esoteric_score',
    'jarvis_score',
    'context_modifier',
    'confluence_boost',
    'jason_sim_boost',
    'msrf_boost',
    'line',
    'odds_american',
    'rest_factor',
    'injury_impact',
]


def load_graded_picks(days: int = 7, min_samples: int = 50) -> Tuple[List[Dict], Dict]:
    """Load recently graded picks from storage.

    Args:
        days: Number of days back to look
        min_samples: Minimum samples required for training

    Returns:
        tuple: (picks_list, filter_telemetry)
    """
    from grader_store import load_predictions

    telemetry = {
        'loaded_total': 0,
        'graded_total': 0,
        'drop_no_result': 0,
        'drop_no_features': 0,
        'drop_wrong_market': 0,
        'drop_outside_window': 0,
        'eligible_total': 0,
        'filter_version': '1.0',
    }

    try:
        all_picks = load_predictions()
        telemetry['loaded_total'] = len(all_picks)

        # Filter to recent days
        cutoff = datetime.now() - timedelta(days=days)
        eligible = []

        for pick in all_picks:
            # Must have result
            result = pick.get('result', '').upper()
            if result not in ['WIN', 'LOSS']:
                telemetry['drop_no_result'] += 1
                continue

            # Must be game pick (not prop)
            pick_type = pick.get('pick_type', '').upper()
            if pick_type in ['PROP', 'PLAYER_PROP'] or pick.get('player_name'):
                telemetry['drop_wrong_market'] += 1
                continue

            # Must have required features
            if not pick.get('ai_score') or not pick.get('research_score'):
                telemetry['drop_no_features'] += 1
                continue

            # Check date window
            created_at = pick.get('created_at', '')
            if created_at:
                try:
                    pick_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if pick_date.replace(tzinfo=None) < cutoff:
                        telemetry['drop_outside_window'] += 1
                        continue
                except (ValueError, TypeError):
                    pass

            eligible.append(pick)

        telemetry['graded_total'] = sum(1 for p in all_picks if p.get('result') in ['WIN', 'LOSS', 'win', 'loss'])
        telemetry['eligible_total'] = len(eligible)

        if len(eligible) < min_samples:
            logger.warning(
                "Insufficient samples for training: %d < %d minimum",
                len(eligible), min_samples
            )

        return eligible, telemetry

    except Exception as e:
        logger.error("Failed to load picks: %s", e)
        return [], telemetry


def extract_features(pick: Dict) -> Optional[np.ndarray]:
    """Extract feature vector from a pick.

    Returns None if required features are missing.
    """
    features = []

    for feature_name in FEATURE_SCHEMA:
        value = pick.get(feature_name)

        # Handle nested fields
        if value is None and feature_name == 'context_modifier':
            # Try scoring_breakdown
            breakdown = pick.get('scoring_breakdown', {})
            value = breakdown.get('context_modifier', 0.0)

        if value is None and feature_name in ['rest_factor', 'injury_impact']:
            # Try context_breakdown or ai_breakdown
            ctx = pick.get('context_breakdown', {})
            ai = pick.get('ai_breakdown', {})
            value = ctx.get(feature_name) or ai.get(feature_name, 0.0)

        # Default to 0 for missing optional features
        if value is None:
            value = 0.0

        try:
            features.append(float(value))
        except (ValueError, TypeError):
            features.append(0.0)

    return np.array(features)


def extract_label(pick: Dict) -> float:
    """Extract label from pick result.

    Binary classification: WIN=1.0, LOSS=0.0
    """
    result = pick.get('result', '').upper()
    if result == 'WIN':
        return 1.0
    elif result == 'LOSS':
        return 0.0
    else:
        # PUSH or unknown - treat as 0.5
        return 0.5


def train_regressors(
    X: 'np.ndarray',
    y: 'np.ndarray',
    test_size: float = 0.2
) -> Tuple[Dict, Dict]:
    """Train sklearn regressors on the data.

    Args:
        X: Feature matrix
        y: Label vector
        test_size: Validation split ratio

    Returns:
        tuple: (trained_models_dict, training_metrics)
    """
    if not DEPS_AVAILABLE:
        raise ImportError(f"Missing required dependencies: {MISSING_DEPS}")

    # Imports already done at module level with availability check

    # Split data
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=test_size, random_state=42
    )

    logger.info("Training on %d samples, validating on %d", len(X_train), len(X_val))

    # Initialize models
    base_models = {
        'xgboost': XGBRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=6,
            random_state=42
        ),
        'lightgbm': LGBMRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=6,
            random_state=42,
            verbose=-1
        ),
        'random_forest': RandomForestRegressor(
            n_estimators=200,
            max_depth=8,
            random_state=42,
            n_jobs=-1
        )
    }

    # Optional scaler
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)

    # Train base models
    base_predictions_train = []
    base_predictions_val = []
    model_metrics = {}

    for name, model in base_models.items():
        logger.info("Training %s...", name)
        model.fit(X_train_scaled, y_train)

        train_pred = model.predict(X_train_scaled)
        val_pred = model.predict(X_val_scaled)

        base_predictions_train.append(train_pred)
        base_predictions_val.append(val_pred)

        # Calculate metrics
        mse = mean_squared_error(y_val, val_pred)
        r2 = r2_score(y_val, val_pred)
        model_metrics[name] = {'mse': mse, 'r2': r2}
        logger.info("  %s: MSE=%.4f, R2=%.4f", name, mse, r2)

    # Train meta model on stacked predictions
    stacked_train = np.column_stack(base_predictions_train)
    stacked_val = np.column_stack(base_predictions_val)

    meta_model = GradientBoostingRegressor(n_estimators=50, random_state=42)
    logger.info("Training meta model...")
    meta_model.fit(stacked_train, y_train)

    meta_pred = meta_model.predict(stacked_val)
    meta_mse = mean_squared_error(y_val, meta_pred)
    meta_r2 = r2_score(y_val, meta_pred)
    model_metrics['meta'] = {'mse': meta_mse, 'r2': meta_r2}
    logger.info("  meta: MSE=%.4f, R2=%.4f", meta_mse, meta_r2)

    # Calculate accuracy (binary classification at 0.5 threshold)
    predictions_binary = (meta_pred >= 0.5).astype(int)
    accuracy = np.mean(predictions_binary == y_val)
    logger.info("Meta model accuracy: %.2f%%", accuracy * 100)

    training_metrics = {
        'train_samples': len(X_train),
        'val_samples': len(X_val),
        'feature_count': X.shape[1],
        'model_metrics': model_metrics,
        'meta_accuracy': accuracy,
        'trained_at': datetime.now().isoformat(),
    }

    return {
        'base_models': base_models,
        'meta_model': meta_model,
        'scaler': scaler,
    }, training_metrics


def save_models(models: Dict, metrics: Dict) -> bool:
    """Save trained models using EnsembleStackingModel.save_models().

    Uses the central model class to ensure consistency.
    """
    try:
        from advanced_ml_backend import EnsembleStackingModel

        # Create instance and inject trained models
        ensemble = EnsembleStackingModel()
        ensemble.base_models = models['base_models']
        ensemble.meta_model = models['meta_model']
        ensemble.scaler = models.get('scaler')
        ensemble._ensemble_pipeline_trained = True
        ensemble.is_trained = True
        ensemble._last_train_time = metrics.get('trained_at')
        ensemble._training_samples_count = metrics.get('train_samples', 0)

        # Save using the class method
        success = ensemble.save_models()

        if success:
            logger.info("Models saved successfully")

        return success

    except Exception as e:
        logger.error("Failed to save models: %s", e)
        return False


def train_all(days: int = 7, min_samples: int = 50) -> Dict:
    """Main training function.

    Args:
        days: Number of days of data to use
        min_samples: Minimum samples required

    Returns:
        Training result dictionary with status and metrics
    """
    result = {
        'status': 'pending',
        'picks_loaded': 0,
        'picks_used': 0,
        'filter_telemetry': {},
        'training_metrics': {},
        'error': None,
        'missing_deps': MISSING_DEPS if not DEPS_AVAILABLE else [],
    }

    logger.info("=" * 60)
    logger.info("ENSEMBLE SKLEARN REGRESSOR TRAINING")
    logger.info("Days: %d, Min samples: %d", days, min_samples)
    logger.info("=" * 60)

    # Check dependencies first
    if not DEPS_AVAILABLE:
        result['status'] = 'SKIPPED_MISSING_DEPS'
        result['error'] = f"Missing dependencies: {', '.join(MISSING_DEPS)}"
        logger.warning("Skipping training - missing dependencies: %s", MISSING_DEPS)
        logger.info("=" * 60)
        return result

    # Load picks
    picks, telemetry = load_graded_picks(days=days, min_samples=min_samples)
    result['filter_telemetry'] = telemetry
    result['picks_loaded'] = telemetry['loaded_total']

    if len(picks) < min_samples:
        result['status'] = 'insufficient_data'
        result['error'] = f"Only {len(picks)} picks available, need {min_samples}"
        logger.warning(result['error'])
        return result

    # Extract features and labels
    X_list = []
    y_list = []

    for pick in picks:
        features = extract_features(pick)
        label = extract_label(pick)

        if features is not None and label != 0.5:  # Exclude PUSH
            X_list.append(features)
            y_list.append(label)

    if len(X_list) < min_samples:
        result['status'] = 'insufficient_features'
        result['error'] = f"Only {len(X_list)} picks with valid features"
        logger.warning(result['error'])
        return result

    X = np.array(X_list)
    y = np.array(y_list)
    result['picks_used'] = len(X)

    logger.info("Training on %d picks with %d features", len(X), X.shape[1])

    # Train models
    try:
        models, metrics = train_regressors(X, y)
        result['training_metrics'] = metrics
    except Exception as e:
        result['status'] = 'training_error'
        result['error'] = str(e)
        logger.error("Training failed: %s", e)
        return result

    # Save models
    if save_models(models, metrics):
        result['status'] = 'success'
        logger.info("Training complete and models saved")
    else:
        result['status'] = 'save_error'
        result['error'] = "Failed to save models"

    logger.info("=" * 60)
    logger.info("TRAINING COMPLETE: %s", result['status'])
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train ensemble sklearn regressors")
    parser.add_argument("--days", type=int, default=7, help="Days of data to use")
    parser.add_argument("--min-samples", type=int, default=50, help="Minimum samples required")

    args = parser.parse_args()

    result = train_all(days=args.days, min_samples=args.min_samples)

    # Exit with status code
    if result['status'] == 'success':
        sys.exit(0)
    else:
        sys.exit(1)
