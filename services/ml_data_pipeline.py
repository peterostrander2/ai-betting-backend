"""
ML Data Pipeline - Training Data Preparation (v18.1)
=====================================================

Prepares enriched training data for LSTM and Ensemble model retraining.
Loads graded predictions and adds contextual features from various sources.

Usage:
    from services.ml_data_pipeline import MLDataPipeline

    pipeline = MLDataPipeline()
    df = pipeline.get_training_data(
        sport="NBA",
        min_final_score=6.5,
        days_back=90
    )
"""

import os
import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import pandas/numpy
try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas/numpy not available - ML data pipeline disabled")


class MLDataPipeline:
    """
    Prepares training data with enrichment for ML model retraining.

    Features:
    - Load graded predictions from JSONL storage
    - Filter by sport, date range, score thresholds
    - Add contextual features (weather, rest days, officials)
    - Add outcome labels (hit/miss)
    - Return clean DataFrame ready for training
    """

    def __init__(self, predictions_path: str = None):
        """
        Initialize the ML data pipeline.

        Args:
            predictions_path: Path to predictions JSONL file.
                            Defaults to /data/grader/predictions.jsonl
        """
        if predictions_path is None:
            # Use Railway volume or local fallback
            base_dir = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")
            predictions_path = os.path.join(base_dir, "grader", "predictions.jsonl")

        self.predictions_path = predictions_path
        self._cache = {}
        self._cache_time = None
        self._cache_ttl = 300  # 5 minute cache

    def get_training_data(
        self,
        sport: str = None,
        start_date: date = None,
        end_date: date = None,
        days_back: int = 90,
        min_final_score: float = 6.5,
        pick_type: str = None,
        include_context: bool = True
    ) -> Optional["pd.DataFrame"]:
        """
        Get enriched training data for ML models.

        Args:
            sport: Filter to specific sport (NBA, NFL, etc.)
            start_date: Start date for training window
            end_date: End date for training window
            days_back: Days back from today (if start_date not specified)
            min_final_score: Minimum final_score to include
            pick_type: Filter to PROP, SPREAD, TOTAL, or MONEYLINE
            include_context: Whether to add contextual features

        Returns:
            DataFrame with features and labels, or None if unavailable
        """
        if not PANDAS_AVAILABLE:
            logger.warning("pandas not available - cannot prepare training data")
            return None

        # Load raw predictions
        predictions = self._load_predictions()
        if not predictions:
            logger.warning("No predictions found")
            return None

        # Calculate date range
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=days_back)

        # Filter predictions
        filtered = self._filter_predictions(
            predictions=predictions,
            sport=sport,
            start_date=start_date,
            end_date=end_date,
            min_final_score=min_final_score,
            pick_type=pick_type
        )

        if not filtered:
            logger.warning("No predictions after filtering")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(filtered)

        # Add outcome labels
        df = self._add_outcome_labels(df)

        # Add contextual features if requested
        if include_context:
            df = self._add_contextual_features(df)

        # Clean up and return
        df = self._clean_dataframe(df)

        logger.info(
            "Training data prepared: %d samples, %d features, sport=%s",
            len(df), len(df.columns), sport or "ALL"
        )

        return df

    def get_prop_training_data(
        self,
        sport: str = None,
        stat_type: str = None,
        days_back: int = 90,
        min_samples: int = 100
    ) -> Optional["pd.DataFrame"]:
        """
        Get training data specifically for LSTM prop models.

        Args:
            sport: Sport filter
            stat_type: Stat type filter (points, assists, etc.)
            days_back: Training window
            min_samples: Minimum samples required

        Returns:
            DataFrame with prop-specific features
        """
        df = self.get_training_data(
            sport=sport,
            days_back=days_back,
            pick_type="PROP",
            include_context=True
        )

        if df is None or len(df) < min_samples:
            return None

        # Filter by stat type if specified
        if stat_type:
            stat_lower = stat_type.lower()
            df = df[df['market'].str.lower().str.contains(stat_lower, na=False)]

        if len(df) < min_samples:
            return None

        return df

    def get_game_training_data(
        self,
        sport: str = None,
        days_back: int = 90,
        min_samples: int = 100
    ) -> Optional["pd.DataFrame"]:
        """
        Get training data for ensemble game pick model.

        Args:
            sport: Sport filter
            days_back: Training window
            min_samples: Minimum samples required

        Returns:
            DataFrame with game pick features
        """
        # Get spread, total, and moneyline picks
        all_data = []

        for pick_type in ["SPREAD", "TOTAL", "MONEYLINE"]:
            df = self.get_training_data(
                sport=sport,
                days_back=days_back,
                pick_type=pick_type,
                include_context=True
            )
            if df is not None and len(df) > 0:
                all_data.append(df)

        if not all_data:
            return None

        df = pd.concat(all_data, ignore_index=True)

        if len(df) < min_samples:
            return None

        return df

    def get_data_stats(self) -> Dict[str, Any]:
        """
        Get statistics about available training data.

        Returns:
            Dict with counts by sport, pick_type, graded status
        """
        predictions = self._load_predictions()

        if not predictions:
            return {"total": 0, "by_sport": {}, "by_pick_type": {}, "graded": 0}

        stats = {
            "total": len(predictions),
            "by_sport": {},
            "by_pick_type": {},
            "graded": 0,
            "wins": 0,
            "losses": 0,
            "pending": 0
        }

        for p in predictions:
            # By sport
            sport = p.get("sport", "UNKNOWN").upper()
            stats["by_sport"][sport] = stats["by_sport"].get(sport, 0) + 1

            # By pick type
            pick_type = p.get("pick_type", p.get("market_type", "UNKNOWN")).upper()
            stats["by_pick_type"][pick_type] = stats["by_pick_type"].get(pick_type, 0) + 1

            # Grading status
            grade_status = p.get("grade_status", "").upper()
            if grade_status == "GRADED":
                stats["graded"] += 1
                result = p.get("result", p.get("grade_result", "")).upper()
                if result in ["WIN", "HIT", "1"]:
                    stats["wins"] += 1
                elif result in ["LOSS", "MISS", "0"]:
                    stats["losses"] += 1
            else:
                stats["pending"] += 1

        # Calculate hit rate
        if stats["wins"] + stats["losses"] > 0:
            stats["hit_rate"] = stats["wins"] / (stats["wins"] + stats["losses"])
        else:
            stats["hit_rate"] = None

        return stats

    def _load_predictions(self) -> List[Dict]:
        """Load predictions from JSONL file with caching."""
        # Check cache
        now = datetime.now()
        if (self._cache_time and
            (now - self._cache_time).total_seconds() < self._cache_ttl and
            self._cache.get("predictions")):
            return self._cache["predictions"]

        predictions = []

        if not os.path.exists(self.predictions_path):
            logger.warning("Predictions file not found: %s", self.predictions_path)
            return predictions

        try:
            with open(self.predictions_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        pred = json.loads(line)
                        predictions.append(pred)
                    except json.JSONDecodeError:
                        continue

            # Update cache
            self._cache["predictions"] = predictions
            self._cache_time = now

            logger.debug("Loaded %d predictions from %s", len(predictions), self.predictions_path)

        except Exception as e:
            logger.error("Failed to load predictions: %s", e)

        return predictions

    def _filter_predictions(
        self,
        predictions: List[Dict],
        sport: str = None,
        start_date: date = None,
        end_date: date = None,
        min_final_score: float = None,
        pick_type: str = None
    ) -> List[Dict]:
        """Filter predictions based on criteria."""
        filtered = []

        for p in predictions:
            # Sport filter
            if sport:
                pred_sport = p.get("sport", "").upper()
                if pred_sport != sport.upper():
                    continue

            # Date filter
            if start_date or end_date:
                pred_date_str = p.get("created_at", p.get("game_date", ""))
                if pred_date_str:
                    try:
                        if isinstance(pred_date_str, str):
                            pred_date = datetime.fromisoformat(pred_date_str.replace("Z", "+00:00")).date()
                        else:
                            pred_date = pred_date_str

                        if start_date and pred_date < start_date:
                            continue
                        if end_date and pred_date > end_date:
                            continue
                    except:
                        continue

            # Score filter
            if min_final_score:
                final_score = p.get("final_score", 0)
                if final_score < min_final_score:
                    continue

            # Pick type filter
            if pick_type:
                pred_type = p.get("pick_type", p.get("market_type", "")).upper()
                if pick_type.upper() not in pred_type:
                    continue

            # Must be graded
            grade_status = p.get("grade_status", "").upper()
            if grade_status != "GRADED":
                continue

            filtered.append(p)

        return filtered

    def _add_outcome_labels(self, df: "pd.DataFrame") -> "pd.DataFrame":
        """Add hit/miss outcome labels."""

        def get_outcome(row):
            result = str(row.get("result", row.get("grade_result", ""))).upper()
            if result in ["WIN", "HIT", "1"]:
                return 1
            elif result in ["LOSS", "MISS", "0"]:
                return 0
            else:
                return np.nan

        df["outcome"] = df.apply(get_outcome, axis=1)

        # Drop rows without valid outcome
        df = df.dropna(subset=["outcome"])
        df["outcome"] = df["outcome"].astype(int)

        return df

    def _add_contextual_features(self, df: "pd.DataFrame") -> "pd.DataFrame":
        """Add contextual features for enrichment."""

        # Days since created (recency)
        def days_since(created_at):
            try:
                if isinstance(created_at, str):
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                else:
                    dt = created_at
                return (datetime.now(dt.tzinfo) - dt).days
            except:
                return np.nan

        if "created_at" in df.columns:
            df["days_ago"] = df["created_at"].apply(days_since)

        # Encode categorical variables
        if "sport" in df.columns:
            sport_map = {"NBA": 0, "NFL": 1, "MLB": 2, "NHL": 3, "NCAAB": 4}
            df["sport_encoded"] = df["sport"].str.upper().map(sport_map).fillna(0).astype(int)

        if "pick_type" in df.columns or "market_type" in df.columns:
            type_col = "pick_type" if "pick_type" in df.columns else "market_type"
            type_map = {"PROP": 0, "SPREAD": 1, "TOTAL": 2, "MONEYLINE": 3}
            df["pick_type_encoded"] = (
                df[type_col].str.upper()
                .apply(lambda x: next((v for k, v in type_map.items() if k in str(x)), 3))
            )

        # Extract side encoding
        if "side" in df.columns or "pick_side" in df.columns:
            side_col = "side" if "side" in df.columns else "pick_side"

            def encode_side(side):
                side_upper = str(side).upper()
                if "OVER" in side_upper:
                    return 0
                elif "UNDER" in side_upper:
                    return 1
                elif "HOME" in side_upper:
                    return 2
                else:
                    return 3

            df["side_encoded"] = df[side_col].apply(encode_side)

        # Titanium flag
        if "titanium_triggered" in df.columns:
            df["titanium"] = df["titanium_triggered"].astype(int)
        elif "titanium" not in df.columns:
            df["titanium"] = 0

        return df

    def _clean_dataframe(self, df: "pd.DataFrame") -> "pd.DataFrame":
        """Clean and prepare final DataFrame."""

        # Define feature columns we want to keep
        feature_cols = [
            # Engine scores
            "ai_score", "research_score", "esoteric_score", "jarvis_score",
            "context_score", "final_score",

            # Boosts
            "confluence_boost", "jason_sim_boost",

            # Bet details
            "line", "odds_american", "odds",

            # Encoded categoricals
            "sport_encoded", "pick_type_encoded", "side_encoded",

            # Flags
            "titanium", "titanium_triggered",

            # Context
            "days_ago",

            # Label
            "outcome"
        ]

        # Keep columns that exist
        cols_to_keep = [c for c in feature_cols if c in df.columns]

        # Also keep metadata for reference
        metadata_cols = ["prediction_id", "sport", "pick_type", "market_type", "created_at"]
        for col in metadata_cols:
            if col in df.columns and col not in cols_to_keep:
                cols_to_keep.append(col)

        df = df[cols_to_keep].copy()

        # Fill missing numeric values
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].fillna(0)

        return df


# Global singleton instance
_ml_pipeline: Optional[MLDataPipeline] = None


def get_ml_pipeline() -> MLDataPipeline:
    """Get or create the global ML data pipeline instance."""
    global _ml_pipeline
    if _ml_pipeline is None:
        _ml_pipeline = MLDataPipeline()
    return _ml_pipeline


# Convenience functions
def get_training_data(**kwargs) -> Optional["pd.DataFrame"]:
    """Wrapper for MLDataPipeline.get_training_data()"""
    return get_ml_pipeline().get_training_data(**kwargs)


def get_data_stats() -> Dict[str, Any]:
    """Wrapper for MLDataPipeline.get_data_stats()"""
    return get_ml_pipeline().get_data_stats()
