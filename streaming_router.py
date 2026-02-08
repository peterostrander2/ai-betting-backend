"""
REAL-TIME STREAMING ROUTER - SSE/WebSocket endpoints (v20.0 Phase 9)

Provides real-time data streaming for:
- Live game updates
- Score changes
- Line movements
- Pick status changes

Uses Server-Sent Events (SSE) for unidirectional streaming.

FEATURE FLAG: PHASE9_STREAMING_ENABLED (default: false until tested)

Dependencies:
- sse-starlette>=1.6.5
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
import asyncio
import json
import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger("streaming")

# Feature flag
STREAMING_ENABLED = os.getenv("PHASE9_STREAMING_ENABLED", "false").lower() == "true"

# Stream configuration
DEFAULT_REFRESH_INTERVAL = 30  # seconds
MIN_REFRESH_INTERVAL = 15      # minimum allowed
MAX_REFRESH_INTERVAL = 120     # maximum allowed

# Try to import SSE support
try:
    from sse_starlette.sse import EventSourceResponse
    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False
    EventSourceResponse = None
    logger.warning("sse-starlette not installed. Streaming disabled.")

router = APIRouter(prefix="/live/stream", tags=["streaming"])


def get_streaming_status() -> Dict[str, Any]:
    """Get streaming feature status."""
    return {
        "enabled": STREAMING_ENABLED,
        "sse_available": SSE_AVAILABLE,
        "default_refresh_seconds": DEFAULT_REFRESH_INTERVAL,
        "status": "ACTIVE" if (STREAMING_ENABLED and SSE_AVAILABLE) else "DISABLED"
    }


async def _fetch_live_games(sport: str) -> List[Dict[str, Any]]:
    """
    Fetch live games for a sport.

    Returns list of games with current status, scores, and line info.
    """
    live_games = []

    try:
        # Import ESPN scoreboard fetcher
        from alt_data_sources.espn_lineups import get_espn_scoreboard, ESPN_AVAILABLE

        if not ESPN_AVAILABLE:
            return []

        # Get scoreboard data
        scoreboard = await get_espn_scoreboard(sport)

        if not scoreboard:
            return []

        # Filter to live games only
        for event in scoreboard:
            status = event.get("status", {})
            status_type = status.get("type", {})
            state = status_type.get("state", "")

            # Live games have state "in"
            if state.lower() == "in":
                competition = event.get("competitions", [{}])[0]
                competitors = competition.get("competitors", [])

                home_team = None
                away_team = None
                home_score = 0
                away_score = 0

                for comp in competitors:
                    if comp.get("homeAway") == "home":
                        home_team = comp.get("team", {}).get("displayName", "")
                        home_score = int(comp.get("score", 0) or 0)
                    else:
                        away_team = comp.get("team", {}).get("displayName", "")
                        away_score = int(comp.get("score", 0) or 0)

                live_games.append({
                    "event_id": event.get("id"),
                    "sport": sport.upper(),
                    "status": "LIVE",
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_score": home_score,
                    "away_score": away_score,
                    "period": status_type.get("shortDetail", ""),
                    "clock": status.get("displayClock", ""),
                    "last_update": datetime.now(tz=timezone.utc).isoformat()
                })

    except Exception as e:
        logger.warning(f"Error fetching live games for {sport}: {e}")

    return live_games


async def _fetch_line_movements(sport: str) -> List[Dict[str, Any]]:
    """
    Fetch recent line movements for a sport.

    Returns list of significant line changes in last update cycle.
    """
    movements = []

    try:
        # Import line history from database
        from database import get_session, get_recent_line_movements

        async with get_session() as session:
            # Get movements from last 30 minutes
            movements = await get_recent_line_movements(session, sport, minutes=30)

    except ImportError:
        logger.debug("Line movement tracking not available")
    except Exception as e:
        logger.debug(f"Error fetching line movements: {e}")

    return movements


@router.get("/status")
async def get_stream_status():
    """
    Get streaming endpoint status.

    Returns whether streaming is enabled and available.
    """
    return get_streaming_status()


@router.get("/games/{sport}")
async def stream_live_games(
    sport: str,
    request: Request,
    refresh: int = Query(default=DEFAULT_REFRESH_INTERVAL, ge=MIN_REFRESH_INTERVAL, le=MAX_REFRESH_INTERVAL)
):
    """
    SSE endpoint for live game state updates.

    Streams live game data for a sport. Updates at specified refresh interval.

    Args:
        sport: Sport code (NBA, NFL, MLB, NHL, NCAAB)
        refresh: Refresh interval in seconds (15-120, default 30)

    Returns:
        Server-Sent Events stream with game updates
    """
    # Check if streaming is enabled
    if not STREAMING_ENABLED:
        return JSONResponse(
            status_code=503,
            content={
                "error": "Streaming disabled",
                "detail": "Set PHASE9_STREAMING_ENABLED=true to enable streaming"
            }
        )

    # Check if SSE is available
    if not SSE_AVAILABLE or EventSourceResponse is None:
        return JSONResponse(
            status_code=503,
            content={
                "error": "SSE not available",
                "detail": "Install sse-starlette>=1.6.5 to enable streaming"
            }
        )

    sport_upper = sport.upper()
    valid_sports = ["NBA", "NFL", "MLB", "NHL", "NCAAB"]

    if sport_upper not in valid_sports:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sport. Must be one of: {', '.join(valid_sports)}"
        )

    async def event_generator():
        """Generate SSE events for live games."""
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.debug(f"Client disconnected from {sport_upper} stream")
                    break

                # Fetch live games
                games = await _fetch_live_games(sport_upper)

                # Build event data
                event_data = {
                    "sport": sport_upper,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "live_count": len(games),
                    "games": games
                }

                # Yield as SSE event
                yield {
                    "event": "games",
                    "data": json.dumps(event_data),
                    "retry": refresh * 1000  # Retry in milliseconds
                }

                # Wait for next refresh
                await asyncio.sleep(refresh)

        except asyncio.CancelledError:
            logger.debug(f"Stream cancelled for {sport_upper}")
        except Exception as e:
            logger.error(f"Stream error for {sport_upper}: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())


@router.get("/lines/{sport}")
async def stream_line_movements(
    sport: str,
    request: Request,
    refresh: int = Query(default=DEFAULT_REFRESH_INTERVAL, ge=MIN_REFRESH_INTERVAL, le=MAX_REFRESH_INTERVAL)
):
    """
    SSE endpoint for line movement updates.

    Streams line movement data. Useful for detecting sharp action in real-time.

    Args:
        sport: Sport code (NBA, NFL, MLB, NHL, NCAAB)
        refresh: Refresh interval in seconds (15-120, default 30)

    Returns:
        Server-Sent Events stream with line movements
    """
    # Check if streaming is enabled
    if not STREAMING_ENABLED:
        return JSONResponse(
            status_code=503,
            content={
                "error": "Streaming disabled",
                "detail": "Set PHASE9_STREAMING_ENABLED=true to enable streaming"
            }
        )

    # Check if SSE is available
    if not SSE_AVAILABLE or EventSourceResponse is None:
        return JSONResponse(
            status_code=503,
            content={
                "error": "SSE not available",
                "detail": "Install sse-starlette>=1.6.5 to enable streaming"
            }
        )

    sport_upper = sport.upper()

    async def event_generator():
        """Generate SSE events for line movements."""
        try:
            while True:
                if await request.is_disconnected():
                    break

                # Fetch line movements
                movements = await _fetch_line_movements(sport_upper)

                event_data = {
                    "sport": sport_upper,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "movement_count": len(movements),
                    "movements": movements[:20]  # Limit to 20 most recent
                }

                yield {
                    "event": "lines",
                    "data": json.dumps(event_data),
                    "retry": refresh * 1000
                }

                await asyncio.sleep(refresh)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Line stream error for {sport_upper}: {e}")

    return EventSourceResponse(event_generator())


@router.get("/picks/{sport}")
async def stream_pick_updates(
    sport: str,
    request: Request,
    min_score: float = Query(default=7.0, ge=6.5, le=10.0),
    refresh: int = Query(default=60, ge=30, le=300)
):
    """
    SSE endpoint for high-confidence pick updates.

    Streams picks that meet the minimum score threshold.
    Useful for real-time alerts on new high-confidence picks.

    Args:
        sport: Sport code
        min_score: Minimum final_score to include (default 7.0)
        refresh: Refresh interval in seconds (30-300, default 60)

    Returns:
        Server-Sent Events stream with pick updates
    """
    if not STREAMING_ENABLED:
        return JSONResponse(
            status_code=503,
            content={"error": "Streaming disabled"}
        )

    if not SSE_AVAILABLE or EventSourceResponse is None:
        return JSONResponse(
            status_code=503,
            content={"error": "SSE not available"}
        )

    sport_upper = sport.upper()
    seen_picks = set()  # Track picks we've already sent

    async def event_generator():
        """Generate SSE events for new picks."""
        nonlocal seen_picks

        try:
            while True:
                if await request.is_disconnected():
                    break

                new_picks = []

                try:
                    # Import best-bets function
                    from live_data_router import get_best_bets

                    # Fetch current picks
                    result = await get_best_bets(sport_upper, debug=False)

                    # Combine game picks and props
                    all_picks = []
                    if result.get("game_picks", {}).get("picks"):
                        all_picks.extend(result["game_picks"]["picks"])
                    if result.get("props", {}).get("picks"):
                        all_picks.extend(result["props"]["picks"])

                    # Filter to high-confidence and new picks
                    for pick in all_picks:
                        pick_id = pick.get("pick_id") or pick.get("prediction_id", "")
                        final_score = pick.get("final_score", 0)

                        if final_score >= min_score and pick_id not in seen_picks:
                            # Slim down pick data for streaming (bandwidth)
                            slim_pick = {
                                "pick_id": pick_id,
                                "description": pick.get("description", ""),
                                "matchup": pick.get("matchup", ""),
                                "tier": pick.get("tier", ""),
                                "final_score": final_score,
                                "line": pick.get("line"),
                                "odds": pick.get("odds_american"),
                                "book": pick.get("book", "")
                            }
                            new_picks.append(slim_pick)
                            seen_picks.add(pick_id)

                except Exception as e:
                    logger.warning(f"Error fetching picks for stream: {e}")

                event_data = {
                    "sport": sport_upper,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "new_picks_count": len(new_picks),
                    "picks": new_picks,
                    "min_score_filter": min_score
                }

                yield {
                    "event": "picks",
                    "data": json.dumps(event_data),
                    "retry": refresh * 1000
                }

                await asyncio.sleep(refresh)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Picks stream error: {e}")

    return EventSourceResponse(event_generator())


# ============================================================
# POLLING FALLBACK ENDPOINTS (For clients that don't support SSE)
# ============================================================

@router.get("/poll/games/{sport}")
async def poll_live_games(sport: str):
    """
    Polling endpoint for live games (SSE fallback).

    Use this if your client doesn't support Server-Sent Events.
    Returns current snapshot of live games.
    """
    sport_upper = sport.upper()
    games = await _fetch_live_games(sport_upper)

    return {
        "sport": sport_upper,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "live_count": len(games),
        "games": games,
        "next_refresh_seconds": DEFAULT_REFRESH_INTERVAL
    }


@router.get("/poll/lines/{sport}")
async def poll_line_movements(sport: str):
    """
    Polling endpoint for line movements (SSE fallback).
    """
    sport_upper = sport.upper()
    movements = await _fetch_line_movements(sport_upper)

    return {
        "sport": sport_upper,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "movement_count": len(movements),
        "movements": movements[:20],
        "next_refresh_seconds": DEFAULT_REFRESH_INTERVAL
    }
