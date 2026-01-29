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
        get_lineups_for_game,
        get_referee_impact,
        get_todays_games,
        get_game_details,
        get_espn_status
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
    # ESPN Lineups & Referees
    "get_lineups_for_game",
    "get_referee_impact",
    "get_todays_games",
    "get_game_details",
    "get_espn_status",
    "ESPN_AVAILABLE",
    # Integration
    "get_alt_data_status",
]
