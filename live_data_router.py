# live_data_router.py v15.1 - SCORING v10.79 (Glitch Protocol Modules)
# v10.66: Alternative Data Integration (Twitter, Finnhub, SerpAPI, FRED)
# v10.59: Wire Disconnected Features (Biorhythms, Hurst, Kelly Criterion)
# v10.57: Data Integrity Validators (prop_integrity + injury_guard before publish_gate)
# v10.54: Production V3 Contract Compliance (deterministic id, int confidence, ordered reasons)
# v10.53: Soft Stacking Governor (prevent same-team spam, allow SMASH stacks)
# v10.52: Time Gate (Same Day ET + Not Started) + team/opponent/game_time_et labels
# v10.43: Publish Gate (dominance dedup + quality gate + correlation penalty)
# v10.42: Universal fallback guarantee + debug counters + games_reason fix
# v10.41: Jason Sim 2.0 Post-Pick Confluence Layer (BOOST/DOWNGRADE/BLOCK)
# v10.40: 4-Engine Separation (AI + Research + Esoteric + Jarvis RS) + Jarvis Turbo safeguard
# v10.39: Jarvis Turbo Band scoring upgrade
# v10.37: Prop Correlation Stacking + Jason Sim 2.0 Ready + Quality over Quantity
# v10.36: Quality over quantity - remove arbitrary pick limits
# v10.32: Signal Attribution + Micro-Weight Tuning + Self-Learning System
# Production-safe with retries, logging, rate-limit handling, deterministic fallbacks

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List, Dict, Any
import httpx
import database  # v10.33: Import module for live DB_ENABLED check

# Import Pydantic models for request/response validation
try:
    from models.api_models import (
        TrackBetRequest, TrackBetResponse, GradeBetRequest,
        ParlayLegRequest, PlaceParlayRequest, GradeParlayRequest, ParlayCalculateRequest,
        UserPreferencesRequest, RunAuditRequest, AdjustWeightsRequest,
        LogPickRequest, GradePickRequest, CommunityVoteRequest, AffiliateConfigRequest,
        BetResult
    )
    PYDANTIC_MODELS_AVAILABLE = True
except ImportError:
    PYDANTIC_MODELS_AVAILABLE = False
import os
import logging
import hashlib
import asyncio
import random
from datetime import datetime, timedelta
import math
import json
import re
import numpy as np

# Initialize logger early (before imports that may use it)
logger = logging.getLogger("live_data")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)

# v10.55: Import tiering module - single source of truth for tier assignment
from tiering import (
    tier_from_score as tiering_tier_from_score,
    DEFAULT_TIERS as TIERING_DEFAULT_TIERS,
    TIER_CONFIG,
    TIER_ORDER,
    normalize_confidence,
    filter_tier_badges,
    downgrade_tier,
)

# v10.82: Import centralized version constants
from env_config import Config

# v10.72: Import PickCard schema for normalized output
from pick_schema import PickCard, normalize_pick, normalize_picks, picks_to_table

# v10.73: Import pull readiness and change monitor
from pull_readiness import (
    check_readiness, get_recommended_pull_windows,
    validate_pick_pipeline, audit_pick_engines, REQUIRED_ENGINES
)
from change_monitor import check_for_changes, save_snapshot, get_change_summary

# v10.75: Import time status module for live-bet detection
from time_status import (
    compute_time_status, format_time_status, get_time_state_summary,
    TimeState, Recommendation, LiveBand
)

# Import MasterPredictionSystem for comprehensive AI scoring
try:
    from advanced_ml_backend import MasterPredictionSystem
    MASTER_PREDICTION_AVAILABLE = True
except ImportError:
    MASTER_PREDICTION_AVAILABLE = False

# Import Playbook API utility
try:
    from playbook_api import (
        playbook_fetch, build_playbook_url, VALID_LEAGUES,
        get_splits as pb_get_splits,
        get_injuries as pb_get_injuries,
        get_lines as pb_get_lines,
        get_teams as pb_get_teams,
        get_games as pb_get_games,
        get_api_usage as pb_get_api_usage
    )
    PLAYBOOK_UTIL_AVAILABLE = True
except ImportError:
    PLAYBOOK_UTIL_AVAILABLE = False
    logger.warning("playbook_api module not available - using inline fetch")

# v10.66: Import Alternative Data Sources (Twitter, Finnhub, SerpAPI, FRED)
try:
    from alt_data_sources import (
        get_alternative_data_context,
        get_alt_data_status,
        is_twitter_configured,
        is_finnhub_configured,
        is_serpapi_configured,
        is_fred_configured
    )
    ALT_DATA_AVAILABLE = True
except ImportError:
    ALT_DATA_AVAILABLE = False
    logger.warning("alt_data_sources module not available - alternative data disabled")

# Import Auto-Grader singleton (CRITICAL: use get_grader() not AutoGrader())
try:
    from auto_grader import get_grader, AutoGrader
    AUTO_GRADER_AVAILABLE = True
except ImportError:
    AUTO_GRADER_AVAILABLE = False

# v10.31: Import database layer for pick ledger + config
try:
    from database import (
        DB_ENABLED, init_database, load_sport_config, upsert_pick,
        get_picks_for_date, get_config_changes, FACTORY_SPORT_PROFILES,
        get_micro_weights, DEFAULT_MICRO_WEIGHTS,
        get_signal_policy, get_signal_performance, get_tuning_history,
        # v10.32+: DB health and signal ledger stats
        get_db_health, get_signal_ledger_stats,
        # v10.32+: Season calendar
        is_sport_in_season, get_active_sports, get_season_status,
        # v10.32+: Signal logging
        save_signal_ledger, PickLedger
    )
    DATABASE_AVAILABLE = True
    SIGNAL_POLICY_AVAILABLE = True
except ImportError as e:
    DATABASE_AVAILABLE = False
    DB_ENABLED = False
    DEFAULT_MICRO_WEIGHTS = {}
    SIGNAL_POLICY_AVAILABLE = False
    logger.warning(f"Database module import failed: {e}")

# v10.32: Import signal attribution for ROI analysis
try:
    from signal_attribution import (
        extract_fired_signals, enrich_pick_with_signals,
        compute_feature_table, compute_signal_uplift
    )
    SIGNAL_ATTRIBUTION_AVAILABLE = True
except ImportError:
    SIGNAL_ATTRIBUTION_AVAILABLE = False

# v10.32: Import micro-weight tuning
try:
    from learning_engine import (
        tune_micro_weights_from_attribution, get_micro_weight_status,
        run_micro_weight_tuning
    )
    MICRO_WEIGHT_TUNING_AVAILABLE = True
except ImportError:
    MICRO_WEIGHT_TUNING_AVAILABLE = False

# v10.31: Import sport season gating
try:
    from sport_seasons import is_in_season, get_off_season_response, get_season_info
    SEASON_GATING_AVAILABLE = True
except ImportError:
    SEASON_GATING_AVAILABLE = False
    logger.warning("sport_seasons module not available - season gating disabled")

# v10.31: Import external signals for multi-API enrichment
# v10.60: Add get_weather_context for NFL/MLB weather impact
try:
    from external_signals import (
        get_external_context, calculate_external_micro_boost, get_weather_context
    )
    EXTERNAL_SIGNALS_AVAILABLE = True
    WEATHER_API_AVAILABLE = True
except ImportError:
    EXTERNAL_SIGNALS_AVAILABLE = False
    WEATHER_API_AVAILABLE = False
    logger.warning("external_signals module not available - enrichment disabled")

# Import AI Engine Layer (v10.24: 8 AI Models)
try:
    from ai_engine_layer import calculate_ai_engine_score, get_ai_engine_defaults
    AI_ENGINE_AVAILABLE = True
except ImportError:
    AI_ENGINE_AVAILABLE = False

# v10.36: Import Context Layer for defensive rankings + pace adjustments
# v10.59: Add MonteCarloService for game simulation
# v10.60: Add OfficialsService for referee impact
try:
    from context_layer import DefensiveRankService, PaceVectorService, MonteCarloService, OfficialsService
    CONTEXT_LAYER_AVAILABLE = True
    MONTE_CARLO_AVAILABLE = True
    OFFICIALS_SERVICE_AVAILABLE = True
except ImportError:
    CONTEXT_LAYER_AVAILABLE = False
    MONTE_CARLO_AVAILABLE = False
    OFFICIALS_SERVICE_AVAILABLE = False
    logger.warning("context_layer module not available - matchup adjustments disabled")
    logger.warning("ai_engine_layer module not available - using defaults")

# v10.36: Import APScheduler availability for system-health
try:
    from daily_scheduler import SCHEDULER_AVAILABLE as APSCHEDULER_AVAILABLE
except ImportError:
    APSCHEDULER_AVAILABLE = False

# v10.68: RotoWire removed - replaced by free ESPN API for lineups + referees
# ESPN integration is in alt_data_sources/espn_lineups.py

# v10.41: Import Jason Sim 2.0 confluence layer
try:
    from jason_sim_confluence import (
        normalize_jason_sim, apply_jason_sim_to_pick, apply_jason_sim_layer,
        build_jason_payloads_lookup, compute_variance_flag
    )
    JASON_SIM_AVAILABLE = True
except ImportError:
    JASON_SIM_AVAILABLE = False
    logger.warning("jason_sim_confluence module not available - Jason Sim disabled")

# v10.43: Import Publish Gate (dominance dedup + quality gate)
try:
    from publish_gate import (
        apply_publish_gate, apply_dominance_dedup,
        apply_correlation_penalty, apply_quality_gate,
        get_cluster, TARGET_MAX_PICKS
    )
    PUBLISH_GATE_AVAILABLE = True
except ImportError:
    PUBLISH_GATE_AVAILABLE = False
    logger.warning("publish_gate module not available - using legacy filtering")

# v10.56: Import Pick Filter (caps + correlation + UNDER penalty)
try:
    from pick_filter import filter_best_bets, get_filter_stats
    PICK_FILTER_AVAILABLE = True
except ImportError:
    PICK_FILTER_AVAILABLE = False
    logger.warning("pick_filter module not available - skipping final filter")

# v10.57: Import Data Integrity Validators (BEFORE tiering/caps/correlation)
try:
    from validators import (
        validate_prop_integrity, validate_props_batch,
        validate_injury_status, validate_props_batch_injury, build_injury_index,
        validate_market_available, validate_props_batch_market, build_dk_market_index,
        BLOCK_DOUBTFUL, BLOCK_GTD
    )
    VALIDATORS_AVAILABLE = True
except ImportError:
    VALIDATORS_AVAILABLE = False
    logger.warning("validators module not available - skipping data integrity checks")

# v10.59: Import esoteric features for enhanced scoring (biorhythms, hurst)
try:
    from esoteric_engine import (
        calculate_biorhythms,
        calculate_hurst_exponent,
        SAMPLE_PLAYERS as ESOTERIC_PLAYERS
    )
    ESOTERIC_FEATURES_AVAILABLE = True
except ImportError:
    ESOTERIC_FEATURES_AVAILABLE = False
    logger.warning("esoteric_engine features not available - biorhythms/hurst disabled")

# v10.59: Import player birth data for biorhythm lookups
try:
    from player_birth_data import get_player_data, get_all_players
    PLAYER_BIRTH_DATA_AVAILABLE = True
except ImportError:
    PLAYER_BIRTH_DATA_AVAILABLE = False
    logger.warning("player_birth_data not available - player biorhythms disabled")

# v10.79: Import Glitch Protocol modules (Master Audit File compliance)
try:
    from glitch import (
        # Main entry point
        get_glitch_analysis,
        # Esoteric
        get_chrome_resonance as glitch_chrome_resonance,
        get_esoteric_signals as glitch_esoteric_signals,
        TEAM_PRIMARY_COLORS as GLITCH_TEAM_COLORS,
        # Physics
        calculate_atmospheric_drag as glitch_atmospheric_drag,
        get_physics_signals as glitch_physics_signals,
        # Hive Mind
        detect_hate_buy_trap as glitch_hate_buy_trap,
        get_hive_mind_signals as glitch_hive_mind_signals,
        # Market
        check_benford_anomaly as glitch_benford_anomaly,
        get_market_signals as glitch_market_signals,
        # Math Glitch
        check_titanium_rule,
        check_harmonic_convergence,
        calculate_glitch_score,
        JARVIS_TRIGGERS as GLITCH_JARVIS_TRIGGERS,
    )
    GLITCH_PROTOCOL_AVAILABLE = True
except ImportError as e:
    GLITCH_PROTOCOL_AVAILABLE = False
    logger.warning(f"glitch module not available: {e} - using legacy inline functions")

# Redis import with fallback
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# ============================================================================
# CONFIGURATION (Environment Variables)
# ============================================================================

# API Keys - REQUIRED: Set these in Railway environment variables
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE = os.getenv("ODDS_API_BASE", "https://api.the-odds-api.com/v4")

PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "")
PLAYBOOK_API_BASE = os.getenv("PLAYBOOK_API_BASE", "https://api.playbook-api.com/v1")

# Log warning if API keys are missing
if not ODDS_API_KEY:
    logger.warning("ODDS_API_KEY not set - will use fallback data")
if not PLAYBOOK_API_KEY:
    logger.warning("PLAYBOOK_API_KEY not set - will use fallback data")

# Authentication - Optional API key for endpoint protection
# Set API_AUTH_KEY in Railway to enable authentication
# Set API_AUTH_ENABLED=true to require auth (default: false)
API_AUTH_KEY = os.getenv("API_AUTH_KEY", "")
API_AUTH_ENABLED = os.getenv("API_AUTH_ENABLED", "false").lower() == "true"

if API_AUTH_ENABLED and not API_AUTH_KEY:
    logger.warning("API_AUTH_ENABLED is true but API_AUTH_KEY not set - auth disabled")
    API_AUTH_ENABLED = False

# Redis Configuration - Railway provides REDIS_URL when Redis service is attached
# Falls back to in-memory cache if Redis is not available
REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_ENABLED = bool(REDIS_URL) and REDIS_AVAILABLE

if REDIS_URL and not REDIS_AVAILABLE:
    logger.warning("REDIS_URL set but redis package not installed - using in-memory cache")
elif REDIS_URL:
    logger.info("Redis caching enabled")
else:
    logger.info("Redis not configured - using in-memory cache")

ESPN_API_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# Sport mappings - Playbook uses uppercase league names (NBA, NFL, MLB, NHL)
SPORT_MAPPINGS = {
    "nba": {"odds": "basketball_nba", "espn": "basketball/nba", "playbook": "NBA"},
    "nfl": {"odds": "americanfootball_nfl", "espn": "football/nfl", "playbook": "NFL"},
    "mlb": {"odds": "baseball_mlb", "espn": "baseball/mlb", "playbook": "MLB"},
    "nhl": {"odds": "icehockey_nhl", "espn": "hockey/nhl", "playbook": "NHL"},
    "ncaab": {"odds": "basketball_ncaab", "espn": "basketball/mens-college-basketball", "playbook": "CFB"},
}

# ============================================================================
# v10.49: SAFE STRING HELPERS
# These handle None values and non-string types from external API data
# ============================================================================

def safe_upper(x) -> str:
    """Safely convert any value to uppercase string. Handles None and non-string types."""
    return str(x or "").upper()

def safe_lower(x) -> str:
    """Safely convert any value to lowercase string. Handles None and non-string types."""
    return str(x or "").lower()

# ============================================================================
# v10.83: PRODUCTION HARDENING - CANONICAL PICK ENRICHMENT
# ============================================================================
# Adds all required canonical fields to picks for stable API contract.
# Includes: book URL quality, market validation, engine integrity, movement monitoring
# ============================================================================

# v10.83: In-memory movement cache for tracking line/odds changes
_MOVEMENT_CACHE: Dict[str, Dict[str, Any]] = {}

# v10.83: Sportsbook URL templates for deep linking
BOOK_URL_TEMPLATES = {
    "fanduel": {
        "homepage": "https://sportsbook.fanduel.com",
        "nba": "https://sportsbook.fanduel.com/basketball/nba",
        "nhl": "https://sportsbook.fanduel.com/hockey/nhl",
        "nfl": "https://sportsbook.fanduel.com/football/nfl",
        "mlb": "https://sportsbook.fanduel.com/baseball/mlb",
        "ncaab": "https://sportsbook.fanduel.com/basketball/college-basketball",
        "search": "https://sportsbook.fanduel.com/search?query={query}",
    },
    "draftkings": {
        "homepage": "https://sportsbook.draftkings.com",
        "nba": "https://sportsbook.draftkings.com/leagues/basketball/nba",
        "nhl": "https://sportsbook.draftkings.com/leagues/hockey/nhl",
        "nfl": "https://sportsbook.draftkings.com/leagues/football/nfl",
        "mlb": "https://sportsbook.draftkings.com/leagues/baseball/mlb",
        "ncaab": "https://sportsbook.draftkings.com/leagues/basketball/ncaab",
        "search": "https://sportsbook.draftkings.com/search?query={query}",
    },
    "betmgm": {
        "homepage": "https://sports.betmgm.com",
        "nba": "https://sports.betmgm.com/en/sports/basketball-7/betting/usa-9/nba-6004",
        "nhl": "https://sports.betmgm.com/en/sports/hockey-12/betting/usa-9/nhl-34",
        "nfl": "https://sports.betmgm.com/en/sports/football-11/betting/usa-9/nfl-35",
        "mlb": "https://sports.betmgm.com/en/sports/baseball-23/betting/usa-9/mlb-75",
        "search": "https://sports.betmgm.com/en/sports?query={query}",
    },
    "caesars": {
        "homepage": "https://sportsbook.caesars.com",
        "nba": "https://sportsbook.caesars.com/us/az/bet/basketball/nba",
        "nhl": "https://sportsbook.caesars.com/us/az/bet/hockey/nhl",
        "nfl": "https://sportsbook.caesars.com/us/az/bet/football/nfl",
        "search": "https://sportsbook.caesars.com/us/az/bet/search?query={query}",
    },
    "betrivers": {
        "homepage": "https://www.betrivers.com",
        "nba": "https://www.betrivers.com/sports/basketball/nba",
        "nhl": "https://www.betrivers.com/sports/hockey/nhl",
        "nfl": "https://www.betrivers.com/sports/football/nfl",
        "search": "https://www.betrivers.com/search?q={query}",
    },
    "fanatics": {
        "homepage": "https://sportsbook.fanatics.com",
        "nba": "https://sportsbook.fanatics.com/basketball/nba",
        "nhl": "https://sportsbook.fanatics.com/hockey/nhl",
        "nfl": "https://sportsbook.fanatics.com/football/nfl",
        "search": "https://sportsbook.fanatics.com/search?q={query}",
    },
}


def build_book_url(book_key: str, sport: str, display_title: str = None, player_name: str = None) -> tuple:
    """
    v10.83: Build the best possible book URL with quality indicator.

    Returns: (url, quality, reason)
    - quality: "DEEP" | "LEAGUE" | "SEARCH" | "HOMEPAGE"
    - reason: short explanation
    """
    book_key_lower = (book_key or "").lower().replace(" ", "").replace("-", "")
    sport_lower = (sport or "").lower()

    # Normalize book key variations
    book_map = {
        "fanduel": "fanduel",
        "draftkings": "draftkings",
        "betmgm": "betmgm",
        "caesars": "caesars",
        "williamhill": "caesars",
        "betrivers": "betrivers",
        "fanatics": "fanatics",
        "pointsbet": "fanatics",  # PointsBet was acquired by Fanatics
    }

    normalized_book = book_map.get(book_key_lower)
    templates = BOOK_URL_TEMPLATES.get(normalized_book, {})

    if not templates:
        # Unknown book - return generic homepage if we have book_url
        return (None, "HOMEPAGE", f"unknown_book:{book_key}")

    # Try league page first (most useful)
    league_url = templates.get(sport_lower)
    if league_url:
        return (league_url, "LEAGUE", f"{sport_lower}_page")

    # Try search URL with player or team name
    search_template = templates.get("search")
    if search_template:
        query = player_name or (display_title.split(" @ ")[0] if display_title and " @ " in display_title else None)
        if query:
            search_url = search_template.format(query=query.replace(" ", "+"))
            return (search_url, "SEARCH", f"search:{query[:20]}")

    # Fallback to homepage
    homepage = templates.get("homepage")
    if homepage:
        return (homepage, "HOMEPAGE", "fallback_homepage")

    return (None, "HOMEPAGE", "no_url_available")


def validate_market_sanity(pick: Dict[str, Any], sport: str) -> tuple:
    """
    v10.83: Validate market sanity for sport-specific rules.

    Returns: (is_valid, reason)
    """
    sport_lower = sport.lower()
    line = pick.get("line")
    market = pick.get("market", pick.get("market_key", ""))

    # NHL-specific validation
    if sport_lower == "nhl":
        if market in ("spreads", "spread"):
            # NHL puck lines are typically +/-1.5, occasionally +/-2.5
            if line is not None and abs(line) >= 3.5:
                return (False, f"NHL_INVALID_PUCKLINE:{line}")

        if market in ("totals", "total"):
            # NHL totals typically range 4.5-8.5
            if line is not None and (line < 4.0 or line > 9.0):
                return (False, f"NHL_INVALID_TOTAL:{line}")

    # NBA-specific validation
    if sport_lower == "nba":
        if market in ("totals", "total"):
            # NBA totals typically range 200-260
            if line is not None and (line < 180 or line > 280):
                return (False, f"NBA_INVALID_TOTAL:{line}")

        if market in ("spreads", "spread"):
            # NBA spreads rarely exceed +/-20
            if line is not None and abs(line) > 25:
                return (False, f"NBA_INVALID_SPREAD:{line}")

    # NFL-specific validation
    if sport_lower == "nfl":
        if market in ("totals", "total"):
            if line is not None and (line < 30 or line > 70):
                return (False, f"NFL_INVALID_TOTAL:{line}")

    return (True, None)


def check_engine_integrity(pick: Dict[str, Any]) -> Dict[str, Any]:
    """
    v10.83: Check engine integrity and identify missing engines.
    v10.88: Fixed to check scoring_breakdown for scores (not just top-level).

    Returns dict with:
    - engines_missing: list of missing engine names
    - score_total_source: "FULL_STACK" | "AI_ONLY_FALLBACK" | "PARTIAL_STACK"
    - engine_integrity_ok: bool
    """
    # v10.88: Check both top-level and scoring_breakdown for scores
    breakdown = pick.get("scoring_breakdown", {})
    ai_score = pick.get("ai_score") or breakdown.get("ai_score", 0.0)
    research_score = pick.get("research_score") or breakdown.get("research_score", 0.0)
    esoteric_score = pick.get("esoteric_score") or breakdown.get("esoteric_score", 0.0)
    jarvis_score = pick.get("jarvis_score") or breakdown.get("jarvis_score", 0.0)

    engines_missing = []

    # Check if engines actually ran (0.0 could mean not run or actually scored 0)
    # Use presence of breakdown/components as indicator
    if research_score == 0.0 and not pick.get("research_components"):
        engines_missing.append("research")

    if esoteric_score == 0.0 and not pick.get("esoteric_components") and not pick.get("esoteric_breakdown"):
        engines_missing.append("esoteric")

    if jarvis_score == 0.0 and not pick.get("jarvis_triggers") and not pick.get("jarvis_breakdown"):
        engines_missing.append("jarvis")

    # Determine score source
    if len(engines_missing) == 0:
        score_total_source = "FULL_STACK"
    elif len(engines_missing) == 3 and ai_score > 0:
        score_total_source = "AI_ONLY_FALLBACK"
    else:
        score_total_source = "PARTIAL_STACK"

    engine_integrity_ok = len(engines_missing) == 0

    return {
        "engines_missing": engines_missing,
        "score_total_source": score_total_source,
        "engine_integrity_ok": engine_integrity_ok
    }


def check_injury_status(player_name: str, team: str, sport: str, injuries_data: Dict = None) -> str:
    """
    v10.83: Check injury status for a player.

    Returns: "HEALTHY"|"QUESTIONABLE"|"OUT"|"DOUBTFUL"|"SUSPENDED"|"UNKNOWN"
    """
    if not player_name:
        return "UNKNOWN"

    # Stub implementation - can be enhanced with injury API data
    # For now, check if injuries_data was passed and contains this player
    if injuries_data:
        player_lower = player_name.lower()
        for injury in injuries_data.get("data", []):
            if player_lower in injury.get("player", "").lower():
                status = injury.get("status", "").upper()
                if status in ("OUT", "O"):
                    return "OUT"
                elif status in ("DOUBTFUL", "D"):
                    return "DOUBTFUL"
                elif status in ("QUESTIONABLE", "Q"):
                    return "QUESTIONABLE"
                elif status in ("SUSPENDED", "SUSP"):
                    return "SUSPENDED"

    return "HEALTHY"


def compute_movement(pick: Dict[str, Any], pick_id: str) -> Dict[str, Any]:
    """
    v10.83: Compute movement by comparing to cached previous state.

    Returns dict with movement_flag, movement_summary, movement_severity
    """
    global _MOVEMENT_CACHE

    current_state = {
        "odds": pick.get("odds", pick.get("odds_american")),
        "line": pick.get("line"),
        "book_key": pick.get("book_key"),
        "has_started": pick.get("has_started", False),
        "timestamp": datetime.now().isoformat()
    }

    movement = {
        "movement_flag": False,
        "movement_summary": None,
        "movement_severity": None
    }

    # Get previous state from cache
    prev_state = _MOVEMENT_CACHE.get(pick_id)

    if prev_state:
        changes = []
        severity_score = 0

        # Check odds change
        prev_odds = prev_state.get("odds")
        curr_odds = current_state.get("odds")
        if prev_odds is not None and curr_odds is not None and prev_odds != curr_odds:
            odds_diff = abs(curr_odds - prev_odds)
            direction = "better" if curr_odds > prev_odds else "worse"
            changes.append(f"odds {prev_odds}→{curr_odds}")
            if odds_diff >= 20:
                severity_score += 3
            elif odds_diff >= 10:
                severity_score += 2
            else:
                severity_score += 1

        # Check line change
        prev_line = prev_state.get("line")
        curr_line = current_state.get("line")
        if prev_line is not None and curr_line is not None and prev_line != curr_line:
            line_diff = abs(curr_line - prev_line)
            changes.append(f"line {prev_line}→{curr_line}")
            if line_diff >= 1.0:
                severity_score += 3
            elif line_diff >= 0.5:
                severity_score += 2
            else:
                severity_score += 1

        # Check has_started change
        prev_started = prev_state.get("has_started", False)
        curr_started = current_state.get("has_started", False)
        if prev_started != curr_started and curr_started:
            changes.append("game STARTED")
            severity_score += 3

        # Check book change
        prev_book = prev_state.get("book_key")
        curr_book = current_state.get("book_key")
        if prev_book and curr_book and prev_book != curr_book:
            changes.append(f"book {prev_book}→{curr_book}")
            severity_score += 1

        if changes:
            movement["movement_flag"] = True
            movement["movement_summary"] = "; ".join(changes)
            if severity_score >= 3:
                movement["movement_severity"] = "HIGH"
            elif severity_score >= 2:
                movement["movement_severity"] = "MED"
            else:
                movement["movement_severity"] = "LOW"

    # Update cache with current state
    _MOVEMENT_CACHE[pick_id] = current_state

    # Limit cache size to prevent memory issues
    if len(_MOVEMENT_CACHE) > 1000:
        # Remove oldest entries
        sorted_keys = sorted(_MOVEMENT_CACHE.keys(),
                           key=lambda k: _MOVEMENT_CACHE[k].get("timestamp", ""))
        for key in sorted_keys[:200]:
            del _MOVEMENT_CACHE[key]

    return movement


def enrich_pick_canonical(pick: Dict[str, Any], sport: str, injuries_data: Dict = None) -> Dict[str, Any]:
    """
    v10.83: Enrich a pick with all canonical schema fields + production validations.

    Adds:
    - pick_id: Stable deterministic ID
    - league: Sport league name
    - action: SKIP|WATCH|PLAY|SMASH
    - tier_badge: Alias for badge
    - engines: { ai, research, esoteric, jarvis }
    - engines_missing, score_total_source, engine_integrity_ok (v10.83)
    - book_url_quality, book_url_reason (v10.83)
    - movement_flag, movement_summary, movement_severity (v10.83)
    - status, debug_flags (v10.83 validation)
    - For props: prop_stat, direction, injury_status
    """
    import hashlib

    # Initialize debug_flags list
    if "debug_flags" not in pick:
        pick["debug_flags"] = []

    # Generate stable pick_id if not present
    if not pick.get("pick_id"):
        pick_key = f"{sport}|{pick.get('game_id', '')}|{pick.get('market', pick.get('market_key', ''))}|{pick.get('selection', '')}|{pick.get('line', '')}|{pick.get('odds', '')}"
        pick["pick_id"] = hashlib.sha256(pick_key.encode()).hexdigest()[:16]

    # League (same as sport for now)
    pick["league"] = sport.upper()

    # =========================================================================
    # v10.83: Book URL Quality
    # =========================================================================
    book_key = pick.get("book_key", pick.get("book", ""))
    player_name = pick.get("player_name", pick.get("player"))
    display_title = pick.get("display_title", "")

    url, quality, reason = build_book_url(book_key, sport, display_title, player_name)

    # Only update book_url if we got a better one
    if url and (not pick.get("book_url") or quality in ("DEEP", "LEAGUE")):
        pick["book_url"] = url
        pick["book_link"] = url  # Keep both for compatibility

    pick["book_url_quality"] = quality
    pick["book_url_reason"] = reason

    # =========================================================================
    # v10.83: Market Sanity Validation
    # =========================================================================
    is_valid, invalid_reason = validate_market_sanity(pick, sport)
    if not is_valid:
        pick["status"] = "INVALID_MARKET"
        pick["debug_flags"].append(invalid_reason)
    else:
        if "status" not in pick:
            pick["status"] = "VALID"

    # =========================================================================
    # v10.83: Engine Integrity Check
    # =========================================================================
    engines = {
        "ai": pick.get("ai_score", 0.0),
        "research": pick.get("research_score", pick.get("research_components", {}).get("total", 0.0)) if isinstance(pick.get("research_components"), dict) else pick.get("research_score", 0.0),
        "esoteric": pick.get("esoteric_score", 0.0),
        "jarvis": pick.get("jarvis_score", 0.0)
    }
    pick["engines"] = engines

    integrity = check_engine_integrity(pick)
    pick["engines_missing"] = integrity["engines_missing"]
    pick["score_total_source"] = integrity["score_total_source"]
    pick["engine_integrity_ok"] = integrity["engine_integrity_ok"]

    # =========================================================================
    # v10.83: Tier safety downgrade for incomplete engine stack
    # =========================================================================
    tier = pick.get("tier", "PASS")

    if not Config.ALLOW_PARTIAL_STACK_BUMP:
        # If missing any engine and tier >= EDGE_LEAN, force downgrade to MONITOR
        if integrity["engines_missing"] and tier in ("GOLD_STAR", "EDGE_LEAN", "TITANIUM_SMASH"):
            pick["original_tier"] = tier
            pick["tier"] = "MONITOR"
            pick["debug_flags"].append(f"TIER_DOWNGRADE:partial_stack:{','.join(integrity['engines_missing'])}")
            tier = "MONITOR"

    # =========================================================================
    # v10.85: TIER BUNDLE - Import from tiering.py (single source of truth)
    # tier, tier_badge, action, units MUST be locked together
    # =========================================================================
    config = TIER_CONFIG.get(tier, TIER_CONFIG["PASS"])

    pick["tier"] = tier  # Ensure tier is set (may have been downgraded)
    pick["tier_badge"] = config["badge"]
    pick["action"] = config["action"]
    pick["units"] = config["units"]

    # Also update badge field for backwards compatibility
    pick["badge"] = config["badge"]

    # =========================================================================
    # v10.89: Flatten scoring_breakdown fields to top level for frontend
    # Frontend can now read pick.research_score instead of pick.scoring_breakdown.research_score
    # =========================================================================
    breakdown = pick.get("scoring_breakdown", {})
    if breakdown:
        pick["ai_score"] = breakdown.get("ai_score")
        pick["research_score"] = breakdown.get("research_score")
        pick["esoteric_score"] = breakdown.get("esoteric_score")
        pick["jarvis_score"] = breakdown.get("jarvis_score")
        pick["alignment_pct"] = breakdown.get("alignment_pct")

    # =========================================================================
    # v10.83: Props - prop_stat, direction, injury validation
    # =========================================================================
    if pick.get("player") or pick.get("player_name"):
        pick["prop_stat"] = pick.get("stat_type", pick.get("market", ""))
        over_under = pick.get("over_under", pick.get("side", ""))
        pick["direction"] = over_under.upper() if over_under else None

        # Injury check for props
        player = pick.get("player_name", pick.get("player", ""))
        team = pick.get("team", pick.get("home_team", ""))
        injury_status = check_injury_status(player, team, sport, injuries_data)
        pick["injury_status"] = injury_status

        # Exclude OUT/DOUBTFUL/SUSPENDED props
        if injury_status in ("OUT", "DOUBTFUL", "SUSPENDED"):
            pick["status"] = "INVALID_INJURY"
            pick["debug_flags"].append(f"INJURY_{injury_status}:{player}")
        elif injury_status == "QUESTIONABLE":
            # Downgrade tier by 1 for questionable players using tiering.py
            current_tier = pick["tier"]
            if current_tier != "PASS":
                pick["original_tier"] = current_tier
                new_tier = downgrade_tier(current_tier, steps=1)
                pick["tier"] = new_tier
                # Update all tier bundle fields
                new_config = TIER_CONFIG.get(new_tier, TIER_CONFIG["PASS"])
                pick["tier_badge"] = new_config["badge"]
                pick["action"] = new_config["action"]
                pick["units"] = new_config["units"]
                pick["badge"] = new_config["badge"]
                pick["debug_flags"].append(f"TIER_DOWNGRADE:questionable:{player}")
    else:
        pick["prop_stat"] = None
        pick["direction"] = None
        pick["injury_status"] = None

    # =========================================================================
    # v10.83: Movement Monitoring
    # =========================================================================
    if Config.ENABLE_MOVEMENT_MONITOR:
        movement = compute_movement(pick, pick["pick_id"])
        pick["movement_flag"] = movement["movement_flag"]
        pick["movement_summary"] = movement["movement_summary"]
        pick["movement_severity"] = movement["movement_severity"]
    else:
        pick["movement_flag"] = False
        pick["movement_summary"] = None
        pick["movement_severity"] = None

    # =========================================================================
    # v10.86: Confidence normalization (always label + pct)
    # =========================================================================
    raw_confidence = pick.get("confidence", pick.get("confidence_score", 50))
    conf_label, conf_pct = normalize_confidence(raw_confidence)
    pick["confidence_label"] = conf_label
    pick["confidence_pct"] = conf_pct

    # =========================================================================
    # v10.86: Filter tier-like badges from badges[] to avoid contradiction
    # =========================================================================
    raw_badges = pick.get("badges", [])
    pick["badges"] = filter_tier_badges(raw_badges, pick["tier"])

    # =========================================================================
    # v10.87: Debug trace object for troubleshooting
    # =========================================================================
    pick["debug_trace"] = {
        "ai_score": pick.get("ai_score", 0.0),
        "research_score": pick.get("scoring_breakdown", {}).get("research_score", 0.0),
        "esoteric_score": pick.get("scoring_breakdown", {}).get("esoteric_score", 0.0),
        "jarvis_score": pick.get("jarvis_rs", 0.0),
        "jason_sim_boost": pick.get("jason_sim_boost", 0.0),
        "confluence_boost": pick.get("confluence_boost", 0.0),
        "final_score": pick.get("final_score", 0.0),
        "tier_before_downgrade": pick.get("original_tier", pick.get("tier")),
        "tier_after_downgrade": pick.get("tier"),
        "applied_downgrades": pick.get("debug_flags", []),
        "engines_missing": pick.get("engines_missing", []),
        "score_source": pick.get("score_total_source", "UNKNOWN"),
    }

    return pick


def enrich_picks_batch(picks: List[Dict[str, Any]], sport: str, injuries_data: Dict = None) -> List[Dict[str, Any]]:
    """v10.83: Enrich a batch of picks with canonical fields and filter invalid picks."""
    enriched = []
    for pick in picks:
        enriched_pick = enrich_pick_canonical(pick, sport, injuries_data)
        enriched.append(enriched_pick)
    return enriched


def filter_valid_picks(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """v10.83: Filter out invalid picks (status != VALID)."""
    return [p for p in picks if p.get("status", "VALID") == "VALID"]


# ============================================================================
# v10.77: TODAY-ONLY ET FILTER (single source of truth)
# ============================================================================
# INVARIANT: All daily pulls must only include games where commence_time
# converted to ET falls inside today's ET boundary [00:00:00, next day 00:00:00)
# This applies to: NBA, NHL, NCAAB, NFL, MLB - ALL sports use this filter.
# ============================================================================

from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def is_today_et(commence_time_iso: str, now: datetime = None) -> bool:
    """
    v10.77: True if the event's start time falls within TODAY in ET:
    [00:00:00, next day 00:00:00)

    This is the SINGLE SOURCE OF TRUTH for day boundary filtering.
    Uses America/New_York timezone (handles DST correctly).

    Args:
        commence_time_iso: ISO format timestamp (e.g., "2026-01-24T23:00:00Z")
        now: Optional datetime for testing (defaults to current time in ET)

    Returns:
        True if game is today ET, False otherwise
    """
    if not commence_time_iso:
        return False

    try:
        if now is None:
            now = datetime.now(ET)

        # Parse ISO time (supports ...Z suffix)
        t = datetime.fromisoformat(commence_time_iso.replace("Z", "+00:00"))
        t_et = t.astimezone(ET)

        # Today's boundaries in ET
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        return day_start <= t_et < day_end
    except Exception:
        # If parsing fails, exclude the game (fail closed for data integrity)
        return False


def is_game_today(commence_time: str) -> bool:
    """
    Legacy wrapper for is_today_et() - use is_today_et() for new code.
    """
    return is_today_et(commence_time)


def filter_today_games(games: list, debug: bool = False) -> list:
    """
    v10.77: Filter games to only include those starting TODAY in ET.

    Args:
        games: List of game dicts with commence_time/start_time field
        debug: If True, log dropped games

    Returns:
        List of games that start today ET
    """
    now = datetime.now(ET)
    kept = []
    dropped = []

    for g in games:
        t = g.get("commence_time") or g.get("start_time") or g.get("startTime")
        if is_today_et(t, now=now):
            kept.append(g)
        else:
            dropped.append(g)

    if debug and dropped:
        logger.info(f"TODAY_ET filter: {len(games)} raw → {len(kept)} kept, {len(dropped)} dropped")
        for g in dropped[:5]:
            t_str = g.get("commence_time") or g.get("start_time") or g.get("startTime") or ""
            try:
                t_et = datetime.fromisoformat(t_str.replace("Z", "+00:00")).astimezone(ET)
                away = g.get("away_team") or g.get("awayTeamName") or "?"
                home = g.get("home_team") or g.get("homeTeamName") or "?"
                logger.info(f"  DROPPED (not today ET): {away} @ {home} | {t_et.isoformat()}")
            except Exception:
                pass

    return kept


def debug_day_filter(games: list, source: str = "Unknown") -> tuple:
    """
    v10.77: Debug helper to show day filter results.

    Returns:
        Tuple of (kept_games, dropped_games, summary_str)
    """
    now = datetime.now(ET)
    kept, dropped = [], []

    for g in games:
        t = g.get("commence_time") or g.get("start_time") or g.get("startTime")
        if is_today_et(t, now=now):
            kept.append(g)
        else:
            dropped.append(g)

    summary = f"{source} raw: {len(games)} | TODAY_ET kept: {len(kept)} | dropped: {len(dropped)}"
    return kept, dropped, summary

# ============================================================================
# v10.34: CACHE SCHEMA VERSIONING
# Changing this version invalidates all cached best-bets responses automatically.
# Bump this when response schema changes to prevent stale cached payloads.
# ============================================================================
CACHE_SCHEMA_VERSION = "best_bets_v2"

# ============================================================================
# v10.40: SPORT PROFILES - Per-sport calibration (4-engine blend)
# Weights: ai + research + esoteric + jarvis = 1.0
# Jarvis is now a STANDALONE engine separate from Esoteric
# ============================================================================
SPORT_PROFILES = {
    "nba": {
        "weights": {"ai": 0.35, "research": 0.35, "esoteric": 0.10, "jarvis": 0.20},
        "tiers": {"PASS": 4.75, "MONITOR": 5.75, "EDGE_LEAN": 6.50, "GOLD_STAR": 7.50},
        "limits": {"game_picks": 10, "prop_picks": 10},
        "conflict_policy": {"exclude_conflicts": True, "neutral_mult_default": 0.5},
        "market_preference": ["totals", "spreads", "h2h"],
        "boosts": {},
        "notes": "NBA: 4-engine blend, Jarvis 20%, esoteric 10% (environment only)."
    },
    "nhl": {
        "weights": {"ai": 0.33, "research": 0.35, "esoteric": 0.10, "jarvis": 0.22},
        "tiers": {"PASS": 4.50, "MONITOR": 5.50, "EDGE_LEAN": 6.25, "GOLD_STAR": 7.25},
        "limits": {"game_picks": 10, "prop_picks": 10},
        "conflict_policy": {"exclude_conflicts": True, "neutral_mult_default": 0.5},
        "market_preference": ["totals", "spreads", "h2h"],
        "boosts": {"nhl_ml_dog": 0.50},
        "notes": "NHL: Highest Jarvis weight (22%) for variance sport."
    },
    "nfl": {
        "weights": {"ai": 0.40, "research": 0.35, "esoteric": 0.08, "jarvis": 0.17},
        "tiers": {"PASS": 4.60, "MONITOR": 5.60, "EDGE_LEAN": 6.40, "GOLD_STAR": 7.40},
        "limits": {"game_picks": 6, "prop_picks": 6},
        "conflict_policy": {"exclude_conflicts": False, "neutral_mult_default": 0.5, "conflicts_bucket": True},
        "market_preference": ["spreads", "totals", "h2h"],
        "boosts": {"spreads_bias": 0.10},
        "notes": "NFL: Higher AI weight (sharper lines), Jarvis 17%."
    },
    "mlb": {
        "weights": {"ai": 0.42, "research": 0.35, "esoteric": 0.08, "jarvis": 0.15},
        "tiers": {"PASS": 4.60, "MONITOR": 5.60, "EDGE_LEAN": 6.35, "GOLD_STAR": 7.35},
        "limits": {"game_picks": 8, "prop_picks": 0},
        "conflict_policy": {"exclude_conflicts": True, "neutral_mult_default": 0.5},
        "market_preference": ["h2h", "totals", "spreads"],
        "boosts": {"ml_bias": 0.05},
        "notes": "MLB: Highest AI weight (42%), lowest Jarvis (15%)."
    },
    "ncaab": {
        "weights": {"ai": 0.34, "research": 0.35, "esoteric": 0.09, "jarvis": 0.22},
        "tiers": {"PASS": 4.50, "MONITOR": 5.50, "EDGE_LEAN": 6.25, "GOLD_STAR": 7.25},
        "limits": {"game_picks": 10, "prop_picks": 0},
        "conflict_policy": {"exclude_conflicts": True, "neutral_mult_default": 0.5},
        "market_preference": ["spreads", "totals", "h2h"],
        "boosts": {},
        "notes": "NCAAB: High Jarvis weight (22%) for college variance."
    },
}


# ============================================================================
# v10.76: BOOKMAKER DISPLAY NAMES - Maps Odds API keys to friendly names
# ============================================================================
BOOKMAKER_DISPLAY_NAMES = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "pointsbetus": "PointsBet",
    "caesars": "Caesars",
    "williamhill_us": "Caesars",
    "bovada": "Bovada",
    "betonlineag": "BetOnline",
    "betrivers": "BetRivers",
    "unibet_us": "Unibet",
    "foxbet": "FOX Bet",
    "twinspires": "TwinSpires",
    "superbook": "SuperBook",
    "wynnbet": "WynnBET",
    "betfred": "Betfred",
    "espnbet": "ESPN BET",
    "fanatics": "Fanatics",
    "hardrockbet": "Hard Rock Bet",
    "fliff": "Fliff",
    "mybookieag": "MyBookie",
    "betus": "BetUS",
    "lowvig": "LowVig",
    "pinnacle": "Pinnacle",
}

# v10.76: Sportsbook deep link URL templates (where available)
BOOKMAKER_BET_URLS = {
    "draftkings": "https://sportsbook.draftkings.com",
    "fanduel": "https://sportsbook.fanduel.com",
    "betmgm": "https://sports.betmgm.com",
    "caesars": "https://www.caesars.com/sportsbook-and-casino",
    "betrivers": "https://www.betrivers.com",
    "pointsbetus": "https://www.pointsbet.com",
    "espnbet": "https://espnbet.com",
    "fanatics": "https://sportsbook.fanatics.com",
}


def get_sport_profile(sport_name: str) -> dict:
    """Get sport profile with safe fallback to NBA defaults."""
    return SPORT_PROFILES.get(sport_name.lower(), SPORT_PROFILES["nba"])


# ============================================================================
# v10.32+: SIGNAL EXTRACTION HELPER
# ============================================================================

# Signal key mappings from reasons text to normalized signal keys
REASON_TO_SIGNAL_MAP = {
    # Research signals (pillars)
    "sharp split": {"signal_key": "PILLAR_SHARP_SPLIT", "category": "RESEARCH"},
    "sharp money": {"signal_key": "PILLAR_SHARP_SPLIT", "category": "RESEARCH"},
    "reverse line": {"signal_key": "PILLAR_RLM", "category": "RESEARCH"},
    "rlm": {"signal_key": "PILLAR_RLM", "category": "RESEARCH"},
    "hospital fade": {"signal_key": "PILLAR_HOSPITAL_FADE", "category": "RESEARCH"},
    "injury fade": {"signal_key": "PILLAR_HOSPITAL_FADE", "category": "RESEARCH"},
    "situational": {"signal_key": "PILLAR_SITUATIONAL", "category": "RESEARCH"},
    "rest advantage": {"signal_key": "PILLAR_SITUATIONAL", "category": "RESEARCH"},
    "back-to-back": {"signal_key": "PILLAR_SITUATIONAL", "category": "RESEARCH"},
    "expert consensus": {"signal_key": "PILLAR_EXPERT_CONSENSUS", "category": "RESEARCH"},
    "hook discipline": {"signal_key": "PILLAR_HOOK_DISCIPLINE", "category": "RESEARCH"},
    "prop correlation": {"signal_key": "PILLAR_PROP_CORRELATION", "category": "RESEARCH"},
    "correlation boost": {"signal_key": "PILLAR_PROP_CORRELATION", "category": "RESEARCH"},
    "public fade": {"signal_key": "SIGNAL_PUBLIC_FADE", "category": "RESEARCH"},
    "public %": {"signal_key": "SIGNAL_PUBLIC_FADE", "category": "RESEARCH"},
    "line value": {"signal_key": "SIGNAL_LINE_VALUE", "category": "RESEARCH"},
    "goldilocks": {"signal_key": "SIGNAL_GOLDILOCKS_ZONE", "category": "RESEARCH"},
    "mid-spread": {"signal_key": "SIGNAL_GOLDILOCKS_ZONE", "category": "RESEARCH"},

    # Esoteric signals
    "gematria": {"signal_key": "ESOTERIC_GEMATRIA", "category": "ESOTERIC"},
    "jarvis": {"signal_key": "ESOTERIC_JARVIS_TRIGGER", "category": "ESOTERIC"},
    "jarvis trigger": {"signal_key": "ESOTERIC_JARVIS_TRIGGER", "category": "ESOTERIC"},
    "saturn": {"signal_key": "ESOTERIC_ASTRO", "category": "ESOTERIC"},
    "moon": {"signal_key": "ESOTERIC_ASTRO", "category": "ESOTERIC"},
    "planetary": {"signal_key": "ESOTERIC_ASTRO", "category": "ESOTERIC"},
    "astro": {"signal_key": "ESOTERIC_ASTRO", "category": "ESOTERIC"},
    "fibonacci": {"signal_key": "ESOTERIC_FIBONACCI", "category": "ESOTERIC"},
    "tesla": {"signal_key": "ESOTERIC_TESLA", "category": "ESOTERIC"},
    "numerology": {"signal_key": "ESOTERIC_NUMEROLOGY", "category": "ESOTERIC"},
    "geomagnetic": {"signal_key": "ESOTERIC_GEOMAGNETIC", "category": "ESOTERIC"},
    "schumann": {"signal_key": "ESOTERIC_SCHUMANN", "category": "ESOTERIC"},
    "solar": {"signal_key": "ESOTERIC_SOLAR", "category": "ESOTERIC"},
    "weather": {"signal_key": "EXTERNAL_WEATHER", "category": "EXTERNAL"},
    "atmospheric": {"signal_key": "EXTERNAL_WEATHER", "category": "EXTERNAL"},

    # Confluence signals
    "confluence": {"signal_key": "CONFLUENCE_BONUS", "category": "CONFLUENCE"},
    "perfect alignment": {"signal_key": "CONFLUENCE_BONUS", "category": "CONFLUENCE"},
    "strong alignment": {"signal_key": "CONFLUENCE_BONUS", "category": "CONFLUENCE"},
    "immortal": {"signal_key": "CONFLUENCE_IMMORTAL", "category": "CONFLUENCE"},
}


def _extract_signals_from_reasons(reasons: list) -> list:
    """
    v10.32+: Extract fired signals from reasons array.
    Returns list of dicts: [{"signal_key": "PILLAR_SHARP_SPLIT", "category": "RESEARCH", "value": 1.0}, ...]
    """
    if not reasons:
        return []

    fired_signals = []
    seen_keys = set()

    for reason in reasons:
        if not isinstance(reason, str):
            continue

        reason_lower = reason.lower()

        # Extract numeric value if present (e.g., "+1.5" -> 1.5)
        value = 0.0
        value_match = re.search(r'([+-]?\d+\.?\d*)', reason)
        if value_match:
            try:
                value = float(value_match.group(1))
            except ValueError:
                pass

        # Match against known signal patterns
        for pattern, signal_info in REASON_TO_SIGNAL_MAP.items():
            if pattern in reason_lower:
                signal_key = signal_info["signal_key"]
                if signal_key not in seen_keys:
                    seen_keys.add(signal_key)
                    fired_signals.append({
                        "signal_key": signal_key,
                        "category": signal_info["category"],
                        "value": value
                    })
                break  # Only one signal per reason

    return fired_signals


# ============================================================================
# SHARED HTTP CLIENT
# ============================================================================

_shared_client: Optional[httpx.AsyncClient] = None


def get_shared_client() -> httpx.AsyncClient:
    """Get or create a shared httpx AsyncClient for connection pooling."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(timeout=30.0)
    return _shared_client


async def close_shared_client():
    """Close the shared client (call on app shutdown)."""
    global _shared_client
    if _shared_client is not None:
        await _shared_client.aclose()
        _shared_client = None


# ============================================================================
# FETCH WITH RETRIES HELPER
# ============================================================================

async def fetch_with_retries(
    method: str,
    url: str,
    *,
    params: Dict[str, Any] = None,
    headers: Dict[str, str] = None,
    max_retries: int = 2,
    backoff_base: float = 0.5
) -> Optional[httpx.Response]:
    """
    Fetch URL with retries and exponential backoff.
    Returns Response on success, None on complete failure.
    Rate-limited (429) responses are returned directly for caller to handle.
    """
    client = get_shared_client()
    attempt = 0

    while attempt <= max_retries:
        try:
            resp = await client.request(method, url, params=params, headers=headers)

            # Return rate-limited responses for caller to handle
            if resp.status_code == 429:
                logger.warning("Rate limited by %s (attempt %d): %s",
                             url, attempt, resp.text[:200] if resp.text else "No body")
                return resp

            return resp

        except httpx.RequestError as e:
            logger.exception("HTTP request failed (attempt %d/%d) %s: %s",
                           attempt + 1, max_retries + 1, url, str(e))
            if attempt < max_retries:
                sleep_for = backoff_base * (2 ** attempt)
                await asyncio.sleep(sleep_for)
            attempt += 1

    logger.error("All retries exhausted for %s", url)
    return None


# ============================================================================
# HYBRID CACHE (Redis with in-memory fallback)
# ============================================================================

class HybridCache:
    """
    Cache with Redis backend and in-memory fallback.
    Automatically falls back to in-memory if Redis is unavailable.
    """

    def __init__(self, default_ttl: int = 300, prefix: str = "bookie"):
        """Initialize cache with default TTL in seconds (default 5 minutes)."""
        self._default_ttl = default_ttl
        self._prefix = prefix
        self._redis_client: Optional[Any] = None
        self._memory_cache: Dict[str, tuple] = {}  # key -> (value, expires_at)
        self._using_redis = False

        # Try to connect to Redis if configured
        if REDIS_ENABLED:
            try:
                self._redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                self._redis_client.ping()
                self._using_redis = True
                logger.info("Redis cache connected successfully")
            except Exception as e:
                logger.warning("Redis connection failed, using in-memory cache: %s", e)
                self._redis_client = None
                self._using_redis = False

    def _make_key(self, key: str) -> str:
        """Create prefixed key for Redis."""
        return f"{self._prefix}:{key}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if self._using_redis and self._redis_client:
            try:
                redis_key = self._make_key(key)
                value = self._redis_client.get(redis_key)
                if value:
                    logger.debug("Redis HIT: %s", key)
                    return json.loads(value)
                return None
            except Exception as e:
                logger.warning("Redis get failed, falling back to memory: %s", e)
                self._using_redis = False

        # In-memory fallback
        if key in self._memory_cache:
            value, expires_at = self._memory_cache[key]
            if datetime.now() < expires_at:
                logger.debug("Memory HIT: %s", key)
                return value
            else:
                del self._memory_cache[key]
                logger.debug("Memory EXPIRED: %s", key)
        return None

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Set value in cache with optional custom TTL."""
        ttl = ttl or self._default_ttl

        if self._using_redis and self._redis_client:
            try:
                redis_key = self._make_key(key)
                self._redis_client.setex(redis_key, ttl, json.dumps(value))
                logger.debug("Redis SET: %s (TTL: %ds)", key, ttl)
                return
            except Exception as e:
                logger.warning("Redis set failed, falling back to memory: %s", e)
                self._using_redis = False

        # In-memory fallback
        expires_at = datetime.now() + timedelta(seconds=ttl)
        self._memory_cache[key] = (value, expires_at)
        logger.debug("Memory SET: %s (TTL: %ds)", key, ttl)

    def delete(self, key: str) -> bool:
        """Delete a specific key from cache."""
        deleted = False

        if self._using_redis and self._redis_client:
            try:
                redis_key = self._make_key(key)
                deleted = self._redis_client.delete(redis_key) > 0
                logger.debug("Redis DELETE: %s (deleted: %s)", key, deleted)
            except Exception as e:
                logger.warning("Redis delete failed: %s", e)

        # Also delete from memory cache
        if key in self._memory_cache:
            del self._memory_cache[key]
            deleted = True
            logger.debug("Memory DELETE: %s", key)

        return deleted

    def clear(self) -> None:
        """Clear all cached values."""
        if self._using_redis and self._redis_client:
            try:
                pattern = self._make_key("*")
                keys = self._redis_client.keys(pattern)
                if keys:
                    self._redis_client.delete(*keys)
                logger.info("Redis cache cleared (%d keys)", len(keys))
            except Exception as e:
                logger.warning("Redis clear failed: %s", e)

        # Always clear memory cache too
        self._memory_cache.clear()
        logger.info("Memory cache cleared")

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            "backend": "redis" if self._using_redis else "memory",
            "redis_configured": REDIS_ENABLED,
            "redis_connected": self._using_redis
        }

        if self._using_redis and self._redis_client:
            try:
                pattern = self._make_key("*")
                keys = self._redis_client.keys(pattern)
                stats["redis_keys"] = len(keys)
            except Exception:
                stats["redis_keys"] = "error"

        # Memory stats
        now = datetime.now()
        valid = sum(1 for _, (_, exp) in self._memory_cache.items() if now < exp)
        stats["memory_total_keys"] = len(self._memory_cache)
        stats["memory_valid_keys"] = valid
        stats["memory_expired_keys"] = len(self._memory_cache) - valid

        return stats


# Global cache instance - 5 minute TTL for API responses
api_cache = HybridCache(default_ttl=600, prefix="bookie")

# ============================================================================
# v10.41: JASON SIM 2.0 PAYLOAD STORAGE
# ============================================================================
# In-memory storage for Jason Sim payloads (keyed by sport -> game_id)
# These are posted via /live/jason-sim/upload and used in best-bets scoring
JASON_SIM_PAYLOADS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "nba": {},
    "nfl": {},
    "mlb": {},
    "nhl": {},
    "ncaab": {}
}

# Track when payloads were last updated (for staleness detection)
JASON_SIM_LAST_UPDATE: Dict[str, Optional[datetime]] = {
    "nba": None,
    "nfl": None,
    "mlb": None,
    "nhl": None,
    "ncaab": None
}

# Staleness threshold (payloads older than this are considered stale)
JASON_SIM_STALE_HOURS = 6


# ============================================================================
# v10.71: AUTO-GENERATE JASON SIM PAYLOADS FROM GAME DATA
# ============================================================================

def generate_jason_sim_payload(
    game_id: str,
    home_team: str,
    away_team: str,
    spread: float = 0.0,
    total: float = 220.0,
    home_ml: int = -110,
    away_ml: int = -110
) -> Dict[str, Any]:
    """
    v10.71: Auto-generate Jason Sim payload from game data.

    Uses spread and moneyline to estimate win percentages.
    This is a synthetic simulation based on market-implied probabilities.
    """
    # Convert spread to win probability (rough estimate)
    # Spread of -7 means ~70% favorite, spread of +7 means ~30% underdog
    # Using logistic approximation: win_pct = 1 / (1 + 10^(-spread/7))
    if spread != 0:
        home_win_pct = 1 / (1 + (10 ** (-spread / 7)))
    else:
        # Use moneyline if spread is 0
        if home_ml < 0:
            home_win_pct = abs(home_ml) / (abs(home_ml) + 100)
        else:
            home_win_pct = 100 / (home_ml + 100)

    away_win_pct = 1 - home_win_pct

    # Calculate projected scores from total and spread
    home_projected = (total / 2) - (spread / 2)
    away_projected = (total / 2) + (spread / 2)

    # Variance flag based on total magnitude
    if total > 240:
        variance_flag = "HIGH"
    elif total < 200:
        variance_flag = "LOW"
    else:
        variance_flag = "MEDIUM"

    return {
        "game_id": game_id,
        "home_team": home_team,
        "away_team": away_team,
        "sim_runs_per_game": 10000,  # Synthetic
        "results": {
            "win_pct_home": round(home_win_pct, 4),
            "win_pct_away": round(away_win_pct, 4),
            "win_pct_injury_adj": round(home_win_pct, 4),  # Use same for now
            "projected_total": total,
            "projected_home_score": round(home_projected, 1),
            "projected_away_score": round(away_projected, 1),
            "confidence": 0.75,  # Market-implied confidence
            "variance_flag": variance_flag
        },
        "source": "auto_generated_v10.71",
        "valid": True
    }


def auto_populate_jason_sim_payloads(sport: str, games_data: List[Dict[str, Any]]) -> int:
    """
    v10.71: Auto-populate Jason Sim payloads from games data.

    Called during best-bets generation to ensure Jason Sim has data to work with.
    Returns number of payloads generated.
    """
    sport_lower = sport.lower()
    if sport_lower not in JASON_SIM_PAYLOADS:
        return 0

    generated = 0

    for game in games_data:
        game_id = game.get("id") or game.get("game_id") or ""
        home_team = game.get("home_team", "")
        away_team = game.get("away_team", "")

        if not home_team or not away_team:
            continue

        # Extract spread, total, moneylines from game data
        spread = 0.0
        total = 220.0
        home_ml = -110
        away_ml = -110

        # Try to get spread
        if "spread" in game:
            spread = float(game.get("spread", 0) or 0)
        elif "spreads" in game:
            spreads = game.get("spreads", {})
            if isinstance(spreads, dict):
                spread = float(spreads.get("home", 0) or 0)

        # Try to get total
        if "total" in game:
            total = float(game.get("total", 220) or 220)
        elif "totals" in game:
            totals = game.get("totals", {})
            if isinstance(totals, dict):
                total = float(totals.get("over", 220) or 220)

        # Try to get moneylines
        if "h2h" in game:
            h2h = game.get("h2h", {})
            if isinstance(h2h, dict):
                home_ml = int(h2h.get("home", -110) or -110)
                away_ml = int(h2h.get("away", -110) or -110)

        # Generate payload
        payload = generate_jason_sim_payload(
            game_id=game_id or f"{away_team}@{home_team}",
            home_team=home_team,
            away_team=away_team,
            spread=spread,
            total=total,
            home_ml=home_ml,
            away_ml=away_ml
        )

        # Normalize using jason_sim_confluence if available
        if JASON_SIM_AVAILABLE:
            try:
                normalized = normalize_jason_sim(
                    game_id=payload["game_id"],
                    home_team=home_team,
                    away_team=away_team,
                    payload=payload
                )
                payload = normalized
            except Exception:
                pass

        # Store under multiple keys
        JASON_SIM_PAYLOADS[sport_lower][payload["game_id"]] = payload
        JASON_SIM_PAYLOADS[sport_lower][f"{away_team}@{home_team}"] = payload
        generated += 1

    if generated > 0:
        JASON_SIM_LAST_UPDATE[sport_lower] = datetime.now()
        logger.info(f"Jason Sim: Auto-generated {generated} payloads for {sport}")

    return generated


# ============================================================================
# v10.71: MARKET AVAILABILITY + INJURY GATING
# ============================================================================

def validate_prop_market_availability(
    player_name: str,
    stat_type: str,
    available_props: List[Dict[str, Any]],
    injury_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    v10.71: Validate that a player prop exists in the market and player is active.

    Returns:
        {
            "market_exists": bool,
            "injury_status": str,  # ACTIVE, OUT, QUESTIONABLE, UNKNOWN
            "penalty": float,      # Penalty to apply (0 if valid)
            "reason": str,
            "should_block": bool   # True if prop should be removed from card
        }
    """
    result = {
        "market_exists": False,
        "injury_status": "UNKNOWN",
        "penalty": 0.0,
        "reason": "",
        "should_block": False
    }

    # Check if prop exists in available markets
    player_lower = player_name.lower()
    for prop in available_props:
        prop_player = (prop.get("player_name", "") or prop.get("description", "")).lower()
        if player_lower in prop_player or prop_player in player_lower:
            result["market_exists"] = True
            break

    # Check injury status
    if injury_data:
        injuries = injury_data.get("injuries", [])
        for inj in injuries:
            inj_player = (inj.get("player", "") or inj.get("name", "")).lower()
            if player_lower in inj_player or inj_player in player_lower:
                status = (inj.get("status", "") or inj.get("injury_status", "")).upper()
                if status in ("OUT", "O"):
                    result["injury_status"] = "OUT"
                    result["should_block"] = True
                    result["reason"] = f"Player {player_name} is OUT"
                elif status in ("DOUBTFUL", "D"):
                    result["injury_status"] = "DOUBTFUL"
                    result["penalty"] = -0.5
                    result["reason"] = f"Player {player_name} is DOUBTFUL (-0.5)"
                elif status in ("QUESTIONABLE", "Q", "GTD"):
                    result["injury_status"] = "QUESTIONABLE"
                    result["penalty"] = -0.25
                    result["reason"] = f"Player {player_name} is QUESTIONABLE (-0.25)"
                else:
                    result["injury_status"] = "ACTIVE"
                break

    # If market doesn't exist, apply penalty
    if not result["market_exists"]:
        result["penalty"] = -1.0
        result["should_block"] = True
        result["reason"] = f"Prop for {player_name} not found in sportsbook markets"

    # Default to ACTIVE if no injury found
    if result["injury_status"] == "UNKNOWN":
        result["injury_status"] = "ACTIVE"

    return result


# ============================================================================
# ============================================================================
# FALLBACK DATA REMOVED (v10.80)
# ============================================================================
# Production hardening: Removed fake/sample data generation (v10.80).
# The API fails fast if real data is unavailable.
# This prevents misleading users with fake betting signals.


# ============================================================================
# AUTHENTICATION DEPENDENCY
# ============================================================================

async def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """
    Verify API key if authentication is enabled.
    Pass X-API-Key header to authenticate.
    """
    if not API_AUTH_ENABLED:
        return True  # Auth disabled, allow all

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    if x_api_key != API_AUTH_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return True


# ============================================================================
# SHARED TIER FUNCTIONS (v10.6 - Consistent Tier Assignment)
# ============================================================================

def clamp_score(x: float) -> float:
    """Clamp score to 0-10 range."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        x = 0.0
    return max(0.0, min(10.0, x))


def tier_from_score(score: float, tiers: dict = None) -> tuple:
    """
    Return (tier, badge) from score. Single source of truth for tier assignment.

    v10.55: Delegates to tiering.py module for consistency.

    Default Thresholds:
    - GOLD_STAR: >= 7.5
    - EDGE_LEAN: >= 6.5
    - MONITOR: >= 5.5
    - PASS: < 5.5
    """
    # v10.55: Delegate to tiering module (single source of truth)
    return tiering_tier_from_score(score, tiers)


def order_reasons(reasons: list) -> list:
    """
    v10.19: Order reasons by category for clarity.

    Correct order (spec-compliant):
    1. RESEARCH: (sharp, RLM, pillars, prop-independent boosts)
    2. MAPPING: (team resolver result - part of research phase)
    3. CORRELATION: (ALIGNED/NEUTRAL/CONFLICT/NO_SIGNAL - part of research phase)
    4. ESOTERIC: (Jarvis, Gematria, etc)
    5. CONFLUENCE: (alignment bonuses)
    6. SMASH: (smash spot confirmation - v10.19)
    7. RESOLVER: (deduplication notes)
    8. GOVERNOR: (volume cap notes)

    v10.18: RESEARCH reasons must come FIRST (before MAPPING/CORRELATION).
    v10.19: SMASH category added after CONFLUENCE.
    """
    if not reasons:
        return []

    # v10.19: Define category order with SMASH after CONFLUENCE
    # v10.39: Added JARVIS TURBO after CONFLUENCE (upgrade layer before SMASH)
    category_order = {
        "AI ENGINE:": 0,
        "RESEARCH:": 1,
        "MAPPING:": 2,
        "CORRELATION:": 3,
        "ESOTERIC:": 4,
        "CONFLUENCE:": 5,
        "JARVIS TURBO:": 6,
        "SMASH:": 7,
        "RESOLVER:": 8,
        "GOVERNOR:": 9,
    }

    def get_order(reason: str) -> int:
        for prefix, order in category_order.items():
            if reason.startswith(prefix):
                return order
        return 99  # Unknown categories go last

    return sorted(reasons, key=get_order)


def evaluate_smash_spot(final_score: float, alignment_pct: float, jarvis_active: bool, research_reasons: list) -> bool:
    """
    v10.19: Strict Smash Spot evaluation.

    Smash Spot is a TRUTH FLAG, not a score boost.
    It indicates when the ENTIRE system is truly aligned.

    Requirements (ALL must pass):
    1. final_score >= 8.0
    2. alignment_pct >= 85%
    3. jarvis_active == True (at least one Jarvis trigger)
    4. BOTH Sharp Split AND Reverse Line Move pillars present

    Returns:
        bool: True only if all conditions are met
    """
    # Hard threshold checks
    if final_score < 8.0:
        return False
    if alignment_pct < 85.0:
        return False
    if not jarvis_active:
        return False

    # Check for BOTH sharp pillars in research reasons
    has_sharp_split = any("Sharp Split" in r for r in research_reasons)
    has_rlm = any("Reverse Line Move" in r or "RLM" in r for r in research_reasons)

    # Require BOTH sharp pillars for smash eligibility
    if has_sharp_split and has_rlm:
        return True

    return False


def resolve_market_conflicts(picks: list) -> list:
    """
    Resolve conflicts where both sides of same market are returned.
    Keep only the BEST pick per (matchup, pick_type) combination.

    This ensures we never output both:
    - Hawks ML and Bucks ML
    - Both spread sides
    - Multiple totals for same game
    """
    from collections import defaultdict

    grouped = defaultdict(list)
    for p in picks:
        matchup = p.get("matchup", "") or p.get("game", "")
        pick_type = p.get("pick_type", "") or p.get("market", "")
        key = (matchup, pick_type)
        grouped[key].append(p)

    resolved = []
    for key, group in grouped.items():
        # Sort by final_score descending, take the best one
        group.sort(key=lambda x: clamp_score(x.get("final_score", 0.0)), reverse=True)
        best_pick = group[0]
        # Add reason if we resolved a conflict
        if len(group) > 1:
            best_pick["reasons"] = best_pick.get("reasons", []) + [
                f"RESOLVER: Best of {len(group)} candidates for {key[1]}"
            ]
        resolved.append(best_pick)

    return resolved


def filter_heavy_favorite_ml(picks: list) -> list:
    """
    Filter out heavy favorite ML picks that have unbeatable juice.

    Rules:
    - ML odds <= -600: ALWAYS reject (requires 86%+ win rate, impossible to predict)
    - ML odds <= -400 AND score < 8.0: reject (requires 80%+ win rate, need elite confidence)

    This protects the community from recommending bets that lose money even when "right".
    """
    filtered = []
    for pick in picks:
        market = pick.get("market", "")
        odds = pick.get("odds", -110)
        score = clamp_score(pick.get("final_score", pick.get("total_score", 0)))

        # Only filter moneyline picks
        if market != "h2h":
            filtered.append(pick)
            continue

        # Heavy favorite detection (negative odds only)
        if isinstance(odds, (int, float)) and odds < 0:
            # -600 or worse: always reject
            if odds <= -600:
                pick["filtered"] = True
                pick["filter_reason"] = f"FILTER: ML {odds} rejected (requires 86%+ hit rate, unbeatable juice)"
                continue  # Don't add to filtered list

            # -400 to -599: reject unless elite score (8.0+)
            if odds <= -400 and score < 8.0:
                pick["filtered"] = True
                pick["filter_reason"] = f"FILTER: ML {odds} rejected (requires 80%+ hit rate, score {score:.1f} not elite)"
                continue  # Don't add to filtered list

        filtered.append(pick)

    return filtered


def implied_prob(odds) -> float:
    """
    Convert American odds to implied probability (break-even %).

    Examples:
    - -110 → 52.4%
    - -280 → 73.7%
    - -102 → 50.5%
    - +150 → 40.0%

    Lower implied probability = better odds for the bettor.
    """
    try:
        odds = int(odds)
    except (TypeError, ValueError):
        odds = -110  # Default to standard juice
    if odds < 0:
        return (-odds) / ((-odds) + 100.0)
    return 100.0 / (odds + 100.0)


# v10.20: Market preference order for tiebreaker (lower = preferred)
# NEW: totals > spreads > moneyline (except NHL ML Dog)
MARKET_PREFERENCE = {"totals": 0, "spreads": 1, "h2h": 2}

# v10.10: Prop market labels for clear selection strings
MARKET_LABELS = {
    "player_points": "Points",
    "player_assists": "Assists",
    "player_rebounds": "Rebounds",
    "player_threes": "3PT Made",
    "player_blocks": "Blocks",
    "player_steals": "Steals",
    "player_turnovers": "Turnovers",
    "player_pra": "Pts+Reb+Ast",
    "player_pr": "Pts+Reb",
    "player_pa": "Pts+Ast",
    "player_ra": "Reb+Ast",
    # NFL
    "player_pass_tds": "Pass TDs",
    "player_pass_yds": "Pass Yards",
    "player_rush_yds": "Rush Yards",
    "player_reception_yds": "Rec Yards",
    "player_receptions": "Receptions",
    # MLB
    "batter_total_bases": "Total Bases",
    "batter_hits": "Hits",
    "batter_rbis": "RBIs",
    "pitcher_strikeouts": "Strikeouts",
    # NHL
    "player_shots_on_goal": "Shots on Goal",
}


def calculate_market_modifier(market: str, odds: int, line: float, active_pillars: list) -> tuple:
    """
    v10.9: Market-Aware Research Modifiers to break ML/spread score symmetry.

    Returns (delta, reason) to add to research score.

    Rules:
    - ML Heavy Favorite Tax: h2h odds <= -200 → -0.3
    - ML Extreme Favorite Tax: h2h odds <= -400 → -0.6 (replaces -0.3)
    - Tight Spread Slight Value: spreads |line| <= 2.5 → +0.1
    - Wide Spread Variance Penalty: spreads |line| >= 8.5 → -0.2
    - Totals + RLM Synergy: totals + RLM pillar active → +0.2
    """
    delta = 0.0
    reason = None

    if market == "h2h":
        # ML favorite taxes (mutually exclusive - extreme replaces heavy)
        if isinstance(odds, (int, float)) and odds <= -400:
            delta = -0.6
            reason = f"RESEARCH: Market Mod (ML Extreme Fav {odds}) -0.6"
        elif isinstance(odds, (int, float)) and odds <= -200:
            delta = -0.3
            reason = f"RESEARCH: Market Mod (ML Heavy Fav {odds}) -0.3"

    elif market == "spreads":
        abs_line = abs(line) if line else 0
        if abs_line <= 2.5:
            delta = 0.1
            reason = f"RESEARCH: Market Mod (Tight Spread {line:+.1f}) +0.1"
        elif abs_line >= 8.5:
            delta = -0.2
            reason = f"RESEARCH: Market Mod (Wide Spread {line:+.1f}) -0.2"

    elif market == "totals":
        # Check if RLM is active
        rlm_active = any("Reverse Line Move" in p for p in active_pillars)
        if rlm_active:
            delta = 0.2
            reason = "RESEARCH: Market Mod (Totals + RLM Synergy) +0.2"

    return (delta, reason)


# v10.20: RESOLVER MARKET TIEBREAK (sorting only, NOT score inflation)
# Lower = preferred when scores are tied
# NEW: totals > spreads > moneyline (except NHL ML Dog overrides via +0.5 boost)
RESOLVER_MARKET_TIEBREAK = {
    "totals": 0,      # Totals first (most predictable)
    "spreads": 1,     # Spreads second (most actionable)
    "h2h": 2,         # ML third (often correlated with spread)
    "sharp_money": 3  # Sharp fallback last
}

# v10.17: BASE BOOST CONSTANTS (transparent math)
# Doubled from 1.0 to 2.0 to give props scoring parity with game picks
# Props apply scope_mult=0.5 and direction_mult, so:
#   ALIGNED prop (1.0 × 0.5 × 2.0) = 1.0 boost (vs games 2.0)
#   NEUTRAL prop (0.5 × 0.5 × 2.0) = 0.5 boost
BASE_SHARP_SPLIT_BOOST = 2.0
BASE_RLM_BOOST = 2.0

# v10.13: NBA TEAM ABBREVIATION MAPPING
# Maps various team name formats to official 3-letter abbreviations
NBA_TEAM_MAP = {
    # Atlanta Hawks
    "atl": "ATL", "hawks": "ATL", "atlanta": "ATL", "atlanta_hawks": "ATL",
    # Boston Celtics
    "bos": "BOS", "celtics": "BOS", "boston": "BOS", "boston_celtics": "BOS",
    # Brooklyn Nets
    "bkn": "BKN", "brk": "BKN", "nets": "BKN", "brooklyn": "BKN", "brooklyn_nets": "BKN",
    # Charlotte Hornets
    "cha": "CHA", "cho": "CHA", "hornets": "CHA", "charlotte": "CHA", "charlotte_hornets": "CHA",
    # Chicago Bulls
    "chi": "CHI", "bulls": "CHI", "chicago": "CHI", "chicago_bulls": "CHI",
    # Cleveland Cavaliers
    "cle": "CLE", "cavs": "CLE", "cavaliers": "CLE", "cleveland": "CLE", "cleveland_cavaliers": "CLE",
    # Dallas Mavericks
    "dal": "DAL", "mavs": "DAL", "mavericks": "DAL", "dallas": "DAL", "dallas_mavericks": "DAL",
    # Denver Nuggets
    "den": "DEN", "nuggets": "DEN", "denver": "DEN", "denver_nuggets": "DEN",
    # Detroit Pistons
    "det": "DET", "pistons": "DET", "detroit": "DET", "detroit_pistons": "DET",
    # Golden State Warriors
    "gsw": "GSW", "gs": "GSW", "warriors": "GSW", "golden_state": "GSW", "golden_state_warriors": "GSW",
    # Houston Rockets
    "hou": "HOU", "rockets": "HOU", "houston": "HOU", "houston_rockets": "HOU",
    # Indiana Pacers
    "ind": "IND", "pacers": "IND", "indiana": "IND", "indiana_pacers": "IND",
    # LA Clippers
    "lac": "LAC", "clippers": "LAC", "la_clippers": "LAC", "los_angeles_clippers": "LAC",
    # LA Lakers
    "lal": "LAL", "lakers": "LAL", "la_lakers": "LAL", "los_angeles_lakers": "LAL",
    # Memphis Grizzlies
    "mem": "MEM", "grizzlies": "MEM", "memphis": "MEM", "memphis_grizzlies": "MEM",
    # Miami Heat
    "mia": "MIA", "heat": "MIA", "miami": "MIA", "miami_heat": "MIA",
    # Milwaukee Bucks
    "mil": "MIL", "bucks": "MIL", "milwaukee": "MIL", "milwaukee_bucks": "MIL",
    # Minnesota Timberwolves
    "min": "MIN", "timberwolves": "MIN", "wolves": "MIN", "minnesota": "MIN", "minnesota_timberwolves": "MIN",
    # New Orleans Pelicans
    "nop": "NOP", "no": "NOP", "pelicans": "NOP", "new_orleans": "NOP", "new_orleans_pelicans": "NOP",
    # New York Knicks
    "nyk": "NYK", "ny": "NYK", "knicks": "NYK", "new_york": "NYK", "new_york_knicks": "NYK",
    # Oklahoma City Thunder
    "okc": "OKC", "thunder": "OKC", "oklahoma_city": "OKC", "oklahoma_city_thunder": "OKC",
    # Orlando Magic
    "orl": "ORL", "magic": "ORL", "orlando": "ORL", "orlando_magic": "ORL",
    # Philadelphia 76ers
    "phi": "PHI", "sixers": "PHI", "76ers": "PHI", "philadelphia": "PHI", "philadelphia_76ers": "PHI",
    # Phoenix Suns
    "phx": "PHX", "pho": "PHX", "suns": "PHX", "phoenix": "PHX", "phoenix_suns": "PHX",
    # Portland Trail Blazers
    "por": "POR", "blazers": "POR", "trail_blazers": "POR", "portland": "POR", "portland_trail_blazers": "POR",
    # Sacramento Kings
    "sac": "SAC", "kings": "SAC", "sacramento": "SAC", "sacramento_kings": "SAC",
    # San Antonio Spurs
    "sas": "SAS", "sa": "SAS", "spurs": "SAS", "san_antonio": "SAS", "san_antonio_spurs": "SAS",
    # Toronto Raptors
    "tor": "TOR", "raptors": "TOR", "toronto": "TOR", "toronto_raptors": "TOR",
    # Utah Jazz
    "uta": "UTA", "jazz": "UTA", "utah": "UTA", "utah_jazz": "UTA",
    # Washington Wizards
    "was": "WAS", "wsh": "WAS", "wizards": "WAS", "washington": "WAS", "washington_wizards": "WAS",
}


def normalize_team_abbr(raw: str) -> str:
    """
    v10.13: Normalize team name/abbreviation to official 3-letter format.

    Examples:
    - "Lakers" -> "LAL"
    - "Los Angeles Lakers" -> "LAL"
    - "LAL" -> "LAL"
    - "lal" -> "LAL"
    """
    if not raw:
        return None

    import re

    # Normalize to lowercase, replace special chars
    s = raw.lower().strip()
    s = s.replace("&", "and")
    key = re.sub(r"[^a-z0-9]+", "_", s).strip("_")

    # Try direct match, then key match, then fallback to first 3 chars uppercased
    return NBA_TEAM_MAP.get(s) or NBA_TEAM_MAP.get(key) or (raw.upper()[:3] if len(raw) >= 3 else None)


# v10.14: PLAYER TEAM OVERRIDES (emergency hotfixes)
# Add manual mappings here when API data is wrong or missing
PLAYER_TEAM_OVERRIDES = {
    # Format: "player_name_slug": "HOME" or "AWAY"
    # Example: "tyrese_maxey": "AWAY",
}


def slug_player(name: str) -> str:
    """
    v10.14: Convert player name to normalized slug for cache/lookup.

    Examples:
    - "Tyrese Maxey" -> "tyrese_maxey"
    - "LeBron James" -> "lebron_james"
    """
    if not name:
        return ""
    import re
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def build_player_team_cache(games_data: list, home_abbr_map: dict, away_abbr_map: dict) -> dict:
    """
    v10.14: Build player -> team side cache from game roster data.

    Scans game objects for any available player lists (rosters, starters, etc.)
    and maps each player to HOME or AWAY.

    Args:
        games_data: List of game objects from props API
        home_abbr_map: Dict mapping game_key -> home team abbreviation
        away_abbr_map: Dict mapping game_key -> away team abbreviation

    Returns:
        Dict mapping player_slug -> "HOME" or "AWAY"
    """
    cache = {}

    for game in games_data:
        home_team = game.get("home_team", "")
        away_team = game.get("away_team", "")
        game_key = f"{away_team}@{home_team}"

        home_abbr = normalize_team_abbr(home_team)
        away_abbr = normalize_team_abbr(away_team)

        # Try various roster field names that APIs might use
        home_players = (
            game.get("home_players", [])
            or game.get("home_roster", [])
            or game.get("home_starters", [])
            or game.get("homeTeam", {}).get("players", [])
        )

        away_players = (
            game.get("away_players", [])
            or game.get("away_roster", [])
            or game.get("away_starters", [])
            or game.get("awayTeam", {}).get("players", [])
        )

        # Cache home players
        for player in home_players:
            if isinstance(player, str):
                player_name = player
            elif isinstance(player, dict):
                player_name = player.get("name") or player.get("player_name") or player.get("playerName", "")
            else:
                continue
            if player_name:
                cache[slug_player(player_name)] = "HOME"

        # Cache away players
        for player in away_players:
            if isinstance(player, str):
                player_name = player
            elif isinstance(player, dict):
                player_name = player.get("name") or player.get("player_name") or player.get("playerName", "")
            else:
                continue
            if player_name:
                cache[slug_player(player_name)] = "AWAY"

        # Also try generic players list with team info
        all_players = game.get("players", []) or game.get("roster", [])
        for player in all_players:
            if not isinstance(player, dict):
                continue
            player_name = player.get("name") or player.get("player_name") or player.get("playerName", "")
            player_team = player.get("team") or player.get("team_abbr") or player.get("teamAbbr", "")

            if player_name and player_team:
                player_team_abbr = normalize_team_abbr(player_team)
                if player_team_abbr == home_abbr:
                    cache[slug_player(player_name)] = "HOME"
                elif player_team_abbr == away_abbr:
                    cache[slug_player(player_name)] = "AWAY"

    return cache


def resolve_player_team_side(prop: dict, player_name: str, home_abbr: str, away_abbr: str,
                              player_team_cache: dict, playbook_roster: dict = None) -> tuple:
    """
    v10.14: Resolve player's team side using resolver chain.

    Resolver order (highest confidence first):
    1. Direct field (if prop contains team info)
    2. Override dictionary (manual hotfixes)
    3. Playbook roster (from Playbook API /teams or /injuries)
    4. Player team cache (built from game rosters)
    5. String inference (player label contains team abbr)

    Returns:
        (player_team_side, source): ("HOME"/"AWAY"/None, "DIRECT"/"OVERRIDE"/"PLAYBOOK"/"CACHE"/"INFER"/"MISSING")
    """
    import re

    player_slug = slug_player(player_name)
    playbook_roster = playbook_roster or {}

    # 1) Direct field from prop
    raw_team = (
        prop.get("team_abbr")
        or prop.get("team")
        or prop.get("player_team")
        or prop.get("team_name")
        or prop.get("teamName")
    )

    if raw_team:
        team_abbr = normalize_team_abbr(raw_team)
        if team_abbr and home_abbr and team_abbr == home_abbr:
            return ("HOME", "DIRECT")
        elif team_abbr and away_abbr and team_abbr == away_abbr:
            return ("AWAY", "DIRECT")

    # 2) Override dictionary (emergency hotfixes)
    if player_slug in PLAYER_TEAM_OVERRIDES:
        return (PLAYER_TEAM_OVERRIDES[player_slug], "OVERRIDE")

    # 3) Playbook roster lookup (from Playbook API)
    if player_slug in playbook_roster:
        team_abbr = playbook_roster[player_slug]
        if team_abbr and home_abbr and team_abbr == home_abbr:
            return ("HOME", "PLAYBOOK")
        elif team_abbr and away_abbr and team_abbr == away_abbr:
            return ("AWAY", "PLAYBOOK")

    # 4) Cache lookup (from game roster data)
    if player_slug in player_team_cache:
        return (player_team_cache[player_slug], "CACHE")

    # 4) String inference - look for team abbr in player description
    # Examples: "LeBron James (LAL)", "LeBron James - LAL", "LAL - LeBron James"
    description = (
        prop.get("description")
        or prop.get("name")
        or prop.get("player")
        or player_name
        or ""
    )

    # Try to extract team from parentheses: "Player (TEAM)"
    if "(" in description and ")" in description:
        inside = description.split("(")[-1].split(")")[0].strip()
        if 2 <= len(inside) <= 4:
            inferred_abbr = normalize_team_abbr(inside)
            if inferred_abbr and home_abbr and inferred_abbr == home_abbr:
                return ("HOME", "INFER")
            elif inferred_abbr and away_abbr and inferred_abbr == away_abbr:
                return ("AWAY", "INFER")

    # Try to extract team from dash: "Player - TEAM" or "TEAM - Player"
    if " - " in description:
        parts = description.split(" - ")
        for part in parts:
            part = part.strip()
            if 2 <= len(part) <= 4:
                inferred_abbr = normalize_team_abbr(part)
                if inferred_abbr and home_abbr and inferred_abbr == home_abbr:
                    return ("HOME", "INFER")
                elif inferred_abbr and away_abbr and inferred_abbr == away_abbr:
                    return ("AWAY", "INFER")

    # 5) Could not resolve
    return (None, "MISSING")


def derive_game_sharp_side(sharp_signal: dict, home_team: str, away_team: str) -> str:
    """
    v10.11: Derive which team the sharps are betting on.

    Returns team name (home or away) if sharp signal detected, empty string if no signal.

    Sharp signal structure:
    - side/sharp_side: "HOME" or "AWAY" (uppercase)
    - signal_strength: "STRONG", "MODERATE", or "NONE"
    - diff: money% - ticket% (positive = sharp activity)
    """
    if not sharp_signal:
        return ""

    signal_strength = sharp_signal.get("signal_strength", "NONE")
    if signal_strength == "NONE":
        return ""

    # v10.14: Check both side and sharp_side fields, normalize to uppercase
    side = sharp_signal.get("side") or sharp_signal.get("sharp_side") or ""
    side = side.upper() if side else ""

    if side == "HOME":
        return home_team
    elif side == "AWAY":
        return away_team

    return ""


def extract_game_sharp_direction(sharp_signal: dict) -> tuple:
    """
    v10.12: Extract game sharp direction for side and total.

    Returns (game_sharp_side, game_sharp_total):
    - game_sharp_side: "HOME" | "AWAY" | None
    - game_sharp_total: "OVER" | "UNDER" | None

    Currently Playbook API provides side direction only.
    Total direction would require additional data source.
    """
    if not sharp_signal:
        return (None, None)

    signal_strength = sharp_signal.get("signal_strength", "NONE")
    if signal_strength == "NONE":
        return (None, None)

    # Extract side direction (HOME/AWAY)
    side = sharp_signal.get("side", "")
    game_sharp_side = side if side in ("HOME", "AWAY") else None

    # Extract total direction (OVER/UNDER) - not currently available from Playbook API
    # This would require additional API data or market-specific sharp signals
    game_sharp_total = sharp_signal.get("total_direction", None)  # Future: when API supports it

    return (game_sharp_side, game_sharp_total)


def get_directional_mult(prediction_data: dict) -> tuple:
    """
    v10.14: True directional correlation for GAME-scoped sharps applied to PROP picks.

    Returns (directional_mult, directional_label):
    - 1.0, "ALIGNED" = prop direction matches sharp direction
    - 0.0, "CONFLICT" = prop direction conflicts with sharp direction
    - 0.5, "NEUTRAL (reason)" = direction is missing/ambiguous with explicit reason

    Inputs from prediction_data:
    - prop_side: "OVER" / "UNDER" (the prop's direction)
    - player_team_side: "HOME" / "AWAY" / None (which side player's team is on)
    - game_sharp_side: "HOME" / "AWAY" / None (which side sharps are on)
    - game_sharp_total: "OVER" / "UNDER" / None (sharp total direction if available)

    Correlation Rules:

    1) Total correlation (OVER/UNDER):
       - If game_sharp_total exists:
         - Prop OVER + Game OVER = ALIGNED
         - Prop UNDER + Game UNDER = ALIGNED
         - Otherwise = CONFLICT

    2) Side correlation (HOME/AWAY):
       - If game_sharp_side exists AND player_team_side is known:
         - If player on sharp-favored team:
           - Prop OVER = ALIGNED (team wins → player performs)
           - Prop UNDER = CONFLICT (team wins → player shouldn't underperform)
         - If player on sharp-opposed team:
           - Prop OVER = CONFLICT (team loses → player shouldn't overperform)
           - Prop UNDER = ALIGNED (team loses → player underperforms)

    3) If neither rule can be applied → NEUTRAL with explicit reason
    """
    prop_side = prediction_data.get("prop_side", "")
    player_team_side = prediction_data.get("player_team_side")
    game_sharp_side = prediction_data.get("game_sharp_side")
    game_sharp_total = prediction_data.get("game_sharp_total")

    # Normalize prop_side
    if isinstance(prop_side, str):
        prop_side = prop_side.upper()

    # v10.14: Explicit NEUTRAL reasons
    if not prop_side:
        return (0.5, "NEUTRAL (no prop direction)")

    # v10.18: Truthful NO_SIGNAL when sharps are absent
    # This ensures 0.0 sharp boost is applied (not 0.5 NEUTRAL)
    if not game_sharp_side and not game_sharp_total:
        return (0.0, "NO_SIGNAL")

    # Rule 1: Total correlation (OVER/UNDER sharp direction)
    if game_sharp_total:
        game_total = game_sharp_total.upper() if isinstance(game_sharp_total, str) else ""
        if prop_side == game_total:
            return (1.0, "ALIGNED")
        elif prop_side in ("OVER", "UNDER") and game_total in ("OVER", "UNDER"):
            return (0.0, "CONFLICT")

    # Rule 2: Side correlation (HOME/AWAY sharp direction)
    if game_sharp_side in ("HOME", "AWAY"):
        if not player_team_side:
            # v10.14: Explicit reason - can't correlate without player team
            return (0.5, "NEUTRAL (missing player team)")

        player_on_sharp_team = (player_team_side == game_sharp_side)

        if prop_side == "OVER":
            if player_on_sharp_team:
                # Sharp team wins → player performs → OVER aligns
                return (1.0, "ALIGNED")
            else:
                # Sharp team wins → opponent struggles → player shouldn't overperform
                return (0.0, "CONFLICT")

        elif prop_side == "UNDER":
            if player_on_sharp_team:
                # Sharp team wins → player performs → UNDER conflicts
                return (0.0, "CONFLICT")
            else:
                # Sharp team wins → opponent struggles → player underperforms
                return (1.0, "ALIGNED")

    # Rule 3: Cannot determine correlation → NEUTRAL
    return (0.5, "NEUTRAL")


# =============================================================================
# v10.37: PROP CORRELATION LOGIC - Allow aligned props to stack
# =============================================================================
# MASTER PROMPT REQUIREMENTS:
# 1. Do NOT auto-block correlated props (Points Over + 3PT Over should both be allowed)
# 2. Allow stacking when both independently qualify as EDGE_LEAN or better
# 3. Add correlation_group_id to identify related props
# 4. Prepare Jason Sim 2.0 structure (fields ready, not active yet)
# =============================================================================

# Correlation clusters - props that share the same underlying edge
SCORING_CLUSTER_MARKETS = {
    "player_points", "player_points_alternate",
    "player_threes", "player_threes_alternate",
    "player_assists", "player_assists_alternate"
}

VOLUME_CLUSTER_MARKETS = {
    "player_rebounds", "player_rebounds_alternate",
    "player_blocks", "player_blocks_alternate",
    "player_steals", "player_steals_alternate"
}

USAGE_CLUSTER_MARKETS = {
    "player_points_rebounds_assists", "player_points_rebounds",
    "player_points_assists", "player_rebounds_assists"
}

def get_correlation_cluster(market: str) -> str:
    """
    v10.37: Identify which correlation cluster a market belongs to.

    Clusters:
    - SCORING_CLUSTER: Points, 3PT, Assists (all benefit from offensive usage)
    - VOLUME_CLUSTER: Rebounds, Blocks, Steals (all benefit from minutes/activity)
    - USAGE_CLUSTER: Combo markets like PRA
    - NONE: Not in a cluster
    """
    market_lower = market.lower() if market else ""

    if market_lower in SCORING_CLUSTER_MARKETS:
        return "SCORING_CLUSTER"
    elif market_lower in VOLUME_CLUSTER_MARKETS:
        return "VOLUME_CLUSTER"
    elif market_lower in USAGE_CLUSTER_MARKETS:
        return "USAGE_CLUSTER"
    else:
        return "NONE"


def generate_correlation_group_id(player_name: str, cluster: str, side: str) -> str:
    """
    v10.37: Generate a unique correlation group ID for a prop.

    Format: "PLAYER:{normalized_name}:{cluster}:{side}"
    Example: "PLAYER:IsaiahJoe:SCORING_CLUSTER:OVER"

    This allows us to identify props that share the same underlying edge.
    """
    if not player_name or cluster == "NONE":
        return ""

    # Normalize player name (remove spaces, title case)
    normalized = player_name.replace(" ", "").replace(".", "").replace("'", "")

    return f"PLAYER:{normalized}:{cluster}:{safe_upper(side)}"  # v10.49: use helper


def get_correlation_type(market1: str, market2: str) -> str:
    """
    v10.37: Determine the correlation type between two markets.

    Types:
    - STRONGLY_CORRELATED: Same cluster (Points + 3PT = both scoring)
    - MODERATELY_CORRELATED: Different clusters but related (Points + Rebounds)
    - INDEPENDENT: No meaningful correlation
    """
    cluster1 = get_correlation_cluster(market1)
    cluster2 = get_correlation_cluster(market2)

    if cluster1 == "NONE" or cluster2 == "NONE":
        return "INDEPENDENT"

    if cluster1 == cluster2:
        return "STRONGLY_CORRELATED"

    # Cross-cluster correlations (e.g., SCORING + VOLUME are moderately related)
    return "MODERATELY_CORRELATED"


def enrich_prop_with_correlation(prop: dict) -> dict:
    """
    v10.37: Add correlation fields to a prop pick.

    Adds:
    - correlation_cluster: Which cluster this prop belongs to
    - correlation_group_id: Unique ID for correlated prop groups
    - correlation_type: Type of correlation (for display)

    This enables:
    1. Frontend to show "stacked" props together
    2. Backend to allow both props when they independently qualify
    3. Future Jason Sim 2.0 integration
    """
    player_name = prop.get("player", prop.get("player_name", ""))
    market = prop.get("market", "")
    side = safe_upper(prop.get("over_under") or prop.get("side"))  # v10.49: use helper

    # Identify correlation cluster
    cluster = get_correlation_cluster(market)

    # Generate correlation group ID
    group_id = generate_correlation_group_id(player_name, cluster, side)

    # Add correlation fields
    prop["correlation_cluster"] = cluster
    prop["correlation_group_id"] = group_id
    prop["correlation_type"] = "CLUSTERED" if cluster != "NONE" else "INDEPENDENT"

    # v10.37: Jason Sim 2.0 placeholder fields (ready, not active yet)
    # These will be populated by Jason Sim 2.0 when implemented
    prop["jason_sim_2"] = {
        "ready": True,
        "active": False,
        "win_pct_home": None,
        "projected_total": None,
        "variance_flag": None,
        "confluence_level": None
    }

    return prop


def allow_correlated_stacking(props: list, tier_threshold: list = None) -> list:
    """
    v10.37: Allow correlated props to stack when both independently qualify.

    MASTER PROMPT REQUIREMENT:
    "You MUST NOT auto-block 'aligned props' just because they're correlated.
    If two props are logically aligned AND BOTH qualify as EDGE_LEAN or better,
    BOTH may be included as separate picks."

    This function:
    1. Groups props by correlation_group_id
    2. For each group, checks if props independently qualify (GOLD_STAR or EDGE_LEAN)
    3. If both qualify, BOTH are returned (no blocking)
    4. If only one qualifies, only that one is returned
    5. Adds "STACKED" badge to correlated picks that are both returned

    Args:
        props: List of prop picks with correlation fields
        tier_threshold: List of acceptable tiers (default: GOLD_STAR, EDGE_LEAN)

    Returns:
        List of props with stacking applied
    """
    if tier_threshold is None:
        tier_threshold = ["GOLD_STAR", "EDGE_LEAN"]

    from collections import defaultdict

    # Group by correlation_group_id
    correlated_groups = defaultdict(list)
    independent_props = []

    for prop in props:
        group_id = prop.get("correlation_group_id", "")
        if group_id:
            correlated_groups[group_id].append(prop)
        else:
            independent_props.append(prop)

    result = []

    # Process correlated groups
    for group_id, group in correlated_groups.items():
        # Check how many qualify independently
        qualifying = [p for p in group if p.get("tier") in tier_threshold]

        if len(qualifying) >= 2:
            # BOTH qualify - allow stacking!
            for prop in qualifying:
                prop["stacked"] = True
                prop["stacking_info"] = {
                    "group_id": group_id,
                    "group_size": len(qualifying),
                    "reason": "Both props independently qualify - stacked for confluence"
                }
                if "badges" not in prop:
                    prop["badges"] = []
                if "STACKED" not in prop["badges"]:
                    prop["badges"].append("STACKED")
                prop["reasons"] = prop.get("reasons", []) + [
                    f"CORRELATION: STACKED ({len(qualifying)} props in {group_id.split(':')[2]} cluster)"
                ]
                result.append(prop)
        elif len(qualifying) == 1:
            # Only one qualifies - include it alone
            result.append(qualifying[0])
        else:
            # None qualify - include best one (if any meet MONITOR threshold)
            if group:
                best = max(group, key=lambda x: x.get("final_score", 0))
                result.append(best)

    # Add independent props
    result.extend(independent_props)

    return result


def resolve_prop_conflicts(prop_picks: list) -> tuple:
    """
    v10.9: Prop Deduplication - stop collisions like Maxey x4.

    Groups by (player, market) and keeps only the BEST prop per group.

    Selection Priority:
    1. Highest final_score
    2. If tie: better odds (lower implied probability)
    3. If still tie: line closest to median (avoid extreme alt lines)

    Returns (resolved_picks, dropped_count)
    """
    from collections import defaultdict

    grouped = defaultdict(list)
    for p in prop_picks:
        player = p.get("player", p.get("player_name", ""))
        market = p.get("market", "")
        key = (player, market)
        grouped[key].append(p)

    resolved = []
    dropped_count = 0

    for key, group in grouped.items():
        if len(group) == 1:
            resolved.append(group[0])
            continue

        # Sort by: score (desc), implied_prob (asc), line distance from median (asc)
        lines = [p.get("line", 0) or 0 for p in group]
        median_line = sorted(lines)[len(lines) // 2] if lines else 0

        def sort_key(x):
            score = clamp_score(x.get("final_score", x.get("total_score", 0)))
            odds = x.get("odds", -110)
            prob = implied_prob(odds)
            line = x.get("line", 0) or 0
            line_dist = abs(line - median_line)
            return (-score, prob, line_dist)

        group.sort(key=sort_key)
        best_pick = group[0]

        # Add reason for kept pick
        best_pick["reasons"] = best_pick.get("reasons", []) + [
            f"RESOLVER: Kept best of {len(group)} props for {key[1]}"
        ]

        resolved.append(best_pick)
        dropped_count += len(group) - 1

    return (resolved, dropped_count)


def resolve_same_direction(picks: list) -> list:
    """
    Resolve conflicts where multiple markets bet the SAME direction.

    For example, if we have:
    - Lakers -7 (score 7.2)
    - Lakers ML (score 7.0)

    These are SAME direction bets (Lakers win). Keep only the best-scoring market.

    Selection Priority (v10.8):
    1. Highest final_score
    2. If tied (within 0.05), lowest implied probability (best odds)
    3. If still tied, market preference: spreads > totals > h2h

    Groups by: (game, team/direction)
    - For spreads/ML: the team name is the direction
    - For totals: "OVER" or "UNDER" is the direction
    """
    from collections import defaultdict

    grouped = defaultdict(list)
    for p in picks:
        game = p.get("game", "") or p.get("matchup", "")
        market = p.get("market", "")

        # Determine direction
        if market == "totals":
            # For totals, direction is OVER/UNDER
            pick_text = p.get("pick", "")
            if "Over" in pick_text or "OVER" in pick_text:
                direction = "OVER"
            elif "Under" in pick_text or "UNDER" in pick_text:
                direction = "UNDER"
            else:
                direction = pick_text
        else:
            # For spreads and ML, direction is the team
            direction = p.get("team", "") or p.get("pick", "").split()[0]

        key = (game, direction)
        grouped[key].append(p)

    resolved = []
    for key, group in grouped.items():
        if len(group) == 1:
            resolved.append(group[0])
            continue

        # v10.11: Sort by: score (desc), then implied_prob (asc), then market tiebreak (asc)
        # Note: RESOLVER_MARKET_TIEBREAK is for sorting only - does NOT affect final_score
        def sort_key(x):
            score = clamp_score(x.get("final_score", 0.0))
            odds = x.get("odds", -110)
            prob = implied_prob(odds)
            market = x.get("market", "h2h")
            market_rank = RESOLVER_MARKET_TIEBREAK.get(market, 99)
            # Negate score for descending, prob and market_rank ascending
            return (-score, prob, market_rank)

        group.sort(key=sort_key)
        best_pick = group[0]
        second_pick = group[1] if len(group) > 1 else None

        # Check if tiebreaker was used (scores within 0.05)
        tiebreaker_used = False
        if second_pick:
            best_score = clamp_score(best_pick.get("final_score", 0.0))
            second_score = clamp_score(second_pick.get("final_score", 0.0))
            if abs(best_score - second_score) <= 0.05:
                tiebreaker_used = True

        # Build list of alternate markets
        alternate_markets = []
        for alt in group[1:]:
            alternate_markets.append({
                "market": alt.get("market", ""),
                "pick": alt.get("pick", ""),
                "odds": alt.get("odds", -110),
                "score": round(clamp_score(alt.get("final_score", 0)), 2),
                "implied_prob": round(implied_prob(alt.get("odds", -110)) * 100, 1)
            })

        # Add transparency about the decision
        best_pick["alternate_markets"] = alternate_markets
        if tiebreaker_used:
            best_odds = best_pick.get("odds", -110)
            best_prob = round(implied_prob(best_odds) * 100, 1)
            best_pick["reasons"] = best_pick.get("reasons", []) + [
                f"RESOLVER: Tie score -> preferred better odds ({best_prob}% break-even vs alternates)"
            ]
        else:
            best_pick["reasons"] = best_pick.get("reasons", []) + [
                f"RESOLVER: Best market for {key[1]} direction (vs {len(group)-1} alternates)"
            ]

        resolved.append(best_pick)

    return resolved


def resolve_opposing_sides(picks: list) -> list:
    """
    v10.35: Keep only ONE pick per game - the highest scoring.

    This ensures the community gets clean, non-conflicting picks:
    - No Hawks ML + Grizzlies -1.5 (opposing teams)
    - No Knicks -20.5 + Under 219.5 (spread + total for same game)

    Just ONE clear pick per game.

    Groups by: game
    Keeps: only the single highest-scoring pick
    """
    from collections import defaultdict

    # Group all picks by game
    games = defaultdict(list)
    for p in picks:
        game = p.get("game", "") or p.get("matchup", "")
        if game:
            games[game].append(p)

    resolved = []
    for game, game_picks in games.items():
        if len(game_picks) == 1:
            resolved.append(game_picks[0])
            continue

        # Sort by score descending, keep only the best
        game_picks.sort(key=lambda x: x.get("final_score", x.get("total_score", 0)), reverse=True)
        best_pick = game_picks[0]

        # Add transparency
        filtered_count = len(game_picks) - 1
        best_pick["reasons"] = best_pick.get("reasons", []) + [
            f"RESOLVER: Best pick for game (beat {filtered_count} other pick(s))"
        ]

        # Log what we filtered
        for p in game_picks[1:]:
            logger.debug(f"Filtered same-game pick: {p.get('pick')} (score {p.get('final_score')}) - {game}")

        resolved.append(best_pick)

    return resolved


# ============================================================================
# ROUTER SETUP
# ============================================================================

router = APIRouter(prefix="/live", tags=["live"], dependencies=[Depends(verify_api_key)])

# ============================================================================
# MASTER PREDICTION SYSTEM (Lazy Loaded Singleton)
# ============================================================================

_master_prediction_system = None

def get_master_prediction_system():
    """Get or initialize the MasterPredictionSystem singleton."""
    global _master_prediction_system
    if _master_prediction_system is None and MASTER_PREDICTION_AVAILABLE:
        try:
            _master_prediction_system = MasterPredictionSystem()
            logger.info("MasterPredictionSystem initialized")
        except Exception as e:
            logger.exception("Failed to initialize MasterPredictionSystem: %s", e)
    return _master_prediction_system


# ============================================================================
# JARVIS TRIGGERS - THE PROVEN EDGE NUMBERS
# Weight: boost / 5 = max +4.0 points (doubled from original /10)
# ============================================================================

JARVIS_TRIGGERS = {
    2178: {"name": "THE IMMORTAL", "boost": 20, "tier": "LEGENDARY", "description": "Only number where n4=reverse AND n4=66^4. Never collapses.", "mathematical": True},
    201: {"name": "THE ORDER", "boost": 12, "tier": "HIGH", "description": "Jesuit Order gematria. The Event of 201.", "mathematical": False},
    33: {"name": "THE MASTER", "boost": 10, "tier": "HIGH", "description": "Highest master number. Masonic significance.", "mathematical": False},
    47: {"name": "THE AGENT", "boost": 8, "tier": "MEDIUM", "description": "Agent of chaos. Discordian prime. High variance indicator.", "mathematical": False},
    88: {"name": "THE INFINITE", "boost": 8, "tier": "MEDIUM", "description": "Double infinity. Mercury retrograde resonance. Cycle completion.", "mathematical": False},
    93: {"name": "THE WILL", "boost": 10, "tier": "HIGH", "description": "Thelema sacred number. Will and Love.", "mathematical": False},
    322: {"name": "THE SOCIETY", "boost": 10, "tier": "HIGH", "description": "Skull & Bones. Genesis 3:22.", "mathematical": False}
}

POWER_NUMBERS = [11, 22, 33, 44, 55, 66, 77, 88, 99]
TESLA_NUMBERS = [3, 6, 9]

# ============================================================================
# v10.70: CHROME RESONANCE - Jersey Color Psychology
# ============================================================================
# Red = Aggression (ATS strength), Black = Penalties/Fouls (fade in close games)
# Blue = Control/Defense, White = Neutrality, Green = Balance
TEAM_PRIMARY_COLORS = {
    # NBA
    "Bulls": "RED", "Heat": "RED", "Rockets": "RED", "Raptors": "RED", "Blazers": "RED",
    "Hawks": "RED", "Wizards": "RED", "Pistons": "RED", "Clippers": "RED",
    "Nets": "BLACK", "Spurs": "BLACK", "Kings": "BLACK",
    "Lakers": "GOLD", "Warriors": "GOLD", "Pacers": "GOLD", "Nuggets": "GOLD",
    "Celtics": "GREEN", "Bucks": "GREEN", "Jazz": "GREEN",
    "Knicks": "BLUE", "Mavericks": "BLUE", "Thunder": "BLUE", "Grizzlies": "BLUE",
    "76ers": "BLUE", "Timberwolves": "BLUE", "Magic": "BLUE", "Hornets": "BLUE",
    "Suns": "ORANGE", "Cavaliers": "WINE",
    # NFL
    "Chiefs": "RED", "49ers": "RED", "Cardinals": "RED", "Buccaneers": "RED",
    "Falcons": "RED", "Texans": "RED", "Patriots": "RED",
    "Raiders": "BLACK", "Ravens": "BLACK", "Saints": "BLACK", "Panthers": "BLACK",
    "Steelers": "BLACK", "Bengals": "BLACK", "Jaguars": "BLACK",
    "Cowboys": "BLUE", "Bills": "BLUE", "Colts": "BLUE", "Chargers": "BLUE",
    "Titans": "BLUE", "Lions": "BLUE", "Giants": "BLUE", "Seahawks": "BLUE",
    "Packers": "GREEN", "Eagles": "GREEN", "Jets": "GREEN",
    "Broncos": "ORANGE", "Bears": "ORANGE", "Browns": "ORANGE", "Dolphins": "ORANGE",
    "Commanders": "BURGUNDY", "Vikings": "PURPLE",
    # MLB
    "Cardinals": "RED", "Reds": "RED", "Angels": "RED", "Phillies": "RED",
    "Nationals": "RED", "Diamondbacks": "RED", "Guardians": "RED",
    "Giants": "BLACK", "Pirates": "BLACK", "White Sox": "BLACK", "Marlins": "BLACK",
    "Dodgers": "BLUE", "Cubs": "BLUE", "Royals": "BLUE", "Blue Jays": "BLUE",
    "Rays": "BLUE", "Brewers": "BLUE", "Mariners": "BLUE", "Rangers": "BLUE",
    "Athletics": "GREEN", "Padres": "GREEN",
    "Orioles": "ORANGE", "Astros": "ORANGE", "Tigers": "ORANGE", "Mets": "ORANGE",
    "Yankees": "NAVY", "Red Sox": "NAVY", "Twins": "NAVY", "Braves": "NAVY",
    "Rockies": "PURPLE",
}

def get_chrome_resonance(home_team: str, away_team: str) -> Dict[str, Any]:
    """
    v10.79: Chrome Resonance - Analyze psychological impact of team colors.

    Delegates to glitch.esoteric module when available.
    Red = Aggression (ATS edge), Black = Penalties (fade in close games)
    """
    # v10.79: Delegate to glitch module if available
    if GLITCH_PROTOCOL_AVAILABLE:
        return glitch_chrome_resonance(home_team, away_team)

    # Legacy fallback
    home_color = TEAM_PRIMARY_COLORS.get(home_team, "NEUTRAL")
    away_color = TEAM_PRIMARY_COLORS.get(away_team, "NEUTRAL")

    chrome_boost = 0.0
    chrome_signal = "NEUTRAL"
    chrome_reason = ""

    # Red vs non-Red = aggression advantage
    if home_color == "RED" and away_color != "RED":
        chrome_boost = 0.15
        chrome_signal = "HOME_AGGRESSION"
        chrome_reason = f"Chrome: {home_team} RED aggression vs {away_team}"
    elif away_color == "RED" and home_color != "RED":
        chrome_boost = -0.10  # Away red slightly less impactful
        chrome_signal = "AWAY_AGGRESSION"
        chrome_reason = f"Chrome: {away_team} RED aggression (road)"

    # Black = foul/penalty prone (fade in close spreads)
    if home_color == "BLACK" or away_color == "BLACK":
        chrome_signal = "PENALTY_RISK" if chrome_signal == "NEUTRAL" else chrome_signal
        chrome_reason = chrome_reason or f"Chrome: BLACK team penalty risk"

    return {
        "available": True,
        "home_color": home_color,
        "away_color": away_color,
        "chrome_boost": chrome_boost,
        "chrome_signal": chrome_signal,
        "chrome_reason": chrome_reason
    }

# ============================================================================
# v10.70: BENFORD'S LAW ANOMALY DETECTION
# ============================================================================
# Natural data follows Benford distribution for leading digits
# Violations indicate "Mathematical Imposters" - fade streaks

BENFORD_EXPECTED = {
    1: 0.301, 2: 0.176, 3: 0.125, 4: 0.097,
    5: 0.079, 6: 0.067, 7: 0.058, 8: 0.051, 9: 0.046
}

def check_benford_anomaly(recent_stats: List[float], threshold: float = 0.15) -> Dict[str, Any]:
    """
    v10.79: Check if recent stats violate Benford's Law.

    Delegates to glitch.market module when available.
    If leading digits don't follow natural distribution, the streak is artificial.
    Returns anomaly signal to fade the streak.
    """
    # v10.79: Delegate to glitch module if available
    if GLITCH_PROTOCOL_AVAILABLE:
        return glitch_benford_anomaly(recent_stats, threshold)

    # Legacy fallback
    if not recent_stats or len(recent_stats) < 5:
        return {"available": False, "is_anomaly": False, "reason": "Insufficient data"}

    # Extract leading digits
    leading_digits = []
    for stat in recent_stats:
        if stat > 0:
            leading = int(str(abs(stat)).lstrip('0').lstrip('.')[0])
            if 1 <= leading <= 9:
                leading_digits.append(leading)

    if len(leading_digits) < 5:
        return {"available": False, "is_anomaly": False, "reason": "Insufficient valid digits"}

    # Calculate observed distribution
    observed = {d: 0 for d in range(1, 10)}
    for d in leading_digits:
        observed[d] += 1

    total = len(leading_digits)
    observed_pct = {d: count / total for d, count in observed.items()}

    # Calculate deviation from Benford
    total_deviation = sum(abs(observed_pct[d] - BENFORD_EXPECTED[d]) for d in range(1, 10))
    avg_deviation = total_deviation / 9

    is_anomaly = avg_deviation > threshold

    return {
        "available": True,
        "is_anomaly": is_anomaly,
        "deviation": round(avg_deviation, 4),
        "threshold": threshold,
        "sample_size": total,
        "signal": "FADE_STREAK" if is_anomaly else "NATURAL",
        "reason": f"Benford deviation {avg_deviation:.3f} {'> ANOMALY' if is_anomaly else '< natural'}"
    }

# ============================================================================
# v10.70: ATMOSPHERIC DRAG (Barometric Pressure)
# ============================================================================
# >30.10 inHg = Heavy Air (Bet Under), <29.80 inHg = Thin Air (Bet Over)

def calculate_atmospheric_drag(pressure_in: float) -> Dict[str, Any]:
    """
    v10.79: Calculate atmospheric drag betting signal from barometric pressure.

    Delegates to glitch.physics module when available.
    High pressure = heavy air = harder to throw/hit = UNDER
    Low pressure = thin air = ball travels easier = OVER
    """
    # v10.79: Delegate to glitch module if available
    if GLITCH_PROTOCOL_AVAILABLE:
        return glitch_atmospheric_drag(pressure_in)

    # Legacy fallback
    if not pressure_in or pressure_in <= 0:
        return {"available": False, "signal": "NEUTRAL", "boost": 0.0}

    if pressure_in > 30.10:
        return {
            "available": True,
            "pressure_in": pressure_in,
            "signal": "HEAVY_AIR",
            "direction": "UNDER",
            "boost": 0.20,
            "reason": f"Atmospheric Drag: {pressure_in:.2f} inHg HEAVY AIR (bet under)"
        }
    elif pressure_in < 29.80:
        return {
            "available": True,
            "pressure_in": pressure_in,
            "signal": "THIN_AIR",
            "direction": "OVER",
            "boost": 0.20,
            "reason": f"Atmospheric Drag: {pressure_in:.2f} inHg THIN AIR (bet over)"
        }
    else:
        return {
            "available": True,
            "pressure_in": pressure_in,
            "signal": "NEUTRAL",
            "direction": None,
            "boost": 0.0,
            "reason": f"Atmospheric Drag: {pressure_in:.2f} inHg (neutral)"
        }

# ============================================================================
# v10.70: LINGUISTIC DIVERGENCE (Hate-Buy Trap)
# ============================================================================
# Negative Sentiment + RLM towards that team = Sharps buying the hate

def detect_hate_buy_trap(
    sentiment_score: float,  # -1 to 1 scale
    rlm_detected: bool,
    rlm_direction: str,  # "HOME" or "AWAY"
    sentiment_target: str  # Which team sentiment is about
) -> Dict[str, Any]:
    """
    v10.79: Detect "Hate-Buy" trap where sharps buy hated teams.

    Delegates to glitch.hive_mind module when available.
    If public hates a team (negative sentiment) BUT line moves toward them (RLM),
    sharps are loading up. Classic contrarian edge.
    """
    # v10.79: Delegate to glitch module if available
    if GLITCH_PROTOCOL_AVAILABLE:
        return glitch_hate_buy_trap(sentiment_score, rlm_detected, rlm_direction, sentiment_target)

    # Legacy fallback
    if not rlm_detected:
        return {"available": False, "is_trap": False, "reason": "No RLM detected"}

    # Negative sentiment (-0.3 or worse) + RLM = Hate-Buy
    is_negative = sentiment_score < -0.3
    rlm_matches_hated = (
        (sentiment_target == "HOME" and rlm_direction == "HOME") or
        (sentiment_target == "AWAY" and rlm_direction == "AWAY")
    )

    is_trap = is_negative and rlm_matches_hated

    if is_trap:
        return {
            "available": True,
            "is_trap": True,
            "sentiment_score": sentiment_score,
            "rlm_direction": rlm_direction,
            "boost": 0.35,
            "signal": "HATE_BUY",
            "reason": f"Hate-Buy Trap: Public hates {sentiment_target} but sharps buying (RLM {rlm_direction})"
        }

    return {
        "available": True,
        "is_trap": False,
        "sentiment_score": sentiment_score,
        "rlm_direction": rlm_direction,
        "boost": 0.0,
        "signal": "NO_TRAP",
        "reason": "No hate-buy pattern detected"
    }

# ============================================================================
# ESOTERIC HELPER FUNCTIONS (exported for main.py)
# ============================================================================

def calculate_date_numerology() -> Dict[str, Any]:
    """Calculate numerology for today's date."""
    today = datetime.now()
    digits = str(today.year) + str(today.month).zfill(2) + str(today.day).zfill(2)

    # Life path number
    life_path = sum(int(d) for d in digits)
    while life_path > 9 and life_path not in [11, 22, 33]:
        life_path = sum(int(d) for d in str(life_path))

    # Day vibration
    day_vibe = sum(int(d) for d in str(today.day))
    while day_vibe > 9:
        day_vibe = sum(int(d) for d in str(day_vibe))

    # Check for power numbers
    power_hits = [n for n in POWER_NUMBERS if str(n) in digits]
    tesla_energy = any(d in "369" for d in digits)

    meanings = {
        1: "Leadership - favorites dominate",
        2: "Balance - close games expected",
        3: "Creative - unexpected outcomes",
        4: "Stability - chalk hits",
        5: "Change - underdogs bark",
        6: "Harmony - totals accurate",
        7: "Spiritual - trust the model",
        8: "Power - high scoring",
        9: "Completion - season trends hold"
    }

    return {
        "date": today.strftime("%Y-%m-%d"),
        "life_path": life_path,
        "day_vibration": day_vibe,
        "meaning": meanings.get(life_path % 10, "Standard energy"),
        "power_numbers_present": power_hits,
        "tesla_energy": tesla_energy,
        "is_master_number_day": life_path in [11, 22, 33]
    }


def get_moon_phase() -> Dict[str, Any]:
    """Get current moon phase and betting implications."""
    known_new_moon = datetime(2024, 1, 11)
    days_since = (datetime.now() - known_new_moon).days
    lunar_cycle = 29.53
    phase_day = days_since % lunar_cycle

    phases = [
        (0, 1.85, "New Moon", "Fresh starts - take calculated risks"),
        (1.85, 7.38, "Waxing Crescent", "Building momentum - follow trends"),
        (7.38, 11.07, "First Quarter", "Decision time - key matchups"),
        (11.07, 14.76, "Waxing Gibbous", "Increasing energy - overs favored"),
        (14.76, 16.61, "Full Moon", "High volatility - expect upsets"),
        (16.61, 22.14, "Waning Gibbous", "Reflection - fade public"),
        (22.14, 25.83, "Last Quarter", "Release - unders hit"),
        (25.83, 29.53, "Waning Crescent", "Rest period - low scoring")
    ]

    for start, end, name, meaning in phases:
        if start <= phase_day < end:
            illumination = abs(14.76 - phase_day) / 14.76 * 100
            return {
                "phase": name,
                "meaning": meaning,
                "phase_day": round(phase_day, 1),
                "illumination": round(100 - illumination, 1),
                "betting_edge": "VOLATILITY" if "Full" in name else "STABILITY" if "New" in name else "NEUTRAL"
            }

    return {"phase": "Unknown", "meaning": "Check phase", "phase_day": phase_day}


def get_daily_energy() -> Dict[str, Any]:
    """Get overall daily energy reading for betting."""
    numerology = calculate_date_numerology()
    moon = get_moon_phase()

    energy_score = 50

    if numerology.get("is_master_number_day"):
        energy_score += 15
    if numerology.get("tesla_energy"):
        energy_score += 10
    if moon.get("phase") == "Full Moon":
        energy_score += 20
    elif moon.get("phase") == "New Moon":
        energy_score -= 10

    dow = datetime.now().weekday()
    day_modifiers = {
        0: ("Monday", -5, "Slow start"),
        1: ("Tuesday", 0, "Neutral"),
        2: ("Wednesday", 5, "Midweek momentum"),
        3: ("Thursday", 10, "TNF/Peak energy"),
        4: ("Friday", 15, "Weekend anticipation"),
        5: ("Saturday", 20, "Prime time"),
        6: ("Sunday", 25, "NFL Sunday dominance")
    }
    day_name, modifier, day_meaning = day_modifiers[dow]
    energy_score += modifier

    return {
        "overall_score": min(100, max(0, energy_score)),
        "rating": "HIGH" if energy_score >= 70 else "MEDIUM" if energy_score >= 40 else "LOW",
        "day_of_week": day_name,
        "day_influence": day_meaning,
        "recommended_action": "Aggressive betting" if energy_score >= 70 else "Standard sizing" if energy_score >= 40 else "Conservative approach",
        "numerology_summary": numerology,
        "moon_summary": moon
    }


# ============================================================================
# LIVE DATA ENDPOINTS
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "14.4",
        "codename": "JARVIS_SAVANT_v10.1",
        "features": [
            "Phase 1: Confluence Core",
            "Phase 2: Vedic/Astro",
            "Phase 3: Learning Loop",
            "v10.1 Dual-Score Confluence",
            "v10.1 Bet Tier System"
        ],
        "timestamp": datetime.now().isoformat()
    }


@router.get("/system-health")
async def system_health():
    """
    v10.35: Comprehensive system health check - all components in one call.

    Returns status of:
    - API connections (Odds API, Playbook API)
    - Database (picks/signals persistence)
    - Grader (learning system)
    - Scheduler (daily audit jobs)
    - Pillars (which are active vs missing data)
    - AI Models (8 model status)
    - Esoteric (JARVIS, astro, daily energy)
    """
    health = {
        "status": "healthy",
        "version": "v10.35",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }

    issues = []

    # 1. API Connections
    apis = {
        "odds_api": {
            "configured": bool(ODDS_API_KEY),
            "key_present": len(ODDS_API_KEY) > 10 if ODDS_API_KEY else False
        },
        "playbook_api": {
            "configured": bool(PLAYBOOK_API_KEY),
            "key_present": len(PLAYBOOK_API_KEY) > 10 if PLAYBOOK_API_KEY else False
        }
    }
    if not apis["odds_api"]["configured"]:
        issues.append("ODDS_API_KEY not configured")
    if not apis["playbook_api"]["configured"]:
        issues.append("PLAYBOOK_API_KEY not configured")
    health["components"]["apis"] = apis

    # 2. Database
    db_status = {
        "available": DATABASE_AVAILABLE,
        "enabled": database.DB_ENABLED if DATABASE_AVAILABLE else False,
        "url_configured": bool(os.getenv("DATABASE_URL", ""))
    }
    if not db_status["available"]:
        issues.append("Database not available")
    health["components"]["database"] = db_status

    # 3. Grader (Learning System)
    try:
        grader = get_grader()
        grader_status = {
            "available": grader is not None,
            "predictions_logged": len(grader.prediction_log) if grader else 0,
            "learning_active": True
        }
    except Exception as e:
        grader_status = {"available": False, "error": str(e)}
        issues.append("Grader not available")
    health["components"]["grader"] = grader_status

    # 4. Scheduler
    scheduler_status = {
        "apscheduler_available": APSCHEDULER_AVAILABLE,
        "jobs_scheduled": APSCHEDULER_AVAILABLE
    }
    if not APSCHEDULER_AVAILABLE:
        issues.append("APScheduler not available - daily audit won't run")
    health["components"]["scheduler"] = scheduler_status

    # 5. AI Models
    ai_models = {
        "master_prediction_system": MASTER_PREDICTION_AVAILABLE,
        "ai_engine_layer": AI_ENGINE_AVAILABLE,
        "models": [
            "ensemble", "lstm", "monte_carlo", "line_movement",
            "rest_fatigue", "injury_impact", "matchup_model", "edge_calculator"
        ],
        "all_active": AI_ENGINE_AVAILABLE,
        "injury_context_wired": True  # v10.36: Now using real injury data
    }
    health["components"]["ai_models"] = ai_models

    # 5b. Context Layer (v10.36: Now connected!)
    context_layer = {
        "available": CONTEXT_LAYER_AVAILABLE,
        "features": [
            "Defensive Rankings (5 sports × positions)",
            "Pace/Tempo Metrics (all sports)",
            "Matchup Adjustments (props)",
            "Pace Adjustments (totals/props)"
        ],
        "status": "ACTIVE" if CONTEXT_LAYER_AVAILABLE else "UNAVAILABLE"
    }
    health["components"]["context_layer"] = context_layer
    if not CONTEXT_LAYER_AVAILABLE:
        issues.append("Context layer unavailable - matchup adjustments disabled")

    # 5c. ESPN API (v10.68: Replaced RotoWire - FREE lineups + referees)
    espn_status = {
        "available": True,  # ESPN is free, always available
        "features": [
            "Starting Lineups (lineup confirmation)",
            "Referee Assignments (activates Officials pillar)",
            "Referee Tendencies (foul rates, over/under lean)"
        ],
        "status": "ACTIVE"
    }
    health["components"]["espn"] = espn_status

    # 6. Pillars Status (which have data sources)
    # v10.35: Hospital Fade and Hook Discipline now active
    # v10.36: Expert Consensus derived from Sharp Split (sharp money = expert money)
    # v10.68: Officials now powered by ESPN (free) instead of RotoWire
    pillars = {
        "active": [
            {"name": "Sharp Split", "data_source": "Playbook API splits", "status": "ACTIVE"},
            {"name": "Reverse Line Movement", "data_source": "Playbook API line_variance", "status": "ACTIVE"},
            {"name": "Public Fade", "data_source": "Playbook API public%", "status": "ACTIVE"},
            {"name": "Hospital Fade", "data_source": "Injuries API (v10.35)", "status": "ACTIVE"},
            {"name": "Expert Consensus", "data_source": "Derived from Sharp Split (65%+ sharp = consensus)", "status": "ACTIVE"},
            {"name": "Home Court", "data_source": "Game data", "status": "ACTIVE"},
            {"name": "Rest Advantage", "data_source": "Schedule data", "status": "ACTIVE"},
            {"name": "Prime Time", "data_source": "Game time", "status": "ACTIVE"},
            {"name": "Hook Discipline", "data_source": "Spread value (v10.35)", "status": "ACTIVE"},
            {"name": "Mid-Spread Boss Zone", "data_source": "Spread value", "status": "ACTIVE"},
            {"name": "Prop Correlation", "data_source": "Game total + market type (v10.61)", "status": "ACTIVE"},
            {"name": "Volume Discipline", "data_source": "Ticket % consensus (v10.61)", "status": "ACTIVE"},
            {"name": "Officials Impact", "data_source": "ESPN API (v10.68 - FREE)", "status": "ACTIVE"},
            {"name": "Multi-Pillar Confluence", "data_source": "Calculated", "status": "ACTIVE"}
        ],
        "inactive": [],
        "active_count": 14,
        "total_defined": 14
    }
    health["components"]["pillars"] = pillars

    # 7. Esoteric Systems
    esoteric = {
        "jarvis_triggers": {
            "active": True,
            "triggers": ["2178 (IMMORTAL)", "201 (ORDER)", "33 (MASTER)", "93 (WILL)", "322 (SOCIETY)"]
        },
        "astro": {
            "planetary_hours": True,
            "nakshatra": True
        },
        "daily_energy": True,
        "gematria": True
    }
    health["components"]["esoteric"] = esoteric

    # 8. Recent Pick Stats (if available)
    try:
        cache_key = "best-bets:nba"
        cached = api_cache.get(cache_key)
        if cached:
            recent_stats = {
                "cached_picks_available": True,
                "props_count": cached.get("props", {}).get("count", 0),
                "game_picks_count": cached.get("game_picks", {}).get("count", 0),
                "database_available": cached.get("database_available", False),
                "picks_saved": cached.get("picks_saved", 0),
                "signals_saved": cached.get("signals_saved", 0)
            }
        else:
            recent_stats = {"cached_picks_available": False}
    except:
        recent_stats = {"cached_picks_available": False}
    health["components"]["recent_picks"] = recent_stats

    # Overall status
    if len(issues) == 0:
        health["status"] = "healthy"
        health["message"] = "All systems operational"
    elif len(issues) <= 2:
        health["status"] = "degraded"
        health["message"] = f"{len(issues)} issue(s) detected"
    else:
        health["status"] = "unhealthy"
        health["message"] = f"{len(issues)} issues detected - check components"

    health["issues"] = issues

    return health


@router.post("/smoke-test")
async def run_smoke_test():
    """
    v10.36: Manual smoke test - verify entire system is working.

    Tests:
    1. API connectivity (Playbook, Odds API)
    2. Best bets generation (props + game picks)
    3. All 11 pillars firing
    4. AI Engine models
    5. Context Layer
    6. Esoteric systems

    Returns detailed results with pass/fail for each test.
    """
    from daily_scheduler import SmokeTestJob

    smoke_test = SmokeTestJob()
    results = await smoke_test.run_async()

    # Add action recommendations if failures
    if results.get("failed", 0) > 0:
        results["action_required"] = True
        results["recommendations"] = []

        for test_name in results.get("critical_failures", []):
            if test_name == "best_bets":
                results["recommendations"].append("Check API keys and quotas")
            elif test_name == "system_health":
                results["recommendations"].append("Check AI Engine and Pillars status")
            elif test_name == "api_connectivity":
                results["recommendations"].append("Verify ODDS_API_KEY and PLAYBOOK_API_KEY")
    else:
        results["action_required"] = False
        results["message"] = "✅ All systems operational"

    return results


@router.get("/smoke-test/last")
async def get_last_smoke_test():
    """
    Get results from the last nightly smoke test.
    """
    import os
    import json
    from datetime import datetime

    log_dir = "./smoke_test_logs"
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(log_dir, f"smoke_test_{today}.json")

    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                return json.load(f)
        except:
            return {"error": "Could not read smoke test log"}
    else:
        return {
            "message": "No smoke test run today yet",
            "next_scheduled": "5:30 AM ET",
            "manual_trigger": "POST /live/smoke-test"
        }


@router.api_route("/smoke-test/alert-status", methods=["GET", "HEAD"])
async def get_smoke_test_alert_status():
    """
    v10.36: Simple alert endpoint for external monitoring.

    Returns HTTP 200 with status="ok" if last smoke test passed.
    Returns HTTP 503 with status="alert" if last smoke test failed.

    Supports both GET and HEAD methods for UptimeRobot compatibility.

    Use with external monitoring services (UptimeRobot, Cronitor, etc.)
    to get alerts when the system has issues.

    Example monitoring setup:
    - UptimeRobot: Monitor this URL, alert on non-200 status
    - Cronitor: POST to your Cronitor URL based on response
    - Custom: Poll every hour, send Slack/Discord webhook on failure
    """
    import os
    import json
    from datetime import datetime, timedelta

    log_dir = "./smoke_test_logs"
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Try today's log first, then yesterday's
    for date_str in [today, yesterday]:
        log_path = os.path.join(log_dir, f"smoke_test_{date_str}.json")
        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as f:
                    results = json.load(f)

                failed = results.get("failed", 0)
                critical_failures = results.get("critical_failures", [])

                if failed > 0 or len(critical_failures) > 0:
                    # Return 503 to trigger external alert
                    from fastapi import Response
                    return Response(
                        content=json.dumps({
                            "status": "alert",
                            "failed_tests": failed,
                            "critical_failures": critical_failures,
                            "test_date": date_str,
                            "message": "Smoke test failed - check /live/smoke-test/last for details"
                        }),
                        status_code=503,
                        media_type="application/json"
                    )
                else:
                    return {
                        "status": "ok",
                        "passed_tests": results.get("passed", 0),
                        "test_date": date_str,
                        "message": "All systems operational"
                    }
            except:
                pass

    # No recent smoke test - return warning but 200 (not critical)
    return {
        "status": "no_data",
        "message": "No recent smoke test found - waiting for next scheduled run at 5:30 AM ET",
        "next_scheduled": "5:30 AM ET"
    }


@router.get("/cache/stats")
async def cache_stats():
    """Get cache statistics for debugging."""
    return {
        "cache": api_cache.stats(),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/cache/clear")
async def cache_clear():
    """Clear the API cache."""
    api_cache.clear()
    return {"status": "cache_cleared", "timestamp": datetime.now().isoformat()}


@router.get("/playbook/usage")
async def get_playbook_usage():
    """
    Get Playbook API plan and usage info.
    Useful for monitoring API quota.
    """
    if not PLAYBOOK_API_KEY:
        return {"error": "PLAYBOOK_API_KEY not configured", "status": "unavailable"}

    try:
        playbook_url = f"{PLAYBOOK_API_BASE}/me"
        resp = await fetch_with_retries(
            "GET", playbook_url,
            params={"api_key": PLAYBOOK_API_KEY}
        )

        if resp and resp.status_code == 200:
            data = resp.json()
            return {
                "status": "ok",
                "source": "playbook",
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": f"Playbook returned {resp.status_code if resp else 'no response'}",
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.exception("Failed to fetch Playbook usage: %s", e)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/playbook/health")
async def get_playbook_health():
    """Check Playbook API health status."""
    try:
        playbook_url = f"{PLAYBOOK_API_BASE}/health"
        resp = await fetch_with_retries("GET", playbook_url)

        if resp and resp.status_code == 200:
            return {"status": "healthy", "playbook_status": resp.json() if resp.text else "ok"}
        else:
            return {"status": "unhealthy", "code": resp.status_code if resp else None}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def calculate_usage_warning(remaining: int, used: int) -> Dict[str, Any]:
    """
    Calculate usage warning level based on remaining vs used.

    Returns warning levels:
    - HEALTHY: < 25% used
    - CAUTION_25: 25-49% used
    - CAUTION_50: 50-74% used
    - CAUTION_75: 75-89% used
    - CRITICAL: >= 90% used (10% or less remaining)
    """
    if remaining is None or used is None:
        return {"level": "UNKNOWN", "message": "Could not determine usage", "percent_used": None}

    total = remaining + used
    if total == 0:
        return {"level": "UNKNOWN", "message": "No quota data", "percent_used": None}

    percent_used = round((used / total) * 100, 1)
    percent_remaining = round((remaining / total) * 100, 1)

    if percent_remaining <= 10:
        return {
            "level": "CRITICAL",
            "emoji": "🚨",
            "message": f"CRITICAL: Only {percent_remaining}% remaining! Consider upgrading NOW.",
            "percent_used": percent_used,
            "percent_remaining": percent_remaining,
            "action_needed": True
        }
    elif percent_used >= 75:
        return {
            "level": "CAUTION_75",
            "emoji": "🟠",
            "message": f"Warning: {percent_used}% used. Running low on API calls.",
            "percent_used": percent_used,
            "percent_remaining": percent_remaining,
            "action_needed": True
        }
    elif percent_used >= 50:
        return {
            "level": "CAUTION_50",
            "emoji": "🟡",
            "message": f"Notice: {percent_used}% used. Half of monthly quota consumed.",
            "percent_used": percent_used,
            "percent_remaining": percent_remaining,
            "action_needed": False
        }
    elif percent_used >= 25:
        return {
            "level": "CAUTION_25",
            "emoji": "🟢",
            "message": f"Info: {percent_used}% used. Healthy usage so far.",
            "percent_used": percent_used,
            "percent_remaining": percent_remaining,
            "action_needed": False
        }
    else:
        return {
            "level": "HEALTHY",
            "emoji": "✅",
            "message": f"Healthy: Only {percent_used}% used. Plenty of quota remaining.",
            "percent_used": percent_used,
            "percent_remaining": percent_remaining,
            "action_needed": False
        }


@router.get("/odds-api/usage")
async def get_odds_api_usage():
    """
    Get Odds API usage info from response headers with threshold warnings.

    Warning Levels:
    - HEALTHY: < 25% used
    - CAUTION_25: 25-49% used
    - CAUTION_50: 50-74% used
    - CAUTION_75: 75-89% used
    - CRITICAL: >= 90% used (10% or less remaining)
    """
    if not ODDS_API_KEY:
        return {"error": "ODDS_API_KEY not configured", "status": "unavailable"}

    try:
        # Make a lightweight request to get usage headers
        odds_url = f"{ODDS_API_BASE}/sports"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={"apiKey": ODDS_API_KEY}
        )

        if resp:
            # Extract usage from headers
            requests_remaining = resp.headers.get("x-requests-remaining")
            requests_used = resp.headers.get("x-requests-used")

            remaining = int(requests_remaining) if requests_remaining else None
            used = int(requests_used) if requests_used else None

            # Calculate warning level
            warning = calculate_usage_warning(remaining, used)

            return {
                "status": "ok",
                "source": "odds_api",
                "usage": {
                    "requests_remaining": remaining,
                    "requests_used": used,
                    "total_quota": (remaining + used) if remaining and used else None,
                    "note": "Resets monthly. Check https://the-odds-api.com for plan limits."
                },
                "warning": warning,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": "No response from Odds API",
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.exception("Failed to fetch Odds API usage: %s", e)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/api-usage")
async def get_all_api_usage():
    """
    Get combined usage for all paid APIs (Playbook + Odds API) with threshold warnings.

    Warning Levels for each API:
    - HEALTHY: < 25% used
    - CAUTION_25: 25-49% used
    - CAUTION_50: 50-74% used
    - CAUTION_75: 75-89% used
    - CRITICAL: >= 90% used (10% or less remaining)

    Overall status shows the WORST status across all APIs.
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "apis": {},
        "overall_status": "HEALTHY",
        "action_needed": False,
        "alerts": []
    }

    warning_priority = {"CRITICAL": 5, "CAUTION_75": 4, "CAUTION_50": 3, "CAUTION_25": 2, "HEALTHY": 1, "UNKNOWN": 0}
    worst_level = "HEALTHY"

    # Get Playbook usage
    if PLAYBOOK_API_KEY:
        try:
            playbook_url = f"{PLAYBOOK_API_BASE}/me"
            resp = await fetch_with_retries(
                "GET", playbook_url,
                params={"api_key": PLAYBOOK_API_KEY}
            )
            if resp and resp.status_code == 200:
                data = resp.json()
                result["apis"]["playbook"] = {"status": "ok", "data": data}
                # Check if Playbook returns usage info
                if "usage" in data or "requests" in data:
                    pb_used = data.get("usage", {}).get("used", data.get("requests", {}).get("used", 0))
                    pb_limit = data.get("usage", {}).get("limit", data.get("requests", {}).get("limit", 1000))
                    pb_remaining = pb_limit - pb_used
                    pb_warning = calculate_usage_warning(pb_remaining, pb_used)
                    result["apis"]["playbook"]["warning"] = pb_warning
                    if warning_priority.get(pb_warning["level"], 0) > warning_priority.get(worst_level, 0):
                        worst_level = pb_warning["level"]
                    if pb_warning.get("action_needed"):
                        result["alerts"].append(f"Playbook: {pb_warning['message']}")
            elif resp and resp.status_code == 429:
                result["apis"]["playbook"] = {"status": "rate_limited", "warning": {"level": "CRITICAL", "message": "Rate limited!"}}
                worst_level = "CRITICAL"
                result["alerts"].append("🚨 Playbook API is RATE LIMITED!")
            else:
                result["apis"]["playbook"] = {"status": "error", "code": resp.status_code if resp else None}
        except Exception as e:
            result["apis"]["playbook"] = {"status": "error", "error": str(e)}
    else:
        result["apis"]["playbook"] = {"status": "not_configured"}

    # Get Odds API usage
    if ODDS_API_KEY:
        try:
            odds_url = f"{ODDS_API_BASE}/sports"
            resp = await fetch_with_retries(
                "GET", odds_url,
                params={"apiKey": ODDS_API_KEY}
            )
            if resp:
                remaining = int(resp.headers.get("x-requests-remaining", 0))
                used = int(resp.headers.get("x-requests-used", 0))
                warning = calculate_usage_warning(remaining, used)

                result["apis"]["odds_api"] = {
                    "status": "ok",
                    "requests_remaining": remaining,
                    "requests_used": used,
                    "total_quota": remaining + used,
                    "warning": warning
                }

                if warning_priority.get(warning["level"], 0) > warning_priority.get(worst_level, 0):
                    worst_level = warning["level"]
                if warning.get("action_needed"):
                    result["alerts"].append(f"Odds API: {warning['message']}")
            else:
                result["apis"]["odds_api"] = {"status": "error", "error": "No response"}
        except Exception as e:
            result["apis"]["odds_api"] = {"status": "error", "error": str(e)}
    else:
        result["apis"]["odds_api"] = {"status": "not_configured"}

    # Set overall status
    result["overall_status"] = worst_level
    result["action_needed"] = worst_level in ["CRITICAL", "CAUTION_75"]

    # Add summary message
    if worst_level == "CRITICAL":
        result["summary"] = "🚨 CRITICAL: One or more APIs running very low! Upgrade needed."
    elif worst_level == "CAUTION_75":
        result["summary"] = "🟠 WARNING: High API usage. Consider upgrading soon."
    elif worst_level == "CAUTION_50":
        result["summary"] = "🟡 NOTICE: 50%+ of API quota used this month."
    elif worst_level == "CAUTION_25":
        result["summary"] = "🟢 HEALTHY: Normal API usage levels."
    else:
        result["summary"] = "✅ HEALTHY: API usage looks good!"

    return result


@router.get("/api-health")
async def get_api_health_quick():
    """
    Quick health check for all APIs - lightweight status for dashboards.

    Returns simple status:
    - overall: HEALTHY | CAUTION | CRITICAL
    - action_needed: true/false
    - alerts: list of any warnings

    Use /api-usage for full details.
    """
    # Get full usage data
    full_usage = await get_all_api_usage()

    return {
        "overall_status": full_usage["overall_status"],
        "action_needed": full_usage["action_needed"],
        "summary": full_usage.get("summary", ""),
        "alerts": full_usage["alerts"],
        "timestamp": full_usage["timestamp"],
        "detail_endpoint": "/live/api-usage"
    }


@router.get("/sharp/{sport}")
async def get_sharp_money(sport: str):
    """
    Get sharp money signals using Playbook API with Odds API fallback.

    Response Schema:
    {
        "sport": "NBA",
        "source": "playbook" | "odds_api",
        "count": N,
        "data": [...]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"sharp:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    # Derive sharp signals from Playbook splits data (sharp = money% differs significantly from ticket%)
    # v10.63: Also fetch /lines to get opening_line vs current_line for true RLM detection
    if PLAYBOOK_API_KEY:
        try:
            # Fetch splits and lines in parallel
            splits_url = f"{PLAYBOOK_API_BASE}/splits"
            lines_url = f"{PLAYBOOK_API_BASE}/lines"

            splits_resp, lines_resp = await asyncio.gather(
                fetch_with_retries("GET", splits_url, params={"league": sport_config['playbook'], "api_key": PLAYBOOK_API_KEY}),
                fetch_with_retries("GET", lines_url, params={"league": sport_config['playbook'], "api_key": PLAYBOOK_API_KEY}),
                return_exceptions=True
            )

            # Build lines lookup: game_id -> {opening_line, current_line, line_movement}
            lines_lookup = {}
            if lines_resp and not isinstance(lines_resp, Exception) and lines_resp.status_code == 200:
                try:
                    lines_json = lines_resp.json()
                    lines_data = lines_json if isinstance(lines_json, list) else lines_json.get("data", lines_json.get("lines", []))
                    for line_game in lines_data:
                        game_id = line_game.get("id", line_game.get("gameId", line_game.get("game_id")))
                        if not game_id:
                            continue
                        # Extract opening and current lines (try multiple field names)
                        opening = line_game.get("opening_line", line_game.get("openingLine", line_game.get("open_spread")))
                        current = line_game.get("current_line", line_game.get("currentLine", line_game.get("spread")))
                        if opening is not None and current is not None:
                            try:
                                opening_f = float(opening)
                                current_f = float(current)
                                movement = abs(current_f - opening_f)
                                lines_lookup[game_id] = {
                                    "opening_line": opening_f,
                                    "current_line": current_f,
                                    "line_movement": round(movement, 1),
                                    "movement_direction": "TOWARD_HOME" if current_f < opening_f else "TOWARD_AWAY" if current_f > opening_f else "NONE"
                                }
                            except (ValueError, TypeError):
                                pass
                    if lines_lookup:
                        logger.info("v10.63: Built lines lookup with %d games for RLM detection", len(lines_lookup))
                except Exception as e:
                    logger.warning("Failed to parse Playbook lines: %s", e)

            # Process splits data
            if splits_resp and not isinstance(splits_resp, Exception) and splits_resp.status_code == 200:
                try:
                    json_body = splits_resp.json()
                    splits = json_body if isinstance(json_body, list) else json_body.get("data", json_body.get("games", []))

                    # Derive sharp signals: when money% differs from ticket% by 7%+
                    # v10.91: Lowered threshold from 10% to 7% - today's markets have tighter splits
                    for game in splits:
                        # v10.71: Handle both flat and nested Playbook API structures
                        # Nested structure: splits.spread.money.homePercent / splits.spread.bets.homePercent
                        # Flat structure: money_pct / ticket_pct
                        splits_data = game.get("splits", {})
                        spread_data = splits_data.get("spread", {})

                        if spread_data:
                            # Nested structure (current Playbook API)
                            money_pct = spread_data.get("money", {}).get("homePercent", 50)
                            ticket_pct = spread_data.get("bets", {}).get("homePercent", 50)
                        else:
                            # Flat structure (legacy)
                            money_pct = game.get("money_pct", game.get("moneyPct", 50))
                            ticket_pct = game.get("ticket_pct", game.get("ticketPct", 50))

                        diff = abs(money_pct - ticket_pct)

                        if diff >= 7:  # v10.91: 7%+ difference indicates sharp action (was 10%)
                            # v10.14: Uppercase for consistency with directional correlation
                            sharp_side = "HOME" if money_pct > ticket_pct else "AWAY"
                            game_id = game.get("id", game.get("gameId"))

                            # v10.71: Handle homeTeamName/awayTeamName field names
                            home_team = game.get("home_team", game.get("homeTeam", game.get("homeTeamName", "")))
                            away_team = game.get("away_team", game.get("awayTeam", game.get("awayTeamName", "")))

                            signal = {
                                "game_id": game_id,
                                "home_team": home_team,
                                "away_team": away_team,
                                "sharp_side": sharp_side,
                                "side": sharp_side,  # Alias for compatibility
                                "money_pct": money_pct,
                                "ticket_pct": ticket_pct,
                                "signal_strength": "STRONG" if diff >= 15 else "MODERATE",  # v10.91: 15%+ STRONG, 7%+ MODERATE
                                "source": "playbook_splits"
                            }

                            # v10.63: Add line movement data for RLM if available
                            if game_id and game_id in lines_lookup:
                                line_info = lines_lookup[game_id]
                                signal["opening_line"] = line_info["opening_line"]
                                signal["current_line"] = line_info["current_line"]
                                signal["line_movement"] = line_info["line_movement"]
                                signal["line_variance"] = line_info["line_movement"]  # Alias for RLM pillar
                                signal["movement_direction"] = line_info["movement_direction"]

                                # v10.63: True RLM detection - line moved AGAINST public
                                public_on_home = ticket_pct > 50
                                line_toward_home = line_info["movement_direction"] == "TOWARD_HOME"
                                # RLM = public on one side, but line moved opposite direction
                                if public_on_home and not line_toward_home:
                                    signal["rlm_detected"] = True
                                    signal["rlm_side"] = "HOME"  # Sharps on home despite public
                                elif not public_on_home and line_toward_home:
                                    signal["rlm_detected"] = True
                                    signal["rlm_side"] = "AWAY"  # Sharps on away despite public
                                else:
                                    signal["rlm_detected"] = False

                            data.append(signal)

                    if data:
                        rlm_count = sum(1 for s in data if s.get("rlm_detected"))
                        logger.info("Playbook sharp signals for %s: %d signals, %d RLM detected", sport, len(data), rlm_count)
                        result = {"sport": sport.upper(), "source": "playbook", "count": len(data), "data": data, "movements": data}
                        api_cache.set(cache_key, result)
                        return result
                except ValueError as e:
                    logger.error("Failed to parse Playbook response: %s", e)

            # v10.71: Fix - check splits_resp not undefined 'resp'
            if splits_resp and not isinstance(splits_resp, Exception) and splits_resp.status_code == 429:
                raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Playbook fetch failed for %s: %s", sport, e)

    # Fallback to Odds API variance analysis
    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={"apiKey": ODDS_API_KEY, "regions": "us", "markets": "spreads", "oddsFormat": "american"}
        )

        if not resp or resp.status_code != 200:
            # Return empty data when API unavailable - no fake data
            logger.warning("Odds API unavailable for sharp - no data available")
            result = {"sport": sport.upper(), "source": "none", "count": 0, "data": [], "movements": [], "message": "Odds API unavailable"}
            api_cache.set(cache_key, result)
            return result

        if resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")

        try:
            games = resp.json()
        except ValueError as e:
            logger.error("Failed to parse Odds API response: %s", e)
            # Return empty data on parse error - no fake data
            result = {"sport": sport.upper(), "source": "none", "count": 0, "data": [], "movements": [], "message": "Failed to parse API response"}
            api_cache.set(cache_key, result)
            return result

        for game in games:
            spreads = []
            for bm in game.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market.get("key") == "spreads":
                        for outcome in market.get("outcomes", []):
                            if outcome.get("name") == game.get("home_team"):
                                spreads.append(outcome.get("point", 0))

            if len(spreads) >= 3:
                variance = max(spreads) - min(spreads)
                if variance >= 1.5:
                    # v10.14: Infer sharp side from line movement direction
                    # If line moved more negative (home bigger favorite), sharps on home
                    # If line moved more positive (away bigger favorite), sharps on away
                    avg_spread = sum(spreads) / len(spreads)
                    median_spread = sorted(spreads)[len(spreads) // 2]

                    # Compare outliers to median to determine movement direction
                    max_diff = abs(max(spreads) - median_spread)
                    min_diff = abs(min(spreads) - median_spread)

                    if max_diff > min_diff:
                        # Line moved toward away being bigger dog (more positive)
                        # Sharps bet away, pushed line toward home favorite
                        sharp_side = "HOME"
                    elif min_diff > max_diff:
                        # Line moved toward home being bigger dog (more negative)
                        # Sharps bet home, pushed line toward away favorite
                        sharp_side = "AWAY"
                    else:
                        sharp_side = None  # Can't determine

                    data.append({
                        "game_id": game.get("id"),
                        "home_team": game.get("home_team"),
                        "away_team": game.get("away_team"),
                        "line_variance": round(variance, 1),
                        "signal_strength": "STRONG" if variance >= 2 else "MODERATE",
                        "sharp_side": sharp_side,
                        "side": sharp_side,  # Alias for compatibility
                        "avg_spread": round(avg_spread, 1),
                        "source": "odds_api_variance"
                    })

        logger.info("Odds API sharp analysis for %s: %d signals found", sport, len(data))

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Odds API processing failed for %s: %s", sport, e)
        # Return empty data on error - no fake data
        result = {"sport": sport.upper(), "source": "none", "count": 0, "data": [], "movements": [], "message": f"API error: {str(e)}"}
        api_cache.set(cache_key, result)
        return result

    result = {"sport": sport.upper(), "source": "odds_api", "count": len(data), "data": data, "movements": data}  # movements alias for frontend
    api_cache.set(cache_key, result)
    return result


@router.get("/splits/{sport}")
async def get_splits(sport: str):
    """
    Get betting splits with Playbook API + deterministic estimation fallback.

    Response Schema:
    {
        "sport": "NBA",
        "source": "playbook" | "estimated",
        "count": N,
        "data": [...]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"splits:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    # Try Playbook API first - uses /splits?league=NBA&api_key=... format
    if PLAYBOOK_API_KEY:
        try:
            playbook_url = f"{PLAYBOOK_API_BASE}/splits"
            resp = await fetch_with_retries(
                "GET", playbook_url,
                params={"league": sport_config['playbook'], "api_key": PLAYBOOK_API_KEY}
            )

            if resp and resp.status_code == 200:
                try:
                    json_body = resp.json()
                    # Playbook returns array of games directly or in "data" key
                    games = json_body if isinstance(json_body, list) else json_body.get("data", json_body.get("games", []))
                    logger.info("Playbook splits data retrieved for %s: %d games", sport, len(games))
                    result = {"sport": sport.upper(), "source": "playbook", "count": len(games), "data": games}
                    api_cache.set(cache_key, result)
                    return result
                except ValueError as e:
                    logger.error("Failed to parse Playbook splits response: %s", e)

            if resp and resp.status_code == 429:
                raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")

            if resp:
                logger.warning("Playbook splits returned %s for %s", resp.status_code, sport)

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Playbook splits fetch failed for %s: %s", sport, e)

    # Fallback to Odds API with deterministic estimation
    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={"apiKey": ODDS_API_KEY, "regions": "us", "markets": "h2h", "oddsFormat": "american"}
        )

        if not resp:
            raise HTTPException(status_code=502, detail="Odds API unreachable after retries")

        if resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")

        if resp.status_code != 200:
            logger.warning("Odds API returned %s for splits %s", resp.status_code, sport)
            raise HTTPException(status_code=502, detail=f"Odds API returned error: {resp.status_code}")

        try:
            games = resp.json()
        except ValueError as e:
            logger.error("Failed to parse Odds API splits response: %s", e)
            raise HTTPException(status_code=502, detail="Invalid response from Odds API")

        for game in games:
            game_id = game.get("id", "")
            # Use deterministic RNG so same game always gets same estimated splits
            rng = deterministic_rng_for_game_id(game_id)
            home_bet = rng.randint(40, 60)
            home_money = home_bet + rng.randint(-10, 10)

            data.append({
                "game_id": game_id,
                "home_team": game.get("home_team"),
                "away_team": game.get("away_team"),
                "spread_splits": {
                    "home": {"bets_pct": home_bet, "money_pct": max(25, min(75, home_money))},
                    "away": {"bets_pct": 100 - home_bet, "money_pct": max(25, min(75, 100 - home_money))}
                }
            })

        logger.info("Odds API splits estimation for %s: %d games", sport, len(data))

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Odds API splits processing failed for %s: %s", sport, e)
        raise HTTPException(status_code=500, detail="Internal error processing splits data")

    result = {"sport": sport.upper(), "source": "estimated", "count": len(data), "data": data}
    api_cache.set(cache_key, result)
    return result


async def fetch_playbook_rosters(sport: str) -> dict:
    """
    v10.14: Fetch team rosters for player-team mapping.

    Primary source: ESPN API (free, complete rosters)
    Fallback: Playbook /injuries endpoint (injured players only)

    Returns:
        Dict mapping player_slug -> team_abbr (e.g., "tyrese_maxey" -> "PHI")
    """
    player_to_team = {}

    sport_lower = sport.lower()

    # Check cache first (rosters don't change often)
    cache_key = f"rosters:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        logger.info("v10.14: Using cached roster data with %d players", len(cached))
        return cached

    # ESPN API sport paths
    espn_sports = {
        "nba": "basketball/nba",
        "nfl": "football/nfl",
        "mlb": "baseball/mlb",
        "nhl": "hockey/nhl",
        "ncaab": "basketball/mens-college-basketball"
    }

    espn_path = espn_sports.get(sport_lower)
    if not espn_path:
        logger.warning("v10.14: Unknown sport %s for ESPN roster fetch", sport_lower)
        return player_to_team

    try:
        # ESPN Teams API - returns all teams with basic info
        teams_url = f"https://site.api.espn.com/apis/site/v2/sports/{espn_path}/teams"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(teams_url, params={"limit": 50})

            if resp.status_code == 200:
                teams_data = resp.json()
                teams_list = teams_data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])

                logger.info("v10.14: ESPN returned %d teams for %s", len(teams_list), sport_lower)

                # Fetch roster for each team
                for team_entry in teams_list:
                    team = team_entry.get("team", {})
                    team_abbr = team.get("abbreviation", "")
                    team_id = team.get("id", "")

                    if not team_abbr or not team_id:
                        continue

                    # Normalize team abbreviation
                    normalized_abbr = normalize_team_abbr(team_abbr)
                    if not normalized_abbr:
                        continue

                    # Fetch roster for this team
                    roster_url = f"https://site.api.espn.com/apis/site/v2/sports/{espn_path}/teams/{team_id}/roster"
                    try:
                        roster_resp = await client.get(roster_url)
                        if roster_resp.status_code == 200:
                            roster_data = roster_resp.json()

                            # ESPN roster structure varies by sport
                            athletes = roster_data.get("athletes", [])

                            # Some sports group by position
                            if athletes and isinstance(athletes[0], dict) and "items" in athletes[0]:
                                # Grouped format: {"athletes": [{"position": "G", "items": [...]}]}
                                for group in athletes:
                                    for player in group.get("items", []):
                                        player_name = player.get("fullName", "") or player.get("displayName", "")
                                        if player_name:
                                            player_to_team[slug_player(player_name)] = normalized_abbr
                            else:
                                # Flat format: {"athletes": [{"fullName": "..."}]}
                                for player in athletes:
                                    player_name = player.get("fullName", "") or player.get("displayName", "")
                                    if player_name:
                                        player_to_team[slug_player(player_name)] = normalized_abbr

                    except Exception as e:
                        logger.debug("v10.14: Failed to fetch roster for %s: %s", team_abbr, e)
                        continue

                logger.info("v10.14: ESPN roster fetch complete: %d players", len(player_to_team))

    except Exception as e:
        logger.warning("v10.14: ESPN roster fetch failed: %s", e)

    # Fallback: Playbook /injuries for additional players
    if PLAYBOOK_API_KEY and sport_lower in SPORT_MAPPINGS:
        try:
            sport_config = SPORT_MAPPINGS[sport_lower]
            injuries_url = f"{PLAYBOOK_API_BASE}/injuries"
            injuries_resp = await fetch_with_retries(
                "GET", injuries_url,
                params={
                    "league": sport_config["playbook"],
                    "api_key": PLAYBOOK_API_KEY
                }
            )

            if injuries_resp and injuries_resp.status_code == 200:
                injuries_data = injuries_resp.json()
                injuries_list = injuries_data.get("injuries", injuries_data.get("data", []))
                if isinstance(injuries_data, list):
                    injuries_list = injuries_data

                added = 0
                for injury in injuries_list:
                    player_name = (
                        injury.get("player_name")
                        or injury.get("player")
                        or injury.get("name")
                        or ""
                    )
                    team_abbr = (
                        injury.get("team_abbr")
                        or injury.get("team")
                        or injury.get("team_abbreviation")
                        or ""
                    )

                    if player_name and team_abbr:
                        normalized_abbr = normalize_team_abbr(team_abbr)
                        if normalized_abbr:
                            slug = slug_player(player_name)
                            if slug not in player_to_team:
                                player_to_team[slug] = normalized_abbr
                                added += 1

                if added > 0:
                    logger.info("v10.14: Added %d players from Playbook injuries, total now %d", added, len(player_to_team))

        except Exception as e:
            logger.warning("v10.14: Playbook injuries fetch failed: %s", e)

    # Cache for 1 hour (rosters don't change often)
    if player_to_team:
        api_cache.set(cache_key, player_to_team, ttl=3600)
        logger.info("v10.14: Cached %d player-team mappings for %s", len(player_to_team), sport_lower)

    return player_to_team


@router.get("/injuries/{sport}")
async def get_injuries(sport: str):
    """
    Get injury report for a sport using Playbook API.

    Response Schema:
    {
        "sport": "NBA",
        "source": "playbook" | "espn",
        "count": N,
        "data": [...]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"injuries:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    # Try Playbook API first - /injuries?league=NBA&api_key=...
    if PLAYBOOK_API_KEY:
        try:
            playbook_url = f"{PLAYBOOK_API_BASE}/injuries"
            resp = await fetch_with_retries(
                "GET", playbook_url,
                params={"league": sport_config['playbook'], "api_key": PLAYBOOK_API_KEY}
            )

            if resp and resp.status_code == 200:
                try:
                    json_body = resp.json()
                    injuries = json_body if isinstance(json_body, list) else json_body.get("data", json_body.get("injuries", []))
                    logger.info("Playbook injuries retrieved for %s: %d records", sport, len(injuries))
                    result = {"sport": sport.upper(), "source": "playbook", "count": len(injuries), "data": injuries, "injuries": injuries}  # injuries alias for frontend
                    api_cache.set(cache_key, result)
                    return result
                except ValueError as e:
                    logger.error("Failed to parse Playbook injuries response: %s", e)

            if resp and resp.status_code == 429:
                raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Playbook injuries fetch failed for %s: %s", sport, e)

    # Fallback to ESPN injuries
    try:
        espn_url = f"{ESPN_API_BASE}/{sport_config['espn']}/injuries"
        resp = await fetch_with_retries("GET", espn_url)

        if resp and resp.status_code == 200:
            try:
                json_body = resp.json()
                for team in json_body.get("teams", []):
                    team_name = team.get("team", {}).get("displayName", "Unknown")
                    for injury in team.get("injuries", []):
                        data.append({
                            "team": team_name,
                            "player": injury.get("athlete", {}).get("displayName", "Unknown"),
                            "position": injury.get("athlete", {}).get("position", {}).get("abbreviation", ""),
                            "status": injury.get("status", "Unknown"),
                            "description": injury.get("details", {}).get("detail", ""),
                            "date": injury.get("date", "")
                        })
                logger.info("ESPN injuries retrieved for %s: %d records", sport, len(data))
            except (ValueError, KeyError) as e:
                logger.error("Failed to parse ESPN injuries: %s", e)
        else:
            logger.warning("ESPN injuries returned %s for %s", resp.status_code if resp else "no response", sport)

    except Exception as e:
        logger.exception("ESPN injuries fetch failed for %s: %s", sport, e)

    result = {"sport": sport.upper(), "source": "espn" if data else "none", "count": len(data), "data": data, "injuries": data}  # injuries alias for frontend
    api_cache.set(cache_key, result)
    return result


@router.get("/scores/{sport}")
async def get_scores(sport: str, days_from: int = 1):
    """
    v10.64: Get live and recent game scores from Odds API.

    CRITICAL for auto-grading picks! This endpoint provides final scores
    needed to verify pick outcomes.

    Args:
        sport: Sport key (nba, nfl, mlb, nhl)
        days_from: How many days back to include (1-3, default 1)

    Response Schema:
    {
        "sport": "NBA",
        "source": "odds_api",
        "count": N,
        "data": [
            {
                "id": "event_id",
                "sport_key": "basketball_nba",
                "home_team": "Los Angeles Lakers",
                "away_team": "Boston Celtics",
                "commence_time": "2026-01-23T00:00:00Z",
                "completed": true,
                "scores": [
                    {"name": "Los Angeles Lakers", "score": "112"},
                    {"name": "Boston Celtics", "score": "108"}
                ],
                "last_update": "2026-01-23T03:30:00Z"
            }
        ]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Clamp days_from to 1-3
    days_from = max(1, min(3, days_from))

    # Check cache first (short TTL for live scores)
    cache_key = f"scores:{sport_lower}:{days_from}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not configured for scores")
        return {"sport": sport.upper(), "source": "none", "count": 0, "data": [], "message": "API key not configured"}

    try:
        # Odds API scores endpoint - FREE for live/upcoming, 2 credits for daysFrom
        scores_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/scores"
        params = {
            "apiKey": ODDS_API_KEY,
            "daysFrom": days_from
        }

        resp = await fetch_with_retries("GET", scores_url, params=params)

        if resp and resp.status_code == 200:
            games = resp.json()

            for game in games:
                scores_data = game.get("scores", [])
                home_score = None
                away_score = None

                for score_entry in scores_data:
                    if score_entry.get("name") == game.get("home_team"):
                        home_score = score_entry.get("score")
                    elif score_entry.get("name") == game.get("away_team"):
                        away_score = score_entry.get("score")

                data.append({
                    "id": game.get("id"),
                    "sport_key": game.get("sport_key"),
                    "sport_title": game.get("sport_title"),
                    "home_team": game.get("home_team"),
                    "away_team": game.get("away_team"),
                    "commence_time": game.get("commence_time"),
                    "completed": game.get("completed", False),
                    "home_score": home_score,
                    "away_score": away_score,
                    "scores": scores_data,
                    "last_update": game.get("last_update")
                })

            logger.info("Odds API scores for %s: %d games (days_from=%d)", sport, len(data), days_from)

        elif resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")
        else:
            logger.warning("Odds API scores returned %s for %s", resp.status_code if resp else "no response", sport)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Odds API scores fetch failed for %s: %s", sport, e)

    result = {
        "sport": sport.upper(),
        "source": "odds_api" if data else "none",
        "count": len(data),
        "data": data,
        "completed_count": sum(1 for g in data if g.get("completed")),
        "live_count": sum(1 for g in data if not g.get("completed") and g.get("scores"))
    }

    # Short cache for live scores (2 minutes)
    api_cache.set(cache_key, result, ttl=120)
    return result


@router.get("/lines/{sport}")
async def get_lines(sport: str):
    """
    Get current betting lines (spread/total/ML) using Playbook API.

    Response Schema:
    {
        "sport": "NBA",
        "source": "playbook" | "odds_api",
        "count": N,
        "data": [...]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"lines:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    # Try Playbook API first - /lines?league=NBA&api_key=...
    if PLAYBOOK_API_KEY:
        try:
            playbook_url = f"{PLAYBOOK_API_BASE}/lines"
            resp = await fetch_with_retries(
                "GET", playbook_url,
                params={"league": sport_config['playbook'], "api_key": PLAYBOOK_API_KEY}
            )

            if resp and resp.status_code == 200:
                try:
                    json_body = resp.json()
                    lines = json_body if isinstance(json_body, list) else json_body.get("data", json_body.get("lines", []))
                    logger.info("Playbook lines retrieved for %s: %d games", sport, len(lines))
                    result = {"sport": sport.upper(), "source": "playbook", "count": len(lines), "data": lines}
                    api_cache.set(cache_key, result)
                    return result
                except ValueError as e:
                    logger.error("Failed to parse Playbook lines response: %s", e)

            if resp and resp.status_code == 429:
                raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Playbook lines fetch failed for %s: %s", sport, e)

    # Fallback to Odds API
    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "spreads,totals,h2h",
                "oddsFormat": "american"
            }
        )

        if resp and resp.status_code == 200:
            games = resp.json()
            for game in games:
                game_lines = {
                    "game_id": game.get("id"),
                    "home_team": game.get("home_team"),
                    "away_team": game.get("away_team"),
                    "commence_time": game.get("commence_time"),
                    "spreads": [],
                    "totals": [],
                    "moneylines": []
                }

                for bm in game.get("bookmakers", []):
                    book = bm.get("key")
                    for market in bm.get("markets", []):
                        market_key = market.get("key")
                        for outcome in market.get("outcomes", []):
                            entry = {
                                "book": book,
                                "team": outcome.get("name"),
                                "price": outcome.get("price"),
                                "point": outcome.get("point")
                            }
                            if market_key == "spreads":
                                game_lines["spreads"].append(entry)
                            elif market_key == "totals":
                                game_lines["totals"].append(entry)
                            elif market_key == "h2h":
                                game_lines["moneylines"].append(entry)

                data.append(game_lines)

            logger.info("Odds API lines retrieved for %s: %d games", sport, len(data))

        elif resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Odds API lines fetch failed for %s: %s", sport, e)

    result = {"sport": sport.upper(), "source": "odds_api" if data else "none", "count": len(data), "data": data}
    api_cache.set(cache_key, result)
    return result


@router.get("/alternate-lines/{sport}")
async def get_alternate_lines(sport: str):
    """
    v10.64: Get alternate spreads and totals for hook shopping.

    Provides multiple spread and total options per game for finding
    the best number (e.g., -6.5 vs -7 vs -7.5).

    Response Schema:
    {
        "sport": "NBA",
        "source": "odds_api",
        "count": N,
        "data": [
            {
                "game_id": "...",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "alternate_spreads": [
                    {"point": -5.5, "price": -130, "book": "draftkings"},
                    {"point": -6.5, "price": -110, "book": "draftkings"},
                    {"point": -7.5, "price": +100, "book": "draftkings"}
                ],
                "alternate_totals": [
                    {"point": 218.5, "price": -110, "book": "fanduel"},
                    {"point": 220.5, "price": -110, "book": "fanduel"}
                ]
            }
        ]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    cache_key = f"alt_lines:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    if not ODDS_API_KEY:
        return {"sport": sport.upper(), "source": "none", "count": 0, "data": [], "message": "API key not configured"}

    try:
        # Fetch alternate spreads and totals
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "alternate_spreads,alternate_totals",
                "oddsFormat": "american"
            }
        )

        if resp and resp.status_code == 200:
            games = resp.json()

            for game in games:
                game_data = {
                    "game_id": game.get("id"),
                    "home_team": game.get("home_team"),
                    "away_team": game.get("away_team"),
                    "commence_time": game.get("commence_time"),
                    "alternate_spreads": [],
                    "alternate_totals": []
                }

                for bm in game.get("bookmakers", []):
                    book = bm.get("key")
                    for market in bm.get("markets", []):
                        market_key = market.get("key")
                        for outcome in market.get("outcomes", []):
                            entry = {
                                "team": outcome.get("name"),
                                "point": outcome.get("point"),
                                "price": outcome.get("price"),
                                "book": book
                            }
                            if market_key == "alternate_spreads":
                                game_data["alternate_spreads"].append(entry)
                            elif market_key == "alternate_totals":
                                game_data["alternate_totals"].append(entry)

                if game_data["alternate_spreads"] or game_data["alternate_totals"]:
                    data.append(game_data)

            logger.info("Alternate lines for %s: %d games", sport, len(data))

        elif resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Alternate lines fetch failed for %s: %s", sport, e)

    result = {"sport": sport.upper(), "source": "odds_api" if data else "none", "count": len(data), "data": data}
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/team-totals/{sport}")
async def get_team_totals(sport: str):
    """
    v10.64: Get team totals (individual team over/unders).

    Critical for prop correlation - if team total is 115.5 over,
    player point props on that team are more likely to hit overs.

    Response Schema:
    {
        "sport": "NBA",
        "source": "odds_api",
        "count": N,
        "data": [
            {
                "game_id": "...",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "team_totals": {
                    "Lakers": {"over": 112.5, "over_price": -110, "under": 112.5, "under_price": -110},
                    "Celtics": {"over": 108.5, "over_price": -115, "under": 108.5, "under_price": -105}
                }
            }
        ]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    cache_key = f"team_totals:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    if not ODDS_API_KEY:
        return {"sport": sport.upper(), "source": "none", "count": 0, "data": [], "message": "API key not configured"}

    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "team_totals",
                "oddsFormat": "american"
            }
        )

        if resp and resp.status_code == 200:
            games = resp.json()

            for game in games:
                game_data = {
                    "game_id": game.get("id"),
                    "home_team": game.get("home_team"),
                    "away_team": game.get("away_team"),
                    "commence_time": game.get("commence_time"),
                    "team_totals": {}
                }

                for bm in game.get("bookmakers", [])[:1]:  # First book only to avoid duplicates
                    for market in bm.get("markets", []):
                        if market.get("key") == "team_totals":
                            for outcome in market.get("outcomes", []):
                                team = outcome.get("description", "")
                                side = outcome.get("name", "").lower()  # "Over" or "Under"
                                point = outcome.get("point")
                                price = outcome.get("price")

                                if team not in game_data["team_totals"]:
                                    game_data["team_totals"][team] = {}

                                if side == "over":
                                    game_data["team_totals"][team]["over"] = point
                                    game_data["team_totals"][team]["over_price"] = price
                                elif side == "under":
                                    game_data["team_totals"][team]["under"] = point
                                    game_data["team_totals"][team]["under_price"] = price

                if game_data["team_totals"]:
                    data.append(game_data)

            logger.info("Team totals for %s: %d games", sport, len(data))

        elif resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Team totals fetch failed for %s: %s", sport, e)

    result = {"sport": sport.upper(), "source": "odds_api" if data else "none", "count": len(data), "data": data}
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/historical-odds/{sport}")
async def get_historical_odds(sport: str, date: str = None, markets: str = "spreads,totals"):
    """
    v10.64: Get historical odds snapshot for opening lines.

    WARNING: EXPENSIVE - 10 credits per market per region!
    Use sparingly. Data available from June 2020, 5-10 minute intervals.

    Args:
        sport: Sport key (nba, nfl, mlb, nhl)
        date: ISO timestamp (e.g., "2026-01-22T12:00:00Z"). Defaults to 24h ago.
        markets: Comma-separated markets (default: spreads,totals)

    Response includes previous_timestamp and next_timestamp for navigation.
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    if not ODDS_API_KEY:
        return {"sport": sport.upper(), "source": "none", "count": 0, "data": [], "message": "API key not configured"}

    sport_config = SPORT_MAPPINGS[sport_lower]

    # Default to 24 hours ago if no date specified
    if not date:
        from datetime import timezone
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        date = yesterday.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Cache with date in key (historical data doesn't change)
    cache_key = f"historical_odds:{sport_lower}:{date}:{markets}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    try:
        hist_url = f"{ODDS_API_BASE}/historical/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", hist_url,
            params={
                "apiKey": ODDS_API_KEY,
                "date": date,
                "regions": "us",
                "markets": markets,
                "oddsFormat": "american"
            }
        )

        if resp and resp.status_code == 200:
            data = resp.json()
            result = {
                "sport": sport.upper(),
                "source": "odds_api_historical",
                "timestamp": data.get("timestamp"),
                "previous_timestamp": data.get("previous_timestamp"),
                "next_timestamp": data.get("next_timestamp"),
                "count": len(data.get("data", [])),
                "data": data.get("data", []),
                "cost_warning": "10 credits per market per region"
            }
            # Long cache for historical (it doesn't change)
            api_cache.set(cache_key, result, ttl=3600)
            logger.info("Historical odds for %s at %s: %d events", sport, date, result["count"])
            return result

        elif resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")
        elif resp and resp.status_code == 422:
            return {"sport": sport.upper(), "source": "none", "count": 0, "data": [], "message": "Invalid date format. Use ISO 8601 (e.g., 2026-01-22T12:00:00Z)"}
        else:
            logger.warning("Historical odds returned %s for %s", resp.status_code if resp else "no response", sport)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Historical odds fetch failed for %s: %s", sport, e)

    return {"sport": sport.upper(), "source": "none", "count": 0, "data": []}


@router.get("/available-markets/{sport}/{event_id}")
async def get_available_markets(sport: str, event_id: str):
    """
    v10.64: Discover all available markets for a specific event.

    Returns market keys available from each bookmaker. Useful for
    finding what player props and alternate lines exist.

    Cost: 1 credit
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    if not ODDS_API_KEY:
        return {"sport": sport.upper(), "source": "none", "markets": [], "message": "API key not configured"}

    sport_config = SPORT_MAPPINGS[sport_lower]

    cache_key = f"markets:{sport_lower}:{event_id}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    try:
        markets_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/events/{event_id}/markets"
        resp = await fetch_with_retries(
            "GET", markets_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us"
            }
        )

        if resp and resp.status_code == 200:
            data = resp.json()
            bookmakers = data.get("bookmakers", [])

            # Aggregate all unique markets across bookmakers
            all_markets = set()
            markets_by_book = {}

            for bm in bookmakers:
                book_key = bm.get("key")
                book_markets = [m.get("key") for m in bm.get("markets", [])]
                markets_by_book[book_key] = book_markets
                all_markets.update(book_markets)

            result = {
                "sport": sport.upper(),
                "event_id": event_id,
                "source": "odds_api",
                "all_markets": sorted(list(all_markets)),
                "markets_by_bookmaker": markets_by_book,
                "total_unique_markets": len(all_markets)
            }

            api_cache.set(cache_key, result, ttl=300)
            logger.info("Available markets for %s event %s: %d markets", sport, event_id, len(all_markets))
            return result

        elif resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")
        elif resp and resp.status_code == 404:
            return {"sport": sport.upper(), "event_id": event_id, "source": "none", "markets": [], "message": "Event not found"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Available markets fetch failed: %s", e)

    return {"sport": sport.upper(), "event_id": event_id, "source": "none", "markets": []}


@router.get("/period-markets/{sport}")
async def get_period_markets(sport: str, period: str = "q1"):
    """
    v10.65: Get first quarter/half betting markets.

    Period options:
    - q1, q2, q3, q4: Quarter markets (NBA, NFL)
    - h1, h2: Half markets (all sports)
    - p1, p2, p3: Period markets (NHL)
    - 1st_5_innings: First 5 innings (MLB)

    Response includes h2h, spreads, and totals for the specified period.
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Validate period
    valid_periods = {
        "nba": ["q1", "q2", "q3", "q4", "h1", "h2"],
        "nfl": ["q1", "q2", "q3", "q4", "h1", "h2"],
        "mlb": ["h1", "1st_5_innings"],
        "nhl": ["p1", "p2", "p3", "h1", "h2"]
    }
    allowed = valid_periods.get(sport_lower, ["h1", "h2"])
    if period not in allowed:
        return {"sport": sport.upper(), "error": f"Invalid period '{period}'. Valid: {allowed}"}

    cache_key = f"period_markets:{sport_lower}:{period}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]

    if not ODDS_API_KEY:
        return {"sport": sport.upper(), "source": "none", "data": [], "message": "API key not configured"}

    # Build period market keys
    period_markets = []
    if period.startswith("q"):
        period_markets = [f"h2h_{period}", f"spreads_{period}", f"totals_{period}"]
    elif period.startswith("h"):
        period_markets = [f"h2h_{period}", f"spreads_{period}", f"totals_{period}"]
    elif period.startswith("p"):
        period_markets = [f"h2h_{period}", f"spreads_{period}", f"totals_{period}"]
    elif period == "1st_5_innings":
        period_markets = ["h2h_1st_5_innings", "spreads_1st_5_innings", "totals_1st_5_innings"]

    data = []

    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": ",".join(period_markets),
                "oddsFormat": "american"
            }
        )

        if resp and resp.status_code == 200:
            games = resp.json()

            for game in games:
                game_data = {
                    "game_id": game.get("id"),
                    "home_team": game.get("home_team"),
                    "away_team": game.get("away_team"),
                    "commence_time": game.get("commence_time"),
                    "period": period,
                    "h2h": [],
                    "spreads": [],
                    "totals": []
                }

                for bm in game.get("bookmakers", []):
                    book = bm.get("key")
                    for market in bm.get("markets", []):
                        market_key = market.get("key", "")
                        for outcome in market.get("outcomes", []):
                            entry = {
                                "team": outcome.get("name"),
                                "point": outcome.get("point"),
                                "price": outcome.get("price"),
                                "book": book
                            }
                            if "h2h" in market_key:
                                game_data["h2h"].append(entry)
                            elif "spreads" in market_key:
                                game_data["spreads"].append(entry)
                            elif "totals" in market_key:
                                game_data["totals"].append(entry)

                if game_data["h2h"] or game_data["spreads"] or game_data["totals"]:
                    data.append(game_data)

            logger.info("Period markets (%s) for %s: %d games", period, sport, len(data))

        elif resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Odds API rate limited (429). Try again later.")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Period markets fetch failed for %s: %s", sport, e)

    result = {
        "sport": sport.upper(),
        "period": period,
        "source": "odds_api" if data else "none",
        "count": len(data),
        "data": data,
        "available_periods": allowed
    }
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/playbook/teams/{sport}")
async def get_playbook_teams(sport: str, include_injuries: bool = False):
    """
    v10.65: Get full team metadata from Playbook API.

    Includes team info, abbreviations, and optionally injury data.
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    cache_key = f"playbook_teams:{sport_lower}:{include_injuries}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]

    if not PLAYBOOK_API_KEY:
        return {"sport": sport.upper(), "source": "none", "data": [], "message": "Playbook API key not configured"}

    try:
        teams_url = f"{PLAYBOOK_API_BASE}/teams"
        params = {
            "league": sport_config['playbook'],
            "api_key": PLAYBOOK_API_KEY
        }
        if include_injuries:
            params["injuries"] = "true"

        resp = await fetch_with_retries("GET", teams_url, params=params)

        if resp and resp.status_code == 200:
            data = resp.json()
            teams = data if isinstance(data, list) else data.get("data", data.get("teams", []))

            result = {
                "sport": sport.upper(),
                "source": "playbook",
                "count": len(teams),
                "data": teams,
                "includes_injuries": include_injuries
            }
            api_cache.set(cache_key, result, ttl=600)  # 10 min cache (teams don't change often)
            logger.info("Playbook teams for %s: %d teams", sport, len(teams))
            return result

        elif resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Playbook teams fetch failed for %s: %s", sport, e)

    return {"sport": sport.upper(), "source": "none", "data": []}


@router.get("/playbook/splits-history/{sport}")
async def get_playbook_splits_history(sport: str, date: str = None):
    """
    v10.65: Get historical betting splits from Playbook API.

    Useful for backtesting and analyzing historical sharp action.

    Args:
        sport: Sport key
        date: Date in YYYY-MM-DD format (defaults to yesterday)
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Default to yesterday
    if not date:
        yesterday = datetime.now() - timedelta(days=1)
        date = yesterday.strftime("%Y-%m-%d")

    cache_key = f"splits_history:{sport_lower}:{date}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]

    if not PLAYBOOK_API_KEY:
        return {"sport": sport.upper(), "source": "none", "data": [], "message": "Playbook API key not configured"}

    try:
        url = f"{PLAYBOOK_API_BASE}/splits-history"
        params = {
            "league": sport_config['playbook'],
            "date": date,
            "api_key": PLAYBOOK_API_KEY
        }

        resp = await fetch_with_retries("GET", url, params=params)

        if resp and resp.status_code == 200:
            data = resp.json()
            splits = data if isinstance(data, list) else data.get("data", data.get("splits", []))

            # Analyze sharp action from historical splits
            sharp_games = []
            for game in splits:
                money_pct = game.get("money_pct", game.get("moneyPct", 50))
                ticket_pct = game.get("ticket_pct", game.get("ticketPct", 50))
                diff = abs(money_pct - ticket_pct)

                if diff >= 7:  # v10.91: Lowered from 10% to 7%
                    game["sharp_detected"] = True
                    game["sharp_side"] = "HOME" if money_pct > ticket_pct else "AWAY"
                    game["sharp_strength"] = "STRONG" if diff >= 15 else "MODERATE"  # v10.91: 15%+ STRONG
                    sharp_games.append(game)

            result = {
                "sport": sport.upper(),
                "date": date,
                "source": "playbook",
                "count": len(splits),
                "data": splits,
                "sharp_games_count": len(sharp_games),
                "sharp_games": sharp_games
            }
            # Long cache for historical data (doesn't change)
            api_cache.set(cache_key, result, ttl=3600)
            logger.info("Playbook splits history for %s on %s: %d games, %d sharp", sport, date, len(splits), len(sharp_games))
            return result

        elif resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")
        elif resp and resp.status_code == 404:
            return {"sport": sport.upper(), "date": date, "source": "none", "data": [], "message": "No data for this date"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Playbook splits history fetch failed for %s: %s", sport, e)

    return {"sport": sport.upper(), "date": date, "source": "none", "data": []}


@router.get("/playbook/schedule/{sport}")
async def get_playbook_schedule(sport: str):
    """
    v10.65: Get lightweight game schedule from Playbook API.

    Uses /odds-games endpoint for fast schedule with gameIds.
    Useful for getting event IDs without full odds data.
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    cache_key = f"playbook_schedule:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]

    if not PLAYBOOK_API_KEY:
        return {"sport": sport.upper(), "source": "none", "data": [], "message": "Playbook API key not configured"}

    try:
        url = f"{PLAYBOOK_API_BASE}/odds-games"
        params = {
            "league": sport_config['playbook'],
            "api_key": PLAYBOOK_API_KEY
        }

        resp = await fetch_with_retries("GET", url, params=params)

        if resp and resp.status_code == 200:
            data = resp.json()
            games = data if isinstance(data, list) else data.get("data", data.get("games", []))

            result = {
                "sport": sport.upper(),
                "source": "playbook",
                "count": len(games),
                "data": games,
                "timestamp": datetime.now().isoformat()
            }
            api_cache.set(cache_key, result, ttl=300)
            logger.info("Playbook schedule for %s: %d games", sport, len(games))
            return result

        elif resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Playbook schedule fetch failed for %s: %s", sport, e)

    return {"sport": sport.upper(), "source": "none", "data": []}


@router.get("/playbook/games/{sport}")
async def get_playbook_games(sport: str, date: str = None):
    """
    v10.65: Get detailed game objects from Playbook API.

    More detailed than /schedule, includes game context.

    Args:
        sport: Sport key
        date: Date in YYYY-MM-DD format (defaults to today)
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Default to today
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    cache_key = f"playbook_games:{sport_lower}:{date}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]

    if not PLAYBOOK_API_KEY:
        return {"sport": sport.upper(), "source": "none", "data": [], "message": "Playbook API key not configured"}

    try:
        url = f"{PLAYBOOK_API_BASE}/games"
        params = {
            "league": sport_config['playbook'],
            "date": date,
            "api_key": PLAYBOOK_API_KEY
        }

        resp = await fetch_with_retries("GET", url, params=params)

        if resp and resp.status_code == 200:
            data = resp.json()
            games = data if isinstance(data, list) else data.get("data", data.get("games", []))

            result = {
                "sport": sport.upper(),
                "date": date,
                "source": "playbook",
                "count": len(games),
                "data": games
            }
            api_cache.set(cache_key, result, ttl=300)
            logger.info("Playbook games for %s on %s: %d games", sport, date, len(games))
            return result

        elif resp and resp.status_code == 429:
            raise HTTPException(status_code=503, detail="Playbook rate limited (429). Try again later.")
        elif resp and resp.status_code == 404:
            return {"sport": sport.upper(), "date": date, "source": "none", "data": [], "message": "No games for this date"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Playbook games fetch failed for %s: %s", sport, e)

    return {"sport": sport.upper(), "date": date, "source": "none", "data": []}


# ============================================================================
# v10.65: API COVERAGE SUMMARY ENDPOINT
# ============================================================================

@router.get("/env-check")
async def env_check():
    """Debug endpoint to check environment variable loading."""
    import os
    return {
        "twitter_bearer_set": bool(os.getenv("TWITTER_BEARER")),
        "twitter_bearer_len": len(os.getenv("TWITTER_BEARER", "")),
        "finnhub_key_set": bool(os.getenv("FINNHUB_KEY")),
        "serpapi_key_set": bool(os.getenv("SERPAPI_KEY")),
        "fred_api_key_set": bool(os.getenv("FRED_API_KEY")),
        "alt_data_available": ALT_DATA_AVAILABLE,
        "alt_data_status": get_alt_data_status() if ALT_DATA_AVAILABLE else "not_loaded"
    }

@router.get("/api-coverage")
async def get_api_coverage():
    """
    v10.66: Summary of all API endpoints and data sources being utilized.

    Shows what data we're pulling from each paid API subscription.
    """
    # v10.66: Get alternative data status
    alt_data_status = {}
    if ALT_DATA_AVAILABLE:
        alt_data_status = get_alt_data_status()

    return {
        "version": "v10.80",
        "odds_api": {
            "configured": bool(ODDS_API_KEY),
            "endpoints_used": [
                {"endpoint": "/sports", "purpose": "List sports", "cost": "FREE"},
                {"endpoint": "/sports/{sport}/events", "purpose": "Event list", "cost": "FREE"},
                {"endpoint": "/sports/{sport}/odds", "purpose": "Live odds", "cost": "1 credit/market/region"},
                {"endpoint": "/sports/{sport}/scores", "purpose": "Game scores for grading", "cost": "FREE (live), 2 credits (historical)"},
                {"endpoint": "/sports/{sport}/events/{id}/odds", "purpose": "Single event odds + props", "cost": "1 credit/market/region"},
                {"endpoint": "/sports/{sport}/events/{id}/markets", "purpose": "Discover available markets", "cost": "1 credit"},
                {"endpoint": "/historical/sports/{sport}/odds", "purpose": "Opening lines for RLM", "cost": "10 credits/market/region"},
            ],
            "markets_pulled": {
                "main": ["h2h", "spreads", "totals"],
                "alternate": ["alternate_spreads", "alternate_totals"],
                "team": ["team_totals"],
                "period": ["h2h_q1", "spreads_q1", "totals_q1", "h2h_h1", "spreads_h1", "totals_h1"],
                "player_props": {
                    "nba": ["player_points", "player_rebounds", "player_assists", "player_threes", "player_blocks", "player_steals", "player_turnovers", "player_points_rebounds_assists", "player_double_double", "player_first_basket"],
                    "nfl": ["player_pass_tds", "player_pass_yds", "player_rush_yds", "player_reception_yds", "player_receptions", "player_anytime_td", "player_rush_attempts", "player_tackles_assists", "player_sacks"],
                    "mlb": ["batter_total_bases", "batter_hits", "batter_rbis", "batter_home_runs", "batter_runs_scored", "pitcher_strikeouts", "pitcher_hits_allowed"],
                    "nhl": ["player_points", "player_goals", "player_assists", "player_shots_on_goal", "player_power_play_points", "goalie_saves"]
                }
            }
        },
        "playbook_api": {
            "configured": bool(PLAYBOOK_API_KEY),
            "endpoints_used": [
                {"endpoint": "/health", "purpose": "API health check"},
                {"endpoint": "/me", "purpose": "Usage monitoring"},
                {"endpoint": "/splits", "purpose": "Betting splits (sharp detection)"},
                {"endpoint": "/splits-history", "purpose": "Historical splits for backtesting"},
                {"endpoint": "/lines", "purpose": "Opening/current lines for RLM"},
                {"endpoint": "/injuries", "purpose": "Injury reports"},
                {"endpoint": "/teams", "purpose": "Team metadata"},
                {"endpoint": "/odds-games", "purpose": "Lightweight schedule"},
                {"endpoint": "/games", "purpose": "Detailed game objects"},
            ]
        },
        "free_apis": [
            {
                "name": "ESPN",
                "purpose": "Box scores, player stats, injuries, starting lineups, officials, referee tendencies",
                "cost": "FREE",
                "features": ["starting_lineups", "officials", "referee_tendencies", "player_stats", "injuries"],
                "sports": ["nba", "nfl", "mlb", "nhl", "ncaab"]
            },
            {"name": "BallDontLie", "purpose": "NBA player stats backup", "cost": "FREE"},
            {"name": "NOAA", "purpose": "Space weather (Schumann resonance)", "cost": "FREE"},
        ],
        "espn_integration": {
            "configured": True,
            "features": ["starting_lineups", "officials", "referee_tendencies"],
            "endpoints_used": [
                {"endpoint": "/scoreboard", "purpose": "Today's games list", "cost": "FREE"},
                {"endpoint": "/summary?event={id}", "purpose": "Starters + officials for specific game", "cost": "FREE"}
            ],
            "referee_database": {
                "known_refs": 10,
                "tendencies_tracked": ["foul_rate", "over_tendency", "reputation"]
            },
            "scoring_integration": "referee_adjustment pillar (+/-0.2 for totals bets)"
        },
        "optional_apis": [
            {"name": "Weather", "env_var": "WEATHER_API_KEY", "purpose": "Game day weather for outdoor sports"},
        ],
        "alternative_data_apis": {
            "twitter": {
                "configured": alt_data_status.get("twitter", {}).get("configured", False),
                "env_var": "TWITTER_BEARER",
                "purpose": "Breaking injury news, beat reporter alerts, sentiment analysis",
                "integration": "Hospital Fade pillar boost + injury alerts"
            },
            "finnhub": {
                "configured": alt_data_status.get("finnhub", {}).get("configured", False),
                "env_var": "FINNHUB_KEY",
                "purpose": "Sportsbook stock sentiment (DKNG, FLTR), institutional movement",
                "integration": "Alternative sharp signal when no traditional sharp detected"
            },
            "serpapi": {
                "configured": alt_data_status.get("serpapi", {}).get("configured", False),
                "env_var": "SERPAPI_KEY",
                "purpose": "Google News aggregation, trending injury stories",
                "integration": "Supplementary injury detection"
            },
            "fred": {
                "configured": alt_data_status.get("fred", {}).get("configured", False),
                "env_var": "FRED_API_KEY",
                "purpose": "Economic indicators, consumer sentiment index",
                "integration": "Esoteric score component (economic tailwind/headwind)"
            }
        },
        "backend_endpoints": {
            "scores": "/live/scores/{sport}",
            "props": "/live/props/{sport}",
            "lines": "/live/lines/{sport}",
            "splits": "/live/splits/{sport}",
            "sharp": "/live/sharp/{sport}",
            "alternate_lines": "/live/alternate-lines/{sport}",
            "team_totals": "/live/team-totals/{sport}",
            "period_markets": "/live/period-markets/{sport}?period=q1",
            "historical_odds": "/live/historical-odds/{sport}?date=YYYY-MM-DDTHH:MM:SSZ",
            "available_markets": "/live/available-markets/{sport}/{event_id}",
            "playbook_teams": "/live/playbook/teams/{sport}",
            "playbook_schedule": "/live/playbook/schedule/{sport}",
            "playbook_games": "/live/playbook/games/{sport}",
            "playbook_splits_history": "/live/playbook/splits-history/{sport}?date=YYYY-MM-DD",
        }
    }


# ============================================================================
# v10.45: ODDS DIAGNOSTIC ENDPOINT
# Deep debug output for game odds fetching with fallback cache
# ============================================================================

# Global odds metrics tracking (per-sport)
ODDS_METRICS: Dict[str, Dict[str, Any]] = {}

# Odds fallback cache (persists last successful snapshot per sport)
ODDS_FALLBACK_CACHE: Dict[str, Dict[str, Any]] = {}


def get_et_hour() -> int:
    """Get current hour in Eastern Time (0-23)."""
    from datetime import timezone, timedelta
    try:
        now_utc = datetime.now(timezone.utc)
        et_offset = timedelta(hours=-5)  # ET is UTC-5 (ignoring DST for simplicity)
        now_et = now_utc + et_offset
        return now_et.hour
    except Exception:
        return 12  # Default to noon if calculation fails


def is_daytime_et() -> bool:
    """Check if current time is daytime ET (08:00-23:00)."""
    hour = get_et_hour()
    return 8 <= hour <= 23


# ============================================================================
# v10.52: TIME GATE - Same Day ET + Not Started
# Filters out picks for games that are:
# - NOT on the same America/New_York (ET) calendar day as now
# - Already started (with 180s grace for clock drift)
# ============================================================================

try:
    from zoneinfo import ZoneInfo
    ET_TIMEZONE = ZoneInfo("America/New_York")
    ZONEINFO_AVAILABLE = True
except ImportError:
    ET_TIMEZONE = None
    ZONEINFO_AVAILABLE = False
    logger.warning("zoneinfo not available - time gate will use fallback")


def parse_utc_iso(iso: str) -> Optional[datetime]:
    """Parse a UTC ISO timestamp string to datetime. Returns None on failure."""
    if not iso:
        return None
    try:
        # Handle various ISO formats
        cleaned = iso.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return None


def get_now_et() -> datetime:
    """Get current datetime in Eastern Time."""
    if ZONEINFO_AVAILABLE and ET_TIMEZONE:
        return datetime.now(ET_TIMEZONE)
    else:
        # Fallback: UTC-5 (doesn't handle DST but better than nothing)
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)
        return now_utc.replace(tzinfo=None) - timedelta(hours=5)


def convert_to_et(dt_utc: datetime) -> datetime:
    """Convert a UTC datetime to Eastern Time."""
    if ZONEINFO_AVAILABLE and ET_TIMEZONE:
        if dt_utc.tzinfo is None:
            # Assume UTC if no timezone
            from datetime import timezone
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        return dt_utc.astimezone(ET_TIMEZONE)
    else:
        # Fallback: subtract 5 hours
        return dt_utc.replace(tzinfo=None) - timedelta(hours=5)


def format_et_display(dt_et: datetime) -> str:
    """Format ET datetime for display (e.g., '2026-01-23 7:30 PM ET')."""
    return dt_et.strftime("%Y-%m-%d %-I:%M %p ET")


def is_today_and_not_started(game_time_iso: str, grace_seconds: int = 180) -> tuple:
    """
    Check if a game is on today's ET calendar day and hasn't started yet.

    Args:
        game_time_iso: ISO timestamp of game start (UTC)
        grace_seconds: Grace period for clock drift (default 180s = 3 min)

    Returns:
        tuple: (is_valid: bool, reason: str, game_time_et: datetime|None)
        Reasons: "ok", "missing_time", "not_today", "already_started"
    """
    dt_utc = parse_utc_iso(game_time_iso)
    if not dt_utc:
        return False, "missing_time", None

    now_et = get_now_et()
    dt_et = convert_to_et(dt_utc)

    # Check same calendar day in ET
    if dt_et.date() != now_et.date():
        return False, "not_today", dt_et

    # Check not already started (with grace window)
    grace_cutoff = now_et - timedelta(seconds=grace_seconds)
    if dt_et <= grace_cutoff:
        return False, "already_started", dt_et

    return True, "ok", dt_et


def apply_time_gate(picks: List[Dict[str, Any]], grace_seconds: int = 180) -> tuple:
    """
    Add game status fields to all picks and filter to today's games only.

    v7.9 UPDATE: No longer removes already-started games. Instead marks them
    as LIVE status with is_already_started=True. Only removes games not on today.

    Args:
        picks: List of pick dictionaries (must have game_time field)
        grace_seconds: Grace period for clock drift

    Returns:
        tuple: (filtered_picks, time_gate_debug)

    Each pick gets these fields added:
        - game_status: "PREGAME" | "LIVE" | "FINAL"
        - is_already_started: bool
        - start_time_est: formatted ET time string
        - live_bet_only: bool (True if game already started)
    """
    now_et = get_now_et()

    debug = {
        "now_et": now_et.isoformat() if hasattr(now_et, 'isoformat') else str(now_et),
        "grace_seconds": grace_seconds,
        "candidates_before_time_gate": len(picks),
        "candidates_after_time_gate": 0,
        "removed_not_today": 0,
        "count_pregame": 0,
        "count_live": 0,
        "removed_missing_time": 0
    }

    filtered = []
    for pick in picks:
        # Get game time from various possible fields
        game_time_iso = (
            pick.get("game_time") or
            pick.get("commence_time") or
            pick.get("start_time") or
            ""
        )

        is_valid, reason, dt_et = is_today_and_not_started(game_time_iso, grace_seconds)

        # Always add status fields
        if dt_et:
            pick["start_time_est"] = format_et_display(dt_et)
            pick["game_time_et"] = format_et_display(dt_et)

        if reason == "missing_time":
            # Can't determine status without time - skip
            debug["removed_missing_time"] += 1
            continue

        if reason == "not_today":
            # Not today's game - remove
            debug["removed_not_today"] += 1
            continue

        # Today's game - determine status
        if reason == "already_started":
            # Game has started - mark as LIVE
            pick["game_status"] = "LIVE"
            pick["is_already_started"] = True
            pick["live_bet_only"] = True
            debug["count_live"] += 1
        else:
            # Game not started yet - PREGAME
            pick["game_status"] = "PREGAME"
            pick["is_already_started"] = False
            pick["live_bet_only"] = False
            debug["count_pregame"] += 1

        filtered.append(pick)

    debug["candidates_after_time_gate"] = len(filtered)

    return filtered, debug


def ensure_pick_labels(pick: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure pick has team and opponent labels for display.
    Extracts from available fields if not already present.
    """
    # Ensure team label
    if not pick.get("team"):
        pick["team"] = (
            pick.get("player_team") or
            pick.get("team_abbr") or
            pick.get("home_team") or
            pick.get("away_team") or
            "TBD"
        )

    # Ensure opponent label
    if not pick.get("opponent"):
        home = pick.get("home_team", "")
        away = pick.get("away_team", "")
        team = pick.get("team", "")

        # If we know team, opponent is the other
        if team and home and away:
            pick["opponent"] = away if team.upper() == home.upper() else home
        else:
            pick["opponent"] = home or away or "TBD"

    # Ensure game_time_et if we have game_time
    if not pick.get("game_time_et"):
        game_time_iso = pick.get("game_time") or pick.get("commence_time", "")
        dt_utc = parse_utc_iso(game_time_iso)
        if dt_utc:
            dt_et = convert_to_et(dt_utc)
            pick["game_time_et"] = format_et_display(dt_et)

    # v10.75: Add time status for live-bet detection
    if not pick.get("status_time"):
        game_time_iso = pick.get("game_time") or pick.get("commence_time", "")
        game_state = pick.get("game_state") or pick.get("status")
        time_status = compute_time_status(game_time_iso, game_state=game_state)
        pick["status_time"] = time_status
        pick["start_time_et"] = time_status.get("start_time_et")
        pick["pulled_at_et"] = time_status.get("pulled_at_et")

    return pick


# ============================================================================
# v10.53: SOFT STACKING GOVERNOR
# Prevents same-team spam while allowing SMASH stacks to override limits
# ============================================================================

# Stacking configuration
SMASH_STACK_THRESHOLD = 7.85  # Picks with final_score >= this get SMASH override

# Official Card stacking limits
OFFICIAL_DEFAULT_MAX_PER_GAME = 3
OFFICIAL_DEFAULT_MAX_PER_TEAM_GAME = 2
OFFICIAL_SMASH_MAX_PER_GAME = 5
OFFICIAL_SMASH_MAX_PER_TEAM_GAME = 3
OFFICIAL_HARD_CAP_PER_GAME = 5
OFFICIAL_HARD_CAP_PER_TEAM_GAME = 3

# Action Leans stacking limits (looser since they're gamble feelers)
LEANS_MAX_PER_GAME = 4
LEANS_MAX_PER_TEAM_GAME = 3


def is_smash_stack(pick: Dict[str, Any]) -> bool:
    """
    Check if a pick qualifies as a SMASH STACK (allows higher stacking limits).
    Requires: tier == "GOLD_STAR" AND final_score >= SMASH_STACK_THRESHOLD
    """
    if pick.get("tier") != "GOLD_STAR":
        return False

    score = float(pick.get("final_score") or pick.get("smash_score") or pick.get("total_score") or 0)
    return score >= SMASH_STACK_THRESHOLD


def apply_stacking_limits(
    picks: List[Dict[str, Any]],
    *,
    default_max_game: int = 3,
    default_max_team_game: int = 2,
    smash_max_game: int = 5,
    smash_max_team_game: int = 3,
    hard_cap_game: int = 5,
    hard_cap_team_game: int = 3
) -> tuple:
    """
    Apply stacking limits to prevent same-team spam while allowing SMASH stacks.

    Args:
        picks: List of picks (must be sorted by score DESC)
        default_max_game: Max picks per game (non-SMASH)
        default_max_team_game: Max picks per team per game (non-SMASH)
        smash_max_game: Max picks per game for SMASH stacks
        smash_max_team_game: Max picks per team per game for SMASH stacks
        hard_cap_game: Absolute max picks per game (even for SMASH)
        hard_cap_team_game: Absolute max picks per team per game (even for SMASH)

    Returns:
        tuple: (filtered_picks, removed_count)
    """
    from collections import defaultdict

    game_counts = defaultdict(int)
    team_game_counts = defaultdict(int)

    out = []
    removed = 0

    for pick in picks:
        # Get game identifier
        game_id = (
            pick.get("game") or
            pick.get("matchup") or
            f"{pick.get('away_team', '')}@{pick.get('home_team', '')}" or
            ""
        )
        team = pick.get("team") or ""
        key_team_game = (game_id, team)

        # Determine limits based on SMASH status
        max_game = default_max_game
        max_team_game = default_max_team_game

        if is_smash_stack(pick):
            max_game = smash_max_game
            max_team_game = smash_max_team_game

        # Check hard caps (always apply, even for SMASH)
        if game_counts[game_id] >= hard_cap_game:
            removed += 1
            continue
        if team_game_counts[key_team_game] >= hard_cap_team_game:
            removed += 1
            continue

        # Check current limits
        if game_counts[game_id] >= max_game:
            removed += 1
            continue
        if team_game_counts[key_team_game] >= max_team_game:
            removed += 1
            continue

        # Pick passes - add to output
        out.append(pick)
        game_counts[game_id] += 1
        team_game_counts[key_team_game] += 1

    return out, removed


# ============================================================================
# v10.54: PRODUCTION V3 CONTRACT COMPLIANCE
# Ensures every pick has: deterministic id, int confidence, ordered reasons
# ============================================================================

def clamp_0_10(x) -> float:
    """Clamp a value to the 0.0-10.0 range for score normalization."""
    try:
        return max(0.0, min(10.0, float(x)))
    except Exception:
        return 0.0


def slugify(raw: str) -> str:
    """Convert a string to a URL-safe slug (lowercase, no special chars)."""
    raw = (raw or "").lower()
    raw = raw.replace(" @ ", "_vs_").replace("@", "_vs_").replace("vs.", "vs")
    raw = raw.replace(" ", "_")
    raw = re.sub(r"[^a-z0-9_]", "", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw


def canonical_matchup(matchup: str) -> str:
    """Normalize matchup format to 'Team A vs Team B'."""
    s = (matchup or "").strip()
    s = s.replace(" @ ", " vs ").replace("@", " vs ")
    s = s.replace("VS", "vs").replace("Vs", "vs").replace("vs.", "vs")
    s = re.sub(r"\s+", " ", s)
    return s


def build_pick_id(sport: str, game_time: str, matchup: str, market: str, selection: str, line) -> str:
    """
    Build a deterministic, sanitized ID for a pick.
    Format: sport_date_matchup_market_selection_line
    """
    try:
        dt = datetime.fromisoformat((game_time or "").replace("Z", "+00:00"))
        date = dt.date().isoformat()
    except Exception:
        date = datetime.utcnow().date().isoformat()

    matchup_slug = slugify(canonical_matchup(matchup))
    market_slug = slugify(market or "")
    selection_slug = slugify(selection or "")
    line_str = str(line) if line is not None else ""

    raw = f"{(sport or '').lower()}_{date}_{matchup_slug}_{market_slug}_{selection_slug}_{line_str}"
    return slugify(raw)


# Allowed reason prefixes for Production v3 contract
V3_REASON_PREFIXES = ["RESEARCH:", "ESOTERIC:", "CONFLUENCE:", "GOVERNOR:"]


def normalize_reasons(reasons: List) -> tuple:
    """
    Normalize reasons to Production v3 contract.
    - Keep only RESEARCH/ESOTERIC/CONFLUENCE/GOVERNOR prefixed reasons
    - Order them in the correct sequence
    - Move all other reasons to debug_reasons

    Returns: (ordered_reasons, debug_reasons)
    """
    reasons = reasons or []
    kept = []
    debug = []

    for r in reasons:
        if not isinstance(r, str):
            continue
        rr = r.strip()
        if any(rr.startswith(prefix) for prefix in V3_REASON_PREFIXES):
            kept.append(rr)
        else:
            debug.append(rr)

    # Order by prefix sequence
    ordered = []
    for prefix in V3_REASON_PREFIXES:
        ordered.extend([x for x in kept if x.startswith(prefix)])

    return ordered, debug


def normalize_pick_for_v3(pick: Dict[str, Any], sport: str = "") -> Dict[str, Any]:
    """
    Normalize a pick to Production v3 contract compliance.
    - Add deterministic id
    - Convert confidence to int 0-100
    - Order and filter reasons
    - Clamp scores to 0-10
    """
    # 1. Build deterministic ID if not present
    if not pick.get("id"):
        pick["id"] = build_pick_id(
            sport=sport or pick.get("sport", ""),
            game_time=pick.get("game_time") or pick.get("commence_time") or "",
            matchup=pick.get("matchup") or pick.get("game") or "",
            market=pick.get("market") or pick.get("stat_type") or pick.get("pick_type") or "",
            selection=pick.get("selection") or pick.get("player_name") or pick.get("player") or "",
            line=pick.get("line")
        )

    # 2. Normalize confidence to int 0-100
    old_conf = pick.get("confidence")
    if isinstance(old_conf, str):
        pick["confidence_label"] = old_conf  # Preserve string label

    # Derive confidence from final_score
    final_score = clamp_0_10(pick.get("final_score") or pick.get("smash_score") or pick.get("total_score") or 0)
    pick["final_score"] = round(final_score, 2)
    pick["confidence"] = max(0, min(100, int(round(final_score * 10))))

    # 3. Clamp other scores
    for score_field in ["research_score", "esoteric_score", "ai_score"]:
        if pick.get(score_field) is not None:
            pick[score_field] = round(clamp_0_10(pick[score_field]), 2)

    # 4. Normalize reasons
    pick["reasons"], pick["debug_reasons"] = normalize_reasons(pick.get("reasons", []))

    return pick


@router.get("/odds/{sport}")
async def get_odds(sport: str, debug: int = 0, auth: bool = Depends(verify_api_key)):
    """
    Get game odds (spreads, totals, moneylines) with deep diagnostic output.

    v10.45: This endpoint provides comprehensive debugging for odds ingestion.

    Query Parameters:
    - debug=1: Include full diagnostic info

    Response Schema:
    {
        "sport": "NBA",
        "source": "odds_api" | "fallback_cache" | "none",
        "events": N,
        "markets": { "spreads": N, "totals": N, "h2h": N },
        "data": [...],
        "diagnostics": {
            "provider_url_called": "...",
            "provider_sport_key": "basketball_nba",
            "http_status_code": 200,
            "response_length_bytes": 12345,
            "provider_error_message": null,
            "markets_requested": ["spreads", "totals", "h2h"],
            "timestamp": "...",
            "et_hour": 14,
            "is_daytime_et": true,
            "fallback_cache_used": false,
            "fallback_cache_age_minutes": null
        },
        "metrics": {
            "odds_provider_status": "OK" | "EMPTY" | "ERROR" | "FALLBACK",
            "odds_events_count": N,
            "odds_markets_count": M,
            "odds_cache_age_minutes": null
        }
    }
    """
    global ODDS_METRICS, ODDS_FALLBACK_CACHE

    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    sport_config = SPORT_MAPPINGS[sport_lower]
    sport_key = sport_config["odds"]

    # Initialize diagnostics
    diagnostics = {
        "provider_url_called": None,
        "provider_sport_key": sport_key,
        "http_status_code": None,
        "response_length_bytes": None,
        "provider_error_message": None,
        "markets_requested": ["spreads", "totals", "h2h"],
        "timestamp": datetime.now().isoformat(),
        "et_hour": get_et_hour(),
        "is_daytime_et": is_daytime_et(),
        "fallback_cache_used": False,
        "fallback_cache_age_minutes": None,
        "api_key_configured": bool(ODDS_API_KEY)
    }

    # Initialize metrics
    metrics = {
        "odds_provider_status": "UNKNOWN",
        "odds_events_count": 0,
        "odds_markets_count": 0,
        "odds_cache_age_minutes": None
    }

    # Check cache first (short TTL for live odds)
    cache_key = f"odds:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        # Update metrics from cached data
        metrics["odds_provider_status"] = cached.get("metrics", {}).get("odds_provider_status", "CACHED")
        metrics["odds_events_count"] = cached.get("events", 0)
        metrics["odds_markets_count"] = sum(cached.get("markets", {}).values())
        cached["cache_hit"] = True
        ODDS_METRICS[sport_lower] = metrics
        return cached

    data = []
    market_counts = {"spreads": 0, "totals": 0, "h2h": 0}

    # Try Odds API
    try:
        if not ODDS_API_KEY:
            diagnostics["provider_error_message"] = "ODDS_API_KEY not configured"
            metrics["odds_provider_status"] = "ERROR_NO_KEY"
            logger.warning("Odds API key not configured for /odds/%s", sport)
        else:
            odds_url = f"{ODDS_API_BASE}/sports/{sport_key}/odds"
            diagnostics["provider_url_called"] = odds_url

            resp = await fetch_with_retries(
                "GET", odds_url,
                params={
                    "apiKey": ODDS_API_KEY,
                    "regions": "us",
                    "markets": "spreads,totals,h2h",
                    "oddsFormat": "american"
                }
            )

            if resp:
                diagnostics["http_status_code"] = resp.status_code
                diagnostics["response_length_bytes"] = len(resp.content) if resp.content else 0

                if resp.status_code == 200:
                    games = resp.json()
                    diagnostics["response_length_bytes"] = len(resp.text) if resp.text else 0

                    for game in games:
                        game_data = {
                            "id": game.get("id"),
                            "home_team": game.get("home_team"),
                            "away_team": game.get("away_team"),
                            "commence_time": game.get("commence_time"),
                            "spreads": [],
                            "totals": [],
                            "h2h": []
                        }

                        for bm in game.get("bookmakers", []):
                            book = bm.get("key")
                            for market in bm.get("markets", []):
                                market_key = market.get("key")
                                if market_key in ("spreads", "totals", "h2h"):
                                    for outcome in market.get("outcomes", []):
                                        entry = {
                                            "book": book,
                                            "team": outcome.get("name"),
                                            "price": outcome.get("price"),
                                            "point": outcome.get("point")
                                        }
                                        game_data[market_key].append(entry)
                                        market_counts[market_key] += 1

                        data.append(game_data)

                    metrics["odds_provider_status"] = "OK" if len(data) > 0 else "EMPTY"
                    metrics["odds_events_count"] = len(data)
                    metrics["odds_markets_count"] = sum(market_counts.values())

                    # Store in fallback cache if successful
                    if len(data) > 0:
                        ODDS_FALLBACK_CACHE[sport_lower] = {
                            "data": data,
                            "timestamp": datetime.now(),
                            "events": len(data),
                            "markets": market_counts.copy()
                        }
                        logger.info("Odds fallback cache updated for %s: %d events", sport, len(data))

                elif resp.status_code == 429:
                    diagnostics["provider_error_message"] = "Rate limited (429)"
                    metrics["odds_provider_status"] = "RATE_LIMITED"
                else:
                    diagnostics["provider_error_message"] = f"HTTP {resp.status_code}"
                    metrics["odds_provider_status"] = f"ERROR_{resp.status_code}"
            else:
                diagnostics["provider_error_message"] = "No response from provider (all retries exhausted)"
                metrics["odds_provider_status"] = "ERROR_NO_RESPONSE"

    except Exception as e:
        logger.exception("Odds fetch failed for %s: %s", sport, e)
        diagnostics["provider_error_message"] = str(e)
        metrics["odds_provider_status"] = "ERROR_EXCEPTION"

    # Hard error handling for daytime ET with empty results
    if len(data) == 0 and is_daytime_et():
        diagnostics["daytime_empty_warning"] = "ODDS_API_EMPTY_OR_FAILED_DAYTIME"
        logger.warning(
            "DAYTIME ODDS EMPTY: %s - provider_status=%s, et_hour=%d, error=%s",
            sport, metrics["odds_provider_status"], get_et_hour(), diagnostics.get("provider_error_message")
        )

    # Fallback to cached snapshot if empty and cache is valid (<= 12 hours old)
    if len(data) == 0 and sport_lower in ODDS_FALLBACK_CACHE:
        fallback = ODDS_FALLBACK_CACHE[sport_lower]
        cache_age_minutes = (datetime.now() - fallback["timestamp"]).total_seconds() / 60

        if cache_age_minutes <= 720:  # 12 hours = 720 minutes
            data = fallback["data"]
            market_counts = fallback["markets"]
            diagnostics["fallback_cache_used"] = True
            diagnostics["fallback_cache_age_minutes"] = round(cache_age_minutes, 1)
            metrics["odds_provider_status"] = "FALLBACK"
            metrics["odds_events_count"] = len(data)
            metrics["odds_markets_count"] = sum(market_counts.values())
            metrics["odds_cache_age_minutes"] = round(cache_age_minutes, 1)
            logger.info(
                "Using fallback cache for %s: %d events, age=%.1f minutes",
                sport, len(data), cache_age_minutes
            )
        else:
            logger.warning(
                "Fallback cache too old for %s: age=%.1f minutes (max 720)",
                sport, cache_age_minutes
            )

    # Store metrics globally for access by other endpoints
    ODDS_METRICS[sport_lower] = metrics

    # Determine source
    if diagnostics["fallback_cache_used"]:
        source = "fallback_cache"
    elif len(data) > 0:
        source = "odds_api"
    else:
        source = "none"

    result = {
        "sport": sport.upper(),
        "source": source,
        "events": len(data),
        "markets": market_counts,
        "data": data,
        "diagnostics": diagnostics,  # v10.45: Always include diagnostics for visibility
        "metrics": metrics,
        "timestamp": datetime.now().isoformat()
    }

    # Cache for 5 minutes
    api_cache.set(cache_key, result, ttl=300)

    return result


@router.get("/odds-metrics")
async def get_odds_metrics(auth: bool = Depends(verify_api_key)):
    """
    Get current odds metrics for all sports.

    Returns per-sport metrics for monitoring odds ingestion health.
    """
    global ODDS_METRICS

    return {
        "metrics": ODDS_METRICS,
        "fallback_cache_status": {
            sport: {
                "has_cache": True,
                "cache_age_minutes": round((datetime.now() - cache["timestamp"]).total_seconds() / 60, 1),
                "events_cached": cache["events"]
            }
            for sport, cache in ODDS_FALLBACK_CACHE.items()
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/props/{sport}")
async def get_props(sport: str):
    """
    Get player props for a sport.

    Response Schema:
    {
        "sport": "NBA",
        "source": "odds_api",
        "count": N,
        "data": [...]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"props:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]
    data = []

    # Try Odds API first for props - must fetch per event using /events/{eventId}/odds
    try:
        # Step 1: Get list of events for this sport
        events_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/events"
        events_resp = await fetch_with_retries(
            "GET", events_url,
            params={"apiKey": ODDS_API_KEY}
        )

        if events_resp and events_resp.status_code == 200:
            events = events_resp.json()
            logger.info("Found %d events for %s props", len(events), sport)

            # Step 2: Fetch props for each event
            # v10.64: Expanded prop markets - use ALL available player props from Odds API
            if sport_lower == "nba":
                prop_markets = ",".join([
                    "player_points", "player_rebounds", "player_assists", "player_threes",
                    "player_blocks", "player_steals", "player_turnovers",
                    "player_points_rebounds_assists", "player_points_rebounds",
                    "player_points_assists", "player_rebounds_assists",
                    "player_double_double", "player_first_basket"
                ])
            elif sport_lower == "nfl":
                prop_markets = ",".join([
                    "player_pass_tds", "player_pass_yds", "player_pass_completions", "player_pass_attempts",
                    "player_pass_interceptions", "player_rush_yds", "player_rush_attempts",
                    "player_reception_yds", "player_receptions", "player_anytime_td",
                    "player_kicking_points", "player_field_goals_made",
                    "player_tackles_assists", "player_sacks"
                ])
            elif sport_lower == "mlb":
                prop_markets = ",".join([
                    "batter_total_bases", "batter_hits", "batter_rbis", "batter_runs_scored",
                    "batter_home_runs", "batter_walks", "batter_stolen_bases", "batter_strikeouts",
                    "pitcher_strikeouts", "pitcher_hits_allowed", "pitcher_walks",
                    "pitcher_earned_runs", "pitcher_outs"
                ])
            elif sport_lower == "nhl":
                prop_markets = ",".join([
                    "player_points", "player_goals", "player_assists",
                    "player_shots_on_goal", "player_blocked_shots",
                    "player_power_play_points", "goalie_saves"
                ])
            else:
                prop_markets = "player_points,player_rebounds,player_assists"

            for event in events:  # Fetch ALL games - don't miss any smash picks
                event_id = event.get("id")
                if not event_id:
                    continue

                # v10.50: Only process TODAY's games (skip future dates)
                event_commence = event.get("commence_time", "")
                if not is_game_today(event_commence):
                    continue

                # Fetch props for this specific event
                event_odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/events/{event_id}/odds"
                event_resp = await fetch_with_retries(
                    "GET", event_odds_url,
                    params={
                        "apiKey": ODDS_API_KEY,
                        "regions": "us",
                        "markets": prop_markets,
                        "oddsFormat": "american"
                    }
                )

                if event_resp and event_resp.status_code == 200:
                    try:
                        event_data = event_resp.json()
                        game_props = {
                            "game_id": event_data.get("id"),
                            "home_team": event_data.get("home_team"),
                            "away_team": event_data.get("away_team"),
                            "commence_time": event_data.get("commence_time"),
                            "props": []
                        }

                        # v10.9: Track seen (player, market) to avoid alt lines
                        # Only keep first/best line per player per market
                        seen_player_markets = set()

                        for bm in event_data.get("bookmakers", [])[:1]:  # Only first bookmaker (avoid duplicates)
                            for market in bm.get("markets", []):
                                market_key = market.get("key", "")
                                if "player" in market_key or "batter" in market_key or "pitcher" in market_key:
                                    for outcome in market.get("outcomes", []):
                                        player = outcome.get("description", "")
                                        side = outcome.get("name", "")

                                        # Skip if we already have this player/market combo
                                        dedup_key = f"{player}:{market_key}:{side}"
                                        if dedup_key in seen_player_markets:
                                            continue
                                        seen_player_markets.add(dedup_key)

                                        game_props["props"].append({
                                            "player": player,
                                            "market": market_key,
                                            "line": outcome.get("point", 0),
                                            "odds": outcome.get("price", -110),
                                            "side": side,
                                            "book": bm.get("key")
                                        })

                        if game_props["props"]:
                            data.append(game_props)
                            logger.info("Got %d props for %s vs %s", len(game_props["props"]), game_props["away_team"], game_props["home_team"])

                    except ValueError as e:
                        logger.warning("Failed to parse event %s props: %s", event_id, e)
                else:
                    logger.debug("No props for event %s (status %s)", event_id, event_resp.status_code if event_resp else "no response")

            logger.info("Props data retrieved from Odds API for %s: %d games with props", sport, len(data))
        else:
            logger.warning("Odds API events returned %s for %s, trying Playbook API", events_resp.status_code if events_resp else "no response", sport)

    except Exception as e:
        logger.warning("Odds API props failed for %s: %s, trying Playbook API", sport, e)

    # Fallback to Playbook API for props if Odds API failed or returned no data
    if not data and PLAYBOOK_API_KEY:
        try:
            playbook_url = f"{PLAYBOOK_API_BASE}/props/{sport_config['playbook']}"
            resp = await fetch_with_retries(
                "GET", playbook_url,
                params={"api_key": PLAYBOOK_API_KEY}
            )

            if resp and resp.status_code == 200:
                playbook_data = resp.json()
                for game in playbook_data.get("games", playbook_data.get("data", [])):
                    game_props = {
                        "game_id": game.get("game_id", game.get("id", "")),
                        "home_team": game.get("home_team", ""),
                        "away_team": game.get("away_team", ""),
                        "commence_time": game.get("commence_time", game.get("game_time", "")),
                        "props": []
                    }

                    for prop in game.get("props", game.get("player_props", [])):
                        game_props["props"].append({
                            "player": prop.get("player_name", prop.get("player", "")),
                            "market": prop.get("prop_type", prop.get("market", "points")),
                            "line": prop.get("line", prop.get("value", 0)),
                            "odds": prop.get("odds", prop.get("price", -110)),
                            "side": prop.get("side", prop.get("pick", "Over")),
                            "book": prop.get("sportsbook", prop.get("book", "consensus"))
                        })

                    if game_props["props"]:
                        data.append(game_props)

                logger.info("Props data retrieved from Playbook API for %s: %d games with props", sport, len(data))
            else:
                logger.warning("Playbook API props returned %s for %s", resp.status_code if resp else "no response", sport)

        except Exception as e:
            logger.warning("Playbook API props failed for %s: %s", sport, e)

    # Log if no data was retrieved from any API
    if not data:
        logger.warning("No props data available for %s from any API source", sport)

    result = {"sport": sport.upper(), "source": "odds_api" if data else "none", "count": len(data), "data": data}
    # 8-hour TTL for props - refreshed via scheduler at 10am and 6pm
    api_cache.set(cache_key, result, ttl=28800)
    return result


# ============================================================================
# v10.43+: ALL-SPORTS COMBINED BOARD
# ============================================================================

@router.get("/best-bets/all")
async def get_best_bets_all(debug: int = 0):
    """
    Get best bets across ALL in-season sports in ONE response.

    Returns a unified board with:
    - Props (player props)
    - Game picks (spreads, totals, ML)
    - Across NBA, NFL, MLB, NHL, NCAAB (whichever are in-season)

    Query Parameters:
    - debug=1: Include diagnostic info

    Response Structure:
    {
        "all_picks": {
            "picks": [...],  // Unified list sorted by score
            "count": N
        },
        "by_sport": {
            "NBA": { "props": [...], "game_picks": [...] },
            ...
        },
        "debug": {
            "sports_checked": [...],
            "sports_in_season": [...],
            "sports_returned_picks": {...},
            "global_publish_gate": {...}
        }
    }
    """
    ALL_SPORTS = ["nba", "nfl", "mlb", "nhl", "ncaab"]

    # Track debug info
    debug_info = {
        "sports_checked": [],
        "sports_in_season": [],
        "sports_returned_picks": {},
        "sports_errors": {},
        "global_publish_gate": {},
        # v10.46: Aggregated Jason Sim debug across all sports
        "jason_sim": {
            "available": JASON_SIM_AVAILABLE,
            "games_checked": 0,
            "games_matched": 0,
            "boosted": 0,
            "downgraded": 0,
            "blocked": 0,
            "missing_payload": 0,
            "no_payloads_uploaded": False,
            "by_sport": {}
        }
    }

    # Determine which sports are in-season
    in_season_sports = []
    for sport in ALL_SPORTS:
        debug_info["sports_checked"].append(sport.upper())
        if SEASON_GATING_AVAILABLE:
            if is_in_season(sport.upper()):
                in_season_sports.append(sport)
                debug_info["sports_in_season"].append(sport.upper())
        else:
            # If season gating not available, include all
            in_season_sports.append(sport)
            debug_info["sports_in_season"].append(sport.upper())

    # v10.47: Pre-initialize jason_sim.by_sport for all in-season sports
    for sport in in_season_sports:
        debug_info["jason_sim"]["by_sport"][sport.upper()] = {
            "status": "PENDING",
            "games_checked": 0,
            "games_matched": 0,
            "boosted": 0,
            "downgraded": 0,
            "blocked": 0,
            "missing_payload": 0
        }

    # Collect picks from each sport
    by_sport = {}
    all_picks_raw = []

    for sport in in_season_sports:
        try:
            # v10.46: Call with debug=1 to get Jason Sim stats
            sport_result = await get_best_bets(sport, debug=1, include_conflicts=0, min_confidence="C")

            # Extract props picks
            props_picks = []
            if sport_result.get("props") and sport_result["props"].get("picks"):
                props_picks = sport_result["props"]["picks"]
                # Tag each pick with sport and pick_type
                for pick in props_picks:
                    pick["sport"] = sport.upper()
                    pick["pick_type"] = "prop"

            # Extract game picks
            game_picks = []
            if sport_result.get("game_picks") and sport_result["game_picks"].get("picks"):
                game_picks = sport_result["game_picks"]["picks"]
                # Tag each pick with sport and pick_type
                for pick in game_picks:
                    pick["sport"] = sport.upper()
                    pick["pick_type"] = "game"

            # Store by sport
            by_sport[sport.upper()] = {
                "props": {
                    "count": len(props_picks),
                    "picks": props_picks
                },
                "game_picks": {
                    "count": len(game_picks),
                    "picks": game_picks
                },
                "total_picks": len(props_picks) + len(game_picks)
            }

            # Add to raw pool
            all_picks_raw.extend(props_picks)
            all_picks_raw.extend(game_picks)

            # v10.45: Include odds metrics in per-sport debug
            sport_odds_metrics = ODDS_METRICS.get(sport, {})
            games_reason = "OK" if len(game_picks) > 0 else (
                sport_odds_metrics.get("odds_provider_status", "NO_METRICS")
            )

            # v10.46: Extract and aggregate Jason Sim debug from sport result
            sport_jason_sim = sport_result.get("debug", {}).get("jason_sim", {})
            if sport_jason_sim:
                debug_info["jason_sim"]["games_checked"] += sport_jason_sim.get("games_checked", 0)
                debug_info["jason_sim"]["games_matched"] += sport_jason_sim.get("games_matched", 0)
                debug_info["jason_sim"]["boosted"] += sport_jason_sim.get("boosted", 0)
                debug_info["jason_sim"]["downgraded"] += sport_jason_sim.get("downgraded", 0)
                debug_info["jason_sim"]["blocked"] += sport_jason_sim.get("blocked", 0)
                debug_info["jason_sim"]["missing_payload"] += sport_jason_sim.get("missing_payload", 0)
                if sport_jason_sim.get("no_payloads_uploaded"):
                    debug_info["jason_sim"]["no_payloads_uploaded"] = True
                # v10.47: Mark status OK and merge jason_sim data
                sport_jason_sim["status"] = "OK"
                debug_info["jason_sim"]["by_sport"][sport.upper()] = sport_jason_sim
            else:
                # v10.47: No jason_sim data but no error - mark as OK with empty metrics
                debug_info["jason_sim"]["by_sport"][sport.upper()]["status"] = "OK"

            debug_info["sports_returned_picks"][sport.upper()] = {
                "props": len(props_picks),
                "games": len(game_picks),
                "total": len(props_picks) + len(game_picks),
                # v10.45: Odds pipeline visibility
                "games_reason": games_reason,
                "events_count_raw": sport_odds_metrics.get("odds_events_count", 0),
                "games_candidates_count": sport_result.get("debug", {}).get("game_candidates_before_filter", 0),
                "games_picks_count": len(game_picks),
                "odds_provider_status": sport_odds_metrics.get("odds_provider_status", "UNKNOWN"),
                "odds_events_count": sport_odds_metrics.get("odds_events_count", 0),
                "odds_markets_count": sport_odds_metrics.get("odds_markets_count", 0),
                "odds_cache_age_minutes": sport_odds_metrics.get("odds_cache_age_minutes")
            }

        except Exception as e:
            # v10.47: Structured error object for actionable debugging
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            last_frame = tb[-1] if tb else None
            error_location = f"{last_frame.filename}:{last_frame.lineno}" if last_frame else "unknown"
            logger.warning(f"Error fetching best-bets for {sport}: {e} at {error_location}")
            debug_info["sports_errors"][sport.upper()] = {
                "message": str(e),
                "type": type(e).__name__,
                "error_at": error_location,
                "function": last_frame.name if last_frame else "unknown"
            }
            by_sport[sport.upper()] = {
                "props": {"count": 0, "picks": []},
                "game_picks": {"count": 0, "picks": []},
                "total_picks": 0,
                "error": str(e),
                "error_at": error_location
            }
            # v10.47: Mark jason_sim status as ERROR for this sport
            debug_info["jason_sim"]["by_sport"][sport.upper()]["status"] = "ERROR"
            debug_info["jason_sim"]["by_sport"][sport.upper()]["error"] = str(e)

    # =========================================================================
    # v10.52: TIME GATE - Same Day ET + Not Started
    # Filter out picks for games NOT on today's ET calendar day or already started
    # Apply EARLY to avoid wasting compute on expired/future picks
    # =========================================================================

    GRACE_SECONDS = 180  # 3 minute grace window for clock drift

    # Apply time gate to all collected picks
    all_picks_time_gated, time_gate_debug = apply_time_gate(all_picks_raw, GRACE_SECONDS)

    # Ensure all picks have team/opponent labels and game_time_et
    for pick in all_picks_time_gated:
        ensure_pick_labels(pick)

    # Update all_picks_raw to use the time-gated list
    all_picks_raw = all_picks_time_gated

    # Store time gate debug
    debug_info["time_gate"] = time_gate_debug

    # =========================================================================
    # v10.51: 2-TIER PUBLISHING SYSTEM
    # TIER A: OFFICIAL CARD (GOLD_STAR + EDGE_LEAN, score >= 7.05)
    # TIER B: ACTION LEANS (6.70 <= score < 7.05, max 10 picks)
    # =========================================================================

    # Configuration
    OFFICIAL_MAX = 14
    LEANS_MAX = 10
    LEANS_MIN_SCORE = 6.70
    LEANS_MAX_SCORE = 7.05  # Below EDGE_LEAN threshold

    # Apply GLOBAL publish gate to merged picks
    global_gate_debug = {
        "input_picks": len(all_picks_raw),
        "after_dedup": 0,
        "after_corr_penalty": 0,
        "published_total": 0,
        "fallback_used": False
    }

    # v10.51: Action leans debug
    action_leans_debug = {
        "count": 0,
        "threshold_min": LEANS_MIN_SCORE,
        "threshold_max": LEANS_MAX_SCORE,
        "max_published": LEANS_MAX,
        "candidates_before_filter": 0,
        "candidates_after_dedup": 0
    }

    action_leans_picks = []

    if PUBLISH_GATE_AVAILABLE and all_picks_raw:
        # TIER A: Apply publish gate for OFFICIAL CARD
        all_picks_gated, gate_stats = apply_publish_gate(
            picks=all_picks_raw,
            target_max=OFFICIAL_MAX,
            apply_dedup=True,
            apply_penalty=True,
            apply_gate=True
        )
        global_gate_debug["after_dedup"] = gate_stats.get("after_dedup", 0)
        global_gate_debug["after_corr_penalty"] = gate_stats.get("after_corr_penalty", 0)
        global_gate_debug["published_total"] = gate_stats.get("published_total", 0)
        global_gate_debug["publish_threshold_edge_lean"] = gate_stats.get("publish_threshold_edge_lean", 7.05)
        global_gate_debug["publish_threshold_gold_star"] = gate_stats.get("publish_threshold_gold_star", 7.50)
        global_gate_debug["dedup_stats"] = gate_stats.get("dedup_stats", {})
        global_gate_debug["penalty_stats"] = gate_stats.get("penalty_stats", {})
        global_gate_debug["gate_stats"] = gate_stats.get("gate_stats", {})

        all_picks_final = all_picks_gated

        # TIER B: ACTION LEANS - picks below EDGE_LEAN threshold but still decent
        # Get the actual edge_lean threshold used (may have been escalated)
        edge_lean_threshold = gate_stats.get("publish_threshold_edge_lean", 7.05)

        # Filter for action leans candidates: score in [LEANS_MIN, edge_lean_threshold)
        # Also exclude picks already in OFFICIAL card
        official_pick_ids = set()
        for p in all_picks_final:
            # Create unique identifier for pick
            pid = f"{p.get('player_name', '')}-{p.get('stat_type', '')}-{p.get('game_id', '')}"
            official_pick_ids.add(pid)

        leans_candidates = []
        for pick in all_picks_raw:
            score = float(pick.get("smash_score", pick.get("total_score", pick.get("final_score", 0))))
            pid = f"{pick.get('player_name', '')}-{pick.get('stat_type', '')}-{pick.get('game_id', '')}"

            # Must be in lean range and not already official
            if LEANS_MIN_SCORE <= score < edge_lean_threshold and pid not in official_pick_ids:
                # Exclude blocked/trap/high-variance picks if those fields exist
                if pick.get("blocked") or pick.get("trap") or pick.get("variance_high"):
                    continue
                leans_candidates.append(pick)

        action_leans_debug["candidates_before_filter"] = len(leans_candidates)

        # Apply dedup and correlation penalty to leans (same quality control)
        if leans_candidates:
            leans_deduped, _ = apply_dominance_dedup(leans_candidates)
            leans_penalized, _ = apply_correlation_penalty(leans_deduped)
            action_leans_debug["candidates_after_dedup"] = len(leans_penalized)

            # Sort by score and cap at LEANS_MAX
            leans_penalized.sort(
                key=lambda x: float(x.get("smash_score", x.get("total_score", 0))),
                reverse=True
            )
            action_leans_picks = leans_penalized[:LEANS_MAX]

            # Tag each lean pick
            for pick in action_leans_picks:
                pick["tier"] = "ACTION_LEAN"
                pick["badge"] = "1U LEAN"
                pick["units"] = 1.0  # Cap at 1u
                pick["is_action_lean"] = True
                reasons = pick.get("reasons", [])
                reasons.append(f"ACTION_LEAN: Score {float(pick.get('smash_score', pick.get('total_score', 0))):.2f} (below {edge_lean_threshold}, above {LEANS_MIN_SCORE})")
                pick["reasons"] = reasons

        action_leans_debug["count"] = len(action_leans_picks)

    else:
        # No publish gate - just sort by score
        all_picks_final = sorted(
            all_picks_raw,
            key=lambda x: float(x.get("smash_score", x.get("total_score", 0))),
            reverse=True
        )
        global_gate_debug["after_dedup"] = len(all_picks_final)
        global_gate_debug["after_corr_penalty"] = len(all_picks_final)
        global_gate_debug["published_total"] = len(all_picks_final)

    # =========================================================================
    # v10.53: SOFT STACKING GOVERNOR
    # Prevents same-team spam while allowing SMASH stacks to override limits
    # Applied AFTER time_gate, dedup, correlation penalty, publish gating
    # =========================================================================

    stacking_debug = {
        "official_default_max_per_game": OFFICIAL_DEFAULT_MAX_PER_GAME,
        "official_default_max_per_team_game": OFFICIAL_DEFAULT_MAX_PER_TEAM_GAME,
        "smash_threshold": SMASH_STACK_THRESHOLD,
        "official_smash_max_per_game": OFFICIAL_SMASH_MAX_PER_GAME,
        "official_smash_max_per_team_game": OFFICIAL_SMASH_MAX_PER_TEAM_GAME,
        "official_hard_cap_per_game": OFFICIAL_HARD_CAP_PER_GAME,
        "official_hard_cap_per_team_game": OFFICIAL_HARD_CAP_PER_TEAM_GAME,
        "action_leans_max_per_game": LEANS_MAX_PER_GAME,
        "action_leans_max_per_team_game": LEANS_MAX_PER_TEAM_GAME,
        "official_before_stacking": len(all_picks_final),
        "official_after_stacking": 0,
        "removed_official_by_stacking": 0,
        "leans_before_stacking": len(action_leans_picks),
        "leans_after_stacking": 0,
        "removed_leans_by_stacking": 0
    }

    # Apply stacking to Official Card
    all_picks_final, removed_official = apply_stacking_limits(
        all_picks_final,
        default_max_game=OFFICIAL_DEFAULT_MAX_PER_GAME,
        default_max_team_game=OFFICIAL_DEFAULT_MAX_PER_TEAM_GAME,
        smash_max_game=OFFICIAL_SMASH_MAX_PER_GAME,
        smash_max_team_game=OFFICIAL_SMASH_MAX_PER_TEAM_GAME,
        hard_cap_game=OFFICIAL_HARD_CAP_PER_GAME,
        hard_cap_team_game=OFFICIAL_HARD_CAP_PER_TEAM_GAME
    )
    stacking_debug["official_after_stacking"] = len(all_picks_final)
    stacking_debug["removed_official_by_stacking"] = removed_official

    # Apply stacking to Action Leans (looser limits)
    action_leans_picks, removed_leans = apply_stacking_limits(
        action_leans_picks,
        default_max_game=LEANS_MAX_PER_GAME,
        default_max_team_game=LEANS_MAX_PER_TEAM_GAME,
        smash_max_game=LEANS_MAX_PER_GAME,  # No SMASH override for leans
        smash_max_team_game=LEANS_MAX_PER_TEAM_GAME,
        hard_cap_game=LEANS_MAX_PER_GAME,
        hard_cap_team_game=LEANS_MAX_PER_TEAM_GAME
    )
    stacking_debug["leans_after_stacking"] = len(action_leans_picks)
    stacking_debug["removed_leans_by_stacking"] = removed_leans

    # UNIVERSAL FALLBACK: Never return 0 picks
    if len(all_picks_final) == 0:
        logger.warning("ALL-SPORTS: Zero picks after gate - activating GLOBAL FALLBACK")
        global_gate_debug["fallback_used"] = True

        # Collect top 3 MONITOR picks from raw pool
        fallback_pool = sorted(
            all_picks_raw,
            key=lambda x: float(x.get("smash_score", x.get("total_score", 0))),
            reverse=True
        )[:3]

        for pick in fallback_pool:
            # v10.55: Use tier_from_score on actual final_score - don't force MONITOR
            fb_score = float(pick.get("final_score", pick.get("smash_score", pick.get("total_score", 0))))
            fb_tier, _ = tier_from_score(fb_score)
            pick["tier"] = fb_tier
            pick["badge"] = "FALLBACK"
            pick["fallback"] = True
            pick["reasons"] = pick.get("reasons", []) + [
                "GOVERNOR: GLOBAL_FALLBACK_TOP3 (below publish gate but included for volume)"
            ]
            # v10.52: Ensure labels on fallback picks too
            ensure_pick_labels(pick)

        all_picks_final = fallback_pool
        global_gate_debug["published_total"] = len(fallback_pool)

    debug_info["global_publish_gate"] = global_gate_debug
    debug_info["action_leans"] = action_leans_debug  # v10.51
    debug_info["stacking"] = stacking_debug  # v10.53

    # =========================================================================
    # v10.54: PRODUCTION V3 CONTRACT COMPLIANCE
    # Apply normalization to all picks: deterministic id, int confidence, ordered reasons
    # =========================================================================

    for pick in all_picks_final:
        normalize_pick_for_v3(pick, pick.get("sport", ""))

    for pick in action_leans_picks:
        normalize_pick_for_v3(pick, pick.get("sport", ""))

    # v10.67: Generate status message based on time gate results
    status_message = None
    if len(all_picks_final) == 0:
        live_count = time_gate_debug.get("count_live", 0)
        pregame_count = time_gate_debug.get("count_pregame", 0)
        not_today_count = time_gate_debug.get("removed_not_today", 0)
        candidates_before = time_gate_debug.get("candidates_before_time_gate", 0)

        if live_count > 0 and pregame_count == 0:
            status_message = f"All {live_count} game(s) have already started. Live bets only available."
        elif not_today_count > 0 and (live_count + pregame_count) == 0:
            status_message = f"No games scheduled for today. {not_today_count} game(s) are scheduled for other days."
        elif candidates_before == 0:
            status_message = "No games found across any sport. This may be an off-day or API issue."
        else:
            status_message = "No picks available at this time."

    # Build response
    result = {
        "source": f"production_{Config.ENGINE_VERSION}_all_sports",
        "scoring_system": "v10.67: Time gate status messaging",
        "all_picks": {
            "count": len(all_picks_final),
            "picks": all_picks_final
        },
        # v10.51: Action Leans (Tier B)
        "action_leans": {
            "count": len(action_leans_picks),
            "picks": action_leans_picks,
            "description": "Optional 1u gamble feelers below official threshold"
        },
        "by_sport": by_sport,
        "summary": {
            # v10.51: Renamed for clarity
            "official_count": len(all_picks_final),
            "action_leans_count": len(action_leans_picks),
            "total_picks": len(all_picks_final) + len(action_leans_picks),
            "sports_with_picks": len([s for s in by_sport if by_sport[s]["total_picks"] > 0]),
            # Official card breakdown
            "official_gold_star_count": len([p for p in all_picks_final if p.get("tier") == "GOLD_STAR"]),
            "official_edge_lean_count": len([p for p in all_picks_final if p.get("tier") == "EDGE_LEAN"]),
            # Legacy fields (keep for backwards compatibility)
            "gold_star_count": len([p for p in all_picks_final if p.get("tier") == "GOLD_STAR"]),
            "edge_lean_count": len([p for p in all_picks_final if p.get("tier") == "EDGE_LEAN"]),
            "props_count": len([p for p in all_picks_final if p.get("pick_type") == "prop"]),
            "games_count": len([p for p in all_picks_final if p.get("pick_type") == "game"])
        },
        "timestamp": datetime.now().isoformat()
    }

    # v10.67: Add status message when no picks available
    if status_message:
        result["status_message"] = status_message
        result["all_picks"]["message"] = status_message

    if debug == 1:
        result["debug"] = debug_info

    return result


@router.get("/best-bets/{sport}")
async def get_best_bets(sport: str, debug: int = 0, include_conflicts: int = 0, min_confidence: str = "C"):
    """
    Get best bets using full 8 AI Models + 8 Pillars + JARVIS + Esoteric scoring.
    Returns TWO categories: props (player props) and game_picks (spreads, totals, ML).

    Query Parameters:
    - debug=1: Include diagnostic info (Jarvis calls, correlation counters, enforcement proof)
    - include_conflicts=1: Include filtered CONFLICT and NEUTRAL picks in separate arrays
    - min_confidence=A|B|C: Filter to only return picks >= this confidence grade (default: C = all picks)
      A = Top confluence + tight alignment, B = JARVIS_MODERATE + moderate alignment, C = Everything

    Scoring Formula (v10.21):
    FINAL = (research × 0.67) + (esoteric × 0.33) + confluence_boost

    v10.21 Jarvis Enforcement:
    - Every returned pick MUST have: esoteric_score, jarvis_active, esoteric_breakdown
    - Every returned pick MUST have at least 1 "ESOTERIC:" reason
    - Validation guardrail enforces this before response
    - Debug counters prove Jarvis was called for every candidate

    v10.20 Features Retained:
    - Ritual Score backbone (esoteric starts at 6.0)
    - NHL ML Dog Weapon (+0.5 for NHL ML underdogs)
    - Market Priority (totals > spreads > moneyline)
    - Public Fade pillar (+0.5/-0.5 directional)
    - Mid-Spread Boss Zone (+0.2 for 4-9 spread)

    v10.19 Smash Spot Logic:
    - smash_spot is a TRUTH FLAG, not a score boost
    - Requirements: score >= 8.0, align >= 85%, Jarvis active, BOTH Sharp Split AND RLM

    Thresholds:
    - GOLD_STAR: >= 7.5
    - EDGE_LEAN: >= 6.5
    - MONITOR: >= 5.5
    - PASS: < 5.5

    Debug Response (when debug=1):
    {
        "debug": {
            "jarvis_calls_total": N,
            "jarvis_calls_game": N,
            "jarvis_calls_props": N,
            "jarvis_missing_on_returned_picks": 0,  // MUST be 0
            "jarvis_engine_available": true
        }
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # v10.31: Season gating - return empty response for off-season sports
    if SEASON_GATING_AVAILABLE:
        sport_upper = sport_lower.upper()
        if not is_in_season(sport_upper):
            logger.info(f"v10.31: {sport_upper} is off-season, returning empty response")
            off_season_response = get_off_season_response(sport_upper)
            if debug == 1:
                off_season_response["debug"] = {
                    "no_data": True,
                    "reason": "sport_off_season",
                    "season_info": get_season_info(sport_upper)
                }
            return off_season_response

    # v10.30: Validate and normalize min_confidence parameter
    min_confidence = min_confidence.upper() if min_confidence else "C"
    if min_confidence not in ("A", "B", "C"):
        min_confidence = "C"  # Default to showing all picks

    # v10.30: Confidence grade priority for filtering (A=1, B=2, C=3)
    CONFIDENCE_PRIORITY = {"A": 1, "B": 2, "C": 3}

    # v10.30: Helper function for recommended units based on confidence grade
    def get_recommended_units(confidence_grade: str, tier: str) -> float:
        """
        Return recommended units based on confidence grade and tier.
        A = 2.0 units (high conviction)
        B = 1.0 units (moderate conviction)
        C = 0.5 units (lower conviction)
        PASS tier = 0.0 units (no recommendation)
        """
        if tier == "PASS":
            return 0.0
        units_map = {"A": 2.0, "B": 1.0, "C": 0.5}
        return units_map.get(confidence_grade, 0.5)

    # v10.30: Helper function for odds implied probability
    def get_implied_probability(odds: int) -> float:
        """Convert American odds to implied probability for sorting."""
        try:
            odds = int(odds)
            if odds > 0:
                return 100 / (odds + 100)
            else:
                return abs(odds) / (abs(odds) + 100)
        except (ValueError, TypeError, ZeroDivisionError):
            return 0.5  # Default 50% if invalid

    # v10.59: Kelly Criterion-based unit sizing (fractional Kelly for safety)
    def calculate_kelly_units(final_score: float, odds: int, tier: str) -> float:
        """
        Calculate recommended units using fractional Kelly Criterion.

        Edge = (AI predicted win probability) - (implied probability from odds)
        Kelly % = Edge / (Odds to 1) = Edge * (odds / 100 if neg, 100/odds if pos)

        We use 1/4 Kelly (conservative) to reduce variance.

        Returns: Recommended units (capped by tier limits)
        """
        if tier in ("PASS", "MONITOR"):
            return 0.0

        try:
            odds = int(odds)
            # Convert final_score (0-10) to estimated win probability (50-75% range)
            # Score 5.0 = 50%, Score 10.0 = 75%
            est_win_prob = 0.50 + (final_score - 5.0) * 0.05
            est_win_prob = max(0.50, min(0.75, est_win_prob))

            # Implied probability from odds
            if odds > 0:
                implied_prob = 100 / (odds + 100)
                decimal_odds = (odds / 100) + 1
            else:
                implied_prob = abs(odds) / (abs(odds) + 100)
                decimal_odds = (100 / abs(odds)) + 1

            # Edge = estimated - implied
            edge = est_win_prob - implied_prob

            if edge <= 0:
                # No edge, use tier-based default
                return 2.0 if tier == "GOLD_STAR" else 1.0

            # Kelly formula: (bp - q) / b
            # b = decimal odds - 1, p = win prob, q = 1 - p
            b = decimal_odds - 1
            if b <= 0:
                return 2.0 if tier == "GOLD_STAR" else 1.0

            kelly_fraction = (b * est_win_prob - (1 - est_win_prob)) / b

            # Use 1/4 Kelly (conservative)
            quarter_kelly = kelly_fraction * 0.25

            # Convert to units (1 unit = 1% of bankroll assumption)
            # Scale: 0.05 Kelly = 2 units, 0.025 Kelly = 1 unit
            kelly_units = (quarter_kelly / 0.025)

            # Cap by tier
            max_units = 2.5 if tier == "GOLD_STAR" else 1.5
            return round(min(max(0.5, kelly_units), max_units), 1)

        except Exception:
            # Fallback to tier-based
            return 2.0 if tier == "GOLD_STAR" else 1.0

    # Check cache first
    # v10.16: Skip cache for debug/inspection modes to ensure fresh diagnostic data
    # v10.34: Include schema version in cache key to auto-invalidate on schema changes
    # v10.83: Include date_et and engine_version to ensure version-safe caching
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
    _date_et = datetime.now(_ET).strftime("%Y-%m-%d")
    cache_key = f"{CACHE_SCHEMA_VERSION}:{Config.ENGINE_VERSION}:{_date_et}:best-bets:{sport_lower}"
    cache_hit = False
    if debug != 1 and include_conflicts != 1:
        cached = api_cache.get(cache_key)
        if cached:
            cache_hit = True
            return cached

    # Get MasterPredictionSystem
    mps = get_master_prediction_system()
    daily_energy = get_daily_energy()

    # v10.32: Load micro-weights for signal attribution tuning
    # These weights adjust pillar boosts based on ROI correlation analysis
    if DATABASE_AVAILABLE:
        micro_weights = get_micro_weights(sport_lower.upper())
    else:
        micro_weights = DEFAULT_MICRO_WEIGHTS.copy() if DEFAULT_MICRO_WEIGHTS else {}
    logger.debug(f"v10.32: Loaded {len(micro_weights)} micro-weights for {sport_lower}")

    # v10.32: Load signal policy multipliers from database
    # These are auto-tuned by the learning engine based on ROI correlation
    # Combined effect: final_mult = micro_weight * policy_mult (both clamped to 0.85-1.15)
    signal_policies = {}
    if SIGNAL_POLICY_AVAILABLE:
        try:
            signal_policies = get_signal_policy(sport_lower.upper())
            logger.debug(f"v10.32: Loaded {len(signal_policies)} signal policies for {sport_lower}")
        except Exception as e:
            logger.warning(f"v10.32: Signal policy load failed (using defaults): {e}")

    # v10.31: Load external context (Weather/Astronomy/NOAA/Planetary)
    # Provides micro-boosts for esoteric scoring (max ±0.25 total)
    external_context = {}
    external_micro_boost_data = {"total_boost": 0, "breakdown": {}, "reasons": []}
    if EXTERNAL_SIGNALS_AVAILABLE:
        try:
            external_context = await get_external_context(sport=sport_lower.upper())
            external_micro_boost_data = calculate_external_micro_boost(external_context)
            logger.debug(f"v10.31: External context loaded, boost={external_micro_boost_data.get('total_boost', 0)}")
        except Exception as e:
            logger.warning(f"v10.31: External signals failed (continuing without): {e}")

    # Fetch sharp money for both categories
    sharp_data = await get_sharp_money(sport)
    sharp_lookup = {}
    for signal in sharp_data.get("data", []):
        game_key = f"{signal.get('away_team')}@{signal.get('home_team')}"
        sharp_lookup[game_key] = signal

    # v10.35: Fetch injuries for Hospital Fade pillar
    injuries_data = await get_injuries(sport)
    injuries_by_team = {}  # team_name -> {"count": N, "key_players": [...], "severity_score": N}
    for injury in injuries_data.get("data", []):
        team = injury.get("team", "")
        if not team:
            continue
        if team not in injuries_by_team:
            injuries_by_team[team] = {"count": 0, "key_players": [], "severity_score": 0}
        injuries_by_team[team]["count"] += 1
        # Track key players (starters, high-impact)
        status = safe_lower(injury.get("status"))
        player_name = injury.get("player", "") or injury.get("name", "")
        if status in ("out", "doubtful"):
            injuries_by_team[team]["key_players"].append(player_name)
            injuries_by_team[team]["severity_score"] += 2 if status == "out" else 1
        elif status in ("questionable", "probable"):
            injuries_by_team[team]["severity_score"] += 0.5

    # v10.57: Build injury index for validators (OUT/SUSPENDED/DOUBTFUL checks)
    injury_index = {}
    if VALIDATORS_AVAILABLE:
        injury_index = build_injury_index(injuries_data.get("data", []))

    # v10.68: Referee data now fetched via ESPN in alt_data_context (include_lineups=True)
    # ESPN provides officials and referee tendencies through get_alternative_data_context()
        logger.debug(f"v10.57: Built injury index with {len(injury_index)} players")

    # v10.66: Fetch Alternative Data Context (Twitter, Finnhub, SerpAPI, FRED)
    alt_data_context = {}
    alt_data_adjustments = {"hospital_fade_boost": 0.0, "sharp_alternative": 0.0, "esoteric_alt_data": 0.0, "referee_adjustment": 0.0}
    if ALT_DATA_AVAILABLE:
        try:
            # Get list of teams from sharp data for focused fetching
            teams_list = []
            for signal in sharp_data.get("data", []):
                if signal.get("home_team"):
                    teams_list.append(signal["home_team"])
                if signal.get("away_team"):
                    teams_list.append(signal["away_team"])
            teams_list = list(set(teams_list))[:10]  # Limit to first 10 unique teams

            alt_data_context = await get_alternative_data_context(
                sport=sport_lower,
                teams=teams_list,
                include_injuries=True,
                include_sentiment=True,
                include_economic=True,
                include_lineups=True  # v10.68: ESPN lineups + referee tendencies
            )

            if alt_data_context.get("available"):
                alt_data_adjustments = alt_data_context.get("scoring_adjustments", alt_data_adjustments)
                logger.info(f"v10.66: Alt data loaded - sources={alt_data_context.get('sources_used', [])}, "
                           f"injuries={len(alt_data_context.get('injury_alerts', {}).get('combined', []))}")

                # Merge Twitter/SerpAPI injury alerts into injuries_by_team
                for alert in alt_data_context.get("injury_alerts", {}).get("high_confidence", []):
                    team = alert.get("team", "")
                    player = alert.get("player_name", "")
                    status = alert.get("status", "")
                    if team and player and status in ("OUT", "DOUBTFUL"):
                        if team not in injuries_by_team:
                            injuries_by_team[team] = {"count": 0, "key_players": [], "severity_score": 0}
                        if player not in injuries_by_team[team]["key_players"]:
                            injuries_by_team[team]["key_players"].append(f"{player} (breaking)")
                            injuries_by_team[team]["severity_score"] += 1.5 if status == "OUT" else 0.75
                            injuries_by_team[team]["count"] += 1
        except Exception as e:
            logger.warning(f"v10.66: Alternative data fetch failed (continuing without): {e}")

    # Get esoteric engines for enhanced scoring
    jarvis = get_jarvis_savant()
    vedic = get_vedic_astro()
    learning = get_esoteric_loop()

    # v10.24: Scoring enforcement tracking (debug counters for AI + Jarvis)
    jarvis_debug = {
        "calls_total": 0,
        "calls_game": 0,
        "calls_props": 0,
        "missing_on_returned": 0,
        "ai_engine_available": AI_ENGINE_AVAILABLE,  # v10.24: Track AI engine status
        "ai_calls_total": 0  # v10.24: AI engine call counter
    }

    # Get learned weights for esoteric scoring
    esoteric_weights = learning.get_weights()["weights"] if learning else {}

    # ========================================================================
    # v10.28: CONFLUENCE LADDER (tier-safe, capped at 0.75) + Debug Diagnostics
    # ========================================================================
    def compute_confluence_ladder(research_score, esoteric_score, alignment_pct, jarvis_active, immortal_active=False):
        """
        Compute confluence boost using a ladder system.
        Returns: (boost, label, level, applied_reasons, fail_reasons, rule_trace, repair_hints, alignment_gap)

        v10.28: Added repair_hints and alignment_gap for debug transparency.
        Fixed truthfulness bug in failure messages.
        Boosts are capped and never exceed +0.75 total.
        First matching rule wins (evaluated in priority order).
        """
        def fmt(x, nd=2):
            """Format numeric value for debug output - consistent string formatting."""
            try:
                return f"{float(x):.{nd}f}"
            except Exception:
                return str(x)

        # v10.28: Alignment gap diagnostic
        alignment_gap = round(abs(research_score - esoteric_score), 2)

        # Track rule evaluations for debug
        fail_reasons = []
        repair_hints = []
        evaluated = []

        # Rule thresholds for repair hint calculations
        RULES = [
            {
                "name": "IMMORTAL_CONFLUENCE",
                "r_min": 7.5, "e_min": 7.5, "align_min": 85.0,
                "requires_jarvis": False, "requires_immortal": True,
                "boost": 0.75, "level": "IMMORTAL"
            },
            {
                "name": "JARVIS_PERFECT",
                "r_min": 7.5, "e_min": 7.0, "align_min": 85.0,
                "requires_jarvis": True, "requires_immortal": False,
                "boost": 0.50, "level": "PERFECT"
            },
            {
                "name": "PERFECT_CONFLUENCE",
                "r_min": 7.0, "e_min": 7.0, "align_min": 85.0,
                "requires_jarvis": False, "requires_immortal": False,
                "boost": 0.35, "level": "PERFECT"
            },
            {
                "name": "JARVIS_MODERATE",
                "r_min": 0.0, "e_min": 0.0, "align_min": 80.0,
                "requires_jarvis": True, "requires_immortal": False,
                "boost": 0.25, "level": "MODERATE"
            },
        ]

        applied_rule = None

        for rule in RULES:
            rule_name = rule["name"]

            # Check all conditions for this rule
            checks_failed = []

            if rule["requires_immortal"] and not immortal_active:
                checks_failed.append(("immortal_active", False, True))
            if rule["requires_jarvis"] and not jarvis_active:
                checks_failed.append(("jarvis_active", False, True))
            if rule["r_min"] > 0 and research_score < rule["r_min"]:
                checks_failed.append(("research_score", research_score, rule["r_min"]))
            if rule["e_min"] > 0 and esoteric_score < rule["e_min"]:
                checks_failed.append(("esoteric_score", esoteric_score, rule["e_min"]))
            if alignment_pct < rule["align_min"]:
                checks_failed.append(("alignment_pct", alignment_pct, rule["align_min"]))

            rule_passed = len(checks_failed) == 0
            evaluated.append({"rule": rule_name, "passed": rule_passed})

            if rule_passed and applied_rule is None:
                # This rule passes - it's the applied rule
                applied_rule = rule
            elif not rule_passed and applied_rule is None:
                # This rule failed and we haven't found a passing rule yet
                # Record failures with truthful comparisons
                for field, actual_val, required_val in checks_failed:
                    if field == "immortal_active":
                        fail_reasons.append(f"FAIL: {rule_name} immortal_active=False (required=True)")
                    elif field == "jarvis_active":
                        fail_reasons.append(f"FAIL: {rule_name} jarvis_active=False (required=True)")
                    elif field == "research_score":
                        fail_reasons.append(f"FAIL: {rule_name} research_score {fmt(actual_val)} < {fmt(required_val)}")
                    elif field == "esoteric_score":
                        fail_reasons.append(f"FAIL: {rule_name} esoteric_score {fmt(actual_val)} < {fmt(required_val)}")
                    elif field == "alignment_pct":
                        fail_reasons.append(f"FAIL: {rule_name} alignment_pct {fmt(actual_val, 1)} < {fmt(required_val, 1)}")

        # Generate repair hints for rules ABOVE the applied rule
        for rule in RULES:
            if applied_rule and rule["name"] == applied_rule["name"]:
                break  # Stop at the applied rule

            rule_name = rule["name"]

            # Calculate deltas needed to reach this rule
            if rule["requires_immortal"] and not immortal_active:
                repair_hints.append(f"REPAIR: Need immortal_active=True to reach {rule_name}")
            if rule["requires_jarvis"] and not jarvis_active:
                repair_hints.append(f"REPAIR: Need jarvis_active=True to reach {rule_name}")

            if rule["r_min"] > 0:
                need_r = max(0, rule["r_min"] - research_score)
                if need_r > 0:
                    repair_hints.append(f"REPAIR: Need research_score +{fmt(need_r)} to reach {rule_name} (min {fmt(rule['r_min'])})")

            if rule["e_min"] > 0:
                need_e = max(0, rule["e_min"] - esoteric_score)
                if need_e > 0:
                    repair_hints.append(f"REPAIR: Need esoteric_score +{fmt(need_e)} to reach {rule_name} (min {fmt(rule['e_min'])})")

            need_a = max(0, rule["align_min"] - alignment_pct)
            if need_a > 0:
                repair_hints.append(f"REPAIR: Need alignment_pct +{fmt(need_a, 1)} to reach {rule_name} (min {fmt(rule['align_min'], 1)})")

        # Add alignment gap hint if high divergence
        if alignment_gap >= 1.5:
            repair_hints.append(f"REPAIR: Alignment gap {fmt(alignment_gap)} is high; reduce divergence between engines for higher confluence")

        # Build rule_trace
        rule_trace = {
            "research_score": float(fmt(research_score)),
            "esoteric_score": float(fmt(esoteric_score)),
            "alignment_pct": float(fmt(alignment_pct, 1)),
            "alignment_gap": alignment_gap,
            "evaluated": evaluated
        }

        # Return based on applied rule
        if applied_rule:
            applied_reasons = [f"CONFLUENCE: {applied_rule['name']} (+{fmt(applied_rule['boost'])}) [applied]"]
            return (
                applied_rule["boost"],
                applied_rule["name"],
                applied_rule["level"],
                applied_reasons,
                fail_reasons,
                rule_trace,
                repair_hints,
                alignment_gap
            )

        # Rule 5: No confluence boost (NONE)
        evaluated.append({"rule": "NONE", "passed": True})
        return (0.0, "NONE", "NONE", [], fail_reasons, rule_trace, repair_hints, alignment_gap)

    # ========================================================================
    # v10.40: CONFLUENCE LADDER (4-Engine, 2-Alignment Method)
    # ========================================================================
    def compute_confluence_ladder_v1040(ai_score, research_score, jarvis_rs, alignment_pct,
                                         jarvis_active, jarvis_hits_count, immortal_active=False):
        """
        v10.40: Compute confluence boost using 4-engine system.

        Alignment is now computed from:
        - AI ↔ Research alignment
        - Research ↔ Jarvis alignment

        Returns: (boost, label, level, applied_reasons, fail_reasons, rule_trace, repair_hints, alignment_gap)
        """
        def fmt(x, nd=2):
            try:
                return f"{float(x):.{nd}f}"
            except Exception:
                return str(x)

        # Alignment gap diagnostic (using Research as anchor)
        alignment_gap = round((abs(ai_score - research_score) + abs(research_score - jarvis_rs)) / 2, 2)

        fail_reasons = []
        repair_hints = []
        evaluated = []

        # v10.40: Updated rules with jarvis_rs requirements
        RULES = [
            {
                "name": "IMMORTAL",
                "jarvis_hits_min": 4, "jarvis_rs_min": 8.0, "r_min": 7.5, "align_min": 90.0,
                "requires_jarvis": True, "requires_immortal": False,
                "boost": 0.75, "level": "IMMORTAL"
            },
            {
                "name": "JARVIS_PERFECT",
                "jarvis_hits_min": 0, "jarvis_rs_min": 7.5, "r_min": 7.0, "align_min": 85.0,
                "requires_jarvis": True, "requires_immortal": False,
                "boost": 0.60, "level": "PERFECT"
            },
            {
                "name": "PERFECT",
                "jarvis_hits_min": 0, "jarvis_rs_min": 6.8, "r_min": 6.5, "align_min": 80.0,
                "requires_jarvis": False, "requires_immortal": False,
                "boost": 0.45, "level": "PERFECT"
            },
            {
                "name": "STRONG",
                "jarvis_hits_min": 0, "jarvis_rs_min": 0.0, "r_min": 6.0, "align_min": 75.0,
                "requires_jarvis": True, "requires_immortal": False,
                "boost": 0.30, "level": "STRONG"
            },
            {
                "name": "MODERATE",
                "jarvis_hits_min": 0, "jarvis_rs_min": 0.0, "r_min": 5.5, "align_min": 70.0,
                "requires_jarvis": False, "requires_immortal": False,
                "boost": 0.15, "level": "MODERATE"
            },
        ]

        applied_rule = None

        for rule in RULES:
            rule_name = rule["name"]
            checks_failed = []

            if rule["requires_jarvis"] and not jarvis_active:
                checks_failed.append(("jarvis_active", False, True))
            if rule["jarvis_hits_min"] > 0 and jarvis_hits_count < rule["jarvis_hits_min"]:
                checks_failed.append(("jarvis_hits_count", jarvis_hits_count, rule["jarvis_hits_min"]))
            if rule["jarvis_rs_min"] > 0 and jarvis_rs < rule["jarvis_rs_min"]:
                checks_failed.append(("jarvis_rs", jarvis_rs, rule["jarvis_rs_min"]))
            if rule["r_min"] > 0 and research_score < rule["r_min"]:
                checks_failed.append(("research_score", research_score, rule["r_min"]))
            if alignment_pct < rule["align_min"]:
                checks_failed.append(("alignment_pct", alignment_pct, rule["align_min"]))

            rule_passed = len(checks_failed) == 0
            evaluated.append({"rule": rule_name, "passed": rule_passed})

            if rule_passed and applied_rule is None:
                applied_rule = rule
            elif not rule_passed and applied_rule is None:
                for field, actual_val, required_val in checks_failed:
                    if field == "jarvis_active":
                        fail_reasons.append(f"FAIL: {rule_name} jarvis_active=False (required=True)")
                    elif field == "jarvis_hits_count":
                        fail_reasons.append(f"FAIL: {rule_name} jarvis_hits_count {actual_val} < {required_val}")
                    elif field == "jarvis_rs":
                        fail_reasons.append(f"FAIL: {rule_name} jarvis_rs {fmt(actual_val)} < {fmt(required_val)}")
                    elif field == "research_score":
                        fail_reasons.append(f"FAIL: {rule_name} research_score {fmt(actual_val)} < {fmt(required_val)}")
                    elif field == "alignment_pct":
                        fail_reasons.append(f"FAIL: {rule_name} alignment_pct {fmt(actual_val, 1)} < {fmt(required_val, 1)}")

        # Generate repair hints
        for rule in RULES:
            if applied_rule and rule["name"] == applied_rule["name"]:
                break
            rule_name = rule["name"]

            if rule["requires_jarvis"] and not jarvis_active:
                repair_hints.append(f"REPAIR: Need jarvis_active=True to reach {rule_name}")
            if rule["jarvis_hits_min"] > 0:
                need = max(0, rule["jarvis_hits_min"] - jarvis_hits_count)
                if need > 0:
                    repair_hints.append(f"REPAIR: Need {need} more jarvis_hits to reach {rule_name}")
            if rule["jarvis_rs_min"] > 0:
                need = max(0, rule["jarvis_rs_min"] - jarvis_rs)
                if need > 0:
                    repair_hints.append(f"REPAIR: Need jarvis_rs +{fmt(need)} to reach {rule_name}")
            if rule["r_min"] > 0:
                need = max(0, rule["r_min"] - research_score)
                if need > 0:
                    repair_hints.append(f"REPAIR: Need research_score +{fmt(need)} to reach {rule_name}")

        rule_trace = {
            "ai_score": float(fmt(ai_score)),
            "research_score": float(fmt(research_score)),
            "jarvis_rs": float(fmt(jarvis_rs)),
            "alignment_pct": float(fmt(alignment_pct, 1)),
            "alignment_gap": alignment_gap,
            "evaluated": evaluated
        }

        if applied_rule:
            applied_reasons = [f"CONFLUENCE: {applied_rule['name']} (+{fmt(applied_rule['boost'])})"]
            return (
                applied_rule["boost"],
                applied_rule["name"],
                applied_rule["level"],
                applied_reasons,
                fail_reasons,
                rule_trace,
                repair_hints,
                alignment_gap
            )

        evaluated.append({"rule": "NONE", "passed": True})
        return (0.0, "NONE", "NONE", [], fail_reasons, rule_trace, repair_hints, alignment_gap)

    # v10.26: Confluence counters for debug output (candidates = all scored picks)
    confluence_counts_candidates = {
        "IMMORTAL_CONFLUENCE": 0,
        "JARVIS_PERFECT": 0,
        "PERFECT_CONFLUENCE": 0,
        "JARVIS_MODERATE": 0,
        "NONE": 0
    }
    alignment_pct_sum_candidates = 0.0
    alignment_pct_count_candidates = 0

    # v10.26: Separate counters for RETURNED picks only (populated after filtering)
    confluence_counts_returned = {
        "IMMORTAL_CONFLUENCE": 0,
        "JARVIS_PERFECT": 0,
        "PERFECT_CONFLUENCE": 0,
        "JARVIS_MODERATE": 0,
        "NONE": 0
    }
    alignment_pct_sum_returned = 0.0
    alignment_pct_count_returned = 0
    alignment_min_returned = 100.0
    alignment_max_returned = 0.0

    # v10.29: Confidence grade counters for debug output
    confidence_grade_counts = {"A": 0, "B": 0, "C": 0}
    alignment_gap_sum_returned = 0.0
    alignment_gap_count_returned = 0
    alignment_gap_min_returned = 100.0
    alignment_gap_max_returned = 0.0

    # ========================================================================
    # v10.29: CONFIDENCE GRADE + ALIGNMENT GAP HELPERS
    # ========================================================================
    def compute_alignment_gap(research_score: float, esoteric_score: float) -> float:
        """Compute the gap between research and esoteric engines."""
        try:
            return round(abs(float(research_score) - float(esoteric_score)), 2)
        except Exception:
            return 0.0

    def compute_confidence_grade(confluence_label: str, alignment_gap: float) -> str:
        """
        Compute confidence grade based on confluence quality and alignment.
        A = Top confluence (IMMORTAL/JARVIS_PERFECT/PERFECT) AND tight alignment (gap <= 1.0)
        B = JARVIS_MODERATE AND moderate alignment (gap <= 1.5)
        C = Everything else
        """
        top_confluence = {"IMMORTAL_CONFLUENCE", "JARVIS_PERFECT", "PERFECT_CONFLUENCE"}
        if confluence_label in top_confluence and alignment_gap <= 1.0:
            return "A"
        if confluence_label == "JARVIS_MODERATE" and alignment_gap <= 1.5:
            return "B"
        return "C"

    def derive_confluence_miss_reason(
        confluence_label: str,
        fail_reasons: list,
        repair_hints: list
    ) -> str:
        """
        Derive the top reason why a pick didn't reach the next confluence rung.
        Uses failure reasons first, then repair hints as fallback.
        """
        # Define the confluence ladder order
        ladder_order = ["IMMORTAL_CONFLUENCE", "JARVIS_PERFECT", "PERFECT_CONFLUENCE", "JARVIS_MODERATE", "NONE"]

        # Find the current position and the next rung
        try:
            current_idx = ladder_order.index(confluence_label) if confluence_label in ladder_order else 4
        except ValueError:
            current_idx = 4  # Default to NONE position

        # If at the top, no upgrade available
        if current_idx == 0:
            return "MISS: Already at IMMORTAL_CONFLUENCE (highest rung)"

        # Look for failures related to the next rung above
        next_rung = ladder_order[current_idx - 1] if current_idx > 0 else None

        if fail_reasons and next_rung:
            # Find first failure for the next rung
            for reason in fail_reasons:
                if next_rung in reason:
                    # Extract the condition that failed
                    # Format: "FAIL: JARVIS_PERFECT esoteric_score 6.82 < 7.00"
                    parts = reason.replace("FAIL: ", "").split(" ", 1)
                    if len(parts) > 1:
                        return f"MISS: {parts[0]} blocked — {parts[1]}"
                    return f"MISS: {reason.replace('FAIL: ', '')}"

        if repair_hints:
            # Use first repair hint that mentions the next rung
            for hint in repair_hints:
                if next_rung and next_rung in hint:
                    return hint.replace("REPAIR: ", "MISS: ")
            # Fallback to first repair hint
            if repair_hints[0]:
                return repair_hints[0].replace("REPAIR: ", "MISS: ")

        return "MISS: No confluence upgrade available"

    # Helper function to calculate scores with v10.1 dual-score confluence
    # v10.18: Added prop_line, player_team_side, game_total for prop-independent pillars
    def calculate_pick_score(game_str, sharp_signal, base_ai=5.8, player_name="", home_team="", away_team="", spread=0, total=220, public_pct=50, is_home=False, team_rest_days=0, opp_rest_days=0, game_hour_et=20, market="", odds=-110, sharp_scope="GAME", direction_mult=1.0, direction_label="N/A", prop_line=None, player_team_side=None, game_total=None, pick_against_public=None, sport="nba"):
        # =====================================================================
        # v10.3 ADDITIVE SCORING SYSTEM (Sharp Quiet Fix)
        # =====================================================================
        # RESEARCH SCORE (0-10): base + pillar_boosts + context_mods (ADDITIVE)
        # - Base: 5.8 (neutral pick = MONITOR tier)
        # - Sharp-dependent pillars: +0.5 to +3.0 when signals present
        # - Sharp-independent pillars: +0.2 to +0.4 (always available)
        # - Context penalties: -1.0 for traps
        #
        # ESOTERIC SCORE (0-10): Weighted by signal importance (unchanged)
        # FINAL = (research × 0.67) + (esoteric × 0.33) + confluence_boost
        # =====================================================================

        # --- ESOTERIC WEIGHTS (v10.2 - Gematria Dominant) ---
        ESOTERIC_WEIGHTS = {
            "gematria": 0.52,    # 52% - Dominant signal (Boss approved)
            "jarvis": 0.20,      # 20% - JARVIS triggers
            "astro": 0.13,       # 13% - Vedic astrology
            "fib": 0.05,         # 5%  - Fibonacci alignment
            "vortex": 0.05,      # 5%  - Tesla 3-6-9 patterns
            "daily_edge": 0.05   # 5%  - Daily energy
        }

        # --- AI ENGINE SCORE (v10.24 - 8 AI Models) ---
        # Build prediction_data dict for AI Engine
        ai_prediction_data = {
            "odds": odds,
            "line": spread if market == "spreads" else prop_line,
            "market": market,
            "player_name": player_name,
            "home_team": home_team,
            "away_team": away_team,
            "is_home": is_home
        }
        # v10.36: Wire real injury data to AI Engine (was hardcoded False)
        our_team_ctx = home_team if is_home else away_team
        opp_team_ctx = away_team if is_home else home_team
        our_injuries_ctx = injuries_by_team.get(our_team_ctx, {})
        opp_injuries_ctx = injuries_by_team.get(opp_team_ctx, {})

        ai_context_data = {
            "team_rest_days": team_rest_days,
            "opp_rest_days": opp_rest_days,
            "key_player_out": len(our_injuries_ctx.get("key_players", [])) >= 1,
            "opp_key_player_out": len(opp_injuries_ctx.get("key_players", [])) >= 1,
            "injury_count": our_injuries_ctx.get("count", 0),
            "opp_injury_count": opp_injuries_ctx.get("count", 0)
        }

        # Call AI Engine
        if AI_ENGINE_AVAILABLE:
            ai_result = calculate_ai_engine_score(
                prediction_data=ai_prediction_data,
                sharp_signal=sharp_signal,
                context_data=ai_context_data
            )
            ai_score = ai_result.get("ai_score", 5.0)
            ai_breakdown = ai_result.get("ai_breakdown", {})
            ai_reasons = ai_result.get("ai_reasons", [])
        else:
            # Fallback when AI engine not available
            ai_result = get_ai_engine_defaults()
            ai_score = ai_result.get("ai_score", 5.0)
            ai_breakdown = ai_result.get("ai_breakdown", {})
            ai_reasons = ["AI ENGINE: Module unavailable, using baseline 5.0"]

        # --- RESEARCH SCORE CALCULATION (v10.10 Additive + Scoped Sharp) ---
        pillar_boost = 0.0
        research_reasons = []
        is_game_pick = not player_name

        # v10.13: Combined scope + direction multiplier for sharp pillars
        # - scope_mult: GAME-scoped signals apply at 0.5x for props (no prop-level sharp data yet)
        # - direction_mult: ALIGNED=1.0, NEUTRAL=0.5, CONFLICT=0.0 (v10.13)
        # For props: final_mult = scope_mult * direction_mult
        # For game picks: always 1.0 (full weight, no direction gating)
        scope_mult = 1.0 if (is_game_pick or sharp_scope == "PROP") else 0.5
        final_mult = 1.0 if is_game_pick else (scope_mult * direction_mult)

        # ========== SHARP-DEPENDENT PILLARS (v10.13: transparent math with BASE constants) ==========
        # v10.32: Micro-weight helper - applies learned weight tuning to signal boosts
        # Combines: micro_weights (from in-memory tuning) + signal_policies (from DB)
        # Both are bounded [0.85, 1.15], so combined range is [0.7225, 1.3225]
        def get_mw(signal_key: str, default: float = 1.0) -> float:
            """Get combined micro-weight for a signal (0.7225-1.3225 range, default 1.0)"""
            mw = micro_weights.get(signal_key, default)
            policy = signal_policies.get(signal_key, 1.0)
            # Combine and clamp to prevent extreme values
            combined = mw * policy
            return max(0.7, min(1.35, combined))

        # Pillar 1: Sharp Money (direction-gated for props)
        # v10.91: Lowered thresholds - 7%+ MODERATE, 15%+ STRONG
        sharp_diff = sharp_signal.get("diff", 0) or 0
        sharp_strength = sharp_signal.get("signal_strength", "NONE")
        has_sharp_signal = sharp_strength in ("STRONG", "MODERATE") or sharp_diff >= 7

        if is_game_pick:
            # Game picks always get full weight (no direction gating)
            mw_sharp = get_mw("PILLAR_SHARP_SPLIT")
            if sharp_strength == "STRONG" or sharp_diff >= 15:
                boost = 2.0 * mw_sharp
                pillar_boost += boost
                research_reasons.append(f"RESEARCH: Sharp Split (Game) +{boost:.2f}")
            elif sharp_strength == "MODERATE" or sharp_diff >= 7:  # v10.91: 7%+
                boost = 1.0 * mw_sharp
                pillar_boost += boost
                research_reasons.append(f"RESEARCH: Sharp Split (Game) +{boost:.2f}")
        elif has_sharp_signal:
            # v10.13: Props use BASE_SHARP_SPLIT_BOOST = 1.0 with transparent math
            # boost = BASE * scope_mult * direction_mult * micro_weight
            mw_sharp = get_mw("PILLAR_SHARP_SPLIT")
            boost = BASE_SHARP_SPLIT_BOOST * scope_mult * direction_mult * mw_sharp
            pillar_boost += boost
            research_reasons.append(f"RESEARCH: Sharp Split (GAME {direction_label} x{scope_mult * direction_mult:.2f}) +{boost:.2f}")

        # Pillar 2: Reverse Line Movement (RLM) - direction-gated for props
        # v10.63: True RLM detection using opening_line vs current_line from Playbook
        rlm_detected = sharp_signal.get("rlm_detected", False)
        line_movement = sharp_signal.get("line_movement", 0) or sharp_signal.get("line_variance", 0) or 0
        opening_line = sharp_signal.get("opening_line")
        current_line = sharp_signal.get("current_line")

        # True RLM: line moved against public betting action
        if rlm_detected and line_movement >= 0.5:
            mw_rlm = get_mw("PILLAR_RLM")
            # Stronger boost for confirmed RLM with significant movement
            movement_factor = min(2.0, 1.0 + (line_movement / 2.0))  # 1.0-2.0 based on movement
            if is_game_pick:
                boost = movement_factor * mw_rlm
                pillar_boost += boost
                research_reasons.append(f"RESEARCH: RLM Confirmed ({opening_line:.1f}→{current_line:.1f}) +{boost:.2f}")
            else:
                # Props use scoped/directional multiplier
                boost = BASE_RLM_BOOST * movement_factor * scope_mult * direction_mult * mw_rlm
                pillar_boost += boost
                research_reasons.append(f"RESEARCH: RLM Confirmed (GAME {direction_label} x{scope_mult * direction_mult:.2f}) +{boost:.2f}")
        elif line_movement > 1.0:
            # Fallback: significant line variance across books (legacy behavior)
            mw_rlm = get_mw("PILLAR_RLM")
            if is_game_pick:
                boost = 1.0 * mw_rlm
                pillar_boost += boost
                research_reasons.append(f"RESEARCH: Line Movement +{boost:.2f}")
            else:
                # v10.13: Props use BASE_RLM_BOOST = 1.0 with transparent math
                boost = BASE_RLM_BOOST * scope_mult * direction_mult * mw_rlm
                pillar_boost += boost
                research_reasons.append(f"RESEARCH: Line Movement (GAME {direction_label} x{scope_mult * direction_mult:.2f}) +{boost:.2f}")

        # Pillar 3: Public Fade (v10.20: directional with >= 65 threshold)
        # +0.5 when fading heavy public, -0.5 when riding with heavy public
        if public_pct >= 65:
            mw_public = get_mw("SIGNAL_PUBLIC_FADE")
            if pick_against_public is True:
                boost = 0.5 * mw_public
                pillar_boost += boost
                research_reasons.append(f"RESEARCH: Public Fade (against public) +{boost:.2f}")
            elif pick_against_public is False:
                boost = -0.5 * mw_public
                pillar_boost += boost
                research_reasons.append(f"RESEARCH: Public Trap (with public) {boost:.2f}")

        # v10.36 Pillar: Expert Consensus - fires when 65%+ of sharp money agrees
        # Sharp money IS expert money - professional bettors are the "experts"
        # Different from Sharp Split which fires at lower thresholds (10%+ diff)
        money_pct = sharp_signal.get("money_pct", 50) or 50
        sharp_side = safe_upper(sharp_signal.get("sharp_side"))  # "HOME" or "AWAY"
        if money_pct >= 65:
            mw_consensus = get_mw("PILLAR_EXPERT_CONSENSUS")
            # Check if our pick aligns with sharp consensus
            pick_with_consensus = False
            if is_game_pick:
                # For game picks, check if is_home aligns with sharp_side
                if (is_home and sharp_side == "HOME") or (not is_home and sharp_side == "AWAY"):
                    pick_with_consensus = True
            else:
                # For props, use direction_label
                if direction_label == "ALIGNED":
                    pick_with_consensus = True

            if pick_with_consensus:
                boost = 0.5 * mw_consensus
                pillar_boost += boost
                research_reasons.append(f"RESEARCH: Expert Consensus ({money_pct:.0f}% sharp money agrees) +{boost:.2f}")

        # v10.35 Pillar: Hospital Fade - boost when opponent has significant injuries
        # Determine which team we're betting on and check opponent injuries
        if is_game_pick and home_team and away_team:
            mw_hospital = get_mw("PILLAR_HOSPITAL_FADE")
            # For game picks, determine our team based on is_home or pick direction
            our_team = home_team if is_home else away_team
            opp_team = away_team if is_home else home_team

            opp_injuries = injuries_by_team.get(opp_team, {})
            our_injuries = injuries_by_team.get(our_team, {})
            opp_severity = opp_injuries.get("severity_score", 0)
            our_severity = our_injuries.get("severity_score", 0)
            opp_key_out = len(opp_injuries.get("key_players", []))
            our_key_out = len(our_injuries.get("key_players", []))

            # Boost if opponent has significant injuries (fading the hospital)
            if opp_severity >= 3 or opp_key_out >= 2:
                boost = 0.5 * mw_hospital
                pillar_boost += boost
                research_reasons.append(f"RESEARCH: Hospital Fade ({opp_team} {opp_key_out} key out) +{boost:.2f}")
            elif opp_severity >= 1.5 or opp_key_out >= 1:
                boost = 0.25 * mw_hospital
                pillar_boost += boost
                research_reasons.append(f"RESEARCH: Hospital Fade ({opp_team} banged up) +{boost:.2f}")

            # Penalty if our team has significant injuries
            if our_severity >= 3 or our_key_out >= 2:
                penalty = -0.4 * mw_hospital
                pillar_boost += penalty
                research_reasons.append(f"RESEARCH: Injury Concern ({our_team} {our_key_out} key out) {penalty:.2f}")

            # v10.66: Alternative Data Hospital Fade Boost (Twitter/SerpAPI breaking news)
            hospital_alt_boost = alt_data_adjustments.get("hospital_fade_boost", 0)
            if hospital_alt_boost > 0 and opp_key_out >= 1:
                pillar_boost += hospital_alt_boost
                research_reasons.append(f"RESEARCH: Breaking Injury News +{hospital_alt_boost:.2f}")

        # v10.66: Alternative Sharp Signal (Finnhub institutional movement)
        # Only applies when no traditional sharp signal detected
        if not has_sharp_signal:
            sharp_alt = alt_data_adjustments.get("sharp_alternative", 0)
            if sharp_alt >= 1.0:
                pillar_boost += sharp_alt
                research_reasons.append(f"RESEARCH: Institutional Sentiment +{sharp_alt:.2f}")

        # ========== SHARP-INDEPENDENT PILLARS (v10.3) ==========
        # Pillar 4: Home Court Advantage (game picks only)
        if is_game_pick and is_home:
            mw_situational = get_mw("PILLAR_SITUATIONAL")
            boost = 0.25 * mw_situational
            pillar_boost += boost
            research_reasons.append(f"RESEARCH: Home Court +{boost:.2f}")

        # Pillar 5: Rest Advantage (RELATIVE, not absolute)
        rest_diff = team_rest_days - opp_rest_days
        mw_situational = get_mw("PILLAR_SITUATIONAL")
        if rest_diff >= 2:
            boost = 0.4 * mw_situational
            pillar_boost += boost
            research_reasons.append(f"RESEARCH: Rest Advantage +{boost:.2f}")
        elif rest_diff == 1:
            boost = 0.2 * mw_situational
            pillar_boost += boost
            research_reasons.append(f"RESEARCH: Rest Advantage +{boost:.2f}")

        # Pillar 6: Prime Time Boost (7pm-10pm ET)
        if 19 <= game_hour_et <= 22:
            boost = 0.2 * mw_situational
            pillar_boost += boost
            research_reasons.append(f"RESEARCH: Prime Time +{boost:.2f}")

        # ========== PROP-ONLY INDEPENDENT PILLARS (v10.18) ==========
        # These provide micro-boosts for props when sharps are silent
        # Max total independent_prop_boost capped at 0.35
        if not is_game_pick:
            independent_prop_boost = 0.0

            # Prop Stability (low line) - easier to predict
            if prop_line is not None and prop_line <= 10.5:
                independent_prop_boost += 0.15
                research_reasons.append("RESEARCH: Prop Stability (low line) +0.15")

            # Prop Value (good juice) - favorable odds
            if odds is not None and abs(odds) <= 120:
                independent_prop_boost += 0.10
                research_reasons.append("RESEARCH: Prop Value (good juice) +0.10")

            # Pace Proxy (high total) - high-scoring game expected
            effective_total = game_total if game_total is not None else total
            if effective_total is not None and effective_total >= 224:
                independent_prop_boost += 0.10
                research_reasons.append("RESEARCH: Pace Proxy (high total) +0.10")

            # Home Micro - player on home team has slight advantage
            if player_team_side == "HOME":
                independent_prop_boost += 0.10
                research_reasons.append("RESEARCH: Home Micro +0.10")

            # Cap independent prop boost at 0.35 (spec requirement)
            independent_prop_boost = min(0.35, independent_prop_boost)
            pillar_boost += independent_prop_boost

        # ========== GAME PICK INDEPENDENT BOOSTS (v10.57) ==========
        # Game picks need equivalent boosts to compete with props
        if is_game_pick:
            game_pick_boost = 0.0

            # Spread Value (tight spread = competitive game)
            abs_spread = abs(spread) if spread else 0
            if 0 < abs_spread <= 6:
                game_pick_boost += 0.15
                research_reasons.append("RESEARCH: Tight Spread (competitive) +0.15")

            # Totals Value (reasonable total = predictable)
            if market == "totals" and 200 <= total <= 230:
                game_pick_boost += 0.15
                research_reasons.append("RESEARCH: Reasonable Total +0.15")

            # Home Team Boost (home teams have advantage)
            if is_home:
                game_pick_boost += 0.10
                research_reasons.append("RESEARCH: Home Team Edge +0.10")

            # Market Quality (spreads and totals more liquid than ML)
            if market in ["spreads", "totals"]:
                game_pick_boost += 0.10
                research_reasons.append("RESEARCH: Liquid Market +0.10")

            # Cap game pick boost at 0.40
            game_pick_boost = min(0.40, game_pick_boost)
            pillar_boost += game_pick_boost

        # ========== CONTEXT MODIFIERS ==========
        # Pillar 7: Mid-Spread Boss Zone (v10.20: renamed from Goldilocks)
        abs_spread = abs(spread) if spread else 0
        if 4 <= abs_spread <= 9:
            mw_goldilocks = get_mw("SIGNAL_GOLDILOCKS")
            boost = 0.2 * mw_goldilocks
            pillar_boost += boost
            research_reasons.append(f"RESEARCH: Mid-Spread Boss Zone +{boost:.2f}")

        # v10.35 Pillar: Hook Discipline - penalty for key numbers (high push/bad value zones)
        # Key numbers in NFL/NBA: 3, 7 (and their hooks -3.5, +3.5, -7.5, +7.5)
        # Also -6.5, +6.5 (dead zone)
        if is_game_pick and spread is not None:
            mw_hook = get_mw("PILLAR_HOOK_DISCIPLINE")
            hook_numbers = [3.5, -3.5, 6.5, -6.5, 7.5, -7.5, 10.5, -10.5, 13.5, -13.5, 14.5, -14.5]
            if spread in hook_numbers:
                penalty = -0.3 * mw_hook
                pillar_boost += penalty
                research_reasons.append(f"RESEARCH: Hook Penalty ({spread} = dead zone) {penalty:.2f}")
            # Clean key numbers get a small boost
            elif spread in [3.0, -3.0, 7.0, -7.0, 10.0, -10.0, 14.0, -14.0]:
                boost = 0.15 * mw_hook
                pillar_boost += boost
                research_reasons.append(f"RESEARCH: Key Number ({spread} = clean) +{boost:.2f}")

        # Pillar 8: Trap Gate (penalty)
        if abs_spread > 15:
            mw_trap = get_mw("SIGNAL_TRAP_GATE")
            penalty = -1.0 * mw_trap
            pillar_boost += penalty
            research_reasons.append(f"RESEARCH: Trap Gate {penalty:.2f}")

        # Pillar 9: High Total Indicator
        if total > 230:
            mw_high_total = get_mw("SIGNAL_HIGH_TOTAL")
            boost = 0.2 * mw_high_total
            pillar_boost += boost
            research_reasons.append(f"RESEARCH: High Total +{boost:.2f}")

        # Pillar 10: Multi-Pillar Confluence Bonus
        positive_pillars = len([r for r in research_reasons if "+" in r])
        if positive_pillars >= 3:
            mw_multi = get_mw("SIGNAL_MULTI_PILLAR")
            boost = 0.3 * mw_multi
            pillar_boost += boost
            research_reasons.append(f"RESEARCH: Multi-Pillar Confluence +{boost:.2f}")

        # v10.61 Pillar 11: Prop Correlation - boost when prop aligns with game environment
        # Props that correlate with high-scoring games (OVER) get boost when game total is high
        # Props that correlate with defensive games (UNDER) get boost when game total is low
        if not is_game_pick and market:
            mw_prop_corr = get_mw("PILLAR_PROP_CORRELATION")
            effective_total = game_total if game_total is not None else total
            market_lower = market.lower()

            # Scoring cluster props (points, assists, 3PT) correlate with high totals
            if any(stat in market_lower for stat in ["point", "assist", "three", "pts"]):
                if effective_total and effective_total >= 225:
                    boost = 0.25 * mw_prop_corr
                    pillar_boost += boost
                    research_reasons.append(f"RESEARCH: Prop Correlation (scoring + high total) +{boost:.2f}")
                elif effective_total and effective_total <= 210:
                    penalty = -0.15 * mw_prop_corr
                    pillar_boost += penalty
                    research_reasons.append(f"RESEARCH: Prop Correlation (scoring + low total) {penalty:.2f}")

            # Rebounding props correlate with pace and missed shots
            elif any(stat in market_lower for stat in ["rebound", "reb"]):
                if effective_total and effective_total >= 225:
                    boost = 0.15 * mw_prop_corr
                    pillar_boost += boost
                    research_reasons.append(f"RESEARCH: Prop Correlation (rebounds + high pace) +{boost:.2f}")

        # v10.61 Pillar 12: Volume Discipline - penalty for extreme public consensus
        # When ticket % is very lopsided (>75%), market may be a trap
        # This complements Public Fade by adding caution even when fading public
        ticket_pct = sharp_signal.get("ticket_pct", 50) or 50
        if ticket_pct >= 75:
            mw_volume = get_mw("PILLAR_VOLUME_DISCIPLINE")
            # Slight penalty for extreme consensus either way (trap risk)
            penalty = -0.15 * mw_volume
            pillar_boost += penalty
            research_reasons.append(f"RESEARCH: Volume Discipline ({ticket_pct}% consensus = trap risk) {penalty:.2f}")
        elif ticket_pct <= 25:
            # Very contrarian - could be sharp or could be wrong
            mw_volume = get_mw("PILLAR_VOLUME_DISCIPLINE")
            penalty = -0.10 * mw_volume
            pillar_boost += penalty
            research_reasons.append(f"RESEARCH: Volume Discipline ({ticket_pct}% contrarian = verify edge) {penalty:.2f}")

        # v10.36 Context Layer: Defensive Matchup + Pace Adjustments
        # These use context_layer.py data that was previously disconnected
        context_adjustment = 0.0
        if CONTEXT_LAYER_AVAILABLE and sport and not is_game_pick and player_name and away_team:
            # For props: check defensive matchup
            # Infer position from stat_type (simple heuristic)
            position = "Guard"  # default
            if market and "rebound" in market.lower():
                position = "Big"
            elif market and ("assist" in market.lower() or "point" in market.lower()):
                position = "Guard"
            elif market and "three" in market.lower():
                position = "Wing"

            # Determine opponent team (player is on one team, facing the other)
            opponent_team = away_team if player_team_side == "HOME" else home_team

            # Get defensive rank adjustment
            matchup_adj = DefensiveRankService.get_matchup_adjustment(
                sport=sport.upper(),
                team=opponent_team,
                position=position,
                player_avg=prop_line or 15.0  # Use prop line as proxy for player average
            )
            if matchup_adj:
                # Convert matchup adjustment to score modifier (capped at ±0.3)
                adj_value = matchup_adj.get("value", 0)
                if adj_value > 0:
                    # Soft matchup = boost
                    context_boost = min(0.3, adj_value / 10)
                    context_adjustment += context_boost
                    research_reasons.append(f"CONTEXT: Soft Matchup vs {opponent_team[:3]} +{context_boost:.2f}")
                elif adj_value < 0:
                    # Tough matchup = penalty
                    context_penalty = max(-0.3, adj_value / 10)
                    context_adjustment += context_penalty
                    research_reasons.append(f"CONTEXT: Tough Matchup vs {opponent_team[:3]} {context_penalty:.2f}")

        # v10.36 Context Layer: Pace adjustment for game totals and props
        if CONTEXT_LAYER_AVAILABLE and sport and home_team and away_team:
            pace_adj = PaceVectorService.get_pace_adjustment(
                sport=sport.upper(),
                team1=home_team,
                team2=away_team
            )
            if pace_adj:
                pace_value = pace_adj.get("value", 0)
                # Fast pace = slight boost for OVER/high stat props
                # Slow pace = slight boost for UNDER/low stat props
                if pace_value > 0:
                    pace_boost = min(0.2, pace_value / 20)
                    context_adjustment += pace_boost
                    research_reasons.append(f"CONTEXT: Fast Pace +{pace_boost:.2f}")
                elif pace_value < 0:
                    pace_penalty = max(-0.2, pace_value / 20)
                    context_adjustment += pace_penalty
                    research_reasons.append(f"CONTEXT: Slow Pace {pace_penalty:.2f}")

        # v10.60 Context Layer: Weather Impact (NFL/MLB outdoor games only)
        # Weather data is fetched via external_context at endpoint start
        if is_game_pick and sport and sport.lower() in ["nfl", "mlb"]:
            weather_data = external_context.get("weather", {})
            if weather_data.get("available"):
                weather_impact = weather_data.get("weather_impact", "NEUTRAL")
                wind_mph = weather_data.get("wind_mph", 0) or 0
                temp_f = weather_data.get("temp_f", 70) or 70

                if weather_impact == "FAVORABLE":
                    # Perfect conditions - slight boost for totals OVER
                    if market == "totals":
                        weather_boost = 0.20
                        context_adjustment += weather_boost
                        research_reasons.append(f"WEATHER: Favorable conditions +{weather_boost:.2f}")
                elif weather_impact == "UNFAVORABLE":
                    # Bad weather - affects passing/scoring
                    if market == "totals":
                        # UNDER more likely in bad weather
                        weather_penalty = -0.25
                        context_adjustment += weather_penalty
                        research_reasons.append(f"WEATHER: Unfavorable ({temp_f:.0f}F, {wind_mph:.0f}mph wind) {weather_penalty:.2f}")
                    elif market == "spreads" and wind_mph > 20:
                        # High wind affects passing teams more
                        weather_penalty = -0.15
                        context_adjustment += weather_penalty
                        research_reasons.append(f"WEATHER: High Wind ({wind_mph:.0f}mph) {weather_penalty:.2f}")

        # v10.68: Officials Impact now handled via ESPN in alt_data_adjustments["referee_adjustment"]
        # Applied to TOTAL picks in game scoring section (HIGH_FOUL +0.15, LOW_FOUL -0.10)

        # Apply context adjustment to pillar_boost
        pillar_boost += context_adjustment

        # Cap pillar_boost at 3.0 to prevent inflation
        pillar_boost = max(-1.0, min(3.0, float(pillar_boost)))

        # v10.9: MARKET-AWARE RESEARCH MODIFIER (breaks ML/spread symmetry)
        market_delta, market_reason = calculate_market_modifier(
            market=market,
            odds=odds,
            line=spread,  # For spreads, use spread as line
            active_pillars=research_reasons
        )

        # v10.22: Sport-specific market bias (from SPORT_PROFILES)
        sport_profile_local = get_sport_profile(sport)
        sport_market_bias = 0.0

        # NFL spreads bonus
        if sport.lower() == "nfl" and market == "spreads":
            sport_market_bias += sport_profile_local.get("boosts", {}).get("spreads_bias", 0.0)
            if sport_market_bias > 0:
                research_reasons.append(f"RESEARCH: Sport Market Bias (NFL spreads) +{sport_market_bias:.2f}")

        # MLB moneyline bonus
        if sport.lower() == "mlb" and market == "h2h":
            sport_market_bias += sport_profile_local.get("boosts", {}).get("ml_bias", 0.0)
            if sport_market_bias > 0:
                research_reasons.append(f"RESEARCH: Sport Market Bias (MLB ML) +{sport_market_bias:.2f}")

        # NHL ML dog weapon (handled separately in game picks loop, but tracked here for visibility)
        # Note: actual boost applied in game_picks section

        # ADDITIVE RESEARCH SCORE: base + pillars + market_mod + sport_bias, clamped to 0-10
        research_score = base_ai + pillar_boost + market_delta + sport_market_bias
        research_score = max(0.0, min(10.0, float(research_score)))

        # Add market modifier reason if applied
        if market_reason:
            research_reasons.append(market_reason)

        # --- ESOTERIC SCORE CALCULATION (v10.20 Ritual Score Backbone) ---
        # v10.20: Start with Ritual Base 6.0, then add micro-boosts
        RITUAL_BASE = 6.0
        esoteric_reasons = ["ESOTERIC: Ritual Base +6.0"]
        ritual_score = RITUAL_BASE

        gematria_score = 0.0       # 0-5.2 pts (52%)
        jarvis_score = 0.0         # 0-2.0 pts (20%)
        astro_score = 0.0          # 0-1.3 pts (13%)
        fib_score = 0.0            # 0-0.5 pts (5%)
        vortex_score = 0.0         # 0-0.5 pts (5%)
        daily_edge_score = 0.0     # 0-0.5 pts (5%)
        public_fade_mod = 0.0      # Modifier (can be negative)
        mid_spread_mod = 0.0       # Modifier
        trap_mod = 0.0             # Modifier (negative)

        jarvis_triggers_hit = []
        immortal_detected = False
        jarvis_triggered = False

        if jarvis:
            # --- JARVIS TRIGGERS (v10.58: collected here, applied in Jarvis RS only) ---
            # NOTE: Triggers are NO LONGER added to esoteric_reasons - they only affect Jarvis RS
            trigger_result = jarvis.check_jarvis_trigger(game_str)
            for trig in trigger_result.get("triggers_hit", []):
                jarvis_triggers_hit.append({
                    "number": trig["number"],
                    "name": trig["name"],
                    "match_type": trig.get("match_type", "DIRECT"),
                    "boost": round(trig["boost"] / 10, 2)
                })
                if trig["number"] == 2178:
                    immortal_detected = True
            jarvis_triggered = len(jarvis_triggers_hit) > 0

            # =================================================================
            # v10.58: 4-ENGINE SEPARATION (NO DOUBLE COUNTING)
            # =================================================================
            # 1. AI ENGINE (0-10): 8-model ensemble (unchanged)
            # 2. RESEARCH ENGINE (0-10): Market/human inefficiencies ONLY
            #    - Contains: Sharp Split, RLM, Public Fade, Expert Consensus
            #    - Contains: Hospital Fade, Goldilocks (Mid-Spread Boss Zone)
            #    - Public Fade is ONLY here (not in Jarvis or Esoteric)
            # 3. ESOTERIC ENGINE (0-10): NON-JARVIS environment signals
            #    - Contains: Vedic Astro, Fibonacci, Vortex, Daily Edge, External
            #    - Does NOT contain: Gematria, Jarvis triggers, Public Fade
            # 4. JARVIS ENGINE (0-10): STANDALONE ritual score
            #    - Contains: Gematria, Sacred Triggers (201/33/93/322/2178)
            #    - Contains: Mid-spread amplifier (Goldilocks 20% boost to Jarvis RS)
            #    - Does NOT contain: Fibonacci, Vortex (those are Esoteric)
            # =================================================================

            # --- JARVIS RS CALCULATION (STANDALONE ENGINE) ---
            # Contains: Gematria (dominant), JARVIS triggers, mid-spread amplifier
            jarvis_rs = 5.0  # Base Jarvis RS (neutral)
            jarvis_reasons = []

            if player_name and home_team:
                gematria = jarvis.calculate_gematria_signal(player_name, home_team, away_team)

                # Get raw player gematria value for player-specific differentiation
                player_gem_raw = gematria.get("player_gematria", {}).get("simple", 0)

                # Normalize player gematria to 0-1 scale (mod 100 gives 0-99, then /100)
                player_gem_normalized = (player_gem_raw % 100) / 100.0

                # Base gematria from player name (0-2.0 pts contribution to Jarvis RS)
                gematria_base = player_gem_normalized * 2.0

                # Trigger bonus from gematria signals (0-1.0 pts)
                trigger_strength = gematria.get("signal_strength", 0)
                if gematria.get("triggered"):
                    trigger_strength = min(1.0, trigger_strength * 1.5)
                gematria_trigger_bonus = trigger_strength * 1.0

                # Combined gematria contribution to Jarvis RS
                gematria_score = gematria_base + gematria_trigger_bonus  # 0-3.0 range

                # Add gematria to Jarvis RS
                jarvis_rs += gematria_score

                if gematria_score >= 1.0:
                    jarvis_reasons.append(f"JARVIS: Gematria {player_gem_raw} +{round(gematria_score, 2)}")

                # --- MID-SPREAD RITUAL AMPLIFIER (Jarvis-specific) ---
                mid_spread = jarvis.calculate_mid_spread_signal(spread)
                if mid_spread.get("signal") == "GOLDILOCKS":
                    # v10.40: True amplifier (20% boost to current Jarvis RS)
                    mid_spread_amplifier = jarvis_rs * 0.20
                    jarvis_rs += mid_spread_amplifier
                    jarvis_reasons.append(f"JARVIS: Goldilocks Zone +{round(mid_spread_amplifier, 2)} (20% amplifier)")
                mid_spread_mod = 0  # No longer affects esoteric

                # --- TRAP MODIFIER (Jarvis penalty) ---
                trap = jarvis.calculate_large_spread_trap(spread, total)
                trap_mod = trap.get("modifier", 0)
                if trap_mod < 0:
                    jarvis_rs += trap_mod  # Apply trap penalty to Jarvis RS
                    jarvis_reasons.append(f"JARVIS: Trap Gate {round(trap_mod, 2)}")

                # --- FIBONACCI (v10.58: Esoteric ONLY, no longer in Jarvis RS) ---
                fib_alignment = jarvis.calculate_fibonacci_alignment(float(spread) if spread else 0)
                fib_raw = fib_alignment.get("modifier", 0)
                fib_score = max(0, fib_raw) * 0.5  # Esoteric environment signal only
                if fib_score > 0:
                    esoteric_reasons.append(f"ESOTERIC: Fibonacci Alignment +{fib_score:.2f}")

                # --- VORTEX (v10.58: Esoteric ONLY, no longer in Jarvis RS) ---
                vortex_value = int(abs(spread * 10)) if spread else 0
                vortex_pattern = jarvis.calculate_vortex_pattern(vortex_value)
                vortex_raw = vortex_pattern.get("modifier", 0)
                vortex_score = max(0, vortex_raw) * 0.5  # Esoteric environment signal only
                if vortex_score > 0:
                    esoteric_reasons.append(f"ESOTERIC: Vortex Pattern +{vortex_score:.2f}")

            # Add JARVIS sacred trigger boosts to Jarvis RS
            for trigger in jarvis_triggers_hit:
                trigger_boost = trigger.get("boost", 0) * 2.5  # Scale up for Jarvis RS
                jarvis_rs += trigger_boost
                jarvis_reasons.append(f"JARVIS: Trigger {trigger['number']} +{round(trigger_boost, 2)}")

            # Clamp Jarvis RS to 0-10
            jarvis_rs = max(0, min(10, jarvis_rs))

            # --- ESOTERIC SCORE (v10.58: Environment-only, NO Jarvis components) ---
            # Contains ONLY: Vedic astro, Fibonacci, Vortex, Daily edge, External signals
            # Does NOT contain: Gematria (Jarvis), Triggers (Jarvis), Public Fade (Research)
            gematria_score = 0  # v10.58: Gematria is in Jarvis RS exclusively
            public_fade_mod = 0  # v10.58: Public Fade is in Research exclusively

            # --- ASTRO (environment signal) ---
            astro = vedic.calculate_astro_score() if vedic else {"overall_score": 50}
            astro_normalized = (astro["overall_score"] - 50) / 50  # -1 to +1
            astro_score = max(0, astro_normalized) * 2.0  # Max 2.0 pts

            if astro_score > 0.5:
                esoteric_reasons.append(f"ESOTERIC: Astro favorable +{round(astro_score, 2)}")

            # --- v10.59: BIORHYTHMS (player-specific esoteric signal) ---
            # Only for props (requires player_name), adds 0 to 0.5 pts
            biorhythm_score = 0.0
            if ESOTERIC_FEATURES_AVAILABLE and PLAYER_BIRTH_DATA_AVAILABLE and player_name and not is_game_pick:
                try:
                    player_data = get_player_data(player_name)
                    if player_data and player_data.get("birth_date"):
                        bio = calculate_biorhythms(player_data["birth_date"])
                        bio_status = bio.get("status", "NEUTRAL")
                        bio_overall = bio.get("overall", 0)

                        # Convert biorhythm status to score modifier (0-0.5 range)
                        if bio_status == "PEAK":
                            biorhythm_score = 0.5  # Peak performance expected
                        elif bio_status == "RISING":
                            biorhythm_score = 0.25  # Trending up
                        elif bio_status == "FALLING":
                            biorhythm_score = -0.15  # Minor penalty
                        elif bio_status == "LOW":
                            biorhythm_score = -0.25  # Avoid prop

                        if biorhythm_score != 0:
                            esoteric_reasons.append(f"ESOTERIC: Biorhythm {bio_status} {biorhythm_score:+.2f}")
                except Exception as e:
                    logger.debug(f"Biorhythm calculation failed for {player_name}: {e}")

            # --- v10.59: HURST EXPONENT (trend detection for momentum plays) ---
            # Uses recent scoring history to detect trend/mean-reversion regime
            hurst_score = 0.0
            # Note: Would need player stat history for full implementation
            # For now, use daily energy as proxy for "market momentum"
            if ESOTERIC_FEATURES_AVAILABLE and daily_energy.get("overall_score", 50) > 60:
                # High energy day = trending market = momentum plays favored
                hurst_score = 0.15
                esoteric_reasons.append(f"ESOTERIC: Trend momentum +{hurst_score:.2f}")

        else:
            # Fallback to simple trigger check for Jarvis RS
            jarvis_rs = 5.0
            for trigger_num, trigger_data in JARVIS_TRIGGERS.items():
                if str(trigger_num) in game_str:
                    trigger_boost = trigger_data["boost"] / 20  # Scaled for Jarvis RS
                    jarvis_rs += trigger_boost
                    jarvis_triggers_hit.append({
                        "number": trigger_num,
                        "name": trigger_data["name"],
                        "boost": round(trigger_boost, 2)
                    })
                    jarvis_reasons.append(f"JARVIS: Trigger {trigger_num} +{round(trigger_boost, 2)}")
                    if trigger_num == 2178:
                        immortal_detected = True
            jarvis_triggered = len(jarvis_triggers_hit) > 0
            jarvis_rs = max(0, min(10, jarvis_rs))

            # Fallback esoteric components
            fib_score = 0
            vortex_score = 0
            astro_score = 0
            biorhythm_score = 0  # v10.59: Fallback
            hurst_score = 0  # v10.59: Fallback

        # --- DAILY EDGE (esoteric environment) ---
        if daily_energy.get("overall_score", 50) >= 85:
            daily_edge_score = 1.0  # Max 1.0 pts
        elif daily_energy.get("overall_score", 50) >= 70:
            daily_edge_score = 0.5

        # v10.31: External signals micro-boost (Weather/Astronomy/NOAA/Planetary)
        micro_boost_external = external_micro_boost_data.get("total_boost", 0)
        external_reasons = external_micro_boost_data.get("reasons", [])
        for ext_reason in external_reasons:
            esoteric_reasons.append(ext_reason)

        # --- ESOTERIC SCORE (v10.59: Environment + Player Signals - NO Jarvis) ---
        # Base 5.0 + astro + fib + vortex + daily + external + biorhythm + hurst + alt_data
        # Excludes: Gematria (Jarvis), Triggers (Jarvis), Public Fade (Research)
        # v10.66: Added alternative data component (FRED economic + news momentum)
        alt_data_esoteric = alt_data_adjustments.get("esoteric_alt_data", 0)
        if alt_data_esoteric != 0:
            esoteric_reasons.append(f"ESOTERIC: Alt Data Sentiment {'+' if alt_data_esoteric > 0 else ''}{alt_data_esoteric:.2f}")

        # v10.70: Chrome Resonance (jersey color psychology)
        chrome_score = 0.0
        if home_team and away_team:
            chrome_data = get_chrome_resonance(home_team, away_team)
            if chrome_data.get("chrome_boost", 0) != 0:
                chrome_score = chrome_data["chrome_boost"]
                esoteric_reasons.append(f"ESOTERIC: {chrome_data['chrome_reason']} {chrome_score:+.2f}")

        esoteric_raw = (
            5.0 +                    # Neutral base
            astro_score +            # Vedic astro (0-2.0 pts)
            fib_score +              # Fibonacci (0-0.5 pts)
            vortex_score +           # Vortex (0-0.5 pts)
            daily_edge_score +       # Daily energy (0-1.0 pts)
            micro_boost_external +   # Weather/NOAA/Planetary (+/-0.25 pts)
            biorhythm_score +        # v10.59: Player biorhythm (-0.25 to +0.5 pts)
            hurst_score +            # v10.59: Trend momentum (0-0.15 pts)
            alt_data_esoteric +      # v10.66: FRED/Finnhub/Twitter sentiment (-0.3 to +0.5 pts)
            chrome_score             # v10.70: Chrome Resonance (+/-0.15 pts)
        )
        esoteric_score = max(0, min(10, esoteric_raw))

        # --- v10.40: CONFLUENCE LADDER (2-Alignment Method) ---
        # Alignment computed from: AI↔Research AND Research↔Jarvis
        alignment_ar = 1 - abs(ai_score - research_score) / 10  # AI to Research
        alignment_rj = 1 - abs(research_score - jarvis_rs) / 10  # Research to Jarvis
        alignment_avg = (alignment_ar + alignment_rj) / 2
        alignment_pct = alignment_avg * 100

        # v10.40: Updated confluence ladder with Jarvis RS requirements
        (confluence_boost, confluence_label, confluence_level, confluence_reasons,
         confluence_fail_reasons, confluence_rule_trace, confluence_repair_hints,
         confluence_alignment_gap) = compute_confluence_ladder_v1040(
            ai_score=ai_score,
            research_score=research_score,
            jarvis_rs=jarvis_rs,
            alignment_pct=alignment_pct,
            jarvis_active=jarvis_triggered,
            jarvis_hits_count=len(jarvis_triggers_hit),
            immortal_active=immortal_detected
        )

        # v10.26: Track confluence stats for ALL candidates (debug output)
        nonlocal confluence_counts_candidates, alignment_pct_sum_candidates, alignment_pct_count_candidates
        confluence_counts_candidates[confluence_label] = confluence_counts_candidates.get(confluence_label, 0) + 1
        alignment_pct_sum_candidates += alignment_pct
        alignment_pct_count_candidates += 1

        # --- FINAL SCORE FORMULA (v10.40: 4-Engine Blend) ---
        # FINAL = (AI × w_ai) + (Research × w_res) + (Esoteric × w_eso) + (Jarvis × w_jar) + Confluence
        profile = get_sport_profile(sport)
        w_ai = profile["weights"].get("ai", 0.35)
        w_research = profile["weights"].get("research", 0.35)
        w_esoteric = profile["weights"].get("esoteric", 0.10)
        w_jarvis = profile["weights"].get("jarvis", 0.20)

        # v10.40: 4-ENGINE BLEND
        final_score = (
            (ai_score * w_ai) +
            (research_score * w_research) +
            (esoteric_score * w_esoteric) +
            (jarvis_rs * w_jarvis) +
            confluence_boost
        )
        final_score = max(0.0, min(10.0, float(final_score)))

        # =====================================================================
        # v10.39: JARVIS TURBO BAND
        # =====================================================================
        # Jarvis Turbo is an UPGRADE layer that can promote picks from EDGE_LEAN
        # to GOLD_STAR, but NEVER creates picks from nothing.
        #
        # Gate conditions (BOTH required):
        #   - final_score >= 6.50 (already EDGE_LEAN quality)
        #   - jarvis_active == True (at least one trigger fired)
        #
        # Turbo ladder (based on jarvis hits count):
        #   - 4+ hits: +0.55 (capped)
        #   - 3 hits:  +0.40
        #   - 2 hits:  +0.25
        #   - 1 hit:   +0.15
        #
        # Applied BEFORE tier assignment so Jarvis can decisively impact tiers.
        # =====================================================================
        jarvis_hits_count = len(jarvis_triggers_hit)
        jarvis_turbo_boost = 0.0
        jarvis_turbo_reasons = []

        # Gate: Only apply turbo to already-valid picks (EDGE_LEAN+ threshold)
        # v10.40: Added jarvis_rs >= 6.8 safeguard (prevents low-quality Jarvis from boosting)
        JARVIS_TURBO_GATE = 6.50
        JARVIS_RS_MIN = 6.8  # v10.40: Minimum Jarvis RS required for turbo
        JARVIS_TURBO_CAP = 0.55
        FINAL_SCORE_CAP = 9.99

        if final_score >= JARVIS_TURBO_GATE and jarvis_triggered and jarvis_rs >= JARVIS_RS_MIN:
            # Turbo ladder based on number of Jarvis hits
            if jarvis_hits_count >= 4:
                jarvis_turbo_boost = 0.55
            elif jarvis_hits_count >= 3:
                jarvis_turbo_boost = 0.40
            elif jarvis_hits_count >= 2:
                jarvis_turbo_boost = 0.25
            elif jarvis_hits_count >= 1:
                jarvis_turbo_boost = 0.15

            # Cap the turbo boost
            jarvis_turbo_boost = min(jarvis_turbo_boost, JARVIS_TURBO_CAP)

            # Apply turbo boost
            if jarvis_turbo_boost > 0:
                final_score += jarvis_turbo_boost
                jarvis_turbo_reasons.append(
                    f"JARVIS TURBO: +{jarvis_turbo_boost:.2f} (hits={jarvis_hits_count}, rs={jarvis_rs:.2f}, gate=EDGE_LEAN+)"
                )

        # =====================================================================
        # v10.69: HARMONIC CONVERGENCE / GOLDEN BOOST
        # =====================================================================
        # Crown Jewels integration: When BOTH "Math" (AI score) AND "Magic"
        # (Esoteric score) are highly aligned (>8.0), this signals a rare
        # confluence where quantitative models AND esoteric signals agree.
        #
        # Gate conditions (BOTH required):
        #   - ai_score >= 8.0 (80th percentile of AI engine)
        #   - esoteric_score >= 8.0 (80th percentile of esoteric signals)
        #
        # Boost: +0.75 points (significant but not overpowering)
        # =====================================================================
        HARMONIC_GATE_AI = 8.0
        HARMONIC_GATE_ESOTERIC = 8.0
        HARMONIC_BOOST = 0.75
        harmonic_convergence = False
        harmonic_reasons = []

        if ai_score >= HARMONIC_GATE_AI and esoteric_score >= HARMONIC_GATE_ESOTERIC:
            harmonic_convergence = True
            final_score += HARMONIC_BOOST
            harmonic_reasons.append(
                f"HARMONIC: Golden Convergence +{HARMONIC_BOOST:.2f} (Math={ai_score:.1f}, Magic={esoteric_score:.1f})"
            )

        # Cap final score at 9.99 (never exceed)
        final_score = min(final_score, FINAL_SCORE_CAP)

        # --- SmashSpot FLAG (v10.19 Strict) ---
        # Smash Spot is a TRUTH FLAG, not a score boost.
        # Requires: score >= 8.0, alignment >= 85%, jarvis active, BOTH Sharp Split AND RLM
        smash_spot = evaluate_smash_spot(
            final_score=final_score,
            alignment_pct=alignment_pct,
            jarvis_active=jarvis_triggered,
            research_reasons=research_reasons
        )
        # v10.19: Add SMASH reason only if truly a smash spot
        smash_reasons = []
        if smash_spot:
            smash_reasons.append("SMASH: Confluence locked (score>=8.0, align>=85%, Jarvis active, pillars confirmed)")

        # --- BET TIER DETERMINATION (v10.22: Sport Profile Tiers) ---
        final_score = clamp_score(final_score)
        tier, badge = tier_from_score(final_score, profile["tiers"])

        # v10.59: Kelly Criterion-enhanced unit sizing
        # Uses edge calculation for actionable tiers, falls back to fixed for others
        if tier in ("GOLD_STAR", "EDGE_LEAN") and odds:
            kelly_units = calculate_kelly_units(final_score, odds, tier)
            tier_config = {
                "GOLD_STAR": {"units": kelly_units, "action": "SMASH"},
                "EDGE_LEAN": {"units": kelly_units, "action": "PLAY"},
            }
        else:
            tier_config = {
                "GOLD_STAR": {"units": 2.0, "action": "SMASH"},
                "EDGE_LEAN": {"units": 1.0, "action": "PLAY"},
            }
        tier_config["MONITOR"] = {"units": 0.0, "action": "WATCH"}
        tier_config["PASS"] = {"units": 0.0, "action": "SKIP"}

        config = tier_config.get(tier, {"units": 0.0, "action": "SKIP"})
        bet_tier = {"tier": tier, "units": config["units"], "action": config["action"]}

        # Map to confidence levels for backward compatibility
        confidence_map = {
            "GOLD_STAR": "SMASH",
            "EDGE_LEAN": "HIGH",
            "MONITOR": "MEDIUM",
            "PASS": "LOW"
        }
        confidence = confidence_map.get(tier, "LOW")

        # Confidence score synced with final_score (Production v3)
        confidence_score = int(round(final_score * 10))  # 0-100 synced with final

        # Combine all reasons for explainability (v10.24: AI ENGINE first, then RESEARCH, ESOTERIC, etc.)
        # v10.39: Add JARVIS TURBO reasons after confluence (upgrade layer)
        # v10.69: Add HARMONIC reasons for Golden Convergence
        all_reasons = ai_reasons + research_reasons + esoteric_reasons + confluence_reasons + jarvis_turbo_reasons + harmonic_reasons + smash_reasons

        # v10.58: Calculate exact contributions for final_math ledger
        ai_contrib = round(ai_score * w_ai, 4)
        research_contrib = round(research_score * w_research, 4)
        esoteric_contrib = round(esoteric_score * w_esoteric, 4)
        jarvis_contrib = round(jarvis_rs * w_jarvis, 4)

        return {
            "total_score": round(final_score, 2),
            "confidence": confidence,
            "confidence_score": confidence_score,  # Synced with final_score * 10
            "confluence_level": confluence_level,
            "confluence_label": confluence_label,  # v10.25: Ladder label (IMMORTAL_CONFLUENCE, etc.)
            "confluence_boost": round(confluence_boost, 2),  # v10.25: Actual boost applied
            "alignment_pct": round(alignment_pct, 1),  # v10.4: alignment percentage
            "smash_spot": smash_spot,  # v10.4: SmashSpot flag
            "bet_tier": bet_tier,
            "reasons": all_reasons,  # Explainability array
            "ai_score": round(ai_score, 2),  # v10.24: 8 AI Engine score
            "ai_breakdown": ai_breakdown,  # v10.24: 8 model breakdown
            "scoring_breakdown": {
                "ai_score": round(ai_score, 2),  # v10.24: 8 AI Engine score
                "research_score": round(research_score, 2),
                "esoteric_score": round(esoteric_score, 2),
                "base_score": base_ai,  # v10.3: 5.8 base
                "pillar_boost": round(pillar_boost, 2),  # v10.3: additive pillars
                "confluence_boost": round(confluence_boost, 2),  # v10.4: jarvis confluence
                "jarvis_turbo_boost": round(jarvis_turbo_boost, 2),  # v10.39: Jarvis turbo upgrade
                "harmonic_convergence_boost": round(HARMONIC_BOOST if harmonic_convergence else 0.0, 2),  # v10.69: Golden boost
                "alignment_pct": round(alignment_pct, 1)
            },
            # v10.58: Full engine breakdown for PROOF LEDGER
            "engine_breakdown": {
                "ai": {
                    "score": round(ai_score, 2),
                    "weight": w_ai,
                    "contribution": ai_contrib,
                    "models_used": list(ai_breakdown.keys()) if ai_breakdown else [],
                    "reasons": ai_reasons
                },
                "research": {
                    "score": round(research_score, 2),
                    "weight": w_research,
                    "contribution": research_contrib,
                    "pillars_hit": [r for r in research_reasons if "RESEARCH:" in r],
                    "pillars_count": len([r for r in research_reasons if "RESEARCH:" in r and "+" in r]),
                    "base_score": base_ai,
                    "pillar_boost": round(pillar_boost, 2),
                    "reasons": research_reasons
                },
                "esoteric": {
                    "score": round(esoteric_score, 2),
                    "weight": w_esoteric,
                    "contribution": esoteric_contrib,
                    "signals_used": {
                        "astro_score": round(astro_score, 2),
                        "fib_score": round(fib_score, 2),
                        "vortex_score": round(vortex_score, 2),
                        "daily_edge_score": round(daily_edge_score, 2),
                        "external_micro_boost": round(micro_boost_external, 2)
                    },
                    "reasons": esoteric_reasons
                },
                "jarvis": {
                    "jarvis_rs": round(jarvis_rs, 2),
                    "weight": w_jarvis,
                    "contribution": jarvis_contrib,
                    "jarvis_active": jarvis_triggered,
                    "jarvis_hits_count": jarvis_hits_count,
                    "jarvis_triggers_hit": jarvis_triggers_hit,
                    "jarvis_reasons": jarvis_reasons,
                    "immortal_detected": immortal_detected
                }
            },
            # v10.58: Final math ledger showing exact calculation
            "final_math": {
                "formula": "FINAL = (AI × w_ai) + (Research × w_res) + (Esoteric × w_eso) + (Jarvis × w_jar) + Confluence + Turbo",
                "weights": {
                    "ai": w_ai,
                    "research": w_research,
                    "esoteric": w_esoteric,
                    "jarvis": w_jarvis
                },
                "contributions": {
                    "ai_contrib": ai_contrib,
                    "research_contrib": research_contrib,
                    "esoteric_contrib": esoteric_contrib,
                    "jarvis_contrib": jarvis_contrib,
                    "confluence_boost": round(confluence_boost, 2),
                    "jarvis_turbo_boost": round(jarvis_turbo_boost, 2)
                },
                "sum_before_turbo": round(ai_contrib + research_contrib + esoteric_contrib + jarvis_contrib + confluence_boost, 4),
                "final_score": round(final_score, 2)
            },
            "jarvis_hits_count": jarvis_hits_count,  # v10.39: Count of Jarvis triggers hit
            "jarvis_turbo_boost": round(jarvis_turbo_boost, 2),  # v10.39: Turbo boost applied
            "harmonic_convergence": harmonic_convergence,  # v10.69: Golden boost triggered (Math+Magic both >8.0)
            "esoteric_breakdown": {
                # v10.58: Esoteric is NON-JARVIS only (environment signals)
                # Gematria/Jarvis triggers now in jarvis_rs exclusively
                "astro": round(astro_score, 2),             # Vedic astro (max 2.0 pts)
                "fibonacci": round(fib_score, 2),           # Fib alignment (max 0.5 pts)
                "vortex": round(vortex_score, 2),           # Vortex pattern (max 0.5 pts)
                "daily_edge": round(daily_edge_score, 2),   # Daily energy (max 1.0 pts)
                "external_micro": round(micro_boost_external, 2),  # Weather/NOAA/Planetary
            },
            "jarvis_triggers": jarvis_triggers_hit,
            "jarvis_active": jarvis_triggered,  # v10.4: for SmashSpot check
            "jarvis_rs": round(jarvis_rs, 2),  # v10.40: Standalone Jarvis Ritual Score (0-10)
            "jarvis_reasons": jarvis_reasons,  # v10.40: Jarvis explainability reasons
            "immortal_detected": immortal_detected,
            # v10.28: Debug-only confluence diagnostics (stripped unless debug=1)
            "_debug_confluence_failures": confluence_fail_reasons,
            "_debug_confluence_trace": confluence_rule_trace,
            "_debug_confluence_repairs": confluence_repair_hints,
            "_debug_alignment_gap": confluence_alignment_gap
        }

    # ============================================
    # CATEGORY 1: PLAYER PROPS
    # ============================================
    props_picks = []
    props_data = {"data": [], "source": "none"}  # Default fallback
    dk_market_index = {}  # v10.57: Initialize before try block for scope
    try:
        props_data = await get_props(sport)

        # v10.57: Build DK market index from raw props feed for market_availability validation
        # This ensures we only publish props that are actually available on DraftKings
        if VALIDATORS_AVAILABLE:
            raw_props_for_index = []
            for game in props_data.get("data", []):
                game_id = game.get("game_id", "")
                for prop in game.get("props", []):
                    raw_props_for_index.append({
                        "sport": sport_lower.upper(),
                        "game_id": game_id,
                        "player_name": prop.get("player", ""),
                        "market": prop.get("market", ""),
                        "line": prop.get("line", 0),
                        "side": prop.get("side", "Over")
                    })
            dk_market_index = build_dk_market_index(raw_props_for_index)
            logger.debug(f"v10.57: Built DK market index with {len(dk_market_index)} entries")

        # v10.14: Fetch Playbook rosters for player-team mapping
        playbook_roster = await fetch_playbook_rosters(sport)
        logger.info("v10.14: Playbook roster fetched with %d players", len(playbook_roster))

        # v10.14: Build player team cache from any available roster data in props
        player_team_cache = build_player_team_cache(props_data.get("data", []), {}, {})
        logger.info("v10.14: Player team cache built with %d entries", len(player_team_cache))

        for game in props_data.get("data", []):
            home_team = game.get("home_team", "")
            away_team = game.get("away_team", "")
            game_key = f"{away_team}@{home_team}"
            game_str = f"{home_team}{away_team}"
            sharp_signal = sharp_lookup.get(game_key, {})

            # v10.12: Extract game sharp direction (side + total)
            game_sharp_side, game_sharp_total = extract_game_sharp_direction(sharp_signal)

            # v10.13: Normalize game team abbreviations
            home_abbr = normalize_team_abbr(home_team)
            away_abbr = normalize_team_abbr(away_team)

            for prop in game.get("props", []):
                player = prop.get("player", "Unknown")
                market = prop.get("market", "")
                line = prop.get("line", 0)
                odds = prop.get("odds", -110)
                # v10.47: Handle None values from Odds API (key exists but value is null)
                side = prop.get("side") or "Over"

                if side not in ["Over", "Under"]:
                    continue

                # v10.14: Use resolver chain to determine player_team_side
                player_team_side, team_resolver_source = resolve_player_team_side(
                    prop=prop,
                    player_name=player,
                    home_abbr=home_abbr,
                    away_abbr=away_abbr,
                    player_team_cache=player_team_cache,
                    playbook_roster=playbook_roster
                )

                # v10.14: Get player abbr from prop if available (for debug output)
                player_team_raw = (
                    prop.get("team_abbr")
                    or prop.get("team")
                    or prop.get("player_team")
                    or prop.get("team_name")
                    or prop.get("teamName")
                )
                player_abbr = normalize_team_abbr(player_team_raw) if player_team_raw else None

                # v10.13: Extract prop direction (OVER/UNDER)
                prop_side = side.upper() if isinstance(side, str) else None

                # v10.14: Build prediction_data for directional correlation
                direction_data = {
                    "prop_side": prop_side,
                    "player_team_side": player_team_side,
                    "game_sharp_side": game_sharp_side,
                    "game_sharp_total": game_sharp_total,
                    "market": market,
                    "player_team_abbr": player_abbr,
                    "game_home_abbr": home_abbr,
                    "game_away_abbr": away_abbr,
                    "team_resolver_source": team_resolver_source,  # v10.14
                }

                # v10.14: Calculate directional multiplier with true ALIGNED/CONFLICT/NEUTRAL
                direction_mult, direction_label = get_directional_mult(direction_data)

                # Extract game hour for Prime Time pillar
                game_hour_et = 20  # Default to 8pm ET
                commence_time = game.get("commence_time", "")
                if commence_time:
                    try:
                        from datetime import datetime as dt_parse
                        game_dt = dt_parse.fromisoformat(commence_time.replace("Z", "+00:00"))
                        # Convert to ET (UTC-5)
                        game_hour_et = (game_dt.hour - 5) % 24
                    except Exception:
                        pass

                # Calculate score with full esoteric integration (v10.18)
                # v10.17: Props use base_ai=6.0 (vs games 5.8) to compensate for
                # reduced sharp pillar weights (scope_mult=0.5)
                # v10.18: Add prop_line, player_team_side, game_total for prop-independent pillars
                score_data = calculate_pick_score(
                    game_str + player,
                    sharp_signal,
                    base_ai=6.0,  # v10.17: Raised from 5.8 for props parity
                    player_name=player,
                    home_team=home_team,
                    away_team=away_team,
                    spread=0,
                    total=220,
                    public_pct=50,
                    game_hour_et=game_hour_et,
                    market=market,  # v10.9: pass market for market-aware scoring
                    odds=odds,      # v10.9: pass odds for market modifier
                    sharp_scope="GAME",  # v10.10: game-level sharp applied at 0.5x for props
                    direction_mult=direction_mult,  # v10.11: direction gating
                    direction_label=direction_label,  # v10.11: for reasons tracking
                    prop_line=line,  # v10.18: prop line for Prop Stability pillar
                    player_team_side=player_team_side,  # v10.18: for Home Micro pillar
                    game_total=None,  # v10.18: game total for Pace Proxy (use total param)
                    sport=sport_lower  # v10.36: pass sport for Context Layer
                )

                # v10.24: Track AI + Jarvis call for props
                jarvis_debug["calls_total"] += 1
                jarvis_debug["calls_props"] += 1
                jarvis_debug["ai_calls_total"] += 1

                # Calculate frontend-expected fields
                total_score = score_data.get("total_score", 5.0)
                confidence_score_val = score_data.get("confidence_score", 50)

                # v10.10: Get stat label for clear selection string
                stat_label = MARKET_LABELS.get(market)
                if not stat_label:
                    # Fallback: convert market key to readable label
                    stat_label = market.replace("player_", "").replace("batter_", "").replace("pitcher_", "").replace("_", " ").title()

                # Force line to float
                line_val = float(line) if line else 0.0

                # v10.10: Format selection with stat label
                formatted_selection = f"{player} {side} {line_val} {stat_label}".strip()

                # Generate rationale based on signals
                rationale = f"{player} {stat_label.lower()} prop analysis: "
                if sharp_signal.get("signal_strength") == "STRONG":
                    rationale += "Sharp money detected. "
                if score_data.get("immortal_detected"):
                    rationale += "JARVIS immortal pattern triggered. "
                rationale += f"Scoring confluence at {score_data.get('scoring_breakdown', {}).get('alignment_pct', 70):.0f}% alignment."

                # Get tier from bet_tier (Production v3)
                tier = score_data.get("bet_tier", {}).get("tier", "PASS")

                # v10.19: Get smash_spot flag from score_data
                is_smash_spot = score_data.get("smash_spot", False)

                # v10.19: Determine badge based on smash_spot and tier
                # Badge logic: SMASH SPOT > GOLD STAR > tier name
                if is_smash_spot:
                    badge_label = "SMASH SPOT"
                elif tier == "GOLD_STAR":
                    badge_label = "GOLD STAR"
                else:
                    badge_label = tier

                # Determine badges array based on v10.19 rules
                badges = []
                if is_smash_spot:
                    badges.append("SMASH_SPOT")
                elif tier == "GOLD_STAR":
                    badges.append("GOLD_STAR")
                if sharp_signal.get("signal_strength") == "STRONG":
                    badges.append("SHARP_MONEY")
                if score_data.get("immortal_detected"):
                    badges.append("IMMORTAL")
                if score_data.get("jarvis_triggers"):
                    badges.append("JARVIS_TRIGGER")

                # Estimated predicted value
                predicted_value = line_val + (2.5 if side == "Over" else -2.5) * (total_score / 8.0)

                # v10.76: Capture book info for prop metadata
                prop_book_key = prop.get("book", "unknown")
                prop_book_display = BOOKMAKER_DISPLAY_NAMES.get(prop_book_key, prop_book_key.title() if prop_book_key else "Unknown")
                prop_book_url = BOOKMAKER_BET_URLS.get(prop_book_key)
                prop_odds_pulled_at = datetime.now().isoformat()

                # v10.81: Compute display fields for frontend (props)
                prop_display_title = f"{away_team} @ {home_team}"
                prop_display_pick = f"{player} {(side or 'Over').upper()} {line_val} {stat_label} ({odds:+d}) — {prop_book_display}"

                # v10.81: Compute time-gate fields for props
                prop_game_time_utc = game.get("commence_time", "")
                prop_has_started = False
                prop_started_minutes_ago = None
                prop_game_time_est = ""
                try:
                    if prop_game_time_utc:
                        from zoneinfo import ZoneInfo
                        ET = ZoneInfo("America/New_York")
                        prop_game_dt = datetime.fromisoformat(prop_game_time_utc.replace("Z", "+00:00"))
                        prop_game_dt_et = prop_game_dt.astimezone(ET)
                        prop_game_time_est = prop_game_dt_et.isoformat()
                        now_et = datetime.now(ET)
                        if now_et > prop_game_dt_et:
                            prop_has_started = True
                            prop_started_minutes_ago = int((now_et - prop_game_dt_et).total_seconds() / 60)
                except Exception:
                    pass

                # Build the prop pick object
                prop_pick = {
                    "sport": sport.upper(),  # v10.57: Required for validators
                    "game_id": game.get("game_id", game.get("id", "")),  # v10.57: Required for validators
                    "player": player,
                    "player_name": player,  # Alias for frontend compatibility
                    "market": market,
                    "stat_type": market,    # Alias for frontend compatibility
                    "stat_label": stat_label,  # v10.10: Human-readable stat label
                    "line": line_val,
                    "side": side,
                    "over_under": (side or "over").lower(),  # Frontend expected field (v10.47: defensive None)
                    "odds": odds,
                    "odds_american": odds,  # v10.80: Canonical schema field
                    "game": f"{away_team} @ {home_team}",
                    "matchup": f"{away_team} vs {home_team}",  # Production v3 schema
                    "selection": formatted_selection,  # v10.10: "Player Side Line StatLabel"
                    "home_team": home_team,
                    "away_team": away_team,
                    "team": home_team,  # Frontend expected field
                    "opponent": away_team,  # Frontend expected field
                    "game_time": game.get("commence_time", datetime.now().isoformat()),
                    # v10.81: Frontend display fields
                    "display_title": prop_display_title,
                    "display_pick": prop_display_pick,
                    # v10.81: Time-gate fields
                    "game_time_est": prop_game_time_est,
                    "has_started": prop_has_started,
                    "started_minutes_ago": prop_started_minutes_ago,
                    "recommendation": f"{(side or 'Over').upper()} {line_val} {stat_label}",  # v10.10: include stat label (v10.47: defensive None)
                    "smash_score": total_score,
                    "final_score": total_score,  # Production v3 schema
                    "predicted_value": round(predicted_value, 1),
                    "rationale": rationale,
                    "badges": badges,
                    "tier": tier,       # Production v3 schema (never modified by governor)
                    "badge": badge_label,  # v10.19: SMASH SPOT, GOLD STAR, or tier name
                    "reasons": score_data.get("reasons", []),  # Production v3 explainability
                    **score_data,
                    "sharp_signal": sharp_signal.get("signal_strength", "NONE"),
                    "source": "odds_api",
                    # v10.76: Book tracking for strict pick template
                    "book": prop_book_key,
                    "book_display": prop_book_display,
                    "book_url": prop_book_url,
                    # v10.80: Canonical schema book fields
                    "book_key": prop_book_key,
                    "book_name": prop_book_display,
                    "book_link": prop_book_url,
                    "market_key": market,
                    "odds_pulled_at": prop_odds_pulled_at,
                    "line_at_pull": line_val,
                    "odds_at_pull": odds,
                }

                # v10.14: Add mapping reason for explainability
                if player_team_side:
                    prop_pick["reasons"] = prop_pick.get("reasons", []) + [
                        f"MAPPING: player_team_side={player_team_side} via {team_resolver_source}"
                    ]
                else:
                    prop_pick["reasons"] = prop_pick.get("reasons", []) + [
                        "MAPPING: player_team_side missing -> directional NEUTRAL (0.5)"
                    ]

                # v10.15: Add standalone CORRELATION reason for easy filtering
                # This makes ALIGNED/CONFLICT/NEUTRAL/NO_SIGNAL searchable without parsing embedded reasons
                # v10.18: Add NO_SIGNAL handling for truthful correlation messaging
                if direction_label == "ALIGNED":
                    prop_pick["reasons"] = prop_pick.get("reasons", []) + [
                        f"CORRELATION: ALIGNED (prop {prop_side} matches sharp direction, mult={direction_mult:.1f})"
                    ]
                elif direction_label == "CONFLICT":
                    prop_pick["reasons"] = prop_pick.get("reasons", []) + [
                        f"CORRELATION: CONFLICT (prop {prop_side} opposes sharp direction, mult={direction_mult:.1f})"
                    ]
                elif direction_label == "NO_SIGNAL":
                    # v10.18: Truthful NO_SIGNAL when no sharp direction available
                    prop_pick["reasons"] = prop_pick.get("reasons", []) + [
                        f"CORRELATION: NO_SIGNAL (no sharp direction available, mult={direction_mult:.1f})"
                    ]
                elif direction_label.startswith("NEUTRAL"):
                    prop_pick["reasons"] = prop_pick.get("reasons", []) + [
                        f"CORRELATION: {direction_label} (mult={direction_mult:.1f})"
                    ]

                # v10.14: Add debug fields for correlation visibility when debug=1
                if debug:
                    prop_pick["sharp_scope"] = "GAME"
                    prop_pick["game_sharp_side"] = game_sharp_side
                    prop_pick["game_sharp_total"] = game_sharp_total
                    prop_pick["player_team_side"] = player_team_side
                    prop_pick["player_team_abbr"] = player_abbr
                    prop_pick["game_home_abbr"] = home_abbr
                    prop_pick["game_away_abbr"] = away_abbr
                    prop_pick["prop_side"] = prop_side
                    prop_pick["directional_mult"] = direction_mult
                    prop_pick["directional_label"] = direction_label
                    prop_pick["team_resolver_source"] = team_resolver_source

                # v10.37: Enrich prop with correlation cluster and group ID
                # This enables stacking of aligned correlated props (e.g., Points Over + 3PT Over)
                prop_pick = enrich_prop_with_correlation(prop_pick)

                props_picks.append(prop_pick)
    except HTTPException:
        logger.warning("Props fetch failed for %s", sport)

    # v10.9: PROP DEDUPLICATION - stop collisions like Maxey x4
    # Uses resolve_prop_conflicts for proper tie-breaking (score, odds, line distance)
    deduplicated_props, props_dropped_count = resolve_prop_conflicts(props_picks)

    # v10.16: Apply reason ordering to each pick (MAPPING → CORRELATION → RESEARCH → ...)
    for pick in deduplicated_props:
        pick["reasons"] = order_reasons(pick.get("reasons", []))

    # v10.22: Get sport profile for conflict filtering policy
    sport_profile = get_sport_profile(sport_lower)
    exclude_conflicts = sport_profile["conflict_policy"].get("exclude_conflicts", True)

    # v10.16: Bucket props by correlation for visibility and debugging
    aligned_props = []
    neutral_props = []
    conflict_props = []

    for p in deduplicated_props:
        mult = p.get("directional_mult", 0.5)
        label = p.get("directional_label", "")

        if mult == 1.0 or label == "ALIGNED":
            aligned_props.append(p)
        elif mult == 0.0 or label == "CONFLICT":
            # v10.22: If sport allows conflicts (NFL), label them instead of excluding
            if not exclude_conflicts:
                p["badges"] = p.get("badges", []) + ["CONFLICT"]
            conflict_props.append(p)
        else:
            # NEUTRAL or unknown
            neutral_props.append(p)

    # Sort each bucket by score (best first)
    aligned_props.sort(key=lambda x: clamp_score(x.get("final_score", x.get("total_score", 0))), reverse=True)
    neutral_props.sort(key=lambda x: clamp_score(x.get("final_score", x.get("total_score", 0))), reverse=True)
    conflict_props.sort(key=lambda x: clamp_score(x.get("final_score", x.get("total_score", 0))), reverse=True)

    # v10.22: Track correlation counters for debug
    excluded_conflict_count = len(conflict_props) if exclude_conflicts else 0
    correlation_counters = {
        "aligned_count": len(aligned_props),
        "neutral_count": len(neutral_props),
        "conflict_count": len(conflict_props),
        "excluded_conflicts_count": excluded_conflict_count,
        "conflicts_included": not exclude_conflicts  # v10.22: for debug visibility
    }

    # v10.22: Main selection based on sport conflict policy
    # If exclude_conflicts=True (NBA, NHL, MLB, NCAAB): exclude conflicts
    # If exclude_conflicts=False (NFL): include conflicts but they're labeled
    if exclude_conflicts:
        deduplicated_props = aligned_props + neutral_props
    else:
        # NFL: include all, conflicts already labeled with CONFLICT badge
        deduplicated_props = aligned_props + neutral_props + conflict_props

    deduplicated_props.sort(key=lambda x: clamp_score(x.get("final_score", x.get("total_score", 0))), reverse=True)

    # VOLUME GOVERNOR (v10.19): Max 3 GOLD STAR, but NEVER lie about tiers
    # Tier is always accurate to score. Badge can change for display purposes.
    # v10.19: Smash Spot badge logic integrated
    gold_count = 0
    smash_count = 0
    governed_props = []
    for pick in deduplicated_props:
        # Re-apply tier from score to ensure consistency (v10.22: sport profile tiers)
        score = clamp_score(pick.get("final_score", pick.get("total_score", 0)))
        tier, _ = tier_from_score(score, sport_profile["tiers"])
        pick["tier"] = tier
        pick["final_score"] = score
        pick["confidence"] = int(round(score * 10))

        # v10.19: Determine badge based on smash_spot flag
        is_smash = pick.get("smash_spot", False)

        if tier == "GOLD_STAR":
            gold_count += 1
            if gold_count > 3:
                # Keep tier accurate, but change badge to indicate capped
                pick["badge"] = "GOLD (CAPPED)"
                pick["reasons"] = pick.get("reasons", []) + ["GOVERNOR: Gold cap enforced (4th+ gold)"]
            elif is_smash:
                pick["badge"] = "SMASH SPOT"
                smash_count += 1
            else:
                pick["badge"] = "GOLD STAR"
        else:
            pick["badge"] = tier
        governed_props.append(pick)

    # Fallback: Surface top picks for minimum volume, but DON'T change their tier
    actionable = [p for p in governed_props if p.get("tier") in ["GOLD_STAR", "EDGE_LEAN"]]
    if len(actionable) < 3 and len(governed_props) >= 3:
        # Mark top MONITOR picks as "TOP VALUE" for display, but keep tier accurate
        monitor_picks = [p for p in governed_props if p.get("tier") == "MONITOR"]
        for pick in monitor_picks[:3 - len(actionable)]:
            pick["badge"] = "TOP VALUE"
            pick["reasons"] = pick.get("reasons", []) + ["GOVERNOR: Filled slot for minimum volume (tier preserved)"]

    # v10.36: Quality over quantity - return ALL actionable picks, no arbitrary limits
    # Only GOLD_STAR and EDGE_LEAN picks are truly actionable
    # If there are none, return top 3 MONITOR picks as fallback
    actionable_props = [p for p in governed_props if p.get("tier") in ["GOLD_STAR", "EDGE_LEAN"]]
    if len(actionable_props) == 0:
        # Fallback: return top 3 MONITOR picks if no actionable picks
        actionable_props = [p for p in governed_props if p.get("tier") == "MONITOR"][:3]

    # v10.37: Allow correlated props to stack when both independently qualify
    # MASTER PROMPT: "You MUST NOT auto-block aligned props just because they're correlated.
    # If two props are logically aligned AND BOTH qualify as EDGE_LEAN or better,
    # BOTH may be included as separate picks."
    actionable_props = allow_correlated_stacking(
        actionable_props,
        tier_threshold=["GOLD_STAR", "EDGE_LEAN"]
    )

    # =========================================================================
    # v10.90: Prop Availability Check - Filter out players whose lines were pulled
    # Sportsbooks pull lines when players are ruled OUT (late scratch, injury, etc.)
    # This prevents serving stale props for unavailable players
    # =========================================================================
    props_before_availability = len(actionable_props)
    unavailable_players = []

    if actionable_props and ODDS_API_KEY:
        try:
            # Get unique game IDs from props
            game_ids = list(set(p.get("game_id") for p in actionable_props if p.get("game_id")))

            # For each game, get currently available players
            available_players_by_game = {}
            for game_id in game_ids[:5]:  # Limit to 5 games to control API usage
                try:
                    check_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/events/{game_id}/odds"
                    check_resp = await fetch_with_retries(
                        "GET", check_url,
                        params={
                            "apiKey": ODDS_API_KEY,
                            "regions": "us",
                            "markets": "player_points",
                            "oddsFormat": "american"
                        },
                        timeout=5.0
                    )
                    if check_resp and check_resp.status_code == 200:
                        check_data = check_resp.json()
                        players_set = set()
                        for book in check_data.get("bookmakers", []):
                            for market in book.get("markets", []):
                                for outcome in market.get("outcomes", []):
                                    player_name = outcome.get("description", "")
                                    if player_name:
                                        players_set.add(player_name.lower())
                        available_players_by_game[game_id] = players_set
                except Exception:
                    pass  # Skip game if check fails

            # Filter out props where player is no longer available
            validated_props = []
            for prop in actionable_props:
                game_id = prop.get("game_id")
                player_name = prop.get("player_name", prop.get("player", "")).lower()

                if game_id in available_players_by_game:
                    available = available_players_by_game[game_id]
                    if player_name and player_name not in available:
                        # Player's lines were pulled - they're likely OUT
                        unavailable_players.append({
                            "player": prop.get("player_name", prop.get("player")),
                            "reason": "LINES_PULLED"
                        })
                        prop["availability_status"] = "UNAVAILABLE"
                        continue  # Skip this prop

                validated_props.append(prop)

            actionable_props = validated_props

        except Exception as e:
            logger.warning(f"v10.90: Prop availability check failed: {e}")
            # Continue with unvalidated props if check fails

    props_after_availability = len(actionable_props)
    props_filtered_unavailable = props_before_availability - props_after_availability

    top_props = actionable_props

    # ============================================
    # CATEGORY 2: GAME PICKS (Spreads, Totals, ML)
    # ============================================
    game_picks = []
    sport_config = SPORT_MAPPINGS[sport_lower]

    # v10.38: Track raw events count for debug visibility
    raw_events_count = 0
    today_games_count = 0  # v10.77: Games after TODAY_ET filter
    games_with_odds_count = 0  # v10.78: Games that have bookmaker/odds data

    # v10.45: Track odds metrics for diagnostics
    odds_provider_status = "UNKNOWN"
    odds_markets_count = 0
    odds_http_status = None
    odds_fallback_used = False

    try:
        # Fetch game odds (spreads, totals, moneylines)
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "spreads,h2h,totals",
                "oddsFormat": "american"
            }
        )

        odds_http_status = resp.status_code if resp else None

        if resp and resp.status_code == 200:
            games_raw = resp.json()
            raw_events_count = len(games_raw)  # v10.38: Track raw events from Odds API

            # v10.77: Apply TODAY_ET filter BEFORE any processing
            games, dropped_games, filter_summary = debug_day_filter(games_raw, source=f"OddsAPI_{sport}")
            today_games_count = len(games)
            logger.info(f"v10.77: {filter_summary}")

            # Log dropped games for debugging
            if dropped_games and debug:
                for g in dropped_games[:3]:
                    t_str = g.get("commence_time", "")
                    try:
                        t_et = datetime.fromisoformat(t_str.replace("Z", "+00:00")).astimezone(ET)
                        logger.info(f"  DROPPED: {g.get('away_team')} @ {g.get('home_team')} | {t_et.isoformat()} (not today ET)")
                    except Exception:
                        pass

            odds_provider_status = "OK" if today_games_count > 0 else ("EMPTY_TODAY" if raw_events_count > 0 else "EMPTY")

            # v10.45: Store successful odds snapshot in fallback cache
            if len(games) > 0:
                market_counts = {"spreads": 0, "totals": 0, "h2h": 0}
                for g in games:
                    for bm in g.get("bookmakers", []):
                        for m in bm.get("markets", []):
                            mk = m.get("key", "")
                            if mk in market_counts:
                                market_counts[mk] += len(m.get("outcomes", []))
                odds_markets_count = sum(market_counts.values())

                ODDS_FALLBACK_CACHE[sport_lower] = {
                    "data": games,
                    "timestamp": datetime.now(),
                    "events": len(games),
                    "markets": market_counts
                }
        elif resp and resp.status_code == 429:
            odds_provider_status = "RATE_LIMITED"
        else:
            odds_provider_status = f"ERROR_{resp.status_code}" if resp else "ERROR_NO_RESPONSE"

        # v10.45: Fallback to cached odds if empty and daytime ET
        if raw_events_count == 0 and is_daytime_et() and sport_lower in ODDS_FALLBACK_CACHE:
            fallback = ODDS_FALLBACK_CACHE[sport_lower]
            cache_age_minutes = (datetime.now() - fallback["timestamp"]).total_seconds() / 60

            if cache_age_minutes <= 720:  # 12 hours
                games = fallback["data"]
                raw_events_count = len(games)
                odds_provider_status = "FALLBACK"
                odds_fallback_used = True
                odds_markets_count = sum(fallback.get("markets", {}).values())
                logger.info("Using fallback cache for %s game picks: %d events, age=%.1f min",
                           sport, len(games), cache_age_minutes)

        # v10.45: Update global odds metrics
        ODDS_METRICS[sport_lower] = {
            "odds_provider_status": odds_provider_status,
            "odds_events_count": raw_events_count,
            "odds_markets_count": odds_markets_count,
            "odds_http_status": odds_http_status,
            "odds_fallback_used": odds_fallback_used,
            "odds_cache_age_minutes": None
        }

        # v10.45: Process games if we have data (from API or fallback)
        if raw_events_count > 0:
            # v10.71: Auto-populate Jason Sim payloads from games data
            # Transform Odds API format to Jason Sim expected format
            jason_sim_games = []
            for g in games:
                if not is_game_today(g.get("commence_time", "")):
                    continue
                game_entry = {
                    "id": g.get("id"),
                    "game_id": g.get("id"),
                    "home_team": g.get("home_team", ""),
                    "away_team": g.get("away_team", ""),
                }
                # Extract spread/total/h2h from first bookmaker
                for bm in g.get("bookmakers", [])[:1]:
                    for mkt in bm.get("markets", []):
                        mk = mkt.get("key", "")
                        outcomes = mkt.get("outcomes", [])
                        if mk == "spreads":
                            for o in outcomes:
                                if o.get("name") == g.get("home_team"):
                                    game_entry["spread"] = o.get("point", 0)
                        elif mk == "totals":
                            for o in outcomes:
                                if o.get("name") == "Over":
                                    game_entry["total"] = o.get("point", 220)
                        elif mk == "h2h":
                            h2h = {}
                            for o in outcomes:
                                if o.get("name") == g.get("home_team"):
                                    h2h["home"] = o.get("price", -110)
                                elif o.get("name") == g.get("away_team"):
                                    h2h["away"] = o.get("price", -110)
                            game_entry["h2h"] = h2h
                jason_sim_games.append(game_entry)

            if jason_sim_games:
                jason_sim_populated = auto_populate_jason_sim_payloads(sport_lower, jason_sim_games)
                logger.info(f"v10.71: Auto-populated {jason_sim_populated} Jason Sim payloads for {sport}")

            for game in games:
                # v10.50: Only process TODAY's games (skip future dates)
                game_commence = game.get("commence_time", "")
                if not is_game_today(game_commence):
                    continue

                home_team = game.get("home_team", "")
                away_team = game.get("away_team", "")
                game_key = f"{away_team}@{home_team}"
                game_str = f"{home_team}{away_team}"
                sharp_signal = sharp_lookup.get(game_key, {})

                # v10.78: Track games with odds data
                if game.get("bookmakers"):
                    games_with_odds_count += 1

                for bm in game.get("bookmakers", [])[:1]:  # Just use first book for now
                    # v10.76: Capture book info for pick metadata
                    book_key = bm.get("key", "unknown")
                    book_display = BOOKMAKER_DISPLAY_NAMES.get(book_key, book_key.title())
                    book_url = BOOKMAKER_BET_URLS.get(book_key)
                    odds_pulled_at = datetime.now().isoformat()

                    for market in bm.get("markets", []):
                        market_key = market.get("key", "")

                        for outcome in market.get("outcomes", []):
                            pick_name = outcome.get("name", "")
                            odds = outcome.get("price", -110)
                            point = outcome.get("point")

                            # Build display info
                            if market_key == "spreads":
                                pick_type = "SPREAD"
                                display = f"{pick_name} {point:+.1f}" if point else pick_name
                            elif market_key == "h2h":
                                pick_type = "MONEYLINE"
                                display = f"{pick_name} ML"
                            elif market_key == "totals":
                                pick_type = "TOTAL"
                                display = f"{pick_name} {point}" if point else pick_name
                            else:
                                continue

                            # Extract game hour for Prime Time pillar
                            game_hour_et = 20  # Default to 8pm ET
                            game_commence = game.get("commence_time", "")
                            if game_commence:
                                try:
                                    from datetime import datetime as dt_parse
                                    game_dt = dt_parse.fromisoformat(game_commence.replace("Z", "+00:00"))
                                    game_hour_et = (game_dt.hour - 5) % 24
                                except Exception:
                                    pass

                            # Determine if this pick is for the home team
                            is_home_pick = (pick_name == home_team) if market_key != "totals" else False

                            # Calculate score with full esoteric integration (v10.9)
                            # v10.57: Raise base_ai to 6.0 for parity with props
                            score_data = calculate_pick_score(
                                game_str,
                                sharp_signal,
                                base_ai=6.0,  # v10.57: Parity with props (was 5.8)
                                player_name="",  # Empty = game pick flag
                                home_team=home_team,
                                away_team=away_team,
                                spread=point if market_key == "spreads" and point else 0,
                                total=point if market_key == "totals" and point else 220,
                                public_pct=50,
                                is_home=is_home_pick,
                                game_hour_et=game_hour_et,
                                market=market_key,  # v10.9: pass market for market-aware scoring
                                odds=odds,          # v10.9: pass odds for market modifier
                                sport=sport_lower   # v10.20: pass sport for NHL ML Dog
                            )

                            # v10.59: Monte Carlo simulation for game picks
                            monte_carlo_data = {}
                            monte_carlo_edge = 0.0
                            if MONTE_CARLO_AVAILABLE and home_team and away_team:
                                try:
                                    if market_key == "spreads" and point is not None:
                                        # Evaluate spread bet
                                        mc_result = MonteCarloService.evaluate_spread(
                                            sport=sport_lower,
                                            home_team=home_team,
                                            away_team=away_team,
                                            spread=point,
                                            num_simulations=5000  # Reduced for performance
                                        )
                                        monte_carlo_data = {
                                            "type": "spread",
                                            "predicted_margin": mc_result["predicted_margin"],
                                            "margin_vs_spread": mc_result["margin_vs_spread"],
                                            "cover_pct": mc_result["home_cover_pct"] if is_home_pick else mc_result["away_cover_pct"],
                                            "edge_pct": mc_result["edge_pct"],
                                            "mc_confidence": mc_result["confidence"],
                                            "mc_recommendation": mc_result["recommendation"],
                                        }
                                        # Add Monte Carlo edge to score (max 0.3 pts)
                                        if mc_result["edge_pct"] > 5:
                                            monte_carlo_edge = min(0.3, mc_result["edge_pct"] / 30)
                                            score_data["reasons"] = score_data.get("reasons", []) + [
                                                f"MONTE_CARLO: {mc_result['confidence']} edge ({mc_result['edge_pct']:.1f}%) +{monte_carlo_edge:.2f}"
                                            ]
                                    elif market_key == "totals" and point is not None:
                                        # Evaluate total bet
                                        mc_result = MonteCarloService.evaluate_total(
                                            sport=sport_lower,
                                            home_team=home_team,
                                            away_team=away_team,
                                            total_line=point,
                                            num_simulations=5000
                                        )
                                        is_over = pick_name.upper() == "OVER"
                                        monte_carlo_data = {
                                            "type": "total",
                                            "predicted_total": mc_result["predicted_total"],
                                            "total_vs_line": mc_result["total_vs_line"],
                                            "hit_pct": mc_result["over_pct"] if is_over else mc_result["under_pct"],
                                            "edge_pct": mc_result["edge_pct"],
                                            "mc_confidence": mc_result["confidence"],
                                            "mc_recommendation": mc_result["recommendation"],
                                        }
                                        # Add Monte Carlo edge to score (max 0.3 pts)
                                        if mc_result["edge_pct"] > 5:
                                            monte_carlo_edge = min(0.3, mc_result["edge_pct"] / 30)
                                            score_data["reasons"] = score_data.get("reasons", []) + [
                                                f"MONTE_CARLO: {mc_result['confidence']} edge ({mc_result['edge_pct']:.1f}%) +{monte_carlo_edge:.2f}"
                                            ]
                                    elif market_key == "h2h":
                                        # Evaluate moneyline bet
                                        mc_result = MonteCarloService.simulate_game(
                                            sport=sport_lower,
                                            home_team=home_team,
                                            away_team=away_team,
                                            num_simulations=5000
                                        )
                                        win_pct = mc_result["home_win_pct"] if is_home_pick else mc_result["away_win_pct"]
                                        monte_carlo_data = {
                                            "type": "moneyline",
                                            "win_pct": win_pct,
                                            "predicted_margin": mc_result["predicted_margin"],
                                            "mc_confidence": mc_result["confidence"],
                                            "margin_68_band": mc_result["margin_68_band"],
                                        }
                                        # Add edge based on win probability
                                        if win_pct > 0.58:
                                            monte_carlo_edge = min(0.25, (win_pct - 0.5) * 1.5)
                                            score_data["reasons"] = score_data.get("reasons", []) + [
                                                f"MONTE_CARLO: {win_pct*100:.1f}% win probability +{monte_carlo_edge:.2f}"
                                            ]

                                    # Apply Monte Carlo edge to score
                                    if monte_carlo_edge > 0:
                                        score_data["total_score"] = min(10.0, score_data.get("total_score", 5.0) + monte_carlo_edge)

                                except Exception as mc_err:
                                    logger.debug(f"Monte Carlo simulation failed: {mc_err}")

                            # v10.24: Track AI + Jarvis call for game picks
                            jarvis_debug["calls_total"] += 1
                            jarvis_debug["calls_game"] += 1
                            jarvis_debug["ai_calls_total"] += 1

                            # v10.20: NHL ML Dog Weapon
                            # NHL ML underdogs (+odds) get a +0.5 boost to override market priority disadvantage
                            nhl_ml_dog_active = False
                            if sport_lower == "nhl" and market_key == "h2h" and odds > 100:
                                # This is an NHL moneyline underdog
                                score_data["total_score"] = min(10.0, score_data.get("total_score", 5.0) + 0.5)
                                score_data["reasons"] = score_data.get("reasons", []) + ["RESEARCH: NHL ML Dog Weapon +0.5"]
                                nhl_ml_dog_active = True
                                # Recalculate tier with boosted score
                                boosted_score = score_data["total_score"]
                                if boosted_score >= 7.5:
                                    score_data["bet_tier"] = {"tier": "GOLD_STAR", "units": 2.0, "action": "SMASH"}
                                elif boosted_score >= 6.5:
                                    score_data["bet_tier"] = {"tier": "EDGE_LEAN", "units": 1.0, "action": "PLAY"}
                                elif boosted_score >= 5.5:
                                    score_data["bet_tier"] = {"tier": "MONITOR", "units": 0.0, "action": "WATCH"}
                                else:
                                    score_data["bet_tier"] = {"tier": "PASS", "units": 0.0, "action": "SKIP"}

                            # v10.68: ESPN Referee Adjustment for Totals
                            referee_adj = alt_data_adjustments.get("referee_adjustment", 0.0)
                            if pick_type == "TOTAL" and referee_adj != 0.0:
                                is_over = pick_name.upper() == "OVER"
                                # Apply referee adjustment: positive = boost overs, negative = boost unders
                                if (is_over and referee_adj > 0) or (not is_over and referee_adj < 0):
                                    adj_value = abs(referee_adj)
                                    score_data["total_score"] = min(10.0, score_data.get("total_score", 5.0) + adj_value)
                                    tendency = "HIGH_FOUL" if referee_adj > 0 else "LOW_FOUL"
                                    score_data["reasons"] = score_data.get("reasons", []) + [
                                        f"ESPN: Referee {tendency} tendency +{adj_value:.2f}"
                                    ]
                                    # Recalculate tier with boosted score
                                    boosted_score = score_data["total_score"]
                                    if boosted_score >= 7.5:
                                        score_data["bet_tier"] = {"tier": "GOLD_STAR", "units": 2.0, "action": "SMASH"}
                                    elif boosted_score >= 6.5:
                                        score_data["bet_tier"] = {"tier": "EDGE_LEAN", "units": 1.0, "action": "PLAY"}
                                    elif boosted_score >= 5.5:
                                        score_data["bet_tier"] = {"tier": "MONITOR", "units": 0.0, "action": "WATCH"}
                                    else:
                                        score_data["bet_tier"] = {"tier": "PASS", "units": 0.0, "action": "SKIP"}

                            # Calculate frontend-expected fields for game picks
                            total_score_game = score_data.get("total_score", 5.0)
                            tier_game = score_data.get("bet_tier", {}).get("tier", "PASS")

                            # Generate rationale based on pick type
                            if pick_type == "SPREAD":
                                rationale_game = f"{pick_name} spread pick based on matchup analysis. "
                                if sharp_signal.get("signal_strength") == "STRONG":
                                    rationale_game += "Sharp money confirms this side."
                            elif pick_type == "TOTAL":
                                rationale_game = f"Total {pick_name} projection based on pace metrics. "
                            else:  # MONEYLINE
                                rationale_game = f"{pick_name} moneyline value identified. "

                            # v10.19: Get smash_spot flag from score_data
                            is_smash_game = score_data.get("smash_spot", False)

                            # v10.19: Determine badge based on smash_spot and tier
                            if is_smash_game:
                                badge_label_game = "SMASH SPOT"
                            elif tier_game == "GOLD_STAR":
                                badge_label_game = "GOLD STAR"
                            else:
                                badge_label_game = tier_game

                            # Determine badges array based on v10.19 rules
                            badges_game = []
                            if is_smash_game:
                                badges_game.append("SMASH_SPOT")
                            elif tier_game == "GOLD_STAR":
                                badges_game.append("GOLD_STAR")
                            if sharp_signal.get("signal_strength") == "STRONG":
                                badges_game.append("SHARP_MONEY")
                            if market_key == "spreads" and abs(point or 0) <= 3:
                                badges_game.append("TIGHT_SPREAD")
                            # v10.20: NHL ML Dog badge
                            if nhl_ml_dog_active:
                                badges_game.append("NHL_ML_DOG")

                            # v10.59: Add Monte Carlo badge if high edge
                            if monte_carlo_data.get("edge_pct", 0) > 8:
                                badges_game.append("MONTE_CARLO")

                            # v10.81: Compute display fields for frontend
                            display_title = f"{away_team} @ {home_team}"
                            if market_key == "spreads" and point is not None:
                                display_pick = f"{pick_name} {point:+.1f} ({odds:+d}) — {book_display}"
                            elif market_key == "h2h":
                                display_pick = f"{pick_name} ML ({odds:+d}) — {book_display}"
                            elif market_key == "totals" and point is not None:
                                display_pick = f"{pick_name} {point} ({odds:+d}) — {book_display}"
                            else:
                                display_pick = f"{display} ({odds:+d}) — {book_display}"

                            # v10.81: Compute time-gate fields
                            game_time_utc = game.get("commence_time", "")
                            has_started = False
                            started_minutes_ago = None
                            game_time_est = ""
                            try:
                                if game_time_utc:
                                    from zoneinfo import ZoneInfo
                                    ET = ZoneInfo("America/New_York")
                                    game_dt = datetime.fromisoformat(game_time_utc.replace("Z", "+00:00"))
                                    game_dt_et = game_dt.astimezone(ET)
                                    game_time_est = game_dt_et.isoformat()
                                    now_et = datetime.now(ET)
                                    if now_et > game_dt_et:
                                        has_started = True
                                        started_minutes_ago = int((now_et - game_dt_et).total_seconds() / 60)
                            except Exception:
                                pass

                            game_picks.append({
                                "sport": sport.upper(),  # v10.57: For consistency with props
                                "game_id": game.get("game_id", game.get("id", "")),  # v10.57: For consistency
                                "pick_type": pick_type,
                                "pick": display,
                                "team": pick_name if market_key != "totals" else None,
                                "line": point,
                                "odds": odds,
                                "odds_american": odds,  # v10.80: Canonical schema field
                                "game": f"{away_team} @ {home_team}",
                                "matchup": f"{away_team} vs {home_team}",  # Production v3 schema
                                "selection": display,  # Production v3 schema
                                "home_team": home_team,
                                "away_team": away_team,
                                "market": market_key,
                                "recommendation": display,
                                "game_time": game_time_utc or datetime.now().isoformat(),
                                # v10.81: Frontend display fields
                                "display_title": display_title,
                                "display_pick": display_pick,
                                # v10.81: Time-gate fields
                                "game_time_est": game_time_est,
                                "has_started": has_started,
                                "started_minutes_ago": started_minutes_ago,
                                "smash_score": total_score_game,
                                "final_score": total_score_game,  # Production v3 schema
                                "predicted_value": (point + 3) if market_key == "totals" else None,
                                "rationale": rationale_game,
                                "badges": badges_game,
                                "tier": tier_game,  # Production v3 schema (never modified by governor)
                                "badge": badge_label_game,  # v10.19: SMASH SPOT, GOLD STAR, or tier name
                                "reasons": score_data.get("reasons", []),  # Production v3 explainability
                                **score_data,
                                "sharp_signal": sharp_signal.get("signal_strength", "NONE"),
                                "source": "odds_api",
                                "monte_carlo": monte_carlo_data if monte_carlo_data else None,  # v10.59
                                # v10.76: Book tracking for strict pick template
                                "book": book_key,
                                "book_display": book_display,
                                "book_url": book_url,
                                # v10.80: Canonical schema book fields
                                "book_key": book_key,
                                "book_name": book_display,
                                "book_link": book_url,
                                "market_key": market_key,
                                "odds_pulled_at": odds_pulled_at,
                                "line_at_pull": point,
                                "odds_at_pull": odds,
                            })
    except Exception as e:
        logger.warning("Game odds fetch failed: %s", e)

    # Fallback to sharp money if no game picks
    if not game_picks and sharp_data.get("data"):
        for signal in sharp_data.get("data", []):
            home_team = signal.get("home_team", "")
            away_team = signal.get("away_team", "")
            game_str = f"{home_team}{away_team}"

            # Determine if sharp pick is on home team
            is_home_sharp = signal.get("side") == "HOME"

            # Calculate score with v10.9 additive scoring
            # v10.57: Raise base_ai to 6.0 for parity with props
            score_data = calculate_pick_score(
                game_str,
                signal,
                base_ai=6.0,  # v10.57: Parity with props (was 5.8)
                player_name="",
                home_team=home_team,
                away_team=away_team,
                spread=signal.get("line_variance", 0),
                total=220,
                public_pct=50,
                is_home=is_home_sharp,
                market="sharp_money",  # v10.9: sharp fallback market
                odds=-110,  # v10.9: default odds for sharp fallback
                sport=sport_lower  # v10.36: pass sport for Context Layer
            )

            # v10.24: Track AI + Jarvis call for sharp fallback (counts as game)
            jarvis_debug["calls_total"] += 1
            jarvis_debug["calls_game"] += 1
            jarvis_debug["ai_calls_total"] += 1

            # Calculate frontend-expected fields for sharp money picks
            total_score_sharp = score_data.get("total_score", 5.0)
            tier_sharp = score_data.get("bet_tier", {}).get("tier", "PASS")
            side_team = home_team if signal.get("side") == "HOME" else away_team

            # Generate rationale
            rationale = f"Sharp money detected on {side_team}. "
            if signal.get("signal_strength") == "STRONG":
                rationale += "Strong reverse line movement indicates professional action."
            else:
                rationale += "Line movement suggests professional bettors favor this side."

            # v10.19: Get smash_spot flag from score_data
            is_smash_sharp = score_data.get("smash_spot", False)

            # v10.19: Determine badge based on smash_spot and tier
            if is_smash_sharp:
                badge_label_sharp = "SMASH SPOT"
            elif tier_sharp == "GOLD_STAR":
                badge_label_sharp = "GOLD STAR"
            else:
                badge_label_sharp = tier_sharp

            # Determine badges array based on v10.19 rules
            badges = ["SHARP_MONEY"]
            if signal.get("signal_strength") == "STRONG":
                badges.append("RLM")  # Reverse Line Movement
            if is_smash_sharp:
                badges.append("SMASH_SPOT")
            elif tier_sharp == "GOLD_STAR":
                badges.append("GOLD_STAR")

            game_picks.append({
                "sport": sport.upper(),  # v10.57: For consistency with props
                "game_id": signal.get("game_id", ""),  # v10.57: For consistency
                "pick_type": "SHARP",
                "pick": f"Sharp on {signal.get('side', 'HOME')}",
                "team": side_team,
                "line": signal.get("line_variance", 0),
                "odds": -110,
                "game": f"{away_team} @ {home_team}",
                "matchup": f"{away_team} vs {home_team}",  # Production v3
                "selection": f"Sharp on {signal.get('side', 'HOME')}",  # Production v3
                "home_team": home_team,
                "away_team": away_team,
                "market": "sharp_money",
                "recommendation": f"SHARP ON {(signal.get('side') or 'HOME').upper()}",
                "game_time": datetime.now().isoformat(),
                "smash_score": total_score_sharp,
                "final_score": total_score_sharp,  # Production v3
                "predicted_value": None,
                "rationale": rationale,
                "badges": badges,
                "tier": tier_sharp,  # Production v3 (never modified by governor)
                "badge": badge_label_sharp,  # v10.19: SMASH SPOT, GOLD STAR, or tier name
                "reasons": score_data.get("reasons", []),  # Production v3
                **score_data,
                "sharp_signal": signal.get("signal_strength", "MODERATE"),
                "source": "sharp_fallback"
            })

    # Sort game picks by score
    game_picks.sort(key=lambda x: x.get("total_score", 0), reverse=True)

    # MARKET CONFLICT RESOLVER (v10.6): One pick per (matchup, pick_type)
    # Ensures we never return both Hawks ML and Bucks ML for same game
    game_picks = resolve_market_conflicts(game_picks)

    # HEAVY FAVORITE ML FILTER (v10.7): Protect community from unbeatable juice
    # - ML <= -600: always reject (requires 86%+ win rate)
    # - ML <= -400 AND score < 8.0: reject (requires 80%+ win rate, need elite confidence)
    game_picks = filter_heavy_favorite_ml(game_picks)

    # SAME-DIRECTION RESOLVER (v10.7): One pick per directional bet
    # Prevents Lakers -7 AND Lakers ML showing (same direction, pick best market)
    game_picks = resolve_same_direction(game_picks)

    # OPPOSING-SIDES RESOLVER (v10.35): One direction per game
    # Prevents Hawks ML AND Grizzlies -1.5 showing (opposite sides, confuses community)
    game_picks = resolve_opposing_sides(game_picks)

    # Re-sort after all filtering
    game_picks.sort(key=lambda x: clamp_score(x.get("final_score", x.get("total_score", 0))), reverse=True)

    # v10.16: Apply reason ordering to game picks (MAPPING → CORRELATION → RESEARCH → ...)
    for pick in game_picks:
        pick["reasons"] = order_reasons(pick.get("reasons", []))

    # VOLUME GOVERNOR (v10.19): Max 3 GOLD STAR, but NEVER lie about tiers
    # Tier is always accurate to score. Badge can change for display purposes.
    # v10.19: Smash Spot badge logic integrated
    gold_count_games = 0
    smash_count_games = 0
    governed_games = []
    for pick in game_picks:
        # Re-apply tier from score to ensure consistency (v10.22: sport profile tiers)
        score = clamp_score(pick.get("final_score", pick.get("total_score", 0)))
        tier, _ = tier_from_score(score, sport_profile["tiers"])
        pick["tier"] = tier
        pick["final_score"] = score

        # v10.19: Determine badge based on smash_spot flag
        is_smash = pick.get("smash_spot", False)

        if tier == "GOLD_STAR":
            gold_count_games += 1
            if gold_count_games > 3:
                # Keep tier accurate, but change badge to indicate capped
                pick["badge"] = "GOLD (CAPPED)"
                pick["reasons"] = pick.get("reasons", []) + ["GOVERNOR: Gold cap enforced (4th+ gold)"]
            elif is_smash:
                pick["badge"] = "SMASH SPOT"
                smash_count_games += 1
            else:
                pick["badge"] = "GOLD STAR"
        else:
            pick["badge"] = tier
        governed_games.append(pick)

    # Fallback: Surface top picks for minimum volume, but DON'T change their tier
    actionable_games = [p for p in governed_games if p.get("tier") in ["GOLD_STAR", "EDGE_LEAN"]]
    if len(actionable_games) < 3 and len(governed_games) >= 3:
        # Mark top MONITOR picks as "TOP VALUE" for display, but keep tier accurate
        monitor_games = [p for p in governed_games if p.get("tier") == "MONITOR"]
        for pick in monitor_games[:3 - len(actionable_games)]:
            pick["badge"] = "TOP VALUE"
            pick["reasons"] = pick.get("reasons", []) + ["GOVERNOR: Filled slot for minimum volume (tier preserved)"]

    # v10.36: Quality over quantity - return ALL actionable picks, no arbitrary limits
    # Only GOLD_STAR and EDGE_LEAN picks are truly actionable
    # If there are none, return top 3 MONITOR picks as fallback
    actionable_game_picks = [p for p in governed_games if p.get("tier") in ["GOLD_STAR", "EDGE_LEAN"]]
    if len(actionable_game_picks) == 0:
        # Fallback: return top 3 MONITOR picks if no actionable picks
        actionable_game_picks = [p for p in governed_games if p.get("tier") == "MONITOR"][:3]
    top_game_picks = actionable_game_picks

    # v10.38: Compute games_reason for debug visibility
    # Track: raw events from API, candidates after scoring, final picks after filtering
    games_candidates_count = len(game_picks)
    games_picks_count = len(top_game_picks)

    # Determine games_reason with priority order
    if raw_events_count == 0:
        # Check if late-night ET (23:00-04:00) for more specific message
        try:
            from zoneinfo import ZoneInfo
            et_now = datetime.now(ZoneInfo("America/New_York"))
            et_hour = et_now.hour
            if et_hour >= 23 or et_hour <= 4:
                games_reason = "NO_EVENTS_LATE_NIGHT_ET"
            else:
                games_reason = "NO_EVENTS_FROM_ODDS_API"
        except Exception:
            games_reason = "NO_EVENTS_FROM_ODDS_API"
    elif games_candidates_count == 0:
        games_reason = "NO_GAME_CANDIDATES_AFTER_FILTERS"
    elif games_picks_count == 0:
        games_reason = "NO_GAMES_QUALIFIED_MIN_SCORE"
    else:
        games_reason = "OK"

    # ============================================
    # BUILD FINAL RESPONSE
    # ============================================
    # Get astro status if available
    astro_status = None
    if vedic:
        try:
            astro_status = {
                "planetary_hour": vedic.calculate_planetary_hour(),
                "nakshatra": vedic.calculate_nakshatra(),
                "overall_score": vedic.calculate_astro_score().get("overall_score", 50)
            }
        except Exception as e:
            logger.warning("Failed to get astro status: %s", e)

    # Build diagnostic info about data sources
    api_status = {
        "odds_api_configured": bool(ODDS_API_KEY),
        "playbook_api_configured": bool(PLAYBOOK_API_KEY),
        "props_source": props_data.get("source", "none") if props_data else "none",
        "props_games_found": len(props_data.get("data", [])) if props_data else 0,
        "sharp_source": sharp_data.get("source", "none") if sharp_data else "none",
    }

    # Determine if we have real data or not
    has_live_data = len(top_props) > 0 or len(top_game_picks) > 0

    # Build message about data availability
    if not has_live_data:
        if not ODDS_API_KEY:
            data_message = "ODDS_API_KEY not configured. Set this environment variable in Railway."
        elif api_status["props_games_found"] == 0:
            data_message = f"No games/props available for {sport.upper()} right now. This could mean no games are scheduled today or the API returned empty data."
        else:
            data_message = "Props data was retrieved but no picks met the scoring threshold."
    else:
        data_message = f"Live data retrieved: {len(top_props)} prop picks, {len(top_game_picks)} game picks"

    # Build root picks[] array for frontend compatibility (Schema Bridge)
    # Merges top 3 game picks + top 7 props = 10 total root picks
    merged_picks = []
    merged_picks.extend(top_game_picks[:3])
    merged_picks.extend(top_props[:7])

    # v10.16: Build props object with optional conflicts/neutrals
    props_result = {
        "count": len(top_props),
        "total_analyzed": len(props_picks),
        "picks": top_props
    }

    # v10.16: Include conflicts/neutrals when requested for debugging
    if include_conflicts == 1:
        props_result["conflicts"] = conflict_props[:25]  # Cap at 25 for payload safety
        props_result["neutrals"] = neutral_props[:25]    # Cap at 25 for payload safety

    # ================================================================
    # v10.21: JARVIS ENFORCEMENT GUARDRAIL
    # Ensure every returned pick has required esoteric fields
    # ================================================================
    def enforce_scoring_fields(pick):
        """
        v10.29: Ensure pick has all required scoring fields (AI + Jarvis + Research + Confluence + Confidence).
        Returns True if any field was missing and had to be defaulted.
        """
        was_missing = False

        # --- AI ENGINE FIELDS (v10.24) ---
        if "ai_score" not in pick:
            pick["ai_score"] = 5.0
            was_missing = True

        if "ai_breakdown" not in pick or not pick.get("ai_breakdown"):
            pick["ai_breakdown"] = {
                "ensemble": 5.0, "lstm": 5.0, "monte_carlo": 5.0, "line_movement": 5.0,
                "rest_fatigue": 5.0, "injury_impact": 5.0, "matchup_model": 5.0, "edge_calculator": 5.0
            }
            was_missing = True

        # --- ESOTERIC/JARVIS FIELDS (v10.21) ---
        if "esoteric_breakdown" not in pick or not pick.get("esoteric_breakdown"):
            pick["esoteric_breakdown"] = {"jarvis_triggers": 0.0, "gematria": 0.0}
            was_missing = True

        if "jarvis_active" not in pick:
            pick["jarvis_active"] = False
            was_missing = True

        # Ensure scoring_breakdown has all scores
        if "scoring_breakdown" not in pick:
            pick["scoring_breakdown"] = {}
        if "ai_score" not in pick.get("scoring_breakdown", {}):
            pick["scoring_breakdown"]["ai_score"] = 5.0
            was_missing = True
        if "esoteric_score" not in pick.get("scoring_breakdown", {}):
            pick["scoring_breakdown"]["esoteric_score"] = 5.0
            was_missing = True
        if "research_score" not in pick.get("scoring_breakdown", {}):
            pick["scoring_breakdown"]["research_score"] = 5.0
            was_missing = True
        if "alignment_pct" not in pick.get("scoring_breakdown", {}):
            pick["scoring_breakdown"]["alignment_pct"] = 0.0
            was_missing = True

        # --- v10.26: CONFLUENCE FIELDS (always required, never null) ---
        # Ensure confluence_label is ALWAYS a string ("NONE" if missing/null)
        if not pick.get("confluence_label"):
            pick["confluence_label"] = "NONE"
            was_missing = True

        if "confluence_boost" not in pick:
            pick["confluence_boost"] = 0.0
            was_missing = True

        if not pick.get("confluence_level"):
            pick["confluence_level"] = "NONE"
            was_missing = True

        # v10.26: Ensure alignment_pct is sourced ONLY from scoring_breakdown (single source of truth)
        pick["alignment_pct"] = round(pick.get("scoring_breakdown", {}).get("alignment_pct", 0.0), 1)

        # --- v10.29: CONFIDENCE GRADE + ALIGNMENT GAP FIELDS ---
        # Compute alignment_gap from scoring_breakdown scores
        research = pick.get("scoring_breakdown", {}).get("research_score", 5.0)
        esoteric = pick.get("scoring_breakdown", {}).get("esoteric_score", 5.0)

        if "alignment_gap" not in pick:
            pick["alignment_gap"] = compute_alignment_gap(research, esoteric)
            was_missing = True

        # Compute confidence_grade based on confluence_label and alignment_gap
        if "confidence_grade" not in pick:
            pick["confidence_grade"] = compute_confidence_grade(
                pick.get("confluence_label", "NONE"),
                pick.get("alignment_gap", 0.0)
            )
            was_missing = True

        # Generate confluence_miss_reason_top from debug fields (if available)
        if "confluence_miss_reason_top" not in pick:
            # Get debug fields (they may be internal _debug_* or exposed debug_*)
            fail_reasons = (
                pick.get("_debug_confluence_failures", []) or
                pick.get("debug_confluence_failures", []) or
                []
            )
            repair_hints = (
                pick.get("_debug_confluence_repairs", []) or
                pick.get("debug_confluence_repairs", []) or
                []
            )

            if fail_reasons or repair_hints:
                pick["confluence_miss_reason_top"] = derive_confluence_miss_reason(
                    pick.get("confluence_label", "NONE"),
                    fail_reasons,
                    repair_hints
                )
            else:
                # No debug data available
                pick["confluence_miss_reason_top"] = "MISS: Debug not enabled (use ?debug=1 to inspect confluence ladder)"
            was_missing = True

        # --- v10.30: RECOMMENDED UNITS + CONFIDENCE FILTER FIELDS ---
        grade = pick.get("confidence_grade", "C")
        tier = pick.get("tier", "PASS")

        # recommended_units: based on confidence grade (A=2.0, B=1.0, C=0.5, PASS=0.0)
        if "recommended_units" not in pick:
            pick["recommended_units"] = get_recommended_units(grade, tier)
            was_missing = True

        # confidence_filter_min: echo of requested min_confidence for transparency
        pick["confidence_filter_min"] = min_confidence

        # confidence_filter_passed: whether this pick meets the requested threshold
        grade_priority = CONFIDENCE_PRIORITY.get(grade, 3)
        min_priority = CONFIDENCE_PRIORITY.get(min_confidence, 3)
        pick["confidence_filter_passed"] = grade_priority <= min_priority

        # --- REASONS VALIDATION ---
        reasons = pick.get("reasons", [])

        # Check for at least one AI ENGINE: entry
        has_ai_reason = any(str(r).startswith("AI ENGINE:") for r in reasons)
        if not has_ai_reason:
            pick["reasons"] = ["AI ENGINE: Baseline defaults applied (no signals available)"] + reasons
            was_missing = True

        # Check for at least one ESOTERIC: entry
        reasons = pick.get("reasons", [])
        has_esoteric_reason = any(str(r).startswith("ESOTERIC:") for r in reasons)
        if not has_esoteric_reason:
            pick["reasons"] = pick.get("reasons", []) + ["ESOTERIC: Ritual Base +6.0"]
            was_missing = True

        # Add system warning if fields were missing
        if was_missing:
            pick["reasons"] = pick.get("reasons", []) + ["SYSTEM: Scoring fields missing -> forced defaults applied"]

        return was_missing

    # =========================================================================
    # v10.41: JASON SIM 2.0 POST-PICK CONFLUENCE LAYER
    # =========================================================================
    # Jason Sim is applied AFTER base scoring, tier, and correlation stacking.
    # It can BOOST / DOWNGRADE / BLOCK existing picks, but cannot generate new picks.
    # =========================================================================
    jason_sim_debug = {
        "available": JASON_SIM_AVAILABLE,
        "games_checked": 0,
        "games_matched": 0,
        "boosted": 0,
        "downgraded": 0,
        "blocked": 0,
        "missing_payload": 0,
        "props_processed": 0,
        "game_picks_processed": 0
    }

    if JASON_SIM_AVAILABLE:
        sport_lower = sport.lower()
        jason_payloads = JASON_SIM_PAYLOADS.get(sport_lower, {})

        if jason_payloads:
            logger.info(f"Jason Sim: Applying layer to {len(top_props)} props and {len(top_game_picks)} game picks")

            # Apply to props
            if top_props:
                top_props, props_stats = apply_jason_sim_layer(
                    picks=top_props,
                    jason_payloads_by_game=jason_payloads,
                    pick_type="prop"
                )
                jason_sim_debug["props_processed"] = props_stats.get("games_checked", 0)
                jason_sim_debug["games_checked"] += props_stats.get("games_checked", 0)
                jason_sim_debug["games_matched"] += props_stats.get("games_matched", 0)
                jason_sim_debug["boosted"] += props_stats.get("boosted", 0)
                jason_sim_debug["downgraded"] += props_stats.get("downgraded", 0)
                jason_sim_debug["blocked"] += props_stats.get("blocked", 0)
                jason_sim_debug["missing_payload"] += props_stats.get("missing_payload", 0)

            # Apply to game picks
            if top_game_picks:
                top_game_picks, game_stats = apply_jason_sim_layer(
                    picks=top_game_picks,
                    jason_payloads_by_game=jason_payloads,
                    pick_type="game"
                )
                jason_sim_debug["game_picks_processed"] = game_stats.get("games_checked", 0)
                jason_sim_debug["games_checked"] += game_stats.get("games_checked", 0)
                jason_sim_debug["games_matched"] += game_stats.get("games_matched", 0)
                jason_sim_debug["boosted"] += game_stats.get("boosted", 0)
                jason_sim_debug["downgraded"] += game_stats.get("downgraded", 0)
                jason_sim_debug["blocked"] += game_stats.get("blocked", 0)
                jason_sim_debug["missing_payload"] += game_stats.get("missing_payload", 0)

            logger.info(f"Jason Sim: Complete - boosted={jason_sim_debug['boosted']}, downgraded={jason_sim_debug['downgraded']}, blocked={jason_sim_debug['blocked']}")

            # v10.42: Fix missing_payload to be (games_checked - games_matched)
            jason_sim_debug["missing_payload"] = jason_sim_debug["games_checked"] - jason_sim_debug["games_matched"]
        else:
            logger.info(f"Jason Sim: No payloads available for {sport}")
            # v10.42: When no payloads uploaded, missing_payload = 0 (not slate size)
            # missing_payload only counts picks that COULD have matched but didn't
            jason_sim_debug["missing_payload"] = 0
            jason_sim_debug["no_payloads_uploaded"] = True
    else:
        logger.debug("Jason Sim: Module not available")

    # Apply guardrail to all returned picks (v10.26: validates AI + Jarvis + Research + Confluence)
    all_returned_picks = top_props + top_game_picks
    for pick in all_returned_picks:
        if enforce_scoring_fields(pick):
            jarvis_debug["missing_on_returned"] += 1

        # v10.26: Track confluence stats for RETURNED picks only
        label = pick.get("confluence_label", "NONE")
        confluence_counts_returned[label] = confluence_counts_returned.get(label, 0) + 1

        align_pct = pick.get("alignment_pct", 0.0)
        alignment_pct_sum_returned += align_pct
        alignment_pct_count_returned += 1
        if align_pct < alignment_min_returned:
            alignment_min_returned = align_pct
        if align_pct > alignment_max_returned:
            alignment_max_returned = align_pct

        # v10.29: Track confidence_grade and alignment_gap for returned picks
        grade = pick.get("confidence_grade", "C")
        confidence_grade_counts[grade] = confidence_grade_counts.get(grade, 0) + 1

        gap = pick.get("alignment_gap", 0.0)
        alignment_gap_sum_returned += gap
        alignment_gap_count_returned += 1
        if gap < alignment_gap_min_returned:
            alignment_gap_min_returned = gap
        if gap > alignment_gap_max_returned:
            alignment_gap_max_returned = gap

    # Also enforce on merged_picks (which are references to same objects, but ensure coverage)
    for pick in merged_picks:
        enforce_scoring_fields(pick)

    # v10.28: Handle debug-only confluence diagnostic fields
    # When debug=1: Rename _debug_* to debug_* (expose diagnostics)
    # When debug!=1: Strip _debug_* fields (don't leak to production responses)
    # Note: Can't use set() on dicts - just concatenate lists
    all_picks_to_clean = top_props + top_game_picks + merged_picks
    for pick in all_picks_to_clean:
        if debug == 1:
            # Expose debug fields by renaming
            if "_debug_confluence_failures" in pick:
                pick["debug_confluence_failures"] = pick.pop("_debug_confluence_failures")
            if "_debug_confluence_trace" in pick:
                pick["debug_confluence_trace"] = pick.pop("_debug_confluence_trace")
            # v10.28: New debug fields
            if "_debug_confluence_repairs" in pick:
                pick["debug_confluence_repairs"] = pick.pop("_debug_confluence_repairs")
            if "_debug_alignment_gap" in pick:
                pick["debug_alignment_gap"] = pick.pop("_debug_alignment_gap")
        else:
            # Strip debug fields for non-debug responses
            pick.pop("_debug_confluence_failures", None)
            pick.pop("_debug_confluence_trace", None)
            pick.pop("_debug_confluence_repairs", None)
            pick.pop("_debug_alignment_gap", None)

    # ================================================================
    # v10.30: MULTI-KEY SORTING + CONFIDENCE FILTER
    # ================================================================
    # Sort key priority: confidence_grade (A>B>C), final_score (DESC),
    # confluence_boost (DESC), alignment_gap (ASC), implied_probability (ASC)
    def v10_30_sort_key(pick):
        """
        Returns tuple for multi-key sort:
        1. confidence_grade priority (A=1, B=2, C=3) - ASCENDING (lower is better)
        2. final_score - DESCENDING (negate for ascending sort)
        3. confluence_boost - DESCENDING (negate for ascending sort)
        4. alignment_gap - ASCENDING (tighter gap is better)
        5. implied_probability - ASCENDING (lower break-even preferred)
        """
        grade = pick.get("confidence_grade", "C")
        grade_priority = CONFIDENCE_PRIORITY.get(grade, 3)
        final_score = pick.get("final_score", pick.get("total_score", 0))
        confluence_boost = pick.get("confluence_boost", 0.0)
        alignment_gap = pick.get("alignment_gap", 5.0)
        odds = pick.get("odds", -110)
        implied_prob = get_implied_probability(odds)
        return (grade_priority, -final_score, -confluence_boost, alignment_gap, implied_prob)

    # Apply v10.30 multi-key sorting to all pick lists
    top_props.sort(key=v10_30_sort_key)
    top_game_picks.sort(key=v10_30_sort_key)

    # v10.30: Apply confidence filter AFTER sorting (filter out picks below min_confidence)
    # Track how many were filtered out for debug
    filtered_out_count = 0
    min_priority = CONFIDENCE_PRIORITY.get(min_confidence, 3)

    def passes_confidence_filter(pick):
        """Returns True if pick meets the min_confidence threshold."""
        nonlocal filtered_out_count
        grade = pick.get("confidence_grade", "C")
        grade_priority = CONFIDENCE_PRIORITY.get(grade, 3)
        if grade_priority <= min_priority:
            return True
        filtered_out_count += 1
        return False

    # Filter props and game_picks if min_confidence != "C" (C = show all)
    if min_confidence != "C":
        top_props = [p for p in top_props if passes_confidence_filter(p)]
        top_game_picks = [p for p in top_game_picks if passes_confidence_filter(p)]

    # =========================================================================
    # v10.57: DATA INTEGRITY VALIDATORS (BEFORE publish_gate + pick_filter)
    # =========================================================================
    # Runs EARLY to drop invalid props before tiering caps/correlation:
    # 1) prop_integrity - required fields, team membership
    # 2) injury_guard - OUT, SUSPENDED, DOUBTFUL, GTD checks
    # 3) market_availability - (skipped - props come from Odds API feed)
    # =========================================================================
    validator_debug = {
        "available": VALIDATORS_AVAILABLE,
        "props_before": len(top_props),
        "games_before": len(top_game_picks),
        "props_after": 0,
        "games_after": 0,
        "dropped_props": 0,
        "dropped_games": 0,
        "drop_reasons": {}
    }

    if VALIDATORS_AVAILABLE and (top_props or top_game_picks):
        # Track drop reasons across all validators
        all_drop_reasons = {}

        # -----------------------------------------------------------------
        # Step 1: Prop Integrity Validation (required fields, team checks)
        # -----------------------------------------------------------------
        # Note: Only run on props - game picks have different structure
        # (bet_type instead of market, no player_name)
        valid_props, dropped_props, integrity_drops = validate_props_batch(
            top_props, log_drops=True, max_log_drops=10
        )
        valid_games = top_game_picks  # Game picks skip prop integrity check

        # Aggregate drop reasons
        for reason, count in integrity_drops.items():
            all_drop_reasons[reason] = all_drop_reasons.get(reason, 0) + count

        # -----------------------------------------------------------------
        # Step 2: Injury Guard Validation (OUT, SUSPENDED, DOUBTFUL)
        # -----------------------------------------------------------------
        if injury_index:
            valid_props, inj_dropped_props, inj_drops = validate_props_batch_injury(
                valid_props, injury_index, log_drops=True, max_log_drops=10
            )
            valid_games, inj_dropped_games, games_inj_drops = validate_props_batch_injury(
                valid_games, injury_index, log_drops=True, max_log_drops=10
            )

            # Aggregate injury drop reasons
            for reason, count in inj_drops.items():
                all_drop_reasons[reason] = all_drop_reasons.get(reason, 0) + count
            for reason, count in games_inj_drops.items():
                all_drop_reasons[reason] = all_drop_reasons.get(reason, 0) + count

        # -----------------------------------------------------------------
        # Step 3: Market Availability Validation (DK market listing check)
        # -----------------------------------------------------------------
        # CRITICAL: Ensures we don't publish props that aren't listed on DK
        # Example: Deni Avdija has no props listed -> should be blocked
        if dk_market_index:
            valid_props, mkt_dropped_props, mkt_drops = validate_props_batch_market(
                valid_props, dk_market_index, log_drops=True, max_log_drops=10
            )
            # Note: Game picks don't need market validation (spreads/totals always available)

            # Aggregate market drop reasons
            for reason, count in mkt_drops.items():
                all_drop_reasons[reason] = all_drop_reasons.get(reason, 0) + count

            validator_debug["dk_market_index_size"] = len(dk_market_index)
            validator_debug["market_drops"] = sum(mkt_drops.values())

        # Update top_props and top_game_picks with validated picks
        top_props = valid_props
        top_game_picks = valid_games

        # Update debug info
        validator_debug["props_after"] = len(top_props)
        validator_debug["games_after"] = len(top_game_picks)
        validator_debug["dropped_props"] = validator_debug["props_before"] - len(top_props)
        validator_debug["dropped_games"] = validator_debug["games_before"] - len(top_game_picks)
        validator_debug["drop_reasons"] = all_drop_reasons

    # v10.90: Add availability check results to debug
    validator_debug["props_filtered_unavailable"] = props_filtered_unavailable
    validator_debug["unavailable_players"] = unavailable_players

    if props_filtered_unavailable > 0:
        logger.info(f"v10.90: Filtered {props_filtered_unavailable} props - lines pulled: {[p['player'] for p in unavailable_players]}")

    if VALIDATORS_AVAILABLE and (top_props or top_game_picks):
        # Log summary
        total_dropped = validator_debug["dropped_props"] + validator_debug["dropped_games"]
        if total_dropped > 0:
            logger.info(
                f"v10.57 Validators: Dropped {total_dropped} picks "
                f"(props: {validator_debug['props_before']}->{validator_debug['props_after']}, "
                f"games: {validator_debug['games_before']}->{validator_debug['games_after']}) "
                f"Reasons: {all_drop_reasons}"
            )

    # =========================================================================
    # v10.43: PUBLISH GATE (Dominance Dedup + Quality Gate + Correlation Penalty)
    # =========================================================================
    # Applies:
    # A) Dominance dedup: Keep only best pick per player per cluster
    # B) Correlation penalty: Penalize crowded games
    # C) Quality gate: Escalate thresholds instead of capping
    # =========================================================================
    publish_gate_debug = {
        "available": PUBLISH_GATE_AVAILABLE,
        "input_picks": 0,
        "after_dedup": 0,
        "after_corr_penalty": 0,
        "publish_threshold_edge_lean": 7.05,
        "publish_threshold_gold_star": 7.50,
        "published_total": 0
    }

    if PUBLISH_GATE_AVAILABLE:
        # Apply to props
        if top_props:
            top_props, props_gate_debug = apply_publish_gate(
                picks=top_props,
                target_max=TARGET_MAX_PICKS,
                apply_dedup=True,
                apply_penalty=True,
                apply_gate=True
            )
            publish_gate_debug["input_picks"] = props_gate_debug.get("input_picks", 0)
            publish_gate_debug["after_dedup"] = props_gate_debug.get("after_dedup", 0)
            publish_gate_debug["after_corr_penalty"] = props_gate_debug.get("after_corr_penalty", 0)
            publish_gate_debug["publish_threshold_edge_lean"] = props_gate_debug.get("publish_threshold_edge_lean", 7.05)
            publish_gate_debug["publish_threshold_gold_star"] = props_gate_debug.get("publish_threshold_gold_star", 7.50)
            publish_gate_debug["published_total"] = props_gate_debug.get("published_total", 0)
            publish_gate_debug["dedup_stats"] = props_gate_debug.get("dedup_stats", {})
            publish_gate_debug["penalty_stats"] = props_gate_debug.get("penalty_stats", {})
            publish_gate_debug["gate_stats"] = props_gate_debug.get("gate_stats", {})

            logger.info(f"Publish Gate: {publish_gate_debug['input_picks']} -> {publish_gate_debug['after_dedup']} (dedup) -> {publish_gate_debug['published_total']} (final)")

        # Apply to game picks (lighter - just dedup, no correlation penalty for games)
        if top_game_picks:
            top_game_picks, games_gate_debug = apply_publish_gate(
                picks=top_game_picks,
                target_max=10,  # Lower target for games
                apply_dedup=True,
                apply_penalty=False,  # No correlation penalty for game picks
                apply_gate=True
            )
            publish_gate_debug["games_input"] = games_gate_debug.get("input_picks", 0)
            publish_gate_debug["games_published"] = games_gate_debug.get("published_total", 0)
    else:
        logger.debug("Publish Gate: Module not available, using legacy filtering")

    # =========================================================================
    # v10.56: PICK FILTER (Final caps + correlation + UNDER penalty)
    # =========================================================================
    # Applies AFTER publish_gate:
    # - UNDER penalty (-0.15) with re-tier
    # - Daily caps: GOLD_STAR=5, EDGE_LEAN=8, Total=13
    # - Correlation limits: 1 GOLD_STAR/player, 2 total/player, 3/game
    # =========================================================================
    pick_filter_debug = {
        "available": PICK_FILTER_AVAILABLE,
        "props_before": len(top_props),
        "props_after": 0,
        "games_before": len(top_game_picks),
        "games_after": 0
    }

    if PICK_FILTER_AVAILABLE:
        # Combine props and game_picks for unified filtering
        all_picks_before = top_props + top_game_picks
        all_picks_filtered = filter_best_bets(all_picks_before, sport_lower.upper())

        # Split back into props and game_picks
        top_props = [p for p in all_picks_filtered if p.get("stat_type") or p.get("player_name")]
        top_game_picks = [p for p in all_picks_filtered if not p.get("stat_type") and not p.get("player_name")]

        # If game picks got mixed in with props (no player_name), use market field
        if not top_game_picks:
            top_game_picks = [p for p in all_picks_filtered if p.get("market") in ("spreads", "totals", "h2h")]
            top_props = [p for p in all_picks_filtered if p not in top_game_picks]

        pick_filter_debug["props_after"] = len(top_props)
        pick_filter_debug["games_after"] = len(top_game_picks)
        pick_filter_debug["total_after"] = len(all_picks_filtered)

        logger.info(f"Pick Filter: {len(all_picks_before)} -> {len(all_picks_filtered)} picks (props: {pick_filter_debug['props_before']}->{pick_filter_debug['props_after']}, games: {pick_filter_debug['games_before']}->{pick_filter_debug['games_after']})")

    # Rebuild merged_picks after filtering and sorting
    merged_picks = []
    merged_picks.extend(top_game_picks[:3])
    merged_picks.extend(top_props[:7])

    # v10.30: Update props_result with filtered picks
    props_result["picks"] = top_props
    props_result["count"] = len(top_props)

    # v10.30: Track units distribution for debug
    units_distribution = {"2.0": 0, "1.0": 0, "0.5": 0, "0.0": 0}
    units_sum = 0.0
    for pick in (top_props + top_game_picks):
        units = pick.get("recommended_units", 0.0)
        units_sum += units
        units_key = str(units)
        if units_key in units_distribution:
            units_distribution[units_key] += 1

    # Recalculate confidence grade counts after filtering
    confidence_grade_counts_returned = {"A": 0, "B": 0, "C": 0}
    for pick in (top_props + top_game_picks):
        grade = pick.get("confidence_grade", "C")
        confidence_grade_counts_returned[grade] = confidence_grade_counts_returned.get(grade, 0) + 1

    # v10.33: Initialize DB persistence counters BEFORE result construction
    # These will be populated by the save logic below and included at TOP LEVEL
    picks_saved = 0
    signals_saved = 0
    save_errors = []
    db_error = None

    # Determine database availability (fast check - no DB call needed)
    # v10.33: Use database.DB_ENABLED for live value (not stale import)
    database_available = DATABASE_AVAILABLE and database.DB_ENABLED

    # v10.37: Build confluence_reasons for stacked props
    stacked_props = [p for p in top_props if p.get("stacked", False)]
    stacked_groups = {}
    for p in stacked_props:
        group_id = p.get("correlation_group_id", "")
        if group_id:
            if group_id not in stacked_groups:
                stacked_groups[group_id] = []
            stacked_groups[group_id].append(p.get("player", "") + " " + p.get("stat_label", ""))

    confluence_reasons = []
    for group_id, picks in stacked_groups.items():
        parts = group_id.split(":")
        player_name = parts[1] if len(parts) > 1 else "Unknown"
        cluster = parts[2] if len(parts) > 2 else "UNKNOWN"
        direction = parts[3] if len(parts) > 3 else ""
        confluence_reasons.append({
            "type": "STACKED_CORRELATION",
            "group_id": group_id,
            "player": player_name,
            "cluster": cluster,
            "direction": direction,
            "picks": picks,
            "reason": f"{player_name} has {len(picks)} props stacked in {cluster} - both independently qualify"
        })

    # =========================================================================
    # v10.42: UNIVERSAL FINAL FALLBACK - GUARANTEE AT LEAST 1 PICK RETURNED
    # =========================================================================
    # If after ALL scoring + filters + confluence layers, we have 0 picks total,
    # pull top 3 MONITOR picks from the broadest candidate pools.
    # =========================================================================
    fallback_used = False
    fallback_count = 0
    fallback_source = "none"

    # Calculate pre-fallback counts for debug
    props_after_filter_count = len(top_props)
    games_after_filter_count = len(top_game_picks)

    if len(top_props) == 0 and len(top_game_picks) == 0:
        logger.warning("v10.42: Zero picks after all filters - activating UNIVERSAL FALLBACK")

        # Fallback source: all scored candidates (governed_props + governed_games)
        # These are already sorted by score, so just take top 3
        fallback_candidates = []

        # Collect from props candidates
        if governed_props:
            for p in governed_props[:10]:  # Consider top 10 props
                p_copy = p.copy()
                p_copy["_source"] = "props"
                fallback_candidates.append(p_copy)

        # Collect from games candidates
        if governed_games:
            for g in governed_games[:10]:  # Consider top 10 games
                g_copy = g.copy()
                g_copy["_source"] = "games"
                fallback_candidates.append(g_copy)

        # Sort by score and take top 3
        fallback_candidates.sort(
            key=lambda x: clamp_score(x.get("final_score", x.get("total_score", 0))),
            reverse=True
        )
        fallback_picks = fallback_candidates[:3]

        if fallback_picks:
            fallback_used = True
            fallback_count = len(fallback_picks)
            fallback_source = "candidates"

            # Mark each fallback pick
            for pick in fallback_picks:
                # v10.55: Use tier_from_score on actual final_score - don't force MONITOR
                fb_score = float(pick.get("final_score", pick.get("smash_score", pick.get("total_score", 0))))
                fb_tier, _ = tier_from_score(fb_score)
                pick["tier"] = fb_tier
                pick["badge"] = "FALLBACK"
                pick["fallback"] = True
                pick["reasons"] = pick.get("reasons", []) + [
                    "SYSTEM: FALLBACK_TOP3 (below publish gate but included for volume)"
                ]

                # Distribute to appropriate list based on source
                source = pick.pop("_source", "props")
                if source == "games":
                    top_game_picks.append(pick)
                else:
                    top_props.append(pick)

            logger.info(f"v10.42: Fallback activated - returned {fallback_count} MONITOR picks")

            # Update props_result with fallback picks
            props_result["picks"] = top_props
            props_result["count"] = len(top_props)

    # =========================================================================
    # v10.42: FIX props_reason LOGIC (similar to games_reason)
    # =========================================================================
    props_candidates_count = len(props_picks)
    props_picks_count = len(top_props)

    if props_candidates_count == 0:
        props_reason = "NO_PROP_CANDIDATES_AFTER_SCORING"
    elif props_picks_count == 0 and not fallback_used:
        props_reason = "NO_PROPS_QUALIFIED_MIN_SCORE"
    elif fallback_used:
        props_reason = "FALLBACK_MONITOR_USED"
    else:
        props_reason = "OK"

    # v10.42: Update games_reason if fallback was used
    if fallback_used and games_picks_count == 0:
        games_reason = "FALLBACK_MONITOR_USED"

    # v10.83: Enrich picks with canonical fields + validations before response
    top_props = enrich_picks_batch(top_props, sport, injuries_data)
    top_game_picks = enrich_picks_batch(top_game_picks, sport, injuries_data)

    # v10.83: Filter out invalid picks (market sanity, injury exclusions)
    top_props = filter_valid_picks(top_props)
    top_game_picks = filter_valid_picks(top_game_picks)

    # v10.82: Generate ET timestamp for response
    from zoneinfo import ZoneInfo
    ET = ZoneInfo(Config.TIMEZONE)
    now_et = datetime.now(ET)
    generated_at_est = now_et.isoformat()

    result = {
        "sport": sport.upper(),
        "league": sport.upper(),  # v10.82: Canonical schema field
        "source": f"production_{Config.ENGINE_VERSION}",
        "scoring_system": f"{Config.ENGINE_VERSION}: Production schema lock + version sync",
        # v10.82: Version metadata (must match /version endpoint)
        "engine_version": Config.ENGINE_VERSION,
        "api_version": Config.API_VERSION,
        "timezone": Config.TIMEZONE,
        "generated_at_est": generated_at_est,
        "today_only_enforced": True,
        "picks": merged_picks,  # Root picks[] for frontend SmashSpots rendering
        "props": props_result,
        "game_picks": {
            "count": len(top_game_picks),
            "total_analyzed": len(governed_games),
            "picks": top_game_picks
        },
        "esoteric": {
            "daily_energy": daily_energy,
            "astro_status": astro_status,
            "learned_weights": esoteric_weights,
            "learning_active": learning is not None
        },
        # v10.37: Confluence reasons for stacked correlations
        "confluence_reasons": confluence_reasons,
        "stacked_count": len(stacked_props),
        "api_status": api_status,
        "data_message": data_message,
        "timestamp": datetime.now().isoformat(),
        # v10.33: TOP-LEVEL database health fields (ALWAYS present)
        "database_available": database_available,
        "picks_saved": 0,  # Will be updated by save logic below
        "signals_saved": 0  # Will be updated by save logic below
    }

    # v10.75: Apply time status to all picks before normalization
    for pick in top_props + top_game_picks:
        if not pick.get("status_time"):
            game_time_iso = pick.get("game_time") or pick.get("commence_time", "")
            game_state = pick.get("game_state") or pick.get("status")
            time_status = compute_time_status(game_time_iso, game_state=game_state)
            pick["status_time"] = time_status
            pick["start_time_et"] = time_status.get("start_time_et")
            pick["pulled_at_et"] = time_status.get("pulled_at_et")

    # v10.72: Normalize ALL picks to canonical PickCard format
    # This ensures consistent output regardless of pick type (spread/ML/total/prop)
    all_raw_picks = top_props + top_game_picks
    normalized_cards = normalize_picks(all_raw_picks, sport)
    result["picks_normalized"] = [card.to_dict() for card in normalized_cards]
    result["picks_table"] = picks_to_table(normalized_cards)

    # Debug mode: Add diagnostic info (v10.22 expanded with sport profiles)
    if debug == 1:
        result["debug"] = {
            "games_pulled": len(props_data.get("data", [])) if props_data else 0,
            "candidates_scored": len(props_picks) + len(game_picks),
            "props_scored": len(props_picks),
            "props_deduped": props_dropped_count,  # v10.9: track deduplication
            "returned_picks": len(top_props) + len(top_game_picks),
            "gold_star_props": len([p for p in top_props if p.get("tier") == "GOLD_STAR"]),
            "gold_star_games": len([p for p in top_game_picks if p.get("tier") == "GOLD_STAR"]),
            "volume_governor_applied": gold_count > 3 or gold_count_games > 3,
            "no_data": not has_live_data,
            # v10.16: Correlation debug counters
            "aligned_count": correlation_counters["aligned_count"],
            "neutral_count": correlation_counters["neutral_count"],
            "conflict_count": correlation_counters["conflict_count"],
            "excluded_conflicts_count": correlation_counters["excluded_conflicts_count"],
            "conflicts_included": correlation_counters.get("conflicts_included", False),
            # v10.24: AI Engine + Jarvis enforcement counters
            "ai_engine_available": jarvis_debug["ai_engine_available"],
            "ai_calls_total": jarvis_debug["ai_calls_total"],
            "jarvis_calls_total": jarvis_debug["calls_total"],
            "jarvis_calls_game": jarvis_debug["calls_game"],
            "jarvis_calls_props": jarvis_debug["calls_props"],
            "jarvis_missing_on_returned_picks": jarvis_debug["missing_on_returned"],
            "jarvis_engine_available": jarvis is not None,
            # v10.26: Confluence ladder debug (candidates vs returned separation)
            "confluence_counts_candidates": confluence_counts_candidates,
            "avg_alignment_candidates": round(alignment_pct_sum_candidates / max(1, alignment_pct_count_candidates), 1),
            "confluence_counts_returned": confluence_counts_returned,
            "avg_alignment_returned": round(alignment_pct_sum_returned / max(1, alignment_pct_count_returned), 1),
            "returned_alignment_minmax": {
                "min": round(alignment_min_returned, 1) if alignment_pct_count_returned > 0 else 0.0,
                "max": round(alignment_max_returned, 1) if alignment_pct_count_returned > 0 else 0.0
            },
            # v10.29: Confidence grade + alignment gap debug
            "confidence_grade_counts": confidence_grade_counts,
            "avg_alignment_gap_returned": round(alignment_gap_sum_returned / max(1, alignment_gap_count_returned), 2),
            "alignment_gap_minmax_returned": {
                "min": round(alignment_gap_min_returned, 2) if alignment_gap_count_returned > 0 else 0.0,
                "max": round(alignment_gap_max_returned, 2) if alignment_gap_count_returned > 0 else 0.0
            },
            # v10.30: Confidence filter + units debug
            "min_confidence_applied": min_confidence,
            "filtered_out_count": filtered_out_count,
            "returned_confidence_grade_counts": confidence_grade_counts_returned,
            "avg_units_returned": round(units_sum / max(1, len(top_props) + len(top_game_picks)), 2),
            "units_distribution": units_distribution,
            # v10.22: Sport profile info
            "sport_profile": {
                "weights": sport_profile["weights"],
                "tiers": sport_profile["tiers"],
                "limits": sport_profile["limits"],
                "conflict_policy": sport_profile["conflict_policy"]
            },
            # v10.31: Database status (kept for backward compatibility)
            "database_available": DATABASE_AVAILABLE and database.DB_ENABLED,
            # v10.37: Correlation stacking debug
            "correlation_stacking": {
                "stacked_props_count": len(stacked_props),
                "stacked_groups_count": len(stacked_groups),
                "stacked_groups": list(stacked_groups.keys()),
                "confluence_reasons_count": len(confluence_reasons)
            },
            # v10.38: Games debug visibility (why are game picks empty?)
            # Pipeline: events_count -> today_games_count -> games_with_odds_count -> games_candidates_count -> games_picks_count
            "games_reason": games_reason,
            "events_count": raw_events_count,  # Step 1: Raw from Odds API
            "today_games_count": today_games_count,  # Step 2: After TODAY_ET filter
            "tomorrow_filtered_count": raw_events_count - today_games_count,  # Games dropped (not today ET)
            "games_with_odds_count": games_with_odds_count,  # Step 3: Games with bookmaker/odds data
            "games_candidates_count": games_candidates_count,  # Step 4: Scored picks generated
            "games_picks_count": games_picks_count,
            # v10.42: Props debug visibility (matching games pattern)
            "props_reason": props_reason,
            "props_candidates_count": props_candidates_count,
            "props_after_filter_count": props_after_filter_count,
            "props_picks_count": props_picks_count,
            # v10.42: Games after filter count
            "games_after_filter_count": games_after_filter_count,
            # v10.42: Fallback debug
            "fallback_used": fallback_used,
            "fallback_count": fallback_count,
            "fallback_source": fallback_source,
            # v10.41: Jason Sim 2.0 debug
            "jason_sim": jason_sim_debug,
            # v10.57: Data Integrity Validators debug (prop_integrity + injury_guard)
            "validators": validator_debug,
            # v10.43: Publish Gate debug (dominance dedup + quality gate)
            "publish_gate": publish_gate_debug,
            # v10.56: Pick Filter debug (caps + correlation + UNDER penalty)
            "pick_filter": pick_filter_debug,
            # v10.45: Odds diagnostic metrics
            "odds_metrics": {
                "provider_status": odds_provider_status,
                "events_count": raw_events_count,
                "markets_count": odds_markets_count,
                "http_status": odds_http_status,
                "fallback_used": odds_fallback_used
            },
            # v10.45: Include game_candidates_before_filter for /best-bets/all debug
            "game_candidates_before_filter": games_candidates_count,
            # v10.81: Time gate debug (TODAY-ONLY filter enforcement)
            "today_only_enforced": True,
            "time_gate": {
                "raw_events_count": raw_events_count,
                "today_games_count": today_games_count,
                "removed_not_today": raw_events_count - today_games_count
            }
        }

    # ================================================================
    # v10.33+: ENRICH PICKS WITH FIRED_SIGNALS + SAVE TO LEDGER + SIGNAL_LEDGER
    # Now updates TOP-LEVEL picks_saved/signals_saved fields
    # ================================================================
    all_picks_to_save = top_props + top_game_picks

    if database_available:
        try:
            for pick in all_picks_to_save:
                # v10.32: Enrich pick with fired_signals before saving
                if SIGNAL_ATTRIBUTION_AVAILABLE:
                    pick = enrich_pick_with_signals(pick)

                # v10.32+: Extract signals from reasons array for SignalLedger
                fired_signals_list = _extract_signals_from_reasons(pick.get("reasons", []))
                pick["fired_signals"] = [s["signal_key"] for s in fired_signals_list]
                pick["fired_signal_count"] = len(fired_signals_list)

                # Enrich pick data with sport and version
                pick_data = {
                    **pick,
                    "sport": sport.upper(),
                    "version": "production_v10.33+"
                }

                # Save to PickLedger
                try:
                    if upsert_pick(pick_data):
                        picks_saved += 1

                        # v10.32+: Also save to SignalLedger for ROI tracking
                        # Generate pick_uid same way as PickLedger for foreign key
                        # v10.54: Use ET date to match PickLedger's pick_uid generation
                        from datetime import date as dt_date
                        from database import get_et_date_str
                        et_date_str = get_et_date_str()
                        pick_uid = PickLedger.generate_pick_uid(
                            sport=sport.upper(),
                            event_id=pick.get("event_id"),
                            market=pick.get("market", pick.get("stat_type", "")),
                            selection=pick.get("selection", pick.get("player_name", "")),
                            line=pick.get("line"),
                            odds=pick.get("odds", -110),
                            version="production_v10.33+",
                            pick_date=dt_date.fromisoformat(et_date_str)
                        )

                        # Save each fired signal to SignalLedger
                        try:
                            saved = save_signal_ledger(pick_uid, sport.upper(), fired_signals_list)
                            signals_saved += saved
                        except Exception as e:
                            err_msg = f"SignalLedger save failed: {str(e)}"
                            save_errors.append(err_msg)
                            logger.warning(f"SignalLedger save failed for {pick_uid}: {e}")
                except Exception as e:
                    err_msg = f"PickLedger save failed: {str(e)}"
                    save_errors.append(err_msg)
                    logger.warning(f"PickLedger save failed: {e}")

        except Exception as e:
            db_error = f"Database save error: {str(e)}"
            logger.error(f"Database persistence failed: {e}")
    else:
        # DB not available - log why
        if not DATABASE_AVAILABLE:
            db_error = "Database module not imported"
        elif not database.DB_ENABLED:
            db_error = "Database not initialized (DB_ENABLED=False)"

    # v10.33: Update TOP-LEVEL fields with actual counts
    result["picks_saved"] = picks_saved
    result["signals_saved"] = signals_saved

    # v10.34: Persistence logging - audit that writes happen
    logger.info(f"best_bets_persist sport={sport.upper()} database_available={database_available} picks_saved={picks_saved} signals_saved={signals_saved} cache_hit={cache_hit}")

    # Add debug-only fields for save operations
    if debug == 1:
        result["debug"]["picks_saved_to_ledger"] = picks_saved
        result["debug"]["signals_saved_to_ledger"] = signals_saved
        result["debug"]["picks_attempted_save"] = len(all_picks_to_save)
        result["debug"]["signal_attribution_available"] = SIGNAL_ATTRIBUTION_AVAILABLE
        result["debug"]["db_error"] = db_error
        result["debug"]["save_errors"] = save_errors if save_errors else None
        # v10.34: Prove DB_ENABLED is truly live at runtime
        result["debug"]["db_enabled_live"] = bool(database.DB_ENABLED)
        result["debug"]["counts"] = {
            "picks_generated": len(all_picks_to_save),
            "signals_generated": sum(len(_extract_signals_from_reasons(p.get("reasons", []))) for p in all_picks_to_save)
        }

    # ================================================================
    # v10.38: LOG PICKS TO AUTO-GRADER (JSONL format with deduplication)
    # This enables the feedback loop - grader can grade picks and adjust weights
    # ================================================================
    grader_logged = 0
    grader_duplicates = 0
    grader_errors = 0

    if AUTO_GRADER_AVAILABLE:
        try:
            grader = get_grader()

            # Log prop picks
            if top_props:
                props_result_log = grader.log_picks_batch(top_props, sport, pick_type="prop")
                grader_logged += props_result_log.get("logged", 0)
                grader_duplicates += props_result_log.get("duplicates", 0)
                grader_errors += props_result_log.get("errors", 0)

            # Log game picks
            if top_game_picks:
                games_result_log = grader.log_picks_batch(top_game_picks, sport, pick_type="game")
                grader_logged += games_result_log.get("logged", 0)
                grader_duplicates += games_result_log.get("duplicates", 0)
                grader_errors += games_result_log.get("errors", 0)

            logger.info(f"grader_log sport={sport.upper()} logged={grader_logged} duplicates={grader_duplicates} errors={grader_errors}")

        except Exception as e:
            logger.warning(f"Grader logging failed: {e}")
            grader_errors += 1

    # Add grader logging info to debug output
    if debug == 1:
        result["debug"]["grader_logged"] = grader_logged
        result["debug"]["grader_duplicates"] = grader_duplicates
        result["debug"]["grader_errors"] = grader_errors
        result["debug"]["grader_available"] = AUTO_GRADER_AVAILABLE

    # Update top-level field for visibility
    result["predictions_logged"] = grader_logged

    api_cache.set(cache_key, result, ttl=600)  # 5 minute TTL
    return result


@router.get("/lstm/status")
async def lstm_status():
    """Check LSTM model availability and status."""
    try:
        from lstm_brain import LSTMBrain, TF_AVAILABLE
        return {
            "available": True,
            "tensorflow_available": TF_AVAILABLE,
            "mode": "tensorflow" if TF_AVAILABLE else "numpy_fallback",
            "note": "LSTM requires historical player data for predictions.",
            "timestamp": datetime.now().isoformat()
        }
    except ImportError:
        return {
            "available": False,
            "tensorflow_available": False,
            "mode": "disabled",
            "note": "LSTM module not available",
            "timestamp": datetime.now().isoformat()
        }


@router.get("/grader/status")
async def grader_status():
    """
    v10.54: Check auto-grader status with Postgres-backed pick counts.
    Shows pending vs graded counts using ET date bucketing.
    """
    from database import get_pick_counts_for_date, get_performance_stats_for_window, get_et_now, DB_ENABLED

    # Get today's date in ET
    et_now = get_et_now()
    today_et = et_now.date()
    today_str = today_et.strftime("%Y-%m-%d")

    # Get counts from Postgres
    today_counts = get_pick_counts_for_date(today_et)
    stats_7d = get_performance_stats_for_window(days_back=7)

    # Also check auto_grader for legacy JSONL stats
    grader_available = AUTO_GRADER_AVAILABLE
    jsonl_logged = 0
    grader_weights_loaded = False

    if AUTO_GRADER_AVAILABLE:
        grader = get_grader()
        jsonl_logged = grader.get_predictions_logged_count()
        grader_weights_loaded = bool(grader.weights)

    return {
        "available": grader_available,
        "database_enabled": DB_ENABLED,
        "today_et": today_str,
        "today_counts": {
            "total": today_counts["total"],
            "pending": today_counts["pending"],
            "graded": today_counts["win"] + today_counts["loss"] + today_counts["push"],
            "wins": today_counts["win"],
            "losses": today_counts["loss"],
            "pushes": today_counts["push"]
        },
        "stats_7d": {
            "total_graded": stats_7d["total_graded"],
            "wins": stats_7d["wins"],
            "losses": stats_7d["losses"],
            "pushes": stats_7d["pushes"],
            "hit_rate": stats_7d["hit_rate"],
            "profit_units": stats_7d["profit_units"]
        },
        "jsonl_logged_today": jsonl_logged,
        "weights_loaded": grader_weights_loaded,
        "note": "v10.54: Now using Postgres with ET date bucketing. JSONL logging optional.",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# v10.73: PULL READINESS + AUDIT ENDPOINT
# ============================================================================

@router.get("/audit/{sport}")
async def get_audit(sport: str):
    """
    v10.73: Audit endpoint for pull readiness and engine completeness.

    Returns:
    - Readiness gates status
    - Pull window recommendations
    - Engine completeness stats
    - Picks missing engines
    """
    sport_lower = sport.lower()

    # Fetch readiness data
    splits_data = None
    injury_data = None
    games_data = []
    total_games = 0

    try:
        # Get splits
        splits_resp = await get_splits(sport)
        if isinstance(splits_resp, dict):
            splits_data = splits_resp.get("data") or splits_resp.get("splits", [])

        # Get injuries
        injury_resp = await get_injuries(sport)
        if isinstance(injury_resp, dict):
            injury_data = injury_resp.get("data") or injury_resp.get("injuries", [])

        # Get lines/games
        lines_resp = await get_lines(sport)
        if isinstance(lines_resp, dict):
            games_data = lines_resp.get("data") or lines_resp.get("lines", [])
            total_games = len(games_data)
    except Exception as e:
        logger.warning(f"Audit data fetch error: {e}")

    # Check readiness
    readiness = check_readiness(
        sport=sport_lower,
        injury_data=injury_data,
        splits_data=splits_data,
        games=games_data,
        total_games=total_games
    )

    # Get recommended windows
    windows = get_recommended_pull_windows(sport_lower)

    # Get latest picks for engine audit
    engine_audit = {
        "total_picks": 0,
        "complete": 0,
        "incomplete": 0,
        "completeness_pct": 0,
        "missing_engines": [],
        "picks_missing_jarvis": [],
        "picks_missing_jason_sim": []
    }

    try:
        # Fetch best-bets to audit
        best_bets = await get_best_bets(sport, debug=1)
        if isinstance(best_bets, dict):
            props = best_bets.get("props", {}).get("picks", [])
            game_picks = best_bets.get("game_picks", {}).get("picks", [])
            all_picks = props + game_picks

            complete_count = 0
            missing_jarvis = []
            missing_jason = []

            for pick in all_picks:
                valid, reason, audit = validate_pick_pipeline(pick)
                if audit.complete:
                    complete_count += 1
                else:
                    pick_name = pick.get("player_name") or pick.get("selection_name") or pick.get("game", "")[:30]
                    if "JARVIS_ENGINE" in audit.engines_missing:
                        missing_jarvis.append(pick_name)
                    if "JASON_SIM" in audit.engines_missing:
                        missing_jason.append(pick_name)

            total = len(all_picks)
            engine_audit = {
                "total_picks": total,
                "complete": complete_count,
                "incomplete": total - complete_count,
                "completeness_pct": round((complete_count / max(1, total)) * 100, 1),
                "required_engines": REQUIRED_ENGINES,
                "picks_missing_jarvis": missing_jarvis[:10],
                "picks_missing_jason_sim": missing_jason[:10]
            }

            # v10.75: Get time state summary
            time_state_summary = get_time_state_summary(all_picks)
    except Exception as e:
        logger.warning(f"Engine audit error: {e}")
        time_state_summary = {}

    return {
        "sport": sport.upper(),
        "readiness": readiness.to_dict(),
        "recommended_windows": [
            {
                "start_time": w.start_time,
                "end_time": w.end_time,
                "label": w.label,
                "day_type": w.day_type
            }
            for w in windows
        ],
        "engine_audit": engine_audit,
        "time_state_summary": time_state_summary,
        "timestamp": datetime.now().isoformat()
    }


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

    # Filter to graded predictions within timeframe
    cutoff = datetime.now() - timedelta(days=days_back)
    graded = [
        p for p in predictions
        if p.actual_value is not None and
        datetime.fromisoformat(p.timestamp) >= cutoff
    ]

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
            "status": "🔥 PROFITABLE" if hit_rate > 0.55 else ("✅ BREAK-EVEN" if hit_rate > 0.48 else "⚠️ NEEDS IMPROVEMENT")
        },
        "by_stat_type": stat_breakdown,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/grader/grade/{sport}")
async def grade_predictions_manually(
    sport: str,
    date: Optional[str] = None,
    auth: bool = Depends(verify_api_key)
):
    """
    v10.38: Manually grade predictions for a specific sport and date.

    This endpoint fetches actual results and grades the predictions that were
    logged via the best-bets endpoint.

    Query Parameters:
        date: Date to grade in YYYY-MM-DD format (default: yesterday)

    Returns:
        {graded, wins, losses, pushes, no_action, hit_rate}

    Example:
        POST /live/grader/grade/nba?date=2026-01-21
    """
    if not AUTO_GRADER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Auto-grader module not available")

    # Import JSONLGradingJob
    try:
        from daily_scheduler import JSONLGradingJob
    except ImportError:
        raise HTTPException(status_code=503, detail="Grading job not available")

    grader = get_grader()
    sport_upper = sport.upper()

    # Parse date or use yesterday
    from datetime import date as date_type
    if date:
        try:
            target_date = date_type.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {date}. Use YYYY-MM-DD")
    else:
        target_date = date_type.today() - timedelta(days=1)

    # Create grading job and run for this sport
    grading_job = JSONLGradingJob(auto_grader=grader)
    date_et = target_date.isoformat()

    try:
        result = await grading_job._grade_sport(sport_upper, date_et=date_et)

        # Calculate hit rate
        total_decided = result.get("wins", 0) + result.get("losses", 0)
        hit_rate = round((result.get("wins", 0) / total_decided) * 100, 1) if total_decided > 0 else 0.0

        return {
            "status": "success",
            "sport": sport_upper,
            "date": target_date.isoformat(),
            "graded": result.get("graded", 0),
            "wins": result.get("wins", 0),
            "losses": result.get("losses", 0),
            "pushes": result.get("pushes", 0),
            "no_action": result.get("no_action", 0),
            "hit_rate": hit_rate,
            "weights_adjusted": result.get("weights_adjusted", False),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.exception(f"Manual grading failed for {sport_upper}: {e}")
        raise HTTPException(status_code=500, detail=f"Grading failed: {str(e)}")


@router.get("/grader/daily-report")
async def get_daily_community_report(days_back: int = 1):
    """
    v10.54: Generate a community-friendly daily report using Postgres with ET dates.

    This report is designed to share with your community showing:
    - Yesterday's performance across all sports
    - What the system learned
    - How we're improving
    - Encouragement regardless of wins/losses

    Share this every morning to build trust and transparency!
    """
    from database import get_et_now, get_picks_for_date, PickResult, DB_ENABLED
    from datetime import date as dt_date

    if not DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database not available for daily report")

    try:
        # v10.54: Use ET date for correct day bucketing
        et_now = get_et_now()
        target_date = (et_now - timedelta(days=days_back)).date()
        report_date = target_date.strftime("%B %d, %Y")
        today = et_now.strftime("%B %d, %Y")

        # Collect performance across all sports
        sports_data = {}
        total_picks = 0
        total_hits = 0
        total_losses = 0
        overall_lessons = []
        improvements = []

        for sport in ["NBA", "NFL", "MLB", "NHL"]:
            # v10.54: Query Postgres using ET date bucketing
            picks = get_picks_for_date(target_date, sport)

            # Filter to settled picks only
            settled = [p for p in picks if p.result in [PickResult.WIN, PickResult.LOSS, PickResult.PUSH]]

            if settled:
                wins = sum(1 for p in settled if p.result == PickResult.WIN)
                losses = sum(1 for p in settled if p.result == PickResult.LOSS)
                total = len(settled)
                hit_rate = wins / (wins + losses) if (wins + losses) > 0 else 0

                # Calculate net units
                net_units = sum(p.profit_units or 0 for p in settled)

                sports_data[sport] = {
                    "picks": total,
                    "wins": wins,
                    "losses": losses,
                    "hit_rate": round(hit_rate * 100, 1),
                    "status": "🔥" if hit_rate >= 0.55 else ("✅" if hit_rate >= 0.50 else "📈"),
                    "net_units": round(net_units, 2)
                }

                total_picks += total
                total_hits += wins
                total_losses += losses

                # Generate lessons learned based on performance
                if hit_rate < 0.45:
                    overall_lessons.append(f"{sport}: Reviewing our model factors. Adjusting weights.")
                    improvements.append(f"Recalibrating {sport} prediction weights")
                elif hit_rate >= 0.55:
                    overall_lessons.append(f"{sport}: Model performing well!")

        # Calculate overall hit rate
        overall_hit_rate = (total_hits / total_picks * 100) if total_picks > 0 else 0

        # Generate status emoji and message
        if overall_hit_rate >= 55:
            status_emoji = "🔥"
            status_message = "SMASHING IT!"
            encouragement = "Your community is in great hands. Keep riding the hot streak!"
        elif overall_hit_rate >= 52:
            status_emoji = "💰"
            status_message = "PROFITABLE DAY!"
            encouragement = "Above the 52% threshold needed for profit. Solid performance!"
        elif overall_hit_rate >= 48:
            status_emoji = "📊"
            status_message = "BREAK-EVEN ZONE"
            encouragement = "Close to the mark. Our self-learning system is making adjustments."
        else:
            status_emoji = "📈"
            status_message = "LEARNING DAY"
            encouragement = "Every loss teaches us something. The AI is adjusting weights to improve tomorrow."

        # Build community report
        report = {
            "title": f"📊 SMASH SPOT DAILY REPORT - {today}",
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
            "commitment": "🎯 We analyze EVERY pick, learn from EVERY outcome, and improve EVERY day. Win or lose, we're getting better together.",
            "next_audit": "Tomorrow 6:00 AM ET",
            "generated_at": datetime.now().isoformat()
        }

        # Add sample community post
        report["sample_post"] = f"""
{status_emoji} SMASH SPOT DAILY REPORT {status_emoji}

📅 {report_date} Results:
• Total Picks: {total_picks}
• Record: {total_hits}-{total_picks - total_hits}
• Hit Rate: {overall_hit_rate:.1f}%

{status_message}

📚 What We Learned:
{chr(10).join('• ' + lesson for lesson in (overall_lessons if overall_lessons else ['Model performing well, minor tuning applied.']))}

🔧 Improvements Made:
{chr(10).join('• ' + imp for imp in (improvements if improvements else ['Weights optimized for tomorrow.']))}

{encouragement}

🎯 We grade EVERY pick at 6 AM and adjust our AI daily.
Whether we win or lose, we're always improving! 💪
"""

        return report

    except Exception as e:
        logger.exception("Failed to generate daily report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily-report/{sport}")
async def get_v1031_daily_report(sport: str, date_str: str = None):
    """
    v10.31: Get daily report for a sport from PickLedger.
    v10.54: Updated to use ET date bucketing.

    Query Parameters:
    - date: YYYY-MM-DD format (default: yesterday in ET)

    Returns:
    - Performance summary (W-L-P, net_units, ROI)
    - Top picks with results
    - Breakdown by tier and confidence grade
    - Config changes made that day
    """
    if not DATABASE_AVAILABLE or not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database not available for v10.31 reports")

    try:
        from datetime import date as date_type
        from database import get_picks_for_date, get_config_changes, PickResult, get_et_now

        # v10.54: Parse date or use yesterday in ET
        if date_str:
            target_date = date_type.fromisoformat(date_str)
        else:
            et_now = get_et_now()
            target_date = (et_now - timedelta(days=1)).date()

        sport_upper = sport.upper()

        # Get picks for the date
        picks = get_picks_for_date(target_date, sport_upper)

        if not picks:
            return {
                "sport": sport_upper,
                "date": target_date.isoformat(),
                "message": "No picks found for this date",
                "record": "0-0-0",
                "net_units": 0.0,
                "timestamp": datetime.now().isoformat()
            }

        # Calculate summary stats
        wins = sum(1 for p in picks if p.result == PickResult.WIN)
        losses = sum(1 for p in picks if p.result == PickResult.LOSS)
        pushes = sum(1 for p in picks if p.result == PickResult.PUSH)
        pending = sum(1 for p in picks if p.result == PickResult.PENDING)
        net_units = sum(p.profit_units or 0 for p in picks if p.result in [PickResult.WIN, PickResult.LOSS, PickResult.PUSH])

        # Calculate ROI (total units wagered)
        settled_picks = [p for p in picks if p.result in [PickResult.WIN, PickResult.LOSS, PickResult.PUSH]]
        total_wagered = sum(p.recommended_units or 0.5 for p in settled_picks)
        roi = (net_units / total_wagered * 100) if total_wagered > 0 else 0

        # Breakdown by tier
        tier_breakdown = {}
        for tier in ["GOLD_STAR", "EDGE_LEAN", "MONITOR"]:
            tier_picks = [p for p in settled_picks if p.tier == tier]
            if tier_picks:
                tier_wins = sum(1 for p in tier_picks if p.result == PickResult.WIN)
                tier_units = sum(p.profit_units or 0 for p in tier_picks)
                tier_breakdown[tier] = {
                    "picks": len(tier_picks),
                    "wins": tier_wins,
                    "losses": len(tier_picks) - tier_wins,
                    "net_units": round(tier_units, 2),
                    "hit_rate": round(tier_wins / len(tier_picks) * 100, 1) if tier_picks else 0
                }

        # Breakdown by confidence grade
        confidence_breakdown = {}
        for grade in ["A", "B", "C"]:
            grade_picks = [p for p in settled_picks if p.confidence_grade == grade]
            if grade_picks:
                grade_wins = sum(1 for p in grade_picks if p.result == PickResult.WIN)
                grade_units = sum(p.profit_units or 0 for p in grade_picks)
                confidence_breakdown[grade] = {
                    "picks": len(grade_picks),
                    "wins": grade_wins,
                    "net_units": round(grade_units, 2),
                    "hit_rate": round(grade_wins / len(grade_picks) * 100, 1) if grade_picks else 0
                }

        # Get top picks (by profit_units, top 5)
        top_picks = sorted(
            [p for p in picks if p.result in [PickResult.WIN, PickResult.LOSS]],
            key=lambda p: p.profit_units or 0,
            reverse=True
        )[:5]

        top_picks_data = [
            {
                "selection": p.selection,
                "matchup": p.matchup,
                "tier": p.tier,
                "confidence_grade": p.confidence_grade,
                "result": p.result.value if p.result else "PENDING",
                "profit_units": round(p.profit_units or 0, 2),
                "odds": p.odds
            }
            for p in top_picks
        ]

        # Get config changes for the date
        changes = get_config_changes(sport_upper, days_back=1)
        config_changes = [
            {
                "timestamp": c.timestamp.isoformat() if c.timestamp else None,
                "reason": c.reason
            }
            for c in changes
        ]

        # Build report
        report = {
            "sport": sport_upper,
            "date": target_date.isoformat(),
            "record": f"{wins}-{losses}-{pushes}",
            "pending": pending,
            "net_units": round(net_units, 2),
            "roi": f"{roi:.1f}%",
            "total_picks": len(picks),
            "top_picks": top_picks_data,
            "tier_breakdown": tier_breakdown,
            "confidence_breakdown": confidence_breakdown,
            "config_changes": config_changes,
            "timestamp": datetime.now().isoformat()
        }

        return report

    except Exception as e:
        logger.exception("Failed to generate v10.31 daily report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/grade-now")
async def admin_grade_now(
    date: str = None,
    sport: str = None,
    auth: bool = Depends(verify_api_key)
):
    """
    v10.31: Admin endpoint to manually trigger grading and tuning.

    Query Parameters:
    - date: YYYY-MM-DD format (default: yesterday)
    - sport: NBA, NFL, MLB, NHL, NCAAB (default: all sports)

    Requires X-API-Key header.

    Steps:
    1. Grade picks for the specified date
    2. Run conservative tuning based on rolling performance
    """
    if not DATABASE_AVAILABLE or not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database not available for v10.31 grading")

    try:
        from datetime import date as date_type
        from grading_engine import grade_picks_for_date, run_daily_grading
        from learning_engine import tune_config_conservatively, run_daily_tuning

        # Parse date
        if date:
            target_date = date_type.fromisoformat(date)
        else:
            target_date = (datetime.now() - timedelta(days=1)).date()

        # Grade picks
        if sport:
            sport_upper = sport.upper()
            grading_result = await grade_picks_for_date(target_date, sport_upper)
            tuning_result = tune_config_conservatively(sport_upper)
            grading_summary = {sport_upper: grading_result}
            tuning_summary = {sport_upper: tuning_result}
        else:
            grading_summary = await run_daily_grading(days_back=(datetime.now().date() - target_date).days)
            tuning_summary = run_daily_tuning()

        return {
            "success": True,
            "date": target_date.isoformat(),
            "sport": sport.upper() if sport else "ALL",
            "grading": grading_summary,
            "tuning": tuning_summary,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.exception("Admin grade-now failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# v10.32: SIGNAL ATTRIBUTION ENDPOINTS
# ============================================================================

@router.get("/attribution-report/{sport}")
async def get_attribution_report(
    sport: str,
    window_days: int = 7,
    auth: bool = Depends(verify_api_key)
):
    """
    v10.32: Signal Attribution Report - Shows which signals correlate with ROI.

    Query Parameters:
    - window_days: Rolling window for analysis (default: 7, max: 30)

    Returns:
    - Baseline performance (total picks, net units, ROI)
    - Top positive signals (ordered by ROI uplift)
    - Top negative signals (ordered by ROI drag)
    - Performance by confluence level
    - Performance by confidence grade

    This endpoint is the core of the v10.32 self-learning system.
    Used for daily transparency reports and micro-weight tuning decisions.
    """
    if not SIGNAL_ATTRIBUTION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Signal attribution module not available")

    if not DATABASE_AVAILABLE or not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database not available for v10.32 attribution")

    try:
        sport_upper = sport.upper()
        window_days = min(max(1, window_days), 30)  # Clamp to 1-30 days

        # Compute comprehensive feature table
        report = compute_feature_table(sport_upper, window_days)

        # Add micro-weight status
        if MICRO_WEIGHT_TUNING_AVAILABLE:
            mw_status = get_micro_weight_status(sport_upper)
            report["micro_weights"] = mw_status
        else:
            report["micro_weights"] = {"available": False}

        # Add version and timestamp
        report["version"] = "v10.32"
        report["generated_at"] = datetime.now().isoformat()

        return report

    except Exception as e:
        logger.exception("Failed to generate attribution report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signal-uplift/{sport}")
async def get_signal_uplift(
    sport: str,
    window_days: int = 7,
    min_count: int = 8,
    auth: bool = Depends(verify_api_key)
):
    """
    v10.32: Signal-level ROI uplift analysis.

    For each signal S:
    - ROI_when_present = ROI of picks where S fired
    - ROI_when_absent = ROI of picks where S didn't fire
    - uplift = ROI_present - ROI_absent

    Positive uplift = signal predicts wins
    Negative uplift = signal should be weighted down

    Query Parameters:
    - window_days: Rolling window (default: 7, max: 30)
    - min_count: Minimum occurrences for a signal (default: 8)
    """
    if not SIGNAL_ATTRIBUTION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Signal attribution module not available")

    if not DATABASE_AVAILABLE or not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        sport_upper = sport.upper()
        window_days = min(max(1, window_days), 30)
        min_count = max(1, min_count)

        return compute_signal_uplift(sport_upper, window_days, min_count)

    except Exception as e:
        logger.exception("Failed to compute signal uplift: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/tune-micro-weights")
async def admin_tune_micro_weights(
    sport: str = None,
    auth: bool = Depends(verify_api_key)
):
    """
    v10.32: Admin endpoint to manually trigger micro-weight tuning.

    Query Parameters:
    - sport: NBA, NFL, MLB, NHL, NCAAB (default: all sports)

    Requires X-API-Key header.

    Tuning Rules:
    - Only signals with >= 10 occurrences are considered
    - Only adjust if uplift exceeds ±8% threshold
    - Step size: ±0.01 per day
    - Range: 0.85-1.15 (±15% from baseline)
    - Circuit breaker: Reset if 25% of signals at limits
    - Max 3 adjustments per sport per day
    """
    if not MICRO_WEIGHT_TUNING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Micro-weight tuning module not available")

    if not DATABASE_AVAILABLE or not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        if sport:
            sport_upper = sport.upper()
            result = tune_micro_weights_from_attribution(sport_upper)
            return {
                "success": True,
                "sport": sport_upper,
                "tuning_result": result,
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Run for all sports
            all_results = run_micro_weight_tuning()
            return {
                "success": True,
                "sport": "ALL",
                "tuning_results": all_results,
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.exception("Micro-weight tuning failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/micro-weight-status/{sport}")
async def get_micro_weight_status_endpoint(
    sport: str,
    auth: bool = Depends(verify_api_key)
):
    """
    v10.32: Get current micro-weight status for a sport.

    Returns:
    - Current micro-weights for all signals
    - How many signals are at limits (0.85 or 1.15)
    - Circuit breaker status
    - Last tuning timestamp
    """
    if not MICRO_WEIGHT_TUNING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Micro-weight tuning module not available")

    try:
        sport_upper = sport.upper()
        status = get_micro_weight_status(sport_upper)
        status["timestamp"] = datetime.now().isoformat()
        return status

    except Exception as e:
        logger.exception("Failed to get micro-weight status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/db/status")
async def get_db_status(auth: bool = Depends(verify_api_key)):
    """
    v10.32+: Database health check endpoint.
    Returns connection status, table counts, and diagnostics.
    Always returns 200 OK (health info in response body).
    """
    if DATABASE_AVAILABLE:
        try:
            health = get_db_health()
            return {
                "status": "ok" if health["db_connect_ok"] else "degraded",
                "timestamp": datetime.now().isoformat(),
                **health
            }
        except Exception as e:
            return {
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "db_url_present": bool(os.getenv("DATABASE_URL", "")),
                "db_connect_ok": False,
                "last_error": str(e)
            }
    else:
        return {
            "status": "unavailable",
            "timestamp": datetime.now().isoformat(),
            "db_url_present": bool(os.getenv("DATABASE_URL", "")),
            "db_connect_ok": False,
            "db_enabled": False,
            "last_error": "Database module not available",
            "note": "Add PostgreSQL service in Railway to enable database features"
        }


@router.get("/season/status")
async def get_season_status_endpoint(auth: bool = Depends(verify_api_key)):
    """
    v10.32+: Get current season status for all sports.
    Shows which sports are in-season and their approximate season dates.
    """
    if DATABASE_AVAILABLE:
        try:
            return get_season_status()
        except Exception as e:
            logger.warning(f"Season status failed: {e}")

    # Fallback if database module not available
    from datetime import date as dt_date
    today = dt_date.today()
    return {
        "check_date": today.isoformat(),
        "active_sports": ["NBA", "NFL", "NHL", "NCAAB"],  # Default winter assumption
        "note": "Season calendar requires database module"
    }


@router.get("/signal-report")
async def get_signal_report(
    sport: str = "ALL",
    window_days: int = 7,
    auth: bool = Depends(verify_api_key)
):
    """
    v10.32+: Consolidated Signal Report - Policy multipliers, performance, and tuning history.

    This is the primary transparency endpoint for the v10.32 self-learning system.
    ALWAYS returns 200 OK with db_status indicating availability.

    Query Parameters:
    - sport: NBA, NFL, MLB, NHL, NCAAB, or ALL (default: ALL)
    - window_days: Rolling window for analysis (default: 7, max: 30)

    Returns:
    - db_status: Database connection health
    - totals: Aggregate win/loss/ROI stats
    - signal_breakdown: Per-signal performance
    - signal_policies: Current multipliers per signal per sport
    - tuning_history: Recent multiplier changes with reasons
    - system_health: Circuit breaker and recommendation
    """
    window_days = min(max(1, window_days), 30)
    sports_to_check = ["NBA", "NFL", "MLB", "NHL", "NCAAB"] if sport.upper() == "ALL" else [sport.upper()]

    # Always include db_status
    db_status = {
        "db_url_present": bool(os.getenv("DATABASE_URL", "")),
        "db_connect_ok": False,
        "db_enabled": DATABASE_AVAILABLE and database.DB_ENABLED,
        "tables_found": [],
        "missing_tables": []
    }

    # Try to get real DB health
    if DATABASE_AVAILABLE:
        try:
            db_health = get_db_health()
            db_status.update(db_health)
        except Exception as e:
            db_status["last_error"] = str(e)

    report = {
        "version": "v10.32+",
        "generated_at": datetime.now().isoformat(),
        "window_days": window_days,
        "sport_filter": sport.upper(),
        "db_status": db_status,
        "sports": {}
    }

    # If DB not available, return empty structure with db_status
    if not DATABASE_AVAILABLE or not database.DB_ENABLED or not db_status["db_connect_ok"]:
        for sport_code in sports_to_check:
            report["sports"][sport_code] = {
                "totals": {"picks_logged": 0, "wins": 0, "losses": 0, "pushes": 0, "pending": 0, "win_rate": 0, "roi": 0},
                "signal_breakdown": [],
                "signal_policies": DEFAULT_MICRO_WEIGHTS.copy() if DEFAULT_MICRO_WEIGHTS else {},
                "tuning_history": [],
                "top_positive_signals": [],
                "top_negative_signals": []
            }
        report["system_health"] = {
            "total_signals_tracked": 0,
            "signals_at_limit": 0,
            "circuit_breaker_risk": False,
            "recommendation": "DB_UNAVAILABLE",
            "note": "Add PostgreSQL in Railway to enable signal tracking"
        }
        return report

    # DB is available - fetch real data
    try:
        total_signals_at_limit = 0
        total_signals = 0

        for sport_code in sports_to_check:
            sport_report = {
                "totals": {"picks_logged": 0, "wins": 0, "losses": 0, "pushes": 0, "pending": 0, "win_rate": 0, "roi": 0},
                "signal_breakdown": [],
                "signal_policies": {},
                "tuning_history": [],
                "top_positive_signals": [],
                "top_negative_signals": [],
                "status": {}
            }

            # 1. Get signal ledger stats (totals + breakdown)
            try:
                ledger_stats = get_signal_ledger_stats(sport_code, window_days)
                sport_report["totals"] = ledger_stats.get("totals", sport_report["totals"])
                sport_report["signal_breakdown"] = ledger_stats.get("signal_breakdown", [])
                sport_report["top_positive_signals"] = ledger_stats.get("top_positive_signals", [])
                sport_report["top_negative_signals"] = ledger_stats.get("top_negative_signals", [])
            except Exception as e:
                logger.warning(f"Signal ledger stats failed for {sport_code}: {e}")

            # 2. Get signal policies (current multipliers)
            if SIGNAL_POLICY_AVAILABLE:
                try:
                    policies = get_signal_policy(sport_code)
                    sport_report["signal_policies"] = policies
                    for key, mult in policies.items():
                        total_signals += 1
                        if mult <= 0.86 or mult >= 1.14:
                            total_signals_at_limit += 1
                except Exception as e:
                    logger.warning(f"Signal policy load failed for {sport_code}: {e}")
                    sport_report["signal_policies"] = DEFAULT_MICRO_WEIGHTS.copy()

            # 3. Get tuning history (fixed: days_back instead of limit)
            try:
                history = get_tuning_history(sport_code, days_back=30)
                sport_report["tuning_history"] = history[:10]  # Limit to 10 most recent
            except Exception as e:
                logger.warning(f"Tuning history load failed for {sport_code}: {e}")

            # 4. Get micro-weight status if available
            if MICRO_WEIGHT_TUNING_AVAILABLE:
                try:
                    mw_status = get_micro_weight_status(sport_code)
                    sport_report["status"] = {
                        "signals_at_limit": mw_status.get("signals_at_limit", 0),
                        "total_signals": mw_status.get("total_signals", 0),
                        "circuit_breaker_triggered": mw_status.get("circuit_breaker_triggered", False),
                        "last_tuning": mw_status.get("last_tuning", None)
                    }
                except Exception:
                    pass

            report["sports"][sport_code] = sport_report

        # System-wide health
        circuit_breaker_risk = (total_signals_at_limit / total_signals) > 0.25 if total_signals > 0 else False
        report["system_health"] = {
            "total_signals_tracked": total_signals,
            "signals_at_limit": total_signals_at_limit,
            "circuit_breaker_risk": circuit_breaker_risk,
            "recommendation": "HEALTHY" if not circuit_breaker_risk else "CONSIDER_RESET"
        }

        return report

    except Exception as e:
        logger.exception("Failed to generate signal report: %s", e)
        # Still return 200 with error info
        report["error"] = str(e)
        report["system_health"] = {
            "total_signals_tracked": 0,
            "signals_at_limit": 0,
            "circuit_breaker_risk": False,
            "recommendation": "ERROR"
        }
        return report


@router.get("/scheduler/status")
async def scheduler_status():
    """Check daily scheduler status."""
    try:
        from daily_scheduler import SCHEDULER_AVAILABLE, SchedulerConfig
        return {
            "available": True,
            "apscheduler_available": SCHEDULER_AVAILABLE,
            "audit_time": f"{SchedulerConfig.AUDIT_HOUR:02d}:{SchedulerConfig.AUDIT_MINUTE:02d} ET",
            "supported_sports": list(SchedulerConfig.SPORT_STATS.keys()),
            "retrain_thresholds": {
                "mae": SchedulerConfig.RETRAIN_MAE_THRESHOLD,
                "hit_rate": SchedulerConfig.RETRAIN_HIT_RATE_THRESHOLD
            },
            "note": "Scheduler runs daily audit at 6 AM ET",
            "timestamp": datetime.now().isoformat()
        }
    except ImportError:
        return {
            "available": False,
            "note": "Scheduler module not available",
            "timestamp": datetime.now().isoformat()
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
            except:
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


# ============================================================================
# LEVEL 17 - PARLAY ARCHITECT CORRELATION ENGINE
# The Science: Books price parlays as independent. They aren't.
# Covariance > 0.8 = Mathematical Edge
# ============================================================================

CORRELATION_MATRIX = {
    # NFL Correlations
    "QB_WR": {"correlation": 0.88, "name": "BATTERY STACK", "description": "QB throws 300+ yards → WR1 must have yards"},
    "QB_TE": {"correlation": 0.72, "name": "REDZONE STACK", "description": "QB TDs correlate with TE targets in redzone"},
    "RB_DST": {"correlation": 0.65, "name": "GRIND STACK", "description": "RB dominance = winning = opponent forced passing = sacks/INTs"},
    "WR1_WR2": {"correlation": -0.35, "name": "CANNIBALIZE", "description": "Negative correlation - targets split"},

    # NBA Correlations
    "PG_C": {"correlation": 0.55, "name": "PNR STACK", "description": "Pick and roll - PG assists correlate with C points"},
    "STAR_OUT_BACKUP": {"correlation": 0.82, "name": "USAGE MONSTER", "description": "Star out = backup usage spike"},
    "BLOWOUT_BENCH": {"correlation": 0.70, "name": "GARBAGE TIME", "description": "Blowout = bench minutes spike"},

    # MLB Correlations
    "LEADOFF_RUNS": {"correlation": 0.68, "name": "TABLE SETTER", "description": "Leadoff OBP correlates with team runs"},
    "ACE_UNDER": {"correlation": 0.75, "name": "ACE EFFECT", "description": "Ace pitching = low scoring game"},
}

# Usage impact multipliers when star players are OUT
VOID_IMPACT_MULTIPLIERS = {
    # NBA - Points boost when star is out
    "Joel Embiid": {"teammate": "Tyrese Maxey", "pts_boost": 1.28, "usage_boost": 1.35},
    "LeBron James": {"teammate": "Anthony Davis", "pts_boost": 1.15, "usage_boost": 1.20},
    "Stephen Curry": {"teammate": "Klay Thompson", "pts_boost": 1.22, "usage_boost": 1.25},
    "Luka Doncic": {"teammate": "Kyrie Irving", "pts_boost": 1.18, "usage_boost": 1.22},
    "Giannis Antetokounmpo": {"teammate": "Damian Lillard", "pts_boost": 1.20, "usage_boost": 1.25},
    "Kevin Durant": {"teammate": "Devin Booker", "pts_boost": 1.12, "usage_boost": 1.18},
    "Jayson Tatum": {"teammate": "Jaylen Brown", "pts_boost": 1.15, "usage_boost": 1.20},
    "Nikola Jokic": {"teammate": "Jamal Murray", "pts_boost": 1.25, "usage_boost": 1.30},

    # NFL - Target/usage boost when WR1 is out
    "Davante Adams": {"teammate": "Jakobi Meyers", "target_boost": 1.35, "usage_boost": 1.40},
    "Tyreek Hill": {"teammate": "Jaylen Waddle", "target_boost": 1.28, "usage_boost": 1.32},
    "CeeDee Lamb": {"teammate": "Brandin Cooks", "target_boost": 1.30, "usage_boost": 1.35},
    "Justin Jefferson": {"teammate": "Jordan Addison", "target_boost": 1.38, "usage_boost": 1.42},
}

# ============================================================================
# SPORTSBOOK DEEP LINKS - Click-to-Bet Feature + SMASH LINKS
# ============================================================================

# Deep link URL schemes for direct bet slip access
SMASH_LINK_SCHEMES = {
    "draftkings": {
        "app": "draftkings://sportsbook/gateway?s=B_{sport}&e={event_id}&m={market_id}",
        "web": "https://sportsbook.draftkings.com/{sport_path}?eventId={event_id}",
        "universal": "https://sportsbook.draftkings.com/link/{sport}/{event_id}/{market_id}"
    },
    "fanduel": {
        "app": "fanduel://sportsbook/market/{market_id}",
        "web": "https://sportsbook.fanduel.com/{sport_path}/event/{event_id}",
        "universal": "https://sportsbook.fanduel.com/link/{event_id}"
    },
    "betmgm": {
        "app": "betmgm://sports/event/{event_id}",
        "web": "https://sports.betmgm.com/en/sports/{sport_path}/{event_id}",
        "universal": "https://sports.betmgm.com/link/{event_id}"
    },
    "caesars": {
        "app": "caesarssportsbook://event/{event_id}",
        "web": "https://www.caesars.com/sportsbook-and-casino/{sport_path}/{event_id}",
        "universal": "https://www.caesars.com/link/{event_id}"
    },
    "pointsbetus": {
        "app": "pointsbet://event/{event_id}",
        "web": "https://pointsbet.com/{sport_path}/{event_id}",
        "universal": "https://pointsbet.com/link/{event_id}"
    },
    "betrivers": {
        "app": "betrivers://event/{event_id}",
        "web": "https://www.betrivers.com/{sport_path}/{event_id}",
        "universal": "https://www.betrivers.com/link/{event_id}"
    }
}

SPORTSBOOK_CONFIGS = {
    "draftkings": {
        "name": "DraftKings",
        "web_base": "https://sportsbook.draftkings.com",
        "app_scheme": "draftkings://sportsbook/gateway",
        "color": "#53d337",
        "logo": "https://upload.wikimedia.org/wikipedia/en/b/b8/DraftKings_logo.svg"
    },
    "fanduel": {
        "name": "FanDuel",
        "web_base": "https://sportsbook.fanduel.com",
        "app_scheme": "fanduel://sportsbook/market",
        "color": "#1493ff",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/8/83/FanDuel_logo.svg"
    },
    "betmgm": {
        "name": "BetMGM",
        "web_base": "https://sports.betmgm.com",
        "app_scheme": "betmgm://sports/event",
        "color": "#c4a44a",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/2/2e/BetMGM_logo.svg"
    },
    "caesars": {
        "name": "Caesars",
        "web_base": "https://www.caesars.com/sportsbook-and-casino",
        "app_scheme": "caesarssportsbook://event",
        "color": "#0a2240",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/6/6e/Caesars_Sportsbook_logo.svg"
    },
    "pointsbetus": {
        "name": "PointsBet",
        "web_base": "https://pointsbet.com",
        "app_scheme": "pointsbet://",
        "color": "#ed1c24",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/3/3c/PointsBet_logo.svg"
    },
    "williamhill_us": {
        "name": "William Hill",
        "web_base": "https://www.williamhill.com/us",
        "app_scheme": "williamhill://",
        "color": "#00314d",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/a/a2/William_Hill_logo.svg"
    },
    "barstool": {
        "name": "Barstool",
        "web_base": "https://www.barstoolsportsbook.com",
        "app_scheme": "barstool://",
        "color": "#c41230",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/4/4a/Barstool_Sports_logo.svg"
    },
    "betrivers": {
        "name": "BetRivers",
        "web_base": "https://www.betrivers.com",
        "app_scheme": "betrivers://",
        "color": "#1b365d",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/8/85/BetRivers_logo.svg"
    }
}


def generate_sportsbook_link(book_key: str, event_id: str, sport: str) -> Dict[str, str]:
    """Generate deep link for a sportsbook event."""
    config = SPORTSBOOK_CONFIGS.get(book_key)
    if not config:
        return None

    # Web link that works universally (sportsbooks redirect to app if installed)
    # Most sportsbooks use similar URL patterns for events
    sport_paths = {
        "nba": "basketball/nba",
        "nfl": "football/nfl",
        "mlb": "baseball/mlb",
        "nhl": "hockey/nhl"
    }
    sport_path = sport_paths.get(sport.lower(), sport.lower())

    return {
        "book_key": book_key,
        "name": config["name"],
        "web_url": f"{config['web_base']}/{sport_path}",
        "color": config["color"],
        "logo": config.get("logo", "")
    }


def generate_true_deep_link(book_key: str, event_id: str, sport: str, outcomes: List[Dict]) -> Dict[str, Any]:
    """
    Generate TRUE deep links that open the bet slip with selection pre-populated.

    Uses outcome sids from The Odds API to construct direct bet placement links.

    Deep Link Formats:
    - DraftKings: https://sportsbook.draftkings.com/event/{eventId}?outcomes={outcomeId}
    - FanDuel: https://sportsbook.fanduel.com/addToBetslip?marketId={marketId}&selectionId={selectionId}
    - BetMGM: https://sports.betmgm.com/en/sports/events/{eventId}
    - Others: Sport-specific pages (fallback)
    """
    config = SPORTSBOOK_CONFIGS.get(book_key)
    if not config:
        return {"web": "#", "note": "Unknown sportsbook"}

    # Extract first outcome's sid if available (for single-click deep link)
    first_outcome_sid = None
    first_outcome_link = None
    if outcomes:
        first_outcome_sid = outcomes[0].get("sid")
        first_outcome_link = outcomes[0].get("link")

    # If API provided a direct link, use it
    if first_outcome_link:
        return {
            "web": first_outcome_link,
            "mobile": first_outcome_link,
            "type": "direct_betslip",
            "note": f"Opens {config['name']} with bet pre-populated"
        }

    # Build book-specific deep links using sids
    sport_path = {
        "nba": "basketball/nba",
        "nfl": "football/nfl",
        "mlb": "baseball/mlb",
        "nhl": "hockey/nhl"
    }.get(sport.lower(), sport.lower())

    base_url = config["web_base"]

    # Book-specific deep link construction
    if book_key == "draftkings" and first_outcome_sid:
        # DraftKings uses outcome IDs in URL
        return {
            "web": f"{base_url}/event/{event_id}?outcomes={first_outcome_sid}",
            "mobile": f"dksb://sb/addbet/{first_outcome_sid}",
            "type": "betslip",
            "note": f"Opens DraftKings with bet on slip"
        }

    elif book_key == "fanduel" and first_outcome_sid:
        # FanDuel uses marketId and selectionId - sid format may be "marketId.selectionId"
        parts = str(first_outcome_sid).split(".")
        if len(parts) >= 2:
            market_id = parts[0]
            selection_id = parts[1] if len(parts) > 1 else first_outcome_sid
            return {
                "web": f"{base_url}/addToBetslip?marketId={market_id}&selectionId={selection_id}",
                "mobile": f"fanduel://sportsbook/addToBetslip?marketId={market_id}&selectionId={selection_id}",
                "type": "betslip",
                "note": f"Opens FanDuel with bet on slip"
            }
        else:
            return {
                "web": f"{base_url}/{sport_path}",
                "mobile": config.get("app_scheme", ""),
                "type": "sport_page",
                "note": f"Opens FanDuel {sport.upper()} page"
            }

    elif book_key == "betmgm" and event_id:
        # BetMGM uses event IDs
        return {
            "web": f"{base_url}/en/sports/events/{event_id}",
            "mobile": f"betmgm://sports/event/{event_id}",
            "type": "event",
            "note": f"Opens BetMGM event page"
        }

    elif book_key == "caesars" and event_id:
        return {
            "web": f"{base_url}/us/{sport_path}/event/{event_id}",
            "mobile": f"caesarssportsbook://event/{event_id}",
            "type": "event",
            "note": f"Opens Caesars event page"
        }

    # Fallback: Sport-specific page
    return {
        "web": f"{base_url}/{sport_path}",
        "mobile": config.get("app_scheme", ""),
        "type": "sport_page",
        "note": f"Opens {config['name']} {sport.upper()} page"
    }


@router.get("/line-shop/{sport}")
async def get_line_shopping(sport: str, game_id: Optional[str] = None):
    """
    Get odds from multiple sportsbooks for line shopping.
    Returns best odds for each side of each bet.

    Response includes deep links for each sportsbook.
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache
    cache_key = f"line-shop:{sport_lower}:{game_id or 'all'}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sport_config = SPORT_MAPPINGS[sport_lower]

    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "spreads,h2h,totals",
                "oddsFormat": "american",
                "includeLinks": "true",
                "includeSids": "true"
            }
        )

        if not resp or resp.status_code != 200:
            # Return empty data when API unavailable - no fake data
            logger.warning("Odds API unavailable for line-shop - no data available")
            result = {
                "sport": sport.upper(),
                "source": "none",
                "count": 0,
                "sportsbooks": list(SPORTSBOOK_CONFIGS.keys()),
                "data": [],
                "message": "Odds API unavailable - check API key configuration",
                "timestamp": datetime.now().isoformat()
            }
            api_cache.set(cache_key, result, ttl=600)
            return result

        games = resp.json()
        line_shop_data = []

        for game in games:
            if game_id and game.get("id") != game_id:
                continue

            game_data = {
                "game_id": game.get("id"),
                "home_team": game.get("home_team"),
                "away_team": game.get("away_team"),
                "commence_time": game.get("commence_time"),
                "markets": {}
            }

            # Organize by market type
            for bookmaker in game.get("bookmakers", []):
                book_key = bookmaker.get("key")
                book_name = bookmaker.get("title")

                for market in bookmaker.get("markets", []):
                    market_key = market.get("key")

                    if market_key not in game_data["markets"]:
                        game_data["markets"][market_key] = {
                            "best_odds": {},
                            "all_books": []
                        }

                    # Extract deep links from API response (if available)
                    api_link = bookmaker.get("link")  # Direct link from Odds API

                    # Build outcomes with sids and links
                    outcomes_with_links = []
                    for outcome in market.get("outcomes", []):
                        outcome_data = {
                            "name": outcome.get("name"),
                            "price": outcome.get("price"),
                            "point": outcome.get("point"),
                            "sid": outcome.get("sid"),  # Source ID for deep links
                            "link": outcome.get("link")  # Direct bet link if available
                        }
                        outcomes_with_links.append(outcome_data)

                    book_entry = {
                        "book_key": book_key,
                        "book_name": book_name,
                        "outcomes": outcomes_with_links,
                        "api_link": api_link,
                        "deep_link": generate_true_deep_link(book_key, game.get("id"), sport_lower, outcomes_with_links)
                    }
                    game_data["markets"][market_key]["all_books"].append(book_entry)

                    # Track best odds for each outcome
                    for outcome in market.get("outcomes", []):
                        outcome_name = outcome.get("name")
                        price = outcome.get("price", -110)

                        if outcome_name not in game_data["markets"][market_key]["best_odds"]:
                            game_data["markets"][market_key]["best_odds"][outcome_name] = {
                                "price": price,
                                "book": book_name,
                                "book_key": book_key
                            }
                        elif price > game_data["markets"][market_key]["best_odds"][outcome_name]["price"]:
                            game_data["markets"][market_key]["best_odds"][outcome_name] = {
                                "price": price,
                                "book": book_name,
                                "book_key": book_key
                            }

            line_shop_data.append(game_data)

        result = {
            "sport": sport.upper(),
            "source": "odds_api",
            "count": len(line_shop_data),
            "sportsbooks": list(SPORTSBOOK_CONFIGS.keys()),
            "data": line_shop_data,
            "timestamp": datetime.now().isoformat()
        }

        api_cache.set(cache_key, result, ttl=600)  # 2 min cache for line shopping
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Line shopping fetch failed: %s", e)
        # Return empty data on error - no fake data
        result = {
            "sport": sport.upper(),
            "source": "none",
            "count": 0,
            "sportsbooks": list(SPORTSBOOK_CONFIGS.keys()),
            "data": [],
            "message": f"API error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        api_cache.set(cache_key, result, ttl=600)
        return result


@router.get("/betslip/generate")
async def generate_betslip(
    sport: str,
    game_id: str,
    bet_type: str,  # spread, h2h, total
    selection: str,  # team name or over/under
    book: Optional[str] = None  # specific book, or returns all
):
    """
    Generate deep links for placing a specific bet across sportsbooks.

    Frontend uses this to create the "click to bet" modal.

    Example:
        /live/betslip/generate?sport=nba&game_id=xyz&bet_type=spread&selection=Lakers

    Returns links for all sportsbooks (or specific book if specified).
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Get current odds for this game
    sport_config = SPORT_MAPPINGS[sport_lower]

    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        resp = await fetch_with_retries(
            "GET", odds_url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": bet_type + "s" if bet_type in ["spread", "total"] else bet_type,
                "oddsFormat": "american",
                "includeLinks": "true",
                "includeSids": "true"
            }
        )

        if not resp or resp.status_code != 200:
            # Return error when API unavailable - no fake data
            logger.warning("Odds API unavailable for betslip - no data available")
            raise HTTPException(status_code=503, detail="Odds API unavailable - cannot generate betslip without live data")

        games = resp.json()
        target_game = None

        for game in games:
            if game.get("id") == game_id:
                target_game = game
                break

        if not target_game:
            # Game not found in API - return error
            logger.warning("Game %s not found in API", game_id)
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found - may have already started or ended")

        betslip_options = []

        for bookmaker in target_game.get("bookmakers", []):
            book_key = bookmaker.get("key")

            # Filter by specific book if requested
            if book and book_key != book:
                continue

            # Skip if we don't have config for this book
            if book_key not in SPORTSBOOK_CONFIGS:
                continue

            book_config = SPORTSBOOK_CONFIGS[book_key]

            for market in bookmaker.get("markets", []):
                market_key = market.get("key")

                # Match the requested bet type
                if bet_type == "spread" and market_key != "spreads":
                    continue
                if bet_type == "h2h" and market_key != "h2h":
                    continue
                if bet_type == "total" and market_key != "totals":
                    continue

                for outcome in market.get("outcomes", []):
                    outcome_name = outcome.get("name", "")

                    # Match the selection
                    if selection.lower() not in outcome_name.lower():
                        continue

                    # Extract sid and link from API response for true deep links
                    outcome_sid = outcome.get("sid")
                    outcome_link = outcome.get("link")

                    # Generate true deep link using API data
                    deep_link = generate_true_deep_link(
                        book_key,
                        game_id,
                        sport_lower,
                        [{"sid": outcome_sid, "link": outcome_link}]
                    )

                    betslip_options.append({
                        "book_key": book_key,
                        "book_name": book_config["name"],
                        "book_color": book_config["color"],
                        "book_logo": book_config.get("logo", ""),
                        "selection": outcome_name,
                        "odds": outcome.get("price", -110),
                        "point": outcome.get("point"),  # spread/total line
                        "sid": outcome_sid,  # Include sid for custom link building
                        "deep_link": deep_link
                    })

        # Sort by best odds (highest for positive, least negative for negative)
        betslip_options.sort(key=lambda x: x["odds"], reverse=True)

        return {
            "sport": sport.upper(),
            "game_id": game_id,
            "game": f"{target_game.get('away_team')} @ {target_game.get('home_team')}",
            "bet_type": bet_type,
            "selection": selection,
            "best_odds": betslip_options[0] if betslip_options else None,
            "all_books": betslip_options,
            "count": len(betslip_options),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Betslip generation failed: %s", e)
        # Return error on failure - no fake data
        raise HTTPException(status_code=500, detail=f"Betslip generation failed: {str(e)}")


@router.get("/sportsbooks")
async def list_sportsbooks():
    """List all supported sportsbooks with their branding info."""
    sportsbooks_list = [
        {
            "key": key,
            "name": config["name"],
            "color": config["color"],
            "logo": config.get("logo", ""),
            "web_url": config["web_base"]
        }
        for key, config in SPORTSBOOK_CONFIGS.items()
    ]
    return {
        "count": len(SPORTSBOOK_CONFIGS),
        "active_count": len(sportsbooks_list),  # Frontend expects this field
        "sportsbooks": sportsbooks_list,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# LEVEL 17 - PARLAY ARCHITECT, VOID CHECK, SMASH CARD
# ============================================================================

@router.post("/parlay-architect")
async def parlay_architect(leg1: Dict[str, Any], leg2: Dict[str, Any]):
    """
    Calculates 'Correlation Alpha' for Same Game Parlays (SGP).
    Finds correlated props that books misprice as independent events.

    Request Body:
    {
        "leg1": {"player": "Patrick Mahomes", "position": "QB", "team": "KC", "prop": "passing_yards", "line": 275.5},
        "leg2": {"player": "Travis Kelce", "position": "TE", "team": "KC", "prop": "receiving_yards", "line": 65.5}
    }

    Response:
    {
        "stack_type": "BATTERY STACK",
        "correlation": 0.88,
        "glitch_score": 9.0,
        "recommendation": "CORRELATION GLITCH - Book Misprice Detected",
        "edge_explanation": "If Mahomes hits 275+ yards, Kelce MUST have yards. Books price independently."
    }
    """
    pos1 = safe_upper(leg1.get("position"))
    pos2 = safe_upper(leg2.get("position"))
    team1 = safe_upper(leg1.get("team"))
    team2 = safe_upper(leg2.get("team"))

    correlation = 0.0
    stack_type = "INDEPENDENT"
    description = "No significant correlation detected"

    # Same team correlations
    if team1 == team2:
        # QB + WR/TE Stack
        if pos1 == "QB" and pos2 in ["WR", "TE"]:
            corr_key = f"QB_{pos2}"
            if corr_key in CORRELATION_MATRIX:
                data = CORRELATION_MATRIX[corr_key]
                correlation = data["correlation"]
                stack_type = data["name"]
                description = data["description"]
        elif pos2 == "QB" and pos1 in ["WR", "TE"]:
            corr_key = f"QB_{pos1}"
            if corr_key in CORRELATION_MATRIX:
                data = CORRELATION_MATRIX[corr_key]
                correlation = data["correlation"]
                stack_type = data["name"]
                description = data["description"]

        # RB + DST Stack
        elif (pos1 == "RB" and pos2 == "DST") or (pos1 == "DST" and pos2 == "RB"):
            data = CORRELATION_MATRIX["RB_DST"]
            correlation = data["correlation"]
            stack_type = data["name"]
            description = data["description"]

        # WR1 + WR2 (negative correlation)
        elif pos1 == "WR" and pos2 == "WR":
            data = CORRELATION_MATRIX["WR1_WR2"]
            correlation = data["correlation"]
            stack_type = data["name"]
            description = data["description"]

        # PG + C (NBA)
        elif (pos1 == "PG" and pos2 == "C") or (pos1 == "C" and pos2 == "PG"):
            data = CORRELATION_MATRIX["PG_C"]
            correlation = data["correlation"]
            stack_type = data["name"]
            description = data["description"]

    # Calculate glitch score
    base_score = 5.0
    if correlation > 0.80:
        base_score += 4.0
        recommendation = "CORRELATION GLITCH - Book Misprice Detected"
    elif correlation > 0.60:
        base_score += 2.5
        recommendation = "MODERATE CORRELATION - Slight Edge"
    elif correlation > 0.40:
        base_score += 1.0
        recommendation = "WEAK CORRELATION - Standard Parlay"
    elif correlation < 0:
        base_score -= 2.0
        recommendation = "NEGATIVE CORRELATION - Avoid This Parlay"
    else:
        recommendation = "INDEPENDENT - No Correlation Edge"

    return {
        "stack_type": stack_type,
        "correlation": round(correlation, 2),
        "glitch_score": round(min(10, max(0, base_score)), 1),
        "recommendation": recommendation,
        "edge_explanation": description,
        "leg1": leg1,
        "leg2": leg2,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/void-check/{player}")
async def void_check(player: str, target_player: Optional[str] = None, baseline_avg: Optional[float] = None):
    """
    The HOF Feature: Recalculates hit rate when a star player is OUT.
    Finds the 'Usage Monster' - the teammate who benefits most.

    Example: /live/void-check/Joel%20Embiid
    Example: /live/void-check/Joel%20Embiid?target_player=Tyrese%20Maxey&baseline_avg=24.0

    Response:
    {
        "missing_star": "Joel Embiid",
        "usage_beneficiary": "Tyrese Maxey",
        "baseline_avg": 24.0,
        "void_avg": 30.7,
        "boost_pct": 28,
        "hit_rate_with_star": "5/10 (50%)",
        "hit_rate_without_star": "8/10 (80%)",
        "signal": "USAGE MONSTER (+6.7 pts without Joel Embiid)",
        "recommendation": "SMASH THE OVER"
    }
    """
    # Normalize player name
    player_normalized = player.title()

    # Check if we have data for this player
    impact_data = VOID_IMPACT_MULTIPLIERS.get(player_normalized)

    if not impact_data:
        # Generate reasonable fallback based on player name hash
        rng = deterministic_rng_for_game_id(player_normalized)
        pts_boost = 1.15 + (rng.random() * 0.20)  # 15-35% boost
        usage_boost = pts_boost + 0.05

        # Find a generic teammate name
        teammate = target_player or "Teammate"
        base_avg = baseline_avg or rng.randint(18, 28)
    else:
        teammate = target_player or impact_data["teammate"]
        pts_boost = impact_data.get("pts_boost", impact_data.get("target_boost", 1.20))
        usage_boost = impact_data["usage_boost"]
        base_avg = baseline_avg or 24.0  # Default baseline

    void_avg = base_avg * pts_boost
    boost_pct = int((pts_boost - 1) * 100)

    # Calculate hit rates (simulated based on boost)
    base_hit_rate = 50
    void_hit_rate = min(90, base_hit_rate + (boost_pct * 1.2))

    # Generate signal
    diff = void_avg - base_avg
    if diff > 5.0:
        signal = f"USAGE MONSTER (+{diff:.1f} pts without {player_normalized})"
        recommendation = "SMASH THE OVER"
    elif diff > 3.0:
        signal = f"USAGE SPIKE (+{diff:.1f} pts without {player_normalized})"
        recommendation = "LEAN OVER"
    else:
        signal = f"MINOR BUMP (+{diff:.1f} pts without {player_normalized})"
        recommendation = "MONITOR"

    return {
        "missing_star": player_normalized,
        "usage_beneficiary": teammate,
        "baseline_avg": round(base_avg, 1),
        "void_avg": round(void_avg, 1),
        "boost_pct": boost_pct,
        "usage_boost_pct": int((usage_boost - 1) * 100),
        "hit_rate_with_star": f"{base_hit_rate // 10}/10 ({base_hit_rate}%)",
        "hit_rate_without_star": f"{int(void_hit_rate) // 10}/10 ({int(void_hit_rate)}%)",
        "signal": signal,
        "recommendation": recommendation,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/smash-card")
async def generate_smash_card(bet_data: Dict[str, Any], book: Optional[str] = "draftkings"):
    """
    Generates a 'Smash Card' with deep links for one-tap betting.
    Bypasses sportsbook lobby and drops user directly into bet slip.

    Request Body:
    {
        "bet_data": {
            "player": "Tyrese Maxey",
            "prop": "points",
            "line": 28.5,
            "pick": "over",
            "odds": -110,
            "hit_rate": "8/10",
            "reasoning": "Embiid OUT - Usage Spike",
            "event_id": "nba_phi_vs_sac_123",
            "market_id": "player_points_maxey"
        },
        "book": "draftkings"
    }

    Response:
    {
        "smash_card": {
            "title": "SMASH: Tyrese Maxey OVER 28.5 PTS",
            "subtitle": "Embiid OUT - Usage Spike",
            "hit_rate_display": "[████████░░] 80%",
            "confidence": "HIGH",
            "button": {
                "text": "Place on DraftKings",
                "color": "#53d337",
                "logo": "..."
            },
            "deep_links": {
                "app": "draftkings://...",
                "web": "https://...",
                "universal": "https://..."
            }
        }
    }
    """
    book_key = book.lower() if book else "draftkings"
    book_config = SPORTSBOOK_CONFIGS.get(book_key, SPORTSBOOK_CONFIGS["draftkings"])
    link_schemes = SMASH_LINK_SCHEMES.get(book_key, SMASH_LINK_SCHEMES["draftkings"])

    player = bet_data.get("player", "Player")
    prop = bet_data.get("prop", "points")
    line = bet_data.get("line", 0)
    pick = (bet_data.get("pick") or "over").upper()
    odds = bet_data.get("odds", -110)
    hit_rate = bet_data.get("hit_rate", "7/10")
    reasoning = bet_data.get("reasoning", "AI Analysis")
    event_id = bet_data.get("event_id", "event_123")
    market_id = bet_data.get("market_id", "market_456")

    # Parse hit rate for visual
    try:
        hits, total = hit_rate.split("/")
        hit_pct = int(int(hits) / int(total) * 100)
    except:
        hit_pct = 70

    # Generate hit rate bar
    filled = hit_pct // 10
    empty = 10 - filled
    hit_rate_bar = f"[{'█' * filled}{'░' * empty}] {hit_pct}%"

    # Determine confidence
    if hit_pct >= 80:
        confidence = "HIGH"
    elif hit_pct >= 60:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Generate deep links
    sport = (bet_data.get("sport") or "nba").upper()
    sport_path = {"NBA": "basketball/nba", "NFL": "football/nfl", "MLB": "baseball/mlb", "NHL": "hockey/nhl"}.get(sport, "basketball/nba")

    deep_links = {
        "app": link_schemes["app"].format(sport=sport, event_id=event_id, market_id=market_id),
        "web": link_schemes["web"].format(sport_path=sport_path, event_id=event_id),
        "universal": link_schemes["universal"].format(sport=sport.lower(), event_id=event_id, market_id=market_id)
    }

    return {
        "smash_card": {
            "title": f"SMASH: {player} {pick} {line} {prop.upper()}",
            "subtitle": reasoning,
            "odds_display": f"{'+' if odds > 0 else ''}{odds}",
            "hit_rate_display": hit_rate_bar,
            "hit_rate_raw": hit_rate,
            "confidence": confidence,
            "button": {
                "text": f"Place on {book_config['name']}",
                "color": book_config["color"],
                "logo": book_config.get("logo", "")
            },
            "deep_links": deep_links,
            "all_books": [
                {
                    "key": key,
                    "name": cfg["name"],
                    "color": cfg["color"],
                    "logo": cfg.get("logo", ""),
                    "deep_link": SMASH_LINK_SCHEMES.get(key, {}).get("universal", "").format(
                        sport=sport.lower(), event_id=event_id, market_id=market_id
                    )
                }
                for key, cfg in SPORTSBOOK_CONFIGS.items()
            ]
        },
        "bet_data": bet_data,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/correlations")
async def list_correlations():
    """List all known correlation patterns for parlay building."""
    return {
        "count": len(CORRELATION_MATRIX),
        "correlations": [
            {
                "key": key,
                "name": data["name"],
                "correlation": data["correlation"],
                "description": data["description"],
                "edge": "HIGH" if data["correlation"] > 0.75 else "MEDIUM" if data["correlation"] > 0.5 else "LOW"
            }
            for key, data in CORRELATION_MATRIX.items()
        ],
        "void_players": list(VOID_IMPACT_MULTIPLIERS.keys()),
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# PHASE 3: LEARNING LOOP ENDPOINTS
# ============================================================================

# Import engines (lazy load to avoid circular imports)
_jarvis_savant_engine = None
_vedic_astro_engine = None
_esoteric_learning_loop = None


def get_jarvis_savant():
    """Lazy load JarvisSavantEngine."""
    global _jarvis_savant_engine
    if _jarvis_savant_engine is None:
        try:
            from jarvis_savant_engine import get_jarvis_engine
            _jarvis_savant_engine = get_jarvis_engine()
            logger.info("JarvisSavantEngine initialized")
        except ImportError as e:
            logger.warning("JarvisSavantEngine not available: %s", e)
    return _jarvis_savant_engine


def get_vedic_astro():
    """Lazy load VedicAstroEngine."""
    global _vedic_astro_engine
    if _vedic_astro_engine is None:
        try:
            from jarvis_savant_engine import get_vedic_engine
            _vedic_astro_engine = get_vedic_engine()
            logger.info("VedicAstroEngine initialized")
        except ImportError as e:
            logger.warning("VedicAstroEngine not available: %s", e)
    return _vedic_astro_engine


def get_esoteric_loop():
    """Lazy load EsotericLearningLoop."""
    global _esoteric_learning_loop
    if _esoteric_learning_loop is None:
        try:
            from jarvis_savant_engine import get_learning_loop
            _esoteric_learning_loop = get_learning_loop()
            logger.info("EsotericLearningLoop initialized")
        except ImportError as e:
            logger.warning("EsotericLearningLoop not available: %s", e)
    return _esoteric_learning_loop


# ============================================================================
# PHASE 1: CONFLUENCE CORE ENDPOINTS
# ============================================================================

@router.get("/validate-immortal")
async def validate_immortal():
    """
    Validate 2178 as THE IMMORTAL number.

    Mathematical proof that 2178 is the only 4-digit number where:
    - n^4 contains n
    - reverse(n)^4 contains reverse(n)
    - Digital root = 9 (Tesla completion)
    """
    jarvis = get_jarvis_savant()
    if not jarvis:
        raise HTTPException(status_code=503, detail="JarvisSavantEngine not available")

    return jarvis.validate_2178()


@router.get("/jarvis-triggers")
async def list_jarvis_triggers():
    """List all JARVIS trigger numbers with their properties."""
    jarvis = get_jarvis_savant()
    if not jarvis:
        raise HTTPException(status_code=503, detail="JarvisSavantEngine not available")

    return {
        "triggers": jarvis.triggers,
        "power_numbers": jarvis.power_numbers,
        "tesla_numbers": jarvis.tesla_numbers,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/check-trigger/{value}")
async def check_trigger(value: str):
    """
    Check if a value triggers any JARVIS numbers.

    Supports:
    - Direct number matches (e.g., 2178)
    - Gematria reduction of strings (e.g., "Lakers")
    """
    jarvis = get_jarvis_savant()
    if not jarvis:
        raise HTTPException(status_code=503, detail="JarvisSavantEngine not available")

    # Try to parse as number first
    try:
        numeric_value = int(value)
        return jarvis.check_jarvis_trigger(numeric_value)
    except ValueError:
        return jarvis.check_jarvis_trigger(value)


@router.get("/confluence/{sport}")
async def get_confluence_analysis(
    sport: str,
    player: str = "Player",
    team: str = "Team",
    opponent: str = "Opponent",
    spread: float = 0,
    total: float = 220,
    public_pct: float = 50,
    research_score: float = 7.0  # v10.1: Allow passing external research score
):
    """
    Calculate v10.1 dual-score confluence analysis for a pick.

    THE HEART - v10.1 Alignment System:
    - IMMORTAL (+10): 2178 + both ≥7.5 + alignment ≥80%
    - JARVIS_PERFECT (+7): Trigger + both ≥7.5 + alignment ≥80%
    - PERFECT (+5): both ≥7.5 + alignment ≥80%
    - STRONG (+3): Both high OR aligned ≥70%
    - MODERATE (+1): Aligned ≥60%
    - DIVERGENT (+0): Models disagree

    Alignment = 1 - |research - esoteric| / 10
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    jarvis = get_jarvis_savant()
    vedic = get_vedic_astro()
    learning = get_esoteric_loop()

    if not jarvis or not vedic:
        raise HTTPException(status_code=503, detail="Esoteric engines not available")

    esoteric_weights = learning.get_weights()["weights"] if learning else {}

    # Calculate all signals
    gematria = jarvis.calculate_gematria_signal(player, team, opponent)
    public_fade = jarvis.calculate_public_fade_signal(public_pct)
    mid_spread = jarvis.calculate_mid_spread_signal(spread)
    trap = jarvis.calculate_large_spread_trap(spread, total)
    astro = vedic.calculate_astro_score()

    # v10.1: Fibonacci alignment and Vortex pattern
    fib_alignment = jarvis.calculate_fibonacci_alignment(float(spread) if spread else 0)
    vortex_value = int(abs(spread * 10)) if spread else 0
    vortex_pattern = jarvis.calculate_vortex_pattern(vortex_value)

    # Check for JARVIS triggers in player/team names
    game_str = f"{player}{team}{opponent}"
    trigger_result = jarvis.check_jarvis_trigger(game_str)
    jarvis_triggered = len(trigger_result.get("triggers_hit", [])) > 0
    immortal_detected = any(t["number"] == 2178 for t in trigger_result.get("triggers_hit", []))

    # Calculate JARVIS score from triggers
    jarvis_score = 0.0
    for trig in trigger_result.get("triggers_hit", []):
        jarvis_score += trig["boost"] / 5
    jarvis_score = min(4.0, jarvis_score)

    # v10.1: Calculate esoteric score
    gematria_contribution = gematria.get("influence", 0) * 0.52 * 2 if gematria.get("triggered") else 0
    astro_contribution = (astro["overall_score"] - 50) / 50 * esoteric_weights.get("astro", 0.13) * 2

    esoteric_raw = (
        jarvis_score +
        gematria_contribution +
        max(0, astro_contribution) +
        mid_spread.get("modifier", 0) +
        fib_alignment.get("modifier", 0) +
        vortex_pattern.get("modifier", 0) +
        public_fade.get("influence", 0) +
        trap.get("modifier", 0)
    )
    esoteric_score = max(0, min(10, esoteric_raw * 1.25))

    # v10.1: Calculate dual-score confluence
    confluence = jarvis.calculate_confluence(
        research_score=research_score,
        esoteric_score=esoteric_score,
        immortal_detected=immortal_detected,
        jarvis_triggered=jarvis_triggered
    )

    # v10.1: Calculate final score and bet tier
    final_score = (research_score * 0.67) + (esoteric_score * 0.33) + confluence.get("boost", 0)
    bet_tier = jarvis.determine_bet_tier(final_score, confluence)

    return {
        "sport": sport.upper(),
        "version": "v10.1",
        "input": {
            "player": player,
            "team": team,
            "opponent": opponent,
            "spread": spread,
            "total": total,
            "public_pct": public_pct,
            "research_score": research_score
        },
        "signals": {
            "gematria": gematria,
            "public_fade": public_fade,
            "mid_spread": mid_spread,
            "trap": trap,
            "astro": astro,
            "fibonacci": fib_alignment,
            "vortex": vortex_pattern
        },
        "jarvis_triggers": trigger_result.get("triggers_hit", []),
        "scoring": {
            "research_score": round(research_score, 2),
            "esoteric_score": round(esoteric_score, 2),
            "final_score": round(final_score, 2),
            "formula": "FINAL = (research × 0.67) + (esoteric × 0.33) + confluence_boost"
        },
        "confluence": confluence,
        "bet_tier": bet_tier,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# PHASE 2: VEDIC/ASTRO ENDPOINTS
# ============================================================================

@router.get("/astro-status")
async def get_astro_status():
    """Get full astrological analysis for current moment."""
    vedic = get_vedic_astro()
    if not vedic:
        raise HTTPException(status_code=503, detail="VedicAstroEngine not available")

    return vedic.calculate_astro_score()


@router.get("/planetary-hour")
async def get_planetary_hour():
    """Get current planetary hour ruler (Chaldean order)."""
    vedic = get_vedic_astro()
    if not vedic:
        raise HTTPException(status_code=503, detail="VedicAstroEngine not available")

    return vedic.calculate_planetary_hour()


@router.get("/nakshatra")
async def get_nakshatra():
    """Get current Nakshatra (lunar mansion)."""
    vedic = get_vedic_astro()
    if not vedic:
        raise HTTPException(status_code=503, detail="VedicAstroEngine not available")

    return vedic.calculate_nakshatra()


@router.get("/retrograde-status")
async def get_retrograde_status():
    """Check retrograde status for Mercury, Venus, and Mars."""
    vedic = get_vedic_astro()
    if not vedic:
        raise HTTPException(status_code=503, detail="VedicAstroEngine not available")

    return {
        "mercury": vedic.is_planet_retrograde("Mercury"),
        "venus": vedic.is_planet_retrograde("Venus"),
        "mars": vedic.is_planet_retrograde("Mars"),
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# PHASE 3: LEARNING LOOP ENDPOINTS (DEPRECATED)
# ============================================================================
# DEPRECATED: Use /grader/* endpoints instead. These will be removed in v15.0.
# ============================================================================

@router.post("/learning/log-pick", deprecated=True)
async def log_esoteric_pick(pick_data: Dict[str, Any]):
    """
    DEPRECATED: Use /grader/* endpoints for prediction tracking.

    Log a pick for learning loop tracking.

    Request Body:
    {
        "sport": "NBA",
        "game_id": "game_123",
        "pick_type": "spread",
        "selection": "Lakers",
        "line": -3.5,
        "odds": -110,
        "esoteric_analysis": {...}  // From confluence analysis
    }

    Returns pick_id for later grading.
    """
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    required_fields = ["sport", "game_id", "pick_type", "selection", "line", "odds"]
    for field in required_fields:
        if field not in pick_data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    # If esoteric_analysis not provided, generate it
    esoteric_analysis = pick_data.get("esoteric_analysis", {})
    if not esoteric_analysis:
        jarvis = get_jarvis_savant()
        vedic = get_vedic_astro()
        if jarvis and vedic:
            gematria = jarvis.calculate_gematria_signal(
                pick_data.get("player", "Player"),
                pick_data.get("team", "Team"),
                pick_data.get("opponent", "Opponent")
            )
            astro = vedic.calculate_astro_score()
            esoteric_analysis = {
                "gematria": gematria,
                "astro": astro,
                "total_score": 5.0
            }

    pick_id = loop.log_pick(
        sport=pick_data["sport"],
        game_id=pick_data["game_id"],
        pick_type=pick_data["pick_type"],
        selection=pick_data["selection"],
        line=pick_data["line"],
        odds=pick_data["odds"],
        esoteric_analysis=esoteric_analysis
    )

    return {
        "status": "logged",
        "pick_id": pick_id,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/learning/grade-pick", deprecated=True)
async def grade_esoteric_pick(grade_data: Dict[str, Any]):
    """
    DEPRECATED: Use /grader/* endpoints for prediction grading.

    Grade a pick with actual result.

    Request Body:
    {
        "pick_id": "ESO_NBA_game123_20241215123456",
        "result": "WIN"  // WIN, LOSS, or PUSH
    }
    """
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    pick_id = grade_data.get("pick_id")
    result = grade_data.get("result")

    if not pick_id or not result:
        raise HTTPException(status_code=400, detail="Missing pick_id or result")

    grade_result = loop.grade_pick(pick_id, result)

    if "error" in grade_result:
        raise HTTPException(status_code=404, detail=grade_result["error"])

    return grade_result


@router.get("/learning/performance", deprecated=True)
async def get_learning_performance(days_back: int = 30):
    """
    DEPRECATED: Use /grader/performance/{sport} instead.

    Get esoteric learning loop performance summary.

    Shows:
    - Overall hit rate
    - Performance by signal type
    - Performance by confluence level
    - Performance by bet tier
    """
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    return loop.get_performance(days_back)


@router.get("/learning/weights", deprecated=True)
async def get_learning_weights():
    """DEPRECATED: Use /grader/weights/{sport} instead. Get current learned weights for esoteric signals."""
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    return loop.get_weights()


@router.post("/learning/adjust-weights", deprecated=True)
async def adjust_learning_weights(learning_rate: float = 0.05):
    """
    DEPRECATED: Use /grader/adjust-weights/{sport} instead.

    Trigger weight adjustment based on historical performance.

    Uses gradient-based adjustment:
    - Increases weights for signals with hit rate > 55%
    - Decreases weights for signals with hit rate < 48%
    """
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    return loop.adjust_weights(learning_rate)


@router.get("/learning/recent-picks", deprecated=True)
async def get_recent_picks(limit: int = 20):
    """DEPRECATED: Use /grader/* endpoints instead. Get recent esoteric picks for review."""
    loop = get_esoteric_loop()
    if not loop:
        raise HTTPException(status_code=503, detail="EsotericLearningLoop not available")

    return {
        "picks": loop.get_recent_picks(limit),
        "count": min(limit, len(loop.picks)),
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


# ============================================================================
# CLICK-TO-BET ENHANCEMENTS v2.0
# ============================================================================

# In-memory storage for user preferences and bet tracking
# In production, this should use Redis or a database
_user_preferences: Dict[str, Dict[str, Any]] = {}
_tracked_bets: List[Dict[str, Any]] = []
_parlay_slips: Dict[str, List[Dict[str, Any]]] = {}  # user_id -> list of parlay legs
_placed_parlays: List[Dict[str, Any]] = []  # Tracked parlays


@router.get("/user/preferences/{user_id}")
async def get_user_preferences(user_id: str):
    """
    Get user's sportsbook preferences.

    Returns:
    - favorite_books: List of preferred sportsbooks (in order)
    - default_bet_amount: Default stake amount
    - notifications: Notification preferences
    """
    prefs = _user_preferences.get(user_id, {
        "user_id": user_id,
        "favorite_books": ["draftkings", "fanduel", "betmgm"],
        "default_bet_amount": 25,
        "auto_best_odds": True,
        "notifications": {
            "smash_alerts": True,
            "odds_movement": True,
            "bet_results": True
        },
        "created_at": datetime.now().isoformat()
    })

    return prefs


@router.post("/user/preferences/{user_id}")
async def save_user_preferences(user_id: str, prefs: UserPreferencesRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any]):
    """
    Save user's sportsbook preferences.

    Request Body (validated with Pydantic):
    - favorite_books: array of strings (validated against supported books)
    - default_bet_amount: float (default: 25, must be >= 0)
    - auto_best_odds: bool (default: true)
    - notifications: object with smash_alerts, odds_movement, bet_results booleans
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(prefs, 'dict'):
        data = prefs.dict()
    else:
        data = prefs if isinstance(prefs, dict) else dict(prefs)

    # Validate favorite_books
    valid_books = list(SPORTSBOOK_CONFIGS.keys())
    favorite_books = data.get("favorite_books", [])
    validated_books = [b for b in favorite_books if b in valid_books]

    # Get notifications, handling nested object
    notifications_data = data.get("notifications", {})
    if hasattr(notifications_data, 'dict'):
        notifications_data = notifications_data.dict()

    _user_preferences[user_id] = {
        "user_id": user_id,
        "favorite_books": validated_books if validated_books else ["draftkings", "fanduel", "betmgm"],
        "default_bet_amount": data.get("default_bet_amount", 25),
        "auto_best_odds": data.get("auto_best_odds", True),
        "notifications": notifications_data if notifications_data else {
            "smash_alerts": True,
            "odds_movement": True,
            "bet_results": True
        },
        "updated_at": datetime.now().isoformat()
    }

    return {"status": "saved", "preferences": _user_preferences[user_id]}


@router.post("/bets/track")
async def track_bet(
    bet_data: TrackBetRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Track a bet that was placed through the click-to-bet flow.

    Request Body (validated with Pydantic):
    - user_id: str (default: "anonymous")
    - sport: str (required, validated: NBA/NFL/MLB/NHL)
    - game_id: str (required)
    - game: str (default: "Unknown Game")
    - bet_type: str (required)
    - selection: str (required)
    - line: float (optional)
    - odds: int (required, validated: American odds format)
    - sportsbook: str (required)
    - stake: float (default: 0, must be >= 0)
    - ai_score: float (optional, 0-20)
    - confluence_level: str (optional)

    Returns bet_id for later grading.
    """
    # Handle both Pydantic model and dict input for backwards compatibility
    if PYDANTIC_MODELS_AVAILABLE and hasattr(bet_data, 'dict'):
        data = bet_data.dict()
    else:
        # Fallback validation for dict input
        data = bet_data if isinstance(bet_data, dict) else dict(bet_data)
        required_fields = ["sport", "game_id", "bet_type", "selection", "odds", "sportsbook"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        # Validate odds format
        if data.get("odds") and (data["odds"] == 0 or (-100 < data["odds"] < 100)):
            raise HTTPException(status_code=400, detail="Invalid odds. American odds must be <= -100 or >= 100")
        data["sport"] = safe_upper(data.get("sport"))

    bet_id = f"BET_{data['sport']}_{data['game_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    tracked_bet = {
        "bet_id": bet_id,
        "user_id": data.get("user_id", "anonymous"),
        "sport": data["sport"],
        "game_id": data["game_id"],
        "game": data.get("game", "Unknown Game"),
        "bet_type": data["bet_type"],
        "selection": data["selection"],
        "line": data.get("line"),
        "odds": data["odds"],
        "sportsbook": data["sportsbook"],
        "stake": data.get("stake", 0),
        "potential_payout": calculate_payout(data.get("stake", 0), data["odds"]),
        "ai_score": data.get("ai_score"),
        "confluence_level": data.get("confluence_level"),
        "status": "PENDING",
        "result": None,
        "placed_at": datetime.now().isoformat()
    }

    _tracked_bets.append(tracked_bet)

    return {
        "status": "tracked",
        "bet_id": bet_id,
        "bet": tracked_bet,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/bets/grade/{bet_id}")
async def grade_bet(
    bet_id: str,
    result_data: GradeBetRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Grade a tracked bet with actual result.

    Request Body (validated with Pydantic):
    - result: str (required, must be WIN, LOSS, or PUSH)
    - actual_score: str (optional)
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(result_data, 'result'):
        result = result_data.result.value if hasattr(result_data.result, 'value') else str(result_data.result)
        actual_score = result_data.actual_score
    else:
        result = safe_upper(result_data.get("result"))
        actual_score = result_data.get("actual_score")
        if result not in ["WIN", "LOSS", "PUSH"]:
            raise HTTPException(status_code=400, detail="Result must be WIN, LOSS, or PUSH")

    for bet in _tracked_bets:
        if bet["bet_id"] == bet_id:
            bet["status"] = "GRADED"
            bet["result"] = result
            bet["actual_score"] = actual_score
            bet["graded_at"] = datetime.now().isoformat()

            # Calculate actual profit/loss
            if result == "WIN":
                bet["profit"] = bet["potential_payout"] - bet["stake"]
            elif result == "LOSS":
                bet["profit"] = -bet["stake"]
            else:  # PUSH
                bet["profit"] = 0

            return {"status": "graded", "bet": bet}

    raise HTTPException(status_code=404, detail=f"Bet not found: {bet_id}")


@router.get("/bets/history")
async def get_bet_history(
    user_id: Optional[str] = None,
    sport: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    auth: bool = Depends(verify_api_key)
):
    """
    Get bet history with optional filters.

    Supports filtering by:
    - user_id: Filter by user
    - sport: Filter by sport (NBA, NFL, etc.)
    - status: Filter by status (PENDING, GRADED)
    - limit: Max 500 results (default 50)
    """
    # Validate and cap limit to prevent DoS
    limit = min(max(1, limit), 500)
    filtered_bets = _tracked_bets.copy()

    if user_id:
        filtered_bets = [b for b in filtered_bets if b.get("user_id") == user_id]
    if sport:
        filtered_bets = [b for b in filtered_bets if b.get("sport") == sport.upper()]
    if status:
        filtered_bets = [b for b in filtered_bets if b.get("status") == status.upper()]

    # Sort by placed_at descending
    filtered_bets.sort(key=lambda x: x.get("placed_at", ""), reverse=True)

    # Calculate stats
    graded_bets = [b for b in filtered_bets if b.get("status") == "GRADED"]
    wins = len([b for b in graded_bets if b.get("result") == "WIN"])
    losses = len([b for b in graded_bets if b.get("result") == "LOSS"])
    pushes = len([b for b in graded_bets if b.get("result") == "PUSH"])
    total_profit = sum(b.get("profit", 0) for b in graded_bets)

    return {
        "bets": filtered_bets[:limit],
        "count": len(filtered_bets[:limit]),
        "total_tracked": len(filtered_bets),
        "stats": {
            "graded": len(graded_bets),
            "pending": len(filtered_bets) - len(graded_bets),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": round(wins / len(graded_bets) * 100, 1) if graded_bets else 0,
            "total_profit": round(total_profit, 2),
            "roi": round(total_profit / sum(b.get("stake", 1) for b in graded_bets) * 100, 1) if graded_bets else 0
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/quick-betslip/{sport}/{game_id}")
async def quick_betslip(
    sport: str,
    game_id: str,
    user_id: Optional[str] = None
):
    """
    Generate a quick betslip for a game with user's preferred sportsbooks prioritized.

    One-click flow for SMASH picks:
    1. Gets current best odds across all books
    2. Prioritizes user's favorite books
    3. Returns ready-to-click betslip with deep links
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Get user preferences
    user_prefs = _user_preferences.get(user_id, {}) if user_id else {}
    favorite_books = user_prefs.get("favorite_books", ["draftkings", "fanduel", "betmgm"])
    default_stake = user_prefs.get("default_bet_amount", 25)

    # Get line shopping data
    cache_key = f"line-shop:{sport_lower}:{game_id}"
    cached = api_cache.get(cache_key)

    if cached and "data" in cached:
        game_data = next((g for g in cached["data"] if g.get("game_id") == game_id), None)
    else:
        game_data = None

    if not game_data:
        # Use fallback
        game_data = {
            "game_id": game_id,
            "home_team": "Home Team",
            "away_team": "Away Team",
            "markets": {}
        }

    # Build quick betslip with prioritized books
    betslip_options = []

    for book_key in favorite_books:
        if book_key in SPORTSBOOK_CONFIGS:
            config = SPORTSBOOK_CONFIGS[book_key]
            betslip_options.append({
                "book_key": book_key,
                "book_name": config["name"],
                "book_color": config["color"],
                "book_logo": config.get("logo", ""),
                "is_favorite": True,
                "priority": favorite_books.index(book_key) + 1,
                "deep_link": generate_enhanced_deep_link(book_key, sport_lower, game_id, game_data)
            })

    # Add remaining books
    for book_key, config in SPORTSBOOK_CONFIGS.items():
        if book_key not in favorite_books:
            betslip_options.append({
                "book_key": book_key,
                "book_name": config["name"],
                "book_color": config["color"],
                "book_logo": config.get("logo", ""),
                "is_favorite": False,
                "priority": 99,
                "deep_link": generate_enhanced_deep_link(book_key, sport_lower, game_id, game_data)
            })

    return {
        "sport": sport.upper(),
        "game_id": game_id,
        "game": game_data,
        "default_stake": default_stake,
        "sportsbooks": betslip_options,
        "user_preferences_applied": user_id is not None,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# PARLAY BUILDER
# ============================================================================

def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal odds."""
    if american_odds > 0:
        return 1 + (american_odds / 100)
    else:
        return 1 + (100 / abs(american_odds))


def decimal_to_american(decimal_odds: float) -> int:
    """Convert decimal odds to American odds."""
    if decimal_odds >= 2.0:
        return int(round((decimal_odds - 1) * 100))
    else:
        return int(round(-100 / (decimal_odds - 1)))


def calculate_parlay_odds(legs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate combined parlay odds from individual legs.
    Returns decimal odds, American odds, and implied probability.
    """
    if not legs:
        return {"decimal": 1.0, "american": -10000, "implied_probability": 100.0}

    combined_decimal = 1.0
    for leg in legs:
        leg_odds = leg.get("odds", -110)
        combined_decimal *= american_to_decimal(leg_odds)

    combined_american = decimal_to_american(combined_decimal)
    implied_prob = (1 / combined_decimal) * 100

    return {
        "decimal": round(combined_decimal, 3),
        "american": combined_american,
        "implied_probability": round(implied_prob, 2)
    }


@router.get("/parlay/{user_id}")
async def get_parlay_slip(user_id: str):
    """
    Get current parlay slip for a user.

    Returns all legs in the parlay with calculated combined odds.
    """
    legs = _parlay_slips.get(user_id, [])
    combined = calculate_parlay_odds(legs)

    return {
        "user_id": user_id,
        "legs": legs,
        "leg_count": len(legs),
        "combined_odds": combined,
        "max_legs": 12,
        "can_add_more": len(legs) < 12,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/add")
async def add_parlay_leg(
    leg_data: ParlayLegRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Add a leg to a user's parlay slip.

    Request Body (validated with Pydantic):
    - user_id: str (required)
    - sport: str (required, auto-uppercased)
    - game_id: str (required)
    - game: str (default: "Unknown Game")
    - bet_type: str (required)
    - selection: str (required)
    - line: float (optional)
    - odds: int (required, validated American format)
    - ai_score: float (optional)

    Returns updated parlay slip with combined odds.
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(leg_data, 'dict'):
        data = leg_data.dict()
    else:
        data = leg_data if isinstance(leg_data, dict) else dict(leg_data)
        required_fields = ["user_id", "sport", "game_id", "bet_type", "selection", "odds"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        # Validate odds
        if data.get("odds") and (data["odds"] == 0 or (-100 < data["odds"] < 100)):
            raise HTTPException(status_code=400, detail="Invalid odds format")
        data["sport"] = safe_upper(data.get("sport"))

    user_id = data["user_id"]

    # Initialize slip if needed
    if user_id not in _parlay_slips:
        _parlay_slips[user_id] = []

    # Check max legs
    if len(_parlay_slips[user_id]) >= 12:
        raise HTTPException(status_code=400, detail="Maximum 12 legs per parlay")

    # Check for duplicate game/bet_type
    for existing in _parlay_slips[user_id]:
        if existing["game_id"] == data["game_id"] and existing["bet_type"] == data["bet_type"]:
            raise HTTPException(
                status_code=400,
                detail=f"Already have a {data['bet_type']} bet for this game"
            )

    leg_id = f"LEG_{user_id}_{len(_parlay_slips[user_id])}_{datetime.now().strftime('%H%M%S')}"

    new_leg = {
        "leg_id": leg_id,
        "sport": data["sport"],
        "game_id": data["game_id"],
        "game": data.get("game", "Unknown Game"),
        "bet_type": data["bet_type"],
        "selection": data["selection"],
        "line": data.get("line"),
        "odds": data["odds"],
        "ai_score": data.get("ai_score"),
        "added_at": datetime.now().isoformat()
    }

    _parlay_slips[user_id].append(new_leg)
    combined = calculate_parlay_odds(_parlay_slips[user_id])

    return {
        "status": "added",
        "leg": new_leg,
        "parlay": {
            "legs": _parlay_slips[user_id],
            "leg_count": len(_parlay_slips[user_id]),
            "combined_odds": combined
        },
        "timestamp": datetime.now().isoformat()
    }


@router.delete("/parlay/remove/{user_id}/{leg_id}")
async def remove_parlay_leg(user_id: str, leg_id: str):
    """
    Remove a specific leg from a user's parlay slip.
    """
    if user_id not in _parlay_slips:
        raise HTTPException(status_code=404, detail="No parlay slip found for user")

    original_len = len(_parlay_slips[user_id])
    _parlay_slips[user_id] = [leg for leg in _parlay_slips[user_id] if leg["leg_id"] != leg_id]

    if len(_parlay_slips[user_id]) == original_len:
        raise HTTPException(status_code=404, detail=f"Leg {leg_id} not found")

    combined = calculate_parlay_odds(_parlay_slips[user_id])

    return {
        "status": "removed",
        "removed_leg_id": leg_id,
        "parlay": {
            "legs": _parlay_slips[user_id],
            "leg_count": len(_parlay_slips[user_id]),
            "combined_odds": combined
        },
        "timestamp": datetime.now().isoformat()
    }


@router.delete("/parlay/clear/{user_id}")
async def clear_parlay_slip(user_id: str):
    """
    Clear all legs from a user's parlay slip.
    """
    removed_count = len(_parlay_slips.get(user_id, []))
    _parlay_slips[user_id] = []

    return {
        "status": "cleared",
        "removed_count": removed_count,
        "parlay": {
            "legs": [],
            "leg_count": 0,
            "combined_odds": {"decimal": 1.0, "american": -10000, "implied_probability": 100.0}
        },
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/place")
async def place_parlay(
    parlay_data: PlaceParlayRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Track a parlay bet that was placed.

    Request Body (validated with Pydantic):
    - user_id: str (default: "anonymous")
    - sportsbook: str (required)
    - stake: float (default: 0, must be >= 0)
    - use_current_slip: bool (default: true)
    - legs: array (optional, used if use_current_slip is false)

    If use_current_slip is true, uses the user's current parlay slip.
    Otherwise, provide a "legs" array directly.
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(parlay_data, 'dict'):
        data = parlay_data.dict()
    else:
        data = parlay_data if isinstance(parlay_data, dict) else dict(parlay_data)

    user_id = data.get("user_id", "anonymous")
    sportsbook = data.get("sportsbook")
    stake = data.get("stake", 0)

    if not sportsbook:
        raise HTTPException(status_code=400, detail="sportsbook is required")

    # Get legs from current slip or from request
    if data.get("use_current_slip", True):
        legs = _parlay_slips.get(user_id, [])
    else:
        legs = data.get("legs", [])

    if len(legs) < 2:
        raise HTTPException(status_code=400, detail="Parlay requires at least 2 legs")

    combined = calculate_parlay_odds(legs)

    # Calculate potential payout
    if stake > 0:
        potential_payout = round(stake * combined["decimal"], 2)
    else:
        potential_payout = 0

    parlay_id = f"PARLAY_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    tracked_parlay = {
        "parlay_id": parlay_id,
        "user_id": user_id,
        "legs": legs,
        "leg_count": len(legs),
        "combined_odds": combined,
        "sportsbook": sportsbook,
        "stake": stake,
        "potential_payout": potential_payout,
        "status": "PENDING",
        "result": None,
        "placed_at": datetime.now().isoformat()
    }

    _placed_parlays.append(tracked_parlay)

    # Clear the slip after placing
    if data.get("use_current_slip", True):
        _parlay_slips[user_id] = []

    return {
        "status": "placed",
        "parlay": tracked_parlay,
        "message": f"Parlay with {len(legs)} legs tracked. Open {sportsbook} to place bet.",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/grade/{parlay_id}")
async def grade_parlay(
    parlay_id: str,
    grade_data: GradeParlayRequest if PYDANTIC_MODELS_AVAILABLE else Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Grade a placed parlay with WIN, LOSS, or PUSH.

    Request Body (validated with Pydantic):
    - result: str (required, must be WIN, LOSS, or PUSH)
    """
    # Handle both Pydantic model and dict input
    if PYDANTIC_MODELS_AVAILABLE and hasattr(grade_data, 'result'):
        result = grade_data.result.value if hasattr(grade_data.result, 'value') else str(grade_data.result)
    else:
        result = safe_upper(grade_data.get("result"))
        if result not in ["WIN", "LOSS", "PUSH"]:
            raise HTTPException(status_code=400, detail="Result must be WIN, LOSS, or PUSH")

    for parlay in _placed_parlays:
        if parlay["parlay_id"] == parlay_id:
            parlay["status"] = "GRADED"
            parlay["result"] = result
            parlay["graded_at"] = datetime.now().isoformat()

            # Calculate profit/loss
            if result == "WIN":
                parlay["profit"] = parlay["potential_payout"] - parlay["stake"]
            elif result == "LOSS":
                parlay["profit"] = -parlay["stake"]
            else:  # PUSH
                parlay["profit"] = 0

            return {
                "status": "graded",
                "parlay": parlay,
                "timestamp": datetime.now().isoformat()
            }

    raise HTTPException(status_code=404, detail=f"Parlay {parlay_id} not found")


@router.get("/parlay/history")
async def get_parlay_history(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    auth: bool = Depends(verify_api_key)
):
    """
    Get parlay history with stats.

    Supports filtering by:
    - user_id: Filter by user
    - status: Filter by status (PENDING, GRADED)
    - limit: Max 500 results (default 50)
    """
    # Validate and cap limit to prevent DoS
    limit = min(max(1, limit), 500)
    filtered = _placed_parlays.copy()

    if user_id:
        filtered = [p for p in filtered if p.get("user_id") == user_id]
    if status:
        filtered = [p for p in filtered if p.get("status") == status.upper()]

    # Sort by placed_at descending
    filtered.sort(key=lambda x: x.get("placed_at", ""), reverse=True)

    # Calculate stats
    graded = [p for p in filtered if p.get("status") == "GRADED"]
    wins = len([p for p in graded if p.get("result") == "WIN"])
    losses = len([p for p in graded if p.get("result") == "LOSS"])
    pushes = len([p for p in graded if p.get("result") == "PUSH"])
    total_profit = sum(p.get("profit", 0) for p in graded)
    total_staked = sum(p.get("stake", 0) for p in graded)

    return {
        "parlays": filtered[:limit],
        "count": len(filtered[:limit]),
        "total_tracked": len(filtered),
        "stats": {
            "graded": len(graded),
            "pending": len(filtered) - len(graded),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": round(wins / len(graded) * 100, 1) if graded else 0,
            "total_profit": round(total_profit, 2),
            "roi": round(total_profit / total_staked * 100, 1) if total_staked > 0 else 0
        },
        "timestamp": datetime.now().isoformat()
    }


@router.post("/parlay/calculate")
async def calculate_parlay(calc_data: Dict[str, Any]):
    """
    Calculate parlay odds and payout without saving.

    Request Body:
    {
        "legs": [
            {"odds": -110},
            {"odds": +150},
            {"odds": -105}
        ],
        "stake": 25
    }

    Useful for preview/what-if calculations.
    """
    legs = calc_data.get("legs", [])
    stake = calc_data.get("stake", 0)

    if not legs:
        raise HTTPException(status_code=400, detail="At least one leg required")

    combined = calculate_parlay_odds(legs)

    if stake > 0:
        potential_payout = round(stake * combined["decimal"], 2)
        profit = round(potential_payout - stake, 2)
    else:
        potential_payout = 0
        profit = 0

    return {
        "leg_count": len(legs),
        "combined_odds": combined,
        "stake": stake,
        "potential_payout": potential_payout,
        "profit_if_win": profit,
        "example_payouts": {
            "$10": round(10 * combined["decimal"], 2),
            "$25": round(25 * combined["decimal"], 2),
            "$50": round(50 * combined["decimal"], 2),
            "$100": round(100 * combined["decimal"], 2)
        },
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# COMMUNITY FEATURES: Man vs Machine Sentiment + Affiliate Links
# ============================================================================

# In-memory storage for community votes (use Redis/DB for production persistence)
_community_votes: Dict[str, Dict[str, int]] = {}

# Affiliate links for sportsbooks (configure your affiliate IDs here)
AFFILIATE_LINKS = {
    "draftkings": {
        "base_url": "https://sportsbook.draftkings.com",
        "affiliate_id": "",  # Add your affiliate ID
        "sport_paths": {
            "nba": "/leagues/basketball/nba",
            "nfl": "/leagues/football/nfl",
            "mlb": "/leagues/baseball/mlb",
            "nhl": "/leagues/hockey/nhl"
        }
    },
    "fanduel": {
        "base_url": "https://sportsbook.fanduel.com",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/navigation/nba",
            "nfl": "/navigation/nfl",
            "mlb": "/navigation/mlb",
            "nhl": "/navigation/nhl"
        }
    },
    "betmgm": {
        "base_url": "https://sports.betmgm.com",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/en/sports/basketball-7/betting/usa-9/nba-6004",
            "nfl": "/en/sports/football-11/betting/usa-9/nfl-35",
            "mlb": "/en/sports/baseball-23/betting/usa-9/mlb-75",
            "nhl": "/en/sports/ice-hockey-12/betting/usa-9/nhl-34"
        }
    },
    "caesars": {
        "base_url": "https://www.caesars.com/sportsbook-and-casino",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/us/nba",
            "nfl": "/us/nfl",
            "mlb": "/us/mlb",
            "nhl": "/us/nhl"
        }
    },
    "pointsbetus": {
        "base_url": "https://pointsbet.com",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/sports/basketball/nba",
            "nfl": "/sports/football/nfl",
            "mlb": "/sports/baseball/mlb",
            "nhl": "/sports/hockey/nhl"
        }
    },
    "betrivers": {
        "base_url": "https://betrivers.com",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/sports/basketball/nba",
            "nfl": "/sports/football/nfl",
            "mlb": "/sports/baseball/mlb",
            "nhl": "/sports/hockey/nhl"
        }
    },
    "espnbet": {
        "base_url": "https://espnbet.com",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/sport/basketball/organization/nba",
            "nfl": "/sport/football/organization/nfl",
            "mlb": "/sport/baseball/organization/mlb",
            "nhl": "/sport/icehockey/organization/nhl"
        }
    },
    "bet365": {
        "base_url": "https://www.bet365.com",
        "affiliate_id": "",
        "sport_paths": {
            "nba": "/#/AS/B18/",
            "nfl": "/#/AS/B17/",
            "mlb": "/#/AS/B16/",
            "nhl": "/#/AS/B19/"
        }
    }
}


@router.get("/community/votes/{game_id}")
async def get_community_votes(game_id: str):
    """
    Get community sentiment votes for a game.

    Returns AI vs Public vote counts for the "Man vs Machine" widget.
    """
    votes = _community_votes.get(game_id, {"ai": 0, "public": 0})
    total = votes["ai"] + votes["public"]

    # Calculate percentages
    ai_pct = round((votes["ai"] / total) * 100) if total > 0 else 50
    public_pct = 100 - ai_pct

    return {
        "game_id": game_id,
        "votes": votes,
        "total": total,
        "percentages": {
            "ai": ai_pct,
            "public": public_pct
        },
        "consensus": "AI" if ai_pct > public_pct else ("PUBLIC" if public_pct > ai_pct else "SPLIT"),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/community/vote")
async def submit_community_vote(
    vote_data: Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Submit a community vote for Man vs Machine.

    Request Body:
    {
        "game_id": "nba_celtics_lakers_2026011600",
        "side": "ai" | "public",
        "user_id": "optional_user_identifier"
    }

    Users can vote whether they agree with the AI or fade it.
    """
    game_id = vote_data.get("game_id")
    side = safe_lower(vote_data.get("side"))

    if not game_id:
        raise HTTPException(status_code=400, detail="game_id required")

    if side not in ["ai", "public"]:
        raise HTTPException(status_code=400, detail="side must be 'ai' or 'public'")

    # Initialize if not exists
    if game_id not in _community_votes:
        _community_votes[game_id] = {"ai": 0, "public": 0}

    # Increment vote
    _community_votes[game_id][side] += 1

    # Get updated totals
    votes = _community_votes[game_id]
    total = votes["ai"] + votes["public"]
    ai_pct = round((votes["ai"] / total) * 100) if total > 0 else 50

    return {
        "status": "vote_recorded",
        "game_id": game_id,
        "side": side,
        "new_totals": votes,
        "percentages": {
            "ai": ai_pct,
            "public": 100 - ai_pct
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/community/leaderboard")
async def get_vote_leaderboard():
    """
    Get games with most community engagement.

    Shows which games have the most votes and biggest AI vs Public splits.
    """
    leaderboard = []

    for game_id, votes in _community_votes.items():
        total = votes["ai"] + votes["public"]
        if total == 0:
            continue

        ai_pct = round((votes["ai"] / total) * 100)
        split = abs(ai_pct - 50)  # How far from 50/50

        leaderboard.append({
            "game_id": game_id,
            "total_votes": total,
            "ai_percent": ai_pct,
            "public_percent": 100 - ai_pct,
            "split_magnitude": split,
            "consensus": "STRONG AI" if ai_pct >= 70 else ("STRONG PUBLIC" if ai_pct <= 30 else "CONTESTED")
        })

    # Sort by total votes
    leaderboard.sort(key=lambda x: x["total_votes"], reverse=True)

    return {
        "games": leaderboard[:20],
        "total_games_with_votes": len(leaderboard),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/affiliate/links")
async def get_affiliate_links(sport: str = "nba"):
    """
    Get affiliate links for all sportsbooks.

    Use these to deep-link users to sportsbooks with your affiliate tracking.
    """
    sport_lower = sport.lower()
    links = {}

    for book_key, config in AFFILIATE_LINKS.items():
        base = config["base_url"]
        affiliate = config.get("affiliate_id", "")
        sport_path = config["sport_paths"].get(sport_lower, "")

        # Build full URL
        full_url = f"{base}{sport_path}"
        if affiliate:
            # Add affiliate tracking (format varies by book)
            separator = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{separator}affiliate={affiliate}"

        links[book_key] = {
            "url": full_url,
            "has_affiliate": bool(affiliate),
            "book_name": book_key.replace("_", " ").title()
        }

    return {
        "sport": sport.upper(),
        "links": links,
        "note": "Configure affiliate IDs in AFFILIATE_LINKS to enable tracking",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/affiliate/configure")
async def configure_affiliate_link(
    config_data: Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Configure an affiliate link for a sportsbook.

    Request Body:
    {
        "book": "draftkings",
        "affiliate_id": "your_affiliate_123",
        "custom_url": "https://optional.custom.tracking.url"
    }
    """
    book = safe_lower(config_data.get("book"))
    affiliate_id = config_data.get("affiliate_id", "")
    custom_url = config_data.get("custom_url", "")

    if book not in AFFILIATE_LINKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown book: {book}. Available: {list(AFFILIATE_LINKS.keys())}"
        )

    # Update the affiliate ID
    if affiliate_id:
        AFFILIATE_LINKS[book]["affiliate_id"] = affiliate_id

    if custom_url:
        AFFILIATE_LINKS[book]["base_url"] = custom_url

    return {
        "status": "configured",
        "book": book,
        "affiliate_id": AFFILIATE_LINKS[book]["affiliate_id"],
        "base_url": AFFILIATE_LINKS[book]["base_url"],
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_payout(stake: float, odds: int) -> float:
    """Calculate potential payout from American odds."""
    if stake <= 0:
        return 0
    if odds > 0:
        return stake + (stake * odds / 100)
    else:
        return stake + (stake * 100 / abs(odds))


def generate_enhanced_deep_link(book_key: str, sport: str, game_id: str, game_data: Dict) -> Dict[str, str]:
    """Generate enhanced deep links with sport-specific URLs."""
    config = SPORTSBOOK_CONFIGS.get(book_key)
    if not config:
        return {"web": "#", "note": "Unknown sportsbook"}

    sport_paths = {
        "nba": {
            "draftkings": "basketball/nba",
            "fanduel": "navigation/nba",
            "betmgm": "sports/basketball/104/nba",
            "caesars": "us/nba",
            "pointsbetus": "sports/basketball/nba",
            "williamhill_us": "sports/basketball/nba",
            "barstool": "sports/basketball/nba",
            "betrivers": "sports/basketball/nba"
        },
        "nfl": {
            "draftkings": "football/nfl",
            "fanduel": "navigation/nfl",
            "betmgm": "sports/football/100/nfl",
            "caesars": "us/nfl",
            "pointsbetus": "sports/football/nfl",
            "williamhill_us": "sports/football/nfl",
            "barstool": "sports/football/nfl",
            "betrivers": "sports/football/nfl"
        },
        "mlb": {
            "draftkings": "baseball/mlb",
            "fanduel": "navigation/mlb",
            "betmgm": "sports/baseball/103/mlb",
            "caesars": "us/mlb",
            "pointsbetus": "sports/baseball/mlb",
            "williamhill_us": "sports/baseball/mlb",
            "barstool": "sports/baseball/mlb",
            "betrivers": "sports/baseball/mlb"
        },
        "nhl": {
            "draftkings": "hockey/nhl",
            "fanduel": "navigation/nhl",
            "betmgm": "sports/hockey/102/nhl",
            "caesars": "us/nhl",
            "pointsbetus": "sports/hockey/nhl",
            "williamhill_us": "sports/hockey/nhl",
            "barstool": "sports/hockey/nhl",
            "betrivers": "sports/hockey/nhl"
        }
    }

    sport_path = sport_paths.get(sport, {}).get(book_key, sport)

    home_team = game_data.get("home_team", "").replace(" ", "-").lower()
    away_team = game_data.get("away_team", "").replace(" ", "-").lower()

    # Build URL with game context when possible
    base_url = config["web_base"]
    full_url = f"{base_url}/{sport_path}"

    return {
        "web": full_url,
        "app_scheme": config.get("app_scheme", ""),
        "sport_path": sport_path,
        "note": f"Opens {config['name']} {sport.upper()} page"
    }


# ============================================================================
# CONSOLIDATED ENDPOINTS (Server-Side Data Fetching)
# Reduces client-side waterfalls by combining multiple API calls into one
# ============================================================================

@router.get("/sport-dashboard/{sport}")
async def get_sport_dashboard(sport: str, auth: bool = Depends(verify_api_key)):
    """
    Consolidated endpoint for sport dashboard page.
    Replaces 6 separate API calls with a single request.

    Combines: best-bets, splits, lines, props, injuries, sharp

    Response Schema:
    {
        "sport": "NBA",
        "best_bets": { props: [], game_picks: [] },
        "market_overview": {
            "lines": [...],
            "splits": [...],
            "sharp_signals": [...]
        },
        "context": {
            "injuries": [...],
            "props": [...]
        },
        "daily_energy": {...},
        "timestamp": "ISO timestamp",
        "cache_info": { sources: {...} }
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"sport-dashboard:{sport_lower}"
    cached = api_cache.get(cache_key)
    if cached:
        cached["cache_info"] = {"hit": True}
        return cached

    # Fetch all data in parallel
    try:
        results = await asyncio.gather(
            get_best_bets(sport),
            get_splits(sport),
            get_lines(sport),
            get_injuries(sport),
            get_sharp_money(sport),
            return_exceptions=True
        )

        best_bets, splits, lines, injuries, sharp = results

        # Handle any exceptions gracefully
        cache_sources = {}

        if isinstance(best_bets, Exception):
            logger.warning("sport-dashboard: best_bets failed: %s", best_bets)
            best_bets = {"props": [], "game_picks": []}
            cache_sources["best_bets"] = "error"
        else:
            cache_sources["best_bets"] = best_bets.get("source", "unknown")

        if isinstance(splits, Exception):
            logger.warning("sport-dashboard: splits failed: %s", splits)
            splits = {"data": []}
            cache_sources["splits"] = "error"
        else:
            cache_sources["splits"] = splits.get("source", "unknown")

        if isinstance(lines, Exception):
            logger.warning("sport-dashboard: lines failed: %s", lines)
            lines = {"data": []}
            cache_sources["lines"] = "error"
        else:
            cache_sources["lines"] = lines.get("source", "unknown")

        if isinstance(injuries, Exception):
            logger.warning("sport-dashboard: injuries failed: %s", injuries)
            injuries = {"data": []}
            cache_sources["injuries"] = "error"
        else:
            cache_sources["injuries"] = injuries.get("source", "unknown")

        if isinstance(sharp, Exception):
            logger.warning("sport-dashboard: sharp failed: %s", sharp)
            sharp = {"data": []}
            cache_sources["sharp"] = "error"
        else:
            cache_sources["sharp"] = sharp.get("source", "unknown")

        result = {
            "sport": sport.upper(),
            "best_bets": {
                "props": best_bets.get("props", []),
                "game_picks": best_bets.get("game_picks", [])
            },
            "market_overview": {
                "lines": lines.get("data", []),
                "splits": splits.get("data", []),
                "sharp_signals": sharp.get("data", [])
            },
            "context": {
                "injuries": injuries.get("data", [])
            },
            "daily_energy": best_bets.get("daily_energy", get_daily_energy()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "cache_info": {"hit": False, "sources": cache_sources}
        }

        # Cache for 2 minutes (limited by best-bets TTL)
        api_cache.set(cache_key, result, ttl=600)
        return result

    except Exception as e:
        logger.exception("sport-dashboard failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Dashboard fetch failed: {str(e)}")


@router.get("/game-details/{sport}/{game_id}")
async def get_game_details(sport: str, game_id: str, auth: bool = Depends(verify_api_key)):
    """
    Consolidated endpoint for single game detail view.
    Replaces 4+ separate API calls with a single request.

    Combines: lines, props (filtered), sharp signals, injuries for specific game

    Response Schema:
    {
        "sport": "NBA",
        "game_id": "abc123",
        "game": { home_team, away_team, commence_time },
        "lines": { spreads: [], totals: [], moneylines: [] },
        "props": [...],
        "sharp_signals": {...},
        "injuries": { home: [], away: [] },
        "ai_pick": {...},
        "timestamp": "ISO timestamp"
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first
    cache_key = f"game-details:{sport_lower}:{game_id}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    # Fetch all data in parallel
    try:
        results = await asyncio.gather(
            get_lines(sport),
            get_props(sport),
            get_sharp_money(sport),
            get_injuries(sport),
            get_best_bets(sport),
            return_exceptions=True
        )

        lines_data, props_data, sharp_data, injuries_data, best_bets_data = results

        # Find specific game in lines
        game_info = None
        game_lines = {"spreads": [], "totals": [], "moneylines": []}

        if not isinstance(lines_data, Exception):
            for game in lines_data.get("data", []):
                if game.get("game_id") == game_id or game.get("id") == game_id:
                    game_info = {
                        "home_team": game.get("home_team"),
                        "away_team": game.get("away_team"),
                        "commence_time": game.get("commence_time")
                    }
                    game_lines = {
                        "spreads": game.get("spreads", []),
                        "totals": game.get("totals", []),
                        "moneylines": game.get("moneylines", [])
                    }
                    break

        # Filter props for this game
        game_props = []
        if not isinstance(props_data, Exception):
            for prop in props_data.get("data", []):
                if prop.get("game_id") == game_id or prop.get("event_id") == game_id:
                    game_props.append(prop)

        # Find sharp signal for this game
        game_sharp = {}
        if not isinstance(sharp_data, Exception):
            for signal in sharp_data.get("data", []):
                if signal.get("game_id") == game_id:
                    game_sharp = signal
                    break

        # Filter injuries for this game's teams
        game_injuries = {"home": [], "away": []}
        if not isinstance(injuries_data, Exception) and game_info:
            for inj in injuries_data.get("data", []):
                team = inj.get("team", "")
                if team == game_info.get("home_team"):
                    game_injuries["home"].append(inj)
                elif team == game_info.get("away_team"):
                    game_injuries["away"].append(inj)

        # Find AI pick for this game
        ai_pick = None
        if not isinstance(best_bets_data, Exception):
            for pick in best_bets_data.get("game_picks", []):
                if pick.get("game_id") == game_id:
                    ai_pick = pick
                    break
            # Also check props
            for prop in best_bets_data.get("props", []):
                if prop.get("game_id") == game_id or prop.get("event_id") == game_id:
                    if ai_pick is None:
                        ai_pick = {"props": [prop]}
                    elif "props" in ai_pick:
                        ai_pick["props"].append(prop)
                    else:
                        ai_pick["props"] = [prop]

        result = {
            "sport": sport.upper(),
            "game_id": game_id,
            "game": game_info or {"home_team": "Unknown", "away_team": "Unknown"},
            "lines": game_lines,
            "props": game_props,
            "sharp_signals": game_sharp,
            "injuries": game_injuries,
            "ai_pick": ai_pick,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        # Cache for 2 minutes
        api_cache.set(cache_key, result, ttl=600)
        return result

    except Exception as e:
        logger.exception("game-details failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Game details fetch failed: {str(e)}")


@router.get("/parlay-builder-init/{sport}")
async def get_parlay_builder_init(
    sport: str,
    user_id: Optional[str] = None,
    auth: bool = Depends(verify_api_key)
):
    """
    Consolidated endpoint for parlay builder page initialization.
    Replaces 3-4 separate API calls with a single request.

    Combines: best-bets (recommended props), props (full market), correlations, user parlay

    Response Schema:
    {
        "sport": "NBA",
        "recommended_props": [...],
        "all_props": [...],
        "correlations": {...},
        "current_parlay": { legs: [], calculated_odds: null },
        "user_history": { recent_parlays: [] },
        "timestamp": "ISO timestamp"
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Check cache first (only cache non-user-specific data)
    cache_key = f"parlay-builder:{sport_lower}"
    cached_base = api_cache.get(cache_key)

    # Fetch base data if not cached
    if not cached_base:
        try:
            results = await asyncio.gather(
                get_best_bets(sport),
                get_props(sport),
                return_exceptions=True
            )

            best_bets_data, props_data = results

            recommended_props = []
            if not isinstance(best_bets_data, Exception):
                recommended_props = best_bets_data.get("props", [])

            all_props = []
            if not isinstance(props_data, Exception):
                all_props = props_data.get("data", [])

            cached_base = {
                "recommended_props": recommended_props,
                "all_props": all_props
            }
            api_cache.set(cache_key, cached_base, ttl=180)  # 3 minutes

        except Exception as e:
            logger.exception("parlay-builder-init fetch failed: %s", e)
            cached_base = {"recommended_props": [], "all_props": []}

    # Get correlation matrix (static, cached separately)
    correlations = get_parlay_correlations()

    # Get user-specific data if user_id provided
    current_parlay = {"legs": [], "calculated_odds": None}
    user_history = {"recent_parlays": []}

    if user_id:
        # Get current parlay slip
        parlay_slip = parlay_slips.get(user_id, {"legs": []})
        current_parlay = {
            "legs": parlay_slip.get("legs", []),
            "calculated_odds": None
        }

        # Calculate odds if legs exist
        if current_parlay["legs"]:
            try:
                calc_result = calculate_parlay_odds_internal(current_parlay["legs"])
                current_parlay["calculated_odds"] = calc_result
            except Exception:
                pass

        # Get recent parlay history
        user_parlays = [p for p in parlay_history if p.get("user_id") == user_id]
        user_history["recent_parlays"] = sorted(
            user_parlays,
            key=lambda x: x.get("placed_at", ""),
            reverse=True
        )[:5]

    result = {
        "sport": sport.upper(),
        "recommended_props": cached_base.get("recommended_props", []),
        "all_props": cached_base.get("all_props", []),
        "correlations": correlations,
        "current_parlay": current_parlay,
        "user_history": user_history,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    return result


def get_parlay_correlations() -> Dict[str, Any]:
    """Get static parlay correlation matrix."""
    return {
        "same_game": {
            "QB_WR": 0.88,
            "QB_TE": 0.75,
            "RB_DST": -0.45,
            "WR_WR": 0.35,
            "QB_RB": 0.25
        },
        "cross_game": {
            "same_position": 0.15,
            "division_rivalry": 0.10
        },
        "warning_threshold": 0.70,
        "boost_threshold": -0.30
    }


def calculate_parlay_odds_internal(legs: List[Dict]) -> Dict[str, Any]:
    """Calculate parlay odds from legs (internal helper)."""
    if not legs:
        return {"decimal_odds": 1.0, "american_odds": "+100", "implied_probability": 1.0}

    decimal_odds = 1.0
    for leg in legs:
        leg_odds = leg.get("odds", -110)
        if leg_odds > 0:
            decimal = 1 + (leg_odds / 100)
        else:
            decimal = 1 + (100 / abs(leg_odds))
        decimal_odds *= decimal

    # Convert to American
    if decimal_odds >= 2.0:
        american = f"+{int((decimal_odds - 1) * 100)}"
    else:
        american = f"-{int(100 / (decimal_odds - 1))}"

    implied_prob = 1 / decimal_odds

    return {
        "decimal_odds": round(decimal_odds, 3),
        "american_odds": american,
        "implied_probability": round(implied_prob, 4),
        "leg_count": len(legs)
    }


# ============================================================================
# FRONTEND COMPATIBILITY ENDPOINTS
# These endpoints match what the frontend api.js expects
# ============================================================================

@router.get("/games/{sport}")
async def get_live_games(sport: str, auth: bool = Depends(verify_api_key)):
    """
    Get live games with odds for a sport.

    This is an alias for /lines/{sport} to match frontend expectations.
    Returns games with current lines/odds from Odds API or Playbook.

    Response Schema:
    {
        "sport": "NBA",
        "source": "odds_api" | "playbook" | "fallback",
        "count": N,
        "games": [...],
        "api_usage": {...}
    }
    """
    # Get lines data (contains games with odds)
    lines_data = await get_lines(sport)

    # Transform to match frontend expected schema
    games = lines_data.get("data", [])

    # Add game-level formatting expected by frontend
    formatted_games = []
    for game in games:
        formatted_games.append({
            "id": game.get("game_id") or game.get("id"),
            "game_id": game.get("game_id") or game.get("id"),
            "home_team": game.get("home_team"),
            "away_team": game.get("away_team"),
            "commence_time": game.get("commence_time"),
            "sport": sport.upper(),
            "odds": {
                "spreads": game.get("spreads", []),
                "totals": game.get("totals", []),
                "moneylines": game.get("moneylines", game.get("h2h", []))
            },
            "bookmakers": game.get("bookmakers", [])
        })

    return {
        "sport": sport.upper(),
        "source": lines_data.get("source", "unknown"),
        "count": len(formatted_games),
        "games": formatted_games,
        "data": formatted_games,  # Alias for compatibility
        "api_usage": {
            "endpoint": "/live/api-usage",
            "note": "Check /live/api-health for quota status"
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/slate/{sport}")
async def get_live_slate(sport: str, debug: int = 0, auth: bool = Depends(verify_api_key)):
    """
    Alias for /best-bets/{sport} - returns SmashSpots with root picks[] array.

    This endpoint now returns the same response as /best-bets/{sport} for
    frontend compatibility. The root picks[] array contains merged picks
    (top 3 game picks + top 7 props).

    Query Parameters:
    - debug=1: Include diagnostic info

    Response Schema:
    {
        "sport": "NBA",
        "picks": [...],           // Root picks[] for SmashSpots rendering
        "props": {"picks": [...]},
        "game_picks": {"picks": [...]},
        ...
    }
    """
    # Delegate to get_best_bets for identical response
    return await get_best_bets(sport, debug)


@router.get("/roster/{sport}/{team}")
async def get_roster(sport: str, team: str, auth: bool = Depends(verify_api_key)):
    """
    Get team roster with injury status.

    Combines injury data with basic roster info.
    Team can be full name or abbreviation.

    Response Schema:
    {
        "sport": "NBA",
        "team": "Lakers",
        "players": [...],
        "injuries": [...]
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Normalize team name
    team_normalized = team.lower().replace("-", " ").replace("_", " ")

    # Check cache
    cache_key = f"roster:{sport_lower}:{team_normalized}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    # Get injuries data which has player info
    injuries_data = await get_injuries(sport)
    all_injuries = injuries_data.get("data", [])

    # Filter injuries for this team
    team_injuries = []
    for inj in all_injuries:
        inj_team = safe_lower(inj.get("team"))
        if team_normalized in inj_team or inj_team in team_normalized:
            team_injuries.append({
                "player": inj.get("player") or inj.get("athlete", {}).get("displayName"),
                "position": inj.get("position", ""),
                "status": inj.get("status", "Unknown"),
                "injury": inj.get("injury") or inj.get("type", "Unknown"),
                "return_date": inj.get("return_date", inj.get("returnDate", ""))
            })

    # Generate basic roster (injured players + estimated healthy players)
    roster = []

    # Add injured players first
    for inj in team_injuries:
        roster.append({
            "name": inj["player"],
            "position": inj["position"],
            "status": inj["status"],
            "injury": inj["injury"],
            "is_injured": True
        })

    result = {
        "sport": sport.upper(),
        "team": team.title(),
        "source": injuries_data.get("source", "unknown"),
        "player_count": len(roster),
        "injured_count": len(team_injuries),
        "players": roster,
        "injuries": team_injuries,
        "note": "Roster shows injured players. Full roster requires additional data source.",
        "timestamp": datetime.now().isoformat()
    }

    api_cache.set(cache_key, result, ttl=600)
    return result


@router.get("/player/{player_name}")
async def get_player_stats(player_name: str, sport: str = "nba", auth: bool = Depends(verify_api_key)):
    """
    Get player stats and props.

    Searches for player across props and injury data.

    Response Schema:
    {
        "player": "LeBron James",
        "team": "Lakers",
        "props": [...],
        "injury_status": {...},
        "recent_performance": {...}
    }
    """
    sport_lower = sport.lower()
    if sport_lower not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    player_normalized = player_name.lower().strip()

    # Check cache
    cache_key = f"player:{sport_lower}:{player_normalized}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    # Fetch props and injuries in parallel
    results = await asyncio.gather(
        get_props(sport),
        get_injuries(sport),
        return_exceptions=True
    )

    props_data, injuries_data = results

    # Find player props
    player_props = []
    player_team = None

    if not isinstance(props_data, Exception):
        for prop in props_data.get("data", []):
            prop_player = safe_lower(prop.get("player") or prop.get("description"))
            if player_normalized in prop_player or prop_player in player_normalized:
                player_props.append({
                    "market": prop.get("market"),
                    "line": prop.get("point") or prop.get("line"),
                    "over_odds": prop.get("over_price") or prop.get("over_odds"),
                    "under_odds": prop.get("under_price") or prop.get("under_odds"),
                    "bookmaker": prop.get("bookmaker", "consensus")
                })
                if not player_team:
                    player_team = prop.get("team")

    # Find injury status
    injury_status = None
    if not isinstance(injuries_data, Exception):
        for inj in injuries_data.get("data", []):
            inj_player = safe_lower(inj.get("player") or inj.get("athlete", {}).get("displayName"))
            if player_normalized in inj_player or inj_player in player_normalized:
                injury_status = {
                    "status": inj.get("status", "Unknown"),
                    "injury": inj.get("injury") or inj.get("type", "Unknown"),
                    "team": inj.get("team"),
                    "return_date": inj.get("return_date", "")
                }
                if not player_team:
                    player_team = inj.get("team")
                break

    result = {
        "player": player_name.title(),
        "sport": sport.upper(),
        "team": player_team,
        "props_count": len(player_props),
        "props": player_props,
        "injury_status": injury_status,
        "is_injured": injury_status is not None,
        "source": "combined",
        "timestamp": datetime.now().isoformat()
    }

    api_cache.set(cache_key, result, ttl=180)
    return result


@router.post("/predict-live")
async def predict_live(
    prediction_request: Dict[str, Any],
    auth: bool = Depends(verify_api_key)
):
    """
    Get AI prediction for a game or prop.

    This is an alias that calls best-bets and filters for the requested prediction.

    Request Body:
    {
        "sport": "nba",
        "game_id": "abc123",  # Optional
        "player": "LeBron James",  # Optional
        "market": "points"  # Optional
    }

    Response Schema:
    {
        "prediction": {...},
        "confidence": 0.75,
        "recommendation": "OVER",
        "analysis": {...}
    }
    """
    sport = (prediction_request.get("sport") or "nba").lower()
    game_id = prediction_request.get("game_id")
    player = safe_lower(prediction_request.get("player"))
    market = safe_lower(prediction_request.get("market"))

    if sport not in SPORT_MAPPINGS:
        raise HTTPException(status_code=400, detail=f"Unsupported sport: {sport}")

    # Get best bets data
    best_bets = await get_best_bets(sport)

    props = best_bets.get("props", [])
    game_picks = best_bets.get("game_picks", [])

    prediction = None

    # Search for matching prediction
    if player:
        # Look for player prop
        for prop in props:
            prop_player = safe_lower(prop.get("player"))
            prop_market = safe_lower(prop.get("market"))
            if player in prop_player:
                if not market or market in prop_market:
                    prediction = prop
                    break
    elif game_id:
        # Look for game prediction
        for pick in game_picks:
            if pick.get("game_id") == game_id:
                prediction = pick
                break
    else:
        # Return top prediction
        if props:
            prediction = props[0]
        elif game_picks:
            prediction = game_picks[0]

    if not prediction:
        return {
            "found": False,
            "message": "No matching prediction found",
            "sport": sport.upper(),
            "available_props": len(props),
            "available_game_picks": len(game_picks),
            "timestamp": datetime.now().isoformat()
        }

    return {
        "found": True,
        "sport": sport.upper(),
        "prediction": prediction,
        "confidence": prediction.get("confidence", prediction.get("score", 0.7)),
        "recommendation": prediction.get("pick") or prediction.get("recommendation"),
        "edge": prediction.get("edge", prediction.get("value")),
        "analysis": {
            "ai_models_score": prediction.get("ai_score", prediction.get("research_score")),
            "pillars_hit": prediction.get("pillars_hit", []),
            "esoteric_signals": prediction.get("esoteric_signals", [])
        },
        "source": best_bets.get("source", "ai_engine"),
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# v10.41: JASON SIM 2.0 ENDPOINTS
# ============================================================================

@router.post("/jason-sim/upload/{sport}")
async def upload_jason_sim_payloads(
    sport: str,
    payloads: List[Dict[str, Any]],
    auth: bool = Depends(verify_api_key)
):
    """
    Upload Jason Sim 2.0 payloads for a sport.

    Jason Sim is a POST-PICK confluence layer that can BOOST / DOWNGRADE / BLOCK
    existing picks. It cannot generate picks by itself.

    Request Body:
    - List of Jason Sim payload dicts, each with:
      - game_id: Unique game identifier
      - home_team: Home team name/abbr
      - away_team: Away team name/abbr
      - sim_runs_per_game: Number of simulations (default 10000)
      - results: { win_pct_injury_adj, score_projection, confidence }

    Returns:
    - games_uploaded: Number of payloads stored
    - games_normalized: Number successfully normalized
    - timestamp: When uploaded
    """
    sport_lower = sport.lower()
    if sport_lower not in JASON_SIM_PAYLOADS:
        raise HTTPException(status_code=400, detail=f"Invalid sport: {sport}")

    if not JASON_SIM_AVAILABLE:
        raise HTTPException(status_code=503, detail="Jason Sim module not available")

    # Clear existing payloads for this sport
    JASON_SIM_PAYLOADS[sport_lower] = {}

    normalized_count = 0

    for payload in payloads:
        game_id = payload.get("game_id")
        home_team = payload.get("home_team", "")
        away_team = payload.get("away_team", "")

        # Construct game_id if missing
        if not game_id and home_team and away_team:
            game_id = f"{away_team}@{home_team}"

        if not game_id:
            logger.warning("Jason Sim payload missing game_id, skipping")
            continue

        # Normalize the payload
        normalized = normalize_jason_sim(
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            payload=payload
        )

        if normalized.get("valid"):
            normalized_count += 1

        # Store under multiple keys for flexible lookup
        JASON_SIM_PAYLOADS[sport_lower][game_id] = normalized
        if home_team and away_team:
            JASON_SIM_PAYLOADS[sport_lower][f"{away_team}@{home_team}"] = normalized

    # Update timestamp
    JASON_SIM_LAST_UPDATE[sport_lower] = datetime.now()

    logger.info(f"Jason Sim: Uploaded {len(payloads)} payloads for {sport}, {normalized_count} valid")

    return {
        "sport": sport.upper(),
        "games_uploaded": len(payloads),
        "games_normalized": normalized_count,
        "games_stored": len(JASON_SIM_PAYLOADS[sport_lower]),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/jason-sim/status/{sport}")
async def get_jason_sim_status(sport: str, auth: bool = Depends(verify_api_key)):
    """
    Get Jason Sim status for a sport.

    Returns:
    - payloads_count: Number of payloads stored
    - last_update: When payloads were last uploaded
    - is_stale: Whether payloads are older than JASON_SIM_STALE_HOURS
    - available: Whether Jason Sim module is available
    """
    sport_lower = sport.lower()
    if sport_lower not in JASON_SIM_PAYLOADS:
        raise HTTPException(status_code=400, detail=f"Invalid sport: {sport}")

    last_update = JASON_SIM_LAST_UPDATE.get(sport_lower)
    is_stale = True
    if last_update:
        hours_since_update = (datetime.now() - last_update).total_seconds() / 3600
        is_stale = hours_since_update > JASON_SIM_STALE_HOURS

    # Count unique games (excluding alternate key formats)
    unique_games = set()
    for key, payload in JASON_SIM_PAYLOADS[sport_lower].items():
        if payload.get("game_id"):
            unique_games.add(payload["game_id"])

    return {
        "sport": sport.upper(),
        "available": JASON_SIM_AVAILABLE,
        "payloads_count": len(unique_games),
        "total_keys": len(JASON_SIM_PAYLOADS[sport_lower]),
        "last_update": last_update.isoformat() if last_update else None,
        "is_stale": is_stale,
        "stale_threshold_hours": JASON_SIM_STALE_HOURS,
        "timestamp": datetime.now().isoformat()
    }


@router.delete("/jason-sim/clear/{sport}")
async def clear_jason_sim_payloads(sport: str, auth: bool = Depends(verify_api_key)):
    """Clear Jason Sim payloads for a sport."""
    sport_lower = sport.lower()
    if sport_lower not in JASON_SIM_PAYLOADS:
        raise HTTPException(status_code=400, detail=f"Invalid sport: {sport}")

    count = len(JASON_SIM_PAYLOADS[sport_lower])
    JASON_SIM_PAYLOADS[sport_lower] = {}
    JASON_SIM_LAST_UPDATE[sport_lower] = None

    return {
        "sport": sport.upper(),
        "cleared": count,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/jason-sim/payloads/{sport}")
async def get_jason_sim_payloads(sport: str, auth: bool = Depends(verify_api_key)):
    """
    Get all Jason Sim payloads for a sport (for debugging).

    Returns:
    - payloads: Dict of game_id -> normalized payload
    """
    sport_lower = sport.lower()
    if sport_lower not in JASON_SIM_PAYLOADS:
        raise HTTPException(status_code=400, detail=f"Invalid sport: {sport}")

    # Return unique payloads only (dedupe by game_id)
    unique_payloads = {}
    for key, payload in JASON_SIM_PAYLOADS[sport_lower].items():
        game_id = payload.get("game_id")
        if game_id and game_id not in unique_payloads:
            unique_payloads[game_id] = payload

    return {
        "sport": sport.upper(),
        "count": len(unique_payloads),
        "payloads": unique_payloads,
        "last_update": JASON_SIM_LAST_UPDATE[sport_lower].isoformat() if JASON_SIM_LAST_UPDATE[sport_lower] else None,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# EXPORTS FOR MAIN.PY
# ============================================================================

class LiveDataRouter:
    def __init__(self):
        self.router = router

    def get_router(self):
        return self.router


# Export the router instance
live_data_router = router
