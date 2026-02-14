# services/__init__.py
# Service modules for AI Betting Backend (v18.1)

# v20.23: Wrap in try/except to avoid import failures when sqlalchemy unavailable
try:
    from .officials_tracker import OfficialsTracker, officials_tracker
    OFFICIALS_TRACKER_AVAILABLE = True
except ImportError:
    OFFICIALS_TRACKER_AVAILABLE = False
    OfficialsTracker = None
    officials_tracker = None

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

# v20.23: Player Data Service for unified NBA player context
try:
    from .player_data_service import (
        PlayerDataService,
        PlayerContext,
        calculate_line_difficulty,
    )
    PLAYER_DATA_SERVICE_AVAILABLE = True
except ImportError:
    PLAYER_DATA_SERVICE_AVAILABLE = False
    PlayerDataService = None
    PlayerContext = None
    calculate_line_difficulty = None

__all__ = [
    "OfficialsTracker",
    "officials_tracker",
    "OFFICIALS_TRACKER_AVAILABLE",
    # v18.1
    "MLDataPipeline",
    "get_ml_pipeline",
    "get_training_data",
    "get_data_stats",
    "ML_PIPELINE_AVAILABLE",
    # v20.23
    "PlayerDataService",
    "PlayerContext",
    "calculate_line_difficulty",
    "PLAYER_DATA_SERVICE_AVAILABLE",
]
