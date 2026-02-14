"""
⏰ DAILY SCHEDULER v1.1
========================
Automated daily tasks for Bookie-o-em:

1. Grade yesterday's predictions (6 AM)
2. Adjust weights based on bias
3. Retrain LSTM if performance drops
4. Clean up old prediction logs
5. Auto-grade picks every 30 minutes (v14.9)

All 5 Sports: NBA, NFL, MLB, NHL, NCAAB
"""

# Explicit exports - prevents "cannot import name" errors
__all__ = [
    'DailyScheduler',
    'SchedulerConfig',
    'SCHEDULER_AVAILABLE',
    'scheduler_router',
    'init_scheduler',
    'get_scheduler',
    'get_daily_scheduler',  # Alias for backward compatibility
]

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
logger = logging.getLogger(__name__)
import threading
import time
from core.time_et import now_et

# APScheduler for cron-like scheduling
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not installed - using simple threading")

# Result Fetcher for auto-grading (v14.9)
try:
    from result_fetcher import auto_grade_picks, scheduled_auto_grade
    RESULT_FETCHER_AVAILABLE = True
except ImportError:
    RESULT_FETCHER_AVAILABLE = False
    logger.warning("result_fetcher not available - auto-grading disabled")

# Best-bets cache pre-warm (v15.0)
WARM_AVAILABLE = False
try:
    from live_data_router import _best_bets_inner, api_cache, SPORT_MAPPINGS
    WARM_AVAILABLE = True
except ImportError:
    logger.warning("live_data_router not available - cache pre-warm disabled")

# v16.1: ML Model Retraining
ML_RETRAIN_AVAILABLE = False
try:
    from ml_integration import get_lstm_manager, get_ensemble_manager, get_ml_status
    ML_RETRAIN_AVAILABLE = True
except ImportError:
    logger.warning("ml_integration not available - ML retraining disabled")


async def warm_best_bets_cache():
    """Pre-warm best-bets cache for sports with games today. Called by scheduler."""
    if not WARM_AVAILABLE:
        logger.warning("WARM skipped: live_data_router not available")
        return

    import pytz
    ET = pytz.timezone("America/New_York")
    now_et = datetime.now(ET)
    today_str = now_et.strftime("%Y-%m-%d")
    from data_dir import SUPPORTED_SPORTS
    sports = [s.lower() for s in SUPPORTED_SPORTS]

    for sport in sports:
        cache_key = f"best-bets:{sport}"
        try:
            # Skip if cache already warm
            cached = api_cache.get(cache_key)
            if cached:
                logger.info("WARM skip cache hot: %s", sport)
                continue

            # Distributed lock so multiple containers don't warm simultaneously
            lock_key = f"warm_best_bets:{sport}:{today_str}"
            if not api_cache.acquire_lock(lock_key, ttl=900):
                logger.info("WARM skip locked: %s", sport)
                continue

            # Check if sport has games today (lightweight events fetch)
            try:
                import httpx
                odds_api_key = os.getenv("ODDS_API_KEY", "")
                odds_base = os.getenv("ODDS_API_BASE", "https://api.the-odds-api.com/v4")
                sport_config = SPORT_MAPPINGS.get(sport, {})
                odds_sport = sport_config.get("odds", "")
                if odds_api_key and odds_sport:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.get(
                            f"{odds_base}/sports/{odds_sport}/events",
                            params={"apiKey": odds_api_key}
                        )
                        if resp.status_code == 200:
                            events = resp.json()
                            # Filter to today's games (simple date check)
                            today_events = [e for e in events
                                          if e.get("commence_time", "")[:10] == today_str]
                            if not today_events:
                                logger.info("WARM skip no games: %s", sport)
                                api_cache.release_lock(lock_key)
                                continue
                        else:
                            logger.warning("WARM events fetch failed for %s: %d", sport, resp.status_code)
                            api_cache.release_lock(lock_key)
                            continue
                else:
                    logger.info("WARM skip no API key or sport config: %s", sport)
                    api_cache.release_lock(lock_key)
                    continue
            except Exception as e:
                logger.warning("WARM events check error for %s: %s", sport, e)
                api_cache.release_lock(lock_key)
                continue

            # Warm the cache by calling _best_bets_inner directly
            logger.info("WARM start: %s", sport)
            _start = time.time()
            await _best_bets_inner(sport, sport, False, cache_key)
            duration = time.time() - _start
            logger.info("WARM done: %s in %.1fs", sport, duration)

            # Store warm metadata
            api_cache.set(f"warm_meta:{sport}", {
                "last_warm_time": datetime.now(ET).isoformat(),
                "duration_seconds": round(duration, 1)
            }, ttl=86400)

        except Exception as e:
            logger.error("WARM error for %s: %s", sport, e)
            try:
                api_cache.release_lock(f"warm_best_bets:{sport}:{today_str}")
            except Exception:
                pass


# ============================================
# CONFIGURATION
# ============================================

class SchedulerConfig:
    """Scheduler configuration."""
    
    # Audit time (6 AM ET)
    AUDIT_HOUR = 6
    AUDIT_MINUTE = 0
    
    # Retrain threshold
    RETRAIN_MAE_THRESHOLD = 5.0  # Retrain if MAE exceeds this
    RETRAIN_HIT_RATE_THRESHOLD = 0.48  # Retrain if hit rate below this
    
    # Cleanup
    KEEP_PREDICTIONS_DAYS = 30  # Keep 30 days of prediction history
    
    # v20.15: Sports and default stats - all prop types for complete learning
    SPORT_STATS = {
        "NBA": ["points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers", "pra"],
        "NFL": ["pass_tds", "pass_yds", "rush_yds", "reception_yds", "receptions", "anytime_td"],
        "MLB": ["hits", "runs", "rbis", "home_runs", "total_bases", "strikeouts", "outs"],
        "NHL": ["goals", "assists", "points", "shots", "saves"],
        "NCAAB": ["points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers"]
    }


# ============================================
# DAILY AUDIT JOB
# ============================================

class DailyAuditJob:
    """
    Daily audit job that:
    1. Grades yesterday's predictions
    2. Calculates feature bias
    3. Adjusts weights
    4. Logs results
    """
    
    def __init__(self, auto_grader=None, training_pipeline=None):
        self.auto_grader = auto_grader
        self.training_pipeline = training_pipeline
        self.last_run = None
        self.last_results = {}
    
    def run(self):
        """Execute daily audit for all sports."""
        logger.info("=" * 50)
        logger.info("⏰ DAILY AUDIT STARTING")
        logger.info(f"   Time: {datetime.now().isoformat()}")
        logger.info("=" * 50)
        
        self.last_run = datetime.now()
        results = {
            "timestamp": self.last_run.isoformat(),
            "sports": {}
        }
        
        from data_dir import SUPPORTED_SPORTS
        for sport in SUPPORTED_SPORTS:
            try:
                sport_result = self.audit_sport(sport)
                results["sports"][sport] = sport_result
                logger.info(f"[{sport}] Audit complete: {sport_result.get('summary', {})}")
            except Exception as e:
                logger.error(f"[{sport}] Audit failed: {e}")
                results["sports"][sport] = {"error": str(e)}
        
        # Save results
        self.last_results = results
        self._save_audit_log(results)
        self._save_daily_lesson(results)
        
        logger.info("=" * 50)
        logger.info("✅ DAILY AUDIT COMPLETE")
        logger.info("=" * 50)
        
        return results
    
    def audit_sport(self, sport: str) -> Dict:
        """Audit a single sport."""
        sport = sport.upper()
        result = {
            "sport": sport,
            "graded": 0,
            "bias": {},
            "weights_adjusted": False,
            "retrain_triggered": False,
            "reconciliation_skipped": []
        }

        if not self.auto_grader:
            return {"error": "Auto-grader not initialized"}

        # Reload predictions from grader_store to ensure fresh data
        try:
            self.auto_grader._load_state()
        except Exception as e:
            logger.warning(f"[{sport}] Failed to reload predictions: {e}")

        # Define all stat types: prop_stat_types + game_stat_types
        prop_stat_types = SchedulerConfig.SPORT_STATS.get(sport, ["points"])
        game_stat_types = ["spread", "total", "moneyline", "sharp"]
        all_stat_types = prop_stat_types + game_stat_types

        # Grade predictions for each stat type
        for stat_type in all_stat_types:
            try:
                # Calculate bias
                bias = self.auto_grader.calculate_bias(sport, stat_type, days_back=1)
                result["bias"][stat_type] = bias

                # Check if weights need adjustment
                if self._should_adjust_weights(bias):
                    # Use reconciliation-aware adjustment to prevent conflicts with trap learning
                    adjustment = self.auto_grader.adjust_weights_with_reconciliation(
                        sport, stat_type, days_back=1, apply_changes=True
                    )
                    if adjustment and adjustment.get("applied"):
                        result["weights_adjusted"] = True
                        logger.info(f"[{sport}/{stat_type}] Weights adjusted: {adjustment}")
                    elif adjustment and adjustment.get("reconciliation_skipped"):
                        result["reconciliation_skipped"].append(stat_type)
                        logger.info(f"[{sport}/{stat_type}] Skipped due to trap reconciliation")

                # Check if retrain needed
                if self._should_retrain(bias):
                    result["retrain_triggered"] = True
                    logger.warning(f"[{sport}/{stat_type}] Retrain triggered due to high MAE")
                    if self.training_pipeline:
                        self.training_pipeline.train_sport(sport, stat_type, epochs=30)

            except Exception as e:
                logger.warning(f"[{sport}/{stat_type}] Bias calculation failed: {e}")

        # Get summary stats
        try:
            audit_summary = self.auto_grader.get_audit_summary(sport)
            result["summary"] = audit_summary
            result["graded"] = audit_summary.get("total_graded", 0)
        except Exception:
            pass

        return result

    def _should_adjust_weights(self, bias: Dict) -> bool:
        """Check if weights should be adjusted based on bias."""
        if not bias:
            return False

        # Access factor_bias from the actual bias response structure
        factor_bias = bias.get("factor_bias", {})
        if not factor_bias:
            return False

        # Adjust if any feature correlation exceeds threshold
        for feature in ["vacuum", "defense", "pace", "lstm", "officials"]:
            feature_data = factor_bias.get(feature, {})
            correlation = feature_data.get("correlation", 0) if isinstance(feature_data, dict) else 0
            if abs(correlation) > 0.3:  # Significant correlation (scaled appropriately)
                return True

        return False
    
    def _should_retrain(self, bias: Dict) -> bool:
        """Check if model should be retrained."""
        if not bias:
            return False

        # Access overall metrics from the actual bias response structure
        overall = bias.get("overall", {})
        if not overall:
            return False

        mae = overall.get("mean_error", 0)
        hit_rate_pct = overall.get("hit_rate", 50)  # This is a percentage (0-100)
        hit_rate = hit_rate_pct / 100.0 if hit_rate_pct > 1 else hit_rate_pct  # Convert to decimal

        return (mae > SchedulerConfig.RETRAIN_MAE_THRESHOLD or
                hit_rate < SchedulerConfig.RETRAIN_HIT_RATE_THRESHOLD)
    
    def _save_audit_log(self, results: Dict):
        """Save audit results to file."""
        from data_dir import AUDIT_LOGS
        log_dir = AUDIT_LOGS
        os.makedirs(log_dir, exist_ok=True)
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_path = os.path.join(log_dir, f"audit_{date_str}.json")
        
        try:
            with open(log_path, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Audit log saved: {log_path}")
        except Exception as e:
            logger.error(f"Failed to save audit log: {e}")

    def _generate_daily_lesson(self, results: Dict) -> Dict:
        """Generate a short, structured daily lesson from audit results."""
        now = now_et()
        date_et = now.strftime("%Y-%m-%d")
        sports = results.get("sports", {}) if isinstance(results, dict) else {}

        total_graded = 0
        weighted_hit = 0.0
        weighted_mae = 0.0
        best_sport = None
        worst_sport = None
        best_hit = None
        worst_hit = None
        adjusted_sports = []
        retrain_sports = []

        for sport, data in sports.items():
            if not isinstance(data, dict):
                continue
            summary = data.get("summary", {}) or {}
            graded = summary.get("total_graded", 0) or data.get("graded", 0) or 0
            hit_rate = summary.get("hit_rate")
            mae = summary.get("mae")

            if isinstance(graded, (int, float)) and graded > 0:
                total_graded += graded
                if isinstance(hit_rate, (int, float)):
                    weighted_hit += hit_rate * graded
                if isinstance(mae, (int, float)):
                    weighted_mae += mae * graded

            if isinstance(hit_rate, (int, float)):
                if best_hit is None or hit_rate > best_hit:
                    best_hit = hit_rate
                    best_sport = sport
                if worst_hit is None or hit_rate < worst_hit:
                    worst_hit = hit_rate
                    worst_sport = sport

            if data.get("weights_adjusted"):
                adjusted_sports.append(sport)
            if data.get("retrain_triggered"):
                retrain_sports.append(sport)

        overall_hit = round(weighted_hit / total_graded, 3) if total_graded else None
        overall_mae = round(weighted_mae / total_graded, 3) if total_graded else None

        bullets = []
        if total_graded:
            bullets.append(
                f"Graded {int(total_graded)} picks. "
                f"Hit rate {overall_hit if overall_hit is not None else 'n/a'}, "
                f"MAE {overall_mae if overall_mae is not None else 'n/a'}."
            )
        else:
            bullets.append("No completed games to grade. Learning loop paused for today.")

        if best_sport and worst_sport and best_sport != worst_sport:
            bullets.append(
                f"Best sport: {best_sport} (hit {best_hit:.3f}). "
                f"Worst sport: {worst_sport} (hit {worst_hit:.3f})."
            )
        elif best_sport:
            bullets.append(f"Sport signal: {best_sport} hit {best_hit:.3f}.")

        if adjusted_sports or retrain_sports:
            if adjusted_sports:
                bullets.append(f"Weights adjusted for: {', '.join(adjusted_sports)}.")
            if retrain_sports:
                bullets.append(f"Retrain triggered for: {', '.join(retrain_sports)}.")
        else:
            bullets.append("No weight adjustments or retrains triggered today.")

        return {
            "date_et": date_et,
            "generated_at_et": now.isoformat(),
            "total_graded": int(total_graded),
            "overall_hit_rate": overall_hit,
            "overall_mae": overall_mae,
            "best_sport": best_sport,
            "worst_sport": worst_sport,
            "weights_adjusted": adjusted_sports,
            "retrain_triggered": retrain_sports,
            "bullets": bullets,
        }

    def _save_daily_lesson(self, results: Dict):
        """Persist daily lesson to audit logs (JSON + JSONL)."""
        from data_dir import AUDIT_LOGS
        log_dir = AUDIT_LOGS
        os.makedirs(log_dir, exist_ok=True)

        lesson = self._generate_daily_lesson(results)
        date_et = lesson.get("date_et", now_et().strftime("%Y-%m-%d"))
        lesson_path = os.path.join(log_dir, f"lesson_{date_et}.json")
        lesson_jsonl = os.path.join(log_dir, "lessons.jsonl")

        try:
            with open(lesson_path, "w") as f:
                json.dump(lesson, f, indent=2)
            with open(lesson_jsonl, "a") as f:
                f.write(json.dumps(lesson) + "\n")
            logger.info(f"Daily lesson saved: {lesson_path}")
        except Exception as e:
            logger.error(f"Failed to save daily lesson: {e}")


# ============================================
# CLEANUP JOB
# ============================================

class CleanupJob:
    """Cleans up old prediction logs."""
    
    def __init__(self, auto_grader=None):
        self.auto_grader = auto_grader
    
    def run(self):
        """Remove predictions older than configured days."""
        logger.info("🧹 Running cleanup job...")
        
        cutoff = datetime.now() - timedelta(days=SchedulerConfig.KEEP_PREDICTIONS_DAYS)
        removed = 0
        
        if self.auto_grader:
            for sport, predictions in self.auto_grader.predictions.items():
                original_count = len(predictions)
                # Filter to keep only recent predictions
                self.auto_grader.predictions[sport] = [
                    p for p in predictions
                    if datetime.fromisoformat(p.timestamp) > cutoff
                ]
                removed += original_count - len(self.auto_grader.predictions[sport])
        
        # Cleanup old audit logs
        from data_dir import AUDIT_LOGS
        log_dir = AUDIT_LOGS
        if os.path.exists(log_dir):
            for filename in os.listdir(log_dir):
                filepath = os.path.join(log_dir, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_time < cutoff:
                    os.remove(filepath)
                    removed += 1
        
        logger.info(f"🧹 Cleanup complete: removed {removed} old records")
        return {"removed": removed}


# ============================================
# SCHEDULER
# ============================================

class DailyScheduler:
    """
    Manages scheduled tasks.
    """
    
    def __init__(self, auto_grader=None, training_pipeline=None):
        self.auto_grader = auto_grader
        self.training_pipeline = training_pipeline
        self.audit_job = DailyAuditJob(auto_grader, training_pipeline)
        self.cleanup_job = CleanupJob(auto_grader)
        self.scheduler = None
        self.running = False
        self._thread = None
    
    def start(self):
        """Start the scheduler."""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        if SCHEDULER_AVAILABLE:
            self._start_apscheduler()
        else:
            self._start_simple_scheduler()
        
        self.running = True
        logger.info("⏰ Daily scheduler started")
    
    def _start_apscheduler(self):
        """Start using APScheduler."""
        self.scheduler = BackgroundScheduler()

        # Daily audit at 6 AM
        self.scheduler.add_job(
            self.audit_job.run,
            CronTrigger(hour=SchedulerConfig.AUDIT_HOUR, minute=SchedulerConfig.AUDIT_MINUTE),
            id="daily_audit",
            name="Daily Audit"
        )

        # Weekly cleanup on Sunday at 3 AM
        self.scheduler.add_job(
            self.cleanup_job.run,
            CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="weekly_cleanup",
            name="Weekly Cleanup"
        )

        # Auto-grade picks every 30 minutes (v14.9)
        if RESULT_FETCHER_AVAILABLE:
            self.scheduler.add_job(
                self._run_auto_grade,
                IntervalTrigger(minutes=30),
                id="auto_grade",
                name="Auto-Grade Picks"
            )
            logger.info("Auto-grading enabled: runs every 30 minutes")

        # Cache pre-warm at 11:00 AM, 4:30 PM, 6:30 PM ET (v15.0)
        if WARM_AVAILABLE:
            for hour, minute, label in [(11, 0, "morning"), (16, 30, "afternoon"), (18, 30, "evening")]:
                self.scheduler.add_job(
                    self._run_warm_cache,
                    CronTrigger(hour=hour, minute=minute, timezone="America/New_York"),
                    id=f"warm_cache_{label}",
                    name=f"Cache Pre-Warm ({label})"
                )
            logger.info("Cache pre-warm enabled: 11:00 AM, 4:30 PM, 6:30 PM ET")

            # Startup warm: 2 minutes after boot (uses same lock path as scheduled warm)
            def _startup_warm():
                """Startup warm with stampede guard."""
                if not WARM_AVAILABLE:
                    return
                import pytz
                ET = pytz.timezone("America/New_York")
                today_str = datetime.now(ET).strftime("%Y-%m-%d")
                lock_key = f"warm_startup:{today_str}"
                if not api_cache.acquire_lock(lock_key, ttl=300):
                    logger.info("Startup warm skipped: another instance already warming")
                    return
                self._run_warm_cache()
            threading.Timer(120, _startup_warm).start()
            logger.info("Startup cache warm scheduled in 2 minutes")

        # v16.1: Weekly LSTM retraining (Sundays 4 AM ET)
        if ML_RETRAIN_AVAILABLE:
            self.scheduler.add_job(
                self._run_lstm_retrain,
                CronTrigger(day_of_week="sun", hour=4, minute=0, timezone="America/New_York"),
                id="lstm_retrain_weekly",
                name="Weekly LSTM Retrain"
            )
            logger.info("LSTM retraining enabled: runs weekly on Sundays at 4 AM ET")

            # v16.1: Daily ensemble retraining (6:45 AM ET, after grading at 6:30 AM)
            self.scheduler.add_job(
                self._run_ensemble_retrain,
                CronTrigger(hour=6, minute=45, timezone="America/New_York"),
                id="ensemble_retrain_daily",
                name="Daily Ensemble Retrain"
            )
            logger.info("Ensemble retraining enabled: runs daily at 6:45 AM ET")

        # v17.6: Line snapshot capture (every 30 minutes on game days)
        # Captures spread/total values across books for Hurst Exponent analysis
        try:
            from database import DB_ENABLED
            if DB_ENABLED:
                self.scheduler.add_job(
                    self._run_line_snapshot_capture,
                    IntervalTrigger(minutes=30),
                    id="line_snapshot_capture",
                    name="Line Snapshot Capture"
                )
                logger.info("Line snapshot capture enabled: runs every 30 minutes")

                # v17.6: Update season extremes daily at 5 AM ET
                self.scheduler.add_job(
                    self._run_update_season_extremes,
                    CronTrigger(hour=5, minute=0, timezone="America/New_York"),
                    id="update_season_extremes",
                    name="Update Season Extremes"
                )
                logger.info("Season extremes update enabled: runs daily at 5 AM ET")

                # v18.0: Weekly officials tendency recalculation (Sundays 3 AM ET)
                self.scheduler.add_job(
                    self._run_officials_tendency_update,
                    CronTrigger(day_of_week="sun", hour=3, minute=0, timezone="America/New_York"),
                    id="officials_tendency_update",
                    name="Weekly Officials Tendency Recalculation"
                )
                logger.info("Officials tendency update enabled: runs weekly on Sundays at 3 AM ET")
        except ImportError:
            logger.warning("Database not available - line history capture disabled")

        # v19.0: Post-game trap evaluation (daily at 6:15 AM ET, after grading)
        try:
            self.scheduler.add_job(
                self._run_trap_evaluation,
                CronTrigger(hour=6, minute=15, timezone="America/New_York"),
                id="trap_evaluation",
                name="Post-Game Trap Evaluation"
            )
            logger.info("Trap evaluation enabled: runs daily at 6:15 AM ET (after grading)")
        except Exception as e:
            logger.warning("Failed to schedule trap evaluation: %s", e)

        # v20.16: Daily team model training (7 AM ET, after all grading complete)
        # Updates LSTM, Matchup, and Ensemble models from graded picks
        try:
            self.scheduler.add_job(
                self._run_team_model_train,
                CronTrigger(hour=7, minute=0, timezone="America/New_York"),
                id="team_model_train",
                name="Daily Team Model Training"
            )
            logger.info("Team model training enabled: runs daily at 7 AM ET")
        except Exception as e:
            logger.warning("Failed to schedule team model training: %s", e)

        # v20.22: Ensemble sklearn regressor training (7:15 AM ET, after team models)
        # Trains XGBoost/LightGBM/RandomForest regressors from graded picks
        try:
            self.scheduler.add_job(
                self._run_ensemble_regressor_train,
                CronTrigger(hour=7, minute=15, timezone="America/New_York"),
                id="ensemble_regressor_train",
                name="Ensemble Sklearn Regressor Training"
            )
            logger.info("Ensemble sklearn regressor training enabled: runs daily at 7:15 AM ET")
        except Exception as e:
            logger.warning("Failed to schedule ensemble regressor training: %s", e)

        # v20.16.4: Training verification (7:30 AM ET, verifies 7 AM training ran)
        # Checks training_telemetry and logs WARNING if training didn't execute
        try:
            self.scheduler.add_job(
                self._run_training_verification,
                CronTrigger(hour=7, minute=30, timezone="America/New_York"),
                id="training_verification",
                name="Training Verification Check"
            )
            logger.info("Training verification enabled: runs daily at 7:30 AM ET")
        except Exception as e:
            logger.warning("Failed to schedule training verification: %s", e)

        # v20.23: Player cache warming (6:47 AM ET, before picks generation)
        # Pre-fetches NBA player data from BallDontLie for expected props
        try:
            self.scheduler.add_job(
                self._run_player_cache_warm,
                CronTrigger(hour=6, minute=47, timezone="America/New_York"),
                id="player_cache_warm",
                name="Player Data Cache Warm"
            )
            logger.info("Player cache warming enabled: runs daily at 6:47 AM ET")
        except Exception as e:
            logger.warning("Failed to schedule player cache warming: %s", e)

        self.scheduler.start()
        logger.info("APScheduler started with daily audit at 6 AM")

    def _run_auto_grade(self):
        """Run auto-grading in an async context."""
        if not RESULT_FETCHER_AVAILABLE:
            return

        try:
            # Create event loop for async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(scheduled_auto_grade())
                logger.info(f"Auto-grade complete: {result}")
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Auto-grade failed: {e}")

    def _run_team_model_train(self):
        """
        v20.16: Train team ML models from graded picks.

        Updates:
        - Team scoring cache (for LSTM predictions)
        - Matchup matrix (for team-vs-team predictions)
        - Ensemble weights (learns what combinations work)

        Runs daily at 7 AM ET, after grading is complete.
        """
        try:
            from scripts.train_team_models import train_all
            result = train_all(days=7)  # Process last 7 days
            logger.info(f"Team model training complete: {result}")
        except ImportError:
            # Fallback to direct call
            try:
                from team_ml_models import (
                    get_team_cache, get_team_matchup, get_game_ensemble
                )
                from grader_store import load_predictions

                picks = load_predictions()
                graded = [p for p in picks if p.get('result') in ['WIN', 'LOSS']]
                logger.info(f"Training team models on {len(graded)} graded picks")

                # Just trigger the models to initialize and save any updates
                cache = get_team_cache()
                matchup = get_team_matchup()
                ensemble = get_game_ensemble()

                logger.info("Team models initialized and ready")
            except Exception as inner_e:
                logger.error(f"Team model training fallback failed: {inner_e}")
        except Exception as e:
            logger.error(f"Team model training failed: {e}")

    def _run_ensemble_regressor_train(self):
        """
        v20.22: Train sklearn ensemble regressors from graded picks.

        Trains XGBoost, LightGBM, and RandomForest regressors on:
        - 12 features: ai_score, research_score, esoteric_score, jarvis_score,
          context_modifier, confluence_boost, jason_sim_boost, msrf_boost,
          line, odds_american, rest_factor, injury_impact
        - Target: binary hit classification (WIN=1, LOSS=0)

        Saves trained models to /data/models/ensemble_sklearn_regressors.joblib
        for EnsembleStackingModel to load on next restart.

        NOTE: Models are trained in SHADOW MODE by default (telemetry only).
        Set ENSEMBLE_SKLEARN_ENABLED=true to use for live predictions.

        Runs daily at 7:15 AM ET (after team model training at 7 AM).
        """
        logger.info("🎯 Starting ensemble sklearn regressor training...")
        try:
            # Try standard import first
            try:
                from scripts.train_ensemble_regressors import train_all
            except ImportError:
                # Fallback: add repo root to path for scripts.* imports
                import sys
                repo_root = os.path.dirname(__file__)
                if repo_root not in sys.path:
                    sys.path.insert(0, repo_root)
                from scripts.train_ensemble_regressors import train_all

            result = train_all(days=7, min_samples=50)

            status = result.get('status', 'unknown')
            logger.info(f"Ensemble regressor training complete: {status}")

            if status == 'SKIPPED_MISSING_DEPS':
                # Non-fatal - log once and continue
                logger.warning("   Skipped due to missing deps: %s", result.get('missing_deps', []))
            elif status == 'success' and result.get('training_metrics'):
                meta_acc = result['training_metrics'].get('meta_accuracy', 0)
                logger.info(f"   Meta model accuracy: {meta_acc:.2%}")
                logger.info("   NOTE: Models in SHADOW MODE (telemetry only)")
            elif result.get('error'):
                logger.warning("   Error: %s", result.get('error'))

        except ImportError as e:
            logger.warning("train_ensemble_regressors script not available: %s", e)
        except Exception as e:
            logger.error(f"Ensemble regressor training failed: {e}")

    def _run_training_verification(self):
        """
        v20.16.4: Verify that 7 AM training job actually ran.

        Checks:
        1. last_train_run_at is from today
        2. Artifact files have recent mtime (within last hour)
        3. training_health is HEALTHY

        Logs WARNING if training didn't execute.
        Runs daily at 7:30 AM ET (30 min after training).
        """
        from zoneinfo import ZoneInfo
        ET = ZoneInfo("America/New_York")
        now_et_time = datetime.now(ET)
        today_str = now_et_time.strftime("%Y-%m-%d")

        logger.info("🔍 Training verification starting for %s...", today_str)

        alerts = []
        training_ran = False

        try:
            # Check training telemetry from team_ml_models
            from team_ml_models import get_game_ensemble

            ensemble = get_game_ensemble()
            telemetry = ensemble.training_telemetry

            last_train_run_at = telemetry.get("last_train_run_at")
            graded_samples_seen = telemetry.get("graded_samples_seen", 0)
            samples_used = telemetry.get("samples_used_for_training", 0)

            if last_train_run_at:
                # Parse and check if it's from today
                try:
                    if isinstance(last_train_run_at, str):
                        last_run = datetime.fromisoformat(last_train_run_at.replace('Z', '+00:00'))
                    else:
                        last_run = last_train_run_at

                    # Make timezone aware if needed
                    if last_run.tzinfo is None:
                        last_run = last_run.replace(tzinfo=ET)

                    last_run_date = last_run.astimezone(ET).strftime("%Y-%m-%d")
                    last_run_hour = last_run.astimezone(ET).hour

                    if last_run_date == today_str and last_run_hour >= 7:
                        training_ran = True
                        logger.info("✅ Training ran today at %s", last_run.astimezone(ET).isoformat())
                        logger.info("   Graded samples seen: %d, Used for training: %d",
                                   graded_samples_seen, samples_used)
                    else:
                        alerts.append(f"last_train_run_at is {last_run_date} {last_run_hour}:00, expected {today_str} 07:00+")
                except Exception as e:
                    alerts.append(f"Failed to parse last_train_run_at: {e}")
            else:
                alerts.append("last_train_run_at is NULL - training never ran")

            # Check training_health status
            training_status = ensemble.training_status
            if training_status != "TRAINED":
                alerts.append(f"training_status is {training_status}, expected TRAINED")

        except ImportError as e:
            alerts.append(f"Could not import team_ml_models: {e}")
        except Exception as e:
            alerts.append(f"Error checking training telemetry: {e}")

        # Check artifact file mtimes
        try:
            import os
            from data_dir import GRADER_DATA_DIR

            artifact_files = [
                "team_data_cache.json",
                "matchup_matrix.json",
                "ensemble_weights.json"
            ]

            for filename in artifact_files:
                filepath = os.path.join(GRADER_DATA_DIR, filename)
                if os.path.exists(filepath):
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath), tz=ET)
                    hours_old = (now_et_time - mtime).total_seconds() / 3600

                    if hours_old > 1.5:  # More than 1.5 hours old
                        alerts.append(f"{filename} is {hours_old:.1f} hours old (expected <1.5h)")
                    else:
                        logger.info("   Artifact %s: %.1f hours old", filename, hours_old)
                else:
                    alerts.append(f"{filename} does not exist")

        except Exception as e:
            alerts.append(f"Error checking artifact files: {e}")

        # Log results
        if training_ran and not alerts:
            logger.info("✅ Training verification PASSED - all checks OK")
        elif training_ran and alerts:
            logger.warning("⚠️ Training verification PARTIAL - training ran but: %s", alerts)
        else:
            logger.error("❌ TRAINING VERIFICATION FAILED - 7 AM training did NOT execute!")
            for alert in alerts:
                logger.error("   - %s", alert)
            logger.error("   ACTION: Check scheduler logs, consider manual trigger via /live/grader/train-team-models")

            # Write alert to file for external monitoring
            try:
                from data_dir import AUDIT_LOGS
                alert_file = os.path.join(AUDIT_LOGS, f"training_alert_{today_str}.json")
                alert_data = {
                    "date_et": today_str,
                    "check_time_et": now_et_time.isoformat(),
                    "training_ran": False,
                    "alerts": alerts,
                    "action": "Check scheduler logs, trigger manual training"
                }
                with open(alert_file, "w") as f:
                    json.dump(alert_data, f, indent=2)
                logger.error("   Alert written to: %s", alert_file)
            except Exception as e:
                logger.error("   Failed to write alert file: %s", e)
    
    def _run_player_cache_warm(self):
        """
        v20.23: Pre-warm NBA player data cache before picks generation.

        Fetches player context (season averages, birth dates) from BallDontLie
        for likely prop players (starters + top bench) before daily picks run.

        Runs at 6:47 AM ET, before cache warm and picks generation.
        """
        from zoneinfo import ZoneInfo
        ET = ZoneInfo("America/New_York")
        today_str = datetime.now(ET).strftime("%Y-%m-%d")

        logger.info("🏀 Starting player cache warm for %s...", today_str)

        try:
            # Try to import PlayerDataService
            from services.player_data_service import PlayerDataService

            # Get today's NBA games to determine likely players
            # We'll pre-fetch common NBA prop players
            players_to_warm = []

            try:
                # Try to get today's games from odds API
                from get_props import get_props
                nba_events = get_props("NBA")

                if nba_events:
                    # Extract player names from prop markets
                    for event in nba_events[:10]:  # Limit to first 10 games
                        for bm in event.get("bookmakers", []):
                            for mkt in bm.get("markets", []):
                                for outcome in mkt.get("outcomes", []):
                                    desc = outcome.get("description", "")
                                    if desc and len(desc) > 3:
                                        players_to_warm.append(desc)

                    # Dedupe
                    players_to_warm = list(dict.fromkeys(players_to_warm))[:50]
                    logger.info("   Found %d likely NBA players from props", len(players_to_warm))

            except Exception as e:
                logger.debug("Could not fetch props for player list: %s", e)

            # v20.23: No hardcoded fallback - only warm from actual props
            # If we couldn't get props, skip warming (don't use stale player list)
            if len(players_to_warm) < 5:
                logger.info("   Skipping cache warm: not enough players from props (%d)", len(players_to_warm))
                return

            # Run async cache warming using asyncio.run() (safer pattern)
            import asyncio
            result = asyncio.run(
                PlayerDataService.warm_cache_for_players(players_to_warm)
            )
            logger.info("✅ Player cache warm complete: warmed=%d, errors=%d, cache_size=%d",
                       result.get("warmed", 0), result.get("errors", 0), result.get("cache_size", 0))

        except ImportError as e:
            logger.warning("PlayerDataService not available for cache warming: %s", e)
        except Exception as e:
            logger.error("Player cache warm failed: %s", e)

    def _run_warm_cache(self):
        """Pre-warm best-bets cache in an async context."""
        if not WARM_AVAILABLE:
            return
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(warm_best_bets_cache())
            finally:
                loop.close()
        except Exception as e:
            logger.error("Cache warm failed: %s", e)

    def _run_lstm_retrain(self):
        """
        v18.1: Weekly LSTM model retraining (enhanced).

        Uses enhanced LSTM trainer with early stopping, model versioning,
        and metric logging. Only runs if sufficient graded data is available.
        """
        if not ML_RETRAIN_AVAILABLE:
            return

        logger.info("🧠 Starting weekly LSTM retrain (enhanced)...")
        try:
            # v18.1: Use enhanced LSTM trainer
            import subprocess
            import sys

            script_path = os.path.join(os.path.dirname(__file__), "scripts", "train_lstm_enhanced.py")

            if not os.path.exists(script_path):
                # Fallback to old method
                logger.warning("Enhanced LSTM trainer not found, trying legacy...")
                try:
                    from lstm_training_pipeline import LSTMTrainingPipeline
                    pipeline = LSTMTrainingPipeline()
                    stats = pipeline.get_data_stats()
                    if stats.get("total_samples", 0) < 500:
                        logger.info("LSTM retrain skipped: only %d samples (need 500+)",
                                  stats.get("total_samples", 0))
                        return
                    results = pipeline.retrain_all_models(min_samples=100)
                    logger.info("🧠 LSTM retrain complete (legacy): %s", results)
                except ImportError:
                    logger.warning("LSTM training pipeline not available")
                return

            # Run enhanced training for all models
            result = subprocess.run(
                [sys.executable, script_path, "--all", "--min-samples", "500"],
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout
            )

            if result.returncode == 0:
                logger.info("🧠 LSTM retrain complete (enhanced):\n%s",
                          result.stdout[-1000:] if result.stdout else "")
            else:
                logger.warning("LSTM retrain exited with code %d: %s",
                             result.returncode, result.stderr[-500:] if result.stderr else "")

        except subprocess.TimeoutExpired:
            logger.error("LSTM retrain timed out after 30 minutes")
        except Exception as e:
            logger.error("LSTM retrain failed: %s", e)

    def _run_ensemble_retrain(self):
        """
        v18.1: Daily ensemble model retraining (enhanced).

        Uses enhanced ensemble trainer with cross-validation, hyperparameter
        tuning, and Platt scaling calibration. Runs after daily grading.
        """
        if not ML_RETRAIN_AVAILABLE:
            return

        logger.info("🎯 Starting daily ensemble retrain (enhanced)...")
        try:
            import subprocess
            import sys

            # v18.1: Try enhanced training script first
            enhanced_script = os.path.join(os.path.dirname(__file__), "scripts", "train_ensemble_enhanced.py")
            legacy_script = os.path.join(os.path.dirname(__file__), "scripts", "train_ensemble.py")

            if os.path.exists(enhanced_script):
                script_path = enhanced_script
                # Use fast tuning for daily runs (full tuning on Sundays)
                from datetime import datetime
                import pytz
                ET = pytz.timezone("America/New_York")
                is_sunday = datetime.now(ET).weekday() == 6

                args = [sys.executable, script_path, "--min-picks", "100"]
                if not is_sunday:
                    args.append("--no-tuning")  # Skip tuning on non-Sundays for speed

                timeout = 600 if is_sunday else 300  # Longer timeout for Sunday tuning
            elif os.path.exists(legacy_script):
                script_path = legacy_script
                args = [sys.executable, script_path, "--min-picks", "100"]
                timeout = 300
            else:
                logger.warning("No ensemble training script found")
                return

            # Run training
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode == 0:
                logger.info("🎯 Ensemble retrain complete:\n%s", result.stdout[-500:] if result.stdout else "")
            else:
                logger.warning("Ensemble retrain exited with code %d: %s",
                             result.returncode, result.stderr[-500:] if result.stderr else "")

        except subprocess.TimeoutExpired:
            logger.error("Ensemble retrain timed out")
        except Exception as e:
            logger.error("Ensemble retrain failed: %s", e)

    def _run_line_snapshot_capture(self):
        """
        v17.6: Capture line snapshots for Hurst Exponent analysis.

        Fetches current lines from Odds API and stores in line_snapshots table.
        Runs every 30 minutes during game days.
        """
        logger.info("📈 Starting line snapshot capture...")
        try:
            from database import get_db, save_line_snapshot, DB_ENABLED
            if not DB_ENABLED:
                logger.warning("Database not enabled - skipping line snapshot capture")
                return

            from data_dir import SUPPORTED_SPORTS
            import httpx

            # Get games from Odds API for each sport
            ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
            if not ODDS_API_KEY:
                logger.warning("ODDS_API_KEY not set - skipping line snapshot capture")
                return

            ODDS_SPORT_KEYS = {
                "NBA": "basketball_nba",
                "NFL": "americanfootball_nfl",
                "MLB": "baseball_mlb",
                "NHL": "icehockey_nhl",
                "NCAAB": "basketball_ncaab"
            }

            snapshots_saved = 0
            with get_db() as db:
                if not db:
                    return

                for sport in SUPPORTED_SPORTS:
                    sport_key = ODDS_SPORT_KEYS.get(sport.upper())
                    if not sport_key:
                        continue

                    try:
                        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
                        response = httpx.get(url, params={
                            "apiKey": ODDS_API_KEY,
                            "regions": "us",
                            "markets": "spreads,totals",
                            "oddsFormat": "american"
                        }, timeout=30.0)

                        if response.status_code != 200:
                            logger.warning("Odds API error for %s: %d", sport, response.status_code)
                            continue

                        games = response.json()

                        for game in games:
                            event_id = game.get("id", "")
                            home_team = game.get("home_team", "")
                            away_team = game.get("away_team", "")
                            commence_time = game.get("commence_time")

                            # Parse game start time
                            game_start = None
                            if commence_time:
                                try:
                                    from datetime import datetime as dt
                                    game_start = dt.fromisoformat(commence_time.replace("Z", "+00:00"))
                                except Exception:
                                    pass

                            # Extract lines from first bookmaker (consensus)
                            for bm in game.get("bookmakers", [])[:3]:  # Top 3 books
                                book_name = bm.get("key", "unknown")
                                spread = None
                                spread_odds = None
                                total = None
                                total_odds = None

                                for market in bm.get("markets", []):
                                    if market.get("key") == "spreads":
                                        for outcome in market.get("outcomes", []):
                                            if outcome.get("name") == home_team:
                                                spread = outcome.get("point")
                                                spread_odds = outcome.get("price")
                                                break
                                    elif market.get("key") == "totals":
                                        for outcome in market.get("outcomes", []):
                                            if outcome.get("name") == "Over":
                                                total = outcome.get("point")
                                                total_odds = outcome.get("price")
                                                break

                                if spread is not None or total is not None:
                                    save_line_snapshot(
                                        db=db,
                                        event_id=event_id,
                                        sport=sport.upper(),
                                        home_team=home_team,
                                        away_team=away_team,
                                        spread=spread,
                                        total=total,
                                        book=book_name,
                                        spread_odds=spread_odds,
                                        total_odds=total_odds,
                                        game_start_time=game_start
                                    )
                                    snapshots_saved += 1

                    except Exception as e:
                        logger.error("Line snapshot capture failed for %s: %s", sport, e)

            logger.info("📈 Line snapshot capture complete: %d snapshots saved", snapshots_saved)

        except ImportError as e:
            logger.warning("Line snapshot capture unavailable: %s", e)
        except Exception as e:
            logger.error("Line snapshot capture failed: %s", e)

    def _run_update_season_extremes(self):
        """
        v17.6: Update season extremes for Fibonacci Retracement.

        Calculates season high/low from historical line_snapshots data.
        Runs daily at 5 AM ET.
        """
        logger.info("📊 Updating season extremes...")
        try:
            from database import get_db, SeasonExtreme, LineSnapshot, DB_ENABLED
            if not DB_ENABLED:
                logger.warning("Database not enabled - skipping season extremes update")
                return

            from sqlalchemy import func
            import pytz
            ET = pytz.timezone("America/New_York")
            now_et = datetime.now(ET)

            # Determine current season
            if now_et.month >= 9:
                season = f"{now_et.year}-{str(now_et.year + 1)[2:]}"
            else:
                season = f"{now_et.year - 1}-{str(now_et.year)[2:]}"

            with get_db() as db:
                if not db:
                    return

                from data_dir import SUPPORTED_SPORTS
                updates = 0

                for sport in SUPPORTED_SPORTS:
                    # Get min/max spreads and totals from line_snapshots
                    try:
                        # Aggregate spread extremes
                        spread_stats = db.query(
                            func.min(LineSnapshot.spread).label("min_spread"),
                            func.max(LineSnapshot.spread).label("max_spread"),
                            func.avg(LineSnapshot.spread).label("avg_spread")
                        ).filter(
                            LineSnapshot.sport == sport.upper(),
                            LineSnapshot.spread.isnot(None)
                        ).first()

                        if spread_stats and spread_stats.min_spread is not None:
                            # Update or create season extreme for spread
                            existing = db.query(SeasonExtreme).filter(
                                SeasonExtreme.sport == sport.upper(),
                                SeasonExtreme.season == season,
                                SeasonExtreme.stat_type == "spread"
                            ).first()

                            if existing:
                                existing.season_low = spread_stats.min_spread
                                existing.season_high = spread_stats.max_spread
                                existing.current_value = spread_stats.avg_spread
                            else:
                                db.add(SeasonExtreme(
                                    sport=sport.upper(),
                                    season=season,
                                    stat_type="spread",
                                    season_low=spread_stats.min_spread,
                                    season_high=spread_stats.max_spread,
                                    current_value=spread_stats.avg_spread
                                ))
                            updates += 1

                        # Aggregate total extremes
                        total_stats = db.query(
                            func.min(LineSnapshot.total).label("min_total"),
                            func.max(LineSnapshot.total).label("max_total"),
                            func.avg(LineSnapshot.total).label("avg_total")
                        ).filter(
                            LineSnapshot.sport == sport.upper(),
                            LineSnapshot.total.isnot(None)
                        ).first()

                        if total_stats and total_stats.min_total is not None:
                            existing = db.query(SeasonExtreme).filter(
                                SeasonExtreme.sport == sport.upper(),
                                SeasonExtreme.season == season,
                                SeasonExtreme.stat_type == "total"
                            ).first()

                            if existing:
                                existing.season_low = total_stats.min_total
                                existing.season_high = total_stats.max_total
                                existing.current_value = total_stats.avg_total
                            else:
                                db.add(SeasonExtreme(
                                    sport=sport.upper(),
                                    season=season,
                                    stat_type="total",
                                    season_low=total_stats.min_total,
                                    season_high=total_stats.max_total,
                                    current_value=total_stats.avg_total
                                ))
                            updates += 1

                    except Exception as e:
                        logger.error("Season extremes update failed for %s: %s", sport, e)

            logger.info("📊 Season extremes update complete: %d records updated", updates)

        except ImportError as e:
            logger.warning("Season extremes update unavailable: %s", e)
        except Exception as e:
            logger.error("Season extremes update failed: %s", e)

    def _run_officials_tendency_update(self):
        """
        v18.0: Weekly officials tendency recalculation.

        Recalculates referee tendencies from game history for all sports.
        Uses data collected from OfficialGameRecord table.
        Runs weekly on Sundays at 3 AM ET.
        """
        logger.info("👨‍⚖️ Starting weekly officials tendency update...")
        try:
            from services.officials_tracker import officials_tracker

            if not officials_tracker.enabled:
                logger.warning("Officials tracker not enabled - skipping tendency update")
                return

            from data_dir import SUPPORTED_SPORTS
            total_updated = 0

            for sport in SUPPORTED_SPORTS:
                try:
                    tendencies = officials_tracker.calculate_tendencies(
                        sport=sport,
                        min_games=50  # Require 50+ games for sufficient sample
                    )
                    updated_count = len([t for t in tendencies.values()
                                       if t.get("sample_size_sufficient")])
                    total_updated += updated_count
                    logger.info("👨‍⚖️ %s: Updated %d official tendencies (%d with sufficient data)",
                              sport, len(tendencies), updated_count)
                except Exception as e:
                    logger.error("Officials tendency update failed for %s: %s", sport, e)

            logger.info("👨‍⚖️ Officials tendency update complete: %d officials with sufficient data",
                       total_updated)

        except ImportError as e:
            logger.warning("Officials tracker not available: %s", e)
        except Exception as e:
            logger.error("Officials tendency update failed: %s", e)

    def _run_trap_evaluation(self):
        """
        v19.0: Post-game trap evaluation.

        Evaluates pre-game traps against yesterday's game results.
        Runs daily at 6:15 AM ET (after grading completes at 6 AM).
        Applies weight adjustments when trap conditions are met.
        """
        logger.info("🪤 Starting post-game trap evaluation...")
        try:
            from trap_learning_loop import get_trap_loop, enrich_game_result

            trap_loop = get_trap_loop()
            active_traps = trap_loop.get_active_traps()

            if not active_traps:
                logger.info("🪤 No active traps to evaluate")
                return

            # Get yesterday's game results
            yesterday_results = self._fetch_yesterday_results()

            if not yesterday_results:
                logger.warning("🪤 No game results available for trap evaluation")
                return

            total_evaluations = 0
            triggered = 0
            applied = 0

            for trap in active_traps:
                # Get games for this trap's sport
                sport_results = yesterday_results.get(trap.sport, [])
                if trap.sport == "ALL":
                    # Combine all sports
                    sport_results = []
                    for games in yesterday_results.values():
                        sport_results.extend(games)

                for game in sport_results:
                    # Skip if trap is team-specific and team not in game
                    if trap.team:
                        game_teams = [game.get("home_team", ""), game.get("away_team", "")]
                        if trap.team not in game_teams:
                            continue

                    # Enrich game result with calculated fields
                    enriched_game = enrich_game_result(game)

                    # Evaluate trap
                    evaluation = trap_loop.evaluate_trap(trap, enriched_game)
                    total_evaluations += 1

                    if evaluation.condition_met:
                        triggered += 1
                        if evaluation.action_taken == "APPLIED":
                            applied += 1
                            logger.info("🪤 TRAP FIRED: %s | %s vs %s | adjustment=%s",
                                       trap.name,
                                       game.get("away_team", "?"),
                                       game.get("home_team", "?"),
                                       evaluation.adjustment_applied)

            logger.info("🪤 Trap evaluation complete: %d evaluations, %d triggered, %d adjustments applied",
                       total_evaluations, triggered, applied)

        except ImportError as e:
            logger.warning("Trap learning loop not available: %s", e)
        except Exception as e:
            logger.error("Trap evaluation failed: %s", e)

    def _fetch_yesterday_results(self) -> dict:
        """
        Fetch yesterday's game results for trap evaluation.

        Returns dict mapping sport -> list of game results.
        Each game result contains: home_team, away_team, home_score, away_score,
        result, margin, spread_result, over_under_result, etc.
        """
        from datetime import datetime, timedelta
        from core.time_et import now_et

        yesterday = (now_et() - timedelta(days=1)).strftime("%Y-%m-%d")
        results = {}

        try:
            # Try to get results from graded predictions
            from grader_store import load_predictions

            predictions = load_predictions(date_et=yesterday)

            # Group by sport and extract game-level results
            for pred in predictions:
                sport = pred.get("sport", "").upper()
                if sport not in results:
                    results[sport] = []

                # Build game result from graded prediction
                game_result = {
                    "event_id": pred.get("event_id"),
                    "game_date": yesterday,
                    "home_team": pred.get("home_team"),
                    "away_team": pred.get("away_team"),
                    "sport": sport,
                    # From grading
                    "result": pred.get("result"),  # WIN/LOSS
                    "actual_value": pred.get("actual_value"),
                    # Engine scores at bet time
                    "ai_score_was": pred.get("ai_score"),
                    "research_score_was": pred.get("research_score"),
                    "esoteric_score_was": pred.get("esoteric_score"),
                    "jarvis_score_was": pred.get("jarvis_score"),
                    "final_score_was": pred.get("final_score"),
                }

                # Dedupe by event_id
                existing_ids = [g.get("event_id") for g in results[sport]]
                if game_result["event_id"] not in existing_ids:
                    results[sport].append(game_result)

        except Exception as e:
            logger.warning("Could not load predictions for trap evaluation: %s", e)

        # Try to get actual scores from ESPN/BallDontLie
        try:
            from alt_data_sources.espn_lineups import get_espn_scoreboard, SPORT_MAPPING

            for sport, mapping in SPORT_MAPPING.items():
                try:
                    scoreboard = get_espn_scoreboard(mapping["sport"], mapping["league"])
                    events = scoreboard.get("events", [])

                    for event in events:
                        # Check if game is final
                        status = event.get("status", {}).get("type", {}).get("state", "")
                        if status != "post":
                            continue

                        competition = event.get("competitions", [{}])[0]
                        competitors = competition.get("competitors", [])

                        if len(competitors) < 2:
                            continue

                        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
                        away = next((c for c in competitors if c.get("homeAway") == "away"), {})

                        home_score = int(home.get("score", 0))
                        away_score = int(away.get("score", 0))
                        home_team = home.get("team", {}).get("displayName", "")
                        away_team = away.get("team", {}).get("displayName", "")

                        game_result = {
                            "event_id": event.get("id"),
                            "game_date": yesterday,
                            "home_team": home_team,
                            "away_team": away_team,
                            "home_score": home_score,
                            "away_score": away_score,
                            "total_points": home_score + away_score,
                            "sport": sport,
                        }

                        # Calculate result and margin
                        if home_score > away_score:
                            game_result["result"] = "win"  # Home win
                            game_result["margin"] = home_score - away_score
                        elif away_score > home_score:
                            game_result["result"] = "loss"  # Home loss
                            game_result["margin"] = away_score - home_score
                        else:
                            game_result["result"] = "push"
                            game_result["margin"] = 0

                        if sport not in results:
                            results[sport] = []

                        # Dedupe
                        existing_ids = [g.get("event_id") for g in results[sport]]
                        if game_result["event_id"] not in existing_ids:
                            results[sport].append(game_result)

                except Exception as e:
                    logger.debug("Could not get ESPN results for %s: %s", sport, e)

        except ImportError:
            logger.debug("ESPN integration not available for trap evaluation")

        return results

    def _start_simple_scheduler(self):
        """Fallback simple scheduler using threading."""
        def run_scheduler():
            last_audit_date = None
            last_auto_grade_time = None

            while self.running:
                now = datetime.now()
                today = now.date()

                # Check if we should run audit (6 AM, once per day)
                if (now.hour == SchedulerConfig.AUDIT_HOUR and
                    now.minute < 5 and
                    last_audit_date != today):

                    self.audit_job.run()
                    last_audit_date = today

                # Check if we should run auto-grade (every 30 minutes)
                if RESULT_FETCHER_AVAILABLE:
                    if last_auto_grade_time is None or (now - last_auto_grade_time).total_seconds() >= 1800:
                        self._run_auto_grade()
                        last_auto_grade_time = now

                # Sleep for 1 minute
                time.sleep(60)

        self._thread = threading.Thread(target=run_scheduler, daemon=True)
        self._thread.start()
        logger.info("Simple scheduler started (APScheduler not available)")
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None
        
        logger.info("⏰ Daily scheduler stopped")
    
    def run_audit_now(self) -> Dict:
        """Manually trigger audit."""
        logger.info("Manual audit triggered")
        return self.audit_job.run()
    
    def get_status(self) -> Dict:
        """Get scheduler status."""
        status = {
            "running": self.running,
            "scheduler_type": "apscheduler" if SCHEDULER_AVAILABLE else "simple",
            "last_audit": self.audit_job.last_run.isoformat() if self.audit_job.last_run else None,
            "next_audit": f"{SchedulerConfig.AUDIT_HOUR:02d}:{SchedulerConfig.AUDIT_MINUTE:02d} daily",
            "last_results": self.audit_job.last_results
        }
        
        if SCHEDULER_AVAILABLE and self.scheduler:
            jobs = []
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None
                })
            status["scheduled_jobs"] = jobs
        
        return status


# ============================================
# FASTAPI ROUTER
# ============================================

from fastapi import APIRouter, HTTPException

scheduler_router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

# Global scheduler instance (initialized in main app)
_scheduler: Optional[DailyScheduler] = None


def init_scheduler(auto_grader=None, training_pipeline=None) -> DailyScheduler:
    """Initialize the global scheduler."""
    global _scheduler
    _scheduler = DailyScheduler(auto_grader, training_pipeline)
    return _scheduler


def get_scheduler() -> Optional[DailyScheduler]:
    """Get the global scheduler instance."""
    return _scheduler


# Alias for backward compatibility (used by live_data_router status endpoint)
get_daily_scheduler = get_scheduler


@scheduler_router.get("/status")
async def scheduler_status():
    """Get scheduler status."""
    if not _scheduler:
        return {"status": "not_initialized"}
    return {
        "status": "success",
        "scheduler": _scheduler.get_status()
    }


@scheduler_router.post("/start")
async def start_scheduler():
    """Start the scheduler."""
    if not _scheduler:
        raise HTTPException(500, "Scheduler not initialized")
    
    _scheduler.start()
    return {"status": "started"}


@scheduler_router.post("/stop")
async def stop_scheduler():
    """Stop the scheduler."""
    if not _scheduler:
        raise HTTPException(500, "Scheduler not initialized")
    
    _scheduler.stop()
    return {"status": "stopped"}


@scheduler_router.post("/run-audit")
async def run_audit_now():
    """Manually trigger daily audit."""
    if not _scheduler:
        raise HTTPException(500, "Scheduler not initialized")
    
    result = _scheduler.run_audit_now()
    return {
        "status": "success",
        "result": result
    }


@scheduler_router.post("/run-cleanup")
async def run_cleanup_now():
    """Manually trigger cleanup."""
    if not _scheduler:
        raise HTTPException(500, "Scheduler not initialized")
    
    result = _scheduler.cleanup_job.run()
    return {
        "status": "success",
        "result": result
    }


# ============================================
# STANDALONE TEST
# ============================================

if __name__ == "__main__":
    logger.info("Testing Daily Scheduler...")

    scheduler = DailyScheduler()

    # Test manual audit
    logger.info("\nRunning manual audit...")
    result = scheduler.run_audit_now()
    logger.info(json.dumps(result, indent=2, default=str))

    # Test status
    logger.info("\nScheduler status:")
    logger.info(json.dumps(scheduler.get_status(), indent=2, default=str))
