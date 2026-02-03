"""
Live Data Router - Main API Entry Point
========================================

Version: v17.9
- Weather integration to research_score
- Altitude integration to esoteric_score
- Travel/B2B integration to context_score

Endpoints:
- /health - Health check
- /live/best-bets/{sport} - Get best bets for a sport
- /games/{sport} - Get games for a sport
- /props/{sport} - Get props for a sport
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# =============================================================================
# IMPORTS - Context Layer (v17.8 + v17.9)
# =============================================================================

try:
    from context_layer import (
        DefensiveRankService,
        PaceVectorService,
        UsageVacuumService,
        OfficialsService,
        ParkFactorsService,
        StadiumAltitudeService,  # v17.9
        compute_context_modifiers,
    )
    CONTEXT_LAYER_AVAILABLE = True
except ImportError as e:
    logger.warning("Context layer not available: %s", e)
    CONTEXT_LAYER_AVAILABLE = False

# =============================================================================
# IMPORTS - Travel Module (v17.9)
# =============================================================================

try:
    from alt_data_sources.travel import calculate_distance, calculate_fatigue_impact
    TRAVEL_MODULE_AVAILABLE = True
except ImportError:
    TRAVEL_MODULE_AVAILABLE = False
    logger.debug("Travel module not available")

# =============================================================================
# IMPORTS - Officials Data (v17.8)
# =============================================================================

try:
    from officials_data import get_referee_tendency, calculate_officials_adjustment
    OFFICIALS_DATA_AVAILABLE = True
except ImportError:
    OFFICIALS_DATA_AVAILABLE = False
    logger.debug("Officials data not available")

# =============================================================================
# IMPORTS - Database
# =============================================================================

DB_ENABLED = os.getenv("DB_ENABLED", "false").lower() == "true"

if DB_ENABLED:
    try:
        from database import get_db, get_line_history_values, get_season_extreme
        DATABASE_AVAILABLE = True
    except ImportError:
        DATABASE_AVAILABLE = False
        logger.warning("Database module not available")
else:
    DATABASE_AVAILABLE = False

# =============================================================================
# IMPORTS - Esoteric Engine
# =============================================================================

try:
    from esoteric_engine import (
        get_glitch_aggregate,
        calculate_fibonacci_retracement,
    )
    ESOTERIC_ENGINE_AVAILABLE = True
except ImportError:
    ESOTERIC_ENGINE_AVAILABLE = False
    logger.warning("Esoteric engine not available")

# =============================================================================
# APP SETUP
# =============================================================================

app = FastAPI(
    title="Sports Betting API",
    description="Esoteric sports betting signal API",
    version="17.9"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key validation
API_KEY = os.getenv("API_KEY", "test_key")


def validate_api_key(x_api_key: str = Header(None)):
    """Validate API key from header."""
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# =============================================================================
# HEALTH ENDPOINT
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "17.9",
        "timestamp": datetime.utcnow().isoformat(),
        "modules": {
            "context_layer": CONTEXT_LAYER_AVAILABLE,
            "travel_module": TRAVEL_MODULE_AVAILABLE,
            "officials_data": OFFICIALS_DATA_AVAILABLE,
            "database": DATABASE_AVAILABLE,
            "esoteric_engine": ESOTERIC_ENGINE_AVAILABLE,
        }
    }


# =============================================================================
# MAIN SCORING FUNCTION
# =============================================================================

async def calculate_pick_score(
    sport: str,
    home_team: str,
    away_team: str,
    pick_type: str,
    pick_side: str,
    line_value: Optional[float] = None,
    event_id: Optional[str] = None,
    game_date: Optional[str] = None,
    game_time: Optional[str] = None,
    _game_weather: Optional[dict] = None,
    _ctx_mods: Optional[dict] = None,
    _officials_by_game: Optional[dict] = None,
    _rest_days_by_team: Optional[dict] = None,
    **kwargs
) -> dict:
    """
    Calculate pick score with all 17 pillars + alt data integrations.

    Engine Weights:
    - Context: 30%
    - Esoteric: 35%
    - Research: 20%
    - AI: 15%

    v17.9 Alt Data Integration:
    - Weather → research_score (-0.5 to 0.0)
    - Altitude → esoteric_score (-0.3 to +0.5)
    - Travel/B2B → context_score (-0.5 to 0.0)
    """
    sport_upper = sport.upper() if sport else ""

    # Initialize scores
    context_raw = 5.0
    context_reasons = []
    esoteric_raw = 5.0
    esoteric_reasons = []
    research_raw = 5.0
    research_reasons = []
    ai_raw = 5.0
    ai_reasons = []

    # =========================================================================
    # CONTEXT SCORING SECTION (~line 3165)
    # =========================================================================

    # Pillar 13: Defensive Rank
    if CONTEXT_LAYER_AVAILABLE:
        try:
            def_adj, def_reasons = DefensiveRankService.get_defensive_adjustment(
                sport_upper, home_team, away_team, pick_type
            )
            if def_adj != 0:
                context_raw += def_adj
                context_reasons.extend(def_reasons)
        except Exception as e:
            logger.debug("Defensive rank failed: %s", e)

    # Pillar 14: Pace Vector
    if CONTEXT_LAYER_AVAILABLE:
        try:
            pace_adj, pace_reasons = PaceVectorService.get_pace_adjustment(
                sport_upper, home_team, away_team, pick_type
            )
            if pace_adj != 0:
                context_raw += pace_adj
                context_reasons.extend(pace_reasons)
        except Exception as e:
            logger.debug("Pace vector failed: %s", e)

    # Pillar 15: Usage Vacuum (if injuries data available)
    # ... would be added here ...

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

    # Also check _rest_days_by_team directly if _ctx_mods wasn't computed
    elif _rest_days_by_team and away_team and TRAVEL_MODULE_AVAILABLE:
        try:
            away_lower = away_team.lower().strip()
            rest_days = None
            for team_key, days in _rest_days_by_team.items():
                if away_lower in team_key.lower() or team_key.lower() in away_lower:
                    rest_days = days
                    break

            if rest_days is not None:
                distance = calculate_distance(away_team, home_team) if home_team else 0
                fatigue = calculate_fatigue_impact(sport_upper, distance, rest_days, 0)

                _rest = rest_days
                _dist = distance
                _impact = fatigue.get("overall_impact", "NONE")

                if _rest == 0:
                    travel_adj = -0.5
                    context_reasons.append("B2B: Back-to-back game (-0.5)")
                elif _rest == 1 and _dist > 1500:
                    travel_adj = -0.35
                    context_reasons.append(f"Travel: {_dist}mi + 1-day rest (-0.35)")
                elif _impact == "HIGH":
                    travel_adj = -0.4
                    for r in fatigue.get("reasons", []):
                        context_reasons.append(f"Travel: {r}")
                elif _impact == "MEDIUM" and _dist > 1000:
                    travel_adj = -0.2
                    context_reasons.append(f"Travel: {_dist}mi distance (-0.2)")

                if travel_adj != 0.0:
                    context_raw += travel_adj
        except Exception as e:
            logger.debug("Direct travel calc failed: %s", e)

    # Clamp context score
    context_score = max(0.0, min(10.0, context_raw))

    # =========================================================================
    # ESOTERIC SCORING SECTION (~line 3745)
    # =========================================================================

    # GLITCH Protocol
    if ESOTERIC_ENGINE_AVAILABLE:
        try:
            # Fetch line history for Hurst if DB available
            _line_history = None
            if DATABASE_AVAILABLE and DB_ENABLED and event_id:
                try:
                    with get_db() as db:
                        if db:
                            _line_history = get_line_history_values(
                                db, event_id, "spread", 30
                            )
                except Exception as e:
                    logger.debug("Line history fetch failed: %s", e)

            # Fetch season extremes for Fibonacci
            _season_high = None
            _season_low = None
            if DATABASE_AVAILABLE and DB_ENABLED:
                try:
                    with get_db() as db:
                        if db:
                            extremes = get_season_extreme(
                                db, sport_upper, "2025-26", "spread"
                            )
                            if extremes:
                                _season_high = extremes.get("season_high")
                                _season_low = extremes.get("season_low")
                except Exception as e:
                    logger.debug("Season extremes fetch failed: %s", e)

            glitch_result = get_glitch_aggregate(
                game_date=game_date,
                game_time=game_time,
                line_history=_line_history,
                season_high=_season_high,
                season_low=_season_low,
                current_line=line_value,
            )

            if glitch_result:
                glitch_score = glitch_result.get("score", 5.0)
                glitch_reasons = glitch_result.get("reasons", [])
                esoteric_raw = glitch_score
                esoteric_reasons.extend(glitch_reasons)
        except Exception as e:
            logger.debug("GLITCH aggregate failed: %s", e)

    # Pillar 17: Park Factors (MLB only)
    if CONTEXT_LAYER_AVAILABLE and sport_upper == "MLB":
        try:
            park_adj, park_reasons = ParkFactorsService.get_park_adjustment(
                home_team, kwargs.get("stadium", ""), pick_type, pick_side
            )
            if park_adj != 0:
                esoteric_raw += park_adj
                esoteric_reasons.extend(park_reasons)
        except Exception as e:
            logger.debug("Park factors failed: %s", e)

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

    # Clamp esoteric score
    esoteric_score = max(0.0, min(10.0, esoteric_raw))

    # =========================================================================
    # RESEARCH SCORING SECTION (~line 4060)
    # =========================================================================

    # Pillar 9: Sharp Money (RLM) - would be added here
    # Pillar 10: Line Variance - would be added here
    # Pillar 11: Public Fade - would be added here
    # Pillar 12: Splits Base - would be added here

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

    # ===== PILLAR 16: OFFICIALS (v17.8) =====
    _officials_adjustment = 0.0
    _officials_reasons = []
    if CONTEXT_LAYER_AVAILABLE and _officials_by_game and home_team and away_team:
        try:
            _home_lower = home_team.lower().strip()
            _away_lower = away_team.lower().strip()

            # Try different key formats
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
                    sport=sport_upper,
                    officials=_game_officials,
                    pick_type=pick_type,
                    pick_side=pick_side,
                    is_home_team=_pick_is_home
                )

                if _officials_adjustment != 0:
                    research_raw += _officials_adjustment
                    research_reasons.extend(_officials_reasons)
                    logger.debug(
                        "Officials adjustment: %.2f for %s vs %s (%s)",
                        _officials_adjustment, home_team, away_team, _officials_reasons
                    )
        except Exception as e:
            logger.debug("Officials adjustment skipped: %s", e)

    # Clamp research score
    research_score = max(0.0, min(10.0, research_raw))

    # =========================================================================
    # AI SCORING SECTION
    # =========================================================================

    # Pillars 1-8: AI Models - would be added here
    ai_score = max(0.0, min(10.0, ai_raw))

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

    # v17.9: Weather now applied to research_score (see above)
    # Old direct application to final_score has been removed

    # Combine all reasons
    final_reasons = []
    if context_reasons:
        final_reasons.extend([f"[Context] {r}" for r in context_reasons])
    if esoteric_reasons:
        final_reasons.extend([f"[Esoteric] {r}" for r in esoteric_reasons])
    if research_reasons:
        final_reasons.extend([f"[Research] {r}" for r in research_reasons])
    if ai_reasons:
        final_reasons.extend([f"[AI] {r}" for r in ai_reasons])

    # Build result
    result = {
        "score": round(final_score, 2),
        "confidence": "HIGH" if final_score >= 7.0 else "MEDIUM" if final_score >= 5.5 else "LOW",
        "sport": sport_upper,
        "home_team": home_team,
        "away_team": away_team,
        "pick_type": pick_type,
        "pick_side": pick_side,
        "line": line_value,

        # Engine scores
        "context_score": round(context_score, 2),
        "esoteric_score": round(esoteric_score, 2),
        "research_score": round(research_score, 2),
        "ai_score": round(ai_score, 2),

        # Reasons by engine
        "context_reasons": context_reasons,
        "esoteric_reasons": esoteric_reasons,
        "research_reasons": research_reasons,
        "ai_reasons": ai_reasons,
        "final_reasons": final_reasons,

        # v17.9 adjustments
        "weather_adjustment": weather_adj,
        "altitude_adjustment": altitude_adj,
        "travel_adjustment": travel_adj,

        # v17.8 officials
        "officials_adjustment": _officials_adjustment,
        "officials_reasons": _officials_reasons,
    }

    return result


# =============================================================================
# BEST BETS ENDPOINT
# =============================================================================

@app.get("/live/best-bets/{sport}")
async def get_best_bets(
    sport: str,
    x_api_key: str = Header(None),
    debug: bool = Query(False),
):
    """
    Get best bets for a sport.

    Args:
        sport: Sport code (NBA, NFL, NHL, MLB, NCAAB, NCAAF)
        debug: Include debug information in response
    """
    validate_api_key(x_api_key)

    sport_upper = sport.upper()
    if sport_upper not in ("NBA", "NFL", "NHL", "MLB", "NCAAB", "NCAAF"):
        raise HTTPException(status_code=400, detail=f"Invalid sport: {sport}")

    # In production, this would fetch real games from ESPN/odds APIs
    # For now, return sample structure

    picks = []

    # Sample pick calculation
    sample_pick = await calculate_pick_score(
        sport=sport_upper,
        home_team="Denver Nuggets" if sport_upper == "NBA" else "Denver Broncos",
        away_team="Los Angeles Lakers" if sport_upper == "NBA" else "Kansas City Chiefs",
        pick_type="SPREAD",
        pick_side="Denver",
        line_value=-3.5,
        _game_weather={
            "available": True,
            "weather_modifier": -0.3,
            "weather_reasons": ["Wind 15mph", "Temperature 35°F"]
        } if sport_upper in ("NFL", "NCAAF") else None,
        _rest_days_by_team={
            "los angeles lakers": 0,  # B2B
            "denver nuggets": 2,
        } if sport_upper == "NBA" else None,
    )

    picks.append(sample_pick)

    response = {
        "sport": sport_upper,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "17.9",
        "game_picks": {
            "count": len(picks),
            "picks": picks,
        }
    }

    if debug:
        response["debug"] = {
            "modules": {
                "context_layer": CONTEXT_LAYER_AVAILABLE,
                "travel_module": TRAVEL_MODULE_AVAILABLE,
                "officials_data": OFFICIALS_DATA_AVAILABLE,
                "database": DATABASE_AVAILABLE,
                "esoteric_engine": ESOTERIC_ENGINE_AVAILABLE,
            }
        }

    return response


# =============================================================================
# GAMES ENDPOINT
# =============================================================================

@app.get("/games/{sport}")
async def get_games(
    sport: str,
    x_api_key: str = Header(None),
):
    """Get games for a sport."""
    validate_api_key(x_api_key)

    sport_upper = sport.upper()

    # In production, fetch from ESPN API
    return {
        "sport": sport_upper,
        "timestamp": datetime.utcnow().isoformat(),
        "games": []
    }


# =============================================================================
# PROPS ENDPOINT
# =============================================================================

@app.get("/props/{sport}")
async def get_props(
    sport: str,
    x_api_key: str = Header(None),
):
    """Get props for a sport."""
    validate_api_key(x_api_key)

    sport_upper = sport.upper()

    # In production, fetch from odds API
    return {
        "sport": sport_upper,
        "timestamp": datetime.utcnow().isoformat(),
        "props": []
    }


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
