#!/usr/bin/env python3
"""
v17.7 Apply Changes Script
==========================

This script applies the Hurst Exponent & Fibonacci Retracement wiring
to live_data_router.py.

Usage:
    python v17.7_apply_changes.py [--dry-run]

Options:
    --dry-run    Show changes without applying them
"""

import re
import sys
import shutil
from pathlib import Path
from datetime import datetime


# =============================================================================
# CHANGE DEFINITIONS
# =============================================================================

IMPORTS_TO_ADD = [
    ("from database import", "get_line_history_values"),
    ("from database import", "get_season_extreme"),
    ("from database import", "DB_ENABLED"),
    ("from esoteric_engine import", "calculate_fibonacci_retracement"),
]

HURST_FETCH_CODE = '''
            # ===== v17.7: HURST EXPONENT DATA =====
            _line_history = None
            try:
                _event_id = candidate.get("id") if isinstance(candidate, dict) else None
                if _event_id and DB_ENABLED:
                    with get_db() as db:
                        if db:
                            _line_history = get_line_history_values(
                                db,
                                event_id=_event_id,
                                value_type="spread",  # Use spread for game picks, could use "total"
                                limit=30
                            )
            except Exception as e:
                logger.debug("Line history fetch skipped: %s", e)

'''

FIBONACCI_RETRACEMENT_CODE = '''
            # ===== v17.7: FIBONACCI RETRACEMENT (Season Extremes) =====
            try:
                if DB_ENABLED and _is_game_pick:
                    # Determine current season (Sept-Aug)
                    _now = datetime.now()
                    _season = f"{_now.year}-{str(_now.year+1)[-2:]}" if _now.month >= 9 else f"{_now.year-1}-{str(_now.year)[-2:]}"

                    # Get primary line value
                    _fib_line = abs(spread) if spread else total if total else None
                    _fib_stat = "spread" if spread else "total"

                    if _fib_line:
                        with get_db() as db:
                            if db:
                                extremes = get_season_extreme(db, sport, _season, _fib_stat)

                                if extremes and extremes.get("season_high") and extremes.get("season_low"):
                                    fib_result = calculate_fibonacci_retracement(
                                        current_line=_fib_line,
                                        season_high=extremes["season_high"],
                                        season_low=extremes["season_low"]
                                    )

                                    if fib_result.get("near_fib_level"):
                                        _fib_boost = 0.35 if fib_result["signal"] == "REVERSAL_ZONE" else 0.2
                                        esoteric_raw += _fib_boost
                                        esoteric_reasons.append(
                                            f"Fib Retracement: {fib_result['closest_fib_level']}% ({fib_result['signal']})"
                                        )
            except Exception as e:
                logger.debug("Fibonacci retracement skipped: %s", e)

'''


def find_file():
    """Find live_data_router.py in common locations."""
    locations = [
        Path("live_data_router.py"),
        Path("src/live_data_router.py"),
        Path("app/live_data_router.py"),
        Path("../live_data_router.py"),
    ]
    for loc in locations:
        if loc.exists():
            return loc
    return None


def backup_file(filepath):
    """Create a backup of the file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = filepath.with_suffix(f".py.backup_{timestamp}")
    shutil.copy2(filepath, backup_path)
    return backup_path


def add_imports(content):
    """Add missing imports to the file."""
    changes = []

    # Check and add database imports
    if "from database import" in content:
        # Find existing database import line
        match = re.search(r'(from database import [^\n]+)', content)
        if match:
            existing = match.group(1)
            new_imports = []

            if "get_line_history_values" not in existing:
                new_imports.append("get_line_history_values")
            if "get_season_extreme" not in existing:
                new_imports.append("get_season_extreme")
            if "DB_ENABLED" not in existing:
                new_imports.append("DB_ENABLED")
            if "get_db" not in existing:
                new_imports.append("get_db")

            if new_imports:
                # Append to existing import
                new_line = existing.rstrip() + ", " + ", ".join(new_imports)
                content = content.replace(existing, new_line)
                changes.append(f"Added to database imports: {', '.join(new_imports)}")
    else:
        # Add new database import line
        import_line = "from database import get_db, get_line_history_values, get_season_extreme, DB_ENABLED\n"
        # Add after other imports
        if "import " in content:
            lines = content.split('\n')
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    insert_idx = i + 1
            lines.insert(insert_idx, import_line.rstrip())
            content = '\n'.join(lines)
            changes.append("Added database import line")

    # Check and add esoteric_engine import
    if "calculate_fibonacci_retracement" not in content:
        if "from esoteric_engine import" in content:
            match = re.search(r'(from esoteric_engine import [^\n]+)', content)
            if match:
                existing = match.group(1)
                new_line = existing.rstrip() + ", calculate_fibonacci_retracement"
                content = content.replace(existing, new_line)
                changes.append("Added calculate_fibonacci_retracement to esoteric_engine imports")
        else:
            import_line = "from esoteric_engine import calculate_fibonacci_retracement\n"
            if "import " in content:
                lines = content.split('\n')
                insert_idx = 0
                for i, line in enumerate(lines):
                    if line.startswith('import ') or line.startswith('from '):
                        insert_idx = i + 1
                lines.insert(insert_idx, import_line.rstrip())
                content = '\n'.join(lines)
                changes.append("Added esoteric_engine import line")

    return content, changes


def add_hurst_fetch(content):
    """Add Hurst line history fetch before GLITCH call."""
    changes = []

    if "_line_history = None" in content:
        changes.append("Hurst fetch already present (skipped)")
        return content, changes

    # Find the GLITCH call with line_history=None
    pattern = r'(\s+)(glitch_result\s*=\s*get_glitch_aggregate\([^)]*line_history\s*=\s*None)'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        indent = match.group(1)
        # Insert before the GLITCH call
        insert_pos = match.start()
        hurst_code = HURST_FETCH_CODE.replace('\n            ', '\n' + indent)
        content = content[:insert_pos] + hurst_code + content[insert_pos:]
        changes.append("Added Hurst line history fetch before GLITCH call")
    else:
        changes.append("WARNING: Could not find GLITCH call pattern to insert Hurst fetch")

    return content, changes


def update_glitch_call(content):
    """Update GLITCH call to use _line_history instead of None."""
    changes = []

    if "line_history=_line_history" in content:
        changes.append("GLITCH call already updated (skipped)")
        return content, changes

    if "line_history=None" in content:
        content = content.replace(
            "line_history=None",
            "line_history=_line_history,  # v17.7: Wire to line_snapshots data"
        )
        changes.append("Updated GLITCH call: line_history=None -> line_history=_line_history")
    else:
        changes.append("WARNING: Could not find line_history=None in GLITCH call")

    return content, changes


def add_fibonacci_retracement(content):
    """Add Fibonacci Retracement section."""
    changes = []

    if "v17.7: FIBONACCI RETRACEMENT" in content:
        changes.append("Fibonacci retracement already present (skipped)")
        return content, changes

    # Find existing Fibonacci alignment section (Jarvis) to insert after
    patterns = [
        r'(# ===== FIBONACCI.*?esoteric_reasons\.append.*?\))',
        r'(jarvis\.calculate_fibonacci_alignment.*?esoteric_reasons\.append.*?\))',
        r'(calculate_fibonacci_alignment.*?esoteric_reasons\.append.*?\))',
    ]

    inserted = False
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            insert_pos = match.end()
            # Preserve indentation
            content = content[:insert_pos] + '\n' + FIBONACCI_RETRACEMENT_CODE + content[insert_pos:]
            changes.append("Added Fibonacci retracement section after existing Fibonacci alignment")
            inserted = True
            break

    if not inserted:
        # Try to find a good location - after esoteric_raw calculations
        match = re.search(r'(esoteric_raw\s*\+=.*?\n)', content)
        if match:
            insert_pos = match.end()
            content = content[:insert_pos] + '\n' + FIBONACCI_RETRACEMENT_CODE + content[insert_pos:]
            changes.append("Added Fibonacci retracement section (after esoteric_raw)")
        else:
            changes.append("WARNING: Could not find suitable location for Fibonacci retracement")

    return content, changes


def apply_changes(dry_run=False):
    """Apply all v17.7 changes to live_data_router.py."""
    print("=" * 60)
    print("v17.7 Apply Changes: Hurst Exponent & Fibonacci Retracement")
    print("=" * 60)

    # Find file
    filepath = find_file()
    if not filepath:
        print("\nERROR: Could not find live_data_router.py")
        print("Please run this script from the directory containing the file.")
        sys.exit(1)

    print(f"\nFound: {filepath}")

    # Read content
    content = filepath.read_text()
    original_content = content
    all_changes = []

    # Apply changes
    print("\n1. Adding imports...")
    content, changes = add_imports(content)
    all_changes.extend(changes)
    for c in changes:
        print(f"   {c}")

    print("\n2. Adding Hurst line history fetch...")
    content, changes = add_hurst_fetch(content)
    all_changes.extend(changes)
    for c in changes:
        print(f"   {c}")

    print("\n3. Updating GLITCH call...")
    content, changes = update_glitch_call(content)
    all_changes.extend(changes)
    for c in changes:
        print(f"   {c}")

    print("\n4. Adding Fibonacci retracement...")
    content, changes = add_fibonacci_retracement(content)
    all_changes.extend(changes)
    for c in changes:
        print(f"   {c}")

    # Summary
    print("\n" + "=" * 60)
    if dry_run:
        print("DRY RUN - No changes written")
        print("=" * 60)
        print(f"\nWould apply {len(all_changes)} changes to {filepath}")
    else:
        if content != original_content:
            # Backup
            backup_path = backup_file(filepath)
            print(f"Backup created: {backup_path}")

            # Write
            filepath.write_text(content)
            print(f"Changes written to: {filepath}")
            print("=" * 60)
            print(f"\nApplied {len(all_changes)} changes")

            # Verify syntax
            print("\nVerifying syntax...")
            import subprocess
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(filepath)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("✓ Syntax OK")
            else:
                print(f"✗ Syntax error: {result.stderr}")
                print("Restoring backup...")
                shutil.copy2(backup_path, filepath)
                print("Backup restored. Please check the changes manually.")
                sys.exit(1)
        else:
            print("No changes needed - all modifications already present")
            print("=" * 60)

    return all_changes


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    apply_changes(dry_run=dry_run)
