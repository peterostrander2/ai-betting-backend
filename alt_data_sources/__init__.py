"""
Alternative Data Sources Module - v11.10
========================================
Integrates non-traditional data sources for betting edge signals:
- BallDontLie: NBA live game data, player stats, grading (GOAT TIER)
- Twitter: Breaking injury news from beat reporters (optional)
- ESPN: Starting lineups and referee tendencies (FREE)
- Weather: Weather conditions for outdoor games (stub - OpenWeather when implemented)
- Refs: Referee tendencies and historical impact (stub)
- Stadium: Venue altitude, surface, roof status (stub with known venues)
- Travel: Team travel distance and fatigue analysis (stub with estimated distances)
"""

# BallDontLie - GOAT tier (always try to import)
try:
    from .balldontlie import (
        is_balldontlie_configured,
        get_balldontlie_status,
        get_live_games as get_bdl_live_games,
        get_nba_live_context,
        search_player,
        get_player_game_stats,
        get_player_season_averages,
        get_box_score,
        grade_nba_prop,
        BDL_API_KEY,
    )
    BALLDONTLIE_AVAILABLE = True
except ImportError as e:
    BALLDONTLIE_AVAILABLE = False

    def is_balldontlie_configured():
        return False

    def get_balldontlie_status():
        return {"configured": False, "reason": "Module not available"}

# Optional modules - import if available, otherwise provide stubs
try:
    from .twitter_api import (
        get_twitter_injury_alerts,
        get_twitter_sentiment,
        is_twitter_configured
    )
    TWITTER_AVAILABLE = True
except ImportError:
    TWITTER_AVAILABLE = False

    def get_twitter_injury_alerts(*args, **kwargs):
        return []

    def get_twitter_sentiment(*args, **kwargs):
        return {"sentiment": "neutral", "configured": False}

    def is_twitter_configured():
        return False

try:
    from .espn_lineups import (
        # Core functions
        get_lineups_for_game,
        get_referee_impact,
        get_todays_games,
        get_game_details,
        get_espn_status,
        get_espn_scoreboard,
        get_espn_event_id,
        get_officials_for_event,
        get_officials_for_game,
        get_officials_sync,
        # Expanded data extraction
        get_espn_odds,
        get_espn_injuries,
        get_espn_player_stats,
        get_espn_venue_info,
        get_game_summary_enriched,
        get_all_games_enriched,
    )
    ESPN_AVAILABLE = True
except ImportError:
    ESPN_AVAILABLE = False

    def get_lineups_for_game(*args, **kwargs):
        return []

    def get_referee_impact(*args, **kwargs):
        return {}

    def get_todays_games(*args, **kwargs):
        return []

    def get_game_details(*args, **kwargs):
        return {}

    def get_espn_status():
        return {"configured": False}

    def get_espn_scoreboard(*args, **kwargs):
        return {"events": []}

    def get_espn_event_id(*args, **kwargs):
        return None

    def get_officials_for_event(*args, **kwargs):
        return {"available": False}

    def get_officials_for_game(*args, **kwargs):
        return {"available": False}

    def get_officials_sync(*args, **kwargs):
        return {"available": False}

    def get_espn_odds(*args, **kwargs):
        return {"available": False}

    def get_espn_injuries(*args, **kwargs):
        return {"available": False, "injuries": []}

    def get_espn_player_stats(*args, **kwargs):
        return {"available": False}

    def get_espn_venue_info(*args, **kwargs):
        return {"available": False}

    def get_game_summary_enriched(*args, **kwargs):
        return {"available": False}

    def get_all_games_enriched(*args, **kwargs):
        return []

# Weather, Refs, Stadium, Travel - Stub modules (always available)
try:
    from .weather import (
        get_weather_for_game,
        is_weather_relevant,
        calculate_weather_impact,
        WEATHER_ENABLED
    )
    from .refs import (
        get_referee_for_game,
        calculate_referee_impact,
        REFS_ENABLED
    )
    from .stadium import (
        get_stadium_info,
        calculate_altitude_impact,
        lookup_altitude,
        STADIUM_ENABLED
    )
    from .travel import (
        get_travel_impact,
        calculate_fatigue_impact,
        calculate_distance,
        TRAVEL_ENABLED
    )
    STUB_MODULES_AVAILABLE = True
except ImportError as e:
    STUB_MODULES_AVAILABLE = False

    def get_weather_for_game(*args, **kwargs):
        return {"available": False, "reason": "MODULE_IMPORT_FAILED"}

    def is_weather_relevant(*args, **kwargs):
        return False

    def calculate_weather_impact(*args, **kwargs):
        return {"overall_impact": "NONE", "reasons": ["Module not available"]}

    def get_referee_for_game(*args, **kwargs):
        return {"available": False, "reason": "MODULE_IMPORT_FAILED"}

    def calculate_referee_impact(*args, **kwargs):
        return {"overall_impact": "NONE", "reasons": ["Module not available"]}

    def get_stadium_info(*args, **kwargs):
        return {"available": False, "reason": "MODULE_IMPORT_FAILED"}

    def calculate_altitude_impact(*args, **kwargs):
        return {"overall_impact": "NONE", "reasons": ["Module not available"]}

    def lookup_altitude(*args, **kwargs):
        return 0

    def get_travel_impact(*args, **kwargs):
        return {"available": False, "reason": "MODULE_IMPORT_FAILED"}

    def calculate_fatigue_impact(*args, **kwargs):
        return {"overall_impact": "NONE", "reasons": ["Module not available"]}

    def calculate_distance(*args, **kwargs):
        return 0

    WEATHER_ENABLED = False
    REFS_ENABLED = False
    STADIUM_ENABLED = False
    TRAVEL_ENABLED = False

# NOAA Space Weather (GLITCH Protocol - Kp-Index)
try:
    from .noaa import (
        fetch_kp_index_live,
        get_kp_betting_signal,
        get_space_weather_summary,
        NOAA_ENABLED,
    )
    NOAA_AVAILABLE = True
except ImportError:
    NOAA_AVAILABLE = False
    NOAA_ENABLED = False

    def fetch_kp_index_live(*args, **kwargs):
        return {"kp_value": 3.0, "storm_level": "QUIET", "source": "fallback"}

    def get_kp_betting_signal(*args, **kwargs):
        return {"score": 0.6, "reason": "KP_FALLBACK", "triggered": False, "kp_value": 3.0}

    def get_space_weather_summary(*args, **kwargs):
        return {"betting_outlook": "NEUTRAL", "outlook_reason": "NOAA unavailable"}

# SerpAPI (GLITCH Protocol - Noosphere Velocity / Search Trends)
try:
    from .serpapi import (
        get_search_trend,
        get_team_buzz,
        get_player_buzz,
        get_noosphere_data,
        SERPAPI_ENABLED,
    )
    SERPAPI_AVAILABLE = True
except ImportError:
    SERPAPI_AVAILABLE = False
    SERPAPI_ENABLED = False

    def get_search_trend(*args, **kwargs):
        return {"trend_score": 0.5, "source": "fallback"}

    def get_team_buzz(*args, **kwargs):
        return {"velocity": 0.0, "direction": "NEUTRAL", "source": "fallback"}

    def get_player_buzz(*args, **kwargs):
        return {"buzz_score": 0.5, "interest_level": "MODERATE", "source": "fallback"}

    def get_noosphere_data(*args, **kwargs):
        return {"velocity": 0.0, "direction": "NEUTRAL", "source": "fallback"}

# SERP Intelligence (v17.4 - Betting Signals from Search Trends)
try:
    from .serp_intelligence import (
        get_serp_betting_intelligence,
        get_serp_prop_intelligence,
        detect_silent_spike,
        detect_sharp_chatter,
        detect_narrative,
        detect_situational,
        detect_noosphere,
        SPORT_QUERIES,
    )
    SERP_INTEL_AVAILABLE = True
except ImportError:
    SERP_INTEL_AVAILABLE = False

    def get_serp_betting_intelligence(*args, **kwargs):
        return {"available": False, "boosts": {"ai": 0, "research": 0, "esoteric": 0, "jarvis": 0, "context": 0}}

    def get_serp_prop_intelligence(*args, **kwargs):
        return {"available": False, "boosts": {"ai": 0, "research": 0, "esoteric": 0, "jarvis": 0, "context": 0}}

    def detect_silent_spike(*args, **kwargs):
        return {"triggered": False, "boost": 0.0}

    def detect_sharp_chatter(*args, **kwargs):
        return {"triggered": False, "boost": 0.0}

    def detect_narrative(*args, **kwargs):
        return {"triggered": False, "boost": 0.0}

    def detect_situational(*args, **kwargs):
        return {"triggered": False, "boost": 0.0}

    def detect_noosphere(*args, **kwargs):
        return {"triggered": False, "boost": 0.0}

    SPORT_QUERIES = {}

# Integration helpers
def get_alt_data_status():
    """Get status of all alternative data sources."""
    return {
        "balldontlie": {
            "available": BALLDONTLIE_AVAILABLE,
            "configured": is_balldontlie_configured() if BALLDONTLIE_AVAILABLE else False
        },
        "twitter": {
            "available": TWITTER_AVAILABLE,
            "configured": is_twitter_configured() if TWITTER_AVAILABLE else False
        },
        "espn": {
            "available": ESPN_AVAILABLE,
            "configured": True if ESPN_AVAILABLE else False
        },
        "noaa": {
            "available": NOAA_AVAILABLE,
            "enabled": NOAA_ENABLED,
            "purpose": "GLITCH Protocol - Kp-Index geomagnetic data"
        },
        "serpapi": {
            "available": SERPAPI_AVAILABLE,
            "enabled": SERPAPI_ENABLED,
            "purpose": "GLITCH Protocol - Noosphere Velocity (search trends)"
        },
        "serp_intelligence": {
            "available": SERP_INTEL_AVAILABLE,
            "purpose": "v17.4 - Betting signals from search trends (5 engines)"
        }
    }


__all__ = [
    # BallDontLie (NBA Live Context + GOAT Features)
    "is_balldontlie_configured",
    "get_balldontlie_status",
    "get_bdl_live_games",
    "get_nba_live_context",
    "BALLDONTLIE_AVAILABLE",
    # Twitter (Optional)
    "get_twitter_injury_alerts",
    "get_twitter_sentiment",
    "is_twitter_configured",
    "TWITTER_AVAILABLE",
    # ESPN - Lineups, Referees, Odds, Injuries, Venue
    "get_lineups_for_game",
    "get_referee_impact",
    "get_todays_games",
    "get_game_details",
    "get_espn_status",
    "get_espn_scoreboard",
    "get_espn_event_id",
    "get_officials_for_event",
    "get_officials_for_game",
    "get_officials_sync",
    "get_espn_odds",
    "get_espn_injuries",
    "get_espn_player_stats",
    "get_espn_venue_info",
    "get_game_summary_enriched",
    "get_all_games_enriched",
    "ESPN_AVAILABLE",
    # NOAA Space Weather (GLITCH Protocol)
    "fetch_kp_index_live",
    "get_kp_betting_signal",
    "get_space_weather_summary",
    "NOAA_AVAILABLE",
    "NOAA_ENABLED",
    # SerpAPI (GLITCH Protocol - Noosphere)
    "get_search_trend",
    "get_team_buzz",
    "get_player_buzz",
    "get_noosphere_data",
    "SERPAPI_AVAILABLE",
    "SERPAPI_ENABLED",
    # SERP Intelligence (v17.4 - Betting Signals)
    "get_serp_betting_intelligence",
    "get_serp_prop_intelligence",
    "detect_silent_spike",
    "detect_sharp_chatter",
    "detect_narrative",
    "detect_situational",
    "detect_noosphere",
    "SERP_INTEL_AVAILABLE",
    # Integration
    "get_alt_data_status",
]
