"""
v17.7 Implementation: Wire Hurst Exponent & Fibonacci Retracement
=================================================================

This file contains the code snippets to add to live_data_router.py

Apply these changes in the following order:
1. Add imports at top of file
2. Add Hurst line history fetch before GLITCH call (~line 3340)
3. Update GLITCH call parameter (~line 3347)
4. Add Fibonacci Retracement section (~line 3590)
"""

# =============================================================================
# IMPORTS TO ADD (at top of live_data_router.py)
# =============================================================================

# Add these imports to the existing import section:
# (If database imports already exist, just add the missing functions)

"""
from database import get_db, get_line_history_values, get_season_extreme, DB_ENABLED
from esoteric_engine import calculate_fibonacci_retracement
"""


# =============================================================================
# HURST EXPONENT: Line History Fetch (~line 3340)
# =============================================================================
# Insert this code BEFORE the get_glitch_aggregate() call
# Inside calculate_pick_score() function

HURST_LINE_HISTORY_FETCH = '''
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


# =============================================================================
# HURST EXPONENT: Update GLITCH Call (~line 3347)
# =============================================================================
# Change the line_history parameter from None to _line_history

GLITCH_CALL_BEFORE = '''
            glitch_result = get_glitch_aggregate(
                birth_date_str=_player_birth,
                game_date=_game_date_obj,
                game_time=game_datetime,
                line_history=None,
                value_for_benford=_line_values if len(_line_values) >= 10 else None,
                primary_value=prop_line if prop_line else spread
            )
'''

GLITCH_CALL_AFTER = '''
            glitch_result = get_glitch_aggregate(
                birth_date_str=_player_birth,
                game_date=_game_date_obj,
                game_time=game_datetime,
                line_history=_line_history,  # v17.7: Wire to line_snapshots data
                value_for_benford=_line_values if len(_line_values) >= 10 else None,
                primary_value=prop_line if prop_line else spread
            )
'''


# =============================================================================
# FIBONACCI RETRACEMENT: Season Extremes Section (~line 3590)
# =============================================================================
# Insert AFTER the existing Fibonacci alignment (Jarvis) section

FIBONACCI_RETRACEMENT_SECTION = '''
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


# =============================================================================
# VERIFICATION SCRIPT
# =============================================================================

def verify_implementation():
    """Run basic verification checks after implementation."""
    import subprocess
    import sys

    print("=" * 60)
    print("v17.7 Implementation Verification")
    print("=" * 60)

    # 1. Syntax check
    print("\n1. Syntax check...")
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", "live_data_router.py"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("   ✓ Syntax OK")
    else:
        print(f"   ✗ Syntax error: {result.stderr}")
        return False

    # 2. Check imports exist
    print("\n2. Checking imports...")
    with open("live_data_router.py", "r") as f:
        content = f.read()

    imports_ok = True
    for imp in ["get_line_history_values", "get_season_extreme", "calculate_fibonacci_retracement"]:
        if imp in content:
            print(f"   ✓ {imp} imported")
        else:
            print(f"   ✗ {imp} NOT found")
            imports_ok = False

    # 3. Check Hurst wiring
    print("\n3. Checking Hurst wiring...")
    if "_line_history = None" in content and "line_history=_line_history" in content:
        print("   ✓ Hurst line history wired")
    else:
        print("   ✗ Hurst line history NOT wired")

    # 4. Check Fibonacci retracement
    print("\n4. Checking Fibonacci retracement...")
    if "Fib Retracement:" in content and "calculate_fibonacci_retracement" in content:
        print("   ✓ Fibonacci retracement wired")
    else:
        print("   ✗ Fibonacci retracement NOT wired")

    print("\n" + "=" * 60)
    print("Verification complete!")
    print("=" * 60)

    return True


if __name__ == "__main__":
    verify_implementation()
