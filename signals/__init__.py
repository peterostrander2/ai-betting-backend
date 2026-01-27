"""
SIGNALS MODULE - Centralized Signal Calculations
=================================================
v14.11 - Single-calculation policy for signals

This module provides centralized signal calculations to prevent
double-counting across engines.

Modules:
- public_fade: Public betting fade signal (Research Engine owns boost)
"""

from .public_fade import (
    calculate_public_fade,
    get_public_fade_context,
    PublicFadeSignal,
)

__all__ = [
    "calculate_public_fade",
    "get_public_fade_context",
    "PublicFadeSignal",
]
