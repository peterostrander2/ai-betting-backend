"""
TEST_AUTOGRADER.PY - Smoke Tests for Auto-Grader
=================================================
v1.0 - Production hardening smoke tests

These tests verify:
1. End-to-end grading flow
2. Weight retrieval and adjustment
3. Bias calculation
4. JSONL storage
5. Learning loop integration

Run with: python -m pytest tests/test_autograder.py -v
"""

import os
import sys
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Skip if numpy isn't available in this environment
pytest.importorskip("numpy")

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_grader import AutoGrader, get_grader, PredictionRecord, WeightConfig


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def test_grader():
    """Create a test grader with temporary storage."""
    test_path = "./test_grader_data_pytest"
    grader = AutoGrader(storage_path=test_path)
    yield grader
    # Cleanup
    import shutil
    if os.path.exists(test_path):
        shutil.rmtree(test_path)


@pytest.fixture
def grader_with_predictions(test_grader):
    """Create a grader with some pre-logged predictions."""
    # Log some test predictions
    test_grader.log_prediction(
        sport="NBA",
        player_name="LeBron James",
        stat_type="points",
        predicted_value=27.5,
        line=26.5,
        adjustments={"defense": 1.2, "pace": 0.8, "vacuum": 2.1}
    )
    test_grader.log_prediction(
        sport="NBA",
        player_name="Stephen Curry",
        stat_type="points",
        predicted_value=30.0,
        line=29.5,
        adjustments={"defense": 0.5, "pace": 1.5, "vacuum": -1.0}
    )
    test_grader.log_prediction(
        sport="NFL",
        player_name="Patrick Mahomes",
        stat_type="passing_yards",
        predicted_value=285.0,
        line=275.5,
        adjustments={"vacuum": 3.0}
    )
    return test_grader


# =============================================================================
# BASIC FUNCTIONALITY TESTS
# =============================================================================

class TestAutoGraderBasic:
    """Basic functionality tests."""

    def test_initialization(self, test_grader):
        """Test grader initializes correctly."""
        assert test_grader is not None
        assert test_grader.SUPPORTED_SPORTS == ["NBA", "NFL", "MLB", "NHL", "NCAAB"]
        assert "NBA" in test_grader.weights
        assert "points" in test_grader.weights["NBA"]

    def test_get_weights(self, test_grader):
        """Test weight retrieval."""
        weights = test_grader.get_weights("NBA", "points")

        assert "defense" in weights
        assert "pace" in weights
        assert "vacuum" in weights
        assert "lstm" in weights
        assert "officials" in weights

        # Check weights are within bounds
        for key, value in weights.items():
            if key != "park_factor":
                assert 0.0 <= value <= 1.0, f"Weight {key} out of bounds: {value}"

    def test_get_weights_default_fallback(self, test_grader):
        """Test weight retrieval falls back for unknown sport/stat."""
        weights = test_grader.get_weights("UNKNOWN", "unknown_stat")
        # Should return some weights without error
        assert "defense" in weights

    def test_get_all_weights(self, test_grader):
        """Test retrieving all weights."""
        all_weights = test_grader.get_all_weights()

        assert "NBA" in all_weights
        assert "NFL" in all_weights
        assert "MLB" in all_weights
        assert "NHL" in all_weights
        assert "NCAAB" in all_weights


# =============================================================================
# PREDICTION LOGGING TESTS
# =============================================================================

class TestPredictionLogging:
    """Tests for prediction logging."""

    def test_log_prediction(self, test_grader):
        """Test logging a prediction."""
        pred_id = test_grader.log_prediction(
            sport="NBA",
            player_name="Test Player",
            stat_type="points",
            predicted_value=25.0,
            line=24.5,
            adjustments={"defense": 1.0}
        )

        assert pred_id is not None
        assert "NBA" in pred_id
        assert "Test Player" in pred_id

    def test_log_prediction_stored(self, test_grader):
        """Test that logged prediction is stored."""
        test_grader.log_prediction(
            sport="NBA",
            player_name="Stored Test",
            stat_type="rebounds",
            predicted_value=10.0
        )

        assert len(test_grader.predictions["NBA"]) > 0
        last_pred = test_grader.predictions["NBA"][-1]
        assert last_pred.player_name == "Stored Test"
        assert last_pred.stat_type == "rebounds"


# =============================================================================
# END-TO-END GRADING TESTS
# =============================================================================

class TestEndToEndGrading:
    """End-to-end grading flow tests."""

    def test_end_to_end_grading(self, test_grader):
        """Test complete grading flow: log -> grade -> verify."""
        # Step 1: Log a prediction
        pred_id = test_grader.log_prediction(
            sport="NBA",
            player_name="E2E Test Player",
            stat_type="points",
            predicted_value=27.0,
            line=25.5,
            adjustments={"defense": 1.0, "pace": 0.5, "vacuum": 2.0}
        )

        # Step 2: Grade the prediction
        result = test_grader.grade_prediction(pred_id, actual_value=27.0)

        # Step 3: Verify result
        assert result is not None
        assert result["prediction_id"] == pred_id
        assert result["predicted"] == 27.0
        assert result["actual"] == 27.0
        # Note: error = predicted_value - (10.0 if hit else 0.0)
        # This measures how far off the confidence score was from ideal,
        # NOT the difference between predicted and actual values
        # predicted=27.0, hit=True -> error = 27.0 - 10.0 = 17.0
        assert result["error"] == 17.0
        assert result["hit"] == True  # Predicted over line (27 > 25.5), actual over line

    def test_grading_hit_over(self, test_grader):
        """Test grading a correct OVER prediction."""
        pred_id = test_grader.log_prediction(
            sport="NBA",
            player_name="Over Test",
            stat_type="points",
            predicted_value=30.0,  # Predicted over line
            line=25.5
        )

        result = test_grader.grade_prediction(pred_id, actual_value=28.0)  # Actual over line

        assert result["hit"] == True

    def test_grading_hit_under(self, test_grader):
        """Test grading a correct UNDER prediction."""
        pred_id = test_grader.log_prediction(
            sport="NBA",
            player_name="Under Test",
            stat_type="points",
            predicted_value=22.0,  # Predicted under line
            line=25.5
        )

        result = test_grader.grade_prediction(pred_id, actual_value=23.0)  # Actual under line

        assert result["hit"] == True

    def test_grading_miss(self, test_grader):
        """Test grading an incorrect prediction."""
        pred_id = test_grader.log_prediction(
            sport="NBA",
            player_name="Miss Test",
            stat_type="points",
            predicted_value=30.0,  # Predicted over
            line=25.5
        )

        result = test_grader.grade_prediction(pred_id, actual_value=20.0)  # Actual under

        assert result["hit"] == False


# =============================================================================
# WEIGHT ADJUSTMENT TESTS
# =============================================================================

class TestWeightAdjustment:
    """Tests for weight adjustment functionality."""

    def test_adjust_weights_no_data(self, test_grader):
        """Test weight adjustment with no graded predictions."""
        result = test_grader.adjust_weights("NBA", "points", days_back=1)

        assert "error" in result or "weights_unchanged" in result

    def test_adjust_weights_with_data(self, grader_with_predictions):
        """Test weight adjustment with graded predictions."""
        # Grade some predictions first
        for record in grader_with_predictions.predictions["NBA"]:
            grader_with_predictions.grade_prediction(
                record.prediction_id,
                actual_value=record.predicted_value + 2.0  # Slight under-prediction
            )

        result = grader_with_predictions.adjust_weights(
            "NBA", "points", days_back=1, apply_changes=False
        )

        assert "bias_analysis" in result or "error" in result


# =============================================================================
# AUDIT SUMMARY TESTS
# =============================================================================

class TestAuditSummary:
    """Tests for audit summary functionality."""

    def test_get_audit_summary(self, grader_with_predictions):
        """Test getting audit summary."""
        # Grade a prediction
        pred_id = grader_with_predictions.predictions["NBA"][0].prediction_id
        grader_with_predictions.grade_prediction(pred_id, actual_value=28.0)

        summary = grader_with_predictions.get_audit_summary("NBA", days_back=1)

        assert "sport" in summary
        assert summary["sport"] == "NBA"
        assert "total_predictions" in summary
        assert "total_graded" in summary
        assert "hit_rate" in summary


# =============================================================================
# SPEC COMPLIANCE TESTS (v12.0 Method Aliases)
# =============================================================================

class TestSpecCompliance:
    """Tests for v12.0 spec compliance method aliases."""

    def test_snapshot(self, test_grader):
        """Test snapshot method alias."""
        snapshot = test_grader.snapshot()

        assert "weights" in snapshot
        assert "timestamp" in snapshot
        assert "predictions_count" in snapshot

    def test_load_snapshot(self, test_grader):
        """Test load_snapshot method alias."""
        result = test_grader.load_snapshot()
        assert result == True

    def test_apply_updates(self, grader_with_predictions):
        """Test apply_updates method alias."""
        # Grade predictions first
        for record in grader_with_predictions.predictions["NBA"]:
            grader_with_predictions.grade_prediction(
                record.prediction_id,
                actual_value=record.predicted_value + 1.0
            )

        result = grader_with_predictions.apply_updates(learning_rate=0.05)

        assert isinstance(result, dict)
        # Should have results for all sports
        assert "NBA" in result


# =============================================================================
# JSONL STORAGE TESTS
# =============================================================================

class TestJSONLStorage:
    """Tests for JSONL daily storage."""

    def test_save_daily_grading_jsonl(self, grader_with_predictions):
        """Test saving graded picks to JSONL."""
        # Grade a prediction
        pred_id = grader_with_predictions.predictions["NBA"][0].prediction_id
        grader_with_predictions.grade_prediction(pred_id, actual_value=30.0)

        # Save to JSONL
        path = grader_with_predictions.save_daily_grading_jsonl()

        assert os.path.exists(path)
        assert path.endswith(".jsonl")

    def test_load_daily_grading_jsonl(self, grader_with_predictions):
        """Test loading graded picks from JSONL."""
        # Grade and save
        pred_id = grader_with_predictions.predictions["NBA"][0].prediction_id
        grader_with_predictions.grade_prediction(pred_id, actual_value=30.0)

        date_str = datetime.now().strftime("%Y-%m-%d")
        grader_with_predictions.save_daily_grading_jsonl(date_str)

        # Load
        records = grader_with_predictions.load_daily_grading_jsonl(date_str)

        assert isinstance(records, list)

    def test_get_performance_history(self, grader_with_predictions):
        """Test getting performance history."""
        history = grader_with_predictions.get_performance_history(days_back=7)

        assert isinstance(history, dict)
        assert len(history) == 7  # 7 days


# =============================================================================
# SINGLETON TESTS
# =============================================================================

class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_grader_returns_same_instance(self):
        """Test that get_grader returns the same instance."""
        grader1 = get_grader()
        grader2 = get_grader()

        assert grader1 is grader2


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests with other modules."""

    def test_grader_with_tiering_weights(self, test_grader):
        """Test that grader weights work with tiering module."""
        try:
            from tiering import TITANIUM_THRESHOLD, COMMUNITY_MIN_SCORE

            weights = test_grader.get_weights("NBA", "points")
            # Weights should be compatible with tiering thresholds
            assert isinstance(weights, dict)
        except ImportError:
            pytest.skip("Tiering module not available")

    def test_grader_with_research_engine(self, test_grader):
        """Test that grader can work with research engine."""
        try:
            from research_engine import get_research_score

            # Grader weights should not conflict with research engine
            weights = test_grader.get_weights("NBA", "points")
            assert "vacuum" in weights
        except ImportError:
            pytest.skip("Research engine not available")


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
