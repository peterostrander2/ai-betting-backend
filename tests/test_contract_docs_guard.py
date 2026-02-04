"""
Guard tests for scoring contract docs and sanity scripts.
"""
from __future__ import annotations

import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CLAUDE_MD = os.path.join(REPO_ROOT, "CLAUDE.md")
SCORING_LOGIC_MD = os.path.join(REPO_ROOT, "SCORING_LOGIC.md")
ENDPOINT_CONTRACT_MD = os.path.join(REPO_ROOT, "docs", "ENDPOINT_CONTRACT.md")
ENDPOINT_MATRIX = os.path.join(REPO_ROOT, "scripts", "endpoint_matrix_sanity.sh")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_docs_include_option_a_formula_and_caps() -> None:
    text = _read(CLAUDE_MD) + "\n" + _read(SCORING_LOGIC_MD)

    # Must include base_4 formula and context cap
    assert "BASE_4" in text
    assert "context_modifier" in text
    assert "0.35" in text

    # Must include ensemble adjustment mention
    assert "ensemble_adjustment" in text


def test_endpoint_contract_lists_required_fields() -> None:
    text = _read(ENDPOINT_CONTRACT_MD)
    for field in [
        "base_4_score",
        "context_modifier",
        "confluence_boost",
        "msrf_boost",
        "jason_sim_boost",
        "serp_boost",
        "ensemble_adjustment",
        "final_score",
    ]:
        assert field in text, f"Missing required field in ENDPOINT_CONTRACT.md: {field}"


def test_endpoint_matrix_math_includes_ensemble_adjustment() -> None:
    text = _read(ENDPOINT_MATRIX)
    # Require ensemble_adjustment in the math sum check
    assert "ensemble_adjustment" in text
    # Ensure math uses explicit additive terms
    assert "base_4_score" in text and "context_modifier" in text
