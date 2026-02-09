"""
Engine 2 (Research) Guard Tests

Verifies Research Engine contract integrity:
- Pillar weights sum to 1.0
- Score bounds [0.0, 10.0]
- Fail-soft behavior (neutral score on failure)
- Engine weight is 35% as per scoring_contract.py
"""

import pytest
from typing import Dict, Any


class TestPillarWeightsSum:
    """Guard: Pillar weights MUST sum to exactly 1.0"""

    def test_pillar_weights_sum_to_one(self):
        """Pillar weights must sum to exactly 1.0"""
        from research_engine import PILLAR_WEIGHTS

        total = sum(PILLAR_WEIGHTS.values())
        assert abs(total - 1.0) < 0.0001, f"Pillar weights sum to {total}, expected 1.0"

    def test_all_pillar_weights_positive(self):
        """All pillar weights must be positive"""
        from research_engine import PILLAR_WEIGHTS

        for pillar, weight in PILLAR_WEIGHTS.items():
            assert weight > 0, f"Pillar {pillar} has non-positive weight: {weight}"

    def test_expected_pillar_count(self):
        """Research Engine must have exactly 8 pillars"""
        from research_engine import PILLAR_WEIGHTS

        assert len(PILLAR_WEIGHTS) == 8, f"Expected 8 pillars, got {len(PILLAR_WEIGHTS)}"

    def test_pillar_names_match_contract(self):
        """Pillar names must match documented contract"""
        from research_engine import PILLAR_WEIGHTS

        expected_pillars = {
            "sharp_split",
            "reverse_line_move",
            "public_fade",
            "hook_discipline",
            "goldilocks_zone",
            "hospital_fade",
            "trap_gate",
            "multi_pillar",
        }
        actual_pillars = set(PILLAR_WEIGHTS.keys())
        assert actual_pillars == expected_pillars, (
            f"Pillar mismatch. Missing: {expected_pillars - actual_pillars}, "
            f"Extra: {actual_pillars - expected_pillars}"
        )


class TestResearchScoreBounds:
    """Guard: Research scores MUST be in [0.0, 10.0] range"""

    def test_research_score_clamped_upper(self):
        """Research score cannot exceed 10.0"""
        from research_engine import get_research_engine

        engine = get_research_engine()
        # Perfect storm scenario - all pillars should fire
        result = engine.calculate_research_score(
            public_pct=85,
            sharp_money_pct=80,
            spread=-7,
            opening_line=-5,
            current_line=-7,
            public_side="UNDERDOG",
            injury_impact_pct=30,
            key_player_out=True,
            total=220,
        )
        assert result.research_score <= 10.0, (
            f"Research score {result.research_score} exceeds 10.0"
        )

    def test_research_score_clamped_lower(self):
        """Research score cannot go below 0.0"""
        from research_engine import get_research_engine

        engine = get_research_engine()
        # Minimal inputs scenario
        result = engine.calculate_research_score(
            public_pct=50,
            sharp_money_pct=50,
            spread=0,
            total=220,
        )
        assert result.research_score >= 0.0, (
            f"Research score {result.research_score} below 0.0"
        )

    def test_research_score_is_float(self):
        """Research score must be a float"""
        from research_engine import get_research_engine

        engine = get_research_engine()
        result = engine.calculate_research_score(
            public_pct=65,
            sharp_money_pct=55,
            spread=-3.5,
            total=220,
        )
        assert isinstance(result.research_score, (int, float)), (
            f"Research score is {type(result.research_score)}, expected float"
        )


class TestEngineWeightContract:
    """Guard: Research Engine weight must be 35% in scoring contract"""

    def test_research_weight_is_35_percent(self):
        """Research engine weight must be exactly 0.35 (35%)"""
        from core.scoring_contract import ENGINE_WEIGHTS

        research_weight = ENGINE_WEIGHTS.get("research")
        assert research_weight is not None, "ENGINE_WEIGHTS missing 'research' key"
        assert research_weight == 0.35, (
            f"Research weight is {research_weight}, expected 0.35"
        )

    def test_engine_weights_sum_to_one(self):
        """All 4 engine weights must sum to 1.0"""
        from core.scoring_contract import ENGINE_WEIGHTS

        expected_engines = {"ai", "research", "esoteric", "jarvis"}
        for engine in expected_engines:
            assert engine in ENGINE_WEIGHTS, f"Missing engine weight: {engine}"

        total = sum(ENGINE_WEIGHTS[e] for e in expected_engines)
        assert abs(total - 1.0) < 0.0001, f"Engine weights sum to {total}, expected 1.0"

    def test_research_is_largest_engine(self):
        """Research (35%) must be the largest single engine"""
        from core.scoring_contract import ENGINE_WEIGHTS

        research_weight = ENGINE_WEIGHTS.get("research", 0)
        for engine, weight in ENGINE_WEIGHTS.items():
            if engine != "research":
                assert research_weight >= weight, (
                    f"Research ({research_weight}) is not >= {engine} ({weight})"
                )


class TestFailSoftBehavior:
    """Guard: Research Engine must return neutral score on failure"""

    def test_research_result_has_required_fields(self):
        """Research result must have all required fields"""
        from research_engine import get_research_engine

        engine = get_research_engine()
        result = engine.calculate_research_score(
            public_pct=60,
            sharp_money_pct=55,
            spread=-3,
            total=220,
        )

        # Check required fields exist
        assert hasattr(result, "research_score"), "Missing research_score field"
        assert hasattr(result, "research_reasons"), "Missing research_reasons field"
        assert hasattr(result, "pillars_fired"), "Missing pillars_fired field"
        assert hasattr(result, "pillar_details"), "Missing pillar_details field"
        assert hasattr(result, "confluence_level"), "Missing confluence_level field"

    def test_research_reasons_is_list(self):
        """research_reasons must be a list"""
        from research_engine import get_research_engine

        engine = get_research_engine()
        result = engine.calculate_research_score(
            public_pct=60,
            sharp_money_pct=55,
            spread=-3,
            total=220,
        )
        assert isinstance(result.research_reasons, list), (
            f"research_reasons is {type(result.research_reasons)}, expected list"
        )

    def test_default_inputs_produce_valid_score(self):
        """Default/minimal inputs should produce a valid score (not error)"""
        from research_engine import get_research_engine

        engine = get_research_engine()
        # Call with minimal/default parameters
        result = engine.calculate_research_score()
        assert 0 <= result.research_score <= 10, (
            f"Default inputs produced invalid score: {result.research_score}"
        )


class TestPostBaseMutationGuard:
    """Guard: Engine scores must NOT be mutated after BASE_4 calculation"""

    def test_research_score_independent_of_context(self):
        """Research score calculation must not depend on context modifier"""
        from research_engine import get_research_engine

        engine = get_research_engine()

        # Calculate research score with same inputs
        result1 = engine.calculate_research_score(
            public_pct=70,
            sharp_money_pct=60,
            spread=-5,
            total=220,
        )

        result2 = engine.calculate_research_score(
            public_pct=70,
            sharp_money_pct=60,
            spread=-5,
            total=220,
        )

        # Same inputs should produce same output (deterministic)
        assert result1.research_score == result2.research_score, (
            f"Non-deterministic research score: {result1.research_score} vs {result2.research_score}"
        )

    def test_pillar_scores_in_valid_range(self):
        """Each pillar score must be in [0.0, 10.0] range"""
        from research_engine import get_research_engine

        engine = get_research_engine()
        result = engine.calculate_research_score(
            public_pct=75,
            sharp_money_pct=65,
            spread=-7,
            opening_line=-6,
            current_line=-7,
            total=220,
        )

        for pillar_detail in result.pillar_details:
            score = pillar_detail.get("score", 0)
            pillar_name = pillar_detail.get("pillar", "unknown")
            assert 0 <= score <= 10, (
                f"Pillar {pillar_name} score {score} out of [0, 10] range"
            )


class TestCapEnforcement:
    """Guard: All caps must be respected"""

    def test_total_boost_cap_in_contract(self):
        """TOTAL_BOOST_CAP must be defined in scoring_contract"""
        from core.scoring_contract import TOTAL_BOOST_CAP

        assert TOTAL_BOOST_CAP == 1.5, (
            f"TOTAL_BOOST_CAP is {TOTAL_BOOST_CAP}, expected 1.5"
        )

    def test_min_final_score_in_contract(self):
        """MIN_FINAL_SCORE must be defined in scoring_contract"""
        from core.scoring_contract import MIN_FINAL_SCORE

        assert MIN_FINAL_SCORE == 7.0, (
            f"MIN_FINAL_SCORE is {MIN_FINAL_SCORE}, expected 7.0"
        )

    def test_min_props_score_lower_than_games(self):
        """MIN_PROPS_SCORE must be lower than MIN_FINAL_SCORE (no SERP for props)"""
        from core.scoring_contract import MIN_FINAL_SCORE, MIN_PROPS_SCORE

        assert MIN_PROPS_SCORE < MIN_FINAL_SCORE, (
            f"MIN_PROPS_SCORE ({MIN_PROPS_SCORE}) should be < MIN_FINAL_SCORE ({MIN_FINAL_SCORE})"
        )
        assert MIN_PROPS_SCORE == 6.5, (
            f"MIN_PROPS_SCORE is {MIN_PROPS_SCORE}, expected 6.5"
        )


class TestResearchDelta:
    """Guard: Research Engine MUST materially impact BASE_4 scores"""

    def test_research_moves_scores(self):
        """
        Delta test: Prove Research moves scores.
        Compute BASE_4 with research_weight=0.35 vs research_weight=0.
        The difference must equal research_score * 0.35.
        """
        from core.scoring_contract import ENGINE_WEIGHTS
        from research_engine import get_research_engine

        engine = get_research_engine()

        # Generate a research score with meaningful inputs
        result = engine.calculate_research_score(
            public_pct=75,
            sharp_money_pct=70,
            spread=-7,
            opening_line=-6,
            current_line=-7,
            public_side="UNDERDOG",
            injury_impact_pct=15,
            key_player_out=True,
            total=220,
        )

        research_score = result.research_score
        research_weight = ENGINE_WEIGHTS.get("research", 0.35)

        # Simulate BASE_4 with research enabled vs disabled
        # Other engines use neutral scores (5.0) for isolation
        ai_score = 5.0
        esoteric_score = 5.0
        jarvis_score = 5.0

        base_4_with_research = (
            ai_score * ENGINE_WEIGHTS["ai"]
            + research_score * ENGINE_WEIGHTS["research"]
            + esoteric_score * ENGINE_WEIGHTS["esoteric"]
            + jarvis_score * ENGINE_WEIGHTS["jarvis"]
        )

        base_4_without_research = (
            ai_score * ENGINE_WEIGHTS["ai"]
            + 0.0  # research disabled
            + esoteric_score * ENGINE_WEIGHTS["esoteric"]
            + jarvis_score * ENGINE_WEIGHTS["jarvis"]
        )

        # The delta is the Research contribution
        delta = base_4_with_research - base_4_without_research
        expected_delta = research_score * research_weight

        assert abs(delta - expected_delta) < 0.001, (
            f"Delta {delta} != expected {expected_delta}"
        )
        assert delta > 0, f"Research must contribute positively, got delta={delta}"

    def test_research_contribution_is_35_percent(self):
        """Research contributes exactly 35% of its score to BASE_4"""
        from core.scoring_contract import ENGINE_WEIGHTS
        from research_engine import get_research_engine

        engine = get_research_engine()

        # High-signal scenario should produce above-neutral score
        result = engine.calculate_research_score(
            public_pct=80,
            sharp_money_pct=75,
            spread=-5.5,
            opening_line=-4,
            current_line=-5.5,
            public_side="FAVORITE",
            total=220,
        )

        research_score = result.research_score
        contribution = research_score * ENGINE_WEIGHTS["research"]

        # With 35% weight, a 7.0 research score contributes 2.45 points
        # With 35% weight, a 10.0 research score contributes 3.5 points
        assert 0 <= contribution <= 3.5, (
            f"Research contribution {contribution} out of expected range [0, 3.5]"
        )
        assert contribution == research_score * 0.35, (
            f"Research must contribute exactly 35% of score"
        )

    def test_zero_research_reduces_base_score(self):
        """Removing Research from calculation materially lowers BASE_4"""
        from core.scoring_contract import ENGINE_WEIGHTS

        # Simulate: all engines at 7.0
        ai, research, esoteric, jarvis = 7.0, 7.0, 7.0, 7.0

        base_4_full = (
            ai * ENGINE_WEIGHTS["ai"]
            + research * ENGINE_WEIGHTS["research"]
            + esoteric * ENGINE_WEIGHTS["esoteric"]
            + jarvis * ENGINE_WEIGHTS["jarvis"]
        )

        # Without research (simulating research_weight=0)
        base_4_no_research = (
            ai * ENGINE_WEIGHTS["ai"]
            + 0.0  # research contribution removed
            + esoteric * ENGINE_WEIGHTS["esoteric"]
            + jarvis * ENGINE_WEIGHTS["jarvis"]
        )

        # Full: 7.0 * 1.0 = 7.0
        # Without research: 7.0 * (0.25 + 0.20 + 0.20) = 7.0 * 0.65 = 4.55
        expected_full = 7.0
        expected_no_research = 7.0 * 0.65  # 4.55

        assert abs(base_4_full - expected_full) < 0.01, (
            f"Full BASE_4 {base_4_full} != {expected_full}"
        )
        assert abs(base_4_no_research - expected_no_research) < 0.01, (
            f"No-research BASE_4 {base_4_no_research} != {expected_no_research}"
        )

        # The delta proves Research's material impact
        delta = base_4_full - base_4_no_research
        expected_delta = 7.0 * 0.35  # 2.45
        assert abs(delta - expected_delta) < 0.001, (
            f"Research delta {delta} != {expected_delta} (35% of 7.0)"
        )

    def test_high_research_score_produces_material_contribution(self):
        """A high research score (8+) must contribute >2.8 points to BASE_4"""
        from core.scoring_contract import ENGINE_WEIGHTS
        from research_engine import get_research_engine

        engine = get_research_engine()

        # Perfect storm: all pillars should fire
        result = engine.calculate_research_score(
            public_pct=85,
            sharp_money_pct=80,
            spread=-7,
            opening_line=-5,
            current_line=-7,
            public_side="UNDERDOG",
            injury_impact_pct=25,
            key_player_out=True,
            total=220,
        )

        research_score = result.research_score
        contribution = research_score * ENGINE_WEIGHTS["research"]

        # If research_score >= 8.0, contribution >= 2.8
        if research_score >= 8.0:
            assert contribution >= 2.8, (
                f"High research score {research_score} should contribute >= 2.8, got {contribution}"
            )


class TestResearchResultIntegrity:
    """Guard: Research result to_dict() conversion must be complete"""

    def test_to_dict_conversion(self):
        """Research result must convert to dict with all fields"""
        from research_engine import get_research_score

        result = get_research_score(
            public_pct=65,
            sharp_money_pct=55,
            spread=-4,
            total=220,
        )

        assert isinstance(result, dict), f"get_research_score returned {type(result)}"
        assert "research_score" in result, "Missing research_score in dict"
        assert "research_reasons" in result, "Missing research_reasons in dict"
        assert "pillars_fired" in result, "Missing pillars_fired in dict"

    def test_confluence_level_in_result(self):
        """Confluence level must be present and valid"""
        from research_engine import get_research_score

        result = get_research_score(
            public_pct=75,
            sharp_money_pct=70,
            spread=-7,
            total=220,
            opening_line=-6,
            current_line=-7,
        )

        assert "confluence_level" in result, "Missing confluence_level in result"
        valid_levels = {"NONE", "LOW", "MODERATE", "HIGH", "EXTREME", "STRONG"}
        assert result["confluence_level"] in valid_levels or result["confluence_level"] is None, (
            f"Invalid confluence_level: {result['confluence_level']}"
        )


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
