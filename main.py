"""
Bookie-o-em v14.1 - PRODUCTION HARDENED
FastAPI Backend Server

Features:
- v10.1 Research-optimized weights (+94.40u YTD)
- Standalone Esoteric Edge (Gematria/Numerology/Astro)
- v10.4 SCALAR-SAVANT (6 modules)
- v11.0 OMNI-GLITCH (6 modules)
- v13.0 GANN PHYSICS (3 modules)
- v14.0 NOOSPHERE VELOCITY (3 modules - MAIN MODEL)
- v14.1 Production hardening (retries, logging, rate-limit handling)

Total: 18 esoteric modules
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from fastapi.responses import Response
from live_data_router import router as live_router, close_shared_client
import database
from daily_scheduler import scheduler_router, init_scheduler, get_scheduler
from metrics import get_metrics_response, get_metrics_status, PROMETHEUS_AVAILABLE

app = FastAPI(
    title="Bookie-o-em API",
    description="AI Sports Prop Betting Service - v14.1 PRODUCTION HARDENED",
    version="14.1"
)

# CORS - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(live_router)
app.include_router(scheduler_router)

# Startup event - initialize database and scheduler
@app.on_event("startup")
async def startup_event():
    database.init_database()
    # Initialize and start daily scheduler
    scheduler = init_scheduler()
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

    today = date.today()
    reading = get_daily_esoteric_reading(today)

    # Build void moon periods array
    void_moon_periods = []
    if reading["void_moon"]["is_void"]:
        void_moon_periods.append({
            "start": reading["void_moon"]["void_start"],
            "end": reading["void_moon"]["void_end"]
        })

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
        "recommendation": reading["recommendation"]
    }

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
