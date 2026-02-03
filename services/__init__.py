# services/__init__.py
# Service modules for AI Betting Backend (v18.1)

from .officials_tracker import OfficialsTracker, officials_tracker

# v18.1: ML Data Pipeline
try:
    from .ml_data_pipeline import MLDataPipeline, get_ml_pipeline, get_training_data, get_data_stats
    ML_PIPELINE_AVAILABLE = True
except ImportError:
    ML_PIPELINE_AVAILABLE = False
    MLDataPipeline = None
    get_ml_pipeline = None
    get_training_data = None
    get_data_stats = None

__all__ = [
    "OfficialsTracker",
    "officials_tracker",
    # v18.1
    "MLDataPipeline",
    "get_ml_pipeline",
    "get_training_data",
    "get_data_stats",
    "ML_PIPELINE_AVAILABLE",
]
