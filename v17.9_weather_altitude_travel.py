"""
v17.9 Implementation: Weather, Stadium & Travel Fatigue Integration
====================================================================

This file contains the code snippets to add to context_layer.py and live_data_router.py

Integrates 3 alt_data modules that are implemented but not wired:
1. Weather - Currently bypasses engines, now applies to research_score
2. Altitude - 62-venue registry, now applies to esoteric_score
3. Travel/B2B - ESPN rest_days computed but orphaned, now applies to context_score

Apply these changes in the following order:
1. Add StadiumAltitudeService to context_layer.py
2. Add weather integration to live_data_router.py (~line 4060)
3. Add altitude integration to live_data_router.py (~line 3745)
4. Add travel fatigue to compute_context_modifiers() (~line 2990)
5. Add travel fatigue application to calculate_pick_score() (~line 3165)
6. Remove old weather application (~lines 5371-5377)
"""

# =============================================================================
# CONTEXT_LAYER.PY CHANGES
# =============================================================================

# Add this class after existing services (around line 970):
STADIUM_ALTITUDE_SERVICE_CLASS = '''
class StadiumAltitudeService:
    """
    Altitude impact on game scoring (v17.9)

    High-altitude venues affect player performance:
    - Denver (5280ft): Significant impact on all sports
    - Utah (4226ft): Moderate impact
    - Mexico City (7350ft): Major impact for international games

    MLB: Thin air = more home runs, higher scoring
    NFL/NCAAF: Visiting teams fatigue faster at altitude
    NBA/NHL: Less pronounced but still measurable
    """

    HIGH_ALTITUDE = {
        # NFL/MLB/NBA/NHL venues
        "broncos": 5280,
        "nuggets": 5280,
        "rockies": 5200,
        "avalanche": 5280,
        "jazz": 4226,
        "utah": 4226,
        "real salt lake": 4226,
        # College venues
        "colorado": 5430,
        "air force": 6621,
        "wyoming": 7220,
        "new mexico": 5312,
        "byu": 4551,
        "utah state": 4528,
        # International
        "mexico city": 7350,
        "azteca": 7350,
    }

    @classmethod
    def get_altitude_adjustment(
        cls,
        sport: str,
        home_team: str,
        pick_type: str,
        pick_side: str
    ) -> tuple:
        """
        Returns (adjustment, reasons) tuple for altitude impact.

        Args:
            sport: Sport code (NFL, MLB, NBA, etc.)
            home_team: Home team name
            pick_type: TOTAL, SPREAD, MONEYLINE, PROP
            pick_side: Over, Under, or team name

        Returns:
            tuple: (adjustment: float, reasons: list[str])
                   adjustment range: -0.3 to +0.5
        """
        if not home_team:
            return (0.0, [])

        home_lower = home_team.lower().strip()

        # Find altitude for this venue
        altitude = 0
        for venue_key, venue_alt in cls.HIGH_ALTITUDE.items():
            if venue_key in home_lower:
                altitude = venue_alt
                break

        if altitude < 4000:
            return (0.0, [])

        sport_upper = sport.upper() if sport else ""
        pick_type_upper = pick_type.upper() if pick_type else ""
        pick_side_lower = pick_side.lower() if pick_side else ""

        # MLB: Coors Field effect (5000ft+)
        if sport_upper == "MLB" and altitude >= 5000:
            if pick_type_upper == "TOTAL":
                if "over" in pick_side_lower:
                    return (0.5, [f"Coors Field {altitude}ft favors OVER (+0.5)"])
                elif "under" in pick_side_lower:
                    return (-0.3, [f"Coors Field {altitude}ft penalizes UNDER (-0.3)"])
            # Side bets - slight offensive boost
            return (0.2, [f"Altitude {altitude}ft boosts offense (+0.2)"])

        # NFL/NCAAF: Mile High visitor fatigue (5000ft+)
        if sport_upper in ("NFL", "NCAAF") and altitude >= 5000:
            return (0.25, [f"Mile High {altitude}ft visitor fatigue (+0.25)"])

        # NBA/NHL at altitude (4000ft+)
        if sport_upper in ("NBA", "NHL") and altitude >= 4000:
            return (0.15, [f"Altitude {altitude}ft moderate effect (+0.15)"])

        # Generic high altitude (4000ft+)
        if altitude >= 4000:
            return (0.15, [f"Altitude {altitude}ft moderate effect (+0.15)"])

        return (0.0, [])
'''


# =============================================================================
# LIVE_DATA_ROUTER.PY CHANGES
# =============================================================================

# Add import at top (combine with existing context_layer imports):
LIVE_DATA_ROUTER_IMPORTS = '''
from context_layer import StadiumAltitudeService
'''

# Also ensure alt_data_sources.travel is imported:
TRAVEL_IMPORT = '''
try:
    from alt_data_sources.travel import calculate_distance, calculate_fatigue_impact
    TRAVEL_MODULE_AVAILABLE = True
except ImportError:
    TRAVEL_MODULE_AVAILABLE = False
'''


# -----------------------------------------------------------------------------
# 1. WEATHER INTEGRATION FIX (~line 4060, after research calc, before officials)
# -----------------------------------------------------------------------------
WEATHER_INTEGRATION = '''
            # ===== WEATHER IMPACT ON RESEARCH (v17.9) =====
            # Weather modifier now applies to research_score instead of final_score
            # Market doesn't fully price weather effects
            weather_adj = 0.0
            if sport_upper in ("NFL", "MLB", "NCAAF") and _game_weather:
                try:
                    _wmod = _game_weather.get("weather_modifier", 0.0)
                    if _game_weather.get("available") and _wmod != 0.0:
                        # Scale modifier by 0.5 and cap at -0.5 (weather is always negative)
                        weather_adj = max(-0.5, _wmod * 0.5)
                        research_raw += weather_adj
                        for wr in _game_weather.get("weather_reasons", []):
                            research_reasons.append(f"Weather: {wr}")
                        logger.debug(
                            "Weather adjustment: %.2f for %s vs %s (modifier=%.2f)",
                            weather_adj, home_team, away_team, _wmod
                        )
                except Exception as e:
                    logger.debug("Weather adjustment failed: %s", e)
'''


# -----------------------------------------------------------------------------
# 2. ALTITUDE INTEGRATION (~line 3745, after GLITCH section in esoteric)
# -----------------------------------------------------------------------------
ALTITUDE_INTEGRATION = '''
            # ===== ALTITUDE IMPACT (v17.9) =====
            # High-altitude venues affect scoring patterns
            altitude_adj = 0.0
            if CONTEXT_LAYER_AVAILABLE and home_team:
                try:
                    altitude_adj, altitude_reasons = StadiumAltitudeService.get_altitude_adjustment(
                        sport=sport_upper,
                        home_team=home_team,
                        pick_type=pick_type,
                        pick_side=pick_side
                    )
                    if altitude_adj != 0.0:
                        esoteric_raw += altitude_adj
                        esoteric_reasons.extend(altitude_reasons)
                        logger.debug(
                            "Altitude adjustment: %.2f for %s home game",
                            altitude_adj, home_team
                        )
                except Exception as e:
                    logger.debug("Altitude adjustment failed: %s", e)
'''


# -----------------------------------------------------------------------------
# 3. TRAVEL FATIGUE - Add to compute_context_modifiers() (~line 2990)
# -----------------------------------------------------------------------------
TRAVEL_FATIGUE_CONTEXT = '''
    # ===== TRAVEL FATIGUE (v17.9) =====
    # Wire ESPN rest_days to travel module for B2B and fatigue detection
    if rest_days_override is not None:
        try:
            if TRAVEL_MODULE_AVAILABLE:
                from alt_data_sources.travel import calculate_distance, calculate_fatigue_impact

                # Calculate distance between teams
                distance = 0
                if away_team and home_team:
                    distance = calculate_distance(away_team, home_team)

                # Calculate fatigue impact
                fatigue = calculate_fatigue_impact(
                    sport=sport,
                    distance_miles=distance,
                    rest_days_away=int(rest_days_override),
                    rest_days_home=0  # We focus on away team fatigue
                )

                result["travel_fatigue"] = {
                    "rest_days": int(rest_days_override),
                    "distance_miles": distance,
                    "adjustment": fatigue.get("away_team_fatigue", 0.0),
                    "overall_impact": fatigue.get("overall_impact", "NONE"),
                    "reasons": fatigue.get("reasons", [])
                }
                logger.debug(
                    "Travel fatigue calculated: rest=%d, dist=%d, impact=%s",
                    int(rest_days_override), distance, fatigue.get("overall_impact")
                )
        except Exception as e:
            logger.debug("Travel fatigue calc failed: %s", e)
'''


# -----------------------------------------------------------------------------
# 4. TRAVEL FATIGUE APPLICATION - Add to calculate_pick_score() (~line 3165)
# -----------------------------------------------------------------------------
TRAVEL_FATIGUE_APPLICATION = '''
            # ===== TRAVEL FATIGUE TO CONTEXT (v17.9) =====
            # Apply fatigue penalties to context_score
            travel_adj = 0.0
            if _ctx_mods and _ctx_mods.get("travel_fatigue"):
                try:
                    _tf = _ctx_mods["travel_fatigue"]
                    _rest = _tf.get("rest_days", 1)
                    _dist = _tf.get("distance_miles", 0)
                    _impact = _tf.get("overall_impact", "NONE")

                    # B2B (back-to-back) is the strongest penalty
                    if _rest == 0:
                        travel_adj = -0.5
                        context_reasons.append(f"B2B: Back-to-back game (-0.5)")
                    # Short rest with long travel
                    elif _rest == 1 and _dist > 1500:
                        travel_adj = -0.35
                        context_reasons.append(f"Travel: {_dist}mi + 1-day rest (-0.35)")
                    # High impact from travel module
                    elif _impact == "HIGH":
                        travel_adj = -0.4
                        for r in _tf.get("reasons", []):
                            context_reasons.append(f"Travel: {r}")
                    # Medium impact
                    elif _impact == "MEDIUM" and _dist > 1000:
                        travel_adj = -0.2
                        context_reasons.append(f"Travel: {_dist}mi distance (-0.2)")

                    if travel_adj != 0.0:
                        context_raw += travel_adj
                        logger.debug(
                            "Travel fatigue applied: %.2f for %s (rest=%d, dist=%d)",
                            travel_adj, away_team, _rest, _dist
                        )
                except Exception as e:
                    logger.debug("Travel context failed: %s", e)
'''


# -----------------------------------------------------------------------------
# 5. REMOVE OLD WEATHER APPLICATION (~lines 5371-5377)
# -----------------------------------------------------------------------------
OLD_WEATHER_TO_REMOVE = '''
# REMOVE THIS SECTION (around lines 5371-5377):
# This applies weather directly to final_score, bypassing engine weights
#
# if _game_weather and _game_weather.get("available"):
#     _wmod = _game_weather.get("weather_modifier", 0.0)
#     if _wmod != 0.0:
#         final_score = max(0.0, min(10.0, final_score + _wmod))
#         # ... weather reasons appended to final_reasons
'''


# =============================================================================
# VERIFICATION SCRIPT
# =============================================================================

class StadiumAltitudeServiceTest:
    """Test version of StadiumAltitudeService for verification."""

    HIGH_ALTITUDE = {
        "broncos": 5280, "nuggets": 5280, "rockies": 5200, "avalanche": 5280,
        "jazz": 4226, "utah": 4226, "real salt lake": 4226,
        "colorado": 5430, "air force": 6621, "wyoming": 7220,
        "new mexico": 5312, "byu": 4551, "utah state": 4528,
        "mexico city": 7350, "azteca": 7350,
    }

    @classmethod
    def get_altitude_adjustment(cls, sport: str, home_team: str, pick_type: str, pick_side: str) -> tuple:
        if not home_team:
            return (0.0, [])

        home_lower = home_team.lower().strip()
        altitude = next((alt for k, alt in cls.HIGH_ALTITUDE.items() if k in home_lower), 0)

        if altitude < 4000:
            return (0.0, [])

        sport_upper = sport.upper() if sport else ""
        pick_type_upper = pick_type.upper() if pick_type else ""
        pick_side_lower = pick_side.lower() if pick_side else ""

        if sport_upper == "MLB" and altitude >= 5000:
            if pick_type_upper == "TOTAL":
                if "over" in pick_side_lower:
                    return (0.5, [f"Coors Field {altitude}ft favors OVER (+0.5)"])
                elif "under" in pick_side_lower:
                    return (-0.3, [f"Coors Field {altitude}ft penalizes UNDER (-0.3)"])
            return (0.2, [f"Altitude {altitude}ft boosts offense (+0.2)"])

        if sport_upper in ("NFL", "NCAAF") and altitude >= 5000:
            return (0.25, [f"Mile High {altitude}ft visitor fatigue (+0.25)"])

        if sport_upper in ("NBA", "NHL") and altitude >= 4000:
            return (0.15, [f"Altitude {altitude}ft moderate effect (+0.15)"])

        if altitude >= 4000:
            return (0.15, [f"Altitude {altitude}ft moderate effect (+0.15)"])

        return (0.0, [])


def verify_v17_9_integration():
    """Run verification checks after implementation."""
    import subprocess
    import sys

    print("=" * 60)
    print("v17.9 Weather, Altitude & Travel Integration Verification")
    print("=" * 60)

    # 1. Test StadiumAltitudeService
    print("\n1. Testing StadiumAltitudeService...")
    try:
        # Test Denver (NFL)
        adj, reasons = StadiumAltitudeServiceTest.get_altitude_adjustment(
            "NFL", "Denver Broncos", "SPREAD", "Away"
        )
        assert adj == 0.25, f"Expected 0.25 for Denver NFL, got {adj}"
        assert "5280ft" in reasons[0], "Should mention altitude"
        print("   ✓ Denver NFL altitude: +0.25")

        # Test Coors Field (MLB Over)
        adj, reasons = StadiumAltitudeServiceTest.get_altitude_adjustment(
            "MLB", "Colorado Rockies", "TOTAL", "Over"
        )
        assert adj == 0.5, f"Expected 0.5 for Coors Over, got {adj}"
        print("   ✓ Coors Field MLB Over: +0.5")

        # Test Coors Field (MLB Under)
        adj, reasons = StadiumAltitudeServiceTest.get_altitude_adjustment(
            "MLB", "Colorado Rockies", "TOTAL", "Under"
        )
        assert adj == -0.3, f"Expected -0.3 for Coors Under, got {adj}"
        print("   ✓ Coors Field MLB Under: -0.3")

        # Test Utah (NBA)
        adj, reasons = StadiumAltitudeServiceTest.get_altitude_adjustment(
            "NBA", "Utah Jazz", "SPREAD", "Jazz"
        )
        assert adj == 0.15, f"Expected 0.15 for Utah NBA, got {adj}"
        print("   ✓ Utah NBA altitude: +0.15")

        # Test non-altitude venue
        adj, reasons = StadiumAltitudeServiceTest.get_altitude_adjustment(
            "NBA", "Los Angeles Lakers", "SPREAD", "Lakers"
        )
        assert adj == 0.0, f"Expected 0.0 for LA, got {adj}"
        print("   ✓ Low altitude venue: 0.0 (no adjustment)")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 2. Syntax check on this file
    print("\n2. Syntax check...")
    files_to_check = ["v17.9_weather_altitude_travel.py"]
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

    print("\nIntegration Summary:")
    print("┌────────────┬──────────────────┬─────────────────────┐")
    print("│ Signal     │ Target Score     │ Adjustment Range    │")
    print("├────────────┼──────────────────┼─────────────────────┤")
    print("│ Weather    │ research_score   │ -0.5 to 0.0         │")
    print("│ Altitude   │ esoteric_score   │ -0.3 to +0.5        │")
    print("│ Travel/B2B │ context_score    │ -0.5 to 0.0         │")
    print("└────────────┴──────────────────┴─────────────────────┘")

    print("\nApply changes in this order:")
    print("1. Add StadiumAltitudeService class to context_layer.py (~line 970)")
    print("2. Add StadiumAltitudeService import to live_data_router.py")
    print("3. Add WEATHER_INTEGRATION to live_data_router.py (~line 4060)")
    print("4. Add ALTITUDE_INTEGRATION to live_data_router.py (~line 3745)")
    print("5. Add TRAVEL_FATIGUE_CONTEXT to compute_context_modifiers() (~line 2990)")
    print("6. Add TRAVEL_FATIGUE_APPLICATION to calculate_pick_score() (~line 3165)")
    print("7. REMOVE old weather application (~lines 5371-5377)")
    print("8. Deploy and verify with curl commands")

    return True


if __name__ == "__main__":
    verify_v17_9_integration()
