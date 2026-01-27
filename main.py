"""
Bookie-o-em v14.7 - TITANIUM TIER SUPPORT
FastAPI Backend Server

Features:
- v10.1 Research-optimized weights (+94.40u YTD)
- Standalone Esoteric Edge (Gematria/Numerology/Astro)
- v10.4 SCALAR-SAVANT (6 modules)
- v11.0 OMNI-GLITCH (6 modules)
- v11.08 TITANIUM SMASH tier (3/4 engines >= 8.0)
- v13.0 GANN PHYSICS (3 modules)
- v14.0 NOOSPHERE VELOCITY (3 modules - MAIN MODEL)
- v14.1 Production hardening (retries, logging, rate-limit handling)
- v14.7 Single source of truth for tiers (tiering.py)

Total: 18 esoteric modules
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from fastapi.responses import Response
from live_data_router import router as live_router, close_shared_client
import database
from daily_scheduler import scheduler_router, init_scheduler, get_scheduler
from auto_grader import get_grader
from data_dir import ensure_dirs, DATA_DIR
from metrics import get_metrics_response, get_metrics_status, PROMETHEUS_AVAILABLE

app = FastAPI(
    title="Bookie-o-em API",
    description="AI Sports Prop Betting Service - v14.7 TITANIUM TIER SUPPORT",
    version="14.7"
)

# CORS - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Smoke test MUST be registered before the /live router (which requires auth)
@app.get("/live/smoke-test/alert-status")
@app.head("/live/smoke-test/alert-status")
async def smoke_test_alert_status():
    return {"status": "ok"}

# Include routers
app.include_router(live_router)
app.include_router(scheduler_router)

# Startup event - initialize database and scheduler
@app.on_event("startup")
async def startup_event():
    ensure_dirs()
    database.init_database()
    # Initialize and start daily scheduler with auto_grader connection
    # CRITICAL: Pass grader so scheduler can adjust weights on audit
    grader = get_grader()
    scheduler = init_scheduler(auto_grader=grader)
    scheduler.start()

# Shutdown event - clean up shared httpx client and scheduler
@app.on_event("shutdown")
async def shutdown_event():
    await close_shared_client()
    scheduler = get_scheduler()
    if scheduler:
        scheduler.stop()


# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Bookie-o-em",
        "version": "14.1",
        "codename": "PRODUCTION_HARDENED",
        "status": "operational",
        "message": "Someone always knows.",
        "endpoints": {
            "health": "/live/health",
            "sharp_money": "/live/sharp/{sport}",
            "splits": "/live/splits/{sport}",
            "props": "/live/props/{sport}",
            "best_bets": "/live/best-bets/{sport}",
            "esoteric_edge": "/live/esoteric-edge",
            "esoteric_today": "/esoteric/today-energy",
            "noosphere": "/live/noosphere/status",
            "gann_physics": "/live/gann-physics-status"
        },
        "sports": ["nba", "nfl", "mlb", "nhl"]
    }

# Health check at root level (some frontends expect this)
@app.get("/health")
async def health():
    return {"status": "healthy", "version": "14.2", "database": database.DB_ENABLED}


# Database status endpoint
@app.get("/database/status")
async def database_status():
    return database.get_database_status()


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    content, content_type = get_metrics_response()
    return Response(content=content, media_type=content_type)


# Metrics status endpoint
@app.get("/metrics/status")
async def metrics_status():
    return get_metrics_status()

# Esoteric today energy (frontend expects this at /esoteric/today-energy)
@app.get("/esoteric/today-energy")
async def esoteric_today_energy():
    from datetime import date
    from esoteric_engine import get_daily_esoteric_reading
    from esoteric_grader import get_esoteric_grader

    today = date.today()
    reading = get_daily_esoteric_reading(today)
    grader = get_esoteric_grader()

    # Build void moon periods array
    void_moon_periods = []
    if reading["void_moon"]["is_void"]:
        void_moon_periods.append({
            "start": reading["void_moon"]["void_start"],
            "end": reading["void_moon"]["void_end"]
        })

    # Get accuracy stats for current signals
    outlook_accuracy = grader.get_signal_accuracy("betting_outlook", reading["betting_outlook"])
    void_moon_accuracy = grader.get_signal_accuracy("void_moon", reading["void_moon"]["is_void"])
    planetary_accuracy = grader.get_signal_accuracy("planetary_ruler", reading["planetary_hours"]["current_ruler"])
    noosphere_accuracy = grader.get_signal_accuracy("noosphere", reading["noosphere"]["trending_direction"])

    # Calculate combined edge for today
    current_signals = {
        "void_moon_active": reading["void_moon"]["is_void"],
        "planetary_ruler": reading["planetary_hours"]["current_ruler"],
        "noosphere_direction": reading["noosphere"]["trending_direction"],
        "betting_outlook": reading["betting_outlook"],
    }
    combined_edge = grader.get_combined_edge(current_signals)

    return {
        "date": today.isoformat(),
        "betting_outlook": reading["betting_outlook"],
        "overall_energy": reading["overall_energy"],
        "moon_phase": reading["void_moon"]["moon_sign"].lower(),
        "void_moon_periods": void_moon_periods,
        "schumann_reading": {
            "frequency_hz": reading["schumann_reading"]["current_hz"],
            "status": reading["schumann_reading"]["status"]
        },
        "planetary_hours": reading["planetary_hours"],
        "noosphere": reading["noosphere"],
        "recommendation": reading["recommendation"],
        "accuracy": {
            "outlook": outlook_accuracy,
            "void_moon": void_moon_accuracy,
            "planetary": planetary_accuracy,
            "noosphere": noosphere_accuracy
        },
        "combined_edge": combined_edge
    }

# ============================================================================
# DEBUG: AUTOGRADER VERIFICATION ENDPOINTS (no auth)
# ============================================================================

@app.get("/debug/pending-picks")
async def debug_pending_picks():
    """Return count and sample of ungraded picks."""
    try:
        from pick_logger import get_pick_logger
        from datetime import datetime, timedelta
        import pytz
        now_et = datetime.now(pytz.timezone("America/New_York"))
        today = now_et.strftime("%Y-%m-%d")
        yesterday = (now_et - timedelta(days=1)).strftime("%Y-%m-%d")

        pl = get_pick_logger()
        today_picks = pl.get_picks_for_date(today)
        yesterday_picks = pl.get_picks_for_date(yesterday)
        today_pending = [p for p in today_picks if not p.result]
        yesterday_pending = [p for p in yesterday_picks if not p.result]

        def pick_summary(p):
            return {
                "pick_id": p.pick_id, "sport": p.sport, "matchup": p.matchup,
                "player": p.player_name, "line": p.line, "side": p.side,
                "final_score": p.final_score, "tier": p.tier,
                "result": p.result, "date": p.date,
            }

        return {
            "today": today, "yesterday": yesterday,
            "today_total": len(today_picks), "today_pending": len(today_pending),
            "yesterday_total": len(yesterday_picks), "yesterday_pending": len(yesterday_pending),
            "sample_today": [pick_summary(p) for p in today_pending[:5]],
            "sample_yesterday": [pick_summary(p) for p in yesterday_pending[:5]],
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/debug/seed-pick")
async def debug_seed_pick():
    """Create 1 fake pending pick dated yesterday for autograder testing."""
    try:
        from pick_logger import get_pick_logger
        from datetime import datetime, timedelta
        import pytz
        ET = pytz.timezone("America/New_York")
        yesterday = (datetime.now(ET) - timedelta(days=1)).strftime("%Y-%m-%d")

        pl = get_pick_logger()
        fake = {
            "sport": "NBA", "pick_type": "PROP",
            "player_name": "LeBron James", "matchup": "LAL @ BOS",
            "home_team": "Boston Celtics", "away_team": "Los Angeles Lakers",
            "prop_type": "points", "line": 25.5, "side": "Over",
            "odds": -110, "book": "fanduel", "final_score": 8.5,
            "ai_score": 7.0, "research_score": 8.0,
            "esoteric_score": 6.0, "jarvis_score": 5.0,
            "tier": "GOLD_STAR", "units": 1.0,
            "start_time_et": (datetime.now(ET) - timedelta(hours=3)).isoformat(),
        }
        result = pl.log_pick(pick_data=fake, game_start_time=fake["start_time_et"], skip_duplicates=False)
        return {"seeded": True, "date": yesterday, "result": result}
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/storage-info")
async def debug_storage_info():
    """Show storage paths and file counts for diagnosing persistence."""
    import os, glob
    from data_dir import DATA_DIR, PICK_LOGS, GRADED_PICKS, GRADER_DATA, AUDIT_LOGS
    try:
        from pick_logger import get_pick_logger
        pl = get_pick_logger()
        storage = pl.storage_path
        graded = pl.graded_path
        in_memory = {date: len(picks) for date, picks in pl.picks.items()}
    except Exception as e:
        storage = graded = str(e)
        in_memory = {}

    def list_files(d):
        if not os.path.exists(d):
            return {"exists": False}
        files = os.listdir(d)
        return {"exists": True, "count": len(files), "files": files[:20]}

    return {
        "DATA_DIR": DATA_DIR,
        "RAILWAY_VOLUME_MOUNT_PATH": os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "NOT SET"),
        "pick_logger_storage_path": storage,
        "pick_logger_graded_path": graded,
        "in_memory_picks": in_memory,
        "dirs": {
            "pick_logs": list_files(PICK_LOGS),
            "graded_picks": list_files(GRADED_PICKS),
            "grader_data": list_files(GRADER_DATA),
            "audit_logs": list_files(AUDIT_LOGS),
        }
    }


@app.post("/debug/run-autograde")
async def debug_run_autograde():
    """Trigger one grading pass immediately."""
    try:
        from result_fetcher import scheduled_auto_grade
        result = await scheduled_auto_grade()
        return {"triggered": True, "result": result}
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/prediction-store-status")
async def debug_prediction_store_status():
    """Counts for pending/graded picks, last 24h, and filenames."""
    try:
        import os
        from pick_logger import get_pick_logger
        from datetime import datetime, timedelta
        from dataclasses import asdict
        import pytz
        ET = pytz.timezone("America/New_York")
        now_et = datetime.now(ET)
        today = now_et.strftime("%Y-%m-%d")
        yesterday = (now_et - timedelta(days=1)).strftime("%Y-%m-%d")
        from data_dir import PICK_LOGS, GRADED_PICKS

        pl = get_pick_logger()

        def date_stats(date_str):
            picks = pl.get_picks_for_date(date_str)
            pending = [p for p in picks if not p.result]
            graded = [p for p in picks if p.result]
            log_file = os.path.join(PICK_LOGS, f"picks_{date_str}.jsonl")
            graded_file = os.path.join(GRADED_PICKS, f"graded_{date_str}.jsonl")
            return {
                "total": len(picks),
                "pending": len(pending),
                "graded": len(graded),
                "wins": sum(1 for p in graded if p.result == "WIN"),
                "losses": sum(1 for p in graded if p.result == "LOSS"),
                "pushes": sum(1 for p in graded if p.result == "PUSH"),
                "log_file": log_file,
                "log_exists": os.path.exists(log_file),
                "graded_file": graded_file,
                "graded_exists": os.path.exists(graded_file),
            }

        return {
            "today": {"date": today, **date_stats(today)},
            "yesterday": {"date": yesterday, **date_stats(yesterday)},
            "in_memory_dates": list(pl.picks.keys()),
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/debug/seed-pick-and-grade")
async def debug_seed_pick_and_grade():
    """Seed a fake pick, persist it, run one grading pass, return the updated record."""
    try:
        from pick_logger import get_pick_logger
        from result_fetcher import auto_grade_picks
        from datetime import datetime, timedelta
        from dataclasses import asdict
        import pytz
        ET = pytz.timezone("America/New_York")
        now_et = datetime.now(ET)
        today = now_et.strftime("%Y-%m-%d")

        pl = get_pick_logger()

        # Seed a pick with a start time in the past so it's gradable
        fake = {
            "sport": "NBA", "pick_type": "PROP",
            "player_name": "LeBron James", "matchup": "LAL @ BOS",
            "home_team": "Boston Celtics", "away_team": "Los Angeles Lakers",
            "prop_type": "points", "line": 25.5, "side": "Over",
            "odds": -110, "book": "fanduel", "final_score": 8.5,
            "ai_score": 7.0, "research_score": 8.0,
            "esoteric_score": 6.0, "jarvis_score": 5.0,
            "tier": "GOLD_STAR", "units": 1.0,
            "start_time_et": (now_et - timedelta(hours=4)).isoformat(),
        }
        seed_result = pl.log_pick(pick_data=fake, game_start_time=fake["start_time_et"], skip_duplicates=False)
        pick_id = seed_result.get("pick_id")

        # Run autograde
        grade_result = await auto_grade_picks(date=today)

        # Fetch the pick back
        updated_pick = None
        for p in pl.get_picks_for_date(today):
            if p.pick_id == pick_id:
                updated_pick = {
                    "pick_id": p.pick_id, "result": p.result,
                    "graded": p.graded, "grade_status": p.grade_status,
                    "actual_value": p.actual_value, "graded_at": p.graded_at,
                    "units_won_lost": p.units_won_lost,
                }
                break

        return {
            "seed": seed_result,
            "grade_summary": {
                "picks_graded": grade_result.get("picks_graded", 0),
                "picks_failed": grade_result.get("picks_failed", 0),
            },
            "updated_pick": updated_pick,
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
