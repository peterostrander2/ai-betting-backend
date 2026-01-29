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

__all__ = [
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
]
