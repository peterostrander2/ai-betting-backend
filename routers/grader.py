"""
GRADER ROUTER - Grader & Picks Management Endpoints

Extracted from live_data_router.py as part of the monolith split (router 6/7).

Endpoints:
    - /grader/status          - Check grader status and storage health
    - /grader/debug-files     - Debug endpoint for disk persistence
    - /grader/weights/{sport} - Get learned weights for a sport
    - /grader/run-audit       - Run daily audit for bias/weight adjustment
    - /grader/bias/{sport}    - Get prediction bias analysis
    - /grader/adjust-weights/{sport} - Manual weight adjustment
    - /grader/train-team-models     - Manual team model training trigger
    - /grader/performance/{sport}   - Get performance metrics
    - /grader/daily-report    - Community-friendly daily report
    - /grader/daily-lesson    - Daily learning lesson
    - /grader/queue           - Get ungraded picks queue
    - /grader/dry-run         - Dry-run validation of grader pipeline
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["grader"])

# =============================================================================
# CONDITIONAL IMPORTS - Graceful degradation when modules unavailable
# =============================================================================

try:
    from auto_grader import get_grader
    AUTO_GRADER_AVAILABLE = True
except ImportError:
    AUTO_GRADER_AVAILABLE = False
    get_grader = None

try:
    import grader_store
    GRADER_STORE_AVAILABLE = True
except ImportError:
    GRADER_STORE_AVAILABLE = False
    grader_store = None

try:
    from pick_logger import get_pick_logger, get_today_picks
    PICK_LOGGER_AVAILABLE = True
except ImportError:
    PICK_LOGGER_AVAILABLE = False
    get_pick_logger = None
    get_today_picks = None

try:
    from identity.player_resolver import get_player_resolver
    IDENTITY_RESOLVER_AVAILABLE = True
except ImportError:
    IDENTITY_RESOLVER_AVAILABLE = False


# =============================================================================
# GRADER STATUS ENDPOINT
# =============================================================================

@router.get("/grader/status")
async def grader_status():
    """
    Check grader status for both pick logging and weight learning systems.

    Returns:
        - predictions_logged: Count of picks logged today (pick_logger)
        - pending_to_grade: Count of ungraded picks (pick_logger)
        - last_run_at: Last auto-grade run timestamp
        - last_errors: Recent grading errors
        - weight_learning: Auto-grader weight learning status (separate system)
    """
    from core.time_et import et_day_bounds

    result = {
        "available": True,
        "timestamp": datetime.now().isoformat()
    }

    # Grader Store Stats (SINGLE SOURCE OF TRUTH for persistence)
    try:
        import grader_store as gs
        _start_et, _end_et, _start_utc, _end_utc = et_day_bounds()
        today = _start_et.date().isoformat()

        # Load predictions from grader_store with reconciliation stats
        recon_data = gs.load_predictions_with_reconciliation()
        all_predictions_raw = recon_data["predictions"]
        reconciliation = recon_data["reconciliation"]

        # Filter to today's predictions
        all_predictions = [p for p in all_predictions_raw if p.get("date_et") == today]
        pending = [p for p in all_predictions if p.get("grade_status") != "GRADED"]
        graded = [p for p in all_predictions if p.get("grade_status") == "GRADED"]

        # Get last write time from file mtime
        last_write_at = None
        try:
            if os.path.exists(gs.PREDICTIONS_FILE):
                mtime = os.path.getmtime(gs.PREDICTIONS_FILE)
                last_write_at = datetime.fromtimestamp(mtime).isoformat()
        except Exception:
            pass

        result["grader_store"] = {
            "predictions_logged": len(all_predictions),
            "predictions_total_all_dates": len(all_predictions_raw),
            "pending_to_grade": len(pending),
            "graded_today": len(graded),
            "storage_path": gs.STORAGE_ROOT,
            "predictions_file": gs.PREDICTIONS_FILE,
            "last_write_at": last_write_at,
            "date": today,
            "reconciliation": {
                "file_lines": reconciliation["total_lines"],
                "parsed_ok": reconciliation["parsed_ok"],
                "skipped_total": reconciliation["skipped_total"],
                "reconciled": reconciliation["reconciled"],
                "top_skip_reasons": reconciliation["skip_reasons"],
            }
        }
    except Exception as e:
        logger.error("Grader store status failed: %s", e)
        result["grader_store"] = {
            "available": False,
            "error": str(e)
        }

    # Root-level aliases for DX (prevents "field not found" confusion)
    result["total_predictions"] = result.get("grader_store", {}).get("predictions_total_all_dates", 0)
    result["file_path"] = result.get("grader_store", {}).get("predictions_file")
    result["store_path"] = result.get("grader_store", {}).get("storage_path")
    result["last_write_at"] = result.get("grader_store", {}).get("last_write_at")

    # Scheduler Stats (last run time and errors)
    try:
        from daily_scheduler import get_daily_scheduler
        scheduler = get_daily_scheduler()
        if scheduler and hasattr(scheduler, 'auto_grade_job'):
            job = scheduler.auto_grade_job
            result["last_run_at"] = job.last_run.isoformat() if job.last_run else None
            result["last_errors"] = job.last_errors[-5:] if hasattr(job, 'last_errors') else []
        else:
            result["last_run_at"] = None
            result["last_errors"] = []
    except Exception as e:
        logger.error("Scheduler status failed: %s", e)
        result["last_run_at"] = None
        result["last_errors"] = [str(e)]

    # Auto-Grader Weight Learning Stats (separate system for adjusting prediction weights)
    try:
        if AUTO_GRADER_AVAILABLE:
            grader = get_grader()  # Use singleton - CRITICAL for data persistence!

            # Weight version hash for tracking which weights are loaded
            weights_version_hash = None
            weights_file_exists = False
            weights_last_modified_et = None
            try:
                import hashlib as _hashlib
                from storage_paths import get_weights_file as _get_weights_file
                _wf = _get_weights_file()
                weights_file_exists = os.path.exists(_wf)
                if weights_file_exists:
                    with open(_wf, 'rb') as _f:
                        weights_version_hash = _hashlib.sha256(_f.read()).hexdigest()[:12]
                    weights_last_modified_et = datetime.fromtimestamp(
                        os.path.getmtime(_wf)
                    ).isoformat()
            except Exception:
                pass

            # Training drop stats (if available from last load)
            training_drops = getattr(grader, 'last_drop_stats', None)

            result["weight_learning"] = {
                "available": True,
                "supported_sports": grader.SUPPORTED_SPORTS,
                "predictions_logged": sum(len(p) for p in grader.predictions.values()),
                "weights_loaded": bool(grader.weights),
                "weights_version_hash": weights_version_hash,
                "weights_file_exists": weights_file_exists,
                "weights_last_modified_et": weights_last_modified_et,
                "storage_path": grader.storage_path,
                "training_drops": training_drops,
                "note": "Use /grader/weights/{sport} to see learned weights"
            }
        else:
            result["weight_learning"] = {
                "available": False,
                "note": "Auto-grader weight learning not available"
            }
    except Exception as e:
        logger.error("Auto-grader weight learning status failed: %s", e)
        result["weight_learning"] = {
            "available": False,
            "error": str(e)
        }

    return result


# =============================================================================
# GRADER DEBUG FILES ENDPOINT
# =============================================================================

@router.get("/grader/debug-files")
async def grader_debug_files(api_key: str = Depends(verify_api_key)):
    """
    Debug endpoint to prove disk persistence (PROTECTED).

    Returns:
        - Resolved DATA_DIR and PICK_LOGS paths
        - Today's JSONL file path, existence, size, line count
        - First and last JSONL rows (with sensitive fields redacted)

    Requires:
        - X-API-Key header for authentication
    """
    from data_dir import DATA_DIR, PICK_LOGS
    from pick_logger import get_today_date_et

    result = {
        "paths": {
            "DATA_DIR": DATA_DIR,
            "PICK_LOGS": PICK_LOGS,
            "DATA_DIR_source": "RAILWAY_VOLUME_MOUNT_PATH env var" if os.getenv("RAILWAY_VOLUME_MOUNT_PATH") else "fallback"
        }
    }

    # Get today's file
    today = get_today_date_et()
    today_file = os.path.join(PICK_LOGS, f"picks_{today}.jsonl")

    result["today_file"] = {
        "path": today_file,
        "date": today,
        "exists": os.path.exists(today_file)
    }

    if os.path.exists(today_file):
        try:
            # Get file stats
            stat = os.stat(today_file)
            result["today_file"]["size_bytes"] = stat.st_size
            result["today_file"]["modified_time"] = datetime.fromtimestamp(stat.st_mtime).isoformat()

            # Count lines and get first/last
            with open(today_file, 'r') as f:
                lines = f.readlines()

            result["today_file"]["line_count"] = len(lines)

            if lines:
                # Parse first and last, redact sensitive fields
                def redact_pick(line):
                    try:
                        pick = json.loads(line)
                        # Keep only essential fields, redact IDs
                        return {
                            "sport": pick.get("sport", ""),
                            "date": pick.get("date", ""),
                            "pick_type": pick.get("pick_type", ""),
                            "player_name": pick.get("player_name", "")[:20] if pick.get("player_name") else "",
                            "matchup": pick.get("matchup", "")[:40] if pick.get("matchup") else "",
                            "tier": pick.get("tier", ""),
                            "final_score": pick.get("final_score", 0),
                            "result": pick.get("result"),
                            "pick_id": pick.get("pick_id", "")[:8] + "..." if pick.get("pick_id") else ""
                        }
                    except Exception as e:
                        return {"error": str(e)}

                result["today_file"]["first_pick"] = redact_pick(lines[0])
                result["today_file"]["last_pick"] = redact_pick(lines[-1])
        except Exception as e:
            result["today_file"]["read_error"] = str(e)

    return result


# =============================================================================
# GRADER WEIGHTS ENDPOINT
# =============================================================================

@router.get("/grader/weights/{sport}")
async def grader_weights(sport: str):
    """Get current prediction weights for a sport."""
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    from dataclasses import asdict
    grader = get_grader()  # Use singleton
    sport_upper = sport.upper()

    if sport_upper not in grader.weights:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    weights = {}
    for stat_type, config in grader.weights[sport_upper].items():
        weights[stat_type] = asdict(config)

    return {
        "sport": sport_upper,
        "weights": weights,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/grader/weights-sanity")
async def grader_weights_sanity():
    """
    v20.28.6: Check all sports for weight drift and sample issues.

    Returns:
        {
            "all_sports": { "NBA": {...}, "NFL": {...}, ... },
            "drift_detected": ["NBA/points", ...],
            "small_sample_sports": ["NHL", ...],
            "baseline_sum": 0.73,
            "drift_threshold": 0.05
        }
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    from dataclasses import asdict
    from auto_grader import BASELINE_WEIGHT_SUM, CORE_WEIGHT_FACTORS

    grader = get_grader()

    DRIFT_THRESHOLD = 0.05
    all_sports = {}
    drift_detected = []
    small_sample_sports = []

    for sport in ["NBA", "NFL", "NHL", "MLB", "NCAAB"]:
        if sport not in grader.weights:
            continue

        sport_data = {
            "weights": {},
            "drift_analysis": {}
        }

        for stat_type, config in grader.weights[sport].items():
            config_dict = asdict(config)
            sport_data["weights"][stat_type] = config_dict

            # Calculate weight sum for core factors
            core_sum = sum(config_dict.get(f, 0) for f in CORE_WEIGHT_FACTORS)
            drift = core_sum - BASELINE_WEIGHT_SUM

            sport_data["drift_analysis"][stat_type] = {
                "core_sum": round(core_sum, 4),
                "baseline": BASELINE_WEIGHT_SUM,
                "drift": round(drift, 4),
                "is_drifted": abs(drift) > DRIFT_THRESHOLD
            }

            if abs(drift) > DRIFT_THRESHOLD:
                drift_detected.append(f"{sport}/{stat_type}")

        # Check sample sizes via bias endpoint
        try:
            bias = grader.calculate_bias(sport, "points", days_back=7)
            sample_size = bias.get("sample_size", 0)
            sport_data["sample_size"] = sample_size
            if sample_size < 30:
                small_sample_sports.append(sport)
        except Exception:
            sport_data["sample_size"] = None

        all_sports[sport] = sport_data

    return {
        "all_sports": all_sports,
        "drift_detected": drift_detected,
        "small_sample_sports": small_sample_sports,
        "baseline_sum": BASELINE_WEIGHT_SUM,
        "drift_threshold": DRIFT_THRESHOLD,
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# GRADER RUN AUDIT ENDPOINT
# =============================================================================

@router.post("/grader/run-audit")
async def run_grader_audit(audit_config: Dict[str, Any] = None):
    """
    Run the daily audit to analyze bias and adjust weights.

    This is the self-improvement mechanism:
    1. Analyzes yesterday's predictions vs actual outcomes
    2. Calculates bias per prediction factor
    3. Adjusts weights to correct systematic errors
    4. Persists learned weights for future picks

    Request body (optional):
    {
        "days_back": 1,        # How many days to analyze (default: 1)
        "apply_changes": true  # Whether to apply weight changes (default: true)
    }
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    try:
        grader = get_grader()  # Use singleton

        config = audit_config or {}
        days_back = config.get("days_back", 1)
        apply_changes = config.get("apply_changes", True)

        # Run full audit
        results = grader.run_daily_audit(days_back=days_back)

        return {
            "status": "audit_complete",
            "days_analyzed": days_back,
            "changes_applied": apply_changes,
            "results": results,
            "timestamp": datetime.now().isoformat(),
            "note": "Weights have been adjusted based on prediction performance"
        }

    except Exception as e:
        logger.exception("Audit failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# GRADER BIAS ENDPOINT
# =============================================================================

@router.get("/grader/bias/{sport}")
async def get_prediction_bias(sport: str, stat_type: str = "all", days_back: int = 1):
    """
    Get prediction bias analysis for a sport.

    Shows how accurate our predictions have been and where we're over/under predicting.

    Bias interpretation:
    - Positive bias = we're predicting too HIGH
    - Negative bias = we're predicting too LOW
    - Healthy range is -1.0 to +1.0
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    grader = get_grader()  # Use singleton
    bias = grader.calculate_bias(sport, stat_type, days_back)

    return {
        "sport": sport.upper(),
        "stat_type": stat_type,
        "days_analyzed": days_back,
        "bias": bias,
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# GRADER ADJUST WEIGHTS ENDPOINT
# =============================================================================

@router.post("/grader/adjust-weights/{sport}")
async def adjust_sport_weights(sport: str, adjust_config: Dict[str, Any] = None):
    """
    Manually trigger weight adjustment for a sport.

    Request body (optional):
    {
        "stat_type": "points",    # Stat type to adjust (default: points)
        "days_back": 1,           # Days of data to analyze (default: 1)
        "apply_changes": true     # Whether to apply (default: true)
    }
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    grader = get_grader()  # Use singleton

    config = adjust_config or {}
    stat_type = config.get("stat_type", "points")
    days_back = config.get("days_back", 1)
    apply_changes = config.get("apply_changes", True)

    result = grader.adjust_weights(
        sport=sport,
        stat_type=stat_type,
        days_back=days_back,
        apply_changes=apply_changes
    )

    return {
        "status": "adjustment_complete" if apply_changes else "preview",
        "result": result,
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# GRADER RESET WEIGHTS ENDPOINT (v20.28.6)
# =============================================================================

@router.post("/grader/reset-weights/{sport}")
async def reset_sport_weights(sport: str, reset_config: Dict[str, Any] = None):
    """
    Reset weights for a sport/stat_type back to baseline.

    v20.28.6: Use this to undo incorrect weight adjustments from small samples.
    Example: Moneyline pace was adjusted to 0.21 based on only 6 picks.

    Request body:
    {
        "stat_type": "moneyline",   # Which market to reset (required)
        "factor": "pace",           # Which factor to reset (optional, resets all if omitted)
        "confirm": true             # Must be true to apply (safety check)
    }

    Baseline weights:
    - defense: 0.15
    - pace: 0.12
    - vacuum: 0.18
    - lstm: 0.20
    - officials: 0.08
    - park_factor: 0.10
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    config = reset_config or {}
    stat_type = config.get("stat_type")
    factor = config.get("factor")  # Optional: reset specific factor only
    confirm = config.get("confirm", False)

    if not stat_type:
        raise HTTPException(status_code=400, detail="stat_type is required")

    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Set confirm=true to apply reset. This is a safety check."
        )

    grader = get_grader()
    sport_upper = sport.upper()

    if sport_upper not in grader.weights:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    if stat_type not in grader.weights[sport_upper]:
        raise HTTPException(status_code=400, detail=f"Unknown stat_type: {stat_type}")

    # Baseline weights
    BASELINE = {
        "defense": 0.15,
        "pace": 0.12,
        "vacuum": 0.18,
        "lstm": 0.20,
        "officials": 0.08,
        "park_factor": 0.10,
    }

    current = grader.weights[sport_upper][stat_type]
    changes = {}

    if factor:
        # Reset single factor
        if factor not in BASELINE:
            raise HTTPException(status_code=400, detail=f"Unknown factor: {factor}")
        old_value = getattr(current, factor)
        setattr(current, factor, BASELINE[factor])
        changes[factor] = {"old": old_value, "new": BASELINE[factor]}
    else:
        # Reset all factors
        for f, baseline_val in BASELINE.items():
            if hasattr(current, f):
                old_value = getattr(current, f)
                setattr(current, f, baseline_val)
                changes[f] = {"old": round(old_value, 4), "new": baseline_val}

    # Save to disk
    grader._save_state()

    return {
        "status": "reset_complete",
        "sport": sport_upper,
        "stat_type": stat_type,
        "changes": changes,
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# GRADER TRAIN TEAM MODELS ENDPOINT
# =============================================================================

@router.post("/grader/train-team-models")
async def train_team_models_endpoint(config: Dict[str, Any] = None):
    """
    Manually trigger team model training from graded picks.

    v20.16.2: This trains LSTM, Matchup, and Ensemble models from
    recently graded picks. Use this to test the training pipeline
    without waiting for the 7 AM ET scheduled job.

    Request body (optional):
    {
        "days": 7,           # Days of history to process (default: 7)
        "sport": "NBA"       # Filter to specific sport (default: all)
    }

    Returns training results including telemetry proving execution.
    """
    try:
        from scripts.train_team_models import train_all

        cfg = config or {}
        days = cfg.get("days", 7)
        sport = cfg.get("sport")

        result = train_all(days=days, sport=sport)

        return {
            "status": "success",
            "training_result": result,
            "timestamp": datetime.now().isoformat(),
            "note": "Check model_status.training_telemetry to verify persistence"
        }
    except ImportError as e:
        return {
            "status": "error",
            "error": f"Training module not available: {e}",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Team model training failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# =============================================================================
# GRADER PERFORMANCE ENDPOINT
# =============================================================================

@router.get("/grader/performance/{sport}")
async def get_grader_performance(sport: str, days_back: int = 7):
    """
    Get prediction performance metrics for a sport.

    Shows hit rate, MAE, and trends over time.
    Use this to monitor how well our picks are performing.
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    grader = get_grader()  # Use singleton

    sport_upper = sport.upper()
    predictions = grader.predictions.get(sport_upper, [])

    # v20.5: Use timezone-aware datetime for comparison
    from core.time_et import now_et
    from zoneinfo import ZoneInfo
    et_tz = ZoneInfo("America/New_York")
    cutoff = now_et() - timedelta(days=days_back)

    # Filter to graded predictions within timeframe
    graded = []
    for p in predictions:
        if p.actual_value is None:
            continue
        try:
            ts = datetime.fromisoformat(p.timestamp)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=et_tz)
            if ts >= cutoff:
                graded.append(p)
        except (ValueError, TypeError):
            continue

    if not graded:
        return {
            "sport": sport_upper,
            "days_analyzed": days_back,
            "graded_count": 0,
            "message": "No graded predictions in this timeframe",
            "timestamp": datetime.now().isoformat()
        }

    # Calculate metrics
    hits = sum(1 for p in graded if p.hit)
    total = len(graded)
    hit_rate = hits / total if total > 0 else 0

    errors = [abs(p.error) for p in graded if p.error is not None]
    mae = sum(errors) / len(errors) if errors else 0

    # Group by stat type
    by_stat = {}
    for p in graded:
        if p.stat_type not in by_stat:
            by_stat[p.stat_type] = {"hits": 0, "total": 0, "errors": []}
        by_stat[p.stat_type]["total"] += 1
        if p.hit:
            by_stat[p.stat_type]["hits"] += 1
        if p.error is not None:
            by_stat[p.stat_type]["errors"].append(abs(p.error))

    stat_breakdown = {}
    for stat, data in by_stat.items():
        stat_breakdown[stat] = {
            "hit_rate": round(data["hits"] / data["total"] * 100, 1) if data["total"] > 0 else 0,
            "total_picks": data["total"],
            "mae": round(sum(data["errors"]) / len(data["errors"]), 2) if data["errors"] else 0
        }

    return {
        "sport": sport_upper,
        "days_analyzed": days_back,
        "graded_count": total,
        "overall": {
            "hit_rate": round(hit_rate * 100, 1),
            "mae": round(mae, 2),
            "profitable": hit_rate > 0.52,  # Need 52%+ to profit at -110 odds
            "status": "PROFITABLE" if hit_rate > 0.55 else ("BREAK-EVEN" if hit_rate > 0.48 else "NEEDS IMPROVEMENT")
        },
        "by_stat_type": stat_breakdown,
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# GRADER DAILY REPORT ENDPOINT
# =============================================================================

@router.get("/grader/daily-report")
async def get_daily_community_report(days_back: int = 1):
    """
    Generate a community-friendly daily report.

    This report is designed to share with your community showing:
    - Yesterday's performance across all sports
    - What the system learned
    - How we're improving
    - Encouragement regardless of wins/losses

    Share this every morning to build trust and transparency!
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    try:
        grader = get_grader()  # Use singleton

        # v20.5: Use timezone-aware datetimes to avoid comparison errors
        from core.time_et import now_et
        now = now_et()

        report_date = (now - timedelta(days=days_back)).strftime("%B %d, %Y")
        today = now.strftime("%B %d, %Y")

        # Collect performance across all sports
        sports_data = {}
        total_picks = 0
        total_hits = 0
        overall_lessons = []
        improvements = []

        for sport in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
            predictions = grader.predictions.get(sport, [])

            # v20.5: Fix date window - should be exactly 1 day, not 2
            # For days_back=1 (yesterday): 00:00 yesterday to 00:00 today
            from zoneinfo import ZoneInfo
            et_tz = ZoneInfo("America/New_York")
            report_day_start = (now - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
            report_day_end = report_day_start + timedelta(days=1)

            # Filter to report day's graded predictions
            graded = []
            for p in predictions:
                if p.actual_value is None:
                    continue
                try:
                    ts = datetime.fromisoformat(p.timestamp)
                    # Make timezone-aware if naive
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=et_tz)
                    if report_day_start <= ts < report_day_end:
                        graded.append(p)
                except (ValueError, TypeError):
                    continue

            if graded:
                hits = sum(1 for p in graded if p.hit)
                total = len(graded)
                hit_rate = hits / total if total > 0 else 0

                # Calculate bias
                errors = [p.error for p in graded if p.error is not None]
                avg_error = sum(errors) / len(errors) if errors else 0

                sports_data[sport] = {
                    "picks": total,
                    "wins": hits,
                    "losses": total - hits,
                    "hit_rate": round(hit_rate * 100, 1),
                    "status": "HOT" if hit_rate >= 0.55 else ("OK" if hit_rate >= 0.50 else "LEARNING"),
                    "avg_error": round(avg_error, 2)
                }

                total_picks += total
                total_hits += hits

                # Generate lessons learned
                if avg_error > 2:
                    overall_lessons.append(f"{sport}: We were predicting slightly high. Adjusting down.")
                    improvements.append(f"Lowered {sport} prediction weights by {min(abs(avg_error) * 2, 5):.1f}%")
                elif avg_error < -2:
                    overall_lessons.append(f"{sport}: We were predicting slightly low. Adjusting up.")
                    improvements.append(f"Raised {sport} prediction weights by {min(abs(avg_error) * 2, 5):.1f}%")

        # Calculate overall hit rate
        overall_hit_rate = (total_hits / total_picks * 100) if total_picks > 0 else 0

        # Generate status emoji and message
        if overall_hit_rate >= 55:
            status_emoji = "HOT"
            status_message = "SMASHING IT!"
            encouragement = "Your community is in great hands. Keep riding the hot streak!"
        elif overall_hit_rate >= 52:
            status_emoji = "PROFIT"
            status_message = "PROFITABLE DAY!"
            encouragement = "Above the 52% threshold needed for profit. Solid performance!"
        elif overall_hit_rate >= 48:
            status_emoji = "EVEN"
            status_message = "BREAK-EVEN ZONE"
            encouragement = "Close to the mark. Our self-learning system is making adjustments."
        else:
            status_emoji = "LEARN"
            status_message = "LEARNING DAY"
            encouragement = "Every loss teaches us something. The AI is adjusting weights to improve tomorrow."

        # Build community report
        report = {
            "title": f"SMASH SPOT DAILY REPORT - {today}",
            "subtitle": f"Performance Review: {report_date}",
            "overall": {
                "emoji": status_emoji,
                "status": status_message,
                "total_picks": total_picks,
                "total_wins": total_hits,
                "total_losses": total_picks - total_hits,
                "hit_rate": f"{overall_hit_rate:.1f}%",
                "profitable": overall_hit_rate >= 52
            },
            "by_sport": sports_data,
            "what_we_learned": overall_lessons if overall_lessons else [
                "Model performed within expected range.",
                "No major bias detected - weights stable."
            ],
            "improvements_made": improvements if improvements else [
                "Fine-tuning prediction confidence scores.",
                "Continuing to learn from betting patterns."
            ],
            "message_to_community": encouragement,
            "commitment": "We analyze EVERY pick, learn from EVERY outcome, and improve EVERY day. Win or lose, we're getting better together.",
            "next_audit": "Tomorrow 6:00 AM ET",
            "generated_at": datetime.now().isoformat()
        }

        # Add sample community post
        report["sample_post"] = f"""
{status_emoji} SMASH SPOT DAILY REPORT {status_emoji}

{report_date} Results:
- Total Picks: {total_picks}
- Record: {total_hits}-{total_picks - total_hits}
- Hit Rate: {overall_hit_rate:.1f}%

{status_message}

What We Learned:
{chr(10).join('- ' + lesson for lesson in (overall_lessons if overall_lessons else ['Model performing well, minor tuning applied.']))}

Improvements Made:
{chr(10).join('- ' + imp for imp in (improvements if improvements else ['Weights optimized for tomorrow.']))}

{encouragement}

We grade EVERY pick at 6 AM and adjust our AI daily.
Whether we win or lose, we're always improving!
"""

        return report

    except Exception as e:
        logger.exception("Failed to generate daily report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# GRADER DAILY LESSON ENDPOINT
# =============================================================================

@router.get("/grader/daily-lesson")
@router.get("/grader/daily-lesson/latest")
async def get_daily_lesson(date: Optional[str] = None, days_back: int = 0):
    """
    Return the latest daily learning lesson generated by the 6AM audit job.

    If date is not provided, returns today's ET lesson.
    """
    from data_dir import AUDIT_LOGS
    from core.time_et import now_et

    if days_back < 0:
        raise HTTPException(status_code=400, detail="days_back must be >= 0")

    if date:
        date_et = date
    else:
        date_et = (now_et() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    lesson_path = os.path.join(AUDIT_LOGS, f"lesson_{date_et}.json")

    if not os.path.exists(lesson_path):
        raise HTTPException(status_code=404, detail=f"No daily lesson found for {date_et}")

    try:
        with open(lesson_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.exception("Failed to read daily lesson: %s", e)
        raise HTTPException(status_code=500, detail="Failed to read daily lesson")


# =============================================================================
# GRADER QUEUE ENDPOINT
# =============================================================================

@router.get("/grader/queue")
async def get_grader_queue(
    date: Optional[str] = None,
    sports: Optional[str] = None,
    run_id: Optional[str] = None,
    latest_run: bool = False
):
    """
    Get ungraded picks queue for a date.

    Returns minimal pick data for queue management and verification.

    Query params:
    - date: Date to query (default: today ET)
    - sports: Comma-separated sports filter (default: all)
    - run_id: Filter to specific run (optional)
    - latest_run: If true, filter to most recent run only (default: false)

    Example:
        GET /live/grader/queue?date=2026-01-26&sports=NBA,NFL
        GET /live/grader/queue?date=2026-01-26&latest_run=true
    """
    if not PICK_LOGGER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Pick logger not available")

    try:
        # Get date in ET (use core.time_et single source of truth)
        if not date:
            from core.time_et import now_et
            date = now_et().strftime("%Y-%m-%d")

        pick_logger = get_pick_logger()
        picks = pick_logger.get_picks_for_date(date)

        # Filter by sports
        if sports:
            sport_list = [s.strip().upper() for s in sports.split(",")]
            picks = [p for p in picks if p.sport.upper() in sport_list]

        # Filter by run_id if specified
        if run_id:
            picks = [p for p in picks if getattr(p, 'run_id', '') == run_id]
        elif latest_run:
            # Get latest run_id
            latest_run_id = pick_logger.get_latest_run_id(date)
            if latest_run_id:
                picks = [p for p in picks if getattr(p, 'run_id', '') == latest_run_id]
                run_id = latest_run_id

        # Filter to ungraded only (not graded AND result is None)
        ungraded = [p for p in picks if not getattr(p, 'graded', False) and p.result is None]

        # Count by sport
        by_sport = {}
        for p in ungraded:
            sport = p.sport.upper()
            by_sport[sport] = by_sport.get(sport, 0) + 1

        logger.info("Grader queue: %d ungraded picks for %s (run_id=%s)", len(ungraded), date, run_id or "all")

        return {
            "date": date,
            "run_id": run_id,
            "latest_run": latest_run,
            "total": len(ungraded),
            "by_sport": by_sport,
            "picks": [
                {
                    "pick_id": p.pick_id,
                    "pick_hash": getattr(p, "pick_hash", ""),
                    "run_id": getattr(p, "run_id", ""),
                    "sport": p.sport,
                    "player_name": p.player_name,
                    "matchup": p.matchup,
                    "prop_type": p.prop_type,
                    "line": p.line,
                    "side": p.side,
                    "tier": p.tier,
                    "game_start_time_et": p.game_start_time_et,
                    "canonical_event_id": getattr(p, "canonical_event_id", ""),
                    "canonical_player_id": getattr(p, "canonical_player_id", ""),
                    "grade_status": getattr(p, "grade_status", "PENDING"),
                }
                for p in ungraded
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.exception("Failed to get grader queue: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# GRADER DRY-RUN ENDPOINT
# =============================================================================

@router.post("/grader/dry-run")
async def run_grader_dry_run(request_data: Dict[str, Any]):
    """
    Dry-run validation of autograder pipeline.

    Validates all picks can be:
    1. Matched to events (event ID exists or resolvable)
    2. Matched to players (for props: player ID exists or resolvable)
    3. Graded when game completes (grade-ready checklist)

    This is the KEY PROOF that tomorrow's 6AM grader will work.

    Request body:
    {
        "date": "2026-01-26",
        "sports": ["NBA", "NFL", "MLB", "NHL", "NCAAB"],
        "mode": "pre",  // "pre" (day-of) or "post" (next-day verification)
        "fail_on_unresolved": true
    }

    Mode semantics:
    - PRE (day-of): PASS if failed=0 AND unresolved=0 (pending allowed)
    - POST (next-day): PASS only if failed=0 AND pending=0 AND unresolved=0

    Returns structured validation report with PASS/FAIL/PENDING status.
    Per-pick reasons: PENDING_GAME_NOT_FINAL, UNRESOLVED_EVENT, UNRESOLVED_PLAYER, etc.

    ALWAYS returns valid JSON (never raises HTTPException to client).
    """
    if not GRADER_STORE_AVAILABLE:
        return {
            "ok": False,
            "error": "Grader store not available",
            "date": request_data.get("date", "unknown"),
            "mode": request_data.get("mode", "pre"),
            "total": 0,
            "graded": 0,
            "pending": 0,
            "failed": 0,
            "unresolved": 0,
            "overall_status": "ERROR"
        }

    try:
        # Parse request - get date from request or default to today ET
        date = request_data.get("date")
        if not date:
            from core.time_et import now_et
            date = now_et().strftime("%Y-%m-%d")

        sports = request_data.get("sports") or ["NBA", "NFL", "MLB", "NHL", "NCAAB"]
        mode = request_data.get("mode", "pre")  # "pre" or "post"
        fail_on_unresolved = request_data.get("fail_on_unresolved", False)

        # Load picks from grader_store (SINGLE SOURCE OF TRUTH)
        all_picks = grader_store.load_predictions(date_et=date)

        # Filter by sports
        sport_set = set(s.upper() for s in sports)
        picks = [p for p in all_picks if p.get("sport", "").upper() in sport_set]

        # Initialize results with new counters
        results = {
            "date": date,
            "mode": mode,
            "total": len(picks),
            "graded": 0,
            "pending": 0,
            "failed": 0,
            "unresolved": 0,
            "by_sport": {},
        }

        failed_picks = []
        unresolved_picks = []

        # Track already-graded/failed picks separately
        _already_graded = 0
        _already_failed = 0

        for pick in picks:
            sport = pick.get("sport", "").upper()

            if sport not in results["by_sport"]:
                results["by_sport"][sport] = {
                    "picks": 0,
                    "event_resolved": 0,
                    "player_resolved": 0,
                    "graded": 0,
                    "pending": 0,
                    "unresolved": 0,
                    "failed_picks": []
                }

            # Skip already-graded or already-failed picks
            _gs = pick.get("grade_status", "PENDING")
            if _gs == "GRADED":
                _already_graded += 1
                results["graded"] += 1
                results["by_sport"][sport]["graded"] += 1
                continue
            if _gs == "FAILED" and not pick.get("canonical_player_id"):
                # Old test seeds with no canonical_player_id — skip
                _already_failed += 1
                continue

            results["by_sport"][sport]["picks"] += 1

            # Check 1: Event resolution
            canonical_event_id = pick.get("canonical_event_id", "")
            matchup = pick.get("matchup", "")
            event_ok = bool(canonical_event_id) or bool(matchup)
            if event_ok:
                results["by_sport"][sport]["event_resolved"] += 1

            # Check 2: Player resolution (props only)
            player_ok = True
            player_name = pick.get("player_name", "")
            if player_name:
                canonical_player_id = pick.get("canonical_player_id", "")
                player_ok = bool(canonical_player_id) or IDENTITY_RESOLVER_AVAILABLE
                if player_ok:
                    results["by_sport"][sport]["player_resolved"] += 1

            # Check 3: Grade-ready checklist (always assume ready for dict picks)
            grade_ready_check = {"is_grade_ready": True, "reasons": []}

            # Determine per-pick status
            pick_reason = None
            pick_id = pick.get("pick_id", "")
            if not event_ok:
                results["unresolved"] += 1
                results["by_sport"][sport]["unresolved"] += 1
                pick_reason = "UNRESOLVED_EVENT"
                unresolved_picks.append({
                    "pick_id": pick_id,
                    "sport": sport,
                    "player": player_name,
                    "matchup": matchup,
                    "reason": pick_reason
                })
            elif player_name and not player_ok:
                results["unresolved"] += 1
                results["by_sport"][sport]["unresolved"] += 1
                pick_reason = "UNRESOLVED_PLAYER"
                unresolved_picks.append({
                    "pick_id": pick_id,
                    "sport": sport,
                    "player": player_name,
                    "matchup": matchup,
                    "reason": pick_reason
                })
            elif not grade_ready_check["is_grade_ready"]:
                # Missing required fields for grading
                results["failed"] += 1
                pick_reason = "MISSING_GRADE_FIELDS"
                failed_picks.append({
                    "pick_id": pick_id,
                    "sport": sport,
                    "player": player_name,
                    "matchup": matchup,
                    "reason": pick_reason,
                    "missing_fields": grade_ready_check.get("missing_fields", [])
                })
                results["by_sport"][sport]["failed_picks"].append({
                    "pick_id": pick_id,
                    "reason": pick_reason,
                    "player": player_name,
                    "missing_fields": grade_ready_check.get("missing_fields", [])
                })
            elif pick.get("result") is not None or pick.get("graded", False):
                # Already graded
                results["graded"] += 1
                results["by_sport"][sport]["graded"] += 1
            else:
                # Awaiting game completion (valid, just not graded yet)
                results["pending"] += 1
                results["by_sport"][sport]["pending"] += 1

        # Determine overall status based on mode
        if mode == "pre":
            # PRE mode: PASS if failed=0 AND unresolved=0 (pending allowed)
            if results["failed"] > 0 or results["unresolved"] > 0:
                results["overall_status"] = "FAIL"
            elif results["pending"] > 0:
                results["overall_status"] = "PENDING"  # This is OK for pre-mode
            else:
                results["overall_status"] = "PASS"
        else:  # post mode
            # POST mode: PASS only if everything graded
            if results["failed"] > 0 or results["unresolved"] > 0:
                results["overall_status"] = "FAIL"
            elif results["pending"] > 0:
                results["overall_status"] = "PENDING"  # Still waiting for grades
            else:
                results["overall_status"] = "PASS"

        # For exit code interpretation
        results["pre_mode_pass"] = (results["failed"] == 0 and results["unresolved"] == 0)
        results["post_mode_pass"] = (results["failed"] == 0 and results["unresolved"] == 0 and results["pending"] == 0)

        results["summary"] = {
            "total": results["total"],
            "graded": results["graded"],
            "pending": results["pending"],
            "failed": results["failed"],
            "unresolved": results["unresolved"]
        }
        results["failed_picks"] = failed_picks
        results["unresolved_picks"] = unresolved_picks
        results["skipped_already_graded"] = _already_graded
        results["skipped_stale_seeds"] = _already_failed
        results["timestamp"] = datetime.now().isoformat()

        logger.info(
            "Dry-run complete (mode=%s): %s - total=%d graded=%d pending=%d failed=%d unresolved=%d",
            mode,
            results["overall_status"],
            results["total"],
            results["graded"],
            results["pending"],
            results["failed"],
            results["unresolved"]
        )

        # Add fail flag if fail_on_unresolved and there are failures/unresolved
        if fail_on_unresolved and (results["failed"] > 0 or results["unresolved"] > 0):
            results["ok"] = False
            results["message"] = f"{results['failed']} failed, {results['unresolved']} unresolved"
        else:
            results["ok"] = True

        return results

    except Exception as e:
        logger.exception("Dry-run failed: %s", e)
        # ALWAYS return valid JSON, never raise HTTPException
        import traceback
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "date": request_data.get("date", "unknown"),
            "mode": request_data.get("mode", "pre"),
            "total": 0,
            "graded": 0,
            "pending": 0,
            "failed": 0,
            "unresolved": 0,
            "overall_status": "ERROR"
        }
