"""
v17.8 Implementation: Officials Tendency Integration (Pillar 16)
================================================================

This file contains the code snippets to add to context_layer.py and live_data_router.py

Apply these changes in the following order:
1. Add officials_data.py to the project (already created)
2. Update OfficialsService in context_layer.py
3. Wire officials adjustment in live_data_router.py
"""

# =============================================================================
# CONTEXT_LAYER.PY CHANGES
# =============================================================================

# Add import at top of context_layer.py:
CONTEXT_LAYER_IMPORT = '''
from officials_data import get_referee_tendency, calculate_officials_adjustment
'''

# Replace the OfficialsService class (around lines 1527-1620):
OFFICIALS_SERVICE_CLASS = '''
class OfficialsService:
    """
    Pillar 16: Officials Analysis

    Adjusts scores based on referee tendencies.
    Data source: ESPN officials API + officials_data.py tendency database.

    v17.8: Now uses real referee tendency data.
    """

    @staticmethod
    def get_officials_adjustment(
        sport: str,
        officials: dict,
        pick_type: str,
        pick_side: str,
        is_home_team: bool = False
    ) -> tuple:
        """
        Calculate scoring adjustment based on referee tendencies.

        Args:
            sport: NBA, NFL, NHL (NCAAB/MLB not supported)
            officials: Dict with lead_official, official_2, etc. from ESPN
            pick_type: TOTAL, SPREAD, MONEYLINE, PROP
            pick_side: Over, Under, or team name
            is_home_team: True if pick is on home team

        Returns:
            (adjustment: float, reasons: List[str])
        """
        adjustment = 0.0
        reasons = []

        # Only NBA, NFL, NHL have referee data
        if sport.upper() not in ("NBA", "NFL", "NHL"):
            return adjustment, reasons

        if not officials:
            return adjustment, reasons

        # Get lead official (most influential)
        lead_ref = (
            officials.get("lead_official") or
            officials.get("referee") or
            officials.get("Referee") or
            officials.get("officials", [{}])[0].get("displayName") if isinstance(officials.get("officials"), list) else None
        )

        if not lead_ref:
            return adjustment, reasons

        # Calculate adjustment using officials_data module
        adj, reason = calculate_officials_adjustment(
            sport=sport,
            referee_name=lead_ref,
            pick_type=pick_type,
            pick_side=pick_side,
            is_home_team=is_home_team
        )

        if adj != 0 and reason:
            adjustment = adj
            reasons.append(reason)

        return adjustment, reasons

    @staticmethod
    def get_referee_info(sport: str, referee_name: str) -> dict:
        """Get detailed info about a specific referee."""
        tendency = get_referee_tendency(sport, referee_name)
        if not tendency:
            return {"found": False, "name": referee_name, "sport": sport}

        return {
            "found": True,
            "name": referee_name,
            "sport": sport,
            "over_tendency": tendency.get("over_tendency"),
            "home_bias": tendency.get("home_bias"),
            "total_games": tendency.get("total_games"),
            "notes": tendency.get("notes"),
        }
'''


# =============================================================================
# LIVE_DATA_ROUTER.PY CHANGES
# =============================================================================

# Add import at top of live_data_router.py (combine with existing context_layer imports):
LIVE_DATA_ROUTER_IMPORT = '''
from context_layer import OfficialsService
'''

# Update the officials section in calculate_pick_score() (~line 3720-3770):
OFFICIALS_SCORING_SECTION = '''
            # ===== PILLAR 16: OFFICIALS (v17.8) =====
            _officials_adjustment = 0.0
            _officials_reasons = []
            try:
                # Check if we have officials data for this game
                if _officials_by_game and home_team and away_team:
                    _home_lower = home_team.lower().strip()
                    _away_lower = away_team.lower().strip()

                    # Try different key formats (ESPN may return various formats)
                    _game_officials = (
                        _officials_by_game.get((_home_lower, _away_lower)) or
                        _officials_by_game.get((_away_lower, _home_lower)) or
                        _officials_by_game.get((home_team, away_team))
                    )

                    if _game_officials:
                        # Determine if pick is on home team
                        _pick_is_home = False
                        if pick_side:
                            _pick_side_lower = pick_side.lower().strip()
                            _pick_is_home = (
                                _pick_side_lower == _home_lower or
                                _pick_side_lower in home_team.lower()
                            )

                        _officials_adjustment, _officials_reasons = OfficialsService.get_officials_adjustment(
                            sport=sport,
                            officials=_game_officials,
                            pick_type=pick_type,
                            pick_side=pick_side,
                            is_home_team=_pick_is_home
                        )

                        if _officials_adjustment != 0:
                            logger.debug(
                                "Officials adjustment: %.2f for %s vs %s (%s)",
                                _officials_adjustment, home_team, away_team, _officials_reasons
                            )
            except Exception as e:
                logger.debug("Officials adjustment skipped: %s", e)

            # Apply officials adjustment to research score
            if _officials_adjustment != 0:
                research_raw += _officials_adjustment
                research_reasons.extend(_officials_reasons)
'''

# Add officials data to pick output (in the return dict):
OFFICIALS_OUTPUT_FIELDS = '''
            # Add to the pick result dict:
            "officials_adjustment": _officials_adjustment,
            "officials_reasons": _officials_reasons,
            "officials_data": _game_officials if _game_officials else None,
'''


# =============================================================================
# VERIFICATION SCRIPT
# =============================================================================

def verify_officials_integration():
    """Run verification checks after implementation."""
    import subprocess
    import sys

    print("=" * 60)
    print("v17.8 Officials Integration Verification")
    print("=" * 60)

    # 1. Test officials_data module
    print("\n1. Testing officials_data module...")
    try:
        from officials_data import (
            get_referee_tendency,
            calculate_officials_adjustment,
            get_database_stats
        )

        # Test lookups
        foster = get_referee_tendency("NBA", "Scott Foster")
        assert foster is not None, "Scott Foster not found"
        assert foster["over_tendency"] == 0.54, "Scott Foster over_tendency wrong"
        print("   ✓ Referee lookups working")

        # Test adjustment calculation
        adj, reason = calculate_officials_adjustment("NBA", "Scott Foster", "TOTAL", "Over")
        assert adj > 0, "Should have positive adjustment for Over with Scott Foster"
        assert "54%" in reason, "Reason should mention 54%"
        print("   ✓ Adjustment calculations working")

        # Test stats
        stats = get_database_stats()
        assert stats["NBA"]["count"] >= 25, "Should have 25+ NBA refs"
        assert stats["NFL"]["count"] >= 15, "Should have 15+ NFL refs"
        assert stats["NHL"]["count"] >= 15, "Should have 15+ NHL refs"
        print(f"   ✓ Database stats: NBA={stats['NBA']['count']}, NFL={stats['NFL']['count']}, NHL={stats['NHL']['count']}")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # 2. Syntax check
    print("\n2. Syntax check...")
    files_to_check = ["officials_data.py"]
    for f in files_to_check:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", f],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"   ✓ {f} syntax OK")
        else:
            print(f"   ✗ {f} syntax error: {result.stderr}")
            return False

    print("\n" + "=" * 60)
    print("Verification complete!")
    print("=" * 60)

    print("\nNext steps:")
    print("1. Add import to context_layer.py")
    print("2. Replace OfficialsService class in context_layer.py")
    print("3. Update officials section in live_data_router.py")
    print("4. Add officials output fields to pick result dict")
    print("5. Deploy and verify with curl commands")

    return True


if __name__ == "__main__":
    verify_officials_integration()
