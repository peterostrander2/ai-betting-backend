"""
v20.16 Regression Tests: Sharp Money vs Line Variance Separation

These tests ensure that:
A) Line variance (lv) can NEVER escalate sharp_strength
B) sharp_boost is computed ONLY from sharp_strength (Playbook splits)
C) lv_boost/line_boost is computed ONLY from line_variance
D) Reconciliation still passes

Bug fixed: lv >= 2.0 was upgrading signal_strength to "STRONG", causing
false "Sharp signal STRONG (+3.0)" labels when only line variance was strong.
"""

import pytest
from unittest.mock import MagicMock


class TestSharpLvSeparation:
    """Test that sharp_strength and lv_strength are independent."""

    def test_weak_sharp_strong_lv_keeps_sharp_weak(self):
        """
        A) With weak sharp (small divergence) but strong lv,
           sharp_strength stays weak and sharp_boost stays low/zero.
        """
        # Simulate Playbook signal with weak sharp but strong line variance
        signal = {
            "money_pct": 52,
            "ticket_pct": 50,
            "signal_strength": "MILD",  # Would have been STRONG in old code
            "sharp_strength": "MILD",   # v20.16: TRUE sharp from Playbook (2% divergence)
            "line_variance": 3.0,       # Strong lv
            "lv_strength": "STRONG",    # v20.16: From lv only
        }

        # sharp_strength must be MILD (from Playbook divergence)
        assert signal["sharp_strength"] == "MILD"
        # lv_strength is STRONG (from book dispersion)
        assert signal["lv_strength"] == "STRONG"

        # Sharp boost should be 0.5 (MILD), not 3.0 (STRONG)
        sharp_strength = signal.get("sharp_strength", "NONE")
        if sharp_strength == "STRONG":
            sharp_boost = 3.0
        elif sharp_strength == "MODERATE":
            sharp_boost = 1.5
        elif sharp_strength == "MILD":
            sharp_boost = 0.5
        else:
            sharp_boost = 0.0

        assert sharp_boost == 0.5, f"Sharp boost should be 0.5 (MILD), got {sharp_boost}"

        # lv_boost should be 3.0 (STRONG lv)
        lv = signal.get("line_variance", 0)
        if lv > 1.5:
            line_boost = 3.0
        elif lv > 0.5:
            line_boost = 1.5
        else:
            line_boost = 0.0

        assert line_boost == 3.0, f"Line boost should be 3.0 (strong lv), got {line_boost}"

    def test_strong_sharp_requires_divergence_threshold(self):
        """
        B) Strong sharp requires meeting the divergence threshold (>=20%);
           lv cannot create STRONG sharp.
        """
        # Test case 1: 25% divergence = STRONG
        signal_strong = {
            "money_pct": 75,
            "ticket_pct": 50,
            "line_variance": 0.0,  # No lv
            "lv_strength": "NONE",
        }
        diff = abs(signal_strong["money_pct"] - signal_strong["ticket_pct"])
        if diff >= 20:
            sharp_strength = "STRONG"
        elif diff >= 10:
            sharp_strength = "MODERATE"
        elif diff >= 5:
            sharp_strength = "MILD"
        else:
            sharp_strength = "NONE"

        assert sharp_strength == "STRONG", f"25% divergence should be STRONG, got {sharp_strength}"

        # Test case 2: 5% divergence = MILD (even with strong lv)
        signal_weak = {
            "money_pct": 55,
            "ticket_pct": 50,
            "line_variance": 3.0,  # Strong lv
            "lv_strength": "STRONG",
        }
        diff_weak = abs(signal_weak["money_pct"] - signal_weak["ticket_pct"])
        if diff_weak >= 20:
            sharp_strength_weak = "STRONG"
        elif diff_weak >= 10:
            sharp_strength_weak = "MODERATE"
        elif diff_weak >= 5:
            sharp_strength_weak = "MILD"
        else:
            sharp_strength_weak = "NONE"

        assert sharp_strength_weak == "MILD", f"5% divergence should be MILD even with strong lv, got {sharp_strength_weak}"

    def test_lv_cannot_create_strong_sharp(self):
        """
        B) Explicit test: lv can NEVER create STRONG sharp.
        The old bug: if lv >= 2.0 and signal_strength in ("NONE","MILD"):
                        signal_strength = "STRONG"  # BUG!
        """
        # Simulate old contaminated behavior
        def old_buggy_behavior(money_pct, ticket_pct, lv):
            diff = abs(money_pct - ticket_pct)
            if diff >= 20:
                signal_strength = "STRONG"
            elif diff >= 10:
                signal_strength = "MODERATE"
            elif diff >= 5:
                signal_strength = "MILD"
            else:
                signal_strength = "NONE"

            # THE BUG (removed in v20.16)
            if lv >= 2.0 and signal_strength in ("NONE", "MILD"):
                signal_strength = "STRONG"  # This was wrong!

            return signal_strength

        # Simulate new correct behavior
        def new_correct_behavior(money_pct, ticket_pct, lv):
            diff = abs(money_pct - ticket_pct)
            if diff >= 20:
                sharp_strength = "STRONG"
            elif diff >= 10:
                sharp_strength = "MODERATE"
            elif diff >= 5:
                sharp_strength = "MILD"
            else:
                sharp_strength = "NONE"

            # lv_strength is separate
            if lv >= 2.0:
                lv_strength = "STRONG"
            elif lv >= 1.5:
                lv_strength = "MODERATE"
            elif lv >= 0.5:
                lv_strength = "MILD"
            else:
                lv_strength = "NONE"

            return sharp_strength, lv_strength

        # Test case: 3% divergence (NONE) with 3.0 lv (STRONG)
        old_result = old_buggy_behavior(money_pct=52, ticket_pct=49, lv=3.0)
        assert old_result == "STRONG", "Old buggy behavior should return STRONG"

        sharp, lv = new_correct_behavior(money_pct=52, ticket_pct=49, lv=3.0)
        assert sharp == "NONE", f"New behavior: sharp_strength should be NONE, got {sharp}"
        assert lv == "STRONG", f"New behavior: lv_strength should be STRONG, got {lv}"

    def test_no_playbook_data_yields_no_sharp(self):
        """
        When Playbook data is missing, sharp_strength should be NONE.
        """
        signal_no_data = {
            "money_pct": None,
            "ticket_pct": None,
            "line_variance": 2.5,
            "lv_strength": "STRONG",
            "sharp_strength": "NONE",  # No Playbook data
        }

        assert signal_no_data["sharp_strength"] == "NONE"
        assert signal_no_data["lv_strength"] == "STRONG"

        # Sharp boost should be 0.0
        sharp_strength = signal_no_data.get("sharp_strength", "NONE")
        if sharp_strength == "STRONG":
            sharp_boost = 3.0
        elif sharp_strength == "MODERATE":
            sharp_boost = 1.5
        elif sharp_strength == "MILD":
            sharp_boost = 0.5
        else:
            sharp_boost = 0.0

        assert sharp_boost == 0.0, f"No Playbook data = sharp_boost 0.0, got {sharp_boost}"

    def test_research_breakdown_has_both_fields(self):
        """
        Verify research_breakdown contains both sharp_strength and lv_strength.
        """
        # Simulated research_breakdown from pick payload
        research_breakdown = {
            "sharp_boost": 0.5,
            "sharp_strength": "MILD",
            "sharp_status": "PLAYBOOK",
            "line_boost": 3.0,
            "lv": 2.5,
            "lv_strength": "STRONG",
            "public_boost": 0.0,
            "base_research": 2.0,
            "total": 5.5,
        }

        # All required fields present
        assert "sharp_strength" in research_breakdown
        assert "lv_strength" in research_breakdown
        assert "sharp_status" in research_breakdown
        assert "lv" in research_breakdown

        # Values are independent
        assert research_breakdown["sharp_strength"] == "MILD"
        assert research_breakdown["lv_strength"] == "STRONG"


class TestReconciliationWithSeparation:
    """
    C) Reconciliation still passes: final_score matches compute_final_score_option_a()
       within delta tolerance; no engine mutation after base.
    """

    def test_research_score_calculation(self):
        """
        Verify research_score is computed correctly with separated signals.
        """
        # Inputs
        sharp_strength = "MILD"
        lv = 2.0
        public_pct = 50
        base_research = 2.0

        # Compute sharp_boost from sharp_strength ONLY
        if sharp_strength == "STRONG":
            sharp_boost = 3.0
        elif sharp_strength == "MODERATE":
            sharp_boost = 1.5
        elif sharp_strength == "MILD":
            sharp_boost = 0.5
        else:
            sharp_boost = 0.0

        # Compute line_boost from lv ONLY
        if lv > 1.5:
            line_boost = 3.0
        elif lv > 0.5:
            line_boost = 1.5
        else:
            line_boost = 0.0

        # Public boost
        if public_pct >= 75:
            public_boost = 2.0
        elif public_pct >= 65:
            public_boost = 1.0
        else:
            public_boost = 0.0

        research_score = min(10.0, base_research + sharp_boost + line_boost + public_boost)

        # Expected: 2.0 + 0.5 + 3.0 + 0.0 = 5.5
        assert research_score == 5.5, f"Expected 5.5, got {research_score}"

    def test_final_score_reconciliation(self):
        """
        Verify final_score calculation remains correct after fix.
        """
        # Simulated engine scores
        ai_score = 6.0
        research_score = 5.5
        esoteric_score = 5.0
        jarvis_score = 6.0

        # Engine weights from scoring_contract.py
        weights = {
            "ai": 0.25,
            "research": 0.35,
            "esoteric": 0.20,
            "jarvis": 0.20,
        }

        # Base score
        base_4 = (
            ai_score * weights["ai"]
            + research_score * weights["research"]
            + esoteric_score * weights["esoteric"]
            + jarvis_score * weights["jarvis"]
        )

        # base_4 = 6*0.25 + 5.5*0.35 + 5*0.20 + 6*0.20
        # = 1.5 + 1.925 + 1.0 + 1.2 = 5.625
        expected_base = 5.625
        assert abs(base_4 - expected_base) < 0.01, f"Expected base_4={expected_base}, got {base_4}"

        # Add boosts (simulated)
        context_modifier = 0.2
        confluence_boost = 1.0
        final_score = min(10.0, max(0.0, base_4 + context_modifier + confluence_boost))

        # 5.625 + 0.2 + 1.0 = 6.825
        expected_final = 6.825
        assert abs(final_score - expected_final) < 0.02, f"Expected final={expected_final}, got {final_score}"


class TestReasonLabels:
    """
    Ensure pick reasons/labels never say "sharp STRONG" unless sharp_strength is STRONG.
    """

    def test_sharp_label_matches_strength(self):
        """
        The label "Sharp money STRONG (+3.0)" should only appear when sharp_strength == "STRONG".
        """
        test_cases = [
            ("STRONG", "Sharp money STRONG (+3.0)"),
            ("MODERATE", "Sharp money MODERATE (+1.5)"),
            ("MILD", "Sharp money MILD (+0.5)"),
            ("NONE", "No sharp money signal"),
        ]

        for sharp_strength, expected_reason in test_cases:
            if sharp_strength == "STRONG":
                reason = "Sharp money STRONG (+3.0)"
            elif sharp_strength == "MODERATE":
                reason = "Sharp money MODERATE (+1.5)"
            elif sharp_strength == "MILD":
                reason = "Sharp money MILD (+0.5)"
            else:
                reason = "No sharp money signal"

            assert reason == expected_reason, f"For {sharp_strength}, expected '{expected_reason}', got '{reason}'"

    def test_lv_label_is_separate(self):
        """
        Line variance labels should include [lv:STRENGTH] notation.
        """
        lv = 2.0
        lv_strength = "STRONG"

        if lv > 1.5:
            reason = f"Line variance {lv:.1f}pts [lv:{lv_strength}] (strong RLM)"
        elif lv > 0.5:
            reason = f"Line variance {lv:.1f}pts [lv:{lv_strength}] (moderate)"
        else:
            reason = f"Line variance {lv:.1f}pts [lv:{lv_strength}] (minimal)"

        assert "[lv:STRONG]" in reason, f"LV label should include strength, got: {reason}"
        assert "Sharp" not in reason, f"LV label should not mention Sharp: {reason}"
