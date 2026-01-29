"""
Test: Titanium 3-of-4 rule (MANDATORY).

REQUIREMENT: titanium=True ONLY when >= 3 of 4 engines >= 8.0
Engines: AI, Research, Esoteric, Jarvis
"""

import pytest


def is_titanium(ai: float, research: float, esoteric: float, jarvis: float) -> bool:
    """
    Check if pick qualifies for Titanium tier.

    Rule: >= 3 of 4 engines must score >= 8.0
    """
    engines = [ai, research, esoteric, jarvis]
    qualifying = sum(1 for e in engines if e >= 8.0)
    return qualifying >= 3


def test_titanium_requires_3_of_4_engines():
    """Titanium requires at least 3 engines >= 8.0."""
    # 3/4 engines >= 8.0 -> TRUE
    assert is_titanium(8.5, 8.2, 8.1, 7.0) is True

    # 4/4 engines >= 8.0 -> TRUE
    assert is_titanium(8.5, 8.2, 8.1, 8.0) is True

    # 2/4 engines >= 8.0 -> FALSE
    assert is_titanium(8.5, 8.2, 7.9, 7.0) is False

    # 1/4 engines >= 8.0 -> FALSE
    assert is_titanium(8.5, 7.9, 7.8, 7.0) is False

    # 0/4 engines >= 8.0 -> FALSE
    assert is_titanium(7.9, 7.8, 7.7, 7.6) is False


def test_titanium_exactly_8_0_qualifies():
    """Exactly 8.0 counts as qualifying."""
    # All exactly 8.0 -> TRUE
    assert is_titanium(8.0, 8.0, 8.0, 8.0) is True

    # 3 exactly 8.0, one below -> TRUE
    assert is_titanium(8.0, 8.0, 8.0, 7.99) is True


def test_titanium_7_99_does_not_qualify():
    """7.99 does NOT count as qualifying (must be >= 8.0)."""
    # All 7.99 -> FALSE
    assert is_titanium(7.99, 7.99, 7.99, 7.99) is False

    # 3 at 8.0, one at 7.99 -> TRUE (3 qualify)
    assert is_titanium(8.0, 8.0, 8.0, 7.99) is True

    # 2 at 8.0, two at 7.99 -> FALSE (only 2 qualify)
    assert is_titanium(8.0, 8.0, 7.99, 7.99) is False
