"""
Tests for mechanically checkable training telemetry.

v20.17.0: Verifies filter telemetry assertions and training signatures.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import scripts module to allow patching
import scripts.train_team_models as train_module

# Check if numpy is available (needed for team_ml_models)
try:
    import numpy
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class TestFilterTelemetryAssertions:
    """Tests that filter telemetry math is correct."""

    def test_filter_counts_sum_correctly(self):
        """Verify: eligible_total + sum(drops) == graded_loaded_total."""
        # Mock grader_store with test data
        mock_picks = [
            # Will pass all filters
            {"grade_status": "GRADED", "result": "WIN", "pick_type": "SPREAD",
             "home_team": "Lakers", "away_team": "Celtics", "date_et": "2026-02-09", "sport": "NBA"},
            {"grade_status": "GRADED", "result": "LOSS", "pick_type": "TOTAL",
             "home_team": "Heat", "away_team": "Bulls", "date_et": "2026-02-09", "sport": "NBA"},
            # Will be dropped: no grade
            {"grade_status": "PENDING", "result": "WIN", "pick_type": "SPREAD",
             "home_team": "Lakers", "away_team": "Celtics", "date_et": "2026-02-09"},
            # Will be dropped: no result
            {"grade_status": "GRADED", "result": None, "pick_type": "SPREAD",
             "home_team": "Lakers", "away_team": "Celtics", "date_et": "2026-02-09"},
            # Will be dropped: wrong market (prop)
            {"grade_status": "GRADED", "result": "WIN", "pick_type": "PLAYER_POINTS",
             "home_team": "Lakers", "away_team": "Celtics", "date_et": "2026-02-09"},
            # Will be dropped: missing required fields
            {"grade_status": "GRADED", "result": "WIN", "pick_type": "SPREAD",
             "home_team": "", "away_team": "Celtics", "date_et": "2026-02-09"},
            # Will be dropped: outside window (old date)
            {"grade_status": "GRADED", "result": "WIN", "pick_type": "SPREAD",
             "home_team": "Lakers", "away_team": "Celtics", "date_et": "2020-01-01"},
        ]

        with patch('grader_store.load_predictions', return_value=mock_picks):
            picks, telemetry = train_module.load_graded_picks(days=7, sport=None)

        # Verify assertion passed
        assert telemetry['assertion_passed'] is True, f"Assertion failed: {telemetry.get('assertion_error')}"

        # Verify the math manually
        sum_of_drops = (
            telemetry['drop_no_grade'] +
            telemetry['drop_no_result'] +
            telemetry['drop_wrong_market'] +
            telemetry['drop_missing_required_fields'] +
            telemetry['drop_outside_time_window'] +
            telemetry['drop_wrong_sport']
        )
        expected = telemetry['eligible_total'] + sum_of_drops
        assert expected == telemetry['graded_loaded_total'], \
            f"Math error: {telemetry['eligible_total']} + {sum_of_drops} != {telemetry['graded_loaded_total']}"

        # Verify used <= eligible
        assert telemetry['used_for_training_total'] <= telemetry['eligible_total']

    def test_used_for_training_never_exceeds_eligible(self):
        """Verify: used_for_training_total <= eligible_total."""
        mock_picks = [
            {"grade_status": "GRADED", "result": "WIN", "pick_type": "SPREAD",
             "home_team": "Lakers", "away_team": "Celtics", "date_et": "2026-02-09", "sport": "NBA"},
        ]

        with patch('grader_store.load_predictions', return_value=mock_picks):
            picks, telemetry = train_module.load_graded_picks(days=7)

        assert telemetry['used_for_training_total'] <= telemetry['eligible_total']
        assert telemetry['assertion_passed'] is True

    def test_drop_counts_are_mutually_exclusive(self):
        """Each pick should only be counted in one drop bucket."""
        # Create picks that could match multiple drop conditions
        mock_picks = [
            # No grade AND no result - should only count as no_grade (first check)
            {"grade_status": "PENDING", "result": None, "pick_type": "SPREAD",
             "home_team": "Lakers", "away_team": "Celtics", "date_et": "2026-02-09"},
        ]

        with patch('grader_store.load_predictions', return_value=mock_picks):
            picks, telemetry = train_module.load_graded_picks(days=7)

        # Should only be in one bucket
        assert telemetry['drop_no_grade'] == 1
        assert telemetry['drop_no_result'] == 0  # Never reached this check
        assert telemetry['assertion_passed'] is True

    def test_filter_version_present(self):
        """Filter version should be present for schema tracking."""
        with patch('grader_store.load_predictions', return_value=[]):
            picks, telemetry = train_module.load_graded_picks(days=7)

        assert 'filter_version' in telemetry
        assert telemetry['filter_version'] == '2.0'


class TestTrainingSignatures:
    """Tests for training signatures and schema hashes."""

    def test_schema_hash_consistency(self):
        """Same features should produce same hash."""
        hash1 = train_module._compute_schema_hash(['a', 'b', 'c'])
        hash2 = train_module._compute_schema_hash(['a', 'b', 'c'])
        hash3 = train_module._compute_schema_hash(['c', 'b', 'a'])  # Different order, same set

        assert hash1 == hash2, "Same input should produce same hash"
        assert hash1 == hash3, "Sorted features should produce same hash regardless of input order"

    def test_schema_hash_differs_for_different_features(self):
        """Different features should produce different hash."""
        hash1 = train_module._compute_schema_hash(['a', 'b', 'c'])
        hash2 = train_module._compute_schema_hash(['a', 'b', 'd'])

        assert hash1 != hash2, "Different features should produce different hash"

    @pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
    def test_team_cache_returns_training_signature(self):
        """update_team_cache should return a training signature."""
        from team_ml_models import get_team_cache

        mock_picks = [
            {"pick_type": "SPREAD", "sport": "NBA", "home_team": "Lakers",
             "away_team": "Celtics", "result": "WIN", "line": -5},
        ]

        # Use real team_cache but mock _save_cache to avoid file I/O
        cache = get_team_cache()
        with patch.object(cache, '_save_cache'):
            result = train_module.update_team_cache(mock_picks)

        assert 'games_processed' in result
        assert 'teams_cached_total' in result
        assert 'feature_schema_hash' in result
        assert 'sports_included' in result

    @pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
    def test_matchup_matrix_returns_training_signature(self):
        """update_matchup_matrix should return a training signature."""
        from team_ml_models import get_team_matchup

        mock_picks = [
            {"pick_type": "SPREAD", "sport": "NBA", "home_team": "Lakers",
             "away_team": "Celtics", "result": "WIN", "line": -5},
        ]

        # Use real matchup model but mock _save_matchups to avoid file I/O
        matchup = get_team_matchup()
        with patch.object(matchup, '_save_matchups'):
            result = train_module.update_matchup_matrix(mock_picks)

        assert 'games_processed' in result
        assert 'matchups_tracked_total' in result
        assert 'feature_schema_hash' in result
        assert 'sports_included' in result

    @pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
    def test_ensemble_returns_training_signature(self):
        """update_ensemble_weights should return a training signature with label definition."""
        from team_ml_models import get_game_ensemble

        mock_picks = [
            {
                "pick_type": "SPREAD", "sport": "NBA", "result": "WIN", "line": -5,
                "ai_breakdown": {
                    "raw_inputs": {
                        "model_preds": {"values": [1.0, 2.0, 3.0, 4.0]}
                    }
                }
            },
        ]

        # Use real ensemble but mock _save_weights to avoid file I/O
        ensemble = get_game_ensemble()
        with patch.object(ensemble, '_save_weights'):
            result = train_module.update_ensemble_weights(mock_picks)

        assert 'samples_used' in result
        assert 'markets_included' in result
        assert 'sports_included' in result
        assert 'training_feature_schema_hash' in result
        assert 'label_definition' in result
        assert 'label_type' in result


@pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
class TestModelStatusTelemetry:
    """Tests for get_model_status telemetry output."""

    def test_model_status_includes_training_telemetry(self):
        """get_model_status should include training_telemetry section."""
        from team_ml_models import get_model_status

        status = get_model_status()

        assert 'training_telemetry' in status
        assert 'telemetry_version' in status['training_telemetry']
        assert 'filter_telemetry' in status['training_telemetry']
        assert 'training_signatures' in status['training_telemetry']

    def test_model_status_includes_per_model_signatures(self):
        """Each model should have a training_signature field."""
        from team_ml_models import get_model_status

        status = get_model_status()

        assert 'training_signature' in status['lstm']
        assert 'training_signature' in status['matchup']
        assert 'training_signature' in status['ensemble']
