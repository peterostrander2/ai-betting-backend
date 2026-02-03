"""
live_data_router.py v17.9 Changes
=================================

This file contains the exact code blocks to add/modify in live_data_router.py
for the Weather, Altitude & Travel Fatigue integration.

Apply these changes in order:
1. Add imports (top of file)
2. Add travel fatigue application (~line 3165)
3. Add altitude integration (~line 3745)
4. Add weather integration (~line 4060)
5. Remove old weather code (~lines 5371-5377)
"""

# =============================================================================
# 1. IMPORTS - Add at top of file with other imports
# =============================================================================

IMPORTS_TO_ADD = '''
# v17.9 imports
from context_layer import StadiumAltitudeService

# Travel module import (v17.9)
try:
    from alt_data_sources.travel import calculate_distance, calculate_fatigue_impact
    TRAVEL_MODULE_AVAILABLE = True
except ImportError:
    TRAVEL_MODULE_AVAILABLE = False
    logger.debug("Travel module not available")
'''


# =============================================================================
# 2. TRAVEL FATIGUE APPLICATION - Add in calculate_pick_score() ~line 3165
#    (in the context scoring section, after context_raw is initialized)
# =============================================================================

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
                        context_reasons.append("B2B: Back-to-back game (-0.5)")
                    # Short rest with long travel
                    elif _rest == 1 and _dist > 1500:
                        travel_adj = -0.35
                        context_reasons.append(f"Travel: {_dist}mi + 1-day rest (-0.35)")
                    # High impact from travel module
                    elif _impact == "HIGH":
                        travel_adj = -0.4
                        for r in _tf.get("reasons", []):
                            context_reasons.append(f"Travel: {r}")
                    # Medium impact with significant distance
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


# =============================================================================
# 3. ALTITUDE INTEGRATION - Add in esoteric section ~line 3745
#    (after GLITCH aggregate calculation)
# =============================================================================

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


# =============================================================================
# 4. WEATHER INTEGRATION - Add after research calc ~line 4060
#    (before officials section)
# =============================================================================

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


# =============================================================================
# 5. REMOVE OLD WEATHER CODE - Delete lines ~5371-5377
#    (this code applies weather directly to final_score, bypassing engines)
# =============================================================================

OLD_WEATHER_TO_REMOVE = '''
# FIND AND DELETE THIS BLOCK (approximately lines 5371-5377):
# ------------------------------------------------------------
            # Apply weather modifier directly to final score
            if _game_weather and _game_weather.get("available"):
                _wmod = _game_weather.get("weather_modifier", 0.0)
                if _wmod != 0.0:
                    final_score = max(0.0, min(10.0, final_score + _wmod))
                    for wr in _game_weather.get("weather_reasons", []):
                        final_reasons.append(f"Weather: {wr}")
# ------------------------------------------------------------
# Replace with a comment:
            # v17.9: Weather now applied to research_score (see ~line 4060)
'''


# =============================================================================
# FULL EXAMPLE OF calculate_pick_score SECTION WITH ALL v17.9 CHANGES
# =============================================================================

EXAMPLE_CALCULATE_PICK_SCORE_SECTION = '''
async def calculate_pick_score(
    sport: str,
    home_team: str,
    away_team: str,
    pick_type: str,
    pick_side: str,
    # ... other params ...
    _game_weather: Optional[dict] = None,
    _ctx_mods: Optional[dict] = None,
    _officials_by_game: Optional[dict] = None,
    **kwargs
) -> dict:
    """Calculate pick score with all 17 pillars."""

    sport_upper = sport.upper() if sport else ""

    # Initialize scores
    context_raw = 5.0
    context_reasons = []
    esoteric_raw = 5.0
    esoteric_reasons = []
    research_raw = 5.0
    research_reasons = []

    # ... existing code ...

    # =========================================================================
    # CONTEXT SCORING SECTION (~line 3165)
    # =========================================================================

    # ... existing context calculations ...

    # ===== TRAVEL FATIGUE TO CONTEXT (v17.9) =====
    travel_adj = 0.0
    if _ctx_mods and _ctx_mods.get("travel_fatigue"):
        try:
            _tf = _ctx_mods["travel_fatigue"]
            _rest = _tf.get("rest_days", 1)
            _dist = _tf.get("distance_miles", 0)
            _impact = _tf.get("overall_impact", "NONE")

            if _rest == 0:  # B2B
                travel_adj = -0.5
                context_reasons.append("B2B: Back-to-back game (-0.5)")
            elif _rest == 1 and _dist > 1500:
                travel_adj = -0.35
                context_reasons.append(f"Travel: {_dist}mi + 1-day rest (-0.35)")
            elif _impact == "HIGH":
                travel_adj = -0.4
                for r in _tf.get("reasons", []):
                    context_reasons.append(f"Travel: {r}")
            elif _impact == "MEDIUM" and _dist > 1000:
                travel_adj = -0.2
                context_reasons.append(f"Travel: {_dist}mi distance (-0.2)")

            if travel_adj != 0.0:
                context_raw += travel_adj
        except Exception as e:
            logger.debug("Travel context failed: %s", e)

    # Clamp context score
    context_score = max(0.0, min(10.0, context_raw))

    # =========================================================================
    # ESOTERIC SCORING SECTION (~line 3745)
    # =========================================================================

    # ... GLITCH aggregate calculation ...

    # ===== ALTITUDE IMPACT (v17.9) =====
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
        except Exception as e:
            logger.debug("Altitude adjustment failed: %s", e)

    # Clamp esoteric score
    esoteric_score = max(0.0, min(10.0, esoteric_raw))

    # =========================================================================
    # RESEARCH SCORING SECTION (~line 4060)
    # =========================================================================

    # ... existing research calculations ...

    # ===== WEATHER IMPACT ON RESEARCH (v17.9) =====
    weather_adj = 0.0
    if sport_upper in ("NFL", "MLB", "NCAAF") and _game_weather:
        try:
            _wmod = _game_weather.get("weather_modifier", 0.0)
            if _game_weather.get("available") and _wmod != 0.0:
                weather_adj = max(-0.5, _wmod * 0.5)
                research_raw += weather_adj
                for wr in _game_weather.get("weather_reasons", []):
                    research_reasons.append(f"Weather: {wr}")
        except Exception as e:
            logger.debug("Weather adjustment failed: %s", e)

    # ... OFFICIALS section (v17.8) ...

    # Clamp research score
    research_score = max(0.0, min(10.0, research_raw))

    # =========================================================================
    # FINAL SCORE CALCULATION (~line 5371)
    # =========================================================================

    # Calculate weighted final score
    final_score = (
        context_score * 0.30 +   # Context engine 30%
        esoteric_score * 0.35 +  # Esoteric engine 35%
        research_score * 0.20 +  # Research engine 20%
        ai_score * 0.15          # AI engine 15%
    )

    # v17.9: Weather now applied to research_score (see ~line 4060)
    # Old direct application to final_score has been removed

    # ... rest of function ...
'''


# =============================================================================
# VERIFICATION CODE
# =============================================================================

def print_changes_summary():
    """Print summary of changes to apply."""
    print("=" * 70)
    print("v17.9 Changes for live_data_router.py")
    print("=" * 70)
    print()
    print("1. ADD IMPORTS (top of file):")
    print("   - from context_layer import StadiumAltitudeService")
    print("   - Travel module import with try/except")
    print()
    print("2. ADD TRAVEL FATIGUE (~line 3165, context section):")
    print("   - B2B detection: -0.5 adjustment")
    print("   - Short rest + long travel: -0.35 adjustment")
    print("   - HIGH impact: -0.4 adjustment")
    print("   - MEDIUM + distance: -0.2 adjustment")
    print()
    print("3. ADD ALTITUDE (~line 3745, esoteric section):")
    print("   - Denver/Coors: +0.25 to +0.5")
    print("   - Utah: +0.15")
    print("   - College high-altitude: +0.25")
    print()
    print("4. ADD WEATHER (~line 4060, research section):")
    print("   - Scale by 0.5, cap at -0.5")
    print("   - Add to research_reasons with 'Weather:' prefix")
    print()
    print("5. REMOVE OLD WEATHER (~lines 5371-5377):")
    print("   - Delete direct application to final_score")
    print("   - Replace with comment noting v17.9 change")
    print()
    print("=" * 70)


if __name__ == "__main__":
    print_changes_summary()
