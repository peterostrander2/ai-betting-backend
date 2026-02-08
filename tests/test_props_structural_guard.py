"""
Structural regression tests for Lesson 54: Props Indentation Bug.

Prevents the bug where `if _props_deadline_hit: break` was placed at
the wrong indentation level (12 spaces) between calculate_pick_score()
and props_picks.append(), making all prop processing dead code.

These tests do NOT execute the code — they pattern-match on the source
to enforce structural invariants.
"""

from __future__ import annotations

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROUTER_PATH = os.path.join(REPO_ROOT, "live_data_router.py")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _find_prop_score_call(lines: list[str]) -> int:
    """Find the calculate_pick_score() call for PROP picks (multiline aware).

    The call spans multiple lines, e.g.:
        score_data = calculate_pick_score(   # line N
            ...
            pick_type="PROP",                # line N+k
            ...
        )
    Returns the line index of 'calculate_pick_score(' that has 'pick_type="PROP"'
    within the next 25 lines.
    """
    for i, line in enumerate(lines):
        if "calculate_pick_score(" in line:
            # Look ahead for pick_type="PROP" within the call
            for j in range(i, min(i + 25, len(lines))):
                if 'pick_type="PROP"' in lines[j]:
                    return i
    return -1


def test_props_picks_append_reachable() -> None:
    """
    props_picks.append() must appear AFTER calculate_pick_score() in the
    props scoring section and must be at 16-space indentation (inside the
    inner loop), not at 12-space indentation (game loop level).
    """
    src = _read(ROUTER_PATH)
    lines = src.splitlines()

    prop_score_idx = _find_prop_score_call(lines)
    assert prop_score_idx >= 0, (
        "Could not find calculate_pick_score() call with pick_type=\"PROP\" "
        "in live_data_router.py"
    )

    # Find props_picks.append(
    append_lines = [
        i for i, line in enumerate(lines)
        if "props_picks.append(" in line
    ]
    assert append_lines, (
        "Could not find props_picks.append() in live_data_router.py"
    )

    # The append must come AFTER the prop score calculation
    first_append = min(append_lines)
    assert first_append > prop_score_idx, (
        f"props_picks.append() (line {first_append + 1}) must appear AFTER "
        f"calculate_pick_score(PROP) (line {prop_score_idx + 1})"
    )

    # The append line must be at 16-space indentation (inner loop level)
    for al in append_lines:
        indent = len(lines[al]) - len(lines[al].lstrip())
        assert indent == 16, (
            f"props_picks.append() at line {al + 1} has {indent}-space indent; "
            f"expected 16 spaces (inner loop level). "
            f"If at 12 spaces, it may be inside a deadline guard and unreachable."
        )


def test_deadline_break_after_append() -> None:
    """
    The _props_deadline_hit break that is at 12-space indent (game loop level)
    and appears AFTER the inner props loop must come AFTER props_picks.append().

    Note: There are TWO legitimate deadline breaks:
    1. At the start of the game loop (before scoring) - this is OK
    2. At the start of the inner prop loop (before scoring) - this is OK
    The invariant is: no deadline break between calculate_pick_score() and
    props_picks.append().
    """
    src = _read(ROUTER_PATH)
    lines = src.splitlines()

    prop_score_idx = _find_prop_score_call(lines)
    assert prop_score_idx >= 0, "Could not find prop calculate_pick_score()"

    append_lines = [
        i for i, line in enumerate(lines)
        if "props_picks.append(" in line
    ]
    assert append_lines, "Could not find props_picks.append()"
    last_append = max(append_lines)

    # Find _props_deadline_hit references that are BETWEEN score and append
    # These are the dangerous ones (Lesson 54 bug pattern)
    for i in range(prop_score_idx, last_append):
        stripped = lines[i].strip()
        if "_props_deadline_hit" in stripped:
            assert False, (
                f"_props_deadline_hit at line {i + 1} is between "
                f"calculate_pick_score() (line {prop_score_idx + 1}) and "
                f"props_picks.append() (line {last_append + 1}). "
                f"This makes prop processing dead code (Lesson 54)."
            )


def test_props_loop_structure_invariant() -> None:
    """
    Verify the structural ordering in the props scoring loop:
    score -> process -> append -> deadline check

    NOT: score -> deadline -> process -> append (which would make
    process+append unreachable).
    """
    src = _read(ROUTER_PATH)
    lines = src.splitlines()

    prop_score_idx = _find_prop_score_call(lines)
    assert prop_score_idx >= 0, "Could not find prop calculate_pick_score()"

    # Find props_picks.append after the score call
    append_idx = None
    for i in range(prop_score_idx, len(lines)):
        if "props_picks.append(" in lines[i]:
            append_idx = i
            break
    assert append_idx is not None, (
        "Could not find props_picks.append() after calculate_pick_score(PROP)"
    )

    # Between score and append, there must NOT be a _props_deadline_hit reference
    for i in range(prop_score_idx, append_idx):
        if "_props_deadline_hit" in lines[i]:
            assert False, (
                f"Found _props_deadline_hit at line {i + 1}, which is between "
                f"calculate_pick_score() (line {prop_score_idx + 1}) and "
                f"props_picks.append() (line {append_idx + 1}). "
                f"This breaks the score->process->append->deadline invariant "
                f"(Lesson 54 regression)."
            )
