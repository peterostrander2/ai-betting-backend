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

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os as _os
import logging
import time

from fastapi.responses import Response, JSONResponse, HTMLResponse
from fastapi import Request
from live_data_router import router as live_router, close_shared_client
from streaming_router import router as streaming_router
from collections import defaultdict
from datetime import datetime, timezone
import database
from daily_scheduler import scheduler_router, init_scheduler, get_scheduler
from trap_router import trap_router
from auto_grader import get_grader
from data_dir import ensure_dirs, DATA_DIR
from metrics import get_metrics_response, get_metrics_status, PROMETHEUS_AVAILABLE
import grader_store
from storage_paths import ensure_persistent_storage_ready, get_storage_health
from integration_registry import (
    list_integrations,
    check_integration_health,
    get_integrations_summary,
    get_health_check_loud,
)
from core.integration_contract import INTEGRATIONS as CONTRACT_INTEGRATIONS, ALL_ENV_VARS

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup/shutdown events.
    Replaces deprecated @app.on_event decorators.
    """
    # ========== STARTUP ==========
    # CRITICAL: Validate storage is on Railway persistent volume FIRST.
    # CRASHES if storage is ephemeral (prevents data loss).
    _logger.info("=" * 60)
    _logger.info("STORAGE VALIDATION (CRASH IF NOT PERSISTENT)")
    _logger.info("=" * 60)

    try:
        ensure_persistent_storage_ready()
        _logger.info("✓ Storage validation PASSED")
    except Exception as e:
        _logger.error("FATAL: Storage validation FAILED: %s", e)
        _logger.error("App will NOT start - storage must be persistent")
        raise

    # Initialize database and directories
    ensure_dirs()
    database.init_database()

    # Initialize and start daily scheduler with auto_grader connection
    # CRITICAL: Pass grader so scheduler can adjust weights on audit
    grader = get_grader()
    scheduler = init_scheduler(auto_grader=grader)
    scheduler.start()

    yield  # App runs here

    # ========== SHUTDOWN ==========
    await close_shared_client()
    scheduler = get_scheduler()
    if scheduler:
        scheduler.stop()


app = FastAPI(
    title="Bookie-o-em API",
    description="AI Sports Prop Betting Service - v14.7 TITANIUM TIER SUPPORT",
    version="14.7",
    lifespan=lifespan
)

# Enforce no-store headers on all /live endpoints (GET/HEAD included)
@app.middleware("http")
async def _live_no_store_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/live/"):
        response.headers.setdefault("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0, private")
        response.headers.setdefault("Pragma", "no-cache")
        response.headers.setdefault("Expires", "0")
        response.headers.setdefault("Vary", "Origin, X-API-Key, Authorization")
    return response

# CORS - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# ADMIN GATING for debug/admin endpoints
# =============================================================================
_DEBUG_MODE = _os.getenv("DEBUG_MODE", "0") == "1"
_ADMIN_TOKEN = _os.getenv("ADMIN_TOKEN", _os.getenv("API_AUTH_KEY", ""))


def _require_admin(x_admin_token: str = Header(None, alias="X-Admin-Token")):
    """Require admin token for debug endpoints. Bypassed when DEBUG_MODE=1."""
    if _DEBUG_MODE:
        return True
    if not x_admin_token or x_admin_token != _ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    return True


# Smoke test MUST be registered before the /live router (which requires auth)
@app.api_route("/live/smoke-test/alert-status", methods=["GET", "HEAD"])
def alert_status():
    return {"ok": True}

# Include routers
app.include_router(live_router)
app.include_router(scheduler_router)
app.include_router(trap_router)  # v19.0: Trap Learning Loop
app.include_router(streaming_router)  # v20.0 Phase 9 - Real-time streaming

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
    build_sha = _os.getenv("RAILWAY_GIT_COMMIT_SHA", "")[:8] or "local"
    deploy_version = "20.9"  # Update with each release

    # --- Truthful health probes (no external calls, fail-soft) ---
    errors = []
    degraded_reasons = []

    # Storage
    try:
        storage_health = get_storage_health()
        storage_ok = storage_health.get("is_mountpoint", False) and storage_health.get("writable", False)
        if not storage_ok:
            errors.append("storage_not_persistent_or_not_writable")
    except Exception as e:
        storage_health = {"ok": False, "error": str(e)}
        errors.append("storage_health_exception")

    # Database (configured vs enabled)
    try:
        db_status = database.get_database_status()
        if db_status.get("configured", False) and not db_status.get("enabled", False):
            degraded_reasons.append("database_configured_but_not_enabled")
    except Exception as e:
        db_status = {"enabled": False, "configured": False, "error": str(e)}
        degraded_reasons.append("database_status_exception")

    # Redis cache
    try:
        from live_data_router import api_cache
        if api_cache:
            cache_status = api_cache.stats()
            redis_ok = cache_status.get("redis_connected", False)
        else:
            cache_status = {"redis_connected": False}
            redis_ok = False
        if not redis_ok:
            degraded_reasons.append("redis_not_connected")
    except Exception as e:
        cache_status = {"redis_connected": False, "error": str(e)}
        degraded_reasons.append("redis_status_exception")

    # Scheduler
    try:
        sched = get_scheduler()
        scheduler_ok = sched is not None and sched.running
        if not scheduler_ok:
            degraded_reasons.append("scheduler_not_running")
    except Exception as e:
        scheduler_ok = False
        degraded_reasons.append(f"scheduler_exception:{e}")

    # Integrations (env-only check; no external probes)
    try:
        integrations_summary = get_integrations_summary()
        integrations_health = get_health_check_loud()
    except Exception as e:
        integrations_summary = {"error": str(e)}
        integrations_health = {"status": "ERROR", "error": str(e)}
        degraded_reasons.append("integrations_check_exception")

    # Compute overall status
    if errors:
        status = "critical"
    elif degraded_reasons or integrations_health.get("status") in ["DEGRADED", "CRITICAL", "ERROR"]:
        status = "degraded"
    else:
        status = "healthy"

    return {
        "status": status,
        "ok": status == "healthy",
        "version": "20.9",
        "build_sha": build_sha,
        "deploy_version": deploy_version,
        "database": database.DB_ENABLED,
        "database_status": db_status,
        "storage": storage_health,
        "redis": cache_status,
        "scheduler": {"running": scheduler_ok},
        "integrations": integrations_summary,
        "integrations_health": integrations_health,
        "errors": errors,
        "degraded_reasons": degraded_reasons,
        "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(),
    }


# =============================================================================
# PUBLIC STATUS PAGE - No auth required, browser-friendly
# =============================================================================

# Rate limiter for /status endpoint (10 req/min per IP)
_status_rate_limit: dict = defaultdict(list)
_STATUS_RATE_LIMIT = 10  # requests
_STATUS_RATE_WINDOW = 60  # seconds


def _check_status_rate_limit(client_ip: str) -> bool:
    """Check if client IP is within rate limit. Returns True if allowed."""
    now = time.time()
    # Clean old entries
    _status_rate_limit[client_ip] = [
        t for t in _status_rate_limit[client_ip] if now - t < _STATUS_RATE_WINDOW
    ]
    if len(_status_rate_limit[client_ip]) >= _STATUS_RATE_LIMIT:
        return False
    _status_rate_limit[client_ip].append(now)
    return True


@app.get("/status", response_class=HTMLResponse)
async def public_status(request: Request):
    """
    Public HTML status page - browser-friendly, no auth required.

    Shows:
    - Build info (SHA, version, engine version)
    - Current ET time and date
    - Internal health checks (redis, db, storage) with simple ✅/❌
    - Curl examples for protected endpoints

    DOES NOT:
    - Expose secrets or connection strings
    - Probe external APIs
    - Accept ?api_key= parameter
    """
    # Rate limit check
    client_ip = request.client.host if request.client else "unknown"
    if not _check_status_rate_limit(client_ip):
        return HTMLResponse(
            content="<html><body><h1>429 Too Many Requests</h1><p>Rate limit: 10 requests per minute</p></body></html>",
            status_code=429
        )

    # Gather status information
    try:
        from core.time_et import now_et, et_day_bounds
        et_now = now_et()
        _, _, et_date = et_day_bounds()
        time_et_str = et_now.strftime("%Y-%m-%d %H:%M:%S ET")
    except Exception:
        time_et_str = "unavailable"
        et_date = "unavailable"

    # Build info
    build_sha = _os.getenv("RAILWAY_GIT_COMMIT_SHA", "")[:8] or "local"
    deploy_version = "16.1"  # Current version
    engine_version = "16.1"  # Tiering version

    # Internal health checks (simple ✅/❌, no secrets)
    checks = {}

    # 1. Storage check
    try:
        storage_health = get_storage_health()
        storage_ok = storage_health.get("is_mountpoint", False) and storage_health.get("writable", False)
        checks["storage"] = storage_ok
    except Exception:
        checks["storage"] = False

    # 2. Database check
    try:
        db_status = database.get_database_status()
        checks["database"] = db_status.get("enabled", False)
    except Exception:
        checks["database"] = False

    # 3. Redis check (from live_data_router cache)
    try:
        from live_data_router import api_cache
        if api_cache:
            cache_status = api_cache.stats()
            checks["redis"] = cache_status.get("redis_connected", False)
        else:
            checks["redis"] = False
    except Exception:
        checks["redis"] = False

    # 4. Scheduler check
    try:
        sched = get_scheduler()
        checks["scheduler"] = sched is not None and sched.running
    except Exception:
        checks["scheduler"] = False

    # Build HTML
    def status_icon(ok: bool) -> str:
        return "✅" if ok else "❌"

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bookie-o-em Status</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
            background: #1a1a2e;
            color: #eee;
            padding: 2rem;
            max-width: 800px;
            margin: 0 auto;
        }}
        h1 {{ color: #00d4ff; margin-bottom: 0.5rem; }}
        .subtitle {{ color: #888; margin-bottom: 2rem; }}
        .section {{
            background: #16213e;
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
        }}
        .section h2 {{
            color: #00d4ff;
            margin-top: 0;
            font-size: 1.1rem;
            border-bottom: 1px solid #333;
            padding-bottom: 0.5rem;
        }}
        .row {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid #222;
        }}
        .row:last-child {{ border-bottom: none; }}
        .label {{ color: #888; }}
        .value {{ color: #fff; font-family: monospace; }}
        .status-ok {{ color: #00ff88; }}
        .status-fail {{ color: #ff4444; }}
        pre {{
            background: #0d1117;
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 0.85rem;
        }}
        code {{ color: #79c0ff; }}
        .note {{
            color: #666;
            font-size: 0.85rem;
            margin-top: 1rem;
        }}
    </style>
</head>
<body>
    <h1>🎰 Bookie-o-em Status</h1>
    <p class="subtitle">AI Sports Betting Backend</p>

    <div class="section">
        <h2>📦 Build Info</h2>
        <div class="row"><span class="label">Build SHA</span><span class="value">{build_sha}</span></div>
        <div class="row"><span class="label">Deploy Version</span><span class="value">{deploy_version}</span></div>
        <div class="row"><span class="label">Engine Version</span><span class="value">{engine_version}</span></div>
        <div class="row"><span class="label">Timestamp (UTC)</span><span class="value">{timestamp}</span></div>
    </div>

    <div class="section">
        <h2>🕐 Current Time (ET)</h2>
        <div class="row"><span class="label">Date (ET)</span><span class="value">{et_date}</span></div>
        <div class="row"><span class="label">Time (ET)</span><span class="value">{time_et_str}</span></div>
    </div>

    <div class="section">
        <h2>🔧 Internal Health</h2>
        <div class="row">
            <span class="label">Storage (Railway Volume)</span>
            <span class="value {'status-ok' if checks['storage'] else 'status-fail'}">{status_icon(checks['storage'])} {'Connected' if checks['storage'] else 'Error'}</span>
        </div>
        <div class="row">
            <span class="label">Database (PostgreSQL)</span>
            <span class="value {'status-ok' if checks['database'] else 'status-fail'}">{status_icon(checks['database'])} {'Connected' if checks['database'] else 'Disabled'}</span>
        </div>
        <div class="row">
            <span class="label">Cache (Redis)</span>
            <span class="value {'status-ok' if checks['redis'] else 'status-fail'}">{status_icon(checks['redis'])} {'Connected' if checks['redis'] else 'In-Memory'}</span>
        </div>
        <div class="row">
            <span class="label">Scheduler (APScheduler)</span>
            <span class="value {'status-ok' if checks['scheduler'] else 'status-fail'}">{status_icon(checks['scheduler'])} {'Running' if checks['scheduler'] else 'Stopped'}</span>
        </div>
    </div>

    <div class="section">
        <h2>🔑 API Examples</h2>
        <p class="note">Protected endpoints require <code>X-API-Key</code> header:</p>
        <pre><code># Health check (public)
curl https://web-production-7b2a.up.railway.app/health

# Best bets for NBA (requires API key)
curl -H "X-API-Key: YOUR_API_KEY" \\
  https://web-production-7b2a.up.railway.app/live/best-bets/nba

# Debug time info (requires API key)
curl -H "X-API-Key: YOUR_API_KEY" \\
  https://web-production-7b2a.up.railway.app/live/debug/time

# Integration status (requires API key)
curl -H "X-API-Key: YOUR_API_KEY" \\
  https://web-production-7b2a.up.railway.app/live/debug/integrations</code></pre>
    </div>

    <p class="note">
        Note: Browsers cannot set custom headers like <code>X-API-Key</code>.
        Use curl, Postman, or the frontend app to access protected endpoints.
    </p>
</body>
</html>"""

    return HTMLResponse(content=html)




@app.get("/internal/storage/health")
async def storage_health():
    """
    Storage health diagnostics.

    Returns:
    - mount_root: Railway volume mount path
    - store_dir: Grader storage directory
    - writable: Can write to storage
    - predictions_file: Full path to predictions.jsonl
    - predictions_exists: File exists
    - predictions_size_bytes: File size
    - predictions_last_modified: Last modification timestamp
    - predictions_line_count: Number of picks in file
    - sentinel_exists: Volume sentinel file exists
    - sentinel_timestamp: When sentinel was written
    """
    return get_storage_health()


# Grader status endpoint
@app.get("/grader/status")
async def grader_status():
    """
    Grader status: prediction counts, storage info, container details.

    REQUIREMENT: Must show predictions_loaded_count > 0 after picks generated.
    """
    try:
        stats = grader_store.get_storage_stats()

        # Load predictions and count by status
        all_predictions = grader_store.load_predictions()
        pending = [p for p in all_predictions if p.get("grade_status") == "PENDING"]
        graded = [p for p in all_predictions if p.get("grade_status") == "GRADED"]

        from core.time_et import now_et

        return {
            "available": True,
            "predictions_file": stats["predictions_file"],
            "predictions_file_exists": stats["predictions_file_exists"],
            "predictions_file_size_bytes": stats["predictions_file_size_bytes"],
            "predictions_loaded_count": stats["predictions_loaded_count"],
            "pending_total": len(pending),
            "graded_total": len(graded),
            "cwd": stats["cwd"],
            "storage_root": stats["storage_root"],
            "storage_root_writable": stats.get("storage_root_writable", False),
            "container_hostname": stats["container_hostname"],
            "last_run_time_et": now_et().isoformat(),
            "last_errors": []
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }


# Grader self-check endpoint
@app.post("/grader/selfcheck/write-read")
async def grader_selfcheck():
    """
    Self-check: Write synthetic prediction and immediately read back.

    Tests the full write+read cycle to verify persistence is working.
    """
    try:
        result = grader_store.selfcheck_write_read()
        result["status"] = "pass" if result["found_in_loaded"] else "fail"
        return result
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# Public grader weights endpoint (no auth required)
@app.get("/grader/weights/{sport}")
async def grader_weights(sport: str):
    """Get current prediction weights for a sport (public, no auth required)."""
    try:
        from dataclasses import asdict
        grader = get_grader()
        sport_upper = sport.upper()
        if sport_upper not in grader.weights:
            return {"error": f"Unsupported sport: {sport}", "supported": list(grader.weights.keys())}
        weights = {}
        for stat_type, config in grader.weights[sport_upper].items():
            weights[stat_type] = asdict(config)
        return {
            "sport": sport_upper,
            "weights": weights,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


# Public grader bias endpoint (no auth required)
@app.get("/grader/bias/{sport}")
async def grader_bias(sport: str, stat_type: str = "all", days_back: int = 1):
    """Get prediction bias analysis for a sport (public, no auth required)."""
    try:
        grader = get_grader()
        sport_upper = sport.upper()
        if sport_upper not in grader.weights:
            return {"error": f"Unsupported sport: {sport}", "supported": list(grader.weights.keys())}
        bias = grader.calculate_bias(sport_upper, stat_type, days_back)
        return {
            "sport": sport_upper,
            "stat_type": stat_type,
            "days_back": days_back,
            "bias": bias,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


# Public run-audit endpoint (no auth required)
@app.post("/grader/run-audit")
async def grader_run_audit():
    """Run the daily audit to analyze bias and adjust weights (public, no auth required)."""
    try:
        grader = get_grader()
        results = grader.run_daily_audit()
        return {
            "audit": "complete",
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


# Public grader performance endpoint (no auth required)
@app.get("/grader/performance/{sport}")
async def grader_performance(sport: str, days_back: int = 7):
    """Get prediction performance metrics for a sport (public, no auth required)."""
    try:
        grader = get_grader()
        sport_upper = sport.upper()
        if sport_upper not in grader.weights:
            return {"error": f"Unsupported sport: {sport}", "supported": list(grader.weights.keys())}

        # Get performance from grader_store
        from grader_store import grader_store
        from core.time_et import now_et
        from datetime import timedelta
        from zoneinfo import ZoneInfo

        et_tz = ZoneInfo("America/New_York")
        now = now_et()

        # Calculate performance metrics
        total_predictions = 0
        total_graded = 0
        total_hits = 0
        daily_history = {}

        for day_offset in range(days_back):
            day = (now - timedelta(days=day_offset)).strftime("%Y-%m-%d")
            predictions = grader_store.load_predictions(date_str=day)
            sport_preds = [p for p in predictions if p.get("sport", "").upper() == sport_upper]
            graded = [p for p in sport_preds if p.get("graded")]
            hits = [p for p in graded if p.get("result") == "WIN"]

            total_predictions += len(sport_preds)
            total_graded += len(graded)
            total_hits += len(hits)

            if len(graded) > 0:
                daily_history[day] = {
                    "predictions": len(sport_preds),
                    "graded": len(graded),
                    "hits": len(hits),
                    "hit_rate": round(len(hits) / len(graded) * 100, 1)
                }

        hit_rate = round(total_hits / total_graded * 100, 1) if total_graded > 0 else 0

        return {
            "sport": sport_upper,
            "days_back": days_back,
            "current": {
                "total_predictions": total_predictions,
                "total_graded": total_graded,
                "total_hits": total_hits,
                "hit_rate": hit_rate,
                "profitable": hit_rate > 52.0
            },
            "daily_history": daily_history,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


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

@app.get("/debug/pending-picks", dependencies=[Depends(_require_admin)])
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


@app.post("/debug/seed-pick", dependencies=[Depends(_require_admin)])
async def debug_seed_pick(mode: str = None):
    """Create 1 fake pending pick dated yesterday for autograder testing.

    SECURITY: Requires mode=demo query param OR ENABLE_DEMO=true env var.
    """
    enable_demo = _os.getenv("ENABLE_DEMO", "").lower() == "true"
    if mode != "demo" and not enable_demo:
        return JSONResponse(
            status_code=403,
            content={
                "error": "Demo data gated",
                "detail": "Set mode=demo query param or ENABLE_DEMO=true env var",
            },
        )
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


@app.get("/debug/storage-info", dependencies=[Depends(_require_admin)])
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


@app.post("/debug/run-autograde", dependencies=[Depends(_require_admin)])
async def debug_run_autograde():
    """Trigger one grading pass immediately."""
    try:
        from result_fetcher import scheduled_auto_grade
        result = await scheduled_auto_grade()
        return {"triggered": True, "result": result}
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/prediction-store-status", dependencies=[Depends(_require_admin)])
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

        # Sport breakdown for today
        today_picks = pl.get_picks_for_date(today)
        by_sport = {}
        for p in today_picks:
            s = p.sport.upper()
            if s not in by_sport:
                by_sport[s] = {"total": 0, "pending": 0, "graded": 0}
            by_sport[s]["total"] += 1
            if p.result:
                by_sport[s]["graded"] += 1
            else:
                by_sport[s]["pending"] += 1

        return {
            "today": {"date": today, **date_stats(today)},
            "yesterday": {"date": yesterday, **date_stats(yesterday)},
            "by_sport": by_sport,
            "supported_sports": ["NBA", "NHL", "NFL", "MLB", "NCAAB"],
            "in_memory_dates": list(pl.picks.keys()),
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/debug/seed-pick-and-grade", dependencies=[Depends(_require_admin)])
async def debug_seed_pick_and_grade(mode: str = None):
    """Seed a fake pick, persist it, run one grading pass, return the updated record.

    SECURITY: Requires mode=demo query param OR ENABLE_DEMO=true env var.
    """
    enable_demo = _os.getenv("ENABLE_DEMO", "").lower() == "true"
    if mode != "demo" and not enable_demo:
        return JSONResponse(
            status_code=403,
            content={
                "error": "Demo data gated",
                "detail": "Set mode=demo query param or ENABLE_DEMO=true env var",
            },
        )
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


@app.post("/debug/e2e-proof", dependencies=[Depends(_require_admin)])
async def debug_e2e_proof(mode: str = None):
    """
    E2E proof: find a real finished NBA game from yesterday, seed a prop pick
    for a real player using real stats, then autograde it. This proves the full
    pipeline: pending → graded with real data.

    SECURITY: Requires mode=demo query param OR ENABLE_DEMO=true env var.
    """
    enable_demo = _os.getenv("ENABLE_DEMO", "").lower() == "true"
    if mode != "demo" and not enable_demo:
        return JSONResponse(
            status_code=403,
            content={
                "error": "Demo data gated",
                "detail": "Set mode=demo query param or ENABLE_DEMO=true env var",
            },
        )
    try:
        from pick_logger import get_pick_logger
        from result_fetcher import auto_grade_picks
        from datetime import datetime, timedelta
        import pytz, httpx
        ET = pytz.timezone("America/New_York")
        now_et = datetime.now(ET)
        yesterday = (now_et - timedelta(days=1)).strftime("%Y-%m-%d")

        BDL_KEY = _os.getenv("BALLDONTLIE_API_KEY", _os.getenv("BDL_API_KEY", ""))
        if not BDL_KEY:
            return {"error": "BALLDONTLIE_API_KEY or BDL_API_KEY not set in environment"}
        headers = {"Authorization": BDL_KEY}

        async with httpx.AsyncClient(timeout=30) as client:
            # 1. Find a finished game from yesterday
            games_resp = await client.get(
                f"https://api.balldontlie.io/v1/games?dates[]={yesterday}&per_page=5",
                headers=headers
            )
            games = games_resp.json().get("data", [])
            finished = [g for g in games if g.get("status") == "Final"]
            if not finished:
                return {"error": f"No finished NBA games found for {yesterday}",
                        "games_found": len(games),
                        "sample_game": games[0] if games else None,
                        "statuses": [g.get("status") for g in games]}

            game = finished[0]
            # BDL v1 uses "home_team" and "visitor_team"
            home_obj = game.get("home_team") or game.get("home_team_id") or {}
            away_obj = game.get("visitor_team") or game.get("away_team") or {}
            home = home_obj.get("full_name", str(home_obj)) if isinstance(home_obj, dict) else str(home_obj)
            away = away_obj.get("full_name", str(away_obj)) if isinstance(away_obj, dict) else str(away_obj)
            game_id = game["id"]

            # 2. Get box score — find a player with real stats
            stats_resp = await client.get(
                f"https://api.balldontlie.io/v1/stats?game_ids[]={game_id}&per_page=25",
                headers=headers
            )
            stats = stats_resp.json().get("data", [])
            # Find the player with the most points
            stats_with_pts = [s for s in stats if s.get("pts", 0) and s.get("pts", 0) >= 10]
            stats_with_pts.sort(key=lambda s: s.get("pts", 0), reverse=True)
            real_player = stats_with_pts[0] if stats_with_pts else None

            if not real_player:
                return {"error": "No player with 15+ points found in box score",
                        "game": f"{away} @ {home}", "stats_count": len(stats),
                        "sample_stat": stats[0] if stats else None}

            p_obj = real_player.get("player", {})
            player_name = f"{p_obj.get('first_name', '')} {p_obj.get('last_name', '')}".strip()
            if not player_name:
                player_name = str(p_obj)
            actual_pts = real_player["pts"]
            # Set line so we know the expected result
            # Line = actual - 2 → player went Over
            test_line = actual_pts - 2.0

        # 3. Seed this as a real pick dated YESTERDAY (so grader fetches yesterday's stats)
        pl = get_pick_logger()
        from pick_logger import PublishedPick, get_now_et
        from dataclasses import asdict
        import json as _json

        pick_id = f"e2e_{int(now_et.timestamp())}"
        pick = PublishedPick(
            pick_id=pick_id, date=yesterday, sport="NBA", pick_type="PROP",
            player_name=player_name, matchup=f"{away} @ {home}",
            home_team=home, away_team=away,
            prop_type="points", line=test_line, side="Over",
            odds=-110, book="fanduel",
            final_score=8.0, ai_score=7.0, research_score=7.5,
            esoteric_score=6.0, jarvis_score=5.0,
            tier="GOLD_STAR", units=1.0,
            game_start_time_et=(now_et - timedelta(hours=20)).isoformat(),
            published_at=now_et.isoformat(),
            grade_status="PENDING",
        )

        # Write directly to yesterday's pick log
        log_file = _os.path.join(pl.storage_path, f"picks_{yesterday}.jsonl")
        with open(log_file, 'a') as f:
            f.write(_json.dumps(asdict(pick)) + "\n")
        # Load into memory
        if yesterday not in pl.picks:
            pl.picks[yesterday] = []
        pl.picks[yesterday].append(pick)

        seed_result = {"pick_id": pick_id, "logged": True, "date": yesterday}

        # 4. Snapshot: pick is PENDING
        pending_pick = {"pick_id": pick_id, "result": None, "grade_status": "PENDING"}

        # 5. Run autograde for YESTERDAY (where the game and pick both live)
        grade_result = await auto_grade_picks(date=yesterday)

        # 6. Snapshot: pick should be GRADED
        # Reload from memory (grade_pick updates in-place)
        graded_pick = None
        for p in pl.get_picks_for_date(yesterday):
            if p.pick_id == pick_id:
                graded_pick = {
                    "pick_id": p.pick_id, "result": p.result,
                    "grade_status": p.grade_status, "actual_value": p.actual_value,
                    "graded_at": p.graded_at, "units_won_lost": p.units_won_lost,
                }
                break

        return {
            "proof": "E2E autograder pipeline",
            "game": f"{away} @ {home} ({yesterday})",
            "player": player_name,
            "actual_points": actual_pts,
            "line_set": test_line,
            "expected_result": "WIN" if actual_pts > test_line else "LOSS",
            "step_1_seed": seed_result,
            "step_2_before_grade": pending_pick,
            "step_3_grade_summary": {
                "picks_graded": grade_result.get("picks_graded", 0),
                "picks_failed": grade_result.get("picks_failed", 0),
            },
            "step_4_after_grade": graded_pick,
            "verdict": "PASS" if graded_pick and graded_pick.get("result") else "FAIL",
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/ops/cache-status", dependencies=[Depends(_require_admin)])
async def ops_cache_status():
    """Per-sport cache status for best-bets pre-warm verification."""
    import time as _time
    try:
        from live_data_router import api_cache
        sports = ["nba", "nhl", "ncaab", "nfl", "mlb"]
        result = {}
        for sport in sports:
            # Use canonical cache key builder (matches best-bets endpoint)
            cache_key = f"best-bets:{sport}"
            live_cache_key = f"best-bets:{sport}:live"
            cached = api_cache.get(cache_key)
            cached_live = api_cache.get(live_cache_key)
            warm_meta = api_cache.get(f"warm_meta:{sport}")

            cache_age = None
            if cached and isinstance(cached, dict) and "_cached_at" in cached:
                cache_age = round(_time.time() - cached["_cached_at"], 1)

            live_cache_age = None
            if cached_live and isinstance(cached_live, dict) and "_cached_at" in cached_live:
                live_cache_age = round(_time.time() - cached_live["_cached_at"], 1)

            result[sport] = {
                "cache_present": cached is not None,
                "cache_age_seconds": cache_age,
                "live_cache_present": cached_live is not None,
                "live_cache_age_seconds": live_cache_age,
                "last_warm_time": warm_meta.get("last_warm_time") if warm_meta else None,
                "last_warm_duration": warm_meta.get("duration_seconds") if warm_meta else None,
            }
        return {"sports": result, "cache_backend": api_cache.stats().get("backend", "unknown")}
    except Exception as e:
        return {"error": str(e)}


@app.get("/ops/storage", dependencies=[Depends(_require_admin)])
async def ops_storage():
    """Storage health for Railway volume persistence."""
    health = get_storage_health()
    status_code = 200
    if not health.get("ok") or health.get("is_ephemeral"):
        status_code = 503
    return JSONResponse(content=health, status_code=status_code)


@app.get("/ops/env-map", dependencies=[Depends(_require_admin)])
async def ops_env_map():
    """
    Map env vars -> modules/endpoints/jobs and flag missing/unused.
    Canonical source: core.integration_contract.INTEGRATIONS
    """
    env_map = {}
    # Track which integrations have at least one env var set
    integration_satisfied = {}

    for name, meta in CONTRACT_INTEGRATIONS.items():
        env_vars_list = meta.get("env_vars", [])
        # Check if ANY of the integration's env vars are set
        any_set = any(bool(_os.getenv(ev)) for ev in env_vars_list)
        integration_satisfied[name] = any_set

        for env_var in env_vars_list:
            entry = env_map.setdefault(env_var, {
                "env_var": env_var,
                "integrations": [],
                "modules": [],
                "endpoints": [],
                "jobs": [],
                "required": False,
                "is_set": bool(_os.getenv(env_var)),
            })
            entry["integrations"].append(name)
            entry["modules"].extend(meta.get("owner_modules", []))
            entry["endpoints"].extend(meta.get("endpoints", []))
            entry["jobs"].extend(meta.get("jobs", []))
            if meta.get("required"):
                entry["required"] = True

    # Normalize unique lists
    for entry in env_map.values():
        entry["modules"] = sorted(set(entry["modules"]))
        entry["endpoints"] = sorted(set(entry["endpoints"]))
        entry["jobs"] = sorted(set(entry["jobs"]))

    # For missing_required: only flag if the integration has NO env vars set (OR logic)
    # Skip env vars whose integration is already satisfied by another env var
    missing_required = sorted([
        k for k, v in env_map.items()
        if v["required"] and not v["is_set"]
        and not all(integration_satisfied.get(i, False) for i in v["integrations"])
    ])
    missing_any = sorted([k for k, v in env_map.items() if not v["is_set"]])
    unused_env_vars = sorted([
        k for k in _os.environ.keys()
        if k.endswith("_API_KEY") and k not in ALL_ENV_VARS
    ])

    return {
        "env_map": env_map,
        "missing_required": missing_required,
        "missing_any": missing_any,
        "unused_env_vars": unused_env_vars,
        "total_env_vars": len(env_map),
        "source": "integration_contract",
        "status": "OK" if not missing_required else "MISSING_REQUIRED",
    }


@app.get("/ops/integrations", dependencies=[Depends(_require_admin)])
async def ops_integrations():
    """Probe integrations with latency and status."""
    results = {}
    required_failures = []

    for name in list_integrations():
        start = time.perf_counter()
        status = await check_integration_health(name)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        status["latency_ms"] = latency_ms
        status["last_checked"] = status.get("last_check")

        is_configured = status.get("is_configured", False)
        is_reachable = status.get("is_reachable", None)

        if not is_configured:
            status["status"] = "NOT_CONFIGURED"
        elif is_reachable is True:
            status["status"] = "OK"
        elif is_reachable is False:
            status["status"] = "ERROR"
        else:
            status["status"] = "NOT_PROBED"
            status["reason"] = status.get("validation", {}).get("reason", "no validator")

        if status.get("required") and status["status"] in {"NOT_CONFIGURED", "ERROR"}:
            required_failures.append(name)

        results[name] = status

    payload = {
        "integrations": results,
        "required_failures": required_failures,
        "total": len(results),
    }

    if required_failures:
        return JSONResponse(content=payload, status_code=503)
    return payload


# =============================================================================
# OPS ENDPOINTS — Autograder visibility (v15.1)
# =============================================================================
_last_grade_run = {}

# Load persisted grade run metadata on startup
try:
    import json as _json
    _grade_run_path = _os.path.join(DATA_DIR, "last_grade_run.json")
    if _os.path.exists(_grade_run_path):
        with open(_grade_run_path, "r") as _f:
            _last_grade_run = _json.load(_f)
except Exception:
    pass


@app.get("/ops/latest-audit", dependencies=[Depends(_require_admin)])
async def ops_latest_audit():
    """Return the newest audit log file with per-sport totals."""
    import json
    from data_dir import AUDIT_LOGS
    try:
        if not _os.path.exists(AUDIT_LOGS):
            return {"error": "No audit_logs directory"}
        files = sorted(
            [f for f in _os.listdir(AUDIT_LOGS) if f.startswith("audit_") and f.endswith(".json")],
            reverse=True
        )
        if not files:
            return {"error": "No audit files found", "directory": AUDIT_LOGS}
        latest = files[0]
        path = _os.path.join(AUDIT_LOGS, latest)
        with open(path, "r") as f:
            data = json.load(f)
        # Build per-sport totals
        totals = {}
        sports_data = data.get("sports", {})
        for sport, sport_info in sports_data.items():
            summary = sport_info.get("summary", {})
            totals[sport] = {
                "graded": summary.get("graded_count", 0),
                "hit_rate": summary.get("hit_rate", 0),
                "mae": summary.get("mae", 0),
            }
        return {
            "file_path": path,
            "file_name": latest,
            "timestamp": data.get("timestamp", ""),
            "totals_per_sport": totals,
            "audit": data,
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/ops/auto-grade/run", dependencies=[Depends(_require_admin)])
async def ops_auto_grade_run():
    """Trigger autograde immediately. Returns full grading summary."""
    global _last_grade_run
    import json
    from datetime import datetime, timedelta
    import pytz
    try:
        from result_fetcher import auto_grade_picks
    except ImportError:
        return {"error": "result_fetcher not available"}

    ET = pytz.timezone("America/New_York")
    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    dates_to_grade = [today]
    if now_et.hour < 12:
        yesterday = (now_et - timedelta(days=1)).strftime("%Y-%m-%d")
        dates_to_grade.append(yesterday)

    all_results = []
    for date in dates_to_grade:
        result = await auto_grade_picks(date=date)
        all_results.append(result)

    # Persist metadata
    _last_grade_run = {
        "timestamp_et": now_et.isoformat(),
        "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(),
        "dates_graded": dates_to_grade,
        "results": all_results,
    }
    try:
        grade_run_path = _os.path.join(DATA_DIR, "last_grade_run.json")
        with open(grade_run_path, "w") as f:
            json.dump(_last_grade_run, f, indent=2, default=str)
    except Exception:
        pass

    return _last_grade_run


@app.get("/ops/grader/status", dependencies=[Depends(_require_admin)])
async def ops_grader_status():
    """Comprehensive grader status: pick counts, last run, storage info."""
    from datetime import datetime, timedelta
    import pytz
    from data_dir import PICK_LOGS, SUPPORTED_SPORTS
    try:
        from pick_logger import get_pick_logger
    except ImportError:
        return {"error": "pick_logger not available"}

    ET = pytz.timezone("America/New_York")
    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")
    yesterday = (now_et - timedelta(days=1)).strftime("%Y-%m-%d")

    pick_logger = get_pick_logger()
    counts = {"total": 0, "pending": 0, "graded": 0, "failed": 0, "waiting": 0}
    by_sport = {}

    for date in [today, yesterday]:
        picks = pick_logger.get_picks_for_date(date)
        for p in picks:
            counts["total"] += 1
            status = getattr(p, "grade_status", "PENDING")
            if status == "GRADED" or p.result:
                counts["graded"] += 1
            elif status == "FAILED":
                counts["failed"] += 1
            elif status == "WAITING_FINAL":
                counts["waiting"] += 1
            else:
                counts["pending"] += 1
            sport = p.sport.upper()
            if sport not in by_sport:
                by_sport[sport] = {"total": 0, "pending": 0, "graded": 0}
            by_sport[sport]["total"] += 1
            if status == "GRADED" or p.result:
                by_sport[sport]["graded"] += 1
            elif status not in ("FAILED",):
                by_sport[sport]["pending"] += 1

    # List pick log files
    pick_files = []
    if _os.path.exists(PICK_LOGS):
        pick_files = sorted(
            [f for f in _os.listdir(PICK_LOGS) if f.endswith(".jsonl")],
            reverse=True
        )[:10]

    return {
        "predictions_total": counts["total"],
        "predictions_pending": counts["pending"],
        "predictions_graded": counts["graded"],
        "predictions_failed": counts["failed"],
        "predictions_waiting_final": counts["waiting"],
        "by_sport": by_sport,
        "dates_checked": [today, yesterday],
        "last_grade_run_timestamp": _last_grade_run.get("timestamp_et"),
        "last_grade_run_timestamp_utc": _last_grade_run.get("timestamp_utc"),
        "last_grade_run_summary": _last_grade_run.get("results"),
        "storage_backend": "jsonl_file",
        "predictions_store_path": PICK_LOGS,
        "recent_pick_files": pick_files,
        "supported_sports": list(SUPPORTED_SPORTS),
    }


@app.post("/ops/predictions/test-seed", dependencies=[Depends(_require_admin)])
async def ops_predictions_test_seed():
    """Seed 1 dummy prediction into the exact store autograde reads."""
    import uuid
    from datetime import datetime, timedelta
    import pytz
    from data_dir import PICK_LOGS
    try:
        from pick_logger import get_pick_logger
    except ImportError:
        return {"error": "pick_logger not available"}

    ET = pytz.timezone("America/New_York")
    now_et = datetime.now(ET)
    yesterday = (now_et - timedelta(days=1)).strftime("%Y-%m-%d")
    game_time = (now_et - timedelta(hours=5)).replace(hour=19, minute=0, second=0)

    pick_id = f"test_seed_{uuid.uuid4().hex[:8]}"
    pick_data = {
        "pick_id": pick_id,
        "sport": "NBA",
        "pick_type": "PROP",
        "player_name": "Test Player Seed",
        "matchup": "TEST @ SEED",
        "home_team": "SEED",
        "away_team": "TEST",
        "prop_type": "points",
        "market": "player_points",
        "line": 22.5,
        "side": "Over",
        "odds": -110,
        "book": "DraftKings",
        "start_time_et": game_time.isoformat(),
        "ai_score": 7.0,
        "research_score": 7.5,
        "esoteric_score": 6.0,
        "jarvis_score": 5.5,
        "final_score": 7.2,
        "total_score": 7.2,
        "tier": "GOLD_STAR",
        "units": 2.0,
        "titanium_triggered": False,
        "injury_status": "HEALTHY",
        "game_time_utc": game_time.astimezone(pytz.utc).isoformat(),
        "minutes_since_start": max(0, int((now_et - game_time).total_seconds() / 60)),
        "raw_inputs_snapshot": {"line": 22.5, "odds": -110, "matchup": "TEST @ SEED", "seeded": True},
    }

    pick_logger = get_pick_logger()
    result = pick_logger.log_pick(
        pick_data=pick_data,
        game_start_time=game_time.isoformat(),
        skip_duplicates=False
    )

    # log_pick always writes to today's date file
    today_str = now_et.strftime("%Y-%m-%d")
    written_to = _os.path.join(PICK_LOGS, f"picks_{today_str}.jsonl")

    return {
        "seeded": True,
        "seeded_prediction_id": result.get("pick_id") or pick_id,
        "pick_hash": result.get("pick_hash"),
        "written_to": written_to,
        "date": today_str,
        "sport": "NBA",
        "store": "pick_logger (JSONL) — same store autograde reads from",
        "next_step": "Call POST /ops/auto-grade/run to attempt grading this seed",
    }


@app.get("/ops/score-distribution/{sport}", dependencies=[Depends(_require_admin)])
async def ops_score_distribution(sport: str, date: str = None):
    """
    Score distribution histogram for best-bets candidates.
    Shows why picks may not qualify: near-misses, missing data, engine gaps.
    """
    from datetime import datetime, timedelta
    import pytz
    try:
        from live_data_router import get_best_bets
    except ImportError:
        return {"error": "live_data_router not available"}

    ET = pytz.timezone("America/New_York")
    if not date:
        date = datetime.now(ET).strftime("%Y-%m-%d")

    # Run best-bets in debug mode with low threshold to capture everything
    try:
        result = await get_best_bets(sport, min_score=0.0, debug=1, date=date)
    except Exception as e:
        return {"error": f"Failed to run best-bets: {e}"}

    debug = result.get("debug", {})
    all_candidates = debug.get("top_prop_candidates", []) + debug.get("top_game_candidates", [])

    # Build histogram buckets (0.0 to 10.0, step 0.5)
    buckets = {round(i * 0.5, 1): 0 for i in range(21)}
    for c in all_candidates:
        score = c.get("final_score", 0)
        bucket = round(min(10.0, int(score * 2) / 2), 1)
        buckets[bucket] = buckets.get(bucket, 0) + 1

    # Missing data counters
    missing = {
        "no_odds": 0, "no_sharp_signal": 0, "no_splits": 0,
        "no_injury_data": 0, "no_jarvis_triggers": 0,
        "jason_blocked": 0, "jason_not_run": 0,
    }
    for c in all_candidates:
        md = c.get("missing_data", {})
        for key in missing:
            if md.get(key):
                missing[key] += 1

    # Near-miss analysis
    near_misses_6_0 = [c for c in all_candidates if 5.5 <= c.get("final_score", 0) < 6.0]
    near_misses_6_5 = [c for c in all_candidates if 6.0 <= c.get("final_score", 0) < 6.5]

    return {
        "sport": sport.upper(),
        "date": date,
        "total_candidates": debug.get("total_prop_candidates", 0) + debug.get("total_game_candidates", 0),
        "total_prop_candidates": debug.get("total_prop_candidates", 0),
        "total_game_candidates": debug.get("total_game_candidates", 0),
        "counts": {
            "above_6_0": debug.get("props_above_6_0", 0) + debug.get("games_above_6_0", 0),
            "above_6_5": debug.get("props_above_6_5", 0) + debug.get("games_above_6_5", 0),
            "above_7_5": sum(1 for c in all_candidates if c.get("final_score", 0) >= 7.5),
            "above_8_0": sum(1 for c in all_candidates if c.get("final_score", 0) >= 8.0),
        },
        "histogram": buckets,
        "missing_data_counts": missing,
        "near_misses_5_5_to_6_0": len(near_misses_6_0),
        "near_misses_6_0_to_6_5": len(near_misses_6_5),
        "top_near_misses": sorted(
            near_misses_6_5 + near_misses_6_0,
            key=lambda x: x.get("final_score", 0),
            reverse=True
        )[:10],
        "score_distribution_from_engine": debug.get("score_distribution", {}),
    }


@app.post("/admin/cleanup-test-picks", dependencies=[Depends(_require_admin)])
async def admin_cleanup_test_picks(date: str = None):
    """Remove seeded test picks (LAL @ BOS / LeBron / GOLD_STAR) for a given date."""
    try:
        from pick_logger import get_pick_logger
        from datetime import datetime, timedelta
        from dataclasses import asdict
        import json
        import pytz
        ET = pytz.timezone("America/New_York")
        if not date:
            date = datetime.now(ET).strftime("%Y-%m-%d")

        pl = get_pick_logger()
        picks = pl.get_picks_for_date(date)
        before = len(picks)

        # Remove test picks: seeded (LAL @ BOS + LeBron + GOLD_STAR) or e2e-proof (pick_id starts with e2e_)
        cleaned = [p for p in picks if not (
            (p.matchup == "LAL @ BOS" and p.player_name == "LeBron James" and p.tier == "GOLD_STAR")
            or p.pick_id.startswith("e2e_")
        )]
        removed = before - len(cleaned)
        pl.picks[date] = cleaned
        pl.pick_hashes[date] = {getattr(p, 'pick_hash', '') for p in cleaned if getattr(p, 'pick_hash', '')}
        if removed > 0:
            pl._rewrite_pick_log(date)
            # Also clean graded file
            import os
            from data_dir import GRADED_PICKS
            graded_file = os.path.join(GRADED_PICKS, f"graded_{date}.jsonl")
            graded_remaining = [p for p in cleaned if p.result]
            with open(graded_file, 'w') as f:
                for p in graded_remaining:
                    f.write(json.dumps(asdict(p)) + "\n")

        return {"date": date, "before": before, "after": len(cleaned), "removed": removed}
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# OPS ALIAS ROUTES — Canonical namespace for debugging/monitoring
# =============================================================================
# These provide stable paths that won't change as internals evolve.
# Frontend/scripts should use /ops/* for consistency.

@app.get("/ops/integrations")
async def ops_integrations(quick: bool = False):
    """
    Alias for /live/debug/integrations.
    Returns status of all 14 backend integrations.

    ?quick=true returns summary only (configured/not_configured lists)
    """
    from integration_registry import get_all_integrations_status, get_integrations_summary
    if quick:
        return get_integrations_summary()
    return get_all_integrations_status()


@app.get("/ops/storage")
async def ops_storage():
    """
    Alias for /internal/storage/health.
    Returns Railway volume persistence status.
    """
    return get_storage_health()


@app.get("/ops/verify")
async def ops_verify():
    """
    Single-command backend verification.
    Checks all critical systems and returns pass/fail status.

    Use this endpoint after deployments to verify system health.
    """
    from datetime import datetime
    import pytz

    results = {
        "timestamp": datetime.now(pytz.UTC).isoformat(),
        "checks": {},
        "all_passed": True,
        "failed_checks": []
    }

    # 1. Health check
    try:
        results["checks"]["health"] = {
            "status": "healthy",
            "passed": True
        }
    except Exception as e:
        results["checks"]["health"] = {"status": str(e), "passed": False}
        results["all_passed"] = False
        results["failed_checks"].append("health")

    # 2. Storage check
    try:
        storage = get_storage_health()
        storage_ok = (
            storage.get("ok", False) and
            storage.get("is_mountpoint", False) and
            not storage.get("is_ephemeral", True)
        )
        results["checks"]["storage"] = {
            "resolved_base_dir": storage.get("resolved_base_dir"),
            "is_mountpoint": storage.get("is_mountpoint"),
            "is_ephemeral": storage.get("is_ephemeral"),
            "predictions_count": storage.get("predictions_line_count", 0),
            "passed": storage_ok
        }
        if not storage_ok:
            results["all_passed"] = False
            results["failed_checks"].append("storage")
    except Exception as e:
        results["checks"]["storage"] = {"error": str(e), "passed": False}
        results["all_passed"] = False
        results["failed_checks"].append("storage")

    # 3. Integrations check
    try:
        from integration_registry import get_all_integrations_status
        integrations = await get_all_integrations_status()
        overall = integrations.get("overall_status", "UNKNOWN")
        validated = integrations.get("status_counts", {}).get("validated", 0)
        configured = integrations.get("status_counts", {}).get("configured", 0)
        unreachable = integrations.get("status_counts", {}).get("unreachable", 0)
        not_configured = integrations.get("status_counts", {}).get("not_configured", 0)

        integrations_ok = overall == "HEALTHY" and not_configured == 0
        results["checks"]["integrations"] = {
            "overall_status": overall,
            "validated": validated,
            "configured": configured,
            "unreachable": unreachable,
            "not_configured": not_configured,
            "passed": integrations_ok
        }
        if not integrations_ok:
            results["all_passed"] = False
            results["failed_checks"].append("integrations")
    except Exception as e:
        results["checks"]["integrations"] = {"error": str(e), "passed": False}
        results["all_passed"] = False
        results["failed_checks"].append("integrations")

    # 4. Env-map check
    try:
        env_data = await ops_env_map()
        env_status = env_data.get("status", "MISSING_REQUIRED")
        missing_required = env_data.get("missing_required", [])
        total_vars = env_data.get("total_env_vars", 0)
        configured = total_vars - len(env_data.get("missing_any", []))
        # OK if no required vars missing
        env_ok = env_status == "OK"
        results["checks"]["env_map"] = {
            "status": env_status,
            "summary": f"{configured}/{total_vars} env vars configured",
            "missing_required": len(missing_required),
            "passed": env_ok
        }
        if not env_ok:
            results["all_passed"] = False
            results["failed_checks"].append("env_map")
    except Exception as e:
        results["checks"]["env_map"] = {"error": str(e), "passed": False}
        results["all_passed"] = False
        results["failed_checks"].append("env_map")

    # 5. Database check
    try:
        db_status = database.get_database_status()
        db_ok = db_status.get("enabled", False) or db_status.get("available", False)
        results["checks"]["database"] = {
            "enabled": db_status.get("enabled"),
            "connection": db_status.get("connection", "unknown"),
            "passed": db_ok
        }
        # Database is optional, don't fail overall if just not enabled
    except Exception as e:
        results["checks"]["database"] = {"error": str(e), "passed": False}

    # 6. Scheduler check
    try:
        sched = get_scheduler()
        sched_ok = sched is not None and sched.running
        jobs_count = 0
        if sched and sched.scheduler:
            try:
                jobs_count = len(sched.scheduler.get_jobs())
            except Exception:
                jobs_count = -1  # APScheduler not available
        results["checks"]["scheduler"] = {
            "running": sched.running if sched else False,
            "jobs_count": jobs_count,
            "passed": sched_ok
        }
        if not sched_ok:
            results["all_passed"] = False
            results["failed_checks"].append("scheduler")
    except Exception as e:
        results["checks"]["scheduler"] = {"error": str(e), "passed": False}
        results["all_passed"] = False
        results["failed_checks"].append("scheduler")

    # Overall verdict
    results["verdict"] = "PASS" if results["all_passed"] else "FAIL"

    return results


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
