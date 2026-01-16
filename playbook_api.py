# playbook_api.py - Playbook API v1 Client Utility
# Clean fetch wrapper with automatic api_key injection and query validation

import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PLAYBOOK_BASE_URL = os.getenv("PLAYBOOK_API_BASE", "https://api.playbook-api.com/v1")
PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "")

# Valid leagues (uppercase)
VALID_LEAGUES = {"NBA", "NFL", "CFB", "MLB", "NHL"}


@dataclass
class PlaybookEndpoint:
    """Definition for a Playbook API endpoint."""
    method: str
    path: str
    required_query: List[str]
    optional_query: List[str] = None

    def __post_init__(self):
        if self.optional_query is None:
            self.optional_query = []


# All Playbook API v1 endpoints
PLAYBOOK_ENDPOINTS: Dict[str, PlaybookEndpoint] = {
    "health": PlaybookEndpoint(
        method="GET",
        path="/health",
        required_query=[]
    ),
    "me": PlaybookEndpoint(
        method="GET",
        path="/me",
        required_query=["api_key"]
    ),
    "teams": PlaybookEndpoint(
        method="GET",
        path="/teams",
        required_query=["league", "api_key"],
        optional_query=["injuries"]  # injuries=true
    ),
    "injuries": PlaybookEndpoint(
        method="GET",
        path="/injuries",
        required_query=["league", "api_key"],
        optional_query=["reportDate"]  # YYYY-MM-DD
    ),
    "splits": PlaybookEndpoint(
        method="GET",
        path="/splits",
        required_query=["league", "api_key"]
    ),
    "splits_history": PlaybookEndpoint(
        method="GET",
        path="/splits-history",
        required_query=["league", "date", "api_key"]  # date = YYYY-MM-DD
    ),
    "odds_games": PlaybookEndpoint(
        method="GET",
        path="/odds-games",
        required_query=["league", "api_key"]
    ),
    "lines": PlaybookEndpoint(
        method="GET",
        path="/lines",
        required_query=["league", "api_key"]
    ),
    "games": PlaybookEndpoint(
        method="GET",
        path="/games",
        required_query=["league", "date", "api_key"]  # date = YYYY-MM-DD
    ),
}


class PlaybookAPIError(Exception):
    """Custom exception for Playbook API errors."""
    pass


def validate_league(league: str) -> str:
    """Validate and normalize league to uppercase."""
    league_upper = league.upper()
    if league_upper not in VALID_LEAGUES:
        raise PlaybookAPIError(f"Invalid league: {league}. Must be one of: {VALID_LEAGUES}")
    return league_upper


def build_playbook_url(
    endpoint_name: str,
    params: Dict[str, Any] = None,
    api_key: str = None
) -> tuple[str, Dict[str, Any]]:
    """
    Build a Playbook API URL with validated params.

    Args:
        endpoint_name: Name of the endpoint (e.g., "splits", "injuries")
        params: Query parameters (league, date, etc.)
        api_key: Optional API key override (defaults to env var)

    Returns:
        Tuple of (full_url, query_params)

    Raises:
        PlaybookAPIError: If endpoint unknown or required params missing

    Example:
        url, params = build_playbook_url("splits", {"league": "NBA"})
        # Returns: ("https://api.playbook-api.com/v1/splits", {"league": "NBA", "api_key": "..."})
    """
    if endpoint_name not in PLAYBOOK_ENDPOINTS:
        raise PlaybookAPIError(f"Unknown endpoint: {endpoint_name}. Available: {list(PLAYBOOK_ENDPOINTS.keys())}")

    endpoint = PLAYBOOK_ENDPOINTS[endpoint_name]
    params = params or {}

    # Use provided api_key or fall back to env var
    key = api_key or PLAYBOOK_API_KEY
    if not key and "api_key" in endpoint.required_query:
        raise PlaybookAPIError("PLAYBOOK_API_KEY not set and no api_key provided")

    # Build query params
    query_params = {}

    # Validate league if required
    if "league" in endpoint.required_query:
        if "league" not in params:
            raise PlaybookAPIError(f"Missing required param 'league' for endpoint '{endpoint_name}'")
        query_params["league"] = validate_league(params["league"])

    # Add date if required
    if "date" in endpoint.required_query:
        if "date" not in params:
            raise PlaybookAPIError(f"Missing required param 'date' for endpoint '{endpoint_name}'")
        query_params["date"] = params["date"]

    # Add api_key
    if "api_key" in endpoint.required_query:
        query_params["api_key"] = key

    # Add optional params if provided
    for opt in endpoint.optional_query:
        if opt in params:
            query_params[opt] = params[opt]

    url = f"{PLAYBOOK_BASE_URL}{endpoint.path}"
    return url, query_params


def get_endpoint_info(endpoint_name: str) -> Dict[str, Any]:
    """Get info about a specific endpoint."""
    if endpoint_name not in PLAYBOOK_ENDPOINTS:
        raise PlaybookAPIError(f"Unknown endpoint: {endpoint_name}")

    ep = PLAYBOOK_ENDPOINTS[endpoint_name]
    return {
        "name": endpoint_name,
        "method": ep.method,
        "path": ep.path,
        "url": f"{PLAYBOOK_BASE_URL}{ep.path}",
        "required_params": ep.required_query,
        "optional_params": ep.optional_query
    }


def list_endpoints() -> Dict[str, Dict[str, Any]]:
    """List all available Playbook API endpoints."""
    return {name: get_endpoint_info(name) for name in PLAYBOOK_ENDPOINTS}


# ============================================================================
# ASYNC FETCH WRAPPER (for use with httpx in live_data_router.py)
# ============================================================================

async def playbook_fetch(
    endpoint_name: str,
    params: Dict[str, Any] = None,
    client = None,
    api_key: str = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch data from Playbook API with automatic URL building and error handling.

    Args:
        endpoint_name: Name of the endpoint (e.g., "splits", "injuries")
        params: Query parameters (league, date, etc.)
        client: httpx.AsyncClient instance (required)
        api_key: Optional API key override

    Returns:
        JSON response data or None on error

    Example:
        async with httpx.AsyncClient() as client:
            data = await playbook_fetch("splits", {"league": "NBA"}, client=client)
    """
    if client is None:
        raise PlaybookAPIError("httpx client is required for playbook_fetch")

    try:
        url, query_params = build_playbook_url(endpoint_name, params, api_key)

        logger.debug("Playbook API request: %s %s", url, query_params)

        resp = await client.get(url, params=query_params, timeout=30.0)

        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            logger.warning("Playbook API rate limited (429)")
            return None
        else:
            logger.warning("Playbook API returned %s: %s", resp.status_code, resp.text[:200])
            return None

    except PlaybookAPIError:
        raise
    except Exception as e:
        logger.exception("Playbook API fetch error for %s: %s", endpoint_name, e)
        return None


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def get_splits(league: str, client) -> Optional[Dict[str, Any]]:
    """Get betting splits for a league."""
    return await playbook_fetch("splits", {"league": league}, client=client)


async def get_injuries(league: str, client, report_date: str = None) -> Optional[Dict[str, Any]]:
    """Get injury report for a league."""
    params = {"league": league}
    if report_date:
        params["reportDate"] = report_date
    return await playbook_fetch("injuries", params, client=client)


async def get_lines(league: str, client) -> Optional[Dict[str, Any]]:
    """Get current betting lines for a league."""
    return await playbook_fetch("lines", {"league": league}, client=client)


async def get_teams(league: str, client, include_injuries: bool = False) -> Optional[Dict[str, Any]]:
    """Get team metadata for a league."""
    params = {"league": league}
    if include_injuries:
        params["injuries"] = "true"
    return await playbook_fetch("teams", params, client=client)


async def get_games(league: str, date: str, client) -> Optional[Dict[str, Any]]:
    """Get game objects for a league and date."""
    return await playbook_fetch("games", {"league": league, "date": date}, client=client)


async def get_odds_games(league: str, client) -> Optional[Dict[str, Any]]:
    """Get lightweight schedule with gameIds."""
    return await playbook_fetch("odds_games", {"league": league}, client=client)


async def get_splits_history(league: str, date: str, client) -> Optional[Dict[str, Any]]:
    """Get historical splits for a league and date."""
    return await playbook_fetch("splits_history", {"league": league, "date": date}, client=client)


async def get_api_usage(client) -> Optional[Dict[str, Any]]:
    """Get current API plan and usage info."""
    return await playbook_fetch("me", {}, client=client)
