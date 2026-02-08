"""
Hard guardrails to prevent regression from Option A:

Option A:
- BASE_4 weighted engines only: ai, research, esoteric, jarvis
- Context is NOT an engine weight
- Context is a bounded modifier via CONTEXT_MODIFIER_CAP
- FINAL = base_score + context_modifier + confluence_boost + msrf_boost + jason_sim_boost + serp_boost

This test is intentionally "dumb and strict":
- It checks the contract file for the exact engine keys.
- It checks the two active scoring paths for forbidden patterns and required invariants.
"""

from __future__ import annotations

import os
import re


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# The only two places that should compute final_score in production per your repo invariant.
SCORING_PATHS = [
    os.path.join(REPO_ROOT, "core", "scoring_pipeline.py"),
    os.path.join(REPO_ROOT, "live_data_router.py"),
]

CONTRACT_PATH = os.path.join(REPO_ROOT, "core", "scoring_contract.py")

FORBIDDEN_PATTERNS_GLOBAL = [
    r'ENGINE_WEIGHTS\[\s*"context"\s*\]',
    r"ENGINE_WEIGHT_CONTEXT",
    r"CONTEXT_WEIGHT",
    r"\bBASE_5\b",
    r"\b5-Engine\b",
    r"\b5 engine\b",
]

# Required signals for Option A being present.
REQUIRED_CONTRACT_MARKERS = [
    "ENGINE_WEIGHTS",
    "CONTEXT_MODIFIER_CAP",
]

# Option A engine keys (context must not appear)
REQUIRED_ENGINE_KEYS = {"ai", "research", "esoteric", "jarvis"}
FORBIDDEN_ENGINE_KEYS = {"context"}


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _assert_no_patterns(text: str, patterns: list[str], where: str) -> None:
    for pat in patterns:
        if re.search(pat, text):
            raise AssertionError(f"Forbidden pattern matched in {where}: {pat}")


def test_option_a_contract_is_canonical() -> None:
    """Contract must describe Option A: 4 engine weights + context cap, no context engine weight."""
    text = _read(CONTRACT_PATH)

    for marker in REQUIRED_CONTRACT_MARKERS:
        assert marker in text, f"Missing required marker in contract: {marker}"

    # Pull ENGINE_WEIGHTS dict keys using a conservative regex.
    # This avoids importing the module (which could have side effects in some repos).
    m = re.search(r"ENGINE_WEIGHTS\s*=\s*\{([\s\S]*?)\}\s*", text)
    assert m, "Could not locate ENGINE_WEIGHTS dict in core/scoring_contract.py"

    body = m.group(1)
    keys = set(re.findall(r'"\s*([a-zA-Z0-9_]+)\s*"\s*:', body))

    # Must contain exactly the 4 base engines; forbid context.
    assert REQUIRED_ENGINE_KEYS.issubset(keys), f"ENGINE_WEIGHTS missing keys: {REQUIRED_ENGINE_KEYS - keys}"
    assert keys.isdisjoint(FORBIDDEN_ENGINE_KEYS), f"ENGINE_WEIGHTS contains forbidden keys: {keys & FORBIDDEN_ENGINE_KEYS}"


def test_option_a_scoring_paths_forbid_context_engine_weighting() -> None:
    """The two active scoring paths must not reference context as an engine weight or BASE_5."""
    for path in SCORING_PATHS:
        text = _read(path)
        _assert_no_patterns(text, FORBIDDEN_PATTERNS_GLOBAL, where=os.path.relpath(path, REPO_ROOT))


def test_option_a_scoring_paths_reference_context_cap() -> None:
    """
    Hard requirement: context modifier must be bounded by CONTEXT_MODIFIER_CAP in scoring paths
    (or imported and used indirectly, but still present as a token).
    """
    for path in SCORING_PATHS:
        text = _read(path)
        assert "CONTEXT_MODIFIER_CAP" in text, (
            f"{os.path.relpath(path, REPO_ROOT)} does not reference CONTEXT_MODIFIER_CAP; "
            "this risks unbounded context drift or accidental context weighting."
        )


def test_option_a_final_score_formula_present() -> None:
    """
    Ensure both scoring paths still include the Option A FINAL shape.
    This is intentionally strict because you want to prevent silent formula drift.
    """
    required_tokens = [
        "final_score",
        "base_score",
        "context_modifier",
        "confluence_boost",
        "jason_sim_boost",
    ]

    for path in SCORING_PATHS:
        text = _read(path)
        for tok in required_tokens:
            assert tok in text, f"{os.path.relpath(path, REPO_ROOT)} missing token: {tok}"

        # Require the shared helper to be used (single source of final score math).
        assert "compute_final_score_option_a" in text, (
            f"{os.path.relpath(path, REPO_ROOT)} must use compute_final_score_option_a for final score math"
        )


def test_option_a_sample_formula_with_context_cap_and_additive_boosts() -> None:
    """
    Ensure Option A math is consistent:
    - BASE_4 uses only the 4 engines and their weights.
    - context_modifier is capped to CONTEXT_MODIFIER_CAP.
    - boosts (confluence, MSRF, SERP, Jason) are additive and NOT engines.
    """
    from core.scoring_contract import ENGINE_WEIGHTS, CONTEXT_MODIFIER_CAP

    ai = 8.0
    research = 7.0
    esoteric = 6.0
    jarvis = 5.0

    base_score = (
        ai * ENGINE_WEIGHTS["ai"]
        + research * ENGINE_WEIGHTS["research"]
        + esoteric * ENGINE_WEIGHTS["esoteric"]
        + jarvis * ENGINE_WEIGHTS["jarvis"]
    )

    # Context is a bounded modifier, not a weighted engine.
    raw_context_modifier = 0.6
    context_modifier = max(-CONTEXT_MODIFIER_CAP, min(CONTEXT_MODIFIER_CAP, raw_context_modifier))

    confluence_boost = 1.0
    msrf_boost = 0.4
    serp_boost = 0.2
    jason_sim_boost = -0.3

    expected_final = base_score + context_modifier + confluence_boost + msrf_boost + serp_boost + jason_sim_boost

    # Sanity checks on cap and additive boosts
    assert context_modifier == CONTEXT_MODIFIER_CAP, "Context modifier must be capped to CONTEXT_MODIFIER_CAP"
    assert round(expected_final, 4) == round(
        base_score + context_modifier + (confluence_boost + msrf_boost + serp_boost) + jason_sim_boost,
        4,
    )


def test_context_modifier_clamped() -> None:
    """Context modifier must be clamped to ±CONTEXT_MODIFIER_CAP."""
    from core.scoring_pipeline import clamp_context_modifier
    from core.scoring_contract import CONTEXT_MODIFIER_CAP

    assert clamp_context_modifier(0.9) == CONTEXT_MODIFIER_CAP
    assert clamp_context_modifier(-0.9) == -CONTEXT_MODIFIER_CAP


def test_compute_final_score_caps_serp_and_clamps_final() -> None:
    """SERP boost must be capped, total boosts capped, and final_score clamped to [0, 10]."""
    from core.scoring_pipeline import compute_final_score_option_a
    from core.scoring_contract import SERP_BOOST_CAP_TOTAL, TOTAL_BOOST_CAP

    # SERP individually capped to 4.3, but total boosts also capped to TOTAL_BOOST_CAP
    final_score, _ = compute_final_score_option_a(
        base_score=1.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=10.0,
    )
    assert final_score == 1.0 + TOTAL_BOOST_CAP  # Total boost cap applies

    # SERP within total boost cap (no stacking, stays under cap)
    # v20.11: TOTAL_BOOST_CAP lowered from 2.0 to 1.5, use 1.0 serp to stay under cap
    final_score, _ = compute_final_score_option_a(
        base_score=5.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=1.0,
    )
    assert final_score == 6.0  # 1.0 < TOTAL_BOOST_CAP (1.5), no cap applied

    # Final clamp (stacked boosts hit total cap, then clamped to 10)
    final_score, _ = compute_final_score_option_a(
        base_score=9.9,
        context_modifier=0.35,
        confluence_boost=1.0,
        msrf_boost=1.0,
        jason_sim_boost=1.0,
        serp_boost=SERP_BOOST_CAP_TOTAL,
    )
    assert final_score == 10.0


def test_msrf_and_serp_not_folded_into_confluence() -> None:
    """
    Guard: MSRF and SERP must NOT be folded into confluence_boost.
    They must remain separate additive boosts in the final score formula.
    """
    path = os.path.join(REPO_ROOT, "live_data_router.py")
    text = _read(path)

    assert not re.search(
        r'confluence\["boost"\]\s*=\s*confluence\.get\("boost",\s*0\)\s*\+\s*msrf_boost',
        text,
    ), "MSRF must not be added into confluence_boost"

    assert not re.search(
        r'confluence\["boost"\]\s*=\s*confluence\.get\("boost",\s*0\)\s*\+\s*serp_boost_total',
        text,
    ), "SERP must not be added into confluence_boost"


def test_payload_boost_fields_present_in_router() -> None:
    """
    Guard: best-bets payload must include separate boost fields and base/context fields.
    This is a code-level presence check to prevent silent removals.
    """
    path = os.path.join(REPO_ROOT, "live_data_router.py")
    text = _read(path)

    required_fields = [
        "base_score",
        "base_4_score",
        "context_modifier",
        "context_breakdown",
        "context_reasons",
        "confluence_boost",
        "confluence_reasons",
        "msrf_boost",
        "msrf_status",
        "jason_sim_boost",
        "jason_status",
        "serp_boost",
        "serp_status",
        # v20.3 post-base signals (8 Pillars of Execution)
        "hook_penalty",
        "hook_flagged",
        "hook_reasons",
        "expert_consensus_boost",
        "expert_status",
        "prop_correlation_adjustment",
        "prop_corr_status",
    ]
    for field in required_fields:
        assert field in text, f"live_data_router.py missing required payload field: {field}"


def test_scoring_contract_matches_scoring_logic_doc() -> None:
    """
    Guard: SCORING_LOGIC.md contract block must match core/scoring_contract.py.
    """
    contract = _read(CONTRACT_PATH)
    doc_path = os.path.join(REPO_ROOT, "SCORING_LOGIC.md")
    doc = _read(doc_path)

    # Extract JSON contract block from SCORING_LOGIC.md
    m = re.search(r"SCORING_CONTRACT_JSON\s*\n(\{[\s\S]*?\})\s*\nSCORING_CONTRACT_JSON", doc)
    assert m, "Missing SCORING_CONTRACT_JSON block in SCORING_LOGIC.md"

    # Extract ENGINE_WEIGHTS dict from contract file
    m2 = re.search(r"ENGINE_WEIGHTS\s*=\s*\{([\s\S]*?)\}\s*", contract)
    assert m2, "Could not locate ENGINE_WEIGHTS in core/scoring_contract.py"
    weights_text = m2.group(1)
    weights = dict(re.findall(r'"(ai|research|esoteric|jarvis)"\\s*:\\s*([0-9.]+)', weights_text))

    # Ensure the doc block contains matching weights
    for k, v in weights.items():
        assert f'"{k}": {v}' in m.group(1), f"SCORING_LOGIC.md contract missing {k}: {v}"


# ============================================================================
# v20.3 Post-Base Signals Tests (8 Pillars of Execution)
# ============================================================================

def test_v20_3_post_base_signals_math_reconciliation() -> None:
    """
    CRITICAL RECONCILIATION TEST: Ensures final_score = clamp(sum(all_terms)).

    This test verifies that:
    1. All additive terms are correctly summed in compute_final_score_option_a()
    2. The result is clamped to [0, 10]
    3. The difference from manual calculation is <= 0.02 (rounding tolerance)

    This prevents regression where signals are computed but not included in final score.
    """
    from core.scoring_pipeline import compute_final_score_option_a
    from core.scoring_contract import TOTAL_BOOST_CAP

    test_cases = [
        # Case 1: All positive values, under total boost cap
        {
            "base_score": 6.5,
            "context_modifier": 0.25,
            "confluence_boost": 0.5,
            "msrf_boost": 0.2,
            "jason_sim_boost": 0.1,
            "serp_boost": 0.3,
            "ensemble_adjustment": 0.15,
            "totals_calibration_adj": 0.0,
            "hook_penalty": 0.0,  # No penalty
            "expert_consensus_boost": 0.2,
            "prop_correlation_adjustment": 0.1,
        },
        # Case 2: Hook penalty active
        {
            "base_score": 7.0,
            "context_modifier": 0.2,
            "confluence_boost": 0.3,
            "msrf_boost": 0.1,
            "jason_sim_boost": 0.0,
            "serp_boost": 0.2,
            "ensemble_adjustment": 0.0,
            "totals_calibration_adj": -0.5,
            "hook_penalty": -0.2,  # Penalty active
            "expert_consensus_boost": 0.0,
            "prop_correlation_adjustment": -0.1,
        },
        # Case 3: All signals active with negative prop correlation
        {
            "base_score": 8.0,
            "context_modifier": 0.35,
            "confluence_boost": 0.0,
            "msrf_boost": 0.0,
            "jason_sim_boost": 0.0,
            "serp_boost": 0.0,
            "ensemble_adjustment": 0.5,
            "totals_calibration_adj": 0.75,
            "hook_penalty": -0.15,
            "expert_consensus_boost": 0.3,
            "prop_correlation_adjustment": -0.15,
        },
        # Case 4: Edge case - would exceed 10, should clamp
        {
            "base_score": 9.0,
            "context_modifier": 0.35,
            "confluence_boost": 1.0,
            "msrf_boost": 0.5,
            "jason_sim_boost": 0.5,
            "serp_boost": 0.5,  # Will be capped by TOTAL_BOOST_CAP
            "ensemble_adjustment": 0.5,
            "totals_calibration_adj": 0.75,
            "hook_penalty": 0.0,
            "expert_consensus_boost": 0.35,
            "prop_correlation_adjustment": 0.2,
        },
        # Case 5: Edge case - would go below 0, should clamp
        {
            "base_score": 1.0,
            "context_modifier": -0.35,
            "confluence_boost": 0.0,
            "msrf_boost": 0.0,
            "jason_sim_boost": -0.5,
            "serp_boost": 0.0,
            "ensemble_adjustment": -0.5,
            "totals_calibration_adj": -0.75,
            "hook_penalty": -0.25,
            "expert_consensus_boost": 0.0,
            "prop_correlation_adjustment": -0.2,
        },
    ]

    for i, case in enumerate(test_cases):
        final_score, _ = compute_final_score_option_a(**case)

        # Manual calculation (what the function should compute)
        # Note: boosts are capped by TOTAL_BOOST_CAP inside the function
        total_boosts = case["confluence_boost"] + case["msrf_boost"] + case["jason_sim_boost"] + case["serp_boost"]
        capped_boosts = min(TOTAL_BOOST_CAP, total_boosts)

        expected_raw = (
            case["base_score"]
            + case["context_modifier"]
            + capped_boosts
            + case["ensemble_adjustment"]
            + case["totals_calibration_adj"]
            + case["hook_penalty"]
            + case["expert_consensus_boost"]
            + case["prop_correlation_adjustment"]
        )
        expected_clamped = max(0.0, min(10.0, expected_raw))

        diff = abs(final_score - expected_clamped)
        assert diff <= 0.02, (
            f"Case {i+1} RECONCILIATION FAILED: "
            f"final_score={final_score}, expected={expected_clamped}, diff={diff}"
        )


def test_v20_3_hook_penalty_cap_enforcement() -> None:
    """
    Guard: hook_penalty must be capped to [-HOOK_PENALTY_CAP, 0].
    Penalties exceeding the cap should be clamped.
    """
    from core.scoring_pipeline import compute_final_score_option_a
    from core.scoring_contract import HOOK_PENALTY_CAP

    # Test excessive penalty is capped
    final_with_excessive, _ = compute_final_score_option_a(
        base_score=7.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=0.0,
        hook_penalty=-1.0,  # Excessive, should be capped to -0.25
    )

    final_with_capped, _ = compute_final_score_option_a(
        base_score=7.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=0.0,
        hook_penalty=-HOOK_PENALTY_CAP,
    )

    assert final_with_excessive == final_with_capped, (
        f"hook_penalty not capped: excessive={final_with_excessive}, capped={final_with_capped}"
    )

    # Verify penalty can't be positive
    final_with_positive, _ = compute_final_score_option_a(
        base_score=7.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=0.0,
        hook_penalty=0.5,  # Positive should be clamped to 0
    )

    final_with_zero, _ = compute_final_score_option_a(
        base_score=7.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=0.0,
        hook_penalty=0.0,
    )

    assert final_with_positive == final_with_zero, (
        "hook_penalty must be <=0, positive values should be clamped to 0"
    )


def test_v20_3_expert_consensus_cap_enforcement() -> None:
    """
    Guard: expert_consensus_boost must be capped to [0, EXPERT_CONSENSUS_CAP].
    """
    from core.scoring_pipeline import compute_final_score_option_a
    from core.scoring_contract import EXPERT_CONSENSUS_CAP

    # Test excessive boost is capped
    final_with_excessive, _ = compute_final_score_option_a(
        base_score=7.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=0.0,
        expert_consensus_boost=1.0,  # Excessive, should be capped to 0.35
    )

    final_with_capped, _ = compute_final_score_option_a(
        base_score=7.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=0.0,
        expert_consensus_boost=EXPERT_CONSENSUS_CAP,
    )

    assert final_with_excessive == final_with_capped, (
        f"expert_consensus_boost not capped: excessive={final_with_excessive}, capped={final_with_capped}"
    )

    # Verify boost can't be negative
    final_with_negative, _ = compute_final_score_option_a(
        base_score=7.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=0.0,
        expert_consensus_boost=-0.5,  # Negative should be clamped to 0
    )

    final_with_zero, _ = compute_final_score_option_a(
        base_score=7.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=0.0,
        expert_consensus_boost=0.0,
    )

    assert final_with_negative == final_with_zero, (
        "expert_consensus_boost must be >=0, negative values should be clamped to 0"
    )


def test_v20_3_prop_correlation_cap_enforcement() -> None:
    """
    Guard: prop_correlation_adjustment must be capped to [-PROP_CORRELATION_CAP, PROP_CORRELATION_CAP].
    """
    from core.scoring_pipeline import compute_final_score_option_a
    from core.scoring_contract import PROP_CORRELATION_CAP

    # Test excessive positive is capped
    final_with_excessive_pos, _ = compute_final_score_option_a(
        base_score=7.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=0.0,
        prop_correlation_adjustment=1.0,  # Excessive, should be capped to 0.20
    )

    final_with_capped_pos, _ = compute_final_score_option_a(
        base_score=7.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=0.0,
        prop_correlation_adjustment=PROP_CORRELATION_CAP,
    )

    assert final_with_excessive_pos == final_with_capped_pos, (
        f"prop_correlation_adjustment positive not capped: excessive={final_with_excessive_pos}, capped={final_with_capped_pos}"
    )

    # Test excessive negative is capped
    final_with_excessive_neg, _ = compute_final_score_option_a(
        base_score=7.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=0.0,
        prop_correlation_adjustment=-1.0,  # Excessive, should be capped to -0.20
    )

    final_with_capped_neg, _ = compute_final_score_option_a(
        base_score=7.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=0.0,
        prop_correlation_adjustment=-PROP_CORRELATION_CAP,
    )

    assert final_with_excessive_neg == final_with_capped_neg, (
        f"prop_correlation_adjustment negative not capped: excessive={final_with_excessive_neg}, capped={final_with_capped_neg}"
    )


def test_v20_3_no_research_score_mutation_in_router() -> None:
    """
    HARD GUARD: v20.3 signals must NOT mutate research_score.

    Hook Discipline, Expert Consensus, and Prop Correlation must be
    post-base additive signals, not engine mutations.
    """
    path = os.path.join(REPO_ROOT, "live_data_router.py")
    text = _read(path)

    # These patterns would indicate research_score mutation (FORBIDDEN)
    forbidden_patterns = [
        r'research_score\s*=\s*research_score\s*[-+]',  # research_score = research_score +/- X
        r'research_score\s*[-+]=',  # research_score += X or research_score -= X
    ]

    for pattern in forbidden_patterns:
        matches = re.findall(pattern, text)
        # Filter out lines that are in the expected places (before base_score computation)
        # by checking context - these mutations should not exist after base_score is computed
        assert len(matches) == 0, (
            f"CRITICAL: Found research_score mutation pattern: {pattern}\n"
            f"Matches: {matches}\n"
            "v20.3 signals must be post-base additive, not engine mutations!"
        )
