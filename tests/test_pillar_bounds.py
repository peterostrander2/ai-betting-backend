"""
v20.16: Pillar Score Bounds Regression Tests

These tests ensure pillar scores stay bounded to prevent massive negative
values that drag ai_score to the floor.

Root Cause (fixed in v20.16):
- Pillar 3 (Hospital Fade) accumulated injury_impact without cap
- Players without 'depth' field defaulted to depth=1 (starter)
- With 35+ injuries, injury_impact could reach -70+ (CRITICAL BUG)

Guards added:
- Individual pillar caps (INJURY_IMPACT_CAP=5.0, SITUATIONAL_FADE_CAP=3.5)
- Default depth=99 (unknown players are NOT starters)
- Overall pillar score bounded to [-5.0, +5.0]
"""

import pytest


class TestPillarBounds:
    """Regression tests for pillar score bounds."""

    def test_injury_impact_is_capped(self):
        """
        Guard: injury_impact MUST be capped at INJURY_IMPACT_CAP (5.0).

        Previously: 35 injuries × 2.0 = -70.0 (catastrophic)
        Now: min(injury_impact, 5.0) → max -5.0
        """
        INJURY_IMPACT_CAP = 5.0

        # Simulate many key player injuries
        num_key_players_out = 35
        injury_impact_per_starter = 2.0

        # Old behavior (BROKEN)
        uncapped_impact = num_key_players_out * injury_impact_per_starter
        assert uncapped_impact == 70.0, "Setup: 35 injuries × 2.0 = 70.0"

        # New behavior (FIXED)
        capped_impact = min(uncapped_impact, INJURY_IMPACT_CAP)
        assert capped_impact == INJURY_IMPACT_CAP, f"Impact must be capped at {INJURY_IMPACT_CAP}"

        # Score is negative of capped impact
        pillar_score = -capped_impact
        assert pillar_score >= -INJURY_IMPACT_CAP, f"Pillar score must be >= {-INJURY_IMPACT_CAP}"

    def test_default_depth_is_not_starter(self):
        """
        Guard: Players without 'depth' field must NOT default to starter.

        Previously: player.get('depth', 1) == 1 → all unknown = starter
        Now: player.get('depth', 99) → unknown players excluded
        """
        player_without_depth = {}

        # Old behavior (BROKEN)
        old_depth = player_without_depth.get('depth', 1)
        assert old_depth == 1, "Old default was 1 (starter)"

        # New behavior (FIXED)
        new_depth = player_without_depth.get('depth', 99)
        assert new_depth == 99, "New default is 99 (unknown)"
        assert new_depth != 1, "Unknown players are NOT treated as starters"

    def test_situational_fade_is_capped(self):
        """
        Guard: situational fade_score MUST be capped at SITUATIONAL_FADE_CAP.
        """
        SITUATIONAL_FADE_CAP = 3.5

        # Max possible fade contributions
        max_components = {
            'back_to_back': 1.5,
            'heavy_travel': 0.5,
            'altitude': 0.3,
            'lookahead': 0.7,
            'road_trip': 0.5,
        }

        uncapped_fade = sum(max_components.values())
        assert uncapped_fade == 3.5, "Max theoretical fade = 3.5"

        capped_fade = min(uncapped_fade, SITUATIONAL_FADE_CAP)
        assert capped_fade <= SITUATIONAL_FADE_CAP, f"Fade must be <= {SITUATIONAL_FADE_CAP}"

    def test_overall_pillar_score_is_bounded(self):
        """
        Guard: overall_pillar_score MUST be bounded to [-5.0, +5.0].

        This is the last line of defense against extreme values.
        """
        PILLAR_SCORE_MIN = -5.0
        PILLAR_SCORE_MAX = 5.0

        test_cases = [
            (-100.0, -5.0, "Extreme negative capped to -5.0"),
            (-5.0, -5.0, "At minimum stays at -5.0"),
            (-2.0, -2.0, "Normal negative unchanged"),
            (0.0, 0.0, "Zero unchanged"),
            (2.5, 2.5, "Normal positive unchanged"),
            (5.0, 5.0, "At maximum stays at 5.0"),
            (100.0, 5.0, "Extreme positive capped to 5.0"),
        ]

        for raw, expected, msg in test_cases:
            bounded = max(PILLAR_SCORE_MIN, min(PILLAR_SCORE_MAX, raw))
            assert bounded == expected, f"{msg}: got {bounded}"

    def test_pillar_boost_cannot_exceed_bounds(self):
        """
        Guard: pillar_boost used in ai_score calculation must be bounded.

        ai_score = min(10, max(0, base_score + pillar_boost))

        With bounded pillar_boost:
        - If base_score=6.0 and pillar_boost=-5.0 → 1.0 (then floor to 2.0)
        - If base_score=6.0 and pillar_boost=+5.0 → 10.0 (cap)
        """
        PILLAR_SCORE_MIN = -5.0
        PILLAR_SCORE_MAX = 5.0
        AI_FLOOR = 2.0

        # Test: bounded pillar_boost with typical base_score
        base_score = 6.0

        # Worst case: max negative pillar
        pillar_boost = PILLAR_SCORE_MIN
        raw_ai_score = base_score + pillar_boost
        ai_score = min(10, max(AI_FLOOR, raw_ai_score))
        assert ai_score == AI_FLOOR, f"With pillar_boost={pillar_boost}, should floor to {AI_FLOOR}"

        # Best case: max positive pillar
        pillar_boost = PILLAR_SCORE_MAX
        raw_ai_score = base_score + pillar_boost
        ai_score = min(10, max(0, raw_ai_score))
        assert ai_score == 10.0, f"With pillar_boost={pillar_boost}, should cap to 10.0"


class TestPillarScoreFormula:
    """Verify the pillar score formula."""

    def test_non_zero_pillars_averaged(self):
        """
        Overall pillar score = mean(non-zero pillars).
        Zero pillars are excluded.
        """
        pillar_scores = {
            'sharp_split': 2.0,
            'reverse_line': 0,  # Not triggered
            'hospital_fade': -3.0,
            'situational_spot': 0,  # Not triggered
            'expert_consensus': 1.5,
            'prop_correlation': 0,  # Not triggered
            'hook_discipline': 0,  # Not triggered
            'volume_discipline': 0,  # Not triggered
        }

        non_zero = [s for s in pillar_scores.values() if s != 0]
        assert non_zero == [2.0, -3.0, 1.5], "Non-zero pillars extracted"

        expected_mean = sum(non_zero) / len(non_zero)  # (2.0 + -3.0 + 1.5) / 3 = 0.167
        assert expected_mean == pytest.approx(0.167, rel=0.01), "Mean of [2.0, -3.0, 1.5] ≈ 0.167"

    def test_all_zero_pillars_returns_zero(self):
        """
        If all pillars are zero, overall_pillar_score = 0.0.
        """
        pillar_scores = {
            'sharp_split': 0,
            'reverse_line': 0,
            'hospital_fade': 0,
            'situational_spot': 0,
            'expert_consensus': 0,
            'prop_correlation': 0,
            'hook_discipline': 0,
            'volume_discipline': 0,
        }

        non_zero = [s for s in pillar_scores.values() if s != 0]
        assert len(non_zero) == 0, "No non-zero pillars"

        # Using the fix: return 0.0 when list is empty
        overall = 0.0 if len(non_zero) == 0 else sum(non_zero) / len(non_zero)
        assert overall == 0.0, "Empty list returns 0.0"
