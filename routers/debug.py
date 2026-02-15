"""
DEBUG ROUTER - Debug and Diagnostic Endpoints

Extracted from live_data_router.py for better maintainability.
Contains endpoints for system health, time debugging, integration status,
predictions status, and training status.

These are read-only endpoints that provide observability into system state.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import os
import logging
import httpx

# Auth dependency
from core.auth import verify_api_key

logger = logging.getLogger("debug_router")

router = APIRouter(tags=["debug"])


# ============================================================================
# DEBUG PREDICTIONS STATUS
# ============================================================================

@router.get("/debug/predictions/status")
async def debug_predictions_status(api_key: str = Depends(verify_api_key)):
    """
    Show prediction storage state (PROTECTED).

    Returns:
        - total_predictions: int
        - pending_predictions: int
        - graded_predictions: int
        - last_prediction_time: str
        - by_sport: Dict[sport, count]
        - storage_path: str
        - file_sizes: Dict[date, size_bytes]

    Requires:
        X-API-Key header
    """
    try:
        from core.persistence import get_storage_stats
        stats = get_storage_stats()
        return stats
    except ImportError:
        # Fallback if core.persistence not available
        try:
            from pick_logger import get_pick_logger, get_today_date_et
            pick_logger = get_pick_logger()
            today = get_today_date_et()
            all_picks = pick_logger.get_picks_for_date(today)

            pending = [p for p in all_picks if p.get("grade_status") == "PENDING"]
            graded = [p for p in all_picks if p.get("grade_status") in ["WIN", "LOSS", "PUSH"]]

            by_sport = {}
            for pick in all_picks:
                sport = pick.get("sport", "UNKNOWN")
                by_sport[sport] = by_sport.get(sport, 0) + 1

            return {
                "storage_path": pick_logger.storage_path,
                "total_predictions": len(all_picks),
                "pending_predictions": len(pending),
                "graded_predictions": len(graded),
                "last_prediction_time": all_picks[-1].get("published_at", "") if all_picks else "",
                "by_sport": by_sport,
                "file_sizes": {},
            }
        except Exception as e:
            logger.error("Failed to get predictions status: %s", e)
            return {
                "storage_path": "unavailable",
                "total_predictions": 0,
                "pending_predictions": 0,
                "graded_predictions": 0,
                "last_prediction_time": "",
                "by_sport": {},
                "file_sizes": {},
                "error": str(e)
            }


# ============================================================================
# DEBUG SYSTEM HEALTH
# ============================================================================

@router.get("/debug/system/health")
async def debug_system_health(api_key: str = Depends(verify_api_key)):
    """
    Comprehensive system health check (PROTECTED).

    Checks:
        - API connectivity (Playbook, Odds API, BallDontLie)
        - Persistence read/write sanity check
        - Scoring pipeline sanity on synthetic candidate
        - Core modules availability

    Returns:
        - ok: bool (overall health)
        - errors: List[str] (problems found)
        - checks: Dict[check_name, result]

    IMPORTANT: NEVER crashes - returns ok=false + errors list if problems found.

    Requires:
        X-API-Key header
    """
    errors = []
    checks = {}

    # =========================================================================
    # CHECK 1: API Connectivity
    # =========================================================================
    api_checks = {}

    # Playbook API
    try:
        from playbook_api import build_playbook_url
        PLAYBOOK_UTIL_AVAILABLE = True
    except ImportError:
        PLAYBOOK_UTIL_AVAILABLE = False

    try:
        if PLAYBOOK_UTIL_AVAILABLE:
            test_url, test_params = build_playbook_url("health", {})
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(test_url, params=test_params)
                api_checks["playbook"] = {
                    "ok": resp.status_code == 200,
                    "status_code": resp.status_code
                }
                if resp.status_code != 200:
                    errors.append(f"Playbook API returned {resp.status_code}")
        else:
            api_checks["playbook"] = {"ok": False, "error": "playbook_api module not available"}
            errors.append("playbook_api module not available")
    except Exception as e:
        api_checks["playbook"] = {"ok": False, "error": str(e)}
        errors.append(f"Playbook API check failed: {e}")

    # Odds API
    try:
        odds_api_key = os.getenv("ODDS_API_KEY", "")
        if odds_api_key:
            # Use params dict instead of embedding key in URL (prevents log leakage)
            test_url = "https://api.the-odds-api.com/v4/sports/"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(test_url, params={"apiKey": odds_api_key})
                api_checks["odds_api"] = {
                    "ok": resp.status_code == 200,
                    "status_code": resp.status_code,
                    "remaining": resp.headers.get("x-requests-remaining", "unknown")
                }
                if resp.status_code != 200:
                    errors.append(f"Odds API returned {resp.status_code}")
        else:
            api_checks["odds_api"] = {"ok": False, "error": "ODDS_API_KEY not set"}
            errors.append("ODDS_API_KEY environment variable not set")
    except Exception as e:
        api_checks["odds_api"] = {"ok": False, "error": str(e)}
        errors.append(f"Odds API check failed: {e}")

    # BallDontLie
    try:
        from alt_data_sources.balldontlie import BDL_API_KEY
        if BDL_API_KEY:
            test_url = "https://api.balldontlie.io/v1/players?per_page=1"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    test_url,
                    headers={"Authorization": BDL_API_KEY}
                )
                api_checks["balldontlie"] = {
                    "ok": resp.status_code == 200,
                    "status_code": resp.status_code
                }
                if resp.status_code != 200:
                    errors.append(f"BallDontLie API returned {resp.status_code}")
        else:
            api_checks["balldontlie"] = {"ok": False, "error": "BDL_API_KEY not set"}
    except Exception as e:
        api_checks["balldontlie"] = {"ok": False, "error": str(e)}

    checks["api_connectivity"] = api_checks

    # =========================================================================
    # CHECK 2: Persistence Read/Write
    # =========================================================================
    try:
        from core.persistence import validate_storage_writable
        is_writable, write_error = validate_storage_writable()
        checks["persistence"] = {
            "ok": is_writable,
            "writable": is_writable,
            "error": write_error if not is_writable else None
        }
        if not is_writable:
            errors.append(f"Persistence not writable: {write_error}")
    except ImportError:
        # Fallback
        try:
            from pick_logger import get_pick_logger
            pick_logger = get_pick_logger()
            test_file = os.path.join(pick_logger.storage_path, ".health_check")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            checks["persistence"] = {"ok": True, "writable": True}
        except Exception as e:
            checks["persistence"] = {"ok": False, "writable": False, "error": str(e)}
            errors.append(f"Persistence write check failed: {e}")

    # =========================================================================
    # CHECK 3: Scoring Pipeline Sanity
    # =========================================================================
    try:
        from core.scoring_pipeline import score_candidate

        # Synthetic test candidate
        test_candidate = {
            "game_str": "Test @ Team",
            "player_name": "",
            "pick_type": "SPREAD",
            "line": -5.5,
            "side": "Test",
            "spread": -5.5,
            "total": 220,
            "odds": -110,
            "prop_line": 0,
        }

        test_context = {
            "sharp_signal": {"signal_strength": "MODERATE", "line_variance": 0.8},
            "public_pct": 65,
            "home_team": "Team",
            "away_team": "Test",
        }

        result = score_candidate(test_candidate, test_context)

        # Validate result has required fields
        required_fields = ["ai_score", "research_score", "esoteric_score", "jarvis_score", "final_score", "tier"]
        missing = [f for f in required_fields if f not in result]

        if missing:
            checks["scoring_pipeline"] = {
                "ok": False,
                "error": f"Missing fields in result: {missing}"
            }
            errors.append(f"Scoring pipeline missing fields: {missing}")
        else:
            checks["scoring_pipeline"] = {
                "ok": True,
                "test_final_score": result["final_score"],
                "test_tier": result["tier"]
            }
    except ImportError:
        checks["scoring_pipeline"] = {
            "ok": False,
            "error": "core.scoring_pipeline module not available"
        }
        errors.append("Scoring pipeline module not available")
    except Exception as e:
        checks["scoring_pipeline"] = {"ok": False, "error": str(e)}
        errors.append(f"Scoring pipeline sanity check failed: {e}")

    # =========================================================================
    # CHECK 4: Core Modules
    # =========================================================================
    core_modules = {}

    try:
        from core import invariants
        core_modules["invariants"] = {"ok": True, "version": "15.1"}
    except ImportError as e:
        core_modules["invariants"] = {"ok": False, "error": str(e)}
        errors.append("core.invariants module not available")

    try:
        from core import scoring_pipeline
        core_modules["scoring_pipeline"] = {"ok": True}
    except ImportError as e:
        core_modules["scoring_pipeline"] = {"ok": False, "error": str(e)}

    try:
        from core import time_window_et
        core_modules["time_window_et"] = {"ok": True}
    except ImportError as e:
        core_modules["time_window_et"] = {"ok": False, "error": str(e)}

    try:
        from core import persistence
        core_modules["persistence"] = {"ok": True}
    except ImportError as e:
        core_modules["persistence"] = {"ok": False, "error": str(e)}

    checks["core_modules"] = core_modules

    # =========================================================================
    # OVERALL STATUS
    # =========================================================================
    ok = len(errors) == 0

    return {
        "ok": ok,
        "errors": errors,
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# DEBUG TIME
# ============================================================================

@router.get("/debug/time")
async def debug_time(api_key: str = Depends(verify_api_key)):
    """
    ET timezone debug endpoint (PROTECTED).

    Returns current time info from single source of truth (core.time_et)
    plus fail-loud validation of ET bounds invariants.

    CANONICAL ET SLATE WINDOW:
        Start: 00:00:00 ET (midnight) - inclusive
        End:   00:00:00 ET next day (midnight) - exclusive
        Interval: [start, end)

    Returns:
        - now_utc_iso: Current UTC time
        - now_et_iso: Current ET time
        - et_date: Today's date in ET (YYYY-MM-DD)
        - et_day_start_iso: Start of ET day (00:00:00)
        - et_day_end_iso: End of ET day (00:00:00 next day, exclusive)
        - canonical_window: Description of the canonical window
        - bounds_validation: Invariant validation results (FAIL LOUD if invalid)
        - build_sha: Git commit SHA
        - deploy_version: Deployment version

    Requires:
        X-API-Key header
    """
    try:
        from core.time_et import now_et, et_day_bounds, assert_et_bounds

        # Current times
        now_utc = datetime.now(timezone.utc)
        now_et_dt = now_et()

        # ET day bounds
        start_et, end_et, _start_utc, _end_utc = et_day_bounds()
        et_date = start_et.date().isoformat()

        # FAIL LOUD: Validate bounds invariants
        validation = assert_et_bounds(start_et, end_et)

        # Build info
        build_sha = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "unknown")[:8]
        deploy_version = os.environ.get("DEPLOY_VERSION", "unknown")

        return {
            "now_utc_iso": now_utc.isoformat(),
            "now_et_iso": now_et_dt.isoformat(),
            "et_date": et_date,
            "et_day_start_iso": start_et.isoformat(),
            "et_day_end_iso": end_et.isoformat(),
            "window_display": f"{et_date} 00:00:00 to 23:59:59 ET",
            "canonical_window": {
                "start_time": "00:00:00 ET",
                "end_time": "00:00:00 ET (next day, exclusive)",
                "interval_notation": "[start, end)",
                "description": "ET day runs midnight to midnight (exclusive end)",
            },
            "bounds_validation": validation,
            "bounds_valid": validation["valid"],
            "build_sha": build_sha,
            "deploy_version": deploy_version,
        }
    except Exception as e:
        return {
            "error": str(e),
            "bounds_valid": False,
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# DEBUG INTEGRATIONS
# ============================================================================

@router.get("/debug/integrations")
async def debug_integrations(
    api_key: str = Depends(verify_api_key),
    quick: bool = False
):
    """
    Get status of ALL external integrations.

    This endpoint provides comprehensive visibility into:
    - Which APIs are configured (env vars set)
    - Which APIs are reachable (can connect)
    - Last success/error timestamps
    - Which modules and endpoints depend on each integration

    Args:
        quick: If true, returns fast summary without connectivity checks

    Returns:
        Complete integration status for monitoring and debugging.

    Requires:
        X-API-Key header
    """
    try:
        from integration_registry import (
            get_all_integrations_status,
            get_integrations_summary
        )

        if quick:
            result = get_integrations_summary()
        else:
            result = await get_all_integrations_status()

        # v2.0: Add Jarvis runtime proof section
        jarvis_savant_loaded = False
        jarvis_hybrid_loaded = False

        try:
            from jarvis_savant_engine import get_jarvis_engine as _get_savant
            jarvis_savant_loaded = True
        except ImportError:
            pass

        try:
            from core.jarvis_ophis_hybrid import get_jarvis_hybrid
            jarvis_hybrid_loaded = True
        except ImportError:
            pass

        # Add Jarvis status to result
        result["jarvis_runtime"] = {
            "savant_loaded": jarvis_savant_loaded,
            "hybrid_loaded": jarvis_hybrid_loaded,
            "active_impl": "hybrid" if jarvis_hybrid_loaded else ("savant" if jarvis_savant_loaded else "fallback"),
        }

        return result

    except ImportError as e:
        return {
            "error": "Integration registry not available",
            "detail": str(e),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.exception("Error getting integration status: %s", e)
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# DEBUG INTEGRATION ROLLUP
# ============================================================================

@router.get("/debug/integration-rollup")
async def debug_integration_rollup(
    api_key: str = Depends(verify_api_key)
):
    """
    Get integration usage rollup and health metrics.

    Provides aggregated metrics for monitoring:
    - Call counts by integration (last 15 min, last hour, last 24h)
    - Error rates
    - Cache hit rates
    - Latency percentiles

    Requires:
        X-API-Key header
    """
    try:
        from core.integration_rollup import get_rollup

        result = get_rollup()
        return result

    except ImportError as e:
        return {
            "error": "Integration rollup module not available",
            "detail": str(e),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.exception("Error getting integration rollup: %s", e)
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# DEBUG ALERTS
# ============================================================================

@router.get("/debug/alerts")
async def debug_alerts(
    api_key: str = Depends(verify_api_key)
):
    """
    Get active integration alerts.

    Alert types:
    - CRITICAL_INTEGRATION_DOWN: CRITICAL tier integration has errors
    - CRITICAL_STALENESS: CRITICAL tier data is stale
    - SUCCESS_RATE_DROP: Significant drop in success rate
    - UNUSED_INTEGRATION: Configured but never used

    Returns:
        List of active alerts with severity levels (critical, warning, info)

    Requires:
        X-API-Key header
    """
    try:
        from core.integration_rollup import get_alerts

        result = get_alerts()

        # Add health summary based on alerts
        result["health_summary"] = {
            "ok": result["critical_count"] == 0,
            "status": "critical" if result["critical_count"] > 0 else
                      "warning" if result["warning_count"] > 0 else "healthy",
            "message": f"{result['critical_count']} critical, {result['warning_count']} warnings"
        }

        return result

    except ImportError as e:
        return {
            "error": "Integration rollup module not available",
            "detail": str(e),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.exception("Error getting alerts: %s", e)
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# DEBUG LEARNING LATEST
# ============================================================================

@router.get("/debug/learning/latest")
async def debug_learning_latest():
    """
    DEBUG ENDPOINT: Get latest learning loop status and report.

    Shows:
    - Current weights for all esoteric signals
    - Recent performance by signal
    - Weight adjustment history
    - Grading statistics
    """
    result = {
        "esoteric_learning": {},
        "auto_grader": {},
        "timestamp": datetime.now().isoformat()
    }

    # Esoteric Learning Loop
    try:
        from esoteric_learning_loop import get_esoteric_loop
        loop = get_esoteric_loop()
        if loop:
            result["esoteric_learning"] = {
                "available": True,
                "current_weights": loop.get_weights(),
                "performance_30d": loop.get_performance(days_back=30),
                "recent_picks": loop.get_recent_picks(limit=5)
            }
        else:
            result["esoteric_learning"] = {"available": False}
    except Exception as e:
        result["esoteric_learning"] = {"available": False, "error": str(e)}

    # Auto Grader
    try:
        from auto_grader import get_grader, AUTO_GRADER_AVAILABLE
        if AUTO_GRADER_AVAILABLE:
            grader = get_grader()
            total_predictions = sum(len(p) for p in grader.predictions.values())

            # Get performance for each sport
            sport_performance = {}
            for sport in grader.SUPPORTED_SPORTS:
                try:
                    perf = grader.get_performance(sport, days_back=7)
                    sport_performance[sport] = perf
                except Exception:
                    sport_performance[sport] = {"error": "Could not fetch"}

            result["auto_grader"] = {
                "available": True,
                "total_predictions_logged": total_predictions,
                "storage_path": grader.storage_path,
                "sports_tracked": grader.SUPPORTED_SPORTS,
                "performance_by_sport": sport_performance
            }
        else:
            result["auto_grader"] = {"available": False}
    except Exception as e:
        result["auto_grader"] = {"available": False, "error": str(e)}

    # Esoteric Grader (from esoteric_grader.py)
    try:
        from esoteric_grader import get_esoteric_grader
        eso_grader = get_esoteric_grader()
        result["esoteric_grader"] = {
            "available": True,
            "accuracy_stats": eso_grader.get_all_accuracy_stats(),
            "performance_summary": eso_grader.get_performance_summary(days_back=30)
        }
    except Exception as e:
        result["esoteric_grader"] = {"available": False, "error": str(e)}

    return result


# ============================================================================
# DEBUG TRAINING STATUS
# ============================================================================

@router.get("/debug/training-status")
async def get_training_status():
    """
    Get comprehensive training status for production monitoring.

    v20.17.2: Returns all proof fields needed to verify training pipeline health,
    including store audit with mechanically verifiable counts.

    Returns:
        - build_info: build_sha, deploy_version, engine_version
        - model_status: ensemble/lstm/matchup status with proof fields
        - training_telemetry: last_train_run_at, graded_samples_seen, etc.
        - artifact_proof: file existence, size, mtime for each model artifact
        - scheduler_proof: next_run_time for training job
        - store_audit: mechanically verifiable store provenance and data quality
        - training_health: HEALTHY | STALE | NEVER_RAN

    This endpoint is safe: no secrets, no heavy compute, fail-soft with errors[].
    """
    import json
    try:
        import pytz
        ET = pytz.timezone("America/New_York")
    except ImportError:
        from zoneinfo import ZoneInfo
        ET = ZoneInfo("America/New_York")

    errors = []
    now_et = datetime.now(ET)

    # 0. Build info for deployment tracking
    build_info = {
        "build_sha": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "local")[:7],
        "deploy_version": os.environ.get("DEPLOY_VERSION", "dev"),
        "engine_version": "v20.17.2",
    }

    # 1. Get model status
    model_status = {}
    training_telemetry = {}
    try:
        from team_ml_models import get_model_status, get_game_ensemble

        status = get_model_status()
        model_status = {
            "ensemble": status.get("ensemble", {}).get("status", "UNKNOWN"),
            "ensemble_samples_trained": status.get("ensemble", {}).get("samples_trained", 0),
            "ensemble_is_trained": status.get("ensemble", {}).get("is_trained", False),
            # v20.22: Sklearn regressor status (shadow mode by default)
            "sklearn_status": status.get("ensemble", {}).get("sklearn_status", {}),
            "lstm": status.get("lstm", {}).get("status", "UNKNOWN"),
            "lstm_teams_cached": status.get("lstm", {}).get("teams_cached", 0),
            "matchup": status.get("matchup", {}).get("status", "UNKNOWN"),
            "matchup_tracked": status.get("matchup", {}).get("matchups_tracked", 0),
        }

        # v20.17.3: Fix path - training_telemetry is at top level, not inside "ensemble"
        training_telemetry = status.get("training_telemetry", {})
    except Exception as e:
        errors.append(f"model_status: {e}")

    # 2. Get artifact proof
    artifact_proof = {}
    models_dir = os.path.join(os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/data"), "models")
    artifact_files = [
        "team_data_cache.json",
        "matchup_matrix.json",
        "ensemble_weights.json",
    ]

    for filename in artifact_files:
        filepath = os.path.join(models_dir, filename)
        try:
            if os.path.exists(filepath):
                stat = os.stat(filepath)
                mtime = datetime.fromtimestamp(stat.st_mtime, tz=ET)
                artifact_proof[filename] = {
                    "exists": True,
                    "size_bytes": stat.st_size,
                    "mtime_iso": mtime.isoformat(),
                }
            else:
                artifact_proof[filename] = {
                    "exists": False,
                    "size_bytes": 0,
                    "mtime_iso": None,
                }
        except Exception as e:
            artifact_proof[filename] = {
                "exists": False,
                "error": str(e),
            }
            errors.append(f"artifact {filename}: {e}")

    # 3. Get scheduler proof
    scheduler_proof = {}
    try:
        from daily_scheduler import get_scheduler

        scheduler_instance = get_scheduler()
        if scheduler_instance and scheduler_instance.scheduler:
            for job in scheduler_instance.scheduler.get_jobs():
                if job.id == "team_model_train":
                    next_run_et = None
                    if job.next_run_time:
                        next_run_et = job.next_run_time.astimezone(ET).isoformat()
                    scheduler_proof = {
                        "job_registered": True,
                        "next_run_time_et": next_run_et,
                    }
                    break
            else:
                scheduler_proof = {"job_registered": False}
        else:
            scheduler_proof = {"scheduler_running": False}
    except Exception as e:
        scheduler_proof = {"error": str(e)}
        errors.append(f"scheduler_proof: {e}")

    # 4. Determine training health
    # NEVER_RAN: last_train_run_at is null AND graded picks > 0
    # STALE: last_train_run_at older than 24h AND graded picks > 0
    # HEALTHY: otherwise
    training_health = "HEALTHY"
    graded_count = 0

    try:
        # Count graded picks
        predictions_file = os.path.join(
            os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/data"),
            "grader", "predictions.jsonl"
        )
        if os.path.exists(predictions_file):
            with open(predictions_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            pick = json.loads(line)
                            result = pick.get("result", "").upper()
                            if result in ("WIN", "LOSS"):
                                graded_count += 1
                        except Exception:
                            pass
    except Exception as e:
        errors.append(f"graded_count: {e}")

    last_train_run_at = training_telemetry.get("last_train_run_at")

    if graded_count > 0:
        if not last_train_run_at:
            training_health = "NEVER_RAN"
        else:
            try:
                # Parse last_train_run_at
                if isinstance(last_train_run_at, str):
                    # Handle both formats: with and without timezone
                    if '+' in last_train_run_at or 'Z' in last_train_run_at:
                        last_run = datetime.fromisoformat(last_train_run_at.replace('Z', '+00:00'))
                    else:
                        last_run = datetime.fromisoformat(last_train_run_at).replace(tzinfo=ET)

                    hours_since_train = (now_et - last_run.astimezone(ET)).total_seconds() / 3600
                    if hours_since_train > 24:
                        training_health = "STALE"
            except Exception as e:
                errors.append(f"training_health parse: {e}")

    # 5. Store audit - mechanically verifiable counts
    store_audit = {}
    try:
        from scripts.audit_training_store import get_store_audit_summary
        store_audit = get_store_audit_summary()
    except Exception as e:
        errors.append(f"store_audit: {e}")
        store_audit = {"error": str(e), "available": False}

    return {
        "build_sha": build_info["build_sha"],  # Top-level for easy jq access
        "build_info": build_info,
        "model_status": model_status,
        "training_telemetry": training_telemetry,
        "artifact_proof": artifact_proof,
        "scheduler_proof": scheduler_proof,
        "store_audit": store_audit,
        "training_health": training_health,
        "graded_picks_count": graded_count,
        "timestamp_et": now_et.isoformat(),
        "errors": errors if errors else None,
    }
