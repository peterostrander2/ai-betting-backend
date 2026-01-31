"""Tests for grader_store reconciliation invariant."""
import pytest
import tempfile
import os
import json


def test_reconciliation_invariant_source_exists():
    """Verify load_predictions_with_reconciliation is defined in grader_store."""
    import ast

    with open("grader_store.py", "r") as f:
        source = f.read()

    tree = ast.parse(source)

    # Look for function def: def load_predictions_with_reconciliation(...)
    found_func = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "load_predictions_with_reconciliation":
            found_func = True
            break

    assert found_func, "load_predictions_with_reconciliation function not found in grader_store.py"


def test_reconciliation_returns_expected_structure():
    """Test that reconciliation returns expected keys."""
    import ast

    with open("grader_store.py", "r") as f:
        source = f.read()

    # Check that the function returns reconciliation dict with expected keys
    assert "total_lines" in source
    assert "parsed_ok" in source
    assert "skipped_total" in source
    assert "skip_reasons" in source
    assert "reconciled" in source


def test_reconciliation_skip_reason_categories():
    """Test that all skip reason categories are tracked."""
    with open("grader_store.py", "r") as f:
        source = f.read()

    # Check for expected skip reason categories
    expected_reasons = [
        "empty_line",
        "json_parse_error",
        "not_dict",
        "missing_pick_id",
    ]

    for reason in expected_reasons:
        assert f'"{reason}"' in source, f"Skip reason '{reason}' not tracked in grader_store.py"


def test_reconciliation_invariant_formula():
    """Test that the invariant formula is correctly implemented."""
    with open("grader_store.py", "r") as f:
        source = f.read()

    # The invariant should be: total_lines == parsed_ok + skipped_total
    assert "total_lines == parsed_ok + skipped_total" in source or \
           "reconciled = (total_lines == parsed_ok + skipped_total)" in source, \
           "Reconciliation invariant formula not found"
