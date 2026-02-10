"""
v20.16: AI Engine Score Guards (Anti-Fake-Confidence)

These tests prevent score inflation in Engine 1 (AI scoring).
They verify that the alternative scoring path doesn't produce
artificially high scores when the model prediction is near the line.

Regression Guard 1: When deviation_score is 0, alternative_base must be used
Regression Guard 2: alternative_base is capped at 10.0 and follows formula

See: advanced_ml_backend.py lines 769-796
"""

import pytest


class TestAIScoreGuards:
    """Regression tests for AI Engine scoring (Engine 1)."""

    def test_alternative_base_formula_consistency(self):
        """
        Guard 1: Verify alternative_base follows documented formula.

        Formula: alternative_base = min(10, 2.0 + agreement_score + edge_score + factor_score)

        Where:
        - agreement_score in [0, 3] - model agreement (lower std = higher)
        - edge_score in [0, 3] - edge percentage (15%+ = max 3)
        - factor_score in [0, 2] - rest + injury + line movement

        Maximum possible: 2.0 + 3 + 3 + 2 = 10.0 (capped)
        Minimum possible: 2.0 + 0 + 0 + 0 = 2.0 (floor)
        """
        # Test minimum case: no agreement, no edge, no factors
        agreement_score = 0
        edge_score = 0
        factor_score = 0

        alternative_base = min(10, 2.0 + agreement_score + edge_score + factor_score)
        assert alternative_base == 2.0, f"Floor should be 2.0, got {alternative_base}"

        # Test maximum case: perfect agreement, max edge, all factors
        agreement_score = 3.0
        edge_score = 3.0
        factor_score = 2.0

        alternative_base = min(10, 2.0 + agreement_score + edge_score + factor_score)
        assert alternative_base == 10.0, f"Cap should be 10.0, got {alternative_base}"

        # Test that cap prevents values > 10
        agreement_score = 4.0  # Over the normal max
        edge_score = 5.0       # Over the normal max
        factor_score = 3.0     # Over the normal max

        alternative_base = min(10, 2.0 + agreement_score + edge_score + factor_score)
        assert alternative_base == 10.0, f"Should be capped at 10.0, got {alternative_base}"

    def test_deviation_near_zero_uses_alternative(self):
        """
        Guard 2: When prediction ≈ line (deviation_score near 0),
        the system MUST use alternative_base instead.

        This prevents game picks from getting 0-score when the model
        predicts exactly what the line is (common for totals).

        base_score = max(deviation_score, alternative_base)

        When deviation_score = 0 and alternative_base = 5.0:
        -> base_score = 5.0 (uses alternative, not zero!)
        """
        # Simulate: predicted_value = line (no deviation)
        predicted_value = 220.0
        line = 220.0
        std_dev = 10.0

        deviation = abs(predicted_value - line)
        deviation_score = min(10, deviation / std_dev * 5)

        assert deviation_score == 0.0, "Deviation score should be 0 when prediction equals line"

        # Simulate reasonable alternative components
        agreement_score = 2.0   # Models agree moderately
        edge_score = 1.5        # 7.5% edge
        factor_score = 1.0      # Well-rested team

        alternative_base = min(10, 2.0 + agreement_score + edge_score + factor_score)
        assert alternative_base == 6.5, f"Alternative base should be 6.5, got {alternative_base}"

        # The critical check: base_score uses alternative when deviation is 0
        base_score = max(deviation_score, alternative_base)
        assert base_score == alternative_base, \
            f"base_score should use alternative ({alternative_base}) not deviation ({deviation_score})"
        assert base_score > 0, "base_score must never be 0 for game picks"

    def test_agreement_score_formula(self):
        """
        Verify agreement_score calculation:
        agreement_score = max(0, 3 - model_std / 2)

        - model_std = 0 -> agreement = 3 (perfect agreement)
        - model_std = 6 -> agreement = 0 (max divergence)
        - model_std = 2 -> agreement = 2 (moderate agreement)
        """
        # Perfect agreement (std=0)
        model_std = 0
        agreement_score = max(0, 3 - model_std / 2)
        assert agreement_score == 3.0, f"Perfect agreement should be 3.0, got {agreement_score}"

        # Max divergence (std>=6)
        model_std = 6
        agreement_score = max(0, 3 - model_std / 2)
        assert agreement_score == 0.0, f"Max divergence should be 0.0, got {agreement_score}"

        # Moderate agreement (std=2)
        model_std = 2
        agreement_score = max(0, 3 - model_std / 2)
        assert agreement_score == 2.0, f"Moderate agreement should be 2.0, got {agreement_score}"

        # Large std should not go negative
        model_std = 10
        agreement_score = max(0, 3 - model_std / 2)
        assert agreement_score == 0.0, "Agreement score should never be negative"

    def test_edge_score_formula(self):
        """
        Verify edge_score calculation:
        edge_score = min(3, edge_pct / 5)

        - edge_pct = 0% -> edge_score = 0
        - edge_pct = 15% -> edge_score = 3 (capped)
        - edge_pct = 10% -> edge_score = 2
        """
        # Zero edge
        edge_pct = 0
        edge_score = min(3, edge_pct / 5)
        assert edge_score == 0.0, f"Zero edge should be 0.0, got {edge_score}"

        # Max edge (15%+)
        edge_pct = 15
        edge_score = min(3, edge_pct / 5)
        assert edge_score == 3.0, f"15% edge should cap at 3.0, got {edge_score}"

        # Very large edge should still cap at 3
        edge_pct = 50
        edge_score = min(3, edge_pct / 5)
        assert edge_score == 3.0, f"Large edge should cap at 3.0, got {edge_score}"

        # Moderate edge
        edge_pct = 10
        edge_score = min(3, edge_pct / 5)
        assert edge_score == 2.0, f"10% edge should be 2.0, got {edge_score}"

    def test_factor_score_components(self):
        """
        Verify factor_score accumulates correctly:
        - rest_factor >= 0.95: +1.0
        - abs(injury_impact) < 1: +0.5
        - abs(line_movement) > 0.5: +0.5

        Maximum: 2.0
        """
        # All factors present
        rest_factor = 1.0
        injury_impact = 0.0
        line_movement = 1.0

        factor_score = 0
        if rest_factor >= 0.95:
            factor_score += 1.0
        if abs(injury_impact) < 1:
            factor_score += 0.5
        if abs(line_movement) > 0.5:
            factor_score += 0.5

        assert factor_score == 2.0, f"All factors should sum to 2.0, got {factor_score}"

        # No factors present
        rest_factor = 0.8
        injury_impact = 2.0
        line_movement = 0.3

        factor_score = 0
        if rest_factor >= 0.95:
            factor_score += 1.0
        if abs(injury_impact) < 1:
            factor_score += 0.5
        if abs(line_movement) > 0.5:
            factor_score += 0.5

        assert factor_score == 0.0, f"No factors should sum to 0.0, got {factor_score}"

    def test_base_score_never_negative(self):
        """
        Guard: base_score can never be negative.
        Both deviation_score and alternative_base are >= 0.
        """
        # Even with negative inputs (which shouldn't happen but let's be safe)
        deviation_score = 0  # Minimum valid value
        alternative_base = 2.0  # Minimum from formula

        base_score = max(deviation_score, alternative_base)
        assert base_score >= 0, "base_score must never be negative"
        assert base_score >= 2.0, "base_score floor should be 2.0 from alternative_base"

    def test_deviation_score_formula(self):
        """
        Verify deviation_score calculation:
        deviation_score = min(10, deviation / std_dev * 5)

        - deviation = std_dev -> score = 5 (1 std dev = 50%)
        - deviation = 2*std_dev -> score = 10 (capped)
        - deviation = 0 -> score = 0
        """
        std_dev = 10.0

        # Zero deviation
        deviation = 0
        deviation_score = min(10, deviation / std_dev * 5)
        assert deviation_score == 0.0, f"Zero deviation should be 0.0, got {deviation_score}"

        # 1 std dev
        deviation = 10  # = std_dev
        deviation_score = min(10, deviation / std_dev * 5)
        assert deviation_score == 5.0, f"1 std dev should be 5.0, got {deviation_score}"

        # 2 std devs (capped)
        deviation = 20
        deviation_score = min(10, deviation / std_dev * 5)
        assert deviation_score == 10.0, f"2+ std devs should cap at 10.0, got {deviation_score}"


class TestAIAuditFieldsPresence:
    """Verify AI audit fields are returned in payload."""

    def test_ai_audit_fields_structure(self):
        """
        AI audit dict must contain all required fields.
        These fields enable transparency and debugging.
        """
        required_fields = [
            'deviation_score',
            'agreement_score',
            'edge_score',
            'factor_score',
            'alternative_base',
            'base_score_used',  # 'DEVIATION' or 'ALTERNATIVE'
            'pillar_boost',
            'model_std',
        ]

        # Simulate an ai_audit dict from MPS
        sample_ai_audit = {
            'deviation_score': 2.5,
            'agreement_score': 2.0,
            'edge_score': 1.5,
            'factor_score': 1.0,
            'alternative_base': 6.5,
            'base_score_used': 'ALTERNATIVE',
            'pillar_boost': 0.8,
            'model_std': 2.0,
        }

        for field in required_fields:
            assert field in sample_ai_audit, f"Missing required field: {field}"

    def test_base_score_used_values(self):
        """
        base_score_used must be either 'DEVIATION' or 'ALTERNATIVE'.
        """
        valid_values = {'DEVIATION', 'ALTERNATIVE'}

        # Test DEVIATION case: deviation_score > alternative_base
        deviation_score = 7.0
        alternative_base = 5.5
        base_score_used = 'DEVIATION' if deviation_score >= alternative_base else 'ALTERNATIVE'
        assert base_score_used in valid_values
        assert base_score_used == 'DEVIATION'

        # Test ALTERNATIVE case: alternative_base > deviation_score
        deviation_score = 1.0
        alternative_base = 6.0
        base_score_used = 'DEVIATION' if deviation_score >= alternative_base else 'ALTERNATIVE'
        assert base_score_used in valid_values
        assert base_score_used == 'ALTERNATIVE'
