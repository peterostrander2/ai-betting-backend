"""Test that scheduler exports are available."""
import pytest
import importlib.util


def test_get_daily_scheduler_export_exists():
    """
    Verify get_daily_scheduler is exported from daily_scheduler module.
    This is a static check that doesn't require full import (avoids dependency issues).
    """
    import ast

    with open("daily_scheduler.py", "r") as f:
        source = f.read()

    # Check that the alias assignment exists in the source
    assert "get_daily_scheduler = get_scheduler" in source, \
        "get_daily_scheduler alias must be defined in daily_scheduler.py"

    # Parse the module and check for the assignment
    tree = ast.parse(source)

    # Look for assignment: get_daily_scheduler = get_scheduler
    found_alias = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "get_daily_scheduler":
                    found_alias = True
                    break

    assert found_alias, "get_daily_scheduler assignment not found in AST"


def test_get_scheduler_function_exists():
    """Verify get_scheduler function is defined."""
    import ast

    with open("daily_scheduler.py", "r") as f:
        source = f.read()

    tree = ast.parse(source)

    # Look for function def: def get_scheduler(...)
    found_func = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "get_scheduler":
            found_func = True
            break

    assert found_func, "get_scheduler function not found"
