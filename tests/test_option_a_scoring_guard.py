"""
Hard guardrails to prevent regression from Option A:

Option A:
- BASE_4 weighted engines only: ai, research, esoteric, jarvis
- Context is NOT an engine weight
- Context is a bounded modifier via CONTEXT_MODIFIER_CAP
- FINAL = base_score + context_modifier + confluence_boost + jason_sim_boost

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

        # Extra strict: ensure there is at least one line that looks like the Option A final addition.
        assert re.search(
            r"final_score\s*=\s*base_score\s*\+\s*context_modifier\s*\+\s*confluence_boost\s*\+\s*jason_sim_boost",
            text,
        ), f"{os.path.relpath(path, REPO_ROOT)} does not contain the Option A final_score formula"
