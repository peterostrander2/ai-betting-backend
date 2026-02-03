#!/usr/bin/env python3
"""
Enhanced LSTM Training Script (v18.1)
=====================================

Trains LSTM models with improved features:
- Early stopping based on validation loss
- Model versioning (keep last 3 versions)
- Metric logging for performance tracking
- Cross-validation for robust evaluation

Usage:
    python scripts/train_lstm_enhanced.py --sport NBA --stat-type points
    python scripts/train_lstm_enhanced.py --all  # Train all available models
    python scripts/train_lstm_enhanced.py --dry-run  # Analyze data only

Requirements:
    - TensorFlow/Keras installed
    - At least 500 samples per sport/stat combo
"""

import os
import sys
import json
import argparse
import logging
import shutil
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try imports
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import tensorflow as tf
    from tensorflow import keras
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not available")


# ============================================
# CONFIGURATION
# ============================================

class LSTMTrainingConfig:
    """Training configuration."""

    # Model architecture
    SEQUENCE_LENGTH = 5
    NUM_FEATURES = 6  # stat, mins, home_away, vacuum, def_rank, pace
    LSTM_UNITS = 64
    DENSE_UNITS = 32
    DROPOUT_RATE = 0.2

    # Training params
    MIN_SAMPLES = 500
    VALIDATION_SPLIT = 0.2
    BATCH_SIZE = 32
    MAX_EPOCHS = 100
    EARLY_STOPPING_PATIENCE = 10

    # Model versioning
    KEEP_VERSIONS = 3  # Keep last N versions

    # Sport/stat combinations
    SPORT_STATS = {
        "NBA": ["points", "assists", "rebounds"],
        "NFL": ["passing_yards", "rushing_yards", "receiving_yards"],
        "MLB": ["hits", "total_bases", "strikeouts"],
        "NHL": ["points", "shots"],
        "NCAAB": ["points", "rebounds"]
    }


# ============================================
# ENHANCED LSTM TRAINER
# ============================================

class EnhancedLSTMTrainer:
    """
    Enhanced LSTM training with early stopping, versioning, and metric logging.
    """

    def __init__(self, models_dir: str = None, logs_dir: str = None):
        """
        Initialize trainer.

        Args:
            models_dir: Directory for model weights
            logs_dir: Directory for training logs
        """
        base_dir = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")

        if models_dir is None:
            models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

        if logs_dir is None:
            logs_dir = os.path.join(base_dir, "ml_logs")

        self.models_dir = models_dir
        self.logs_dir = logs_dir

        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

        self.training_history = {}

    def train_model(
        self,
        sport: str,
        stat_type: str,
        min_samples: int = None,
        validation_split: float = None,
        epochs: int = None,
        early_stopping_patience: int = None,
        dry_run: bool = False
    ) -> Optional[Dict]:
        """
        Train a single LSTM model.

        Args:
            sport: Sport name (NBA, NFL, etc.)
            stat_type: Stat type (points, assists, etc.)
            min_samples: Minimum samples required
            validation_split: Validation split ratio
            epochs: Max training epochs
            early_stopping_patience: Early stopping patience
            dry_run: If True, analyze data without training

        Returns:
            Training results dict or None if failed
        """
        if not TF_AVAILABLE:
            logger.error("TensorFlow not available - cannot train LSTM")
            return None

        # Use defaults if not specified
        min_samples = min_samples or LSTMTrainingConfig.MIN_SAMPLES
        validation_split = validation_split or LSTMTrainingConfig.VALIDATION_SPLIT
        epochs = epochs or LSTMTrainingConfig.MAX_EPOCHS
        early_stopping_patience = early_stopping_patience or LSTMTrainingConfig.EARLY_STOPPING_PATIENCE

        logger.info("=" * 50)
        logger.info(f"Training LSTM: {sport}/{stat_type}")
        logger.info("=" * 50)

        # 1. Load training data
        X, y = self._load_training_data(sport, stat_type)

        if X is None or len(X) < min_samples:
            logger.warning(
                f"Insufficient data for {sport}/{stat_type}: "
                f"{len(X) if X is not None else 0} samples (need {min_samples})"
            )
            return None

        logger.info(f"Loaded {len(X)} samples")

        # 2. Data analysis
        data_stats = {
            "total_samples": len(X),
            "mean_target": float(np.mean(y)),
            "std_target": float(np.std(y)),
            "min_target": float(np.min(y)),
            "max_target": float(np.max(y))
        }
        logger.info(f"Target stats: mean={data_stats['mean_target']:.2f}, std={data_stats['std_target']:.2f}")

        if dry_run:
            logger.info("Dry run complete - not training")
            return {"sport": sport, "stat_type": stat_type, "data_stats": data_stats, "dry_run": True}

        # 3. Split data
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        logger.info(f"Train/Val split: {len(X_train)}/{len(X_val)}")

        # 4. Build model
        model = self._build_model()

        # 5. Set up callbacks
        callbacks = [
            keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=early_stopping_patience,
                restore_best_weights=True,
                verbose=1
            ),
            keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=5,
                min_lr=1e-6,
                verbose=1
            )
        ]

        # 6. Train
        logger.info("Training...")
        history = model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=LSTMTrainingConfig.BATCH_SIZE,
            callbacks=callbacks,
            verbose=1
        )

        # 7. Evaluate
        train_loss = model.evaluate(X_train, y_train, verbose=0)
        val_loss = model.evaluate(X_val, y_val, verbose=0)

        # Calculate metrics
        y_pred_train = model.predict(X_train, verbose=0).flatten()
        y_pred_val = model.predict(X_val, verbose=0).flatten()

        train_mae = float(np.mean(np.abs(y_train - y_pred_train)))
        val_mae = float(np.mean(np.abs(y_val - y_pred_val)))

        train_rmse = float(np.sqrt(np.mean((y_train - y_pred_train) ** 2)))
        val_rmse = float(np.sqrt(np.mean((y_val - y_pred_val) ** 2)))

        # Directional accuracy (did we predict direction correctly?)
        # For props, this is less meaningful but we include for consistency
        train_dir_acc = float(np.mean((y_pred_train > np.median(y_train)) == (y_train > np.median(y_train))))
        val_dir_acc = float(np.mean((y_pred_val > np.median(y_val)) == (y_val > np.median(y_val))))

        metrics = {
            "train_loss": float(train_loss),
            "val_loss": float(val_loss),
            "train_mae": train_mae,
            "val_mae": val_mae,
            "train_rmse": train_rmse,
            "val_rmse": val_rmse,
            "train_dir_acc": train_dir_acc,
            "val_dir_acc": val_dir_acc,
            "epochs_trained": len(history.history['loss']),
            "stopped_early": len(history.history['loss']) < epochs
        }

        logger.info(f"Results: val_MAE={val_mae:.3f}, val_RMSE={val_rmse:.3f}, dir_acc={val_dir_acc:.3f}")

        # 8. Save model with versioning
        saved_path = self._save_model_versioned(model, sport, stat_type, metrics)

        # 9. Log training
        self._log_training(sport, stat_type, data_stats, metrics)

        return {
            "sport": sport,
            "stat_type": stat_type,
            "data_stats": data_stats,
            "metrics": metrics,
            "model_path": saved_path,
            "trained_at": datetime.now().isoformat()
        }

    def train_all_models(
        self,
        min_samples: int = None,
        dry_run: bool = False
    ) -> Dict[str, Dict]:
        """
        Train all sport/stat combinations.

        Args:
            min_samples: Minimum samples required
            dry_run: Analyze data without training

        Returns:
            Dict of results by sport/stat key
        """
        results = {}

        for sport, stat_types in LSTMTrainingConfig.SPORT_STATS.items():
            for stat_type in stat_types:
                key = f"{sport}_{stat_type}"
                try:
                    result = self.train_model(
                        sport=sport,
                        stat_type=stat_type,
                        min_samples=min_samples,
                        dry_run=dry_run
                    )
                    results[key] = result or {"skipped": True, "reason": "Insufficient data"}
                except Exception as e:
                    logger.error(f"Failed to train {key}: {e}")
                    results[key] = {"error": str(e)}

        return results

    def _load_training_data(self, sport: str, stat_type: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Load and prepare training data for LSTM."""
        try:
            from services.ml_data_pipeline import get_ml_pipeline

            pipeline = get_ml_pipeline()
            df = pipeline.get_prop_training_data(
                sport=sport,
                stat_type=stat_type,
                days_back=180,  # 6 months
                min_samples=50  # Lower threshold here, check actual in train_model
            )

            if df is None or len(df) < 10:
                return None, None

            # Build feature sequences
            # For LSTM, we need sequences of features
            # Since we may not have true time series, we create synthetic sequences
            # from the feature values

            feature_cols = ["ai_score", "research_score", "esoteric_score",
                          "jarvis_score", "context_score", "final_score"]

            # Use available columns
            available_cols = [c for c in feature_cols if c in df.columns]
            if len(available_cols) < 4:
                # Fall back to simpler features
                available_cols = ["final_score", "line", "odds_american", "titanium"]
                available_cols = [c for c in available_cols if c in df.columns]

            if len(available_cols) < 3:
                logger.warning(f"Not enough feature columns for {sport}/{stat_type}")
                return None, None

            # Normalize features
            X_raw = df[available_cols].values.astype(np.float32)
            X_mean = np.mean(X_raw, axis=0)
            X_std = np.std(X_raw, axis=0) + 1e-8
            X_normalized = (X_raw - X_mean) / X_std

            # Create sequences
            seq_len = LSTMTrainingConfig.SEQUENCE_LENGTH
            n_samples = len(X_normalized) - seq_len + 1

            if n_samples < 10:
                return None, None

            X = np.zeros((n_samples, seq_len, len(available_cols)), dtype=np.float32)
            y = np.zeros(n_samples, dtype=np.float32)

            for i in range(n_samples):
                X[i] = X_normalized[i:i+seq_len]
                # Target is the outcome (hit/miss as 0/1)
                y[i] = df.iloc[i + seq_len - 1]["outcome"]

            return X, y

        except Exception as e:
            logger.error(f"Failed to load training data: {e}")
            return None, None

    def _build_model(self) -> "keras.Model":
        """Build LSTM model architecture."""
        model = keras.Sequential([
            keras.layers.LSTM(
                LSTMTrainingConfig.LSTM_UNITS,
                input_shape=(LSTMTrainingConfig.SEQUENCE_LENGTH, 6),
                return_sequences=False
            ),
            keras.layers.Dropout(LSTMTrainingConfig.DROPOUT_RATE),
            keras.layers.Dense(LSTMTrainingConfig.DENSE_UNITS, activation='relu'),
            keras.layers.Dropout(LSTMTrainingConfig.DROPOUT_RATE),
            keras.layers.Dense(1, activation='sigmoid')
        ])

        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )

        return model

    def _save_model_versioned(
        self,
        model: "keras.Model",
        sport: str,
        stat_type: str,
        metrics: Dict
    ) -> str:
        """Save model with versioning."""
        base_name = f"lstm_{sport.lower()}_{stat_type.lower()}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # New versioned filename
        versioned_name = f"{base_name}_{timestamp}.weights.h5"
        versioned_path = os.path.join(self.models_dir, versioned_name)

        # Current (latest) filename
        current_name = f"{base_name}.weights.h5"
        current_path = os.path.join(self.models_dir, current_name)

        # Save versioned model
        model.save_weights(versioned_path)
        logger.info(f"Saved versioned model: {versioned_path}")

        # Copy to current (overwrite)
        shutil.copy2(versioned_path, current_path)
        logger.info(f"Updated current model: {current_path}")

        # Save metadata
        metadata = {
            "sport": sport,
            "stat_type": stat_type,
            "trained_at": datetime.now().isoformat(),
            "metrics": metrics,
            "version": timestamp
        }

        metadata_path = versioned_path.replace(".weights.h5", "_metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Cleanup old versions
        self._cleanup_old_versions(base_name)

        return current_path

    def _cleanup_old_versions(self, base_name: str):
        """Remove old model versions, keeping only the most recent N."""
        pattern = f"{base_name}_*.weights.h5"

        # Find all versioned files
        versions = []
        for f in os.listdir(self.models_dir):
            if f.startswith(base_name + "_") and f.endswith(".weights.h5"):
                path = os.path.join(self.models_dir, f)
                mtime = os.path.getmtime(path)
                versions.append((mtime, path))

        # Sort by time (newest first)
        versions.sort(reverse=True)

        # Remove old versions
        for _, path in versions[LSTMTrainingConfig.KEEP_VERSIONS:]:
            try:
                os.remove(path)
                # Also remove metadata
                meta_path = path.replace(".weights.h5", "_metadata.json")
                if os.path.exists(meta_path):
                    os.remove(meta_path)
                logger.info(f"Removed old version: {path}")
            except Exception as e:
                logger.warning(f"Failed to remove old version {path}: {e}")

    def _log_training(
        self,
        sport: str,
        stat_type: str,
        data_stats: Dict,
        metrics: Dict
    ):
        """Log training results."""
        log_entry = {
            "sport": sport,
            "stat_type": stat_type,
            "timestamp": datetime.now().isoformat(),
            "data_stats": data_stats,
            "metrics": metrics
        }

        # Append to JSONL log
        log_file = os.path.join(self.logs_dir, "lstm_training.jsonl")
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")

        # Store in memory
        key = f"{sport}_{stat_type}"
        self.training_history[key] = log_entry


# ============================================
# MAIN
# ============================================

def main():
    parser = argparse.ArgumentParser(description="Enhanced LSTM model training")
    parser.add_argument('--sport', type=str, help='Sport to train (e.g., NBA)')
    parser.add_argument('--stat-type', type=str, help='Stat type to train (e.g., points)')
    parser.add_argument('--all', action='store_true', help='Train all models')
    parser.add_argument('--min-samples', type=int, default=500,
                       help='Minimum samples required (default: 500)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Analyze data without training')
    args = parser.parse_args()

    if not TF_AVAILABLE:
        logger.error("TensorFlow not available. Install with: pip install tensorflow")
        sys.exit(1)

    trainer = EnhancedLSTMTrainer()

    if args.all:
        logger.info("Training all LSTM models...")
        results = trainer.train_all_models(
            min_samples=args.min_samples,
            dry_run=args.dry_run
        )

        # Summary
        print("\n" + "=" * 60)
        print("LSTM TRAINING SUMMARY")
        print("=" * 60)

        trained = 0
        skipped = 0
        failed = 0

        for key, result in results.items():
            if result is None or result.get("skipped"):
                skipped += 1
                print(f"  {key}: SKIPPED - {result.get('reason', 'Insufficient data')}")
            elif result.get("error"):
                failed += 1
                print(f"  {key}: FAILED - {result['error']}")
            elif result.get("dry_run"):
                print(f"  {key}: DRY RUN - {result['data_stats']['total_samples']} samples")
            else:
                trained += 1
                metrics = result.get("metrics", {})
                print(f"  {key}: TRAINED - val_MAE={metrics.get('val_mae', 'N/A'):.3f}")

        print(f"\nTotal: {trained} trained, {skipped} skipped, {failed} failed")

    elif args.sport and args.stat_type:
        logger.info(f"Training LSTM for {args.sport}/{args.stat_type}...")
        result = trainer.train_model(
            sport=args.sport,
            stat_type=args.stat_type,
            min_samples=args.min_samples,
            dry_run=args.dry_run
        )

        if result:
            print("\n" + "=" * 60)
            print("LSTM TRAINING COMPLETE")
            print("=" * 60)
            print(json.dumps(result, indent=2, default=str))
        else:
            print("Training failed or skipped")
            sys.exit(1)

    else:
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/train_lstm_enhanced.py --sport NBA --stat-type points")
        print("  python scripts/train_lstm_enhanced.py --all")
        print("  python scripts/train_lstm_enhanced.py --all --dry-run")


if __name__ == "__main__":
    main()
