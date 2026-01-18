"""
⏰ DAILY SCHEDULER v2.0
========================
Automated daily tasks for Bookie-o-em:

1. Grade yesterday's predictions (6 AM)
2. Adjust weights based on bias
3. Retrain LSTM if performance drops
4. Clean up old prediction logs
5. Fetch props twice daily (10 AM, 6 PM) - API credit optimization

All 5 Sports: NBA, NFL, MLB, NHL, NCAAB
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
import threading
import time

# APScheduler for cron-like scheduling
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not installed - using simple threading")


# ============================================
# CONFIGURATION
# ============================================

class SchedulerConfig:
    """Scheduler configuration."""

    # Audit time (6 AM ET)
    AUDIT_HOUR = 6
    AUDIT_MINUTE = 0

    # Props fetch times
    # Weekdays: 10 AM and 6 PM
    # Weekends: 10 AM, 12 PM, 2 PM, 6 PM (games all day)
    PROPS_FETCH_HOURS_WEEKDAY = [10, 18]  # 10 AM and 6 PM
    PROPS_FETCH_HOURS_WEEKEND = [10, 12, 14, 18]  # 10 AM, 12 PM, 2 PM, 6 PM
    PROPS_FETCH_MINUTE = 0

    # Props cache TTL - 8 hours to last between scheduled fetches
    PROPS_CACHE_TTL = 28800  # 8 hours in seconds

    # Retrain threshold
    RETRAIN_MAE_THRESHOLD = 5.0  # Retrain if MAE exceeds this
    RETRAIN_HIT_RATE_THRESHOLD = 0.48  # Retrain if hit rate below this

    # Cleanup
    KEEP_PREDICTIONS_DAYS = 30  # Keep 30 days of prediction history

    # Sports to fetch props for
    PROPS_SPORTS = ["nba", "nfl", "mlb", "nhl"]

    # Sports and default stats
    SPORT_STATS = {
        "NBA": ["points", "rebounds", "assists"],
        "NFL": ["passing_yards", "rushing_yards", "receiving_yards"],
        "MLB": ["hits", "total_bases", "strikeouts"],
        "NHL": ["points", "shots"],
        "NCAAB": ["points", "rebounds"]
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
        
        for sport in ["NBA", "NFL", "MLB", "NHL", "NCAAB"]:
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
            "retrain_triggered": False
        }
        
        if not self.auto_grader:
            return {"error": "Auto-grader not initialized"}
        
        # Get yesterday's predictions
        yesterday = datetime.now() - timedelta(days=1)
        
        # Grade predictions for each stat type
        for stat_type in SchedulerConfig.SPORT_STATS.get(sport, ["points"]):
            try:
                # Calculate bias
                bias = self.auto_grader.calculate_bias(sport, stat_type, days_back=1)
                result["bias"][stat_type] = bias
                
                # Check if weights need adjustment
                if self._should_adjust_weights(bias):
                    adjustment = self.auto_grader.adjust_weights(
                        sport, stat_type, days_back=1, apply_changes=True
                    )
                    result["weights_adjusted"] = True
                    logger.info(f"[{sport}/{stat_type}] Weights adjusted: {adjustment}")
                
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
        except:
            pass
        
        return result
    
    def _should_adjust_weights(self, bias: Dict) -> bool:
        """Check if weights should be adjusted based on bias."""
        if not bias:
            return False
        
        # Adjust if any feature bias exceeds threshold
        for feature in ["vacuum", "defense", "pace", "lstm", "officials"]:
            feature_bias = bias.get(f"{feature}_bias", 0)
            if abs(feature_bias) > 2.0:  # Significant bias
                return True
        
        return False
    
    def _should_retrain(self, bias: Dict) -> bool:
        """Check if model should be retrained."""
        if not bias:
            return False
        
        mae = bias.get("mae", 0)
        hit_rate = bias.get("hit_rate", 0.5)
        
        return (mae > SchedulerConfig.RETRAIN_MAE_THRESHOLD or 
                hit_rate < SchedulerConfig.RETRAIN_HIT_RATE_THRESHOLD)
    
    def _save_audit_log(self, results: Dict):
        """Save audit results to file."""
        log_dir = "./audit_logs"
        os.makedirs(log_dir, exist_ok=True)
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_path = os.path.join(log_dir, f"audit_{date_str}.json")
        
        try:
            with open(log_path, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Audit log saved: {log_path}")
        except Exception as e:
            logger.error(f"Failed to save audit log: {e}")


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
        log_dir = "./audit_logs"
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
# PROPS FETCH JOB
# ============================================

class PropsFetchJob:
    """
    Fetches props for all sports twice daily (10 AM and 6 PM).
    This minimizes API credit usage while keeping data fresh.
    """

    def __init__(self):
        self.last_run = None
        self.last_results = {}

    async def run_async(self):
        """Execute props fetch for all sports (async version)."""
        import httpx

        logger.info("=" * 50)
        logger.info("🎯 PROPS FETCH STARTING")
        logger.info(f"   Time: {datetime.now().isoformat()}")
        logger.info("=" * 50)

        self.last_run = datetime.now()
        results = {
            "timestamp": self.last_run.isoformat(),
            "sports": {},
            "total_api_calls": 0
        }

        # Import here to avoid circular imports
        try:
            from live_data_router import get_props, api_cache
        except ImportError:
            logger.error("Could not import live_data_router")
            return {"error": "Import failed"}

        for sport in SchedulerConfig.PROPS_SPORTS:
            try:
                # Clear the cache for this sport to force fresh fetch
                cache_key = f"props:{sport}"
                api_cache.delete(cache_key)

                # Fetch fresh props
                props_data = await get_props(sport)

                # Cache with 8-hour TTL
                api_cache.set(cache_key, props_data, ttl=SchedulerConfig.PROPS_CACHE_TTL)

                results["sports"][sport] = {
                    "status": "success",
                    "count": props_data.get("count", 0),
                    "source": props_data.get("source", "unknown"),
                    "games_with_props": len(props_data.get("data", []))
                }
                logger.info(f"[{sport.upper()}] Fetched {props_data.get('count', 0)} props from {props_data.get('source', 'unknown')}")

            except Exception as e:
                logger.error(f"[{sport.upper()}] Props fetch failed: {e}")
                results["sports"][sport] = {"status": "error", "error": str(e)}

        self.last_results = results

        logger.info("=" * 50)
        logger.info("✅ PROPS FETCH COMPLETE")
        logger.info(f"   Sports fetched: {len(results['sports'])}")
        logger.info("=" * 50)

        return results

    def run(self):
        """Sync wrapper for scheduled execution."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, create a new task
                asyncio.create_task(self.run_async())
                return {"status": "scheduled"}
            else:
                return loop.run_until_complete(self.run_async())
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.run_async())


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
        self.props_job = PropsFetchJob()
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

        # Props fetch at 10 AM daily (morning fresh data for community)
        self.scheduler.add_job(
            self.props_job.run,
            CronTrigger(hour=10, minute=SchedulerConfig.PROPS_FETCH_MINUTE),
            id="props_fetch_morning",
            name="Props Fetch (10 AM daily)"
        )

        # Props fetch at 6 PM daily (evening refresh for goldilocks zone)
        self.scheduler.add_job(
            self.props_job.run,
            CronTrigger(hour=18, minute=SchedulerConfig.PROPS_FETCH_MINUTE),
            id="props_fetch_evening",
            name="Props Fetch (6 PM daily)"
        )

        # Weekend-only: Props fetch at 12 PM (noon games)
        self.scheduler.add_job(
            self.props_job.run,
            CronTrigger(day_of_week="sat,sun", hour=12, minute=SchedulerConfig.PROPS_FETCH_MINUTE),
            id="props_fetch_weekend_noon",
            name="Props Fetch (12 PM weekends)"
        )

        # Weekend-only: Props fetch at 2 PM (afternoon games)
        self.scheduler.add_job(
            self.props_job.run,
            CronTrigger(day_of_week="sat,sun", hour=14, minute=SchedulerConfig.PROPS_FETCH_MINUTE),
            id="props_fetch_weekend_afternoon",
            name="Props Fetch (2 PM weekends)"
        )

        # Weekly cleanup on Sunday at 3 AM
        self.scheduler.add_job(
            self.cleanup_job.run,
            CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="weekly_cleanup",
            name="Weekly Cleanup"
        )

        self.scheduler.start()
        logger.info("APScheduler started: audit@6AM, props@10AM+6PM daily (+12PM+2PM weekends), cleanup@Sun3AM")
    
    def _start_simple_scheduler(self):
        """Fallback simple scheduler using threading."""
        def run_scheduler():
            last_audit_date = None
            last_props_10am = None
            last_props_12pm = None
            last_props_2pm = None
            last_props_6pm = None

            while self.running:
                now = datetime.now()
                today = now.date()
                is_weekend = now.weekday() >= 5  # Saturday=5, Sunday=6

                # Check if we should run audit (6 AM, once per day)
                if (now.hour == SchedulerConfig.AUDIT_HOUR and
                    now.minute < 5 and
                    last_audit_date != today):

                    self.audit_job.run()
                    last_audit_date = today

                # Check if we should run props fetch (10 AM daily)
                if (now.hour == 10 and
                    now.minute < 5 and
                    last_props_10am != today):

                    self.props_job.run()
                    last_props_10am = today

                # Check if we should run props fetch (12 PM weekends only)
                if (is_weekend and
                    now.hour == 12 and
                    now.minute < 5 and
                    last_props_12pm != today):

                    self.props_job.run()
                    last_props_12pm = today

                # Check if we should run props fetch (2 PM weekends only)
                if (is_weekend and
                    now.hour == 14 and
                    now.minute < 5 and
                    last_props_2pm != today):

                    self.props_job.run()
                    last_props_2pm = today

                # Check if we should run props fetch (6 PM daily)
                if (now.hour == 18 and
                    now.minute < 5 and
                    last_props_6pm != today):

                    self.props_job.run()
                    last_props_6pm = today

                # Sleep for 1 minute
                time.sleep(60)

        self._thread = threading.Thread(target=run_scheduler, daemon=True)
        self._thread.start()
        logger.info("Simple scheduler started: audit@6AM, props@10AM+6PM daily, +12PM+2PM weekends")
    
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
    
    def run_props_fetch_now(self) -> Dict:
        """Manually trigger props fetch."""
        logger.info("Manual props fetch triggered")
        return self.props_job.run()

    def get_status(self) -> Dict:
        """Get scheduler status."""
        status = {
            "running": self.running,
            "scheduler_type": "apscheduler" if SCHEDULER_AVAILABLE else "simple",
            "last_audit": self.audit_job.last_run.isoformat() if self.audit_job.last_run else None,
            "last_props_fetch": self.props_job.last_run.isoformat() if self.props_job.last_run else None,
            "next_audit": f"{SchedulerConfig.AUDIT_HOUR:02d}:{SchedulerConfig.AUDIT_MINUTE:02d} daily",
            "next_props_fetch": "10AM+6PM daily, +12PM+2PM on weekends",
            "props_cache_ttl": f"{SchedulerConfig.PROPS_CACHE_TTL // 3600} hours",
            "last_results": self.audit_job.last_results,
            "last_props_results": self.props_job.last_results
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


@scheduler_router.post("/run-props-fetch")
async def run_props_fetch_now():
    """
    Manually trigger props fetch for all sports.
    Use this to refresh props data outside of scheduled times (10 AM, 6 PM).
    """
    if not _scheduler:
        raise HTTPException(500, "Scheduler not initialized")

    result = await _scheduler.props_job.run_async()
    return {
        "status": "success",
        "result": result
    }


# ============================================
# STANDALONE TEST
# ============================================

if __name__ == "__main__":
    print("Testing Daily Scheduler...")
    
    scheduler = DailyScheduler()
    
    # Test manual audit
    print("\nRunning manual audit...")
    result = scheduler.run_audit_now()
    print(json.dumps(result, indent=2, default=str))
    
    # Test status
    print("\nScheduler status:")
    print(json.dumps(scheduler.get_status(), indent=2, default=str))
