"""
ESOTERIC.PY - Esoteric Analysis Router

Esoteric signals, noosphere, GANN physics, and debug endpoints.

Endpoints:
    GET  /debug/esoteric-candidates/{sport}  - Debug esoteric candidates with full audit data
    GET  /esoteric-edge                       - Comprehensive esoteric edge analysis
    GET  /esoteric-accuracy                   - Historical accuracy stats for all signals
    GET  /esoteric-accuracy/{signal_type}     - Accuracy stats for specific signal type
    GET  /noosphere/status                    - Noosphere velocity indicators
    GET  /gann-physics-status                 - W.D. Gann geometric principles
    GET  /esoteric-analysis                   - Complete esoteric analysis (Phase 1-3)
"""

import hashlib
import logging
import os
import random
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from core.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["esoteric"])

# Sport mappings for validation
SPORT_MAPPINGS = {
    "nba": {"odds": "basketball_nba", "espn": "basketball/nba", "playbook": "NBA"},
    "nfl": {"odds": "americanfootball_nfl", "espn": "football/nfl", "playbook": "NFL"},
    "mlb": {"odds": "baseball_mlb", "espn": "baseball/mlb", "playbook": "MLB"},
    "nhl": {"odds": "icehockey_nhl", "espn": "hockey/nhl", "playbook": "NHL"},
    "ncaab": {"odds": "basketball_ncaab", "espn": "basketball/mens-college-basketball", "playbook": "NCAAB"},
}

# Scoring constants for debug endpoint (simplified calculations)
ESOTERIC_WEIGHT = 0.20
OUTPUT_MINIMUM = 6.5


async def _fetch_props_internal(sport: str, date_str: str) -> Dict[str, Any]:
    """Internal helper to fetch props for esoteric debug endpoint."""
    try:
        from odds_api import get_props
        props = await get_props(sport)
        return {"events": props.get("events", []) if props else []}
    except Exception as e:
        logger.warning("Props fetch error: %s", e)
        return {"events": []}


async def _fetch_games_internal(sport: str, date_str: str) -> Dict[str, Any]:
    """Internal helper to fetch games for esoteric debug endpoint."""
    try:
        from odds_api import get_games
        games = await get_games(sport)
        return {"events": games if isinstance(games, list) else games.get("events", []) if games else []}
    except Exception as e:
        logger.warning("Games fetch error: %s", e)
        return {"events": []}


@router.get("/debug/esoteric-candidates/{sport}")
async def debug_esoteric_candidates(
    sport: str,
    limit: int = 25,
    api_key: str = Depends(verify_api_key)
):
    """
    DEBUG ENDPOINT: Esoteric candidates with full semantic audit data.

    Returns ALL candidates (including suppressed below 6.5) with:
    - Full esoteric_breakdown with per-signal provenance
    - auth_context (NOAA: auth_type="none", SerpAPI: key_present bool)
    - request_proof (request-local NOAA call counters)
    - filtered_out_reason for suppressed candidates

    This endpoint enables semantic truthfulness verification:
    - Every signal has source_api attribution
    - Every external API call has call_proof with http_requests_delta
    - auth_context shows auth_type="none" for NOAA (NOT key_present)
    - request_proof proves calls happened on THIS request

    Args:
        sport: Sport code (NBA, NFL, etc.)
        limit: Maximum candidates to return (default 25)

    Returns:
        candidates_pre_filter: All scored candidates with full breakdown
        auth_context: NOAA/SerpAPI auth info
        request_proof: Request-local NOAA call counters
        total_candidates: Total count before any filtering
        passed_filter_count: Count passing 6.5 threshold
        suppressed_count: Count below 6.5 threshold
        build_sha: Deployed commit SHA

    Requires:
        X-API-Key header
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    sport_upper = sport.upper()

    # Initialize request-local NOAA proof
    try:
        from alt_data_sources.noaa import (
            init_noaa_request_proof,
            get_noaa_request_proof,
            get_noaa_auth_context,
        )
        noaa_proof = init_noaa_request_proof()
        noaa_auth = get_noaa_auth_context()
    except ImportError:
        noaa_proof = None
        noaa_auth = {"auth_type": "none", "enabled": False, "base_url_source": "unavailable"}

    # Get SerpAPI auth context
    try:
        from esoteric_engine import get_serpapi_auth_context
        serpapi_auth = get_serpapi_auth_context()
    except ImportError:
        serpapi_auth = {"auth_type": "api_key", "key_present": False, "key_source": "none"}

    # Get ET date for filtering
    try:
        from core.time_et import et_day_bounds
        start_et, end_et, start_utc, end_utc = et_day_bounds()
        date_str = start_et.date().isoformat()
    except Exception:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Fetch candidates
    candidates_pre_filter = []
    total_candidates = 0
    passed_filter_count = 0
    suppressed_count = 0

    try:
        # Get props for the sport
        props_data = await _fetch_props_internal(sport_lower, date_str)
        props_events = props_data.get("events", [])

        # Get game events
        games_data = await _fetch_games_internal(sport_lower, date_str)
        game_events = games_data.get("events", [])

        # Process a sample of props
        for prop_event in props_events[:min(limit, len(props_events))]:
            total_candidates += 1

            try:
                # Extract prop info
                player_name = prop_event.get("player_name", "Unknown")
                prop_line = prop_event.get("line", 0)
                home_team = prop_event.get("home_team", "")
                away_team = prop_event.get("away_team", "")
                game_str = f"{away_team}@{home_team}"
                game_datetime = prop_event.get("commence_time")
                event_id = prop_event.get("event_id", "")

                # Get player birth data
                from player_birth_data import get_player_data
                player_data = get_player_data(player_name)
                birth_date_str = player_data.get("birth_date") if player_data else None

                # Calculate GLITCH aggregate
                from esoteric_engine import get_glitch_aggregate, get_phase8_esoteric_signals, build_esoteric_breakdown_with_provenance

                game_date_obj = None
                if game_datetime:
                    try:
                        if isinstance(game_datetime, str):
                            game_datetime = datetime.fromisoformat(game_datetime.replace('Z', '+00:00'))
                        game_date_obj = game_datetime.date() if hasattr(game_datetime, 'date') else None
                    except Exception:
                        game_date_obj = datetime.now().date()
                else:
                    game_date_obj = datetime.now().date()

                # Get GLITCH result
                glitch_result = get_glitch_aggregate(
                    birth_date_str=birth_date_str,
                    game_date=game_date_obj,
                    game_time=game_datetime if isinstance(game_datetime, datetime) else None,
                    line_history=None,
                    value_for_benford=None,
                    primary_value=prop_line
                )

                # Get Phase 8 result
                phase8_result = get_phase8_esoteric_signals(
                    game_datetime=game_datetime if isinstance(game_datetime, datetime) else None,
                    game_date=game_date_obj,
                    sport=sport_upper,
                    home_team=home_team,
                    away_team=away_team,
                    pick_type="PROP",
                    pick_side="Over",
                )

                # Build esoteric breakdown with provenance
                esoteric_breakdown = build_esoteric_breakdown_with_provenance(
                    glitch_result=glitch_result,
                    phase8_result=phase8_result,
                    numerology_raw=0.5,
                    numerology_signals=[],
                    player_name=player_name,
                    game_date=game_date_obj,
                    birth_date_str=birth_date_str,
                    astro_score=5.0,
                    fib_score=0,
                    vortex_score=0,
                    daily_edge_score=0,
                    trap_mod=0,
                    vortex_boost=0,
                    fib_retracement_boost=0,
                    altitude_boost=0,
                    surface_boost=0,
                    sport=sport_upper,
                    home_team=home_team,
                    away_team=away_team,
                    spread=None,
                    total=None,
                    prop_line=prop_line,
                    venue_city=None,
                    noaa_request_proof=noaa_proof,
                )

                # Calculate a sample esoteric score
                esoteric_score = glitch_result.get("glitch_score_10", 5.0)
                final_score = 5.0 + esoteric_score * ESOTERIC_WEIGHT  # Simplified for demo

                # Determine if passed filter
                passed_filter = final_score >= OUTPUT_MINIMUM
                if passed_filter:
                    passed_filter_count += 1
                else:
                    suppressed_count += 1

                candidate = {
                    "pick_id": hashlib.sha256(f"{event_id}|{player_name}|{prop_line}".encode()).hexdigest()[:12],
                    "player_name": player_name,
                    "matchup": game_str,
                    "prop_line": prop_line,
                    "esoteric_score": round(esoteric_score, 2),
                    "final_score": round(final_score, 2),
                    "passed_filter": passed_filter,
                    "filtered_out_reason": None if passed_filter else "score_below_threshold",
                    "esoteric_breakdown": esoteric_breakdown,
                    "esoteric_reasons": glitch_result.get("reasons", []) + phase8_result.get("reasons", []),
                }
                candidates_pre_filter.append(candidate)

            except Exception as e:
                logger.warning("Error processing prop candidate: %s", e)
                continue

        # Process a sample of games
        for game_event in game_events[:min(limit - len(candidates_pre_filter), len(game_events))]:
            if len(candidates_pre_filter) >= limit:
                break

            total_candidates += 1

            try:
                home_team = game_event.get("home_team", "")
                away_team = game_event.get("away_team", "")
                game_str = f"{away_team}@{home_team}"
                spread = game_event.get("spread", 0)
                total = game_event.get("total", 220)
                game_datetime = game_event.get("commence_time")
                event_id = game_event.get("id", "")

                game_date_obj = None
                if game_datetime:
                    try:
                        if isinstance(game_datetime, str):
                            game_datetime = datetime.fromisoformat(game_datetime.replace('Z', '+00:00'))
                        game_date_obj = game_datetime.date() if hasattr(game_datetime, 'date') else None
                    except Exception:
                        game_date_obj = datetime.now().date()
                else:
                    game_date_obj = datetime.now().date()

                from esoteric_engine import get_glitch_aggregate, get_phase8_esoteric_signals, build_esoteric_breakdown_with_provenance

                # Get GLITCH result (no birth date for games)
                glitch_result = get_glitch_aggregate(
                    birth_date_str=None,
                    game_date=game_date_obj,
                    game_time=game_datetime if isinstance(game_datetime, datetime) else None,
                    line_history=None,
                    value_for_benford=None,
                    primary_value=spread
                )

                # Get Phase 8 result
                phase8_result = get_phase8_esoteric_signals(
                    game_datetime=game_datetime if isinstance(game_datetime, datetime) else None,
                    game_date=game_date_obj,
                    sport=sport_upper,
                    home_team=home_team,
                    away_team=away_team,
                    pick_type="SPREAD",
                    pick_side=home_team,
                )

                # Build esoteric breakdown with provenance
                esoteric_breakdown = build_esoteric_breakdown_with_provenance(
                    glitch_result=glitch_result,
                    phase8_result=phase8_result,
                    numerology_raw=0.5,
                    numerology_signals=[],
                    player_name=None,
                    game_date=game_date_obj,
                    birth_date_str=None,
                    astro_score=5.0,
                    fib_score=0,
                    vortex_score=0,
                    daily_edge_score=0,
                    trap_mod=0,
                    vortex_boost=0,
                    fib_retracement_boost=0,
                    altitude_boost=0,
                    surface_boost=0,
                    sport=sport_upper,
                    home_team=home_team,
                    away_team=away_team,
                    spread=spread,
                    total=total,
                    prop_line=None,
                    venue_city=None,
                    noaa_request_proof=noaa_proof,
                )

                esoteric_score = glitch_result.get("glitch_score_10", 5.0)
                final_score = 5.0 + esoteric_score * ESOTERIC_WEIGHT

                passed_filter = final_score >= OUTPUT_MINIMUM
                if passed_filter:
                    passed_filter_count += 1
                else:
                    suppressed_count += 1

                candidate = {
                    "pick_id": hashlib.sha256(f"{event_id}|{home_team}|{spread}".encode()).hexdigest()[:12],
                    "player_name": None,
                    "matchup": game_str,
                    "spread": spread,
                    "total": total,
                    "esoteric_score": round(esoteric_score, 2),
                    "final_score": round(final_score, 2),
                    "passed_filter": passed_filter,
                    "filtered_out_reason": None if passed_filter else "score_below_threshold",
                    "esoteric_breakdown": esoteric_breakdown,
                    "esoteric_reasons": glitch_result.get("reasons", []) + phase8_result.get("reasons", []),
                }
                candidates_pre_filter.append(candidate)

            except Exception as e:
                logger.warning("Error processing game candidate: %s", e)
                continue

    except Exception as e:
        logger.error("Error fetching candidates for esoteric debug: %s", e)

    # Build request proof from noaa_proof
    request_proof = noaa_proof.to_dict() if noaa_proof else {
        "noaa_calls": 0,
        "noaa_2xx": 0,
        "noaa_4xx": 0,
        "noaa_5xx": 0,
        "noaa_timeouts": 0,
        "noaa_cache_hits": 0,
        "noaa_errors": 0,
    }

    # Build auth context
    auth_context = {
        "noaa": noaa_auth,
        "serpapi": serpapi_auth,
    }

    # Get build SHA
    build_sha = os.getenv("RAILWAY_GIT_COMMIT_SHA", os.getenv("BUILD_SHA", "unknown"))[:8]

    return {
        "candidates_pre_filter": candidates_pre_filter,
        "auth_context": auth_context,
        "request_proof": request_proof,
        "total_candidates": total_candidates,
        "passed_filter_count": passed_filter_count,
        "suppressed_count": suppressed_count,
        "sport": sport_upper,
        "date_et": date_str,
        "build_sha": build_sha,
    }


@router.get("/esoteric-edge")
async def get_esoteric_edge():
    """
    Get comprehensive esoteric edge analysis with historical accuracy stats.
    Returns daily energy + game signals + prop signals + accuracy data.
    """
    from esoteric_engine import (
        get_daily_esoteric_reading,
        calculate_void_moon,
        get_schumann_frequency,
        get_planetary_hour,
        calculate_noosphere_velocity,
        check_founders_echo,
        analyze_spread_gann,
        calculate_atmospheric_drag,
        calculate_biorhythms,
        check_life_path_sync,
        calculate_hurst_exponent,
        calculate_life_path,
        SAMPLE_PLAYERS
    )
    from esoteric_grader import get_esoteric_grader

    today = datetime.now().date()
    grader = get_esoteric_grader()

    # Daily reading
    daily = get_daily_esoteric_reading(today)

    # Get accuracy for current signals
    current_signals = {
        "void_moon_active": daily["void_moon"]["is_void"],
        "planetary_ruler": daily["planetary_hours"]["current_ruler"],
        "noosphere_direction": daily["noosphere"]["trending_direction"],
        "betting_outlook": daily["betting_outlook"],
    }
    combined_edge = grader.get_combined_edge(current_signals)

    # Get accuracy stats for each signal type
    outlook_accuracy = grader.get_signal_accuracy("betting_outlook", daily["betting_outlook"])
    void_moon_accuracy = grader.get_signal_accuracy("void_moon", daily["void_moon"]["is_void"])
    planetary_accuracy = grader.get_signal_accuracy("planetary_ruler", daily["planetary_hours"]["current_ruler"])
    noosphere_accuracy = grader.get_signal_accuracy("noosphere", daily["noosphere"]["trending_direction"])

    # Sample game signals (in production, would fetch from best-bets)
    sample_games = [
        {"game_id": "sample1", "home_team": "Lakers", "away_team": "Celtics", "spread": -3.5, "total": 225.5, "city": "Los Angeles"},
        {"game_id": "sample2", "home_team": "Warriors", "away_team": "Bulls", "spread": -7.5, "total": 232, "city": "San Francisco"},
    ]

    game_signals = []
    for game in sample_games:
        founders_home = check_founders_echo(game["home_team"])
        founders_away = check_founders_echo(game["away_team"])
        gann = analyze_spread_gann(game["spread"], game["total"])
        gann_accuracy = grader.get_signal_accuracy("gann_resonance", gann["combined_resonance"])
        founders_accuracy = grader.get_signal_accuracy("founders_echo", founders_home["resonance"] or founders_away["resonance"])

        game_signals.append({
            "game_id": game["game_id"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "signals": {
                "founders_echo": {
                    "home_match": founders_home["resonance"],
                    "away_match": founders_away["resonance"],
                    "boost": founders_home["boost"] + founders_away["boost"],
                    "accuracy": founders_accuracy
                },
                "gann_square": {
                    "spread_angle": gann["spread"]["angle"],
                    "resonant": gann["combined_resonance"],
                    "accuracy": gann_accuracy
                },
                "atmospheric": calculate_atmospheric_drag(game["city"])
            }
        })

    # Sample player signals with accuracy
    prop_signals = []
    for player_name, player_data in list(SAMPLE_PLAYERS.items())[:4]:
        bio = calculate_biorhythms(player_data["birth_date"])
        life_path = check_life_path_sync(player_name, player_data["birth_date"], player_data["jersey"])

        # Get accuracy for this player's signals
        bio_accuracy = grader.get_signal_accuracy("biorhythm", bio["status"])
        life_path_accuracy = grader.get_signal_accuracy("life_path", life_path["life_path"])

        prop_signals.append({
            "player_id": player_name.lower().replace(" ", "_"),
            "player_name": player_name,
            "signals": {
                "biorhythms": {
                    "physical": bio["physical"],
                    "emotional": bio["emotional"],
                    "intellectual": bio["intellectual"],
                    "status": bio["status"],
                    "accuracy": bio_accuracy
                },
                "life_path_sync": {
                    "player_life_path": life_path["life_path"],
                    "jersey_number": life_path["jersey_number"],
                    "sync_score": life_path["sync_score"],
                    "accuracy": life_path_accuracy
                }
            }
        })

    return {
        "timestamp": datetime.now().isoformat() + "Z",
        "daily_energy": {
            "betting_outlook": daily["betting_outlook"],
            "overall_energy": daily["overall_energy"],
            "moon_phase": daily["void_moon"]["moon_sign"].lower() if daily["void_moon"] else "unknown",
            "void_moon": daily["void_moon"],
            "schumann_frequency": daily["schumann_reading"],
            "planetary_hours": daily["planetary_hours"],
            "accuracy": {
                "outlook": outlook_accuracy,
                "void_moon": void_moon_accuracy,
                "planetary": planetary_accuracy,
                "noosphere": noosphere_accuracy
            }
        },
        "combined_edge": combined_edge,
        "game_signals": game_signals,
        "prop_signals": prop_signals,
        "parlay_warnings": [],
        "noosphere": daily["noosphere"]
    }


@router.get("/esoteric-accuracy")
async def get_esoteric_accuracy():
    """
    Get historical accuracy stats for all esoteric signals.
    Shows edge percentages based on historical performance.
    """
    from esoteric_grader import get_esoteric_grader

    grader = get_esoteric_grader()
    all_stats = grader.get_all_accuracy_stats()
    performance = grader.get_performance_summary(days_back=30)

    return {
        "timestamp": datetime.now().isoformat(),
        "accuracy_by_signal": all_stats,
        "recent_performance": performance,
        "methodology": {
            "edge_calculation": "Hit rate vs 50% baseline",
            "sample_sources": "Historical betting data + tracked predictions",
            "update_frequency": "Real-time as predictions are graded"
        }
    }


@router.get("/esoteric-accuracy/{signal_type}")
async def get_signal_accuracy(signal_type: str, value: str = None):
    """
    Get accuracy stats for a specific signal type.

    signal_type options: life_path, biorhythm, void_moon, planetary_ruler,
                        noosphere, gann_resonance, founders_echo, betting_outlook
    """
    from esoteric_grader import get_esoteric_grader

    grader = get_esoteric_grader()

    valid_types = [
        "life_path", "biorhythm", "void_moon", "planetary_ruler",
        "noosphere", "gann_resonance", "founders_echo", "betting_outlook"
    ]

    if signal_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid signal_type. Must be one of: {valid_types}"
        )

    if value:
        # Convert value to appropriate type
        if signal_type == "life_path":
            try:
                value = int(value)
            except Exception:
                pass
        elif signal_type in ["void_moon", "gann_resonance", "founders_echo"]:
            value = value.lower() in ["true", "1", "yes"]

        accuracy = grader.get_signal_accuracy(signal_type, value)
        return {
            "signal_type": signal_type,
            "value": value,
            "accuracy": accuracy,
            "timestamp": datetime.now().isoformat()
        }
    else:
        # Return all values for this signal type
        all_stats = grader.get_all_accuracy_stats()
        return {
            "signal_type": signal_type,
            "all_values": all_stats.get(signal_type, {}),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/noosphere/status")
async def get_noosphere_status():
    """Noosphere Velocity - Global consciousness indicators."""
    # Use deterministic RNG based on current hour for stable results within the hour
    hour_seed = int(datetime.now().strftime("%Y%m%d%H"))
    rng = random.Random(hour_seed)
    coherence = rng.uniform(0.3, 0.9)
    anomaly_detected = coherence > 0.7

    return {
        "status": "ACTIVE",
        "version": "14.1",
        "global_coherence": round(coherence, 3),
        "anomaly_detected": anomaly_detected,
        "anomaly_strength": "STRONG" if coherence > 0.8 else "MODERATE" if coherence > 0.6 else "WEAK",
        "interpretation": "Collective attention spike - information asymmetry likely" if anomaly_detected else "Normal variance",
        "betting_signal": "FADE PUBLIC" if anomaly_detected else "FOLLOW TRENDS",
        "modules": {
            "insider_leak": {"status": "monitoring", "signal": "NEUTRAL"},
            "main_character_syndrome": {"status": "active", "signal": "CHECK NARRATIVES"},
            "phantom_injury": {"status": "scanning", "signal": "NO ALERTS"}
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/gann-physics-status")
async def get_gann_physics_status():
    """GANN Physics - W.D. Gann's geometric principles applied to sports."""
    today = datetime.now()
    day_of_year = today.timetuple().tm_yday

    retracement_level = (day_of_year % 90) / 90 * 100
    rule_of_three = (day_of_year % 3 == 0)
    annulifier = (day_of_year % 7 == 0)

    return {
        "status": "ACTIVE",
        "date": today.strftime("%Y-%m-%d"),
        "modules": {
            "50_retracement": {
                "level": round(retracement_level, 1),
                "signal": "REVERSAL ZONE" if 45 <= retracement_level <= 55 else "TREND CONTINUATION",
                "description": "Gravity check - markets tend to retrace 50%"
            },
            "rule_of_three": {
                "active": rule_of_three,
                "signal": "EXHAUSTION" if rule_of_three else "MOMENTUM",
                "description": "Third attempt usually fails or succeeds dramatically"
            },
            "annulifier_cycle": {
                "active": annulifier,
                "signal": "HARMONIC LOCK" if annulifier else "NORMAL",
                "description": "7-day cycle completion - expect resolution"
            }
        },
        "overall_signal": "REVERSAL" if (retracement_level > 45 and rule_of_three) else "CONTINUATION",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/esoteric-analysis")
async def get_esoteric_analysis(
    player: str = "Player",
    team: str = "Team",
    opponent: str = "Opponent",
    spread: float = 0,
    total: float = 220,
    public_pct: float = 50,
    model_probability: float = 50
):
    """
    Get complete esoteric analysis using all Phase 1-3 components.

    Returns:
    - Gematria signal
    - Public fade analysis
    - Mid-spread/Goldilocks
    - Trap detection
    - Astro/Vedic score
    - Confluence level
    - Blended probability (67/33 formula)
    - Bet tier recommendation
    """
    try:
        from jarvis_savant_engine import calculate_full_esoteric_analysis

        analysis = calculate_full_esoteric_analysis(
            player=player,
            team=team,
            opponent=opponent,
            spread=spread,
            total=total,
            public_pct=public_pct,
            model_probability=model_probability
        )

        return analysis

    except ImportError:
        raise HTTPException(status_code=503, detail="Esoteric analysis module not available")
