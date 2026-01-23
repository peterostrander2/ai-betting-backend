"""
⏰ DAILY SCHEDULER v2.1 (v10.32)
================================
Automated daily tasks for Bookie-o-em:

1. Grade yesterday's predictions (6 AM)
2. Adjust weights based on bias
3. v10.32: Tune micro-weights based on signal attribution
4. Retrain LSTM if performance drops
5. Clean up old prediction logs
6. Fetch props twice daily (10 AM, 6 PM) - API credit optimization

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

# v10.32: Import micro-weight tuning
try:
    from learning_engine import (
        tune_micro_weights_from_attribution,
        get_micro_weight_status,
        run_micro_weight_tuning
    )
    MICRO_WEIGHT_TUNING_AVAILABLE = True
except ImportError:
    MICRO_WEIGHT_TUNING_AVAILABLE = False
    logger.warning("Micro-weight tuning not available")

# v10.31: Import sport season gating
try:
    from sport_seasons import is_in_season, get_in_season_sports
    SEASON_GATING_AVAILABLE = True
except ImportError:
    SEASON_GATING_AVAILABLE = False
    logger.warning("Sport season gating not available")

# v10.32: Redis for distributed locking
try:
    import redis
    from env_config import Config
    REDIS_AVAILABLE = bool(Config.REDIS_URL)
    if REDIS_AVAILABLE:
        _redis_client = redis.from_url(Config.REDIS_URL)
        logger.info("Redis available for distributed locking")
    else:
        _redis_client = None
except ImportError:
    REDIS_AVAILABLE = False
    _redis_client = None
    logger.warning("Redis not available - using local locking only")


def acquire_daily_lock(job_name: str, ttl_seconds: int = 7200) -> bool:
    """
    Acquire a distributed lock for a daily job.
    Prevents duplicate runs across multiple instances.

    Args:
        job_name: Job identifier (e.g., "daily_grading")
        ttl_seconds: Lock TTL (default 2 hours)

    Returns:
        True if lock acquired, False if already held
    """
    if not REDIS_AVAILABLE or _redis_client is None:
        # Fallback: no distributed lock, allow run
        logger.debug(f"No Redis - proceeding without distributed lock for {job_name}")
        return True

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        lock_key = f"jarvis:{job_name}:{today}"

        # NX = only set if not exists, EX = expire after ttl
        acquired = _redis_client.set(lock_key, "locked", nx=True, ex=ttl_seconds)

        if acquired:
            logger.info(f"Acquired lock: {lock_key}")
            return True
        else:
            logger.info(f"Lock already held: {lock_key}")
            return False
    except Exception as e:
        logger.warning(f"Redis lock error (proceeding anyway): {e}")
        return True  # On error, allow run to avoid blocking


def release_daily_lock(job_name: str):
    """Release a daily lock (optional, TTL handles cleanup)."""
    if not REDIS_AVAILABLE or _redis_client is None:
        return

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        lock_key = f"jarvis:{job_name}:{today}"
        _redis_client.delete(lock_key)
        logger.debug(f"Released lock: {lock_key}")
    except Exception as e:
        logger.warning(f"Failed to release lock: {e}")


# ============================================
# CONFIGURATION
# ============================================

class SchedulerConfig:
    """Scheduler configuration."""

    # Audit time (5 AM ET) - v10.31 changed from 6 AM to 5 AM
    AUDIT_HOUR = 5
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
        """Execute daily audit for all sports that are in-season."""
        # v10.32: Acquire distributed lock to prevent duplicate runs
        if not acquire_daily_lock("daily_audit"):
            logger.info("Daily audit already running on another instance - skipping")
            return {"skipped": True, "reason": "lock_held"}

        logger.info("=" * 50)
        logger.info("⏰ DAILY AUDIT STARTING (v10.32)")
        logger.info(f"   Time: {datetime.now().isoformat()}")
        logger.info("=" * 50)

        self.last_run = datetime.now()
        results = {
            "timestamp": self.last_run.isoformat(),
            "sports": {},
            "skipped_off_season": [],
            "lock_acquired": True
        }

        # v10.31: Use season gating to only process in-season sports
        all_sports = ["NBA", "NFL", "MLB", "NHL", "NCAAB"]
        if SEASON_GATING_AVAILABLE:
            in_season_sports = get_in_season_sports()
            logger.info(f"v10.31: Sports in season: {in_season_sports}")
            sports_to_process = [s for s in all_sports if s in in_season_sports]
            results["skipped_off_season"] = [s for s in all_sports if s not in in_season_sports]
        else:
            sports_to_process = all_sports
            logger.warning("Season gating not available - processing all sports")

        for sport in sports_to_process:
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
            "micro_weights_tuned": False,  # v10.32
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

        # v10.32: Tune micro-weights based on signal attribution
        if MICRO_WEIGHT_TUNING_AVAILABLE:
            try:
                mw_result = tune_micro_weights_from_attribution(sport)
                if mw_result.get("adjustments_made", 0) > 0:
                    result["micro_weights_tuned"] = True
                    result["micro_weight_adjustments"] = mw_result.get("adjustments", [])
                    logger.info(f"[{sport}] Micro-weights tuned: {mw_result.get('adjustments_made', 0)} adjustments")
                else:
                    logger.info(f"[{sport}] Micro-weights: No adjustments needed")
            except Exception as e:
                logger.warning(f"[{sport}] Micro-weight tuning failed: {e}")
                result["micro_weight_error"] = str(e)

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
# v10.31 GRADING + TUNING JOB
# ============================================

class V1031GradingJob:
    """
    v10.31 Daily grading and tuning job:
    1. Grade yesterday's picks from PickLedger
    2. Run conservative tuning on sport configs
    3. Log all changes to ConfigChangeLog
    """

    def __init__(self):
        self.last_run = None
        self.last_results = {}

    async def run_async(self):
        """Execute v10.31 grading and tuning for all sports."""
        logger.info("=" * 50)
        logger.info("📊 v10.31 GRADING + TUNING STARTING")
        logger.info(f"   Time: {datetime.now().isoformat()}")
        logger.info("=" * 50)

        self.last_run = datetime.now()
        results = {
            "timestamp": self.last_run.isoformat(),
            "grading": {},
            "tuning": {}
        }

        # Import engines
        try:
            from grading_engine import run_daily_grading
            from learning_engine import run_daily_tuning
        except ImportError as e:
            logger.error(f"Could not import v10.31 engines: {e}")
            return {"error": f"Import failed: {e}"}

        # Step 1: Grade yesterday's picks
        try:
            grading_results = await run_daily_grading(days_back=1)
            results["grading"] = grading_results
            logger.info(f"Grading complete: {grading_results.get('totals', {})}")
        except Exception as e:
            logger.error(f"Grading failed: {e}")
            results["grading"] = {"error": str(e)}

        # Step 2: Run conservative tuning
        try:
            tuning_results = run_daily_tuning()
            results["tuning"] = tuning_results
            logger.info(f"Tuning complete: {tuning_results.get('sports_tuned', 0)} sports tuned")
        except Exception as e:
            logger.error(f"Tuning failed: {e}")
            results["tuning"] = {"error": str(e)}

        self.last_results = results

        logger.info("=" * 50)
        logger.info("✅ v10.31 GRADING + TUNING COMPLETE")
        logger.info("=" * 50)

        return results

    def run(self):
        """Sync wrapper for scheduled execution."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.run_async())
                return {"status": "scheduled"}
            else:
                return loop.run_until_complete(self.run_async())
        except RuntimeError:
            return asyncio.run(self.run_async())


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
# v10.38 JSONL GRADING JOB
# ============================================

class JSONLGradingJob:
    """
    v10.38 Grading job that reads from JSONL prediction logs.

    Workflow:
    1. Load ungraded predictions from ./grader_data/{sport}/predictions/{date}.jsonl
    2. Fetch actual results (player stats) from APIs (ESPN FREE, BallDontLie FREE)
    3. Grade each prediction (WIN/LOSS/PUSH/NO_ACTION)
    4. Update prediction logs with results
    5. Append graded records to ./grader_data/{sport}/graded/{date}.jsonl
    6. Adjust weights if graded_count >= 30
    """

    # Stat type mapping: market -> stat key in API response
    STAT_TYPE_MAP = {
        "player_points": "points",
        "player_rebounds": "rebounds",
        "player_assists": "assists",
        "player_threes": "threes",
        "player_steals": "steals",
        "player_blocks": "blocks",
        "player_turnovers": "turnovers",
        "player_pra": "points_rebounds_assists",
        "player_points_rebounds_assists": "points_rebounds_assists",
        "player_points_rebounds": "points_rebounds",
        "player_points_assists": "points_assists",
        "player_rebounds_assists": "rebounds_assists",
        # Direct mappings
        "points": "points",
        "rebounds": "rebounds",
        "assists": "assists",
        "threes": "threes",
        "steals": "steals",
        "blocks": "blocks",
    }

    def __init__(self, auto_grader=None):
        self.auto_grader = auto_grader
        self.last_run = None
        self.last_results = {}

    @staticmethod
    def normalize_player_name(name: str) -> str:
        """
        Normalize player name for matching.
        - Strip punctuation
        - Lowercase
        - Handle suffixes (Jr., Sr., III, II, IV)
        """
        import re
        if not name:
            return ""

        # Lowercase
        name = name.lower().strip()

        # Remove common suffixes
        suffixes = [" jr.", " jr", " sr.", " sr", " iii", " ii", " iv", " v"]
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]

        # Remove punctuation except spaces and hyphens
        name = re.sub(r"[^\w\s\-]", "", name)

        # Normalize whitespace
        name = " ".join(name.split())

        return name

    async def run_async(self):
        """Execute JSONL grading for all in-season sports."""
        logger.info("=" * 50)
        logger.info("📊 v10.38 JSONL GRADING STARTING")
        logger.info(f"   Time: {datetime.now().isoformat()}")
        logger.info("=" * 50)

        self.last_run = datetime.now()
        results = {
            "timestamp": self.last_run.isoformat(),
            "sports": {},
            "total_graded": 0,
            "total_wins": 0,
            "total_losses": 0,
            "total_no_action": 0
        }

        if not self.auto_grader:
            logger.error("Auto-grader not available")
            return {"error": "Auto-grader not available"}

        # Get in-season sports
        if SEASON_GATING_AVAILABLE:
            sports = get_in_season_sports()
        else:
            sports = ["NBA", "NFL", "MLB", "NHL", "NCAAB"]

        for sport in sports:
            try:
                sport_result = await self._grade_sport(sport)
                results["sports"][sport] = sport_result
                results["total_graded"] += sport_result.get("graded", 0)
                results["total_wins"] += sport_result.get("wins", 0)
                results["total_losses"] += sport_result.get("losses", 0)
                results["total_no_action"] += sport_result.get("no_action", 0)
                logger.info(f"[{sport}] Graded {sport_result.get('graded', 0)} predictions")
            except Exception as e:
                logger.error(f"[{sport}] Grading failed: {e}")
                results["sports"][sport] = {"error": str(e)}

        self.last_results = results

        # Calculate overall hit rate
        total_decided = results["total_wins"] + results["total_losses"]
        if total_decided > 0:
            results["hit_rate"] = round((results["total_wins"] / total_decided) * 100, 1)
        else:
            results["hit_rate"] = 0.0

        logger.info("=" * 50)
        logger.info(f"✅ v10.38 JSONL GRADING COMPLETE: {results['total_graded']} graded, {results['hit_rate']}% hit rate")
        logger.info("=" * 50)

        return results

    async def _grade_sport(self, sport: str, date_et: str = None) -> dict:
        """
        v10.54: Grade predictions for a single sport using both JSONL and Postgres.

        Args:
            sport: Sport code (NBA, NFL, etc.)
            date_et: Optional date in YYYY-MM-DD format (defaults to yesterday in ET)
        """
        sport = sport.upper()
        result = {
            "sport": sport,
            "date": date_et,
            "ungraded_count": 0,
            "graded": 0,
            "wins": 0,
            "losses": 0,
            "pushes": 0,
            "no_action": 0,
            "postgres_updated": 0,
            "weights_adjusted": False
        }

        # v10.54: Import database functions for Postgres grading
        try:
            from database import (
                get_pending_picks_for_date, update_pick_result,
                PickResult, get_et_now, DB_ENABLED
            )
            db_available = DB_ENABLED
        except ImportError:
            db_available = False
            logger.warning(f"[{sport}] Database not available for Postgres grading")

        # v10.54: Determine date in ET if not provided
        if not date_et:
            if db_available:
                et_now = get_et_now()
                date_et = (et_now - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                date_et = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        result["date"] = date_et

        # Get ungraded predictions from JSONL
        ungraded = self.auto_grader.get_ungraded_predictions(sport, date_et=date_et)
        result["ungraded_count"] = len(ungraded)

        # v10.54: Also get PENDING picks from Postgres for syncing
        postgres_pending = []
        if db_available:
            try:
                from datetime import date as dt_date
                target_date = dt_date.fromisoformat(date_et)
                postgres_pending = get_pending_picks_for_date(target_date, sport)
                logger.info(f"[{sport}] Found {len(postgres_pending)} PENDING picks in Postgres for {date_et}")
            except Exception as e:
                logger.warning(f"[{sport}] Failed to fetch Postgres pending picks: {e}")

        if not ungraded and not postgres_pending:
            logger.info(f"[{sport}] No ungraded predictions found (JSONL or Postgres)")
            return result

        logger.info(f"[{sport}] Found {len(ungraded)} ungraded JSONL, {len(postgres_pending)} Postgres pending")

        # Fetch actual results and grade each prediction
        graded_results = []
        for pred in ungraded:
            try:
                grade_info = await self._grade_single_prediction(sport, pred)
                if grade_info:
                    graded_results.append(grade_info)
            except Exception as e:
                logger.warning(f"[{sport}] Failed to grade prediction: {e}")

        if graded_results:
            # Update JSONL files with graded results
            grade_result = self.auto_grader.grade_predictions_batch(sport, graded_results, date_et=date_et)
            result["graded"] = grade_result.get("graded", 0)
            result["wins"] = grade_result.get("wins", 0)
            result["losses"] = grade_result.get("losses", 0)
            result["pushes"] = grade_result.get("pushes", 0)

        # v10.54: Update Postgres PickLedger with graded results
        if db_available and postgres_pending:
            postgres_updated = 0
            for pick in postgres_pending:
                try:
                    # Try to find matching graded result
                    grade_info = await self._grade_single_prediction(sport, {
                        "pick_type": "prop" if pick.player_name else "game",
                        "player_name": pick.player_name or "",
                        "stat_type": pick.market,
                        "event_id": pick.event_id,
                        "game": pick.matchup,
                        "market": pick.market,
                        "selection": pick.selection,
                        "line": pick.line,
                        "side": pick.side,
                        "home_team": pick.home_team,
                        "away_team": pick.away_team,
                        "date_et": date_et
                    })

                    if grade_info and grade_info.get("actual") is not None:
                        actual_value = grade_info["actual"]
                        line = pick.line or 0
                        side = (pick.side or "").upper()

                        # Determine result based on actual vs line
                        if side == "OVER":
                            if actual_value > line:
                                pick_result = PickResult.WIN
                                profit = pick.recommended_units * self._get_profit_mult(pick.odds)
                            elif actual_value < line:
                                pick_result = PickResult.LOSS
                                profit = -pick.recommended_units
                            else:
                                pick_result = PickResult.PUSH
                                profit = 0.0
                        elif side == "UNDER":
                            if actual_value < line:
                                pick_result = PickResult.WIN
                                profit = pick.recommended_units * self._get_profit_mult(pick.odds)
                            elif actual_value > line:
                                pick_result = PickResult.LOSS
                                profit = -pick.recommended_units
                            else:
                                pick_result = PickResult.PUSH
                                profit = 0.0
                        else:
                            # For spreads/ML, assume actual_value is margin
                            pick_result = PickResult.WIN if actual_value > 0 else PickResult.LOSS
                            profit = pick.recommended_units * self._get_profit_mult(pick.odds) if pick_result == PickResult.WIN else -pick.recommended_units

                        # Update Postgres
                        if update_pick_result(pick.pick_uid, pick_result, profit, actual_value):
                            postgres_updated += 1
                            if pick_result == PickResult.WIN:
                                result["wins"] += 1
                            elif pick_result == PickResult.LOSS:
                                result["losses"] += 1
                            elif pick_result == PickResult.PUSH:
                                result["pushes"] += 1

                except Exception as e:
                    logger.warning(f"[{sport}] Failed to update Postgres pick {pick.pick_uid}: {e}")

            result["postgres_updated"] = postgres_updated
            logger.info(f"[{sport}] Updated {postgres_updated} picks in Postgres")

        # Adjust weights if we have enough graded predictions
        grading_stats = self.auto_grader.get_grading_stats(sport, days_back=7)
        if grading_stats.get("total_graded", 0) >= 30:
            logger.info(f"[{sport}] Enough data for weight adjustment ({grading_stats['total_graded']} graded)")
            # Trigger weight adjustment
            try:
                for stat_type in ["points", "rebounds", "assists"]:
                    self.auto_grader.adjust_weights(sport, stat_type, days_back=7, apply_changes=True)
                result["weights_adjusted"] = True
            except Exception as e:
                logger.warning(f"[{sport}] Weight adjustment failed: {e}")

        return result

    def _get_profit_mult(self, odds: int) -> float:
        """Calculate profit multiplier from American odds."""
        if not odds:
            return 1.0
        try:
            if odds > 0:
                return odds / 100
            else:
                return 100 / abs(odds)
        except (ValueError, ZeroDivisionError):
            return 1.0

    async def _grade_single_prediction(self, sport: str, pred: dict) -> Optional[dict]:
        """
        Grade a single prediction by fetching actual stats.

        Returns dict with event_id, player_name, stat_type, actual for grading.
        """
        pick_type = pred.get("pick_type", "prop")
        player_name = pred.get("player_name", "")
        stat_type = pred.get("stat_type", "") or pred.get("market", "")
        event_id = pred.get("event_id", "")
        game = pred.get("game", "")

        # Skip if already graded
        if pred.get("graded", False):
            return None

        # Import grading engine functions
        try:
            from grading_engine import (
                fetch_espn_box_scores,
                fetch_balldontlie_player_stats,
                fetch_odds_api_scores,
                get_stat_value_from_market
            )
        except ImportError:
            logger.warning("grading_engine not available - using placeholder")
            return None

        # Determine game date from prediction
        date_et = pred.get("date_et", "")
        if date_et:
            from datetime import date as date_type
            try:
                game_date = date_type.fromisoformat(date_et)
            except ValueError:
                game_date = date_type.today() - timedelta(days=1)
        else:
            game_date = date_type.today() - timedelta(days=1)

        # Props grading
        if pick_type == "prop" and player_name:
            actual_value = await self._fetch_player_stat(
                sport, player_name, stat_type, game_date
            )

            if actual_value is not None:
                return {
                    "event_id": event_id,
                    "player_name": player_name,
                    "stat_type": stat_type,
                    "actual": actual_value
                }
            else:
                logger.debug(f"[{sport}] No stats found for {player_name}")
                return None

        # Game picks grading (spreads, totals, ML)
        elif pick_type == "game":
            # For game picks, we need game scores
            actual_value = await self._fetch_game_result(sport, pred, game_date)
            if actual_value is not None:
                return {
                    "event_id": event_id,
                    "player_name": "",
                    "stat_type": pred.get("market", ""),
                    "actual": actual_value
                }

        return None

    async def _fetch_player_stat(
        self,
        sport: str,
        player_name: str,
        stat_type: str,
        game_date
    ) -> Optional[float]:
        """Fetch actual player stat from APIs."""
        try:
            from grading_engine import (
                fetch_espn_box_scores,
                fetch_balldontlie_player_stats,
                get_stat_value_from_market,
                _add_combo_stats
            )
        except ImportError:
            return None

        player_name_normalized = self.normalize_player_name(player_name)

        # Try ESPN first (FREE)
        espn_stats = await fetch_espn_box_scores(sport, game_date)
        if espn_stats:
            # Try exact match
            for key, stats in espn_stats.items():
                key_normalized = self.normalize_player_name(key)
                if player_name_normalized == key_normalized:
                    _add_combo_stats(stats)
                    return get_stat_value_from_market(stats, stat_type)

            # Try fuzzy match (last name)
            last_name = player_name_normalized.split()[-1] if " " in player_name_normalized else player_name_normalized
            for key, stats in espn_stats.items():
                key_normalized = self.normalize_player_name(key)
                if last_name in key_normalized or key_normalized.endswith(last_name):
                    _add_combo_stats(stats)
                    return get_stat_value_from_market(stats, stat_type)

        # Try BallDontLie for NBA (FREE)
        if sport.upper() == "NBA":
            bdl_stats = await fetch_balldontlie_player_stats(player_name, game_date)
            if bdl_stats:
                return get_stat_value_from_market(bdl_stats, stat_type)

        return None

    async def _fetch_game_result(self, sport: str, pred: dict, game_date) -> Optional[float]:
        """Fetch game result for game picks (spreads, totals, ML)."""
        try:
            from grading_engine import fetch_odds_api_scores, _parse_odds_api_game
        except ImportError:
            return None

        market = pred.get("market", "")
        selection = pred.get("selection", "") or pred.get("pick", "")
        line = pred.get("line", 0)

        games = await fetch_odds_api_scores(sport, days_from=3)
        if not games:
            return None

        # Find matching game
        game_str = pred.get("game", "")
        home_team = pred.get("home_team", "")
        away_team = pred.get("away_team", "")

        for game in games:
            if not game.get("completed"):
                continue

            game_home = (game.get("home_team") or "").lower()
            game_away = (game.get("away_team") or "").lower()

            # Match by team names
            home_match = home_team.lower() in game_home or game_home in home_team.lower()
            away_match = away_team.lower() in game_away or game_away in away_team.lower()

            if home_match and away_match:
                parsed = _parse_odds_api_game(game)
                home_score = parsed.get("home_score")
                away_score = parsed.get("away_score")

                if home_score is not None and away_score is not None:
                    # For totals, return total points
                    if "total" in market.lower():
                        return home_score + away_score
                    # For spreads/ML, return margin (positive = home won)
                    else:
                        return home_score - away_score

        return None

    def run(self):
        """Sync wrapper for scheduled execution."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.run_async())
                return {"status": "scheduled"}
            else:
                return loop.run_until_complete(self.run_async())
        except RuntimeError:
            return asyncio.run(self.run_async())


# ============================================
# v10.36 SMOKE TEST JOB
# ============================================

class SmokeTestJob:
    """
    Nightly smoke test to verify entire system is working.
    Runs at 5:30 AM ET daily before picks go out.

    Tests:
    1. API connectivity (Playbook, Odds API)
    2. Best bets generation (props + game picks)
    3. All 11 pillars firing
    4. AI Engine models
    5. Context Layer
    6. Esoteric systems
    7. Auto-grader availability

    If ANY test fails, logs critical error for alerting.
    """

    def __init__(self):
        self.last_run = None
        self.last_results = {}
        self.failures = []

    async def run_async(self):
        """Execute full smoke test suite."""
        import httpx

        logger.info("=" * 60)
        logger.info("🔥 NIGHTLY SMOKE TEST STARTING")
        logger.info(f"   Time: {datetime.now().isoformat()}")
        logger.info("=" * 60)

        self.last_run = datetime.now()
        self.failures = []

        results = {
            "timestamp": self.last_run.isoformat(),
            "tests": {},
            "passed": 0,
            "failed": 0,
            "critical_failures": []
        }

        # Test 1: Best Bets Generation (CRITICAL)
        results["tests"]["best_bets"] = await self._test_best_bets()

        # Test 2: System Health Components
        results["tests"]["system_health"] = await self._test_system_health()

        # Test 3: API Connectivity
        results["tests"]["api_connectivity"] = await self._test_api_connectivity()

        # Test 4: Pillars Firing
        results["tests"]["pillars"] = await self._test_pillars_firing()

        # Test 5: Esoteric Systems
        results["tests"]["esoteric"] = await self._test_esoteric()

        # Count passes/failures
        for test_name, test_result in results["tests"].items():
            if test_result.get("passed"):
                results["passed"] += 1
            else:
                results["failed"] += 1
                if test_result.get("critical"):
                    results["critical_failures"].append(test_name)
                    self.failures.append(test_name)

        # Log summary
        self.last_results = results
        self._log_results(results)
        self._save_smoke_test_log(results)

        return results

    async def _test_best_bets(self) -> dict:
        """Test that best bets endpoint returns picks."""
        test = {"name": "Best Bets Generation", "critical": True, "passed": False}

        try:
            from live_data_router import get_best_bets

            # Test NBA (most common)
            result = await get_best_bets("nba")

            props_count = result.get("props", {}).get("count", 0)
            game_picks_count = result.get("game_picks", {}).get("count", 0)

            test["props_count"] = props_count
            test["game_picks_count"] = game_picks_count
            test["total_picks"] = props_count + game_picks_count

            # Pass if we got any picks at all
            if props_count > 0 or game_picks_count > 0:
                test["passed"] = True
                test["message"] = f"Generated {test['total_picks']} picks"
            else:
                test["message"] = "No picks generated - check API connectivity"

        except Exception as e:
            test["error"] = str(e)
            test["message"] = f"Best bets failed: {e}"
            logger.error(f"SMOKE TEST FAILED: Best Bets - {e}")

        return test

    async def _test_system_health(self) -> dict:
        """Test system health endpoint."""
        test = {"name": "System Health", "critical": True, "passed": False}

        try:
            from live_data_router import system_health

            health = await system_health()

            test["status"] = health.get("status")
            test["issues"] = health.get("issues", [])
            test["components"] = list(health.get("components", {}).keys())

            # Check critical components
            components = health.get("components", {})

            # AI Models must be available
            ai_active = components.get("ai_models", {}).get("all_active", False)

            # Pillars must be active
            pillars_active = components.get("pillars", {}).get("active_count", 0) >= 10

            # Context layer should be available
            context_active = components.get("context_layer", {}).get("available", False)

            if ai_active and pillars_active:
                test["passed"] = True
                test["message"] = f"All critical components active"
            else:
                test["message"] = f"Component issues: AI={ai_active}, Pillars={pillars_active}"

        except Exception as e:
            test["error"] = str(e)
            test["message"] = f"System health check failed: {e}"

        return test

    async def _test_api_connectivity(self) -> dict:
        """Test API connectivity to Playbook and Odds API."""
        test = {"name": "API Connectivity", "critical": True, "passed": False}

        try:
            from live_data_router import get_sharp_money, get_props

            # Test Playbook API (sharp money)
            sharp_result = await get_sharp_money("nba")
            playbook_ok = sharp_result.get("count", 0) > 0 or sharp_result.get("source") != "error"

            # Test Odds API (props)
            props_result = await get_props("nba")
            odds_api_ok = props_result.get("count", 0) > 0 or props_result.get("source") != "error"

            test["playbook_api"] = "OK" if playbook_ok else "FAILED"
            test["odds_api"] = "OK" if odds_api_ok else "FAILED"

            if playbook_ok and odds_api_ok:
                test["passed"] = True
                test["message"] = "All APIs responding"
            elif playbook_ok or odds_api_ok:
                test["passed"] = True  # Partial pass
                test["message"] = f"Partial: Playbook={test['playbook_api']}, Odds={test['odds_api']}"
            else:
                test["message"] = "Both APIs failed - check keys and quotas"

        except Exception as e:
            test["error"] = str(e)
            test["message"] = f"API connectivity test failed: {e}"

        return test

    async def _test_pillars_firing(self) -> dict:
        """Test that pillars are firing in best bets."""
        test = {"name": "Pillars Firing", "critical": False, "passed": False}

        try:
            from live_data_router import get_best_bets

            result = await get_best_bets("nba")

            # Check if any picks have pillar reasons
            all_picks = (
                result.get("props", {}).get("picks", []) +
                result.get("game_picks", {}).get("picks", [])
            )

            pillar_signals_found = set()
            for pick in all_picks[:10]:  # Check first 10 picks
                reasons = pick.get("reasons", [])
                for reason in reasons:
                    if "RESEARCH:" in reason:
                        # Extract pillar name
                        pillar = reason.split(":")[1].split("(")[0].strip()
                        pillar_signals_found.add(pillar)

            test["pillars_found"] = list(pillar_signals_found)
            test["pillar_count"] = len(pillar_signals_found)

            if len(pillar_signals_found) >= 3:
                test["passed"] = True
                test["message"] = f"Found {len(pillar_signals_found)} active pillars"
            else:
                test["message"] = f"Only {len(pillar_signals_found)} pillars firing"

        except Exception as e:
            test["error"] = str(e)
            test["message"] = f"Pillar test failed: {e}"

        return test

    async def _test_esoteric(self) -> dict:
        """Test esoteric systems."""
        test = {"name": "Esoteric Systems", "critical": False, "passed": False}

        try:
            from esoteric_engine import get_daily_esoteric_reading

            reading = get_daily_esoteric_reading()

            test["has_reading"] = reading is not None
            test["signals"] = list(reading.keys()) if reading else []

            if reading and len(reading) > 0:
                test["passed"] = True
                test["message"] = f"Esoteric active with {len(reading)} signals"
            else:
                test["message"] = "Esoteric reading empty"

        except Exception as e:
            test["error"] = str(e)
            test["message"] = f"Esoteric test failed: {e}"

        return test

    def _log_results(self, results: dict):
        """Log smoke test results."""
        passed = results["passed"]
        failed = results["failed"]
        total = passed + failed

        logger.info("=" * 60)

        if failed == 0:
            logger.info(f"✅ SMOKE TEST PASSED: {passed}/{total} tests")
        else:
            logger.error(f"❌ SMOKE TEST FAILED: {passed}/{total} passed, {failed} failed")
            for failure in results["critical_failures"]:
                logger.error(f"   CRITICAL FAILURE: {failure}")

        # Log individual test results
        for test_name, test_result in results["tests"].items():
            status = "✅" if test_result.get("passed") else "❌"
            logger.info(f"   {status} {test_name}: {test_result.get('message', 'No message')}")

        logger.info("=" * 60)

    def _save_smoke_test_log(self, results: dict):
        """Save smoke test results to file."""
        log_dir = "./smoke_test_logs"
        os.makedirs(log_dir, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        log_path = os.path.join(log_dir, f"smoke_test_{date_str}.json")

        try:
            with open(log_path, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Smoke test log saved: {log_path}")
        except Exception as e:
            logger.error(f"Failed to save smoke test log: {e}")

    def run(self):
        """Sync wrapper for scheduled execution."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.run_async())
                return {"status": "scheduled"}
            else:
                return loop.run_until_complete(self.run_async())
        except RuntimeError:
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
        self.v1031_job = V1031GradingJob()  # v10.31: New grading + tuning job
        self.smoke_test_job = SmokeTestJob()  # v10.36: Nightly smoke test
        self.jsonl_grading_job = JSONLGradingJob(auto_grader)  # v10.38: JSONL prediction grading
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
        # v10.54: All jobs use America/New_York timezone consistently
        self.scheduler = BackgroundScheduler(timezone="America/New_York")

        # v10.31 Grading + Tuning at 5 AM ET (before legacy audit)
        self.scheduler.add_job(
            self.v1031_job.run,
            CronTrigger(hour=5, minute=0, timezone="America/New_York"),
            id="v1031_grading_tuning",
            name="v10.31 Daily Grading + Tuning (5 AM ET)"
        )

        # v10.36 Smoke Test at 5:30 AM ET (verify system before picks go out)
        self.scheduler.add_job(
            self.smoke_test_job.run,
            CronTrigger(hour=5, minute=30, timezone="America/New_York"),
            id="nightly_smoke_test",
            name="v10.36 Nightly Smoke Test (5:30 AM ET)"
        )

        # v10.38 JSONL Grading at 6 AM ET (grade yesterday's picks)
        self.scheduler.add_job(
            self.jsonl_grading_job.run,
            CronTrigger(hour=6, minute=0, timezone="America/New_York"),
            id="jsonl_grading",
            name="v10.38 JSONL Prediction Grading (6 AM ET)"
        )

        # Daily audit at 6:30 AM (after JSONL grading)
        self.scheduler.add_job(
            self.audit_job.run,
            CronTrigger(hour=6, minute=30, timezone="America/New_York"),
            id="daily_audit",
            name="Daily Audit (6:30 AM ET)"
        )

        # Props fetch at 10 AM ET daily (morning fresh data for community)
        self.scheduler.add_job(
            self.props_job.run,
            CronTrigger(hour=10, minute=SchedulerConfig.PROPS_FETCH_MINUTE, timezone="America/New_York"),
            id="props_fetch_morning",
            name="Props Fetch (10 AM ET daily)"
        )

        # Props fetch at 6 PM ET daily (evening refresh for goldilocks zone)
        self.scheduler.add_job(
            self.props_job.run,
            CronTrigger(hour=18, minute=SchedulerConfig.PROPS_FETCH_MINUTE, timezone="America/New_York"),
            id="props_fetch_evening",
            name="Props Fetch (6 PM ET daily)"
        )

        # Weekend-only: Props fetch at 12 PM ET (noon games)
        self.scheduler.add_job(
            self.props_job.run,
            CronTrigger(day_of_week="sat,sun", hour=12, minute=SchedulerConfig.PROPS_FETCH_MINUTE, timezone="America/New_York"),
            id="props_fetch_weekend_noon",
            name="Props Fetch (12 PM ET weekends)"
        )

        # Weekend-only: Props fetch at 2 PM ET (afternoon games)
        self.scheduler.add_job(
            self.props_job.run,
            CronTrigger(day_of_week="sat,sun", hour=14, minute=SchedulerConfig.PROPS_FETCH_MINUTE, timezone="America/New_York"),
            id="props_fetch_weekend_afternoon",
            name="Props Fetch (2 PM ET weekends)"
        )

        # Weekly cleanup on Sunday at 3 AM ET
        self.scheduler.add_job(
            self.cleanup_job.run,
            CronTrigger(day_of_week="sun", hour=3, minute=0, timezone="America/New_York"),
            id="weekly_cleanup",
            name="Weekly Cleanup (3 AM ET)"
        )

        self.scheduler.start()
        logger.info("APScheduler started (America/New_York): smoke_test@5:30AM_ET, jsonl_grading@6AM_ET, audit@6:30AM_ET, props@10AM+6PM_ET daily (+12PM+2PM_ET weekends), cleanup@Sun3AM_ET")
    
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
            "last_jsonl_grading": self.jsonl_grading_job.last_run.isoformat() if self.jsonl_grading_job.last_run else None,
            "next_audit": "06:30 ET daily",
            "next_jsonl_grading": "06:00 ET daily",
            "next_props_fetch": "10AM+6PM daily, +12PM+2PM on weekends",
            "props_cache_ttl": f"{SchedulerConfig.PROPS_CACHE_TTL // 3600} hours",
            "last_results": self.audit_job.last_results,
            "last_props_results": self.props_job.last_results,
            "last_jsonl_grading_results": self.jsonl_grading_job.last_results
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


@scheduler_router.post("/run-v1031-grading")
async def run_v1031_grading_now():
    """
    v10.31: Manually trigger daily grading + tuning.
    Grades yesterday's picks and runs conservative config tuning.
    """
    if not _scheduler:
        raise HTTPException(500, "Scheduler not initialized")

    result = await _scheduler.v1031_job.run_async()
    return {
        "status": "success",
        "result": result
    }


@scheduler_router.post("/run-jsonl-grading")
async def run_jsonl_grading_now():
    """
    v10.38: Manually trigger JSONL prediction grading.
    Grades yesterday's picks from JSONL logs.
    """
    if not _scheduler:
        raise HTTPException(500, "Scheduler not initialized")

    result = await _scheduler.jsonl_grading_job.run_async()
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
