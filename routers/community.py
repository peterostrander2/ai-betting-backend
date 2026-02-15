"""
COMMUNITY.PY - Community Features Router

Community voting and affiliate link endpoints.

Endpoints:
    GET  /community/votes/{game_id}  - Get community sentiment votes
    POST /community/vote             - Submit a community vote
    GET  /community/leaderboard      - Get games with most engagement
    GET  /affiliate/links            - Get affiliate links for sportsbooks
    POST /affiliate/configure        - Configure affiliate link
"""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends

from core.auth import verify_api_key

router = APIRouter(tags=["community"])

# In-memory storage for community votes (use Redis/DB for production persistence)
_community_votes: Dict[str, Dict[str, int]] = {}

# Affiliate links for sportsbooks (configure your affiliate IDs here)
AFFILIATE_LINKS = {
    "draftkings": {
        "base_url": "https://sportsbook.draftkings.com",
        "affiliate_id": "",
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
    side = vote_data.get("side", "").lower()

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
    book = config_data.get("book", "").lower()
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
