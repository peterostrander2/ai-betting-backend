"""
LINE_SHOP.PY - Line Shopping & Betslip Router

Line shopping, betslip generation, and sportsbook configuration.

Endpoints:
    GET  /line-shop/{sport}   - Get odds from multiple sportsbooks for line shopping
    GET  /betslip/generate    - Generate deep links for placing a specific bet
    GET  /sportsbooks         - List all supported sportsbooks with branding info
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from core.auth import verify_api_key
from core.sportsbooks import SPORTSBOOK_CONFIGS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["line-shop"])

# Sport mappings for validation
SPORT_MAPPINGS = {
    "nba": {"odds": "basketball_nba", "espn": "basketball/nba", "playbook": "NBA"},
    "nfl": {"odds": "americanfootball_nfl", "espn": "football/nfl", "playbook": "NFL"},
    "mlb": {"odds": "baseball_mlb", "espn": "baseball/mlb", "playbook": "MLB"},
    "nhl": {"odds": "icehockey_nhl", "espn": "hockey/nhl", "playbook": "NHL"},
    "ncaab": {"odds": "basketball_ncaab", "espn": "basketball/mens-college-basketball", "playbook": "NCAAB"},
}

# Odds API configuration
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE = os.getenv("ODDS_API_BASE", "https://api.the-odds-api.com/v4")


# Simple TTL cache for line-shop responses
_line_shop_cache: Dict[str, Dict[str, Any]] = {}


def _cache_get(key: str) -> Optional[Dict]:
    """Get cached value if not expired."""
    entry = _line_shop_cache.get(key)
    if entry and entry.get("expires_at", 0) > datetime.now().timestamp():
        return entry.get("data")
    return None


def _cache_set(key: str, data: Dict, ttl: int = 120):
    """Set cache value with TTL in seconds."""
    _line_shop_cache[key] = {
        "data": data,
        "expires_at": datetime.now().timestamp() + ttl
    }


def _sanitize_public(payload: dict) -> dict:
    """Sanitize payload for public output. Imports sanitizer if available."""
    try:
        from utils.public_payload_sanitizer import sanitize_public_payload
        return sanitize_public_payload(payload)
    except Exception:
        return payload


def generate_sportsbook_link(book_key: str, event_id: str, sport: str) -> Optional[Dict[str, str]]:
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
            "note": "Opens DraftKings with bet on slip"
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
                "note": "Opens FanDuel with bet on slip"
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
            "note": "Opens BetMGM event page"
        }

    elif book_key == "caesars" and event_id:
        return {
            "web": f"{base_url}/us/{sport_path}/event/{event_id}",
            "mobile": f"caesarssportsbook://event/{event_id}",
            "type": "event",
            "note": "Opens Caesars event page"
        }

    # Fallback: Sport-specific page
    return {
        "web": f"{base_url}/{sport_path}",
        "mobile": config.get("app_scheme", ""),
        "type": "sport_page",
        "note": f"Opens {config['name']} {sport.upper()} page"
    }


def generate_fallback_line_shop(sport: str) -> List[Dict[str, Any]]:
    """Return empty list when line shop data is unavailable. No sample data."""
    return []


def generate_fallback_betslip(sport: str, game_id: str, bet_type: str, selection: str) -> Dict[str, Any]:
    """Return empty betslip response when data is unavailable. No sample data."""
    return {
        "sport": sport.upper(),
        "game_id": game_id,
        "game": None,
        "bet_type": bet_type,
        "selection": selection,
        "source": "unavailable",
        "data_status": "NO_DATA",
        "best_odds": None,
        "all_books": [],
        "count": 0,
        "timestamp": datetime.now().isoformat(),
        "message": "No betting data available for this game"
    }


async def _fetch_odds_api(url: str, params: Dict[str, Any]) -> Optional[Dict]:
    """Fetch from Odds API with retry logic."""
    try:
        from odds_api import odds_api_get
        resp, used = await odds_api_get(url, params)
        if resp and resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        logger.warning("Odds API fetch error: %s", e)
        return None


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
    cached = _cache_get(cache_key)
    if cached:
        return JSONResponse(_sanitize_public(cached))

    sport_config = SPORT_MAPPINGS[sport_lower]

    try:
        odds_url = f"{ODDS_API_BASE}/sports/{sport_config['odds']}/odds"
        data = await _fetch_odds_api(
            odds_url,
            {
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "spreads,h2h,totals",
                "oddsFormat": "american",
                "includeLinks": "true",
                "includeSids": "true"
            }
        )

        if not data:
            # Use fallback data when API unavailable
            logger.warning("Odds API unavailable for line-shop, using fallback data")
            line_shop_data = generate_fallback_line_shop(sport_lower)
            result = {
                "sport": sport.upper(),
                "source": "fallback",
                "count": len(line_shop_data),
                "sportsbooks": list(SPORTSBOOK_CONFIGS.keys()),
                "data": line_shop_data,
                "timestamp": datetime.now().isoformat()
            }
            _cache_set(cache_key, result, ttl=120)
            return JSONResponse(_sanitize_public(result))

        games = data if isinstance(data, list) else data.get("data", [])
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

        _cache_set(cache_key, result, ttl=120)  # 2 min cache for line shopping
        return JSONResponse(_sanitize_public(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Line shopping fetch failed: %s, using fallback", e)
        # Return fallback data on any error
        line_shop_data = generate_fallback_line_shop(sport_lower)
        result = {
            "sport": sport.upper(),
            "source": "fallback",
            "count": len(line_shop_data),
            "sportsbooks": list(SPORTSBOOK_CONFIGS.keys()),
            "data": line_shop_data,
            "timestamp": datetime.now().isoformat()
        }
        _cache_set(cache_key, result, ttl=120)
        return JSONResponse(_sanitize_public(result))


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
        data = await _fetch_odds_api(
            odds_url,
            {
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": bet_type + "s" if bet_type in ["spread", "total"] else bet_type,
                "oddsFormat": "american",
                "includeLinks": "true",
                "includeSids": "true"
            }
        )

        if not data:
            # Use fallback data when API unavailable
            logger.warning("Odds API unavailable for betslip, using fallback data")
            return generate_fallback_betslip(sport_lower, game_id, bet_type, selection)

        games = data if isinstance(data, list) else data.get("data", [])
        target_game = None

        for game in games:
            if game.get("id") == game_id:
                target_game = game
                break

        if not target_game:
            # Game not found in API, use fallback
            logger.warning("Game %s not found, using fallback data", game_id)
            return generate_fallback_betslip(sport_lower, game_id, bet_type, selection)

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
        logger.exception("Betslip generation failed: %s, using fallback", e)
        # Return fallback data on any error
        return generate_fallback_betslip(sport_lower, game_id, bet_type, selection)


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
