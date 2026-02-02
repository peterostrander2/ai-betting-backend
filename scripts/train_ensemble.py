#!/usr/bin/env python3
"""
Ensemble Model Training Script
==============================

Trains an XGBoost ensemble model from graded predictions to predict hit/miss outcomes.

This script:
1. Loads graded predictions from /data/grader/predictions.jsonl
2. Extracts features: [research_score, esoteric_score, jarvis_score, ai_score, line, odds, etc.]
3. Trains XGBoost classifier on hit prediction
4. Saves model to /data/models/ensemble_hit_predictor.joblib

Usage:
    python scripts/train_ensemble.py [--min-picks N] [--output-dir DIR]

Requirements:
    - At least 100 graded picks (configurable)
    - XGBoost and scikit-learn installed
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import ML libraries
try:
    import numpy as np
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
    import joblib
    ML_LIBS_AVAILABLE = True
except ImportError as e:
    ML_LIBS_AVAILABLE = False
    logger.error(f"ML libraries not available: {e}")
    logger.error("Install with: pip install numpy scikit-learn xgboost joblib")

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not available, will use sklearn alternatives")


# ============================================
# FEATURE EXTRACTION
# ============================================

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
    "sport_encoded",  # NBA=0, NFL=1, MLB=2, NHL=3, NCAAB=4
    "pick_type_encoded",  # PROP=0, SPREAD=1, TOTAL=2, MONEYLINE=3
    "side_encoded",  # Over=0, Under=1, Home=2, Away=3
]

SPORT_ENCODING = {"NBA": 0, "NFL": 1, "MLB": 2, "NHL": 3, "NCAAB": 4}
PICK_TYPE_ENCODING = {"PROP": 0, "SPREAD": 1, "TOTAL": 2, "MONEYLINE": 3}
SIDE_ENCODING = {"Over": 0, "Under": 1, "Home": 2, "Away": 3}


def extract_features(pick: Dict) -> Optional[np.ndarray]:
    """
    Extract feature vector from a pick dictionary.

    Returns None if pick is missing required fields.
    """
    try:
        # Core engine scores (required)
        ai_score = pick.get("ai_score", 5.0)
        research_score = pick.get("research_score", 5.0)
        esoteric_score = pick.get("esoteric_score", 5.0)
        jarvis_score = pick.get("jarvis_score", pick.get("jarvis_rs", 5.0))

        # Bet details
        line = pick.get("line", 0.0)
        if line is None:
            line = 0.0

        odds = pick.get("odds", pick.get("odds_american", -110))
        if odds is None:
            odds = -110

        # Boosts
        confluence_boost = pick.get("confluence_boost", 0.0)
        jason_sim_boost = pick.get("jason_sim_boost", 0.0)

        # Titanium
        titanium = 1.0 if pick.get("titanium_triggered", False) else 0.0

        # Sport encoding
        sport = pick.get("sport", "NBA").upper()
        sport_encoded = SPORT_ENCODING.get(sport, 0)

        # Pick type encoding
        pick_type = pick.get("pick_type", pick.get("market", "PROP")).upper()
        if "PROP" in pick_type or "PLAYER" in pick_type:
            pick_type_encoded = 0
        elif "SPREAD" in pick_type:
            pick_type_encoded = 1
        elif "TOTAL" in pick_type:
            pick_type_encoded = 2
        else:
            pick_type_encoded = 3  # Moneyline or other

        # Side encoding
        side = pick.get("side", pick.get("pick_side", "Over"))
        if side in ["Over", "OVER"]:
            side_encoded = 0
        elif side in ["Under", "UNDER"]:
            side_encoded = 1
        elif pick.get("selection_home_away") == "HOME":
            side_encoded = 2
        else:
            side_encoded = 3

        features = np.array([
            ai_score,
            research_score,
            esoteric_score,
            jarvis_score,
            float(line),
            float(odds),
            confluence_boost,
            jason_sim_boost,
            titanium,
            sport_encoded,
            pick_type_encoded,
            side_encoded
        ], dtype=np.float32)

        return features

    except Exception as e:
        logger.debug(f"Feature extraction failed: {e}")
        return None


def get_label(pick: Dict) -> Optional[int]:
    """
    Extract label (1=hit, 0=miss) from graded pick.

    Returns None if pick is not graded.
    """
    grade_status = pick.get("grade_status", "").upper()
    if grade_status != "GRADED":
        return None

    result = pick.get("result", pick.get("grade_result", "")).upper()
    if result in ["WIN", "HIT", "1"]:
        return 1
    elif result in ["LOSS", "MISS", "0"]:
        return 0
    else:
        return None


# ============================================
# DATA LOADING
# ============================================

def load_predictions(predictions_path: str) -> List[Dict]:
    """Load predictions from JSONL file."""
    predictions = []

    if not os.path.exists(predictions_path):
        logger.error(f"Predictions file not found: {predictions_path}")
        return predictions

    with open(predictions_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                pick = json.loads(line)
                predictions.append(pick)
            except json.JSONDecodeError as e:
                logger.debug(f"Line {line_num}: Invalid JSON - {e}")
                continue

    logger.info(f"Loaded {len(predictions)} predictions from {predictions_path}")
    return predictions


def prepare_dataset(predictions: List[Dict]) -> Tuple[np.ndarray, np.ndarray, List[Dict]]:
    """
    Prepare feature matrix and label vector from predictions.

    Returns:
        X: Feature matrix (n_samples, n_features)
        y: Label vector (n_samples,)
        valid_picks: List of picks that were included (for analysis)
    """
    X_list = []
    y_list = []
    valid_picks = []

    for pick in predictions:
        # Get label (skip ungraded)
        label = get_label(pick)
        if label is None:
            continue

        # Extract features (skip if missing required fields)
        features = extract_features(pick)
        if features is None:
            continue

        X_list.append(features)
        y_list.append(label)
        valid_picks.append(pick)

    if not X_list:
        return np.array([]), np.array([]), []

    X = np.vstack(X_list)
    y = np.array(y_list)

    logger.info(f"Prepared dataset: {len(y)} samples, {X.shape[1]} features")
    logger.info(f"Class distribution: {np.sum(y==1)} wins ({100*np.mean(y):.1f}%), {np.sum(y==0)} losses")

    return X, y, valid_picks


# ============================================
# MODEL TRAINING
# ============================================

def train_xgboost_model(X: np.ndarray, y: np.ndarray, random_state: int = 42) -> Tuple[any, Dict]:
    """
    Train XGBoost classifier with cross-validation.

    Returns:
        model: Trained XGBClassifier
        metrics: Dict with performance metrics
    """
    if not XGBOOST_AVAILABLE:
        from sklearn.ensemble import GradientBoostingClassifier
        logger.warning("Using sklearn GradientBoosting instead of XGBoost")

        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=random_state
        )
    else:
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            objective='binary:logistic',
            eval_metric='logloss',
            random_state=random_state,
            use_label_encoder=False
        )

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=random_state, stratify=y
    )

    # Train
    logger.info("Training ensemble model...")
    model.fit(X_train, y_train)

    # Evaluate on test set
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_prob),
        "train_samples": len(y_train),
        "test_samples": len(y_test),
        "train_hit_rate": np.mean(y_train),
        "test_hit_rate": np.mean(y_test),
    }

    # Cross-validation
    cv_scores = cross_val_score(model, X, y, cv=5, scoring='accuracy')
    metrics["cv_accuracy_mean"] = np.mean(cv_scores)
    metrics["cv_accuracy_std"] = np.std(cv_scores)

    # Feature importance
    if hasattr(model, 'feature_importances_'):
        importance = dict(zip(FEATURE_NAMES, model.feature_importances_.tolist()))
        metrics["feature_importance"] = importance

    logger.info(f"Model trained. Test accuracy: {metrics['accuracy']:.3f}, ROC-AUC: {metrics['roc_auc']:.3f}")
    logger.info(f"Cross-validation: {metrics['cv_accuracy_mean']:.3f} ± {metrics['cv_accuracy_std']:.3f}")

    return model, metrics


def save_model(model, output_path: str, metrics: Dict):
    """Save model and metadata."""
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Save model
    joblib.dump(model, output_path)
    logger.info(f"Model saved to {output_path}")

    # Save metadata
    metadata_path = output_path.replace('.joblib', '_metadata.json')
    metadata = {
        "trained_at": datetime.now().isoformat(),
        "metrics": metrics,
        "feature_names": FEATURE_NAMES,
        "model_type": type(model).__name__,
    }

    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Metadata saved to {metadata_path}")


# ============================================
# MAIN
# ============================================

def main():
    parser = argparse.ArgumentParser(description="Train ensemble model from graded predictions")
    parser.add_argument('--min-picks', type=int, default=100,
                       help='Minimum graded picks required to train (default: 100)')
    parser.add_argument('--predictions-path', type=str,
                       default='/data/grader/predictions.jsonl',
                       help='Path to predictions JSONL file')
    parser.add_argument('--output-dir', type=str,
                       default='/data/models',
                       help='Output directory for model files')
    parser.add_argument('--dry-run', action='store_true',
                       help='Analyze data without training')
    args = parser.parse_args()

    if not ML_LIBS_AVAILABLE:
        logger.error("Required ML libraries not available. Exiting.")
        sys.exit(1)

    # Load predictions
    predictions = load_predictions(args.predictions_path)
    if not predictions:
        logger.error("No predictions found. Exiting.")
        sys.exit(1)

    # Prepare dataset
    X, y, valid_picks = prepare_dataset(predictions)

    if len(y) < args.min_picks:
        logger.error(f"Only {len(y)} graded picks available. Need at least {args.min_picks}.")
        logger.info("Waiting for more graded picks before training...")
        sys.exit(1)

    if args.dry_run:
        logger.info("Dry run complete. Data analysis:")
        logger.info(f"  - Total predictions: {len(predictions)}")
        logger.info(f"  - Graded picks: {len(y)}")
        logger.info(f"  - Hit rate: {100*np.mean(y):.1f}%")
        logger.info(f"  - Features: {len(FEATURE_NAMES)}")
        return

    # Train model
    model, metrics = train_xgboost_model(X, y)

    # Save model
    output_path = os.path.join(args.output_dir, 'ensemble_hit_predictor.joblib')
    save_model(model, output_path, metrics)

    # Print summary
    print("\n" + "="*60)
    print("ENSEMBLE MODEL TRAINING COMPLETE")
    print("="*60)
    print(f"Training samples: {metrics['train_samples']}")
    print(f"Test samples: {metrics['test_samples']}")
    print(f"Test accuracy: {metrics['accuracy']:.3f}")
    print(f"Test ROC-AUC: {metrics['roc_auc']:.3f}")
    print(f"CV accuracy: {metrics['cv_accuracy_mean']:.3f} ± {metrics['cv_accuracy_std']:.3f}")
    print(f"\nModel saved to: {output_path}")

    if 'feature_importance' in metrics:
        print("\nFeature Importance:")
        sorted_features = sorted(metrics['feature_importance'].items(), key=lambda x: x[1], reverse=True)
        for name, importance in sorted_features[:5]:
            print(f"  {name}: {importance:.3f}")


if __name__ == "__main__":
    main()
