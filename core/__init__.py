"""
Core module - System invariants and single source of truth
"""

from .invariants import (
    # Titanium invariants
    TITANIUM_ENGINE_COUNT,
    TITANIUM_ENGINE_THRESHOLD,
    TITANIUM_MIN_ENGINES,
    TITANIUM_ENGINE_NAMES,

    # Score filtering
    COMMUNITY_MIN_SCORE,

    # Engine weights
    ENGINE_WEIGHT_AI,
    ENGINE_WEIGHT_RESEARCH,
    ENGINE_WEIGHT_ESOTERIC,
    ENGINE_WEIGHT_JARVIS,

    # Jarvis contract
    JARVIS_REQUIRED_FIELDS,
    JARVIS_BASELINE_FLOOR,

    # Jason Sim contract
    JASON_SIM_REQUIRED_FIELDS,

    # Time windows
    ET_TIMEZONE,
    ET_DAY_START,
    ET_DAY_END,

    # Storage
    PICK_STORAGE_REQUIRED_FIELDS,

    # Validation functions
    validate_titanium_assignment,
    validate_jarvis_output,
    validate_pick_storage,
    validate_score_threshold,
)

# Import time_et (SINGLE SOURCE OF TRUTH for ET timezone)
from .time_et import (
    now_et,
    et_day_bounds,
    is_in_et_day,
    filter_events_et,
)

# Import titanium (SINGLE SOURCE OF TRUTH for titanium flag - FIX 2)
from .titanium import compute_titanium_flag

# Import runtime modules (optional - graceful fallback if not available)
try:
    from . import scoring_pipeline
    from . import persistence
    RUNTIME_MODULES_AVAILABLE = True
except ImportError:
    RUNTIME_MODULES_AVAILABLE = False

__all__ = [
    # Invariants
    'TITANIUM_ENGINE_COUNT',
    'TITANIUM_ENGINE_THRESHOLD',
    'TITANIUM_MIN_ENGINES',
    'TITANIUM_ENGINE_NAMES',
    'COMMUNITY_MIN_SCORE',
    'JARVIS_REQUIRED_FIELDS',
    'JARVIS_BASELINE_FLOOR',
    'ET_TIMEZONE',
    'ET_DAY_START',
    'ET_DAY_END',
    'PICK_STORAGE_REQUIRED_FIELDS',
    'validate_titanium_assignment',
    'validate_jarvis_output',
    'validate_pick_storage',
    'validate_score_threshold',

    # Time handling (SINGLE SOURCE OF TRUTH)
    'now_et',
    'et_day_bounds',
    'is_in_et_day',
    'filter_events_et',

    # Titanium (SINGLE SOURCE OF TRUTH - FIX 2)
    'compute_titanium_flag',

    # Runtime modules
    'scoring_pipeline',
    'persistence',
]
