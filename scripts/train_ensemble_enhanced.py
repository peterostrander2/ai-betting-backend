#!/usr/bin/env python3
"""
Enhanced Ensemble Training Script (v18.1)
==========================================

Trains XGBoost ensemble model with improved features:
- Cross-validation (5-fold) for robust evaluation
- Hyperparameter tuning via grid search
- Platt scaling for probability calibration
- Model versioning and metric logging

Usage:
    python scripts/train_ensemble_enhanced.py
    python scripts/train_ensemble_enhanced.py --min-picks 200
    python scripts/train_ensemble_enhanced.py --no-tuning  # Skip grid search
    python scripts/train_ensemble_enhanced.py --dry-run

Requirements:
    - scikit-learn installed
    - XGBoost installed (optional, falls back to sklearn)
    - At least 100 graded picks
"""

import os
import sys
import json
import argparse
import logging
import shutil
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try imports
try:
    import numpy as np
    from sklearn.model_selection import (
        train_test_split, cross_val_score, GridSearchCV, StratifiedKFold
    )
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        roc_auc_score, brier_score_loss, log_loss
    )
    from sklearn.calibration import CalibratedClassifierCV
    import joblib
    ML_AVAILABLE = True
except ImportError as e:
    ML_AVAILABLE = False
    logger.error(f"ML libraries not available: {e}")

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not available, will use sklearn GradientBoosting")


# ============================================
# CONFIGURATION
# ============================================

class EnsembleTrainingConfig:
    """Training configuration."""

    # Minimum data requirements
    MIN_PICKS = 100
    MIN_PICKS_FOR_TUNING = 500  # Need more data for reliable grid search

    # Cross-validation
    CV_FOLDS = 5
    RANDOM_STATE = 42

    # Hyperparameter grid for tuning
    PARAM_GRID = {
        "n_estimators": [100, 200, 300],
        "max_depth": [3, 5, 7],
        "learning_rate": [0.01, 0.05, 0.1],
        "subsample": [0.8, 0.9, 1.0]
    }

    # Smaller grid for faster tuning
    PARAM_GRID_FAST = {
        "n_estimators": [100, 200],
        "max_depth": [3, 5],
        "learning_rate": [0.05, 0.1]
    }

    # Default params (when not tuning)
    DEFAULT_PARAMS = {
        "n_estimators": 200,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.9,
        "random_state": 42
    }

    # Model versioning
    KEEP_VERSIONS = 3


# Feature names (must match train_ensemble.py)
FEATURE_NAMES = [
    "ai_score",
    "research_score",
    "esoteric_score",
    "jarvis_score",
    "line",
    "odds_american",
    "confluence_boost",
    "jason_sim_boost",
    "titanium_triggered",
    "sport_encoded",
    "pick_type_encoded",
    "side_encoded",
]


# ============================================
# ENHANCED ENSEMBLE TRAINER
# ============================================

class EnhancedEnsembleTrainer:
    """
    Enhanced ensemble training with CV, hyperparameter tuning, and calibration.
    """

    def __init__(self, models_dir: str = None, logs_dir: str = None):
        """
        Initialize trainer.

        Args:
            models_dir: Directory for model files
            logs_dir: Directory for training logs
        """
        base_dir = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")

        if models_dir is None:
            models_dir = os.path.join(base_dir, "models")

        if logs_dir is None:
            logs_dir = os.path.join(base_dir, "ml_logs")

        self.models_dir = models_dir
        self.logs_dir = logs_dir

        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

        self.training_history = {}

    def train_model(
        self,
        min_picks: int = None,
        enable_tuning: bool = True,
        fast_tuning: bool = True,
        enable_calibration: bool = True,
        dry_run: bool = False
    ) -> Optional[Dict]:
        """
        Train enhanced ensemble model.

        Args:
            min_picks: Minimum picks required
            enable_tuning: Enable hyperparameter tuning
            fast_tuning: Use smaller grid for faster tuning
            enable_calibration: Enable Platt scaling calibration
            dry_run: Analyze data without training

        Returns:
            Training results dict or None if failed
        """
        if not ML_AVAILABLE:
            logger.error("ML libraries not available")
            return None

        min_picks = min_picks or EnsembleTrainingConfig.MIN_PICKS

        logger.info("=" * 60)
        logger.info("ENHANCED ENSEMBLE TRAINING")
        logger.info("=" * 60)

        # 1. Load training data
        X, y, metadata = self._load_training_data()

        if X is None or len(X) < min_picks:
            logger.warning(
                f"Insufficient data: {len(X) if X is not None else 0} picks "
                f"(need {min_picks})"
            )
            return None

        logger.info(f"Loaded {len(X)} picks")
        logger.info(f"Class distribution: {np.sum(y==1)} wins ({100*np.mean(y):.1f}%), "
                   f"{np.sum(y==0)} losses")

        # 2. Data stats
        data_stats = {
            "total_samples": len(X),
            "wins": int(np.sum(y == 1)),
            "losses": int(np.sum(y == 0)),
            "hit_rate": float(np.mean(y)),
            "features": len(FEATURE_NAMES)
        }

        if dry_run:
            logger.info("Dry run complete - not training")
            return {"data_stats": data_stats, "dry_run": True}

        # 3. Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2,
            random_state=EnsembleTrainingConfig.RANDOM_STATE,
            stratify=y
        )

        logger.info(f"Train/Test split: {len(X_train)}/{len(X_test)}")

        # 4. Create base model
        if XGBOOST_AVAILABLE:
            base_model = xgb.XGBClassifier(
                objective='binary:logistic',
                eval_metric='logloss',
                use_label_encoder=False,
                random_state=EnsembleTrainingConfig.RANDOM_STATE
            )
            model_type = "XGBClassifier"
        else:
            from sklearn.ensemble import GradientBoostingClassifier
            base_model = GradientBoostingClassifier(
                random_state=EnsembleTrainingConfig.RANDOM_STATE
            )
            model_type = "GradientBoostingClassifier"

        # 5. Hyperparameter tuning (optional)
        best_params = EnsembleTrainingConfig.DEFAULT_PARAMS.copy()
        tuning_results = None

        if enable_tuning and len(X_train) >= EnsembleTrainingConfig.MIN_PICKS_FOR_TUNING:
            logger.info("Running hyperparameter tuning...")
            param_grid = (
                EnsembleTrainingConfig.PARAM_GRID_FAST if fast_tuning
                else EnsembleTrainingConfig.PARAM_GRID
            )

            cv = StratifiedKFold(n_splits=EnsembleTrainingConfig.CV_FOLDS, shuffle=True,
                                random_state=EnsembleTrainingConfig.RANDOM_STATE)

            grid_search = GridSearchCV(
                base_model, param_grid, cv=cv, scoring='roc_auc',
                n_jobs=-1, verbose=1
            )

            grid_search.fit(X_train, y_train)

            best_params = grid_search.best_params_
            tuning_results = {
                "best_params": best_params,
                "best_score": float(grid_search.best_score_),
                "grid_size": len(list(
                    np.prod([len(v) for v in param_grid.values()])
                ))
            }

            logger.info(f"Best params: {best_params}")
            logger.info(f"Best CV ROC-AUC: {grid_search.best_score_:.4f}")

        # 6. Train final model with best params
        if XGBOOST_AVAILABLE:
            final_model = xgb.XGBClassifier(
                **best_params,
                objective='binary:logistic',
                eval_metric='logloss',
                use_label_encoder=False
            )
        else:
            from sklearn.ensemble import GradientBoostingClassifier
            # Filter out XGBoost-specific params
            sklearn_params = {k: v for k, v in best_params.items()
                           if k in ['n_estimators', 'max_depth', 'learning_rate', 'subsample', 'random_state']}
            final_model = GradientBoostingClassifier(**sklearn_params)

        logger.info("Training final model...")
        final_model.fit(X_train, y_train)

        # 7. Cross-validation on full training data
        cv = StratifiedKFold(n_splits=EnsembleTrainingConfig.CV_FOLDS, shuffle=True,
                            random_state=EnsembleTrainingConfig.RANDOM_STATE)

        cv_scores = cross_val_score(final_model, X_train, y_train, cv=cv, scoring='accuracy')
        cv_auc_scores = cross_val_score(final_model, X_train, y_train, cv=cv, scoring='roc_auc')

        logger.info(f"CV Accuracy: {np.mean(cv_scores):.4f} ± {np.std(cv_scores):.4f}")
        logger.info(f"CV ROC-AUC: {np.mean(cv_auc_scores):.4f} ± {np.std(cv_auc_scores):.4f}")

        # 8. Probability calibration (Platt scaling)
        calibrated_model = None
        if enable_calibration:
            logger.info("Applying Platt scaling calibration...")
            calibrated_model = CalibratedClassifierCV(
                final_model, method='sigmoid', cv='prefit'
            )
            calibrated_model.fit(X_test, y_test)

        # 9. Evaluate on test set
        model_to_eval = calibrated_model if calibrated_model else final_model

        y_pred = model_to_eval.predict(X_test)
        y_prob = model_to_eval.predict_proba(X_test)[:, 1]

        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1": float(f1_score(y_test, y_pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_test, y_prob)),
            "brier_score": float(brier_score_loss(y_test, y_prob)),
            "log_loss": float(log_loss(y_test, y_prob)),
            "cv_accuracy_mean": float(np.mean(cv_scores)),
            "cv_accuracy_std": float(np.std(cv_scores)),
            "cv_auc_mean": float(np.mean(cv_auc_scores)),
            "cv_auc_std": float(np.std(cv_auc_scores)),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "calibrated": enable_calibration
        }

        logger.info(f"Test Accuracy: {metrics['accuracy']:.4f}")
        logger.info(f"Test ROC-AUC: {metrics['roc_auc']:.4f}")
        logger.info(f"Brier Score: {metrics['brier_score']:.4f}")

        # 10. Feature importance
        feature_importance = {}
        if hasattr(final_model, 'feature_importances_'):
            importance = final_model.feature_importances_
            feature_importance = dict(zip(FEATURE_NAMES, [float(x) for x in importance]))
            metrics["feature_importance"] = feature_importance

            # Log top features
            sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            logger.info("Top features:")
            for name, imp in sorted_features[:5]:
                logger.info(f"  {name}: {imp:.4f}")

        # 11. Save model with versioning
        saved_path = self._save_model_versioned(
            model_to_eval, metrics, best_params, enable_calibration
        )

        # 12. Log training
        self._log_training(data_stats, metrics, best_params, tuning_results)

        return {
            "data_stats": data_stats,
            "metrics": metrics,
            "best_params": best_params,
            "tuning_results": tuning_results,
            "model_path": saved_path,
            "model_type": model_type,
            "calibrated": enable_calibration,
            "trained_at": datetime.now().isoformat()
        }

    def _load_training_data(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Dict]:
        """Load training data from predictions file."""
        try:
            # First try enhanced pipeline
            from services.ml_data_pipeline import get_ml_pipeline

            pipeline = get_ml_pipeline()
            df = pipeline.get_game_training_data(
                days_back=180,  # 6 months
                min_samples=50
            )

            if df is not None and len(df) >= 50:
                # Extract features
                X = self._extract_features_from_df(df)
                y = df['outcome'].values.astype(np.int32)
                metadata = {"source": "ml_data_pipeline", "samples": len(df)}
                return X, y, metadata

        except Exception as e:
            logger.warning(f"ML data pipeline failed: {e}")

        # Fallback to original method
        return self._load_from_jsonl()

    def _load_from_jsonl(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Dict]:
        """Load training data from JSONL file (fallback)."""
        base_dir = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")
        predictions_path = os.path.join(base_dir, "grader", "predictions.jsonl")

        if not os.path.exists(predictions_path):
            logger.warning(f"Predictions file not found: {predictions_path}")
            return None, None, {}

        X_list = []
        y_list = []

        with open(predictions_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    pick = json.loads(line)

                    # Check if graded
                    grade_status = pick.get("grade_status", "").upper()
                    if grade_status != "GRADED":
                        continue

                    # Get outcome
                    result = pick.get("result", pick.get("grade_result", "")).upper()
                    if result in ["WIN", "HIT", "1"]:
                        label = 1
                    elif result in ["LOSS", "MISS", "0"]:
                        label = 0
                    else:
                        continue

                    # Extract features
                    features = self._extract_features(pick)
                    if features is not None:
                        X_list.append(features)
                        y_list.append(label)

                except json.JSONDecodeError:
                    continue

        if not X_list:
            return None, None, {}

        X = np.vstack(X_list)
        y = np.array(y_list, dtype=np.int32)

        return X, y, {"source": "jsonl", "samples": len(y)}

    def _extract_features_from_df(self, df) -> np.ndarray:
        """Extract feature matrix from DataFrame."""
        feature_values = []

        for col in FEATURE_NAMES:
            if col in df.columns:
                feature_values.append(df[col].fillna(0).values)
            elif col == "titanium_triggered" and "titanium" in df.columns:
                feature_values.append(df["titanium"].fillna(0).values)
            else:
                feature_values.append(np.zeros(len(df)))

        return np.column_stack(feature_values).astype(np.float32)

    def _extract_features(self, pick: Dict) -> Optional[np.ndarray]:
        """Extract feature vector from a pick dictionary."""
        try:
            # Encoding maps
            sport_encoding = {"NBA": 0, "NFL": 1, "MLB": 2, "NHL": 3, "NCAAB": 4}
            type_encoding = {"PROP": 0, "SPREAD": 1, "TOTAL": 2, "MONEYLINE": 3}

            ai_score = pick.get("ai_score", 5.0)
            research_score = pick.get("research_score", 5.0)
            esoteric_score = pick.get("esoteric_score", 5.0)
            jarvis_score = pick.get("jarvis_score", pick.get("jarvis_rs", 5.0))

            line = pick.get("line", 0.0) or 0.0
            odds = pick.get("odds_american", pick.get("odds", -110)) or -110

            confluence = pick.get("confluence_boost", 0.0)
            jason_sim = pick.get("jason_sim_boost", 0.0)
            titanium = 1.0 if pick.get("titanium_triggered", False) else 0.0

            sport = pick.get("sport", "NBA").upper()
            sport_encoded = sport_encoding.get(sport, 0)

            pick_type = pick.get("pick_type", pick.get("market_type", "GAME")).upper()
            if "PROP" in pick_type:
                type_encoded = 0
            elif "SPREAD" in pick_type:
                type_encoded = 1
            elif "TOTAL" in pick_type:
                type_encoded = 2
            else:
                type_encoded = 3

            side = pick.get("side", pick.get("pick_side", ""))
            if "OVER" in str(side).upper():
                side_encoded = 0
            elif "UNDER" in str(side).upper():
                side_encoded = 1
            elif pick.get("selection_home_away") == "HOME":
                side_encoded = 2
            else:
                side_encoded = 3

            features = np.array([
                ai_score, research_score, esoteric_score, jarvis_score,
                float(line), float(odds), confluence, jason_sim, titanium,
                sport_encoded, type_encoded, side_encoded
            ], dtype=np.float32)

            return features

        except Exception as e:
            logger.debug(f"Feature extraction failed: {e}")
            return None

    def _save_model_versioned(
        self,
        model: Any,
        metrics: Dict,
        params: Dict,
        calibrated: bool
    ) -> str:
        """Save model with versioning."""
        base_name = "ensemble_hit_predictor"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Versioned filename
        versioned_name = f"{base_name}_{timestamp}.joblib"
        versioned_path = os.path.join(self.models_dir, versioned_name)

        # Current filename
        current_name = f"{base_name}.joblib"
        current_path = os.path.join(self.models_dir, current_name)

        # Save versioned model
        joblib.dump(model, versioned_path)
        logger.info(f"Saved versioned model: {versioned_path}")

        # Copy to current
        shutil.copy2(versioned_path, current_path)
        logger.info(f"Updated current model: {current_path}")

        # Save metadata
        metadata = {
            "trained_at": datetime.now().isoformat(),
            "metrics": metrics,
            "params": params,
            "calibrated": calibrated,
            "feature_names": FEATURE_NAMES,
            "model_type": type(model).__name__,
            "version": timestamp
        }

        metadata_path = current_path.replace(".joblib", "_metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Cleanup old versions
        self._cleanup_old_versions(base_name)

        return current_path

    def _cleanup_old_versions(self, base_name: str):
        """Remove old model versions."""
        versions = []
        for f in os.listdir(self.models_dir):
            if f.startswith(base_name + "_") and f.endswith(".joblib"):
                path = os.path.join(self.models_dir, f)
                mtime = os.path.getmtime(path)
                versions.append((mtime, path))

        versions.sort(reverse=True)

        for _, path in versions[EnsembleTrainingConfig.KEEP_VERSIONS:]:
            try:
                os.remove(path)
                logger.info(f"Removed old version: {path}")
            except Exception as e:
                logger.warning(f"Failed to remove {path}: {e}")

    def _log_training(
        self,
        data_stats: Dict,
        metrics: Dict,
        params: Dict,
        tuning_results: Optional[Dict]
    ):
        """Log training results."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "data_stats": data_stats,
            "metrics": metrics,
            "params": params,
            "tuning_results": tuning_results
        }

        log_file = os.path.join(self.logs_dir, "ensemble_training.jsonl")
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")


# ============================================
# MAIN
# ============================================

def main():
    parser = argparse.ArgumentParser(description="Enhanced ensemble model training")
    parser.add_argument('--min-picks', type=int, default=100,
                       help='Minimum graded picks required (default: 100)')
    parser.add_argument('--no-tuning', action='store_true',
                       help='Disable hyperparameter tuning')
    parser.add_argument('--full-tuning', action='store_true',
                       help='Use full (slower) hyperparameter grid')
    parser.add_argument('--no-calibration', action='store_true',
                       help='Disable Platt scaling calibration')
    parser.add_argument('--dry-run', action='store_true',
                       help='Analyze data without training')
    args = parser.parse_args()

    if not ML_AVAILABLE:
        logger.error("ML libraries not available. Install with: pip install scikit-learn xgboost joblib")
        sys.exit(1)

    trainer = EnhancedEnsembleTrainer()

    result = trainer.train_model(
        min_picks=args.min_picks,
        enable_tuning=not args.no_tuning,
        fast_tuning=not args.full_tuning,
        enable_calibration=not args.no_calibration,
        dry_run=args.dry_run
    )

    if result:
        print("\n" + "=" * 60)
        print("ENHANCED ENSEMBLE TRAINING COMPLETE")
        print("=" * 60)

        if result.get("dry_run"):
            print(f"Data stats: {result['data_stats']}")
        else:
            metrics = result.get("metrics", {})
            print(f"Training samples: {metrics.get('train_samples', 'N/A')}")
            print(f"Test samples: {metrics.get('test_samples', 'N/A')}")
            print(f"Test accuracy: {metrics.get('accuracy', 0):.4f}")
            print(f"Test ROC-AUC: {metrics.get('roc_auc', 0):.4f}")
            print(f"CV accuracy: {metrics.get('cv_accuracy_mean', 0):.4f} ± {metrics.get('cv_accuracy_std', 0):.4f}")
            print(f"Brier score: {metrics.get('brier_score', 0):.4f}")
            print(f"Calibrated: {result.get('calibrated', False)}")

            if result.get("best_params"):
                print(f"\nBest params: {result['best_params']}")

            if result.get("model_path"):
                print(f"\nModel saved to: {result['model_path']}")

            if metrics.get("feature_importance"):
                print("\nTop features:")
                sorted_features = sorted(
                    metrics["feature_importance"].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
                for name, imp in sorted_features:
                    print(f"  {name}: {imp:.4f}")
    else:
        print("Training failed or insufficient data")
        sys.exit(1)


if __name__ == "__main__":
    main()
