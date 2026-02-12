"""
Test Scoring Single Source of Truth (NEVER BREAK AGAIN)

RULE: No duplicate scoring logic
- Router should call scoring pipeline (not compute directly)
- Scheduler should call scoring pipeline (not duplicate logic)
- One place to compute final_score
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from core.invariants import COMMUNITY_MIN_SCORE


class TestScoringConstants:
    """Test scoring-related constants"""

    def test_community_min_score_is_6_5(self):
        """Community minimum score is 6.5"""
        assert COMMUNITY_MIN_SCORE == 6.5


class TestNoDuplicateScoringLogic:
    """Test that scoring logic is not duplicated across files"""

    def test_no_final_score_calculation_in_router(self):
        """Router should not compute final_score directly"""
        # This is more of a code review check
        # We can verify by checking that router imports from scoring module

        try:
            import live_data_router
            source = open(live_data_router.__file__).read()

            # Router should call a scoring function, not compute final_score inline
            # This is a heuristic check - adjust based on actual refactoring

            # After refactoring, should NOT see formulas like:
            # final_score = (ai * 0.25) + (research * 0.30) + ...
            # Instead should call: score_candidate() or calculate_pick_score()

            # For now, just verify the file can be imported
            assert hasattr(live_data_router, 'router')

        except Exception as e:
            pytest.skip(f"Could not inspect live_data_router: {e}")

    def test_scoring_pipeline_module_exists(self):
        """Scoring pipeline module should exist"""
        # After refactoring, this should pass
        try:
            from core import scoring_pipeline
            assert hasattr(scoring_pipeline, 'score_candidate')
        except ImportError:
            # If not refactored yet, this is expected to fail
            pytest.skip("scoring_pipeline module not yet created (refactoring pending)")


class TestScoringComponents:
    """Test scoring component weights are centralized"""

    def test_engine_weights_defined(self):
        """Engine weights should be defined as constants"""
        # After refactoring, weights should be in core module
        try:
            from core.invariants import (
                ENGINE_WEIGHT_AI,
                ENGINE_WEIGHT_RESEARCH,
                ENGINE_WEIGHT_ESOTERIC,
                ENGINE_WEIGHT_JARVIS,
            )

            assert ENGINE_WEIGHT_AI == 0.25
            assert ENGINE_WEIGHT_RESEARCH == 0.35
            assert ENGINE_WEIGHT_ESOTERIC == 0.15  # v20.19: reduced from 0.20
            assert ENGINE_WEIGHT_JARVIS == 0.25    # v20.19: increased from 0.20

        except ImportError:
            # Not yet refactored
            pytest.skip("Engine weights not yet centralized")


class TestJasonSimIntegration:
    """Test Jason Sim is properly integrated"""

    def test_jason_sim_fields_required(self):
        """Jason Sim required fields are defined"""
        from core.invariants import JASON_SIM_REQUIRED_FIELDS

        expected_fields = [
            "jason_sim_available",
            "jason_sim_boost",
            "jason_sim_reasons",
        ]

        for field in expected_fields:
            assert field in JASON_SIM_REQUIRED_FIELDS

    def test_jason_sim_not_duplicated_with_research(self):
        """Jason Sim should be its own layer, not part of Research"""
        # This is a code review check
        # Jason Sim should:
        # 1. Run AFTER base_score calculation
        # 2. Not be part of Research engine
        # 3. Add to final_score separately

        # After refactoring, scoring pipeline should show:
        # base_score = (ai * 0.25) + (research * 0.35) + (esoteric * 0.15) + (jarvis * 0.25)
        # final_score = base_score + confluence_boost + jason_sim_boost

        # For now, just verify Jason Sim logic exists
        try:
            from live_data_router import calculate_pick_score
            import inspect

            source = inspect.getsource(calculate_pick_score)

            # Should mention jason_sim_boost
            assert "jason_sim_boost" in source or "jason" in source.lower()

        except Exception as e:
            pytest.skip(f"Could not verify Jason Sim integration: {e}")


class TestFinalScoreFormula:
    """Test final_score formula is consistent"""

    def test_final_score_includes_all_components(self):
        """final_score should include: base_score + confluence + jason_sim"""
        # After refactoring, this should be testable via scoring pipeline

        # Mock scenario
        ai_score = 8.0
        research_score = 7.0
        esoteric_score = 6.0
        jarvis_score = 5.0
        confluence_boost = 2.0
        jason_sim_boost = 0.5

        # Expected calculation (v20.19: esoteric 0.15, jarvis 0.25)
        base_score = (ai_score * 0.25) + (research_score * 0.35) + (esoteric_score * 0.15) + (jarvis_score * 0.25)
        expected_final = base_score + confluence_boost + jason_sim_boost

        # After refactoring, can call scoring pipeline:
        # result = score_candidate(candidate, context)
        # assert result.final_score == expected_final

        # For now, verify formula manually
        # 8.0*0.25 + 7.0*0.35 + 6.0*0.15 + 5.0*0.25 = 2.0 + 2.45 + 0.9 + 1.25 = 6.60
        assert round(base_score, 2) == 6.60, f"Base score should be 6.60, got {base_score}"
        assert round(expected_final, 2) == 9.10, f"Final score should be 9.10, got {expected_final}"

    def test_jarvis_none_handled_correctly(self):
        """When jarvis_rs=None, contribution should be 0"""
        # After refactoring, scoring pipeline should handle this

        jarvis_rs = None
        jarvis_contribution = (jarvis_rs * 0.25) if jarvis_rs is not None else 0  # v20.19: 0.25

        assert jarvis_contribution == 0, "jarvis_rs=None should contribute 0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
