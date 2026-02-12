"""
test_reconciliation.py — v20.1 Migration Verification
======================================================
Run: cd /Users/apple/ai-betting-backend && python -m pytest tests/test_reconciliation.py -v

Tests:
  1. Final score reconciles to within 0.02 of explicit term sum
  2. jarvis_msrf_component never exceeds JARVIS_MSRF_COMPONENT_CAP
  3. serp_boost always 0.0 and serp_status == "DISABLED"
  4. jason_sim_boost respects new cap (2.0) and preserves sign
  5. Engine weights frozen at 25/35/20/20
  6. MSRF post-base boost is always 0.0
  7. Tier determination stable across known scenarios
  8. Jarvis engine surfaces all required audit fields
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date
from core.compute_final_score import (
    ENGINE_WEIGHTS, JARVIS_MSRF_COMPONENT_CAP, JASON_SIM_BOOST_CAP,
    MSRF_BOOST_CAP, MSRF_ENABLED, SERP_BOOST_CAP_TOTAL, SERP_ENABLED,
    GOLD_STAR_GATES, TITANIUM_RULE, CONFLUENCE_LEVELS,
    compute_final_score_option_a, compute_base_score,
)
from core.jarvis_ophis_hybrid import calculate_hybrid_jarvis_score


# =========================================================================
# TEST 1: Reconciliation — final_score matches term sum within 0.02
# =========================================================================

class TestReconciliation:

    def _make(self, **kw):
        defaults = dict(
            ai_score=7.0, research_score=7.5, esoteric_score=6.0, jarvis_score=6.5,
            context_modifier=0.15, confluence_boost=1.0, jason_sim_boost=0.5,
        )
        defaults.update(kw)
        return compute_final_score_option_a(**defaults)

    def test_basic_reconciliation(self):
        r = self._make()
        assert r["reconciliation_pass"], f"delta={r['reconciliation_delta']}"
        assert r["reconciliation_delta"] <= 0.02

    def test_reconciliation_with_all_terms(self):
        r = self._make(
            ensemble_boost=0.5, hook_penalty=-0.3,
            expert_consensus_boost=0.4, prop_correlation_adjustment=0.2,
            totals_calibration_adj=-0.1,
        )
        assert r["reconciliation_pass"], f"delta={r['reconciliation_delta']}"

    def test_reconciliation_at_ceiling(self):
        """Scores that hit 10.0 cap still reconcile."""
        r = self._make(
            ai_score=9.0, research_score=9.5, esoteric_score=9.0, jarvis_score=9.0,
            confluence_boost=5.0, jason_sim_boost=2.0,
        )
        assert r["final_score"] == 10.0
        assert r["reconciliation_pass"]

    def test_reconciliation_at_floor(self):
        """Very low scores still reconcile."""
        r = self._make(
            ai_score=2.0, research_score=2.0, esoteric_score=2.0, jarvis_score=2.0,
            context_modifier=0.0, confluence_boost=0.0, jason_sim_boost=-2.0,
        )
        assert r["final_score"] >= 0.0
        assert r["reconciliation_pass"]

    def test_reconciliation_negative_terms(self):
        r = self._make(
            jason_sim_boost=-1.5, hook_penalty=-0.3,
            totals_calibration_adj=-0.4,
        )
        assert r["reconciliation_pass"]

    def test_every_term_present_in_output(self):
        """Contract: every additive/subtractive term surfaced in payload."""
        r = self._make()
        required = [
            "base_score", "context_modifier", "confluence_boost",
            "jason_sim_boost", "ensemble_boost", "hook_penalty",
            "expert_consensus_boost", "prop_correlation_adjustment",
            "totals_calibration_adj", "serp_boost", "msrf_boost",
        ]
        for key in required:
            assert key in r["terms"], f"Missing term: {key}"


# =========================================================================
# TEST 2: MSRF component clamped inside Jarvis engine
# =========================================================================

class TestMSRFClamping:

    def test_jarvis_msrf_component_capped(self):
        r = calculate_hybrid_jarvis_score(
            home_team="Boston Bruins", away_team="Pittsburgh Penguins",
            spread=-1.5, odds=120, public_pct=70, sport="NHL",
            matchup_date=date(2026, 2, 10),
        )
        assert r["jarvis_msrf_component"] <= JARVIS_MSRF_COMPONENT_CAP, (
            f"MSRF component {r['jarvis_msrf_component']} exceeds cap {JARVIS_MSRF_COMPONENT_CAP}"
        )

    def test_msrf_status_is_in_jarvis(self):
        r = calculate_hybrid_jarvis_score(
            home_team="Toronto Maple Leafs", away_team="Montreal Canadiens",
            sport="NHL", matchup_date=date(2026, 2, 10),
        )
        assert r["msrf_status"] == "IN_JARVIS"

    def test_msrf_raw_vs_clamped(self):
        r = calculate_hybrid_jarvis_score(
            home_team="Chicago Blackhawks", away_team="Detroit Red Wings",
            spread=-2, odds=130, sport="NHL", matchup_date=date(2026, 2, 10),
        )
        # clamped <= cap always
        assert r["jarvis_msrf_component"] <= JARVIS_MSRF_COMPONENT_CAP
        # clamped <= raw always
        assert r["jarvis_msrf_component"] <= r["jarvis_msrf_component_raw"] + 0.001

    def test_msrf_not_in_postbase_sum(self):
        """MSRF must never appear as a non-zero post-base boost."""
        r = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=7.0,
            msrf_boost=999.0,  # caller tries to pass MSRF — must be forced to 0.0
        )
        assert r["terms"]["msrf_boost"] == 0.0, "MSRF post-base must be forced to 0.0"

    def test_contract_msrf_disabled(self):
        assert MSRF_BOOST_CAP == 0.0
        assert MSRF_ENABLED is False


# =========================================================================
# TEST 3: SERP always 0.0 and status DISABLED
# =========================================================================

class TestSERPDisabled:

    def test_serp_boost_zero(self):
        r = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=7.0,
            serp_boost=100.0,  # caller tries to pass SERP — must be forced to 0.0
        )
        assert r["terms"]["serp_boost"] == 0.0
        assert r["serp_status"] == "DISABLED"

    def test_serp_never_influences_score(self):
        r1 = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=7.0,
            serp_boost=0.0,
        )
        r2 = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=7.0,
            serp_boost=4.3,  # old max — should be ignored
        )
        assert r1["final_score"] == r2["final_score"], "SERP must not affect score"

    def test_contract_serp_disabled(self):
        assert SERP_BOOST_CAP_TOTAL == 0.0
        assert SERP_ENABLED is False


# =========================================================================
# TEST 4: Jason Sim respects new cap (2.0) and preserves sign
# =========================================================================

class TestJasonSimBounded:

    def test_positive_capped(self):
        r = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=7.0,
            jason_sim_boost=5.0,  # exceeds cap
        )
        assert r["terms"]["jason_sim_boost"] == JASON_SIM_BOOST_CAP

    def test_negative_capped(self):
        r = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=7.0,
            jason_sim_boost=-5.0,  # exceeds negative cap
        )
        assert r["terms"]["jason_sim_boost"] == -JASON_SIM_BOOST_CAP

    def test_sign_preserved_positive(self):
        r = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=7.0,
            jason_sim_boost=1.5,
        )
        assert r["terms"]["jason_sim_boost"] == 1.5
        assert r["terms"]["jason_sim_boost"] > 0

    def test_sign_preserved_negative(self):
        r = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=7.0,
            jason_sim_boost=-1.2,
        )
        assert r["terms"]["jason_sim_boost"] == -1.2
        assert r["terms"]["jason_sim_boost"] < 0

    def test_within_old_cap_unchanged(self):
        """Values within old 1.5 cap pass through identically."""
        r = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=7.0,
            jason_sim_boost=1.0,
        )
        assert r["terms"]["jason_sim_boost"] == 1.0

    def test_newly_uncapped_values(self):
        """Values between 1.5 and 2.0 that were previously capped now pass through."""
        for v in [1.6, 1.8, 2.0]:
            r = compute_final_score_option_a(
                ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=7.0,
                jason_sim_boost=v,
            )
            assert abs(r["terms"]["jason_sim_boost"] - v) < 0.001, f"Expected {v}, got {r['terms']['jason_sim_boost']}"

    def test_jason_audit_fields(self):
        r = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=6.0, jarvis_score=7.0,
            jason_sim_boost=1.5, jason_status="BOOST",
            jason_reasons=["Monte Carlo +1.5: sharp alignment"],
        )
        assert r["jason_status"] == "BOOST"
        assert len(r["jason_reasons"]) == 1

    def test_cap_matches_contract(self):
        assert JASON_SIM_BOOST_CAP == 2.0


# =========================================================================
# TEST 5: Engine weights frozen at 25/35/20/20
# =========================================================================

class TestWeightsFrozen:

    def test_weights_exact(self):
        assert ENGINE_WEIGHTS["ai"] == 0.25
        assert ENGINE_WEIGHTS["research"] == 0.35
        assert ENGINE_WEIGHTS["esoteric"] == 0.15  # v20.19: reduced from 0.20
        assert ENGINE_WEIGHTS["jarvis"] == 0.25    # v20.19: increased from 0.20

    def test_weights_sum(self):
        assert abs(sum(ENGINE_WEIGHTS.values()) - 1.0) < 0.001

    def test_base_score_uses_frozen_weights(self):
        b = compute_base_score(8.0, 8.0, 8.0, 8.0)
        # All engines at 8.0 → base = 8.0 * 1.0 = 8.0
        assert abs(b["base_score"] - 8.0) < 0.001

    def test_base_score_individual_contributions(self):
        b = compute_base_score(10.0, 10.0, 10.0, 10.0)
        assert abs(b["contributions"]["ai"] - 2.5) < 0.001
        assert abs(b["contributions"]["research"] - 3.5) < 0.001
        assert abs(b["contributions"]["esoteric"] - 1.5) < 0.001  # v20.19: 10.0 * 0.15 = 1.5
        assert abs(b["contributions"]["jarvis"] - 2.5) < 0.001   # v20.19: 10.0 * 0.25 = 2.5


# =========================================================================
# TEST 6: Tier determination stable
# =========================================================================

class TestTiering:

    def test_titanium(self):
        r = compute_final_score_option_a(
            ai_score=8.5, research_score=8.2, esoteric_score=8.1, jarvis_score=8.8,
            confluence_boost=1.0,
        )
        assert r["tier"] == "TITANIUM"

    def test_gold_star(self):
        r = compute_final_score_option_a(
            ai_score=7.0, research_score=7.5, esoteric_score=5.5, jarvis_score=7.0,
            confluence_boost=1.0,
        )
        assert r["tier"] == "GOLD_STAR"

    def test_edge_lean_fails_gate(self):
        r = compute_final_score_option_a(
            ai_score=7.0, research_score=7.0, esoteric_score=5.0, jarvis_score=5.5,
            confluence_boost=1.0,
        )
        # Jarvis 5.5 < gate 6.0 → fails gates
        assert r["tier"] == "EDGE_LEAN"
        assert "jarvis_score" in r["tier_detail"]["failed_gates"]

    def test_no_pick(self):
        r = compute_final_score_option_a(
            ai_score=4.0, research_score=5.0, esoteric_score=3.0, jarvis_score=4.0,
        )
        assert r["tier"] == "NO_PICK"


# =========================================================================
# TEST 7: Jarvis engine payload completeness
# =========================================================================

class TestJarvisPayload:

    def test_all_audit_fields_present(self):
        r = calculate_hybrid_jarvis_score(
            home_team="Los Angeles Lakers", away_team="Boston Celtics",
            sport="NBA", matchup_date=date(2026, 2, 10),
        )
        # v2.2: Updated field names to match actual hybrid output
        required = [
            "jarvis_rs", "jarvis_active", "jarvis_hits_count",
            "jarvis_triggers_hit", "jarvis_reasons", "jarvis_fail_reasons",
            "jarvis_inputs_used", "immortal_detected", "version",
            "blend_type", "whisper_tier",
            "ophis_raw", "ophis_score_norm",  # v2.2: was ophis_normalized
            "jarvis_msrf_component", "jarvis_msrf_component_raw", "msrf_status",
            "gematria",
        ]
        for field in required:
            assert field in r, f"Missing Jarvis field: {field}"

    def test_jarvis_score_0_to_10(self):
        r = calculate_hybrid_jarvis_score(
            home_team="New York Rangers", away_team="New Jersey Devils",
            sport="NHL", matchup_date=date(2026, 2, 10),
        )
        assert 0.0 <= r["jarvis_rs"] <= 10.0

    def test_jarvis_contributes_correct_weight_in_base4(self):
        r = calculate_hybrid_jarvis_score(
            home_team="Golden State Warriors", away_team="Phoenix Suns",
            sport="NBA", matchup_date=date(2026, 2, 10),
        )
        js = r["jarvis_rs"]
        base = compute_base_score(7.0, 7.0, 7.0, js)
        expected_contribution = round(js * 0.25, 4)  # v20.19: 0.25
        assert abs(base["contributions"]["jarvis"] - expected_contribution) < 0.001

    def test_empty_inputs_returns_null_score(self):
        r = calculate_hybrid_jarvis_score(home_team="", away_team="")
        assert r["jarvis_rs"] is None
        # v2.2.1: When inputs are missing, MSRF can't compute - correct status is INPUTS_MISSING
        assert r["msrf_status"] == "INPUTS_MISSING"


# =========================================================================
# TEST 8: Production audit scenario — exact reconciliation
# =========================================================================

class TestProductionScenario:
    """Replay the exact NHL Under 5.5 audit scenario from production."""

    def test_nhl_audit_scenario(self):
        """
        v20.19 weights: ai=0.25, research=0.35, esoteric=0.15, jarvis=0.25
          base = 6.56*0.25 + 7.2*0.35 + 5.1*0.15 + 4.5*0.25 = 6.05
          final = min(10, 6.05+3.0+0.0+0.0+0.1+0.2) = 9.35
        """
        r = compute_final_score_option_a(
            ai_score=6.56, research_score=7.2,
            esoteric_score=5.1, jarvis_score=4.5,
            context_modifier=0.2,
            confluence_boost=3.0,
            jason_sim_boost=0.1,
            msrf_boost=0.8,   # passed but forced to 0.0
            serp_boost=0.5,   # passed but forced to 0.0
        )
        assert abs(r["base_score_detail"]["base_score"] - 6.05) < 0.01  # v20.19: updated for new weights
        assert r["terms"]["msrf_boost"] == 0.0
        assert r["terms"]["serp_boost"] == 0.0
        assert abs(r["final_score"] - 9.35) < 0.02  # v20.19: 6.05+0.2+3.0+0.1 = 9.35
        assert r["reconciliation_pass"]
        assert r["tier"] == "EDGE_LEAN"  # Jarvis 4.5 < gate 6.0


# =========================================================================
# Runner
# =========================================================================

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
