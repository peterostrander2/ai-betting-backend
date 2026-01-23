"""
validators - Data Integrity Validation for Props
Version: 1.0

Provides hard guardrails that run BEFORE tiering/caps/correlation.
"""

from .prop_integrity import (
    validate_prop_integrity,
    validate_props_batch,
    REQUIRED_KEYS
)

from .injury_guard import (
    validate_injury_status,
    validate_props_batch_injury,
    build_injury_index,
    BLOCK_DOUBTFUL,
    BLOCK_GTD
)

from .market_availability import (
    validate_market_available,
    validate_props_batch_market,
    build_dk_market_index,
    build_dk_market_index_from_events
)

__all__ = [
    # Prop integrity
    "validate_prop_integrity",
    "validate_props_batch",
    "REQUIRED_KEYS",
    # Injury guard
    "validate_injury_status",
    "validate_props_batch_injury",
    "build_injury_index",
    "BLOCK_DOUBTFUL",
    "BLOCK_GTD",
    # Market availability
    "validate_market_available",
    "validate_props_batch_market",
    "build_dk_market_index",
    "build_dk_market_index_from_events",
]
