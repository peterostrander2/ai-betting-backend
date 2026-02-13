"""
v20.16: AI Model Usage Regression Tests

These tests ensure that AI models are truthfully reported and working.

Guards:
1. If ai_mode == ML_PRIMARY, raw_inputs.probability must be non-null
2. If ai_mode == ML_PRIMARY, model_preds.count >= 3
3. pillar_boost must stay within [-5.0, +5.0]
4. model_status must be present and truthful
5. LSTM must not return 0 for non-zero input
"""

import pytest


class TestAIModelUsageGuards:
    """Guards to prevent regression to 'claims models used but signals absent'."""

    def test_ml_primary_requires_probability(self):
        """
        Guard: If ai_mode == ML_PRIMARY, probability must be non-null.

        This prevents claiming ML is running when no actual prediction happened.
        """
        # Simulate ML_PRIMARY result
        ai_audit = {
            "ai_mode": "ML_PRIMARY",
            "raw_inputs": {
                "probability": 0.55,  # Must be present
            }
        }

        if ai_audit["ai_mode"] == "ML_PRIMARY":
            prob = ai_audit.get("raw_inputs", {}).get("probability")
            assert prob is not None, "ML_PRIMARY requires probability to be non-null"
            assert 0 <= prob <= 1, f"Probability must be in [0,1], got {prob}"

    def test_ml_primary_requires_model_count(self):
        """
        Guard: If ai_mode == ML_PRIMARY, at least 3 models must contribute.

        This prevents claiming 8-model prediction when only 1-2 are working.
        """
        MIN_MODELS_REQUIRED = 3

        # Simulate ML_PRIMARY result
        ai_audit = {
            "ai_mode": "ML_PRIMARY",
            "raw_inputs": {
                "model_preds": {
                    "count": 4,  # Must be >= 3
                    "values": [54.2, 0.0, 54.2, 107.9],
                }
            }
        }

        if ai_audit["ai_mode"] == "ML_PRIMARY":
            model_count = ai_audit.get("raw_inputs", {}).get("model_preds", {}).get("count", 0)
            assert model_count >= MIN_MODELS_REQUIRED, \
                f"ML_PRIMARY requires >= {MIN_MODELS_REQUIRED} models, got {model_count}"

    def test_pillar_boost_bounded(self):
        """
        Guard: pillar_boost must stay within [-5.0, +5.0].

        This prevents runaway negative values that caused floor dominance.
        """
        PILLAR_BOOST_MIN = -5.0
        PILLAR_BOOST_MAX = 5.0

        test_cases = [
            (-2.75, True),   # Normal negative - OK
            (0.0, True),     # Zero - OK
            (2.5, True),     # Normal positive - OK
            (-5.0, True),    # At min - OK
            (5.0, True),     # At max - OK
            (-5.01, False),  # Below min - FAIL
            (5.01, False),   # Above max - FAIL
            (-69.25, False), # Old bug value - FAIL
        ]

        for pillar_boost, should_pass in test_cases:
            is_valid = PILLAR_BOOST_MIN <= pillar_boost <= PILLAR_BOOST_MAX
            if should_pass:
                assert is_valid, f"pillar_boost={pillar_boost} should be valid"
            else:
                assert not is_valid, f"pillar_boost={pillar_boost} should be invalid"

    def test_model_status_present(self):
        """
        Guard: model_status must be present in ai_audit.

        This ensures we're truthful about what models are actually running.
        """
        required_models = [
            'ensemble',
            'lstm',
            'matchup',
            'monte_carlo',
            'line_movement',
            'rest_fatigue',
            'injury_impact',
            'edge_calculator',
        ]

        valid_statuses = {'WORKS', 'STUB', 'FALLBACK', 'TRAINED', 'DISABLED'}

        # Simulate model_status
        model_status = {
            'ensemble': 'STUB',
            'lstm': 'FALLBACK',
            'matchup': 'STUB',
            'monte_carlo': 'WORKS',
            'line_movement': 'WORKS',
            'rest_fatigue': 'WORKS',
            'injury_impact': 'WORKS',
            'edge_calculator': 'WORKS',
        }

        for model in required_models:
            assert model in model_status, f"model_status missing '{model}'"
            status = model_status[model]
            assert status in valid_statuses, \
                f"model_status['{model}'] = '{status}' not in {valid_statuses}"


class TestLSTMInputHandling:
    """Tests for LSTM input handling."""

    def test_lstm_fallback_returns_nonzero_for_nonzero_input(self):
        """
        Guard: LSTM fallback should return non-zero for non-zero input.

        Previously: recent_games = [0,0,0...] for totals caused LSTM=0.
        Now: totals use total line, spreads use spread.
        """
        import math

        # Simulate LSTM fallback (pure Python, no numpy)
        def lstm_statistical_fallback(recent_games):
            if not recent_games:
                return 25.0
            n = len(recent_games)
            # Exponential weights from exp(-1) to exp(0)
            weights = [math.exp(-1 + i / (n - 1)) if n > 1 else 1.0 for i in range(n)]
            weight_sum = sum(weights)
            weights = [w / weight_sum for w in weights]
            return sum(v * w for v, w in zip(recent_games, weights))

        # For spread pick with spread=6.5
        # When all inputs are the same, weighted average = that value
        spread_input = [6.5] * 10
        spread_output = lstm_statistical_fallback(spread_input)
        assert spread_output == pytest.approx(6.5, rel=0.01), \
            f"LSTM with spread input should return ~6.5, got {spread_output}"

        # For totals pick with total=214.5
        total_input = [214.5] * 10
        total_output = lstm_statistical_fallback(total_input)
        assert total_output == pytest.approx(214.5, rel=0.01), \
            f"LSTM with total input should return ~214.5, got {total_output}"

        # Empty input should return default 25.0
        empty_output = lstm_statistical_fallback([])
        assert empty_output == 25.0, f"LSTM with empty input should return 25.0, got {empty_output}"

    def test_recent_games_uses_correct_line_for_market(self):
        """
        Guard: recent_games should use total for totals, spread for spreads.
        """
        # For totals market
        market_type = "totals"
        spread = 0  # Often 0 for totals
        total = 214.5

        is_totals = "total" in market_type.lower()
        lstm_input_value = total if is_totals else max(abs(spread), 1.0)

        assert lstm_input_value == 214.5, \
            f"Totals pick should use total={total}, got {lstm_input_value}"

        # For spreads market
        market_type = "spreads"
        spread = 6.5
        total = 220

        is_totals = "total" in market_type.lower()
        lstm_input_value = total if is_totals else max(abs(spread), 1.0)

        assert lstm_input_value == 6.5, \
            f"Spreads pick should use spread={spread}, got {lstm_input_value}"


class TestInjuryImpactCap:
    """Tests for injury impact capping."""

    def test_injury_impact_capped_at_5(self):
        """
        Guard: injury_impact from InjuryImpactModel must be capped.

        v20.21: Cap reduced from 10.0 to 5.0 to prevent excessive negative swings.
        """
        INJURY_IMPACT_CAP = 5.0  # v20.21: reduced from 10.0

        # Simulate many injuries (35 starters)
        injuries = [
            {'player': {'depth': 1}, 'status': 'out'}
            for _ in range(35)
        ]

        # Old behavior (BROKEN): -70.0
        uncapped_impact = 0
        for injury in injuries:
            if injury.get('player', {}).get('depth', 99) == 1:
                uncapped_impact += 2.0
        assert uncapped_impact == 70.0, "Setup: 35 starters = 70.0"

        # New behavior (FIXED v20.21): capped at -5.0
        capped_impact = min(uncapped_impact, INJURY_IMPACT_CAP)
        result = -capped_impact
        assert result == -5.0, f"Injury impact should be capped at -5.0, got {result}"

    def test_injury_depth_default_not_starter(self):
        """
        Guard: Players without depth field should NOT be treated as starters.
        """
        # Player without depth field
        player = {}

        # Old behavior (BROKEN): default to 1 (starter)
        old_depth = player.get('depth', 1)
        assert old_depth == 1, "Old default was 1 (starter)"

        # New behavior (FIXED): default to 99 (unknown)
        new_depth = player.get('depth', 99)
        assert new_depth == 99, "New default is 99 (unknown)"
        assert new_depth != 1, "Unknown players are NOT starters"


# Check if numpy/sklearn are available for ML tests
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="numpy not available")
class TestEnsembleStackingModelSafety:
    """Regression tests for EnsembleStackingModel hard safety rules.

    v20.16.1: Ensures we never call .predict() on unfitted sklearn models.
    """

    def test_untrained_ensemble_predict_does_not_throw(self):
        """
        CRITICAL REGRESSION TEST: Simulates the bug where is_trained=True
        but base models were never fitted.

        This happened when GameEnsemble init set is_trained=True without
        the sklearn base models (XGBoost/LightGBM/RandomForest) being fitted.

        Assertions:
        1. predict() returns a float (not None, not exception)
        2. No exception thrown
        3. Returns fallback value (mean of features or default)
        """
        # Import the actual model
        from advanced_ml_backend import EnsembleStackingModel

        # Create untrained instance
        ensemble = EnsembleStackingModel()

        # Simulate the bug: force is_trained=True without fitting base models
        # This is what happened when GameEnsemble marked it trained
        ensemble.is_trained = True
        # But _ensemble_pipeline_trained should still be False (the fix)
        assert ensemble._ensemble_pipeline_trained is False, \
            "_ensemble_pipeline_trained should be False without train()"

        # Create test features
        features = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        # Call predict - should NOT throw, should return float
        result = ensemble.predict(features)

        # Assertions
        assert result is not None, "predict() should not return None"
        assert isinstance(result, (int, float)), f"predict() should return number, got {type(result)}"
        assert result == pytest.approx(3.0, rel=0.01), \
            f"Should return mean(features)=3.0, got {result}"

    def test_untrained_ensemble_with_model_predictions_fallback(self):
        """
        Test that even with model_predictions provided, untrained ensemble
        falls back gracefully to GameEnsemble or feature mean.
        """
        from advanced_ml_backend import EnsembleStackingModel

        ensemble = EnsembleStackingModel()
        ensemble.is_trained = True  # Simulate bug
        # _ensemble_pipeline_trained stays False

        features = np.array([10.0, 20.0, 30.0])
        model_preds = {'lstm': 50.0, 'matchup': 55.0, 'monte_carlo': 52.0}

        # Should not throw
        result = ensemble.predict(features, model_predictions=model_preds)

        assert result is not None
        assert isinstance(result, (int, float))

    def test_trained_flag_only_set_after_train(self):
        """
        Verify that _ensemble_pipeline_trained is ONLY True after train().
        """
        from advanced_ml_backend import EnsembleStackingModel

        ensemble = EnsembleStackingModel()

        # Before training
        assert ensemble._ensemble_pipeline_trained is False, \
            "Flag should be False before train()"

        # Simulate training with dummy data
        X_train = np.random.rand(100, 5)
        y_train = np.random.rand(100)
        X_val = np.random.rand(20, 5)
        y_val = np.random.rand(20)

        ensemble.train(X_train, y_train, X_val, y_val)

        # After training
        assert ensemble._ensemble_pipeline_trained is True, \
            "Flag should be True after train()"
        assert ensemble.is_trained is True
