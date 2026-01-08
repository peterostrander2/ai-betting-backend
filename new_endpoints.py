# new_endpoints.py - Complete API Integration
# Add to your FastAPI backend on Railway

import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, date
import hashlib

# ============================================
# API KEYS (Set in Railway Environment Variables)
# ============================================
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "ceb2e3a6a3302e0f38fd0d34150294e9")
PLAYBOOK_API_KEY = os.getenv("PLAYBOOK_API_KEY", "pbk_d6f65d6a74c53d5ef9b455a9a147c853b82b")

# API Base URLs
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
PLAYBOOK_API_BASE = "https://api.playbook-api.com/v1"

# Sport mapping for The Odds API
SPORT_KEYS = {
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "MLB": "baseball_mlb",
    "NHL": "icehockey_nhl",
    "NCAAB": "basketball_ncaab",
    "NCAAF": "americanfootball_ncaaf"
}

# ============================================
# MODELS
# ============================================

class VoteRequest(BaseModel):
    side: str

class VoteResponse(BaseModel):
    game_vote_id: str
    home: int
    away: int
    over: int
    under: int
    total: int
    userVote: Optional[str]

# ============================================
# IN-MEMORY STORAGE
# ============================================
votes_store = {}
graded_picks_store = []

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_user_id(request: Request) -> str:
    ip = request.client.host if request.client else "anonymous"
    return hashlib.md5(ip.encode()).hexdigest()[:12]

async def fetch_json(url: str, headers: dict = None) -> dict:
    """Helper to fetch JSON from external API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers or {})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"API Error: {url} - {e}")
            return None

# ============================================
# THE ODDS API - LIVE ODDS
# ============================================

@app.get("/live/odds/{sport}")
async def get_live_odds(sport: str):
    """Get live odds from 8+ sportsbooks via The Odds API"""
    sport_key = SPORT_KEYS.get(sport.upper(), "basketball_nba")
    
    url = f"{ODDS_API_BASE}/sports/{sport_key}/odds"
    params = f"?apiKey={ODDS_API_KEY}&regions=us&markets=spreads,totals,h2h&oddsFormat=american"
    
    data = await fetch_json(url + params)
    
    if not data:
        return {"games": [], "sport": sport, "updated_at": datetime.now().isoformat()}
    
    games = []
    for game in data:
        book_odds = {}
        best = {"spread_odds": -999, "over_odds": -999, "under_odds": -999, "home_ml": -999, "away_ml": -999}
        
        home_team = game.get("home_team", "")
        away_team = game.get("away_team", "")
        
        for bookmaker in game.get("bookmakers", []):
            book_name = bookmaker.get("key", "unknown").lower()
            book_data = {"spread": None, "spread_odds": -110, "total": None, "over_odds": -110, "under_odds": -110, "home_ml": None, "away_ml": None}
            
            for market in bookmaker.get("markets", []):
                if market["key"] == "spreads":
                    for outcome in market.get("outcomes", []):
                        if outcome["name"] == home_team:
                            book_data["spread"] = outcome.get("point", 0)
                            book_data["spread_odds"] = outcome.get("price", -110)
                            if book_data["spread_odds"] > best["spread_odds"]:
                                best["spread_odds"] = book_data["spread_odds"]
                                best["spread_book"] = book_name
                                
                elif market["key"] == "totals":
                    for outcome in market.get("outcomes", []):
                        book_data["total"] = outcome.get("point", 0)
                        if outcome["name"] == "Over":
                            book_data["over_odds"] = outcome.get("price", -110)
                            if book_data["over_odds"] > best["over_odds"]:
                                best["over_odds"] = book_data["over_odds"]
                                best["over_book"] = book_name
                        else:
                            book_data["under_odds"] = outcome.get("price", -110)
                            if book_data["under_odds"] > best["under_odds"]:
                                best["under_odds"] = book_data["under_odds"]
                                best["under_book"] = book_name
                                
                elif market["key"] == "h2h":
                    for outcome in market.get("outcomes", []):
                        if outcome["name"] == home_team:
                            book_data["home_ml"] = outcome.get("price", -110)
                            if book_data["home_ml"] > best["home_ml"]:
                                best["home_ml"] = book_data["home_ml"]
                                best["home_ml_book"] = book_name
                        else:
                            book_data["away_ml"] = outcome.get("price", -110)
                            if book_data["away_ml"] > best["away_ml"]:
                                best["away_ml"] = book_data["away_ml"]
                                best["away_ml_book"] = book_name
            
            book_odds[book_name] = book_data
        
        games.append({
            "home_team": home_team,
            "away_team": away_team,
            "time": game.get("commence_time", ""),
            "spread": book_odds.get("fanduel", {}).get("spread", 0),
            "total": book_odds.get("fanduel", {}).get("total", 0),
            "books": book_odds,
            "best": best
        })
    
    return {
        "games": games,
        "sport": sport,
        "books": list(set(b for g in games for b in g.get("books", {}).keys())),
        "updated_at": datetime.now().isoformat()
    }

# ============================================
# PLAYBOOK API - SHARP MONEY
# ============================================

@app.get("/sharp-money/{sport}")
async def get_sharp_money(sport: str):
    """Get sharp money signals from Playbook API"""
    headers = {"Authorization": f"Bearer {PLAYBOOK_API_KEY}"}
    
    url = f"{PLAYBOOK_API_BASE}/sharp-action/{sport.lower()}"
    data = await fetch_json(url, headers)
    
    if not data:
        # Fallback: return empty but valid response
        return {"signals": [], "sport": sport, "updated_at": datetime.now().isoformat()}
    
    signals = []
    for item in data.get("signals", data if isinstance(data, list) else []):
        signals.append({
            "game": item.get("game", item.get("matchup", "")),
            "sport": sport,
            "side": item.get("side", item.get("selection", "")),
            "line": item.get("line", item.get("spread", 0)),
            "book": item.get("book", "Consensus"),
            "divergence": item.get("divergence", item.get("sharp_vs_public", 0)),
            "direction": item.get("direction", "SHARP"),
            "strength": "STRONG" if abs(item.get("divergence", 0)) > 15 else "MODERATE",
            "timestamp": item.get("timestamp", datetime.now().isoformat())
        })
    
    return {"signals": signals, "sport": sport, "updated_at": datetime.now().isoformat()}

# ============================================
# PLAYBOOK API - BETTING SPLITS
# ============================================

@app.get("/live/splits/{sport}")
async def get_splits(sport: str):
    """Get public betting percentages from Playbook API"""
    headers = {"Authorization": f"Bearer {PLAYBOOK_API_KEY}"}
    
    url = f"{PLAYBOOK_API_BASE}/betting-splits/{sport.lower()}"
    data = await fetch_json(url, headers)
    
    if not data:
        return []
    
    splits = []
    for item in data if isinstance(data, list) else data.get("games", []):
        splits.append({
            "game": item.get("game", item.get("matchup", "")),
            "home_team": item.get("home_team", ""),
            "away_team": item.get("away_team", ""),
            "spread_home_pct": item.get("spread_home_pct", item.get("home_spread_pct", 50)),
            "spread_away_pct": item.get("spread_away_pct", item.get("away_spread_pct", 50)),
            "ml_home_pct": item.get("ml_home_pct", 50),
            "ml_away_pct": item.get("ml_away_pct", 50),
            "over_pct": item.get("over_pct", 50),
            "under_pct": item.get("under_pct", 50),
            "total_bets": item.get("total_bets", item.get("bet_count", 0))
        })
    
    return splits

# ============================================
# ESPN - INJURIES (FREE)
# ============================================

@app.get("/live/injuries/{sport}")
async def get_injuries(sport: str):
    """Get injuries from ESPN (free)"""
    sport_map = {"NBA": "basketball/nba", "NFL": "football/nfl", "MLB": "baseball/mlb", "NHL": "hockey/nhl"}
    espn_sport = sport_map.get(sport.upper(), "basketball/nba")
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/{espn_sport}/injuries"
    data = await fetch_json(url)
    
    if not data:
        return []
    
    injuries = []
    for team in data.get("teams", []):
        team_name = team.get("team", {}).get("displayName", "")
        for injury in team.get("injuries", []):
            injuries.append({
                "team": team_name,
                "player": injury.get("athlete", {}).get("displayName", ""),
                "position": injury.get("athlete", {}).get("position", {}).get("abbreviation", ""),
                "status": injury.get("status", ""),
                "injury": injury.get("type", {}).get("text", ""),
                "return_date": injury.get("details", {}).get("returnDate", "")
            })
    
    return injuries

# ============================================
# COMMUNITY VOTING
# ============================================

@app.get("/votes/{game_vote_id}")
async def get_votes(game_vote_id: str, request: Request):
    user_id = get_user_id(request)
    
    if game_vote_id not in votes_store:
        return VoteResponse(game_vote_id=game_vote_id, home=0, away=0, over=0, under=0, total=0, userVote=None)
    
    data = votes_store[game_vote_id]
    user_vote = data.get("user_votes", {}).get(user_id)
    
    return VoteResponse(
        game_vote_id=game_vote_id,
        home=data.get("home", 0),
        away=data.get("away", 0),
        over=data.get("over", 0),
        under=data.get("under", 0),
        total=sum([data.get(k, 0) for k in ["home", "away", "over", "under"]]),
        userVote=user_vote
    )

@app.post("/votes/{game_vote_id}")
async def submit_vote(game_vote_id: str, vote: VoteRequest, request: Request):
    user_id = get_user_id(request)
    
    if vote.side not in ["home", "away", "over", "under"]:
        raise HTTPException(status_code=400, detail="Invalid vote side")
    
    if game_vote_id not in votes_store:
        votes_store[game_vote_id] = {"home": 0, "away": 0, "over": 0, "under": 0, "user_votes": {}}
    
    data = votes_store[game_vote_id]
    
    if user_id in data["user_votes"]:
        old_vote = data["user_votes"][user_id]
        data[old_vote] = max(0, data[old_vote] - 1)
    
    data[vote.side] += 1
    data["user_votes"][user_id] = vote.side
    
    return VoteResponse(
        game_vote_id=game_vote_id,
        home=data["home"],
        away=data["away"],
        over=data["over"],
        under=data["under"],
        total=sum([data[k] for k in ["home", "away", "over", "under"]]),
        userVote=vote.side
    )

@app.get("/votes/leaderboard")
async def get_leaderboard():
    return {"weekly": [], "ai_record": {"correct": 0, "total": 0, "accuracy": 0}}

# ============================================
# GRADED PICKS
# ============================================

@app.get("/grader/picks")
async def get_graded_picks():
    return graded_picks_store

@app.post("/grader/grade")
async def grade_pick(data: dict):
    pick = {
        "id": data.get("pick_id", str(len(graded_picks_store))),
        "result": data.get("result"),
        "graded_at": datetime.now().isoformat()
    }
    graded_picks_store.append(pick)
    return {"success": True, "pick": pick}

# ============================================
# ESOTERIC - TODAY ENERGY
# ============================================

@app.get("/esoteric/today-energy")
async def get_today_energy():
    phases = ["New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous", 
              "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent"]
    moon = phases[datetime.now().timetuple().tm_yday % 8]
    
    today = datetime.now()
    digits = str(today.year) + str(today.month).zfill(2) + str(today.day).zfill(2)
    life_path = sum(int(d) for d in digits)
    while life_path > 9:
        life_path = sum(int(d) for d in str(life_path))
    
    zodiacs = [(120, "Capricorn"), (219, "Aquarius"), (320, "Pisces"), (420, "Aries"),
               (521, "Taurus"), (621, "Gemini"), (722, "Cancer"), (823, "Leo"),
               (923, "Virgo"), (1023, "Libra"), (1122, "Scorpio"), (1222, "Sagittarius"), (1231, "Capricorn")]
    date_num = today.month * 100 + today.day
    zodiac = next((sign for cutoff, sign in zodiacs if date_num <= cutoff), "Capricorn")
    
    return {
        "moon_phase": moon,
        "moon_meaning": {"Full Moon": "High volatility - expect upsets", "New Moon": "Fresh starts - take calculated risks"}.get(moon, "Normal energy"),
        "life_path": life_path,
        "life_path_meaning": {1: "Leadership day - favorites strong", 5: "Change day - underdogs bark", 7: "Spiritual day - trust the model"}.get(life_path, "Standard day"),
        "zodiac": zodiac,
        "zodiac_meaning": {"Aries": "Fire energy - overs hit", "Leo": "Fire energy - star players shine"}.get(zodiac, "Neutral energy"),
        "date": date.today().isoformat()
    }
