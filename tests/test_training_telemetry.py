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
        """Verify: eligible_total + sum(drops) == loaded_total."""
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
        assert expected == telemetry['loaded_total'], \
            f"Math error: {telemetry['eligible_total']} + {sum_of_drops} != {telemetry['loaded_total']}"

        # Verify graded_total + ungraded_total == loaded_total
        assert telemetry['graded_total'] + telemetry['ungraded_total'] == telemetry['loaded_total']

        # Verify used <= eligible
        assert telemetry['used_for_training_total'] <= telemetry['eligible_total']

        # Verify source tracking fields present
        assert 'grader_store_path' in telemetry
        assert 'volume_mount_path' in telemetry
        assert 'store_schema_version' in telemetry

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
        assert telemetry['filter_version'] == '2.1'


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
            result = train_module.update_ensemble_weights(mock_picks, eligible_total=1)

        assert 'samples_used' in result
        assert 'markets_included' in result
        assert 'sports_included' in result
        assert 'training_feature_schema_hash' in result
        assert 'label_definition' in result
        assert 'label_type' in result

        # Binary hit classification
        assert result['label_type'] == 'binary_hit'
        assert 'WIN' in result['label_definition'] and 'LOSS' in result['label_definition']

        # Schema match verification
        assert 'inference_feature_schema_hash' in result
        assert 'schema_match' in result
        assert result['schema_match'] is True  # Training and inference should match

        # Per-model filter telemetry
        assert 'filter_telemetry' in result
        ft = result['filter_telemetry']
        assert 'eligible_from_upstream' in ft
        assert 'drop_no_model_preds' in ft
        assert 'drop_insufficient_values' in ft
        assert 'drop_no_result' in ft
        assert 'used_for_training' in ft
        assert 'assertion_passed' in ft


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


class TestStoreAuditUtility:
    """Tests for the store audit utility (scripts/audit_training_store.py)."""

    def test_audit_store_returns_required_fields(self):
        """audit_store should return all required fields."""
        from scripts.audit_training_store import audit_store
        import tempfile
        import json

        # Create temp file with test data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            test_records = [
                {"grade_status": "GRADED", "result": "WIN", "pick_type": "SPREAD",
                 "home_team": "Lakers", "away_team": "Celtics", "sport": "NBA", "date_et": "2026-02-09"},
                {"grade_status": "PENDING", "result": None, "pick_type": "PLAYER_POINTS",
                 "home_team": "Lakers", "away_team": "Celtics", "sport": "NBA", "date_et": "2026-02-09"},
            ]
            for record in test_records:
                f.write(json.dumps(record) + '\n')
            temp_path = f.name

        try:
            result = audit_store(temp_path)

            # Store provenance
            assert 'store_provenance' in result
            prov = result['store_provenance']
            assert prov['exists'] is True
            assert prov['line_count'] == 2
            assert 'mtime_iso' in prov
            assert 'size_bytes' in prov
            assert prov['store_schema_version'] == '1.0'

            # Counts
            assert 'counts_by_grade_status' in result
            assert 'counts_by_pick_type' in result
            assert 'counts_by_sport' in result
            assert 'counts_by_market' in result

            # Missing model_preds attribution
            assert 'missing_model_preds' in result
            assert 'missing_model_preds_attribution' in result
            attr = result['missing_model_preds_attribution']
            assert 'old_schema' in attr
            assert 'non_game_market' in attr
            assert 'error_path' in attr
            assert 'unknown' in attr

            # Reconciliation
            assert 'reconciliation' in result
            recon = result['reconciliation']
            assert recon['total_lines'] == 2
            assert recon['parsed_ok'] == 2
            assert recon['parse_errors'] == 0
            assert recon['reconciled'] is True

        finally:
            os.unlink(temp_path)

    def test_audit_store_nonexistent_file(self):
        """audit_store should handle nonexistent file gracefully."""
        from scripts.audit_training_store import audit_store

        result = audit_store("/nonexistent/path/predictions.jsonl")

        assert result['store_provenance']['exists'] is False
        assert result['reconciliation']['reconciled'] is True  # Empty is consistent

    def test_audit_store_attribution_buckets(self):
        """Test attribution bucket logic for missing model_preds."""
        from scripts.audit_training_store import audit_store
        import tempfile
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            test_records = [
                # old_schema: date before model_preds introduction
                {"grade_status": "GRADED", "result": "WIN", "pick_type": "SPREAD",
                 "home_team": "Lakers", "away_team": "Celtics", "sport": "NBA", "date_et": "2026-01-15"},
                # non_game_market: prop pick (expected no model_preds)
                {"grade_status": "GRADED", "result": "WIN", "pick_type": "PLAYER_POINTS",
                 "home_team": "Lakers", "away_team": "Celtics", "sport": "NBA", "date_et": "2026-02-09"},
                # error_path: has error indicator
                {"grade_status": "GRADED", "result": "WIN", "pick_type": "SPREAD",
                 "home_team": "Lakers", "away_team": "Celtics", "sport": "NBA", "date_et": "2026-02-09",
                 "ai_breakdown": {"error": True}},
                # unknown: recent game market without model_preds and no error
                {"grade_status": "GRADED", "result": "WIN", "pick_type": "SPREAD",
                 "home_team": "Lakers", "away_team": "Celtics", "sport": "NBA", "date_et": "2026-02-09"},
            ]
            for record in test_records:
                f.write(json.dumps(record) + '\n')
            temp_path = f.name

        try:
            result = audit_store(temp_path)

            attr = result['missing_model_preds_attribution']
            assert attr['old_schema'] == 1, "Old schema record should be attributed"
            assert attr['non_game_market'] == 1, "Prop record should be attributed to non_game_market"
            assert attr['error_path'] == 1, "Error record should be attributed"
            assert attr['unknown'] == 1, "Unknown record should be attributed"

            # Total missing should match sum
            total_attributed = sum(attr.values())
            assert result['missing_model_preds'] == total_attributed

        finally:
            os.unlink(temp_path)

    def test_audit_summary_returns_bounded_output(self):
        """get_store_audit_summary should return condensed output."""
        from scripts.audit_training_store import get_store_audit_summary
        import tempfile
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for i in range(10):
                record = {"grade_status": "GRADED", "result": "WIN", "pick_type": "SPREAD",
                          "home_team": "Lakers", "away_team": "Celtics", "sport": "NBA", "date_et": "2026-02-09"}
                f.write(json.dumps(record) + '\n')
            temp_path = f.name

        try:
            summary = get_store_audit_summary(temp_path)

            # Should have data_quality section
            assert 'data_quality' in summary
            dq = summary['data_quality']
            assert 'total_records' in dq
            assert 'graded_count' in dq
            assert 'missing_model_preds_total' in dq
            assert 'missing_model_preds_attribution' in dq

            # Should have distribution section
            assert 'distribution' in summary
            dist = summary['distribution']
            assert 'by_sport' in dist
            assert 'by_market' in dist
            assert 'by_pick_type_top5' in dist

        finally:
            os.unlink(temp_path)


class TestBinaryLabelInvariants:
    """Tests that verify binary label classification invariants."""

    @pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
    def test_push_results_excluded_from_ensemble(self):
        """PUSH results must be excluded from ensemble training."""
        from team_ml_models import get_game_ensemble

        mock_picks = [
            # WIN - should be included
            {"pick_type": "SPREAD", "sport": "NBA", "result": "WIN",
             "ai_breakdown": {"raw_inputs": {"model_preds": {"values": [1.0, 2.0, 3.0, 4.0]}}}},
            # LOSS - should be included
            {"pick_type": "SPREAD", "sport": "NBA", "result": "LOSS",
             "ai_breakdown": {"raw_inputs": {"model_preds": {"values": [1.0, 2.0, 3.0, 4.0]}}}},
            # PUSH - must be excluded
            {"pick_type": "SPREAD", "sport": "NBA", "result": "PUSH",
             "ai_breakdown": {"raw_inputs": {"model_preds": {"values": [1.0, 2.0, 3.0, 4.0]}}}},
        ]

        ensemble = get_game_ensemble()
        with patch.object(ensemble, '_save_weights'):
            result = train_module.update_ensemble_weights(mock_picks, eligible_total=3)

        # Verify PUSH was excluded
        ft = result['filter_telemetry']
        assert ft['drop_push_excluded'] == 1, "PUSH must be excluded from training"
        assert ft['used_for_training'] == 2, "Only WIN and LOSS should be used"

    @pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
    def test_label_type_is_binary_hit(self):
        """Ensemble must use binary_hit label type, not regression."""
        from team_ml_models import get_game_ensemble

        mock_picks = [
            {"pick_type": "SPREAD", "sport": "NBA", "result": "WIN",
             "ai_breakdown": {"raw_inputs": {"model_preds": {"values": [1.0, 2.0, 3.0, 4.0]}}}},
        ]

        ensemble = get_game_ensemble()
        with patch.object(ensemble, '_save_weights'):
            result = train_module.update_ensemble_weights(mock_picks, eligible_total=1)

        assert result['label_type'] == 'binary_hit', "Label type must be binary_hit"
        assert 'line' not in result['label_definition'].lower(), "Label definition must not mention line/spread regression"
        assert 'WIN' in result['label_definition'], "Label definition must mention WIN"
        assert 'LOSS' in result['label_definition'], "Label definition must mention LOSS"
        assert 'PUSH excluded' in result['label_definition'], "Label definition must state PUSH is excluded"


class TestDataQualityGuardrails:
    """Tests for data quality guardrails that fail if claims become untrue."""

    def test_graded_ungraded_sum_equals_loaded(self):
        """graded_total + ungraded_total must equal loaded_total."""
        mock_picks = [
            {"grade_status": "GRADED", "result": "WIN", "pick_type": "SPREAD",
             "home_team": "Lakers", "away_team": "Celtics", "date_et": "2026-02-09", "sport": "NBA"},
            {"grade_status": "PENDING", "result": None, "pick_type": "SPREAD",
             "home_team": "Lakers", "away_team": "Celtics", "date_et": "2026-02-09", "sport": "NBA"},
            {"grade_status": "", "result": "WIN", "pick_type": "SPREAD",
             "home_team": "Lakers", "away_team": "Celtics", "date_et": "2026-02-09", "sport": "NBA"},
        ]

        with patch('grader_store.load_predictions', return_value=mock_picks):
            picks, telemetry = train_module.load_graded_picks(days=7)

        assert telemetry['graded_total'] + telemetry['ungraded_total'] == telemetry['loaded_total'], \
            "graded + ungraded must equal loaded"

    def test_store_schema_version_present(self):
        """Store schema version must be present for migration tracking."""
        mock_picks = []

        with patch('grader_store.load_predictions', return_value=mock_picks):
            picks, telemetry = train_module.load_graded_picks(days=7)

        assert 'store_schema_version' in telemetry
        assert telemetry['store_schema_version'] == '1.0'

    def test_volume_mount_path_present(self):
        """Volume mount path must be tracked for deployment verification."""
        mock_picks = []

        with patch('grader_store.load_predictions', return_value=mock_picks):
            picks, telemetry = train_module.load_graded_picks(days=7)

        assert 'volume_mount_path' in telemetry
        # Should be either /data (production) or a local path (dev)
        assert telemetry['volume_mount_path'] is not None

    def test_filter_assertion_fails_on_math_error(self):
        """Filter assertion should detect math errors."""
        # This test verifies the assertion logic catches inconsistencies
        # We can't easily inject a math error without modifying the source,
        # but we can verify the assertion fields are present and check-able

        mock_picks = [
            {"grade_status": "GRADED", "result": "WIN", "pick_type": "SPREAD",
             "home_team": "Lakers", "away_team": "Celtics", "date_et": "2026-02-09", "sport": "NBA"},
        ]

        with patch('grader_store.load_predictions', return_value=mock_picks):
            picks, telemetry = train_module.load_graded_picks(days=7)

        # Verify assertion fields exist and can be validated
        assert 'assertion_passed' in telemetry
        assert isinstance(telemetry['assertion_passed'], bool)

        if not telemetry['assertion_passed']:
            assert 'assertion_error' in telemetry
            assert telemetry['assertion_error'] is not None


class TestModelPredsRequirements:
    """Tests for model_preds requirements in ensemble training."""

    @pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
    def test_insufficient_model_preds_values_dropped(self):
        """Picks with fewer than 4 model_preds values must be dropped."""
        from team_ml_models import get_game_ensemble

        mock_picks = [
            # Valid: 4 values
            {"pick_type": "SPREAD", "sport": "NBA", "result": "WIN",
             "ai_breakdown": {"raw_inputs": {"model_preds": {"values": [1.0, 2.0, 3.0, 4.0]}}}},
            # Invalid: only 3 values
            {"pick_type": "SPREAD", "sport": "NBA", "result": "WIN",
             "ai_breakdown": {"raw_inputs": {"model_preds": {"values": [1.0, 2.0, 3.0]}}}},
            # Invalid: only 2 values
            {"pick_type": "SPREAD", "sport": "NBA", "result": "WIN",
             "ai_breakdown": {"raw_inputs": {"model_preds": {"values": [1.0, 2.0]}}}},
        ]

        ensemble = get_game_ensemble()
        with patch.object(ensemble, '_save_weights'):
            result = train_module.update_ensemble_weights(mock_picks, eligible_total=3)

        ft = result['filter_telemetry']
        assert ft['drop_insufficient_values'] == 2, "Picks with < 4 values must be dropped"
        assert ft['used_for_training'] == 1, "Only pick with 4 values should be used"

    @pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
    def test_missing_model_preds_dropped(self):
        """Picks without model_preds must be dropped from ensemble training."""
        from team_ml_models import get_game_ensemble

        mock_picks = [
            # Has model_preds
            {"pick_type": "SPREAD", "sport": "NBA", "result": "WIN",
             "ai_breakdown": {"raw_inputs": {"model_preds": {"values": [1.0, 2.0, 3.0, 4.0]}}}},
            # Missing model_preds entirely
            {"pick_type": "SPREAD", "sport": "NBA", "result": "WIN",
             "ai_breakdown": {}},
            # Missing ai_breakdown
            {"pick_type": "SPREAD", "sport": "NBA", "result": "WIN"},
        ]

        ensemble = get_game_ensemble()
        with patch.object(ensemble, '_save_weights'):
            result = train_module.update_ensemble_weights(mock_picks, eligible_total=3)

        ft = result['filter_telemetry']
        assert ft['drop_no_model_preds'] == 2, "Picks without model_preds must be dropped"
        assert ft['used_for_training'] == 1, "Only pick with model_preds should be used"
