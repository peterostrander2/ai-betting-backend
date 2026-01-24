"""
Alternative Data Sources Module - v10.68
========================================
Integrates non-traditional data sources for betting edge signals:
- Twitter: Breaking injury news from beat reporters
- Finnhub: Sportsbook stock sentiment (DKNG, FLTR)
- SerpAPI: News aggregation and trending topics
- FRED: Economic indicators and consumer sentiment
- ESPN: Starting lineups and referee tendencies (FREE)
"""

from .twitter_api import (
    get_twitter_injury_alerts,
    get_twitter_sentiment,
    is_twitter_configured
)
from .finnhub_api import (
    get_sportsbook_sentiment,
    get_market_sentiment,
    is_finnhub_configured
)
from .serpapi_news import (
    get_trending_news,
    get_injury_news,
    is_serpapi_configured
)
from .fred_api import (
    get_economic_sentiment,
    get_consumer_confidence,
    is_fred_configured
)
from .espn_lineups import (
    get_lineups_for_game,
    get_referee_impact,
    get_todays_games,
    get_game_details,
    get_espn_status
)
from .integration import (
    get_alternative_data_context,
    get_alt_data_status
)

__all__ = [
    # Twitter
    "get_twitter_injury_alerts",
    "get_twitter_sentiment",
    "is_twitter_configured",
    # Finnhub
    "get_sportsbook_sentiment",
    "get_market_sentiment",
    "is_finnhub_configured",
    # SerpAPI
    "get_trending_news",
    "get_injury_news",
    "is_serpapi_configured",
    # FRED
    "get_economic_sentiment",
    "get_consumer_confidence",
    "is_fred_configured",
    # ESPN Lineups & Referees
    "get_lineups_for_game",
    "get_referee_impact",
    "get_todays_games",
    "get_game_details",
    "get_espn_status",
    # Integration
    "get_alternative_data_context",
    "get_alt_data_status",
]
