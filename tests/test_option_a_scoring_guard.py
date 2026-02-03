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
    """SERP boost must be capped and final_score clamped to [0, 10]."""
    from core.scoring_pipeline import compute_final_score_option_a
    from core.scoring_contract import SERP_BOOST_CAP_TOTAL

    # SERP cap
    final_score, _ = compute_final_score_option_a(
        base_score=1.0,
        context_modifier=0.0,
        confluence_boost=0.0,
        msrf_boost=0.0,
        jason_sim_boost=0.0,
        serp_boost=10.0,
    )
    assert final_score == 1.0 + SERP_BOOST_CAP_TOTAL

    # Final clamp
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
