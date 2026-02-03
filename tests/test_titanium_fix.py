"""
Unit tests for Titanium 3-of-4 rule (FIX 2)

RULE: titanium=true ONLY when >= 3 of 4 engines >= 8.0
"""

import pytest
from core.titanium import compute_titanium_flag


def test_titanium_1_of_4_must_be_false():
    """1/4 engines >= 8.0 -> titanium MUST be false"""
    titanium, diag = compute_titanium_flag(
        ai_score=8.5,
        research_score=6.0,
        esoteric_score=5.0,
        jarvis_score=4.0
    )
    assert titanium is False, "1/4 must NOT trigger Titanium"
    assert diag["titanium_hits_count"] == 1
    assert diag["titanium"] is False
    assert "Only 1/4" in diag["titanium_reason"]


def test_titanium_2_of_4_must_be_false():
    """2/4 engines >= 8.0 -> titanium MUST be false"""
    titanium, diag = compute_titanium_flag(
        ai_score=8.5,
        research_score=8.2,
        esoteric_score=6.0,
        jarvis_score=5.0
    )
    assert titanium is False, "2/4 must NOT trigger Titanium"
    assert diag["titanium_hits_count"] == 2
    assert diag["titanium"] is False


def test_titanium_3_of_4_must_be_true():
    """3/4 engines >= 8.0 -> titanium MUST be true"""
    titanium, diag = compute_titanium_flag(
        ai_score=8.5,
        research_score=8.2,
        esoteric_score=8.1,
        jarvis_score=7.0
    )
    assert titanium is True, "3/4 MUST trigger Titanium"
    assert diag["titanium_hits_count"] == 3
    assert diag["titanium"] is True
    assert "3/4" in diag["titanium_reason"]
    assert len(diag["titanium_engines_hit"]) == 3


def test_titanium_4_of_4_must_be_true():
    """4/4 engines >= 8.0 -> titanium MUST be true"""
    titanium, diag = compute_titanium_flag(
        ai_score=8.5,
        research_score=8.2,
        esoteric_score=8.1,
        jarvis_score=8.0
    )
    assert titanium is True, "4/4 MUST trigger Titanium"
    assert diag["titanium_hits_count"] == 4
    assert diag["titanium"] is True


def test_titanium_exact_threshold():
    """Exactly 8.0 should qualify"""
    titanium, diag = compute_titanium_flag(
        ai_score=8.0,
        research_score=8.0,
        esoteric_score=8.0,
        jarvis_score=7.9
    )
    assert titanium is True, "Exactly 8.0 qualifies (3/4)"
    assert diag["titanium_hits_count"] == 3


def test_titanium_below_threshold():
    """7.99 should NOT qualify"""
    titanium, diag = compute_titanium_flag(
        ai_score=7.99,
        research_score=7.99,
        esoteric_score=7.99,
        jarvis_score=7.99
    )
    assert titanium is False, "7.99 does NOT qualify (0/4)"
    assert diag["titanium_hits_count"] == 0


def test_titanium_diagnostics_present():
    """All diagnostic fields must be present"""
    titanium, diag = compute_titanium_flag(8.5, 8.2, 8.1, 7.0)

    # Required fields
    assert "titanium" in diag
    assert "titanium_hits_count" in diag
    assert "titanium_engines_hit" in diag
    assert "titanium_reason" in diag
    assert "titanium_threshold" in diag
    assert "engine_scores" in diag

    # Check types
    assert isinstance(diag["titanium"], bool)
    assert isinstance(diag["titanium_hits_count"], int)
    assert isinstance(diag["titanium_engines_hit"], list)
    assert isinstance(diag["titanium_reason"], str)
    assert isinstance(diag["engine_scores"], dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
